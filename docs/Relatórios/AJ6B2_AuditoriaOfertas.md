# AJ6-B2 — Auditoria pós-AJ6-B da autorização do professor por OFERTA

Auditoria de verificação após a correção da AJ6-B (fix `160ab51`, já em
`HEAD`). Branch `nova_feature`. **Sem migration, sem push, nenhuma escrita em
banco real (só SELECT), `git status --porcelain` antes de qualquer checkout,
reversão em `git worktree`, nenhum dado pessoal (só ids, contagens e rótulos
sintéticos).**

Cenário sintético usado nos testes (`tests/test_aj6b2_auditoria_ofertas.py`):

```
T1: A(pA)  B(pB)  C(pC)     — pA só leciona A em T1
T2: D(pA)  E(pA)  F(pB)     — pA leciona D e E (duas na MESMA turma)
pC: 0 ofertas em T2          — "professor dono de 0 ofertas da turma"
Alunos "Aluno A".."Aluno F"  — um por oferta; diário DIY-A..DIY-F
```

---

## 1. Escrita cruzada histórica (bancos reais, SELECT-only)

Pergunta: existe linha de `frequencia` (`autor_id`) ou `registro_aula`
(`instrutor_id`) cujo autor é `role='professor'` **e diferente** de
`turma_curso.professor_id` daquela linha? Separamos linhas com
`turma_curso_id` NULL. Script: `.tmp/aj6b2_audit.py` (saída
`.tmp/aj6b2_audit_out.txt` / `.json`).

| Banco | tabela | oferta ligada (n) | oferta NULL (n) | ids | faixa de datas |
|---|---|---|---|---|---|
| pautaon | frequencia | 0 | 0 | — | — |
| pautaon | registro_aula | 0 | 0 | — | — |
| pautaon_ensaio | frequencia | 0 | 0 | — | — |
| pautaon_ensaio | registro_aula | 0 | 1 | `[12]` | 2026-08-03 .. 2026-08-03 |

**Conclusão:** não há **nenhuma** escrita cruzada histórica real (autor
professor ≠ professor da oferta) em nenhum dos dois bancos. A única linha
destacada (`registro_aula` id=12 no ensaio) tem `turma_curso_id NULL` — é um
registro **legado**, anterior ao vínculo por oferta, e **não** configura escrita
cruzada (não há oferta para contrastar). Ou seja: o leak da AJ6-B era de
**superfície/seletor**, não de gravação — o dado histórico está limpo. Não há
o que sanar em produção.

## 2. Impacto da nova regra em dado real (bancos reais, SELECT-only)

"Quantos professores perdem acesso por isso" — acesso, aqui, é poder lançar
frequência / abrir diário / ver pauta (a régua nova é `TurmaCurso.professor_id
== usuário`, sem herdar `Turma.professor_id`).

| Item | pautaon | pautaon_ensaio | professores que perdem acesso |
|---|---|---|---|
| (a) ofertas ativas com `professor_id` NULL | 0 | 0 | 0 |
| (b) turmas ativas **sem** oferta ativa | 0 | 0 | 0 |
| (c) turma ativa com `Turma.professor_id` cheio, mas nenhuma oferta ativa dele | 0 | 0 | 0 |
| (d) professores ativos **sem nenhuma** oferta ativa | **4** (ids 5, 89, 91, 92) | **4** (ids 5, 91, 92, 100) | 4 (cada banco) |

Notas:

- **(a) é estruturalmente 0**: desde `d6e7f8a9b0c1` `turma_curso.professor_id`
  é `NOT NULL`. Confirmado em dados: nenhuma oferta ativa sem professor.
- **(b)=0 e (c)=0**: nenhum professor está sendo sustentado por herança de
  turma. Logo, os 4 de **(d)** não "perdem" acesso que já exerciam via turma —
  simplesmente não lecionam oferta ativa alguma (contas de professor sem
  vínculo ativo: novos, inativos ou desenturmados). Perda efetiva de capacidade
  de lançamento para os perfis professor: **4 por banco**, todos sem oferta ativa
  própria. Os demais perfis (admin/pedagógico/secretaria/gerência/serviço
  social) são inalterados pela regra.

## 3. Guarda final pulada sem oferta resolvida (`core.py`, POST /frequencia)

A guarda FINAL só atua quando o `resolver_oferta_lancamento` devolveu uma
oferta. Quando `oferta_post` é `None` (cenário sem data no form), ela é
deliberadamente pulada — linhas relevantes (`app/registros/core.py`):

