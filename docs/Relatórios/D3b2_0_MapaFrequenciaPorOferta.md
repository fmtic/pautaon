# D3b-2.0 — Mapa da frequência/diário por oferta (somente leitura)

**Branch:** `nova_feature` · **HEAD Alembic:** `8d2e3f4a5b6c` · **Suíte:** 662 passed · **Data:** 27/10/2026

Tarefa de **mapeamento** (P0–P4). Nenhuma alteração de código, teste, schema ou banco. Nenhuma migration.

---

## P0 — Pré-requisitos

- Branch: `nova_feature` (confirmado).
- HEAD: `a4dfbe99161c042ba82e3e8bb035c4ef67aecdf1` → Alembic `8d2e3f4a5b6c`.
- Suíte: `662 passed, 222 warnings`.
- **Atenção:** `git status` NÃO está limpo (modificações da série H + tmp*). Recomenda-se limpar antes das etapas D3b-2.x. Este relatório é o único artefato novo do commit.

---

## P1 — Inventário exaustivo

Legenda: **(a)** já por oferta; **(b)** agrega por `turma_id` somando ofertas; **(c)** ramo legado `turma_curso_id IS NULL`; **(d)** escrita/limpeza destrutiva por `turma_id`; **(e)** N+1.

### 1.1 Modelo e serviço

| Arquivo:linha | Função / classe | O que faz hoje | Impacto com 2+ ofertas | Class. |
|---|---|---|---|---|
| `app/models/academico.py:151` | `Turma.freq_geral` (property) | Soma todas as linhas (ofertas + legado) via `agregar_por_turma` | % única por turma, mistura ofertas | **(b)** |
| `app/models/academico.py:170` | `Turma.freq_geral_oferta(id)` | % de uma oferta; legado só se oferta única ativa (D2) | % por oferta | **(a)** |
| `app/services/frequencia_oferta.py:134` | `ofertas_unicas_ativas` | Define ofertas que recebem legado | Auxiliar D2 | **(a)** |
| `app/services/frequencia_oferta.py:181` | `agregar_por_oferta` | 1 consulta, bucketing por oferta + legado | Sem N+1, por oferta | **(a)** |
| `app/services/frequencia_oferta.py:312` | `agregar_por_turma` | 1 consulta por `turma_id` (soma ofertas + legado) | % por turma | **(b)** |

### 1.2 Utils

| Arquivo:linha | Função | O que faz hoje | Impacto com 2+ ofertas | Class. |
|---|---|---|---|---|
| `app/utils/logica.py:104` | `calcular_estatisticas_frequencia` | Função pura de conceitos → % | Sem efeito de oferta | neutro |
| `app/utils/logica.py:372` | `carregar_frequencias` | Por oferta se `turma_curso_id` informado; senão legado (NULL) | Leitura correta por oferta | **(a)/(c)** |
| `app/utils/logica.py:429` | `salvar_frequencia` | Resolve oferta; grava por (oferta, data) ou legado (turma, data, NULL) | Escrita correta por oferta | **(a)/(c)** |
| `app/utils/logica.py:613` | `calcular_frequencias_relatorio` | `p_geral`: todas as linhas; `f_prog`: `Turma.programa`; `f_turma`: `agregar_por_turma`; `f_prof`: `agregar_por_oferta` | turma/programa agregam; prof por oferta | **(b)** turma/programa |
| `app/utils/logica.py:713` | `calcular_metricas_conselho` | `RegistroAula` por unidade | Não separa por oferta | **(b)** |
| `app/utils/frequencia.py:29` | `alunos_ativos_da_turma` | `Inscricao.turma_id == turma_id` | Alunos de todas as ofertas | **(b)** |
| `app/utils/frequencia.py:50` | `frequencias_lancadas` | Por oferta se `turma_curso_id` informado; senão por turma | Correto quando por oferta | **(a)/(c)** |
| `app/utils/frequencia.py:106` | `contar_pendencias_frequencia` | Com 2+ ofertas: por oferta; senão por turma | Já por oferta no ramo multi | **(a)/(b)** |

### 1.3 Painel pedagógico

