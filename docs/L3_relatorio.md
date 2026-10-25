# ETAPA L3 — Sincronização do MER e do backlog com o estado atual

**Data:** 25/10/2026
**Escopo:** somente documentação — `app/models/MER.md` e `backlog_desenvolvimento.md`.
**Autorizado e alterado:** apenas esses dois arquivos (ver §6 sobre `app/static/css/sidebar.css`).
**Suíte:** não executada nesta etapa (etapa só de docs); valor vigente herdado da D5.5: **359 passed, 0 falhas**.

---

## 0. Fontes lidas

| Fonte | Uso |
|---|---|
| `docs/T1_relatorio.md`, `docs/P1_relatorio.md` | base do §10 (correção de "em produção") e da dívida B5-P1/B5-P2 |
| `docs/V1_relatorio.md` | conferência de histórico antigo (sem alteração) |
| `docs/B7_relatorio.md` | entrada B7 no §10 e no backlog |
| `docs/D5_0_desenho.md` | decisões Q1/Q4/Q5 que sustentam o §8.2 reescrito |
| `docs/D5_1_relatorio.md` … `docs/D5_5_relatorio.md` | entradas D5.0–D5.5, números de suíte, natureza de cada etapa |
| `docs/relatorio_migracao_rotas.md`, `docs/Plano_Acao_Carga_Horaria.md`, `docs/manual_*.md` | conferência de afirmações sobre rotas/deploy (sem alteração) |
| `app/models/MER.md` | documento editado |
| `backlog_desenvolvimento.md` | documento editado |
| código (`app/`, `tests/`, `migrations/`) | verificação de cada afirmação nova (grep/leitura) |

Regra aplicada: **onde relatório e código divergem, o texto registra as duas leituras** em vez de escolher uma.

---

## 1. MER — Passo 1 (esquema)

### §7.7 `turma`
- **Removida** a linha `conselho_concluido` da tabela de colunas.
- Acrescentada nota de remoção: a coluna **não existe mais** desde `f6a7b8c9d0e1` (D5.5); o encerramento é da oferta (`turma_curso.conselho_concluido`) e a visão da turma é derivada na leitura por `turma_conselho_concluido()`.
- `avaliacao_inicial`, `avaliacao_percurso` e `avaliacao_final` marcadas **LEGADO**, com a indicação do novo local (`turma_curso.avaliacao_*`) e a condição de remoção ("após conferir o dump autêntico").
- **Conferência no código:** `app/models/academico.py` — `Turma` não declara mais `conselho_concluido`; mantém as três colunas `avaliacao_*`.
- **Conferência na migration:** `f6a7b8c9d0e1_conselho_oferta_endurecimento_d55.py` dropa `turma.conselho_concluido` (batch no SQLite) e não toca nas `avaliacao_*`.

### §7.24 `conselho_classe`
- `turma_curso_id` agora descrita como **não nula**, FK → `turma_curso` com `ON DELETE RESTRICT`, anotada como D5.5 ("conselho sem oferta não existe").
- Registrada a **unicidade por oferta**: `uix_conselho_oferta` = UNIQUE (`turma_curso_id`, `aluno_id`, `etapa`), com a observação de que o predicado `WHERE turma_curso_id IS NOT NULL` foi **mantido e é inócuo** desde o NOT NULL (nenhum índice novo foi criado na etapa).
- Registrado o índice de apoio `ix_conselho_turma_curso` (não único).
- Registradas as **remoções**: UNIQUE antiga `uix_conselho_turma_aluno_etapa` (`turma_id`, `aluno_id`, `etapa` — já removida na D5.1) e o índice parcial do ramo legado `uix_conselho_legado` (removido na D5.5).
- Registrado que a leitura é sempre por (`aluno_id`, `turma_curso_id`, `etapa`) via `app/services/conselho_leitura.py`, e que `turma_id` permanece denormalizado por compatibilidade.
- **Conferência no código:** `app/models/conselho.py` (`ConselhoClasse.turma_curso_id` `nullable=False`, `ondelete="RESTRICT"`).
- **Conferência na migration:** `f6a7b8c9d0e1` — `alter_column` para NOT NULL, recria `uix_conselho_oferta` apenas se ausente, `DROP INDEX uix_conselho_legado`.

