"""ETAPA D5.3 — encerramento e contagens do conselho por oferta.

Regras cobertas (docs/D5_0_desenho.md §2.6 + D5.3):
    - Encerramento MANUAL e por OFERTA (`TurmaCurso.conselho_concluido`,
      via `alternar_conselho`).
    - A turma NÃO tem coluna de conclusão (removida na D5.5) nem ponte: a
      visão da turma é lida pelas contagens e pelo painel por oferta
      (`contar_ofertas_conselho()` e `ofertas_do_painel_conselho()`).
    - Turma sem oferta ativa não abre conselho e NÃO entra nas contagens.
    - Nenhum leitor lê `Turma.conselho_concluido`: a coluna foi REMOVIDA na
      D5.5 e o encerramento existe só na oferta.

Um usuário por teste: cada teste semeia o cenário via `_setup` da D5.2 e
faz um único login.
"""
# ruff: noqa: F811 — os fixtures `app`/`client` são reaproveitados da D5.2
# e seus nomes coincidem com os parâmetros dos testes.

import re
from datetime import date

from _helpers import nova_inscricao, nova_oferta
from test_conselho_oferta import (  # noqa: F401  (fixtures reaproveitadas)
    _enturma,
    _loga,
    _setup,
    app,
    client,
)

from app.database import db
from app.models import Curso, PeriodoLetivo, Turma, TurmaCurso, Unidade
from app.services.turma_curso import (
    contar_ofertas_conselho,
    ofertas_do_painel_conselho,
)
from app.utils.logica import calcular_metricas_conselho

# ---------------------------------------------------------------------------
# Helpers locais
# ---------------------------------------------------------------------------

def _concluir(app, oferta_ids, flags):
    with app.app_context():
        for oferta_id, flag in zip(oferta_ids, flags, strict=True):
            db.session.get(TurmaCurso, oferta_id).conselho_concluido = flag
        db.session.commit()


def _turma_extra(app, ids, *, nome, unidade_id, com_oferta=True):
    """Cria uma turma extra (com ou sem oferta ativa) e devolve o id."""
    with app.app_context():
        turma = Turma(
            nome=nome, turno="Tarde", data_inicio=None, data_fim=None,
            unidade_id=unidade_id, ativo=True,
        )
        db.session.add(turma)
        db.session.flush()
        if com_oferta:
            curso = Curso(nome=f"Curso {nome}", unidade_id=unidade_id, ativo=True)
            db.session.add(curso)
            db.session.flush()
            nova_oferta(turma.id, curso.id, unidade_id)
        db.session.commit()
        return turma.id


def _unidade_b_com_turma(app, ids):
    """Unidade B com uma turma e uma oferta (pendente). Devolve os ids."""
    with app.app_context():
        un_b = Unidade(nome="Unidade B", ativo=True)
        db.session.add(un_b)
        db.session.flush()
        turma_b = Turma(
            nome="Turma B", turno="Manhã",
            unidade_id=un_b.id, ativo=True,
        )
        db.session.add(turma_b)
        db.session.flush()
        curso_b = Curso(nome="Curso B", unidade_id=un_b.id, ativo=True)
        db.session.add(curso_b)
        db.session.flush()
        oferta_b = nova_oferta(turma_b.id, curso_b.id, un_b.id)
        # O aluno da unidade A participa da turma B só para o certificado.
        nova_inscricao(ids["aluno_a"], turma_b.id, oferta_b.id)
        db.session.commit()
        return {
            "un_b": un_b.id,
            "turma_b": turma_b.id,
            "oferta_b": oferta_b.id,
        }


def _painel_html(client):
    resposta = client.get("/conselho")
    assert resposta.status_code == 200
    return resposta.data.decode("utf-8")


# ---------------------------------------------------------------------------
# Encerramento por oferta nas contagens e no painel
# ---------------------------------------------------------------------------

def test_derivacao_uma_oferta(app):
    ids = _setup(app, ofertas=1)
    with app.app_context():
        assert contar_ofertas_conselho(ids["un_a"]) == (0, 1)
        assert [o["concluida"] for o in ofertas_do_painel_conselho(ids["un_a"])] == [False]

    _concluir(app, ids["ofertas"], [True])
    with app.app_context():
        assert contar_ofertas_conselho(ids["un_a"]) == (1, 1)
        assert [o["concluida"] for o in ofertas_do_painel_conselho(ids["un_a"])] == [True]


