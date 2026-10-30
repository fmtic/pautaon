# ETAPA D3b.0 — Desenho da migração dos leitores restantes + Fases 5–7 + cobertura de rotas (SOMENTE LEITURA)

**Data:** 25/10/2026
**Modalidade:** somente leitura. Nenhum código, teste, migration, template ou doc existente foi alterado; nenhum commit. Este documento é o único artefato produzido (além do helper de varredura `instance/backups/d3b0_scan.py`, ignorado pelo Git).
**Estado de partida:** conselho de classe por oferta concluído (D5.1–D5.5, suíte **359 passed**); MER e backlog sincronizados na L3.
**Fontes:** `app/models/MER.md` (§8.2, §8.10, §10, §12.18–§12.24), `backlog_desenvolvimento.md` (seção 25/10 e “Pendências abertas”), `docs/D5_0_desenho.md` (formato), `docs/D5_4_relatorio.md` (§4 decisões e §5 pendências), `docs/B7_relatorio.md` (visão por período), leitura direta do código e varredura mecânica das rotas.

**Decisões já tomadas pelo responsável (não reabertas aqui):**
1. O aluno em duas ofertas tem **frequência separada** em cada oferta.
2. O BI conta **“alunos distintos” por padrão**.
3. O isolamento por unidade vale para **todos** os perfis (as leituras filtram pela unidade da sessão).
4. `Frequencia`/`RegistroAula` legados com `turma_curso_id IS NULL` existem e a coluna **continua nullable**.

**Nota sobre a especificação da Onda 4:** o texto original (“especificação de 390 linhas”, citado no backlog §“Onda 4 — Fases 0–4”, L221) **não está versionado em `docs/`** — a busca por “Onda 4”, “Fase 5”, “TurmaCurso” encontra apenas relatórios (B5, B6, D5_1, L1, L2, P1) e o backlog. O Passo 4 reconstrói o escopo das Fases 5–7 a partir do que ficou registrado no MER §8.10/§10, no backlog e nos comentários do código, e **marca explicitamente o que é reconstituição**.

---

## Passo 1 — Mapa dos leitores restantes (D3b-2/J3)

Legenda de classificação:
**OF** = já por oferta (correto) · **TUR** = por turma corretamente (explicado) · **MIG** = a migrar · **MIG-D** = a migrar com decisão.

### 1.1 Frequência e diário — `app/utils/logica.py`

| Onde | O quê | Classe | Observação |
|---|---|---|---|
| `:370` `carregar_frequencias(turma_id, data, turma_curso_id=None)` | leitura do dia | **OF** | com `turma_curso_id` filtra a oferta; sem ele cai no legado e ainda força `turma_curso_id IS NULL` (`:406`, `:409`) |
| `:420` `salvar_frequencia(form)` | escrita do dia | **OF** | resolve a oferta antes (`resolver_oferta_lancamento`), grava `turma_id` + `turma_curso_id` |
| `:589` `calcular_frequencias_relatorio` | relatório geral/Excel | **MIG** | `q_geral` (`:601`) e `f_turma` (`:621-623`) por `Frequencia.turma_id`; `f_prog` (`:609-618`) por **`Turma.programa`**; `f_prof` (`:631-637`) por **`Turma.professor_id`** |
| `:541` `calcular_estatisticas_idade` | relatório geral | **MIG-D** | média por programa via `Turma.programa` (`:554-568`); média por turma via `t.alunos` (`:570-580`) é correta porque a turma é o agrupador |
| `:642` `calcular_metricas_conselho` | KPI do relatório geral | **OF** | D5.3: `contar_ofertas_conselho` (`:689-694`) |

**Unidade sugerida para os MIG:** **oferta** para `f_turma`/`f_prog`/`f_prof` (uma linha por oferta ativa; turma sem oferta ativa mantém a linha legada por turma). **Comportamento com legado `NULL`:** as linhas legadas só entram quando a turma **não** tem oferta ativa (mesma regra da pauta D2, `app/registros/turmas.py:2198-2209`), nunca somadas a uma oferta.

### 1.2 Frequência operacional — `app/utils/frequencia.py`

| Onde | O quê | Classe | Observação |
|---|---|---|---|
| `:29` `alunos_ativos_da_turma` | pauta da turma | **TUR** | `Inscricao.turma_id` + `ativo`; usada só no caminho legado (0 ofertas) |
| `:50` `frequencias_lancadas(..., turma_curso_id=None)` | contagem de lançamentos | **OF** | por oferta quando informado; legado por turma |
| `:106` `contar_pendencias_frequencia` | pendências do dashboard | **OF** | delega `_pendencias_por_ofertas` (`:155`) com 2+ ofertas; por turma com 0/1 (decisão D2) |
| `:155` `_pendencias_por_ofertas` | agenda por oferta | **OF** | `datas_esperadas_oferta` por oferta |

### 1.3 Modelo — `app/models/academico.py`

| Onde | O quê | Classe | Observação |
|---|---|---|---|
| `:144` `Turma.freq_geral` (property) | % da turma | **MIG** | `Frequencia.query.filter_by(turma_id=self.id)` — **soma todas as ofertas e o legado**; 1 consulta por turma (N+1 na listagem) |
| `:169` `Turma.freq_geral_oferta(id)` | % de uma oferta | **OF** | filtro `turma_id` + `turma_curso_id`; documenta o N+1 (`:179-182`) |
| `:68` `PeriodoLetivo.alunos_enturmados()` | alunos do período | **MIG** | `join(Aluno.turmas)` + `distinct`; **não** filtra `Inscricao.ativo` nem oferta efetiva (§12.5) |

**Unidade:** `freq_geral` deve virar agregação por oferta servida em lote (`GROUP BY turma_curso_id, conceito`), mantendo a property apenas como somatório explícito de “turma” para telas antigas. Com legado `NULL`: somar na turma é aceitável **se** a tela rotular “turma (todas as ofertas)”; para % por oferta, o legado entra só na oferta única (regra D2).

### 1.4 Painel pedagógico — `app/relatorios/painel_pedagogico/`

