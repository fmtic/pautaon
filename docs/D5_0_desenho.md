# ETAPA D5.0 — Desenho do conselho de classe por oferta (SOMENTE LEITURA)

**Data:** 25/10/2026
**Decisão do responsável (24/10/2026, MER §12.18):** o conselho de classe passa a ser por **oferta** (`TurmaCurso`).
**Nesta etapa:** nenhum arquivo de código, teste, migration ou doc existente foi alterado; nenhum commit foi feito. Este documento é exclusivamente desenho e plano.
**Fontes:** `app/models/MER.md` (§6.5, §7.21–§7.25, §8.2, §8.10, §12.18), `backlog_desenvolvimento.md` e leitura direta do código atual.

---

## Passo 1 — Mapa do conselho no código atual (arquivo:linha)

### 1.1 Modelos

| Onde | O quê |
|---|---|
| `app/models/conselho.py:33` | `PeriodoConselho` — janela do conselho por `periodo_letivo_id` + `unidade_id`; `conselho_final` (L50); cascade do `PeriodoLetivo` (L55-58) |
| `app/models/conselho.py:64` | `PerguntaConselho` — `etapa` (L80), `tipo` TURMA/ALUNO (L89), `texto`/`opcoes` (L100-101); soft-delete |
| `app/models/conselho.py:104` | `OpcaoProximaTurma` — catálogo de destinos pós-conselho final |
| `app/models/conselho.py:115` | `ConselhoClasse` — UNIQUE `uix_conselho_turma_aluno_etapa` `(turma_id, aluno_id, etapa)` (L132-134); CHECK `ck_conselho_situacao_final` (L135-139); `turma_id`/`aluno_id` (L143-144); `etapa` (L147); `concluido` (L159); `situacao_final` (L164); `proxima_turma_id` (L166-169); **não tem `turma_curso_id`** |
| `app/models/conselho.py:176` | `ConselhoResposta` — FK `conselho_id` (L186), `aluno_id` nullable (L189), `pergunta_id` (L190), `resposta`/`observacao` |
| `app/models/academico.py:133-136` | `Turma.avaliacao_inicial/percurso/final` (Text/JSON) e `Turma.conselho_concluido` (bool NOT NULL default false) |
| `app/models/academico.py:138` | `Turma.conselhos` → relationship `ConselhoClasse`, backref `turma` |
| `app/models/academico.py:264` | `TurmaCurso` (a oferta): `principal` (L307), `programa` NOT NULL (L327) — destino natural dos novos campos por oferta |
| `app/models/enums.py:146-149` | `ETAPA_PARA_CAMPO_AVALIACAO` (INICIAL/PERCURSO/FINAL → `avaliacao_*`); exportado em `__all__` (L165) |
| `app/models/__init__.py:28,53,86` | exports do domínio `conselho` |

### 1.2 Rotas de escrita/leitura do conselho — `app/conselho.py`

