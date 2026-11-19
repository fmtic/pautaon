"""AJ22-F — Blocos de níveis recolhíveis na aba Níveis do planejamento.

Sem migration, sem schema e sem mudança nas regras de agrupamento/ordenação
(AJ22-D): cada bloco de curso passa a ser um ``collapse`` do Bootstrap,
recolhido por padrão. O aviso "Níveis sem curso" fica sempre aberto, e o
bloco do curso de um nível gravado é reaberto pelo servidor no redirect
(parâmetro ``nivel_grupo``), sem depender de JS.

O conteúdo das linhas continua integralmente no HTML: sem JS, um bloco
``<noscript>`` força a exibição de todos os blocos (progressive enhancement).
"""

from __future__ import annotations

import re
from datetime import date
from urllib.parse import parse_qs, urlparse

from sqlalchemy import event

from app.database import db
from app.models import Curso, Nivel, PeriodoLetivo, Turma, Unidade, User
from _helpers import login_as, nova_oferta

DATA_INI = date(2026, 2, 2)
DATA_FIM = date(2026, 6, 30)


def _seed(app):
    with app.app_context():
        un = Unidade(nome="Unidade F Colapso", ativo=True)
        db.session.add(un)
        db.session.flush()
        usuario = User(
            name="Admin F Colapso", email="aj22f-colapso@example.com", role="admin",
            first_login=False, unidade_id=un.id,
        )
        periodo = PeriodoLetivo(
            nome="Periodo F Colapso", data_inicio=DATA_INI, data_fim=DATA_FIM,
            unidade_id=un.id, ativo=True,
        )
        curso_a = Curso(nome="Curso A", unidade_id=un.id, ativo=True)
        curso_b = Curso(nome="Curso B", unidade_id=un.id, ativo=True)
        db.session.add_all([usuario, periodo, curso_a, curso_b])
        db.session.flush()
        turma = Turma(
            nome="Turma F", data_inicio=DATA_INI, data_fim=DATA_FIM,
            periodo_letivo_id=periodo.id, unidade_id=un.id, ativo=True,
        )
        db.session.add(turma)
        db.session.flush()
        nova_oferta(turma.id, curso_a.id, un.id, principal=True)

        n_a1 = Nivel(nome="Iniciante A", curso_id=curso_a.id, unidade_id=un.id, ativo=True)
        n_a2 = Nivel(nome="Avançado A", curso_id=curso_a.id, unidade_id=un.id, ativo=True)
        n_b1 = Nivel(nome="Módulo B", curso_id=curso_b.id, unidade_id=un.id, ativo=True)
        n_legado = Nivel(nome="Legado", curso_id=None, unidade_id=un.id, ativo=True)
        db.session.add_all([n_a1, n_a2, n_b1, n_legado])
        db.session.commit()
        return {
            "user_id": usuario.id,
            "unidade": un.id,
            "curso_a": curso_a.id,
            "curso_b": curso_b.id,
            "n_a1": n_a1.id,
            "n_b1": n_b1.id,
        }


def _login(client, ids):
    login_as(client, str(ids["user_id"]), ids["unidade"])


def _cabecalho(body, chave):
    match = re.search(
        r'(<tr[^>]*data-grupo-nivel="' + re.escape(str(chave)) + r'"[^>]*>.*?</tr>)',
        body,
        re.S,
    )
    assert match, f"cabeçalho do grupo {chave} não encontrado no HTML"
    return match.group(0)


def _membros(body, chave):
    match = re.search(
        r'<tbody id="nivel-grupo-' + re.escape(str(chave)) + r'"[^>]*>', body
    )
    assert match, f"tbody do grupo {chave} não encontrado no HTML"
    return match.group(0)


