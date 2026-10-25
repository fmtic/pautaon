# ETAPA D5.5 — Endurecimento do conselho por oferta + limpeza + seletor da ficha 360°

**Resultado:** migration `f6a7b8c9d0e1` aplicada e ensaiada em SCRATCH (`pautaon_ensaio`), suíte
`359 passed, 83 warnings in 55.61s` (0 falhas; meta ≥349), banco `pautaon` **não** tocado,
nenhum commit.

Decisões do responsável implementadas:

1. `conselho_classe.turma_curso_id` NOT NULL; `uix_conselho_legado` removido e
   `uix_conselho_oferta` como unicidade plena por oferta.
2. `Turma.conselho_concluido` **removida** (encerramento derivado das ofertas).
3. `Turma.avaliacao_inicial/percurso/final` **mantidas**, apenas documentadas como legado.
4. Ponte que sincronizava `Turma.conselho_concluido` em `alternar_conselho` removida.
5. `MER.md` e `backlog_desenvolvimento.md` não foram alterados.

---

## 1. Leitura e relato (antes de qualquer alteração)

### (a) Ocorrências de `conselho_concluido` em `app/`, templates, scripts e tests

| Arquivo:linha | Classificação | Destino |
|---|---|---|
| `app/models/academico.py:136` (coluna) + docstring da `Turma` | **modelo** | coluna `Turma.conselho_concluido` **removida**; docstring passou a dizer que o encerramento é da oferta e derivado |
| `app/planejamento.py:86-90` | **ponte** | `alternar_conselho` gravava `turma.conselho_concluido = all(...)` — ponte **removida** |
| `app/services/turma_curso.py:57-95` (`turma_conselho_concluido`) | leitor derivado | já só lê `TurmaCurso.conselho_concluido`; **intocado** (fora do escopo) |
| `app/services/turma_curso.py:171`, `app/registros/periodos.py:596` | leitores | certificado/lista já usam a flag da **oferta** (D5.3/D5.4) — intocados |
| `app/templates/conselho/painel.html:130`, `app/conselho.py:212` | textos | descrevem o encerramento por oferta — intocados |
| `app/models/MER.md:423` | **documentação** | fora do escopo (etapa própria de docs) |
| `tests/test_conselho_oferta.py:120,572,587,593,609,616,626,638` | **teste** | sementes `Turma(conselho_concluido=False)` e asserções da ponte → ajustados |
| `tests/test_d5_encerramento.py:55,77,155,174,276` | **teste** | sementes/asserções da ponte → ajustados |
| `tests/test_d5_leitores.py:221,443` | **teste** | idem |
| `tests/test_painel_periodo.py:55` | **teste** | idem |
| `tests/test_isolamento_unidade_escrita.py:112,118,659,669,689-692` | **teste** | idem (agora assere a **ausência** da coluna e a flag da oferta) |
| `tests/test_d5_schema.py:144-153,197-222` | **teste** | coexistência legado×oferta → reescrita para o estado novo |

Nenhum **script** lia/escrevia `Turma.conselho_concluido`.

### (b) Migration head, `verificar_onda4_d5.py` e `preparar_deploy_onda4.py`

- Head: `migrations/versions/e5f6a7b8c9d0_conselho_oferta_esquema_d51.py` (D5.1) — criou
  `turma_curso_id` nullable, `uix_conselho_legado`, `uix_conselho_oferta`, `ix_conselho_turma_curso`
  e `turma_curso.conselho_concluido/avaliacao_*`.
- `scripts/verificar_onda4_d5.py:74` (`main`): estrutura (colunas/índices/FK) + seções (a)
  conselhos NULL, (c) duplicatas, (d) flag legado × ofertas, (e) parecer coletivo legado,
  (f) `ConselhoResposta.aluno_id` NULL, (g) conselho × turma da oferta.
- `scripts/preparar_deploy_onda4.py:509` seção **F** (informativa, D5.1) e `:88`
  `_nullable_insp` — não havia seção de bloqueio para o endurecimento.

### (c) Mapas etapa→campo

- `app/models/enums.py:146-150` — `ETAPA_PARA_CAMPO_AVALIACAO`
  (`INICIAL→avaliacao_inicial`, `PERCURSO→avaliacao_percurso`, `FINAL→avaliacao_final`).
- Mapas **inline duplicados** em `app/conselho.py:141-152` (`_get_turma_avaliacao_respostas`) e
  `app/conselho.py:844` (`setattr` de `avaliar_turma`).
