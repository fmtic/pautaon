# AJ21 — Resumo e impressão das respostas do conselho

> **Adendo AJ21-B (13/11/2026):** as duas rotas do AJ21 foram unificadas em
> **uma página só** — ver a seção "AJ21-B" ao final. O conteúdo abaixo
> descreve a etapa original (duas rotas), mantido como histórico.

**Data:** 13/11/2026
**Branch:** `nova_feature`
**Base:** `6e43bc9` (sem push/merge)
**Schema:** nenhuma migration; nenhuma alteração de modelo/tabela.

## ETAPA 0 — leitura e linha de base

- Rotas existentes do conselho usam `ofertas_ativas(turma)` e `_resolver_oferta_conselho` (política M1: 0/1/2+ ofertas), com isolamento por unidade (`get_unidade_id` + `assert_unidade_context`) e gravação restrita a admin/pedagógico/professor da oferta (AJ7-D).
- Desde o AJ20, `GET /conselho/lancamento` não cria `ConselhoClasse`; `cond_conselho_sem_conteudo()` (`app/services/conselho_leitura.py`) define casca ≡ ausente.
- AJ19 consolidou a observação geral em `ConselhoClasse.observacao` (`obs_<aluno>`, 5000 caracteres, `white-space: pre-line`) e aposentou `ConselhoResposta.observacao` sem migration.
- O parecer coletivo vive em `TurmaCurso.avaliacao_inicial/percurso/final` (JSON), mapeado por `ETAPA_PARA_CAMPO_AVALIACAO`.
- Linha de base informada: **1776 passed**. A suíte final desta etapa fechou em **1806 passed** (+30 testes AJ21), sem falhas.
- Observação de ambiente: os goldens AJ7-D já estavam defasados em relação ao HTML do HEAD antes desta etapa (verificado em worktree destacado no mesmo dia). Como o AJ21 altera intencionalmente as duas telas, os hashes foram regravados e o motivo está comentado no próprio teste.

## Decisões

1. **Duas rotas dedicadas, sem POST:** o resumo individual e o coletivo são GET puros. Nenhum caminho cria/atualiza `ConselhoClasse`, `ConselhoResposta` ou `TurmaCurso`.
2. **Um único guarda de perfil** (`_ROLES_RESUMO_CONSELHO` = admin/pedagógico/secretaria). Professor e demais perfis recebem 403 antes de consultar turma/oferta.
3. **Reutilização da política de oferta:** `_resolver_oferta_conselho` + `_escolha_fora_das_ativas`. Com 2+ ofertas, `turma_curso_id` é obrigatório; oferta inativa, de outra turma ou inexistente → 404. Com 1 oferta, a escolha explícita inválida também é recusada.
4. **Resumo individual lista todos os alunos ativos da oferta**, não apenas quem tem linha em `ConselhoClasse`. Quem não tem linha (ou só tem casca) aparece como “Sem respostas registradas”.
5. **Uma consulta de respostas para toda a oferta/etapa**, agrupada por `conselho_id` em memória. Perguntas são carregadas em uma consulta pelos ids respondidos; a numeração vem da ordenação estável de `pergunta_id`.
6. **Perguntas inativas com resposta salva entram**; perguntas sem resposta não entram no individual. A etiqueta “inativa” é visual, não filtro de histórico.
7. **Coletivo em layout de formulário**, lendo o JSON da oferta e exibindo apenas as perguntas TURMA com resposta gravada (inclusive inativas), na ordem de `pergunta_id`. Valores `NULL`/vazios não imprimem o literal “None”.
8. **Cabeçalho compartilhado** (`_resumo_cabecalho.html`) nos dois resumos: logo institucional, turma, oferta/curso, professor, etapa, período letivo com datas, emissão/atualização e usuário logado. Impressão em paisagem, botões/navegação ocultos no print.
9. **Sem foto de aluno** nos resumos: nenhum template referencia foto/URL de foto.
10. **Link “Editar”** aponta para o lançamento da mesma oferta/etapa com `#aluno-<id>`; o JS de paginação do lançamento foi ajustado para abrir o card do aluno da âncora.
11. **Painel pedagógico:** o card do conselho passa a listar as três etapas (incluindo FINAL) e a avaliação coletiva; a barra sem rótulo foi substituída por “opção + contagem”. Cada oferta/etapa tem link para abrir o resumo em nova janela, exibido apenas para os três perfis autorizados; os demais continuam vendo os dados agregados. A montagem usa `ofertas_ativas` e mantém os filtros lazy do AJ20.
12. **Botões “Ver respostas”** em `lancamento.html` e `turma_aval.html` apenas para os três perfis, com `target="_blank" rel="noopener"`.