| Onde | O quê | Classe | Observação |
|---|---|---|---|
| `frequencia.py:26` `agregar_por_turma` | agregação base | **MIG** | `GROUP BY` implícito por `Frequencia.turma_id` (`:33-43`); devolve `por_aluno` (listas de todas as ofertas) e `pct_turma` somado; **não** filtra `unidade_id` nem `turma_curso_id` |
| `frequencia.py:73` `semanal` | quebra semanal | **MIG-D** | reprocessa `por_aluno`; se a base passar a ser por oferta, precisa receber a chave da oferta |
| `periodo.py:211` `agregar_por_turma(turmas_ids)` | visão por período | **MIG** | idem; `:220-223` omite turma sem frequência (§12.21); `:237` `_montar_turma_linha` (B7) |
| `periodo.py:181-182` `_montar_turma_linha` | programa/turno da linha | **MIG-D** | `turma.programa` / `turma.turno` (projeção), não a oferta |
| `periodo.py:231-232` `(t.turno or "").startswith("noite")` | sinal de noturno | **MIG-D** | turno da **turma**; com ofertas de turnos diferentes a classificação é arbitrária |
| `turma.py:67` `agregar_por_turma([turma.id])` | ficha por turma | **MIG** | mesma agregação; `:70` conselho já vem por oferta (`conselho.por_turma`) |
| `turma.py:194` `_media_periodo` | média do período | **MIG** | agrega todas as turmas por `turma_id` |
| `conselho.py:67` `por_turma` | conselho do painel | **OF** | agrega por oferta e expõe `ofertas` (`:111-139`); exclui `turma_curso_id IS NULL` (`:74`) |
| `rota.py:115` `busca_alunos` | busca do painel | **MIG-D** | pega **uma** inscrição ativa (`.first()` com `data_inicio desc`, `:153-157`) e mostra um vínculo só |
| `rota.py:216` `ficha_aluno_view` | ficha 360° | **OF** | D5.4/D5.5 (`?oferta_sel=`); `_frequencia` em `ficha_aluno.py:157` filtra pela oferta |
| `ficha_aluno.py:263` `pct_turma = serie_turma[-1]` | “frequência da turma” da ficha | **MIG** | usa o **último ponto da série semanal**, não o acumulado (ver Passo 2.4) |
| `ficha_aluno.py:436` `LIMIAR_CRITICO <= freq["pct"] < 90` | faixa 75–89% | **MIG** | `90` hardcoded (o limiar existe em `regras.py:16`) |
| `regras.py:15-16` | `LIMIAR_CRITICO=75.0`, `LIMIAR_ATENCAO=90.0` | **TUR** | fonte correta dos limiares — usada por `helpers.py:32-34`, `sinais.py`, `periodo.py:62` |

**Unidade:** **oferta** como chave primária do painel (`{turma_id: {oferta_id: ...}}`), mantendo a linha “turma” como agregado explícito (soma) para os sinais que são de turma (ex.: “N turmas abaixo de 75%”). **Com legado `NULL`:** incluir na oferta única da turma; em turma sem oferta, manter a chave `None` (linha “turma (legado)”) e rotular.

### 1.5 BI — `app/relatorios/bi_alunos.py`, `bi_filtros.py`, `bi_routes.py`

| Onde | Indicador | Classe | Observação |
|---|---|---|---|
| `bi_filtros.py:59` `cond_inscricao_enturmada` + `:17` `cond_oferta_efetiva` | predicado canônico | **OF** | já exige oferta efetiva (M4) |
| `bi_filtros.py:102` `aplicar_filtros_aluno` / `:159` `aplicar_filtros_inscricao` | filtros globais | **MIG-D** | filtram `curso_id` por **`Turma.curso_id`** (`:140`, `:179`) e `professor_id` por **`Turma.professor_id`** (`:146`, `:185`) |
| `bi_alunos.py:462` `alunos_por_curso` (ALU-009) | alunos por curso | **MIG-D** | usa `cond_inscricao_enturmada()` (`:507` — **a pendência do backlog de que ALU-009/010 não aplicam o helper está desatualizada**), mas junta `Curso` por `Turma.curso_id` (`:503`) e filtra professor por `Turma.professor_id` (`:525`) |
| `bi_alunos.py:554` `alunos_por_turma` (ALU-010) | alunos por turma | **MIG-D** | idem (`:597`, `:609`, `:615`) |
| `bi_alunos.py:878/920/962/1004/1046` | lançamentos, presenças, faltas, justificadas, média | **MIG** | todos filtram `Frequencia.turma_id` (`:894`, `:936`, `:978`, `:1020`, `:1062`) e fazem join em `Turma` para período/curso/professor |
| `bi_alunos.py:1098/1164/1231` | faixas ≥90 / 75–89 / <75 | **MIG** | três blocos quase idênticos; `90`, `89` e `75` literais; **divergência de arredondamento entre as faixas** (Passo 2.3) |
| `bi_alunos.py:1293` `frequencia_por_turma` | frequência por turma | **MIG** | usa `turma.freq_geral` (`:1327`) e, com datas, filtra `Frequencia.turma_id` (`:1330`) |
| `bi_alunos.py:1371` `frequencia_por_curso` | frequência por curso | **MIG** | agrupa por `Curso` via **`Turma.curso_id`** (`:1382-1384`) |
| `bi_alunos.py:2449` `frequencia_critica_por_vulnerabilidade` | <75% por vulnerabilidade | **MIG** | filtros por `Turma.curso_id`/`professor_id` (`:2475`, `:2479`) |
| `bi_alunos.py:2517` `alunos_raca_conselho` (CRU-002) | raça/cor no conselho | **MIG-D** | `count(distinct aluno)` correto (D5.4), mas filtros por `Turma.*` (`:2535-2544`) |
| `bi_alunos.py:2615` `transferencias_por_curso` | transferências por curso | **MIG-D** | curso de origem via **`Turma.curso_id`** (`:2629`) — depende da Fase 7 |
| `bi_alunos.py:2667` `desempenho_conselho_por_renda` (CRU-005) | desempenho por renda | **MIG-D** | uma linha por conselho; filtros por `Turma.*` (`:2687-2695`) |
| `bi_alunos.py:2738` `_contar_status_aluno` + `:2752+` `alunos_enturmados`… | status no BI | **OF** | usam `status_alunos_para_bi` (serviço canônico) |
| `bi_routes.py:88` `bi_api_dados` | JSON do gráfico | **MIG-D** | recebe **apenas** `unidade_id` (`:113-116`) — curso/turma/professor nunca chegam |
| `bi_routes.py:142` `bi_exportar_xlsx` | Excel do indicador | **MIG-D** | aceita `unidade_id`, `periodo_letivo_id`, `turno` (`:158-162`); sem curso/turma/professor |
| `bi_routes.py:279` `bi_indicador` | execução avulsa | **MIG-D** | idem (`:287-291`) |

**Unidade:** **aluno distinto** nos indicadores de aluno (decisão 2), **oferta** nos de frequência/conselho, **curso da oferta** (`TurmaCurso.curso_id`) em ALU-009/`frequencia_por_curso`/`transferencias_por_curso`. **Com legado `NULL`:** frequência legada entra no total **da turma** (nunca de uma oferta) e é marcada como “sem oferta” quando o indicador for por oferta.

### 1.6 Relatórios, impressões e histórico

| Onde | Rota | Classe | Observação |
|---|---|---|---|
| `relatorios/geral.py:58` `relatorio_geral` / `:119` `exportar_relatorio` | `/relatorios/` e `/relatorios/exportar` | **MIG** | herdam `calcular_frequencias_relatorio` (por turma/programa/professor) |
| `relatorios/alunos.py:95/182` | `/relatorios/alunos` e exportação | **TUR** | contagens por aluno (perfil/inscrição); não agrega frequência |
| `registros/turmas.py:2042` `imprimir_pauta` | pauta | **OF** | exige `turma_curso` com 2+ (`:2064-2077`); oferta única inclui legado `NULL` (`:2199-2207`) |
| `registros/turmas.py:2002` `ver_observacoes` | observações do diário | **OF** | filtro opcional por oferta; sem filtro mostra **todas** com rótulo (`:2006-2029`) — decisão de UX a confirmar |
| `registros/alunos.py:830` `historico_aluno` | histórico | **OF** | D5.4: uma linha por inscrição; frequência por inscrição (N+1 aceito, §12.23) |
| `registros/periodos.py:521` certificado | certificado | **OF** | D5.4 |
| `registros/turmas.py:359-361` listagem `/turma` | coluna de frequência | **OF/TUR** | com 2+ ofertas usa `freq_geral_oferta(principal)`; com 0/1 usa `freq_geral` (agregado) — correto, mas a coluna não diz “principal” |
| `registros/turmas.py:576` `imprimir_centros_custo_turmas` | impressão por centro | **OF** | ofertas por centro com `centro_custo or turma.centro_custo` (`:656-667`) |
| `registros/core.py:997` `imprimir_temas` | temas por curso | **TUR** | não depende de oferta |
| `registros/alunos.py:960` `imprimir_aluno` | ficha impressa | **TUR** | só cadastro/perfil |

