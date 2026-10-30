# L4.2 — `Turma.programa` na reativação + auditoria do harness (perfis)

**Branch:** `nova_feature` · **HEAD Alembic:** `8d2e3f4a5b6c` (inalterado) · **Suíte:** 712 → **722 passed** · **Data:** 28/10/2026

Sem migration. Sem push. Dois commits: **A** `e1409db` (serviço + caracterização/testes) e **B** (helper do harness + testes de prova + docs: este relatório, MER §8.10/§10/§12.16, backlog).

---

## 1. Resumo

- **Parte A:** `reativar_turma` devolvia turma e ofertas à vida **sem reprojetar** `Turma.programa`. Quando a seleção da lixeira deixava ativa uma oferta diferente da antiga principal, a turma passava a exibir o programa de uma oferta que não voltou. Correção: uma chamada a `sincronizar_programa_turma` ao final do serviço, na mesma transação, **só quando ao menos uma oferta é reativada**.
- **Parte B:** auditoria de todo o diretório `tests/` (AST + grep). **Uma** função troca de perfil no mesmo teste (`test_h4_leitores_grade_variavel_smoke.py::test_aluno_ficha_atendimento_conselho_frequencia_seletor`) e ela **funciona** (classe **a**): o módulo não mantém AppContext aberto durante os requests. Nenhum teste cai na armadilha `g`/Flask-Login (classe **b**). A armadilha foi **reproduzida** num teste mínimo e o helper `login_as` foi adicionado a `tests/_helpers.py` **sem alterar nenhum teste existente** (722 passed).

---

## 2. P1 — regra confirmada (antes de mexer)

`sincronizar_programa_turma(turma)` (`app/services/turma_curso.py:452`): projeta em `Turma.programa` o programa da **oferta principal ativa**; com **uma** oferta ativa ela é a referência **mesmo sem** a marca de principal; **sem** ofertas ativas a projeção fica `None`.

Chamadores (antes desta entrega): `criar_oferta_inicial_da_turma`, `adicionar_oferta`, `editar_oferta`, `definir_principal`, `desativar_oferta` — e as rotas `editar_turma` (`app/registros/turmas.py:1809` e `:1953`). `reativar_turma` **não** chamava. A regra da tarefa (projeção da principal ativa) foi confirmada — sem divergência, P1 liberado.

---

## 3. P2 — caracterização (antes × depois)

`tests/test_l4_2_programa_reativacao.py` (7 testes). Semente: turma com **A** (principal, programa `X`) e **B** (`Y`), inscrição em A e uma `Frequencia` (força a exclusão **lógica**); exclusão e reativação pelas **rotas reais**; `Turma.programa` lido do banco após `db.session.expire_all()`.

**Antes** (código do L4.1, sem a chamada):

```
.FFFF.F                                                                  [100%]
FAILED test_p2_reativar_so_b_reprojeta_programa_de_b
  assert 'X' == 'Y'                             # programa ficou na oferta que NÃO voltou
FAILED test_p2_reativar_so_b_com_marcador_da_exclusao
  assert 'X' == 'Y'
FAILED test_p2_programa_desatualizado_e_corrigido_na_reativacao
  assert 'PROGRAMA ANTIGO' == 'X'               # projeção suja não era corrigida
FAILED test_p4_servico_reprojeta_sem_commit
  assert 'PROGRAMA ANTIGO' == 'X'               # idem, chamando o serviço
4 failed, 3 passed
```

Passavam **antes** (e continuam passando): reativar A+B (o valor já era `X`), recusa atômica (nada é escrito) e turma sem oferta reativada (não há projeção a recalcular). Esses três são guardas de regressão da correção, não caracterização do defeito.

**Depois:**

```
.......                                                                  [100%]
7 passed
```

| Cenário | Antes | Depois |
|---|---|---|
| 1. reativar A+B (A principal, X) | `X` | `X` |
| 2. reativar só B (B desativada antes; escolha explícita) | `X` ❌ | `Y` |
| 2'. reativar só B (A e B caíram juntas; só B marcada) | `X` ❌ | `Y` |
| 3. projeção suja (`PROGRAMA ANTIGO`) | `PROGRAMA ANTIGO` ❌ | `X` |
| 4. recusa atômica (2 marcas de principal) | `DESATUALIZADO` | `DESATUALIZADO` |
| 5. turma sem ofertas (nada reativado) | `MANTER` | `MANTER` |
| 6. serviço sem commit (rollback) | não reprojetava ❌ | reprojeta e o rollback desfaz |

