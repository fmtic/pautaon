# Checklist e Plano de Remediação: Segurança, Privacidade e Dívidas Técnicas

> **Projeto**: pautaON  
> **Data do Levantamento**: 20/09/2026  
> **Classificação**: Auditoria Interna de Segurança e Proteção de Dados (LGPD / ECA)  
> **Objetivo**: Documento de consulta técnica e checklist operacional para mitigação de vulnerabilidades, eliminação de acessos indevidos e adequação de privacidade.

---

## Sumário Executivo

| ID | Área / Vulnerabilidade | Severidade | Esforço | Status |
| :--- | :--- | :---: | :---: | :---: |
| **SEC-01** | Uploads de documentos e laudos expostos na pasta pública `/static` sem autenticação | **Crítica** | Médio | `[x] Feito` |
| **SEC-02** | Operações de mutação e deleção via método HTTP `GET` (Vulnerabilidade CSRF) | **Crítica** | Médio | `[x] Feito` |
| **SEC-03** | Falta de interceptor global (`before_request`) para perfil `pendente` e `first_login` | **Alta** | Baixo | `[x] Feito` |
| **SEC-04** | Ações destrutivas e consultas de alunos/serviço social sem checagem de perfil (RBAC) | **Alta** | Médio | `[x] Feito` |
| **SEC-05** | Quebra de isolamento multitenant entre unidades (IDOR em atendimentos e períodos) | **Alta** | Médio | `[x] Feito` |
| **SEC-06** | Pre-Account Takeover no Google OAuth (vínculo automático sem comprovação) | **Média** | Baixo | `[x] Feito` |
| **SEC-07** | Troca de senha não exige a senha atual do operador | **Média** | Baixo | `[x] Feito` |
| **SEC-08** | Rate limiting de autenticação em memória volátil e risco de DoS sem `ProxyFix` | **Média** | Baixo | `[x] Feito` |
| **SEC-09** | Flag `SESSION_COOKIE_SECURE` desativada quando configurado apenas `APP_ENV` | **Média** | Baixo | `[x] Feito` |
| **SEC-10** | Ausência de cabeçalhos HTTP de segurança (*Security Headers*) e Clickjacking | **Baixa** | Baixo | `[x] Feito` |
| **SEC-11** | Vazamento de detalhes internos e nomes de banco em mensagens *flash* | **Baixa** | Baixo | `[x] Feito` |

---

## 1. Vulnerabilidades Críticas

### [SEC-01] Uploads de documentos e laudos expostos publicamente na pasta `/static`

- **Arquivos afetados**:
  - `app/registros/shared.py` (funções `salvar_documento`, `salvar_foto`, `_build_upload_path`)
  - `app/registros/atendimentos.py` (função `_salvar_anexo`)
  - `app/registros/alunos.py` (função `_atualizar_documentos_entregues`)
- **Descrição do Risco**:
  Os uploads de alunos (RG, CPF, Certidão de Nascimento, Termos de Responsabilidade, Anexos do Serviço Social e **Laudos Médicos/PCD**) estão sendo gravados dentro de `app/static/uploads/documentos/...`.
  No ecossistema Flask e na maioria dos servidores WSGI/web (Nginx, IIS, Apache), a pasta `static` é servida abertamente sem passar por autenticação (`@login_required`). Como as pastas e arquivos seguem padrões sequenciais e previsíveis (ex.: `/static/uploads/documentos/aluno_1/doc_laudo.pdf`), qualquer pessoa anônima pode enumerar e baixar dados pessoais e médicos de menores de idade, configurando infração grave à LGPD e ao ECA.
- **Plano de Ação**:
  1. Mover o diretório base de uploads para fora da pasta `static` (ex.: `instance/uploads/`).
  2. Criar uma rota controlada protegida com `@login_required` para servir os arquivos após verificar se o usuário autenticado tem permissão para acessar a unidade e o registro do aluno.
  3. Utilizar `send_from_directory(..., as_attachment=...)` na rota controlada.
  4. Migrar os arquivos físicos legados já existentes em `app/static/uploads/documentos/` para a nova pasta protegida.

#### Checklist SEC-01
- [ ] Criar diretório seguro `instance/uploads/documentos/` e `instance/uploads/fotos/`.
- [ ] Atualizar `_build_upload_path` em `app/registros/shared.py` para apontar para `instance/uploads/`.
- [ ] Atualizar `_salvar_anexo` em `app/registros/atendimentos.py` para gravar no novo diretório seguro.
- [ ] Criar endpoint protegido `GET /documentos/<tipo>/<int:aluno_id>/<filename>` com `@login_required` e validação de `assert_unidade_context`.
- [ ] Substituir nos templates Jinja referências diretas de `url_for('static', filename='uploads/documentos/...')` pelo novo endpoint protegido.
- [ ] Testar se uma requisição não autenticada recebe `302/401` ao tentar acessar um documento.

