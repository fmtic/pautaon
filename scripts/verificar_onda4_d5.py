"""
Verificação da Onda 4 — conselho por oferta (D5.1 → D5.5).

Uso (com o banco de destino ativo via .env):
    python scripts/verificar_onda4_d5.py
    python scripts/verificar_onda4_d5.py --db pautaon_ensaio

Somente LEITURA: nenhum INSERT/UPDATE/DELETE. Uma linha OK/FALHA/AVISO por
checagem. Exit code 0 = estrutura íntegra e nenhuma inconsistência grave;
1 = falha estrutural, duplicatas (c) ou vínculo cruzado (g). Checagens
marcadas como AVISO (a/b/d/e/f e o estado intermediário D5.1) não impactam o
código de saída.

Funciona ANTES e DEPOIS de `flask db upgrade` (head f6a7b8c9d0e1):
    Estrutura (D5.1 → D5.5):
      - colunas `conselho_classe.turma_curso_id` e
        `turma_curso.conselho_concluido/avaliacao_*`;
      - FK PG, índice de apoio ix_conselho_turma_curso e o índice único
        uix_conselho_oferta;
      - `turma_curso_id` NULLABLE (D5.5 pendente) × NOT NULL (D5.5 aplicada);
      - `uix_conselho_legado` e `turma.conselho_concluido` PRESENTES (estado
        D5.1) × AUSENTES (estado D5.5);
      - ausência da constraint antiga `uix_conselho_turma_aluno_etapa`.
    Dados (itens do desenho D5.0/D5.1):
      (a) conselhos com turma_curso_id NULL, classificados em
          "2+ OFERTAS" (aluno inscrito em 2+ ofertas da turma),
          "TURMA SEM OFERTA" e "SEM INSCRICAO" (AVISO; bloqueia a D5.5);
      (b) quantos desses estão concluídos ou com situacao_final
          (prioridade máxima de revisão manual) (AVISO);
      (c) duplicatas que violariam uix_conselho_oferta (FALHA);
      (d) divergência turma.conselho_concluido × ofertas (AVISO; só roda
          enquanto a coluna da turma existir);
      (e) turmas com 2+ ofertas ativas e avaliacao_* legado preenchido
          (parecer coletivo sem dono por oferta) (AVISO);
      (f) ConselhoResposta com aluno_id NULL (respostas coletivas legadas):
          quantidade por turma e etapa (AVISO, quantifica);
      (g) conselhos cujo turma_id difere do turma_id da oferta (FALHA).

Padrão copied from scripts/verificar_onda4_fase4.py; --db/--dsn de
scripts/preparar_deploy_onda4.py.
"""
from __future__ import annotations

import argparse
import os
import sys

from sqlalchemy import make_url, text

MAX_LINHAS = 20


def _linha(status: str, msg: str) -> bool:
    """Imprime uma linha de checagem e retorna True se foi falha."""
    print(f"{status}: {msg}")
    return status == "FALHA"


