# ETAPA B6 — Limpeza pós-Onda 4 (relatório)

Escopo: isolamentos de escrita no planejamento, D3 (turma sem período na
listagem), R2 (contexto órfão em nova_turma) e remoção do código morto de
**inscrições** introduzido pelo `NOT NULL` de `Inscricao.turma_curso_id`
(migration da Onda 4 `c3d4e5f6a7b8`). Nada de Frequencia/RegistroAula foi
tocado — esses `turma_curso_id IS NULL` seguem válidos (coluna nullable).

Base da suíte na entrada: **257 passed**. Saída: **262 passed, 0 falhas**
(5 testes novos). Nenhum commit feito.

---

## Passo 1 — Leitura e classificação (arquivo:linha na entrada)

### (a) Isolamento em `app/registros/core.py`
- Criação de nível (POST `/planejamento`, ramo `tipo_post == 'nivel'`) em
  L733-758: construía `Nivel(unidade_id=nivel_unidade_id)` **sem**
  `assert_unidade_context`. Como `nivel_unidade_id = get_unidade_id()`, um
  ADMIN em Visão Global (sessão sem unidade) gravava nível com
  `unidade_id = NULL`.
- `editar_tema` L885-898 e `inativar_tema` L930-943: a checagem
  `if curso and not curso.ativo:` (flash + redirect 302) vinha **antes** do
  `assert_unidade_context`. Um tema de curso **inativo de outra unidade**
  devolvia 302 (revelando a existência do curso) em vez de 403.
- O ramo "novo tema" (L762-802) já tinha `assert_unidade_context` (L767)
  **antes** de `curso.ativo` (L768) — ordem correta, preservada.
- `editar_nivel`/`inativar_nivel`: já corretos, não alterados.
- `assert_unidade_context` (`app/registros/shared.py` L27-39): `abort(403)`
  se `obj_unidade_id is None` **ou** `unidade_id is None` **ou** mismatch.

### (b) Listagem de turmas (`app/registros/turmas.py`)
- `aplicar_filtros_turmas` L213-327: ramo `ano_periodo` (L236-245) usava
  `Turma.periodo_letivo_id.in_(subquery)`, que **exclui NULL**.
- Rota `turma()` L402-407: quando nem período nem ano eram escolhidos,
  injetava `filtros["ano_periodo"] = str(ano_atual)` → a vista padrão ocultava
  turmas com `periodo_letivo_id NULL`.

### (c) `programas=` no render de nova_turma
- `_PROGRAMAS_OFERTA` L170. `nova_turma()` (def L713) montava
  `programas = list(_PROGRAMAS_OFERTA)` e passava `programas=programas` no
  `render_template('turmas/nova_turma.html', ...)` (entrada: L896/L903).
- `editar_turma()` ainda usa `_PROGRAMAS_OFERTA` (constante L170; render
  `turmas/editar.html` com `programas=programas`) → **manter a constante**.
- `app/templates/turmas/nova_turma.html` (89 linhas): **não** referencia
  `programas` (grep 0 ocorrências) → remoção do contexto é segura.

### (d) Ramo NULL de inscrição
- `cond_inscricao_enturmada` (`app/relatorios/bi_filtros.py` L16-72):
  retornava `or_(oferta_apontada_ativa, and_(Inscricao.turma_curso_id.is_(None),
  oferta_unicica == 1))`. `oferta_unicica` usava `func.count`. Imports
  `and_, func, or_, select` (L11). `func`/`or_` só usados nesse ramo.
- `_alunos_da_oferta` (`app/services/turma_curso.py` L595-646): parâmetro
  `incluir_inscricoes_null` (L599) com ramo `or_(== oferta, IS NULL)`
  (L623-631). `or_` (import L30) usado noutros locais → manter import.
- **Todos os chamadores de `_alunos_da_oferta`**:
  - `core.py` L277-280 (POST, `incluir_null = len(ativas_post) == 1`) e
    L382-383 (GET, `incluir_inscricoes_null=(len(ofertas) == 1)`).
  - `turmas.py` L2095-2096 (`incluir_inscricoes_null=False`).
  - `dashboard_professor.py` **4** sítios: L79-81, L164-165, L218-219,
    L289-290 (dois com `incluir_null = len(ativas_turma) <= 1`).
  - `app/utils/frequencia.py` L168-169 (`incluir_inscricoes_null=False`).
  - Testes: `test_enturmacao_oferta.py` L389-390;
    `test_turma_curso_fase4.py` L104-105.

### (e) Classificação das leituras `turma_curso_id IS NULL`
- **Inscrição (MORTO):** `cond_inscricao_enturmada` (ramo NULL) e
  `_alunos_da_oferta` (`incluir_inscricoes_null`). `Inscricao.turma_curso_id`
  é `nullable=False` (`app/models/matriculas.py` L59-61) → estado inalcançável.
