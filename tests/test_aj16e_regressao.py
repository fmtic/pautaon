# ruff: noqa: F811
"""AJ16-E — regressão: "Ir para a próxima pendente" → Salvar.

Causa raiz: o POST de ``/frequencia`` validava ``data`` contra o calendário
da TURMA (``gerar_datas`` via ``carregar_contexto_turma``), enquanto o GET
do seletor e o ``situacao_datas.proxima_pendente`` usam o calendário da
OFERTA (``datas_aula_oferta``). Quando a vigência da oferta divergia da
vigência da turma — ou a turma não tinha vigência própria — a data pendente
oferecida pelo botão não pertencia ao calendário da turma e o salvamento
era recusado.

Estes testes seguem o fluxo real do navegador: extraem o link "Ir para a
próxima pendente" do HTML, abrem a data pendente e enviam o formulário
renderizado (com o campo ``data`` do ``<select>`` preenchido).
"""

import re
from datetime import time, timedelta

import pytest

from _helpers import (
    dia_de_aula_ate,
    hoje_ref,
    login_as,
    nova_inscricao,
    nova_oferta,
)

from app import db
from app.models import (
    Aluno,
    Curso,
    Frequencia,
    PeriodoLetivo,
    Turma,
    Unidade,
    User,
)
from app.services.turma_curso import datas_aula_oferta
from config import Config

pytestmark = pytest.mark.usefixtures("hoje_fixo")

HOJE = dia_de_aula_ate(hoje_ref())


class SQLiteTestConfig(Config):
    SECRET_KEY = "chave-de-teste-aj16e-regressao-1234567890abcdef"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    WTF_CSRF_ENABLED = False


def _usuario(nome, email, role, unidade_id):
    user = User(name=nome, email=email, role=role, first_login=False,
                unidade_id=unidade_id)
    user.set_password("SenhaLocal!123")
    return user


def _seed(app, *, turma_vigencia=True, oferta_vigencia=None):
    """Turma + 1 oferta (Seg/Qua) + 1 aluno + professor e admin.

    ``turma_vigencia=False`` deixa ``turma.data_inicio/data_fim`` nulos —
    ``gerar_datas`` devolve [] (calendário da turma vazio), enquanto a
    oferta com vigência própria continua com datas. ``oferta_vigencia``
    define (inicio, fim) próprios da oferta.
    """
    with app.app_context():
        un = Unidade(nome="Unidade AJ16E-R", ativo=True)
        db.session.add(un)
        db.session.flush()

        prof = _usuario("Prof R", "prof.r@x.com", "professor", un.id)
        admin = _usuario("Admin R", "admin.r@x.com", "admin", un.id)
        db.session.add_all([prof, admin])
        db.session.flush()

        ini = HOJE - timedelta(days=40)
        fim = HOJE + timedelta(days=40)
        periodo = PeriodoLetivo(
            nome="P R", data_inicio=ini, data_fim=fim, unidade_id=un.id,
            ativo=True,
        )
        db.session.add(periodo)
        db.session.flush()

        turma = Turma(
            nome="Turma R", unidade_id=un.id, periodo_letivo_id=periodo.id,
            professor_id=prof.id, ativo=True,
            data_inicio=ini if turma_vigencia else None,
            data_fim=fim if turma_vigencia else None,
        )
        db.session.add(turma)
        db.session.flush()

        curso = Curso(nome="Curso R", unidade_id=un.id, ativo=True)
        db.session.add(curso)
        db.session.flush()

        kwargs = {}
        if oferta_vigencia is not None:
            kwargs["data_inicio"], kwargs["data_fim"] = oferta_vigencia
        oferta = nova_oferta(
            turma.id, curso.id, un.id, principal=True,
            professor_id=prof.id, dias_semana="Segunda, Quarta",
            hora_inicio=time(8), hora_fim=time(10), **kwargs,
        )

        aluno = Aluno(nome="Aluno R", unidade_id=un.id, ativo=True)
        db.session.add(aluno)
        db.session.flush()
        nova_inscricao(aluno.id, turma.id, oferta.id)

        db.session.commit()
        return {
            "un": un.id, "prof": prof.id, "admin": admin.id,
            "turma": turma.id, "oferta": oferta.id, "aluno": aluno.id,
        }


def _datas_oferta_ate_hoje(app, turma_id, oferta_id):
    with app.app_context():
        from app.models import TurmaCurso
        from app.utils.frequencia import datas_bloqueadas_str
        turma = db.session.get(Turma, turma_id)
        oferta = db.session.get(TurmaCurso, oferta_id)
        blocked = datas_bloqueadas_str(turma.periodo_letivo_id)
        return [
            d for d in datas_aula_oferta(oferta, blocked=blocked)
            if d <= HOJE
        ]