### §7.32 `turma_curso`
- Acrescentadas as colunas `conselho_concluido` (bool, NOT NULL, default false — encerramento **manual** da oferta) e `avaliacao_inicial` / `avaliacao_percurso` / `avaliacao_final` (text, JSON de perguntas tipo TURMA).
- Nota de migration consolidada: `e5f6a7b8c9d0` (D5.1) cria as colunas; `f6a7b8c9d0e1` (D5.5) as torna a **única** fonte do encerramento e do parecer coletivo (a flag e os pareceres de `Turma` foram aposentados).

### §6.2 e §6.5 (diagramas ER)
- Adicionada a aresta `TURMA_CURSO ||--o{ CONSELHO_CLASSE : oferta`, deixando explícito que o conselho pende da oferta e não apenas da turma. A aresta antiga `TURMA ||--o{ CONSELHO_CLASSE` permanece porque `turma_id` continua existindo (denormalizado).

### §4 (multitenancy)
- Novo item 9: `conselho_classe` **não** tem dimensão própria de unidade além do `unidade_id` herdado do `TenantMixin` (nullable, espelho da unidade da turma/oferta); a unicidade por oferta (`uix_conselho_oferta`) não inclui unidade; o escopo é aplicado nas rotas (`assert_unidade_context`) e nos leitores.
- **Conferência no código:** `ConselhoClasse` herda `TenantMixin` e não redeclara `unidade_id`; `uix_conselho_oferta` é `turma_curso_id + aluno_id + etapa` — confirmado na migration e no modelo.

### Cabeçalho e §11
- **Cabeçalho:** "Última atualização" reescrita para 25/10/2026 com a lista de etapas sincronizadas (T1, P1, B1–B7, M1, M1.1, M2, M4, L1, L2, D5.0–D5.5), o resumo do conselho por oferta (NOT NULL, `Turma.conselho_concluido` removida, leitores por oferta) e **Suíte: 359 passed**.
- **§11:** duas linhas novas na tabela — `e5f6a7b8c9d0` (D5.1, aditiva) e `f6a7b8c9d0e1` (D5.5, endurecimento + drop da coluna da turma); nota de **head atual** (`f6a7b8c9d0e1`, única cabeça esperada em `flask db heads`); §11.1 item 6 atualizado para refletir que a UNIQUE antiga foi removida na D5.1.

---

## 2. MER — Passo 2 (regras)

### §8.2 Conselho de Classe — reescrita completa (agora "por OFERTA desde a D5.1–D5.5")
Blocos novos/reescritos:
1. **Unidade de resultado:** `(aluno, OFERTA, etapa)`; `turma_curso_id` NOT NULL; `uix_conselho_oferta`; `turma_id` denormalizado. `situacao_final`/`proxima_turma_id` por oferta (Q4 da D5.0).
2. **Escrita por oferta (D5.2/D5.2b), padrão M1 0/1/2+:** lançamento (`oferta_sel`/`turma_curso_id` validado contra `ofertas_ativas`), fechamento (lista os alunos **da oferta**, grava `situacao_final` normalizada e `proxima_turma_id` do catálogo `OpcaoProximaTurma`, validação atômica, POST JSON **com CSRF**), avaliação coletiva (parecer TURMA em `turma_curso.avaliacao_*`).
3. **Encerramento MANUAL por oferta** (`POST /turma/<id>/alternar-conselho`): alterna `TurmaCurso.conselho_concluido`, não escreve na turma, exige oferta ativa da própria turma e isolamento por unidade.
4. **Encerramento DERIVADO da turma (D5.3):** `turma_conselho_concluido()` verdadeiro só com ≥1 oferta ativa e todas concluídas; turma sem oferta ativa **não abre conselho** e **não entra nas contagens** (`contar_ofertas_conselho()`).
5. **Leitura por oferta (D5.4/D5.5):** `conselho_leitura.py` (lote, sem N+1, `turma_curso_id=None` nunca adotado); leitores migrados (histórico, ficha 360° com `?oferta_sel=`, painel por turma, resultado do conselho, certificado), uma linha por inscrição.
6. **BI:** `CRU-002` conta aluno **distinto** por raça/cor; `CRU-005` conta uma linha por situação; ambos filtram por unidade e opcionalmente período/curso/turma/professor **da turma** (BI não migrado para oferta — decisão da D5.4).
7. **Resíduos legados:** `Turma.avaliacao_*` (LEGADO, remoção condicionada ao dump autêntico); conselho sem oferta recusado pelo banco.