## Arquivos alterados

- `app/conselho.py` — rotas `resumo_conselho` e `resumo_avaliacao_turma`, helpers de perfil/turma/oferta/etapa e montagem dos dados.
- `app/templates/conselho/resumo_conselho.html` — resumo individual/impressão.
- `app/templates/conselho/resumo_avaliacao.html` — resumo coletivo/impressão.
- `app/templates/conselho/_resumo_cabecalho.html` — cabeçalho comum dos dois resumos.
- `app/templates/conselho/lancamento.html` — botão “Ver respostas” e `data-aluno-id` por card.
- `app/templates/conselho/turma_aval.html` — botão “Ver respostas” da avaliação coletiva.
- `app/static/js/conselho/conselho.js` — seleção do card via `#aluno-<id>`.
- `app/relatorios/painel_pedagogico/conselho.py` — etapa FINAL, `carregar_avaliacoes_coletivas` e distribuições.
- `app/relatorios/painel_pedagogico/turma.py` — merge de ofertas só com avaliação coletiva e mapa de perguntas.
- `app/templates/relatorios/painel_pedagogico.html` — links por etapa, lista opção+contagem e bloco coletivo.
- `tests/test_aj21_resumo_conselho.py` — 30 testes novos.
- `tests/test_aj7b_conselho_none.py` — varredura reconhece o novo template (coberto por R10).
- `tests/test_aj7d_gravacao_conselho.py` — goldens regravados para os links/`data-aluno-id`.
- `app/models/MER.md` — §8.2 e cabeçalho de atualização.
- `backlog_desenvolvimento.md` — entrada do AJ21.
- `docs/Relatórios/AJ21_ResumoConselho.md` — este relatório.

## Consultas, EXPLAIN e prova de ausência de N+1

Fluxo do resumo individual (por requisição):

1. Turma com escopo de unidade (1 consulta).
2. Ofertas ativas da turma (1 consulta; `ofertas_ativas`).
3. Alunos ativos da oferta via join `inscricoes` × `aluno` (1 consulta).
4. Conselhos da oferta/etapa para os alunos (1 consulta).
5. Respostas de todos os conselhos em uma única consulta (`conselho_id IN (...)`).
6. Perguntas respondidas em uma única consulta (`conselho_pergunta.id IN (...)`).
7. Cabeçalho: curso/professor/período por lazy load da própria oferta/turma (constante, não por aluno).

Contagem instrumentada com `before_cursor_execute` no app de teste (SQLite), variando apenas o número de alunos:

| Cenário | Alunos | Queries — resumo individual | Queries — resumo coletivo |
|---|---:|---:|---:|
| Base | 2 | 22 | 18 |
| Ampliado | 7 | 22 | 18 |

A contagem não varia com o número de alunos, o que evidencia ausência de N+1 por aluno. O resumo coletivo também não varia com o número de perguntas (as perguntas vêm em uma consulta).

`EXPLAIN QUERY PLAN` representativo (SQLite, schema de teste):

