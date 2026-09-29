"/app/relatorios/bi.py"

"""Camada de execução dos indicadores do BI do pautaON."""

from . import bi_alunos
from .catalogo import obter_indicador

INDICADORES_ALUNOS = {
    "ALU-001": bi_alunos.total_alunos,
    "ALU-002": bi_alunos.alunos_ativos,
    "ALU-003": bi_alunos.alunos_inativos,
    "ALU-004": bi_alunos.novos_alunos,
    "ALU-005": bi_alunos.alunos_sexo,
    "ALU-006": bi_alunos.alunos_por_faixa_etaria,
    "ALU-007": bi_alunos.alunos_pcd,
    "ALU-008": bi_alunos.alunos_por_unidade,
    "ALU-009": bi_alunos.alunos_por_curso,
    "ALU-010": bi_alunos.alunos_por_turma,
    "INS-001": bi_alunos.total_inscricoes,
    "INS-002": bi_alunos.inscricoes_ativas,
    "INS-003": bi_alunos.inscricoes_encerradas,
    "INS-004": bi_alunos.novas_inscricoes,
    "INS-005": bi_alunos.inscricoes_desativadas,
    #INS-006 → motivo da desativação → não implementado, pois não há dados
    #INS-007 → tempo médio de permanência → não implementado, pois não há registros com data_desativacao
    "INS-008": bi_alunos.inscricoes_por_curso,
    "FRE-001": bi_alunos.total_lancamentos_frequencia,
    "FRE-002": bi_alunos.total_presencas,
    "FRE-003": bi_alunos.total_faltas,
    "FRE-004": bi_alunos.total_faltas_justificadas,
    "FRE-005": bi_alunos.frequencia_media,
    "FRE-006": bi_alunos.alunos_frequencia_90,
    "FRE-007": bi_alunos.alunos_frequencia_75_89,
    "FRE-008": bi_alunos.alunos_frequencia_inferior_75,
    "FRE-009": bi_alunos.frequencia_por_turma,
    "FRE-010": bi_alunos.frequencia_por_curso,
    "TUR-001": bi_alunos.total_turmas,
    "TUR-002": bi_alunos.turmas_ativas,
    "TUR-003": bi_alunos.alunos_por_turma,
    "TUR-004": bi_alunos.media_alunos_por_turma,
    "TUR-005": bi_alunos.turmas_por_curso,
    "TUR-006": bi_alunos.turmas_por_periodo,
    "TUR-007": bi_alunos.turmas_por_unidade,
    "TUR-008": bi_alunos.turmas_por_professor,
    "AUL-001": bi_alunos.total_aulas_registradas,
    "AUL-002": bi_alunos.aulas_por_turma,
    "AUL-003": bi_alunos.aulas_por_periodo,
    "AUL-004": bi_alunos.aulas_por_professor,
    "AUL-005": bi_alunos.aulas_por_curso,
    "AUL-006": bi_alunos.aulas_por_unidade,
    "AUL-007": bi_alunos.aulas_por_tema,
    "AUL-008": bi_alunos.aulas_por_dia,
    "SOC-001": bi_alunos.alunos_por_faixa_renda,
    "SOC-002": bi_alunos.alunos_beneficiarios_programas_sociais,
    "DIV-001": bi_alunos.alunos_por_tipo_deficiencia,
    "ATD-001": bi_alunos.total_atendimentos,
    "CRU-001": bi_alunos.frequencia_critica_por_vulnerabilidade,
    "CRU-002": bi_alunos.alunos_raca_conselho,
    "CRU-003": bi_alunos.sem_internet_por_bairro_zona,
    "CRU-004": bi_alunos.transferencias_por_curso,
    "CRU-005": bi_alunos.desempenho_conselho_por_renda,
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







