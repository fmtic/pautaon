# AJ9 — Dependências e ensaio de migrations

- **Branch:** `nova_feature`
- **Push:** não realizado
- **Bancos reais:** somente `SELECT`; nenhuma gravação
- **Resultado geral:** dependências e suíte aprovadas; migrations não estão prontas para banco vazio

## Resumo executivo

- No ambiente isolado, foram validados `cryptography==50.0.0`,
  `oauthlib==4.0.0` e `pytest==9.0.3`. `pytest` e `pytest-timeout` ficam em
  `requirements-dev.txt`; as versões de produção não incluem `pytest`.
- `pip check` não encontrou requisitos quebrados e `pip-audit -r
  requirements-dev.txt` não encontrou vulnerabilidades conhecidas. A varredura
  AppMod de CVEs não aceita o ecossistema Python; foi usado `pip-audit`.
- A suíte completa terminou com **1610 passed, 0 failed, 0 skipped**, em
  19m21s. Houve 896 warnings, principalmente `LegacyAPIWarning` (`Query.get`)
  e um `DeprecationWarning` sobre `datetime.utcnow()`.
- O dump restaurado já estava na única head, `c1d2e3f4a5b6`; não havia
  migrations pendentes. `flask db upgrade` não alterou tabelas nem contagens.
- A prova de upgrade a partir de banco vazio **falhou**: a migration raiz
  tenta alterar `user`, tabela que não é criada pela cadeia. Este é um bloqueio
  para instalação nova.
- A comparação do schema do dump com os modelos encontrou divergência em
  `curso`: três colunas de auditoria e sua FK existem no banco, mas não no
  modelo ORM.
- Os bancos temporários foram removidos e sua ausência foi confirmada. As
  contagens completas de `pautaon` e `pautaon_ensaio` permaneceram idênticas
  ao baseline.

## Resultado por prova

| Prova | Resultado | Evidência principal |
|---|---|---|
| Dependências isoladas | **PASSOU** | cryptography 50.0.0, oauthlib 4.0.0, pytest 9.0.3; `pip check` e `pip-audit` limpos |
| Migrations de banco vazio | **FALHOU** | migration raiz espera tabela `user` preexistente |
| Restore + upgrade do dump | **PASSOU, sem migrations pendentes** | revisão permaneceu `c1d2e3f4a5b6`; contagens iguais |
| Comparação schema/modelos | **DIVERGÊNCIA** | `curso` tem 3 colunas e 1 FK de auditoria extras no banco |
| Downgrade da última revisão | **PASSOU** | `c1d2e3f4a5b6 → b5c6d7e8f9a0` em clone descartável |
| Smoke GET por papel | **PASSOU** | respostas 200/302 esperadas; conexões em modo read-only |
| Rota de teste de e-mail | **PASSOU** | rota ausente; testes existentes garantem 404 |
| Remoção ticker/notificador | **PASSOU** | código preservado em `feature/ticker`; suíte completa verde |

## Achados e recomendações

