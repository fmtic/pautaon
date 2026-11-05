# Catálogo de Indicadores — Módulo de Relatórios e BI (pautaON)

Este documento descreve todos os indicadores implementados na camada de Business Intelligence (BI)
do sistema `pautaON`, bem como as funcionalidades de visualização e exportação disponíveis na
**Central de BI** (`/relatorios/bi`).

Os indicadores estão agrupados por categorias temáticas. Cada item detalha o seu propósito
funcional, as tabelas/modelos consultados no banco de dados e a estrutura do dado retornado.

## Glossário do catálogo

Termos fixados na auditoria do AJ12 (§5 do relatório `docs/Relatórios/AJ12_AuditoriaBI.md`) e vale para toda a Central:

- **Cadastro novo vs aluno novo:** "cadastro novo" (ALU-004) é registro recém-criado em `Aluno.created_at`; **não** é "aluno novo no período" (ALU-013 — status Novo, sem inscrição em período anterior da mesma unidade). Os termos nunca devem ser usados como sinônimos.
- **"Ativo" sempre com o nome do campo:** `Aluno.ativo` (cadastro), `Inscricao.ativo` (vínculo), `Turma.ativo` (turma) ou `TurmaCurso.ativo` (oferta). Nenhum indicador deve dizer "ativo" sem qualificar o campo.
- **"Outros":** é o status **residual do classificador** de enturmação (`app.services.aluno_status`) — aluno que não se enquadra em nenhuma das outras categorias; entra em ALU-012 e não tem regra própria além do resíduo.
- **Unidade estatística de frequência/aulas:** FRE-* contam **linhas de lançamento** e AUL-* contam **linhas de registro de aula** — não pessoas nem dias. Um aluno com 20 lançamentos pesa 20 vezes em FRE-001/002/003; `J` (falta justificada) fica fora do numerador e do denominador das taxas.
- **Regra D2 (legado):** linhas de frequência/registro com `turma_curso_id NULL` pertencem à **oferta ativa única** da turma; fora desse caso ficam só nos totais de unidade/turma.

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
10. [Pendências do catálogo](#10-pendências-do-catálogo-bi-pósrelease--aj12aj14aj15)

(Além do [Glossário do catálogo](#glossário-do-catálogo), logo após a introdução.)

---

## 1. Categoria: Alunos

### ALU-001: Total de alunos com cadastro ativo no período
- **O que faz:** Conta alunos com `Aluno.ativo=True` no escopo do período, incluindo Novo, Renovado, Retornante e todas as categorias de não enturmados. Exclui cadastros inativos. ALU-001 deve ser igual a ALU-011 + ALU-012.
- **Onde busca os dados:** `app.services.aluno_status`, a partir de `Aluno`, `Inscricao`, `Turma` e `PeriodoLetivo`.
- **O que retorna:** Um número inteiro (`int`) com a contagem total.

### ALU-002: Alunos com cadastro ativo
- **O que faz:** Retorna o total de alunos cujo cadastro está ativo (`Aluno.ativo=True`). Esse indicador representa a situação cadastral, não a enturmação no período.
- **Onde busca os dados:** Tabela/Modelo `Aluno`; filtros de curso/professor resolvem pela OFERTA (`Inscricao.turma_curso_id` → `TurmaCurso`).
- **O que retorna:** Um número inteiro (`int`).

### ALU-003: Alunos com cadastro inativo
- **O que faz:** Retorna o total de alunos cujo cadastro está inativo (`Aluno.ativo=False`). Esse indicador representa a situação cadastral, não a enturmação no período.
- **Onde busca os dados:** Tabela/Modelo `Aluno`; filtros de curso/professor resolvem pela OFERTA (`Inscricao.turma_curso_id` → `TurmaCurso`).
- **O que retorna:** Um número inteiro (`int`).

### ALU-004: Novos cadastros
- **O que faz:** Conta registros **criados** em `Aluno.created_at` dentro do intervalo selecionado — **cadastro novo**, não "aluno novo no período" (ver Glossário; distinção travada na auditoria AJ12). Com período informado, usa `PeriodoLetivo.data_inicio` e `data_fim`; sem período, usa o período ativo vigente de cada unidade. Não exige enturmação nem `Aluno.ativo=True`; registros com `created_at` nulo não entram. O filtro de turno não se aplica a cadastros.
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
- **O que faz:** Conta alunos enturmados em P (Novo + Renovado + Retornante) identificados como PCD, usando `PerfilDiversidade.saude_laudo` ou o fallback legado `Aluno.diversidade_json`. **Base distinta de DIV-001:** ALU-007 restringe à enturmação em P; DIV-001 distribui todos os alunos com perfil PCD (ver DIV-001) — os totais não são comparáveis entre si.
- **Onde busca os dados:** `app.services.aluno_status`, `Aluno`, `Inscricao`, `Turma`, `PeriodoLetivo` e `PerfilDiversidade`.
- **O que retorna:** Um número inteiro (`int`).

### ALU-008: Alunos cadastrados por unidade
- **O que faz:** Agrupa e conta alunos cadastrados distintos por unidade de ensino, sem restringir pelo status da enturmação.
- **Onde busca os dados:** Tabelas `Aluno` e `Unidade`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": int, "nome": str, "valor": int}, ...]`.

### ALU-009: Alunos enturmados por curso
- **O que faz:** Agrupa por curso e conta alunos distintos enturmados em P/D (Novo + Renovado + Retornante), com inscrição vigente. O curso vem da OFERTA da inscrição (`TurmaCurso.curso_id`), não da turma. Cada aluno conta uma vez dentro de cada curso, de modo que a soma dos cursos pode exceder o total de alunos distintos da unidade. Sem período explícito, usa o período vigente de cada unidade.
- **Onde busca os dados:** `app.services.aluno_status`, `Aluno`, `Inscricao`, `TurmaCurso`, `Curso` e `PeriodoLetivo`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": int, "nome": str, "valor": int}, ...]`.
- **Pendente (BI pós-release, AJ12):** o filtro de **turno** ainda não se aplica a este indicador; decisão registrada no backlog (AJ15).

### ALU-010: Alunos por turma
- **O que faz:** Agrupa e conta a quantidade de alunos distintos vinculados a cada turma. Cada aluno conta UMA vez por turma, mesmo inscrito em mais de uma oferta; filtros de curso/professor resolvem pela OFERTA (`TurmaCurso`).
- **Onde busca os dados:** Tabelas `Aluno`, `Inscricao`, `TurmaCurso` e `Turma`.
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
- **O que faz:** Retorna o volume total de registros de inscrições conforme os filtros aplicados; curso/professor resolvem pela OFERTA da inscrição (`Inscricao.turma_curso_id` → `TurmaCurso`).
- **Onde busca os dados:** Tabela/Modelo `Inscricao` vinculada a `Turma` e `TurmaCurso`.
- **O que retorna:** Um número inteiro (`int`).

### INS-002: Inscrições ativas
- **O que faz:** Retorna o total de inscrições com status ativo (`ativo.is_(True)`); curso/professor pela OFERTA (`TurmaCurso`).
- **Onde busca os dados:** Tabela/Modelo `Inscricao` (e `TurmaCurso` para filtros de curso/professor).
- **O que retorna:** Um número inteiro (`int`).

### INS-003: Inscrições encerradas
- **O que faz:** Retorna o total de inscrições com status encerrado/inativo (`ativo.is_(False)`).
- **Onde busca os dados:** Tabela/Modelo `Inscricao`.
- **O que retorna:** Um número inteiro (`int`).

### INS-004: Novas inscrições
- **O que faz:** Retorna o volume de inscrições com **início** (`Inscricao.data_inicio`) no período informado — "nova" aqui é **início de vigência**, não data de criação do registro (semântica fixada na auditoria AJ12; a alternativa de usar `created_at` ficou pendente de decisão de negócio).
- **Onde busca os dados:** Tabela/Modelo `Inscricao` (`data_inicio`).
- **O que retorna:** Um número inteiro (`int`).

### INS-005: Desativações
- **O que faz:** Retorna a contagem de inscrições desativadas.
- **Onde busca os dados:** Tabela/Modelo `Inscricao`.
- **O que retorna:** Um número inteiro (`int`).

### INS-006: Motivos de desativação _(indisponível — não implementado, oculto da Central)_
- **Motivo:** Não há dados de motivo de desativação registrados no banco. Desde o AJ14, o indicador **não aparece na lista da Central** enquanto não for implementado; a chamada direta pela API continua respondendo com o erro de não implementado (400).

### INS-007: Tempo médio de permanência _(indisponível — não implementado, oculto da Central)_
- **Motivo:** Não há registros com `data_desativacao` preenchida no banco. Desde o AJ14, o indicador **não aparece na lista da Central** enquanto não for implementado; a chamada direta pela API continua respondendo com o erro de não implementado (400).

### INS-008: Inscrições por curso
- **O que faz:** Agrupa e conta o total de inscrições vinculadas a cada curso; o curso vem da OFERTA da inscrição (`Inscricao.turma_curso_id` → `TurmaCurso.curso_id`).
- **Onde busca os dados:** Tabelas `Inscricao`, `TurmaCurso` e `Curso`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": int, "nome": str, "valor": int}, ...]`.

---

## 3. Categoria: Frequência

### FRE-001: Total de lançamentos de frequência
- **O que faz:** Retorna o número total de registros de frequência lançados. Filtros de curso/professor resolvem pela OFERTA da linha (`Frequencia.turma_curso_id` → `TurmaCurso`); linhas legadas (NULL) entram quando a oferta é a única ativa da turma (regra D2).
- **Onde busca os dados:** Tabela/Modelo `Frequencia` (e `TurmaCurso` para filtros de curso/professor).
- **O que retorna:** Um número inteiro (`int`).

### FRE-002: Total de presenças
- **O que faz:** Conta o total de registros onde o conceito de presença está contabilizado (`A`, `B`, `C`, `D`); curso/professor pela OFERTA da linha (legado segue a regra D2).
- **Onde busca os dados:** Tabela/Modelo `Frequencia` (e `TurmaCurso` para filtros de curso/professor).
- **O que retorna:** Um número inteiro (`int`).

### FRE-003: Total de faltas
- **O que faz:** Conta o total de registros de faltas não justificadas (`F`); curso/professor pela OFERTA da linha (legado segue a regra D2).
- **Onde busca os dados:** Tabela/Modelo `Frequencia` (e `TurmaCurso` para filtros de curso/professor).
- **O que retorna:** Um número inteiro (`int`).

### FRE-004: Total de faltas justificadas
- **O que faz:** Conta o total de registros de faltas justificadas (`J`); curso/professor pela OFERTA da linha (legado segue a regra D2).
- **Onde busca os dados:** Tabela/Modelo `Frequencia` (e `TurmaCurso` para filtros de curso/professor).
- **O que retorna:** Um número inteiro (`int`).

### FRE-005: Frequência média
- **O que faz:** Calcula a **taxa global ponderada por lançamento** de frequência — presenças / (presenças + faltas) sobre **todas as linhas** do escopo, desconsiderando faltas justificadas (`J` fora de numerador e denominador). **Não é** a média aritmética dos percentuais por aluno: alunos com mais lançamentos pesam mais (distinção travada na auditoria AJ12). Arredondado a 1 casa, pelo serviço `app/services/frequencia_oferta.py`; curso/professor pela OFERTA da linha (legado segue a regra D2).
- **Onde busca os dados:** Tabela/Modelo `Frequencia` (e `TurmaCurso` para filtros de curso/professor).
- **O que retorna:** Um valor percentual arredondado (`float`).

### FRE-006: Alunos com frequência ≥ 90%
- **O que faz:** Conta os alunos cuja frequência individual, **arredondada a 1 casa**, é ≥ 90 (faixa hi do serviço `app/services/frequencia_oferta.py`). Um aluno com 89,96 vira 90,0 e entra aqui. As três faixas (FRE-006/007/008) somam exatamente o total de alunos com frequência contável.
- **Onde busca os dados:** Tabela/Modelo `Frequencia` (e `TurmaCurso` para filtros de curso/professor).
- **O que retorna:** Um número inteiro (`int`).

### FRE-007: Alunos com frequência entre 75% e 89%
- **O que faz:** Conta os alunos cuja frequência individual, **arredondada a 1 casa**, está entre 75 e 89,9 (faixa mid do serviço `app/services/frequencia_oferta.py`). Valores como 89,95 arredondam para 90,0 e pertencem à faixa FRE-006.
- **Onde busca os dados:** Tabela/Modelo `Frequencia` (e `TurmaCurso` para filtros de curso/professor).
- **O que retorna:** Um número inteiro (`int`).

### FRE-008: Alunos com frequência inferior a 75%
- **O que faz:** Conta os alunos cuja frequência individual, **arredondada a 1 casa**, está abaixo de 75 (faixa lo do serviço `app/services/frequencia_oferta.py`); 74,9 é lo e 75,0 é mid.
- **Onde busca os dados:** Tabela/Modelo `Frequencia` (e `TurmaCurso` para filtros de curso/professor).
- **O que retorna:** Um número inteiro (`int`).

### FRE-009: Frequência por turma
- **O que faz:** Calcula a taxa média de frequência agrupada por cada turma, em lote pelo serviço `app/services/frequencia_oferta.py` (`agregar_por_turma`), sem iterar turma a turma. O percentual é POR TURMA sobre todas as suas linhas (inclusive legado); com filtro de curso/professor, as turmas são selecionadas pela OFERTA.
- **Onde busca os dados:** Tabelas `Turma`, `Frequencia` e `TurmaCurso`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": int, "nome": str, "valor": float}, ...]`.

### FRE-010: Frequência por curso
- **O que faz:** Calcula a taxa média de frequência agrupada por curso, em lote pelo serviço `app/services/frequencia_oferta.py` (`agregar_por_oferta`). Usa somente linhas da OFERTA; linhas legadas entram no curso da oferta quando ela é a única ativa da turma (regra D2) e, nos demais casos, só nos totais da unidade/turma.
- **Onde busca os dados:** Tabelas `Frequencia`, `TurmaCurso` e `Curso`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": int, "nome": str, "valor": float}, ...]`.

---

## 4. Categoria: Turmas

### TUR-001: Turmas ativas
- **O que faz:** Retorna o total de turmas **ativas** (`Turma.ativo=True`) conforme os filtros aplicados — descreve exatamente a implementação (alinado no AJ12; "total geral" com inativas seria mudança de regra, registrada como decisão em aberto na seção de duplicados).
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
- **O que faz:** Agrupa e conta turmas por **curso da OFERTA ativa** (`TurmaCurso.curso_id`), e não pelo curso legado da turma; cada turma conta **uma vez por curso** (implementado no AJ14). Turma sem oferta ativa com curso não entra na distribuição.
- **Onde busca os dados:** Tabelas `Turma`, `TurmaCurso` e `Curso`.
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
- **O que faz:** Agrupa e conta turmas pelo **professor da OFERTA ativa** (`TurmaCurso.professor_id`), e não pelo `professor_id` vestigial da turma; cada turma conta **uma vez por professor** (implementado no AJ14). Turma sem oferta ativa com professor não entra na distribuição.
- **Onde busca os dados:** Tabelas `Turma`, `TurmaCurso` e `User`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": int, "nome": str, "valor": int}, ...]`.

---

## 5. Categoria: Aulas

### AUL-001: Total de aulas registradas
- **O que faz:** Retorna o total consolidado de aulas ministradas e registradas. Filtros de curso/professor resolvem pela OFERTA do registro (`RegistroAula.turma_curso_id` → `TurmaCurso`); registros legados (NULL) entram quando a oferta é a única ativa da turma (regra D2).
- **Onde busca os dados:** Tabela/Modelo `RegistroAula` (com `Turma` para período e `TurmaCurso` para curso/professor).
- **O que retorna:** Um número inteiro (`int`).

### AUL-002: Aulas por turma
- **O que faz:** Agrupa e conta a quantidade de aulas registradas por turma; com filtro de curso/professor, as turmas são selecionadas pela OFERTA (`TurmaCurso`).
- **Onde busca os dados:** Tabelas `RegistroAula`, `Turma` e `TurmaCurso`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": int, "nome": str, "valor": int}, ...]`.

### AUL-003: Aulas por período
- **O que faz:** Agrupa e conta a quantidade de aulas registradas por período letivo.
- **Onde busca os dados:** Tabelas `RegistroAula`, `Turma` e `PeriodoLetivo`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": int, "nome": str, "valor": int}, ...]`.

### AUL-004: Aulas por professor
- **O que faz:** Agrupa e conta a quantidade de aulas registradas por professor. A distribuição é pelo PROFESSOR DA OFERTA do registro (`TurmaCurso.professor_id`), não pelas colunas da turma; registros legados seguem a oferta única ativa da turma (regra D2).
- **Onde busca os dados:** Tabelas `RegistroAula`, `TurmaCurso` e `User`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": int, "nome": str, "valor": int}, ...]`.

### AUL-005: Aulas por curso
- **O que faz:** Agrupa e conta a quantidade de aulas registradas por curso. A distribuição é pelo CURSO DA OFERTA do registro (`TurmaCurso.curso_id`); registros legados entram só quando a oferta é a única ativa da turma (regra D2).
- **Onde busca os dados:** Tabelas `RegistroAula`, `TurmaCurso` e `Curso`.
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
- **O que faz:** Distribui os alunos PCD por tipo de deficiência declarada, sobre **todos os alunos com perfil** (não restringe à enturmação em P — **base distinta de ALU-007**, que conta só enturmados em P). Um aluno com **mais de um tipo** declarado é contado **em cada tipo**, por isso a soma das categorias **pode exceder** o total de alunos PCD distintos.
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
- **O que faz:** Identifica alunos com frequência crítica — percentual **arredondado a 1 casa** abaixo de 75 (faixa lo do serviço `app/services/frequencia_oferta.py`) — cruzando com o perfil de vulnerabilidade socioeconômica.
- **Onde busca os dados:** Tabelas `Frequencia`, `TurmaCurso` e `PerfilSocioeconomico`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": str, "nome": str, "valor": int}, ...]`.

### CRU-002: Alunos por raça/cor no Conselho de Classe
- **O que faz:** Distribui por raça/cor declarada os alunos **com ao menos uma `ConselhoResposta` preenchida** no escopo do conselho (turma/período) — existência de registro-base sem resposta **não** conta como participação (regra implementada no AJ14); filtros de curso/professor resolvem pela OFERTA do conselho (`ConselhoClasse.turma_curso_id` → `TurmaCurso`).
- **Onde busca os dados:** Tabelas `ConselhoClasse`, `TurmaCurso` e `PerfilDiversidade`.
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
- **O que faz:** Cruza os resultados do Conselho de Classe com a faixa de renda familiar dos alunos, considerando **somente `ConselhoClasse` com `situacao_final` não nula** (regra implementada no AJ14); filtros de curso/professor resolvem pela OFERTA do conselho (`ConselhoClasse.turma_curso_id` → `TurmaCurso`).
- **Onde busca os dados:** Tabelas `ConselhoClasse`, `TurmaCurso` e `PerfilSocioeconomico`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": str, "nome": str, "valor": int}, ...]`.

---

## 9. Visualizações e Exportações

Esta seção documenta as funcionalidades de apresentação e exportação disponíveis na
**Central de BI** (`/relatorios/bi`), implementadas em
`app/relatorios/bi_routes.py` e `app/templates/relatorios/bi.html`.

---

### 9.1 Tipos de Visualização

Após executar um indicador, resultados do tipo **distribuição** (lista) oferecem **cinco** modos
de visualização selecionáveis no cabeçalho do card de resultado (corrigido no AJ12 — o texto
antigo dizia "quatro" e listava cinco):

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

Os **três filtros visíveis** da Central de BI são aplicados tanto na **execução dos indicadores** quanto
na **exportação XLSX** (os valores selecionados no momento do clique em "Exportar XLSX" são
enviados junto à requisição). **Somente estes três têm controles na tela** (alinado no AJ12);
curso, turma e professor são aceitos pela API/exportação, mas **não possuem controles visíveis** na Central:

| Filtro | ID HTML | Parâmetro de API |
|---|---|---|
| Período Letivo | `filtroPeriodo` | `periodo_letivo_id` |
| Unidade | `filtroUnidade` | `unidade_id` |
| Turno | `filtroTurno` | `turno` |

---

## 10. Pendências do catálogo (BI pós-release — AJ12/AJ14/AJ15)

Registradas no backlog (entrada de 05/11/2026), sem alteração de código neste documento:

- **CRU-004** deve apurar o **curso de origem pela OFERTA** da inscrição transferida (hoje resolve por turma/curso legado).
- **ALU-009** deve passar a aceitar o **filtro de turno** (ver nota no item).
- **TUR-004** deve contar **aluno distinto** por turma (hoje é média sobre linhas de inscrição).
- **Consolidar duplicados:** INS-003/INS-005 (mesmo critério de inscrição inativa), TUR-001/TUR-002 (ambos contam turmas ativas), ALU-010/TUR-003 (aliases da mesma função).
- **Implementar INS-006/INS-007** com critérios aprovados (hoje indisponíveis e ocultos da Central).
- **DIV-001 vs ALU-007:** bases distintas documentadas; eventual unificação depende de decisão de negócio.

---

_Última atualização: 2026-11-05 — glossário e correções da auditoria AJ12 (§5 do relatório) e das correções do AJ14 (INS-006/007 ocultos, TUR-005/008 por oferta, CRU-002 por resposta preenchida, CRU-005 só com `situacao_final`), registradas na tarefa AJ15._