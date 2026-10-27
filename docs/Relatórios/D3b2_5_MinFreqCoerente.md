# D3b-2.5 — min_freq coerente com a frequência exibida (D7)

**Branch:** `nova_feature` · **HEAD Alembic:** `8d2e3f4a5b6c` · **Suíte:** 678 passed · **Data:** 27/10/2026

Etapa que **muda resultado de filtro** (só em turma com 2+ ofertas). Sem migration. Sem push.

---

## P1 — Leitura e TRAVA

- `pos_filtrar_turmas` (app/registros/turmas.py) era o único consumidor de `min_freq`.
- Consumidores da rota: `turma()` (L767) e `imprimir_centros_custo_turmas` (L999) — ambos chamam `pos_filtrar_turmas`, que agora compara a soma (turma). A sub-linha por oferta continua exibindo `freq_oferta_map` (inalterada).
- **TRAVA não acionou**: todos os consumidores compartilham o mesmo valor da coluna (soma) após a mudança. `imprimir_centros_custo_turmas` não monta mapa próprio, mas `pos_filtrar_turmas` calcula o batch internamente (1 consulta).
- Fallback para objetos sem `id` (SimpleNamespace dos testes unitários) mantido: usa `freq_geral` (soma).

## P2/P4 — Caracterização e testes

Arquivo `tests/test_d3b2_5_min_freq.py` (5 testes) + ajuste em `test_d3b2_2_listagem_caracterizacao.py`.

### Testes ajustados (P4)

| Teste | Antigo | Novo | Motivo |
|---|---|---|---|
| `test_min_freq_turma_multi_ofertas_compara_oferta_principal` | min_freq=70 mantém Alfa (principal 75≥70); min_freq=80 exclui | renomeado `test_min_freq_turma_multi_ofertas_compara_turma_soma`: min_freq=70 exclui (soma 50<70); min_freq=40 mantém | D7: filtro compara soma, não oferta principal |

### Novos testes

- `test_min_freq_multi_principal_acima_soma_abaixo_deixa_de_aparecer`: principal 75, soma 50, min_freq=60 → exclui (antes incluía).
- `test_min_freq_multi_soma_acima_principal_abaixo_passa_a_aparecer`: coerência coluna==filtro.
- `test_min_freq_zero_ofertas_inalterado`: Zeta (0 lançamentos) inalterado.
- `test_min_freq_uma_oferta_inalterado`: Gema (1 oferta) inalterado.
- `test_n1_min_freq_constante`: ≤ 1 SELECT em `frequencia`.

## P3 — Implementação

- `pos_filtrar_turmas`: `min_freq` agora compara `_agg_turma_freq` (soma da turma), não a oferta principal. Precompute simplificado (apenas agregado turma).
- Sub-linha por oferta (`freq_oferta_map`) inalterada.

## Tabela antigo × novo por cenário

| Cenário | Antes (filtro) | Depois (filtro) |
|---|---|---|
| Alfa (principal 75, soma 50), min_freq=70 | mantém (principal 75≥70) | exclui (soma 50<70) |
| Alfa, min_freq=40 | mantém | mantém (soma 50≥40) |
| Gema (1 oferta, 75), min_freq=70 | mantém | mantém (inalterado) |
| Zeta (0 lançamentos, 0), min_freq=0 | mantém | mantém (inalterado) |

## Desvios

- Nenhum. Comportamento da coluna (soma) e do filtro agora coincidem (D7).

## Validação

- Suíte: 678 passed, 238 warnings.
- `ruff check --select F821,F811`: limpo.
- `git diff --check`: limpo.
- Sem push.
