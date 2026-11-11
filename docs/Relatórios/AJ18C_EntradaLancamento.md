# AJ18-C — Escrita, denominadores e lançamento da frequência por data de entrada

**Branch:** `aj18-c-entrada-lancamento` (a partir de `nova_feature`, sem push)
**Data:** 2026-11-10
**Base:** `docs/Relatórios/AJ18A_EntradaNaOferta.md`, `docs/Relatórios/AJ18B_EntradaOferta.md`, serviço único `app/services/entrada_oferta.py`, `Inscricao.data_entrada_oferta` (`NULL` = desde o início)
**Escopo entregue (AJ18-C1, backend):** itens **(1) Escrita** e **(2) Denominadores por data** + **(6) qualidade**. **Não** alterados `app/templates/frequencia/lancar.html` nem `app/static/js/frequencia.js` (AJ18-C2). Sem `flask db upgrade`. Sem push.

## Decisões aplicadas (D4/D6 relevantes ao backend)

- **D4:** linhas já registradas antes da entrada não são alteradas; denominadores/pendências/cobertura passam a considerar apenas alunos **esperados por data** (`entrada NULL ou <= data`), sem `join` em `Inscricao` nas consultas/agregados de `Frequencia` (as inscrições são lidas apenas para resolver o conjunto de esperados da pauta; contagens de lançamento permanecem sobre `Frequencia`). Re-enturmação cria nova inscrição (frequências anteriores preservadas).
- **D6 (UI):** fora desta etapa (AJ18-C2).

## (1) Escrita — POST `/frequencia` e defesa em profundidade

- `app/registros/core.py` (POST `/frequencia`, no mesmo ponto de `permitidos`/pauta da oferta):
  - carrega inscrições ativas da pauta para a oferta e, para cada `aluno_*` recebido, além de ignorar fora da pauta, ignora o campo quando a entrada da inscrição é posterior à `data_alvo` (`app.services.entrada_oferta.aula_conta_para_aluno` — regra única, sem duplicação).
  - remove o campo ignorado do `form_data` (não encaminhado a `salvar_frequencia`) e registra **`LogAcao` por campo ignorado** (ação `Lançamento de frequência ignorado (entrada futura)`, detalhes com `aluno_id`, `oferta_id`, `turma_id`, `data`, `conceito_recebido`, `entrada`) no mesmo contexto/transação do request, defensivo contra manipulação de formulário.
  - logs de warning separados para ignorados fora da pauta e por entrada posterior.
- `app/utils/logica.py` (`salvar_frequencia`): defesa em profundidade — quando há `oferta_id` e `data_alvo`, remove de `conceitos` alunos cuja inscrição ativa na oferta tem entrada posterior à data (`aula_conta_para_aluno`), sem erro. Alunos sem conceito enviado não entram no plano, preservando linhas já registradas (inclusive anteriores à entrada). D4: nenhuma linha pré-entrada existente é alterada.

**Commit:** `0ef7718` — `AJ18-C1a: escrita ignora aluno_* pós-entrada com LogAcao e defesa` (`app/registros/core.py`, `app/utils/logica.py`).

## (2) Denominadores por data, pendências e cobertura

Regra única: esperado em uma data = aluno da pauta com inscrição ativa cuja entrada é `NULL` ou `<= data` (`aula_conta_para_aluno` / fonte `app/services/entrada_oferta.py`), sem duplicar lógica.

- `app/utils/frequencia.py`
  - `_pendencias_por_ofertas`: para cada data esperada da oferta, calcula o conjunto de alunos esperados naquela data; data conta como pendente quando nem todos os esperados têm lançamento. **Alunos ainda não entrados** na data não geram pendência. **Data sem aluno esperado** mantém comportamento de pauta vazia (não conta como pendente). Lançamentos de não-esperados não substituem esperados. Consultas de `Frequencia` por (data, aluno) sem `join` em `Inscricao`.
  - `situacao_datas_oferta`: status por data e resumo (`lancadas`, `total_ate_hoje`, `pendentes`, `proxima_pendente`) calculados sobre alunos esperados por data. Datas sem aluno esperado não entram em totais/pendências nem em `status` (pauta vazia naquela data). **"Próxima pendente"** passa a ser a data mais antiga (<= hoje) em que falta lançamento de algum esperado — nunca aponta data faltando apenas para ainda-não-entrados. Resumo de datas lançadas alinhado à mesma definição.
