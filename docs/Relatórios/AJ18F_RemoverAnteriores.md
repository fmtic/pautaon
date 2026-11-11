# AJ18-F — Remover frequências anteriores ao avançar a data de entrada

**Branch:** j18-f-remover-anteriores (a partir de 
ova_feature) · **Data:** 11/11/2026 · **Sem migration** · **Sem push**

## Escopo
Estende AJ18-E: ao avançar Inscricao.data_entrada_oferta para uma data com frequências já gravadas antes do novo piso, o operador escolhe explicitamente **Manter** (comportamento AJ18-E, linhas preservadas — D4) ou **Remover** (exclui as linhas anteriores na mesma transação). Recuar/igualar a data segue no-op/dispensa sem remoção.

## Implementação
- pp/services/entrada_oferta.py: EntradaComLinhasAnteriores passa a carregar quantidade e intervalo (data_min/data_max); esumo_frequencias_anteriores/_condicoes_frequencias_anteriores (read-only, escopo mesma oferta/aluno, data < nova, resolução D2 legado 	urma_curso_id NULL quando oferta única ativa); _remover_frequencias_anteriores (delete sem commit); lterar_entrada(..., confirmar=False, remover_anteriores=False) retorna ResultadoAlteracaoEntrada (anterior/nova, removidas+intervalo, anteriores+intervalo). Remoção ocorre na **mesma transação** da alteração da data e só quando há avanço com linhas anteriores (emover_anteriores ignorado nos demais casos).
- pp/registros/turmas.py: rota de alteração lê cao_anteriores (manter|emover); valor inválido → **400**; manter equivale à confirmação; confirmar=1 legado aceito; reabertura do modal devolve contagem/intervalo e escolha; LogAcao "Alteração da data de entrada na oferta" inclui mantidas N ou emovidas N frequências anteriores a dd/mm/aaaa (de ... a ...); flash informa remoções.
- pp/templates/turmas/detalhe.html: aviso server-driven com contagem/intervalo e dois botões (cao_anteriores=manter|remover), alerta de irreversibilidade; modal/JS existentes preservados.

## Regras atendidas
- Escopo da remoção: apenas Frequencia do mesmo aluno e da mesma oferta, com data < nova (condições compartilhadas com a contagem; legado D2 tratado).
- Manter preserva linhas (D4); Remover apaga definitivamente as anteriores listadas.
- Atomicidade: data, remoção e LogAcao no mesmo commit da rota; falha reverte.
- cao_anteriores inválida → 400. Perfis: admin/pedagógico/secretaria (rota existente); professor/gerência/outros → 403; unidade divergente 403; inscrição/turma/oferta inválidas 404.
- Recuar/igualar: no-op/sem remoção e sem pergunta de anteriores.
- Pauta/pendências/agregados recalculados a partir das linhas remanescentes (sem cache), coberto em teste.
- Não há trava específica de conselho/período fechado no fluxo de alteração de entrada no código atual; não introduzida nesta mudança.

## Testes
- 	ests/test_aj18f_remover_anteriores.py (novo, não rastreado antes): cobertura de escopo, manter/remover, log, confirmação UI, atomicidade, perfis/403, cao_anteriores inválida/400, recuar/igualar, pauta/pendências/agregados, legado oferta única, visibilidade para gerência.
- 	ests/test_aj18e_editar_entrada.py: ajuste da asserção/submissão para cao_anteriores=manter (compatível com confirmar=1), mantendo preservação D4.
- Snapshots AJ6-B3 (j6b3_*_t1/t2) e AJ6-B6 (j6b6_admin_registros_ver_turma.txt, j6b6_secretaria_registros_frequencia.txt) regenerados por refletirem a UI/ambiente atual do detalhe/lancamento.

**Validação direcionada (SQLite memória, APP_ENV=development):** pytest -q tests/test_aj18f_remover_anteriores.py tests/test_aj18e_editar_entrada.py tests/test_aj6b3_snapshot_nao_professor.py "tests/test_aj6b6_matriz_rotas_professor.py::test_snapshot_nao_professor_inalterado" → **37 passed**. Ruff (F821,F811,F841,F401) limpo nos arquivos alterados/tocados.

## Pendências
- Suíte completa pytest tests/ -q não executada nesta sessão.
- Revisão/merge conforme fluxo do repositório; deploy segue dependente da migration 1fdc7c03bdc2 (pendente em produção, estado herdado do AJ18).
