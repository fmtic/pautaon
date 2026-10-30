# G1/P2 — Fechamento da obrigatoriedade do professor na oferta (E0–E5)

**Data:** 30/10/2026 · **Branch de trabalho:** `nova_feature` · **Destino:** `main` (local, sem push)
**Escopo:** fechar o item (3) do G1 (`turma_curso.professor_id` NOT NULL), o item (4) (links de impressão sem `turma_curso`) e a pendência de harness (`login_as`), com saneamento e conferência nos dois bancos.

---

## 1. Contexto da rodada (por que a E0 divergiu do plano)

O plano previa working tree com o rename "Diário de Observações" → "Diário de Bordo" e as ofertas 16/17/18 ainda presentes. O estado real era outro:

- O rename **já estava commitado** em `9652adc` (HEAD~5) — nada a fazer na E0.
- **E1 e E2 já estavam concluídos e aplicados** (commits `ee922c5`, `59880c3`, `3af4ee2`, `434c53f`; MER §8.23). As ofertas 16/17/18 **não existem** no principal nem no ensaio e `turma_curso.professor_id` já é `NOT NULL` nos dois bancos.
- Cinco arquivos do working tree estavam **revertidos para versões antigas** pela sincronização do Nextcloud (`app/models/academico.py` sem `TurmaCurso`, `MER.md`, `base.html`, `dashboard/index.html`, `painel_admin.html`). Restaurados do HEAD antes da E0 (backup em `.tmp/revert_bak/`), e `__pycache__`/`.pytest_cache` limpos.
- Decisão do usuário: **prosseguir com o delta** (E3/E4/E5 + relatório), documentando E1/E2 como já entregues.

---

## 2. Resultado por etapa

### E0 — Estado inicial e commit do working tree

- **HEAD de partida:** `434c53f` (branch `nova_feature`).
- **Suíte com o working tree como estava:** **1042 passed**, 0 falhas (5m50s). Os 1033 esperados + **9** testes novos de `tests/test_g1p2_links_impressao.py` (arquivo ainda não rastreado).
- **Commits (sem alterar conteúdo):**

| Hash | Assunto |
|---|---|
| `53d6f2e` | feat(g1p2): links de impressao sempre com turma_curso (G1-4) |
| `9ed074b` | style(ui): topbar de 56px na sidebar |
| `49aa982` | docs(readme): alinhamento das tabelas markdown |
| `d91969a` | chore(dev): fixa interpretador do .venv no VS Code |

- **Rename do Diário de Bordo:** já em `9652adc`; nenhum commit novo necessário.
- **Lixo não commitado (já coberto pelo `.gitignore`, nenhuma regra alterada):** `.env`, `.venv/`, `.qoder/`, `.ruff_cache/`, `.pytest_cache/`, `__pycache__/` (todos os níveis), `.tmp/`, `instance/backups/`, `instance/certs/`, `instance/error.log`, `instance/uploads/`, `app/static/uploads/`, `runtests copy.bat` e os temporários de raiz `tmpqeu1k0e6`, `tmprlhrxzr4`, `tmptcjkoxm_`, `tmpzm8mlkii`. Um deles estava **versionado** (`tmpfldc2ofh`, 0 byte, desde `5f3254c`) e foi removido em `484cbcf`.
- **Leitura SELECT (16/17/18):** inexistentes nos dois bancos → divergência reportada e E1/E2 não reexecutadas, conforme a regra de parada.

### E1 — Saneamento das ofertas 16, 17 e 18 (já aplicado em 29/10)

- **Ferramenta:** `scripts/remover_ofertas_sem_lancamento.py` com `--remover-lancamentos` (dry-run padrão, trava do principal por `--autorizar-principal`, backup, contagens antes/depois, remoção na ordem das FKs, só linhas com `turma_curso_id` em 16/17/18).
- **Backup:** `instance/backups/pautaon_pre_saneamento_ofertas_2.sql` (576 KB, 29/10 19:32).
- **Removido (principal):**

| Oferta | Turma | frequencia | inscrições |
|---|---|---|---|
| 16 | 12 | 5 | 2 |
| 17 | 12 | 2 | 2 |
| 18 | 13 | 2 | 1 |

