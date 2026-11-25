# AJ27 — Resultado do Conselho: quebra natural da tabela, coluna Conceito, separador de turmas e botão Voltar no fechamento

**Data:** 20/11/2026
**Escopo:** `/relatorios/conselho` (tela, impressão e CSV) e `/conselho/fechamento/<turma_id>` (botão Voltar)
**Estado:** implementado e verificado. Sem commit, push ou merge.

---

## 1. Diagnóstico (antes de qualquer alteração)

A hipótese inicial — `break-inside: avoid` no wrapper da tabela — **estava errada**. O wrapper já computava `break-inside: auto` / `page-break-inside: auto` e `.table-responsive` já computava `overflow: visible`.

**Causa real:** `app/static/css/style.css:128` define, para TODA tabela Bootstrap:

```css
@media print {
  .table { page-break-inside: avoid !important; }
}
```

A regra da AJ26 em `resultado_conselho.css` (`#tabelaResultado { page-break-inside: auto; }`) não tem `!important`, então perde a disputa de cascata. A tabela inteira é tratada como um bloco indivisível e salta para a página 2, deixando a página 1 somente com o cabeçalho institucional.

Evidências coletadas no navegador (mídia print emulada, antes da correção):

| Elemento | `break-inside` | `page-break-inside` | `overflow` |
|---|---|---|---|
| `#tabelaResultado` | `avoid` | `avoid` | — |
| wrapper `.card.report-header.shadow-sm.mb-5` | `auto` | `auto` | `visible` |
| `.table-responsive` | — | — | `visible` |

O wrapper também herdava de `.report-header` e `.card.shadow-sm` (regras globais de impressão): `display: block !important`, `margin: 0 0 12px`, `padding: 0 0 12px` e `border-bottom`. Isso **não** causava a página em branco, mas era herança indevida de estilo de cabeçalho e foi removido na raiz.

A cascata efetiva desta rota é: Bootstrap → `style.css` → `sidebar.css` → `relatorios/resultado_conselho.css`. O arquivo `conselho.css` **não** é carregado aqui.

## 2. Correção na raiz

1. **`app/templates/relatorios/resultado_conselho.html`**
   - Wrapper da tabela deixou de usar `report-header`: agora é `card shadow-sm mb-5 resultado-tabela-card`.
   - A tabela volta a iniciar imediatamente abaixo do cabeçalho na página 1 e quebra naturalmente.
2. **`app/static/css/relatorios/resultado_conselho.css`** (dentro de `@media print`)
   - `#tabelaResultado { page-break-inside: auto !important; break-inside: auto !important; }` — vence o `!important` global de `.table`.
   - `#conteudo-impressao .resultado-tabela-card`: `break-inside/page-break-inside: auto !important`, `overflow: visible !important`, `min-height: 0 !important`, `border: none`, `box-shadow: none`, `background: transparent`, `margin: 0 !important`, `padding: 0 !important`, `display: block !important`.
   - Mantidos os contratos AJ23/AJ26: `@page { size: A4 landscape; margin: 1cm }`, `thead { display: table-header-group }`, `tr { break-inside/page-break-inside: avoid }`, bordas finas, 8.5pt, badges e rodapé.
   - **Nenhuma** regra `break-before` / `page-break-before`: não há quebra forçada entre turmas.

Estilos computados finais (mídia print emulada no navegador):

| Elemento | Resultado |
|---|---|
| wrapper | `break-inside: auto`, `page-break-inside: auto`, `display: block`, `margin: 0`, `padding: 0`, `border-top-style: none`, `min-height: 0`, `overflow: visible` |
| `#tabelaResultado` | `break-inside: auto`, `page-break-inside: auto` |
| `tbody tr` | `break-inside: avoid`, `page-break-inside: avoid` |
| `thead` | `display: table-header-group` |

## 3. Ordem das colunas (tela, impressão e CSV)

Ordem final: **Turma, Programa, Professor, Aluno, Nível, Conceito, Presença, Situação Final**.

`<th>` e `<td>` foram reordenados juntos no template. `exportarCSV()` continua derivando cabeçalho e células do DOM (`querySelectorAll('tr')` + `querySelectorAll('th, td')`), sem lista duplicada — portanto o CSV acompanha automaticamente a nova ordem. Nenhuma regra de negócio, rota, banco, migration, filtro ou cálculo do conceito foi alterado.

Verificação em navegador:

- `th`: `Turma | Programa | Professor | Aluno | Nível | Conceito | Presença | Situação Final`
- 1ª linha: `Turma Tubarão… | Esporte | Professora AJ26 | Aluno 01… | - | A — 75% | 75.0% | Aprovado`
- 1ª linha do CSV: `"Turma";"Programa";"Professor";"Aluno";"Nível";"Conceito";"Presença";"Situação Final"`

## 4. Separador entre turmas/ofertas

- Classe `inicio-turma` gerada **no template**, via `loop.changed((linha.turma, linha.oferta))` com `not loop.first`. A chave de agrupamento é turma + oferta/curso (`linha.oferta` vem de `rotulo_oferta()`); a primeira linha da tabela nunca recebe separador. Nenhuma lógica foi feita em JS.
- CSS somente na impressão:

```css
#tabelaResultado tbody tr.inicio-turma {
    border-top: 2pt dashed #212529 !important;
}
```

- A borda foi aplicada ao `<tr>` (não ao `<td>`) porque, com `border-collapse: collapse`, o Chrome absorve a borda do `<td>` na borda da célula anterior e não desenha o tracejado; teste mínimo confirmou o comportamento.
- **Decisão para a tela:** sem separador. A classe existe no HTML, mas a regra de borda vive dentro de `@media print`; na tela as linhas mantêm apenas a formatação padrão da tabela. Isso evita ruído visual sem duplicar regras.

