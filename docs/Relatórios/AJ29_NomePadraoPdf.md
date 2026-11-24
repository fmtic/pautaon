# AJ29 — Nome padrão do arquivo PDF nos relatórios impressos

**Data:** 23/11/2026 · **Branch:** `nova_feature` · **Sem commit/push/merge** · **Sem migration**

## 1. Causa

Ao clicar em **Imprimir** (ou pressionar **Ctrl+P**) em qualquer relatório, o Chrome sugeria como nome do arquivo PDF o título genérico da aba — normalmente `pautaON - pautaON`, ou um título que continha o nome do aluno. Todo PDF precisava ser renomeado na hora de salvar, e alguns carregavam informação pessoal desnecessária no nome do arquivo.

## 2. Decisão de design

**Tocar somente em `document.title`, somente durante a impressão.** Nenhuma rota, consulta, cálculo, permissão, tabela, coluna, migration, CSS de tela ou markup visível foi alterado.

### 2.1 Módulo compartilhado

`app/static/js/impressao_pdf.js` é o único ponto que altera o título:

- carregado **uma vez** em `app/templates/base.html`, logo antes do bootstrap/app.js (dentro da hierarquia de scripts, antes dos scripts de página); também carregado explicitamente nos 6 documentos HTML impressos que não extendem `base.html`;
- no `beforeprint`: lê `data-pdf-nome` de `#conteudo-impressao`, com fallback para `<body>`; se o atributo não existir, **não faz nada**; guarda `document.title` original e aplica o nome sanitizado;
- no `afterprint`: restaura o título original **exatamente** (inclusive se outro script já tiver alterado o título no carregamento — caso do calendário de bloqueios);
- o token literal `{data}` vira a **data local do navegador** `AAAA-MM-DD` (não UTC, não `Date.toISOString()`);
- sanitização: NFD + remoção de marcas diacríticas (acentos), tudo fora de `[A-Za-z0-9._-]` vira `-`, `--` colapsado, `-` nas bordas removido, limite de **100 caracteres** (corte sem deixar `-` no fim);
- publica as funções puras em `globalThis.impressaoPdf` e em `module.exports` para os testes node; os listeners são registrados somente se `window`/`document` existirem;
- **adicional**, não substitutivo: não chama `window.print()`, não redefine `prepararImpressao()` e não remove os listeners `beforeprint` já existentes (`preencherEmissao()`/`sincronizarSpans()` continuam rodando). Funciona igual para o botão Imprimir e para o Ctrl+P, porque ambos disparam `beforeprint`.

### 2.2 Nomes adotados nos três relatórios principais

| Template | `data-pdf-nome` | Exemplo sanitizado (23/11/2026) |
|---|---|---|
| `app/templates/relatorios/geral.html` | `Resumo-Primeira-Vista{% if escopo_unidade %}_{{ escopo_unidade }}{% endif %}_{data}` | `Resumo-Primeira-Vista_MGB_2026-11-23` |
| `app/templates/relatorios/resultado_conselho.html` | `Resultado-Conselho{% if unidade_contexto %}_{{ unidade_contexto }}{% endif %}{% if periodo_selecionado %}_{{ periodo_selecionado.nome }}{% endif %}_{data}` | `Resultado-Conselho_MGB_2026-2_2026-11-23` |
| `app/templates/conselho/fechamento.html` | `Fechamento-Conselho{% if oferta %}_{{ oferta.curso.nome }}{% endif %}{% if turma %}_{{ turma.nome }}{% endif %}_{data}` | `Fechamento-Conselho_Esporte_Turma-3_2026-11-23` |

Segmentos vazios são omitidos por `{% if %}` — nunca aparece `None`, nunca sobra `-` solto. Chave `{data}` é literal em Jinja (chave única, sem conflito com `{{ }}`).

### 2.3 Como o atributo chega ao `<body>`

`base.html` ganhou um bloco vazio `{% block body_atributos %}` dentro de `<body>`; os templates que extendem a base e imprimem preenchem esse bloco com `data-pdf-nome="..."`. Para os 6 documentos standalone, o atributo foi colocado diretamente em `<body>` junto com a tag `<script>` do módulo. Nenhum bloco `scripts` de página precisou mudar.

