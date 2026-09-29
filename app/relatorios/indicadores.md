# Catálogo de Indicadores - Módulo de Relatórios e BI (pautaON)

Este documento descreve todos os indicadores implementados na camada de Business Intelligence (BI) do sistema `pautaON`. Os indicadores estão agrupados por categorias temáticas (`alunos`, `inscricoes`, `frequencia`, `turmas` e `aulas`). Cada item detalha o seu propósito funcional, as tabelas/modelos consultados no banco de dados e a estrutura do dado retornado.

---

## 1. Categoria: Alunos

### ALU-001: Total de alunos
- **O que faz:** Retorna o total geral de alunos distintos cadastrados que correspondem aos filtros globais da central de BI.
- **Onde busca os dados:** Tabela/Modelo `Aluno` (com suporte a filtros por unidade, período letivo, curso, turma e professor através de junções com `Inscricao` e `Turma`).
- **O que retorna:** Um número inteiro (`int`) com a contagem total.

### ALU-002: Alunos ativos
- **O que faz:** Retorna o total de alunos cujo status está marcado como ativo (`ativo.is_(True)`).
- **Onde busca os dados:** Tabela/Modelo `Aluno`.
- **O que retorna:** Um número inteiro (`int`).

### ALU-003: Alunos inativos
- **O que faz:** Retorna o total de alunos cuja situação está marcada como inativa (`ativo.is_(False)`).
- **Onde busca os dados:** Tabela/Modelo `Aluno`.
- **O que retorna:** Um número inteiro (`int`).

### ALU-004: Novos alunos
- **O que faz:** Retorna a quantidade de novos alunos cadastrados considerando os filtros temporais ou de período informados.
- **Onde busca os dados:** Tabela/Modelo `Aluno`.
- **O que retorna:** Um número inteiro (`int`).

### ALU-005: Alunos por sexo
- **O que faz:** Distribui e conta os alunos ativos agrupados por gênero. Prioriza o campo estruturado `PerfilDiversidade.genero` (Onda 3A); para alunos sem perfil estruturado, faz fallback no JSON legado `Aluno.diversidade_json`. Suporta os filtros globais do BI.
- **Onde busca os dados:** Tabelas/Modelos `Aluno` e `PerfilDiversidade` (com fallback em `Aluno.diversidade_json`).
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": str, "nome": str, "valor": int}, ...]`, ordenada do maior para o menor.

### ALU-006: Alunos por faixa etária
- **O que faz:** Distribui e conta os alunos ativos agrupados por faixa etária, calculada a partir de `Aluno.data_nascimento`. Alunos sem data de nascimento são agrupados em "Não Informado". Suporta os filtros globais do BI. As faixas são: **Menor de 12 anos**, **12 a 17 anos**, **18 a 24 anos**, **25 a 39 anos**, **40 a 59 anos**, **60 anos ou mais** e **Não Informado**.
- **Onde busca os dados:** Tabela/Modelo `Aluno`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": str, "nome": str, "valor": int}, ...]`, na ordem das faixas definidas, omitindo faixas com zero alunos.

### ALU-007: Alunos PCD
- **O que faz:** Retorna a quantidade de alunos identificados como PCD (Pessoa com Deficiência), validando o relacionamento estruturado `PerfilDiversidade` (campo `saude_laudo`) ou fallback em dados legados JSON.
- **Onde busca os dados:** Tabela/Modelo `Aluno` e `PerfilDiversidade`.
- **O que retorna:** Um número inteiro (`int`).

### ALU-008: Alunos por unidade
- **O que faz:** Agrupa e conta a quantidade de alunos distintos segmentados por unidade de ensino.
- **Onde busca os dados:** Tabelas `Aluno` e `Unidade`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": int, "nome": str, "valor": int}, ...]`.

### ALU-009: Alunos por curso
- **O que faz:** Agrupa e conta a quantidade de alunos distintos matriculados em cada curso.
- **Onde busca os dados:** Tabelas `Aluno`, `Inscricao`, `Turma` e `Curso`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": int, "nome": str, "valor": int}, ...]`.

### ALU-010: Alunos por turma
- **O que faz:** Agrupa e conta a quantidade de alunos distintos vinculados a cada turma.
- **Onde busca os dados:** Tabelas `Aluno`, `Inscricao` e `Turma`.
- **O que retorna:** Uma lista de dicionários estruturados: `[{"id": int, "nome": str, "valor": int}, ...]`.

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

### FRE-006: Alunos com frequência $\ge 90\%$
- **O que faz:** Identifica e conta o número de alunos cuja frequência individual calculada é maior ou igual a $90\%$.
- **Onde busca os dados:** Tabela/Modelo `Frequencia`.
- **O que retorna:** Um número inteiro (`int`).

### FRE-007: Alunos com frequência entre $75\%$ e $89\%$
- **O que faz:** Identifica e conta o número de alunos com frequência individual situada na faixa entre $75\%$ e $89\%$.
- **Onde busca os dados:** Tabela/Modelo `Frequencia`.
- **O que retorna:** Um número inteiro (`int`).

### FRE-008: Alunos com frequência inferior a $75\%$
- **O que faz:** Identifica e conta o número de alunos cuja frequência individual está abaixo do limite crítico de $75\%$.
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