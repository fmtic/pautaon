# H5b — Drop físico das colunas escalares de agenda e CHECK 0–5

**Data:** 26/10/2026 (ensaio) · **Aplicação no principal:** 27/10/2026 · **Branch:** `nova_feature` (sem push) · **Head Alembic:** `8d2e3f4a5b6c` — **aplicado no principal**
**Escopo:** remover **fisicamente** as seis colunas escalares de agenda (`turma.dias_semana/hora_inicio/hora_fim` e `turma_curso.dias_semana/hora_inicio/hora_fim`) e apertar `ck_tch_dia` de 0–6 para **0–5**, em **duas migrations reversíveis**. A grade `turma_curso_horario` permanece a única fonte de agenda (§7.32a do MER).

**Decisões aplicadas:** migration A separada da B; upgrade recusa dia 6 (A) e oferta sem grade (B) **antes de qualquer DDL**; downgrade da B reconstrói uma projeção a partir da grade, com **perda documentada**; turma com 0 ou 2+ ofertas ativas → NULL; principal **migrado em 27/10/2026 sob autorização explícita**, após preflight e backup novos (§6).

---

## 1. Commits

| Commit | Conteúdo |
|---|---|
| `d19687b` | H5b-A — migration `7c1d2e3f4a5b`: CHECK `ck_tch_dia` 0–6 → 0–5, pré-checagem read-only de dia 6, downgrade reversível. |
| `29080aa` | H5b-B — migration `8d2e3f4a5b6c`: drop das 6 colunas, pré-checagem read-only de oferta sem grade, downgrade que reconstrói a projeção; modelos `Turma`/`TurmaCurso` limpos. |
| `a40bbec` | H5b-P4 — `tests/test_h5b_migrations.py` + `test_turma_curso_horario_schema.py` (0–5). |
| `dd38d35` | H5b-P7/P8 — MER, backlog e este relatório (ensaio no scratch, principal ainda intocado). |
| (este commit) | H5b-P9 — aplicação real de A+B no principal, evidências, MER/backlog e relatório atualizados. |

Os scripts temporários do ensaio (`_tmp_h5b_*`) foram apagados; nenhum deles foi commitado.

---

## 2. Pré-requisitos, backup e preflight (somente leitura no principal)

- `flask db heads` = **`5730d7c594ba`**; suíte de partida **640 passed**.
- Backup: `instance/backups/pautaon_pre_H5b.sql`, SHA256 `C5D5398354267EC66AF99C7B61BAC39063A9C4F515708E75E81021C72CCB5258`; restore provado no scratch antes de qualquer ensaio.
- Preflight no principal, em transação **read-only** (sem derrubar sessões):

```
head 5730d7c594ba
3 turmas / 5 ofertas / 8 linhas de grade
ofertas (qualquer status) sem grade ......... 0
linhas de grade com dia_semana = 6 .......... 0
6 colunas presentes em turma/turma_curso .... sim
constraints/indexes/defaults/views/triggers/
functions/pg_depend sobre as 6 colunas ...... nenhuma
```

Nenhum PARE. O principal permaneceu em `5730d7c594ba` durante todo o ensaio do H5b, até a autorização de 27/10/2026 (§6).

---

## 3. Migrations

### 3.1 H5b-A — `7c1d2e3f4a5b` (revises `5730d7c594ba`)

- **Upgrade:** `_checar_dia_6(bind)` lê a grade e, se houver qualquer linha com `dia_semana = 6`, levanta `RuntimeError` listando `id`/oferta e **não altera nada**. Sem dia 6, dropa e recria o CHECK nomeado:
  `dia_semana >= 0 AND dia_semana <= 5`.
- **Downgrade:** recria o CHECK anterior (`<= 6`); nenhum dado é alterado.
- **Portabilidade:** PostgreSQL usa `DROP/ADD CONSTRAINT`; SQLite usa `batch_alter_table(recreate="always")`. O modelo `TurmaCursoHorario` declara o mesmo CHECK 0–5.

