"""H4 — Passo 4: UI de grade por dia (test client, só servidor).

Cobre o contrato novo do formulário (``grade_do_formulario``) nas três telas
que gravam agenda — nova_turma, editar_turma e rotas de oferta:

    - modo padrão = comportamento atual (par único replicado nos dias);
    - modo personalizado (``horario_por_dia`` + ``hora_inicio_<w>/hora_fim_<w>``)
      cria grade NÃO uniforme em turma nova, oferta nova e oferta editada;
    - editar_turma com 1 oferta grava pela definir_grade da oferta única e os
      escalares da Turma só mudam por projeção; com 2+ ofertas o bloqueio do
      POST permanece (só o nome grava);
    - erros por dia (fim <= início, dia marcado sem hora, domingo) devolvem o
      formulário preenchido (inclusive modo personalizado aberto); hora em dia
      NÃO marcado é ignorada;
    - edição de oferta com grade não uniforme abre em modo personalizado;
    - reenviar o mesmo formulário é idempotente (nada duplica nem deriva).
"""

import re
from datetime import date, time

from app import create_app, db
from app.models import (
    Curso,
    PeriodoLetivo,
    Turma,
    TurmaCurso,
    TurmaCursoHorario,
    Unidade,
    User,
)
from app.services.turma_curso_horario import definir_grade
from config import Config

DATA_INI = date(2026, 3, 2)   # segunda-feira
DATA_FIM = date(2026, 12, 15)


class SQLiteTestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    WTF_CSRF_ENABLED = False


def _loga(app, user_id, unidade_id):
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True
        session["unidade_id"] = unidade_id
    return client


def _seed(*, ofertas=0, grade=None, duplo_prof=False):
    """Unidade + período + turma "T H4" (Seg/Qua 08:00–11:00) com `ofertas`
    ofertas ativas. `grade` são os itens da oferta única (default uniforme
    Seg/Qua 08:00–11:00). Retorna (app, ids)."""
    app = create_app(SQLiteTestConfig)
    with app.app_context():
        db.create_all()
        unidade = Unidade(nome="U H4", ativo=True)
        db.session.add(unidade)
        db.session.flush()
        coord = User(
            name="Coord H4", email="coord.h4@example.com", role="pedagogico",
            first_login=False, unidade_id=unidade.id,
        )
        p1 = User(
            name="Prof Um", email="p1.h4@example.com", role="professor",
            first_login=False, unidade_id=unidade.id,
        )
        p2 = User(
            name="Prof Dois", email="p2.h4@example.com", role="professor",
            first_login=False, unidade_id=unidade.id,
        )
        db.session.add_all([coord, p1, p2])
        periodo = PeriodoLetivo(
            nome="2026.1", data_inicio=DATA_INI, data_fim=DATA_FIM,
            unidade_id=unidade.id, ativo=True,
        )
        db.session.add(periodo)
        cA = Curso(nome="Curso A", unidade_id=unidade.id, ativo=True)
        cB = Curso(nome="Curso B", unidade_id=unidade.id, ativo=True)
        db.session.add_all([cA, cB])
        db.session.flush()

        turma = Turma(
            nome="T H4", unidade_id=unidade.id, curso_id=cA.id,
            professor_id=p1.id, turno="Manhã",
            data_inicio=DATA_INI, data_fim=DATA_FIM,
            periodo_letivo_id=periodo.id, programa="Profissionalizante",
            ativo=True, ordenacao=1,
        )
        db.session.add(turma)
        db.session.flush()

        oferta_ids = []
        prof_oferta = p2.id if duplo_prof else p1.id
        for i in range(ofertas):
            oferta = TurmaCurso(
                turma_id=turma.id, curso_id=(cA.id if i == 0 else cB.id),
                unidade_id=unidade.id, ativo=True, principal=(i == 0),
                professor_id=prof_oferta, turno="Manhã",
                data_inicio=DATA_INI, data_fim=DATA_FIM,
                programa="Profissionalizante",
            )
            db.session.add(oferta)
            db.session.flush()
            definir_grade(
                oferta,
                grade if (grade and i == 0)
                else [(0, time(8), time(11)), (2, time(8), time(11))],
            )
            oferta_ids.append(oferta.id)

        db.session.commit()
        ids = {
            "coord": coord.id, "unidade": unidade.id, "p1": p1.id,
            "p2": p2.id, "periodo": periodo.id, "cA": cA.id, "cB": cB.id,
            "turma": turma.id, "ofertas": oferta_ids,
        }
    return app, ids


