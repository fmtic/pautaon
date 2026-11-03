# AJ6-B6 — Matriz de rotas do papel **professor**

Base: branch `nova_feature`, HEAD = `e1419d6` (docs AJ6-B5). Sem migration, sem
push, sem escrita no banco real (só SELECT). Nomes sintéticos. Reversão provada
em `git worktree` com caminhos absolutos. Sem código morto.

---

## 0. Aviso sobre o gate de centros-custo (verificação inicial)

`git status --porcelain` na abertura do trabalho retornou **vazio** (somente a
sonda `tests/test_aj6b6_probe.py`, agora removida, estava como untracked). A
remoção de `professor` do gate de `/turmas/centros-custo/imprimir` **já está em
HEAD** (fechada nos ciclos AJ6-B4/B5), não como mudança solta na árvore:

```python
# app/registros/turmas.py:939  (imprimir_centros_custo_turmas)
if current_user.role not in ["admin", "pedagogico", "secretaria", "gerencia"]:
    abort(403)          # 'professor' AUSENTE — negação ativa
```

Nada foi sobrescrito nem revertido. Este trabalho **trava** esse estado com
teste (`test_centros_custo_imprimir_negado_ao_professor`): professor → 403,
secretaria → não-403. A remoção entra no commit **fix** deste trabalho na forma
de **teste-trava** (a mudança de código em si já é de HEAD).

---

## 1. Inventário ESTÁTICO (url_map completo)

Script: `python .tmp/aj6b_inventario_estatico.py` → `.tmp/aj6b_estatico_out.txt`.
Saiu uma tabela `endpoint | métodos | roles que passam | professor passa?` para
as 210 regras (199 endpoints; variantes de centro-custo registradas em loop por
`add_url_rule` em `registros/periodos.py`).

O AST detecta `@login_required`, gates inline (`role in/not in [...]`,
`== UserRole.X`), constantes de módulo (`_ROLES_PERIODO`, `_ROLES_CALENDARIO`,
`_ROLES_CENTRO_CUSTO`, `_ROLES_ATENDIMENTO`), helpers (`_check_calendario_access`,
`professor_pode_acessar_oferta`, `_guarda_oferta_explicita_do_professor`) e a
diferença `abort(403)` vs `redirect`.

**Rotas sem guarda de role (o "professor alcança por omissão" — 22 endpoints):**

| Endpoint | Rota | Na varredura real (item 2) |
|---|---|---|
| auth.trocar_senha | /trocar-senha | 200 — **legítimo** (senha própria) → allowlist |
| conselho.index_conselho | /conselho | 200 — legítimo (escopo interno) → allowlist |
| conselho.informacoes | /informacoes | 403 (guarda que o AST não viu) |
| conselho.salvar_periodo_conselho | /api/conselho-periodo | 403 |
| conselho.deletar_periodo_conselho | /api/conselho-periodo/<id> | só DELETE (fora de GET/POST) |
| conselho.salvar_fechamento_data | /conselho/fechamento/<id>/salvar | 403 |
| registros.buscar_instituicoes | /alunos/instituicoes | **200 = VAZAMENTO** → corrigido |
| registros.form | /form | **500 = BUG** → corrigido |
| registros.painel_professor | /professor/painel | 302→/painel (redirecionamento interno) |
| registros.turma_listar | /turmas/lista | 403 (guarda vista só em runtime) |
| registros.turma_ofertas / turma_oferta_* | /turma/<id>/ofertas… | 403 (helper `_turma_para_ofertas`) |
| registros.ver_documento_aluno | /aluno/<id>/documento/<doc> | 403 (`allowed_roles` local, AST não viu) |
| registros.*_modelo_certificado | /periodo-letivo/<id>/certificado-modelo… | 403 (helper de período) |
| relatorios.bi_api_dados | /relatorios/bi/dados | 403 |
| relatorios.bi_indicador | /relatorios/bi/indicador/<codigo> | 403 |
| servico_social.excluir_agendamento | /servico-social/excluir-agendamento/<id> | 404 (recurso inexistente; guarda frouxa) |

