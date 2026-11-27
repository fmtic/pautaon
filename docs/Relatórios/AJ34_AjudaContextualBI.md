# AJ34 — Ajuda contextual na Central de BI, aviso de filtro, TUR-004 e INS-009

**Data:** 27/11/2026
**Status:** implementado e validado; sem commit, push ou deploy.

## 1. Objetivo e escopo

Entregar ajuda contextual na Central de BI sem copiar texto do catálogo, avisar quando um filtro visível selecionado é ignorado, corrigir **apenas** `TUR-004` para média de alunos distintos e criar o indicador novo `INS-009`. Escopo restrito a `/relatorios/bi`, ao guia `/relatorios/bi/indicadores`, ao catálogo e à documentação.

Restrições atendidas:

- **Sem migration e sem dependência nova.** `Inscricao.data_inicio`, `PeriodoLetivo.data_inicio/data_fim`, `aplicar_filtros_inscricao()`, SQLAlchemy e `xlsxwriter` já existiam. MER atualizado apenas para citar o catálogo como metadado de apresentação.
- **Única mudança de cálculo:** `TUR-004`. Todos os demais números seguem idênticos; regressão verificada pelas suítes BI e pela suíte completa.
- Nenhum arquivo de deploy/configuração foi tocado (`aplicar_deploy.ps1`, `empacotar_deploy.ps1`, `deploy_pacotes/`, `wsgi.py`, `.env`).

## 2. Ajuda contextual a partir do catálogo

Fonte única: `app/relatorios/catalogo.py` (versão **1.2**, **62 indicadores**, `ULTIMA_REVISAO_CATALOGO = "2026-11-27"`).

- `app/relatorios/bi_routes.py` expõe `dados_ajuda_central()` e `_metadados_ajuda_central()` à Central; `_sem_codigos_ocultos()` remove aliases/indisponíveis também do HTML embutido, preservando o contrato da AJ33.
- A Central usa a **mesma permissão** da rota `/relatorios/bi`; o guia e o PDF herdam esse controle.
- Texto ao usuário sem SQL e sem código de tarefa (verificado por `PADRAO_TAREFA` nos testes do guia).
- Dica curta das opções (`title`/`aria-label`) derivada de `sigla_do_codigo()` e `titulo_sigla()`; example real: `SOC — Socioeconômico · Categoria: Alunos`.

### Modal “Como ler a Central”

Exibe, do catálogo: siglas, categorias, tipos de resultado, unidades de medida, filtros, o texto de que Central e guia mostram o mesmo texto e link “Abrir guia completo”. Categorias passaram a ser listadas explicitamente nesta AJ34 (`ajudaCategorias`), além das siglas.

### Modal ⓘ “Entender este indicador”

Por indicador: código, nome, o que mede, como é calculado, unidade, filtros respeitados/não aplicáveis, “não confundir com…”, link **Ver no guia** para `#CODIGO` e **Imprimir/baixar guia (PDF)**. Metadados vêm do catálogo; nenhum texto duplicado à mão.

Acessibilidade: foco nos botões, `aria-label`, `aria-labelledby`, fechamento por ESC (confirmado no Playwright após a transição do modal) e por `btn-close`; responsivo a 390 px sem rolagem horizontal.

### Botão PDF

`Baixar guia (PDF)` abre `/relatorios/bi/indicadores?imprimir=1`. Em `guia_indicadores.js`, o parâmetro expande itens/glossário e chama `window.print()` após o carregamento. A impressão usa o modelo A4, `#conteudo-impressao`, `data-pdf-nome="Guia de Indicadores - pautaON - {data}"`, `@page` e `impressao_pdf.js` já existentes — **nenhuma biblioteca de PDF no servidor**.

## 3. Aviso de filtro não aplicado

`FILTROS_PARCIAIS` é a fonte única dos textos, reaproveitados no aviso da Central, no modal ⓘ e no guia:

| Indicador | Filtro visível | Situação | Texto exibido |
|---|---|---|---|
| `AUL-006` | Período Letivo | `nao_aplicavel` | O filtro de período da Central não é repassado a este indicador. |
| `ALU-009` | Turno | `parcial` | O filtro de turno seleciona a coorte, mas não restringe as inscrições usadas na distribuição por curso. |

O aviso só aparece quando o filtro está selecionado **e** é ignorado. `TEXTO_FILTRO_NAO_APLICADO` padroniza os casos gerais; no caso parcial prevalece o texto específico do catálogo. Nenhum cálculo foi alterado por causa do aviso.

## 4. Única mudança de cálculo — TUR-004

`media_alunos_por_turma()` agora soma os valores de `alunos_por_turma()` (mesma regra de `ALU-010`, com os mesmos filtros) e mantém o denominador histórico: turmas ativas do escopo, com unidade/período/curso legado/turma/professor legado/datas aplicados à própria turma. Arredondamento em uma casa decimal; turma ativa sem aluno entra com zero.

Prova da igualdade exigida:

```
TUR-004 = soma(ALU-010 por turma) ÷ número de turmas ativas do escopo
```

Cenário canônico de `tests/test_bi_turma_desativada.py`:

| Momento | Numerador | Denominador | Resultado |
|---|---:|---:|---:|
| ANTES (linhas de inscrição enturmadas) | 5 | 2 | **2,5** |
| DEPOIS (alunos distintos = soma de ALU-010) | 4 | 2 | **2,0** |

O teste `test_tur004_usa_alunos_distintos_e_mantem_denominador` calcula a soma de `ALU-010`, conta as turmas ativas, reconstrói o cálculo antigo com `cond_inscricao_enturmada()` e afirma `antes >= soma`, `antes / turmas != atual` e a igualdade `atual == round(soma / turmas, 1)`.

## 5. INS-009 — Inscrições iniciadas no período

Código **novo e canônico**; `INS-004` continua alias de `INS-001` e não foi reutilizado.

- Conta inscrições em turmas ativas com `Inscricao.data_inicio` dentro de `PeriodoLetivo.data_inicio..data_fim`, **bordas inclusive**.
- Sem período, usa `periodos_de_referencia_bi()` (vigente por unidade na data atual), como `ALU-004`.
- Unidade, curso e professor pela **oferta** (`TurmaCurso`), como `INS-001`; turno da oferta com fallback para `Turma.turno`, incluindo o caso `Outros`.
- Tipo `contagem`, unidade `inscrições`, metadados completos no catálogo/guia, incluindo “não confundir com `INS-001`/`INS-004` e `ALU-004`/`ALU-013`”.
- A API `/relatorios/bi/indicador/INS-009` e o XLSX continuam devolvendo o código solicitado (`Código: INS-009`).

Bordas verificadas no teste: início/fim contam; um dia antes/depois ficam de fora; período antigo e turma desativada ficam de fora; `data_entrada_oferta` futura não substitui `data_inicio`.

## 6. Testes

| Comando | Resultado |
|---|---|
| `python -m pytest tests/test_aj34_ajuda_contextual_bi.py -q` | **8 passed** |
| `python -m pytest tests/test_aj33_guia_indicadores.py tests/test_bi_turma_desativada.py -q` | **18 passed** |
| `python -m pytest tests/test_aj34_ajuda_contextual_bi.py tests/test_aj33_guia_indicadores.py tests/test_bi_turma_desativada.py -q` | **26 passed** |
| `python -m pytest tests/test_bi_indicadores.py tests/test_bi_turma_desativada.py tests/test_aj33_guia_indicadores.py tests/test_aj34_ajuda_contextual_bi.py -q` | **38 passed** |
| `python -m compileall -q app` | sem erros |
| `python -m pytest -q` | **2093 passed, 1275 warnings in 1127.61s (0:18:47)** |

