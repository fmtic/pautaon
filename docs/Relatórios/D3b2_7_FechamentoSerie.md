# D3b-2.7 — Fechamento da série D3b-2 (testes D2 no f_prog + conferência documental)

**Branch:** `nova_feature` · **HEAD Alembic:** `8d2e3f4a5b6c` · **Suíte:** 684 passed · **Data:** 27/10/2026

NÃO alterou lógica de app/. Só testes e documentação. Sem migration. Sem push.

---

## Parte A — testes D2 no f_prog

Arquivo `tests/test_d3b2_7_fprog_d2.py` (3 testes, todos passando):
1. `test_fprog_legado_oferta_unica_vai_ao_programa_da_oferta`: legado NULL em turma de oferta única conta no programa da OFERTA (D2) — `ProgOferta` 100.0, `ProgTurma` ausente.
2. `test_fprog_legado_sem_oferta_unica_cai_em_turma_programa`: legado em turma com 2+ ofertas cai em `Turma.programa` (exceção) — `ProgTurma` 100.0.
3. `test_fprog_turma_sem_lancamento_sem_divisao_por_zero`: turma sem lançamento → 0.0, sem divisão por zero.

Nenhum bug real detectado (os 3 passaram contra o código atual).

## Parte B — conferência documental (a–g)

| Item | Status | Ação |
|---|---|---|
| a) §7.20/§8.10: estatísticas do GET `/frequencia` por oferta (2+ ofertas ignoram legado NULL) + contrato de leitura da pauta | **corrigido** | Adicionados bullets em §8.10 (estatísticas, min_freq, funções em lote, f_prog). |
| b) min_freq compara o valor exibido (turma = soma) | **corrigido** | Bullet em §8.10 + §12.22 (D7). |
| c) funções em lote: `freq_geral_turmas_em_lote`, `freq_geral_ofertas_em_lote`, `frequencias_aluno_por_inscricao`, `conceitos_frequencia_por_aluno` (nomes/arquivo conferidos com grep) | **corrigido** | Listadas em §8.10 e §12.22. |
| d) f_prog por `TurmaCurso.programa` com regra D2 e exceção | **corrigido** | Bullet em §8.10 + relatório D3b-2.6. |
| e) §12.22 mantido como decisão D1 (turma = soma, sem drill-down); N+1 de freq_geral e do histórico removidos das dívidas; §12.23 atualizado | **corrigido** | §12.22 e §12.23 reescritos. |
| f) cabeçalho/Última atualização e contagem de testes do MER (684 passed) | **corrigido** | Suíte 662 → 684 no cabeçalho. |
| g) backlog: entrada 27/10/2026 (D3b-2.0–2.7) com etapas, suíte 662 → final, decisões D1–D7; Pendências abertas sem itens resolvidos | **corrigido** | Entrada adicionada/atualizada. |

## Desvios

- Nenhum bug real nos 3 testes D2.
- Documentação corrigida apenas onde ausente/errado (nenhum item "já estava correto" além do que já existia).

## Validação

- Suíte: 684 passed, 241 warnings.
- `ruff check --select F821,F811`: limpo.
- `git diff --check`: limpo.
- Sem push.
