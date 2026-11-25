# AJ31-B — Fechamento de Informações Gerais do Período

**Data:** 25/11/2026 · **Branch:** `nova_feature` · **Migration:** nenhuma (head do código segue `b8c9d0e1f2a3`) · **Commit/push/merge/deploy:** não realizados.

Objeto: conferir, corrigir e testar **Informações Gerais do Período** antes de produção, sem alterar outras telas/relatórios. AJ30-B e o diagnóstico do `CheckViolation` permanecem como histórico concluído e não foram reabertos.

## 1. Antes × Depois (pontos 2a–2j)

As referências "antes" são do estado inicial da AJ31-B (arquivos já existentes na árvore, sem alterações locais naquele momento).

| Ponto | Antes | Depois | Motivo |
|---|---|---|---|
| **2a — mesma base de contagens** | `app/services/relatorio_periodo_info.py:63-74` montava a contagem de inscritos direto de `Inscricao`; `:80-97` consultava `ConselhoClasse` com outro `FROM` (sem `Inscricao`). Dois conjuntos diferentes. | `app/services/relatorio_periodo_info.py:97-135` cria **uma** subquery `inscritos_base` de pares `(aluno_id, turma_curso_id)` e uma subquery de pares FINAL; `:150-176` usa a mesma base para inscritos, contagens e pendentes (join por `aluno_id` + `turma_curso_id`). | Sem par comum, um conselho podia virar "avaliado" sem existir inscrição naquele período/unidade. |
| **2b — ativos** | `Inscricao.ativo` não era filtrado; `Turma.ativo`/`Aluno.ativo` não eram verificados no serviço. | `:107-113` filtra `Turma.periodo_letivo_id`, `Turma.ativo`, `Aluno.ativo` e usa `cond_inscricao_enturmada()` (que já contém `Inscricao.ativo`, `Turma.ativo` e `cond_oferta_efetiva()` — `app/services/enturmado.py:77-117`). | Contagens passam a respeitar a definição canônica de "enturmado" do BI. |
| **2c — oferta efetiva** | `cond_oferta_efetiva()` era aplicada só na contagem de conselhos, sem exigir a inscrição correspondente. | Aplicada dentro da base (`cond_inscricao_enturmada()`), vale para as duas contagens; oferta inativa em período encerrado continua contando (regra M4), oferta inativa em período aberto não conta. | Histórico preservado, sem duplicar regra. |
| **2d — unidade** | Serviço não filtrava unidade; rota em `app/relatorios/geral.py:129` buscava o período com `get_or_404` sem conferir `periodo.unidade_id`. | Serviço filtra `Turma.unidade_id == unidade_id` quando há unidade (`:116-117`); rota devolve **404** para período de outra unidade (`app/relatorios/geral.py:137-143`). | Isolamento de tenant e badge correto na Visão Global. |
| **2e — só pares inscritos** | `ConselhoClasse` FINAL era contado isoladamente (`relatorio_periodo_info.py:80-97`). | `_pares_avaliados()` (`:121-135`) + `mesmo_par` (`:150-153`) no join; testes provam que conselho FINAL de aluno sem inscrição não entra. | Nenhum avaliado "fantasma". |
| **2f — pendentes** | `:128` usava `pendentes_definicao = max(0, total_inscritos - total_avaliados)`, escondendo inconsistência. | `:168-176` conta diretamente os pares da base sem conselho FINAL com situação não nula, sem `max(0, ...)`. | A origem do número é a base, não uma subtração defensiva. |
| **2g — vocabulário** | `_CONFIG_SITUACOES` (`:8-51`) duplicava os seis valores; `exibir_se_zero` (`:42,49`) ocultava `Evadido`/`Empregado` quando zero. | Valores vêm de `SITUACAO_FINAL_OPCOES` (`:179`); config é **só apresentação** (`:21-94`), `exibir_se_zero` não existe mais; valores gravados fora da config entram ao final da lista (`:180`) com presentation padrão (`:67-73`); `soma(quantidades) == total_avaliados`. | Fonte única `SituacaoFinal`/enum, sem valor descartado em silêncio. |
| **2h — zero avaliados** | Divisão por zero era possível em `:113` e a tela escondia totais/pendentes (`informacoes_gerais_periodo.html:99-133`); mensagem era diferente (`:90-95`). | Serviço usa `percentual()` (`app/services/frequencia_oferta.py:47-50`, 1 casa) com guarda `if total_avaliados` (`:185-189, 204-208`); tela mostra sempre inscritos/avaliados/pendentes e a mensagem exata "Nenhuma situação final definida neste período ainda." | Sem `ZeroDivisionError`, estado vazio legível e honesto. |
| **2i — Aproveitamento** | Não existia. | `:199-211`: `SITUACOES_FINAIS_FAVORAVEIS` (`app/models/enums.py:124-127`) ÷ `total_avaliados`, `—` quando não há avaliados; fórmula `Aprovado + Participante ÷ alunos com situação definida` e legenda "Concluído vale como Aprovado (AJ30)." visíveis na tela. | Fórmula explícita, sem regra nova de negócio. |
| **2j — isolamento** | Qualquer período abria (`geral.py:129`); Visão Global dizia "Visão Global" (`:138`); sem unidade, perfil operacional caía em agregação global; professor já era barrado por `ROLES_RELATORIOS`. | 403 fora de `ROLES_RELATORIOS`; 404 para período inexistente/de outra unidade; perfil não-global sem unidade → 404 (`geral.py:131-134`); Visão Global agrega todas as unidades e mostra "Todas as unidades" (`:151-157`); período sem `unidade_id` é descrito sem erro. | Nenhum vazamento de nome/datas entre unidades. |

