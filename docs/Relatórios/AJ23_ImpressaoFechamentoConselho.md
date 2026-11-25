# AJ23 — Impressão da tela `/conselho/fechamento/`

**Data:** 20/11/2026 · **Branch:** `nova_feature` · **Base:** `8900014` (AJ24-B) · **Commit/push/merge:** nenhum (conforme solicitado) · **Schema/migration:** nenhuma

## Motivação

A listagem de alunos do fechamento do conselho tinha uma implementação de impressão parcial (A4 paisagem e rodapé), mas sem cabeçalho institucional, com a foto do aluno na folha, sem repetição garantida de `thead`, sem bordas finas consistentes e sem sincronização dos textos de impressão quando o usuário usa Ctrl+P. Este ajuste alinha a tela ao padrão dos relatórios já existentes, sem tocar regra de negócio, rotas, banco ou migrations.

## Descoberta (antes de alterar)

Varredura de `templates/**/*.html`, `static/css/**/*.css` e `static/js/**/*.js` por `print-footer-container`, `@media print`, `d-print-none`, `@page`, `page-break-inside`/`break-inside`, `table-header-group`, `print-color-adjust` e cabeçalho institucional (`logo_secundaria_url`, `nome_instituicao`).

**Modelo escolhido (arquivos usados como referência):**

| Arquivo | O que foi tomado como padrão |
| --- | --- |
| `app/templates/conselho/imprimir_formulario.html` | `@page` paisagem, thead repetido (`table-header-group`), `break-inside`/`page-break-inside`, tipografia e rodapé |
| `app/templates/conselho/_resumo_cabecalho.html` | logo institucional + instituição + título + turma/período + emissão/colaborador (padrão AJ21) |
| `app/static/css/turmas/carga_horaria_curso.css` | cabeçalho claro com borda inferior escura, tabela 8.5pt, bordas `1px solid #adb5bd`, rodapé 7.5pt cinza |

Modelos secundários conferidos: `frequencia/imprimir_pauta.html`, `turmas/imprimir_listar_turma.html`, `alunos/historico.css`, `planejamento/impressao_temas.css` e o `@media print` global de `static/css/style.css`. O padrão "mais recente e comum" nos relatórios tabulares é o conjunto acima; o AJ21 já havia decidido **nenhuma foto de aluno** em relatórios do conselho (`docs/Relatórios/AJ21_ResumoConselho.md`).

Leitura dos arquivos alvo: `conselho.css` já tinha um bloco de impressão com A4 paisagem/1cm/10pt, mas sem `thead` repetido, sem bordas explícitas e forçando fundo escuro; `conselho.js` tinha `prepararImpressao()` que sincronizava os spans, porém chamado apenas pelo botão — sem `beforeprint`, então o Ctrl+P podia imprimir valores velhos.

## Implementação

1. **Cabeçalho de impressão** em `fechamento.html`: `<header class="print-only report-header fechamento-print-header">` com `informacao_padrao.logo_secundaria_url`, `nome_instituicao`, título "Conselho da Turma — Fechamento", curso, turma, período letivo, "Emitido em" e colaborador. A data é preenchida pelo mesmo `toLocaleString("pt-BR")` do rodapé, mantendo os dois valores idênticos.
2. **Foto**: `d-print-none` + classe `foto-aluno-fechamento` no `<img>` e regra explícita `display: none !important` no CSS de impressão; `me-3` removido e o bloco do nome passou a ocupar 100% da célula (`fechamento-aluno-linha` / `fechamento-aluno-nome`). Na tela a foto continua visível.
3. **Tabela**: `#tabelaFechamento` com `font-size: 8.5pt`, `border-collapse`, thead claro (`#f1f3f5`, texto `#212529`, borda inferior `#343a40`), bordas finas em `th`/`td`, `thead { display: table-header-group }`, `break-inside`/`page-break-inside: avoid` nas linhas. Sem fundo escuro na impressão.
4. **Badges de conceitos (A/B/C/D/F/J)**: fundo branco, texto `#212529`, borda `1px solid #212529` e negrito — legíveis em P&B sem depender de cor de fundo.
5. **Spans dos selects**: `situacao-texto`, `proxima-texto` e `nivel-texto` continuam sendo preenchidos pela seleção **atual** (prioritária sobre `legado_nome` quando há valor escolhido). `prepararImpressao()` continua chamando `sincronizarSpans()` antes de `window.print()` e foi acrescentado `window.addEventListener('beforeprint', sincronizarSpans)` para cobrir Ctrl+P/menu do navegador e alterações ainda não salvas.
6. **Itens interativos fora do papel**: botões, selects, alertas, modais, topbar/sidebar do `base.html`, resumo de tela (card duplicado) e card de escolha de oferta receberam `d-print-none` e/ou regras no `@media print`. O rodapé de auditoria (`Impresso por` / `Data-Hora` / `URL`) foi mantido.
7. **Ajustes de especificidade encontrados na verificação**: `style.css` reexibe `.card.shadow-sm` e força `.report-header { display:block !important }` na impressão, e `sidebar.css` reserva 260px em `.app-main`. Foram necessários um seletor com ID para manter o cabeçalho em duas colunas, um seletor `#conteudo-impressao .card.d-print-none` para os cards de tela e o reset `margin-left/padding: 0` em `.app-main`/`.app-footer` — sem isso o conteúdo ficava deslocado e cortado na largura da folha.

