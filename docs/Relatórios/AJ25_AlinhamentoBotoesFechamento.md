# AJ25 — Alinhamento da barra de botões do `/conselho/fechamento/`

**Data:** 20/11/2026 · **Branch:** `nova_feature` · **Commit/push/merge:** nenhum (conforme solicitado) · **Schema/migration:** nenhuma

## Motivação

A barra do topo do fechamento tinha contêiner sem `gap`/`flex-wrap`, wrapper de botões sem classes (botões colados), `btn-dark` (único uso no projeto) e ícones com `me-2`. A tarefa alinha esse cabeçalho ao padrão visual já usado nas demais telas, sem alterar rótulos, ícones, `onclick`, comportamento, impressão, tabela, rotas ou regra de negócio.

## Descoberta — telas-modelo

Varredura de `app/templates/**/*.html` por `d-flex`, `justify-content-between`, `align-items-center`, `gap-`, `flex-wrap`, `btn-primary`, `btn-outline-*`, `btn-sm`, ícones `bi-*` e `d-print-none`; conferência de CSS global (`style.css`) por classes de cabeçalho reutilizáveis.

| Tela-modelo | Trecho / linhas | O que foi adotado |
| --- | --- | --- |
| `app/templates/relatorios/geral.html` (principal) | 11–27 | `d-flex flex-wrap justify-content-between align-items-center mb-4 gap-3` no contêiner; grupo `d-print-none d-flex gap-2 flex-wrap`; botões tamanho normal, ícone + texto com `me-1`; imprimir como `btn-outline-secondary`, exportar com ícone de planilha, ação principal em `btn-primary`; título em `<div>` com `<h2>` + subtítulo `text-muted small mb-0` |
| `app/templates/conselho/perguntas.html` | 59–68 | Mesmo contêiner externo (`flex-wrap` + `gap-3`) no domínio do conselho; `h2.fw-bold.mb-1` com ícone `me-2`; botão `btn-primary` sem `btn-sm` |
| `app/templates/turmas/listar.html` | 4–20 | Wrapper interno `d-flex gap-2`; `btn-outline-secondary` para Imprimir; ícones `me-1`; ordem com a ação principal por último |

Modelos secundários conferidos: `frequencia/relatorio.html` (`btn-outline-secondary btn-sm d-print-none`, ícone `me-1`), `planejamento/planejamento.html` (mesmo par externo/interno), `conselho/painel.html` e `relatorios/resultado_conselho.html`.

O padrão é **utilitário Bootstrap**, não uma classe CSS global: não existem `.page-header`, `.toolbar` ou `.actions` aplicáveis ao fechamento (as classes `.actions`/`.toolbar` existem apenas em folhas locais que `fechamento.html` não carrega). `btn btn-dark` aparece apenas no fechamento; por isso foi substituído pelo `btn-outline-secondary` dos modelos.

## Arquivos alterados

- `app/templates/conselho/fechamento.html` — barra de ações (linhas 33–57 após a alteração).
- `tests/test_aj25_botoes_fechamento.py` — novo, 2 testes de renderização/estrutura.
- `tests/test_aj23_impressao_fechamento_conselho.py` — uma asserção desatualizada corrigida (ver "Decisões").
- `docs/Relatórios/AJ25_AlinhamentoBotoesFechamento.md` — este relatório.

Nenhum CSS novo foi necessário em `app/static/css/conselho/conselho.css`.

## Decisões

- **Estrutura:** contêiner `d-flex flex-wrap justify-content-between align-items-center mb-4 gap-3 d-print-none`; grupo `d-flex gap-2 flex-wrap justify-content-end ms-auto d-print-none` — os botões ficam à direita tanto na linha do título quanto quando a barra quebra em telas estreitas; sem `btn-sm` (coerente com os modelos de 3 botões).
- **Título e curso:** o texto `Curso: {{ oferta.curso.nome }}` estava inline no `<h2>` e, com o curso longo da tela de demonstração, empurrava os botões para a linha seguinte mesmo em 1440px. Passou a subtítulo (`<p class="text-muted small mb-0">`) dentro do `<div>` do título, exatamente como `relatorios/geral.html`; o `<h2>` passou a `h4` (mesmo tamanho visual dos modelos) com `mb-0`. Assim título e botões ficam na mesma linha em desktop, e o texto do curso continua visível logo abaixo.
- **Botões:** ordem preservada (Imprimir → Exportar .CSV → Salvar Fechamento), com `Salvar Fechamento` como ação principal em `btn-primary`. `Imprimir`: `btn-dark` → `btn-outline-secondary`; `Exportar .CSV`: `btn-outline-success` mantido. Ícones `bi-printer`, `bi-file-earmark-excel` e `bi-save` inalterados; só o espaçamento passou de `me-2` para `me-1` (padrão dos modelos). `me-2` permanece apenas no ícone do título.
- **`onclick` intactos:** `prepararImpressao()`, `exportTableToCSV('{{ turma.nome }}.csv')` e `salvarFechamento()` — nenhum comportamento foi tocado.
- **Impressão:** `d-print-none` continua no contêiner (e também no grupo), e nenhuma regra de `@media print` foi alterada.
- **Ajuste de teste AJ23 (sem efeito em produção):** o teste `test_renderizacao_tem_foto_oculta_spans_cabecalho_e_rodapé` esperava o rótulo `Impresso por:` no rodapé, mas o template já trazia `v {{ app_version }}-{{ app_stage }}` **antes do início da AJ25** (essa alteração de rodapé não é desta tarefa). A asserção foi atualizada para aceitar a versão, sem modificar o template.

## Verificação

### Testes automatizados

- Novo arquivo: 2 testes (renderização com os 3 botões/`onclick`/ícones/`d-print-none`; estrutura das classes e variantes).
- Foco AJ25 + AJ23: **6 passed**.
- `python -m ruff check` e `git diff --check`: limpos.
- Suíte completa: **1935 passed, 1218 warnings in 1394.39s (0:23:14)**.

### Conferência em navegador

Base SQLite isolada em `%TEMP%`, servidor local na porta 5099, login na tela e abertura de `/conselho/fechamento/1?oferta_sel=1`. Medição de geometria no navegador e em Chrome headless:

| Largura da janela | Resultado |
| --- | --- |
| 1440 px | Barra em uma linha: título (412 px) à esquerda, grupo de botões (455 px) à direita; `gap` 16 px externo e 8 px interno; sem overflow horizontal |
| 1000 px | Mesma linha; título 400 px + botões 455 px; sem overflow |
| 480 px | Quebra controlada: título na primeira linha; na segunda, `Imprimir` e `Exportar .CSV` alinhados à direita; `Salvar Fechamento` também à direita na terceira linha. Sem corte nem rolagem horizontal |

Sem erros de console relevantes à barra. A impressão foi comparada com o estado imediatamente anterior à AJ25: mesmo número de páginas (4, A4 paisagem), `thead` repetido, 30 alunos, nenhum botão no PDF e **texto idêntico após normalizar data/hora**. (O PDF antigo da própria AJ23 difere apenas no rodapé — `Impresso por:` → versão — alteração já presente antes desta tarefa.)

## Pendências

- Nenhuma pendência funcional neste escopo.
- Alterações de AJ23 e AJ25 permanecem na árvore de trabalho, sem commit/push/merge.
