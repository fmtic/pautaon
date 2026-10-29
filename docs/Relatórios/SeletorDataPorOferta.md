# Seletor "Data da Aula" filtrado pelo calendário da oferta escolhida

Data: 29/10/2026 · Branch `nova_feature` · Sem push · Sem migration

Depende da **V3a** (`docs/Relatórios/V3a_DatasLancadas.md`) — reusa `datas_aula_oferta`, as marcas ✔/○ e o resumo
`X de Y · Z pendente(s)`.

## 1. Pedido

Em `GET /frequencia` (pauta `frequencia/lancar.html`), quando há **uma oferta selecionada** (turma com 2+ ofertas e
escolha feita, ou oferta única automática), o seletor "Data da Aula" deve listar **somente** as datas do calendário
daquela oferta até hoje (vigência + grade da oferta, feriados/dias bloqueados descontados). Sem oferta escolhida ou em
turma sem oferta ativa (legado), o comportamento atual (união das ofertas, sem marcas) fica **inalterado**.

Regras adicionais:
- se a `data` da URL não pertence ao calendário da oferta escolhida (ex.: troca de oferta), **cair na data mais recente
  da oferta**, sem erro;
- manter marcas ✔/○, resumo e botão "próxima pendente" (V3a), com **Z igual às pendências do dashboard**;
- **POST `/frequencia`**: não alterar a regra de gravação; apenas conferir que a data postada continua aceita.

## 2. P0 — estado inicial

- Branch `nova_feature`; working tree com apenas a T1 recém-commitada (`6bbdd26`).
- **Baseline da sessão (P0, colhido antes da T1): 1000 passed, 0 failed.** Com a T1 (+1 teste de certificado) HEAD
  passa a **1001**; esta T2 acrescenta 5 → **1006**.

## 3. P1 — como a lista de datas era produzida

`GET /frequencia` (`app/registros/core.py`) chama `carregar_contexto_turma(turma_id)` (`app/utils/logica.py:317`) →
`gerar_datas(turma, incluir_futuro=False, ...)` → `dias_da_turma(turma.id)` (união dos dias das ofertas **ativas**).
Portanto, antes desta tarefa, o seletor mostrava a **união** das datas de todas as ofertas, mesmo com uma oferta
escolhida. As marcas da V3a (`situacao_datas_oferta`) já sabiam o calendário **da oferta** (`datas_aula_oferta`); o
que divergia era apenas a lista de opções do seletor.

## 4. Mudança (só no GET; POST intocado)

Em `app/registros/core.py`, dentro do bloco `if turma_id:` do GET, **depois** de resolver `oferta_atual` e montar a
pauta, e **antes** de carregar `data`:

```python
if oferta_atual is not None and not exigir_escolha:
    datas_calendario = [
        dia.strftime('%Y-%m-%d')
        for dia in datas_aula_oferta(
            oferta_atual, limite=get_local_now().date(),
            blocked=_blocked_dates_str(ctx['turma']),
        )
    ]
    ctx['datas'] = datas_calendario
    ctx['meses'] = _meses_disponiveis(datas_calendario)
    if data and data not in datas_calendario:
        data = datas_calendario[-1] if datas_calendario else None
```

- **Mesma fonte das marcas:** `datas_aula_oferta(oferta, limite=hoje, blocked=...)` é exatamente o calendário que
  `situacao_datas_oferta` usa para ✔/○ e para `total_ate_hoje` — logo o resumo e o **Z** continuam coerentes com as
  pendências do dashboard (a definição de "lançada" não foi tocada).
- **`dias_aula_oferta` em memória:** `datas_aula_oferta` só percorre a vigência com a **grade já carregada** por
  `selectin` em `ofertas_ativas` — não abre nova consulta por data (comprovado no teste de SELECTs constantes).
- **Fallback de data:** se a `data` da URL não está no calendário da oferta escolhida (troca de oferta), cai na mais
  recente (`datas_calendario[-1]`; `datas_aula_oferta` devolve em ordem crescente). Calendário vazio → `None` (o
  seletor fica só com "Selecione a data", sem erro).
- **`meses` do botão Imprimir:** recomposto com `_meses_disponiveis` (novo helper, espelha `meses_disponiveis` de
  `carregar_contexto_turma`) para refletir o calendário filtrado.
