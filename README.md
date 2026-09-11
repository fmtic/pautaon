# pautaON

Aplicação web para gestão escolar e pedagógica, com autenticação local e integração opcional com Active Directory/LDAP.

## Visão geral

O projeto é construído com Flask, SQLAlchemy, Flask-Login e templates Jinja2. Ele suporta:

- autenticação local e híbrida com AD/LDAP;
- cadastro e gestão de usuários, unidades, turmas, alunos e períodos letivos;
- importação em lote de alunos a partir de arquivos Excel;
- tratamento centralizado de falhas críticas para exibir a tela de indisponibilidade do sistema.

## Requisitos

- Python 3.11+
- Dependências listadas em requirements.txt
- Banco de dados configurado via variável DATABASE_URL ou SQLite local

## Configuração rápida

### Ambiente virtual (Windows)

No repositório já existe uma pasta de ambiente virtual local em .venv. Para usá-la, execute:

```powershell
.\.venv\Scripts\Activate.ps1
```

Se o PowerShell bloquear a execução do script, rode antes:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

### Instalação das dependências

```bash
pip install -r requirements.txt
```

### Variáveis de ambiente

Defina as variáveis de ambiente necessárias, por exemplo:

```powershell
$env:SECRET_KEY="troque-esta-chave"
$env:DATABASE_URL="postgresql://usuario:senha@host:5432/banco"
```

Em sistemas Linux/macOS, o equivalente é usar export.

### Execução local

```bash
python run.py
```

Ou, se preferir executar pelo WSGI do projeto:

```bash
python wsgi.py
```

### Produção local / IIS / WSGI

Em ambientes Windows com IIS ou outro gateway WSGI, o projeto pode ser servido via wsgi.py e o arquivo web.config já presente na raiz do projeto. Nesse cenário, é fundamental garantir que:

- SECRET_KEY esteja definido corretamente;
- DATABASE_URL aponte para o banco de produção;
- as dependências estejam instaladas no ambiente Python usado pelo servidor.

## Autenticação

A aplicação suporta dois fluxos principais:

- Login local: usa credenciais armazenadas no banco.
- Login AD/LDAP: tenta validar o usuário no domínio quando a integração estiver habilitada.

Para habilitar o fluxo do Active Directory, configure as variáveis abaixo:

```bash
export LDAP_ENABLED=true
export LDAP_SERVER_URI="ldaps://srv001.dominio.local"
export LDAP_DOMAIN="dominio.local"
export LDAP_USE_SSL=true
export LDAP_VALIDATE_CERT=true
export LDAP_CA_CERT_FILE="/caminho/para/ca.pem"
```

A autenticação no AD deve aceitar as três formas mais comuns de identidade do usuário:

- nome simples: `usuario`
- UPN: `usuario@dominio.local`
- formato domínio\usuário: `DOMINIO\usuario`

Quando a autenticação AD/LDAP é bem-sucedida, o usuário pode ser provisionado localmente em status pendente para aprovação administrativa. O sistema também bloqueia o bind quando a integração estiver desabilitada ou quando `LDAP_SERVER_URI` estiver ausente, evitando tentativas inúteis e diagnóstico incorreto.

## Tratamento de indisponibilidade

Quando ocorrem falhas críticas, como problemas de conexão com o banco ou exceções inesperadas, a aplicação renderiza o template de indisponibilidade para o usuário com status HTTP 503.

Esse comportamento está centralizado na criação da aplicação e ajuda a manter uma experiência consistente durante incidentes.

## Importação de alunos por planilha

A importação em lote pode ser feita com o script:

```bash
python scripts/ImportaçãoPlanilha/importar_matriculas.py caminho/para/arquivo.xlsx
```

Regras importantes:

- a coluna de unidade é obrigatória para cada linha com dados;
- a unidade informada precisa existir no cadastro de unidades do sistema;
- valores longos são truncados para respeitar o schema do banco;
- linhas sem nome são ignoradas.

## Estrutura principal

- app/: aplicação Flask, modelos, rotas, templates e serviços
- scripts/: utilidades de manutenção, bootstrap e importação
- config.py: configuração central da aplicação

## Manutenção

Ao alterar fluxos de login, tratamento de erro ou importação em lote, mantenha os comentários de intenção e as regras de negócio no próprio código para facilitar a compreensão futura.

## Códigos de Erro e Suporte

Para evitar exposição de detalhes internos aos usuários, o sistema gera um código curto sempre que uma exceção não tratada ocorre. O usuário vê apenas:

- "Um erro foi encontrado (código CODE), contate o suporte."

Onde `CODE` tem o formato `CC-YYYYMMDDThhmmss-XXXXXX`, por exemplo `01-20260909T111523-3f4a1b`.

Mapeamento de prefixos (CC):

- `01`: Banco de dados / SQLAlchemy
- `02`: Chamadas externas / HTTP APIs
- `03`: LDAP / Active Directory
- `04`: Template / URL building
- `05`: Autenticação / Autorização
- `06`: Validação de entrada
- `99`: Desconhecido / Outros

Onde procurar o diagnóstico:

- Logs da aplicação: `instance/error.log` (procure pelo código exato entre colchetes, por exemplo `[01-20260909T111523-3f4a1b]`).
- Em ambiente WSGI, verifique também `instance/wsgi_error.log` se aplicável.

Procedimento para suporte:

1. Peça ao usuário o código exibido na tela.
2. No servidor, pesquise nos logs por esse código e revise o stacktrace completo registrado ao lado do código.
3. Use o timestamp embutido no código para correlacionar logs de infra (DB / LDAP / rede).

Desenvolvedores: o helper para gerar e registrar esses códigos está em `app/utils/errors.py`.
