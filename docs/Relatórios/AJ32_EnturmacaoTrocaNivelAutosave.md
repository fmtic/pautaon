# AJ32 — Enturmação: troca de nível do aluno sem recarregar (autosave)

**Data:** 27/11/2026 · **Branch:** `nova_feature` · **Migration:** nenhuma (sem alteração de schema) · **Commit/push/merge/deploy:** não realizados.

## 1. Escopo e restrições

- **Incluído:** autosave da troca de nível do aluno na ficha da turma (`/turma/<id>`), endpoint AJAX/JSON com fallback sem JS, indicadores por linha, testes, documentação.
- **Não incluído:** mudança de regra de negócio, migration/schema, deploy/scripts de deploy/wsgi/.env, recarregamentos escondidos.
- **LogAcao/AJ4:** o endpoint `POST /aluno/<aluno_id>/atualizar-nivel` **não registrava `LogAcao` antes** e **continua sem registrar**. Não havia rótulo congelado da AJ4 para esse endpoint; nenhuma alteração de auditoria foi introduzida.

## 1.1 AJ32-B — correção do loop infinito (bug crítico)

**Sintoma reportado:** ao trocar nível, o navegador disparava POSTs em sequência infinita para `/aluno/<id>/atualizar-nivel` (todos 200) e o nível não persistia visualmente/confiavelmente.

**Causa raiz:**
- O JS confirmava sucesso usando fallback para o valor enviado (`valorServidor !== undefined ? valorServidor : valor`) e, após sucesso, reaplicava `select.value` com o valor do servidor. Quando o valor devolvido não casava exatamente com o valor selecionado no DOM (normalização/canonicalização, espaço/casefold, ou cenário de valor sanitizado/recusado), o `change`/estado divergente fazia a fila reenfileirar.
- O `finalizar` marcava confirmado como o valor enviado mesmo sem prova forte do servidor, e não havia limite de tentativas nem guarda contra divergência persistente.
- No servidor, valor fora do catálogo da oferta era sanitizado para `None` e ainda respondia `ok:true` com `nivel_valor="Não se aplica"`, o que mascarava recusa e podia conflitar com a intenção do usuário.

**Correção:**
- **JS (`app/static/js/turmas/nivel_autosave.js`):** normalização única `normalizarValor` (trim, `null/undefined` → `""`); confirmado só avança com `nivel_valor/nivel_nome` do servidor em sucesso; se o servidor apenas canonicaliza espaço/caixa, o select é alinhado ao valor canônico e o indicador vai para `✓ Salvo` (sem erro e sem reenvio); reenvio somente se `ultimo` mudou após envio (`analisarSucesso`/`deveReenfileirar`); máx. 1 request em voo por linha; erro não gera retry automático (somente nova alteração do usuário) e o limite `MAX_TENTATIVAS=3` barra divergências/tentativas repetidas; ao exceder, para, reverte ao último confirmado e mostra erro claro. `change` só agenda; valor igual ao confirmado não agenda.
- **Servidor (`app/registros/alunos.py`):** normalização única trim/casefold; aceita canônico do catálogo e preserva AJ22-F (reenviar valor atual legado não apaga/não erra); valor fora do catálogo da oferta em requisição AJAX retorna **422** `ok:false` com mensagem clara em PT e `nivel_valor` confirmado, sem gravar; fallback form sem JS redireciona com warning sem gravar. Idempotência mantida.

**Por que o teste anterior não pegou:** os testes AJ32 cobriam fila pura e contrato básico do endpoint, mas não simulavam o ciclo DOM+fetch onde a resposta do servidor difere por normalização/canonicalização e dispara reenvio; também não havia teste de contagem de POSTs no navegador nem caso de nível fora do catálogo retornando erro explícito. AJ32-B adicionou regressões JS puras (normalização, limite de tentativas, reenfileira só com mudança do usuário), testes de servidor (422 fora catálogo, casefold/trim, legado reenviado, vazio) e verificação Playwright com contagem de requisições.

## 2. Descoberta e inventário de efeitos colaterais

### 2.1 Tela e endpoint

