# D3b-2.6 — f_prog por TurmaCurso.programa + fechamento documental

**Branch:** `nova_feature` · **HEAD Alembic:** `8d2e3f4a5b6c` · **Suíte:** 681 passed · **Data:** 27/10/2026

Parte A muda número visível (só se `turma.programa` divergir do programa da oferta). Parte B é só documentação. Sem migration. Sem push.

---

## Parte A — código

### P1 — Leitura e TRAVA

- `calcular_frequencias_relatorio` (app/utils/logica.py ~L613): `f_prog` agrupava por `Turma.programa` (projeção).
- Consumidor: `app/relatorios/geral.py` (relatório geral e exportação Excel).
- TRAVA não acionou: o código real coincidia com o comportamento-alvo (agrupamento por `Turma.programa`). Implementação aplicada.

### Inventário de `Turma.programa` em app/ (NÃO alterados nesta etapa)

| Arquivo:linha | O que faz | Projeção legítima? |
|---|---|---|
| `app/conselho.py:218/409` | `select(Turma.programa).distinct()` para filtro de perguntas | Sim (filtro de UI) |
| `app/conselho.py:244/422` | `Turma.programa == programa_ativo` | Sim (filtro) |
| `app/registros/alunos.py:974-975` | exibição no histórico: oferta.programa or turma.programa | Sim (fallback) |
| `app/registros/core.py:143/155` | filtro de programa na pauta | Sim (filtro) |
| `app/registros/core.py:842` | `programas = sorted({t.programa for t in turmas})` | Sim (opções de filtro) |
| `app/registros/turmas.py:429/589/1704` | filtro/listagem por programa (projeção da oferta principal) | Sim (projeção) |
| `app/relatorios/conselho.py:217` | `"programa": oferta.programa or turma.programa` | Sim (fallback) |
| `app/relatorios/painel_pedagogico/periodo.py:181` | `"programa": turma.programa` | Sim (visão por turma) |
| `app/services/turma_curso.py:147/166/448/460/503/526` | filtros/sincronização/projeção da oferta principal | Sim (projeção) |

### P2/P4 — Caracterização e testes

Arquivo `tests/test_d3b2_6_fprog.py` (3 testes):
- `test_fprog_oferta_nao_principal_conta_no_seu_programa`: oferta não principal conta no SEU programa (ProgSecundario 0.0, ProgPrincipal 100.0).
- `test_fprog_programa_igual_inalterado`: quando `Turma.programa == oferta.programa`, inalterado.
- `test_n1_fprog_constante`: SELECTs em `frequencia` constantes.

### P3 — Implementação

- `calcular_frequencias_relatorio` (app/utils/logica.py): `f_prog` agrupa por `TurmaCurso.programa` nas linhas com oferta; legado via D2 (oferta única ativa recebe o legado; senão cai em `Turma.programa`, projeção). Fórmula §8.1 inalterada. Reusa `ofertas_unicas_ativas` de `services/frequencia_oferta.py`.

### Tabela antigo × novo

| Cenário | Antes | Depois |
|---|---|---|
| Turma com programas divergentes entre ofertas | não principal cai no programa da principal | não principal conta no SEU programa |
| Turma oferta única + legado NULL | legado no programa da turma | legado no programa da oferta (D2) |
| Turma sem oferta única ativa com legado | legado no programa da turma | legado no programa da turma (exceção) |
| Turma com programa igual à oferta | inalterado | inalterado |

## Parte B — documentação

- `app/models/MER.md` L1123 atualizado: lista "o que ainda lê/agrega por turma_id" reflete D3b-2.0–2.6 (resolvidos vs. pendentes).
- `backlog_desenvolvimento.md`: nova entrada "27/10/2026 (D3b-2.0–2.6)" + pendências abertas atualizadas (ALU-009/ALU-010 já aplicam `cond_inscricao_enturmada`; legado NULL sem backfill; fases 5–7; transferência; turma_lixeira; dívida de migrations; dump autêntico; teste manual no navegador; conftest único; Onda 3C; resíduos do conselho; painel por período e BI que ainda leem `Turma.programa`).

## Desvios

- Nenhum. `frequencia_por_curso` (BI) já agrupava por oferta (D3b-4a); `calcular_frequencias_relatorio.f_prog` alinhado agora.

## Validação

- Suíte: 681 passed, 241 warnings.
- `ruff check --select F821,F811`: limpo.
- `git diff --check`: limpo.
- Sem push.
