# AJ12 — Auditoria do catálogo de indicadores do BI

**Escopo:** comparar o catálogo atualizado em 2026-09-29 com o despacho do BI (`app/relatorios/bi.py`, `app/relatorios/bi_alunos.py`, `app/services/aluno_status.py`, `app/relatorios/bi_filtros.py` e serviços relacionados); conferir as hipóteses e os invariantes solicitados no clone `pautaon_rel_prod4`, restaurado e atualizado até `c1d2e3f4a5b6`.

**Privacidade e escrita:** nenhum dado pessoal, nome de aluno ou identificador de aluno foi registrado. A leitura do clone e dos bancos reais foi planejada como somente leitura (`PGOPTIONS=-c default_transaction_read_only=on`). Nenhum código ou catálogo foi alterado; este relatório é o único artefato AJ12.

**Limite de verificação operacional:** a execução inicial dos 61 códigos e os agregados abaixo estão preservados da execução anterior. Na tentativa de retomada em 2026-11-04, o servidor local aceitou conexões, mas as credenciais PostgreSQL configuradas falharam na autenticação tanto por SQLAlchemy quanto por `psql`; o PostgreSQL MCP também falhou ao inicializar. Por isso, não foi possível repetir as consultas finais, comparar contagens posteriores dos bancos reais ou confirmar o `DROP DATABASE` do clone. Os resultados marcados como não verificados não devem ser interpretados como prova de igualdade nem de remoção do clone.

## 1. Comparação dos 61 indicadores

Referências à implementação apontam para funções e linhas em `app/relatorios/bi_alunos.py`, salvo indicação em contrário. O mapeamento de serviço/código está em `app/relatorios/bi.py:12-70`. O catálogo contém 61 itens; 59 estão mapeados. `INS-006` e `INS-007` constam no catálogo, mas não têm função mapeada.