```text
-- alunos
SEARCH inscricoes USING INDEX ix_inscricoes_turma_curso_id (turma_curso_id=?)
SEARCH aluno USING INTEGER PRIMARY KEY (rowid=?)
USE TEMP B-TREE FOR DISTINCT
USE TEMP B-TREE FOR ORDER BY

-- conselhos
SEARCH conselho_classe USING COVERING INDEX uix_conselho_oferta
  (turma_curso_id=? AND aluno_id=? AND etapa=?)

-- perguntas
SEARCH conselho_pergunta USING INTEGER PRIMARY KEY (rowid=?)
```

A consulta de respostas (`conselho_resposta WHERE conselho_id IN (...)`) aparece como `SCAN conselho_resposta`: não há índice em `conselho_id` no modelo atual. É uma leitura única por oferta/etapa (não por aluno) e o volume histórico do conselho é pequeno; criar índice exigiria migration, fora do escopo desta etapa. Risco registrado abaixo.

## Verificações executadas

- `tests/test_aj21_resumo_conselho.py`: **30 passed**.
- Direcionados de conselho/AJ20/painel: **65 passed** e **19 passed** nos grupos executados; AJ7-B/AJ7-D verdes após o ajuste da varredura/goldens.
- Suíte completa: **1806 passed, 0 failed** (`1806 passed, 1089 warnings in 1341.81s`).
- `ruff check --select F821,F811,F841` nos arquivos Python tocados: limpo.
- `git diff --check`: limpo.
- `GET` do resumo não cria `ConselhoClasse` (teste R2 compara a contagem antes/depois).
- Nenhuma migration criada; `git status` contém apenas código/templates/testes/docs desta etapa (e o `test_append2.txt` pré-existente, intocado).

## Riscos e limitações

- **Scan em `conselho_resposta`:** a consulta em lote por `conselho_id IN (...)` varre a tabela por falta de índice na FK. Sem migration nesta etapa; se o histórico crescer muito, avaliar índice em `conselho_resposta.conselho_id` (ou composto com `aluno_id`).
- **Casca ≠ ausente apenas na leitura:** o resumo ignora casca para conteúdo, mas não apaga linhas antigas. A limpeza continua sendo decisão separada (AJ20-F2 só remove casca na exclusão física de turma).
- **Coletivo mostra só perguntas TURMA com resposta gravada** (perguntas inativas com resposta continuam entrando; respostas `NULL`/vazias não entram). O individual segue a mesma regra de omitir pergunta sem resposta.
- **Goldens AJ7-D:** foram regravados porque as telas ganharam o link “Ver respostas” e o atributo `data-aluno-id`. Como o HTML é sensível a mudanças de template, qualquer ajuste visual futuro nessas telas exige nova gravação consciente.
- **Painel:** o mapa de perguntas (`PerguntaConselho.query.all()`) é montado por turma na visão do painel. O volume de perguntas é pequeno e não há N+1 por aluno/oferta; se o painel passar a listar muitas turmas, vale mover o mapa para o nível da visão.
- **Sem push/merge:** as alterações permanecem no working tree da branch `nova_feature`, conforme solicitado.

---

## AJ21-B — Unificação em "Resumo do Conselho de Classe" (13/11/2026)

**Pedido:** substituir as duas rotas/templates do AJ21 por UMA rota e UM
template, sem migration, sem push/merge.

### O que mudou

- **Rota única:** `GET /conselho/resumo/<turma_id>?etapa=<INICIAL|PERCURSO|FINAL>&turma_curso_id=<id>&aluno_id=<opcional>`
  (`resumo_conselho` em `app/conselho.py`). Mesmos guardas do AJ21:
  `_exigir_resumo_conselho` (admin/pedagógico/secretaria; professor e
  demais 403), `_turma_do_contexto` (isolamento por unidade),
  `_oferta_do_resumo` (política 0/1/2+; 2+ sem `turma_curso_id` → 404) e
  GET que nunca escreve.
