"""AJ3-E2 — Filtro de auditoria por categoria de ação (`/admin/logs`).

Cobre o commit f79c964 (filtro por categoria no banco, com `ilike` parametrizado
e o `select` do formulário) e o `fix(logs)` desta etapa, que corrige a
classificação de `Exclusão de Turma` — a ação era gravada de fato
(`app/registros/turmas.py`) mas caía em `outras`, enquanto a própria tela a pinta
com o selo vermelho de Exclusão.

Regras verificadas:

    T1 `categoria_acao` devolve a categoria esperada para cada ação real dos
       bancos e para cada rótulo que o código emite (parametrizado).
    T2 `GET /admin/logs?acao=<categoria>` devolve apenas as linhas daquela
       categoria e a contagem anunciada é o número de linhas criadas — a
       categoria `exclusao` atravessa mais de uma página.
    T3 "Todas" devolve tudo; "Outras" não duplica linha de nenhuma categoria.
    T4 os links de paginação mantêm o filtro (`acao=<categoria>`).
    T5 valor de categoria inválido na querystring é tratado como "Todas".
    T6 o `select` reexibe a opção escolhida com o atributo `selected`.
    T7 somente `admin` acessa (pedagogico, secretaria, professor e serviço
       social: 403; anônimo: redirecionamento para o login).

Os bancos reais foram lidos uma única vez, com `SELECT DISTINCT acao, COUNT(*)`
(sem a coluna `detalhes`), e o resultado está congelado em `ACOES_REAIS` — os
testes não tocam em Postgres. Toda a escrita é em SQLite de teste, com marcadores
sintéticos (sem e-mail, IP, hash ou CPF).
"""

import re
from datetime import datetime, timedelta

import pytest

from _helpers import login_as

from app import db
from app.models import LogAcao, Unidade, User
from app.auth import categoria_acao

#: Tamanho de página fixado em `app/auth.py::ver_logs` (`per_page=20`).
PER_PAGE = 20

#: Ação no centro do defeito corrigido: é uma exclusão, mas o prefixo faltava.
ACAO_DEFEITO = "Exclusão de Turma"

#: (ação, categoria esperada, linhas em `pautaon`, linhas em `pautaon_ensaio`) —
#: censo de 31/10/2026, 30 ações distintas (27 no banco principal, 29 no de
#: ensaio), evidência bruta em `.tmp/acoes_reais.json`.
ACOES_REAIS = [
    ("Acesso Aprovado", "login", 195, 356),
    ("Alterar Aluno", "edicao", 278, 383),
    ("Alterar ConselhoClasse", "edicao", 0, 27),
    ("Alterar Inscricao", "edicao", 0, 107),
    ("Alterar RegistroAula", "edicao", 10, 34),
    ("Alterar TemaAula", "edicao", 7, 28),
    ("Alterar Turma", "edicao", 51, 142),
    ("Alterar TurmaCurso", "edicao", 32, 159),
    ("Alteração de Cadastros", "edicao", 1, 2),
    ("Aviso de Invasão/Falha", "login", 17, 44),
    ("Cadastro Local", "login", 15, 15),
    ("Criar Aluno", "criacao", 4, 25),
    ("Criar ConselhoClasse", "criacao", 39, 19),
    ("Criar Inscricao", "criacao", 62, 89),
    ("Criar RegistroAula", "criacao", 5, 15),
    ("Criar TemaAula", "criacao", 51, 57),
    ("Criar Turma", "criacao", 14, 25),
    ("Criar TurmaCurso", "criacao", 16, 32),
    ("Disparo de E-mail", "outras", 7, 6),
    ("Editar aluno", "edicao", 74, 80),
    ("Erro E-mail", "outras", 5, 5),
    ("Excluir turma (lógica)", "exclusao", 0, 1),
    (ACAO_DEFEITO, "exclusao", 8, 6),
    ("Informacao Padrao", "outras", 4, 10),
    ("Logoff", "login", 114, 63),
    ("Manutenção", "outras", 2, 2),
    ("Remoção Grave", "exclusao", 6, 6),
    ("Reset de Senha", "login", 4, 3),
    ("Sessões revogadas", "outras", 1, 0),
    ("Troca de Senha", "edicao", 6, 6),
]

#: Rótulos que o código emite mas que ainda não têm nenhuma linha nos bancos —
#: entraram na tabela do relatório e na parametrização para não serem esquecidos
#: quando a primeira linha for gravada.
ACOES_CODIGO_SEM_LINHA = [
    ("Acesso via Google", "outras"),
    ("Cadastro Período Letivo", "outras"),
    ("DESENTURMADO", "outras"),
    ("Desbloqueio de login", "login"),
    ("Excluir aluno", "exclusao"),
    ("Gestão de Unidade", "outras"),
    ("Reativação de Turma", "outras"),
    ("Trocar Professor da Oferta", "edicao"),
    ("TRANSFERENCIA", "outras"),
    ("Vínculo Google", "outras"),
]