| Item | Local | Observação |
|---|---|---|
| Tela enturmação/ficha | `app/templates/turmas/detalhe.html` | select de nível por aluno/oferta no card da oferta; `onchange="this.form.submit()"` antes da AJ32. |
| Endpoint | `app/registros/alunos.py` (`atualizar_nivel_aluno`, `POST /aluno/<aluno_id>/atualizar-nivel`) | recebia `nivel`, `turma_id`, `turma_curso_id`; validava role, sanitizava nível pelo curso da oferta, aceitava valor atual "(atual)" (AJ22-F), gravava `aluno.nivel` e `inscricao.nivel`, redirect + flash. |
| Níveis por oferta | `app/registros/turmas.py` (`ver_turma`) | `niveis_por_curso_id` com níveis ativos da unidade/global do curso; template renderiza opções. |

### 2.2 Regras/efeitos colaterais inventariados

| Efeito | Status AJ32 | Detalhe |
|---|---|---|
| Validação de vínculo curso↔nível | **Mantido** | nível novo só aceito se ativo no curso da oferta e unidade/global; senão sanitiza para `None` como antes (fallback). |
| Valor atual "(atual)" texto livre/legado/outro curso | **Mantido** | AJ22-F preservado: reenviar o valor atual não apaga; valor novo fora do catálogo do curso segue sanitizado. |
| Gravação em `Inscricao.nivel` e `Aluno.nivel` | **Mantido** | mesma atribuição; sem campos extras. |
| Permissão | **Mantido** | `admin`, `pedagogico`, `secretaria`; professor 403. |
| Isolamento por unidade | **Mantido** | AJAX recusa aluno/oferta de outra unidade/contexto com 404 JSON; fallback mantém comportamento de app. |
| CSRF | **Mantido** | Flask-WTF; form mantém token; AJAX envia `X-CSRFToken` do `<meta name="csrf-token">`. |
| LogAcao | **Mantido (ausente)** | endpoint não gerava log antes; não foi criado. |
| Mensagens/redirect | **Mantido no fallback** | POST normal continua redirect para turma + flash sucesso. |
| Filtros/busca/ordenação/rolagem/linha aberta | **Preservados** | sem reload; atualização local só do select/status da linha. |
| Contadores/agrupamentos dependentes do nível | **Não aplicável na tela** | a ficha exibe o nível por linha; não há contador/agregação por nível a recalcular no detalhe da turma. |
| Conflito com turma atual | **Não aplicável** | endpoint altera nível, não enturma/desenturma. |

### 2.3 Reuso do conselho

Reaproveitado do padrão de `app/static/js/conselho/autosave.js` e `fechamento.html`:

- debounce 300 ms;
- fila por linha (um envio em voo + último estado pendente; última alteração vence);
- indicador discreto por linha com estados salvando/salvo/erro;
- `beforeunload` com pendência/erro;
- funções puras testáveis em node (módulo exportado) sem DOM/timers/rede;
- CSRF por `X-CSRFToken` e JSON.

**Não extraí núcleo compartilhado** entre conselho e turma. Motivo: o autosave do conselho salva payload completo da linha (situação/curso/nível), tem semântica própria de `situacao_indefinida`, renderização de impressão e contratos já cobertos por AJ30; extrair agora exigiria refatorar JS/HTML/testes do conselho com risco de regressão. O custo de duplicação é pequeno e isolado; o padrão foi replicado com nomes/contrato do domínio de nível. Registrado aqui conforme instrução.

## 3. Contrato do endpoint

`POST /aluno/<aluno_id>/atualizar-nivel`

### Requisição

- **Fallback form:** `nivel`, `turma_id`, `turma_curso_id`, `csrf_token`.
- **AJAX/JSON:** mesmos campos em JSON; detectado por `request.is_json`, `Accept: application/json` ou `X-Requested-With: XMLHttpRequest`.

### Resposta AJAX sucesso (200)

```json
{
  "ok": true,
  "nivel_id": null,
  "nivel_nome": "Avancado",
  "nivel_valor": "Avancado",
  "message": "Nível do aluno ... atualizado com sucesso!",
  "mensagem": "Nível do aluno ... atualizado com sucesso!",
  "aluno_id": 123,
  "turma_curso_id": 45
}
```

Observação: `nivel_id` é `null` porque `Inscricao.nivel`/`Aluno.nivel` são texto livre (sem FK); o contrato inclui o campo pedido e também `nivel_valor`/`nivel_nome` para a UI.

### Erros AJAX

