# I1 — regra por oferta nos guardas restantes + higiene (29/10/2026)

Rodada com **P0 bloqueante**: o pré-requisito G1/P2 (toda oferta ativa com professor +
trava) **não está aplicado**, então a **T1 não foi implementada**. Entrega: inventário
T0 (somente leitura, itens a–e) e a higiene T2. **Sem migration, sem push, banco
principal intocado** (apenas `SELECT`).

| Etapa | Estado | Registro |
|---|---|---|
| P0 — pré-requisito G1/P2 | **FALHOU** → T1 parada (decisão do usuário: entregar T0 + T2) | §2 |
| T0 — verificação a–e | Concluída (só leitura) | §3 |
| T1 — migrar guardas para a oferta | **Não implementada** — nada migrado | §4 |
| T2 — higiene (2 F401 + 9 F841) | Concluída | commit `72e9d40` |
| Suíte | 1006 passed → **1006 passed**, 0 failed | §5 |

---

## 1. Pergunta objetiva: "e se trocar o professor no meio do curso?"

Resumo cru, com os pontos §3a–c detalhados adiante:

- **Pode trocar?** Sim, por duas rotas independentes, **sem qualquer confirmação** sobre
  os lançamentos já feitos e **sem exigir professor** (é possível deixar a oferta vazia).
- **Quem lançou fica registrado?** Em parte, e mal. A **pauta de frequência não guarda
  autor nenhum** (nenhuma coluna de autoria em `frequencia`). O **Diário** (`registro_aula`)
  guarda `instrutor_id`, mas a gravação **sobrescreve** o campo a cada salvamento — o autor
  anterior desaparece. `updated_by_id` (AuditoriaMixin) também é sempre "o último".
- **Tem auditoria da troca?** Tem linha em `log_acao` (`Alterar TurmaCurso`), mas o
  `detalhes` é `repr(obj)` → `'<TurmaCurso 14>'`. **Não há registro do valor anterior**:
  não é possível reconstruir quem era o professor antes da troca.
- **E o conselho?** Ainda mais fraco: a linha de `conselho_classe` nasce **sem instrutor**
  no lançamento normal (`app/conselho.py:766-772`) e `conselho_resposta` não tem autor nem
  oferta — só `updated_by_id` (o último editor) sobrevive.
- **Efeito prático da troca no meio do curso:** o novo professor passa a ser dono dos
  lançamentos futuros **e** reinvindica os dias já lançados no Diário (o `instrutor_id`
  é reescrito quando ele salva aquele dia); o antigo perde a escrita e, nos pontos já
  migrados para a oferta (pauta impressa, I1), também a leitura. Histórico de frequência
  não tem como ser atribuído a ninguém.

---

## 2. P0 — pré-requisito G1/P2: **não aplicado** (motivo da parada)

| Checagem | Resultado |
|---|---|
| Toda oferta ativa tem professor? | **Não.** 6 ofertas ativas, **4 sem professor**: 16 e 17 (turma 12 "Turma Alfa"), 18 (turma 13 "Turma Gema"), 19 (turma 14 "Turma Zeta") — período "Periodo Freq", `data_fim = 30/06/2026`. No ensaio, a oferta 50. |
| As turmas têm professor para copiar? | **Não.** `scripts/saneamento_professor_oferta.py` (dry-run): *copiáveis da turma: 0; pendentes de decisão: 4*. |
| Trava no serviço? | **Não.** `_validar_professor` (`app/services/turma_curso.py:402-414`) faz `if not professor_id: return None` — vazio aceito silenciosamente; `editar_oferta` (`:651`) e `adicionar_oferta` (`:538`, herdando de `turma.professor_id` em `:594`) mantêm o caminho livre. |
| Trava no formulário? | **Não.** `-- Sem professor --` continua opção e não há `required`: `turmas/ofertas.html:112` (edição) e `:238` (criação); `turmas/editar.html:174`. |
| NOT NULL no banco? | **Não.** `turma_curso.professor_id` com `is_nullable = YES` (consultado no principal, head Alembic `e1f2a3b4c5d6`); nenhuma migration depois de `311d554dfd6e` apertou a coluna. |

