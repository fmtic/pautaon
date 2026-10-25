# ETAPA L2 — Relatório

**Data:** 25/10/2026
**Escopo autorizado:** somente `app/models/MER.md` e `backlog_desenvolvimento.md`.
**Código, testes, migrations e demais docs:** intocados. **Commit:** não realizado.

---

## Passo 1 — Restauração dos docs deletados

Executado `git checkout -- docs/M1_relatorio.md docs/M1_1_relatorio.md docs/checklist_seguranca_dividas_tecnicas.md`. `git status --short` confirma que as três linhas `D` desapareceram — os arquivos voltaram ao estado do HEAD e não aparecem como modificados. `M1_relatorio.md` (73 linhas) e `M1_1_relatorio.md` (130 linhas) foram lidos na íntegra e serviram de base para o Passo 2. `checklist_seguranca_dividas_tecnicas.md` foi restaurado sem necessidade de leitura para as correções desta etapa.

## Passo 2 — Entrada do M1 e inclusão do M1.1

### O que estava errado

A entrada anterior do M1 no MER §10 e no backlog (dia 24/10) omitia a M1.1 e misturava regras históricas com regras vigentes. Faltava ainda registrar que a **lógica de adoção/vínculo de `Inscricao` NULL** — tanto em `enturmar_alunos` quanto em `adicionar_oferta` — foi **tornada obsoleta** pelo NOT NULL de `c3d4e5f6a7b8` (T1) e removida.

### Correções aplicadas (MER §10 + backlog dia 25/10)

- **M1 (24/10)** no MER e no backlog: enturmação por oferta com `enturmar_alunos` gravando `turma_curso_id`; regras 0/1/2+ ofertas (0 recusa; 1 automática; 2+ exige escolha validada contra `ofertas_ativas`); duplicidade por aluno+turma+oferta; `ver_turma` com `?oferta_sel=&modal=enturmar`, disponíveis por oferta e selos de curso por aluno (`cursos_por_aluno`); 11 testes em `tests/test_enturmacao_oferta.py`; semente de `test_security_regressions` ganhou 1 oferta. Suíte ao fim do M1: 211P/2F preexistentes em `/cursos`.
- **M1.1 (24/10)** no MER e no backlog: adoção de `Inscricao` NULL ativa ao enturmar (menor id, `data_inicio` preservado) e criação de `scripts/verificar_onda4_m1.py` (somente leitura). +6 testes (17 total naquela rodada). Registrado que essa lógica foi **substituída** pelo NOT NULL de `c3d4e5f6a7b8` e **removida na T1** (7 testes eliminados; restam 13 em `test_enturmacao_oferta.py`).
- **Script `scripts/verificar_onda4_m1.py`**: confirmado presente no repositório (Glob retornou o arquivo; 164 linhas).

### Divergências relatório × código atual (registradas, não "escolhidas")

| Afirmação no relatório M1/M1.1 | Estado no código hoje | Como foi tratado |
|---|---|---|
| "`adicionar_oferta` vinculava NULL ativas" | A função hoje (em `app/services/turma_curso.py:~321`) **não** contém o ramo `Inscricao.turma_curso_id.is_(None)` — a lógica foi removida pela T1 após o NOT NULL de `c3d4e5f6a7b8`. | Redigido no MER §10 e no backlog como regra **histórica** do M1, com nota explícita de que o ramo foi removido na T1. |
| "adoção de `Inscricao` NULL ativa ao enturmar" (M1.1) | Não existe mais em `enturmar_alunos` (`app/registros/turmas.py:~1037`). | Mesmo tratamento: marcado como obsoleto/removido; mantido o texto original como registro histórico. |
| "11 testes em `test_enturmacao_oferta.py`" | Grep `^def test_` retornou **13** testes atualmente (M1.1 somou 6 → T1 removeu 4 lógicos). | No MER §10 mantive "11 testes" como o número histórico do M1; na linha da M1.1 acrescentei "+6 → 17 total; restam 13 após a T1". |
| "`scripts/verificar_onda4_m1.py` criado na M1.1" | Confirmado presente. | Registrado como "ainda presente". |

## Passo 3 — Backlog, lista "Pendências abertas"

