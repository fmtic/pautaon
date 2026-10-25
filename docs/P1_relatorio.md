# ETAPA P1 — Ensaio de upgrade da Onda 4 sobre dump (banco SCRATCH)

Data: 25/10/2026 · Ramo: `Onda4` · Banco de origem **não tocado** · Nenhum commit · Nenhuma migration alterada.

---

## 0. Ressalva obrigatória: o dump pedido não existe

O enunciado pede `backup_20261020_204018.sql`. Ele **não existe** no repositório nem em disco: foi
procurado em `instance/backups/`, em todo `C:\Users\FMtic\Documents\Nextcloud` e em
Downloads/Desktop (qualquer `backup_*.sql`, `*.dump`, `*.gz`) — zero resultados.

O único dump disponível é:

| Arquivo | Data | Conteúdo |
|---|---|---|
| `instance/backups/antes_fase4_20261022_211317.sql` | 22/10/2026 21:13 | pg_dump 18.6 / PostgreSQL 18.6, `alembic_version = 8c4e1f9a7d32` |

Como a instrução autoriza "use o dump de produção mais recente, se houver", foi esse o arquivo
restaurado. Consequências que limitam o valor do ensaio:

* **Volume**: `unidade=2`, `aluno=1154`, `turma=3`, `turma_curso=3`, `inscricoes=10`,
  `frequencia=0`, `registro_aula=0`. É um banco de trabalho local, não um retrato de produção.
* **Estado dos dados**: as 10 inscrições já têm `turma_curso_id` e as 3 turmas já têm
  `programa='Esporte'` com oferta ativa. **Não há NULL nem duplicata** — portanto este dump,
  sozinho, não exercita os bloqueios que a etapa teme.
* Para cobrir isso foram criados **ensaios sintéticos (B, C, D, E)**: o mesmo dump, restaurado de
  novo, com injeção deliberada das condições legadas (seção 4). Os dados sintéticos viveram
  **apenas** em `pautaon_ensaio`.

**Recomendação (§7):** antes do deploy real, repetir este procedimento com o dump autêntico de
produção — os bloqueios prováveis (N inscrições `turma_curso_id IS NULL`, M duplicatas) só podem
ser contados lá.

---

## 1. Passo 1 — Banco scratch e restauração

Comandos (PowerShell, na raiz; `PGPASSWORD` omitido aqui):

```powershell
psql -U postgres -h localhost -d postgres -c "DROP DATABASE IF EXISTS pautaon_ensaio WITH (FORCE);" -c "CREATE DATABASE pautaon_ensaio OWNER postgres ENCODING 'UTF8' TEMPLATE template0;"
psql -U postgres -h localhost -d pautaon_ensaio -v ON_ERROR_STOP=1 -f "instance\backups\antes_fase4_20261022_211317.sql"
psql -U postgres -h localhost -d pautaon_ensaio -tA -c "SELECT version_num FROM alembic_version;"
```

* Restauração sem erros (`ON_ERROR_STOP=1`, exit 0; `\restrict` do pg_dump 18.6 aceito pelo psql 18.6).
* **`alembic_version` resultante: `8c4e1f9a7d32`** (Onda 4 fase 1 — fix `turma_curso.updated_by_id`).
* Caminho de upgrade a partir daí (5 revisões, linear, sem heads múltiplos):

| # | Revisão | Título | Efeito |
|---|---|---|---|
| 1 | `e7f3a1b9c4d5` | Onda 4 Fase 4: `turma_curso_id` em `frequencia`/`registro_aula` | drop do UNIQUE legado, 2 colunas + FKs, índices parciais `uix_freq_legado`/`uix_freq_oferta`, backfill restrito a turma com exatamente 1 oferta |
| 2 | `d2e3f4a5b6c7` | CentroCusto: catálogo por unidade | cria `centro_custo` + backfill dos strings `centro_custo` de `periodo_letivo`/`turma`/`turma_curso` |
| 3 | `a1b2c3d4e5f6` | Adiciona coluna `programa` em `turma_curso` | `add_column` NULL-able + `UPDATE ... SET programa = (SELECT turma.programa ...)` |
| 4 | `c3d4e5f6a7b8` | Inscrição exige oferta | `ALTER ... SET NOT NULL` em `inscricoes.turma_curso_id` + `CREATE UNIQUE INDEX uix_inscricao_ativa_aluno_oferta ... WHERE ativo IS TRUE` |
| 5 | `d4e5f6a7b8c9` | Programa obrigatório na oferta | `UPDATE turma SET programa = (subconsulta da oferta ativa)` **sem cláusula WHERE** + `ALTER ... SET NOT NULL` em `turma_curso.programa` |

