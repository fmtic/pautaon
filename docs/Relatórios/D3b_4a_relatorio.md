# ETAPA D3b.4a — BI e relatório geral POR OFERTA

Data: 26/10/2026. Fontes: `docs/D3b_0_desenho.md` (Passos 1.1, 1.3, 1.5, 2.3, D3b.4),
`docs/D3b_2_relatorio.md`, `docs/D3b_3_relatorio.md`.
Fora do escopo (intocados): painel pedagógico (D3b.4b), filtro/coorte por turno
(D3b.7), `transferencias_por_curso` (D3b.8) e a tela do BI (templates e JS).

Arquivos alterados nesta etapa (único escopo autorizado):
`app/relatorios/bi_filtros.py`, `app/relatorios/bi_alunos.py`,
`app/relatorios/bi_routes.py`, `app/relatorios/catalogo.py`,
`app/relatorios/indicadores.md`, `app/utils/logica.py`
(apenas `calcular_frequencias_relatorio`), `tests/test_bi_oferta.py`.
`app/relatorios/geral.py` foi lido e **não precisou mudar** (apenas consome o
dict devolvido por `calcular_frequencias_relatorio`). Serviços
`frequencia_oferta.py` e `enturmado.py` não foram alterados.

---

## Passo 1 — Leitura e classificação (linhagens do momento da leitura, antes das alterações)

### (a) `app/relatorios/bi_filtros.py` (140 linhas pré-migração)

- `aplicar_filtros_aluno` (~L20-90): com qualquer filtro acadêmico fazia
  `join(Inscricao).join(Turma)` e resolvia **todos** os filtros por `Turma`
  (`Turma.periodo_letivo_id`, `Turma.id`, `Turma.curso_id`,
  `Turma.professor_id`); `cond_linhas` para frequência/aulas não existia.
- `aplicar_filtros_inscricao` (~L93-140): join `Inscricao → Turma`; curso e
  professor filtrados por `Turma.curso_id` / `Turma.professor_id`.
- Reexportava `cond_oferta_efetiva` / `cond_inscricao_enturmada` (D3b.3).

### (b) `app/relatorios/bi_alunos.py` — classificação de cada indicador

Regiões lidas: imports ~L1-120; INS-008 ~L769-862; FRE-001..005 ~L862-1100;
faixas/FRE-009/FRE-010 ~L1100-1450; demais funções (ALU/CRU/AUL/ATD/SOC) ao
longo do arquivo (2.793 linhas pré-migração).

