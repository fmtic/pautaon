# D3b-2.3 — Remoção de N+1 de frequência no histórico do aluno

**Branch:** `nova_feature` · **HEAD Alembic:** `8d2e3f4a5b6c` · **Suíte:** 669 passed · **Data:** 27/10/2026

Etapa de **performance**: nenhum número ou texto do histórico alterado. Sem migration. Sem push.

---

## P0 — Fechar lacuna do D3b-2.2

Testes de caracterização criados em `tests/test_d3b2_2_listagem_caracterizacao.py`:
- `test_listagem_exibe_freq_geral_e_por_oferta`: smoke da renderização da listagem.
- `test_min_freq_turma_multi_ofertas_compara_oferta_principal`: `min_freq` numa turma com 2+ ofertas compara a oferta principal.

Commit: `67f479d`. Suíte verde (665 passed) antes de seguir.

## P1 — Leitura (sem editar)

- `app/registros/alunos.py:historico_aluno` consultava `Frequencia` **dentro do loop** de inscrições (N+1): uma consulta por inscrição, filtrando `aluno_id`, `turma_id`, `turma_curso_id`.
- Regra de pertencimento: linha de `Frequencia` pertence à inscrição quando `turma_id` e `turma_curso_id` coincidem. Inscrição legada (`oferta_id is None`) lê as linhas com `turma_curso_id IS NULL`. O histórico é por inscrição/oferta e **não** aplica a regra D2 (legado não migra para oferta em turma com 2+ ofertas) — preserva números.
- Ficha 360° (`imprimir_aluno`) e certificado (`periodo_letivo_relatorio_certificado`): **apenas listados, não alterados** nesta etapa. A ficha não consulta `Frequencia` (só conselho). O certificado não consulta `Frequencia`. Nenhum N+1 de frequência nesses dois.

## P2/P4 — Caracterização e testes novos

Arquivo `tests/test_d3b2_3_n1_historico.py` (2 testes):
- `test_equivalencia_batch_vs_antigo`: resultado em lote == cálculo antigo por inscrição (inclui conceitos A/B/C/D/F/J e legado NULL).
- `test_n1_historico_constante`: GET `/aluno/<id>/historico` faz ≤ 1 SELECT em `frequencia`, independente do número de inscrições.

## P3 — Implementação

- Serviço: `frequencias_aluno_por_inscricao(aluno_id, pares)` em `app/services/frequencia_oferta.py` — UMA consulta (`Frequencia.aluno_id == aluno_id`), agrupa por `(turma_id, turma_curso_id)`, calcula totais com `calcular_estatisticas_frequencia` (mesma fórmula).
- `historico_aluno` chama a função uma vez, antes do loop; dentro do loop usa `freq_stats_map.get(...)`.

Propriedades e conselho não alterados.

## Consultas antes × depois

| Cenário | Antes | Depois |
|---|---|---|
| Aluno com K inscrições | K SELECTs em `frequencia` | 1 SELECT |

## Equivalência

Verificada por `test_equivalencia_batch_vs_antigo` (inscrição com oferta + legado NULL, conceitos misturados). Números idênticos.

## O que foi só listado (não alterado)

- Ficha 360° (`app/registros/alunos.py:imprimir_aluno`): não consulta `Frequencia`.
- Certificado (`app/registros/periodos.py:periodo_letivo_relatorio_certificado`): não consulta `Frequencia`.

## Desvios

- Nenhum. Semântica (filtro exato por `turma_curso_id`) preservada.

## Validação

- Suíte: 669 passed, 227 warnings.
- `ruff check --select F821,F811`: limpo.
- `git diff --check`: limpo.
- Sem push.