#: Linhas extras da ação do defeito: garantem mais de uma página em `exclusao`
#: (o tamanho de página é 20 e o censo só daria 3 linhas da categoria).
EXTRAS_DO_DEFEITO = 25

CATEGORIAS = ("login", "criacao", "edicao", "exclusao", "outras")

_TOTAL_RE = re.compile(r"(\d+)\s+registros encontrados")
_PAGINA_RE = re.compile(r"Página (\d+) de (\d+)")
_MARCADOR_RE = re.compile(r"aj3-\d{3}")
_SELECT_ACAO_RE = re.compile(r'<select name="acao".*?</select>', re.DOTALL)
_OPCAO_RE = re.compile(r'<option value="([a-z]*)"[^>]*\bselected\b')
_PROXIMA_RE = re.compile(r'<a class="page-link" href="([^"]+)">Próxima</a>')


# ---------------------------------------------------------------------------
# Semente sintética
# ---------------------------------------------------------------------------

def _linhas():
    """`(marcador, acao, data_hora)` de toda linha criada pela semente.

    Uma linha por ação real, mais `EXTRAS_DO_DEFEITO` repetições da ação do
    defeito. As `data_hora` são distintas para a ordenação `desc()` da rota ser
    determinística entre páginas (sem isso, a travessia de páginas poderia
    repetir ou perder linha).
    """
    base = datetime(2026, 10, 1, 8, 0)
    acoes = [acao for acao, _, _, _ in ACOES_REAIS]
    acoes += [ACAO_DEFEITO] * EXTRAS_DO_DEFEITO
    return [
        (f"aj3-{i:03d}", acao, base + timedelta(minutes=i))
        for i, acao in enumerate(acoes, start=1)
    ]


def _categoria_esperada(acao):
    """Categoria esperada pela tabela `ACOES_*` — nunca pela função sob teste.

    Se a expectativa viesse de `categoria_acao`, um erro de classificação da
    função passaria despercebido no filtro: a prova fica na tabela congelada.
    """
    for linha_acao, categoria, _, _ in ACOES_REAIS:
        if linha_acao == acao:
            return categoria
    for linha_acao, categoria in ACOES_CODIGO_SEM_LINHA:
        if linha_acao == acao:
            return categoria
    raise AssertionError(f"ação fora da tabela de expectativas: {acao!r}")


#: Expectativas da semente: `marcador -> acao` e contagem por categoria.
LINHAS = _linhas()
ACAO_POR_MARCADOR = {marcador: acao for marcador, acao, _ in LINHAS}
POR_CATEGORIA = {
    categoria: sorted(
        marcador for marcador, acao, _ in LINHAS
        if _categoria_esperada(acao) == categoria
    )
    for categoria in CATEGORIAS
}
TOTAL_LINHAS = len(LINHAS)

#: Nome de usuário de todas as linhas sintéticas (o identificador de cada linha
#: vive só em `detalhes`, para a leitura do HTML não contar duas vezes).
USUARIO_SINTETICO = "Auditoria AJ3"


def _semente(app):
    """Admin, um usuário de cada outro perfil e as linhas de auditoria."""
    with app.app_context():
        unidade = Unidade(nome="Unidade AJ3 Logs", ativo=True)
        db.session.add(unidade)
        db.session.flush()

        ids = {}
        papeis = ("admin", "pedagogico", "secretaria", "professor", "servico_social")
        for papel in papeis:
            user = User(
                name=f"Auditoria {papel}", email=f"{papel}.aj3logs@x.invalid",
                role=papel, first_login=False, unidade_id=unidade.id,
            )
            user.set_password("SenhaLocal!123")
            db.session.add(user)
            db.session.flush()
            ids[papel] = user.id

        for marcador, acao, quando in LINHAS:
            db.session.add(LogAcao(
                usuario_id=ids["admin"], usuario_nome=USUARIO_SINTETICO,
                acao=acao, detalhes=marcador, data_hora=quando,
                unidade_id=unidade.id,
            ))
        db.session.commit()
        return {"unidade": unidade.id, **ids}


# ---------------------------------------------------------------------------
# Leitura do HTML da tela de auditoria
# ---------------------------------------------------------------------------

def _admin(client, ids):
    login_as(client, ids["admin"], ids["unidade"])


