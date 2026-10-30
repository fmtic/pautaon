# ruff: noqa: F811
"""A1 (item 2) — status do conselho sem `situacao_final` no histórico.

Achado M1: a célula de situação do histórico imprimia ``I: None`` quando o
conselho da etapa existia mas `situacao_final` era NULL (estado criado pela
semente e pelo lançamento antes do fechamento). O contrato das demais telas é
exibir ``—`` para valor ausente.
"""

from datetime import date

from _helpers import login_as, nova_inscricao, nova_oferta

from app import db
from app.models import (
    Aluno,
    ConselhoClasse,
    Curso,
    PeriodoLetivo,
    Turma,
    Unidade,
    User,
)
from app.models.enums import EtapaConselho

DATA_INI = date(2026, 2, 2)
DATA_FIM = date(2026, 6, 30)


def _cenario(app):
    with app.app_context():
        un = Unidade(nome="Unidade A1S", ativo=True)
        user = User(
            name="Admin A1S",
            email="admin.a1s@example.com",
            role="admin",
            first_login=False,
            unidade_id=un.id,
        )
        db.session.add_all([un, user])
        db.session.flush()
        periodo = PeriodoLetivo(
            nome="P A1S",
            data_inicio=DATA_INI,
            data_fim=DATA_FIM,
            unidade_id=un.id,
            ativo=True,
        )
        db.session.add(periodo)
        db.session.flush()
        turma = Turma(
            nome="Turma A1S",
            turno="Manhã",
            data_inicio=DATA_INI,
            data_fim=DATA_FIM,
            periodo_letivo_id=periodo.id,
            unidade_id=un.id,
            ativo=True,
        )
        db.session.add(turma)
        db.session.flush()
        curso = Curso(nome="Curso A1S", unidade_id=un.id, ativo=True)
        db.session.add(curso)
        db.session.flush()
        oferta = nova_oferta(turma.id, curso.id, un.id, principal=True)
        aluno = Aluno(nome="Aluno A1S", unidade_id=un.id, ativo=True)
        db.session.add(aluno)
        db.session.flush()
        nova_inscricao(aluno.id, turma.id, oferta.id)
        db.session.add(
            ConselhoClasse(
                turma_id=turma.id,
                aluno_id=aluno.id,
                turma_curso_id=oferta.id,
                etapa=EtapaConselho.INICIAL,
                unidade_id=un.id,
                situacao_final=None,
                concluido=True,
            )
        )
        db.session.commit()
        return {
            "unidade": un.id,
            "user": user.id,
            "aluno": aluno.id,
        }


def test_status_ausente_imprime_travessao(app, client):
    ids = _cenario(app)
    login_as(client, ids["user"], ids["unidade"])

    resposta = client.get(f"/aluno/{ids['aluno']}/historico")
    assert resposta.status_code == 200
    corpo = resposta.get_data(as_text=True)

    # Antes: "<small>I: None · P: —</small>"; agora o bloco I/P é omitido.
    assert "I: None" not in corpo
    assert "P: None" not in corpo
    assert "I: —" not in corpo