| Código | Catálogo diz | Código faz | Divergência? | Impacto |
|---|---|---|---|---|
| ALU-001 | Cadastros ativos no período: enturmados + não enturmados | Conta o resultado do classificador de status por período/unidade | Não | — |
| ALU-002 | Alunos com `Aluno.ativo=True` | Conta cadastro ativo; unidade é `Aluno.unidade_id`; filtros acadêmicos usam inscrição/oferta | Não | Universo cadastral, não o de enturmação |
| ALU-003 | Alunos com `Aluno.ativo=False` | Conta cadastro inativo; filtros acadêmicos usam inscrição/oferta | Não | — |
| ALU-004 | Cadastros criados no intervalo/período | Compara `func.date(Aluno.created_at)` com strings ISO; no PostgreSQL ocorre `date >= character varying` | **Sim — erro visível** | Indicador falha com `ProgrammingError`, em vez de retornar contagem |
| ALU-005 | Sexo dos enturmados P; perfil estruturado e JSON legado | Usa status Novo/Renovado/Retornante e fallback JSON quando não há perfil estruturado | Não | Universo limitado a alunos ativos e unidade própria |
| ALU-006 | Faixa etária dos enturmados P, com faixa não informada | Usa status P e data de nascimento; calcula idade na data corrente | Parcial | O catálogo não fixa a data de referência da idade |
| ALU-007 | PCD enturmados P, perfil ou JSON legado | Usa `PerfilDiversidade.saude_laudo`; JSON legado só quando não existe perfil | Não | A regra de fallback é condicional; diverge do universo de DIV-001 |
| ALU-008 | Cadastrados por unidade, sem status de enturmação | Junta `Aluno.unidade_id` a `Unidade`, sem filtro de ativo | Não | `unidade_id=NULL` não entra em nenhuma unidade |
| ALU-009 | Enturmados P/D por curso; curso da oferta | Seleciona status P e agrupa pelas ofertas ativas em P; turno seleciona coorte P/P-1, mas a agregação posterior considera as ofertas P dos alunos selecionados | Parcial | Um filtro de turno pode retornar cursos/ofertas de outros turnos para alunos da coorte |
| ALU-010 | Alunos distintos por turma, uma vez por turma | Conta distintos com status P; requer aluno ativo, unidade própria e vínculo/oferta efetiva; curso/professor usam oferta | Parcial | O catálogo não explicita que exclui cadastros inativos e alunos sem status P |
| ALU-011 | Enturmados no período: Novo + Renovado + Retornante | Conta status P; classificador restringe a `Aluno.ativo=True` e `Aluno.unidade_id` da unidade do período | Não | NULL de unidade própria fica fora, sem inferência pela inscrição |
| ALU-012 | Não enturmados ativos: Em janela, Não renovado, Desenturmado e Outros | Soma esses quatro status no mesmo universo cadastral ativo | Não | `Outros` é o status residual (sem histórico anterior e sem inscrição em P), não um indicador separado |
| ALU-013 | Novos no período, sem inscrição anterior na unidade | Status Novo se não há inscrição em qualquer período anterior da unidade | Não | — |
| ALU-014 | Renovados com vínculo em P-1 e primeira inscrição em P até o 14º dia | Usa `data_inicio(P)+JANELA_RENOVACAO_DIAS` e compara inclusivamente | Parcial | Redação deve esclarecer se o início é “dia 0” ou “dia 1” para evitar uma diferença de um dia |
| ALU-015 | Enturmados com histórico, não renovados | Status Retornante: vínculo atual, histórico anterior e não classificado como renovado | Não | — |
| ALU-016 | Não renovados após fechar a janela | Conta somente alunos ativos, da unidade própria, com vínculo em P-1 e sem vínculo atual após a janela | Não | — |
| ALU-017 | Em janela de renovação | Conta somente alunos ativos, da unidade própria, com vínculo em P-1 e sem vínculo atual enquanto a janela está aberta | Não | — |
| ALU-018 | Desenturmados com inscrição histórica em P e sem vínculo atual | Conta somente alunos ativos, da unidade própria; a inscrição histórica é limitada a turma ativa de P | Parcial | A condição “turma ativa” não está explícita na descrição do catálogo |
| INS-001 | Volume total de inscrições | Conta todas as inscrições ligadas a turmas ativas; não exige `Inscricao.ativo=True` | Não | “Total” inclui ativas e inativas |
| INS-002 | Inscrições ativas | Filtra `Inscricao.ativo=True` e turma ativa | Não | — |
| INS-003 | Inscrições encerradas/inativas | Filtra `Inscricao.ativo=False` e turma ativa | Não | É duplicado de INS-005 |
| INS-004 | Novas inscrições efetuadas no período | Conta inscrições no escopo de turma/período; filtros de data usam `Inscricao.data_inicio`, sem critério próprio de “novo” nem `created_at` | **Sim — número/definição** | Sem intervalo de datas, o resultado corresponde ao total INS-001; “novas” não mede criação no período |
| INS-005 | Desativações | Usa a mesma condição de INS-003 (`Inscricao.ativo=False`) | **Sim — duplicidade** | Dois códigos e rótulos para a mesma contagem |
| INS-006 | Motivos de desativação | Sem implementação; `executar_indicador` lança `ValueError` | **Sim — não implementado** | Aparece na lista da Central, mas não produz dados |
| INS-007 | Tempo médio de permanência | Sem implementação; `executar_indicador` lança `ValueError` | **Sim — não implementado** | Aparece na lista da Central, mas não produz dados |
| INS-008 | Inscrições por curso, curso da oferta | Conta inscrições ligadas a turma ativa, agrupadas por `TurmaCurso.curso_id`; não filtra status da inscrição | Não | Soma pode diferir de INS-001 se houver inscrição sem curso/oferta correspondente |
| FRE-001 | Total de lançamentos | Conta linhas de frequência em turmas ativas, incluindo conceitos fora das categorias de presença/falta | Não | Não é contagem de alunos nem de dias |
| FRE-002 | Presenças A/B/C/D | Conta linhas com conceito A, B, C ou D | Não | — |
| FRE-003 | Faltas não justificadas | Conta linhas F | Não | — |
| FRE-004 | Faltas justificadas | Conta linhas J | Não | J fica fora do denominador percentual |
| FRE-005 | Frequência média global, sem J | Calcula `soma(presenças)/(soma(presenças)+soma(F))`, ponderada pelo número de lançamentos | Parcial | “Média dos alunos” pode ser lida como média aritmética dos percentuais individuais; o código não faz essa média |
| FRE-006 | Alunos com frequência ≥90% | Classifica percentuais individuais arredondados a uma casa; agrega linhas contáveis em turmas ativas | Não | O código não restringe `Aluno.ativo`; define alunos pelos lançamentos de frequência |
| FRE-007 | Alunos com frequência 75–89% | Faixa mid do serviço compartilhado, sobre o percentual individual arredondado | Não | Mesmo universo de FRE-006 |
| FRE-008 | Alunos com frequência <75% | Faixa lo do serviço compartilhado, sobre o percentual individual arredondado | Não | Mesmo universo de FRE-006 |
| FRE-009 | Frequência percentual por turma | Agrega todas as linhas contáveis da turma, inclusive legado; com filtros de curso/professor, seleciona turmas pelas ofertas | Não | Frequência é por linhas de aluno/conceito, não por dias distintos |
| FRE-010 | Frequência percentual por curso/oferta | Agrega por oferta; linha legada só é atribuída quando a turma tem exatamente uma oferta ativa | Não | Sem atribuição de legado em turma com múltiplas ofertas |
| TUR-001 | Total geral de turmas | Conta apenas `Turma.ativo=True` | **Parcial — catálogo** | Se “total geral” inclui inativas, a contagem diverge; no clone coincide com TUR-002 |
| TUR-002 | Turmas ativas | Conta `Turma.ativo=True` | Não | — |
| TUR-003 | Equivalente a ALU-010 | Mapeia para a mesma função `alunos_por_turma` | Não | Duplicado deliberado |
| TUR-004 | Média de alunos ativos por turma | Denominador: turmas ativas; numerador: linhas de `Inscricao` que satisfazem o vínculo ativo/oferta efetiva; não exige `Aluno.ativo` nem conta aluno distinto | **Sim — universo/medida** | Pode contar mais de uma inscrição do mesmo aluno na turma e incluir cadastro inativo |
| TUR-005 | Turmas por curso | Agrupa por `Turma.curso_id`, não pelo curso das ofertas | Parcial | Confirmada a hipótese; em turma multi-oferta o resultado não representa cursos efetivamente ofertados |
| TUR-006 | Turmas por período | Conta turmas ativas agrupadas por período | Parcial | A exclusão de turmas inativas não está descrita |
| TUR-007 | Turmas por unidade | Conta turmas ativas agrupadas por unidade | Parcial | A exclusão de turmas inativas não está descrita |
| TUR-008 | Turmas sob responsabilidade de cada professor | Agrupa por `Turma.professor_id` e associa `User`; não usa `TurmaCurso.professor_id` | Parcial | Confirmada a hipótese; decisão necessária para turmas com ofertas/professores distintos |
| AUL-001 | Total de aulas registradas | Conta linhas de `RegistroAula`; filtro curso/professor usa oferta e a regra de legado D2 | Não | Mede registros, não dias distintos |
| AUL-002 | Aulas registradas por turma | Conta linhas de `RegistroAula` por turma | Não | A unidade é registro; a soma não é necessariamente número de dias |
| AUL-003 | Aulas registradas por período | Conta linhas de `RegistroAula` por período | Não | — |
| AUL-004 | Aulas por professor | Agrupa pelo professor da oferta do registro; legado só entra pela oferta ativa única | Não | Não usa `Turma.professor_id` |
| AUL-005 | Aulas por curso | Agrupa pelo curso da oferta do registro; legado só entra pela oferta ativa única | Não | — |
| AUL-006 | Aulas por unidade | Conta registros pela unidade da turma | Não | — |
| AUL-007 | Aulas por tema | Junta a relação N:N `RegistroAula.temas` e conta registros distintos por tema | Parcial | Uma aula com vários temas contribui em cada tema; a soma pode exceder AUL-001 |
| AUL-008 | Aulas por dia | Agrupa registros pela data de `RegistroAula` | Não | Conta registros por data, não dias únicos |
| SOC-001 | Alunos por faixa de renda | Faz outer join com perfil socioeconômico e conta Aluno; sem perfil/renda nula vai para “Não informado”; não restringe `Aluno.ativo` | Parcial | Catálogo não define universo ativo/inativo |
| SOC-002 | Beneficiários de programas sociais | Filtra `beneficio_social_status == "Sim"`; não restringe `Aluno.ativo` | Parcial | “Programas” no plural é apresentado por um campo binário/status único |
| DIV-001 | PCD por tipo declarado | Filtra apenas `PerfilDiversidade.saude_laudo=True` e agrupa `tipo_deficiencia`; não usa JSON legado | **Sim — universo** | Pode diferir de ALU-007, que tem fallback JSON e conta por aluno |
| ATD-001 | Atendimentos por unidade/período | Filtra unidade e datas de atendimento; período acadêmico é obtido por inscrição/turma, sem restringir inscrição ativa, turma ativa ou aluno ativo | Parcial | “Período” pode significar data do atendimento, mas `periodo_letivo_id` filtra a turma vinculada |
| CRU-001 | Frequência crítica (<75%) por vulnerabilidade | Usa percentual individual contábil arredondado; perfil ausente/valor falso entra em “Não vulnerável” | Parcial | A ausência de perfil é tratada como “Não”, não como desconhecido |
| CRU-002 | Participantes de conselho por raça/cor | Conta alunos distintos com `ConselhoClasse` e `PerfilDiversidade`; não consulta `ConselhoResposta` nem conclusão da oferta | **Sim — regra de negócio** | Um registro de conselho vazio pode contar como participante; o GET de lançamento cria registros-base (conselho.py:724-730) |
| CRU-003 | Alunos sem internet por bairro/zona | Usa `EnderecoAluno.possui_acesso_internet=False`; agrupa endereço e conta aluno distinto, sem restrição de `Aluno.ativo` | Parcial | Nulos/desconhecidos não entram; universo cadastral não está explicitado |
| CRU-004 | Transferências por curso de origem | Junta `Transferencia.turma_origem_id` a `Turma` e `Curso` por `Turma.curso_id` | Não | Confirmada a hipótese: curso da turma de origem, não da oferta |
| CRU-005 | Desempenho de conselho por faixa de renda | Usa `ConselhoClasse.situacao_final`; qualquer situação contendo “APROVADO” é aprovado, demais/null são “Outros” | **Sim — regra/definição** | Não mede respostas nem conselho concluído; o nome “desempenho” é mais amplo que a classificação efetiva |

