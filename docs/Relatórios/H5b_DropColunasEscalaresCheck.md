# H5b — Drop físico das colunas escalares de agenda e CHECK 0–5

**Data:** 26/10/2026 · **Branch:** `nova_feature` (sem push) · **Head Alembic:** `8d2e3f4a5b6c`
**Escopo:** remover **fisicamente** as seis colunas escalares de agenda (`turma.dias_semana/hora_inicio/hora_fim` e `turma_curso.dias_semana/hora_inicio/hora_fim`) e apertar `ck_tch_dia` de 0–6 para **0–5**, em **duas migrations reversíveis**. A grade `turma_curso_horario` permanece a única fonte de agenda (§7.32a do MER).

**Decisões aplicadas:** migration A separada da B; upgrade recusa dia 6 (A) e oferta sem grade (B) **antes de qualquer DDL**; downgrade da B reconstrói uma projeção a partir da grade, com **perda documentada**; turma com 0 ou 2+ ofertas ativas → NULL; principal **intocado** até autorização explícita.

---

## 1. Commits

| Commit | Conteúdo |
|---|---|
| `d19687b` | H5b-A — migration `7c1d2e3f4a5b`: CHECK `ck_tch_dia` 0–6 → 0–5, pré-checagem read-only de dia 6, downgrade reversível. |
| `29080aa` | H5b-B — migration `8d2e3f4a5b6c`: drop das 6 colunas, pré-checagem read-only de oferta sem grade, downgrade que reconstrói a projeção; modelos `Turma`/`TurmaCurso` limpos. |
| `a40bbec` | H5b-P4 — `tests/test_h5b_migrations.py` + `test_turma_curso_horario_schema.py` (0–5). |
| (este commit) | H5b-P7/P8 — MER, backlog e este relatório. |

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

Nenhum PARE. O principal permaneceu em `5730d7c594ba` durante todo o H5b.

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
- Scratch deixado na head `8d2e3f4a5b6c`. **Principal intocado em `5730d7c594ba`.**

---

## 6. O que NÃO mudou

- **Comportamento visível:** nenhum texto/valor muda em grades uniformes; a agenda continua vindo exclusivamente da grade. Não há projeção, espelho nem fallback.
- **Escritores:** `definir_grade` continua a única escrita de agenda; contrato de dias 0–5, par completo, `fim > início`, sem duplicata.
- **Migrations históricas:** `5730d7c594ba` e anteriores intactas; o teste histórico da H1 continua recriando as colunas por DDL manual no SQLite.
- **`app/utils/dias_semana.py`:** permanece (formulários/serviços usam o conversor de texto).
- **Principal:** nenhuma migration aplicada, nenhuma sessão derrubada, nenhum comando de escrita executado.

---

## 7. Pendência e reprodução

**Pendência:** aplicar A+B no banco principal **somente após autorização explícita**. Antes disso, repetir o preflight (0 dia 6, 0 oferta sem grade) e confirmar o backup.

```
flask db heads                                  # 8d2e3f4a5b6c
flask db upgrade                                # no scratch: aplica A+B
flask db downgrade 7c1d2e3f4a5b                 # ensaio da reconstrução
flask db upgrade                                # volta ao head
pytest -q                                       # 641 passed
ruff check app tests --select F821               # limpo
ruff check migrations --select F821              # limpo
```
