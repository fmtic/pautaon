# Relatório do dia — 14/09/2026

**Projeto:** pautaON (Flask)
**Objetivo:** reparar referências quebradas após a reorganização de `app/` descrita em `app/LEIA-ME.md`, para que a aplicação volte a importar e registrar as rotas na estrutura nova.
**Público:** qualquer agente de IA (ou humano) que for continuar neste repositório.

Este documento complementa `docs/relatorioMigracaoRotas/relatorio_migracao_rotas.md` (11/09/2026), que corrigiu `url_for` e blueprints **ainda no caminho `app/routes/`**. Depois disso, as rotas foram movidas para `app/` e o pacote `app/routes` deixou de existir. As correções daquele relatório **não estavam refletidas** em todos os arquivos novos.

---

## 1. Contexto (o que a refatoração fez)

Houve duas mudanças de layout, nesta ordem:

1. **Quebra de monolitos** (descrita em `app/LEIA-ME.md`):
   - `main.py` → pacote `main/` (`home`, `dashboard`, dashboards por perfil, `secretaria`, `unidade`)
   - `relatorios.py` → pacote `relatorios/` (`geral`, `alunos`, `conselho`, `shared`)
   - rota duplicada `POST /planejamento/configurar-conselho` removida de `registros/core.py`; a versão canônica ficou em `planejamento.py`
2. **Saída de `app/routes/`**: os módulos de rota passaram a viver direto em `app/` (`app/auth.py`, `app/main/`, `app/registros/`, etc.). A árvore antiga foi copiada para `app/routesOLD/` (arquivo, não importar).

O factory (`app/__init__.py`) **continuava importando `app.routes`**, que não existe mais. Isso impedia `create_app()`.

---

## 2. Mapa atual das rotas (código ativo)

Não use `app.routes.*`. Importações corretas:

| Blueprint Flask | Prefixo URL | Módulo ativo |
|---|---|---|
| `auth` | raiz | `app/auth.py` → `bp` |
| `main` | raiz | `app/main/__init__.py` → `bp` |
| `registros` | raiz | `app/registros/__init__.py` → `bp` |
| `conselho` | raiz | `app/conselho.py` → `bp` |
| `informacao_padrao` | raiz | `app/informacao_padrao.py` → `bp` (só rotas HTTP) |
| `servico_social` | `/servico-social` | `app/registros/servico_social.py` → `bp` (blueprint **próprio**, registrado à parte) |
| `relatorios` | `/relatorios` | `app/relatorios/__init__.py` → `bp_relatorios` |
| `planejamento` | raiz | `app/planejamento.py` → `bp_planejamento` |

Serviço de dados institucionais (logos, CNPJ, etc.):

- **Antes:** pacote `app/informacao_padrao/` (`__init__.py` + `service.py`)
- **Agora:** `app/services/informacao_padrao.py`
- Funções públicas: `get_informacao_padrao_context`, `get_informacao_padrao_values`, `upsert_informacao_padrao`

**Por que o serviço saiu de `app/informacao_padrao/`:** em Python não podem coexistir `app/informacao_padrao.py` (rotas) e o pacote `app/informacao_padrao/`. A refatoração colapsou os dois no mesmo nome; o módulo de rotas importava a si mesmo.

Arquivos **arquivo / não usar em import**:

- `app/routesOLD/` — cópia das rotas no layout `app.routes`
- `app/informacao_padraoOLD/` — cópia do pacote de serviço antigo

Nomes de blueprint, `url_prefix` e paths HTTP foram preservados. Endpoints Flask (`url_for('relatorios.relatorio_geral')` etc.) continuam os mesmos nomes de blueprint.

---

## 3. Problemas encontrados e correções desta sessão

### 3.1 Factory ainda apontava para `app.routes`

**Arquivo:** `app/__init__.py`, `_register_blueprints()`

Quebrava na inicialização (`ModuleNotFoundError: app.routes`).

```python
# ANTES
from app.routes import auth, conselho, informacao_padrao, main
from app.routes.registros import bp as registros_bp
from app.routes.registros.servico_social import bp as servico_social_bp
from app.routes.relatorios import bp_relatorios
from app.routes.planejamento import bp_planejamento

# DEPOIS
from app.auth import bp as auth_bp
from app.conselho import bp as conselho_bp
from app.informacao_padrao import bp as informacao_padrao_bp
from app.main import bp as main_bp
from app.registros import bp as registros_bp
from app.registros.servico_social import bp as servico_social_bp
from app.relatorios import bp_relatorios
from app.planejamento import bp_planejamento
```

### 3.2 Colisão `informacao_padrao` (rotas vs serviço)

**Arquivos:**

- criado `app/services/informacao_padrao.py` (conteúdo equivalente a `app/informacao_padraoOLD/service.py`)
- `app/informacao_padrao.py` (rotas) agora importa de `app.services.informacao_padrao`
- context processor em `app/__init__.py` usa `from app.services.informacao_padrao import get_informacao_padrao_context`

O arquivo de rotas fazia `from app.informacao_padrao import get_informacao_padrao_values, upsert_informacao_padrao` — import circular / nomes inexistentes no próprio módulo.

### 3.3 `app/relatorios/conselho.py` voltou à versão quebrada

A cópia em `app/relatorios/` **não** tinha as correções já feitas em `app/routesOLD/relatorios/conselho.py` (e documentadas no relatório de 11/09).