## 3. Inventário completo dos templates de impressão

Critérios de busca: `window.print`, `prepararImpressao`, `@media print`, `d-print-none`, `print-only`, `page-break`/`break-*`, `@page`, `conteudo-impressao`, `imprimir`/`impressão`. **20 templates com impressão** receberam nome; 1 partial, 9 launchers e 4 negativos foram examinados e excluídos com motivo.

### 3.1 Grupo A — `#conteudo-impressao` + `prepararImpressao()` (3, extendem `base.html`)

| # | Template | Nome atribuído | Observação |
|---|---|---|---|
| 1 | `relatorios/geral.html` | `Resumo-Primeira-Vista_{unidade}_{data}` | `escopo_unidade` do context processor; principal |
| 2 | `relatorios/resultado_conselho.html` | `Resultado-Conselho_{unidade}_{período}_{data}` | `unidade_contexto` + `periodo_selecionado.nome`; principal |
| 3 | `conselho/fechamento.html` | `Fechamento-Conselho_{curso}_{turma}_{data}` | `oferta.curso.nome` + `turma.nome`; principal |

### 3.2 Grupo B — documentos HTML standalone com `<head>` próprio (6, não extendem `base.html`)

| # | Template | Nome atribuído | Observação |
|---|---|---|---|
| 4 | `frequencia/imprimir_pauta.html` | `Relatorio-Pauta_{turma}_{curso}_{mês}_{data}` | usa turma/curso/mês; **nenhum aluno** |
| 5 | `conselho/imprimir_formulario.html` | `Relatorio-Formulario-Conselho_{etapa}_{data}` | formulário em branco |
| 6 | `alunos/impressao.html` | `Relatorio-Ficha-Inscricao_{data}` | ficha de inscrição; sem nome do aluno |
| 7 | `alunos/historico.html` | `Historico-Aluno_{data}` | histórico; sem nome do aluno |
| 8 | `turmas/imprimir_listar_turma.html` | `Relatorio-Turmas_{período}_{unidade}_{data}` | agrupa centro → turma → ofertas |
| 9 | `planejamento/impressao_temas.html` | `Relatorio-Temas{curso}_{data}` | curso_only quando há um único curso filtrado |

### 3.3 Grupo C — `base.html` com impressão própria (8, inclui 1 parcial)

| # | Template | Nome atribuído | Observação |
|---|---|---|---|
| 10 | `planejamento/calendario_bloqueados_print.html` | `Relatorio-Dias-Sem-Aula_{periodo}_{data}` | ver conflito de título em §5 |
| 11 | `conselho/resumo_conselho.html` | `Relatorio-Resumo-Conselho_{turma}_{curso}_{etapa}_{data}` | avaliação individual + coletiva |
| 12 | `conselho/_resumo_cabecalho.html` | — | **excluído**: partial incluído por #11, nunca impresso sozinho |
| 13 | `periodos/certificado.html` | `Relatorio-Certificados_{periodo}_{data}` | vários certificados por aluno na mesma página; sem nome de aluno |
| 14 | `turmas/carga_horaria_curso.html` | `Relatorio-Carga-Horaria{curso}_{status}_{data}` | catálogo vigente/concluído |
| 15 | `frequencia/relatorio.html` | `Relatorio-Frequencia_{turma}_{data}` | turma + intervalo |
| 16 | `servico_social/forms/socioeconomica.html` | `Relatorio-Formulario-Socioeconomico_{data}` | modo impressão pela rota |
| 17 | `servico_social/forms/notificacao_violencia.html` | `Relatorio-Notificacao-Violencia_{data}` | modo impressão pela rota |

### 3.4 Grupo D — formulários do Serviço Social impressos via rota (4)

A rota `servico_social.gerar_impressao` passa `modo_impressao=True` ao template; embora não haja `window.print` neles, o navegador imprime a página renderizada.

| # | Template | Nome atribuído |
|---|---|---|
| 18 | `servico_social/forms/atendimento_social.html` | `Relatorio-Atendimento-Social_{data}` |
| 19 | `servico_social/forms/profissionalizante_30.html` | `Relatorio-Entrevista-Profissionalizante_{data}` |
| 20 | `servico_social/forms/profissionalizante_geral.html` | `Relatorio-Entrevista-Profissionalizante_{data}` |
| 21 | `servico_social/forms/plano_individual_trans.html` | `Relatorio-Plano-Individual-Trans_{data}` |

