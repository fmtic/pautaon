# ETAPA B7 — `_montar_turma_linha` (visão por período) + varredura F821

**Problema:** `periodo.py` chamava `_montar_turma_linha(...)` desde `1c8604c`, mas
a função nunca existiu em nenhum commit → a visão por período do painel
pedagógico respondia `NameError`. Não havia teste cobrindo a rota.

**Resultado:** função implementada dentro do contrato do template, `ruff check
app --select F821` limpo, 3 testes novos e suíte com **352 passed**. Sem commit;
nenhum modelo, migration, rota de escrita, BI ou conselho alterado.

---

## 1. Leitura (passo 1)

### (a) `periodo.py` — o laço e a origem de cada argumento

`app/relatorios/painel_pedagogico/periodo.py`

| Elemento | Onde | O que é |
|---|---|---|
| `def montar(periodo, unidade_id)` | `:201` | orquestra a visão por período |
| turmas do período | `:202-207` | `Turma.query.filter_by(periodo_letivo_id=…, ativo=True).options(joinedload(Turma.professor)).order_by(Turma.nome)` — o `joinedload` foi adicionado nesta etapa |
| `turmas_ids` | `:208` | ids para as consultas agregadas |
| `semanas` | `:209` | `semanas_do_periodo(periodo)` → `list[date]` das segundas-feiras |
| `freq` | `:211` | `frequencia.agregar_por_turma(turmas_ids)` → `{turma_id: FrequenciaTurma}` (**1 consulta**) |
| `cons` | `:212` | `conselho.por_turma(turmas_ids)` → `{turma_id: bloco}` (formato D5.4) |
| laço | `:220-237` | `for t in turmas:` |
| `info` | `:221-223` | `freq.get(t.id)`; turma **sem nenhuma** linha de frequência é pulada (`if not info: continue`) |
| `cons_turma` | `:226` | `cons.get(t.id, {})` |
| chamada | `:237` | `turmas_dados.append(_montar_turma_linha(t, info, cons_turma, semanas))` |
| pós-laço | `:239-251` | `turmas_dados.sort(key=lambda d: d["pct_turma"])`, sinais (`_gerar_sinais_e_entradas`) e `cons_total/cons_ok` somando as linhas |
| saída | `:257` | `"turmas": turmas_dados` |

`turmas_dados` alimenta três consumidores: a ordenação/sinais dentro do próprio
`montar` (usa `pct_turma` e `nome`) e as duas tabelas do template (chaves
abaixo).

### (b) Template — TODAS as chaves lidas por linha

`app/templates/relatorios/painel_pedagogico.html` (visão por período em
`:124-339`; não há `include`/partial — as macros `kpi_card`, `barra_faixas` e
`lista_sinais` são inline em `:42-81` e nenhuma lê `vp.turmas`).

Tabela “Frequência por turma e semana” (`:273-334`):

| Chave | Linha |
|---|---|
| `t.nome` | 276 |
| `t.turno` | 277 |
| `t.alunos` | 277 |
| `t.semanais_celulas` (`c.valor_str`, `c.classe`) | 279-282 |
| `t.pct_turma_str` | 284 |

Tabela “Comparativo de turmas” (`:312-335`):

| Chave | Linha |
|---|---|
| `t.nome` | 315 |
| `t.programa` | 316 |
| `t.turno` | 316 |
| `t.professor` | 318 |
| `t.alunos` | 319 |
| `t.pct_turma_str` | 321 |
| `t.faixa_meta.classe` / `t.faixa_meta.label` | 322 |
| `t.em_risco` / `t.em_risco_pct_str` | 325 |
| `t.tendencia_classe` / `t.tendencia_str` | 327 |
| `t.conselho_percurso_ok` / `t.conselho_percurso_total` | 328 |
| `t.id` (link “Abrir”) | 330 |

Fora do laço, `vp.conselho_total_percurso`, `vp.conselho_ok_percurso` e
`vp.conselho_percurso_pct` (`:140-142`) vêm das somas de `montar` — logo a linha
precisa expor `conselho_percurso_total` e `conselho_percurso_ok` coerentes.

### (c) `turma.py` — nomes e regras reaproveitados

`app/relatorios/painel_pedagogico/turma.py`

- `montar` (`:30-143`) calcula `freq = frequencia.agregar_por_turma(...)`
  (`:67`), `faixas_alunos(freq.por_aluno_pct)` (`:73`), `semanal` (`:74`),
  `tendencia` (`:75`), `faixa`/`faixa_meta` (`:100-101`), `fmt_pct`/`fmt_diff`
  (`:114/122-123`), `classe_tendencia` (`:124/129`) e
  `celulas_semanais` (`:126`) — **as mesmas regras usadas na nova função**.
- `FrequenciaTurma` (`frequencia.py:17-23`): `por_aluno`, `por_aluno_pct`,
  `total`, `presentes`, `pct_turma`.
