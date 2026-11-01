# AJ5-C — Formulário de aluno unificado + re-render com os dados digitados na falha

**Etapa:** série de ajuste AJ5 (corrige o Achado 0.4 do AJ5-A — validação fazia flash + redirect e descartava tudo o que foi digitado).
**Branch:** `nova_feature` · **Base:** 1395 passed · **Sem migration, sem push, sem escrita em banco real ou storage real** (testes com `tmp_path` e `:memory:`; nenhum dado pessoal real em teste ou relatório — todos os valores são fictícios).
**Regra de ouro:** refatoração **sem mudança visual**, travada por teste de caracterização com snapshots (Etapa 1) antes de qualquer mexida (Etapa 2). Cada commit deixa a suíte verde.

Commits (empilhados, sem push): `1708112` `test(aj5c): caracterização do formulário` · `032f261` `refactor(alunos): parcial unico do formulario com contrato v e catalogos` · `1754cd2` `fix(alunos): re-render com dados digitados na falha de validacao` · `43c1af1` `fix(informacao): nao engolir 413 no salvar_informacao_padrao` · docs (este arquivo + backlog + MER).

## Etapa 0 — Leitura (somente leitura, reportada antes de codar)

### 0.1 Os dois templates old e as divergências entre eles

`novo.html` (1113 linhas) e `editar.html` (775 linhas) duplicavam os mesmos seis passos de formulário. Divergências encontradas no OLD (`1708112^`), todas eliminadas na Etapa 2:

- **Campos exclusivos de cada modo (legítimos):** `unidade_id` — só no novo, e só para usuário global sem contexto de unidade (admin de unidade recebe `unidades=[]` e o seletor some); `beneficio_social_nome` — no editar existia como `input type=hidden` por benefício salvo (servidor despejava os chips), no novo os hidden eram **criados só por JS** (`adicionarBeneficioSocial`, `aluno.js:232`) — na falha com redirect, os tags adicionados se perdiam.
- **Selects com opções digitadas à mão no `novo.html`** e lidas de catálogo Python no `editar.html` (via `{% for %}`): `escolaridade` (6), `status_escolar` (4), `tipo_instituicao` (3), `turno_escolar` (5) — no novo as `<option>` **nem `value=` tinham** (value = texto implícito). Essa é a causa raiz dos bugs do AJ5-A (listas que divergem quando alguém mexe em um dos dois).
- **Divergências de atributo** nas listas coincidentes: `selected`/`checked` marcados com Jinja de formas diferentes nos dois; no editar, o checkbox `possui_acesso_internet`/`nao_possui_acesso_internet` lia `ident.get(...)` (dict errado — nunca achava o valor salvo) enquanto o resto do bloco lia `endereco`.
- **Textos/ordens:** as listas de `acompanhante_aulas` e `ocupacao`/`raca_cor` batiam em conteúdo, quebrando só em quebra de linha do texto (inocente).

### 0.2 Os caminhos de falha nas rotas (`novo_aluno` / `editar_aluno` no OLD)

`novo_aluno` (POST) — quatro falhas com **flash + redirect**, todas perdendo o digitado:

| Validação | Flash | Para onde ia |
|-----------|-------|--------------|
| `nome` vazio | "O Campo 'Nome' não deve ser vazio no momento do Cadastro." | `redirect(gerenciar_alunos)` — nem no form voltava |
| CPF inválido (`_validar_cpf`, 11 dígitos) | "CPF inválido. Informe somente os 11 dígitos numéricos do CPF." | `redirect(novo_aluno)` |
| unidade ausente (usuário global sem `unidade_id`) | "Selecione a unidade em que o aluno será cadastrado." | `redirect(novo_aluno)` |
| unidade inválida (id não existe) | "Unidade inválida." | `redirect(novo_aluno)` |

`editar_aluno` (POST) — **não havia validação de nome** (`aluno.nome = formatar_nome_proprio(form.get("nome"))` direto dentro do `try`; nome vazio dependia do NOT NULL do banco estourar no commit); CPF inválido fazia `flash + redirect(editar_aluno)` **dentro do `try`**, estourando o rollback do `except Exception` — dados digitados perdidos de novo. **Não existe checagem de CPF duplicado** em nenhuma das duas rotas (o "duplicado" citado no prompt só aparece em `transferir_aluno`, para `Inscricao` — fora do escopo). Sucesso: PRG para `gerenciar_alunos` (novo) / flash + redirect (editar) — **inalterado** neste trabalho.

