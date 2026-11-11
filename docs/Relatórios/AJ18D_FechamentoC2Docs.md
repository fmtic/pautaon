# AJ18-D — Fechamento do AJ18-C2 e documentação

**Branch:** `aj18-c2-entrada-ui` · **Data:** 11/11/2026 · **Sem push** · Trabalho no repositório real `D:\pautaon`, com o `.venv` existente (sem worktree, sem cópia e sem venv novo).

**Escopo:** fechar o AJ18-C2 (tela de lançamento com aluno pós-entrada desabilitado): commitar a alteração pendente, auditar todos os pontos que tocam `aluno_*`, provar a regressão de markup contra a `nova_feature`, cobrir dois cenários de inscrição que faltavam, corrigir a seção 1 do relatório do C2, atualizar MER/backlog e registrar tudo neste relatório. **Nenhuma alteração de código de aplicação além da auditoria do item 2** (que terminou em refatoração sem mudança de comportamento no JS).

---

## 1. Alteração pendente no início do fechamento

O `git status` mostrava `tests/test_aj18c2_entrada_ui.py` modificado. O diff era **exclusivamente uma linha em branco adicional no fim do arquivo**:

```diff
@@ -394,3 +394,4 @@ def test_js_conceitos_marcados_ignora_disabled(node):
 
     # E não gera pendência de valor obrigatório
     assert saida["pendenciaSoDesabilitado"] is False
+
```

A execução da suíte acrescenta essa quebra de linha final; o conteúdo do teste não muda. A alteração foi tratada como intencional (preserva o estado após rodar a suíte) e commitada sozinha, com caminho explícito:

- `e75d619` — `test(aj18c2): preserva linha em branco final do teste apos execucao da suite`
  - `tests/test_aj18c2_entrada_ui.py` (1 inserção)

---

## 2. Auditoria dos pontos que tocam `aluno_*` (item 2a)

Inventário em `app/static/js/frequencia.js` e `app/templates/frequencia/lancar.html`, com a situação de `disabled`:

| Arquivo:linha | Ponto | Toca `aluno_*`? | Ignora `disabled`? | Situação |
|---|---|---|---|---|
| `app/static/js/frequencia.js:37-41` | `radiosAlunoHabilitados(form)` — seletor `input.btn-check[name^="aluno_"]:not(:disabled)` | Sim | **Sim** | Fonte única; devolve habilitados (marcados ou não) |
| `app/static/js/frequencia.js:43-47` | `conceitosMarcados(form)` — compõe `radiosAlunoHabilitados` com `.filter(radio => radio.checked)` | Sim | **Sim** | Usado no resumo/pendência de valor |
| `app/static/js/frequencia.js:133-137` | Listener de `change` dos radios de aluno — `radiosAlunoHabilitados(formPauta).forEach(...)` | Sim | **Sim** | Só radios habilitados reavaliam pendência |
| `app/static/js/frequencia.js:124-130` | Listener de `change` de `input[name="valor_ids"]` | Não | N/A | Valores da aula, não aluno |
| `app/templates/frequencia/lancar.html:320-329` | Grupo de radios do aluno: `name="aluno_<id>"` só quando `not entrada_aluno`; `disabled` quando `not pode_receber_frequencia or is_readonly or entrada_aluno` | Sim | N/A (é a origem do `disabled`) | Aluno pós-entrada fica sem `name` e desabilitado |
| `app/templates/frequencia/lancar.html:331-332` | Rótulo `"Entrou em dd/mm"` quando `entrada_aluno` | Sim (contexto) | N/A | Texto informativo |
| `app/templates/frequencia/lancar.html:403-420` | IIFE do contador "N de M selecionados" | Não | N/A | Conta apenas `tema_ids`/`valor_ids` |

**Conclusão da auditoria:** não havia bug de comportamento. Os dois seletores existentes já usavam `:not(:disabled)`; o único risco era a regra estar duplicada em dois pontos. Foi extraída para `radiosAlunoHabilitados(form)`, exportada em `module.exports`, e os dois usos passaram a consumi-la — mesmo resultado, contrato único e testável. **Nenhuma mudança em `lancar.html`.**

---

## 3. Regressão de markup contra a `nova_feature` (item 2b)

Verificação **one-off** (script temporário, removido ao final; não ficou no repositório):

