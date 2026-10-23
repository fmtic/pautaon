"""
Testes da Onda 4 — Fase 4 (D3b-1): "frequência lançada" e pendências por oferta.

Cobrem `contar_pendencias_frequencia` e `app.main.dashboard_professor._aulas_pendentes`
com 2+ ofertas ativas. Cenários montados em torno de HOJE para casar com a
agenda das ofertas (vigência + dias da semana). REGRA GERAL verificada: com 0
ou 1 oferta o cálculo continua por turma, exatamente como antes.
"""

from datetime import date, timedelta

import pytest

from app import create_app, db
from app.main.dashboard_professor import _aulas_pendentes
from app.models import (
    Aluno,
    Curso,
    Frequencia,
    Inscricao,
    Turma,
    TurmaCurso,
    Unidade,
)
from app.models.enums import ConceitoFrequencia
from app.utils.frequencia import contar_pendencias_frequencia
from config import Config

HOJE = date.today()
_DIAS = ("Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo")
DIA_HOJE = _DIAS[HOJE.weekday()]
DIA_OUTRO = _DIAS[(HOJE.weekday() + 1) % 7]


class SQLiteTestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    WTF_CSRF_ENABLED = False


@pytest.fixture
def app():
    test_app = create_app(SQLiteTestConfig)
    test_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
    )
    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


def _seed(app, ofertas_cfg):
    """Cria unidade + turma (calendário legado = hoje) e uma oferta por cfg.

    cada cfg: dict(curso, dias, data_inicio, data_fim, alunos=[(nome, lançado)])
    'lançado=True' grava uma Frequencia da oferta em HOJE.
    Retorna o id da turma.
    """
    with app.app_context():
        unidade = Unidade(nome="Unidade D3b1", ativo=True)
        db.session.add(unidade)
        db.session.flush()

        turma = Turma(
            nome="Turma D3b1", unidade_id=unidade.id, ativo=True, curso_id=None,
            dias_semana=DIA_HOJE, data_inicio=HOJE, data_fim=HOJE,
        )
        db.session.add(turma)
        db.session.flush()

        for cfg in ofertas_cfg:
            curso = Curso(nome=cfg["curso"], unidade_id=unidade.id, ativo=True)
            db.session.add(curso)
            db.session.flush()
            oferta = TurmaCurso(
                turma_id=turma.id, curso_id=curso.id, unidade_id=unidade.id,
                ativo=True, dias_semana=cfg["dias"],
                data_inicio=cfg["data_inicio"], data_fim=cfg["data_fim"],
            )
            db.session.add(oferta)
            db.session.flush()
            for nome, lancado in cfg["alunos"]:
                aluno = Aluno(nome=nome, unidade_id=unidade.id, ativo=True)
                db.session.add(aluno)
                db.session.flush()
                db.session.add(Inscricao(
                    aluno_id=aluno.id, turma_id=turma.id,
                    turma_curso_id=oferta.id, ativo=True,
                ))
                if lancado:
                    db.session.add(Frequencia(
                        aluno_id=aluno.id, turma_id=turma.id,
                        turma_curso_id=oferta.id, data=HOJE,
                        conceito=ConceitoFrequencia.A, unidade_id=unidade.id,
                    ))
        db.session.commit()
        return turma.id


def _cfg(curso, alunos, dias=DIA_HOJE, inicio=HOJE, fim=HOJE):
    return {
        "curso": curso, "dias": dias, "data_inicio": inicio,
        "data_fim": fim, "alunos": alunos,
    }


def test_pendencia_por_oferta_segunda_oferta_nao_sobe_com_outra_lancada(app):
    """2 ofertas esperadas hoje; lançar só A → sobra a pendência da oferta B."""
    _seed(app, [
        _cfg("Natação", [("Aluno A1", True)]),
        _cfg("Judô", [("Aluno B1", False)]),
    ])
    with app.app_context():
        turma = Turma.query.one()
        # Uma pendência: a aula de hoje da oferta B (A está completa).
        assert contar_pendencias_frequencia([turma]) == 1
        pend = _aulas_pendentes([turma])
        assert len(pend) == 1
        assert pend[0]["data"] == HOJE
        assert "Judô" in pend[0]["oferta_label"]
        assert "Natação" not in [p["oferta_label"] for p in pend]


def test_oferta_fora_da_grade_hoje_nao_gera_pendencia(app):
    """Oferta B em outro dia da semana (não hoje) → sem pendência de B."""
    _seed(app, [
        _cfg("Natação", [("Aluno A1", True)]),
        _cfg("Judô", [("Aluno B1", False)], dias=DIA_OUTRO),
    ])
    with app.app_context():
        turma = Turma.query.one()
        assert contar_pendencias_frequencia([turma]) == 0
        assert _aulas_pendentes([turma]) == []


def test_oferta_fora_da_vigencia_nao_gera_pendencia(app):
    """Oferta B com vigência começando depois de hoje → sem pendência de B."""
    amanha = HOJE + timedelta(days=1)
    _seed(app, [
        _cfg("Natação", [("Aluno A1", True)]),
        _cfg("Judô", [("Aluno B1", False)], inicio=amanha, fim=amanha + timedelta(days=7)),
    ])
    with app.app_context():
        turma = Turma.query.one()
        assert contar_pendencias_frequencia([turma]) == 0
        assert _aulas_pendentes([turma]) == []


def test_oferta_unica_calculo_por_turma_inalterado(app):
    """1 oferta ativa: behaves como hoje (por turma), lançado→0, pendente→1."""
    # Lançado → sem pendência.
    _seed(app, [_cfg("Natação", [("Aluno A1", True)])])
    with app.app_context():
        turma = Turma.query.one()
        assert contar_pendencias_frequencia([turma]) == 0
        assert _aulas_pendentes([turma]) == []

    # Recria sem lançamento → pendência de 1 aula (critério legado por turma).
    with app.app_context():
        db.session.query(Frequencia).delete()
        db.session.commit()
        turma = Turma.query.one()
        assert contar_pendencias_frequencia([turma]) == 1


def test_contar_soma_por_oferta_com_2_e_por_turma_com_1(app):
    """2 ofertas não lançadas hoje → soma 2 (uma por oferta)."""
    _seed(app, [
        _cfg("Natação", [("Aluno A1", False)]),
        _cfg("Judô", [("Aluno B1", False)]),
    ])
    with app.app_context():
        turma = Turma.query.one()
        assert contar_pendencias_frequencia([turma]) == 2
