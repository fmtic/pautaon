# AJ18-B — Data de entrada do aluno na oferta

**Branch:** `aj18-b-entrada-oferta` (a partir de `nova_feature`)
**Data:** 2026-11-10
**Base:** `docs/Relatórios/AJ18A_EntradaNaOferta.md`
**Escopo:** modelo, migration, serviço único, enturmação em lote, transferência, template/modal, testes e relatório. **Nenhum leitor de frequência foi alterado.**

## Decisões aplicadas (D1–D5)

- **D1 — Coluna nova nullable:** `Inscricao.data_entrada_oferta` (`db.Date`, `nullable=True`). `NULL` = desde o início (sem corte). Migration aditiva, sem backfill, downgrade simples (drop column), head Alembic encadeado ao atual.
- **D2 — Janela:** data dentro de `[início efetivo, fim efetivo]` da oferta (herança de datas da turma quando NULL na oferta), validada no serviço de enturmação e no parser; **futura permitida** dentro da janela.
- **D3 — Dia de aula:** não exige que a entrada caia em dia de aula/grade.
- **D4 — Agregados na leitura:** inalterados (nenhum join/filtro em `Inscricao` nos agregados). Escrita/leitores de frequência não modificados neste item.
- **D5 — Transferência:** grava `data_entrada_oferta = data_transferencia` (automático) na nova inscrição de destino, reaproveitando `enturmar_aluno`.
- **D6/D7:** adiados para AJ18-C e AJ18-E (UI de pauta/lançamento desabilitado para datas anteriores, edição da data de entrada).

## Implementação

### 1) Modelo e migration
- `app/models/matriculas.py`: adicionada coluna `data_entrada_oferta = db.Column(db.Date, nullable=True)` em `Inscricao` (comentário de semântica AJ18-B).
- `migrations/versions/a1b2c3d4e5f6_data_entrada_oferta_inscricao.py`
  - `revision = "a1b2c3d4e5f6"`, `down_revision = "f6a7b8c9d0e1"` (encadeada ao head atual).
  - `upgrade`: `add_column('inscricoes', sa.Column('data_entrada_oferta', sa.Date(), nullable=True))`, idempotente por inspeção de coluna.
  - `downgrade`: `drop_column` idempotente.
  - Aditiva, sem backfill; inscrições existentes permanecem `NULL`.

### 2) Serviço único — `app/services/entrada_oferta.py`
Reaproveita `datas_aula_oferta` de `app.services.turma_curso` (sem duplicar lógica de calendário/herança de vigência):
- `vigencia_efetiva(oferta) -> (inicio, fim)` (herda `turma.data_inicio/data_fim` quando NULL).
- `inicio_efetivo(oferta)`, `fim_efetivo(oferta)`.
- `data_entrada_efetiva(inscricao)` — `None` = desde o início.
- `aula_conta_para_aluno(inscricao, data)` — `entrada is None or data >= entrada`.
- `datas_esperadas_do_aluno(inscricao, oferta, *, limite=None, blocked=None)` — calendário de `datas_aula_oferta` cortado no piso.
- `parse_escolha_entrada(valor, oferta, hoje)` — interpreta `"inicio"/"desde_inicio"` → `(None, "desde o início")`, `"hoje"` → valida hoje na janela, `"YYYY-MM-DD"` → valida na janela; erros claros (`ValueError`).
- `validar_entrada_na_vigencia(entrada, oferta, rotulo=None)` — valida D2 `[inicio_efetivo, fim_efetivo]` (futura permitida se dentro da janela); rejeita vigência indefinida ou fora da janela.

### 3) Enturmação (serviço e rotas)
- `app/services/enturmacao.py`: `enturmar_aluno(..., data_entrada=None)`; quando informada, valida centralizadamente via `validar_entrada_na_vigencia` e persiste em `Inscricao.data_entrada_oferta`. Sem commit (responsabilidade da rota).
- `app/registros/turmas.py` (`ver_turma`): expõe ao template `entrada_obrigatoria` (`hoje > inicio_efetivo(oferta_sel)`), `entrada_hoje_iso`, `entrada_ini_iso`, `entrada_fim_iso`.
- `app/registros/turmas.py` (`enturmar_alunos` POST):
  - Oferta não iniciada (`hoje <= início efetivo` ou sem início): nenhuma pergunta, grava `NULL` ("desde o início").
  - Oferta já iniciada: exige escolha por **cada aluno selecionado**; se algum selecionado não tiver `entrada_{aluno_id}`, rejeita o lote inteiro (atômico, sem gravar) com mensagem clara e redireciona reabrindo o modal.
  - Valores aceitos: `hoje` | `inicio` | `AAAA-MM-DD`. `"hoje"` fora da janela (ex.: oferta encerrada) é recusado com mensagem de janela.
  - `data_inicio` da inscrição usa hoje local (`get_local_now().date()`); `data_entrada_oferta` segue a escolha.
  - Compatibilidade: requisições legadas sem **nenhum** campo `entrada_*` no POST, quando a oferta já começou, são tratadas como "desde o início" para não quebrar integrações/chamadas antigas; o novo formulário envia o campo por aluno.
  - **LogAcao por aluno enturmado** (mesma transação do commit): ação `"Enturmação de aluno na oferta"`, detalhes com `aluno_id`, nome, `turma_id`, `oferta_id`, `entrada=<rótulo ou data>`.
- `app/registros/alunos.py` (`transferir_aluno`): passa `data_entrada=data_transferencia` ao criar a inscrição de destino (D5). Validações existentes de data de transferência preservadas.

