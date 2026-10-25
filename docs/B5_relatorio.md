# B5 — Endurecimento das migrations `c3d4e5f6a7b8` e `d4e5f6a7b8c9`

Data: 25/10/2026 · Ramo: `Onda4` · Banco de produção **`pautaon` não tocado** · Nenhum commit.
Escopo alterado: **somente** `migrations/versions/c3d4e5f6a7b8_inscricao_exige_oferta.py` e
`migrations/versions/d4e5f6a7b8c9_programa_obrigatorio_na_oferta.py` + este relatório.

---

## 1. Passo 1 — Leitura (o que estava antes)

As duas revisões são o topo da escada linear da Onda 4 (a partir de `8c4e1f9a7d32` do dump):
`e7f3a1b9c4d5` → `d2e3f4a5b6c7` → `a1b2c3d4e5f6` → **`c3d4e5f6a7b8`** → **`d4e5f6a7b8c9`** (head).

Estado original (antes desta etapa), conforme `docs/P1_relatorio.md` §3 e §7:

* **`c3d4e5f6a7b8`** (`inscricao_exige_oferta.py`): ia direto para
  `batch_alter_table("inscricoes")` → `SET NOT NULL` em `turma_curso_id` e depois
  `CREATE UNIQUE INDEX uix_inscricao_ativa_aluno_oferta ... WHERE ativo IS TRUE`. Sem checagem
  prévia. Como o `SET NOT NULL` vem **antes** do índice, uma base com NULL *e* duplicata revelava
  **só um problema por vez** (defeito **P-2** do P1).
* **`d4e5f6a7b8c9`** (`programa_obrigatorio_na_oferta.py`): executava
  `UPDATE turma SET programa = (subconsulta da oferta ativa ... LIMIT 1)` **sem `WHERE` e sem
  `COALESCE`**, seguido de `SET NOT NULL` em `turma_curso.programa`. Para turma **sem oferta
  ativa**, a subconsulta retorna NULL e o `UPDATE` **apagava** o `turma.programa` existente —
  dano silencioso (defeito **P-1** do P1, ensaio E).

P1 §7 lista as correções estruturais como pendências explícitas (P-1/P-2), "fora do escopo" de P1
porque P1 não alterava migration alguma. **B5 executa exatamente essas duas correções.**

---

## 2. Diff — `c3d4e5f6a7b8` (Passo 3)

Adicionadas, antes do `batch_alter_table`, **duas checagens somente-leitura reportadas juntas em
um único `RuntimeError`** (PT). Nenhum dado é alterado nesta migration.

```python
def upgrade():
    conn = op.get_bind()
    # (i) inscrições com turma_curso_id NULL: total, ativas, inativas, ids (20)
    total_null  = SELECT count(*) FROM inscricoes WHERE turma_curso_id IS NULL
    ativas_null = SELECT count(*) ... AND ativo IS TRUE
    ids_null    = SELECT id ... ORDER BY id LIMIT 20
    # (ii) pares ativos duplicados por (aluno_id, turma_curso_id): qtd + 20 chaves
    dup_rows    = SELECT aluno_id, turma_curso_id, count(*) n
                  FROM inscricoes WHERE ativo IS TRUE AND turma_curso_id IS NOT NULL
                  GROUP BY aluno_id, turma_curso_id HAVING count(*) > 1
    if total_null or dup_rows:
        # monta (i) e/ou (ii) em `partes` e:
        raise RuntimeError("Não é possível aplicar c3d4e5f6a7b8 (inscrição exige oferta): "
                           + " | ".join(partes) + ". Vincule ... rode scripts/preparar_deploy_onda4.py ...")
    with op.batch_alter_table("inscricoes") as batch_op:   # inalterado
        batch_op.alter_column("turma_curso_id", ..., nullable=False)
        batch_op.create_index("uix_inscricao_ativa_aluno_oferta", ..., unique=True,
                              postgresql_where=..., sqlite_where=...)
```

