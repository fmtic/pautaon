# I1 — Informações do aluno para o professor da oferta (modal + pauta impressa)

**Data:** 28/10/2026 · **Branch:** `nova_feature` · **Head Alembic:** `c8d9e0f1a2b3` (sem migration)
**Suíte:** 870 → **904 passed** (34 novos, 0 falhas) · **Commits:** `372b588` (serviço+endpoint), `af67066`
(pauta/JS/modal), `ee256d3` (impressão), + este relatório no commit de docs.

---

## P0 — estado inicial

- `git status --porcelain` vazio; HEAD `8b90912` (V2), `origin/nova_feature` sincronizado.
- Suíte de partida: **870 passed** (confirmada no fechamento da V2).

## P1 — leitura (sem editar)

### Campos e rótulos

| Bloco | Campo | Tipo | Onde é editado | Onde é lido |
| --- | --- | --- | --- | --- |
| "Quem acompanha?" | `aluno.acompanhante_aulas` **+ flag** `aluno.vai_acompanhado_aulas` | `String(150)` + `Boolean NOT NULL` | `alunos/editar.html` (rótulo "Quem acompanha?", select Mãe/Pai/Avô-Avó/Irmão-Tio/Outro/Vai sozinho + `acompanhante_aulas_outro`), `alunos/novo.html` | pauta impressa (`dados_alunos_impressao`), ficha (`get_perfil_completo`) |
| "Informações para o professor da turma" | `perfil_diversidade.informacoes_para_professor` | `Text` | `alunos/editar.html` (textarea, rótulo idêntico) | pauta impressa, ficha |
| Medicação (fora do escopo) | `perfil_diversidade.saude_medicacao` (`Sim`/`Não`) + `saude_medicamento_nome` | `String(5)`/`String(150)` | mesma seção da ficha | pauta impressa |

Regra de "preenchido" **da impressão** (replicada): `acompanhante = aluno.acompanhante_aulas if
aluno.vai_acompanhado_aulas else None`, renderizado com `{% if %}` (texto vazio não imprime);
`informacoes_professor = perfil.informacoes_para_professor.strip() if perfil and ... else None`.

### Pauta impressa — guarda e separação das linhas

`imprimir_pauta` (`app/registros/turmas.py`) — guarda atual, **não alterada**:

1. perfil em `[admin, pedagogico, secretaria]` ou `professor` (senão 403);
2. `assert_unidade_context(turma.unidade_id, get_unidade_id())`;
3. professor só na **própria turma** (`turma.professor_id == current_user.id`).

Acompanhante, medicação e instruções são **três blocos independentes** no template
(`frequencia/imprimir_pauta.html`), alimentados por `dados_alunos_impressao` — portanto é possível
omitir acompanhante + instruções **sem tocar na medicação**. Sem TRAVA.

### Professor efetivo da oferta e data local

- Regra do sistema: `COALESCE(turma_curso.professor_id, turma.professor_id)` — usada nos filtros de
  turma (`registros/turmas.py`, `_filtro_por_oferta`) e em `ofertas_do_painel_conselho`
  (`app/services/turma_curso.py`: `oferta.professor or oferta.turma.professor`). Não existe função
  Python única; o I1 a materializou uma vez no serviço (`_condicoes_acesso`), documentada como a
  mesma regra.
- Data local: `app.utils.timezone.get_local_now()` (America/Sao_Paulo). Usado no serviço
  (`hoje_local()`).

### Telas em que o professor vê o nome do aluno (inventário, nada implementado)

`frequencia/lancar.html` (pauta — **alvo deste I1**), `turmas/detalhe.html`, `dashboard/professor.html`
(+`registros.core.painel_professor`), `turmas/observacoes.html` (por turma e visão global),
`conselho/lancamento.html` e painel por turma, `alunos/historico.html`, foto do aluno
(`/aluno/<id>/foto`), atendimento pedagógico, `alunos/gerenciar.html`, `alunos/transferir.html`,
relatórios/BI. Todas guardadas por **turma** ou por **perfil**; nenhuma exibe acompanhante/instruções
(registrado no backlog como decisão futura).

### TRAVAs da P1

- Nenhuma TRAVA bloqueante: os campos existem e têm o sentido esperado.
- Achado 1: `periodo_letivo.data_fim` é **NOT NULL** no schema. O ramo "`data_fim` nula" da regra
  permanece como defesa, mas não há como criar tal período pela aplicação — o caso testável é
  **turma sem período** (`periodo_letivo_id IS NULL`), coberto.