### Universo e filtros transversais

- `status_alunos_para_bi` escolhe o período vigente por unidade; `status_alunos` inclui apenas `Aluno.ativo=True` e `Aluno.unidade_id == PeriodoLetivo.unidade_id` (`aluno_status.py:47-70, 181-182`). Desde AJ10-R, a unidade não é inferida por inscrição: aluno sem unidade própria não entra nos indicadores de status, mesmo que tenha inscrição. `bi_filtros.py:86-105` também filtra unidade diretamente em `Aluno.unidade_id`.
- O vínculo vigente no período presente/futuro requer `Inscricao.ativo=True` e oferta efetiva; turmas inativas são excluídas do status (`aluno_status.py:207-220, 237-246`; predicado comum em `enturmado.py:35-115`). O histórico anterior aceita inscrições inativas (`aluno_status.py:251-270`).
- O filtro de turno dos indicadores de status forma uma coorte das inscrições em P/P-1, mas a classificação usa histórico completo (`aluno_status.py:110-135`). ALU-009/010 usam IDs dessa coorte e depois consultam vínculos do período; o filtro não necessariamente limita cada linha final ao mesmo turno.
- Frequência e registro de aula não aplicam, em geral, `Aluno.ativo`; partem das linhas e de turmas ativas. Filtros de curso/professor usam `TurmaCurso`; linhas legadas nullable só podem ser atribuídas a curso/professor se há exatamente uma oferta ativa (`bi_filtros.py:20-29, 34-80`; `frequencia_oferta.py:9-14`).

