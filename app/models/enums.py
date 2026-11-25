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
    Resultado final de um aluno no conselho de classe (vocabulário AJ30).

    Mantido como VARCHAR + CHECK no banco (não enum nativo) porque o conjunto
    pode evoluir. Um resultado ``não definido`` NÃO é valor deste enum: é
    ``NULL`` na coluna, exibido como ``—`` em tela e impressão.

    Os dois apelidos no fim são aliases de NOME (não aparecem na iteração):
    código legado que ainda escreve ``SituacaoFinal.PARTICIPACAO`` ou
    ``SituacaoFinal.REPROVADO_POR_FALTA`` resolve para o valor canônico.
    """
    APROVADO = 'Aprovado'
    PARTICIPANTE = 'Participante'
    REPROVADO_POR_FALTAS = 'Reprovado por faltas'
    DESISTENTE = 'Desistente'
    EVADIDO = 'Evadido'
    EMPREGADO = 'Empregado'

    PARTICIPACAO = 'Participante'
    REPROVADO_POR_FALTA = 'Reprovado por faltas'


#: Única ordem de exibição do select de situação final (e dos filtros).
#: A option ``—`` (value="") é acrescentada à frente pelo template; ela não
#: entra aqui porque NULL não é valor do domínio.
SITUACAO_FINAL_OPCOES: tuple[str, ...] = tuple(s.value for s in SituacaoFinal)

#: Situações que contam como aprovação nas regras de certificado e da ficha
#: 360°. "Concluído" foi fundido em "Aprovado" pela migration AJ30, então a
#: semântica "Concluído vale como Aprovado" fica preservada sem valor extra.
SITUACOES_FINAIS_FAVORAVEIS: frozenset[str] = frozenset({
    SituacaoFinal.APROVADO.value,
    SituacaoFinal.PARTICIPANTE.value,
})

#: Valores gravados antes da AJ30 que a fronteira (normalizador) e a migration
#: convertem. Mapa único — não duplicar em rotas, templates ou relatórios.
SITUACAO_FINAL_LEGADO: dict[str, str] = {
    'Concluído': SituacaoFinal.APROVADO.value,
    'Participação': SituacaoFinal.PARTICIPANTE.value,
    'Reprovado por Falta': SituacaoFinal.REPROVADO_POR_FALTAS.value,
}

#: Texto canônico do ausente (NULL) em tela, leitores e impressão.
SITUACAO_FINAL_INDEFINIDA = '—'

#: Badges do "Resultado do Conselho": (classe CSS, rótulo curto), pela fonte
#: única de valores. NULL vira ``—`` — nunca "Sem Registro".
SITUACAO_FINAL_BADGES: dict[str, tuple[str, str]] = {
    SituacaoFinal.APROVADO.value: ('badge-situacao-aprovado', 'Aprovado'),
    SituacaoFinal.PARTICIPANTE.value: ('badge-situacao-participante', 'Participante'),
    SituacaoFinal.REPROVADO_POR_FALTAS.value: ('badge-situacao-reprovado', 'Rep. por faltas'),
    SituacaoFinal.DESISTENTE.value: ('badge-situacao-desistente', 'Desistente'),
    SituacaoFinal.EVADIDO.value: ('badge-situacao-evadido', 'Evadido'),
    SituacaoFinal.EMPREGADO.value: ('badge-situacao-empregado', 'Empregado'),
    '': ('badge-situacao-nao-definido', SITUACAO_FINAL_INDEFINIDA),
}
# Apelidos históricos e códigos em maiúsculas também resolvem para o mesmo
# badge — leitores antigos podem encontrar valores gravados pré-AJ30.
for _antigo, _novo in SITUACAO_FINAL_LEGADO.items():
    SITUACAO_FINAL_BADGES.setdefault(_antigo, SITUACAO_FINAL_BADGES[_novo])
for _valor, _info in list(SITUACAO_FINAL_BADGES.items()):
    SITUACAO_FINAL_BADGES.setdefault(_valor.upper(), _info)
SITUACAO_FINAL_BADGES.setdefault(
    'REPROVADO_POR_FALTA', SITUACAO_FINAL_BADGES[SituacaoFinal.REPROVADO_POR_FALTAS.value]
)
SITUACAO_FINAL_BADGES.setdefault(
    'PARTICIPACAO', SITUACAO_FINAL_BADGES[SituacaoFinal.PARTICIPANTE.value]
)


class StatusAluno(str, enum.Enum):
    """Situação derivada do aluno em relação a um período letivo."""
    NOVO = 'NOVO'
    RENOVADO = 'RENOVADO'
    RETORNANTE = 'RETORNANTE'
    EM_JANELA = 'EM_JANELA'
    NAO_RENOVADO = 'NAO_RENOVADO'
    DESENTURMADO = 'DESENTURMADO'
    OUTROS = 'OUTROS'


JANELA_RENOVACAO_DIAS = 14


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
    'StatusAluno',
    'JANELA_RENOVACAO_DIAS',
    'CONCEITOS_PRESENCA',
    'CONCEITOS_CONTABEIS',
    'ETAPAS_ORDEM',
    'ETAPA_PARA_CAMPO_AVALIACAO',
]