## 2. Impressão, JS e contratos vizinhos

| Item | Antes | Depois |
|---|---|---|
| CSS | `informacoes_gerais_periodo.html:5-6` carregava `resultado_conselho.css` (A4 paisagem) **e** o CSS próprio (A4 retrato). | Só o CSS próprio; `app/static/css/relatorios/informacoes_gerais_periodo.css:34-37` mantém **uma única** declaração `@page { size: A4 portrait; margin: 1cm }`; `print-color-adjust: exact`, bordas e `break-inside: avoid` preservados. |
| JS | `informacoes_gerais_periodo.html:154` carregava `resultado_conselho.js` (filtro/CSV). | Removido; restam só `prepararImpressao()`/`beforeprint` e o módulo AJ29 do `base.html`, com `data-pdf-nome="Informacoes-Gerais-Periodo_{unidade}_{periodo}_{data}"`. |
| Cabeçalho/rodapé | Unidade e período em linhas separadas (`:14-42`); sem reaproveitamento claro do padrão. | `resultado-print-header` com logos (`logo_irn.png` + institucional), instituição, título e **uma** linha "Unidade: X · Período: Y (datas)"; emissão e colaborador; rodapé com `v{{ app_version }}-{{ app_stage }}`, data/hora e URL; sem foto. Cor nunca é único sinal (número, rótulo e legenda acompanham a barra). |
| AJ26/AJ27/AJ28/AJ29 | Contratos existentes. | `resultado_conselho.css` continua com `@page`/`A4 landscape`; template continua com `resultado-print-header`, `Período do Conselho`, `Conceito`, `loop.changed((linha.turma, linha.oferta))`. Foco 60 passed nos módulos AJ26/27/28/29/30 após a mudança. |

## 3. Botão no Resultado do Conselho

| Antes (`resultado_conselho.html:129-133, 331-343`) | Depois | Motivo |
|---|---|---|
| `class="btn btn-outline-primary {{ 'disabled' ... }}"` sem `d-print-none`, sem atributo `disabled`/`aria-disabled`, `div` sem `flex-wrap`. | `d-print-none` no `<a>`, `disabled aria-disabled="true" tabindex="-1"` quando não há período, `flex-wrap` no contêiner. | Sem período o `href` já era `#`, mas o clique/leitura de teclado ainda era ambíguo; agora o desabilitado é explícito e some na impressão. |
| JS trocava só `href` e a classe `disabled`. | JS também remove/põe `disabled`, `aria-disabled` e `tabindex` ao trocar o select. | Mantém coerência entre HTML inicial e mudança dinâmica. |
| Ícone `bi bi-pie-chart` no botão de informações; ícone de Imprimir é `bi bi-printer`. | Ícones inalterados. | Nenhum teste antigo depende de `bi-file-pdf` (varredura em `tests/`: 0 ocorrências); não houve troca a registrar. |

**Ajuste autorizado em teste antigo (antigo × novo × motivo):** `tests/test_aj1_servico_social_relatorios.py::_rotas_relatorios` preenchia só `<int:aluno_id>` e `<codigo>`. Passou a preencher também `<int:periodo_id>` com `ids["per_a"]`, período real da própria semente. A rota AJ31 continua no varredor e é exercitada pelas mesmas asserções de paridade/isolamento/login; nenhuma asserção, papel ou resposta esperada foi relaxada. Sem esse ajuste as 5 falhas da linha de base (T1, T2, T2b, T6, T7) permaneceriam — a suíte final deve **zerar as 5 falhas**.