### 3.5 Exclusões

| Template | Motivo |
|---|---|
| `conselho/painel.html` | launcher: abre o formulário/relatório em outra aba; não é impresso |
| `turmas/listar.html` | launcher: link para `imprimir_centros_custo_turmas` |
| `turmas/detalhe.html` | launcher: links para a pauta impressa |
| `frequencia/lancar.html` | launcher: link "Imprimir Pauta" |
| `planejamento/planejamento.html` | launcher: link "Exportar / Imprimir" |
| `periodos/calendario.html` | launcher: link para `calendario_exportar` |
| `periodos/lista.html` | launcher: link "Certificados" |
| `alunos/gerenciar.html` | launcher: links para `imprimir_aluno`/`historico_aluno` |
| `servico_social/entrevistas.html` | launcher: link para `gerar_impressao` |
| `turmas/observacoes.html` | "Diário de Bordo" não tem `window.print`, `@media print` nem rota de impressão |
| `relatorios/ficha_aluno.html` | ficha 360° interativa, sem impressão |
| `relatorios/relatorio_alunos.html` | exportação XLSX, não PDF impresso |
| `relatorios/bi.html` | painel/exportação XLSX, não PDF impresso |

## 4. Privacidade

Nenhum `data-pdf-nome` contém nome, matrícula, CPF, e-mail ou foto de aluno. Regras aplicadas:

- **pauta** (`frequencia/imprimir_pauta.html`): turma + curso + mês + data;
- **histórico/ficha** (`alunos/historico.html`, `alunos/impressao.html`): `Historico-Aluno_{data}` / `Relatorio-Ficha-Inscricao_{data}`;
- **certificados**: `Relatorio-Certificados_{periodo}_{data}` — um único PDF reúne vários alunos, sem distingui-los no nome;
- os três relatórios principais usam apenas unidade/período/curso/turma.

## 5. Conflito conhecido: calendário de bloqueios

`planejamento/calendario_bloqueados_print.html` já executava
`document.title = 'dias_sem_aula_{{ periodo.nome_exibicao | replace(" ", "_") }}';` no carregamento. O módulo AJ29 trata esse valor como o título **original** e o restaura no `afterprint`. Consequência: depois de fechar o diálogo, a aba volta a mostrar `dias_sem_aula_*` (e não `pautaON - pautaON`) — comportamento pré-existente preservado, sem regressão.

## 6. Testes e verificação

### 6.1 Testes automatizados

- `tests/test_aj29_nome_pdf_js.py` — **8 casos** executados em Node (padrão de `tests/test_grade_horario_js.py`, com skip se node ausente): sanitização de acentos (`acento → Acao`, `acentosTodos → AEIOU-aeiou-Cc-Ao`), substituição de `{data}` pela data injetada, limite de 100 caracteres sem `-` final, colapso de hífens, ausência de `data-pdf-nome` (título intacto), fallback para `<body>` e ciclo `beforeprint`/`afterprint` com restauração.
- `tests/test_aj29_nome_pdf.py` — **6 casos** de contrato: carregamento único do módulo em `base.html` antes do bootstrap/app.js e dos scripts de página; contrato do JS (eventos, seletor, sanitização, exports, nenhuma chamada a `window.print`/`prepararImpressao` no código executável); os 3 templates principais com o atributo no padrão e segmentos condicionais; ausência de dados pessoais nos atributos.
- Comando: `.\.venv\Scripts\python.exe -m pytest -q tests/test_aj29_nome_pdf.py tests/test_aj29_nome_pdf_js.py -p no:cacheprovider` → **14 passed**.
- Snapshots dourados regenerados **somente** pela nova tag `<script>` no `base.html`: 10 arquivos AJ6-B3, 6 AJ5-C/AJ5-E, 4 AJ6-B5 e 2 AJ6-B6 (22 arquivos, cada um com apenas a linha do script adicionada). Os 6 hashes SHA-256 do HTML renderizado em `tests/test_aj7d_gravacao_conselho.py` também foram regravados pela mesma razão (a única diferença no HTML é a nova tag); o módulo passa com **32 passed**.

