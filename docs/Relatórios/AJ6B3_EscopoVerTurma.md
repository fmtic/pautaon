# AJ6-B3 — escopo de OFERTA na ficha da turma e no dashboard do professor

Etapa da série AJ. Branch `nova_feature`, base `f763ba6` (HEAD da AJ6-B2). Sem
migration, sem push, **nenhuma escrita em banco real** (somente SELECT), nomes
sintéticos em teste, reversão provada em `git worktree` com caminho absoluto.

Decisões do responsável que orientaram a etapa:

1. `ver_turma`: o professor **continua entrando** na turma onde leciona alguma
   oferta ativa (régua de entrada inalterada); o **payload e o HTML** ficam
   restritos às ofertas dele. Reusar `professor_pode_acessar_oferta` /
   `ofertas_do_professor`, sem duplicar a regra.
2. Remover o fallback `Turma.professor_id` do dashboard: "professor da turma"
   não existe; só professor da oferta.

---

## 1. `ver_turma` — o que foi escopado e o que foi mantido

Rota: `ver_turma` em `app/registros/turmas.py`. Contexto renderizado:
`app/templates/turmas/detalhe.html`. O bloco novo atua **só** quando
`current_user.role == UserRole.PROFESSOR`, depois de toda a resolução que a
propária rota já fazia, e usa apenas `ofertas_do_professor(usuario, ofertas)` —
que por dentro é `professor_pode_acessar_oferta` → `professor_da_oferta`
(`app/services/aluno_info_professor.py`). **Nenhuma predicação nova de acesso.**

### 1.1 Escopado (cai da visão/payload do professor)

| # | Item | Onde | Antes | Depois |
|---|------|------|-------|--------|
| E1 | `ofertas_todas` → cards "Ofertas da Turma" | `turmas.py` (bloco AJ6-B3) | todas as ofertas da turma (inclusive inativas) | só as ofertas que ele acessa |
| E2 | `alunos_por_oferta` (nomes, fotos, `aluno_id` em links/ações) | idem | inscrições de **todas** as ofertas | `Inscricao.turma_curso_id ∈ ofertas dele` |
| E3 | `grade_oferta_map` (dias/horários por oferta) | idem | chave por todas as ofertas | filtrado pelas ofertas dele |
| E4 | `ofertas_lista` (template: `ofertas`) | idem | todas as ativas | só as ativas dele |
| E5 | `ctx["alunos"]` (payload) | `carregar_contexto_turma` lista por turma | todos os alunos ativos da turma | só os matriculados nas ofertas dele |
| E6 | `ctx["datas"]` / `ctx["meses"]` (payload/seletor) | união da agenda de todas as ofertas | agenda `datas_aula_oferta` das ofertas ativas dele; meses recompostos |
| E7 | `ctx["temas"]` (payload) | temas do `turma.curso_id` ou da turma | temas dos **cursos das ofertas dele** |
| E8 | `alunos_ativos_count` (badge "Alunos ativos") | contagem da turma inteira | contagem nas ofertas dele |
| E9 | `alunos_sem_turma` (modal de enturmar) | lista de candidatos da turma | `[]` para o professor (o modal já é negado por papel) |
| E10 | `oferta_sel` (`?oferta_sel=`) | aceita qualquer oferta ativa | `None` se a oferta pedida não é dele |
| E11 | links `?oferta_sel=` do dropdown CONSELHO | base `ofertas` da turma | base `ofertas_do_professor` (detalhe.html) |
| E12 | `turma_curso=<id>` em links de Diário/enturmar/transferir | saía com id de oferta alheia | só ids das ofertas dele (consequência de E1/E4) |
| E13 | `{{ oferta.professor or turma.professor }}` | detalhe.html:109 | `{{ oferta.professor }}` — ramo inalcançável (`TurmaCurso.professor_id` é `NOT NULL` desde `d6e7f8a9b0c1`); sem o fallback, nenhum nome de "professor da turma" sai da tela |

### 1.2 Mantido (e por quê)

