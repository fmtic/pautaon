# ETAPA T1 — Relatório de reparo da suíte após `c3d4e5f6a7b8` e `d4e5f6a7b8c9`

Data: 24/10/2026 · Ramo: `Onda4` · Escopo alterado: **somente `tests/`** · **Nenhum commit foi feito.**

---

## 1. Resultado da suíte

| Momento | Passed | Failed | Errors |
|---|---|---|---|
| partida (docs/V1_relatorio.md) | 88 | 120 | 11 |
| após T1 | **210** | **10** | **0** |

Comando de reprodução (PowerShell, na raiz do repositório):

```powershell
$env:PYTHONPATH="."
.\.venv\Scripts\python.exe -m pytest tests -q --tb=line
```

Contagem por arquivo (execução individual, pós-T1):

| Arquivo | Resultado |
|---|---|
| test_aluno_perfil.py | 5 passed |
| test_aluno_status.py | 10 passed |
| test_bi_indicadores.py | 6 passed |
| test_bi_turma_desativada.py | 9 passed |
| test_carga_horaria.py | 19 passed |
| test_carga_horaria_curso.py | 1 passed |
| test_dashboard.py | 3 passed |
| test_enturmacao_oferta.py | 13 passed |
| test_filtros_turmas.py | 15 passed, **1 failed** (bug de produção, §4.1) |
| test_maintenance.py | 4 passed |
| test_pauta_professor.py | 2 passed |
| test_sec01_uploads.py | 3 passed |
| test_security_regressions.py | 21 passed, **2 failed** (preexistentes de `/cursos`) |
| test_transferencia_oferta.py | **8 passed** (arquivo novo, passo 4) |
| test_turma_curso.py | 7 passed |
| test_turma_curso_edicao.py | 11 passed, **1 failed** (bug de produção, §4.3) |
| test_turma_curso_exclusao.py | 8 passed |
| test_turma_curso_fase2.py | 14 passed |
| test_turma_curso_fase3.py | 16 passed, **4 failed** (§4.2) |
| test_turma_curso_fase4.py | 21 passed, **2 failed** (§4.4) |
| test_turma_curso_fase4_dash.py | 5 passed |
| test_turma_curso_lista.py | 9 passed |

**A meta "só as 2 falhas preexistentes de `/cursos` permanecem" não foi alcançada e não pode ser alcançada sem tocar em `app/`.** As 8 falhas restantes são bloqueadas por quatro defeitos de código de produção documentados em §4. Conforme a regra desta etapa, eles foram **parados e reportados, não corrigidos**.

---

## 2. Causas das falhas de partida

| # | Causa | Efeito observado | Tratamento |
|---|---|---|---|
| (a) | `d4e5f6a7b8c9` → `TurmaCurso.programa` NOT NULL. Sementes criavam ofertas sem programa. | `IntegrityError: NOT NULL failed on turma_curso.programa` em quase todas as sementes de oferta; `adicionar_oferta(...)` levantando `ValueError("Toda oferta precisa ter um programa.")`. | Toda semente de oferta passou a informar programa (`programa="Teste"`, ou `PROGRAMA_PADRAO` do helper); chamadas de `adicionar_oferta` e formulários `ofertas/nova` ganharam o campo. |
| (b) | `c3d4e5f6a7b8` → `Inscricao.turma_curso_id` NOT NULL + índice único parcial `uix_inscricao_ativa_aluno_oferta (aluno_id, turma_curso_id) WHERE ativo`. | `IntegrityError` de NOT NULL e, depois de dar oferta às inscrições, `UNIQUE constraint failed: inscricoes.aluno_id, inscricoes.turma_curso_id` onde a semente duplicava a ativa na mesma oferta. | Cada `Inscricao` de semente passou a apontar para uma oferta concreta; duplicatas na mesma oferta foram reencaminhadas para uma 2ª oferta (ou removidas, quando o teste era justamente sobre o índice). |
| (c) | Testes da Etapa M1.1 (adoção/vínculo de inscrições NULL) e leitores de fallback NULL. | Pressupõem um estado (`turma_curso_id IS NULL`) que o banco não permite mais; eram falhas por premissa, não por defeito. | Removidos no passo 3, por ordem expressa, e substituídos por testes do estado válido + rede de segurança do índice. |
| (d) | `KeyError: 2026` em `test_filtros_turmas.py::test_rota_listagem_aplica_filtro_nome`. | 500 na rota `/turma`. | **Bug de produção confirmado** (§4.1) — parei e reportei. O teste não é dependente de data: a semente não cadastra nenhum `PeriodoLetivo`, e a rota indexa o dicionário pelo ano corrente sem proteção. |
| (e) | *Descoberta nesta etapa:* asserções de substring sobre o HTML inteiro em `test_turma_curso_lista.py`. | 4 falhas que pareciam "filtro não aplicado" (já listadas no V1 como "asserts de conteúdo de HTML"). | Falso alarme de teste: os `<select>` de "Nome da Turma"/"Professor" listam todas as turmas/professores da unidade independentemente do resultado filtrado (comportamento documentado em `app/models/MER.md`, Etapa K2). Escopadas para a linha da tabela (§3, arquivo 14). |

