"""H2-P4 / H5a — Escritores de oferta passam pelo `definir_grade` (porta única).

Cobertura:
    - criar_oferta_inicial_da_turma: a grade vem de `agenda=` (formulário);
      sem agenda completa é rejeitada (nada é gravado).
    - adicionar_oferta: herança da GRADE de uma oferta ativa; agenda ausente
      ou só domingo rejeitadas; substituição via editar_oferta regrava a
      grade; agenda vazia na edição preserva a grade anterior.
    - Escritores não corrompem grade NÃO uniforme ao editar outros campos.
    - POST /turma/editar/<id>: com oferta única a agenda do formulário é
      gravada via grade (com grade não uniforme também: decisão H4).
    - Escrita limitada (sem N+1): aplicar uma grade de K dias faz no máximo
      K INSERTs na tabela, sem UPDATE/DELETE por dia e sem sonda por dia.

H5a: as colunas escalares `dias_semana`/`hora_inicio`/`hora_fim` de `Turma`
e `TurmaCurso` não são semeadas, lidas nem asseridas aqui — a grade é a única
fonte de agenda (por isso não há mais casos de "projeção").
"""
from __future__ import annotations

from datetime import date, time

import pytest
from sqlalchemy import event

from app import db
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

from _helpers import login_as, itens_grade, nova_oferta

DATA_INI = date(2026, 3, 2)   # segunda-feira
DATA_FIM = date(2026, 12, 15)


class SQLiteTestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    WTF_CSRF_ENABLED = False


def _base(app, *, curso_na_turma=True):
    """Semente: unidade, 2 cursos, admin/professor e 1 turma SEM agenda.

    H5a: a turma não nasce com agenda — ela nasce com a oferta (grade).
    """
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

        turma = Turma(
            nome="T esc", unidade_id=unidade.id, ativo=True,
            curso_id=(c1.id if curso_na_turma else None),
            professor_id=p1.id, turno="Manhã",
            data_inicio=DATA_INI, data_fim=DATA_FIM,
            programa="Teste",
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
def test_oferta_inicial_cria_grade_uniforme(app):
    """Com `agenda=` a oferta inicial nasce com a grade informada."""
    ids = _base(app)
    with app.app_context():
        turma = _get(Turma, ids["turma"])
        oferta = criar_oferta_inicial_da_turma(
            turma, agenda=itens_grade("Segunda", time(9, 0), time(10, 0)),
        )
        db.session.commit()
        assert [
            (l.dia_semana, l.hora_inicio, l.hora_fim) for l in grade_da_oferta(oferta)
        ] == [(0, time(9, 0), time(10, 0))]
        # Persistiu de verdade (releitura do banco, não só a sessão)
        db.session.expire_all()
        oferta2 = _get(TurmaCurso, oferta.id)
        assert TurmaCursoHorario.query.filter_by(
            turma_curso_id=oferta2.id
        ).count() == 1


def test_oferta_inicial_sem_agenda_completa_rejeitada(app):
    """H5a: sem `agenda=` (e sem grade para herdar) não há grade — recusa,
    nunca grade parcial nem leitura das colunas da turma."""
    ids = _base(app)
    with app.app_context():
        turma = _get(Turma, ids["turma"])
        with pytest.raises(ValueError, match="agenda completa"):
            criar_oferta_inicial_da_turma(turma)
        db.session.rollback()
        assert TurmaCurso.query.count() == 0


# --- adicionar_oferta ----------------------------------------------------------
def test_adicionar_oferta_herda_agenda_da_grade_da_outra_oferta(app):
    """H5a: sem `agenda`, a herança vem da GRADE de uma oferta ativa (a
    principal quando houver) — nunca das colunas escalares da turma.

    O cenário usa uma turma SEM vínculo legado (`curso_id IS NULL`) que já
    tem uma oferta com grade (estado de dados migrados); a primeira oferta é
    semeada direto no modelo para não espelhar o vínculo na turma.
    """
    ids = _base(app, curso_na_turma=False)
    with app.app_context():
        turma = _get(Turma, ids["turma"])
        primeira = nova_oferta(
            turma.id, ids["c1"], ids["unidade"], principal=True,
            professor_id=ids["p1"],
            dias_semana="Segunda, Quarta", hora_inicio=time(8), hora_fim=time(10),
        )
        db.session.commit()

        segunda = adicionar_oferta(turma, curso_id=ids["c2"], programa="Teste")
        db.session.commit()
        assert [
            (l.dia_semana, l.hora_inicio, l.hora_fim)
            for l in grade_da_oferta(segunda)
        ] == [(0, time(8, 0), time(10, 0)), (2, time(8, 0), time(10, 0))]
        assert len(grade_da_oferta(primeira)) == 2


def test_adicionar_oferta_sem_agenda_rejeitada_sem_escrita(app):
    """Turma já vinculada (herança não se aplica): sem agenda → recusa total."""
    ids = _base(app)
    with app.app_context():
        turma = _get(Turma, ids["turma"])
        with pytest.raises(ValueError, match="ao menos um dia"):
            # Professor explícito: sem vínculo legado é que vale a herança da
            # turma (G1/P2), então aqui o id vem do formulário.
            adicionar_oferta(
                turma, curso_id=ids["c2"], programa="Teste",
                professor_id=ids["p1"],
            )
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
                agenda=itens_grade("Domingo", time(9), time(10)),
            )
        db.session.rollback()
        assert TurmaCurso.query.count() == 0