**Por que isso trava a T1.** A regra por oferta é **sem herança**
(`app/services/aluno_info_professor.py:60-79`): `condicao_professor_da_oferta` compara
somente com `turma_curso.professor_id`, e `professor_da_oferta` devolve `False` quando a
oferta não tem professor ("oferta sem professor não libera nada"). Migrar `ver_turma`,
`ver_observacoes` e `/frequencia` agora **retiraria o acesso** dos professores que hoje
entram por `turma.professor_id` nessas 4 ofertas sem professor — perda de funcionalidade
sem contrapartida. **Nenhuma linha de código de aplicação foi alterada nesta rodada.**

---

## 3. T0 — verificação (somente leitura)

### a) A rota/form de edição da oferta permite TROCAR o professor? Permite deixar vazio?

Trocar: **sim, por dois caminhos.** Deixar vazio: **sim** (não deveria).

1. **`POST /turma/oferta/<oferta_id>/editar`** (`app/registros/turmas.py:2194-2225`) →
   `_dados_oferta_form` (`:2043-2052`) monta `professor_id = _parse_int_arg(form.get("professor_id"))`,
   que vale `None` quando o formulário traz a opção vazia → `editar_oferta` →
   `_validar_professor` aceita `None`.
2. **`POST /turma/<id>/editar`** (edição da turma) → `turma_obj.professor_id = novo_professor_raw`
   (`:1844`) e, havendo **1 oferta ativa**, o espelho `oferta_única.professor_id = turma_obj.professor_id`
   (`:1945`) propaga inclusive o `NULL` para a oferta.

Comportamentos adjacentes que interessam à decisão:

- **Com 2+ ofertas ativas** a tela da turma **ignora** os campos de oferta no servidor e
  apenas avisa ("Os dados de curso, professor, turno… são editados em Cursos da Turma",
  `:1755-1777`); a troca acontece só no caminho 1.
- **Nenhuma confirmação ao trocar professor com lançamentos existentes.** O bloco que exige
  confirmação para limpar lançamentos (`:1819-1835`) olha **só** `mudou_agenda`,
  `data_inicio` e `data_fim` — professor não está na conta.
- Nenhum teste caracteriza "troca de professor da oferta com frequência já lançada"; o
  único contrato testado é o de **acesso** (`test_pauta_impressa_por_oferta.py`, oferta sem
  professor → 403 para perfil professor).

### b) Quais tabelas com `turma_curso_id` guardam o autor do lançamento?

Varredura da metadados (5 tabelas com `turma_curso_id`):

| Tabela | Coluna de autoria | O que vale na prática |
|---|---|---|
| `frequencia` | **nenhuma** (cols: `id, aluno_id, turma_id, turma_curso_id, data, conceito, valor_esportista_id, unidade_id`) | o lançamento da pauta **não tem autor** |
| `registro_aula` | `instrutor_id` + `updated_by_id`/`updated_by_name` | **`instrutor_id` é sobrescrito a cada gravação** (`app/utils/logica.py:744`, no ramo "registro já existe"; `:753` na criação) → fica o último que salvou o dia |
| `conselho_classe` | `instrutor_id` + mixin | `instrutor_id` **só** no caminho do fechamento final (`app/conselho.py:957-965`); o lançamento normal cria a linha **sem** instrutor (`:766-772`) e nunca o reescreve → sobra `updated_by_id` (o último que salvou) |
| `inscricoes` | `updated_by_id`/`updated_by_name` | registra apenas "quem mexeu por último" na matrícula |
| `turma_curso_horario` | **nenhuma** | grade sem autoria |

Fora do grupo (não tem `turma_curso_id`): **`conselho_resposta`** usa só `TenantMixin` —
**sem `turma_curso_id` e sem coluna de autoria**. A resposta individual do conselho não
permite dizer quem a digitou, nem a qual oferta pertence (só por junção com
`conselho_classe`).

**Perda de autoria reportada:** na troca de professor no meio do curso, não há como
distinguir o que o anterior lançou do que o novo lançou na **pauta** (nunca houve autor) e,
no **Diário**, o dia já lançado muda de dono na primeira reescrita. É a resposta objetiva
ao item 4 da T1: **ausência de autoria** + **auditoria sem valor anterior** → não
implementar migração de guarda de escrita sem decisão da instituição.