| Onde | O quê |
|---|---|
| `:40` `_build_turma_avaliacao_payload` / `:58` `_get_turma_avaliacao_respostas` | serializam/lêem parecer coletivo da **turma** nos campos `avaliacao_*`, mapa etapa→campo duplicado inline (L60-64) |
| `:79` `_normalize_conselho_request` | normaliza POST só com `turma_id` (sem oferta) |
| `:120` `index_conselho` (`GET /conselho`) | painel: lista `Turma.ativo` (L133-144), sem dimensão oferta |
| `:157/:187/:218` `gerenciar_perguntas`/`salvar_pergunta`/`excluir_pergunta` | CRUD `PerguntaConselho` (global entre unidades, L172) |
| `:235` `lancamento_conselho` (`GET /conselho/lancamento?turma=&etapa=`) | alunos via `Inscricao.turma_id` (L279-283, **sem `distinct`** — aluno com 2 ofertas ativas aparece 2×); cria um `ConselhoClasse` por aluno/turma/etapa (L292-304); respostas lidas por `turma_id`+`etapa` (L327-331) |
| `:347` `salvar_conselho` (`POST /conselho/salvar`) | `conselho_map` por `aluno_id` (L361-364); respostas tipo TURMA (`aluno_id=None`) são anexadas ao **primeiro** `ConselhoClasse` da turma (L384-395, `conselhos_turma[0]` L395) |
| `:425` `fechamento_turma` (`GET /conselho/fechamento/<turma_id>`) | stats por `Frequencia(aluno_id, turma_id)` (L452); lista fixa de "próximas turmas" hardcoded (L443-448, duplica `OpcaoProximaTurma`) |
| `:477` `salvar_fechamento_data` (`POST /fechamento/<turma_id>/salvar`) | cria/atualiza `ConselhoClasse` FINAL por aluno (L490-510): `situacao_final`, `proxima_turma_id`, `concluido=True` |
| `:525` `avaliar_turma` (`GET/POST /turma/<turma_id>/avaliacao`) | grava JSON das perguntas tipo TURMA em `Turma.avaliacao_*` (L543-551; mapa inline de novo L544-548) |
| `:570` `informacoes` (`GET /informacoes`) | lista `PeriodoConselho` (L578); `turmas_pendentes` = `Turma.conselho_concluido=False` (L580) |
| `:588/:669` `salvar_periodo_conselho`/`deletar_periodo_conselho` (`/api/conselho-periodo` [POST], `/api/conselho-periodo/<id>` [DELETE]) | CRUD `PeriodoConselho`; um único `conselho_final=True` por unidade (L636-638) |

### 1.3 Planejamento — `app/planejamento.py`

| Onde | O quê |
|---|---|
| `:10` `salvar_configuracao_conselho` (`POST /configurar-conselho`) | datas globais em `ConfiguracaoSistema` (`inicio_conselho`/`fim_conselho`, L18-28) |
| `:39` `alternar_conselho` (`POST /turma/alternar-conselho/<turma_id>`) | **toggle `turma.conselho_concluido`** (L52), com isolamento B4 (L49) |

### 1.4 Serviços e utilitários

| Onde | O quê |
|---|---|
| `app/services/turma_curso.py:56-94` `turma_tem_historico` | `ConselhoClasse.query.filter_by(turma_id=...)` (L85) — conselho **por turma** impede exclusão física |
| `app/services/turma_curso.py:482-539` `_alunos_ativos_em_andamento`/`desativar_oferta` | guarda M4: recusa desativar oferta com aluno ativo em período em andamento (usada em `app/registros/turmas.py:1652-1655`) |
| `app/utils/logica.py:642-700` `calcular_metricas_conselho` | `progresso_reunioes`/`turmas_concluidas` contam `Turma.conselho_concluido` (L684-693) |
| `app/registros/core.py:30` | importa `PerguntaConselho` (sem uso aparente no arquivo — import morto a confirmar); `:785-786` lê `inicio/fim_conselho` no painel de planejamento |

### 1.5 Registros (rotas de turmas/alunos/períodos)

| Onde | O quê |
|---|---|
| `app/registros/turmas.py:17,990` | `ver_turma` carrega todas as `PerguntaConselho` para o modal de conselho da ficha da turma |
| `app/registros/turmas.py:1663-1728` `excluir_turma` | com histórico (L1680-1698): exclusão **lógica**, preserva `ConselhoClasse`; sem histórico (L1700-1714): física (não toca conselho por definição — não existe) |
| `app/registros/alunos.py:828-884,914-916` `historico_aluno` | `get_conselho(etapa)` por `(turma_id, aluno_id)` (L877-880); colunas de status inicial/percurso/final do histórico impresso |
| `app/registros/periodos.py:519-583` `periodo_letivo_relatorio_certificado` | certificado: `ConselhoClasse` FINAL por `(turma_id, aluno_id)` (L551-555); `turma.conselho_concluido` (L577) |

### 1.6 Relatórios, BI e Painel Pedagógico