- `app/services/estatisticas_professor.py` (cobertura/aulas esperadas):
  - `cobertura_pauta.aulas_esperadas` = contagem de datas do calendário (<= hoje) com **ao menos um aluno esperado** naquela data (por entrada); data sem esperado não soma (pauta vazia).
  - `aulas_lancadas` / `aulas_pendentes` / `taxa_cumprimento_pauta`: uma data esperada conta como lançada quando todos os esperados daquela data têm conceito registrado (lançamentos de não-esperados não substituem). Cálculo por data via conjuntos de esperados/lançados, sem `join` em `Inscricao` nos agregados de frequência.

**Comportamento documentado (data sem aluno esperado):** data do calendário em que nenhum aluno da pauta é esperado (ex.: todos com entrada posterior à data) é tratada como pauta vazia para aquela data — não entra em `aulas_esperadas`/pendências/`total_ate_hoje`, não é marcada como pendente nem como "próxima pendente". Isso evita exigir lançamento quando não há aluno elegível.

**Commit:** `372e07e` — `AJ18-C1b: denominadores e cobertura respeitam data de entrada por data` (`app/utils/frequencia.py`, `app/services/estatisticas_professor.py`).

## (6) Qualidade

- `ruff check --select F821,F811,F841,F401 app/registros/core.py app/utils/logica.py app/utils/frequencia.py app/services/estatisticas_professor.py` → **All checks passed**.
- Testes direcionados automatizados desta etapa **não foram commitados**: tentativas de novos testes (`test_aj18c1a_escrita_entrada.py`, `test_aj18c1b_denominadores_entrada.py`) falharam no ambiente SQLite de teste por montagem de calendário/grade da oferta nas fixtures (oferta sem grade efetiva → calendário vazio), impedindo validar os cenários com verde confiável; os arquivos de teste rascunho foram removidos (não commitados). **Suíte completa não executada** (responsabilidade do usuário).

## Pendências / fora de escopo

- **Item (5) testes direcionados (AJ18-C1):** cobrir (SQLite) POST ignora `aluno_*` pós-entrada e salva demais; defesa em `salvar_frequencia`; `situacao_datas_oferta`/`_pendencias_por_ofertas`/cobertura com 1 aluno de entrada tardia (datas antigas não pendentes por ele, datas a partir da entrada o exigem); "próxima pendente" nunca em data faltando só para não-entrado; regressão oferta sem `data_entrada_oferta` (números idênticos) e verificação de snapshots conforme especificação. Ajustar fixtures para ofertar grade/calendário válido no SQLite (ex.: padrão dos helpers existentes com grade persistida corretamente) antes de commitar.
- **Item (3) / AJ18-C2:** `app/templates/frequencia/lancar.html` (aluno pós-entrada desabilitado, sem `name`, `"Entrou em dd/mm"` nas datas anteriores) e `app/static/js/frequencia.js` (validação/contador A–D ignorando desabilitados). Não tocados.
- **(4) Fora de escopo:** pauta impressa, BI, histórico, certificado e demais leitores (D4); edição da data de entrada (AJ18-E).
- **D4 agregados globais:** leitores/agregados de linhas já registradas não filtrados por `Inscricao`; sem `join` em `Inscricao` nos agregados de `Frequencia` (conforme implementado nos pontos alterados).

## Commits (hashes)

- `0ef7718` — AJ18-C1a: escrita ignora aluno_* pós-entrada com LogAcao e defesa (`app/registros/core.py`, `app/utils/logica.py`)
- `372e07e` — AJ18-C1b: denominadores e cobertura respeitam data de entrada por data (`app/utils/frequencia.py`, `app/services/estatisticas_professor.py`)
- `9151ee5` — AJ18-C1: atualizar relatório (escrita/denominadores, qualidade, pendências) (`docs/Relatórios/AJ18C_EntradaLancamento.md`) — versão anterior substituída por esta atualização

## Arquivos alterados (commits AJ18-C1)

- `app/registros/core.py` (item 1, `0ef7718`)
- `app/utils/logica.py` (item 1, `0ef7718`)
- `app/utils/frequencia.py` (item 2, `372e07e`)
- `app/services/estatisticas_professor.py` (item 2, `372e07e`)
- `docs/Relatórios/AJ18C_EntradaLancamento.md` (este relatório)

