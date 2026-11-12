"""AJ20 — GET do lançamento não escreve; ConselhoClasse nasce só no POST.

Antes do AJ20, `GET /conselho/lancamento` criava uma `ConselhoClasse` por
aluno ativo da oferta/etapa e dava commit — GET com efeito colateral, cascas
vazias em produção e risco de UNIQUE (`uix_conselho_oferta`) em aberturas
simultâneas. Agora a linha só nasce quando um fluxo de ESCRITA vai gravar
conteúdo, via `get_or_create_conselho` (SAVEPOINT + releitura em
IntegrityError — nunca 500 em corrida).

Cobertura:
    T1 GET não escreve: contagem de ConselhoClasse/ConselhoResposta igual
       antes e depois, sessão sem new/dirty, duas aberturas seguidas.
    T2 POST sem conteúdo não cria linha.
    T3 POST com resposta cria exatamente 1 ConselhoClasse por
       aluno/etapa/oferta; POST só com observação idem; fechamento FINAL
       idem.
    T4 corrida simulada: a linha aparece entre o select e o insert —
       IntegrityError é capturado, a linha vencedora é relida e o POST
       grava nela (sem 500, sem duplicar).
    T5 casca vazia pré-existente (o que o GET antigo criava) funciona como
       antes: GET mostra vazio e o POST grava NA MESMA linha.
    T6 leitores com linha ausente: ficha 360°, painel, resultado do
       conselho, fechamento e guardas de histórico/lançamento — todos com
       comportamento idêntico à casca vazia.
    T7 perfis: secretaria/gerência/serviço social seguem 403 sem gravar.
    T8 o número de queries do GET não aumenta com mais alunos (o laço
       por-aluno de SELECT foi removido).
"""

import pytest
from _helpers import login_as, nova_inscricao
from sqlalchemy import event
from test_conselho_oferta import _enturma, _perguntas, _setup

import app.conselho as conselho_mod
from app import db
from app.models import Aluno, ConselhoClasse, ConselhoResposta, User
from app.models.enums import EtapaConselho
from app.services.turma_curso import (
    oferta_tem_lancamentos,
    ofertas_com_lancamentos,
    turma_tem_historico,
)

_URL_LANCAMENTO = (
    "/conselho/lancamento?turma={turma}&etapa={etapa}&oferta_sel={oferta}"
)


# ---------------------------------------------------------------------------
# Semente / helpers (mesmo padrão do test_aj19)
# ---------------------------------------------------------------------------

def _cenario(app, *, role="admin"):
    ids = _setup(app, ofertas=1, role=role)
    with app.app_context():
        usuario = db.session.get(User, ids["user_id"])
        usuario.unidade_id = ids["un_a"]
        db.session.commit()
    _enturma(app, ids, "aluno_a", oferta_idx=0)
    _enturma(app, ids, "aluno_b", oferta_idx=0)
    p_aluno, p_turma = _perguntas(app)
    ids["p_aluno"] = p_aluno
    ids["p_turma"] = p_turma
    return ids


def _login(client, ids, role="admin"):
    if role == "professor":
        login_as(client, ids["prof"], ids["un_a"])
    else:
        login_as(client, ids["user_id"], ids["un_a"])


def _url(ids, *, etapa="INICIAL"):
    return _URL_LANCAMENTO.format(
        turma=ids["turma"], etapa=etapa, oferta=ids["ofertas"][0]
    )


def _post(client, ids, *, etapa="INICIAL", campos=None):
    data = {
        "turma_id": str(ids["turma"]),
        "etapa": etapa,
        "turma_curso_id": str(ids["ofertas"][0]),
    }
    data.update(campos or {})
    return client.post("/conselho/salvar", data=data)


def _contagens(app):
    with app.app_context():
        return (
            ConselhoClasse.query.count(),
            ConselhoResposta.query.count(),
        )


# ---------------------------------------------------------------------------
# T1 — GET não escreve
# ---------------------------------------------------------------------------

def test_t1_get_nao_escreve_nem_cria_cascas(client, app):
    ids = _cenario(app)
    _login(client, ids)

    assert _contagens(app) == (0, 0)
    for _ in range(2):  # duas aberturas seguidas
        r = client.get(_url(ids))
        assert r.status_code == 200
        assert "Observações e informações adicionais" in r.data.decode("utf-8")

    assert _contagens(app) == (0, 0), (
        "o GET criou ConselhoClasse/ConselhoResposta — o lazy-create do "
        "AJ20 não está valendo"
    )
    with app.app_context():
        assert len(db.session.new) == 0
        assert not [o for o in db.session.dirty]