- Chaves são `EtapaConselho` (str-enum com nome == valor), portanto o `lookup` por string
  `'INICIAL'` vindo de `request.values` funciona; `TurmaCurso.avaliacao_*` tem os mesmos nomes.

### (d) Órfãos

| Órfão | Grep | Resultado |
|---|---|---|
| `app/static/js/periodos/conselhos.js` | `conselhos.js` em `app/`, templates, `pyproject` | **nenhuma** referência |
| `app/templates/conselho/relatorio.html` | `conselho/relatorio.html` / `relatorio.html` | **nenhuma** referência |
| `PerguntaConselho` em `app/registros/core.py:23-35` | uso no arquivo | nenhum — **import morto** |

### (e) Ficha 360° (antes)

- `app/relatorios/painel_pedagogico/rota.py:195-217` escolhia a inscrição com
  `filter_by(aluno_id, turma_id, ativo=True).first()` (com `turma_id`) ou a inscrição ativa mais
  recente; jamais considerava oferta.
- `ficha_aluno.py:623-646` — `_resolver_inscricao()` já resolvia `?oferta_sel=` **dentro do
  serviço** (via `has_request_context()`), o que duplicava a regra M1.
- `ficha_aluno.html:205-257` — card de identidade; ponto do seletor após "Dias e horário"
  (L250-253).

---

## 2. Migration nova — `f6a7b8c9d0e1`

`migrations/versions/f6a7b8c9d0e1_conselho_oferta_endurecimento_d55.py` (`down_revision =
'e5f6a7b8c9d0'`), no padrão de `c3d4e5f6a7b8`/`d4e5f6a7b8c9`:

- **Pré-checagens somente leitura** (`_checar_antes_de_alterar`), reunidas em **um único
  `RuntimeError` em português**; nada é corrigido nem atribuído:
  - **(i)** `conselho_classe.turma_curso_id IS NULL`: total, quantos com `concluido` ou
    `situacao_final`, primeiros 20 ids e remissão a `scripts/verificar_onda4_d5.py`;
  - **(ii)** duplicatas `(turma_curso_id, aluno_id, etapa)` com contagem e amostra;
  - **(iii)** `conselho.turma_id <> turma_curso.turma_id` (id do conselho, turma, oferta e turma
    da oferta);
  - **(iv)** `turma.conselho_concluido IS TRUE` com alguma oferta **ativa** pendente (nome da turma
    e "concluídas de ativas").
- **Upgrade** (por inspeção, idempotente): guarda se `turma_curso_id` não existe (→ mensagem
  própria pedindo `e5f6a7b8c9d0`); `batch_alter_table` `turma_curso_id` → `nullable=False`;
  recria `uix_conselho_oferta` só se ausente; `drop_index uix_conselho_legado` se presente;
  remove `turma.conselho_concluido` (`op.drop_column` no PG, `batch` no SQLite).
- **Downgrade**: guarda contra duplicatas `(turma_id, aluno_id, etapa)` de linhas NULL; recria
  `turma.conselho_concluido BOOLEAN NOT NULL DEFAULT false` e **repopula com o derivado**
  (`todas as ativas concluídas`); recria `uix_conselho_legado` (WHERE `turma_curso_id IS NULL`);
  `turma_curso_id` volta a `nullable=True`.
- `uix_conselho_oferta` foi **mantido** como está (com `WHERE turma_curso_id IS NOT NULL`), que é
  o pedido literal do passo 2 ("manter"); o predicado é inócuo após o NOT NULL.

---

## 3. Modelos

`app/models/conselho.py`
- `turma_curso_id`: `nullable=False`, com `comment` "FK → turma_curso (D5.5: obrigatória; conselho
  legado sem oferta não existe)".
- `__table_args__` sem `uix_conselho_legado`; permanecem `uix_conselho_oferta` (único, WHERE
  parcial), `ix_conselho_turma_curso` e o `CheckConstraint` de `situacao_final`.
- Docstring do módulo atualizada (o ramo legado NULL saiu).

`app/models/academico.py`
- `Turma.conselho_concluido` **removida**; docstring da `Turma` agora diz que o encerramento é da
  OFERTA (`turma_curso.conselho_concluido`) e que a visão da turma é derivada na leitura.
- `Turma.avaliacao_inicial/percurso/final` preservadas, com o comentário
  **"LEGADO: parecer coletivo agora em turma_curso.avaliacao_*; remover após conferir dump
  autêntico"**.

---

## 4. Código

