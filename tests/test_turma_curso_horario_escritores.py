"""H2-P4 — Escritores de oferta passam pelo `definir_grade` (porta única).

Cobertura exigida pelo protocolo H2, passo 4:
    - criar_oferta_inicial_da_turma: grade uniforme a partir da agenda da
      turma + projeção; herança INCOMPLETA é rejeitada (nada é gravado).
    - adicionar_oferta: herança completa da turma; agenda ausente ou só
      domingo rejeitadas; substituição via editar_oferta recalcula a grade e
      a projeção; agenda incompleta na edição preserva a grade anterior.
    - Projeção: uniforme preenche o par escalar; não uniforme deixa as horas
      NULL — e os escritores não corrompem essa projeção ao editar outros
      campos.
    - POST /turma/editar/<id>: com grade NÃO uniforme os campos de agenda da
      turma são ignorados (flash); com grade uniforme a agenda nova espelha
      na oferta via definir_grade.
    - Escrita limitada (sem N+1): aplicar uma grade de K dias faz no máximo
      K INSERTs na tabela, sem UPDATE/DELETE por dia e sem sonda por dia.
"""
from __future__ import annotations

from datetime import date, time

import pytest
from sqlalchemy import event

from app import create_app, db
from app.models import Curso, Turma, TurmaCurso, TurmaCursoHorario, Unidade, User
from app.services.turma_curso import (
    adicionar_oferta,
    criar_oferta_inicial_da_turma,
    editar_oferta,
)
from app.services.turma_curso_horario import (
    definir_grade,
    grade_da_oferta,
    grade_uniforme,
)
from config import Config

from _helpers import nova_oferta

DATA_INI = date(2026, 3, 2)   # segunda-feira
DATA_FIM = date(2026, 12, 15)


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


def _base(app, *, agenda_completa=True, curso_na_turma=True):
    """Semente: unidade, 2 cursos, admin e 1 turma. Turma nasce com agenda
    Segunda 09:00–10:00 (completa) ou sem horas (incompleta). Retorna ids."""
    with app.app_context():
        unidade = Unidade(nome="U esc", ativo=True)
        db.session.add(unidade)
        db.session.flush()
        admin = User(
            name="Admin Esc", email="admin.esc@example.com",
            role="pedagogico", first_login=False, unidade_id=unidade.id,
        )
        p1 = User(
            name="Prof Um", email="prof1.esc@example.com",
            role="professor", first_login=False, unidade_id=unidade.id,
        )
        db.session.add_all([admin, p1])
        c1 = Curso(nome="Curso 1", unidade_id=unidade.id, ativo=True)
        c2 = Curso(nome="Curso 2", unidade_id=unidade.id, ativo=True)
        db.session.add_all([c1, c2])
        db.session.flush()

        kwargs = {}
        if agenda_completa:
            kwargs = dict(
                dias_semana="Segunda", hora_inicio=time(9, 0), hora_fim=time(10, 0),
            )
        turma = Turma(
            nome="T esc", unidade_id=unidade.id, ativo=True,
            curso_id=(c1.id if curso_na_turma else None),
            professor_id=p1.id, turno="Manhã",
            data_inicio=DATA_INI, data_fim=DATA_FIM,
            programa="Teste", **kwargs,
        )
        db.session.add(turma)
        db.session.commit()
        return {
            "unidade": unidade.id, "admin": admin.id, "p1": p1.id,
            "c1": c1.id, "c2": c2.id, "turma": turma.id,
        }


def _get(model, pk):
    return db.session.get(model, pk)