# ---------------------------------------------------------------------------
# T2 — POST sem conteúdo não cria linha
# ---------------------------------------------------------------------------

def test_t2_post_sem_conteudo_nao_cria_linha(client, app):
    ids = _cenario(app)
    _login(client, ids)

    r = _post(client, ids)  # só ids, nenhum resp_/obs_
    assert r.status_code == 302
    assert _contagens(app) == (0, 0)

    # obs_ enviado vazio também não cria (mesma regra do AJ19).
    r = _post(client, ids, campos={
        f"obs_{ids['aluno_a']}": "",
        f"obs_{ids['aluno_b']}": "   ",
    })
    assert r.status_code == 302
    assert _contagens(app) == (0, 0)


# ---------------------------------------------------------------------------
# T3 — POST com conteúdo cria exatamente 1 linha por aluno/etapa/oferta
# ---------------------------------------------------------------------------

def test_t3_post_com_resposta_cria_uma_linha_por_aluno(client, app):
    ids = _cenario(app)
    _login(client, ids)

    r = _post(client, ids, campos={
        f"resp_{ids['aluno_a']}_{ids['p_aluno']}": "Sempre",
    })
    assert r.status_code == 302

    with app.app_context():
        linhas = ConselhoClasse.query.filter_by(
            turma_curso_id=ids["ofertas"][0],
            etapa=EtapaConselho.INICIAL,
        ).all()
        # Só o aluno com resposta enviada ganhou linha — nada de casca
        # para o outro aluno.
        assert [c.aluno_id for c in linhas] == [ids["aluno_a"]]
        assert len(linhas) == 1
        assert ConselhoResposta.query.count() == 1


def test_t3b_post_so_com_observacao_cria_uma_linha(client, app):
    ids = _cenario(app)
    _login(client, ids)

    r = _post(client, ids, campos={
        f"obs_{ids['aluno_b']}": "Parecer geral do Beto",
    })
    assert r.status_code == 302

    with app.app_context():
        linhas = ConselhoClasse.query.filter_by(
            turma_curso_id=ids["ofertas"][0],
            etapa=EtapaConselho.INICIAL,
        ).all()
        assert [c.aluno_id for c in linhas] == [ids["aluno_b"]]
        assert linhas[0].observacao == "Parecer geral do Beto"
        # Sem resposta enviada, nenhuma ConselhoResposta nasce.
        assert ConselhoResposta.query.count() == 0


def test_t3c_fechamento_cria_uma_linha_final_por_aluno(client, app):
    ids = _cenario(app)
    _login(client, ids)

    r = client.post(
        f"/conselho/fechamento/{ids['turma']}/salvar",
        json={
            "oferta_id": ids["ofertas"][0],
            "dados": [
                {"aluno_id": ids["aluno_a"], "situacao": "APROVADO",
                 "proxima_turma_id": None},
                {"aluno_id": ids["aluno_b"], "situacao": "", 
                 "proxima_turma_id": None},
            ],
        },
    )
    assert r.status_code == 200
    assert r.get_json()["success"] is True

    with app.app_context():
        finais = ConselhoClasse.query.filter_by(
            turma_curso_id=ids["ofertas"][0],
            etapa=EtapaConselho.FINAL,
        ).all()
        assert len(finais) == 2
        assert {c.aluno_id for c in finais} == {
            ids["aluno_a"], ids["aluno_b"],
        }
        assert all(c.concluido for c in finais)
        # E nada nasceu na etapa INICIAL.
        assert ConselhoClasse.query.filter_by(
            etapa=EtapaConselho.INICIAL
        ).count() == 0


# ---------------------------------------------------------------------------
# T4 — corrida: linha criada entre o select e o insert
# ---------------------------------------------------------------------------

