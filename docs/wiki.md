# Wiki do pautaON

Ponto de entrada para entender, operar e desenvolver o pautaON. Esta wiki resume os conceitos e aponta para os documentos e módulos que são a fonte de detalhe. Quando uma instrução operacional divergir daqui, siga o manual específico e mantenha esta página como índice.

## Navegação

- [Visão geral](#visão-geral)
- [Conceitos do domínio](#conceitos-do-domínio)
- [Perfis e acesso](#perfis-e-acesso)
- [Arquitetura](#arquitetura)
- [Iniciar localmente](#iniciar-localmente)
- [Fluxos principais](#fluxos-principais)
- [Central de BI](#central-de-bi)
- [Banco e migrations](#banco-e-migrations)
- [Testes](#testes)
- [Operação e diagnóstico](#operação-e-diagnóstico)
- [Documentação relacionada](#documentação-relacionada)

## Visão geral

O pautaON é um sistema de gestão escolar e pedagógica em Flask. Organiza dados por unidade e oferece gestão de usuários, alunos, períodos letivos, turmas, inscrições, frequência, planejamento, conselho de classe, atendimentos e relatórios.

O código da aplicação fica principalmente em `app/`; templates Jinja2 em `app/templates/`; arquivos estáticos em `app/static/`; documentação operacional e de domínio em `docs/` e nos diretórios dos módulos.

## Conceitos do domínio

- **Unidade:** tenant e fronteira principal de isolamento dos dados.
- **Período letivo:** intervalo acadêmico pertencente a uma unidade.
- **Turma:** oferta operacional associada a período, curso, turno e unidade.
- **Aluno:** cadastro da pessoa. `Aluno.ativo` indica se o cadastro permanece ativo no sistema; não significa, por si só, que o aluno esteja enturmado.
- **Inscrição:** vínculo histórico entre aluno e turma. `Inscricao.ativo=True` identifica o vínculo atual; podem existir várias inscrições para o mesmo aluno e turma.
- **Status do aluno por período:** classificação calculada pelo serviço `app.services.aluno_status`, sem coluna de status persistida. Inclui Novo, Renovado, Retornante, Em janela, Não renovado, Desenturmado e Outros.
- **Histórico:** transferências e reativações não devem ser deduzidas apenas de `Aluno.ativo`; use as inscrições e suas datas conforme a regra do serviço.

## Perfis e acesso

O sistema usa autenticação local e pode integrar LDAP/Active Directory e Google OAuth2. Os papéis de negócio incluem `admin`, `gerencia`, `pedagogico`, `secretaria`, `professor`, `servico_social` e `pendente`.

O acesso de perfis operacionais é restrito à unidade vinculada ao usuário. Admin e gerência podem ter visão global, sujeita aos filtros e regras de cada tela/indicador. Consulte `app/relatorios/shared.py`, `app/utils/logica.py` e `app/registros/shared.py` ao alterar autorização ou escopo de unidade.

## Arquitetura

- `app/__init__.py`: factory `create_app`, inicialização de extensões, registro de blueprints, hooks e comandos CLI.
- `app/models/`: entidades SQLAlchemy e enums. `app/models/MER.md` documenta o esquema e as regras persistidas.
- `app/services/`: regras de negócio compartilhadas, como bootstrap, calendário, perfil e status por período.
- `app/registros/`: rotas e operações de alunos, turmas, períodos, frequência e serviço social.
- `app/main/`: dashboards por perfil.
- `app/relatorios/`: relatórios e BI; `bi_routes.py` atende a Central, `bi.py` registra códigos, `catalogo.py` define metadados e `bi_alunos.py` contém consultas.
- `app/templates/` e `app/static/`: interface Jinja2, CSS, JavaScript e assets.
- `migrations/`: histórico Alembic/Flask-Migrate.
- `tests/`: testes automatizados; fixtures que criam e removem schema devem usar banco SQLite isolado.

## Iniciar localmente

Pré-requisitos: Python 3.11 ou superior, dependências de `requirements.txt` e um `.env` local com configurações apropriadas. Não coloque credenciais reais em arquivos versionados ou em documentação.

No PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

A aplicação local abre em `http://127.0.0.1:5000`.

Para PostgreSQL vazio, o README descreve a criação inicial do schema e o alinhamento do Alembic. Depois do schema disponível, o comando Flask `seed-admin` cria o usuário inicial a partir das variáveis `ADMIN_EMAIL`, `ADMIN_NAME`, `ADMIN_DEFAULT_PASSWORD` e `ADMIN_FORCE_PASSWORD_CHANGE`:

```powershell
python scripts/create_postgres_schema.py
python -m flask --app run:app db stamp head
python -m flask --app run:app seed-admin
```

`seed-admin` é explícito; iniciar `run.py` não cria automaticamente um administrador. O comando não altera uma conta admin já existente.

## Fluxos principais

### Alunos e enturmações

O cadastro do aluno e a inscrição em turma são operações distintas. Uma inscrição pertence a uma turma; o período vem de `Turma.periodo_letivo_id`. A tabela `inscricoes` guarda histórico e permite múltiplos vínculos ao longo do tempo.

### Frequência e aulas

A frequência associa aluno, turma, data e conceito. Os conceitos e as regras de contagem ficam em `app/models/enums.py` e `app/utils/frequencia.py`. Planejamento e registros de aula ficam em módulos próprios.

### Conselho de classe

Conselhos são vinculados a turmas, alunos e períodos de conselho. A configuração de perguntas e respostas está em `app/models/conselho.py`; as rotas e fluxos ficam em `app/conselho.py`.

### Serviço social e atendimentos

Atendimentos, agendas e formulários ficam nos domínios `app/models/atendimento.py` e `app/models/servico_social.py`, com operações em `app/registros/` e `app/services/`.

## Central de BI

A Central fica em `/relatorios/bi`. O catálogo de códigos e descrições está em `app/relatorios/catalogo.py`; a descrição funcional completa fica em `app/relatorios/indicadores.md`.

Os filtros visíveis incluem período letivo, unidade e turno. O significado de um filtro vazio depende do indicador. Nos indicadores de status, sem período explícito o serviço usa o período ativo vigente de cada unidade. A visão histórica agregada “Todos” e a série histórica por período ainda são uma etapa planejada; não assuma que a opção atual representa um total histórico deduplicado.

Exportações da Central incluem XLSX e, para gráficos, PNG. Ao alterar um indicador, mantenha alinhados cálculo, catálogo, filtros, exportação e testes.

## Banco e migrations

PostgreSQL é recomendado para produção; os testes locais usam SQLite. A fonte dos models é `app/models/`, e o MER documenta as colunas e relações.

- Banco novo: siga o procedimento de criação inicial do schema em `README.md` e só então alinhe o Alembic.
- Banco existente: faça backup e use as migrations com `flask db upgrade`.
- Mudança de tabela/coluna: atualize models, gere/revise migration e atualize o MER.
- `db.create_all()` cria tabelas ausentes; não substitui migrations para atualizar tabelas existentes.

## Testes

Execute a suíte pelo ambiente virtual:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Use testes focados durante a implementação. Fixtures que chamam `db.create_all()`/`db.drop_all()` precisam fixar SQLite antes de `db.init_app`; nunca deixe testes destrutivos apontarem para a URL PostgreSQL do `.env`.

## Operação e diagnóstico

- Logs da aplicação: `instance/error.log`.
- Uploads e documentos: `instance/uploads/`; revise permissões e backup no deploy.
- Falhas de autenticação: confira o provedor e suas configurações sem registrar senhas ou tokens.
- Erros de banco: confirme URL, conectividade, schema e usuário; não rode criação/reset de schema em banco existente sem backup e verificação.
- Em produção, use servidor WSGI atrás de IIS/Apache e não `python run.py`.

## Documentação relacionada

- [README e configuração geral](../README.md)
- [MER e regras do banco](../app/models/MER.md)
- [Catálogo detalhado do BI](../app/relatorios/indicadores.md)
- [Manual de deploy](manual_deploy.md)
- [Integração Google](manual_google_integracao.md)
- [Programas sociais](manual_programas_sociais.md)
- [Checklist de segurança e dívidas técnicas](checklist_seguranca_dividas_tecnicas.md)
- [Relatório de migração de rotas](relatorio_migracao_rotas.md)