def _grade_rows(app, oferta_id):
    with app.app_context():
        linhas = (
            TurmaCursoHorario.query.filter_by(turma_curso_id=oferta_id)
            .order_by(TurmaCursoHorario.dia_semana)
            .all()
        )
        return [(l.dia_semana, l.hora_inicio, l.hora_fim) for l in linhas]


GRADE_POR_DIA = {
    "horario_por_dia": "1",
    "dias_semana": ["0", "2"],
    "hora_inicio": "08:00",
    "hora_fim": "11:00",
    "hora_inicio_0": "08:00",
    "hora_fim_0": "11:00",
    "hora_inicio_2": "14:00",
    "hora_fim_2": "17:00",
}
GRADE_PADRAO = {"dias_semana": ["0", "2"], "hora_inicio": "08:00", "hora_fim": "11:00"}


def _form_turma_base(ids, **over):
    form = {
        "turma": "T H4",
        "periodo_letivo_id": str(ids["periodo"]),
        "curso_id": str(ids["cA"]),
        "programa": "Profissionalizante",
        "turno": "Manhã",
        "professor_id": str(ids["p1"]),
        "centro_custo": "",
    }
    form.update(over)
    return form


def _form_oferta(ids, curso="cB", prof="p2", **over):
    form = {
        "curso_id": str(ids[curso]),
        "programa": "Profissionalizante",
        "professor_id": str(ids[prof]),
        "turno": "Tarde",
        "data_inicio": DATA_INI.isoformat(),
        "data_fim": DATA_FIM.isoformat(),
        "centro_custo": "",
    }
    form.update(over)
    return form


# --- modo padrão (igual ao comportamento atual) -------------------------------
def test_modo_padrao_nova_turma_replica_par_em_todos_os_dias():
    app, ids = _seed(ofertas=0)
    client = _loga(app, ids["coord"], ids["unidade"])
    r = client.post("/turma/nova", data=_form_turma_base(ids, **GRADE_PADRAO))
    assert r.status_code == 302
    nova_id = int(re.search(r"/turma/(\d+)/ofertas", r.headers["Location"]).group(1))
    with app.app_context():
        oferta = TurmaCurso.query.filter_by(turma_id=nova_id).one()
    assert _grade_rows(app, oferta.id) == [
        (0, time(8), time(11)), (2, time(8), time(11)),
    ]


def test_modo_personalizado_nova_turma_cria_grade_nao_uniforme():
    app, ids = _seed(ofertas=0)
    client = _loga(app, ids["coord"], ids["unidade"])
    r = client.post("/turma/nova", data=_form_turma_base(ids, **GRADE_POR_DIA))
    assert r.status_code == 302
    nova_id = int(re.search(r"/turma/(\d+)/ofertas", r.headers["Location"]).group(1))
    with app.app_context():
        oferta = TurmaCurso.query.filter_by(turma_id=nova_id).one()
    assert _grade_rows(app, oferta.id) == [
        (0, time(8), time(11)), (2, time(14), time(17)),
    ]


# --- oferta nova / oferta editada em modo personalizado -----------------------
def test_modo_personalizado_oferta_nova():
    app, ids = _seed(ofertas=1)
    client = _loga(app, ids["coord"], ids["unidade"])
    r = client.post(
        f"/turma/{ids['turma']}/ofertas/nova",
        data=_form_oferta(ids, **GRADE_POR_DIA),
    )
    assert r.status_code == 302
    with app.app_context():
        nova = (
            TurmaCurso.query.filter_by(turma_id=ids["turma"])
            .order_by(TurmaCurso.id.desc())
            .first()
        )
        nova_id = nova.id
    assert _grade_rows(app, nova_id) == [
        (0, time(8), time(11)), (2, time(14), time(17)),
    ]


