# D5.3 — Encerramento e contagens do conselho por oferta

**Status:** concluída. Suíte completa: `337 passed, 74 warnings in 52.13s` (0 falhas; meta ≥324). Sem commit.
**Fontes:** docs/D5_0_desenho.md (§2.6, D5.3), docs/D5_2_relatorio.md, docs/D5_2b_relatorio.md.

> ⚠️ **Continua valendo: NÃO deve haver deploy/publicação entre a D5.2 e a D5.4.** Agora as LEITURAS do encerramento (painel, pendências, métricas do relatório geral e certificado) foram migradas para a OFERTA, mas ficha do aluno, histórico, BI e relatórios de resultado continuam lendo o legado até a D5.4.

---

## 1. Passo 1 — Leitura e classificação das leituras de `Turma.conselho_concluido`

`grep conselho_concluido` em `app/` (código + templates) ⇒ **exatamente três leituras em produção** e uma escrita-ponte:

| # | Local (antes) | Tipo de leitura | Destino nesta etapa |
|---|---|---|---|
| 1 | `app/conselho.py:852` — `informacoes()`: `Turma.query.filter_by(ativo=True, conselho_concluido=False, unidade_id=...).count()` | **Contagem** (pendências) | substituída por `contar_ofertas_conselho(unidade_id)` → `ofertas_pendentes`/`ofertas_total` |
| 2 | `app/utils/logica.py:684-690` — `calcular_metricas_conselho`: `Turma.query.filter_by(ativo=True, conselho_concluido=True)` × total | **Contagem agregada** (métrica) | substituída pelo mesmo helper (`concluidas × total` por oferta, respeitando unidade) |
| 3 | `app/registros/periodos.py:577` — `"concluido": turma.conselho_concluido` no montador do **certificado** | **Exibição** (ícone Concluído/Pendente por aluno×curso) | `turma_conselho_concluido(turma)` (derivado). A busca do `ConselhoClasse` FINAL (L551-555) foi **intocada** |
| — | `app/planejamento.py:86-90` — `alternar_conselho` | **Escrita** (ponte) | mantida — a coluna e a ponte ficam até a D5.5 |

Outros fatos da leitura:

- **(b) `index_conselho` (app/conselho.py:199-229) e `painel.html`** — o painel **não lia** o flag: listava TODAS as turmas ativas (com filtros de programa/turno e professor), sem nenhum status de conselho e **sem botão de alternar** (a rota `planejamento.alternar_conselho` não tinha chamador em template algum). Os links de lançamento/fechamento não levavam oferta.
- **(c) `informacoes` (app/conselho.py:852-857)** — passava `turmas_pendentes` (count) e `informacoes.html:14-15` exibia "Turmas Pendentes".
- **(d) `calcular_metricas_conselho` (logica.py:642-700)** — devolve `progresso_reunioes`, `turmas_concluidas`, `total_turmas`; único consumidor é `relatorios/geral.py:73` (`metricas`), exibido em `relatorios/geral.html:82-89` ("Turmas Avaliadas" / "X de Y turmas finalizadas").
- **(e) `periodos.py:~577`** — o trecho **não é `periodos/lista.html`**: é o montador do **certificado** (`periodo_letivo_relatorio_certificado`, template `periodos/certificado.html:78-83`, ícone `title="Concluído"/"Pendente"`). `templates/periodos/lista.html` **não lê** o flag (nenhuma ocorrência de `conselho`/`concluido`) ⇒ não aplicável.
- **(f) `turmas.py`** — só há **um** `render_template("turmas/detalhe.html")` (L1020-1021) e a query `perguntas` (L990) que só alimentava esse parâmetro. Ambas removidas (ver §4).
- Nenhum template lê a coluna diretamente; `app/models/academico.py:99/136` é a definição/documentação.

---

## 2. Passo 2 — Helpers novos em `app/services/turma_curso.py` (+122)