| Arquivo:linha | Função | O que faz hoje | Impacto com 2+ ofertas | Class. |
|---|---|---|---|---|
| `app/relatorios/painel_pedagogico/frequencia.py:24` | `agregar_por_turma` | Delegação ao serviço (soma ofertas + legado) | % por turma | **(b)** |
| `app/relatorios/painel_pedagogico/periodo.py:211` | `montar_visao_periodo` | `agregar_por_turma(turmas_ids)` | Turmas sem linha não aparecem (§12.21) | **(b)** |

### 1.4 BI

| Arquivo:linha | Função | O que faz hoje | Impacto com 2+ ofertas | Class. |
|---|---|---|---|---|
| `app/relatorios/bi_alunos.py:54` | `_base_frequencia` | `Frequencia.turma_id == filtros["turma_id"]`; lê `turma_curso_id` | Filtra por turma, não por oferta | **(b)** |
| `app/relatorios/bi_alunos.py:97` | `_base_registro_aula` | Join único em `Turma`; lê `turma_curso_id` | Por turma (diário) | **(b)** |
| `app/relatorios/bi_alunos.py:1047`+ | `total_lancamentos_frequencia`, `total_presencas`, `total_faltas`, `total_faltas_justificadas`, `frequencia_media` | Via `_base_frequencia` | Por turma | **(b)** |
| `app/relatorios/bi_alunos.py:1192/1216/1240` | `alunos_frequencia_90/75_89/inferior_75` | `_contagem_por_faixa` sobre `_base_frequencia` | Por turma | **(b)** |
| `app/relatorios/bi_alunos.py:1264` | `frequencia_por_turma` | Agrega por `Frequencia.turma_id` (todas as linhas) | % por turma (soma ofertas) | **(b)** |
| `app/relatorios/bi_alunos.py:1362` | `frequencia_por_curso` | Por curso via `TurmaCurso.curso_id` + regra D2 legado | % por curso (por oferta) | **(a)** |
| `app/relatorios/bi_alunos.py:1943/2000` | `aulas_por_*` (professor/curso/tema/unidade/dia) | `RegistroAula` por oferta (`turma_curso_id`) com ramo legado NULL | Por oferta + legado | **(a)/(c)** |
| `app/relatorios/bi_alunos.py:2572` | `frequencia_critica_por_vulnerabilidade` | Via `_base_frequencia` | Por turma | **(b)** |
| `app/relatorios/bi_alunos.py:2630` | `alunos_raca_conselho` (CRU-002) | `ConselhoClasse` por turma/oferta | Por oferta (conselho) | **(a)** |
| `app/relatorios/bi_alunos.py:2788` | `desempenho_conselho_por_renda` (CRU-005) | Idem | Por oferta | **(a)** |
| `app/relatorios/bi_alunos.py:614/712` | `alunos_por_curso` (ALU-009) / `alunos_por_turma` (ALU-010) | Aplicam `cond_inscricao_enturmada` | Já por oferta | **(a)** (já aplicado) |

### 1.5 Registros (rotas)

| Arquivo:linha | Função | O que faz hoje | Impacto com 2+ ofertas | Class. |
|---|---|---|---|---|
| `app/registros/core.py:196` | `frequencia()` GET | Estatísticas por turma (todas as linhas do aluno) + `carregar_frequencias` por oferta/legado | Estats agregam ofertas; pauta por oferta | **(b)** estats / **(a)/(c)** pauta |
| `app/registros/core.py:456` | `frequencia_relatorio` | Via `calcular_estatisticas_frequencia` | Por turma | **(b)** |
| `app/registros/turmas.py:489` | `aplicar_filtros_turmas` | `min_freq` sobre `freq_geral_oferta(principal.id)` ou `freq_geral` | Só oferta principal filtrada | **(a)** (só principal) |
| `app/registros/turmas.py:614` | `pos_filtrar_turmas` | idem (`min_freq`) | idem | **(a)** (só principal) |
| `app/registros/turmas.py:1238` | `ver_turma` | Lê ofertas; frequência por oferta quando aplicável | Por oferta | **(a)** |
| `app/registros/turmas.py:1456` | `_editar_turma_contexto` | `tem_lancamentos` por `turma_id` (todas as ofertas) | Não distingue oferta | **(b)** |
| `app/registros/turmas.py:1541` | `editar_turma` | Limpeza `Frequencia`/`RegistroAula` por `turma_id` (todas as ofertas) | **Destrutivo** para todas as ofertas | **(d)** |
| `app/registros/turmas.py:2135` | `excluir_turma` | `turma_tem_historico` (por turma ou oferta); exclusão física apaga ofertas | Histórico detectado; apaga todas as ofertas | **(a)** detecção / **(d)** apagar |
| `app/registros/turmas.py:2521` | `imprimir_pauta` | Por oferta (`turma_curso_id`) com ramo legado | Por oferta | **(a)/(c)** |
| `app/registros/alunos.py:869` | `historico_aluno` | Frequência por inscrição/oferta (`turma_curso_id=oferta_id`) | Por oferta; **N+1** (consulta no loop) | **(a)** + **(e)** |
| `app/registros/periodos.py:522` | `periodo_letivo_relatorio_certificado` | Por oferta (`turma_curso_id=oferta.id`) | Por oferta | **(a)** |

