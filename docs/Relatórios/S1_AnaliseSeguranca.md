# S1 — Análise de segurança (somente leitura)

**Data:** 30/10/2026 · **Branch:** `nova_feature`@`715fe57` · **Sem push**
**Escopo:** análise de segurança da aplicação `pautaon` (código + sondagem com cliente de teste contra `pautaon_ensaio`).
**Natureza:** **nenhum código de aplicação foi alterado**. Este documento, o backlog e os scripts de sondagem (em `.tmp/`, não versionados) são os únicos artefatos.

---

## 1. Método, ambiente e limites

### 1.1 Método

1. **Leitura de código**: `app/__init__.py`, `app/auth.py`, `app/services/auth_service.py`, `config.py`, `run.py`, `app/conselho.py`, `app/registros/*` (alunos, turmas, atendimentos, períodos, shared), `app/relatorios/*`, `app/services/{certificado_modelo,informacao_padrao}.py`, `app/models/*`, templates com `|safe` e scripts inline.
2. **Inventário estático de rotas**: `app.url_map` (207 rotas) cruzado por AST com os decoradores de cada *view* (`@login_required`, `@csrf.exempt`) e com a presença de checagem de papel (`current_user.role` / `abort(403)`) no corpo da função. Gerou a matriz do Apêndice A.
3. **Varredura de padrões de risco**: `text(f"...")`, `ilike(f"...")`, `|safe`, `Markup`, `csrf.exempt`, `eval/exec/pickle/yaml.load`, `subprocess`, segredos literais, `get_json(force=True)`, `secure_filename`/`.save(`, `session.permanent`, `session_protection`, `autoescape`.
4. **Sondagem dinâmica** com o cliente de teste do Flask contra **`pautaon_ensaio`**, com login HTTP real nos usuários `[ROTEIRO]` (senha conhecida do seed), sem tocar no banco principal.
5. **Histórico Git**: `git log --all -- <caminho>`, `git rev-list --all --objects`, `git cat-file`.

### 1.2 Regras de banco respeitadas

- Nenhuma linha pré-existente foi alterada ou apagada.
- As únicas escritas foram: linhas de `log_acao` (login/logout/tentativa falha) e a chave `login_attempts:*` de `configuracao_sistema` — **todas listadas por id antes de remover** e conferidas por contagem.

| Momento | `log_acao` | `configuracao_sistema` |
|---|---|---|
| antes da sondagem final | 1485 | 13 (7 `informacao_padrao.*`, 6 `login_attempts:*`, `manutencao_ativa`) |
| depois da limpeza | **1485** | **13** (lista de chaves idêntica) |

> **Divergência registrada e explicada:** a primeira execução (`.tmp/s1_sonda3.py`) partiu de `configuracao_sistema = 14` e terminou em 13. A linha removida (id 26) era uma chave `login_attempts:<hash>` criada **pelos meus próprios diagnósticos** (POST /login falho em `s1_diag6`/`s1_diag7`) e foi apagada pelo próprio aplicativo (`_clear_failed_attempts`) no primeiro login bem-sucedido. Não era dado de negócio; nenhuma outra contagem mudou. As execuções seguintes passaram a validar a lista de chaves, não só a contagem.

### 1.3 Limites

- **Nenhum bind LDAP foi executado**: os logins da sondagem usam senha local correta e, nos testes de falha, `LDAP_SERVER_URI=None` **apenas na config do harness** (o `.env` não foi alterado). Assim evitou-se qualquer contagem de bloqueio de conta no AD real.
- Sem varredura de rede, sem ataque ao banco principal, sem força bruta.
- HTTPS real, proxy reverso, certificados e headers do IIS/nginx **não** são observáveis a partir do código (ver §5).

---

## 2. (a) Matriz de rotas × proteção

### 2.1 Resumo

| Blueprint | Rotas | Sem `@login_required` | Observação |
|---|---|---|---|
| `registros` | 143 | 0 | todas autenticadas; papel e unidade validados no corpo ou em guardas (`_turma_para_ofertas`, `_periodo_para_modelo_certificado`, `assert_unidade_context`) |
| `auth` | 19 | **4** | `/login`, `/logout` (protegido), `/auth/google/login`, `/auth/google/callback`, `/auth/google/confirmar-vinculo` |
| `conselho` | 13 | 0 | 2 rotas com `@csrf.exempt` e **sem checagem de papel** (S1-05) |
| `relatorios` | 13 | 0 | exportações e BI com escopo de unidade (`_escopar_unidade`) |
| `main` | 9 | **4** | `/`, `/politica_privacidade`, `/termos_servico`, **`/teste-email`** (S1-04) |
| `servico_social` | 6 | 0 | formulários com papel |
| `informacao_padrao` | 2 | 0 | papéis administrativos |
| `planejamento` | 2 | 0 | `_check_calendario_access` |
| **Total** | **207** | **8** | |

### 2.2 As 8 rotas sem `@login_required`

| Método | Rota | Endpoint | Escreve? | Situação |
|---|---|---|---|---|
| GET | `/` | `main.home` | não | pública por desenho (renderiza a tela de login) |
| GET | `/login` | `auth.login` | sessão | pública por desenho; CSRF no POST |
| GET,POST | `/auth/google/login` | `auth.google_login` | sessão (`state`) | pública por desenho |
| GET | `/auth/google/callback` | `auth.google_callback` | sim | pública por desenho, protegida por `state` de 32 bytes em sessão |
| GET,POST | `/auth/google/confirmar-vinculo` | `auth.google_confirmar_vinculo` | sim | pública por desenho; exige `google_link_pending` na sessão (TTL 600 s) |
| GET | `/politica_privacidade` | `main.politica_privacidade` | não | pública por desenho |
| GET | `/termos_servico` | `main.termos_servico` | não | pública por desenho |
| GET | **`/teste-email`** | `main.teste_email` | **envia e-mail** | **achado S1-04** — sem autenticação e sem limite |

`/logout` é `@login_required`; `/login` e `/auth/google/*` são as únicas entradas públicas legítimas. **Não existe rota pública de arquivo**: fotos, documentos do aluno, anexos de atendimento, modelo de certificado e exportações estão todas sob `@login_required` + papel + unidade (ver §4).

### 2.3 Rotas que servem arquivos, exportam ou imprimem

| Rota | Proteção | Verificação adicional |
|---|---|---|
| `/aluno/<id>/foto` | `login_required` + papel | `assert_unidade_context`; professor só vê aluno de oferta ativa em que leciona |
| `/aluno/<id>/documento/<doc_id>` | `login_required` + papel | `assert_unidade_context`; `doc_id` em lista fixa; `secure_filename`; `mimetype` fixo `application/pdf` |
| `/atendimentos/<id>/anexo` | `login_required` + papel | `assert_unidade_context`; `Path(rel).name`; pasta fixa |
| `/periodo-letivo/<id>/certificado-modelo/<centro>/arquivo` | `login_required` + papel | `_periodo_para_modelo_certificado` (papel + unidade) e centro da **mesma** unidade |
| `/relatorios/exportar` (XLSX) | `login_required` + papel | consultas filtradas por `get_unidade_id()` |
| `/relatorios/relatorio_alunos/exportar` (XLSX) | `login_required` + papel | idem |
| `/relatorios/bi/exportar/xlsx` | `login_required` + papel | `_escopar_unidade` → 403 se pedir outra unidade |
| `/planejamento/calendario/<id>/exportar` | `login_required` + papel | `_check_calendario_access` |
| `/conselho/imprimir`, `/turma/<id>/imprimir-pauta`, `/aluno/imprimir/<id>`, `/planejamento/imprimir-temas`, `/turmas/centros-custo/imprimir` | `login_required` + papel | telas server-side, sem dados de outra unidade |

### 2.4 Matriz completa

Ver **Apêndice A** (207 rotas, agrupadas por blueprint, com método, `@login_required`, presença de checagem de papel no corpo e situação de CSRF).