| Onde | O quê |
|---|---|
| `app/relatorios/conselho.py:13-125` `resultado_conselho` (`GET /relatorios/conselho`) | etapa FINAL filtrada por `turma_id` (L53-57); `Inscricao`/`Frequencia` por `turma_id` (L65-73); `proxima_turma` (L77); template `relatorios/resultado_conselho.html:213` + `static/js/relatorios/resultado_conselho.js` |
| `app/relatorios/painel_pedagogico/conselho.py:11-87` `por_turma` | agregação por `ConselhoClasse.turma_id` (L16-18); **L35 usa `p.enunciado` — atributo inexistente** (`PerguntaConselho` tem `texto`): AttributeError latente quando há respostas |
| `app/relatorios/painel_pedagogico/ficha_aluno.py:277-351` `_conselho` | conselhos por `(aluno_id, turma_id)` (L279-283); diff Inicial×Percurso usa `p.texto` corretamente (L341); `_sinais` lê `situacao_final` (L357, L563-567); importa `PeriodoConselho` (L35) |
| `app/relatorios/bi_alunos.py:2517-2566` `alunos_raca_conselho` (CRU-002, registrado em `app/relatorios/bi.py:66`) | join `ConselhoClasse`→`Turma` por `turma_id` (L2536); conta `distinct aluno_id` (L2549) — sem dimensão oferta |
| `app/relatorios/bi_alunos.py:2667-2700+` `desempenho_conselho_por_renda` (CRU-005, `bi.py:69`) | idem, agrupa por `situacao_final` (L2698) |
| `app/relatorios/geral.py:22,73,101` | usa `calcular_metricas_conselho` → "Painel do Conselho" em `templates/relatorios/geral.html:60-89` |
| `app/relatorios/indicadores.md:341-358` | documentação CRU-002/CRU-005 (lerá `ConselhoClasse`+`Turma`) |

### 1.7 Templates e JS

| Onde | O quê |
|---|---|
| `templates/conselho/painel.html` | painel (links por turma, sem oferta) |
| `templates/conselho/lancamento.html` (`:91` carrega `js/conselho/conselho.js`) | seletor `?turma=`, grade aluno×pergunta, campo turma `resp_turma_<id>` |
| `templates/conselho/fechamento.html` (`:169`) | grade de fechamento; POST AJAX via `conselho.js:208-238` (`window.location.pathname + "/salvar"`) |
| `templates/conselho/turma_aval.html` | formulário de avaliação coletiva por turma/etapa |
| `templates/conselho/informacoes.html` (`:141-223`) | CRUD inline de `PeriodoConselho` via `/api/conselho-periodo` |
| `templates/conselho/perguntas.html` (`:273`) | gestão de perguntas |
| `templates/conselho/relatorio.html` | **órfão** — nenhuma rota o renderiza (grep em `app/` não retornou) |
| `templates/turmas/detalhe.html:349-374` | dropdown "CONSELHO DE CLASSE" (links `/conselho/lancamento?turma={{turma.id}}&etapa=...`) e `modalConselho` com `form action="/conselho/salvar"` |
| `templates/periodos/lista.html:51-88` | coluna "Conselhos" (backref `p.conselhos`) |
| `templates/periodos/certificado.html`, `templates/relatorios/ficha_aluno.html`, `templates/relatorios/painel_pedagogico.html`, `templates/relatorios/resultado_conselho.html`, `templates/relatorios/geral.html:60-89` | telas de saída com dados de conselho |
| `templates/partials/sidebar.html:70` e `templates/base.html` | menu do domínio |
| `static/js/app.js:3-8` `abrirModalConselho` | modal da ficha da turma |
| `static/js/conselho/conselho.js` | validação de lançamento (L91-146) e fechamento AJAX (L207-238) |
| `static/js/periodos/conselhos.js` | **órfão/quebrado** — chama `/periodos/<id>/conselhos/novo` e `/conselhos-periodo/<id>/editar|excluir`, rotas que **não existem** no backend (grep 0 ocorrências em `*.py`), e nenhum template o referencia |

### 1.8 Tests atuais que tocam conselho

| Onde | O quê |
|---|---|
| `tests/test_isolamento_unidade_escrita.py` | isolamento nas rotas de escrita do conselho (B4) |
| `tests/test_turma_curso_exclusao.py` | `ConselhoClasse` como histórico que bloqueia exclusão física de turma (Etapa I) |

### 1.9 Achaços (anotar, não corrigir nesta etapa)

