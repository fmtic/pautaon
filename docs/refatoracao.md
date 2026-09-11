# Guia de Refatoração

## O que mudou

### 1. Inicialização previsível

No projeto original, importar a aplicação já podia criar tabelas e preparar estados globais. Na cópia refatorada, isso foi removido para que:

- testes sejam mais fáceis de escrever
- deploys fiquem mais previsíveis
- tarefas administrativas sejam explícitas

### 2. Serviços separados das rotas

As rotas continuaram existindo, mas parte da responsabilidade foi deslocada:

- LDAP e auditoria em `app/services/auth_service.py`
- criação de schema e admin inicial em `app/services/bootstrap.py`
- Google Calendar em `app/services/calendar_service.py`

Esse desenho facilita futuras substituições sem reescrever controllers inteiros.

### 2.1. Rotas grandes começaram a ser quebradas em pacote

O antigo módulo de registros virou um pacote próprio em `app/routes/registros/`, com um blueprint único e implementação distribuída por arquivos específicos:

- `app/routes/registros/__init__.py`
- `app/routes/registros/core.py`
- `app/routes/registros/periodos.py`
- `app/routes/registros/servico_social.py`

Com isso, a separação por domínio começou sem exigir uma reescrita total de uma vez só.

### 3. Configuração por ambiente

Valores fixos como:

- senha padrão
- caminho do arquivo de credenciais
- servidor LDAP
- modo debug

foram empurrados para variáveis de ambiente.

### 3.1. Tratamento uniforme de erros e observabilidade

Uma correção importante desta etapa foi remover a prática de expor exceções diretamente no front-end. Antes, algumas rotas e flashes mostravam mensagens com conteúdo bruto de erro, o que era ruim para UX e para segurança.

Hoje o padrão é:

- registrar o stack trace completo em log;
- gerar um código curto para suporte;
- exibir uma mensagem genérica ao usuário;
- manter a página de indisponibilidade consistente quando a falha for crítica.

Esse comportamento foi centralizado em `app/utils/errors.py` e reforçado em `app/__init__.py` para captar exceções globais e renderizar o template `sistema_indisponivel.html`.

O caso mais visível foi um erro de template em `url_for()` com rota inexistente. O erro foi rastreado até a referência quebrada em `app/templates/base.html` e corrigido sem deixar o sistema em 500 para o usuário final.

### 3.2. Códigos de erro para suporte

O esquema atual usa o formato:

```text
CC-YYYYMMDDThhmmss-XXXXXX
```

exemplo:

```text
99-20260909T144745-1153e2
```

Esse código é gravado junto ao stack trace em `instance/error.log`, permitindo correlacionar a falha com o momento exato do incidente sem expor o detalhe bruto ao cliente.

## Convenções adotadas

- comentários curtos só onde ajudam a explicar decisão estrutural
- nomes em inglês nos pontos de infraestrutura e bootstrap
- lógica compartilhada extraída para `services`
- `current_app.logger` preferido a `print()`

## Limites desta etapa

Esta refatoração melhora a fundação, mas ainda não conclui a modernização completa. A base ainda possui:

- arquivos ainda grandes, embora menores do que no início
- poucos testes automatizados
- muitas capturas genéricas de exceção
- modelos com datas armazenadas como string

## Próxima evolução sugerida

1. Continuar extraindo `app/routes/registros/core.py` em módulos menores de alunos, turmas, frequência e planejamento.
2. Criar camada de serviços para turmas, alunos e frequências.
3. Introduzir migração formal com Alembic.
4. Padronizar qualidade com `pytest`, `ruff` e `black`.
