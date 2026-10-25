# Relatório — V1: Verificação pós-migration `c3d4e5f6a7b8` (somente leitura)

Data: 24/10/2026. Nada alterado: código, banco, migrations e docs intocados; nenhum
commit. Três arquivos temporários de apoio (`_v1_consulta.py`, `_v1_simula.py`,
`_v1_pytest.log`/`_v1_failures.txt`) foram criados para executar os passos 2/4/5 e
**apagados** ao final — o repo voltou ao estado anterior.

---

## 1. A migration `c3d4e5f6a7b8` (lida por inteiro)

Arquivo: `migrations/versions/c3d4e5f6a7b8_inscricao_exige_oferta.py` (41 linhas).
Revisa `a1b2c3d4e5f6`; **possui sucessora** `d4e5f6a7b8c9`
(`programa_obrigatorio_na_oferta`), que é o head da cadeia.

**O que faz com inscrições `turma_curso_id` NULL: absolutamente nada.** Não há UPDATE,
DELETE, INSERT nem qualquer guarda por nº de ofertas ativas (0 / 1 / 2+). O upgrade
executa apenas, dentro de `batch_alter_table("inscricoes")`:

1. `alter_column("turma_curso_id", nullable=False)`;
2. criação do índice único (abaixo).

**Não atribui oferta e não aborta por decisão própria** — quem aborta é o banco: se
qualquer linha (ativa **ou inativa**) tiver `turma_curso_id IS NULL` no momento da
execução, o PostgreSQL rejeita o ALTER com `NotNullViolation` e a migration inteira
falha (DDL transacional). A limpeza prévia é pré-requisito implícito da migration.

**Índice único criado:** `uix_inscricao_ativa_aluno_oferta` sobre
(`aluno_id`, `turma_curso_id`), `unique=True`, parcial —
`postgresql_where="ativo IS TRUE"` / `sqlite_where="ativo = 1"`. Leitura:

- só vale para **ativas** → duplicatas inativas (histórico) continuam permitidas,
  intencional;
- **não protege contra NULL** (no PostgreSQL NULLs são distintos em índice único) —
  a proteção contra NULL vem exclusivamente do NOT NULL;
- duas linhas NULL ativas do mesmo aluno não são deduplicadas pelo índice (ficam fora
  do WHERE); com NOT NULL isso deixa de existir.

**Downgrade:** drop do índice + `nullable=True`. Reversível, sem perda de dados.

## 2. Estado do banco local (apenas SELECT — executado)

`flask db current` → **`d4e5f6a7b8c9 (head)`** — a `c3d4e5f6a7b8` **já foi aplicada**
no PostgreSQL local (`localhost:5432/pautaon`; credenciais no `.env`, não copiadas).

| Checagem | Resultado |
|---|---|
| Inscrições com `turma_curso_id` NULL ativas | **0** |
| Inscrições com `turma_curso_id` NULL inativas | **0** |
| Duplicatas ativas por (`aluno_id`, `turma_curso_id`) | **nenhuma** |
| Inscrições ativas apontando para oferta inativa | **0** |
| `information_schema` → `inscricoes.turma_curso_id` | `is_nullable = NO` (aplicado) |
| `pg_indexes` → `uix_inscricao_ativa_aluno_oferta` | presente: `CREATE UNIQUE INDEX ... (aluno_id, turma_curso_id) WHERE (ativo IS TRUE)` |

Nota histórica: `scripts/verificar_onda4_m1.py` rodado neste mesmo banco ainda hoje
encontrou 7 NULL ativos na turma #6; hoje estão em zero — houve backfill/limpeza entre
a M1.1 e a aplicação da migration. Banco local está **coerente com o novo schema**.

## 3. Código (executado por grep, leitura confirmada)

**Modelo** (`app/models/matriculas.py`): `Inscricao.turma_curso_id` está
**`nullable=False`** (L59-61) e `__table_args__` (L42-52) declara o mesmo índice único
parcial `uix_inscricao_ativa_aluno_oferta` — modelo e banco alinhados com a migration.
Docstring já afirma "Só pode existir uma inscrição ativa por aluno e oferta".

**Todos os pontos que criam `Inscricao(` em `app/` (2 ocorrências; ambos cumprem o NOT NULL):**

| Arquivo:linha | Função | Passa `turma_curso_id`? |
|---|---|---|
| `app/registros/turmas.py:1070` | `enturmar_alunos` | Sim — `oferta_id` resolvido pelas regras 1/2+ ofertas (nunca NULL) |
| `app/registros/alunos.py:1100` | `transferir_aluno` | Sim — `oferta_destino.id`; a rota exige `turma_curso_id_destino` no POST, valida contra ofertas ativas da unidade e checa duplicata por aluno+turma+oferta antes de inserir |

