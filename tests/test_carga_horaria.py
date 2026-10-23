"""
Testes unitários e de integração para carga horária de turmas.

Cobre:
    - formatar_ch(): conversão de minutos para string legível
    - Turma.carga_horaria_aula: cálculo de duração de aula
    - Turma.carga_horaria_total: cálculo de carga horária total
    - calcular_dias_aula_turma: cálculo de dias de aula efetivos
"""

import pytest
from datetime import time, date
from app.utils.formatters import formatar_ch
from app.models import Turma, PeriodoLetivo, Curso, Unidade, User
from app.database import db
from app.utils.logica import calcular_dias_aula_turma
from config import Config


class SQLiteTestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    WTF_CSRF_ENABLED = False


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
    """Testes para Turma.carga_horaria_aula."""

    def test_carga_horaria_aula_com_horarios_validos(self, app):
        """Hora início 14:00 e hora fim 16:30 deve retornar 150 minutos."""
        with app.app_context():
            turma = Turma(
                nome="Teste",
                hora_inicio=time(14, 0),
                hora_fim=time(16, 30),
                unidade_id=1,
                ativo=True
            )
            assert turma.carga_horaria_aula == 150

    def test_carga_horaria_aula_sem_hora_inicio(self, app):
        """Sem hora_inicio deve retornar None."""
        with app.app_context():
            turma = Turma(
                nome="Teste",
                hora_inicio=None,
                hora_fim=time(16, 30),
                unidade_id=1,
                ativo=True
            )
            assert turma.carga_horaria_aula is None

    def test_carga_horaria_aula_sem_hora_fim(self, app):
        """Sem hora_fim deve retornar None."""
        with app.app_context():
            turma = Turma(
                nome="Teste",
                hora_inicio=time(14, 0),
                hora_fim=None,
                unidade_id=1,
                ativo=True
            )
            assert turma.carga_horaria_aula is None

    def test_carga_horaria_aula_hora_fim_menor_igual_inicio(self, app):
        """Hora fim <= hora início deve retornar None."""
        with app.app_context():
            turma1 = Turma(
                nome="Teste",
                hora_inicio=time(16, 30),
                hora_fim=time(14, 0),
                unidade_id=1,
                ativo=True
            )
            assert turma1.carga_horaria_aula is None

            turma2 = Turma(
                nome="Teste",
                hora_inicio=time(14, 0),
                hora_fim=time(14, 0),
                unidade_id=1,
                ativo=True
            )
            assert turma2.carga_horaria_aula is None


class TestTurmaCargaHorariaTotal:
    """Testes para Turma.carga_horaria_total."""

    def test_carga_horaria_total_com_dados_validos(self, app):
        """C.H. total = C.H. aula × dias efetivos."""
        with app.app_context():
            turma = Turma(
                nome="Teste",
                hora_inicio=time(14, 0),
                hora_fim=time(16, 0),  # 120 minutos por aula
                data_inicio=date(2024, 1, 1),
                data_fim=date(2024, 1, 31),
                dias_semana="Segunda, Quarta",
                unidade_id=1,
                ativo=True
            )
            # Calcula dias efetivos (segundas e quartas em janeiro 2024)
            ch_total = turma.carga_horaria_total
            assert ch_total is not None
            assert ch_total > 0

    def test_carga_horaria_total_sem_hora_inicio(self, app):
        """Sem hora_inicio deve retornar None."""
        with app.app_context():
            turma = Turma(
                nome="Teste",
                hora_inicio=None,
                hora_fim=time(16, 0),
                data_inicio=date(2024, 1, 1),
                data_fim=date(2024, 1, 31),
                dias_semana="Segunda",
                unidade_id=1,
                ativo=True
            )
            assert turma.carga_horaria_total is None

    def test_carga_horaria_total_sem_dias_semana(self, app):
        """Sem dias_semana deve retornar None."""
        with app.app_context():
            turma = Turma(
                nome="Teste",
                hora_inicio=time(14, 0),
                hora_fim=time(16, 0),
                data_inicio=date(2024, 1, 1),
                data_fim=date(2024, 1, 31),
                dias_semana=None,
                unidade_id=1,
                ativo=True
            )
            assert turma.carga_horaria_total is None

    def test_carga_horaria_total_sem_datas(self, app):
        """Sem data_inicio/data_fim deve retornar None."""
        with app.app_context():
            turma = Turma(
                nome="Teste",
                hora_inicio=time(14, 0),
                hora_fim=time(16, 0),
                data_inicio=None,
                data_fim=None,
                dias_semana="Segunda",
                unidade_id=1,
                ativo=True
            )
            assert turma.carga_horaria_total is None


class TestCalcularDiasAulaTurma:
    """Testes para calcular_dias_aula_turma()."""

    def test_calcular_dias_sem_bloqueios(self, app):
        """Sem dias bloqueados, deve contar todos os dias da semana no período."""
        with app.app_context():
            turma = Turma(
                nome="Teste",
                data_inicio=date(2024, 1, 1),  # Segunda
                data_fim=date(2024, 1, 7),   # Domingo
                dias_semana="Segunda, Quarta, Sexta",
                unidade_id=1,
                ativo=True
            )
            dias = calcular_dias_aula_turma(turma)
            # Segunda (1), Quarta (3), Sexta (5) = 3 dias
            assert dias == 3

    def test_calcular_dias_com_bloqueios(self, app):
        """Com dias bloqueados, deve descontar os dias especificados."""
        with app.app_context():
            from app.models import DiaBloqueado
            from app.models.enums import TipoDiaBloqueado

            periodo = PeriodoLetivo(
                nome="2024-1",
                data_inicio=date(2024, 1, 1),
                data_fim=date(2024, 12, 20),
                unidade_id=1,
                ativo=True,
            )
            db.session.add(periodo)
            db.session.flush()

            turma = Turma(
                nome="Teste",
                data_inicio=date(2024, 1, 1),
                data_fim=date(2024, 1, 7),
                dias_semana="Segunda, Quarta, Sexta",
                periodo_letivo_id=periodo.id,
                unidade_id=1,
                ativo=True
            )

            # Bloquear a segunda (01/01/2024)
            bloqueio = DiaBloqueado(
                data=date(2024, 1, 1),
                tipo=TipoDiaBloqueado.FERIADO,
                descricao="Feriado",
                periodo_letivo_id=periodo.id,
                unidade_id=1
            )
            db.session.add(bloqueio)
            db.session.commit()

            dias = calcular_dias_aula_turma(turma)
            # Segunda bloqueada, sobram Quarta e Sexta = 2 dias
            assert dias == 2

    def test_calcular_dias_sem_dias_semana(self, app):
        """Sem dias_semana, deve retornar 0."""
        with app.app_context():
            turma = Turma(
                nome="Teste",
                data_inicio=date(2024, 1, 1),
                data_fim=date(2024, 1, 7),
                dias_semana=None,
                unidade_id=1,
                ativo=True
            )
            dias = calcular_dias_aula_turma(turma)
            assert dias == 0

    def test_calcular_dias_periodo_invalido(self, app):
        """Data fim < data início deve retornar 0."""
        with app.app_context():
            turma = Turma(
                nome="Teste",
                data_inicio=date(2024, 1, 7),
                data_fim=date(2024, 1, 1),
                dias_semana="Segunda",
                unidade_id=1,
                ativo=True
            )
            dias = calcular_dias_aula_turma(turma)
            assert dias == 0


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