Correção factual: a versão anterior atribuía `conselho_final` a `ConselhoClasse`. **É coluna de `periodo_conselho`** (§7.21); o texto agora diz "é coluna de `periodo_conselho`, não de `ConselhoClasse`" e mantém `PeriodoConselho` como janela por **período letivo e unidade**.

### §8.10
- Bullet "D5 decidido, implementação pendente" **removido**.
- Bullet "Conselho, ficha do aluno, BI e transferências ainda leem por `turma_id`" **substituído** por três bullets:
  - *Conselho de classe concluído (D5, 24–25/10)*: escrito e lido por oferta; `Turma.conselho_concluido` removida.
  - *O que ainda lê/agrega por `turma_id` (D3b-2/J3, aberto)*: frequência e diário do ramo legado (`app/utils/logica.py`, `app/utils/frequencia.py`), `Turma.freq_geral`, `agregar_por_turma` (painel pedagógico), BI de frequência (`frequencia_por_turma`/`frequencia_por_curso` e vizinhos), `calcular_frequencias_relatorio` e `freq_geral` da listagem/BI; indicadores de conselho do BI filtram pela turma. Histórico, ficha 360° e certificado já são por inscrição/oferta.
  - *Transferências*: POST exige oferta de destino (M2), mas a tabela não persiste oferta de origem/destino.
- Novos bullets: **B7** (visão por período; `_montar_turma_linha` nunca existiu desde `1c8604c`; omite turma sem frequência — §12.21) e **D5.4** (HTTP 500 latentes da ficha 360° e do painel por turma/resultado do conselho, corrigidos).
- **Confirmação por grep do que continua por `turma_id`:** `Frequencia.turma_id` usado em `app/utils/logica.py` (busca legada com `turma_curso_id IS NULL`), `app/utils/frequencia.py`, `Turma.freq_geral` (`app/models/academico.py`), `agregar_por_turma` (`app/relatorios/painel_pedagogico/frequencia.py:26`, agrupa por `Frequencia.turma_id`), `frequencia_por_turma`/`frequencia_por_curso` (`app/relatorios/bi_alunos.py`) e `calcular_frequencias_relatorio` (`app/relatorios/geral.py`).

---

## 3. MER — Passo 3 (histórico e dívidas)

### §10 — Histórico de ondas
Novas entradas por etapa (o que mudou, arquivos principais, suíte):

| Etapa | Suíte |
|---|---|
| L2 (só docs) | não executada |
| D5.0 (desenho) | 291P |
| D5.1 (migration aditiva + backfill inequívoco) | 297P |
| D5.2 (escrita por oferta, M1, fechamento JSON, avaliação coletiva) | 320P |
| D5.2b (4 defeitos de tela, CSRF do fechamento) | 324P |
| D5.3 (encerramento/contagens por oferta) | 337P |
| D5.4 (leitores por oferta via `conselho_leitura.py`) | 349P |
| B7 (`_montar_turma_linha`) | 352P |
| D5.5 (endurecimento, NOT NULL, drop de coluna, seletor da ficha) | 359P |

Também corrigidas, no mesmo §10: a linha histórica da Fase 4 (que listava como pendentes a ficha do aluno, os certificados e o histórico por `turma_id`) e as menções de T1/P1 a "produção".

