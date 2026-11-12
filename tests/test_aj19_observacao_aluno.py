"""AJ19 — uma observação geral por aluno no conselho individual.

Regra: o lançamento individual do conselho deixa de ter um textarea de
observação por pergunta e passa a ter UM campo "Observações e informações
adicionais" no fim do card de cada aluno. O texto é gravado em
``ConselhoClasse.observacao`` (uma linha por aluno × etapa × oferta);
``ConselhoResposta.observacao`` deixa de ser lido/escrito (a coluna continua
no schema, sem migration).

Cobertura:
    T1 GET: um único ``obs_<aluno>`` por aluno, nenhum ``obs_<aluno>_<pergunta>``.
    T2 POST grava em ``ConselhoClasse.observacao`` e o GET devolve por aluno.
    T3 aluno sem observação fica vazio e não contamina o outro aluno.
    T4 isolamento: aluno × etapa e aluno × oferta não se misturam.
    T5 perfis: admin/pedagógico/professor gravam; secretaria/gerência/serviço
       social recebem 403 e nada é gravado.
    T6 limite de 5000 caracteres: 5000 aceita, 5001 recusa sem gravar nada.
    T7 escape na exibição (lançamento e ficha 360°).
    T8 leitor da ficha: a observação geral aparece por etapa.
    T9 ``ConselhoResposta.observacao`` permanece NULL (coluna sem uso).
    T10 caracterização do GET: ele cria as cascas de ``ConselhoClasse`` por
        aluno sem salvar (comportamento existente; reportado no AJ19).
"""

import re

import pytest
from _helpers import login_as
from test_conselho_oferta import _enturma, _perguntas, _setup

from app import db
from app.models import ConselhoClasse, ConselhoResposta, User
from app.models.enums import EtapaConselho

_URL_LANCAMENTO = (
    "/conselho/lancamento?turma={turma}&etapa={etapa}&oferta_sel={oferta}"
)

_OBS_TA = re.compile(
    r'<textarea\b[^>]*name="obs_(\d+)"[^>]*>(.*?)</textarea>', re.S
)


# ---------------------------------------------------------------------------
# Semente / helpers locais
# ---------------------------------------------------------------------------

def _cenario(app, *, role="admin", ofertas=1):
    """Turma com 2 alunos enturmados + uma pergunta ALUNO e uma TURMA.

    Com ``ofertas=2`` cada aluno fica numa oferta distinta (para o teste de
    isolamento por oferta); com 1 oferta ambos ficam nela.
    """
    ids = _setup(app, ofertas=ofertas, role=role)
    # Perfis não-globais (pedagógico, secretaria, serviço social) precisam de
    # unidade no usuário: `get_unidade_id` ignora a sessão para eles.
    with app.app_context():
        usuario = db.session.get(User, ids["user_id"])
        usuario.unidade_id = ids["un_a"]
        db.session.commit()
    _enturma(app, ids, "aluno_a", oferta_idx=0)
    _enturma(app, ids, "aluno_b", oferta_idx=1 if ofertas > 1 else 0)
    p_aluno, p_turma = _perguntas(app)
    ids["p_aluno"] = p_aluno
    ids["p_turma"] = p_turma
    return ids


def _login(client, ids, role):
    # O professor precisa ser o professor DA OFERTA (G1/P2); os demais usam o
    # usuário semeado com o papel pedido.
    if role == "professor":
        login_as(client, ids["prof"], ids["un_a"])
    else:
        login_as(client, ids["user_id"], ids["un_a"])


def _url(ids, *, etapa="INICIAL", oferta_idx=0):
    return _URL_LANCAMENTO.format(
        turma=ids["turma"], etapa=etapa, oferta=ids["ofertas"][oferta_idx]
    )


def _post(client, ids, *, etapa="INICIAL", oferta_idx=0, campos=None):
    data = {
        "turma_id": str(ids["turma"]),
        "etapa": etapa,
        "turma_curso_id": str(ids["ofertas"][oferta_idx]),
    }
    data.update(campos or {})
    return client.post("/conselho/salvar", data=data)


