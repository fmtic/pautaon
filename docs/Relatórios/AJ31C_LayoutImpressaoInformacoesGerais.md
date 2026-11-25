# AJ31-C — Layout de impressão e textos de Informações Gerais do Período

**Data:** 25/11/2026 · **Branch:** `nova_feature` · **Migration:** nenhuma (head do código segue `b8c9d0e1f2a3`) · **Commit/push/merge/deploy:** não realizados.

Objeto: corrigir **somente** o layout de impressão e os textos de apresentação de "Informações Gerais do Período". AJ31 e AJ31-B permanecem como histórico concluído: cálculo, rota, permissão, schema e a impressão dos demais relatórios não foram alterados.

## 1. Causa raiz (descoberta somente leitura)

O PDF da AJ31-B saía em **2 páginas** e com a interface do app. Três causas somadas:

| Causa | Evidência | Correção |
|---|---|---|
| O CSS próprio escondia `.app-header`, seletor que **não existe** no `base.html`. A barra real é `header.app-topbar` e é `position: fixed` (`sidebar.css`). | PDF "antes": `getComputedStyle('.app-topbar').display === 'flex'` na mídia print; 2 páginas A4 com a barra se repetindo. | Replication do seletor `.app-topbar` no `@media print` do CSS próprio. |
| As regras de hide/reset vinham de `resultado_conselho.css`, `conselho.css` e `geral.css`, que a AJ31-B deixou de carregar (só o CSS próprio entrou). | `informacoes_gerais_periodo.html` carregava apenas o CSS próprio após a AJ31-B. | Replicação completa do conjunto de seletores no CSS próprio, sem importar os outros. |
| `style.css` global reexibe `.report-header` e `.card.shadow-sm` com `display: block !important`; `sidebar.css` reserva ~260 px em `.app-main`/`.app-footer`. | `app/static/css/style.css:119-166`; `sidebar.css` (margens laterais) e `base.html` (`header.app-topbar`, `aside.app-sidebar`, `.sidebar-backdrop`, `main.app-main`, `footer.app-footer`). | Reset com `margin-left`/`padding` zero e `#conteudo-impressao .card.d-print-none { display: none !important }`; o bloco de papel usa `#conteudo-impressao ...` para vencer a especificidade global. |

Artefatos "antes" em `docs/Relatórios/aj31c_evidencias/ANTES_real.pdf` e `ANTES_real_pagina_1.png` (não versionados).

## 2. Design da impressão

