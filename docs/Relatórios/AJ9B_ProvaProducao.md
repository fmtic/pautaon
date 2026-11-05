# AJ9-B — Prova do dump de produção

## Resumo e segurança

- Dump usado: `instance/backups/pautaon_producao_2026-11-03.dump` (3/11/2026, 182.373 bytes), restaurado localmente em `pautaon_rel_prod2`.
- As consultas em `pautaon` e `pautaon_ensaio` foram `SELECT` em transações somente leitura. Nenhuma migration, backfill ou smoke test foi executado nesses bancos.
- `pautaon_rel_prod2` e os dois clones de teste do backfill foram removidos; a ausência dos três nomes foi confirmada.
- Nenhum commit ou push foi feito. A variante do backfill está em `.tmp/aj9b_backfill_unidade_id_nulos.sql`, ignorada pelo Git.
- O `git status` inicial estava limpo na branch `nova_feature` (22 commits à frente da upstream).

## 1. Revisões e versão

| Banco | `alembic_version` antes do upgrade | Head do código | Estado |
|---|---|---|---|
| Dump restaurado (`pautaon_rel_prod2`) | `c4d5e6f7a8b9` | `c1d2e3f4a5b6` | 24 revisões pendentes; upgrade aplicado no clone |
| `pautaon` consultado somente para leitura | `c1d2e3f4a5b6` | `c1d2e3f4a5b6` | **Não há migration pendente para esta instância** |

O clone do dump não estava na head; as 24 revisões pendentes identificadas foram:

1. `d1e2f3a4b5c6` — [d1e2f3a4b5c6_onda3c_drop_curso_carga_horaria.py](../../migrations/versions/d1e2f3a4b5c6_onda3c_drop_curso_carga_horaria.py)
2. `5a676f37b9a3` — [5a676f37b9a3_fix_onda2a_converte_varchar_para_date_.py](../../migrations/versions/5a676f37b9a3_fix_onda2a_converte_varchar_para_date_.py)
3. `b7c1d2e3f4a5` — [b7c1d2e3f4a5_fix_inscricoes_sequencia_id.py](../../migrations/versions/b7c1d2e3f4a5_fix_inscricoes_sequencia_id.py)
4. `311d554dfd6e` — [311d554dfd6e_onda4_fase1_turmacurso_inscricao_turma_.py](../../migrations/versions/311d554dfd6e_onda4_fase1_turmacurso_inscricao_turma_.py)
5. `8c4e1f9a7d32` — [8c4e1f9a7d32_onda4_fase1_fix_turma_curso_updated_by_id.py](../../migrations/versions/8c4e1f9a7d32_onda4_fase1_fix_turma_curso_updated_by_id.py)
6. `e7f3a1b9c4d5` — [e7f3a1b9c4d5_onda4_fase4_turma_curso_id_frequencia.py](../../migrations/versions/e7f3a1b9c4d5_onda4_fase4_turma_curso_id_frequencia.py)
7. `d2e3f4a5b6c7` — [d2e3f4a5b6c7_centro_custo.py](../../migrations/versions/d2e3f4a5b6c7_centro_custo.py)
8. `a1b2c3d4e5f6` — [a1b2c3d4e5f6_programa_oferta.py](../../migrations/versions/a1b2c3d4e5f6_programa_oferta.py)
9. `c3d4e5f6a7b8` — [c3d4e5f6a7b8_inscricao_exige_oferta.py](../../migrations/versions/c3d4e5f6a7b8_inscricao_exige_oferta.py)
10. `d4e5f6a7b8c9` — [d4e5f6a7b8c9_programa_obrigatorio_na_oferta.py](../../migrations/versions/d4e5f6a7b8c9_programa_obrigatorio_na_oferta.py)
11. `e5f6a7b8c9d0` — [e5f6a7b8c9d0_conselho_oferta_esquema_d51.py](../../migrations/versions/e5f6a7b8c9d0_conselho_oferta_esquema_d51.py)
12. `f6a7b8c9d0e1` — [f6a7b8c9d0e1_conselho_oferta_endurecimento_d55.py](../../migrations/versions/f6a7b8c9d0e1_conselho_oferta_endurecimento_d55.py)
13. `a8b9c0d1e2f3` — [a8b9c0d1e2f3_registro_aula_multiplos_temas.py](../../migrations/versions/a8b9c0d1e2f3_registro_aula_multiplos_temas.py)
14. `5730d7c594ba` — [5730d7c594ba_horario_por_dia_na_oferta_h1.py](../../migrations/versions/5730d7c594ba_horario_por_dia_na_oferta_h1.py)
15. `7c1d2e3f4a5b` — [7c1d2e3f4a5b_h5b_check_dia_0_5.py](../../migrations/versions/7c1d2e3f4a5b_h5b_check_dia_0_5.py)
16. `8d2e3f4a5b6c` — [8d2e3f4a5b6c_h5b_drop_colunas_agenda.py](../../migrations/versions/8d2e3f4a5b6c_h5b_drop_colunas_agenda.py)
17. `b7c8d9e0f1a2` — [b7c8d9e0f1a2_valor_esportista.py](../../migrations/versions/b7c8d9e0f1a2_valor_esportista.py)
18. `c8d9e0f1a2b3` — [c8d9e0f1a2b3_atividades_aula.py](../../migrations/versions/c8d9e0f1a2b3_atividades_aula.py)
19. `e1f2a3b4c5d6` — [e1f2a3b4c5d6_modelo_certificado.py](../../migrations/versions/e1f2a3b4c5d6_modelo_certificado.py)
20. `d6e7f8a9b0c1` — [d6e7f8a9b0c1_notnull_professor_oferta_g1.py](../../migrations/versions/d6e7f8a9b0c1_notnull_professor_oferta_g1.py)
21. `c9d0e1f2a3b4` — [c9d0e1f2a3b4_autor_lancamento_f1.py](../../migrations/versions/c9d0e1f2a3b4_autor_lancamento_f1.py)
22. `b5c6d7e8f9a0` — [b5c6d7e8f9a0_session_version.py](../../migrations/versions/b5c6d7e8f9a0_session_version.py)
23. `c1d2e3f4a5b6` — [c1d2e3f4a5b6_login_controle.py](../../migrations/versions/c1d2e3f4a5b6_login_controle.py)
24. `b02f2051bc1e` — [b02f2051bc1e_merge_heads_onda3c_inscricoes_seq.py](../../migrations/versions/b02f2051bc1e_merge_heads_onda3c_inscricoes_seq.py) — revisão de merge sem operações.

## 2. Revisão das migrations pendentes

“Lock” abaixo descreve o efeito esperado no PostgreSQL; locks reais dependem da versão, duração e plano do comando. Índices foram criados sem `CONCURRENTLY`.