## 2. Hipóteses verificadas

| Hipótese | Resultado e evidência |
|---|---|
| TUR-008 usa `Turma.professor_id` | **Confirmada.** `bi_alunos.py:1824-1884` junta `User.id == Turma.professor_id`. |
| TUR-005 usa curso da turma | **Confirmada.** `bi_alunos.py:1636-1693` agrupa por `Curso.id == Turma.curso_id`. |
| CRU-004 usa curso de origem da turma, não oferta | **Confirmada.** `bi_alunos.py:2739-2789` junta `Transferencia.turma_origem_id` e `Curso.id == Turma.curso_id`. |
| CRU-002/005 contam ConselhoClasse, não respostas ou conclusão | **Confirmada.** CRU-002 consulta ConselhoClasse e PerfilDiversidade (`bi_alunos.py:2633-2687`); CRU-005 consulta `ConselhoClasse.situacao_final` e PerfilSocioeconomico (`2791-2879`). O GET cria registros-base vazios em `conselho.py:724-730`; não há filtro por resposta/conclusão nesses serviços. |
| DIV-001 usa `tipo_deficiencia`; ALU-007 usa `saude_laudo` e JSON legado | **Confirmada com ressalva.** DIV-001 agrupa tipo e exige laudo estruturado (`bi_alunos.py:2478-2518`). ALU-007 usa o campo estruturado quando há perfil e recorre ao JSON apenas se o perfil inexiste (`476-534`). |
| AUL-001/002 contam RegistroAula; painel conta dias distintos | **Parcialmente confirmada.** AUL-001/002 contam `RegistroAula.id` (`1886-1946`). O painel não conta dias distintos: agrega linhas de `Frequencia` contáveis por aluno/conceito (`frequencia_oferta.py:328-364`, `painel_pedagogico/periodo.py:47-59`). São medidas com unidades diferentes. |
| AUL-007 usa N:N de temas e a soma pode exceder AUL-001 | **Confirmada como possibilidade.** Usa `RegistroAula.temas` e `count(distinct RegistroAula.id)` por tema (`bi_alunos.py:2253-2293`; relação em `models/aulas.py:48-66, 230-233`). No clone a soma observada foi 10, igual a AUL-001; não houve excedente observado. |
| TUR-004 usa inscrição ativa e ALU-010 não restringe aluno ativo | **Hipótese refutada em parte.** TUR-004 conta inscrições vigentes sem exigir `Aluno.ativo` (`bi_alunos.py:1584-1633`). ALU-010 seleciona status P via `status_alunos_para_bi`, portanto restringe `Aluno.ativo` (`715-815`, `aluno_status.py:181-182`). TUR-004 também não usa aluno distinto. |
| ALU-016/017/018 restringem `Aluno.ativo` | **Confirmada.** Os três chamam `status_alunos_para_bi`, que parte do filtro `Aluno.ativo=True` (`bi_alunos.py:2924-2941`, `aluno_status.py:181-182`). |
| Definição real de “Outros” | É o resíduo do classificador: aluno ativo da unidade, sem vínculo atual, sem inscrição em P e sem histórico em período anterior (`aluno_status.py:295-303`). Não é categoria de inscrição nem código separado no catálogo. |
| INS-005 versus INS-003 | **Duplicados.** Ambos contam `Inscricao.ativo=False` em turma ativa (`bi_alunos.py:886-983`). |
| Campo de data de INS-004 | **`Inscricao.data_inicio`.** Os filtros de data são aplicados nessa coluna (`bi_alunos.py:921-952`, `bi_filtros.py:145-155`); a consulta não identifica `created_at` nem novos registros por criação. |
| Origem do campo de internet em CRU-003 | **`EnderecoAluno.possui_acesso_internet`.** Só `False` é contado (`bi_alunos.py:2690-2736`). |
| XLSX usa `write_string` ou `write` e está sujeito a fórmula? | Usa `worksheet.write` em texto e `write_number` para números (`bi_routes.py:238-279`); rótulos/valores textuais passam por `sanitizar_valor_xlsx`, que prefixa caracteres de fórmula (`utils/xlsx.py:1-17`). Não foi encontrada escrita textual sem essa sanitização na tabela de dados. A hipótese de injeção por valores do indicador não se confirmou. |

