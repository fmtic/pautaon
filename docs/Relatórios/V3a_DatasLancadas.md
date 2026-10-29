# V3a — Datas já lançadas na pauta de frequência + botão Imprimir coerente

Data: 29/10/2026 · Branch `nova_feature` · Sem push · Sem migration

## 1. Pedido

**(A)** No seletor "Data da Aula" da pauta (`app/templates/frequencia/lancar.html`), marcar em texto quais datas já foram
lançadas e quais estão pendentes, com resumo (`X de Y até hoje · Z pendente(s)`) e botão para a próxima pendente.
**(B)** Mostrar o botão "Imprimir" só quando a impressão é permitida.

## 2. P0 — estado inicial

- `git status` limpo; `HEAD = 4d40102` (`origin/nova_feature`), com os commits da sessão anterior (`bd2c54f`…`96543a3`)
  já integrados e **quatro commits novos do usuário** por cima (`5f3254c`, `cbbe75a`, `d05cbe3`, `4d40102`).
- **Suíte em HEAD: 940 passed, 1 failed** (941 testes) — a falha (`test_lancar_template_estrutura.py::test_render_nao_perde_textos`)
  vinha do `cbbe75a`, que reescreveu o aviso "Este conteúdo será arquivado no diário de classe". Corrigida em commit
  próprio (`5b47bb4`) **antes** da V3a (941 passed); a tarefa começou de base verde.

## 3. P1 — leitura e divergências do enunciado

### 3.1 Como a lista de datas é produzida

`GET /frequencia` (`app/registros/core.py`) → `carregar_contexto_turma(turma_id)` (`app/utils/logica.py:317`) →
`gerar_datas(turma, incluir_futuro=False, blocked_dates=...)` (`app/utils/logica.py:211`).

- `gerar_datas` usa `dias_da_turma(turma.id)` (`services/turma_curso_horario.py:229`), que é a **união dos dias das
  ofertas ATIVAS** da turma — não a grade de uma oferta.
- Com `incluir_futuro=False`, o limite é `min(turma.data_fim, hoje)`: **a lista nunca tem datas futuras** e volta do
  mais recente para o mais antigo (o template reordena com `datas|sort`).

**DIVERGÊNCIA 1 (registrada, não "consertada"):** o R1 do enunciado afirma que o seletor "continua listando TODAS as
datas, inclusive futuras". No código real **não há datas futuras** na pauta. Consequências: o estado "futura sem
marca" e o caso "data futura já lançada recebe ✔" **nunca ocorrem** na tela. A regra foi implementada de forma
genérica (o helper devolve `lancada` para data futura completa), então se a lista ganhar futuras um dia o
comportamento já é o pedido. **Nada foi adicionado nem removido do seletor.**

**DIVERGÊNCIA 2 (registrada):** o R6 diz "tudo é por OFERTA", mas a lista de datas é da **turma** (união). Numa turma
com 2+ ofertas o seletor mostra as datas das duas (ex.: seg/qua da oferta A + ter/qui da oferta B). Decisão tomada:
**só recebem marca as datas que pertencem ao calendário da oferta** (`datas_aula_oferta`); as datas da outra oferta
ficam sem marca — e `Y`/`Z` contam somente as aulas da oferta. Isso mantém `Z` igual às pendências do dashboard e
evita marcar como "pendente" uma aula que não existe na oferta.

### 3.2 Definição de "lançada" usada (R3)

`app/utils/frequencia.py`:

- `frequencias_lancadas(turma_id, data, aluno_ids, turma_curso_id=None)` conta linhas de `frequencia` com
  `conceito IS NOT NULL` para os alunos da pauta (na data e, quando informado, na oferta).
- `contar_pendencias_frequencia` / `_pendencias_por_ofertas` chamam esse helper e consideram a aula **pendente**
  quando `lancados < len(aluno_ids)`.

**Definição adotada:** uma data está **lançada** quando **todos** os alunos da pauta da oferta têm conceito registrado;
caso contrário, **pendente**. Nenhuma definição nova. Não há TRAVA neste ponto: a pauta só grava o que for marcado e
todos os alunos da pauta podem receber frequência (`pode_receber_frequencia = insc.ativo` da própria inscrição na
oferta, `core.py:521`), portanto "salvo na pauta" e a regra do dashboard coincidem para a data completa.

### 3.3 Outras telas

"Data da Aula" existe **somente** em `frequencia/lancar.html` (nenhum outro template tem o rótulo). Nada mais foi
alterado.

### 3.4 "Hoje" local

`app/utils/timezone.py::get_local_now().date()` — mesma função usada por `_pendencias_por_ofertas`.

