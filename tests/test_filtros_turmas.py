"""Testes dos filtros da listagem de turmas."""

from datetime import date, time
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app import create_app
from app.database import db
from app.models import Curso, PeriodoLetivo, Turma, TurmaCurso, Unidade, User
from app.registros.turmas import aplicar_filtros_turmas, pos_filtrar_turmas
from app.services.turma_curso_horario import definir_grade
from app.utils.timezone import get_local_now
from config import Config

from _helpers import login_as


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


def _nomes(stmt):
    return {t.nome for t in db.session.execute(stmt).scalars().all()}


def _linha(body, turma_id):
    """True se a turma aparece como LINHA da tabela de resultados.

    Os <select> de "Nome da Turma" e "Professor" listam todas as turmas
    ativas da unidade independentemente do filtro aplicado (MER.md, Etapa
    K2), então ``"Natação Tarde" in body`` seria falso positivo para "a
    turma foi filtrada". O marcador confiável da linha é o link de ação da
    turma (``href="/turma/<id>"``, gerado por ``registros.ver_turma``).
    """
    return f'href="/turma/{turma_id}"' in body


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

    # A listagem abre filtrada pelo ano corrente (MER §8.10 — navegação por
    # período), e o filtro de ano exige vínculo com um período da unidade.
    # Sem período vigente na semente, nenhuma turma apareceria na tela e o
    # filtro de nome não poderia ser medido pelas linhas da tabela.
    ano = get_local_now().year
    periodo = PeriodoLetivo(
        nome="Corrente",
        data_inicio=date(ano, 1, 15),
        data_fim=date(ano, 12, 15),
        unidade_id=unidade.id,
        ativo=True,
    )
    db.session.add(periodo)
    db.session.flush()

    turmas = [
        Turma(
            nome="Informática Manhã",
            ativo=True,
            unidade_id=unidade.id,
            periodo_letivo_id=periodo.id,
            professor_id=prof_ana.id,
            turno="Manhã",
            programa="Profissionalizante",
        ),
        Turma(
            nome="Natação Tarde",
            ativo=True,
            unidade_id=unidade.id,
            periodo_letivo_id=periodo.id,
            professor_id=prof_bruno.id,
            turno="Tarde",
            programa="Esporte",
        ),
        Turma(
            nome="Horta Noite",
            ativo=True,
            unidade_id=unidade.id,
            periodo_letivo_id=periodo.id,
            professor_id=None,
            turno="Noite",
            programa="Meio Ambiente",
        ),
    ]
    db.session.add_all(turmas)
    db.session.flush()

    # H5a: os dias/horários vêm da GRADE da oferta ativa (não há colunas
    # escalares de agenda na turma). "Horta Noite" fica sem oferta — sem agenda.
    agendas = {
        "Informática Manhã": [
            (0, time(8, 0), time(9, 30)), (2, time(8, 0), time(9, 30)),
        ],
        "Natação Tarde": [
            (1, time(14, 0), time(15, 0)), (3, time(14, 0), time(15, 0)),
        ],
    }
    for turma in turmas:
        itens = agendas.get(turma.nome)
        if not itens:
            continue
        curso = Curso(nome=f"Curso {turma.nome}", unidade_id=unidade.id, ativo=True)
        db.session.add(curso)
        db.session.flush()
        oferta = TurmaCurso(
            turma_id=turma.id, curso_id=curso.id, unidade_id=unidade.id,
            ativo=True, principal=True, programa=turma.programa,
            professor_id=turma.professor_id, turno=turma.turno,
        )
        db.session.add(oferta)
        db.session.flush()
        definir_grade(oferta, itens)
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


def _seed_unidade_periodo_passado(app):
    """Unidade com período somente no ano ANTERIOR e uma turma sem período.

    Era o estado que expunha o defeito P2: `periodos_por_ano` não tem a chave
    do ano corrente, mas a listagem continua abrindo no ano vigente.

    A 'Turma Avulsa' tem periodo_letivo_id NULL — estado LEGADO: a criação
    de turma hoje exige período (select obrigatório em nova_turma e
    `periodo_letivo_id` required em turmas.py:719), mas turmas históricas
    ainda podem estar sem vínculo. Desde a ETAPA B6 (D3) elas aparecem na
    vista padrão com o selo "Sem período".
    Devolve (unidade_id, admin_id).
    """
    with app.test_request_context():
        unidade = Unidade(nome="Unidade Ano Anterior", ativo=True)
        admin = User(
            name="Admin Ano Anterior",
            email="admin.past@example.com",
            role="admin",
            first_login=False,
        )
        db.session.add_all([unidade, admin])
        db.session.flush()
        ano = get_local_now().year
        db.session.add(PeriodoLetivo(
            nome="Anterior",
            data_inicio=date(ano - 1, 2, 1),
            data_fim=date(ano - 1, 11, 30),
            unidade_id=unidade.id,
            ativo=True,
        ))
        db.session.add(Turma(
            nome="Turma Avulsa",
            ativo=True,
            unidade_id=unidade.id,
            turno="Manhã",
        ))
        db.session.commit()
        return unidade.id, admin.id


def test_listagem_padrao_inclui_turma_sem_periodo_e_nao_quebra_sem_periodo_no_ano(app, client):
    """ETAPA B6 (D3) + guarda anti-P2.

    Mantém o cerne do antigo teste de P2 (sem período no ano corrente a
    listagem não pode dar 500/KeyError e o ano vigente segue oferecido), mas
    agora a turma sem vínculo APARECE na vista padrão, marcada com o selo
    "Sem período". O comportamento inverso (escolher um período torna o
    filtro estrito e a turma sem período some) está coberto em
    tests/test_turma_curso_lista.py::test_turma_sem_periodo_some_quando_periodo_escolhido.
    """
    with app.app_context():
        unidade_id, admin_id = _seed_unidade_periodo_passado(app)
        turma_id = Turma.query.filter_by(nome="Turma Avulsa").first().id

    login_as(client, str(admin_id), unidade_id)
    ano = get_local_now().year
    resp = client.get("/turma")
    # Anti-P2: a listagem não pode quebrar (KeyError) quando o ano corrente
    # não tem período cadastrado.
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # O ano corrente segue oferecido como opção visual, mesmo sem período.
    assert f"ano_periodo={ano}" in html
    # D3: a turma sem vínculo entra na tabela da vista padrão...
    assert _linha(html, turma_id)
    # ... exibida com o selo dedicado.
    assert "Sem período" in html


def test_rota_listagem_aplica_filtro_nome(app, client):
    with app.app_context():
        unidade = _seed_turmas(app)
        ids = {t.nome: t.id for t in Turma.query.all()}
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

    login_as(client, str(admin_id), unidade_id)
    resp = client.get("/turma?nome=Informática")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # Marcador por linha (ver _linha): o nome também aparece nos <select>.
    assert _linha(html, ids["Informática Manhã"])
    assert not _linha(html, ids["Natação Tarde"])
    assert not _linha(html, ids["Horta Noite"])
    assert 'id="collapseFiltros" class="accordion-collapse collapse show"' in html