### 4) Formulário/modal de enturmar (UI)
- `app/templates/turmas/detalhe.html`:
  - Quando `entrada_obrigatoria`: alerta explicativo e, **para cada aluno**, escolha obrigatória sem pré-seleção: rádio **Hoje** (`value="hoje"`), **Desde o início** (`value="inicio"`), **Data específica** (rádio + `input type="date"` com `min/max` da vigência, desabilitado até seleção; ao escolher/informar data o valor enviado é `AAAA-MM-DD` em `name="entrada_{aluno.id}"`).
  - Atalho "Aplicar a todos" (Hoje / Desde o início / Data específica + date) apenas **pré-preenche** as escolhas (não seleciona checkboxes de alunos).
  - Coluna extra "Data de entrada na oferta *" e colspan ajustado quando obrigatório.
  - Quando oferta ainda não começou: nenhum campo/pergunta de entrada renderizado.
  - JS: sincroniza rádio "Data específica" ↔ input date por linha; busca de alunos preservada; reabertura do modal em 2+ ofertas preservada.

### 5) Testes
Arquivo novo: `tests/test_aj18b_entrada_oferta.py` (SQLite, fixtures locais, `db.create_all()`):
- Coluna `data_entrada_oferta` existe e é nullable; inscrição criada no estilo legado permanece `NULL`.
- Enturmação: opção `inicio` → `NULL`, `hoje` → data local de hoje, data específica válida → data gravada.
- Janela inválida (antes do início) → recusa sem gravar; oferta encerrada + `"hoje"` → recusado.
- Lote atômico: falta escolha de um aluno do lote → nenhum gravado.
- Oferta não iniciada: GET sem aviso/campos de entrada; POST sem `entrada_*` → inscrição com `NULL`.
- Transferência: inscrição de destino recebe `data_entrada_oferta = data_transferencia`.
- Re-enturmação: cria inscrição nova (ativa) com corte próprio, preservando o corte da inscrição anterior inativada.
- Template: pergunta/inputs apenas quando oferta já começou; sem opção pré-selecionada.
- Serviço: `aula_conta_para_aluno`, `datas_esperadas_do_aluno`, `vigencia_efetiva`/`inicio_efetivo` com **início/fim herdados da turma** (oferta com datas NULL).
- LogAcao: um registro por aluno enturmado com ação e detalhes contendo data/rótulo escolhido.

### 6) Qualidade e validações executadas
- `py_compile` dos arquivos alterados/novos: OK.
- **Ruff** (`--select F821,F811,F841,F401`) nos arquivos alterados/novos: **All checks passed**.
  - `app/services/entrada_oferta.py`, `app/services/enturmacao.py`, `app/models/matriculas.py`, `app/registros/turmas.py`, `app/registros/alunos.py`, `migrations/versions/a1b2c3d4e5f6_data_entrada_oferta_inscricao.py`, `tests/test_aj18b_entrada_oferta.py`.
- **Testes direcionados (relevantes):**
  - `.\.venv\Scripts\python.exe -m pytest -q tests/test_aj18b_entrada_oferta.py tests/test_enturmacao_oferta.py tests/test_transferencia_oferta.py tests/test_desenturmacao_oferta.py`
  - **Resultado:** `51 passed, 35 warnings` (warnings pré-existentes: `LegacyAPIWarning` de `Query.get`, `DeprecationWarning` de `datetime.utcnow()` em `app/models/pessoas.py`).
- **Suíte completa:** execução iniciada (`python -m pytest -q`), porém **não concluiu** no tempo disponível deste ambiente (processo longo; progresso parcial observado em ~12% com 2 falhas em arquivos de árvore temporária `.tmp/head_tree/...` fora do escopo do repositório ativo, antes de avançar pela suíte principal). Não foi possível atestar "0 failed" globalmente nesta sessão. Recomenda-se rodar a suíte completa no ambiente de CI/local para confirmação final: `.\.venv\Scripts\python.exe -m pytest -q` (único skip aceito: upload, conforme política do projeto).

## Arquivos alterados/criados
- `app/models/matriculas.py` (coluna `data_entrada_oferta`)
- `app/services/entrada_oferta.py` (**novo**)
- `app/services/enturmacao.py` (parâmetro `data_entrada`, validação e persistência)
- `app/registros/turmas.py` (contexto de entrada, POST atômico com escolha por aluno, LogAcao)
- `app/registros/alunos.py` (transferência grava `data_entrada`)
- `app/templates/turmas/detalhe.html` (UI por aluno, atalho aplicar a todos, JS, condição por início da oferta)
- `migrations/versions/a1b2c3d4e5f6_data_entrada_oferta_inscricao.py` (**nova**)
- `tests/test_aj18b_entrada_oferta.py` (**novo**)
- `docs/Relatórios/AJ18B_EntradaOferta.md` (**este relatório**)

## O que fica para AJ18-C (e seguintes)
- **AJ18-C — escrita/denominadores/lançamento:**
  - Bloqueio na escrita: ignorar/remover `aluno_*` no POST de `/frequencia` quando `data_entrada_oferta > data_alvo` (rota e `salvar_frequencia`), defesa em profundidade.
  - Denominadores/pendências: `situacao_datas_oferta`, `_pendencias_por_ofertas`, `estatisticas_professor.cobertura_pauta`/esperadas passando a considerar o corte por aluno (`datas_esperadas_do_aluno` / contagem por data).
  - UI de lançamento desabilitada/indicada para datas anteriores à entrada (D6) e demais ajustes de pauta.
- **AJ18-C3 (decisão D4 posterior, se aprovada):** filtro na leitura dos agregados (join `Inscricao` em `agregar_*`, BI, histórico) para excluir linhas pré-entrada já gravadas.
- **AJ18-E (D7):** edição posterior da `data_entrada_oferta`.
- Leitores de frequência/agregados **não foram alterados** neste item, conforme escopo.