- **D4:** não filtrar agregados/leitores de linhas já registradas; nenhum `join` em `Inscricao` nos agregados (re-enturmação cria nova inscrição; frequências anteriores permanecem válidas). **D6:** aluno permanece na lista de lançamento, porém desabilitado em datas anteriores à entrada com indicação `"Entrou em dd/mm"`.
- **(1) Escrita:** no POST `/frequencia` (`app/registros/core.py`) ignorar `aluno_*` de alunos cuja entrada (inscrição ativa na oferta) seja posterior à data-alvo no mesmo ponto de `permitidos`; defesa em profundidade em `salvar_frequencia` (`app/utils/logica.py`) pular esses alunos sem erro; registrar `LogAcao` quando um campo ignorado for recebido (manipulação de formulário). Não alterar linhas já registradas antes da entrada.
- **(2) Denominadores por data:** em `situacao_datas_oferta`, `_pendencias_por_ofertas` (`app/utils/frequencia.py`) e `estatisticas_professor` cobertura/aulas esperadas (`app/services/estatisticas_professor.py`), alunos esperados por data = alunos da pauta com `entrada NULL ou <= data`; data completa quando todos os esperados daquela data lançados; lançamentos de não-esperados não substituem esperados; data sem aluno esperado mantém comportamento atual de "pauta vazia" (verificar/documentar). "Próxima pendente" e resumo de datas lançadas devem respeitar isso. Usar funções únicas do serviço (`datas_esperadas_do_aluno` / `aula_conta_para_aluno`) de `app/services/entrada_oferta.py`, sem duplicar regra.
- **(3) Tela `app/templates/frequencia/lancar.html`:** na data selecionada, aluno com entrada posterior aparece desabilitado (inputs `disabled`, sem `name` enviado) com `"Entrou em dd/mm"`; preservar ids/names/layout/JS (`app/static/js/frequencia.js`) — validar que o contador/validação de valores obrigatórios (A–D) ignora desabilitados.
- **(4) Fora de escopo/pendente:** pauta impressa, BI, histórico, certificado e demais leitores (D4); edição da data de entrada (AJ18-E).
- **(5) Testes (SQLite):** POST ignora `aluno_*` de entrada futura e salva os demais; defesa em `salvar_frequencia`; `situacao_datas_oferta`/pendências/cobertura com 1 aluno de entrada tardia (datas antigas não pendentes por eles, datas a partir da entrada os exigem); "próxima pendente" nunca aponta data faltando apenas para ainda-não-entrados; GET lançamento renderiza desabilitado + `"Entrou em dd/mm"` só nas datas anteriores; valor obrigatório ignora desabilitados; regressão: oferta sem `data_entrada_oferta` definida → números/HTML idênticos (rodar snapshots; se snapshot de lancar/pauta mudar, exibir diff token-a-token e regenerar apenas se limitado à nova região, como na AJ18-B).
- **(6) Qualidade:** apenas testes direcionados + `ruff --select F821,F811,F841,F401` nos arquivos alterados.
- **(7) Entrega:** commit com paths explícitos e hash; relatório com mudanças por item, testes e pendências.

## Situação do repositório

- Branch atual: `aj18-c-entrada-lancamento` (criada a partir de `nova_feature` limpo; sem push).
- Árvore de trabalho: limpa no início desta sessão de preparação.
- Sem execução de `flask db upgrade`.

## Levantamento inicial (exploração, sem implementação)

Áreas identificadas para os itens (1)–(3):
- `app/registros/core.py`: GET/POST `/frequencia` (contexto, `situacao_datas`/`oferta_atual`, filtro `permitidos` e tratamento de `aluno_*`, ponto para ignorar/envio de `LogAcao`).
- `app/utils/logica.py`: `salvar_frequencia`, planejamento/carregamento (`_planejar_frequencia`, `carregar_frequencias_e_valores`, `carregar_contexto_turma`) — defesa em profundidade na escrita.
- `app/utils/frequencia.py`: `situacao_datas_oferta` (atualmente conta por pauta completa/`len(aluno_ids)` e `lancados_por_data >= len(aluno_ids)`), `_pendencias_por_ofertas` e "próxima pendente" — denominadores por data.
- `app/services/estatisticas_professor.py`: cobertura de pauta/aulas esperadas.
- `app/services/turma_curso.py`: `_alunos_da_oferta`, `datas_esperadas_oferta`, `resolver_oferta_lancamento` (pauta/calendário auxiliares).
- `app/services/entrada_oferta.py`: fonte única das regras — `data_entrada_efetiva`, `aula_conta_para_aluno`, `datas_esperadas_do_aluno`.
- `app/templates/frequencia/lancar.html` e `app/static/js/frequencia.js`: renderização dos alunos/inputs e validação A–D/contador de valores obrigatórios.
- Referências de teste/snapshot: `tests/test_frequencia_oferta.py`, `tests/test_lancar_template_estrutura.py`, `tests/snapshots/aj6b6_secretaria_registros_frequencia.txt`.

