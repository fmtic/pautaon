# AJ6-B — Autorização do professor por OFERTA

Tarefa: um professor vinculado a UMA oferta consegue acessar (ler e escrever)
a pauta de frequência — inclusive o CRUD — de TODAS as ofertas da turma da qual
faz parte. Regra desejada: o professor só acessa dados das ofertas em que ele é
o professor (`TurmaCurso.professor_id == usuário`). Demais perfis inalterados.

Restrições: sem migration, sem push, nenhuma escrita em banco real (só SELECT),
sem dado pessoal, `git status --porcelain` antes de checkout, reversão em
worktree. **"CRD" no enunciado = CRUD** (inserção/atualização/exclusão), não um
relatório à parte.

Branch `nova_feature`. HEAD atual: `dff6746`.

---

## Etapa 0 — Mapeamento (somente leitura)

### 0.1 A regra "professor da oferta" já existe, centralizada

`app/services/aluno_info_professor.py`:

- `condicao_professor_da_oferta(user_id)` → expressão SQL única:
  `TurmaCurso.professor_id == user_id` (sem herança de `turma.professor_id`).
- `professor_da_oferta(oferta, usuario)` → mesma regra para oferta carregada;
  `None` nunca libera.
- `professor_de_alguma_oferta_ativa(turma_id, usuario)` → **nível de TURMA**: o
  usuário é professor de *alguma* oferta ativa desta turma? É esta a função que
  as telas ainda montadas por turma usam para o guard, e a fonte do vazamento.

### 0.2 Superfície visível ao professor e o nível da guarda hoje

| # | Rota | Método | Guarda de acesso do professor | Nível | Vaza entre ofertas? |
|---|------|--------|-------------------------------|-------|---------------------|
| 1 | `/frequencia` (pauta + lançamento) | GET | lista turmas por `condicao_professor_da_oferta`; `turma_id ∈ turmas` (`core.py:412`) | **TURMA** | **SIM** — com 2+ ofertas o seletor aceita `turma_curso` de oferta alheia e carrega alunos/frequência/temas dela (`core.py:432-460`) |
| 2 | `/frequencia` (lançar/salvar — **CRUD de escrita**) | POST | `professor_de_alguma_oferta_ativa(turma)` (`core.py:255-266`) | **TURMA** | **SIM** — resolve oferta do form e grava frequência/diário em oferta de outro professor |
| 3 | `/turma/<id>/observacoes` (Diário de Bordo) | GET | `professor_de_alguma_oferta_ativa` (`turmas.py:2730`) | **TURMA** | **SIM** — lista `RegistroAula` de todas as ofertas; o filtro `turma_curso` aceita oferta alheia (`turmas.py:2751-2753`) |
| 4 | `/turma/<id>` (ver_turma / detalhe) | GET | `professor_de_alguma_oferta_ativa` (`turmas.py:1396`) | **TURMA** | **PARCIAL** — o payload carrega todas as ofertas/alunos (`ofertas_todas`, `alunos_por_oferta`, `ctx`); o template esconde os links que ele não abre via `ofertas_do_professor` (`turmas.py:1512`) |
| 5 | `/turma` (lista) | GET | **nenhuma** por professor; só unidade (`turmas.py:711-752`) | — | **SIM (visibilidade)** — lista todas as turmas ativas da unidade |
| 6 | `/turma/<id>/imprimir-pauta` (impressão) | GET | `professor_da_oferta(oferta)` (`turmas.py:2813`) | **OFERTA** ✅ | não (já oferta-level) |
| 7 | `/aluno/<id>/info-professor` (JSON) | GET | `consultar_aluno_para_professor` (`alunos.py:1572`) | **OFERTA** ✅ | não |
| 8 | `/conselho`, `/conselho/lancamento`, salvar, fechamento | GET/POST | `_escopo_professor()` + `professor_da_oferta` + `_guarda_oferta_explicita_do_professor` (`conselho.py:112,724,1057`) | **OFERTA** ✅ | aparentemente não (a confirmar no teste) |
| 9 | `/frequencia_relatorio` | GET | `role == PEDAGOGICO` (`core.py:648`) | — | N/A — o professor nem entra |
| 10 | dashboard do professor (`main.painel`) | GET | `_aulas_pendentes(..., professor_id)` filtra ofertas próprias (`dashboard_professor.py:82`) | OFERTA (pendências) | a confirmar escopo de `minhas_turmas` |

### 0.3 CRUD / exclusão de frequência

- **Escrita** (create/update) do professor = POST `/frequencia` (item 2). Não há
  endpoint por-registro de delete para o professor.
