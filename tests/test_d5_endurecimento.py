"""ETAPA D5.5 — endurecimento do conselho por oferta (schema + código + ficha).

Regras cobertas (docs/D5_0_desenho.md §3.3, D5.5):
    - `conselho_classe.turma_curso_id` é NOT NULL: conselho sem oferta deixou
      de existir e o próprio banco recusa (IntegrityError).
    - `uix_conselho_oferta` é a UNIQUE plena: duplicata na MESMA oferta/etapa é
      recusada; o mesmo aluno em 2 ofertas da mesma turma é permitido.
    - `turma.conselho_concluido` foi REMOVIDA — a flag vive só na oferta.
    - `alternar_conselho` alterna a oferta e NÃO escreve na turma.
    - `avaliar_turma` grava cada etapa no campo certo da oferta via
      `ETAPA_PARA_CAMPO_AVALIACAO`.
    - Ficha 360°: aluno com 2+ inscrições na mesma turma escolhe a oferta por
      `?oferta_sel=` (validado) e o template mostra o seletor "Turma — Curso".

Um usuário por teste (T1 §5.6): a semente vem de `_setup` da D5.2 e cada teste
faz no máximo um login.
"""
# ruff: noqa: F811 — os fixtures `app`/`client` são reaproveitados da D5.2
# e seus nomes coincidem com os parâmetros dos testes.

import json

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from test_conselho_oferta import _enturma, _loga, _setup

from app.database import db
from app.models import (
    ConselhoClasse,
    PerguntaConselho,
    Turma,
    TurmaCurso,
)
from app.models.enums import (
    ETAPA_PARA_CAMPO_AVALIACAO,
    EtapaConselho,
)


def _conselho(ids, aluno_id, turma_curso_id, etapa=EtapaConselho.INICIAL):
    return ConselhoClasse(
        turma_id=ids["turma"], aluno_id=aluno_id, etapa=etapa,
        turma_curso_id=turma_curso_id, unidade_id=ids["un_a"],
    )


# ---------------------------------------------------------------------------
# 1. Conselho sem oferta → recusado pelo banco
# ---------------------------------------------------------------------------

def test_conselho_sem_oferta_levanta_integrity_error(app):
    ids = _setup(app, ofertas=1)
    with app.app_context():
        db.session.add(_conselho(ids, ids["aluno_a"], None))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
        assert ConselhoClasse.query.count() == 0


# ---------------------------------------------------------------------------
# 2. UNIQUE por oferta: duplicata recusada, 2 ofertas permitidas
# ---------------------------------------------------------------------------

def test_duplicata_por_oferta_recusada_e_duas_ofertas_permitidas(app):
    ids = _setup(app, ofertas=2)
    with app.app_context():
        db.session.add(_conselho(ids, ids["aluno_a"], ids["ofertas"][0]))
        db.session.add(_conselho(ids, ids["aluno_a"], ids["ofertas"][1]))
        db.session.commit()
        assert ConselhoClasse.query.filter_by(aluno_id=ids["aluno_a"]).count() == 2

        # Mesma oferta + mesma etapa → recusado por uix_conselho_oferta.
        db.session.add(_conselho(ids, ids["aluno_a"], ids["ofertas"][0]))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
        assert ConselhoClasse.query.filter_by(
            turma_curso_id=ids["ofertas"][0]
        ).count() == 1


# ---------------------------------------------------------------------------
# 3. Turma sem o atributo (e sem a coluna) conselho_concluido
# ---------------------------------------------------------------------------

def test_turma_sem_atributo_conselho_concluido(app):
    ids = _setup(app, ofertas=1)
    with app.app_context():
        assert not hasattr(Turma, "conselho_concluido")
        assert "conselho_concluido" not in Turma.__table__.c
        colunas = {c["name"] for c in inspect(db.engine).get_columns("turma")}
        assert "conselho_concluido" not in colunas

        with pytest.raises(TypeError):
            Turma(nome="Turma X", unidade_id=ids["un_a"], ativo=True,
                  conselho_concluido=True)

        # A flag continua existindo — e obrigatória — na OFERTA.
        assert db.session.get(TurmaCurso, ids["ofertas"][0]).conselho_concluido is False


# ---------------------------------------------------------------------------
# 4. alternar_conselho não escreve na turma
# ---------------------------------------------------------------------------

def test_alternar_conselho_nao_escreve_na_turma(client, app):
    ids = _setup(app, ofertas=1)
    _loga(client, ids, unidade_id=ids["un_a"])

    resposta = client.post(f"/turma/alternar-conselho/{ids['turma']}")
    assert resposta.status_code == 302

    with app.app_context():
        assert db.session.get(TurmaCurso, ids["ofertas"][0]).conselho_concluido is True
        turma = db.session.get(Turma, ids["turma"])
        assert not hasattr(turma, "conselho_concluido")
        colunas = {c["name"] for c in inspect(db.engine).get_columns("turma")}
        assert "conselho_concluido" not in colunas  # nada para sincronizar


