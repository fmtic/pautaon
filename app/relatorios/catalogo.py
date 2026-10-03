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
especializados de app/relatorios/.
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
        "nome": "Total de alunos com cadastro ativo no período",
        "categoria": "alunos",
        "tipo": "contagem",
        "unidade": "alunos",
        "fonte": "Aluno / Inscricao / Turma / PeriodoLetivo",
        "dimensoes": [
            "unidade",
            "sexo",
            "faixa_etaria",
        ],
    },
    "ALU-002": {
        "nome": "Alunos com cadastro ativo",
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
        "nome": "Alunos com cadastro inativo",
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
        "nome": "Novos cadastros",
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
        "nome": "Alunos enturmados por sexo",
        "categoria": "alunos",
        "tipo": "distribuicao",
        "unidade": "alunos",
        "fonte": "Aluno / Inscricao / Turma / PeriodoLetivo / PerfilDiversidade",
        "dimensoes": [
            "unidade",
            "sexo",
        ],
    },
    "ALU-006": {
        "nome": "Alunos enturmados por faixa etária",
        "categoria": "alunos",
        "tipo": "distribuicao",
        "unidade": "alunos",
        "fonte": "Aluno / Inscricao / Turma / PeriodoLetivo",
        "dimensoes": [
            "unidade",
            "faixa_etaria",
        ],
    },
    "ALU-007": {
        "nome": "Alunos PCD enturmados",
        "categoria": "alunos",
        "tipo": "contagem",
        "unidade": "alunos",
        "fonte": "Aluno / Inscricao / Turma / PeriodoLetivo / PerfilDiversidade",
        "dimensoes": [
            "unidade",
            "sexo",
            "faixa_etaria",
        ],
    },
    "ALU-008": {
        "nome": "Alunos cadastrados por unidade",
        "categoria": "alunos",
        "tipo": "distribuicao",
        "unidade": "alunos",
        "fonte": "Aluno / Unidade",
        "dimensoes": [
            "unidade",
        ],
    },
    "ALU-009": {
        "nome": "Alunos enturmados por curso",
        "categoria": "alunos",
        "tipo": "distribuicao",
        "unidade": "alunos",
        "fonte": "Aluno / Inscricao / Turma / Curso / PeriodoLetivo",
        "dimensoes": [
            "unidade",
            "periodo",
            "curso",
        ],
    },
    "ALU-010": {
        "nome": "Alunos enturmados por turma",
        "categoria": "alunos",
        "tipo": "distribuicao",
        "unidade": "alunos",
        "fonte": "Aluno / Inscricao / Turma / PeriodoLetivo",
        "dimensoes": [
            "unidade",
            "periodo",
            "curso",
            "turma",
        ],
    },
    "ALU-011": {
        "nome": "Alunos enturmados no período",
        "categoria": "alunos",
        "tipo": "contagem",
        "unidade": "alunos",
        "fonte": "Aluno / Inscricao / Turma / PeriodoLetivo",
        "dimensoes": ["unidade", "periodo"],
    },
    "ALU-012": {
        "nome": "Alunos não enturmados no período",
        "categoria": "alunos",
        "tipo": "contagem",
        "unidade": "alunos",
        "fonte": "Aluno / Inscricao / Turma / PeriodoLetivo",
        "dimensoes": ["unidade", "periodo"],
    },
    "ALU-013": {
        "nome": "Alunos novos no período",
        "categoria": "alunos",
        "tipo": "contagem",
        "unidade": "alunos",
        "fonte": "Aluno / Inscricao / Turma / PeriodoLetivo",
        "dimensoes": ["unidade", "periodo"],
    },
    "ALU-014": {
        "nome": "Alunos renovados",
        "categoria": "alunos",
        "tipo": "contagem",
        "unidade": "alunos",
        "fonte": "Aluno / Inscricao / Turma / PeriodoLetivo",
        "dimensoes": ["unidade", "periodo"],
    },
    "ALU-015": {
        "nome": "Alunos retornantes",
        "categoria": "alunos",
        "tipo": "contagem",
        "unidade": "alunos",
        "fonte": "Aluno / Inscricao / Turma / PeriodoLetivo",
        "dimensoes": ["unidade", "periodo"],
    },
    "ALU-016": {
        "nome": "Alunos não renovados",
        "categoria": "alunos",
        "tipo": "contagem",
        "unidade": "alunos",
        "fonte": "Aluno / Inscricao / Turma / PeriodoLetivo",
        "dimensoes": ["unidade", "periodo"],
    },
    "ALU-017": {
        "nome": "Alunos em janela de renovação",
        "categoria": "alunos",
        "tipo": "contagem",
        "unidade": "alunos",
        "fonte": "Aluno / Inscricao / Turma / PeriodoLetivo",
        "dimensoes": ["unidade", "periodo"],
    },
    "ALU-018": {
        "nome": "Alunos desenturmados",
        "categoria": "alunos",
        "tipo": "contagem",
        "unidade": "alunos",
        "fonte": "Aluno / Inscricao / Turma / PeriodoLetivo",
        "dimensoes": ["unidade", "periodo"],
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
    # -------------------------------------------------------------------------
    # AULAS
    # -------------------------------------------------------------------------
    "AUL-001": {
        "nome": "Total de aulas registradas",
        "categoria": "aulas",
        "tipo": "contagem",
        "unidade": "aulas",
        "fonte": "RegistroAula",
        "dimensoes": [
            "unidade",
            "periodo",
            "curso",
            "turma",
            "professor",
        ],
    },
    "AUL-002": {
        "nome": "Aulas por turma",
        "categoria": "aulas",
        "tipo": "distribuicao",
        "unidade": "aulas",
        "fonte": "RegistroAula / Turma",
        "dimensoes": [
            "unidade",
            "periodo",
            "curso",
            "turma",
        ],
    },
    "AUL-003": {
        "nome": "Aulas por período",
        "categoria": "aulas",
        "tipo": "distribuicao",
        "unidade": "aulas",
        "fonte": "RegistroAula / Turma / PeriodoLetivo",
        "dimensoes": [
            "unidade",
            "periodo",
        ],
    },
    "AUL-004": {
        "nome": "Aulas por professor",
        "categoria": "aulas",
        "tipo": "distribuicao",
        "unidade": "aulas",
        "fonte": "RegistroAula / Turma / User",
        "dimensoes": [
            "unidade",
            "periodo",
            "professor",
        ],
    },
    "AUL-005": {
        "nome": "Aulas por curso",
        "categoria": "aulas",
        "tipo": "distribuicao",
        "unidade": "aulas",
        "fonte": "RegistroAula / Turma / Curso",
        "dimensoes": [
            "unidade",
            "periodo",
            "curso",
        ],
    },
    "AUL-006": {
        "nome": "Aulas por unidade",
        "categoria": "aulas",
        "tipo": "distribuicao",
        "unidade": "aulas",
        "fonte": "RegistroAula / Turma / Unidade",
        "dimensoes": ["unidade", "periodo"],
    },
    "AUL-007": {
        "nome": "Aulas por tema",
        "categoria": "aulas",
        "tipo": "distribuicao",
        "unidade": "aulas",
        "fonte": "RegistroAula / TemaAula",
        "dimensoes": [
            "unidade",
            "periodo",
            "curso",
            "turma",
        ],
    },
    "AUL-008": {
        "nome": "Aulas por dia",
        "categoria": "aulas",
        "tipo": "distribuicao",
        "unidade": "aulas",
        "fonte": "RegistroAula",
        "dimensoes": [
            "unidade",
            "periodo",
            "curso",
            "turma",
            "professor",
        ],
    },
    # -------------------------------------------------------------------------
    # SOCIOECONOMICO
    # -------------------------------------------------------------------------
    "SOC-001": {
        "nome": "Alunos por faixa de renda familiar",
        "categoria": "alunos",
        "tipo": "distribuicao",
        "unidade": "alunos",
        "fonte": "Aluno / PerfilSocioeconomico",
        "dimensoes": [
            "unidade",
            "periodo",
        ],
    },
    "SOC-002": {
        "nome": "Alunos beneficiários de programas sociais",
        "categoria": "alunos",
        "tipo": "contagem",
        "unidade": "alunos",
        "fonte": "Aluno / PerfilSocioeconomico",
        "dimensoes": [
            "unidade",
            "periodo",
        ],
    },
    "DIV-001": {
        "nome": "Alunos por tipo de deficiência",
        "categoria": "alunos",
        "tipo": "distribuicao",
        "unidade": "alunos",
        "fonte": "Aluno / PerfilDiversidade",
        "dimensoes": [
            "unidade",
            "periodo",
        ],
    },
    # -------------------------------------------------------------------------
    # ATENDIMENTO
    # -------------------------------------------------------------------------
    "ATD-001": {
        "nome": "Total de atendimentos",
        "categoria": "atendimento",
        "tipo": "contagem",
        "unidade": "atendimentos",
        "fonte": "Atendimento",
        "dimensoes": [
            "unidade",
            "periodo",
        ],
    },
    # -------------------------------------------------------------------------
    # INDICADORES CRUZADOS (CRU)
    # -------------------------------------------------------------------------
    "CRU-001": {
        "nome": "Frequência crítica (< 75%) por vulnerabilidade social",
        "categoria": "frequencia",
        "tipo": "distribuicao",
        "unidade": "alunos",
        "fonte": "Frequencia / PerfilSocioeconomico",
        "dimensoes": ["unidade", "periodo", "curso", "turma"],
    },
    "CRU-002": {
        "nome": "Alunos por raça/cor no Conselho de Classe",
        "categoria": "conselho",
        "tipo": "distribuicao",
        "unidade": "alunos",
        "fonte": "ConselhoClasse / PerfilDiversidade",
        "dimensoes": ["unidade", "periodo", "curso", "turma"],
    },
    "CRU-003": {
        "nome": "Alunos sem acesso à internet por bairro e zona",
        "categoria": "alunos",
        "tipo": "distribuicao",
        "unidade": "alunos",
        "fonte": "Aluno / EnderecoAluno",
        "dimensoes": ["unidade", "periodo"],
    },
    "CRU-004": {
        "nome": "Transferências por curso de origem",
        "categoria": "matriculas",
        "tipo": "distribuicao",
        "unidade": "transferências",
        "fonte": "Transferencia / Turma / Curso",
        "dimensoes": ["unidade", "periodo", "curso"],
    },
    "CRU-005": {
        "nome": "Desempenho no Conselho de Classe por faixa de renda",
        "categoria": "conselho",
        "tipo": "distribuicao",
        "unidade": "alunos",
        "fonte": "ConselhoClasse / PerfilSocioeconomico",
        "dimensoes": ["unidade", "periodo", "curso", "turma"],
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
