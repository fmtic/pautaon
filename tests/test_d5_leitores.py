"""ETAPA D5.4 — leitores do conselho POR OFERTA.

Regras cobertas (docs/D5_0_desenho.md §1.5/§1.6 + D5.4):
    - A unidade de leitura é (aluno, oferta, etapa). Cada linha de histórico,
      ficha e certificado é uma INSCRIÇÃO (aluno × oferta).
    - `app/services/conselho_leitura.py` busca em LOTE (uma consulta) e nunca
      adota pares sem oferta (`turma_curso_id` NULL); desde a D5.5 o próprio
      banco recusa um conselho sem oferta.
    - Painel pedagógico agrega por oferta (rótulo "Turma — Curso") e usa
      `PerguntaConselho.texto` (o antigo `enunciado` estourava).
    - Resultado do conselho segue o padrão M1 por oferta: 0 oferta ativa
      recusa com aviso, 1 usa direto, 2+ exigem `?oferta_sel=`; alunos e
      frequência vêm da própria oferta.
    - Certificado: uma linha por inscrição; o ícone Concluído/Pendente vem de
      `TurmaCurso.conselho_concluido` da oferta (nunca do derivado da turma).
    - BI CRU-002 conta aluno DISTINTO; CRU-005 conta uma linha por situação
      distinta (comportamento caracterizado, sem alterar a lógica).
    - Isolamento por unidade nas leituras.

Um usuário por teste (T1 §5.6): cada teste semeia via `_setup` da D5.2 e faz
um único login.
"""
# ruff: noqa: F811 — os fixtures `app`/`client` são reaproveitados da D5.2.

import re
from datetime import date

import pytest
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from test_conselho_oferta import (  # noqa: F401  (fixtures reaproveitadas)
    _enturma,
    _loga,
    _perguntas,
    _setup,
    app,
    client,
)

from app.database import db
from app.models import (
    ConselhoClasse,
    ConselhoResposta,
    Frequencia,
    PerfilDiversidade,
    PerfilSocioeconomico,
    PeriodoLetivo,
    Turma,
    TurmaCurso,
    Unidade,
)
from app.models.enums import EtapaConselho
from app.relatorios.bi_alunos import (
    alunos_raca_conselho,
    desempenho_conselho_por_renda,
)
from app.relatorios.painel_pedagogico import conselho as conselho_svc
from app.services.conselho_leitura import conselho_do_aluno, conselhos_por_oferta

# ---------------------------------------------------------------------------
# Helpers locais
# ---------------------------------------------------------------------------


def _periodo_id(app):
    with app.app_context():
        return PeriodoLetivo.query.first().id


def _vincular_turma_ao_periodo(app, ids):
    """`_setup` cria a turma sem `periodo_letivo_id` (quirk da fixture D5.2):
    os leitores que filtram por período precisam do vínculo explícito."""
    with app.app_context():
        periodo = PeriodoLetivo.query.first()
        db.session.get(Turma, ids["turma"]).periodo_letivo_id = periodo.id
        db.session.commit()
        return periodo.id


def _conselho_em(app, ids, aluno_id, oferta_id, etapa, *,
                 situacao=None, concluido=True):
    """Cria um conselho (aluno × oferta × etapa); `oferta_id=None` = legado."""
    with app.app_context():
        conselho = ConselhoClasse(
            turma_id=ids["turma"],
            aluno_id=aluno_id,
            turma_curso_id=oferta_id,
            etapa=etapa,
            unidade_id=ids["un_a"],
            situacao_final=situacao,
            concluido=concluido,
        )
        db.session.add(conselho)
        db.session.commit()
        return conselho.id


def _responder(app, conselho_id, aluno_id, pergunta_id, texto):
    with app.app_context():
        db.session.add(
            ConselhoResposta(
                conselho_id=conselho_id,
                aluno_id=aluno_id,
                pergunta_id=pergunta_id,
                resposta=texto,
            )
        )
        db.session.commit()


