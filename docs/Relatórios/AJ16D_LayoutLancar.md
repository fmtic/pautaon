# AJ16-D — Novo layout de `app/templates/frequencia/lancar.html`

Data: 10/11/2026 · Branch `aj16-d-layout-lancar` (worktree `D:/pautaon-aj16d`, base `nova_feature` @ `71ca987`) · Sem push · SQLite only

## 1. Pedido

Substituir `app/templates/frequencia/lancar.html` pelo novo layout (arquivo anexado), sem alterar mais nada no
template (ids, `name` e `data-*` já preservados); ajustar somente os testes presos à estrutura antiga;
regenerar apenas o snapshot `aj6b6_secretaria_registros_frequencia.txt`; suíte completa sem falhas;
relatório.

## 2. O que foi feito

### 2.1 Template

`app/templates/frequencia/lancar.html` substituído pelo novo layout (o arquivo já constava modificado no
working copy de `main`; copiado verbatim para o worktree). O novo markup reorganiza o "QUADRO DE DADOS DA
AULA" em três seções (`<section>` com `secao-aula-titulo`):

1. **Seleção** — turma, curso da oferta e data (selects preservados: `select-turma`, `select-turma-curso`,
   `select-data`, hidden `turma`, `turma_curso`, `data_hidden`);
2. **Conteúdo da aula** — temas e valores do esportista (chips com contador "N de M selecionados");
3. **Registro da aula** — `atividades` e `observacoes` lado a lado (`col-md-6` cada, mesmo card).

Verificação dos campos do formulário (antes × depois): `name="turma"` (hidden + select), `name="turma_curso"`,
`name="data"` (select), `name="data_hidden"`, `name="tema_ids"`, `name="valor_ids"`, `name="atividades"`,
`name="observacoes"`, `name="aluno_{{id}}"`, `csrf_token` — todos presentes, ids e `data-*` preservados.
O CSS do layout é um `<style>` inline no próprio template (`.card-dados-aula .secao-aula-titulo`) —
autossuficiente, sem alteração em `static/css`.

### 2.2 Testes ajustados

- **`tests/test_atividades_aula.py::test_atividades_ficam_acima_das_observacoes_no_mesmo_card`** —
  mantida a asserção de ordem (`atividades` antes de `observacoes` no HTML); a checagem "`col-md-` não
  aparece no trecho" foi substituída por uma checagem de que os dois campos estão **dentro do mesmo
  `card-dados-aula`** (trecho entre a abertura do card e o início do "QUADRO DE FREQUÊNCIA"), refletindo o
  novo layout de duas colunas.

### 2.3 Snapshot regenerado

`tests/snapshots/aj6b6_secretaria_registros_frequencia.txt` regenerado com
`AJ6B6_ATUALIZAR_SNAPSHOTS=1` restrito ao caso `[secretaria-registros.frequencia]` (o outro caso
`[admin-registros.ver_turma]` não foi tocado — snapshot distinto).

**Resumo do diff do snapshot** (diff token a token, 546 → 575 tokens, 18 blocos não iguais — todos na
região de layout):

- reestruturação do quadro em 3 `<section>` com títulos (`titulo-selecao-aula`, `titulo-conteudo-aula`,
  `titulo-registro-aula`);
- novos wrappers de apresentação (`painel-temas`, `painel-valores`, `contador-temas`, `contador-valores`);
- `rows` dos textareas 2 → 3; estilos inline movidos para classes;
- `<div id="aviso-valor-pendente">` mudou de posição (mesmo conteúdo);
- novo `<style>` inline + `<script>` de contador "N de M selecionados" (somente apresentação).

**Contagens idênticas antes × depois** para todos os atributos de dados: `name="aluno_"` (6), `name="data"`,
`name="turma"` (2), `name="turma_curso"`, `name="tema_ids"`, `name="valor_ids"`, `id="select-data"`,
"Ir para a" (botão pendente) etc. **Conclusão: mudança exclusivamente de layout/markup — nenhum dado,
nenhuma regra por papel ou de renderização condicional foi alterado.**

## 3. Outros testes afetados por estrutura HTML

Nenhum outro teste falhou por estrutura. Os sensíveis à estrutura foram verificados antes da suíte
completa e passam: `test_lancar_template_estrutura.py`, `test_seletor_data_oferta.py`,
`test_valor_obrigatorio_ui.py`, `test_grade_horario_js.py`, `test_aj6b3_snapshot_nao_professor.py`,
`test_atividades_aula.py`, `test_aj6b6_matriz_rotas_professor.py` (58 testes).

## 4. Validação

- Suíte completa `pytest tests/`: **1659 passed, 0 failed, 1 skipped** (17min) — o único skip é o
  ambiental aceito (`test_aj5c_form_rerender.py`, "pasta de upload não existe no ambiente de teste").
- Ruff `F821,F811,F841,F401`: `tests/test_atividades_aula.py` limpo (único arquivo Python alterado;
  template `.html` e snapshot `.txt` não são Python).

## 5. Commits

- Commit `AJ16-D` neste branch: `app/templates/frequencia/lancar.html`,
  `tests/test_atividades_aula.py`, `tests/snapshots/aj6b6_secretaria_registros_frequencia.txt` e este
  relatório. Sem push.
