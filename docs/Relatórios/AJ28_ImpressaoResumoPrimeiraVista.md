# AJ28 — Impressão do "Resumo - Primeira Vista" (`/relatorios/`)

**Data:** 20/11/2026 · **Branch:** `nova_feature` · **Commit/push/merge:** nenhum (conforme solicitado) · **Schema/migration:** nenhuma · **Head do código:** `a7b8c9d0e1f2` (inalterado)

## 1. Motivação e limites

O painel "Resumo - Primeira Vista" já exibia os 9 blocos na tela, mas sua impressão estava incompleta: declarava A4 **retrato** com margem 1.5 cm, não tinha cabeçalho institucional nem rodapé de auditoria, e as três listas com rolagem (`max-height` inline de 180px/250px) imprimiam somente o trecho visível na tela.

A regra da tarefa foi **corrigir somente a impressão**. Não houve alteração de rota, consulta, cálculo, permissão, banco ou migration; nenhum texto, ordem, classe visual ou comportamento da tela foi mudado. Toda regra nova vive dentro de `@media print` ou em elementos `.print-only`.

### Escopo descoberto na rota

`app/relatorios/geral.py::relatorio_geral()` (rota `GET /relatorios/`, `@login_required`, perfis de `ROLES_RELATORIOS`) filtra apenas por `get_unidade_id()` e passa ao template `total_alunos`, `total_professores`, `total_turmas`, `p_presenca`, `media_geral`, `media_programa`, `media_turma`, `conselho`, `freq_programa`, `freq_turma`, `freq_professor`, `todas_as_turmas` e contagens por gênero. **Não existe `turma_selecionada` nem filtro de turma nesta rota.** Por isso o cabeçalho de impressão mostra a unidade do `unidade_contexto` e **"Todas"** para turma (com a contagem de turmas ativas quando disponível), sem inventar parâmetro novo. O context processor de `app/__init__.py` fornece `unidade_contexto`, `informacao_padrao`, `app_version` e `app_stage`; o colaborador vem de `current_user.name`.

## 2. Modelo de impressão usado

| Papel | Arquivo-modelo |
| --- | --- |
| Cabeçalho/rodapé e `prepararImpressao()` | `app/templates/conselho/fechamento.html`, `app/static/css/conselho/conselho.css`, `app/static/js/conselho/conselho.js` (AJ23) |
| Paisagem, especificidade por ID e `beforeprint` | `app/templates/relatorios/resultado_conselho.html`, `app/static/css/relatorios/resultado_conselho.css`, `app/static/js/relatorios/resultado_conselho.js` (AJ26/AJ27) |
| Decisões documentadas | `docs/Relatórios/AJ23_ImpressaoFechamentoConselho.md`, `AJ25_AlinhamentoBotoesFechamento.md`, `AJ26_ResultadoConselhoImpressaoConceito.md`, `AJ27_ResultadoConselhoQuebraSeparador.md` |

Transportados: `.print-only` oculto na tela, `#conteudo-impressao`, `@page { size: A4 landscape; margin: 1cm }`, cabeçalho institucional, rodapé de auditoria, `window.prepararImpressao` + `beforeprint`, quebras controladas e neutralização das regras globais de `style.css`/`sidebar.css`.

## 3. Blocos impressos (9/9)

| # | Bloco | Conteúdo no papel |
| --- | --- | --- |
| 1 | Comunidade Ativa | Alunos / Profs / Turmas |
| 2 | Painel do Conselho | Conteúdos Registrados %, Ofertas Avaliadas %, "X de Y ofertas finalizadas" |
| 3 | Distribuição por Sexo | MASC. / FEM. / OUTRO |
| 4 | Média de Idade Geral | valor + "anos" (texto `text-uppercase` no PDF) |
| 5 | Média por Programa | program + média |
| 6 | Média por Turma | **30/30 turmas** no cenário de verificação |
| 7 | Frequência por Programa | barras + percentual em texto |
| 8 | Desempenho por Professor | **15/15 professores**, badge com percentual e borda legível em P&B |
| 9 | Frequência por Turma | **30/30 turmas**, barras + percentual |

Os valores são exatamente os da tela — nenhum recálculo foi introduzido; as larguras `style="width: {{ perc }}%"` continuam inline, vindas do servidor.

## 4. Arquivos alterados / criados

