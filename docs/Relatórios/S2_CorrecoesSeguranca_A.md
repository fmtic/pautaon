# S2 — Correções de segurança (Prompt A)

**Data:** 30/10/2026
**Branch:** `nova_feature` (sem push)
**Escopo:** S1-01, S1-02, S1-04, S1-05, S1-07, S1-08 + varredura de segredos no histórico (S1-03)
**Relatório base:** `docs/Relatórios/S1_AnaliseSeguranca.md`
**Migration:** nenhuma. Head do Alembic continua `c9d0e1f2a3b4`.

## Resumo por etapa

| Etapa | Achado | Commit | Suíte |
|---|---|---|---|
| E1 | S1-01 (`SECRET_KEY`) e S1-02 (`DEBUG`) | `7318ece` | 1054 → 1073 |
| E2 | S1-04 (`/teste-email`) | `3dcfe2f` | 1073 → 1076 |
| E3 | S1-05 (períodos de conselho) | `21db731` | 1076 → 1090 |
| E4 | S1-07 (XSS no conselho) | `95751b5` | 1090 → 1094 |
| E5 | S1-08 (upload de foto) | `ac21726` | 1094 → 1109 |
| E6 | prova final no ensaio | — | 13/13 verificações OK |
| E7 | S1-03 (varredura do histórico) | `6a28e6d` | leitura, sem mudança de código |

## 1. E0 — leitura

Confirmado nos arquivos antes de implementar:

- `config.py`: `SECRET_KEY` vinha de `os.getenv(...)` com fallback fixo `dev-key-substituir-em-producao`; `DEBUG` vinha de `FLASK_DEBUG` sem exigir `development`; `APP_ENV` já era a chave oficial com `FLASK_ENV` como alias.
- `run.py`: chamava `app.run()` direto, usando `app.config["DEBUG"]` — qualquer valor de `FLASK_DEBUG` abria o depurador.
- `app/__init__.py`: `validar_configuracao` não existia; os handlers de erro re-levantavam a exceção quando `app.debug`.
- `app/main/rota_disparo_email.py`: rota `/teste-email?para=` registrada em `app/main/__init__.py`, sem login e sem limite.
- `app/conselho.py`: as duas rotas de `/api/conselho-periodo` tinham `@csrf.exempt` e **nenhuma** checagem de papel; na exclusão/edição a unidade era filtrada na consulta (404 em vez de 403).
- `conselho/informacoes.html`: `onclick="editConselho({{ c.id }}, '{{ c.nome }}', …)"`.
- `app/registros/shared.py::salvar_foto` e `alunos.py`: gravava `aluno_<id>_<nome do cliente>` sem whitelist, sem limite e sem conferir o conteúdo.
- Testes: nenhum dependia do fallback de `SECRET_KEY` (a suíte criava `app` sem chave); `53` arquivos de teste ganharam `SECRET_KEY` explícita para que a nova regra não afetasse a harness.

## 2. E1 — S1-01 e S1-02

**`SECRET_KEY`.** Removido o fallback público. `SECRET_KEY` é lida do ambiente sem valor padrão e `validar_configuracao` (chamada por `create_app`) recusa, em **qualquer** `APP_ENV`:

- ausente ou vazia;
- igual ao valor histórico ou começando com `dev-key`;
- com menos de **32** caracteres.

A mensagem é em português e ensina `python -c "import secrets; print(secrets.token_urlsafe(48))"`. A validação fica em `create_app` (não no import de `config.py`) para que as Configs de teste definam a própria chave sem afrouxar a regra da aplicação. `FLASK_ENV` permanece apenas como alias legado de `APP_ENV`.

**`DEBUG`.** Padrão `False` em qualquer ambiente; só liga com `FLASK_DEBUG=true` **e** `APP_ENV=development`. `DEBUG` ligado com `APP_ENV=production` **falha na inicialização** (RuntimeError explicando o risco do debugger do Werkzeug).

**`run.py`.** Passou a usar `app.utils.execucao.escolher_bind_dev`:

- com debug → escuta **somente** `127.0.0.1:5000`;
- em `development` sem debug → `0.0.0.0:5000`;
- fora de `development` → recusa o servidor embarcado e orienta waitress/gunicorn/IIS (o deploy do IIS usa `run.app` como handler WSGI, onde o bloco `__main__` não roda).

**`.env.example`.** `SECRET_KEY` vazia e marcada como obrigatória, `APP_ENV=development`, `FLASK_DEBUG=false`, sem valores reais.

**Testes:** `tests/test_s1_config_endurecimento.py` (**19**) — chave ausente/vazia/padrão/curta recusadas, chave de 32 aceita, `create_app` falhando nos três casos, `DEBUG` falso por padrão, `DEBUG` só em `development`, `DEBUG` em produção recusando, alias `FLASK_ENV` e os três binds do servidor de desenvolvimento.

## 3. E2 — S1-04

