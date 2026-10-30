# F1 — Autor do lançamento em frequência e conselho de classe

**Data:** 30/10/2026 · **Branch de trabalho:** `nova_feature` · **Sem push**
**Escopo:** registrar quem salvou cada linha de `frequencia` e de `conselho_resposta` — o autor é **sempre o último usuário que salvou** (sem campo de autor original). Só banco: nenhuma tela, relatório, BI, impressão ou permissão foi alterada.

---

## 1. Pré-requisito e guarda de sincronização

**G1/P2 conferido antes de começar:** head `d6e7f8a9b0c1` em **pautaon** e **pautaon_ensaio**, `turma_curso.professor_id` com `is_nullable = NO` e zero ofertas com professor NULL nos dois bancos. Suíte de partida: **1042 passed** (4m56s).

**A guarda disparou na abertura:** o `HEAD` estava em `main@c16a5ce` (o merge do `git pull --tags origin main` externo), `nova_feature` tinha voltado para `a24574b` e existia `nova_feature (conflicted copy 2026-10-30 144052)` dentro de `.git/refs/heads/` — o Nextcloud está sincronizando o diretório `.git`. O conteúdo **não** se perdeu (`git diff 90988bd HEAD` vazio). Por decisão do usuário: **sanitizar e retomar** — o ref conflitado desapareceu sozinho, `nova_feature` voltou a apontar para `90988bd` e a rodada seguiu nessa branch (árvore idêntica, `git checkout` sem escrita de arquivo).

Nenhum arquivo de código apareceu alterado por sincronização durante as quatro etapas (`git status` conferido no início de cada uma).

---

## 2. Resultado por etapa

### E0 — Leitura (sem commit)

Inventário completo dos pontos de gravação e do que o projeto já oferecia:

| Ponto | Tabela | Cria/altera | `current_user`? | Passou a gravar autor? |
|---|---|---|---|---|
| `app/utils/logica.py::salvar_frequencia` (único caminho do `POST /frequencia`, rota `app/registros/core.py::frequencia`) | `frequencia` | cria + altera `conceito`/`valor_esportista_id` | **sim** (já usava `current_user.id` para `RegistroAula.instrutor_id`) | **sim** |
| `app/utils/logica.py::_planejar_frequencia` | `frequencia` | só leitura | — | não (não grava) |
| `app/registros/turmas.py:1943` (exclusão de turma) | `frequencia` | delete em massa | sim | não (não há autor em delete) |
| `app/registros/alunos.py:823` (desenturmação) | `frequencia` | só leitura | — | não (não grava) |
| `app/registros/alunos.py::transferir_aluno` | — | **não toca** `frequencia` (só desativa inscrição de origem, cria a de destino e `Transferencia`) | — | não |
| `app/services/turma_curso.py` (`oferta_tem_lancamentos`, `ofertas_com_lancamentos`) | `frequencia` | só leitura | — | não |
| `scripts/semear_roteiro_manual.py::_frequencia` (L537) | `frequencia` | cria + altera `conceito` | **não** (script) | NULL |
| `scripts/ensaio_l4_1_reativacao.py:255` | `frequencia` | cria (ensaio descartável) | **não** | NULL |
| `scripts/verificar_sinal_updated_at.py:102` | `frequencia` | cria (verificação descartada) | **não** | NULL |
| `scripts/remover_ofertas_sem_lancamento.py` | `frequencia` | delete | **não** | não |
| `migrations/versions/e7f3a1b9c4d5_...py:186` | `frequencia` | `UPDATE` (backfill de `turma_curso_id`) | **não** | não |
| 18 arquivos de `tests/test_*.py` | `frequencia` | criam sementes | **não** | NULL |
| `app/conselho.py::salvar_conselho` (L786 cria, L784 altera `resposta`) | `conselho_resposta` | cria + altera texto | **sim** (`@login_required`) | **sim** |
| `app/conselho.py::avaliar_turma` (L991) | — | grava `TurmaCurso.avaliacao_*`, **não** `conselho_resposta` | sim | não |
| `app/conselho.py::salvar_fechamento_data` (L892) | `ConselhoClasse` | grava `situacao_final`/`proxima_turma`, **não** a resposta | sim | não |
| `scripts/semear_roteiro_manual.py::_conselho` (L620-629) | `conselho_resposta` | cria + altera | **não** | NULL |
| `tests/test_painel_periodo.py:110`, `tests/test_d5_leitores.py:101` | `conselho_resposta` | sementes | **não** | NULL |

