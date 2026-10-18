pautaON protótipo

Coordenação pedagógica Unidade Exemplo

# Ficha 360° do aluno

Frequência, conselho de classe e atendimentos reunidos em uma única turma.

Turma [Histórico impresso](#) [Atendimentos](#) [Voltar](#)

Protótipo com dados fictícios. Os números são calculados a partir das 22 aulas mostradas no mapa.

ML

## Mariana Souza Lima

Renovado Menor de idade

Matrícula 2025-00417 · 14 anos · Unidade Exemplo

---

Turma

Vela Optimist — Iniciação A

Professor

Ricardo Alves

Nível

Iniciante

Dias e horário

Ter e Qui · 08:00–10:00

Sinais de atenção

- 3 faltas seguidas em setembro

  08/09 a 15/09 · regra: 2 ou mais faltas (F) seguidas; J não conta.
- 5,4 pontos abaixo da média da turma

  81,0% contra 86,4% · regra: diferença de 5 pontos ou mais.
- Faixa de frequência 75–89%

  Mais 2 faltas seguidas levariam a aluna abaixo de 75% (faixa crítica).
- Retomada após o atendimento de 16/09

  8 presenças em 9 aulas desde então.

Frequência

81,0% 75–89%

7590

17 presenças em 21 aulas válidas

Média da turma

86,4% -5,4 pp

Diferença do aluno em pontos percentuais. Calculada com as mesmas regras.

Faltas

4 1 justificada

Maior sequência: 3 aulas (08/09 a 15/09).

Atendimentos

1 no período

Último em 16/09, pela equipe pedagógica.

Aula a aula · cada quadrado é uma aula

04/08 11/08 18/08 25/08 01/09 08/09 15/09 22/09 29/09 06/10 13/10 Ter A B B C C F F D B F B Qui A A B B J F C C C C B

ABCDpresença Ffalta Jjustificada (fora do cálculo)

Frequência acumulada · aluno × turma

Conselho de classe

1. Inicial · 18/08

   Participação
2. Percurso · 29/09

   Participação
3. Final · janela de 19/10 a 30/10

   Situação final e próxima turma serão definidas aqui.

Respostas do conselho por etapa

Respostas do conselho de classe nas etapas inicial e percurso

| Pergunta | Inicial | Percurso |
| --- | --- | --- |
| Participa das atividades propostas? | Sempre | Na maioria das vezes |
| Relaciona-se bem com colegas e instrutores? | Na maioria das vezes | Sempre |
| Segue as orientações de segurança na água? | Sempre | Sempre |
| Observação do instrutor | Tímida no início, evita as manobras em dupla. | Mais confiante, assume o leme sozinha. Faltas de setembro ligadas a transporte. |

Células marcadas mudaram entre as etapas. Perguntas e opções vêm de `PerguntaConselho`; os textos são exemplos.

Linha do tempo

1. 06/10 · Falta isolada

   Aula 19 de 22, depois de 5 presenças seguidas.
2. 29/09 · Conselho de percurso concluído

   Situação: Participação. Instrutor: Ricardo Alves.
3. 17/09 · Primeira presença após 3 faltas
4. 16/09 · Atendimento pedagógico

   Contato com a família sobre dificuldade de transporte nas manhãs.
5. 08/09 a 15/09 · 3 faltas seguidas
6. 03/09 · Falta justificada
7. 18/08 · Conselho inicial concluído
8. 04/08 · Inscrição na turma

   Renovação dentro dos 14 primeiros dias do período.

Percurso do aluno

Turmas cursadas, com frequência e situação final

| Período | Turma | Nível | Aulas | % Freq. | Situação |
| --- | --- | --- | --- | --- | --- |
| 2026.2 | Vela Optimist — Iniciação A | Iniciante | 21 | 81,0% | Em andamento |
| 2026.1 | Segurança na Água | Básico | 19 | 94,7% | Aprovado |
| 2025.2 | Marinharia Básica | Básico | 18 | 88,9% | Aprovado |

Mesma lógica da página de histórico atual, em formato de consulta.

Contexto socioeconômico Restrito

Faixa de renda familiar

Até 1 salário mínimo

Programa social

Sim

Internet em casa

Sim

Bairro

Bairro Exemplo

Vem de `PerfilSocioeconomico` e `EnderecoAluno`. Proposta: visível só para administração, pedagógico e serviço social.

Fonte de dados e consulta de cada bloco da ficha

| Bloco | Fonte | Consulta | Índice |
| --- | --- | --- | --- |
| Identidade e status | `Aluno`, `Inscricao`, `Turma`, `aluno_status` | Por `aluno_id`; uma turma por vez | Chaves primárias e estrangeiras |
| Mapa, KPIs e curva do aluno | `Frequencia` | Uma consulta: `aluno_id` + `turma_id`, ordenada por data | `ix_frequencia_aluno_data` |
| Média e curva da turma | `Frequencia` | Uma agregação por semana, filtrada por `turma_id` | `ix_frequencia_turma_data` |
| Conselho e respostas | `ConselhoClasse`, `ConselhoResposta`, `PerguntaConselho` | Uma consulta com junção, para evitar uma consulta por etapa | `uix_conselho_turma_aluno_etapa` |
| Atendimentos | `Atendimento` | Por `aluno_id`, mais recentes primeiro, com limite | O model não declara índice em `aluno_id`; confirmar nas migrations |
| Contexto restrito | `PerfilSocioeconomico`, `EnderecoAluno` | Só quando o perfil tem permissão | Chave estrangeira |
| Sinais de atenção | Dados já carregados | Calculados em Python, sem consulta extra | Não se aplica |