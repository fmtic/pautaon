# AJ9-C — evidências pós-upgrade

Data da execução: 2026-11-04. Ambiente: branch `nova_feature`.

- Backup de entrada: `D:\pautaon\instance\backups\pautaon_producao_2026-11-03.dump`.
- Banco temporário: `pautaon_rel_prod3`, restaurado do dump e atualizado até `c1d2e3f4a5b6`.
- Revisão no dump: `c4d5e6f7a8b9`; cadeia aplicada: 24 revisões até o head.
- O clone foi removido ao final; consulta posterior confirmou ausência.
- `pautaon` e `pautaon_ensaio` foram acessados exclusivamente com transações read-only. Nenhum commit foi criado e nenhum dado de produção foi gravado no repositório.
- A varredura não coletou nem registrou conteúdo pessoal. Os resultados abaixo são contagens, estados HTTP e resultados agregados.

## 1. Dados removidos e destino

A leitura do dump antes do upgrade encontrou 7 valores não nulos em `curso.carga_horaria`. A revisão `d1e2f3a4b5c6` remove a coluna sem copiá-la. Não há coluna homônima de destino em `turma_curso`; a duração atual pode ser calculada em minutos a partir dos horários da turma/oferta, mas isso não preserva necessariamente o valor original em horas. Assim, os 7 valores não têm destino persistente equivalente demonstrado.

`turma.conselho_concluido` tinha 12 valores não nulos: 0 `true`, 12 `false`. A revisão `e5f6a7b8c9d0` cria `turma_curso.conselho_concluido`, copia o estado quando há exatamente uma oferta ativa, e `f6a7b8c9d0e1` remove a coluna da turma. No clone, as 12 turmas tinham exatamente uma oferta ativa; após upgrade, as 12 ofertas estão `false`. Nenhum estado `true` foi perdido.

O dump não tinha a tabela `turma_curso`; portanto, as três colunas de agenda dessa tabela ainda não tinham valores no ponto inicial. A revisão `311d554dfd6e` cria as ofertas copiando os campos de `turma`, e `5730d7c594ba` materializa os horários na grade. Antes do upgrade, `turma.dias_semana` tinha 12 valores não nulos, `hora_inicio` 11 e `hora_fim` 11. Após upgrade, `turma_curso_horario` contém 23 linhas cobrindo 12 ofertas; 21 linhas têm par completo de horários, 2 têm ao menos um horário ausente, nenhuma oferta ficou sem grade e não foi encontrada oferta com horários não uniformes (0). Os dados escalares de agenda têm destino na grade; não foi observada perda de variação por dia.

| Revisão | Coluna removida no upgrade | Não nulos antes | Destino / resultado |
|---|---|---:|---|
| `d1e2f3a4b5c6` | `curso.carga_horaria` | 7 | Sem cópia para coluna equivalente; duração pode ser derivada do intervalo, mas não garante recuperar o valor original. |
| `f6a7b8c9d0e1` | `turma.conselho_concluido` | 12 (0 true, 12 false) | `turma_curso.conselho_concluido`; as 12 ofertas ficaram false. |
| `8d2e3f4a5b6c` | `turma.dias_semana` | 12 | Grade por dia `turma_curso_horario`; coberta para as 12 ofertas. |
| `8d2e3f4a5b6c` | `turma.hora_inicio` | 11 | Grade por dia; pares completos em 21 linhas de grade. |
| `8d2e3f4a5b6c` | `turma.hora_fim` | 11 | Grade por dia; pares completos em 21 linhas de grade. |
| `8d2e3f4a5b6c` | `turma_curso.dias_semana` | tabela ausente no dump | Criada/backfillada pelas revisões anteriores e projetada na grade antes do drop. |
| `8d2e3f4a5b6c` | `turma_curso.hora_inicio` | tabela ausente no dump | Criada/backfillada pelas revisões anteriores e projetada na grade antes do drop. |
| `8d2e3f4a5b6c` | `turma_curso.hora_fim` | tabela ausente no dump | Criada/backfillada pelas revisões anteriores e projetada na grade antes do drop. |

