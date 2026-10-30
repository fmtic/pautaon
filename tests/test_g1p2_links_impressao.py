# ruff: noqa: F811
"""G1-4: links de impressão sempre com a oferta explícita (nenhum cai em 403).

Prova em HTML duas coisas:

- `lancar.html`: enquanto `exigir_escolha` (2+ ofertas sem curso selecionado)
  nenhum botão/link de impressão é ofertado; com 1 oferta ativa (ou escolha
  feita) todo href de `imprimir-pauta` carrega `turma_curso` e nenhuma URL
  vazia/`None` escapa.
- `detalhe.html`: com exatamente 1 oferta ativa os links mensal e completa
  passam a oferta; com 0 ofertas vale o legado por turma (sem parâmetro).

antigo × novo × motivo: antes da E3 os links dos dois templates podiam sair
sem `turma_curso` — na rota isso caía em redirecionamento/403 para o professor
(G1 item 4). Agora a oferta é explícita sempre que existe.
"""

import re
from datetime import date, time

from _helpers import login_as, nova_oferta

from app import db
from app.models import Curso, PeriodoLetivo, Turma, Unidade, User

GRADE = dict(
    dias_semana="Segunda, Terça, Quarta, Quinta, Sexta",
    hora_inicio=time(8),
    hora_fim=time(10),
)

# Todo href de imprimir-pauta (dropdown dos dois templates).
_HREF_PAUTA = re.compile(r'href="[^"]*/turma/\d+/imprimir-pauta[^"]*"')


def _seed(app, *, ofertas=1, ofertas_ativas=None):
    """Unidade + pedagógico + turma com `ofertas` ofertas ativas (ou o par
    `(ativas, inativas)` em `ofertas_ativas`) e grade uniforme."""
    with app.app_context():
        un = Unidade(nome="Unidade G4", ativo=True)
        db.session.add(un)
        db.session.flush()

        resp = User(name="Coord G4", email="coord.g4@x.com",
                    role="pedagogico", first_login=False, unidade_id=un.id)
        prof = User(name="Prof G4", email="prof.g4@x.com",
                    role="professor", first_login=False, unidade_id=un.id)
        db.session.add_all([resp, prof])
        db.session.flush()

        periodo = PeriodoLetivo(
            nome="P G4", data_inicio=date(2026, 1, 1), data_fim=date(2026, 12, 31),
            unidade_id=un.id, ativo=True,
        )
        db.session.add(periodo)
        db.session.flush()

        turma = Turma(
            nome="Turma G4", unidade_id=un.id, ativo=True,
            periodo_letivo_id=periodo.id,
            data_inicio=periodo.data_inicio, data_fim=periodo.data_fim,
        )
        db.session.add(turma)
        db.session.flush()

        # UNIQUE (turma_id, curso_id): um curso distinto por oferta.
        n_ativas, n_inativas = (
            ofertas_ativas if ofertas_ativas is not None else (ofertas, 0)
        )
        ids = []
        for k in range(n_ativas + n_inativas):
            curso = Curso(nome=f"Curso G4 {k}", unidade_id=un.id, ativo=True)
            db.session.add(curso)
            db.session.flush()
            oferta = nova_oferta(
                turma.id, curso.id, un.id,
                principal=(k == 0), ativo=(k < n_ativas),
                professor_id=prof.id, **GRADE,
            )
            ids.append(oferta.id)

        db.session.commit()
        return {
            "un": un.id, "resp": resp.id, "prof": prof.id,
            "turma": turma.id, "ofertas": ids, "ativas": ids[:n_ativas],
        }


def _hrefs_pauta(html):
    return _HREF_PAUTA.findall(html)


# ---------------------------------------------------------------------------
# lançar.html — exigir_escolha esconde; oferta única/Escolhida explícita
# ---------------------------------------------------------------------------

def test_lancar_uma_oferta_todo_link_leva_a_oferta(app, client):
    ids = _seed(app, ofertas=1)
    login_as(client, ids["resp"], ids["un"])

    corpo = client.get(f"/frequencia?turma_id={ids['turma']}")
    assert corpo.status_code == 200
    html = corpo.get_data(as_text=True)
    assert "Imprimir Pauta" in html

    hrefs = _hrefs_pauta(html)
    assert hrefs, "dropdown deve ofertar links de impressão"
    for href in hrefs:
        assert f"turma_curso={ids['ativas'][0]}" in href
        assert "turma_curso=None" not in href


def test_lancar_duas_ofertas_sem_escolha_nao_oferta_impressao(app, client):
    ids = _seed(app, ofertas=2)
    login_as(client, ids["resp"], ids["un"])

    html = client.get(f"/frequencia?turma_id={ids['turma']}").get_data(as_text=True)
    # Botão escondido enquanto o curso não foi escolhido (exigir_escolha).
    assert "Imprimir Pauta" not in html
    assert _hrefs_pauta(html) == []


def test_lancar_duas_ofertas_com_escolha_link_explícito(app, client):
    ids = _seed(app, ofertas=2)
    login_as(client, ids["resp"], ids["un"])

    escolhida = ids["ativas"][1]
    html = client.get(
        f"/frequencia?turma_id={ids['turma']}&turma_curso={escolhida}"
    ).get_data(as_text=True)
    hrefs = _hrefs_pauta(html)
    assert hrefs
    for href in hrefs:
        assert f"turma_curso={escolhida}" in href


# ---------------------------------------------------------------------------
# detalhe.html — 1 oferta explícita; 0 ofertas = legado por turma
# ---------------------------------------------------------------------------

def test_detalhe_uma_oferta_todo_link_leva_a_oferta(app, client):
    ids = _seed(app, ofertas=1)
    login_as(client, ids["resp"], ids["un"])

    resposta = client.get(f"/turma/{ids['turma']}")
    assert resposta.status_code == 200
    html = resposta.get_data(as_text=True)

    hrefs = _hrefs_pauta(html)
    assert hrefs
    for href in hrefs:
        assert f"turma_curso={ids['ativas'][0]}" in href
        assert "turma_curso=None" not in href


def test_detalhe_duas_ofertas_um_link_por_oferta(app, client):
    ids = _seed(app, ofertas=2)
    login_as(client, ids["resp"], ids["un"])

    html = client.get(f"/turma/{ids['turma']}").get_data(as_text=True)
    hrefs = _hrefs_pauta(html)
    # Um link por oferta ativa, cada um com a sua — nenhum genérico.
    assert len(hrefs) == 2
    for oferta_id in ids["ativas"]:
        assert any(f"turma_curso={oferta_id}" in href for href in hrefs)
    for href in hrefs:
        assert "turma_curso=None" not in href


def test_detalhe_sem_oferta_link_legado_sem_parametro(app, client):
    """0 ofertas ativas: impressão legacy por turma segue sem `turma_curso`
    (e a rota aceita esse caminho — não é caso de 403)."""
    ids = _seed(app, ofertas_ativas=(0, 1))
    login_as(client, ids["resp"], ids["un"])

    html = client.get(f"/turma/{ids['turma']}").get_data(as_text=True)
    hrefs = _hrefs_pauta(html)
    assert hrefs
    assert all("turma_curso=" not in href for href in hrefs)
