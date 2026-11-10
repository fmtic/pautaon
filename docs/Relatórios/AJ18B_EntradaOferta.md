# AJ18-B — Data de entrada do aluno na oferta

**Branch:** `aj18-b-entrada-oferta` (a partir de `nova_feature`)
**Commit base:** `fc82a1c` — `AJ18-B: entrada do aluno na oferta (modelo, serviço, enturmação, testes)`
**Data:** 2026-11-10
**Base:** `docs/Relatórios/AJ18A_EntradaNaOferta.md`
**Escopo:** modelo, migration, serviço único, enturmação em lote, transferência, template/modal, testes, correções pós-review (1–7) e relatório. **Nenhum leitor/agregado de frequência foi alterado** (D4/D6/D7 fora do escopo). Sem push; `flask db upgrade` não executado.

## Decisões aplicadas (D1–D5)

- **D1 — Coluna nova nullable:** `Inscricao.data_entrada_oferta` (`db.Date`, `nullable=True`). `NULL` = desde o início (sem corte). Migration aditiva, sem backfill, downgrade simples (drop column), encadeada ao head Alembic vigente.
- **D2 — Janela:** data dentro de `[início efetivo, fim efetivo]` da oferta (herança de datas da turma quando `NULL` na oferta), validada no serviço de enturmação e no parser; **futura permitida** dentro da janela.
- **D3 — Dia de aula:** não exige que a entrada caia em dia de aula/grade.
- **D4 — Agregados na leitura:** inalterados (nenhum join/filtro em `Inscricao` nos agregados). Escrita/leitores de frequência não modificados.
- **D5 — Transferência:** grava `data_entrada_oferta = data_transferencia` (automático) na nova inscrição de destino, reaproveitando `enturmar_aluno`.
- **D6/D7:** adiados para AJ18-C e AJ18-E.

## Implementação

### 1) Modelo e migration (correção 1 aplicada)
- `app/models/matriculas.py`: coluna `data_entrada_oferta = db.Column(db.Date, nullable=True)` em `Inscricao`.
- `migrations/versions/1fdc7c03bdc2_data_entrada_oferta_inscricao.py`
  - `revision = "1fdc7c03bdc2"`, `down_revision = "f2a3b4c5d6e7"` (encadeada ao head atual).
  - `upgrade`: `add_column('inscricoes', sa.Column('data_entrada_oferta', sa.Date(), nullable=True))`, idempotente por inspeção de coluna.
  - `downgrade`: `drop_column` idempotente.
  - Aditiva, sem backfill; inscrições existentes permanecem `NULL`.
  - **Correção 1:** a colisão de ID detectada na revisão anterior foi resolvida renomeando/ajustando a migration para `1fdc7c03bdc2` com `down_revision="f2a3b4c5d6e7"` (o ID antigo pertencia a `migrations/versions/a1b2c3d4e5f6_programa_oferta.py`, preservado). Verificação: `flask db heads` → `1fdc7c03bdc2 (head)`; `flask db history -r -5:` termina em `f2a3b4c5d6e7 -> 1fdc7c03bdc2 (head), AJ18-B — data de entrada...` sem avisos; `__pycache__` do nome antigo removido.

### 2) Serviço único — `app/services/entrada_oferta.py`
Reaproveita `datas_aula_oferta` de `app.services.turma_curso` (sem duplicar lógica de calendário/herança de vigência):
- `vigencia_efetiva(oferta) -> (inicio, fim)`, `inicio_efetivo(oferta)`, `fim_efetivo(oferta)` (herdam `turma.data_inicio/data_fim` quando `NULL`).
- `data_entrada_efetiva(inscricao)` — `None` = desde o início.
- `aula_conta_para_aluno(inscricao, data)` — `entrada is None or data >= entrada`.
- `datas_esperadas_do_aluno(inscricao, oferta, *, limite=None, blocked=None)` — calendário de `datas_aula_oferta` cortado no piso.
- `parse_escolha_entrada(valor, oferta, hoje)` — `"inicio"/"desde_inicio"` → `(None, "desde o início")`, `"hoje"` → valida hoje na janela, `"YYYY-MM-DD"` → valida na janela; erros claros (`ValueError`).
- `validar_entrada_na_vigencia(entrada, oferta, rotulo=None)` — valida D2 `[inicio_efetivo, fim_efetivo]` (futura permitida se dentro da janela); rejeita vigência indefinida ou fora da janela.