### 6.2 Verificação em navegador

Playwright + Chromium **153.0.8010.12**, Python do sistema (Playwright/pypdf não entram em `requirements*.txt`). Scratch page montada com o **módulo real** copiado de `app/static/js/impressao_pdf.js` (SHA-256 `d2d07c3a…78c4`), sem gravar nada no repositório. Data local do navegador: **2026-11-23**.

**Cenário 1 — `#conteudo-impressao` com acento e `{data}`**

| Momento | `document.title` observado |
|---|---|
| antes | `pautaON - pautaON` |
| durante `beforeprint` | `Resumo-Primeira-Vista_Unidade-Acao_2026-11-23` |
| depois de `afterprint` | `pautaON - pautaON` |

Atributo bruto `Resumo-Primeira-Vista_Unidade-Ação_{data}`: acento removido (`Ação → Acao`), `{data}` substituído pela data local, sem `{data}` residual, somente `[A-Za-z0-9._-]`, 45 caracteres (≤ 100), restauração exata. Caminho do **botão Imprimir** (`window.print()` real): **PASSOU** — o listener `beforeprint` viu exatamente o nome acima e o `afterprint` restaurou o título.

**Cenário 2 — fallback para `<body>` e privacidade**

Atributo no `<body>`: `Historico-Aluno_{data}`, sem `#conteudo-impressao`, com `Aluno: João da Silva` no DOM. Título durante `beforeprint`: `Historico-Aluno_2026-11-23`; depois: `pautaON - pautaON`. Nenhuma ocorrência de `João`, `Joao`, `Silva` ou `Aluno:` em nenhum título observado. Botão Imprimir: **PASSOU**.

**Limitação do Ctrl+P nativo:** `page.keyboard.press('Control+P')` em Chromium headless **não emitiu** `beforeprint`/`afterprint` (título permaneceu inalterado). Tentativa adicional em modo **headed** com evento de teclado no nível do SO (`keybd_event`) também não alcançou o acelerador do navegador. Não há evidência direta do atalho nativo neste ambiente; a prova disponível é o disparo explícito de `beforeprint`/`afterprint` (idêntico ao que o navegador emite) somado ao caminho real do botão `window.print()`, que passou nos dois cenários. Nenhuma alegação de sucesso do Ctrl+P nativo é feita.

### 6.3 Suíte completa

**1982 passed, 1219 warnings in 824,43 s (0:13:44)** — baseline AJ28-B: **1968 passed, 1219 warnings in 1451,27 s**; acréscimo exato de **14** testes (8 node + 6 Python). Nenhuma falha, nenhum teste existente removido. Rodada com `.\\.venv\\Scripts\\python.exe -m pytest -q -p no:cacheprovider`.

### 6.4 `git diff --stat`