- `turma_conselho_concluido(turma_ou_id)` — **derivado**: `True` somente se existir **ao menos uma oferta ativa** e **todas** estiverem com `TurmaCurso.conselho_concluido`; turma sem oferta ativa → `False`. Não lê a coluna da turma.
- `contar_ofertas_conselho(unidade_id=None)` → `(concluídas, total)` de ofertas ativas de turmas ativas (turma sem oferta ativa não entra em nenhum dos lados).
- `alunos_ativos_por_oferta(oferta_ids)` — contagem agrupada (`count(distinct aluno)`) em **uma** consulta.
- `ofertas_do_painel_conselho(unidade_id=None, *, programa, turno, professor_id)` — lista de view-models (`oferta`, `turma`, `curso`, `professor`, `programa`, `turno`, `concluida`, `alunos_ativos`) das ofertas ativas de turmas ativas, com `joinedload(turma/curso/professor)` + uma agregação de alunos ⇒ **sem N+1**. Filtros de programa/turno aplicados na TURMA (mesma semântica do dropdown existente); filtro de professor aceita oferta **ou** turma (professor legado).

---

## 3. Passo 3 — Leitores migrados (diff por arquivo)

| Arquivo | Mudança |
|---|---|
| `app/conselho.py` (+39/-9) | `index_conselho`: lista por **oferta** (`ofertas_do_painel_conselho`), passa `ofertas` + `turmas_sem_oferta` (aviso discreto, não conta como pendência). `informacoes`: `ofertas_pendentes`/`ofertas_total` via `contar_ofertas_conselho`. |
| `app/templates/conselho/painel.html` (+60/-21) | Um card por **oferta**: turma + curso, badge **Concluído/Pendente vindo da oferta**, programa/turno/professor/dias/horário/alunos da oferta; links de lançamento com `?oferta_sel=<id>` e fechamento com `?oferta_sel=<id>`; **botão de alternar encerramento por oferta** (form POST `planejamento.alternar_conselho` com `turma_curso_id`); aviso discreto para turmas sem oferta ativa; estado vazio "Nenhuma oferta ativa...". |
| `app/templates/conselho/informacoes.html` (+5/-3) | "Cursos Pendentes (Conselho Final)" + total de ofertas ativas; rótulo e variável migrados. |
| `app/utils/logica.py` (+8/-7) | `calcular_metricas_conselho` conta **ofertas** (`contar_ofertas_conselho`), mantendo as chaves `turmas_concluidas`/`total_turmas` do dict (compatibilidade do template). Import **local** do serviço para não criar ciclo `app.services → app.utils`. |
| `app/templates/relatorios/geral.html` (+2/-2) | Apenas rótulos: "Ofertas Avaliadas" e "X de Y ofertas finalizadas" — layout intacto. `relatorios/geral.py` **não** precisou mudar (já usa `calcular_metricas_conselho`). |
| `app/registros/periodos.py` (+4/-1) | Import do helper e `"concluido": turma_conselho_concluido(turma)` na montagem do certificado. A busca do `ConselhoClasse` FINAL (L551-555) **não** foi tocada. |
| `templates/periodos/lista.html` | **Não alterado** — não lê o flag. |

---

## 4. Passo 4 — Limpeza em `app/registros/turmas.py` (-3)

Grep confirmou que `perguntas` só existia para o modal removido na D5.2b (`detalhe.html` não a referencia). Removidos: `perguntas=perguntas` do (único) `render_template("turmas/detalhe.html")`, a query `PerguntaConselho.query...` que só a alimentava e o import `PerguntaConselho` (consequência direta, para não deixar import morto).

---

## 5. Testes — `tests/test_d5_encerramento.py` (13 testes, um usuário por teste)

Derivação: 1 oferta (False → True, aceitando id ou objeto); 2 ofertas com uma pendente (False) e todas concluídas (True); turma sem oferta ativa = `False` e `(0, 0)` nas contagens; oferta **inativa** ignorada (conclui a turma e conta só a ativa).

Painel: com 2 ofertas e **`Turma.conselho_concluido=True` mas ofertas pendentes**, o painel mostra **2 Pendentes** e nenhum Concluído (prova que o leitor não usa a coluna); com todas concluídas e a flag da turma `False`, mostra 2 Concluídos + botões "Reabrir"; turma sem oferta ativa não aparece e o aviso discreto aparece; links contêm `oferta_sel` das duas ofertas.

