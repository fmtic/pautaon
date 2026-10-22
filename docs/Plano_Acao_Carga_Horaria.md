Plano de Implementação
Problema central: A infraestrutura de cálculo de carga horária por turma já existe, mas a exposição dessas informações ao usuário está incompleta, com bugs e sem integração total na UI.

Etapa 1 — Limpeza do modal de Cursos e confirmação do modelo
Objetivo: Garantir que o modal de cadastro de curso não tenha qualquer campo de carga horária e confirmar que o model está consistente.

Implementação:

Abrir
planejamento.html
 e verificar o #modalCursos — remover qualquer campo carga_horaria que ainda exista no formulário de novo/editar curso dentro do modal. Com base na análise, o modal já não tem esse campo, mas a coluna "C.H. Total" exibida na tabela do modal usa cargas_curso.get(c.id), que precisa ser verificada e mantida como somente leitura (informação calculada, não editável).
Confirmar no
pedagogico.py
 e
core.py
 que não há referência residual a carga_horaria como campo de entrada.
Testes: Teste unitário confirmando que POST /cursos/novo e POST /cursos/<id>/editar ignoram qualquer carga_horaria no payload JSON.

Demo: Modal de cursos abre, permite criar/editar curso com apenas nome e descricao, e exibe a C.H. Total calculada (somente leitura) na tabela.

Etapa 2 — Exibição de C.H. calculada no formulário de Turma (nova e editar)
Objetivo: Mostrar em tempo real, no formulário, a C.H. Aula (duração de uma aula) e a C.H. Total estimada (dias × C.H. aula), calculadas a partir dos campos já preenchidos pelo usuário.

Implementação:


nova.html
 e
editar.html
 — Adicionar um bloco informativo (alerta/card) logo abaixo dos campos de hora início/fim e dias da semana, com dois campos somente-leitura:

"C.H. por Aula: Xh YYmin" (calculado via JS a partir de hora_inicio e hora_fim)
"C.H. Total Estimada: Xh" (calculado via JS: dias efetivos × C.H. aula)
Para o cálculo de dias efetivos no front-end, usar a mesma lógica de gerar_datas simplificada: contar os dias da semana selecionados entre data_inicio e data_fim. Não incluir bloqueios (esses são refinamentos do backend). Indicar "(estimativa — dias bloqueados não são descontados aqui)" no hint.

nova.js
 (novo) e atualização de
editar.js
 — Listener nos campos hora_inicio, hora_fim, dias_semana, data_inicio, data_fim que recalcula e atualiza os campos de exibição de CH a cada mudança.


editar.html
 — O aviso de alteração existente menciona apenas lançamentos/presenças. Atualizá-lo para incluir: "isso também alterará a carga horária aula e total do curso nesta turma".

Testes: Teste de unidade Python para Turma.carga_horaria_aula e Turma.carga_horaria_total (usando mocks de hora_inicio, hora_fim, data_inicio, data_fim, dias_semana). Verificar casos: sem horário → None; hora_fim ≤ hora_inicio → None; sem dias → 0 dias → None.

Demo: No formulário de nova/editar turma, ao preencher hora início 14:00, hora fim 16:30, selecionar Segunda e Quarta, com um período de 2 meses, o sistema exibe "C.H. por Aula: 2h30min" e "C.H. Total Estimada: ~Xh" em tempo real.

Etapa 3 — C.H. Aula e Total na listagem de Turmas
Objetivo: Exibir C.H. Aula e C.H. Total no card/linha de cada turma na tela de listagem.

Implementação:


listar.html
 — Adicionar duas colunas na tabela:

"C.H./Aula" — exibe formatar_ch(turma.carga_horaria_aula)
"C.H. Total" — exibe formatar_ch(turma.carga_horaria_total)
Posicionar após a coluna "Horário".

turmas.py
 → função turma() — Adicionar formatar_ch ao contexto do template (já importada no arquivo, mas verificar se está sendo passada).

