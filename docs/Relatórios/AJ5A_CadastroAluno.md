# AJ5-A — Cadastro de aluno: correções de dados + exclusão de documento entregue

Data: 01/11/2026. Branch `nova_feature`, base `ea7d0e2` (AJ4-B). Regras: sem
migration, sem push, sem escrita em banco real nem no storage real (testes usam
`tmp_path`); reversão apenas em `git worktree` com `git status --porcelain` antes
de cada checkout. Nenhum CPF/e-mail/IP/hash/nome real de aluno neste arquivo.

## Etapa 0 — Auditoria (somente leitura)

### 0.1 `salvar_documento` (`app/registros/shared.py:86`)

- **Onde grava:** `UPLOAD_FOLDER` (fallback `instance/uploads`) `/documentos/<matricula|aluno_<id>>/` — **fora de `static`** desde a SEC-01 (entrega só por rota autenticada). ✓
- **Nome do arquivo:** gerado pelo servidor — `secure_filename(f"{doc_id}.pdf")` com `doc_id` já validado contra `DOC_IDS` pelo chamador; nada do `filename` do cliente chega ao disco. A pasta passa por `_build_upload_path` (resolve + checagem de prefixo). **Sem path traversal.** ✓ (A checagem `startswith` é de string e não de path parts — residual teórico, sem vetor prático porque nenhum segmento vem do cliente.)
- **Validação real:** **só a extensão `.pdf`**. Sem checagem de mimetype, **sem magic bytes `%PDF`**, **sem limite de tamanho no servidor**. O "Somente arquivos PDF de no máximo 2MB" é texto dos templates e `accept=".pdf"` é sugestão de UI — nenhum dos dois é imposto. Um POST direto grava um `.pdf` de 500 MB ou um `.exe` renomeado (não existe `MAX_CONTENT_LENGTH` global no config — grep zero). Comparável ao que o S1-08 corrigiu para **foto** (whitelist + assinatura + 2 MB) — para documentos continua aberto (**AJ5-B**).

### 0.2 Rota de visualização/entrega

**Existe**: `GET /aluno/<int:aluno_id>/documento/<doc_id>` (`ver_documento_aluno`, `app/registros/alunos.py:1271`): `@login_required`, roles `ADMIN/PEDAGOGICO/SECRETARIA/GERENCIA/SERVICO_SOCIAL`, `doc_id` fora de `DOC_IDS` → 404, `assert_unidade_context` (unidade do aluno × contexto; mismatch/sem contexto → 403), serve com mimetype fixo `application/pdf` (`as_attachment=False`). **Professor não tem acesso** (a rota de foto tem regra própria por oferta; a de documento, não). Como a rota existe, o botão "Ver" foi ligado a ela no editar.html; **não criei rota nova de visualização** (por instrução).

### 0.3 Consumidores do flag

```
app/models/pessoas.py:252  documentos_dict()      # acessor (JSONB → fallback escolaridade_json)
app/models/pessoas.py:268  documento_entregue(id) # helper booleano (nenhum chamado em app/ hoje)
templates/alunos/gerenciar.html:224  # listagem: ícone entregue/pendente por documento
templates/alunos/impressao.html:181  # ficha impressa: mesma marcação
templates/alunos/editar.html:14,454,629  # estado dos boxes (has-file)
```

Nenhum consumo em pauta, relatórios ou BI (grep `doc_entregue|documentos_dict|documentos_entregues` em `app/**.py`: só os acima + a escrita em `alunos.py` e um comentário em `servico_social.py:281`). **Quando um flag passa a `False`**: a listagem e a impressão mostram o documento como não entregue e o box do editar perde o estado `has-file`/check — **nenhum cálculo, filtro ou bloqueio** depende hoje do flag. É dado de Painel/Serviço Social, não de regra de negócio.

### 0.4 Re-render na validação (Achado 4)

Não re-renderiza com os dados do form — **perde tudo**:

- POST `novo_aluno`: `nome` vazio → flash + redirect para `gerenciar_alunos` (`alunos.py:458-463`); CPF inválido → flash + redirect para `novo_aluno` (`:466-471`) e o GET seguinte renderiza o form **em branco**;
- POST `editar_aluno`: CPF inválido → flash + redirect para `editar_aluno` (`:613-618`) — recarrega do banco e **descarta a edição em andamento**.

