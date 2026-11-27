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
        "nome": "Alunos ativos no período (enturmados + não enturmados)",
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
        "nome": "Alunos com cadastro ativo (base cadastral)",
        "categoria": "alunos",
        "tipo": "contagem",
        "unidade": "alunos",
        "fonte": "Aluno / Inscricao / Turma / TurmaCurso",
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
        "fonte": "Aluno / Inscricao / Turma / TurmaCurso",
        "dimensoes": [
            "unidade",
            "sexo",
            "faixa_etaria",
            "situacao",
        ],
    },
    "ALU-004": {
        "nome": "Cadastros novos no intervalo (data de criação)",
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
        "fonte": "Aluno / Inscricao / Turma / TurmaCurso / PeriodoLetivo / PerfilDiversidade",
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
        "fonte": "Aluno / Inscricao / Turma / TurmaCurso / PeriodoLetivo",
        "dimensoes": [
            "unidade",
            "faixa_etaria",
        ],
    },
    "ALU-007": {
        "nome": "Alunos PCD enturmados no período (base P)",
        "categoria": "alunos",
        "tipo": "contagem",
        "unidade": "alunos",
        "fonte": "Aluno / Inscricao / Turma / TurmaCurso / PeriodoLetivo / PerfilDiversidade",
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
        "fonte": "Aluno / Inscricao / TurmaCurso / Curso / PeriodoLetivo",
        "descricao": (
            "Alunos enturmados (Aluno.ativo) contados como DISTINTOS dentro "
            "de cada curso; o curso vem da OFERTA da inscrição "
            "(TurmaCurso.curso_id). Um aluno matriculado em dois cursos conta "
            "uma vez em cada, de modo que a soma dos cursos pode exceder o "
            "total de alunos distintos da unidade."
        ),
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
        "fonte": "Aluno / Inscricao / TurmaCurso / Turma / PeriodoLetivo",
        "descricao": (
            "Cada aluno conta UMA vez por turma, mesmo inscrito em mais de "
            "uma oferta (curso/professor da oferta para o filtro)."
        ),
        "dimensoes": [
            "unidade",
            "periodo",
            "curso",
            "turma",
        ],
    },
    "ALU-011": {
        "nome": "Alunos enturmados no período (status P)",
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
        "nome": "Alunos novos no período (sem histórico na unidade)",
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
        "fonte": "Inscricao / Turma / TurmaCurso",
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
        "fonte": "Inscricao / Turma / TurmaCurso",
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
        "nome": "Inscrições no intervalo (código legado de INS-001)",
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
        "nome": "Inscrições inativas (código legado de INS-003)",
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
        "fonte": "Inscricao / TurmaCurso / Curso",
        "dimensoes": [
            "unidade",
            "periodo",
            "curso",
        ],
    },
    "INS-009": {
        "nome": "Inscrições iniciadas no período",
        "categoria": "inscricoes",
        "tipo": "contagem",
        "unidade": "inscrições",
        "fonte": "Inscricao / Turma / TurmaCurso / PeriodoLetivo",
        "dimensoes": [
            "unidade",
            "periodo",
            "curso",
            "turma",
            "professor",
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
        "fonte": "Frequencia / TurmaCurso",
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
        "fonte": "Frequencia / TurmaCurso",
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
        "fonte": "Frequencia / TurmaCurso",
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
        "fonte": "Frequencia / TurmaCurso",
        "dimensoes": [
            "unidade",
            "periodo",
            "curso",
            "turma",
            "professor",
        ],
    },
    "FRE-005": {
        "nome": "Frequência média ponderada por lançamentos",
        "categoria": "frequencia",
        "tipo": "media",
        "unidade": "%",
        "fonte": "Frequencia / TurmaCurso",
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
        "fonte": "Frequencia / TurmaCurso",
        "descricao": (
            "Faixa hi do serviço frequencia_oferta: percentual "
            "(presenças / (presenças+faltas), J fora) ARREDONDADO a 1 casa "
            "e >= 90. As três faixas (hi/mid/lo) somam exatamente o total de "
            "alunos com frequência contável."
        ),
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
        "fonte": "Frequencia / TurmaCurso",
        "descricao": (
            "Faixa mid do serviço frequencia_oferta: valor ARREDONDADO a 1 "
            "casa entre 75 e 89,9. Um 89,95 vira 90,0 e pertence à faixa hi."
        ),
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
        "fonte": "Frequencia / TurmaCurso",
        "descricao": (
            "Faixa lo do serviço frequencia_oferta: valor ARREDONDADO a 1 "
            "casa abaixo de 75."
        ),
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
        "fonte": "Frequencia / Turma / TurmaCurso",
        "descricao": (
            "Percentual POR TURMA sobre todas as suas linhas (inclusive "
            "legado); com filtro de curso/professor, as turmas são "
            "selecionadas pela OFERTA."
        ),
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
        "fonte": "Frequencia / TurmaCurso / Curso",
        "descricao": (
            "Agregação por curso usando apenas linhas da OFERTA; linhas "
            "legadas (turma_curso_id NULL) entram no curso quando a oferta é "
            "a única ativa da turma (regra D2), caso contrário só nos totais "
            "da unidade/turma."
        ),
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
        "nome": "Turmas ativas (código legado de TUR-002)",
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
        "nome": "Alunos por turma (código legado de ALU-010)",
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
        "nome": "Média de alunos distintos por turma",
        "categoria": "turmas",
        "tipo": "media",
        "unidade": "alunos/turma",
        "fonte": "Turma / Aluno / Inscricao / TurmaCurso",
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
        "fonte": "RegistroAula / TurmaCurso",
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
        "fonte": "RegistroAula / Turma / TurmaCurso",
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
        "fonte": "RegistroAula / TurmaCurso / User",
        "descricao": (
            "Distribuição pelo PROFESSOR DA OFERTA do registro "
            "(TurmaCurso.professor_id); registros legados (turma_curso_id "
            "NULL) seguem a oferta única ativa da turma (regra D2)."
        ),
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
        "fonte": "RegistroAula / TurmaCurso / Curso",
        "descricao": (
            "Distribuição pelo CURSO DA OFERTA do registro; registros "
            "legados entram só quando a oferta é a única ativa da turma "
            "(regra D2)."
        ),
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
        "nome": "Alunos com perfil PCD por tipo (todos os cadastros)",
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
        "fonte": "Atendimento / Inscricao / Turma / TurmaCurso",
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
        "fonte": "Frequencia / TurmaCurso / PerfilSocioeconomico",
        "dimensoes": ["unidade", "periodo", "curso", "turma"],
    },
    "CRU-002": {
        "nome": "Alunos por raça/cor no Conselho de Classe",
        "categoria": "conselho",
        "tipo": "distribuicao",
        "unidade": "alunos",
        "fonte": "ConselhoClasse / TurmaCurso / PerfilDiversidade",
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
        "fonte": "ConselhoClasse / TurmaCurso / PerfilSocioeconomico",
        "dimensoes": ["unidade", "periodo", "curso", "turma"],
    },
}