```python
# 315-337  professor: auto-amarra a oferta dele quando tem exatamente 1;
#          com 2+ dele, exige escolha (oferta_id_post segue None).
if current_user.role == UserRole.PROFESSOR:
    ativas_post = ofertas_do_professor(current_user, ativas_todas_post)
    if len(ativas_post) == 1 and oferta_id_post is None:
        oferta_id_post = ativas_post[0].id
...
    resolver_curso_id = oferta_id_post          # None com 2+ ofertas dele
    oferta_post = resolver_oferta_lancamento(
        int(turma_post_id), data_alvo_post,
        turma_curso_id=resolver_curso_id, tema_ids=tema_ids_post,
    )                                          # ValueError com 2+ sem escolha
except ValueError as exc:
    flash(str(exc), "warning")
    return redirect(...)                        # <- retorna SEM gravar

# 349-354  guarda FINAL (pulada se oferta_post é None):
if (
    current_user.role == UserRole.PROFESSOR
    and oferta_post is not None
    and not professor_pode_acessar_oferta(current_user, oferta_post)
):
    abort(403)
```

Por que a pulança é **segura** (nunca grava `turma_curso_id NULL` numa turma
com 2+ ofertas ativas):

- Com **data presente**, o resolver da própria roda (333) para o professor com
  2+ ofertas dele e sem escolha levanta `ValueError` → flash → `redirect`
  (340). `salvar_frequencia` **não é alcançado**. `oferta_post` nunca chega
  `None` ao gravar nesse caminho.
- O resolver só devolve `None` quando a turma tem **0** ofertas ativas (legado)
  — mas o professor com 0 ofertas cai antes, na **guarda de adesão**
  (`professor_de_alguma_oferta_ativa`, linhas 255-266) → 403.
- Mesmo que `salvar_frequencia` fosse chamado sem `turma_curso`, ele re-resolve
  internamente (logica.py 697) e, sem data, devolve `(turma_id, None)` → a rota
  só faz flash "Preencha a data" (412-414). Nenhuma linha nasce com oferta NULL
  em turma com 2+ ofertas.

**Prova empírica (3 testes novos):** `test_item3_post_duas_ofertas_sem_turma_curso_nao_grava_null`
(pA em T2, POST com data e sem `turma_curso` → 302, zero linhas em T2),
`test_item3_post_zero_ofertas_da_turma_403_sem_gravar` (pC POST em T2 → 403, zero
linhas) e `test_item3_post_oferta_alheia_explicita_403_sem_gravar` (pA POST na
oferta B de pB → 403, não grava). **Não gravei nenhuma linha com
`turma_curso_id NULL`; nada a corrigir nem a perguntar.**

## 4. Itens "a confirmar" da matriz

### 4.1 Rotas recém-confirmadas (testes pA/pB no arquivo novo)

| Rota | resultado | base (pré-AJ6-B) |
|---|---|---|
| `GET /conselho` (painel) | 200 p/ pA; lista já é filtrada por `professor_id=current_user.id` (conselho.py 300-309) | já correta |
| `GET /conselho/lancamento?oferta_sel=<alheia>` | **403** pA→B/C e pB→D/E (`_guarda_oferta_explicita_do_professor`) | já correta |
| `GET /conselho/lancamento?oferta_sel=<própria>` | ≠403 (pA→A, pB→F) | já correta |
| `POST /conselho/salvar` com `turma_curso_id=<alheia>` | **403** (conselho.py 724) | já correta |
| `GET /conselho/fechamento/<turma>` | **403 p/ todo professor** (guarda de papel, 859-862) | já correta |
| `/dashboard` (`_entradas_professor`) | só ofertas do professor: pA→{A,D,E}, pB→{B,F} | já correta |
| `GET /api/alunos/<turma>` (JSON) | **403** p/ professor (whitelist de papel não o inclui) | já correta |
| `GET /conselho/imprimir` (export) | **403** p/ professor (só pedagógico/admin/gerência) | já correta |

Todas as rotas da matriz **já estavam** escopadas por oferta ou por papel antes
do fix `160ab51` (que só mexeu em `core.py`, `ver_observacoes` e os helpers).
Por isso esses testes passam também na base `dff6746` — o único teste novo que
**falha** na base é o do POST de oferta alheia (seção 6), que é exatamente a
superfície que a AJ6-B corrigiu.

### 4.2 Grep dos usos restantes (com arquivo:linha e veredito)

`professor_de_alguma_oferta_ativa` — **concede acesso, e pela OFERTA (correto)**:

- `aluno_info_professor.py:117` — definição (checa `TurmaCurso` ativo do usuário,
  **sem** herdar `Turma.professor_id`).
- `core.py:259,263` — guarda de adesão no POST /frequencia.
- `turmas.py:1385,1396` — adesão em `ver_turma` (`/turma/<id>`).
- `turmas.py:2726,2733` — adesão em `ver_observacoes` (`/turma/<id>/observacoes`).

