# ETAPA H1 — Relatório final

**Horário por dia de aula na oferta: modelo, migration, serviço e conversor (sem mudar comportamento)**

Data: 26/10/2026 · Branch: `nova_feature` (sem push) · Baseline: 400 passed / head `a8b9c0d1e2f3`

---

## 1. Commits criados (branch `nova_feature`, sem push)

| Hash | Mensagem (resumida) |
|---|---|
| `850be94` | P0a (B5-P1): `fileConfig` com `disable_existing_loggers=False` no `env.py`; MER §12.17 atualizado com a prova no scratch |
| `b3cb389` | P0b: remover template morto `turmas/listar copy.html` (grep: nenhuma rota/template/JS a referencia) |
| `cb5418c` | P1: conversor único de dias (`app/utils/dias_semana.py`) com testes; parsers antigos intocados até o H3 |
| `fbab4fe` | P2: modelo `TurmaCursoHorario` com constraints; relacionamento `horarios` em `TurmaCurso`; `dias_semana` → `String(80)` |
| `910c291` | P3: migration aditiva `5730d7c594ba` (tabela + ALTER varchar80 + backfill herança campo a campo); checagens (i)–(v) num `RuntimeError`; downgrade com guarda |
| `c3469fe` | P4: serviço `turma_curso_horario.py` (leitura em lote, `definir_grade` atômico, `duracao/uniforme/resumo`, `sincronizar_projecao_horario` como único ponto de projeção) |
| `7677d0c` | P5: testes de schema/serviço/migration + helper `grade_a_partir_do_legado` |
| `b0c2f1a` | P6: ensaio A–E no scratch; MER (cabeçalho, §2, §6.2, §7.7, §7.32, nova §7.32a, §8.10, §10, §11, §12.5/§12.25) + backlog; correção da mensagem da checagem (iii) |

- Prova P0a: migration descartável (não commitada) forçando `RuntimeError` → `flask db upgrade` exibiu `ERROR [flask_migrate] Error: ...` (antes o logger ficava silenciado).
- Prova P0b: `grep` por `listar copy` em `app/` retornou zero referências.

## 2. Suíte e head

- **458 passed, 0 failed** (baseline 400 + 15 do P1 + 43 do P5).
- Head Alembic única: **`5730d7c594ba`** (`flask db heads`, conferido ao final).
- `ruff check app --select F821`: **All checks passed!**

## 3. Ensaio A–E no scratch `pautaon_ensaio`

- **A — upgrade limpo**: a partir da head `a8b9c0d1e2f3` (dump restaurado, dados apagados com `TRUNCATE ... CASCADE`): upgrade ok, tabela `turma_curso_horario` criada com todas as constraints (verificadas via `information_schema`/`pg_get_constraintdef`), 0 linhas, `varchar(80)` aplicado nas duas tabelas.
- **B — dados reais**: restore do dump do `pautaon` local; upgrade populou **8 linhas para 5 ofertas** (ids 11–15); comparação `resumo_grade` × colunas antigas para toda oferta: **0 divergências**.
- **C — um caso por checagem** (injeção via UPDATE; upgrade falhou com `rc=1` e mensagem visível em todos, graças ao B5-P1):
  - (i) `"Fulgora"` → `(i) oferta N: token de dia desconhecido em dias_semana: 'Fulgora'`
  - (ii) `"Seg., Segunda"` → `(ii) oferta N: dia duplicado após normalização`
  - (iii) início da oferta + sem fim em lugar algum → `(iii) oferta N: par de horas incompleto após COALESCE (tem início, falta fim)` (rótulo estava invertido na versão inicial; corrigido e revalidado no commit P6)
  - (iv) 15:00–13:00 e 13:00–13:00 → duas ocorrências de `(iv) ... fim <= início` acumuladas no mesmo erro
  - (v) horas sem dias (oferta e turma limpos) → `(v) oferta N: tem horário efetivo mas nenhum dia`
  - (vi) oferta ativa com dias e sem horário: **upgrade prosseguiu**, apenas log informativo.
- **D — downgrade**: com grades uniformes recompôs `dias_semana`/`hora_inicio`/`hora_fim` idênticas às originais e dropou a tabela; re-upgrade recriou as 8 linhas. Teste unitário separado prova recusa clara quando há grade não uniforme (`NÃO uniforme`, lista ids). O `varchar(80)` **não** foi reduzido de volta (documentado no docstring da migration).
- **E — idempotência**: `stamp` na própria revisão + `upgrade` duas vezes → 8 linhas antes e depois, sem duplicação nem alteração.
- O scratch terminou rebaixado a `a8b9c0d1e2f3`, sem resíduo; todos os scripts temporários do ensaio foram apagados.

## 4. `max(length(dias_semana))` e divergências no ensaio B