# =============================================================================
# ALIASES E VISIBILIDADE DA CENTRAL (AJ33)
# =============================================================================
#
# Nenhum código é apagado ou reutilizado. Os códigos abaixo continuam
# resolvendo normalmente pela API e pela exportação XLSX; apenas não são
# oferecidos na lista da Central, para evitar cartões duplicados. A prova de
# equivalência (mesmos filtros, mesmos dados) está em
# docs/Relatórios/AJ33_GuiaIndicadoresBI.md.

VERSAO_CATALOGO = "1.2"
ULTIMA_REVISAO_CATALOGO = "2026-11-27"

ALIASES = {
    "INS-004": "INS-001",   # mesma consulta, inclusive com intervalo de datas
    "INS-005": "INS-003",   # ambos contam inscrições inativas
    "TUR-001": "TUR-002",   # ambos contam somente turmas ativas
    "TUR-003": "ALU-010",   # aliases explícitos da mesma função
}

INDICADORES_INDISPONIVEIS = frozenset({"INS-006", "INS-007"})

CODIGOS_OCULTOS_DA_CENTRAL = frozenset(ALIASES) | INDICADORES_INDISPONIVEIS


def resolver_codigo(codigo):
    """Devolve o código canônico de `codigo`, aplicando aliases explícitos."""
    return ALIASES.get(codigo, codigo)


def eh_alias(codigo):
    """Indica se `codigo` é um código legado substituído por outro."""
    return codigo in ALIASES