## 3. Invariantes numéricos no clone

Resultados da execução anterior, agregados sem nomes ou IDs de alunos. Listas estão somadas por `valor`.

| Invariante | Lado esquerdo | Lado direito | Resultado |
|---|---:|---:|---|
| ALU-001 = ALU-011 + ALU-012 | 1.153 | 106 + 1.047 = 1.153 | Fecha |
| ALU-011 = ALU-013 + ALU-014 + ALU-015 | 106 | 106 + 0 + 0 = 106 | Fecha |
| ALU-012 = ALU-016 + ALU-017 + ALU-018 + Outros | 1.047 | 0 + 0 + 0 + 1.047 = 1.047 | Fecha; “Outros” é residual |
| INS-001 = INS-002 + INS-003 | 113 | 113 + 0 = 113 | Fecha |
| Soma DIV-001 = ALU-007 | 10 | 9 | **Não fecha**; bases diferentes (tipo estruturado versus fallback JSON/perfil) |
| Soma ALU-005 = ALU-011 | 106 | 106 | Fecha |
| Soma ALU-006 = ALU-011 | 106 | 106 | Fecha |
| FRE-006 + FRE-007 + FRE-008 = alunos com frequência contável | 3 + 1 + 9 = 13 | 13, pela partição exclusiva das faixas do helper por aluno | Fecha por construção do helper; a consulta independente de `count(distinct aluno_id)` não pôde ser repetida nesta retomada |
| AUL-001 = soma AUL-002 | 10 | 10 | Fecha |
| AUL-001 = soma AUL-003 | 10 | 10 | Fecha |
| AUL-001 = soma AUL-006 | 10 | 10 | Fecha |
| AUL-001 = soma AUL-007 | 10 | 10 | Fecha no clone; não prova que N:N nunca excederá |
| TUR-003 = soma ALU-010 | 113 | 113 | Fecha; indicadores usam a mesma função |
| FRE-005 BI versus painel pedagógico na mesma turma/período | BI geral sem filtro: 63,8% | Não obtido | **Pendente**: não foi possível repetir a conexão para selecionar turma/período e obter os dois resultados comparáveis. Não inferir igualdade entre escopos globais. |

