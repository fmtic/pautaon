# Adendo AJ24 — Admin vincula conta Google pendente a usuário existente (unificação sem perda de dados)

**Data:** 20/11/2026 · **Branch:** `nova_feature` · **Migration:** nenhuma · **Schema:** inalterado · **Push/merge:** nenhum

## Motivação

Caso real em produção: a conta pendente `fabianomotta@projetograel.org.br`
(Global), criada pelo login Google (AJ17-B), precisava ser unificada à conta
existente `fabianomotta@pgrael.local` (Professor, NIT). O fluxo atual não
vincula sozinho e-mails diferentes — por decisão anterior, só o admin pode
fazer isso. A pendente nunca teve acesso; todo o histórico (frequência,
conselho, autoria de lançamentos, `log_acao`, professor da turma/oferta) pertence
ao alvo e deve continuar no `id` dele.

## Viabilidade sem migration

Confirmado no modelo (`app/models/usuarios.py:91-92`) e na migration
`6a8df39d_add_google_oauth_fields_to_user.py`: `user.google_id` (UNIQUE,
indexado) e `user.google_email` já existem. Não há coluna adicional de vínculo.
A unificação é, portanto, uma atualização atômica dessas duas colunas —
**nenhuma migration ou alteração de schema foi necessária**.

## Implementação

1. **Serviço transacional** `app/services/vinculo_google_admin.py` (novo):
   - valida origem (`role='pendente'` **e** `google_id` preenchido) e alvo
     (existe, ativo, não pendente, sem `google_id`, diferente da origem);
   - varre **todo o metadata do SQLAlchemy** (`db.metadata.tables` →
     `column.foreign_keys` com alvo `user.id`) — nenhuma lista manual de
     tabelas — e **recusa** se existir qualquer linha apontando para a pendente,
     com mensagem que nomeia `tabela.coluna=contagem`;
   - ordem na transação: `DELETE` da pendente + `flush()` **antes** de gravar
     `google_id`/`google_email` no alvo (evita violar `UNIQUE(user.google_id)`);
   - `LogAcao` na **mesma transação** (`Alteração de Cadastros`, rótulo já
     congelado pelo AJ4), com `admin_id`, `origem_id`, `alvo_id`, os dois
     e-mails e `google_email`; sem token/`secret`/senha;
   - `rollback` total em qualquer erro; `VinculoGoogleAdminError` para recusas
     esperadas (mensagem segura para o flash).

2. **Rota admin** `POST /usuarios/vincular-google/<id>` em `app/auth.py`:
   `@login_required` + checagem explícita `role == admin` (`abort(403)`),
   token CSRF via `csrf_token()` no formulário, confirmação explícita
   (`confirmar=1` + os dois e-mails conferidos no servidor) e
   `flash` + `redirect` para o painel. `painel_admin()` calcula os alvos
   elegíveis (ativos, não pendentes, sem vínculo Google, diferentes da própria
   pendente) e passa `alvos_vinculo` ao template.

3. **UI** `app/templates/admin/painel_admin.html`: botão de link só em
   pendentes com identidade Google; modal com `select` mostrando nome, e-mail,
   perfil e unidade de cada alvo, os dois e-mails em destaque e checkbox de
   confirmação. Sem alvo elegível, o modal explica o motivo e não submete nada.

4. **Efeito**: no próximo login Google com aquele e-mail, o callback encontra o
   alvo por `google_id`, atualiza só `google_email`, mantém `User.email`
   original (AD/local continua funcionando) e aplica as regras vigentes de
   domínio permitido, e-mail verificado e conta ativa. Fluxo OAuth, vínculo,
   domínios e perfis não foram alterados.

Fora de escopo (não implementado): desvincular, mesclar histórico de duas
contas, alterar perfil/unidade/senha/AD do alvo.

> **Atenção operacional:** a varredura é estrita, conforme especificado. Se a
> pendente tiver qualquer linha em outra tabela — incluindo `log_acao` de
> tentativas de "Acesso via Google" — a unificação será recusada com mensagem
> clara, para não descartar dados. Nesse caso é necessária decisão separada
> (por exemplo, autorizar o descarte apenas desses logs de acesso da pendente);
> nada foi feito automaticamente aqui.
>
> **Atualizado pelo Adendo AJ24-B (abaixo):** `log_acao.usuario_id` deixou de
> ser impeditivo — passou a ser reaponteado para o alvo na mesma transação.
> As demais FKs seguem estritas, com a mesma mensagem `tabela.coluna=contagem`.

## Arquivos tocados (pacote de deploy)

- `app/services/vinculo_google_admin.py` — **novo**: serviço transacional + varredura de FKs
- `app/auth.py` — rota admin, cálculo dos alvos e passagem ao template
- `app/templates/admin/painel_admin.html` — botão, modal e confirmação
- `tests/test_aj24_vinculo_google_admin.py` — **novo**: 15 testes
- `backlog_desenvolvimento.md`, este relatório

Goldens (`tests/snapshots/*`) **não** foram alterados: a tela do painel admin
não possui golden congelado e nenhum HTML de golden existente mudou.

## Verificação