- **Exclusão** de lançamentos só aparece em `editar_turma`
  (`turmas.py:1943`, `Frequencia.query.filter_by(turma_id=id).delete()`) sob
  fluxo administrativo — não é rota do perfil professor.

### 0.4 Caso legado (`turma_curso_id NULL` / turma sem oferta ativa)

- Frequência/registro com `turma_curso_id NULL` só existem em turma com **0 ou
  1** oferta ativa (regra D2: inscrição sem curso cai na oferta única). Com 1
  oferta, a pauta da oferta inclui as linhas NULL.
- Turma **sem nenhuma oferta ativa**: `condicao_professor_da_oferta`/
  `professor_de_alguma_oferta_ativa` não casam com nada → hoje o professor **não
  consegue abrir** essa turma (não aparece na lista, e o POST daria 403).

---

## Decisões de regra (PARAR-e-perguntar — obtidas do responsável)

As três decisões propostas no Etapa 0 foram confirmadas antes da correção:

1. **Oferta alheia no seletor**: nenhuma oferta que não seja a dele deve **sequer
   aparecer** para preenchimento. Consequência: o seletor e a autoescolha passam
   a considerar só as ofertas dele (`ofertas_do_professor`); um professor com uma
   única oferta própria numa turma de várias é **autoescopo** nela.
2. **Legado / "professor da turma"**: *não existe mais* professor da turma — só o
   professor da OFERTA, que por sua vez pertence a uma turma. `Turma.professor_id`
   é vestigial e **jamais** concede acesso. Sem fallback: turma 100 % legada (0
   ofertas ativas) continua inacessível ao professor (mantém 403 / fora da lista).
3. **`/turma` (lista) e `ver_turma` (detalhe)**: **só reportar** agora (item
   "Itens que vazam" abaixo); não corrigir nesta tarefa.

Pedir oferta alheia de forma explícita (`?turma_curso=` / POST) → **403**, sem
revelar se a oferta existe (não há reescopo silencioso nesse caminho).

---

## Etapa 2 — Correção (helper central único)

`app/services/aluno_info_professor.py` ganhou o ponto único da regra:

- `professor_pode_acessar_oferta(usuario, oferta)` → `False` por padrão se anônimo;
  `True` para todo não-professor (deixa a guarda de role/unidade da rota agir,
  inalterada); para professor delega a `professor_da_oferta` (sem herança).
- `ofertas_do_professor(usuario, ofertas)` → filtra uma coleção pelas ofertas dele.

Aplicado nas três rotas que guardavam por TURMA (a regra **não** foi duplicada;
`assert_unidade_context` e as listas de roles intocadas):

- **GET `/frequencia`** (`core.py`): escopo do seletor às ofertas dele + 403
  antecipado quando `turma_curso` pedido não é dele; `somente_oferta` decidido
  pelo **total** de ofertas da turma (para não misturar linhas de outra oferta).
- **POST `/frequencia`** (`core.py`): autoescolha restrita às ofertas dele; a
  oferta dele é amarrada ao `resolver_oferta_lancamento`; **guarda final por
  OFERTA** (`professor_pode_acessar_oferta`) nega 403 sem gravar; `form_data`
  reamarrado à oferta resolvida antes de `salvar_frequencia`. A guarda final é
  pulada quando não há oferta resolvida (form sem data → caminho legítimo de
  flash+302 de `salvar_frequencia`), preservando `test_i1`.
- **`ver_observacoes`** (`turmas.py`): diário escopado às ofertas dele; 403 em
  `turma_curso` alheio; sem escolha, a query restringe aos `turma_curso_id` dele.

---

## Matriz antes × depois

Cenário `tests/test_aj6b_professor_oferta.py`: T1 = {A/pA, B/pB, C/pC},
T2 = {D/pA, E/pA, F/pB}; `turma.professor_id` de T1 é pA (vestigial). ANTES =
código de `HEAD dff6746` (prova de reversão em worktree `.tmp/aj6b_rev`);
DEPOIS = working tree com o fix. "—" = já estava correto (guarda por OFERTA).

