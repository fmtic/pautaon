# AJ31 — Informações Gerais do Período

**Data:** 24/11/2026 · **Branch:** `nova_feature` · **Migration:** nenhuma (head do código segue `b8c9d0e1f2a3`) · **Push/merge:** não realizados

## Objetivo

Novo relatório **"Informações Gerais do Período"**: distribuição percentual das situações finais (`Aprovado`, `Participante`, `Reprovado por faltas`, `Desistente`, `Evadido`, `Empregado`) de todas as ofertas efetivas de um período letivo, acessado a partir do Resultado do Conselho. Sem alteração de schema, permissão nova ou regra de negócio — apenas leitura agregada.

## Escopo entregue (worktree)

| Arquivo | Mudança |
|---|---|
| `app/services/relatorio_periodo_info.py` | **novo** — serviço de agregação `obter_informacoes_gerais_periodo(periodo_letivo_id, unidade_id)` |
| `app/relatorios/geral.py` | nova rota `GET /relatorios/periodo/<int:periodo_id>/informacoes-gerais` |
| `app/templates/relatorios/informacoes_gerais_periodo.html` | **novo** — tela + impressão do relatório |
| `app/static/css/relatorios/informacoes_gerais_periodo.css` | **novo** — estilos de tela e `@media print` (A4 **retrato**) |
| `app/static/img/logo_irn.png` | **novo** — logo institucional usada no cabeçalho de impressão |
| `app/templates/relatorios/resultado_conselho.html` | botão "Informações Gerais do Período" no rodapé do card de filtro + JS que atualiza o `href` ao trocar o período; ajustes de layout do cabeçalho (`flex-wrap`, `min-w-0`, `flex-shrink-0`) e ícone do botão Imprimir (`file-pdf` → `printer`) |
| `scripts/verificar_imports.py` | **novo** — utilitário que importa todos os módulos de `app.*` e reporta falhas (verificação de sanidade do pacote) |

**Fora do escopo (não fazem parte da feature):** `aplicar_deploy.ps1` e `empacotar_deploy.ps1` (scripts de deploy locais, não versionados nesta entrega), `app/relatorios/geral copy.py` (cópia duplicada acidental do módulo — recomendo remover; não é importada por nada).

## Regra de agregação (`relatorio_periodo_info.py`)

- **Base de inscritos:** `Inscricao` → `TurmaCurso` → `Turma` → `Aluno`, filtrando `Turma.periodo_letivo_id`, `Turma.ativo`, `Aluno.ativo` e `cond_oferta_efetiva()` (mesmo predicado do BI — oferta ativa ou em período encerrado). Quando `unidade_id` é informado, filtra `Turma.unidade_id`.
- **Base de avaliados:** `ConselhoClasse` com `etapa == EtapaConselho.FINAL` e `situacao_final IS NOT NULL`, agrupado por situação — mesma base de oferta efetiva.
- **Indicadores:** configuração fixa `_CONFIG_SITUACOES` com rótulo, descrição, cor Bootstrap e flag `exibir_se_zero` (`Evadido` e `Empregado` só aparecem se tiverem contagem > 0). Percentual calculado sobre `total_avaliados` (não sobre inscritos).
- **Pendentes:** `pendentes_definicao = max(0, total_inscritos - total_avaliados)` — inscrições efetivas sem situação final definida no conselho.
- Retorno: `{total_inscritos, total_avaliados, pendentes_definicao, indicadores[]}`.

## Rota (`relatorios.informacoes_gerais_periodo`)

- `GET /relatorios/periodo/<int:periodo_id>/informacoes-gerais`, `@login_required`, exige papel em `ROLES_RELATORIOS` (`admin`, `pedagogico`, `secretaria`, `gerencia`, `servico_social`) — 403 caso contrário.
- `PeriodoLetivo.query.get_or_404(periodo_id)`; escopo por `get_unidade_id()` (perfil não global fica restrito à própria unidade; Visão Global agrega tudo).
- Emissão em `America/Sao_Paulo` (`data_emissao_iso` para o nome do PDF, `data_hora_emissao` para tela/impressão).
- Erro genérico → `flash_and_log` + redirect para `relatorio_geral`; `HTTPException` propagada.

## Tela e impressão

- **Tela:** card executivo com badge de unidade, nome/vigência do período, síntese de aproveitamento (percentual + barra de progresso + contagem por situação) e alerta informativo quando há pendentes de definição. Botões: "Resultado do Conselho" (volta com `periodo_letivo_id`) e "Imprimir".
- **Cabeçalho de impressão** (`print-only`, padrão AJ23/AJ26/AJ27): logo IRN (`logo_irn.png`) + logo institucional secundária, nome da instituição, título, unidade, período letivo com datas, "Emitido em" e colaborador.
- **`@page A4 portrait`** — exceção deliberada ao padrão landscape dos demais relatórios de tabela (o conteúdo é uma síntese de indicadores, não tabela).
- Reutiliza `resultado_conselho.css`/`resultado_conselho.js` para o padrão de impressão compartilhado (`prepararImpressao`, `beforeprint`, rodapé de auditoria).

## Entrada pelo Resultado do Conselho

- Botão "Informações Gerais do Período" (`btn-outline-primary`, ícone `bi-pie-chart`) no rodapé do card de filtro, ao lado de "Filtrar".
- Sem período selecionado renderiza `href="#"` com classe `disabled`; o JS inline atualiza o `href` para `/relatorios/periodo/<id>/informacoes-gerais` quando o `<select>` de período muda (sem recarregar a página).
- Ajuste de layout do cabeçalho da página: `flex-wrap`/`gap-2` no container e `flex-shrink-0` no grupo de ações para os botões não serem cortados em telas estreitas.

## Verificação

- Rota registrada: `/relatorios/periodo/<int:periodo_id>/informacoes-gerais` → `relatorios.informacoes_gerais_periodo`.
- `ruff --select F401,F821,F811,F841` limpo em `geral.py` e `relatorio_periodo_info.py` (import `get_local_now` não utilizado removido nesta documentação).
- **Sem testes automatizados dedicados** — a feature ainda não tem `tests/test_aj31_*.py`; recomendado cobrir: 403 para papel fora de `ROLES_RELATORIOS`, 404 para período inexistente, isolamento por unidade, contagens/percentuais com massa conhecida e renderização do botão no resultado do conselho.

## Deploy

Sem migration: deploy é apenas substituir código estático e reiniciar o app. Nenhuma verificação de banco é necessária.
