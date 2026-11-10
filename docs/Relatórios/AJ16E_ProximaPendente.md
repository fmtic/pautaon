# AJ16-E — "Ir para a próxima pendente" → Salvar → "Preencha a data da aula antes de salvar."

Data: 09/11/2026 · Branch `aj16-e-proxima-pendente` (worktree `D:/pautaon-aj16e`) · Sem push · SQLite only

## 1. Pedido

Na tela `/frequencia`, ao clicar em **"Ir para a próxima pendente"**, a página abre na data pendente
(ex.: 19/08/2026, bem anterior à atual), temas/valores/conceitos preenchidos, e ao **Salvar** aparece
**"Preencha a data da aula antes de salvar."** Investigar a causa raiz em SQLite, dizer se é pré-existente
(`release-2026-11-05`) ou regressão do AJ16-B, corrigir na fonte e cobrir com teste de regressão.

## 2. Reprodução e causa raiz

### 2.1 O que foi verificado (e descartado)

| Hipótese | Resultado |
|---|---|
| (a) `proxima_pendente` fora das opções do `<select name="data">` | **FALSO.** Ver §2.2. |
| (b) POST usa `data` ou cai em `data_hidden`? | Usa `data or data_hidden` (`core.py`), com fallback — mesmo com `data=""` o `data_hidden` carrega a data. |
| (c) link usa `turma_id=` e GET lê outro parâmetro? | Consistente: GET lê `request.args.get('turma_id')`; JS e links emitem `turma_id`/`data`/`turma_curso`. |

### 2.2 `proxima_pendente` e o `<select>` saem da MESMA fonte — sempre

- `situacao_datas.proxima_pendente` vem de `situacao_datas_oferta(turma, oferta_atual)`
  (`app/utils/frequencia.py`), que calcula as datas por `datas_aula_oferta(oferta, blocked=datas_bloqueadas_str(periodo))`.
- As opções do `<select name="data">` vêm de `ctx['datas']`, preenchido no GET por
  `datas_aula_oferta(oferta_atual, limite=hoje, blocked=_blocked_dates_str(turma))` (`core.py`, bloco T2).

As duas chamadas usam **o mesmo calendário da oferta** (vigência + grade + bloqueios). Para a data
pendente especificamente, a inclusão é garantida: o conjunto de bloqueios de `situacao_datas_oferta`
(`datas_bloqueadas_str`, nível período, **sem** as exceções por turma) é um **superconjunto** do de
`_blocked_dates_str` (período **menos** `DiaBloqueadoTurma`). Logo as datas de `situacao` são subconjunto
das do seletor, e `proxima_pendente ∈ datas` do `<select>`. Verificado empiricamente em vários cenários
(1 oferta, 2 ofertas, prof/admin, bloqueios, exceções, parcial, legado, outra oferta na mesma data).

**A hipótese (a) está descartada** — e mesmo que a pendente não estivesse nas opções, a primeira opção do
select é `value=""` mas o campo `data_hidden` continuaria com a data, e o fallback `data or data_hidden`
impediria `data_post` vazio.

### 2.3 A divergência REAL encontrada (e reproduzida)

O POST de `/frequencia` validava `data_post` **antes** de resolver a oferta, contra
`carregar_contexto_turma(turma_id)['datas']` = `gerar_datas(turma)` — o calendário da **TURMA**:

- `gerar_datas` exige `turma.data_inicio` **e** `turma.data_fim` não nulos (senão devolve `[]`);
- usa a **união** dos dias de grade de **todas** as ofertas ativas (`dias_da_turma`);
- limita a `[turma.data_inicio, min(turma.data_fim, hoje)]`.

Já o seletor e a `proxima_pendente` usam `datas_aula_oferta(oferta)` — vigência e grade **da oferta**
(`NULL` herda da turma). Quando a **vigência da oferta diverge da vigência da turma** — ou a turma não
tem vigência própria — uma data legítima da oferta, **inclusive a apontada pelo botão**, **não pertence**
ao calendário da turma e era recusada no POST.

**Reproduzido em SQLite** (antes da correção):
- turma sem `data_inicio/data_fim` + oferta com vigência própria → `gerar_datas=[]` → toda data de oferta
  rejeitada com *"A data informada não pertence ao calendário válido da turma."*
- oferta com `data_inicio` anterior ao da turma → a pendente (data mais antiga da oferta) caía fora do
  calendário da turma → mesma recusa.

### 2.4 De onde vem "Preencha a data da aula antes de salvar."

A mensagem é emitida em `app/registros/core.py` quando `salvar_frequencia` retorna `data` falsy
(`(0, None)`). Isso acontece em dois casos dentro de `salvar_frequencia` (`app/utils/logica.py`):