- Achado 2: `bi-chat-left-dots-fill` (classe do ícone) já era usada em `lancar.html` no rótulo
  "Observações da Aula" — os testes marcam presença do ícone por `btn-info-professor` +
  `data-aluno-id`, não pela classe do ícone.

## P2 — caracterização ANTES (worktree de HEAD)

Não existia teste que fixasse o comportamento da pauta impressa para acompanhante/instruções
(`grep` por "Quem acompanha"/`acompanhante_aulas` em `tests/`: nenhum). A caracterização foi escrita
para o worktree `.tmp/i1_antes` (HEAD `8b90912`) e executada **no código antigo**:

```
2 passed — test_antes_professor_dono_ve_acompanhante_e_instrucoes
           test_antes_periodo_encerrado_ainda_imprime_acompanhante_e_instrucoes
```

Leitura: o professor dono da turma **sempre** via as duas linhas (contrato preservado) e o período
encerrado **também** as imprimia (vazamento fechado pelo I1). Worktree removido com
`git worktree remove --force` (nenhum resíduo).

**Teste existente ajustado: nenhum.** O contrato do professor com acesso é idêntico antes/depois
(`tests/test_info_professor_impressao.py::test_impressao_professor_com_acesso_imprime_os_dois_blocos`),
e o caso do período encerrado (que mudou) só existia no worktree de caracterização.

## P3 — implementação

| Arquivo | Papel |
| --- | --- |
| `app/services/aluno_info_professor.py` | regra única: `_condicoes_acesso`, `_stmt_inscricoes_qualificadas` (**uma** consulta), `blocos_preenchidos`, `consultar_aluno_para_professor`, `alunos_com_info_professor` (lote) |
| `app/registros/alunos.py` | `GET /aluno/<id>/info-professor` (403/404/200 + `Cache-Control: no-store`, sem log) |
| `app/registros/core.py` | pauta: `alunos_com_info` para PROFESSOR (uma consulta em lote) |
| `app/templates/frequencia/lancar.html` | ícone condicional (só professor, só com bloco), modal Bootstrap e include do JS |
| `app/static/js/aluno_info_professor.js` | fetch + modal, `textContent`/`white-space: pre-wrap`, mensagens de 403/404/rede |
| `app/registros/turmas.py` | impressão: `alunos_com_info` (`None` = sem restrição) |
| `app/templates/frequencia/imprimir_pauta.html` | linhas de acompanhante/instruções condicionadas; medicação intacta |

## Tabela de casos de acesso (endpoint)

| Caso | Esperado | Teste |
| --- | --- | --- |
| professor da oferta, inscrição ativa, período vigente, 2 blocos | 200 (2 blocos) | `test_professor_da_oferta_ve_os_dois_blocos` |
| só acompanhante / só instruções | 200 (1 bloco, outro `null`) | `test_so_acompanhante_preenchido`, `test_so_instrucoes_preenchidas` |
| acompanhante com flag `vai_acompanhado_aulas=False` | 404 | `test_acompanhante_exige_a_flag_auxiliar` |
| nenhum bloco preenchido | 404 | `test_sem_nenhum_bloco_devolve_404` |
| aluno inexistente | 404 | `test_aluno_inexistente_devolve_404` |
| período futuro / turma sem período | 200 | `test_periodo_futuro_libera`, `test_turma_sem_periodo_letivo_libera` |
| aluno em 2 ofertas, uma qualificada | 200 | `test_aluno_em_duas_ofertas_uma_qualificada` |
| professor de outra turma | 403 | `test_outra_turma_devolve_403` |
| professor da mesma turma em oferta em que o aluno NÃO está inscrito | 403 | `test_mesma_turma_outra_oferta_devolve_403` |
| oferta inativa / turma inativa / inscrição inativa / aluno inativo | 403 | `test_oferta_inativa...`, `test_turma_inativa...`, `test_inscricao_inativa...`, `test_aluno_inativo...` |
| período encerrado com inscrição ainda ativa | 403 | `test_periodo_encerrado_devolve_403_mesmo_com_inscricao_ativa` |
| professor de outra unidade (isolando a unidade) | 403 | `test_professor_de_outra_unidade_devolve_403` |
| admin / pedagógico / secretaria / gerência / serviço social | 403 | `test_perfis_que_nao_sao_professor_recebem_403[5]` |
| medicação e idade | nunca na resposta (4 chaves) | `test_medicacao_e_idade_nunca_aparecem` |
| `Cache-Control` | `no-store` | `test_cache_control_no_store` |
| texto com `<script>` e quebra de linha | texto puro + `\n` preservado | `test_textos_com_html_nao_sao_interpretados` |
| JS sem HTML ativo | `textContent`, sem `.innerHTML` | `test_js_renderiza_texto_sem_innerhtml` |

