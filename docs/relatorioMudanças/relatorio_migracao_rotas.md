# Relatório Técnico — Migração e Desfragmentação das Rotas (pautaON)

**Data de execução:** 11 de setembro de 2026
**Projeto:** pautaON (Flask / Python)
**Responsável pela análise e correção:** Kiro (agente autônomo)
**Commit base analisado:** `99c5d2d` (HEAD → main)

---

## 1. Contexto

O desenvolvedor realizou uma refatoração profunda na camada de rotas do projeto, fragmentando um
arquivo monolítico (`app/routes/main.py`, ~964 linhas) em múltiplos submódulos e pacotes
especializados. Após essa desfragmentação, diversas referências a endpoints, imports de modelos e
definições de blueprints ficaram inconsistentes, quebrando silenciosamente funcionalidades críticas
— inclusive o menu de navegação global do `base.html`, que afetava **todas** as páginas da aplicação.

---

## 2. Diagnóstico — Problemas Encontrados

### 2.1 Blueprints definidos mas não registrados no factory

Dois blueprints foram criados nos novos módulos mas jamais importados nem registrados na função
`_register_blueprints()` de `app/__init__.py`. Em tempo de execução, suas rotas simplesmente não
existiam — qualquer `url_for()` apontando para esses blueprints lançava `BuildError`.

| Blueprint | Variável | Prefixo URL | Arquivo |
|---|---|---|---|
| `relatorios` | `bp_relatorios` | `/relatorios` | `app/routes/relatorios/__init__.py` |
| `planejamento` | `bp_planejamento` | *(sem prefixo)* | `app/routes/planejamento.py` |

---

### 2.2 `url_for()` quebrados em templates HTML

Todos os templates continuavam referenciando endpoints pelo nome antigo (`main.*`), que existia
no arquivo monolítico removido. Com a migração, esses endpoints foram movidos para blueprints
separados.

| Arquivo | `url_for()` antigo (quebrado) | `url_for()` correto |
|---|---|---|
| `base.html` | `main.relatorio_geral` | `relatorios.relatorio_geral` |
| `base.html` | `main.relatorio_alunos` | `relatorios.relatorio_alunos` |
| `base.html` | `main.resultado_conselho` | `relatorios.resultado_conselho` |
| `relatorios/geral.html` | `main.relatorio_alunos` | `relatorios.relatorio_alunos` |
| `relatorios/geral.html` | `main.exportar_relatorio` | `relatorios.exportar_relatorio` |
| `relatorios/relatorio_alunos.html` | `main.relatorio_geral` | `relatorios.relatorio_geral` |
| `relatorios/relatorio_alunos.html` | `main.exportar_relatorio_alunos` (no `<form action>`) | `relatorios.exportar_relatorio_alunos` |
| `relatorios/relatorio_alunos.html` | `main.relatorio_alunos` (botão Limpar) | `relatorios.relatorio_alunos` |
| `relatorios/resultado_conselho.html` | `main.relatorio_geral` | `relatorios.relatorio_geral` |
| `relatorios/resultado_conselho.html` | `main.resultado_conselho` (no `<form action>`) | `relatorios.resultado_conselho` |
| `relatorios/alunosOLD.html` | `main.relatorio_geral` | `relatorios.relatorio_geral` |
| `relatorios/alunosOLD.html` | `main.exportar_relatorio_alunos` | `relatorios.exportar_relatorio_alunos` |
| `relatorios/alunosOLD.html` | `main.relatorio_alunos` | `relatorios.relatorio_alunos` |
| `planejamento/planejamento.html` | `registros.salvar_configuracao_conselho` | `planejamento.salvar_configuracao_conselho` |
| `planejamento/planejamento.html` | `main.alternar_conselho` | `planejamento.alternar_conselho` |

> **Impacto crítico:** Os 3 `url_for()` em `base.html` eram executados no menu de navegação de
> **todas** as páginas autenticadas. Qualquer usuário com perfil pedagógico, admin, gerência,
> secretaria ou serviço social recebia `BuildError` ao tentar acessar qualquer tela.

---

### 2.3 `url_for()` quebrados em arquivos Python

| Arquivo | `url_for()` antigo (quebrado) | Correção aplicada |
|---|---|---|
| `app/routes/registros/core.py` (função `editar`) | `'main.relatorios'` | `'registros.form'` |
| `app/routes/registros/core.py` (função `excluir`) | `'main.relatorios'` | `'registros.form'` |

