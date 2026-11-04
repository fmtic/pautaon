# AJ10 — `unidade_id` nulo e downgrade

## Escopo e segurança

- Branch `nova_feature`; sem push e sem migration nova.
- Nenhuma escrita foi feita em `pautaon` ou `pautaon_ensaio`. As consultas de comparação foram somente `SELECT`.
- Testes usam dados sintéticos. As duas worktrees de regressão foram removidas.
- A revisão de `3b7c9d1e4f20` só removeu do downgrade o `drop_column` de `perfil_diversidade.tipo_deficiencia`. `upgrade`, `revision` e `down_revision` não foram alterados.

## Revisão de leitores

O escopo compartilhado de aluno está em `app/services/enturmado.py:147-204`. Aluno com unidade própria continua no escopo dela; aluno sem unidade só é incluído quando suas inscrições apontam para turmas de uma única unidade. Sem turma ou com turmas em mais de uma unidade, permanece fora do escopo de unidades.

Leitores de alunos atualizados para esse critério:

- `app/services/aluno_status.py:184`.
- `app/relatorios/bi_filtros.py:102`; `app/relatorios/bi_alunos.py:461,472,554,676,769`.
- `app/registros/alunos.py:427,486-487`; `app/registros/turmas.py:1492,1669`.
- `app/relatorios/alunos.py:126,197`; `app/relatorios/painel_pedagogico/rota.py:146`.
- `app/main/dashboard_admin.py:26`; `app/main/dashboard_servico_social.py:22`; `app/main/secretaria.py:39`.
- `app/utils/logica.py:831,853-854`: médias gerais, por programa e por turma usam o mesmo conjunto permitido; a regressão também protege alunos explicitamente associados a outra unidade.

Para as tabelas filhas, não foram encontrados filtros de leitura por `Frequencia.unidade_id`, `RegistroAula.unidade_id` ou `ConselhoResposta.unidade_id`, nem SQL cru equivalente em `app/`. O escopo vem de `Turma`, oferta ou conselho pai nos seguintes leitores identificados: `app/relatorios/bi_alunos.py:58,103`, `app/relatorios/conselho.py:182`, `app/relatorios/observacoes.py:106`, `app/relatorios/painel_pedagogico/ficha_aluno.py:181`, `app/relatorios/painel_pedagogico/conselho.py:82`, `app/services/estatisticas_professor.py:92,105`, `app/utils/logica.py:404,416,919,1070`, `app/conselho.py:755,1106` e `app/registros/turmas.py:2882,3101`.

Foi encontrada uma exceção efetiva: `app/utils/logica.py:1070` filtrava o progresso do diário por `RegistroAula.unidade_id`, zerando o resultado para registros legados nulos. O leitor agora junta `Turma` e usa `Turma.unidade_id`. `tests/test_aj6a_causa_real.py:808` prova que um diário com unidade nula entra no progresso da unidade correta.

O filtro próprio da listagem de atendimentos em `app/registros/atendimentos.py:150` permanece baseado na unidade do aluno; não é leitor das tabelas alvo de frequência, diário ou conselho. O único aluno real sem unidade não tem inscrição e, portanto, não há unidade pai inequívoca que permita ampliar esse escopo com segurança.

## Escritores e aluno sem unidade

- Conselho: `salvar_conselho` grava a unidade da turma ao criar a resposta e preenche unidade nula em resposta existente (`app/conselho.py:931,985`). Não muda autoria nem logging.
- Frequência e diário: `salvar_frequencia` já gravava a unidade da turma ao criar e preenchia valor nulo em updates (`app/utils/logica.py:653,760,767,784,796`). Os testes cobrem esses dois caminhos.
- Aluno: `novo_aluno` grava a unidade informada (`app/registros/alunos.py:515,595`; `tests/test_aj5_cadastro_aluno_form.py:120`). O aluno existente sem unidade não foi alterado.
- Consultas somente leitura confirmaram que o único `aluno.unidade_id IS NULL` em `pautaon` é o ID **269**, com **zero inscrições**. Assim, ele não aparece em listagens por unidade: nenhuma unidade pode ser inferida. O registro foi preservado.