def _resolver_dsn(args) -> str | None:
    if args.dsn:
        return args.dsn
    if not args.db:
        return None
    raw = os.getenv("DATABASE_URL")
    if not raw:
        from dotenv import dotenv_values

        raw = dotenv_values(os.path.join(os.getcwd(), ".env")).get("DATABASE_URL")
    if not raw:
        raise SystemExit("--db exige uma DATABASE_URL base no ambiente ou no .env.")
    return make_url(raw).set(database=args.db).render_as_string(hide_password=False)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verificação somente-leitura do esquema D5.1 do conselho.",
    )
    parser.add_argument("--db", help="nome do banco (mantém credenciais/host do .env)")
    parser.add_argument("--dsn", help="URL SQLAlchemy completa do banco-alvo")
    parser.add_argument(
        "--sem-lista", action="store_true",
        help="imprime só os totais, sem detalhar linha a linha",
    )
    args = parser.parse_args()

    dsn = _resolver_dsn(args)
    if dsn:
        os.environ["DATABASE_URL"] = dsn

    from app import create_app  # noqa: E402 (import tardio de propósito)

    app = create_app()
    falhas = 0
    mostrar = not args.sem_lista

    with app.app_context():
        from sqlalchemy import inspect

        from app.database import db

        insp = inspect(db.engine)
        is_pg = db.engine.dialect.name == "postgresql"
        conn_ctx = db.engine.connect()

        with conn_ctx as conn:
            # ---------------------------------------------------------------
            # 1. Estrutura
            # ---------------------------------------------------------------
            for tabela in ("conselho_classe", "turma_curso", "conselho_resposta"):
                if not insp.has_table(tabela):
                    falhas += _linha(
                        "FALHA", f"tabela '{tabela}' não existe (rode `flask db upgrade`)"
                    )
            if falhas:
                return 1

            cols_cc = {c["name"] for c in insp.get_columns("conselho_classe")}
            cols_tc = {c["name"] for c in insp.get_columns("turma_curso")}

            if "turma_curso_id" in cols_cc:
                _linha("OK", "coluna conselho_classe.turma_curso_id presente")
                nullable_cc = next(
                    c.get("nullable") for c in insp.get_columns("conselho_classe")
                    if c["name"] == "turma_curso_id"
                )
                if nullable_cc:
                    _linha(
                        "AVISO",
                        "conselho_classe.turma_curso_id ainda é NULLABLE — "
                        "f6a7b8c9d0e1 (D5.5) não aplicada (estado D5.1)",
                    )
                else:
                    _linha(
                        "OK",
                        "conselho_classe.turma_curso_id NOT NULL (D5.5 aplicada)",
                    )
            else:
                falhas += _linha(
                    "FALHA", "coluna conselho_classe.turma_curso_id AUSENTE "
                    "(migration e5f6a7b8c9d0 não aplicada)"
                )
            for nome in ("conselho_concluido", "avaliacao_inicial",
                         "avaliacao_percurso", "avaliacao_final"):
                if nome in cols_tc:
                    _linha("OK", f"coluna turma_curso.{nome} presente")
                else:
                    falhas += _linha("FALHA", f"coluna turma_curso.{nome} AUSENTE")

            cols_turma = {c["name"] for c in insp.get_columns("turma")}
            if "conselho_concluido" in cols_turma:
                _linha(
                    "AVISO",
                    "coluna turma.conselho_concluido presente — f6a7b8c9d0e1 "
                    "(D5.5) ainda não aplicada (será removida)",
                )
            else:
                _linha(
                    "OK",
                    "coluna turma.conselho_concluido removida (D5.5 aplicada)",
                )

            idx_cc = {i["name"]: i for i in insp.get_indexes("conselho_classe") if i.get("name")}
            info = idx_cc.get("uix_conselho_oferta")
            if info and info.get("unique"):
                _linha("OK", "uix_conselho_oferta presente e único (UNIQUE por oferta)")
            else:
                falhas += _linha("FALHA", "uix_conselho_oferta ausente ou não-único")
            if "uix_conselho_legado" in idx_cc:
                _linha(
                    "AVISO",
                    "uix_conselho_legado presente — f6a7b8c9d0e1 (D5.5) ainda "
                    "não aplicada (será removido)",
                )
            else:
                _linha("OK", "uix_conselho_legado ausente (ramo legado encerrado)")

            if "ix_conselho_turma_curso" in idx_cc:
                _linha("OK", "ix_conselho_turma_curso presente")
            else:
                falhas += _linha("FALHA", "ix_conselho_turma_curso AUSENTE")

            unicos_cc = {u["name"] for u in insp.get_unique_constraints("conselho_classe") if u.get("name")}
            if "uix_conselho_turma_aluno_etapa" not in unicos_cc and \
               "uix_conselho_turma_aluno_etapa" not in idx_cc:
                _linha("OK", "constraint antiga uix_conselho_turma_aluno_etapa removida")
            else:
                falhas += _linha(
                    "FALHA",
                    "uix_conselho_turma_aluno_etapa ainda existe (deve ser substituída pelos parciais)",
                )

            if is_pg:
                fks = {fk["name"] for fk in insp.get_foreign_keys("conselho_classe") if fk.get("name")}
                if "fk_conselho_classe_turma_curso" in fks:
                    _linha("OK", "FK conselho_classe.turma_curso_id → turma_curso presente (PG)")
                else:
                    falhas += _linha("FALHA", "FK fk_conselho_classe_turma_curso AUSENTE (PG)")
            else:
                _linha("AVISO", "checagem de FK individual só se aplica a PostgreSQL")

            if "turma_curso_id" not in cols_cc:
                print("\nColuna ausente; checagens de dados (a)-(g) puladas.")
                if falhas:
                    print(f"\n{falhas} checagem(ens) com FALHA.")
                    return 1
                return 0

            # ---------------------------------------------------------------
            # (a) conselhos NULL por categoria + (b) concluídos/situação
            # ---------------------------------------------------------------
            print("\n--- (a) conselhos com turma_curso_id NULL ---")
            rows = conn.execute(
                text(
                    "SELECT cc.id, cc.turma_id, t.nome AS turma, cc.aluno_id, cc.etapa, "
                    "  cc.concluido, cc.situacao_final, "
                    "  (SELECT COUNT(DISTINCT i.turma_curso_id) FROM inscricoes i "
                    "     WHERE i.aluno_id = cc.aluno_id AND i.turma_id = cc.turma_id) AS ofertas_inscritas, "
                    "  (SELECT COUNT(*) FROM turma_curso tc WHERE tc.turma_id = cc.turma_id) AS ofertas_turma "
                    "FROM conselho_classe cc "
                    "JOIN turma t ON t.id = cc.turma_id "
                    "WHERE cc.turma_curso_id IS NULL "
                    "ORDER BY cc.concluido DESC, cc.id"
                )
            ).mappings().all()

            cat_2p = [r for r in rows if r["ofertas_inscritas"] >= 2]
            cat_sem_oferta = [r for r in rows if r["ofertas_turma"] == 0]
            cat_sem_inscricao = [
                r for r in rows
                if r["ofertas_inscritas"] <= 1 and r["ofertas_turma"] > 0
            ]
            n_concl = sum(1 for r in rows if r["concluido"] or r["situacao_final"])
            if rows:
                _linha(
                    "AVISO",
                    f"{len(rows)} conselho(s) legado(s) sem oferta — "
                    f"2+ ofertas: {len(cat_2p)} | turma sem oferta: {len(cat_sem_oferta)} | "
                    f"sem inscrição do aluno na oferta: {len(cat_sem_inscricao)}",
                )
                _linha(
                    "AVISO",
                    f"desses, {n_concl} concluído(s) ou com situacao_final "
                    "(revisão prioritária: impacto em certificado/ficha)",
                )
                if mostrar:
                    print(
                        "    conselho | turma_id | turma | aluno | etapa | "
                        "concluido | situacao | ofertas_inscritas | ofertas_turma | categoria"
                    )
                    for r in rows[:MAX_LINHAS]:
                        categoria = (
                            "2+ OFERTAS" if r["ofertas_inscritas"] >= 2
                            else "TURMA SEM OFERTA" if r["ofertas_turma"] == 0
                            else "SEM INSCRICAO"
                        )
                        print(
                            f"    {r['id']} | {r['turma_id']} | {r['turma']} | "
                            f"{r['aluno_id']} | {r['etapa']} | {r['concluido']} | "
                            f"{r['situacao_final']} | {r['ofertas_inscritas']} | "
                            f"{r['ofertas_turma']} | {categoria}"
                        )
                    if len(rows) > MAX_LINHAS:
                        print(f"    (+{len(rows) - MAX_LINHAS} linha(s) restante(s))")
            else:
                _linha("OK", "nenhum conselho com turma_curso_id NULL")

            # ---------------------------------------------------------------
            # (c) duplicatas que violariam uix_conselho_oferta
            # ---------------------------------------------------------------
            print("\n--- (c) duplicatas por (turma_curso_id, aluno_id, etapa) ---")
            dup = conn.execute(
                text(
                    "SELECT turma_curso_id, aluno_id, etapa, count(*) AS n, "
                    "  min(id) AS id_menor, max(id) AS id_maior "
                    "FROM conselho_classe WHERE turma_curso_id IS NOT NULL "
                    "GROUP BY turma_curso_id, aluno_id, etapa HAVING count(*) > 1 "
                    "ORDER BY n DESC, turma_curso_id"
                )
            ).mappings().all()
            if dup:
                falhas += _linha(
                    "FALHA",
                    f"{len(dup)} grupo(s) (oferta, aluno, etapa) com conselhos "
                    f"duplicados ({sum(r['n'] for r in dup)} linhas)",
                )
                if mostrar:
                    print("    oferta | aluno | etapa | n | id_menor | id_maior")
                    for r in dup[:MAX_LINHAS]:
                        print(
                            f"    {r['turma_curso_id']} | {r['aluno_id']} | "
                            f"{r['etapa']} | {r['n']} | {r['id_menor']} | {r['id_maior']}"
                        )
            else:
                _linha("OK", "nenhuma duplicata por (oferta, aluno, etapa)")

            # ---------------------------------------------------------------
            # (d) divergência turma.conselho_concluido × ofertas
            # ---------------------------------------------------------------
            print("\n--- (d) turma.conselho_concluido × ofertas ativas ---")
            div = (
                conn.execute(
                    text(
                    "SELECT t.id, t.nome, t.conselho_concluido, "
                    "  (SELECT count(*) FROM turma_curso tc "
                    "     WHERE tc.turma_id = t.id AND tc.ativo) AS ofertas_ativas, "
                    "  (SELECT count(*) FROM turma_curso tc "
                    "     WHERE tc.turma_id = t.id AND tc.ativo AND tc.conselho_concluido) AS ofertas_concluidas "
                    "FROM turma t "
                    "WHERE (t.conselho_concluido AND EXISTS (SELECT 1 FROM turma_curso tc "
                    "        WHERE tc.turma_id = t.id AND tc.ativo AND NOT tc.conselho_concluido)) "
                    "   OR (NOT t.conselho_concluido AND EXISTS (SELECT 1 FROM turma_curso tc "
                    "        WHERE tc.turma_id = t.id AND tc.ativo) "
                    "       AND NOT EXISTS (SELECT 1 FROM turma_curso tc "
                    "        WHERE tc.turma_id = t.id AND tc.ativo AND NOT tc.conselho_concluido)) "
                    "ORDER BY t.id"
                    )
                ).mappings().all()
                if "conselho_concluido" in cols_turma
                else []
            )
            if div:
                _linha(
                    "AVISO",
                    f"{len(div)} turma(s) com flag legado divergente das ofertas "
                    "(esperado até D5.3 mover a escrita)",
                )
                if mostrar:
                    print("    turma_id | turma | turma_concluido | ofertas_ativas | ofertas_concluidas")
                    for r in div[:MAX_LINHAS]:
                        print(
                            f"    {r['id']} | {r['nome']} | {r['conselho_concluido']} | "
                            f"{r['ofertas_ativas']} | {r['ofertas_concluidas']}"
                        )
            else:
                if "conselho_concluido" in cols_turma:
                    _linha(
                        "OK",
                        "flag legado × ofertas das turmas consistentes (ou ambos falsos)",
                    )
                else:
                    _linha(
                        "OK",
                        "coluna turma.conselho_concluido removida (D5.5 "
                        "aplicada); sem flag legado a comparar",
                    )

            # ---------------------------------------------------------------
            # (e) turmas 2+ ofertas com avaliacao_* legado preenchido
            # ---------------------------------------------------------------
            print("\n--- (e) parecer coletivo legado em turma com 2+ ofertas ativas ---")
            aval = conn.execute(
                text(
                    "SELECT t.id, t.nome, "
                    "  (SELECT count(*) FROM turma_curso tc "
                    "     WHERE tc.turma_id = t.id AND tc.ativo) AS ofertas_ativas "
                    "FROM turma t "
                    "WHERE (t.avaliacao_inicial IS NOT NULL "
                    "       OR t.avaliacao_percurso IS NOT NULL "
                    "       OR t.avaliacao_final IS NOT NULL) "
                    "  AND (SELECT count(*) FROM turma_curso tc "
                    "         WHERE tc.turma_id = t.id AND tc.ativo) >= 2 "
                    "ORDER BY t.id"
                )
            ).mappings().all()
            if aval:
                _linha(
                    "AVISO",
                    f"{len(aval)} turma(s) com 2+ ofertas ativas e avaliacao_* legado "
                    "preenchido — parecer sem dono por oferta (decisão Q2 do desenho)",
                )
                if mostrar:
                    print("    turma_id | turma | ofertas_ativas")
                    for r in aval[:MAX_LINHAS]:
                        print(f"    {r['id']} | {r['nome']} | {r['ofertas_ativas']}")
            else:
                _linha("OK", "nenhum parecer coletivo legado em turma com 2+ ofertas ativas")

            # ---------------------------------------------------------------
            # (f) respostas coletivas legadas (ConselhoResposta aluno_id NULL)
            # ---------------------------------------------------------------
            print("\n--- (f) ConselhoResposta com aluno_id NULL (coletivas legadas) ---")
            resp_null = conn.execute(
                text(
                    "SELECT cc.turma_id, t.nome AS turma, cc.etapa, count(*) AS n "
                    "FROM conselho_resposta cr "
                    "JOIN conselho_classe cc ON cc.id = cr.conselho_id "
                    "JOIN turma t ON t.id = cc.turma_id "
                    "WHERE cr.aluno_id IS NULL "
                    "GROUP BY cc.turma_id, t.nome, cc.etapa ORDER BY n DESC, cc.turma_id"
                )
            ).mappings().all()
            total_resp = sum(r["n"] for r in resp_null)
            if resp_null:
                _linha(
                    "AVISO",
                    f"{total_resp} resposta(coletiva)(s) legada(s) com aluno_id NULL "
                    f"em {len(resp_null)} grupo(s) turma×etapa (D5.2 as move para turma_curso.avaliacao_*)",
                )
                if mostrar:
                    print("    turma_id | turma | etapa | n")
                    for r in resp_null[:MAX_LINHAS]:
                        print(f"    {r['turma_id']} | {r['turma']} | {r['etapa']} | {r['n']}")
            else:
                _linha("OK", "nenhuma ConselhoResposta com aluno_id NULL")

            # ---------------------------------------------------------------
            # (g) conselho com turma_id ≠ turma_id da oferta
            # ---------------------------------------------------------------
            print("\n--- (g) conselho × turma da oferta ---")
            cruz = conn.execute(
                text(
                    "SELECT cc.id, cc.aluno_id, cc.turma_id, cc.turma_curso_id, "
                    "  tc.turma_id AS turma_da_oferta "
                    "FROM conselho_classe cc "
                    "JOIN turma_curso tc ON tc.id = cc.turma_curso_id "
                    "WHERE tc.turma_id <> cc.turma_id ORDER BY cc.id"
                )
            ).mappings().all()
            if cruz:
                falhas += _linha(
                    "FALHA",
                    f"{len(cruz)} conselho(s) com turma_id divergente da turma da oferta",
                )
                if mostrar:
                    print("    conselho | aluno | turma_inscricao | oferta | turma_da_oferta")
                    for r in cruz[:MAX_LINHAS]:
                        print(
                            f"    {r['id']} | {r['aluno_id']} | {r['turma_id']} | "
                            f"{r['turma_curso_id']} | {r['turma_da_oferta']}"
                        )
            else:
                _linha("OK", "todo conselho aponta para oferta da própria turma")

            # informativo
            n_cc = conn.execute(text("SELECT count(*) FROM conselho_classe")).scalar() or 0
            n_vinc = conn.execute(
                text("SELECT count(*) FROM conselho_classe WHERE turma_curso_id IS NOT NULL")
            ).scalar() or 0
            _linha("OK", f"linhas (informativo): conselho_classe={n_cc} vinculadas={n_vinc}")

    if falhas:
        print(f"\n{falhas} checagem(ens) com FALHA.")
        return 1
    print("\nOK: estrutura e integridade do conselho por oferta (D5.1/D5.5) íntegras.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