`app/main/rota_disparo_email.py` **removido** e o import tirado de `app/main/__init__.py`. O endpoint `main.teste_email` saiu do `url_map` (207 → 206 rotas). `GET /teste-email` responde 404 para anônimo e para autenticado. Nenhum template, teste ou script consumia a rota (restam apenas menções históricas no relatório S1 e em entradas antigas do backlog).

**Testes:** `tests/test_s1_teste_email_removido.py` (**3**) — endpoint fora do `url_map`, 404 anônimo, 404 autenticado.

## 4. E3 — S1-05

`GET /informacoes`, `POST /api/conselho-periodo` e `DELETE /api/conselho-periodo/<id>` passaram a exigir os papéis de **Conselho > Data-Informações** (`admin`, `pedagogico`, `gerencia`, `secretaria` — a mesma lista da navegação); professor e demais recebem **403**. As duas rotas de API perderam `@csrf.exempt` e o template passou a enviar `X-CSRFToken` nos dois `fetch` (mesmo padrão do calendário do período letivo).

`assert_unidade_context` entrou na edição e na exclusão: conselho de outra unidade → **403**; id inexistente → **404**. **Divergência do relatório S1 registrada:** a checagem existia de forma indireta (a consulta filtrava `unidade_id` e devolvia 404); agora é explícita e distingue “de outra unidade” de “não existe”.

**Testes:** `tests/test_s1_conselho_periodos.py` (**14**) — 4 papéis × `/informacoes` 200, professor 403 nas três rotas (com token), anônimo 302, POST/DELETE sem token → 400 de CSRF, com token → 200, conselho de outra unidade → 403 na edição e na exclusão, id inexistente → 404.

## 5. E4 — S1-07

O template interpolava `'{{ c.nome }}'` dentro de `onclick`: o Jinja escapa a aspa como `&#39;`, mas o parser HTML decodifica a entidade **antes** de entregar ao JS, então `x');alert(1);//` fechava a string e executava código. Os botões de edição e exclusão passaram a usar `data-conselho-id`, `data-nome`, `data-inicio`, `data-fim`, `data-final` e `data-periodo-letivo-id` + `addEventListener` lendo o `dataset`. Nenhum dado de usuário entra em string JS inline.

**Varredura dos demais templates** (`onclick` com `{{ }}` e `|safe`): só o conselho era vulnerável. `dashboard/painel_pedagogico.html`, `periodos/calendario.html`, `servico_social/forms/notificacao_violencia.html` e `socioeconomica.html` usam `|tojson|safe`, que escapa `<`, `>`, `&` e `'` como `\u003c`/`\u003e`/`\u0026`/`\u0027` — seguros; `periodos/certificado.html` e os `goToStep(i)` do serviço social interpolam inteiros; `turmas/listar.html` e `turmas/detalhe.html` usam `{{ }}` em atributos comuns.

**Bancos (SELECT, somente leitura):** `periodo_conselho` tem 1 linha no `pautaon` (`FINAL`) e nenhuma no `pautaon_ensaio`; `periodo_letivo` tem 3 e 5. **Zero** nomes com aspas, `<`, `>`, `&`, `;`, `(` ou `)` — nada foi explorado.

**Testes:** `tests/test_s1_conselho_xss.py` (**4**) — nome `x');alert(1);//` sai escapado em `data-nome`, o padrão `onclick="editConselho(` não existe mais, `<script>alert(2)</script>` renderiza como `&lt;script&gt;…` e `data-conselho-id` é sempre numérico.

## 6. E5 — S1-08

As regras ficaram em `app/utils/fotos.py`:

- whitelist de extensão `jpg`, `jpeg`, `png`, `webp`;
- limite de **2 MB**;
- conteúdo conferido pela **assinatura de bytes** (PNG `\x89PNG\r\n\x1a\n`, JPEG `\xff\xd8\xff`, WEBP `RIFF....WEBP`) e, quando o Pillow está instalado, também por `Image.open(...).verify()`. **O Pillow não faz parte do `requirements.txt`**, então na prática a assinatura é o portão — reportado conforme o prompt;
- nome gerado pelo servidor (`aluno_<id>_<uuid>.<ext>`) e extensão vinda do **conteúdo**, não do nome enviado (JPEG chamado `.png` vira `.jpg`);
- recusa devolve mensagem em português e **não grava nada**; `novo_aluno`/`editar_aluno` mostram por `flash` e seguem (a foto é opcional);
- na entrega, `foto_aluno` usa `mimetype` fixo da extensão validada + `X-Content-Type-Options: nosniff`; extensão legada cai em `application/octet-stream` e continua sendo servida.

**Fotos existentes (somente leitura, nada migrado nem apagado):** `instance/uploads/fotos` tem **11** arquivos — 4 `.jpg` e 7 `.png`, **todas** dentro da whitelist.

**Pendência anterior, fora do escopo:** `app/registros/servico_social.py` monta `foto_url` com `url_for("static", filename=aluno.foto_path)` (e `notificacao_violencia.html` repete o padrão); `/static/uploads/...` não é servido desde a SEC-01, então a foto desse formulário sai quebrada.

