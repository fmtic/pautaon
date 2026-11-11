# AJ18-C2 — Tela de lançamento: aluno ainda não entrado desabilitado

**Branch:** `aj18-c2-entrada-ui` (criada a partir de `nova_feature`, sem push)  
**Data:** 2026-11-10  
**Base:** AJ18B / AJ18C (`app/services/entrada_oferta.py`, `Inscricao.data_entrada_oferta`)  
**Escopo:** item 3 do AJ18-C — tela de lançamento de frequência (`app/templates/frequencia/lancar.html`, `app/registros/core.py`, `app/static/js/frequencia.js`).

---

## 1. Contexto e Motivação

Quando um aluno é enturmado em uma oferta após o início das aulas (possuindo `Inscricao.data_entrada_oferta` preenchida com data posterior à data da aula selecionada):
1. **Aulas anteriores à entrada:** o aluno não deve ter lançamento de frequência exigido nas datas anteriores à sua entrada na oferta.
2. **Tela de lançamento:** o aluno permanece visível na lista da turma/oferta, porém seus botões de conceito aparecem desabilitados e sem envio de formulário, indicando visualmente `"Entrou em dd/mm"`.
3. **Regras de Negócio e Defesa:**
   - Nas datas a partir da entrada (e para alunos com entrada `NULL`), os campos renderizam normalmente com `name="aluno_<id>"` e habilitados.
   - A validação de valor do esportista obrigatório (A–D) e scripts de manipulação de formulário ignoram inputs desabilitados.
   - Pauta impressa, BI, histórico, certificados e agregados não foram tocados: a regra vale para **quem é esperado em cada data** (escrita, pendências e cobertura), não para as linhas de frequência já gravadas nem para os agregados de leitura.

---

## 2. Modificações Implementadas

### 2.1. `app/registros/core.py` (GET `/frequencia`)
- No fluxo do GET `/frequencia`, para a data da aula selecionada (`data`), resolve os alunos da pauta e carrega suas inscrições ativas.
- Utiliza a função única de negócio `aula_conta_para_aluno(insc, data_alvo)` (de `app.services.entrada_oferta`) para determinar se a aula é anterior à entrada de cada aluno.
- Mapeia os alunos cuja aula não conta por entrada posterior:
  ```python
  alunos_entrada_posterior[aluno_id] = insc.data_entrada_oferta
  ```
- Passa `alunos_entrada_posterior` para o template `render_template('frequencia/lancar.html', ...)`.

### 2.2. `app/templates/frequencia/lancar.html`
- Para cada aluno na lista:
  - Recupera a data de entrada se for posterior: `{% set entrada_aluno = (alunos_entrada_posterior.get(aluno.id) if alunos_entrada_posterior else None) %}`.
  - Se `entrada_aluno` existir:
    - O atributo `name="aluno_{{ aluno.id }}"` é **omitido** nos inputs `<input type="radio">`.
    - Os inputs recebem o atributo `disabled`.
    - Exibe abaixo dos botões a indicação:
      ```html
      <small class="text-muted mt-1 d-block"><i class="bi bi-info-circle me-1"></i>Entrou em {{ entrada_aluno.strftime('%d/%m') }}</small>
      ```
  - Se o aluno for elegível na data (ou tiver entrada `NULL`):
    - Mantém a renderização padrão com `name="aluno_{{ aluno.id }}"`, sem `disabled` (salvo readonly / transferido).
  - O layout novo (AJ16-D), os `ids` e o `?v={{ range(...) | random }}` do script permanecem estritamente preservados.

### 2.3. `app/static/js/frequencia.js`
- O seletor dos radios de aluno foi centralizado em `radiosAlunoHabilitados(form)`:
  ```javascript
  form.querySelectorAll('input.btn-check[name^="aluno_"]:not(:disabled)')
  ```
  Ele é a **fonte única** usada tanto pelo resumo de conceitos quanto pelo listener de alteração, de modo que a regra "ignorar aluno pós-entrada" tem um só ponto de manutenção e um contrato testável.
- `conceitosMarcados(form)` passou a compor `radiosAlunoHabilitados(form)` com o filtro `:checked`, mantendo o mesmo resultado anterior.
- No listener de eventos de alteração de conceitos, apenas radios habilitados (`:not(:disabled)`) disparam verificação de pendência de valores da aula.
- Exporta `radiosAlunoHabilitados` e `conceitosMarcados` em `module.exports` para testes estáticos em Node.js.

---

