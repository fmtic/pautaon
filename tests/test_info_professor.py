# ruff: noqa: F811
"""I1 — endpoint `GET /aluno/<id>/info-professor`.

Regra ÚNICA de acesso (serviço `app/services/aluno_info_professor.py`), usada
pelo endpoint, pela pauta de frequência (ícone) e pela pauta impressa:

    existe inscrição do aluno com inscrição ativa, aluno ativo, oferta ativa,
    turma ativa, professor efetivo da oferta = usuário
    (`coalesce(oferta.professor_id, turma.professor_id)`), turma na unidade do
    usuário e período letivo NÃO encerrado (`data_fim` nula ou >= hoje).

Blocos exibidos, cada um só quando preenchido: ``acompanhante``
(`Aluno.acompanhante_aulas` + flag `vai_acompanhado_aulas`, igual à impressão)
e ``instrucoes`` (`PerfilDiversidade.informacoes_para_professor`).
Medicação e idade NUNCA entram na resposta.
"""

from datetime import date

import pytest
from _helpers import login_as
from _i1_helpers import (
    conteudo,
    desativar_inscricao,
    dois_blocos,
    info,
    mudar,
    seed,
)

from app import db
from app.models import Aluno, Turma, TurmaCurso
from _helpers import nova_inscricao


# ---------------------------------------------------------------------------
# 200 — professor da oferta, inscrição ativa, período vigente
# ---------------------------------------------------------------------------

def test_professor_da_oferta_ve_os_dois_blocos(app, client):
    ids = seed(app)
    dois_blocos(app, ids["aluno"])
    login_as(client, ids["prof"], ids["un"])

    resposta = info(client, ids["aluno"])

    assert resposta.status_code == 200
    dados = resposta.get_json()
    assert dados["aluno_id"] == ids["aluno"]
    assert dados["nome"] == "Aluno I1 0"
    assert dados["acompanhante"] == "Mãe"
    assert dados["instrucoes"] == "Usa óculos e precisa de lugar na frente."


def test_so_acompanhante_preenchido(app, client):
    ids = seed(app)
    conteudo(app, ids["aluno"], acompanhante="Avô/Avó", vai=True)
    login_as(client, ids["prof"], ids["un"])

    dados = info(client, ids["aluno"]).get_json()

    assert dados["acompanhante"] == "Avô/Avó"
    assert dados["instrucoes"] is None


def test_so_instrucoes_preenchidas(app, client):
    ids = seed(app)
    conteudo(app, ids["aluno"], instrucoes="Conversar antes das aulas.")
    login_as(client, ids["prof"], ids["un"])

    dados = info(client, ids["aluno"]).get_json()

    assert dados["acompanhante"] is None
    assert dados["instrucoes"] == "Conversar antes das aulas."


def test_periodo_futuro_libera(app, client):
    """Período que ainda vai começar ENTRA."""
    ids = seed(app, dias_inicio=10, dias_fim=40)
    dois_blocos(app, ids["aluno"])
    login_as(client, ids["prof"], ids["un"])

    assert info(client, ids["aluno"]).status_code == 200


def test_turma_sem_periodo_letivo_libera(app, client):
    """Sem período na turma não há data de fim para encerrar (branch NULL)."""
    ids = seed(app)
    dois_blocos(app, ids["aluno"])
    mudar(app, Turma, ids["t1"], periodo_letivo_id=None)
    login_as(client, ids["prof"], ids["un"])

    assert info(client, ids["aluno"]).status_code == 200


def test_aluno_em_duas_ofertas_uma_qualificada(app, client):
    """Inscrição na turma de outro professor não atrapalha a qualificada."""
    ids = seed(app)
    dois_blocos(app, ids["aluno"])
    with app.app_context():
        nova_inscricao(ids["aluno"], ids["t2"], ids["o3"])
        db.session.commit()
    login_as(client, ids["prof"], ids["un"])

    assert info(client, ids["aluno"]).status_code == 200


def test_acompanhante_exige_a_flag_auxiliar(app, client):
    """Mesma regra da impressão: sem `vai_acompanhado_aulas` não há bloco."""
    ids = seed(app)
    conteudo(app, ids["aluno"], acompanhante="Mãe", vai=False)
    login_as(client, ids["prof"], ids["un"])

    assert info(client, ids["aluno"]).status_code == 404


def test_sem_nenhum_bloco_devolve_404(app, client):
    ids = seed(app)
    conteudo(app, ids["aluno"], acompanhante="", vai=False, instrucoes="   ")
    login_as(client, ids["prof"], ids["un"])

    assert info(client, ids["aluno"]).status_code == 404


def test_aluno_inexistente_devolve_404(app, client):
    ids = seed(app)
    login_as(client, ids["prof"], ids["un"])

    assert info(client, 999999).status_code == 404


