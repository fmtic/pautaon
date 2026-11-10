# AJ18-C — Escrita, denominadores e lançamento da frequência por data de entrada

**Branch:** `aj18-c-entrada-lancamento` (a partir de `nova_feature`, limpo, sem push)
**Data:** 2026-11-10
**Base:** `docs/Relatórios/AJ18A_EntradaNaOferta.md`, `docs/Relatórios/AJ18B_EntradaOferta.md` (AJ18-A/AJ18-B), serviço único `app/services/entrada_oferta.py`, `Inscricao.data_entrada_oferta` (`NULL` = desde o início)
**Estado:** **não implementado nesta sessão** — relatório de preparação/escopo (nenhuma alteração de código da AJ18-C aplicada; sem commit AJ18-C).

## Escopo solicitado (especificação)

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
