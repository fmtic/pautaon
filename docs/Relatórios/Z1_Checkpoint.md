# Z1 — Checkpoint de integridade (28/10/2026)

**Branch:** `nova_feature` · **HEAD:** `43d6bdb` (= `origin/nova_feature`, sem commits locais pendentes) · **Autor dos commits do dia:** fabiano-motta
**Natureza:** tarefa de leitura. Nenhum arquivo de `app/` ou `tests/` foi alterado. Único efeito colateral planejado: upgrade/downgrade **somente** no banco de ensaio (`pautaon_ensaio`). O banco principal (`pautaon`) recebeu apenas `SELECT`.
**Entregas do dia sob verificação:** A1 achados M1, Valores do Esportista, Atividades da aula, Diário global com filtros, guarda de acesso do diário, abas persistentes.

---

## 1. P0 — Commits de 28/10 desde `a5b34c8`

`git log --pretty="%h|%ad|%an|%s" --date=iso a5b34c8..HEAD` → 13 commits, todos de `fabiano-motta`.

| Commit | Hora | Entrega | Conteúdo principal |
|---|---|---|---|
| `b362d29` | 10:17:46 | M1 (apoio) | `scripts/semear_roteiro_manual.py` |
| `2622bb4` | 10:17:59 | M1 (apoio) | roteiro manual (93 casos) + `docs/Relatórios/M1_RoteiroTesteManual.md` |
| `e422ff0` | 10:41:10 | **Valores do Esportista (parte 1)** | **apenas templates**: `frequencia/lancar.html`, `planejamento/planejamento.html` e o novo `frequencia/lancar copy.html`. A própria mensagem diz "as rotas ainda não foram criadas" |
| `45a1312` | 10:49:54 | **A1 achado D2** | `app/services/frequencia_oferta.py` + `tests/test_a1_historico_legado_d2.py` |
| `1a9bfda` | 10:50:32 | **A1 travessão** | `app/registros/alunos.py` + `tests/test_a1_historico_status_ausente.py` |
| `71e5991` | 10:55:00 | **A1 critério turma ativa** | `app/relatorios/bi_alunos.py` + `tests/test_a1_bi_turma_ativa.py` |
| `bd6236d` | 11:01:23 | A1 (docs) | `docs/Relatórios/A1_AchadosM1.md`, MER, backlog |
| `596c3ab` | 13:21:27 | **Valores (parte 2) + Atividades da aula** | modelos (`aulas.py`, `pedagogico.py`), `app/registros/core.py`, `frequencia.js`, `lancar.html`, `app/utils/logica.py`, migrations `b7c8d9e0f1a2` e `c8d9e0f1a2b3`, 5 arquivos de teste |
| `9f93d0e` | 13:26:33 | **Abas persistentes** | `app/conselho.py`, `conselho/perguntas.html`, `planejamento/planejamento.html` + `test_conselho_perguntas_abas.py` e `test_planejamento_abas.py` |
| `5b99ab6` | 13:26:46 | **Diário — acesso/navegação** | `app/registros/turmas.py`, `dashboard/professor.html`, `turmas/detalhe.html`, `turmas/observacoes.html` + `test_diario_observacoes_acesso.py` |
| `0f00504` | 13:26:53 | Docs do dia | MER, backlog e 4 relatórios (`A1_ValoresDoEsportista`, `DIARIO_ObservacoesAcesso`, `FREQ_AtividadesDaAula`, `UI_AbasPersistentes`) |
| `bcbcfd3` | 13:32:56 | **Observações globais com filtros** | `app/relatorios/observacoes.py` (novo), `relatorios/__init__.py`, `painel_pedagogico.html`, `turmas/observacoes.html` + `test_relatorios_observacoes.py` |
| `43d6bdb` | 13:41:19 | Limpeza de layout | remove link *Períodos*; **deleta `docs/erros MD/Erro.md` e `tmp_test.txt`** |

**Confirmação dos SHAs citados na tarefa:** `45a1312`, `1a9bfda`, `71e5991` (A1) ✔ · `e422ff0` (Valores) existe, mas é commit **parcial/WIP**: só templates, zero teste, rotas inexistentes — a entrega funcional está em `596c3ab` ✔ (com ressalva) · Atividades = `596c3ab` ✔ · Diário/acesso = `5b99ab6` ✔ · Observações globais = `bcbcfd3` ✔ · Abas = `9f93d0e` ✔.

### Working tree no momento do checkpoint

