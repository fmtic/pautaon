# AJ5-B — Validação de upload de documento no servidor

**Etapa:** série de ajuste AJ5 (continua o AJ5-A; corrige o Achado 0.1 dele).
**Branch:** `nova_feature` · **Base:** 1382 passed · **Sem migration, sem push, sem escrita em banco real ou storage real** (testes com `tmp_path` e bytes gerados em memória).

## Etapa 0 — Auditoria (somente leitura)

### 0.1 Todos os usos de `request.files` / `salvar_documento`

| Rota | Campo(s) | Conteúdo legítimo | Validação hoje | Maior corpo legítimo |
|------|----------|-------------------|----------------|----------------------|
| `POST /alunos/novo` e `POST /aluno/editar/<id>` | `foto` | imagem webcam/arquivo | **S1-08** (`validar_foto`: whitelist + assinatura + 2 MB) | 2 MB |
| mesmas rotas | 7 campos `DOC_IDS` (`doc_aluno`, `doc_residencia`, `doc_declaracao`, `doc_atestado`, `doc_termo`, `doc_responsavel`, `doc_laudo`) via `salvar_documento` | PDF | **só a extensão `.pdf`** — sem tamanho, sem conteúdo | 7 × (ilimitado!) |
| `periodos` — modelo de certificado (`request.files.get("arquivo")`) | `arquivo` | docx/odt/pdf (SVG de fora) | whitelist de extensão + **5 MB** (`certificado_modelo.MAX_BYTES`, seek/tell) | 5 MB |
| `atendimentos` — anexo (`_salvar_anexo`) | `anexo` | documentos de atendimento | whitelist de extensão + **2 MB** (`_MAX_ANEXO_BYTES`, seek/tell); sem assinatura de conteúdo | 2 MB |
| `informacao_padrao` — logos/favicon/foto padrão | 4 campos de imagem | imagem | whitelist de extensão + **3 MB** (`MAX_UPLOAD_BYTES`) | ~12 MB (4 campos) |

`salvar_documento` (`app/registros/shared.py`) era o único upload **sem teto de tamanho nem checagem de conteúdo** (a extensão `.pdf` era a única regra). Pontos que já eram corretos e **não mudaram**: gravação fora de `static`, caminho por `_build_upload_path` (guarda anti-traversal), nome gerado pelo servidor (`<doc_id>.pdf`, nada do cliente).

### 0.2 Como a foto é validada (padrão S1-08)

`app/utils/fotos.py::validar_foto`: extensão na whitelist → tamanho por `stream.seek(0, END)`/`tell()` (sem carregar tudo) → assinatura de bytes (`tipo_por_assinatura`, 32 bytes lidos) → Pillow opcional com teto de 25 MP. **Este é o estilo reutilizado pelo `validar_pdf`.** A webcam **não** envia base64 em campo de texto: `aluno_utils.js` faz `canvas.toBlob → new File('foto_webcam.jpg') → DataTransfer → input file`, chegando como multipart comum (`request.files.get("foto")`). Tamanho típico: JPEG 640×480 @0.92, poucas dezenas de KB.

### 0.3 `MAX_CONTENT_LENGTH` e 413

`grep` não acha `MAX_CONTENT_LENGTH` em lugar algum — o corpo da requisição era **ilimitado** (Werkzeug bufferia até o navegador aguentar). Não havia handler de 413: cairia no `@app.errorhandler(HTTPException)` genérico, que renderiza `sistema_indisponivel.html` (sem stack trace, mas não amigável nem devolvia ao form). Achado novo durante os testes: o `try/except Exception` gigante de `novo_aluno`/`editar_aluno` **engolia** o 413 como "falha de banco" — corrigido com `except HTTPException: raise` nos dois.

### 0.4 Como `ver_documento_aluno` entrega o arquivo

`send_from_directory(pasta, "<doc_id>.pdf", mimetype="application/pdf", as_attachment=False)` — inline, mimetype já era fixo pelo servidor. **Nenhum header próprio**: sem `nosniff`, sem `Cache-Control` explícito, sem `Content-Disposition`.

## Etapa 1 — O que foi implementado

- **`validar_pdf(documento, max_bytes=2 MB)`** em `app/registros/shared.py`, chamado por `salvar_documento` **antes de gravar qualquer byte**: extensão `.pdf` (continua exigida); arquivo vazio rejeitado; tamanho por `seek`/`tell` — exatamente 2 MB passa, 2 MB + 1 não; assinatura `%PDF-` procurada nos primeiros 1024 bytes (a especificação permite até 1023 bytes antes do cabeçalho).
- **`salvar_documento` passou a devolver o motivo em português ou `None`** (mesmo contrato do `salvar_foto` do S1-08), em vez do `bool` anterior.
- **Falha deixou de ser silenciosa:** `_atualizar_documentos_entregues` trata cada documento por vez e faz `flash` com o **nome amigável** (`DOC_LABELS`: "RG/CPF Aluno", "Laudo Médico", …) + motivo — nunca o nome do arquivo do cliente. Documento recusado **não grava nada e não vira flag `true`**; os demais documentos válidos do mesmo POST são salvos normalmente e o cadastro do aluno **não é desfeito**.
- **Limite global:** `MAX_CONTENT_LENGTH = 20 MB` no `Config` — decisão: **global, não por rota**, porque *todas* as rotas de upload da 0.1 cabem nele (pior caso ≈ 16 MB: 7 PDFs × 2 MB + foto 2 MB + campos; a rota maior fora do form de aluno é o modelo de certificado, 5 MB; nenhuma importação exige mais). Handler `@app.errorhandler(413)` com flash amigável + redirect: usa o `Referer` **só se for do mesmo host** (referrer externo viraria open redirect; sem referrer confiável, cai na raiz) — sem stack trace.
- **Headers de `ver_documento_aluno`:** `X-Content-Type-Options: nosniff`, `Cache-Control: private, no-store`, `Content-Disposition: inline; filename="<doc_id>.pdf"`. Roles e escopo de unidade **inalterados**.
- **Não mudaram:** layout de pastas (`uploads/documentos/<matrícula>/`), nome gravado (`<doc_id>.pdf`) e o fluxo de exclusão do AJ5-A.

