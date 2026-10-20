 (2026-10-20), escopo (rotas + templates do painel pedagógico)

Quebra de sistema / bugs
~ficha_aluno.html linhas ~404 e ~413 iteram mapa, mas a variável está em frequencia.mapa (retorno de montar em ficha_aluno.py). Corrigir para f.mapa ou expor mapa no contexto.~ ✅ RESOLVIDO
~painel_pedagogico.html linha ~376 chama macro lista_sinais(vt.sinais) inexistente → UndefinedError. Definir o macro ou reutilizar o bloco de sinais da visão de período.~ ✅ RESOLVIDO
~ficha_aluno.html linhas ~448-450 usam data-labels="{{ ...|tojson }}" com aspas duplas → atributo quebrado; trocar para aspas simples como em painel_pedagogico.html linha 383.~ ✅ RESOLVIDO
~ficha_aluno.py linhas ~202-204: acumulam pres_acum/falt_acum dentro do agregador semanal → série semanal inflada; somar presença/falta da aula, não o acumulado.~ ✅ RESOLVIDO
~turma.montar retorna {"vazia": True} sem as chaves que o template usa (pct_turma_str, faixas, sinais...) → campos em branco/erro; tratar vazia no template ou retornar contexto completo.~ ✅ RESOLVIDO
Segurança
~rota.py ficha_aluno_view: Turma.query.get_or_404(turma_id) sem filtro de unidade_id → possível acesso cruzado de unidade. Filtrar por unidade e validar insc.~ ✅ RESOLVIDO
~busca_alunos: quando unidade_id é None, query retorna vazio silenciosamente; periodo_id inválido também falha em silêncio.~ ✅ RESOLVIDO
~Conferir se a exclusão de secretaria/gerencia do contexto_restrito.permitido é intencional.~ ✅ RESOLVIDO (incluídos de volta)
Dívida técnica
~Textos hardcoded de protótipo: "Janela de renovação encerrada em 18/08" (painel_pedagogico.html ~193), "27% dos alunos" e "etapa final abre em 19/10" (periodo.py ~110-118) — calcular a partir de dados reais.~ ✅ RESOLVIDO (condicionados a dados reais)
~N+1 em _percurso (3 queries por turma anterior) — consolidar com func.count + group_by.~ ✅ RESOLVIDO
~_segunda_da usa __import__("datetime") — usar timedelta importado.~ ✅ RESOLVIDO
~Heatmap ficha_aluno.html: grid fixo repeat(11, ...) e linhas apenas Ter/Qui (dia_semana == 1/3) — derivar colunas de f.labels e linhas dos dias presentes em mapa.~ ✅ RESOLVIDO
~__init__.py do pacote: __all__ = ["painel_pedagogico"] inconsistente com o import real (rota).~ ✅ RESOLVIDO

Conclusão: rotas estão corretas na estrutura (autenticação, roles, filtros de unidade no aluno), todos os bugs foram corrigidos e textos de protótipo foram removidos/condicionados.