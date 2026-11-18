# AJ22 — Próximo Curso + Nível no fechamento do conselho

**Data:** 17/11/2026 · **Branch:** `nova_feature` · **Migration:** `a7b8c9d0e1f2` (head do código; **pendente de deploy** — produção em `1fdc7c03bdc2`)

> **AJ22-B (17/11/2026) — substitui integralmente a versão inicial deste relatório.** O AJ22 original nunca chegou à produção; a migration `a7b8c9d0e1f2` foi **reescrita no mesmo id/arquivo** (`down_revision = 1fdc7c03bdc2`). O "próximo curso" agora é um **`Curso` já cadastrado** (`conselho_classe.proximo_curso_id`), não mais o catálogo paralelo `opcao_proxima_turma`. `opcao_proxima_turma`/`proxima_turma_id` ficam **LEGADOS** (sem UI, sem novas escritas; só fallback de leitura) e `opcao_proxima_turma.programa` **não existe**. O programa passa a ser `curso.programa`; `nivel.programa` e a unicidade funcional permanecem. A aba "Próximos Cursos" e as rotas `editar_programa_proxima_opcao`/`inativar_proxima_opcao` foram removidas (404). As seções abaixo descrevem a versão inicial e ficam como histórico; **prevalecem** o addendum, o MER (§7.4/§7.5/§7.23/§7.24/§8.2) e o SQL de deploy deste bloco.

## AJ22-B — o que mudou em relação à versão inicial

- **E1:** `conselho_classe.proximo_curso_id` int NULL, FK → `curso.id` `ON DELETE RESTRICT`. Só entram cursos ATIVOS da unidade da turma; curso já gravado que ficou inativo é aceito **inalterado** e exibido com "(inativo)".
- **E2:** `curso.programa` varchar(50) NULL (lista `PROGRAMAS_CURSO`), editável no modal de Cursos do planejamento com os mesmos perfis/isolamento de `editar_curso`; sem backfill; `turma_curso.programa` intocado. Curso sem programa → somente "Não se aplica".
- **E3:** mantidos `nivel.programa`, unicidade funcional `(nome, unidade_id, COALESCE(programa,''))` com guarda D8, `proximo_nivel_id`, regras de elegibilidade, UI de nível e "Níveis sem programa".
- **E4:** `opcao_proxima_turma` e `proxima_turma_id` legados (sem drop). Sem aba/rotas de "Próximos Cursos". Leitores exibem curso + nível; fallback legado mostra só o nome da opção (sem nível) quando `proximo_curso_id` é NULL. Dívida de remoção registrada no backlog.
- **E5:** rótulos "Próximo Curso"/"Nível"; nomes de rota/endpoint preservados quando não removidos.
- **Leitores atualizados:** resultado do conselho, ficha 360°, resumo do conselho e painel pedagógico, todos em lote (sem N+1).
- **Arquivos-chave:** `app/services/proximo_curso.py` (`cursos_da_unidade`, `curso_da_escolha`, `programa_do_curso`, `destinos_por_conselho`), `app/conselho.py` (GET/POST do fechamento e resumo), `app/registros/core.py` (modal de cursos + remoção do legado), `app/static/js/conselho/conselho.js`, `app/static/js/planejamento/planejamento.js`, templates de fechamento/planejamento/ficha/resumo/painel, MER e `tests/test_aj22_proximo_curso_nivel.py`.

## AJ22-B — SQL de verificação pós-deploy (PostgreSQL)

```sql
-- colunas novas (esperado: curso.programa, nivel.programa,
-- conselho_classe.proximo_curso_id e proximo_nivel_id)
SELECT table_name, column_name, data_type, is_nullable
  FROM information_schema.columns
 WHERE (table_name = 'curso'    AND column_name = 'programa')
    OR (table_name = 'nivel'    AND column_name = 'programa')
    OR (table_name = 'conselho_classe'
        AND column_name IN ('proximo_curso_id','proximo_nivel_id'))
 ORDER BY table_name, column_name;

-- opcao_proxima_turma NÃO deve ter a coluna programa (0 linhas)
SELECT column_name FROM information_schema.columns
 WHERE table_name = 'opcao_proxima_turma' AND column_name = 'programa';

-- unicidade funcional do nível ativa e constraint antiga ausente
SELECT indexname, indexdef FROM pg_indexes
 WHERE tablename = 'nivel' AND indexname = 'uq_nivel_nome_unidade_programa';
SELECT conname FROM pg_constraint
 WHERE conrelid = 'nivel'::regclass AND conname = 'uq_nivel_nome_unidade';

-- FKs do fechamento (curso e nível, ON DELETE RESTRICT)
SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
 WHERE conrelid = 'conselho_classe'::regclass AND contype = 'f'
   AND (pg_get_constraintdef(oid) ILIKE '%curso%'
        OR pg_get_constraintdef(oid) ILIKE '%nivel%');

-- sanidade (esperado: sem backfill; tudo NULL)
SELECT COUNT(*) FROM curso           WHERE programa IS NOT NULL;
SELECT COUNT(*) FROM nivel           WHERE programa IS NOT NULL;
SELECT COUNT(*) FROM conselho_classe WHERE proximo_curso_id IS NOT NULL;
SELECT COUNT(*) FROM conselho_classe WHERE proximo_nivel_id IS NOT NULL;
```

