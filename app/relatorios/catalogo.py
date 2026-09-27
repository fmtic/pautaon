"""
Catálogo de indicadores do módulo de Relatórios e BI do pautaON.

Responsabilidades deste módulo:
    - definir os indicadores disponíveis;
    - definir as dimensões de análise;
    - definir os tipos de resultado;
    - identificar a fonte conceitual de cada indicador;
    - disponibilizar presets para a interface.

Este módulo NÃO deve:
    - executar consultas ao banco;
    - importar modelos SQLAlchemy;
    - aplicar filtros;
    - calcular indicadores;
    - conhecer regras específicas de apresentação.

As consultas e regras de cálculo serão implementadas nos módulos
especializados de app/services/relatorios/.
"""

# =============================================================================
# TIPOS DE RESULTADO
# =============================================================================

TIPOS_RESULTADO = {
    "contagem": "Contagem",
    "soma": "Soma",
    "media": "Média",
    "percentual": "Percentual",
    "taxa": "Taxa",
    "distribuicao": "Distribuição",
    "comparacao": "Comparação",
    "evolucao": "Evolução",
}


# =============================================================================
# DIMENSÕES
# =============================================================================

DIMENSOES = {
    "unidade": {
        "nome": "Unidade",
    },
    "periodo": {
        "nome": "Período letivo",
    },
    "curso": {
        "nome": "Curso",
    },
    "turma": {
        "nome": "Turma",
    },
    "professor": {
        "nome": "Professor",
    },
    "aluno": {
        "nome": "Aluno",
    },
    "sexo": {
        "nome": "Sexo",
    },
    "faixa_etaria": {
        "nome": "Faixa etária",
    },
    "situacao": {
        "nome": "Situação",
    },
}


# =============================================================================
# INDICADORES
# =============================================================================

