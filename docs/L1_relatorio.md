# ETAPA L1 — Limpeza das pendências pequenas + sincronização de MER e backlog

Ramo `Onda4`. Suíte final: **291 passed, 51 warnings in 37.60s** (0 falhas).
Nenhum commit feito.

---

## Parte A — Limpeza de código

| Item | Ação | Arquivo(s) |
|------|------|------------|
| A1 | **Removido** `app/templates/turmas/detalhe copy.html` — cópia obsoleta sem referência em nenhum outro template/rota (confirmado via grep). | `app/templates/turmas/detalhe copy.html` (delecionado) |
| A2 | **Não aplicado** — `request.values` está correto: o template `detalhe.html` envia `turma_curso_id` na query string da action URL (`url_for(..., turma_curso_id=oferta.id)`); trocar para `request.form` retornaria `None` e quebraria o desenturmar. Confirmado por leitura do template e da rota. | — (mantido como está) |
| A3 | **Removido** `_contagem_inscricoes_sem_curso` (função em `core.py` L187–201), a chamada (L369), o kwarg `sem_curso_count` no `render_template` e o bloco `{% if sem_curso_count %}` em `lancar.html` (~7 linhas). Código morto desde o NOT NULL de `Inscricao.turma_curso_id` — nenhuma inscrição pode ter `turma_curso_id IS NULL`. Nenhum teste dependia da função ou do bloco. | `app/registros/core.py`, `app/templates/frequencia/lancar.html` |
| A4 | **Atualizado** comentário de rodapé em `test_enturmacao_oferta.py` (~L415–420): menciona a remoção do parâmetro `incluir_inscricoes_null` na ETAPA B6; o nome `sem_null` no teste é marcado como histórico. | `tests/test_enturmacao_oferta.py` |

**Frequencia/RegistroAula:** nenhuma alteração (`turma_curso_id` dessas tabelas continua nullable — legado válido).

## Parte B — Documentação

### Relatórios lidos

V1, T1, P1, B1, B2, B3, B4, B5, B6, M2, M4 (todos `docs/*_relatorio.md` presentes no working tree).

**git status (relatórios removidos do working tree):**
- `docs/M1_relatorio.md` — `D` (deleted)
- `docs/M1_1_relatorio.md` — `D` (deleted)
- `docs/checklist_seguranca_dividas_tecnicas.md` — `D` (deleted)

Nenhum foi restaurado nem apagado por esta etapa.

### Edições no MER (`app/models/MER.md`)

| Seção | O que mudou |
|-------|-------------|
| Cabeçalho "Última atualização" | Atualizado para 2026-10-25; resume NOT NULL, índice parcial, serviço enturmacao, guarda M4, cond_oferta_efetiva, isolamento B3/B4, D5 decidido, suíte 291. |
| §7.15 `inscricoes` | `turma_curso_id` → Nulo="não"; nota sobre índice parcial `uix_inscricao_ativa_aluno_oferta`; múltiplas ofertas permitidas; NOT NULL aplicado. |
| §8.10 Turma/ofertas | Novos bullets: Enturmação (serviço único M2), Desenturmar por oferta (M2), Transferência por oferta (M2), Desativar oferta — guarda M4, cond_oferta_efetiva (M4), Pauta da oferta (sem fallback NULL), Isolamento B3/B4. Removido: trecho NULL fallback (antigo L974). Atualizado: matrícula NOT NULL, BI J2→B6→M4, D5 decisão registrada. |
| §10 Histórico | Nova subseção "Onda 4 — Pós-Fase 4 (24–25/10)" com entradas T1, P1, B1–B6, M1, M2, M4, L1. |
| §11 Migrations | Linhas `c3d4e5f6a7b8` e `d4e5f6a7b8c9` atualizadas: "endurecida na B5". |
| §12 Dívidas | Novos itens §12.13–§12.18: duplicação predicado, ofertas.html, avisos transiente, conftest, deploy CLI/observabilidade, D5. |

### Edições no backlog (`backlog_desenvolvimento.md`)

Adicionada seção "Alterações do dia — 25/10/2026 (Onda 4 pós-Fase 4)" com resumo de cada etapa (T1–L1, suíte 291P) e lista "Pendências abertas (pós-L1)" — removidos itens resolvidos (D4/P2/P3/P4, R1/R2 isolamento, código morto NULL), mantidos os pendentes (D5, D3b-2, Fases 5–7, Onda 3C, etc.).

## Divergências encontradas

| Ponto | Relatório × Código |
|-------|--------------------|
| A2 `request.values` | O enunciado pedia trocar para `request.form`; a leitura confirmou que o template envia `turma_curso_id` na query string da action — `request.form` retornaria `None`. **NÃO alterado.** |
| M1/M1.1 relatórios | Referenciados pelo enunciado mas não existem no working tree (status `D`). Não foram lidos nem restaurados. |

## Pendências (não resolvidas nesta etapa)

- D5 conselho por oferta (decidido, implementação pendente).
- D3b-2/J3 leitores por `turma_id`.
- Fases 5–7, turma_lixeira, Onda 3C.
- Dívidas §11.1 (itens 2–6, 8).
- Dump autêntico de produção para novo ensaio.
- §12.13–§12.17 (dívidas M4, D6, D7, P7, B5-P1/P2).

## Resumo pytest

```
291 passed, 51 warnings in 37.60s
```
