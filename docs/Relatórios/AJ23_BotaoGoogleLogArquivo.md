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

---

## Adendo AJ23-B — authorization_response a partir do redirect_uri configurado

**Data:** 19/11/2026 · **Branch:** `nova_feature` · **Migration:** nenhuma · **Schema:** inalterado · **Push/merge:** nenhum

### Motivação

O log real de produção (`logs\app.log`) registrou
`InsecureTransportError (insecure_transport) OAuth 2 MUST utilize https` no
`google_callback`. O TLS termina antes do app (IIS/wfastcgi), então
`request.url` chegava com esquema `http` e o authlib recusava a troca do código.
`OAUTHLIB_INSECURE_TRANSPORT` não pode ser ligado em produção.

### Implementação

`app/auth.py` não usa mais `request.url` no `fetch_token`. Novo helper puro
`_authorization_response_oauth(redirect_uri, query_string)` monta:

```python
qs = query_string.decode("utf-8")
authorization_response = redirect_uri + (("?" + qs) if qs else "")
```

com `redirect_uri` vindo de `GOOGLE_OAUTH_REDIRECT_URI` (o mesmo já atribuído a
`flow.redirect_uri`). Sem query, o resultado é apenas o `redirect_uri`.
State anti-CSRF, PKCE (`google_code_verifier`), escopos longos, domínios
permitidos, vínculo e perfis permanecem intactos. Log/flash do `except` seguem
como no AJ23 (tipo + mensagem sanitizada, traceback anexo).

### Auditoria de esquema (somente relato — nada alterado além do callback)

| Local | Uso | Risco em produção | Proposta (separada, não implementada) |
| --- | --- | --- | --- |
| `app/auth.py` (`fetch_token`) | `request.url` | **Era o bug corrigido**: `http` → `InsecureTransportError` | Corrigido neste adendo |
| `app/__init__.py` (`set_security_headers`) | `request.is_secure` | HSTS não é emitido se `TRUSTED_PROXY` não estiver ligado no IIS | Confirmar `TRUSTED_PROXY=true` + `HTTP_X_FORWARDED_PROTO=https` no `web.config` (já documentado em `docs/manual_deploy.md`); nenhuma mudança de código |
| `app/templates/emails/base_email.html:62` | `request.url_root` na `<img>` do logo | E-mail pode sair com `http://...` (mixed content/bloqueio) atrás do terminador TLS | Usar base pública configurada (`PUBLIC_BASE_URL`) no render do e-mail, ou garantir `TRUSTED_PROXY`; sem mudança aqui |
| `app/templates/conselho/fechamento.html:183` | `{{ request.url }}` no rodapé de impressão | Imprime `http://...` com a query completa da tela | Trocar por URL canônica configurada / remover a query do rodapé; sem mudança aqui |
| `app/__init__.py` (handler 413, `redirect(ref or "/")`) | `request.referrer` | Pode devolver para `http` se o IIS não redirecionar HTTP→HTTPS | Validar/normalizar o esquema do referrer ou voltar sempre à rota relativa; sem mudança aqui |

Não há ocorrências de `request.host_url`, `request.scheme` ou `url_for(...,
_external=True)` no projeto. Cookies não dependem do esquema observado:
`SESSION_COOKIE_SECURE` é `True` por padrão (S1-09).

### Arquivos tocados (AJ23-B)

- `app/auth.py` — helper + `fetch_token` com `authorization_response` derivado do `redirect_uri`
- `tests/test_aj23b_callback_authorization_response.py` — **novo**: 5 testes
- `backlog_desenvolvimento.md`, este relatório (adendo AJ23-B)

### Verificação (AJ23-B)

- Novos testes: **5 passed** (HTTP com `?state=...&code=...` → URL https + mesma query; sem query → só o `redirect_uri`; state divergente recusado sem chamar `fetch_token`; state/PKCE/escopos preservados; exceção logada com tipo/mensagem sanitizada e flash).
- Regressão AJ23: **13 passed**; suíte completa: **1911 passed, 0 failed** (base 1906 + 5 novos).
- `ruff --select F821,F811,F841` e `git diff --check`: limpos.