| Rota (perfil pA) | Oferta própria | Oferta alheia | ANTES (HEAD) | DEPOIS |
|------------------|----------------|---------------|--------------|--------|
| GET `/frequencia` (pauta) | 200 | **200 (leak)** | leak | **403** |
| GET `/frequencia` (auto, sem param) | 200 | ofertas alheias **aparecem** na lista | leak | só as dele; alheias ocultas |
| POST `/frequencia` (gravar) | 302 | **302 + grava (leak)** | leak | **403, sem gravar** |
| GET `/turma/<id>/observacoes` (auto) | 200 | mostra `DIARIO` alheio | leak | só o diário dele |
| GET `/turma/<id>/observacoes?turma_curso=` | 200 | **200 (leak)** | leak | **403** |
| GET `/turma/<id>/imprimir-pauta?turma_curso=` | 200 | 403 | — | 200 / 403 |
| GET `/aluno/<id>/info-professor` (alheio) | — | 403 | — | 403 |
| POST `/frequencia` **sem data** (prof da oferta) | 302 | — | 302 | 302 (não 403) |
| Perfil não-professor (admin/ped/secre) | 200 | 200 | 200 | 200 (inalterado) |

Prova de reversão (worktree no `HEAD`, teste copiado, **sem** o fix): **7 falhas / 13
passes**, exatamente nas asserções de leak (GET/POST/alheia/auto + inativa). Com o
fix no mesmo arquivo de teste: **20/20**.

---

## Efeitos colaterais tratados (testes que codificavam o leak)

A suíte completa acusou, além do leak corrigido, testes escritos sobre o
comportamento antigo. Ajustados **mantendo a intenção** sob a nova regra:

- `test_i1_guardas_por_oferta.py::test_professor_da_oferta_ganha_acesso...` —
  **era regressão real**: POST sem data dava 403 (oferta resolvida `None`).
  Corrigido no **código** (guarda final só quando há oferta resolvida). Teste
  intocado.
- `test_v3a_datas_lancadas.py::test_html_sem_oferta_escolhida_nao_mostra_marcas`
  — usava `prof` (1 oferta própria) que agora é autoescopo. Passa a usar `admin`
  (2 ofertas → exige escolha). Novo teste
  `test_professor_com_oferta_unica_propria_e_autoescopo` cobre a autoescopa.
- `test_v3a_imprimir_coerente.py::test_imprimir_oculto_para_professor_que_nao_e_o_da_oferta`
  — oferta alheia agora é **403** (não 200 com botão oculto); docstring explica.
- `test_v3a_imprimir_coerente.py::test_imprimir_oculto_sem_oferta_escolhida_com_2_ofertas`
  — `prof` (autoescopo → botão visível) sai do laço; entram `admin`/`secretaria`/
  `pedagogico` (exige escolha → botão oculto) + asserção da autoescopa do professor.

## Itens que vazam e NÃO foram corrigidos (reportar — decisão do responsável)

- **`/turma` (lista)** `turmas.py:711-752`: sem filtro por professor; lista todas
  as turmas ativas da unidade. *Recomendação*: filtrar por `condicao_professor_da_oferta`
  para o professor (tarefa futura).
- **`ver_turma` (detalhe)** `turmas.py:1396`: o payload carrega todas as ofertas
  (`ofertas_todas`, `alunos_por_oferta`); o template já esconde os links alheios
  via `ofertas_do_professor`, mas os **dados** continuam no contexto da resposta.
  *Recomendação*: escopar o payload às ofertas dele.

## Pendência descoberta (pertence à AJ6-A, não à AJ6-B)

`tests/test_seletor_data_oferta.py` — 3 falhas (roda como **admin**, logo
independente deste fix): o seletor "Data da Aula" usa `get_local_now().date()`
como limite (`core.py:535`) em vez do relógio congelado do fixture, então
inclui uma data além de `hoje_ref()` (off-by-one de "hoje"). Coincide com o
subitem AJ6-A "migrar as 3 falhas de `test_seletor_data_oferta.py` para
`hoje_fixo`". Não tratado aqui.

---

## Validação

- Suíte completa, ruff `F821,F811,F841,F401` limpo nos 6 arquivos tocados,
  `py_compile` ok, git limpo, `git worktree list` só o principal.

## Commits

- `9b018c1` — `test(aj6b): matriz de autorizacao do professor por oferta`
  (novo `tests/test_aj6b_professor_oferta.py` + ajustes `test_v3a_datas_lancadas.py`
  e `test_v3a_imprimir_coerente.py`).
- `160ab51` — `fix(autorizacao): professor so acessa suas ofertas`
  (`aluno_info_professor.py`, `core.py`, `turmas.py`).
- `4af87c7` — `docs(aj6b): relatorio de autorizacao do professor por oferta`.

Branch `nova_feature`, sem push. Suíte completa pós-fix: **3 failed / 1465
passed**; as 3 falhas são as pré-existentes de `test_seletor_data_oferta.py`
(AJ6-A, admin). Prova de reversão (worktree no `HEAD`): **7 falhas / 13 passes**.