### 1.7 “Enturmado”/status e dashboards

| Onde | O quê | Classe |
|---|---|---|
| `services/aluno_status.py:190` `status_alunos` / `:109` `status_alunos_para_bi` | status canônico (aluno × período) | **OF** (usa `cond_oferta_efetiva`, `:242-257`) |
| `services/aluno_status.py:68` `_ids_coorte_turno` | coorte por turno | **MIG-D** | `Turma.turno` (projeção) |
| `registros/alunos.py:380` `total_enturmados` | card da listagem | **MIG** | `Aluno.turmas.any(Turma.ativo)` — ignora inscrição ativa e oferta efetiva |
| `registros/core.py:167` `total_alunos` (`/professor/painel`) | card do painel do professor | **TUR** | `Inscricao.ativo` + `distinct(aluno)` — correto para “alunos distintos”, mas não filtra oferta efetiva |
| `main/dashboard_professor.py:252` `render_dashboard_professor` | dashboard por perfil | **OF** | `_entradas_professor` (`:136`) usa `TurmaCurso.professor_id` (`:151`) com fallback `Turma.professor_id` (`:181`); `_aulas_pendentes(..., professor_id)` (`:41`) |
| `main/dashboard_admin.py:12` | dashboard gerencial | **TUR** | `Turma.professor_id` para contar professores distintos (`:34`) |
| `main/dashboard_servico_social.py:11` | dashboard do serviço social | **TUR** | conta turmas ativas |
| `registros/core.py:130` `painel_professor` | painel legado do professor | **MIG** | filtra `Turma.professor_id` (`:155-158`) — **divergente do dashboard novo** |

---

## Passo 2 — Divergências entre telas (confirmadas por leitura)

### 2.1 “Status” com duas fontes — **CONFIRMADO**
- **Fonte A (canônica):** `services/aluno_status.status_alunos` (por aluno × período, com `cond_oferta_efetiva`). Usada pela ficha (`ficha_aluno.py:670`), pelo BI (`bi_alunos.py:2738`) e pelo painel (`coorte.py:12`).
- **Fonte B (ad hoc):** presença de qualquer linha em `inscricoes` ligada a turma ativa — `registros/alunos.py:380` (`Aluno.turmas.any(Turma.ativo == True)`) e `academico.py:68` (`PeriodoLetivo.alunos_enturmados()`).
- Efeito: aluno **desenturmado** (inscrição inativa) em turma ativa conta como “enturmado” no card de `/alunos` e na property do período, mas como **Desenturmado** no BI/ficha. Os números das telas não fecham.
- Contexto histórico: `docs/D5_4_relatorio.md` §4.1 registra que a ficha usava `inscricao.status_aluno` — **campo inexistente** (`Inscricao` não tem `status`, `app/models/matriculas.py:54-88`). A “segunda fonte” nasceu de um atributo que nunca existiu.

### 2.2 “Enturmado” definido de 4 formas — **CONFIRMADO (na verdade 5)**
1. `registros/alunos.py:380` — `Aluno.turmas.any(Turma.ativo)`.
2. `academico.py:68` — `join(Aluno.turmas).filter(Turma.periodo_letivo_id).distinct()`.
3. `bi_filtros.py:59` — `cond_inscricao_enturmada()` (inscrição ativa + turma ativa + oferta efetiva).
4. `aluno_status.py:190` — `status_alunos` (inscrição ativa/até a data + oferta efetiva + regras Novo/Renovado/…).
5. `registros/core.py:167` — `Inscricao.ativo` + `Aluno.ativo` + `distinct` (sem oferta efetiva).

### 2.3 Faixas 90/75 duplicadas — **CONFIRMADO**
- Fonte única existente: `painel_pedagogico/regras.py:15-16`.
- Duplicações: `periodo.py:87` (`< 75.0` hardcoded) e `:94` (texto “75%”); `ficha_aluno.py:436` (`< 90`); `bi_alunos.py:1154` (`>= 90`), `:1222` (`75 <= round(...,1) <= 89`), `:1287` (`< 75`), `:2492` (`< 75`).
- **Bug de fronteira encontrado:** `alunos_frequencia_90` compara o valor **sem** arredondar (`:1154`), enquanto `alunos_frequencia_75_89` arredonda a 1 casa (`:1222`). Um aluno com 89,96% vira 90,0 no arredondamento e **não entra em nenhuma das duas faixas**; 90,04% entra em ≥90 e também não é barrado pelo limite superior. As três faixas não somam o total de alunos com frequência.

### 2.4 “Frequência da turma” da ficha usa o último ponto da série — **CONFIRMADO**
`ficha_aluno.py:263`: `pct_turma = serie_turma[-1] if serie_turma else 0.0`. A série é semanal (`:252-257`) e a última semana quase sempre é **parcial**; se a última semana não tiver aula lançada, o valor é `0.0`. Consequências: `diff_turma` (`:276-282`) fica artificialmente positivo e o selo muda de cor; o mesmo aluno pode aparecer “+80 p.p. acima da turma”. O acumulado da oferta (`turma_data`/`turma_total`, `:183-217`) já é calculado e **não é usado** para esse número.

### 2.5 Regra de frequência repetida em 4 lugares — **CONFIRMADO (em 7)**
1. `academico.py:144` (`freq_geral`) e `:169` (`freq_geral_oferta`).
2. `bi_alunos.py:1293` e `:1371` (por turma/curso) + `:1098-1290` (faixas).
3. `painel_pedagogico/frequencia.py:26` (`agregar_por_turma`) e `:73` (`semanal`).
4. `ficha_aluno.py:157` (`_frequencia`).
5. `logica.py:589` (`calcular_frequencias_relatorio`).
6. `registros/core.py:380` (estatística por aluno na tela de lançamento) e `:464` (`frequencia_relatorio`).
7. `registros/core.py:1039`/`turmas.py:2211` (leitura da pauta).

Todas usam o mesmo par `CONCEITOS_CONTABEIS`/`CONCEITOS_PRESENCA`, mas **cada uma reimplementa o loop**; a divergência do Passo 2.3 e o N+1 de `core.py:373-394` vêm daí.

### 2.6 O que a D3b deve unificar (sem mudar regra de negócio)
- **Serviço único de frequência por oferta** (`app/services/frequencia_oferta.py`, nome proposto): uma função de agregação em lote (`por_oferta(ids)`, `por_turma(ids)` derivada), uma de percentual (mesma fórmula `presentes/(presentes+faltas)`, J fora, arredondamento a 1 casa) e uma de faixas com **um** conjunto de limiares (`regras.LIMIAR_*` + `>=`, `<` consistentes).
- **Serviço único de “enturmado”** (reaproveitar `aluno_status`): expor `enturmado_em(aluno_ids, periodo, data)` / `cond_enturmado()` e substituir as 5 definições do Passo 2.2. `cond_inscricao_enturmada()` passa a ser o predicado SQL canônico e `status_alunos` a versão por aluno.
- **Nenhuma mudança de semântica**: J continua fora do denominador; oferta inativa em período encerrado continua contando; turma desativada continua fora.