### 3) Enturmação (serviço e rotas) — correções 2–5
- `app/services/enturmacao.py`: `enturmar_aluno(..., data_entrada=None)`; quando informada, valida via `validar_entrada_na_vigencia` e persiste em `Inscricao.data_entrada_oferta`. Sem commit (responsabilidade da rota).
- `app/registros/turmas.py` (`ver_turma`): expõe `entrada_obrigatoria` (`hoje > inicio_efetivo(oferta_sel)`), `entrada_hoje_iso`, `entrada_ini_iso`, `entrada_fim_iso`.
- `app/registros/turmas.py` (`enturmar_alunos` POST):
  - Oferta não iniciada (`hoje <= início efetivo` ou sem início): nenhuma pergunta, grava `NULL` ("desde o início").
  - Oferta já iniciada: exige escolha por **cada aluno selecionado**; se algum selecionado não tiver `entrada_{aluno_id}`, rejeita o lote inteiro (atômico, sem gravar) com mensagem clara e reabre o modal. Valores aceitos: `hoje` | `inicio` | `AAAA-MM-DD`. `"hoje"` fora da janela (ex.: oferta encerrada) é recusado.
  - `data_inicio` da inscrição usa hoje local (`get_local_now().date()`); `data_entrada_oferta` segue a escolha.
  - **Correção 2 (sem compatibilidade legada):** requisições/POST sem **nenhum** campo `entrada_*` quando a oferta já começou **não** são mais tratadas como "desde o início" — o lote é recusado (o formulário atual envia o campo por aluno). Testes de enturmação ajustados para enviar `entrada_{aluno}="inicio"` em ofertas iniciadas (correção 3).
  - **LogAcao por aluno enturmado** (mesma transação): ação `"Enturmação de aluno na oferta"`, detalhes com `aluno_id`, nome, `turma_id`, `oferta_id`, `entrada=<rótulo ou data>`.
- `app/registros/alunos.py` (`transferir_aluno`): passa `data_entrada=data_transferencia` ao criar a inscrição de destino (D5).
- **Correção 4:** `tests/test_aj18b_entrada_oferta.py` inclui `test_oferta_iniciada_sem_nenhum_campo_entrada_recusa_lote` cobrindo POST sem campos `entrada_*` em oferta iniciada → lote recusado, nada gravado.
- **Correção 5:** `pyproject.toml` — `norecursedirs` inclui `.tmp`.

### 4) Formulário/modal de enturmar (UI)
- `app/templates/turmas/detalhe.html`:
  - Quando `entrada_obrigatoria`: alerta explicativo e, **para cada aluno**, escolha obrigatória sem pré-seleção: rádio **Hoje** (`value="hoje"`), **Desde o início** (`value="inicio"`), **Data específica** (rádio + `input type="date"` com `min/max` da vigência, desabilitado até seleção; valor enviado `AAAA-MM-DD` em `name="entrada_{aluno.id}"`).
  - Atalho "Aplicar a todos" (Hoje / Desde o início / Data específica + date) apenas **pré-preenche** as escolhas (não seleciona checkboxes de alunos).
  - Coluna extra "Data de entrada na oferta *" e `colspan` ajustado quando obrigatório. Quando a oferta não começou: nenhum campo/pergunta de entrada.
  - JS: sincroniza rádio "Data específica" ↔ input date por linha; busca de alunos preservada (guarda `if (searchInput)`); reabertura do modal em 2+ ofertas preservada.

### 5) Testes (AJ18-B)
`tests/test_aj18b_entrada_oferta.py` (SQLite, fixtures locais, `db.create_all()`):
- Coluna `data_entrada_oferta` nullable; inscrição legada permanece `NULL`.
- Enturmação: `inicio` → `NULL`, `hoje` → hoje local, data específica válida → gravada; janela inválida/`"hoje"` fora da janela → recusa sem gravar.
- Lote atômico: falta escolha de um aluno → nenhum gravado. **POST sem nenhum campo `entrada_*` em oferta iniciada → recusa do lote** (correção 4).
- Oferta não iniciada: GET sem aviso/campos; POST sem `entrada_*` → `NULL`.
- Transferência: destino recebe `data_entrada_oferta = data_transferencia`. Re-enturmação cria inscrição nova ativa com corte próprio, preservando o corte da inscrição anterior inativada.
- Template: pergunta/inputs apenas quando oferta já começou; sem pré-seleção.
- Serviço: `aula_conta_para_aluno`, `datas_esperadas_do_aluno`, `vigencia_efetiva`/`inicio_efetivo` com herança de vigência da turma.
- LogAcao: um registro por aluno enturmado com ação e detalhes contendo data/rótulo.

## Correções pós-review (6–7)

