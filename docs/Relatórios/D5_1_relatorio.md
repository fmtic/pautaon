# D5.1 — Esquema aditivo do conselho por oferta (relatório)

Etapa: **D5.1** da Onda 4 (ramo `Onda4`). Escopo: somente esquema (modelos +
migration + scripts de verificação + testes de schema + ensaio em banco SCRATCH).
Nenhuma rota, template, serviço, BI, relatório, MER ou backlog foi alterado.
Nenhum commit foi feito.

Fonte: `docs/D5_0_desenho.md` com as 3 correções decididas pelo responsável
(24/10/2026), registradas na seção "Decisões".

---

## 1. Passo 1 — Leituras e achados

### 1.1 Modelos

- `app/models/conselho.py` — `ConselhoClasse` (L128-215): TenantMixin
  (`unidade_id`) + AuditoriaMixin; `etapa` ENUM nativo `etapa_conselho_enum`
  (`INICIAL/PERCURSO/FINAL`); `situacao_final` VARCHAR(30) com CHECK
  (`ck_conselho_situacao_final`: Aprovado, Reprovado por Falta, Desistente,
  Evadido, Participação, Concluído); `concluido` bool NOT NULL default False;
  UNIQUE antiga `(turma_id, aluno_id, etapa)` em `__table_args__`.
  `ConselhoResposta` (L220-240): `aluno_id` **NOT NULL** no modelo — respostas
  "coletivas" com `aluno_id NULL` só podem existir como resquício legado de
  produção; o script quantifica (nenhuma no local).
- `app/models/academico.py` — `Turma.conselho_concluido` (bool NOT NULL) e
  `Turma.avaliacao_inicial/percurso/final` (Text nullable) — pareceres coletivos
  legados por turma; `TurmaCurso` (L264+): UNIQUE `(turma_id, curso_id)`,
  `programa` NOT NULL (d4e5), `principal`, SoftDelete+Tenant+Auditoria.

### 1.2 Migrations lidas

- `73f922fd358f` — criou a UNIQUE via `create_unique_constraint(...)` em
  `batch_alter_table`, nome `uix_conselho_turma_aluno_etapa`.
- `5a676f37b9a3` — padrão de **idempotência por inspeção**
  (`sa.inspect(op.get_bind())` → conjuntos de colunas/índices/constraints/FKs,
  cada DDL protegido por checagem de existência).
- `e7f3a1b9c4d5` — padrão dos **índices únicos parciais**
  (`uix_freq_legado`/`uix_freq_oferta` com `postgresql_where`/`sqlite_where`),
  do tratamento constraint×índice por dialecto e da **guarda de downgrade**
  (duplicatas bloqueiam a reversão).
- `c3d4e5f6a7b8` — padrão de checagem/pré-requisito de inscrições por oferta.
- `d4e5f6a7b8c9` — head anterior (programa NOT NULL na oferta).

### 1.3 Como a UNIQUE antiga vive no banco (respondendo à pergunta do passo)

SELECT no PostgreSQL local (estado `d4e5f6a7b8c9`, antes da migration nova):

- `pg_constraint`: `uix_conselho_turma_aluno_etapa` com `contype='u'`
  → **CONSTRAINT** `UNIQUE (turma_id, aluno_id, etapa)`.
- `pg_indexes`: `conselho_classe_pkey` + `uix_conselho_turma_aluno_etapa`
  → existe também o **índice de apoio homônimo** (criado junto pela constraint).

Conclusão: em PG são **ambos** (constraint + índice de mesmo nome); dropping da
constraint remove o índice. Em SQLite (testes usam `create_all`), a constraint
era inline na tabela via `__table_args__` do modelo — sem índice separado.
A migration trata os dois casos (constraint → `drop_constraint`; se restar só
índice → `drop_index`; SQLite via `batch_alter_table`).

### 1.4 Números do banco local (somente leitura)

