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