Nenhum arquivo de `app/`/`tests/` foi tocado por esta tarefa. Porém o working tree **não está limpo**: há 8 arquivos modificados por edição paralela (mtime 15:12–15:13, durante a execução desta tarefa) — troca do rótulo "Observações/Descrição da Aula" → "Observações da Aula" em `lancar.html`, `lancar copy.html`, `turmas/observacoes.html`, `MER.md`, `backlog_desenvolvimento.md`, `c8d9e0f1a2b3_atividades_aula.py`, `test_atividades_aula.py` e `FREQ_AtividadesDaAula.md`. Não foram incluídos no commit do relatório.

Não rastreados: `scripts/ensaio_shell.ps1` (P5, entrou no commit) e `instance/error.log.1` (5,2 MB, rotação do `RotatingFileHandler` durante as execuções de teste — não é coberto pelo `.gitignore`, que só ignora `*.log`).

---

## 2. P1 — Suíte por ponto da história

Execução em `git worktree` temporário (detached), `python -m pytest -q -p no:cacheprovider`, sem tocar no working tree principal. Todas as árvores removidas ao final (`git worktree list` volta a mostrar apenas o repo principal).

| Ponto | Commit | Esperado (relatórios) | Obtido | Falhas |
|---|---|---|---|---|
| (a) base | `a5b34c8` | 722 | **722 passed** (144 s) | 0 |
| (b) `e422ff0~1` | `2622bb4` | 722 (M1 não mexe em teste) | **722 passed** (220 s) | 0 |
| (c) `e422ff0` | `e422ff0` | **773** (`A1_ValoresDoEsportista` §8) | **722 passed** (223 s) | 0 |
| (d) HEAD | `43d6bdb` | 826 | **826 passed** (248 s) | 0 |

Nenhum `failed`/`error` em nenhum ponto. O ponto (d) foi executado em worktree limpo porque o working tree principal recebeu edições paralelas durante a tarefa.

### Contagem coletada commit a commit (`--collect-only`, sem executar)

| Commit | Testes coletados | Δ | Origem do Δ |
|---|---|---|---|
| `a5b34c8` | 722 | — | baseline |
| `b362d29` | 722 | 0 | só script |
| `2622bb4` | 722 | 0 | só docs |
| `e422ff0` | 722 | 0 | só templates |
| `45a1312` | 728 | +6 | `test_a1_historico_legado_d2.py` |
| `1a9bfda` | 729 | +1 | `test_a1_historico_status_ausente.py` |
| `71e5991` | **735** | +6 | `test_a1_bi_turma_ativa.py` |
| `596c3ab` | **787** | +52 | 38 de Valores (`test_valor_esportista*` = 5 arquivos) + 14 de Atividades |
| `9f93d0e` | **805** | +18 | 10 `test_planejamento_abas.py` + 8 `test_conselho_perguntas_abas.py` |
| `5b99ab6` | **813** | +8 | `test_diario_observacoes_acesso.py` |
| `bcbcfd3` | **826** | +13 | `test_relatorios_observacoes.py` |
| `43d6bdb` | 826 | 0 | só layout |

### Reconciliação com a cadeia dos relatórios (722 → 735 → 773 → 783 → 791 → 805 → 813 → 826)

| Número do relatório | Existe no histórico? | Testes que mudam e por quê |
|---|---|---|
| 722 | ✔ `a5b34c8` (= `b362d29` = `2622bb4` = `e422ff0`) | baseline |
| 735 | ✔ `71e5991` | A1 nos 3 commits (6 + 1 + 6 = 13). Coincide com `A1_AchadosM1.md` |
| **773** | ✘ **nenhum commit** | `A1_ValoresDoEsportista.md` atribui 735 → 773 (+38) à entrega Valores, mas o commit de Valores (`e422ff0`) **não adicionou teste algum** — só templates. Os 38 testes de Valores entraram junto com os 14 de Atividades em `596c3ab`, que salta 735 → **787** |
| **783** | ✘ **nenhum commit** | `A1_ValoresDoEsportista.md` §9 (§ "correção de abas") conta +10 → 783 |
| **791** | ✘ **nenhum commit** | `UI_AbasPersistentes.md` conta a **mesma** entrega de abas como 783 → 791 (+8). Os dois arquivos de teste de abas (10 + 8 = 18) foram commitados **juntos** em `9f93d0e`, que leva 787 → **805**. A mesma entrega aparece somada duas vezes, com bases diferentes |
| 805 | ✔ `9f93d0e` — **mas com outro dono** | `FREQ_AtividadesDaAula.md` atribui 791 → 805 (+14) a Atividades. O +14 de Atividades é real, porém ele está dentro do +52 de `596c3ab` (787). O estado 805 é o commit das **abas** |
| 813 | ✔ `5b99ab6` | +8 — diário/acesso, coerente com `DIARIO_ObservacoesAcesso.md` |
| 826 | ✔ `bcbcfd3` (= HEAD) | +13 — observações globais, coerente com `REL_ObservacoesFiltros.md` |

