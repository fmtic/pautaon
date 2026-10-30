# D3b-2.4 — Estatísticas do GET /frequencia por oferta

**Branch:** `nova_feature` · **HEAD Alembic:** `8d2e3f4a5b6c` · **Suíte:** 673 passed · **Data:** 27/10/2026

Etapa que **muda número visível** (apenas em turma com 2+ ofertas). Sem migration. Sem push.

---

## P1 — Leitura e TRAVA

- `frequencia()` em `app/registros/core.py`: o bloco de estatísticas calculava `Frequencia` filtrando apenas `turma_id` (todas as linhas, todas as ofertas) — **misturava ofertas** em turma com 2+.
- Oferta selecionada chega via `oferta_atual` (resolvida por `resolver_oferta_lancamento` / `turma_curso` do request). Com 2+ ofertas sem escolha, `exigir_escolha=True` e `ctx['alunos']=[]` (sem estatísticas).
- `frequencia_relatorio` (~L456) usa `calcular_estatisticas_frequencia` sobre conceitos já carregados (não o mesmo trecho inline) — **não alterado**.
- **TRAVA não acionou**: o código real coincidia com o comportamento-alvo esperado (estatística por turma, não por oferta). Implementação aplicada conforme decidido.

## P2/P4 — Caracterização e testes

Arquivo `tests/test_d3b2_4_estatisticas.py` (4 testes):
- `test_estats_oferta_a_nao_ve_b`: Caia vê só o1 → 50.0% (antes 33.3%).
- `test_estats_oferta_b_nao_ve_a`: Caia vê só o2 → 0.0% (antes 33.3%).
- `test_estats_oferta_unica_legado_inalterada`: Dan → 75.0% (inalterado).
- `test_n1_estats_constante`: ≤ 2 SELECTs em `frequencia`.

### Testes ajustados (P4)

| Teste (P2) | Antigo | Novo | Motivo |
|---|---|---|---|
| `test_caracterizacao_estats_misturadas_oferta_a` | `P: 33.3%` (misturado) | `P: 50.0%` (só o1) | comportamento-alvo: 2+ ofertas → só a oferta selecionada |
| `test_caracterizacao_estats_misturadas_oferta_b` | `P: 33.3%` (misturado) | `P: 0.0%` (só o2) | idem |

## P3 — Implementação

- Serviço: `conceitos_frequencia_por_aluno(aluno_ids, turma_id, oferta_id, somente_oferta)` em `app/services/frequencia_oferta.py` — UMA consulta; filtra por `turma_curso_id` quando `somente_oferta` (2+ ofertas) e por `turma_id` caso contrário (inclui legado).
- `core.py:frequencia()`: substituiu a query inline pelo serviço; `somente_oferta = (len(ofertas) >= 2 and oferta_atual is not None)`.

Fórmula §8.1 inalterada (J fora do denominador, 1 casa decimal).

## Tabela antigo × novo por cenário

| Cenário | Antes | Depois |
|---|---|---|
| Turma 2+ ofertas, oferta A selecionada | Caia 33.3% (A+F misturado) | Caia 50.0% (só A) |
| Turma 2+ ofertas, oferta B selecionada | Caia 33.3% (misturado) | Caia 0.0% (só F) |
| Turma oferta única + legado | Dan 75.0% | Dan 75.0% (inalterado) |
| Turma 0 ofertas (legado) | inalterado | inalterado |

## Desvios

- Nenhum. `frequencia_relatorio` não alterado (fora do escopo).

## Validação

- Suíte: 673 passed, 231 warnings.
- `ruff check --select F821,F811`: limpo.
- `git diff --check`: limpo.
- Sem push.