---

### [SEC-02] Operações de mutação e deleção via método HTTP `GET` (Vulnerabilidade CSRF)

- **Arquivos afetados**:
  - `app/registros/alunos.py` (`/aluno/excluir/<id>`, `/aluno/inativar/<id>`, `/turma/desenturmar/<id>`)
  - `app/auth.py` (`/admin/unidades/alternar/<id>`)
  - `app/conselho.py` (`/conselho/pergunta/excluir/<id>`)
  - `app/planejamento.py` (`/turma/alternar-conselho/<turma_id>`)
  - `app/registros/periodos.py` (`/periodo-letivo/inativar/<id>`, `/periodo-letivo/ativar/<id>`)
  - `app/registros/servico_social.py` (`/servico-social/excluir-agendamento/<id>`)
  - `app/registros/core.py` (`/excluir/<id>`)
- **Descrição do Risco**:
  O `CSRFProtect` da extensão `flask-wtf` apenas protege métodos de alteração de estado (`POST`, `PUT`, `PATCH`, `DELETE`). O método `GET` é isento de validação de token CSRF por especificação.
  Rotas que excluem ou inativam registros via `GET` permitem que um invasor induza um usuário autenticado (através de um link ou tag `<img src="...">` em um fórum, site externo ou e-mail corporativo) a disparar a exclusão física ou inativação de dados no sistema sem o consentimento da vítima.
- **Plano de Ação**:
  1. Alterar a assinatura das rotas para aceitar exclusivamente `methods=["POST"]`.
  2. Nos templates onde há botões ou links de exclusão/alteração, transformar as tags `<a>` em pequenos formulários HTML com `<button type="submit">` contendo o token CSRF (`<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`).

#### Checklist SEC-02
- [ ] Alterar rota `/aluno/excluir/<int:id>` para `methods=['POST']` e atualizar botão no template.
- [ ] Alterar rota `/aluno/inativar/<int:id>` para `methods=['POST']` e atualizar botão no template.
- [ ] Alterar rota `/turma/desenturmar/<int:id>` para `methods=['POST']` e atualizar botão no template.
- [ ] Alterar rota `/admin/unidades/alternar/<int:id>` para `methods=['POST']` e atualizar botão no template.
- [ ] Alterar rota `/conselho/pergunta/excluir/<int:id>` para `methods=['POST']` e atualizar botão no template.
- [ ] Alterar rota `/turma/alternar-conselho/<int:turma_id>` para `methods=['POST']` e atualizar botão no template.
- [ ] Alterar rotas `/periodo-letivo/inativar/<int:id>` e `/periodo-letivo/ativar/<int:id>` para `methods=['POST']`.
- [ ] Alterar rota `/servico-social/excluir-agendamento/<int:id>` para `methods=['POST']`.
- [ ] Alterar rota `/excluir/<int:id>` em `app/registros/core.py` para `methods=['POST']`.
- [ ] Testar envio de requisições `GET` contra essas rotas e certificar que retornam `405 Method Not Allowed`.

---

## 2. Falhas de Autorização e Isolamento Multitenant

### [SEC-03] Ausência de `before_request` para usuários `pendente` e `first_login`

- **Arquivos afetados**:
  - `app/__init__.py`
  - `app/auth.py`
  - `app/main/dashboard.py`
- **Descrição do Risco**:
  A checagem de perfil `UserRole.PENDENTE` (usuários novos originados via AD/LDAP ou Google OAuth) só é aplicada dentro da função `dashboard()` e da finalização de `login()`. Se o usuário alterar diretamente a URL no navegador (ex.: `/alunos`, `/turmas`, `/frequencia`), ele navega pelas funções do sistema sem que o administrador tenha aprovado seu perfil. Da mesma forma, o sinalizador `first_login` (troca de senha obrigatória) não trava a navegação caso o usuário ignore o redirecionamento inicial.
- **Plano de Ação**:
  Criar um hook global `@app.before_request` em `app/__init__.py` (ou `app/auth.py`) que:
  - Ignore requisições para rotas estáticas (`static`) e rotas essenciais de autenticação (`auth.login`, `auth.logout`, `auth.trocar_senha`, `auth.aguardando_aprovacao`).
  - Redirecione para `auth.aguardando_aprovacao` caso `current_user.is_authenticated and current_user.role == UserRole.PENDENTE`.
  - Redirecione para `auth.trocar_senha` caso `current_user.is_authenticated and current_user.first_login and not current_user.is_ad_user`.