# --- criar_oferta_inicial_da_turma -------------------------------------------
def test_oferta_inicial_cria_grade_uniforme_com_projecao(app):
    ids = _base(app)
    with app.app_context():
        turma = _get(Turma, ids["turma"])
        oferta = criar_oferta_inicial_da_turma(turma)
        db.session.commit()
        assert [
            (l.dia_semana, l.hora_inicio, l.hora_fim) for l in grade_da_oferta(oferta)
        ] == [(0, time(9, 0), time(10, 0))]
        assert oferta.dias_semana == "Segunda"
        assert oferta.hora_inicio == time(9, 0) and oferta.hora_fim == time(10, 0)
        # Persistiu de verdade (releitura do banco, não só a sessão)
        db.session.expire_all()
        oferta2 = _get(TurmaCurso, oferta.id)
        assert TurmaCursoHorario.query.filter_by(
            turma_curso_id=oferta2.id
        ).count() == 1


def test_oferta_inicial_sem_agenda_completa_rejeitada(app):
    """Turma sem horas: a herança não monta grade — recusa, nunca grade parcial."""
    ids = _base(app, agenda_completa=False)
    with app.app_context():
        turma = _get(Turma, ids["turma"])
        with pytest.raises(ValueError, match="agenda completa"):
            criar_oferta_inicial_da_turma(turma)
        db.session.rollback()
        assert TurmaCurso.query.count() == 0


# --- adicionar_oferta ----------------------------------------------------------
def test_adicionar_oferta_herda_agenda_completa_da_turma(app):
    ids = _base(app, curso_na_turma=False)
    with app.app_context():
        turma = _get(Turma, ids["turma"])
        oferta = adicionar_oferta(turma, curso_id=ids["c1"], programa="Teste")
        db.session.commit()
        assert [l.dia_semana for l in grade_da_oferta(oferta)] == [0]
        assert oferta.hora_inicio == time(9, 0)


def test_adicionar_oferta_sem_agenda_rejeitada_sem_escrita(app):
    """Turma já vinculada (herança não se aplica): sem agenda → recusa total."""
    ids = _base(app)
    with app.app_context():
        turma = _get(Turma, ids["turma"])
        with pytest.raises(ValueError, match="ao menos um dia"):
            adicionar_oferta(turma, curso_id=ids["c2"], programa="Teste")
        db.session.rollback()
        assert TurmaCurso.query.count() == 0


def test_adicionar_oferta_so_domingo_rejeitada(app):
    """Domingo fora do domínio 0–5: agenda resultante fica vazia → recusa."""
    ids = _base(app, curso_na_turma=False)
    with app.app_context():
        turma = _get(Turma, ids["turma"])
        with pytest.raises(ValueError, match="ao menos um dia"):
            adicionar_oferta(
                turma, curso_id=ids["c1"], programa="Teste",
                dias_semana="Domingo", hora_inicio=time(9), hora_fim=time(10),
            )
        db.session.rollback()
        assert TurmaCurso.query.count() == 0


# --- editar_oferta --------------------------------------------------------------
def test_editar_oferta_substitui_grade_e_reprojeta(app):
    ids = _base(app, curso_na_turma=False)
    with app.app_context():
        turma = _get(Turma, ids["turma"])
        oferta = adicionar_oferta(
            turma, curso_id=ids["c1"], programa="Teste",
            dias_semana="Segunda", hora_inicio=time(8), hora_fim=time(12),
        )
        db.session.commit()

        editar_oferta(
            oferta, dias_semana="Terça",
            hora_inicio=time(14), hora_fim=time(16),
        )
        db.session.commit()
        assert [
            (l.dia_semana, l.hora_inicio, l.hora_fim) for l in grade_da_oferta(oferta)
        ] == [(1, time(14, 0), time(16, 0))]
        assert oferta.dias_semana == "Terça"
        assert oferta.hora_inicio == time(14, 0) and oferta.hora_fim == time(16, 0)
        assert TurmaCursoHorario.query.count() == 1


