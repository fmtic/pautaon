# A1 — Achados 1, 2 e 3 do M1 (correções) e 4–5 (análise)

**Data:** 28/10/2026 · **Branch:** `nova_feature` · **Base:** `e422ff0` · **Head Alembic:** `8d2e3f4a5b6c` (sem migration)

Escopo: corrigir os achados 1, 2 e 3 do roteiro manual (M1) e **apenas analisar** os 4 e 5.
Alterações em `app/` restritas a `app/services/frequencia_oferta.py`, `app/registros/alunos.py`
e `app/relatorios/bi_alunos.py`. Sem push.

| Item | Commit | Entrega |
|---|---|---|
| 1 — legado NULL no histórico | `45a1312` | regra D2 em `frequencias_aluno_por_inscricao` |
| 2 — `I: None` | `1a9bfda` | status sem `situacao_final` exibe `—` |
| 3 — BI × turma excluída | `71e5991` | `_base_frequencia`/`_base_registro_aula` com `turma.ativo` |
| 4 e 5 — análise | (sem código) | relatório + backlog (Pendências) + MER |

---

## 1. P0 — working tree

O estado mudou entre o pedido e a execução: **as mudanças alheias já estavam commitadas pelo
dono da máquina** no commit `e422ff0` (*"feat(frequência, planejamento): Inserir
valores/postura para cada aluno na chamada de frequência e criação de nova aba Valores do
Esportista..."*), que também subiu para `origin/nova_feature`. Nada foi tocado, apagado ou
adicionado ao stage por esta tarefa; o working tree estava limpo no início.

Os três arquivos citados no pedido:

| Arquivo | `git diff --stat` | `git diff -w --stat` |
|---|---|---|
| `app/templates/frequencia/lancar.html` | 78 linhas alteradas | 68 |
| `app/templates/planejamento/planejamento.html` | 412 linhas alteradas | 234 |
| `app/templates/frequencia/lancar copy.html` (novo) | 238 inserções | 238 |

**Não é só espaço em branco**: `-w` remove ~100 linhas do primeiro e ~178 do segundo, mas
sobram 68 + 234 + 238 — há quebra de atributos, reindentação e, principalmente, **conteúdo
novo** (a aba "Valores do Esportista" e as colunas de valores/postura na chamada). O
`lancar copy.html` é uma cópia integral (238 linhas) do template reformatado; continua no
repositório, como o dono deixou.

Outros dois arquivos não rastreados apareceram no diretório (`tmpexsgok03`, `tmpwe1fm69z`,
nomes gerados por ferramenta, não por esta tarefa) e **não** foram tocados. Os temporários
criados por esta tarefa (`tmp_len.py`, `tmp_bi_ensaio*.py`, `tmp_hist_ensaio.py`, `tmp_head_*.py`) foram apagados.

Commits desta tarefa foram feitos **por caminho explícito** (nunca `git add -A`).
Suíte na base: **722 passed**.

---

## 2. Item 1 — histórico do aluno ignorava o legado NULL

### TRAVA (P1) — o que a regra real dizia

`frequencias_aluno_por_inscricao` (`app/services/frequencia_oferta.py`) carregava **todas** as
linhas do aluno e indexava por `(turma_id, turma_curso_id)` exatos; o docstring dizia
explicitamente *"não aplica a regra D2 do legado (preserva números)"*. `historico_aluno`
(`app/registros/alunos.py`) passava `(insc.turma_id, insc.turma_curso_id)` de cada inscrição.
Ou seja: a regra real era **filtro exato**, divergindo do comportamento-alvo — que é
exatamente o achado a corrigir, e o alvo coincide com a regra que `agregar_por_oferta` já
aplica (`ofertas_unicas_ativas`). **TRAVA não acionada.**

Uma restrição de schema encontrada: `Inscricao.turma_curso_id` é **NOT NULL** desde
`c3d4e5f6a7b8`, então "inscrição legada (sem oferta)" não existe mais como linha de
`inscricoes`. O ramo continua no serviço (parâmetro `(turma_id, None)`) e é coberto chamando o
serviço direto — registrado como desvio no §8.

### P2 — caracterização (falhava antes)

`tests/test_a1_historico_legado_d2.py` (6 testes). Cenário: turma com **1 oferta ativa**,
inscrição na oferta e frequência **legada** (`turma_curso_id IS NULL`) 3 A + 1 F.

| Leitor | Antes | Depois |
|---|---|---|
| `agregar_por_oferta` (pauta/listagem) | 75,0% (4 aulas) | 75,0% (4 aulas) |
| `frequencias_aluno_por_inscricao` (histórico) | **0,0% (0 aulas)** | **75,0% (4 aulas)** |
| rota `/aluno/<id>/historico` | `0.0%` | `75.0%` |

### P3 — correção

Mesma consulta agregada única (sem N+1), agora com o helper de oferta única:

```python
oferta_ids = sorted({o for _, o in pares if o is not None})
unicas = ofertas_unicas_ativas(oferta_ids)          # 2 consultas em turma_curso
turmas_unicas = {t for t, o in pares if o in unicas}
turmas_legadas = {t for t, o in pares if o is None}
# 1 consulta em frequencia: linhas das ofertas + (D2) legado das turmas únicas
#                                    + legado das turmas de inscrição sem oferta
```

e, no bucketing, `conceitos.extend(contagens.get((turma_id, None), ()))` **somente** quando
`oferta_id in unicas`. Nenhuma regra duplicada: o critério é o mesmo `ofertas_unicas_ativas`
usado por `agregar_por_oferta` e `oferta_unica_com_legado`.

Ganho colateral: a função não carrega mais objetos ORM de `frequencia` (antes trazia todas as
linhas do aluno e descartava as colunas) — agora traz `turma_id`, `turma_curso_id`,
`conceito` e `COUNT`.

### P4 — testes

| Teste | Antes | Depois |
|---|---|---|
| `test_pauta_ja_aplica_d2_e_historico_nao` | falhava (0 aulas) | passa (4 aulas, 75,0%) |
| `test_rota_historico_mostra_o_mesmo_percentual_da_pauta` | falhava (`75.0%` ausente) | passa |
| `test_multi_oferta_legado_nao_entra_em_nenhuma` | — (já correto) | passa |
| `test_oferta_unica_inativa_nao_recebe_legado` | — (já correto) | passa |
| `test_par_legado_le_somente_linhas_null` | — (já correto) | passa |
| `test_consultas_constantes_por_inscricao` | — | passa (mesmo nº de SELECTs com 1 e 3 inscrições) |

**Testes existentes ajustados: nenhum.** Os dois candidatos continuam válidos:
`test_d3b2_3_n1_historico.py::test_equivalencia_batch_vs_antigo` usa a Turma Alfa com **2
ofertas** (a D2 não muda o resultado) e `::test_n1_historico_constante` conta apenas statements
em `frequencia` (continua **1**).

---

## 3. Item 2 — `I: None` no histórico

Local: o dicionário montado em `historico_aluno` (`app/registros/alunos.py`), não o template.
`c_inicial.situacao_final if c_inicial else "—"` devolvia `None` quando o conselho da etapa
**existia** e `situacao_final` estava NULL (lançamento aberto — é o estado que a semente do M1
cria). O template (`alunos/historico.html`) imprime `I: {{ h.status_inicial }}` e só esconde o
bloco quando o valor é exatamente `—`, então saía `I: None · P: —`.

Correção (os três status, porque o defeito é o mesmo):

```python
"status_inicial": ((c_inicial.situacao_final if c_inicial else None) or "—"),
"status_percurso": ((c_percurso.situacao_final if c_percurso else None) or "—"),
"situacao_final": ((c_final.situacao_final if c_final else None) or "—"),
```

`or` cobre `None` e string vazia. Teste de renderização:
`tests/test_a1_historico_status_ausente.py::test_status_ausente_imprime_travessao` — antes
`I: None` presente (falhava), depois o bloco `I/P` nem aparece (os dois lados são ausentes);
`test_d5_leitores.py` confirma que `I: Aprovado` continua sendo exibido quando há valor.

---

## 4. Item 3 — BI incluía turma excluída logicamente

### TRAVA (P1) — comparação dos critérios

| Leitor | Critério de "turma ativa" | Arquivo |
|---|---|---|
| Resumo (relatório geral) | `Turma.query.filter_by(ativo=True)` | `app/relatorios/geral.py` |
| `FRE-009` (`frequencia_por_turma`) | `Turma.ativo.is_(True)` | `bi_alunos.py` |
| `FRE-010` (`frequencia_por_curso`) | `Turma.ativo.is_(True)` | `bi_alunos.py` |
| Painel pedagógico (período) | `filter_by(periodo_letivo_id=..., ativo=True)` | `painel_pedagogico/periodo.py`, `turma.py`, `rota.py` |
| **`_base_frequencia`** | **nenhum** (só `Frequencia.unidade_id`; join em `Turma` só com período) | `bi_alunos.py` |
| **`_base_registro_aula`** | **nenhum** (join sem filtro `ativo`) | `bi_alunos.py` |

Os quatro "demais" **concordam entre si** (`Turma.ativo = True`) — TRAVA não acionada. A
divergência estava inteiramente nas duas bases do BI.

**Indicadores afetados** (todos que passam por `_base_frequencia`/`_base_registro_aula`):
`FRE-001` `total_lancamentos_frequencia`, `FRE-002` `total_presencas`, `FRE-003`
`total_faltas`, `FRE-004` `total_faltas_justificadas`, `FRE-005` `frequencia_media`,
`FRE-006/007/008` (faixas, via `_totais_por_aluno`), `CRU-001`
`frequencia_critica_por_vulnerabilidade` (também via `_totais_por_aluno`), `AUL-001`
`total_aulas_registradas`, `AUL-002/003/006/007/008` (`aulas_por_turma/periodo/unidade/tema/dia`).

### P2 — caracterização (falhava antes)

`tests/test_a1_bi_turma_ativa.py` (6 testes). Cenário com os **números reais do ensaio**
(conferidos por SQL no `pautaon_ensaio`, unidade 13): turma ativa **9 P + 6 F**, turma na
lixeira **2 P**, ambas com lançamentos preservados.

| Indicador | Antes | Depois | Conta |
|---|---|---|---|
| `frequencia_media` (`FRE-005`) | **64,7%** (11/17) | **60,0%** (9/15) | soma a turma `ativo=False` |
| `total_lancamentos_frequencia` | 17 | 15 | idem |
| `total_presencas` / `total_faltas` | 11 / 6 | 9 / 6 | idem |
| `alunos_frequencia_90` | 1 (100% da lixeira) | 0 | idem |
| `alunos_frequencia_inferior_75` | 1 | 1 | só o aluno da turma ativa (60%) |
| `total_aulas_registradas` (`AUL-001`) | 5 | 2 | 3 registros na turma excluída |
| `aulas_por_turma` | 2 turmas | 1 turma | idem |
| `frequencia_media(turma_id=<excluída>)` | 100,0% | 0,0% | filtro explícito também respeita `ativo` |

### P3 — correção

```python
query = Frequencia.query.join(Turma, Turma.id == Frequencia.turma_id) \
                       .filter(Turma.ativo.is_(True))
...
query = RegistroAula.query.join(Turma, Turma.id == RegistroAula.turma_id) \
                          .filter(Turma.ativo.is_(True))
```

O join em `Turma` passou a ser **um só** em `_base_frequencia` (o join condicional do período
saiu; o filtro virou `Turma.periodo_letivo_id`). Nenhuma outra regra mudou: legado pela D2
(`cond_linha_por_oferta`), `J` fora do percentual, escopo de unidade pela coluna de
`Frequencia`, curso/professor pela oferta.

### P4 — testes de BI que mudaram

**Nenhum.** `test_bi_oferta.py`, `test_bi_indicadores.py`, `test_bi_turma_desativada.py`,
`test_dashboard.py` e `test_painel_periodo.py` passaram **sem ajuste** (40 testes): os cenários
deles não têm turma `ativo=False` com lançamento — a lacuna era justamente essa. Como o limite
de "mais de 3 testes" não foi atingido (zero), não houve parada.

---

## 5. Item 4 — "Alunos enturmados 6" × "7 novos" (somente leitura)

**Onde nasce cada número** (template `relatorios/painel_pedagogico.html`, linha 129):

```jinja
{{ kpi_card('Alunos enturmados', vp.totais.alunos,
            extra='%d novos · %d renovados · %d retornantes' | format(...)) }}
```

- **6** = `vp.totais.alunos` → `_Acumulado.alunos` (`painel_pedagogico/periodo.py:56`),
  somado como `self.alunos += len(info.por_aluno)` de `frequencia.agregar_por_turma(turmas_ids)`.
  `por_aluno` é montado **a partir das linhas de `frequencia`**: aluno sem nenhum lançamento
  **não existe** nesse mapa. É, na prática, "alunos na pauta", não "alunos enturmados".
- **7** = `vp.totais.novos` → `status_alunos_para_bi` (`app/services/aluno_status.py`),
  que classifica como `NOVO` quem tem **inscrição ativa + turma ativa + oferta efetiva** e
  nenhum histórico anterior. Essa é a definição canônica de enturmado
  (`contar_alunos_enturmados`, `app/services/enturmado.py`), a mesma usada por
  `PeriodoLetivo.alunos_enturmados()`, `gerenciar` e o próprio BI.

**Por que diferem na semente:** as turmas ativas têm 7 alunos enturmados (A: 2, B: 2, C: 3) e
**6** deles têm lançamento. A diferença é **1 aluno transferido** para a Turma C
(`Gabriela Transf`) que **nunca recebeu frequência** — não é o desenturmado (`Heitor`, inscrição
inativa, fora dos dois números) nem o aluno da turma na lixeira (`Inacia`, turma `ativo=False`,
excluída dos dois). Ou seja, a diferença é **esperada para os dados**, mas o **rótulo é
errado**: é impossível "6 enturmados" terem "7 novos" como subconjunto.

**Proposta (não implementada):**
1. trocar o big number pela contagem canônica — `len(enturmados_ids)` restrito às turmas do
   período ou `contar_alunos_enturmados(periodo_letivo_id=...)`;
2. se o número da pauta for útil, expô-lo **à parte** ("alunos com frequência lançada"), sem
   chamá-lo de enturmado;
3. teste novo: aluno enturmado sem lançamento conta no KPI (antes 6, depois 7).
Não mexer na visão por período (que de propósito omite turma sem frequência, §12.21).

---

## 6. Item 5 — filtro *Programa* e a projeção `Turma.programa` (somente leitura)

**Onde o filtro usa a projeção:**

| Ponto | Código | Observação |
|---|---|---|
| Listagem `/turma` | `aplicar_filtros_turmas` (`app/registros/turmas.py:588-590`) — `stmt.where(Turma.programa == programa)` | professor, turno e **centro de custo** já usam `_filtro_por_oferta`; programa não |
| Painel do professor | `app/registros/core.py:154-155` — `stmt.where(Turma.programa == programa_selecionado)` | opções do select vêm de `select(Turma.programa).distinct()`, também projeção |
| Coluna exibida / conselho / painel pedagógico | `turma.programa`, `oferta.programa or turma.programa` | exibição — não é filtro |
| Impressão de centros de custo | `/turmas/centros-custo/imprimir` usa os **mesmos** filtros da listagem | herda o comportamento |

`Turma.programa` é a projeção da **oferta principal ativa** (MER §8.10). Uma turma com 2+
ofertas de programas diferentes (semente: Turma B, *Esporte* principal + *Meio Ambiente*) fica
invisível no filtro do programa da oferta secundária.

**Proposta (não implementada):** usar o helper que o resto da listagem já usa —

```python
stmt = stmt.where(
    _filtro_por_oferta(
        func.coalesce(TurmaCurso.programa, Turma.programa) == programa,
        Turma.programa == programa,
    )
)
```

`_filtro_por_oferta` é `EXISTS` em oferta ativa (sem duplicar linhas da turma) com fallback à
coluna congelada apenas quando a turma **não tem oferta ativa** — exatamente a semântica de
`professor` e `turno`.

**Impactos:**
- **Opções do select:** não mudam. São hardcoded em `turmas/listar.html` (Profissionalizante,
  Esporte, Meio Ambiente, Outros) — nenhuma opção nova aparece, então turma com programa fora
  dessa lista continua não filtrável (dívida separada: `ofertas.html` também tem lista embutida,
  MER §12.14).
- **Contagens:** a turma multi-programa passa a aparecer em **cada** programa que qualquer
  oferta ativa declare (antes: só no da principal). Na semente, `?programa=Meio Ambiente` sai de
  0 para 1 turma. Nenhuma turma é duplicada no resultado (`EXISTS`, não join).
- **Impressão de centros de custo:** herda o mesmo filtro — a turma passa a aparecer no grupo de
  centro quando o programa casar por oferta; a hierarquia centro → turma → ofertas não muda.
- **Exibição:** a coluna continua mostrando `Turma.programa` (projeção/principal); se o filtro
  for por programa secundário, a linha aparecerá com o programa da principal — vale um texto de
  apoio ("filtra qualquer oferta ativa") para não confundir.
- **Testes que mudariam:** `tests/test_filtros_turmas.py::test_filtra_por_programa` (hoje fixa
  o comportamento por `Turma.programa`) + um caso novo "2 ofertas, programas diferentes" (casa
  nos dois). Nenhum teste de impressão cobre programa hoje.

---

## 7. Validação final

**No banco de ensaio (`pautaon_ensaio`, unidade 13, leitura via app factory):**

| Leitura | Antes (M1) | Depois |
|---|---|---|
| `FRE-005` `frequencia_media` | 64,7% | **60,0%** |
| `FRE-009` por turma | A 75,0 · B 50,0 · C 66,7 | A 75,0 · B 50,0 · C 66,7 (sem a Turma D) |
| `AUL-001` `total_aulas_registradas` | 5 | **4** |
| histórico da Ana (Turma A, oferta 44, legado NULL) | 0,0% (0 aulas) | **100,0% (2 aulas)** |
| histórico da Carla (Turma B, ofertas 45 e 46) | 66,7% / 0,0% | 66,7% / 0,0% (legado não entra: 2 ofertas) |

| Verificação | Resultado |
|---|---|
| Suíte completa | **735 passed**, 0 falhas (722 + 13 novos) em 157 s |
| Novos testes | `test_a1_historico_legado_d2.py` (6), `test_a1_historico_status_ausente.py` (1), `test_a1_bi_turma_ativa.py` (6) |
| Testes existentes ajustados | **0** |
| `ruff check --select F821,F811` (arquivos alterados) | *All checks passed* |
| `ruff check` nos arquivos novos | limpo (os 3 testes com `# ruff: noqa: F811`, padrão dos testes que reexportam fixtures) |
| `git diff --check` | limpo |
| Migration | nenhuma (head `8d2e3f4a5b6c`) |
| Push | não |

---

## 8. Desvios e observações

1. **Working tree mudou antes do início:** as mudanças em `app/templates` citadas no P0 já
   estavam no commit `e422ff0` (do dono da máquina), não no working tree. `git diff --stat`
   e `git diff -w --stat` foram medidos contra `e422ff0~1` — ver §1.
2. **Número do achado 3:** a tarefa descreve "turma ativa 9P/6F + turma excluída 11P/6F →
   64,7%". No ensaio, **11P/6F já é o total** (turmas ativas 9P/6F + turma na lixeira 2P) e
   **64,7% = 11/17**; a turma excluída tem 2 presenças, não 11. O teste reproduz o fenômeno com
   os números reais (64,7 → 60,0). A "turma excluída 11P/6F" da descrição daria 20/32 = 62,5%,
   que não é o valor observado no app.
3. **Inscrição legada sem oferta não existe mais** (NOT NULL desde `c3d4e5f6a7b8`): o ramo
   `(turma_id, None)` do serviço é coberto por chamada direta, não pela rota. A documentação do
   serviço foi atualizada para dizer isso.
4. **Ruff pré-existente:** `app/services/frequencia_oferta.py` (I001 no bloco de imports, E741
   em `l`) e `app/registros/alunos.py` (I001 nos imports) já falhavam no ruff **antes** desta
   tarefa — mantidos como estavam, porque alterar `app/` fora dos itens 1–3 era proibido. Os
   arquivos alterados passam em `F821,F811`.
5. **Itens 4 e 5** ficaram registrados em `backlog_desenvolvimento.md` → *Pendências abertas*
   com a proposta completa, sem tocar em código.
6. **Deleção externa detectada no fechamento:** `docs/erros MD/Erro.md` (rastreado desde
   `00244ae`) foi **apagado do disco** durante a execução, por processo externo — o diretório
   está vazio e o `git status` passou a mostrar `D "docs/erros MD/Erro.md"`. Não foi esta
   tarefa: não foi restaurado nem commitado, e fica para o dono da máquina decidir (`git
   restore` para manter, ou incluir na próxima limpeza). O primeiro `git status` da sessão não
   mostrava essa deleção.
