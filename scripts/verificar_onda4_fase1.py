"""
Verificação da Onda 4 — Fase 1 (múltiplos cursos por turma).

Uso (com o banco de destino ativo via .env):
    python scripts/verificar_onda4_fase1.py

Checa, após `flask db upgrade`:
    1. Existência da tabela turma_curso, da coluna inscricoes.turma_curso_id,
       das constraints/índices esperados e da sequência da PK (PostgreSQL).
    2. Backfill: toda turma com curso_id possui exatamente uma oferta com os
       mesmos curso_id/professor_id da coluna legada.
    3. Nenhuma inscrição de turma com curso ficou sem turma_curso_id.
    4. Nenhum par (turma, curso) duplicado e no máximo um principal por turma.

Exit code 0 = tudo íntegro; 1 = divergências (listadas na saída).
"""
from __future__ import annotations

import sys

from app import create_app

EXPECTED_INDEXES = {
    "ix_turma_curso_curso_id",
    "ix_turma_curso_professor_id",
    "uix_turma_curso_principal",
}


def main() -> int:
    app = create_app()
    with app.app_context():
        from sqlalchemy import inspect, text

        from app.database import db

        insp = inspect(db.engine)
        errors: list[str] = []

        if not insp.has_table("turma_curso"):
            print("FALHA: tabela 'turma_curso' não existe. Rode `flask db upgrade`.")
            return 1

        cols_insc = {c["name"] for c in insp.get_columns("inscricoes")}
        if "turma_curso_id" not in cols_insc:
            errors.append("coluna 'inscricoes.turma_curso_id' ausente")

        # AuditoriaMixin completo na tabela nova: a omissão de updated_by_id
        # na revision original (corrigida por 8c4e1f9a7d32) só aparecia em
        # consultas ORM no PostgreSQL — detecta-lo aqui protege o deploy.
        cols_turma_curso = {c["name"] for c in insp.get_columns("turma_curso")}
        faltas_auditoria = {
            "updated_by_id", "updated_by_name", "updated_at"
        } - cols_turma_curso
        if faltas_auditoria:
            errors.append(
                f"colunas de auditoria ausentes em turma_curso: {sorted(faltas_auditoria)}"
            )

        idx_turma_curso = {i["name"] for i in insp.get_indexes("turma_curso")}
        faltando = EXPECTED_INDEXES - idx_turma_curso
        if faltando:
            errors.append(f"índices ausentes em turma_curso: {sorted(faltando)}")

        unicos = {u["name"] for u in insp.get_unique_constraints("turma_curso")}
        if "uix_turma_curso_oferta" not in unicos:
            errors.append("UNIQUE uix_turma_curso_oferta ausente")

        with db.engine.connect() as conn:
            if conn.dialect.name == "postgresql":
                tem_seq = conn.execute(
                    text(
                        "SELECT EXISTS(SELECT 1 FROM pg_class "
                        "WHERE relname='turma_curso_id_seq')"
                    )
                ).scalar()
                if not tem_seq:
                    errors.append("sequência 'turma_curso_id_seq' ausente (PG)")

            n_turmas = conn.execute(
                text("SELECT count(*) FROM turma WHERE curso_id IS NOT NULL")
            ).scalar()
            n_ofertas = conn.execute(
                text("SELECT count(*) FROM turma_curso")
            ).scalar()
            if n_ofertas < n_turmas:
                errors.append(
                    f"ofertas ({n_ofertas}) < turmas com curso ({n_turmas}): backfill incompleto"
                )

            opt = conn.execute(
                text(
                    "SELECT count(*) FROM inscricoes i "
                    "JOIN turma t ON t.id = i.turma_id "
                    "WHERE t.curso_id IS NOT NULL AND i.turma_curso_id IS NULL"
                )
            ).scalar()
            if opt:
                errors.append(f"{opt} inscrição(ões) órfãs (turma com curso sem oferta)")

            dups = conn.execute(
                text(
                    "SELECT count(*) FROM (SELECT turma_id, curso_id FROM turma_curso "
                    "GROUP BY turma_id, curso_id HAVING count(*) > 1) d"
                )
            ).scalar()
            if dups:
                errors.append(f"{dups} par(es) turma/curso duplicado(s)")

            multi_principais = conn.execute(
                text(
                    "SELECT count(*) FROM (SELECT turma_id FROM turma_curso "
                    "WHERE principal AND ativo GROUP BY turma_id HAVING count(*) > 1) p"
                )
            ).scalar()
            if multi_principais:
                errors.append(
                    f"{multi_principais} turma(s) com mais de um principal ativo"
                )

            mism = conn.execute(
                text(
                    "SELECT count(*) FROM turma_curso tc JOIN turma t ON t.id = tc.turma_id "
                    "WHERE t.curso_id IS NOT NULL AND tc.curso_id <> t.curso_id"
                )
            ).scalar()
            if mism:
                errors.append(
                    f"{mism} oferta(s) com curso diferente do curso legado da turma"
                )

        print(f"turmas com curso_id: {n_turmas} | ofertas turma_curso: {n_ofertas}")
        if errors:
            print("DIVERGÊNCIAS:")
            for e in errors:
                print("  -", e)
            return 1
        print("OK: estrutura e backfill da Fase 1 íntegros.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