### c) A troca de professor gera `log_acao`?

**Sim, mas sem conteúdo útil.**

- `TurmaCurso` e `Turma` herdam `AuditoriaMixin`; o listener `before_flush`
  (`app/models/auditoria_listener.py:44-75`) preenche `updated_by_*` e insere
  `LogAcao(usuario_*, acao="Alterar TurmaCurso", detalhes=repr(obj), ip, unidade_id)`.
- Evidência no banco principal (SELECT): **32** linhas `Alterar TurmaCurso`, **16** `Criar
  TurmaCurso`, **51** `Alterar Turma`.
- Amostra real (29/10/2026 14:33, por "Afonso Magno"): `detalhes = '<TurmaCurso 14>'`.
- `log_acao` tem apenas `id, data_hora, usuario_id, usuario_nome, acao, detalhes, ip,
  unidade_id` — **sem campo de entidade/atributo/valor anterior**. Conclusão: sabe-se *que
  alguém alterou a oferta 14*, não sabe-se *o que* mudou nem *quem era o professor antes*.

### d) Texto exato do I1 e a "decisão da instituição" (medicação na pauta)

Texto literal do backlog (`backlog_desenvolvimento.md:266`):

> **I1 — DECISÃO PENDENTE COM A INSTITUIÇÃO (medicação na pauta, 28/10/2026):** "Medicação
> regular" informada como "sim" é impressa na pauta para **qualquer** professor com acesso
> à pauta da turma (inclusive de períodos encerrados, via URL). Verificar se há necessidade
> de expor a medicação ao professor da oferta — nem toda medicação precisa ser conhecida por
> ele. Se não houver, retirar da pauta; se houver só em parte, a secretaria informa o
> necessário no campo "Informações para o professor da turma", que está sob a regra de
> acesso do I1. **Nada muda no comportamento da medicação enquanto a decisão não for
> tomada.**

Leitura para a T1.2: a decisão é **de conteúdo** (o que a pauta impressa/modal exibe sobre o
aluno), **não de competência** (quem pode abrir a pauta ou lançar). O I1 já está sob a regra
por oferta (`aluno_info_professor.py:60-79`, endpoint `/aluno/<id>/info-professor`) e a
medicação **não passa** pela regra do I1 (backlog `:112` e `:114`). Portanto, **em princípio
o `/frequencia` (GET e POST) não depende dessa decisão** — ele está parado pelo **P0**, não
pela medicação.

Apontamento de documentação: a linha `:111` do backlog ainda descreve a regra do I1 com
`coalesce(turma_curso.professor_id, turma.professor_id)`; a PARTE B do mesmo dia (`:100`,
`:104`) e o MER §8.12 fixaram a regra **somente** em `turma_curso.professor_id`, **sem
herança**. O código atual é o segundo. Inconsistência a corrigir na documentação (não
alterada aqui por ser entrada histórica de "alterações do dia").

### e) Inventário de `Turma.professor_id` como regra de ACESSO

**Guardas por turma (o que a T1 migraria):**

| Arquivo:linha | Rota / função | Efeito hoje |
|---|---|---|
| `app/registros/turmas.py:1374-1378` | `GET /turma/<id>` (`ver_turma`, detalhe da turma) | `abort(403)` se `turma.professor_id != current_user.id` |
| `app/registros/turmas.py:2640-2644` | `GET /turma/<id>/observacoes` (`ver_observacoes`, **Diário de Bordo**) | `abort(403)` pelo mesmo critério |
| `app/registros/core.py:256-259` | `POST /frequencia` (gravação da pauta) | `abort(403)` se o professor não é o **da turma** |
| `app/registros/core.py:382-399` | `GET /frequencia` | monta o `<select>` de turmas só com `Turma.professor_id == usuário` e, se `turma_id` fora da lista, redireciona com flash ("Você não tem permissão…") |
| `app/registros/alunos.py:881-893` | `historico_aluno` | `abort(403)` se nenhuma inscrição ativa em turma com `Turma.professor_id == usuário` |
| `app/registros/alunos.py:1316-1327` | `/aluno/<id>/foto` | `abort(403)` pelo mesmo critério |