### 1.6 Templates / JS

| Arquivo:linha | O que faz hoje | Class. |
|---|---|---|
| `app/templates/turmas/listar.html:308` | `turma.freq_geral` (soma) na sub-linha/coluna | **(b)** |
| `app/templates/turmas/listar.html:422` | `turma.freq_geral_oferta(o.id)` por oferta | **(a)** |
| `app/static/js/relatorios/relatorio_alunos.js:13` | campo `freq_geral` (BI) | **(b)** |

### 1.7 BI programa

| Arquivo:linha | O que faz hoje | Class. |
|---|---|---|
| `app/utils/logica.py:660` | `f_prog` por `Turma.programa` (projeção), não `TurmaCurso.programa` | **(b)** — decisão 6 do L3 (MANTER por enquanto) |

---

## P2 — Dados reais (READ ONLY)

Bancos consultados (transação `BEGIN READ ONLY`): **`pautaon`** (principal) e **`pautaon_ensaio`** (scratch). Ambos com Alembic `8d2e3f4a5b6c`.

### 2.1 Contagens agregadas

| Tabela | principal (`pautaon`) | scratch (`pautaon_ensaio`) |
|---|---|---|
| `frequencia` total | 0 | 0 |
| `frequencia` com `turma_curso_id IS NULL` | 0 | 0 |
| `frequencia` com `turma_curso_id NOT NULL` | 0 | 0 |
| `registro_aula` total | 0 | 0 |
| `registro_aula` com `turma_curso_id IS NULL` | 0 | 0 |
| `registro_aula` com `turma_curso_id NOT NULL` | 0 | 0 |
| `turma` | 3 | 3 |
| `turma_curso` (ofertas) | 5 | 5 |
| `inscricoes` | 26 | 26 |

### 2.2 Turmas e ofertas

| Turma | Ofertas (ativas) | Inscritos por oferta |
|---|---|---|
| 9 — Mecânica de popa | 3 (11, 12, 13) | oferta 11: 0; oferta 12: 0; oferta 13: 3 |
| 10 — Informática | 1 (14) | 13 |
| 11 — Natação | 1 (15) | 10 |

- **Turmas com 2+ ofertas:** 1 (`Mecânica de popa`, 3 ofertas). Lançamentos por oferta: **0 em todas**.
- **Turmas sem oferta ativa com lançamentos:** 0.
- **Duplicatas potenciais (aluno, turma, data):** 0 em `frequencia` e `registro_aula`.

### 2.3 Observação

Os dois bancos locais estão **sem lançamentos** de frequência/diário. A caracterização numérica depende de dados; os valores de referência são os da suíte (`tests/test_frequencia_oferta.py`, `tests/test_bi_oferta.py`), que exercitam 2 ofertas (Alfa) e turma de oferta única com legado (Gema). Recomenda-se validar as etapas no scratch após inserir dados de teste.

---

## P3 — Decisões a propor

### D1 — Contrato por leitor (por oferta × turma = soma das ofertas)

