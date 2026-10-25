"""
Verificação da Onda 4 — Etapa M1.1 (enturmação por curso: inscrições NULL).

Uso (com o banco de destino ativo via .env):
    python scripts/verificar_onda4_m1.py

Somente LEITURA: nenhum INSERT/UPDATE/DELETE. Uma linha OK/AVISO/FALHA por
checagem. Exit code 0 = sem violação de integridade; 1 = alguma checagem de
integridade falhou. Checagens marcadas como AVISO não impactam o código de
saída (são decisões de dados/backfill, não corrupção).

Relata:
    (a) Inscrições ATIVAS com turma_curso_id NULL, por turma, classificadas
        pelo nº de ofertas ativas da turma:
            1  = backfill seguro (dá para vincular sem ambiguidade);
            2+ = decisão manual (secretaria precisa escolher o curso);
            0  = turma sem oferta ativa (não há para onde vincular).
    (b) Duplicatas ATIVAS por (aluno_id, turma_curso_id) com turma_curso_id
        NOT NULL — mesmo aluno duas vezes na mesma oferta (FALHA).
    (c) Inscrições ativas apontando para oferta INATIVA (inconsistência
        legada; AVISO).
"""
from __future__ import annotations

import sys

from app import create_app


def _linha(status: str, msg: str) -> bool:
    """Imprime uma linha de checagem e retorna True se foi falha."""
    print(f"{status}: {msg}")
    return status == "FALHA"


def main() -> int:
    app = create_app()
    falhas = 0
    with app.app_context():
        from sqlalchemy import inspect, text

        from app.database import db

        insp = inspect(db.engine)

        # Tabelas-alvo precisam existir.
        for tabela in ("inscricoes", "turma_curso", "turma"):
            if not insp.has_table(tabela):
                falhas += _linha(
                    "FALHA", f"tabela '{tabela}' não existe (rode `flask db upgrade`)"
                )
        if falhas:
            return 1

        with db.engine.connect() as conn:
            # (a) NULLs ativas por turma, classificadas por nº de ofertas ativas
            rows = conn.execute(
                text(
                    "SELECT i.turma_id, t.nome, "
                    "  count(*) AS n_null, "
                    "  (SELECT count(*) FROM turma_curso tc "
                    "     WHERE tc.turma_id = i.turma_id AND tc.ativo) AS n_ofertas "
                    "FROM inscricoes i "
                    "JOIN turma t ON t.id = i.turma_id "
                    "WHERE i.ativo AND i.turma_curso_id IS NULL "
                    "GROUP BY i.turma_id, t.nome, n_ofertas "
                    "ORDER BY n_ofertas, i.turma_id"
                )
            ).all()

            seguro = manual = sem_oferta = 0
            for turma_id, nome, n_null, n_ofertas in rows:
                if n_ofertas == 1:
                    seguro += n_null
                    tag = "backfill seguro"
                elif n_ofertas >= 2:
                    manual += n_null
                    tag = "decisão manual (2+ ofertas)"
                else:
                    sem_oferta += n_null
                    tag = "turma sem oferta ativa"
                _linha(
                    "AVISO" if n_ofertas != 1 else "OK",
                    f"turma #{turma_id} '{nome}': {n_null} NULL ativa(s) "
                    f"[{n_ofertas} oferta(s) ativa(s)] → {tag}",
                )

            total_null = seguro + manual + sem_oferta
            if total_null == 0:
                _linha("OK", "nenhuma inscrição ativa sem curso (turma_curso_id NULL)")
            else:
                _linha(
                    "OK",
                    f"resumo (a): total NULL ativas={total_null} | "
                    f"backfill seguro={seguro} | decisão manual={manual} | "
                    f"sem oferta={sem_oferta}",
                )
                if manual:
                    _linha(
                        "AVISO",
                        f"{manual} inscrição(ões) em turma com 2+ ofertas exigem "
                        "decisão manual do curso (a adoção da M1.1 só ocorre ao enturmar)",
                    )
                if sem_oferta:
                    _linha(
                        "AVISO",
                        f"{sem_oferta} inscrição(ões) em turma SEM oferta ativa "
                        "(não há para onde vincular; cadastre um curso na turma)",
                    )

            # (b) duplicatas ativas por (aluno_id, turma_curso_id) NOT NULL
            dups = conn.execute(
                text(
                    "SELECT aluno_id, turma_curso_id, count(*) FROM inscricoes "
                    "WHERE ativo AND turma_curso_id IS NOT NULL "
                    "GROUP BY aluno_id, turma_curso_id HAVING count(*) > 1 "
                    "ORDER BY count(*) DESC, aluno_id"
                )
            ).all()
            if dups:
                falhas += _linha(
                    "FALHA",
                    f"{len(dups)} par(es) aluno+oferta com 2+ inscrições ativas",
                )
                for aluno_id, oferta_id, q in dups[:20]:
                    _linha(
                        "FALHA",
                        f"  aluno #{aluno_id} na oferta #{oferta_id}: {q} ativas",
                    )
            else:
                _linha(
                    "OK",
                    "nenhuma duplicata ativa por (aluno_id, turma_curso_id)",
                )

            # (c) inscrições ativas apontando para oferta inativa
            apontando_inativa = conn.execute(
                text(
                    "SELECT count(*) FROM inscricoes i "
                    "JOIN turma_curso tc ON tc.id = i.turma_curso_id "
                    "WHERE i.ativo AND NOT tc.ativo"
                )
            ).scalar() or 0
            if apontando_inativa:
                _linha(
                    "AVISO",
                    f"{apontando_inativa} inscrição(ões) ativa(s) apontando para "
                    "oferta INATIVA (legado; somem da leitura estrita por oferta)",
                )
            else:
                _linha(
                    "OK",
                    "nenhuma inscrição ativa apontando para oferta inativa",
                )

    if falhas:
        print(f"\n{falhas} checagem(ens) com FALHA.")
        return 1
    print("\nOK: verificações da M1.1 sem violação de integridade.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