| Status | Quando | Corpo |
|---:|---|---|
| 400 | oferta inválida/turma_curso ausente em AJAX | `{"ok":false,"message":"...","mensagem":"..."}` |
| 403 | role sem permissão | `{"ok":false,"message":"Permissão negada."}` |
| 404 | aluno/oferta fora da unidade/contexto, inscrição ativa inexistente para oferta | `{"ok":false,"message":"..."}` |
| 422 | nível fora do catálogo da oferta (AJ32-B) | `{"ok":false,"message":"Nível inválido para o curso desta oferta. Selecione um nível disponível.","nivel_valor":"..."}` |
| 500 | falha inesperada de gravação | `{"ok":false,"message":"Erro ao salvar o nível. Tente novamente."}` |

### Fallback sem JS

- Sucesso: redirect para `ver_turma` (ou gerenciar alunos sem turma_id) + flash `success`.
- Erro: redirect/flash conforme fluxo antigo; permissões seguem `abort(403)` quando não-AJAX.

### Idempotência e concorrência

- Mesmo nível efetivo reenviado: retorna 200/ok sem alterar estado.
- Concorrência/duas trocas rápidas na mesma linha: fila JS mantém último estado pendente; servidor processa requisições na ordem recebida e o último valor enviado vence. A UI reverte ao valor confirmado em erro.

## 4. Alterações de código

- `app/registros/alunos.py`: helpers AJAX/fallback; `atualizar_nivel_aluno` com JSON, idempotência, validação/isolamento/permissão preservados; AJ32-B 422 para nível fora do catálogo, normalização única e AJ22-F preservada.
- `app/templates/turmas/detalhe.html`: wrapper de autosave, remoção do submit inline, status `aria-live`, inclusão do JS.
- `app/static/js/turmas/nivel_autosave.js`: autosave por linha (debounce/fila/reversão/beforeunload) + funções puras exportadas; AJ32-B normalização, limite de tentativas e reenvio só após mudança real do usuário.
- `tests/test_aj32_enturmacao_nivel_autosave.py`: contrato servidor + AJ32-B (422, trim/casefold, legado reenviado, vazio).
- `tests/test_aj32_nivel_autosave_js.py`: contrato JS puro + regressões AJ32-B (loop, 1 POST por alteração, limite de tentativas).
- `tests/test_aj22e_nivel_enturmar.py`, `tests/test_aj22f_nivel_aluno_enturmado.py`: ajuste de expectativa para rejeição sem gravar (AJ32-B), preservando AJ22-F.
- `tests/snapshots/aj6b6_admin_registros_ver_turma.txt`: atualizado pelo novo markup esperado da ficha.

## 5. Testes

### Executados

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_aj22e_nivel_enturmar.py tests/test_aj22f_nivel_aluno_enturmado.py tests/test_aj6b6_matriz_rotas_professor.py -q
# 1 failed (snapshot esperado), 30 passed, 84 warnings

$env:AJ6B6_ATUALIZAR_SNAPSHOTS='1'; .\.venv\Scripts\python.exe -m pytest tests/test_aj6b6_matriz_rotas_professor.py::test_snapshot_nao_professor_inalterado[admin-registros.ver_turma] -q
# 1 passed, 2 warnings

.\.venv\Scripts\python.exe -m pytest tests/test_aj32_nivel_autosave_js.py tests/test_aj22e_nivel_enturmar.py tests/test_aj22f_nivel_aluno_enturmado.py tests/test_aj6b6_matriz_rotas_professor.py::test_snapshot_nao_professor_inalterado[admin-registros.ver_turma] -q
# 25 passed, 57 warnings

.\.venv\Scripts\python.exe -m pytest tests/test_aj32_enturmacao_nivel_autosave.py -q
# 9 passed

.\.venv\Scripts\python.exe -m pytest tests/test_aj30_situacao_final.py tests/test_aj30_autosave_js.py -q
# 20 passed, 17 warnings

