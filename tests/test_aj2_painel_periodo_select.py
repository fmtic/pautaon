"""AJ2 bloco B — select de período do painel pedagógico usa `nome_exibicao`.

Cobre o commit 9794165 (`feat(painel): nome_exibicao no select de periodos`),
que mudou duas coisas na rota `/relatorios/painel`:

    - o `<option>` do filtro passou a exibir `p.nome_exibicao`
      (`"<unidade> <nome>"`, ou só `"<nome>"` quando o período não tem
      unidade) em vez de `p.nome`;
    - a consulta de períodos passou a carregar `unidade` com `joinedload`,
      para a propriedade não virar N+1 na renderização.

Regras verificadas:

    T1 dois períodos homônimos em unidades diferentes aparecem distintos no
       select (com o prefixo da unidade), e continuam sendo duas opções.
    T2 o `value` continua sendo o id; o período pedido por
       `?periodo_letivo_id=` volta com `selected` (e um único `selected`).
    T3 período sem unidade mostra só o nome, sem espaço/prefixo sobrando.
    T4 nome de unidade com HTML sai escapado no texto da opção.
    T5 o número de SELECTs do request é o mesmo com 3 e com 12 períodos
       (medido com listener `before_cursor_execute`): nada de N+1.
    T6 escopo de unidade e permissões do painel inalterados: o pedagógico de A
       só vê períodos de A; os perfis de `ROLES_RELATORIOS` entram e o
       professor continua em 403.

Semente em SQLite (fixtures `app`/`client` do conftest); T5 monta apps novos
para nascer o banco já no estado final — o mesmo padrão de
`tests/test_impressao_grade_oferta.py`.
"""

import html
import re
from datetime import date, timedelta

from _helpers import login_as

from app import create_app, db
from app.models import PeriodoLetivo, Turma, Unidade, User
from config import Config
from sqlalchemy import event

# Config local para o app novo da medição de SELECTs (T5).
class SQLiteTestConfig(Config):
    SECRET_KEY = "chave-de-teste-s1-sem-valor-real-1234567890"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    WTF_CSRF_ENABLED = False


UN_A = "Alfa AJ3E4"
UN_B = "Beta AJ3E4"
#: Nome de unidade com HTML: precisa sair escapado do <option> (T4).
UN_C = "Gamma <b>negrito</b> AJ3E4"

NOME_GEMEO = "Periodo Geminio"
NOME_A_EXTRA = "Periodo Alfa Extra"
NOME_C = "Periodo Gamma"
NOME_SEM_UNIDADE = "Periodo Sem Unidade"

HOJE = date.today()
DATA_INI = HOJE - timedelta(days=30)
DATA_FIM = HOJE + timedelta(days=30)

URL_PAINEL = "/relatorios/painel"

_SELECT_PERIODO = re.compile(r'<select id="filtroPeriodo"[\s\S]*?</select>')
_OPTAO = re.compile(r'<option value="(\d+)"([^>]*)>([\s\S]*?)</option>')


# ---------------------------------------------------------------------------
# Leitura do select de período no HTML renderizado
# ---------------------------------------------------------------------------

def _opcoes_periodo(corpo):
    """`[(value, atributos, texto_bruto)]` das opções do filtro de período."""
    bloco = _SELECT_PERIODO.search(corpo)
    assert bloco, "o painel não renderizou o select #filtroPeriodo"
    return _OPTAO.findall(bloco.group(0))


def _rotulos(corpo):
    return [texto for _v, _a, texto in _opcoes_periodo(corpo)]


def _selecionados(corpo):
    return [(v, texto) for v, attrs, texto in _opcoes_periodo(corpo)
            if "selected" in attrs]


def _corpo(resposta):
    return resposta.get_data(as_text=True)


def _usuario(nome, email, role, unidade_id):
    user = User(
        name=nome, email=email, role=role, first_login=False,
        unidade_id=unidade_id,
    )
    user.set_password("SenhaLocal!123")
    db.session.add(user)
    db.session.flush()
    return user


def _periodo(nome, unidade_id, data_inicio=DATA_INI):
    periodo = PeriodoLetivo(
        nome=nome, data_inicio=data_inicio, data_fim=DATA_FIM,
        unidade_id=unidade_id, ativo=True,
    )
    db.session.add(periodo)
    db.session.flush()
    return periodo


# ---------------------------------------------------------------------------
# Semente principal (T1–T4 e T6)
# ---------------------------------------------------------------------------