def test_editar_oferta_agenda_incompleta_preserva_grade(app):
    """Só hora_inicio enviado: fim vigente (12:00) não passa do início novo →
    agenda efetiva inválida → recusa e grade anterior intacta."""
    ids = _base(app, curso_na_turma=False)
    with app.app_context():
        turma = _get(Turma, ids["turma"])
        oferta = adicionar_oferta(
            turma, curso_id=ids["c1"], programa="Teste",
            dias_semana="Segunda", hora_inicio=time(8), hora_fim=time(12),
        )
        db.session.commit()

        with pytest.raises(ValueError, match="ao menos um dia"):
            editar_oferta(oferta, hora_inicio=time(14))
        db.session.rollback()

        db.session.expire_all()
        oferta2 = _get(TurmaCurso, oferta.id)
        assert [
            (l.dia_semana, l.hora_inicio, l.hora_fim)
            for l in grade_da_oferta(oferta2)
        ] == [(0, time(8, 0), time(12, 0))]


# --- projeção uniforme / NULL com escritores ------------------------------------
def test_escritores_nao_corrompem_projecao_nao_uniforme(app):
    ids = _base(app, curso_na_turma=False)
    with app.app_context():
        turma = _get(Turma, ids["turma"])
        oferta = adicionar_oferta(
            turma, curso_id=ids["c1"], programa="Teste",
            dias_semana="Segunda", hora_inicio=time(8), hora_fim=time(10),
        )
        db.session.commit()

        # Grade NÃO uniforme criada pelo serviço (H4 ainda não expõe isso na UI)
        definir_grade(
            oferta, [(0, time(8, 0), time(10, 0)), (1, time(14, 0), time(16, 0))]
        )
        db.session.commit()
        assert oferta.dias_semana == "Segunda, Terça"
        assert oferta.hora_inicio is None and oferta.hora_fim is None

        # Escritor mexe só em campo não-agenda: projeção NULL permanece
        editar_oferta(oferta, turno="Noite")
        db.session.commit()
        assert grade_uniforme(oferta) is False
        assert oferta.hora_inicio is None and oferta.hora_fim is None
        assert [l.dia_semana for l in grade_da_oferta(oferta)] == [0, 1]


# --- POST /turma/editar/<id> -------------------------------------------------------
def _loga(app, user_id):
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True
    return client


def _seed_rota(app, grade_itens):
    """Turma + 1 oferta ativa única com a grade dada (projeção via serviço).
    Turma nasce Segunda 09:00–10:00. Retorna ids."""
    ids = _base(app, curso_na_turma=True)
    with app.app_context():
        turma = _get(Turma, ids["turma"])
        oferta = nova_oferta(
            turma.id, ids["c1"], ids["unidade"],
            principal=True, ativo=True, professor_id=ids["p1"],
            turno="Manhã", data_inicio=DATA_INI, data_fim=DATA_FIM,
            programa="Teste",
        )
        definir_grade(oferta, grade_itens)
        turma.dias_semana = oferta.dias_semana
        turma.hora_inicio = oferta.hora_inicio
        turma.hora_fim = oferta.hora_fim
        db.session.commit()
        ids["oferta"] = oferta.id
    return ids


def _post_edit(app, ids, **over):
    client = _loga(app, ids["admin"])
    form = {
        "turma": "T esc",
        "programa": "Teste",
        "turno": "Manhã",
        "data_inicio": DATA_INI.isoformat(),
        "data_fim": DATA_FIM.isoformat(),
        "hora_inicio": "09:00",
        "hora_fim": "10:00",
        "professor_id": str(ids["p1"]),
        "dias_semana": "Segunda",
        "centro_custo": "",
        "curso_id": str(ids["c1"]),
        "periodo_letivo_id": "",
        "limpar_lancamentos": "0",
    }
    form.update(over)
    return client.post(f"/turma/editar/{ids['turma']}", data=form, follow_redirects=True)