def _contar_selects(engine, fn):
    contagem = {"n": 0}

    def counter(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            contagem["n"] += 1

    event.listen(engine, "before_cursor_execute", counter)
    try:
        fn()
    finally:
        event.remove(engine, "before_cursor_execute", counter)
    return contagem["n"]


def _criar_nivel(app, nome, curso_id, unidade_id):
    with app.app_context():
        db.session.add(Nivel(nome=nome, curso_id=curso_id, unidade_id=unidade_id, ativo=True))
        db.session.commit()


# ---------------------------------------------------------------------------
# Collapse por curso / ARIA / progressive enhancement
# ---------------------------------------------------------------------------


def test_blocos_de_curso_comecam_recolhidos_com_aria_e_teclado(client, app):
    ids = _seed(app)
    _login(client, ids)
    body = client.get("/planejamento?aba=niveis").get_data(as_text=True)

    for curso_id in (ids["curso_a"], ids["curso_b"]):
        cabecalho = _cabecalho(body, curso_id)
        assert 'data-bs-toggle="collapse"' in cabecalho
        assert f'data-bs-target="#nivel-grupo-{curso_id}"' in cabecalho
        assert f'aria-controls="nivel-grupo-{curso_id}"' in cabecalho
        assert 'aria-expanded="false"' in cabecalho
        assert 'role="button"' in cabecalho
        assert 'tabindex="0"' in cabecalho
        assert 'grupo-nivel-chevron' in cabecalho
        membros = _membros(body, curso_id)
        assert 'class="grupo-nivel-membros collapse"' in membros

    # O conteúdo continua no HTML (não é injetado por JS).
    for nome in ("Iniciante A", "Avançado A", "Módulo B", "Legado"):
        assert nome in body
    assert "1 nível" in body  # Curso B
    assert "2 níveis" in body  # Curso A


def test_sem_curso_fica_aberto_e_fora_do_collapse(client, app):
    ids = _seed(app)
    _login(client, ids)
    body = client.get("/planejamento?aba=niveis").get_data(as_text=True)

    alerta = re.search(r'<div class="alert alert-warning[^"]*">(.*?)</div>', body, re.S)
    assert alerta and "Níveis sem curso" in alerta.group(1)
    assert body.index("Níveis sem curso") < body.index('<tbody id="nivel-grupo-')

    cabecalho = _cabecalho(body, "sem-curso")
    assert 'aria-expanded="true"' in cabecalho
    assert 'aria-controls="nivel-grupo-sem-curso"' in cabecalho
    assert 'data-bs-toggle="collapse"' not in cabecalho
    assert 'class="grupo-nivel-membros collapse show"' in _membros(body, "sem-curso")


def test_botoes_expandir_e_recolher_todos_presentes(client, app):
    ids = _seed(app)
    _login(client, ids)
    body = client.get("/planejamento?aba=niveis").get_data(as_text=True)

    assert 'id="btnExpandirNiveis"' in body
    assert 'id="btnRecolherNiveis"' in body
    assert "Expandir todos" in body
    assert "Recolher todos" in body
    assert 'class="btn btn-sm btn-outline-secondary js-nivel-collapse"' in body
    assert "<noscript>" in body
    assert ".grupo-nivel-membros.collapse:not(.show)" in body


# ---------------------------------------------------------------------------
# Reabertura do bloco após escrita (state vindo do servidor)
# ---------------------------------------------------------------------------


def test_criar_nivel_reabre_bloco_do_curso(client, app):
    ids = _seed(app)
    _login(client, ids)
    resposta = client.post("/planejamento", data={
        "tipo_post": "nivel",
        "nome_nivel": "Nível Novo A",
        "curso_nivel": str(ids["curso_a"]),
        "aba": "niveis",
    })
    assert resposta.status_code == 302
    local = resposta.headers["Location"]
    assert parse_qs(urlparse(local).query) == {
        "aba": ["niveis"],
        "nivel_grupo": [str(ids["curso_a"])],
    }

    body = client.get(local).get_data(as_text=True)
    assert 'aria-expanded="true"' in _cabecalho(body, ids["curso_a"])
    assert 'collapse show' in _membros(body, ids["curso_a"])
    assert 'aria-expanded="false"' in _cabecalho(body, ids["curso_b"])
    assert 'Nível Novo A' in body


def test_editar_nivel_reabre_bloco_do_curso_resultante(client, app):
    ids = _seed(app)
    _login(client, ids)
    resposta = client.post(
        f"/planejamento/nivel/editar/{ids['n_a1']}",
        data={
            "nome_nivel": "Iniciante A revisado",
            "curso_nivel": str(ids["curso_b"]),
            "aba": "niveis",
        },
    )
    assert resposta.status_code == 302
    assert parse_qs(urlparse(resposta.headers["Location"]).query)["nivel_grupo"] == [
        str(ids["curso_b"])
    ]

    body = client.get(resposta.headers["Location"]).get_data(as_text=True)
    assert 'aria-expanded="true"' in _cabecalho(body, ids["curso_b"])
    assert 'collapse show' in _membros(body, ids["curso_b"])
    assert 'aria-expanded="false"' in _cabecalho(body, ids["curso_a"])
    assert "Iniciante A revisado" in body


def test_inativar_nivel_reabre_bloco_do_curso(client, app):
    ids = _seed(app)
    _login(client, ids)
    resposta = client.post(
        f"/planejamento/nivel/inativar/{ids['n_a1']}", data={"aba": "niveis"}
    )
    assert resposta.status_code == 302
    assert parse_qs(urlparse(resposta.headers["Location"]).query)["nivel_grupo"] == [
        str(ids["curso_a"])
    ]

    body = client.get(resposta.headers["Location"]).get_data(as_text=True)
    assert 'aria-expanded="true"' in _cabecalho(body, ids["curso_a"])
    assert 'collapse show' in _membros(body, ids["curso_a"])
    assert "INATIVO" in body


def test_parametro_invalido_nao_reabre_bloco(client, app):
    ids = _seed(app)
    _login(client, ids)
    body = client.get("/planejamento?aba=niveis&nivel_grupo=nao-e-id").get_data(
        as_text=True
    )
    assert 'aria-expanded="false"' in _cabecalho(body, ids["curso_a"])
    assert 'aria-expanded="false"' in _cabecalho(body, ids["curso_b"])
    assert 'aria-expanded="true"' in _cabecalho(body, "sem-curso")


def test_ordem_e_agrupamento_a_z_inalterados(client, app):
    ids = _seed(app)
    _login(client, ids)
    body = client.get("/planejamento?aba=niveis").get_data(as_text=True)
    posicoes = {
        chave: body.index(f'data-grupo-nivel="{chave}"')
        for chave in ("sem-curso", ids["curso_a"], ids["curso_b"])
    }
    assert posicoes["sem-curso"] < posicoes[ids["curso_a"]] < posicoes[ids["curso_b"]]
    assert body.index("Avançado A") < body.index("Iniciante A")


# ---------------------------------------------------------------------------
# Sem N+1
# ---------------------------------------------------------------------------


def test_queries_constantes_com_2x7_niveis(client, app):
    ids = _seed(app)
    _login(client, ids)

    def carregar():
        return client.get("/planejamento?aba=niveis").get_data(as_text=True)

    n7 = _contar_selects(db.engine, carregar)
    for indice in range(7):
        _criar_nivel(app, f"Nível {indice:02d}", ids["curso_a"], ids["unidade"])
    n14 = _contar_selects(db.engine, carregar)

    assert n14 <= n7 + 5