O banco `pautaon` **não foi conectado em nenhum momento** — todas as ligações foram a
`postgres` (para criar/derrubar) e a `pautaon_ensaio`.

---

## 2. Passo 2 — Diagnóstico SOMENTE LEITURA do estado restaurado

Ferramenta criada no passo 4 (`scripts/preparar_deploy_onda4.py`, 0 writes, exit 0/1) e executada
contra o scratch parado em `8c4e1f9a7d32`:

```
=== preparar_deploy_onda4 — SOMENTE LEITURA ===
alvo: postgresql+psycopg://localhost:5432/pautaon_ensaio
OK: alembic_version atual: 8c4e1f9a7d32
OK: volume: turma=3 | turma_curso=3 | inscricoes=10 | frequencia=0 | registro_aula=0

--- A. inscrições sem oferta (turma_curso_id NULL) ---
OK: nenhuma inscrição com turma_curso_id NULL                       → (a) = 0 linhas

--- D. duplicatas ativas por (aluno_id, turma_curso_id) ---
OK: nenhuma inscrição ativa duplicada por oferta                    → (d) = 0 linhas

--- B. programa da turma × ofertas ativas ---
OK: nenhuma turma com programa e sem oferta ativa                   → (b) = 0 linhas
OK: toda turma com oferta tem programa (backfill não produziria NULL)

--- C. turmas com curso e sem oferta ---
OK: nenhuma turma com curso sem oferta                              → (c) = 0 linhas

--- E. inscrição × turma da oferta ---
OK: toda inscrição aponta para oferta da própria turma

OK: nenhum bloqueio para c3d4e5f6a7b8 e d4e5f6a7b8c9 neste banco.   EXITO=0
```

Leitura honesta: **nada a limpar neste dump**. Isso não significa que o upgrade em produção seja
seguro — significa que o dump usado não contém o estado legado que a etapa quer ensaiar. As
seções 3 e 4 criam esse estado e mostram o comportamento real de cada revisão.

---

## 3. Passo 3 — `flask db upgrade` revisão por revisão

Alvo definido por variável de ambiente (não se editou `.env`):

```powershell
$env:DATABASE_URL='postgresql+psycopg://postgres:***@localhost:5432/pautaon_ensaio'
flask db current      # → 8c4e1f9a7d32  (confirma que é o scratch, não o pautaon)
foreach ($r in 'e7f3a1b9c4d5','d2e3f4a5b6c7','a1b2c3d4e5f6','c3d4e5f6a7b8','d4e5f6a7b8c9') { flask db upgrade $r }
```

### Ensaio A — dump restaurado, sem alterações (limpo)

| Revisão | Resultado |
|---|---|
| `e7f3a1b9c4d5` | ✅ `Running upgrade 8c4e1f9a7d32 -> e7f3a1b9c4d5` |
| `d2e3f4a5b6c7` | ✅ `Running upgrade e7f3a1b9c4d5 -> d2e3f4a5b6c7` |
| `a1b2c3d4e5f6` | ✅ `Running upgrade d2e3f4a5b6c7 -> a1b2c3d4e5f6` |
| `c3d4e5f6a7b8` | ✅ `Running upgrade a1b2c3d4e5f6 -> c3d4e5f6a7b8` |
| `d4e5f6a7b8c9` | ✅ `Running upgrade c3d4e5f6a7b8 -> d4e5f6a7b8c9` |

Estado final verificado:

```
rev = d4e5f6a7b8c9
inscricoes.turma_curso_id  is_nullable = NO
turma_curso.programa       is_nullable = NO
CREATE UNIQUE INDEX uix_inscricao_ativa_aluno_oferta ON public.inscricoes USING btree (aluno_id, turma_curso_id) WHERE (ativo IS TRUE)
centro_custo = 3 linhas | frequencia.turma_curso_id + registro_aula.turma_curso_id presentes
uix_freq_legado / uix_freq_oferta únicos | constraint legada uix_frequencia_aluno_turma_data removida
scripts/verificar_onda4_fase4.py → "OK: estrutura e integridade da Fase 4 íntegros." (exit 0)
```

