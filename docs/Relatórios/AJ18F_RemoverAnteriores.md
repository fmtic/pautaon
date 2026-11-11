# AJ18-F — Remover frequências anteriores ao avançar a data de entrada

**Branch:** `aj18-f-remover-anteriores` (a partir de `nova_feature`) · **Data:** 11/11/2026 · **Sem migration** · **Sem push**

## Escopo
Estende AJ18-E: ao avançar `Inscricao.data_entrada_oferta` para uma data com frequências já gravadas antes do novo piso, o operador escolhe explicitamente **Manter** (comportamento AJ18-E, linhas preservadas — D4) ou **Remover** (exclui as linhas anteriores na mesma transação). Recuar/igualar a data segue no-op/dispensa sem remoção.

## Implementação
- `app/services/entrada_oferta.py`: `EntradaComLinhasAnteriores` passa a carregar quantidade e intervalo (`data_min`/`data_max`); `resumo_frequencias_anteriores`/`_condicoes_frequencias_anteriores` (read-only, escopo mesma oferta/aluno, `data < nova`, resolução D2 legado `turma_curso_id NULL` quando oferta única ativa); `_remover_frequencias_anteriores` (delete sem commit); `alterar_entrada(..., confirmar=False, remover_anteriores=False)` retorna `ResultadoAlteracaoEntrada` (anterior/nova, removidas+intervalo, anteriores+intervalo). Remoção ocorre na **mesma transação** da alteração da data e só quando há avanço com linhas anteriores (`remover_anteriores` ignorado nos demais casos).
- **AJ18-F2 (trava opção A, conselho concluído):** quando `remover_anteriores=True` e `oferta.conselho_concluido` é verdadeiro, `alterar_entrada` levanta `ValueError("Não é possível remover frequências anteriores: o conselho desta oferta já foi concluído. Mantenha as frequências para avançar a entrada.")` sem alterar a data e sem remover linhas; `acao_anteriores=manter` segue permitido.
- `app/registros/turmas.py`: rota de alteração lê `acao_anteriores` (`manter`|`remover`); valor inválido → **400**; `manter` equivale à confirmação; `confirmar=1` legado aceito; reabertura do modal devolve contagem/intervalo e escolha; `LogAcao` "Alteração da data de entrada na oferta" inclui `mantidas N` ou `removidas N frequências anteriores a dd/mm/aaaa (de ... a ...)`; flash informa remoções. Contexto `entrada_conselho_bloqueia_remocao` expõe `inscricao.turma_curso.conselho_concluido` para o modal.
- `app/templates/turmas/detalhe.html`: aviso server-driven com contagem/intervalo e dois botões (`acao_anteriores=manter|remover`), alerta de irreversibilidade; quando o conselho da oferta está concluído, o botão "Remover frequências" é ocultado e o aviso informa que só é possível manter as frequências para avançar a entrada. Modal/JS existentes preservados.

## Regras atendidas
- Escopo da remoção: apenas `Frequencia` do mesmo aluno e da mesma oferta, com `data < nova` (condições compartilhadas com a contagem; legado D2 tratado).
- Manter preserva linhas (D4); Remover apaga definitivamente as anteriores listadas.
- **Trava (opção A):** com `TurmaCurso.conselho_concluido` verdadeiro, remover anteriores é bloqueado no serviço e na UI; manter permanece permitido.
- Atomicidade: data, remoção e `LogAcao` no mesmo commit da rota; falha reverte.
- `acao_anteriores` inválida → 400. Perfis: admin/pedagógico/secretaria (rota existente); professor/gerência/outros → 403; unidade divergente 403; inscrição/turma/oferta inválidas 404.
- Recuar/igualar: no-op/sem remoção e sem pergunta de anteriores.
- Pauta/pendências/agregados recalculados a partir das linhas remanescentes (sem cache), coberto em teste.

