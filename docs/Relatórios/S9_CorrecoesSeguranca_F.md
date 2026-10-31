# S9 — Fechamento (Prompt F)

**Data:** 31/10/2026 · **Branch:** nova_feature · **Sem push**

## Suíte completa final

Linha final: `1218 passed, 693 warnings in 420.35s (0:07:00)`

## Ruff

`ruff check --select F821,F811,F841 app tests scripts migrations`: All checks passed!

## Diagnóstico da lentidão

A suíte rodou em ~7 min (dentro do esperado ~5-6 min). A lentidão anterior era apenas tempo de execução normal. Fixture autouse `_limpar_login_controle` reativada em tests/conftest.py.

## Commits

- 5baa565 fix(tests): fixture autouse limpa login_controle + ruff seed (Prompt F)

## Conclusão

Prompt F concluído. Suíte verde, ruff limpo, sem push.

## Complemento

Tabela dos 10 testes mais lentos (``pytest tests --durations=10 -q``, saída em ``.tmp/pytest_durations.txt``):

| # | Tempo | Fase | Teste |
|---|-------|------|-------|
| 1 | 1.51s | call | tests/test_v3b_engajamento_turma.py::test_rodape_com_total |
| 2 | 1.44s | call | tests/test_info_professor.py::test_medicacao_e_idade_nunca_aparecem |
| 3 | 1.44s | call | tests/test_pauta_impressa_por_oferta.py::test_sem_parametro_usa_a_oferta_de_menor_id_quando_e_dele |
| 4 | 1.43s | call | tests/test_valor_obrigatorio_ui.py::test_form_marca_obrigatoriedade_quando_ha_catalogo |
| 5 | 1.39s | call | tests/test_valor_obrigatorio.py::test_presenca_com_valor_grava_conceito_valor_e_diario[D] |
| 6 | 1.29s | call | tests/test_relatorios_observacoes.py::test_periodo_anterior_mostra_o_historico |
| 7 | 1.27s | call | tests/test_valor_esportista_lancamento.py::test_is_readonly_desabilita_o_select_e_o_post_e_recusado |
| 8 | 1.14s | setup | tests/test_valor_obrigatorio.py::test_duas_ofertas_valida_so_alunos_da_oferta_do_formulario |
| 9 | 1.11s | call | tests/test_ui_grade_por_dia.py::test_editar_turma_modo_padrao_atualiza_grade_uniforme |
| 10 | 1.10s | setup | tests/test_valor_esportista_lancamento.py::test_conceito_j_limpa_valor_anterior |

Linha final desta execução: `1218 passed, 693 warnings in 344.82s (0:05:44)`.

O S9 não reportou a lista dos testes mais lentos nem a duração detalhada da suíte (apenas a linha final agregada); este complemento preenche essa lacuna.