- **Um único `@page { size: A4 portrait; margin: 1cm }`**, fora do `@media print`, preservado do estado anterior. Nenhum `@page` do Resultado do Conselho foi copiado.
- **Bloco `.print-only` próprio**, oculto em tela (`display: none`) e exibido na impressão via `#conteudo-impressao .print-only`/`.info-print`. O card antigo ganhou `d-print-none` e é neutralizado explicitamente (o global o reexibia).
- **Hide/reset completo no `@media print`:** `.app-topbar`, `.app-sidebar`, `.sidebar-backdrop`, `nav`, `.navbar`, `.sidebar`, `#sidebarMenu`, `footer`, `.btn`, `.no-print`, `.d-print-none`, `.alert`, `.modal`, `.modal-backdrop`, `.filter-card`, `.status-card`, `body.sidebar-collapsed .app-main`, `.app-footer`; `body` com cor/fundo brancos e `print-color-adjust: exact`.
- **Cabeçalho padrão:** dois logos inteiros lado a lado (`logo_irn.png` + `logo_secundaria_url`, `max-width: 95px`, sem crop), instituição, título "Informações Gerais do Período", **uma** linha `Unidade: {nome} · Período: {nome} ({início} a {fim})`, emissão e colaborador. Quando `nome == sigla` (ex.: "MGB"), a sigla não é repetida entre parênteses; quando diferem, aparece "Unidade MGB (UNI)".
- **Faixa de 4 indicadores em uma linha:** "Inscrições no período" | "Com situação final definida" | "Sem situação final definida" | "Aproveitamento", com subtítulo `N de M alunos Aprovados ou Participantes` (ex.: `4 de 6 alunos`). Sem avaliados, o valor é `—` e o subtítulo `0 de 0 alunos ...` permanece honesto.
- **Aviso parcial exato** quando `pendentes > 0`: `Resultado parcial: X de Y inscrições ainda não têm situação final definida. Os percentuais abaixo consideram apenas os Z alunos com situação já definida.` Com `Z = 0`, usa-se a mensagem vazia existente "Nenhuma situação final definida neste período ainda." e `—` no Aproveitamento (sem o aviso parcial).
- **Tabela de papel "Distribuição das situações finais":** colunas Situação | O que significa | Alunos | % | barra; 6 linhas do enum + `Total com situação definida` com `100,0%` (`—` no estado vazio). Bordas finas cinza, fundo claro apenas no cabeçalho/total, `break-inside: avoid` na tabela e nas linhas, `display: table-header-group` no `thead`. A cor aparece **só no preenchimento da barra**; número, rótulo e descrição acompanham a barra, mantendo leitura em P&B.
- **Rodapé:** `v{{ app_version }}-{{ app_stage }}`, data/hora e URL; `prepararImpressao()`/`beforeprint` preenchem a emissão; `data-pdf-nome` e o módulo AJ29 seguem intactos (`Informacoes-Gerais-Periodo_{unidade}_{periodo}_{data}`).

## 3. Textos: antigo × novo

| Onde | Antes | Depois |
|---|---|---|
| Título da seção (tela e papel) | "Síntese de Aproveitamento dos Alunos Inscritos" / sem título de tabela | "Distribuição das situações finais" |
| Totais | "Inscrições efetivas:", "Avaliados:", "Pendentes de definição:" | "Inscrições no período:", "Com situação final definida:", "Sem situação final definida:" |
| Aprovado | "Concluíram com aproveitamento e frequência" / "Conclusão com aproveitamento." | "Concluiu o curso com aproveitamento" |
| Participante | "Participação regular sem certificação integral" / "Participaram sem certificação integral." | "Participou do curso" |
| Reprovado por faltas | "Frequência abaixo do mínimo exigido" / "Frequência abaixo do mínimo." | "Frequência abaixo do mínimo exigido" |
| Desistente | "Cancelamento formal de matrícula" / "Cancelamento formal da matrícula." | "Cancelou a matrícula" |
| Evadido | "Abandono sem formalização" / "Saída sem formalização." | "Deixou de frequentar sem formalizar a saída" |
| Empregado | "Inseridos no mercado de trabalho durante o curso" / "Inserção no mercado de trabalho." | "Inserido no mercado de trabalho" |
| Aproveitamento | `Aprovado + Participante ÷ alunos com situação definida`; legenda "Concluído vale como Aprovado (AJ30)." | `alunos Aprovados ou Participantes ÷ alunos com situação final definida`; legenda "Aproveitamento = alunos Aprovados ou Participantes ÷ alunos com situação final definida." |
| Alerta na tela | "Existem N inscrição(ões) ativa(s) ainda sem situação final definida (—) no Conselho de Classe." | A mesma frase exata do aviso parcial do papel (seção 2). |

Removidos do HTML renderizado: "Aprovado + Participante ÷ alunos com situação definida", "Concluído vale como Aprovado (AJ30).", qualquer "AJ30"/"AJxx"/"Concluído" e "sem certificação integral". Os rótulos/cores das seis situações continuam sendo só apresentação (`_CONFIG_SITUACOES`); `SITUACOES_FINAIS_FAVORAVEIS` e os cálculos não mudaram.

### `Participante` e as regras de certificado/ficha 360°