### 3.2 H5b-B — `8d2e3f4a5b6c` (revises `7c1d2e3f4a5b`)

- **Upgrade:** `_checar_ofertas_sem_grade(bind)` verifica **toda oferta, de qualquer status**, e aborta com `RuntimeError` listando as ofertas sem nenhuma linha de grade. Passando, dropa `dias_semana`, `hora_inicio` e `hora_fim` de `turma_curso` e de `turma` (idempotente por coluna; `IF EXISTS` no PostgreSQL).
- **Downgrade:** recria as colunas nullable (`VARCHAR(80)`, `TIME`, `TIME`) e repopula a projeção:
  - oferta com grade **uniforme** (mesmo par em todos os dias, com hora) → CSV canônico dos dias + o par;
  - oferta **não uniforme** ou com dias sem hora → CSV dos dias + `hora_inicio`/`hora_fim` **NULL**;
  - oferta sem grade → tudo NULL;
  - turma com **exatamente 1** oferta ativa → espelha a projeção dessa oferta;
  - turma com **0 ou 2+** ofertas ativas → tudo NULL.
- **Perda de informação:** a grade **nunca** é perdida; o que se perde é a possibilidade de o par escalar representar horários diferentes por dia. Reaplicar o upgrade (drop) é seguro.

---

## 4. Modelos e testes

- `app/models/academico.py`: `Turma` e `TurmaCurso` perdem as seis declarações; `TurmaCursoHorario` documenta o domínio 0–5 e o CHECK do modelo passa a `<= 5`.
- `tests/test_h5b_migrations.py` (7 testes): recusa de dia 6; aceitação de 0 e 5; drop idempotente; recusa de oferta sem grade; downgrade uniforme/espelho; não uniforme; turma com 0 e 2+ ofertas; re-upgrade.
- `tests/test_turma_curso_horario_schema.py`: domínio 0–5, incluindo recusa de 6 e aceitação de 0/5.
- **Suíte completa: 641 passed, 0 falhas.** `ruff check app tests --select F821` e `ruff check migrations --select F821`: limpos.

---

## 5. Ensaio no scratch Postgres (`pautaon_ensaio`)

- Scratch restaurado do backup do principal (head `5730d7c594ba`, 3 turmas / 5 ofertas / 8 linhas).
- **Antes:** snapshot determinístico (duas execuções idênticas, rodapé volátil `Em dd/mm/aaaa às HH:MM` normalizado para `<AGORA>`), incluindo schema, contagens, valores dos serviços, C.H., filtros e **49 leitores HTTP**.
- `flask db upgrade` aplicou A e B → head `8d2e3f4a5b6c`; CHECK `(dia_semana >= 0 AND dia_semana <= 5)`; seis colunas ausentes nas duas tabelas.
- **Depois:** snapshot equivalente com **61 comparações e 0 divergências** (contagens, serviços, filtros, C.H., leitores HTTP). C.H. da oferta 14 = **6.300 min**, igual ao H5a/H4; nenhum 500.
- **Smoke de escrita no head:** turma criada sem oferta (0 ofertas, 302), primeira oferta criada via POST real com grade Seg/Qua 09:00–10:00, C.H. **2.280 min** (= ocorrências × 60), limpeza confirmada (contagens de volta a 3/5/8).

### 5.1 Downgrade comparado ao dump original

`flask db downgrade 7c1d2e3f4a5b` seguido de snapshot:

| Objeto | Original (dump) | Reconstruído da grade | Resultado |
|---|---|---|---|
| ofertas 11–15 | dias + par | idênticos | ✅ exatos |
| turma 11 | Seg/Ter 13:00–15:00 | idêntico | ✅ |
| turma 10 | `Segunda` 14:00–17:00 | `Segunda, Quarta` 14:00–17:00 | ⚠️ dump **estagnado**; a oferta 14 tem grade Seg/Qua |
| turma 9 | `Segunda, Quarta` 08:00–11:00 | NULL | ⚠️ perda documentada: 3 ofertas ativas → regra 2+ |