## 4. Fórmulas

- Percentual de cada situação: `quantidade ÷ total_avaliados`, arredondado a **1 casa** pelo helper existente `percentual()` (`app/services/frequencia_oferta.py:47-50`). Exemplo da massa de teste: 1 de 7 → `14,3%`; 2 de 7 → `28,6%`.
- Aproveitamento: `(Aprovado + Participante) ÷ total_avaliados` — no exemplo, `2 ÷ 7 = 28,6%`; sem avaliados, `—` (nenhuma divisão).
- Pendentes: `COUNT(pares da base sem situação final definida)`, **não** `max(0, inscritos − avaliados)`.
- Massa conhecida do teste: 10 inscritos, 7 avaliados, 3 pendentes, 2 favoráveis; Visão Global (A + B): 11 inscritos, 8 avaliados, 3 pendentes.

## 5. Testes e checagens

- Novo: `tests/test_aj31_informacoes_gerais_periodo.py` — **21 testes** (base única/atvos/oferta efetiva/histórico/unidade, conselho fora da base, enum e 1 casa, config só apresentação, valor gravado fora da config, Aproveitamento, estado vazio, 403/404, Visão Global, período sem unidade, render, cabeçalho/rodapé, CSS/JS, contratos AJ26–AJ29 e botão). Helper `login_as` de `tests/_helpers.py`.
- Foco: `34 passed` (AJ31 + AJ1); `60 passed` (AJ26/27/28/29/30); `python scripts/verificar_imports.py` → **tudo importa**; `ruff --select F401,F821,F811,F841` limpo; `git diff --check` limpo; `compileall` OK.
- **Linha de base (antes):** `5 failed, 2000 passed, 1230 warnings in 1723.94s`; as 5 falhas eram todas as do varredor de rotas AJ1 acima. **Nenhuma falha AJ26/AJ27 na base.**
- **Suíte final:** `python -m pytest -q` → **2026 passed, 1271 warnings in 1731.80s (0:28:51), 0 falhas**. Diferença vs linha de base (`5 failed, 2000 passed, 1230 warnings in 1723.94s`): **+21 testes e −5 falhas** (2005 → 2026 testes coletados). As 5 falhas do varredor AJ1 foram zeradas sem relaxar asserções.

## 6. Conferência somente leitura no scratch

`pautaon_ensaio` (SELECT-only, via `.env` com `postgresql://`): `alembic_version = b8c9d0e1f2a3`; `conselho_classe` com 5 linhas, todas `situacao_final IS NULL` e 0 com `etapa = 'FINAL'`; 37 inscrições ativas, 7 turmas ativas, 10 ofertas ativas. Ou seja, o cenário **zero avaliados** é o estado real do scratch e foi coberto sem divisão por zero. Nenhum banco principal foi usado para semear testes (fixtures usam SQLite em memória, trava AJ6-C).

## 7. Arquivos que entram no pacote (sem script de deploy alterado)

- `app/services/relatorio_periodo_info.py`
- `app/relatorios/geral.py`
- `app/templates/relatorios/informacoes_gerais_periodo.html`
- `app/static/css/relatorios/informacoes_gerais_periodo.css`
- `app/static/img/logo_irn.png` (existente, sem alteração)
- `app/templates/relatorios/resultado_conselho.html`
- `scripts/verificar_imports.py`
- `tests/test_aj31_informacoes_gerais_periodo.py` (novo)
- `tests/test_aj1_servico_social_relatorios.py` (somente o helper `_rotas_relatorios`)
- Documentação: `backlog_desenvolvimento.md`, `app/models/MER.md`, este relatório.

**Fora do pacote, intactos:** migrations, schema, permissões, banco principal, `aplicar_deploy.ps1`, `empacotar_deploy.ps1`, `deploy_pacotes/`, `app/utils/logica.py` (o `# noqa: F401` de `get_local_now` é resíduo fora do escopo autorizado).

## 8. Pendências

- Nenhuma pendência funcional da AJ31-B: suíte final sem as 5 falhas da linha de base e contratos AJ26–AJ30 preservados.
- Validação visual do PDF A4 retrato em navegador real: o contrato está coberto por testes de template/CSS/JS e pela conferência no scratch; não foi gerado artefato de deploy nem executado navegador neste fechamento.
- `app/relatorios/geral copy.py` e `get_local_now` em `app/utils/logica.py:56` seguem como resíduos já identificados, fora do escopo autorizado — não foram apagados nem alterados.
- Nada foi commitado, pushado, mesclado ou deployado.