Fechamento aritmético: 722 + 13 (A1) + 52 (Valores+Atividades) + 18 (abas) + 8 (diário) + 13 (observações) = **826**. Ou seja, o total está certo; o que não existe é o estado intermediário 773/783/791, e o rótulo do 805 está deslocado em um commit. Causa provável: os números intermediários foram medidos no working tree daquela sessão (antes do agrupamento final dos arquivos de teste em `596c3ab` e `9f93d0e`), não em commits.

---

## 3. P2 — Alembic

**Cadeia confirmada no código:** `8d2e3f4a5b6c` (h5b drop colunas agenda) → `b7c8d9e0f1a2` (valor_esportista) → `c8d9e0f1a2b3` (atividades_aula).

**Head única no código:** `ScriptDirectory.get_heads()` = `['c8d9e0f1a2b3']`; `get_bases()` = `['6a8df39d']` (branch único, sem head múltipla após o merge `b02f2051bc1e`).

### `alembic_version` nos dois bancos (SQL somente leitura)

| Banco | Alvo mascarado | `alembic_version` | Situação |
|---|---|---|---|
| principal | `postgresql+psycopg://postgres:***@localhost:5432/pautaon` | `c8d9e0f1a2b3` | no head — **não tocado** |
| ensaio | `postgresql+psycopg://postgres:***@localhost:5432/pautaon_ensaio` | `b7c8d9e0f1a2` | atrás do head (1 revisão) |

### O que foi feito no ensaio

Somente no `pautaon_ensaio`, com o alvo mascarado impresso antes e recusa explícita caso o nome não contivesse "ensaio":

1. `upgrade` → `b7c8d9e0f1a2` → **`c8d9e0f1a2b3`** (log do Alembic: `Running upgrade b7c8d9e0f1a2 -> c8d9e0f1a2b3`).
2. Conferência por SQL: `registro_aula.atividades` = `text`, `nullable=YES`; `valor_esportista` presente; `count(*)` de `registro_aula` = **4** (sem perda de linha).
3. Ciclo `downgrade -1` → volta a `b7c8d9e0f1a2`; SQL confirma que a coluna `atividades` **desaparece** e as 4 linhas permanecem.
4. `upgrade` de volta → `c8d9e0f1a2b3`; SQL confirma a coluna novamente.

Estado final: **principal = ensaio = `c8d9e0f1a2b3`**. Nenhuma variável `DATABASE_URL` foi definida na sessão do shell (verificado ao final: vazia); os comandos rodaram em processo próprio com a DSN derivada do `.env` trocando apenas o nome do banco.

---

## 4. P3 — Integridade de `<div>` nos templates

Contagem bruta (após neutralizar blocos Jinja, preservando linhas) + verificação com `html.parser.HTMLParser` (pilha de `<div>` com linha de abertura).

| Template | Linhas | `<div` | `</div>` | Δ | Parser |
|---|---|---|---|---|---|
| `frequencia/lancar.html` | 282 | 31 | 30 | **+1** | 1 `<div>` aberto e nunca fechado |
| `planejamento/planejamento.html` | 842 | 127 | 127 | 0 | OK |
| `conselho/perguntas.html` | 321 | 28 | 28 | 0 | OK |
| `turmas/observacoes.html` | 141 | 17 | 17 | 0 | OK |
| `relatorios/painel_pedagogico.html` | 541 | 140 | 140 | 0 | OK |

**Desbalanceamento em `frequencia/lancar.html`:** o `<div class="card mb-4 p-3">` aberto na **linha 56** nunca é fechado — o `</form>` da linha 276 encerra o form com o card ainda aberto (falta um `</div>` logo antes, ~linha 275). O HTMLParser não encontra nenhum `</div>` órfão, só esse fechamento ausente.

**É pré-existente, não foi introduzido em 28/10:** em `a5b34c8` a mesma contagem é 30/29 (Δ +1), e a cópia `lancar copy.html` em `e422ff0` repete 30/29. Browsers fecham o card automaticamente, por isso o sintoma não aparece em tela. **Não corrigido** (fora do escopo desta tarefa).

---

## 5. P4 — Referências mortas

### `app/templates/frequencia/lancar copy.html`