A divergência da turma 10 mostra que o valor escalar antigo já não representava a grade real; a reconstrução prioriza a **verdade da grade**. A turma 9 tinha três ofertas ativas e um escalar herdado da oferta 11 — o downgrade não escolhe arbitrariamente uma delas e grava NULL. Em ambos os casos a grade permanece intacta e o comportamento visível no head não muda.

- **Re-upgrade:** head `8d2e3f4a5b6c`, colunas ausentes, 3/5/8; downgrade/re-upgrade sem perda de grade.
- Scratch deixado na head `8d2e3f4a5b6c`. Durante o ensaio o principal permaneceu intocado em `5730d7c594ba`; a aplicação real está na §6.

---

## 6. Aplicação no banco principal (27/10/2026)

Autorização explícita recebida em 27/10/2026. Execução entre 00:04 e 00:05 (America/Sao_Paulo), sem corrigir dados à mão e sem downgrade.

### 6.1 Preflight final (somente leitura)

Executado em transação `default_transaction_read_only=on` imediatamente antes da escrita:

```
server 18.6 / database pautaon / user postgres
head 5730d7c594ba
3 turmas / 5 ofertas / 8 linhas de grade
linhas de grade com dia_semana = 6 .......... 0
ofertas (qualquer status) sem grade ......... 0
6 colunas presentes em turma/turma_curso .... sim
constraints/indexes/defaults/views/triggers/
functions/pg_depend/policies sobre as 6 colunas ... nenhuma
```

Nenhum PARE. Nenhuma outra sessão ativa no banco `pautaon` no momento do upgrade. Os 4 processos `run.py` do app local (listener `0.0.0.0:5000`, PID 544000) foram **mantidos vivos**: a migration exigiu apenas lock breve e o app continuou atendendo, sem reinício.

### 6.2 Backup de rollback

| Arquivo | Tamanho | SHA256 | Horário |
|---|---|---|---|
| `instance/backups/pautaon_pre_H5b_final.sql` | 549.114 bytes | `FB1D89FA48D96CDE6948CCCEF8FE450BF09CF9C5113B5DCA407C71AA4DBF6CAF` | 27/10/2026 00:04:37 |

`pg_dump --format=plain --clean --if-exists --no-owner --no-privileges --encoding=UTF8`, returncode 0; 35 `CREATE TABLE` e `COPY` de `aluno`, `turma`, `turma_curso` e `turma_curso_horario` presentes. Este é o **rollback preferido**.

### 6.3 Upgrade

```
$ flask db upgrade
INFO  [alembic.runtime.migration] Running upgrade 5730d7c594ba -> 7c1d2e3f4a5b, H5b-A — aperta o CHECK `ck_tch_dia` de 0–6 para 0–5.
INFO  [alembic.runtime.migration] Running upgrade 7c1d2e3f4a5b -> 8d2e3f4a5b6c, H5b-B — remove as 6 colunas escalares de agenda (Turma e TurmaCurso).
exit=0
```

Executado em 27/10/2026 00:04:55.

### 6.4 Conferência pós-upgrade

```
flask db heads ................................. 8d2e3f4a5b6c (head)
alembic_version ................................ 8d2e3f4a5b6c
ck_tch_dia ..................................... CHECK (((dia_semana >= 0) AND (dia_semana <= 5)))
colunas escalares restantes em turma ........... []
colunas escalares restantes em turma_curso ..... []
total de colunas turma / turma_curso ........... 19 / 20
turmas / ofertas / linhas de grade ............. 3 / 5 / 8
ofertas sem grade / linhas com dia 6 ........... 0 / 0
```

### 6.5 Dump pós-upgrade