#### Checklist SEC-03
- [ ] Implementar a função interceptora `_enforce_user_access_state` e registrá-la em `app.before_request`.
- [ ] Adicionar exceções estritas para `static`, `auth.logout`, `auth.aguardando_aprovacao` e `auth.trocar_senha`.
- [ ] Testar com um usuário no estado `pendente` acessando diretamente `/alunos` e certificar o redirecionamento.
- [ ] Testar com um usuário no estado `first_login=True` tentando acessar `/dashboard` e certificar o redirecionamento forçado para `/trocar-senha`.

---

### [SEC-04] Rotas sensíveis e destrutivas sem validação de perfil (RBAC)

- **Arquivos afetados**:
  - `app/registros/alunos.py`
  - `app/registros/servico_social.py`
  - `app/registros/core.py`
- **Descrição do Risco**:
  Várias rotas possuem apenas o decorador `@login_required`, sem verificar `current_user.role`:
  - `/aluno/excluir/<id>` e `/aluno/inativar/<id>` não conferem papel, permitindo que professores ou assistentes excluam alunos.
  - `/servico-social/excluir-agendamento/<id>` permite a qualquer usuário autenticado apagar reuniões do Serviço Social e do Google Calendar integrado.
  - `/aluno/<int:aluno_id>/historico` não confere se o usuário autenticado possui perfil pedagógico/gerencial.
  - `/api/alunos/<int:turma_id>` em `core.py` permite enumerar todos os alunos de qualquer turma sem restrição de papel.
- **Plano de Ação**:
  Incluir restrições explícitas de papéis canônicos (`UserRole`) no topo das rotas usando `if current_user.role not in (...): abort(403)`.

#### Checklist SEC-04
- [ ] Proteger `/aluno/excluir/<id>` para permitir apenas `UserRole.ADMIN` e `UserRole.PEDAGOGICO`.
- [ ] Proteger `/aluno/inativar/<id>` para permitir apenas `UserRole.ADMIN`, `UserRole.PEDAGOGICO` e `UserRole.SECRETARIA`.
- [ ] Proteger `/servico-social/excluir-agendamento/<id>` para permitir apenas o autor do agendamento ou `UserRole.ADMIN` / `UserRole.SERVICO_SOCIAL`.
- [ ] Proteger `/aluno/<id>/historico` validando perfil e associação de turma quando for professor.
- [ ] Proteger `/api/alunos/<turma_id>` validando permissão e contexto de unidade.

---

### [SEC-05] Quebra de isolamento multitenant entre unidades (IDOR)

- **Arquivos afetados**:
  - `app/registros/atendimentos.py` (`detalhe_atendimento`)
  - `app/registros/periodos.py` (`periodo_letivo_inativar`, `periodo_letivo_ativar`)
  - `app/registros/shared.py` (`assert_unidade_context`)
  - `app/utils/logica.py` (`get_unidade_id`)
- **Descrição do Risco**:
  1. A rota `/atendimentos/<int:id>` recupera o atendimento do banco e entrega os dados JSON completos sem chamar `assert_unidade_context(a.unidade_id, get_unidade_id())`. Usuários de uma unidade conseguem ler atendimentos confidenciais de outra unidade apenas alterando o ID.
  2. As rotas de inativação e ativação de período letivo não checam a unidade de origem.
  3. Se um usuário sem papel global (`admin`, `gerencia`) for cadastrado sem unidade vinculada (`user.unidade_id is None`), a função `get_unidade_id()` retorna `None`. Como `assert_unidade_context` começa com `if unidade_id:`, quando o valor é `None` a trava é ignorada e o usuário ganha acesso a dados de todas as unidades.
- **Plano de Ação**:
  1. Adicionar `assert_unidade_context` nas rotas órfãs.
  2. Ajustar `assert_unidade_context` para rejeitar requisições de operadores locais cujo `unidade_id` seja nulo.

#### Checklist SEC-05
- [ ] Inserir `assert_unidade_context(a.unidade_id, get_unidade_id())` em `detalhe_atendimento` (`app/registros/atendimentos.py`).
- [ ] Inserir `assert_unidade_context(periodo.unidade_id, get_unidade_id())` em `periodo_letivo_inativar` e `periodo_letivo_ativar` (`app/registros/periodos.py`).
- [ ] Ajustar `assert_unidade_context` para validar que usuários não-globais possuam obrigatoriamente `unidade_id`.
- [ ] Testar tentativa de acesso cruzado de um operador da Unidade A acessando o ID de atendimento da Unidade B, garantindo retorno `403 Forbidden`.