A inspeção das 24 revisões não encontrou outras colunas removidas na direção `upgrade`. `turma.avaliacao_inicial/percurso/final` não são removidas por essa cadeia e continuam no schema; não havia valores não nulos nesses campos no clone. Após upgrade, nenhuma das oito colunas listadas acima permanece no schema.

## 2. Atomicidade

Em [migrations/env.py](../../migrations/env.py), `context.configure` recebe `**conf_args`, sem definir `transaction_per_migration` ou `transactional_ddl`; Flask-Migrate também não forneceu essas opções explicitamente. No contexto PostgreSQL verificado, Alembic reportou `transactional_ddl=True`; `transaction_per_migration` usa o default `False`, e `env.py` envolve `run_migrations()` em `context.begin_transaction()`.

Foi feita uma cópia temporária das migrations fora do Git e injetado `RuntimeError` ao final do corpo da revisão final `c1d2e3f4a5b6`. A execução falhou intencionalmente. Comparando imediatamente antes/depois: `alembic_version` continuou em `c4d5e6f7a8b9`, a assinatura do schema não mudou e as contagens de todas as tabelas não mudaram. Em seguida, sem a injeção, `flask db upgrade` concluiu até `c1d2e3f4a5b6`. Não foi encontrado `autocommit_block`, `COMMIT` ou desativação explícita de DDL transacional nas revisões examinadas; nenhuma revisão não atômica foi identificada neste caminho PostgreSQL. Essa prova é específica à configuração PostgreSQL ensaiada.

## 3. Integridade após upgrade

| Verificação | Contagem |
|---|---:|
| Turmas sem oferta | 0 |
| Ofertas sem professor (total / ativas) | 0 / 0 |
| Inscrições com `turma_curso_id IS NULL` | 0 |
| Frequência com `turma_curso_id IS NULL` (total / turma com exatamente 1 oferta total / exatamente 1 oferta ativa) | 0 / 0 / 0 |
| Registro de aula com `turma_curso_id IS NULL` (total / turma com exatamente 1 oferta total / exatamente 1 oferta ativa) | 0 / 0 / 0 |
| Pares duplicados `(turma, curso)` (grupos / linhas excedentes) | 0 / 0 |
| Divergência `Turma.professor_id` vs `TurmaCurso.professor_id` | 0 |
| Professores ativos sem oferta ativa (contas afetadas pela regra AJ6-B) | 2 |

A contagem de professores é agregada; nenhuma identidade foi listada.

## 4. Varredura das regras GET

Executadas as 113 regras GET do `url_map` para cada um dos 5 papéis com usuário ativo no clone (`admin`, `gerencia`, `pedagogico`, `professor`, `secretaria`): 565 combinações. As conexões foram iniciadas com `PGOPTIONS=-c default_transaction_read_only=on`; IDs de rota foram escolhidos do próprio clone e não são gravados neste relatório.

Distribuição: `200`: 330, `302`: 54, `403`: 157, `404`: 14, `N/A`: 10. Não houve resposta 5xx; portanto, não há exceção 5xx a detalhar. As duas rotas abaixo não puderam receber um identificador porque não há registro correspondente no clone:

| Endpoint | Regra | Motivo |
|---|---|---|
| `registros.editar` | `/editar/<int:id>` | não há registro da tabela `registro` no clone |
| `servico_social.gerar_impressao` | `/servico-social/impressao/<int:resposta_id>` | não há resposta em `respostas_formulario` no clone |

A matriz agrupa as 113 regras em 112 pares endpoint/caminho; `/centros-custo/inativos` está registrada duas vezes no `url_map` e ambas as regras foram chamadas (resultados iguais). O campo “Regras” preserva essa multiplicidade.