Outros resultados de execução: `ALU-004` falhou com erro PostgreSQL de comparação `date`/`character varying`; `INS-006` e `INS-007` falharam como não implementados. `CRU-002=0`, `CRU-003=0`, `CRU-004=0`; `CRU-005` retornou quatro faixas com soma zero. `TUR-001=TUR-002=12`; `TUR-004=9,4`; `TUR-005/006/007/008` somaram 12 cada. `AUL-002/003/006/007` somaram 10 cada. A soma de INS-008 foi 113.

## 4. Redundâncias e indicadores não implementados

- **Duplicados no código:** INS-003 e INS-005 usam o mesmo critério de inscrição inativa; TUR-001 e TUR-002 contam somente turmas ativas e retornaram o mesmo total; ALU-010 e TUR-003 são aliases da mesma função.
- **Duplicidade condicional:** INS-004, sem filtro de datas, mede o mesmo conjunto-base de INS-001. INS-008 somou 113, igual ao total INS-001 no clone, mas é uma distribuição por curso e pode não fechar quando houver registros sem curso/oferta correspondente.
- **Não equivalentes, apesar de nomes próximos:** ALU-002 é cadastro ativo e ALU-011 é enturmação ativa em P; seus resultados no clone foram 1.154 e 106. ALU-008 também não equivale a ALU-002: não filtra cadastro ativo. FRE-001 conta lançamentos, enquanto FRE-005 é uma taxa ponderada por linhas.
- **INS-006/007:** presentes no catálogo e listados pela Central (o template percorre todos os itens retornados pelo catálogo: `bi.html:77-80`). Não estão no mapa de execução (`bi.py:33-39`); a chamada direta lança `ValueError` e a rota converte em resposta 400 (`bi_routes.py:298-355`). No clone, ambos retornaram erro de não implementado.

## 5. Proposta de atualização do catálogo (sem alterar `indicadores.md`)

1. **Glossário explícito**
   - **Cadastro novo:** registro recém-criado em `Aluno.created_at`; distinto de “aluno novo no período”.
   - **Aluno novo no período:** status Novo, sem inscrição em período anterior da mesma unidade.
   - **Inscrição nova:** definir como criada (`created_at`) ou com início (`data_inicio`) no período. Até essa decisão, não chamar INS-004 de “novas inscrições” sem qualificador.
   - Definir “ativo” sempre com o nome do campo: `Aluno.ativo`, `Inscricao.ativo`, `Turma.ativo` ou `TurmaCurso.ativo`.
   - Definir “alunos com frequência” como alunos distintos com ao menos um lançamento contável (A/B/C/D/F), sem J; declarar se o aluno precisa ter cadastro ativo.
   - Especificar que `Outros` é o status residual do classificador e publicar sua regra.