Nenhuma semente foi "consertada" mudando o que o teste verifica: quando o vínculo NULL deixou de existir, a oferta foi escolhida de modo a preservar exatamente as mesmas contagens/valores que o teste já media.

---

## 3. Diff por arquivo

Legenda: **[P]** = passos do enunciado; **O** = oferta (`TurmaCurso`); **I** = inscrição (`Inscricao`).

1. **`tests/_helpers.py`** — *novo* (passo 1). 84 linhas. Documenta as duas migrations e centraliza os NOT NULL:
   - `PROGRAMA_PADRAO = "Programa de Teste"`;
   - `nova_oferta(turma_id, curso_id, unidade_id, *, programa=PROGRAMA_PADRAO, ativo=True, principal=False, salvar=True, **campos)`;
   - `nova_inscricao(aluno_id, turma_id, turma_curso_id, *, ativo=True, salvar=True, **campos)` — levanta `ValueError` se `turma_curso_id is None`, para impedir o retorno do estado extinto;
   - `salvar=False` existe para os testes que precisam forçar `IntegrityError` no commit.
2. **`tests/test_turma_curso.py`** — O: `programa="Teste"` em 3 sementes de oferta. Nada mais. 7 passed.
3. **`tests/test_turma_curso_fase2.py`** — O: `programa="Teste"` em todas as ofertas de `base`; I: inscrição ligada à oferta criada; chamada `adicionar_oferta(..., programa="Teste")`. 14 passed.
4. **`tests/test_turma_curso_fase3.py`** — O: `programa="Teste"` nas ofertas e kwarg obrigatório em `adicionar_oferta`; form `ofertas/nova` ganhou `"programa": "Teste"`. 16 passed + 4 falhas de produção (§4.2) — os testes de bloqueio de concomitância **não foram alterados em sua finalidade**.
5. **`tests/test_turma_curso_fase4.py`** — O: `programa="Teste"` em ~8 sementes; I: NULL removido da fixture `base`; removidos 3 testes que só existiam para o estado NULL (`test_aluno_com_duas_inscricoes_aparece_uma_vez_na_pauta`, `test_contagem_sem_curso_conta_aluno_uma_vez`, `test_inscricao_null_entra_com_1_oferta_e_fica_fora_com_2`), com o caso válido remanescente renomeado para `test_aluno_da_oferta_aparece_no_modo_estrito`; dívida de teste corrigida: `_mk_app_criacao` agora cadastra `PeriodoLetivo` e `_post_nova_turma` envia `periodo_letivo_id` (obrigatório desde `turmas.py:719`) e `programa`. 21 passed + 2 falhas de produção (§4.4).
6. **`tests/test_turma_curso_fase4_dash.py`** — O: `programa="Teste"` em uma oferta. 5 passed.
7. **`tests/test_turma_curso_exclusao.py`** — O: `programa="Teste"`; I: oferta da outra turma criada e vinculada. 8 passed.
8. **`tests/test_turma_curso_edicao.py`** — O: `programa="Teste"` nas sementes; monkeypatch atualizado do símbolo renomeado `_validar_horario_concomitante` → `_conflitos_horario_concomitante` (dívida de teste pura: o teste exercita o *rollback* da rota quando a validação explode, e como o nome antigo não existe mais ele nunca poderia passar). 11 passed + 1 falha de produção (§4.3).
9. **`tests/test_aluno_status.py`** — O: uma oferta ativa por turma (curso criado) e helper `_inscricao(..., oferta=None)` que resolve a oferta ativa da turma; onde a semente precisava de uma 2ª linha para o mesmo aluno, ela foi colocada em **outra oferta** da mesma turma (a mesma oferta duplicada violaria o índice novo) — as contagens de status ficaram idênticas. 10 passed.
10. **`tests/test_bi_indicadores.py`** — O: `programa="Teste"`; I: inscrição vinculada à única oferta ativa da turma (o fallback "NULL + oferta única" contava do mesmo jeito, logo os números do indicador não mudaram). 6 passed.
11. **`tests/test_bi_turma_desativada.py`** — O: `curso_z` + 2ª oferta `o1b` na mesma turma; I: `a4` anexado à oferta `o1`; `a3` **removido** (era o aluno "ambíguo por NULL", estado inexistente) com ajuste honesto de `total_inscricoes` de 6 → 5; `a6`, que tinha duas ativas na mesma oferta (violação do índice), movido para `o1`+`o1b` mantendo a turma com 5 linhas / média 2,5 / 4 distintos; `test_regressao_sem_turma_desativada` ganhou curso+oferta. 9 passed.
12. **`tests/test_pauta_professor.py`** — O: oferta associada à grade de aulas, `programa="Teste"`; I: inscrição da semente vinculada. 2 passed.
13. **`tests/test_security_regressions.py`** — O: `programa="Teste"` nas ofertas usadas nos fluxos de turma; I: inscrições com oferta. As **2 falhas preexistentes de `/cursos`** (`test_cursos_exigem_unidade_e_isolam_cursos_de_outra_unidade`, `test_curso_criar_editar_inativar_e_validar_carga_horaria`) permanecem exatamente como estavam no V1: `assert 200 == 403` e `assert 200 == 400`. 21 passed + 2 falhas pré-existentes.
14. **`tests/test_turma_curso_lista.py`** *(descoberta nova, causa (e))* — adicionado `_linha(body, turma_id)`, que procura o link de ação da turma (`href="/turma/<id>"`) em vez de procurar o nome no HTML inteiro; as 7 asserções de presença/ausência de `T1`/`T2`/`T3` passaram a usar o marcador. Finalidade preservada (o que se testa continua sendo "o filtro por oferta casa / não casa a turma"); **os filtros funcionam** — quem estava errado era o marcador. 9 passed.
15. **`tests/test_enturmacao_oferta.py`** *(passo 3)* — REMOVIDOS: `_null_ativa`, `test_adota_null_ativa_com_uma_oferta`, `test_adota_null_ativa_com_duas_ofertas`, `test_nao_adota_null_inativa`, `test_adota_apenas_menor_id_entre_duas_null`, `test_duplicata_recusada_apos_adocao`, `test_adicionar_oferta_vincula_null_ativas`. MANTIDOS/AJUSTADOS: `programa="Teste"` em todas as ofertas; `test_duplicata_mesma_oferta_recusada` fortalecido com `assert r1.status_code == 302` e `r2 == 302` (a rota faz pré-checagem de duplicata, `flash` + redirect — nunca 500). ACRESCENTADOS: `test_indice_unicidade_bloqueia_duplicata_ativa_mesma_oferta` (usa `_helpers.nova_inscricao`, espera `IntegrityError` do `uix_inscricao_ativa_aluno_oferta` e confirma 1 ativa após rollback) e `test_duas_ofertas_diferentes_mesma_turma_nao_violam_indice` (aluno em duas ofertas da mesma turma → 2 ativas). 13 passed.
16. **`tests/test_transferencia_oferta.py`** *(novo, passo 4)* — 8 testes sobre `/aluno/transferir/<aluno_id>` usando `_helpers.nova_oferta`/`nova_inscricao`: destino com 1 oferta (GET lista a oferta e POST transferir); destino com 2 ofertas (POST **sem** `turma_curso_id_destino` é recusado sem alterar nada; **com** escolha grava na oferta apontada); recusa de oferta de destino **inativa**; recusa de oferta da **própria turma de origem**; recusa de oferta de turma de **outra unidade**; usuário de outra unidade → **403** no GET e no POST; usuário da mesma unidade → 200 com o destino no select; e os **efeitos** (origem `ativo=False`, `motivo_desativacao="TRANSFERENCIA"`, `data_desativacao` = véspera, nova inscrição ativa na oferta escolhida com `data_inicio` da transferência, registro `Transferencia` com turmas de origem/destino e observações). 8 passed.