1. `data_alvo` vazio/não parseável ou `turma_id == 0` — **impossível no fluxo do botão** (o `data` do
   select e o `data_hidden` sempre carregam a pendente; `data_post` nunca é vazio).
2. **`except Exception` genérico → rollback + `return (0, None)`** — qualquer exceção inesperada durante
   a gravação é convertida na mensagem enganosa "Preencha a data". O erro real fica só no log
   (`current_app.logger.exception`).

O caso (2) é a causa mais provável do sintoma relatado em produção: uma exceção específica de dados que o
SQLite de teste não reproduz (ex.: `IntegrityError`, `ValueError` do `resolver_oferta_lancamento` interno
num caminho de resolução divergente). A correção da divergência de calendário remove a recusa espúria na
fronteira; o `except` genérico que mascara o erro real permanece como dívida técnica registrada (não foi
alterado para não esconder falhas nem mudar o contrato de `salvar_frequencia`).

## 3. Pré-existente ou regressão?

**PRÉ-EXISTENTE.** O código da tag `release-2026-11-05` (`app/registros/core.py`) tem **exatamente** a
mesma lógica de POST: o mesmo `data_post = data or data_hidden`, a mesma checagem antecipada contra
`carregar_contexto_turma(...)['datas']` e o mesmo flash "Preencha a data". A divergência calendário da
turma × calendário da oferta **já existia** na release — não foi introduzida pelo AJ16-B (que tratou de
valores da aula, não de datas).

## 4. Correção implementada

`app/registros/core.py` (rota `frequencia`, POST):

- Removida a checagem antecipada de `data_post` contra `contexto['datas']` (calendário da turma) que
  rodava **antes** da resolução da oferta.
- Após `oferta_post` ser resolvida (e a guarda de professor), a data agora é validada contra o
  **mesmo calendário que a tela oferece**:
  - com oferta resolvida → `datas_aula_oferta(oferta_post, limite=hoje, blocked=_blocked_dates_str(turma))`
    — idêntico ao `<select>` e ao `situacao_datas` do GET;
  - sem oferta (legado) → `contexto['datas']` (`gerar_datas`), comportamento inalterado.
- A recusa continua com a mensagem coerente *"A data informada não pertence ao calendário válido da
  turma."*, agora redirecionando com `redirect_back` (preserva `data`/`turma_curso`).

Resultado: datas que a UI oferece — inclusive a "próxima pendente" — passam a ser aceitas; datas que a UI
**não** oferece (fora da grade/vigência da oferta, bloqueadas, futuras) continuam recusadas. Não é remendo:
a fonte da validação foi unificada com a fonte do seletor.

Além disso, o flash final foi tornado honesto: quando `data_post` foi efetivamente enviada e passou pela
validação de calendário, um retorno sem data de `salvar_frequencia` só pode vir de uma exceção interna
(já registrada no log) — a rota passa a mostrar *"Não foi possível salvar a frequência. Tente novamente."*
em vez da mensagem enganosa "Preencha a data da aula antes de salvar.". O caso de data realmente ausente
(`data_post` vazio) continua com a mensagem original.

## 5. Testes

`tests/test_aj16e_regressao.py` — segue o fluxo real do navegador: extrai o link "Ir para a próxima
pendente" do HTML renderizado, abre a data pendente (GET) e envia o formulário com o campo `data` do
`<select>` preenchido.

| Teste | Cenário | Código antigo | Código novo |
|---|---|---|---|
| `test_pendente_salva_com_turma_sem_vigencia` | turma sem vigência + oferta com vigência | **falha** (recusa "não pertence") | passa (grava) |
| `test_pendente_salva_com_oferta_vigencia_alem_da_turma` | oferta vigente antes da turma | **falha** (recusa "não pertence") | passa (grava) |
| `test_pendente_salva_cenario_normal` | turma=oferta mesma vigência (controle) | passa | passa |
| `test_data_fora_do_calendario_da_oferta_e_recusada` | data que não é dia de aula da oferta | — | recusa coerente, não grava |

Verificado com `git stash` do `core.py`: os dois testes de divergência **falham no código antigo** e passam
com a correção — regressão comprovada.

**Suíte completa** (`pytest tests/`): **1663 passed, 0 failed, 1 skipped** — o único skip é ambiental e
pré-existente (`test_aj5c_form_rerender.py:180`, "pasta de upload não existe no ambiente de teste"; a pasta
de upload não existe neste worktree, nada a ver com a mudança). **Ruff** `F821,F811,F841,F401` nos arquivos
alterados: sem achados (os 43 achados repo-wide são pré-existentes em arquivos não tocados).

## 6. Commits

- Commit `AJ16-E` neste branch (`aj16-e-proxima-pendente`): `app/registros/core.py` (correção),
  `tests/test_aj16e_regressao.py` (regressão) e este relatório. Sem push.
