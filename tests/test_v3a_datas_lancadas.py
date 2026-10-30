# ruff: noqa: F811
"""V3a — datas já lançadas no seletor "Data da Aula" + botão Imprimir coerente.

Cobre o helper `situacao_datas_oferta` (app/utils/frequencia.py), o GET
/frequencia e o template (marcas ✔/○, resumo X/Y/Z, "Ir para a próxima
pendente") e a Parte B (botão Imprimir só quando a impressão é permitida).

Definição de "lançada" (a mesma das pendências do dashboard): **todos** os
alunos da pauta da oferta têm conceito registrado na data.
"""

import re
from datetime import time, timedelta

from sqlalchemy import event

from _helpers import login_as, nova_inscricao, nova_oferta

from app import db
from app.models import (
    Aluno,
    Curso,
    Frequencia,
    PeriodoLetivo,
    Turma,
    TurmaCurso,
    Unidade,
    User,
)
from app.models.enums import ConceitoFrequencia
from app.services.frequencia_oferta import ofertas_unicas_ativas
from app.services.turma_curso import (
    _alunos_da_oferta,
    datas_aula_oferta,
    datas_esperadas_oferta,
)
from app.utils.dias_semana import weekday_para_abrev
from app.utils.frequencia import (
    datas_bloqueadas_str,
    frequencias_lancadas,
    situacao_datas_oferta,
)
from app.utils.timezone import get_local_now
from config import Config

HOJE = get_local_now().date()
DIAS_GRADE_1 = "Segunda, Quarta"
DIAS_GRADE_2 = "Terça, Quinta"


class SQLiteTestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    WTF_CSRF_ENABLED = False


def _usuario(nome, email, role, unidade_id):
    user = User(name=nome, email=email, role=role, first_login=False,
                unidade_id=unidade_id)
    user.set_password("SenhaLocal!123")
    return user


def _seed(app, *, ofertas=2, dias_periodo=40):
    """Turma de `prof` (professor da TURMA); O1 é dele, O2 é de `prof2`."""
    with app.app_context():
        un = Unidade(nome="Unidade V3a", ativo=True)
        db.session.add(un)
        db.session.flush()

        prof = _usuario("Prof V3a", "prof.v3a@x.com", "professor", un.id)
        prof2 = _usuario("Prof V3a 2", "prof2.v3a@x.com", "professor", un.id)
        admin = _usuario("Admin V3a", "admin.v3a@x.com", "admin", un.id)
        secretaria = _usuario("Sec V3a", "sec.v3a@x.com", "secretaria", un.id)
        pedagogico = _usuario("Ped V3a", "ped.v3a@x.com", "pedagogico", un.id)
        db.session.add_all([prof, prof2, admin, secretaria, pedagogico])
        db.session.flush()

        periodo = PeriodoLetivo(
            nome="P V3a", data_inicio=HOJE - timedelta(days=dias_periodo),
            data_fim=HOJE + timedelta(days=dias_periodo), unidade_id=un.id,
            ativo=True,
        )
        db.session.add(periodo)
        db.session.flush()

        turma = Turma(
            nome="Turma V3a", unidade_id=un.id, periodo_letivo_id=periodo.id,
            professor_id=prof.id, ativo=True,
            data_inicio=periodo.data_inicio, data_fim=periodo.data_fim,
        )
        db.session.add(turma)
        db.session.flush()

        cursos = [
            Curso(nome=f"Curso V3a {i}", unidade_id=un.id, ativo=True)
            for i in range(2)
        ]
        db.session.add_all(cursos)
        db.session.flush()

        o1 = nova_oferta(turma.id, cursos[0].id, un.id, principal=True,
                         professor_id=prof.id, dias_semana=DIAS_GRADE_1,
                         hora_inicio=time(8), hora_fim=time(10))
        o2 = None
        if ofertas >= 2:
            o2 = nova_oferta(turma.id, cursos[1].id, un.id, principal=False,
                             professor_id=prof2.id, dias_semana=DIAS_GRADE_2,
                             hora_inicio=time(8), hora_fim=time(10))

        alunos = [
            Aluno(nome=nome, unidade_id=un.id, ativo=True)
            for nome in ("Aluno Um", "Aluno Dois")
        ]
        db.session.add_all(alunos)
        db.session.flush()
        for aluno in alunos:
            nova_inscricao(aluno.id, turma.id, o1.id)
            if o2 is not None:
                nova_inscricao(aluno.id, turma.id, o2.id)

        db.session.commit()
        return {
            "un": un.id,
            "prof": prof.id,
            "prof2": prof2.id,
            "admin": admin.id,
            "secretaria": secretaria.id,
            "pedagogico": pedagogico.id,
            "turma": turma.id,
            "o1": o1.id,
            "o2": o2.id if o2 is not None else None,
            "alunos": [a.id for a in alunos],
        }


