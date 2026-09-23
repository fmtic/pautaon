# pautaON

Sistema de gestão escolar e pedagógica desenvolvido em Flask, com suporte a autenticação local, Active Directory/LDAP e Google OAuth2.

---

## Funcionalidades

- Autenticação híbrida: local, AD/LDAP e Google OAuth2
- Gestão de usuários, unidades, turmas, alunos e períodos letivos
- Registro de frequência, atendimentos pedagógicos e serviço social
- Conselho de classe com perguntas configuráveis
- Planejamento de aulas e temas
- Integração com Google Calendar e Google Chat
- Importação em lote de alunos via planilha Excel
- Relatórios e histórico por aluno
- Controle de acesso por perfil (RBAC) com isolamento multitenant por unidade
- Servimento seguro e autenticado de documentos e fotos de alunos

---

## Requisitos

- Python 3.11+
- PostgreSQL (recomendado para produção) ou SQLite (desenvolvimento)
- Dependências listadas em `requirements.txt`

---

## Configuração

### 1. Ambiente virtual

```powershell
# Windows — ativar o .venv já presente no repositório
.\.venv\Scripts\Activate.ps1

# Se o PowerShell bloquear a execução:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

```bash
# Linux / macOS
source .venv/bin/activate
```

### 2. Dependências

```bash
pip install -r requirements.txt
```

### 3. Variáveis de ambiente

Copie `.env.example` para `.env` e ajuste os valores:

```bash
cp .env.example .env
```

Variáveis obrigatórias:

| Variável | Descrição |
|---|---|
| `SECRET_KEY` | Chave criptográfica da sessão Flask |
| `DATABASE_URL` | URI de conexão com o banco de dados |
| `APP_ENV` | `development` ou `production` |

### 4. Banco de dados

Para um banco PostgreSQL vazio, crie primeiro as tabelas a partir dos models e
somente depois registre a revisão atual. A cadeia histórica contém migrations
incrementais sobre um schema existente e não deve ser iniciada em `base`.

```bash
# PowerShell — criar as tabelas na primeira execução
python scripts/create_postgres_schema.py
flask db stamp head

# Se o banco já existir e tiver tabelas, use migrations normalmente:
flask db upgrade

