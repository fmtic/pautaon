# S4 — Correções de segurança (Prompt B)

**Data:** 30/10/2026
**Branch:** `nova_feature` (sem push)
**Escopo:** S1-09, S1-10, S1-14, S1-15 + `.gitignore` de logs + senhas expostas nos dumps
**Relatórios de referência:** `docs/Relatórios/S1_AnaliseSeguranca.md` e `docs/Relatórios/S3_RoteiroLimpezaHistorico.md`
**Migration:** nenhuma. Head do Alembic continua `c9d0e1f2a3b4`.

## Resumo por etapa

| Etapa | Achado | Commit | Resultado |
|---|---|---|---|
| E0 | leitura e inventário de hosts externos | — | inventário fechado (§1) |
| E1 | S1-09 (cookie `Secure`, HSTS) e S1-15 (`ProxyFix`) | `8c73977` | cookie seguro por padrão, HSTS só em HTTPS, ProxyFix desligado por padrão |
| E2 | S1-10 (cache de página autenticada) | `a6b7c1f` | `no-store, private` em resposta autenticada |
| E3 | S1-14 (CSP) | `e77b88c` | `Content-Security-Policy-Report-Only` com o inventário |
| E4 | logs versionados | *pendente de commit* | `.gitignore` com `instance/error.log*`; `error.log.1` fora do índice |
| E5 | senhas expostas nos dumps | *pendente de commit* | script + 14 testes; dry-run executado, aplicação não executada |

## 1. E0 — leitura e inventário

Lido antes de implementar: `app/__init__.py` (hooks `before_request`/`after_request`, `ProxyFix` na linha 23, handlers de erro), `config.py` (`APP_ENV`, `_resolver_app_env`, `SESSION_COOKIE_*`, `DEBUG`), `docs/manual_deploy.md` (IIS + `wfastcgi`, `web.config`), `app/templates/base.html`, `app/templates/login.html` e o CSS/JS de `app/static`.

**Estado encontrado**

- `ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)` era aplicado **sempre**.
- HSTS existia, mas saía com `includeSubDomains` e apenas quando `APP_ENV == "production"` — inclusive em resposta HTTP.
- `SESSION_COOKIE_SECURE` valia `APP_ENV == "production"`: com `APP_ENV` ausente ou `development`, o cookie ia sem `Secure`.
- Bootstrap e `bootstrap-icons` são **locais** (`app/static/bootstrap/…`); não há Bootstrap, FontAwesome nem Google Fonts por CDN.
- 172 atributos `onclick`/`onchange`/`onsubmit` inline nos templates (28 em `editar.html`, 29 em `novo.html`, 11 em `notificacao_violencia.html`…), além de blocos `<script>` e `<style>` inline em `base.html` e `login.html`.

**Inventário de hosts externos (base da CSP)**

| Host | Onde | Como é usado | Diretiva |
|---|---|---|---|
| `cdn.jsdelivr.net` | `relatorios/bi.html`, `relatorios/ficha_aluno.html`, `relatorios/painel_pedagogico.html`, `dashboard/painel_pedagogico.html` (Chart.js 4.4.7 / 4 + chartjs-plugin-datalabels 2) e `auth/confirmar_vinculo_google.html` (bootstrap-icons 1.11.1) | `<script src>` e `<link rel="stylesheet">`; o CSS de ícones puxa `.woff2` do mesmo host | `script-src`, `style-src`, `font-src` |
| `calendar.google.com` | `dashboard/servico_social.html` | `<iframe src="…/calendar/embed?…">` | `frame-src` |
| `sos.grael.org.br` | `erros/403.html`, `erros/sistema_indisponivel.html` | `<a href target="_blank">` | nenhuma (navegação) |
| `developers.google.com` | `termos/politica_privacidade.html` | `<a href>` de política do Google | nenhuma (navegação) |
| `www.w3.org` | `aguardando.html`, `erros/*`, `relatorios/bi.html` | `xmlns` de SVG | nenhuma (não é requisição) |

Nenhum outro host externo foi encontrado em `app/templates`, `app/static/css` ou `app/static/js`.

## 2. E1 — S1-09 e S1-15

**Cookie `Secure` (S1-09).** `config.py` ganhou `_app_env_explicito()` (lê só `APP_ENV`, devolvendo `None` quando não declarado) e `_resolver_session_cookie_secure()`: o padrão é `True` em qualquer cenário e só cai para `False` com `APP_ENV=development` **explícito**. `FLASK_ENV=development` não derruba o padrão. `SESSION_COOKIE_SECURE` no ambiente continua sobrepondo nos dois sentidos.