---

## 3. (b) Achados

Legenda de gravidade: **crítica** (compromete todo o sistema / dados pessoais em massa), **alta** (abuso direto por perfil de baixo privilégio ou exposição de dados), **média** (requer condição ou perfil específico), **baixa** (endurecimento/defesa em profundidade).
Esforço: **S** (≤ 1 h), **M** (algumas horas), **L** (≥ 1 dia).

### 3.1 Tabela resumo

| ID | Gravidade | Achado | Evidência | Correção proposta | Esforço |
|---|---|---|---|---|---|
| S1-01 | **crítica** | `SECRET_KEY` com valor fixo de fallback; a proteção só dispara quando `APP_ENV == "production"` | `config.py:49-53`; `.env` com `FLASK_ENV=development` | falhar sempre que `SECRET_KEY` faltar (ou no mínimo exigir ≥ 32 bytes aleatórios e recusar o valor `dev-key-...`); tratar `FLASK_ENV` como alias legado | S |
| S1-02 | **crítica** | `DEBUG` ligado por `FLASK_DEBUG=true` no `.env` em uso; em produção expõe o debugger do Werkzeug (console interativo = execução de código) e desliga a página genérica de erro | `config.py:45-46`; `app/__init__.py:245-253`; `run.py:6`; `.env` | `DEBUG=False` fixo no deploy e remover `FLASK_DEBUG` do `.env` de produção; `run.py` não deve usar `app.config["DEBUG"]` | S |
| S1-03 | **crítica** | Bancos SQLite de desenvolvimento e log de erro **versionados no histórico Git** (dados pessoais de alunos, parâmetros SQL em stack traces) | `git log --all -- instance/` → `instance/database.db` (`175244d`, `8dece84`), `instance/database.db.bak` (`ca4178d`, `f66a731`), `instance/backups/database-antes-initdb-2026-09-29.db` (`38980ef`), `instance/error.log.1` (`2185afe`, blob `98bfd23`, 5,2 MB) | `git filter-repo --path instance/ --invert-paths`, rotação de `SECRET_KEY`/senhas, purga de clones e do histórico do Nextcloud, revisão LGPD (art. 46) | M |
| S1-04 | **alta** | `/teste-email?para=` público: envia e-mail HTML arbitrário para qualquer endereço, sem login e sem limite | `app/main/rota_disparo_email.py:5-27`; `app/main/__init__.py:16`; prova §7.2 | remover a rota do blueprint (ou `@login_required` + papel admin + rate limit + destinatário restrito ao domínio) | S |
| S1-05 | **alta** | `POST /api/conselho-periodo` e `DELETE /api/conselho-periodo/<id>`: `@csrf.exempt` **e** sem checagem de papel — qualquer usuário autenticado (inclusive professor) cria, edita e apaga períodos de conselho da própria unidade | `app/conselho.py:1111-1114`, `1192-1197`; provas §7.3 | exigir papel (`admin`/`pedagogico`/`gerencia`) e remover `@csrf.exempt` (enviar `X-CSRFToken` no `fetch`, como já é feito no calendário) | S |
| S1-06 | **alta** | Logout não invalida a sessão no servidor: cópia do cookie continua autenticando depois do logout em outro dispositivo | `app/auth.py:269-274`; prova §7.4 (B permaneceu autenticada como secretaria após o logout de A) | versão de sessão por usuário (`user.session_token`/`auth_version`, conferida em `before_request`) ou store de sessões no servidor; no logout, incrementar a versão; adicionar expiração absoluta | M |
| S1-07 | **média** | XSS armazenado: nome do período de conselho interpolado dentro de string JS em atributo `onclick` | `app/templates/conselho/informacoes.html:63`; entrada em `salvar_periodo_conselho` (`app/conselho.py:1133`) | passar os dados por `tojson` em `<script>` ou usar `data-*` + `addEventListener`; nunca interpolar em `onclick` | S |
| S1-08 | **média** | Upload de foto do aluno sem validação de extensão/tipo/tamanho; servido inline por `/aluno/<id>/foto` | `app/registros/shared.py:62-67`; `app/registros/alunos.py:1341-1346`; uso em `alunos.py:541` e `645` | whitelist de extensão + verificação de assinatura (Pillow) + limite de bytes; servir com `Content-Disposition: inline` e `X-Content-Type-Options: nosniff` (já existe) e mimetype fixo por tipo permitido | S |
| S1-09 | **média** | Cookie de sessão sem `Secure` e HSTS ausente quando `APP_ENV != production` — o caso do `.env` atual | `config.py:57`; `app/__init__.py:130-133`; prova §7.1 (`secure=False`, sem `Strict-Transport-Security`) | derivar `Secure`/HSTS do esquema real (`request.is_secure`/proxy confiável) e não de `APP_ENV`; documentar `SESSION_COOKIE_SECURE=True` no deploy | S |
| S1-10 | **média** | Nenhuma resposta autenticada envia `Cache-Control`/`Pragma`/`Expires`; o botão Voltar reexibe páginas com dados | `app/__init__.py:123-134`; prova §7.5 (`/painel/secretaria` 200 com apenas `Vary: Cookie`) | `after_request`: `Cache-Control: no-store, private` para respostas autenticadas (e `no-cache` para o login) | S |
| S1-11 | **média** | Rate limit só por IP, persistido em `ConfiguracaoSistema`: NAT compartilhado bloqueia a instituição inteira, não há contador por conta, e `X-Forwarded-For` pode contornar se o app não estiver atrás de proxy confiável | `app/auth.py:41-105`, `136-146`; `app/__init__.py:19` (`ProxyFix(x_for=1)`); provas §7.6 (bloqueio atingiu login válido) | contador por conta + por IP, backoff progressivo, IP real vindo de proxy confiável (`ProxyFix` só quando `TRUSTED_PROXY=1`), desbloqueio administrativo | M |
| S1-12 | **média** | Enumeração de usuários por tempo: usuário existente ≈ 120 ms, inexistente ≈ 19 ms (caminho local, sem LDAP) | `app/auth.py:189`; prova §7.7 | executar `check_password` contra um hash *dummy* quando o usuário não existir (custo constante) | S |
| S1-13 | **média** | Senha inicial definida pelo admin **sem política de força** e enviada em texto claro por e-mail (cadastro e reset) | `app/auth.py:512-562`, `590-631`; `validate_password_strength` só é usada em `/trocar-senha` (`app/auth.py:955`) | exigir `validate_password_strength` no cadastro; enviar link de definição de senha com token de uso único em vez da senha | M |
| S1-14 | **média** | Nenhuma `Content-Security-Policy`; `X-Frame-Options`, `nosniff` e `Referrer-Policy` já existem | `app/__init__.py:123-134`; prova §7.1 | CSP com `default-src 'self'` e nonces/`unsafe-inline` apenas onde inevitável (há muitos `onclick` inline — S1-07) | M |
| S1-15 | **média** | `ProxyFix(x_for=1, x_proto=1, x_host=1)` confia em cabeçalhos do cliente se não houver proxy na frente | `app/__init__.py:19` | condicionar a `TRUSTED_PROXY`/variável de ambiente e documentar no manual de deploy | S |
| S1-16 | **baixa** | Estado alterado por GET: `/logout` e `/trocar-unidade/<id>` | `app/auth.py:269-274`; `app/main/unidade.py:12-25` | POST + CSRF; logout por POST | S |
| S1-17 | **baixa** | Injeção de fórmula em XLSX: valor iniciado por `=` vira fórmula no arquivo exportado | `app/relatorios/alunos.py:228-235`; `app/relatorios/geral.py:153-176`; prova §7.8 | prefixar `'` (ou `\t`) em células que comecem com `= + - @` antes de exportar, ou `strings_to_formulas=False` | S |
| S1-18 | **baixa** | `ldap3==2.10.2rc3` (release candidate) em uso; `pip-audit` não está instalado no venv | `pip list`; `python -m pip_audit` → “No module named pip_audit” | fixar `ldap3` estável e adicionar `pip-audit -r requirements.txt` ao CI | S |
| S1-19 | **baixa** | Logs de segurança guardam e-mail tentado + IP (`detalhes`, `ip`); retenção de 30 dias sem base legal documentada | `app/services/auth_service.py:59-68`; `app/auth.py:256`; `app/auth.py:820-851` | pseudonimizar o alvo (`hash`) ou restringir o campo; documentar finalidade/retenção (LGPD art. 16) | S |
| S1-20 | **baixa** | `_simple_markdown_to_html` produz HTML sem escape e lê arquivo de `static/uploads`; hoje o template **não** renderiza `content` (código morto) | `app/main/home.py:17-60`; `app/templates/termos/*.html` (conteúdo fixo) | remover a função/rotas mortas ou usar um renderizador Markdown com sanitização | S |
| S1-21 | **baixa** | Senha fixa no seed (`Roteiro!2026`) e senha de exemplo no `.env.example` | `scripts/semear_roteiro_manual.py:53`; `.env.example:12` | exigir senha por argumento/ambiente no seed e marcar o exemplo como inválido | S |
| S1-22 | **baixa** | `editar_usuario` grava `role` sem validar o enum e `email` sem validação/unicidade | `app/auth.py:565-587` | validar contra `UserRole` e normalizar/validar o e-mail | S |
| S1-23 | **baixa** | Google: `state` é consumido antes de ser validado (um `state` inválido invalida o fluxo legítimo) e o vínculo dispensa senha quando o usuário local não tem senha | `app/auth.py:346-350`, `893-905` | validar antes do `pop`; exigir senha ou confirmação por e-mail para contas sem senha local | S |
| S1-24 | **baixa** | Dados sensíveis (saúde, diversidade, socioeconômico, atendimentos) acessíveis a vários perfis operacionais na ficha 360 | `app/relatorios/painel_pedagogico/rota.py:216-252`; `app/registros/atendimentos.py:27` | revisar matriz de necessidade por perfil e registrar log de acesso a dados sensíveis | M |

