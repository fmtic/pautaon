# AJ6-B5 — Lista `/turma` por papel (fechamento do acesso do professor à lista)

- **Branch:** `nova_feature` · **HEAD anterior:** `da0b527` (docs AJ6-B4)
- **Escopo:** apenas leitura/autorização na **lista** de turmas. Sem migration, sem
  push, nenhuma escrita em banco real (só `SELECT`), nomes sintéticos.
- **Regra central reutilizada:** `ofertas_do_professor` / `professor_pode_acessar_oferta`
  (`app/services/aluno_info_professor.py`). **Nenhuma predicação nova de acesso.**
- **Reversão:** `git worktree` em `D:/pautaon/.tmp/aj6b5_wt` (caminhos absolutos), removido ao final.

## REGRA DE NEGÓCIO (responsável)

A **lista** `GET /turma` só pode ser acessada por **admin, secretaria, pedagógico e
gerência**. O **professor NUNCA acessa a lista** — ele entra nas ofertas dele pelo
painel/ficha, regido pela autorização por oferta (AJ6-B3/B4). Esta decisão
**substitui** o "manter" registrado no **AJ6-B4, item 4** (que deixava `/turma`
intocado aguardando a posição do responsável).

## Resumo por item

| # | Item | Estado |
|---|------|--------|
| 1 | Gate da lista `[admin, secretaria, pedagogico, gerencia]`; professor → 403; reportar `servico_social` | Feito |
| 2 | Navegação do professor: nenhum link/redirect à lista (ficha e redirect de erro) | Feito |
| 3 | Código morto exclusivo de professor na rota | Nenhum a remover (provado por grep) |
| 4 | Testes: matriz de papéis + navegação + snapshot gestores idêntico | Feito (38 verdes) |
| 5 | Dados reais: usuários ativos por role (SELECT) | Feito |
| 6 | Reversão, ruff, suíte, contagens, git, commits | Em §5/§6 |
| 7 | Complemento AJ6-B4: inscrições ativas com `turma_curso_id` NULL | Feito (0 em ambos) |

---

## Item 1 — Gate da rota `turma` (lista)

`app/registros/turmas.py`, função `turma()` (rota `@bp.route("/turma")`).

- **Antes:** `["admin", "pedagogico", "secretaria", "gerencia", "professor"]`
- **Depois:** `["admin", "pedagogico", "secretaria", "gerencia"]`

**Quem perdeu acesso:** somente **`professor`**.

**`servico_social`:** **não** estava na lista antes e **não** foi adicionado — já
recebia **403** na lista. Portanto **ninguém além do professor** perdeu acesso
(inalterado para os demais). Confirmado por teste de matriz (item 4) e pelo gate original.

### Inventário de roles das demais rotas `/turma*` (NÃO alteradas — só reportadas)

| Rota (endpoint) | Roles com acesso |
|---|---|
| `GET /turma` (`turma`) — **a lista** | **antes** `[admin, pedagogico, secretaria, gerencia, professor]` → **depois** `[admin, pedagogico, secretaria, gerencia]` |
| `GET /turmas/lista` (`turma_lista`) | sem gate próprio; delega `turma()` → herda o novo gate (professor agora 403) |
| `GET /turmas/lixeira` (`turma_lixeira`) | `[admin, pedagogico, secretaria]` |
| `POST /turmas/reativar/<id>` (`reativar_turma_route`) | `[admin, pedagogico, secretaria]` |
| `GET/POST /turma/nova` (`nova_turma`) | `[admin, pedagogico, gerencia, secretaria]` |
| `GET /turma/<id>` (`ver_turma`) | ficha **por oferta** (AJ6-B3): professor entra se leciona oferta ativa da turma (`professor_de_alguma_oferta_ativa`); **não bloqueada** |
| `POST /turma/enturmar/<id>` (`enturmar_alunos`) | `[admin, pedagogico, secretaria, gerencia]` |
| `GET/POST /turma/editar/<id>` (`editar_turma`) | `[admin, pedagogico, secretaria]` |
| `GET /turma/<id>/ofertas` (`turma_ofertas` via `_turma_para_ofertas`) | `[admin, pedagogico, secretaria, gerencia]` |
| `POST /turma/excluir/<id>` (`excluir_turma`) | `[admin, pedagogico, secretaria]` |
| `GET /turma/<id>/observacoes` (`ver_observacoes` — diário) | `[admin, pedagogico, secretaria, professor]` |
| `GET /turma/<id>/imprimir-pauta` (`imprimir_pauta`) | gestores + professor (por oferta) |
| `GET /turmas/centros-custo/imprimir` (`imprimir_centros_custo_turmas`) | `[admin, pedagogico, secretaria, gerencia, professor]` — **ainda inclui professor** |