1. `GET /frequencia` renderizado com o template atual;
2. o loader do Jinja foi trocado por um `ChoiceLoader([DictLoader({'frequencia/lancar.html': antigo}), loader_original])`, com `app.jinja_env.cache.clear()`;
3. novo `GET` com o template de `git show nova_feature:app/templates/frequencia/lancar.html`;
4. extraído o mesmo trecho nos dois HTMLs: entre `<h5 class="mb-3">Frequência</h5>` e `<div class="d-flex justify-content-end mt-3 mb-4">`;
5. comparação **token a token** — tags + nós de texto não vazios, ignorando apenas espaços em branco.

**Resultado:** `129 == 129` tokens nos dois lados e **diff unificado vazio**. A única diferença textual bruta foi uma linha em branco, causada pela nova diretiva `{% set entrada_aluno ... %}` no template; ela não produz token e não altera o HTML entregue. Layout (AJ16-D), `ids`, `name`s, `data-*` e o script permanecem idênticos na renderização normal.

---

## 4. Novos testes de inscrição (item 2c)

Adicionados a `tests/test_aj18c2_entrada_ui.py` (o arquivo passou de 7 para **10 testes**):

| Teste | Cenário | O que prova |
|---|---|---|
| `test_js_radios_aluno_habilitados_ignora_disabled` | Node.js via `subprocess` | O seletor único devolve apenas habilitados (`["A","B"]`) e `conceitosMarcados` mantém só o marcado (`["A"]`) |
| `test_inscricao_inativa_com_entrada_posterior_nao_desabilita` | Inscrição **inativa** antiga, na mesma oferta, com entrada posterior; inscrição ativa com `data_entrada_oferta` `NULL` | A linha inativa não vence: o aluno renderiza normal, com `name` e sem `disabled` |
| `test_inscricao_de_outra_oferta_nao_desabilita` | Inscrição ativa com entrada posterior em **outra oferta da mesma turma** | Na oferta selecionada (entrada `NULL`) o aluno é normal; na oferta onde a entrada existe, aparece `"Entrou em dd/mm"` e o input some |

### Prova de que o `core.py` usa somente a inscrição ativa da oferta selecionada

Trecho de `app/registros/core.py:757-785` (GET `/frequencia`):

```python
if data_alvo_get and aluno_ids:
    inscricoes_get = []
    if oferta_atual is not None:
        inscricoes_get = Inscricao.query.filter(
            Inscricao.turma_curso_id == oferta_atual.id,   # oferta SELECIONADA
            Inscricao.ativo.is_(True),                     # somente ATIVA
            Inscricao.aluno_id.in_(aluno_ids),
        ).all()
    elif turma_id:
        inscricoes_get = (
            Inscricao.query
            .filter(
                Inscricao.turma_id == turma_id,
                Inscricao.ativo.is_(True),
                Inscricao.aluno_id.in_(aluno_ids),
            )
            .order_by(Inscricao.id)
            .all()
        )
    insc_map_get = {}
    for insc in inscricoes_get:
        insc_map_get.setdefault(insc.aluno_id, insc)      # 1 inscrição por aluno

    for aid in aluno_ids:
        insc = insc_map_get.get(aid)
        if insc is not None and not aula_conta_para_aluno(insc, data_alvo_get):
            entrada_ef = getattr(insc, "data_entrada_oferta", None)
            if entrada_ef is not None:
                alunos_entrada_posterior[aid] = entrada_ef
```

O filtro é explícito em `turma_curso_id == oferta_atual.id` **e** `ativo IS True`. Inscrições inativas ou de outra oferta não entram no mapa; a decisão de corte fica em `aula_conta_para_aluno` (serviço único `app/services/entrada_oferta.py`). O fallback por `turma_id` só existe quando não há oferta resolvida (mesma regra de autorização/escopo do GET).

---

## 5. Correção do relatório do C2 (item 2d)

`docs/Relatórios/AJ18C2_EntradaTela.md`, seção 1: os rótulos **D4/D6** estavam aplicados de forma invertida/ambígua (D4 é a regra de denominadores/leitura e D6 é a interface). A seção passou a descrever os dois pontos por comportamento:

- aulas anteriores à entrada **não são exigidas** do aluno;
- o aluno continua visível, com inputs desabilitados e `"Entrou em dd/mm"`;
- a regra vale para **quem é esperado em cada data** (escrita, pendências e cobertura), **não** para linhas de frequência já gravadas nem para agregados de leitura.