def _oferta(app, oferta_id):
    with app.app_context():
        return db.session.get(TurmaCurso, oferta_id)


def _turma(app, turma_id):
    with app.app_context():
        return db.session.get(Turma, turma_id)


def _datas_ate_hoje(app, ids, oferta_id):
    with app.app_context():
        oferta = db.session.get(TurmaCurso, oferta_id)
        turma = db.session.get(Turma, ids["turma"])
        blocked = datas_bloqueadas_str(turma.periodo_letivo_id)
        return [
            d for d in datas_aula_oferta(oferta, blocked=blocked) if d <= HOJE
        ]


def _lancar_direto(app, ids, oferta_id, data_alvo, *, alunos=None, legado=False):
    """Grava conceito para todos os alunos da pauta na data (ORM, sem rota)."""
    with app.app_context():
        for aluno_id in (alunos or ids["alunos"]):
            db.session.add(Frequencia(
                aluno_id=aluno_id,
                turma_id=ids["turma"],
                turma_curso_id=None if legado else oferta_id,
                data=data_alvo,
                conceito=ConceitoFrequencia.A,
                unidade_id=ids["un"],
            ))
        db.session.commit()


def _situacao(app, ids, oferta_id):
    with app.app_context():
        turma = db.session.get(Turma, ids["turma"])
        oferta = db.session.get(TurmaCurso, oferta_id)
        return situacao_datas_oferta(turma, oferta)


def _iso(data_alvo):
    return data_alvo.strftime("%Y-%m-%d")


def _br(data_alvo):
    return data_alvo.strftime("%d/%m/%Y")


def _abrev(data_alvo):
    return weekday_para_abrev(data_alvo.weekday())


def _get(client, ids, **params):
    query = f"?turma_id={ids['turma']}"
    for chave, valor in params.items():
        if valor is not None:
            query += f"&{chave}={valor}"
    resposta = client.get(f"/frequencia{query}")
    return resposta.status_code, re.sub(r"\s+", " ", resposta.get_data(as_text=True))


# ---------------------------------------------------------------------------
# Helper / serviço
# ---------------------------------------------------------------------------

def test_marcas_lancada_pendente_e_resumo(app):
    ids = _seed(app)
    datas = _datas_ate_hoje(app, ids, ids["o1"])
    assert len(datas) >= 4

    lancada = datas[0]
    _lancar_direto(app, ids, ids["o1"], lancada)

    situacao = _situacao(app, ids, ids["o1"])

    assert situacao["status"][_iso(lancada)] == "lancada"
    assert situacao["status"][_iso(datas[1])] == "pendente"
    assert situacao["lancadas"] == 1
    assert situacao["total_ate_hoje"] == len(datas)
    assert situacao["pendentes"] == len(datas) - 1
    assert situacao["proxima_pendente"] == _iso(datas[1])