- **Contagens antes → depois (principal):** `frequencia` 63 → 54 (−9); `inscricoes` 18 → 13 (−5); `turma_curso` 5 → 2 (−3). `registro_aula`, `conselho_classe`, `conselho_resposta` e `turma_curso_horario` sem vínculo (zero linhas).
- **Legado preservado (`turma_curso_id IS NULL`):** 2 linhas na turma 13 (principal) e 4 na turma 30 (ensaio) — intocadas.
- **Resíduo das turmas (SELECT de 30/10):** principal — turma 12 Alfa, 13 Gema e 14 Zeta ativas e **sem oferta ativa** (0 inscrições ativas; turma 13 mantém as 2 frequências legadas). Ensaio — turma 34 sem oferta ativa; turma 30 segue com 1 oferta ativa.
- **Conferência:** **zero** ofertas com `professor_id` NULL (ativas ou inativas) nos dois bancos.

### E2 — Migration NOT NULL em `turma_curso.professor_id` (já aplicada em 29/10)

- **Revisão:** `d6e7f8a9b0c1_notnull_professor_oferta_g1.py` — pré-checagem somente leitura com `RuntimeError` em português listando ids, idempotência por inspeção e downgrade para nullable.
- **Protocolo:** backup, upgrade, `\d` da coluna, downgrade, upgrade — primeiro no ensaio, depois no principal.
- **Estado em 30/10 (reconferido por SELECT):** `alembic_version = d6e7f8a9b0c1` e `information_schema.columns.is_nullable = NO` em **principal e ensaio**.
- **Efeito:** INSERT bruto sem professor passa a ser recusado pelo banco; coberto por `tests/test_notnull_professor_oferta.py` (3).
- **Docs:** MER §8.23 (coluna NOT NULL e efeito) e backlog com o item (3) do G1 fechado.

### E3 — G1-4: links de impressão sem `turma_curso`

- **`frequencia/lancar.html`:** o bloco de impressão passou a exigir `pode_imprimir_pauta and not exigir_escolha` — com 2+ ofertas e nenhum curso escolhido o botão e o dropdown **não aparecem** (nenhum link é publicado). Todo href publicado leva `turma_curso` quando existe oferta.
- **`turmas/detalhe.html`:** o professor só vê links das ofertas dele (cada um com `turma_curso`); a gestão com 2+ ofertas ativas vê um link por oferta; com **exatamente 1** oferta ativa mensal/completa passam `turma_curso`; com **0** vale o legado por turma (sem parâmetro). Nenhum link da tela cai em 403.
- **Testes:** `tests/test_g1p2_links_impressao.py` — 9 casos (1/2/0 ofertas nas duas telas, `exigir_escolha`, ausência de `turma_curso=None`).
- **Commits:** código em `53d6f2e` (E0); documentação em `a0a5926` (MER §8.14 e item (4) do G1 no backlog).
- **MER/backlog:** atualizados — item (4) marcado **RESOLVIDO**.

### E4 — Harness: login local → `login_as`

- **Motivo:** o fixture `app` mantém AppContext aberto; o `_login_user` cacheado em `flask.g` sobrevive e a troca de perfil na mesma função não vale. `tests/_helpers.py::login_as` limpa `g`, grava `_fresh` e o `unidade_id` condicional.
- **Migração:** **38 arquivos** e **50 blocos** que ainda atribuíam `session["_user_id"]` direto passaram a chamar `login_as(...)`; `_fresh` e o `if unidade_id is not None` viraram o próprio helper.
- **Exceção deliberada:** `tests/test_l4_2_harness_perfis.py` ficou intocado — o `_login_inline` dele **caracteriza** a armadilha (classe b da auditoria L4.2).
- **Restante em `tests/`:** apenas `_helpers.py` e o `_login_inline` acima.
- **Qualidade:** `ruff --select F821,F811,F841` limpo; **suíte 1042 passed** (mesmo total da E0), 5m51s.
- **Commit:** `d744693` (testes + MER §12.16 + backlog).
- **Arquivos migrados (38):** `test_bi_indicadores`, `test_bi_oferta`, `test_carga_horaria_curso`, `test_carga_horaria_oferta_variavel`, `test_conselho_oferta`, `test_d3b2_2_listagem_caracterizacao`, `test_d3b2_2_n1_freq_geral`, `test_d3b2_3_n1_historico`, `test_d3b2_4_estatisticas`, `test_dashboard`, `test_dashboard_professor_pedagogico`, `test_desativar_oferta`, `test_desenturmacao_oferta`, `test_enturmacao_oferta`, `test_filtros_turmas`, `test_g1_p2_professor_oferta`, `test_h4_leitores_grade_variavel_smoke`, `test_i1_guardas_por_oferta`, `test_impressao_grade_oferta`, `test_isolamento_unidade_escrita`, `test_l4_1_reativacao_ofertas`, `test_l4_2_programa_reativacao`, `test_l4_lixeira`, `test_leitores_grade_h3e`, `test_leituras_residuais_grade_h3f`, `test_maintenance`, `test_pauta_professor`, `test_sec01_uploads`, `test_security_regressions` (10 blocos), `test_transferencia_oferta`, `test_turma_curso_edicao`, `test_turma_curso_exclusao`, `test_turma_curso_fase2`, `test_turma_curso_fase3`, `test_turma_curso_fase4`, `test_turma_curso_horario_escritores`, `test_turma_curso_lista`, `test_ui_grade_por_dia`.