## Backfill preparado, não executado

`scripts/backfill_unidade_id_nulos.sql` é rollback-first: `\set ON_ERROR_STOP on`, `BEGIN`, contagens esperadas (frequência 52, diário 4, respostas 78), validação de parent/ambiguidade, atualizações apenas de linhas nulas, `RETURNING id`, verificações finais e `ROLLBACK`; `COMMIT` fica comentado. Snapshots temporários dentro da transação verificam que unidades já preenchidas não mudaram. `aluno` fica fora do script por não ter unidade pai derivável.

**Validação pendente:** não foi possível executar o script em clone `TEMPLATE`. Uma consulta a `pg_stat_activity` encontrou uma sessão `idle` adicional em `pautaon`, que bloqueia `CREATE DATABASE ... TEMPLATE pautaon`. Nenhuma sessão foi encerrada, nenhum clone foi criado e nenhum `DROP DATABASE` foi necessário. Nem a execução com `ROLLBACK` nem a variante com `COMMIT` foi feita. É necessária nova janela com o banco sem conexões, ou autorização explícita para validar por clone lógico `pg_dump`/restore.

## Migration

O downgrade isolado de `3b7c9d1e4f20` foi exercitado em clone descartável: `perfil_diversidade.tipo_deficiencia` e seus quatro valores não nulos foram preservados. A tentativa de downgrade da cadeia inteira parou antes dessa revisão em `5730d7c594ba`, por uma falha preexistente relacionada a horários de ofertas; o clone foi removido. A correção da revisão está no commit `8cb3350a6f164de11a228f8169dea928ed7174a1`.

## Bancos reais — somente leitura

Foram comparadas as contagens de todas as **38 tabelas** antes e depois; não houve diferença em nenhuma tabela, inclusive `log_acao`. Totais antes = depois:

| Banco | `aluno` | `conselho_resposta` | `frequencia` | `registro_aula` | `log_acao` |
|---|---:|---:|---:|---:|---:|
| `pautaon` | 1155 | 78 | 64 | 6 | 1198 |
| `pautaon_ensaio` | 1166 | 6 | 20 | 4 | 1747 |

Nulos de `unidade_id` após a comparação:

| Banco | `aluno` | `conselho_resposta` | `frequencia` | `registro_aula` |
|---|---:|---:|---:|---:|
| `pautaon` | 1 | 78 | 52 | 4 |
| `pautaon_ensaio` | 1 | 0 | 0 | 0 |

## Testes e qualidade

- Suíte completa final: **1614 passed, 0 failed, 0 skipped**, 956 warnings, 1184,83 s.
- Ruff `F821,F811,F841,F401` passou nos arquivos Python alterados.
- As regressões falharam como esperado na worktree pré-fix e passaram após a correção; a worktree foi removida. A matriz `tests/test_aj6b6_matriz_rotas_professor.py` e `tests/test_aj6b7_complemento.py` ficou coberta pela suíte focalizada e pela completa.
- Uma execução completa anterior teve uma falha transitória em `tests/test_valor_esportista_nao_regressao.py::test_pauta_impressa_identica_com_e_sem_valor`: somente o carimbo de minuto no HTML diferiu. O teste isolado passou e a suíte completa final passou; nenhum arquivo desse teste foi alterado.

## Commits

- Migration: `8cb3350a6f164de11a228f8169dea928ed7174a1`.
- Testes: `1f58565a4cc60d0baee9443c232a62ca27a831e1`, `372fb868f5e65aad436c5f0d8562ef46f37e56d2`, `c18ade6427608543b48c683bfcba06bf42b15bb1`, `75f6915b565f1504d96e42716898ba082e36c4d0`, `1bec27e083231c07f8b9bde0b383c1a280997743`, `7d4273e838458d31931fafb2b4ce521597e44b5f`.
- Correções de leitores/escritores e script preparado: `314c50c4e56a7791e59b5a819204fae328d5b70b`.
- Documentação e atualização desta nota no MER foram commitadas separadamente; o hash do commit de documentação é informado na entrega.