## 4. Implementação

### 4.1 Serviço (Parte A)

`app/utils/frequencia.py::situacao_datas_oferta(turma, oferta)`:

```
{ "status": {ISO: "lancada" | "pendente"},   # datas do calendário da oferta
  "lancadas": X, "total_ate_hoje": Y, "pendentes": Z,   # Z = Y - X
  "proxima_pendente": ISO | None }                     # a pendente mais antiga
```

- Pauta: `_alunos_da_oferta(turma.id, oferta.id)`; calendário: `datas_aula_oferta(oferta, blocked=...)`
  (vigência + grade da oferta, feriados do período descontados).
- **Uma** consulta agregada: `SELECT data, count(DISTINCT aluno_id) FROM frequencia WHERE data IN (...) AND
  aluno_id IN (...) AND conceito IS NOT NULL AND <escopo> GROUP BY data`.
- **D2 (legado):** quando a oferta é a **única ativa** da turma (`ofertas_unicas_ativas`), linhas com
  `turma_curso_id IS NULL` contam como dela.

### 4.2 GET /frequencia (Partes A e B)

- `situacao_datas` só é calculado quando há oferta selecionada e **não** é `exigir_escolha` (R6); turma sem oferta
  ativa (legado) também não marca nada.
- `dias_abrev` = `{ISO: "Seg"}` via `weekday_para_abrev` (mesma fonte dos formulários).
- `pode_imprimir_pauta` (Parte B): falso com 2+ ofertas e nenhuma escolhida (todos os perfis) e, para PROFESSOR,
  quando `oferta_atual is None` ou `professor_da_oferta(oferta_atual, current_user)` é falso — **a mesma regra** da
  guarda de `imprimir_pauta` (PARTE B/G1), sem regra nova.

### 4.3 Template

- Opções: `✔ dd/mm/aaaa (Dia)`, `○ dd/mm/aaaa (Dia) — pendente`, ou o texto de antes (`dd/mm/aaaa`) quando não se
  aplica. Marca em **texto** (não em cor), texto sempre escapado pelo Jinja.
- Abaixo do seletor: `X de Y aulas até hoje lançadas · Z pendente(s)` ou `Todas as aulas até hoje estão lançadas ✔`;
  botão `Ir para a próxima pendente` → `?turma_id=…&turma_curso=…&data=…` (a mesma navegação de `atualizarUrl()`),
  ausente quando `Z = 0`.
- O bloco inteiro do dropdown "Imprimir Pauta" foi envolvido por `{% if pode_imprimir_pauta %}`; os links já levavam
  `turma_curso` sempre que havia oferta.

## 5. R11 — o que `turmas/detalhe.html` faz (não alterado)

- **Com 2+ ofertas ativas:** cada item do dropdown leva `turma_curso=o.id`; o professor que não é o daquela oferta
  recebe **403** ao abrir os meses/a pauta completa da oferta alheia (e 200 na dele).
- **Com 0 ou 1 oferta ativa:** os links vão **sem** `turma_curso` (`detalhe.html:53,63`) → a rota resolve a oferta
  ativa (uma) ou a de **menor id** e, se o professor não for o dela, **403**.
- Ou seja: o detalhe da turma continua podendo levar a um 403 — reportado, **fora do escopo** por decisão do
  enunciado ("NÃO alterar; apenas reportar").

## 6. Testes

`tests/test_v3a_datas_lancadas.py` (12):

1. `test_marcas_lancada_pendente_e_resumo` — ✔ na lançada, ○ na seguinte, X/Y/Z e `proxima_pendente`.
2. `test_pendente_quando_falta_um_aluno` — data com 1 de 2 alunos continua pendente.
3. `test_z_zero_quando_tudo_lancado` — `Z = 0`, `proxima_pendente = None`, mensagem "Todas as aulas…" e **sem** botão.
4. `test_ofertas_independentes` — lançamento na oferta A não aparece na B (nem contagem, nem data).
5. `test_legado_d2_conta_na_oferta_unica` — linha `turma_curso_id` NULL conta na oferta única ativa.
6. `test_legado_d2_nao_conta_com_duas_ofertas` — com 2 ativas a mesma linha **não** conta.
7. `test_contagem_consistente_com_pendencias_do_dashboard` — `Z` == laço de `frequencias_lancadas` +
   `datas_esperadas_oferta` para a mesma oferta.