---

## Passo 3 — Mapa de cobertura das rotas de leitura

### 3.1 Método
`instance/backups/d3b0_scan.py` cria a app com config SQLite em memória, percorre `app.url_map`, seleciona as rotas GET dos blueprints `main.`, `registros.`, `relatorios.`, `conselho.` e `servico_social.` e procura a URL (com `<...>` convertido em curinga) no texto de todos os arquivos de `tests/`. É **citação**, não prova de execução — os casos ambíguos foram conferidos por leitura.
Total do app: **110 rotas GET**; nos cinco blueprints de negócio: **98**; sem citação em teste: **51**.

### 3.2 Rotas de leitura e cobertura

| Rota (endpoint) | URL | Teste |
|---|---|---|
| `main.dashboard` / `main.painel` | `/dashboard`, `/painel` | `test_dashboard.py`, `test_maintenance.py`, `test_security_regressions.py`, `test_d5_leitores.py`, `test_painel_periodo.py` |
| `main.painel_secretaria` | `/painel/secretaria` | **sem** |
| `registros.painel_professor` | `/professor/painel` | **sem** |
| `registros.frequencia` | `/frequencia` | `test_pauta_professor.py`, `test_turma_curso_fase4.py` |
| `registros.frequencia_relatorio` | `/frequencia_relatorio` | **sem** |
| `registros.imprimir_pauta` | `/turma/<id>/imprimir-pauta` | `test_pauta_professor.py` |
| `registros.ver_observacoes` | `/turma/<id>/observacoes` | **sem** |
| `registros.historico_aluno` | `/aluno/<id>/historico` | `test_security_regressions.py` + `test_d5_leitores.py` |
| `registros.imprimir_aluno` | `/aluno/imprimir/<id>` | **sem** |
| `registros.periodo_letivo_relatorio_certificado` | `/periodo-letivo/relatorio/<id>` | `test_d5_encerramento.py`, `test_d5_leitores.py` |
| `registros.turma` / `ver_turma` | `/turma`, `/turma/<id>` | `test_filtros_turmas.py` (+ `ver_turma` em 9 arquivos) |
| `registros.turma_listar` | `/turmas/lista` | **sem** (alias de `/turma`) |
| `registros.turma_lixeira` | `/turmas/lixeira` | **sem** |
| `registros.turma_ofertas` | `/turma/<id>/ofertas` | `test_turma_curso_fase2.py` |
| `registros.carga_horaria_turmas` | `/turmas/carga-horaria` | `test_carga_horaria_curso.py` |
| `registros.imprimir_centros_custo_turmas` | `/turmas/centros-custo/imprimir` | **sem** |
| `registros.planejamento` | `/planejamento` | `test_isolamento_unidade_escrita.py`, `test_security_regressions.py` |
| `registros.calendario_dias` | `/planejamento/calendario/<id>` | `test_isolamento_unidade_escrita.py` |
| `registros.calendario_exportar` | `…/exportar` | **sem** |
| `registros.imprimir_temas` | `/planejamento/imprimir-temas` | **sem** |
| `registros.api_alunos` | `/api/alunos/<turma_id>` | `test_security_regressions.py` |
| `relatorios.relatorio_geral` | `/relatorios/` | `test_bi_indicadores.py`, `test_d5_endurecimento.py`, `test_d5_leitores.py`, `test_painel_periodo.py` |
| `relatorios.exportar_relatorio` | `/relatorios/exportar` | **sem** |
| `relatorios.relatorio_alunos` | `/relatorios/alunos` | `test_d5_endurecimento.py`, `test_d5_leitores.py` |
| `relatorios.exportar_relatorio_alunos` | `/relatorios/relatorio_alunos/exportar` | **sem** |
| `relatorios.painel_pedagogico` | `/relatorios/painel` | `test_painel_periodo.py`, `test_d5_leitores.py` |
| `relatorios.busca_alunos` | `/relatorios/painel/busca` | **sem** |
| `relatorios.ficha_aluno_view` | `/relatorios/alunos/<id>/ficha` | `test_d5_endurecimento.py`, `test_d5_leitores.py` |
| `relatorios.resultado_conselho` | `/relatorios/conselho` | `test_d5_leitores.py` |
| `relatorios.bi_dashboard` | `/relatorios/bi` | `test_bi_indicadores.py` |
| `relatorios.bi_api_dados` | `/relatorios/bi/dados` | **sem** |
| `relatorios.bi_indicador` | `/relatorios/bi/indicador/<codigo>` | `test_bi_indicadores.py` |
| `relatorios.bi_exportar_xlsx` | `/relatorios/bi/exportar/xlsx` | **sem** |
| `conselho.index_conselho` | `/conselho` | 5 arquivos |
| `conselho.lancamento_conselho` | `/conselho/lancamento` | `test_conselho_oferta.py`, `test_conselho_ui.py` |
| `conselho.fechamento_turma` | `/conselho/fechamento/<id>` | `test_conselho_oferta.py`, `test_conselho_ui.py` |
| `conselho.avaliar_turma` | `/turma/<id>/avaliacao` | `test_conselho_oferta.py`, `test_conselho_ui.py`, `test_d5_endurecimento.py` |
| `conselho.informacoes` | `/informacoes` | `test_d5_encerramento.py` |
| `conselho.gerenciar_perguntas` | `/conselho/perguntas` | **sem** |
| `servico_social.*` (4 rotas) | `/servico-social/*` | **sem** |
| `registros.*` de cadastro/atendimento (9 rotas) | `/form`, `/editar`, `/aluno/novo`, … | **sem** (fora do escopo de leitura agregada) |

Observação: as **28 rotas** de `/centros-custo*` (variantes de alias registradas em `app/registros/periodos.py`) são todas GET e apenas 8 aparecem em teste — a duplicação de `rule` para o mesmo endpoint indica um bloco de aliases legados que merece limpeza futura (não é dívida desta etapa).

### 3.3 Varredura estática — `ruff check app --select F821,F811,F841`
Resultado: **9 achados, 0 F821** (nenhum `NameError` pendente — confirma que a correção do B7 fechou `_montar_turma_linha`).

| Regra | Arquivo:linha | Achado | Avaliação |
|---|---|---|---|
| F841 | `app/__init__.py:60` | `migrate = Migrate(app, db)` — variável não usada | cosmético; o efeito colateral (registro do Migrate) é o que importa |
| F841 | `app/conselho.py:279` | `unidade_id = get_unidade_id()` não usada (perguntas são globais) | cosmético/legado |
| F841 | `app/conselho.py:785` | `except Exception as e` sem uso (o `str(e)` está no bloco anterior) | cosmético |
| F841 | `app/planejamento.py:90` | `except Exception as e` sem uso | cosmético |
| F841 | `app/registros/servico_social.py:277` | `socio = perfil["socioeconomico"]` não usado | cosmético (leitura descartada) |
| F811 | `app/relatorios/bi_alunos.py:2369` | reimport de `PerfilDiversidade` (já no topo, `:11`) | cosmético |
| F811 | `app/relatorios/bi_alunos.py:2527` | idem | cosmético |
| F841 | `app/relatorios/bi_routes.py:208` | `fmt_valor` criado e não usado | cosmético (formato morto no Excel) |
| F841 | `app/relatorios/bi_routes.py:211` | `fmt_item` criado e não usado | cosmético |