**HSTS (S1-09).** O cabeçalho só é emitido quando `request.is_secure` e `HSTS_MAX_AGE > 0`, com valor `max-age=<n>` (padrão `15552000` = 180 dias). **Sem** `includeSubDomains` e **sem** `preload` — os subdomínios não são geridos por este sistema. `HSTS_MAX_AGE=0` desliga.

**`ProxyFix` (S1-15).** Passou a ser condicional a `TRUSTED_PROXY` (padrão `false`). O manual de deploy documenta quando ligar, o comando `appcmd` que libera `HTTP_X_FORWARDED_PROTO` e o risco de ligar sem proxy (cliente forja `X-Forwarded-Proto`, `-For` e `-Host`, afetando HTTPS aparente, IP de origem/auditoria e links).

**Redirecionamento HTTP→HTTPS.** Continua **fora** do app: com TLS terminado no IIS, `request.is_secure` seria falso sem `TRUSTED_PROXY` e o redirecionamento entraria em laço. `docs/manual_deploy.md` ganhou a seção “HTTPS, HSTS e proxy reverso” com:

1. `appcmd` para autorizar a server variable;
2. regra de URL Rewrite que define `HTTP_X_FORWARDED_PROTO: https`;
3. `TRUSTED_PROXY=true` no `web.config`;
4. regra de redirecionamento `{HTTPS} = off → https://{HTTP_HOST}/{R:1}` (antes da regra do header);
5. conferência por `curl` (301/308 no HTTP, `200` + `Strict-Transport-Security` no HTTPS, `Set-Cookie` com `Secure`).

**Testes:** `tests/test_seguranca_e1_headers.py` (**19**) — cookie por ambiente (ausente, `production`, `development`, com espaço/caixa, `staging`), independência de `FLASK_ENV`, override explícito nos dois sentidos, reload do `config` aplicando o ambiente, HSTS ausente em HTTP e presente em HTTPS, ausência de `includeSubDomains`/`preload`, `HSTS_MAX_AGE` 600/0, HSTS em resposta 404 HTTPS, `ProxyFix` desligado ignorando cabeçalho forjado, ligado honrando `X-Forwarded-Proto` e ligado sem cabeçalho continuando HTTP.

## 3. E2 — S1-10 (cache)

Novo `after_request` `set_cache_headers` em `app/__init__.py`:

- usuário autenticado → `Cache-Control: no-store, private`, `Pragma: no-cache`, `Expires: 0`;
- rotas que já definiam `no-store` são preservadas (`/aluno/<id>/info-professor`);
- downloads de `send_file`/`send_from_directory`, que saem com `no-cache`, passam a `no-store, private` **sem alterar o corpo**;
- `/login` e páginas de erro anônimas → apenas `no-cache` (sem `no-store`, que atrapalha o botão Voltar);
- `/static` fica fora do hook.

**Regressão encontrada pela suíte e corrigida:** `current_user.is_authenticated` do Flask-Login lê `is_active`, que é coluna — em objeto expirado por commit isso disparava um `SELECT` extra em `user` por resposta. O `test_f1_autor_lancamento.py::test_post_sem_select_por_linha_em_user` pegou o problema (2 SELECTs onde o contrato é ≤ 1). O hook passou a usar `session.get("_user_id")`, que responde sem consulta.

**Testes:** `tests/test_seguranca_e2_cache.py` (**6**) — `/painel` com `no-store, private` + `Pragma`/`Expires`; XLSX do BI (`/relatorios/bi/exportar/xlsx?codigo=ALU-001`) baixando íntegro (começa com `PK`) e sem cache; `/login` com `no-cache` e sem `no-store`; 404 anônimo com `no-cache`; `/static` sem o header; rota JSON que já definia `no-store` intacta.

## 4. E3 — S1-14 (CSP em Report-Only)

`Content-Security-Policy-Report-Only` em toda resposta de documento (fora `/static`), montada a partir do inventário:

```
default-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self';
frame-ancestors 'self'; frame-src 'self' https://calendar.google.com;
img-src 'self' data:;
script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net;
style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net;
font-src 'self' data: https://cdn.jsdelivr.net
```

`CSP_REPORT_ONLY` (padrão `true`) desliga a emissão; `CSP_REPORT_ONLY_POLICY` troca a política inteira. **Não** foi criado endpoint de coleta (evita rota pública nova).

