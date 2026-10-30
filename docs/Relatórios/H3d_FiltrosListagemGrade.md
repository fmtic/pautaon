# H3d — Filtros, listagem, detalhe e impressão leem a grade

**Data:** 26/10/2026 · **Branch:** `nova_feature` (sem push) · **Schema:** sem migration — head `5730d7c594ba`

---

## 1. Pré-requisitos (PASSO 0)

| Item | Resultado |
|---|---|
| `flask db heads` | `5730d7c594ba` (única) |
| Commits do H3c presentes | `6de7d05` (H3c-P4) e `071e2cc` (H3c-P6) |
| Suíte antes de editar | **537 passed** |
| Fontes usadas | `docs/Relatórios/` (H1–H3c), MER §7.32a/§8.10/§12.25, backlog |

---

## 2. Commits

| Hash | Passo | Mensagem |
|---|---|---|
| `435c885` | P2 | H3d-P2: caracterizacao dos filtros dia/horario, agregacao de dias e texto da listagem/detalhe/impressao |
| `2635502` | P3 | H3d-P3: servico da grade para listagem - grades em lote, GradeExibicao, dias por turma e condicao SQL dia/horario na mesma linha |
| `52ebf9d` | P4 | H3d-P4: listagem, detalhe e impressao leem a grade - filtros dia/horario na mesma linha, dias da turma pela uniao das ofertas, C.H. por aula com 'varia' e min_ch_aula global |
| `dd10b85` | P5 | H3d-P5: testes de filtro dia/horario pela grade, mesma linha, min_ch_aula global, texto por dia com 'varia' e ausencia de N+1 |
| `c43e43d` | P7 | H3d-P7: MER (7.32a, 8.10, 10, 12.25), backlog e script de ensaio dos filtros pela grade |
| _(este)_ | P9 | H3d-P9: relatorio final da H3d (filtros/listagem/impressao pela grade) |

---

## 3. Suíte e revisão Alembic

- **Suíte final:** **571 passed**, 1 deselected — 572 testes no total (537 do H3c + 35 novos: 21 em `test_filtros_turma_grade.py` e 14 em `test_impressao_grade_oferta.py`).
- **Head Alembic:** `5730d7c594ba` (nenhuma revisão nova; `flask db heads` conferido no início e ao final).
- **Ruff:** `--select F821` **limpo em `app tests scripts`**; `F811`/`F401` limpos nos arquivos tocados. O repositório tem **71 `F401` pré-existentes** (imports não usados fora do escopo do H3d) — não foram introduzidos nem "consertados" nesta etapa.

### Falha externa ao H3d (registrada, não corrigida)

`tests/test_maintenance.py::test_maintenance_blocks_non_admin_users` falha com `TemplateNotFound: sistema_indisponivel.html`. A causa está **fora do H3d**, no working tree não commitado:

- `app/templates/sistema_indisponivel.html` aparece como **deletado** e foi movido para `app/templates/erros/` (ainda não rastreado);
- `app/__init__.py` foi alterado (novo handler 403/404), mas `enforce_user_access_state` (~linha 101) continua renderizando `"sistema_indisponivel.html"` no caminho antigo.

Prova de que não é do H3d: `git ls-tree HEAD app/templates/` mostra o template presente em HEAD, e `git log -1 -- app/__init__.py` aponta para `a67dbf8` (anterior a esta etapa). Nada foi commitado desses arquivos por mim; eles seguem intactos no working tree.

---

## 4. Leitores de dias/horário do grupo — classificação (PASSO 1)