def test_modo_personalizado_oferta_editada_e_get_abre_personalizado():
    app, ids = _seed(ofertas=1)
    client = _loga(app, ids["coord"], ids["unidade"])
    r = client.post(
        f"/turma/oferta/{ids['ofertas'][0]}/editar",
        data=_form_oferta(ids, curso="cA", prof="p1", turno="Manhã", **GRADE_POR_DIA),
    )
    assert r.status_code == 302
    assert _grade_rows(app, ids["ofertas"][0]) == [
        (0, time(8), time(11)), (2, time(14), time(17)),
    ]
    # A edição da oferta não uniforme abre já em modo personalizado, preenchida.
    html = client.get(f"/turma/{ids['turma']}/ofertas").get_data(as_text=True)
    assert re.search(r'name="horario_por_dia"[^>]*checked', html)
    assert re.search(r'name="hora_inicio_2"[^>]*value="14:00"', html)
    assert re.search(r'name="hora_fim_2"[^>]*value="17:00"', html)


def test_turma_uma_oferta_nao_uniforme_e_editavel_nao_bloqueia():
    """Decisão H4: critério de bloqueio é só "2+ ofertas"."""
    app, ids = _seed(
        ofertas=1, grade=[(0, time(8), time(11)), (2, time(14), time(17))]
    )
    client = _loga(app, ids["coord"], ids["unidade"])
    html = client.get(f"/turma/editar/{ids['turma']}").get_data(as_text=True)
    assert "Somente leitura" not in html
    # Componente presente (checkboxes data-weekday) e aberto em personalizado.
    assert 'data-weekday="4"' in html
    assert re.search(r'name="horario_por_dia"[^>]*checked', html)


# --- editar_turma: 1 oferta grava pela grade; 2+ mantém bloqueio --------------
def test_editar_turma_uma_oferta_grava_via_grade_com_projecao():
    app, ids = _seed(ofertas=1)
    client = _loga(app, ids["coord"], ids["unidade"])
    form = _form_turma_base(
        ids,
        **{"data_inicio": DATA_INI.isoformat(), "data_fim": DATA_FIM.isoformat(),
           "limpar_lancamentos": "0"},
        **GRADE_POR_DIA,
    )
    r = client.post(f"/turma/editar/{ids['turma']}", data=form)
    assert r.status_code == 302
    assert _grade_rows(app, ids["ofertas"][0]) == [
        (0, time(8), time(11)), (2, time(14), time(17)),
    ]


def test_editar_turma_modo_padrao_atualiza_grade_uniforme():
    app, ids = _seed(ofertas=1)
    client = _loga(app, ids["coord"], ids["unidade"])
    form = _form_turma_base(
        ids,
        **{
            "data_inicio": DATA_INI.isoformat(), "data_fim": DATA_FIM.isoformat(),
            "limpar_lancamentos": "0",
            "dias_semana": ["1"], "hora_inicio": "09:00", "hora_fim": "10:00",
        },
    )
    r = client.post(f"/turma/editar/{ids['turma']}", data=form)
    assert r.status_code == 302
    assert _grade_rows(app, ids["ofertas"][0]) == [(1, time(9), time(10))]


def test_editar_turma_duas_ofertas_post_bloqueado_nao_toca_agenda():
    app, ids = _seed(ofertas=2, duplo_prof=True)
    client = _loga(app, ids["coord"], ids["unidade"])
    form = _form_turma_base(
        ids,
        **{
            "turma": "T H4 renomeada",
            "data_inicio": DATA_INI.isoformat(), "data_fim": DATA_FIM.isoformat(),
            "limpar_lancamentos": "0",
            "dias_semana": ["3"], "hora_inicio": "19:00", "hora_fim": "20:00",
        },
    )
    r = client.post(f"/turma/editar/{ids['turma']}", data=form)
    assert r.status_code == 302
    # Critério "2+ ofertas" permanece no backend: agenda intocada.
    assert _grade_rows(app, ids["ofertas"][0]) == [
        (0, time(8), time(11)), (2, time(8), time(11)),
    ]


# --- erros com re-render preenchido -------------------------------------------
def _responda_erro_agenda_turma(client, ids, sobre):
    form = _form_turma_base(
        ids,
        **{
            "data_inicio": DATA_INI.isoformat(), "data_fim": DATA_FIM.isoformat(),
            "limpar_lancamentos": "0",
        },
        **sobre,
    )
    return client.post(f"/turma/editar/{ids['turma']}", data=form)


