# AJ26 — Resultado do Conselho: impressão padrão AJ23, coluna Conceito e filtro de turmas

**Data:** 20/11/2026
**Escopo:** `/relatorios/conselho` (leitura de resultado do conselho por período letivo)
**Estado:** implementado e verificado. Sem commit, push ou merge.

---

## 1. Modelo de impressão adotado (AJ23)

O padrão foi confirmado nos arquivos abaixo e replicado no resultado do conselho:

| Papel | Arquivo-modelo (AJ23) |
|---|---|
| Cabeçalho/rodapé institucional | `app/templates/conselho/fechamento.html` + `app/templates/conselho/_resumo_cabecalho.html` |
| CSS de impressão | `app/static/css/conselho/conselho.css` + `app/static/css/turmas/carga_horaria_curso.css` |
| JS de impressão | `app/static/js/conselho/conselho.js` (`prepararImpressao()` + `beforeprint`) |
| Decisão documentada | `docs/Relatórios/AJ23_ImpressaoFechamentoConselho.md` |

Elementos transportados: `.print-only` (visível só no papel), `@page { size: A4 landscape; margin: 1cm }`, `#conteudo-impressao`, `thead { display: table-header-group }`, `break-inside/page-break-inside: avoid` nas linhas, bordas `#adb5bd`, cabeçalho `#f1f3f5`, tipografia 8.5pt, badges brancos com borda `#212529` (legíveis em P&B), rodapé 7.5pt e botão **Imprimir** que chama `prepararImpressao()`.

Adaptações específicas: a tabela imprimível é `#tabelaResultado` (não `#tabelaFechamento`) e as colunas são **Turma, Programa, Professor, Aluno, Nível, Presença, Situação Final, Conceito**. Não há foto de aluno. O resumo de status e todos os cards de tela foram marcados `d-print-none`; o cabeçalho já traz período letivo, janela do conselho e escopo.

## 2. Origem do "Período do Conselho" (correção de fonte)

**Antes (errado):** `app/relatorios/conselho.py` lia `ConfiguracaoSistema` com as chaves globais `inicio_conselho`/`fim_conselho`. Problemas:

- não variavam com o `periodo_letivo_id` selecionado nem com a unidade;
- `ConfiguracaoSistema.valor` é `String` (`app/models/organizacao.py`), gravado como `"YYYY-MM-DD"`, enquanto o template chamava `.strftime('%d/%m/%Y')` — com as chaves preenchidas, a página quebrava (500);
- a consulta usava `.first()` sem `unidade_id` e engolia exceções, podendo mostrar datas arbitrárias;
- a legenda "Datas do ciclo de fechamento" era enganosa: o cartão ao lado usa as datas do período letivo.

**Depois (correto):** nova função `_janela_fechamento_conselho(periodo_id, unidade_id)` consulta `PeriodoConselho` (`app/models/conselho.py`) filtrando por `periodo_letivo_id`, `conselho_final=True` e `unidade_id` do contexto (quando houver). São as mesmas datas cadastradas em `/conselho/informacoes`, já validadas para ficar dentro do período letivo. `data_inicio`/`data_fim` são `date`, exibidos com `%d/%m/%Y`. Se não houver janela final cadastrada, o cabeçalho mostra `—`.

As chaves legadas permanecem no banco e ainda são consumidas por outros módulos (`calcular_metricas_conselho`, `app/registros/core.py`); não foram removidas nesta AJ para evitar regressão fora do escopo.

## 3. Regra do Conceito (base única, sem duplicação)

Extraídos para `app/utils/logica.py`:

- `percs_por_conceito(estatisticas)` — `round(counts[c] / total_registros * 100, 1)`, com `total_registros = A+B+C+D+F+J` (inclui F e J no denominador). É exatamente a regra que estava inline em `app/conselho.py:1228-1233`; o fechamento agora chama o helper, então **não existe segunda cópia**.
- `conceito_predominante(estatisticas)` — maior percentual entre `A, B, C, D`; F e J nunca concorrem. Formatos:
  - único: `B — 75%`
  - empate (após arredondamento de 1 casa): `A/B — 50%`, `A/B/C — 33.3%`, `A/B/C/D — 25%`
  - sem A–D (inclusive só F/J, ou sem lançamento): `—`

