# D3b-2.2 — Remoção de N+1 de freq_geral/freq_geral_oferta na listagem

**Branch:** `nova_feature` · **HEAD Alembic:** `8d2e3f4a5b6c` · **Suíte:** 665 passed · **Data:** 27/10/2026

Etapa de **performance**: nenhum número exibido ou resultado de filtro alterado. Sem migration. Sem push.

---

## P0 — Pré-requisitos

- `git status` limpo após remoção dos 3 tmp* (confirmados: 0 bytes, sem referência em código).
- Suíte verde: 662 passed (baseline).

## P1 — Leituras mapeadas

| Arquivo:linha | Função | Consultas por linha (antes) | Pode receber mapa? | Class. |
|---|---|---|---|---|
| `app/models/academico.py:151` | `Turma.freq_geral` (property) | 1 SELECT em `frequencia` (via `agregar_por_turma`) | Uso unitário (mantém) | (b) |
| `app/models/academico.py:170` | `Turma.freq_geral_oferta` | 1–2 SELECTs (oferta + legado) | Uso unitário (mantém) | (a) |
| `app/services/frequencia_oferta.py:312` | `agregar_por_turma` | 1 SELECT (todas as turmas) | Base do mapa turma | (b) |
| `app/services/frequencia_oferta.py:181` | `agregar_por_oferta` | 1–2 SELECTs | Base do mapa oferta | (a) |
| `app/registros/turmas.py:489` | `aplicar_filtros_turmas` | 0 (não usa freq) | — | — |
| `app/registros/turmas.py:614` | `pos_filtrar_turmas` | 1 SELECT por turma com `min_freq` (via property) | **Sim** — batch | (e) |
| `app/registros/turmas.py:686` | rota `turma()` | 1 SELECT por turma (template) + 1 por oferta na sub-linha | **Sim** — mapas | (e) |
| `app/templates/turmas/listar.html:308` | `turma.freq_geral` | (chamada por linha) | **Sim** — `freq_turma_map` | (b) |
| `app/templates/turmas/listar.html:422` | `turma.freq_geral_oferta(o.id)` | (chamada por oferta) | **Sim** — `freq_oferta_map` | (a) |

## P2/P4 — Caracterização e testes novos

Arquivo `tests/test_d3b2_2_n1_freq_geral.py` (3 testes):
- `test_equivalencia_mapa_batch_vs_property`: mapa em lote == property para todas as turmas/ofertas da semente.
- `test_batch_uma_consulta_por_mapa`: 1 SELECT por mapa, independente do número de ids.
- `test_listagem_rota_nao_faz_n_plus_1`: GET `/turma` faz ≤ 2 SELECTs em `frequencia`.

## P3 — Implementação

- Serviço: `freq_geral_turmas_em_lote` e `freq_geral_ofertas_em_lote` (reusam `agregar_por_turma`/`agregar_por_oferta`, UMA consulta por mapa).
- Rota `turma()`: monta `freq_turma_map` e `freq_oferta_map` uma vez por request; passa ao template.
- Template: `freq_turma_map.get(turma.id, 0.0)` e `freq_oferta_map.get(o.id, 0.0)`.
- `pos_filtrar_turmas`: agregados em lote para `min_freq` (com fallback à property para objetos sem `id`, mantendo compatibilidade com testes unitários).

Propriedades `Turma.freq_geral`/`freq_geral_oferta` mantidas para uso unitário (delegam ao mesmo cálculo).

## Consultas antes × depois (listagem de N turmas)

| Cenário | Antes | Depois |
|---|---|---|
| N turmas, coluna freq | N SELECTs (`freq_geral`) | 1 SELECT (`freq_turma_map`) |
| M ofertas na sub-linha | M SELECTs (`freq_geral_oferta`) | 1 SELECT (`freq_oferta_map`) |
| Filtro `min_freq` | 1 SELECT por turma | 1–2 SELECTs no total |

## Equivalência

Verificada por `test_equivalencia_mapa_batch_vs_property` (3 turmas, 4 ofertas, incluindo legado D2). Números idênticos.

## Remoção dos tmp

Os 3 arquivos (`tmpf1u8j29n`, `tmpg0wpq02k`, `tmpopmmqv3a`) foram removidos em D3b-2.1 (0 bytes, sem referência).

## Desvios

- `pos_filtrar_turmas` mantém fallback à property para objetos sem `id` (compatibilidade com `tests/test_filtros_turmas.py` que usa `SimpleNamespace`). Comportamento e números inalterados.
- Semântica de `min_freq` (oferta principal com 2+ ofertas) preservada.

## Validação

- Suíte: 665 passed, 225 warnings.
- `ruff check --select F821,F811`: limpo.
- `git diff --check`: limpo.
- Sem push.