- **Frequencia/RegistroAula (VÁLIDO — NÃO tocar):**
  `app/utils/logica.py` L402-410 usa `filter_by(..., turma_curso_id=None)` no
  ramo legado; `Frequencia.turma_curso_id` é `nullable=True`
  (`app/models/aulas.py` L81-84, "NULL = registro legado"). Correto.
- **Fora do escopo do Passo 5 (NÃO removido, anotado):**
  `_contagem_inscricoes_sem_curso` (`core.py` L187-201) conta `Inscricao` com
  `turma_curso_id NULL` → morto desde o NOT NULL, mas o Passo 5 delimita a
  remoção a `cond_inscricao_enturmada` + `incluir_inscricoes_null` (e
  chamadores). Mantido intacto; registrado em "Pendências".

---

## Passo 2 — Isolamento (core.py)

**2a — criar nível exige unidade efetiva.** Inserido
`assert_unidade_context(nivel_unidade_id, nivel_unidade_id)` logo após
`nivel_unidade_id = get_unidade_id()` no ramo `tipo_post == 'nivel'`. Como
`assert_unidade_context` aborta 403 quando o id é `None`, a Visão Global passa
a recusar a criação (igual aos demais ramos de escrita).

**2b — ordem assert × curso.ativo.** Em `editar_tema` e `inativar_tema`, o
`assert_unidade_context(...)` foi movido para **antes** de
`if curso and not curso.ativo:`. Agora um tema de curso inativo de outra unidade
devolve **403**; na mesma unidade, o curso inativo ainda produz o redirect 302
com flash (comportamento legítimo preservado). Comentários `ETAPA B6`
acima de cada assert.

## Passo 3 — D3 (listagem inclui turma sem período na vista padrão)

- `aplicar_filtros_turmas(stmt, args, incluir_turmas_sem_periodo=False)`: novo
  parâ opcional. No ramo `ano_periodo`, quando a flag é `True`, a condição
  passa a `or_(por_ano, Turma.periodo_letivo_id.is_(None))` — a turma sem
  vínculo não é ocultada pelo ano vigente injetado. Docstring atualizada.
- Rota `turma()`: calcula `vista_padrao = not periodo_selecionado and not
  _parse_int_arg(filtros.get("ano_periodo"))` **antes** da injeção do ano e
  repassa `incluir_turmas_sem_periodo=vista_padrao`. Quando o usuário escolhe
  período/ano explicitamente, `vista_padrao` é `False` → filtro **estrito**.
- O chamador do relatório (`imprimir_centros_custo_turmas`, L610) mantém o
  padrão `False` (filtro estrito) — não é a "listagem padrão".
- Isolamento por unidade inalterado (`stmt_base.where(unidade_id)`).
- Template `app/templates/turmas/listar.html`: selo
  `Sem período` (`badge bg-secondary`) na célula do nome quando
  `turma.periodo_letivo_id is none`.

## Passo 4 — R2 (nova_turma sem `programas`)

- Removidos `programas = list(_PROGRAMAS_OFERTA)` e o kwarg
  `programas=programas` do `render_template('turmas/nova_turma.html', ...)`.
- Substituído por comentário `ETAPA B6 (R2)` explicando que o programa é
  projeção da oferta principal e que o template não consome `programas`.
- `_PROGRAMAS_OFERTA` (L170) **mantida** — `editar_turma` ainda a usa
  (`programas=programas` no render de `turmas/editar.html`).

## Passo 5 — Código morto SOMENTE de inscrições

- `bi_filtros.cond_inscricao_enturmada`: removido o bloco `oferta_unicica` e o
  `or_(..., and_(Inscricao.turma_curso_id.is_(None), ...))`. Retorno agora
  `and_(Inscricao.ativo.is_(True), turma_ativa, oferta_apontada_ativa)`.
  Imports reduzidos de `and_, func, or_, select` → `and_, select`
  (`func`/`or_` ficaram sem uso no ficheiro). Docstring atualizada com a nota
  do NOT NULL (`c3d4e5f6a7b8`).
- `services.turma_curso._alunos_da_oferta`: removido o parâmetro
  `incluir_inscricoes_null` e o `if/or_`. Filtro fixo
  `Inscricao.turma_curso_id == oferta_id`. Docstring atualizada. Import `or_`
  mantido (usado noutros locais do ficheiro).
- **Todos os chamadores atualizados** (kwarg/variável removidos):
  `core.py` (POST e GET), `turmas.py` (ver_turma),
  `dashboard_professor.py` (4 sítios; as linhas órfãs
  `ativas_turma = ofertas_ativas(...)`/`incluir_null = ...` removidas onde só
  existiam para o kwarg — `ofertas_ativas` segue importado e usado em
  L73/L183), `app/utils/frequencia.py` (1 sítio),
  `tests/test_enturmacao_oferta.py` (2), `tests/test_turma_curso_fase4.py` (1).