---

## 3. Autenticação, Gestão de Senhas e OAuth

### [SEC-06] Pre-Account Takeover no Google OAuth (Insecure Account Linking)

- **Arquivo afetado**: `app/auth.py` (rota `google_callback`)
- **Descrição do Risco**:
  No fluxo de retorno do Google OAuth, se não for encontrado usuário pelo `google_id`, o sistema busca um usuário existente pelo `email`. Se encontrado, vincula imediatamente a conta Google e efetua login (`login_user(user)`).
  Porém:
  - Não há conferência da claim `email_verified: True` retornada pelo Google.
  - Não há restrição de domínio corporativo (`hd` - *hosted domain*).
  - Um terceiro pode criar uma conta Google com o e-mail de um funcionário ainda não cadastrado no Google e assumir a conta local e suas permissões no pautaON.
- **Plano de Ação**:
  1. Verificar explicitamente se `userinfo.get("email_verified") is True`.
  2. (Se aplicável) Validar se o domínio do e-mail coincide com o domínio institucional da organização.
  3. Se a conta local já existir e possuir senha cadastrada, exigir confirmação de senha local antes do primeiro vínculo com conta externa Google.

#### Checklist SEC-06
- [ ] Adicionar validação: `if not userinfo.get("email_verified"): abort(400)`.
- [ ] Configurar parâmetro opcional `GOOGLE_OAUTH_ALLOWED_DOMAINS` no `.env` para limitar domínios corporativos.
- [ ] Em contas pré-existentes que nunca fizeram login via Google, solicitar confirmação da senha local antes de associar o `google_id`.

---

### [SEC-07] Troca de senha não exige a senha atual do operador

- **Arquivo afetado**: `app/auth.py` (rota `trocar_senha`)
- **Descrição do Risco**:
  A rota `/trocar-senha` recebe apenas os campos `nova_senha` e `confirma_senha`. Ela não exige que o usuário digite a sua senha em uso (`senha_atual`).
  Em caso de estações de trabalho não bloqueadas temporariamente pelo operador ou sequestro de sessão (XSS/Cookie theft), qualquer pessoa pode redefinir a credencial sem saber a senha antiga, trancando o usuário legítimo para fora do sistema.
- **Plano de Ação**:
  Exigir o campo `senha_atual` no formulário e validar via `current_user.check_password(senha_atual)` antes de aceitar a nova credencial (exceto no fluxo onde `current_user.first_login` é verdadeiro e a conta possui senha padrão inicial).

#### Checklist SEC-07
- [ ] Adicionar campo `senha_atual` no formulário `app/templates/trocar_senha.html` quando `not first_login`.
- [ ] Validar `current_user.check_password(senha_atual)` em `app/auth.py:trocar_senha`.
- [ ] Testar tentativa de alteração com senha atual incorreta e confirmar bloqueio.

---

### [SEC-08] Rate Limiting de login em memória volátil e risco de DoS sem `ProxyFix`

- **Arquivo afetado**: `app/auth.py` (funções `_is_login_blocked`, `_register_failed_attempt`)
- **Descrição do Risco**:
  1. A proteção de força bruta `_FAILED_ATTEMPTS` usa um dicionário Python em memória. Em servidores WSGI (Gunicorn, uWSGI, IIS com múltiplos processos), cada processo tem sua própria memória isolada e os contadores são apagados em qualquer reinicialização de worker.
  2. Sem o middleware `werkzeug.middleware.proxy_fix.ProxyFix`, caso a aplicação rode atrás de um proxy reverso (Nginx, Traefik, IIS URL Rewrite), `request.remote_addr` será `127.0.0.1` para todos os clientes. Consequentemente, 5 erros de login por qualquer atacante bloquearão o acesso de todos os colaboradores da instituição.
- **Plano de Ação**:
  1. Configurar `ProxyFix` na inicialização do Flask (`app/__init__.py`).
  2. Considerar o armazenamento de tentativas de login falhas no banco de dados SQLite/Postgres ou Redis para persistência compartilhada entre processos.

#### Checklist SEC-08
- [ ] Configurar `ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)` no `create_app` se executado em produção com proxy reverso.
- [ ] Migrar contadores de bloqueio de IP/usuário de memória volátil para persistência de curto prazo.

---

## 4. Configurações de Ambiente e Segurança HTTP

### [SEC-09] Flag `SESSION_COOKIE_SECURE` desativada com `APP_ENV`