1. `painel_pedagogico/conselho.py:35` — `p.enunciado` não existe em `PerguntaConselho` (é `texto`): bug latente.
2. `conselhos.js` e `templates/conselho/relatorio.html` — órfãos (nenhuma rota/referência).
3. `ETAPA_PARA_CAMPO_AVALIACAO` (`enums.py:146`) — definido e exportado, **nunca usado**; `app/conselho.py` duplica o mapa inline duas vezes (L60-64, L544-548).
4. `app/conselho.py:443-448` — lista hardcoded de "próximas turmas" ignorando o catálogo `OpcaoProximaTurma`.
5. `lancamento_conselho` (L279-283) — query de alunos sem `distinct`: com 2 ofertas ativas o mesmo aluno lista 2× (já é um sintoma atual da ausência da dimensão oferta).
6. Respostas tipo TURMA vivem **dois lugares** diferentes: JSON em `Turma.avaliacao_*` (rota `avaliar_turma`) e `ConselhoResposta` com `aluno_id=None` anexado ao primeiro conselho da turma (rota `salvar_conselho` L384-395) — inconsistência a resolver no desenho.

---

## Passo 2 — Desenho proposto (sem implementação)

### 2.1 Princípio

A unidade de conselho passa a ser **(oferta, etapa)**: `ConselhoClasse` vinculado a `turma_curso_id`, tal como `Inscricao` desde `c3d4e5f6a7b8`. `turma_id` permanece denormalizado (escopo tenant, joins legados e `turma_tem_historico`), com regra de consistência aplicada na aplicação: `conselho.turma_id == oferta.turma_id`.

### 2.2 Colunas novas

| Tabela | Coluna | Tipo | Nota |
|---|---|---|---|
| `conselho_classe` | `turma_curso_id` | FK → `turma_curso.id`, **nullable na fase 1, NOT NULL na fase final** | espelha a trajetória de `inscricoes.turma_curso_id` (Fase 1 → `c3d4`) |
| `conselho_classe` | índice | `ix_conselho_turma_curso` | leitura por oferta |
| `turma_curso` | `conselho_concluido` | bool NOT NULL default false | encerramento **por oferta** (substitui `Turma.conselho_concluido`) |
| `turma_curso` | `avaliacao_inicial`, `avaliacao_percurso`, `avaliacao_final` | Text (JSON), nullable | pareceres coletivos (perguntas tipo TURMA) por oferta (substituem os de `Turma`) |

As colunas legacy de `Turma` (`conselho_concluido`, `avaliacao_*`) ficam **somente-leitura** durante a transição e são aposentadas na última etapa (com decisão do responsável — Q1/Q3).

### 2.3 UNIQUE

- Atual: `uix_conselho_turma_aluno_etapa` `(turma_id, aluno_id, etapa)`.
- Nova: `uix_conselho_oferta_aluno_etapa` `(turma_curso_id, aluno_id, etapa)`.
- A antiga é **substituída** (não coexistem) na migration de endurecimento: com `turma_curso_id` NOT NULL, a unicidade por oferta é estritamente mais fraca por aluno e mais forte por oferta — mantém "um conselho por aluno/oferta/etapa", permitindo que o **mesmo aluno em 2+ ofertas da mesma turma tenha um conselho por oferta** (requisito explícito).

### 2.4 ConselhoResposta e perguntas tipo TURMA

- Respostas **individuais** (`tipo=ALUNO`): inalteradas — `ConselhoResposta` continua pendurado em `ConselhoClasse`, que agora é por oferta. O `aluno_id` da resposta passa a ser validado contra as inscrições **da oferta** daquele conselho.
- Respostas **coletivas** (`tipo=TURMA`): deixam de ser anexadas ao "primeiro conselho" (achado 6). Proposta: persistir o JSON por oferta nos novos campos `turma_curso.avaliacao_*` (mesma codificação atual de `avaliar_turma`, movendo o portador de `Turma` para `TurmaCurso`), e **descontinuar** o gravador paralelo em `salvar_conselho` (o form de lançamento passa a só gravar respostas ALUNO; o link de "avaliação da turma" vira "avaliação da oferta"). Alternativa estruturada (tabela `conselho_avaliacao_coletiva` linha a linha) fica como evolução futura — Q5.
- `PerguntaConselho` e `OpcaoProximaTurma`: permanecem **globais** (catálogos; sem dimensão oferta — §4 item 8 do MER).