**Recomendação:**
- **Manter por turma = soma das ofertas** para: `Turma.freq_geral`, `frequencia_por_turma` (BI), `calcular_frequencias_relatorio.f_turma`, painel pedagógico (turma/período), listagem (coluna freq), relatório geral.
- **Manter por oferta** para: `freq_geral_oferta`, `frequencia_por_curso` (BI), conselho (CRU-002/005), ficha/histórico do aluno, certificado, painel do professor, pauta de lançamento.
- **Decisão dependente:** o painel pedagógico deve ganhar visão **por oferta** (drill-down) além da visão por turma? Recomendação: adicionar como opcional, sem remover a visão por turma.

### D2 — Destino dos registros legados (`turma_curso_id IS NULL`)

**Recomendação:** manter os registros legados (não backfill) e aplicar a regra D2 em leitura (oferta única ativa recebe o legado). Backfill inequívoco só para turmas com **exatamente uma oferta ativa**; para 2+ ofertas o legado é ambíguo.
- **Decisão dependente:** autorizar script de backfill (não migration) para o ramo inequívoco (oferta única ativa), com dry-run? Recomendação: sim, em etapa separada, com backup do scratch.

### D3 — `excluir_turma` / `editar_turma`: apagar só da oferta afetada

**Recomendação:**
- `excluir_turma`: detecção de histórico já é por turma ou oferta (correto). Exclusão física apaga todas as ofertas (cascata) — manter (exclusão da turma inteira).
- `editar_turma` (limpeza de lançamentos): hoje apaga **todas** as ofertas. Recomendação: com 2+ ofertas ativas, exigir escolha da oferta (ou confirmar "todas"); com 0/1 oferta, manter atual.
- **Decisão dependente:** confirmar se a limpeza deve ser por oferta (recomendado) ou manter por turma.

### D4 — Estatísticas do GET `/frequencia` separadas por oferta

**Recomendação:** hoje as estatísticas (presença/falta/J) são calculadas sobre **todas as linhas do aluno na turma** (agregam ofertas). Com `turma_curso_id` informado, filtrar `Frequencia` por oferta. Impacto: números visíveis mudam para turmas com 2+ ofertas.
- **Decisão dependente:** confirmar a mudança (recomendado: sim, por oferta quando houver oferta selecionada).

### D5 — Remoção do N+1 de `freq_geral` e do histórico do aluno

**Recomendação:**
- `freq_geral` (property) chama `agregar_por_turma` por turma → N consultas. Na listagem, pré-calcular um mapa `turma_id → pct` uma única vez. **Não muda número**, só performance.
- Histórico do aluno: consulta `Frequencia` dentro do loop de inscrições (N+1). Buscar em lote por `aluno_id` e agrupar por `turma_curso_id`. **Não muda número**.
- **Decisão dependente:** priorizar junto com D3b-2.2 (recomendado: sim).

### D6 — ALU-009/ALU-010 e `cond_inscricao_enturmada`; BI ler `turma_curso.programa`

**Recomendação:**
- ALU-009 (`alunos_por_curso`) e ALU-010 (`alunos_por_turma`) **já aplicam** `cond_inscricao_enturmada` (verificado em código). Backlog desatualizado — marcar como concluído.
- BI ler `turma_curso.programa` em vez de `Turma.programa`: `calcular_frequencias_relatorio.f_prog` usa `Turma.programa` (projeção). Migrar para `TurmaCurso.programa` (já obrigatório) pode mudar números se `turma.programa ≠ oferta.programa`.
- **Decisão dependente:** autorizar a migração de `f_prog` para `TurmaCurso.programa` (recomendado: sim, em etapa separada, com ensaio de números).

---

## P4 — Plano em etapas

### D3b-2.1 — Caracterização (já iniciada)
- **Escopo:** fixar números atuais via testes (`tests/test_frequencia_oferta.py`, `tests/test_bi_oferta.py`).
- **Arquivos:** testes existentes.
- **Migration:** não.
- **Risco:** baixo.

### D3b-2.2 — Remover N+1 de `freq_geral` na listagem
- **Escopo:** pré-calcular mapa `turma_id → pct_turma` uma vez em `aplicar_filtros_turmas`/rota `turma`; template lê o mapa.
- **Arquivos:** `app/registros/turmas.py`, `app/templates/turmas/listar.html`.
- **Testes de caracterização antes:** `tests/test_filtros_turmas.py` (N+1), `tests/test_frequencia_oferta.py`.
- **Ensaio no scratch:** comparar consultas (EXPLAIN) antes/depois; números inalterados.
- **Risco:** baixo. **Não muda número visível.**
- **Migration:** não.