**Downgrade:** `flask db downgrade -1` remove as FKs/colunas novas, `nivel.programa`, `curso.programa` e o índice funcional, recriando `uq_nivel_nome_unidade`. A guarda D8 recusa se houver duplicata de `(nome, unidade_id)` entre programas — renomear antes. Nada é migrado de/para `opcao_proxima_turma`.

## AJ22-B — Verificação

- Suíte completa: **1852 passed, 0 failed** (base 1846 + 6 testes novos; o arquivo AJ22 tem **38 testes**).
- Rodada com `git` no PATH: `tests/test_forcar_troca_contas_expostas.py` executa `git init` em subprocesso.
- `ruff --select F821,F811,F841` limpo nos arquivos Python tocados;
- `git diff --check` limpo.

## Objetivo

O fechamento do conselho passa a registrar, por aluno da oferta, o **próximo
curso** (catálogo `opcao_proxima_turma`, antes rotulado "Próxima Turma") e um
**nível de destino** (`nivel`) condicionado ao programa do curso escolhido.

## Etapa 0 — leitura (mapeamento)

1. **Leitores/escritores de `proxima_turma_id`/`OpcaoProximaTurma`:**
   - Escrita: `salvar_fechamento_data` (`app/conselho.py`) — único escritor.
   - Leitores: `relatorios/conselho.py` (resultado do conselho, coluna
     "Próxima Turma"), tela `conselho/fechamento.html` (select do catálogo),
     `conselho_lancamento`/painel (só contagens, sem exibir o valor).
   - **Não havia UI de cadastro** de `OpcaoProximaTurma` — o catálogo só era
     semeado por script; o AJ22 criou a aba "Próximos Cursos" no planejamento.
   - `Nivel`: cadastro em `registros/core.py` (planejamento, aba "niveis");
     leitores em `registros/turmas.py` (select de nível da turma/oferta) e
     `app/services/proximo_curso.py` (novo, AJ22).
   - `Inscricao.nivel` é texto e **não** foi tocado (D6).
2. **Cadastros:** níveis — POST `tipo_post='nivel'` + rotas
   `editar_nivel`/`inativar_nivel` (admin/pedagógico/secretaria, isolamento
   por unidade via `assert_unidade_context`); exclusão é **lógica**
   (`ativo=False`), sem delete físico — nível em uso nunca é apagado.
   Opções de próximo curso não tinham tela (ver acima).
3. **`salvar_fechamento_data`:** JSON `{oferta_id, dados[]}` com CSRF via
   meta token; política de oferta 0/1/2+ (`_resolver_oferta_conselho`);
   professor → 403; validação de `situacao` antes de mutar (atômica);
   `get_or_create_conselho` com savepoint (AJ20); grava
   `situacao_final`/`proxima_turma_id`/`concluido`/`data_fim`.
4. **Programas hardcoded:** `_PROGRAMAS_OFERTA` em
   `app/registros/turmas.py` (select de `turma_curso.programa`) e
   `ofertas.html`/`listar.html`. O AJ22 criou a lista central
   `PROGRAMAS_CURSO` em `app/services/proximo_curso.py`, reutilizada **apenas
   pelos novos selects** (opção de próximo curso e nível) — o restante não
   foi refatorado, por decisão.

## Decisões implementadas (D1–D8)

- **D1:** programa na própria opção (`opcao_proxima_turma.programa`).
- **D2:** `nivel.programa` NULL (legado) nunca aparece no fechamento; sem
  backfill; a tela lista "Níveis sem programa" no topo da aba.
- **D3:** `conselho_classe.proximo_nivel_id` FK → `nivel` RESTRICT, NULL =
  "Não se aplica"; vínculo por referência; inativado depois da escolha
  continua visível na edição com "(inativo)" e é aceito **inalterado**.
- **D4:** "programa com níveis" derivado (≥1 nível ativo da unidade da
  turma com o programa).
- **D5:** campo Programa da opção de próximo curso editável **só por admin**
  (rota dedicada devolve 403 aos demais; criação ignora o campo).
- **D6:** `Inscricao.nivel` intocado.
- **D7:** nomes de coluna/rota/endpoint preservados; só rótulos.
- **D8:** unicidade funcional `(nome, unidade_id, COALESCE(programa,''))`;
  downgrade com guarda que recusa duplicatas de (nome, unidade).

## Arquivos

- `migrations/versions/a7b8c9d0e1f2_aj22_proximo_curso_nivel.py` — aditiva,
  idempotente por inspeção; SQLite (testes) e PostgreSQL cobertos; guarda D8.
- `app/models/pedagogico.py` (`Nivel.programa` + índice funcional),
  `app/models/conselho.py` (`OpcaoProximaTurma.programa`,
  `ConselhoClasse.proximo_nivel_id` + `proximo_nivel_obj`).
