# ETAPA M4 — Política de desativar_oferta + histórico de oferta inativa em período encerrado

Ramo `Onda4`. Suíte final: **291 passed, 0 falhas** (entrada: 278 pós-M2; +13
no arquivo novo). Nenhum commit foi feito.

---

## Passo 1 — Leitura (antes de alterar)

### `desativar_oferta` (serviço) e sua rota

- **Serviço**: `app/services/turma_curso.py`, `desativar_oferta` (L472–485 em
  HEAD). Guardas atuais: apenas um — se, removida esta oferta, restarem **2+
  ofertas ativas sem principal**, `ValueError("A turma ficará com mais de um
  curso ativo sem principal…")`. Depois: `oferta.ativo = False`,
  `sincronizar_programa_turma(oferta.turma)` e `db.session.commit()` (padrão
  do módulo: serviços daqui commitam; conversão em flash é da rota).
- **Rota**: `app/registros/turmas.py`, `turma_oferta_desativar` —
  `POST /turma/oferta/<int:oferta_id>/desativar` (L1643–1657). Perfis e
  isolamento via `_turma_para_ofertas` (L1481–1489): papel em
  admin/pedagogico/secretaria/gerencia (senão 403), turma existente (senão
  404) e `assert_unidade_context(turma.unidade_id, get_unidade_id())` (403 —
  vale também para ADMIN/GERENCIA sem unidade na sessão). `ValueError` →
  flash warning + redirect; sucesso → flash "O curso '…' foi removido da
  turma." + redirect.
- **Chamadores de `desativar_oferta`** (grep exaustivo): somente a rota acima
  e `tests/test_turma_curso_fase2.py` (3 testes de unidade do serviço).
  **`excluir_turma` NÃO chama `desativar_oferta`** — desativa as ofertas por
  atributo próprio (`turmas.py` L1682–1683: `oferta.ativo = False` em loop,
  na transação da exclusão lógica). Nenhum outro fluxo interno usa o serviço.
  Portanto a exigência do enunciado ("a guarda não pode alterar excluir_turma")
  foi atendida **sem tocar excluir_turma** — não foi necessário PARE.

### `cond_inscricao_enturmada` (BI)

`app/relatorios/bi_filtros.py` L16–60 em HEAD: `Inscricao.ativo` AND turma
ativa (EXISTS anti-auto-correlação) AND **oferta apontada ATIVA e pertencente
à mesma turma** (EXISTS `TurmaCurso.ativo IS TRUE`, endurecido na B6). Oferta
inativa não contava em hipótese alguma — era o ponto de retroatividade a
resolver. Consumidores: `bi_alunos.py`, `bi_indicadores`, `test_bi_turma_desativada.py`
(helper `_count_inscricoes_enturmadas`).

### `aluno_status` e oferta/turma inativas

`app/services/aluno_status.py`, `status_alunos`: filtra por `Turma.ativo`
(True obrigatório; comentado contra inflar DESENTURMADO) e por
`Turma.periodo_letivo_id == periodo.id`. Para `data_ref >= hoje` usava
**apenas `Inscricao.ativo`** — não olhava a oferta de forma alguma (isto é,
desativar oferta não alterava o status hoje, mas também não havia noção de
"oferta efetiva"). Para datas passadas reconstrói o vínculo por
`data_inicio`/`data_desativacao` (oferta também não olhada — intocado).

### Período da turma

`Turma.periodo_letivo_id` **nullable** → `Turma.periodo_letivo` relationship;
`PeriodoLetivo` (`app/models/academico.py` L37–67): `nome`, `data_inicio`,
`data_fim` (Date, não-nulos), `TenantMixin` (unidade_id) e `SoftDeleteMixin`
(`ativo` default True). Turma sem período é estado possível (D3/B6 tratam
disso na listagem); para a guarda M4 conta como **em andamento** (regra
explícita do enunciado).

---

## Passo 2 — Guarda em `desativar_oferta` + rota

