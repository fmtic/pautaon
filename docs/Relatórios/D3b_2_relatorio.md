# ETAPA D3b.2 — Serviço único de frequência por oferta

**Status:** concluída. Suíte completa verde (`372 passed, 0 falhas`), acima da meta
de 359. Nenhum commit feito.

Fontes: `docs/D3b_0_desenho.md` (Passo 1.1-1.4, Passo 2.3-2.6, D3b.2).

---

## 1. Leitura (consumidores mapeados antes de alterar)

Regra canônica fixada pelo responsável:
`percentual = presentes/(presentes+faltas)`, **J fora do denominador**, 1 casa
decimal; faixas `hi >= LIMIAR_ATENCAO (90)`, `mid >= LIMIAR_CRITICO (75)`, `lo`
abaixo, **comparando o valor já arredondado a 1 casa**; frequência **por oferta**
só recebe as linhas legadas (`turma_curso_id IS NULL`) quando a oferta é a
**única ativa** da turma (regra D2); frequência **por turma** soma **todas** as
linhas (ofertas + legado), como hoje.

| Arquivo : linha | O que reimplementa | Destino |
|---|---|---|
| `app/models/academico.py:142-183` (`Turma.freq_geral`, `Turma.freq_geral_oferta`) | loop sobre `Frequencia` com `CONCEITOS_PRESENCA`/`CONCEITOS_CONTABEIS` | **migrado** (delega ao serviço) |
| `app/relatorios/painel_pedagogico/frequencia.py` (`agregar_por_turma`, `FrequenciaTurma`, `semanal`) | agregado por turma em 1 consulta + quebra semanal | **migrado** (vira adaptador fino; `semanal` preservado) |
| `app/relatorios/painel_pedagogico/helpers.py` (`faixa`, `pct`) | limiar hardcoded e contagem presença/falta | **migrado** (delegam ao serviço; limiares via `regras`) |
| `app/relatorios/painel_pedagogico/turma.py` | consome `agregar_por_turma`, literais `75`/`90` | **migrado** (usa `LIMIAR_CRITICO`, escopo de unidade) |
| `app/relatorios/painel_pedagogico/periodo.py` | consome `agregar_por_turma`, literal `75` | **migrado** (usa `LIMIAR_CRITICO`, escopo de unidade) |
| `app/relatorios/painel_pedagogico/ficha_aluno.py` (`_frequencia`, `pct_turma = serie_turma[-1]`, `< 90`) | último ponto da série semanal como "frequência da turma"; limiares hardcoded | **migrado** (acumulado da oferta; limiares via `regras`) |
| `app/registros/core.py:~L373-394` (estatísticas por aluno da tela de lançamento) | loop de contagem reimplementado, 1 consulta por aluno | **migrado** (lote em 2 consultas) |
| `app/registros/core.py:~L413-470` (`frequencia_relatorio`) | `int(turma_id)` sem validação (500) e duplicação de aluno com 2 ofertas | **migrado** (validação `type=int`, `.distinct()`) |
| `app/relatorios/bi_alunos.py:1107,1161,1240,2458` (4 reimplementações do loop) | contagem presença/falta própria, por turma/período | **fica para D3b.4** |
| `app/utils/logica.py:44-120` (`calcular_frequencias_relatorio`) | contagem com `counts[c.value]` sobre `CONCEITOS_PRESENCA` | **fica para D3b.4** |
| `app/relatorios/geral.py` | consome `logica.calcular_frequencias_relatorio` | **fica para D3b.4** |

Grep de `CONCEITOS_PRESENCA`/`CONCEITOS_CONTABEIS` em `app/`: além do serviço e
dos consumidores migrados, as reimplementações restantes estão concentradas em
`bi_alunos.py` (4 blocos) e `utils/logica.py` — exatamente os alvos da D3b.4,
intocados nesta etapa.

---

## 2. O serviço — `app/services/frequencia_oferta.py` (novo)

Fonte única de percentual, faixas e agregação. Sem N+1; sem alterar regras de
negócio além dos dois casos decididos.