| Indicador | Uso prévio | Classificação |
|---|---|---|
| FRE-001..005 (`total_lancamentos_frequencia`, `total_presencas`, `total_faltas`, `total_faltas_justificadas`, `frequencia_media`) | filtros de curso/prof por `Turma.curso_id/professor_id`; média somando linhas | **MIGRAR** — curso/prof pela oferta da linha (`Frequencia.turma_curso_id`), legado pela regra D2 |
| FRE-006/007/008 (faixas ≥90 / 75-89 / <75) | laço linha a linha acumulando por aluno; comparação sem arredondamento (89,9521 ficava FORA de todas as faixas) | **MIGRAR** — percentual/faixa pelo serviço `frequencia_oferta`; três faixas viram UMA função auxiliar parametrizada (`_contagem_por_faixa("hi"/"mid"/"lo")`) |
| FRE-009 `frequencia_por_turma` | iterava turma a turma (N+1), 1 consulta por turma | **MIGRAR** — percentual continua POR TURMA (decisão 3) mas via `agregar_por_turma` em lote; seleção de turmas pela oferta |
| FRE-010 `frequencia_por_curso` | carregava todas as linhas e agrupava por `Turma.curso_id` | **MIGRAR** — somente linhas de oferta + legado D2, agregado via `agregar_por_oferta` em lote |
| ALU-002/003/005/006/007 (`alunos_ativos`, `alunos_inativos`, `alunos_sexo`, `alunos_por_faixa_etaria`, `alunos_pcd`) | base cadastral/demográfica do aluno; filtros curso/prof transitivos em `aplicar_filtros_aluno` (pela turma) | **MIGRAR apenas os filtros** (pela oferta da inscrição); bases **MANTER** |
| ALU-008 `alunos_por_unidade` | catalogado como **"Alunos cadastrados por unidade"** (cadastral) | **MANTER a base** (decisão 6 — a descrição do catálogo é cadastral, não aplica `cond_aluno_enturmado`); **filtros MIGRADOS** |
| ALU-009 `alunos_por_curso` / ALU-010 `alunos_por_turma` | agrupavam por `Turma.curso_id` / vínculo turma | **MIGRAR** — curso pela oferta (`Inscricao.turma_curso_id` → `TurmaCurso`); ALU-009 distinto POR CURSO (decisão 2); ALU-010 1× por turma |
| INS-001/002/008 (`total_inscricoes`, `inscricoes_ativas`, `inscricoes_por_curso`) | join `Inscricao→Turma`; curso por `Turma.curso_id` | **MIGRAR** — join por `Inscricao.turma_curso_id` (NOT NULL, sem fallback) |
| AUL-001/002/003/007/008 (totais/turma/período/instrutor/tema) | `Turma.curso_id/professor_id` para filtros; **AUL-001 juntava `Turma` duas vezes** | **MIGRAR** filtros via `RegistroAula.turma_curso_id` (+D2 no legado); AUL-003 por período **MANTER** (período pertence à Turma) |
| AUL-004 `aulas_por_professor` / AUL-005 `aulas_por_curso` | agrupavam por `Turma.professor_id` / `Turma.curso_id` | **MIGRAR** — professor/curso **da oferta do registro** (`TurmaCurso.professor_id/curso_id`), legado pela D2 (decisão 1/3) |
| AUL-006 `aulas_por_unidade` | filtrava `RegistroAula.periodo_id` e `RegistroAula.professor_id` — **atributos que não existem no modelo** | **MIGRAR/BUGFIX** — período via `Turma`, professor via oferta |
| ATD-001 `total_atendimentos`, SOC-001/002, DIV-001 | base em `Atendimento`/`PerfilSocioeconomico`; filtros curso/prof transitivos em `aplicar_filtros_aluno` | **MIGRAR apenas os filtros**; bases **MANTER** |
| CRU-001 `frequencia_critica_por_vulnerabilidade` | média individual `< 75` sem arredondamento | **MIGRAR** — faixa lo do serviço + linhas por oferta |
| CRU-002/005 (conselho por raça/renda) | join `ConselhoClasse→Turma`; curso/prof por `Turma` | **MIGRAR** — `ConselhoClasse.turma_curso_id` (NOT NULL desde D5.5) → `TurmaCurso` |
| CRU-003 (sem internet por bairro/zona) | base `EnderecoAluno`; curso/prof transitivos pela turma | filtros **MIGRADOS** em lote com `aplicar_filtros_aluno`; base **MANTER** |
| turno em qualquer indicador | `Turma.turno` | **FORA** — coorte por turno é D3b.7; `programa` (dimensão do relatório geral) **MANTER** |
| CRU-004 `transferencias_por_curso` | — | **FORA** — D3b.8 |

### (c) `app/utils/logica.py` e `app/relatorios/geral.py`

- `calcular_frequencias_relatorio` (logica.py, ~L589-): média global por
  `Turma`; por programa via `Turma.programa` (**MANTER**); por turma iterando
  linha a linha (N+1); por professor via `Turma.professor_id` (ignorava a
  oferta e as turmas com `professor_id` NULL).
- Consumidor: `app/relatorios/geral.py` (relatório geral) usa as quatro
  estruturas devolvidas; **nenhum código do geral precisou mudar**.

### (d) `app/relatorios/bi_routes.py`