- `app/planejamento.py` (`alternar_conselho`): removida a sincronização
  `turma.conselho_concluido = all(...)`; mantidos o toggle da oferta, a validação da oferta e o
  isolamento por unidade.
- `app/conselho.py`: `ETAPA_PARA_CAMPO_AVALIACAO` importado de `app.models.enums` e usado nos dois
  pontos antes inline (`_get_turma_avaliacao_respostas` e `avaliar_turma`). Não restou nenhum mapa
  etapa→campo local (grep `avaliacao_inicial|avaliacao_percurso|avaliacao_final` só acha o mapa,
  o comentário e o default do `.get`).
- Órfãos removidos após o grep do passo 1(d): `app/static/js/periodos/conselhos.js`,
  `app/templates/conselho/relatorio.html` e o import morto `PerguntaConselho` em
  `app/registros/core.py`.

---

## 5. Scripts

`scripts/verificar_onda4_d5.py` (somente leitura; funciona **antes e depois**):
- antes (`turma_curso_id` nullable): `AVISO: conselho_classe.turma_curso_id ainda é NULLABLE —
  f6a7b8c9d0e1 (D5.5) não aplicada (estado D5.1)` e
  `AVISO: uix_conselho_legado presente — ... (será removido)`, além de
  `AVISO: coluna turma.conselho_concluido presente — ... (será removida)`;
- depois: `OK: conselho_classe.turma_curso_id NOT NULL (D5.5 aplicada)` e ausência das duas
  estruturas antigas;
- a seção **(d)** só roda quando a coluna da turma existe (`cols_turma`), e o resumo final
  permanece `OK: estrutura e integridade do conselho por oferta (D5.1/D5.5) íntegras.`

`scripts/preparar_deploy_onda4.py` (`:88` `_nullable_insp`, `:573` **seção G**):
- se `turma_curso_id` já é NOT NULL e a coluna da turma sumiu →
  `OK: D5.5 aplicada (...) — nenhum bloqueio de endurecimento`;
- senão, (i)–(iv) viram **BLOQUEIO** (`FALHA` + `bloqueios += 1`), exit **1**, com remissão a
  `scripts/verificar_onda4_d5.py`;
- seções informativas (A–F) intactas; mensagem final agora cita
  `c3d4e5f6a7b8, d4e5f6a7b8c9 e f6a7b8c9d0e1`.

---

## 6. Ficha 360° — seletor de oferta

`app/relatorios/painel_pedagogico/rota.py`
- novos helpers `_inscricoes_da_turma()` (inscrições **ativas** do aluno na turma, `joinedload`
  da oferta, ordem por id) e `_resolver_oferta(candidatas, atual, oferta_sel)`: 1 inscrição →
  comportamento anterior; 2+ → `?oferta_sel=` só vale se casar com uma inscrição **do aluno
  naquela turma**, senão mantém a inscrição entregue/primeira.
- o contexto ganhou `ofertas_disponiveis` (`{turma_curso_id, rotulo}` via `rotulo_oferta`, formato
  "Turma — Curso") e `oferta_sel`.

`app/templates/relatorios/ficha_aluno.html` — `<form method="get">` com `turma_id` oculto e
`<select name="oferta_sel" onchange="this.form.submit()">`, exibido **somente** com
`ofertas_disponiveis|length > 1`.

`ficha_aluno.py` — `_resolver_inscricao()` removida (virou lógica duplicada da rota) junto com o
import `has_request_context, request`; `montar()` continua recebendo a inscrição já resolvida.

---

## 7. Testes

Novo `tests/test_d5_endurecimento.py` (7 testes, um usuário por teste):

| Teste | Cobre |
|---|---|
| `test_conselho_sem_oferta_levanta_integrity_error` | conselho sem oferta → `IntegrityError`, nada gravado |
| `test_duplicata_por_oferta_recusada_e_duas_ofertas_permitidas` | mesmo aluno em 2 ofertas OK; duplicata na mesma oferta/etapa recusada |
| `test_turma_sem_atributo_conselho_concluido` | sem atributo/sem coluna; `Turma(conselho_concluido=...)` → `TypeError`; flag existe na oferta |
| `test_alternar_conselho_nao_escreve_na_turma` | `alternar_conselho` muda só a oferta; coluna da turma inexistente |
| `test_avaliar_turma_grava_cada_etapa_no_campo_certo` | INICIAL/PERCURSO/FINAL caem em `avaliacao_*` via `ETAPA_PARA_CAMPO_AVALIACAO`; nada vaza entre etapas; `Turma.avaliacao_*` intocada |
| `test_ficha_com_aluno_em_duas_ofertas_escolhe_por_oferta_sel` | ficha escolhe por `?oferta_sel=` (validado; valor fora das inscrições cai na primeira) e mostra o seletor |
| `test_ficha_com_uma_inscricao_nao_mostra_seletor` | 1 inscrição por turma → comportamento anterior |