def _setup(app):
    """Três unidades + cinco períodos, dois deles homônimos em A e B."""
    with app.app_context():
        un_a = Unidade(nome=UN_A, ativo=True)
        un_b = Unidade(nome=UN_B, ativo=True)
        un_c = Unidade(nome=UN_C, ativo=True)
        db.session.add_all([un_a, un_b, un_c])
        db.session.flush()

        ped_a = _usuario("Ped Alfa", "ped.aj3e4a@x.invalid", "pedagogico", un_a.id)
        sec_a = _usuario("Sec Alfa", "sec.aj3e4a@x.invalid", "secretaria", un_a.id)
        ss_a = _usuario("SS Alfa", "ss.aj3e4a@x.invalid", "servico_social", un_a.id)
        prof_a = _usuario("Prof Alfa", "prof.aj3e4a@x.invalid", "professor", un_a.id)
        adm = _usuario("Adm Global", "adm.aj3e4g@x.invalid", "admin", None)
        db.session.flush()

        per_a = _periodo(NOME_GEMEO, un_a.id)
        per_a2 = _periodo(NOME_A_EXTRA, un_a.id, data_inicio=DATA_INI - timedelta(days=10))
        per_b = _periodo(NOME_GEMEO, un_b.id)
        per_c = _periodo(NOME_C, un_c.id)
        per_nil = _periodo(NOME_SEM_UNIDADE, None)

        # Uma turma em A para o painel ter o que montar (e nada vazar de B).
        db.session.add(Turma(
            nome="Turma Alfa", turno="Manhã", data_inicio=DATA_INI,
            data_fim=DATA_FIM, periodo_letivo_id=per_a.id,
            unidade_id=un_a.id, ativo=True, professor_id=prof_a.id,
        ))
        db.session.commit()

        return {
            "un_a": un_a.id, "un_b": un_b.id, "un_c": un_c.id,
            "ped_a": ped_a.id, "sec_a": sec_a.id, "ss_a": ss_a.id,
            "prof_a": prof_a.id, "adm": adm.id,
            "per_a": per_a.id, "per_a2": per_a2.id, "per_b": per_b.id,
            "per_c": per_c.id, "per_nil": per_nil.id,
        }


def _pagina_global(client, ids, periodo=None):
    login_as(client, ids["adm"])
    url = URL_PAINEL
    if periodo is not None:
        url = f"{url}?periodo_letivo_id={periodo}"
    return _corpo(client.get(url))


# ---------------------------------------------------------------------------
# T1 — homônimos de unidades diferentes aparecem distintos
# ---------------------------------------------------------------------------

def test_t1_periodos_homonomos_de_unidades_diferentes_aparecem_distintos(client, app):
    ids = _setup(app)
    # Visão global (admin sem unidade na sessão): os dois períodos estão no select.
    corpo = _pagina_global(client, ids)
    rotulos = _rotulos(corpo)

    assert len(rotulos) == 5, rotulos
    opcoes = _opcoes_periodo(corpo)
    valores = [v for v, _a, _t in opcoes]
    assert valores.count(str(ids["per_a"])) == 1
    assert valores.count(str(ids["per_b"])) == 1

    # Os dois homônimos continuam sendo opções diferentes, cada uma com o
    # prefixo da sua unidade — é exatamente o que o nome_exibicao resolve.
    por_valor = {v: t for v, _a, t in opcoes}
    assert por_valor[str(ids["per_a"])] == f"{UN_A} {NOME_GEMEO}"
    assert por_valor[str(ids["per_b"])] == f"{UN_B} {NOME_GEMEO}"
    assert NOME_GEMEO in por_valor[str(ids["per_a"])]

    # O rótulo nunca é o nome solto quando há unidade (regressão do bug).
    for valor, periodo_id in ((str(ids["per_a"]), "per_a"), (str(ids["per_b"]), "per_b")):
        assert por_valor[valor] != NOME_GEMEO, (
            f"o período {periodo_id} voltou a ser exibido sem a unidade"
        )


# ---------------------------------------------------------------------------
# T2 — value continua o id e o período pedido vem selected
# ---------------------------------------------------------------------------

def test_t2_value_e_o_id_e_o_periodo_pedido_vem_selected(client, app):
    ids = _setup(app)
    corpo = _pagina_global(client, ids, periodo=ids["per_b"])
    opcoes = _opcoes_periodo(corpo)

    # value == id (nenhuma mudança de contrato do formulário).
    assert str(ids["per_b"]) in [v for v, _a, _t in opcoes]
    assert str(ids["per_nil"]) in [v for v, _a, _t in opcoes]

    # Um único selected, e é o período pedido — com o rótulo da unidade.
    selecionadas = _selecionados(corpo)
    assert len(selecionadas) == 1, selecionadas
    valor, texto = selecionadas[0]
    assert valor == str(ids["per_b"])
    assert texto == f"{UN_B} {NOME_GEMEO}"

    corpo_outro = _pagina_global(client, ids, periodo=ids["per_a"])
    valor_outro, texto_outro = _selecionados(corpo_outro)[0]
    assert valor_outro == str(ids["per_a"])
    assert texto_outro == f"{UN_A} {NOME_GEMEO}"