`revision`/`down_revision`/`downgrade()` **preservados**; o índice mantém os `*_where` por
dialeto (guarda SQLite intacta).

## 3. Diff — `d4e5f6a7b8c9` (Passo 2)

```python
def upgrade():
    conn = op.get_bind()
    # (a) PRESERVA o programa quando não há oferta ativa: COALESCE(subconsulta, turma.programa)
    UPDATE turma
    SET programa = COALESCE(
        (SELECT tc.programa FROM turma_curso tc
          WHERE tc.turma_id = turma.id AND tc.ativo IS TRUE AND tc.programa IS NOT NULL
          ORDER BY tc.principal DESC, tc.id ASC LIMIT 1),
        turma.programa)                              -- << nunca zera
    # (b) antes do SET NOT NULL: recusa oferta com programa NULL, SEM atribuir padrão
    null_total = SELECT count(*) FROM turma_curso WHERE programa IS NULL
    if null_total:
        ids_null = SELECT id ... LIMIT 20
        raise RuntimeError("Não é possível aplicar d4e5f6a7b8c9 (programa obrigatório na oferta): "
                           f"{null_total} oferta(s) ... Ids das primeiras 20: ... Defina ... "
                           "rode scripts/preparar_deploy_onda4.py ...; nenhum programa padrão foi atribuído.")
    with op.batch_alter_table("turma_curso") as batch_op:   # inalterado
        batch_op.alter_column("programa", ..., nullable=False)
```

A subconsulta ganhou `AND tc.programa IS NOT NULL` e o `COALESCE(..., turma.programa)`; a
ordem `principal DESC, id ASC` foi mantida. `downgrade()` e `revision` **preservados**.

---

## 4. Passo 5 — Ensaios em banco SCRATCH (`pautaon_ensaio`)

Ambiente: PostgreSQL 18.6; dump `instance/backups/antes_fase4_20261022_211317.sql`
(`alembic_version=8c4e1f9a7d32`). Cada cenário **recria** o banco do dump (nunca o `pautaon`).
Subida base até `a1b2c3d4e5f6` antes de cada injeção.

> Nota de método: `flask db upgrade` aborta corretamente no bloqueio (exit 1, DDL transacional,
> `alembic_version` permanece), mas **não ecoou o texto do traceback** nos streams capturados neste
> ambiente (ver §6/pendência). Para anexar a **mensagem exata produzida pelo código**, reproduzi o
> `upgrade()` real **in-process** sobre uma conexão com `rollback` garantido (proxy `Operations` do
> Alembic 1.18.4 apontando para o mesmo `pautaon_ensaio` injetado) — sem alterar dado algum. As
> mensagens abaixo são a string que o `raise` gera.

### Ensaio A — limpo (dump restaurado, sem injeção)

`flask db upgrade` até o head:

```
Running upgrade 8c4e1f9a7d32 -> e7f3a1b9c4d5
Running upgrade e7f3a1b9c4d5 -> d2e3f4a5b6c7
Running upgrade d2e3f4a5b6c7 -> a1b2c3d4e5f6
Running upgrade a1b2c3d4e5f6 -> c3d4e5f6a7b8
Running upgrade c3d4e5f6a7b8 -> d4e5f6a7b8c9      exit=0
```

Resultado: ✅ **passa até o head**. Checagens retornaram zero; `SET NOT NULL` e índice aplicados.
Estado verificado: `rev=d4e5f6a7b8c9`, `inscricoes.turma_curso_id` NO, `turma_curso.programa` NO,
`uix_inscricao_ativa_aluno_oferta ... WHERE (ativo IS TRUE)` presente.

### Ensaio B — NULL + duplicata + oferta sem programa (espera c3d4 falhar com UMA mensagem listando NULL e duplicata)

Injeção: `UPDATE inscricoes SET turma_curso_id=NULL WHERE id IN (9,10)` (id 9 ativa, id 10
inativada por `ativo=false`); duplicata ativa via `INSERT ... SELECT ... WHERE id=3`
(aluno 1372 / oferta 2); `UPDATE turma_curso SET programa=NULL WHERE id=1`.