- No banco principal: **15** caracteres em `turma` e **15** em `turma_curso` (cabe folgadamente nos 80).
- Ensaio B: **0 de 5 ofertas divergiram**. Valores reais distintos: `Quarta`, `Segunda, Quarta`, `Segunda, Terça`, `Terça` — todos já canônicos com acento.

## 5. Testes existentes que MUDARIAM se o conversor novo substituísse o antigo

- `tests/test_turma_curso_fase3.py::TestParseDias` (3 testes: `test_csv_normal`, `test_none`, `test_vazio`): assertam `_parse_dias` devolvendo **set de strings** minúsculas; o conversor devolve `list[int]` → todos falham (mudança de contrato).
- `tests/test_turma_curso_fase4.py::test_data_bate_dias_semana_acento_espace_variante`: os casos atuais passariam no conversor novo (inclusive `Terça-feira`), **mas** o teste ancora o contrato antigo; entradas sem acento ("Terca") hoje dão `False` e dariam `True` — nenhuma fixture pré-H1 usa forma sem acento/abreviada (grep confirmado), então o resultado deste teste específico não mudaria com os dados atuais.
- Casos de fronteira sem teste hoje, que mudariam de comportamento (registrar para o H3):
  - `tests/test_turma_curso_lista.py:136` `"Segunda,Quarta"` (sem espaço): os splits atuais toleram; a projeção canônica via `weekdays_para_csv` regravaria para `"Segunda, Quarta"` — as asserções do teste (marcadores `href`/nomes) não quebrariam.
  - Tokens desconhecidos: o parser antigo os guarda no set (inofensivo); o novo os descarta silenciosamente — `csv_tokens_desconhecidos` existe justamente para dar voz a isso no H3.
  - Filtros de listagem (`app/registros/turmas.py:197-203`): com os fixtures canônicos atuais (`test_filtros_turmas.py`, `test_carga_horaria.py`) o resultado seria idêntico; só mudaria com tokens variantes (abreviados/sem acento), inexistentes hoje.

## 6. Desvios do pedido e por quê

1. **Ensaio A reformulado**: o histórico Alembic do projeto não sobe de um banco vazio (revisões antigas pressupõem schema legado `user`); "upgrade limpo" foi feito como restore do dump → `TRUNCATE ... CASCADE` dos dados → upgrade (schema na head + tabelas vazias).
2. **Refill do scratch via `pg_dump`/`psql`** em vez de `CREATE DATABASE ... TEMPLATE pautaon`: o template falhou com `ObjectInUse` (2 sessões ativas no principal) e a regra proíbe derrubar sessões dele.
3. **Correção na migration durante o P6**: rótulo da checagem (iii) dizia "tem fim" quando na verdade tem início; corrigido, revalidado por reinjeção + 14 testes unitários (commit `b0c2f1a`).
4. **`tests/_helpers.py` ganhou apenas** `grade_a_partir_do_legado` (aditivo, como pedido); nenhum teste existente foi tocado — a suíte pré-existente continua 100% verde sem alterações.

## 7. Perguntas abertas

1. **Autorização para aplicar `5730d7c594ba` no principal `pautaon`** (hoje intacto em `a8b9c0d1e2f3`; backup já feito: `instance/backups/pautaon_pre_H1.sql`, 530.906 bytes). Aguarda decisão — não será aplicada sem isso.
2. O scratch `pautaon_ensaio` deve permanecer rebaixado a `a8b9c0d1e2f3` (estado atual) ou já deixar na head nova para conveniência do H2?
3. No H5, ao remover as colunas escalares: o espelho `Turma.dias_semana`/horas (usado por `calcular_dias_aula_turma` e geradores de data) também será removido ou a turma passaria a derivar dias da oferta principal?
4. `Sábado-feira` foi tolerado pelo conversor (o parser antigo só conhecia `{nome}-feira` exato, e "segunda-feira"…"domingo-feira" eram as formas dele); normalizar essa forma estranha é desejado, ou deve virar token desconhecido?

## 8. Confirmações explícitas

- **Nenhum leitor/escritor existente foi alterado**: nenhuma rota, template, JS, serviço ou parser existente (`_parse_dias`, `_data_bate_dias_semana`, `calcular_dias_aula_turma`, splits de listagem, `_sincronizar_legado`) sofreu mudança de comportamento; o diff `658120c..HEAD` toca apenas os arquivos listados nos passos. A grade nasce populada pela migration, mas ninguém a lê ainda nos fluxos da aplicação.
- **A migration NÃO foi aplicada no banco principal**: conferido ao final — `alembic_version` do `pautaon` continua `a8b9c0d1e2f3`. Todos os ensaios rodaram exclusivamente no scratch `pautaon_ensaio`.