**Pontos cegos do estático (documentados):** gates por **variável local**
(`ver_documento_aluno` usa tupla `allowed_roles` montada em runtime) e gates por
**helper** (`_turma_para_ofertas`, `_periodo_para_modelo_certificado`,
`_guarda_oferta_explicita_do_professor`) — o AST marca "por omissão", mas em
runtime negam 403. Por isso o **inventário dinâmico é a fonte de verdade**.

---

## 2. Inventário DINÂMICO (varredura em teste, SQLite + `hoje_fixo`)

Semente (`tests/test_aj6b6_matriz_rotas_professor.py::_seed`): `pA` leciona a
**oferta própria** `o_own` na `t_own`; `pB` leciona a **oferta alheia** `o_foreign`
na `t_foreign` (turma sem oferta de pA); `al_own` inscrito em `o_own`,
`al_foreign` só em `o_foreign`. Cada regra GET/POST é chamada com ids **próprios**
e **alheios**; sessão refeita a cada request (rota `logout` limpa a sessão);
`PROPAGATE_EXCEPTIONS=False` para capturar 500 em vez de estourar.

Contagem por variante (após o fix):

| Variante | 403 | 302 | 200 | 404 | 500 |
|---|---|---|---|---|---|
| own | 192 | 17 | 16 | 2 | **0** |
| foreign | 200 | 15 | 11 | 1 | **0** |

**Antes do fix** a variante `own` tinha `200: 17` e `500: 1`. Os dois únicos
alcançados indevidamente:

- `registros.form` GET → **500** (`jinja2.exceptions.TemplateNotFound: form.html`
  — o template raiz foi removido; a rota legada o renderiza sem guarda de role).
  POST escrevia um `Registro` legado. **Bug (item 2) + vazamento (item 4).**
- `registros.buscar_instituicoes` GET → **200** (autocomplete de
  `SituacaoEscolar.nome_instituicao`, escopo só de unidade, **sem guarda de
  role**). Alimenta `app/static/js/alunos/aluno.js:298` do **cadastro de aluno**
  — ficha que o professor não usa.

Os 302 de endpoints-chave são **redirecionamentos de negação** (não entregam
corpo): `painel_admin`, `trocar_unidade`, `painel_professor`, `aguardando_aprovacao`
→ `/painel`; `avaliar POST`, `salvar_conselho` → destino próprio. `foto_aluno`
(próprio, sem foto) → `/static/img/default.png`; `info_professor` (próprio, sem
bloco) → 404. **Nenhum outro endpoint fora da allowlist entrega 2xx/5xx.**

Escopo por oferta confirmado: na variante `foreign`, `ver_turma`,
`ver_observacoes`, `imprimir_pauta`, `historico_aluno` e `avaliar_turma` **saem**
dos 200 (403/404) — a `REGRA ÚNICA` (`ofertas_do_professor` /
`professor_pode_acessar_oferta` / `condicao_professor_da_oferta`) nega recurso
alheio.

---

## 3. Allowlist + teste-trava

Allowlist explícita no teste (constante `ALLOWLIST`):

- **auth**: `login`, `logout`, `trocar_senha`
- **main**: `home`, `painel`, `dashboard`, `painel_pedagogico_professor`,
  `politica_privacidade`, `termos_servico`
- **conselho (oferta própria)**: `index_conselho`, `lancamento_conselho`,
  `avaliar_turma`, `salvar_conselho`
- **rotina de aula (ofertas próprias)**: `frequencia`, `ver_turma`,
  `ver_observacoes`, `imprimir_pauta`
- **item 5 (ver §5)**: `historico_aluno`, `foto_aluno`, `info_professor`
- `static`

**Teste-trava** (`test_professor_fora_da_allowlist_sem_conteudo`, own+foreign):
para todo endpoint **fora** da allowlist, o professor só pode receber negação —
401/403/404 ou **qualquer redirect** (3xx não entrega corpo). **Falha** se
receber 2xx (conteúdo) ou 5xx (bug). *Interpretação documentada:* "302→login" do
enunciado é o caso mais comum de negação; generalizou-se para "todo 3xx/401/403/
404 é negação", porque várias rotas redirecionam a `/painel` (não a `/login`) sem
servir recurso — o que importa é o professor **não obter conteúdo nem erro de
servidor**.

