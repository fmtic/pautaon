# S3 — Segredos no histórico do Git: o que há, o que rotacionar e como limpar

**Data:** 30/10/2026
**Escopo:** varredura de **todo** o histórico do repositório local (`d:\Nextcloud\FMtic\SysAdmin\pautaon`) — todas as branches, tags, remotos e refs (inclusive os refs de ferramentas de IA) — em busca de segredos e de dados sensíveis.
**Natureza:** **somente leitura**. Nada foi reescrito, nada foi apagado, nada foi empurrado (`push`) e nenhum segredo foi rotacionado por mim. Os passos da §4 são para **você** executar.
**Por que importa:** `github.com/fmtic/pautaon` é **público**. Tudo o que já foi commitado — inclusive o que foi apagado depois — continua acessível no histórico para qualquer pessoa (e por SHA, mesmo depois de reescrito, até o GitHub expurgar).

---

## §1 Como a varredura foi feita

| Item | Valor |
|---|---|
| Commits alcançáveis | **390** |
| Objetos no histórico | **4.435** (3.549 com caminho + 390 commits) |
| Blobs lidos no conteúdo | **1.969** (o restante são árvores) |
| Blobs pulados por tipo | **182** — imagens, fontes, PDF, zip, `.pyc`, `.css` (não carregam credencial) |
| Refs cobertas | **61** — `refs/heads` (5), `refs/remotes` (4), `refs/stash`, **`refs/agents/*` (19)**, **`refs/cline/checkpoints/*` (26)**, **`refs/codex/*` (4)** |
| Tags | **0** |
| `refs/pull/*` no clone local | **nenhuma** (o GitHub só materializa essa ref quando existe PR aberto) |
| Tamanho do `.git` | ~29 MB |

**Ferramentas:** `gitleaks`, `trufflehog` e `git-filter-repo` **não estão instalados** (e não instalei nada). O caminho usado foi:

```powershell
git rev-list --all --objects                      # todo objeto alcançável por qualquer ref
git cat-file --batch  <lista de blobs>            # conteúdo, em lotes de 200
git log --all --diff-filter=A -- <caminho>        # commit em que cada arquivo entrou
git log --all --diff-filter=D -- <caminho>        # commit em que saiu
git for-each-ref --format="%(refname)"            # refs cobertas
```

**Padrões aplicados** (13 grupos): `SECRET_KEY`, URL de banco com senha (`postgres*://usuário:senha@`), `LDAP_*PASSWORD/SECRET/BIND` e `ldap(s)://usuário:senha@`, `GOOGLE_*CLIENT_SECRET`, `MAIL/SMTP/EMAIL_*PASSWORD/USERNAME`, `-----BEGIN … PRIVATE KEY-----`, `-----BEGIN CERTIFICATE-----`, `AIza…` (Google), `sk-…` (OpenAI), `gh*_…` (GitHub), `AKIA…` (AWS), `xox[baprs]-…` (Slack) e, num segundo passo, **hashes de senha** (`scrypt:`, `pbkdf2:`, `$2[aby]$`, `$argon2`). Blobs binários (`.db`, dumps SQL) foram lidos como *latin-1* para pegar strings legíveis.

**Valores neste documento:** sempre mascarados (2 primeiros e 2 últimos caracteres, com o tamanho). Nenhum segredo completo aparece aqui.

---

## §2 Achados

### §2.1 Nenhum segredo de aplicação real no histórico

Os 9 padrões que dispararam (fora os hashes) são **todos placeholders**, conferidos um a um:

| Tipo | Onde | O que realmente é | Conclusão |
|---|---|---|---|
| `SECRET_KEY` | `.env.example` (6 versões), `README.md`, `config.py` (9 versões), `docs/Relatórios/*.md`, 53 `tests/*.py` | `tr...ao`, `de...ao` (o **fallback público** antigo, removido na E1 `7318ece`), `os.getenv("SECRET_KEY")`, chaves de teste `ch...90` | Placeholder / leitura de ambiente |
| URL de banco com senha | `.env.example`, `README.md`, `docs/manual_deploy.md`, `docs/Relatórios/P1_relatorio.md`, `I1_InfoProfessorModal.md`, `V2_ValorObrigatorio.md`, `V3b_EngajamentoTurma.md`, `scripts/preparar_deploy_onda4.py`, `scripts/ensaio_shell.ps1` | `usuario:se...ha` e `postgres:***` — nos relatórios os asteriscos são **literais** (`so_asteriscos=True`) | Placeholder mascarado |
| `LDAP_*` | — | nenhuma ocorrência com valor | — |
| URL LDAP com credencial | — | nenhuma ocorrência | — |
| `GOOGLE_*CLIENT_SECRET` | `README.md` | o “valor” é o nome da variável seguinte (`GOOGLE_OAUTH_REDIRECT_URI`), 72 caracteres | **Falso positivo** |
| `MAIL/SMTP` | `config.py` (2 versões) | `os.getenv("MAIL_PASSWORD")`, `os.getenv("MAIL_USERNAME")` | Leitura de ambiente |
| Chave privada / certificado | — | nenhuma ocorrência | — |
| Tokens (`AIza`, `sk-`, `gh*_`, `AKIA`, `xox`) | — | nenhuma ocorrência | — |
| `.env` real | — | **não está no histórico** (só `.env.example`) | — |

Ou seja: **não há chave de API, senha de banco, senha de bind LDAP, senha de SMTP, chave privada ou certificado reais no histórico** do que foi commitado até aqui.

### §2.2 O que existe de verdadeiro: dumps e log com dados pessoais

O problema real do histórico público **não é chave, é dado**:

| Caminho | Blob | Entrou em | Saiu em | Em `HEAD`? | Conteúdo |
|---|---|---|---|---|---|
| `instance/database.db` | `b624c789` | `8dece84` (15/04/2026) | `175244d` (15/04/2026) | não | SQLite de desenvolvimento: **7 hashes `scrypt`**, 47 e-mails distintos |
| `instance/database.db.bak` | `8567a0fa` | `f66a731` (22/09/2026) | `ca4178d` (27/09/2026) | não | **9 hashes `scrypt`**, 54 e-mails, 4 nomes |
| `instance/backups/database-antes-initdb-2026-09-29.db` | `8decfe47` | `ca9a736`/`6ca7600` (17–20/10/2026) | `38980ef` (22/10/2026) | não | **9 hashes `scrypt`**, 23 e-mails (inclui `projetograel.org.br`, `pgrael.local`) |
| `backup_20260923_194945.sql` (**raiz do repo**) | `edf721e4` | `ca9a736`/`6ca7600` (17–20/10/2026) | `667f4a8` (20/10/2026) | não | Dump SQL de **314.640 bytes**: **7 hashes `scrypt`**, 84 e-mails distintos (Gmail, Hotmail, iCloud, Outlook, institucionais) e **102 números de 11 dígitos** (formato CPF) |
| `instance/error.log.1` | `98bfd237` | `2185afe` (28/10/2026) | **nunca** | **SIM** | **5.199.585 bytes / 43.196 linhas** de traceback: caminhos locais do desenvolvedor (`C:\Users\FMtic\…`), 12 caminhos Windows distintos, 4 e-mails (um `@fmtic.com.br`), 240 linhas de erro de LDAP (mensagem, **sem credencial**) e 56 linhas de SQL com a coluna `user.password` |

Observações:

- `6ca7600` **não está em nenhuma branch** — veio de um checkpoint de agente de IA (`refs/agents/…`) e ainda é alcançável por esse ref no clone local. Ele **não** foi empurrado ao GitHub (os refs `agents/`, `cline/` e `codex/` são locais do IDE), mas o blob também aparece em `ca9a736`/`667f4a8`, que estão em `main`/`nova_feature`.
- Os hashes são `scrypt` do Werkzeug: não são reversíveis, mas **permitem ataque de dicionário offline** — e o dump traz o e-mail ao lado, o que torna o ataque direcionado.
- O `error.log.1` **está versionado agora**: `.gitignore` cobre `instance/*.db`, `instance/backups/` e `instance/uploads/`, mas **não** `instance/error.log*`.
- Nenhum desses arquivos foi tocado nesta etapa (não migrei, não apaguei, não reescrevi).

---

## §3 O que ROTACIONAR (o que realmente protege)

Ordem de prioridade, do risco maior para o menor:

1. **`SECRET_KEY` da instância em produção — rotacionar.** O fallback público `dev-key-*` ficou na árvore até a E1 (`7318ece`, 30/10/2026). Se o deploy (IIS/wfastcgi) chegou a subir **sem** `SECRET_KEY` no ambiente, ele usou esse valor, que é público: qualquer pessoa poderia **forjar cookie de sessão** (inclusive de admin). Mesmo com a E1 impedindo a inicialização sem chave, a chave que estiver em uso agora precisa ser troca de lugar se houver dúvida. Gerar com:
   `python -c "import secrets; print(secrets.token_urlsafe(48))"`
   Consequência da troca: **todas as sessões caem** (todo mundo faz login de novo) — avise antes.