Total do diff: 14 arquivos modificados + 2 criados, **+370/−344 linhas** em `tests/`. **Zero alterações em `app/`, `migrations/`, `scripts/` ou configuração.**

---

## 4. Bugs de produção encontrados (PAREI e reportei; não corrigi)

### 4.1 `KeyError` no ano corrente → 500 em `/turma` (1 teste)
`app/registros/turmas.py:440` monta `anos_periodos = [ano_atual]` **incondicionalmente** (ano de `get_local_now()`), enquanto `periodos_por_ano` (§ L436-439) só contém chaves dos anos de `data_inicio` dos períodos existentes. `app/registros/turmas.py:472` faz `for periodo in periodos_por_ano[ano]:` sem `.get()`.
**Reprodução:** qualquer unidade sem período letivo cujo `data_inicio` caia no ano corrente → `KeyError: <ano>` → 500. Em `test_filtros_turmas.py::test_rota_listagem_aplica_filtro_nome` a semente não cadastra período nenhum, daí `KeyError: 2026`.
**Consequência prática:** na virada de ano, a listagem de turmas quebra para toda unidade que ainda não cadastrou o período do novo ano — exatamente o cenário mais comum.
**Correção sugerida (fora do escopo desta etapa):** `periodos_por_ano.get(ano, [])`, ou derivar `anos_periodos` das chaves reais mantendo o ano corrente apenas como etiqueta visual.