| Medição | Valor |
|---|---|
| `conselho_classe` (linhas) | **0** |
| `conselho_resposta` com `aluno_id IS NULL` | **0** |
| turmas com `conselho_concluido=true` | **0 de 3** |
| `alembic_version` antes | `d4e5f6a7b8c9` |
| `alembic_version` depois (upgrade aplicado nesta etapa) | `e5f6a7b8c9d0` |

---

## 2. Diff por arquivo

### 2.1 `app/models/conselho.py` (+56/−6)

- `ConselhoClasse.__table_args__`: **saída** do
  `UniqueConstraint('turma_id','aluno_id','etapa', name='uix_conselho_turma_aluno_etapa')`;
  **entrada** de dois `db.Index` únicos parciais, no padrão da Fase 4:
  - `uix_conselho_legado` `(turma_id, aluno_id, etapa)`
    `WHERE turma_curso_id IS NULL` (`postgresql_where`+`sqlite_where`);
  - `uix_conselho_oferta` `(turma_curso_id, aluno_id, etapa)`
    `WHERE turma_curso_id IS NOT NULL`;
  - `ix_conselho_turma_curso` (não único, apoio à FK).
- Nova coluna `turma_curso_id` (Integer, FK `turma_curso.id`, **nullable**,
  `ondelete='RESTRICT'`, comment identificando NULL = legado).
- Relationship `oferta = db.relationship('TurmaCurso', lazy='joined')` (sem
  backref, para não tocar `academico.py` além do necessário).
- Docstrings de módulo e classe atualizados (NOTAS ONDA 4 — D5.1).

### 2.2 `app/models/academico.py` (+15/−0)

- `TurmaCurso` ganha, após `programa`:
  `conselho_concluido` (Boolean, NOT NULL, default False,
  `server_default=sa.text('false')`) e
  `avaliacao_inicial`/`avaliacao_percurso`/`avaliacao_final` (Text, nullable) —
  **mesmos tipos** usados em `Turma`.
- `Turma` permanece intacta (colunas legadas preservadas).

### 2.3 `migrations/versions/e5f6a7b8c9d0_conselho_oferta_esquema_d51.py` (novo, 322 linhas)

- `revision='e5f6a7b8c9d0'`, `down_revision='d4e5f6a7b8c9'`.
- Idempotente por inspeção (helpers `_colunas/_indices/_constraints/_fks`,
  padrão 5a67/e7f3). Upgrade em 6 passos: (1) coluna + FK PG
  `fk_conselho_classe_turma_curso` RESTRICT + `ix_conselho_turma_curso`;
  (2) colunas de conselho em `turma_curso`; (3) **remoção da UNIQUE antiga**
  (constraint → elif índice; SQLite em `batch_alter_table`); (4) os dois
  índices parciais únicos; (5) **backfill (d)** — ver decisão 2; (6) **cópia
  (e)** de `turma.conselho_concluido`/`avaliacao_*` para a oferta **somente
  quando a turma tem exatamente 1 oferta ativa** (nada atribuído por padrão nos
  demais casos; ramais PG `IS TRUE` / SQLite `= 1`).
- Backfill (d), portável (sem `UPDATE...FROM`):
  ```sql
  UPDATE conselho_classe SET turma_curso_id = (
      SELECT MIN(i.turma_curso_id) FROM inscricoes i
      WHERE i.aluno_id = conselho_classe.aluno_id
        AND i.turma_id = conselho_classe.turma_id
        AND i.turma_curso_id IS NOT NULL
      HAVING COUNT(DISTINCT i.turma_curso_id) = 1
  )
  WHERE conselho_classe.turma_curso_id IS NULL
  ```
  Sem valor único → subconsulta sem linhas → coluna segue NULL. **Não aborta**
  com ambiguidade.
