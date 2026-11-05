# Runbook de Deploy/Release — pautaON

Runbook de **atualização de release** (código + banco) no servidor de produção.
Complementa o `docs/manual_deploy.md` (montagem inicial de IIS/Apache, HTTPS, LDAP, notificador) —
este arquivo trata **somente** da janela de atualização de uma instalação já existente.

**Contexto desta release:** o código na branch `nova_feature` está em **24 revisões Alembic à frente**
da produção. Produção atual em `c4d5e6f7a8b9`; head do código `c1d2e3f4a5b6` ( cadeia completa e
prova no dump restaurada em `docs/Relatórios/AJ9B_ProvaProducao.md`, `AJ9C_PosUpgrade.md` e `AJ13_Verificacao.md`).

> **Regra permanente:** nenhuma consulta neste runbook grava nada. Os `UPDATE`s indicados são
> **manuais, caso a caso, com VALUES explícito** — nunca scripts de atualização em massa.

---

## 1. Janela de manutenção

- Agendar janela com o sistema **indisponível** (pare o IIS no início; não há modo de somente-leitura para usuários).
- Duração estimada: 30–60 min (backup + cópia + upgrade + smoke). Previsão de rollback cabe na mesma janela.
- Antes de começar, confirmar: espaço em disco para o dump, acesso ao servidor e ao banco, e que não há gravação em andamento (turno de lançamento).

## 2. Backup do banco — imediatamente antes de qualquer mudança

Logo antes de tocar em qualquer coisa (código incluso), gerar o dump **novo** do banco de produção:

```powershell
pg_dump -Fc -f pautaon_pre_release_<YYYY-MM-DD>.dump <banco_producao>
```

- Formato custom (`-Fc`) para restaurar com `pg_restore`.
- **Conferir o tamanho e a data do arquivo gerado antes de continuar.** Este dump é o único ponto de rollback de dados.
- Fazer o dump **imediatamente antes** minimiza a janela de dados perdidos (qualquer gravação posterior ao dump não estará nele — por isso o app deve estar parado).

## 3. Cópia do código

Copiar os arquivos do release para o diretório da aplicação, **sem sobrescrever**:

- `.env` (configuração local do servidor — chaves, DATABASE_URL);
- `instance/` (SQLite local, uploads, backups, logs);
- `chaves/` (certificados/segredos locais).

Itens obrigatórios na cópia:

- **`migrations/` inteira** (a pasta completa, inclusive `versions/` — copiar só arquivos novos quebra a cadeia);
- `app/`, `scripts/`, `tests/` (opcional em produção), `requirements.txt`, `requirements-dev.txt`, `config.py`, `run.py`, templates e estáticos.

**Remover do servidor os arquivos que foram deletados no código** do release (comparar a lista de
arquivos do pacote com o diretório de destino; arquivos órfãos de releases anteriores continuam sendo
importados/servidos). Conferir em particular `app/`, `app/templates/` e `app/static/`.

## 4. Dependências

No virtualenv da aplicação, com **Python 3.14.7** (versão usada nos ensaios AJ9/AJ13/AJ14):

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 5. Migrations

```powershell
flask db upgrade
flask db current   # DEVE responder: c1d2e3f4a5b6 (head)
```

- Ponto de partida esperado em produção: `c4d5e6f7a8b9` → **24 revisões** serão aplicadas.
- Se `flask db current` não fechar em `c1d2e3f4a5b6`, **parar** e investigar antes de seguir (não rodar `downgrade`; a recuperação é pelo dump).
- Atenção conhecida: **banco vazio não chega ao head** (baseline quebrada; `e1e3a5b2c333` não idempotente — pendência no backlog). Este runbook vale para **upgrade** de banco que já está em `c4d5e6f7a8b9`.
- Nota da release: a coluna `curso.carga_horaria` **deixa de existir** (removida em `d1e2f3a4b5c6`); no banco atual há **7 valores não nulos** que serão descartados pelo upgrade, sem destino no novo schema. O dump do passo 2 é o que guarda esses valores (ver `AJ9C_PosUpgrade.md`).

