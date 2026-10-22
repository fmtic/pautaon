"""Testes dos filtros da listagem de turmas."""

from datetime import time
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app import create_app
from app.database import db
from app.models import Turma, Unidade, User
from app.registros.turmas import aplicar_filtros_turmas, pos_filtrar_turmas
from config import Config


class SQLiteTestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


@pytest.fixture
def app():
    test_app = create_app(SQLiteTestConfig)
    test_app.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    })
    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _nomes(stmt):
    return {t.nome for t in db.session.execute(stmt).scalars().all()}


def _seed_turmas(app):
    with app.test_request_context():
        return _criar_turmas()


def _criar_turmas():
    unidade = Unidade(nome="Unidade Filtro", ativo=True)
    prof_ana = User(
        name="Ana Souza",
        email="ana@example.com",
        role="professor",
        first_login=False,
    )
    prof_bruno = User(
        name="Bruno Lima",
        email="bruno@example.com",
        role="professor",
        first_login=False,
    )
    db.session.add_all([unidade, prof_ana, prof_bruno])
    db.session.flush()

    turmas = [
        Turma(
            nome="Informática Manhã",
            ativo=True,
            unidade_id=unidade.id,
            professor_id=prof_ana.id,
            turno="Manhã",
            programa="Profissionalizante",
            dias_semana="Segunda, Quarta",
            hora_inicio=time(8, 0),
            hora_fim=time(9, 30),
        ),
        Turma(
            nome="Natação Tarde",
            ativo=True,
            unidade_id=unidade.id,
            professor_id=prof_bruno.id,
            turno="Tarde",
            programa="Esporte",
            dias_semana="Terça, Quinta",
            hora_inicio=time(14, 0),
            hora_fim=time(15, 0),
        ),
        Turma(
            nome="Horta Noite",
            ativo=True,
            unidade_id=unidade.id,
            professor_id=None,
            turno="Noite",
            programa="Meio Ambiente",
            dias_semana="Sábado",
            hora_inicio=time(19, 0),
            hora_fim=time(21, 0),
        ),
    ]
    db.session.add_all(turmas)
    db.session.commit()
    return unidade


class TestAplicarFiltrosTurmas:
    def test_filtra_por_nome(self, app):
        with app.app_context():
            _seed_turmas(app)
            stmt = aplicar_filtros_turmas(select(Turma), {"nome": "natação"})
            assert _nomes(stmt) == {"Natação Tarde"}

    def test_filtra_por_turno(self, app):
        with app.app_context():
            _seed_turmas(app)
            stmt = aplicar_filtros_turmas(select(Turma), {"turno": "Manhã"})
            assert _nomes(stmt) == {"Informática Manhã"}

    def test_filtra_por_programa(self, app):
        with app.app_context():
            _seed_turmas(app)
            stmt = aplicar_filtros_turmas(select(Turma), {"programa": "Esporte"})
            assert _nomes(stmt) == {"Natação Tarde"}

    def test_filtra_por_dia(self, app):
        with app.app_context():
            _seed_turmas(app)
            stmt = aplicar_filtros_turmas(select(Turma), {"dia": "Quarta"})
            assert _nomes(stmt) == {"Informática Manhã"}

    def test_filtra_por_horario_inicio(self, app):
        with app.app_context():
            _seed_turmas(app)
            stmt = aplicar_filtros_turmas(select(Turma), {"horario_inicio": "14:00"})
            assert _nomes(stmt) == {"Natação Tarde"}

    def test_filtra_por_professor(self, app):
        with app.app_context():
            _seed_turmas(app)
            stmt = aplicar_filtros_turmas(select(Turma), {"professor": "ana"})
            assert _nomes(stmt) == {"Informática Manhã"}

    def test_professor_exclui_turma_sem_professor(self, app):
        with app.app_context():
            _seed_turmas(app)
            stmt = aplicar_filtros_turmas(select(Turma), {"professor": "Horta"})
            assert _nomes(stmt) == set()

    def test_argumentos_vazios_nao_filtram(self, app):
        with app.app_context():
            _seed_turmas(app)
            stmt = aplicar_filtros_turmas(
                select(Turma),
                {
                    "nome": "",
                    "professor": "  ",
                    "turno": "",
                    "horario_inicio": "invalido",
                },
            )
            assert len(_nomes(stmt)) == 3

    def test_filtros_combinam_and(self, app):
        with app.app_context():
            _seed_turmas(app)
            stmt = aplicar_filtros_turmas(
                select(Turma),
                {"turno": "Tarde", "programa": "Esporte", "dia": "Terça"},
            )
            assert _nomes(stmt) == {"Natação Tarde"}