`tests/test_aj34_ajuda_contextual_bi.py` cobre catálogo/guia e versão, aliases ocultos, INS-009 (bordas, unidade, período, turno, curso/professor, não confundir), TUR-004 (antes × depois e igualdade com ALU-010), metadados iguais ao guia nos casos parciais, presença dos modais/aviso/opção de impressão, API/XLSX e `?imprimir=1`.

## 7. Evidências Playwright (reais)

Diretório ignorado pelo Git: `docs/Relatórios/aj34_evidencias/`. Resumo em `evidencias.json`; sessão em `estado_sessao.json`.

- Desktop 1440×1000: Central (57 opções visíveis, `INS-009` presente, seis códigos ocultos ausentes), dica de sigla, modal “Como ler a Central” com todas as categorias/seções, avisos de `AUL-006` e `ALU-009` com o mesmo texto do modal, ausência de aviso quando não devido, resultado `INS-009 = 3`, gráfico e XLSX disponíveis.
- Modal ⓘ por categoria: alunos, inscrições, frequência, turmas, aulas, atendimento, conselho e matrículas — todos com código e “Como é calculado”; screenshots individuais.
- PDF: `?imprimir=1`, nome padrão `Guia-de-Indicadores-pautaON-2026-11-27` gerado em `beforeprint` e original restaurado em `afterprint`. `Guia_de_Indicadores_AJ34.pdf` inspecionado com `pypdf`: **34 páginas**, A4 (595,9 × 842,9 pt), com `INS-009`, `TUR-004`, “O que mede” e “Como é calculado”.
- Celular 390 px: Central e ambos os modais com `scrollWidth == innerWidth == 390`; screenshots `central_mobile.png`, `modal_como_ler_mobile.png`, `modal_indicador_mobile.png`.
- **Zero erros de JS** (`pageerror` + `console.error`) em toda a sessão.

## 8. Documentação

- `app/relatorios/indicadores.md`: INS-009, TUR-004 com antes × depois, ajuda contextual, PDF, pendências baixadas e versão 1.2.
- `backlog_desenvolvimento.md`: entrada AJ34 e as três pendências antigas baixadas.
- `app/models/MER.md`: apenas cita o catálogo como metadado de apresentação/auditoria, sem esquema/migration.
- Relatórios anteriores preservados; nenhum arquivo de deploy/configuração alterado.

## 9. Estado do Git (sem commit)

`git diff --stat`:

```
 app/models/MER.md                 |   3 +-
 app/relatorios/bi.py              |  10 +-
 app/relatorios/bi_alunos.py       | 117 ++++-
 app/relatorios/bi_routes.py       | 148 +++++-
 app/relatorios/catalogo.py        | 949 +++++++++++++++++++++++++++++++++++++-
 app/relatorios/indicadores.md     | 101 ++--
 app/templates/relatorios/bi.html  | 401 +++++++++++++++-
 backlog_desenvolvimento.md        |   7 +-
 tests/test_bi_indicadores.py      |   2 +
 tests/test_bi_turma_desativada.py |   7 +-
 10 files changed, 1672 insertions(+), 73 deletions(-)
```

`git status --short`:

```
 M app/models/MER.md
 M app/relatorios/bi.py
 M app/relatorios/bi_alunos.py
 M app/relatorios/bi_routes.py
 M app/relatorios/catalogo.py
 M app/relatorios/indicadores.md
 M app/templates/relatorios/bi.html
 M backlog_desenvolvimento.md
 M tests/test_bi_indicadores.py
 M tests/test_bi_turma_desativada.py
?? app/static/css/relatorios/guia_indicadores.css
?? app/static/js/relatorios/guia_indicadores.js
?? app/templates/relatorios/guia_indicadores.html
?? "docs/Relatórios/AJ33_GuiaIndicadoresBI.md"
?? "docs/Relatórios/AJ34_AjudaContextualBI.md"
?? tests/test_aj33_guia_indicadores.py
?? tests/test_aj34_ajuda_contextual_bi.py
```

Os números acima foram regenerados após a suíte completa. Nenhum commit, push ou deploy foi realizado.