INDICADORES = {
    # -------------------------------------------------------------------------
    # ALUNOS
    # -------------------------------------------------------------------------
    "ALU-001": {
        "nome": "Total de alunos",
        "categoria": "alunos",
        "tipo": "contagem",
        "unidade": "alunos",
        "fonte": "Aluno",
        "dimensoes": [
            "unidade",
            "sexo",
            "faixa_etaria",
        ],
    },
    "ALU-002": {
        "nome": "Alunos ativos",
        "categoria": "alunos",
        "tipo": "contagem",
        "unidade": "alunos",
        "fonte": "Aluno",
        "dimensoes": [
            "unidade",
            "sexo",
            "faixa_etaria",
        ],
    },
    "ALU-003": {
        "nome": "Alunos inativos",
        "categoria": "alunos",
        "tipo": "contagem",
        "unidade": "alunos",
        "fonte": "Aluno",
        "dimensoes": [
            "unidade",
            "sexo",
            "faixa_etaria",
            "situacao",
        ],
    },
    "ALU-004": {
        "nome": "Novos alunos",
        "categoria": "alunos",
        "tipo": "contagem",
        "unidade": "alunos",
        "fonte": "Aluno",
        "dimensoes": [
            "unidade",
            "periodo",
            "sexo",
            "faixa_etaria",
        ],
    },
    "ALU-005": {
        "nome": "Alunos por sexo",
        "categoria": "alunos",
        "tipo": "distribuicao",
        "unidade": "alunos",
        "fonte": "Aluno",
        "dimensoes": [
            "unidade",
            "sexo",
        ],
    },
    "ALU-006": {
        "nome": "Alunos por faixa etária",
        "categoria": "alunos",
        "tipo": "distribuicao",
        "unidade": "alunos",
        "fonte": "Aluno",
        "dimensoes": [
            "unidade",
            "faixa_etaria",
        ],
    },
    "ALU-007": {
        "nome": "Alunos PCD",
        "categoria": "alunos",
        "tipo": "contagem",
        "unidade": "alunos",
        "fonte": "Aluno / PerfilDiversidade",
        "dimensoes": [
            "unidade",
            "sexo",
            "faixa_etaria",
        ],
    },
    "ALU-008": {
        "nome": "Alunos por unidade",
        "categoria": "alunos",
        "tipo": "distribuicao",
        "unidade": "alunos",
        "fonte": "Aluno / Unidade",
        "dimensoes": [
            "unidade",
        ],
    },
    "ALU-009": {
        "nome": "Alunos por curso",
        "categoria": "alunos",
        "tipo": "distribuicao",
        "unidade": "alunos",
        "fonte": "Aluno / Inscricao / Turma / Curso",
        "dimensoes": [
            "unidade",
            "periodo",
            "curso",
        ],
    },
    "ALU-010": {
        "nome": "Alunos por turma",
        "categoria": "alunos",
        "tipo": "distribuicao",
        "unidade": "alunos",
        "fonte": "Aluno / Inscricao / Turma",
        "dimensoes": [
            "unidade",
            "periodo",
            "curso",
            "turma",
        ],
    },
    # -------------------------------------------------------------------------
    # INSCRIÇÕES
    # -------------------------------------------------------------------------
    "INS-001": {
        "nome": "Total de inscrições",
        "categoria": "inscricoes",
        "tipo": "contagem",
        "unidade": "inscrições",
        "fonte": "Inscricao",
        "dimensoes": [
            "unidade",
            "periodo",
            "curso",
            "turma",
        ],
    },
    "INS-002": {
        "nome": "Inscrições ativas",
        "categoria": "inscricoes",
        "tipo": "contagem",
        "unidade": "inscrições",
        "fonte": "Inscricao",
        "dimensoes": [
            "unidade",
            "periodo",
            "curso",
            "turma",
        ],
    },
    "INS-003": {
        "nome": "Inscrições encerradas",
        "categoria": "inscricoes",
        "tipo": "contagem",
        "unidade": "inscrições",
        "fonte": "Inscricao",
        "dimensoes": [
            "unidade",
            "periodo",
            "curso",
            "turma",
            "situacao",
        ],
    },
    "INS-004": {
        "nome": "Novas inscrições",
        "categoria": "inscricoes",
        "tipo": "contagem",
        "unidade": "inscrições",
        "fonte": "Inscricao",
        "dimensoes": [
            "unidade",
            "periodo",
            "curso",
            "turma",
        ],
    },
    "INS-005": {
        "nome": "Desativações",
        "categoria": "inscricoes",
        "tipo": "contagem",
        "unidade": "inscrições",
        "fonte": "Inscricao",
        "dimensoes": [
            "unidade",
            "periodo",
            "curso",
            "turma",
        ],
    },
    "INS-006": {
        "nome": "Motivos de desativação",
        "categoria": "inscricoes",
        "tipo": "distribuicao",
        "unidade": "inscrições",
        "fonte": "Inscricao",
        "dimensoes": [
            "unidade",
            "periodo",
            "curso",
            "turma",
            "situacao",
        ],
    },
    "INS-007": {
        "nome": "Tempo médio de permanência",
        "categoria": "inscricoes",
        "tipo": "media",
        "unidade": "dias",
        "fonte": "Inscricao",
        "dimensoes": [
            "unidade",
            "periodo",
            "curso",
            "turma",
        ],
    },
    "INS-008": {
        "nome": "Inscrições por curso",
        "categoria": "inscricoes",
        "tipo": "distribuicao",
        "unidade": "inscrições",
        "fonte": "Inscricao / Turma / Curso",
        "dimensoes": [
            "unidade",
            "periodo",
            "curso",
        ],
    },
    # -------------------------------------------------------------------------
    # FREQUÊNCIA
    # -------------------------------------------------------------------------
    "FRE-001": {
        "nome": "Total de lançamentos de frequência",
        "categoria": "frequencia",
        "tipo": "contagem",
        "unidade": "lançamentos",
        "fonte": "Frequencia",
        "dimensoes": [
            "unidade",
            "periodo",
            "curso",
            "turma",
            "professor",
        ],
    },
    "FRE-002": {
        "nome": "Total de presenças",
        "categoria": "frequencia",
        "tipo": "contagem",
        "unidade": "presenças",
        "fonte": "Frequencia",
        "dimensoes": [
            "unidade",
            "periodo",
            "curso",
            "turma",
            "professor",
        ],
    },
    "FRE-003": {
        "nome": "Total de faltas",
        "categoria": "frequencia",
        "tipo": "contagem",
        "unidade": "faltas",
        "fonte": "Frequencia",
        "dimensoes": [
            "unidade",
            "periodo",
            "curso",
            "turma",
            "professor",
        ],
    },
    "FRE-004": {
        "nome": "Total de faltas justificadas",
        "categoria": "frequencia",
        "tipo": "contagem",
        "unidade": "faltas justificadas",
        "fonte": "Frequencia",
        "dimensoes": [
            "unidade",
            "periodo",
            "curso",
            "turma",
            "professor",
        ],
    },
    "FRE-005": {
        "nome": "Frequência média",
        "categoria": "frequencia",
        "tipo": "media",
        "unidade": "%",
        "fonte": "Frequencia",
        "dimensoes": [
            "unidade",
            "periodo",
            "curso",
            "turma",
            "professor",
        ],
    },
    "FRE-006": {
        "nome": "Alunos com frequência igual ou superior a 90%",
        "categoria": "frequencia",
        "tipo": "contagem",
        "unidade": "alunos",
        "fonte": "Frequencia",
        "dimensoes": [
            "unidade",
            "periodo",
            "curso",
            "turma",
        ],
    },
    "FRE-007": {
        "nome": "Alunos com frequência entre 75% e 89%",
        "categoria": "frequencia",
        "tipo": "contagem",
        "unidade": "alunos",
        "fonte": "Frequencia",
        "dimensoes": [
            "unidade",
            "periodo",
            "curso",
            "turma",
        ],
    },
    "FRE-008": {
        "nome": "Alunos com frequência inferior a 75%",
        "categoria": "frequencia",
        "tipo": "contagem",
        "unidade": "alunos",
        "fonte": "Frequencia",
        "dimensoes": [
            "unidade",
            "periodo",
            "curso",
            "turma",
        ],
    },
    "FRE-009": {
        "nome": "Frequência por turma",
        "categoria": "frequencia",
        "tipo": "distribuicao",
        "unidade": "%",
        "fonte": "Frequencia / Turma",
        "dimensoes": [
            "unidade",
            "periodo",
            "curso",
            "turma",
        ],
    },
    "FRE-010": {
        "nome": "Frequência por curso",
        "categoria": "frequencia",
        "tipo": "distribuicao",
        "unidade": "%",
        "fonte": "Frequencia / Turma / Curso",
        "dimensoes": [
            "unidade",
            "periodo",
            "curso",
        ],
    },
    # -------------------------------------------------------------------------
    # TURMAS
    # -------------------------------------------------------------------------
    "TUR-001": {
        "nome": "Total de turmas",
        "categoria": "turmas",
        "tipo": "contagem",
        "unidade": "turmas",
        "fonte": "Turma",
        "dimensoes": [
            "unidade",
            "periodo",
            "curso",
            "professor",
            "situacao",
        ],
    },
    "TUR-002": {
        "nome": "Turmas ativas",
        "categoria": "turmas",
        "tipo": "contagem",
        "unidade": "turmas",
        "fonte": "Turma",
        "dimensoes": [
            "unidade",
            "periodo",
            "curso",
            "professor",
        ],
    },
    "TUR-003": {
        "nome": "Alunos por turma",
        "categoria": "turmas",
        "tipo": "distribuicao",
        "unidade": "alunos",
        "fonte": "Turma / Inscricao",
        "dimensoes": [
            "unidade",
            "periodo",
            "curso",
            "turma",
        ],
    },
    "TUR-004": {
        "nome": "Média de alunos por turma",
        "categoria": "turmas",
        "tipo": "media",
        "unidade": "alunos/turma",
        "fonte": "Turma / Inscricao",
        "dimensoes": [
            "unidade",
            "periodo",
            "curso",
        ],
    },
    "TUR-005": {
        "nome": "Turmas por curso",
        "categoria": "turmas",
        "tipo": "distribuicao",
        "unidade": "turmas",
        "fonte": "Turma / Curso",
        "dimensoes": [
            "unidade",
            "periodo",
            "curso",
        ],
    },
    "TUR-006": {
        "nome": "Turmas por período",
        "categoria": "turmas",
        "tipo": "distribuicao",
        "unidade": "turmas",
        "fonte": "Turma / PeriodoLetivo",
        "dimensoes": [
            "unidade",
            "periodo",
        ],
    },
    "TUR-007": {
        "nome": "Turmas por unidade",
        "categoria": "turmas",
        "tipo": "distribuicao",
        "unidade": "turmas",
        "fonte": "Turma / Unidade",
        "dimensoes": [
            "unidade",
        ],
    },
    "TUR-008": {
        "nome": "Turmas por professor",
        "categoria": "turmas",
        "tipo": "distribuicao",
        "unidade": "turmas",
        "fonte": "Turma / User",
        "dimensoes": [
            "unidade",
            "periodo",
            "curso",
            "professor",
        ],
    },
}