def indicadores_visiveis_na_central():
    """Catálogo ordenado como hoje, sem aliases e sem indicadores indisponíveis."""
    return {
        codigo: indicador
        for codigo, indicador in INDICADORES.items()
        if codigo not in CODIGOS_OCULTOS_DA_CENTRAL
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
            "INS-009",
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


# =============================================================================
# GUIA DE INDICADORES — TEXTO PARA O USUÁRIO (AJ33)
# =============================================================================
#
# Fonte única da verdade do guia: este módulo. Nenhum texto de AJxx aparece na
# interface; os números e as consultas dos indicadores não são definidos aqui.

FILTROS_POSSIVEIS = ("unidade", "periodo", "turno", "curso", "turma", "professor")

ROTULOS_FILTROS_GUIA = {
    "unidade": "Unidade",
    "periodo": "Período letivo",
    "turno": "Turno",
    "curso": "Curso",
    "turma": "Turma",
    "professor": "Professor",
}

GLOSSARIO_GUIA = (
    {
        "termo": "Cadastro novo × aluno novo",
        "texto": (
            "Cadastro novo é um registro recém-criado; aluno novo é quem não "
            "tinha inscrição em período anterior da mesma unidade. Não são sinônimos."
        ),
    },
    {
        "termo": '"Ativo" sempre qualificado',
        "texto": (
            "Cadastro ativo, inscrição ativa, turma ativa e oferta ativa são "
            "coisas diferentes. Quando o guia diz apenas \"ativo\", o campo está "
            "nomeado no indicador correspondente."
        ),
    },
    {
        "termo": "Inscrição x linha de lançamento",
        "texto": (
            "Indicadores de frequência e aulas contam linhas lançadas, não "
            "pessoas nem dias. Um aluno com vários lançamentos pesa várias vezes "
            "nos totais."
        ),
    },
    {
        "termo": "Regra D2 (lançamentos legados)",
        "texto": (
            "Linhas sem oferta vinculada entram no curso ou no professor quando "
            "a turma tem uma única oferta ativa; nos demais casos ficam só nos "
            "totais da unidade e da turma."
        ),
    },
    {
        "termo": "Outros",
        "texto": (
            "É o resíduo da classificação de enturmação: aluno ativo que não se "
            "enquadra em nenhuma das demais situações. Não é um tipo de inscrição."
        ),
    },
    {
        "termo": "Período P e P-1",
        "texto": (
            "P é o período de referência; P-1 é o período anterior da mesma "
            "unidade. Sem período escolhido, usa-se o vigente na data de hoje."
        ),
    },
    {
        "termo": "Arredondamento de percentual",
        "texto": (
            "As faixas de frequência usam o percentual arredondado a uma casa "
            "decimal antes de comparar com os limites."
        ),
    },
)


# -----------------------------------------------------------------------------
# AJUDA CONTEXTUAL DA CENTRAL — textos derivados deste catálogo
# -----------------------------------------------------------------------------
# A Central, o modal de cada indicador e o guia leem os mesmos dados abaixo.
# Nenhum número, consulta ou regra de cálculo é definido aqui.

FILTROS_CENTRAL = ("unidade", "periodo", "turno")

SIGLAS_CATEGORIA = {
    "ALU": "Alunos",
    "INS": "Inscrições",
    "FRE": "Frequência",
    "TUR": "Turmas",
    "AUL": "Aulas",
    "SOC": "Socioeconômico",
    "DIV": "Diversidade",
    "ATD": "Atendimento",
    "CRU": "Cruzados",
    "MAT": "Matrículas",
}

CATEGORIAS_AJUDA = (
    {"nome": "Alunos", "texto": "Cadastro e situação das pessoas atendidas."},
    {"nome": "Inscrições", "texto": "Vínculos das pessoas com ofertas de turma."},
    {"nome": "Frequência", "texto": "Lançamentos de presença, falta e conceitos."},
    {"nome": "Turmas", "texto": "Agrupamentos ativos por período, curso ou professor."},
    {"nome": "Aulas", "texto": "Registros de aula e suas dimensões."},
    {"nome": "Atendimento", "texto": "Atendimentos registrados às pessoas."},
    {"nome": "Conselho", "texto": "Resultados do conselho de classe cruzados com perfis."},
    {
        "nome": "Matrículas",
        "texto": "Movimentações de matrícula, como transferências entre cursos.",
    },
)

TIPOS_RESULTADO_AJUDA = (
    {"nome": "Contagem", "texto": "Um número total de registros ou pessoas."},
    {"nome": "Distribuição", "texto": "Valores agrupados por uma dimensão."},
    {"nome": "Média", "texto": "Total dividido pelo número de elementos do escopo."},
    {"nome": "Soma", "texto": "Total acumulado de valores."},
    {"nome": "Percentual", "texto": "Relação entre partes e total, em porcentagem."},
    {"nome": "Taxa", "texto": "Relação entre ocorrências e base de referência."},
    {"nome": "Comparação", "texto": "Valores lado a lado para contraste."},
    {"nome": "Evolução", "texto": "Valores ao longo do tempo."},
)

UNIDADES_MEDIDA_AJUDA = {
    "alunos": "Pessoas contadas uma vez, conforme a regra de cada indicador.",
    "inscrições": "Vínculos de uma pessoa com uma oferta de turma.",
    "lançamentos": "Linhas de frequência registradas, não pessoas.",
    "aulas": "Registros de aula lançados.",
    "turmas": "Turmas ativas do escopo.",
    "presenças": "Linhas de frequência com conceito de presença.",
    "faltas": "Linhas de frequência com conceito de falta simples.",
    "faltas justificadas": "Linhas de frequência com falta justificada.",
    "atendimentos": "Registros de atendimento.",
    "transferências": "Movimentações de matrícula entre cursos.",
    "dias": "Quantidade de dias, usada em médias de permanência.",
    "%": "Porcentagem sobre a base do indicador.",
    "alunos/turma": "Média de pessoas por turma ativa do escopo.",
}

FILTROS_AJUDA = {
    "unidade": "Restringe o escopo à unidade de ensino escolhida.",
    "periodo": "Seleciona o período letivo de referência; sem escolha, usa o vigente.",
    "turno": "Seleciona o turno, quando o indicador foi escrito para usá-lo.",
    "curso": "Filtra pelo curso da oferta da inscrição, não pelo campo legado.",
    "turma": "Restringe o resultado a uma turma específica.",
    "professor": "Filtra pelo professor da oferta da inscrição.",
}

TEXTO_COMPARTILHADO_AJUDA = (
    "A Central e o guia mostram o mesmo texto: ele vem do catálogo de indicadores."
)

TEXTO_FILTRO_NAO_APLICADO = "Este indicador não aplica o filtro de {rotulo}."

# Casos em que a assinatura da função não basta para descrever o filtro:
# o texto é a fonte única usada no aviso da Central, no modal e no guia.
FILTROS_PARCIAIS = {
    "ALU-009": {
        "turno": (
            "O filtro de turno seleciona a coorte, mas não restringe as "
            "inscrições usadas na distribuição por curso."
        ),
    },
    "AUL-006": {
        "periodo": "O filtro de período da Central não é repassado a este indicador.",
    },
}


def dados_ajuda_central():
    """Textos da ajuda contextual da Central, derivados do catálogo."""
    unidades = sorted({item["unidade"] for item in INDICADORES.values()})
    return {
        "siglas": [
            {"sigla": sigla, "nome": nome}
            for sigla, nome in SIGLAS_CATEGORIA.items()
        ],
        "categorias": [dict(item) for item in CATEGORIAS_AJUDA],
        "tipos": [dict(item) for item in TIPOS_RESULTADO_AJUDA],
        "unidades": [
            {
                "nome": unidade,
                "texto": UNIDADES_MEDIDA_AJUDA.get(unidade, "Unidade do indicador."),
            }
            for unidade in unidades
        ],
        "filtros": [
            {
                "chave": filtro,
                "rotulo": ROTULOS_FILTROS_GUIA[filtro],
                "texto": FILTROS_AJUDA[filtro],
            }
            for filtro in FILTROS_POSSIVEIS
        ],
        "texto_compartilhado": TEXTO_COMPARTILHADO_AJUDA,
        "texto_nao_aplicado": TEXTO_FILTRO_NAO_APLICADO,
    }


def sigla_do_codigo(codigo):
    """Sigla da categoria de um código (ex.: ALU de ALU-010)."""
    return codigo.split("-", 1)[0]


def titulo_sigla(codigo, categoria):
    """Texto curto para título/aria de um código exibido na Central."""
    sigla = sigla_do_codigo(codigo)
    nome = SIGLAS_CATEGORIA.get(sigla, sigla)
    if categoria and categoria.lower() != nome.lower():
        return f"{sigla} — {nome} · Categoria: {categoria.capitalize()}"
    return f"{sigla} — {nome}"


def _det(mede, regra, filtros, observacoes=(), relacionados=(), servico=None):
    """Monta um registro de texto do guia e infere os filtros não aplicáveis."""
    return {
        "mede": mede,
        "regra": regra,
        "filtros": tuple(filtros),
        "nao_aplicaveis": tuple(
            filtro for filtro in FILTROS_POSSIVEIS if filtro not in filtros
        ),
        "observacoes": tuple(observacoes),
        "relacionados": tuple(relacionados),
        "servico": servico or "Consulta direta do módulo de relatórios",
    }


GUIA_METADADOS = {
    # --- Alunos -------------------------------------------------------------
    "ALU-001": _det(
        "Quantos alunos com cadastro ativo fazem parte do escopo do período, "
        "incluindo enturmados e não enturmados.",
        "Conta cada aluno ativo classificado no período, somando as situações "
        "de enturmados e não enturmados. O resultado é igual a ALU-011 mais ALU-012.",
        ("unidade", "periodo", "turno"),
        observacoes=(
            '"Ativo" é o cadastro do aluno; a situação de enturmação é separada.',
        ),
        relacionados=(
            ("ALU-011", "conta só os enturmados no período"),
            ("ALU-012", "conta só os não enturmados no período"),
            ("ALU-002", "base cadastral, sem classificação por período"),
        ),
        servico="app.services.aluno_status",
    ),
    "ALU-002": _det(
        "Quantos alunos têm o cadastro ativo, independentemente da enturmação.",
        "Conta alunos com cadastro ativo. Quando há filtro de período, turma, "
        "curso ou professor, a presença de inscrição é usada apenas para selecionar "
        "esses alunos; a condição contada continua sendo a do cadastro.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        observacoes=(
            "Não mede enturmação: um aluno ativo sem vínculo no período entra.",
        ),
        relacionados=(
            ("ALU-001", "escopo do período, com classificação de situação"),
            ("ALU-011", "somente enturmados no período"),
            ("ALU-003", "cadastro inativo (complemento cadastral)"),
        ),
    ),
    "ALU-003": _det(
        "Quantos alunos têm o cadastro inativo.",
        "Conta alunos cujo cadastro está inativo. Não é a mesma coisa que "
        "inscrição encerrada ou aluno desenturmado.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        observacoes=("A condição é a do cadastro, não a do vínculo.",),
        relacionados=(("ALU-002", "cadastro ativo"), ("INS-003", "inscrições inativas")),
    ),
    "ALU-004": _det(
        "Quantos cadastros foram criados no intervalo escolhido.",
        "Conta registros de aluno pela data de criação dentro do intervalo. "
        "Não exige inscrição nem cadastro ativo; sem período explícito usa o "
        "período vigente de cada unidade.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        observacoes=(
            "É cadastro novo, não aluno novo no período (ALU-013).",
            "Registros sem data de criação não entram.",
            "Turno não se aplica: cadastro não tem vínculo que determine turno.",
        ),
        relacionados=(("ALU-013", "aluno novo pela história de inscrições"),),
    ),
    "ALU-005": _det(
        "Como os alunos enturmados se distribuem por gênero.",
        "Separa os alunos enturmados no período e agrupa pelo gênero declarado "
        "no perfil, usando o dado legado quando não há perfil estruturado.",
        ("unidade", "periodo", "turno", "curso", "turma", "professor"),
        observacoes=(
            "Com turno, a coorte vem das inscrições daquele turno; a "
            "classificação usa o histórico completo.",
        ),
        relacionados=(("ALU-011", "total de enturmados"), ("ALU-006", "distribuição por faixa etária")),
        servico="app.services.aluno_status",
    ),
    "ALU-006": _det(
        "Como os alunos enturmados se distribuem por faixa etária.",
        "Calcula a idade na data de referência e agrupa em faixas. Sem data de "
        "nascimento, o aluno aparece em Não Informado.",
        ("unidade", "periodo", "turno", "curso", "turma", "professor"),
        observacoes=(
            "As faixas são Menor de 12, 12 a 17, 18 a 24, 25 a 39, 40 a 59, "
            "60 ou mais e Não Informado.",
        ),
        relacionados=(("ALU-011", "total de enturmados"), ("ALU-005", "distribuição por gênero")),
        servico="app.services.aluno_status",
    ),
    "ALU-007": _det(
        "Quantos alunos enturmados no período são identificados como PCD.",
        "Dentro dos alunos enturmados, conta quem tem laudo de saúde marcado "
        "no perfil ou no dado legado.",
        ("unidade", "periodo", "turno", "curso", "turma", "professor"),
        observacoes=(
            "Base restrita aos enturmados: não é comparável com DIV-001.",
        ),
        relacionados=(("DIV-001", "todos os cadastros com perfil PCD, por tipo"),),
        servico="app.services.aluno_status",
    ),
    "ALU-008": _det(
        "Como os cadastros de alunos se distribuem entre unidades.",
        "Agrupa alunos pela unidade de ensino, sem exigir enturmação.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        relacionados=(("ALU-001", "alunos ativos no escopo do período"),),
    ),
    "ALU-009": _det(
        "Como os alunos enturmados se distribuem por curso.",
        "Conta alunos distintos dentro de cada curso da oferta da inscrição. "
        "Um aluno em dois cursos aparece uma vez em cada um.",
        ("unidade", "periodo", "turno", "curso", "turma", "professor"),
        observacoes=(
            "A soma dos cursos pode passar do total de alunos distintos.",
            "O curso vem da oferta, não do campo legado da turma.",
            "O filtro de turno seleciona a coorte, mas não restringe as inscrições "
            "usadas na distribuição por curso.",
        ),
        relacionados=(("ALU-010", "distribuição por turma"), ("ALU-011", "total de enturmados")),
        servico="app.services.aluno_status",
    ),
    "ALU-010": _det(
        "Como os alunos enturmados se distribuem por turma.",
        "Conta cada aluno uma vez por turma, mesmo com mais de uma inscrição. "
        "Com filtro de curso ou professor, a seleção usa a oferta da inscrição.",
        ("unidade", "periodo", "turno", "curso", "turma", "professor"),
        observacoes=(
            "Código canônico: TUR-003 é o mesmo indicador.",
            "Exige cadastro ativo e situação de enturmado no período.",
        ),
        relacionados=(("TUR-003", "código legado substituído"), ("ALU-009", "distribuição por curso")),
        servico="app.services.aluno_status",
    ),
    "ALU-011": _det(
        "Quantos alunos estão enturmados no período.",
        "Conta alunos com situação Novo, Renovado ou Retornante no período "
        "de referência.",
        ("unidade", "periodo", "turno"),
        observacoes=("Não inclui os não enturmados; para o total use ALU-001.",),
        relacionados=(
            ("ALU-001", "enturmados + não enturmados"),
            ("ALU-013", "somente os novos"),
            ("ALU-012", "somente os não enturmados"),
        ),
        servico="app.services.aluno_status",
    ),
    "ALU-012": _det(
        "Quantos alunos com cadastro ativo não estão enturmados no período.",
        "Conta as situações Em janela, Não renovado, Desenturmado e Outros.",
        ("unidade", "periodo", "turno"),
        observacoes=(
            "Outros é o resíduo da classificação, não um tipo de inscrição.",
        ),
        relacionados=(("ALU-001", "total do escopo"), ("ALU-011", "enturmados")),
        servico="app.services.aluno_status",
    ),
    "ALU-013": _det(
        "Quantos alunos enturmados no período são novos na unidade.",
        "Conta alunos enturmados no período que não tinham inscrição em "
        "período anterior da mesma unidade.",
        ("unidade", "periodo", "turno"),
        observacoes=("Não é ALU-004, que olha a data de criação do cadastro.",),
        relacionados=(("ALU-004", "cadastros criados no intervalo"), ("ALU-011", "total de enturmados")),
        servico="app.services.aluno_status",
    ),
    "ALU-014": _det(
        "Quantos alunos renovaram a enturmação no período.",
        "Conta alunos enturmados no período anterior cuja primeira inscrição "
        "no período atual ocorreu nos primeiros quatorze dias.",
        ("unidade", "periodo", "turno"),
        observacoes=(
            "Pode coincidir com ALU-018 em bases pequenas, mas mede outra coisa.",
        ),
        relacionados=(("ALU-018", "desenturmados, com histórico e sem vínculo atual"),),
        servico="app.services.aluno_status",
    ),
    "ALU-015": _det(
        "Quantos alunos voltaram a estudar após um intervalo.",
        "Conta alunos enturmados no período com histórico anterior que não "
        "se enquadram como renovados.",
        ("unidade", "periodo", "turno"),
        servico="app.services.aluno_status",
    ),
    "ALU-016": _det(
        "Quantos alunos não renovaram depois de encerrada a janela.",
        "Conta alunos enturmados no período anterior, sem vínculo vigente no "
        "período atual, após o fim da janela de renovação.",
        ("unidade", "periodo", "turno"),
        servico="app.services.aluno_status",
    ),
    "ALU-017": _det(
        "Quantos alunos estão na janela de renovação.",
        "Conta alunos enturmados no período anterior, sem vínculo vigente no "
        "período atual, enquanto a janela ainda está aberta.",
        ("unidade", "periodo", "turno"),
        servico="app.services.aluno_status",
    ),
    "ALU-018": _det(
        "Quantos alunos foram desenturmados no período.",
        "Conta alunos com inscrição histórica no período, mas sem vínculo "
        "vigente na data de referência.",
        ("unidade", "periodo", "turno"),
        observacoes=(
            "Pode coincidir com ALU-014 em bases pequenas; as regras são distintas.",
        ),
        relacionados=(("ALU-014", "renovados dentro dos primeiros quatorze dias"),),
        servico="app.services.aluno_status",
    ),
    # --- Inscrições ---------------------------------------------------------
    "INS-001": _det(
        "Quantas inscrições existem no escopo escolhido.",
        "Conta todas as inscrições em turmas ativas, com ou sem vínculo ativo.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        observacoes=(
            "Código canônico: INS-004 é o mesmo indicador.",
            "Curso e professor vêm da oferta da inscrição.",
        ),
        relacionados=(("INS-002", "somente inscrições ativas"), ("INS-003", "somente inativas")),
    ),
    "INS-002": _det(
        "Quantas inscrições estão ativas.",
        "Conta inscrições com vínculo ativo em turmas ativas.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        relacionados=(("INS-001", "todas as inscrições"), ("INS-003", "inscrições inativas")),
    ),
    "INS-003": _det(
        "Quantas inscrições estão encerradas.",
        "Conta inscrições com vínculo inativo em turmas ativas.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        observacoes=("Código canônico: INS-005 é o mesmo indicador.",),
        relacionados=(("INS-005", "código legado substituído"), ("INS-001", "todas as inscrições")),
    ),
    "INS-004": _det(
        "Quantas inscrições existem no intervalo escolhido.",
        "Conta todas as inscrições em turmas ativas; o intervalo, quando "
        "informado, filtra a data de início da inscrição.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        observacoes=(
            "Código legado substituído por INS-001: a consulta é a mesma, "
            "inclusive com intervalo de datas.",
            "Não usa data de criação do registro.",
        ),
        relacionados=(("INS-001", "código canônico"),),
    ),
    "INS-005": _det(
        "Quantas inscrições estão inativas.",
        "Conta inscrições com vínculo inativo em turmas ativas.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        observacoes=("Código legado substituído por INS-003.",),
        relacionados=(("INS-003", "código canônico"),),
    ),
    "INS-006": _det(
        "Como as desativações de inscrição se distribuem por motivo.",
        "Indicador indisponível: o banco não registra o motivo da desativação.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        observacoes=(
            "Não aparece na Central; a chamada direta responde como não implementado.",
        ),
        relacionados=(("INS-003", "inscrições inativas disponíveis"),),
    ),
    "INS-007": _det(
        "Qual é o tempo médio de permanência das inscrições.",
        "Indicador indisponível: não há data de desativação registrada.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        observacoes=(
            "Não aparece na Central; a chamada direta responde como não implementado.",
        ),
        relacionados=(("INS-003", "inscrições inativas disponíveis"),),
    ),
    "INS-008": _det(
        "Como as inscrições se distribuem por curso.",
        "Agrupa inscrições pelo curso da oferta, sem exigir que a oferta esteja ativa.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        observacoes=("Inscrições sem oferta correspondente ficam de fora.",),
        relacionados=(("INS-001", "total de inscrições"),),
    ),
    "INS-009": _det(
        "Quantas inscrições começaram dentro do período escolhido.",
        "Conta inscrições em turmas ativas cuja data de início está entre o "
        "primeiro e o último dia do período letivo, inclusive. Sem período "
        "escolhido, usa o período vigente de cada unidade na data de hoje. "
        "Curso e professor vêm da oferta da inscrição.",
        ("unidade", "periodo", "turno", "curso", "turma", "professor"),
        observacoes=(
            "Usa a data de início da inscrição, não a data de criação do cadastro.",
            "O turno é o da oferta da inscrição; sem turno na oferta, usa o da turma.",
            "Não confundir com INS-001/INS-004, que contam o estoque de inscrições, "
            "nem com ALU-004/ALU-013, que contam cadastros ou alunos novos.",
            "Código novo: INS-004 continua sendo apenas o código legado de INS-001.",
        ),
        relacionados=(
            ("INS-001", "total de inscrições no escopo"),
            ("ALU-004", "cadastros novos pela data de criação"),
            ("ALU-013", "alunos novos no período"),
        ),
        servico="app.services.aluno_status",
    ),
    # --- Frequência ---------------------------------------------------------
    "FRE-001": _det(
        "Quantas linhas de frequência foram lançadas.",
        "Conta uma unidade por linha lançada, não por aluno nem por dia.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        observacoes=(
            "Com filtro de curso ou professor, linhas sem oferta seguem a regra D2.",
        ),
        relacionados=(("FRE-002", "linhas de presença"), ("FRE-003", "linhas de falta")),
    ),
    "FRE-002": _det(
        "Quantas presenças foram lançadas.",
        "Conta linhas de frequência com conceito de presença.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        observacoes=("Linhas com falta justificada não entram aqui.",),
        relacionados=(("FRE-001", "todas as linhas"), ("FRE-003", "faltas")),
    ),
    "FRE-003": _det(
        "Quantas faltas não justificadas foram lançadas.",
        "Conta linhas de frequência com conceito de falta simples.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        relacionados=(("FRE-004", "faltas justificadas"), ("FRE-001", "todas as linhas")),
    ),
    "FRE-004": _det(
        "Quantas faltas justificadas foram lançadas.",
        "Conta linhas de frequência com conceito de falta justificada.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        observacoes=("Faltas justificadas ficam fora do cálculo das taxas.",),
        relacionados=(("FRE-003", "faltas não justificadas"),),
    ),
    "FRE-005": _det(
        "Qual é a taxa global de presença no escopo.",
        "Divide as presenças pela soma de presenças e faltas de todas as linhas. "
        "Não é a média das porcentagens dos alunos.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        observacoes=(
            "Alunos com mais lançamentos pesam mais na taxa.",
            "O resultado é arredondado a uma casa decimal; faltas justificadas ficam fora.",
        ),
        relacionados=(("FRE-009", "taxa por turma"), ("FRE-010", "taxa por curso")),
        servico="app.services.frequencia_oferta",
    ),
    "FRE-006": _det(
        "Quantos alunos têm frequência de 90% ou mais.",
        "Calcula a frequência individual de cada aluno, arredonda a uma casa "
        "decimal e conta os que ficam na faixa alta.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        observacoes=(
            "Um valor como 89,96 vira 90,0 e entra nesta faixa.",
            "As três faixas de frequência somam o total de alunos contáveis.",
        ),
        relacionados=(("FRE-007", "faixa intermediária"), ("FRE-008", "faixa crítica")),
        servico="app.services.frequencia_oferta",
    ),
    "FRE-007": _det(
        "Quantos alunos têm frequência entre 75% e 89%.",
        "Calcula a frequência individual arredondada a uma casa decimal e "
        "conta os valores da faixa intermediária.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        observacoes=("Um valor como 89,95 vira 90,0 e vai para FRE-006.",),
        relacionados=(("FRE-006", "faixa alta"), ("FRE-008", "faixa crítica")),
        servico="app.services.frequencia_oferta",
    ),
    "FRE-008": _det(
        "Quantos alunos têm frequência abaixo de 75%.",
        "Calcula a frequência individual arredondada a uma casa decimal e "
        "conta os valores abaixo do limite.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        observacoes=("74,9 fica nesta faixa; 75,0 vai para FRE-007.",),
        relacionados=(("FRE-006", "faixa alta"), ("CRU-001", "faixa crítica por vulnerabilidade")),
        servico="app.services.frequencia_oferta",
    ),
    "FRE-009": _det(
        "Qual é a taxa de frequência de cada turma.",
        "Para cada turma, divide presenças pela soma de presenças e faltas de "
        "todas as suas linhas, inclusive as legadas.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        observacoes=("Com filtro de curso ou professor, as turmas são escolhidas pela oferta.",),
        relacionados=(("FRE-010", "taxa por curso"), ("FRE-005", "taxa global")),
        servico="app.services.frequencia_oferta",
    ),
    "FRE-010": _det(
        "Qual é a taxa de frequência de cada curso.",
        "Agrupa as linhas da oferta por curso e calcula a taxa. Linhas legadas "
        "entram no curso quando a oferta é a única ativa da turma.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        observacoes=("Nos demais casos, a linha legada fica só nos totais de unidade e turma.",),
        relacionados=(("FRE-009", "taxa por turma"), ("FRE-005", "taxa global")),
        servico="app.services.frequencia_oferta",
    ),
    # --- Turmas -------------------------------------------------------------
    "TUR-001": _det(
        "Quantas turmas ativas existem no escopo.",
        "Conta turmas com o cadastro ativo.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        observacoes=(
            "Código legado substituído por TUR-002. O nome antigo dizia "
            '"total", mas inativas nunca foram contadas.',
        ),
        relacionados=(("TUR-002", "código canônico"),),
    ),
    "TUR-002": _det(
        "Quantas turmas ativas existem no escopo.",
        "Conta turmas com o cadastro ativo.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        observacoes=(
            "Código canônico: TUR-001 é o mesmo indicador.",
            "Não conta turmas inativas.",
        ),
        relacionados=(("TUR-001", "código legado substituído"), ("TUR-005", "turmas por curso")),
    ),
    "TUR-003": _det(
        "Como os alunos enturmados se distribuem por turma.",
        "Conta cada aluno uma vez por turma.",
        ("unidade", "periodo", "turno", "curso", "turma", "professor"),
        observacoes=("Código legado substituído por ALU-010.",),
        relacionados=(("ALU-010", "código canônico"),),
        servico="app.services.aluno_status",
    ),
    "TUR-004": _det(
        "Qual é a média de alunos distintos por turma.",
        "Soma os alunos distintos apurados por ALU-010 em cada turma e divide "
        "pelo número de turmas ativas do escopo, arredondando a uma casa decimal. "
        "O numerador usa os mesmos critérios de vínculo, cadastro ativo e filtros "
        "de ALU-010; uma pessoa em duas ofertas da mesma turma conta uma vez.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        observacoes=(
            "Numerador: soma dos valores de ALU-010 por turma, com os mesmos filtros.",
            "Denominador: turmas ativas do escopo, com os mesmos filtros de turma, "
            "unidade, período, curso, professor e datas.",
            "Turma ativa sem aluno entra no denominador com zero no numerador.",
            "Não aceita filtro de turno: a coorte de ALU-010 é calculada sem ele.",
        ),
        relacionados=(("ALU-010", "alunos distintos por turma"),),
        servico="app.services.aluno_status",
    ),
    "TUR-005": _det(
        "Como as turmas se distribuem por curso.",
        "Conta cada turma uma vez por curso da oferta ativa.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        observacoes=("Turma sem oferta ativa com curso fica de fora.",),
        relacionados=(("TUR-002", "total de turmas ativas"),),
    ),
    "TUR-006": _det(
        "Como as turmas se distribuem por período letivo.",
        "Agrupa as turmas pelo período letivo vinculado.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        relacionados=(("TUR-002", "total de turmas ativas"),),
    ),
    "TUR-007": _det(
        "Como as turmas se distribuem por unidade.",
        "Agrupa as turmas pela unidade de ensino.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        relacionados=(("TUR-002", "total de turmas ativas"),),
    ),
    "TUR-008": _det(
        "Como as turmas se distribuem por professor.",
        "Conta cada turma uma vez por professor da oferta ativa.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        observacoes=("Turma sem oferta ativa com professor fica de fora.",),
        relacionados=(("TUR-002", "total de turmas ativas"),),
    ),
    # --- Aulas --------------------------------------------------------------
    "AUL-001": _det(
        "Quantas aulas foram registradas.",
        "Conta uma unidade por registro de aula, não por dia letivo.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        observacoes=("Registros sem oferta seguem a regra D2.",),
        relacionados=(("AUL-002", "aulas por turma"), ("AUL-004", "aulas por professor")),
    ),
    "AUL-002": _det(
        "Como as aulas se distribuem por turma.",
        "Agrupa os registros de aula pela turma.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        relacionados=(("AUL-001", "total de aulas"),),
    ),
    "AUL-003": _det(
        "Como as aulas se distribuem por período.",
        "Agrupa os registros de aula pelo período da turma.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        relacionados=(("AUL-001", "total de aulas"),),
    ),
    "AUL-004": _det(
        "Como as aulas se distribuem por professor.",
        "Agrupa os registros pelo professor da oferta, não pelo campo legado da turma.",
        ("unidade", "periodo", "curso", "professor"),
        observacoes=("Registros sem oferta seguem a regra D2.",),
        relacionados=(("AUL-001", "total de aulas"), ("AUL-005", "aulas por curso")),
    ),
    "AUL-005": _det(
        "Como as aulas se distribuem por curso.",
        "Agrupa os registros pelo curso da oferta.",
        ("unidade", "periodo", "curso"),
        observacoes=("Registros sem oferta entram só quando a oferta é a única ativa da turma.",),
        relacionados=(("AUL-001", "total de aulas"),),
    ),
    "AUL-006": _det(
        "Como as aulas se distribuem por unidade.",
        "Agrupa os registros de aula pela unidade da turma.",
        ("unidade", "turma", "professor"),
        observacoes=(
            "O filtro de período da Central não é repassado a este indicador.",
        ),
        relacionados=(("AUL-001", "total de aulas"),),
    ),
    "AUL-007": _det(
        "Como as aulas se distribuem por tema.",
        "Agrupa os registros pelos temas vinculados a cada aula.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        observacoes=(
            "Uma aula com vários temas entra em cada tema; a soma pode passar do total.",
        ),
        relacionados=(("AUL-001", "total de aulas"),),
    ),
    "AUL-008": _det(
        "Como as aulas se distribuem por dia.",
        "Agrupa os registros cronologicamente pela data da aula.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        observacoes=("Conta registros por data, não dias com aula.",),
        relacionados=(("AUL-001", "total de aulas"),),
    ),
    # --- Socioeconômico e diversidade ---------------------------------------
    "SOC-001": _det(
        "Como os alunos se distribuem por faixa de renda familiar.",
        "Agrupa alunos com perfil socioeconômico pela faixa declarada.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        relacionados=(("CRU-005", "desempenho por faixa de renda"),),
    ),
    "SOC-002": _det(
        "Quantos alunos recebem benefício de programa social.",
        "Conta alunos com benefício social marcado no perfil.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        relacionados=(("SOC-001", "faixas de renda"),),
    ),
    "DIV-001": _det(
        "Como os alunos com perfil PCD se distribuem por tipo de deficiência.",
        "Agrupa todos os alunos com perfil pelos tipos declarados.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        observacoes=(
            "Um aluno com mais de um tipo entra em cada um: a soma pode passar "
            "do total de pessoas.",
            "Base é o perfil completo, não só os enturmados (ALU-007).",
        ),
        relacionados=(("ALU-007", "PCD enturmados no período"),),
    ),
    # --- Atendimento --------------------------------------------------------
    "ATD-001": _det(
        "Quantos atendimentos foram registrados.",
        "Conta registros de atendimento no escopo de unidade e período.",
        ("unidade", "periodo", "curso", "turma", "professor"),
    ),
    # --- Indicadores cruzados ----------------------------------------------
    "CRU-001": _det(
        "Quantos alunos em frequência crítica recebem vulnerabilidade social.",
        "Seleciona alunos com frequência individual arredondada abaixo de 75% "
        "e cruza com a marca de vulnerabilidade do perfil.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        observacoes=("Usa a mesma faixa crítica de FRE-008.",),
        relacionados=(("FRE-008", "faixa crítica"), ("SOC-001", "faixas de renda")),
        servico="app.services.frequencia_oferta",
    ),
    "CRU-002": _det(
        "Como os participantes do conselho se distribuem por raça/cor.",
        "Conta alunos com ao menos uma resposta preenchida no conselho e "
        "agrupa pela raça/cor declarada.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        observacoes=(
            "Registro de conselho sem resposta preenchida não conta como participação.",
        ),
        relacionados=(("CRU-005", "desempenho no conselho por renda"),),
    ),
    "CRU-003": _det(
        "Como os alunos sem acesso à internet se distribuem por bairro e zona.",
        "Seleciona alunos com acesso à internet marcado como não e agrupa pelo "
        "endereço.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        observacoes=("Somente a marca explícita de sem acesso é contada.",),
        relacionados=(("SOC-001", "perfil socioeconômico"),),
    ),
    "CRU-004": _det(
        "Como as transferências se distribuem pelo curso de origem.",
        "Conta transferências agrupadas pelo curso da turma de origem.",
        ("unidade", "periodo", "curso"),
        observacoes=("O curso é o da turma de origem, não o da oferta atual.",),
        relacionados=(("ALU-018", "alunos desenturmados"),),
    ),
    "CRU-005": _det(
        "Como o desempenho no conselho se distribui por faixa de renda.",
        "Conta conselhos com situação final preenchida e cruza com a faixa de "
        "renda do perfil do aluno.",
        ("unidade", "periodo", "curso", "turma", "professor"),
        observacoes=("Conselho sem situação final fica de fora.",),
        relacionados=(("CRU-002", "participação no conselho por raça/cor"), ("SOC-001", "faixas de renda")),
    ),
}