Mecânica validada: as 5 revisões encadeiam sem conflitos, sem múltiplos heads, e são idempotentes
o suficiente para subir do estado `8c4e1f9a7d32` até o head.

### Ensaio B — estado legado completo (injeção no scratch)

Injetado após restauração limpa: 5 inscrições com `turma_curso_id NULL` em 3 turmas distintas
(1 com exatamente 1 oferta, 1 com 2 ofertas, 1 sem oferta nenhuma — esta com 1 ativa e 1 inativa),
1 par ativo duplicado `(1341, oferta 3)`, oferta da turma 3 inativada (turma ficou com programa e
sem oferta ativa) e `turma.programa = NULL` na turma 1.

Diagnóstico (`preparar_deploy_onda4.py`, exit 1):

```
--- A --- FALHA: 5 inscrição(ões) com turma_curso_id NULL (4 ativas / 1 inativas)
        OK: turmas com inscrições NULL: 3 — vínculo automático possível em 1 (exatamente 1 oferta),
            decisão manual em 1 (2+ ofertas), sem destino em 1 (0 ofertas)
            2 | 1 - Natação          | 2 NULLativas | ofertas_ativas=2 | ofertas_total=2 | MANUAL
            4 | ENSAIO-B sem oferta  | 1 ativa/1 inativa | ofertas_total=0              | SEM-DESTINO
            3 | 4 - Canoagem         | 1 NULLativa | ofertas_ativas=0 | ofertas_total=1 | AUTO
--- D --- FALHA: 1 par(es) aluno/oferta com inscrições ativas duplicadas (2 linhas)
--- B --- FALHA: 2 turma(s) com programa preenchido e SEM oferta ativa
            3 | 4 - Canoagem        | programa=Esporte | ofertas_ativas=0 | ofertas_total=1
            4 | ENSAIO-B sem oferta | programa=Esporte | ofertas_ativas=0 | ofertas_total=0
        FALHA: 1 turma(s) com oferta(s) e programa NULL (turma 1) → ofertas herdarão NULL
--- C --- AVISO: 1 turma(s) com curso e sem nenhuma oferta (turma 4)
4 checagem(ns) com FALHA — há limpeza obrigatória antes do upgrade.                     EXITO=1
```

Upgrade: as 3 primeiras revisões passam; **`c3d4e5f6a7b8` falha** com a mensagem exata:

```
psycopg.errors.NotNullViolation: a coluna "turma_curso_id" da relação "inscricoes" contém valores nulos
[SQL: ALTER TABLE inscricoes ALTER COLUMN turma_curso_id SET NOT NULL]
sqlalchemy.exc.IntegrityError: (psycopg.errors.NotNullViolation) ...
```

Ponto importante medido: **nada fica pela metade.** Alembic/PostgreSQL usam DDL transacional
("Will assume transactional DDL"), então a revisão falha inteira e `alembic_version` permanece
`a1b2c3d4e5f6`. As revisões já aplicadas (`e7f`, `d2e`, `a1b2`) ficam aplicadas — ou seja, o
deploy é retomável depois da limpeza, sem precisar de `downgrade`.

Com o banco parado em `a1b2c3d4e5f6`, o mesmo script é relido e passa a descrever o dano real
(em vez de projetá-lo):

```
OK: alembic_version atual: a1b2c3d4e5f6
FALHA: 1 oferta(s) com turma_curso.programa NULL — o NOT NULL de d4e5f6a7b8c9 falha
```

### Ensaio C — só duplicata ativa (sem NULL)

```
psycopg.errors.UniqueViolation: não foi possível criar o índice único "uix_inscricao_ativa_aluno_oferta"
DETAIL:  Chave (aluno_id, turma_curso_id)=(1341, 3) está duplicada.
[SQL: CREATE UNIQUE INDEX uix_inscricao_ativa_aluno_oferta ON inscricoes (aluno_id, turma_curso_id) WHERE ativo IS TRUE]
```