Nenhum achado fora dos já conhecidos e nenhum com impacto de execução.

### 3.4 Simulação, por leitura, das 10 rotas de leitura mais críticas sem teste

Cenários: **(A)** turma com 2 ofertas ativas; **(B)** aluno em 2 ofertas da mesma turma; **(C)** turma sem nenhuma frequência; **(D)** período sem turmas.

| # | Rota | A | B | C | D | Risco de 500 |
|---|---|---|---|---|---|---|
| 1 | `registros.frequencia_relatorio` (`core.py:413`) | soma as duas ofertas por aluno (`:455-458`) | **duplica o aluno na tabela** (loop sobre `Inscricao` sem `distinct`, `:443-452`) | `percentual=0.0`, sem quebra | lista vazia | **ALTO**: `int(turma_id)` em `:439` sem validação → `ValueError` com `?turma=abc` |
| 2 | `relatorios.bi_api_dados` (`bi_routes.py:88`) | ignora a oferta (nunca recebe `turma_id`) | conta aluno distinto por curso (ALU-009 correto) | valores zerados | listas vazias | baixo (dimensão inválida devolve listas vazias) |
| 3 | `relatorios.bi_exportar_xlsx` (`bi_routes.py:142`) | idem | idem | planilha “Sem resultados” | idem | baixo (400/403 explícitos) |
| 4 | `relatorios.exportar_relatorio` (`geral.py:119`) | freq. por programa/professor somando ofertas (`logica.py:609-637`) | conta o aluno uma vez por média (`t.alunos` deduplica) | 0% | DataFrames vazios (`:133-150`) → planilha sem linhas | baixo: o `except` genérico (`:181`) faz flash+redirect, não 500 |
| 5 | `relatorios.exportar_relatorio_alunos` (`alunos.py:182`) | não usa oferta | idem | ok | ok | baixo |
| 6 | `relatorios.busca_alunos` (`rota.py:115`) | mostra a turma uma vez | **mostra só 1 dos 2 vínculos** (`.first()` em `:153-157`) | ok | ok | baixo |
| 7 | `registros.painel_professor` (`core.py:130`) | 1 linha por turma; `total_alunos` distinto (`:167-176`) | conta 1 aluno | `Turma.programa` `None` cai fora do filtro de programa (`:152-153`) | lista vazia | baixo; **incorreto** para Fase 5 (filtra `Turma.professor_id`) |
| 8 | `registros.imprimir_centros_custo_turmas` (`turmas.py:576`) | C.H. somada das ofertas (`:642-647`); turma repetida em centros diferentes (intencional) | ok | ok | nada a imprimir | baixo |
| 9 | `registros.ver_observacoes` (`turmas.py:2002`) | mistura ofertas se `turma_curso` não vier (`:2014-2024`) | ok | lista vazia | 404 da turma | baixo |
| 10 | `registros.turma_lixeira` (`turmas.py:702`) | **`TemplateNotFound`** (`turma_lixeira.html` não existe) | idem | idem | idem | **CERTEIRO (500)** + `Turma.query.filter_by(ativo=False)` sem unidade (`:707`) → vaza outras unidades |
| 11 (nota) | `registros.imprimir_aluno` (`alunos.py:960`) | sem oferta | ok | ok | ok | baixo |
| 12 (nota) | `conselho.gerenciar_perguntas` (`conselho.py:268`) | ok (perguntas globais) | ok | ok | ok | baixo |

**Achados adicionais de 500 latente (fora das 10):** `ficha_aluno.py:263` não quebra, mas produz número errado; `periodo.py:220-223` omite turma sem frequência (§12.21) — não é 500.

---

## Passo 4 — Fases 5–7 redefinidas

### 4.0 O que a especificação previa (reconstituído)
- Backlog §“Onda 4”, L239: “**Fases 5–7** — autorização por professor ofertado (§8), turno por curso e centro de custo compartilhado/individual (§9), transferências por oferta (§10)”; o mesmo parágrafo registra as Fases 8–9 e o NOT NULL final como concluídos.
- MER §8.10 e §10 repetem a mesma redação, sem detalhar critérios de aceite.
- **Não há** documento com o texto integral da especificação; qualquer critério abaixo é **reconstituição** deste desenho.

### 4.1 Fase 5 — autorização por professor da oferta

**Como o professor enxerga hoje (por arquivo:linha):**

| Superfície | Regra atual | Fonte |
|---|---|---|
| Dashboard `/dashboard` e `/painel` | ofertas com `TurmaCurso.professor_id == user`; fallback `Turma.professor_id` só em turma sem oferta | `main/dashboard_professor.py:151` e `:181-190` |
| Painel `/professor/painel` | **`Turma.professor_id == user`** | `registros/core.py:155-158` |
| Lançamento `/frequencia` (GET e POST) | **`Turma.professor_id == user`** para listar e para autorizar o POST | `registros/core.py:304-321` e `:204-207` |
| Pauta `/turma/<id>/imprimir-pauta` | **`turma.professor_id == user`** | `registros/turmas.py:2049` |
| Ficha da turma `/turma/<id>` | **`turma.professor_id == user`** | `registros/turmas.py:916-920` |
| Observações do diário | não restringe por professor (só role) | `registros/turmas.py:2003` |
| Conselho — painel | `TurmaCurso.professor_id **OR** Turma.professor_id` | `services/turma_curso.py:153-159` |
| Conselho — lançamento/fechamento | **sem checagem de professor** (apenas `login_required` + unidade) | `app/conselho.py:235+`, `:425+` |
| Conselho — avaliação coletiva | **`turma.professor_id == user`** | `app/conselho.py:800` |
| Histórico/impressão do aluno | permitido a `professor` sem vínculo com a oferta | `registros/alunos.py:840`, `:962-968` |

**O que falta (reconstituído):** uma regra única de acesso por oferta, aplicada nas superfícies acima, e a coerência entre as duas telas de painel do professor.

**Desenho proposto:**
1. Novo módulo `app/services/acesso_oferta.py` com:
   - `ofertas_do_usuario(user, unidade_id=None) -> list[TurmaCurso]` — admin/pedagogico/gerencia/secretaria: todas as ofertas ativas da unidade; professor: `TurmaCurso.professor_id == user.id` **ou** (`TurmaCurso.professor_id IS NULL` **e** `Turma.professor_id == user.id`) — o fallback só cobre oferta **sem responsável** e é marcado como legado;
   - `pode_gerir_oferta(user, oferta) -> bool` — mesma regra, por oferta;
   - `pode_ver_turma(user, turma) -> bool` — verdadeiro se tem ao menos uma oferta visível.
2. Aplicar em: `painel_professor`, `frequencia` (GET lista e POST), `imprimir_pauta`, `ver_turma`, `ver_observacoes`, `index_conselho`, `lancamento_conselho`, `fechamento_turma`, `avaliar_turma`, `historico_aluno`/`imprimir_aluno` (professor só vê aluno com inscrição em oferta sua).
3. Unificar `/professor/painel` no dashboard novo (`render_dashboard_professor`) ou transformá-lo em redirect — mantê-lo com regra antiga perpetua a divergência.
4. **Critério de aceite:** professor responsável por 1 das 2 ofertas de uma turma vê/lança **apenas** a sua oferta; não vê a outra em pauta, conselho, observações nem dashboard; pedagogia continua vendo tudo.