`Turma.professor_id` — 37 ocorrências, agrupadas por efeito:

- **Comentários/docstrings** (não executam; afirmam "sem herdar"):
  `turmas.py:1391,2723,2827`; `core.py:257,434`; `aluno_info_professor.py:13,92,120`;
  `bi_alunos.py:2036`.
- **Resolução de nome / busca (exibição), não concede acesso**:
  `turmas.py:574,578,585` (COALESCE do nome do professor; busca por `prof_like`).
- **Relatórios de gestão/BI — professor toma 403 por papel**
  (`ROLES_RELATORIOS` não inclui professor; `carga_horaria_turmas` exige
  admin/pedagogico/gerencia/secretaria). `professor_id` é **parâmetro de filtro**
  escolhido por quem vê, não escopo da sessão:
  `turmas.py:2535,2554,2566,2585,2605,2654,2657,2685`;
  `bi_alunos.py:1536,1573,1612,1666,1728,1792,1838,1854,2764`.
- **Aviso de contagem no painel de conselho** (`stmt.where(Turma.professor_id ==
  professor_id)` para somar "turmas sem oferta ativa"):
  `conselho.py:321` — não libera dado de aula, é só um número de aviso.
- **ÚNICO ponto que ainda influencia a lista de acesso do professor** (reportado,
  não corrigido): `dashboard_professor.py:200` — fallback legado
  `Turma.query.filter_by(professor_id=user_id, ativo=True)`. Só dispara quando a
  turma **não tem nenhuma oferta ativa** (linhas 203-206 fazem `continue` se ele
  tem oferta ou se a turma tem ofertas ativas). Impacto em dado real = **0**
  (item 2b = 0 turmas ativas sem oferta ativa). Ainda assim é o resquício de
  herança `Turma.professor_id` num escopo de acesso, e conflita com a decisão
  "legado sem fallback" da AJ6-B — fica como pendência de decisão do operador.

## 5. `ver_turma`: o corpo revela alunos de oferta alheia?

**SIM — vaza.** O `professor_de_alguma_oferta_ativa` libera a **entrada** em
`/turma/<id>` por adesão à turma (basta o professor ter **uma** oferta ativa
nela). Uma vez dentro, o corpo (`turmas/detalhe.html`) monta `alunos_por_oferta`
a partir de **todas** as inscrições ativas da turma (`turmas.py:1490-1498`) e o
filtro `ofertas_do_professor` (1512-1516) só esconde os **links** de pauta/
diário, não a **lista de alunos**.

Medido no teste `test_item5_ver_turma_corpo_markes_oferta_alheia`: pA (só oferta
A em T1) abre `/turma/<T1>` e o HTML **contém** "Aluno A" (próprio), **e também**
"Aluno B" e "Aluno C" (ofertas de pB e pC).

**Não corrigido, a pedido.** É a mesma natureza do item reportado na AJ6-B
(adesão por turma em `ver_turma`): para fechar, a régua de entrada precisaria
ser por oferta (ou o corpo precisaria filtrar `alunos_por_oferta` pelas ofertas
do professor). Fica para decisão do operador.

## 6. Prova de reversão, ruff, suíte e contagens

- **Prova de reversão** (worktree `.tmp/aj6b2_rev` em `dff6746`, base pré-AJ6-B;
  copiou-se o arquivo de teste novo para lá): **1 falha / 15 passes**. A falha é
  `test_item3_post_oferta_alheia_explicita_403_sem_gravar` → recebeu **302** na
  base (escrevia na oferta alheia, o leak) contra **403** esperado na HEAD.
  Confirma que a âncora detecta a regressão. Worktree removido em seguida
  (`git worktree list` só o principal).
- **Ruff** `F821,F811,F841,F401` em `tests/test_aj6b2_auditoria_ofertas.py` e no
  script-probe: **limpo**.
- **Suíte completa** (repo principal, com fix): **1484 passed / 0 failed**
  em 963s (EXIT=0). São as 1468 da AJ6-B/AJ6-A + os 16 testes novos deste
  arquivo — repositório inteiro verde.
- **Contagens antes/depois (bancos reais)**: rodadas com
  `.tmp/aj6c2_contagens.py` imediatamente antes e depois da suíte;
  `pautaon` e `pautaon_ensaio` **IDÊNTICOS** (dict a dict, incluindo
  `count(*)` de todas as tabelas e `last_value` das sequências). Prova de
  que a suíte não tocou Postgres e de que esta auditoria foi **SELECT-only**.
  Snapshot: `.tmp/aj6b2_counts_before.json` / `.tmp/aj6b2_counts_after.json`.