| Arquivo | Tamanho | SHA256 | Horário |
|---|---|---|---|
| `instance/backups/pautaon_pos_H5b.sql` | 548.564 bytes | `69021097A2376E915E4FB3438A5C51D104E779FAEB6D6B0FA2E271151701A42D` | 27/10/2026 00:05:19 |

O dump confirma o schema final: `COPY public.turma` com 19 colunas (sem `hora_inicio`, `hora_fim`, `dias_semana`), `COPY public.turma_curso` com 20 (idem) e `CONSTRAINT ck_tch_dia CHECK (((dia_semana >= 0) AND (dia_semana <= 5)))`.

### 6.6 Smoke de UI (GET-only, app vivo)

35 GETs contra `http://127.0.0.1:5000` com sessão do usuário 24 (`pedagogico`, unidade 2): listagem e filtros de dia/horário, detalhe, ofertas, impressão de pauta e centros de custo, C.H., dashboard/painel, aluno/ficha, conselho, frequência e relatórios. **34/35 responderam 200**, sem traceback e sem redirecionamento para login.

Único erro: **500 em `/turmas/lixeira`** — `jinja2.exceptions.TemplateNotFound: turma_lixeira.html`. É **pré-existente e fora do H5b**: a rota e a chamada `render_template("turma_lixeira.html")` existem desde `14f5e47` e o template nunca existiu no repositório; o H5b não toca essa rota.

Fingerprints (`count` + `md5` de `t.*` ordenado por `id`) de `aluno`, `turma`, `turma_curso`, `turma_curso_horario`, `inscricoes`, `frequencia`, `registro_aula` e `conselho_classe` **idênticos antes/depois** dos GETs — nenhuma escrita acidental.

### 6.7 Rollback

Preferido: parar o app, restaurar `instance/backups/pautaon_pre_H5b_final.sql` e voltar o código ao commit `dd38d35` (ou anterior). Alternativa, **só por decisão explícita**: `flask db downgrade 7c1d2e3f4a5b` — use a revisão explícita, porque `downgrade -1` falha neste shell/Click. O resultado do downgrade já aceito: ofertas 11–15 exatas, turma 10 defasada no dump e turma 9 NULL pela regra 2+ (§5.1).

---

## 7. O que NÃO mudou

- **Comportamento visível:** nenhum texto/valor muda em grades uniformes; a agenda continua vindo exclusivamente da grade. Não há projeção, espelho nem fallback.
- **Escritores:** `definir_grade` continua a única escrita de agenda; contrato de dias 0–5, par completo, `fim > início`, sem duplicata.
- **Migrations históricas:** `5730d7c594ba` e anteriores intactas; o teste histórico da H1 continua recriando as colunas por DDL manual no SQLite.
- **`app/utils/dias_semana.py`:** permanece (formulários/serviços usam o conversor de texto).
- **Principal:** A+B aplicadas em 27/10/2026 (head `8d2e3f4a5b6c`), com backup pré/pós e smoke GET-only; sessões ativas não foram derrubadas e o app vivo seguiu respondendo, sem reinício.

---

## 8. Estado final e reprodução

**Estado:** principal e scratch na head **`8d2e3f4a5b6c`**; 3 turmas / 5 ofertas / 8 linhas de grade; 0 dia 6; 0 oferta sem grade; 6 colunas ausentes. Relatório e demais docs commitados na `nova_feature`, **sem push e sem merge**.

```
flask db heads                                  # 8d2e3f4a5b6c
flask db upgrade                                # aplica A+B (já aplicado no principal)
flask db downgrade 7c1d2e3f4a5b                 # ensaio da reconstrução (só por decisão explícita)
flask db upgrade                                # volta ao head
pytest -q                                       # 641 passed
ruff check app tests --select F821               # limpo
ruff check migrations --select F821              # limpo
```

Artefatos de rollback: `instance/backups/pautaon_pre_H5b_final.sql` (pré, preferido) e `instance/backups/pautaon_pos_H5b.sql` (pós).
