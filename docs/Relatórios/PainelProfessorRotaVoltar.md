# Painel do professor — pendências em 2 linhas e botão "Voltar" do conselho (29/10/2026)

## Pedido

Na tela de avaliação coletiva do conselho (`conselho/turma_aval.html`), o botão **Voltar ao Painel** abria o painel do professor **sem os dados** — enquanto o item **Painel Geral** da lateral mostrava tudo corretamente. O pedido era analisar a rota antes de corrigir.

## Diagnóstico (P1)

Não havia rota quebrada: existem **duas rotas servindo o mesmo template** `dashboard/professor.html`, com contextos diferentes.

| Rota | Endpoint | Contexto entregue ao template |
|---|---|---|
| `/painel` | `main.painel` → `render_dashboard_professor()` | `entradas`, `aulas_pendentes`, `dias_bloqueados`, `total_alunos` (por **oferta**) |
| `/professor/painel` | `registros.painel_professor` (`app/registros/core.py:194`) | `turmas`, `total_alunos`, `lista_programas`, `programa_ativo`, `is_readonly` — **sem** `entradas`, `aulas_pendentes` e `dias_bloqueados` |

O template consome o contexto da rota canônica:

- `dashboard/professor.html:36` → `{{ entradas|length }}` no card **Minhas Turmas**;
- `dashboard/professor.html:75` → `{% for e in entradas %}` na tabela;
- `dashboard/professor.html:140` e `:192` → `{% if aulas_pendentes %}` / `{% if dias_bloqueados %}` (cards da coluna direita).

Com a rota legada, essas variáveis são `Undefined` na Jinja: `|length` = 0 e o loop cai no `{% else %}`. Resultado observado: **“Minhas Turmas: 0”**, tabela “Nenhuma turma vinculada” e nenhum card lateral. O `total_alunos` da rota legada também é calculado por `Turma.professor_id` (regra pré-oferta), então “Meus Alunos” pode divergir do valor canônico.

O mesmo defeito já havia sido registrado em `docs/Relatórios/DIARIO_ObservacoesAcesso.md` §6, onde o “Voltar” do Diário de Bordo foi corrigido — `turma_aval.html` e `conselho.py` ficaram para trás.

## Correção aplicada (Solução A — menor risco)

- `app/templates/conselho/turma_aval.html`: o botão **Voltar ao Painel** passa a usar `url_for('main.painel')`.
- `app/conselho.py`, em `avaliar_turma`: os dois redirects (o do POST de “Salvar Avaliação” e o do caso “turma sem oferta ativa”) passam a usar `url_for('main.painel')`.

Nenhuma migration, tabela, coluna ou dado alterado. Nesta entrega a rota legada **não** foi removida nem redirecionada — foi no mesmo dia, na Solução B abaixo.

## Solução B (aplicada no mesmo dia — ver `PainelProfessorRotaUnificada.md`)

Unificação de vez: `registros.painel_professor` virou `redirect(url_for('main.painel'))` e a montagem duplicada (~65 linhas) foi removida. O que havia impedido fazer junto, e como ficou:

- `tests/test_enturmado.py:218` e `:371` exercitavam a rota legada esperando **200** e o número em “Meus Alunos” → passaram a testar o contrato do redirect, com o número caracterizado na definição única (`app.services.enturmado`) que alimentava aquela montagem.
- A rota legada atendia admin/pedagógico/secretaria com o template do professor; `main.painel` roteia por perfil e manda os gestores para o painel gerencial. Adotou-se o comportamento do menu, que é o coerente — a tela que aqueles perfis abriam pela rota legada estava vazia de qualquer forma.

## Card “Frequências Pendentes” (tarefa que estava no working tree)

O commit `e5428c2` trouxe para o histórico a alteração que estava apenas no working tree e a completou:

- o card exibe as **2 primeiras** pendências (`limite_pendentes`);
- o mesmo valor alimenta o aviso do rodapé — antes o aviso calculava sobre 5 e, com 2 linhas exibidas, informava um número errado de dias ocultos;
- 2 testes de dashboard ajustados ao novo contrato, ambos **sem perda do comportamento verificado**:
  - `tests/test_h4_leitores_grade_variavel_smoke.py`: assere as 2 linhas exibidas (04/03 quarta e 09/03 segunda), mantendo a prova de que o intervalo vem do weekday na grade não uniforme; comentário corrigido (o seed lança 02/03 e **06/03**, não 04/03);
  - `tests/test_leitores_grade_h3e.py`: assere as 2 primeiras linhas (02/03, T-MULTI e T-UNI); a variação da hora pelo weekday continua coberta por `test_pendencia_usa_o_intervalo_do_weekday_da_data`.

## Testes

Asserções novas em testes existentes (nenhum arquivo de teste novo):

1. `tests/test_conselho_professor.py::test_avaliacao_da_oferta_abre_e_grava_para_o_professor` — `href="/painel"` no GET e `Location` terminando em `/painel` no POST;
2. `tests/test_conselho_oferta.py::test_avaliar_turma_sem_oferta_recusa` — `Location` terminando em `/painel`.

Regressão dirigida (conselho + UI + perguntas + oferta): **53 passed**.

Suíte completa: **996 passed, 0 failed** (o collect permanece em 996; as novas asserções entraram em testes já existentes).

## Banco de dados (migration pendente do certificado)

`flask db upgrade` no principal foi aplicado neste mesmo dia, com o protocolo de migration:

- backup `instance/backups/pautaon_pre_modelo_certificado.sql`;
- 36 tabelas / **2947** linhas antes e depois — a única diferença é a tabela nova `modelo_certificado` (0 linhas);
- `\d modelo_certificado` conferido (PK, UNIQUE `uq_modelo_certificado_periodo_centro` e as duas FKs);
- `downgrade c8d9e0f1a2b3` + `upgrade` reaplicados; revisão final `e1f2a3b4c5d6 (head)`.

## Pendências

- ~~Solução B (unificar `/professor/painel` com `main.painel`)~~ — **aplicada no mesmo dia**; ver `docs/Relatórios/PainelProfessorRotaUnificada.md` e o MER §8.18.
- ~~`app/templates/partials/sidebar.html` continua sendo partial legado (não incluído por nenhum template).~~ — **resolvido em 29/10/2026 (T3):** o partial foi **removido**; o menu de `base.html` é o único (MER §8.19, `docs/Relatórios/MenuUnicoSidebarLegado.md`).