## 3. Testes Automatizados Executados

### 3.1. Nova Suíte Direcionada (`tests/test_aj18c2_entrada_ui.py`)
Cobre os 10 cenários abaixo (7 originais + 3 adicionados no fechamento):
1. `test_get_data_anterior_renderiza_desabilitado_com_rotulo_e_sem_name`: GET em data anterior renderiza o aluno com `"Entrou em dd/mm"`, inputs `disabled` e sem atributo `name`. O aluno de entrada `NULL` permanece normal.
2. `test_get_data_na_entrada_ou_posterior_renderiza_normal`: GET na data exata de entrada ou em datas posteriores renderiza ambos com `name` e sem `disabled`.
3. `test_aluno_entrada_null_sempre_normal`: Aluno com entrada `NULL` nunca recebe `disabled` por entrada.
4. `test_regressao_oferta_sem_entrada_renderiza_todos_normais`: Ofertas sem datas de entrada renderizam todos os alunos normalmente.
5. `test_ida_e_volta_post_grava_somente_aluno_elegivel`: POST simulando a submissão do formulário na data anterior (sem `name` do aluno desabilitado) grava apenas o aluno elegível.
6. `test_valor_obrigatorio_ignora_aluno_desabilitado`: Com catálogo de valores ativo na unidade, aula sem conceitos A–D de alunos elegíveis não exige seleção de valor do esportista.
7. `test_js_conceitos_marcados_ignora_disabled`: Executado em Node.js via subprocess, valida que `conceitosMarcados` descarta inputs com `disabled: true`.
8. `test_js_radios_aluno_habilitados_ignora_disabled`: Executado em Node.js via subprocess, valida que o seletor único `radiosAlunoHabilitados` devolve apenas radios habilitados (marcados ou não) e que `conceitosMarcados` continua interseccionando com `:checked`.
9. `test_inscricao_inativa_com_entrada_posterior_nao_desabilita`: aluno com inscrição **inativa** antiga (entrada posterior) na mesma oferta e inscrição ativa com `data_entrada_oferta` `NULL` renderiza normalmente — a linha inativa não vence.
10. `test_inscricao_de_outra_oferta_nao_desabilita`: inscrição com entrada posterior em **outra oferta da mesma turma** não desabilita o aluno na oferta selecionada; na oferta onde a entrada existe, ele é desabilitado.

### 3.2. Bateria Completa de Testes Direcionados
- `tests/test_lancar_template_estrutura.py`: **2 passed** (divs balanceados e integridade de textos mantida).
- `tests/test_valor_obrigatorio.py`: **25 passed**.
- `tests/test_valor_obrigatorio_ui.py`: **13 passed**.
- `tests/test_valor_obrigatorio_caracterizacao.py`: **6 passed**.
- `tests/test_frequencia_oferta.py`: **16 passed**.
- `tests/test_aj6b6_matriz_rotas_professor.py`: **11 passed** (inclusive `test_snapshot_nao_professor_inalterado[secretaria-registros.frequencia]`).
- `tests/test_aj6b3_snapshot_nao_professor.py`: **1 passed**.
- `tests/test_aj18c1_entrada_backend.py`: **9 passed**.
- `tests/test_aj18c2_entrada_ui.py`: **10 passed**.
- `tests/test_grade_horario_js.py`: **12 passed**.
- **Total: 105 testes direcionados passando com sucesso.**

---

## 4. Linting e Qualidade de Código

Executado:
```powershell
python -m ruff check app/registros/core.py tests/test_aj18c2_entrada_ui.py --select F821,F811,F841,F401
```
Resultado: **All checks passed!**

A varredura de `tests/` com as mesmas regras (`F821,F811,F841,F401`) aponta **13 F401 preexistentes** em arquivos não tocados por esta tarefa (imports não usados em testes antigos), mantidos como estão para não misturar escopo. Nenhum achado nos arquivos alterados.

---

## 5. Commits Realizados na Branch `aj18-c2-entrada-ui`

- `43e22ce` — `feat(aj18c2): desabilita inputs e exibe 'Entrou em dd/mm' para aluno pos-entrada na tela de lancamento`
- `85ba662` — `docs(aj18c2): relatorio da tela de lancamento com aluno pos-entrada desabilitado`
- `e75d619` — `test(aj18c2): preserva linha em branco final do teste apos execucao da suite`
- `b2dd8d9` — `refactor(aj18c2): centraliza seletor de radios de aluno e cobre inscricao inativa e outra oferta`