| Revisão | Dados, DDL e locks | Guardas PG e risco de schema parcial | Downgrade |
|---|---|---|---|
| `d1e2f3a4b5c6` | Remove `curso.carga_horaria`; `DROP COLUMN` toma lock forte da tabela. | Sem guarda de coluna/tabela; falha se o schema divergir. | Recria nullable, sem recuperar valores: **perda irreversível**. |
| `5a676f37b9a3` | Converte colunas VARCHAR para DATE/TIME/ENUM e cria índices, inclusive únicos; conversão pode reescrever/bloquear tabelas e índice normal bloqueia escrita. | Verifica tipo atual e usa `IF NOT EXISTS` nos índices, mas não protege coluna/tabela ausente, valores inválidos ou duplicatas nos índices únicos. | Converte tipos de volta para VARCHAR, mas não remove os índices criados; não é reversão integral. |
| `b7c1d2e3f4a5` | Cria/associa sequência para `inscricoes.id`, define default e alinha `setval` ao máximo existente. | PostgreSQL-only; sequência usa `IF NOT EXISTS`. Assume tabela/coluna existentes e substitui ownership/defaults. | Remove default e sequência; pode remover sequência/default preexistente. |
| `311d554dfd6e` | Cria `turma_curso`, índices/FKs; adiciona `inscricoes.turma_curso_id`; cria ofertas de turmas e associa inscrições. `ADD COLUMN`/FK/index têm locks e validações. | Sem guards para tabela/coluna existente; UNIQUE/FK pode falhar com schema ou dados incompatíveis. Backfill só evita duplicar o par turma/curso. | Zera vínculos e remove a nova tabela; perde associações e dados de ofertas. |
| `8c4e1f9a7d32` | Adiciona três colunas de auditoria nullable em `turma_curso` e FK. | Inspeciona colunas e nome da FK; tabela ausente ou coluna existente com definição errada não é reparada. FK valida dados e bloqueia operações concorrentes. | Remove colunas/FK e perde auditoria gravada nelas. |
| `e7f3a1b9c4d5` | Remove UNIQUE legado; adiciona `turma_curso_id` em frequência/diário, FKs e índices; associa apenas turmas com exatamente uma oferta. | Inspeção de colunas, índices, constraints e FKs; schema parcialmente criado pode deixar tipos/constraints incoerentes. Índices únicos podem falhar com duplicatas. | Tem guarda contra duplicatas antes de restaurar UNIQUE; ao remover as colunas, perde os vínculos do backfill. |
| `d2e3f4a5b6c7` | Cria catálogo `centro_custo` e insere nomes deduplicados derivados de período, turma e oferta. | `CREATE TABLE` sem guarda de existência; consultas de origem usam `except Exception` e podem ocultar erro de coluna/tabela ao continuar o backfill. | `DROP TABLE` apaga catálogo e dados novos. |
| `a1b2c3d4e5f6` | Adiciona `turma_curso.programa` e copia o programa da turma por UPDATE. | Sem guardas; coluna já existente com migration não marcada causa falha. | Remove a coluna e os valores copiados/editados. |
| `c3d4e5f6a7b8` | Valida inscrições sem oferta e duplicatas ativas; define `turma_curso_id NOT NULL` e cria UNIQUE parcial. | Pré-checagens de dados antes do DDL; não é idempotente para índice/nullable parcialmente aplicado. DDL exige varredura/lock e índice único pode falhar. | Volta nullable e remove o índice, sem alterar linhas. |
| `d4e5f6a7b8c9` | Projeta programa da oferta principal para turma com `COALESCE`; define programa da oferta como NOT NULL. | Conta programas nulos antes do DDL; espera coluna e tabelas da cadeia anterior. Lock/varredura para NOT NULL. | Retorna nullable, mas não recupera o valor anterior de `turma.programa`. |
| `e5f6a7b8c9d0` | Adiciona vínculo de conselho à oferta, FK/índice, quatro campos em `turma_curso`, troca UNIQUE por índices parciais e faz dois backfills. | Guardas por inspeção; UNIQUE/FK/índices podem falhar em schema parcial ou dados duplicados. Coluna não nula com default `false` e FK têm locks de DDL/validação. | Checa duplicatas antes de recriar UNIQUE; remove vínculo/campos novos, perdendo dados atribuídos a ofertas. |
| `f6a7b8c9d0e1` | Pré-checa conselhos órfãos/inconsistentes; torna o vínculo NOT NULL e remove índice legado e `turma.conselho_concluido`. | Confere coluna e dados, mas helpers de inspeção convertem exceções em conjunto vazio; schema parcial pode levar a DDL inadequado. NOT NULL/drop tomam lock. | Recria flag derivada das ofertas, volta nullable e restaura índice; não recompõe exatamente o estado legado. |
| `a8b9c0d1e2f3` | Cria relação N:N entre diário e temas, copia `registro_aula.tema_id`; novo índice/FKs. | Sem guarda de tabela existente; falha se a estrutura/relacionamentos estiverem parciais. | Drop da relação perde associações N:N adicionadas após o backfill. |
| `5730d7c594ba` | Amplia `dias_semana`, cria grade por dia e materializa horários/dias efetivos; UPDATE/INSERT por oferta. ALTER de tipo e criação de tabela/constraints tomam locks. | Pré-checagens de tokens, duplicatas e pares de horário; inspeção de tabela/coluna e backfill idempotente por oferta. Tabela preexistente parcialmente populada é ignorada por inteiro. | Recusa grades não uniformes; se uniforme, projeta de volta e remove grade. Não reduz VARCHAR; horários distintos por dia não cabem no modelo legado. |
| `7c1d2e3f4a5b` | Recusa domingos e troca CHECK de 0–6 para 0–5; nenhuma atualização de dados. | Checa dia 6 e existência da tabela; no PostgreSQL pressupõe CHECK com o nome esperado, então drift do nome/constraint pode falhar. | Restaura domínio 0–6 sem alterar dados. |
| `8d2e3f4a5b6c` | Checa grade e remove seis colunas escalares de agenda; `DROP COLUMN` toma lock forte. | Idempotência por coluna. **Se a tabela da grade estiver ausente, a checagem retorna vazia e ainda permite remover as colunas**, risco em schema parcial. | Recria/projeta colunas; horário não uniforme vira NULL. A grade não é removida no downgrade. |
| `b7c8d9e0f1a2` | Cria catálogo de valor esportista, índice único funcional e coluna/FK/índice em frequência. | Sem guardas de existência para tabela, coluna e índice; replay em schema parcial falha. Coluna nova fica NULL nas linhas antigas. | Remove coluna e catálogo, perdendo valores cadastrados/associados. |
| `c8d9e0f1a2b3` | Adiciona `registro_aula.atividades` nullable, sem backfill. | ALTER direto, sem guarda de coluna; pode falhar se a coluna já existir sem revisão marcada. | DROP da coluna perde textos preenchidos depois. |
| `e1f2a3b4c5d6` | Cria `modelo_certificado` com FKs e UNIQUE. | Sem guarda de tabela existente; falha em schema parcial ou se referências estiverem ausentes. | DROP da tabela perde modelos cadastrados. |
| `d6e7f8a9b0c1` | Checa `professor_id IS NULL` e define NOT NULL; lock/varredura da tabela. | Verifica coluna, nulidade e dados antes do DDL; não corrige linhas. | Volta nullable sem tocar dados; reversível. |
| `c9d0e1f2a3b4` | Adiciona `autor_id`/`autor_nome` em frequência e resposta de conselho; histórico fica NULL. | Guarda colunas/tabelas; FK só é criada junto com coluna ausente, portanto coluna preexistente sem FK não é corrigida. DDL valida FK e bloqueia operações. | Remove colunas e apaga atribuições de autoria preenchidas após a revisão. |
| `b5c6d7e8f9a0` | Adiciona `user.session_version NOT NULL DEFAULT 0`; sem backfill explícito. | Inspeciona tabela/colunas; default constante é otimizado nas versões recentes do PG, mas o ALTER ainda requer lock. | Remove contador e perde o estado de versão/revogação. |
| `c1d2e3f4a5b6` | Cria `login_controle` e UNIQUE. | Retorna se a tabela já existir, mas não valida sua estrutura: tabela parcial pode ser aceita como aplicada. | Drop da tabela remove controles registrados. |
| `b02f2051bc1e` | Merge de heads; upgrade/downgrade sem operações. | Nenhum DDL ou dado. | No-op; seguro. |