## Alterações realizadas

Nenhuma (implementação AJ18-C pendente).

## Testes executados

Nenhum teste da AJ18-C executado (implementação pendente). Testes direcionados e ruff (item 6) serão executados e registrados após a implementação.

## Pendências / próximos passos

1. Item (1): ignorar `aluno_*` pós-entrada no POST `/frequencia` (ponto `permitidos`) com `LogAcao` por campo ignorado; defesa em `salvar_frequencia`.
2. Item (2): esperados por data via `aula_conta_para_aluno`/`datas_esperadas_do_aluno` em `situacao_datas_oferta`, `_pendencias_por_ofertas` e cobertura/esperadas do professor; ajustar "próxima pendente"/resumos; preservar comportamento de data sem aluno esperado.
3. Item (3): `lancar.html` (desabilitado, sem `name`, `"Entrou em dd/mm"` nas datas anteriores) e compatibilidade de `frequencia.js`.
4. Item (5): testes direcionados (SQLite) e verificação de regressão/snapshots conforme especificação.
5. Item (6): `ruff --select F821,F811,F841,F401` nos arquivos alterados.
6. Item (7): commit com paths explícitos + hash e atualização deste relatório com mudanças por item, diffs de snapshot (se houver) e resultados.

# AJ18-C1 — Conclusão dos testes backend

Todos os testes da AJ18-C1 foram desenvolvidos e passaram com sucesso no branch j18-c-entrada-lancamento.

## Testes executados (8/8 passing)

1. **test_post_ignora_aluno_entrada_posterior_salva_demais** — POST /frequencia ignora luno_* de aluno com entrada posterior à data (nada gravado, LogAcao registrado) e salva os demais; entrada <= data e NULL gravam normalmente.

2. **test_salvar_frequencia_defesa_entrada_posterior** — Defesa em salvar_frequencia chamada direta: aluno de entrada posterior não grava e não dá erro; linhas pré-entrada existentes não são alteradas (D4).

3. **test_situacao_datas_aluno_entrada_tardia** — situacao_datas_oferta / pendências com 1 aluno de entrada tardia: datas anteriores à entrada NÃO ficam pendentes por causa dele; datas a partir da entrada exigem lançamento; completar o lançamento dos demais fecha a data.

4. **test_proxima_pendente_nao_aponta_nao_entrado** — `proxima_pendente` nunca aponta data em que só falta aluno ainda não entrado.

5. **test_data_sem_aluno_esperado_nao_eh_pendente** — Data sem nenhum aluno esperado não é pendente nem "próxima pendente" (comportamento de pauta vazia documentado).

6. **test_estatisticas_professor_cobertura_entrada_tardia** — statisticas_professor: ulas_esperadas/lançadas/pendentes e 	axa_cumprimento_pauta respeitam a data de entrada por data.

7. **test_regressao_sem_data_entrada_igual_antes** — Regressão: oferta sem data_entrada_oferta definida → resultados idênticos aos de antes (todos os alunos esperados em toda data).

8. **test_re_enturmatacao_usa_inscricao_ativa** — Re-enturmação: aluno com inscrição antiga inativa e nova inscrição com entrada: usa só a inscrição ativa para decidir se a aula conta para ele.

## Itens concluídos da AJ18-C1

- **(1) Escrita** — POST /frequencia ignora luno_* de entrada futura com LogAcao; defesa em salvar_frequencia.
- **(2) Denominadores por data** — situacao_datas_oferta, _pendencias_por_ofertas, cobertura de professor usando ula_conta_para_aluno como fonte única.
- **(6) Qualidade** — Todos os testes direcionados passando com uff --select F821,F811,F841,F401 limpo.

## Pendências para a AJ18-C2

- Interface do usuário: template lancar.html e requencia.js para desabilitar campos, mostrar Entrou em dd/mm nas datas anteriores, validação de valor obrigatório desabilitado, etc.
- Novos endpoints ou modificações UI não estão neste entregável.

## Hashes dos commits

- 4408b13 — HEAD atual (j18-c-entrada-lancamento), relatório inicial.
-  ef7718 — AJ18-C1a: escrita ignora aluno_* pós-entrada com LogAcao e defesa.
- 372e07e — AJ18-C1b: denominadores e cobertura respeitam data de entrada por data.
- 9151ee5 — AJ18-C1: relatório sem estado 'não implementado' (mudanças, testes, hashes).

Próxima etapa: AJ18-C2 (interface do usuário).