**Como observar as violações**

1. Abrir a aplicação em HTTPS, com o console do navegador aberto (`F12` → Console).
2. Navegar pelas telas que usam Chart.js (`/relatorios/bi`, `/relatorios/painel-pedagogico`, `/dashboard/painel-pedagogico`, ficha do aluno) e pelo Serviço Social (iframe do calendário).
3. As violações aparecem como `Refused to load … because it violates the following Content Security Policy directive …` (no Chrome/Edge) ou `Content-Security-Policy: The page's settings blocked …` (Firefox). Como o header é `Report-Only`, **nada é bloqueado** — a página continua funcionando.

**O que contar como violação real**

- Recurso do próprio site (`'self'`) ou dos dois hosts do inventário recusado por uma diretiva: é achado real, indica host ou diretiva faltando.
- Bloqueio de `connect-src` (fetch/XHR) caindo em `default-src 'self'`: real, se a chamada for do sistema.
- Violação com origem `chrome-extension://`, `moz-extension://`, `about:` ou `data:` gerada por extensão do navegador/gerenciador de senhas: **não** é do site — ignorar (ou repetir em janela anônima sem extensões).
- `unsafe-inline` já cobre `<script>`/`<style>`/`onclick` inline: se aparecer violação de inline, ela vem de `javascript:` em `href` ou de `eval` — investigar.

**Plano de endurecimento (próximas etapas)**

1. Trocar os 172 `onclick`/`onchange` inline por `data-*` + `addEventListener` (mesmo padrão já aplicado em `conselho/informacoes.html` na S1-07).
2. Mover os blocos `<script>`/`<style>` de `base.html` e `login.html` para arquivos em `app/static`.
3. Introduzir `nonce` por resposta para o que restar de inline e então remover `'unsafe-inline'` de `script-src`/`style-src`.
4. Só depois trocar `Report-Only` por `Content-Security-Policy` (enforcing), começando por `default-src`/`frame-ancestors` e mantendo o Report-Only em paralelo por um ciclo.

**Testes:** `tests/test_seguranca_e3_csp.py` (**18**) — header no `/login` e no `/painel`, ausência de header enforcing, as seis diretivas obrigatórias, os hosts nas diretivas certas, hosts de navegação fora da política, ausência de `*`, desligamento por config, política customizada, `/static` sem header, página com Chart.js renderizando (`/relatorios/bi`).

## 5. E4 — logs fora do Git

- `.gitignore`: incluído `instance/error.log*` (o `*.log` existente não cobria `error.log.1`).
- `git rm --cached instance/error.log.1`: remove o rastreamento, mantém o histórico intacto.
- **Divergência registrada:** quando a etapa rodou, `instance/error.log.1` **já não existia no disco** — foi apagado por fonte externa antes desta sessão (o `git status` inicial já mostrava `D instance/error.log.1`). Portanto não houve “arquivo permanece em disco”; o conteúdo continua recuperável no histórico (`git show <commit>:instance/error.log.1`). Nada foi apagado por este trabalho e o histórico **não** foi reescrito — isso permanece no roteiro do S3.

## 6. E5 — senhas expostas nos dumps

**Script:** `scripts/forcar_troca_contas_expostas.py` (dry-run por padrão).

- Lê os quatro dumps do histórico com `git cat-file` (somente leitura): `instance/database.db`, `instance/database.db.bak`, `instance/backups/database-antes-initdb-2026-09-29.db` e `backup_20260923_194945.sql`.
- SQLite é aberto em cópia temporária com `mode=ro`; o `.sql` é `pg_dump` no formato `COPY … FROM stdin` (não há `INSERT INTO`), lido por um parser que respeita o cabeçalho de colunas e os escapes do formato.
- Cruza com a tabela `"user"` de `pautaon` e `pautaon_ensaio` por `SELECT` (`id, email, password, is_active, is_ad_user, first_login`).
- **Nenhum** e-mail, hash ou CPF é impresso — a saída é só de contagens.
- `--aplicar` exige `--autorizar-principal` fora do banco de ensaio, grava backup `.sql` do valor anterior de `first_login` em `instance/backups/` e marca apenas as contas com senha local e hash idêntico ao vazado.
- Gera `.tmp/forcar_troca_producao_<banco>_<carimbo>.sql`, com um `UPDATE` por e-mail (o hash entra no `WHERE`, então a conta só é marcada se a senha ainda for a que vazou). O relatório informa o caminho; o conteúdo não é reproduzido aqui.