A lista foi renomeada para **"Pendências abertas (pós-L2)"** e reescrita:

- **(a) `turma_lixeira` (substituído):** a redação antiga ("Turma lixeira sem período — estado legado, D3/B6") foi trocada por: *"GET `/turmas/lixeira` renderiza `turma_lixeira.html` inexistente; não há rota para **reativar** turma desativada."* — conforme o enunciado.
- **(b) Pendências omitidas pela L1 e restauradas (texto resgatado da seção 23/10):**
  - Turma sem oferta que lança frequência e depois ganha a **primeira oferta**: registros com `turma_curso_id` NULL somem da tela por oferta e relançar o mesmo dia cria linha duplicada.
  - Turma que **desativa todas as ofertas** perde o histórico lançado por oferta na tela legada.
  - Estatísticas do GET `/frequencia` (`app/registros/core.py` ~L396–400) agregam oferta e legado **sem separar**.
  - `excluir_turma` e a limpeza em `editar_turma` apagam por `turma_id`, alcançando todas as ofertas.
  - **J3**: ALU-009/ALU-010 ainda não aplicam `cond_inscricao_enturmada`; BI ainda lê `Turma.programa` (projeção) em vez de `turma_curso.programa`.
- **(c) Acrescentada:** *"`Transferencia` (MER §7.16) **não registra a oferta de origem nem a de destino** — apenas `turma_origem_id`/`turma_destino_id`; decisão pendente sobre adicionar colunas `turma_curso_id_origem`/`_destino` ou manter rastreamento via `Inscricao`."*
- **(d) Acrescentada:** *"Frequencia/RegistroAula legados com `turma_curso_id IS NULL` ainda existem em produção (coluna nullable); backfill definitivo só na antiga Fase 9 (fora do alcance das rotas atuais de leitura, que preservam `IS NULL` de propósito)."* — nota: a "Fase 9" original tratava do NOT NULL de `inscricoes` (aplicado); a coluna de `frequencia`/`registro_aula` continua nullable e o backfill definitivo ainda não tem fase designada.

Pendências já resolvidas que **saíram** corretamente da lista: NOT NULL `inscricoes.turma_curso_id` (T1), NOT NULL `turma_curso.programa` (B5), M2 serviço único, M4 guarda e `cond_oferta_efetiva`, D5 decidido, B4 isolamento em rotas de escrita, B6 código morto NULL removido.

## Passo 4 — MER, resíduos

| Subseção | Correção |
|---|---|
| **§2 (árvore `app/services/`)** | Incluídos `turma_curso.py`, `aluno_status.py`, `maintenance.py` e `enturmacao.py` com uma linha descritiva cada. |
| **§3 glossário — "Inscrição"** | Removida a expressão "na transição"; agora: *"Vínculo do aluno a uma oferta concreta (`inscricoes.turma_curso_id`, NOT NULL desde `c3d4e5f6a7b8`), com histórico de ativação/desativação por oferta."* |
| **§6.3 (Mermaid)** | Arestas `TURMA_CURSO |o--o{ INSCRICAO` (zero ou um) trocadas por `TURMA_CURSO ||--o{ INSCRICAO` (obrigatório), alinhado ao NOT NULL. |
| **§7.16 (`transferencia`)** | Adicionada nota: *"a transferência é por oferta (`turma_curso_id_destino` obrigatório no POST de `transferir_aluno`; ver §8.10), porém a tabela **não persiste** `turma_curso_id` de origem nem de destino — apenas `turma_origem_id`/`turma_destino_id`. Rastrear qual oferta foi envolvida exige consultar `Inscricao`. Decisão pendente."* |
| **§10, bullet "Etapa J2"** | Rebatizado **"Etapa J2 (histórica; regra vigente em §8.10)"**; o texto foi preservado para contexto histórico com pointer claro para `cond_oferta_efetiva()` e §8.10 como regra atual, sem o antigo ramo NULL. |

## Passo 5 — Afirmações obsoletas encontradas

Varredura com `Select-String` sobre `app/models/MER.md` e `backlog_desenvolvimento.md`, buscando os padrões `aguardando decis`, `Fase 9`, `Fases 5-9`, `NOT NULL final pendente`.