### 4.2 Fase 6 — turno por curso e centro de custo compartilhado/individual

**Já feito (não precisa refazer):**
- `TurmaCurso.turno`, `dias_semana`, `hora_inicio`, `hora_fim`, `data_inicio`, `data_fim`, `centro_custo` existem no modelo (`app/models/academico.py:283-337`) com `NULL = herda da turma`.
- Listagem de turmas: filtros e resumo usam `COALESCE(oferta→turma)` (`registros/turmas.py:173-179`, `:182-210`, `:285-296`).
- Centro de custo: catálogo por unidade, CSV nas três tabelas, propagação de renomeação e impressão por centro (`registros/periodos.py:613-707`, `registros/turmas.py:576-693`) — individual por oferta com fallback `oferta.centro_custo or turma.centro_custo` (`:656-658`).
- C.H. por oferta com herança de horários (`academico.py:361-400`).

**O que realmente falta:**
| Onde | Problema | Arquivo:linha |
|---|---|---|
| Painel do conselho | filtros de programa e turno usam `Turma.programa` / `Turma.turno` (projeção) e a coluna exibe o fallback | `conselho.py:245`, `:368`; `services/turma_curso.py:150-152`, `:169-170` |
| Painel pedagógico — período | linha da turma mostra `turma.programa` / `turma.turno`; sinal de “noturno” por `turma.turno` | `periodo.py:181-182`, `:231-232` |
| BI — coorte por turno | `_ids_coorte_turno` filtra `Turma.turno` | `services/aluno_status.py:68-106` |
| BI — filtros | `curso_id`/`professor_id` por `Turma.*` (mesmo problema do turno) | `bi_filtros.py:140/146/179/185` |
| Listagem/impressão | exibe “turnos” como conjunto (correto), mas o filtro por turno casa **qualquer** oferta — não permite “turno da oferta X” | `turmas.py:194`, `:213-337` |

**Desenho:** trocar as leituras de `Turma.programa/turno` por `COALESCE(oferta, turma)` **na mesma consulta** (não em Python), mantendo a coluna da turma como projeção apenas para agrupamentos de turma. Nos filtros com 2+ ofertas de turnos diferentes, exibir a linha por oferta (depende do D3b.4).

### 4.3 Fase 7 — transferências por oferta

**Estado atual (`app/registros/alunos.py:988-1180`):** o fluxo já é **por oferta** — exige inscrição ativa na oferta de origem (`:1044-1055`), lista ofertas de destino ativas de outras turmas (`:1060-1070`), valida vigência da oferta de destino (`:1111-1119`) e duplicidade por oferta (`:1121-1129`), desativa a origem com motivo `TRANSFERENCIA` (`:1132-1136`) e delega a criação ao serviço `enturmar_aluno` (`:1141-1147`).

**O que falta:** a tabela `transferencia` grava apenas `turma_origem_id`/`turma_destino_id` (`app/models/matriculas.py:106-119`). Toda a rastreabilidade de oferta depende de reconstrução por `Inscricao` (MER §7.16).

**Desenho:**
1. **Migration aditiva** (`d3b_fase7_transferencia_oferta`): `turma_curso_origem_id` e `turma_curso_destino_id` (`Integer`, FK → `turma_curso.id`, `ON DELETE RESTRICT`, **nullable**), mais índices `ix_transferencia_oferta_origem`/`_destino`.
2. **Backfill somente inequívoco** (mesmo padrão de `e5f6a7b8c9d0`):
   - origem: inscrição com `motivo_desativacao='TRANSFERENCIA'` e `data_desativacao` igual à véspera de `data_transferencia`, **única** para o par (aluno, turma_origem);
   - destino: inscrição ativa do par (aluno, turma_destino) com `data_inicio = data_transferencia`, **única**;
   - qualquer ambiguidade (2+ candidatas) fica `NULL` e é listada por script somente-leitura (`scripts/verificar_onda4_d3b.py`).
3. **Escrita:** preencher os dois campos em `transferir_aluno` (`alunos.py:1151-1162`); o valor da origem está em `inscricao_origem.turma_curso_id` e o do destino em `oferta_destino.id`.
4. **Leitores a migrar:** `transferencias_por_curso` (`bi_alunos.py:2615-2664`) passa a agrupar por `TurmaCurso.curso_id` (fallback `Turma.curso_id` quando o campo é `NULL`); `turma_tem_historico` (`services/turma_curso.py:178+`) passa a considerar as colunas de oferta; histórico do aluno pode mostrar origem/destino por oferta.
5. **Impacto/risco:** o campo nullable mantém as transferências antigas funcionando; nenhuma constraint nova quebra dados existentes (diferente do NOT NULL de `conselho_classe`).
6. **Critério de aceite:** transferência nova grava as duas ofertas; leitura no BI mostra o curso correto mesmo quando `Turma.curso_id` (legado) aponta outro curso; backfill relata N preenchidos e M ambíguos sem alterar dados.

---

## Passo 5 — Plano em etapas executáveis

Ordem por **risco crescente + dependência** (cada etapa entrega suíte verde e pode ir a commit isolado). Todas seguem o protocolo do projeto: sem commit automático, relatório `docs/<etapa>_relatorio.md`, suíte completa ao final.

### D3b.1 — Limpeza de docstrings e do derivado `turma_conselho_concluido` (risco: baixo)
**Por quê primeiro:** é dívida documental/estrutural sem efeito de dados e destrava leitura do código para as etapas seguintes.
**Escopo:**
- `app/services/turma_curso.py:64-65` — remover “a coluna permanece apenas como ponte de escrita até a D5.5” (a coluna não existe mais).
- `app/services/conselho_leitura.py:6-10` — idem (ponte e “antes da D5.5”).
- Decidir `turma_conselho_concluido()` (MER §12.20): **consumir** nos leitores que hoje refazem o derivado (`conselho.py` painel, `periodos.py` certificado, `logica.calcular_metricas_conselho`) ou **remover** a função e os testes. Recomendação: consumir (evita regra duplicada).
- Corrigir os `except ... as e` sem uso e imports duplicados apontados pelo ruff (9 achados do §3.3) **apenas** nos arquivos já tocados pela etapa.
**Testes:** `test_d5_encerramento.py` (13) deve continuar verde; se a função for consumida, acrescentar asserção de equivalência entre o derivado e o leitor do painel.
**Riscos:** nenhum de dados; risco de regressão só se a função divergir dos leitores (comparar os três caminhos).
**Pronto quando:** `ruff check app --select F821,F811,F841` voltar a **0** nos arquivos tocados; suíte ≥359; nenhuma docstring citar “ponte/até a D5.5”.

