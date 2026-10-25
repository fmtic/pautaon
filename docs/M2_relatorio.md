# ETAPA M2 — Serviço único de criação de inscrição + desenturmar por oferta

Ramo `Onda4`. Suíte final: **278 passed, 0 falhas** (baseline pós-B6: 262; +16 no
arquivo novo). Nenhum commit foi feito.

---

## Passo 1 — Leitura (antes de alterar)

### (a) Rota de desenturmação

- **Arquivo/linhas**: `app/registros/alunos.py`, `desenturmar_alunos`, rota
  `POST /turma/desenturmar/<int:id>` (em HEAD: def na L727; corpo ~L728–820).
- **Perfis autorizados**: `PEDAGOGICO`, `ADMIN`, `SECRETARIA`, `GERENCIA`;
  qualquer outro (`PROFESSOR`, `SERVICO_SOCIAL`) → `abort(403)`.
- **Isolamento**: `assert_unidade_context(aluno.unidade_id, get_unidade_id())` e,
  havendo turma, `assert_unidade_context(turma.unidade_id, get_unidade_id())`
  (`app/registros/shared.py` L27–39: obj None → 403; sessão sem unidade → 403;
  mismatch → 403 — vale também para ADMIN/GERENCIA, que usam a unidade da
  sessão; Visão Global é somente leitura).
- **Semântica de saída (duas, preservadas)**:
  - existe `Frequencia` com `conceito` não-nulo para aluno+turma+oferta →
    **soft-desativa** a inscrição: `ativo=False`,
    `data_desativacao=get_local_now()`, `motivo_desativacao="DESENTURMADO"`;
  - sem Frequencia conceituada → **delete físico** da inscrição.
- **Descoberta relevante**: em HEAD a rota **já tinha suporte parcial por
  oferta** — aceitava `turma_curso_id` e filtrava por ele — porém com `.first()`
  (alunos.py L751–753 na versão anterior), que "escolhia" silenciosamente quando
  o id era omitido. O template `detalhe.html` **já tinha botão por oferta** (POST
  com `turma_curso_id=oferta.id` + CSRF, dentro do card de cada oferta, desde a
  M1). O alvo real do Passo 3 era portanto o `.first()` e o caso 2+ sem escolha.
- **Chamadores/templates**: `app/templates/turmas/detalhe.html` (botão por
  oferta na lista de matriculados) — único chamador. Existe um
  `detalhe copy.html` no diretório, cópia obsoleta **fora do escopo** (ver
  Pendências).

### (b) Os dois pontos que criam `Inscricao`