## 3. Upgrade, contagens e schema

`flask db upgrade` foi executado com `DATABASE_URL` explicitamente apontado para `pautaon_rel_prod2`: **sucesso em 3,69 s, sem erros, 24 revisões aplicadas**; versão final `c1d2e3f4a5b6`. As 31 tabelas preexistentes mantiveram suas contagens. As sete tabelas novas aparecem com `Antes = inexistente`.

| Tabela | Antes | Depois |
|---|---:|---:|
| agenda_servico_social | 0 | 0 |
| alembic_version | 1 | 1 |
| aluno | 1.154 | 1.154 |
| atendimento | 1 | 1 |
| centro_custo | inexistente | 3 |
| configuracao_sistema | 18 | 18 |
| conselho_classe | 0 | 0 |
| conselho_pergunta | 5 | 5 |
| conselho_resposta | 0 | 0 |
| curso | 7 | 7 |
| dia_bloqueado | 14 | 14 |
| dia_bloqueado_turma | 0 | 0 |
| endereco_aluno | 111 | 111 |
| frequencia | 130 | 130 |
| inscricoes | 113 | 113 |
| log_acao | 949 | 949 |
| login_controle | inexistente | 0 |
| modelo_certificado | inexistente | 0 |
| nivel | 6 | 6 |
| opcao_proxima_turma | 0 | 0 |
| perfil_diversidade | 111 | 111 |
| perfil_socioeconomico | 111 | 111 |
| periodo_conselho | 0 | 0 |
| periodo_letivo | 2 | 2 |
| registro | 0 | 0 |
| registro_aula | 10 | 10 |
| registro_aula_tema | inexistente | 10 |
| responsavel_aluno | 82 | 82 |
| respostas_formulario | 0 | 0 |
| situacao_escolar | 103 | 103 |
| tema_aula | 63 | 63 |
| transferencia | 0 | 0 |
| turma | 12 | 12 |
| turma_curso | inexistente | 12 |
| turma_curso_horario | inexistente | 23 |
| unidade | 2 | 2 |
| user | 18 | 18 |
| valor_esportista | inexistente | 0 |

