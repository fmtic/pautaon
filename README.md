# PautaON Refatorado

Versão de trabalho do projeto original preparada para evolução com menos risco operacional e mais previsibilidade de manutenção.

## Objetivos desta cópia

- preservar o projeto original intacto
- reduzir efeitos colaterais na inicialização
- remover segredos e caminhos absolutos do fluxo principal
- centralizar integrações e bootstrap
- melhorar legibilidade e extensibilidade da base

## Melhorias aplicadas

- `create_app()` agora sobe a aplicação sem criar banco nem usuário administrador automaticamente
- configuração centralizada por ambiente em [config.py](/C:/Users/FMtic/Documents/Nextcloud/MeusDados/Codeberg/pauta-online-refatorado/config.py:1)
- extensões Flask isoladas em [app/extensions.py](/C:/Users/FMtic/Documents/Nextcloud/MeusDados/Codeberg/pauta-online-refatorado/app/extensions.py:1)
- bootstrap administrativo e inicialização do banco movidos para [app/services/bootstrap.py](/C:/Users/FMtic/Documents/Nextcloud/MeusDados/Codeberg/pauta-online-refatorado/app/services/bootstrap.py:1)
- autenticação LDAP, auditoria e validação de senha movidas para [app/services/auth_service.py](/C:/Users/FMtic/Documents/Nextcloud/MeusDados/Codeberg/pauta-online-refatorado/app/services/auth_service.py:1)
- integração com Google Calendar movida para [app/services/calendar_service.py](/C:/Users/FMtic/Documents/Nextcloud/MeusDados/Codeberg/pauta-online-refatorado/app/services/calendar_service.py:1)
- domínio `registros` promovido a pacote em [app/routes/registros](/C:/Users/FMtic/Documents/Nextcloud/MeusDados/Codeberg/pauta-online-refatorado/app/routes/registros/__init__.py:1)
- núcleo principal mantido em [app/routes/registros/core.py](/C:/Users/FMtic/Documents/Nextcloud/MeusDados/Codeberg/pauta-online-refatorado/app/routes/registros/core.py:1)
- rotas de período letivo e calendário extraídas para [app/routes/registros/periodos.py](/C:/Users/FMtic/Documents/Nextcloud/MeusDados/Codeberg/pauta-online-refatorado/app/routes/registros/periodos.py:1)
- rotas do serviço social extraídas para [app/routes/registros/servico_social.py](/C:/Users/FMtic/Documents/Nextcloud/MeusDados/Codeberg/pauta-online-refatorado/app/routes/registros/servico_social.py:1)
- arquivos sensíveis removidos da cópia e substituídos por [.env.example](/C:/Users/FMtic/Documents/Nextcloud/MeusDados/Codeberg/pauta-online-refatorado/.env.example:1)
- scripts de migração ad hoc, cargas de teste antigas e assets redundantes removidos da cópia

## Estrutura relevante

```text
pauta-online-refatorado/
├── app/
│   ├── routes/         # Controllers HTTP e pacotes por domínios
│   ├── services/       # Regras de integração e bootstrap
│   ├── utils/          # Funções utilitárias legadas e auxiliares
│   ├── extensions.py   # Instâncias compartilhadas do Flask
│   └── __init__.py     # Application factory sem side effects
├── docs/
├── scripts/
├── .env.example
├── config.py
└── run.py
```

## Comportamento de exclusão de turma

- A exclusão de turma é feita como desativação parcial: o registro de `Turma` recebe `ativo=False`.
- Ao excluir uma turma, o sistema também remove:
  - lançamentos de frequência (`Frequencia`) ligados a essa turma;
  - registros de aula (`RegistroAula`) ligados a essa turma;
  - vínculos de alunos com a turma, para evitar resquícios em cálculos de frequência.
- Essa regra garante que uma turma excluída não reproveite presenças/faltas antigas caso seja recriada.

## Como rodar

1. Crie e ative uma `venv`.
2. Instale as dependências:

```bash
pip install -r requirements.txt
```

3. Copie `.env.example` para `.env` e ajuste os valores necessários.
4. Inicialize o banco:

```bash
flask --app run init-db
```

5. Crie o administrador inicial:

```bash
flask --app run seed-admin
```

6. Execute a aplicação:

```bash
python run.py
```

## Próximos passos recomendados

- introduzir Alembic ou Flask-Migrate
- continuar quebrando [app/routes/registros/core.py](/C:/Users/FMtic/Documents/Nextcloud/MeusDados/Codeberg/pauta-online-refatorado/app/routes/registros/core.py:1) em módulos menores por domínio
- criar testes com `pytest` para autenticação, turmas, frequência e permissões
- substituir capturas genéricas de exceção por exceções mais específicas nos fluxos mais sensíveis