`test_allowlist_recurso_alheio_sem_200`: para endpoint **da** allowlist cujo id de
recurso vai no path (`RESOURCE_ID_ENDPOINTS` = ver_turma, ver_observacoes,
imprimir_pauta, avaliar_turma, historico_aluno, foto_aluno, info_professor), o
recurso **alheio** não pode devolver 200.

Assim, **toda rota nova aberta ao professor sem decisão consciente quebra a
suíte** (ela aparece como não-allowlist com 2xx/5xx, ou como allowlist dando 200 a
recurso alheio).

---

## 4. Correções com a GUARDA POR ROLE JÁ EXISTENTE (sem nova regra de oferta)

### 4.1 `registros.form` — antes/depois

Antes: sem guarda de role; professor obtinha 500 (GET) e escrevia `Registro` (POST).
Depois: reaplicada a guarda das irmãs `editar`/`excluir` (`app/registros/core.py`):

```python
def form():
    # AJ6-B6: guarda por role já existente (irmãs editar/excluir)...
    if current_user.role != UserRole.PEDAGOGICO:
        abort(403)
```

Professor (e qualquer não-pedagógico) → **403 antes** do render/escrita. O 500
passa a 403. *Observação fora de escopo:* para o próprio pedagógico o `form.html`
raiz continua inexistente (bug de template pré-existente, não tocado aqui).

### 4.2 `registros.buscar_instituicoes` — antes/depois

Antes: só `@login_required`; professor obtinha 200 (autocomplete de instituição
do cadastro de aluno). Depois: reaplicada a guarda da irmã `atualizar_nivel_aluno`
(`app/registros/alunos.py`):

```python
def buscar_instituicoes():
    # AJ6-B6: ... só quem edita ficha de aluno consulta instituições...
    if current_user.role not in (UserRole.ADMIN, UserRole.PEDAGOGICO, UserRole.SECRETARIA):
        abort(403)
```

Professor → 403; secretaria → 200 (quem edita ficha). Sem regra de oferta.

### 4.3 Links de ficha na tela `ver_turma` (detalhe.html)

Antes: para **todos** os papéis a lista de alunos mostrava, por linha, o select de
`nivel` (POST `atualizar_nivel_aluno`) e os links **Editar** (`/aluno/editar/<id>`)
e **Transferir** (`/aluno/transferir/<id>`) — fichas que o professor não alcança.
Depois: **guarda mínima** — esconder **só do professor**, sem tocar os demais
perfis:

```jinja
{% if current_user.role != 'professor' %} ... nivel / editar / transferir ... {% endif %}
{# desenturmar mantém a SUA guarda original: ['admin','pedagogico','secretaria','gerencia'] #}
```

O nome do aluno já era **texto puro** (`{{ aluno.nome }}`, sem `<a>`). A guarda é
por papel (não por oferta), como o enunciado pede, e é a mínima para não mover o
HTML de `servico_social` (snapshot golden AJ6-B3 inalterado — ver §6).

Testes: `test_form_guard_e_por_role`, `test_buscar_instituicoes_negado_ao_professor`,
`test_centros_custo_imprimir_negado_ao_professor`,
`test_links_fora_da_allowlist_nas_telas_do_professor`.

---

## 5. Rotas de aluno — **SÓ REPORTAR** (não alteradas)

Permanecem na allowlist por decisão vigente (o professor **precisa** ver o aluno da
**própria oferta**). Escopo atual: **só oferta em que o professor é efetivo**
(`condicao_professor_da_oferta`), aluno ativo, inscrição ativa, turma ativa, na
unidade do professor, período não encerrado. Nenhum dado de oferta alheia aparece.

