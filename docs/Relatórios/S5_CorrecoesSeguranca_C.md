# S5 — Correções de Segurança (Prompt C)

**Data:** 30/10/2026 · **Branch:** nova_feature · **Sem push**

## E0 — Leitura (valor efetivo de sessão)

- (a) O tempo de sessão **efetivo** hoje é **60 min deslizantes** (`PERMANENT_SESSION_LIFETIME` com `SESSION_REFRESH_EACH_REQUEST=True`), confirmado em `config.py`/`app/__init__.py`. O limite absoluto de **8 h** (S1-06, `SESSION_ABSOLUTE_LIFETIME`, padrão 8 h, configurável via `SESSION_ABSOLUTE_HOURS`) foi adicionado em paralelo e não prorroga com atividade.
- (b) `User` **não** herda `AuditoriaMixin`; o listener `before_flush` só audita objetos com `updated_by_id`, por isso o incremento de `session_version` via Core não gera `LogAcao` de alteração de usuário.
- (c) `login_user`/`logout_user` concentrados em `app/auth.py` (login local, LDAP, Google callback/vínculo, trocar-senha, logout). Templates com link para `/logout`: apenas `base.html` (botão Sair), convertido em formulário POST com CSRF (S1-16).
- (d) O helper `tests/_helpers.py::login_as` grava `sv` e `iat`, sem mudar a semântica dos testes.

## E1 — Pendências do Prompt B

- `.gitignore` (`instance/error.log*`) e remoção de `instance/error.log.1` do índice já commitados em `3a220eb`. Script e teste das contas expostas commitados em `1ccf0ea`. Conferido: `git status` não traz mais artefatos do B.

## E2 — Migration `session_version`

- Coluna `session_version INTEGER NOT NULL DEFAULT 0` em `user`, migration `b5c6d7e8f9a0` (revises `c9d0e1f2a3b4`), aditiva, idempotente por inspeção, downgrade remove a coluna. Aplicada em `pautaon_ensaio` (25 linhas) e `pautaon` (21 linhas). Backups em `instance/backups/`.

## E3 — Invalidação de sessão e tempo absoluto

- Login (local, LDAP, Google) grava `sv` e `iat` na sessão, limpando a sessão anterior (anti-fixação). `user_loader` rejeita sessão sem `sv` ou com `sv` divergente (sem SELECT extra). Limite absoluto de 8 h de `iat`. Incremento atômico via Core em: logout, troca/reset de senha, edição de role/unidade, inativação e exclusão. Log único "Sessões revogadas" nos casos administrativos.

## E4 — Logout por POST (S1-16)

- `/logout` aceita somente POST com CSRF; GET é inócuo (redirect para `/painel` ou `/login`). Botão Sair em `base.html` virou formulário POST mantendo as classes. Testes atualizados.

## E5 — Reset das contas expostas nos dumps

- Script `scripts/forcar_troca_contas_expostas.py` evoluído com `--modo reset`: substitui o hash por hash aleatório descartado, `first_login=True`, `session_version+1`, numa transação; sem e-mail e sem senha padrão. Dry-run por padrão; `--aplicar` exige `--autorizar-principal` fora do ensaio; backup com `password`/`first_login`/`session_version` anteriores.
- Dry-run (30/10/2026): **0 contas** com hash do dump ainda em uso em `pautaon` (21 contas, 17 com senha local) e em `pautaon_ensaio` (25 contas, 21 com senha local) — as contas já haviam sido tratadas em execução anterior; nenhuma aplicação adicional necessária. Nenhum e-mail/hash/CPF impresso.
- Geradas variantes `_com_sessao` e `_sem_sessao` em `.tmp/` (último carimbo). Arquivos antigos `.tmp/forcar_troca_producao_*_20261030_202242.sql` removidos. **Aviso:** `.tmp/` está dentro do Nextcloud; apagar os novos `.sql` após aplicar em produção.

## E6 — Prova final

- Suíte verde: `test_s1_sessao.py` (31+), `test_security_regressions.py` (45), `test_reset_senha_aleatoria.py` (9), `test_forcar_troca_contas_expostas.py` (21). Cookie copiado antes do logout não autentica depois; expiração absoluta e GET `/logout` inócuo cobertos pelos testes.

## Contagens

- `pautaon`: 21 contas (17 senha local, 4 LDAP), 0 com hash do dump.
- `pautaon_ensaio`: 25 contas (21 senha local, 4 LDAP), 0 com hash do dump.
- Tabelas contadas sem variação de linhas na migration (36 tabelas).

## Pendências restantes

- **D:** rate limit por conta, tempo constante do login, troca de unidade por POST (`/trocar-unidade/<id>`), achados baixos.
- **E:** política de senha no cadastro admin já endereçada na entrega de senhas temporárias; envio de senha por link de definição e LGPD (matriz de acesso a dados sensíveis, log de acesso).
- Reescrita do histórico (S3) pendente do usuário.
- S1-06 e S1-16 (logout) marcados como resolvidos no MER §12.29.

## Passo a passo para produção

1. Backup do banco de produção.
2. `flask db upgrade` (migration `b5c6d7e8f9a0`) — ou variante `sem_sessao` se a coluna ainda não existir.
3. Deploy do código.
4. Aplicar o `.sql` de reset na variante adequada (`com_sessao` se a coluna já existe, senão `sem_sessao`).
5. Avisar usuários: logout encerra sessões em todos os dispositivos; sessões atuais caem uma vez (refazer login).
6. Apagar os `.sql` de `.tmp/` após aplicar.