### §12.18
- Cabeçalho e status atualizados para **CONCLUÍDO (24–25/10/2026)**, com remissão ao §8.2 e às migrations `e5f6a7b8c9d0` + `f6a7b8c9d0e1`; "Resíduos" aponta para §12.19 e §12.20.

### §12 — Novas dívidas
- **§12.19** `Turma.avaliacao_inicial/percurso/final` — LEGADO; remoção só após diagnóstico no dump autêntico (risco de perder parecer de turma com 2+ ofertas, não copiável para uma oferta única).
- **§12.20** `turma_conselho_concluido()` sem leitor no código de aplicação (só testes). **Verificado por grep:** a função é definida em `app/services/turma_curso.py:57` e referenciada apenas em `tests/test_d5_encerramento.py`; `contar_ofertas_conselho()` tem leitores (`app/conselho.py:880`, `app/utils/logica.py:691`).
- **§12.21** Painel por período omite turma sem frequência lançada (`periodo.py`, `if not info: continue` — comportamento implementado na B7).
- **§12.22** `agregar_por_turma` agrega por `turma_id` (soma as ofertas).
- **§12.23** N+1 residual do histórico (frequência consultada por inscrição; conselhos já em lote).
- **§12.24** CSRF e UX do fechamento exigem teste manual no navegador (a suíte roda com `WTF_CSRF_ENABLED=False`).
- **§12.17 (B5-P1) — CAUSA:** `flask db upgrade` e `flask_migrate.upgrade()` passam por `catch_errors`, que loga e chama `sys.exit(1)`; o `fileConfig(...)` de `migrations/env.py` roda com `disable_existing_loggers=True` e **desabilita** o logger do Flask-Migrate, de modo que o `RuntimeError` das checagens desaparece e o operador só vê `exit code 1`. Correção pendente: `fileConfig(..., disable_existing_loggers=False)` na etapa de preparação do deploy; até lá, a mensagem só aparece chamando `alembic.command.upgrade` direto (`instance/backups/ensaio_d55/msg_upgrade.py`).

### "em produção"
Corrigida em todo o MER e no backlog a expressão onde o ambiente era apenas local/teste. Não há produção real; o banco local veio de dump antigo e o **dump autêntico não existe**:
- MER §1: `Banco: PostgreSQL (banco local de desenvolvimento/ensaio) / SQLite (testes). Não há ambiente de produção real…`.
- MER §10 (T1/P1) e §12.17: "produção" → "banco local/ensaio" e "dump autêntico".
- Backlog: quatro ocorrências (linhas ~341, ~384, ~427 e ~473 do arquivo anterior) reescritas para banco local/ensaio.

---

## 4. Backlog — Passo 4

### Seção "Alterações do dia — 25/10/2026"
Reescrita com entradas por etapa (T1, P1, B1–B7, M1, M1.1, M2, M4, L1, L2, D5.0–D5.5), cada uma com o que mudou, arquivos principais e o número da suíte; fechamento com **"Ao final da D5.5: 359 passed, 0 falhas"** (o "291 passed" ficou explicitamente marcado como **histórico de L1**).

### "Pendências abertas (pós-L3)"
Reorganizada. **Removidos** (resolvidos): conselho por oferta e seus itens; código morto de inscrição NULL (removido na B6/T1). **Mantidos/reformulados**:

