# Menu único — remoção do partial legado `partials/sidebar.html`

Data: 29/10/2026 · Branch `nova_feature` · T3 · Sem push · Sem migration

## 1. Pedido

Acabar com a duplicação de menu: remover `app/templates/partials/sidebar.html`, confirmar por grep que nenhum
template, teste ou doc o inclui/referencia (reportando as referências) e marcar como **resolvidas** as pendências
"partial legado" no MER, no backlog e nos relatórios. O menu real é o de `base.html` e **seu comportamento por perfil
não muda**.

## 2. P0 — estado inicial

- T1 (`6bbdd26`) e T2 (`73d2ee5`) já commitadas; suíte completa em **1006 passed, 0 failed**.
- Linha de base dirigida (menu por perfil), rodada **antes** de mexer: `test_conselho_professor` (15) +
  `test_l4_2_harness_perfis` + `test_conselho_ui` + `test_dashboard_professor_pedagogico` = **28 passed**.

## 3. P1 — o que o partial era, de fato

| Pergunta | Resposta (grep) |
| --- | --- |
| Algum template `{% include %}` ou `{% extends %}` o usa? | **Não.** As únicas ocorrências de `partials/` em templates são `partials/_modal_agendamento.html` → `{% include "partials/_campos_agendamento.html" %}` e `{% include "partials/_modal_agendamento.html" %}` em `dashboard/secretaria.html` e `dashboard/servico_social.html`. |
| Alguma rota o renderiza? | **Não** — `render_template("partials/sidebar.html")` não existe no código. |
| Algum teste o referencia? | **Não.** `test_conselho_professor.py::test_sidebar_professor_ve_painel_e_nao_ve_itens_restritos` tem "sidebar" no **nome**, mas lê o corpo de `GET /conselho` — o menu vem de `base.html`. |
| E no CSS/JS? | `css/sidebar.css` e o JS do `toggleSidebar`/`sidebarBackdrop` servem ao `<aside class="app-sidebar" id="appSidebar">` de `base.html`; nada aponta para o partial. |
| Referências restantes | **9 ocorrências, todas em documentação**: MER §8.16; `backlog_desenvolvimento.md` (linha das mudanças do conselho); `ConselhoProfessor.md` (§Menu e §Pendências); `PainelProfessorRotaUnificada.md` (§Pendências); `PainelProfessorRotaVoltar.md` (§Pendências); `M1_RoteiroTesteManual.md` (local do seletor de unidade e lista de templates conferidos); `D5_0_desenho.md` (inventário de arquivos da fase D5). |

Conclusão: o arquivo era **código morto** — uma cópia paralela do menu, mantida "alinhada para não divergir" desde a
entrega do conselho pelo professor, sem efeito em nenhuma página.

## 4. Mudança

- **Apagado** `app/templates/partials/sidebar.html` (155 linhas).
- **Nada** em `base.html` foi tocado: estrutura, itens por perfil, seletor de unidade, CSS e JS permanecem os mesmos.
- Nenhuma rota, guarda, permissão ou consulta alterada — por isso não há migration e o ensaio em banco próprio foi
  dispensado (não há o que exercitar além do que a suíte já cobre).

### Docs atualizados (pendências "partial legado" → resolvidas)

| Arquivo | O que mudou |
| --- | --- |
| `app/models/MER.md` | §8.16: a frase do partial legado riscada com a nota da resolução; **nova §8.19 "Menu único"** descrevendo a remoção. |
| `backlog_desenvolvimento.md` | Seção nova "T3 — menu único" e a linha da entrega do conselho (que dizia "é legado e ficou alinhado") atualizada para "removido na T3". |
| `docs/Relatórios/ConselhoProfessor.md` | §Menu e §Pendências: pendência riscada e marcada como **RESOLVIDO em 29/10/2026**. |
| `docs/Relatórios/PainelProfessorRotaUnificada.md` | §Pendências: idem. |
| `docs/Relatórios/PainelProfessorRotaVoltar.md` | §Pendências: idem. |
| `docs/Relatórios/M1_RoteiroTesteManual.md` | O seletor de unidade passou a apontar para `app/templates/base.html` (é onde ele vive) e a lista de templates conferidos trocou `partials/sidebar.html` por `base.html`. |
| `docs/Relatórios/D5_0_desenho.md` | **Não alterado** — é inventário/snapshot de desenho da fase D5, não uma pendência; a referência fica como registro histórico e está reportada aqui. |

## 5. Testes

- **Sem ajuste** em nenhum teste, como previsto. Os testes de menu por perfil (`test_conselho_professor`,
  `test_l4_2_harness_perfis`, `test_conselho_ui`, `test_dashboard_professor_pedagogico`) passaram **28 → 28**.
- Suíte completa após a remoção: **1006 passed, 0 failed** (mesmo total da T2 — nenhum teste removido, nenhum novo).
- Ruff: nada de Python alterado nesta tarefa; `ruff --select F821,F811,F841` mantido limpo nos arquivos da sessão.

## 6. Efeito colateral conhecido (reportado, não corrigido)

O `README.md`/`wiki.md` não citam o partial, então não há o que alinhar. A única consequência prática da remoção é
que edições futuras do menu acontecem **num só lugar** — historicamente o risco era alterar `base.html` e esquecer o
partial (foi o que aconteceu nas entregas de conselho e do painel do professor, quando os dois "foram mantidos alinhados").
