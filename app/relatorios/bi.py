"/app/relatorios/bi.py"

"""Camada de execução dos indicadores do BI do pautaON."""

from . import bi_alunos
from .catalogo import obter_indicador

INDICADORES_ALUNOS = {
    "ALU-001": bi_alunos.total_alunos,
    "ALU-002": bi_alunos.alunos_ativos,
    "ALU-003": bi_alunos.alunos_inativos,
    "ALU-004": bi_alunos.novos_alunos,
    "ALU-007": bi_alunos.alunos_pcd,
    "ALU-008": bi_alunos.alunos_por_unidade,
    "ALU-009": bi_alunos.alunos_por_curso,
    "ALU-010": bi_alunos.alunos_por_turma,
    "INS-001": bi_alunos.total_inscricoes,
    "INS-002": bi_alunos.inscricoes_ativas,
    "INS-003": bi_alunos.inscricoes_encerradas,
    "INS-004": bi_alunos.novas_inscricoes,
    "INS-005": bi_alunos.inscricoes_desativadas,
}


def executar_indicador(codigo, **filtros):
    """Executa um indicador previamente cadastrado no catálogo."""

    indicador = obter_indicador(codigo)

    if indicador is None:
        raise ValueError(f"Indicador '{codigo}' não existe no catálogo.")

    funcao = INDICADORES_ALUNOS.get(codigo)

    if funcao is None:
        raise ValueError(
            f"Indicador '{codigo}' está no catálogo, " "mas ainda não foi implementado."
        )

    return funcao(**filtros)