| Problema | Correção |
|---|---|
| `from app.models import Configuracao` (classe inexistente) | `ConfiguracaoSistema` |
| `cons.nivel` | `Inscricao.nivel` da turma, fallback `aluno.nivel` |
| `cons.presenca_percentual` | `Frequencia` + `calcular_estatisticas_frequencia()` |
| `cons.proxima_turma` | `cons.proxima_turma_obj.nome` |
| `Configuracao.query.first()` / `inicio_conselho` no model | `ConfiguracaoSistema.query.filter_by(chave='inicio_conselho'/'fim_conselho')` |

### 3.4 Redirects mortos em `app/registros/core.py`

`editar()` e `excluir()` faziam `url_for('main.relatorios')` (endpoint que nunca existiu).

Corrigido para `url_for('registros.form')`, igual à versão já corrigida em `routesOLD`.

### 3.5 Strings de log / `flash_and_log` com endpoint antigo

| Arquivo | Antes | Depois |
|---|---|---|
| `app/planejamento.py` | `main.salvar_configuracao_conselho` | `planejamento.salvar_configuracao_conselho` |
| `app/relatorios/geral.py` | `main.relatorio_geral` | `relatorios.relatorio_geral` |

### 3.6 CSS do relatório de alunos

`app/templates/relatorios/relatorio_alunos.html` apontava para `css/relatorios/alunos.css` (arquivo inexistente).

Arquivo real: `app/static/css/relatorios/relatorio_alunos.css`.

O template de planejamento **já** usava `url_for('planejamento.salvar_configuracao_conselho')` e `url_for('planejamento.alternar_conselho')` — nada a mudar ali (era a ressalva do LEIA-ME).

### 3.7 Documentação de integração no LEIA-ME

`app/LEIA-ME.md` seção “Como integrar” ainda dizia para importar `app.routes.main`. Atualizada para o mapa real em `app/`.

---

## 4. O que NÃO foi alterado (de propósito)

- Regras de negócio, queries e templates além do CSS citado.
- Pastas `app/routesOLD/` e `app/informacao_padraoOLD/` (arquivo histórico).
- Campos `User.google_id` / `User.google_email` em `app/models.py` (já presentes).
- Registro dos 8 blueprints (já estava no factory; só o **caminho de import** mudou).

---

## 5. Pendências conhecidas (não bloqueiam o boot)

1. **CSS ausentes (404 de estático, a página ainda renderiza):**
   - `app/templates/relatorios/geral.html` → `css/relatorios/geral.css` (não existe em `app/static/css/`)
   - `app/templates/relatorios/resultado_conselho.html` → `css/relatorios/resultado_conselho.css` (não existe)
2. **Arquivos *OLD* no repositório:** `routesOLD`, `informacao_padraoOLD`, e possivelmente templates/CSS legado. Podem ser removidos quando o time confirmar que não precisa mais do diff.
3. **Migration Google OAuth:** há `migrations/versions/6a8df39d_add_google_oauth_fields_to_user.py` e `7aa724d05691_add_google_id_and_google_email_to_user.py`. Revisar qual aplicar no banco antes de `flask db upgrade` em produção (ver relatório de 11/09).
4. `app/registros/__init__.py` importa `servico_social` embora esse módulo **não** registre rotas no blueprint `registros` (tem blueprint próprio). Comportamento antigo; não mudado.

---

## 6. Como um agente deve importar daqui para frente

```python
# Factory / testes
from app import create_app
from app.auth import bp as auth_bp
from app.main import bp as main_bp
from app.registros import bp as registros_bp
from app.relatorios import bp_relatorios
from app.planejamento import bp_planejamento
from app.services.informacao_padrao import get_informacao_padrao_context
```

`url_for` de relatórios: blueprint `relatorios.*`, nunca `main.relatorio_*`.
`url_for` de configurar/alternar conselho: `planejamento.*`, nunca `registros.salvar_configuracao_conselho`.

---

## 7. Validação feita nesta sessão

Com `python` no diretório do projeto:

- `create_app()` conclui sem exceção
- **101** regras no `url_map` (mesmo total do relatório de 11/09)
- Endpoints conferidos presentes: `auth.login`, `main.dashboard`, `relatorios.relatorio_geral`, `relatorios.relatorio_alunos`, `relatorios.resultado_conselho`, `planejamento.salvar_configuracao_conselho`, `planejamento.alternar_conselho`, `informacao_padrao.painel_informacao_padrao`, `registros.form`, `registros.planejamento`, `servico_social.agendar_entrevista`, `conselho.index_conselho`
- `url_for` desses nomes resolve dentro de `test_request_context`

Não foi feito teste E2E no browser (login + cliques) nesta sessão.

---

## 8. Arquivos tocados nesta sessão

| Arquivo | Alteração |
|---|---|
| `app/__init__.py` | imports de blueprint + `get_informacao_padrao_context` |
| `app/informacao_padrao.py` | import do serviço |
| `app/services/informacao_padrao.py` | **novo** — serviço institucional |
| `app/relatorios/conselho.py` | import/campos/config alinhados ao model |
| `app/registros/core.py` | redirects `registros.form` |
| `app/planejamento.py` | location do log |
| `app/relatorios/geral.py` | location do log |
| `app/templates/relatorios/relatorio_alunos.html` | CSS existente |
| `app/LEIA-ME.md` | seção de integração |
| `docs/relatorioDia.md` | este relatório |
