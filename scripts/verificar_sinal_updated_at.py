"""Sonda P1 (L4.1) — mede o `updated_at` gravado na exclusão lógica.

Serve de evidência para o relatório L4_1: verifica se o timestamp da oferta
coincide com o da turma na exclusão lógica e se isso DISCRIMINA a oferta que
já estava inativa antes da exclusão. SQLite e PostgreSQL scratch.

Uso:
  python scripts/verificar_sinal_updated_at.py
  python scripts/verificar_sinal_updated_at.py --db pautaon_ensaio
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import make_url, text

from config import Config

MARCA = "SONDA_L41"
D_INI = date(2026, 2, 2)
D_FIM = date(2026, 6, 30)
D_AULA = date(2026, 3, 2)


class _Cfg(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db")
    args = parser.parse_args()

    dsn = "sqlite:///:memory:"
    if args.db:
        raw = os.getenv("DATABASE_URL")
        if not raw:
            from dotenv import dotenv_values

            raw = dotenv_values(os.path.join(os.getcwd(), ".env")).get("DATABASE_URL")
        dsn = make_url(raw).set(database=args.db).render_as_string(hide_password=False)
        if "ensaio" not in make_url(dsn).database:
            raise SystemExit("sonda recusada fora do banco scratch.")
    _Cfg.SQLALCHEMY_DATABASE_URI = dsn
    os.environ["DATABASE_URL"] = dsn

    from app import create_app
    from app.database import db
    from app.models import (
        Aluno, Curso, Frequencia, Inscricao, PeriodoLetivo, Turma, TurmaCurso,
        Unidade, User,
    )

    app = create_app(_Cfg)
    with app.app_context():
        print(f"=== sonda updated_at ({db.engine.dialect.name}) ===")
        if db.engine.dialect.name == "sqlite":
            db.create_all()

        log_base = db.session.execute(text("SELECT coalesce(max(id),0) FROM log_acao")).scalar()
        un = Unidade(nome=f"{MARCA} Un", ativo=True)
        db.session.add(un)
        db.session.flush()
        admin = User(name=f"{MARCA} Admin", email=f"{MARCA.lower()}@example.com",
                     role="admin", first_login=False, unidade_id=un.id)
        admin.set_password("SenhaLocal!123")
        db.session.add(admin)
        db.session.flush()
        per = PeriodoLetivo(nome=f"{MARCA} Per", data_inicio=D_INI,
                            data_fim=D_FIM, unidade_id=un.id, ativo=True)
        db.session.add(per)
        db.session.flush()
        t = Turma(nome=f"{MARCA} Turma", turno="Manhã", data_inicio=D_INI,
                  data_fim=D_FIM, periodo_letivo_id=per.id,
                  unidade_id=un.id, ativo=True)
        db.session.add(t)
        db.session.flush()
        ids = {}
        for letra, principal in (("A", True), ("B", False)):
            c = Curso(nome=f"{MARCA} Curso {letra}", unidade_id=un.id, ativo=True)
            db.session.add(c)
            db.session.flush()
            o = TurmaCurso(turma_id=t.id, curso_id=c.id, unidade_id=un.id,
                           programa=f"{MARCA} P", ativo=True,
                           principal=principal)
            db.session.add(o)
            db.session.flush()
            ids[letra] = (o.id, c.id)
        al = Aluno(nome=f"{MARCA} Aluno", unidade_id=un.id, ativo=True)
        db.session.add(al)
        db.session.flush()
        ins = Inscricao(aluno_id=al.id, turma_id=t.id, turma_curso_id=ids["A"][0],
                        ativo=True, data_inicio=D_INI)
        db.session.add(ins)
        # histórico -> força exclusão LÓGICA
        db.session.add(Frequencia(aluno_id=al.id, turma_id=t.id,
                                  turma_curso_id=ids["A"][0], data=D_AULA,
                                  conceito="A", unidade_id=un.id))
        db.session.commit()

        # B sai do curso ANTES da exclusão (equivalente a `desativar_oferta`)
        db.session.get(TurmaCurso, ids["B"][0]).ativo = False
        db.session.commit()
        db.session.expire_all()

        ts = {k: (db.session.get(TurmaCurso, v[0]).updated_at) for k, v in ids.items()}
        print(f"antes: turma={db.session.get(Turma, t.id).updated_at} "
              f"A={ts['A']} B={ts['B']}")

        client = app.test_client()
        with client.session_transaction() as sess:
            sess["_user_id"] = str(admin.id)
            sess["_fresh"] = True
            sess["unidade_id"] = un.id
        r = client.post(f"/turma/excluir/{t.id}")
        print(f"POST /turma/excluir -> {r.status_code}")
        db.session.expire_all()

        turma = db.session.get(Turma, t.id)
        a = db.session.get(TurmaCurso, ids["A"][0])
        b = db.session.get(TurmaCurso, ids["B"][0])
        i = db.session.get(Inscricao, ins.id)
        print(f"depois: turma.ativo={turma.ativo} A.ativo={a.ativo} B.ativo={b.ativo}")
        print(f"  turma.updated_at = {turma.updated_at!r}")
        print(f"  A.updated_at     = {a.updated_at!r}")
        print(f"  B.updated_at     = {b.updated_at!r}  (B estava INATIVA antes)")
        print(f"  ins.updated_at   = {i.updated_at!r}")
        print(f"  igualdade turma==A: {turma.updated_at == a.updated_at}")
        print(f"  igualdade turma==B: {turma.updated_at == b.updated_at}  "
              f"<- True significa que updated_at NÃO discrimina")

        logs = db.session.execute(
            text("SELECT acao, count(*) FROM log_acao WHERE id > :b GROUP BY acao "
                 "ORDER BY acao"), {"b": log_base}).fetchall()
        print("  LogAcao do listener nesta transação:", logs)

        if db.engine.dialect.name == "postgresql":
            db.session.execute(text("DELETE FROM frequencia WHERE turma_id = :t"), {"t": t.id})
            db.session.execute(text("DELETE FROM inscricoes WHERE turma_id = :t"), {"t": t.id})
            db.session.execute(text("DELETE FROM turma_curso WHERE turma_id = :t"), {"t": t.id})
            db.session.execute(text("DELETE FROM turma WHERE id = :t"), {"t": t.id})
            for cid in (ids["A"][1], ids["B"][1]):
                db.session.execute(text("DELETE FROM curso WHERE id = :i"), {"i": cid})
            db.session.execute(text("DELETE FROM aluno WHERE id = :i"), {"i": al.id})
            db.session.execute(text("DELETE FROM periodo_letivo WHERE id = :i"), {"i": per.id})
            db.session.execute(text("DELETE FROM log_acao WHERE id > :b"), {"b": log_base})
            db.session.execute(text('DELETE FROM "user" WHERE id = :i'), {"i": admin.id})
            db.session.execute(text("DELETE FROM unidade WHERE id = :i"), {"i": un.id})
            db.session.commit()
            sobra = db.session.execute(
                text("SELECT count(*) FROM turma WHERE nome LIKE :p"),
                {"p": f"{MARCA}%"}).scalar()
            print(f"  limpeza: turmas da sonda restantes = {sobra}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