### E5 — Merge local em `main` (sem push)

- **Gate:** working tree limpo (E4 commitada) e suíte verde (1042).
- **`nova_feature` ← `main`:** `a24574b` — merge sem conflito e **sem mudança de conteúdo** (`git diff d744693 a24574b` vazio; os 2 commits exclusivos de `main` eram merges da `Onda4`, já contidos na árvore).
- **`main` ← `nova_feature`:** `37b2042` (`--no-ff`), árvore idêntica a `nova_feature` (`git diff nova_feature HEAD` vazio).
- **Higiene:** `484cbcf` remove `tmpfldc2ofh` (arquivo vazio versionado por engano).
- **Sem push:** `origin/main` e `origin/nova_feature` intocados.

---

## 3. Conferência de banco (30/10/2026, somente SELECT)

| Item | principal | ensaio |
|---|---|---|
| `alembic_version` | `d6e7f8a9b0c1` | `d6e7f8a9b0c1` |
| `turma_curso.professor_id` `is_nullable` | `NO` | `NO` |
| Ofertas com `professor_id` NULL | 0 | 0 |
| `turma_curso` (total) | 2 | 11 |
| Ofertas 16/17/18 | inexistentes | inexistentes |
| Turmas ativas sem oferta ativa | 12, 13, 14 | 34 |
| `frequencia` legada (`turma_curso_id` NULL) preservada | 2 (turma 13) | 4 (turma 30) |

---

## 4. Pendências restantes

1. **Autor em `frequencia`** — a tabela não guarda quem lançou; `registro_aula.instrutor_id` é sobrescrito a cada salvamento e `conselho_resposta` não tem autor nem `turma_curso_id`. Registrado no T0-b; sem decisão de produto.
2. **Medicação na pauta** — decisão **institucional** de conteúdo (se o professor da oferta deve ver "medicação regular"); nada mudou no comportamento.
3. **F401 globais** — **89** ocorrências hoje (82 corrigíveis por `--fix`), majoritariamente re-exports de `app/models/__init__.py` e scripts; o número subiu de 87 porque a suíte ganhou arquivos desde a medição anterior (inclui o novo `test_g1p2_links_impressao.py`).
4. **Harness (resíduos do §12.16)** — falta o `tests/conftest.py` único e trocar os asserts de 200 do teste do H4 por uma rota restrita, para que a identidade seja discriminadora.

---

## 5. Hashes da rodada

```
E0  53d6f2e  feat(g1p2): links de impressao sempre com turma_curso (G1-4)
E0  9ed074b  style(ui): topbar de 56px na sidebar
E0  49aa982  docs(readme): alinhamento das tabelas markdown
E0  d91969a  chore(dev): fixa interpretador do .venv no VS Code
E3  a0a5926  docs(g1-4): links de impressao com oferta explicita em MER e backlog
E4  d744693  test(harness): migra login local para login_as em 38 arquivos (E4)
E5  a24574b  merge(e5): atualiza nova_feature com main (sem mudanca de conteudo)
E5  37b2042  merge(g1p2): fechamento E0-E5 (NOT NULL, G1-4 links, harness login_as)
E5  484cbcf  chore(higiene): remove tmpfldc2ofh vazio versionado por engano
```

**Pré-existentes (E1/E2, 29/10):** `ee922c5`, `59880c3`, `3af4ee2`, `434c53f`.
