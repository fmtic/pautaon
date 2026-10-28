# L4.1 — Reativação só das ofertas desativadas junto com a turma

**Branch:** `nova_feature` · **HEAD Alembic:** `8d2e3f4a5b6c` (inalterado) · **Suíte:** 693 → **712 passed** · **Data:** 27/10/2026

Sem migration. Sem push. Commits: `5c57fc1` (caracterização P2), `00b792b` (regra + rotas + template), `be97a6b` (testes P4 + ensaio P5), docs (este relatório, MER §8.10, backlog).

---

## 1. Problema

`reativar_turma` (L4, `7a7edd0`) reativa **todas** as ofertas inativas da turma, presumindo que todas foram desativadas pela exclusão lógica. Falso quando uma oferta já tinha saído do curso **antes** (`desativar_oferta`, rota `turma_oferta_desativar`): ela era ressuscitada contra a intenção do operador e o conjunto final podia violar `uix_turma_curso_principal` / a regra "2+ ativas ⇒ exatamente 1 principal".

O relatório do L4 (§P1) registrava justamente a premissa errada: "*sinal confiável: `turma.ativo=False` implica que todas as ofertas foram desativadas pela exclusão lógica*" — `desativar_oferta` não toca a turma, mas a oferta desativada fica inativa dentro de uma turma depois excluída, e o L4 não distingue as duas origens.

## 2. P0 — pré-condição

`git status` limpo; suíte 693 passed; head alembic `8d2e3f4a5b6c`.

## 3. P1 — leitura e TRAVA (evidência)

Hipótese da tarefa: usar `updated_at` da oferta igual ao da turma na exclusão (mesma transação do `excluir_turma`).

Leitura do código:

- `app/models/auditoria_listener.py:57` — no `before_flush`, todo objeto em `session.new + session.dirty` que tenha `updated_by_id` recebe `obj.updated_at = db.func.now()`.
- `app/registros/turmas.py` (`excluir_turma`, ramo lógico) — percorre **todas** as ofertas da turma com `oferta.ativo = False`. Para a oferta que **já estava inativa** essa atribuição é no-op, mas ainda assim dispara o evento de atribuição: a oferta entra em `session.dirty` e o listener reescreve o seu `updated_at` com o timestamp da transação da exclusão.

Medição (`scripts/verificar_sinal_updated_at.py`, semente com A ativa e B **desativada antes** da exclusão; exclusão pela rota real `/turma/excluir/<id>` com histórico para forçar o ramo lógico):

PostgreSQL scratch (`pautaon_ensaio`):

```
antes:  turma=2026-10-27 19:50:42.039117  A=2026-10-27 19:50:42.039117  B=2026-10-27 19:50:42.279381
depois: turma.updated_at = 2026-10-27 19:50:42.290356
        A.updated_at     = 2026-10-27 19:50:42.290356
        B.updated_at     = 2026-10-27 19:50:42.290356   <- B estava INATIVA antes e foi reescrita
        igualdade turma==A: True      igualdade turma==B: True
        LogAcao da transação: Alterar Turma 1, Alterar TurmaCurso 3, Alterar Inscricao 1, ...
```

O timestamp de B (`.279381`, anterior à exclusão) foi **substituído** pelo da transação de exclusão, idêntico ao da turma e ao de A. Confirma também que `db.func.now()` devolve o **mesmo valor** em todas as linhas da transação (PostgreSQL `now()` = transaction timestamp).

SQLite (`:memory:`):

```
depois: turma == A == B == inscricao = 2026-10-27 22:50:33   (igualdade turma==B: True)
```

Aqui a granularidade de 1 s torna a comparação ainda mais inútil como discriminador.

**Conclusão:** `updated_at` **não discrimina** em nenhum dos dois bancos — a TRAVA do P1 foi acionada. As alternativas avaliadas: (a) parsear o `LogAcao` automático do listener → descartado, `detalhes` só guarda `repr(obj)`; (b) **registrar um marcador explícito no `excluir_turma`, sem coluna nova** → adotado.

**Decisão do operador (especificação adotada):** um `LogAcao` com `acao="Excluir turma (lógica)"` e `detalhes="turma_id=N ofertas=[ids] inscricoes=[ids]"`, gravado na mesma transação; `ofertas` lista **só as que estavam ativas**. É o único marcador; preview e reativação leem o **último** log da turma como pré-seleção; sem log → nada pré-marcado e a escolha explícita é obrigatória.

Nota de implementação: `services/auth_service.py::register_security_log` foi **descartado** para o marcador — ele faz `db.session.commit()` próprio (sairia da transação da exclusão) e trunca `detalhes` em 500 caracteres. O marcador usa `db.session.add(LogAcao(...))` direto, sem commit; `LogAcao.detalhes` é `Text` (sem limite).

## 4. P2 — caracterização (antes × depois)

Testes escritos contra o código **do L4** (commit `5c57fc1`), mesma semente do P1 (turma com A principal e B, B removida do curso antes da exclusão, depois `excluir_turma` lógico e reativação pela rota).