Leitura: dentro de `c3d4e5f6a7b8` o `SET NOT NULL` vem **antes** do índice. Uma base com NULL *e*
duplicatas só revela o segundo problema depois que o primeiro for corrigido — logo o diagnóstico
precisa listar os dois de uma vez (é o que o script faz).

### Ensaio D — só ofertas destinadas a ficar com `programa` NULL

`c3d4e5f6a7b8` ✅ passa; **`d4e5f6a7b8c9` falha**:

```
psycopg.errors.NotNullViolation: a coluna "programa" da relação "turma_curso" contém valores nulos
[SQL: ALTER TABLE turma_curso ALTER COLUMN programa SET NOT NULL]
```

Causa: `a1b2c3d4e5f6` preenche `turma_curso.programa` por subconsulta em `turma.programa`; turma
sem programa → oferta sem programa → o `NOT NULL` da revisão seguinte explode.

### Ensaio E — o caso que **passa e destrói dado** (perda silenciosa de `turma.programa`)

Injeção mínima: `UPDATE turma_curso SET ativo=false WHERE id=3;` — turma 3 fica com
`programa='Esporte'` e nenhuma oferta ativa. Sem NULL e sem duplicata, o upgrade **conclui**:

```
INFO  Running upgrade c3d4e5f6a7b8 -> d4e5f6a7b8c9, Require every course offer to have a program.
CODE=0        (head d4e5f6a7b8c9)

 id | nome          | turma_programa | oferta_ativa_programa
  1 | Natação 8h…   | Esporte        | Esporte
  2 | 1 - Natação   | Esporte        | Esporte
  3 | 4 - Canoagem  | (NULL)         | (sem oferta ativa)      ← ERA 'Esporte'
```

O `UPDATE` de `d4e5f6a7b8c9` não tem `WHERE` nem `COALESCE`: para turma sem oferta ativa, a
subconsulta retorna NULL e **o programa que existia é apagado**, sem erro e sem aviso. É o único
dos quatro riscos que o `flask db upgrade` não recusa — por isso a preservação da seção 5 é
obrigatória *antes* da migration (depois, o valor original já era).

Diagnóstico antes (exit 1) e depois (exit 0, com AVISO) do mesmo caso:

```
B: FALHA: 1 turma(s) com programa preenchido e SEM oferta ativa — o UPDATE de d4e5f6a7b8c9 zera turma.programa
   3 | 4 - Canoagem | True | Esporte | ofertas_ativas=0 | ofertas_total=1

B: OK: nenhuma turma com programa e sem oferta ativa        ← a checagem "esvazia" porque o dano já ocorreu
   AVISO: 1 turma(s) já SEM programa — se o upgrade já rodou, é o dano da d4e5f6a7b8c9
```

---

## 4. Passo 4 — script `scripts/preparar_deploy_onda4.py`

* **Somente leitura**: nenhum `INSERT/UPDATE/DELETE/ALTER/DROP`; usa `create_app()` e `engine.connect()`
  para `SELECT`/`inspect`, como `scripts/verificar_onda4_fase4.py` (mesmo padrão de `OK/FALHA/AVISO`
  e `exit 0/1`).
* **Banco por argumento** (o `.env` não é tocado):
  * `python scripts/preparar_deploy_onda4.py` → banco configurado no `.env` (produção/dev);
  * `--db pautaon_ensaio` → troca só o nome do banco da `DATABASE_URL` base;
  * `--dsn "postgresql+psycopg://user:senha@host:5432/db"` → URL completa;
  * `--sem-lista` → só totais (para rodar em produção sem despejar linhas no console).
* Checa, na ordem do enunciado: (a) NULLs por turma com ofertas ativas/total e classificação
  AUTO / MANUAL / SEM-DESTINO; (b) programa da turma × oferta ativa, com a projeção pós-`a1b2c3d4e5f6`
  e a leitura direta quando a coluna já existe; (c) turmas com curso e sem oferta; (d) duplicatas
  ativas por `(aluno_id, turma_curso_id)`; e (e) inscrição apontando para oferta de outra turma
  (extra — a migration não corrige isso, mas quebra os leitores).
* Também imprime `alembic_version` atual e volumes, para o resultado ser autoexplicativo no
  histórico do deploy.
