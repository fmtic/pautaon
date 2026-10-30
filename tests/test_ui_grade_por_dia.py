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

from _helpers import login_as

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
    SECRET_KEY = "chave-de-teste-s1-sem-valor-real-1234567890"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    WTF_CSRF_ENABLED = False


def _loga(app, user_id, unidade_id):
    client = app.test_client()
    login_as(client, str(user_id), unidade_id)
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


# --- H4c: servidor ignora campos corretos em cada modo ------------------------
def test_modo_personalizado_ignora_par_padrao_mesmo_preenchido():
    """H4c PASSO 5: em modo personalizado, o par padrão é ignorado mesmo se vier preenchido."""
    app, ids = _seed(ofertas=1)
    client = _loga(app, ids["coord"], ids["unidade"])
    # Envia par padrão divergente MAS os pares por dia são os que devem ser usados
    form = _form_oferta(ids, curso="cA", prof="p1", turno="Manhã", **{
        "horario_por_dia": "1",
        "dias_semana": ["0", "2"],
        "hora_inicio": "99:99",  # inválido, deve ser ignorado
        "hora_fim": "99:99",     # inválido, deve ser ignorado
        "hora_inicio_0": "08:00",
        "hora_fim_0": "11:00",
        "hora_inicio_2": "14:00",
        "hora_fim_2": "17:00",
    })
    r = client.post(f"/turma/oferta/{ids['ofertas'][0]}/editar", data=form)
    assert r.status_code == 302
    # Grade segue só os pares por dia, ignorando o par padrão
    assert _grade_rows(app, ids["ofertas"][0]) == [
        (0, time(8), time(11)), (2, time(14), time(17)),
    ]


def test_modo_padrao_ignora_campos_por_dia_mesmo_preenchidos():
    """H4c PASSO 5: em modo padrão, os campos por dia são ignorados mesmo se vierem preenchidos."""
    app, ids = _seed(ofertas=1)
    client = _loga(app, ids["coord"], ids["unidade"])
    # Envia campos por dia divergentes MAS o par padrão é o que deve ser usado
    form = _form_oferta(ids, curso="cA", prof="p1", turno="Manhã", **{
        "dias_semana": ["0", "2"],
        "hora_inicio": "08:00",
        "hora_fim": "11:00",
        "hora_inicio_0": "99:99",  # inválido, deve ser ignorado
        "hora_fim_0": "99:99",     # inválido, deve ser ignorado
        "hora_inicio_2": "99:99",  # inválido, deve ser ignorado
        "hora_fim_2": "99:99",     # inválido, deve ser ignorado
    })
    r = client.post(f"/turma/oferta/{ids['ofertas'][0]}/editar", data=form)
    assert r.status_code == 302
    # Grade segue o par padrão replicado, ignorando os campos por dia
    assert _grade_rows(app, ids["ofertas"][0]) == [
        (0, time(8), time(11)), (2, time(8), time(11)),
    ]


def test_modo_personalizado_com_1_dia_gera_grade_correta():
    """H4c PASSO 5: POST horario_por_dia=1 com 1 dia gera a grade correspondente, sem erro."""
    app, ids = _seed(ofertas=1)
    client = _loga(app, ids["coord"], ids["unidade"])
    # H4c: servidor aceita horario_por_dia=1 com 1 dia (pode ser forjado)
    form = _form_oferta(ids, curso="cA", prof="p1", turno="Manhã", **{
        "horario_por_dia": "1",
        "dias_semana": ["0"],
        "hora_inicio": "08:00",
        "hora_fim": "11:00",
        "hora_inicio_0": "09:00",
        "hora_fim_0": "10:00",
    })
    r = client.post(f"/turma/oferta/{ids['ofertas'][0]}/editar", data=form)
    assert r.status_code == 302
    # Grade segue o par por dia (09:00-10:00), não o padrão (08:00-11:00)
    assert _grade_rows(app, ids["ofertas"][0]) == [(0, time(9), time(10))]


# --- H4d: render do servidor dos estados do componente -------------------------
# Lacuna registrada no relatório H4c ("Render do servidor: não testado"). Estado
# inicial é pré-renderizado pelo servidor (layout estável); aqui cada estado do
# contrato H4c é verificado no HTML por seletor/atributo (regex estável — o repo
# não usa BeautifulSoup), sem depender de texto decorativo.