1. **D3b-2/J3** — frequência, BI de frequência, `freq_geral`, relatórios; ALU-009/ALU-010 sem `cond_inscricao_enturmada`; programa lido de `Turma.programa` (projeção) em vez de `turma_curso.programa`; subtópicos: estatísticas do GET `/frequencia` e as limpezas de `excluir_turma`/`editar_turma` por `turma_id`.
2. **Fases 5–7 (a redefinir)** — autorização por professor da oferta, turno e centro de custo por oferta, transferências avançadas (Fases 8–9 e NOT NULL final concluídas).
3. **`Transferencia`** — decidir se registra oferta de origem/destino.
4. **`turma_lixeira`** — template inexistente e sem rota de reativar (permanece).
5. **Frequencia/RegistroAula legados com `turma_curso_id IS NULL`** — backfill sem fase definida e suas consequências.
6. **Dívida de migrations §11.1** (itens 2–6 e 8 do MER).
7. **Dump autêntico** para novo ensaio.
8. **B5-P1 — corrigir `migrations/env.py`** (com a causa e a correção).
9. **Teste manual no navegador** dos fluxos de conselho e de relatórios/painel.
10. **`conftest.py` único (P7)**, **duplicação de `cond_oferta_efetiva`**, **lista de programas embutida em `ofertas.html`**, **`avisos_horario` transiente**.
11. **Onda 3C** (JSONs legados de `Aluno`) e **resíduos §12.19–§12.24** do MER.

### Restrição de publicação
Registrado na entrada **D5.4** que "as leituras passaram a fechar por oferta — a restrição de publicação aberta na D5.2 foi encerrada aqui", com a nota de que o relatório D5.4 ainda dizia "só fecha na D5.5" (ver §5.1).

---

## 5. Divergências relatório × código (registradas, não escolhidas)

1. **Restrição de publicação D5.2 → D5.4/D5.5.** O enunciado da L3 afirma que a restrição "não publicar entre D5.2 e D5.4" foi **encerrada na D5.4**; `docs/D5_4_relatorio.md` registra que o contrato de leitura "só fecha na D5.5". O texto dos dois documentos agora cita **as duas leituras**: encerrada na D5.4 (leitores já por oferta) e consolidada na D5.5 (escrita/estrutura por oferta, `turma_curso_id` NOT NULL).
2. **Docstrings ainda citam a ponte removida.** `app/services/turma_curso.py:64-65` ("a coluna permanece apenas como ponte de escrita até a D5.5") e `app/services/conselho_leitura.py:8-10` ("Nenhum acoplamento com `Turma.conselho_concluido` … ponte de escrita até a D5.5") descrevem um estado que **não existe mais**. É código — **fora do escopo autorizado da L3** —, portanto apenas relatado; o MER registra o estado real (§7.7, §8.2) e a divergência fica anotada aqui.
3. **`turma_conselho_concluido()` "derivado oficial" × sem leitor.** B7/D5.3/D5.4 apresentam a função como derivado oficial do encerramento da turma, mas o grep mostra que só os testes a chamam. Registrado em §12.20 (MER) e no backlog, sem alterar código.
4. **`conselho_final`.** O §8.2 anterior atribuía a coluna a `ConselhoClasse`; o código (`app/models/conselho.py`) e o §7.21 mostram que é de `periodo_conselho`. Corrigido no MER.
5. **Histórico/ficha/certificado "ainda por `turma_id`".** O §10 (linha histórica da Fase 4) e o item de pendências da D3b-2 repetiam que ficha, certificados e histórico liam por `turma_id`; o código da D5.4 já os migrou. Corrigido em §8.10 e §10.
6. **"5 bugs latentes" (D5.4) × descrição resumida no MER.** O relatório lista 5 defeitos; o MER cita 4 causas (`inscricao.status_aluno`, `pres_acum/falt_acum`, `map(attribute="isoformat")` e `ConselhoClasse.aluno`) e remete ao relatório. Sem conflito material — mantido como resumo.
7. **Ambiente "de produção".** Relatórios antigos (T1, P1, V1) usam a expressão para o banco restaurado de dump; não existe produção real nem dump autêntico. Uniformizado para "banco local/ensaio".

---

## 6. Passo 5 — afirmações obsoletas encontradas

Varredura em `app/models/MER.md` e `backlog_desenvolvimento.md` pelos padrões `aguardando`, `pendente`, `D5`, `Fases 5-9`, `conselho_concluido`, `291 passed`, `em produção`, `ainda leem`, `implementação pendente`.