- `celulas_semanais` (`formatacao.py:48-65`) já entrega `valor_str`/`classe` —
  o template não calcula nada.

### (d) Histórico

- `git log --diff-filter=A -- app/relatorios/painel_pedagogico/periodo.py` →
  arquivo criado em **`1c8604c`**.
- `git grep -n "def _montar_turma_linha" $(git rev-list --all)` → **nenhum
  resultado** (a função nunca existiu em nenhum commit).
- `git grep -n "_montar_turma_linha"` em todas as revisões só acha a **chamada**
  (`:188` no arquivo da época; `44fbef8`, `b12b50d`, `e667c70`, …).
- `git show 1c8604c^` não tem `app/relatorios/painel_pedagogico/` (o pacote
  nasceu em `1c8604c`) → **não existe corpo inline anterior a ser migrado**.
  A função foi escrita apenas como chamada, num refactor incompleto.

### (e) Formato de `cons_turma`, `info` e `semanas`

- `conselho.por_turma` (`conselho.py:67-140`) devolve
  `{turma_id: {"inicial": {total, respondidos}, "percurso": {total, respondidos},
  "final": {total, respondidos}, "respostas": {...}, "perguntas": {...},
  "ofertas": [{turma_curso_id, rotulo, inicial, percurso, final, respostas, perguntas}]}}`.
  Os agregados **no nível da turma** continuam existindo na D5.4 (somam as
  ofertas) — é deles que a linha da visão por período tira `ok/total`.
- `info`: `FrequenciaTurma` (`frequencia.py:17-23`).
- `semanas`: `list[date]` das segundas-feiras do período (`helpers.py:13-21`).

### (f) Rota, querystring e perfis

`app/relatorios/painel_pedagogico/rota.py`

- Endpoint `relatorios.painel_pedagogico` → `@bp_relatorios.route("/painel")`
  (`:52-54`) ⇒ `/relatorios/painel`.
- Querystring: `turma_id` (`:59`) e `periodo_letivo_id` (`:60`); a turma vem
  depois por `_escolher_periodo` quando o id não é informado.
- `unidade_id = get_unidade_id()` (`:58`) — sessão; períodos e turmas são
  filtrados por ela (`:62-65`, `:80-84`).
- Perfis: `ROLES_RELATORIOS` = `admin, pedagogico, secretaria, gerencia`
  (`app/relatorios/shared.py:24`); qualquer outro perfil recebe 403.
- A visão por período só é montada quando **não** há turma válida
  (`:95-96`); o template escolhe `visao_periodo` antes de `visao_turma`
  (`painel_pedagogico.html:124`).

---

## 2. Função implementada

`app/relatorios/painel_pedagogico/periodo.py:155-198`

```python
def _montar_turma_linha(turma, info, cons_turma, semanas) -> dict:
    fx = faixas_alunos(info.por_aluno_pct)
    semanais = frequencia.semanal(info.por_aluno, semanas)
    tend = tendencia(semanais)
    f_t = faixa(info.pct_turma)
    perc = (cons_turma or {}).get("percurso", {})

    return {
        "id": turma.id,
        "nome": turma.nome,
        "programa": turma.programa or "—",
        "turno": turma.turno or "—",
        "professor": turma.professor.name if turma.professor else "—",
        "alunos": len(info.por_aluno),
        "pct_turma": info.pct_turma,
        "pct_turma_str": fmt_pct(info.pct_turma),
        "faixa_meta": faixa_meta(f_t),
        "em_risco": fx["lo"],
        "em_risco_pct_str": fmt_pct(pct(fx["lo"], fx["total"])),
        "tendencia_str": fmt_diff(tend),
        "tendencia_classe": classe_tendencia(tend),
        "semanais_celulas": celulas_semanais(semanais),
        "conselho_percurso_ok": perc.get("respondidos", 0),
        "conselho_percurso_total": perc.get("total", 0),
    }
```

- Só as chaves do passo 1(b) + `pct_turma`/`nome` (usadas pelo próprio
  `montar` na ordenação e nos sinais). Nenhuma chave inventada.
- **Zero consultas novas**: `info`, `cons_turma` e `semanas` chegam prontos;
  a única relação acessada (`turma.professor`) passou a vir por
  `joinedload(Turma.professor)` na query de `montar` (`:204`).
- Regras reaproveitadas de `helpers`/`formatacao`/`frequencia` — nenhum
  limiar, rótulo ou fórmula duplicada/alterada.
- Conselho: agregados de PERCURSO no nível da turma (`ok = respondidos`,
  `total = total`), somando as ofertas como na D5.4. A chave `"ofertas"` não é
  lida pelo template desta visão e por isso não é usada aqui.
- Também reordenei os imports de `periodo.py` (`ruff --fix`, I001), sem
  mudança semântica.

---