**Cenário 2 — resultado fixado pela regra:** com uma única oferta ativa, `sincronizar_programa_turma` usa `ativas[0]` como referência mesmo sem a marca de principal ⇒ `Turma.programa = Y`. Não é decisão nova: é exatamente o que `desativar_oferta`/`adicionar_oferta` já fazem na mesma situação.

---

## 4. P3 — implementação

`app/services/turma_curso.py`, final de `reativar_turma` (depois de toda validação, junto com as mutações):

```python
if avaliacao["selecionadas"]:
    sincronizar_programa_turma(turma)
```

- **Mesma transação**, sem `commit` no serviço (a rota continua sendo a única dona do commit — provado por `test_p4_servico_reprojeta_sem_commit`, que faz `rollback` e vê o valor antigo no banco).
- **Condicionada** a `selecionadas`: turma sem ofertas (estado legado) não tem referência e **não pode perder** o programa que ainda alimenta listagem e filtros (`test_p4_turma_sem_reativada_nao_zera_programa`).
- Nenhuma outra alteração em `app/` (o `grep` de chamadores segue com as 4 funções de serviço + 3 pontos de rota).

**P4:** os 7 testes novos passam; a recusa atômica **não** altera `Turma.programa`; `tests/test_l4_1_reativacao_ofertas.py` (19) e `tests/test_l4_lixeira.py` (9) rodam **inalterados** — 35 passed nos três arquivos juntos.

---

## 5. P5 — método e inventário

Ferramentas (script AST descartável + grep, nada versionado):

1. Normalização do corpo das funções de teste **sem descer em `def` aninhadas** (evita contar `sess["_user_id"] = ...` duas vezes quando o login está numa função interna).
2. Detecção de "função que loga": atribui `sess["_user_id"]`, faz `client.post("/login")` ou chama `login_user`.
3. Para cada `test_*`: coleta as **chamadas** a essas funções (helper do módulo ou def aninhada) com os argumentos e as atribuições inline, e sinaliza quem tem **>1 evento**.

Números: **49** atribuições de `_user_id` em **26** arquivos; **3** funções com mais de um evento; **1** com usuários **distintos**.

---

## 6. Tabela da auditoria

| arquivo:função | padrão | classe | prova |
|---|---|---|---|
| `tests/test_h4_leitores_grade_variavel_smoke.py::test_aluno_ficha_atendimento_conselho_frequencia_seletor` | 3 identidades na mesma função: `_client(app, coord, unidade)` → `_client(app, prof)` → `_client(app, pedag, unidade)`; **apps/clientes novos e sem AppContext aberto** no corpo do teste | **a** | `test_p6_classe_a_app_sem_contexto_aberto_a_troca_de_perfil_vale` — o mesmo padrão (app próprio, dois clientes, sem contexto preso) devolve **200** para o admin e **403** para o professor na rota só de gestão |
| `tests/test_leitores_grade_h3e.py::test_conselho_painel_e_fechamento_por_dia` | dois `_client(app, coord, unidade)` — **mesmo** usuário (não é troca de perfil) | — (não é ocorrência) | — |
| `tests/test_ui_grade_por_dia.py::test_erro_domingo_rejeitado` | dois `_loga(app, coord, unidade)` — **mesmo** usuário | — (não é ocorrência) | — |

Descartes examinados um a um (todos com **uma** identidade): `test_bi_indicadores::test_indicadores_de_status_isolam_unidade_do_usuario_na_rota`, `test_dashboard_professor_pedagogico::test_rota_painel_pedagogico_permissao_e_render`, `test_pauta_professor::test_professor_pauta_mostra_somente_alunos_da_turma_associada`, `test_pauta_professor::test_professor_nao_acessa_pauta_de_turma_de_outro_professor`, `test_turma_curso_fase3::test_rota_oferta_nova_conflito_com_aviso` (novo `test_client()` + **um** login), `test_d3b2_2_n1_freq_geral::test_listagem_rota_nao_faz_n_plus_1` (o AST contava o login interno + a chamada do helper: **1** login real), `test_dashboard::_prepare_dashboard` (helper com **um** login), `test_carga_horaria_curso`, `test_filtros_turmas` (login inline único), `test_security_regressions` (login POST único + `login_user` num `test_request_context` próprio em `_criar_admin_cursos`). Fixtures com login: **nenhuma** (verificado por AST em todos os módulos).

**Nenhuma ocorrência de classe (b) ou (c).** Ou seja: os 403 de perfil da suíte **são** exercitados de verdade hoje.

---

## 7. P6 — prova da armadilha e do padrão correto

`tests/test_l4_2_harness_perfis.py` (3 testes, rota `GET /turmas/lixeira`, que dá 403 a professor):

