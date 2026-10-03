# Catálogo de Indicadores — Módulo de Relatórios e BI (pautaON)

Este documento descreve todos os indicadores implementados na camada de Business Intelligence (BI)
do sistema `pautaON`, bem como as funcionalidades de visualização e exportação disponíveis na
**Central de BI** (`/relatorios/bi`).

Os indicadores estão agrupados por categorias temáticas. Cada item detalha o seu propósito
funcional, as tabelas/modelos consultados no banco de dados e a estrutura do dado retornado.

---

## Sumário

1. [Categoria: Alunos](#1-categoria-alunos)
2. [Categoria: Inscrições](#2-categoria-inscrições)
3. [Categoria: Frequência](#3-categoria-frequência)
4. [Categoria: Turmas](#4-categoria-turmas)
5. [Categoria: Aulas](#5-categoria-aulas)
6. [Categoria: Socioeconômico e Diversidade](#6-categoria-socioeconômico-e-diversidade)
7. [Categoria: Atendimento](#7-categoria-atendimento)
8. [Categoria: Indicadores Cruzados (CRU)](#8-categoria-indicadores-cruzados-cru)
9. [Visualizações e Exportações](#9-visualizações-e-exportações)

---

## 1. Categoria: Alunos

### ALU-001: Total de alunos com cadastro ativo no período
- **O que faz:** Conta alunos com `Aluno.ativo=True` no escopo do período, incluindo Novo, Renovado, Retornante e todas as categorias de não enturmados. Exclui cadastros inativos. ALU-001 deve ser igual a ALU-011 + ALU-012.
- **Onde busca os dados:** `app.services.aluno_status`, a partir de `Aluno`, `Inscricao`, `Turma` e `PeriodoLetivo`.
- **O que retorna:** Um número inteiro (`int`) com a contagem total.

### ALU-002: Alunos com cadastro ativo
- **O que faz:** Retorna o total de alunos cujo cadastro está ativo (`Aluno.ativo=True`). Esse indicador representa a situação cadastral, não a enturmação no período.
- **Onde busca os dados:** Tabela/Modelo `Aluno`.
- **O que retorna:** Um número inteiro (`int`).

### ALU-003: Alunos com cadastro inativo
- **O que faz:** Retorna o total de alunos cujo cadastro está inativo (`Aluno.ativo=False`). Esse indicador representa a situação cadastral, não a enturmação no período.
- **Onde busca os dados:** Tabela/Modelo `Aluno`.
- **O que retorna:** Um número inteiro (`int`).

### ALU-004: Novos cadastros
- **O que faz:** Conta registros criados em `Aluno.created_at` dentro do intervalo selecionado. Com período informado, usa `PeriodoLetivo.data_inicio` e `data_fim`; sem período, usa o período ativo vigente de cada unidade. Não exige enturmação nem `Aluno.ativo=True`; registros com `created_at` nulo não entram. O filtro de turno não se aplica a cadastros.
- **Onde busca os dados:** Tabela/Modelo `Aluno` (`created_at`).
- **O que retorna:** Um número inteiro (`int`).

### ALU-005: Alunos enturmados por sexo
- **O que faz:** Distribui os alunos enturmados em P (Novo + Renovado + Retornante) agrupados por gênero. Prioriza `PerfilDiversidade.genero`; para alunos sem perfil estruturado, usa o fallback `Aluno.diversidade_json`. Suporta unidade, período e turno; o turno delimita a coorte, enquanto a classificação usa o histórico completo.
- **Onde busca os dados:** `app.services.aluno_status`, `Aluno`, `Inscricao`, `Turma`, `PeriodoLetivo` e `PerfilDiversidade` (com fallback no JSON legado `Aluno.diversidade_json`).
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": str, "nome": str, "valor": int}, ...]`, ordenada do maior para o menor.

### ALU-006: Alunos enturmados por faixa etária
- **O que faz:** Distribui os alunos enturmados em P (Novo + Renovado + Retornante) por faixa etária, calculada a partir de `Aluno.data_nascimento`. Alunos sem data de nascimento ficam em "Não Informado". Suporta unidade, período e turno. As faixas são: **Menor de 12 anos**, **12 a 17 anos**, **18 a 24 anos**, **25 a 39 anos**, **40 a 59 anos**, **60 anos ou mais** e **Não Informado**.
- **Onde busca os dados:** `app.services.aluno_status`, `Aluno`, `Inscricao`, `Turma` e `PeriodoLetivo`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": str, "nome": str, "valor": int}, ...]`, na ordem das faixas definidas, omitindo faixas com zero alunos.

### ALU-007: Alunos PCD enturmados
- **O que faz:** Conta alunos enturmados em P (Novo + Renovado + Retornante) identificados como PCD, usando `PerfilDiversidade.saude_laudo` ou o fallback legado `Aluno.diversidade_json`.
- **Onde busca os dados:** `app.services.aluno_status`, `Aluno`, `Inscricao`, `Turma`, `PeriodoLetivo` e `PerfilDiversidade`.
- **O que retorna:** Um número inteiro (`int`).

### ALU-008: Alunos cadastrados por unidade
- **O que faz:** Agrupa e conta alunos cadastrados distintos por unidade de ensino, sem restringir pelo status da enturmação.
- **Onde busca os dados:** Tabelas `Aluno` e `Unidade`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": int, "nome": str, "valor": int}, ...]`.

### ALU-009: Alunos enturmados por curso
- **O que faz:** Agrupa por curso e conta alunos distintos enturmados em P/D (Novo + Renovado + Retornante), com inscrição vigente. Sem período explícito, usa o período vigente de cada unidade.
- **Onde busca os dados:** `app.services.aluno_status`, `Aluno`, `Inscricao`, `Turma`, `Curso` e `PeriodoLetivo`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": int, "nome": str, "valor": int}, ...]`.

### ALU-010: Alunos por turma
- **O que faz:** Agrupa e conta a quantidade de alunos distintos vinculados a cada turma.
- **Onde busca os dados:** Tabelas `Aluno`, `Inscricao` e `Turma`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": int, "nome": str, "valor": int}, ...]`.

### ALU-011: Alunos enturmados no período
- **O que faz:** Conta alunos classificados como Novo, Renovado ou Retornante, isto é, com vínculo vigente em uma turma do período na data de referência.
- **Onde busca os dados:** `app.services.aluno_status`, a partir de `Aluno`, `Inscricao`, `Turma` e `PeriodoLetivo`.
- **O que retorna:** Um número inteiro (`int`) de alunos distintos.

### ALU-012: Alunos não enturmados no período
- **O que faz:** Conta alunos com cadastro ativo que não estão enturmados no período na data de referência. Inclui Em janela, Não renovado, Desenturmado e Outros.
- **Onde busca os dados:** `app.services.aluno_status`, a partir de `Aluno`, `Inscricao`, `Turma` e `PeriodoLetivo`.
- **O que retorna:** Um número inteiro (`int`) de alunos distintos.

### ALU-013: Alunos novos no período
- **O que faz:** Conta alunos enturmados em P sem inscrição em qualquer período anterior da mesma unidade.
- **Onde busca os dados:** `app.services.aluno_status`.
- **O que retorna:** Um número inteiro (`int`) de alunos distintos.

### ALU-014: Alunos renovados
- **O que faz:** Conta alunos com enturmação em P-1 cuja primeira inscrição em P ocorreu até o 14º dia, inclusive, contado do início de P.
- **Onde busca os dados:** `app.services.aluno_status`.
- **O que retorna:** Um número inteiro (`int`) de alunos distintos.

### ALU-015: Alunos retornantes
- **O que faz:** Conta alunos enturmados em P com histórico anterior que não se enquadram como Renovados.
- **Onde busca os dados:** `app.services.aluno_status`.
- **O que retorna:** Um número inteiro (`int`) de alunos distintos.

### ALU-016: Alunos não renovados
- **O que faz:** Conta alunos com enturmação em P-1, sem vínculo vigente em P, após o encerramento da janela de renovação.
- **Onde busca os dados:** `app.services.aluno_status`.
- **O que retorna:** Um número inteiro (`int`) de alunos distintos.

### ALU-017: Alunos em janela de renovação
- **O que faz:** Conta alunos com enturmação em P-1, sem vínculo vigente em P, enquanto a janela de renovação permanece aberta.
- **Onde busca os dados:** `app.services.aluno_status`.
- **O que retorna:** Um número inteiro (`int`) de alunos distintos.

### ALU-018: Alunos desenturmados
- **O que faz:** Conta alunos com inscrição histórica em P, mas sem vínculo vigente em P na data de referência.
- **Onde busca os dados:** `app.services.aluno_status`.
- **O que retorna:** Um número inteiro (`int`) de alunos distintos.

**Filtros dos indicadores ALU-011 a ALU-018:** `unidade_id`, `periodo_letivo_id` e `turno`. Sem período informado, considera o período ativo cuja vigência contém a data atual em cada unidade; se houver sobreposição, escolhe o período com início mais recente. Com turno selecionado, a coorte vem das inscrições em P ou P-1 naquele turno, mas o status é calculado com o histórico completo; Outros não entra em um filtro de turno específico por não possuir vínculo que determine turno. Perfis locais ficam restritos à própria unidade. A data de referência padrão é hoje.

---

## 2. Categoria: Inscrições

### INS-001: Total de inscrições
- **O que faz:** Retorna o volume total de registros de inscrições conforme os filtros aplicados.
- **Onde busca os dados:** Tabela/Modelo `Inscricao` vinculada a `Turma`.
- **O que retorna:** Um número inteiro (`int`).

### INS-002: Inscrições ativas
- **O que faz:** Retorna o total de inscrições com status ativo (`ativo.is_(True)`).
- **Onde busca os dados:** Tabela/Modelo `Inscricao`.
- **O que retorna:** Um número inteiro (`int`).

### INS-003: Inscrições encerradas
- **O que faz:** Retorna o total de inscrições com status encerrado/inativo (`ativo.is_(False)`).
- **Onde busca os dados:** Tabela/Modelo `Inscricao`.
- **O que retorna:** Um número inteiro (`int`).

### INS-004: Novas inscrições
- **O que faz:** Retorna o volume de novas inscrições efetuadas no período informado.
- **Onde busca os dados:** Tabela/Modelo `Inscricao`.
- **O que retorna:** Um número inteiro (`int`).

### INS-005: Desativações
- **O que faz:** Retorna a contagem de inscrições desativadas.
- **Onde busca os dados:** Tabela/Modelo `Inscricao`.
- **O que retorna:** Um número inteiro (`int`).

### INS-006: Motivos de desativação _(não implementado)_
- **Motivo:** Não há dados de motivo de desativação registrados no banco.

### INS-007: Tempo médio de permanência _(não implementado)_
- **Motivo:** Não há registros com `data_desativacao` preenchida no banco.

### INS-008: Inscrições por curso
- **O que faz:** Agrupa e conta o total de inscrições vinculadas a cada curso.
- **Onde busca os dados:** Tabelas `Inscricao`, `Turma` e `Curso`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": int, "nome": str, "valor": int}, ...]`.

---

## 3. Categoria: Frequência

### FRE-001: Total de lançamentos de frequência
- **O que faz:** Retorna o número total de registros de frequência lançados.
- **Onde busca os dados:** Tabela/Modelo `Frequencia`.
- **O que retorna:** Um número inteiro (`int`).

### FRE-002: Total de presenças
- **O que faz:** Conta o total de registros onde o conceito de presença está contabilizado (`A`, `B`, `C`, `D`).
- **Onde busca os dados:** Tabela/Modelo `Frequencia`.
- **O que retorna:** Um número inteiro (`int`).

### FRE-003: Total de faltas
- **O que faz:** Conta o total de registros de faltas não justificadas (`F`).
- **Onde busca os dados:** Tabela/Modelo `Frequencia`.
- **O que retorna:** Um número inteiro (`int`).

### FRE-004: Total de faltas justificadas
- **O que faz:** Conta o total de registros de faltas justificadas (`J`).
- **Onde busca os dados:** Tabela/Modelo `Frequencia`.
- **O que retorna:** Um número inteiro (`int`).

### FRE-005: Frequência média
- **O que faz:** Calcula a taxa percentual média global de frequência dos alunos, desconsiderando faltas justificadas.
- **Onde busca os dados:** Tabela/Modelo `Frequencia`.
- **O que retorna:** Um valor percentual arredondado (`float`).

### FRE-006: Alunos com frequência ≥ 90%
- **O que faz:** Identifica e conta o número de alunos cuja frequência individual calculada é maior ou igual a 90%.
- **Onde busca os dados:** Tabela/Modelo `Frequencia`.
- **O que retorna:** Um número inteiro (`int`).

### FRE-007: Alunos com frequência entre 75% e 89%
- **O que faz:** Identifica e conta o número de alunos com frequência individual situada na faixa entre 75% e 89%.
- **Onde busca os dados:** Tabela/Modelo `Frequencia`.
- **O que retorna:** Um número inteiro (`int`).

### FRE-008: Alunos com frequência inferior a 75%
- **O que faz:** Identifica e conta o número de alunos cuja frequência individual está abaixo do limite crítico de 75%.
- **Onde busca os dados:** Tabela/Modelo `Frequencia`.
- **O que retorna:** Um número inteiro (`int`).

### FRE-009: Frequência por turma
- **O que faz:** Calcula a taxa média de frequência agrupada por cada turma.
- **Onde busca os dados:** Tabelas `Turma` e `Frequencia`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": int, "nome": str, "valor": float}, ...]`.

### FRE-010: Frequência por curso
- **O que faz:** Calcula a taxa média de frequência agrupada por curso.
- **Onde busca os dados:** Tabelas `Frequencia`, `Turma` e `Curso`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": int, "nome": str, "valor": float}, ...]`.

---

## 4. Categoria: Turmas

### TUR-001: Total de turmas
- **O que faz:** Retorna o total geral de turmas cadastradas conforme os filtros aplicados.
- **Onde busca os dados:** Tabela/Modelo `Turma`.
- **O que retorna:** Um número inteiro (`int`).

### TUR-002: Turmas ativas
- **O que faz:** Retorna a quantidade de turmas ativas (`ativo.is_(True)`).
- **Onde busca os dados:** Tabela/Modelo `Turma`.
- **O que retorna:** Um número inteiro (`int`).

### TUR-003: Alunos por turma
- **O que faz:** Equivalente a `ALU-010`, mapeando o total de alunos por turma.
- **Onde busca os dados:** Tabelas `Turma` e `Inscricao`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": int, "nome": str, "valor": int}, ...]`.

### TUR-004: Média de alunos por turma
- **O que faz:** Calcula a média aritmética de alunos ativos por turma no escopo filtrado.
- **Onde busca os dados:** Tabelas `Turma` e `Inscricao`.
- **O que retorna:** Um valor decimal (`float`).

### TUR-005: Turmas por curso
- **O que faz:** Agrupa e conta o total de turmas associadas a cada curso.
- **Onde busca os dados:** Tabelas `Turma` e `Curso`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": int, "nome": str, "valor": int}, ...]`.

### TUR-006: Turmas por período
- **O que faz:** Agrupa e conta o total de turmas vinculadas a cada período letivo.
- **Onde busca os dados:** Tabelas `Turma` e `PeriodoLetivo`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": int, "nome": str, "valor": int}, ...]`.

### TUR-007: Turmas por unidade
- **O que faz:** Agrupa e conta o total de turmas por unidade de ensino.
- **Onde busca os dados:** Tabelas `Turma` e `Unidade`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": int, "nome": str, "valor": int}, ...]`.

### TUR-008: Turmas por professor
- **O que faz:** Agrupa e conta o total de turmas sob a responsabilidade de cada professor.
- **Onde busca os dados:** Tabelas `Turma` e `User`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": int, "nome": str, "valor": int}, ...]`.

---

## 5. Categoria: Aulas

### AUL-001: Total de aulas registradas
- **O que faz:** Retorna o total consolidado de aulas ministradas e registradas.
- **Onde busca os dados:** Tabela/Modelo `RegistroAula`.
- **O que retorna:** Um número inteiro (`int`).

### AUL-002: Aulas por turma
- **O que faz:** Agrupa e conta a quantidade de aulas registradas por turma.
- **Onde busca os dados:** Tabelas `RegistroAula` e `Turma`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": int, "nome": str, "valor": int}, ...]`.

### AUL-003: Aulas por período
- **O que faz:** Agrupa e conta a quantidade de aulas registradas por período letivo.
- **Onde busca os dados:** Tabelas `RegistroAula`, `Turma` e `PeriodoLetivo`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": int, "nome": str, "valor": int}, ...]`.

### AUL-004: Aulas por professor
- **O que faz:** Agrupa e conta a quantidade de aulas registradas por professor.
- **Onde busca os dados:** Tabelas `RegistroAula`, `Turma` e `User`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": int, "nome": str, "valor": int}, ...]`.

### AUL-005: Aulas por curso
- **O que faz:** Agrupa e conta a quantidade de aulas registradas por curso.
- **Onde busca os dados:** Tabelas `RegistroAula`, `Turma` e `Curso`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": int, "nome": str, "valor": int}, ...]`.

### AUL-006: Aulas por unidade
- **O que faz:** Agrupa e conta a quantidade de aulas registradas por unidade.
- **Onde busca os dados:** Tabelas `RegistroAula`, `Turma` e `Unidade`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": int, "nome": str, "valor": int}, ...]`.

### AUL-007: Aulas por tema
- **O que faz:** Agrupa e conta a quantidade de aulas registradas por tema pedagógico.
- **Onde busca os dados:** Tabelas `RegistroAula` e `TemaAula`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": int, "nome": str, "valor": int}, ...]`.

### AUL-008: Aulas por dia
- **O que faz:** Agrupa cronologicamente a quantidade de aulas registradas por data.
- **Onde busca os dados:** Tabela/Modelo `RegistroAula`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": datetime.date, "nome": str, "valor": int}, ...]`.

---

## 6. Categoria: Socioeconômico e Diversidade

### SOC-001: Alunos por faixa de renda familiar
- **O que faz:** Distribui os alunos por faixas de renda familiar declarada.
- **Onde busca os dados:** Tabelas `Aluno` e `PerfilSocioeconomico`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": str, "nome": str, "valor": int}, ...]`.

### SOC-002: Alunos beneficiários de programas sociais
- **O que faz:** Conta o total de alunos que são beneficiários de programas sociais (ex.: Bolsa Família).
- **Onde busca os dados:** Tabelas `Aluno` e `PerfilSocioeconomico`.
- **O que retorna:** Um número inteiro (`int`).

### DIV-001: Alunos por tipo de deficiência
- **O que faz:** Distribui os alunos PCD por tipo de deficiência declarada.
- **Onde busca os dados:** Tabelas `Aluno` e `PerfilDiversidade`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": str, "nome": str, "valor": int}, ...]`.

---

## 7. Categoria: Atendimento

### ATD-001: Total de atendimentos
- **O que faz:** Retorna o total de atendimentos registrados conforme os filtros de unidade e período.
- **Onde busca os dados:** Tabela/Modelo `Atendimento`.
- **O que retorna:** Um número inteiro (`int`).

---

## 8. Categoria: Indicadores Cruzados (CRU)

Indicadores que cruzam duas ou mais dimensões de dados para análises integradas.

### CRU-001: Frequência crítica (< 75%) por vulnerabilidade social
- **O que faz:** Identifica alunos com frequência crítica (< 75%) cruzando com o perfil de vulnerabilidade socioeconômica.
- **Onde busca os dados:** Tabelas `Frequencia` e `PerfilSocioeconomico`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": str, "nome": str, "valor": int}, ...]`.

### CRU-002: Alunos por raça/cor no Conselho de Classe
- **O que faz:** Distribui os alunos participantes do Conselho de Classe por raça/cor declarada.
- **Onde busca os dados:** Tabelas `ConselhoClasse` e `PerfilDiversidade`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": str, "nome": str, "valor": int}, ...]`.

### CRU-003: Alunos sem acesso à internet por bairro e zona
- **O que faz:** Identifica e agrupa alunos sem acesso à internet por localização geográfica (bairro/zona).
- **Onde busca os dados:** Tabelas `Aluno` e `EnderecoAluno`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": str, "nome": str, "valor": int}, ...]`.

### CRU-004: Transferências por curso de origem
- **O que faz:** Conta e agrupa transferências de alunos por curso de origem.
- **Onde busca os dados:** Tabelas `Transferencia`, `Turma` e `Curso`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": int, "nome": str, "valor": int}, ...]`.

### CRU-005: Desempenho no Conselho de Classe por faixa de renda
- **O que faz:** Cruza os resultados do Conselho de Classe com a faixa de renda familiar dos alunos.
- **Onde busca os dados:** Tabelas `ConselhoClasse` e `PerfilSocioeconomico`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": str, "nome": str, "valor": int}, ...]`.

---

## 9. Visualizações e Exportações

Esta seção documenta as funcionalidades de apresentação e exportação disponíveis na
**Central de BI** (`/relatorios/bi`), implementadas em
`app/relatorios/bi_routes.py` e `app/templates/relatorios/bi.html`.

---

### 9.1 Tipos de Visualização

Após executar um indicador, resultados do tipo **distribuição** (lista) oferecem quatro modos
de visualização selecionáveis no cabeçalho do card de resultado:

| Modo | Tipo Chart.js | Descrição |
|---|---|---|
| Tabela de Dados | — | Tabela HTML zebrada com Item e Valor |
| Gráfico de Barras | `bar` | Barras verticais com arredondamento e rótulo de valor no topo |
| Gráfico de Linhas | `line` | Linha com área preenchida e rótulo de valor em cada ponto |
| Gráfico de Pizza | `pie` | Fatias com percentual e valor absoluto diretamente na fatia |
| Gráfico de Rosca | `doughnut` | Idem pizza, em formato de rosca |

**Biblioteca utilizada:** [Chart.js v4](https://www.chartjs.org/) +
[chartjs-plugin-datalabels v2](https://chartjs-plugin-datalabels.netlify.app/) — ambos via CDN jsDelivr.

---

### 9.2 Rótulos e Percentuais nos Gráficos (`chartjs-plugin-datalabels`)

#### Gráficos circulares (Pizza / Rosca)

- **Nas fatias:** exibe `XX.X%` na primeira linha e o valor absoluto formatado na segunda linha.
  - Fatias com menos de **3%** do total **não recebem rótulo** (evita poluição visual em fatias pequenas).
  - Rótulos em branco com sombra para contraste em qualquer cor de fundo.
- **Na legenda (embaixo do gráfico):** cada item exibe `Nome da categoria  XX.X%`.
- **No tooltip (hover):** exibe `valor unidade  (XX.X%)`.

#### Gráficos de barra e linha

- **Rótulo de valor** exibido no topo de cada barra ou em cada ponto da linha.
- **No tooltip:** exibe `valor unidade` (sem percentual, pois não se aplica).

---

### 9.3 Exportação — XLSX

**Rota:** `GET /relatorios/bi/exportar/xlsx`

**Parâmetros de query string:**

| Parâmetro | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `codigo` | `str` | ✅ | Código do indicador (ex.: `ALU-005`) |
| `unidade_id` | `int` | ❌ | ID da unidade selecionada no filtro |
| `periodo_letivo_id` | `int` | ❌ | ID do período letivo selecionado |
| `turno` | `str` | ❌ | Turno selecionado (ex.: `Manhã`) |

**Comportamento:**
- Executa o indicador com os mesmos filtros ativos na tela no momento do clique.
- Gera o arquivo `.xlsx` em memória com `xlsxwriter` (sem gravar em disco).
- Retorna o arquivo como download com nome `pautaON_{CODIGO}_{YYYYMMDD_HHMM}.xlsx`.

**Estrutura da planilha gerada:**

| Linha | Conteúdo |
|---|---|
| 1 | Título: `Indicador: {nome}` (fundo branco, borda inferior azul) |
| 2 | `Código: {codigo} \| Unidade: {unidade}` (itálico, cinza) |
| 3 | `Gerado em: DD/MM/AAAA HH:MM` (itálico, cinza) |
| 5 | Cabeçalho da tabela: **Item / Dimensão** e **Valor** (fundo azul `#4361ee`, texto branco) |
| 6+ | Linhas de dados, zebradas (branco / azul-claro `#f0f4ff`), bordas sutis |
| Última | `Total de registros: N` (rodapé interno) |
| Rodapé | `pautaON — {nome indicador} — Página X de Y` |

Para resultados **escalares** (número único), o valor é exibido em célula mesclada A5:C6 com
fonte grande (`28pt`, azul).

**Implementação:** `app/relatorios/bi_routes.py` → função `bi_exportar_xlsx()`.
**Dependência:** `xlsxwriter` (já presente em `requirements.txt`).

---

### 9.4 Exportação — PNG

**Mecanismo:** 100% client-side, sem custo de servidor.

- Usa `Chart.instance.toBase64Image("image/png", 1.0)` do Chart.js para capturar o canvas atual.
- Cria dinamicamente um `<a download>` e dispara o clique para iniciar o download.
- Nome do arquivo: `pautaON_{CODIGO}_{YYYY-MM-DD}.png`.

**Disponibilidade do botão:**

| Estado da tela | Botão XLSX | Botão PNG |
|---|---|---|
| Nenhum indicador executado | oculto | oculto |
| Resultado numérico/escalar | ✅ visível | oculto |
| Resultado em tabela | ✅ visível | oculto |
| Gráfico ativo (barras/linhas/pizza/rosca) | ✅ visível | ✅ visível |
| Voltou para tabela após gráfico | ✅ visível | oculto |

---

### 9.5 Filtros Globais

Os três filtros da Central de BI são aplicados tanto na **execução dos indicadores** quanto
na **exportação XLSX** (os valores selecionados no momento do clique em "Exportar XLSX" são
enviados junto à requisição):

| Filtro | ID HTML | Parâmetro de API |
|---|---|---|
| Período Letivo | `filtroPeriodo` | `periodo_letivo_id` |
| Unidade | `filtroUnidade` | `unidade_id` |
| Turno | `filtroTurno` | `turno` |

---

_Última atualização: 2026-09-29_