| Arquivo | Alteração |
| --- | --- |
| `app/templates/relatorios/geral.html` | `#conteudo-impressao`, cabeçalho `.print-only`, rodapé de auditoria, `onclick="prepararImpressao()"`, `{% else %}` com "—" só no papel nas 5 listas que podem ficar vazias. **Nenhuma classe dos 9 cards foi tocada.** |
| `app/static/css/relatorios/geral.css` | Bloco de impressão retrato/1.5cm **substituído** por uma única regra A4 paisagem/1cm + todas as regras de papel; `.print-only` fora do `@media print`. CSS de tela/herdado intacto. |
| `app/static/js/relatorios/geral.js` | **Novo** (já era referenciado pelo template, mas não existia): `preencherEmissao()`, `prepararImpressao()`, `window.prepararImpressao`, `beforeprint`, `DOMContentLoaded`. |
| `tests/snapshots/aj28_geral_cards_before.txt` | Snapshot do HTML dos 9 cards antes da AJ28. |
| `tests/test_aj28_impressao_resumo_primeira_vista.py` | **Novo**, 9 testes. |
| `backlog_desenvolvimento.md` | Entradas AJ28 e, retroativamente, AJ23 (impressão), AJ25, AJ26 e AJ27. |
| `app/models/MER.md` | Regra de impressão, armadilhas de cascata, origem `PeriodoConselho`, helpers de conceito, "Última atualização" e head sem migration nova. |
| `docs/Relatórios/aj28_evidencias/` | Capturas de tela antes/depois e o PDF gerado na verificação. |

## 5. Decisões

1. **Retrato → paisagem:** o único `@page` do arquivo (`A4 portrait; margin: 1.5cm`, com `body { font-size: 10pt }`) foi substituído por `A4 landscape; margin: 1cm`, alinhado a AJ23/AJ26/AJ27. Não existem duas declarações de `@page`. A tipografia de papel ficou em 8.5pt para acomodar 3 colunas.
2. **Especificidade:** `style.css` força `.report-header { display: block !important }` e reexibe `.card.shadow-sm`; por isso os seletores de impressão usam `#conteudo-impressao` + `!important`. A classe `report-header` foi usada **somente no cabeçalho institucional**, nunca nos cards de dados. `sidebar.css` reserva ~260px em `.app-main`; o print zera `margin-left`/`padding` de `.app-main`, `body.sidebar-collapsed .app-main` e `.app-footer`.
3. **Título duplicado removido:** a pedido, o bloco de tela ("Resumo - Primeira Vista" + "Visão consolidada de indicadores e métricas acadêmicas.") não aparece no papel. Foi usado `#conteudo-impressao > header.print-only + div { display: none !important }` — **nenhuma classe do HTML da tela foi alterada**, inclusive a barra de botões permaneceu exatamente como estava (só o `onclick` mudou, de `window.print()` para `prepararImpressao()`).
4. **Capas de rolagem:** os `max-height`/`overflow-y: auto` inline foram preservados para a tela; o print vence com `[style*="max-height"] { max-height: none !important; height: auto !important; overflow: visible !important; overflow-y: visible !important; scrollbar-width: none }`. A alternativa de mover os estilos para classes foi descartada para garantir tela visualmente idêntica.
5. **Quebras:** cada card começa com `break-inside: avoid`; cards com lista/progresso (`:has(...)`) passam a `auto` para quebrar **entre** itens, cada item com `break-inside: avoid`; o `h6` do título tem `break-after: avoid`; `#conteudo-impressao` tem `break-before: auto` (sem página 1 em branco). Grade mantida em 3 colunas (`col-lg-4`) na paisagem.
6. **Legibilidade P&B:** barras e badges com `-webkit-print-color-adjust/print-color-adjust: exact`, trilho com borda fina `#adb5bd`, barra com borda direita escura, badges com fundo branco, borda `#212529`, texto em negrito e percentual já em texto. Ícones `bi-*` e os quadrados decorativos `rounded-3` ficam ocultos no papel.
7. **Listas vazias:** `#conteudo-impressao .lista-vazia` exibe "—" somente no print (o elemento já nasce com `.print-only`); a tela continua sem nada.
8. **CSS morto/herdado preservado:** `.report-table thead th`, `.report-table tbody tr:hover`, `.filter-card`, `.gender-icon`, `.card.bg-primary`, `.card.bg-dark` e o `<style>` inline de `.custom-scrollbar` não foram removidos nem alterados — apenas listados aqui como observação. A regra global `.table { page-break-inside: avoid !important }` (AJ27) foi registrada; este painel não tem tabela, então não houve conflito.

## 6. Prova de que a tela não mudou