- **Sem oferta escolhida / legado:** `exigir_escolha` (2+ ofertas sem escolha) e `oferta_atual is None` (turma sem
  oferta ativa) **não** entram no `if` — seletor segue com a união da turma, sem marcas, como antes.
- **POST:** a validação de calendário (`data_post not in contexto.get('datas', [])`) continua checando contra a
  **união da turma** (nova chamada a `carregar_contexto_turma`, sem o filtro): toda data válida de uma oferta é
  subconjunto dessa união, então a gravação aceita a data **como hoje**. Nenhuma linha do POST foi alterada.

## 5. Testes (`tests/test_seletor_data_oferta.py`, 5 novos; reaproveitam a semente V3a)

Semente `test_v3a_datas_lancadas` com **2 ofertas de dias disjuntos** (O1 seg/qua, O2 ter/qui). As datas esperadas de
cada oferta são comparadas com as `<option>` do `#select-data`.

- `test_seletor_lista_so_datas_da_oferta_escolhida` — escolhendo O1, o seletor tem exatamente as datas de O1 e nenhuma
  de O2 (e vice-versa);
- `test_troca_de_oferta_com_data_invalida_cai_na_mais_recente` — `?turma_curso=O1&data=<data de O2>` → 200, a data de
  O2 some e a opção `selected` é a mais recente de O1;
- `test_sem_oferta_escolhida_seletor_segue_com_uniao` — sem escolha em 2+ ofertas, o seletor mantém a união da turma e
  **sem** marcas (inalterado);
- `test_marcas_e_resumo_preservados_com_filtro` — ✔/○, `X de Y · Z pendente(s)` e "Ir para a próxima pendente"
  continuam com o filtro;
- `test_selects_constantes_com_periodo_maior` — ampliar a vigência aumenta as opções **sem** alterar o nº de SELECTs do
  GET.

**Nenhum teste existente precisou ser ajustado.** A V3a já testava o seletor por oferta escolhida contra o calendário
da oferta (`_datas_ate_hoje`), e esses testes continuam válidos: as marcas ✔/○ e o resumo sempre vieram de
`situacao_datas_oferta` (por oferta); a mudança só alinhou a **lista de opções** ao mesmo calendário. Rodados e verdes:
`test_v3a_datas_lancadas` (14), `test_v3a_imprimir_coerente` (5), `test_frequencia_oferta`, `test_pauta_professor`,
`test_pauta_impressa_por_oferta`, `test_dias_semana`, `test_atividades_aula`, `test_valor_esportista`.

## 6. Ensaio (`pautaon_ensaio`, semente M1, **read-only — nada a desfazer**)

Turma 31 (`[ROTEIRO] Turma B - Dois Cursos`), ofertas **45** (grade seg/qua — `dia_semana` 0 e 2) e **46** (ter/qui —
1 e 3), ambas vigentes 01/08–31/12, professor 120 nas duas, hoje 29/10. Exercitado pelas rotas reais via test client
(login do professor 120):

- sem oferta escolhida → seletor = união da turma, sem marcas ✔/○;
- `?turma_curso=45` → só seg/qua (26 datas até hoje); nenhuma data de ter/qui;
- `?turma_curso=46` → só ter/qui; nenhuma data de seg/qua;
- `?turma_curso=45&data=<qui mais recente de 46>` → 200, a data some e o `selected` cai em `2026-10-28` (seg/qua mais
  recente de 45);
- POST (não enviado, para não escrever): as datas de 45 e 46 são subconjunto da união da turma, logo continuam aceitas
  pela validação.

Nenhuma gravação foi feita no banco de ensaio. Banco principal intocado.

## 7. Ruff / gates

`ruff --select F821,F811,F841 app/registros/core.py tests/test_seletor_data_oferta.py`: limpo. `git diff --check`: limpo.

## 8. Suíte completa

- **1001 → 1006 passed, 0 failed** (5 novos em `tests/test_seletor_data_oferta.py`; nenhum teste existente ajustado).
- **Falha observada numa primeira rodada** e explicada depois: `test_relatorios_observacoes.py::test_painel_pedagogico_tem_o_botao` marcou o rótulo do botão como ausente (a página ainda dizia "Diário de Observações", o teste já esperava "Diário de Bordo"). **Não é flake nem desta entrega:** era uma **edição de terceiros em andamento** no working tree (o renome do diário), que se completou minutos depois — verde na rodada completa seguinte (1006 passed). Nada nesta T2 toca `/relatorios/painel` nem `PeriodoLetivo`.
