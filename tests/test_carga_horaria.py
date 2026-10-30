"""
Testes unitários e de integração para carga horária de turmas.

Cobre:
    - formatar_ch(): conversão de minutos para string legível
    - Turma.carga_horaria_aula: cálculo de duração de aula (só pela GRADE)
    - Turma.carga_horaria_total: cálculo de carga horária total (só pela GRADE)
    - calcular_dias_aula_turma: cálculo de dias de aula efetivos (só pela GRADE)

H5a: a agenda vem exclusivamente de ``turma_curso_horario``. Turma sem oferta
ou oferta sem grade não têm agenda (nada de fallback para as colunas escalares).
"""

import pytest
from datetime import time, date
from app.utils.formatters import formatar_ch
from app.models import (
    Curso,
    DiaBloqueado,
    PeriodoLetivo,
    Turma,
    Unidade,
)
from app.models.enums import TipoDiaBloqueado
from app.database import db
from app.utils.logica import calcular_dias_aula_turma
from config import Config

from _helpers import nova_oferta


class SQLiteTestConfig(Config):
    SECRET_KEY = "chave-de-teste-s1-sem-valor-real-1234567890"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    WTF_CSRF_ENABLED = False


def _base(app, *, com_periodo=False):
    """Unidade + curso + turma persistidos (a agenda NÃO vive na turma)."""
    unidade = Unidade(nome="U CH", ativo=True)
    db.session.add(unidade)
    db.session.flush()
    curso = Curso(nome="Curso CH", unidade_id=unidade.id, ativo=True)
    db.session.add(curso)
    db.session.flush()
    periodo = None
    if com_periodo:
        periodo = PeriodoLetivo(
            nome="2024-1",
            data_inicio=date(2024, 1, 1),
            data_fim=date(2024, 12, 20),
            unidade_id=unidade.id,
            ativo=True,
        )
        db.session.add(periodo)
        db.session.flush()
    turma = Turma(
        nome="Teste",
        unidade_id=unidade.id,
        periodo_letivo_id=periodo.id if periodo else None,
        ativo=True,
    )
    db.session.add(turma)
    db.session.flush()
    return turma, curso, unidade, periodo


def _oferta_com_grade(turma, curso, unidade, itens):
    """Cria a oferta principal com a grade informada (sem colunas escalares)."""
    return nova_oferta(
        turma.id, curso.id, unidade.id, principal=True, grade=itens,
    )


class TestFormatarCH:
    """Testes para formatar_ch() - conversão de minutos para string legível."""

    def test_formatar_ch_60_minutos(self):
        """60 minutos deve retornar '1h'."""
        assert formatar_ch(60) == "1h"

    def test_formatar_ch_90_minutos(self):
        """90 minutos deve retornar '1h30min'."""
        assert formatar_ch(90) == "1h30min"

    def test_formatar_ch_1800_minutos(self):
        """1800 minutos (30 horas) deve retornar '30h'."""
        assert formatar_ch(1800) == "30h"

    def test_formatar_ch_75_minutos(self):
        """75 minutos deve retornar '1h15min'."""
        assert formatar_ch(75) == "1h15min"

    def test_formatar_ch_none(self):
        """None deve retornar '—'."""
        assert formatar_ch(None) == "—"

    def test_formatar_ch_zero(self):
        """0 deve retornar '—'."""
        assert formatar_ch(0) == "—"

    def test_formatar_ch_negativo(self):
        """Valores negativos devem retornar '—'."""
        assert formatar_ch(-10) == "—"


class TestTurmaCargaHorariaAula:
    """Testes para Turma.carga_horaria_aula (H5a: só a grade da oferta)."""

    def test_carga_horaria_aula_com_grade_uniforme(self, app):
        """Grade uniforme Seg/Qua 14:00–16:30 deve retornar 150 minutos."""
        with app.app_context():
            turma, curso, unidade, _ = _base(app)
            _oferta_com_grade(
                turma, curso, unidade,
                [(0, time(14, 0), time(16, 30)),
                 (2, time(14, 0), time(16, 30))],
            )
            assert turma.carga_horaria_aula == 150

    def test_carga_horaria_aula_sem_grade(self, app):
        """Sem oferta/grade não há agenda: None (sem fallback escalar)."""
        with app.app_context():
            turma, _, _, _ = _base(app)
            assert turma.carga_horaria_aula is None

    def test_carga_horaria_aula_grade_nao_uniforme(self, app):
        """Durações diferentes por dia não têm um valor único: None."""
        with app.app_context():
            turma, curso, unidade, _ = _base(app)
            _oferta_com_grade(
                turma, curso, unidade,
                [(0, time(14, 0), time(16, 0)),
                 (2, time(14, 0), time(17, 0))],
            )
            assert turma.carga_horaria_aula is None