Pauta e impressão: ícone só para professor (com/sem bloco, período encerrado), textos ausentes do
HTML, N+1 constante com 3 e 15 alunos, impressão com/sem acesso e para admin.

## P4 — testes

- Novos: `tests/test_info_professor.py` (25), `tests/test_info_professor_pauta.py` (6) e
  `tests/test_info_professor_impressao.py` (3) sobre `tests/_i1_helpers.py` (universo único: 2
  unidades, 7 perfis, 3 turmas, 4 ofertas).
- **Nenhum teste existente ajustado** (ver P2).
- Suíte completa: **904 passed** (870 + 34).

## P5 — ensaio (`pautaon_ensaio`, semente M1)

Diagnóstico do alvo via `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/ensaio_shell.ps1
-Diagnostico -Banco pautaon_ensaio`:
`postgresql+psycopg://postgres:***@localhost:5432/pautaon_ensaio` · revisão `c8d9e0f1a2b3`.

Driver (`.tmp/i1_ensaio.py`, fora do repositório): app apontado ao ensaio, login pela rota real,
ficha preenchida pelo `POST /aluno/editar/<id>` (GET + formulário completo), checks por HTTP e
limpeza. Alvo: aluno 1482 · turma 30 · oferta 44 · período 22 · professor `professor.m1@roteiro.local`
(id 120) · editor `secretaria.m1@roteiro.local`.

| Passo | Resultado |
| --- | --- |
| `POST /aluno/editar/1482` | 302 → `/alunos`; BD: acompanhante e instruções gravados |
| `GET /aluno/1482/info-professor` (professor da oferta) | **200**, `no-store`, blocos exatos, chaves `[acompanhante, aluno_id, instrucoes, nome]` |
| `GET /frequencia?turma_id=30&turma_curso=44` (professor) | **200**, ícone presente, textos ausentes do HTML |
| `GET /turma/30/imprimir-pauta?turma_curso=44` (professor, período vigente) | **200**, 5 × "Quem acompanha" |
| professor sem inscrição qualificada (criado no ensaio, removido depois) | **403** |
| período encerrado (`data_fim = ontem`) — endpoint | **403** |
| período encerrado — impressão (professor) | **200**, 5 tabelas, **0** acompanhante/instruções, **5** "Medicação regular" |
| período encerrado — impressão (secretaria) | **200**, 5 tabelas, **5** acompanhante/instruções |
| limpeza | campos da ficha e `data_fim` restaurados (`None`/`False`/`None`/`2026-12-31`); professor de ensaio removido |

Banco principal intocado (DSN do `.env` com apenas o nome do banco trocado; mascarada na saída).

Observações do ensaio (artefatos do harness, não da aplicação): (a) a turma da semente M1 tem
`turma.professor_id == professor`, então a guarda da impressão passa; (b) reutilizar o mesmo
`app.test_client` ao longo de mutações de período produziu leituras inconsistentes (0 linhas) — o
resultado da tabela acima foi confirmado em execução isolada por perfil.

## Docs

- MER: nova **§8.12** (blocos, regra única, endpoint, pauta, impressão, decisão pendente da
  medicação) e nota na §8.10 (impressão da pauta mensal).
- Backlog: seção do dia + duas pendências abertas (**decisão pendente com a instituição** sobre
  medicação e **inventário das outras telas**).

## Desvios e decisões

1. **Textos em JSON puro + `textContent`** (em vez de HTML escapado no servidor): satisfaz "sem HTML
   ativo" e "quebras preservadas" com uma única fonte de verdade; testado por round-trip do JSON e
   pela ausência de `.innerHTML` no JS.
2. **`acompanhante` com `strip()`**: a impressão usa a veracidade crua; o serviço considera
   "preenchido" apenas texto não vazio após `strip()` (espaços em branco não geram bloco nem ícone).
   Nenhuma diferença prática para dados reais.
3. **403 x 404 no endpoint**: separados por `consultar_aluno_para_professor` → `(tem_acesso, blocos)`,
   evitando duas consultas e vazamento de existência para quem não tem acesso.
4. **`alunos_com_info` no contexto da impressão** (`None` = sem restrição) evita espalhar a regra no
   template e mantém o resto da folha inalterado.
5. **Guarda da impressão não alterada**: professor que é apenas o professor da oferta continua sem
   abrir `/turma/<id>/imprimir-pauta` (comportamento anterior, registrado no MER).