Confirmação em leitura: `Participante` **recebe certificado** (`app/registros/periodos.py:559-561,592` usa `SITUACOES_FINAIS_FAVORAVEIS`; `certificado.html:187-215` emite o mesmo PDF de "conclusão com êxito" para `Aprovado` e `Participante`) e **não gera sinal de atenção** na ficha 360° (`ficha_aluno.py:78-80,427-441`; `:691-710` classifica como `secondary`, nunca `danger`). A expressão "sem certificação integral" existia **apenas** em `relatorio_periodo_info.py` e era inconsistente com essas regras. Removê-la dos textos não alterou nenhum comportamento — nenhum arquivo de certificado/ficha foi tocado.

## 4. Testes: antigo × novo × motivo

Os 21 testes da AJ31-B foram preservados. Ajustes apenas onde fixavam texto antigo:

| Teste | Antes | Depois | Motivo |
|---|---|---|---|
| `test_aproveitamento_favoraveis_sobre_avaliados` | `assert "Aprovado + Participante" in ap["formula"]`; `assert "situação definida" in ap["formula"]` | `assert "Aprovados ou Participantes" in ap["formula"]`; `assert "situação final definida" in ap["formula"]`; ausência de `AJ30`/`Concluído` na legenda | A fórmula e a legenda passaram a dizer "situação final definida" sem histórico AJ30. |
| `test_render_com_massa_tem_totais_fomula_e_valores` (renomeado para `..._textos_novos_e_valores`) | "Inscrições efetivas:", fórmula antiga, legenda "Concluído vale como Aprovado (AJ30)." | Rótulos novos, "Distribuição das situações finais", aviso parcial exato, `2 de 7 alunos ...`, ausência de textos antigos no conteúdo do relatório | Os valores e a massa (10/7/3, 28,6%, 14,3%) continuam idênticos; só o texto observado mudou. |
| `test_estado_vazio_mantem_totais_mensagem_e_traco` | "Inscrições efetivas:", "Avaliados:", "Pendentes de definição:", fórmula antiga | Rótulos novos, "Distribuição das situações finais", sem "Resultado parcial", sem textos AJ30 | Estado vazio (`—`, 0,0%, mensagem exata) inalterado. |

Contratos novos (5): `test_bloco_impressao_proprio_tabela_seis_situacoes_e_total` (bloco `.print-only` antes do card, 4 KPIs, 6 linhas + total, descrições exatas, legenda), `test_css_esconde_layout_app_com_os_seletores_do_padrao` (todos os seletores de hide/reset, um só `@page`, A4 retrato, `print-color-adjust`, `break-inside`), `test_unidade_com_nome_igual_a_sigla_nao_duplica_no_cabecalho`, `test_sem_pendentes_nao_tem_aviso_parcial_e_total_e_100`, `test_descricoes_de_apresentacao_nao_trazem_regra_de_negocio`. A semente do arquivo ganhou uma unidade "MGB" e seu período/usuário para cobrir o caso nome = sigla, sem alterar nenhum dado dos cenários anteriores.

Foco: `python -m pytest -q tests/test_aj31_informacoes_gerais_periodo.py` → **26 passed**. `python -m ruff check app/services/relatorio_periodo_info.py tests/test_aj31_informacoes_gerais_periodo.py` → limpo (a ordem de imports do teste foi ajustada). `git diff --check` → limpo (só avisos LF→CRLF do Windows). `python scripts/verificar_imports.py` → `tudo importa`.

## 5. Verificação real em navegador (Chromium/Playwright)

Configuração: SQLite em arquivo temporário (`C:\Users\FMtic\AppData\Local\Temp\opencode\aj31c_pdf`), `DATABASE_URL` definida antes de importar `app`, `db.create_all()`, login semeado, `page.pdf(prefer_css_page_size=True, print_background=True)` com `media="print"`, conversão PDF→PNG com `pypdfium2` (escala 1,4). **Nenhum banco principal foi escrito.** Cada página foi convertida em imagem e inspecionada (texto com coordenadas via `pypdfium2` + pixels via Pillow; o modelo não recebeu entrada visual direta).