# =============================================================================
# PRESETS
# =============================================================================

PRESETS = {
    "alunos": {
        "nome": "Visão Geral de Alunos",
        "indicadores": [
            "ALU-001",
            "ALU-002",
            "ALU-003",
            "ALU-004",
            "ALU-005",
            "ALU-006",
            "ALU-007",
            "ALU-008",
            "ALU-009",
            "ALU-010",
        ],
    },
    "inscricoes": {
        "nome": "Análise de Inscrições",
        "indicadores": [
            "INS-001",
            "INS-002",
            "INS-003",
            "INS-004",
            "INS-005",
            "INS-006",
            "INS-007",
            "INS-008",
        ],
    },
    "frequencia": {
        "nome": "Análise de Frequência",
        "indicadores": [
            "FRE-001",
            "FRE-002",
            "FRE-003",
            "FRE-004",
            "FRE-005",
            "FRE-006",
            "FRE-007",
            "FRE-008",
            "FRE-009",
            "FRE-010",
        ],
    },
    "turmas": {
        "nome": "Análise de Turmas",
        "indicadores": [
            "TUR-001",
            "TUR-002",
            "TUR-003",
            "TUR-004",
            "TUR-005",
            "TUR-006",
            "TUR-007",
            "TUR-008",
        ],
    },
}


# =============================================================================
# FUNÇÕES DE ACESSO AO CATÁLOGO
# =============================================================================


def obter_indicador(codigo):
    """
    Retorna a definição de um indicador.

    Args:
        codigo: Código do indicador, por exemplo ``ALU-001``.

    Returns:
        dict | None: definição do indicador ou None se não existir.
    """
    return INDICADORES.get(codigo)


def listar_indicadores():
    """
    Retorna todos os indicadores cadastrados.

    Returns:
        dict: catálogo completo de indicadores.
    """
    return INDICADORES


def listar_indicadores_por_categoria(categoria):
    """
    Retorna somente os indicadores de uma categoria.

    Args:
        categoria: Nome interno da categoria.

    Returns:
        dict: indicadores pertencentes à categoria.
    """
    return {
        codigo: indicador
        for codigo, indicador in INDICADORES.items()
        if indicador["categoria"] == categoria
    }


def obter_preset(nome):
    """
    Retorna a definição de um preset.

    Args:
        nome: Identificador interno do preset.

    Returns:
        dict | None: definição do preset ou None se não existir.
    """
    return PRESETS.get(nome)