**Contagens do dry-run (30/10/2026)**

| Dump | Pares e-mail/hash |
|---|---|
| `instance/database.db` | 7 |
| `instance/database.db.bak` | 9 |
| `instance/backups/database-antes-initdb-2026-09-29.db` | 0 |
| `backup_20260923_194945.sql` | 7 |
| **e-mails distintos** | **15** |

| Banco | Contas | Com senha local | Só LDAP | Inativas | Já `first_login=True` | Mesmo hash do dump | A marcar |
|---|---|---|---|---|---|---|---|
| `pautaon` | 21 | 17 | 4 | 0 | 5 | 6 | 6 |
| `pautaon_ensaio` | 25 | 21 | 4 | 0 | 5 | 6 | 6 |

**Divergência com o S3:** o relatório anterior registrou 9 hashes em `database-antes-initdb-2026-09-29.db`. O blob desse dump tem 438.272 bytes e apenas **4 tabelas** (`alembic_version`, `planejamento`, `registro_pedagogico`, `sqlite_sequence`) — **não existe tabela `user`**, logo o arquivo não contribui com nenhum par. A contagem de 9 hashes não se confirma para esse blob.

**Como aplicar na produção (o agente não acessa essa instância)**

1. Copiar o `.sql` indicado na saída do script (em `.tmp/`) para o servidor de produção.
2. Conferir o conteúdo antes de rodar (há `BEGIN`/`COMMIT`).
3. Aplicar com `psql -f <arquivo>` e conferir `SELECT count(*) FROM "user" WHERE first_login;` antes/depois.
4. Comunicar as contas marcadas; no próximo login o sistema já exige a troca (`first_login` → `/trocar-senha`).

**Testes:** `tests/test_forcar_troca_contas_expostas.py` (**14**) — parser `COPY` (extrai só `user`, ignora outra tabela), leitura de SQLite sintético, arquivo inválido devolvendo vazio, coleta em repositório Git temporário (blob real via `cat-file`), ausência de arquivo sem quebrar, classificação (LDAP, inativa, hash trocado, já marcada), aplicação marcando só as candidatas, geração do `.sql` por e-mail, `main` em dry-run não alterando nada e não imprimindo e-mail/hash, `--aplicar` recusado sem `--autorizar-principal` e aplicação com backup.

## 7. Suíte, ruff e ambiente

- Suíte antes da entrega: **1166 passed** (gate inicial: 1127 passed + 1 falha ambiental por arquivo apagado pelo Nextcloud durante o run).
- Novos testes: 19 (E1) + 6 (E2) + 18 (E3) + 14 (E5) = **57**.
- `ruff check --select F821,F811,F841` limpo em todos os arquivos tocados.
- Sem migration, sem push.

**Ambiente (reportado, não corrigido).** A sincronização do Nextcloud atuou sobre a pasta do projeto durante toda a execução:

- `app/models/academico.py` e `app/templates/base.html` foram revertidos para versões de 06–22/10 (identificadas por hash contra commits antigos);
- `app/models/calendario.py` e `app/templates/dashboard/index.html` foram apagados repetidamente, com `conflicted copy` criada a cada ciclo;
- `.git` e `app/models/academico.py` chegaram a virar *placeholders* do VFS (`ReparsePoint`, tag `0x9000601a`), negando escrita — inclusive do `.git/index.lock`, o que bloqueou commits por um período;
- todas as `conflicted copy` eram byte-idênticas ao HEAD e foram preservadas em `.tmp/seg_b_pre/` (fora do Git); os arquivos foram recriados a partir do HEAD.

**Recomendação:** excluir `.git` (ou a pasta do projeto) da sincronização do Nextcloud.

## 8. Pendências

- **Prompt C** — invalidação de sessão no logout e nas trocas de senha (S1: cookie copiado continua autenticando).
- **Prompt D** — limite de tentativas e tempo de resposta do login (rate limit por IP contornável por NAT/`X-Forwarded-For`; enumeração de usuários por diferença de tempo).
- **Prompt E** — política de senha no cadastro e revisão LGPD dos dados sensíveis.
- **Reescrita do histórico** (`git filter-repo` para os dumps e `instance/error.log.1`): permanece no roteiro do S3, fora deste prompt.
- **Aplicação da E5 nos bancos:** não executada; depende de autorização do usuário após a entrega.