**O que `AuditoriaMixin`/`TenantMixin` já ofereciam**

- `TenantMixin`: só `unidade_id` — **as duas tabelas já herdam**.
- `AuditoriaMixin`: `updated_by_id` (FK `user.id`, `ON DELETE SET NULL`), `updated_by_name` (`String(100)`, snapshot), `updated_at` (`default`/`onupdate`) e o relacionamento `updated_by` (`lazy='joined'`).
- `app/models/auditoria_listener.py::before_flush`: preenche `updated_by_id/name` — e cria **um `LogAcao` por objeto** — em qualquer modelo que tenha o atributo; sem request/usuário grava `None`.
- **Por que as duas tabelas não usavam:** elas herdam **apenas** `TenantMixin`, não têm `updated_by_id` e por isso o listener as ignora. Eram as únicas tabelas de lançamento sem nenhum rastro de autor (`registro_aula.instrutor_id` cobre só o diário; `conselho_classe.instrutor_id` nunca foi preenchido no lançamento).

**Decisão de modelagem (reportada antes de implementar)**

1. **Colunas próprias `autor_id` + `autor_nome`**, sem herdar `AuditoriaMixin`: (a) a semântica pedida é "quem salvou o lançamento", não "última alteração de qualquer atributo"; (b) herdar o mixin faria o listener criar **1 `LogAcao` por linha de frequência a cada salvamento** (pauta de 30 alunos = 30 logs por clique) e um `JOIN` `updated_by` em todos os leitores de pauta; (c) o nome pedido é `autor_id`.
2. **`autor_nome` = sim**, replicando o padrão do projeto (`updated_by_name`, `Aluno.created_by_name`): com `ON DELETE SET NULL` o id desaparece e o snapshot é o único rastro que sobrevive à exclusão do usuário.
3. **Sem índice em `autor_id`:** nenhuma consulta lê autor hoje. O índice entra junto com a primeira consulta real.

### E1 — Modelo e migration (`f36f803`)

- `frequencia.autor_id` / `frequencia.autor_nome` e `conselho_resposta.autor_id` / `conselho_resposta.autor_nome`: nullable, FK `user.id` `ON DELETE SET NULL` (`fk_frequencia_autor`, `fk_conselho_resposta_autor`), snapshot `String(100)`, relacionamento `autor`.
- Migration `c9d0e1f2a3b4` (down_revision `d6e7f8a9b0c1`): **aditiva**, idempotente por inspeção de colunas, upgrade só adiciona e downgrade só remove — nenhuma linha é tocada em nenhuma direção.
- **Backups:** `instance/backups/pautaon_pre_autor_lancamento.sql` (575.629 bytes) e `instance/backups/pautaon_ensaio_pre_autor_lancamento.sql` (618.517 bytes).
- **Protocolo:** ensaio primeiro — `up` → conferência das duas tabelas/`\d` (FK `ON DELETE SET NULL` confirmada) → `down1` → `up` de novo; depois o principal com `up` e conferência. Head `c9d0e1f2a3b4` nos dois bancos.

### E2 — Gravação do autor (`9693f3e`)

- Helper único `app/utils/autor.py::autor_do_lancamento()` → `(id, nome)` do usuário autenticado; `(None, None)` fora de request (scripts/seeds). Mesmo formato de `AuditoriaMixin`, sem herdar o mixin.
- `salvar_frequencia`: **cria** com autor; em linha existente **só troca** quando o **conceito** muda (`elif freq.conceito != conceito`). Mexer apenas no Valor do Esportista não troca o autor.
- `salvar_conselho`: **cria** com autor; em resposta existente **só troca** quando o **texto** muda (`if resposta.resposta != value`). Regravar o mesmo texto não troca.
- Scripts e sementes: nenhuma alteração — continuam gravando NULL.
- **Sem N+1:** o autor vem do `current_user` já carregado pelo Flask-Login; nenhuma consulta nova por linha (coberto por teste na E3).
- **Não alterado:** regra de acesso, `POST /frequencia`, conselho, telas, relatórios, BI, impressão e permissões.

### E3 — Testes, ensaio e documentação