**Tipos e objetos pedidos**

- `aluno.documentos_entregues`: `JSONB` (`jsonb`) após upgrade.
- `perfil_diversidade.tipo_deficiencia`: existe como `VARCHAR(30)`, compatível com o modelo. Nenhuma das 24 revisões pendentes a cria; já estava no schema restaurado.
- Novas tabelas criadas pelo caminho pendente: `turma_curso`, `centro_custo`, `registro_aula_tema`, `turma_curso_horario`, `valor_esportista`, `modelo_certificado` e `login_controle`.
- Outras mudanças de schema incluem vínculos por oferta em inscrições/frequência/diário/conselho, colunas de auditoria/autoria, `programa`, `atividades`, versão de sessão e remoção das colunas escalares de agenda e `curso.carga_horaria`.

**Diferenças schema/modelos** — comparação das 37 tabelas ORM com as 38 tabelas do clone (a tabela adicional é `alembic_version`):

| Objeto | Diferença |
|---|---|
| `curso` | Banco tem colunas `updated_at`, `updated_by_id`, `updated_by_name` e FK de `updated_by_id` que não estão no modelo ORM. |
| `periodo_letivo.unidade_id` | Modelo declara nullable; banco está NOT NULL. |

Não houve outras diferenças de tabela/coluna/tipo/nulidade/FK. As diferenças textuais remanescentes nos CHECKs são casts/parênteses de expressão registrados pelo PostgreSQL; o índice funcional de `valor_esportista` usa `lower(nome)` como no modelo.

## 4. Smoke GET no clone — conexão somente leitura

O processo de teste usou `PGOPTIONS=-c default_transaction_read_only=on` e confirmou `default_transaction_read_only=on`. Papéis ativos disponíveis no clone: admin, gerência, pedagógico, professor e secretaria; não havia usuário ativo de serviço social. `200` indica sucesso; `302` é redirecionamento; `403` é a restrição de acesso esperada.

