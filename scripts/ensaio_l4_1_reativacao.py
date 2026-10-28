"""Ensaio L4.1 — ciclo completo de exclusão lógica e reativação seletiva.

Roda o fluxo REAL pelas rotas (desativar oferta → excluir turma → lixeira →
reativar) e confere o comportamento-alvo da L4.1:

  1. turma com ofertas A (principal) e B, aluno com inscrições e lançamentos;
  2. B é REMOVIDA DO CURSO antes da exclusão (`turma_oferta_desativar`);
  3. exclusão LÓGICA (`excluir_turma`) — grava o LogAcao-marcador só com A;
  4. lixeira (`/turmas/lixeira`) pré-marca A e mostra B como "desativada antes";
  5. reativação (`/turmas/reativar/<id>`) devolve A e a inscrição do aluno
     ativo; B continua inativa; lançamentos/diário/conselho intactos
     (fingerprint por tabela) e o principal intocado;
  6. segundo ciclo com escolha EXPLÍCITA (A + B) — as duas voltam, ainda com
     um único principal;
  7. limpeza do scratch (nada fica).

Uso:
  python scripts/ensaio_l4_1_reativacao.py              # SQLite em memória
  python scripts/ensaio_l4_1_reativacao.py --db pautaon_ensaio   # PostgreSQL

O ensaio em PostgreSQL só é aceito em banco cujo nome contenha "ensaio" —
nunca contra a base de produção.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func, make_url, text

from config import Config

DATA_INI = date(2026, 2, 2)
DATA_FIM = date(2026, 6, 30)
MARCA = "ENSAIO_L41"

#: tabelas cujo conteúdo NÃO pode mudar no ciclo (imutáveis pela reativação)
IMUTAVEIS = {
    "frequencia": "turma_id",
    "registro_aula": "turma_id",
    "conselho_classe": "turma_id",
    "transferencia": "turma_origem_id",
}

_falhas: list[str] = []


def _marcada(html: str, oferta_id: int) -> bool:
    """True se a caixa da oferta vem `checked` no HTML da lixeira."""
    achado = re.search(rf'<input[^>]*value="{oferta_id}"[^>]*>', html)
    return bool(achado and "checked" in achado.group(0))


def confere(rotulo: str, condition: bool) -> bool:
    """Registra o resultado de um ponto de conferência (não interrompe)."""
    print(f"  [{'OK  ' if condition else 'FALHA'}] {rotulo}")
    if not condition:
        _falhas.append(rotulo)
    return bool(condition)


def _dsn(args) -> str:
    if not args.db:
        return "sqlite:///:memory:"
    raw = os.getenv("DATABASE_URL")
    if not raw:
        from dotenv import dotenv_values

        raw = dotenv_values(os.path.join(os.getcwd(), ".env")).get("DATABASE_URL")
    if not raw:
        raise SystemExit("--db exige DATABASE_URL base no ambiente ou no .env.")
    return make_url(raw).set(database=args.db).render_as_string(hide_password=False)


class _Cfg(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False


def _fingerprint(tabela: str, coluna: str, turma_id: int) -> str:
    """Hash do conteúdo bruto da tabela para a turma (sem ORM, sem cache)."""
    linhas = db.session.execute(
        text(f"SELECT * FROM {tabela} WHERE {coluna} = :t ORDER BY id"),
        {"t": turma_id},
    ).fetchall()
    corpo = "|".join(repr(tuple(l)) for l in linhas)
    return f"{len(linhas)}:{hashlib.sha1(corpo.encode()).hexdigest()[:12]}"


def _estado(turma_id: int) -> dict:
    from app.models import Inscricao, Turma, TurmaCurso

    turma = db.session.get(Turma, turma_id)
    ofertas = {
        o.id: (o.ativo, o.principal)
        for o in TurmaCurso.query.filter_by(turma_id=turma_id).order_by(TurmaCurso.id)
    }
    inscricoes = {
        i.id: (i.ativo, i.motivo_desativacao)
        for i in Inscricao.query.filter_by(turma_id=turma_id).order_by(Inscricao.id)
    }
    return {
        "turma": turma.ativo if turma else None,
        "ofertas": ofertas,
        "inscricoes": inscricoes,
    }


def _limpeza(ids: dict, log_base: int) -> None:
    """Remove tudo o que o ensaio criou (ordem das dependências de FK)."""
    turma_id = ids["turma"]
    for tabela, coluna in (("frequencia", "turma_id"), ("registro_aula", "turma_id"),
                           ("conselho_classe", "turma_id"), ("dia_bloqueado_turma", "turma_id"),
                           ("inscricoes", "turma_id")):
        db.session.execute(text(f"DELETE FROM {tabela} WHERE {coluna} = :t"), {"t": turma_id})
    db.session.execute(
        text("DELETE FROM transferencia WHERE turma_origem_id = :t OR turma_destino_id = :t"),
        {"t": turma_id},
    )
    db.session.execute(
        text("DELETE FROM turma_curso_horario WHERE turma_curso_id IN "
             "(SELECT id FROM turma_curso WHERE turma_id = :t)"),
        {"t": turma_id},
    )
    db.session.execute(text("DELETE FROM turma_curso WHERE turma_id = :t"), {"t": turma_id})
    db.session.execute(text("DELETE FROM turma WHERE id = :t"), {"t": turma_id})
    for cid in ids["cursos"]:
        db.session.execute(text("DELETE FROM curso WHERE id = :i"), {"i": cid})
    db.session.execute(text("DELETE FROM aluno WHERE id IN (:a1,:a2)"),
                       {"a1": ids["aluno_ativo"], "a2": ids["aluno_inativo"]})
    db.session.execute(text("DELETE FROM periodo_letivo WHERE id = :i"),
                       {"i": ids["periodo"]})
    db.session.execute(text("DELETE FROM log_acao WHERE id > :b"), {"b": log_base})
    db.session.execute(text('DELETE FROM "user" WHERE id = :i'), {"i": ids["admin"]})
    db.session.execute(text("DELETE FROM unidade WHERE id = :i"), {"i": ids["un"]})
    db.session.commit()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", help="nome do banco PG (mantém credenciais do .env)")
    parser.add_argument(
        "--manter", action="store_true",
        help="não limpa o scratch (para inspecionar o estado depois do ensaio)",
    )
    args = parser.parse_args()

    global db
    dsn = _dsn(args)
    os.environ["DATABASE_URL"] = dsn
    if dsn.startswith("postgresql") and "ensaio" not in make_url(dsn).database:
        raise SystemExit(
            "Ensaio recusado: ensaios PostgreSQL só no banco scratch "
            "(--db pautaon_ensaio)."
        )
    _Cfg.SQLALCHEMY_DATABASE_URI = dsn

    from app import create_app
    from app.database import db as _db

    db = _db
    app = create_app(_Cfg)
    scratch = dsn.startswith("postgresql")
    logs: list[str] = []

    with app.app_context():
        from app.models import (
            Aluno, ConselhoClasse, Curso, Frequencia, Inscricao, LogAcao,
            PeriodoLetivo, RegistroAula, Turma, TurmaCurso, Unidade, User,
        )
        from app.models.enums import EtapaConselho
        from app.services.turma_curso import (
            ACAO_EXCLUSAO_LOGICA_TURMA, MOTIVO_TURMA_DESATIVADA,
            parsear_marcador_exclusao,
        )

        print(f"=== Ensaio L4.1 ({db.engine.dialect.name}) ===")
        if not scratch:
            db.create_all()

        log_base = db.session.query(func.max(LogAcao.id)).scalar() or 0

        # ------------------------------------------------------------------
        # 1. semeadura
        # ------------------------------------------------------------------
        un = Unidade(nome=f"{MARCA} Unidade", ativo=True)
        db.session.add(un)
        db.session.flush()
        admin = User(
            name=f"{MARCA} Admin", email=f"{MARCA.lower()}.admin@example.com",
            role="admin", first_login=False, unidade_id=un.id,
        )
        admin.set_password("SenhaLocal!123")
        db.session.add(admin)
        db.session.flush()
        periodo = PeriodoLetivo(
            nome=f"{MARCA} Periodo", data_inicio=DATA_INI,
            data_fim=date(2026, 3, 31), unidade_id=un.id, ativo=True,
        )
        db.session.add(periodo)
        db.session.flush()
        turma = Turma(
            nome=f"{MARCA} Turma", turno="Manhã", data_inicio=DATA_INI,
            data_fim=DATA_FIM, periodo_letivo_id=periodo.id,
            unidade_id=un.id, ativo=True,
        )
        db.session.add(turma)
        db.session.flush()

        ids_oferta = {}
        cursos = []
        for nome_curso, principal in (("A", True), ("B", False)):
            curso = Curso(nome=f"{MARCA} Curso {nome_curso}", unidade_id=un.id, ativo=True)
            db.session.add(curso)
            db.session.flush()
            cursos.append(curso.id)
            oferta = TurmaCurso(
                turma_id=turma.id, curso_id=curso.id, unidade_id=un.id,
                programa=f"{MARCA} Programa", ativo=True, principal=principal,
            )
            db.session.add(oferta)
            db.session.flush()
            ids_oferta[nome_curso] = oferta.id

        ativo = Aluno(nome=f"{MARCA} Aluno Ativo", unidade_id=un.id, ativo=True)
        inativo = Aluno(nome=f"{MARCA} Aluno Inativo", unidade_id=un.id, ativo=False)
        db.session.add_all([ativo, inativo])
        db.session.flush()
        inscricoes = {}
        for rotulo, al in (("ativo", ativo), ("inativo", inativo)):
            i1 = Inscricao(
                aluno_id=al.id, turma_id=turma.id, turma_curso_id=ids_oferta["A"],
                ativo=True, data_inicio=DATA_INI,
            )
            db.session.add(i1)
            db.session.flush()
            inscricoes[rotulo] = i1.id
        i2 = Inscricao(
            aluno_id=ativo.id, turma_id=turma.id, turma_curso_id=ids_oferta["B"],
            ativo=True, data_inicio=DATA_INI,
        )
        db.session.add(i2)
        db.session.flush()
        inscricoes["b"] = i2.id

        # lançamentos (frequência), diário e conselho — o que a reativação
        # tem de preservar byte a byte
        for dia in (date(2026, 3, 2), date(2026, 3, 4)):
            db.session.add(Frequencia(
                aluno_id=ativo.id, turma_id=turma.id, turma_curso_id=ids_oferta["A"],
                data=dia, conceito="A", unidade_id=un.id,
            ))
        db.session.add(RegistroAula(
            turma_id=turma.id, turma_curso_id=ids_oferta["A"], data=date(2026, 3, 2),
            observacoes=f"{MARCA} diário", unidade_id=un.id,
        ))
        db.session.add(ConselhoClasse(
            turma_id=turma.id, turma_curso_id=ids_oferta["A"], aluno_id=ativo.id,
            etapa=EtapaConselho.INICIAL, unidade_id=un.id,
        ))
        db.session.commit()

        ids = {
            "un": un.id, "admin": admin.id, "periodo": periodo.id, "turma": turma.id,
            "cursos": cursos, "a": ids_oferta["A"], "b": ids_oferta["B"],
            "aluno_ativo": ativo.id, "aluno_inativo": inativo.id,
            "insc_ativo": inscricoes["ativo"], "insc_inativo": inscricoes["inativo"],
            "insc_b": inscricoes["b"],
        }
        antes = {t: _fingerprint(t, c, turma.id) for t, c in IMUTAVEIS.items()}

        client = app.test_client()
        with client.session_transaction() as sess:
            sess["_user_id"] = str(admin.id)
            sess["_fresh"] = True
            sess["unidade_id"] = un.id

        # ------------------------------------------------------------------
        # 2. B sai do curso ANTES da exclusão (rota real)
        # ------------------------------------------------------------------
        r = client.post(f"/turma/oferta/{ids['b']}/desativar")
        confere("POST /turma/oferta/B/desativar aceito", r.status_code == 302)
        db.session.expire_all()

        # ------------------------------------------------------------------
        # 3. exclusão lógica (rota real) + marcador
        # ------------------------------------------------------------------
        r = client.post(f"/turma/excluir/{ids['turma']}")
        confere("POST /turma/excluir aceito", r.status_code == 302)
        db.session.expire_all()

        est = _estado(ids["turma"])
        confere("turma inativa após a exclusão", est["turma"] is False)
        confere("A e B inativas após a exclusão",
                all(not ativa for ativa, _ in est["ofertas"].values()))
        confere("inscrições desativadas com o motivo da turma",
                all(m == MOTIVO_TURMA_DESATIVADA for _, m in est["inscricoes"].values()))

        marcador_row = db.session.execute(
            text("SELECT detalhes FROM log_acao WHERE acao = :a AND detalhes LIKE :p "
                 "ORDER BY id DESC LIMIT 1"),
            {"a": ACAO_EXCLUSAO_LOGICA_TURMA, "p": f"turma_id={ids['turma']} %"},
        ).scalar()
        confere("marcador LogAcao gravado na exclusão", marcador_row is not None)
        marcador = parsear_marcador_exclusao(marcador_row) if marcador_row else None
        confere("marcador lista só A (a que estava ativa)",
                marcador is not None and marcador["ofertas"] == [ids["a"]])
        confere("marcador lista as inscrições desativadas",
                marcador is not None
                and set(marcador["inscricoes"]) == set(est["inscricoes"]))

        # ------------------------------------------------------------------
        # 4. lixeira: pré-marca A, mostra B como "desativada antes"
        # ------------------------------------------------------------------
        r = client.get("/turmas/lixeira")
        corpo = r.get_data(as_text=True)
        confere("GET /turmas/lixeira 200", r.status_code == 200)
        confere("caixa de A vem marcada (desativada na exclusão da turma)",
                _marcada(corpo, ids["a"]) and "desativado na exclusão da turma" in corpo)
        confere("caixa de B vem DESMARCADA (desativada antes / origem desconhecida)",
                not _marcada(corpo, ids["b"])
                and "desativado antes / origem desconhecida" in corpo)

        # ------------------------------------------------------------------
        # 5. reativação com a pré-seleção do marcador
        # ------------------------------------------------------------------
        r = client.post(f"/turmas/reativar/{ids['turma']}", data={
            "confirmar_periodo": "1", "selecao_explicita": "1",
            "oferta_ids": str(ids["a"]),
        })
        confere("POST /turmas/reativar aceito", r.status_code == 302)
        db.session.expire_all()

        est = _estado(ids["turma"])
        confere("turma reativada", est["turma"] is True)
        confere("A voltou ativa", est["ofertas"][ids["a"]] == (True, True))
        confere("B permanece INATIVA (desativada antes da exclusão)",
                est["ofertas"][ids["b"]][0] is False)
        confere("principal continua em A, único", est["ofertas"][ids["a"]][1] is True
                and sum(1 for _, p in est["ofertas"].values() if p) == 1)
        confere("inscrição do aluno ativo voltou",
                est["inscricoes"][ids["insc_ativo"]][0] is True)
        confere("inscrição do aluno INATIVO permanece inativa",
                est["inscricoes"][ids["insc_inativo"]][0] is False
                and est["inscricoes"][ids["insc_inativo"]][1] == MOTIVO_TURMA_DESATIVADA)
        confere("inscrição da oferta B não voltou (oferta continua fora)",
                est["inscricoes"][ids["insc_b"]][0] is False)

        depois = {t: _fingerprint(t, c, ids["turma"]) for t, c in IMUTAVEIS.items()}
        for tabela, valor in antes.items():
            logs.append(f"{tabela}: {valor} -> {depois[tabela]}")
            confere(f"{tabela} preservada no ciclo (fingerprint)", depois[tabela] == valor)

        # ------------------------------------------------------------------
        # 6. novo ciclo com escolha explícita (A + B)
        # ------------------------------------------------------------------
        client.post(f"/turma/excluir/{ids['turma']}")
        db.session.expire_all()
        r = client.post(f"/turmas/reativar/{ids['turma']}", data={
            "confirmar_periodo": "1", "selecao_explicita": "1",
            "oferta_ids": [str(ids["a"]), str(ids["b"])],
        })
        confere("reativação com A+B marcada aceita", r.status_code == 302)
        db.session.expire_all()
        est = _estado(ids["turma"])
        confere("A e B ativas na reativação explícita",
                est["ofertas"][ids["a"]][0] and est["ofertas"][ids["b"]][0])
        confere("ainda exatamente 1 principal (A)",
                sum(1 for _, p in est["ofertas"].values() if p) == 1)
        confere("inscrição da oferta B voltou com a oferta",
                est["inscricoes"][ids["insc_b"]][0] is True)
        marcadores = db.session.execute(
            text("SELECT count(*) FROM log_acao WHERE acao = :a AND detalhes LIKE :p"),
            {"a": ACAO_EXCLUSAO_LOGICA_TURMA, "p": f"turma_id={ids['turma']} %"},
        ).scalar()
        confere("dois ciclos = dois marcadores (sem duplicidade por reativação)",
                marcadores == 2)

        # ------------------------------------------------------------------
        # 7. recusa atômica: estado da variante P2 (duas marcas de principal,
        #    uma delas em oferta inativa) — a reativação não pode parcial
        # ------------------------------------------------------------------
        client.post(f"/turma/excluir/{ids['turma']}")
        db.session.expire_all()
        # B inativa pode conservar principal=True: o índice parcial
        # `uix_turma_curso_principal` filtra por `principal AND ativo`.
        oferta_b = db.session.get(TurmaCurso, ids["b"])
        oferta_a = db.session.get(TurmaCurso, ids["a"])
        oferta_b.principal = True
        db.session.commit()
        db.session.expire_all()
        r = client.post(f"/turmas/reativar/{ids['turma']}", data={
            "confirmar_periodo": "1", "selecao_explicita": "1",
            "oferta_ids": [str(ids["a"]), str(ids["b"])],
        }, follow_redirects=True)
        db.session.expire_all()
        est = _estado(ids["turma"])
        confere("violação de principal recusada sem alteração parcial",
                est["turma"] is False
                and not any(ativa for ativa, _ in est["ofertas"].values())
                and not any(ativa for ativa, _ in est["inscricoes"].values()))
        confere("mensagem de recusa fala do curso principal",
                "curso principal" in r.get_data(as_text=True))
        # deixa o estado coerente para a limpeza
        oferta_b = db.session.get(TurmaCurso, ids["b"])
        oferta_a = db.session.get(TurmaCurso, ids["a"])
        oferta_b.principal = False
        oferta_a.principal = True
        db.session.commit()
        del oferta_a, oferta_b

        # ------------------------------------------------------------------
        # 8. limpeza
        # ------------------------------------------------------------------
        if args.manter:
            print("\n--manter: nada foi removido do scratch.")
        else:
            _limpeza(ids, log_base)
            db.session.expire_all()
            sobra = db.session.execute(
                text("SELECT count(*) FROM turma WHERE nome LIKE :p"),
                {"p": f"{MARCA}%"},
            ).scalar()
            sobra_log = db.session.execute(
                text("SELECT count(*) FROM log_acao WHERE id > :b"), {"b": log_base}
            ).scalar()
            confere("scratch limpo (turmas e logs do ensaio = 0)",
                    sobra == 0 and sobra_log == 0)

    print("\nfingerprints das tabelas-chave:")
    for linha in logs:
        print(f"  {linha}")

    if _falhas:
        print(f"\n{len(_falhas)} conferência(s) com falha:")
        for f in _falhas:
            print(f"  - {f}")
        return 1
    print("\nEnsaio L4.1: todas as conferências passaram.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