| Leitor | Classe | Ação |
|---|---|---|
| `turma()` → `carga_turma_map`, `carga_oferta_map`, `carga_horaria_total_map` | (a) herda do serviço (H3c) | mantido |
| `turma()` → `ofertas_map`, `principal_map` (`_ofertas_ativas_da_turma`/`_oferta_principal`) | (a) herda da relação carregada | mantido |
| `_resumo_ofertas` (`resumo.dias`/`dias_abreviados`) | **(b) split manual do CSV** | **migrado** para união das grades (`csv_para_weekdays` só no fallback) |
| `aplicar_filtros_turmas` (bloco `dia`/`horario_inicio`) | **(b) dois `EXISTS` independentes com `COALESCE(oferta→turma)`** | **migrado** para `filtro_por_dia_horario` (um `EXISTS` na grade) |
| `pos_filtrar_turmas` (`min_ch_aula`) | (b) usava só a principal | **migrado** para o menor valor entre todas as ofertas ativas |
| `listar.html` coluna de horário da turma (`principal.hora_inicio or turma.hora_inicio` / `turma.hora_*`) | **(b)** | **migrado** para `grade_oferta_map` |
| `listar.html` sub-linha (`o.dias_semana or turma.dias_semana`, `o.hora_inicio or turma.hora_inicio`) | **(b)** | **migrado** para `grade_oferta_map` (dias/horário/`"varia"`) |
| `detalhe.html` card (`oferta.dias_semana or turma.dias_semana`, `(oferta.hora_inicio or turma.hora_inicio)`) | **(b)** | **migrado** para `grade_oferta_map` |
| `detalhe.html` rótulo do `<select>` de enturmação (`o.hora_inicio`) | **(b)** | **migrado** (omite a hora quando não uniforme) — ver desvio 1 |
| `imprimir_listar_turma.html` (`oferta.hora_inicio or turma.hora_inicio`, `oferta.dias_semana`, C.H. por aula) | **(b)** | **migrado** para `grade_oferta_map` + `"varia"` |
| `turmas/ofertas.html` tabela da tela de edição (`oferta.dias_semana`, `oferta.hora_inicio`) | (b) | **adiado para o H4** — ver desvio 2 |
| `_tokens_centro_custo` (`split(",")`) | não é leitor de dia | intocado |

**(c) semântica diferente da decidida: nenhum leitor encontrado** — o passo não foi interrompido por esse critério.

### Semântica ATUAL do filtro de horário (documentada antes de migrar)

- **Dia:** `COALESCE(oferta.dias_semana, turma.dias_semana) ILIKE '%dia%'` dentro de um `EXISTS` sobre ofertas ativas, com fallback para `turma.dias_semana` apenas quando a turma não tem oferta ativa.
- **Horário:** **igualdade** com a **hora de INÍCIO** (`hora_inicio`), nunca faixa, sobre `COALESCE(oferta.hora_inicio, turma.hora_inicio)`; o fim do intervalo é ignorado pelo filtro.
- **Dia + horário:** eram **dois `EXISTS` independentes** — podiam casar em **ofertas diferentes** e, dentro da mesma oferta, em **linhas diferentes** (falso-positivo).

### Semântica DEPOIS

- Um único `EXISTS` em `turma_curso_horario` (oferta **ativa**) exigindo `dia_semana` **e** `hora_inicio` na **mesma linha**.
- **Fallback escalar** (comparador antigo) apenas para a turma **sem oferta ativa com grade** — turma sem oferta e oferta 100 % legado continuam funcionando; `logger.warning` quando o token de dia é desconhecido.
- Igualdade na hora de **início** preservada. O efeito é **apenas remoção** de falso-positivo, nunca adição.

---

## 5. Serviço (`app/services/turma_curso_horario.py`)

| Símbolo | Papel |
|---|---|
| `GradeExibicao` | dias (`dias_texto`), `uniforme`, par `hora_inicio`/`hora_fim` já formatado, `por_dia_texto`, `resumo`, `ch_aula_min`, `ch_aula_por_dia_texto`, `ch_aula_varia` |
| `grades_por_oferta(ofertas)` | linhas da grade por oferta reaproveitando `oferta.horarios` carregado; **uma** consulta em lote para as não carregadas |
| `grades_para_exibicao(ofertas, cargas=None, grades=None)` | monta o mapa de exibição em lote; `grades` evita reler |
| `dias_das_turmas_em_lote(turmas, grades=None)` | união dos dias das ofertas ativas por turma, com fallback CSV + `warning` |
| `condicao_grade(dia, hora)` | `EXISTS` em `turma_curso_horario` (oferta ativa), critérios na mesma linha |
| `filtro_por_dia_horario(dia, hora, cond_escalar)` | `OR(grade, AND(~tem_grade, escalar))` |
| `condicao_turma_com_grade()` | `EXISTS` de oferta ativa com **alguma** linha de grade |
| `CargaTurma.min_ch_aula` | menor valor entre **todas** as ofertas ativas (H3d) |

Formato: `_segmento_por_dia` → `"Terça 08:00–10:00"` (**en dash**, estilo do aviso do H3b), unidos por `"; "`; `_ch_por_dia_texto` → `"Ter 2h; Qui 2h"` (abreviação + `formatar_ch`) no `title` da célula.

---

## 6. Testes