- Existe em disco, é **rastreado** (adicionado em `e422ff0`, 238 linhas, 30 `<div>` contra 29 `</div>` — mesmo desbalanceamento do original).
- **Nada renderiza, importa ou inclui o arquivo:** grep por `lancar copy` em `app/`, `tests/`, `scripts/` retorna zero ocorrências; grep por `lancar` em todo `app/` encontra **uma** única referência — `app/registros/core.py:527` → `render_template('frequencia/lancar.html', ...)`. Nenhum `include`/`extends` aponta para a cópia.
- As únicas menções estão em documentação: `docs/Relatórios/M1_RoteiroTesteManual.md:248`, `docs/Relatórios/FREQ_AtividadesDaAula.md:50` e `docs/Relatórios/A1_AchadosM1.md:32` (que já registra "continua no repositório").
- Conclusão: **arquivo morto**, candidato a remoção (não removido aqui).

### `docs/erros MD/`

- O diretório **existe e está vazio** (`Get-ChildItem` sem itens).
- `git ls-files "docs/erros MD"` → vazio; `git ls-tree HEAD "docs/erros MD"` → vazio: **nenhum arquivo rastreado**.
- `Erro.md` foi **adicionado em `00244ae`** ("vincula alunos às ofertas...") e **deletado em `43d6bdb`** (`git log --diff-filter=D` e `--diff-filter=AD` apontam o HEAD), no mesmo commit que também apagou `tmp_test.txt` e mexeu só no link *Períodos*. Ou seja: a exclusão entrou num commit de assunto alheio.
- Recuperável se necessário: `git show 43d6bdb^:"docs/erros MD/Erro.md"`.

---

## 6. P5 — `scripts/ensaio_shell.ps1` (novo)

Abre um PowerShell **filho** com `DATABASE_URL` apontando para o banco de ensaio; a sessão atual não é alterada.

- Uso documentado em uma linha no cabeçalho: `pwsh -NoProfile -File scripts/ensaio_shell.ps1` (e `-Diagnostico` para só conferir).
- DSN de origem: `$env:DATABASE_URL` se existir, senão a linha `DATABASE_URL` do `.env`. Troca **apenas** o segmento do nome do banco (preserva usuário, senha e query string — sem passar por `make_url`, para não re-renderizar a senha percent-encoded).
- **Recusa** (exit 1) qualquer alvo cujo nome de banco não contenha `ensaio`, antes de abrir qualquer processo.
- Imprime o alvo **mascarado** (`postgres:***@`) e a revisão `alembic_version` lida por `SELECT` antes de abrir o shell.
- `-Diagnostico` imprime alvo + revisão e retorna sem abrir o shell (usado no teste abaixo).

Verificação executada:

```
pwsh -File scripts\ensaio_shell.ps1 -Banco pautaon      -> "Recusado: o banco de destino 'pautaon' nao contem 'ensaio'. Nada foi aberto." (rc=1)
pwsh -File scripts\ensaio_shell.ps1 -Diagnostico        -> alvo mascarado + revisao c8d9e0f1a2b3 (rc=0)
"$env:DATABASE_URL"                                     -> vazio (sessao intacta)
```

---

## 7. P6 — Ruff

`ruff check --select F821,F811 app tests migrations scripts` → **All checks passed!**

---

## 8. Divergências e riscos encontrados

1. **Cadeia de números da suíte não é reproduzível** (773/783/791 não existem; 805 pertence às abas, não a Atividades). O total 826 está correto. Ação sugerida: corrigir as tabelas de `A1_ValoresDoEsportista.md`, `UI_AbasPersistentes.md` e `FREQ_AtividadesDaAula.md` para os estados reais (735 → 787 → 805 → 813 → 826).
2. **`e422ff0` é commit parcial** (só templates, sem rotas nem testes, como a própria mensagem admite): o histórico não reflete a divisão descrita nos relatórios. A entrega de Valores só ficou funcional em `596c3ab`, misturada com Atividades.
3. **`lancar.html` com `<div>` não fechado** (linha 56, Δ +1) — pré-existente, invisível em tela; risco de quebra ao editar o rodapé do form.
4. **`lancar copy.html` morto** (238 linhas duplicadas, sem referência) — ruído de manutenção; ainda recebeu edição em 28/10.
5. **`docs/erros MD/Erro.md` apagado** em `43d6bdb`, commit de assunto não relacionado, deixando o diretório vazio. Conteúdo só existe no histórico.
6. **Working tree sujo** por edição paralela (8 arquivos, renome do rótulo das observações) durante esta tarefa: o checkpoint de suíte vale para o **commit** `43d6bdb`, não para o working tree atual. Nada disso foi commitado por mim.
7. **`instance/error.log.1`** (5,2 MB) não rastreado e não ignorado: `.gitignore` cobre `*.log` mas não `*.log.1`. Sugestão: `instance/*.log*`.
8. **`HEAD == origin/nova_feature`**: os commits de 28/10 já estão no remoto; não há trabalho local pendente de push.