`get_perfil_completo(aluno)` devolve dict com `identificacao`, `endereco`, `responsavel_principal`, `perfil_socioeconomico`, `perfil_diversidade`, `situacao_escolar` (cada um já resolvido com fallback de colunas antigas do `Aluno`, quando existir) — é o que a rota de edição injeta no template, e o que o contrato `v` achatava.

### 0.3 Catálogos Python que já existiam vs. opções só no template

Já existiam: `TIPOS_DEFICIENCIA` (+ `TIPOS_DEFICIENCIA_EXIBICAO` derivada) em `app/services/aluno_perfil.py`, listas de UF/cidade (via API IBGE no JS, com `data-selected`). **Só no template** (digitadas uma ou duas vezes): gênero, raça/cor, tipo de responsável, acompanhante, zona, escolaridade, status escolar, período do superior (1–10), tipo de instituição, turno, residente maior renda, ocupação, benefício social status, meio de transporte, saúde medicação, programas sociais (datalist). Todos migraram para `app/services/aluno_formulario.py` na Etapa 2.

### 0.4 O JS do formulário (`aluno.js` / `aluno_utils.js`)

- **UF/cidade** (`aluno_utils.js::carregarUFs`/`carregarCidades`): preenche os selects via API do IBGE e depois lê `ufSelect.getAttribute('data-selected')` → `select.value = salva` + `dispatchEvent('change')` (que dispara `carregarCidades`); cidade repete com o próprio `data-selected`. Basta o template marcar `data-selected="{{ v.natural_uf }}"` para a re-hidratação funcionar — preservado, inclusive na falha re-renderizada.
- **`toggleSituacaoEscolar()`**: mostra/esconde blocos condicionais (ex.: período do superior quando escolaridade = "Ensino superior"); chamado na carga (`aluno.js:403`) — select re-selecionado no servidor já liga o bloco certo.
- **`toggleAcompanhanteAulas(checkbox)`**: habilita o select `acompanhante_aulas` (com opção "Outro" → campo de texto livre); chamado na carga (`aluno.js:376`) com o estado do checkbox — preservado.
- **`goToStep(n)`** (`aluno.js:82`): global e utilizável na carga — `if (n === currentStep || !stepIds.includes(n)) return;` entretanto **não roda validação quando `n <= currentStep`**; como `currentStep` inicia em 1, `goToStep(1)` é no-op (já está no passo 1). Todas as falhas implementadas (nome/CPF/unidade) pertencem ao passo 1, então a casca só emite o script de salto para `passo_erro != 1` — mecanismo genérico pronto para falhas futuras em outros passos.

## Etapa 1 — Trava de caracterização (commit `1708112`, ANTES da refatoração)

`tests/test_aj5c_form_caracterizacao.py` — **3 snapshots** canonizados em `tests/snapshots/`:

- `aj5c_novo_com_unidades.txt` (novo para usuário global, com seletor de unidade);
- `aj5c_novo_sem_unidades.txt` (novo para admin de unidade);
- `aj5c_editar_completo.txt` (aluno fictício semeado com **todos os blocos**: identificação com 3 benefícios em `beneficio_social_nome` separado por `|`, acompanhante "Outro" com texto livre, laudo + tipo de deficiência, responsável, situação escolar, documentos entregues).

Canonizador (parser stdlib, sem dependência nova): ordena atributos por nome, colapsa whitespace, descarta atributo vazio (exceto `option value=""` — placeholder legítimo), normaliza `style` (`a:b` ≡ `a: b`, partes `;`-joinadas), remove o `input[name=csrf_token]` e scrubba o `<meta name="csrf-token">`, normaliza matrícula `#NNNNN.AAAA` → `#MATRICULA`, ignora comentários. Verde no HEAD da época; regeneração controlada por `AJ5C_ATUALIZAR_SNAPSHOTS=1` (o modo de despejo temporário usado para depurar o diff foi **removido antes do commit**).

## Etapa 2 — Unificação (commit `032f261`)