def test_erro_fim_antes_do_inicio_devolve_formulario_preenchido():
    app, ids = _seed(ofertas=1)
    client = _loga(app, ids["coord"], ids["unidade"])
    r = _responda_erro_agenda_turma(client, ids, {
        "horario_por_dia": "1",
        "dias_semana": ["0", "2"],
        "hora_inicio_0": "08:00", "hora_fim_0": "11:00",
        "hora_inicio_2": "14:00", "hora_fim_2": "13:00",
    })
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "O horário da Quarta deve terminar depois de começar." in html
    # Modo personalizado continua aberto e o que foi digitado permanece.
    assert re.search(r'name="horario_por_dia"[^>]*checked', html)
    assert re.search(r'name="hora_inicio_2"[^>]*value="14:00"', html)
    # Nada foi gravado.
    assert _grade_rows(app, ids["ofertas"][0]) == [
        (0, time(8), time(11)), (2, time(8), time(11)),
    ]


def test_erro_dia_marcado_sem_hora_na_oferta_nova():
    app, ids = _seed(ofertas=1)
    client = _loga(app, ids["coord"], ids["unidade"])
    r = client.post(
        f"/turma/{ids['turma']}/ofertas/nova",
        data=_form_oferta(ids, **{
            "horario_por_dia": "1",
            "dias_semana": ["2"],
            "hora_inicio_2": "", "hora_fim_2": "",
        }),
    )
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Informe o horário de início e de fim da Quarta." in html
    assert re.search(r'data-weekday="2"[^>]*checked', html)
    with app.app_context():
        assert TurmaCurso.query.filter_by(turma_id=ids["turma"]).count() == 1


def test_erro_domingo_rejeitado():
    app, ids = _seed(ofertas=1)
    client = _loga(app, ids["coord"], ids["unidade"])
    r = client.post(
        f"/turma/{ids['turma']}/ofertas/nova",
        data=_form_oferta(ids, dias_semana=["6"], hora_inicio="08:00", hora_fim="11:00"),
    )
    assert r.status_code == 200
    assert "Domingo não é dia de aula" in r.get_data(as_text=True)
    with app.app_context():
        assert TurmaCurso.query.filter_by(turma_id=ids["turma"]).count() == 1

    # Em nova_turma a tela não tem agenda: flash + redirect, sem turma criada.
    client2 = _loga(app, ids["coord"], ids["unidade"])
    r2 = client2.post(
        "/turma/nova", data=_form_turma_base(ids, dias_semana=["6"],
                                             hora_inicio="08:00", hora_fim="11:00"),
    )
    assert r2.status_code == 302
    with app.app_context():
        assert Turma.query.count() == 1


def test_hora_em_dia_nao_marcado_e_ignorada():
    app, ids = _seed(ofertas=1)
    client = _loga(app, ids["coord"], ids["unidade"])
    r = client.post(
        f"/turma/{ids['turma']}/ofertas/nova",
        data=_form_oferta(ids, **{
            "horario_por_dia": "1",
            "dias_semana": ["0"],
            "hora_inicio": "08:00", "hora_fim": "11:00",
            "hora_inicio_0": "08:00", "hora_fim_0": "11:00",
            # dia 2 NÃO marcado — par válido deve ser ignorado:
            "hora_inicio_2": "14:00", "hora_fim_2": "17:00",
        }),
    )
    assert r.status_code == 302
    with app.app_context():
        nova = (
            TurmaCurso.query.filter_by(turma_id=ids["turma"])
            .order_by(TurmaCurso.id.desc()).first()
        )
        nova_id = nova.id
    assert _grade_rows(app, nova_id) == [(0, time(8), time(11))]


# --- idempotência --------------------------------------------------------------
def test_reenvio_do_mesmo_formulario_nao_altera_nada():
    app, ids = _seed(ofertas=1)
    client = _loga(app, ids["coord"], ids["unidade"])
    form = _form_oferta(
        ids, curso="cA", prof="p1", turno="Manhã", **GRADE_POR_DIA
    )
    r1 = client.post(f"/turma/oferta/{ids['ofertas'][0]}/editar", data=form)
    assert r1.status_code == 302
    depois_primeiro = _grade_rows(app, ids["ofertas"][0])
    r2 = client.post(f"/turma/oferta/{ids['ofertas'][0]}/editar", data=form)
    assert r2.status_code == 302
    assert _grade_rows(app, ids["ofertas"][0]) == depois_primeiro