### Corrigidas (inequívocas)

1. **MER §10 (linha ~1154)** — "Pendentes: **Fases 5–9** (... NOT NULL final pendente ...)" e "D5 conselho aguardando decisão": reescrito para **"Fases 5–7 ... as Fases 8–9 ... e a NOT NULL final ... estão concluídas ou decididas; D5 conselho por oferta decidido em 24/10/2026"**. Fechamento da lista: "Pendências restantes: D3b-2, Fases 5–7; D5 decidido (implementação pendente)."
2. **Backlog (linha 231, seção 22/10)** — "**D5 conselho — aguardando decisão**" e "Fases 5–9 ... NOT NULL final em `inscricoes.turma_curso_id` (Fase 9)": reescrito com prefixo *"Pendências da Onda 4 (registro histórico de 22/10; status atualizado na L2)"*, separando Fases 5–7 (ainda pendentes) de Fases 8–9 + NOT NULL (**aplicadas**: `c3d4e5f6a7b8` T1 + `d4e5f6a7b8c9` B5), e marcando D5 como **decidido 24/10/2026** com implementação pendente e pointer ao §12.18 do MER.

### Não corrigidas (ambíguas ou contextuais)

- **Backlog linha 38** (recém-adicionada na lista "Pendências abertas (pós-L2)"): usa a expressão "backfill definitivo só na Fase 9". Não é inequivocamente obsoleta — a "Fase 9" original cobria o NOT NULL de `inscricoes` (aplicado); para `frequencia`/`registro_aula` a coluna continua nullable e ainda **não há** fase designada para o backfill definitivo. Mantive a referência com nota explicativa, sem renumerar, por segurança (evitar "inventar" fase nova em doc).
- **Linhas 217, 225, 228, 237, 243 do backlog**: contêm "Fase 1", "Fase 4", "Onda 4 (Fix PG + Fase 3)" — são **descrições contextuais históricas** de migrations e rotas daquela época, **não afirmações sobre trabalho pendente**. Corrigi-las apagaria registro histórico; preservadas.
- **MEN §7.16 nota sobre Transferência**: acrescentada no Passo 4; não havia redação antiga a corrigir.

## Conferência final

- `git status --short`: as duas autorizadas (`app/models/MER.md`, `backlog_desenvolvimento.md`) aparecem como `M`; os três restaurados (`docs/M1_relatorio.md`, `docs/M1_1_relatorio.md`, `docs/checklist_seguranca_dividas_tecnicas.md`) **não** aparecem (voltaram ao HEAD). Demais `M` e `??` são resquício das etapas anteriores ainda sem commit — não alterados nesta L2.
- `app/templates/turmas/detalhe copy.html` ainda figura como `D` — é a limpeza deliberada feita na L1/A1 e não foi revertida aqui.
- Suíte de testes **não** foi rodada nesta etapa (só documentação), conforme o enunciado.

## Resumo das mudanças por seção

**MER.md**
- §2: árvore de `app/services/` expandida (turma_curso, aluno_status, maintenance, enturmacao).
- §3: linha "Inscrição" reescrita (aponta para oferta, NOT NULL).
- §6.3: `TURMA_CURSO ||--o{ INSCRICAO` (obrigatório).
- §7.16: nota sobre ausência de colunas de oferta em `transferencia`.
- §10: entradas M1 e M1.1 reescritas com datas e escopo correto; bullet "Etapa J2" marcado como histórico com pointer a §8.10; lista "Pendentes" reescrita separando concluídas/decididas (Fases 8–9, NOT NULL, D5) das ainda em aberto (Fases 5–7).

**backlog_desenvolvimento.md**
- Dia 25/10: M1 (24/10) reescrito; M1.1 (24/10) adicionado com nota de obsolescência da adoção NULL.
- "Pendências abertas (pós-L2)": renomeada, `turma_lixeira` substituído, 5 itens restaurados da 23/10, 2 novos (Transferência, Frequência legado).
- Seção 22/10 (linha 231): "Fases 5–9" e "D5 aguardando decisão" substituídos por texto atualizado com pointer ao §12.18 do MER.