| Papel | `/` | `/dashboard` | `/painel` | `/conselho` | `/frequencia` | `/turma` | `/relatorios/painel` |
|---|---:|---:|---:|---:|---:|---:|---:|
| admin | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| gerência | 200 | 200 | 200 | 200 | 403 | 200 | 200 |
| pedagógico | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| professor | 200 | 200 | 200 | 200 | 200 | 403 | 403 |
| secretaria | 200 | 302 | 302 | 200 | 200 | 200 | 200 |

Não houve resposta 5xx. As restrições de frequência para gerência, lista de turmas para professor e painel de relatórios para professor foram respeitadas. O papel serviço social não foi exercitado por ausência de usuário no clone.

## 5. `unidade_id IS NULL` e escopo AJ10

Contagens por tabela do clone após upgrade; as exceções legítimas estão assinaladas. Todas as demais linhas com nulo foram contadas, sem selecionar nem imprimir registros.

| Tabela | NULL | Observação |
|---|---:|---|
| aluno | 1 | Ver contagem de inscrição abaixo |
| atendimento | 0 | |
| centro_custo | 0 | |
| configuracao_sistema | 18 | Legítimas |
| conselho_classe | 0 | |
| conselho_resposta | 0 | |
| curso | 0 | |
| dia_bloqueado | 0 | |
| dia_bloqueado_turma | 0 | |
| endereco_aluno | 0 | |
| frequencia | 130 | Backfill AJ10 candidato |
| log_acao | 332 | Legítimas |
| nivel | 0 | |
| perfil_diversidade | 0 | |
| perfil_socioeconomico | 0 | |
| periodo_conselho | 0 | |
| periodo_letivo | 0 | |
| registro | 0 | |
| registro_aula | 10 | Backfill AJ10 candidato |
| responsavel_aluno | 0 | |
| situacao_escolar | 0 | |
| tema_aula | 0 | |
| transferencia | 0 | |
| turma | 0 | |
| turma_curso | 0 | |
| user | 3 | Legítimas: admin 1, gerência 2 |
| valor_esportista | 0 | |

`configuracao_sistema`, `log_acao` e usuários admin/gerência foram mantidos fora do backfill. No clone, entre alunos com unidade nula, **1 não tem inscrição e 0 têm inscrição**; 0 têm unidade única derivável. No `pautaon` consultado, a mesma contagem é **1 sem inscrição, 0 com inscrição**, e 0 com unidade única derivável. Portanto, a mudança de escopo de aluno do [enturmado.py](../../app/services/enturmado.py) **não afeta linha de aluno da produção atual nem do dump**.

As contagens de nulos alvo diferem entre o banco `pautaon` atual e o dump restaurado: no atual são 52/4/78 (frequência/diário/resposta de conselho); no dump são 130/10/0. A variante foi ajustada aos dados do dump que ela efetivamente valida.

## 6. Backfill AJ10 em clones descartáveis

Variante local: `.tmp/aj9b_backfill_unidade_id_nulos.sql` (ignorada pelo Git). Ela valida as contagens esperadas 130/10/0, verifica vínculo inequívoco com turma/oferta, preserva unidades já preenchidas e não imprime IDs.

| Ensaio | Nulos antes (freq./diário/conselho) | UPDATEs tentados | Nulos depois | Total de linhas antes/depois |
|---|---|---|---|---|
| `ROLLBACK` | 130 / 10 / 0 | 130 / 10 / 0 | 130 / 10 / 0 | 130 / 10 / 0 → 130 / 10 / 0 |
| `COMMIT` | 130 / 10 / 0 | 130 / 10 / 0 | 0 / 0 / 0 | 130 / 10 / 0 → 130 / 10 / 0 |

As validações de parent unit passaram; os dados previamente preenchidos permaneceram iguais. Os dois clones descartáveis foram removidos e a ausência foi confirmada.