- `percentual(presentes, faltas)` — regra única, `round(..., 1)`, `0.0` sem
  contável.
- `faixa(valor)` — importa `LIMIAR_ATENCAO`/`LIMIAR_CRITICO` de `regras.py`
  (**import lazy** para não fechar ciclo `services → relatorios → services`);
  compara `round(valor, 1)` contra os limiares (fecha a brecha do 89,96).
- `_count(c)` — `(presença, falta)` de um conceito; `J`/NULL/`Atraso`-não-contável
  → `(0,0)`.
- `ofertas_unicas_ativas(oferta_ids)` — 1 query (turma de cada oferta) + 1 query
  agregada `GROUP BY turma_id HAVING COUNT=1` sobre `TurmaCurso.ativo` (o mixin
  de soft-delete só expõe `ativo`, **não** `deleted_at`); `oferta_unica_com_legado`
  é o caso unitário.
- `agregar_por_oferta(oferta_ids, unidade_id=None, por_turma=None)` → `dict[int,
  OfertaFrequencia]` — **UMA** consulta `GROUP BY turma_id, turma_curso_id,
  aluno_id, conceito` com `COUNT`; filtro `OR(turma_curso_id IN ids,
  AND(turma_curso_id IS NULL, turma_id IN turmas_unicas))`; bucketing em Python
  atribui o legado à oferta única da sua turma (regra D2); oferta sem linha →
  agregado zerado (`pct=0.0`). Retorna dataclasses `OfertaFrequencia` /
  `AlunoOfertaFrequencia` (acesso por atributo e por chave).
- `agregar_por_turma(turmas_ids, unidade_id=None)` → `dict[int, TurmaFrequencia]`
  — **UMA** consulta bruta ordenada por `(turma, aluno, data)`, preserva a lista
  `(data, conceito)` por aluno (inclusive o `J`) para as séries/sequências do
  painel; turmas sem linha **não** entram no dict (mesmo comportamento anterior).
- `TurmaFrequencia` é a estrutura que substitui a antiga `FrequenciaTurma`.

---

## 3. Consumidores migrados

- **Modelo** — `Turma.freq_geral` delega `agregar_por_turma([self.id]).pct_turma`;
  `Turma.freq_geral_oferta(turma_curso_id)` delega
  `agregar_por_oferta([turma_curso_id], por_turma=self.id)`, com guarda
  `info.turma_id != self.id → 0.0`. Assinaturas e retornos idênticos; `try/except`
  → `0.0` preservado.
- **Painel** — `frequencia.py` vira adaptador fino (`FrequenciaTurma =
  TurmaFrequencia`, `agregar_por_turma` delega ao serviço, `semanal` intacto);
  `helpers.faixa`/`helpers.pct` delegam ao serviço; `turma.py` e `periodo.py`
  passam `unidade_id` ao agregador e usam `LIMIAR_CRITICO` no lugar do `75`.
- **Ficha 360** (`ficha_aluno.py`) — `pct_turma` agora é o **acumulado da
  oferta** (`agregar_por_oferta`/`agregar_por_turma`), não `serie_turma[-1]`;
  limiar `< 90` vira `< LIMIAR_ATENCAO`; nenhum literal `75`/`90` permanece.
- **Lançamento/relatório** (`registros/core.py`) — estatísticas por aluno da
  tela de lançamento em **lote** (1 query `Frequencia GROUP BY aluno, conceito`
  + 1 query `Inscricao`, sem N+1); `frequencia_relatorio` lê
  `request.args.get('turma', type=int)` (compara `turma.id == turma_id`, sem
  `int()` cru → sem 500 em valor inválido) e usa `select(Aluno).distinct()` para
  **não duplicar** o aluno inscrito em 2 ofertas.

**Não migrados (D3b.4):** `bi_alunos.py`, `relatorios/geral.py`,
`utils/logica.calcular_frequencias_relatorio`.

---

## 4. Números que mudaram (e por quê)

Somente os **dois casos decididos** divergem do código anterior; todo o resto é
refactor puro (caracterização confirmou igualdade antes da migração).