## Arquivos alterados

- `app/templates/conselho/fechamento.html`
- `app/static/css/conselho/conselho.css`
- `app/static/js/conselho/conselho.js`
- `tests/test_aj23_impressao_fechamento_conselho.py` (novo, 4 testes)
- `docs/Relatórios/AJ23_ImpressaoFechamentoConselho.md` (este relatório)

## Decisões

- Seguir o padrão AJ21/de relatórios recentes em vez de criar um novo layout: logo/instituição no topo, tabela clara e rodapé pequeno.
- Manter o rótulo `Impresso por:` e a URL no rodapé, pois o auditable é o estado atual da tela e o texto já existia (a AJ23 anterior do botão Google sugeriu trocar por URL canônica, mas isso ficou **fora deste escopo**).
- Não alterar `legado_nome` nem a regra de prioridade do valor selecionado — apenas garantir que o `beforeprint` rode a mesma sincronização do botão.
- Não houve alteração de modelo/rota/migration; **`git diff --check`, `ruff F821/F811/F841` e `ruff check` limpos**.

## Verificação

### Testes automatizados

- Novo arquivo: 4 testes (renderização com 3 alunos; CSS do padrão de impressão; ocultação dos controles; sincronização dos spans — incluindo `beforeprint` e prioridade sobre o legado).
- Foco AJ23 + AJ22 + conselho UI: **54 passed**.
- Suíte completa: **1933 passed** (1217 warnings preexistentes, 19min41s; antes da AJ23 eram 1929 — os 4 novos testes explicam a diferença).

### Verificação manual (pré-visualização de impressão)

Feita em navegador real sobre uma base SQLite isolada em `%TEMP%` (30 alunos na turma, sem tocar o banco da aplicação), com login na tela e abertura de `/conselho/fechamento/1?oferta_sel=1`:

1. Pré-visualização com mídia de impressão aplicada: foto com `display: none`, bloco do nome sem recuo, cabeçalho institucional e rodapé visíveis, selects ocultos e spans preenchidos.
2. Troca de "Situação Final" para **Concluído** sem salvar: o span passou a exibir `Concluído`; em seguida, valor alterado via script sem disparar `change` + disparo de `beforeprint` (equivalente ao Ctrl+P) também atualizou o span — a seleção corrente prevalece sobre o valor legado/gravado.
3. Geração de PDF real com `@media print` (`A4 landscape`, `842×595 pt`): **4 páginas** para 30 alunos, cabeçalho institucional na 1ª página, `thead` ("Aluno / Conceitos (%) / Presença / Falta / Situação Final / Próximo Curso / Nível") repetido nas páginas 2, 3 e 4, nenhum aluno cortado entre páginas, 30/30 alunos presentes e nenhuma imagem de aluno no PDF (apenas o logo institucional na 1ª página).
4. Largura: conteúdo dentro da área útil da folha (após o reset da sidebar); nenhum texto excedeu a margem direita.
5. Segundo PDF, com "Situação Final" alterada para `Concluído` sem salvar antes da impressão: o valor apareceu impresso na linha do primeiro aluno.
6. Botões, aviso de "Legado", card de escolha de oferta e resumo duplicado da tela não apareceram no PDF; rodapé `Impresso por / Data-Hora / URL` presente.

## Pendências

- Nenhuma funcional pendente neste escopo.
- O rodapé ainda imprime a URL completa com query string (`?oferta_sel=...`); a substituição por URL canônica foi registrada em `AJ23_BotaoGoogleLogArquivo.md` e permanece como proposta separada, não implementada aqui.
- Sem commit, push ou merge: as alterações ficaram na árvore de trabalho conforme solicitado.