- Downgrade reversível: guarda prévia contra duplicatas
  `(turma_id, aluno_id, etapa)` (RuntimeError, padrão e7f3); drop dos índices;
  recriação da UNIQUE antiga; drop da FK e das colunas novas.

### 2.4 `scripts/verificar_onda4_d5.py` (novo, 402 linhas)

Somente leitura, exit 0/1, padrão `verificar_onda4_fase4.py`
(`--db/--dsn/--sem-lista`, MAX_LINHAS=20). Reporta:
estrutura (colunas, FK PG, parciais únicos com WHERE, `ix_conselho_turma_curso`,
**ausência** da constraint antiga); (a) NULLs classificados
`2+ OFERTAS` / `TURMA SEM OFERTA` / `SEM INSCRICAO` (AVISO); (b) desses, os
concluídos/com `situacao_final` — prioridade de revisão (AVISO);
(c) duplicatas que violariam `uix_conselho_oferta` (FALHA); (d) divergência
`turma.conselho_concluido` × ofertas (AVISO); (e) turmas 2+ ofertas ativas com
`avaliacao_*` legado (AVISO); (f) **ConselhoResposta com `aluno_id` NULL
quantificada por turma × etapa** (AVISO); (g) conselho com `turma_id` ≠ turma da
oferta (FALHA).

### 2.5 `scripts/preparar_deploy_onda4.py` (+63 linhas)

Nova seção **"F. conselho × oferta (D5.1) — informativo"** ao final de `main()`
(após a seção E), com as checagens (a)/(b) em modo **AVISO — nunca bloqueia**
(não incrementa `bloqueios`). Guarda de existência: se `conselho_classe` não
existe ou `turma_curso_id` ainda não foi criado, avisa que a migration não foi
aplicada e segue.

### 2.6 `tests/test_d5_schema.py` (novo, ~250 linhas) — ver seção 4.

**Sementes existentes:** nenhum ajuste foi necessário. A única criação de
`ConselhoClasse` em testes (`tests/test_turma_curso_exclusao.py:142`) não passa
`turma_curso_id` → NULL → cai no índice legado, exatamente o estado pós-D5.1.

---

## 3. Banco local — aplicação

- `flask db upgrade` → `Running upgrade d4e5f6a7b8c9 -> e5f6a7b8c9d0` (OK;
  banco `pautaon` local, 0 linhas de conselho — nada backfill-ável).
- `python scripts/verificar_onda4_d5.py` → **exit 0**: estrutura íntegra
  (5 colunas novas OK, 2 parciais únicos OK, ix OK, constraint antiga removida,
  FK PG presente) e (a)–(g) todos limpos (banco sem conselhos).
- `python scripts/preparar_deploy_onda4.py` → **exit 0**; seção F imprime
  "nenhum conselho com turma_curso_id NULL" (informativo).

---

## 4. Testes — `tests/test_d5_schema.py` (SQLite in-memory, `create_all`)

Fixture no padrão dos testes pós-Onda 4 (`SQLiteTestConfig`, `db.create_all`,
um usuário por teste na semente `_seed`); helpers `nova_oferta`/`nova_inscricao`
de `tests/_helpers.py`. Turma com **2 ofertas exige 2 cursos** (UNIQUE
`turma_id, curso_id`) — a semente cria `Curso D5` e `Curso D5 B`.

| Teste | Regra coberta | Resultado |
|---|---|---|
| `test_colunas_novas_e_defaults` | `conselho_concluido=False` + server_default; `avaliacao_*=None`; `turma_curso_id` nullable, FK RESTRICT; legado aceito | passou |
| `test_conselho_por_oferta_mesmo_aluno_permitido` | mesmo aluno/turma/etapa em 2 ofertas → 2 conselhos | passou |
| `test_duplicata_mesma_oferta_recusada` | duplicata na mesma oferta/etapa → `IntegrityError`; etapa diferente na mesma oferta OK | passou |
| `test_duplicata_legada_recusada` | duplicata com `turma_curso_id NULL` → `IntegrityError` | passou |
| `test_legado_e_oferta_coexistem` | NULL + oferta convivem na mesma turma/aluno/etapa | passou |
| `test_schema_indices_parciais` | 2 parciais únicos + ix presentes; UNIQUE antiga ausente; WHERE visível na DDL `sqlite_master` | passou |

