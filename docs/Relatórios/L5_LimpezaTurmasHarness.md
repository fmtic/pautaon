# L5 — Limpeza das turmas sem oferta e resíduos do harness

**Data:** 30/10/2026 · **Branch:** `nova_feature` · **Sem push**
**Escopo:** (E1) remoção física das turmas de teste sem oferta nos dois bancos; (E2) `tests/conftest.py` único + assert de identidade discriminador no teste do H4.

---

## 1. Pré-requisito e guarda

- `HEAD` = `nova_feature`@`8580c95`, árvore limpa, sem refs “conflicted copy”. O **F1 está contido em `origin/main`** (`488601f`, *Merge pull request #6*). `main` local segue em `c16a5ce` (behind 4) — não foi tocado (sem push).
- Suíte de partida: **1054 passed** (5m14s). `git status` + `git branch -a` conferidos no início das três etapas; nenhuma alteração externa apareceu.
- Bancos: `alembic_version = c9d0e1f2a3b4` nos dois.

---

## 2. E0a — inventário das turmas alvo (somente leitura)

Varredura por **FK dinâmica** (`pg_constraint` → `turma`) e por **nome de coluna** (`*turma*_id`, excluindo `turma_curso_id`), nos dois bancos.

| Banco | Turma | Nome | Ativa | ofertas | inscrições | frequencia | freq. legada | registro_aula | conselho | transferência | dia bloqueado | tema_aula | grade |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pautaon | 12 | Turma Alfa | sim (un. 3, per. 3) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| pautaon | 13 | Turma Gema | sim (un. 3, per. 3) | 0 | 0 | **2** | **2** | 0 | 0 | 0 | 0 | 0 | 0 |
| pautaon | 14 | Turma Zeta | sim (un. 3, per. 3) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| pautaon_ensaio | 34 | [ROTEIRO] Turma Vizinha - Oferta Unica | sim (un. 14, per. 24) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

**Linhas exatas (as únicas existentes):**

| freq.id | turma | aluno | turma_curso_id | data | conceito | valor_esportista | autor |
|---|---|---|---|---|---|---|---|
| 23 | 13 | 1455 | NULL (legado) | 2026-03-04 | A | NULL | NULL |
| 24 | 13 | 1455 | NULL (legado) | 2026-03-05 | A | NULL | NULL |

`log_acao` **não tem FK** para `turma` (guarda texto em `detalhes`) — nenhuma linha de log é alterada. **Resultado idêntico ao esperado** (12 e 14 sem lançamento; 13 com 2 legadas); nada a reportar como divergência.

---

## 3. E1 — remoção física (commit `ce7dcfd`)

**Ferramenta:** `scripts/limpar_turmas_sem_oferta.py`.

- `--ids` obrigatório (lista explícita), dry-run por padrão;
- `--aplicar` só em banco com “ensaio” no nome, salvo `--autorizar-principal`;
- `--aplicar` faz **backup automático** (`pg_dump`) em `instance/backups/<banco>_pre_limpeza_turmas.sql`; falha de backup aborta;
- **recusa** turma com oferta ou com qualquer vínculo fora de `frequencia` legada (`turma_curso_id IS NULL`);
- remove na ordem das FKs (conselho_resposta → conselho_classe → registro_aula → frequencia → inscricoes → transferencia → dia_bloqueado → turma_curso → turma);
- **valida o delta antes do commit**: só `turma` (−N) e `frequencia` (−N) podem mudar; qualquer outra diferença → `rollback` e exit 4.

### Contagens antes → depois

| Tabela | pautaon antes | pautaon depois | Δ | pautaon_ensaio antes | ensaio depois | Δ |
|---|---|---|---|---|---|---|
| `turma` | 5 | **2** | −3 | 8 | **7** | −1 |
| `turma_curso` | 2 | 2 | 0 | 11 | 11 | 0 |
| `turma_curso_horario` | 4 | 4 | 0 | 19 | 19 | 0 |
| `inscricoes` | 13 | 13 | 0 | 39 | 39 | 0 |
| `frequencia` | 54 | **52** | −2 | 18 | 18 | 0 |
| `registro_aula` | 4 | 4 | 0 | 4 | 4 | 0 |
| `conselho_classe` | 39 | 39 | 0 | 4 | 4 | 0 |
| `conselho_resposta` | 78 | 78 | 0 | 5 | 5 | 0 |
| `transferencia` | 0 | 0 | 0 | 1 | 1 | 0 |
| `dia_bloqueado_turma` | 0 | 0 | 0 | 0 | 0 | 0 |
| `tema_aula` | 52 | 52 | 0 | 55 | 55 | 0 |
| `log_acao` | 1014 | 1014 | 0 | 1482 | 1482 | 0 |

**Conferências finais:** nenhuma das turmas alvo existe mais; **zero turma ativa sem oferta ativa** nos dois bancos; nenhuma outra contagem mudou.
**Backups:** `pautaon_pre_limpeza_turmas.sql` (577.948 bytes) e `pautaon_ensaio_pre_limpeza_turmas.sql` (621.103 bytes).

---

## 4. E2 — resíduos do harness

### 4.1 Censo (antes)

**58** definições de `app`/`client` em **15** grupos de corpo distinto (normalização por AST, docstring removida). **43** imports cruzados de fixture: 41 de `test_conselho_oferta`, 1 de `test_v3a_datas_lancadas`.

### 4.2 `tests/conftest.py` (novo)

| Fixture | Origem | Consumidores |
|---|---|---|
| `app` | corpo canônico (sem `SERVER_NAME`) | 14 arquivos |
| `client` | corpo único | 14 arquivos |
| `app_com_servidor` | variante com `SERVER_NAME="localhost"` + assert de dialeto | 3 arquivos (via wrapper) |

Migração aplicada (AST, só o **idêntico**):

- **14** `app` e **14** `client` removidos dos arquivos;
- **3** `app` viraram wrapper — `def app(app_com_servidor): return app_com_servidor` — em `test_conselho_oferta.py`, `test_isolamento_unidade_escrita.py` e `test_security_regressions.py` (corpo idêntico ao da variante com `SERVER_NAME`, comportamento preservado);
- **27 variantes permanecem locais** por divergirem de propósito: `test_aluno_status`, `test_bi_indicadores`, `test_bi_turma_desativada`, `test_carga_horaria`, `test_carga_horaria_curso`, `test_certificado_modelo` (usa `UPLOAD_FOLDER` temporário), `test_concomitancia_grade_por_dia`, `test_d5_schema`, `test_dashboard`, `test_desativar_oferta`, `test_desenturmacao_oferta`, `test_enturmacao_oferta`, `test_filtros_turma_grade`, `test_filtros_turmas`, `test_impressao_grade_oferta`, `test_leitores_grade_h3e`, `test_maintenance`, `test_notnull_professor_oferta`, `test_sec01_uploads`, `test_transferencia_oferta`, `test_turma_curso`, `test_turma_curso_fase2`, `test_turma_curso_fase3`, `test_turma_curso_fase4`, `test_turma_curso_horario_migration`, `test_turma_curso_horario_schema`, `test_valor_esportista_migration`.
  Motivos: config inline (`app.config[...]`), sem `WTF_CSRF_ENABLED`, sem `db.session.remove()`/assert de dialeto, `UPLOAD_FOLDER`/`tempfile` próprio ou app de migrations.

### 4.3 Imports cruzados

**44** linhas `from test_* import ...` ajustadas: **6** reescritas (ficaram só os helpers usados) e as demais removidas por importarem apenas `app`/`client`, agora vindos do conftest.

### 4.4 Assert de identidade no teste do H4

`tests/test_h4_leitores_grade_variavel_smoke.py::...::test_aluno_ficha_atendimento_conselho_frequencia_seletor` — antes, dois `assert status_code == 200` (prof em `/frequencia` e pedag em `/frequencia_relatorio`), que passavam mesmo com o login preso em `coord` (admin). Agora:

| Identidade | Requisição | Esperado | Por que discrimina |
|---|---|---|---|
| prof | `GET /frequencia?turma_id=…` | 200 | professor da oferta acessa a pauta |
| prof | `GET /conselho/fechamento/<turma>` | **403** | `conselho.py:826` aborta só para PROFESSOR — se a sessão ficasse em `coord`, viria 200 |
| coord (admin) | `GET /frequencia_relatorio?turma=…` | **403** | `core.py:648` exige role PEDAGOGICO **exato** |
| pedag | `GET /frequencia_relatorio?turma=…` | 200 | o 200 só existe com a identidade trocada |

Os `200` de `imprimir-pauta` e `carga-horaria` no mesmo arquivo **permanecem** (são smoke de rota, não afirmação de identidade — nenhuma das duas rotas distingue perfil).

### 4.5 Resultado

- Suíte: **1054 passed** (mesmo total da linha de base), 5m11s.
- Ruff `F821/F811/F841` em `app`, `tests`, `migrations`: **limpo**.
- `F401` em `tests`: **37 → 11** (as 26 restantes em arquivos intocados ficam como dívida pré-existente).

---

## 5. Arquivos tocados

- **Novo:** `tests/conftest.py`.
- **Perderam `app` (14):** `test_dashboard_professor_pedagogico`, `test_datas_aula_oferta_grade`, `test_definir_grade`, `test_g1_p2_professor_oferta`, `test_h5b_migrations`, `test_i1_guardas_por_oferta`, `test_leituras_residuais_grade_h3f`, `test_resolver_oferta_grade`, `test_turma_curso_fase4_dash`, `test_turma_curso_horario_escritores`, `test_turma_curso_horario_servico`, `test_v3a_datas_lancadas`, `test_v3a_imprimir_coerente`, `test_v3b_engajamento_turma`.
- **Perderam `client` (14):** `test_carga_horaria_curso`, `test_certificado_modelo`, `test_conselho_oferta`, `test_dashboard`, `test_desativar_oferta`, `test_desenturmacao_oferta`, `test_filtros_turmas`, `test_isolamento_unidade_escrita`, `test_maintenance`, `test_sec01_uploads`, `test_security_regressions`, `test_v3a_datas_lancadas`, `test_v3a_imprimir_coerente`, `test_v3b_engajamento_turma`.
- **Wrapper do conftest (3):** `test_conselho_oferta`, `test_isolamento_unidade_escrita`, `test_security_regressions`.
- **Import cruzado ajustado (6):** `test_conselho_ui`, `test_d5_encerramento`, `test_d5_endurecimento`, `test_d5_leitores`, `test_painel_periodo`, `test_seletor_data_oferta`.
- **Assert de identidade:** `test_h4_leitores_grade_variavel_smoke`.
- **Limpeza `F401` nos arquivos tocados:** os 69 acima (nenhum arquivo fora de `tests/` foi alterado).
- **Banco (E1):** `scripts/limpar_turmas_sem_oferta.py` (novo) + MER §12.27 + backlog.

---

## 6. Pendências restantes

1. **MER §12.16** — item fechado: `conftest.py` existe; restam **27 variantes locais** justificadas acima (migrar exige unificar config de CSRF/uploads/migrations — decisão à parte).
2. **`F401` pré-existente** — 11 ocorrências em `tests/` (arquivos não tocados) e ~89 no total do projeto (82 corrigíveis), como já registrado no backlog.
3. **MER §12.26 (F1)** — segue aberto e sem relação com o harness: exibir autor em tela, autor original e `registro_aula.instrutor_id`.
4. **Seed x limpeza:** `scripts/semear_roteiro_manual.py` recria a turma vizinha (34) do ensaio se rodado de novo — a limpeza não altera o seed.