| # | Item | Justificativa |
|---|------|---------------|
| M1 | Régua de entrada: `professor_de_alguma_oferta_ativa(id, current_user)` (`turmas.py:1394-1398`) | Decisão 1 é explícita: quem leciona qualquer oferta ativa da turma continua abrindo a ficha. **Inalterada.** |
| M2 | `turma` (nome, `programa`, `curso_id`, `turno`, `data_inicio/fim`, `centro_custo`) | Atributos do agregador TURMA, não derivados de oferta. É o objeto que o professor abriu legitimamente. |
| M3 | `oferta_principal` e o badge "Principal" | Projeção de nível de turma usada pelo campo "Centro de custo compartilhado". Não concede acesso; quando a principal não é dele o card simplesmente não aparece e o centro de custo sai "Não definido". |
| M4 | `niveis_cadastrados` | Catálogo da unidade (Planejamento), não por oferta. |
| M5 | Guarda de unidade `assert_unidade_context` e o `role not in [...]` das rotas | Camada de papel/isolamento já existente, fora do escopo desta decisão. |
| M6 | Contagem "N curso(s)" do título da seção | Derivada de E1: passa a contar as ofertas visíveis (subproduto do escopo, não decisão nova). |
| M7 | `alunos_ativos_count` exibido | **Escopado** (E8) porque a contagem é de inscrições, isto é, vem das ofertas. Não é agregado da turma inteira. |

### 1.3 Reuso da regra (sem duplicação) e código morto removido

- `ofertas_do_professor(current_user, ofertas_todas)` e
  `ofertas_do_professor(current_user, ofertas_lista)` — a lista filtrada do
  template (`ofertas_do_professor=...`), que já existia, é **preservada** com o
  mesmo cálculo de antes (sobre `ofertas_lista`), apenas agora a própria
  `ofertas_lista` sai escopada; nada de regra nova.
- `meses_de_datas(datas_iso)` extraído em `app/utils/logica.py`: era um laço
  inline de `carregar_contexto_turma`; virou função única para que a recomposição
  de `ctx["meses"]` após o filtro não copiasse o mapa de nomes de mês.
  `carregar_contexto_turma` passou a chamá-la (mesmo comportamento).
- Ramo legado de `Turma.professor_id` removido de
  `app/main/dashboard_professor.py` (seção 3) e o `if oferta is not None` /
  `else` mortos que ele alimentava.
- `or turma.professor` removido de `detalhe.html:109` (E13).

---

## 2. Snapshot do HTML para perfis não-professor (identidade estrutural)

`tests/test_aj6b3_snapshot_nao_professor.py` renderiza `/turma/T1` e `/turma/T2`
para **admin, pedagógico, secretaria, gerência e serviço social** (5 perfis ×
2 turmas = 10 páginas), normalizando o HTML **sem classes** (remove
`class="..."`, o campo oculto `csrf_token` e a `<meta name="csrf-token">`, que
nascem por sessão; colapsa whitespace). Não há JSON embutido nem `data-*` com
conteúdo de aluno na ficha — o único `data-nome` existe só dentro do modal de
enturmar (negado por papel) e o único `data-*` de agenda é de atributos da
grade, sem nomes.

| lado | arquivos | diferentes |
|------|----------|------------|
| ANTES (HEAD `f763ba6`) × DEPOIS (trabalho desta etapa) | 10 | **0** |

A única variação entre as duas execuções era o token CSRF (uma string por
sessão), neutralizada pela normalização. **Nenhuma mudança de estrutura ou
conteúdo** para os perfis não-professor.

---

## 3. Dashboard do professor — fallback removido

`app/main/dashboard_professor.py`, `_entradas_professor`:

-_branch_ 2 (`Turma.query.filter_by(professor_id=user_id, ativo=True)` para turma
sem oferta ativa) **eliminado**. A única fonte de entrada passou a ser
`TurmaCurso.ativo ∧ Turma.ativo ∧ TurmaCurso.professor_id == user_id`.
- Consequência: nenhuma entrada nasce com `oferta=None`, então os dois ramos
  condicionais que tratavam o legado foram achatados — o cálculo de
  `pendentes_count` (por oferta, com `datas_esperadas_oferta` +
  `frequencias_lancadas(turma_curso_id=...)`) e a soma de alunos sob gestão em
  `render_dashboard_professor` (`_alunos_da_oferta`).
- O ramo legado de `_aulas_pendentes` (0/1 oferta, por turma) **não** foi
  tocado: a função continua chamada sem `professor_id` pelo painel
  administrativo/secretaria, onde o caminho por turma é vivo.