**Antes** (código do L4 restaurado temporariamente de `7a7edd0` para `app/services/turma_curso.py`, `app/registros/turmas.py`, `app/templates/turmas/turma_lixeira.html` e suíte executada):

```
FAILED test_p2_oferta_desativada_antes_da_exclusao_nao_reativada
  tests/test_l4_1_reativacao_ofertas.py:181: assert True is False   # B voltou ATIVA
FAILED test_p2_variante_principal_mudou_apos_remover_b
  tests/test_l4_1_reativacao_ofertas.py:207: assert False is True   # turma não voltou
2 failed
```

A variante é o pior efeito colateral: `definir_principal(A)` **não desmarca** B (inativa conserva `principal=True`, o índice parcial filtra `principal AND ativo`), então a reativação de *todas* as inativas coloca A+B ativas com **duas** marcas de principal e a regra recusa a operação inteira — a turma ficava presa na lixeira, sem conseguir reativar nem a oferta que estava ativa na exclusão.

**Depois:** os dois testes passam (B permanece inativa; A volta e é a única principal; a variante reativa só A).

## 5. P3 — implementação

- **Serviço** (`app/services/turma_curso.py`, seção L4/L4.1, linhas ~1075–1443): constantes `ACAO_EXCLUSAO_LOGICA_TURMA`/`MOTIVO_TURMA_DESATIVADA`; `formatar_marcador_exclusao`/`parsear_marcador_exclusao` (regex sobre `detalhes`); `gravar_marcador_exclusao` (sem commit); `marcador_exclusao_turma` (último marcador) e `marcadores_exclusao_em_lote`; núcleo único `_avaliar_reativacao` compartilhado por `preview_reativacao`/`previews_reativacao_em_lote` e `reativar_turma`; `_contexto_reativacao_em_lote` faz **5 SELECTs constantes** para N turmas.
- **Elegibilidade:** pré-seleção = interseção do marcador com as ofertas inativas da turma; `oferta_ids` da UI sobrepõe a pré-seleção (escolha explícita pode reincluir B, com aviso). Recusas (`ValueError`, **todas antes de qualquer mutação**): sem ≥1 oferta marcada; seleção com oferta que não é oferta inativa daquela turma; violação da regra do principal; período encerrado sem `confirmar_periodo=1`; sem marcador e sem escolha explícita.
- **Inscrições:** só as das ofertas efetivamente reativadas, com `motivo_desativacao == TURMA_DESATIVADA`, aluno ativo e sem inscrição ativa na mesma oferta. Transferências (`TRANSFERENCIA`), desenturmacão manual (`DESENTURMADO`) e outros motivos nunca são tocados; `Aluno.ativo` nunca muda.
- **Rotas** (`app/registros/turmas.py`): `excluir_turma` (ramo lógico) captura `ofertas_reativaveis` (só as ativas) + `inscricoes_desativadas` e chama `gravar_marcador_exclusao` **antes** do `db.session.commit()`; `turma_lixeira` passa a `select(...).options(joinedload(Turma.periodo_letivo)).unique()` + `previews_reativacao_em_lote` (sem as cargas redundantes do L4); `reativar_turma_route` lê `selecao_explicita`/`oferta_ids` e a flash final diz o que voltou, o que ficou inativo e por quê.
- **Template** (`app/templates/turmas/turma_lixeira.html`): uma linha por oferta inativa com checkbox `oferta_ids` (form por turma), badge "desativado na exclusão da turma" × "desativado antes / origem desconhecida", hidden `selecao_explicita=1`, aviso quando a turma não tem marcador e alerta quando a seleção violaria o principal.

## 6. P4 — testes

`tests/test_l4_1_reativacao_ofertas.py` — 15 funções / **19 casos**, todos verdes:

- P2: `test_p2_oferta_desativada_antes_da_exclusao_nao_reativada`, `test_p2_variante_principal_mudou_apos_remover_b`.
- Marcador: `grava_so_a_oferta_que_estava_ativa`; `preview_marca_somente_a_oferta_da_exclusao`; `turma_sem_marcador_exige_escolha_explicita`; `marcador_nao_altera_comportamento_do_excluir_turma` (física × lógica, inscrições, lançamentos); `reativar_duas_vezes_nao_duplica_marcador_de_exclusao`.
- Seleção: `escolha_explicita_pode_reincluir_oferta_removida_antes`; `sem_marca_nenhum_curso_recusa`; `oferta_de_outra_turma_na_selecao_recusada`.
- Inscrições: `inscricao_transferencia_e_desenturmada_nao_reativadas`; `aluno_inativo_permanece_inativo`.
- Principal: `principal_violado_recusa_tudo_sem_alteracao_parcial`.
- Histórico: `lancamentos_diario_conselho_preservados_no_ciclo`.
- Performance: `selects_da_listagem_constantes_com_2_e_6_turmas` — **18 SELECTs com 2 turmas e 18 com 6 turmas** (a contagem é medida por `event.listen(engine, "before_cursor_execute")`).
- Perfis: `perfis_da_lixeira_e_da_reativacao[admin|secretaria|pedagico]=200`, `[professor]=403`.

