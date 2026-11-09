# AJ16-B — Valor do Esportista passa a pertencer à AULA

**Data:** 09/11/2026
**Tipo:** implementação (código, migration, testes, docs)
**Base:** `docs/Relatórios/AJ16A_ValorEsportista.md` (auditoria somente leitura)
**Worktree:** `aj16b-valor-aula` a partir de `nova_feature` (`0e14fef`), sem push
**Head anterior:** `c1d2e3f4a5b6` — **Head novo:** `f2a3b4c5d6e7`

---

## 1. Resumo executivo

O valor/postura do esportista deixou de ser um FK **por aluno** em `frequencia.valor_esportista_id` e passou a ser um **conjunto da aula** (oferta + data), em N:N com `registro_aula` (`registro_aula_valor_esportista`), no mesmo molde dos temas. A migration `f2a3b4c5d6e7` é **atômica**: cria a tabela, roda guardas, faz backfill, verifica e remove a coluna antiga em uma única transação.

**Decisão de produto aceita:** a migração **não preserva o vínculo aluno↔valor**. O dado antigo era por aluno e o novo é por aula; a informação de qual aluno recebeu qual valor é **perdida**. O downgrade recria a coluna mas a deixa vazia (NULL).

---

## 2. Contagens (sem dado pessoal)

### 2.1 `pautaon` local (pós-A1, revisão `c1d2e3f4a5b6`)

| Consulta | Antes | Depois |
|---|---:|---:|
| linhas de `frequencia` | 77 | 77 |
| linhas com `valor_esportista_id` | 54 | 54 |
| pares `(turma_curso_id, data)` com valor | 6 | 6 |
| linhas em `valor_esportista` | 8 | 8 |
| `registro_aula` | 7 | 7 |

> A migration **não foi aplicada** em `pautaon` (responsável aplica). As contagens são idênticas antes e depois do trabalho AJ16-B, confirmando leitura exclusiva.

Distribuição de valores distintos por par (do AJ16-A): 3, 4, 5, 5, 7, 7.

### 2.2 `pautaon_ensaio`

| Consulta | Antes | Depois |
|---|---:|---:|
| linhas de `frequencia` | 20 | 20 |
| linhas com valor | 0 | 0 |
| pares com valor | 0 | 0 |
| `valor_esportista` | 0 | 0 |
| `registro_aula` | 4 | 4 |

### 2.3 Clone de produção (`pautaon_aj16b_clone`)

Dump: `instance/backups/pautaon_producao_2026-11-03.dump` (revisão `c4d5e6f7a8b9`, pré-A1).

| Etapa | Resultado |
|---|---|
| Restore do dump | 130 `frequencia`, 10 `registro_aula`, 0 valores |
| Upgrade até `c1d2e3f4a5b6` | Sucesso (24 revisões aplicadas) |
| Apply `f2a3b4c5d6e7` (sem dados) | Sucesso, **0 vínculos**, coluna removida |
| Downgrade | Coluna recriada, tabela removida, versão volta a `c1d2e3f4a5b6` |

### 2.4 Dados sintéticos no clone (sem dados pessoais)

6 pares `(turma_curso_id, data)` com 3, 4, 5, 5, 7, 7 valores distintos (31 vínculos):

| Par | Data | Valores | Vínculos esperados |
|---:|---|---:|---:|
| 1 | 2026-10-01 | 3 | 3 |
| 2 | 2026-10-02 | 4 | 4 |
| 3 | 2026-10-03 | 5 | 5 |
| 4 | 2026-10-04 | 5 | 5 |
| 5 | 2026-10-05 | 7 | 7 |
| 6 | 2026-10-06 | 7 | 7 |
| **Total** | | | **31** |

| Etapa | Resultado |
|---|---|
| Apply `f2a3b4c5d6e7` (com dados sintéticos) | Sucesso, **31 vínculos** |
| Verificação interna (EXCEPT) | **0/0** (antigo = novo) |
| Detalhe por par | 3, 4, 5, 5, 7, 7 — coincide com o inserido |

### 2.5 Guarda sem diário

Inserido um par `(turma_curso_id=1, data=2026-10-20)` com valor mas **sem** `registro_aula`:

| Etapa | Resultado |
|---|---|
| Apply `f2a3b4c5d6e7` | **Aborta**: "há 1 linha(s) de frequencia com valor em par sem registro_aula correspondente" |
| Coluna antiga existe? | Sim (nada alterado) |
| Tabela nova existe? | Não (nada alterado) |
| Versão Alembic | `c1d2e3f4a5b6` (não avançou) |

### 2.6 Limpeza

- `pautaon_aj16b_clone`: **removido** (confirmado `count(*) = 0` em `pg_database`).
- `pautaon` e `pautaon_ensaio`: contagens idênticas antes e depois (tabela 2.1/2.2).

---

## 3. Suíte de testes

```
1660 passed, 0 failed, 0 skipped, 965 warnings in 1067.96s
```

Testes reescritos para o contrato por aula:
- `test_valor_esportista_lancamento` — persistência, substituição do conjunto, inativo já vinculado, rejeições, duas ofertas, estatísticas
- `test_valor_obrigatorio` — regra de aula (A–D na pauta + catálogo ativo ⇒ ≥1 valor), F/J/sem conceito não exigem, mensagem, nada gravado em pendência
- `test_valor_obrigatorio_ui` — validação JS do grupo da aula, funções puras (`aulaTemPresenca`, `valorAulaPendente`)
- `test_valor_obrigatorio_caracterizacao` — antigo (por aluno) × novo (por aula)
- `test_v3b_engajamento_turma` — fonte N:N, ordenação, empate, percentual, D2, inativo
- `test_lancar_template_estrutura` — contexto fake (`valores_aula`)