def test_t4_corrida_na_unique_rele_a_linha_vencedora(client, app, monkeypatch):
    """Simula duas requisições concorrentes: a "vencedora" grava a
    ConselhoClasse depois do SELECT do mapa mas antes do INSERT do helper.

    O `_buscar_conselho` é patchado para, na primeira chamada (dentro do
    request), criar e dar flush na linha vencedora e devolver None — o
    helper então tenta o INSERT, toma IntegrityError na UNIQUE e relê a
    vencedora. O POST inteiro deve terminar em 302, com a resposta
    gravada NA linha vencedora e sem duplicar.
    """
    ids = _cenario(app)
    _login(client, ids)

    real_buscar = conselho_mod._buscar_conselho
    estado = {"chamadas": 0}

    def buscar_que_perde_a_corrida(*args, **kwargs):
        estado["chamadas"] += 1
        if estado["chamadas"] == 1:
            # "Outra requisição" venceu: grava e dá flush NA MESMA sessão
            # do request (db.session resolve o escopo do request aqui).
            db.session.add(ConselhoClasse(
                turma_id=ids["turma"],
                turma_curso_id=ids["ofertas"][0],
                aluno_id=ids["aluno_a"],
                etapa=EtapaConselho.INICIAL.value,
                unidade_id=ids["un_a"],
            ))
            db.session.flush()
            return None
        return real_buscar(*args, **kwargs)

    monkeypatch.setattr(
        conselho_mod, "_buscar_conselho", buscar_que_perde_a_corrida
    )

    r = _post(client, ids, campos={
        f"resp_{ids['aluno_a']}_{ids['p_aluno']}": "Sempre",
        f"obs_{ids['aluno_a']}": "Obs na linha vencedora",
    })
    assert r.status_code == 302, "a corrida não pode virar 500"

    with app.app_context():
        linhas = ConselhoClasse.query.filter_by(
            turma_curso_id=ids["ofertas"][0],
            etapa=EtapaConselho.INICIAL,
            aluno_id=ids["aluno_a"],
        ).all()
        assert len(linhas) == 1, "a corrida duplicou a linha"
        vencedora = linhas[0]
        assert vencedora.observacao == "Obs na linha vencedora"
        resposta = ConselhoResposta.query.filter_by(
            aluno_id=ids["aluno_a"], pergunta_id=ids["p_aluno"],
        ).one()
        assert resposta.conselho_id == vencedora.id
        assert resposta.resposta == "Sempre"


# ---------------------------------------------------------------------------
# T5 — casca vazia pré-existente (legada do GET antigo) funciona como antes
# ---------------------------------------------------------------------------

def test_t5_casca_vazia_existente_se_comporta_como_ausente(client, app):
    ids = _cenario(app)
    _login(client, ids)

    # Casca idêntica à que o GET antigo criava: linha sem conteúdo.
    with app.app_context():
        casca = ConselhoClasse(
            turma_id=ids["turma"],
            turma_curso_id=ids["ofertas"][0],
            aluno_id=ids["aluno_a"],
            etapa=EtapaConselho.INICIAL,
            unidade_id=ids["un_a"],
        )
        db.session.add(casca)
        db.session.commit()
        casca_id = casca.id

    # GET mostra o campo vazio (casca ≡ ausente na leitura).
    corpo = client.get(_url(ids)).data.decode("utf-8")
    assert f'name="obs_{ids["aluno_a"]}"' in corpo

    # POST grava NA MESMA linha — não nasce uma segunda.
    r = _post(client, ids, campos={
        f"obs_{ids['aluno_a']}": "Texto na casca",
    })
    assert r.status_code == 302
    with app.app_context():
        linhas = ConselhoClasse.query.filter_by(
            turma_curso_id=ids["ofertas"][0],
            etapa=EtapaConselho.INICIAL,
            aluno_id=ids["aluno_a"],
        ).all()
        assert len(linhas) == 1
        assert linhas[0].id == casca_id
        assert linhas[0].observacao == "Texto na casca"


# ---------------------------------------------------------------------------
# T6 — leitores com linha ausente: casca ≡ ausente em todos
# ---------------------------------------------------------------------------