## Auditoria de snapshots (HEAD `95f5edf` + F2)
- **HEAD `95f5edf`** atualizou 12 snapshots: `aj6b3_*_t1/t2` (10) e `aj6b6_admin_registros_ver_turma.txt` ganharam a UI do modal `#modalEntrada`/ações de entrada no detalhe da turma **e** bump de versão de app (`v0.2.0 -> v0.2.2`) em header/footer (coerente com `app/version.py` 0.2.2); `aj6b6_secretaria_registros_frequencia.txt` (tela de lançamento, sem `#modalEntrada`) teve apenas o bump de versão em header/footer, sem mudança de conteúdo de lançamento/modal — efeito colateral do bump global já presente em `app/version.py`, não alteração funcional da pauta.
- **F2 (working tree):** não altera snapshots; o modal continua renderizado da mesma forma quando o conselho não está concluído (direcionados de snapshot AJ6-B3/AJ6-B6 não-concluído permanecem verdes). O caso concluído é coberto por teste de template específico (`test_modal_oculta_remover_quando_conselho_concluido`).

## Testes
- `tests/test_aj18f_remover_anteriores.py`: cobertura de escopo, manter/remover, log, confirmação UI, atomicidade, perfis/403, `acao_anteriores` inválida/400, recuar/igualar, pauta/pendências/agregados, legado oferta única, visibilidade para gerência; **F2:** `_concluir_conselho`, `test_conselho_concluido_bloqueia_remocao_sem_alterar`, `test_conselho_concluido_permite_manter`, `test_sem_conselho_remocao_liberada`, `test_modal_oculta_remover_quando_conselho_concluido`.
- `tests/test_aj18e_editar_entrada.py`: ajuste da asserção/submissão para `acao_anteriores=manter` (compatível com `confirmar=1`), mantendo preservação D4.
- Snapshots AJ6-B3 (`aj6b3_*_t1/t2`) e AJ6-B6 (`aj6b6_admin_registros_ver_turma.txt`, `aj6b6_secretaria_registros_frequencia.txt`) regenerados no commit `95f5edf` por refletirem a UI/ambiente atual do detalhe/lancamento e a versão 0.2.2.

**Validação direcionada (SQLite memória, `APP_ENV=development`, `DATABASE_URL=sqlite:///:memory:`):**
- `pytest -q tests/test_aj18f_remover_anteriores.py tests/test_aj18e_editar_entrada.py tests/test_aj6b3_snapshot_nao_professor.py "tests/test_aj6b6_matriz_rotas_professor.py::test_snapshot_nao_professor_inalterado"` → **41 passed** (F2).
- `pytest -q tests/test_aj18f_remover_anteriores.py tests/test_aj18e_editar_entrada.py tests/test_aj6b3_snapshot_nao_professor.py "tests/test_aj6b6_matriz_rotas_professor.py::test_snapshot_nao_professor_inalterado"` reexecutado após F2: **41 passed**.
- Ruff (`--select F821,F811,F841,F401`) limpo em `app/services/entrada_oferta.py app/registros/turmas.py tests/test_aj18f_remover_anteriores.py`.

**Suíte completa (`pytest tests/ -q`, mesma env):** **1728 passed, 14 failed, 1081 warnings in 1119.45s (0:18:39)**. Falhas não relacionadas a AJ18/F2 (preexistentes/ambientais no estado atual do branch): `tests/test_aj5c_form_caracterizacao.py` (6, snapshots esperam `v0.2.0` enquanto app/snapshots de versão estão em `v0.2.2`), `tests/test_aj6b5_lista_turma_por_papel.py::test_snapshot_lista_gestores_identico` (1, mesmo drift de versão), `tests/test_aj7b_conselho_none.py::test_a5_varredura_get_nos_templates_conselho` (1, presença local de `app/templates/conselho/lancamento - Copia.html` não rastreado), `tests/test_aj7d_gravacao_conselho.py` (6 hashes dourados divergem por bump de versão em templates). Nenhuma dessas falhas envolve `entrada_oferta`, rota/modal de entrada ou casos AJ18.

## Pendências
- Revisão/merge conforme fluxo do repositório; deploy segue dependente da migration `1fdc7c03bdc2` (produção em `f2a3b4c5d6e7`, uma revisão pendente — responsável aplica).
- Falhas de suíte acima são externas a AJ18-F2 e exigem tratamento próprio (atualização de snapshots/goldens de versão e remoção/ignore do arquivo local `lancamento - Copia.html`).