- Novo helper privado `_alunos_ativos_em_andamento(oferta)`: conta
  `Inscricao.ativo` com `turma_curso_id == oferta.id` **em turma ativa** cujo
  período satisfaz `or_(Turma.periodo_letivo_id.is_(None),
  PeriodoLetivo.data_fim.is_(None), PeriodoLetivo.data_fim >= hoje)` —
  distinct por aluno; `data_fim >= hoje` cobre andamento **e** futuro; sem
  período (ou `data_fim` NULL, por conservadorismo) conta como andamento.
- `desativar_oferta(oferta, *, verificar_alunos_em_andamento=False)`: guarda
  executada **só com o flag ligado**, **depois** do guarda antigo de
  principal (preservado intocado). Mensagem do `ValueError`:
  `Não é possível remover o curso '<curso>': há N aluno(s) ativo(s) na oferta
  em período letivo ainda em andamento ('<período>'). A desativação só é
  permitida após o encerramento do período ou quando não houver alunos
  ativos.` — traz **quantidade de alunos** e **nome do período**.
- Rota `turma_oferta_desativar`: única mudança foi
  `desativar_oferta(oferta, verificar_alunos_em_andamento=True)` — o
  `try/except ValueError → flash` existente já exibe a mensagem e **não
  grava** (o serviço levanta antes de tocar `ativo`/commit).
- Padrão `False` mantém o comportamento antigo para qualquer chamada sem o
  flag (testes de fase 2 continuam válidos; `excluir_turma` não passa por
  aqui).

## Passo 3 — Histórico: oferta inativa em período encerrado conta

- `app/relatorios/bi_filtros.py`: novo helper **`cond_oferta_efetiva()`** —
  EXISTS em `TurmaCurso` (id = `Inscricao.turma_curso_id`, turma coerente com
  a inscrição) tal que `TurmaCurso.ativo` **OU** período da turma encerrado
  (`PeriodoLetivo.data_fim < hoje`; JOIN interno Turma→PeriodoLetivo; período
  NULL/sem período ⇒ exige oferta ativa). `correlate_except(TurmaCurso)`
  preservado (lição da anti-auto-correlação).
  `cond_inscricao_enturmada` passou a usar `cond_oferta_efetiva()` no lugar
  do exists "oferta ativa" puro (a exigência de turma ativa e coerente
  permanecem; a checagem `TurmaCurso.turma_id == Inscricao.turma_id` foi
  absorvida pelo novo helper).
- `app/services/aluno_status.py`: no ramo `data_ref >= hoje`,
  `vinculo_em_data = and_(Inscricao.ativo, _cond_oferta_efetiva())` —
  predicado **espelhado** do BI. O ramo de datas passadas (reconstrução por
  início/desativação) ficou intocado.

## Passo 4 — `tests/test_desativar_oferta.py` (novo, 13 testes)

Datas **relativas a `get_local_now().date()`** (HOJE±30/60/100/200 dias) para
o teste sobreviver à rolagem do calendário. Um usuário por teste. Rota:
bloqueia em andamento (2 alunos), flash-fonte com contagem e nome do período,
bloqueia futuro, bloqueia sem período; permite encerrado (assert de
estabilidade: BI `== bi_antes` e `status_alunos` idênticos antes/depois),
permite com inscrição inativa, permite sem alunos. Serviço/leitores: BI de
período em andamento não conta oferta inativa (desativada via caminho
interno); `desativar_oferta` sem flag mantém comportamento antigo; status
estável em período encerrado. Guardas/segurança: principal com 2+ restantes
preservado (via rota + mensagem do serviço); outra unidade → 403; admin sem
unidade na sessão → 403.

---

## Diff por arquivo (exclusivo desta etapa)

