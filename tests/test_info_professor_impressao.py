# ruff: noqa: F811
"""I1 — pauta impressa: acompanhante e instruções sob a regra de acesso.

Antes do I1 as duas linhas saíam para o professor dono da turma em qualquer
situação (inclusive período encerrado — caracterização registrada no relatório
I1 com o worktree de HEAD). Depois do I1 elas seguem a MESMA regra do endpoint:
professor efetivo da oferta, inscrição/turma/oferta ativas, turma na unidade e
período não encerrado. Medicação continua inalterada.
"""

from _helpers import login_as
from _i1_helpers import conteudo, dois_blocos, impressao, seed
from test_conselho_oferta import app, client  # noqa: F401


def _com_medicacao(app, ids):
    dois_blocos(app, ids["aluno"])
    conteudo(app, ids["aluno"], medicacao="Sim", medicamento="Ritalina")


def test_impressao_professor_com_acesso_imprime_os_dois_blocos(app, client):
    """Antes = depois: o contrato do professor dono da turma não muda."""
    ids = seed(app)
    _com_medicacao(app, ids)
    login_as(client, ids["prof"], ids["un"])

    corpo = impressao(client, ids).get_data(as_text=True)

    assert "Quem acompanha:" in corpo
    assert "Usa óculos e precisa de lugar na frente." in corpo
    assert "Medicação regular" in corpo


def test_impressao_professor_sem_acesso_omite_blocos_mantem_medicacao(app, client):
    """Antes imprimia; agora (período encerrado) as duas linhas não saem."""
    ids = seed(app, dias_inicio=-60, dias_fim=-1)
    _com_medicacao(app, ids)
    login_as(client, ids["prof"], ids["un"])

    corpo = impressao(client, ids).get_data(as_text=True)

    assert "Quem acompanha:" not in corpo
    assert "Usa óculos e precisa de lugar na frente." not in corpo
    assert "Medicação regular" in corpo


def test_impressao_admin_imprime_os_dois_blocos(app, client):
    """Outros perfis: inalterado."""
    ids = seed(app)
    _com_medicacao(app, ids)
    login_as(client, ids["admin"], ids["un"])

    corpo = impressao(client, ids).get_data(as_text=True)

    assert "Quem acompanha:" in corpo
    assert "Usa óculos e precisa de lugar na frente." in corpo
    assert "Medicação regular" in corpo