def _input_tag(html, id_attr):
    """Tag <input> inteira pelo `id` (único por formulário na página)."""
    m = re.search(rf'<input[^>]*id="{id_attr}"[^>]*>', html, re.S)
    assert m, f"input id=\"{id_attr}\" não encontrado no HTML"
    return m.group(0)


def _tag_bloco(html, marker, antes_de):
    """Abertura da <div> do bloco identificado por `marker` mais próximo antes
de `antes_de` (âncora = id de um input dentro do bloco)."""
    p = html.rfind(marker, 0, antes_de)
    assert p != -1, f"bloco {marker} não encontrado antes de {antes_de}"
    return html[html.rfind("<div", 0, p):html.find(">", p) + 1]


def _desabilitado(tag):
    return re.search(r"\bdisabled\b", tag) is not None


def _marcado(tag):
    return re.search(r"\bchecked\b", tag) is not None


def _esmaecido(tag):
    return "opacity-50" in tag


def _ancora(html, id_attr):
    i = html.find(f'id="{id_attr}"')
    assert i != -1, f"id=\"{id_attr}\" não encontrado"
    return i


def test_render_uniforme_2_dias_modo_padrao_editar_turma():
    """H4d: grade uniforme 2+ dias em editar turma — padrão ativo, por dia
    desabilitado/esmaecido, interruptor habilitado e desligado."""
    app, ids = _seed(ofertas=1)
    client = _loga(app, ids["coord"], ids["unidade"])
    html = client.get(f"/turma/editar/{ids['turma']}").get_data(as_text=True)

    switch = _input_tag(html, "agenda_horario_por_dia")
    assert not _desabilitado(switch)
    assert not _marcado(switch)
    assert 'aria-describedby="agenda_switch_help"' in switch

    # Par padrão ativo (sem d-none em nenhum momento).
    ancora = _ancora(html, "agenda_hora_inicio")
    bloco_padrao = _tag_bloco(html, "data-grade-padrao", ancora)
    assert "d-none" not in bloco_padrao
    assert not _esmaecido(bloco_padrao)
    assert not _desabilitado(_input_tag(html, "agenda_hora_inicio"))
    assert not _desabilitado(_input_tag(html, "agenda_hora_fim"))

    # Dias marcados (Seg/Qua): linhas esmaecidas, campos desabilitados.
    for w in (0, 2):
        tag_ini = _input_tag(html, f"agenda_hora_inicio_{w}")
        assert _desabilitado(tag_ini)
        assert _esmaecido(_tag_bloco(html, f'data-grade-dia="{w}"', _ancora(html, f"agenda_hora_inicio_{w}")))
    # Dia desmarcado (Terça): campos desabilitados também.
    assert _desabilitado(_input_tag(html, "agenda_hora_inicio_1"))


def test_render_uniforme_2_dias_formulario_edicao_oferta():
    """H4d: mesmo estado na tela Cursos da Turma — formulário de edição da oferta."""
    app, ids = _seed(ofertas=1)
    client = _loga(app, ids["coord"], ids["unidade"])
    html = client.get(f"/turma/{ids['turma']}/ofertas").get_data(as_text=True)
    prefixo = f"ed{ids['ofertas'][0]}"

    switch = _input_tag(html, f"{prefixo}_horario_por_dia")
    assert not _desabilitado(switch) and not _marcado(switch)
    assert 'aria-describedby="' + f'{prefixo}_switch_help"' in switch
    assert not _desabilitado(_input_tag(html, f"{prefixo}_hora_inicio"))
    for w in (0, 2):
        assert _desabilitado(_input_tag(html, f"{prefixo}_hora_inicio_{w}"))


def test_render_0_dias_interruptor_desabilitado_com_texto_apoio():
    """H4d: nova oferta sem dia marcado — interruptor desabilitado e texto de
    apoio presente via aria-describedby (elemento id existe)."""
    app, ids = _seed(ofertas=1)
    client = _loga(app, ids["coord"], ids["unidade"])
    html = client.get(f"/turma/{ids['turma']}/ofertas").get_data(as_text=True)

    switch = _input_tag(html, "novo_horario_por_dia")
    assert _desabilitado(switch)
    assert not _marcado(switch)
    assert 'aria-describedby="novo_switch_help"' in switch
    assert 'id="novo_switch_help"' in html
    assert "Marque 2 ou mais dias" in html