### Correção 6 — classificação do rótulo de LogAcao (AJ4)
- Novo rótulo emitido em `app/registros/turmas.py:1777` (`log_acao("Enturmação de aluno na oferta", ...)`) classificado conscientemente, sem afrouxar asserções:
  - `tests/test_aj4_logs_drift.py`: `"Enturmação de aluno na oferta"` adicionado a `ROTULOS_SEM_LINHA` (counto 8→9) e a `CATEGORIA_ESPERADA` como `"outras"` (decisão explícita, padrão dos rótulos de enturmação/AJ17-B); `Desbloqueio de login` permanece `"login"`. Ajustada a asserção congelada `len(ROTULOS_SEM_LINHA) == 9`.
- Validação: `.\.venv\Scripts\python.exe -m pytest -q tests/test_aj4_logs_drift.py` → **`59 passed in 7.73s`** (SQLite em memória, `APP_ENV=development`, `DATABASE_URL=sqlite:///:memory:`).

### Correção 7 — snapshots `ver_turma` (AJ6-B3/AJ6-B6)
- **Contexto:** `hoje_fixo = 2026-10-29` (`tests/conftest.py`) e fixtures de vigência das turmas/ofertas de auditoria tornam a oferta **já iniciada** nesse contexto (`entrada_obrigatoria` verdadeiro) — logo o modal de enturmar renderiza a UI de entrada por aluno onde aplicável. Mudanças concentradas na **região do modal/JS de enturmar** do `ver_turma`.
- **Regeneração controlada:** com `AJ6B4_ATUALIZAR_SNAPSHOTS=1` e `AJ6B6_ATUALIZAR_SNAPSHOTS=1` (alvos `-k "ver_turma or snapshot_nao_professor"`), regenerados os 11 snapshots afetados. Não houve alteração fora da região do modal de enturmar; não houve mudança em contexto de oferta não iniciada.
- **Diffs (normalizados, token/estrutura; `git diff --` por arquivo, 1 hunk/arquivo, apenas `-`/`+`):**

| Snapshot | +/− linhas | Resumo das mudanças |
|---|---:|---|
| `tests/snapshots/aj6b3_admin_t1.txt` | 1 / 1 | Guarda `if (searchInput)` na busca; JS AJ18-B adicionado: sincroniza rádio "Data específica" ↔ `input date` por linha (`.entrada-celula`/`.entrada-radio*`), "Aplicar a todos" apenas pré-preenche (`.js-aplicar-todos`, `#entrada-aplicar-data`). Sem aviso/coluna de entrada (modal sem lista de alunos carregada). |
| `tests/snapshots/aj6b3_admin_t2.txt` | 1 / 1 | Idem (região modal/JS de enturmar). |
| `tests/snapshots/aj6b3_gerencia_t1.txt` | 1 / 1 | Idem. |
| `tests/snapshots/aj6b3_gerencia_t2.txt` | 1 / 1 | Idem. |
| `tests/snapshots/aj6b3_pedagogico_t1.txt` | 1 / 1 | Idem. |
| `tests/snapshots/aj6b3_pedagogico_t2.txt` | 1 / 1 | Idem. |
| `tests/snapshots/aj6b3_secretaria_t1.txt` | 1 / 1 | Idem. |
| `tests/snapshots/aj6b3_secretaria_t2.txt` | 1 / 1 | Idem. |
| `tests/snapshots/aj6b3_servico_social_t1.txt` | 1 / 1 | Idem. |
| `tests/snapshots/aj6b3_servico_social_t2.txt` | 1 / 1 | Idem. |
| `tests/snapshots/aj6b6_admin_registros_ver_turma.txt` | 1 / 1 | Guarda `if (searchInput)` + JS AJ18-B **e** modal com oferta iniciada: aviso `#entrada-obrigatoria-aviso` ("Esta oferta já começou... nenhuma opção vem pré-selecionada..."), atalhos "Aplicar a todos" (Hoje/Desde o início/Data específica, `#entrada-aplicar-data` `min=2026-09-19` `max=2026-12-08`), cabeçalho extra "Data de entrada na oferta *", linha do aluno com `data-aluno="2"` e células de escolha `entrada_2` (rádios `hoje` — "Hoje (2026-10-29)", `inicio`, data específica com `input type=date` `min/max` desabilitado, sem pré-seleção). Demais regiões inalteradas. |