- **Arquivo afetado**: `config.py:43`
- **Descrição do Risco**:
  A regra atual calcula:
  ```python
  SESSION_COOKIE_SECURE = get_bool("SESSION_COOKIE_SECURE", get_bool("FLASK_DEBUG", False) is False and os.getenv("FLASK_ENV") == "production")
  ```
  O Flask depreciou a variável `FLASK_ENV` em favor de `APP_ENV`. O próprio projeto já utiliza `APP_ENV = os.getenv("APP_ENV", ...)`. Se em produção apenas `APP_ENV=production` estiver definido no `.env`, a condição do `SESSION_COOKIE_SECURE` será avaliada como `False`, permitindo que os cookies de sessão trafeguem em texto claro sem o atributo `Secure`.
- **Plano de Ação**:
  Atualizar a linha para verificar `APP_ENV == "production"`.

#### Checklist SEC-09
- [ ] Atualizar `config.py` para usar `APP_ENV == "production"`.
- [ ] Validar no navegador em ambiente HTTPS se o cookie de sessão possui a flag `Secure`.

---

### [SEC-10] Ausência de cabeçalhos HTTP de segurança (*Security Headers*)

- **Arquivo afetado**: `app/__init__.py`
- **Descrição do Risco**:
  As respostas HTTP do sistema não incluem cabeçalhos defensivos básicos de proteção de navegador:
  - `X-Frame-Options: SAMEORIGIN` (evita Clickjacking / inserção do pautaON em iframes de terceiros).
  - `X-Content-Type-Options: nosniff` (impede interpretação errônea de arquivos de upload como scripts executáveis).
  - `Strict-Transport-Security` (HSTS - força navegadores a comunicarem apenas em HTTPS).
  - `Referrer-Policy: strict-origin-when-cross-origin`.
- **Plano de Ação**:
  Adicionar um decorator `@app.after_request` em `app/__init__.py` para injetar os cabeçalhos em todas as respostas HTTP.

#### Checklist SEC-10
- [ ] Adicionar função `_set_security_headers` via `@app.after_request`.
- [ ] Injetar `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy` e `Strict-Transport-Security` (quando em produção).
- [ ] Testar headers usando ferramentas de inspeção do navegador ou `curl -I`.

---

### [SEC-11] Vazamento de erros internos e detalhes do banco via mensagens *flash*

- **Arquivos afetados**:
  - `app/registros/turmas.py:158`
  - `app/registros/atendimentos.py:329, 410`
  - `app/utils/errors.py`
- **Descrição do Risco**:
  Algumas rotas capturam exceções com `except Exception as exc:` e executam `flash(f"... (Constraint db): {exc}", "danger")` ou retornam `{"erro": str(exc)}`. Isso expõe a estrutura de tabelas, nomes de colunas, índices e caminhos internos do servidor diretamente ao usuário final.
- **Plano de Ação**:
  Substituir as mensagens técnicas por mensagens genéricas e amigáveis para o usuário, registrando o detalhe técnico exclusivamente via `current_app.logger.exception(...)`.

#### Checklist SEC-11
- [ ] Fazer varredura de chamadas `flash(... {exc} ...)` e `jsonify(erro=str(exc))`.
- [ ] Padronizar mensagens para "Ocorreu um erro ao salvar o registro. A equipe técnica foi notificada."
- [ ] Assegurar que os detalhes técnicos completos continuem sendo enviados para `app.logger.exception()`.

---

## 5. Roteiro Sugerido de Execução

1. **Sprint 1 (Imediato - Risco Crítico)**:
   - Implementar rota segura para downloads de arquivos e tirar documentos da pasta `static` (**SEC-01**).
   - Converter todas as rotas destrutivas via `GET` para formulários com `POST` e token CSRF (**SEC-02**).
   - Criar interceptor `@app.before_request` para usuários `pendente` e primeiro acesso (**SEC-03**).

2. **Sprint 2 (Alto Impacto em Acessos e Multitenancy)**:
   - Adicionar checagem de perfil nas rotas órfãs de alunos e serviço social (**SEC-04**).
   - Corrigir checagem de unidade (`assert_unidade_context`) em atendimentos e períodos letivos (**SEC-05**).
   - Corrigir comportamento de `assert_unidade_context` para usuários sem unidade definida (**SEC-05**).

3. **Sprint 3 (Higiene de Autenticação e Configurações)**:
   - Exigir senha atual no formulário de troca de senha (**SEC-07**).
   - Proteger callback do Google OAuth contra Pre-Account Takeover (**SEC-06**).
   - Corrigir `SESSION_COOKIE_SECURE` e adicionar cabeçalhos HTTP defensivos (**SEC-09**, **SEC-10**).
   - Limpar mensagens de exceção técnica nos flashes (**SEC-11**).