# Se o banco já existir mas o schema estiver fora de sincronia com o Alembic,
# faça backup e valide as tabelas antes de usar create_all/stamp head:
python -c "from app import create_app; from app.database import db; import app.models; app = create_app(); app.app_context().push(); db.create_all()"
flask db stamp head
```

### 5. Usuário administrador inicial

O cadastro de múltiplos programas sociais e a manutenção da lista de sugestões
estão descritos em [`docs/manual_programas_sociais.md`](docs/manual_programas_sociais.md).

```bash
python scripts/reset_admin.py admin@exemplo.com senha_inicial
```

### 6. Execução local

```bash
python run.py
```

---

## Deploy em produção

Consulte [`docs/manual_deploy.md`](docs/manual_deploy.md) para instruções detalhadas de deploy no IIS (Windows) e Apache (Linux).

Pontos essenciais para qualquer ambiente de produção:

- `SECRET_KEY` deve ser uma string aleatória longa e única
- `DATABASE_URL` deve apontar para o banco de produção (PostgreSQL)
- `APP_ENV=production` ativa `SESSION_COOKIE_SECURE`, HSTS e outros controles
- Uploads ficam em `instance/uploads/` — garanta permissão de escrita para o processo do servidor
- Arquivos estáticos podem ser servidos diretamente pelo servidor web (Nginx/Apache/IIS) para melhor desempenho

---

## Autenticação

### Login local

Credenciais armazenadas no banco com hash bcrypt. Na primeira autenticação, o usuário é obrigado a definir uma nova senha.

### Active Directory / LDAP

Configure as variáveis abaixo para habilitar o fluxo AD:

```env
LDAP_ENABLED=true
LDAP_SERVER_URI=ldaps://srv001.dominio.local
LDAP_DOMAIN=dominio.local
LDAP_USE_SSL=true
LDAP_VALIDATE_CERT=true
LDAP_CA_CERT_FILE=/caminho/para/ca.pem
LDAP_CONNECT_TIMEOUT=10
```

Formatos de identidade aceitos: `usuario`, `usuario@dominio.local`, `DOMINIO\usuario`.

Usuários autenticados pelo AD são provisionados localmente com perfil `pendente` e precisam de aprovação administrativa antes de acessar o sistema.

### Google OAuth2

Configure as variáveis abaixo para habilitar o botão "Entrar com Google":

```env
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
GOOGLE_OAUTH_REDIRECT_URI=https://seudominio.com.br/auth/google/callback
GOOGLE_OAUTH_ALLOWED_DOMAINS=escola.edu.br   # opcional — restringe por domínio
GOOGLE_OAUTH_REQUIRE_EMAIL_VERIFIED=true
```

Consulte [`docs/manual_google_integracao.md`](docs/manual_google_integracao.md) para criação do projeto no Google Cloud Console.

---

## Perfis de acesso (RBAC)

| Perfil | Descrição |
|---|---|
| `admin` | Acesso total, gestão de usuários e unidades |
| `gerencia` | Visão global entre unidades, sem gestão de usuários |
| `pedagogico` | Gestão de turmas, alunos, frequência e conselho |
| `secretaria` | Cadastro e matrícula de alunos |
| `professor` | Lançamento de frequência e visualização de suas turmas |
| `servico_social` | Atendimentos e agendamentos do serviço social |
| `pendente` | Acesso bloqueado — aguarda aprovação administrativa |

---

## Importação de alunos por planilha

```bash
python scripts/ImportaçãoPlanilha/importar_matriculas.py caminho/para/arquivo.xlsx
```

Regras:
- A coluna de unidade é obrigatória em cada linha com dados
- A unidade informada deve existir no cadastro do sistema
- Linhas sem nome são ignoradas
- Valores longos são truncados para respeitar o schema do banco

---

## Estrutura do projeto

```
app/
├── auth.py                  # Autenticação, OAuth, administração de usuários
├── conselho.py              # Conselho de classe
├── planejamento.py          # Planejamento de aulas
├── main/                    # Dashboards por perfil
├── models/                  # Modelos SQLAlchemy
├── registros/               # Alunos, turmas, frequência, atendimentos, períodos
├── relatorios/              # Geração de relatórios
├── services/                # Serviços de negócio (auth, calendar, bootstrap)
├── templates/               # Templates Jinja2
├── static/                  # CSS, JS, imagens
└── utils/                   # Helpers (erros, datas, lógica)
config.py                    # Configuração central
migrations/                  # Revisões Alembic
scripts/                     # Utilitários de manutenção e importação
docs/                        # Manuais e documentação técnica
instance/                    # Dados locais: banco SQLite, uploads, logs, certificados
```

---

## Segurança

O projeto passou por auditoria interna documentada em [`docs/checklist_seguranca_dividas_tecnicas.md`](docs/checklist_seguranca_dividas_tecnicas.md). Controles implementados:

- Documentos e fotos de alunos servidos por rotas autenticadas — sem exposição via `/static`
- Operações destrutivas restritas ao método `POST` com token CSRF obrigatório
- Interceptor global (`before_request`) para perfis `pendente` e `first_login`
- Isolamento multitenant por unidade com `assert_unidade_context` em todas as rotas sensíveis
- Proteção contra Pre-Account Takeover no Google OAuth
- Troca de senha exige confirmação da senha atual (exceto no primeiro acesso)
- Rate limiting de login persistido em banco — resistente a reinicializações WSGI
- `ProxyFix` configurado para leitura correta de IP real atrás de proxy reverso
- Cabeçalhos HTTP de segurança: `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `HSTS`
- `SESSION_COOKIE_SECURE` ativado automaticamente em `APP_ENV=production`

---

## Códigos de erro

Exceções não tratadas geram um código de rastreamento exibido ao usuário no formato:

```
CC-YYYYMMDDThhmmss-XXXXXX
```

Exemplo: `01-20260909T111523-3f4a1b`

| Prefixo | Categoria |
|---|---|
| `01` | Banco de dados / SQLAlchemy |
| `02` | Chamadas externas / HTTP APIs |
| `03` | LDAP / Active Directory |
| `04` | Template / URL building |
| `05` | Autenticação / Autorização |
| `06` | Validação de entrada |
| `99` | Desconhecido / Outros |

**Para suporte:**
1. Solicite ao usuário o código exibido na tela
2. Pesquise o código em `instance/error.log` (ex.: `grep "01-20260909T111523-3f4a1b" instance/error.log`)
3. Leia o stacktrace completo registrado ao lado do código
4. Use o timestamp embutido para correlacionar com logs de infraestrutura (banco, LDAP, rede)

O helper de geração e registro dos códigos está em `app/utils/errors.py`.

---

## Documentação adicional

| Documento | Conteúdo |
|---|---|
| [`docs/manual_deploy.md`](docs/manual_deploy.md) | Deploy no IIS e Apache, configuração WSGI |
| [`docs/manual_google_integracao.md`](docs/manual_google_integracao.md) | Google Cloud, OAuth2, Calendar e Chat |
| [`docs/checklist_seguranca_dividas_tecnicas.md`](docs/checklist_seguranca_dividas_tecnicas.md) | Auditoria de segurança e LGPD |
| [`app/models/MER.md`](app/models/MER.md) | Modelo entidade-relacionamento |