### Novos

| Arquivo | Casos | Cobre |
|---|---|---|
| `tests/test_filtros_turma_grade.py` | 12 (P2) + 9 (P5) | caracterização de dia/horário/dia+horário em grades **uniformes**, oferta sem grade, turma sem oferta, token inválido, agregação de dias; depois: grade **não uniforme** (casa só no dia certo, hora de início de qualquer dia, `10:00`/`16:00` não casam), **dia+horário na mesma linha**, fallback escalar, `min_ch_aula` global e o filtro `min_ch_aula`, consultas de grade constantes ao crescer turmas |
| `tests/test_impressao_grade_oferta.py` | 7 (P2) + 7 (P5) | caracterização do **texto exato** da linha, sub-linha, detalhe e impressão (uniforme); depois: texto **por dia** na linha/detalhe/impressão, `"varia"` com `title` por dia na sub-linha multi e na impressão, uniforme **sem** `"varia"`, consultas de grade constantes na listagem e no detalhe |

### Alterados

**Nenhum teste existente foi alterado** nesta etapa. Os únicos ajustes foram **dentro dos arquivos novos**, durante a escrita do P5 (`min_ch_aula` é a duração de **uma aula** — 60/90 min nos cenários —, não a soma semanal; as asserções foram corrigidas para o valor real, sem mudar contrato de produção).

---

## 7. Ensaio no scratch Postgres (PASSO 6)

**Banco:** `pautaon_ensaio` · **head:** `5730d7c594ba` · **dados reais:** 3 turmas ativas, 5 ofertas ativas, 8 linhas de grade.
**Script:** `scripts/verificar_h3d_filtros.py` (somente leitura; saída também em `instance/backups/h3d_ensaio.txt`).

### 7.1 Combinações reais (dia, hora de início de uma linha da grade) — exigido 0 divergências

| Métrica | Resultado |
|---|---|
| Combinações reais testadas | **8** |
| Divergências antes × depois | **0** |

### 7.2 Varredura completa (6 dias × 8 horários candidatos = 48 combinações dia+horário)

| Tipo | Quantidade | Detalhe |
|---|---|---|
| **Remoções** (falso-positivo antigo, previstas) | **2** | turma 9 em `Segunda + 10:00` e `Terça + 10:00` — 10:00 é hora de início **somente na quarta** (oferta 13). Antes, o dia casava pela oferta 11/15 e a hora pela oferta 13 (ofertas diferentes). |
| **Adições** | **0** | nenhuma combinação passou a casar além do comparador antigo |
| Dias isolados e horários isolados | 0 divergências | conjuntos idênticos |

### 7.3 Agregação de dias por turma

| Turma | Nome | Antes (união do CSV) | Depois (união da grade) | Divergiu? |
|---|---|---|---|---|
| 9 | Mecânica de popa | Segunda, Terça, Quarta | Segunda, Terça, Quarta | não |
| 10 | Informática | Segunda, Quarta | Segunda, Quarta | não |
| 11 | Natação | Segunda, Terça | Segunda, Terça | não |

### 7.4 C.H. por aula / `min_ch_aula` (decisão do H3d)

| Turma | Ofertas ativas | Aula da turma | `min_ch_aula` | Ofertas |
|---|---|---|---|---|
| 9 | 3 | 180 min | **60 min** (antes: 180, da principal) | 11: 180 min · 12: 60 min · 13: 60 min |
| 10 | 1 | 180 min | 180 min (inalterado) | 14: 180 min |
| 11 | 1 | 120 min | 120 min (inalterado) | 15: 120 min |

### 7.5 Texto de exibição das 5 ofertas reais

Todas as ofertas reais têm grade **uniforme** — nenhuma delas exibe `por_dia_texto`, ou seja, as três telas mantêm **exatamente** o texto anterior:

| Oferta | Turma | Dias | Par | C.H. por aula |
|---|---|---|---|---|
| 11 | 9 | Segunda, Quarta | 08:00–11:00 | 180 min |
| 12 | 9 | Terça | 08:00–09:00 | 60 min |
| 13 | 9 | Quarta | 10:00–11:00 | 60 min |
| 14 | 10 | Segunda, Quarta | 14:00–17:00 | 180 min |
| 15 | 11 | Segunda, Terça | 13:00–15:00 | 120 min |

**Resultado do ensaio: todas as checagens passaram (exit 0).**

---

## 8. Mudanças de texto na tela