- `bi_api_dados` (dimensões unidade/sexo/faixa_etaria/curso/turma): só
  passava `unidade_id` (contexto).
- `bi_exportar_xlsx`: aceitava `unidade_id`, `periodo_letivo_id`, `turno`.
- `bi_indicador/<codigo>`: aceitava `unidade_id`, `periodo_letivo_id`,
  `turno`. **Nenhuma das três rotas aceitava `curso_id`/`turma_id`/
  `professor_id`** — adicionados nesta etapa.

### (e) `catalogo.py` e `relatorios/indicadores.md`

Fontes/descrições citavam `Turma` como resolvedor de curso/professor; as
faixas FRE-006/007/008 eram descritas sem arredondamento; ALU-008 é descrito
como "Alunos cadastrados por unidade" (→ decisão 6: base mantida). Todas as
entradas migradas foram atualizadas no Passo 4.

---

## Passo 2 — Caracterização antes de refatorar

`tests/test_bi_oferta.py` criado com cenário completo (2 cursos; Alfa com 2
ofertas de cursos/professores diferentes e Ana inscrita nas duas; Delta com
oferta única + frequência LEGADA da Fefa; registro legado em Alfa, turma com
2 ofertas; Zeta sem frequência; Gema em período encerrado com J; fronteiras
Beto 90,0 / Caia 89,96 / Davi 74,9 / Ana 75,0; unidade B com Bela/Ivon).
Os 7 testes de caracterização foram **verdes com o código ANTERIOR**
(7 passed) fixando `_ATUAL`, incluindo o defect de AUL-001 como
`pytest.raises(OperationalError)`.

---

## Passo 3 — O que foi migrado

**3a — `bi_filtros.py`:** criado `cond_linha_por_oferta(col_turma_curso_id,
col_turma_id, curso_id, professor_id)` — casa linhas próprias pela oferta
(`TurmaCurso.curso_id/professor_id`) e, para linhas legadas
(`turma_curso_id IS NULL`), a regra D2 (a turma tem exatamente 1 oferta ATIVA
e ela casa o filtro). `aplicar_filtros_aluno`/`aplicar_filtros_inscricao`
passaram a juntar `TurmaCurso` por `Inscricao.turma_curso_id` para
curso/professor; `periodo`/`turma` seguem por `Turma`; `programa` e `turno`
intocados.

**3b — `bi_alunos.py`:** novos helpers `_base_frequencia`,
`_base_registro_aula` (join único de `Turma` — corrige o defect de AUL-001),
`_totais_por_aluno` (GROUP BY aluno+conceito) e `_contagem_por_faixa(alvo)`
— as três faixas FRE-006/007/008 agora são UMA função auxiliar parametrizada
usando `percentual()`/`faixa()` do serviço; FRE-009 via `agregar_por_turma` e
FRE-010 via `agregar_por_oferta` (sem iterar turma a turma); ALU-009 junta o
Curso pela oferta da inscrição (distinto por aluno dentro de cada curso) e
ALU-010 conta distinto por turma; AUL-004/005 reescritas (2 consultas
agregadas — linhas próprias + legadas D2 — e merge, com 1 consulta de nomes);
AUL-006 corrigida; CRU-002/005 via `ConselhoClasse.turma_curso_id`; ALU-008
manteve a base cadastral (decisão 6).

**3c — `logica.calcular_frequencias_relatorio`:** média global e por programa
preservadas; por turma via `agregar_por_turma` (em lote); por professor
agrupando as OFERTAS por `TurmaCurso.professor_id` e somando
`presentes/faltas` com `agregar_por_oferta`. `geral.py` não mudou.

**3d — `bi_routes.py`:** `bi_api_dados`, `bi_exportar_xlsx` e `bi_indicador`
passaram a aceitar `curso_id`, `turma_id` e `professor_id` com `type=int`
(valor inválido vira `None` e o filtro simplesmente não é aplicado — nunca
500). Templates e JS do BI **não foram alterados**.