O percentual é formatado com `:g` para evitar `75.0%`/`50.0%`, preservando casas quando há arredondamento real (`33.3%`). O cálculo acontece no serviço (`app/relatorios/conselho.py`), nunca no template.

A coluna `Próximo curso / Nível` foi substituída por `Conceito` na tela, na impressão e no CSV; o campo `proxima_turma` deixou de ser montado no relatório e `destinos_por_conselho` não é mais chamado ali (o destino continua válido no fechamento e na ficha/relatório AJ22).

## 4. Filtro de turmas

- `<select multiple name="turmas">` substituído por checkboxes em `app/templates/relatorios/resultado_conselho.html`.
- Busca por **turma, curso e professor** (`#buscaTurmas`), com normalização de acentos no JS; o atributo `data-busca` inclui `turma.curso.nome` e os cursos das ofertas ativas, montados em lote em `cursos_por_turma` (uma consulta, sem N+1).
- Botões **Marcar todas** e **Limpar** agem apenas sobre os itens visíveis na busca.
- Ordem por `Turma.nome` (já aplicada na consulta) e cada item mostra nome da turma, curso(s) e professor.
- **Todas as turmas** desabilita a lista de checkboxes; ao desmarcar, eles voltam a ficar habilitados.
- A lista contém somente turmas ativas do `periodo_letivo_id` selecionado; trocar o período recarrega a página e limpa `turmas`, `turmas_all` e `oferta_sel` da query string.
- Parâmetros preservados: `periodo_letivo_id`, `turmas` (repetível), `turmas_all=1`, `oferta_sel`. O fluxo `exigir_escolha` (turma com 2+ ofertas sem escolha) continua idêntico, com hidden fields replicados no formulário de escolha.
- Isolamento por unidade/perfil inalterado: `get_unidade_id()` continua filtrando períodos e turmas; a janela do conselho agora também é filtrada pela unidade.

## 5. CSV

`app/static/js/relatorios/resultado_conselho.js` implementa `exportarCSV()` (antes referenciado, mas inexistente — 404 nos assets). O arquivo sai de `#tabelaResultado`, com:

- cabeçalho `Turma; Programa; Professor; Aluno; Nível; Presença; Situação Final; Conceito`;
- separador `;`, BOM UTF-8, aspas duplas escapadas;
- sem a coluna `Próximo curso / Nível`.

A data/hora de emissão é preenchida no carregamento e atualizada no evento `beforeprint`, cobrindo Ctrl+P e o menu do navegador além do botão **Imprimir**.

## 6. Arquivos alterados

| Arquivo | Alteração |
|---|---|
| `app/utils/logica.py` | novos helpers `CONCEITOS_PREDOMINANTES`, `percs_por_conceito`, `conceito_predominante` |
| `app/conselho.py` | `percs` do fechamento passa a usar o helper compartilhado |
| `app/relatorios/conselho.py` | janela via `PeriodoConselho`, `cursos_por_turma` em lote, campo `conceito`, `escopo_turmas`, remoção de `ConfiguracaoSistema`/`destinos_por_conselho` |
| `app/templates/relatorios/resultado_conselho.html` | cabeçalho de impressão, filtro em checkboxes, coluna Conceito, rodapé de auditoria, `d-print-none` nos controles |
| `app/static/css/relatorios/resultado_conselho.css` | **novo** — estilos de tela e impressão A4 paisagem |
| `app/static/js/relatorios/resultado_conselho.js` | **novo** — filtro, CSV, impressão e `beforeprint` |
| `tests/test_aj26_resultado_conselho.py` | **novo** — 14 testes |
| `tests/test_aj22_proximo_curso_nivel.py` | 2 testes ajustados para a nova coluna |
| `tests/test_d5_leitores.py` | 1 asserção escopada à tabela (o filtro agora lista todos os cursos da turma) |

## 7. Testes

Novo módulo `tests/test_aj26_resultado_conselho.py` (14 testes):