.\.venv\Scripts\python.exe -m pytest -q
# ver resultado final no registro abaixo
```

### Cobertura adicionada

- Servidor: sucesso JSON; idempotência; 400 oferta inválida; 404 inscrição inexistente; 403 sem permissão; isolamento por unidade; fallback form sem JS (redirect + flash); CSRF ausente com CSRF habilitado bloqueia; não altera outros campos do aluno/inscrição.
- Servidor AJ32-B: nível fora do catálogo → 422 sem gravar; trim/casefold aceita valor canônico; valor legado reenviado → ok sem alterar; `""` normalizado para "Não se aplica".
- JS puro: fila por linha, última alteração vence, outra linha não bloqueada, reversão ao valor confirmado, mensagens de erro, payload/tempos/estados.
- JS puro AJ32-B: normalização/trim igual ao confirmado não agenda; resposta com espaços/caixa diferentes canonicaliza sem erro nem reenvio; mudança do usuário durante envio reenfileira uma vez; servidor que não honra a mudança para após 3 divergências e reverte; `finalizar` sem valor confirmado preserva a última intenção.

## 6. Verificação real (Chromium/Playwright)

Executada em app Flask local temporário (SQLite descartável, seed com 2 alunos enturmados na mesma oferta), Chromium headless via Playwright 1.52.0 + browser local `chromium-1243` (`C:\Users\FMtic\AppData\Local\ms-playwright\chromium-1243\chrome-win64\chrome.exe`). Evidências em `docs/Relatórios/aj32_evidencias/` (não versionadas por `.gitignore`).

| Cenário | Evidência | Resultado |
|---|---|---|
| Ficha da turma / select de nível visível | `01_ficha_turma.png` | OK. Select por linha, sem botão salvar, texto "Salvamento automático". |
| Trocar nível, ver estado salvo e recarregar confirmando persistência | `02_apos_salvar_linha1.png`, `03_apos_reload_persistencia.png`, `console.json` (`val1="Avancado"`) | OK. Valor persistiu após reload. |
| Erro simulado (500) com reversão e mensagem | `04_erro_reversao.png` | OK. Mensagem visível "Falha simulada AJ32." e select revertido ao valor confirmado. |
| Duas trocas rápidas na mesma linha | `05_duas_trocas_rapidas_mesma_linha.png` | OK. Último valor vence (`Avancado`); sem reload. |
| Trocas em linhas diferentes | `06_linhas_diferentes.png` | OK. Linhas independentes, sem bloqueio cruzado. |
| Filtro/ordenação/rolagem preservados | `07_scroll_preservado.png`, `console.json` (`scrollBefore=179`, `scrollAfter=179`) | OK. Sem reload; scroll preservado. (Tela seed não tinha filtros ativos além do layout padrão.) |
| Largura estreita | `08_largura_estreita.png` | OK. Layout utilizável em 390px. |

Console: `console.json` registra apenas 404 de `/static/img/default.png` e 500 simulados do cenário de erro; `realConsoleErrors=[]`.

### Verificação AJ32-B (correção)

App Flask local temporário (SQLite descartável), Chromium headless via Playwright, com dados realistas (nível acentuado, valor legado fora do catálogo, vazio, aluno em 2 ofertas). Cada cenário contou `POST /aluno/<id>/atualizar-nivel` por 3s e falharia se excedesse 3 requisições; máximo observado: **1 POST/3s** (`aj32b_resultados.json`).

| Cenário | Resultado | Evidência |
|---|---|---|
| Troca `Básico → Intermediário` (acento), espera 3s | **1 POST**, 200, `nivel_valor="Intermediário"` | `10_aj32b_acento_salvo.png` |
| Duas trocas rápidas na mesma linha | **1 POST** com último valor (`Avançado Nível 1`); sem loop em 3s | `11_aj32b_duas_trocas_rapidas.png` |
| Valor com espaço/caixa diferentes | **1 POST**, 200; servidor devolve canônico `Avançado Nível 1`, select alinhado sem erro | `12a_aj32b_canonicalizacao.png` |
| Reenviar valor legado `(atual)` sem mudança | **0 POST** (normalização/igualdade) | `12_aj32b_legado_zero_post.png` |
| Trocar para `Não se aplica` | **1 POST**, 200, `nivel_valor="Não se aplica"` | `13_aj32b_vazio.png` |
| Injetar opção fora do catálogo | **1 POST**, **422**, `ok:false`, mensagem PT; select revertido ao confirmado | `14_aj32b_fora_catalogo_422.png` |
| Aluno em duas ofertas: trocar só a primeira | **1 POST**; segunda oferta preservada (`Outro`) | `15_aj32b_multi_oferta.png` |
| Reload final | `Avançado Nível 1`, `LEGADO FORA`, `Não se aplica`, `Intermediário`, `Outro` persistidos | `16_aj32b_reload_persistencia.png` |

Console do navegador: apenas 404 conhecido de `/static/img/default.png` e o 422 simulado; nenhum erro inesperado de JS. Evidências completas em `docs/Relatórios/aj32_evidencias/` (diretório gitignored, não versionado).

## 7. Riscos e decisões

- **Sem 409 específico:** não há regra de conflito de versão/lock no nível do aluno; última gravação válida vence, e idempotência evita escrita duplicada do mesmo valor.
- **Sem extração do núcleo JS compartilhado:** decisão consciente para não regressir autosave do conselho.
- **Sem LogAcao:** preserva estado anterior; reportado.
- **Fallback legado sem turma_curso em AJAX:** retorna 400; POST form antigo sem turma_curso ainda segue caminho legado defensivo.

## 8. Arquivos candidatos ao pacote

- `app/registros/alunos.py`
- `app/templates/turmas/detalhe.html`
- `app/static/js/turmas/nivel_autosave.js`
- `tests/test_aj32_enturmacao_nivel_autosave.py`
- `tests/test_aj32_nivel_autosave_js.py`
- `tests/test_aj22e_nivel_enturmar.py`
- `tests/test_aj22f_nivel_aluno_enturmado.py`
- `tests/snapshots/aj6b6_admin_registros_ver_turma.txt`
- `backlog_desenvolvimento.md`
- `app/models/MER.md`
- `docs/Relatórios/AJ32_EnturmacaoTrocaNivelAutosave.md`

## 9. Validação final

- Foco AJ32/AJ22 + snapshots (pós-AJ32-B): **109 passed, 1967 deselected, 148 warnings in 61.25s** (`pytest tests -q -k "snapshot or aj32 or aj22"`).
- Suíte completa pós-AJ32 (antes da correção AJ32-B): **2065 passed, 1 failed, 1259 warnings in 47:58**. Falha única: `tests/test_aj6b3_snapshot_nao_professor.py::test_snapshot_ver_turma_nao_professor` por diferença esperada no HTML da ficha (markup/JS do AJ32). Snapshots AJ6-B3 regenerados com `AJ6B4_ATUALIZAR_SNAPSHOTS=1`.
- Suíte completa pós-AJ32-B (final): **2076 passed, 1275 warnings in 1234.69s (0:20:34)** — ver seção 10.

## 10. Entrega (diff e estado final)

- Suíte completa final (`.\.venv\Scripts\python.exe -m pytest tests -q`, após a última edição do JS): **2076 passed, 1275 warnings in 1234.69s (0:20:34)**. Sem falhas.
- `git diff --stat` (AJ32-B, em cima do commit `763c143` que já continha a AJ32 base):

```text
 app/registros/alunos.py                            |  63 ++++---
 app/static/js/turmas/nivel_autosave.js             | 200 +++++++++++++++++----
 backlog_desenvolvimento.md                         |   6 +-
 docs/Relatórios/AJ32_EnturmacaoTrocaNivelAutosave.md | 86 ++++++++-
 tests/test_aj22e_nivel_enturmar.py                 |  13 +-
 tests/test_aj22f_nivel_aluno_enturmado.py          |  22 ++-
 tests/test_aj32_enturmacao_nivel_autosave.py       | 134 +++++++++++---
 tests/test_aj32_nivel_autosave_js.py               | 121 +++++++++++++
 8 files changed, 546 insertions(+), 99 deletions(-)
```

- `git status --short`:

```text
 M app/registros/alunos.py
 M app/static/js/turmas/nivel_autosave.js
 M backlog_desenvolvimento.md
 M docs/Relatórios/AJ32_EnturmacaoTrocaNivelAutosave.md
 M tests/test_aj22e_nivel_enturmar.py
 M tests/test_aj22f_nivel_aluno_enturmado.py
 M tests/test_aj32_enturmacao_nivel_autosave.py
 M tests/test_aj32_nivel_autosave_js.py
```

- `git diff --check`: sem erros de whitespace (apenas avisos LF→CRLF em 3 arquivos).
- Nenhum arquivo proibido foi alterado (`aplicar_deploy.ps1`, `empacotar_deploy.ps1`, `deploy_pacotes/`, `wsgi.py`, `.env`); nenhuma migration/schema. Evidências Playwright ficam em `docs/Relatórios/aj32_evidencias/` (gitignored; ausentes no `git status`). DBs temporários removidos e servidores encerrados.
- Nenhum commit/push/merge/deploy realizado nesta rodada; as alterações da AJ32-B permanecem não versionadas.