### D3b.2 — Serviço único de frequência por oferta (risco: médio-alto)
**Escopo:**
- Novo `app/services/frequencia_oferta.py`:
  - `percentual(conceitos) -> float` (regra única: `CONCEITOS_PRESENCA`/`CONCEITOS_CONTABEIS`, J fora, 1 casa);
  - `agregar_por_oferta(oferta_ids | turma_ids) -> dict` em **uma** consulta (`GROUP BY turma_curso_id, conceito`) — elimina o N+1 de `Turma.freq_geral_oferta` (`academico.py:169-198`);
  - `agregar_por_turma(turma_ids)` derivada (soma das ofertas + legado `NULL` quando não há oferta ativa);
  - `faixas(pct) -> "hi"|"mid"|"lo"` com `LIMIAR_ATENCAO`/`LIMIAR_CRITICO` de `regras.py` e comparação consistente (corrige o Passo 2.3).
- Migrar consumidores: `painel_pedagogico/frequencia.py` (`agregar_por_turma`, `semanal`), `painel_pedagogico/turma.py:67/194`, `painel_pedagogico/periodo.py:211`, `registros/core.py:373-394` e `:464`, `utils/logica.py:589-639`, `bi_alunos.py:878-1448`.
- `Turma.freq_geral`/`freq_geral_oferta` passam a delegar ao serviço (mantidas por compatibilidade).
**Testes:** novo `tests/test_frequencia_oferta.py` (aluno em 2 ofertas com percentuais distintos; oferta única com legado `NULL`; turma sem oferta; J no meio; fronteiras 74,9/75,0/89,96/90,0). Ajustar os testes que hoje dependem de `freq_geral` somado.
**Riscos:** mudança de número em telas (é o objetivo), mas **exige** conferência visual; risco de soma dupla se o filtro legado for esquecido.
**Pronto quando:** nenhuma tela calcula percentual fora do serviço (grep por `CONCEITOS_PRESENCA` deve retornar só o serviço e `enums.py`); suíte ≥359 + novos testes.

### D3b.3 — Unificação de “enturmado”/status (risco: médio)
**Escopo:** expor em `app/services/aluno_status.py` um predicado SQL `cond_enturmado()` (alias documentado de `cond_inscricao_enturmada`) e uma função `enturmado_em(...)`; substituir as 5 definições do Passo 2.2: `registros/alunos.py:380`, `academico.py:68`, `registros/core.py:167` (opcional, já correto) e os usos em `relatorios/shared.py:72` (período por `Aluno.turmas` sem `ativo`).
**Testes:** `test_aluno_status.py` + novo caso “inscrição inativa em turma ativa não conta como enturmado” usado por `/alunos` e pela property do período; manter `cond_inscricao_enturmada` coberto por `test_bi_turma_desativada.py`.
**Riscos:** os números das telas **vão cair** (é a correção); comunicar no relatório a diferença antes/depois.
**Pronto quando:** só existir **um** predicado e **uma** função de status no código; telas citadas convergirem para os mesmos números.

### D3b.4 — BI e painel por oferta (risco: médio-alto; depende de D3b.2/D3b.3)
**Escopo:**
- `bi_filtros.py`: `curso_id` por `TurmaCurso.curso_id` (join por `Inscricao.turma_curso_id`) e `professor_id` por `TurmaCurso.professor_id` com fallback explícito; `turno` idem.
- `bi_alunos.py`: ALU-009 (`:462`), ALU-010 (`:554`), `frequencia_por_curso` (`:1371`), faixas (`:1098-1290`), `frequencia_por_turma` (`:1293`), `frequencia_critica_por_vulnerabilidade` (`:2449`), `transferencias_por_curso` (após D3b.8).
- `bi_routes.py`: aceitar `curso_id`, `turma_id`, `professor_id` em `bi_api_dados`, `bi_exportar_xlsx` e `bi_indicador` (hoje só unidade/período/turno).
- `painel_pedagogico/periodo.py` e `turma.py`: linha por oferta + agregado da turma; opção “por oferta” na visão por período.
**Testes:** estender `test_bi_indicadores.py` e `test_painel_periodo.py` (turma com 2 ofertas de cursos diferentes; aluno em 2 ofertas; turma sem frequência; faixas somando o total).
**Riscos:** alteração de séries históricas do BI; requer comunicação. `Turma.programa` como fonte de filtro pode divergir da oferta principal — decidir (§pergunta 2).
**Pronto quando:** indicadores por curso/professor não usarem `Turma.*`; faixas 90+75–89+<75 = total; testes cobrem os 4 cenários.

### D3b.5 — Testes de fumaça das rotas de leitura + correção dos 500 (risco: baixo; depende de D3b.2–D3b.4)
**Escopo:**
- Novo `tests/test_rotas_leitura_smoke.py` (parametrizado, um usuário por teste): `GET` 200 em `relatorios.bi_dashboard`, `bi_api_dados`, `bi_exportar_xlsx`, `bi_indicador`, `relatorio_geral`, `exportar_relatorio`, `relatorio_alunos`, `exportar_relatorio_alunos`, `painel_pedagogico`, `busca_alunos`, `ficha_aluno_view`, `resultado_conselho`, `painel_professor`, `frequencia_relatorio`, `ver_observacoes`, `imprimir_pauta`, `imprimir_aluno`, `imprimir_centros_custo_turmas`, `imprimir_temas`, `turma_listar`, `turma_lixeira`, `conselho.perguntas`, `periodo_letivo_relatorio_certificado`, com os 4 cenários (A–D do §3.4).
- Correções: `core.py:439` `int(turma_id)` com validação (`request.args.get(..., type=int)`); `turmas.py:702` `turma_lixeira` (ver D3b.9).
**Riscos:** nenhum de negócio; os testes revelam dívidas já mapeadas.
**Pronto quando:** 24 rotas com pelo menos 1 teste cada nos 4 cenários; suíte verde.

### D3b.6 — Fase 5: autorização por professor da oferta (risco: alto — segurança)
**Escopo:** novo `app/services/acesso_oferta.py`; aplicar em `painel_professor`, `frequencia` (GET/POST), `imprimir_pauta`, `ver_turma`, `ver_observacoes`, `index_conselho`, `lancamento_conselho`, `fechamento_turma`, `avaliar_turma`, `historico_aluno`/`imprimir_aluno`; unificar `/professor/painel` no dashboard novo.
**Testes:** novo `tests/test_acesso_oferta.py` (professor responsável por 1 de 2 ofertas: 200 na sua, 403 na outra, em todas as superfícies; administração vê as duas; professor sem vínculo → 403; unidade cruzada → 403). Estender `test_isolamento_unidade_escrita.py`.
**Riscos:** **bloqueio de acesso legítimo** se o fallback `Turma.professor_id` for removido cedo — por isso a regra de oferta sem responsável; comunicar antes de publicar.
**Pronto quando:** nenhuma superfície do professor usar `Turma.professor_id` como regra principal; matriz de acesso coberta por teste.

### D3b.7 — Fase 6: turno/programa/centro por oferta nas leituras (risco: médio; depende de D3b.4)
**Escopo:** `conselho.py:245/368` e `services/turma_curso.py:150-152/169-170` (filtros e colunas com `COALESCE(oferta→turma)`); `periodo.py:181-182/231-232`; `aluno_status.py:68-106` (coorte por turno); filtros da listagem por “turno da oferta”.
**Testes:** turno por oferta na listagem e no painel do conselho; turma com ofertas em turnos diferentes aparece uma vez por oferta no painel e com o filtro correto.
**Riscos:** turma com ofertas em turnos distintos passa a aparecer 2× em relatórios (esperado); sinais de “noturno” podem mudar de valor.
**Pronto quando:** nenhum filtro de programa/turno ler `Turma.programa/turno` quando a turma tem oferta ativa.