- **`tests/test_f1_autor_lancamento.py` (12 testes):** criação pelo professor da oferta; troca por outro usuário autorizado na mudança de conceito; regravação idêntica não troca; linha anterior à F1 continua NULL com a tela em 200; FK declara `SET NULL` + linha sobrevive à exclusão do usuário com nome preservado; contexto sem usuário grava NULL; ≤1 `SELECT` na tabela `user` no POST com 3 alunos; e os mesmos casos em `conselho_resposta` (`salvar_conselho`) + tela do conselho em 200.
- **Suíte:** 1042 → **1054 passed** (0 falhas, 5m14s). Ruff `F821/F811/F841` limpo em `app`, `tests` e `migrations`.
- **MER:** §7.19 e §7.25 (colunas novas), §8.24 (regra completa), §11 (revisões `d6e7f8a9b0c1` e `c9d0e1f2a3b4` + head atual) e §12.26 (pendências).
- **Backlog:** seção "Alterações do dia — 30/10/2026 (F1 …)".

---

## 3. Contagens de banco (antes → depois)

| Banco | Tabela | Linhas antes | Linhas depois | Linhas com autor | Bloco antes |
|---|---|---|---|---|---|
| pautaon | `frequencia` | 54 | **54** | 0 | 0 |
| pautaon | `conselho_resposta` | 78 | **78** | 0 | 0 |
| pautaon_ensaio | `frequencia` | 18 | **18** | 0 | 0 |
| pautaon_ensaio | `conselho_resposta` | 5 | **5** | 0 | 0 |

Nenhum backfill foi feito: o histórico anterior à F1 permanece NULL nos dois bancos, como decidido.

---

## 4. Ensaio no `pautaon_ensaio` (oferta 45, semente M1)

Roteiro real pelo `POST /frequencia` (cliente de teste), com data **livre** da oferta:

| Passo | Resultado |
|---|---|
| Lançamento como **professor da oferta** (`[ROTEIRO] Professor`, id 120) | `autor_id = 120`, `autor_nome = "[ROTEIRO] Professor"` |
| Reedição por outro usuário (**Administrador**, id 1) mudando A → F | `autor_id = 1`, `autor_nome = "Administrador"` |
| Regravação do **mesmo** conceito F pelo professor | autor **mantido** em 1 |
| Linha criada com autor temporário + exclusão do usuário | linha sobreviveu, `autor_id = NULL`, `autor_nome = "Temp F1"` (SET NULL real no PostgreSQL) |
| Contagens antes × depois | 18 / 5 / 4 → **18 / 5 / 4** |

**Incidente contido:** a primeira execução do roteiro escolheu uma data que **já tinha** frequência e diário semeados e, no cleanup, apagou essas duas linhas pré-existentes do ensaio (18 → 17 e 4 → 3). O ensaio foi **restaurado** pelo dump `pautaon_ensaio_pre_autor_lancamento.sql` e a migration reaplicada (head `c9d0e1f2a3b4`); o roteiro passou a escolher data livre, a nunca apagar linha pré-existente e a validar que as contagens voltam ao valor inicial. O banco principal **não** foi afetado — nele houve **somente** a migration.

---

## 5. Pendências (registradas em MER §12.26)

1. **Exibir o autor em tela** — a coluna existe e é preenchida, mas nenhuma tela, relatório, BI ou impressão a lê; falta a definição de **quem pode ver** (professor, gestão, secretaria, todos).
2. **Autor original** — a decisão atual guarda só o **último** que salvou: a cada reedição o primeiro lançador é perdido. Histórico completo exigiria uma tabela de auditoria de lançamentos, não uma coluna.
3. **`registro_aula.instrutor_id`** — continua sobrescrito a cada salvamento da pauta, com a mesma limitação de "último que salvou" e sem snapshot do nome.

---

## 6. Commits

| Hash | Etapa | Assunto |
|---|---|---|
| — | E0 | leitura (sem commit) |
| `f36f803` | E1 | feat(f1): autor_id e autor_nome em frequencia e conselho_resposta (migration c9d0e1f2a3b4) |
| `9693f3e` | E2 | feat(f1): grava autor do lancamento em frequencia e conselho_resposta (E2) |
| HEAD da rodada | E3 | test(f1): autor do lancamento, relatorio e MER/backlog (E3) — hash final em `git log -1` (este relatório faz parte dele) |

**Regressão focada:** `test_f1_autor_lancamento`, `test_conselho_oferta`, `test_conselho_professor`, `test_valor_esportista_lancamento`, `test_valor_obrigatorio`, `test_notnull_professor_oferta` e `test_g1p2_links_impressao` → **104 passed** (41s).

**Estado final:** branch `nova_feature`, árvore limpa, suíte **1054 passed**, ruff `F821/F811/F841` limpo, head Alembic `c9d0e1f2a3b4` nos dois bancos.