## 7. P5 — ensaio de ciclo completo

`scripts/ensaio_l4_1_reativacao.py` — 8 passos **pelas rotas reais** (semear → desativar B → excluir → lixeira → reativar pré-selecionado → 2.º ciclo explícito A+B → recusa atômica no cenário da variante → limpeza), **31 conferências**, todas OK em SQLite e no scratch PostgreSQL (`--db pautaon_ensaio`; o script recusa PostgreSQL cujo banco não contenha "ensaio").

Fingerprints (sha1 do conteúdo bruto, SQL puro) inalterados no ciclo — PostgreSQL:

```
frequencia:      2:370c2eab0301 -> 2:370c2eab0301
registro_aula:   1:a15eddcb0068 -> 1:a15eddcb0068
conselho_classe: 1:08a11d997660 -> 1:08a11d997660
transferencia:   0:da39a3ee5e6b -> 0:da39a3ee5e6b
```

O ensaio confere ainda o HTML da lixeira (caixa de A marcada, de B desmarcada, rótulos corretos), o número de marcadores (2 ciclos = 2 logs, nenhum criado pela reativação) e a limpeza (`turmas` e `log_acao` do ensaio = 0 no scratch ao final).

## 8. Desvios e achados

1. **TRAVA do P1 acionada** → marcador LogAcao por decisão do operador; o plano original (comparar `updated_at`) é impossível sem mudar o listener (fora de escopo).
2. **Bug real exposto pelos testes do P4:** `reativar_turma` devolvia `"conflitos": [i.id for i in avaliacao["conflitos"]]`, mas `conflitos` já guarda ids → `AttributeError: 'int' object has no attribute 'id'`, que a rota mascarava como flash genérica "código 99-…". Corrigido para `list(avaliacao["conflitos"])`.
3. **Harness — uma identidade por teste:** o fixture `app` (`tests/test_conselho_oferta.py`) mantém um app context aberto durante o teste, então o `g` é reaproveitado por todas as requisições e o flask_login serve sempre o **primeiro** usuário logado (medido: trocar o cookie `_user_id` para o professor, inclusive para `999`, continuava devolvendo o admin → 200 em vez de 403). O teste de perfis passou a usar semente própria `_seed_perfil(app, role)`, com **uma** identidade por caso — a convenção "um usuário por teste" (T1 §5.6) não é opcional.
4. **Sementes no harness precisam de `db.session.commit()`** explícito: dentro de `with app.app_context():` o Flask-SQLAlchemy faz rollback/remove ao sair do bloco, e `flush()` sozinho perdia os registros.
5. **Lacuna observada, fora do escopo:** `reativar_turma` **não** chama `sincronizar_programa_turma`, que mantém `Turma.programa` como projeção da oferta principal ativa (chamado por `adicionar_oferta`/`editar_oferta`/`definir_principal`/`desativar_oferta`). No fluxo normal o principal reativado é o mesmo de antes, então o programa bate; se a reativação trouxer só ofertas não principais, `Turma.programa` pode ficar desatualizado até a próxima operação que o sincronize. **Decidir** (uma linha no serviço + teste) — não feito aqui porque a tarefa limitava `app/` ao escopo mínimo.
6. Escopo ampliado com autorização do operador: `app/registros/turmas.py` e `app/templates/turmas/turma_lixeira.html` (além do serviço), mais `scripts/` (ensaio e sonda do P1) e `tests/`.

## 9. Validação

- Suíte completa: **712 passed**, 0 falhas (693 do L4 + 19 novos).
- `ruff check app tests scripts --select F821,F811`: *All checks passed!*
- `git diff --check`: limpo.
- Alembic head inalterado (`8d2e3f4a5b6c`); **nenhuma** migration.
- Sem push.

## 10. Arquivos

| Arquivo | Mudança |
|---|---|
| `app/services/turma_curso.py` | marcador + elegibilidade + preview em lote + `reativar_turma` seletivo |
| `app/registros/turmas.py` | marcador no `excluir_turma`; lixeira em lote; `oferta_ids` no reativar; flash detalhada |
| `app/templates/turmas/turma_lixeira.html` | checkbox por oferta inativa, badges, avisos |
| `tests/test_l4_1_reativacao_ofertas.py` | caracterização P2 + 13 funções P4 (19 casos no total) |
| `scripts/ensaio_l4_1_reativacao.py` | ensaio P5 (SQLite e scratch PG) |
| `scripts/verificar_sinal_updated_at.py` | evidência reproduzível do P1 |
| `app/models/MER.md` | §8.10: reativação L4, regra de ofertas elegíveis L4.1, limitação do marcador; §10: entrada L4.1 |
| `backlog_desenvolvimento.md` | seção 27/10 (L4/L4.1); `turma_lixeira` removida das Pendências abertas |