def test_pendente_quando_falta_um_aluno(app):
    ids = _seed(app)
    data_alvo = _datas_ate_hoje(app, ids, ids["o1"])[0]
    # Só um dos dois alunos tem conceito: a aula continua pendente.
    _lancar_direto(app, ids, ids["o1"], data_alvo, alunos=[ids["alunos"][0]])

    situacao = _situacao(app, ids, ids["o1"])

    assert situacao["status"][_iso(data_alvo)] == "pendente"
    assert situacao["lancadas"] == 0


def test_z_zero_quando_tudo_lancado(app, client):
    ids = _seed(app, ofertas=1, dias_periodo=3)
    datas = _datas_ate_hoje(app, ids, ids["o1"])
    assert datas, "a semente precisa de ao menos uma aula até hoje"
    for data_alvo in datas:
        _lancar_direto(app, ids, ids["o1"], data_alvo)

    situacao = _situacao(app, ids, ids["o1"])
    assert situacao["pendentes"] == 0
    assert situacao["proxima_pendente"] is None

    login_as(client, ids["prof"], ids["un"])
    status, html = _get(client, ids, turma_curso=ids["o1"])
    assert status == 200
    assert "Todas as aulas até hoje estão lançadas ✔" in html
    assert "Ir para a próxima pendente" not in html


def test_ofertas_independentes(app):
    ids = _seed(app)
    datas_o1 = _datas_ate_hoje(app, ids, ids["o1"])
    _lancar_direto(app, ids, ids["o1"], datas_o1[0])

    s1 = _situacao(app, ids, ids["o1"])
    s2 = _situacao(app, ids, ids["o2"])

    assert s1["status"][_iso(datas_o1[0])] == "lancada"
    assert s1["lancadas"] == 1
    # A oferta 2 não herda nada da oferta 1 (nem a data, nem a contagem).
    assert s2["lancadas"] == 0
    assert _iso(datas_o1[0]) not in s2["status"]


def test_legado_d2_conta_na_oferta_unica(app):
    ids = _seed(app, ofertas=1)
    data_alvo = _datas_ate_hoje(app, ids, ids["o1"])[0]
    _lancar_direto(app, ids, ids["o1"], data_alvo, legado=True)

    with app.app_context():
        assert ids["o1"] in ofertas_unicas_ativas([ids["o1"]])

    situacao = _situacao(app, ids, ids["o1"])
    assert situacao["status"][_iso(data_alvo)] == "lancada"


def test_legado_d2_nao_conta_com_duas_ofertas(app):
    ids = _seed(app)
    data_alvo = _datas_ate_hoje(app, ids, ids["o1"])[0]
    _lancar_direto(app, ids, ids["o1"], data_alvo, legado=True)

    with app.app_context():
        assert ids["o1"] not in ofertas_unicas_ativas([ids["o1"]])

    situacao = _situacao(app, ids, ids["o1"])
    assert situacao["status"][_iso(data_alvo)] == "pendente"


def test_contagem_consistente_com_pendencias_do_dashboard(app):
    """Z == pendências do helper do dashboard para a MESMA oferta."""
    ids = _seed(app)
    datas = _datas_ate_hoje(app, ids, ids["o1"])
    for data_alvo in datas[:2]:
        _lancar_direto(app, ids, ids["o1"], data_alvo)

    with app.app_context():
        turma = db.session.get(Turma, ids["turma"])
        oferta = db.session.get(TurmaCurso, ids["o1"])
        blocked = datas_bloqueadas_str(turma.periodo_letivo_id)
        aluno_ids = [a.id for a in _alunos_da_oferta(turma.id, oferta.id)]
        pendencias_dashboard = sum(
            1
            for data_alvo in datas_esperadas_oferta(oferta, HOJE, blocked)
            if frequencias_lancadas(
                turma.id, data_alvo, aluno_ids, turma_curso_id=oferta.id,
            ) < len(aluno_ids)
        )

    assert _situacao(app, ids, ids["o1"])["pendentes"] == pendencias_dashboard