## 6. Dados: alunos ativos sem `unidade_id`

Aluno sem `unidade_id` **fica fora dos escopos por unidade** (regra AJ10-R; MER §8.27) — não herda unidade das inscrições. Levantar os casos na produção (SELECT):

```sql
SELECT id, nome FROM aluno WHERE ativo = true AND unidade_id IS NULL ORDER BY id;
```

Para cada linha encontrada, decidir **manualmente** a unidade e aplicar um `UPDATE` pontual com
`VALUES` explícito (um aluno por vez, conferindo o nome). **Não** rodar UPDATE em massa.

- Backfill **opcional** (não bloqueia o release): regularizar `unidade_id` NULL em linhas antigas de
  frequência/conselho/registro de aula com `scripts/backfill_unidade_id_nulos.sql` — as agregações já
  escopam por `Turma.unidade_id`, então o efeito é de consistência. Se rodar, **regerar as contagens do
  dia** (BI/painéis) depois do backfill.

## 7. Reiniciar IIS

Reiniciar o pool de aplicação no IIS (ou `iisreset` da aplicação) para carregar o novo código e as
novas dependências. Confirmar que o app sobe sem erro de import e que `/login` responde.

## 8. Smoke manual (pós-deploy)

Percorrer na tela, com usuário real de cada papel:

1. **Login** (local; AD se aplicável) e logout (sessão revogada por `session_version` funciona).
2. **Painel** do gestor e painel do professor (só ofertas dele).
3. **Frequência** — abrir pauta de uma oferta e conferir lançamentos.
4. **Lançamento do conselho** — individual por aluno em uma oferta do professor logado.
5. **Cadastro de aluno com foto e documento** — upload aceito (assinatura validada) e exibição.
6. **BI** — abrir a Central, executar um indicador qualquer com filtros (unidade/período/turno) e exportar XLSX. **INS-006/INS-007 não devem aparecer** na lista.

Sem 500 em nenhuma etapa. Qualquer 500: olhar `instance/error.log`, decidir rollback ou correção pontual.

## 9. Variáveis de ambiente de produção

O `.env`/configuração do servidor deve ter (ver `docs/manual_deploy.md` §1 e S1 no backlog):

| Variável | Valor em produção |
|---|---|
| `APP_ENV` | `production` |
| `SESSION_COOKIE_SECURE` | `true` **se o site atende por HTTPS** (padrão do app já é Secure; desligar só com `APP_ENV=development` declarado) |
| `SECRET_KEY` | obrigatória, aleatória, ≥ 32 caracteres (sem fallback; app recusa subir sem ela) |
| `UPLOAD_FOLDER` | **fora de `static/`** (ex.: `instance/uploads`) — servida só por rota autenticada |
| `GOOGLE_OAUTH_*` | **ausentes** se a integração Google não está em uso (a presença habilita rotas/botões da integração) |

Não versionar `.env`, `instance/` nem `chaves/` (já garantido pelo `.gitignore`; conferir no servidor).

## 10. Rollback

- **Rollback = restaurar o dump + os arquivos antigos da aplicação.** Nunca usar `flask db downgrade`
  para reverter a release: parte das revisões tem perda documentada no downgrade (H5b) e o caminho de
  volta não é garantido. Sequência:
  1. Parar o IIS.
  2. `dropdb`/recriar o banco de produção e `pg_restore -d <banco> --clean pautaon_pre_release_<data>.dump` (ou restaurar sobre o banco conforme a prática do DBA).
  3. Copiar de volta os arquivos de código **pré-release** (o diretório antigo deve ter sido preservado antes do passo 3, ex.: renomeado, não apagado).
  4. Reiniciar IIS e conferir `/login`.
- Dados gravados **depois** do dump são perdidos no rollback — mais uma razão para o dump ser imediatamente antes de qualquer mudança e o app estar parado.

---

_Relatório desta tarefa: `docs/Relatórios/AJ15_Docs.md`. Regras de negócio citadas: MER §8.2/§8.27._