| Regras | Endpoint | Regra GET | admin | gerencia | pedagogico | professor | secretaria |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | `main.home` | `/` | 200 | 200 | 200 | 200 | 200 |
| 1 | `informacao_padrao.painel_informacao_padrao` | `/admin/informacao-padrao` | 200 | 403 | 403 | 403 | 403 |
| 1 | `auth.ver_logs` | `/admin/logs` | 200 | 403 | 403 | 403 | 403 |
| 1 | `auth.painel_admin` | `/admin/painel` | 200 | 302 | 302 | 302 | 302 |
| 1 | `auth.admin_unidades` | `/admin/unidades` | 200 | 403 | 403 | 403 | 403 |
| 1 | `auth.aguardando_aprovacao` | `/aguardando-aprovacao` | 302 | 302 | 302 | 302 | 302 |
| 1 | `registros.ver_documento_aluno` | `/aluno/<int:aluno_id>/documento/<doc_id>` | 404 | 404 | 404 | 403 | 404 |
| 1 | `registros.foto_aluno` | `/aluno/<int:aluno_id>/foto` | 302 | 302 | 302 | 403 | 302 |
| 1 | `registros.historico_aluno` | `/aluno/<int:aluno_id>/historico` | 200 | 200 | 200 | 403 | 200 |
| 1 | `registros.info_professor` | `/aluno/<int:aluno_id>/info-professor` | 403 | 403 | 403 | 403 | 403 |
| 1 | `registros.editar_aluno` | `/aluno/editar/<int:id>` | 200 | 403 | 200 | 403 | 200 |
| 1 | `registros.imprimir_aluno` | `/aluno/imprimir/<int:id>` | 200 | 403 | 200 | 403 | 200 |
| 1 | `registros.novo_aluno` | `/aluno/novo` | 200 | 403 | 200 | 403 | 200 |
| 1 | `registros.transferir_aluno` | `/aluno/transferir/<int:aluno_id>` | 302 | 403 | 200 | 403 | 302 |
| 1 | `registros.gerenciar_alunos` | `/alunos` | 200 | 200 | 200 | 403 | 200 |
| 1 | `registros.historico_atendimentos` | `/alunos/<int:aluno_id>/atendimentos` | 200 | 200 | 200 | 403 | 200 |
| 1 | `registros.listar_atendimentos` | `/alunos/atendimentos` | 200 | 200 | 200 | 403 | 200 |
| 1 | `registros.transicao_atendimentos` | `/alunos/atendimentos/transicao` | 200 | 200 | 200 | 403 | 200 |
| 1 | `registros.buscar_instituicoes` | `/alunos/instituicoes` | 200 | 403 | 200 | 403 | 200 |
| 1 | `registros.api_alunos` | `/api/alunos/<int:turma_id>` | 403 | 403 | 200 | 403 | 403 |
| 1 | `registros.detalhe_atendimento` | `/atendimentos/<int:id>` | 200 | 200 | 403 | 403 | 200 |
| 1 | `registros.baixar_anexo_atendimento` | `/atendimentos/<int:id>/anexo` | 404 | 404 | 403 | 403 | 404 |
| 1 | `auth.google_callback` | `/auth/google/callback` | 302 | 302 | 302 | 302 | 302 |
| 1 | `auth.google_confirmar_vinculo` | `/auth/google/confirmar-vinculo` | 302 | 302 | 302 | 302 | 302 |
| 1 | `auth.google_login` | `/auth/google/login` | 302 | 302 | 302 | 302 | 302 |
| 1 | `registros.listar_centros_custo_variant_centro_custo` | `/centro-custo` | 200 | 200 | 200 | 403 | 200 |
| 1 | `registros.listar_centros_custo_inativos_variant_centro_custo` | `/centro-custo/inativos` | 200 | 200 | 200 | 403 | 200 |
| 1 | `registros.listar_centros_custo_variant_centro_de_custo` | `/centro-de-custo` | 200 | 200 | 200 | 403 | 200 |
| 1 | `registros.listar_centros_custo_inativos_variant_centro_de_custo` | `/centro-de-custo/inativos` | 200 | 200 | 200 | 403 | 200 |
| 1 | `registros.listar_centros_custo_variant_centro_custo` | `/centro_custo` | 200 | 200 | 200 | 403 | 200 |
| 1 | `registros.listar_centros_custo_inativos_variant_centro_custo` | `/centro_custo/inativos` | 200 | 200 | 200 | 403 | 200 |
| 1 | `registros.centro_custo` | `/centros-custo` | 200 | 200 | 200 | 403 | 200 |
| 1 | `registros.centro_custo_list` | `/centros-custo` | 200 | 200 | 200 | 403 | 200 |
| 1 | `registros.centros_custo` | `/centros-custo` | 200 | 200 | 200 | 403 | 200 |
| 1 | `registros.centros_custo_list` | `/centros-custo` | 200 | 200 | 200 | 403 | 200 |
| 1 | `registros.centros_de_custo` | `/centros-custo` | 200 | 200 | 200 | 403 | 200 |
| 1 | `registros.listar_centro_custo` | `/centros-custo` | 200 | 200 | 200 | 403 | 200 |
| 1 | `registros.listar_centros_custo` | `/centros-custo` | 200 | 200 | 200 | 403 | 200 |
| 1 | `registros.listar_centros_de_custo` | `/centros-custo` | 200 | 200 | 200 | 403 | 200 |
| 1 | `registros.centro_custo_inativos` | `/centros-custo/inativos` | 200 | 200 | 200 | 403 | 200 |
| 1 | `registros.centros_custo_inativos` | `/centros-custo/inativos` | 200 | 200 | 200 | 403 | 200 |
| 2 | `registros.listar_centros_custo_inativos` | `/centros-custo/inativos` | 200 x2 | 200 x2 | 200 x2 | 403 x2 | 200 x2 |
| 1 | `registros.listar_centros_custo_variant_centros_de_custo` | `/centros-de-custo` | 200 | 200 | 200 | 403 | 200 |
| 1 | `registros.listar_centros_custo_inativos_variant_centros_de_custo` | `/centros-de-custo/inativos` | 200 | 200 | 200 | 403 | 200 |
| 1 | `registros.listar_centros_custo_variant_centros_custo` | `/centros_custo` | 200 | 200 | 200 | 403 | 200 |
| 1 | `registros.listar_centros_custo_inativos_variant_centros_custo` | `/centros_custo/inativos` | 200 | 200 | 200 | 403 | 200 |
| 1 | `conselho.index_conselho` | `/conselho` | 200 | 200 | 200 | 200 | 200 |
| 1 | `conselho.fechamento_turma` | `/conselho/fechamento/<int:turma_id>` | 403 | 403 | 200 | 403 | 403 |
| 1 | `conselho.imprimir_conselho` | `/conselho/imprimir` | 200 | 200 | 200 | 403 | 403 |
| 1 | `conselho.lancamento_conselho` | `/conselho/lancamento` | 200 | 200 | 200 | 200 | 200 |
| 1 | `conselho.gerenciar_perguntas` | `/conselho/perguntas` | 200 | 200 | 200 | 403 | 403 |
| 1 | `registros.listar_cursos` | `/cursos` | 200 | 403 | 200 | 403 | 200 |
| 1 | `registros.listar_cursos_inativos` | `/cursos/inativos` | 200 | 403 | 200 | 403 | 200 |
| 1 | `main.dashboard` | `/dashboard` | 200 | 200 | 200 | 200 | 302 |
| 1 | `registros.editar` | `/editar/<int:id>` | N/A | N/A | N/A | N/A | N/A |
| 1 | `registros.frequencia` | `/frequencia` | 200 | 403 | 200 | 200 | 200 |
| 1 | `registros.frequencia_relatorio` | `/frequencia_relatorio` | 403 | 403 | 200 | 403 | 403 |
| 1 | `conselho.informacoes` | `/informacoes` | 200 | 200 | 200 | 403 | 200 |
| 1 | `auth.login` | `/login` | 200 | 200 | 200 | 200 | 200 |
| 1 | `auth.logout` | `/logout` | 302 | 302 | 302 | 302 | 302 |
| 1 | `main.painel` | `/painel` | 200 | 200 | 200 | 200 | 302 |
| 1 | `main.painel_secretaria` | `/painel/secretaria` | 200 | 200 | 200 | 403 | 200 |
| 1 | `registros.periodo_letivo` | `/periodo-letivo` | 200 | 200 | 200 | 403 | 200 |
| 1 | `registros.periodo_letivo_calendario` | `/periodo-letivo/<int:id>/calendario` | 200 | 200 | 200 | 403 | 200 |
| 1 | `registros.arquivo_modelo_certificado` | `/periodo-letivo/<int:id>/certificado-modelo/<int:centro_id>/arquivo` | 404 | 404 | 404 | 403 | 404 |
| 1 | `registros.listar_centros_custo_variant_periodo_letivo_centros_custo` | `/periodo-letivo/centros-custo` | 200 | 200 | 200 | 403 | 200 |
| 1 | `registros.listar_centros_custo_inativos_variant_periodo_letivo_centros_custo` | `/periodo-letivo/centros-custo/inativos` | 200 | 200 | 200 | 403 | 200 |
| 1 | `registros.periodo_letivo_editar` | `/periodo-letivo/editar/<int:id>` | 200 | 200 | 200 | 403 | 200 |
| 1 | `registros.periodo_letivo_novo` | `/periodo-letivo/novo` | 200 | 403 | 200 | 403 | 200 |
| 1 | `registros.periodo_letivo_relatorio_certificado` | `/periodo-letivo/relatorio/<int:id>` | 200 | 200 | 200 | 403 | 200 |
| 1 | `registros.listar_centros_custo_variant_periodos_centros_custo` | `/periodos/centros-custo` | 200 | 200 | 200 | 403 | 200 |
| 1 | `registros.listar_centros_custo_inativos_variant_periodos_centros_custo` | `/periodos/centros-custo/inativos` | 200 | 200 | 200 | 403 | 200 |
| 1 | `registros.planejamento` | `/planejamento` | 200 | 403 | 200 | 403 | 200 |
| 1 | `registros.calendario_dias` | `/planejamento/calendario/<int:periodo_id>` | 200 | 200 | 200 | 403 | 200 |
| 1 | `registros.calendario_exportar` | `/planejamento/calendario/<int:periodo_id>/exportar` | 200 | 200 | 200 | 403 | 200 |
| 1 | `registros.imprimir_temas` | `/planejamento/imprimir-temas` | 200 | 403 | 200 | 403 | 200 |
| 1 | `main.politica_privacidade` | `/politica_privacidade` | 200 | 200 | 200 | 200 | 200 |
| 1 | `registros.painel_professor` | `/professor/painel` | 302 | 302 | 302 | 302 | 302 |
| 1 | `main.painel_pedagogico_professor` | `/professor/painel-pedagogico` | 200 | 200 | 200 | 200 | 403 |
| 1 | `relatorios.relatorio_geral` | `/relatorios/` | 200 | 200 | 200 | 403 | 200 |
| 1 | `relatorios.relatorio_alunos` | `/relatorios/alunos` | 200 | 200 | 200 | 403 | 200 |
| 1 | `relatorios.ficha_aluno_view` | `/relatorios/alunos/<int:aluno_id>/ficha` | 404 | 404 | 200 | 403 | 404 |
| 1 | `relatorios.bi_dashboard` | `/relatorios/bi` | 200 | 200 | 200 | 403 | 200 |
| 1 | `relatorios.bi_api_dados` | `/relatorios/bi/dados` | 200 | 200 | 200 | 403 | 200 |
| 1 | `relatorios.bi_exportar_xlsx` | `/relatorios/bi/exportar/xlsx` | 200 | 200 | 200 | 403 | 200 |
| 1 | `relatorios.bi_indicador` | `/relatorios/bi/indicador/<codigo>` | 200 | 200 | 200 | 403 | 200 |
| 1 | `relatorios.resultado_conselho` | `/relatorios/conselho` | 200 | 200 | 200 | 403 | 200 |
| 1 | `relatorios.exportar_relatorio` | `/relatorios/exportar` | 200 | 200 | 200 | 403 | 200 |
| 1 | `relatorios.observacoes` | `/relatorios/observacoes` | 200 | 200 | 200 | 403 | 200 |
| 1 | `relatorios.painel_pedagogico` | `/relatorios/painel` | 200 | 200 | 200 | 403 | 200 |
| 1 | `relatorios.busca_alunos` | `/relatorios/painel/busca` | 200 | 200 | 200 | 403 | 200 |
| 1 | `relatorios.exportar_relatorio_alunos` | `/relatorios/relatorio_alunos/exportar` | 302 | 302 | 302 | 403 | 302 |
| 1 | `servico_social.dados_aluno` | `/servico-social/aluno/<int:aluno_id>/dados` | 200 | 403 | 403 | 403 | 403 |
| 1 | `servico_social.listar_entrevistas` | `/servico-social/entrevistas` | 200 | 403 | 403 | 403 | 403 |
| 1 | `servico_social.preencher_formulario` | `/servico-social/entrevistas/<tipo>` | 200 | 403 | 403 | 403 | 403 |
| 1 | `servico_social.gerar_impressao` | `/servico-social/impressao/<int:resposta_id>` | N/A | N/A | N/A | N/A | N/A |
| 1 | `static` | `/static/<path:filename>` | 200 | 200 | 200 | 200 | 200 |
| 1 | `main.termos_servico` | `/termos_servico` | 200 | 200 | 200 | 200 | 200 |
| 1 | `auth.trocar_senha` | `/trocar-senha` | 200 | 302 | 200 | 302 | 302 |
| 1 | `main.trocar_unidade` | `/trocar-unidade/<int:id>` | 302 | 302 | 302 | 302 | 302 |
| 1 | `registros.turma` | `/turma` | 200 | 200 | 200 | 403 | 200 |
| 1 | `registros.ver_turma` | `/turma/<int:id>` | 403 | 403 | 200 | 403 | 403 |
| 1 | `registros.imprimir_pauta` | `/turma/<int:id>/imprimir-pauta` | 403 | 403 | 200 | 403 | 403 |
| 1 | `registros.turma_ofertas` | `/turma/<int:id>/ofertas` | 403 | 403 | 200 | 403 | 403 |
| 1 | `conselho.avaliar_turma` | `/turma/<int:turma_id>/avaliacao` | 403 | 403 | 200 | 403 | 403 |
| 1 | `registros.ver_observacoes` | `/turma/<int:turma_id>/observacoes` | 403 | 403 | 200 | 403 | 403 |
| 1 | `registros.editar_turma` | `/turma/editar/<int:id>` | 403 | 403 | 200 | 403 | 403 |
| 1 | `registros.nova_turma` | `/turma/nova` | 200 | 200 | 200 | 403 | 200 |
| 1 | `registros.carga_horaria_turmas` | `/turmas/carga-horaria` | 200 | 200 | 200 | 403 | 200 |
| 1 | `registros.imprimir_centros_custo_turmas` | `/turmas/centros-custo/imprimir` | 200 | 200 | 200 | 403 | 200 |
| 1 | `registros.turma_listar` | `/turmas/lista` | 200 | 200 | 200 | 403 | 200 |
| 1 | `registros.turma_lixeira` | `/turmas/lixeira` | 200 | 403 | 200 | 403 | 200 |