Também foram atualizadas as seções 2.3 (seletor único `radiosAlunoHabilitados`), 3.1 (10 cenários), 3.2 (105 testes direcionados, com a lista completa) e 5 (hashes reais).

---

## 6. Suítes e lint

Comando direcionado executado (`.\.venv\Scripts\python.exe -m pytest -q ...`):

| Arquivo | Resultado |
|---|---|
| `tests/test_lancar_template_estrutura.py` | 2 passed |
| `tests/test_valor_obrigatorio.py` | 25 passed |
| `tests/test_valor_obrigatorio_ui.py` | 13 passed |
| `tests/test_valor_obrigatorio_caracterizacao.py` | 6 passed |
| `tests/test_frequencia_oferta.py` | 16 passed |
| `tests/test_aj6b6_matriz_rotas_professor.py` | 11 passed |
| `tests/test_aj6b3_snapshot_nao_professor.py` | 1 passed |
| `tests/test_aj18c1_entrada_backend.py` | 9 passed |
| `tests/test_aj18c2_entrada_ui.py` | 10 passed |
| `tests/test_grade_horario_js.py` | 12 passed |
| **Total** | **105 passed** |

**Suíte completa de referência:** **1699 passed** (o C1 fechou em 1692; o responsável confirma a execução final). A referência anterior do C1 era 1692 passed; o C2 acrescentou 7 testes (3 no fechamento).

**Ruff** (`--select F821,F811,F841,F401`) nos arquivos Python alterados (`app/registros/core.py`, `tests/test_aj18c2_entrada_ui.py`): **All checks passed**. A varredura de todo o `tests/` aponta **13 F401 preexistentes** em arquivos não tocados (imports não usados), mantidos para não misturar escopo. O JS é validado pelo harness Node dos testes, não pelo Ruff.

---

## 7. MER e backlog

### 7.1. MER (`app/models/MER.md`)

- **§7.15:** linha `data_entrada_oferta` na tabela de `inscricoes` e nota explicando `NULL` = desde o início, migration aditiva **sem backfill**, piso de frequência, linhas já gravadas/agregados **não filtrados**, re-enturmação com nova inscrição, transferência gravando `data_transferencia` e ausência de edição posterior (AJ18-E).
- **§8.3:** bloco "Data de entrada do aluno na oferta (AJ18)" com:
  - serviço único `app/services/entrada_oferta.py` e suas funções;
  - valores aceitos no POST (`hoje`, `inicio`, `AAAA-MM-DD`) e lote **atômico**;
  - oferta não iniciada grava `NULL` sem perguntar;
  - transferência e re-enturmação;
  - POST `/frequencia` ignorando `aluno_*` pós-entrada + `LogAcao` "Lançamento de frequência ignorado (entrada futura)" e log de enturmação;
  - pendências e `situacao_datas_oferta` por alunos esperados na data;
  - `cobertura_pauta` (`aulas_esperadas`/`lancadas`/`pendentes`/taxa) e `total_aulas_realizadas`;
  - D4: agregados e linhas gravadas **sem** filtro por entrada;
  - UI desabilitada + `"Entrou em dd/mm"` e o seletor único do JS;
  - migration `1fdc7c03bdc2`, `down_revision = f2a3b4c5d6e7`, **head atual**;
  - AJ18-E explicitamente **ainda não existente**.
- **Tabela de migrations:** nova linha `1fdc7c03bdc2` (head) e `f2a3b4c5d6e7` deixou de ser head.
- **Head e contagem:** §7.4b, §8.3 e o cabeçalho passam a citar `1fdc7c03bdc2` e **26 revisões pendentes** entre a produção (`c4d5e6f7a8b9`) e o head; "Última atualização" em 2026-11-11 com o complemento AJ18-B.

### 7.2. Backlog (`backlog_desenvolvimento.md`)

Entrada nova no topo: **"Alterações do dia — 10/11/2026 (AJ18 — data de entrada do aluno na oferta)"**, com A (auditoria), B (modelo/serviço/enturmação), C1 (escrita/denominadores/cobertura), C2 (tela/JS/testes), docs, números de suíte (1692 e 1699) e pendências (deploy conjunto com a migration, AJ18-E e teste manual).

Entradas ausentes acrescentadas a partir dos relatórios existentes, sem inventar conteúdo:

- **AJ17-B** (10/11, branch `aj17-b-google`, commit `e5ae3df`) — endurecimento do login Google; **não integrado**; 25 testes próprios e suíte 1715 passed na branch.
- **AJ16-D** (10/11) — novo layout de `lancar.html`; nenhum `name`/`id`/`data-*` alterado; snapshot regenerado; suíte 1659 passed.
- **AJ16-E** (09/11) — correção do "Ir para a próxima pendente" (calendário da oferta no POST, não da turma); pré-existente, não regressão do AJ16-B; suíte 1663 passed.

### 7.3. Lacunas de documentação no ciclo AJ4–AJ15

Levantamento feito, **sem escrever as entradas faltantes** (decisão de escopo):

| Etapa | Entrada dedicada no backlog | Seção dedicada no MER | Situação |
|---|---|---|---|
| AJ4 | Sim (`## AJ4-A`, `## AJ4-B`) | Não (nota do drift em §7) | MER sem seção própria |
| AJ5 | Sim (`## AJ5-A/B/C`) | Não (notas em §7 e §8; sem seção AJ5) | MER sem seção própria; AJ5-D/E só em relatório |
| AJ6 | Não (consolidado 02/11, AJ3–AJ6) | Parcial (§8.26) | Falta entrada dedicada; MER consolidado |
| AJ7 | Não (uma linha no AJ15) | Parcial (§8.2, AJ7-A/D) | Falta entrada dedicada; AJ7-B/C sem seção |
| AJ8 | Não (uma linha no AJ15) | Não | Sem entrada dedicada e sem seção |
| AJ9 | Não (uma linha no AJ15) | Não | Sem entrada dedicada e sem seção |
| AJ10 | Não (uma linha no AJ15) | Parcial (bullet em §8.27) | Falta entrada dedicada |
| AJ11 | Não (uma linha no AJ15) | Não | Sem entrada dedicada e sem seção |
| AJ12 | Não (uma linha no AJ15) | Não | Sem entrada dedicada e sem seção |
| AJ13 | Não (uma linha no AJ15) | Parcial (§8.27) | Falta entrada dedicada |
| AJ14 | Não (uma linha no AJ15) | Não | Sem entrada dedicada e sem seção |
| AJ15 | Sim (`###` de 05/11) | Parcial (§8.2/§8.27 como produto) | Documentação da tarefa existe; sem seção "AJ15" |

Nenhuma dessas lacunas foi preenchida nesta tarefa — ficam registradas para uma rodada de documentação dedicada.

---

## 8. Commits

| Hash | Mensagem | Caminhos |
|---|---|---|
| `e75d619` | `test(aj18c2): preserva linha em branco final do teste apos execucao da suite` | `tests/test_aj18c2_entrada_ui.py` |
| `b2dd8d9` | `refactor(aj18c2): centraliza seletor de radios de aluno e cobre inscricao inativa e outra oferta` | `app/static/js/frequencia.js`, `tests/test_aj18c2_entrada_ui.py` |
| `a6fe6c6` | `docs(aj18d): fechamento do C2, auditoria disabled, MER e backlog` | `docs/Relatórios/AJ18D_FechamentoC2Docs.md`, `docs/Relatórios/AJ18C2_EntradaTela.md`, `app/models/MER.md`, `backlog_desenvolvimento.md` |

O hash deste commit de documentação é registrado no commit imediatamente seguinte, que altera apenas esta linha do relatório (o hash de um commit não pode conter o próprio hash).

Os commits anteriores da branch permanecem: `43e22ce` (UI), `85ba662` (relatório C2).

---

## 9. Pendências

1. **Suíte completa:** confirmar a execução final; referência desta entrega: **1699 passed**.
2. **Deploy conjunto:** a migration `1fdc7c03bdc2` deve subir **junto** com o código do AJ18. Produção está em `c4d5e6f7a8b9` (26 revisões atrás); inscrições existentes ficam `NULL` e mantêm o comportamento atual — **sem backfill**.
3. **AJ18-E:** agregados/relatórios e edição posterior da `data_entrada_oferta` **não** foram implementados. BI, histórico, certificados e pauta impressa continuam lendo o que foi gravado (D4).
4. **Teste manual:** enturmar aluno depois do início em uma oferta real; conferir `"Entrou em dd/mm"`, inputs bloqueados, POST manipulado ignorado/auditado e pendências/cobertura sem as aulas anteriores à entrada.
5. **AJ17-B:** branch `aj17-b-google` **não integrada**; não faz parte deste deploy.
6. **F401 preexistentes:** 13 achados em testes antigos, fora do escopo; corrigir em tarefa própria se desejado.
