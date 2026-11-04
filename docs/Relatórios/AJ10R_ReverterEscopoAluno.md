# AJ10-R — Reversão do escopo de aluno por inscrição

Data: 2026-11-04
Base de comparação: `314c50c^` (versão imediatamente anterior ao AJ10)

## Resultado

Foi revertido somente o escopo que atribuía unidade a alunos sem
`Aluno.unidade_id` usando inscrições/turmas. O comportamento voltou a ser:

- consultas de unidade incluem alunos cuja unidade própria corresponde ao
  filtro;
- alunos sem unidade própria não entram em um escopo de unidade, mesmo com
  inscrição em turma daquela unidade;
- consultas sem filtro de unidade continuam globais.

O trabalho foi feito no worktree `D:\pautaon\.tmp\aj10r_revert`, em commits
novos e sem reescrever histórico. Nenhuma migration foi criada, nenhum push foi
feito e nenhum dado de aluno foi lido ou registrado neste relatório.

## Escopo revertido

Removidos `cond_aluno_no_escopo_unidade` e `unidade_efetiva_aluno`, restaurando
os filtros por unidade própria nos seguintes leitores:

- `app/services/enturmado.py` e `app/services/aluno_status.py`;
- `app/relatorios/bi_filtros.py` e `app/relatorios/bi_alunos.py`;
- `app/registros/alunos.py` e `app/registros/turmas.py`;
- `app/relatorios/alunos.py` e `app/relatorios/painel_pedagogico/rota.py`;
- `app/main/dashboard_admin.py`, `app/main/dashboard_servico_social.py` e
  `app/main/secretaria.py`;
- somente as estatísticas de idade em `app/utils/logica.py`.

Os 11 leitores exceto `app/utils/logica.py` são idênticos ao baseline
pré-AJ10. Em `app/utils/logica.py`, a única diferença em relação ao baseline é
a correção mantida do cálculo de métricas do conselho: o diário é associado à
turma para aplicar o escopo da unidade.

Permaneceram intactos:

- escritores de `unidade_id` do conselho, frequência e registro de aula;
- `scripts/backfill_unidade_id_nulos.sql`;
- a correção do downgrade da revisão `3b7c9d1e4f20` e seus testes.

## Testes ajustados

Nenhum teste foi removido. Dois testes que exigiam a unidade derivada por
inscrição foram convertidos em verificações do comportamento pré-AJ10:

| Teste anterior | Teste atualizado | Motivo |
|---|---|---|
| `test_aluno_unidade_nula_usa_unidade_pai_sem_vazar_unidade` | `test_escopo_unidade_exige_unidade_propria_do_aluno` em `tests/test_aj6a_causa_real.py` | Verifica que o aluno com unidade própria continua no escopo e que o aluno sem unidade própria fica fora de listagens, status, enturmação e filtros BI por unidade. |
| `test_estatisticas_idade_isolam_alunos_da_unidade_errada` | `test_estatisticas_idade_nao_derivam_unidade_por_inscricao` em `tests/test_aj6a_causa_real.py` | Verifica que inscrição em turma não atribui unidade ao aluno nem o inclui na média dessa unidade. |

Os testes de escritores de unidade, do diário e do cadastro de aluno foram
mantidos; os módulos afetados e a suíte completa foram executados após a
reversão.

## Verificações

- **Ruff:** `F821,F811,F841,F401` nos 13 arquivos tocados — passou.
- **Testes focados:** 31 passaram em `test_aj6a_causa_real.py` e
  `test_enturmado.py`; os testes selecionados de escopo, escritores e diário
  passaram (7 testes).
- **Suíte completa, uma execução:** 1.635 passaram, 1 ignorado e 2 falharam.
  As falhas foram
  `test_anexo_pdf_valido_usa_uuid_e_download_protegido` e
  `test_modelo_png_valido_usa_uuid_headers_e_download`, em
  `tests/test_aj5d_upload_signature.py`. As duas esperam preservar no nome
  original os separadores de caminho de `..\..`; o comportamento observado
  sanitiza os nomes para `....anexo.pdf` e `....modelo.png`. Os mesmos dois
  testes falharam ao serem executados isoladamente no HEAD original, sem as
  mudanças AJ10-R. Nenhum arquivo desses testes foi alterado.
- **Paridade do código:** os leitores revertidos correspondem ao baseline
  `314c50c^`; a correção do diário foi comparada separadamente e permanece.

## Contagens dos bancos reais

As contagens foram obtidas por `SELECT`, com
`PGOPTIONS=-c default_transaction_read_only=on`; a conexão confirmou o modo
read-only. Cada mapa contém a contagem exata de linhas das 38 tabelas públicas.
Os mapas completos antes/depois foram idênticos:

| Banco | Tabelas | Linhas antes | Linhas depois | Mapas idênticos |
|---|---:|---:|---:|---|
| `pautaon` | 38 | 3.271 | 3.271 | Sim |
| `pautaon_ensaio` | 38 | 3.700 | 3.700 | Sim |

Nenhuma escrita foi executada nos bancos reais.

## Commits

| Tipo | Hash | Mensagem |
|---|---|---|
| Testes | `9ec976b` | `test(AJ10-R): assert legacy unit scope` |
| Testes | `ad4d65f` | `test(AJ10-R): persist own-unit student fixture` |
| Reversão | `c968c8d` | `revert(AJ10-R): restore explicit student unit scope` |

O commit deste próprio relatório é separado; seu hash é apresentado na entrega
e no histórico Git, pois um commit não pode conter o próprio hash sem criar
uma nova versão do commit.
