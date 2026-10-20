 (2026-10-20), escopo (rotas + templates do painel pedagógico)

Quebra de sistema / bugs
ficha_aluno.html linhas ~404 e ~413 iteram mapa, mas a variável está em frequencia.mapa (retorno de montar em ficha_aluno.py). Corrigir para f.mapa ou expor mapa no contexto.
painel_pedagogico.html linha ~376 chama macro lista_sinais(vt.sinais) inexistente → UndefinedError. Definir o macro ou reutilizar o bloco de sinais da visão de período.
ficha_aluno.html linhas ~448-450 usam data-labels="{{ ...|tojson }}" com aspas duplas → atributo quebrado; trocar para aspas simples como em painel_pedagogico.html linha 383.
ficha_aluno.py linhas ~202-204: acumulam pres_acum/falt_acum dentro do agregador semanal → série semanal inflada; somar presença/falta da aula, não o acumulado.
turma.montar retorna {"vazia": True} sem as chaves que o template usa (pct_turma_str, faixas, sinais...) → campos em branco/erro; tratar vazia no template ou retornar contexto completo.
Segurança
rota.py ficha_aluno_view: Turma.query.get_or_404(turma_id) sem filtro de unidade_id → possível acesso cruzado de unidade. Filtrar por unidade e validar insc.
busca_alunos: quando unidade_id é None, query retorna vazio silenciosamente; periodo_id inválido também falha em silêncio.
Conferir se a exclusão de secretaria/gerencia do contexto_restrito.permitido é intencional.
Dívida técnica
Textos hardcoded de protótipo: "Janela de renovação encerrada em 18/08" (painel_pedagogico.html ~193), "27% dos alunos" e "etapa final abre em 19/10" (periodo.py ~110-118) — calcular a partir de dados reais.
N+1 em _percurso (3 queries por turma anterior) — consolidar com func.count + group_by.
_segunda_da usa __import__("datetime") — usar timedelta importado.
Heatmap ficha_aluno.html: grid fixo repeat(11, ...) e linhas apenas Ter/Qui (dia_semana == 1/3) — derivar colunas de f.labels e linhas dos dias presentes em mapa.
__init__.py do pacote: __all__ = ["painel_pedagogico"] inconsistente com o import real (rota).

Conclusão: rotas estão corretas na estrutura (autenticação, roles, filtros de unidade no aluno), mas há 5 bugs que impedem exibição correta com dados reais e textos de protótipo ainda ativos.

## Proposta de ajuste ##

Reparar rotas e templates do painel pedagógico
Corrigir os relatórios do painel pedagógico no repositório fmtic/pautaon para que painel_pedagogico.html e ficha_aluno.html exibam corretamente todos os dados com dados reais. Arquivos envolvidos: app/relatorios/painel_pedagogico/rota.py, ficha_aluno.py, turma.py, periodo.py, __init__.py e app/templates/relatorios/painel_pedagogico.html, ficha_aluno.html.

Correções obrigatórias:

Mapa aula-a-aula da ficha (ficha_aluno.html ~linhas 404 e 413): o template itera mapa, mas montar() devolve em frequencia["mapa"]. Trocar os loops para f.mapa (ou adicionar "mapa" ao contexto raiz na view). Também gerar as linhas do heatmap dinamicamente a partir dos dia_semana presentes em f.mapa (hoje fixo Ter=1 e Qui=3) e ajustar o CSS grid-template-columns: 2rem repeat(11, ...) (~linha 60) para o número real de semanas (usar f.labels|length via style inline ou classe).

Gráfico da ficha (ficha_aluno.html ~linhas 448-450): trocar aspas duplas por simples nos atributos data-labels, data-aluno, data-turma para o tojson não quebrar o HTML (seguir o padrão de painel_pedagogico.html linha 383).

Série semanal inflada (ficha_aluno.py ~linhas 202-204): em _frequencia, por_semana_aluno[seg][0] += pres_acum deve somar a presença/falta daquela aula (1/0 conforme conceito), não o acumulado. Ajustar para que serie_aluno receba pct() por semana corretamente.

Macro lista_sinais inexistente (painel_pedagogico.html ~linha 376): definir o macro lista_sinais(sinais) no próprio template (mesmo padrão visual do bloco de sinais da visão de período: nível→cor, bi-{{ s.icone }}, s.titulo, s.detalhe) para a visão de turma não lançar UndefinedError.

Estado vazio da turma (turma.py ~linhas 34-35 e painel_pedagogico.html): quando montar retorna {"vazia": True}, o template deve exibir mensagem de "sem dados no período" sem acessar vt.pct_turma_str, vt.faixas, vt.sinais etc. Envolver os cards de turma em {% if not vt.vazia %} com um fallback, ou retornar contexto completo com valores zerados.

IDOR na ficha (rota.py ficha_aluno_view ~linhas 186-193): Turma.query.get_or_404(turma_id) deve filtrar unidade_id=get_unidade_id() (mesmo filtro aplicado ao Aluno); se a inscrição insc não existir, retornar 404 ou ignorar o turma_id — nunca renderizar ficha vinculada a turma de outra unidade.

busca_alunos silencioso (rota.py ~linhas 132-139): se unidade_id for None, usar fallback consistente com as demais rotas; validar que periodo_id informado pertence à unidade e, se inválido, cair no período default em vez de seguir com periodo=None.

Dados fake de protótipo: remover/calcular os textos estáticos — "Janela de renovação encerrada em 18/08" (painel_pedagogico.html ~linha 193, colocar atrás de condicional ou vir do contexto), "As turmas noturnas têm 27% dos alunos enturmados" e "A etapa final abre em 19/10" (periodo.py ~linhas 110-118 — calcular % real de enturmação e data real de abertura a partir do banco; se não houver fonte de dados, suprimir o sinal em vez de exibir número inventado).

Limpeza (ficha_aluno.py ~linhas 257-260 e __init__.py): _segunda_da deve usar timedelta importado normalmente no topo do arquivo; corrigir __all__ em app/relatorios/painel_pedagogico/__init__.py para refletir o que o pacote realmente exporta.

N+1 em _percurso (ficha_aluno.py ~linhas 520-548): substituir as 3 queries de Frequencia por turma por agregações com func.count/group_by (ou ao menos uma query por turma), mantendo o mesmo resultado de pct.

Critério de aceite: renderizar painel_pedagogico (visões período e turma, com e sem dados) e ficha_aluno sem UndefinedError, com mapa, gráficos e sinais populados a partir do banco, sem textos hardcoded de protótipo, e sem permitir turma de outra unidade na ficha. Manter app/docs/divida_tecnica.md atualizado marcando os itens resolvidos.