- **Marcadores observados nos diffs:** `entrada-obrigatoria`, `Data de entrada na oferta`, `entrada_2`, `entrada-celula`, `entrada-radio`/`entrada-date`, `js-aplicar-todos`, `entrada-aplicar-data`, "sincroniza rádio \"Data específica\"", "aplicar a todos", "Hoje (2026-10-29)", "Desde o início", guarda `if (searchInput)`. Alterações limitadas ao modal/JS de enturmar; nenhuma outra região do HTML alterada.
- **Validação pós-regeneração:**
  - `pytest -q tests/test_aj6b3_snapshot_nao_professor.py` → **`10 passed, 20 warnings in 7.89s`**
  - `pytest -q tests/test_aj6b6_matriz_rotas_professor.py` → **`12 passed, 26 warnings in 27.30s`**
  - `pytest -q tests/test_aj4_logs_drift.py` → **`59 passed in 7.73s`**
  - (Runs direcionados em SQLite em memória: `APP_ENV=development`, `DATABASE_URL=sqlite:///:memory:`; warnings pré-existentes `LegacyAPIWarning` de `Query.get` e `DeprecationWarning` de `datetime.utcnow()` em `app/models/pessoas.py`.)

## Qualidade e validações (consolidado)

- **Ruff** (`--select F821,F811,F841,F401`) nos arquivos alterados: **All checks passed** (`app/models/matriculas.py`, `app/services/entrada_oferta.py`, `app/services/enturmacao.py`, `app/registros/turmas.py`, `app/registros/alunos.py`, `tests/test_aj18b_entrada_oferta.py`, `tests/test_enturmacao_oferta.py`, `tests/test_aj4_logs_drift.py`).
- **Testes direcionados (AJ18-B e relacionados):** `pytest -q tests/test_aj18b_entrada_oferta.py tests/test_enturmacao_oferta.py tests/test_transferencia_oferta.py tests/test_desenturmacao_oferta.py` → **`52 passed, 38 warnings in 13.02s`**.
- **Correções 6–7:** `test_aj4_logs_drift.py` → **59 passed**; `test_aj6b3_snapshot_nao_professor.py` → **10 passed**; `test_aj6b6_matriz_rotas_professor.py` → **12 passed** (ver acima). `test_aj18b_entrada_oferta.py` → **15 passed** (isolado).
- **Suíte completa:** **não executada pelo agente** nesta sessão (execuções longas anteriores não concluíram). A suíte completa `pytest tests/ -q` deve ser rodada pelo usuário/CI para confirmação global (único skip aceito: upload).

## Arquivos alterados/criados

- `app/models/matriculas.py` (coluna `data_entrada_oferta`)
- `app/services/entrada_oferta.py` (**novo**)
- `app/services/enturmacao.py` (parâmetro `data_entrada`, validação e persistência)
- `app/registros/turmas.py` (contexto de entrada, POST atômico por aluno, recusa sem `entrada_*` em oferta iniciada, LogAcao)
- `app/registros/alunos.py` (transferência grava `data_entrada`)
- `app/templates/turmas/detalhe.html` (UI por aluno, atalho aplicar a todos, JS, condição por início da oferta)
- `migrations/versions/1fdc7c03bdc2_data_entrada_oferta_inscricao.py` (**nova**, head `down_revision="f2a3b4c5d6e7"`)
- `tests/test_aj18b_entrada_oferta.py` (**novo/ajustado**, inclui recusa de POST sem `entrada_*`)
- `tests/test_enturmacao_oferta.py` (ajustes para enviar `entrada_{aluno}` em ofertas iniciadas)
- `tests/test_aj4_logs_drift.py` (correção 6: classificação `"Enturmação de aluno na oferta"` → `outras`, `ROTULOS_SEM_LINHA`=9)
- `tests/snapshots/aj6b3_{admin,gerencia,pedagogico,secretaria,servico_social}_{t1,t2}.txt`, `tests/snapshots/aj6b6_admin_registros_ver_turma.txt` (correção 7: região modal/JS de enturmar)
- `pyproject.toml` (`norecursedirs` inclui `.tmp`)
- `docs/Relatórios/AJ18B_EntradaOferta.md` (**este relatório**)

## O que fica para AJ18-C (e seguintes)

- **AJ18-C — escrita/denominadores/lançamento:**
  - Bloqueio na escrita: ignorar/remover `aluno_*` no POST de `/frequencia` quando `data_entrada_oferta > data_alvo` (rota e `salvar_frequencia`), defesa em profundidade.
  - Denominadores/pendências: `situacao_datas_oferta`, `_pendencias_por_ofertas`, `estatisticas_professor.cobertura_pauta`/esperadas considerando o corte por aluno (`datas_esperadas_do_aluno` / contagem por data).
  - UI de lançamento desabilitada/indicada para datas anteriores à entrada (D6) e demais ajustes de pauta.
- **AJ18-C3 (D4 posterior, se aprovada):** filtro na leitura dos agregados (join `Inscricao` em `agregar_*`, BI, histórico) para excluir linhas pré-entrada já gravadas.
- **AJ18-E (D7):** edição posterior da `data_entrada_oferta`.
- Leitores de frequência/agregados **não foram alterados** neste item, conforme escopo.