* `ruff check` limpo. **Funciona em qualquer ponto da escada**: com `turma_curso.programa` ainda
  inexistente, o item B projeta o que `a1b2c3d4e5f6` vai produzir; existente, conta o NULL real.

---

## 5. PROPOSTA de SQL de limpeza pré-migration — **NÃO EXECUTADA**

Nada aqui foi executado em banco algum (nem no scratch), conforme a ordem do enunciado. A ordem é:
dump novo → `4` (backup) → `5/6/7` (limpezas seguras) → `8` (listas para decisão) → script exit 0 →
`flask db upgrade` → script de novo + `verificar_onda4_fase4.py`. Tudo dentro de transação única por
etapa, com `ROLLBACK` à mão.

```sql
-- =====================================================================
-- 0) Pré-requisitos: janela SEM escrita da aplicação (as ALTER abaixo
--    pedem ACCESS EXCLUSIVE em inscricoes/turma_curso), dump recente e
--    leitura do diagnóstico. Nunca rodar isto sem o passo 4.
-- =====================================================================
BEGIN;

-- =====================================================================
-- 4) PRESERVAR turma.programa ANTES da d4e5f6a7b8c9
--    (a revisão sobrescreve a coluna por subconsulta sem WHERE: turma
--     sem oferta ativa acorda com programa NULL)
-- =====================================================================
CREATE TABLE turma_programa_backup AS
SELECT id, nome, programa
FROM turma;                              -- tabela pequena; cópia integral, sem filtro

-- =====================================================================
-- 5) NULL em turma com EXATAMENTE 1 oferta (ativa ou única existente)
--    → vínculo seguro. O `NOT EXISTS` evita criar duplicata ativa na
--      mesma oferta (que é justamente o que o índice novo proíbe).
-- =====================================================================
UPDATE inscricoes i
SET turma_curso_id = tc.id
FROM turma_curso tc
WHERE i.turma_curso_id IS NULL
  AND tc.turma_id = i.turma_id
  AND (SELECT count(*) FROM turma_curso u WHERE u.turma_id = i.turma_id) = 1
  AND NOT EXISTS (
        SELECT 1 FROM inscricoes x
        WHERE x.aluno_id = i.aluno_id
          AND x.turma_curso_id = tc.id
          AND x.ativo IS TRUE
      );
-- Conferir antes, com o mesmo WHERE transformado em SELECT.

-- =====================================================================
-- 6) Variante: turma com 2+ ofertas, mas EXATAMENTE 1 ATIVA
--    → só liga inscrições ATIVAS (o destino é inequívoco). Inativas ficam
--      para a lista do item 8, porque "em qual oferta ele estava matriculado"
--      não é deduzível sem decisão de negócio.
-- =====================================================================
UPDATE inscricoes i
SET turma_curso_id = act.id
FROM (
    SELECT tc.turma_id, min(tc.id) AS id
    FROM turma_curso tc
    WHERE tc.ativo IS TRUE
    GROUP BY tc.turma_id
    HAVING count(*) = 1
) act
WHERE i.turma_curso_id IS NULL
  AND i.ativo IS TRUE
  AND act.turma_id = i.turma_id
  AND NOT EXISTS (
        SELECT 1 FROM inscricoes x
        WHERE x.aluno_id = i.aluno_id
          AND x.turma_curso_id = act.id
          AND x.ativo IS TRUE
      );

-- =====================================================================
-- 7) Ofertas sem programa (bloqueio do d4e5f6a7b8c9)
--    7a. ANTES de a1b2c3d4e5f6: preencher turma.programa a partir da
--        oferta que vai gerar a coluna é impossível (a coluna não existe);
--        a fonte é a decisão de negócio abaixo, aplicada na turma.
-- =====================================================================
-- LISTAR (não atualizar): turmas com oferta e programa NULL
SELECT t.id AS turma_id, t.nome, t.curso_id, c.nome AS curso,
       (SELECT count(*) FROM turma_curso u WHERE u.turma_id = t.id) AS ofertas
FROM turma t
JOIN curso c ON c.id = t.curso_id
WHERE t.programa IS NULL
  AND EXISTS (SELECT 1 FROM turma_curso u WHERE u.turma_id = t.id);
-- → decidir o programa por turma (ex.: mapa curso→programa) e UPDATE manual.

-- 7b. DEPOIS de a1b2c3d4e5f6 e ainda com `c3d4e5f6a7b8`/`d4e5f6a7b8c9`
--     pendentes: a coluna existe, então espelhar da turma é mecânico.
UPDATE turma_curso tc
SET programa = t.programa
FROM turma t
WHERE t.id = tc.turma_id
  AND tc.programa IS NULL
  AND t.programa IS NOT NULL;

-- =====================================================================
-- 8) LISTAS PARA DECISÃO MANUAL (somente SELECT)
-- =====================================================================
-- 8a. NULL em turma com 2+ ofertas ativas (qual oferta?)
SELECT i.turma_id, t.nome AS turma, count(*) AS inscricoes_null,
       (SELECT count(*) FROM turma_curso u WHERE u.turma_id = i.turma_id AND u.ativo) AS ofertas_ativas
FROM inscricoes i JOIN turma t ON t.id = i.turma_id
WHERE i.turma_curso_id IS NULL
GROUP BY i.turma_id, t.nome
HAVING (SELECT count(*) FROM turma_curso u WHERE u.turma_id = i.turma_id) >= 2
ORDER BY inscricoes_null DESC;

-- 8b. NULL em turma SEM oferta (criar a oferta primeiro, ou desativar a inscrição)
SELECT i.id AS inscricao_id, i.aluno_id, i.turma_id, t.nome AS turma, i.ativo,
       i.data_inicio, i.data_desativacao, i.motivo_desativacao
FROM inscricoes i JOIN turma t ON t.id = i.turma_id
WHERE i.turma_curso_id IS NULL
  AND NOT EXISTS (SELECT 1 FROM turma_curso u WHERE u.turma_id = i.turma_id)
ORDER BY i.ativo DESC, i.turma_id, i.id;

-- 8c. Inativas sem destino possível (turma tem ofertas, nenhuma delas plausível
--     para aquele período — revisar caso a caso)
SELECT i.id, i.aluno_id, i.turma_id, t.nome AS turma, i.data_inicio, i.data_desativacao
FROM inscricoes i JOIN turma t ON t.id = i.turma_id
WHERE i.turma_curso_id IS NULL AND i.ativo IS FALSE
  AND EXISTS (SELECT 1 FROM turma_curso u WHERE u.turma_id = i.turma_id)
ORDER BY i.turma_id, i.id;

-- 8d. Duplicatas ativas por (aluno, oferta) — o índice recusa o upgrade
SELECT aluno_id, turma_curso_id, count(*) AS n,
       array_agg(id ORDER BY id) AS ids,
       max(id) AS sugerido_manter
FROM inscricoes
WHERE ativo IS TRUE AND turma_curso_id IS NOT NULL
GROUP BY aluno_id, turma_curso_id
HAVING count(*) > 1
ORDER BY n DESC, aluno_id;
-- Resolução é decisão de negócio. A menos destrutiva (e a que o ensaio C
-- validou como necessária) é desativar as sobras, NÃO apagá-las:
-- UPDATE inscricoes i SET ativo = FALSE, motivo_desativacao = 'MIGRACAO_ONDA4_DEDUP',
--        data_desativacao = now()
--   FROM (SELECT aluno_id, turma_curso_id, max(id) AS keep FROM inscricoes
--          WHERE ativo IS TRUE AND turma_curso_id IS NOT NULL
--          GROUP BY aluno_id, turma_curso_id HAVING count(*) > 1) k
--  WHERE i.ativo IS TRUE AND i.turma_curso_id = k.turma_curso_id
--    AND i.aluno_id = k.aluno_id AND i.id <> k.keep;

-- =====================================================================
-- 9) Conferência cruzada (a migration não corrige; se houver, corrigir
--    antes porque os leitores por turma e por oferta passam a divergir)
-- =====================================================================
SELECT i.id, i.aluno_id, i.turma_id AS turma_inscricao, tc.turma_id AS turma_da_oferta
FROM inscricoes i JOIN turma_curso tc ON tc.id = i.turma_curso_id
WHERE tc.turma_id <> i.turma_id;

COMMIT;  -- ou ROLLBACK; depois de reler o diagnóstico

-- =====================================================================
-- 10) PÓS-UPGRADE: devolver o que a d4e5f6a7b8c9 zerou
--     (rodar só se o item 4 foi feito antes da migration)
-- =====================================================================
SELECT b.id, b.nome, b.programa AS programa_antes, t.programa AS programa_depois
FROM turma t JOIN turma_programa_backup b ON b.id = t.id
WHERE b.programa IS NOT NULL
  AND t.programa IS DISTINCT FROM b.programa;

UPDATE turma t
SET programa = b.programa
FROM turma_programa_backup b
WHERE b.id = t.id
  AND t.programa IS NULL
  AND b.programa IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM turma_curso u WHERE u.turma_id = t.id AND u.ativo IS TRUE);
```