def _clica_pendente_e_salva(client, ids):
    """Segue o fluxo do usuário: abre a turma, clica no link da próxima
    pendente e envia o formulário renderizado (campo ``data`` do select)."""
    login_as(client, ids["admin"], ids["un"])

    # 1) GET da página da turma/oferta — extrai o link "próxima pendente".
    r = client.get(
        f"/frequencia?turma_id={ids['turma']}&turma_curso={ids['oferta']}"
    )
    assert r.status_code == 200
    html = r.get_data(as_text=True)

    m = re.search(
        r'<a[^>]*href="([^"]*data=[^"]*)"[^>]*>.*?Ir para a pr[^<]*pendente',
        html, re.S,
    )
    assert m, "botão 'Ir para a próxima pendente' não renderizado"
    href = m.group(1).replace("&amp;", "&")

    # 2) GET do link da pendente — a página deve abrir NA data pendente.
    r2 = client.get(href)
    assert r2.status_code == 200
    html2 = r2.get_data(as_text=True)

    data_hidden = re.search(
        r'name="data_hidden" value="([^"]*)"', html2
    ).group(1)
    bloco = re.search(r'<select name="data".*?</select>', html2, re.S)
    selecionada = None
    for om in re.finditer(r'<option value="([^"]*)"([^>]*)>', bloco.group(0)):
        if 'selected' in om.group(2):
            selecionada = om.group(1)
    assert selecionada, "nenhuma data selecionada no <select name='data'>"

    # 3) POST do formulário como o navegador envia — com ``data`` preenchido.
    dados = {
        "turma": str(ids["turma"]),
        "turma_curso": str(ids["oferta"]),
        "data": selecionada,
        "data_hidden": data_hidden,
        f"aluno_{ids['aluno']}": "A",
    }
    resp = client.post("/frequencia", data=dados, follow_redirects=True)
    return resp, selecionada, data_hidden


def _freqs_na_data(app, turma_id, data_iso):
    from datetime import date as _date
    with app.app_context():
        return Frequencia.query.filter_by(
            turma_id=turma_id, data=_date.fromisoformat(data_iso)
        ).count()


def test_pendente_salva_com_turma_sem_vigencia(app, client):
    """Regressão principal: turma sem vigência própria + oferta com vigência.

    ``gerar_datas(turma)`` devolve [] — no código antigo o POST rejeitava a
    data pendente ("não pertence ao calendário"). Com a correção, a data
    pendente pertence ao calendário da oferta e o lançamento é gravado.
    """
    ini = HOJE - timedelta(days=120)
    fim = HOJE + timedelta(days=40)
    ids = _seed(
        app, turma_vigencia=False, oferta_vigencia=(ini, fim),
    )
    datas = _datas_oferta_ate_hoje(app, ids["turma"], ids["oferta"])
    assert datas, "semente precisa de datas de oferta até hoje"
    proxima = datas[0].strftime("%Y-%m-%d")

    resp, selecionada, _ = _clica_pendente_e_salva(client, ids)
    body = resp.get_data(as_text=True)

    assert selecionada == proxima
    assert "sucesso" in body.lower(), body[-2000:]
    assert _freqs_na_data(app, ids["turma"], proxima) == 1


def test_pendente_salva_com_oferta_vigencia_alem_da_turma(app, client):
    """Oferta vigente ALÉM da turma: a pendente cai fora de ``gerar_datas``."""
    # A turma já nasce com vigência "curta" (HOJE±40) no _seed; a oferta
    # começa 80 dias antes → datas de oferta < turma.data_inicio.
    ini_oferta = HOJE - timedelta(days=120)
    ids = _seed(
        app, turma_vigencia=True,
        oferta_vigencia=(ini_oferta, HOJE + timedelta(days=40)),
    )

    datas = _datas_oferta_ate_hoje(app, ids["turma"], ids["oferta"])
    assert datas, "semente precisa de datas de oferta até hoje"
    proxima = datas[0].strftime("%Y-%m-%d")
    # A pendente precisa estar fora do calendário da turma (antes do início).
    assert proxima < (HOJE - timedelta(days=40)).strftime("%Y-%m-%d")

    resp, selecionada, _ = _clica_pendente_e_salva(client, ids)
    body = resp.get_data(as_text=True)

    assert selecionada == proxima
    assert "sucesso" in body.lower(), body[-2000:]
    assert _freqs_na_data(app, ids["turma"], proxima) == 1


def test_pendente_salva_cenario_normal(app, client):
    """Controle: turma e oferta com a mesma vigência — já funcionava."""
    ids = _seed(app)
    datas = _datas_oferta_ate_hoje(app, ids["turma"], ids["oferta"])
    assert datas
    proxima = datas[0].strftime("%Y-%m-%d")

    resp, selecionada, _ = _clica_pendente_e_salva(client, ids)
    body = resp.get_data(as_text=True)

    assert selecionada == proxima
    assert "sucesso" in body.lower(), body[-2000:]
    assert _freqs_na_data(app, ids["turma"], proxima) == 1


def test_data_fora_do_calendario_da_oferta_e_recusada(app, client):
    """Coerência: uma data que NÃO é dia de aula da oferta continua recusada
    com mensagem específica (não grava)."""
    ids = _seed(app)
    login_as(client, ids["admin"], ids["un"])

    # Data que não é segunda nem quarta dentro da vigência da oferta.
    with app.app_context():
        from app.models import TurmaCurso
        oferta = db.session.get(TurmaCurso, ids["oferta"])
        ini = oferta.data_inicio or HOJE - timedelta(days=40)
        # procura um dia que não seja seg/qua
        candidata = ini
        while candidata.weekday() in (0, 2):
            candidata += timedelta(days=1)
        ruim = candidata.strftime("%Y-%m-%d")

    resp = client.post("/frequencia", data={
        "turma": str(ids["turma"]),
        "turma_curso": str(ids["oferta"]),
        "data": ruim,
        "data_hidden": ruim,
        f"aluno_{ids['aluno']}": "A",
    }, follow_redirects=True)
    body = resp.get_data(as_text=True)
    assert _freqs_na_data(app, ids["turma"], ruim) == 0
    # Recusa coerente: ou a mensagem de calendário ou a do resolver de oferta.
    assert (
        "não pertence ao calendário" in body
        or "não cai em um dia de aula" in body
        or "vigência" in body
    ), body[-2000:]