Prova (teste exploratório, executado e **não commitado**): POST com nome/e-mail/whatsapp preenchidos + CPF repetido → 302 para `/aluno/novo`; no follow, nenhum dos valores digitados aparece no HTML e só resta o flash. Evidência: `.tmp/aj5_e04_probe.txt`. **Não implementei correção** — decisão de UX pendente (re-render com `request.form` vs. persistência de rascunho).

## Etapa 1 — Correções de dados (commit `48f8199`)

| # | Defeito | Correção |
|---|---------|----------|
| a | `novo.html`: opção "Não se aplica" com `value="Motora/Física"` | `value="Não se aplica"` + catálogo `TIPOS_DEFICIENCIA` aceita o valor (editar.html já o oferecia e o POST **quebrava** na validação — ValueError → rollback do cadastro inteiro) |
| b | `editar.html`: `tipo_def=='Outra'` (valor que o catálogo nunca grava) | comparação com `'Outro'` |
| c | `editar.html`: acompanhante livre (coluna guarda o texto, não 'Outro') perdia o round-trip | valor fora da lista fixa → `Outro` selecionado, `acompanhante_aulas_outro` pré-preenchido, div visível na carga; `toggleOutroAcompanhante` do aluno.js já mostra o div na carga quando o select vem 'Outro' (linha 377) — conferido, sem mudança no JS |

Testes: `tests/test_aj5_cadastro_aluno_form.py` (6). Linha de base antes do fix: 4 falhas (`novo_oferece`, `persiste`, `editar_seleciona_outro`, `editar_mostra_outro`); depois: 6 passed (`roundtrip` e `canonico` são não-regressão) — `.tmp/aj5_e1_antes.txt` / `.tmp/aj5_e1_depois.txt`.

## Etapa 2 — Exclusão de documento entregue (commits `81826ed` + `7de48d9`)

- **Rota** `POST /alunos/<aluno_id>/documentos/<doc_id>/excluir` (`excluir_documento_aluno`, `registros/alunos.py`): mesmas roles da edição de aluno (admin/pedagógico/secretaria); `doc_id` fora de `DOC_IDS` → 404 **antes** de tocar banco/disco; aluno inexistente → 404; **aluno de outra unidade → 404** (não vaza existência — checagem explícita antes do helper, que continua 403 para operador sem contexto/aluno sem unidade); GET → 405; anônimo → redirect de login.
- **Efeito:** remove o arquivo do storage com a mesma resolução de pastas do `ver_documento_aluno` (matrícula → `aluno_<id>` → `sem_matricula`), idempotente (arquivo ausente não é erro); `entregues[doc_id] = False` preservando as demais chaves e **reatribuindo um dict novo** em `aluno.documentos_entregues` (mutação in-place de JSONB não é detectada pelo SQLAlchemy); commit com rollback em falha; flash. **`doc_laudo` excluído não toca `saude_laudo`** (testado).
- **Auditoria:** `log_acao` `acao="Excluir documento"` via `register_security_log`, `detalhes="aluno_id=N doc_id=... user_id=N"` — sem nome de arquivo nem dado pessoal. Categoria `exclusao` (prefixo "excluir" já cobre em `_CATEGORIAS_ACAO`).
- **Drift AJ4-A:** com a rota no código e antes do registro, `test_rotulo_novo_do_codigo_falha` falhou exatamente como projetado (`rótulo novo sem classificação consciente: ['Excluir documento']`, local `app/registros/alunos.py:1379`; `.tmp/aj5_drift_falha.txt`). Registro no commit `7de48d9`: `CATEGORIA_ESPERADA["Excluir documento"]="exclusao"` + `ROTULOS_SEM_LINHA` 7→8; arquivo passa de 54 para **56** parâmetros (2 novos parametrizados: classificação + emissor).
- **Template editar.html:** nos 6 boxes + laudo, quando `has-file` **e** role apta: "Ver" (link à rota da Etapa 0.2) + "Excluir" (botão `type="submit"` com `form="form-excluir-<doc_id>"`); os `<form>` ocultos ficam **fora** do `multiStepForm` (form aninhado é inválido) e cada um carrega o token CSRF e `onsubmit="return confirm(...)"`; o wrapper leva `onclick="event.stopPropagation()"` porque o box inteiro abre o seletor de arquivo. `novo.html` não mudou.