# ---------------------------------------------------------------------------
# 5. avaliar_turma grava cada etapa no campo certo da oferta
# ---------------------------------------------------------------------------

def test_avaliar_turma_grava_cada_etapa_no_campo_certo(client, app):
    ids = _setup(app, ofertas=1)
    etapa_pergunta = {
        EtapaConselho.INICIAL: ("Inicial ok", "avaliacao_inicial"),
        EtapaConselho.PERCURSO: ("Percurso ok", "avaliacao_percurso"),
        EtapaConselho.FINAL: ("Final ok", "avaliacao_final"),
    }
    with app.app_context():
        perguntas = {}
        for etapa, (texto, _campo) in etapa_pergunta.items():
            p = PerguntaConselho(
                etapa=etapa, tipo="TURMA", texto=f"Pergunta {texto}", ativo=True,
            )
            db.session.add(p)
            db.session.flush()
            perguntas[etapa] = (p.id, texto)
        db.session.commit()

    _loga(client, ids, unidade_id=ids["un_a"])

    for etapa, (pergunta_id, texto) in perguntas.items():
        resposta = client.post(
            f"/turma/{ids['turma']}/avaliacao?etapa={etapa.value}",
            data={
                "turma_curso_id": str(ids["ofertas"][0]),
                f"resp_turma_{pergunta_id}": texto,
            },
        )
        assert resposta.status_code == 302

    with app.app_context():
        oferta = db.session.get(TurmaCurso, ids["ofertas"][0])
        for etapa, (_pergunta_id, texto) in perguntas.items():
            campo = ETAPA_PARA_CAMPO_AVALIACAO[etapa]
            dados = json.loads(getattr(oferta, campo))
            assert texto in dados.values(), f"{etapa} não caiu em {campo}"
        # Nenhum campo de outra etapa foi escrito com o texto alheio.
        assert "Inicial ok" not in json.loads(oferta.avaliacao_final).values()
        assert "Final ok" not in json.loads(oferta.avaliacao_inicial).values()
        # Legado da turma permanece intocado.
        turma = db.session.get(Turma, ids["turma"])
        assert turma.avaliacao_inicial is None


# ---------------------------------------------------------------------------
# 6. Ficha 360°: seletor de oferta (?oferta_sel= validado)
# ---------------------------------------------------------------------------

def test_ficha_com_aluno_em_duas_ofertas_escolhe_por_oferta_sel(client, app):
    ids = _setup(app, ofertas=2)
    _enturma(app, ids, "aluno_a", oferta_idx=0)
    _enturma(app, ids, "aluno_a", oferta_idx=1)
    with app.app_context():
        db.session.add_all([
            _conselho(ids, ids["aluno_a"], ids["ofertas"][0],
                      EtapaConselho.FINAL),
            _conselho(ids, ids["aluno_a"], ids["ofertas"][1],
                      EtapaConselho.FINAL),
        ])
        db.session.commit()

    _loga(client, ids, unidade_id=ids["un_a"])
    base = f"/relatorios/alunos/{ids['aluno_a']}/ficha?turma_id={ids['turma']}"

    resposta = client.get(base + f"&oferta_sel={ids['ofertas'][1]}")
    assert resposta.status_code == 200
    body = resposta.data.decode("utf-8")
    assert "Oferta retratada" in body  # seletor presente
    assert "Turma D52 — Curso 1" in body and "Turma D52 — Curso 2" in body
    assert "classe · Curso 2" in body       # oferta escolhida
    assert "classe · Curso 1" not in body

    resposta = client.get(base + f"&oferta_sel={ids['ofertas'][0]}")
    body = resposta.data.decode("utf-8")
    assert resposta.status_code == 200
    assert "classe · Curso 1" in body
    assert "classe · Curso 2" not in body

    # oferta_sel fora das inscrições do aluno não é adotado: cai na primeira.
    resposta = client.get(base + "&oferta_sel=999999")
    body = resposta.data.decode("utf-8")
    assert resposta.status_code == 200
    assert "classe · Curso 1" in body
    assert "classe · Curso 2" not in body


def test_ficha_com_uma_inscricao_nao_mostra_seletor(client, app):
    ids = _setup(app, ofertas=1)
    _enturma(app, ids, "aluno_a", oferta_idx=0)
    _loga(client, ids, unidade_id=ids["un_a"])

    resposta = client.get(
        f"/relatorios/alunos/{ids['aluno_a']}/ficha?turma_id={ids['turma']}"
    )
    assert resposta.status_code == 200
    body = resposta.data.decode("utf-8")
    assert "Oferta retratada" not in body  # comportamento anterior mantido
    assert "classe · Curso 1" in body