2. **Senha do usuário `postgres`** — **não está no histórico** (só `usuario:senha` de exemplo e `postgres:***`). Rotacionar apenas se você suspeitar que ela já circulou por outro canal (documento, mensagem, backup compartilhado). Se rotacionar: atualizar `DATABASE_URL` no `.env` e nos dois bancos (`pautaon`, `pautaon_ensaio`) na mesma janela.
3. **Senha de bind do LDAP / `GOOGLE_CLIENT_SECRET` / senha de SMTP** — **nenhum valor real no histórico**: as ocorrências são só leitura de `os.getenv(...)`. Não há motivo técnico para rotacionar por causa desta varredura; rotacione se houver outro motivo (troca de pessoa, suspeita de vazamento por outro meio). Lembre que a senha de bind do LDAP, se errada três vezes, bloqueia a conta de serviço no AD.
4. **Senhas dos usuários dos dumps** — os hashes `scrypt` (7 no `database.db`, 9 no `.bak` e no `database-antes-initdb`, 7 no `backup_*.sql`) estão expostos. **Forçar redefinição** dessas contas (as que existem hoje) ou, no mínimo, verificar se alguma delas usa senha fraca. Os e-mails aparecem ao lado dos hashes, então o ataque é direcionado.
5. **Dados pessoais (LGPD)** — e-mails (84 distintos no SQL), nomes e 102 números com formato de CPF em repositório **público**. Não é “rotação”, é **tratamento de incidente**: registrar a ocorrência, avaliar comunicação e, principalmente, executar a limpeza da §4.
6. **Tokens de terceiros** — nenhum encontrado. Se algum dia existiu token de Google/AWS/GitHub em arquivo commitado, ele não aparece nesta varredura; se você já revogou algum por outro motivo, nada a fazer aqui.

> Rotacione **antes** de reescrever o histórico (§4.2). A reescrita remove o passado do repositório, mas não invalida uma credencial que já vazou.

---

## §4 Roteiro de limpeza do histórico (para você executar)

> Nada disto foi executado. É uma reescrita destrutiva: **todo clone existente deixa de ser compatível**. Combine com quem mais usa o repositório antes.

### §4.1 Pré-requisitos

```powershell
python -m pip install --user git-filter-repo      # ou: scoop/choco install git-filter-repo
git filter-repo --version
```

### §4.2 Roteiro, em ordem

**1. Rotacionar o que a §3 manda** (principalmente `SECRET_KEY`) e guardar as chaves novas fora do repositório.

**2. Backup em clone espelho** (não trabalhe no clone do dia a dia):

```powershell
cd D:\Nextcloud\FMtic\SysAdmin
git clone --mirror pautaon pautaon-backup-2026-10-30.git
cd pautaon-backup-2026-10-30.git
git bundle create ..\pautaon-backup-2026-10-30.bundle --all
```

**3. Clone de trabalho para reescrever:**

```powershell
cd D:\Nextcloud\FMtic\SysAdmin
git clone --mirror pautaon pautaon-limpeza.git
cd pautaon-limpeza.git
```

**4. Reescrever removendo os caminhos dos achados** (todos os commits, todas as branches):

```powershell
git filter-repo --invert-paths `
  --path instance/ `
  --path backup_20260923_194945.sql
```

- `--path instance/` cobre `instance/database.db`, `instance/database.db.bak`, `instance/backups/…` e `instance/error.log.1`.
- `--path backup_20260923_194945.sql` cobre o dump da raiz.
- Se você tinha `instance/uploads/` em algum commit antigo, ele sai junto (é o desejado).
- `git filter-repo` remove o `origin` de propósito; o passo 7 recoloca.

**5. Verificação pós-limpeza** (tem de dar zero em tudo):

```powershell
git rev-list --all --objects | Select-String "instance/|backup_20260923_194945.sql"
git log --all --oneline -- instance backup_20260923_194945.sql
git cat-file --batch-all-objects --batch-check='%(objecttype)' | Group-Object | Select-Object Name,Count
# nenhum blob com hash de senha deve sobrar:
git rev-list --all --objects | ForEach-Object { ($_ -split ' ',2) } | ForEach-Object { git cat-file -p $_ } 2>$null | Select-String -Pattern "scrypt:|pbkdf2:sha256"
git count-objects -vH      # confirma que o repositório encolheu
```