```
 app/models/MER.md                                                |   5 +++--
 app/templates/alunos/historico.html                              |   4 +++-
 app/templates/alunos/impressao.html                              |   4 +++-
 app/templates/base.html                                          |   5 ++++-
 app/templates/conselho/fechamento.html                           |   3 ++-
 app/templates/conselho/imprimir_formulario.html                  |   4 +++-
 app/templates/conselho/resumo_conselho.html                      |   2 ++
 app/templates/frequencia/imprimir_pauta.html                     |   4 +++-
 app/templates/frequencia/relatorio.html                          |   2 ++
 app/templates/periodos/certificado.html                          |   2 ++
 app/templates/planejamento/calendario_bloqueados_print.html      |   6 +++++-
 app/templates/planejamento/impressao_temas.html                  |   4 +++-
 app/templates/relatorios/geral.html                              |   3 ++-
 app/templates/relatorios/resultado_conselho.html                 |   3 ++-
 app/templates/servico_social/forms/atendimento_social.html       |   2 ++
 app/templates/servico_social/forms/notificacao_violencia.html    |   2 ++
 app/templates/servico_social/forms/plano_individual_trans.html   |   2 ++
 app/templates/servico_social/forms/profissionalizante_30.html    |   2 ++
 app/templates/servico_social/forms/profissionalizante_geral.html |   2 ++
 app/templates/servico_social/forms/socioeconomica.html           |   2 ++
 app/templates/turmas/carga_horaria_curso.html                    |   2 ++
 app/templates/turmas/imprimir_listar_turma.html                  |   4 +++-
 backlog_desenvolvimento.md                                       |   6 ++++++
 tests/snapshots/aj5c_editar_completo.txt                         |   2 ++
 tests/snapshots/aj5c_novo_com_unidades.txt                        |   2 ++
 tests/snapshots/aj5c_novo_sem_unidades.txt                        |   2 ++
 tests/snapshots/aj5e_estrutura_editar_completo.txt                |   2 ++
 tests/snapshots/aj5e_estrutura_novo_com_unidades.txt              |   2 ++
 tests/snapshots/aj5e_estrutura_novo_sem_unidades.txt              |   2 ++
 tests/snapshots/aj6b3_admin_t1.txt                                |   2 +-
 tests/snapshots/aj6b3_admin_t2.txt                                |   2 +-
 tests/snapshots/aj6b3_gerencia_t1.txt                             |   2 +-
 tests/snapshots/aj6b3_gerencia_t2.txt                             |   2 +-
 tests/snapshots/aj6b3_pedagogico_t1.txt                           |   2 +-
 tests/snapshots/aj6b3_pedagogico_t2.txt                           |   2 +-
 tests/snapshots/aj6b3_secretaria_t1.txt                           |   2 +-
 tests/snapshots/aj6b3_secretaria_t2.txt                           |   2 +-
 tests/snapshots/aj6b3_servico_social_t1.txt                       |   2 +-
 tests/snapshots/aj6b3_servico_social_t2.txt                       |   2 +-
 tests/snapshots/aj6b5_lista_admin.txt                             |   2 +-
 tests/snapshots/aj6b5_lista_gerencia.txt                          |   2 +-
 tests/snapshots/aj6b5_lista_pedagogico.txt                        |   2 +-
 tests/snapshots/aj6b5_lista_secretaria.txt                        |   2 +-
 tests/snapshots/aj6b6_admin_registros_ver_turma.txt               |   2 +-
 tests/snapshots/aj6b6_secretaria_registros_frequencia.txt         |   2 +-
 tests/test_aj7d_gravacao_conselho.py                       | 14 ++++++++------
 46 files changed, 98 insertions(+), 35 deletions(-)
```

> Os 4 arquivos novos (`app/static/js/impressao_pdf.js`, `tests/test_aj29_nome_pdf.py`,
> `tests/test_aj29_nome_pdf_js.py` e este relatório) estão **untracked** — `git diff --stat`
> não os inclui. Os scripts `aplicar_deploy.ps1` e `empacotar_deploy.ps1` também são
> untracked e **preexistentes**, não foram tocados.

## 7. Arquivos alterados

- Novos: `app/static/js/impressao_pdf.js`, `tests/test_aj29_nome_pdf.py`, `tests/test_aj29_nome_pdf_js.py`, `docs/Relatórios/AJ29_NomePadraoPdf.md`.
- Base: `app/templates/base.html` (tag `<script>` + bloco `body_atributos`).
- Relatórios principais: `app/templates/relatorios/geral.html`, `app/templates/relatorios/resultado_conselho.html`, `app/templates/conselho/fechamento.html`.
- Demais templates de impressão: 6 standalone (`frequencia/imprimir_pauta.html`, `conselho/imprimir_formulario.html`, `alunos/impressao.html`, `alunos/historico.html`, `turmas/imprimir_listar_turma.html`, `planejamento/impressao_temas.html`) + 11 que extendem a base via `body_atributos` (calendário de bloqueios, resumo do conselho, certificado, carga horária, frequência/relatório, socioeconômica, notificação de violência e os 4 formulários do Serviço Social).
- Documentação: `backlog_desenvolvimento.md`, `app/models/MER.md`.
- Teste existente ajustado: `tests/test_aj7d_gravacao_conselho.py` (6 hashes dourados).
- Snapshots: 22 arquivos em `tests/snapshots/`.
- **Nenhuma** alteração em rotas, modelos, migrations, consultas, cálculos, permissões, CSS ou arquivos de configuração.