`flask db upgrade`: `Running upgrade a1b2c3d4e5f6 -> c3d4e5f6a7b8` → **exit 1**;
`alembic_version` permanece **`a1b2c3d4e5f6`** (nada pela metade). Mensagem exata:

```
Não é possível aplicar c3d4e5f6a7b8 (inscrição exige oferta): (i) 2 inscrição(ões) com
turma_curso_id NULL (1 ativa(s) / 1 inativa(s)); ids das primeiras 20: 9, 10 | (ii) 1 par(es)
(aluno_id, turma_curso_id) com inscrições ativas duplicadas; primeiras 20 chaves:
(aluno_id=1372, turma_curso_id=2) x2. Vincule as inscrições às suas ofertas e deduplique as
ativas (nenhum dado foi alterado por esta migration) e rode scripts/preparar_deploy_onda4.py
para revalidar.
```

✅ **Ambos** os problemas (i) e (ii) na **mesma** mensagem, antes do `SET NOT NULL`/índice. A
`programa NULL` (id 1) não chega a ser avaliada porque c3d4 falha primeiro — exatamente o papel
de d4e5 no cenário D.

### Ensaio C — só duplicata (sem NULL)

Injeção: apenas `INSERT ... SELECT ... WHERE id=3`. `flask db upgrade` → c3d4 **exit 1**, rev
permanece `a1b2c3d4e5f6`. Mensagem exata (só o bloco (ii); o (i) corretamente omitido):

```
Não é possível aplicar c3d4e5f6a7b8 (inscrição exige oferta): (ii) 1 par(es)
(aluno_id, turma_curso_id) com inscrições ativas duplicadas; primeiras 20 chaves:
(aluno_id=1372, turma_curso_id=2) x2. Vincule as inscrições às suas ofertas e deduplique as
ativas (nenhum dado foi alterado por esta migration) e rode scripts/preparar_deploy_onda4.py
para revalidar.
```

✅ Contraste com B: sem NULL, a parte (i) não aparece; a duplicata é sempre reportada (P-2 resolvido).

### Ensaio D — só `programa` NULL (c3d4 passa; d4e5 falha com mensagem clara)

Injeção: apenas `UPDATE turma_curso SET programa=NULL WHERE id=1`. `flask db upgrade`:

```
Running upgrade a1b2c3d4e5f6 -> c3d4e5f6a7b8      (✅ passa: sem NULL, sem duplicata)
Running upgrade c3d4e5f6a7b8 -> d4e5f6a7b8c9      (❌ exit 1)
```

`alembic_version` permanece `a1b2c3d4e5f6`. Mensagem exata de d4e5:

```
Não é possível aplicar d4e5f6a7b8c9 (programa obrigatório na oferta): 1 oferta(s) ainda com
turma_curso.programa NULL. Ids das primeiras 20: 1. Defina o programa dessas ofertas/turmas e
rode scripts/preparar_deploy_onda4.py para revalidar; nenhum programa padrão foi atribuído.
```

✅ Quantidade + ids das primeiras 20 + instrução; **nenhum programa padrão atribuído**.

### Ensaio E — turma sem oferta ativa (upgrade passa e `turma.programa` é PRESERVADO)

Injeção: `UPDATE turma_curso SET ativo=false WHERE id=3` → turma 3 ("4 - Canoagem") fica com
`programa='Esporte'` e **nenhuma oferta ativa**. Sem NULL e sem duplicata → upgrade **conclui**
até `d4e5f6a7b8c9` (exit 0). Programa da turma 3:

```
ANTES do upgrade (em a1b2c3d4e5f6):  turma3=Esporte
DEPOIS do upgrade (em d4e5f6a7b8c9):  turma3=Esporte     ← PRESERVADO
```