> Nota: o endpoint `main.relatorios` nunca existiu em nenhum blueprint. O redirecionamento foi
> apontado para `registros.form`, que é o equivalente funcional no fluxo atual dos registros legados.

---

### 2.4 Import de modelo inexistente

| Arquivo | Import quebrado | Correção |
|---|---|---|
| `app/routes/relatorios/conselho.py` | `from app.models import Configuracao, ...` | `from app.models import ConfiguracaoSistema, ...` |

A classe `Configuracao` não existe em `app/models.py`. O modelo correspondente chama-se
`ConfiguracaoSistema`. Esse erro gerava `ImportError` ao inicializar qualquer blueprint do pacote
`relatorios`, impedindo o registro das rotas mesmo quando o blueprint fosse corretamente adicionado.

---

### 2.5 Acesso a campos inexistentes no model `ConselhoClasse`

A função `resultado_conselho()` em `app/routes/relatorios/conselho.py` acessava três atributos
que não existem no model `ConselhoClasse`:

| Acesso incorreto | Problema | Solução aplicada |
|---|---|---|
| `cons.nivel` | Campo não existe em `ConselhoClasse` | Buscado via `Inscricao.nivel` (nível do aluno naquela turma); fallback para `aluno.nivel` |
| `cons.presenca_percentual` | Campo calculado não existe | Calculado dinamicamente via `Frequencia.query` + `calcular_estatisticas_frequencia()` |
| `cons.proxima_turma` | Campo não existe (o relacionamento é `proxima_turma_obj`) | Substituído por `cons.proxima_turma_obj.nome` com guard `if cons.proxima_turma_obj` |

Adicionalmente, a busca pelas datas do período do conselho usava `Configuracao.query.first()` com
campos inexistentes (`config.inicio_conselho`, `config.fim_conselho`). Reescrito para:

```python
conf_inicio = ConfiguracaoSistema.query.filter_by(chave='inicio_conselho').first()
conf_fim    = ConfiguracaoSistema.query.filter_by(chave='fim_conselho').first()
```

---

### 2.6 Campos `google_id` e `google_email` ausentes no model `User`

O fluxo de autenticação OAuth Google em `app/routes/auth.py` consultava e gravava os campos
`User.google_id` e `User.google_email` — mas esses campos não estavam definidos em
`app/models.py`. Qualquer tentativa de login via Google resultaria em `AttributeError`.

---

## 3. Correções Aplicadas

### 3.1 `app/__init__.py` — Registro dos blueprints faltantes

```python
# ANTES
def _register_blueprints(app: Flask) -> None:
    from app.routes import auth, conselho, informacao_padrao, main
    from app.routes.registros import bp as registros_bp
    from app.routes.registros.servico_social import bp as servico_social_bp

    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(registros_bp)
    app.register_blueprint(conselho.bp)
    app.register_blueprint(informacao_padrao.bp)
    app.register_blueprint(servico_social_bp)

# DEPOIS
def _register_blueprints(app: Flask) -> None:
    from app.routes import auth, conselho, informacao_padrao, main
    from app.routes.registros import bp as registros_bp
    from app.routes.registros.servico_social import bp as servico_social_bp
    from app.routes.relatorios import bp_relatorios
    from app.routes.planejamento import bp_planejamento

    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(registros_bp)
    app.register_blueprint(conselho.bp)
    app.register_blueprint(informacao_padrao.bp)
    app.register_blueprint(servico_social_bp)
    app.register_blueprint(bp_relatorios)    # ADICIONADO
    app.register_blueprint(bp_planejamento)  # ADICIONADO
```

---

### 3.2 `app/models.py` — Adição dos campos Google OAuth ao model `User`

```python
# ADICIONADO após o campo first_login
google_id: str | None = db.Column(db.String(100), unique=True, nullable=True, index=True)
google_email: str | None = db.Column(db.String(120), nullable=True)
```

Uma migration Alembic foi gerada automaticamente:
`migrations/versions/7aa724d05691_add_google_id_and_google_email_to_user.py`

---

### 3.3 `app/routes/relatorios/conselho.py` — Import, campos e config

- Import `Configuracao` → `ConfiguracaoSistema`
- Campos `cons.nivel`, `cons.presenca_percentual`, `cons.proxima_turma` substituídos por lógica
  correta (ver seção 2.5)
- Busca de configuração de datas do conselho reescrita com `ConfiguracaoSistema.query.filter_by`

---

### 3.4 `app/routes/registros/core.py` — Redirects legados

```python
# ANTES (2 ocorrências)
return redirect(url_for('main.relatorios'))

# DEPOIS
return redirect(url_for('registros.form'))
```

