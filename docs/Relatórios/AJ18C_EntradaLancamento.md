# AJ18-C — Escrita, denominadores e lançamento da frequência por data de entrada

**Branch:** `aj18-c-entrada-lancamento` (a partir de `nova_feature`, sem push)  
**Data:** 2026-11-10  
**Base:** `docs/Relatórios/AJ18A_EntradaNaOferta.md`, `docs/Relatórios/AJ18B_EntradaOferta.md`, serviço único `app/services/entrada_oferta.py`, `Inscricao.data_entrada_oferta` (`NULL` = desde o início)  
**Escopo:** backend (AJ18-C1) — (1) Escrita, (2) Denominadores por data / cobertura, (5) Testes automatizados, (6) Qualidade e correções pós-revisão (C1c). A interface do usuário (AJ18-C2) permanece pendente.

---

## 1. Decisões Arquiteturais Aplicadas (D4/D6)

- **D4 (Histórico e Denominadores):**
  - Linhas já registradas antes da data de entrada do aluno na oferta **não são alteradas nem removidas**.
  - Denominadores de pauta, pendências e cobertura de aulas passam a considerar apenas alunos **esperados por data** (`data_entrada_oferta IS NULL OR data_entrada_oferta <= data`).
  - Consultas e agregações sobre `Frequencia` não realizam `JOIN` com `Inscricao`: as inscrições ativas são consultadas em memória para resolver o conjunto de alunos esperados por data.
  - Re-enturmação gera nova inscrição ativa; histórico anterior permanece íntegro.
- **D6 (Interface de Lançamento):**
  - Escopo da etapa AJ18-C2 (não alterado nesta entrega).

---

## 2. Implementação no Backend (AJ18-C1)

### 2.1. Escrita — POST `/frequencia` e Defesa em Profundidade (`0ef7718`)
- **`app/registros/core.py`:**
  - No processamento do POST `/frequencia` (bloco `permitidos`), busca inscrições ativas da oferta.
  - Para cada campo `aluno_<id>` recebido, se a data de entrada da inscrição ativa for posterior à data da aula, o campo é ignorado (removido de `form_data`).
  - Emite `LogAcao` com rótulo `"Lançamento de frequência ignorado (entrada futura)"` e detalhes (`aluno_id`, `oferta_id`, `turma_id`, `data`, `conceito_recebido`, `entrada`), protegendo contra manipulação indevida de formulário.
- **`app/utils/logica.py` (`salvar_frequencia`):**
  - Defesa em profundidade: descarta do dicionário de conceitos alunos com entrada posterior à data de lançamento da oferta, sem levantar exceção.

### 2.2. Denominadores por Data, Pendências e Cobertura (`372e07e`)
- **`app/utils/frequencia.py`:**
  - `_pendencias_por_ofertas`: avalia para cada data esperada apenas os alunos cuja entrada seja anterior ou igual à data. Alunos de entrada futura não geram pendência. Data sem nenhum aluno esperado é tratada como pauta vazia.
  - `situacao_datas_oferta`: calcula `lancadas`, `total_ate_hoje`, `pendentes` e `proxima_pendente` considerando apenas os alunos esperados em cada data. `proxima_pendente` nunca seleciona data que só aguarda alunos de entrada futura.
- **`app/services/estatisticas_professor.py`:**
  - `cobertura_pauta`: `aulas_esperadas`, `aulas_lancadas`, `aulas_pendentes` e `taxa_cumprimento_pauta` passam a respeitar o calendário da oferta e os alunos com entrada válida na data.

### 2.3. Correção Pós-Revisão C1c: Isolamento de `total_aulas_realizadas` e Drift de Logs
- **`app/services/estatisticas_professor.py`:**
  - O commit `372e07e` havia atribuído `resumo_geral["total_aulas_realizadas"] = aulas_lancadas_qtd`. Como `aulas_lancadas_qtd` depende da grade da oferta (`datas_aula_oferta`), ofertas sem grade ou aulas lançadas fora da grade resultavam em `total_aulas_realizadas == 0`, quebrando o cálculo original e o teste `test_obter_estatisticas_professor_calculos`.
  - **Correção:** restaurado o cálculo original de `total_aulas_realizadas` para `len(datas_ordenadas)` (contagem de datas distintas com frequência lançada). Apenas as métricas de `cobertura_pauta` dependem de calendário e de alunos esperados por data.
- **`tests/test_aj4_logs_drift.py`:**
  - Classificado o rótulo `"Lançamento de frequência ignorado (entrada futura)"` em `ROTULOS_SEM_LINHA` e `CATEGORIA_ESPERADA` como categoria `"outras"`.
  - Atualizada a contagem congelada de `ROTULOS_SEM_LINHA` de 9 para 10.