- **Removidos sem redirecionamento:** a rota `resumo_avaliacao_turma`
  (`GET /turma/<id>/avaliacao/resumo`) e o template
  `conselho/resumo_avaliacao.html` — nunca foram para produção. O teste
  R2 garante 404 no cliente e `BuildError` no `url_for`, e uma varredura
  dos templates confirma que não sobrou referência.
- **Template único** `conselho/resumo_conselho.html` (título "Resumo do
  Conselho de Classe") + `_resumo_cabecalho.html`:
  - Cabeçalho: logo, instituição, turma, oferta/curso, professor, etapa,
    período letivo com datas, colaborador logado e **uma** linha
    "Emitido em" (a duplicata "Atualizado em" foi removida).
  - Barra de ações `no-print`: Imprimir, Atualizar e seletor de etapa
    (Inicial | Percurso | Final) preservando `turma_curso_id` e
    `aluno_id`.
  - **Seção 1 — Avaliação individual dos alunos:** por aluno, somente
    perguntas respondidas, cada uma em linha "N. Pergunta" + resposta
    escolhida (`"B) texto"` para opções; texto puro para dissertativa —
    alternativas não escolhidas nunca aparecem no HTML); observação do
    aluno em `.obs-box` (`white-space: pre-line`, escape Jinja mantido);
    nome = `nome_social or nome`; `autor_nome` da última gravação
    discreto no cabeçalho do aluno; aluno sem conteúdo → "Sem respostas
    registradas."; pergunta inativa com resposta → etiqueta "inativa".
  - **Seção 2 — Avaliação coletiva do curso (oferta):** somente
    perguntas TURMA com resposta no JSON `turma_curso.avaliacao_<etapa>`
    (mesmo formato de alternativa escolhida) + `_obs` em `pre-line`;
    vazio → "Sem avaliação coletiva registrada para esta etapa."
  - **Edição:** "Editar" por aluno (âncora `#aluno-<id>` no lançamento —
    o JS de paginação seleciona o card via `data-aluno-id`) e "Editar
    avaliação da turma" (`avaliar_turma`), ambos **somente para admin e
    pedagógico**; secretaria lê sem ações.
  - **Impressão:** `@page` paisagem, `no-print` em botões/seletor,
    `break-inside: avoid` no bloco do aluno e **nenhuma foto de aluno**
    (teste R9 garante ausência de `<img>` de aluno).
- **Origem dos links:** um único "Ver respostas" por tela —
  `lancamento.html`, `turma_aval.html` e o card do painel pedagógico —
  todos `target="_blank" rel="noopener"` e restritos aos 3 perfis.
- **Consultas:** a página única mantém as mesmas consultas em lote do
  AJ21 (alunos, conselhos, respostas e perguntas em consultas únicas);
  o teste R10 prova contagem constante de queries com 2 × 7 alunos.

### Testes

`tests/test_aj21_resumo_conselho.py` reescrito para a rota única:
**38 testes** cobrindo R1–R11 (perfis/403/isolamento, rota antiga
removida, individual+coletivo juntos, só alternativa escolhida com
letra, dissertativa sem letra, escape e `pre-line` nas duas
observações, nome social, Editar por perfil, seletor preservando
turma_curso_id, FINAL, GET sem escrita, oferta 2+ sem escolha → 404,
pergunta inativa, sem foto, N+1 constante e "Ver respostas" nas três
telas de origem).

### Verificações

- `tests/test_aj21_resumo_conselho.py`: **38 passed**.
- Direcionados de conselho/AJ19/AJ20/AJ7-B/AJ7-D: **147 passed**.
- Suíte completa: **1814 passed, 0 failed** (`1814 passed, 1089 warnings in 1343.19s`) — base 1806 + 8 testes líquidos do AJ21-B.
- `ruff check --select F821,F811,F841` nos arquivos Python tocados: limpo.
- `git diff --check`: limpo.