### 2.5 situacao_final e proxima_turma_id por oferta

Ambos continuam colunas de `ConselhoClasse` — portanto, naturalmente por oferta:
- `situacao_final` (e a CHECK `ck_conselho_situacao_final`) passam a valer "por aluno+oferta+etapa". Um aluno pode ser `Aprovado` em uma oferta e `Desistente` em outra da mesma turma; certificados e fichas passam a exibir a situação **da oferta** consultada.
- `proxima_turma_id`: destino sugerido continua catálogo `OpcaoProximaTurma`, decidido por oferta (Q4). A lista hardcoded de `app/conselho.py:443-448` deve ser substituída pelo catálogo na mesma passada (D5.2).

### 2.6 Encerramento por PeriodoConselho

- `PeriodoConselho` (janela) permanece por **período letivo + unidade** — não ganha oferta (Q6). Ele continua sendo o relógio: o lançamento/fechamento de conselho de qualquer oferta da unidade ocorre dentro da janela do período.
- O **enceramento** passa a ser por oferta: `turma_curso.conselho_concluido=True` quando o conselho FINAL daquela oferta estiver fechado (todos os `ConselhoClasse` da oferta com `concluido=True`, ou toggle manual por oferta em `alternar_conselho`, que passa a receber `oferta_id`).
- `Turma.conselho_concluido` (enquanto existir) vira **derivado**: verdadeiro somente quando **todas as ofertas ativas** da turma estiverem concluídas (turma sem oferta ativa mantém compatibilidade com o flag legado — regra a confirmar, Q3). Leitores agregados (`informacoes` L580, `calcular_metricas_conselho` L684-693) passam a contar **ofertas**, não turmas.
- Interação com a **guarda M4** (`desativar_oferta`, `app/services/turma_curso.py:482-539`): desativar oferta só é permitido sem aluno ativo em período em andamento. Consequências para o conselho: (i) uma oferta desativada **preserva** seus conselhos (histórico por oferta — nenhuma cascata nova é necessária, pois `ConselhoClasse` referencia a oferta e `TurmaCurso` nunca some por via lógica); (ii) o encerramento de conselho **não** pode ser usado para "fechar" turma com ofertas ativas não concluídas — a contagem derivada garante isso; (iii) a exclusão física de turma continua bloqueada por `turma_tem_historico` — que passará a checar conselho também por `turma_curso_id` (equivalente, pois `turma_id` denormalizado é mantido; basta a checagem atual por `turma_id`).

### 2.7 Fluxo de telas

- Painel (`/conselho`) e lançamento (`/conselho/lancamento`): passam a ter **seletor de oferta** no mesmo padrão M1 (`?oferta_sel=`; turmas com 1 oferta vão direto; 2+ exigem escolha), reaproveitando `ofertas_ativas()` (`app/services/turma_curso.py:46`) e o padrão de `ver_turma`. Links de `detalhe.html:349-374` ganham `&oferta={{ oferta.id }}`.
- Fechamento e avaliação coletiva por oferta; modal de `detalhe.html` idem.

---

## Passo 3 — Plano de migração e backfill

Padrão adotado: o endurecimento de `c3d4e5f6a7b8`/`d4e5f6a7b8c9` — checagens **somente leitura** pré-DDL com `RuntimeError` único e mensagem acionável, **sem atribuir valor padrão por conta própria**, backfill automático apenas quando inequívoco (padrão `e7f3a1b9c4d5`: oferta única).

### 3.1 Migration D5-A (aditiva, reversível)