# --- editar_oferta --------------------------------------------------------------
def test_editar_oferta_substitui_grade(app):
    ids = _base(app, curso_na_turma=False)
    with app.app_context():
        turma = _get(Turma, ids["turma"])
        oferta = adicionar_oferta(
            turma, curso_id=ids["c1"], programa="Teste",
            agenda=itens_grade("Segunda", time(8), time(12)),
        )
        db.session.commit()

        editar_oferta(
            oferta, agenda=itens_grade("Terça", time(14), time(16)),
        )
        db.session.commit()
        assert [
            (l.dia_semana, l.hora_inicio, l.hora_fim) for l in grade_da_oferta(oferta)
        ] == [(1, time(14, 0), time(16, 0))]
        assert TurmaCursoHorario.query.count() == 1


def test_editar_oferta_agenda_vazia_preserva_grade(app):
    """`agenda=[]` é recusada (grade nunca fica vazia) e a grade anterior
    permanece intacta — antes do H5a este caso era o trio escalar incompleto."""
    ids = _base(app, curso_na_turma=False)
    with app.app_context():
        turma = _get(Turma, ids["turma"])
        oferta = adicionar_oferta(
            turma, curso_id=ids["c1"], programa="Teste",
            agenda=itens_grade("Segunda", time(8), time(12)),
        )
        db.session.commit()

        with pytest.raises(ValueError, match="não pode ficar vazia"):
            editar_oferta(oferta, agenda=[])
        db.session.rollback()

        db.session.expire_all()
        oferta2 = _get(TurmaCurso, oferta.id)
        assert [
            (l.dia_semana, l.hora_inicio, l.hora_fim)
            for l in grade_da_oferta(oferta2)
        ] == [(0, time(8, 0), time(12, 0))]


# --- grade NÃO uniforme preservada pelos escritores -----------------------------
def test_escritores_nao_corrompem_grade_nao_uniforme(app):
    ids = _base(app, curso_na_turma=False)
    with app.app_context():
        turma = _get(Turma, ids["turma"])
        oferta = adicionar_oferta(
            turma, curso_id=ids["c1"], programa="Teste",
            agenda=itens_grade("Segunda", time(8), time(10)),
        )
        db.session.commit()

        definir_grade(
            oferta, [(0, time(8, 0), time(10, 0)), (1, time(14, 0), time(16, 0))]
        )
        db.session.commit()
        assert grade_uniforme(oferta) is False

        # Escritor mexe só em campo não-agenda: a grade não é tocada.
        editar_oferta(oferta, turno="Noite")
        db.session.commit()
        assert grade_uniforme(oferta) is False
        assert [
            (l.dia_semana, l.hora_inicio, l.hora_fim) for l in grade_da_oferta(oferta)
        ] == [(0, time(8, 0), time(10, 0)), (1, time(14, 0), time(16, 0))]


# --- POST /turma/editar/<id> -------------------------------------------------------
def _loga(app, user_id):
    client = app.test_client()
    login_as(client, str(user_id))
    return client


def _seed_rota(app, grade_itens):
    """Turma + 1 oferta ativa única com a grade dada. Retorna ids."""
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
    (modo padrão). H5a: a agenda vai só para a grade, não para as colunas."""
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


def test_editar_turma_post_com_grade_uniforme_grava_via_grade(app):
    """Com grade uniforme a edição da Turma continua valendo: a agenda nova é
    convertida em grade pelo serviço e gravada na oferta única."""
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
                turma, curso_id=ids["c1"], programa="Teste", agenda=dias,
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