- **Snapshot do HTML dos 9 cards:** comparação linha a linha entre `tests/snapshots/aj28_geral_cards_before.txt` e o template atual, ignorando exclusivamente os `{% else %}` + `<div class="print-only lista-vazia">—</div>` (que não renderizam quando há dados) — **idêntico**. Nenhuma classe nova (`resumo-card`, `lista-impressao`, etc.) foi introduzida; `max-height` 180px (1×) e 250px (2×) e os `style="width: {{ perc }}%"` permanecem.
- **Capturas reais:** `docs/Relatórios/aj28_evidencias/tela_antes.png` e `tela_depois.png` (Chrome headless, 1400×6000, mesma URL, mesma base de dados com 30 turmas e 15 professores). Diferença pixel a pixel: **0 pixels divergentes** (`bbox = None`), resoluções idênticas.
- **Na página real:** `getComputedStyle` confirmou `.geral-print-header` e `.print-footer-container` com `display: none` na tela, topbar visível, 9 cards, 75 itens nas listas de rolagem e emissão preenchida pelo JS.

## 7. Testes

- Novo módulo: **9 passed** (`tests/test_aj28_impressao_resumo_primeira_vista.py`) — escopo/cabeçalho, 9 blocos, botões `d-print-none`/`prepararImpressao`, contrato CSS (um `@page` paisagem, listas, cores, `.app-main`, rodapé), contrato JS, 30 turmas + 15 professores, listas vazias, snapshot dos cards e contratos AJ23/AJ26/AJ27 preservados.
- Suíte completa: **1963 passed, 1219 warnings in 1148.75s (0:19:08)** (baseline AJ27: 1954 passed; a diferença são os 9 testes novos da AJ28). Nenhuma falha, erro ou skip.
- `git diff --check`: limpo.

## 8. Verificação em PDF / navegador

Cenário isolado (HTML gerado pelo test client com 30 turmas, 15 professores e 5 programas), servido localmente e impresso com Chrome headless. Evidências em `docs/Relatórios/aj28_evidencias/resumo_primeira_vista_A4_paisagem.pdf`.

| Verificação | Resultado |
| --- | --- |
| Formato | 5 páginas, todas **841.9 × 595 pt** (A4 paisagem) |
| Página 1 | Cabeçalho institucional + Comunidade Ativa + Painel do Conselho + Distribuição por Sexo — **não está em branco** |
| Páginas em branco | nenhuma |
| Blocos | 9/9 presentes ("Média de Idade Geral" aparece em maiúsculas por `text-uppercase`) |
| Média por Turma | 30/30 itens, completos (nome + "anos") |
| Frequência por Turma | 30/30 itens, completos (nome + %) |
| Desempenho por Professor | 15/15 itens, completos (nome + %) |
| Total de itens das listas | 75/75 (tela × PDF) |
| Título duplicado da tela | ausente (0 ocorrências de "Visão consolidada de indicadores") |
| Cabeçalho/rodapé | instituição, título, escopo, colaborador, emissão, `v 0.2.2-beta`, Data/Hora e URL presentes |
| Margens | texto entre x = 28.5 pt e x = 779.8 pt (folha de 841.9 pt) — nada fora da margem direita |
| Barras | 276 operadores de retângulo no PDF (trilhos, barras e bordas), sem corte |
| Quebra de item | nenhum item parcial: todos os 45 itens com % e os 30 com "anos" estão completos |

## 9. Pendências

- **Nenhuma pendência funcional nesta rodada.** Rotas, consultas, cálculos, permissões, banco e migrations permanecem intactos; nenhum commit/push/merge foi feito.
- **Sugestão registrada a pedido (não implementada):** conforme o contexto informado para esta tarefa, as informações do painel refletem o período letivo **vigente (ativo)** e podem existir vários períodos ativos ao mesmo tempo. Um filtro discreto para escolher qual período ativo exibir — oculto quando houver apenas um — exigiria alterar a rota e as consultas/cálculos de `app/relatorios/geral.py` (hoje filtram por `Turma.ativo`/`Aluno.ativo` e pela unidade do contexto), além do cabeçalho de impressão, o que foge da regra "somente impressão" desta AJ28. Recomenda-se avaliar em tarefa separada, confirmando antes a semântica de "vigente" adotada; a tela e o PDF atuais mantêm o comportamento existente, sem filtro.
- **Observação de ambiente:** `pypdf` foi instalado no virtualenv local apenas para ler o PDF de verificação; nenhuma dependência do projeto foi alterada (`requirements` intactos).
