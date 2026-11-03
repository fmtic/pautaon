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
    ("admin", "individual"): "1c013cd832d641d87bfa1e4f777d72235c8ec328ec4a0856a1a171885bbb04a9",
    ("admin", "coletiva"): "6473f3dab8a56bf38b00692fab76586ed6e6ebcf292847263b9b19e1acc3bd0d",
    ("pedagogico", "individual"): "4b43320b3e39d0790f9b970a05fbba7bd161746f89aac8c040f3988d834909c6",
    ("pedagogico", "coletiva"): "de2bd75798f5cbcaab1c595d2e6b9a6ce34357cfebd3d7e861f3a1f1fb663dc1",
    ("professor", "individual"): "3309d45b117e33953a0be53da2d4d1b6e6b27e9b35ba81c4125ee735b8225553",
    ("professor", "coletiva"): "0f9b05e95fc2c3e0ce9e3a50d7011a656231c95ab58eb90a082d085f4fe065c4",
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