| Documento / local | Achado | Ação |
|---|---|---|
| MER §8.10 | "D5 decidido, implementação pendente" | **corrigido** (substituído pelo estado real) |
| MER §8.10 | "Conselho, ficha do aluno, BI e transferências ainda leem por `turma_id`" | **corrigido** (separado em conselho concluído / o que resta por `turma_id` / transferências) |
| MER §10, linha da Fase 4 | "ficha do aluno, … certificados e histórico ainda leem por `turma_id`" | **corrigido** (ficha, histórico e certificado leem por oferta desde a D5.4) |
| MER §10, mesma linha | "Pendências restantes: D3b-2 (frequência, BI de frequência e relatórios)" | **corrigido** (+ `freq_geral`) |
| MER §8.2 (antigo) | `conselho_final` atribuída a `ConselhoClasse` | **corrigido** (é de `periodo_conselho`) |
| MER §12.18 | "D5 … pendente/decidido" | **corrigido** (CONCLUÍDO) |
| MER §1, §10 (T1/P1), §12.17 | "em produção" | **corrigido** |
| MER §12.3 "Pendente:", §7.16 "Decisão pendente", §7.2/§12.17 "pendente", §10 "Onda 3C — Pendente" | uso legítimo (dívidas reais) | mantidos |
| MER §12.20/§12.21/§12.22/§12.23/§12.24 e §8.2/§8.10 | `conselho_concluido` citado para **explicar a remoção** ou como coluna **da oferta** | mantidos (corretos) |
| Backlog, linha 26 | "Estado da suíte ao final de L1: 291 passed" | mantido, **rotulado como histórico**, seguido de "Ao final da D5.5: 359 passed" |
| Backlog, entradas 22–24 | menções a D5.1–D5.5, `conselho_concluido` (ponte, drop), `_montar_turma_linha` | mantidas (relato histórico correto) |
| Backlog | "Fases 5–9" | não havia ocorrência; o texto vigente fala em **Fases 5–7** (8–9 concluídas) |
| Backlog / MER | "aguardando" | nenhuma ocorrência |

**Não corrigidos por não serem inequívocos (registrados aqui):** docstrings de `app/services/turma_curso.py` e `app/services/conselho_leitura.py` (§5.2) — dependem de edição de código, fora do escopo.

---

## 7. Verificação de escopo (`git status`)

`git status --porcelain` retorna **53 entradas** (38 modificadas/deletadas rastreadas + 15 não rastreadas). Todas as demais decorrem das etapas **B7 a D5.5**, que seguem **sem commit** por decisão do protocolo do projeto (nenhum commit foi feito nesta etapa).

Nesta etapa (L3), as únicas edições feitas por mim foram:
- `app/models/MER.md`
- `backlog_desenvolvimento.md`

**Achado a confirmar pelo usuário:** `app/static/css/sidebar.css` também aparece com mtime 25/10 19:21 (mesmo minuto dos dois docs) e difere do HEAD em 2 linhas:

```diff
-  --topbar-height: 56px;
+  --topbar-height: 48px;
...
-}\ No newline at end of file
+}
```

Essa alteração **não foi feita nesta etapa** (nenhuma ferramenta de edição foi usada nesse arquivo). Provável causa: edição manual no editor/sincronização do Nextcloud no mesmo intervalo. Recomendo conferir antes do commit; o MER e o backlog não dependem dela.

---

## 8. Arquivos alterados nesta etapa

- `app/models/MER.md` — cabeçalho, §1, §2, §3, §4 (item 9), §6.2, §6.5, §7.7, §7.24, §7.32, §8.2, §8.10, §10, §11, §11.1, §12.17, §12.18, §12.19–§12.24.
- `backlog_desenvolvimento.md` — seção 25/10, "Pendências abertas (pós-L3)", linha histórica de 22/10 (D5 concluído, D3b-2 reduzido) e quatro correções de "em produção".
- `docs/L3_relatorio.md` — este relatório.

**Não alterados:** código, testes, migrations, demais docs. **Nenhum commit.**
