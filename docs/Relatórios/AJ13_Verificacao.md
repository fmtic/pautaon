# AJ13 — Verificação pré-release

## Escopo e segurança

O clone isolado `pautaon_aj13_20261104` foi restaurado do backup
`instance/backups/pautaon_producao_2026-11-03.dump` e atualizado até a revisão
Alembic `c1d2e3f4a5b6 (head)`. A validação de rotas e indicadores ocorreu no
clone; `pautaon` e `pautaon_ensaio` foram consultados apenas em transações
read-only. O clone foi removido ao final. Nenhuma identidade ou dado pessoal é
registrado neste relatório.

## Suíte e investigação dos testes AJ5-D

Os testes `test_anexo_pdf_valido_usa_uuid_e_download_protegido` e
`test_modelo_png_valido_usa_uuid_headers_e_download` passaram na execução
direcionada: **24 passed**. A sanitização não foi alterada.

Na comparação do snapshot AJ9 (`868ddc0`) com o HEAD (`162e38e`), não houve
mudanças nos manifests `requirements.txt`, `requirements-dev.txt` ou
`pyproject.toml`. O ambiente usado foi Windows, Python 3.14.7, Werkzeug 3.1.7,
Pillow 12.1.1 e SQLAlchemy 2.0.48; o lock do projeto/AJ9 fixa Werkzeug 3.1.9 e
Pillow 13.0.0. Portanto, há divergência entre versões instaladas e fixadas,
mas os dois testes passam no ambiente observado e não foi possível atribuir a
falha relatada a essa divergência, a uma mudança de código ou ao sistema
operacional sem reproduzir o ambiente que falhou.

O único skip identificado era `test_nada_gravado_no_disco_na_falha`: o teste
pulava quando o diretório de uploads não existia. O teste foi ajustado para
usar um diretório temporário isolado, permitindo verificar efetivamente que
uma falha de validação não grava arquivos. Resultado final da suíte completa:
**1.638 passed, 0 failed, 0 skipped** (990,95 s). A suíte direcionada às
regressões AJ13 teve **52 passed**.

O Ruff reportou 24 ocorrências nos arquivos alterados; a comparação com os
mesmos arquivos no HEAD confirmou que todas já existiam, sem achados novos.

## Varredura GET por papel

Foram usados registros da unidade ativa de cada usuário. Para o professor,
“própria” e “outra” distinguem a oferta atribuída ao próprio professor e a
atribuída a outro professor. Um `403` listado como esperado é autorização por
papel ou vínculo da oferta; não houve `404` nem `5xx` na amostra.

| Endpoint/fluxo | Admin | Gerência | Pedagógico | Secretaria | Professor |
|---|---:|---:|---:|---:|---:|
| Ver turma | 200 | 200 | 200 | 200 | própria 200; outra 403 |
| Imprimir pauta | 200 | 403 | 200 | 200 | própria 200; outra 403 |
| Observações | 200 | 403 | 200 | 200 | própria 200; outra 403 |
| Avaliar turma | 200 | 200 | 200 | 200 | própria 200; outra 403 |
| Frequência | 200 | 403 | 200 | 200 | própria 200; outra 403 |
| Conselho/lançamento | 200 | 200 | 200 | 200 | própria 200; outra 403 |
| Histórico do aluno | 200 | 200 | 200 | 200 | 200 |
| Histórico de atendimentos do aluno | 200 | 200 | 200 | 200 | 403 |
| Detalhe do atendimento | 200 | 200 | N/A¹ | 200 | 403 |

Classificação dos `403`: gerência em impressão, observações e frequência —
esperado por papel; professor em atendimentos — esperado por papel; professor
em qualquer um dos seis fluxos de turma/oferta de outro professor — esperado
pelo vínculo à oferta. Não houve `403` ou `404` inesperado por unidade na
amostra.

¹ Não havia usuário pedagógico na unidade do único atendimento usado para esse
fluxo.

Em `/trocar-senha`, gerência, professor e secretaria receberam `302` porque
as contas usadas são federadas (`is_ad_user`) e a rota redireciona contas
federadas ao painel. Admin e pedagógico receberam `200` por serem contas
locais.

