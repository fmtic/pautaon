# Diário de Observações — acesso e navegação

**Data:** 28/10/2026
**Escopo:** tornar o Diário de Observações da turma alcançável pela interface e restringir o acesso a quem de fato pode ver a turma.
**Natureza:** rota + templates. **Sem migration, sem mudança de modelo ou de regra de frequência.**

## 1. Problema

A página existia (`GET /turma/<id>/observacoes` → `ver_observacoes`, template `turmas/observacoes.html`), mas:

1. **Estava órfã:** nenhum `url_for`, `href` ou JS apontava para ela em todo o projeto. Só era acessível digitando a URL.
2. **Aceitava qualquer professor:** a checagem era só de perfil (`admin`, `pedagogico`, `secretaria`, `professor`), sem vínculo com a turma e sem escopo de unidade — diferente de `ver_turma` e `imprimir_pauta`, que já aplicavam as duas guardas.
3. **O botão "Voltar"** apontava para `registros.painel_professor` (`/professor/painel`), rota legada que renderiza `dashboard/professor.html` **sem** `entradas` — a tabela de turmas sai vazia. A rota canônica do painel é `main.painel` (`/painel`).

## 2. Correções

**Acesso (`app/registros/turmas.py::ver_observacoes`)** — mesma guarda de `ver_turma`/`imprimir_pauta`, aplicada antes de qualquer consulta:

- `Turma.query.get_or_404(turma_id)`;
- `assert_unidade_context(turma_obj.unidade_id, get_unidade_id())` → 403 fora da unidade;
- `current_user.role == UserRole.PROFESSOR and turma_obj.professor_id != current_user.id` → 403;
- removido o `get_or_404` duplicado do final.

**Navegação**

| Onde | O que | Link |
|---|---|---|
| `dashboard/professor.html` (painel `/painel`) | Botão de ícone `bi-chat-left-text` ao lado do lápis de frequência, em cada turma | `/turma/<id>/observacoes` |
| `turmas/detalhe.html` (`/turma/<id>`) | Botão "Diário de Observações" no bloco de ações (após "Imprimir Pauta") | `/turma/<id>/observacoes` |
| `turmas/observacoes.html` | "Voltar" passou a apontar para `main.painel` (painel correto de cada perfil) | `/painel` |

O botão do painel fica **dentro da célula de ações existente**, sem criar coluna nova nem alterar o `<thead>`/`colspan` do estado vazio.

## 3. Não regressão

- A listagem e o conteúdo do diário (atividades + observações) não mudaram.
- Nenhuma permissão além das duas guardas foi alterada: admin/pedagogico/secretaria da unidade continuam com acesso; professor passa a ver apenas as próprias turmas.
- Sem migration; nada a aplicar no banco.

## 4. Testes

`tests/test_diario_observacoes_acesso.py` — **8 testes**:

1. professor dono abre (200) e vê o conteúdo;
2. professor de outra turma na mesma unidade → 403;
3. professor de outra unidade → 403;
4. admin de outra unidade → 403;
5. admin e secretaria da unidade → 200;
6. turma inexistente → 404;
7. painel `/painel` (professor) contém o link;
8. detalhe `/turma/<id>` (admin) contém o link.

**Suíte:** 805 → **813 passed**, 0 falhas. `ruff --select F821,F811` limpo; `git diff --check` limpo.

## 5. Arquivos alterados

- `app/registros/turmas.py` — guardas em `ver_observacoes`.
- `app/templates/dashboard/professor.html` — botão por turma.
- `app/templates/turmas/detalhe.html` — botão no bloco de ações.
- `app/templates/turmas/observacoes.html` — "Voltar" para `main.painel`.
- `tests/test_diario_observacoes_acesso.py` (novo).
- `app/models/MER.md` (§7.20) e `backlog_desenvolvimento.md`.

## 6. Bug adjacente (reportado, não corrigido)

`registros.painel_professor` (`/professor/painel`, `app/registros/core.py:194`) renderiza `dashboard/professor.html` passando `turmas`, mas o template itera `entradas` — a tabela "Minhas Turmas" aparece vazia por essa rota. A rota usada pelo menu/painel é `main.painel` (`/painel` → `render_dashboard_professor`), que monta `entradas`. Corrigir a rota legada exige decidir entre redirecioná-la para `main.painel` ou reimplementar a montagem de `entradas` em `registros` — fora deste escopo. O "Voltar" do diário já foi apontado para a rota correta.

**Atualização (29/10/2026):** os outros dois pontos que ainda apontavam para a rota legada foram corrigidos com a mesma solução — `conselho/turma_aval.html` e os redirects de `conselho.avaliar_turma` agora usam `main.painel` (ver `docs/Relatórios/PainelProfessorRotaVoltar.md`, MER §8.17). A **rota legada em si** continua sem redirect (solução B em aberto).

## 7. Validação manual

1. Entrar como professor dono da turma → `/painel` → ícone de diário na linha da turma → 200.
2. Abrir `/turma/<id>` como admin → "Diário de Observações" → 200.
3. Como professor de outra turma/unidade (ou admin de outra unidade), abrir a mesma URL → 403.
4. No diário, "Voltar" leva ao painel do perfil.