| Cenário | Massa | Páginas | Resultado conferido |
|---|---|---|---|
| (a) `real` | 31 inscrições, 6 com situação (3 Aprovado, 1 Participante, 1 Desistente, 1 Evadido) | **1** | Aproveitamento 66,7% / `4 de 6 alunos`; aviso parcial `25 de 31 ... apenas os 6 alunos`; total `100,0%`; 6 linhas. |
| (b) `vazio` | 4 inscrições, zero avaliados | **1** | `—` no Aproveitamento, `0 de 0 alunos`, mensagem vazia, total `—`, sem aviso parcial, nenhuma barra colorida. |
| (c) `alto` | 300 inscrições com as seis situações (60/55/50/45/40/50) | **1** | Aproveitamento 38,3% / `115 de 300`; total `300` e `100,0%`; sem aviso parcial. |
| (d) `sigla` | Unidade com `nome == sigla` ("MGB"), mesma massa de (a) | **1** | `Unidade: MGB · Período: 2026.2 (...)` — sem "MGB (MGB)". |

Medições comuns aos quatro PDFs: tamanho **595,0 × 841,9 pt** (A4 retrato), margem de 1 cm respeitada (39 px de margem direita na imagem a 1,4×), 4 rótulos de KPI na mesma faixa (x ≈ 40, 173, 306, 439 px), 6 linhas de dados + total, nenhum termo do chrome do app ("Sair", "Painel Geral", "Gerenciar Alunos"), logos com dimensões naturais 500×500 e 1138×455 lado a lado. A faixa escura da topbar cai de **13.961** pixels (faixa y 40–60 no "antes") para **83–86** pixels (apenas texto do cabeçalho) no "depois". As cores saturadas ficam nos logos (164 px, topo) e no preenchimento das barras (135–147 px, x 680–732); no cenário vazio as barras têm **0** pixels saturados.

**Resultado do Conselho preservado:** PDF real da rota `/relatorios/conselho?periodo_letivo_id=...` gerado nos quatro cenários → 841,9 × 595,0 pt (paisagem), 1 página em cada; `resultado_conselho.css` não foi alterado.

Evidências em `docs/Relatórios/aj31c_evidencias/` (não versionadas): `real.pdf`, `vazio.pdf`, `alto.pdf`, `sigla.pdf`, respectivas `_pagina_1.png`, `*_conselho_paisagem.pdf`, `*.json`, `inspecao.json` e os dois artefatos `ANTES_*`.

## 6. Suíte completa

**Suíte completa:** `python -m pytest -q` → **2031 passed, 1277 warnings in 1779.47s (0:29:39), 0 falhas**. Linha de base logo após a AJ31-B: `2026 passed, 1271 warnings in 1731.80s (0:28:51), 0 falhas`. Diferença: **+5 testes** (exatamente os 5 contratos novos da AJ31-C) e nenhuma falha nova; os 21 testes AJ31 continuam verdes com apenas os textos antigos atualizados.

## 7. Arquivos e limites

Alterados nesta AJ31-C: `app/templates/relatorios/informacoes_gerais_periodo.html`, `app/static/css/relatorios/informacoes_gerais_periodo.css`, `app/services/relatorio_periodo_info.py` (somente `_CONFIG_SITUACOES`, `FORMULA_APROVEITAMENTO` e a legenda de apresentação), `tests/test_aj31_informacoes_gerais_periodo.py`, `backlog_desenvolvimento.md`, `app/models/MER.md` e este relatório.

Intactos: migrations/schema, rotas, permissões, cálculo, `resultado_conselho.css`, `conselho.css`, `geral.css`, `style.css`, `sidebar.css`, templates de certificado/ficha 360°, `aplicar_deploy.ps1`, `empacotar_deploy.ps1`, `deploy_pacotes/` e os bancos principais. Nada foi commitado, pushado, mesclado ou deployado.