# ---------------------------------------------------------------------------
# T3 — período sem unidade mostra só o nome
# ---------------------------------------------------------------------------

def test_t3_periodo_sem_unidade_mostra_so_o_nome(client, app):
    ids = _setup(app)
    corpo = _pagina_global(client, ids)
    por_valor = {v: t for v, _a, t in _opcoes_periodo(corpo)}

    assert por_valor[str(ids["per_nil"])] == NOME_SEM_UNIDADE
    assert not por_valor[str(ids["per_nil"])].startswith(" ")
    assert not por_valor[str(ids["per_nil"])].endswith(" ")

    # A regra do `nome_exibicao` vale para TODAS as opções: `<unidade> <nome>`,
    # ou só `<nome>` sem unidade. Comparar com a propriedade lida do banco pega
    # qualquer opção que voltar a exibir `p.nome` puro.
    with app.app_context():
        esperado = {
            str(p.id): html.escape(p.nome_exibicao, quote=False)
            for p in PeriodoLetivo.query.all()
        }
    assert por_valor == esperado


# ---------------------------------------------------------------------------
# T4 — nome de unidade com HTML sai escapado
# ---------------------------------------------------------------------------

def test_t4_nome_de_unidade_com_html_sai_escapado(client, app):
    ids = _setup(app)

    corpo = _pagina_global(client, ids)
    por_valor = {v: t for v, _a, t in _opcoes_periodo(corpo)}
    texto_bruto = por_valor[str(ids["per_c"])]

    # O `<b>` da unidade não vira markup dentro do <option>.
    assert "<b>negrito</b>" not in texto_bruto
    assert "&lt;b&gt;negrito&lt;/b&gt;" in texto_bruto
    assert "<option" not in texto_bruto
    # Descapado, é exatamente o nome_exibicao esperado.
    assert html.unescape(texto_bruto) == f"{UN_C} {NOME_C}"


# ---------------------------------------------------------------------------
# T5 — número de SELECTs constante com 3 e 12 períodos
# ---------------------------------------------------------------------------

def _seed_medicao(app, qtd_periodos):
    """Unidade A com `qtd_periodos` períodos; o mais recente é o alvo."""
    with app.app_context():
        un = Unidade(nome=f"Unid Medidor {qtd_periodos}", ativo=True)
        db.session.add(un)
        db.session.flush()
        adm = _usuario(f"Adm {qtd_periodos}", f"adm.med{qtd_periodos}@x.invalid",
                       "admin", un.id)
        alvo = None
        for i in range(qtd_periodos):
            periodo = _periodo(
                f"Periodo {i:02d}", un.id,
                data_inicio=DATA_INI - timedelta(days=100 + i),
            )
            if i == 0:
                alvo = periodo.id
        db.session.commit()
        return {"un": un.id, "adm": adm.id, "alvo": alvo, "qtd": qtd_periodos}


def _medir_selects(qtd_periodos):
    """SELECTs emitidos num GET do painel em um app NOVO com N períodos.

    Medir em app separado (em vez de criar períodos entre dois requests do
    mesmo app) torna o teste determinístico: o banco já nasce no estado final.
    """
    test_app = create_app(SQLiteTestConfig)
    with test_app.app_context():
        db.create_all()
        engine = db.engine
        ids = _seed_medicao(test_app, qtd_periodos)
        client = test_app.test_client()
        login_as(client, ids["adm"], ids["un"])

        select_lidos = []
        select_so_unidade = []
        select_de_periodos = []

        def _antes(_conn, _cursor, statement, _params, _context, _many):
            texto = str(statement).lower().lstrip()
            if not texto.startswith("select"):
                return
            select_lidos.append(texto)
            # Lazy load do `unidade` por período: SELECT em unidade que não
            # toca periodo_letivo (o joinedload faz os dois na mesma consulta).
            if "from unidade" in texto and "periodo_letivo" not in texto:
                select_so_unidade.append(texto)
            if "from periodo_letivo" in texto:
                select_de_periodos.append(texto)

        event.listen(engine, "before_cursor_execute", _antes)
        try:
            resposta = client.get(f"{URL_PAINEL}?periodo_letivo_id={ids['alvo']}")
        finally:
            event.remove(engine, "before_cursor_execute", _antes)

        assert resposta.status_code == 200
        corpo = resposta.get_data(as_text=True)
        rotulos = _rotulos(corpo)
        db.session.remove()
        db.drop_all()

    return {
        "selects": len(select_lidos),
        "unidade_fora_do_join": len(select_so_unidade),
        # A consulta do painel é a que lista TODOS os períodos da unidade
        # (`order by data_inicio desc`, sem LIMIT); as demais leituras de
        # `periodo_letivo` (referência do BI) são paginadas e não precisam do join.
        "consulta_do_lista_periodo": [
            t for t in select_de_periodos
            if "order by periodo_letivo.data_inicio desc" in t and "limit" not in t
        ],
        "opcoes": len(rotulos),
        "rotulos": rotulos,
        "amostra_unidade": select_so_unidade[:2],
    }