**Já estão sob a regra da oferta** (nada a migrar):

- pauta impressa: `imprimir_pauta` (`app/registros/turmas.py:2685`; regra documentada em
  `:2708-2716` e guarda `professor_da_oferta` em `:2720-2726`);
- I1: `app/services/aluno_info_professor.py:60-79`;
- painel do professor: `app/main/dashboard_professor.py:168` (`TurmaCurso.professor_id`),
  com lista de turmas legadas em `:200`;
- conselho: `app/conselho.py:526` (`TurmaCurso.professor_id`), com `_escopo_professor`
  (`:91-99`) e `_guarda_oferta_explicita_do_professor` (`:100-112`, que usa
  `professor_da_oferta` e dá 403 na oferta ativa de outro professor).

**Não são regra de acesso** (filtro, contagem ou espelho de escrita — fora da T1):

- filtros de listagem/dropdown com COALESCE: `app/registros/turmas.py:562-573`,
  `:2447-2599`; `app/relatorios/bi_alunos.py` (`:1536`, `:1573`, `:1612`, `:1666`, `:1728`,
  `:1792`, `:1838`, `:1854`, `:2764`); `app/relatorios/observacoes.py:133`;
  `app/conselho.py:292`; contagem em `app/main/dashboard_admin.py:34`;
- escrita/projeção turma ↔ oferta: `app/services/turma_curso.py:444` (espelho oferta→turma),
  `:521` e `:594` (herança na criação da oferta), `app/registros/turmas.py:1844` e `:1945`.

**Nenhum template usa `Turma.professor_id` como condição de visibilidade** — os únicos
usos de `professor_id` em templates são campos de formulário (`turmas/editar.html:171-176`,
`turmas/ofertas.html:111-118` e `:236-244`) e selects de filtro
(`turmas/carga_horaria_curso.html:135-138`, `turmas/observacoes.html:44`).

**Links do detalhe da turma (contexto da T1.1).** `app/templates/turmas/detalhe.html`
mostra o dropdown "Imprimir Pauta" (`:35-70`) e o botão **Diário de Bordo** (`:71-73`) para
quem abre a página — hoje **nenhum link leva a 403**, porque `ver_turma` e os alvos usam o
mesmo critério (`turma.professor_id`). Se `ver_turma` fosse migrado sozinho, o professor da
oferta abriria o detalhe de uma turma cujo Diário ele não pode ver → **link para 403**. Daí
a ordem conservadora da T1 (migrar os três juntos e listar links por oferta).

---

## 4. T1 — **não implementada**

- **Migrado:** nada. **Continua em `Turma.professor_id`:** as seis guardas da tabela do §3e
  (`ver_turma`, `ver_observacoes`, `POST /frequencia`, `GET /frequencia`, `historico_aluno`,
  `/aluno/<id>/foto`) e os links do `detalhe.html`.
- **Efeito que a migração teria** (registrado para quando o P0 for resolvido): professor da
  oferta que não é o professor da turma **ganha** acesso ao Diário/pauta/detalhe; professor
  da turma **sem oferta ativa onde leciona perde** o acesso (inclusive nas 4 ofertas sem
  professor do banco principal).
- **Trava adicional (item 4 da tarefa):** os itens T0-b e T0-c confirmam **ausência de
  autoria** na pauta e **auditoria sem valor anterior** na troca. Mesmo com G1/P2 aplicado,
  migrar a guarda de **escrita** (`POST /frequencia`) sem decidir autoria/histórico tornaria
  a troca de professor irrevogavelmente anônima. **Não implementado — apenas reportado.**
- **Ensaio em `pautaon_ensaio`:** não executado (sem mudança a validar; a troca da oferta 50
  não foi feita).

---

## 5. T2 — higiene (commit `72e9d40`)

- `app/registros/core.py`: removidos os 2 imports sem uso — `RegistroAula` e `User` (F401).
  Nenhuma outra ocorrência no módulo; `app/registros/__init__.py` só importa os submódulos
  de rotas, então não há re-export a preservar.