> **Nota (fora do escopo, para decisão do responsável):** `imprimir_centros_custo_turmas`
> (rota de **impressão** de centros de custo, não a lista) ainda tem `professor` no gate.
> O pedido restringe a mudança à **lista** `GET /turma`; não alterei a impressão.
> Se a intenção for alinhar a impressão à mesma regra, é decisão à parte (não fiz).

---

## Item 2 — Navegação do professor (o principal risco)

Varredura de `app/templates/**` e das rotas por `url_for('registros.turma')`, o
literal `"/turma"` e `redirect(url_for(...))` em fluxos alcançáveis pelo professor
(ficha `ver_turma`, diário `ver_observacoes`, frequência, histórico do aluno,
dashboard). Estado **antes** da varredura:

- **Navbar (`base.html:110–127`):** o item "Turmas" (`url_for('registros.turma')`) já
  estava dentro de `{% if current_user.role in ['admin','pedagogico','gerencia','secretaria'] %}`
  — **o professor já não via** o link. Nenhuma mudança necessária.
- **Dashboard do professor:** `main.painel` roteia para `render_dashboard_professor()`
  (template `dashboard/professor.html`), **sem** link à lista. O card "Gestão de turmas"
  (`dashboard/index.html:148`) pertence ao painel **gerencial** (admin/gerência/pedagógico),
  inalcançável ao professor. Nenhuma mudança.
- **Frequência (`lancar.html:7`)** e **Diário (`observacoes.html`)**: o "Voltar" já apontava
  para `main.painel`. Nenhuma mudança.
- **Rotas auxiliares** (`turma_lixeira.html`, `ofertas.html`, `editar.html`, `nova_turma.html`,
  `periodos/lista.html`): contêm link/redirect à lista, mas **nenhuma é alcançável pelo
  professor** (gates do item 1 os excluem). Nenhum risco.

**Dois pontos corrigidos** (única rota da lista alcançável pelo professor):

1. `app/templates/turmas/detalhe.html:391` — botão **"Voltar"** da ficha (`ver_turma`),
   que era o literal `href="/turma"`. Agora: para o professor, `href="{{ url_for('main.painel') }}"`;
   demais perfis mantêm `/turma`.
2. `app/registros/turmas.py:1453` — no `ver_turma`, o **redirect de erro** (falha de
   `carregar_contexto_turma`) ia para `url_for("registros.turma")`. Agora: para o
   professor, `redirect(url_for("main.painel"))`; demais seguem para a lista.

Prova (item 4): nenhum link/redirect à lista aparece nas páginas do professor; nenhum
redirect do professor cai em `/turma` (sem loop/403).

---

## Item 3 — Código morto exclusivo de professor

Após remover o professor do gate, **não há ramo exclusivo de professor** na rota `turma()`
nem em `listar.html` para remover:

- **Prova por grep:** nenhuma ocorrência de `current_user.role == PROFESSOR` /
  `== "professor"` dentro do corpo da rota (linhas ~718–932). Todas as ocorrências de papel
  professor no módulo estão em `ver_turma` e rotas posteriores (≥ linha 1408).
- A lista **nunca** ramificou por papel: o professor via a lista global da unidade.
- O **"dropdown de professores"** (`professores=professores_filtro`) e o filtro por nome de
  professor (`aplicar_filtros_turmas`, chave `professor`) são **critérios de filtragem usados
  pelos perfis gestores** para localizar turmas de um professor — **não** são exclusivos do
  professor. Conforme a instrução "não remover nada usado por outro perfil", **mantidos**.
- As colunas que mostram o nome do professor (`listar.html`) são exibição de dados para o
  gestor que vê a lista — mantidas.

Conclusão: nada a remover; nada de código morto introduzido.

---

## Item 4 — Testes

Arquivo novo: `tests/test_aj6b5_lista_turma_por_papel.py` (SQLite em memória, `hoje_fixo`,
semente do AJ6-B2 `_setup` + usuários por papel). Cobre:

- **Matriz de papéis** na lista: `admin/secretaria/pedagogico/gerencia → 200`;
  `professor → 403`; `servico_social → 403`.
- **Anônimo** → `302` para `/login` (@login_required, não 200/403).
- **Navegação do professor** (parametrizada): `painel`, `ver_turma(t1)`, `ver_turma(t2)`,
  `frequencia(t1)`, `diario(t1)`, `historico(aluno A)` — nenhuma página contém
  `href/action="/turma"` (lista) nem redirect à lista.
- **"Voltar" da ficha** (teste direcionado): aponta a `/painel` para o professor.
- **Snapshot golden** da lista (`admin/secretaria/pedagogico/gerencia`): HTML normalizado
  (sem `class=`, sem csrf, whitespace colapsado) comparado a `tests/snapshots/aj6b5_lista_<role>.txt`.
  Regenerável por `AJ6B5_ATUALIZAR_SNAPSHOTS=1`. **Gerado no HEAD antes do fix** e revalidado
  depois → **idêntico** (a remoção do professor do gate não toca a renderização dos gestores).