def _corpo(client, url):
    resposta = client.get(url)
    assert resposta.status_code == 200, f"{url} -> {resposta.status_code}"
    return resposta.get_data(as_text=True)


def _total(corpo):
    """Contagem anunciada no badge 'N registros encontrados'."""
    match = _TOTAL_RE.search(corpo)
    assert match, "badge de contagem não encontrado no HTML"
    return int(match.group(1))


def _marcadores(corpo):
    """Marcadores das linhas da tabela (só o `<tbody>`, não a página inteira)."""
    inicio = corpo.find("<tbody>")
    fim = corpo.find("</tbody>")
    assert 0 <= inicio < fim, "tabela de logs sem <tbody> no HTML"
    return _MARCADOR_RE.findall(corpo[inicio:fim])


def _paginas(corpo):
    match = _PAGINA_RE.search(corpo)
    assert match, "rodapé de paginação não encontrado no HTML"
    return int(match.group(1)), int(match.group(2))


def _opcao_selecionada(corpo):
    """Valor com `selected` no `<select name="acao">` (lista vazia = 'Todas')."""
    bloco = _SELECT_ACAO_RE.search(corpo)
    assert bloco, "formulário de filtro sem <select name=\"acao\"> no HTML"
    return _OPCAO_RE.findall(bloco.group(0))


def _varrer_paginas(client, filtro):
    """`(marcadores em ordem, total anunciado, número de páginas)`.

    Percorre a tela seguindo os links de "Próxima" — que é exatamente como o
    usuário navega — e confere que o filtro se manteve em cada link.
    """
    vistos = []
    pagina_atual, total_paginas = 1, 1
    total_anunciado = None
    for pagina in range(1, total_paginas + 10):
        url = f"/admin/logs?{filtro}&page={pagina}" if filtro else f"/admin/logs?page={pagina}"
        corpo = _corpo(client, url)
        pagina_atual, total_paginas = _paginas(corpo)
        assert pagina_atual == pagina, f"página pedida {pagina}, exibida {pagina_atual}"
        if total_anunciado is None:
            total_anunciado = _total(corpo)
        else:
            assert _total(corpo) == total_anunciado, "a contagem mudou entre páginas"
        vistos += _marcadores(corpo)
        assert len(_marcadores(corpo)) <= PER_PAGE, "página maior que per_page"
        link = _PROXIMA_RE.search(corpo)
        if link is None:
            assert pagina == total_paginas, "acabou sem ser a última página"
            break
        if filtro:
            assert filtro in link.group(1), (
                f"link de próxima página perdeu o filtro: {link.group(1)}"
            )
    assert pagina_atual == total_paginas, f"parou na página {pagina_atual}/{total_paginas}"
    return vistos, total_anunciado, total_paginas


# ---------------------------------------------------------------------------
# T1 — classificação de cada ação
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "acao,esperada",
    [(acao, categoria) for acao, categoria, _, _ in ACOES_REAIS],
    ids=[acao for acao, _, _, _ in ACOES_REAIS],
)
def test_T1_categoria_acao_classifica_cada_acao_real(acao, esperada):
    """Toda ação dos bancos tem a categoria esperada na função."""
    assert categoria_acao(acao) == esperada


@pytest.mark.parametrize(
    "acao,esperada",
    ACOES_CODIGO_SEM_LINHA,
    ids=[acao for acao, _ in ACOES_CODIGO_SEM_LINHA],
)
def test_T1_categoria_acao_classifica_rotulos_do_codigo(acao, esperada):
    """Rótulos emitidos pelo código (ainda sem linha) já caem na categoria certa."""
    assert categoria_acao(acao) == esperada


def test_T1_acao_do_defeito_nao_fica_em_outras():
    """`Exclusão de Turma` é exclusão — o selo da tela já a pintava assim."""
    assert categoria_acao(ACAO_DEFEITO) == "exclusao"
    assert categoria_acao(ACAO_DEFEITO) != "outras"


def test_T1_acao_vazia_e_deschecida_vao_para_outras():
    """Nada de exceção: vazio, None e texto sem prefixo viram `outras`."""
    assert categoria_acao(None) == "outras"
    assert categoria_acao("") == "outras"
    assert categoria_acao("   ") == "outras"
    assert categoria_acao("Radical Livre") == "outras"


# ---------------------------------------------------------------------------
# T2 — filtro por categoria, contagem e travessia de páginas
# ---------------------------------------------------------------------------