### 4.2 Concomitância de horário deixou de bloquear (4 testes)
`app/services/turma_curso.py:347` e `:422` chamam `_conflitos_horario_concomitante(...)`, que agora **retorna lista de avisos**; a rota `ofertas/nova` os transforma em `flash` e grava mesmo assim (ver o comentário em `app/registros/turmas.py:1330` — "Conflitos de horário geram apenas aviso"). Os testes de fase 3 esperam `ValueError`/recusa: `test_adicionar_oferta_sobreposicao_total_bloqueada`, `test_adicionar_oferta_sobreposicao_parcial_bloqueada`, `test_editar_oferta_cria_conflito_bloqueado` (todos `DID NOT RAISE`) e `test_rota_oferta_nova_conflito_rejeitada` (`assert 2 == 1` — as duas ofertas foram salvas).
**Isto é uma mudança de regra de negócio, não um defeito óbvio.** Não alterei os testes: eles são a única guarda automatizada contra oferta sobreposta, e reescrevê-los para "aceita com aviso" apagaria a decisão em vez de registrá-la. **Exige sua decisão** (§6, item P1).

### 4.3 `editar_turma` com 2+ ofertas descarta o programa (1 teste)
No ramo `n_ativas >= 2` (`app/registros/turmas.py:1154-1214`) a rota grava apenas `nome`, `periodo_letivo_id` e `ordenacao`; **não lê `programa` do form nem chama `sincronizar_programa_turma`** — as chamadas de sincronização existem só nos ramos de 0/1 oferta (L1351/L1353). Antes do commit `853d241` ("programa na oferta e correção de drift") havia `turma_obj.programa = request.form.get("programa")` nos dois ramos; a escrita sumiu e a projeção não cobre o caso multi-oferta.
**Efeito:** a tela de edição mostra o `<select>` de programa, o usuário escolhe um valor, recebe 302 de sucesso e nada é gravado; em turmas multi-oferta `Turma.programa` pode ficar `NULL` para sempre, quebrando a projeção e o filtro `Turma.programa == programa` (L299-301). `test_edicao_duas_ofertas_ignora_campos_de_oferta` falha em `assert None == 'Esporte'` (as demais asserções do mesmo teste passam: os campos de oferta são corretamente ignorados).