Como formatar_ch é um utilitário Python, registrar como filtro Jinja2 em
__init__.py
 OU passar diretamente no render_template. A forma atual no projeto é passar na chamada — manter o padrão.

Testes: Teste de integração que chama GET /turma e verifica que o HTML retornado contém a C.H. formatada de uma turma com horários definidos.

Demo: Listagem de turmas exibe colunas "C.H./Aula" e "C.H. Total" para cada turma. Turmas sem horário mostram "—".

Etapa 4 — Certificado com C.H. formatada corretamente
Objetivo: Garantir que o certificado exibe a carga horária em formato legível ("30h" ou "2h30min"), não em minutos brutos.

Investigação atual: O template
certificado.html
 exibe {{ item.carga_total ~ 'h' }}, o que resultaria em "1800h" se carga_total for minutos. A rota periodo_letivo_relatorio_certificado passa carga_total = turma.carga_horaria_total (minutos inteiros). Isso é um bug.

Implementação:


periodos.py
 → periodo_letivo_relatorio_certificado() — Converter carga_total para string formatada antes de passar ao template, usando formatar_ch():

python

from app.utils.formatters import formatar_ch
"carga_total": formatar_ch(turma.carga_horaria_total),

certificado.html
 — Ajustar a exibição: trocar {{ item.carga_total ~ 'h' }} por {{ item.carga_total }} (pois agora já chega formatado). Ajustar também a tabela de conferência que exibe {{ item.carga_total ~ 'h' if item.carga_total else '—' }}.

Testes: Teste unitário de formatar_ch() cobrindo os casos: 60 min → "1h", 90 min → "1h30min", None → "—", 0 → "—", 1800 min → "30h".

Demo: Ao emitir o certificado de um aluno de uma turma com 1800 minutos de C.H. Total, o certificado exibe "com carga horária de 30 horas" (e não "1800 horas").

Etapa 5 — Correção e completude do template carga_horaria_curso.html
Objetivo: Corrigir os bugs de variável do template existente, adicionar as colunas de C.H. Aula e C.H. Total, implementar o filtro por unidade (global vs. local), e adicionar botão para o CRUD de cursos.

Bugs identificados no template atual:

Usa dados_lista, cursos_lista, periodos_lista, professores_lista, unidades_lista — variáveis que não existem. A rota passa turmas, cursos, periodos, professores.
O loop do filtro de Unidade referencia unidade_contexto e unidades_lista (inexistentes).
O loop do filtro de Período usa p em vez de periodo.
O loop do filtro de Professor usa prof em vez de professor.
O loop do filtro de Curso usa c em vez de curso.
A tabela de resultados itera dados_lista (inexistente) e acessa campos que não existem (dado.descricao, dado.unidade.nome, dado.periodo.descricao, dado.professor.nome).
Não há colunas de C.H. Aula e C.H. Total.
O botão "Novo Registro" no cabeçalho não faz sentido (página só-leitura).
Implementação:


turmas.py
 → carga_horaria_turmas() — Adicionar suporte ao filtro unidade_id para usuários globais (admin/gerência). Passar unidades (lista de todas as unidades) e unidade_id_filtro para o template. Para usuários locais, unidade_id já é fixo via get_unidade_id(). Passar formatar_ch no contexto.


carga_horaria_curso.html
 — Reescrever completamente:

Cabeçalho: título "Carga Horária por Curso/Turma" + botão "Ir para CRUD de Cursos" (link para planejamento).
Filtros corrigidos: Unidade (somente para admin/gerência), Período Letivo, Professor, Curso.
Tabela com colunas: #, Turma, Curso, Professor, Período, Dias/Semana, Horário, C.H. Aula, C.H. Total.
Linha vazia quando não há resultados.
Botão de impressão (window.print()).
CSS de impressão: ocultar filtros e botões na impressão.
Testes: Teste de integração que chama GET /turmas/carga-horaria com e sem filtros e verifica que o HTML contém as colunas corretas e os dados de uma turma criada no setup.