- `app/services/proximo_curso.py` — `PROGRAMAS_CURSO`, `niveis_por_programa`,
  `programa_tem_niveis`, `nivel_elegivel`, `nivel_compativel`,
  `opcao_da_escolha`.
- `app/conselho.py` — GET do fechamento pré-seleciona o conselho gravado e
  embute `niveis_programa`/`opcao_programas`; POST valida nível
  atomicamente (exceção "inalterado" avaliada antes de "programa sem
  níveis").
- `app/templates/conselho/fechamento.html` + `app/static/js/conselho/
  conselho.js` — coluna Nível, "Não se aplica", habilitação por programa,
  spans de impressão, `proximo_nivel_id` no payload.
- `app/registros/core.py` + `app/templates/planejamento/planejamento.html` —
  aba "Próximos Cursos", programa no cadastro de níveis, rotas
  `editar_programa_proxima_opcao` (admin) e `inativar_proxima_opcao`.
- `app/relatorios/conselho.py` + `resultado_conselho.html` — "Próximo
  curso / Nível" em lote.
- `tests/test_aj22_proximo_curso_nivel.py` — 32 testes; ajuste pontual em
  `tests/test_aj21_resumo_conselho.py` (CSS externalizado em `b77b72d`).

## Riscos e observações

- **Ordem da exceção:** o valor já gravado inalterado é aceito mesmo com o
  nível inativo **e** mesmo que o programa fique sem níveis ativos — é a
  leitura literal de D3 (histórico preservado); valores novos/alterados
  seguem as recusas completas.
- **Unidade do nível:** elegível = `unidade_id` da turma **ou** global
  (`NULL`), mesmo critério dos demais leitores de nível do codebase.
- **SQLite:** a FK de `proximo_nivel_id` e a troca da unicidade por
  reconstrução de tabela só se aplicam ao dialeto de produção (PostgreSQL)
  no caminho real; no SQLite dos testes o schema nasce de `create_all`.
- Produção não tem conselhos respondidos (só cascas) — nenhum dado existente
  muda de sentido; `proximo_nivel_id` nasce NULL em todas as linhas.

## Protocolo de deploy da migration (PostgreSQL)

1. **Backup:** `pg_dump -Fc pautaon > pautaon_pre_aj22_$(date +%Y%m%d_%H%M).dump`
   (ou o procedimento de backup usual do projeto).
2. **Ensaio primeiro** (se houver banco de ensaio): `flask db upgrade` →
   conferir head `a7b8c9d0e1f2` → `\d opcao_proxima_turma`, `\d nivel`,
   `\d conselho_classe` → `flask db downgrade -1` (deve passar; falha só se
   houver duplicata de nome+unidade entre programas — guarda D8) →
   `flask db upgrade` de novo.
3. **Produção:** deploy do código + `flask db upgrade`; conferir
   `flask db heads` = `a7b8c9d0e1f2` e `alembic_version`.
4. **Verificação pós-deploy:**

```sql
-- colunas novas presentes
SELECT column_name FROM information_schema.columns
 WHERE table_name IN ('opcao_proxima_turma','nivel','conselho_classe')
   AND column_name IN ('programa','proximo_nivel_id');
-- 3 linhas: programa (2 tabelas) + proximo_nivel_id

-- unicidade funcional ativa
SELECT indexname, indexdef FROM pg_indexes
 WHERE tablename='nivel' AND indexname='uq_nivel_nome_unidade_programa';
-- constraint antiga ausente
SELECT conname FROM pg_constraint
 WHERE conrelid='nivel'::regclass AND conname='uq_nivel_nome_unidade';
-- FK do nível
SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
 WHERE conrelid='conselho_classe'::regclass AND contype='f'
   AND pg_get_constraintdef(oid) ILIKE '%nivel%';

-- sanidade de dados (esperado: tudo NULL/vazio)
SELECT COUNT(*) FROM opcao_proxima_turma WHERE programa IS NOT NULL;
SELECT COUNT(*) FROM nivel WHERE programa IS NOT NULL;
SELECT COUNT(*) FROM conselho_classe WHERE proximo_nivel_id IS NOT NULL;
```

5. **Rollback:** `flask db downgrade -1` (remove só o que a migration
   criou; a guarda D8 pode recusar se já existirem níveis duplicados por
   programa — nesse caso renomear antes).

## Verificação (versão inicial, histórica)
- `tests/test_aj22_proximo_curso_nivel.py`: **32 passed**.
- Direcionados conselho/AJ19/AJ20/AJ21/AJ7/oferta/UI: **178 + 94 passed**
  (duas rodadas de verificação direcionada).
- Suíte completa: **1846 passed, 0 failed** (base 1814 + 32 novos).
- `ruff --select F821,F811,F841` limpo nos arquivos tocados;
  `git diff --check` limpo.
- Ajuste fora do escopo: `tests/test_aj21_resumo_conselho.py` passou a
  conferir `white-space: pre-line` no CSS externalizado
  (`css/conselho/resumo_conselho.css`), porque o commit `b77b72d` separou o
  CSS do HTML depois do AJ21-B.