### 4.4 `/turma/nova` cria turma sem programa e, por isso, nunca salva turma com curso (2 testes)
`app/registros/turmas.py:804` fixa `programa=None` no `Turma(...)` e a rota **não coleta `programa` do formulário** (a coleta existe apenas para oferta, L1474-1476). Em seguida L824 chama `criar_oferta_inicial_da_turma(nova)`, que exige `turma.programa` (`app/services/turma_curso.py:284-285` → `ValueError("Toda oferta precisa ter um programa.")`). O `except` de L831 faz `rollback` e flash genérico.
**Efeito:** criar turma com um curso pelo formulário oficial está quebrado — sempre "Não foi possível salvar a turma". Os 2 testes de criação de turma em fase 3/4 (`test_nova_turma_com_curso_gera_uma_oferta_principal_false`, `test_frequencia_lancada_em_turma_nova_grava_turma_curso_id`) falham por isso.

---

## 5. Decisões tomadas

1. **Um helper único, sem conftest.** `tests/_helpers.py` em vez de fixtures globais: os testes usam quatro padrões de fixture distintos (app por fixture, app por função `_novo_app()`, app sem contexto, `client` fixture); um `conftest.py` teria que unificá-los todos — mudança maior do que o necessário agora. O helper só conhece os dois NOT NULL novos e não conhece regras de negócio.
2. **Nada da finalidade foi alterado.** Quando o NULL sumiu, a escolha da oferta foi feita para manter as **mesmas contagens e valores** que o teste media (ver `test_bi_turma_desativada`: `a4`→`o1`; `a6`→`o1`+`o1b` numa 2ª oferta da mesma turma; `a3` removido e `total_inscricoes` ajustado de 6 para 5, porque aquele aluno só existia como NULL e nenhum reencaminhamento manteria 6). Onde isso era impossível, o teste foi removido e o motivo registrado (passo 3).
3. **Estado proibido ≠ caso de teste.** Não mantive testes "forçando" NULL com `bulk_insert` ou `session.execute(text(...))`: o SQLite dos testes honra o NOT NULL e o índice, e um teste que precisa violar o schema para existir é dívida, não cobertura.
4. **Os testes de índice foram colocados no nível certo.** A duplicata ativa na mesma oferta é recusada (1) pela rota, com flash/302, e (2) pelo banco, com `IntegrityError` — os dois são testados separadamente, porque a rota tem pré-checagem e o índice é a rede de segurança para escritas fora dela.
5. **Não reescrevi os testes de concomitância (4.2) nem os de `/cursos` preexistentes.** O enunciado autoriza mexer em `tests/`, mas redefinir "bloqueio" para "aceita com aviso" é decisão de negócio, não reparo de semente.
6. **Nota de harness descoberta (importante para testes futuros de autorização).** Os fixtures que mantêm `with app.app_context(): yield test_app` deixam o AppContext aberto durante as requisições, e o Flask **reutiliza** esse AppContext em cada request. Como `flask.g` vive no AppContext, o `_login_user` cacheado pelo Flask-Login vaza: um segundo `test_client()` com outro usuário age como o primeiro. Em produção cada request empurra seu próprio AppContext, logo **não é bug de código**. Por isso `test_transferencia_oferta.py` usa **um único usuário por teste** (o caso "legítimo vê 200" e o caso "intruso recebe 403" foram separados em dois testes) e documenta a razão no docstring. Este era um candidato a falso positivo silencioso em toda a suíte: qualquer teste que troque de usuário dentro do mesmo teste está medindo a identidade errada.
7. **Nenhum commit, nenhuma alteração fora de `tests/`.** Os arquivos temporários de debug criados durante a investigação (`tests/_dbg_transf.py`, `tests/_dbg_body.html`, `tests/_dbg_lista.py`) e os resíduos de execução da suíte na raiz (`_t1_suite.txt`, `_t1_line.txt`) foram apagados; restam apenas os `.pyc` obsoletos em `tests/__pycache__/`, que são ignorados pelo git.