## 3. Varredura `ruff check app --select F821`

Antes: **1 ocorrência**, exatamente a que motivou a etapa.

| Arquivo:linha | Nome | Ação |
|---|---|---|
| `app/relatorios/painel_pedagogico/periodo.py:188` | `_montar_turma_linha` | **corrigido** (função implementada em `:155`) |

Depois: `ruff check app --select F821` → **`All checks passed!`** (nenhuma
ocorrência, dentro ou fora do pacote).

Achados **não-F821** que já existiam no pacote e ficaram intocados (fora do
escopo desta etapa, registrados para o futuro):

| Arquivo:linha | Regra |
|---|---|
| `formatacao.py:3` | I001 (import block) |
| `frequencia.py:64` | E741 (`l` ambíguo) |
| `regras.py:6` | I001 (import block) |

---

## 4. Testes — `tests/test_painel_periodo.py` (novo, 3 testes)

Cenário comum: unidade A, período 02/02–30/06/2026, **Turma Alfa** com 2 ofertas
(aluno A na oferta 1 com 4 presenças; aluno B na oferta 2 com 4 faltas ⇒ 50,0%)
e **Turma Beta** (aluno C com 4 presenças ⇒ 100,0%). Conselho FINAL por oferta
nas duas ofertas da Alfa, conselho PERCURSO em ambas (um com resposta) e Beta
sem conselho.

1. `test_visao_por_periodo_200_com_turmas_e_numeros` — `GET
   /relatorios/painel?periodo_letivo_id=…` → 200; página com “Turma Alfa”,
   “Turma Beta”, `50.0%`, `100.0%`, `2 alunos`, `1 alunos`; KPI do conselho
   “1 de 2”; linha da Alfa com `1/2` (percurso) e a Beta com `0/0`; programas
   corretos.
2. `test_visao_por_periodo_sem_turmas_responde_200` — período sem turmas → 200
   com “Sem conselho registrado.” e “Sem dados de renovação.”.
3. `test_visao_por_periodo_outra_unidade_nao_ve_dados` — sessão na unidade B →
   200 com “Nenhum período letivo cadastrado para esta unidade.” e sem
   “Turma Alfa”/`50.0%`.

Não havia smoke anterior dessas rotas (`tests/` não cobria `/relatorios/painel`
sem `turma_id`), então o arquivo foi criado em vez de estendido. Cada teste
semeia o próprio usuário e faz um único login.

Suíte completa: **`352 passed, 78 warnings in 54.86s`** (349 anteriores + 3).

---

## 5. Decisões tomadas sozinho

1. **`em_risco` = faixa `lo`** (mesma classificação de `faixas_alunos`) e
   **`em_risco_pct_str` = lo/total de alunos**, via `pct` + `fmt_pct` — é a
   leitura natural da coluna “Em risco” (`n · p%`), sem novo limiar.
2. **Conselho pelo agregado da turma** (não por oferta): o template desta visão
   mostra apenas `ok/total` por turma e os KPIs somam turmas; `"ofertas"` não é
   lido aqui.
3. **`joinedload(Turma.professor)` em `montar`** para não introduzir N+1 de
   professor por turma — única mudança fora da função.
4. **`semanal` calculado duas vezes** (uma em `montar` para `registrar_queda`,
   outra na linha para tendência/células). Mantive a assinatura exigida de 4
   argumentos em vez de mudá-la; é cálculo puro em memória, sem consulta.
5. **Fallbacks `"—"`** para `programa`, `turno` e professor ausente (mesmo
   padrão de `turma.py`), mantendo rótulos existentes.
6. **Turma sem frequência continua fora do comparativo** (`if not info:
   continue`) — comportamento pré-existente, não alterado (ver Pendências).
7. Reordenação de imports em `periodo.py` (I001) por ser arquivo já tocado.

---

## 6. Pendências

1. **Turma sem nenhuma frequência não aparece** no comparativo por período
   (`periodo.py:221-223`). É o comportamento anterior à B7; listar “turma sem
   aulas lançadas” exigiria montar a linha com `FrequenciaTurma()` vazio e é
   uma decisão de produto.
2. **`frequencia.agregar_por_turma` agrega por `turma_id`**, somando as ofertas
   da turma (coerente com os agregados de conselho da D5.4). Um “% por oferta”
   nesta visão exigiria mudar `frequencia.py` (fora do escopo).
3. Lint pré-existente no pacote (`formatacao.py:3` I001, `frequencia.py:64`
   E741, `regras.py:6` I001) não foi tocado — não são F821.
4. A visão por turma (`/relatorios/painel?turma_id=…`) já é exercitada por
   `tests/test_d5_leitores.py`; não há smoke dedicado a todos os cards dela
   (heatmap por aula, accordion de alunos).

---

## 7. Resumo do pytest

```
352 passed, 78 warnings in 54.86s
```