def _corpo(resposta):
    return resposta.data.decode("utf-8")


def _observacoes(corpo):
    """``{aluno_id (str): texto}`` dos textareas ``obs_<aluno>``."""
    return {a: texto for a, texto in _OBS_TA.findall(corpo)}


# ---------------------------------------------------------------------------
# T1 — GET: UM campo de observação por aluno
# ---------------------------------------------------------------------------

def test_t1_get_tem_uma_observacao_por_aluno_e_nenhuma_por_pergunta(client, app):
    ids = _cenario(app)
    _login(client, ids, "admin")

    corpo = _corpo(client.get(_url(ids)))
    obs = _observacoes(corpo)

    assert set(obs) == {str(ids["aluno_a"]), str(ids["aluno_b"])}, (
        "cada aluno precisa de exatamente UM textarea obs_<aluno>"
    )
    assert all(texto == "" for texto in obs.values())

    # O campo por pergunta foi removido.
    assert f'name="obs_{ids["aluno_a"]}_{ids["p_aluno"]}"' not in corpo
    assert f'name="obs_{ids["aluno_b"]}_{ids["p_aluno"]}"' not in corpo

    # O rótulo e o limite de caracteres estão no controle novo.
    assert "Observações e informações adicionais" in corpo
    assert corpo.count("Observações e informações adicionais") == 2
    assert 'maxlength="5000"' in corpo


# ---------------------------------------------------------------------------
# T2 — gravação/leitura por aluno
# ---------------------------------------------------------------------------

def test_t2_post_grava_e_get_devolve_observacao_por_aluno(client, app):
    ids = _cenario(app)
    _login(client, ids, "admin")

    texto_a = "Parecer geral da Ana"
    texto_b = "Parecer geral do Beto"
    chave_a = f"{ids['aluno_a']}_{ids['p_aluno']}"
    r = _post(client, ids, campos={
        f"resp_{chave_a}": "Sempre",
        f"obs_{ids['aluno_a']}": texto_a,
        f"obs_{ids['aluno_b']}": texto_b,
    })
    assert r.status_code == 302

    with app.app_context():
        a = ConselhoClasse.query.filter_by(
            aluno_id=ids["aluno_a"], etapa=EtapaConselho.INICIAL,
        ).one()
        b = ConselhoClasse.query.filter_by(
            aluno_id=ids["aluno_b"], etapa=EtapaConselho.INICIAL,
        ).one()
        assert a.observacao == texto_a
        assert b.observacao == texto_b
        # A resposta foi gravada e a observação NÃO vive mais nela.
        resposta = ConselhoResposta.query.filter_by(
            aluno_id=ids["aluno_a"], pergunta_id=ids["p_aluno"],
        ).one()
        assert resposta.resposta == "Sempre"
        assert resposta.observacao is None

    obs = _observacoes(_corpo(client.get(_url(ids))))
    assert obs[str(ids["aluno_a"])] == texto_a
    assert obs[str(ids["aluno_b"])] == texto_b


# ---------------------------------------------------------------------------
# T3 — aluno sem observação
# ---------------------------------------------------------------------------

def test_t3_aluno_sem_observacao_fica_vazio_e_nao_afeta_o_outro(client, app):
    ids = _cenario(app)
    _login(client, ids, "admin")

    r = _post(client, ids, campos={f"obs_{ids['aluno_a']}": "Só a Ana tem texto"})
    assert r.status_code == 302

    # O GET cria a casca do Beto; a observação dele fica vazia.
    obs = _observacoes(_corpo(client.get(_url(ids))))
    assert obs[str(ids["aluno_a"])] == "Só a Ana tem texto"
    assert obs[str(ids["aluno_b"])] == ""

    with app.app_context():
        b = ConselhoClasse.query.filter_by(
            aluno_id=ids["aluno_b"], etapa=EtapaConselho.INICIAL,
        ).one()
        assert b.observacao in (None, "")


# ---------------------------------------------------------------------------
# T4 — isolamento aluno × etapa × oferta
# ---------------------------------------------------------------------------