### Defects pré-existentes comprovados e corrigidos (relatados)

1. **AUL-001 `total_aulas_registradas`**: JOIN duplo de `Turma` →
   `ambiguous column name: turma.unidade_id` → `OperationalError` (= 500 na
   rota) com unidade + curso/professor/período. Corrigido no
   `_base_registro_aula` (um único join). A correção é necessária para o
   requisito "sem 500" das rotas.
2. **AUL-006 `aulas_por_unidade`**: filtrava `RegistroAula.periodo_id` e
   `RegistroAula.professor_id`, atributos que **não existem** no modelo.
   Corrigido (período via `Turma`; professor via oferta).

Nenhum serviço (`frequencia_oferta.py`, `enturmado.py`) foi alterado.

---

## Tabela antes → depois (todos os números que mudaram, com a causa)

Causas: **(D1)** curso/professor pela oferta; **(D3)** legado pela regra D2;
**(D4)** faixas sobre o valor arredondado (serviço); **(D2)** ALU-009 distinto
por curso; **(BUG1/BUG2)** defects corrigidos. Sem mudança nos totais de
unidade e turma (exigência da decisão 3): FRE-001..005 sem filtro, FRE-009
sem filtro, GERAL geral/programa/turma permanecem idênticos.

| Indicador | Filtro | Antes | Depois | Causa |
|---|---|---|---|---|
| FRE-001 | curso Natação | 407 | 405 | D1+D3: sai o Xadrez de Ana (4), entram os 2 legados de Fefa via oferta única |
| FRE-001 | curso Xadrez | 6 | 10 | D1: entram as 4 linhas de Ana-o2 |
| FRE-001 | prof Um | 413 | 409 | D1: turmas pela coluna ≠ ofertas; sai Alfa-per-turma, entra só o1 |
| FRE-001 | prof Dois | 0 | 6 | D1+D3: o2 (4) + legados de Delta (2, od é de Prof Dois) |
| FRE-002 | cn / cx / p1 / p2 | 337 / 4 / 341 / 0 | 335 / 7 / 338 / 4 | D1+D3 |
| FRE-003 | cn | 69 | 69 | coincide (mesmo valor por caminhos diferentes) |
| FRE-003 | cx / p1 / p2 | 2 / 71 / 0 | 3 / 70 / 2 | D1+D3 |
| FRE-005 | cn / cx / p2 | 83,0 / 66,7 / 0,0 | 82,9 / 70,0 / 66,7 | D1+D3 (composição das linhas mudou) |
| FRE-006 | unidade / cn | 1 / 1 | 2 / 2 | D4: Caia 89,9521 → 90,0 arredondado agora entra em hi |
| FRE-007 | cx | 0 | 1 | D1+D4: Ana-o2 (75,0) entra em Xadrez |
| FRE-008 | cn | 1 | 2 | D3+D4: Fefa (50,0 via od única) entra em Natação |
| FRE-009 | cn | {Alfa:83, Zeta:0} | {Alfa:83, Delta:50, Zeta:0} | D1: Delta tem oferta única de Natação (Turma.curso_id era NULL) |
| FRE-009 | prof Dois | {Zeta:0} | {Alfa:83, Delta:50} | D1: turmas selecionadas pelas ofertas do professor (Alfa via o2; Zeta é Prof Um na oferta) |
| FRE-010 | unidade | Nat 83,0 / Xad 66,7 | Nat 82,9 / Xad 70,0 | D1+D3: só linhas de oferta + legado D2 (Xadrez ganha Ana-o2) |
| FRE-010 | prof Um | Nat 83,0 | Nat 83,1 | idem (Alfa conta só o1: 334/402) |
| ALU-002 | cn / cx | 6 / 1 | 7 / 2 | D1: vínculo do aluno pela oferta da inscrição (Fefa entra em cn; Ana conta em cx) |
| ALU-005 | cn / cx | NI2,F2,M2 / {} | NI3,F2,M2 / {Fem:1} | D1 (transitivo) |
| ALU-006 | cn / cx | 6 / {} | 7 / {NI:1} | D1 (transitivo) |
| ALU-008 | cn / cx / p1 | 6 / 1 / 6 | 7 / 2 / 7 | D1 nos FILTROS; base cadastral MANTER (decisão 6) |
| ALU-009 | sem filtro | Futsal1, Nat6 | Futsal1, Nat7, Xad1 | D1+D2: Ana conta 1 em cada curso; Fefa entra em Natação |
| ALU-009 | p1 / p2 | Nat5 / Nat1 | Nat6 / Nat1,Xad1 | D1+D2 (Huga via oz; Ana via o2) |
| ALU-010 | cn / cx / p1 | {Alfa5,Zeta1} / {} / {Alfa5} | {Alfa5,Delta1,Zeta1} / {Alfa1} / {Alfa5,Zeta1} | D1; ALU-010 1× por turma (decisão 2) confirmado: Alfa segue 5 |
| INS-001 | cx / p2 | 1 / 1 | 2 / 2 | D1: inscrição de Ana-o2; Gui via og (Prof Dois na oferta) |
| INS-008 | Xadrez | 1 | 2 | D1: Ana-o2 + Gui |
| AUL-001 | cn / cx / p1 / p2 / período | **500 (OperationalError)** | 6 / 3 / 4 / 5 / 9 | BUG1 corrigido + D1+D3 |
| AUL-002 | cn | {Alfa:6} | {Alfa:3, Delta:3} | D1 (só o1 em Alfa) + D3 (legados de Delta via od) |
| AUL-004 | unidade / cn | {ProfUm:7} / {ProfUm:6} | {ProfUm:4, ProfDois:5} / {3,3} | D1: professor da OFERTA do registro; legados por D2 |
| AUL-005 | unidade / p1 / p2 | Nat6,Xad1 / Nat6,Xad1 / {} | Nat6,Xad3 / Nat3,Xad1 / Nat3,Xad2 | D1+D3 |
| ATD-001 | p2 | 0 | 1 | D1 transitivo (Fefa via od de Prof Dois) |
| SOC-001 | cx | 3000-6000:1 | 1500-3000:1, 3000-6000:1 | D1 (Ana entra em Xadrez pela oferta o2) |
| SOC-002 | cx | 0 | 1 | D1 (Ana beneficiária via o2) |
| CRU-001 | cn | {Sim:1, Não:0} | {Sim:2, Não:0} | D3+D4: Fefa (50,0 lo, vulnerável) via oferta única |
| CRU-002 | cx / p2 | {} / {} | {Branca:1} / {Branca:1, Preta:1} | D1: conselho joinedo por `ConselhoClasse.turma_curso_id` |
| CRU-005 | cx | todos 0 | 1500-3000: 1 | D1 (Ana aprovada na oferta o2) |
| GERAL_prof | — | {Prof Um:82,8} | {Prof Um:82,8, Prof Dois:66,7} | D1: professor do relatório geral vem da OFERTA; Delta (legado) passa a ter professor |