def test_derivacao_duas_ofertas_uma_pendente(app):
    ids = _setup(app, ofertas=2)

    _concluir(app, ids["ofertas"], [True, False])
    with app.app_context():
        assert contar_ofertas_conselho(ids["un_a"]) == (1, 2)
        concluidas = [o["concluida"] for o in ofertas_do_painel_conselho(ids["un_a"])]
        assert sorted(concluidas) == [False, True]

    _concluir(app, ids["ofertas"], [True, True])
    with app.app_context():
        assert contar_ofertas_conselho(ids["un_a"]) == (2, 2)
        assert all(o["concluida"] for o in ofertas_do_painel_conselho(ids["un_a"]))


def test_turma_sem_oferta_ativa_nao_conclui_nem_conta(app):
    ids = _setup(app, ofertas=0)
    with app.app_context():
        assert contar_ofertas_conselho(ids["un_a"]) == (0, 0)
        # Turma sem oferta ativa também não aparece no painel por oferta.
        assert ofertas_do_painel_conselho(ids["un_a"]) == []


def test_oferta_inativa_ignorada(app):
    ids = _setup(app, ofertas="1+1i")
    _concluir(app, ids["ofertas"], [True])

    with app.app_context():
        # A oferta inativa está pendente, mas não entra em nada.
        assert db.session.get(TurmaCurso, ids["oferta_inativa"]).conselho_concluido is False
        assert contar_ofertas_conselho(ids["un_a"]) == (1, 1)
        # O painel só lista a oferta ativa — a inativa fica de fora.
        painel = ofertas_do_painel_conselho(ids["un_a"])
        assert [o["oferta"].id for o in painel] == [ids["ofertas"][0]]
        assert [o["concluida"] for o in painel] == [True]


# ---------------------------------------------------------------------------
# Painel por oferta
# ---------------------------------------------------------------------------

def test_painel_uma_linha_por_oferta_status_vem_da_oferta(app, client):
    # D5.5: não existe mais flag da turma — o status de cada linha vem DA OFERTA.
    ids = _setup(app, ofertas=2)

    _loga(client, ids, unidade_id=ids["un_a"])
    body = _painel_html(client)

    assert "Curso 1" in body and "Curso 2" in body
    assert body.count('badge bg-warning text-dark">Pendente') == 2
    assert 'badge bg-success">Concluído' not in body
    assert body.count("Encerrar conselho da oferta") == 2
    for oferta_id in ids["ofertas"]:
        assert f"oferta_sel={oferta_id}" in body


def test_painel_mostra_concluido_quando_todas_concluidas(app, client):
    ids = _setup(app, ofertas=2)
    _concluir(app, ids["ofertas"], [True, True])

    _loga(client, ids, unidade_id=ids["un_a"])
    body = _painel_html(client)

    assert body.count('badge bg-success">Concluído') == 2
    assert 'badge bg-warning text-dark">Pendente' not in body
    assert body.count("Reabrir conselho da oferta") == 2


def test_painel_turma_sem_oferta_nao_aparece(app, client):
    ids = _setup(app, ofertas=1)
    _turma_extra(app, ids, nome="Turma Sem Oferta", unidade_id=ids["un_a"],
                 com_oferta=False)
    _loga(client, ids, unidade_id=ids["un_a"])

    body = _painel_html(client)
    assert "Turma D52" in body
    assert "Turma Sem Oferta" not in body
    assert "sem curso (oferta) ativa" in body


# ---------------------------------------------------------------------------
# turmas_pendentes → ofertas pendentes
# ---------------------------------------------------------------------------

def test_informacoes_conta_ofertas_pendentes(app, client):
    ids = _setup(app, ofertas=2)
    _concluir(app, ids["ofertas"], [True, False])
    _turma_extra(app, ids, nome="Turma Sem Oferta", unidade_id=ids["un_a"],
                 com_oferta=False)
    _loga(client, ids, unidade_id=ids["un_a"])

    resposta = client.get("/informacoes")
    assert resposta.status_code == 200
    body = resposta.data.decode("utf-8")

    assert "Ofertas Pendentes" in body
    pendentes = re.search(r'display-4 fw-bold">\s*(\d+)', body)
    assert pendentes and pendentes.group(1) == "1"


# ---------------------------------------------------------------------------
# Métricas do relatório geral
# ---------------------------------------------------------------------------