- Novos testes: **15 passed** (`tests/test_aj24_vinculo_google_admin.py`):
  UI e alvos válidos, caminho feliz com contagens de `frequencia`/`turma`/
  `log_acao` do alvo idênticas antes e depois, login Google seguinte caindo no
  alvo, `LogAcao`, recusa por FK, recusa de alvo já vinculado/pendente/inativo/
  igual à origem, origem sem identidade Google, não-admin (403), CSRF, sem
  confirmação, rollback com erro simulado e FK criada em runtime descoberta
  pelo metadata.
- Regressões focadas (AJ23 + AJ23-B + logs AJ1/AJ4 + complemento Google +
  admin): **177 passed**.
- Suíte completa: **1926 passed, 0 failed** (base 1911 + 15 novos).
- `ruff --select F821,F811,F841` e `git diff --check`: limpos.
- Nenhuma migration/head alterado; sem push e sem merge.

---

## Adendo AJ24-B — Unificação Google: reaponte de `log_acao` da pendente

**Data:** 20/11/2026 · **Branch:** `nova_feature` · **Migration:** nenhuma · **Schema:** inalterado · **Push/merge:** nenhum · **Commit:** separado do AJ24

### Motivação

Em produção a pendente `fabianomotta@projetograel.org.br` (id 97) tem zero
referências nas 21 colunas de FK para `user`, mas exatamente uma linha em
`log_acao.usuario_id` — o próprio acesso via Google que a criou. Como toda
conta pendente nasce assim, a varredura estrita do AJ24 recusaria a unificação
**sempre**. Reapontear somente essa FK (em vez de descartar ou recusar) preserva
as linhas e mantém o fluxo utilizável.

### Verificação prévia de trava de imutabilidade

Antes de implementar, foi verificado — sem encontrá-la — qualquer trava que
impedisse a alteração:

- `CREATE TRIGGER` / `CREATE RULE`: **zero** ocorrências em todo o repositório;
  o DDL de `log_acao` em `scripts/postgres_schema.sql:172-184` e
  `migrations/versions/` não declaram trigger/regra;
- AJ1 (`tests/test_aj1_logs_filtro.py`) e AJ4 (`tests/test_aj4_logs_drift.py`):
  **zero** ocorrências de `trigger`, `append-only`, `imutável` ou bloqueio de
  escrita. O AJ4 congela **rótulos/categorias**, não linhas; o rótulo da
  unificação continua `Alteração de Cadastros` (categoria `edição`);
- a única menção a "append-only" é prosa descritiva em
  `docs/Relatórios/AJ6B5_ListaTurmaPorPapel.md:184-191`, e o próprio app já
  remove logs antigos em `app/auth.py:1438-1444`.

Não havia trava a contornar; nada foi desativado ou flexibilizado fora da FK
explicitamente autorizada.

### Implementação

1. `app/services/vinculo_google_admin.py`: a varredura via `db.metadata`
   continua cobrindo **todas** as FKs para `user.id`, com recusa
   `tabela.coluna=contagem`, **exceto** `log_acao.usuario_id` (constante
   `FK_LOG_ACAO_USUARIO`). Helpers extraídos: `_contar_fk()` e
   `logs_a_reapontar()` (contagem observável da pendente).
2. Na **mesma transação**, antes do `DELETE` da pendente:
   `UPDATE log_acao SET usuario_id = <alvo> WHERE usuario_id = <pendente>`,
   via `update(LogAcao)` com `synchronize_session=False`; o `rowcount` é a
   contagem exata de linhas movidas. `expire_all()` impede que uma relação
   `User.logs` carregada antes do UPDATE faça o delete anular o FK recém-movido.
3. Qualquer outra tabela com referência continua recusando **antes de qualquer
   escrita**; nem o UPDATE dos logs roda nesse caso.
4. Erro depois do UPDATE (inclusive no INSERT do log) → `rollback` total:
   logs voltam para a origem, pendente e `google_id` permanecem como antes.

### Auditoria

`LogAcao` não tem colunas específicas para os novos dados; o padrão `chave=valor`
em `detalhes`, já usado no AJ24, foi estendido para:

```
admin_id=<id> origem_id=<id> origem_email=<email> alvo_id=<id> alvo_email=<email> google_email=<email> logs_reapontados=<N>
```

`N` é o `rowcount` do UPDATE, então a origem dos registros movidos continua
rastreável. Sem token, `secret`, senha ou outros dados sensíveis.

### Arquivos tocados (AJ24-B)

- `app/services/vinculo_google_admin.py` — varredura com única exceção, reaponte transacional e log ampliado
- `tests/test_aj24_vinculo_google_admin.py` — 3 novos testes + 2 existentes reforçados
- `docs/Relatórios/AJ24_VinculoGoogleAdmin.md`, `backlog_desenvolvimento.md` — adendo/backlog

Nenhuma migration, schema, rota, template, perfil ou vínculo Google alterado.

### Verificação (AJ24-B)

- Foco AJ24 + AJ1/AJ4: **139 passed** (18 do arquivo AJ24 + filtro AJ1 e drift AJ4).
- Novos casos: 3 logs com ações distintas movidos (contagem exata, nenhum restante
  na origem, `logs_reapontados=3`), relação `User.logs` pré-carregada, erro
  simulado depois do UPDATE com rollback dos logs, e recusa por
  `turma.professor_id=1` com nada movido.
- Suíte completa: **1929 passed, 0 failed** (base 1926 + 3 novos).
- `ruff --select F821,F811,F841`, `ruff check`, `git diff --check`: limpos.