- **`tests/test_aj18c1_entrada_backend.py`:**
  - Adicionado teste de regressão `test_total_aulas_realizadas_sem_grade` comprovando que aula lançada em oferta sem grade continua contabilizando em `total_aulas_realizadas`.

---

## 3. Diff e Explicação dos Campos em `estatisticas_professor.py`

Comparativo em relação ao commit base `5b2aeaf` (AJ18-B):

```diff
--- a/app/services/estatisticas_professor.py
+++ b/app/services/estatisticas_professor.py
@@ -11,14 +11,11 @@ from __future__ import annotations
 
 from collections import defaultdict
 from datetime import date
-from typing import Any, Dict, List, Optional
+from typing import Any, Dict, Optional
 
-from sqlalchemy import func
-
-from app.database import db
-from app.models import Aluno, Curso, Frequencia, RegistroAula, TemaAula, Turma, TurmaCurso
-from app.models.enums import CONCEITOS_PRESENCA, ConceitoFrequencia
-from app.services.turma_curso import _alunos_da_oferta, datas_esperadas_oferta, ofertas_ativas
+from app.models import Aluno, Frequencia, Inscricao, RegistroAula, TemaAula, Turma, TurmaCurso
+from app.services.entrada_oferta import aula_conta_para_aluno
+from app.services.turma_curso import _alunos_da_oferta, datas_aula_oferta
 from app.utils.frequencia import alunos_ativos_da_turma, datas_bloqueadas_str
 from app.utils.logica import formatar_nome_proprio, gerar_datas
 from app.utils.timezone import get_local_now
@@ -303,18 +300,56 @@ def obter_estatisticas_professor(
     alunos_processados.sort(key=lambda x: (not x["alerta_duplo"], x["faixa_freq"] != "lo", x["nome"]))
 
     # 8. Relação Professor x Aluno x Pauta (Cobertura curricular e dias esperados)
+    # AJ18-C (item 2): denominadores por data respeitam a entrada do aluno na
+    # oferta (alunos esperados = pauta com entrada NULL ou <= data, regra única
+    # em app.services.entrada_oferta). Data sem aluno esperado mantém
+    # comportamento de pauta vazia (não entra como esperada/pendente).
     hoje = get_local_now().date()
     blocked = datas_bloqueadas_str(turma_alvo.periodo_letivo_id)
     if oferta_alvo is not None:
-        datas_esperadas = datas_esperadas_oferta(oferta_alvo, hoje, blocked)
+        datas_calendario = datas_aula_oferta(oferta_alvo, limite=hoje, blocked=blocked)
         curso_id = oferta_alvo.curso_id
+        inscricoes_pauta = Inscricao.query.filter(
+            Inscricao.turma_curso_id == oferta_alvo.id,
+            Inscricao.ativo.is_(True),
+            Inscricao.aluno_id.in_(aluno_ids_pauta or [-1]),
+        ).all() if aluno_ids_pauta else []
     else:
         datas_geradas = gerar_datas(turma_alvo, incluir_futuro=False, blocked_dates=blocked)
-        datas_esperadas = [d for d in (date.fromisoformat(str(di)) for di in datas_geradas if di) if d <= hoje]
+        datas_calendario = [
+            d for d in (date.fromisoformat(str(di)) for di in datas_geradas if di) if d <= hoje
+        ]
         curso_id = turma_alvo.curso_id
+        inscricoes_pauta = Inscricao.query.filter(
+            Inscricao.turma_id == turma_alvo.id,
+            Inscricao.ativo.is_(True),
+            Inscricao.aluno_id.in_(aluno_ids_pauta or [-1]),
+        ).all() if aluno_ids_pauta else []
+
+    inscr_por_aluno = {}
+    for insc in inscricoes_pauta:
+        inscr_por_aluno.setdefault(insc.aluno_id, insc)
+
+    lancados_por_data = defaultdict(set)
+    for reg in registros_freq:
+        if reg.data is not None and reg.aluno_id is not None:
+            lancados_por_data[reg.data].add(reg.aluno_id)
+
+    aulas_esperadas_qtd = 0
+    aulas_lancadas_qtd = 0
+    for d_cal in datas_calendario:
+        esperados = {
+            aid for aid in aluno_ids_pauta
+            if (insc := inscr_por_aluno.get(aid)) is not None
+            and aula_conta_para_aluno(insc, d_cal)
+        }
+        if not esperados:
+            # Data sem aluno esperado: comportamento de pauta vazia.
+            continue
+        aulas_esperadas_qtd += 1
+        if esperados.issubset(lancados_por_data.get(d_cal, set())):
+            aulas_lancadas_qtd += 1
 
-    aulas_esperadas_qtd = len(datas_esperadas)
-    aulas_lancadas_qtd = len(datas_ordenadas)
     pautas_em_dia_pct = round((aulas_lancadas_qtd / aulas_esperadas_qtd * 100), 1) if aulas_esperadas_qtd > 0 else 100.0
 
     # Temas do curso
@@ -344,7 +379,7 @@ def obter_estatisticas_professor(
 
     resumo_geral = {
         "total_alunos": len(alunos_processados),
-        "total_aulas_realizadas": aulas_lancadas_qtd,
+        "total_aulas_realizadas": len(datas_ordenadas),
         "frequencia_media_turma": taxa_presenca_turma,
         "iqr_nota": iqr_nota,
         "pct_alto_rendimento": round((qtd_alto_rend / len(alunos_processados) * 100), 1) if alunos_processados else 0.0,
```

