# AJ8 — Pré-release: segurança e ensaio de migrations

- **Data:** 2026-11-03
- **Branch:** `nova_feature`
- **Push:** não realizado

## Resumo executivo

- Nenhum `.env`, diretório `chaves/`, arquivo `.pem`, `.cer`, `.key`, `.dump`,
  diretório de credenciais, `instance/uploads/` ou `.tmp/` está versionado no
  HEAD. A busca histórica também não encontrou `.env`, `chaves/`, chaves,
  dumps ou `instance/uploads/`. O `.env` e `chaves/` existem localmente; seus
  conteúdos não foram lidos nem copiados.
- Gitleaks e TruffleHog não estão instalados. A varredura manual do histórico
  por padrões de chave, senha, token e URL com credencial não confirmou nenhum
  segredo commitado. Os falsos positivos em
  [scripts/forcar_troca_contas_expostas.py](../../scripts/forcar_troca_contas_expostas.py#L345)
  e nas linhas 511/543 são literais curtos de SQL e interpolação de variáveis
  de execução, não valores de credenciais.
- O histórico contém 20 arquivos sob `app/static/uploads/` (8 PNG, 3 JPG e
  9 PDF), hoje ausentes do HEAD. Os conteúdos não foram abertos. É necessário
  confirmar que são sintéticos; se contiverem dados pessoais, removê-los do
  histórico Git e avaliar a exposição.
- Foram corrigidos três problemas triviais: conteúdo do ticker agora é texto,
  o dry-run do notificador não registra o corpo da mensagem, e padrões de
  arquivos de ambiente/credenciais foram adicionados ao `.gitignore`.
- `requirements.txt` tem 12 achados do pip-audit em três pacotes. As correções
  de `cryptography` e `oauthlib` exigem saltos major e ficam pendentes de
  decisão, conforme backlog §12.29.
- Os dois bancos reais foram consultados somente por `SELECT`; nenhuma
  contagem mudou. O clone de ensaio foi criado a partir de `pautaon`, testado
  e removido.

## Achados

| ID | Severidade | Arquivo:linha | Recomendação / estado |
|---|---|---|---|
| AJ8-01 | Média — potencial | Histórico: `app/static/uploads/` (20 arquivos binários, sem linha de código) | Confirmar com o responsável se os arquivos são sintéticos. Se houver dados pessoais, purgar o histórico Git e avaliar quem teve acesso; a ausência no HEAD não remove os blobs dos commits antigos. Nenhum conteúdo ou nome de arquivo foi incluído neste relatório. |
| AJ8-02 | Média — corrigido | [app/static/js/utils/ticker.js](../../app/static/js/utils/ticker.js#L14) | A implementação anterior inseria texto do banco com `innerHTML`, permitindo DOM XSS caso o ticker fosse conectado. Corrigido para criar um nó de texto. O ticker está atualmente inativo/desconectado, portanto o achado era latente. |
| AJ8-03 | Média — decisão de configuração | [config.py](../../config.py#L76), [config.py](../../config.py#L168), [config.py](../../config.py#L170) | `SESSION_COOKIE_SECURE` é `true` por padrão, mas uma variável de ambiente explícita pode desligá-lo também em produção. `HttpOnly` permanece `true`; `SameSite` é `Lax` por padrão e pode ser sobrescrito. Confirmar `SESSION_COOKIE_SECURE=true` na implantação; decidir se produção deve rejeitar `false`. O override está documentado como intencional, então não foi alterado sem decisão. |
| AJ8-04 | Média | [config.py](../../config.py#L186), [app/__init__.py](../../app/__init__.py#L222) | CSP é enviada como `Content-Security-Policy-Report-Only` e não bloqueia execução. Planejar a remoção dos usos inline e migrar para uma política CSP efetiva antes de depender dela como mitigação de XSS. |
| AJ8-05 | Média | [app/utils/disparo_email.py](../../app/utils/disparo_email.py#L35), [app/utils/disparo_email.py](../../app/utils/disparo_email.py#L39), [app/utils/disparo_email.py](../../app/utils/disparo_email.py#L97) | O serviço registra destinatários em logs de sucesso/erro e cria uma thread destacada por envio. Redigir identificadores pessoais dos logs e avaliar fila/worker limitado; não alterado por exigir decisão sobre rastreabilidade e execução em produção. |
| AJ8-06 | Baixa — WIP/decisão | [app/utils/tricker.py](../../app/utils/tricker.py#L4), [app/utils/tricker.py](../../app/utils/tricker.py#L23), [app/utils/tricker.py](../../app/utils/tricker.py#L46), [app/__init__.py](../../app/__init__.py#L271) | O blueprint não é registrado; o módulo importa `app.models.rss`, mas o modelo atual está em `app.models.tricker`, e o template solicitado não existe. Por isso, as rotas não estão ativas nem cobertas pela matriz de rotas do professor. Se reativado, decidir também se gerência, secretaria e serviço social devem poder gerenciar avisos: a allowlist atual inclui esses papéis. Não há busca de feeds nem URL controlada pelo usuário no código atual, portanto não foi identificado SSRF. |
| AJ8-07 | Baixa — configuração | [config.py](../../config.py#L203) | O destino padrão de uploads fica em `instance/uploads/`, fora de `static/`, mas `UPLOAD_FOLDER` pode sobrescrevê-lo sem validação de confinamento. Confirmar que a configuração de produção continua fora de conteúdo público. |

### Dependências

O `pip-audit -r requirements.txt` encontrou 12 ocorrências (incluindo
repetições de advisory) em `cryptography`, `oauthlib` e `pytest`. As severidades
e versões de correção foram conferidas em OSV/NVD:

| Severidade | Pacote instalado | Advisory | Correção mínima indicada |
|---|---|---|---|
| Alta (CVSS 4.0: 8.2) | `cryptography==46.0.7` | CVE-2026-69247 / PYSEC-2026-3552 | `50.0.0` |
| Alta (CVSS 4.0: 8.7) | `cryptography==46.0.7` | CVE-2026-69249 / PYSEC-2026-3553 | `49.0.0` |
| Alta (CVSS 3.1: 7.5) | `cryptography==46.0.7` | GHSA-537c-gmf6-5ccf | `48.0.1` |
| Média (CVSS 4.0: 6.9) | `cryptography==46.0.7` | CVE-2026-69248 / PYSEC-2026-3554 | `49.0.0` |
| Média (CVSS 3.1: 6.8) | `oauthlib==3.3.1` | CVE-2026-49265 / PYSEC-2026-4114 | `4.0.0` |
| Sem severidade publicada | `oauthlib==3.3.1` | CVE-2026-49272 | `4.0.0` |
| Média (CVSS 3.1: 6.8) | `pytest==8.3.4` | CVE-2025-71176 / PYSEC-2026-1845 | `9.0.3` |

`requirements.txt` tem 97 requisitos diretos, todos fixados por versão exata
ou commit imutável. Há, porém, um conflito: [requirements-dev.txt](../../requirements-dev.txt#L1)
inclui a base e fixa `pytest==9.0.3`, enquanto a base fixa `pytest==8.3.4`
([requirements.txt](../../requirements.txt#L75)). Assim,
`pip-audit -r requirements-dev.txt` não consegue resolver o ambiente. A
correção do conflito e os saltos major de cryptography/oauthlib devem ser
decididos antes de alterar os manifests. O backlog
[§12.29](../../backlog_desenvolvimento.md#L1604) já registra cryptography e
oauthlib como pendentes de salto major; não foram atualizados nesta auditoria.

## Revisão de RSS, ticker e notificador

- O ticker atual lê texto do banco e o expõe como JSON; não há busca de RSS,
  requisição HTTP para URL fornecida pelo usuário ou SSRF no código atual.
- O script do Google Chat lê o caminho da conta de serviço e escopos de
  variáveis de ambiente em
  [config.py](../../config.py#L233); não foram encontrados segredos
  embutidos. `NOTIFICADOR_DRY_RUN` é `true` por padrão. O dry-run registrava
  anteriormente a mensagem e o identificador do espaço; agora registra apenas
  que a simulação ocorreu.
- O notificador não inicia thread/job nem tem agendamento ou chamada de
  aplicação encontrados. O cliente do Google Chat é chamado sem `timeout`
  explícito, dependendo do padrão da biblioteca.
- A aplicação possui envio de e-mail em thread destacada, registrado no achado
  AJ8-05. O `F401` no import não usado de `app/utils/tricker.py:5` também foi
  observado; o módulo continua WIP e não foi reativado parcialmente.
- O diff de `config.py` na branch não contém alterações locais. O commit
  histórico que adicionou as opções do Google Chat introduz configuração por
  ambiente e dry-run habilitado por padrão; não enfraquece as verificações de
  produção.

## Configuração de produção

- `SECRET_KEY` vem do ambiente, não tem fallback e é validada com mínimo de
  32 caracteres; o valor padrão antigo é recusado.
- `DEBUG` fica desligado por padrão e a aplicação recusa `DEBUG=true` em
  `APP_ENV=production`.
- Cookies: `Secure=true` por padrão, `HttpOnly=true`, `SameSite=Lax` por
  padrão; ver AJ8-03 para overrides.
- `CSRFProtect` é inicializado globalmente. Não foram encontradas rotas
  `csrf.exempt`, portanto a lista de isenções é vazia.
- `MAX_CONTENT_LENGTH` é 20 MiB. Uploads usam `instance/uploads/` por padrão,
  com o risco de override descrito em AJ8-07.
- Há bloqueio de login: conta, 5 falhas em 15 min, com bloqueio escalonado de
  15/30/60 min; IP, 30 falhas em 15 min e bloqueio de 15 min.
- As respostas incluem `X-Frame-Options: SAMEORIGIN`,
  `X-Content-Type-Options: nosniff` e `Referrer-Policy`. HSTS só é emitido
  quando o Flask detecta HTTPS; atrás do IIS, seguir a configuração de proxy
  descrita em [docs/manual_deploy.md](../manual_deploy.md#https-hsts-e-proxy-reverso-s1-09--s1-15).
- Erros 500 devolvem página genérica sem stack trace ao cliente; a stack é
  registrada no log do servidor.
- Não foram consultados valores efetivos de configuração de produção ou do
  `.env`; a avaliação acima cobre o código e seus padrões.

## Ensaio de migrations e dados

- `flask db heads`: uma única head, `c1d2e3f4a5b6`.
- Antes do ensaio, `pautaon` e `pautaon_ensaio` já estavam nessa head. O clone
  `pautaon_rel_teste` foi criado com `TEMPLATE pautaon`; `flask db upgrade`
  terminou com código 0 em 3,06 s e não aplicou revisões, pois não havia
  revisões pendentes. Não houve lock, backfill ou erro. Portanto, o ensaio
  confirma o estado já atualizado, mas não exercita uma migration pendente.
- GETs executados no clone com conexões PostgreSQL configuradas como
  `default_transaction_read_only=on`:

| Papel | `GET /painel` | `GET /conselho` |
|---|---:|---:|
| admin | 200 | 200 |
| pedagógico | 302 para `/trocar-senha` (conta em primeiro acesso) | 302 para `/trocar-senha` |
| professor | 200 | 200 |
| secretaria | 302 para `/painel/secretaria` | 200 |
| serviço social | 200 | 200 |
| gerência | 200 | 200 |
| pendente | sem conta ativa para smoke | sem conta ativa para smoke |

- Após o ensaio, `pautaon_rel_teste` foi removido. As contagens foram iguais
  antes/depois em todas as 38 tabelas dos dois bancos reais:

| Banco | Revisão | Linhas totais | `user` | `conselho_resposta` | `turma_curso` | `log_acao` |
|---|---|---:|---:|---:|---:|---:|
| `pautaon` | `c1d2e3f4a5b6` | 3265 | 22 | 78 | 4 | 1198 |
| `pautaon_ensaio` | `c1d2e3f4a5b6` | 3700 | 25 | 6 | 12 | 1747 |

Não houve diferença em contagens de `log_acao` nem em qualquer outra tabela.

## Correções e validação

| Alteração | Commit |
|---|---|
| Teste de regressão para dry-run sem conteúdo/identificador nos logs | `1c4505c7ecd42e5392592db2267a3e600e912420` |
| Redação dos logs de dry-run do notificador | `e3ab2ac3d1d52753392ce17ff83241c5be4a6f1a` |
| Renderização do ticker por nó de texto | `e80acbf9f07d1425319eeb7863fdbb6a2c0245c2` |
| Ignorar variantes `.env.*`, chaves, dumps e diretórios de credenciais | `952e8b00c75fdaabef4122a0dfdecc18f129367d` |

- Suíte completa (`pytest -q -ra`): **1611 passed, 0 failed, 0 skipped**;
  896 warnings, incluindo `LegacyAPIWarning` do SQLAlchemy.
- Teste focalizado do notificador: **1 passed**.
- Ruff (`F821,F811,F841,F401`) nos arquivos Python alterados:
  **All checks passed**.
- `node --check` e teste isolado com payload HTML sintético no ticker:
  passaram; o payload permanece em nó de texto.
- Nenhum pacote foi alterado nos manifests; a dependência Google Chat ausente
  no ambiente local foi instalada na versão já pinada em `requirements.txt`
  apenas para executar o teste focalizado.

## Decisões pendentes

1. Confirmar se os arquivos históricos em `app/static/uploads/` são sintéticos;
   autorizar limpeza do histórico se não forem.
2. Decidir a política para `SESSION_COOKIE_SECURE=false` em produção.
3. Decidir os upgrades major de `cryptography`/`oauthlib` e resolver o pin
   conflitante de pytest entre manifests.
4. Definir os papéis autorizados a gerenciar o ticker antes de ativar o
   blueprint e incluí-lo na matriz de rotas.
5. Priorizar a migração de CSP Report-Only para uma política efetiva e a
   adoção de fila/redação dos logs de e-mail.