Ajustes sem mudar finalidade:
- `test_d5_schema.py`: `_conselho()` com oferta obrigatória; `turma_curso_id` NOT NULL; o caso
  "duplicata legada/coexistência" virou "conselho sem oferta recusado" e "`turma` sem a flag, a
  flag só na oferta"; índice agora só `uix_conselho_oferta` + `ix_conselho_turma_curso`.
- `test_conselho_oferta.py`: sementes sem `conselho_concluido`; `test_alternar_*` asserem só a
  oferta (e a ausência da coluna); `test_legado_null_nao_e_tocado` → `test_conselho_sem_oferta_
  recusado_pelo_banco`.
- `test_d5_encerramento.py`: removidas as sementes que "mentiam" na turma; docstring atualizada.
- `test_d5_leitores.py`: pares `(aluno, None)` continuam ignorados (sem linha NULL); painel
  "ignora conselho legado NULL" → "não exibe conselho sem oferta" (o banco recusa); ficha passa a
  considerar o seletor na página; `Turma Antiga` sem o flag.
- `test_isolamento_unidade_escrita.py`: `alternar` agora assere `TurmaCurso` e
  `not hasattr(Turma, "conselho_concluido")`.
- `test_painel_periodo.py` e `test_turma_curso_exclusao.py`: semente de `ConselhoClasse` ganhou
  `turma_curso_id`; `Turma` sem o flag.

Nenhuma finalidade de teste **fora** do escopo conflitou — não houve parada.

---

## 8. Ensaio em SCRATCH (`pautaon_ensaio`, nunca `pautaon`)

Harness: `instance/backups/ensaio_d55/` (`run_ensaio.ps1`, `00_diag.sql`, `10_pos.sql`,
`b/c/d/e_inject.sql`, `msg_upgrade.py`, `out/`). Cada cenário recria o banco a partir de
`instance/backups/antes_fase4_20261022_211317.sql`, sobe até `e5f6a7b8c9d0`, injeta e aplica a
migration nova. Base restaurada: 3 turmas, 1 oferta ativa cada, `conselho_classe` vazio.

> `msg_upgrade.py` existe porque `flask db upgrade` (e `flask_migrate.upgrade()`) **engole** a
> exceção: `catch_errors` faz `sys.exit(1)` após logar em logger desabilitado pelo `fileConfig` do
> `migrations/env.py`. Ele chama `alembic.command.upgrade` direto e grava a mensagem em UTF-8
> (o redirecionamento do PowerShell decodifica com a code page do console e transformava acentos
> em mojibake).

### Cenário A — base limpa
- `upg_exit=0`; `msg`: `upgrade ok (sem exceção)`.
- Estado final: `alembic_version = f6a7b8c9d0e1`; `conselho_classe.turma_curso_id` `is_nullable=NO`;
  `turma.conselho_concluido` **0 rows**; índices `conselho_classe_pkey`,
  `ix_conselho_turma_curso`, `uix_conselho_oferta (UNIQUE ... WHERE turma_curso_id IS NOT NULL)`;
  15 constraints, incluindo `conselho_classe_turma_curso_id_not_null` e
  `fk_conselho_classe_turma_curso ... ON DELETE RESTRICT`.
- **Downgrade** (`down_exit=0`): `e5f6a7b8c9d0`, `turma_curso_id` `YES`,
  `turma.conselho_concluido` de volta (`NO`, `column_default=false`), `uix_conselho_legado`
  recriado (`WHERE turma_curso_id IS NULL`), 14 constraints; **re-upgrade** `reup_exit=0`;
  **segundo upgrade** `reup2_exit=0` (idempotência por inspeção, sem DDL).

### Cenário B — conselho com `turma_curso_id` NULL
`upg_exit=1` e a mensagem **única** (checagem i):

```
RuntimeError: Não é possível aplicar f6a7b8c9d0e1 (endurecimento do conselho por oferta): (i) 1 conselho(s) com turma_curso_id NULL (0 concluído(s) ou com situação final); ids das primeiras 20 linhas: 1 — diagnóstico detalhado em scripts/verificar_onda4_d5.py. Nenhum dado foi alterado por esta migration. Resolva as pendências acima (ver scripts/verificar_onda4_d5.py e scripts/preparar_deploy_onda4.py) e rode o upgrade novamente.
```