---

## 6. Pendências

| # | Pendência | Onde | Tipo | Prioridade |
|---|---|---|---|---|
| P1 | Decidir a regra de concomitância: reimplantar bloqueio em `adicionar_oferta`/`editar_oferta` **ou** atualizar os 4 testes de fase 3 para "grava com aviso". Enquanto não decidido, 4 falhas permanecem. | `app/services/turma_curso.py:347,422`, `tests/test_turma_curso_fase3.py` | Negócio | Alta — oferta sobreposta já é gravável hoje |
| P2 | Corrigir o `KeyError` do ano corrente (usar `.get(ano, [])` em `periodos_por_ano`). | `app/registros/turmas.py:440,472` | Defeito | Alta — 500 na listagem a cada virada de ano |
| P3 | Coletar `programa` no `/turma/nova` (ou derivá-lo do curso/período) antes de `criar_oferta_inicial_da_turma`. | `app/registros/turmas.py:802-835` | Defeito | Alta — fluxo oficial de criação de turma quebrado |
| P4 | Gravar/sincronizar `programa` no ramo `n_ativas >= 2` de `editar_turma`, ou remover o `<select>` de programa da tela quando a turma é multi-oferta. | `app/registros/turmas.py:1154-1214`, `app/templates/turmas/editar.html` | Defeito (UI mente) | Média |
| P5 | **Código morto introduzido pelo fim do NULL:** `cond_inscricao_enturmada` ainda tem o ramo `turma_curso_id.is_(None)` + "oferta única" (`app/relatorios/bi_filtros.py:62-72`) e `_alunos_da_oferta(..., incluir_inscricoes_null=...)` continua aceitando o parâmetro. Inalcançável desde `c3d4e5f6a7b8`. | `app/relatorios/bi_filtros.py`, `app/services/turma_curso.py` | Dívida | Média — risco de leitura equivocada do modelo por próximos contribuidores |
| P6 | As 2 falhas preexistentes de `/cursos` (isolamento de unidade `403→200` e validação de carga horária `400→200`) permanecem — fora do escopo de T1, mas **são de segurança/validação**, não de semente. | `tests/test_security_regressions.py:482,512` | Defeito | Alta |
| P7 | Padronizar os fixtures de teste (um `conftest.py` com `app`/`client` e contexto por request) evitaria a armadilha do §5.6 e permitiria testes de autorização multiusuário no mesmo teste. | `tests/` | Dívida de harness | Baixa/Média |
| P8 | `test_turma_curso_lista.py::test_linha_multi_mostra_dois_professores_e_uniao_de_dias` ainda usa substring global ("Prof A"/"Prof B" no HTML inteiro), que é satisfeito pelo `<select>` de professores. Passa, mas é fraco: mereceria escopo na linha da turma como os demais. | `tests/test_turma_curso_lista.py:189-196` | Dívida de teste | Baixa |
| P9 | **Fora do meu escopo, registrado para não se perder:** `git status` acusa a remoção (working tree) de três documentos rastreados — `docs/M1_relatorio.md`, `docs/M1_1_relatorio.md` e `docs/checklist_seguranca_dividas_tecnicas.md`. Não os criei, editei ou apaguei nesta etapa (escopo: só `tests/`) e eles continuam íntegros em `HEAD`. Se a remoção foi sem querer, `git checkout -- docs/M1_relatorio.md docs/M1_1_relatorio.md docs/checklist_seguranca_dividas_tecnicas.md` os restaura. | `docs/` | Integridade do repositório | Média — exige sua decisão |

---

## 7. O que a suíte cobre agora (novos casos desta etapa)

- `uix_inscricao_ativa_aluno_oferta`: duplicata ativa na mesma oferta recusada pelo banco; duas ofertas da mesma turma permitidas (`test_enturmacao_oferta.py`).
- Transferência entre ofertas: 8 cenários de `test_transferencia_oferta.py`, incluindo os 403 de unidade e os efeitos sobre `Inscricao`/`Transferencia`.
- Listagem por oferta com filtros COALESCE (oferta→turma) verificados por marcador de linha, não por substring (`test_turma_curso_lista.py`).
