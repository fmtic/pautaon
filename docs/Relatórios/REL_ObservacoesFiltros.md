# Diário de Observações com filtros (Painel Pedagógico)

**Data:** 28/10/2026
**Escopo:** acesso ao diário a partir do Painel Pedagógico, com filtros por período letivo, turma, curso (oferta) e professor.
**Natureza:** rota nova de leitura + botão no painel + template em modo global. **Sem migration e sem alterar o fluxo por turma.**

## 1. Contexto

O diário só existia no caminho da turma (`/turma/<id>/observacoes`), sem visão consolidada. O Painel Pedagógico (`/relatorios/painel`) já seleciona período e turma, mas não levava ao diário. A proposta: um botão no painel abrindo o diário em modo global, com filtros — disponível apenas para os perfis que já entram no painel (`ROLES_RELATORIOS = admin, pedagogico, secretaria, gerencia`).

## 2. Arquitetura

- **Rota nova:** `GET /relatorios/observacoes` → `relatorios.observacoes` (`app/relatorios/observacoes.py`).
- **Permissão:** a mesma do painel (`ROLES_RELATORIOS`); professor recebe 403. O fluxo por turma (`registros.ver_observacoes`) mantém a sua regra (unidade + vínculo do professor).
- **Template único:** `turmas/observacoes.html` com `modo_global`. No modo global aparecem o formulário de filtros, o período selecionado, o badge da turma em cada registro e um "Voltar" para o painel pedagógico. No modo turma nada disso aparece.
- **Reaproveitamento:** a escolha do período padrão usa `_escolher_periodo` da rota do painel (vigente primeiro, senão o mais recente).

## 3. Filtros

| Filtro | Parâmetro | Comportamento |
|---|---|---|
| Período letivo | `periodo_letivo_id` | Lista os períodos da unidade; ausente/inválido cai no vigente (mesma regra do painel) |
| Turma | `turma_id` | Turmas ativas do período; ausente = todas; id de outro período é ignorado |
| Curso (oferta) | `turma_curso_id` | Só habilitado com turma escolhida (filtro encadeado); oferta de outra turma é ignorada |
| Professor | `professor_id` | Lista derivada das turmas/ofertas filtradas; compara `coalesce(TurmaCurso.professor_id, Turma.professor_id)` |

Todos os selects disparam o GET (`onchange="this.form.submit()"`), com botão "Filtrar" como fallback sem JS.

**Consulta:** `RegistroAula` JOIN `Turma` (período, `Turma.ativo`, unidade) e OUTER JOIN `TurmaCurso`; entram apenas registros com **observações ou atividades** preenchidas (mesmo critério da tela por turma). Ordenação: data desc, turma, id. `joinedload` para turma/professor, oferta/curso, instrutor e temas (sem N+1 no template).

**Limite:** 500 registros por consulta, com aviso na tela para refinar os filtros quando houver mais (a rota busca `LIMITE + 1` só para detectar o truncamento).

## 4. Botão no painel

Em `relatorios/painel_pedagogico.html`, ao lado de "Buscar aluno (ficha 360°)": "Diário de observações", levando `periodo_letivo_id` (e `turma_id` quando o painel está filtrado por turma).

## 5. Não regressão

- `/turma/<id>/observacoes` continua sem filtros, com a guarda de unidade/professor e o "Voltar" para `main.painel`.
- Nenhum modelo, migration, permissão existente ou saída (pauta, BI, relatórios) foi alterado.

## 6. Testes

`tests/test_relatorios_observacoes.py` — **13 testes**:

1. admin vê os textos do período (e não os de outro período);
2. registro sem observações/atividades não aparece;
3. filtro por turma;
4. filtro por curso da turma;
5. filtro por professor (oferta);
6. período anterior mostra o histórico;
7. professor recebe 403 no modo global;
8. unidade B não vê registros da unidade A;
9. botão presente no painel pedagógico;
10. fluxo por turma continua sem o formulário de filtros;
11. `turma_id` de outro período é ignorado (não vaza histórico);
12. aviso de truncamento quando o limite é atingido (monkeypatch);
13. oferta de outra turma não vaza registros.

**Suíte:** 813 → **826 passed**, 0 falhas. `ruff --select F821,F811` limpo; `git diff --check` limpo.

## 7. Arquivos

- `app/relatorios/observacoes.py` (novo) — rota e consulta.
- `app/relatorios/__init__.py` — registro do módulo (depois de `painel_pedagogico`).
- `app/templates/relatorios/painel_pedagogico.html` — botão.
- `app/templates/turmas/observacoes.html` — modo global (filtros, período, badge da turma, aviso de limite, "Voltar").
- `tests/test_relatorios_observacoes.py` (novo).
- `app/models/MER.md` (§7.20) e `backlog_desenvolvimento.md`.

## 8. Limitações e decisões

- **Sem paginação:** teto de 500 + aviso. Se o uso crescer, paginar como a lista de temas do Planejamento.
- **Curso dependente da turma:** evita listar centenas de ofertas e ambiguidade; para ver todas as ofertas, deixe a turma em "Todas".
- **Professor efetivo:** usa o da oferta quando existir; registros legados (sem oferta) usam o professor da turma.
- A visão global não mostra alunos nem frequência — é o mesmo conteúdo da tela por turma, com o contexto de turma/curso visível.

## 9. Validação manual

1. Painel pedagógico → "Diário de observações" → tela global com o período vigente.
2. Trocar o período, depois a turma, depois o curso e o professor; cada troca recarrega com o filtro aplicado.
3. Sem turma, o select de curso fica desabilitado.
4. Abrir o mesmo diário por `/turma/<id>/observacoes`: sem filtros, com "Voltar" para o painel.