def test_T2_filtro_por_categoria_traz_so_a_categoria_e_bate_a_contagem(app, client):
    """Uma página por categoria: linhas mostradas e total conferem com a semente."""
    _admin(client, _semente(app))
    for categoria in CATEGORIAS:
        corpo = _corpo(client, f"/admin/logs?acao={categoria}&page=1")
        esperadas = POR_CATEGORIA[categoria]
        assert _total(corpo) == len(esperadas), (
            f"categoria {categoria}: anunciado {_total(corpo)}, esperado {len(esperadas)}"
        )
        for marcador in _marcadores(corpo):
            acao = ACAO_POR_MARCADOR[marcador]
            assert categoria_acao(acao) == categoria, (
                f"linha {marcador} ({acao!r}) apareceu no filtro {categoria}"
            )


def test_T2_categoria_do_defeito_atravessa_mais_de_uma_pagina(app, client):
    """`exclusao` tem mais linhas que a página: a travessia não perde nem repete."""
    _admin(client, _semente(app))
    vistos, total, paginas = _varrer_paginas(client, "acao=exclusao")
    esperadas = POR_CATEGORIA["exclusao"]

    assert total == len(esperadas), (
        f"filtro exclusao anuncia {total}, criado {len(esperadas)}"
    )
    assert paginas > 1, f"categoria com {total} linhas cabe em uma página"
    assert len(vistos) > PER_PAGE, "a travessia não passou de uma página de fato"
    assert sorted(vistos) == esperadas, (
        "linhas do filtro exclusao != linhas criadas dessa categoria"
    )
    assert len(vistos) == len(set(vistos)), "linha repetiu entre as páginas"


def test_T2_soma_dos_filtros_cobre_a_semente_inteira(app, client):
    """A união dos cinco filtros cobre cada linha exatamente uma vez."""
    _admin(client, _semente(app))
    ajuntado = []
    for categoria in CATEGORIAS:
        vistos, total, _ = _varrer_paginas(client, f"acao={categoria}")
        assert total == len(POR_CATEGORIA[categoria])
        ajuntado += vistos

    assert sorted(ajuntado) == sorted(ACAO_POR_MARCADOR), (
        "a soma dos filtros por categoria não é a semente inteira"
    )
    assert len(ajuntado) == TOTAL_LINHAS


# ---------------------------------------------------------------------------
# T3 — "Todas" e "Outras"
# ---------------------------------------------------------------------------