- Revisão **permanece** `e5f6a7b8c9d0`; `turma_curso_id YES`; `turma.conselho_concluido` presente
  (`NO`); `uix_conselho_legado` presente; o conselho (`id=1`, turma 2, aluno 269, `INICIAL`,
  `turma_curso_id` vazio) **intocado**.
- `verificar_onda4_d5.py`: `AVISO: 1 conselho(s) legado(s) sem oferta — ... sem inscrição do aluno
  na oferta: 1` (exit 0). `preparar_deploy_onda4.py`:
  `FALHA: (i) 1 conselho(s) sem oferta (0 concluído(s)/com situação) — primeiros ids: 1` e
  `1 checagem(ns) com FALHA — há limpeza obrigatória antes do upgrade.` (exit 1).

### Cenário C — `turma_id` divergente da oferta
Injeção: `turma_id=1` com `turma_curso_id=2` (oferta da turma 2). `upg_exit=1`:

```
RuntimeError: Não é possível aplicar f6a7b8c9d0e1 (endurecimento do conselho por oferta): (iii) 1 conselho(s) com turma_id divergente da turma da oferta: conselho=1 (turma=1, oferta=2 da turma 2). Nenhum dado foi alterado por esta migration. Resolva as pendências acima (ver scripts/verificar_onda4_d5.py e scripts/preparar_deploy_onda4.py) e rode o upgrade novamente.
```

- Revisão permanece `e5f6a7b8c9d0`; estrutura antiga intacta; conselho preservado.
- `verificar_onda4_d5.py`: `FALHA: 1 conselho(s) com turma_id divergente da turma da oferta`
  (exit 1). `preparar_deploy_onda4.py`:
  `FALHA: (iii) 1 conselho(s) com turma_id divergente da turma da oferta: conselho=1 (turma=1 ×
  oferta 2 da turma 2)` (exit 1).
- (ii) **não é injetável** aqui: `uix_conselho_oferta`, criado em `e5f6a7b8c9d0`, já recusa a
  duplicata — a checagem é rede de segurança para bases sem o índice (registrado no `c_inject.sql`).

### Cenário D — flag legado da turma sem equivalente por oferta
`turma 3` (`4 - Canoagem`) com `conselho_concluido = TRUE` e a única oferta ativa pendente.
`upg_exit=1`:

```
RuntimeError: Não é possível aplicar f6a7b8c9d0e1 (endurecimento do conselho por oferta): (iv) 1 turma(s) com turma.conselho_concluido = true e ofertas ativas pendentes: turma=3 (4 - Canoagem: 0 de 1 ofertas ativas concluídas). Nenhum dado foi alterado por esta migration. Resolva as pendências acima (ver scripts/verificar_onda4_d5.py e scripts/preparar_deploy_onda4.py) e rode o upgrade novamente.
```

- Revisão permanece `e5f6a7b8c9d0`; coluna da turma e índices antigos presentes.
- `verificar_onda4_d5.py`: `AVISO: 1 turma(s) com flag legado divergente das ofertas` (exit 0).
  `preparar_deploy_onda4.py`:
  `FALHA: (iv) 1 turma(s) com conselho_concluido=true e ofertas pendentes: turma=3 (4 - Canoagem:
  0/1 ofertas ativas concluídas)` (exit 1).

### Cenário E — 1 oferta concluída com conselho vinculado
`turma 2` e oferta 2 com `conselho_concluido = TRUE`; conselho (`aluno 269`, `FINAL`) vinculado à
oferta 2. `upg_exit=0`, `msg`: `upgrade ok (sem exceção)`. Estado final:
`f6a7b8c9d0e1`; `turma_curso_id NO`; `turma.conselho_concluido` **0 rows**; conselho preservado
(`id=1, turma=2, aluno=269, FINAL, turma_curso_id=2`); `turma_curso 2` com flag `t`.

### Estado final do SCRATCH
Recriado do dump e no **head**: `f6a7b8c9d0e1 (head)`, 0 conselhos,
`verificar_onda4_d5.py` → `OK: estrutura e integridade do conselho por oferta (D5.1/D5.5)
íntegras.`

---

## 9. Suíte completa

```
359 passed, 83 warnings in 55.61s
```

(antes da etapa: 352 passed; +7 do `tests/test_d5_endurecimento.py`, sem remoção de testes)