1. `add coluna conselho_classe.turma_curso_id` (nullable FK, `ondelete` compatível com a política de `TurmaCurso` — RESTRICT, pois oferta não some por via lógica) + `ix_conselho_turma_curso`.
2. `add turma_curso.conselho_concluido` (bool, server_default false) e `turma_curso.avaliacao_inicial/percurso/final` (Text nullable).
3. Backfill automático **somente** do caso 1:1:
   ```sql
   UPDATE conselho_classe cc SET turma_curso_id = o.id
   FROM turma_curso o
   WHERE o.turma_id = cc.turma_id AND o.ativo IS TRUE
     AND cc.turma_curso_id IS NULL
     AND (SELECT count(*) FROM turma_curso x
          WHERE x.turma_id = cc.turma_id AND x.ativo IS TRUE) = 1;
   ```
   (mesma semântica do backfill de `frequencia` em `e7f3a1b9c4d5`; oferta **inativa** com conselho não é alvo automático — vai para a lista manual).
4. Copia do flag: `UPDATE turma_curso o SET conselho_concluido = t.conselho_concluido FROM turma t WHERE t.id=o.turma_id AND t.conselho_concluido IS TRUE AND <turma tem exatamente 1 oferta ativa>`; idem para `avaliacao_*` (Q2 pode alterar isso).

### 3.2 Lista de decisão manual (script somente-leitura)

`scripts/verificar_onda4_d5.py` (mesmo formato dos `verificar_onda4_*.py`: exit 0/1 + relatório):
- **(a)** conselhos com `turma_curso_id` NULL após D5-A: turma com **0 oferta ativa** (legado) ou **2+ ofertas** — emitidos com `conselho_id, turma_id, aluno_id, etapa, concluido, situacao_final` e opções de vínculo (uma oferta por conselho existente, ou desdobrar em N — decisão do pedagógico por linha).
- **(b)** conselhos já **concluídos** (FINAL com `situacao_final`): marcados separadamente — aqui o vínculo errado tem consequência jurídica/certificado, prioridade máxima de revisão.
- **(c)** pares que violariam a nova UNIQUE após desdobramento manual: `(turma_curso_id, aluno_id, etapa)` duplicados.
- **(d)** divergência `Turma.conselho_concluido` vs. flags das ofertas (para a fase de derivação).
- **(e)** turmas com 2+ ofertas que têm `avaliacao_*` preenchidos (parecer coletivo legado sem dono por oferta — Q2).

### 3.3 Migration D5-B (endurecimento — espelho de `c3d4e5f6a7b8`)

Pré-checagens somente leitura, todas em um único `RuntimeError` se falharem:
1. `count(*) FROM conselho_classe WHERE turma_curso_id IS NULL` (com primeiros 20 ids, ativos vs. concluídos);
2. duplicatas `(turma_curso_id, aluno_id, etapa)`;
3. consistência `conselho.turma_id == turma_curso.turma_id` (vínculos manuais podem errar a oferta de outra turma);
4. (se Q3 decidir remover `Turma.conselho_concluido`) divergência flag legado × derivação por oferta.

DDL: `alter_column turma_curso_id NOT NULL`; `drop constraint uix_conselho_turma_aluno_etapa`; `create unique index uix_conselho_oferta_aluno_etapa (turma_curso_id, aluno_id, etapa)` (UNIQUE pleno, não parcial — conselho não tem semântica de "ativa"; se preferir permitir reabertura histórica com linhas múltiplas, usar parcial — Q7).

### 3.4 Riscos

- **Dados locais/produção com turmas sem oferta** (`turma_lixeira`, D3): terão conselhos NULL não-backfilláveis; a D5-B **recusa** o upgrade — precisa limpeza/vinculação manual antes (exatamente o comportamento desejado do padrão, mas trava o deploy até decisão; atenuante: script (a) lista tudo).
- **Conselhos concluídos com certificado emitido**: reatribuir oferta errada muda a situação exibida no certificado (`periodos.py:551-557`); mitigação: item (b) da lista manual com revisão obrigatória e backup antes (padrão `instance/backups/`).
- **Dump autêntico ausente (B5-P2, P1)**: o ensaio de upgrade scratch com dados reais de conselho **não pode ser feito hoje** — risco de descobrir NULLs só no servidor de produção; recomendação forte: obter o dump antes da D5-B (pendência já registrada no backlog).
- **Janela de transição**: com coluna nullable, rotas antigas gravam conselho sem oferta → novos NULLs surgem depois do backfill; mitigação: D5.2 (rotas por oferta) **antes** da D5-B, e checagem (1) da D5-B recalcular na hora do upgrade.
- **Performance**: `ix_conselho_turma_curso` necessário antes das leituras por oferta (painel/relatórios filtram `in_(ids)`).
- **SQLite (testes) vs. PostgreSQL (produção)**: drop de UNIQUE via `batch_alter_table` (padrão já usado); índice único novo criado nos dois.
- `scripts/preparar_deploy_onda4.py` precisa ganhar as novas checagens (ele revalida antes do deploy — mesma mensagem de saída referenciada pela D5-B).