- `tests/`: removidas as 9 atribuições a variáveis locais nunca lidas (F841), **mantendo a
  chamada** que produz o efeito de preparo do cenário:

| Arquivo | Ocorrência | Tratamento |
|---|---|---|
| `test_d3b2_2_listagem_caracterizacao.py` | `s = _base(app)` (:22) | `_base(app)` |
| `test_d3b2_2_n1_freq_geral.py` | `turma = next(...)` (:39) | removida (expressão pura, sempre não usada) |
| `test_d3b2_2_n1_freq_geral.py` | `s = _ids(app)` (:82) | `_ids(app)` |
| `test_l4_lixeira.py` | `s = _base(app)` (:55 e :69) | `_base(app)` |
| `test_transferencia_oferta.py` | `aluno_id, of1, of2 = ...` (:210) | `aluno_id, of2 = i["aluno"], ativas[1]` |
| `test_turma_curso_fase3.py` | `o1 = adicionar_oferta(...)` (:292) | `adicionar_oferta(...)` |
| `test_turma_curso_horario_migration.py` | `oferta = _oferta_com_curso(...)` (:239 e :354) | `_oferta_com_curso(...)` |

- **Ruff:** `--select F821,F811,F841` em `app tests scripts` → *All checks passed*;
  `--select F401` em `app/registros/core.py` → limpo.
- **Suíte:** baseline da rodada **1006 passed** → após a T2 **1006 passed, 0 failed**
  (347 s). Os 6 arquivos tocados, isolados: **53 passed**.
- **Fora de escopo (não tocado):** restam 87 F401 no projeto (re-exports de
  `app/models/__init__.py` e imports de conforto em `scripts/`/`tests/`) — muitos
  intencionais; ficam como pendência de higiene se a equipe quiser fechar o `ruff` global.

Artefatos usados (somente leitura, em `.tmp/`): `p0_g1p2_readonly.py` (contagem de ofertas
sem professor, `is_nullable`, head Alembic), `t0b_autores.py` (metadados: autoria por
tabela), `t0c_log_acao_readonly.py` (contagem e amostra de `log_acao`).

---

## 6. Pendências

1. **G1/P2 (destrava a T1):** decidir os professores das ofertas 16, 17, 18, 19 (principal)
   e 50 (ensaio) → `ValueError` no serviço + `required`/remoção do "-- Sem professor --" na
   UI → só depois a migration NOT NULL.
2. **T1 (guardas por oferta):** `ver_turma`, `ver_observacoes`, `/frequencia` GET/POST,
   `historico_aluno`, `/aluno/<id>/foto`, com links de pauta/Diário por oferta no
   `detalhe.html` (admin/gestão veem todas; sem link que leve a 403).
3. **Autoria e auditoria da troca:** decidir se `frequencia` passa a ter autor do
   lançamento e se a troca de professor exige confirmação + registro com valor
   anterior→posterior (hoje `log_acao.detalhes` = `<TurmaCurso 14>`).
4. **Medicação na pauta:** decisão da instituição (conteúdo; não afeta quem lança).
5. **Documentação:** backlog `:111` com a regra antiga por `COALESCE`, contrariada por
   `:100`/`:104` e pelo MER §8.12 — alinhar o texto histórico ou anotar a correção.
6. **Higiene global:** 87 F401 remanescentes (fora do escopo desta rodada).

---

## 7. Registros da rodada

- HEAD inicial: `77e7fef`. Commit da T2: `72e9d40`. Documentação: commit seguinte.
- Nenhum arquivo de aplicação (fora `core.py`, imports) ou de migração foi tocado;
  **nenhuma migration criada**; sem push.
- No working tree permanecem **edições de terceiros** em andamento (rename "Diário de
  Observações" → "Diário de Bordo" em `app/relatorios/observacoes.py`, templates
  `dashboard/professor.html`, `relatorios/painel_pedagogico.html`, `turmas/detalhe.html`,
  `turmas/observacoes.html`, 4 MD e 3 testes) — **excluídas** desta entrega por staging
  seletivo (`git apply --cached` sobre os hunks próprios).