### 3.2 Fichas dos achados principais

#### S1-01 — `SECRET_KEY` com fallback fixo (crítica)

`config.py` só levanta exceção quando `APP_ENV == "production"`; em qualquer outro valor a chave vira a constante pública `dev-key-substituir-em-producao` (linhas 49-53). O `.env` em uso define `FLASK_ENV=development`, que `Config.APP_ENV` aceita como valor (linha 45). Com a chave conhecida, o cookie de sessão do Flask (cliente, assinado, sem store no servidor) pode ser **forjado**, incluindo `_user_id` de um admin — não é preciso senha.

*Impacto no contexto LDAPS + HTTPS:* o TLS protege o transporte, mas não ajuda: a forja é local ao atacante. Se o deploy herdar o `.env` de desenvolvimento (cenário provável, já que é o mesmo arquivo usado hoje), o controle de acesso inteiro cai.

*Correção:* falhar na inicialização quando `SECRET_KEY` não estiver definida, independentemente de `APP_ENV`; rejeitar explicitamente o valor `dev-key-*`; documentar geração com `secrets.token_urlsafe(48)`.

#### S1-02 — `DEBUG` verdadeiro (crítica, condicional ao deploy)

`Config.DEBUG = get_bool("FLASK_DEBUG", APP_ENV == "development")` e o `.env` traz `FLASK_DEBUG=true`. `run.py:6` passa esse valor para `app.run(debug=...)`. Com `DEBUG=True`, `_register_error_handlers` faz `raise e` (linhas 245-253), devolvendo a página de depuração do Werkzeug — que inclui console interativo (execução de código no servidor) quando alcançável.

*Correção:* `DEBUG=False` no processo de produção (não depender de `APP_ENV`), remover `FLASK_DEBUG` do `.env` publicado e nunca rodar `run.py` como servidor de produção (usar `waitress`/`gunicorn`).

#### S1-03 — Dados pessoais no histórico Git (crítica)

O `.gitignore` atual cobre `instance/*.db`, `instance/backups/` e `*.log`, e `git ls-files` confirma que nada disso está em `HEAD`. Porém o histórico contém:

| Caminho | Commits | Tamanho | Conteúdo |
|---|---|---|---|
| `instance/database.db` | `175244d`, `8dece84` | — | banco SQLite de desenvolvimento (tabelas `aluno`, `user`, …) |
| `instance/database.db.bak` | `ca4178d`, `f66a731` | — | idem |
| `instance/backups/database-antes-initdb-2026-09-29.db` | `38980ef` e outros | 438.272 B | schema completo com dados (`CREATE TABLE aluno`, `CREATE TABLE user`) |
| `instance/error.log.1` | `2185afe` e outros | 5.199.585 B | stack traces com `effective_parameters` de consultas |

*Impacto:* dados de menores (nome, CPF, endereço, saúde) no histórico de um repositório que, neste ambiente, é sincronizado por Nextcloud. É um incidente de LGPD (art. 46/48) e sobrevive a qualquer `git rm`.

*Correção:* reescrever o histórico (`git filter-repo --invert-paths --path instance/`), rotacionar `SECRET_KEY` e senhas de banco/LDAP presentes em arquivos vizinhos, purgar clones/backups do Nextcloud e avaliar notificação. **Não executado** nesta análise.

#### S1-04 — `/teste-email` público (alta)

`app/main/rota_disparo_email.py` registra `@bp.route("/teste-email")` sem `@login_required` e envia HTML para `request.args.get("para")`. Prova em §7.2: `GET /teste-email?para=alvo@example.com` → **200** com `send_email(recipients=['alvo@example.com'])` (função substituída por mock para não disparar e-mail real).

*Impacto:* relay de e-mail autenticado por SPF/DKIM da instituição — phishing, spam e queima de reputação do domínio; sem rate limit, também consumo de cota do Google Workspace.

#### S1-05 — Períodos de conselho sem autorização e sem CSRF (alta)

As duas rotas AJAX de `app/conselho.py` têm `@csrf.exempt` e apenas `@login_required`. `GET /conselho/informacoes` também não restringe papel. Prova em §7.3: `POST /api/conselho-periodo` sem token → **400 JSON da própria *view*** (o CSRF não barrou) e `DELETE /api/conselho-periodo/999999` → **404 JSON** (a *view* executou). Na rota protegida equivalente (`POST /admin/manutencao/toggle`) o mesmo teste devolve **400 HTML** de CSRF.

*Impacto:* um professor (ou secretaria) pode apagar o período de conselho da unidade; combinado com `SameSite=Lax`, a janela cross-site é estreita, mas subdomínios irmãos do mesmo site (comum em rede AD) enviam o cookie.

#### S1-06 — Logout não invalida a sessão (alta)

`logout()` executa `logout_user()`, que apenas remove `_user_id` da sessão **daquele** cookie. Como a sessão é um cookie assinado e não há store no servidor, uma cópia anterior continua válida até o `PERMANENT_SESSION_LIFETIME` (60 min deslizantes). Prova em §7.4.

*Impacto:* um cookie capturado (estações compartilhadas, backup de navegador, XSS de S1-07/S1-08) permanece utilizável depois de o usuário “sair”; não há como o usuário ou o admin revogarem a sessão.

#### S1-07 — XSS armazenado no nome do período de conselho (média)

`app/templates/conselho/informacoes.html:63` interpola `{{ c.nome }}` dentro de uma string JavaScript em `onclick="editConselho(..., '{{ c.nome }}', ...)"`. O Jinja escapa `'` como `&#39;`, mas o parser HTML **decodifica** a entidade antes de o JS ser avaliado, então um nome como `x');alert(document.cookie);//` quebra a string e executa. `c.nome` vem de `salvar_periodo_conselho` (`app/conselho.py:1133`) sem sanitização.