- Testes afetados pelo comportamento antigo codificado:
  `tests/test_dashboard.py::test_dashboard_professor_exibe_turma_com_responsavel_direto`
  afirmava exatamente o fallback → reconvertido em
  `test_dashboard_professor_nao_exibe_turma_sem_oferta` (asserção invertida), e
  `tests/test_aj6b2_auditoria_ofertas.py::test_item5_ver_turma_corpo_markes_oferta_alheia`
  (caracterização do leak da AJ6-B2) teve as asserções invertidas.

### 3.1 Prova de que no dado real o dashboard é idêntico (SELECT-only)

`diferença` entre "antes" e "depois" = o conjunto (b) do código removido:
turmas **ativas** com `Turma.professor_id = professor` e **nenhuma oferta ativa**
na turma. Consultado em `pautaon` e `pautaon_ensaio`, ids e contagens apenas:

| banco | professores ativos | com turma SEM oferta ativa (queda potencial) | legado com oferta inativa dele OU inscrição ativa |
|-------|--------------------|----------------------------------------------|---------------------------------------------------|
| `pautaon` | 8 | **0** | **0** |
| `pautaon_ensaio` | 9 | **0** | **0** |

Conjunto (b) vazio nos dois bancos ⇒ as entradas do dashboard são
**matematicamente idênticas** antes/depois para todo professor real. Nenhum
professor perde linha, badge ou contagem.

---

## 4. Testes novos

`tests/test_aj6b3_escopo_professor.py` (11 testes) sobre a mesma malha da
AJ6-B2 (T1: A/pA principal, B/pB, C/pC; T2: D/pA principal, E/pA, F/pB; alunos
sintéticos "Aluno A".."Aluno F"; `Turma.professor_id` vestigial em T1=pA, T2=pB):

| teste | o que prova |
|-------|-------------|
| `test_b3_pA_em_T1_ve_so_a_oferta_dele` | entra (200), vê "Aluno A"; sem "Aluno B"/"Aluno C", sem os cards `detalhes-oferta-{B,C}`, sem link `turma_curso={B,C}` |
| `test_b3_pB_em_T2_ve_so_a_oferta_dele` | inversão: pB vê F e não D/E, inclusive sendo o professor vestigial da T2 |
| `test_b3_pA_em_T2_ve_as_suas_duas_ofertas_e_nao_F` | 2 ofertas próprias aparecem (D, E); F não; também com `?oferta_sel=D` |
| `test_b3_pB_em_T1_ve_so_B` / `test_b3_pC_em_T1_ve_so_C` | cada professor fica só com a sua oferta na mesma turma |
| `test_b3_professor_sem_oferta_na_turma_403` | régua de entrada: pC (0 ofertas em T2) toma 403, sem nome no corpo |
| `test_b3_admin_ve_todas_as_ofertas_e_alunos` | não-professor continua vendo a turma inteira |
| `test_b3_detalhe_do_professor_sem_oferta_alheia` | sem nome de curso alheio (CURSO-BRAVO/CHARLIE) nem registro de diário alheio (DIY-B/DIY-C) |
| `test_b3_links_de_conselho_do_professor_nao_apontam_para_oferta_alheia` | `?oferta_sel=` do dropdown nunca aponta para oferta de outro professor |
| `test_b3_dashboard_nao_mostra_turma_sem_oferta_mesmo_sendo_professor_dela` | turma ativa sem oferta com `Turma.professor_id = pA` fora do dashboard de pA |
| `test_b3_dashboard_entrada_do_professor_bate_com_suas_ofertas` | dashboard == conjunto de ofertas ativas do professor |
| (snapshot) `test_aj6b3_snapshot_nao_professor.py` | seção 2 |

---

## 5. Reportado sem corrigir — outras telas abertas por adesão à turma

Varredura dos usos de `professor_de_alguma_oferta_ativa` (todos os leitores) e
dos templates/rotas de turma/frequência. Estado por ponto:

| local | como o professor chega | vaza dado de outra oferta? | ação |
|-------|----------------------|---------------------------|------|
| `turmas.py:1394` `ver_turma` | adesão por oferta | **era sim** → corrigido nesta etapa | feito (seção 1) |
| `turmas.py:2807` `ver_observacoes` (Diário de Bordo) | adesão por oferta | não (AJ6-B já usa `ofertas_do_professor` no seletor/consulta e 403 em oferta alheia) | — |
| `core.py:263` `POST /frequencia` | adesão por oferta | não (oferta resolvida por `resolver_oferta_lancamento`; guarda final AJ6-B) | — |
| `core.py:432-546` `GET /frequencia` | lista de turmas por oferta | **resíduo pequeno**: com 2+ ofertas próprias e nenhuma escolhida (`exigir_escolha`), `ctx['alunos']`/`ctx['temas']` são zerados, mas `ctx['datas']`/`ctx['meses']` ficam na união da turma — os links "Pauta de <mês>" saem sem `turma_curso` e a impressão nega o professor (403). Sem nome de aluno no vazamento, só agenda | reportado |
| `alunos.py:1001` `historico_aluno` | **por aluno** (inscrição qualificada em oferta ativa dele) | **sim**: a listagem `Inscricao.query.filter_by(aluno_id)` não filtra por oferta, então o professor vê as demais inscrições do aluno (outras ofertas/turmas, inclusive inativas) e o professor de cada uma | reportado |
| `alunos.py:1332` `/aluno/<id>/foto` | por aluno (regra I1) | não (decisão por aluno/oferta qualificada) | — |
| `core.py:1462` `/api/alunos/<turma_id>` | papel | não (professor fora da whitelist → 403) | — |
| `turmas.py:718` `GET /turma` (listagem) | papel + unidade | **não é adesão**: todo professor vê as turmas ativas da unidade com ofertas, grade, carga horária e resumo de frequência (laço 727-768), além do dropdown de professores (886-895) | reportado |
| `conselho.py` (painel, lançamento, salvar, fechamento, imprimir) | oferta explícita / papel | não (matriz confirmada na AJ6-B2) | — |
| `turmas.py:2438+` `carga_horaria_turmas`, `relatorios/bi_alunos.py` | papel (`ROLES_RELATORIOS` não inclui professor) | inalcançável ao professor; `Turma.professor_id` aparece ali como **filtro**, não como concessão de acesso | — |

Pendências sugeridas para a próxima etapa (não abertas aqui): (i) escopar
`historico_aluno` por oferta; (ii) decidir a régua da listagem `/turma` para o
perfil professor (por adesão a oferta, como as telas de registro); (iii) zerar
`datas`/`meses` em `exigir_escolha` no GET /frequencia.

---

## 6. Verificações finais

- **Prova de reversão** (worktree `D:/pautaon/.tmp/aj6b3_rev` em `f763ba6`,
  HEAD sem os fixes, testes desta etapa copiados para lá):
  **10 falhas / 3 passes** em 13 selecionados. As 10 falhas são exatamente os
  marcadores esperados: 7 de escopo de `ver_turma`, 1 de `item5` invertido,
  2 de dashboard (`test_b3_dashboard_nao_mostra_turma...` e o reconvertido
  `test_dashboard_professor_nao_exibe_turma_sem_oferta`). Os 3 passes são os
  controles que não dependem do fix: `professor_sem_oferta_403`,
  `admin_ve_todas_as_ofertas` e `dashboard_entrada_bate_com_suas_ofertas`.
  Worktree removido em seguida (`git worktree list` só tem `D:/pautaon`).
- **ruff** `F821,F811,F841,F401` nos arquivos tocados: limpo.
- **Suíte completa**: ver seção 6.1 (executada uma vez, com o trabalho da etapa
  aplicado).
- **Contagens dos bancos reais antes/depois** (SELECT-only): idênticas —
  `.tmp/aj6b3_counts_before.json` × `.tmp/aj6b3_counts_after.json`.
- Commits separados: `test`, `fix(ver_turma)`, `fix(dashboard)`, `docs`.

### 6.1 Resultado da suíte e das contagens

- **Suíte completa** (uma execução, com os fixes da etapa aplicados, SQLite em
  memória, relógio congelado): **1495 passed, 1 skipped em 1193.82s** (0:19:53).
  Zero falhas. O 1 skipped é um teste já condicionado da base (alheio a esta
  etapa). Saída integral em `.tmp/aj6b3_suite_full.txt`.
- **Contagens dos bancos reais antes/depois** (`pautaon` e `pautaon_ensaio`,
  SELECT-only): **IDÊNTICAS** — `json_equal(.tmp/aj6b3_counts_before.json,
  .tmp/aj6b3_counts_after.json) == True` em todas as 18 tabelas, 8 sequências e
  nos campos compostos (`unidade_ids`, `frequencia_minmax`). Confirma que nenhum
  banco real foi escrito ao longo da etapa (só SELECT).