| Tela | Grade **uniforme** | Grade **não uniforme** |
|---|---|---|
| Listagem — linha (multi) | `08:00 - 11:00` + `principal` (igual) | `Terça 08:00–10:00; Quinta 14:00–16:00` |
| Listagem — linha (1 oferta) | `08:00 - 09:30` (igual) | por dia, no lugar do par que vinha da turma |
| Listagem — sub-linha | `Segunda, Quarta` + `08:00 - 11:00` (igual) | dias da grade + lista por dia |
| Listagem — C.H./Aula | `1h30min` (igual) | **`varia`** (lista por dia no `title`, ex.: `Ter 2h; Qui 2h`) |
| Detalhe — card | `Dias: Segunda, Quarta` / `Horários: 08:00 às 09:30` (igual) | `Horários: Terça 08:00–10:00; Quinta 14:00–16:00` |
| Detalhe — rótulo do select | `Curso — Turno 08:00` (igual) | omite a hora (antes repetia a projeção da Turma) |
| Impressão | `Segunda, Quarta 08:00–09:30 1h30min` (igual) | `Terça, Quinta Terça 08:00–10:00; Quinta 14:00–16:00 varia` |

Textos de dias na listagem continuam com o ponto da Etapa K (`Seg.`, `Ter.`, `Qua.`); o detalhe e a impressão continuam com nomes completos.

---

## 9. Desvios

1. **Rótulo do seletor de enturmação (`detalhe.html`) também migrado.** Não estava enumerado no PASSO 4; a mudança é de uma linha e elimina a hora projetada (que ficaria ausente/errada em grade não uniforme). Efeito visual nulo em grade uniforme.
2. **`turmas/ofertas.html` (tabela da tela de edição) não foi migrada.** É a tela de manutenção das ofertas, junto dos formulários/JS reservados ao **H4**; a instrução do PASSO 4 enumerava apenas listar/detalhe/impressão. Fica registrada como consumidor **(b) pendente** no MER §8.10.
3. **"Esperado 0 divergências" no P6** foi cumprido nas **combinações reais** (8/8). Na varredura completa aparecem **2 remoções** — exatamente o efeito pretendido pela regra "mesma linha" — e **zero adições**; por isso o ensaio **não** foi tratado como divergência que exigisse parada.
4. **`min_ch_aula`** é a duração de **uma aula** (minutos de um dia), não a soma semanal: nos cenários de teste os valores são 60/90 min. A decisão do H3d (mínimo entre todas as ofertas) foi aplicada sobre essa grandeza, mantendo o significado anterior do filtro.
5. **Falha do `test_maintenance`** — causa externa, descrita na seção 3; não corrigida para não tocar no diff alheio.

---

## 10. Perguntas abertas

1. Migrar a **tabela de `turmas/ofertas.html`** no H4, junto dos formulários, ou antecipar como correção pontual?
2. No rótulo do `<select>` de enturmação, quando a grade é **não uniforme**, omitir a hora (comportamento atual) ou exibir o resumo por dia?
3. Na **impressão**, colunas "Dias" e "Horários" repetem o nome do dia na grade não uniforme (`Terça, Quinta | Terça 08:00–10:00; …`). Manter (fiel à decisão de formato) ou compactar a coluna de horários para só os intervalos?
4. `ck_tch_dia` ainda admite 0–6 no banco (herdado do H1/H2) — apertar para 0–5 continua pendente (exigiria migration + limpeza de legado).
5. O N+1 **pré-existente** de `Turma.freq_geral_oferta` na sub-linha da listagem (dívida da Etapa K, registrada em §8.10) permanece fora do escopo do H3d.

---

## 11. O que NÃO mudou

- **Dashboard**, **ficha do aluno**, **conselho de classe** e **certificado** (ficam para o **H3e**).
- **Formulários e JS de edição** de oferta/turma, incluindo a tabela de `turmas/ofertas.html` (**H4**).
- **Schema**: nenhuma migration; `turma_curso.dias_semana/hora_inicio/hora_fim` continuam existindo como projeção (remoção no **H5**).
- Regras de **vigência**, **dias bloqueados**, **concomitância** (H3b) e **C.H. por ocorrência** (H3c) das telas já migradas.
- Semântica do filtro de horário: **igualdade na hora de início** (nunca faixa).
- `freq_geral_oferta` (N+1 conhecido da Etapa K) e os 71 `F401` pré-existentes do repositório.