def _concluir_ofertas(app, oferta_flags):
    with app.app_context():
        for oferta_id, flag in oferta_flags.items():
            db.session.get(TurmaCurso, oferta_id).conselho_concluido = flag
        db.session.commit()


def _linhas(body):
    return re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S)


def _contar_consultas(app, funcao, trecho):
    """Executa `funcao` e devolve (resultado, nº de SELECT no `trecho`)."""
    statements = []

    def _listener(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    with app.app_context():
        event.listen(db.engine, "before_cursor_execute", _listener)
        try:
            resultado = funcao()
        finally:
            event.remove(db.engine, "before_cursor_execute", _listener)
    total = sum(trecho in stmt.lower() for stmt in statements)
    return resultado, total


# ---------------------------------------------------------------------------
# Passo 2 — serviço de leitura em lote
# ---------------------------------------------------------------------------

def test_servico_lote_uma_consulta_por_oferta_ignora_par_sem_oferta(app):
    ids = _setup(app, ofertas=2)
    for oferta_id in ids["ofertas"]:
        _conselho_em(app, ids, ids["aluno_a"], oferta_id,
                     EtapaConselho.FINAL, situacao="Aprovado")

    def _executar():
        return conselhos_por_oferta(
            [
                (ids["aluno_a"], ids["ofertas"][0]),
                (ids["aluno_a"], ids["ofertas"][1]),
                (ids["aluno_a"], None),      # sem oferta → ignorado
                (None, ids["ofertas"][0]),   # sem aluno → ignorado
            ],
            etapas=["FINAL"],
        )

    conselhos, selects = _contar_consultas(app, _executar, "conselho_classe")
    assert len(conselhos) == 2
    assert set(conselhos) == {
        (ids["aluno_a"], ids["ofertas"][0], "FINAL"),
        (ids["aluno_a"], ids["ofertas"][1], "FINAL"),
    }
    # Uma única consulta para todos os pares (sem N+1).
    assert selects == 1

    with app.app_context():
        assert conselho_do_aluno(ids["aluno_a"], None, "FINAL") is None
        achado = conselho_do_aluno(
            ids["aluno_a"], ids["ofertas"][0], EtapaConselho.FINAL
        )
        assert achado is not None
        assert achado.turma_curso_id == ids["ofertas"][0]
        assert achado.situacao_final == "Aprovado"


# ---------------------------------------------------------------------------
# Passo 3 — histórico do aluno por inscrição
# ---------------------------------------------------------------------------

def test_historico_uma_linha_por_inscricao_com_status_da_oferta(client, app):
    ids = _setup(app, ofertas=2)
    _enturma(app, ids, "aluno_a", oferta_idx=0)
    _enturma(app, ids, "aluno_a", oferta_idx=1)
    _conselho_em(app, ids, ids["aluno_a"], ids["ofertas"][0],
                 EtapaConselho.INICIAL, situacao="Aprovado")
    _conselho_em(app, ids, ids["aluno_a"], ids["ofertas"][0],
                 EtapaConselho.FINAL, situacao="Aprovado")
    _conselho_em(app, ids, ids["aluno_a"], ids["ofertas"][1],
                 EtapaConselho.FINAL, situacao="Evadido")
    _loga(client, ids, unidade_id=ids["un_a"])

    resposta = client.get(f"/aluno/{ids['aluno_a']}/historico")
    assert resposta.status_code == 200
    body = resposta.data.decode("utf-8")

    linhas = [ln for ln in _linhas(body) if "Turma D52" in ln]
    assert len(linhas) == 2  # uma por inscrição (aluno × oferta)

    da_oferta_1 = next(ln for ln in linhas if "Curso 1" in ln)
    da_oferta_2 = next(ln for ln in linhas if "Curso 2" in ln)
    assert "Aprovado" in da_oferta_1 and "Evadido" not in da_oferta_1
    assert "Evadido" in da_oferta_2 and "Aprovado" not in da_oferta_2
    # Status INICIAL da oferta 1 aparece junto do FINAL (colunas I/P).
    assert "I: Aprovado" in da_oferta_1


def test_historico_frequencia_da_inscricao_nao_mistura_turmas(client, app):
    """Cada linha conta só a frequência da PRÓPRIA inscrição (turma + oferta)."""
    ids = _setup(app, ofertas=1)
    _enturma(app, ids, "aluno_a", oferta_idx=0)
    with app.app_context():
        outra = Turma(
            nome="Turma Antiga", turno="Tarde",
            unidade_id=ids["un_a"], ativo=True,
        )
        db.session.add(outra)
        db.session.flush()
        outra_id = outra.id
        db.session.add_all([
            Frequencia(aluno_id=ids["aluno_a"], turma_id=outra_id,
                       data=date(2026, 3, 2), conceito="F",
                       unidade_id=ids["un_a"]),
            Frequencia(aluno_id=ids["aluno_a"], turma_id=ids["turma"],
                       turma_curso_id=ids["ofertas"][0],
                       data=date(2026, 3, 3), conceito="A",
                       unidade_id=ids["un_a"]),
        ])
        db.session.commit()
    _loga(client, ids, unidade_id=ids["un_a"])

    resposta = client.get(f"/aluno/{ids['aluno_a']}/historico")
    assert resposta.status_code == 200
    linhas = [ln for ln in _linhas(resposta.data.decode("utf-8"))
              if "Turma D52" in ln]
    assert len(linhas) == 1
    assert "100.0%" in linhas[0]
    assert "Turma Antiga" not in resposta.data.decode("utf-8")


# ---------------------------------------------------------------------------
# Passo 3 — ficha do aluno por oferta
# ---------------------------------------------------------------------------

def test_ficha_por_oferta_nao_mistura_conselhos(client, app):
    ids = _setup(app, ofertas=2)
    _enturma(app, ids, "aluno_a", oferta_idx=0)
    _enturma(app, ids, "aluno_a", oferta_idx=1)
    _conselho_em(app, ids, ids["aluno_a"], ids["ofertas"][0],
                 EtapaConselho.INICIAL, situacao="Aprovado")
    _conselho_em(app, ids, ids["aluno_a"], ids["ofertas"][1],
                 EtapaConselho.FINAL, situacao="Evadido")
    _loga(client, ids, unidade_id=ids["un_a"])

    base = f"/relatorios/alunos/{ids['aluno_a']}/ficha?turma_id={ids['turma']}"

    resposta = client.get(base + f"&oferta_sel={ids['ofertas'][1]}")
    assert resposta.status_code == 200
    body = resposta.data.decode("utf-8")
    assert "classe · Curso 2" in body
    assert "classe · Curso 1" not in body  # a oferta 1 não vaza para a ficha da 2
    assert "Situação final na oferta: Evadido" in body
    # D5.5: o seletor “Turma — Curso” lista as duas ofertas da inscrição.
    assert "Oferta retratada" in body
    assert "Turma D52 — Curso 1" in body and "Turma D52 — Curso 2" in body

    resposta = client.get(base + f"&oferta_sel={ids['ofertas'][0]}")
    assert resposta.status_code == 200
    body = resposta.data.decode("utf-8")
    assert "classe · Curso 1" in body
    assert "classe · Curso 2" not in body
    assert "Evadido" not in body
    # Aprovado é favorável: não gera sinal de situação final.
    assert "Situação final na oferta" not in body


# ---------------------------------------------------------------------------
# Passo 4 — painel pedagógico por oferta (p.texto)
# ---------------------------------------------------------------------------

def test_painel_por_turma_agrega_por_oferta_e_usa_texto_da_pergunta(client, app):
    ids = _setup(app, ofertas=2)
    _enturma(app, ids, "aluno_a", oferta_idx=0)
    _enturma(app, ids, "aluno_b", oferta_idx=1)
    p_aluno, _ = _perguntas(app)
    c_oferta_1 = _conselho_em(app, ids, ids["aluno_a"], ids["ofertas"][0],
                              EtapaConselho.INICIAL)
    c_oferta_2 = _conselho_em(app, ids, ids["aluno_b"], ids["ofertas"][1],
                              EtapaConselho.INICIAL)
    _responder(app, c_oferta_1, ids["aluno_a"], p_aluno, "Sempre")
    _responder(app, c_oferta_2, ids["aluno_b"], p_aluno, "Às vezes")
    periodo_id = _vincular_turma_ao_periodo(app, ids)
    _loga(client, ids, unidade_id=ids["un_a"])

    # Serviço: cada oferta tem o próprio bloco e o texto da pergunta vem de
    # `PerguntaConselho.texto` (antes `p.enunciado` levantava AttributeError).
    with app.app_context():
        agregado = conselho_svc.por_turma([ids["turma"]])[ids["turma"]]
        ofertas = {o["turma_curso_id"]: o for o in agregado["ofertas"]}
        assert set(ofertas) == set(ids["ofertas"])
        assert ofertas[ids["ofertas"][0]]["rotulo"] == "Turma D52 — Curso 1"
        assert ofertas[ids["ofertas"][0]]["perguntas"][p_aluno] == (
            "Como o aluno participa das aulas?"
        )
        assert ofertas[ids["ofertas"][0]]["inicial"] == {
            "total": 1, "respondidos": 1,
        }

    resposta = client.get(
        f"/relatorios/painel?periodo_letivo_id={periodo_id}"
        f"&turma_id={ids['turma']}"
    )
    assert resposta.status_code == 200
    body = resposta.data.decode("utf-8")
    assert "Turma D52 — Curso 1" in body
    assert "Turma D52 — Curso 2" in body
    assert "Como o aluno participa das aulas?" in body


def test_painel_nao_exibe_conselho_sem_oferta(client, app):
    """D5.5: conselho sem oferta não existe mais — o banco recusa e o painel
    segue vazio (antes havia linha legada NULL que os leitores ignoravam)."""
    ids = _setup(app, ofertas=1)
    _enturma(app, ids, "aluno_a", oferta_idx=0)
    with app.app_context():
        db.session.add(ConselhoClasse(
            turma_id=ids["turma"], aluno_id=ids["aluno_a"],
            etapa=EtapaConselho.INICIAL, turma_curso_id=None,
            unidade_id=ids["un_a"],
        ))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
        assert conselho_svc.por_turma([ids["turma"]]) == {}


# ---------------------------------------------------------------------------
# Passo 4 — resultado do conselho por oferta
# ---------------------------------------------------------------------------

def _frequencias_por_oferta(app, ids):
    with app.app_context():
        db.session.add_all([
            Frequencia(aluno_id=ids["aluno_a"], turma_id=ids["turma"],
                       turma_curso_id=ids["ofertas"][0],
                       data=date(2026, 3, 2), conceito="A",
                       unidade_id=ids["un_a"]),
            Frequencia(aluno_id=ids["aluno_a"], turma_id=ids["turma"],
                       turma_curso_id=ids["ofertas"][0],
                       data=date(2026, 3, 3), conceito="A",
                       unidade_id=ids["un_a"]),
            Frequencia(aluno_id=ids["aluno_b"], turma_id=ids["turma"],
                       turma_curso_id=ids["ofertas"][1],
                       data=date(2026, 3, 4), conceito="F",
                       unidade_id=ids["un_a"]),
            Frequencia(aluno_id=ids["aluno_b"], turma_id=ids["turma"],
                       turma_curso_id=ids["ofertas"][1],
                       data=date(2026, 3, 5), conceito="F",
                       unidade_id=ids["un_a"]),
        ])
        db.session.commit()


def test_resultado_2_ofertas_exige_escolha_e_usa_dados_da_oferta(client, app):
    ids = _setup(app, ofertas=2)
    _enturma(app, ids, "aluno_a", oferta_idx=0)
    _enturma(app, ids, "aluno_b", oferta_idx=1)
    _conselho_em(app, ids, ids["aluno_a"], ids["ofertas"][0],
                 EtapaConselho.FINAL, situacao="Aprovado")
    _conselho_em(app, ids, ids["aluno_b"], ids["ofertas"][1],
                 EtapaConselho.FINAL, situacao="Evadido")
    _frequencias_por_oferta(app, ids)
    periodo_id = _vincular_turma_ao_periodo(app, ids)
    _loga(client, ids, unidade_id=ids["un_a"])

    base = (f"/relatorios/conselho?periodo_letivo_id={periodo_id}"
            f"&turmas={ids['turma']}")

    # 2+ ofertas sem escolha: só o seletor, sem dados misturados.
    resposta = client.get(base)
    assert resposta.status_code == 200
    body = resposta.data.decode("utf-8")
    assert "Selecione o curso" in body
    assert "Aluno Ana" not in body and "Aluno Beto" not in body

    resposta = client.get(base + f"&oferta_sel={ids['ofertas'][0]}")
    assert resposta.status_code == 200
    body = resposta.data.decode("utf-8")
    assert "Aluno Ana" in body and "Aluno Beto" not in body
    assert "Curso 1" in body and "Curso 2" not in body
    assert "100.0%" in body  # frequência da oferta 1 (2 presenças)

    resposta = client.get(base + f"&oferta_sel={ids['ofertas'][1]}")
    assert resposta.status_code == 200
    body = resposta.data.decode("utf-8")
    assert "Aluno Beto" in body and "Aluno Ana" not in body
    assert "Curso 2" in body and "Curso 1" not in body
    assert "0.0%" in body  # frequência da oferta 2 (2 faltas)


def test_resultado_uma_oferta_usa_direto(client, app):
    ids = _setup(app, ofertas=1)
    _enturma(app, ids, "aluno_a", oferta_idx=0)
    _conselho_em(app, ids, ids["aluno_a"], ids["ofertas"][0],
                 EtapaConselho.FINAL, situacao="Aprovado")
    periodo_id = _vincular_turma_ao_periodo(app, ids)
    _loga(client, ids, unidade_id=ids["un_a"])

    resposta = client.get(
        f"/relatorios/conselho?periodo_letivo_id={periodo_id}"
        f"&turmas={ids['turma']}"
    )
    assert resposta.status_code == 200
    body = resposta.data.decode("utf-8")
    assert "Selecione o curso" not in body
    assert "Aluno Ana" in body
    assert "Aprovado" in body


def test_resultado_turma_sem_oferta_ativa_recusa_com_aviso(client, app):
    ids = _setup(app, ofertas=0)
    periodo_id = _vincular_turma_ao_periodo(app, ids)
    _loga(client, ids, unidade_id=ids["un_a"])

    resposta = client.get(
        f"/relatorios/conselho?periodo_letivo_id={periodo_id}"
        f"&turmas={ids['turma']}"
    )
    assert resposta.status_code == 200
    body = resposta.data.decode("utf-8")
    assert "não possui curso (oferta) ativa" in body


# ---------------------------------------------------------------------------
# Passo 5 — certificado por inscrição
# ---------------------------------------------------------------------------

def test_certificado_uma_linha_por_inscricao_e_icone_da_oferta(client, app):
    ids = _setup(app, ofertas=2)
    _enturma(app, ids, "aluno_a", oferta_idx=0)
    _enturma(app, ids, "aluno_a", oferta_idx=1)
    _conselho_em(app, ids, ids["aluno_a"], ids["ofertas"][0],
                 EtapaConselho.FINAL, situacao="Aprovado")
    _conselho_em(app, ids, ids["aluno_a"], ids["ofertas"][1],
                 EtapaConselho.FINAL, situacao="Evadido")
    _concluir_ofertas(app, {ids["ofertas"][0]: True, ids["ofertas"][1]: False})
    periodo_id = _vincular_turma_ao_periodo(app, ids)
    _loga(client, ids, unidade_id=ids["un_a"])

    resposta = client.get(f"/periodo-letivo/relatorio/{periodo_id}")
    assert resposta.status_code == 200
    body = resposta.data.decode("utf-8")

    linhas = [ln for ln in _linhas(body) if "Turma D52" in ln]
    assert len(linhas) == 2  # uma linha por inscrição (aluno × oferta)
    linha_1 = next(ln for ln in linhas if "Curso 1" in ln)
    linha_2 = next(ln for ln in linhas if "Curso 2" in ln)
    assert "Aprovado" in linha_1
    assert "Evadido" in linha_2

    # Ícone do encerramento da PRÓPRIA oferta.
    assert body.count("bi-check-circle-fill text-success") == 1
    assert body.count("bi-clock text-warning") == 1


# ---------------------------------------------------------------------------
# Passo 6 — BI de caracterização (CRU-002 / CRU-005)
# ---------------------------------------------------------------------------

def test_bi_cru002_conta_aluno_distinto_e_cru005_conta_por_situacao(app):
    """Caracteriza o comportamento herdado, SEM alterar `bi_alunos.py`.

    Regra do CRU-002: `count(distinct aluno_id)` — o mesmo aluno em 2 ofertas
    da mesma turma conta **1**.
    Regra do CRU-005: itera as LINHAS de conselho — o mesmo aluno conta **1
    por situação distinta** em que aparece (aqui: 1 aprovado + 1 outro).
    """
    ids = _setup(app, ofertas=2)
    _conselho_em(app, ids, ids["aluno_a"], ids["ofertas"][0],
                 EtapaConselho.FINAL, situacao="Aprovado")
    _conselho_em(app, ids, ids["aluno_a"], ids["ofertas"][1],
                 EtapaConselho.FINAL, situacao="Evadido")
    with app.app_context():
        db.session.add(PerfilDiversidade(
            aluno_id=ids["aluno_a"], unidade_id=ids["un_a"], raca_cor="Parda",
        ))
        db.session.add(PerfilSocioeconomico(
            aluno_id=ids["aluno_a"], unidade_id=ids["un_a"],
            renda_familiar=1000,
        ))
        db.session.commit()

    with app.app_context():
        raca = alunos_raca_conselho(unidade_id=ids["un_a"])
        assert raca == [{"id": "Parda", "nome": "Parda", "valor": 1}]

        renda = {item["id"]: item for item in desempenho_conselho_por_renda(
            unidade_id=ids["un_a"]
        )}
        # 2 linhas de conselho do MESMO aluno: 1 aprovada + 1 "outros".
        assert renda["ate_1500"]["valor"] == 2
        assert "Aprovados: 1, Outros: 1" in renda["ate_1500"]["nome"]


# ---------------------------------------------------------------------------
# Passo 7 — isolamento por unidade nas leituras
# ---------------------------------------------------------------------------

def test_isolamento_outra_unidade_nao_le_conselhos_da_unidade_a(client, app):
    ids = _setup(app, ofertas=1)
    _enturma(app, ids, "aluno_a", oferta_idx=0)
    _conselho_em(app, ids, ids["aluno_a"], ids["ofertas"][0],
                 EtapaConselho.FINAL, situacao="Aprovado")
    periodo_id = _vincular_turma_ao_periodo(app, ids)
    with app.app_context():
        un_b = Unidade(nome="Unidade B", ativo=True)
        db.session.add(un_b)
        db.session.commit()
        un_b_id = un_b.id
    _loga(client, ids, unidade_id=un_b_id)

    # Histórico: vínculo é de outra unidade → 403.
    assert client.get(f"/aluno/{ids['aluno_a']}/historico").status_code == 403

    # Ficha: o aluno não existe no escopo da unidade → 404.
    assert client.get(
        f"/relatorios/alunos/{ids['aluno_a']}/ficha"
    ).status_code == 404

    # Resultado: o período da unidade A não entra no seletor → sem dados.
    resposta = client.get(
        f"/relatorios/conselho?periodo_letivo_id={periodo_id}"
        f"&turmas={ids['turma']}"
    )
    assert resposta.status_code == 200
    assert "Aluno Ana" not in resposta.data.decode("utf-8")