---

## Passo 4 — Etapas executáveis e perguntas em aberto

### D5.1 — Esquema aditivo (D5-A)
- **Escopo:** `app/models/conselho.py` (`turma_curso_id` nullable + índice), `app/models/academico.py` (`TurmaCurso.conselho_concluido`/`avaliacao_*`), migration nova (aditiva + backfill 1:1 + cópia do flag 1:1), `scripts/verificar_onda4_d5.py` (somente leitura), `tests/test_d5_schema.py` (modelos + backfill em 0/1/2 ofertas), update de `scripts/preparar_deploy_onda4.py`.
- **Pronto:** suíte completa verde (291P + novos); migration roda em banco scratch (protocolo P1) e no local; script reporta (a)–(e) corretamente; **nenhuma rota alterada** (conselho continua por turma, coluna nova em branco para os casos ambíguos).

### D5.2 — Escrita por oferta (rotas + telas de lançamento/fechamento/avaliação)
- **Escopo:** `app/conselho.py` (`lancamento_conselho`, `salvar_conselho`, `fechamento_turma`, `salvar_fechamento_data`, `avaliar_turma`→ por oferta com `?oferta_sel=`; validação de aluno inscrito **na oferta** via `Inscricao.turma_curso_id`; substituir lista hardcoded L443-448 por `OpcaoProximaTurma`; gravar `turma_curso_id` em todo conselho novo), `app/planejamento.py:alternar_conselho` (por oferta), templates `conselho/painel|lancamento|fechamento|turma_aval.html`, `turmas/detalhe.html` (links com oferta), `static/js/conselho/conselho.js`, `static/js/app.js`.
- **Testes:** `tests/test_conselho_oferta.py` (~12: seletor 0/1/2+ ofertas; aluno em 2 ofertas ganha 2 conselhos; recusa lançamento para oferta inativa; TURMA-type vai para `turma_curso.avaliacao_*`; fechamento por oferta; toggle por oferta com isolamento B4; duplicidade pela nova semântica) + atualização dos de isolamento (rotas mudam de parâmetro).
- **Pronto:** nenhum `ConselhoClasse` novo criado sem `turma_curso_id`; telas funcionam por oferta; suíte verde.

### D5.3 — Encerramento e contagens por oferta
- **Escopo:** `informacoes`/`turmas_pendentes` (contam ofertas), `calcular_metricas_conselho` (L684-693), `Turma.conselho_concluido` vira property derivada (todas as ofertas ativas concluídas) mantendo a coluna como cache legado somente-escrito pela derivação (decisão final em Q3); `periodos/certificado` (`registros/periodos.py:577`) e `templates/periodos/lista.html`.
- **Testes:** derivação (oferta única, 2 ofertas uma não concluída, turma sem oferta), `tests/test_d5_encerramento.py`.
- **Pronto:** encerramento/refleção de progresso corretos por oferta; nenhuma leitura nova de `turma.conselho_concluido` direto no SQL.

### D5.4 — Leitores: fichas, histórico, relatórios, BI (confluência com D3b-2/J3)
- **Escopo:** `registros/alunos.py:historico_aluno` (colunas por oferta; aluno com 2 ofertas vê blocos por oferta), `painel_pedagogico/ficha_aluno.py:_conselho` (parametrizar por oferta quando a ficha for por oferta), `painel_pedagogico/conselho.py:por_turma` (**corrigir `p.enunciado`→`p.texto`** — achado 1), `relatorios/conselho.py` (agrupar por oferta no registro), `bi_alunos.py` CRU-002/CRU-005 (join `TurmaCurso`; manter contagem `distinct aluno_id` — aluno em 2 ofertas não pode contar 2× em "alunos no conselho"; decisão Q6-b), `relatorios/indicadores.md` (atualizar descrição).
- **Testes:** `tests/test_d5_leitores.py` + ajustes em `test_bi_indicadores.py`/`test_pauta_professor.py` onde conselho aparece.
- **Pronto:** D3b-2 do conselho encerrado (nenhum leitor essencial por `turma_id` sem separar oferta); relatórios e certificados batem por oferta.

