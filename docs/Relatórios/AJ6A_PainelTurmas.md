# AJ6-A — Painel Pedagógico: Contagens de Frequência e Diagnóstico de Acesso

## Resumo Executivo (Rodada 2)

- **Painel (`/relatorios/painel`)**: Responde 200 para todos os perfis autorizados (`admin`, `pedagogico`, `secretaria`, `gerencia`, `servico_social`), com e sem `periodo_letivo_id`.
- **Decisão fechada sobre Visualizar e roles de `/turma`**:
  - O retorno 403 de `assert_unidade_context` para admin sem unidade selecionada é **por desenho** (regra de isolamento multitenant). `assert_unidade_context` **não** foi modificado.
  - A lista de permissões de `/turma` foi mantida inalterada por especificação.
- **H3 Retratada (Filtro de unidade)**:
  - Verificação por `SELECT` nos dois bancos (`pautaon` e `pautaon_ensaio`) comprovou que **não existe nenhuma turma com `turma.unidade_id <> periodo_letivo.unidade_id`**.
  - O filtro `Turma.query.filter_by(unidade_id=...)` não tem efeito provado para a MGB (código morto / sem efeito em dados reais bem-comportados) e **foi removido** de `Turma.query` em `rota.py` e `periodo.py`.
- **Causa Real Provada da Divergência (Professor vs Painel)**:
  - Nos dados reais do `pautaon`, todas as 52 linhas de frequência da turma Informática têm `unidade_id IS NULL` (coluna opcional na tabela `frequencia`).
  - O painel pedagógico (funções `periodo_view.montar` e `turma_view.montar`) passava `unidade_id=get_unidade_id()` para `frequencia.agregar_por_turma(..., unidade_id=unidade_id)`, que executava `query.filter(Frequencia.unidade_id == unidade_id)`.
  - Como `Frequencia.unidade_id` é `NULL` para as 52 linhas, a query excluía todas as presenças/aulas para não-professores com unidade no contexto, zerando o painel (`0 alunos, 0.0%`).
  - A visão do professor (`obter_estatisticas_professor`) busca por `Frequencia.turma_curso_id == tc_id` sem filtrar `Frequencia.unidade_id`, exibindo os valores corretos (13 alunos, 42 presenças, 6 faltas, 4 justificadas, 87.5%).
  - Quando não se filtra a coluna opcional `Frequencia.unidade_id`, o painel pedagógico espelha **com 100% de precisão** todas as métricas do professor.
- **H8, H9 e H5 Testadas na Fixture Sintética e no Banco Real**:
  - **H8 (Duplicação por turma de 2 ofertas)**: Descartada. A turma Natação com 2 ofertas (uma de Natação e outra de Mecânica de Popa) não duplica contagens no painel nem no `agregar_por_turma`.
  - **H9 (Agregação por curso_id principal)**: Descartada. A agregação por turma soma as linhas da turma e a agregação por oferta respeita a oferta vinculada.
  - **H5 (Cálculo de dias esperados/pendências pela grade)**: Descartada para frequência contábil. A frequência bruta contabiliza unicamente registros lançados, sem dependência da grade de horário.

---

## 0. Estado da Branch e Validações

### Git Status (`git status --porcelain`)
```text
 M app/relatorios/painel_pedagogico/periodo.py
 M app/relatorios/painel_pedagogico/rota.py
 M tests/test_aj6a_painel_fumaca.py
?? tests/test_aj6a_causa_real.py
```

### Git Diff Stat (`git diff --stat`)
```text
 app/relatorios/painel_pedagogico/periodo.py | 4 +---
 app/relatorios/painel_pedagogico/rota.py    | 4 +---
 tests/test_aj6a_painel_fumaca.py            | 2 +-
 3 files changed, 3 insertions(+), 7 deletions(-)
```

---

## 1. Cross-check SQL nos Bancos Reais (Retratação de H3)

Executado nos dois bancos PostgreSQL (`pautaon` e `pautaon_ensaio`):

```sql
SELECT t.id, t.nome, t.unidade_id AS t_unid, pl.unidade_id AS pl_unid
FROM turma t
JOIN periodo_letivo pl ON pl.id = t.periodo_letivo_id
WHERE t.unidade_id <> pl.unidade_id;
```

**Resultados**:
- `pautaon`: 0 linhas retornadas.
- `pautaon_ensaio`: 0 linhas retornadas.