2. **Universo padrão recomendado**
   - Indicadores de status/enturmação: `Aluno.ativo=True`, unidade própria, período explícito ou vigente e vínculo de inscrição/oferta efetivo.
   - Indicadores cadastrais: todos os cadastros ou apenas `Aluno.ativo=True` devem ser escolhidos e declarados por indicador; não herdar silenciosamente o universo de enturmação.
   - Inscrições: separar total de registros, ativas e inativas; deixar claro se turma inativa é excluída.
   - Frequência/aulas: declarar que contam linhas de lançamento/registro, não pessoas ou dias; documentar `J` fora do denominador e a atribuição de linhas legadas.
   - Conselho: contar participação/resposta somente após definir conclusão e resposta preenchida; não tratar existência de um registro-base como participação automaticamente.
3. **Correções editoriais**
   - A seção de visualização diz “quatro modos”, mas lista **cinco** incluindo a tabela.
   - Atualizar a lista de filtros globais: a UI mostra unidade, período e turno; curso, turma e professor são aceitos por API/export, mas não têm controles visíveis na Central.
   - Corrigir INS-004 para declarar `Inscricao.data_inicio` e o escopo real; ou alterar a implementação para a data de criação, conforme decisão de negócio.
   - Descrever TUR-001 como total de turmas ativas, ou mudar a implementação caso “total geral” inclua inativas.
   - Distinguir em FRE-005 taxa global ponderada por lançamento da média aritmética de percentuais por aluno.
   - Esclarecer as bases distintas de ALU-007 e DIV-001 e que a soma por tipo de deficiência pode contar um aluno em mais de um tipo.

## 6. Classificação e ordem sugerida de correção

| Prioridade | Classe | Itens | Ação sugerida |
|---|---|---|---|
| 1 | Erro de número/erro visível ao usuário | ALU-004; INS-004; TUR-004 | Corrigir a comparação de tipos em ALU-004; decidir se INS-004 usa data de criação ou início; decidir se TUR-004 mede alunos distintos e se deve restringir cadastro ativo |
| 2 | Regra de negócio ambígua | FRE-005; CRU-002/005; TUR-005/008; turno em ALU-009/010; perfil ausente em CRU-001 | Obter decisão do responsável sobre unidade estatística, curso/professor de turma versus oferta, participação/conclusão de conselho e tratamento de ausências |
| 3 | Divergência/documentação | TUR-001/006/007; ALU-006/014/018; AUL-007; divergência ALU-007/DIV-001; filtros e visualizações | Atualizar descrições após decisões; registrar semântica de universo e limitações da agregação |
| 4 | Não implementados | INS-006/007 | Implementar com critérios aprovados ou removê-los/rotulá-los como indisponíveis na Central |
| 5 | Redundâncias | INS-003/005; TUR-001/002; ALU-010/TUR-003; INS-004/001 sem datas | Consolidar ou diferenciar intencionalmente os códigos para evitar gráficos duplicados |

## 7. Contagens reais, clone e fechamento

| Banco | Antes (somente leitura) | Depois | Conclusão |
|---|---:|---:|---|
| pautaon | 38 tabelas; 3.271 linhas | Não medido nesta retomada | Igualdade antes/depois não verificada |
| pautaon_ensaio | 38 tabelas; 3.700 linhas | Não medido nesta retomada | Igualdade antes/depois não verificada |

O clone `pautaon_rel_prod4` foi restaurado e atualizado para `c1d2e3f4a5b6` na execução anterior. A confirmação de remoção não está disponível: a conexão direta falhou na autenticação em 2026-11-04 e o PostgreSQL MCP não inicializou. **Ação operacional pendente:** restaurar a credencial autorizada localmente (sem compartilhá-la no chat), conectar em modo read-only para confirmar o estado e repetir as contagens; depois remover o clone com a conexão autorizada e confirmar sua ausência. Não executei o `DROP` sem conseguir confirmar a conexão e o alvo.

Nenhum commit AJ12 foi criado. Nenhum dado de produção foi adicionado ao repositório.