| Leitor | Antes | Depois | Motivo |
|---|---|---|---|
| `Turma.freq_geral_oferta` — Gema (turma com 1 oferta + legado NULL) | `50.0` | `75.0` | **Regra D2**: legado passa a entrar na oferta única ativa. Cenário `_base`: 3 pres / 4 contáveis (A,A,A,F). |
| Ficha 360 — "frequência da turma" (Ana na o1) | `0.0` (`serie_turma[-1]`: última semana sem aula) | `75.0` (acumulado da oferta) | **Caso decidido (2.4)**: pct da turma passa a ser o acumulado da oferta. |
| `faixa` — valores que arredondam para a fronteira (ex. 89,96 / 89,95) | fora/`mid` | `hi` | **Faixas sobre o valor arredondado**: `round(89.95,1)=90.0` em CPython; fecha a brecha. Não altera números agregados, só a classificação de faixa. |

`freq_geral` (por turma), `agregar_por_turma` do painel, visões por turma e por
período: **números inalterados** (fixados por caracterização e por testes da
parte 2).

---

## 5. Testes — `tests/test_frequencia_oferta.py` (novo, 13 testes)

**Parte 1 — caracterização (rodados verdes com o código ATUAL, antes do Passo 3):**
`_base` monta Unidade A + período; Alfa (2 ofertas, Ana/Beto/Caia), Gema (1
oferta + legado NULL), Zeta (sem frequência), Caia inscrita nas 2 ofertas de
Alfa, `J` no meio. Fixam `freq_geral`/`freq_geral_oferta`, `agregar_por_turma` e
as visões por turma/período.

**Parte 2 — adicionais:**
- `percentual`: `(3,0)=100`, `(0,2)=0`, `(0,0)=0`, `(1,2)=33.3`, `(2,1)=66.7`.
- `faixa` nas fronteiras: `74.9→lo`, `75.0→mid`, `89.94→mid`, `89.95→hi`,
  `89.96→hi`, `90.0→hi`, `74.96→mid` (arredondado).
- Legado só na oferta única (Gema `75.0`; Alfa permanece inalterada).
- Percentuais distintos por oferta (Caia `50.0` na o1, `0.0` na o2).
- `frequencia_relatorio` com `?turma=abc` → **200** (nunca 500); com Caia em 2
  ofertas → **uma linha por aluno** (sem duplicar).
- Ficha com `pct_turma` = acumulado da oferta quando a última semana não tem
  aula (`serie_turma[-1]==0.0`, `pct_turma==75.0`).
- Contagem de consultas via `before_cursor_execute`: `agregar_por_oferta` e a
  visão por período fazem **1 consulta de frequência**, sem N+1.

Nenhuma asserção foi reescrita senão pelos dois casos decididos; nenhum outro
número divergiu.

---

## 6. Decisões

- Import dos limiares (`LIMIAR_*`) feito **lazy** dentro de `faixa` para evitar
  ciclo de importação com o pacote `relatorios`.
- `TurmaCurso` não possui `deleted_at`; "oferta única ativa" usa `ativo`
  (SoftDeleteMixin).
- `agregar_por_turma` mantém o contrato do painel: turmas sem linhas ficam fora
  do dict (não zeradas), preservando os leitores atuais.
- Estruturas de retorno são dataclasses com `__getitem__`, permitindo leitura por
  atributo e por chave.

## 7. Pendências

- **D3b.4:** migrar `bi_alunos.py` (4 reimplementações do loop),
  `relatorios/geral.py` e `utils/logica.calcular_frequencias_relatorio` para o
  serviço único.
- Limpar avisos `LegacyAPIWarning` (`Query.get`) e `datetime.utcnow()` — fora do
  escopo desta etapa.

## 8. Resumo do pytest

```
372 passed, 85 warnings in 61.91s (0:01:01)
```

Escopos alterados (dentro do autorizado): `app/services/frequencia_oferta.py`
(novo), `app/models/academico.py` (só `freq_geral`/`freq_geral_oferta`),
`app/relatorios/painel_pedagogico/*.py`, `app/registros/core.py` (só as funções
do Passo 4) e `tests/`. Sem commit.