*Impacto:* persiste para todos que abrirem a tela de Conselho (incluindo outros administradores) — captura de sessão de admin, ainda mais grave por causa de S1-06.

#### S1-08 — Upload de foto do aluno sem validação (média)

`salvar_foto` (`app/registros/shared.py:62-67`) grava `aluno_{id}_{secure_filename(filename)}` **sem checar extensão, mimetype ou tamanho**; `foto_aluno` (`alunos.py:1341-1346`) serve o arquivo com `send_from_directory` (mimetype inferido pela extensão). Um `.html`/`.svg` enviado como foto é servido como página no domínio da aplicação.

*Impacto:* XSS armazenado no domínio, além de consumo de disco sem limite (o restante dos uploads tem limite: 2 MB em atendimentos, 5 MB em certificado, 3 MB em informação padrão).

#### S1-09 / S1-10 / S1-14 — Cabeçalhos e cookies observados

| Item | Resultado observado (30/10/2026, `.env` atual) |
|---|---|
| `Set-Cookie` após login | `session=…; Expires=+60min; HttpOnly; Path=/; SameSite=Lax` — **sem `Secure`** |
| `X-Frame-Options` | `SAMEORIGIN` |
| `X-Content-Type-Options` | `nosniff` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Strict-Transport-Security` | **ausente** (só em `APP_ENV=production`) |
| `Content-Security-Policy` | **ausente** |
| `Cache-Control` em `/painel/secretaria` | **ausente** (só `Vary: Cookie`) |
| Redirecionamento HTTP→HTTPS | **não existe no código** |

#### S1-11 / S1-12 — Rate limit e enumeração

- O contador vive em `ConfiguracaoSistema` com chave `login_attempts:<sha256(ip)[:32]>`; 5 falhas em 900 s bloqueiam o IP por 15 min. Prova em §7.6: depois do bloqueio, **o login válido do admin também é recusado**.
- O bloqueio é por IP: toda a instituição atrás de um NAT compartilha a cota; e `request.remote_addr` vem de `ProxyFix(x_for=1)`, portanto um `X-Forwarded-For` forjado (quando não há proxy confiável) muda a chave.
- Mensagem de erro é sempre “Credenciais recusadas pelo domínio e banco de dados.” (não enumera por texto), mas o tempo varia ~6x (§7.7) porque `check_password` só roda quando o usuário existe.

#### S1-13 — Senha inicial em texto claro

`cadastrar_usuario` aceita a senha do formulário sem `validate_password_strength` e a envia no corpo do e-mail (`app/auth.py:534-554`); `resetar_senha` faz o mesmo com `ADMIN_DEFAULT_PASSWORD` (`603-623`). `first_login=True` obriga a troca, mas a senha fraca vale até lá e fica registrada no e-mail.

---

## 4. (c) O que foi verificado e está correto

### 4.1 Autorização e isolamento de unidade

| Verificação | Resultado |
|---|---|
| `get_unidade_id()` força a unidade do usuário para todo perfil que não seja `admin`/`gerencia` (ignora sessão *stale*) | `app/utils/logica.py:184-205` |
| Ficha 360 de aluno de outra unidade | `GET /relatorios/alunos/1340/ficha` (unidade 2, logado como pedagógico da 13) → **404** |
| Histórico do aluno de outra unidade | `GET /aluno/1340/historico` → **403** |
| Foto de aluno de outra unidade | `GET /aluno/1340/foto` → **403** |
| BI pedindo `unidade_id` de outra unidade | `GET /relatorios/bi/exportar/xlsx?...&unidade_id=2` → **403** (`_escopar_unidade`) |
| Painel administrativo e logs por perfil não-admin | `GET /admin/logs` como pedagógico → **403** |
| Troca de contexto de unidade por perfil operacional | `GET /trocar-unidade/2` como pedagógico → **403** |
| Escrita de conselho em turma de outra unidade | `assert_unidade_context` em `app/conselho.py:693` |
| Ofertas de turma | `_turma_para_ofertas` valida papel **e** unidade (`app/registros/turmas.py:2059-2067`) |
| Modelo de certificado | `_periodo_para_modelo_certificado` (papel + unidade) e centro da mesma unidade (`app/registros/periodos.py:629-652`) |
| Calendário | `_check_calendario_access` + `assert_unidade_context` (`app/registros/periodos.py:87-91`, `208-218`) |
| Cadastro de aluno por usuário global | unidade do formulário só é aceita quando `get_unidade_id()` é `None` (`app/registros/alunos.py:471-488`) |

### 4.2 Arquivos servidos

- **Fotos, documentos e anexos** não têm rota pública: todas exigem `login_required`, papel e unidade, e o professor só alcança aluno de oferta ativa em que leciona (`app/registros/alunos.py:1309-1335`).
- **Documento do aluno**: `doc_id` em lista fixa, `secure_filename`, `mimetype="application/pdf"` fixo.
- **Anexo de atendimento**: extensão em whitelist (`pdf, doc, docx, odt, rtf, txt, png, jpg, jpeg`), limite de 2 MB, `Path(rel).name` e pasta fixa (`app/registros/atendimentos.py:50-80`, `450-480`).
- **Modelo de certificado**: grava fora de `static` (`instance/uploads/certificados/<periodo>/`), PNG/JPG/WEBP, 5 MB, nome com timestamp + uuid (`app/services/certificado_modelo.py:31-35`, `162-196`).
- **Assets institucionais** (logo/favicon/foto padrão): whitelist de extensão, 3 MB, nome seguro (`app/services/informacao_padrao.py:27-32`, `115-137`).
- **Path traversal**: `_build_upload_path` resolve o caminho e recusa sair da raiz (`app/registros/shared.py:47-60`); `_pasta_modelos` idem (`app/services/certificado_modelo.py:45-51`).

### 4.3 CSRF

- `CSRFProtect` inicializado globalmente (`app/__init__.py:62`), com token nos formulários e header `X-CSRFToken` nos `fetch` (60 ocorrências nos templates; ex.: `app/static/js/periodo_letivo_calendario.js:76-77`, `511`; `app/templates/alunos/gerenciar.html:544`).
- Prova: `POST /login` sem token → **400**; `POST /admin/manutencao/toggle` sem token → **400 HTML** (CSRF).
- Exceções conscientes: apenas as duas rotas de `conselho` (S1-05).

### 4.4 Injeção de SQL

- **Nenhum `text(f"...")`, `execute(f"...")` ou `exec_driver_sql` em `app/`** — as 39 ocorrências do padrão estão em `scripts/`, `migrations/` e `tests/`, com nomes de tabela/coluna constantes de módulo, não de entrada do usuário.
- Os `ilike(f"%{termo}%")` (`auth.py:758`, `alunos.py:245-363`, `atendimentos.py:155-156`, `turmas.py:518`, `relatorios/shared.py:96-102`) passam o valor como **parâmetro** do SQLAlchemy; o risco residual é só o curinga `%`/`_` do usuário (busca mais ampla, sem injeção).
- Consultas administrativas usam `select()`/ORM.

### 4.5 XSS e templates

- `autoescape` do Jinja **ativo** (nenhum `autoescape = False`); nenhum `Markup(`/`markupsafe` no código.
- Os 7 usos de `|safe` são todos `{{ … | tojson | safe }}`, que escapa `<`, `>`, `&` e `'` como `\uXXXX` — padrão correto para embutir JSON (`calendario.html:255-258`, `painel_pedagogico.html:424`, `servico_social/forms/*.html:261/299`).
- A única interpolação insegura encontrada é a de S1-07.

### 4.6 Sessão, cookies e login

- `SESSION_COOKIE_HTTPONLY=True`, `SESSION_COOKIE_SAMESITE=Lax`, `PERMANENT_SESSION_LIFETIME=60 min` deslizante (`session.permanent=True` em `auth.py:238/474/919`), cookie com `Expires` coerente.
- `login_user()` sem `remember`, portanto **não** há cookie `remember_token` persistente de 8 h (a configuração existe, mas não é usada).
- Mensagem de falha sempre genérica (“Credenciais recusadas pelo domínio e banco de dados.”), sem distinguir usuário inexistente, senha errada, conta inativa ou LDAP fora.
- Rate limit de 5 falhas/900 s por IP (efetivo, prova §7.6).
- `first_login` e `PENDENTE` são bloqueados no `before_request` (`app/__init__.py:90-121`), com rotas de escape explícitas; o teste `test_pending_user_redirected_to_approval_screen` cobre.
- `/trocar-senha` exige a senha atual (exceto no primeiro login), aplica complexidade, impede reutilizar a senha atual (`auth.py:944-976`).
- Sem `next` em `/login` (nenhum parâmetro de redirecionamento) → **não há open redirect**; `select-string` por `args.get('next')` retorna 0 ocorrências.
- CORS: não há `flask-cors` nem `Access-Control-Allow-Origin`; requisições cross-origin não leem respostas.

### 4.7 LDAP/AD

- Bind **direto** com UPN (`user=...`, `password=...`) e `auto_bind=True`; **não há bind anônimo** e **nenhum filtro LDAP é construído com entrada do usuário** → injeção de filtro LDAP não se aplica.
- TLS: `use_ssl=True` (636), `Tls(validate=ssl.CERT_REQUIRED)` por padrão, `PROTOCOL_TLSv1_2`, CA configurável por `LDAP_CA_CERT_FILE`, `connect_timeout` de 10 s (`app/services/auth_service.py:31-68`, `config.py:71-78`).
- Falha de bind e falha de conexão resultam na mesma resposta ao usuário.
- Auto-provisionamento sempre como `PENDENTE` (`auth.py:196-213`), sem acesso operacional até aprovação.

### 4.8 Google OAuth (já implementado)

- `state` de 32 bytes em sessão, conferido no callback (`auth.py:303-305`, `346-350`).
- `email_verified` exigido (`GOOGLE_OAUTH_REQUIRE_EMAIL_VERIFIED=True`), domínios permitidos por lista, vínculo com conta existente exige senha local, provisionamento novo entra como `PENDENTE` (`auth.py:407-486`).

### 4.9 Erros e segredos

- Handlers de 403/404/HTTPException/Exception renderizam páginas genéricas e **não** devolvem stack trace quando `DEBUG` está desligado (`app/__init__.py:245-300`).
- `.env` **não** está versionado (`.gitignore` + `git log --all -- .env` vazio); `.env.example` não contém segredo real.
- Nenhum `eval`, `exec`, `pickle.loads`, `yaml.load` ou `subprocess` em `app/`.

### 4.10 Cobertura de testes existente

`tests/test_security_regressions.py` (15 testes) já fixa: login local auditado, redirecionamento de `PENDENTE`, `first_login`, troca de senha com senha atual, `assert_unidade_context`, enturmação/desenturmação por papel e unidade, histórico do aluno para professor não relacionado, API de alunos por papel, rejeição de GET em rotas mutantes e isolamento de cursos.

---

## 5. (d) O que NÃO pôde ser verificado

| Item | Por que não | Como o usuário confere |
|---|---|---|
| HTTPS real, TLS, redirecionamento HTTP→HTTPS, HSTS no fio | não há servidor web no harness; o código não faz o redirect | `curl -I http://<host>/painel` (deve 301/308 para https) e `curl -sI https://<host>/login \| grep -i strict` |
| Certificado do LDAPS (cadeia, hostname, revogação) | exigiria conexão real; proibido tocar no AD | `openssl s_client -connect <host>:636 -showcerts` ou `ldp.exe` do Windows |
| Proxy reverso e confiança em `X-Forwarded-*` | depende do IIS/nginx | conferir `proxy_set_header X-Forwarded-For` (nginx) ou `ARR` (IIS) e se o app aceita conexão direta na porta 5000 |
| Cifras/versões TLS aceitas | idem | `nmap --script ssl-enum-ciphers -p 443 <host>` (autorizado) ou SSL Labs |
| Backup e criptografia em repouso do PostgreSQL | fora do escopo | `pg_dump` cifrado + teste de restauração; verificar volume BitLocker/LUKS |
| Vulnerabilidades em dependências | `pip-audit` não instalado no venv | `.\.venv\Scripts\python.exe -m pip install pip-audit` e `pip-audit -r requirements.txt` (não é instalação global) |
| Configuração do cliente OAuth no Google Cloud | console externo | conferir *Authorized redirect URIs* e *Test users*/domínio interno |
| Outros clones do repositório (histórico com os `.db`) | não há acesso | `git log --all -- instance/` em cada clone; verificar backups do Nextcloud |
| Retenção/rotação dos logs do servidor | fora do código | política de retenção do IIS/nginx e do `instance/error.log` |
| Ausência de malware/backdoor no host | fora do escopo | EDR/antivírus e integridade dos arquivos do deploy |

---

## 6. (e) Ordem sugerida de correção (prompts pequenos)

| # | Prompt | Achados | Pré-requisito |
|---|---|---|---|
| 1 | “Endurecer `SECRET_KEY`/`DEBUG`: falhar sem chave, rejeitar `dev-key-*`, `DEBUG=False` fora de desenvolvimento, `run.py` sem depender de `DEBUG`” | S1-01, S1-02 | nenhum |
| 2 | “Remover `instance/` do histórico Git com `git filter-repo`, rotacionar segredos e documentar o incidente” | S1-03 | janela de manutenção; aviso a todos os clones |
| 3 | “Fechar `/teste-email` (remover do blueprint ou admin + limite)” | S1-04 | nenhum |
| 4 | “Autorizar e proteger CSRF das rotas `/api/conselho-periodo` (+ teste de 403 por papel)” | S1-05 | nenhum |
| 5 | “Invalidação de sessão no logout: versão de sessão por usuário + teste do cookie copiado” | S1-06 | migration |
| 6 | “Trocar o `onclick` de `conselho/informacoes.html` por `data-*` + `tojson`” e “validar upload de foto (extensão, assinatura, tamanho)” | S1-07, S1-08 | nenhum |
| 7 | “Cabeçalhos: `Cache-Control: no-store` autenticado, CSP inicial, `Secure`/HSTS pelo esquema real, `ProxyFix` condicional” | S1-09, S1-10, S1-14, S1-15 | definir CSP com o front |
| 8 | “Rate limit por conta + por IP com IP confiável; hash *dummy* para igualar tempo de login” | S1-11, S1-12 | nenhum |
| 9 | “Política de senha no cadastro admin e troca do envio de senha por link de definição” | S1-13 | e-mail |
| 10 | “Baixos: logout/troca de unidade por POST, escape de fórmula no XLSX, `ldap3` estável + `pip-audit` no CI, PII em log, validação de `role`/`email` no admin, `state` do Google” | S1-16…S1-23 | nenhum |
| 11 | “Revisar matriz de acesso a dados sensíveis (LGPD) e log de acesso” | S1-24 | decisão de negócio |

Ordem racional: 1 e 2 primeiro (eliminam o comprometimento total e o vazamento histórico); 3, 4 e 5 na sequência (abuso direto); 6 e 7 depois (XSS e exposição no navegador); 8 a 11 por último.

---

## 7. Anexos — evidências de sondagem

Todas as provas abaixo foram obtidas com `app.test_client()` contra **`pautaon_ensaio`**, sem `app_context` empilhado durante as requisições (a sessão do Flask vive no *app context* e vazaria entre requests, falseando CSRF e login), e com login HTTP real nos usuários `[ROTEIRO]`.

### 7.1 Cabeçalhos e cookie (anônimo e autenticado)

```
GET /                         -> 200  X-Frame-Options=SAMEORIGIN | X-Content-Type-Options=nosniff |
                                      Referrer-Policy=strict-origin-when-cross-origin |
                                      Set-Cookie=session=…; HttpOnly; Path=/; SameSite=Lax
GET /painel (anônimo)         -> 302 /login?next=%2Fpainel
GET /aluno/1340/foto (anôn.)  -> 302 /login?next=%2Faluno%2F1340%2Ffoto
GET /static/img/logo.png      -> 200  Cache-Control=no-cache
POST /login (sem token)       -> 400  text/html
POST /login (pedagógico)      -> 302 /painel
GET /painel (pedagógico)      -> 200  Set-Cookie=session=…; Expires=+60min; HttpOnly; Path=/; SameSite=Lax
                                      (sem Strict-Transport-Security, sem Content-Security-Policy)
```

### 7.2 `/teste-email` sem login (S1-04)

```
GET /teste-email?para=alvo@example.com -> 200
send_email.called=True  recipients=['alvo@example.com']
{"mensagem": "Solicitação de e-mail enviada para a fila de execução para o endereço alvo@example.com.",
 "status": "sucesso"}
```

### 7.3 CSRF: rota protegida × rotas isentas (S1-05)

| Requisição (autenticado como admin da unidade 13) | Resultado |
|---|---|
| `POST /admin/manutencao/toggle` sem token | **400** `text/html` (CSRF barrou) |
| `POST /api/conselho-periodo` sem token, corpo vazio | **400** `application/json` — resposta da própria *view* (`"Requisição inválida (JSON não recebido)."`) |
| `DELETE /api/conselho-periodo/999999` sem token | **404** `application/json` — a *view* executou e não achou o conselho |

### 7.4 Logout e cópia do cookie (S1-06)

```
login A (secretaria.m1)          -> 302 /painel
A  GET /admin/logs               -> 403          (autenticada como secretaria)
B  cookie copiado  GET /admin/logs -> 403        (a cópia autentica)
A  GET /logout                   -> 302 /login
A  GET /admin/logs depois        -> 302 /login?next=%2Fadmin%2Flogs   (deslogada)
B  GET /admin/logs depois        -> 403          (a cópia CONTINUA autenticada)
```

### 7.5 Cache de página autenticada (S1-10)

```
GET /painel/secretaria -> 200 | Cache-Control=None | Pragma=None | Expires=None | Vary=Cookie
```

### 7.6 Rate limit por IP (S1-11)

```
falha 1 a 4 (fantasma@roteiro.local) -> 200/302; a partir da 5ª: mensagem "Muitas tentativas de login
foram detectadas. Tente novamente mais tarde." no /login
login válido (admin.m1@roteiro.local) durante o bloqueio -> recusado, permanece em /login
chave criada: login_attempts:12ca17b49af2289436f303e0166030a2 = [5 timestamps]
```

### 7.7 Tempo de resposta do login falho (S1-12, sem LDAP no harness)

```
existente   (pedagogico.m1) -> 200  120,8 ms  "Credenciais recusadas pelo domínio e banco de dados."
inexistente (fantasma)      -> 200   18,8 ms  "Credenciais recusadas pelo domínio e banco de dados."
existente2  (admin.m1)      -> 200  113,5 ms  "Credenciais recusadas pelo domínio e banco de dados."
```

### 7.8 Injeção de fórmula no XLSX (S1-17)

`pandas.DataFrame({"Nome": ["=HYPERLINK(...)", "+1+1", "@SUM(A1)", "-2+3"]})` com `ExcelWriter(engine="xlsxwriter")` gera, no `sheet1.xml`:

```xml
<c r="A2"><f>HYPERLINK("http://x","clique")</f><v>0</v></c>   <!-- fórmula -->
<c r="A3" t="s">…</c>  <c r="A4" t="s">…</c>  <c r="A5" t="s">…</c>  <!-- texto -->
```

### 7.9 Contagens de banco

| Momento | `log_acao` | `configuracao_sistema` |
|---|---|---|
| antes | 1485 | 13 (7 `informacao_padrao.*`, 6 `login_attempts:*`, `manutencao_ativa`) |
| depois da limpeza | 1485 | 13 (mesma lista de chaves) |

### 7.10 Script de prova (não versionado)

O roteiro completo está em `.tmp/s1_sonda3.py` e `.tmp/s1_sonda4.py` (ignorados pelo Git). O núcleo, reproduzível:

```python
from app import create_app
from config import Config

class S1Config(Config):
    SECRET_KEY = "s1-analise"
    SQLALCHEMY_DATABASE_URI = "<URL do pautaon_ensaio>"
    TESTING = False
    WTF_CSRF_ENABLED = True
    LDAP_SERVER_URI = None          # nenhum bind no AD

app = create_app(S1Config)

def entrar(cli, email, senha="Roteiro!2026"):
    pagina = cli.get("/login").get_data(as_text=True)
    token = re.search(r'name="csrf_token"\s+value="([^"]+)"', pagina).group(1)
    return cli.post("/login", data={"email": email, "password": senha, "csrf_token": token},
                    follow_redirects=False)

a = app.test_client(); entrar(a, "secretaria.m1@roteiro.local")
copia = a.get_cookie("session").value
b = app.test_client(); b.set_cookie("session", copia, domain="localhost")
a.get("/logout")
assert b.get("/admin/logs").status_code == 403   # cópia ainda autentica -> S1-06
```

> As requisições foram feitas **fora** de um `app_context` já empilhado; dentro dele, a sessão do Flask é compartilhada entre requests e o CSRF/login passam a dar falso negativo.

---

## Apêndice A — Matriz completa (207 rotas)

Colunas: **Papel no corpo** indica a presença de `current_user.role`/`abort(403)` na função (pode haver guarda em função auxiliar, indicada nas seções anteriores); **CSRF** indica `@csrf.exempt` ou cobertura pelo `CSRFProtect` global.

#### `registros (alunos, turmas, períodos, aulas, centros de custo)` — 143 rotas

| Método | Rota | `login_required` | Papel no corpo | CSRF |
|---|---|---|---|---|
| `POST` | `/aluno/<int:aluno_id>/atualizar-nivel` | sim | role | coberto |
| `GET` | `/aluno/<int:aluno_id>/documento/<doc_id>` | sim | role | coberto |
| `GET` | `/aluno/<int:aluno_id>/foto` | sim | role | coberto |
| `GET` | `/aluno/<int:aluno_id>/historico` | sim | role | coberto |
| `GET` | `/aluno/<int:aluno_id>/info-professor` | sim | role | coberto |
| `GET,POST` | `/aluno/editar/<int:id>` | sim | role | coberto |
| `POST` | `/aluno/excluir/<int:id>` | sim | role | coberto |
| `GET` | `/aluno/imprimir/<int:id>` | sim | role | coberto |
| `POST` | `/aluno/inativar/<int:id>` | sim | role | coberto |
| `GET,POST` | `/aluno/novo` | sim | role | coberto |
| `GET,POST` | `/aluno/transferir/<int:aluno_id>` | sim | role | coberto |
| `GET` | `/alunos` | sim | role | coberto |
| `GET` | `/alunos/<int:aluno_id>/atendimentos` | sim | role | coberto |
| `POST` | `/alunos/<int:aluno_id>/atendimentos/novo` | sim | role | coberto |
| `GET` | `/alunos/atendimentos` | sim | role | coberto |
| `GET` | `/alunos/atendimentos/transicao` | sim | role | coberto |
| `GET` | `/alunos/instituicoes` | sim | — | coberto |
| `GET` | `/api/alunos/<int:turma_id>` | sim | role | coberto |
| `GET` | `/atendimentos/<int:id>` | sim | role | coberto |
| `GET` | `/atendimentos/<int:id>/anexo` | sim | role | coberto |
| `POST` | `/atendimentos/<int:id>/editar` | sim | role | coberto |
| `POST` | `/atendimentos/<int:id>/excluir` | sim | role | coberto |
| `GET` | `/centro-custo` | sim | role | coberto |
| `POST` | `/centro-custo/<int:centro_id>/editar` | sim | role | coberto |
| `POST` | `/centro-custo/<int:centro_id>/inativar` | sim | role | coberto |
| `POST` | `/centro-custo/<int:centro_id>/reativar` | sim | role | coberto |
| `GET` | `/centro-custo/inativos` | sim | role | coberto |
| `POST` | `/centro-custo/novo` | sim | role | coberto |
| `GET` | `/centro-de-custo` | sim | role | coberto |
| `POST` | `/centro-de-custo/<int:centro_id>/editar` | sim | role | coberto |
| `POST` | `/centro-de-custo/<int:centro_id>/inativar` | sim | role | coberto |
| `POST` | `/centro-de-custo/<int:centro_id>/reativar` | sim | role | coberto |
| `GET` | `/centro-de-custo/inativos` | sim | role | coberto |
| `POST` | `/centro-de-custo/novo` | sim | role | coberto |
| `GET` | `/centro_custo` | sim | role | coberto |
| `POST` | `/centro_custo/<int:centro_id>/editar` | sim | role | coberto |
| `POST` | `/centro_custo/<int:centro_id>/inativar` | sim | role | coberto |
| `POST` | `/centro_custo/<int:centro_id>/reativar` | sim | role | coberto |
| `GET` | `/centro_custo/inativos` | sim | role | coberto |
| `POST` | `/centro_custo/novo` | sim | role | coberto |
| `GET` | `/centros-custo` | sim | role | coberto |
| `GET` | `/centros-custo` | sim | role | coberto |
| `GET` | `/centros-custo` | sim | role | coberto |
| `GET` | `/centros-custo` | sim | role | coberto |
| `GET` | `/centros-custo` | sim | role | coberto |
| `GET` | `/centros-custo` | sim | role | coberto |
| `GET` | `/centros-custo` | sim | role | coberto |
| `GET` | `/centros-custo` | sim | role | coberto |
| `POST` | `/centros-custo/<int:centro_id>/editar` | sim | role | coberto |
| `POST` | `/centros-custo/<int:centro_id>/editar` | sim | role | coberto |
| `POST` | `/centros-custo/<int:centro_id>/editar` | sim | role | coberto |
| `POST` | `/centros-custo/<int:centro_id>/inativar` | sim | role | coberto |
| `POST` | `/centros-custo/<int:centro_id>/inativar` | sim | role | coberto |
| `POST` | `/centros-custo/<int:centro_id>/inativar` | sim | role | coberto |
| `POST` | `/centros-custo/<int:centro_id>/reativar` | sim | role | coberto |
| `POST` | `/centros-custo/<int:centro_id>/reativar` | sim | role | coberto |
| `POST` | `/centros-custo/<int:centro_id>/reativar` | sim | role | coberto |
| `GET` | `/centros-custo/inativos` | sim | role | coberto |
| `GET` | `/centros-custo/inativos` | sim | role | coberto |
| `GET` | `/centros-custo/inativos` | sim | role | coberto |
| `GET` | `/centros-custo/inativos` | sim | role | coberto |
| `POST` | `/centros-custo/novo` | sim | role | coberto |
| `POST` | `/centros-custo/novo` | sim | role | coberto |
| `POST` | `/centros-custo/novo` | sim | role | coberto |
| `POST` | `/centros-custo/novo` | sim | role | coberto |
| `POST` | `/centros-custo/novo` | sim | role | coberto |
| `GET` | `/centros-de-custo` | sim | role | coberto |
| `POST` | `/centros-de-custo/<int:centro_id>/editar` | sim | role | coberto |
| `POST` | `/centros-de-custo/<int:centro_id>/inativar` | sim | role | coberto |
| `POST` | `/centros-de-custo/<int:centro_id>/reativar` | sim | role | coberto |
| `GET` | `/centros-de-custo/inativos` | sim | role | coberto |
| `POST` | `/centros-de-custo/novo` | sim | role | coberto |
| `GET` | `/centros_custo` | sim | role | coberto |
| `POST` | `/centros_custo/<int:centro_id>/editar` | sim | role | coberto |
| `POST` | `/centros_custo/<int:centro_id>/inativar` | sim | role | coberto |
| `POST` | `/centros_custo/<int:centro_id>/reativar` | sim | role | coberto |
| `GET` | `/centros_custo/inativos` | sim | role | coberto |
| `POST` | `/centros_custo/novo` | sim | role | coberto |
| `GET` | `/cursos` | sim | role | coberto |
| `POST` | `/cursos/<int:curso_id>/editar` | sim | role | coberto |
| `POST` | `/cursos/<int:curso_id>/inativar` | sim | role | coberto |
| `POST` | `/cursos/<int:curso_id>/reativar` | sim | role | coberto |
| `GET` | `/cursos/inativos` | sim | role | coberto |
| `POST` | `/cursos/novo` | sim | role | coberto |
| `GET,POST` | `/editar/<int:id>` | sim | role | coberto |
| `POST` | `/excluir/<int:id>` | sim | role | coberto |
| `GET,POST` | `/form` | sim | — | coberto |
| `GET,POST` | `/frequencia` | sim | role | coberto |
| `GET` | `/frequencia_relatorio` | sim | role | coberto |
| `GET` | `/periodo-letivo` | sim | role | coberto |
| `GET` | `/periodo-letivo/<int:id>/calendario` | sim | role | coberto |
| `POST` | `/periodo-letivo/<int:id>/certificado-modelo/<int:centro_id>` | sim | — | coberto |
| `GET` | `/periodo-letivo/<int:id>/certificado-modelo/<int:centro_id>/arquivo` | sim | — | coberto |
| `POST` | `/periodo-letivo/<int:id>/certificado-modelo/<int:centro_id>/remover` | sim | — | coberto |
| `POST` | `/periodo-letivo/ativar/<int:id>` | sim | role | coberto |
| `GET` | `/periodo-letivo/centros-custo` | sim | role | coberto |
| `POST` | `/periodo-letivo/centros-custo/<int:centro_id>/editar` | sim | role | coberto |
| `POST` | `/periodo-letivo/centros-custo/<int:centro_id>/inativar` | sim | role | coberto |
| `POST` | `/periodo-letivo/centros-custo/<int:centro_id>/reativar` | sim | role | coberto |
| `GET` | `/periodo-letivo/centros-custo/inativos` | sim | role | coberto |
| `POST` | `/periodo-letivo/centros-custo/novo` | sim | role | coberto |
| `GET,POST` | `/periodo-letivo/editar/<int:id>` | sim | role | coberto |
| `POST` | `/periodo-letivo/inativar/<int:id>` | sim | role | coberto |
| `GET,POST` | `/periodo-letivo/novo` | sim | role | coberto |
| `GET` | `/periodo-letivo/relatorio/<int:id>` | sim | role | coberto |
| `GET` | `/periodos/centros-custo` | sim | role | coberto |
| `POST` | `/periodos/centros-custo/<int:centro_id>/editar` | sim | role | coberto |
| `POST` | `/periodos/centros-custo/<int:centro_id>/inativar` | sim | role | coberto |
| `POST` | `/periodos/centros-custo/<int:centro_id>/reativar` | sim | role | coberto |
| `GET` | `/periodos/centros-custo/inativos` | sim | role | coberto |
| `POST` | `/periodos/centros-custo/novo` | sim | role | coberto |
| `GET,POST` | `/planejamento` | sim | role | coberto |
| `GET` | `/planejamento/calendario/<int:periodo_id>` | sim | role | coberto |
| `GET` | `/planejamento/calendario/<int:periodo_id>/exportar` | sim | role | coberto |
| `POST` | `/planejamento/calendario/remover/<int:dia_id>` | sim | — | coberto |
| `POST` | `/planejamento/calendario/salvar` | sim | — | coberto |
| `GET` | `/planejamento/imprimir-temas` | sim | role | coberto |
| `POST` | `/planejamento/nivel/editar/<int:id>` | sim | role | coberto |
| `POST` | `/planejamento/nivel/inativar/<int:id>` | sim | role | coberto |
| `POST` | `/planejamento/tema/editar/<int:id>` | sim | role | coberto |
| `POST` | `/planejamento/tema/inativar/<int:id>` | sim | role | coberto |
| `POST` | `/planejamento/valor/editar/<int:id>` | sim | role | coberto |
| `POST` | `/planejamento/valor/inativar/<int:id>` | sim | role | coberto |
| `GET` | `/professor/painel` | sim | — | coberto |
| `GET` | `/turma` | sim | role | coberto |
| `GET` | `/turma/<int:id>` | sim | role | coberto |
| `GET` | `/turma/<int:id>/imprimir-pauta` | sim | role | coberto |
| `GET` | `/turma/<int:id>/ofertas` | sim | — | coberto |
| `POST` | `/turma/<int:id>/ofertas/nova` | sim | — | coberto |
| `GET` | `/turma/<int:turma_id>/observacoes` | sim | role | coberto |
| `POST` | `/turma/desenturmar/<int:id>` | sim | role | coberto |
| `GET,POST` | `/turma/editar/<int:id>` | sim | role | coberto |
| `POST` | `/turma/enturmar/<int:turma_id>` | sim | role | coberto |
| `POST` | `/turma/excluir/<int:id>` | sim | role | coberto |
| `GET,POST` | `/turma/nova` | sim | role | coberto |
| `POST` | `/turma/oferta/<int:oferta_id>/desativar` | sim | — | coberto |
| `POST` | `/turma/oferta/<int:oferta_id>/editar` | sim | — | coberto |
| `POST` | `/turma/oferta/<int:oferta_id>/principal` | sim | — | coberto |
| `GET` | `/turmas/carga-horaria` | sim | role | coberto |
| `GET` | `/turmas/centros-custo/imprimir` | sim | role | coberto |
| `GET` | `/turmas/lista` | sim | — | coberto |
| `GET` | `/turmas/lixeira` | sim | role | coberto |
| `POST` | `/turmas/reativar/<int:id>` | sim | role | coberto |

#### `auth` — 19 rotas

| Método | Rota | `login_required` | Papel no corpo | CSRF |
|---|---|---|---|---|
| `POST` | `/admin/cadastrar` | sim | role | coberto |
| `GET` | `/admin/logs` | sim | role | coberto |
| `POST` | `/admin/logs/limpar-antigos` | sim | role | coberto |
| `POST` | `/admin/manutencao/toggle` | sim | role | coberto |
| `GET` | `/admin/painel` | sim | role | coberto |
| `GET` | `/admin/unidades` | sim | role | coberto |
| `POST` | `/admin/unidades/alternar/<int:id>` | sim | role | coberto |
| `POST` | `/admin/unidades/cadastrar` | sim | role | coberto |
| `POST` | `/admin/unidades/editar/<int:id>` | sim | role | coberto |
| `GET` | `/aguardando-aprovacao` | sim | role | coberto |
| `GET` | `/auth/google/callback` | **não** | — | coberto |
| `GET,POST` | `/auth/google/confirmar-vinculo` | **não** | — | coberto |
| `GET` | `/auth/google/login` | **não** | — | coberto |
| `GET,POST` | `/login` | **não** | — | coberto |
| `GET` | `/logout` | sim | — | coberto |
| `GET,POST` | `/trocar-senha` | sim | — | coberto |
| `POST` | `/usuarios/editar/<int:id>` | sim | role | coberto |
| `POST` | `/usuarios/excluir/<int:id>` | sim | role | coberto |
| `POST` | `/usuarios/resetar/<int:id>` | sim | role | coberto |

#### `conselho` — 13 rotas

| Método | Rota | `login_required` | Papel no corpo | CSRF |
|---|---|---|---|---|
| `POST` | `/api/conselho-periodo` | sim | — | isento |
| `DELETE` | `/api/conselho-periodo/<int:conselho_id>` | sim | — | isento |
| `GET` | `/conselho` | sim | role | coberto |
| `GET` | `/conselho/fechamento/<int:turma_id>` | sim | role | coberto |
| `POST` | `/conselho/fechamento/<int:turma_id>/salvar` | sim | role | coberto |
| `GET` | `/conselho/imprimir` | sim | role | coberto |
| `GET` | `/conselho/lancamento` | sim | role | coberto |
| `POST` | `/conselho/pergunta/excluir/<int:id>` | sim | role | coberto |
| `POST` | `/conselho/pergunta/salvar` | sim | role | coberto |
| `GET` | `/conselho/perguntas` | sim | role | coberto |
| `POST` | `/conselho/salvar` | sim | — | coberto |
| `GET,POST` | `/informacoes` | sim | — | coberto |
| `GET,POST` | `/turma/<int:turma_id>/avaliacao` | sim | role | coberto |

#### `relatorios` — 13 rotas

| Método | Rota | `login_required` | Papel no corpo | CSRF |
|---|---|---|---|---|
| `GET` | `/relatorios/` | sim | role | coberto |
| `GET` | `/relatorios/alunos` | sim | role | coberto |
| `GET` | `/relatorios/alunos/<int:aluno_id>/ficha` | sim | role | coberto |
| `GET` | `/relatorios/bi` | sim | role | coberto |
| `GET` | `/relatorios/bi/dados` | sim | role | coberto |
| `GET` | `/relatorios/bi/exportar/xlsx` | sim | role | coberto |
| `GET` | `/relatorios/bi/indicador/<codigo>` | sim | role | coberto |
| `GET` | `/relatorios/conselho` | sim | role | coberto |
| `GET` | `/relatorios/exportar` | sim | role | coberto |
| `GET` | `/relatorios/observacoes` | sim | role | coberto |
| `GET` | `/relatorios/painel` | sim | role | coberto |
| `GET` | `/relatorios/painel/busca` | sim | role | coberto |
| `GET` | `/relatorios/relatorio_alunos/exportar` | sim | role | coberto |

#### `main (portais e painéis)` — 9 rotas

| Método | Rota | `login_required` | Papel no corpo | CSRF |
|---|---|---|---|---|
| `GET` | `/` | **não** | — | coberto |
| `GET` | `/dashboard` | sim | role | coberto |
| `GET` | `/painel` | sim | role | coberto |
| `GET` | `/painel/secretaria` | sim | role | coberto |
| `GET` | `/politica_privacidade` | **não** | — | coberto |
| `GET` | `/professor/painel-pedagogico` | sim | role | coberto |
| `GET` | `/termos_servico` | **não** | — | coberto |
| `GET` | `/teste-email` | **não** | — | coberto |
| `GET` | `/trocar-unidade/<int:id>` | sim | role | coberto |

#### `servico_social` — 6 rotas

| Método | Rota | `login_required` | Papel no corpo | CSRF |
|---|---|---|---|---|
| `POST` | `/servico-social/agendar-entrevista` | sim | role | coberto |
| `GET` | `/servico-social/aluno/<int:aluno_id>/dados` | sim | role | coberto |
| `GET` | `/servico-social/entrevistas` | sim | role | coberto |
| `GET,POST` | `/servico-social/entrevistas/<tipo>` | sim | role | coberto |
| `POST` | `/servico-social/excluir-agendamento/<int:id>` | sim | role | coberto |
| `GET` | `/servico-social/impressao/<int:resposta_id>` | sim | role | coberto |

#### `informacao_padrao` — 2 rotas

| Método | Rota | `login_required` | Papel no corpo | CSRF |
|---|---|---|---|---|
| `GET` | `/admin/informacao-padrao` | sim | role | coberto |
| `POST` | `/admin/informacao-padrao` | sim | role | coberto |

#### `planejamento` — 2 rotas

| Método | Rota | `login_required` | Papel no corpo | CSRF |
|---|---|---|---|---|
| `POST` | `/configurar-conselho` | sim | role | coberto |
| `POST` | `/turma/alternar-conselho/<int:turma_id>` | sim | role | coberto |

