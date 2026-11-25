"""AJ31-B — Informações Gerais do Período: base única, enum, isolamento e impressão.

Cobre os pontos 2a-2j do fechamento:

    - contagens (inscritos, por situação, pendentes, aproveitamento) saem do
      MESMO conjunto de pares ``(aluno, oferta)``;
    - ``Inscricao.ativo``, ``Turma.ativo``, ``Aluno.ativo``,
      ``cond_oferta_efetiva()`` e filtro de unidade;
    - ``ConselhoClasse`` FINAL só entra quando o par está entre os inscritos;
    - ``pendentes`` é derivado da base, sem ``max(0, ...)``;
    - vocabulário vem de ``SituacaoFinal``/``SITUACAO_FINAL_OPCOES``;
    - estado vazio sem ZeroDivisionError, mensagem exata e totais preservados;
    - Aproveitamento = favoráveis / avaliados, com 1 casa decimal;
    - 403/404, Visão Global e período sem unidade;
    - imprensa A4 retrato, sem CSS/JS do Resultado do Conselho;
    - botão de entrada no Resultado do Conselho (href/disabled/d-print-none).
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from _helpers import login_as, nova_inscricao, nova_oferta

from app import db
from app.models import (
    Aluno,
    ConselhoClasse,
    Curso,
    PeriodoLetivo,
    Turma,
    Unidade,
    User,
)
from app.models.enums import (
    SITUACAO_FINAL_OPCOES,
    EtapaConselho,
    SituacaoFinal,
)
from app.services import relatorio_periodo_info as servico

RAIZ = Path(__file__).resolve().parents[1]
DATA_INI = date(2026, 2, 2)
DATA_FIM = date(2099, 12, 30)
DATA_FIM_ENCERRADO = date(2020, 12, 30)

UN_A_NOME = "Unidade AJ31 Alfa"
UN_B_NOME = "Unidade AJ31 Beta"
PER_A_NOME = "Período AJ31 Alfa"
MENSAGEM_VAZIA = "Nenhuma situação final definida neste período ainda."


# ---------------------------------------------------------------------------
# Semente
# ---------------------------------------------------------------------------

def _aluno(unidade_id, nome, *, ativo=True):
    aluno = Aluno(nome=nome, unidade_id=unidade_id, ativo=ativo)
    db.session.add(aluno)
    db.session.flush()
    return aluno.id


def _turma(unidade_id, periodo_id, nome, *, ativo=True):
    turma = Turma(
        nome=nome, turno="Manhã", data_inicio=DATA_INI, data_fim=DATA_FIM,
        periodo_letivo_id=periodo_id, unidade_id=unidade_id, ativo=ativo,
    )
    db.session.add(turma)
    db.session.flush()
    return turma.id


def _conselho(aluno_id, turma_id, oferta_id, unidade_id, situacao, etapa=EtapaConselho.FINAL):
    db.session.add(ConselhoClasse(
        aluno_id=aluno_id, turma_id=turma_id, turma_curso_id=oferta_id,
        etapa=etapa, unidade_id=unidade_id, situacao_final=situacao,
        concluido=True,
    ))


def _setup(app):
    """Massa conhecida: 10 inscritos em A, 1 em B, 1 no período encerrado."""
    with app.app_context():
        un_a = Unidade(nome=UN_A_NOME, ativo=True)
        un_b = Unidade(nome=UN_B_NOME, ativo=True)
        un_sigla = Unidade(nome="MGB", ativo=True)
        db.session.add_all([un_a, un_b, un_sigla])
        db.session.flush()

        usuarios = {}
        for chave, nome, role, unidade_id in (
            ("admin", "Admin AJ31", "admin", un_a.id),
            ("ped", "Ped AJ31", "pedagogico", un_a.id),
            ("prof", "Prof AJ31", "professor", un_a.id),
            ("global", "Admin Global AJ31", "admin", None),
            ("sigla", "Admin MGB AJ31", "admin", un_sigla.id),
        ):
            user = User(
                name=nome, email=f"{chave}.aj31@x.invalid", role=role,
                first_login=False, unidade_id=unidade_id,
            )
            user.set_password("SenhaLocal!123")
            db.session.add(user)
            usuarios[chave] = user
        db.session.flush()

        per_a = PeriodoLetivo(
            nome=PER_A_NOME, data_inicio=DATA_INI, data_fim=DATA_FIM,
            unidade_id=un_a.id, ativo=True,
        )
        per_b = PeriodoLetivo(
            nome="Período AJ31 Beta", data_inicio=DATA_INI, data_fim=DATA_FIM,
            unidade_id=un_b.id, ativo=True,
        )
        per_global = PeriodoLetivo(
            nome="Período AJ31 sem unidade", data_inicio=DATA_INI,
            data_fim=DATA_FIM, unidade_id=None, ativo=True,
        )
        per_hist = PeriodoLetivo(
            nome="Período AJ31 encerrado", data_inicio=date(2019, 2, 2),
            data_fim=DATA_FIM_ENCERRADO, unidade_id=un_a.id, ativo=True,
        )
        per_sigla = PeriodoLetivo(
            nome="2026.2", data_inicio=DATA_INI, data_fim=DATA_FIM,
            unidade_id=un_sigla.id, ativo=True,
        )
        db.session.add_all([per_a, per_b, per_global, per_hist, per_sigla])
        db.session.flush()

        def _oferta(unidade_id, periodo_id, sufixo, *, ativo=True, turma_ativa=True):
            turma_id = _turma(
                unidade_id, periodo_id, f"Turma AJ31 {sufixo}", ativo=turma_ativa,
            )
            curso = Curso(
                nome=f"Curso AJ31 {sufixo}", unidade_id=unidade_id, ativo=True,
            )
            db.session.add(curso)
            db.session.flush()
            oferta = nova_oferta(
                turma_id, curso.id, unidade_id, programa="Esporte",
                principal=True, ativo=ativo,
            )
            return turma_id, oferta.id

        turma_a, oferta_a = _oferta(un_a.id, per_a.id, "A")
        turma_b, oferta_b = _oferta(un_b.id, per_b.id, "B")
        # Turma de B apontando para o mesmo período de A: prova a agregação
        # "Todas as unidades" sem trocar o período.
        turma_b2, oferta_b2 = _oferta(un_b.id, per_a.id, "B2")
        _, oferta_inativa = _oferta(
            un_a.id, per_a.id, "Oferta inativa", ativo=False,
        )
        turma_inativa, oferta_inativa_turma = _oferta(
            un_a.id, per_a.id, "Turma inativa", turma_ativa=False,
        )
        turma_hist, oferta_hist = _oferta(un_a.id, per_hist.id, "Histórico", ativo=False)

        # Seis valores do enum + NULL + sem conselho + etapa não FINAL.
        mapa = {
            "aprovado": SituacaoFinal.APROVADO.value,
            "participante": SituacaoFinal.PARTICIPANTE.value,
            "reprovado": SituacaoFinal.REPROVADO_POR_FALTAS.value,
            "desistente": SituacaoFinal.DESISTENTE.value,
            "evadido": SituacaoFinal.EVADIDO.value,
            "empregado": SituacaoFinal.EMPREGADO.value,
            "empregado2": SituacaoFinal.EMPREGADO.value,
        }
        alunos = {}
        for chave, situacao in mapa.items():
            aluno_id = _aluno(un_a.id, f"Aluno AJ31 {chave}")
            nova_inscricao(aluno_id, turma_a, oferta_a)
            _conselho(aluno_id, turma_a, oferta_a, un_a.id, situacao)
            alunos[chave] = aluno_id

        aluno_id = _aluno(un_a.id, "Aluno AJ31 nulo")
        nova_inscricao(aluno_id, turma_a, oferta_a)
        _conselho(aluno_id, turma_a, oferta_a, un_a.id, None)
        alunos["nulo"] = aluno_id

        aluno_id = _aluno(un_a.id, "Aluno AJ31 sem conselho")
        nova_inscricao(aluno_id, turma_a, oferta_a)
        alunos["sem_conselho"] = aluno_id

        aluno_id = _aluno(un_a.id, "Aluno AJ31 etapa inicial")
        nova_inscricao(aluno_id, turma_a, oferta_a)
        _conselho(
            aluno_id, turma_a, oferta_a, un_a.id,
            SituacaoFinal.APROVADO.value, EtapaConselho.INICIAL,
        )
        alunos["etapa_inicial"] = aluno_id

        # Fora da base: inscrição inativa, aluno inativo, turma inativa e
        # oferta inativa em período em andamento.
        aluno_id = _aluno(un_a.id, "Aluno AJ31 inscrição inativa")
        insc = nova_inscricao(aluno_id, turma_a, oferta_a)
        insc.ativo = False
        _conselho(aluno_id, turma_a, oferta_a, un_a.id, SituacaoFinal.APROVADO.value)
        alunos["insc_inativa"] = aluno_id

        aluno_id = _aluno(un_a.id, "Aluno AJ31 inativo", ativo=False)
        nova_inscricao(aluno_id, turma_a, oferta_a)
        _conselho(aluno_id, turma_a, oferta_a, un_a.id, SituacaoFinal.APROVADO.value)
        alunos["aluno_inativo"] = aluno_id

        aluno_id = _aluno(un_a.id, "Aluno AJ31 turma inativa")
        nova_inscricao(aluno_id, turma_inativa, oferta_inativa_turma)
        _conselho(
            aluno_id, turma_inativa, oferta_inativa_turma, un_a.id,
            SituacaoFinal.APROVADO.value,
        )
        alunos["turma_inativa"] = aluno_id

        aluno_id = _aluno(un_a.id, "Aluno AJ31 oferta inativa")
        nova_inscricao(aluno_id, _turma_da_oferta(oferta_inativa), oferta_inativa)
        _conselho(
            aluno_id, _turma_da_oferta(oferta_inativa), oferta_inativa, un_a.id,
            SituacaoFinal.APROVADO.value,
        )
        alunos["oferta_inativa"] = aluno_id

        # Conselho FINAL sem inscrição correspondente: não pode virar avaliado.
        aluno_id = _aluno(un_a.id, "Aluno AJ31 sem inscrição")
        _conselho(aluno_id, turma_a, oferta_a, un_a.id, SituacaoFinal.APROVADO.value)
        alunos["sem_inscricao"] = aluno_id

        # Oferta inativa em período ENCERRADO conta (regra M4 do enturmado).
        aluno_id = _aluno(un_a.id, "Aluno AJ31 histórico")
        nova_inscricao(aluno_id, turma_hist, oferta_hist)
        _conselho(
            aluno_id, turma_hist, oferta_hist, un_a.id,
            SituacaoFinal.PARTICIPANTE.value,
        )
        alunos["historico"] = aluno_id

        # Unidade B, mesma oferta do período de A (agregação global).
        aluno_b = _aluno(un_b.id, "Aluno AJ31 Beta")
        nova_inscricao(aluno_b, turma_b2, oferta_b2)
        _conselho(aluno_b, turma_b2, oferta_b2, un_b.id, SituacaoFinal.APROVADO.value)
        # Unidade B em período próprio (para o teste de 404).
        aluno_b2 = _aluno(un_b.id, "Aluno AJ31 Beta período próprio")
        nova_inscricao(aluno_b2, turma_b, oferta_b)
        _conselho(aluno_b2, turma_b, oferta_b, un_b.id, SituacaoFinal.APROVADO.value)

        db.session.commit()
        return {
            "un_a": un_a.id, "un_b": un_b.id, "un_sigla": un_sigla.id,
            "usuarios": {chave: u.id for chave, u in usuarios.items()},
            "periodo": per_a.id, "periodo_b": per_b.id,
            "periodo_global": per_global.id, "periodo_hist": per_hist.id,
            "periodo_sigla": per_sigla.id,
            "turma_a": turma_a, "oferta_a": oferta_a,
            "alunos": alunos,
        }


def _turma_da_oferta(oferta_id):
    from app.models import TurmaCurso
    return db.session.get(TurmaCurso, oferta_id).turma_id


# ---------------------------------------------------------------------------
# Serviço — base única e regras 2a-2j
# ---------------------------------------------------------------------------

def _dados(app, ids, *, unidade_id="mesma"):
    with app.app_context():
        uid = ids["un_a"] if unidade_id == "mesma" else unidade_id
        return servico.obter_informacoes_gerais_periodo(ids["periodo"], uid)


def test_base_unica_contagens_e_pendentes_derivados(app):
    ids = _setup(app)
    dados = _dados(app, ids)

    # 10 pares inscritos: 6 enum + nulo + sem conselho + etapa inicial
    # + 2º Empregado. Os quatro pares fora da base não entram.
    assert dados["total_inscritos"] == 10
    assert dados["total_avaliados"] == 7
    assert dados["pendentes_definicao"] == 3  # nulo, sem conselho, etapa INICIAL

    contagens = {i["situacao"]: i["quantidade"] for i in dados["indicadores"]}
    assert contagens[SituacaoFinal.APROVADO.value] == 1
    assert contagens[SituacaoFinal.PARTICIPANTE.value] == 1
    assert contagens[SituacaoFinal.REPROVADO_POR_FALTAS.value] == 1
    assert contagens[SituacaoFinal.DESISTENTE.value] == 1
    assert contagens[SituacaoFinal.EVADIDO.value] == 1
    assert contagens[SituacaoFinal.EMPREGADO.value] == 2
    assert sum(contagens.values()) == dados["total_avaliados"]


def test_conselho_fora_da_base_nao_conta_e_pendentes_sem_max_zero(app):
    ids = _setup(app)
    dados = _dados(app, ids)
    # O Conselho FINAL do aluno sem inscrição não aparece: se contasse,
    # total_avaliados seria 8 e pendentes 2.
    assert dados["total_avaliados"] == 7
    assert dados["pendentes_definicao"] == 3
    assert dados["total_inscritos"] - dados["total_avaliados"] == dados["pendentes_definicao"]


def test_filtros_ativo_oferta_efetiva_e_historico(app):
    ids = _setup(app)
    # Oferta inativa em período em andamento não conta; a inativa em período
    # encerrado conta pela regra M4 (reexportada por cond_oferta_efetiva).
    com_hist = _dados(app, ids, unidade_id=None)
    assert com_hist["total_inscritos"] == 11  # 10 de A + 1 de B no mesmo período

    with app.app_context():
        historico = servico.obter_informacoes_gerais_periodo(ids["periodo_hist"], ids["un_a"])
    assert historico["total_inscritos"] == 1
    assert historico["total_avaliados"] == 1
    assert historico["pendentes_definicao"] == 0


def test_unidade_filter_e_visao_global_agregam_as_duas_unidades(app):
    ids = _setup(app)
    so_a = _dados(app, ids, unidade_id=ids["un_a"])
    so_b = _dados(app, ids, unidade_id=ids["un_b"])
    global_it = _dados(app, ids, unidade_id=None)

    assert so_a["total_inscritos"] == 10
    assert so_b["total_inscritos"] == 1
    assert global_it["total_inscritos"] == so_a["total_inscritos"] + so_b["total_inscritos"]
    assert global_it["total_avaliados"] == 8
    assert global_it["pendentes_definicao"] == 3


def test_vocabulario_vem_do_enum_e_percentual_tem_uma_casa(app):
    ids = _setup(app)
    dados = _dados(app, ids)
    assert [i["situacao"] for i in dados["indicadores"]] == list(SITUACAO_FINAL_OPCOES)
    por_situacao = {i["situacao"]: i for i in dados["indicadores"]}
    assert por_situacao[SituacaoFinal.APROVADO.value]["percentual"] == 14.3
    assert por_situacao[SituacaoFinal.EMPREGADO.value]["percentual"] == 28.6


def test_config_e_apresentacao_valor_novo_usa_padrao(monkeypatch):
    assert servico._apresentacao("ValorNaoCatalogado")["rotulo"] == "ValorNaoCatalogado"
    assert servico._apresentacao("ValorNaoCatalogado")["cor"] == "secondary"
    monkeypatch.setattr(servico, "_CONFIG_SITUACOES", {})
    apresentacao = servico._apresentacao(SituacaoFinal.EVADIDO.value)
    assert apresentacao["rotulo"] == SituacaoFinal.EVADIDO.value
    assert apresentacao["cor"] == "secondary"


def test_valor_gravado_fora_da_config_nao_e_descartado(app, monkeypatch):
    ids = _setup(app)
    # Simula um valor novo gravado antes de a config de apresentação existir:
    # some das opções conhecidas e da config, mas continua nos indicadores.
    monkeypatch.setattr(
        servico, "SITUACAO_FINAL_OPCOES",
        tuple(v for v in SITUACAO_FINAL_OPCOES if v != SituacaoFinal.EMPREGADO.value),
    )
    cfg = dict(servico._CONFIG_SITUACOES)
    cfg.pop(SituacaoFinal.EMPREGADO)
    monkeypatch.setattr(servico, "_CONFIG_SITUACOES", cfg)

    with app.app_context():
        dados = servico.obter_informacoes_gerais_periodo(ids["periodo"], ids["un_a"])
    empregado = next(
        i for i in dados["indicadores"]
        if i["situacao"] == SituacaoFinal.EMPREGADO.value
    )
    assert empregado["quantidade"] == 2
    assert empregado["rotulo"] == SituacaoFinal.EMPREGADO.value  # presentation padrão


def test_aproveitamento_favoraveis_sobre_avaliados(app):
    ids = _setup(app)
    dados = _dados(app, ids)
    ap = dados["aproveitamento"]
    assert ap["quantidade"] == 2  # Aprovado + Participante
    assert ap["percentual"] == 28.6
    assert "Aprovados ou Participantes" in ap["formula"]
    assert "situação final definida" in ap["formula"]
    assert "AJ30" not in ap["legenda"] and "Concluído" not in ap["legenda"]


def test_estado_vazio_sem_divisao_por_zero(app):
    ids = _setup(app)
    with app.app_context():
        dados = servico.obter_informacoes_gerais_periodo(ids["periodo_global"], None)
    assert dados["total_inscritos"] == 0
    assert dados["total_avaliados"] == 0
    assert dados["pendentes_definicao"] == 0
    assert all(i["percentual"] == 0.0 for i in dados["indicadores"])
    assert dados["aproveitamento"]["percentual"] is None


# ---------------------------------------------------------------------------
# Rota — acesso, isolamento e renderização
# ---------------------------------------------------------------------------

def _get(client, ids, periodo=None, unidade="un_a"):
    sufixo = f"/relatorios/periodo/{periodo or ids['periodo']}/informacoes-gerais"
    if unidade == "global":
        login_as(client, ids["usuarios"]["global"])
    else:
        login_as(client, ids["usuarios"]["admin"], ids["un_a"])
    return client.get(sufixo)


def test_acesso_negado_a_perfil_fora_de_roles_relatorios(app):
    ids = _setup(app)
    cliente = app.test_client()
    login_as(cliente, ids["usuarios"]["prof"], ids["un_a"])
    resposta = cliente.get(f"/relatorios/periodo/{ids['periodo']}/informacoes-gerais")
    assert resposta.status_code == 403


def test_404_para_periodo_inexistente_e_de_outra_unidade(app):
    ids = _setup(app)
    cliente = app.test_client()
    login_as(cliente, ids["usuarios"]["admin"], ids["un_a"])
    assert cliente.get("/relatorios/periodo/999999/informacoes-gerais").status_code == 404
    assert cliente.get(
        f"/relatorios/periodo/{ids['periodo_b']}/informacoes-gerais"
    ).status_code == 404


def test_visao_global_agrega_e_mostra_todas_as_unidades(app):
    ids = _setup(app)
    cliente = app.test_client()
    resposta = _get(cliente, ids, unidade="global")
    assert resposta.status_code == 200
    html = resposta.get_data(as_text=True)
    assert "Todas as unidades" in html
    assert "<strong>11</strong>" in html  # inscritos de A + B
    assert "<strong>8</strong>" in html  # avaliados de A + B


def test_periodo_sem_unidade_e_descrito_sem_erro(app):
    ids = _setup(app)
    cliente = app.test_client()
    resposta = _get(cliente, ids, periodo=ids["periodo_global"], unidade="global")
    assert resposta.status_code == 200
    html = resposta.get_data(as_text=True)
    assert "Período AJ31 sem unidade" in html
    assert "Todas as unidades" in html
    assert MENSAGEM_VAZIA in html


def test_render_com_massa_tem_totais_textos_novos_e_valores(app):
    ids = _setup(app)
    html = _get(app.test_client(), ids).get_data(as_text=True)
    assert MENSAGEM_VAZIA not in html
    assert "Inscrições no período:" in html
    assert "Com situação final definida:" in html
    assert "Sem situação final definida:" in html
    assert "Distribuição das situações finais" in html
    assert "<strong>10</strong>" in html
    assert "<strong>7</strong>" in html
    assert "<strong>3</strong>" in html
    assert "28,6%" in html
    assert "14,3%" in html
    assert "2 de 7 alunos Aprovados ou Participantes" in html
    assert (
        "Resultado parcial: 3 de 10 inscrições ainda não têm situação final definida. "
        "Os percentuais abaixo consideram apenas os 7 alunos com situação já definida."
    ) in html
    conteudo = re.search(r'<div id="conteudo-impressao".*?</div>\s*</main>', html, re.S)
    assert conteudo, "conteúdo do relatório ausente"
    texto_relatorio = conteudo.group(0)
    assert "sem certificação integral" not in texto_relatorio
    # Nomes/sementes e o data-pdf-nome podem conter "AJ31"; os textos antigos não.
    assert "Concluído vale como Aprovado" not in texto_relatorio
    assert "(AJ30)" not in texto_relatorio
    assert "Aprovado + Participante ÷" not in texto_relatorio
    assert "Concluído" not in texto_relatorio


def test_estado_vazio_mantem_totais_mensagem_e_traco(app):
    ids = _setup(app)
    html = _get(app.test_client(), ids, periodo=ids["periodo_global"]).get_data(as_text=True)
    assert MENSAGEM_VAZIA in html
    assert "Inscrições no período:" in html
    assert "Com situação final definida:" in html
    assert "Sem situação final definida:" in html
    assert "Distribuição das situações finais" in html
    assert "—" in html
    assert "0,0%" in html
    assert "Resultado parcial" not in html
    assert "AJ30" not in html and "Concluído" not in html


# ---------------------------------------------------------------------------
# Impressão / JS / contratos vizinhos
# ---------------------------------------------------------------------------

def test_cabecalho_e_rodape_de_impressao_padrao(app):
    ids = _setup(app)
    html = _get(app.test_client(), ids).get_data(as_text=True)
    cabecalho = re.search(
        r'<header[^>]*resultado-print-header.*?</header>', html, re.S,
    )
    assert cabecalho, "cabeçalho print-only ausente"
    bloco = cabecalho.group(0)
    assert "logo_irn.png" in bloco
    assert "Logo institucional" in bloco
    assert UN_A_NOME in bloco
    assert "Informações Gerais do Período" in bloco
    linha = re.search(r"Unidade:.*?Período:.*?\(.*?\)", bloco, re.S)
    assert linha, "a identificação deve caber em UMA linha"
    assert "Emitido em" in bloco and "resultado-emissao" in bloco
    assert "Colaborador:" in bloco and "Admin AJ31" in bloco
    assert "print-footer-container" in html and 'id="print-date"' in html
    assert "{{ app_version }}" not in html
    assert "foto" not in bloco.lower()


def test_css_proprio_a4_retrato_sem_css_do_resultado(app):
    ids = _setup(app)
    html = _get(app.test_client(), ids).get_data(as_text=True)
    assert "css/relatorios/informacoes_gerais_periodo.css" in html
    assert "css/relatorios/resultado_conselho.css" not in html

    css = app.test_client().get(
        "/static/css/relatorios/informacoes_gerais_periodo.css"
    ).get_data(as_text=True)
    assert css.count("@page") == 1
    assert "size: A4 portrait" in css
    assert "print-color-adjust: exact" in css
    assert "break-inside: avoid" in css


def test_js_apenas_impressao_e_modulo_aj29(app):
    ids = _setup(app)
    html = _get(app.test_client(), ids).get_data(as_text=True)
    assert "js/relatorios/resultado_conselho.js" not in html
    assert html.count("js/impressao_pdf.js") == 1
    assert 'data-pdf-nome="Informacoes-Gerais-Periodo_' in html
    assert "prepararImpressao" in html
    assert "beforeprint" in html
    assert "exportarCSV" not in html
    assert "oferta_sel" not in html


def test_contratos_aj26_aj27_aj28_permanezem_intactos(app):
    html = (RAIZ / "app/templates/relatorios/resultado_conselho.html").read_text(
        encoding="utf-8"
    )
    assert "resultado-print-header" in html
    assert "Período do Conselho" in html
    assert "Conceito" in html
    assert "loop.changed((linha.turma, linha.oferta))" in html
    css = (RAIZ / "app/static/css/relatorios/resultado_conselho.css").read_text(
        encoding="utf-8"
    )
    assert "@page" in css and "size: A4 landscape" in css


def test_botao_entrada_sem_periodo_e_com_periodo(app):
    ids = _setup(app)
    cliente = app.test_client()
    login_as(cliente, ids["usuarios"]["admin"], ids["un_a"])

    sem = cliente.get("/relatorios/conselho").get_data(as_text=True)
    botao = re.search(
        r'<a id="btnInfoGeraisPeriodo"(.*?)>(.*?)</a>', sem, re.S
    )
    assert botao, "botão de informações gerais ausente"
    cabecalho = botao.group(1)
    assert 'href="#"' in cabecalho
    assert "disabled" in cabecalho and 'aria-disabled="true"' in cabecalho
    assert "d-print-none" in cabecalho
    assert "Informações Gerais do Período" in botao.group(2)

    com = cliente.get(
        "/relatorios/conselho",
        query_string={"periodo_letivo_id": ids["periodo"]},
    ).get_data(as_text=True)
    botao = re.search(r'<a id="btnInfoGeraisPeriodo"(.*?)>', com, re.S)
    assert botao
    esperado = f"/relatorios/periodo/{ids['periodo']}/informacoes-gerais"
    assert f'href="{esperado}"' in botao.group(1)
    assert "disabled" not in botao.group(1)


def test_js_atualiza_href_e_desabilitado_ao_trocar_periodo():
    origem = (RAIZ / "app/templates/relatorios/resultado_conselho.html").read_text(
        encoding="utf-8"
    )
    assert "btnInfo.href = baseUrl.replace" in origem
    assert 'btnInfo.setAttribute("disabled", "")' in origem
    assert 'btnInfo.removeAttribute("disabled")' in origem
    assert 'btnInfo.setAttribute("aria-disabled", "true")' in origem


# ---------------------------------------------------------------------------
# AJ31-C — bloco de impressão próprio e textos de apresentação
# ---------------------------------------------------------------------------

def test_bloco_impressao_proprio_tabela_seis_situacoes_e_total(app):
    ids = _setup(app)
    html = _get(app.test_client(), ids).get_data(as_text=True)
    bloco = re.search(r'<section class="print-only info-print">.*?</section>', html, re.S)
    assert bloco, "bloco de impressão próprio ausente"
    impresso = bloco.group(0)
    assert "resultado-print-header" in impresso
    assert "Inscrições no período" in impresso
    assert "Com situação final definida" in impresso
    assert "Sem situação final definida" in impresso
    assert "2 de 7 alunos Aprovados ou Participantes" in impresso
    tabela = re.search(r'<table class="info-print-tabela">.*?</table>', impresso, re.S)
    assert tabela, "tabela de distribuição ausente"
    corpo = re.search(r"<tbody>.*?</tbody>", tabela.group(0), re.S).group(0)
    assert corpo.count("<tr") == 7  # seis situações + total
    assert "O que significa" in tabela.group(0)
    assert "Distribuição das situações finais" in tabela.group(0)
    for descricao in (
        "Concluiu o curso com aproveitamento",
        "Participou do curso",
        "Frequência abaixo do mínimo exigido",
        "Cancelou a matrícula",
        "Deixou de frequentar sem formalizar a saída",
        "Inserido no mercado de trabalho",
    ):
        assert descricao in corpo
    assert "Total com situação definida" in corpo
    assert "100,0%" in corpo
    assert (
        "Percentuais calculados sobre os alunos com situação final definida."
        in impresso
    )
    assert "Aproveitamento = alunos Aprovados ou Participantes ÷ alunos com situação final definida." in impresso
    assert 'class="card card-executivo shadow-sm border-0 mx-auto mb-4 d-print-none"' in html
    assert html.index("print-only info-print") < html.index("card card-executivo")


def test_css_esconde_layout_app_com_os_seletores_do_padrao(app):
    cliente = app.test_client()
    css = cliente.get("/static/css/relatorios/informacoes_gerais_periodo.css").get_data(as_text=True)
    seletores = (
        ".app-topbar", ".app-sidebar", ".sidebar-backdrop", "nav", ".navbar",
        ".sidebar", "#sidebarMenu", "footer", ".btn", ".no-print",
        ".d-print-none", ".alert", ".modal", ".modal-backdrop",
        ".filter-card", ".status-card", "body.sidebar-collapsed .app-main",
        "#conteudo-impressao .card.d-print-none",
    )
    for seletor in seletores:
        assert seletor in css, f"seletor de impressão ausente: {seletor}"
    assert css.count("@page") == 1
    assert "size: A4 portrait" in css
    assert "margin: 1cm" in css
    assert "A4 landscape" not in css
    assert "print-color-adjust: exact" in css
    assert "break-inside: avoid" in css


def test_unidade_com_nome_igual_a_sigla_nao_duplica_no_cabecalho(app):
    ids = _setup(app)
    cliente = app.test_client()
    login_as(cliente, ids["usuarios"]["sigla"], ids["un_sigla"])
    html = cliente.get(
        f"/relatorios/periodo/{ids['periodo_sigla']}/informacoes-gerais"
    ).get_data(as_text=True)
    assert "Unidade: MGB" in html
    assert "MGB (MGB)" not in html
    assert "Período: 2026.2" in html


def test_sem_pendentes_nao_tem_aviso_parcial_e_total_e_100(app):
    ids = _setup(app)
    html = _get(app.test_client(), ids, periodo=ids["periodo_hist"]).get_data(as_text=True)
    assert "Resultado parcial" not in html
    assert "Total com situação definida" in html
    assert "100,0%" in html


def test_descricoes_de_apresentacao_nao_trazem_regra_de_negocio():
    esperado = {
        SituacaoFinal.APROVADO.value: "Concluiu o curso com aproveitamento",
        SituacaoFinal.PARTICIPANTE.value: "Participou do curso",
        SituacaoFinal.REPROVADO_POR_FALTAS.value: "Frequência abaixo do mínimo exigido",
        SituacaoFinal.DESISTENTE.value: "Cancelou a matrícula",
        SituacaoFinal.EVADIDO.value: "Deixou de frequentar sem formalizar a saída",
        SituacaoFinal.EMPREGADO.value: "Inserido no mercado de trabalho",
    }
    for valor, descricao in esperado.items():
        assert servico._apresentacao(valor)["descricao"] == descricao
        assert "certificação" not in servico._apresentacao(valor)["descricao"].lower()
        assert "certificação" not in servico._apresentacao(valor)["legenda"].lower()