### D3b.8 — Fase 7: oferta de origem/destino em `Transferencia` (risco: médio-alto; migration)
**Escopo:** migration aditiva (`turma_curso_origem_id`/`destino`, FKs RESTRICT, nullable, índices), backfill inequívoco, `scripts/verificar_onda4_d3b.py` (somente leitura), escrita em `alunos.py:1151-1162`, leitores (`transferencias_por_curso`, `turma_tem_historico`, histórico do aluno), MER §7.16/§8.10/§11.
**Testes:** `test_transferencia_oferta.py` (estender), `test_d3b_transferencia_schema.py` (colunas/índices/backfill em SQLite e premissas de RESTRICT), ensaio em banco scratch (A–E) como na D5.5.
**Riscos:** backfill ambíguo (2+ candidatas) — não preencher e listar; downgrade que perde a informação nova (documentar como irreversível em dados).
**Pronto quando:** transferência nova grava as 2 ofertas; BI por curso de origem correto; ensaio A–E com mensagens capturadas.

### D3b.9 — `turma_lixeira`: template e rota de reativar (risco: baixo)
**Escopo:** criar `app/templates/turma_lixeira.html` (lista com unidade, período, motivo, data), filtrar por `unidade_id` (`turmas.py:707` hoje vaza entre unidades), nova rota `POST /turma/<id>/reativar` com `assert_unidade_context` e regra: reativar turma reativa **ao menos uma** oferta (ou exige escolha da oferta) e não reativa inscrições automaticamente; link “Lixeira” na listagem.
**Testes:** `test_turma_lixeira.py` (acesso por perfil, isolamento de unidade, reativar turma com histórico, turma com todas as ofertas inativas).
**Riscos:** reativar turma sem oferta ativa reproduz o estado “turma sem conselho” (§8.2) — a regra acima evita.
**Pronto quando:** `/turmas/lixeira` responde 200 e `/turma/<id>/reativar` funciona com auditoria (`LogAcao`).

---

## Perguntas em aberto (dependem do responsável) — com recomendação

1. **Como exibir frequência de turma com 2+ ofertas no painel e no BI: linha por oferta, agregado, ou ambos?**
   *Recomendação:* **ambos, com rótulos explícitos** — linha por oferta (“Turma X — Curso A”) e uma linha “Turma X (todas as ofertas)” para os sinais que já são de turma; hoje `agregar_por_turma` esconde a quebra (`frequencia.py:26`).
2. **`Turma.programa` e `Turma.turno` continuam sendo fonte de filtro?**
   *Recomendação:* **não** quando a turma tem oferta ativa: filtro por `COALESCE(oferta, turma)`; manter as colunas apenas como projeção da oferta principal (já documentado no MER §8.10) e como fallback para turma sem oferta.
3. **ALU-009/ALU-010: aluno em 2 cursos conta 2 vezes?**
   *Recomendação:* **sim, distinto por curso** (é o que a dimensão pede) e documentar no catálogo que a soma dos cursos pode exceder “alunos distintos” da unidade. Manter `count(distinct aluno)` dentro de cada curso.
4. **Professor da oferta quando `TurmaCurso.professor_id` é `NULL`: herda o da turma ou fica “sem responsável”?**
   *Recomendação:* **herdar** (fallback explícito, como já faz `_resumo_ofertas`), com aviso na tela de ofertas de que a oferta não tem responsável próprio; remover o fallback só depois de um diagnóstico de quantas ofertas estão nessa situação.
5. **`Transferencia` histórica: backfill agora ou só gravar daqui para frente?**
   *Recomendação:* **nullable + backfill inequívoco + relatório de ambíguos** (mesmo padrão da D5.1); sem NOT NULL nesta fase.
6. **`Turma.avaliacao_*` (MER §12.19): remover junto da D3b?**
   *Recomendação:* **não** — depende do dump autêntico; fica fora do D3b e vira etapa própria de limpeza.
7. **Frequência legada (`turma_curso_id IS NULL`): a tela por oferta deve exibi-la?**
   *Recomendação:* **só na oferta única** da turma (regra D2 já implementada na pauta) e, quando houver 2+ ofertas, exibir aviso “N lançamentos legados sem oferta” com link para a tela legada — nunca somar a uma oferta arbitrária.
8. **`/professor/painel` deve ser removido ou virar redirect do dashboard novo?**
   *Recomendação:* **redirect** na D3b.6 (preserva links antigos) e remoção do template em etapa posterior; hoje ele é a fonte da divergência de autorização.
9. **Teste manual no navegador (CSRF/UX) é critério de pronto de qual etapa?**
   *Recomendação:* **D3b.5** (fumaça) para as telas de leitura e **D3b.6** para conselho/pauta após a autorização — a suíte roda com `WTF_CSRF_ENABLED=False` (MER §12.24).

---

## Anexos

### A. Comandos usados (somente leitura)
```
python instance/backups/d3b0_scan.py            # rotas GET × citações em tests/
python -m ruff check app --select F821,F811,F841
git status --porcelain
grep/Select-String por turma_id, turma_curso_id, freq_geral, professor_id, status_alunos
```

### B. O que foi verificado no código e não é pendência (correções ao backlog/MER)
| Afirmação anterior | Estado real |
|---|---|
| “ALU-009/ALU-010 sem `cond_inscricao_enturmada`” | **aplicado** (`bi_alunos.py:507`, `:597`) — a pendência é o `curso_id`/`professor_id` por `Turma.*` |
| “Resta um `date.today()` em `dashboard_professor.py` (~L123)” | **não existe**; o módulo usa `get_local_now()` (`:297`). `date.today()` permanece em `bi_alunos.py` (4×), `conselho.py:768/777`, `periodos.py:277/294`, `rota.py:33`, `turmas.py:1743`, `logica.py:289`, `enturmacao.py:91` |
| “Ficha 360° sem seletor de oferta” (D5.4 §5.3) | **resolvido na D5.5** (`?oferta_sel=` + `<select>`) |
| “`_montar_turma_linha` inexistente” | **resolvido na B7**; `ruff F821` = 0 |
| “Conselho, ficha, BI e transferências ainda leem por `turma_id`” (L3 §8.10) | conselho/ficha/histórico/certificado **já por oferta**; restam frequência, BI de frequência, `freq_geral` e relatórios (este documento) |

### C. Confirmação de escopo
Nenhum arquivo de código, teste, migration ou doc existente foi alterado; nenhum commit. Além deste documento, foi criado apenas `instance/backups/d3b0_scan.py` (helper de varredura, diretório ignorado pelo Git) e sua saída `instance/backups/d3b0_scan.txt`/`d3b0_ruff.txt`.

**Observação de escopo (não atribuída a esta etapa):** durante a execução, `git status` passou a exibir `M app/templates/turmas/listar.html` (19:48), `?? app/templates/turmas/listar copy.html` (19:39), `?? runtests.bat` (19:50) e `?? tmp_test.txt` (19:48). Nenhuma ferramenta de edição desta etapa tocou esses caminhos — a alteração é do ambiente/usuário e **não** faz parte do D3b.0. O restante do `git status` (40 arquivos modificados + relatórios/novos testes das etapas B7–D5.5 e L3) é o estado herdado, sem commit por protocolo.
