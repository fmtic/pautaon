# V3b — "Engajamento da turma" no dashboard do professor

**Data:** 28/10/2026 · **Branch:** `nova_feature` · **Head Alembic:** `c8d9e0f1a2b3` (sem migration)
**Suíte:** 923 → **941 passed** (18 novos; **nenhum teste existente alterado**)

---

## P1 — leitura (sem editar)

### Onde o bloco vive

O briefing indica `app/templates/dashboard/professor.html`, "aba Painel Pedagógico". Na prática as duas abas do
dashboard do professor são **páginas separadas**:

- `dashboard/professor.html` → aba **Visão Geral** (`main.painel`, `render_dashboard_professor`);
- `dashboard/painel_pedagogico.html` → aba **Painel Pedagógico** (`main.painel_pedagogico_professor`,
  `render_painel_pedagogico_professor` em `app/main/dashboard_professor.py:362`), que é onde está o gráfico
  "Evolução de Assiduidade Aula a Aula".

O bloco foi implementado em **`dashboard/painel_pedagogico.html`** (o comportamento descrito — "abaixo do
gráfico" — só existe lá). **Desvio de caminho**, sem impacto de comportamento.

### Como a oferta é resolvida

`render_painel_pedagogico_professor` lê `turma_id` e `turma_curso`/`turma_curso_id` da querystring e chama
`estatisticas_professor.obter_estatisticas_professor(user_id, turma_id, turma_curso_id)`, que:

1. monta `entradas = _entradas_professor(user_id)` — **só** ofertas ativas de turmas ativas em que o usuário é o
   `turma_curso.professor_id` (mais o ramo legado de turma sem oferta ativa);
2. escolhe a entrada pelo par (`turma_id`, `turma_curso_id`) e, **se não casar, usa `entradas[0]`**;
3. devolve `entrada_selecionada` (dict com `turma` e `turma_curso_id`).

### Como o gráfico recebe os dados / troca de filtro

- Gráfico: Chart.js 4.4.7 (CDN, já carregado pela página) com dados **renderizados no servidor**
  (`{{ evolucao_temporal|tojson }}` → `#chartEvolucao`).
- Filtro: `<form method="get">` com `<select name="turma_selecionada" onchange="navegarTurma(this.value)">`; a
  função faz `window.location.href = '/professor/painel-pedagogico?turma_id=...&turma_curso=...'`.

**Decisão: recarga por GET (renderização no servidor).** É a opção que **menos altera** o código atual — o
filtro já recarrega a página, e não foi preciso endpoint JSON nem JS novo.

### TRAVAs

1. **Filtro com "Todas"/sem oferta?** **Não.** As opções são exatamente as entradas do professor
   (`turma_id:turma_curso_id`); o `<option value="">` só existe no `{% else %}` do laço, como
   "Nenhuma turma vinculada". Quando o parâmetro não casa, o serviço cai em `entradas[0]` — sempre uma oferta
   concreta. Nada a perguntar.
2. **O painel serve outros perfis?** **Sim:** a rota aceita `professor`, `admin`, `gerencia` e `pedagogico`.
   **Guarda mantida exatamente como estava** — nenhuma permissão foi alterada; para quem não tem ofertas a
   página segue no estado vazio (sem o bloco).

## P2/P3 — implementação

### Serviço `app/services/engajamento_turma.py` (novo)

`valores_mais_atribuidos(turma_id, turma_curso_id, limite=3) -> {"itens": [...], "total": int}` com itens
`{"nome", "quantidade", "percentual"}`.

- **Uma** consulta agregada: `SELECT valor.nome, COUNT(frequencia.id) FROM frequencia JOIN valor_esportista …
  WHERE valor_esportista_id IS NOT NULL AND <escopo> GROUP BY valor.id, valor.nome` — o `total` é a soma de
  **todas** as linhas do agrupamento (o top 3 é recortado depois).
- Ordenação: quantidade **desc**, empate pelo **nome** (alfabético, `casefold` para ser determinístico entre
  SQLite e PostgreSQL).
- **D2 do legado:** `_condicoes_do_escopo` usa `ofertas_unicas_ativas([turma_curso_id])`; quando a oferta é a
  única ativa da turma, soma também as linhas com `turma_curso_id IS NULL`. Nenhuma regra nova.
- `turma_curso_id=None` (entrada legada, turma sem oferta ativa) → conta as linhas da turma.
- Valor **inativo** já lançado entra normalmente (o JOIN não filtra `ativo`).
- Nunca devolve dado por aluno.

### Rota e template

- `render_painel_pedagogico_professor`: monta `engajamento` a partir de `stats["entrada_selecionada"]` e passa
  no contexto (inclusive no caminho de erro, com a estrutura vazia).
- `dashboard/painel_pedagogico.html`: card `#engajamento-turma` inserido **entre o gráfico e a tabela
  "Rendimento e Assiduidade por Aluno"** — título "Engajamento da turma", subtítulo "Valores/Posturas do
  Esportista mais atribuídos", cada valor com nome, contagem, percentual e `progress` do Bootstrap, rodapé
  "Baseado em N registros de presença com valor." e o estado vazio "Ainda não há valores registrados nesta
  oferta.". Nenhum bloco existente foi alterado.

## P4 — testes (`tests/test_v3b_engajamento_turma.py`, 18)

Serviço: ordenação decrescente; empate pelo nome; menos de 3 valores; nenhum valor; percentual sobre o total da
oferta (5 valores, top 3 com 36.4% / 27.3% / 18.2% de 11); oferta A não vê dados da oferta B; legado D2 entra na
oferta única; legado D2 **não** entra com 2+ ofertas; valor inativo já usado aparece; SELECTs constantes com 2 e
com 8 valores (listener `before_cursor_execute`).

HTML/rota: bloco abaixo do gráfico (`index("chartEvolucao") < index("Engajamento da turma")`) e blocos
existentes preservados; estado vazio; rodapé com total e percentual; escape do nome (`<b>Liderança</b>` sai como
texto); **nenhum nome de aluno** dentro do bloco; o bloco muda com o filtro (oferta 1 × oferta 2); pedir a
oferta de **outro professor** cai na entrada do próprio professor (sem vazar dado); professor de **outra
unidade** não vê o dado (cai na entrada dele, sem valores).

**Testes existentes alterados: nenhum.**

## P5 — ensaio (`pautaon_ensaio`, semente M1, desfeito)

Alvo conferido com `scripts/ensaio_shell.ps1 -Diagnostico` (`postgresql+psycopg://postgres:***@localhost:5432/pautaon_ensaio`,
revisão `c8d9e0f1a2b3`). Driver `.tmp/v3b_ensaio.py` (fora da entrega), tudo pelas rotas reais:

1. `secretaria.m1@roteiro.local` → `POST /planejamento` (`tipo_post=valor`) criou 3 valores `[V3b] …` na
   unidade 13;
2. `professor.m1@roteiro.local` → `POST /frequencia` na turma 31, ofertas **45 (B1)** e **46 (B2)**, em datas
   **sem nenhuma frequência** (escolhidas no calendário da turma e compatíveis com a grade da oferta);
3. leitura por HTTP de `/professor/painel-pedagogico`:

| Consulta | Bloco |
| --- | --- |
| `turma_id=31&turma_curso=45` (B1) | `[V3b] Colaboração` 2 (66.7%), `[V3b] Respeito` 1 (33.3%) — total 3 |
| `turma_id=31&turma_curso=46` (B2) | `[V3b] Empatia` 2 (100.0%) — total 2 |
| `turma_id=30&turma_curso=44` (sem valores) | "Ainda não há valores registrados nesta oferta." |

4. **contagem SQL independente**: oferta 45 → `Colaboração 2, Respeito 1`; oferta 46 → `Empatia 2` — idêntica ao
   bloco;
5. **limpeza**: frequências e registros de aula criados foram removidos (só os que não existiam antes) e os 3
   valores apagados; os contadores voltaram ao estado inicial (frequência com valor `[]`, 2 registros de aula, 0
   valores na unidade). Banco principal **intocado**.

## Desvios

1. **Caminho do template:** o bloco entrou em `dashboard/painel_pedagogico.html` (página da aba "Painel
   Pedagógico"), não em `dashboard/professor.html` (aba "Visão Geral"), porque o gráfico citado só existe na
   primeira.
2. `js` não foi necessário: a troca de filtro já é GET.
3. Nenhum outro desvio.