def test_t6_leitores_com_linha_ausente_iguais_a_casca(client, app):
    ids = _cenario(app)
    _login(client, ids)

    ficha_url = (
        f"/relatorios/alunos/{ids['aluno_a']}/ficha"
        f"?turma_id={ids['turma']}&oferta_sel={ids['ofertas'][0]}"
    )
    fechamento_url = (
        f"/conselho/fechamento/{ids['turma']}"
        f"?oferta_sel={ids['ofertas'][0]}"
    )

    # Sem NENHUMA linha: todos os leitores respondem sem erro.
    assert client.get(ficha_url).status_code == 200
    assert client.get(fechamento_url).status_code == 200
    painel = client.get("/conselho")
    assert painel.status_code in (200, 302)
    resultado = client.get("/relatorios/conselho")
    assert resultado.status_code in (200, 302, 403)

    with app.app_context():
        # Guardas de histórico/lançamento: linha ausente = sem histórico.
        assert turma_tem_historico(ids["turma"]) is False
        assert oferta_tem_lancamentos(ids["ofertas"][0]) is False
        assert ofertas_com_lancamentos([ids["ofertas"][0]]) == set()

    # Agora a casca: MESMOS resultados — casca vazia ≡ linha ausente.
    with app.app_context():
        db.session.add(ConselhoClasse(
            turma_id=ids["turma"],
            turma_curso_id=ids["ofertas"][0],
            aluno_id=ids["aluno_a"],
            etapa=EtapaConselho.INICIAL,
            unidade_id=ids["un_a"],
        ))
        db.session.commit()

    assert client.get(ficha_url).status_code == 200
    assert client.get(fechamento_url).status_code == 200
    with app.app_context():
        assert turma_tem_historico(ids["turma"]) is False
        assert oferta_tem_lancamentos(ids["ofertas"][0]) is False
        assert ofertas_com_lancamentos([ids["ofertas"][0]]) == set()


def test_t6b_casca_com_conteudo_conta_como_historico(client, app):
    """A condição `cond_conselho_sem_conteudo` não pode esconder linha
    real: conselho concluído/situacao/observação/resposta contam."""
    ids = _cenario(app)
    _login(client, ids)

    with app.app_context():
        # Observação sozinha já é conteúdo.
        c = ConselhoClasse(
            turma_id=ids["turma"],
            turma_curso_id=ids["ofertas"][0],
            aluno_id=ids["aluno_a"],
            etapa=EtapaConselho.INICIAL,
            unidade_id=ids["un_a"],
            observacao="texto",
        )
        db.session.add(c)
        db.session.commit()
        assert turma_tem_historico(ids["turma"]) is True
        assert oferta_tem_lancamentos(ids["ofertas"][0]) is True
        assert ids["ofertas"][0] in ofertas_com_lancamentos(
            [ids["ofertas"][0]]
        )


# ---------------------------------------------------------------------------
# T7 — perfis inalterados
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("role", ["secretaria", "gerencia", "servico_social"])
def test_t7_perfis_somente_leitura_recebem_403(client, app, role):
    ids = _cenario(app, role=role)
    _login(client, ids, role)

    r = _post(client, ids, campos={
        f"obs_{ids['aluno_a']}": "Invasao",
        f"resp_{ids['aluno_a']}_{ids['p_aluno']}": "Sempre",
    })
    assert r.status_code == 403
    assert _contagens(app) == (0, 0)


# ---------------------------------------------------------------------------
# T8 — queries do GET não aumentam com mais alunos
# ---------------------------------------------------------------------------

def _contar_selects(db_engine, fn):
    contagem = {"n": 0}

    def counter(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            contagem["n"] += 1

    event.listen(db_engine, "before_cursor_execute", counter)
    try:
        fn()
    finally:
        event.remove(db_engine, "before_cursor_execute", counter)
    return contagem["n"]


def test_t8_queries_do_get_nao_aumentam_com_mais_alunos(client, app):
    ids = _cenario(app)
    _login(client, ids)

    with app.app_context():
        engine = db.engine

    n2 = _contar_selects(engine, lambda: client.get(_url(ids)))

    # Terceiro aluno na mesma oferta: o GET antigo faria +1 SELECT por aluno.
    with app.app_context():
        aluno_c = Aluno(nome="Aluno Cid", unidade_id=ids["un_a"], ativo=True)
        db.session.add(aluno_c)
        db.session.flush()
        nova_inscricao(aluno_c.id, ids["turma"], ids["ofertas"][0])
        db.session.commit()

    n3 = _contar_selects(engine, lambda: client.get(_url(ids)))
    assert n3 == n2, (
        f"o GET voltou a escalar por aluno: {n2} selects com 2 alunos, "
        f"{n3} com 3"
    )