Notas de execução:

* Os itens `5` e `6` são **seguros por construção**: só atuam onde o destino é único, e nunca
  violam `uix_inscricao_ativa_aluno_oferta` por causa do `NOT EXISTS`.
* O item `8d` **não apaga** nada: desativa com `motivo_desativacao='MIGRACAO_ONDA4_DEDUP'`,
  conservando histórico. Se a escolha correta for o `min(id)` (a migration antiga de adoção de
  NULL usava esse critério), trocar `max` por `min` — é decisão registrada, não dedução.
* Locks: `ALTER TABLE ... SET NOT NULL` e `CREATE UNIQUE INDEX` (não-CONCURRENT) bloqueiam
  escrita nas tabelas durante a operação. Com `CREATE INDEX CONCURRENTLY` fora da migration o
  índice poderia ser construído sem bloqueio, mas exigiria ajustar a revisão — **fora do escopo
  desta etapa** (não alterei nenhuma migration).

---

## 6. Passo 5 — Saída do script no scratch (anexada)

Janela completa, com o scratch no estado final (dump restaurado + upgrade no head, **sem**
dados sintéticos):

```
# antes do upgrade (8c4e1f9a7d32)
$ python scripts/preparar_deploy_onda4.py --db pautaon_ensaio
... OK em A/B/C/D/E ... EXITO=0
$ flask db upgrade e7f3a1b9c4d5 … d4e5f6a7b8c9     # 5× "Running upgrade", CODE=0

# depois do upgrade (d4e5f6a7b8c9)
=== preparar_deploy_onda4 — SOMENTE LEITURA ===
alvo: postgresql+psycopg://localhost:5432/pautaon_ensaio
OK: alembic_version atual: d4e5f6a7b8c9
OK: volume: turma=3
OK: volume: turma_curso=3
OK: volume: inscricoes=10
OK: volume: frequencia=0
OK: volume: registro_aula=0

--- A. inscrições sem oferta (turma_curso_id NULL) ---
OK: nenhuma inscrição com turma_curso_id NULL

--- D. duplicatas ativas por (aluno_id, turma_curso_id) ---
OK: nenhuma inscrição ativa duplicada por oferta

--- B. programa da turma × ofertas ativas ---
OK: nenhuma turma com programa e sem oferta ativa (nada a preservar antes de d4e5f6a7b8c9)
OK: nenhuma oferta com programa NULL

--- C. turmas com curso e sem oferta ---
OK: nenhuma turma com curso sem oferta

--- E. inscrição × turma da oferta ---
OK: toda inscrição aponta para oferta da própria turma

OK: nenhum bloqueio para c3d4e5f6a7b8 e d4e5f6a7b8c9 neste banco.   EXITO=0
```