Testes ajustados:
- `test_valor_esportista_nao_regressao` — preparo dos dados pelo novo modelo
- `test_valor_esportista_migration` — reescrito com schema pré-AJ16-B montado à mão

Novos testes:
- Migration com dados: `test_upgrade_move_n_valores_para_a_aula` (parametrizado 3 e 7)
- Deduplicação: `test_upgrade_deduplica_valores_do_mesmo_par`
- Diário duplicado: `test_backfill_escolhe_o_diario_canonico_min_id`
- Guardas: `test_guarda_aborta_com_valor_sem_oferta_e_nada_muda`, `test_guarda_aborta_sem_registro_aula_e_nada_muda`
- Idempotência do backfill: `test_backfill_e_idempotente`
- Verificação interna: `test_verificacao_interna_aborta_quando_conjuntos_divergem`
- Downgrade: `test_downgrade_recria_coluna_vazia_e_remove_a_tabela`, `test_docstring_avisa_que_downgrade_nao_restaura_vinculo`
- DDL PostgreSQL: `test_ddl_postgres_cria_tabela_com_pk_fks_e_indice`, `test_ddl_postgres_dropa_indice_fk_e_coluna_antiga`, `test_ddl_postgres_downgrade_recria_coluna_fk_e_indice`, `test_ddl_postgres_downgrade_dropa_tabela_nova`
- N+1 da pauta constante: `test_n1_pauta_constante_com_valores` (2 vs 10 alunos, query count igual)
- Autor F1 não muda ao alterar só os valores: `test_alterar_sozinho_os_valores_nao_troca_autor`

---

## 4. Arquivos alterados

| Arquivo | Mudança |
|---|---|
| `app/models/aulas.py` | Tabela `registro_aula_valor_esportista` + relação `RegistroAula.valores` (selectin); removidos `Frequencia.valor_esportista_id` e `.valor_esportista` |
| `app/models/pedagogico.py` | Docstring: valor deixa de ser "por aluno" |
| `app/models/__init__.py` | Exporta `registro_aula_valor_esportista` |
| `app/utils/logica.py` | `carregar_frequencias_e_valores` devolve a lista da aula; `salvar_frequencia` com parse de `valor_ids`, validação e `registro.valores = ...`; removidos `_resolver_valor_esportista` e `_planejar_frequencia` por aluno |
| `app/registros/core.py` | POST e GET: `valor_ids` da aula, `valores_aula`/`valores_aula_ids`/`valores_aula_inativos` |
| `app/templates/frequencia/lancar.html` | Grupo único de checkboxes junto dos temas; removido select por aluno |
| `app/static/js/frequencia.js` | Validação do grupo da aula; removida lógica por aluno |
| `app/services/engajamento_turma.py` | Fonte N:N (`registro_aula_valor_esportista`) em vez de `Frequencia.valor_esportista_id` |
| `app/templates/dashboard/painel_pedagogico.html` | Rótulo/rodapé: "valores registrados em aulas" |
| `app/models/MER.md` | §7.19, §7.20, §7.20.2 (nova), §8.1, §8.13, tabela de migrations e head |
| `backlog_desenvolvimento.md` | Entrada AJ16-B + decisão de perda do vínculo aluno↔valor |
| `migrations/versions/f2a3b4c5d6e7_valor_esportista_na_aula.py` | Migration atômica (nova) |
| `tests/_valor_aula.py` | Helpers de teste compartilhados (novo) |
| `tests/test_valor_esportista_lancamento.py` | Reescrito |
| `tests/test_valor_obrigatorio.py` | Reescrito |
| `tests/test_valor_obrigatorio_ui.py` | Reescrito |
| `tests/test_valor_obrigatorio_caracterizacao.py` | Reescrito |
| `tests/test_v3b_engajamento_turma.py` | Reescrito |
| `tests/test_lancar_template_estrutura.py` | Ajustado |
| `tests/test_valor_esportista_nao_regressao.py` | Ajustado |
| `tests/test_valor_esportista_migration.py` | Reescrito |
| `tests/test_f1_autor_lancamento.py` | Novo teste de valor sem troca de autor |
| `tests/test_d3b2_4_estatisticas.py` | Novo teste de N+1 constante com valores |

---

## 5. Commits

Worktree `aj16b-valor-aula` a partir de `nova_feature` (`0e14fef`), sem push.

| Hash | Mensagem |
|---|---|
| `5814f81` | AJ16-B: modelo e migration do valor do esportista na aula |
| `fd86b0c` | AJ16-B: aplicação — valor do esportista por aula |
| `89e8385` | AJ16-B: testes reescritos para o contrato por aula + novos testes |
| `1da3ab2` | AJ16-B: docs — MER, backlog e relatório |

---

## 6. Conclusão

A migração foi validada em clone de produção: o upgrade com 0 valores sucede e produz 0 vínculos; o downgrade recria a coluna vazia; dados sintéticos com 31 vínculos (6 pares, 3–7 valores) são backfillados corretamente com verificação 0/0; a guarda aborta sem alterar nada quando há par sem diário. A suíte final tem 1660 passed, 0 failed, 0 skipped.