class TestTurmaCargaHorariaTotal:
    """Testes para Turma.carga_horaria_total (H5a: só a grade da oferta)."""

    def test_carga_horaria_total_com_dados_validos(self, app):
        """C.H. total = tempo da grade × dias de aula no período."""
        with app.app_context():
            turma, curso, unidade, _ = _base(app)
            turma.data_inicio = date(2024, 1, 1)
            turma.data_fim = date(2024, 1, 31)
            _oferta_com_grade(
                turma, curso, unidade,
                [(0, time(14, 0), time(16, 0)),
                 (2, time(14, 0), time(16, 0))],
            )
            ch_total = turma.carga_horaria_total
            assert ch_total is not None
            assert ch_total > 0

    def test_carga_horaria_total_sem_grade(self, app):
        """Sem grade não há C.H. (None), sem ler coluna escalar."""
        with app.app_context():
            turma, _, _, _ = _base(app)
            turma.data_inicio = date(2024, 1, 1)
            turma.data_fim = date(2024, 1, 31)
            assert turma.carga_horaria_total is None

    def test_carga_horaria_total_sem_datas(self, app):
        """Sem data_inicio/data_fim deve retornar None."""
        with app.app_context():
            turma, curso, unidade, _ = _base(app)
            _oferta_com_grade(
                turma, curso, unidade,
                [(0, time(14, 0), time(16, 0))],
            )
            assert turma.carga_horaria_total is None


class TestCalcularDiasAulaTurma:
    """Testes para calcular_dias_aula_turma() (dias derivados da grade)."""

    def test_calcular_dias_sem_bloqueios(self, app):
        """Sem dias bloqueados, deve contar todos os dias da grade no período."""
        with app.app_context():
            turma, curso, unidade, _ = _base(app)
            turma.data_inicio = date(2024, 1, 1)  # Segunda
            turma.data_fim = date(2024, 1, 7)     # Domingo
            _oferta_com_grade(
                turma, curso, unidade,
                [(0, time(8), time(9)),
                 (2, time(8), time(9)),
                 (4, time(8), time(9))],
            )
            dias = calcular_dias_aula_turma(turma)
            # Segunda (1), Quarta (3), Sexta (5) = 3 dias
            assert dias == 3

    def test_calcular_dias_com_bloqueios(self, app):
        """Com dias bloqueados, deve descontar os dias especificados."""
        with app.app_context():
            turma, curso, unidade, periodo = _base(app, com_periodo=True)
            turma.data_inicio = date(2024, 1, 1)
            turma.data_fim = date(2024, 1, 7)
            _oferta_com_grade(
                turma, curso, unidade,
                [(0, time(8), time(9)),
                 (2, time(8), time(9)),
                 (4, time(8), time(9))],
            )

            # Bloquear a segunda (01/01/2024)
            db.session.add(DiaBloqueado(
                data=date(2024, 1, 1),
                tipo=TipoDiaBloqueado.FERIADO,
                descricao="Feriado",
                periodo_letivo_id=periodo.id,
                unidade_id=unidade.id,
            ))
            db.session.commit()

            dias = calcular_dias_aula_turma(turma)
            # Segunda bloqueada, sobram Quarta e Sexta = 2 dias
            assert dias == 2

    def test_calcular_dias_sem_grade(self, app):
        """Sem grade não há dias de aula: 0 (sem ler coluna escalar)."""
        with app.app_context():
            turma, _, _, _ = _base(app)
            turma.data_inicio = date(2024, 1, 1)
            turma.data_fim = date(2024, 1, 7)
            assert calcular_dias_aula_turma(turma) == 0

    def test_calcular_dias_periodo_invalido(self, app):
        """Data fim < data início deve retornar 0 (mesmo com grade)."""
        with app.app_context():
            turma, curso, unidade, _ = _base(app)
            turma.data_inicio = date(2024, 1, 7)
            turma.data_fim = date(2024, 1, 1)
            _oferta_com_grade(
                turma, curso, unidade,
                [(0, time(8), time(9))],
            )
            assert calcular_dias_aula_turma(turma) == 0


@pytest.fixture
def app():
    """Fixture para criar a aplicação Flask para testes."""
    from app import create_app
    app = create_app(SQLiteTestConfig)
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()
