# Painel do professor — rota legada `/professor/painel` unificada (29/10/2026)

Continuação de `docs/Relatórios/PainelProfessorRotaVoltar.md` (Solução A, aplicada no mesmo dia). Este documento registra a **Solução B**: a unificação de fato.

## Pedido

"Solução B agora. Siga o mesmo processo do anterior." — ou seja, transformar `registros.painel_professor` em redirect para a rota canônica, remover a montagem duplicada, ajustar os testes afetados, rodar as gates e documentar.

## O que a rota legada era

`/professor/painel` (`app/registros/core.py:194`) montava um contexto próprio para `dashboard/professor.html`: `turmas` (todas as ativas da unidade para admin/pedagógico/secretaria, ou as do professor para o professor), `total_alunos`, `lista_programas`, `programa_ativo` e `is_readonly`.

Conferido por leitura do template, **nenhum desses valores sustentava a página**, exceto `total_alunos`:

| Variável | Consumida em | Situação pela rota legada |
|---|---|---|
| `entradas` | `:36` (card "Minhas Turmas") e `:75` (tabela) | nunca era passada → 0 / "Nenhuma turma vinculada" |
| `aulas_pendentes` | `:140` (card da coluna direita) | nunca era passada → card ausente |
| `dias_bloqueados` | `:192` (card da coluna direita) | nunca era passada → card ausente |
| `total_alunos` | `:49` (card "Meus Alunos") | única que chegava, com regra pré-oferta |
| `turmas` / `lista_programas` / `programa_ativo` / `is_readonly` | — | o template não as lê |

Ou seja: a montagem duplicada produzia um painel com 1 card em 4 e um filtro de programa que não existia na tela. Não havia o que preservar.

## Correção aplicada (Solução B)

- `app/registros/core.py`: `painel_professor` passou a ser `redirect(url_for('main.painel'))`, com docstring explicando o porquê. Saíram ~60 linhas de montagem (duas consultas `select(Turma)`, filtro de programa e a contagem de alunos por `cond_inscricao_enturmada`) e os dois imports que só ela usava (`sqlalchemy.orm.joinedload` e `app.services.enturmado.cond_inscricao_enturmada`). A rota **continua existindo** — URLs antigas, favoritos e links externos não pegam 404.
- `app/templates/dashboard/index.html`: o card **"Abrir pauta"** do Painel Geral era o último link interno apontando para `/professor/painel`; para um gestor ele abria o template vazio do professor. Passou a apontar para `url_for('registros.frequencia')`, que é a própria pauta (o GET sem `turma_id` lista as turmas do perfil).

Sem migration, sem tabela nova, sem alteração de dados.

## Mudança de comportamento deliberada

A rota legada tinha o próprio guarda de papel (`ADMIN`, `PROFESSOR`, `PEDAGOGICO`, `SECRETARIA`), com flash "Permissões insuficientes" e redirect para `main.painel` nos demais. Quem decide o destino agora é `main.painel`:

| Perfil | Antes, por `/professor/painel` | Agora |
|---|---|---|
| professor | painel com "Meus Alunos" e o resto vazio | painel completo (mesmo do menu) |
| admin / gerência / pedagógico | template do professor com 1 card | painel gerencial (`dashboard/index.html`) |
| secretaria | idem, sem efeito do `is_readonly` | painel da secretaria |
| serviço social | flash de permissão + redirect | painel do serviço social |
| `pendente` | flash de permissão + redirect | tela de aguardando aprovação |
| papel desconhecido | flash de permissão + redirect | **403** |

É a coerência com o menu lateral que a Solução A já tinha assumido: cada perfil cai no painel do próprio perfil.

## Testes

- **Novo** `tests/test_painel_professor_legado.py` (4): redirect do professor com o painel **completo** ao seguir (`"Turma X — Curso X"` presente, `"Nenhuma turma vinculada"` ausente); redirect do gestor para o painel do perfil; exigência de login (sem sessão → `/login`); Painel Geral sem nenhuma referência a `/professor/painel` e com `href="/frequencia"` no card.
- **Ajustados** `tests/test_enturmado.py` (2, eram as duas quebradas pela unificação):
  - `test_caracterizacao_total_alunos_painel_professor`: o contrato passou a ser o redirect (`302` + `Location` `/painel`, destino sem o card "Meus Alunos"), e o **número 4** que ela fixava continua caracterizado em `ids_alunos_enturmados(unidade_id=...)` — a definição única que alimentava aquela montagem. A docstring original (antes 5 → depois 4) foi preservada.
  - `test_consumidores_migrados_equivalem_ao_servico`: o consumidor legado saiu da lista de equivalência (não existe mais) e entrou o contrato do redirect; as demais fontes (card de `/alunos`, `PeriodoLetivo.alunos_enturmados()`, `relatorios/shared`, BI ALU-008) seguem comparadas ao serviço.
- Regressão dirigida (`test_painel_professor_legado`, `test_enturmado`, `test_dashboard`, `test_dashboard_professor_pedagogico`, `test_conselho_professor`, `test_conselho_oferta`, `test_diario_observacoes_acesso`): **66 passed**.

Suíte completa: **1000 passed, 0 failed** (996 + os 4 testes novos; collect foi de 996 a 1000). Ruff em `app` (F821, F811, F841): limpo. Ficaram fora: os 9 `F841` pré-existentes em `tests/` — nenhum em arquivo desta entrega, conferido ao rodar o gate neles — e os 2 `F401` de `core.py` (`RegistroAula`, `User`), que já existiam no `HEAD` (reproduzidos via `git show`).

## Pendências

- ~~`app/templates/partials/sidebar.html` continua sendo partial legado (não incluído por nenhum template).~~ — **resolvido em 29/10/2026 (T3):** o partial foi **removido**; o menu de `base.html` é o único (MER §8.19, `docs/Relatórios/MenuUnicoSidebarLegado.md`).
- A regra pré-oferta de `Turma.professor_id` segue viva em outros pontos (pauta `/frequencia`, guardas por turma); a migração para a regra por oferta é decisão separada (I1 do backlog).