Testes: `tests/test_aj5_documento_excluir.py` (12) — sucesso (arquivo some, flag False, demais chaves preservadas, log com categoria `exclusao` e sem dado pessoal), `doc_id` inválido 404, outra unidade 404, professor 403, gerencia 403, anônimo redirect, GET 405, idempotência (2×), `saude_laudo` intacto, HTML do editar com botão só com arquivo (e form fora do `multiStepForm`, com `stopPropagation`, com `confirm`, com link Ver), reupload volta a flag. Storage dos testes: `tmp_path` (nada no storage real).

## Provas de reversão (worktree `--detach`, guardas `git status --porcelain` antes de cada checkout)

| Sonda | Reversão | Resultado |
|-------|----------|-----------|
| A | `novo.html` → `ea7d0e2` | 1 failed: `test_novo_oferece_nao_se_aplica` ✓ |
| D | `aluno_perfil.py` → `ea7d0e2` (catálogo) | 1 failed: `test_tipo_nao_se_aplica_persiste` ✓ |
| B/C | `editar.html` → `ea7d0e2` | 2 failed: `editar_seleciona_outro` + `editar_mostra_outro` ✓ |
| Rota | em `81826ed`: `alunos.py` + `editar.html` → `48f8199` (sem rota/template) | **10 failed, 2 passed** (os 2 são os 404 que batem por acaso com a rota ausente) ✓ |
| Dict | em `81826ed`: removi a reatribuição `aluno.documentos_entregues = docs` | **4 failed** (flag não persiste: sucesso, laudo, reupload, idempotência) ✓ |

Evidências: `.tmp/aj5_probe_a.txt`, `_d.txt`, `_bc.txt`, `_rota.txt`, `_dict.txt`. Worktree removido ao final (`git worktree list` só com o principal).

## Verificação final

- Suíte completa: **1382 passed, 0 failed** em 434.11s (`.tmp/aj5_suite.txt`) — 1362 da base AJ4-B + 6 (Etapa 1) + 12 (Etapa 2) + 2 (parâmetros novos do drift).
- `ruff check --select F821,F811,F841 app tests scripts migrations`: sem achados.
- `git status`: apenas os prompts untracked em `docs/prompts/`; nenhum banco real tocado; sem push; sem migration.

## Commits

| Hash | Descrição |
|------|-----------|
| `48f8199` | `fix(alunos): valores corretos de tipo de deficiência e acompanhante` (+ teste da Etapa 1) |
| `81826ed` | `feat(alunos): excluir documento entregue` (rota + template + teste; emite o rótulo novo) |
| `7de48d9` | `test(aj4): registra o rótulo "Excluir documento"` |
| (este) | `docs(aj5a): relatório` |

Observação honesta: entre `81826ed` e `7de48d9` a árvore tem o teste de drift vermelho (o enunciado pediu o registro em commit separado, após mostrar a falha).

## Pendências

- **AJ5-B (validação de upload de documento):** magic bytes `%PDF` + mimetype + limite de 2 MB no servidor em `salvar_documento` (padrão S1-08 da foto); hoje só a extensão é checada.
- **Achado 0.4:** perda total do form na validação de CPF (decisão de UX: re-render com `request.form` ou rascunho).
- **Achado 0.2:** `ver_documento_aluno` não tem regra para professor nem checagem de vínculo além da unidade — decisão de produto sobre o laudo (dado de saúde).
- Anteriores: ajuste 4 (Resumo), Central de BI; `cryptography`/`oauthlib` (§12.29).

## Procedimento de reprodução

```powershell
# testes novos
.venv\Scripts\python.exe -m pytest tests/test_aj5_cadastro_aluno_form.py tests/test_aj5_documento_excluir.py -q
# drift (56)
.venv\Scripts\python.exe -m pytest tests/test_aj4_logs_drift.py -q
# sondas: git worktree add --detach .tmp/aj5_wt <commit>; checkout do(s) arquivo(s) do pai; rodar; git worktree remove --force
```