- **Nada** relativo a Frequencia/RegistroAula alterado (`logica.py` intocado).

### Ampliação de escopo (autorizada pelo responsável)
O enunciado B6 autorizava SOMENTE `core.py`, `turmas.py`, `bi_filtros.py`,
`services/turma_curso.py`, o template da listagem e `tests/`. Mas o Passo 5
mandava remover o parâmetro "**e seus chamadores**", e havia chamadores em
`app/main/dashboard_professor.py` (4) e `app/utils/frequencia.py` (1) — a
remoção do parâmetro os quebraria com `TypeError`. Foi apresentada a
inconsistência; o responsável **autorizou ampliar o escopo** para atualizar os
call-sites e remover o parâmetro por completo (opção "fidelidade total ao
Passo 5"). As edições nesses dois ficheiros foram **estritamente mecânicas**
(apenas remover o kwarg e as linhas que só existiam para alimentá-lo).

## Passo 6 — Testes

### Novos
- `test_isolamento_unidade_escrita.py`
  - `test_admin_sem_unidade_nao_cria_nivel` — Visão Global + POST nivel → **403**
    e nenhum `Nivel` gravado (Passo 2a).
  - `test_admin_nao_edita_tema_de_curso_inativo_de_outra_unidade` — curso
    inativo de outra unidade → **403** (não 302) (Passo 2b).
  - `test_curso_inativo_da_propria_unidade_ainda_redireciona` — mesmo curso
    inativo na própria unidade → **302** preservado (Passo 2b, sem regressão).
- `test_turma_curso_lista.py` (novo seed `_seed_d3` ancorado no ano corrente)
  - `test_turma_sem_periodo_aparece_na_vista_padrao_com_selo` — vista padrão
    mostra a turma sem período (via `_linha`) com selo "Sem período".
  - `test_turma_sem_periodo_some_quando_periodo_escolhido` — `?periodo_letivo_id=`
    → só a turma com período; selo ausente (filtro estrito).

Um usuário por teste em todos (regra T1 §5.6).

### Ajustado (conflito por finalidade — Pare-e-relate)
`test_filtros_turmas.py::test_rota_listagem_sem_periodo_no_ano_corrente_nao_quebra`
asseria (`assert not _linha`) que a turma sem período **não** aparece na vista
padrão — exatamente o comportamento que o D3 inverte por requisito. O teste foi
PARADO e reportado; o responsável orientou: **manter** as asserções de `200`
(guarda anti-P2/KeyError) e de `ano_periodo=<ano>` no HTML, **inverter** apenas
a de ausência (turma aparece na vista padrão com selo), **renomear** para
`test_listagem_padrao_inclui_turma_sem_periodo_e_nao_quebra_sem_periodo_no_ano`
e comentar o seed ("turma sem período é estado legado; criação exige período —
turmas.py:719"). O caso inverso (escolher período → estrito → some) ficou
coberto em `test_turma_curso_lista.py::test_turma_sem_periodo_some_quando_periodo_escolhido`
(referenciado no docstring).

---

## Validação

- `py_compile` em todos os ficheiros alterados: OK.
- Arquivos afetados isolados: 86 passed.
- **Suíte completa: `262 passed, 51 warnings in ~34s`** (0 falhas). As
  warnings são preexistentes (LegacyAPIWarning `Query.get()`,
  `datetime.utcnow()`), alheias a esta etapa.
- Contagem: base 257 + 5 novos = 262.

## Decisões
- `dashboard_professor.py` e `frequencia.py`: edição mínima autorizada para
  honrar "remover parâmetro e seus chamadores" sem quebrar runtime.
- D3 implementado via flag opcional (`incluir_turmas_sem_periodo`) para não
  alterar a semântica do chamador do relatório de centros de custo.
- Selo "Sem período" ancorado em `turma.periodo_letivo_id is none` (não em
  string de nome), estável à localização.

## Pendências (fora do escopo B6 — registradas, não alteradas)
- `_contagem_inscricoes_sem_curso` (`core.py` L187-201) e o contador de aviso
  "sem curso definido" na tela — código morto de inscrição desde o NOT NULL,
  mas fora do Passo 5. Candidato a uma etapa de limpeza seguinte.
- `logica.py` L402-410 e o legado `Frequencia/RegistroAula.turma_curso_id IS
  NULL`: **corretos**, mantidos (coluna ainda é nullable).
- `app/templates/turmas/ofertas.html` continua com a lista de programas
  embutida (dívida D6 do B1), não tocada.
- Comentários de rodapé em `test_enturmacao_oferta.py` (L417-420) e notas em
  `MER.md §974`/relatórios históricos (T1/V1) ainda descrevem o fallback NULL
  removido; docs não foram alterados (exceto este relatório), conforme o
  escopo.
