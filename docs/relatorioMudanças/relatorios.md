01 — Alunos

ID

Indicador

Cálculo

ALU-001

Total de alunos

COUNT(DISTINCT aluno.id)

ALU-002

Alunos ativos

COUNT(DISTINCT aluno.id) com aluno ativo

ALU-003

Alunos inativos

COUNT(DISTINCT aluno.id) com aluno inativo

ALU-004

Novos alunos

alunos cuja primeira inscrição ocorre no período

ALU-005

Alunos por sexo

agrupamento

ALU-006

Alunos por faixa etária

agrupamento

ALU-007

Alunos PCD

contagem

ALU-008

Alunos por unidade

agrupamento

ALU-009

Alunos por curso

agrupamento

ALU-010

Alunos por turma

agrupamento

02 — Inscrições

ID

Indicador

Cálculo

INS-001

Total de inscrições

COUNT(inscricao.id)

INS-002

Inscrições ativas

ativo = True

INS-003

Inscrições encerradas

ativo = False

INS-004

Novas inscrições

data_inicio no período

INS-005

Desativações

data_desativacao no período

INS-006

Motivos de desativação

agrupamento

INS-007

Tempo médio de permanência

intervalo entre início/fim

INS-008

Inscrições por curso

agrupamento

03 — Frequência

ID

Indicador

FRE-001

Total de lançamentos

FRE-002

Total de presenças

FRE-003

Total de faltas

FRE-004

Total de faltas justificadas

FRE-005

Frequência média

FRE-006

Alunos ≥ 90%

FRE-007

Alunos entre 75% e 89%

FRE-008

Alunos < 75%

FRE-009

Frequência por turma

FRE-010

Frequência por curso

04 — Turmas

ID

Indicador

TUR-001

Total de turmas

TUR-002

Turmas ativas

TUR-003

Alunos por turma

TUR-004

Média de alunos por turma

TUR-005

Turmas por curso

TUR-006

Turmas por período

TUR-007

Turmas por unidade

TUR-008

Turmas por professor

Regra importante

Desde já vamos separar:

Dimensão

Por quê/por quem/quando quero analisar?

Ex.:

Unidade

Período

Curso

Turma

Professor

Sexo

Faixa etária

Métrica

O que quero medir?

Ex.:

Total de alunos

Frequência média

Total de faltas

Total de inscrições

Isso será fundamental para o gerador analítico.

O que vou fazer na Parte 2

Depois do seu OK, seguimos para:

Parte 2 — indicadores pedagógicos e resultados

Incluindo:

aulas;

planejamento;

carga horária;

professores;

avaliações;

conselho de classe;

aprovação;

reprovação;

desistência;

evasão;

desempenho;

trajetória do aluno.