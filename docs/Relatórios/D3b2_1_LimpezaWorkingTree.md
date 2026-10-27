# D3b-2.1 — Limpeza do working tree (commits coerentes)

**Branch:** `nova_feature` · **HEAD Alembic:** `8d2e3f4a5b6c` · **Suíte inicial:** 662 passed · **Data:** 27/10/2026

Tarefa de **higiene do repositório**: classificar e commitar o trabalho pendente da série H/PQ e da correção da pauta, sem alterar lógica. Nenhuma migration. Sem push.

---

## P0 — Fotografia inicial

`git status --short` (antes):
```
 M app/conselho.py
 M app/models/MER.md
 M app/registros/core.py
 M app/static/js/conselho/conselho.js
 M app/static/js/turmas/grade_horario.js
 M app/templates/conselho/lancamento.html
 M app/templates/conselho/painel.html
 M app/templates/conselho/perguntas.html
 M app/templates/conselho/turma_aval.html
 M app/templates/frequencia/lancar.html
 M app/utils/logica.py
 M backlog_desenvolvimento.md
D  "docs/Relatórios/H4b_SubstituidoPorH4c.md"
 M tests/test_conselho_ui.py
 M tests/test_frequencia_oferta.py
 M tests/test_grade_horario_js.py
 M tests/test_ui_grade_por_dia.py
?? app/templates/conselho/imprimir_formulario.html
?? "docs/Relatórios/H4d_FechamentoLacunasH4c.md"
?? tmpf1u8j29n
?? tmpg0wpq02k
?? tmpopmmqv3a
```
`git diff --stat`: 16 arquivos, 723 inserções, 69 deleções (tracked). Suíte antes: 662 passed.

## P1 — Classificação

| Arquivo | Tipo | Classe | Ação proposta |
|---|---|---|---|
| `app/conselho.py` | código | A — série PQ | commitar |
| `app/static/js/conselho/conselho.js` | código | A — série PQ | commitar |
| `app/templates/conselho/lancamento.html` | template | A — série PQ | commitar |
| `app/templates/conselho/painel.html` | template | A — série PQ | commitar |
| `app/templates/conselho/perguntas.html` | template | A — série PQ | commitar |
| `app/templates/conselho/turma_aval.html` | template | A — série PQ | commitar |
| `app/templates/conselho/imprimir_formulario.html` | template (novo) | A — série PQ | commitar |
| `tests/test_conselho_ui.py` | teste | A — série PQ | commitar |
| `app/static/js/turmas/grade_horario.js` | código | A — série H (H4d) | commitar |
| `tests/test_grade_horario_js.py` | teste | A — série H (H4d) | commitar |
| `tests/test_ui_grade_por_dia.py` | teste | A — série H (H4d) | commitar |
| `app/registros/core.py` | código | A — fix pauta | commitar |
| `app/utils/logica.py` | código | A — fix pauta | commitar |
| `app/templates/frequencia/lancar.html` | template | A — fix pauta | commitar |
| `tests/test_frequencia_oferta.py` | teste | A — fix pauta | commitar |
| `app/models/MER.md` | documentação | B | commitar |
| `backlog_desenvolvimento.md` | documentação | B | commitar |
| `docs/Relatórios/H4d_FechamentoLacunasH4c.md` | documentação (novo) | B | commitar |
| `docs/Relatórios/H4b_SubstituidoPorH4c.md` | documentação (removido) | B | commitar (git rm) |
| `tmpf1u8j29n`, `tmpg0wpq02k`, `tmpopmmqv3a` | lixo temporário | C | **PROPOR remoção (não executado)** |
| `docs/Relatórios/D3b2_0_MapaFrequenciaPorOferta.md` | relatório | B (já commitado em 643d025) | — |
| `docs/Relatórios/D3b2_1_LimpezaWorkingTree.md` | relatório | B | commitar (este) |

**Classificação E (alteração alheia/duvidosa):** nenhum item. Nenhum ponto de parada.

---

## P2 — Commits criados

| Hash | Mensagem | Arquivos |
|---|---|---|
| `8da6655` | Conselho (PQ): impressao de formulario + ordenacao de perguntas + edicao via data-* | 8 (conselho.py, conselho.js, templates, imprimir_formulario.html, test_conselho_ui.py) |
| `b719a1a` | H4d: funcoes puras do componente de agenda (grade_horario.js) + testes | 3 (grade_horario.js, test_grade_horario_js.py, test_ui_grade_por_dia.py) |
| `730822f` | Fix: TypeError nos temas da pauta de frequencia (carregar_frequencias) | 4 (core.py, logica.py, lancar.html, test_frequencia_oferta.py) |
| *(este commit)* | Docs: H4c/H4d + MER/backlog + D3b-2.0/D3b-2.1 | MER.md, backlog, H4d relatório, H4b removido, D3b-2.1 |

---

## P3 — Pendências para aprovação (NADA executado)

### C — Lixo temporário (proposta: remover)

| Arquivo | Tamanho | Proposta |
|---|---|---|
| `tmpf1u8j29n` | (temp) | `Remove-Item` após confirmação |
| `tmpg0wpq02k` | (temp) | `Remove-Item` após confirmação |
| `tmpopmmqv3a` | (temp) | `Remove-Item` após confirmação |

Nenhum deles é rastreado pelo git (untracked). Prováveis resíduos de execuções anteriores de pytest/IDE. **Aguardando sua autorização.**

### D — Artefato de ambiente (proposta: .gitignore)

Nenhum artefato de ambiente (backups SQL, dumps, uploads) encontrado no working tree. `instance/` não contém `.db`/`.sql` locais. Nenhuma ação proposta.

### E — Alteração alheia/duvidosa

Nenhum item. Todos os diffs foram reconhecidos como trabalho legítimo (série H/PQ, fix da pauta, docs).

---

## Verificação final

- `git diff --check`: limpo (nenhum whitespace error).
- Suíte após último commit: 662 passed, 222 warnings.
- `git status --short` restante: apenas `tmpf1u8j29n`, `tmpg0wpq02k`, `tmpopmmqv3a` (classe C, pendentes de aprovação).
- Sem push.

---

## Resumo

Working tree limpo quanto a código e documentação. Três commits criados (8da6655, b719a1a, 730822f) mais este de docs. Três arquivos temporários aguardam autorização para remoção. Nenhuma alteração de lógica, schema ou banco.