def validar_catalogo_guia():
    """Falha se qualquer indicador do catálogo estiver sem texto obrigatório."""
    import re

    erros = []
    for codigo, indicador in INDICADORES.items():
        canonico = resolver_codigo(codigo)
        detalhe = GUIA_METADADOS.get(canonico, {})
        for campo in ("nome", "categoria", "unidade", "tipo"):
            if not indicador.get(campo):
                erros.append(f"{codigo}: campo obrigatório '{campo}' vazio")
        for campo in ("mede", "regra", "filtros", "servico"):
            if not detalhe.get(campo):
                erros.append(f"{codigo}: texto do guia '{campo}' vazio")
        texto = " ".join(
            str(valor)
            for valor in (
                indicador.get("nome", ""),
                detalhe.get("mede", ""),
                detalhe.get("regra", ""),
                *detalhe.get("observacoes", ()),
            )
        )
        if re.search(r"\bAJ\s*\d+[A-Za-z]?\b", texto, re.IGNORECASE):
            erros.append(f"{codigo}: texto do guia menciona código de tarefa")
    if erros:
        raise ValueError("; ".join(erros))
    return True


def indicadores_para_guia():
    """Devolve a visão completa do guia, derivada somente deste catálogo."""
    validar_catalogo_guia()
    itens = []
    for codigo, indicador in INDICADORES.items():
        canonico = resolver_codigo(codigo)
        detalhe = GUIA_METADADOS[canonico]
        item = dict(indicador)
        item.update(detalhe)
        item["codigo"] = codigo
        item["alias_de"] = canonico if eh_alias(codigo) else None
        item["disponivel"] = codigo not in INDICADORES_INDISPONIVEIS
        item["visivel_na_central"] = codigo not in CODIGOS_OCULTOS_DA_CENTRAL
        itens.append(item)
    return itens


def categorias_para_guia():
    """Agrupa a visão do guia mantendo a ordem histórica das categorias."""
    categorias = {}
    for item in indicadores_para_guia():
        categorias.setdefault(item["categoria"], []).append(item)
    return categorias