| Arquivo | Alteração |
|---|---|
| `app/services/turma_curso.py` | `_alunos_ativos_em_andamento` (novo); `desativar_oferta` ganha flag keyword-only `verificar_alunos_em_andamento` (guarda nova; antiga intocada); imports `func`, `PeriodoLetivo`, `get_local_now` |
| `app/registros/turmas.py` | `turma_oferta_desativar`: chama o serviço com `verificar_alunos_em_andamento=True` (+comentário); nada mais |
| `app/relatorios/bi_filtros.py` | Novo `cond_oferta_efetiva()`; `cond_inscricao_enturmada` passa a usá-la (docstring atualizada) |
| `app/services/aluno_status.py` | `_cond_oferta_efetiva()` (espelho local); `vinculo_em_data` do ramo atual passa a exigi-la |
| `tests/test_desativar_oferta.py` | **Novo** — 13 testes (roteiro do Passo 4) |

Nada de enturmação, desenturmação, transferência, conselho, `excluir_turma`,
migrations ou outros docs foi tocado.

## Decisões tomadas sozinho

1. **Guarda parametrizada no serviço** (`verificar_alunos_em_andamento=False`
   por padrão) em vez de guarda incondicional: é a forma mínima de atender
   "só no caminho da rota" sem duplicar lógica e sem tocar `excluir_turma`
   (que, de qualquer forma, não chama o serviço).
2. **Ordem das guardas**: principal primeiro, depois alunos-em-andamento —
   comportamento antigo permanece de cara para chamadores existentes.
3. **`data_fim` NULL no período = em andamento** (conservador), alinhado com
   "turma sem período conta como em andamento".
4. **Anti-auto-correlação** no novo EXISTS do BI com `correlate_except` +
   junções internas (Turma/PeriodoLetivo ficam correlacionados de fora, como
   no padrão J2/B6) — evita o bug histórico de FROM zerado.
5. **Ciclo de import resolvido com duplicação deliberada**:
   `aluno_status` importou `cond_oferta_efetiva` de `app.relatorios.bi_filtros`,
   mas o `__init__` do pacote relatórios importa `bi_alunos`, que importa
   `aluno_status` → `ImportError` em cadeia. Como `bi_*` fora de
   `bi_filtros.py` está fora do escopo, o predicado foi **espelhado** como
   `_cond_oferta_efetiva()` em `aluno_status.py`, com comentário apontando a
   duplicação e o motivo. (Alternativa rejeitada: lazy import — manteria
   acoplamento oculto service→blueprint.)
6. **Status do dia atual passa a respeitar oferta inativa em período em
   andamento** (antes `aluno_status` ignorava a oferta): é a consequência
   direta do enunciado ("oferta inativa em período em andamento… não
   conta"), aplicada só ao ramo `data_ref >= hoje` — o de datas passadas
   permanece intacto.

## Testes

- Arquivo novo: **13 passed**.
- Reteste direcionado pós-mudança (BI/status/fase2): `test_bi_indicadores`,
  `test_bi_turma_desativada`, `test_aluno_status`, `test_turma_curso_fase2` →
  39 passed sem alteração desses arquivos.
- **Suíte completa: `291 passed, 51 warnings in 37.27s`** (meta 0 falhas;
  278 + 13). Warnings = DeprecationWarning pré-existente (`datetime.utcnow`
  em `pessoas.py`).
- Nenhum conflito de finalidade com testes existentes (nenhum testa a rota
  de desativar; os do serviço fase 2 chamam sem o flag e passaram intactos).

## Pendências

- **Duplicação do predicado** `cond_oferta_efetiva` (bi_filtros) vs
  `_cond_oferta_efetiva` (aluno_status): unificável em etapa futura movendo o
  helper para módulo neutro (ex.: `app/models/` ou `app/utils/`), pois
  `app.relatorios` não pode ser importado por `app.services` sem ciclo.
- Coleta da contagem no teste de flash usa o serviço (fonte da mensagem) já
  que a rota redireciona sem renderizar; um teste com `follow_redirects=True`
  na página `turma_ofertas` poderia asserir o flash literal, exigindo seed de
  mais campos da view.
- `PeriodoLetivo.ativo=False` não é considerado na guarda/leitura (regra lida
  só de `data_fim`); se o responsável quiser período inativado = "encerrado"
  independentemente da data, é ajuste de uma linha nos dois predicados.
- Sem commit, conforme instrução.

## Resumo pytest

```
291 passed, 51 warnings in 37.27s
```