def test_editar_turma_post_substitui_grade_nao_uniforme(app):
    """Decisão H4: com oferta ÚNICA a agenda é editável mesmo com grade não
    uniforme — o POST substitui a grade inteira pela agenda do formulário
    (modo padrão) e os escalares da Turma saem só da projeção."""
    ids = _seed_rota(app, [(0, time(9, 0), time(10, 0)), (1, time(14, 0), time(16, 0))])
    r = _post_edit(
        app, ids,
        dias_semana="Quarta", hora_inicio="11:00", hora_fim="12:00",
    )
    assert r.status_code == 200  # follow_redirects
    html = r.get_data(as_text=True)
    assert "não é uniforme" not in html

    with app.app_context():
        db.session.expire_all()
        oferta = _get(TurmaCurso, ids["oferta"])
        assert [
            (l.dia_semana, l.hora_inicio, l.hora_fim)
            for l in grade_da_oferta(oferta)
        ] == [(2, time(11, 0), time(12, 0))]
        turma = _get(Turma, ids["turma"])
        # Projeção da grade uniforme nos escalares da Turma e da oferta
        assert turma.dias_semana == "Quarta"
        assert turma.hora_inicio == time(11, 0) and turma.hora_fim == time(12, 0)
        assert oferta.dias_semana == "Quarta"
        assert oferta.hora_inicio == time(11, 0) and oferta.hora_fim == time(12, 0)


def test_editar_turma_post_espelha_agenda_com_grade_uniforme(app):
    """Com grade uniforme a edição da Turma continua valendo: a agenda nova é
    convertida em grade pelo serviço e espelhada na oferta única."""
    ids = _seed_rota(app, [(0, time(9, 0), time(10, 0))])
    r = _post_edit(
        app, ids,
        dias_semana="Quarta", hora_inicio="11:00", hora_fim="12:00",
    )
    assert r.status_code == 200

    with app.app_context():
        db.session.expire_all()
        oferta = _get(TurmaCurso, ids["oferta"])
        # Quarta = dia 2 no domínio date.weekday() (segunda = 0)
        assert [
            (l.dia_semana, l.hora_inicio, l.hora_fim)
            for l in grade_da_oferta(oferta)
        ] == [(2, time(11, 0), time(12, 0))]
        assert oferta.dias_semana == "Quarta"
        turma = _get(Turma, ids["turma"])
        assert turma.dias_semana == "Quarta"
        assert turma.hora_inicio == time(11, 0) and turma.hora_fim == time(12, 0)


# --- escrita limitada (sem N+1 de escrita) ----------------------------------------
def test_adicionar_oferta_escrita_limitada_sem_n_plus_1(app):
    """Grade de K dias → K linhas inseridas de uma vez: nenhum UPDATE/DELETE na
    tabela durante a criação e no máximo uma sonda de leitura da relação."""
    ids = _base(app, curso_na_turma=False)
    dias = [(d, time(9, 0), time(10, 0)) for d in range(5)]  # seg..sex

    stmts = []

    def _antes(conn, cur, statement, params, context, executemany):
        if "turma_curso_horario" in str(statement).lower():
            stmts.append(str(statement).upper())

    with app.app_context():
        event.listen(db.engine, "before_cursor_execute", _antes)
        try:
            turma = _get(Turma, ids["turma"])
            oferta = adicionar_oferta(
                turma, curso_id=ids["c1"], programa="Teste",
                dias_semana="Segunda, Terça, Quarta, Quinta, Sexta",
                hora_inicio=time(9), hora_fim=time(10),
            )
            db.session.commit()
        finally:
            event.remove(db.engine, "before_cursor_execute", _antes)

        inserts = sum(1 for s in stmts if s.lstrip().startswith("INSERT"))
        updates = sum(1 for s in stmts if "UPDATE" in s)
        deletes = sum(1 for s in stmts if "DELETE" in s)
        selects = sum(1 for s in stmts if s.lstrip().startswith("SELECT"))
        assert inserts >= 1 and inserts <= len(dias)  # batch ou 1/dia, nunca mais
        assert updates == 0 and deletes == 0          # grade nova: só inserir
        # Leituras da tabela são CONSTANTES por operação (acesso à relação +
        # selectin em lote), nunca uma sonda por dia: < K.
        assert selects < len(dias)
        assert TurmaCursoHorario.query.filter_by(
            turma_curso_id=oferta.id
        ).count() == len(dias)