Suíte completa: **nenhum conflito de finalidade com testes existentes** —
nenhum precisou ser alterado.

---

## 5. Passo 6 — Ensaio em SCRATCH (`pautaon_ensaio`)

Protocolo (padrão P1/B5): o banco `pautaon` **não foi aberto** para os ensaios;
tudo em `pautaon_ensaio`, recriado do dump
`instance/backups/antes_fase4_20261022_211317.sql`
(`alembic_version=8c4e1f9a7d32`) para **cada cenário**, subido até
`d4e5f6a7b8c9` (5 migrations), injeção SQL sintética quando o caso pedia, e
`flask db upgrade` (aplica `e5f6a7b8c9d0`). Artefatos (fora do git, em
`instance/backups/ensaio_d5/`): `b/c/d/e_inject.sql`, `10_pos.sql`,
`run_ensaio.ps1`, `out/` (logs `upg_/verif_/pos_/down_*`).

Estrutura pós-upgrade idêntica em todos os cenários (evidência `pos_*.txt`):

```text
uix_conselho_legado  UNIQUE (turma_id, aluno_id, etapa) WHERE turma_curso_id IS NULL
uix_conselho_oferta  UNIQUE (turma_curso_id, aluno_id, etapa) WHERE turma_curso_id IS NOT NULL
ix_conselho_turma_curso  (não único)
fk_conselho_classe_turma_curso  FK → turma_curso(id) ON DELETE RESTRICT
uix_conselho_turma_aluno_etapa  (ausente — substituída)
```

### Cenário A — limpo (sem injeção)

Upgrade OK; script exit **0** tudo OK; downgrade `e5f6→d4e5` OK (recria
constraint `u` + índice homônimo, dropa parciais/colunas); re-upgrade OK
(idempotência por re-aplicação real).

### Cenário B — turma 2 com 2ª oferta, aluno 1372 inscrito só na oferta 2

Conselho legado `(2, 1372, INICIAL)` → **backfill vinculou**:
`turma_curso_id=2`; script: "(a) nenhum conselho NULL";
`conselho_classe=1 vinculadas=1`; exit 0. ✔ esperado.

### Cenário C — aluno inscrito em 2 ofertas da turma (ambíguo)

Injeção cria 2ª oferta + 2ª inscrição ativa do mesmo aluno na outra oferta.
Conselho **permanece NULL** (migration não aborta) e o script reporta:

```text
AVISO: 1 conselho(s) legado(s) sem oferta — 2+ ofertas: 1 | turma sem oferta: 0 | sem inscrição: 0
    1 | 2 | 1 - Natação | 1372 | INICIAL | False | None | 2 | 2 | 2+ OFERTAS
```

Exit **0** (AVISO não bloqueia). Downgrade com a linha ambígua NULL presente:
OK (sem duplicata, constraint recriada; re-upgrade OK). ✔

### Cenário D — turma de 1 oferta, conselho concluído + flags legadas

`turma 2`: `conselho_concluido=t`, `avaliacao_*='Parecer ... legado'`;
conselho `(2, 1372, FINAL, concluido=t, situacao='Aprovado')`. Pós-upgrade:
conselho **vinculado à oferta 2**; **oferta 2 recebeu**
`conselho_concluido=t` + os três pareceres copiados (exatamente 1 oferta
ativa); Turma intacta; script exit 0 (d) consistente. ✔

### Cenário E — turma sem oferta

Turma nova (id 4) sem nenhuma oferta + conselho concluído → **NULL
permanece**; script:

```text
AVISO: 1 conselho(s) legado(s) sem oferta — ... turma sem oferta: 1 ...
AVISO: desses, 1 concluído(s) ou com situacao_final (revisão prioritária...)
    1 | 4 | Turma Ensaio E sem oferta | 1372 | INICIAL | True | None | 0 | 0 | TURMA SEM OFERTA
```

Exit 0. ✔

### Estado final do scratch

`pautaon_ensaio` **recriado do dump e levado ao head `e5f6a7b8c9d0`**, sem
dados sintéticos (limpo); `verificar_onda4_d5.py` → exit 0 no estado final.
Descartável com `DROP DATABASE pautaon_ensaio`.

---

## 6. Decisões (correções do responsável incorporadas)

1. **UNIQUE antiga trocada JÁ na D5.1** por dois índices únicos parciais
   (padrão `uix_freq_legado`/`uix_freq_oferta`) — não se espera o endurecimento
   (D5.5) para liberar "um conselho por oferta".
2. **Backfill por INSCRIÇÕES**: `turma_curso_id` só é preenchido quando o
   conjunto de `turma_curso_id` distintos (inscrições ativas **e** inativas) do
   aluno na mesma turma tem exatamente 1 valor (`HAVING COUNT(DISTINCT...)=1`,
   `MIN` estável). A contagem de ofertas da turma **não** é critério.
3. **Respostas coletivas legadas quantificadas**: item (f) do script conta
   `ConselhoResposta` com `aluno_id IS NULL` por turma × etapa (0 no local;
   o modelo atual é NOT NULL — a checagem existe para o dump real de produção).

Decisões operacionais desta execução: cópia de flag/pareceres somente com
exatamente 1 oferta ativa (nada por padrão); migration não aborta em ambiguidade;
downgrade com guarda de duplicatas; `scripts/preparar_deploy_onda4.py` seção F
estritamente informativa.

---

## 7. Suíte de testes

```text
297 passed, 51 warnings in 39.79s
```

(0 falhas; 291 exigidos → 297 com os 6 novos de `test_d5_schema.py`.)

---

## 8. Pendências

- **D5.2+** (conforme `docs/D5_0_desenho.md`): escrita/rotas/templates ainda
  operam por turma — o esquema agora suporta a oferta, mas nada grava
  `conselho_classe.turma_curso_id` a partir das rotas; migrar a escrita,
  leituras/BI e a guarda M4 nas próximas etapas.
- Repetir o ensaio com **dump autêntico de produção** antes do deploy: local e
  scratch têm 0 conselhos; os volumes reais (inclusive `ConselhoResposta` com
  `aluno_id NULL`, se existirem) só aparecem no dump real.
- A coluna continua **nullable** até o endurecimento (D5.5); enquanto isso,
  `(c)` e `(g)` do script são as travas de integridade.
- `pautaon` local está no head `e5f6a7b8c9d0` (migration aplicada nesta etapa —
  necessário para os testes de fumaça pós-etapa).
- `instance/backups/ensaio_d5/` contém os artefatos do ensaio (fora do git);
  `docs/D5_0_desenho.md` permanece como fonte de desenho.

## 9. Git status (sem commit)

Alterados nesta etapa (dentro do escopo autorizado):
`app/models/conselho.py`, `app/models/academico.py` (M);
`migrations/versions/e5f6a7b8c9d0_conselho_oferta_esquema_d51.py`,
`scripts/verificar_onda4_d5.py`, `tests/test_d5_schema.py` (novos, ??);
`scripts/preparar_deploy_onda4.py` (untracked desde P1, +seção F).
Demais M/?? no `git status` são herança de etapas anteriores não commitadas
(L2: `app/models/MER.md`, `backlog_desenvolvimento.md`; B/M/P: rotas/registros/
templates/testes e relatórios `docs/*_relatorio.md`) — nada disso foi tocado
nesta etapa.
