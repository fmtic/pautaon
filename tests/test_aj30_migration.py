"""AJ30 — migration de renomeação em SQLite (upgrade/downgrade idempotentes).

Segue o padrão de ``tests/test_valor_esportista_migration.py``: a migration é
chamada diretamente com um ``Operations.context`` apontando para o bind SQLite
do app de teste — não depende de ``flask db`` nem de PostgreSQL.

Cobre: pré-checagem somente leitura (aborta com valor fora do mapa), os três
renomes, CHECK final com NULL, repetição segura do upgrade, downgrade e a
guarda que recusa "Empregado" listando os ids.
"""

from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

import pytest
import sqlalchemy as sa
from _helpers import nova_oferta
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.database import db
from app.models import ConselhoClasse, Turma, Unidade

MIGRACAO = (
    Path(__file__).resolve().parents[1] / "migrations" / "versions"
    / "b8c9d0e1f2a3_aj30_situacao_final_vocabulario.py"
)
MIG = None  # preenchido pela fixture `mig` (o nome da fixture sombreia `mig`)

CHECK_ANTIGO = (
    "situacao_final IS NULL OR situacao_final IN "
    "('Aprovado', 'Reprovado por Falta', 'Desistente', 'Evadido', "
    "'Participação', 'Concluído')"
)


@pytest.fixture(scope="module")
def mig():
    global MIG
    especificacao = importlib.util.spec_from_file_location("aj30_migration", MIGRACAO)
    modulo = importlib.util.module_from_spec(especificacao)
    especificacao.loader.exec_module(modulo)
    MIG = modulo
    return modulo


def _operacoes():
    return Operations(MigrationContext.configure(db.session.connection()))


def _valores_check():
    return MIG._valores_da_check(db.session.connection())


def _preparar_schema_antigo():
    """db.create_all() gera a CHECK nova; trocamos pela CHECK pré-AJ30."""
    with _operacoes().batch_alter_table("conselho_classe", recreate="always") as lote:
        lote.drop_constraint("ck_conselho_situacao_final", type_="check")
        lote.create_check_constraint("ck_conselho_situacao_final", CHECK_ANTIGO)


def _remover_check():
    """Para simular dado órfão que a CHECK antiga não aceitaria."""
    with _operacoes().batch_alter_table("conselho_classe", recreate="always") as lote:
        lote.drop_constraint("ck_conselho_situacao_final", type_="check")


def _semear(app, valores):
    with app.app_context():
        unidade = Unidade(nome="Unidade Migration AJ30", ativo=True)
        db.session.add(unidade)
        db.session.flush()
        turma = Turma(
            nome="Turma Migration AJ30", unidade_id=unidade.id,
            data_inicio=date(2026, 1, 1), data_fim=date(2026, 6, 30), ativo=True,
        )
        db.session.add(turma)
        db.session.flush()
        oferta = nova_oferta(
            turma.id, 1, unidade.id, programa="Esporte", principal=True
        )
        for indice, valor in enumerate(valores):
            db.session.add(ConselhoClasse(
                turma_id=turma.id, aluno_id=1000 + indice,
                turma_curso_id=oferta.id, etapa="FINAL", concluido=True,
                situacao_final=valor, unidade_id=unidade.id,
            ))
        db.session.commit()


def _linhas():
    return db.session.execute(sa.text(
        "SELECT aluno_id, situacao_final FROM conselho_classe ORDER BY aluno_id"
    )).all()


def test_upgrade_renomeia_mantem_null_e_recria_check(app, mig):
    _preparar_schema_antigo()
    _semear(app, ["Concluído", "Participação", "Reprovado por Falta", "Aprovado", None])
    assert _valores_check() == {
        "Aprovado", "Reprovado por Falta", "Desistente",
        "Evadido", "Participação", "Concluído",
    }
    with Operations.context(MigrationContext.configure(db.session.connection())):
        mig.upgrade()
        # Reexecutar é seguro (idempotência por inspeção).
        mig.upgrade()
    db.session.commit()

    # Atenção: NÃO abrir `with app.app_context()` aqui — o teardown do contexto
    # aninhado remove a sessão e desfaz as DDL/DML ainda não commitadas.
    assert [linha.situacao_final for linha in _linhas()] == [
        "Aprovado", "Participante", "Reprovado por faltas", "Aprovado", None,
    ]
    assert _valores_check() == {
        "Aprovado", "Participante", "Reprovado por faltas",
        "Desistente", "Evadido", "Empregado",
    }


def test_downgrade_reverte_e_guarda_empregado(app, mig):
    _preparar_schema_antigo()
    _semear(app, ["Concluído", "Participação", "Reprovado por Falta"])
    with Operations.context(MigrationContext.configure(db.session.connection())):
        mig.upgrade()
        mig.downgrade()
        mig.downgrade()  # idempotente
    db.session.commit()

    # Ida e volta NÃO recupera o rótulo original dos alunos que eram
    # "Aprovado" antes da migration (agr viram "Concluído"): perda documentada.
    assert [linha.situacao_final for linha in _linhas()] == [
        "Concluído", "Participação", "Reprovado por Falta",
    ]
    assert _valores_check() == {
        "Aprovado", "Reprovado por Falta", "Desistente",
        "Evadido", "Participação", "Concluído",
    }

    # A CHECK antiga não aceita "Empregado": simulamos um dado órfão de
    # produção removendo a restrição só para inseri-lo e exercitar a guarda.
    _remover_check()
    with app.app_context():
        db.session.execute(sa.text(
            "UPDATE conselho_classe SET situacao_final = 'Empregado' "
            "WHERE aluno_id = 1001"
        ))
        db.session.commit()
    with Operations.context(MigrationContext.configure(db.session.connection())):
        with pytest.raises(RuntimeError, match="ids: 1001"):
            mig.downgrade()
    # A guarda é anterior a qualquer escrita.
    assert _linhas()[1].situacao_final == "Empregado"


def test_pre_checagem_aborta_sem_escrita(app, mig):
    _preparar_schema_antigo()
    _semear(app, ["Concluído", "Aprovado"])
    _remover_check()  # simula dado órfão encontrado em produção
    with app.app_context():
        db.session.execute(sa.text(
            "UPDATE conselho_classe SET situacao_final = 'Valor Fantasma' "
            "WHERE aluno_id = 1001"
        ))
        db.session.commit()

    with Operations.context(MigrationContext.configure(db.session.connection())):
        with pytest.raises(RuntimeError, match="ABORTADA antes de qualquer escrita"):
            mig.upgrade()
    with app.app_context():
        assert [linha.situacao_final for linha in _linhas()] == [
            "Concluído", "Valor Fantasma",
        ]