def test_metricas_contam_ofertas_e_respeitam_unidade(app):
    ids = _setup(app, ofertas=2)
    _concluir(app, ids["ofertas"], [True, False])
    _turma_extra(app, ids, nome="Turma Sem Oferta", unidade_id=ids["un_a"],
                 com_oferta=False)
    un_b = _unidade_b_com_turma(app, ids)

    with app.app_context():
        metricas_a = calcular_metricas_conselho(ids["un_a"])
        metricas_b = calcular_metricas_conselho(un_b["un_b"])
        metricas_global = calcular_metricas_conselho()

    assert (metricas_a["turmas_concluidas"], metricas_a["total_turmas"]) == (1, 2)
    assert (metricas_b["turmas_concluidas"], metricas_b["total_turmas"]) == (0, 1)
    assert (metricas_global["turmas_concluidas"],
            metricas_global["total_turmas"]) == (1, 3)


# ---------------------------------------------------------------------------
# alternar_conselho por oferta refletindo no painel
# ---------------------------------------------------------------------------

def test_alternar_por_oferta_reflete_no_painel(app, client):
    ids = _setup(app, ofertas=2)
    _loga(client, ids, unidade_id=ids["un_a"])

    resposta = client.post(
        f"/turma/alternar-conselho/{ids['turma']}",
        data={"turma_curso_id": str(ids["ofertas"][0])},
    )
    assert resposta.status_code == 302

    body = _painel_html(client)
    assert body.count('badge bg-success">Concluído') == 1
    assert body.count('badge bg-warning text-dark">Pendente') == 1

    client.post(
        f"/turma/alternar-conselho/{ids['turma']}",
        data={"turma_curso_id": str(ids["ofertas"][1])},
    )
    body = _painel_html(client)
    assert body.count('badge bg-success">Concluído') == 2


# ---------------------------------------------------------------------------
# periodos.py: certificado usa o encerramento derivado
# ---------------------------------------------------------------------------

def test_certificado_usa_encerramento_derivado(app, client):
    ids = _setup(app, ofertas=1)
    _enturma(app, ids, "aluno_a")
    # Oferta pendente: o certificado tem de refletir o derivado das ofertas
    # (D5.5: não há mais flag da turma para “mentir”). O período é criado aqui
    # porque a semente da D5.2 não o vincula à turma (periodo.id em flush).
    with app.app_context():
        turma = db.session.get(Turma, ids["turma"])
        periodo = PeriodoLetivo(
            nome="Periodo Certificado",
            data_inicio=date(2026, 2, 2), data_fim=date(2026, 6, 30),
            unidade_id=ids["un_a"], ativo=True,
        )
        db.session.add(periodo)
        db.session.flush()
        turma.periodo_letivo_id = periodo.id
        periodo_id = periodo.id
        db.session.commit()

    _loga(client, ids, unidade_id=ids["un_a"])

    resposta = client.get(f"/periodo-letivo/relatorio/{periodo_id}")
    assert resposta.status_code == 200
    body = resposta.data.decode("utf-8")
    assert 'title="Pendente"' in body
    assert 'title="Concluído"' not in body

    _concluir(app, ids["ofertas"], [True])
    body = client.get(f"/periodo-letivo/relatorio/{periodo_id}").data.decode("utf-8")
    assert 'title="Concluído"' in body


# ---------------------------------------------------------------------------
# Isolamento por unidade
# ---------------------------------------------------------------------------

def test_isolamento_leitura_filtrada_e_alternar_403(app, client):
    ids = _setup(app, ofertas=1)
    un_b = _unidade_b_com_turma(app, ids)
    _loga(client, ids, unidade_id=ids["un_a"])

    # Escrita de outra unidade → 403.
    resposta = client.post(
        f"/turma/alternar-conselho/{un_b['turma_b']}",
        data={"turma_curso_id": str(un_b["oferta_b"])},
    )
    assert resposta.status_code == 403

    # Leitura com contexto da unidade B não mostra ofertas da A.
    _loga(client, ids, unidade_id=un_b["un_b"])
    body = _painel_html(client)
    assert "Turma D52" not in body
    assert "Turma B" in body

    resposta = client.get("/informacoes")
    body = resposta.data.decode("utf-8")
    pendentes = re.search(r'display-4 fw-bold">\s*(\d+)', body)
    assert pendentes and pendentes.group(1) == "1"


def test_admin_sem_unidade_nao_alterna(app, client):
    ids = _setup(app, ofertas=1)
    _loga(client, ids)  # admin em Visão Global

    resposta = client.post(
        f"/turma/alternar-conselho/{ids['turma']}",
        data={"turma_curso_id": str(ids["ofertas"][0])},
    )
    assert resposta.status_code == 403

    with app.app_context():
        assert db.session.get(TurmaCurso, ids["ofertas"][0]).conselho_concluido is False