8. `test_selects_constantes_com_2_e_10_datas` — nº de SELECTs igual com 2 e com 10+ datas da oferta.
9. `test_html_mostra_marks_resumo_e_botao` — ✔/○ com data e dia da semana, resumo e `data=` da pendente mais antiga.
10. `test_html_sem_oferta_escolhida_nao_mostra_marcas` — 2+ ofertas sem escolha: sem `✔`, sem "— pendente", sem resumo.
11. `test_html_apos_salvar_a_data_aparece_lancada` — `POST /frequencia` → GET mostra ✔ na data salva (R7).
12. `test_html_demais_campos_preservados` — demais campos da pauta intactos.

`tests/test_v3a_imprimir_coerente.py` (5):

13. visível para o professor da oferta, com `turma_curso` no link;
14. oculto para professor que não é o da oferta;
15. oculto sem oferta escolhida em 2+ ofertas (professor, admin, secretaria);
16. visível para admin/secretaria/pedagógico (com `turma_curso`);
17. oculto para professor em turma sem oferta ativa (o print daria 403).

**Teste existente ajustado (antigo × novo × motivo):**

| teste | antigo | novo | motivo |
|---|---|---|---|
| `test_lancar_template_estrutura.py::test_render_nao_perde_textos` | `"Este conteúdo será arquivado no diário de classe"` | `"O conteúdo de atividades e observações será arquivado"` | o `cbbe75a` (reorganização do layout de lançamento, do próprio repositório) reescreveu o aviso e deixou a suíte vermelha **antes** da V3a |

Nenhum outro teste existente foi alterado. Suíte: **940 passed + 1 failed em HEAD → 941 (fix do `cbbe75a`) → 958 passed** (941 + 12 + 5 novos).

## 7. P6 — ensaio (`pautaon_ensaio`, desfeito)

Semente M1, turma 31 (professor 120), login `professor.m1@roteiro.local` por `POST /login`.

Alvo conferido antes de qualquer escrita: `host=localhost`, `database=pautaon_ensaio`, `alembic_version =
c8d9e0f1a2b3` (o `scripts/ensaio_shell.ps1 -Diagnostico` falhou nesta sessão com erro de citação do PowerShell —
`File "<string>", line 9` —, então o alvo foi impresso e validado pelo próprio driver, sem `DATABASE_URL` na sessão).

| oferta | pauta | aulas ≤ hoje (Y) | lançadas (X) | pendentes (Z) | marcas conferidas |
|---|---|---|---|---|---|
| 45 (seg/qua) | 2 | 26 | 2 | 24 | ✔ 03/08 e 10/08; ○ 05/08, 12/08, **17/08** (17/08 tem só 1 dos 2 alunos → pendente) |
| 46 (ter/qui) | 2 | 26 | 1 | 25 | ✔ 04/08; ○ 06/08, 11/08 (1/2), 13/08, 18/08, 20/08 |

- Contagem SQL independente (join `frequencia`×`inscricoes` por oferta) **idêntica** aos números da tela.
- `?turma_id=31` (2+ ofertas, sem escolha): **sem** marcas, **sem** resumo e **sem** botão Imprimir.
- Botão Imprimir presente nas duas ofertas do professor (`turma_curso=45|46` no link).
- `POST /frequencia` em 05/08/2026 (oferta 45, 2 alunos com conceito A) → a opção passa a
  `✔ 05/08/2026 (Qua)` e o resumo a `3 de 26 aulas até hoje lançadas · 23 pendente(s)`; SQL: 3. **R7 comprovado.**
- Limpeza: `frequencia` e `registro_aula` da data apagados (turma 31 voltou às 8 linhas originais; 0 linhas na data).
  Restaram 2 linhas de `log_acao` do próprio acesso/salvamento — log de auditoria não é apagado.
- Banco principal (`pautaon`) **intocado**.

## 8. Desvios e pendências

1. **Divergência 1** (sem datas futuras no seletor) e **divergência 2** (lista de datas é da turma, não da oferta):
   registradas na seção 3; a tarefa foi implementada de forma coerente com o código real e sem esconder nenhuma data.
   Se a intenção era **listar também as datas futuras** na pauta, isso é uma mudança de comportamento do seletor
   (`incluir_futuro=True`) — não feita por não estar autorizada.
2. **Datas do seletor fora do calendário da oferta** ficam sem marca (ex.: 26 datas marcadas de 52 opções no ensaio,
   porque metade é da outra oferta). Uma melhoria futura seria filtrar o seletor pela oferta escolhida.
3. **`turmas/detalhe.html`**: continua podendo gerar 403 para professor que não é o da oferta (seção 5), conforme
   decidido no enunciado.
4. **Pendências abertas de tarefas anteriores** (G1/P2: obrigatoriedade do professor na oferta e saneamento das
   ofertas 16/17/18/19 do principal e 50 do ensaio) seguem aguardando decisão — não foram tocadas aqui.