def test_T3_sem_filtro_devolve_tudo(app, client):
    """`?acao=` vazio e ausência do parâmetro são a mesma coisa: todas as linhas."""
    _admin(client, _semente(app))
    for url in ("/admin/logs", "/admin/logs?", "/admin/logs?acao="):
        corpo = _corpo(client, url)
        assert _total(corpo) == TOTAL_LINHAS, url
        assert len(_marcadores(corpo)) == PER_PAGE, f"{url} primeira página cheia"

    vistos, total, paginas = _varrer_paginas(client, "")
    assert total == TOTAL_LINHAS
    assert sorted(vistos) == sorted(ACAO_POR_MARCADOR)
    assert paginas == -(-TOTAL_LINHAS // PER_PAGE), "número de páginas inesperado"


def test_T3_outras_nao_duplica_linha_de_outra_categoria(app, client):
    """`outras` é o complemento exato: nada de login/criacao/edicao/exclusao."""
    _admin(client, _semente(app))
    vistos, total, _ = _varrer_paginas(client, "acao=outras")
    assert sorted(vistos) == POR_CATEGORIA["outras"]
    assert total == len(POR_CATEGORIA["outras"])

    outras = set(vistos)
    for categoria in ("login", "criacao", "edicao", "exclusao"):
        assert outras.isdisjoint(POR_CATEGORIA[categoria]), (
            f"filtro outras repetiu linha da categoria {categoria}"
        )


def test_T3_linhas_do_defeito_saiam_de_outras(app, client):
    """Ação do defeito não pode aparecer no filtro `outras` nem faltar em `exclusao`."""
    _admin(client, _semente(app))
    vistas_outras, _, _ = _varrer_paginas(client, "acao=outras")
    vistas_exclusao, _, _ = _varrer_paginas(client, "acao=exclusao")
    do_defeito = [
        marcador for marcador, acao, _ in LINHAS if acao == ACAO_DEFEITO
    ]

    assert do_defeito, "semente sem linha da ação do defeito"
    for marcador in do_defeito:
        assert marcador not in vistas_outras, (
            f"{marcador} ({ACAO_DEFEITO!r}) ainda aparece em 'outras'"
        )
        assert marcador in vistas_exclusao, (
            f"{marcador} ({ACAO_DEFEITO!r}) falta no filtro de exclusão"
        )


# ---------------------------------------------------------------------------
# T4 — a paginação mantém o filtro
# ---------------------------------------------------------------------------

def test_T4_links_de_paginacao_mantem_o_filtro(app, client):
    """O href de "Próxima" leva `acao=<categoria>` junto com `page=<n+1>`."""
    _admin(client, _semente(app))
    corpo = _corpo(client, "/admin/logs?acao=exclusao&page=1")
    link = _PROXIMA_RE.search(corpo)
    assert link, "sem link de próxima página numa categoria com várias páginas"
    href = link.group(1)
    assert "acao=exclusao" in href, href
    assert "page=2" in href, href

    # A página 2 do filtro continua mostrando só a categoria filtrada.
    corpo2 = _corpo(client, "/admin/logs?acao=exclusao&page=2")
    pagina, total_paginas = _paginas(corpo2)
    assert (pagina, total_paginas) == (2, total_paginas)
    assert _total(corpo2) == len(POR_CATEGORIA["exclusao"])
    for marcador in _marcadores(corpo2):
        assert categoria_acao(ACAO_POR_MARCADOR[marcador]) == "exclusao"


# ---------------------------------------------------------------------------
# T5 — categoria inválida é tratada como "Todas", sem erro
# ---------------------------------------------------------------------------

def test_T5_valor_invalido_na_querystring_vira_todas(app, client):
    """Nada de 500 nem de filtro perdido: valor fora do conjunto = todas as linhas."""
    _admin(client, _semente(app))
    para_todas = [
        "/admin/logs?acao=sessoes",
        "/admin/logs?acao=Exclusao%20de%20Turma",
        "/admin/logs?acao=%25",
        "/admin/logs?acao=_",
        "/admin/logs?acao=0",
        "/admin/logs?acao=login%20criacao",
    ]
    for url in para_todas:
        corpo = _corpo(client, url)
        assert _total(corpo) == TOTAL_LINHAS, (
            f"{url} não tratou a categoria inválida como 'Todas' "
            f"({_total(corpo)} de {TOTAL_LINHAS})"
        )


def test_T5_caixa_alta_e_espacejo_funcionam_como_na_opcao(app, client):
    """O filtro aceita a categoria com a forma do `select` (minúscula) e variações."""
    _admin(client, _semente(app))
    corpo = _corpo(client, "/admin/logs?acao=EXCLUSAO")
    assert _total(corpo) == len(POR_CATEGORIA["exclusao"])
    assert ACAO_DEFEITO in {
        ACAO_POR_MARCADOR[m] for m in _marcadores(corpo)
    }


# ---------------------------------------------------------------------------
# T6 — o select reexibe a opção escolhida
# ---------------------------------------------------------------------------

def test_T6_select_reexibe_a_opcao_escolhida(app, client):
    """A opção correspondente ao filtro vem com `selected`; as outras não."""
    _admin(client, _semente(app))
    for categoria in CATEGORIAS:
        corpo = _corpo(client, f"/admin/logs?acao={categoria}")
        assert _opcao_selecionada(corpo) == [categoria], (
            f"filtro {categoria}: select reexibiu {_opcao_selecionada(corpo)}"
        )

    corpo = _corpo(client, "/admin/logs")
    assert _opcao_selecionada(corpo) == [""], (
        "sem filtro: 'Todas as Ações' deveria vir com selected"
    )

    corpo = _corpo(client, "/admin/logs?acao=inexistente")
    assert _opcao_selecionada(corpo) == [""], (
        "categoria inválida: o select deve voltar para 'Todas as Ações'"
    )


# ---------------------------------------------------------------------------
# T7 — somente admin acessa
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "papel", ["pedagogico", "secretaria", "professor", "servico_social"]
)
def test_T7_perfis_nao_admin_recebem_403(app, client, papel):
    """A tela de auditoria continua restrita ao admin, com ou sem filtro."""
    ids = _semente(app)
    login_as(client, ids[papel], ids["unidade"])
    assert client.get("/admin/logs").status_code == 403
    assert client.get("/admin/logs?acao=exclusao&page=2").status_code == 403


def test_T7_anonimo_e_redirecionado_para_o_login(app, client):
    """Sem sessão não há leitura de log: redirecionamento para a página de login."""
    resposta = client.get("/admin/logs?acao=exclusao")
    assert resposta.status_code in (301, 302)
    assert "/login" in resposta.headers.get("Location", "")


def test_T7_admin_ve_a_pagina(app, client):
    """Contraste do T7: o admin entra (sem isso os 403 acima seriam vazios)."""
    _admin(client, _semente(app))
    corpo = _corpo(client, "/admin/logs")
    assert _total(corpo) == TOTAL_LINHAS
