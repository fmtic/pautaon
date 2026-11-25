# AJ28-B — Layout de impressão próprio do "Resumo - Primeira Vista"

**Data:** 23/11/2026 · **Branch:** `nova_feature` · **Sem commit/push/merge** · **Sem migration**

## 1. Causa

O PDF de produção do `/relatorios/` (MGB: 12 turmas, 4 professores, 2 programas) fechava em **3 páginas** para conteúdo que cabe em 1:

1. os 9 cards da tela usam `h-100` e esticam até a altura do maior da linha — a "Média de Idade Geral" reservava meia página para um único número;
2. cards com lista quebravam no meio da moldura, deixando caixas vazias na página 3;
3. a "Frequência por Turma" era cortada sem repetir o título;
4. o cabeçalho repetia a unidade 3× (`nome em negrito`, `Unidade:`, `Escopo: Unidade ...`) e a turma 2×.

A AJ28 já havia padronizado `@page` A4 paisagem/1cm, cabeçalho/rodapé e a emissão única. O problema não era a folha: era **reusar o layout da tela no papel**.

## 2. Decisão de design

**A tela não muda; o papel passa a ser propositalmente diferente.**

- `app/templates/relatorios/geral.html`
  - único acréscimo no HTML de tela: `<div class="d-print-none">` envolvendo as 3 linhas de cards (classe sem efeito visual em `@media screen`). Captura antes × depois: **0 pixels de diferença** (`aj28b_evidencias/verificar_tela.py`).
  - novo `<section class="print-only geral-print-resumo">` dentro de `#conteudo-impressao`, **alimentado pelas mesmas variáveis** (`total_alunos`, `total_professores`, `total_turmas`, `conselho.*`, `total_masculino/feminino/outro`, `media_geral`, `media_programa`, `media_turma`, `freq_programa`, `freq_turma`, `freq_professor`). Nenhum card é reutilizado; nenhuma rota, consulta, cálculo, permissão, banco ou migration foi tocado.
  - cabeçalho enxuto: logo, instituição, título "Resumo - Primeira Vista", **uma** linha `Unidade: {{ escopo_unidade }} · Turma: Todas (N ativas)`, emissão e colaborador à direita. Rodapé de auditoria e `prepararImpressao()` / `beforeprint` da AJ28 preservados.
- Estrutura do papel:
  - **a)** faixa de indicadores numa linha: Alunos | Professores | Turmas | Média de idade geral (anos) | Sexo (Masc./Fem./Outro) | Conselho ("Conteúdos registrados X%" e "Ofertas avaliadas Y% (N de M ofertas finalizadas)") com barras finas;
  - **b)** coluna esquerda: "Por turma" — `Turma | Média de idade (anos) | Frequência (% + barra)`, junção de `media_turma` × `freq_turma` pela chave, ausente = `—`, ordenação natural pelo inteiro inicial do nome (fallback alfabético) feita no template (macro `chave_natural`);
  - **c)** coluna direita: "Por programa" (`Programa | Média de idade | Frequência`, mesma junção) e "Por professor" (`Professor | Frequência | Faixa`), ordenados por nome, com a marca `≥ 75%` / `< 75%` exatamente no limite do badge da tela (`perc >= 75`);
  - **d)** legenda curta com o significado dos indicadores e a fórmula da frequência.
- `app/static/css/relatorios/geral.css`: mantido o único `@page { size: A4 landscape; margin: 1cm }`, o reset de `.app-main`/`.app-footer` e a tipografia/rodapé 8,5pt/7,5pt. Novo bloco usa `thead { display: table-header-group }`, `tr { break-inside: avoid }`, tabelas da direita atômicas (`break-inside: avoid`, sem borda no contêiner — nunca sobra moldura vazia), trilho das barras com borda e `print-color-adjust: exact`. **Sem `h-100`, sem altura mínima e sem cards no papel.** As regras antigas dos cards ficaram no arquivo como CSS inerte, para não alterar a tela.
- `app/static/js/relatorios/geral.js`: **nenhuma alteração** — a emissão única (`preencherEmissao()` no cabeçalho e no `#print-date`) já atende ao botão e ao Ctrl+P.

Formatação numérica preservada: `media_geral` e as frequências saem direto da variável (já com 1 casa do cálculo); `media_programa`/`media_turma` mantêm o `|round(1)` da tela. Nenhum arredondamento novo.

## 3. Fórmula confirmada no código

Lido antes de escrever a legenda:

- `app/services/frequencia_oferta.py:47-50` — `percentual(presentes, faltas)` = `round(presentes / (presentes + faltas) * 100, 1)`, ou `0.0` sem lançamentos.
- `app/models/enums.py:38-52` — `A/B/C/D` = presença, `F` = falta, **`J` = falta justificada (não conta)**.
- `app/utils/logica.py:944-1102` — `calcular_frequencias_relatorio()` usa essa mesma `percentual()` para **programa** (contagem A–D/F por oferta), **turma** (`agregar_por_turma` → `pct_turma`) e **professor** (`agregar_por_oferta` → soma de presentes/faltas → `percentual`). **Não há divergência entre os três níveis.**
- `app/utils/logica.py:1105-1168` — "Conteúdos registrados" = registros de aula ÷ temas do período; "Ofertas avaliadas" = ofertas com conselho concluído ÷ total de ofertas ativas consideradas (`contar_ofertas_conselho`). A legenda não promete nada além disso e inclui: "0,0% pode indicar que ainda não há lançamentos no período." e "Ofertas = cursos ofertados nas turmas".

## 4. Testes e verificação

- `tests/test_aj28_impressao_resumo_primeira_vista.py`: **14 passed**. Snapshot `tests/snapshots/aj28_geral_cards_before.txt` atualizado apenas com as 2 linhas do wrapper `d-print-none`.
- Novos testes: todos os valores no bloco impresso (comparados com os números renderizados na tela), junção com chave ausente → `—`, ordenação natural (1, 2, 10, sem número), marca `≥75`/`<75` coerente com o badge, legenda presente, um único `@page`, cards de tela com `d-print-none`, ausência de `h-100` no bloco impresso, `thead` repetido no CSS.
- Suíte completa: **1968 passed**, 1219 warnings, 1451,27 s (24 min 11 s) — ver §7.

### Volumes em PDF (Chrome headless via Playwright, `@media print`)

| Volume | Turmas | Professores | Programas | Páginas | Resultado |
|---|---:|---:|---:|---:|---|
| (a) real MGB (equivalente) | 12 | 4 | 2 | **1** | A4 paisagem 841,9 × 595 pt; sem página em branco |
| (b) grande | 30 | 15 | 5 | **2** | `thead` repetido nas 2 páginas; sem moldura vazia, sem linha cortada |

Contagem de itens tela × PDF: 12/12, 4/4, 2/2 no volume (a) e 30/30, 15/15, 5/5 no volume (b). Nenhum valor de média/frequência diverges entre HTML e PDF. Os PDFs, os HTMLs renderizados, `resultado.json` e os scripts `verificar_pdf.py` / `verificar_tela.py` estão em `docs/Relatórios/aj28b_evidencias/`. O Playwright e o `pypdf` são usados **apenas** nessa verificação local com o Python do sistema; não entram em `requirements*.txt` nem na suíte do pytest.

## 5. Arquivos alterados

- `app/templates/relatorios/geral.html`
- `app/static/css/relatorios/geral.css`
- `tests/test_aj28_impressao_resumo_primeira_vista.py`
- `tests/snapshots/aj28_geral_cards_before.txt`
- `backlog_desenvolvimento.md`
- `app/models/MER.md`
- `docs/Relatórios/AJ28B_LayoutImpressaoResumo.md` (novo) + `docs/Relatórios/aj28b_evidencias/*` (novo)

`app/static/js/relatorios/geral.js` foi reaproveitado sem alterações.

## 6. Pendências

- Nenhuma pendência funcional. Os dados de produção reais não foram consultados: os volumes foram reproduzidos com as mesmas contagens e nomes representativos em SQLite em memória; a validação com o PDF real de produção segue como rotina de acompanhamento, sem bloquear a entrega.
- A rota continua sem filtro de turma ou de período letivo; incluir esse escopo seria outra task (a linha de papel informa apenas as turmas ativas do contexto, como na tela).

## 7. Suíte completa

```
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
1968 passed, 1219 warnings in 1451.27s (0:24:11)
```

baseline anterior = 1963 passed; +5 testes novos da AJ28-B, nenhuma regressão. Os warnings são os já conhecidos da suíte (SQLAlchemy `Query.get()`, `datetime.utcnow()`, reflexão de índice SQLite) e não são introduzidos por esta task.

## 8. Encerramento

- Sem commit, push ou merge.
- Sem migration, sem alteração de schema, rota, consulta, cálculo, permissão ou banco.
- Arquivos pré-existentes não versionados (`aplicar_deploy.ps1`, `empacotar_deploy.ps1`, `deploy_pacotes/`) **não foram tocados**.