## ALU-004 e execução dos indicadores

ALU-004 agora compara datas usando objetos `date`, inclusive nos limites
derivados dos períodos de referência, sem alterar a regra de negócio. Foi
adicionado teste de regressão que compila a consulta no dialeto PostgreSQL e
confirma binds `Date`; esse teste falha com os valores string anteriores.

Os 61 códigos foram executados com `executar_indicador` no clone. Os únicos
códigos com erro foram **INS-006** e **INS-007**, ambos com `ValueError`,
conforme esperado.

## FRE-005, ALU-001 e ALU-002

Para uma turma e um período do clone, FRE-005 no BI foi **63,8%** e o painel
pedagógico também mostrou **63,8%**, calculados sobre **130 lançamentos**. Não
houve diferença.

ALU-001 contou **1.153** e ALU-002 contou **1.154**. A diferença é explicada
por **1 aluno ativo sem `unidade_id`**. As duas unidades ativas tinham período
vigente; não havia aluno ativo associado a unidade sem período vigente.

## Integridade das bases originais

As contagens foram obtidas antes e depois em transações read-only. Todas as 38
tabelas permaneceram idênticas:

| Tabela | pautaon antes | pautaon depois | pautaon_ensaio antes | pautaon_ensaio depois |
|---|---:|---:|---:|---:|
| agenda_servico_social | 0 | 0 | 0 | 0 |
| alembic_version | 1 | 1 | 1 | 1 |
| aluno | 1155 | 1155 | 1166 | 1166 |
| atendimento | 1 | 1 | 1 | 1 |
| centro_custo | 6 | 6 | 7 | 7 |
| configuracao_sistema | 7 | 7 | 7 | 7 |
| conselho_classe | 45 | 45 | 5 | 5 |
| conselho_pergunta | 12 | 12 | 10 | 10 |
| conselho_resposta | 78 | 78 | 6 | 6 |
| curso | 9 | 9 | 12 | 12 |
| dia_bloqueado | 11 | 11 | 11 | 11 |
| dia_bloqueado_turma | 0 | 0 | 0 | 0 |
| endereco_aluno | 112 | 112 | 112 | 112 |
| frequencia | 64 | 64 | 20 | 20 |
| inscricoes | 32 | 32 | 41 | 41 |
| log_acao | 1206 | 1206 | 1747 | 1747 |
| login_controle | 0 | 0 | 0 | 0 |
| modelo_certificado | 0 | 0 | 0 | 0 |
| nivel | 6 | 6 | 6 | 6 |
| opcao_proxima_turma | 0 | 0 | 2 | 2 |
| perfil_diversidade | 112 | 112 | 111 | 111 |
| perfil_socioeconomico | 112 | 112 | 112 | 112 |
| periodo_conselho | 1 | 1 | 0 | 0 |
| periodo_letivo | 2 | 2 | 5 | 5 |
| registro | 0 | 0 | 0 | 0 |
| registro_aula | 6 | 6 | 4 | 4 |
| registro_aula_tema | 7 | 7 | 4 | 4 |
| responsavel_aluno | 83 | 83 | 82 | 82 |
| respostas_formulario | 0 | 0 | 0 | 0 |
| situacao_escolar | 104 | 104 | 103 | 103 |
| tema_aula | 54 | 54 | 55 | 55 |
| transferencia | 0 | 0 | 1 | 1 |
| turma | 3 | 3 | 8 | 8 |
| turma_curso | 4 | 4 | 12 | 12 |
| turma_curso_horario | 8 | 8 | 20 | 20 |
| unidade | 2 | 2 | 4 | 4 |
| user | 22 | 22 | 25 | 25 |
| valor_esportista | 8 | 8 | 0 | 0 |

## Encerramento do clone

O banco `pautaon_aj13_20261104` foi removido com `DROP DATABASE` e sua ausência
foi confirmada. `pautaon_rel_prod4` não existia na verificação final; nenhum
banco foi removido além do clone AJ13.