# ---------------------------------------------------------------------------
# 403 — sem inscrição qualificada
# ---------------------------------------------------------------------------

def test_outra_turma_devolve_403(app, client):
    ids = seed(app)
    dois_blocos(app, ids["aluno"])
    login_as(client, ids["outro"], ids["un"])

    assert info(client, ids["aluno"]).status_code == 403


def test_mesma_turma_outra_oferta_devolve_403(app, client):
    """`outro` leciona a oferta O2 da T1, mas o aluno está só na O1."""
    ids = seed(app)
    dois_blocos(app, ids["aluno"])
    login_as(client, ids["outro"], ids["un"])

    assert info(client, ids["aluno"]).status_code == 403


def test_oferta_inativa_devolve_403(app, client):
    ids = seed(app)
    dois_blocos(app, ids["aluno"])
    mudar(app, TurmaCurso, ids["o1"], ativo=False)
    login_as(client, ids["prof"], ids["un"])

    assert info(client, ids["aluno"]).status_code == 403


def test_turma_inativa_devolve_403(app, client):
    ids = seed(app)
    dois_blocos(app, ids["aluno"])
    mudar(app, Turma, ids["t1"], ativo=False)
    login_as(client, ids["prof"], ids["un"])

    assert info(client, ids["aluno"]).status_code == 403


def test_inscricao_inativa_devolve_403(app, client):
    ids = seed(app)
    dois_blocos(app, ids["aluno"])
    desativar_inscricao(app, ids["aluno"])
    login_as(client, ids["prof"], ids["un"])

    assert info(client, ids["aluno"]).status_code == 403


def test_aluno_inativo_devolve_403(app, client):
    ids = seed(app)
    dois_blocos(app, ids["aluno"])
    mudar(app, Aluno, ids["aluno"], ativo=False)
    login_as(client, ids["prof"], ids["un"])

    assert info(client, ids["aluno"]).status_code == 403


def test_periodo_encerrado_devolve_403_mesmo_com_inscricao_ativa(app, client):
    ids = seed(app, dias_inicio=-60, dias_fim=-1)
    dois_blocos(app, ids["aluno"])
    login_as(client, ids["prof"], ids["un"])

    assert info(client, ids["aluno"]).status_code == 403


def test_professor_de_outra_unidade_devolve_403(app, client):
    """O professor da oferta existe, mas a turma está em outra unidade."""
    ids = seed(app)
    dois_blocos(app, ids["aluno"])
    with app.app_context():
        nova_inscricao(ids["aluno"], ids["t3"], ids["o4"])
        db.session.commit()
    login_as(client, ids["prof_un2"], ids["un"])

    assert info(client, ids["aluno"]).status_code == 403


@pytest.mark.parametrize(
    "perfil", ["admin", "pedagogico", "secretaria", "gerencia", "servico_social"],
)
def test_perfis_que_nao_sao_professor_recebem_403(app, client, perfil):
    ids = seed(app)
    dois_blocos(app, ids["aluno"])
    login_as(client, ids[perfil], ids["un"])

    assert info(client, ids["aluno"]).status_code == 403


# ---------------------------------------------------------------------------
# Conteúdo e cabeçalhos
# ---------------------------------------------------------------------------

def test_medicacao_e_idade_nunca_aparecem(app, client):
    ids = seed(app)
    conteudo(
        app, ids["aluno"],
        acompanhante="Mãe", vai=True, instrucoes="Precisa de apoio.",
        medicacao="Sim", medicamento="Ritalina", nascimento=date(2012, 5, 4),
    )
    login_as(client, ids["prof"], ids["un"])

    resposta = info(client, ids["aluno"])
    corpo = resposta.get_data(as_text=True)

    assert "Ritalina" not in corpo
    assert "Medicação" not in corpo
    assert "Idade" not in corpo
    assert set(resposta.get_json()) == {
        "aluno_id", "nome", "acompanhante", "instrucoes",
    }


def test_cache_control_no_store(app, client):
    ids = seed(app)
    dois_blocos(app, ids["aluno"])
    login_as(client, ids["prof"], ids["un"])

    assert info(client, ids["aluno"]).headers["Cache-Control"] == "no-store"


def test_textos_com_html_nao_sao_interpretados(app, client):
    texto = "<script>alert('xss')</script>\nsegunda linha"
    ids = seed(app)
    conteudo(app, ids["aluno"], instrucoes=texto)
    login_as(client, ids["prof"], ids["un"])

    resposta = info(client, ids["aluno"])
    dados = resposta.get_json()

    # JSON com texto puro (sem entidades HTML) e quebras preservadas: a tela
    # renderiza por `textContent` + `white-space: pre-wrap`.
    assert dados["instrucoes"] == texto
    assert "\\n" in resposta.get_data(as_text=True)