---

## 10. Decisões tomadas sozinho

1. **Cenário C = divergência `turma_id`** (iii) em vez de duplicata: a duplicata é impossível de
   injetar com `uix_conselho_oferta` no lugar, e o objetivo do passo 8 ("mensagem") fica coberto.
2. **`uix_conselho_oferta` mantém o `WHERE turma_curso_id IS NOT NULL`** — o passo 2 manda
   "manter" o índice; o predicado é inócuo com NOT NULL. Modelo, migration e teste registram isso.
3. **`_resolver_inscricao` removida de `ficha_aluno.py`**: a regra M1 passou a viver na rota
   (o serviço recebia `request` indiretamente). `montar()` ficou puro.
4. **`?oferta_sel=` inválido cai na inscrição padrão** (a entregue pela rota / primeira por id),
   nunca mistura ofertas nem aborta — mesma semântica do M1 já usada no resultado do conselho.
5. **Reescrita de três testes cuja finalidade (linha legada NULL coexistindo) deixou de existir**:
   `test_d5_schema` (autorizado explicitamente), `test_conselho_oferta::test_legado_null_nao_e_
   tocado` e `test_d5_leitores::test_painel_ignora_conselho_legado_null`. A finalidade foi
   preservada na forma mais forte: o banco **recusa** o conselho sem oferta e o leitor segue sem
   adotar par `(aluno, None)`.
6. **Helper `msg_upgrade.py` no ensaio** para capturar a mensagem exata (os wrappers do
   Flask-Migrate a engolem) e gravar UTF-8 sem mojibake do console.
7. **`verificar_onda4_d5.py` mantém (d) como AVISO**; o bloqueio duro ficou na migration e na
   seção G de `preparar_deploy_onda4.py`.

---

## 11. Pendências

1. Aplicar `flask db upgrade` no banco real (`pautaon`) — **não** executado nesta etapa; rodar
   `scripts/preparar_deploy_onda4.py` (exit 0 obrigatório) e `scripts/verificar_onda4_d5.py`
   antes.
2. Conferir no dump autêntico se existe parecer legado em `Turma.avaliacao_*` antes de removê-las
   (o comentário LEGADO no modelo aponta para isso).
3. `docs/MER.md:423` (e o backlog) ainda descrevem `turma.conselho_concluido` — etapa própria de
   documentação.
4. `turma_conselho_concluido()` (`app/services/turma_curso.py:57`) segue sem leitor de produção
   (só testes) — candidato a limpeza em etapa futura.
5. `ruff` acusa 25 achados **pré-existentes** nos arquivos tocados (E712/F841/F401/I001 em
   `app/conselho.py`, `app/models/academico.py`, `app/models/conselho.py`, `app/planejamento.py`,
   `tests/test_conselho_oferta.py`, `tests/test_d5_schema.py`) — não corrigidos por estarem fora do
   escopo; os arquivos **novos** (`f6a7b8c9d0e1_*.py`, `tests/test_d5_endurecimento.py`,
   `msg_upgrade.py`) e os demais alterados (`rota.py`, `ficha_aluno.py`, scripts) estão limpos.

---

## 12. Arquivos alterados nesta etapa

- **novo:** `migrations/versions/f6a7b8c9d0e1_conselho_oferta_endurecimento_d55.py`
- **novo:** `tests/test_d5_endurecimento.py`
- **novo (ensaio):** `instance/backups/ensaio_d55/` (`run_ensaio.ps1`, `msg_upgrade.py`,
  `00_diag.sql`, `10_pos.sql`, `b/c/d/e_inject.sql`, `out/`)
- **alterados:** `app/models/conselho.py`, `app/models/academico.py`, `app/planejamento.py`,
  `app/conselho.py`, `app/registros/core.py`, `scripts/verificar_onda4_d5.py`,
  `scripts/preparar_deploy_onda4.py`, `app/relatorios/painel_pedagogico/rota.py`,
  `app/relatorios/painel_pedagogico/ficha_aluno.py`, `app/templates/relatorios/ficha_aluno.html`,
  `tests/test_d5_schema.py`, `tests/test_d5_leitores.py`, `tests/test_conselho_oferta.py`,
  `tests/test_d5_encerramento.py`, `tests/test_isolamento_unidade_escrita.py`,
  `tests/test_painel_periodo.py`, `tests/test_turma_curso_exclusao.py`
- **removidos:** `app/static/js/periodos/conselhos.js`, `app/templates/conselho/relatorio.html`