def test_t5_o_numero_de_selects_nao_cresce_com_os_periodos():
    com_3 = _medir_selects(3)
    com_12 = _medir_selects(12)

    # A medição é válida só se os dois cenários realmente renderizaram N opções.
    assert com_3["opcoes"] == 3, com_3["rotulos"]
    assert com_12["opcoes"] == 12, com_12["rotulos"]

    print(
        f"\n[AJ3-E4] SELECTs no painel: 3 periodos={com_3['selects']} | "
        f"12 periodos={com_12['selects']} | SELECTs de unidade fora do join="
        f"{com_3['unidade_fora_do_join']}/{com_12['unidade_fora_do_join']}"
    )

    # Prova direta do `joinedload`: a statement que lista os períodos já traz a
    # unidade na mesma consulta, então o template não paga SELECT por período.
    # Atenção: `periodo_letivo.unidade_id` aparece na projeção mesmo sem o join,
    # por isso a busca é pelo `JOIN unidade` em si.
    for medicao in (com_3, com_12):
        assert len(medicao["consulta_do_lista_periodo"]) == 1, (
            medicao["consulta_do_lista_periodo"]
        )
        assert "join unidade" in medicao["consulta_do_lista_periodo"][0], (
            medicao["consulta_do_lista_periodo"][0]
        )

    assert com_3["selects"] == com_12["selects"], (
        f"o painel fez {com_12['selects']} SELECTs com 12 períodos e "
        f"{com_3['selects']} com 3 (N+1 no nome_exibicao): "
        f"{com_12['amostra_unidade']}"
    )
    assert com_3["unidade_fora_do_join"] == com_12["unidade_fora_do_join"], (
        f"SELECTs em `unidade` fora do join variam com o nº de períodos: "
        f"{com_3['unidade_fora_do_join']} vs {com_12['unidade_fora_do_join']}"
    )


# ---------------------------------------------------------------------------
# T6 — escopo de unidade e permissões inalterados
# ---------------------------------------------------------------------------

def test_t6_pedagogico_de_a_nao_ve_periodos_de_b(client, app):
    ids = _setup(app)
    login_as(client, ids["ped_a"], ids["un_a"])

    corpo = _corpo(client.get(URL_PAINEL))
    rotulos = _rotulos(corpo)

    # Só os dois períodos da unidade A — o homônimo com o prefixo de A.
    assert sorted(rotulos) == sorted(
        [f"{UN_A} {NOME_GEMEO}", f"{UN_A} {NOME_A_EXTRA}"]
    ), rotulos
    assert all(t.startswith(f"{UN_A} ") for t in rotulos), rotulos
    for vedado in (UN_B, UN_C, NOME_SEM_UNIDADE, NOME_C):
        assert vedado not in " | ".join(rotulos)

    # O período selecionado por padrão é de A.
    valor, _texto = _selecionados(corpo)[0]
    with app.app_context():
        periodo = db.session.get(PeriodoLetivo, int(valor))
    assert periodo.unidade_id == ids["un_a"]


def test_t6b_permissoes_do_painel_continuam_as_mesmas(client, app):
    ids = _setup(app)

    for usuario in (ids["adm"], ids["ped_a"], ids["sec_a"], ids["ss_a"]):
        unidade = None if usuario == ids["adm"] else ids["un_a"]
        login_as(client, usuario, unidade)
        assert client.get(URL_PAINEL).status_code == 200, usuario

    login_as(client, ids["prof_a"], ids["un_a"])
    assert client.get(URL_PAINEL).status_code == 403

    # Anônimo continua sem entrada (nenhuma rota descoberta sem login_required).
    assert app.test_client().get(URL_PAINEL).status_code in (301, 302)
