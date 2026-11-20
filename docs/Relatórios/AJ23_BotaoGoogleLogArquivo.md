# Adendo AJ23 — Botão Google em "/" + log em arquivo (diagnóstico do callback OAuth em produção)

**Data:** 19/11/2026 · **Branch:** `nova_feature` · **Migration:** nenhuma · **Schema:** inalterado · **Push/merge:** nenhum

## Motivação

Em produção (IIS + `wfastcgi`), o logger do Flask escreve no `stderr`, que o
`wfastcgi` descarta. Assim, `current_app.logger.exception("Falha no callback
OAuth Google.")` (`app/auth.py`) não deixava rastro em arquivo e não havia como
diagnosticar o login Google. Além disso, `app/main/home.py:home()` renderizava
`login.html` direto, sem a flag `google_login_habilitado` — o botão só aparecia
em `/login`.

## Implementação

1. **Botão em `/` (`app/main/home.py`):** `home()` agora faz
   `redirect(url_for("auth.login"))`. A tela inicial passa a ter uma única
   origem; o comportamento para usuário já autenticado continua sendo o de
   `auth.login` (inclusive os redirecionamentos de perfil pendente/primeira
   senha do `before_request`).

2. **Fonte única da flag (`app/__init__.py`):** novo *context processor*
   `inject_google_login_habilitado` calcula `google_login_habilitado` a partir de
   `current_app.config`: exige `GOOGLE_OAUTH_CLIENT_ID`,
   `GOOGLE_OAUTH_CLIENT_SECRET` **e** `GOOGLE_OAUTH_REDIRECT_URI` preenchidos.
   A duplicação em `auth.login()` foi removida (`render_template("login.html")`
   puro). Auditoria: havia apenas dois `render_template("login.html")` no
   projeto — `home.py` (agora redirect) e `auth.py`. Os demais caminhos citados
   (login inválido, conta pendente, vínculo Google) usam PRG/redirect ou outros
   templates e passam a receber a flag automaticamente em qualquer render.
   O HTML de `login.html` **não foi alterado**.

3. **Log em arquivo (`app/__init__.py`, `config.py`):** `create_app` chama
   `_configure_logging`, que instala um `RotatingFileHandler` em
   `<raiz>/logs/app.log` (5 MB, 5 backups, `utf-8`) com nível `INFO` e formato
   `%(asctime)s %(levelname)s %(name)s: %(message)s`. A pasta é criada quando
   falta; `LOG_DIR` (ambiente ou `Config.LOG_DIR`) sobrepõe o caminho.
   - O handler usa `delay=True` e verifica `TESTING` no `emit`: nem `create_app`
     com `TESTING`, nem harnesses que ligam a flag depois, criam arquivo.
   - Guard de duplicação: o logger `app` é compartilhado entre instâncias no
     mesmo processo (recarga do wfastcgi/múltiplas `create_app`); antes de
     adicionar, handlers instalados por esta função são removidos e fechados.
     Os handlers de stderr/outras bibliotecas não são tocados.
   - O handler antigo `instance/error.log` (WARNING, 3 backups) foi substituído.

4. **Sem segredos no log (`app/utils/logging_seguro.py`, `app/auth.py`):**
   `mascarar_para_log` remove query de URLs, valores de `code`, tokens,
   `client_secret`, senhas e os valores exatos de configuração. No `except` do
   callback o log registra **tipo da exceção + mensagem sanitizada**
   (`logger.exception("Falha no callback OAuth Google: %s: %s", ...)`); o
   traceback continua anexo. O `format` do handler aplica a mesma máscara à
   linha inteira (mensagem e traceback), como defesa em profundidade.
   Fluxo OAuth, regras de vínculo, domínios permitidos e perfis intactos.

## Arquivos tocados (pacote de deploy)

- `app/__init__.py` — logging de arquivo, guard de handler, context processor da flag
- `app/auth.py` — sem duplicação da flag; callback loga tipo/mensagem sanitizada
- `app/main/home.py` — `/` redireciona para `auth.login`
- `config.py` — `DEFAULT_LOG_DIR` / `Config.LOG_DIR` (override por `LOG_DIR`)
- `app/utils/logging_seguro.py` — **novo**: máscara de segredos para o log
- `tests/test_aj23_login_google_log.py` — **novo**: 13 testes
- `.gitignore` — ignora `logs/` (inclusive a rotação `app.log.1`…`app.log.5`)
- `backlog_desenvolvimento.md`, este relatório

Goldens (`tests/snapshots/*`) **não** foram alterados: nenhum HTML mudou de fato.

## Verificação

- Novos testes: **13 passed** (`tests/test_aj23_login_google_log.py`): redirect de `/`,
  flag ligada/desligada (inclusive sem `CLIENT_SECRET`) e no re-render pós-POST
  inválido, usuário autenticado, configuração do handler, ausência de duplicação,
  `TESTING` antes/depois do `create_app`, callback com exceção forçada em
  `fetch_token` (arquivo com tipo + traceback e sem segredos) e máscara JSON/URL.
- Suíte completa: **1906 passed, 0 failed** (base 1893 + 13 novos).
- `ruff --select F821,F811,F841` e `git diff --check`: limpos.
- Nenhuma migration/head alterado; sem push e sem merge.