def test_render_1_dia_interruptor_desabilitado_com_texto_apoio():
    """H4d: 1 dia marcado — interruptor desabilitado e texto de apoio."""
    app, ids = _seed(ofertas=1, grade=[(0, time(8), time(11))])
    client = _loga(app, ids["coord"], ids["unidade"])
    html = client.get(f"/turma/editar/{ids['turma']}").get_data(as_text=True)

    switch = _input_tag(html, "agenda_horario_por_dia")
    assert _desabilitado(switch)
    assert not _marcado(switch)
    assert 'aria-describedby="agenda_switch_help"' in switch
    assert 'id="agenda_switch_help"' in html


def test_render_nao_uniforme_abre_personalizado_par_padrao_visivel_esmaecido():
    """H4d: grade NÃO uniforme abre em modo personalizado — interruptor ligado e
    habilitado, par padrão VISÍVEL (sem d-none) mas esmaecido/desabilitado,
    campos por dia ativos nos dias marcados e desabilitados nos desmarcados."""
    app, ids = _seed(
        ofertas=1, grade=[(0, time(8), time(11)), (2, time(14), time(17))]
    )
    client = _loga(app, ids["coord"], ids["unidade"])
    html = client.get(f"/turma/editar/{ids['turma']}").get_data(as_text=True)

    switch = _input_tag(html, "agenda_horario_por_dia")
    assert _marcado(switch)
    assert not _desabilitado(switch)

    bloco_padrao = _tag_bloco(html, "data-grade-padrao", _ancora(html, "agenda_hora_inicio"))
    assert "d-none" not in bloco_padrao
    assert _esmaecido(bloco_padrao)
    assert _desabilitado(_input_tag(html, "agenda_hora_inicio"))
    assert _desabilitado(_input_tag(html, "agenda_hora_fim"))

    for w, valor in ((0, "08:00"), (2, "14:00")):
        tag_ini = _input_tag(html, f"agenda_hora_inicio_{w}")
        assert not _desabilitado(tag_ini)
        assert f'value="{valor}"' in tag_ini
        assert not _esmaecido(
            _tag_bloco(html, f'data-grade-dia="{w}"', _ancora(html, f"agenda_hora_inicio_{w}"))
        )
    # Dia desmarcado (Terça): campos desabilitados.
    assert _desabilitado(_input_tag(html, "agenda_hora_inicio_1"))
    assert _desabilitado(_input_tag(html, "agenda_hora_fim_1"))


def test_render_erro_personalizado_preserva_estado_e_valores():
    """H4d: re-render de erro em modo personalizado mantém o mesmo estado
    (interruptor ligado/habilitado, par padrão esmaecido/desabilitado) e os
    valores digitados."""
    app, ids = _seed(ofertas=1)
    client = _loga(app, ids["coord"], ids["unidade"])
    r = client.post(
        f"/turma/{ids['turma']}/ofertas/nova",
        data=_form_oferta(ids, **{
            "horario_por_dia": "1",
            "dias_semana": ["0", "2"],
            "hora_inicio": "08:00", "hora_fim": "11:00",
            "hora_inicio_0": "08:00", "hora_fim_0": "11:00",
            "hora_inicio_2": "14:00", "hora_fim_2": "13:00",  # fim < início → erro
        }),
    )
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'id="novo_agenda_erro"' in html

    switch = _input_tag(html, "novo_horario_por_dia")
    assert _marcado(switch)
    assert not _desabilitado(switch)

    bloco_padrao = _tag_bloco(html, "data-grade-padrao", _ancora(html, "novo_hora_inicio"))
    assert "d-none" not in bloco_padrao
    assert _esmaecido(bloco_padrao)
    assert _desabilitado(_input_tag(html, "novo_hora_inicio"))

    # Valores digitados preservados e campos por dia ativos nos dias marcados.
    tag_2 = _input_tag(html, "novo_hora_inicio_2")
    assert 'value="14:00"' in tag_2
    assert not _desabilitado(tag_2)
    assert 'value="08:00"' in _input_tag(html, "novo_hora_inicio_0")
    assert not _desabilitado(_input_tag(html, "novo_hora_fim_0"))
    # Dia desmarcado segue desabilitado no re-render.
    assert _desabilitado(_input_tag(html, "novo_hora_inicio_1"))