Pendências: `/informacoes` conta **ofertas** (2 ofertas, 1 concluída e uma turma sem oferta ⇒ `1`).

Métricas: unidade A (2 ofertas, 1 concluída + turma sem oferta) ⇒ `(1, 2)`; unidade B (1 oferta) ⇒ `(0, 1)`; global ⇒ `(1, 3)`.

Alternar: POST por oferta reflete no painel (1 concluída/1 pendente → 2 concluídas).

Certificado: `Turma.conselho_concluido=True` com oferta pendente ⇒ ícone `Pendente`; concluída a oferta ⇒ `Concluído` (prova a troca do L577 sem tocar no `ConselhoClasse`).

Isolamento: `alternar-conselho` de outra unidade → **403**; leitura com contexto da unidade B não mostra ofertas da A e `/informacoes` conta só a B; admin em Visão Global (sem unidade) → **403** no alternar. (As leituras **filtram** por unidade em vez de 403 — comportamento herdado dos demais leitores; só a escrita recusa.)

Testes existentes: nenhum cobre `/conselho`, `/informacoes`, relatório geral ou certificado ⇒ **nada precisou ser ajustado**.

### Suíte completa

```
337 passed, 74 warnings in 52.13s
```

`ruff`: novo arquivo de teste limpo (`All checks passed`); `app/services/turma_curso.py` com apenas os 2 E712 pré-existentes (`_alunos_da_oferta`), e os demais arquivos com os achados legados de sempre (sem achado novo introduzido).

---

## 6. Decisões tomadas sozinho

1. **View-model de dict** (`ofertas_do_painel_conselho`) em vez de tuplas/objetos ad hoc: deixa o template simples e permite testar a agregação sem HTTP.
2. **Filtros programa/turno continuam na TURMA** (não na oferta): a lista de programas do dropdown é derivada de `Turma.programa` (projeção da oferta principal), então filtrar pela oferta mudaria a semântica do filtro sem pedido.
3. **Filtro de professor por perfil aceita oferta OU turma** para não sumir ofertas onde o professor está só na oferta (turma professor legado continua valendo).
4. **Botão de alternar entrou no painel** — a rota existia sem nenhum chamador; o enunciado pede o botão por oferta, e o painel por oferta é o lugar natural (sem tocar `turmas/detalhe.html` de novo).
5. **Chaves do dict de métricas preservadas** (`turmas_concluidas`/`total_turmas`) para não quebrar templates/consumidores; só o rótulo visível mudou para "ofertas".
6. **Import local** de `app.services.turma_curso` dentro de `calcular_metricas_conselho` para blindar contra o ciclo `app.services → app.utils` já visto antes no projeto.
7. **Certificado usa o derivado por turma** (uma linha por turma/curso legado no documento) — a granularidade por oferta do certificado é D5.4/D5.5; aqui só se trocou a fonte do flag, como mandado.
8. **Remoção do import `PerguntaConselho`** em `turmas.py` como consequência inevitável da limpeza autorizada (senão vira import morto).

---

## 7. Pendências

- `Turma.conselho_concluido` e a ponte em `alternar_conselho` **permanecem** (ordem da etapa) — remover junto com a coluna na D5.5, depois que os leitores de resultado migrarem.
- D5.4: ficha do aluno, histórico, BI, relatórios de resultado e demais leitores de `ConselhoClasse`/resultado continuam legados.
- `ofertas_do_painel_conselho` ordena por `Turma.ordenacao`: NULL ordena antes no SQLite e depois no PostgreSQL — quando a ordenação passar a ser sempre preenchida, vale fixar `nullslast()`.
- A semente `_setup` da D5.2 cria a turma **sem** `periodo_letivo_id` (usa `periodo.id` antes do `flush`) — não afeta o que já existe; corrigir quando a semente for reutilizada por um teste que dependa de período.
- **Não publicar entre a D5.2 e a D5.4.**