def test_t4_observacao_e_isolada_por_etapa(client, app):
    ids = _cenario(app)
    _login(client, ids, "admin")

    _post(client, ids, campos={f"obs_{ids['aluno_a']}": "Texto do inicial"})
    _post(
        client, ids, etapa="PERCURSO",
        campos={f"obs_{ids['aluno_a']}": "Texto do percurso"},
    )

    with app.app_context():
        inicial = ConselhoClasse.query.filter_by(
            aluno_id=ids["aluno_a"], etapa=EtapaConselho.INICIAL,
        ).one()
        percurso = ConselhoClasse.query.filter_by(
            aluno_id=ids["aluno_a"], etapa=EtapaConselho.PERCURSO,
        ).one()
        assert inicial.observacao == "Texto do inicial"
        assert percurso.observacao == "Texto do percurso"

    obs_ini = _observacoes(_corpo(client.get(_url(ids, etapa="INICIAL"))))
    obs_per = _observacoes(_corpo(client.get(_url(ids, etapa="PERCURSO"))))
    assert obs_ini[str(ids["aluno_a"])] == "Texto do inicial"
    assert obs_per[str(ids["aluno_a"])] == "Texto do percurso"


def test_t4_observacao_e_isolada_por_oferta(client, app):
    ids = _cenario(app, ofertas=2)
    _login(client, ids, "admin")

    r = _post(
        client, ids, oferta_idx=0,
        campos={f"obs_{ids['aluno_a']}": "Texto da oferta 1"},
    )
    assert r.status_code == 302

    with app.app_context():
        da_oferta_1 = ConselhoClasse.query.filter_by(
            aluno_id=ids["aluno_a"],
            etapa=EtapaConselho.INICIAL,
            turma_curso_id=ids["ofertas"][0],
        ).one()
        assert da_oferta_1.observacao == "Texto da oferta 1"
        # Nada foi criado na outra oferta.
        assert (
            ConselhoClasse.query.filter_by(
                turma_curso_id=ids["ofertas"][1]
            ).count()
            == 0
        )


# ---------------------------------------------------------------------------
# T5 — perfis
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("role", ["admin", "pedagogico", "professor"])
def test_t5_perfis_autorizados_gravam(client, app, role):
    ids = _cenario(app, role=role)
    _login(client, ids, role)

    r = _post(client, ids, campos={f"obs_{ids['aluno_a']}": f"Por {role}"})
    assert r.status_code == 302
    with app.app_context():
        linha = ConselhoClasse.query.filter_by(
            aluno_id=ids["aluno_a"], etapa=EtapaConselho.INICIAL,
        ).one()
        assert linha.observacao == f"Por {role}"


@pytest.mark.parametrize(
    "role", ["secretaria", "gerencia", "servico_social"]
)
def test_t5_perfis_somente_leitura_nao_gravam(client, app, role):
    ids = _cenario(app, role=role)
    _login(client, ids, role)

    r = _post(client, ids, campos={f"obs_{ids['aluno_a']}": "Invasao"})
    assert r.status_code == 403
    with app.app_context():
        assert ConselhoClasse.query.count() == 0
        assert ConselhoResposta.query.count() == 0


# ---------------------------------------------------------------------------
# T6 — limite de 5000 caracteres
# ---------------------------------------------------------------------------

def test_t6_limite_de_5000_caracteres(client, app):
    ids = _cenario(app)
    _login(client, ids, "admin")

    exato = "x" * 5000
    r = _post(client, ids, campos={f"obs_{ids['aluno_a']}": exato})
    assert r.status_code == 302
    with app.app_context():
        linha = ConselhoClasse.query.filter_by(
            aluno_id=ids["aluno_a"], etapa=EtapaConselho.INICIAL,
        ).one()
        assert linha.observacao == exato
        assert len(linha.observacao) == 5000

    # 5001: recusa ANTES de qualquer mutação — nem a resposta é gravada.
    chave = f"{ids['aluno_b']}_{ids['p_aluno']}"
    r = _post(client, ids, campos={
        f"obs_{ids['aluno_b']}": "y" * 5001,
        f"resp_{chave}": "Sempre",
    })
    assert r.status_code == 302
    with app.app_context():
        assert (
            ConselhoClasse.query.filter_by(aluno_id=ids["aluno_b"]).count()
            == 0
        )
        assert (
            ConselhoResposta.query.filter_by(aluno_id=ids["aluno_b"]).count()
            == 0
        )