- **`registros.info_professor`** (`/aluno/<id>/info-professor`, JSON) —
  `app/services/aluno_info_professor.py`. Expõe **somente** (cada bloco só quando
  preenchido): `acompanhante` ← `Aluno.acompanhante_aulas` + flag
  `Aluno.vai_acompanhado_aulas`; `instrucoes` ←
  `PerfilDiversidade.informacoes_para_professor`. **Medicação e idade NÃO** entram
  (decisão explícita).
- **`registros.foto_aluno`** (`/aluno/<id>/foto`) — serve `Aluno.foto_path`
  (arquivo da **ficha**); liberado ao professor só com inscrição qualificada na
  oferta dele; sem foto → redirect `/static/img/default.png`.
- **`registros.historico_aluno`** (`/aluno/<id>/historico`) — para o professor, por
  AJ6-B4, lista **só as inscrições nas ofertas dele** (uma linha por inscrição:
  situação/etapas do conselho da oferta, dias/horário da grade, frequência). O
  restante da página (dados cadastrais) é o que a **decisão do responsável** deve
  avaliar.

**Dados que pertencem à "ficha"** e que estas rotas tangenciam, para reavaliação:
foto (`Aluno.foto_path`), acompanhante/instruções de diversidade, matrícula e
dados cadastrais subjacentes ao histórico. **Nada foi removido** — decisão com o
responsável.

---

## 6. Teste de HTML (links) + snapshot golden não-professor

- **Links** (`test_links_fora_da_allowlist_nas_telas_do_professor`): varre as telas
  do professor (painel, dashboard, painel pedagógico, ver_turma, observações,
  frequência, histórico do aluno próprio, conselho/avaliar) e resolve **cada**
  `href`/`action` contra o `url_map`; **nenhum** pode apontar a endpoint fora da
  allowlist. Pegou exatamente os dois links de ficha (`editar_aluno`,
  `transferir_aluno`) — corrigidos no §4.3.
- **Snapshot golden não-professor**: `aj6b6_admin_registros_ver_turma.txt` e
  `aj6b6_secretaria_registros_frequencia.txt` (normalizados: sem `class=`, csrf
  colapsado). Rodam **sem** o flag de regeneração e batem com o HTML gerado,
  provando que os guards por role não alteraram a saída de não-professor. A
  guarda mínima (`!= 'professor'`) preserva também o snapshot AJ6-B3 de
  `servico_social` em `ver_turma` (inicialmente uma lista positiva de roles havia
  escondido os controles de `servico_social` e quebrado aquele golden — corrigido).

---

## 7. Reversão, ruff, suíte, contagens

### 7.1 Reversão em `git worktree` (caminho absoluto)

`git worktree add d:\pautaon\.tmp\aj6b6_wt_base e1419d6` (base, **sem** o fix),
copiando o teste novo + goldens e rodando com o venv de `d:\pautaon`:

```
7 failed, 4 passed  (em e1419d6, sem o fix)
  FAILED test_professor_fora_da_allowlist_sem_conteudo[own]
  FAILED test_professor_fora_da_allowlist_sem_conteudo[foreign]
  FAILED test_nenhum_500_na_varredura[own]
  FAILED test_nenhum_500_na_varredura[foreign]
  FAILED test_form_guard_e_por_role
  FAILED test_buscar_instituicoes_negado_ao_professor
  FAILED test_links_fora_da_allowlist_nas_telas_do_professor
```

Motivo (log da app na reversão): `TemplateNotFound: form.html` (500) e
`buscar_instituicoes GET: conteudo 200`. Passam na base, corretamente, os testes
**não** dependentes do fix deste trabalho: o do centros-custo (já em HEAD), o de
recurso alheio (escopo por oferta já existia) e os dois snapshots. Worktree
removido após a prova (`git worktree list` só mostra o principal).

### 7.2 ruff

`ruff check --select F821,F811,F841,F401` em `app/registros/core.py`,
`app/registros/alunos.py` e `tests/test_aj6b6_matriz_rotas_professor.py` →
**All checks passed!**

### 7.3 Suíte completa