## 7. Rotas de autenticação Google

- As rotas `/auth/google/login`, `/auth/google/callback` e `/auth/google/confirmar-vinculo` estão registradas e são alcançáveis por URL direta; nenhuma exige login para iniciar a rota.
- No `create_app()` ensaiado, `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` e `GOOGLE_OAUTH_REDIRECT_URI` não chegam a `app.config` (as três flags efetivas ficaram falsas). Sem configuração, login, callback sem `state` e confirmação sem vínculo redirecionam para `/login` (`302`), sem iniciar autenticação. Não retornam 404.
- Com `client_id` e redirect configurados, mas sem `client_secret`, `/auth/google/login` ainda redireciona para `accounts.google.com` (`302`). Portanto a rota não valida o secret antes de iniciar o fluxo; o secret faltante não desativa a etapa de autorização.
- Não foi encontrada chamada de `auth.google_login` na UI de login; existe template de confirmação de vínculo, mas isso não equivale a botão de login.
- Nenhuma rota ou configuração foi alterada nesta prova.

## 8. Bancos reais — contagens antes/depois

Contagem por tabela em `pautaon` e `pautaon_ensaio`, antes e após a prova. Os dois snapshots têm os mesmos 38 nomes de tabela e todas as contagens coincidem linha a linha.

| Tabela | `pautaon` antes → depois | `pautaon_ensaio` antes → depois |
|---|---:|---:|
| agenda_servico_social | 0 → 0 | 0 → 0 |
| alembic_version | 1 → 1 | 1 → 1 |
| aluno | 1.155 → 1.155 | 1.166 → 1.166 |
| atendimento | 1 → 1 | 1 → 1 |
| centro_custo | 6 → 6 | 7 → 7 |
| configuracao_sistema | 7 → 7 | 7 → 7 |
| conselho_classe | 45 → 45 | 5 → 5 |
| conselho_pergunta | 12 → 12 | 10 → 10 |
| conselho_resposta | 78 → 78 | 6 → 6 |
| curso | 9 → 9 | 12 → 12 |
| dia_bloqueado | 11 → 11 | 11 → 11 |
| dia_bloqueado_turma | 0 → 0 | 0 → 0 |
| endereco_aluno | 112 → 112 | 112 → 112 |
| frequencia | 64 → 64 | 20 → 20 |
| inscricoes | 32 → 32 | 41 → 41 |
| log_acao | 1.204 → 1.204 | 1.747 → 1.747 |
| login_controle | 0 → 0 | 0 → 0 |
| modelo_certificado | 0 → 0 | 0 → 0 |
| nivel | 6 → 6 | 6 → 6 |
| opcao_proxima_turma | 0 → 0 | 2 → 2 |
| perfil_diversidade | 112 → 112 | 111 → 111 |
| perfil_socioeconomico | 112 → 112 | 112 → 112 |
| periodo_conselho | 1 → 1 | 0 → 0 |
| periodo_letivo | 2 → 2 | 5 → 5 |
| registro | 0 → 0 | 0 → 0 |
| registro_aula | 6 → 6 | 4 → 4 |
| registro_aula_tema | 7 → 7 | 4 → 4 |
| responsavel_aluno | 83 → 83 | 82 → 82 |
| respostas_formulario | 0 → 0 | 0 → 0 |
| situacao_escolar | 104 → 104 | 103 → 103 |
| tema_aula | 54 → 54 | 55 → 55 |
| transferencia | 0 → 0 | 1 → 1 |
| turma | 3 → 3 | 8 → 8 |
| turma_curso | 4 → 4 | 12 → 12 |
| turma_curso_horario | 8 → 8 | 20 → 20 |
| unidade | 2 → 2 | 4 → 4 |
| user | 22 → 22 | 25 → 25 |
| valor_esportista | 8 → 8 | 0 → 0 |
