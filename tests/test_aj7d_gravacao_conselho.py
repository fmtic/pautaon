"""AJ7-D — somente admin, pedagógico e professor da oferta podem gravar."""

import hashlib
import json
import re

import pytest

from _helpers import login_as
from app import db
from app.models import LogAcao, TurmaCurso, User
from test_aj6b7_complemento import _contar_tabelas
from test_conselho_oferta import _enturma, _perguntas, _setup

_ACAO_LOG_GESTOR = "Alteração de conselho (gestor)"

# SHA-256 do HTML completo antes da alteração, após normalizar só os tokens
# CSRF. Um hash por papel e tela trava a preservação do HTML autorizado.
_GOLDEN_HTML = {
    # Updated golden HTML hashes after UI changes.
    # AJ21: "Ver respostas" (admin/pedagogico/secretaria) e data-aluno-id
    # mudaram lancamento/turma_aval; hashes regravados com so o CSRF trocado.
    # AJ21-B: o "Ver respostas" da avaliacao coletiva passou a apontar para a
    # rota unica; so os hashes de admin/pedagogico na coletiva mudaram.
    # AJ19: hashes do individual mudaram SÓ na região da observação (o
    # textarea por pergunta virou UM `obs_<aluno>` no fim do card). A
    # coletiva permaneceu idêntica.
    ("admin", "individual"): "1c4f24b029c43c26713f3254e521bf4eb72a228ccef4b59208f9aeeb017f6844",
    ("admin", "coletiva"): "9bb491a1ba6a86b7b0d9ee36ee35c0c8f8824b3e2811680c8a2659271ae4a496",
    ("pedagogico", "individual"): "805c6c8877192309ebde2f8e3833a49e7f34d8c05e8ed32588a09cd662008cfe",
    ("pedagogico", "coletiva"): "46e25a80ea80f50665b65c4d491248e782575bc833f66bd1261c6db66abe2817",
    ("professor", "individual"): "e0e2f376de3388148b5fe98883ff6308a16aee24c80aa8a38cd47a61df754d44",
    ("professor", "coletiva"): "3ff0346bb7031c036e75d42ddeb6ca30938afed774a6c5e2317916e26e7a862c",
}

_ROTAS = ("individual", "coletiva")


def _cenario(app):
    ids = _setup(app, ofertas=1)
    _enturma(app, ids, "aluno_a")
    ids["pergunta_aluno"], ids["pergunta_turma"] = _perguntas(app)

    with app.app_context():
        ids["usuarios"] = {
            "admin": ids["user_id"],
            "professor": ids["prof"],
        }
        for papel in (
            "pedagogico",
            "professor_alheio",
            "gerencia",
            "secretaria",
            "servico_social",
        ):
            role = "professor" if papel == "professor_alheio" else papel
            usuario = User(
                name=f"AJ7D {papel}",
                email=f"aj7d.{papel}@example.test",
                role=role,
                first_login=False,
                unidade_id=ids["un_a"],
            )
            usuario.set_password("SenhaLocal!123")
            db.session.add(usuario)
            db.session.flush()
            ids["usuarios"][papel] = usuario.id
        db.session.commit()
    return ids


def _login(client, ids, papel):
    if papel is not None:
        login_as(client, ids["usuarios"][papel], ids["un_a"])


def _post(client, ids, rota):
    if rota == "individual":
        return client.post(
            "/conselho/salvar",
            data={
                "turma_id": ids["turma"],
                "turma_curso_id": ids["ofertas"][0],
                "etapa": "INICIAL",
                f"resp_{ids['aluno_a']}_{ids['pergunta_aluno']}": "Participa bem",
            },
        )
    return client.post(
        f"/turma/{ids['turma']}/avaliacao?etapa=INICIAL",
        data={
            "turma_curso_id": ids["ofertas"][0],
            f"resp_turma_{ids['pergunta_turma']}": "A turma evoluiu bem",
        },
    )


def _get(client, ids, rota):
    if rota == "individual":
        return client.get(
            f"/conselho/lancamento?turma={ids['turma']}"
            f"&etapa=INICIAL&oferta_sel={ids['ofertas'][0]}"
        )
    return client.get(
        f"/turma/{ids['turma']}/avaliacao?etapa=INICIAL"
        f"&oferta_sel={ids['ofertas'][0]}"
    )


@pytest.mark.parametrize("rota", _ROTAS)
@pytest.mark.parametrize(
    ("papel", "esperado"),
    [
        ("admin", 302),
        ("pedagogico", 302),
        ("professor", 302),
        ("professor_alheio", 403),
        ("gerencia", 403),
        ("secretaria", 403),
        ("servico_social", 403),
        (None, 302),
    ],
)
def test_matriz_post_por_papel_sem_escrita_na_negacao(
    app, client, monkeypatch, papel, esperado, rota,
):
    ids = _cenario(app)
    _login(client, ids, papel)
    antes = _contar_tabelas(app)

    if papel in {"gerencia", "secretaria", "servico_social"}:
        def leitura_de_recurso_proibida(*args, **kwargs):
            pytest.fail("papel sem gravação consultou recurso antes do 403")

        monkeypatch.setattr(
            "app.conselho.db.get_or_404",
            leitura_de_recurso_proibida,
        )

    resposta = _post(client, ids, rota)
    assert resposta.status_code == esperado

    if papel is None:
        assert resposta.headers["Location"].split("?", 1)[0].endswith("/login")

    if esperado != 302 or papel is None:
        assert _contar_tabelas(app) == antes
        return

    with app.app_context():
        if rota == "individual":
            logs = LogAcao.query.filter_by(acao=_ACAO_LOG_GESTOR).all()
            if papel in {"admin", "pedagogico"}:
                assert len(logs) == 1
                assert logs[0].usuario_id == ids["usuarios"][papel]
            else:
                assert logs == []
        else:
            oferta = db.session.get(TurmaCurso, ids["ofertas"][0])
            dados = json.loads(oferta.avaliacao_inicial)
            assert dados[str(ids["pergunta_turma"])] == "A turma evoluiu bem"


@pytest.mark.parametrize("rota", _ROTAS)
@pytest.mark.parametrize(
    ("papel", "esperado"),
    [
        ("admin", 200),
        ("pedagogico", 200),
        ("professor", 200),
        ("professor_alheio", 403),
        ("gerencia", 200),
        ("secretaria", 200),
        ("servico_social", 200),
        (None, 302),
    ],
)
def test_get_permanece_disponivel_e_esconde_salvar_so_de_nao_gravadores(
    app, client, papel, esperado, rota,
):
    ids = _cenario(app)
    _login(client, ids, papel)

    resposta = _get(client, ids, rota)
    assert resposta.status_code == esperado
    if papel is None:
        assert resposta.headers["Location"].split("?", 1)[0].endswith("/login")
    if esperado != 200:
        return

    html = resposta.data.decode("utf-8")
    pode_gravar = papel in {"admin", "pedagogico", "professor"}
    texto_botao = "Salvar Tudo" if rota == "individual" else "Salvar Avaliação"
    assert (texto_botao in html) is pode_gravar

    if pode_gravar:
        html = re.sub(
            r'(<meta name="csrf-token" content=")[^"]*(")',
            r"\1TOKEN\2",
            html,
        )
        html = re.sub(
            r'(name="csrf_token"[^>]*value=")[^"]*(")',
            r"\1TOKEN\2",
            html,
        )
        assert hashlib.sha256(html.encode("utf-8")).hexdigest() == (
            _GOLDEN_HTML[(papel, rota)]
        )