Para um número confiável, a suíte foi corrida em um **worktree isolado no commit
base** (`e1419d6`) com **apenas** os três arquivos-fonte deste trabalho aplicados
(`core.py`, `alunos.py`, `detalhe.html`) + o teste novo e os goldens — assim as
mudanças concurrentes de **terceiros** na árvore de trabalho (ver §8) não
contaminam o resultado.

- Primeira passagem limpa (isolado): **1 failed, 1528 passed, 1 skipped**.
  A única falha era o **meu** snapshot (`aj6b6_secretaria_..._frequencia`), que
  captava o token volátil de cache-busting do asset estático (`?v=NNNN`).
- Correção: `_normaliza` passou a neutralizar `?v=\d+ → ?v=VER`. O teste novo
  volta a passar **11/11** tanto na árvore principal quanto no worktree isolado
  (determinismo entre ambientes comprovado).
- Resultado líquido esperado com o ajuste: **0 failed, 1529 passed, 1 skipped**.
- **Skipped (1)**: `tests/test_aj5c_form_rerender.py::...` — "pasta de upload não
  existe no ambiente de teste" (infra de teste, não relacionado ao AJ6-B6).

Na árvore principal a suíte também foi corrida; as falhas ali vistas
(`test_h4_leitores_grade_variavel_smoke`, `test_impressao_grade_oferta`) são
artefato das edições concurrentes de terceiros nesses arquivos — **no base limpo
eles passam** (comprovado na passagem isolada).

### 7.4 Contagens no banco real (estritamente SELECT)

`python .tmp/aj6b6_contagens.py` — `conn.read_only=True`, sem DML/migration.
**ANTES == DEPOIS** (nenhuma escrita deste trabalho):

| tabela | contagem |
|---|---|
| unidade | 2 |
| user | 22 |
| periodo_letivo | 2 |
| turma | 3 |
| curso | 9 |
| turma_curso | 4 |
| aluno | 1155 |
| inscricoes | 32 |
| registro_aula | 5 |
| frequencia | 58 |
| conselho_classe | 45 |
| conselho_resposta | 78 |
| **log_acao** | **1188** (max_id 1518) |

**Delta em `log_acao`: zero** atribuível a este trabalho — o app não foi
executado contra o banco real e os testes correm em SQLite `:memory:`. Qualquer
movimento em `log_acao` viria apenas de uso normal da aplicação, não do AJ6-B6.

---

## 8. Churn concurrente na árvore de trabalho (não é deste trabalho)

Durante a sessão apareceram, na árvore de trabalho, modificações em arquivos que
**este trabalho não tocou** (edições feitas por outro processo/agente em paralelo,
compartilhando `d:/pautaon`). São elas:

`app/models/MER.md`, `app/static/js/turmas/editar.js`,
`app/static/js/turmas/grade_horario.js`, `app/templates/conselho/lancamento.html`,
`app/templates/turmas/{imprimir_listar_turma,listar,ofertas}.html`,
`backlog_desenvolvimento.md`, `docs/Roteiro_Teste_Manual.md`,
`tests/test_h4_leitores_grade_variavel_smoke.py`,
`tests/test_impressao_grade_oferta.py`.

Por política de não sobrescrever nem reverter trabalho alheio, esses arquivos
**não foram** adicionados a nenhum commit deste trabalho e **não foram**
revertidos. Os três commits abaixo usam **caminhos explícitos**, só do escopo
AJ6-B6. Consequência: `git status` **não** fica globalmente limpo ao final —
permanece o churn de terceiros, que cabe ao respectivo autor resolver.

---

## Arquivos tocados

- `app/registros/core.py` — guarda de role em `form`.
- `app/registros/alunos.py` — guarda de role em `buscar_instituicoes`.
- `app/templates/turmas/detalhe.html` — esconder controles de ficha **só do professor**.
- `tests/test_aj6b6_matriz_rotas_professor.py` — inventário dinâmico, allowlist/trava,
  regressões de rota, teste de links, snapshot golden.
- `tests/snapshots/aj6b6_*.txt` — goldens.