- **`app/templates/alunos/_form_aluno.html`** (672 linhas): os seis passos num arquivo só, parametrizado por `modo` (`'novo'|'editar'`). `novo.html` (1113→71) e `editar.html` (775→70) viraram cascas finas: cabeçalho, botões, modal da webcam e `{% include %}` do parcial. ~1075 linhas de template duplicado eliminadas.
- **Contrato único `v`**: `valores_form_aluno(aluno=None, perfil=None, form=None, foto_url=None)` em `app/services/aluno_formulario.py` (357 linhas) devolve um valor por nome de campo com precedência **`form` (dados digitados, na falha) > banco (editar) > padrões do cadastro novo** (`_PADROES`: nacionalidade Brasileira, UF SP, zona Urbana, pessoas_residencia 1, situação "Cursando"… — as defaults históricas do `novo.html`). O template **só lê `v`** — zero `ident.get(...)`/`request.form.get(...)` solto. O achatamento do banco (`_banco_de`) replica a semântica EXATA dos templates old (incl. `end.get('uf','SP')` e `ident.get('nacionalidade','')`).
- **Catálogos únicos**: todos os selects renderizam `{% for %}` sobre `cat.<campo>` (`catalogos_formulario()`); nenhum `<option>` digitado à mão. `TIPOS_DEFICIENCIA_EXIBICAO` tem `assert` de equivalência com o catálogo canônico de `aluno_perfil`.
- **Preservado**: `data-selected` de UF/cidade; acompanhante "Outro" com texto livre reidratado (select + campo); tags de benefício social agora **também no novo** em re-render (hidden por chip vindo de `v`); `has_laudo`/`tipo_deficiencia` habilitado; botões Ver/Excluir + forms ocultos de exclusão **só em `modo == 'editar'`** (e com a guarda de role do old via `pode_doc`); seletor de unidade só em `novo` com `unidades` não vazia.
- **Escape**: todo valor digitado entra por `{{ }}` (autoescape Jinja) — teste dedicado com `"><script>x</script>` na Etapa 3.
- **Detalhe de render não óbvio**: o `selected` é emitido como expressão inline `{{ " selected" if opcao == v.campo }}` — as variantes `{% if %}` deixavam espaço órfão antes de `>` (quebravam o parser do teste AJ5-A `test_novo_oferece_nao_se_aplica_com_valor_proprio`) ou colavam o atributo. Mesmo tratamento para `checked`/`disabled` onde o old batia literal.

### Diferenças de caracterização após a refatoração (aprováveis, listadas uma a uma)

Diff canônico novo×snapshot no estado final da Etapa 2: **118 linhas**, em 4 famílias — zero mudança visual real:

1. **Novo — 41 linhas**: `<option>` de `escolaridade`/`status_escolar`/`tipo_instituicao`/`turno_escolar` ganham `value=` explícito (o old não tinha; o value implícito era idêntico ao texto — POST inalterado).
2. **Novo — 12 linhas**: `selected` explícito nas defaults dos selects sem placeholder (gênero etc.) — visualmente já estavam selecionados (primeira opção); agora marcado no HTML.
3. **Editar — 5 pares**: datalist de programas sociais passa a fechar `</option>` (o old omitia o fechamento; HTML válido idêntico ao parsear).
4. **Editar — 1 par**: checkbox de internet passa a ler `endereco.possui_acesso_internet` (o old lia `ident.get(...)` — **bug real**: o valor salvo nunca reidratava no editar). Único caso de diferença com comportamento corrigido, a pedido na auditoria da Etapa 0.

Os snapshots foram regenerados no código novo (trava para o futuro: daqui em diante o diff tem que ser **vazio**). Suíte após a Etapa 2: **1398 passed, 0 failed**.

## Etapa 3 — Re-render na falha (commit `1754cd2`; testes primeiro)

`tests/test_aj5c_form_rerender.py` — **10 testes** (fixtures próprias com `tmp_path`/`:memory:`, CPF/emails fictícios):

- falha de nome vazio no novo → status 200, selects/checkboxes/unidade escolhida/acompanhante "Outro"+texto/benefício em tag **voltam preenchidos**, passo 1 aberto, flash presente, **nenhum aluno criado**;
- CPF inválido → nome digitado volta; unidade ausente (global) → tudo volta com a unidade escolhida marcada;
- POST trazendo foto → flash **"Reanexe a foto/os documentos"**;
- valores com `"><script>x</script>` → escapado, sem `<script>` executável no HTML;
- falha não grava arquivo em disco (contagem da pasta de upload inalterada) nem no banco;
- editar com CPF inválido → digitado volta e **banco inalterado** (nome no banco é o antigo);
- sucesso continua **redirect** nos dois modos (PRG intacto);
- **paridade de `name=`** entre o HTML do novo e do editar (parser; lista permitida **vazia** — conjuntos idênticos hoje; admin de unidade para o seletor `unidade_id` não interferir).