`scripts/`: nenhuma instanciação de `Inscricao(`.

**Sementes de `tests/` que violam o NOT NULL (NULL explícito ou campo omitido)** —
inventário completo por grep (`Inscricao(`, 11 arquivos, sem truncamento):

- `test_enturmacao_oferta.py` :334, :340 (NULL explícito) e helper `_null_ativa` :407
- `test_turma_curso_fase4.py` :90, :682 (NULL explícito)
- `test_security_regressions.py` :166, :213 (omitido)
- `test_pauta_professor.py` :71, :76, :159 (omitido)
- `test_bi_indicadores.py` :179, :327 (omitido)
- `test_bi_turma_desativada.py` :270 (omitido); :138 usa `oferta.id if oferta else None`
- `test_turma_curso_exclusao.py` :262 (omitido)
- `test_aluno_status.py` :77 (omitido)

Conformes (passam oferta): `test_turma_curso.py:189`; `test_turma_curso_fase4.py`
:92/:176/:386/:450/:681/:871; `test_turma_curso_fase4_dash.py:90`;
`test_turma_curso_exclusao.py:123`.

## 4. Suíte completa (executada)

```
120 failed, 88 passed, 5 warnings, 11 errors in 105.86s
```

**As 2 falhas preexistentes de `/cursos` continuam entre as falhas**
(`test_cursos_exigem_unidade_e_isolam_cursos_de_outra_unidade` e
`test_curso_criar_editar_inativar_e_validar_carga_horaria`), mas o cenário é outro: a
migration (e a sucessora) **quebrou a suíte inteira**. As 131 entradas
(120 FAILED + 11 ERROR) agrupadas por causa:

| Causa | Qtd | Onde |
|---|---|---|
| `IntegrityError: NOT NULL constraint failed: turma_curso.programa` — sementes criam `TurmaCurso` sem `programa` (nova restrição da **sucessora** `d4e5f6a7b8c9`) | ~86 testes (172 ocorrências no traceback) | `test_turma_curso*.py` (fase2, fase4, edicao, exclusao, lista, dash), `test_enturmacao_oferta.py` (helper `_turma`), `test_bi_turma_desativada.py` (8 ERROR de fixture), `test_security_regressions.py`, `test_pauta_professor.py`, `test_bi_indicadores.py`, `test_turma_curso.py` |
| `ValueError: Toda oferta precisa ter um programa.` — mesmos programas faltando, agora barrados pelos validadores do serviço (`criar_oferta_inicial_da_turma` L285, `adicionar_oferta` L330, `editar_oferta` L417) | 20 | `test_turma_curso_fase2/fase3/fase4.py` |
| `IntegrityError: NOT NULL constraint failed: inscricoes.turma_curso_id` — sementes NULL/omitidas da **c3d4e5f6a7b8** | 16 | `test_enturmacao_oferta.py` (via `_null_ativa`), `test_turma_curso_fase4.py` (:90/:682), `test_bi_indicadores.py`, `test_aluno_status.py`, `test_pauta_professor.py`, `test_security_regressions.py` |
| 2 preexistentes de `/cursos` | 2 | `test_security_regressions.py` |
| Casos isolados: `assert None is not None`, `KeyError: 2026`, `AttributeError: 'NoneType'...`, asserts de conteúdo de HTML (`'adicionado à turma'`, `'curso principal'`, `'já é ofertado'`), `assert 200 == 400`, `assert 200 == 403` | ~7 | `test_filtros_turmas.py` (KeyError 2026 — independente das migrations), `test_turma_curso_lista.py`, `test_turma_curso_fase3/fase4.py` — em geral cascata de semente que não gravou |

Conclusão do passo 4: a causa dominante **não é a c3d4 em si** (16 testes), e sim a
sucessora d4e5f6a7b8c9 (`programa` obrigatório na oferta), que as sementes de teste
não preenchem. A correção é dar `programa` às sementes de `TurmaCurso` e oferta às
sementes de `Inscricao` — trabalho de testes, não de código de produção.

## 5. Simulação `transferir_aluno` em SQLite `:memory:` (executada; nunca tocou o PostgreSQL)

Rota real chamada via `test_client` (usuário `pedagogico`), cenário com turma de
origem (1 oferta) e destinos com 1 e 2 ofertas:

| Cenário | Resultado |
|---|---|
| A) destino com **1 oferta** | POST → 302; inscrição da origem ficou inativa e a ativa passou a `turma=2 oferta=2`. **Sem IntegrityError.** |
| B) destino com **2 ofertas** (escolhida a 2ª via `turma_curso_id_destino`) | POST → 302; ativa em `turma=3 oferta=4`. **Sem IntegrityError.** |
| C) INSERT direto de `Inscricao` com `turma_curso_id=NULL` (comportamento legado da transferência antiga) | `IntegrityError: NOT NULL constraint failed: inscricoes.turma_curso_id` — exatamente a regressão que a c3d4 previne. |

Achados colaterais da simulação:

- O `transferir_aluno` **atual já cumpre** a restrição (resolve e exige a oferta de
  destino) — a pendência "transferência fica NULL" registrada nos relatórios M1/M1.1
  foi resolvida por outra mão entre as sessões.
- Ao criar a 2ª oferta da turma a simulação esbarrou no índice único parcial
  `uix_turma_curso_principal` (marcava `principal=True` nas duas) — comportamento
  esperado do schema; corrigido na própria simulação.
- **Nenhum teste no repositório cobre `transferir_aluno`** (grep
  `transferir_aluno|turma_curso_id_destino` em `tests/` = 0 ocorrências). A rota é
  justamente a que mais interage com a nova restrição.

## 6. Decisões que tomei sozinho

- Reportei o head real da cadeia (`d4e5f6a7b8c9`), não apenas a c3d4, porque "estado
  pós-migration" sem a sucessora daria quadro errado — e foi a sucessora que dominou
  as falhas da suíte.
- Nos SELECTs usei `ativo IS TRUE` / `NOT ativo` (compatível com os dois dialects) em
  vez de `= true`, e chequei o schema físico (`information_schema`, `pg_indexes`) além
  dos dados, para provar que a migration foi aplicada de fato e não apenas registrada.
- Separei as causas da suíte por mensagem de exceção (contagem de ocorrências no
  log) em vez de listar 131 tracebacks; a lista completa fica reproduzível com
  `pytest -q` (o log temporário foi apagado por higiene de escopo).
- Na simulação, exercitei a **rota** (não uma chamada direta de função), para testar
  também as validações de origem/destino que hoje garantem o NOT NULL.

## 7. Pendências que vi (não corrigidas)

1. **Suíte quebrada (~131 resultados)**: sementes de `TurmaCurso` sem `programa`
   (d4e5f6a7b8c9) e sementes de `Inscricao` sem oferta (c3d4e5f6a7b8). É o único
   blocker real antes de qualquer novo commit.
2. **`test_enturmacao_oferta.py` desatualizado com o código atual**: os testes da
   adoção M1.1 (`test_adota_null_*`, `test_duplicata_recusada_apos_adocao`,
   `test_adicionar_oferta_vincula_null_ativas`, `test_zero_ofertas_recusa`) pressupõem
   inscrição NULL legada, que o schema agora proíbe; `enturmar_alunos` não adota mais
   NULL e `adicionar_oferta` não vincula NULLs (marcador `inscricoes_vinculadas` foi
   removido). São 16 testes que precisarão ser reescritos ou excluídos.
3. **Fallback `incluir_inscricoes_null` de `_alunos_da_oferta`** (e leituras legadas
   `turma_curso_id IS NULL` em `core.py`/`logica.py`) virou código morto defensivo com
   o NOT NULL — decidir remoção em etapa própria.
4. **Sem testes de `transferir_aluno`** — recomendação direta da seção 5 (pelo menos:
   destino 1 oferta, destino 2 ofertas, recusa de oferta inativa/de outra turma).
5. `test_filtros_turmas.py::test_rota_listagem_aplica_filtro_nome` falha com
   `KeyError: 2026` — parece independente das migrations (ano corrente vs dados de
   2026 nas sementes); investigar separadamente.
6. Em SQLite, rodar `flask db upgrade` com `batch_alter_table` pode colidir o índice
   parcial declarado no modelo com o `create_index` da migration (os testes só usam
   `create_all`, então ninguém exercita esse caminho).
7. Na sucessora `d4e5f6a7b8c9`, o `UPDATE turma SET programa = (subquery)` resulta
   NULL quando a turma não tem oferta ativa com programa — o NOT NULL é aplicado em
   `turma_curso`, mas `turma.programa` pode ser zerado em linhas assim; verificar se
   há turmas nesse estado em outros bancos (no local, a aplicação passou).

## 8. Linha de resumo do pytest

```
120 failed, 88 passed, 5 warnings, 11 errors in 105.86s
```

(inclui as 2 preexistentes de `/cursos`; as demais 129 falhas/erros são das sementes
incompatíveis com `c3d4e5f6a7b8` + `d4e5f6a7b8c9`, detalhadas no passo 4).
