"""
================================================================================
ENUMS.PY - Enumerações de domínio
================================================================================

Criado na Onda 2B. Centraliza os conjuntos de valores canônicos usados em
colunas de categorização (enums, checks e validações).

CONVENÇÕES
----------
- Todos herdam de `str, enum.Enum` para compatibilidade com JSON, SQLAlchemy
  e comparações diretas com strings (`ConceitoFrequencia.A == 'A'` -> True).
- O **valor** (`value`) é o que persiste no banco. O **nome** (`name`) é o
  identificador Python — mantidos idênticos quando possível.

DISTINÇÃO DE ESTRATÉGIA
-----------------------
- `ConceitoFrequencia`, `TipoDiaBloqueado`, `EtapaConselho`, `TipoPergunta`:
  viraram `db.Enum` NATIVOS no Postgres (tipo ENUM no schema). Conjuntos
  estáveis, mudanças raras.
- `UserRole`, `SituacaoFinal`: permanecem `VARCHAR + CHECK`. Conjuntos que
  podem evoluir; alterar exige apenas um `ALTER TABLE ... DROP/ADD CONSTRAINT`.

CONJUNTOS DERIVADOS
-------------------
- `CONCEITOS_PRESENCA`: A/B/C/D (contam como presença).
- `CONCEITOS_CONTABEIS`: presença + F (denominador da frequência).
- `ETAPAS_ORDEM`: ordem canônica das etapas de conselho (INICIAL, PERCURSO, FINAL).

Estes são definidos aqui (não em `utils/logica.py`) para evitar ciclo de
importação — `enums.py` não depende de nenhum modelo.
================================================================================
"""

import enum


class ConceitoFrequencia(str, enum.Enum):
    """
    Conceito de frequência por aluno/aula.

    Regra de negócio:
        - A, B, C, D  -> presença (gradações qualitativas)
        - F           -> falta
        - J           -> falta justificada (não conta para frequência)
    """
    A = 'A'
    B = 'B'
    C = 'C'
    D = 'D'
    F = 'F'
    J = 'J'


class TipoDiaBloqueado(str, enum.Enum):
    """Categoria de um dia sem aula em um período letivo."""
    FERIADO = 'FERIADO'
    ATIVIDADE_PEDAGOGICA = 'ATIVIDADE_PEDAGOGICA'
    REUNIAO_PAIS = 'REUNIAO_PAIS'
    ATIVIDADE_INTERNA = 'ATIVIDADE_INTERNA'
    MANUTENCAO = 'MANUTENCAO'


class EtapaConselho(str, enum.Enum):
    """Momento do conselho de classe dentro de uma turma."""
    INICIAL = 'INICIAL'
    PERCURSO = 'PERCURSO'
    FINAL = 'FINAL'


class TipoPergunta(str, enum.Enum):
    """Escopo de uma pergunta de conselho."""
    TURMA = 'TURMA'   # avaliação coletiva
    ALUNO = 'ALUNO'   # avaliação individual


class UserRole(str, enum.Enum):
    """
    Perfil de acesso do usuário.

    Mantido como VARCHAR + CHECK no banco (não enum nativo) porque o conjunto
    pode evoluir com frequência.
    """
    ADMIN = 'admin'
    PEDAGOGICO = 'pedagogico'
    PROFESSOR = 'professor'
    SECRETARIA = 'secretaria'
    SERVICO_SOCIAL = 'servico_social'
    GERENCIA = 'gerencia'
    PENDENTE = 'pendente'


class SituacaoFinal(str, enum.Enum):
    """
    Resultado final de um aluno no conselho de classe.

    Mantido como VARCHAR + CHECK no banco (não enum nativo) porque o conjunto
    pode evoluir.
    """
    APROVADO = 'Aprovado'
    REPROVADO_POR_FALTA = 'Reprovado por Falta'
    DESISTENTE = 'Desistente'
    EVADIDO = 'Evadido'
    PARTICIPACAO = 'Participação'
    CONCLUIDO = 'Concluído'


# =============================================================================
# CONJUNTOS DERIVADOS (conveniência)
# =============================================================================

# Conceitos que contam como presença.
CONCEITOS_PRESENCA = frozenset({
    ConceitoFrequencia.A,
    ConceitoFrequencia.B,
    ConceitoFrequencia.C,
    ConceitoFrequencia.D,
})

# Conceitos que entram no denominador da frequência (presença + falta).
CONCEITOS_CONTABEIS = CONCEITOS_PRESENCA | {ConceitoFrequencia.F}

# Ordem canônica das etapas do conselho. Usado em ordenações e agrupamentos.
ETAPAS_ORDEM = (
    EtapaConselho.INICIAL,
    EtapaConselho.PERCURSO,
    EtapaConselho.FINAL,
)

# Mapa etapa -> campo do modelo Turma que guarda a avaliação daquela etapa.
# Evita redefinir esse dicionário em conselho.py e utils.
ETAPA_PARA_CAMPO_AVALIACAO = {
    EtapaConselho.INICIAL: 'avaliacao_inicial',
    EtapaConselho.PERCURSO: 'avaliacao_percurso',
    EtapaConselho.FINAL: 'avaliacao_final',
}


__all__ = [
    'ConceitoFrequencia',
    'TipoDiaBloqueado',
    'EtapaConselho',
    'TipoPergunta',
    'UserRole',
    'SituacaoFinal',
    'CONCEITOS_PRESENCA',
    'CONCEITOS_CONTABEIS',
    'ETAPAS_ORDEM',
    'ETAPA_PARA_CAMPO_AVALIACAO',
]