1. `app/registros/turmas.py` — `enturmar_alunos` (~L1037): validações antes de
   inserir — perfis (PEDAGOGICO/ADMIN/SECRETARIA/GERENCIA), unidade da turma,
   resolução 0/1/2+ ofertas ativas (0 → flash "Esta turma ainda não tem
   curso…"; 2+ sem `turma_curso_id` válido → flash "Selecione o curso
   (oferta)…"; oferta de outra turma/inativa → mesmo flash), e, por aluno:
   `Inscricao` ativa duplicada em aluno+turma+oferta → salto silencioso
   ("já está enturmado"), criação com `data_inicio=date.today()` e `nivel`.
2. `app/registros/alunos.py` — `transferir_aluno` (L964): perfis
   (ADMIN/PEDAGOGICO/SECRETARIA), unidade da sessão obrigatória, origem
   (inscrição ativa + oferta da mesma turma), destino escolhido dentro das
   ofertas ativas de turmas ativas da unidade (exclui a turma de origem), data
   não-anterior ao início da oferta, duplicidade no destino → flash "O aluno já
   está inscrito nessa oferta de destino.", e só então cria a `Inscricao` de
   destino com `data_inicio=data_transferencia` e o `nivel` da origem.

### (c) Como `transferir_aluno` desativa a origem

No mesmo bloco transacional (alunos.py ~L1108–1139): `inscricao_origem.ativo =
False`, `data_desativacao = datetime.combine(data_transferencia - 1 dia,
datetime.min.time())`, `motivo_desativacao = "TRANSFERENCIA"`; em seguida cria a
inscrição de destino, registra `Transferencia` e faz **um único commit**.

---

## Passo 2 — `app/services/enturmacao.py` (novo)

Serviço `enturmar_aluno(aluno, turma, oferta_id=None, *, nivel=None,
data_inicio=None)`:

- resolve 0/1/2+ ofertas via `ofertas_ativas(turma.id)` (já filtra ativo e da
  turma → validação de oferta implícita e confiável);
- 0 ofertas → `ValueError(MSG_TURMA_SEM_OFERTA)`; 2+ sem id, ou id que não
  aponta para oferta ativa da turma → `ValueError(MSG_SELECIONE_OFERTA)`;
- duplicidade ativa por aluno+turma+oferta → `ValueError(MSG_JA_ENTURMADO)`;
- cria a `Inscricao` com `data_inicio` (default `date.today()`) e **não
  commita** — a transação continua sob controle da rota.

Mensagens são **as mesmas strings** que as rotas já exibiam (concentradas em
constantes). Refactor dos chamadores:

- `enturmar_alunos` (turmas.py): mantém os pré-checks de rota (preservam a
  ordem/UX exata dos flashes, ver Decisões) e troca o corpo do loop por
  chamada ao serviço com `try/except ValueError` (duplicata = salto silencioso
  como antes).
- `transferir_aluno` (alunos.py): única alteração foi a criação da inscrição de
  destino (L1117–1123); a checagem de duplicidade prévia da rota (flash
  original) e a desativação da origem ficaram **intocadas**.

**Requisito verificado**: `tests/test_enturmacao_oferta.py` +
`tests/test_transferencia_oferta.py` (+ `tests/test_security_regressions.py`)
passaram **sem nenhuma alteração nesses arquivos** — 44 passed na verificação
intermediária.

## Passo 3 — Desenturmar por oferta (`desenturmar_alunos`)

Substituído o `.first()` por escolha explícita (alunos.py L751–777):

- com `turma_curso_id`: busca escopada em aluno+turma+`ativo=True`+oferta via
  `one_or_none()` (segura pelo índice único parcial
  `uix_inscricao_ativa_aluno_oferta`) **nova guarda**: a oferta apontada precisa
  pertencer à mesma turma (`oferta_alvo.turma_id != turma.id` → tratada como
  não encontrada), o que também barra oferta de outra unidade por
  transitividade (a turma já passou pelo `assert_unidade_context`);
- sem `turma_curso_id`: 1 inscrição ativa → age nela (comportamento atual);
  **2+ → recusa com flash** "Selecione a oferta da qual deseja desenturmar o
  aluno." e **não grava nada**;
- nada encontrado → flash "Aluno não está enturmado nesta oferta.";
- mantidos: perfis, asserts de unidade (inclusive para ADMIN/GERENCIA — regra
  do responsável), motivo `DESENTURMADO`, `data_desativacao`, semântica
  Frequencia→soft / sem→delete físico, redirect com `oferta_sel`.

## Passo 4 — `app/templates/turmas/detalhe.html`

O botão por oferta já existia por card de oferta; ajuste (diff: +5/−2):
`title` e `confirm` passam a trazer **o nome do curso** da oferta
("Desenturmar de {curso}"), com comentário identificando o Passo 4. POST e
`csrf_token` mantidos; nenhuma outra parte da lista de matriculados alterada.
Aluno em 2+ ofertas aparece em cada card com seu próprio botão (estrutura já
vinha da M1 via `alunos_por_oferta`); em 1 oferta o botão é o mesmo de antes.

## Passo 5 — `tests/test_desenturmacao_oferta.py` (novo, 16 testes)

Harness próprio (SQLite `:memory:`, `WTF_CSRF_ENABLED=False`), **um usuário por
teste**. Rota: (1) 1 inscrição sem Frequencia → delete físico como antes;
(2) 1 inscrição com Frequencia conceituada → soft com `DESENTURMADO` +
`data_desativacao`; (3) 2 ofertas sem escolha → recusa, nada gravado; (4) 2
ofertas com escolha → só a apontada sai, a outra segue ativa; (5) oferta de
outra turma recusada; (5b) inscrição inconsistente (turma_id de uma turma,
oferta de outra) recusada pela guarda nova; (6) inscrição inativa não é alvo;
(7) usuário de outra unidade → 403; (8) admin sem unidade na sessão → 403.
Serviço (unitários): 0 ofertas; 1 oferta sem id (auto-seleção, `nivel`/
`data_inicio` gravados); 2+ sem id; 2+ com id; oferta inativa; oferta de outra
turma; duplicata.

Correções durante escrita do teste (só no arquivo novo): `TurmaCurso` tem
UNIQUE `(turma_id, curso_id)` → seed passou a criar um curso por oferta; leitura
de `outra.id` fora do app context causou `DetachedInstanceError` → id capturado
dentro do bloco.

---

## Diff por arquivo (exclusivo desta etapa)

| Arquivo | Alteração |
|---|---|
| `app/services/enturmacao.py` | **Novo** (95 linhas) — serviço único de criação de inscrição |
| `app/registros/turmas.py` | `enturmar_alunos`: import do serviço; corpo do loop delega a `enturmar_aluno` (pré-checks de rota intactos) |
| `app/registros/alunos.py` | `transferir_aluno`: criação da inscrição de destino via serviço (desativação da origem intocada); `desenturmar_alunos`: `.first()` → `one_or_none()` + 2+ exige escolha + guarda oferta∈turma |
| `app/templates/turmas/detalhe.html` | Botão de desenturmar com nome do curso no `title`/`confirm` (+5/−2) |
| `tests/test_desenturmacao_oferta.py` | **Novo** — 16 testes (roteiro do Passo 5) |

Nenhuma outra mão nesta etapa: `tests/test_enturmacao_oferta.py`,
`tests/test_transferencia_oferta.py` e `tests/test_security_regressions.py`
continuam inalterados pela M2 (as diffs que exibem no `git status` são das
etapas anteriores B1–B6/M1). BI, relatórios, conselho, `excluir_turma`,
`adicionar_oferta`/`desativar_oferta`, migrations e docs (exceto este
relatório) não foram tocados.

## Decisões tomadas sozinho

1. **Pré-checks de 0/1/2+ permanecem na rota `enturmar_alunos`** além do
   serviço: a ordem dos flashes é comportamento observado (turma com 0 ofertas
   e zero alunos selecionados flasha "Esta turma ainda não tem curso…" antes
   de qualquer loop); delegar 100% ao serviço inverteria UX. Na path de 1
   oferta a rota resolve `oferta_id = ofertas[0].id` e o serviço nunca recebe
   id inválido dessa rota — os `ValueError` do serviço atuam como rede de
   segurança.
2. **Duplicata comparada pela constante** `MSG_JA_ENTURMADO` (não por texto
   solto) no `except ValueError` da rota; qualquer outro `ValueError` é
   re-lançado (fail-fast).
3. **Flash de duplicidade da transferência preservado pelo pré-check da rota**
   ("O aluno já está inscrito nessa oferta de destino.") — o serviço devolve
   `MSG_JA_ENTURMADO`, textualmente diferente; mantive os dois níveis
   deliberadamente para não mudar flashes existentes.
4. **Guarda `oferta_alvo.turma_id != turma.id`** no desenturmar trata oferta de
   outra turma como "não encontrada" (flash já existente), em vez de flash
   novo — mínimo comportamento adicional exigido pelo Passo 3.
5. **`one_or_none()` é seguro** porque o índice único parcial garante ≤1
   inscrição ativa por aluno+oferta; mesmo assim o resultado é escopado por
   aluno+turma+ativo.

## Testes

- Arquivo novo: 16 passed.
- Suíte de sanitização da M2 (enturmacao + transferencia + security_regressions):
  44 passed, sem alteração nesses arquivos.
- **Suíte completa: `278 passed, 51 warnings in 36.98s`** (meta 0 falhas;
  baseline 262 + 16 novos). Warnings são DeprecationWarning pré-existentes
  (`datetime.utcnow` em `pessoas.py`).

## Pendências

- `app/templates/turmas/detalhe copy.html`: cópia obsoleta com variante antiga
  do botão — fora do escopo da M2; candidate a remoção em etapa de limpeza.
- Checagem de duplicidade existe em dois níveis (rota de transferência +
  serviço); unificável em etapa futura, com cuidado para não alterar o flash
  existente.
- `desenturmar_alunos` usa `request.values` (aceita `turma_curso_id` também por
  query string no POST) — coerente com o template, mas digno de nota.
- Sem commit, conforme instrução.