---

### 3.5 Templates — Correção de `url_for()` quebrados

Todos os `url_for('main.<endpoint_de_relatorio>')` e `url_for('main.alternar_conselho')` foram
corrigidos para os blueprints corretos. Ver tabela completa na seção 2.2.

---

## 4. Mapa Final de Blueprints Registrados

Após as correções, a aplicação conta com **8 blueprints** registrados e **101 endpoints** totais.

| Blueprint | Nome | Prefixo URL | Arquivo principal |
|---|---|---|---|
| `auth.bp` | `auth` | *(raiz)* | `app/routes/auth.py` |
| `main.bp` | `main` | *(raiz)* | `app/routes/main/__init__.py` |
| `registros_bp` | `registros` | *(raiz)* | `app/routes/registros/__init__.py` |
| `conselho.bp` | `conselho` | *(raiz)* | `app/routes/conselho.py` |
| `informacao_padrao.bp` | `informacao_padrao` | *(raiz)* | `app/routes/informacao_padrao.py` |
| `servico_social_bp` | `servico_social` | `/servico-social` | `app/routes/registros/servico_social.py` |
| `bp_relatorios` ✅ *adicionado* | `relatorios` | `/relatorios` | `app/routes/relatorios/__init__.py` |
| `bp_planejamento` ✅ *adicionado* | `planejamento` | *(raiz)* | `app/routes/planejamento.py` |

---

## 5. Arquivos Modificados

| Arquivo | Tipo de alteração |
|---|---|
| `app/__init__.py` | Registro dos blueprints `relatorios` e `planejamento` |
| `app/models.py` | Adição dos campos `google_id` e `google_email` ao model `User` |
| `app/routes/registros/core.py` | Correção de 2 `url_for('main.relatorios')` → `url_for('registros.form')` |
| `app/routes/relatorios/conselho.py` | Import corrigido; campos inexistentes substituídos; busca de config reescrita |
| `app/templates/base.html` | Correção de 3 `url_for('main.*')` → `url_for('relatorios.*')` |
| `app/templates/planejamento/planejamento.html` | Correção de 2 `url_for()` para `planejamento.*` |
| `app/templates/relatorios/geral.html` | Correção de 2 `url_for('main.*')` → `url_for('relatorios.*')` |
| `app/templates/relatorios/relatorio_alunos.html` | Correção de 3 `url_for('main.*')` → `url_for('relatorios.*')` |
| `app/templates/relatorios/resultado_conselho.html` | Correção de 2 `url_for('main.*')` → `url_for('relatorios.*')` |
| `app/templates/relatorios/alunosOLD.html` | Correção de 3 `url_for('main.*')` → `url_for('relatorios.*')` |
| `migrations/versions/7aa724d05691_*.py` | Migration gerada para os novos campos do `User` |

---

## 6. Validação

Todos os itens abaixo foram verificados com saída `exit code 0` usando o interpretador do projeto
(`.venv`):

| Verificação | Resultado |
|---|---|
| Import de todos os módulos de rotas e models | ✅ OK — zero erros |
| Factory `create_app()` sem exceção | ✅ OK |
| 23 endpoints críticos presentes no URL map | ✅ 23/23 |
| Total de endpoints registrados | ✅ 101 |
| Migration Alembic gerada para novos campos | ✅ `7aa724d05691` |

---

## 7. Pendências e Recomendações

1. **Executar a migration no banco de dados de produção/homologação:**
   ```bash
   flask db upgrade
   ```
   Isso adiciona as colunas `google_id` e `google_email` à tabela `user`. Sem isso, o login
   via Google continuará falhando com erro de coluna inexistente no PostgreSQL.

2. **Remover ou arquivar `app/templates/relatorios/alunosOLD.html`:** O arquivo é um template
   legado sem rota associada. Seus `url_for()` foram corrigidos preventivamente, mas o ideal é
   remover o arquivo para evitar confusão futura.

3. **Verificar a migration gerada:** A migration `7aa724d05691` inclui, além dos campos Google,
   outras diferenças detectadas pelo Alembic entre o modelo atual e o banco (ex: mudança de tipo
   em `atendimento.setor`, `atendimento.atendido_por_nome` e remoção de índices em `atendimento`).
   Revisar o arquivo antes de aplicar em produção para garantir que essas diferenças são
   esperadas.

4. **Testes de integração:** Recomenda-se executar os fluxos de login Google, acesso ao painel
   de relatórios e ao planejamento pedagógico em ambiente de homologação para confirmar o
   comportamento end-to-end após as correções.