**6. Refazer as refs de ferramenta de IA** (elas guardaram checkpoints do histórico antigo): apague `refs/agents/*`, `refs/cline/*` e `refs/codex/*` **antes** de reescrever, ou refaça o clone do IDE depois — senão o histórico antigo volta a ser alcançável no seu clone.

```powershell
git for-each-ref --format="%(refname)" refs/agents refs/cline refs/codex |
  ForEach-Object { git update-ref -d $_ }
git stash clear
```

**7. Force-push de todas as branches e tags** (é o passo irreversível, no remoto):

```powershell
git remote add origin https://github.com/fmtic/pautaon.git
git push --force --all origin
git push --force --tags origin
```

**8. `refs/pull/*`:** o GitHub **só cria** essa ref quando existe PR aberto; não há nenhuma neste clone. Se você abriu PRs no passado, os commits antigos continuam pendurados em `refs/pull/<n>/head` — feche/apague os PRs (ou peça ao suporte) e **confirme** com:

```powershell
git ls-remote origin "refs/pull/*"
```

Se aparecer alguma, ela precisa ser apagada no GitHub (Settings → não há UI para isso; é via suporte/API). Como o repositório não tem PRs hoje, o esperado é lista vazia.

**9. Expurgo no GitHub (obrigatório):** force-push **não** apaga os blobs órfãos — eles continuam acessíveis por SHA direto e nos caches da API. Abra um ticket em <https://support.github.com> pedindo **“remove cached views and references to unreachable objects / purge of sensitive data”** informando os SHAs dos blobs da §2.2. Enquanto isso não acontece, considere o conteúdo como **ainda público**.

**10. Depois da limpeza:**

- Todo mundo precisa **re-clonar** (clone antigo volta a empurrar o histórico velho no próximo push).
- Ligar **Secret scanning** e **Push protection** no GitHub (Settings → Code security and analysis).
- Fechar a lacuna do `.gitignore` e tirar o log do índice:
  ```powershell
  Add-Content .gitignore "instance/error.log*"
  git rm --cached instance/error.log.1
  git commit -m "chore: nao versionar logs da instancia"
  ```
- Opcional (recomendado): *pre-commit* com `gitleaks detect --staged` e uma regra de CI com `gitleaks detect --log-opts="--all"` para não repetir.

### §4.3 Checklist

- [ ] `SECRET_KEY` de produção rotacionada (sessões caem)
- [ ] Senhas dos usuários dos dumps forçadas a trocar
- [ ] Backup espelho + bundle guardados fora do repositório
- [ ] `git filter-repo --invert-paths --path instance/ --path backup_20260923_194945.sql` executado
- [ ] Verificação do passo 5 sem nenhum `instance/`, sem `scrypt:` e sem `backup_2026…`
- [ ] `refs/agents`, `refs/cline`, `refs/codex` e `stash` limpos
- [ ] `push --force --all` e `--tags`
- [ ] `git ls-remote origin "refs/pull/*"` vazio
- [ ] Ticket de expurgo aberto no suporte do GitHub
- [ ] `instance/error.log*` fora do índice e no `.gitignore`
- [ ] Secret scanning + push protection ligados

---

## §5 O que esta etapa NÃO fez

- **Não** reescreveu o histórico, **não** apagou arquivo, **não** fez `push` e **não** rotacionou nada.
- **Não** instalou `gitleaks`/`trufflehog`/`git-filter-repo` (a varredura foi feita com `git` nativo).
- **Não** imprimiu nenhum valor completo: tudo mascarado.
- **Não** commitou nada além deste `.md` no backlog/MER.
- Os scripts auxiliares da varredura ficaram em `.tmp/` (fora do Git). Para reproduzir: `git rev-list --all --objects` + `git cat-file --batch` com os 13 padrões da §1.

## §6 Referências

- `docs/Relatórios/S1_AnaliseSeguranca.md` — achados S1-01…S1-24 e ordem de correção.
- MER §12.28 — execução do Prompt A (E1 a E7).
- `docs/manual_deploy.md` — como a instância sobe hoje (IIS + wfastcgi; `run.app` como handler WSGI).