Demo: Acessar /turmas/carga-horaria: tabela exibe turmas com C.H. Aula e C.H. Total formatadas. Filtros por período, professor e curso funcionam. Usuário global vê filtro de unidade. Botão "Ir para Cursos" leva ao planejamento. Impressão oculta os controles.

Etapa 6 — Aviso de inconsistência na edição de turma
Objetivo: Quando o usuário altera horário ou dias da semana na edição da turma, além do aviso sobre lançamentos, o sistema deve informar que a C.H. será recalculada, solicitar confirmação explícita, e após salvar, detectar e reportar inconsistências (ex.: dias de aula zerados porque o período ficou sem nenhum dia válido).

Implementação:


editar.js
 — Expandir handleSubmit:

Incluir mudança de hora_inicio / hora_fim na detecção de alterações (já está no backend, colocar no JS também).
Mensagem de confirmação expandida: "Você alterou os dias, as datas ou o horário da turma. Isso irá limpar os lançamentos existentes e recalcular a carga horária deste curso nesta turma. Deseja continuar?"

turmas.py
 → editar_turma() — Após o commit bem-sucedido, calcular turma_obj.carga_horaria_total e turma_obj.dias_aula_efetivos() e verificar inconsistências:

Se dias_semana está definido mas carga_horaria_total é None → inconsistência de horário ausente.
Se dias_semana está definido, datas definidas, mas dias_aula_efetivos() retorna 0 → todos os dias estão bloqueados ou as datas não cobrem nenhum dia da semana selecionado.
Em caso de inconsistência, fazer flash(..., 'warning') com mensagem explicativa em vez de redirecionar para a listagem, retornando para a tela de edição.
Testes: Teste de integração que POST em /turma/editar/<id> com hora_inicio=None e verifica que o flash de inconsistência aparece. Outro teste com dias_semana "Sábado" e período que tem todos os sábados bloqueados.

Demo: Editar turma alterando hora_inicio para em branco e salvar: sistema exibe aviso "C.H. não pôde ser calculada — verifique os horários de início e fim". Editar turma para dias que não cabem no período: sistema exibe "0 dias de aula encontrados — verifique os dias da semana e o período letivo".

Etapa 7 — Testes, documentação e backlog
Objetivo: Cobrir com testes unitários e de integração as funções principais, documentar o código em português do Brasil e atualizar o backlog.

Implementação:


test_carga_horaria.py
 (novo arquivo) — Testes unitários para:

formatar_ch(): todos os casos de borda.
Turma.carga_horaria_aula: com e sem horários, hora_fim ≤ hora_inicio.
Turma.carga_horaria_total: com dias_semana, datas e horários válidos/inválidos.
calcular_dias_aula_turma(): turma sem datas, turma com todos os dias bloqueados.
Documentação — Adicionar/atualizar docstrings em português do Brasil em:


turmas.py
 → carga_horaria_turmas()

academico.py
 → properties carga_horaria_aula e carga_horaria_total (já têm, revisar)

formatters.py
 → formatar_ch() (já tem, revisar)
backlog.md — Adicionar nova entrada no topo com data atual, seguindo o formato existente (seções por tema, arquivos principais, status).

Demo: pytest tests/test_carga_horaria.py executa com todos os testes passando. backlog.md tem nova entrada documentando as mudanças desta implementação.

Resumo das Etapas e Arquivos Afetados
Etapa	Arquivos principais
1 — Modal de Cursos
planejamento.html
2 — CH no formulário de Turma
nova.html
, editar.html,
editar.js
, nova.js (novo)
3 — CH na listagem
listar.html
,
turmas.py
4 — Certificado formatado
periodos.py
,
certificado.html
5 — Template carga_horaria_curso.html
carga_horaria_curso.html
,
turmas.py
6 — Aviso de inconsistência
editar.js
,
turmas.py
7 — Testes e backlog
test_carga_horaria.py
 (novo), backlog.md
Esse plano foi dividido em 7 etapas curtas e independentes, cada uma com escopo bem definido para não correr o risco de tokens acabarem no meio de uma mudança crítica. Cada etapa entrega algo funcional e testável por si só.
