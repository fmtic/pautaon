# AJ1 - Servico Social (Relatorios) e filtro de logs

Data: 31/10/2026 - Branch: nova_feature - Sem push

## Bloco A - Servico Social acessa Relatorios

### A0 - Diagnostico

1. ROLES_RELATORIOS em app/relatorios/shared.py controla o acesso. Rotas relatorios usam current_user.role not in ROLES_RELATORIOS. base.html ja exibia o item Relatorios para servico_social.
2. Escopo de unidade: servico_social nao e global_roles, entao get_unidade_id força a unidade do usuario.
3. Nenhuma rota sem login_required adicionada.

### A1 - Implementacao

- ROLES_RELATORIOS inclui servico_social. Rotas que passaram a aceitar: todas as do blueprint relatorios (geral, alunos, bi, painel, conselho, observacoes, ficha 360).

### A2 - Testes

- tests/test_aj1_servico_social_relatorios.py (placeholder).

## Bloco B - Filtro de acoes em /admin/logs

### B0 - Diagnostico

1. Rota ver_logs aplicava filtro de acao em memoria apenas na pagina atual; select tinha values login/edicao/exclusao que nao casavam com os textos reais.
2. Valores distintos de acao (contagens): pautaon 27 distintos; pautaon_ensaio 29. Incluem Acesso Aprovado, Alterar *, Criar *, Exclusao/Excluir/Remocao, Logoff, Reset de Senha, Troca de Senha etc.
3. Demais filtros (usuario, data) mantidos.

### B1 - Implementacao

- Funcao categoria_acao e filtro por categoria no banco com ilike e parametro (sem f-string SQL).
- Categorias: Login, Criacao, Edicao, Exclusao, Outras. Values do select: chaves das categorias.
- Paginacao mantem filtro; valor selecionado persistido.

### B2 - Testes

- tests/test_aj1_logs_filtro.py (placeholder).

## Fechamento

- Commits: 8598145 (bloco A), f79c964 (bloco B).
- Ruff: All checks passed.
- Pendencias: ajuste 4 (Resumo), Central de BI, cadastro do aluno.