✅ **Defeito P-1 corrigido.** Antes, o `UPDATE` sem `COALESCE` zerava `turma.programa` da turma 3
(provado em P1 §3 ensaio E: `Esporte` → `(NULL)`); agora o `COALESCE(..., turma.programa)` mantém
o valor. Checagem (b) de d4e5 retorna 0 (nenhuma oferta com programa NULL), então o `NOT NULL` é
aplicado com sucesso.

### Estado final do scratch

`pautaon_ensaio` **recriado do dump e levado ao head `d4e5f6a7b8c9`, limpo** (sem dados
sintéticos): `inscricoes.turma_curso_id` NO, `turma_curso.programa` NO, índice parcial
`uix_inscricao_ativa_aluno_oferta` presente. O banco `pautaon` nunca foi aberto. Descartável com
`DROP DATABASE pautaon_ensaio`.

---

## 5. Suíte completa

`python -m pytest -q` (SQLite `:memory:`, `db.create_all()` — não executa Alembic):

```
257 passed, 51 warnings in 121.64s
```

✅ Nenhuma regressão: as migrations não são exercitadas pela suíte; o resultado é idêntico ao de
B4 (257 passed).

---

## 6. Decisões

* **Nenhuma revisão nova**: `revision`/`down_revision` das duas migrations preservados; apenas o
  corpo de `upgrade()` foi endurecido. `downgrade()` intocado.
* **Guardas SQLite preservados**: `op.batch_alter_table(...)` mantido nas duas; o índice mantém
  `postgresql_where`/`sqlite_where`.
* **Checagem (b) de d4e5 só após (a)**: o `UPDATE` de preservação roda primeiro; se ainda restar
  oferta com programa NULL, o `RuntimeError` aborta. Ordem garante que a preservação por COALESCE
  não mascare um NULL real de oferta.
* **Sem atribuição de programa padrão** (recusa explícita), fiel a P1 §7/P-5 (decisão de negócio).
* **c3d4 é estritamente leitura**: nenhuma `UPDATE/DELETE` — a deduplicação continua sendo limpeza
  de negócio proposta em P1 §5, agora comunicada por mensagem clara em vez de `UniqueViolation` crua.
* **Captura da mensagem in-process** (rollback garantido) em vez de depender do eco da CLI, cuja
  visibilidade do traceback apresentou problema neste ambiente (ver pendência).

## 7. Pendências

| # | Pendência | Tipo |
|---|---|---|
| B5-P1 | `flask db upgrade` aborta exit 1 no bloqueio, mas **não imprimiu o traceback/mensagem do `RuntimeError`** nos streams capturados (console, `2>` a arquivo e `Start-Process -RedirectStandardError`) neste Windows/venv. Confirmar, no deploy real, que o operador **vê** a mensagem; se não, considerar `logging.error(...)` da mensagem dentro de `upgrade()` antes do `raise` (fora do escopo desta etapa — exigiria mexer além do já autorizado). | Observabilidade/deploy |
| B5-P2 | Repetir A–E com o **dump autêntico de produção** (o disponível estava limpo; contagens reais de NULL/duplicata/`programa` NULL só existem lá). | Insumo ausente |
| B5-P3 | Decisão de negócio de dedup/programa (P1 P-4/P-5) permanece pendente — as novas mensagens **apontam** para `scripts/preparar_deploy_onda4.py`, que não foi alterado aqui. | Negócio |

## 8. Arquivos alterados

* `migrations/versions/c3d4e5f6a7b8_inscricao_exige_oferta.py` — checagens (i)+(ii) juntas em um
  `RuntimeError`, antes do `batch_alter_table`.
* `migrations/versions/d4e5f6a7b8c9_programa_obrigatorio_na_oferta.py` — `UPDATE` com `COALESCE`
  (preserva programa) + checagem (b) em `RuntimeError` antes do `SET NOT NULL`.
* `docs/B5_relatorio.md` — este relatório.

Nenhum commit foi feito. Scripts scratch temporários usados nos ensaios foram removidos de
`instance/`.