### D3b-2.3 — Estatísticas do GET `/frequencia` por oferta
- **Escopo:** filtrar `Frequencia` por `turma_curso_id` quando informado, na rota `frequencia()`.
- **Arquivos:** `app/registros/core.py`.
- **Testes de caracterização antes:** `tests/test_frequencia_oferta.py`, testes de lançamento.
- **Ensaio:** números antigo (todas as linhas) × novo (por oferta) no scratch.
- **Risco:** médio. **Muda número visível** (estatísticas da pauta).
- **Migration:** não. **Depende de D4.**

### D3b-2.4 — Limpeza destrutiva por oferta em `editar_turma`
- **Escopo:** substituir `filter_by(turma_id=id).delete()` por limpeza por oferta quando 2+ ofertas (exigir escolha/confirmar todas).
- **Arquivos:** `app/registros/turmas.py`.
- **Testes de caracterização antes:** testes de edição de turma.
- **Ensaio:** verificar que lançamentos de outras ofertas são preservados.
- **Risco:** alto (perda de dados se mal feito). **Muda comportamento visível.**
- **Migration:** não. **Depende de D3.**

### D3b-2.5 — Backfill do legado (script, opcional)
- **Escopo:** script (não migration) para atribuir `turma_curso_id` aos registros `NULL` de turmas com oferta única ativa, com dry-run.
- **Arquivos:** `scripts/` (novo).
- **Ensaio:** contagens antes/depois no scratch; comparar números.
- **Risco:** alto. **Muda número visível** (legado passa a contar na oferta).
- **Migration:** não (script de dados). **Depende de D2.**

### D3b-2.6 — BI `f_prog` por `TurmaCurso.programa`
- **Escopo:** migrar `calcular_frequencias_relatorio.f_prog` de `Turma.programa` para `TurmaCurso.programa`.
- **Arquivos:** `app/utils/logica.py`.
- **Testes de caracterização antes:** `tests/test_bi_oferta.py` (relatório geral).
- **Ensaio:** números antigo × novo.
- **Risco:** médio. **Muda número visível** (frequência por programa).
- **Migration:** não. **Depende de D6.**

### D3b-2.7 — N+1 do histórico do aluno
- **Escopo:** buscar `Frequencia` em lote por `aluno_id` e agrupar por `turma_curso_id`.
- **Arquivos:** `app/registros/alunos.py`.
- **Testes de caracterização antes:** `tests/test_d5_leitores.py`.
- **Risco:** baixo. **Não muda número visível.**
- **Migration:** não. **Depende de D5.**

### Ordem recomendada

1. D3b-2.2 (N+1 freq_geral) — baixo risco, sem mudança de número.
2. D3b-2.7 (N+1 histórico) — baixo risco.
3. D3b-2.3 (estats por oferta) — depende de D4.
4. D3b-2.4 (limpeza por oferta) — depende de D3.
5. D3b-2.6 (BI programa por oferta) — depende de D6.
6. D3b-2.5 (backfill legado) — depende de D2, por último, com ensaio.

### O que muda número visível para o usuário

| Etapa | Muda número? | Onde |
|---|---|---|
| D3b-2.2 | Não | — |
| D3b-2.3 | Sim | Estatísticas da pauta (presença/falta/J) por oferta |
| D3b-2.4 | Não (comportamento) | Limpeza de lançamentos |
| D3b-2.5 | Sim (se executado) | Frequência por oferta (legado passa a contar) |
| D3b-2.6 | Sim | Frequência por programa (BI/relatório) |
| D3b-2.7 | Não | — |

---

## Resumo

Mapeamento completo dos pontos de frequência/diário por oferta. 1 turma com 3 ofertas no scratch/principal, 0 lançamentos, 0 duplicatas. As principais dívidas: estatísticas do GET `/frequencia` agregam ofertas, limpeza destrutiva por `turma_id`, N+1 de `freq_geral`/histórico, BI por programa lê `Turma.programa`. Decisões D1–D6 propostas com recomendações; implementação fica para as etapas D3b-2.1…2.7.