class TestPosFiltrarTurmas:
    def test_min_alunos(self):
        turmas = [
            SimpleNamespace(nome="A", alunos_ativos_count=2, freq_geral=100,
                            carga_horaria_aula=60, carga_horaria_total=600),
            SimpleNamespace(nome="B", alunos_ativos_count=10, freq_geral=100,
                            carga_horaria_aula=60, carga_horaria_total=600),
        ]
        filtradas = pos_filtrar_turmas(turmas, {"min_alunos": "5"})
        assert [t.nome for t in filtradas] == ["B"]

    def test_min_freq(self):
        turmas = [
            SimpleNamespace(nome="A", alunos_ativos_count=1, freq_geral=50,
                            carga_horaria_aula=60, carga_horaria_total=600),
            SimpleNamespace(nome="B", alunos_ativos_count=1, freq_geral=80,
                            carga_horaria_aula=60, carga_horaria_total=600),
        ]
        filtradas = pos_filtrar_turmas(turmas, {"min_freq": "75"})
        assert [t.nome for t in filtradas] == ["B"]

    def test_min_ch_aula_em_horas(self):
        turmas = [
            SimpleNamespace(nome="A", alunos_ativos_count=1, freq_geral=100,
                            carga_horaria_aula=60, carga_horaria_total=600),
            SimpleNamespace(nome="B", alunos_ativos_count=1, freq_geral=100,
                            carga_horaria_aula=90, carga_horaria_total=900),
        ]
        filtradas = pos_filtrar_turmas(turmas, {"min_ch_aula": "1.5"})
        assert [t.nome for t in filtradas] == ["B"]

    def test_min_ch_total_em_horas(self):
        turmas = [
            SimpleNamespace(nome="A", alunos_ativos_count=1, freq_geral=100,
                            carga_horaria_aula=60, carga_horaria_total=600),
            SimpleNamespace(nome="B", alunos_ativos_count=1, freq_geral=100,
                            carga_horaria_aula=60, carga_horaria_total=1800),
        ]
        filtradas = pos_filtrar_turmas(turmas, {"min_ch_total": "20"})
        assert [t.nome for t in filtradas] == ["B"]

    def test_ch_none_fica_de_fora(self):
        turmas = [
            SimpleNamespace(nome="A", alunos_ativos_count=1, freq_geral=100,
                            carga_horaria_aula=None, carga_horaria_total=None),
        ]
        assert pos_filtrar_turmas(turmas, {"min_ch_aula": "1"}) == []
        assert pos_filtrar_turmas(turmas, {"min_ch_total": "1"}) == []

    def test_numeros_invalidos_sao_ignorados(self):
        turmas = [
            SimpleNamespace(nome="A", alunos_ativos_count=1, freq_geral=10,
                            carga_horaria_aula=30, carga_horaria_total=30),
        ]
        filtradas = pos_filtrar_turmas(
            turmas,
            {"min_alunos": "x", "min_freq": "", "min_ch_aula": "abc"},
        )
        assert [t.nome for t in filtradas] == ["A"]


def test_rota_listagem_aplica_filtro_nome(app, client):
    with app.app_context():
        unidade = _seed_turmas(app)
        with app.test_request_context():
            admin = User(
                name="Administrador",
                email="admin@example.com",
                role="admin",
                first_login=False,
            )
            db.session.add(admin)
            db.session.commit()
            admin_id = admin.id
            unidade_id = unidade.id

    with client.session_transaction() as session:
        session["_user_id"] = str(admin_id)
        session["_fresh"] = True
        session["unidade_id"] = unidade_id

    resp = client.get("/turma?nome=Informática")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Informática Manhã" in html
    assert "Natação Tarde" not in html
    assert "Horta Noite" not in html
    assert 'id="collapseFiltros" class="accordion-collapse collapse show"' in html