Verificação: 36 linhas na tela, exatamente 2 linhas com `inicio-turma` (1ª de Golfinho e 1ª de Baleia). Em mídia print, a linha marcada computa `border-top: 2.38095px dashed rgb(33, 37, 41)` e a linha comum `0.595238px solid rgb(222, 226, 230)`.

## 5. Verificação em PDF (3 turmas, 36 alunos)

Base isolada: `aj26_verificacao.db`, turmas Tubarão/Golfinho/Baleia, 36 alunos. Mesma URL, antes e depois: `/relatorios/conselho?periodo_letivo_id=1&turmas_all=1`. A4 landscape (`/MediaBox [0 0 841.91998 594.95996]`).

| | Antes | Depois |
|---|---|---|
| Páginas | **4** | **3** |
| Página 1 | só cabeçalho (12 operadores de texto, 4 retângulos) | cabeçalho + tabela (119 operadores de texto, 408 retângulos) |
| Alunos por página | p1: nenhum; p2: 01–13; p3: 14–26; p4: 27–36 | p1: 01–11; p2: 12–24; p3: 25–36 |
| `thead` repetido | p2/p3/p4 | p2/p3 (`Conceito`, `Presença`, `Situação Final` presentes nas três páginas) |

- 36 alunos únicos, **zero duplicatas e zero linhas cortadas** entre páginas.
- Tracejados localizados nos operadores de desenho do PDF:
  - página 2, primeira linha de **Golfinho** (meio da paginação);
  - página 3, primeira linha de **Baleia** (início de página), com o traço também desenhado no limite da página anterior pelo `border-collapse` — comportamento aceito, pois garante a visibilidade do separador em mudança de página;
  - nenhum tracejado na primeira turma da tabela.

## 6. Botão Voltar no fechamento do conselho

Atendendo ao pedido, `app/templates/conselho/fechamento.html` agora exibe um link **Voltar** para o painel `/conselho` (`url_for('conselho.index_conselho')`) como primeiro item do grupo de ações do cabeçalho:

```html
<a href="{{ url_for('conselho.index_conselho') }}" class="btn btn-outline-secondary">
  <i class="bi bi-arrow-left me-1"></i> Voltar
</a>
```

- É um `<a>` de navegação, não um `<button>` de ação: **Imprimir**, **Exportar .CSV** e **Salvar Fechamento** mantêm rótulos, ícones, `onclick` e ordem — contratos do teste AJ25 preservados.
- Fica dentro do cabeçalho `d-print-none`, portanto não entra na impressão.
- Aparece nas duas situações do template (com oferta escolhida e com `exigir_escolha`).
- Nenhuma rota, regra de negócio ou parâmetro de query foi alterado: o link aponta para `/conselho` sem parâmetros.
- Cobertura nova: `test_voltar_para_o_painel_do_conselho`, em `tests/test_aj25_botoes_fechamento.py`, valida `href="/conselho"`, o ícone `bi bi-arrow-left me-1`, a posição antes dos botões de ação e a permanência no grupo `d-print-none`.

## 7. Testes

Novo arquivo: `tests/test_aj27_resultado_conselho_quebra_separador.py` (4 testes):

1. ordem das colunas na tela e origem DOM do CSV;
2. `inicio-turma` apenas na 1ª linha de cada turma/oferta, gerado pelo template;
3. wrapper sem `report-header` e separador ausente no JS;
4. CSS anula o `avoid` global, não usa quebra forçada e preserva os contratos AJ26.

Conjunto focado (AJ27 + AJ26 + AJ22 + D5): **73 passed**.
Conjunto focado do fechamento (AJ25 + AJ23 + `conselho_ui` + AJ27): **18 passed**, incluindo o novo teste do botão Voltar.
Suíte completa: **1954 passed, 1219 warnings in 1323.72s (0:22:03)** — baseline AJ26 era 1949 passed; a diferença são os 4 testes novos da AJ27 e o novo teste do botão Voltar. Execução feita após todas as alterações.

`git diff --check`: sem erros. `ruff --select F821,F811,F841` nos arquivos Python alterados: limpo.

## 8. `git diff --stat`

```
 app/conselho.py                                    |  14 +-
 app/relatorios/conselho.py                         |  86 +++--
 app/static/css/relatorios/resultado_conselho.css   | 265 +++++++++++++
 app/static/js/relatorios/resultado_conselho.js     | 159 ++++++++
 app/templates/conselho/fechamento.html             |   5 +
 app/templates/relatorios/resultado_conselho.html   | 133 +++++--
 app/utils/logica.py                                |  40 ++
 .../AJ26_ResultadoConselhoImpressaoConceito.md"    | 153 ++++++++
 .../AJ27_ResultadoConselhoQuebraSeparador.md"      | 155 ++++++++++
 tests/test_aj22_proximo_curso_nivel.py             |  12 +-
 tests/test_aj25_botoes_fechamento.py               |  30 ++
 tests/test_aj26_resultado_conselho.py              | 410 +++++++++++++++++++++
 ...est_aj27_resultado_conselho_quebra_separador.py | 158 ++++++++
 tests/test_d5_leitores.py                          |  12 +-
 14 files changed, 1564 insertions(+), 68 deletions(-)
```

O diff é cumulativo porque AJ26 e AJ27 ainda não foram commitados.

---

**Entrega:** nenhum commit, push ou merge foi realizado.
