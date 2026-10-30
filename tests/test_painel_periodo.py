"""ETAPA B7 — visão por PERÍODO do painel pedagógico (smoke funcional).

Cobre a rota `relatorios.painel_pedagogico` sem `turma_id` (visão por período),
que respondia `NameError` porque `periodo._montar_turma_linha` nunca existiu.

Regras cobertas:
    - 200 com uma unidade, um período, 2 turmas (uma com 2 ofertas e conselho
      por oferta, outra sem conselho), alunos e frequências: a página traz as
      turmas, os percentuais de frequência e a contagem de alunos.
    - O conselho do período usa os agregados de PERCURSO no nível da turma
      (`ok/total`), somando as ofertas (D5.4).
    - Período sem turmas responde 200 sem erro.
    - Usuário de outra unidade não vê os dados da unidade A.

Um usuário por teste (T1 §5.6); SQLite in-memory.
"""
# ruff: noqa: F811 — fixtures `app`/`client` reaproveitados da D5.2.

from datetime import date

from _helpers import nova_inscricao, nova_oferta
from test_conselho_oferta import _loga

from app.database import db
from app.models import (
    Aluno,
    ConselhoClasse,
    ConselhoResposta,
    Curso,
    Frequencia,
    PerguntaConselho,
    PeriodoLetivo,
    Turma,
    Unidade,
    User,
)
from app.models.enums import EtapaConselho

DATA_INI = date(2026, 2, 2)
DATA_FIM = date(2026, 6, 30)
AULAS = (date(2026, 3, 2), date(2026, 3, 3), date(2026, 3, 9), date(2026, 3, 10))


# ---------------------------------------------------------------------------
# Semeadura
# ---------------------------------------------------------------------------

def _turma(app, ids, nome, *, unidade_id=None, programa="Programa Base"):
    with app.app_context():
        turma = Turma(
            nome=nome, turno="Manhã", programa=programa,
            data_inicio=DATA_INI, data_fim=DATA_FIM,
            periodo_letivo_id=ids["periodo"],
            unidade_id=unidade_id or ids["un_a"], ativo=True,
        )
        db.session.add(turma)
        db.session.commit()
        return turma.id


def _oferta(app, ids, turma_id, nome_curso, *, programa="Programa Base"):
    with app.app_context():
        curso = Curso(nome=nome_curso, unidade_id=ids["un_a"], ativo=True)
        db.session.add(curso)
        db.session.flush()
        oferta = nova_oferta(
            turma_id, curso.id, ids["un_a"],
            programa=programa, principal=False, professor_id=ids["prof"],
        )
        db.session.commit()
        return oferta.id


def _aluno(app, ids, nome):
    with app.app_context():
        aluno = Aluno(nome=nome, unidade_id=ids["un_a"], ativo=True)
        db.session.add(aluno)
        db.session.commit()
        return aluno.id


def _matricula(app, ids, aluno_id, turma_id, oferta_id):
    with app.app_context():
        nova_inscricao(aluno_id, turma_id, oferta_id)
        db.session.commit()


def _frequencias(app, ids, aluno_id, turma_id, oferta_id, conceito):
    with app.app_context():
        for dia in AULAS:
            db.session.add(Frequencia(
                aluno_id=aluno_id, turma_id=turma_id,
                turma_curso_id=oferta_id, data=dia,
                conceito=conceito, unidade_id=ids["un_a"],
            ))
        db.session.commit()


def _conselho(app, ids, aluno_id, turma_id, oferta_id, etapa, *, situacao=None,
              com_resposta=False, pergunta_id=None):
    with app.app_context():
        conselho = ConselhoClasse(
            turma_id=turma_id, aluno_id=aluno_id, turma_curso_id=oferta_id,
            etapa=etapa, unidade_id=ids["un_a"],
            situacao_final=situacao, concluido=True,
        )
        db.session.add(conselho)
        db.session.flush()
        if com_resposta:
            db.session.add(ConselhoResposta(
                conselho_id=conselho.id, aluno_id=aluno_id,
                pergunta_id=pergunta_id, resposta="Evoluiu bem",
            ))
        db.session.commit()
        return conselho.id


def _pergunta(app):
    with app.app_context():
        pergunta = PerguntaConselho(
            etapa=EtapaConselho.PERCURSO, tipo="ALUNO",
            texto="Como o aluno evoluiu no percurso?", ativo=True,
        )
        db.session.add(pergunta)
        db.session.commit()
        return pergunta.id