Nenhum outro número divergiu dos casos decididos (regravação completa em
`tests/test_bi_oferta.py::_ESPERADO`, coletada com o script de diagnóstico
pós-migração, apagado em seguida).

---

## Passo 4 — Catálogo e documentação

`catalogo.py`: `fonte` atualizada dos indicadores migrados (com
`TurmaCurso`/oferta) e novas `descricao` para ALU-009 (distinto por curso; a
soma pode exceder os distintos da unidade — decisão 2), ALU-010 (1× por
turma), FRE-006/007/008 (faixa sobre o valor arredondado; soma = total
contável), FRE-009/010 (por turma com turmas pela oferta; por curso só linhas
de oferta + D2) e AUL-004/005 (professor/curso da oferta, legado D2).
`indicadores.md`: mesmas informações nas seções ALU/INS/FRE/AUL/CRU.
ALU-008 permanece "Alunos cadastrados por unidade" (decisão 6).

## Passo 5 — Testes

`tests/test_bi_oferta.py` (14 testes, todos verdes):

- 7 testes de caracterização atualizados para `_ESPERADO` (pós-migração) —
  cada mudança listada na tabela acima; o bloco `pytest.raises(OperationalError)`
  de AUL-001 virou asserção dos números corrigidos.
- `test_limites_de_faixa_do_servico`: percentual/faixa com 89,96→90,0 (hi),
  90,0 (hi), 75,0 (mid), 74,9 (lo).
