"""Diagnóstico de PREPARAÇÃO DE DEPLOY — Onda 4 (c3d4e5f6a7b8 + d4e5f6a7b8c9 + f6a7b8c9d0e1).

Uso:
    python scripts/preparar_deploy_onda4.py
    python scripts/preparar_deploy_onda4.py --db pautaon_ensaio
    python scripts/preparar_deploy_onda4.py --dsn "postgresql+psycopg://user:senha@host:5432/nome"

Sem argumentos, usa o banco configurado no `.env` (como os demais `verificar_*`).
`--db` apenas troca o nome do banco da URL já configurada; `--dsn` troca a URL
inteira. O banco de origem nunca é aberto para escrita.

Somente LEITURA: nenhum INSERT/UPDATE/DELETE/ALTER/DROP. Uma linha
OK/FALHA/AVISO por checagem — FALHA = bloqueio que impede (ou corrompe dados
de) `flask db upgrade`. Exit code 0 = sem bloqueios; 1 = há bloqueios.
Checagens AVISO não alteram o código de saída.

O que é medido (o enunciado do ensaio de upgrade):
    A. Inscrições com `turma_curso_id` NULL (ativas/inativas), por turma, com
       o nº de ofertas ativas e o total de ofertas/inscrições da turma — e a
       classificação do destino provável (AUTO / MANUAL / SEM DESTINO).
       Bloqueia `c3d4e5f6a7b8` (NOT NULL).
    B. Turmas com `programa` preenchido e SEM oferta ativa: o UPDATE de
       `d4e5f6a7b8c9` sobrescreve `turma.programa` por subconsulta sobre as
       ofertas ativas, que retorna NULL → programa é perdido.
    B2. Turmas sem `programa` que possuem ofertas: após `a1b2c3d4e5f6` as
        ofertas herdam NULL → o NOT NULL de `d4e5f6a7b8c9` falha. (Antes da
        coluna existir, é projeção; depois, é contagem real.)
    C. Turmas com curso e sem oferta (o espelhamento programa↔oferta não tem
        com que contar).
    D. Inscrições ativas duplicadas por (aluno_id, turma_curso_id): bloqueiam
        a criação do índice único parcial `uix_inscricao_ativa_aluno_oferta`.
    E. Inscrições apontando para oferta de OUTRA turma (inconsistência que a
        migration não corrige, mas que quebra os leitores por oferta).
    F. Conselho × oferta (D5.1) — informativo.
    G. Endurecimento D5.5 (f6a7b8c9d0e1) — BLOQUEIA enquanto a migration não
        foi aplicada: (i) conselho sem oferta (turma_curso_id NULL);
        (ii) duplicatas (turma_curso_id, aluno_id, etapa); (iii) conselho com
        turma_id divergente da turma da oferta; (iv) turma com o flag legado
        `conselho_concluido = true` e ofertas ativas pendentes. Depois de
        aplicada, a seção G só confirma o estado final.

Padrão copied from scripts/verificar_onda4_fase4.py.
"""
from __future__ import annotations

import argparse
import os
import sys

from sqlalchemy import inspect, make_url, text

# Detalhamento máximo por checagem (totais são sempre impressos).
MAX_LINHAS = 20


def _linha(status: str, msg: str) -> bool:
    """Imprime uma linha de checagem e retorna True se foi falha."""
    print(f"{status}: {msg}")
    return status == "FALHA"


def _resolver_dsn(args) -> str | None:
    """Devolve a DSN a usar, ou None para obedecer o `.env`/ambiente."""
    if args.dsn:
        return args.dsn
    if not args.db:
        return None
    raw = os.getenv("DATABASE_URL")
    if not raw:
        from dotenv import dotenv_values  # import local: só para ler o .env

        raw = dotenv_values(os.path.join(os.getcwd(), ".env")).get("DATABASE_URL")
    if not raw:
        raise SystemExit(
            "--db exige uma DATABASE_URL base no ambiente ou no .env "
            "(não há nada configurado)."
        )
    return make_url(raw).set(database=args.db).render_as_string(hide_password=False)