def _semear(app, *, com_turmas=True):
    """Unidade A + usuário admin + período (opcionalmente com as 2 turmas)."""
    with app.app_context():
        un_a = Unidade(nome="Unidade A", ativo=True)
        usuario = User(
            name="Admin B7", email="admin.b7@example.com",
            role="admin", first_login=False,
        )
        usuario.set_password("SenhaLocal!123")
        # G1/P2 (d6e7f8a9b0c1): oferta exige professor — a semente garante um.
        prof = User(
            name="Prof B7", email="prof.b7@example.com",
            role="professor", first_login=False,
        )
        db.session.add_all([un_a, usuario, prof])
        db.session.flush()
        periodo = PeriodoLetivo(
            nome="Periodo B7", data_inicio=DATA_INI, data_fim=DATA_FIM,
            unidade_id=un_a.id, ativo=True,
        )
        db.session.add(periodo)
        db.session.commit()
        ids = {
            "user_id": usuario.id,
            "un_a": un_a.id,
            "periodo": periodo.id,
            "prof": prof.id,
        }

    if not com_turmas:
        return ids

    alfa = _turma(app, ids, "Turma Alfa", programa="Programa Alfa")
    oferta_1 = _oferta(app, ids, alfa, "Curso Alfa 1")
    oferta_2 = _oferta(app, ids, alfa, "Curso Alfa 2")
    beta = _turma(app, ids, "Turma Beta", programa="Programa Beta")
    oferta_beta = _oferta(app, ids, beta, "Curso Beta")

    aluno_a = _aluno(app, ids, "Aluno A")
    aluno_b = _aluno(app, ids, "Aluno B")
    aluno_c = _aluno(app, ids, "Aluno C")
    _matricula(app, ids, aluno_a, alfa, oferta_1)
    _matricula(app, ids, aluno_b, alfa, oferta_2)
    _matricula(app, ids, aluno_c, beta, oferta_beta)

    # Alfa: 4 presenças (oferta 1) + 4 faltas (oferta 2) = 50,0%.
    _frequencias(app, ids, aluno_a, alfa, oferta_1, "A")
    _frequencias(app, ids, aluno_b, alfa, oferta_2, "F")
    # Beta: 100,0%.
    _frequencias(app, ids, aluno_c, beta, oferta_beta, "A")

    # Conselho FINAL por OFERTA em Alfa; Beta sem conselho.
    _conselho(app, ids, aluno_a, alfa, oferta_1, EtapaConselho.FINAL,
              situacao="Aprovado")
    _conselho(app, ids, aluno_b, alfa, oferta_2, EtapaConselho.FINAL,
              situacao="Evadido")
    # PERCURSO: 2 conselhos, 1 com resposta → "1 de 2" no KPI do período.
    pergunta_id = _pergunta(app)
    _conselho(app, ids, aluno_a, alfa, oferta_1, EtapaConselho.PERCURSO,
              com_resposta=True, pergunta_id=pergunta_id)
    _conselho(app, ids, aluno_b, alfa, oferta_2, EtapaConselho.PERCURSO)

    ids.update({
        "alfa": alfa,
        "beta": beta,
        "oferta_1": oferta_1,
        "oferta_2": oferta_2,
        "oferta_beta": oferta_beta,
    })
    return ids


# ---------------------------------------------------------------------------
# Visão por período
# ---------------------------------------------------------------------------

def _pagina(client, periodo_id):
    resposta = client.get(f"/relatorios/painel?periodo_letivo_id={periodo_id}")
    assert resposta.status_code == 200
    return resposta.data.decode("utf-8")


def _linha_comparativo(body, turma_id):
    """Linha do comparativo de turmas (a única com o link `turma_id=`)."""
    linhas = [
        ln for ln in body.split("</tr>")
        if f"turma_id={turma_id}" in ln
    ]
    assert len(linhas) == 1
    return linhas[0]


def test_visao_por_periodo_200_com_turmas_e_numeros(client, app):
    ids = _semear(app)
    _loga(client, ids, unidade_id=ids["un_a"])
    body = _pagina(client, ids["periodo"])

    assert "Turma Alfa" in body
    assert "Turma Beta" in body
    assert "50.0%" in body  # frequência da Turma Alfa
    assert "100.0%" in body  # frequência da Turma Beta
    assert "2 alunos" in body
    assert "1 alunos" in body

    # Conselho de percurso (nível da turma, somando as ofertas).
    assert "1 de 2" in body
    linha_alfa = _linha_comparativo(body, ids["alfa"])
    assert "50.0%" in linha_alfa
    assert "1/2" in linha_alfa  # percurso ok/total da turma
    assert "Programa Alfa" in linha_alfa

    linha_beta = _linha_comparativo(body, ids["beta"])
    assert "100.0%" in linha_beta
    assert "0/0" in linha_beta  # turma sem conselho
    assert "Programa Beta" in linha_beta


def test_visao_por_periodo_sem_turmas_responde_200(client, app):
    ids = _semear(app, com_turmas=False)
    _loga(client, ids, unidade_id=ids["un_a"])
    body = _pagina(client, ids["periodo"])

    assert "Sem conselho registrado." in body
    assert "Sem dados de renovação." in body


def test_visao_por_periodo_outra_unidade_nao_ve_dados(client, app):
    ids = _semear(app)
    with app.app_context():
        un_b = Unidade(nome="Unidade B", ativo=True)
        db.session.add(un_b)
        db.session.commit()
        un_b_id = un_b.id
    _loga(client, ids, unidade_id=un_b_id)

    body = _pagina(client, ids["periodo"])

    assert "Nenhum período letivo cadastrado para esta unidade." in body
    assert "Turma Alfa" not in body
    assert "50.0%" not in body