# ---------------------------------------------------------------------------
# T7 — escape na exibição
# ---------------------------------------------------------------------------

def test_t7_observacao_e_escapada_no_lancamento_e_na_ficha(client, app):
    ids = _cenario(app)
    _login(client, ids, "admin")

    bruto = '<script>alert("aj19")</script>'
    r = _post(client, ids, campos={f"obs_{ids['aluno_a']}": bruto})
    assert r.status_code == 302

    corpo = _corpo(client.get(_url(ids)))
    assert bruto not in corpo, "o texto gravado não pode sair como HTML cru"
    assert "&lt;script&gt;" in corpo

    ficha = _corpo(client.get(
        f"/relatorios/alunos/{ids['aluno_a']}/ficha"
        f"?turma_id={ids['turma']}&oferta_sel={ids['ofertas'][0]}"
    ))
    assert bruto not in ficha
    assert "&lt;script&gt;" in ficha


# ---------------------------------------------------------------------------
# T8 — leitor: ficha 360° por etapa
# ---------------------------------------------------------------------------

def test_t8_ficha_mostra_observacao_geral_por_etapa(client, app):
    ids = _cenario(app)
    _login(client, ids, "admin")

    _post(client, ids, campos={f"obs_{ids['aluno_a']}": "Parecer do inicial"})
    _post(
        client, ids, etapa="PERCURSO",
        campos={f"obs_{ids['aluno_a']}": "Parecer do percurso"},
    )

    corpo = _corpo(client.get(
        f"/relatorios/alunos/{ids['aluno_a']}/ficha"
        f"?turma_id={ids['turma']}&oferta_sel={ids['ofertas'][0]}"
    ))
    assert corpo.count("pt-obs-conselho") == 2, (
        "a ficha deve renderizar a observação das duas etapas preenchidas"
    )
    assert "Parecer do inicial" in corpo
    assert "Parecer do percurso" in corpo


# ---------------------------------------------------------------------------
# T9 — ConselhoResposta.observacao fica sem uso
# ---------------------------------------------------------------------------

def test_t9_conselho_resposta_observacao_nao_e_escrita(client, app):
    ids = _cenario(app)
    _login(client, ids, "admin")

    chave = f"{ids['aluno_a']}_{ids['p_aluno']}"
    r = _post(client, ids, campos={
        f"resp_{chave}": "Sempre",
        f"obs_{ids['aluno_a']}": "Observação geral",
    })
    assert r.status_code == 302

    with app.app_context():
        resposta = ConselhoResposta.query.filter_by(
            aluno_id=ids["aluno_a"], pergunta_id=ids["p_aluno"],
        ).one()
        assert resposta.resposta == "Sempre"
        assert resposta.observacao is None


# ---------------------------------------------------------------------------
# T10 — caracterização: GET cria as cascas de ConselhoClasse
# ---------------------------------------------------------------------------

def test_t10_get_cria_cascas_de_conselho_por_aluno(client, app):
    ids = _cenario(app)
    _login(client, ids, "admin")

    assert client.get(_url(ids)).status_code == 200

    with app.app_context():
        linhas = ConselhoClasse.query.filter_by(
            turma_curso_id=ids["ofertas"][0],
            etapa=EtapaConselho.INICIAL,
        ).all()
        assert len(linhas) == 2
        assert {linha.aluno_id for linha in linhas} == {
            ids["aluno_a"], ids["aluno_b"],
        }
        # Efeito colateral atual: cascas vazias, gravadas sem conteúdo.
        assert all(linha.observacao is None for linha in linhas)
        assert ConselhoResposta.query.count() == 0