Os quatro ensaios sintéticos (B/C/D/E) estão transcritos na §3 com suas saídas e mensagens
exatas de banco.

---

## 7. Conclusões e recomendações para o deploy real

1. **A mecânica está correta.** Do estado `8c4e1f9a7d32` até `d4e5f6a7b8c9`, as 5 revisões
   encadeiam, sem head duplo, e uma falha devolve a revisão inteira (nada de schema pela metade).
2. **Dois bloqueios e um dano silencioso.** `c3d4e5f6a7b8` recusa NULL (`NotNullViolation`) e
   recusa duplicata ativa (`UniqueViolation` na criação do índice); `d4e5f6a7b8c9` recusa oferta
   com `programa` NULL; e, quando nada disso existe, a mesma `d4e5f6a7b8c9` **apaga
   `turma.programa`** das turmas sem oferta ativa — provado no ensaio E.
3. **O ensaio precisa ser repetido com o dump autêntico de produção.** O arquivo pedido
   (`backup_20261020_204018.sql`) não existia; o disponível já estava "limpo" e tem 3 turmas.
   Rodar `preparar_deploy_onda4.py --dsn <produção>` (read-only) dá os números que faltam.
4. **Preservar `turma.programa` é o único item que não pode ser feito depois** — o backup do
   item 4 da proposta deve acontecer antes do `flask db upgrade`.