## 5. Indicadores BI

Executados pelo serviço `executar_indicador`, em conexão read-only, os 61 códigos documentados no catálogo. Para listas foi registrado apenas o tamanho; para indicadores escalares, o valor. Nenhum rótulo ou linha retornada foi incluído.

| Código | Resultado |
|---|---|
| ALU-001 | 1153 |
| ALU-002 | 1154 |
| ALU-003 | 0 |
| ALU-004 | ProgrammingError — comparação DATE >= VARCHAR rejeitada pelo PostgreSQL |
| ALU-005 | lista (3 itens) |
| ALU-006 | lista (5 itens) |
| ALU-007 | 9 |
| ALU-008 | lista (2 itens) |
| ALU-009 | lista (6 itens) |
| ALU-010 | lista (12 itens) |
| ALU-011 | 106 |
| ALU-012 | 1047 |
| ALU-013 | 106 |
| ALU-014 | 0 |
| ALU-015 | 0 |
| ALU-016 | 0 |
| ALU-017 | 0 |
| ALU-018 | 0 |
| ATD-001 | 1 |
| AUL-001 | 10 |
| AUL-002 | lista (1 item) |
| AUL-003 | lista (1 item) |
| AUL-004 | lista (1 item) |
| AUL-005 | lista (1 item) |
| AUL-006 | lista (1 item) |
| AUL-007 | lista (6 itens) |
| AUL-008 | lista (10 itens) |
| CRU-001 | lista (2 itens) |
| CRU-002 | lista (0 itens) |
| CRU-003 | lista (0 itens) |
| CRU-004 | lista (0 itens) |
| CRU-005 | lista (4 itens) |
| DIV-001 | lista (3 itens) |
| FRE-001 | 130 |
| FRE-002 | 81 |
| FRE-003 | 46 |
| FRE-004 | 3 |
| FRE-005 | 63.8 |
| FRE-006 | 3 |
| FRE-007 | 1 |
| FRE-008 | 9 |
| FRE-009 | lista (12 itens) |
| FRE-010 | lista (1 item) |
| INS-001 | 113 |
| INS-002 | 113 |
| INS-003 | 0 |
| INS-004 | 113 |
| INS-005 | 0 |
| INS-006 | ValueError — catalogado como nao implementado |
| INS-007 | ValueError — catalogado como nao implementado |
| INS-008 | lista (6 itens) |
| SOC-001 | lista (5 itens) |
| SOC-002 | 31 |
| TUR-001 | 12 |
| TUR-002 | 12 |
| TUR-003 | lista (12 itens) |
| TUR-004 | 9.4 |
| TUR-005 | lista (6 itens) |
| TUR-006 | lista (1 item) |
| TUR-007 | lista (1 item) |
| TUR-008 | lista (6 itens) |

`ALU-004` falhou com `ProgrammingError`: comparação PostgreSQL `DATE >= VARCHAR` não suportada. `INS-006` e `INS-007` lançaram `ValueError` porque estão catalogados como não implementados; as demais chamadas retornaram valor/lista conforme a tabela.

## 6. Contagens dos bancos reais e limpeza

Contagens exatas por tabela (schemas não sistêmicos) antes e depois do ensaio:

| Banco | Tabelas | Linhas somadas | Contagens idênticas | SHA-256 do mapa tabela=contagem |
|---|---:|---:|---|---|
| `pautaon` | 38 | 3271 | sim | `8a9e43b3acb6b86ff81a31ad12fc2c06daaf0f03af28c8d8eeedfba8edd25fc3` |
| `pautaon_ensaio` | 38 | 3700 | sim | `9bc3df6ccd5d2d4367e0f2eb7d79381af8c3b44996f87a50f22951082aab62fe` |

Os dois bancos mantiveram as mesmas tabelas e contagens em todos os objetos comparados. O banco `pautaon_rel_prod3` foi removido e sua ausência foi confirmada. Nenhum dado do dump foi adicionado ao Git.