**Nenhum teste existente precisou ser invertido/ajustado:** `test_aj6a_painel_fumaca.py::
test_turma_listagem_200` **já pulava** `professor` e `servico_social`. Os demais acessos à
lista em testes (`test_d3b2_2_*`, `test_filtros_turmas`) usam **admin** (200, inalterado).

Rodada do arquivo novo + afetados: **38 passed** (0 failed).

---

## Item 5 — Usuários ativos por role (SELECT-only, bancos reais)

Contagens apenas (`is_active = true`); nenhuma escrita.

| Role | pautaon | pautaon_ensaio | Perde acesso à lista? |
|---|---|---|---|
| admin | 3 | 2 | não |
| gerencia | 3 | 4 | não |
| pedagogico | 2 | 3 | não |
| secretaria | 5 | 6 | não |
| **professor** | **8** | **9** | **sim** |
| **servico_social** | **1** | **1** | **não (já não tinha)** |

- **Quem perde:** os **professores ativos** (8 em `pautaon`, 9 em `pautaon_ensaio`).
- **`servico_social`** (1 em cada banco) **não perde** nada — já era 403 na lista.
- Em ambos os bancos, `ativos == total` por role (não há usuário inativo dessas roles).

---

## Item 6 — Verificação

- **Reversão (`git worktree` em `da0b527`, caminho absoluto):** os testes novos que
  dependem do fix **falham no código antigo** e o snapshot **passa**, provando detecção:
  - `test_matriz_papeis_lista_turma[professor-403]` → **FAIL** (antigo dava 200)
  - `test_navegacao_professor_sem_link_para_lista[ver_turma_t1]` → **FAIL** (Voltar vazava)
  - `test_navegacao_professor_sem_link_para_lista[ver_turma_t2]` → **FAIL**
  - `test_voltar_ficha_turma_leva_professor_ao_painel` → **FAIL**
  - Resultado no worktree: **4 failed / 11 passed**; controles (gestores 200,
    `servico_social` 403, anônimo 302, snapshot, demais páginas) **passaram**.
- **Ruff** `--select F821,F811,F841,F401` nos `.py` tocados (`app/registros/turmas.py`,
  `tests/test_aj6b5_lista_turma_por_papel.py`): **All checks passed**. (O `detalhe.html` é
  template Jinja, não é alvo do ruff.)
- **Suíte completa (uma vez):** **1519 passed / 0 failed / 0 skipped** em 1176.89s
  (0:19:36). **Nenhum skip** (nada de `-rs`). Corresponde a 1504 (fechamento AJ6-B4)
  + 15 novos testes desta tarefa.
- **Contagens dos bancos reais (antes/depois, SELECT-only):** todas as tabelas de
  conteúdo e todas as sequências **idênticas**. A **única** diferença é o log de auditoria
  **append-only** `log_acao` em `pautaon` (1152 → 1158, +6 linhas), cujas linhas são
  exclusivamente eventos **"Acesso Aprovado"/"Logoff" de 127.0.0.1** — logins/logouts
  ambientes durante a janela da suíte, **não** originados pelo código nem pelos testes da
  AJ6-B5 (os testes rodam em SQLite em memória e a trava AJ6-C aborta a suíte se o
  ambiente apontar para Postgres). Nenhuma linha de negócio foi criada/alterada por esta
  tarefa; nenhuma escrita foi feita aos bancos reais.
- **`git status` limpo e commits separados (test, fix, docs):** guarda `git status
  --porcelain` antes de qualquer checkout; worktree de reversão removido (`git worktree
  list` → só `D:/pautaon`). Commits: **test** `69544c5`, **fix** `fd71ca5`, **docs** (este
  relatório). Árvore de trabalho fica limpa ao final.

---

## Item 7 — Complemento AJ6-B4 (inscrições com `turma_curso_id` NULL)

`SELECT` em `pautaon` e `pautaon_ensaio` contando inscrições **ativas** com
`turma_curso_id IS NULL`:

| Banco | contagem | ids | turmas envolvidas |
|---|---|---|---|
| pautaon | **0** | — | — |
| pautaon_ensaio | **0** | — | — |

Nenhuma inscrição ativa órfã de oferta. Portanto o escopo do `historico_aluno` por
`ofertas_do_professor` (AJ6-B4 item 1) **não descarta nenhuma linha real** — inclusive
para professor de oferta única. **Nada a corrigir** (e nada foi corrigido além do escopo).

> Contexto do schema: `Inscricao.turma_curso_id` é `NOT NULL` desde a migration
> `c3d4e5f6a7b8` ("inscrição exige oferta"), consistente com o resultado 0 em produção.