- conceito único `A — 75%`, empate `A/B — 50%`, sem lançamento `—`, só F/J `—`;
- F/J ignorados no ranking, mas mantidos no denominador (`B — 50%` com `percs.B == 50`);
- arredondamento de 1 casa e empate amplo (`A/B/C — 33.3%`, `A/B/C/D — 25%`);
- renderização com `Conceito` e sem `Próximo curso / Nível`;
- datas do cabeçalho vindas de `PeriodoConselho` do período selecionado (com troca de período) e `—` quando não há janela;
- filtro com checkboxes, busca e botões; lista restrita ao período; "todas as turmas" desabilitando a lista; isolamento por unidade;
- contratos do cabeçalho de impressão e do CSS padrão AJ23; `beforeprint`/CSV no JS.

Comandos executados:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_aj26_resultado_conselho.py tests/test_aj22_proximo_curso_nivel.py tests/test_d5_leitores.py tests/test_aj23_impressao_fechamento_conselho.py -p no:cacheprovider
# 69 passed (foco final)

.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
# 1949 passed, 1218 warnings in 1193.15s (0:19:53)
```

Baseline anterior documentado: 1933 passed. Nenhuma falha, erro ou skip.

`git diff --check`: sem erros (apenas aviso de normalização LF→CRLF no template).
`ruff --select F821,F811,F841` nos arquivos Python alterados: `All checks passed!`.

## 8. Verificação em navegador

Base isolada em `%TEMP%` (`aj26_verificacao.db`, SQLite), servidor Flask na porta 5011, login como colaboradora AJ26:

- 36 registros em 3 turmas; cabeçalhos exatos da tabela; conceitos `A — 75%`, `B — 50%`, `—`, `D — 50%` conferidos na tela.
- Filtro: busca por curso (`basquetebol` → só Turma Golfinho) e por professor (3 itens); **Marcar todas** e **Limpar**; **Todas as turmas** desabilitando os 3 checkboxes. Ordem alfabética e itens com turma/curso/professor.
- Console do navegador: nenhum erro.
- Botão **Imprimir** e evento `beforeprint`: campo de emissão atualizado.
- CSV baixado (`resultado_conselho_2026-11-20.csv`): cabeçalho com `Conceito`, 13 linhas, sem coluna antiga.
- PDF gerado no Chrome headless a partir da página autenticada: **4 páginas**, `MediaBox [0 0 841.91998 594.95996]` (A4 paisagem, 297×210 mm).
- Capturas em 1440×1100 (desktop) e 480×1000 (estreita) em `%TEMP%`.

## 9. Decisões e pendências

- Resumo de status omitido na impressão (permitido pelo padrão AJ23); cabeçalho já traz período, janela e escopo.
- Badges em P&B por borda/texto, sem depender de cor de fundo.
- Empate considerado **após** o arredondamento de 1 casa, usando a mesma base do fechamento.
- Busca do filtro considera também cursos das ofertas ativas, porque em dados atuais o curso vive em `turma_curso`, não no campo opcional `turma.curso_id`.
- Pendência consciente: as chaves legadas `inicio_conselho`/`fim_conselho` em `ConfiguracaoSistema` continuam sendo lidas por outros módulos fora do escopo desta AJ; este relatório não as usa mais.
- Nenhuma janela `conselho_final` cadastrada para o período/unidade → cabeçalho exibe `—` (comportamento definido, não erro).

## 10. Diff final

Os arquivos novos foram marcados com `git add -N` (apenas *intent-to-add*, sem conteúdo no índice e sem commit) para que apareçam no `git diff --stat`:

```powershell
git diff --stat
#  app/conselho.py                                    |  14 +-
#  app/relatorios/conselho.py                         |  86 +++--
#  app/static/css/relatorios/resultado_conselho.css   | 235 ++++++++++++
#  app/static/js/relatorios/resultado_conselho.js     | 157 ++++++++
#  app/templates/relatorios/resultado_conselho.html   | 123 +++++--
#  app/utils/logica.py                                |  40 ++
#  .../AJ26_ResultadoConselhoImpressaoConceito.md"    | 153 ++++++++
#  tests/test_aj22_proximo_curso_nivel.py             |  12 +-
#  tests/test_aj26_resultado_conselho.py              | 410 +++++++++++++++++++++
#  tests/test_d5_leitores.py                          |  12 +-
#  10 files changed, 1176 insertions(+), 66 deletions(-)
```

Nenhum commit, push ou merge foi realizado.