- `test_faixas_somam_contaveis_por_escopo`: hi+mid+lo == 6 na unidade,
  5 em Natação, 2 em Xadrez — exatamente os alunos com frequência contável.
- `test_aluno_em_duas_ofertas`: Ana conta 1× por curso (ALU-009) e 1× na
  turma (ALU-010 Alfa=5); filtro de curso devolve só a oferta pedida.
- `test_legado_regra_d2`: legado de Delta entra no curso da oferta única;
  a linha legada de Alfa (2 ofertas) não entra em nenhum curso
  (aulas: cn+cx = total − 1); em frequência cn+cx = total.
- `test_rotas_bi_aceitam_oferta_sem_500`: `/relatorios/bi/dados`,
  `/bi/indicador/<cod>` e `/bi/exportar/xlsx` com `curso_id`/`turma_id`/
  `professor_id` válidos, lixo (`abc`), negativos e inexistentes → apenas
  200/400/404, nunca 500; sanidade do filtro chegando ao indicador (405).
- `test_isolamento_unidade_b`: pedagógico da B vê só Ivon (4 lançamentos);
  pedir unidade A → 403; API de gráfico só devolve "Bela".
- `test_sem_n_plus_1_frequencia_agregada` (`before_cursor_execute`): o número
  de consultas de FRE-009/010 NÃO cresce ao adicionar turma+oferta com
  frequência (custo fixo em lote).

## Decisões aplicadas

1. curso/professor SEMPRE pela oferta (`TurmaCurso`), sem fallback para a
   turma (inscrição e conselho já exigem `turma_curso_id` NOT NULL).
2. ALU-009 = aluno distinto dentro de cada curso (soma pode exceder os
   distintos da unidade — documentado no catálogo); ALU-010 = 1× por turma.
3. Frequência por curso = só linhas de oferta; legado entra pela regra D2;
   totais de unidade/turma inalterados.
4. Percentual/faixa do serviço `frequencia_oferta.py` (faixa sobre o valor
   arredondado; as três faixas somam o total contável).
5. Predicado de enturmado de `enturmado.py` (usado por ALU-009/010 via
   `cond_inscricao_enturmada` reexportada).
6. ALU-008: o catálogo o descreve como **total cadastral** ("Alunos
   cadastrados por unidade") → base mantida; apenas os filtros migraram
   (relatado conforme autorização).

## Pendências

- Templates/JS do BI ainda não enviam `curso_id`/`turma_id`/`professor_id`
  (fora do escopo; as rotas já aceitam).
- `bi_api_dados` só repassa os novos filtros às funções que os aceitam
  (filtro por `inspect.signature` preservado); dimensões sem esses
  parâmetros seguem ignoring-os silenciosamente — comportamento existente.
- N+1 verificado nos indicadores de frequência agregados (FRE-009/010);
  outros indicadores não migrados nesta etapa podem manter padrões antigos.
- Validação em produção (PostgreSQL) não executada — os SQL gerados usam
  apenas `IN`, `GROUP BY`, `EXISTS` e `HAVING` padrão.
- CRU-004 (transferências por curso) e qualquer filtro por turno: D3b.7/D3b.8.

## Resumo da suíte

```
399 passed, 141 warnings in 128.21s (0:02:08)
```

(0 falhas; meta ≥382 atingida; `tests/test_bi_oferta.py`: 14 passed.)
