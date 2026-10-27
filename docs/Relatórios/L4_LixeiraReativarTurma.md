# L4 — /turmas/lixeira: corrigir 500 e reativação de turma

**Branch:** `nova_feature` · **HEAD Alembic:** `8d2e3f4a5b6c` · **Suíte:** 693 passed · **Data:** 27/10/2026

Sem migration. Sem push.

---

## P1 — Leitura e TRAVA

- Rota `turma_lixeira` existia mas renderizava template inexistente → 500.
- `excluir_turma` (lógica) desativa turma + todas as ofertas (`ativo=False`) + inscrições ativas (motivo `TURMA_DESATIVADA`), preservando lançamentos.
- Sinal confiável para distinguir oferta desativada junto com a turma: `turma.ativo=False` implica que todas as ofertas foram desativadas pela exclusão lógica (desativar_oferta manual mantém a turma ativa). Portanto, na reativação, reativar todas as ofertas inativas da turma.
- TRAVA não acionou (sinal confiável encontrado).

## Implementação

- Serviço: `preview_reativacao` e `reativar_turma` em `app/services/turma_curso.py` (sem commit; rota commita).
- Rotas: GET `/turmas/lixeira` (listagem + contagens em lote) e POST `/turmas/reativar/<id>` (CSRF, perfis, isolamento).
- Template: `app/templates/turmas/turma_lixeira.html` novo. Link na listagem (perfis permitidos).
- Reativação: turma + ofertas + inscrições elegíveis (motivo `TURMA_DESATIVADA`, oferta reativada, sem conflito, aluno ativo). Conflitos permanecem inativos. Período encerrado exige confirmação. LogAcao gravado.

## Testes (9)

GET 200/403/Visão Global; reativação básica; conflito; período encerrado; LogAcao; isolamento; idempotência; ciclo.

## Validação

- Suíte: 693 passed, 250 warnings.
- `ruff check --select F821,F811`: limpo.
- `git diff --check`: limpo.
- Sem push.