def _colunas_insp(insp, tabela: str) -> set[str]:
    try:
        return {c["name"] for c in insp.get_columns(tabela)}
    except Exception:
        return set()


def _nullable_insp(insp, tabela: str, coluna: str) -> bool | None:
    """NULLABLE da coluna (True/False) ou None se tabela/coluna não existem."""
    try:
        for c in insp.get_columns(tabela):
            if c["name"] == coluna:
                return bool(c.get("nullable"))
    except Exception:
        return None
    return None


def _tabula(titulo: str) -> None:
    print(f"    {titulo}")


def _fmt(row, chaves) -> str:
    return "    " + " | ".join(f"{k}={row[k]}" for k in chaves)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Diagnóstico somente-leitura de preparação para as "
        "migrations c3d4e5f6a7b8, d4e5f6a7b8c9 e f6a7b8c9d0e1.",
    )
    parser.add_argument("--db", help="nome do banco (mantém credenciais/host do .env)")
    parser.add_argument("--dsn", help="URL SQLAlchemy completa do banco-alvo")
    parser.add_argument(
        "--sem-lista",
        action="store_true",
        help="imprime só os totais, sem detalhar linha a linha",
    )
    args = parser.parse_args()

    dsn = _resolver_dsn(args)
    if dsn:
        # Precisa acontecer ANTES de qualquer import que leia config.py, pois
        # Config.SQLALCHEMY_DATABASE_URI é avaliado na importação do módulo.
        os.environ["DATABASE_URL"] = dsn

    from app import create_app  # noqa: E402  (import tardio de propósito)

    app = create_app()
    bloqueios = 0
    mostrar = not args.sem_lista

    with app.app_context():
        from app.database import db

        engine = db.engine
        url = engine.url
        insp = inspect(engine)
        tabelas = set(insp.get_table_names())

        print("=== preparar_deploy_onda4 — SOMENTE LEITURA ===")
        print(
            f"alvo: {url.drivername}://{url.host}:{url.port}/{url.database}"
            if url.port
            else f"alvo: {url.drivername}://{url.database}"
        )

        # ------------------------------------------------------------------
        # 0. Contexto: revisão atual e volumes
        # ------------------------------------------------------------------
        with engine.connect() as conn:
            rev = None
            if "alembic_version" in tabelas:
                try:
                    revs = [
                        r[0]
                        for r in conn.execute(
                            text("SELECT version_num FROM alembic_version ORDER BY 1")
                        )
                    ]
                    rev = ",".join(revs) or "(tabela vazia)"
                except Exception as exc:  # pragma: no cover - defensivo
                    _linha("AVISO", f"alembic_version ilegível: {exc}")
            _linha("OK", f"alembic_version atual: {rev or '(ausente)'}")

            for tabela in ("turma", "turma_curso", "inscricoes"):
                if tabela not in tabelas:
                    bloqueios += _linha(
                        "FALHA", f"tabela '{tabela}' não existe — banco incompatível"
                    )
            if bloqueios:
                return 1

            for tabela in ("turma", "turma_curso", "inscricoes", "frequencia", "registro_aula"):
                if tabela in tabelas:
                    n = conn.execute(text(f"SELECT count(*) FROM {tabela}")).scalar() or 0
                    _linha("OK", f"volume: {tabela}={n}")

            cols_insc = _colunas_insp(insp, "inscricoes")
            cols_tc = _colunas_insp(insp, "turma_curso")
            cols_turma = _colunas_insp(insp, "turma")

            # ------------------------------------------------------------------
            # A. Inscrições com turma_curso_id NULL
            # ------------------------------------------------------------------
            print("\n--- A. inscrições sem oferta (turma_curso_id NULL) ---")
            if "turma_curso_id" not in cols_insc:
                bloqueios += _linha(
                    "FALHA",
                    "coluna inscricoes.turma_curso_id AUSENTE — o banco está antes "
                    "de 311d554dfd6e; c3d4e5f6a7b8 não pode ser aplicada",
                )
            else:
                n_null = conn.execute(
                    text("SELECT count(*) FROM inscricoes WHERE turma_curso_id IS NULL")
                ).scalar() or 0
                n_null_ativa = conn.execute(
                    text(
                        "SELECT count(*) FROM inscricoes "
                        "WHERE turma_curso_id IS NULL AND ativo"
                    )
                ).scalar() or 0
                if n_null:
                    bloqueios += _linha(
                        "FALHA",
                        f"{n_null} inscrição(ões) com turma_curso_id NULL "
                        f"({n_null_ativa} ativas / {n_null - n_null_ativa} inativas) — "
                        "c3d4e5f6a7b8 falha com 'contains null values'",
                    )
                else:
                    _linha("OK", "nenhuma inscrição com turma_curso_id NULL")

                por_turma = conn.execute(
                    text(
                        "SELECT i.turma_id, t.nome, t.ativo AS turma_ativa, "
                        "  SUM(CASE WHEN i.ativo THEN 1 ELSE 0 END) AS null_ativas, "
                        "  SUM(CASE WHEN i.ativo THEN 0 ELSE 1 END) AS null_inativas, "
                        "  COUNT(*) AS null_total, "
                        "  (SELECT count(*) FROM turma_curso tc "
                        "    WHERE tc.turma_id = i.turma_id) AS ofertas_total, "
                        "  (SELECT count(*) FROM turma_curso tc "
                        "    WHERE tc.turma_id = i.turma_id AND tc.ativo) AS ofertas_ativas, "
                        "  (SELECT count(*) FROM inscricoes i2 "
                        "    WHERE i2.turma_id = i.turma_id) AS inscricoes_turma "
                        "FROM inscricoes i JOIN turma t ON t.id = i.turma_id "
                        "WHERE i.turma_curso_id IS NULL "
                        "GROUP BY i.turma_id, t.nome, t.ativo "
                        "ORDER BY null_total DESC, i.turma_id"
                    )
                ).mappings().all()

                auto = manual = sem_destino = 0
                for r in por_turma:
                    if r["ofertas_total"] == 1:
                        auto += 1
                    elif r["ofertas_total"] >= 2:
                        manual += 1
                    else:
                        sem_destino += 1
                if por_turma:
                    _linha(
                        "OK",
                        f"turmas com inscrições NULL: {len(por_turma)} — "
                        f"vínculo automático possível em {auto} (exatamente 1 oferta), "
                        f"decisão manual em {manual} (2+ ofertas), "
                        f"sem destino em {sem_destino} (0 ofertas)",
                    )
                    if manual:
                        _linha(
                            "AVISO",
                            f"{manual} turma(s) com 2+ ofertas e inscrições NULL — "
                            "nenhum SQL automático é seguro aqui",
                        )
                    if sem_destino:
                        _linha(
                            "AVISO",
                            f"{sem_destino} turma(s) SEM NENHUMA oferta e inscrições "
                            "NULL — criar oferta antes, ou desativar as inscrições",
                        )
                if mostrar and por_turma:
                    _tabula(
                        "turma_id | turma | turma_ativa | NULLativas | NULlinativas "
                        "| ofertas_ativas | ofertas_total | inscricoes_turma | destino"
                    )
                    for r in por_turma[:MAX_LINHAS]:
                        destino = (
                            "AUTO" if r["ofertas_total"] == 1
                            else "MANUAL" if r["ofertas_total"] >= 2
                            else "SEM-DESTINO"
                        )
                        print(
                            f"    {r['turma_id']} | {r['nome']} | {r['turma_ativa']} | "
                            f"{r['null_ativas']} | {r['null_inativas']} | "
                            f"{r['ofertas_ativas']} | {r['ofertas_total']} | "
                            f"{r['inscricoes_turma']} | {destino}"
                        )
                    if len(por_turma) > MAX_LINHAS:
                        print(f"    (+{len(por_turma) - MAX_LINHAS} turma(s) restantes)")

            # ------------------------------------------------------------------
            # D. Duplicatas ativas por (aluno_id, turma_curso_id)
            # ------------------------------------------------------------------
            print("\n--- D. duplicatas ativas por (aluno_id, turma_curso_id) ---")
            if "turma_curso_id" not in cols_insc:
                _linha("AVISO", "coluna ausente; checagem pulada")
            else:
                dup = conn.execute(
                    text(
                        "SELECT aluno_id, turma_curso_id, count(*) AS n, "
                        "  min(id) AS id_menor, max(id) AS id_maior "
                        "FROM inscricoes "
                        "WHERE ativo AND turma_curso_id IS NOT NULL "
                        "GROUP BY aluno_id, turma_curso_id "
                        "HAVING count(*) > 1 ORDER BY n DESC, aluno_id"
                    )
                ).mappings().all()
                if dup:
                    total = sum(r["n"] for r in dup)
                    bloqueios += _linha(
                        "FALHA",
                        f"{len(dup)} par(es) aluno/oferta com inscrições ativas "
                        f"duplicadas ({total} linhas) — "
                        "uix_inscricao_ativa_aluno_oferta não é criado",
                    )
                    if mostrar:
                        _tabula("aluno_id | turma_curso_id | n | id_menor | id_maior")
                        for r in dup[:MAX_LINHAS]:
                            print(
                                f"    {r['aluno_id']} | {r['turma_curso_id']} | "
                                f"{r['n']} | {r['id_menor']} | {r['id_maior']}"
                            )
                        if len(dup) > MAX_LINHAS:
                            print(f"    (+{len(dup) - MAX_LINHAS} par(es) restante(s))")
                else:
                    _linha("OK", "nenhuma inscrição ativa duplicada por oferta")

            # ------------------------------------------------------------------
            # B. Perda de turma.programa na d4e5f6a7b8c9
            # ------------------------------------------------------------------
            print("\n--- B. programa da turma × ofertas ativas ---")
            if "programa" not in cols_turma:
                bloqueios += _linha(
                    "FALHA", "coluna turma.programa AUSENTE — schema anterior à Onda 4"
                )
            else:
                sem_oferta_ativa = conn.execute(
                    text(
                        "SELECT t.id, t.nome, t.ativo, t.programa, "
                        "  (SELECT count(*) FROM turma_curso tc "
                        "     WHERE tc.turma_id = t.id) AS ofertas_total, "
                        "  (SELECT count(*) FROM turma_curso tc "
                        "     WHERE tc.turma_id = t.id AND tc.ativo) AS ofertas_ativas "
                        "FROM turma t "
                        "WHERE t.programa IS NOT NULL "
                        "  AND NOT EXISTS (SELECT 1 FROM turma_curso tc "
                        "                  WHERE tc.turma_id = t.id AND tc.ativo) "
                        "ORDER BY t.id"
                    )
                ).mappings().all()
                if sem_oferta_ativa:
                    bloqueios += _linha(
                        "FALHA",
                        f"{len(sem_oferta_ativa)} turma(s) com programa preenchido e "
                        "SEM oferta ativa — o UPDATE de d4e5f6a7b8c9 zera "
                        "turma.programa (subconsulta retorna NULL). Preservar antes.",
                    )
                    if mostrar:
                        _tabula("turma_id | turma | ativa | programa | ofertas_ativas | ofertas_total")
                        for r in sem_oferta_ativa[:MAX_LINHAS]:
                            print(
                                f"    {r['id']} | {r['nome']} | {r['ativo']} | "
                                f"{r['programa']} | {r['ofertas_ativas']} | {r['ofertas_total']}"
                            )
                        if len(sem_oferta_ativa) > MAX_LINHAS:
                            print(f"    (+{len(sem_oferta_ativa) - MAX_LINHAS} turma(s) restante(s))")
                else:
                    _linha(
                        "OK",
                        "nenhuma turma com programa e sem oferta ativa "
                        "(nada a preservar antes de d4e5f6a7b8c9)",
                    )

                # B2. oferta que nasceria NULL no backfill de a1b2c3d4e5f6
                if "programa" in cols_tc:
                    n_tc_null = conn.execute(
                        text("SELECT count(*) FROM turma_curso WHERE programa IS NULL")
                    ).scalar() or 0
                    if n_tc_null:
                        bloqueios += _linha(
                            "FALHA",
                            f"{n_tc_null} oferta(s) com turma_curso.programa NULL — "
                            "o NOT NULL de d4e5f6a7b8c9 falha",
                        )
                        n_ativa_null = conn.execute(
                            text(
                                "SELECT count(*) FROM turma_curso "
                                "WHERE programa IS NULL AND ativo"
                            )
                        ).scalar() or 0
                        _linha(
                            "AVISO",
                            f"dessas, {n_ativa_null} estão ativas (ficariam visíveis "
                            "em qualquer listagem de ofertas)",
                        )
                    else:
                        _linha("OK", "nenhuma oferta com programa NULL")
                else:
                    turma_sem_prog = conn.execute(
                        text(
                            "SELECT t.id, t.nome, "
                            "  (SELECT count(*) FROM turma_curso tc "
                            "     WHERE tc.turma_id = t.id) AS ofertas "
                            "FROM turma t WHERE t.programa IS NULL "
                            "  AND EXISTS (SELECT 1 FROM turma_curso tc "
                            "               WHERE tc.turma_id = t.id) "
                            "ORDER BY t.id"
                        )
                    ).mappings().all()
                    if turma_sem_prog:
                        bloqueios += _linha(
                            "FALHA",
                            f"{len(turma_sem_prog)} turma(s) com oferta(s) e programa "
                            "NULL — após a1b2c3d4e5f6 as ofertas herdam NULL e "
                            "d4e5f6a7b8c9 falha",
                        )
                        if mostrar:
                            _tabula("turma_id | turma | ofertas")
                            for r in turma_sem_prog[:MAX_LINHAS]:
                                print(f"    {r['id']} | {r['nome']} | {r['ofertas']}")
                    else:
                        _linha(
                            "OK",
                            "toda turma com oferta tem programa (backfill de "
                            "a1b2c3d4e5f6 não produziria NULL)",
                        )

                # Turmas sem programa em qualquer condição: leitura de dano.
                sem_programa = conn.execute(
                    text(
                        "SELECT t.id, t.nome, t.ativo, "
                        "  (SELECT count(*) FROM turma_curso tc "
                        "     WHERE tc.turma_id = t.id) AS ofertas_total, "
                        "  (SELECT count(*) FROM turma_curso tc "
                        "     WHERE tc.turma_id = t.id AND tc.ativo) AS ofertas_ativas "
                        "FROM turma t WHERE t.programa IS NULL ORDER BY t.id"
                    )
                ).mappings().all()
                if sem_programa:
                    _linha(
                        "AVISO",
                        f"{len(sem_programa)} turma(s) já SEM programa — se o upgrade "
                        "já rodou, é o dano da d4e5f6a7b8c9; se não rodou, é a causa "
                        "do NULL nas ofertas",
                    )
                    if mostrar:
                        _tabula("turma_id | turma | ativa | ofertas_ativas | ofertas_total")
                        for r in sem_programa[:MAX_LINHAS]:
                            print(
                                f"    {r['id']} | {r['nome']} | {r['ativo']} | "
                                f"{r['ofertas_ativas']} | {r['ofertas_total']}"
                            )

            # ------------------------------------------------------------------
            # C. Turmas com curso e sem oferta
            # ------------------------------------------------------------------
            print("\n--- C. turmas com curso e sem oferta ---")
            sem_oferta = conn.execute(
                text(
                    "SELECT t.id, t.nome, t.ativo, t.curso_id, c.nome AS curso, "
                    "  t.programa "
                    "FROM turma t JOIN curso c ON c.id = t.curso_id "
                    "WHERE NOT EXISTS (SELECT 1 FROM turma_curso tc "
                    "                    WHERE tc.turma_id = t.id) "
                    "ORDER BY t.id"
                )
            ).mappings().all()
            if sem_oferta:
                _linha(
                    "AVISO",
                    f"{len(sem_oferta)} turma(s) com curso e sem nenhuma oferta "
                    "(sem destino para inscrição NULL e sem programa-pro-oferta)",
                )
                if mostrar:
                    _tabula("turma_id | turma | ativa | curso | programa")
                    for r in sem_oferta[:MAX_LINHAS]:
                        print(
                            f"    {r['id']} | {r['nome']} | {r['ativo']} | "
                            f"{r['curso']} | {r['programa']}"
                        )
            else:
                _linha("OK", "nenhuma turma com curso sem oferta")

            # ------------------------------------------------------------------
            # E. Inscricao apontando para oferta de outra turma
            # ------------------------------------------------------------------
            print("\n--- E. inscrição × turma da oferta ---")
            if "turma_curso_id" not in cols_insc:
                _linha("AVISO", "coluna ausente; checagem pulada")
            else:
                cruz = conn.execute(
                    text(
                        "SELECT i.id, i.aluno_id, i.turma_id, i.turma_curso_id, "
                        "  tc.turma_id AS turma_da_oferta "
                        "FROM inscricoes i JOIN turma_curso tc ON tc.id = i.turma_curso_id "
                        "WHERE tc.turma_id <> i.turma_id ORDER BY i.id"
                    )
                ).mappings().all()
                if cruz:
                    _linha(
                        "AVISO",
                        f"{len(cruz)} inscrição(ões) apontando para oferta de OUTRA "
                        "turma — a migration não corrige; leitores por oferta e por "
                        "turma divergem",
                    )
                    if mostrar:
                        _tabula("inscricao | aluno | turma_inscricao | oferta | turma_da_oferta")
                        for r in cruz[:MAX_LINHAS]:
                            print(
                                f"    {r['id']} | {r['aluno_id']} | {r['turma_id']} | "
                                f"{r['turma_curso_id']} | {r['turma_da_oferta']}"
                            )
                else:
                    _linha("OK", "toda inscrição aponta para oferta da própria turma")

            # ------------------------------------------------------------------
            # F. Conselho × oferta (D5.1) — INFORMATIVO: nunca bloqueia.
            #    Mesmas checagens (a)/(b) de scripts/verificar_onda4_d5.py.
            # ------------------------------------------------------------------
            print("\n--- F. conselho × oferta (D5.1) — informativo ---")
            if "conselho_classe" not in tabelas:
                _linha("AVISO", "tabela conselho_classe ausente; checagem pulada")
            else:
                cols_cc = _colunas_insp(insp, "conselho_classe")
                if "turma_curso_id" not in cols_cc:
                    _linha(
                        "AVISO",
                        "conselho_classe.turma_curso_id ausente — e5f6a7b8c9d0 ainda "
                        "não aplicada; nada que reportar aqui",
                    )
                else:
                    n_null = conn.execute(
                        text(
                            "SELECT count(*) FROM conselho_classe "
                            "WHERE turma_curso_id IS NULL"
                        )
                    ).scalar() or 0
                    if n_null:
                        n_2p = conn.execute(
                            text(
                                "SELECT count(*) FROM conselho_classe cc WHERE "
                                "cc.turma_curso_id IS NULL AND "
                                "(SELECT COUNT(DISTINCT i.turma_curso_id) "
                                "   FROM inscricoes i WHERE i.aluno_id = cc.aluno_id "
                                "   AND i.turma_id = cc.turma_id) >= 2"
                            )
                        ).scalar() or 0
                        n_sem_of = conn.execute(
                            text(
                                "SELECT count(*) FROM conselho_classe cc WHERE "
                                "cc.turma_curso_id IS NULL AND "
                                "NOT EXISTS (SELECT 1 FROM turma_curso tc "
                                "              WHERE tc.turma_id = cc.turma_id)"
                            )
                        ).scalar() or 0
                        _linha(
                            "AVISO",
                            f"{n_null} conselho(s) sem oferta — 2+ ofertas: {n_2p} | "
                            f"turma sem oferta: {n_sem_of} | sem inscrição: "
                            f"{n_null - n_2p - n_sem_of} "
                            "(detalhe: scripts/verificar_onda4_d5.py)",
                        )
                        n_concl = conn.execute(
                            text(
                                "SELECT count(*) FROM conselho_classe cc WHERE "
                                "cc.turma_curso_id IS NULL AND "
                                "(cc.concluido OR cc.situacao_final IS NOT NULL)"
                            )
                        ).scalar() or 0
                        if n_concl:
                            _linha(
                                "AVISO",
                                f"{n_concl} conselho(s) sem oferta já concluído(s) ou "
                                "com situação final — revisão prioritária pós-upgrade",
                            )
                    else:
                        _linha("OK", "nenhum conselho com turma_curso_id NULL")

            # ------------------------------------------------------------------
            # G. Endurecimento D5.5 (f6a7b8c9d0e1) — BLOQUEIA enquanto a
            #    migration não foi aplicada. Depois de aplicada, só confirma o
            #    estado final (turma_curso_id NOT NULL e sem a coluna da turma).
            # ------------------------------------------------------------------
            print("\n--- G. endurecimento D5.5 (f6a7b8c9d0e1) — bloqueio ---")
            if "conselho_classe" not in tabelas:
                _linha("AVISO", "tabela conselho_classe ausente; checagem pulada")
            else:
                cols_cc_g = _colunas_insp(insp, "conselho_classe")
                cols_turma_g = _colunas_insp(insp, "turma")
                nullable_cc = _nullable_insp(
                    insp, "conselho_classe", "turma_curso_id"
                )
                if "turma_curso_id" not in cols_cc_g:
                    _linha(
                        "AVISO",
                        "conselho_classe.turma_curso_id ausente — e5f6a7b8c9d0 "
                        "ainda não aplicada; nada a bloquear nesta seção",
                    )
                elif nullable_cc is False and "conselho_concluido" not in cols_turma_g:
                    _linha(
                        "OK",
                        "D5.5 aplicada (turma_curso_id NOT NULL e sem "
                        "turma.conselho_concluido) — nenhum bloqueio de endurecimento",
                    )
                else:
                    # (i) conselho sem oferta
                    n_null = conn.execute(
                        text(
                            "SELECT count(*) FROM conselho_classe "
                            "WHERE turma_curso_id IS NULL"
                        )
                    ).scalar() or 0
                    if n_null:
                        n_concl_null = conn.execute(
                            text(
                                "SELECT count(*) FROM conselho_classe "
                                "WHERE turma_curso_id IS NULL AND "
                                "(concluido OR situacao_final IS NOT NULL)"
                            )
                        ).scalar() or 0
                        ids_null = [
                            str(row[0]) for row in conn.execute(
                                text(
                                    "SELECT id FROM conselho_classe "
                                    "WHERE turma_curso_id IS NULL "
                                    "ORDER BY id LIMIT 20"
                                )
                            )
                        ]
                        bloqueios += _linha(
                            "FALHA",
                            f"(i) {n_null} conselho(s) sem oferta "
                            f"({n_concl_null} concluído(s)/com situação) — "
                            f"primeiros ids: {', '.join(ids_null)} "
                            "(detalhe: scripts/verificar_onda4_d5.py)",
                        )
                    else:
                        _linha("OK", "(i) nenhum conselho sem oferta")

                    # (ii) duplicatas por (oferta, aluno, etapa)
                    dup = conn.execute(
                        text(
                            "SELECT turma_curso_id, aluno_id, etapa, count(*) AS n "
                            "FROM conselho_classe WHERE turma_curso_id IS NOT NULL "
                            "GROUP BY turma_curso_id, aluno_id, etapa "
                            "HAVING count(*) > 1 "
                            "ORDER BY turma_curso_id, aluno_id, etapa"
                        )
                    ).mappings().all()
                    if dup:
                        chaves = "; ".join(
                            f"(oferta={r['turma_curso_id']}, aluno={r['aluno_id']}, "
                            f"etapa={r['etapa']}) x{r['n']}"
                            for r in dup[:MAX_LINHAS]
                        )
                        bloqueios += _linha(
                            "FALHA",
                            f"(ii) {len(dup)} grupo(s) (turma_curso_id, aluno_id, "
                            f"etapa) com conselhos duplicados: {chaves}",
                        )
                    else:
                        _linha("OK", "(ii) nenhuma duplicata por (oferta, aluno, etapa)")

                    # (iii) turma do conselho ≠ turma da oferta
                    cruz_cc = conn.execute(
                        text(
                            "SELECT cc.id, cc.aluno_id, cc.turma_id, "
                            "  cc.turma_curso_id, tc.turma_id AS turma_da_oferta "
                            "FROM conselho_classe cc "
                            "JOIN turma_curso tc ON tc.id = cc.turma_curso_id "
                            "WHERE tc.turma_id <> cc.turma_id ORDER BY cc.id"
                        )
                    ).mappings().all()
                    if cruz_cc:
                        chaves = "; ".join(
                            f"conselho={r['id']} (turma={r['turma_id']} × "
                            f"oferta {r['turma_curso_id']} da turma "
                            f"{r['turma_da_oferta']})"
                            for r in cruz_cc[:MAX_LINHAS]
                        )
                        bloqueios += _linha(
                            "FALHA",
                            f"(iii) {len(cruz_cc)} conselho(s) com turma_id "
                            f"divergente da turma da oferta: {chaves}",
                        )
                    else:
                        _linha(
                            "OK",
                            "(iii) todo conselho aponta para oferta da própria turma",
                        )

                    # (iv) flag legado da turma sem equivalente por oferta
                    if "conselho_concluido" in cols_turma_g:
                        div = conn.execute(
                            text(
                                "SELECT t.id, t.nome, "
                                "  (SELECT count(*) FROM turma_curso tc "
                                "     WHERE tc.turma_id = t.id AND tc.ativo) AS ativas, "
                                "  (SELECT count(*) FROM turma_curso tc "
                                "     WHERE tc.turma_id = t.id AND tc.ativo "
                                "       AND tc.conselho_concluido) AS concluidas "
                                "FROM turma t "
                                "WHERE t.conselho_concluido IS TRUE "
                                "  AND EXISTS (SELECT 1 FROM turma_curso tc "
                                "              WHERE tc.turma_id = t.id AND tc.ativo) "
                                "  AND EXISTS (SELECT 1 FROM turma_curso tc "
                                "              WHERE tc.turma_id = t.id AND tc.ativo "
                                "                AND NOT tc.conselho_concluido) "
                                "ORDER BY t.id"
                            )
                        ).mappings().all()
                        if div:
                            chaves = "; ".join(
                                f"turma={r['id']} ({r['nome']}: "
                                f"{r['concluidas']}/{r['ativas']} ofertas ativas "
                                "concluídas)"
                                for r in div[:MAX_LINHAS]
                            )
                            bloqueios += _linha(
                                "FALHA",
                                f"(iv) {len(div)} turma(s) com "
                                f"conselho_concluido=true e ofertas pendentes: {chaves}",
                            )
                        else:
                            _linha(
                                "OK",
                                "(iv) nenhuma turma com flag legado divergente das ofertas",
                            )
                    else:
                        _linha(
                            "OK",
                            "(iv) coluna turma.conselho_concluido já removida; "
                            "não se aplica",
                        )

    if bloqueios:
        print(f"\n{bloqueios} checagem(ns) com FALHA — há limpeza obrigatória antes do upgrade.")
        return 1
    print(
        "\nOK: nenhum bloqueio para c3d4e5f6a7b8, d4e5f6a7b8c9 e "
        "f6a7b8c9d0e1 neste banco."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