**Testes:** `tests/test_s1_foto_upload.py` (**15**) — `.svg`/`.html`/`.gif`/sem extensão recusados, HTML e JPEG renomeados como `.png`, conteúdo inválido, vazio, acima de 2 MB, extensão gravada vindo do conteúdo, PNG/JPG válidos gravados e servidos com `image/png`/`image/jpeg` + `nosniff`, nome do cliente não chega ao disco, flash sem gravar, professor 403 no upload, aluno de outra unidade 403, professor sem vínculo 403 na foto e foto legada `.bmp` ainda servida.

## 7. E6 — prova final no ensaio (sem commit)

Sondagem com `app.test_client()` **fora** de `app_context` empilhado contra `pautaon_ensaio`: **13/13 verificações OK**.

- `GET /teste-email` → 404, anônimo e autenticado;
- professor (id 5) → 403 em `/informacoes`, no POST e no DELETE de `/api/conselho-periodo` (com token CSRF);
- gestor `pedagogico` (id 23) → 400 sem token nos dois métodos;
- inicialização sem `SECRET_KEY` falha em subprocesso, com a mensagem que ensina `secrets.token_urlsafe(48)` (o `.env` foi neutralizado com `dotenv.load_dotenv` no-op **apenas no processo filho**; o arquivo do usuário não foi tocado).

Escritas: **nenhuma**. `log_acao` 1485 → 1485 (nenhum id novo) e `configuracao_sistema` com as mesmas 13 chaves antes e depois.

## 8. E7 — S1-03: varredura do histórico (somente leitura)

Escopo do inventário: 390 commits, 4.435 objetos, 1.969 blobs, 61 refs (inclui `refs/agents/*`, `refs/cline/*`, `refs/codex/*` e `stash`), 0 tags e nenhum `refs/pull` local. gitleaks, trufflehog e git-filter-repo **não** estão instalados — a varredura usou `git rev-list --all --objects` + `git cat-file --batch` e inspeção das strings dos artefatos.

**Nenhum segredo de aplicação real**: `SECRET_KEY`, URL de banco, LDAP, Google, SMTP e chaves privadas são placeholders ou `os.getenv(...)`; o `.env` real não está no histórico (só `.env.example`). O que existe são **dados pessoais** nos dumps (`instance/database.db`, `instance/database.db.bak`, `instance/backups/database-antes-initdb-2026-09-29.db`, `backup_20260923_194945.sql`) e em `instance/error.log.1`.

**Status: roteiro gerado, execução pendente do usuário.** O passo a passo (backup em clone espelho, `git filter-repo --invert-paths`, verificação, force-push de branches/tags, `refs/pull/*`, purga no suporte do GitHub, reclone obrigatório, tratamento do Nextcloud e checklist) está em `docs/Relatórios/S3_RoteiroLimpezaHistorico.md`. **Nada foi reescrito, apagado ou empurrado.**

## 9. Suíte, ruff e deploy

- Suíte: **1054 → 1109** (+55: 19 + 3 + 14 + 4 + 15).
- `ruff check --select F821,F811,F841` limpo em todos os arquivos tocados.
- Sem migration, sem push.

**Como o deploy inicia o app (o que o repositório indica).** `docs/manual_deploy.md` usa IIS + `wfastcgi`, com `WSGI_HANDLER=app.create_app()` e `PYTHONPATH` no `web.config`; nesse arranjo o bloco `if __name__ == "__main__"` do `run.py` não roda e o servidor embarcado não é usado. Em desenvolvimento, `python run.py` agora só abre debug em `127.0.0.1` e recusa subir fora de `development`.

## 10. O que fazer no seu ambiente

1. **Gerar a `SECRET_KEY`** (obrigatória para a aplicação subir):
   ```
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```
2. **Conferir o `.env` de produção** (ou as variáveis do `web.config`):
   - `SECRET_KEY` com o valor novo (≥ 32 caracteres, nunca `dev-key*`);
   - `FLASK_DEBUG=false` (ou ausente);
   - `APP_ENV=production`;
   - `SESSION_COOKIE_SECURE` ausente (o padrão já é `True`).
3. **Remover `FLASK_DEBUG` do `.env`** que estiver em produção: com ele `true` e `APP_ENV=development`, o depurador do Werkzeug abre execução de código no servidor.
4. Se trocar a `SECRET_KEY`, todas as sessões ativas caem (os cookies antigos deixam de validar) — é o comportamento desejado depois de um vazamento.

## 11. O que ficou para os prompts seguintes

| Achado | Severidade | Situação |
|---|---|---|
| S1-06 — logout não invalida a sessão | alta | **Prompt C** |
| S1-09, S1-10, S1-14, S1-15 | média | **resolvidos no Prompt B** (S4) |
| S1-11 — rate limit só por IP | média | **Prompt D** |
| S1-12 — enumeração por tempo | média | **Prompt D** |
| S1-13 — política de senha / senha em texto claro | média | **Prompt E** |
| S1-16 a S1-24 | baixa | **Prompt E** |
| S1-03 — execução da limpeza do histórico | crítica | **pendente do usuário** (roteiro no S3) |