Rotas: helper `_render_form_aluno_com_dados(aluno, template, unidades, passo_erro)` constrói `v` de `request.form`, detecta anexos em `request.files` (foto + `doc_*` com filename) para o flash de reanexar, e renderiza com status 200. As 4 falhas de `novo_aluno` e as de nome/CPF de `editar_aluno` (movidas para **antes** do `try`, mesma regra, mesma ordem de validação) passaram a usar o helper; `unidades_postra` recalcula no topo do POST com a mesma regra do GET. **Nenhuma permissão, escopo de unidade ou regra de validação mudou; nada é gravado em banco ou disco na falha** (provado por teste). Cascas abrem o passo do erro via `goToStep(passo_erro)` quando `passo_erro != 1` (hoje todos os erros estão no passo 1, que já abre sozinho na carga).

## Etapa 3b — `informacao_padrao` não engolir 413 (commit `43c1af1`)

`salvar_informacao_padrao` tinha o mesmo `except Exception` amplo que escondia o 413 do AJ5-B. Fix: `except HTTPException: raise` antes do `except ValueError` (mesma receita das rotas de aluno). Teste novo `tests/test_aj5c_informacao_413.py` (1): `MAX_CONTENT_LENGTH` rebaixado para 1 MB no app de teste, POST de logo de 2 MB → flash amigável do handler global ("Envio recusado… 1 MB"), **sem** a genérica "Não foi possivel salvar…", nada gravado. Commit separado por pedido.

## Etapa 4 — Provas e verificação

**Sondas de reversão em `git worktree` com caminho absoluto** (guarda `git status --porcelain` antes de cada checkout; mutações só dentro do worktree; removidos ao final):

| Sonda | Mutação | Resultado |
|-------|---------|-----------|
| P1 — sem o fix das rotas | worktree em `43c1af1` com `app/registros/alunos.py` + cascas revertidos a `032f261` (contrato `v` fica, re-render não); testes novos preservados | **6 failed** exatamente os de re-render (nome vazio, CPF, unidade, reanexar, escape, editar) · 3 passed (PRG sucesso ×2 + paridade) · 1 skipped (disco — sem pasta de upload no worktree) — `.tmp/aj5c_p1_sonda.txt` |
| P2 — sem o contrato `v` | worktree em `43c1af1` com templates+rotas pré-E2 (`1708112`) e `aluno_formulario.py`/`_form_aluno.html` removidos | **3 failed** — todos os snapshots de caracterização (novo com/sem unidades, editar completo) · paridade passa (os `name=` já batiam no old; a trava do contrato é a caracterização) — `.tmp/aj5c_p2_sonda.txt` |

**Suíte completa:** **1409 passed, 0 failed** em 24m11s (evidência `.tmp/aj5c_suite_final.txt`). Aritmética: 1395 (base AJ5-B) + 3 (caracterização, E1) + 10 (rerender/paridade, E3) + 1 (413, E3b). `ruff check --select F821,F811,F841 app tests scripts migrations` → All checks passed!

**Higiene:** `git worktree list` só com o principal; `git status` limpo (exceto os prompts não rastreados de sempre); **nenhum push**; nenhuma migration; bancos reais intocados.

## Pendências (fora do escopo AJ5-C)

- **AJ5-D:** assinatura de conteúdo/headers nos uploads de **atendimento** (anexo 2 MB sem magic bytes) e **modelo de certificado** (docx/odt sem assinatura).
- Decisão de layout do formulário: (a) manter seis passos, (b) reduzir, (c) página única com âncoras — a refatoração deixou uma fonte só para qualquer opção.
- **Achado 0.2** (AJ5-A): visibilidade de professor/laudo — aguarda decisão de produto.
- `beneficio_social_nome` no novo ainda depende de JS para materializar os hidden no POST puro (novo sem falha); com re-render agora haveria como server-side, se quiser unificar de vez.