| ID | Severidade | Arquivo:linha | Recomendação / estado |
|---|---|---|---|
| AJ9-01 | Alta — bloqueio de instalação nova | [`6a8df39d_add_google_oauth_fields_to_user.py`](../../migrations/versions/6a8df39d_add_google_oauth_fields_to_user.py#L40) | Criar/definir um bootstrap de schema antes de liberar `flask db upgrade` em banco vazio. Não corrigido sem decisão sobre baseline. |
| AJ9-02 | Alta — risco de perda no rollback | [`3b7c9d1e4f20_adiciona_renda_mensal_e_tipo_deficiencia.py`](../../migrations/versions/3b7c9d1e4f20_adiciona_renda_mensal_e_tipo_deficiencia.py#L34) | O upgrade não adiciona `tipo_deficiencia`, mas o downgrade remove a coluna. Reconciliar a migration e não voltar a essa revisão sem backup. |
| AJ9-03 | Média — migration não idempotente | [`e1e3a5b2c333_manual_audit_columns.py`](../../migrations/versions/e1e3a5b2c333_manual_audit_columns.py#L21) | As colunas são adicionadas sem guards de existência. Definir tratamento para schema parcial sem reescrever migration já aplicada. |
| AJ9-04 | Média — drift ORM/schema | [`pedagogico.py`](../../app/models/pedagogico.py#L19), [`a9f3c8e2d1b7_add_audit_columns_core_tables.py`](../../migrations/versions/a9f3c8e2d1b7_add_audit_columns_core_tables.py#L66) | Alinhar `Curso` ao schema auditado ou decidir que as colunas/FK não pertencem ao modelo. Não alterado sem decisão. |
| AJ9-05 | Média — dado nulo antes de `NOT NULL` | Bancos reais; contagens na tabela acima | Definir correção/backfill, especialmente para `frequencia` em `pautaon` (52 linhas nulas), antes de aplicar a regra planejada. Nenhuma linha foi alterada. |

## Dependências

| Pacote | Antes | Validado |
|---|---:|---:|
| `cryptography` | `46.0.7` | `50.0.0` |
| `oauthlib` | `3.3.1` | `4.0.0` |
| `pytest` | `8.3.4` na base | `9.0.3` em `requirements-dev.txt` |
| `pytest-timeout` | na base | `2.4.0` em `requirements-dev.txt` |

`google-apps-chat` e `google-apps-card` foram removidos da base junto com o
notificador: a busca de imports/registros não encontrou uso na aplicação em
produção. `google-auth` continua usado pelo OAuth e calendário. A cadeia
reversa confirma `cryptography` via `google-auth` e `oauthlib` via
`requests-oauthlib`/`google-auth-oauthlib`. Não houve incompatibilidade de
dependências no `pip check`; o conjunto isolado passou pela suíte.

Todos os requisitos restantes têm versão exata ou referência imutável; `ldap3`
está fixado por hash de commit. O login Google não foi exercitado contra o
provedor real. **Smoke manual recomendado:** autenticar com uma conta Google
permitida e verificar callback/sessão; cancelar o consentimento e verificar
que não há sessão autenticada; validar rejeição de `state` inválido e logout.

## Migrations

### Prova 1 — banco vazio

`flask db upgrade` não chegou à head. A migration raiz
[`6a8df39d_add_google_oauth_fields_to_user.py`](../../migrations/versions/6a8df39d_add_google_oauth_fields_to_user.py#L32)
é declarada como primeira (`down_revision = None`), mas tenta adicionar
colunas à tabela `user` ([linha 40](../../migrations/versions/6a8df39d_add_google_oauth_fields_to_user.py#L40)).
Não há migration anterior que crie essa tabela. O upgrade foi revertido pela
transação; o clone vazio permaneceu sem tabelas e foi removido.

**Conclusão:** a cadeia não é aplicável a um banco PostgreSQL vazio sem uma
etapa de bootstrap/baseline. É necessária uma decisão sobre como inicializar
o schema antes de liberar instalação nova.

### Prova 2 — dump de produção restaurado

| Verificação | Resultado |
|---|---|
| Revisão antes/depois | `c1d2e3f4a5b6` |
| Heads | uma: `c1d2e3f4a5b6` |
| Revisões pendentes | nenhuma |
| `flask db upgrade` | sucesso, sem operações, 9,39 s |
| Tabelas | 38 antes e depois |
| Contagens por tabela | idênticas; nenhuma tabela mudou |
| Locks, backfills ou erros de migration | nenhum; não havia migration a executar |

No schema restaurado, as 37 tabelas de modelo correspondem às 37 tabelas de
negócio do banco (excluída `alembic_version`): não faltam tabelas nem colunas
do modelo e não há divergências de tipo. O banco contém, porém, três colunas
extras em `curso` — `updated_at`, `updated_by_id` e `updated_by_name` — e uma FK
de `curso.updated_by_id` para `user.id`; a classe ORM
[`Curso`](../../app/models/pedagogico.py#L19) não as declara. As colunas/FK
foram introduzidas por
[`a9f3c8e2d1b7_add_audit_columns_core_tables.py`](../../migrations/versions/a9f3c8e2d1b7_add_audit_columns_core_tables.py#L66).
Não foram alteradas sem decisão sobre qual lado é a fonte de verdade.

Verificações específicas:

- `aluno.documentos_entregues` é `JSONB`.
- `perfil_diversidade.tipo_deficiencia` existe como `varchar`.
- [`e1e3a5b2c333_manual_audit_columns.py`](../../migrations/versions/e1e3a5b2c333_manual_audit_columns.py#L21)
  **não é idempotente**: as três `op.add_column` não verificam se as colunas
  já existem. Reaplicar sobre schema parcialmente alterado pode falhar.
- Em
  [`3b7c9d1e4f20_adiciona_renda_mensal_e_tipo_deficiencia.py`](../../migrations/versions/3b7c9d1e4f20_adiciona_renda_mensal_e_tipo_deficiencia.py#L34),
  o `add_column(tipo_deficiencia)` está comentado, mas o downgrade remove a
  coluna ([linha 41](../../migrations/versions/3b7c9d1e4f20_adiciona_renda_mensal_e_tipo_deficiencia.py#L41)).
  Não foi feito downgrade dessa revisão; voltar até ela pode remover dados.

### Downgrade da última revisão

Em clone separado do banco atual, o downgrade explícito
`c1d2e3f4a5b6 → b5c6d7e8f9a0` terminou com sucesso em 6,35 s e removeu
`login_controle`, como esperado. O clone foi descartado.

### `unidade_id IS NULL` nos bancos reais

As contagens abaixo foram obtidas por `SELECT`; tabelas com `unidade_id` não
listadas têm zero linhas nulas.

| Tabela | `pautaon` | `pautaon_ensaio` |
|---|---:|---:|
| `aluno` | 1 | 1 |
| `configuracao_sistema` | 7 | 7 |
| `frequencia` | 52 | 0 |
| `log_acao` | 735 | 1333 |
| `registro_aula` | 4 | 0 |
| `user` | 6 | 6 |
| `conselho_resposta` | 78 | 0 |

Os 52 registros sem unidade em `frequencia` e os demais valores não nulos
precisam de política de correção/backfill antes de qualquer migration futura
que aplique `NOT NULL` (§12.10 do MER).

## Smoke GET e rota de teste de e-mail

O smoke usou sessões com usuários ativos do clone restaurado, em conexões
PostgreSQL configuradas como somente leitura. Foram consultados `/` e
`/dashboard`; nenhum conteúdo pessoal foi registrado.

| Papel | `/` | `/dashboard` |
|---|---:|---:|
| admin | 200 | 200 |
| gerência | 200 | 200 |
| pedagógico | 302 para troca de senha (`first_login`) | 302 para troca de senha |
| professor | 200 | 200 |
| secretaria | 200 | 302 para painel da secretaria |
| serviço social | 200 | 200 |

A rota legada de teste de e-mail já foi removida. A aplicação não registra
`/teste-email`; [`test_s1_teste_email_removido.py`](../../tests/test_s1_teste_email_removido.py#L21)
valida 404 para anônimo e autenticado. Não foi necessária alteração.

## Ticker/notificador fora do release

A branch local `feature/ticker` foi criada no commit-base
`5c7b2e106c8c6e8307183285f8f904f569165cb4` e conserva os arquivos do ticker e
notificador. Os commits funcionais relevantes preservados incluem:

- `07c90bddca0fd4addd4ed2851a3d6e369330872f` — ticker WIP.
- `6c9cae31d8c3f3e61d72a9b1470b8ae9f653c3e0` — configurações do Google Chat.
- `1c4505c7ecd42e5392592db2267a3e600e912420` — teste de logs do notificador.
- `e3ab2ac3d1d52753392ce17ff83241c5be4a6f1a` — redaction do dry-run.
- `e80acbf9f07d1425319eeb7863fdbb6a2c0245c2` — renderização como texto.
- `a3d3ab1f8e74380fc7d734999923b7e98d17416e` — renomeação dos arquivos.

Na `nova_feature`, foram removidos os arquivos de modelo, serviço, template,
JavaScript, script e teste específicos do ticker/notificador, além das
dependências Google Chat/Card. Não havia import/registro ativo na aplicação.
Nenhum push foi feito.

## Validação de qualidade

- Suíte isolada: **1610 passed, 0 failed, 0 skipped**, 896 warnings, 19m21s.
- `pip check`: `No broken requirements found`.
- `pip-audit -r requirements-dev.txt`: `No known vulnerabilities found`.
- Ruff (`F821,F811,F841,F401`) na árvore restante: 0 ocorrências de
  `F821/F811/F841`; 62 `F401` preexistentes em arquivos não alterados.
  Entre as versões anteriores dos arquivos Python removidos, somente
  `app/utils/tricker.py` tinha um `F401` (import sem uso); o arquivo foi
  removido da branch de release.
- Bancos temporários `pautaon_rel_vazio`, `pautaon_rel_prod` e
  `pautaon_rel_downgrade`: removidos e ausência confirmada.

## Contagens dos bancos reais

| Banco | Baseline | Após validação | `log_acao` |
|---|---:|---:|---:|
| `pautaon` | 38 tabelas / 3265 linhas | 38 / 3265 | 1198 → 1198 |
| `pautaon_ensaio` | 38 tabelas / 3700 linhas | 38 / 3700 | 1747 → 1747 |

Não houve diferença em nenhuma contagem por tabela. As consultas foram
somente leitura.

## Commits

- Dependências: `da321b76e6932cbb496a3c26b7101c04ee4846cc`
  (`fix(deps): patch cryptography and oauthlib pins`).
- Remoção do ticker/notificador: `a8288b12f248d8146efbb593a85506c1d7edd7e6`
  (`chore(release): remove unused ticker and notifier`).
- Este relatório foi commitado separadamente; seu hash está no histórico da
  branch `nova_feature`.

## Decisões pendentes antes do release

1. Definir/bootstrapar um schema-base para que `flask db upgrade` funcione em
   banco vazio.
2. Corrigir a assimetria de upgrade/downgrade da coluna
   `perfil_diversidade.tipo_deficiencia` antes de permitir rollback daquela
   revisão.
3. Decidir a estratégia de idempotência para `e1e3a5b2c333` sem reescrever
   migration já aplicada.
4. Alinhar o ORM de `curso` com as colunas/FK de auditoria do banco.
5. Definir correção/backfill dos `unidade_id` nulos antes de impor `NOT NULL`.