### Detalhamento dos Campos
| Campo | Seção | Comportamento / Origem | Alterado no C1? |
|---|---|---|---|
| `total_aulas_realizadas` | `resumo_geral` | Contagem total de datas distintas com lançamentos (`len(datas_ordenadas)`). Independente da grade da oferta. | **NÃO** (restaurado) |
| `total_alunos` | `resumo_geral` | Total de alunos da pauta processados. | **NÃO** |
| `frequencia_media_turma` | `resumo_geral` | Taxa percentual de presenças sobre lançamentos válidos da turma. | **NÃO** |
| `iqr_nota` | `resumo_geral` | Média ponderada de rendimento escolar. | **NÃO** |
| `aulas_esperadas` | `cobertura_pauta` | Datas do calendário até hoje que possuem pelo menos 1 aluno esperado (respeitando data de entrada). | **SIM** |
| `aulas_lancadas` | `cobertura_pauta` | Datas esperadas em que todos os alunos elegíveis na data receberam lançamento. | **SIM** |
| `aulas_pendentes` | `cobertura_pauta` | `max(0, aulas_esperadas - aulas_lancadas)`. | **SIM** |
| `taxa_cumprimento_pauta` | `cobertura_pauta` | Percentual de cumprimento baseado em `aulas_lancadas / aulas_esperadas`. | **SIM** |

---

## 4. Testes Automatizados Executados

Bateria executada em ambiente SQLite isolado:

1. `tests/test_aj4_logs_drift.py` (2 testes anteriormente falhando + suíte completa do drift): **78 passed**.
2. `tests/test_dashboard_professor_pedagogico.py`: **3 passed** (incluindo `test_obter_estatisticas_professor_calculos`).
3. `tests/test_d3b2_4_estatisticas.py`: **5 passed**.
4. `tests/test_aj18c1_entrada_backend.py`: **9 passed** (incluindo novo teste `test_total_aulas_realizadas_sem_grade`).

Total executado: **78 testes passando**, sem falhas.

---

## 5. Qualidade de Código (Linting)

Executado:
```powershell
python -m ruff check app/services/estatisticas_professor.py tests/test_aj4_logs_drift.py tests/test_aj18c1_entrada_backend.py --select F821,F811,F841,F401
```
Resultado: **All checks passed!**

---

## 6. Histórico de Commits na Branch

- `0ef7718` — AJ18-C1a: escrita ignora aluno_* pós-entrada com LogAcao e defesa
- `372e07e` — AJ18-C1b: denominadores e cobertura respeitam data de entrada por data
- `9151ee5` — AJ18-C1: atualizar relatório (escrita/denominadores, qualidade, pendências)
- `4408b13` — AJ18-C1: relatório sem estado 'não implementado' (mudanças, testes, hashes)
- `cac696a` — AJ18-C1: add backend tests and update report
- `a6e71e4` — fix(aj18c1): classifica rotulo 'entrada futura' como outras no drift
- `10916cb` — fix(aj18c1): restaura total_aulas_realizadas independente de grade; adiciona teste de regressao

---

## 7. Próximos Passos (AJ18-C2)

- Ajustes no template `app/templates/frequencia/lancar.html` para exibir alunos pós-entrada como desabilitados nas datas anteriores com o rótulo `"Entrou em dd/mm"`.
- Adequações em `app/static/js/frequencia.js` para ignorar campos desabilitados na validação e no contador de conceitos obrigatórios.