> **Conclusão sobre H3**: Nenhuma turma possui período letivo pertencente a outra unidade. Portanto, adicionar `filter_by(unidade_id=unidade_id)` na consulta de `Turma` não altera em nada os resultados da MGB (código sem efeito provado / código morto). O filtro foi devidamente removido de `Turma.query` em `periodo.py` e `rota.py`.

---

## 2. Diagnóstico da Causa Real: Professor vs Painel

### Comparação Numérica Direta (MGB - Período 2026.2 - Informática / Oferta 14)

| Métrica | Visão do Professor (`obter_estatisticas_professor`) | Painel Pedagógico (`montar`) |
|---|:---:|:---:|
| **Total de Alunos** | **13** | **13** |
| **Total de Aulas Realizadas** | **4** | **4** |
| **Presenças** | **42** | **42** |
| **Faltas** | **6** | **6** |
| **Justificadas** | **4** | **4** |
| **Frequência Média (%)** | **87.5%** | **87.5%** |
| **Alunos em Risco Crítico (`lo`)** | **1** | **1** |
| **Alunos em Atenção (`mid`)** | **5** | **5** |
| **Alunos Ótimos (`hi`)** | **7** | **7** |

### Onde e como nascia o problema:
Na tabela `frequencia` do `pautaon`:
- As 52 linhas contêm `turma_id = 10`, `turma_curso_id = 14`, mas **`unidade_id = NULL`**.
- `Frequencia.unidade_id` é uma coluna opcional (`nullable=True`).
- Na visão do professor (`app/services/estatisticas_professor.py`), os filtros são aplicados em `turma_id` ou `turma_curso_id`, sem restringir `Frequencia.unidade_id`.
- No painel pedagógico, chamava-se `frequencia.agregar_por_turma(turmas_ids, unidade_id=unidade_id)`. Ao receber `unidade_id=2` (MGB), o serviço `app/services/frequencia_oferta.py` adicionava:
  ```python
  if unidade_id is not None:
      q = q.filter(Frequencia.unidade_id == unidade_id)
  ```
  Isso descartava todas as linhas com `unidade_id IS NULL`, retornando `0` alunos e `0.0%` de frequência no painel dos perfis não-professor com contexto de unidade.

---

## 3. Avaliação das Hipóteses

| Hipótese | Veredito | Evidência |
|---|---|---|
| **H1: Períodos homônimos "2026.2"** | **Impacto Neutro** | Existem períodos com nome "2026.2" em unidades 1 e 2, mas cada turma aponta estritamente para o `periodo_letivo_id` correto de sua unidade. |
| **H2: Frequência legado vs oferta** | **Descartada** | Não há linhas legadas (`turma_curso_id IS NULL`) na turma Informática do `pautaon` (todas 52 linhas têm oferta 14). |
| **H3: Filtro de unidade em Turma** | **Descartada / Retratada** | `turma.unidade_id == periodo_letivo.unidade_id` em 100% dos casos. O filtro em `Turma.query` não tem efeito. |
| **H5: Cálculo de pendências pela grade** | **Descartada** | A contagem de frequência é exclusivamente baseada nas linhas lançadas em `frequencia`. |
| **H8: Duplicação por 2 ofertas (Natação)** | **Descartada** | Natação tem 2 ofertas ativas, mas sem frequência lançada; o `agregar_por_turma` não gera duplicação de contagem de alunos ou aulas. |
| **H9: Agregação por curso principal** | **Descartada** | A agregação de frequência opera nas instâncias corretas e coincide perfeitamente com a visão da oferta. |

---

## 4. Testes e Validação

1. **`tests/test_aj6a_causa_real.py`** (16 testes):
   - Fixture sintética com a exata topologia do `pautaon` (Unidades 1 e 2, períodos "2026.2" homônimos, turma Informática com 13 alunos × 4 dias = 52 lançamentos, turma Natação com 2 ofertas e 0 lançamentos).
   - Validação de que H8, H9 e H5 não causam anomalias.
   - Matriz completa de perfis (`admin`, `pedagogico`, `secretaria`, `gerencia`, `servico_social`), validando HTTP 200 e consistência total de totais.
2. **`tests/test_aj6a_painel_fumaca.py`** (5 testes):
   - Validação de fumaça para todas as rotas do painel pedagógico (`/relatorios/painel`, com e sem período, `/relatorios/painel/busca`, `/turma`).
3. **Execução da Suíte**:
   - 21 testes executados e aprovados: `21 passed in 26.82s`.
   - `ruff check --select F821,F811,F841`: `All checks passed!`.