1. `test_p6_classe_a_app_sem_contexto_aberto_a_troca_de_perfil_vale` — padrão do módulo H4 (app criado no teste, contexto **fechado** antes dos requests): admin **200**, professor **403**. Confirma que a ocorrência real é classe (a).
2. `test_p6_classe_b_fixture_com_contexto_aberto_ignora_a_troca` — fixture clássico (`with app.app_context():` preso): admin **200**; trocando só `sess["_user_id"]` para o professor, a resposta continua **200**. O `g._login_user` do primeiro request sobrevive. **É o motivo de existir a convenção "um usuário por teste"** (T1 §5.6) — e o motivo de o assert de 403 ser enganoso nesse estilo.
3. `test_p7_login_as_limpa_o_cache_e_o_403_acontece` — com `login_as`: admin **200** → professor **403** → admin **200** (reversível).

`python -m pytest tests/test_l4_2_harness_perfis.py -q` → `3 passed` (o item 2 passa **porque** caracteriza o comportamento atual; se o harness mudar, ele falha de propósito, com mensagem explicando).

---

## 8. P7 — correção padrão (aplicada só ao helper)

Adicionado `login_as(client, user, unidade_id=None)` em `tests/_helpers.py`:

```python
if has_app_context():
    g.pop("_login_user", None)   # invalida o cache do Flask-Login
with client.session_transaction() as sess:
    sess["_user_id"] = str(getattr(user, "id", user))
    sess["_fresh"] = True
    if unidade_id is not None:
        sess["unidade_id"] = unidade_id
```

- **Por que é suficiente:** `flask_login.utils._get_user()` só carrega da sessão quando `"_login_user" not in g`; limpar a chave faz o próximo request reler o `_user_id` da sessão (verificado no item 3 acima).
- **Escopo:** função **nova**, nenhum teste existente foi migrado nem teve resultado alterado (`722 passed`, exatamente 712 + 10 novos). A migração dos 26 arquivos para o helper fica como decisão do responsável (§12.16 do MER).
- **Alternativa descartada:** "novo `app_context` por request" (fixture que empurra contexto) exigiria mexer em todos os módulos e mudaria o ciclo de sessão SQLAlchemy de toda a suíte — risco alto para ganho pequeno.

---

## 9. Achados adicionais (sem correção nesta entrega)

1. **Asserts fracos na ocorrência classe (a).** No teste do H4, as três identidades acessam as rotas usadas (`/frequencia` e `/frequencia_relatorio`): o `assert status_code == 200` passaria com qualquer um dos três perfis, então a troca de perfil não é usada como discriminador. Sugestão: usar ao menos uma rota restrita (ex.: `/turmas/lixeira`) quando o objetivo for provar identidade.
2. **§12.16 do MER (conftest único)** continua pendente; `login_as` em `tests/_helpers.py` é o primeiro tijolo dele.
3. **Duas convenções já documentadas no código** (`_seed_perfil` em `test_l4_1_reativacao_ofertas.py` e a nota de harness de `test_transferencia_oferta.py`) descrevem a mesma armadilha — conferidas e coerentes com esta auditoria.

---

## 10. Desvios

1. **Cenário 1 (reativar A+B) não falhava antes.** Como `excluir_turma` não toca `Turma.programa`, o valor já era `X`; o teste entra como guarda de regressão (documentado no docstring).
2. **Cenário 2 com duas variantes** (B desativada antes × B desativada na exclusão): a regra da sincronização dá o **mesmo** resultado (`Y`); as duas ficaram fixadas para não depender do marcador L4.1.
3. **Teste extra de serviço** (`test_p4_servico_reprojeta_sem_commit`) para provar o "sem commit no serviço" por `rollback`, exigido na P3 — não estava na lista de cenários, é barato e cobre o contrato.
4. **`ruff` desta máquina:** `python` do PATH aponta para `C:\Python314` (sem `ruff`); os comandos de validação foram rodados com `.\.venv\Scripts\python.exe -m ruff`.
5. **Achado de harness = 1 ocorrência (classe a), não (b)/(c).** A prova exigida para (b)/(c) foi produzida de todo modo (item 2 do P6) para documentar a armadilha e justificar o helper.
6. **MER:** além de §10, uma frase em §8.10 (regra de reativação) e uma linha em §12.16 (harness) — sem isso a documentação ficaria contraditória.

---

## 11. Validação final

| Item | Resultado |
|---|---|
| `pytest tests -q` | **722 passed**, 0 falhas (712 antes + 10 novos) |
| `ruff check app tests --select F821,F811` | All checks passed |
| `git diff --check` | sem erros |
| Migration | nenhuma (`8d2e3f4a5b6c` inalterado) |
| Push | não houve |