def test_selects_constantes_com_2_e_10_datas(app):
    ids = _seed(app, ofertas=1, dias_periodo=3)

    def _conta():
        consultas = []

        def _registra(_conn, _cursor, statement, _params, _context, _many):
            consultas.append(statement)

        event.listen(db.engine, "before_cursor_execute", _registra)
        try:
            with app.app_context():
                turma = db.session.get(Turma, ids["turma"])
                oferta = db.session.get(TurmaCurso, ids["o1"])
                situacao_datas_oferta(turma, oferta)
        finally:
            event.remove(db.engine, "before_cursor_execute", _registra)
        return len(consultas)

    with app.app_context():
        turma = db.session.get(Turma, ids["turma"])
        oferta = db.session.get(TurmaCurso, ids["o1"])
        situacao_datas_oferta(turma, oferta)  # aquece caches
        assert len(datas_aula_oferta(oferta)) <= 3

        com_2 = _conta()

        # Dobra o período da oferta: passa de 10 datas sem mudar as consultas.
        oferta.data_inicio = HOJE - timedelta(days=120)
        db.session.commit()
        assert len(datas_aula_oferta(db.session.get(TurmaCurso, ids["o1"]))) > 10
        com_10 = _conta()

    assert com_2 == com_10


# ---------------------------------------------------------------------------
# HTML — marcas, resumo e botão
# ---------------------------------------------------------------------------

def test_html_mostra_marks_resumo_e_botao(app, client):
    ids = _seed(app)
    datas = _datas_ate_hoje(app, ids, ids["o1"])
    _lancar_direto(app, ids, ids["o1"], datas[0])

    login_as(client, ids["prof"], ids["un"])
    status, html = _get(client, ids, turma_curso=ids["o1"])

    assert status == 200
    assert f"✔ {_br(datas[0])} ({_abrev(datas[0])})" in html
    assert f"○ {_br(datas[1])} ({_abrev(datas[1])}) — pendente" in html
    assert (
        f"1 de {len(datas)} aulas até hoje lançadas · {len(datas) - 1} pendente(s)"
        in html
    )
    assert "Ir para a próxima pendente" in html
    assert f"data={_iso(datas[1])}" in html


def test_html_sem_oferta_escolhida_nao_mostra_marcas(app, client):
    ids = _seed(app)
    login_as(client, ids["prof"], ids["un"])

    status, html = _get(client, ids)

    assert status == 200
    assert "Selecione o curso" in html
    assert "— pendente" not in html
    assert "✔" not in html
    assert "aulas até hoje lançadas" not in html


def test_html_apos_salvar_a_data_aparece_lancada(app, client):
    ids = _seed(app)
    data_alvo = _datas_ate_hoje(app, ids, ids["o1"])[0]
    login_as(client, ids["prof"], ids["un"])

    dados = {
        "turma": str(ids["turma"]),
        "turma_curso": str(ids["o1"]),
        "data": _iso(data_alvo),
    }
    for aluno_id in ids["alunos"]:
        dados[f"aluno_{aluno_id}"] = "A"
    resposta = client.post("/frequencia", data=dados, follow_redirects=False)
    assert resposta.status_code == 302

    status, html = _get(client, ids, turma_curso=ids["o1"], data=_iso(data_alvo))
    assert status == 200
    assert f"✔ {_br(data_alvo)} ({_abrev(data_alvo)})" in html


def test_html_demais_campos_preservados(app, client):
    ids = _seed(app)
    login_as(client, ids["prof"], ids["un"])

    status, html = _get(client, ids, turma_curso=ids["o1"])

    assert status == 200
    assert "Data da Aula" in html
    assert "Atividades da aula" in html
    assert "Observações da Aula" in html
    assert "Valor / Postura do Esportista" in html
    assert "Aluno Um" in html
