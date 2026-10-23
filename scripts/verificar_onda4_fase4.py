"""
Verificação da Onda 4 — Fase 4 (turma_curso_id em frequencia e registro_aula).

Uso (com o banco de destino ativo via .env):
    python scripts/verificar_onda4_fase4.py

Somente LEITURA: nenhum INSERT/UPDATE/DELETE. Uma linha OK/FALHA por checagem.
Exit code 0 = tudo íntegro; 1 = alguma checagem estrutural/de integridade
falhou. Checagens marcadas como AVISO não impactam o código de saída.

Depois de `flask db upgrade` (head e7f3a1b9c4d5), confere:
    1. Coluna turma_curso_id em frequencia e registro_aula;
    2. Índices únicos parciais uix_freq_legado / uix_freq_oferta e os índices
       de apoio ix_frequencia_turma_curso_data / ix_registro_aula_turma_curso_data;
    3. A constraint antiga uix_frequencia_aluno_turma_data NÃO existe mais;
    4. FKs para turma_curso nas duas tabelas (PostgreSQL);
    5. Contagem de linhas (informativo);
    6. Nenhuma linha com turma_curso_id apontando para oferta de outra turma;
    7. Nenhuma turma com 2+ ofertas ativas sem principal;
    8. Inscrições ativas sem curso em turma com 2+ ofertas (AVISO);
    9. Nenhuma oferta com data_inicio > data_fim;
   10. Turma ativa com curso_id e sem oferta (AVISO; lacuna que a criação
       automática de oferta inicial passou a cobrir).
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
        is_pg = db.engine.dialect.name == "postgresql"

        # Tabelas-alvo precisam existir.
        for tabela in ("frequencia", "registro_aula", "turma_curso"):
            if not insp.has_table(tabela):
                falhas += _linha(
                    "FALHA", f"tabela '{tabela}' não existe (rode `flask db upgrade`)"
                )
        if falhas:
            return 1

        # 1. Coluna turma_curso_id ------------------------------------------------
        for tabela in ("frequencia", "registro_aula"):
            cols = {c["name"] for c in insp.get_columns(tabela)}
            if "turma_curso_id" in cols:
                _linha("OK", f"coluna {tabela}.turma_curso_id presente")
            else:
                falhas += _linha("FALHA", f"coluna {tabela}.turma_curso_id AUSENTE")

        # 2. Índices -------------------------------------------------------------
        idx_freq = {i["name"]: i for i in insp.get_indexes("frequencia") if i.get("name")}
        idx_reg = {i["name"]: i for i in insp.get_indexes("registro_aula") if i.get("name")}

        # 2a. uix_freq_legado: único
        info = idx_freq.get("uix_freq_legado")
        if info and info.get("unique"):
            extra = ""
            if is_pg:
                with db.engine.connect() as conn:
                    d = conn.execute(
                        text("SELECT indexdef FROM pg_indexes "
                             "WHERE tablename='frequencia' AND indexname='uix_freq_legado'")
                    ).scalar() or ""
                if "where" not in d.lower():
                    extra = " (AVISO: sem WHERE parcial?)"
            _linha("OK", f"uix_freq_legado presente e único{extra}")
        else:
            falhas += _linha("FALHA", "uix_freq_legado ausente ou não-único")

        # 2b. uix_freq_oferta: único
        info = idx_freq.get("uix_freq_oferta")
        if info and info.get("unique"):
            _linha("OK", "uix_freq_oferta presente e único")
        else:
            falhas += _linha("FALHA", "uix_freq_oferta ausente ou não-único")

        # 2c. índices de apoio (não-únicos)
        for nome, bucket, tabela in (
            ("ix_frequencia_turma_curso_data", idx_freq, "frequencia"),
            ("ix_registro_aula_turma_curso_data", idx_reg, "registro_aula"),
        ):
            if nome in bucket:
                _linha("OK", f"{nome} presente ({tabela})")
            else:
                falhas += _linha("FALHA", f"{nome} AUSENTE ({tabela})")

        # 3. Constraint antiga removida -----------------------------------------
        unicos_freq = {u["name"] for u in insp.get_unique_constraints("frequencia") if u.get("name")}
        if "uix_frequencia_aluno_turma_data" not in unicos_freq and \
           "uix_frequencia_aluno_turma_data" not in idx_freq:
            _linha("OK", "constraint antiga uix_frequencia_aluno_turma_data removida")
        else:
            falhas += _linha(
                "FALHA", "uix_frequencia_aluno_turma_data ainda existe (deve ser removida)"
            )

        # 4. FKs para turma_curso (PG) ------------------------------------------
        def _fk_para_turma_curso(tabela: str) -> bool:
            for fk in insp.get_foreign_keys(tabela):
                if fk.get("referred_table") == "turma_curso" and \
                   "turma_curso_id" in (fk.get("constrained_columns") or []):
                    return True
            return False

        for tabela in ("frequencia", "registro_aula"):
            if _fk_para_turma_curso(tabela):
                _linha("OK", f"FK {tabela}.turma_curso_id → turma_curso presente")
            elif is_pg:
                falhas += _linha("FALHA", f"FK {tabela}.turma_curso_id → turma_curso AUSENTE (PG)")
            else:
                _linha("AVISO", f"FK {tabela}.turma_curso_id ausente (esperado fora de PG)")

        # 5..9 Checagens de dados -------------------------------------------------
        with db.engine.connect() as conn:
            n_freq = conn.execute(text("SELECT count(*) FROM frequencia")).scalar() or 0
            n_reg = conn.execute(text("SELECT count(*) FROM registro_aula")).scalar() or 0
            _linha("OK", f"linhas (informativo): frequencia={n_freq} registro_aula={n_reg}")

            # 6. oferta de outra turma
            for tabela in ("frequencia", "registro_aula"):
                mismatch = conn.execute(
                    text(
                        f"SELECT count(*) FROM {tabela} x "
                        "JOIN turma_curso tc ON tc.id = x.turma_curso_id "
                        "WHERE tc.turma_id <> x.turma_id"
                    )
                ).scalar() or 0
                if mismatch:
                    falhas += _linha(
                        "FALHA",
                        f"{mismatch} linha(s) de {tabela} com turma_curso de outra turma",
                    )
                else:
                    _linha("OK", f"{tabela}: nenhum turma_curso de turma divergente")

            # 7. 2+ ofertas ativas sem principal
            sem_principal = conn.execute(
                text(
                    "SELECT count(*) FROM ("
                    "  SELECT turma_id FROM turma_curso WHERE ativo "
                    "  GROUP BY turma_id "
                    "  HAVING count(*) >= 2 "
                    "     AND SUM(CASE WHEN principal THEN 1 ELSE 0 END) = 0"
                    ") p"
                )
            ).scalar() or 0
            if sem_principal:
                falhas += _linha(
                    "FALHA", f"{sem_principal} turma(s) com 2+ ofertas ativas sem principal"
                )
            else:
                _linha("OK", "nenhuma turma com 2+ ofertas ativas sem principal")

            # 8. inscrições ativas sem curso em turma 2+ ofertas (AVISO)
            insc_null = conn.execute(
                text(
                    "SELECT count(*) FROM inscricoes i "
                    "JOIN turma t ON t.id = i.turma_id "
                    "WHERE i.ativo AND i.turma_curso_id IS NULL "
                    "  AND (SELECT count(*) FROM turma_curso tc "
                    "         WHERE tc.turma_id = i.turma_id AND tc.ativo) >= 2"
                )
            ).scalar() or 0
            if insc_null:
                _linha(
                    "AVISO",
                    f"{insc_null} inscrição(ões) ativa(s) sem curso em turma com 2+ ofertas "
                    "(as 'sem curso definido'; não é falha)",
                )
            else:
                _linha("OK", "nenhuma inscrição ativa sem curso em turma com 2+ ofertas")

            # 9. oferta com data_inicio > data_fim
            vig_bad = conn.execute(
                text(
                    "SELECT count(*) FROM turma_curso "
                    "WHERE data_inicio IS NOT NULL AND data_fim IS NOT NULL "
                    "  AND data_inicio > data_fim"
                )
            ).scalar() or 0
            if vig_bad:
                falhas += _linha("FALHA", f"{vig_bad} oferta(s) com data_inicio > data_fim")
            else:
                _linha("OK", "nenhuma oferta com data_inicio > data_fim")

            # 10. turma ativa com curso_id e sem oferta (AVISO)
            turma_sem_oferta = conn.execute(
                text(
                    "SELECT count(*) FROM turma t "
                    "WHERE t.ativo AND t.curso_id IS NOT NULL "
                    "  AND NOT EXISTS ("
                    "      SELECT 1 FROM turma_curso tc WHERE tc.turma_id = t.id"
                    "  )"
                )
            ).scalar() or 0
            if turma_sem_oferta:
                _linha(
                    "AVISO",
                    f"{turma_sem_oferta} turma(s) ativa(s) com curso_id e sem oferta "
                    "(criação automática de oferta inicial não foi aplicada; não é falha)",
                )
            else:
                _linha("OK", "nenhuma turma ativa com curso_id e sem oferta")

    if falhas:
        print(f"\n{falhas} checagem(ens) com FALHA.")
        return 1
    print("\nOK: estrutura e integridade da Fase 4 íntegros.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
