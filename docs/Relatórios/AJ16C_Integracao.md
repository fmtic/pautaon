# AJ16-C — Integração e Ensaio Final do AJ16-B

**Data:** 09/11/2026
**Repo:** `D:\pautaon`, branch `nova_feature`
**Tag implantada:** `release-2026-11-05` (commit `0e14fef`)
**HEAD após integração:** `ed21a6b`

---

## 1. Integração

### 1a. Estado do repo

`git status` estava limpo na `nova_feature` (após stash de alterações locais da `main`).

### 1b. Comparação de branches

- `git log --oneline 0e14fef..nova_feature`: **vazio** — a `nova_feature` não avançou depois de `0e14fef`.
- `git log --oneline nova_feature..aj16b-valor-aula`: 4 commits do AJ16-B.
- `git diff --stat 0e14fef nova_feature`: vazio — nenhum arquivo da `nova_feature` toca os arquivos do AJ16-B.

### 1c. Merge

```
git merge aj16b-valor-aula
Updating 0e14fef..ed21a6b
Fast-forward
26 files changed, 2166 insertions(+), 1351 deletions(-)
```

Merge **fast-forward**, sem conflitos. HEAD passou para `ed21a6b`.

### 1d. Head Alembic

```
flask db heads
f2a3b4c5d6e7 (head)
```

Head único confirmado.

### 1e. Limpeza do worktree

- `git worktree remove` do worktree em `AppData\Local\Temp\opencode\aj16b_wt`: OK.
- `git branch -d aj16b-valor-aula`: deletada (was `ed21a6b`).

---

## 2. Suíte

### Venv

Venv novo (`.venv_aj16c`) com `requirements.txt` e `requirements-dev.txt` fixados:
- pytest==9.0.3, Flask==3.1.3, SQLAlchemy==2.0.48, alembic==1.18.4, ruff==0.17.1, psycopg==3.3.6.

### Resultado

```
1660 passed, 0 failed, 0 skipped, 965 warnings in 1444.53s
```

Meta atingida: **0 failed, 0 skipped**.

### Ruff (F821, F811, F841, F401) nos arquivos do AJ16-B

- 1 achado: F401 `datetime` importado mas não usado em `app/models/pedagogico.py:15`.
- **Pré-existente**: o import já estava em `0e14fef` (antes do AJ16-B). Não é achado novo.
- **Sem achados novos do AJ16-B.**

---

## 3. Ensaio com a produção

### Dump

O dump `instance/backups/pautaon_prod_2026-11-09.dump` **não existe**. Usado o dump de produção disponível `instance/backups/pautaon_producao_2026-11-03.dump` (revisão `c4d5e6f7a8b9`, pré-A1) + upgrade até `c1d2e3f4a5b6` + 8 valores sintéticos (sem dado pessoal) para simular o estado esperado da produção (catálogo com 8 valores, 0 frequências com valor).

### Contagens antes da migration (c1d2e3f4a5b6)

| Consulta | Valor |
|---|---:|
| `alembic_version` | `c1d2e3f4a5b6` |
| `frequencia` total | 130 |
| `frequencia` com valor | 0 (esperado 0) |
| `valor_esportista` | 8 (esperado 8) |
| `registro_aula` | 10 |

### Após `flask db upgrade` (f2a3b4c5d6e7)

| Verificação | Resultado |
|---|---|
| `alembic_version` | `f2a3b4c5d6e7` |
| `registro_aula_valor_esportista` | 0 (vazia, esperado) |
| coluna `frequencia.valor_esportista_id` | removida (0 = não existe) |
| `valor_esportista` | 8 (preservado) |
| `frequencia` total | 130 (idêntico) |
| `registro_aula` | 10 (idêntico) |
| dono da tabela nova | `postgres` |

### Ciclo downgrade/upgrade

| Etapa | `alembic_version` | Tabela nova | Coluna antiga | `valor_esportista` |
|---|---|---|---|---:|
| Downgrade -1 | `c1d2e3f4a5b6` | não existe | existe | 8 |
| Upgrade | `f2a3b4c5d6e7` | existe (0) | não existe | 8 |

### GETs autenticados (5 papeis × 3 rotas)

| Papel | `/frequencia` | `/painel` | `/planejamento` |
|---|---:|---:|---:|
| admin | 200 | 200 | 200 |
| pedagogico | 200 | 200 | 200 |
| professor | 200 | 200 | 403 |
| secretaria | 200 | 302 | 200 |
| gerencia | 403 | 200 | 403 |

**Total 5xx: 0.** Os 403 e 302 são esperados (permissão e redirect de papel).

### Limpeza

- Banco temporário `pautaon_aj16c_ensaio`: **removido** (confirmado `exists=0`).
- `pautaon`: **intacto** (freq_total=77, valor_esportista=8).

---

## 4. Lista de Deploy

Gerada em `docs/Relatórios/AJ16C_ListaDeploy.md`.

- **Copiar (A/M):** 26 arquivos (ver lista no documento).
- **Remover (D):** nenhum.
- **Pasta `migrations\`:** copiar inteira.
- **`requirements.txt`:** não mudou — não precisa `pip install`.
- **Excluídos:** `.env`, `instance\`, `chaves\`.

---

## 5. Conclusão

A integração do AJ16-B na `nova_feature` foi feita por merge fast-forward, sem conflitos. O head Alembic é único (`f2a3b4c5d6e7`). A suíte completa passou com 1660 passed, 0 failed, 0 skipped no venv novo com requirements fixados. O ensaio contra banco temporário (produção simulada) confirmou: migration aplica com sucesso (0 vínculos, coluna removida, catálogo preservado), o ciclo downgrade/upgrade é reversível, e GETs autenticados de 5 papeis em 3 rotas não produzem 5xx. O worktree foi removido e a branch deletada.