5. **Ordem do deploy:** dump → script (exit 1 é esperado) → limpeza segura (itens 5/6/7b) →
   decisões manuais (8a–8d) → script (exit 0) → upgrade → script + `verificar_onda4_fase4.py`
   → restaurar programas zerados (item 10) → subir a aplicação.
6. **Nenhuma migration foi alterada** nesta etapa, deliberadamente: as correções estruturais
   (COALESCE no `UPDATE` da `d4e5f6a7b8c9`, índice CONCURRENTLY) mexem em arquivos que o enunciado
   protege. Ficam como pendência P-1/P-2 abaixo.

### Pendências

| # | Pendência | Onde | Tipo |
|---|---|---|---|
| P-1 | `UPDATE turma SET programa = (subconsulta oferta ativa)` sem `WHERE`/`COALESCE` destrói `turma.programa` de turma sem oferta ativa (ensaio E, prova executada) | `migrations/versions/d4e5f6a7b8c9_programa_obrigatorio_na_oferta.py:19-28` | Defeito de migration |
| P-2 | `c3d4e5f6a7b8` faz `SET NOT NULL` e `CREATE UNIQUE INDEX` não-concorrente na mesma transação: bloqueia escrita em `inscricoes` e revela só um problema por vez | `migrations/versions/c3d4e5f6a7b8_inscricao_exige_oferta.py:18-31` | Operação/deploy |
| P-3 | Repetir todo o ensaio com o dump real de produção (`backup_20261020_204018.sql` inexistente aqui) | `instance/backups/` | Insumo ausente |
| P-4 | Decidir o critério de dedup (manter `max(id)` vs. o mais recente vs. decisão por aluno) antes de executar o item 8d | proposta §5 | Negócio |
| P-5 | Decidir programa padrão para turmas com oferta e `programa` NULL (item 7a) — não há fonte automática confiável | proposta §5 | Negócio |

### Decisões tomadas nesta etapa

* Usar o dump disponível e declarar a substituição, em vez de parar por falta de arquivo.
* Injetar o estado legado **no scratch** (B/C/D/E) para obter as mensagens reais de banco — o
  enunciado pede exatamente "mensagem exata do banco", e o dump limpo não as produziria.
* **Não executar** nenhum SQL da seção 5, nem no scratch: é proposta, como ordenado.
* `DATABASE_URL` só por variável de ambiente do processo (`.env` intocado; `load_dotenv` não
  sobrepõe o ambiente, o que foi verificado empiricamente com `flask db current`).
* Criar apenas os dois arquivos autorizados: `scripts/preparar_deploy_onda4.py` e este relatório.

### Estado final do scratch

`pautaon_ensaio` está **restaurado do dump e com o upgrade no head `d4e5f6a7b8c9`**, sem os dados
sintéticos dos ensaios B–E (foi recriado de novo para a corrida limpa). Está descartável com
`DROP DATABASE pautaon_ensaio`. O banco `pautaon` não foi aberto.

Para reproduzir do zero:

```powershell
psql -U postgres -h localhost -d postgres -c "DROP DATABASE IF EXISTS pautaon_ensaio WITH (FORCE);" -c "CREATE DATABASE pautaon_ensaio OWNER postgres;"
psql -U postgres -h localhost -d pautaon_ensaio -v ON_ERROR_STOP=1 -f "instance\backups\antes_fase4_20261022_211317.sql"
$env:DATABASE_URL='postgresql+psycopg://postgres:***@localhost:5432/pautaon_ensaio'
python scripts/preparar_deploy_onda4.py --db pautaon_ensaio   # exit 0 = sem bloqueio
flask db upgrade
```