### D5.5 — Endurecimento (D5-B) + limpeza
- **Escopo:** migration de endurecimento (checagens §3.3), `drop` opcional das colunas legadas de `Turma` (só com decisão Q1/Q3), remoção dos órfãos (achados 2: `conselhos.js`, `conselho/relatorio.html`) **mediante autorização**, adoção de `ETAPA_PARA_CAMPO_AVALIACAO` eliminando os mapas inline (achado 3), update MER §6.5/§7.24/§8.2/§10/§11/§12.18 + backlog.
- **Pronto:** `conselho_classe.turma_curso_id` NOT NULL + `uix_conselho_oferta_aluno_etapa` em vigor; `scripts/preparar_deploy_onda4.py` validando; suíte verde; docs sincronizados.

### Perguntas em aberto (dependem do responsável) — com recomendação

| # | Pergunta | Recomendação |
|---|---|---|
| Q1 | Pareceres coletivos (`avaliacao_*`) vivem em `Turma` hoje. Movem para `turma_curso` (por oferta) ou ficam na turma? | **Mover para `turma_curso`** — o conselho (e a reunião que gera o parecer) é por oferta; turma mantém leitura derivada apenas se algo ainda a consumir. |
| Q2 | Para turmas 2+ ofertas com `avaliacao_*` legado preenchido: replicar o texto para todas as ofertas, atribuir à `principal`, ou deixar para decisão manual? | **Lista manual (item (e) do script)**; se o volume for alto, plano B: atribuir à oferta `principal` — nunca replicar cegamente (texto pode citar curso específico). |
| Q3 | `Turma.conselho_concluido`: apagar na D5.5 ou manter como propriedade derivada por período indefinido? | **Derivada como property Python e coluna removida na D5.5** — duas fontes de verdade é o que produziu os bugs de L2. |
| Q4 | `proxima_turma_id` e `situacao_final` por oferta confirmados (aluno pode ter destinos diferentes em ofertas diferentes)? O certificado deve imprimir o destino da própria oferta? | **Sim, por oferta**; certificado exibe situação/destino da oferta certificada. |
| Q5 | Respostas tipo TURMA hoje têm dois gravadores divergentes (JSON em `Turma` vs. `ConselhoResposta` `aluno_id=None`). Unificar só no JSON por oferta (proposto) ou criar tabela de respostas coletivas? | **Unificar no JSON por oferta** (menor risco, preserva o formato do `avaliar_turma`); tabela estruturada fica como evolução (dívida nova §12.x se aceito). |
| Q6 | `PeriodoConselho` (janela) permanece por período+unidade, sem dimensão oferta — confirmado? E nos BI CRU-002/005, contar "alunos distintos no conselho" ou "linhas aluno×oferta"? | **Janela continua por período+unidade**; BI conta **aluno distinto** (mudança de semântica mínima nos gráficos) com drilldown por oferta. |
| Q7 | Nova UNIQUE plena `(turma_curso_id, aluno_id, etapa)` ou parcial (permitindo reabertura com linhas históricas, como `inscricoes`)? | **Plena** — conselho é registro de resultado por oferta/etapa; reabertura deve editar a linha, não duplicar (mantém paridade com o comportamento atual). |
| Q8 | Remover os órfãos (`conselhos.js`, `conselho/relatorio.html`) e o import morto em `registros/core.py:30` na D5.5? | **Remover**, após `grep` final confirmando ausência de referência. |

---

**Conferência final:** `git status` nesta etapa não registra alteração em código/testes/migrations/docs existentes — apenas este arquivo novo (`docs/D5_0_desenho.md`), além do estado herdado das etapas anteriores (MER.md e backlog modificados na L2, não commitados).