## Etapa 2 — Testes e prova de reversão

`tests/test_aj5b_upload_documento.py` — **13 testes**: PDF mínimo aceito + flag `true`; reupload substitui; conteúdo `MZ` com `.pdf` rejeitado (nada no disco, flag inalterada, flash presente); PDF com extensão errada rejeitado; 2 MB exatos aceito; 2 MB + 1 rejeitado (flash cita o tamanho); vazio rejeitado (flash cita "vazio"); POST misto (válido salvo + flag, inválido recusado, aluno salvo); flash não revela o nome do cliente; `MAX_CONTENT_LENGTH == 20 MB`; 413 com teto rebaixado no app de teste → flash amigável + redirect, sem `Traceback`, sem arquivo parcial; headers do `ver_documento_aluno`; roles/escopo do `ver` intactos (anônimo 302→login, professor 403, outra unidade 403).

Sondas em `git worktree` destacado em `263369f` (guarda `status --porcelain` antes de cada checkout; mutações só dentro do worktree, caminhos absolutos; evidências `.tmp/aj5b_p1.txt`, `.tmp/aj5b_p2.txt`, `.tmp/aj5b_p3.txt`):

| Sonda | Mutação no worktree | Resultado |
|-------|---------------------|-----------|
| Base | código corrigido copiado + arquivo de teste | **13 passed** |
| P1 | chamada a `validar_pdf` removida de `salvar_documento` | **6 failed** (exatamente os de conteúdo/extensão/tamanho/vazio/misto/flash) |
| P2 | só as 3 linhas de headers removidas | **1 failed** (o teste de headers) |
| P3 | `__init__.py` + `config.py` revertidos ao HEAD | falham o teste do teto de 20 MB e o do 413 (o de headers já estava mutado da P2) |

**Higiene de história (feita a pedido):** como nada havia sido enviado (`ahead 10`), o commit de registro de drift `7de48d9` foi juntado em `81826ed` com rebase interativo (fixup) — o `feat` agora já carrega o registro do rótulo e **nenhum commit da série AJ5-A tem a suíte vermelha por drift**. Reescrita local: `81826ed`+`7de48d9` → `7391b90`; `1077ca3` → `263369f`. Árvore idêntica ao backup (`git diff backup-aj5a HEAD` vazio).

## Verificação

- Suíte completa: **1395 passed, 0 failed** (1382 + 13 novos; evidência `.tmp/aj5b_suite.txt`).
- `ruff check --select F821,F811,F841 app tests scripts migrations` → All checks passed!
- `git worktree list` só com o principal; `git status` limpo (exceto os prompts não rasturados de sempre); nenhum push (`origin/nova_feature` em `ef98f7f`).

## Commits

| Hash | Descrição |
|------|-----------|
| `f2d405f` | `feat(alunos): validar upload de documento no servidor` (validador + flash + teto 20 MB + 413 + headers + testes — suíte verde no mesmo commit) |
| (este, docs) | `docs(aj5b): relatório + backlog + MER da validação de upload` |

## Pendências

- **AJ5-C (proposta):** unificar `novo_aluno`/`editar_aluno` em template parcial e **re-renderizar com `request.form` na falha de validação** (Achado 0.4 do AJ5-A — hoje o POST ruim joga fora tudo que foi digitado).
- **`informacao_padrao` engole 413:** a view tem `except Exception` amplo (linha ~40) — merece o mesmo `except HTTPException: raise` aplicado ao form de aluno (fica para a próxima varredura).
- **Conteúdo dos demais uploads:** `anexo` de atendimento e modelo de certificado validam extensão/tamanho mas **não a assinatura** do conteúdo — candidaturas naturais ao mesmo padrão, fora do escopo desta tarefa.
- **Achado 0.2 do AJ5-A:** professor/laudo (dado de saúde) — decisão de produto pendente.

## Procedimento de reprodução

```powershell
.venv\Scripts\python.exe -m pytest tests/test_aj5b_upload_documento.py -q      # 13
.venv\Scripts\python.exe -m pytest tests/test_aj5_documento_excluir.py -q      # 12 (regressão do contrato de salvar_documento)
# sondas: git worktree add --detach d:\pautaon\.tmp\aj5b_wt 263369f; copiar os
# arquivos corrigidos; aplicar mutações cirúrgicas; rodar; git worktree remove --force
```
