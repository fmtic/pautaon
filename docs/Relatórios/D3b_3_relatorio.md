# ETAPA D3b.3 — Definição única de "enturmado"

**Status:** concluída. Suíte completa verde (`382 passed, 0 falhas`, meta ≥372).
Nenhum commit feito. Nenhum número divergiu fora dos casos DECIDIDOS (nenhum
PARE foi necessário).

Fontes: `docs/D3b_0_desenho.md` (Passo 2.1-2.2, 2.6, D3b.3), MER §8.3, §8.10,
§12.13.

**Definição única (decisão do responsável):**
`ENTURMADO = Aluno.ativo E Inscricao.ativo em Turma ativa E oferta EFETIVA
(ativa, ou inativa em período já encerrado — regra do M4)`.
Os números das telas que usavam outras definições mudaram — é a correção; a
tabela antes/depois está na §4.

Fora do escopo (preservado intocado): regras de status (Novo/Renovado/…),
indicadores do BI (D3b.4), coorte por turno (D3b.7).

---

## 1. Leitura (consumidores mapeados antes de alterar)

As 5 definições conviventes (Passo 2.2 do desenho, "na verdade 5"):

| # | Arquivo : linha | Definição usada | Chamadores identificados |
|---|---|---|---|
| 1 | `app/registros/alunos.py:380` (`total_enturmados`) | `Aluno.ativo` + `Aluno.turmas.any(Turma.ativo)` — QUALQUER linha de inscrição (até inativa) em turma ativa; ignora inscrição ativa e oferta | rota `registros.gerenciar_alunos` (`GET /alunos`) → template `app/templates/alunos/gerenciar.html:114` (card "Enturmados") |
| 2 | `app/models/academico.py:67-82` (`PeriodoLetivo.alunos_enturmados()`) | `join(Aluno.turmas)` + `Turma.periodo_letivo_id` + `distinct` — sem `Aluno.ativo`, `Inscricao.ativo`, `Turma.ativo` nem oferta | template `app/templates/periodos/lista.html:74` (coluna da lista de períodos) e `scripts/smoke_models.py:467` |
| 3 | `app/relatorios/bi_filtros.py:17` (`cond_oferta_efetiva`) e `:59` (`cond_inscricao_enturmada`) | predicado canônico (inscrição ativa + turma ativa + oferta efetiva/M4) | `bi_alunos.py:24,420,507,597,1573`; testes `test_desativar_oferta.py:41,197` e `test_bi_turma_desativada.py:38,69` |
| 4 | `app/services/aluno_status.py:145-174` (`_cond_oferta_efetiva` — espelho do BI) + `:243` (`vinculo_em_data` em `status_alunos`) | mesmo predicado #3, duplicado de propósito | internos a `status_alunos` (`:241-244`), consumida por `status_alunos_para_bi`, ficha (`ficha_aluno.py`), painel (`coorte.py`/`periodo.py`) e BI (`bi_alunos.py:2738+`) |
| 5 | `app/registros/core.py:167-176` (`total_alunos` do `/professor/painel`) | `Inscricao.ativo` + `Aluno.ativo` + `distinct` — sem oferta efetiva | rota `registros.painel_professor` → template `app/templates/dashboard/professor.html:39` ("Meus Alunos") |
| + | `app/relatorios/shared.py:70-72` (filtro de período em `aplicar_filtros_alunos`) | join por `Aluno.turmas` sem nenhum `ativo` (duplicava linhas com 2+ inscrições) | `app/relatorios/alunos.py:127` (listagem `/relatorios/alunos`) e `:197` (exportação Excel) |

**Ciclo de importação que gerou o espelho (#4):** `app/relatorios/__init__.py:20-22`
importa os blueprints (`bi_routes` → `bi_alunos`), e `bi_alunos.py:20-24` importa
`app.services.aluno_status`. Se `aluno_status` importasse
`app.relatorios.bi_filtros` no topo, o pacote `app.relatorios` (já em
inicialização por `bi_alunos`) recarregaria `aluno_status` em estado parcial →
`ImportError`. Por isso o predicado foi duplicado (`MER §12.13`). A solução é o
módulo neutro `app/services/enturmado.py`, que só depende de `app.models` — o
espelho foi REMOVIDO e `bi_filtros` reexporta os nomes originais (nenhum
chamador do BI mudou).

## 2. Módulo novo — `app/services/enturmado.py`

- `cond_oferta_efetiva()` e `cond_inscricao_enturmada()` — **movidos** de
  `bi_filtros.py` com comportamento idêntico, corpo a corpo, incluindo os
  `correlate_except(TurmaCurso)`/`correlate_except(Turma)` (lição da
  anti-auto-correlação) e as docstrings originais.
- `cond_aluno_enturmado(periodo_letivo_id=None)` — condição sobre `Aluno`:
  `Aluno.ativo` **E** `EXISTS` de inscrição enturmada (regra única); EXISTS,
  não JOIN: nunca duplica o aluno.
- `ids_alunos_enturmados(unidade_id=None, periodo_letivo_id=None) -> set[int]`
  — conjunto distinto de alunos, **uma** consulta; `unidade_id` é o escopo dos
  chamadores que já filtram pela unidade da sessão.
- `contar_alunos_enturmados(...)` — conveniência (len do conjunto).

`bi_filtros.py` → `from app.services.enturmado import cond_inscricao_enturmada,
cond_oferta_efetiva` (reexporta; identidad confirmed em teste).
`aluno_status.py` → importa o predicado neutro; **`_cond_oferta_efetiva`
removido**; `vinculo_em_data = and_(Inscricao.ativo, cond_oferta_efetiva())` —
regras de status intocadas (caracterização do `status_alunos` passou igual, e
`tests/test_aluno_status.py` continua verde).

## 3. Consumidores migrados (Passo 4)

| Consumidor | Migração |
|---|---|
| `registros/alunos.py:380` | `enturm_q.filter(cond_aluno_enturmado()).count()` — escopo de unidade da sessão preservado (`filter_by(unidade_id)` já existia) |
| `models/academico.py` `PeriodoLetivo.alunos_enturmados()` | delega `contar_alunos_enturmados(periodo_letivo_id=self.id)`; assinatura e retorno (`int`) idênticos; import lazy (padrão dos modelos) |
| `registros/core.py:167` (`/professor/painel`) | `Aluno.join(Inscricao)` + `cond_inscricao_enturmada()` + `Aluno.ativo` + `with_entities(Aluno.id).distinct().count()` — remove o `.distinct(Aluno.id)` (DISTINCT ON só PostgreSQL, deprecation em SQLite) e acrescenta a oferta efetiva que faltava |
| `relatorios/shared.py:72` | join por `Aluno.turmas` → `cond_aluno_enturmado(periodo_letivo_id=...)` (EXISTS) — filtro pela definição única sem duplicar linhas |

Templates dos leitores: **nenhum alterado** (os cards existentes já exibiam os
números vindos das rotas).

## 4. Números antes/depois (cenário do teste, código real)

| Leitor | Antes | Depois | Causa da diferença |
|---|---|---|---|
| Card "Enturmados" `/alunos` | 6 | **4** | Beto sai (inscrição **inativa** em turma ativa contava — `Aluno.turmas.any` não olhava `Inscricao.ativo`); Fanny sai (oferta **inativa em período em andamento** não é efetiva). Gaby fica (M4). |
| `PeriodoLetivo.alunos_enturmados()` P1 | 7 | **3** | Saem Beto (inscrição inativa), Caio (sem `Aluno.ativo` — decisão da definição), Enzo (sem `Turma.ativo`), Fanny (sem oferta efetiva). A property era a definição mais frouxa. |
| `PeriodoLetivo.alunos_enturmados()` P2 / P3 | 2 / 1 | **2 / 1 (inalterado)** | Nenhuma linha espúria no P2/P3; Gaby entra pela regra M4 em ambos. |
| "Meus Alunos" `/professor/painel` | 5 | **4** | Fanny sai — a definição já tinha inscrição/turma/`Aluno.ativo`, faltava só a **oferta efetiva** (era a única divergência dela). |
| Filtro de período `relatorios/shared` (listagem/exportação de alunos) | 6 linhas (Henry aparecia **duplicado** por ter 2 inscrições) | **3 ids únicos** | Beto/Enzo/Fanny saem (definição); a troca join→EXISTS elimina a duplicação de aluno com 2+ vínculos. |
| Status canônico `status_alunos` (P1) | Ana/Henry Novo, Iris Retornante, Beto/Fanny Desenturmado, Gaby Não Renovado, Enzo Outros; enturmados {Ana, Henry, Iris} | **idêntico** | Remoção do espelho é refactor puro — caracterização confirmou. |
| BI ALU-008 com período (P1 / P2) | 4 / 2 | **4 / 2 (inalterado)** | BI não foi tocado (D3b.4). Divergência remanescente: ALU-008 não filtra `Aluno.ativo` (conta Caio) — ver pendências. |

Convergência demonstrada em teste: card = painel = service = property =
`cond_inscricao_enturmada + Aluno.ativo` = `{Ana, Gaby, Henry, Iris}` (unidade)
e shared = property(P1) = status-enturmados = `{Ana, Henry, Iris}` — **uma
definição, um conjunto**.

## 5. Testes — `tests/test_enturmado.py` (novo, 10 testes)

**Parte 1 — caracterização (verde com o CÓDIGO ATUAL antes do Passo 3, 6
testes):** cenário `_base` com unidade A (períodos P1 em andamento / P2
encerrado / unidade B com P3), turmas Alfa (2 ofertas ativas), Beta (turma
desativada), Delta (oferta inativa em andamento), Gema (oferta inativa em
período encerrado), Bela (un B); alunos Ana (enturmada), Beto (inscrição
inativa), Caio (`Aluno.ativo=False` com inscrição ativa), Enzo (turma
desativada), Fanny (oferta inativa em andamento), Gaby (M4), Henry (2 ofertas
da mesma turma), Iris (2 turmas), Jack (unidade B). Fixa card `/alunos`
(6=6→4), property P1/P2/P3 (7/2/1→3/2/1), painel (5→4), shared (6→3),
ALU-008 (4/2) e o status canônico completo.

**Parte 2 — equivalência (Passo 5, 4 testes):**
- `test_bi_filtros_reexporta_os_mesmos_predicados` — identidade dos objetos
  reexportados (nenhum chamador do BI muda).
- `test_consumidores_migrados_equivalem_ao_servico` — TODOS os consumidores
  migrados + BI (ALU-008 e o predicado `cond_inscricao_enturmada`) fecham com
  o MESMO conjunto (a diferença numérica do ALU-008 é exatamente Caio,
  população cadastral — intocada por escopo).
- `test_ids_alunos_enturmados_uma_sozinha_consulta` — `before_cursor_execute`:
  **1** consulta, sem N+1.
- `test_import_modulo_neutro_sem_ciclo` — `app.services.enturmado` importado em
  subprocess limpo não puxa `app.relatorios` nem `app.registros`.

Nenhum outro teste precisou de ajuste (a suíte anterior passou intacta:
372 → 382 = 372 + 10 novos).

## 6. Decisões

- Predicados movidos **corpo a corpo** (docstrings incluídas) — zero mudança
  de comportamento; `bi_filtros` vira façade de reexport.
- `cond_aluno_enturmado` implementado como **EXISTS** (não JOIN): é o que
  permite migrar o filtro de período do `shared.py` sem duplicar alunos e sem
  tocar nos templates/exportação.
- No `/professor/painel`, mantive a lista de turmas visíveis como escopo e
  troquei o `distinct(Aluno.id)` (DISTINCT ON, só PostgreSQL — deprecado em
  SQLite) por `with_entities(Aluno.id).distinct().count()`.
- O escopo por unidade foi preservado onde já existia (card e painel filtram
  pela unidade da sessão; a property do período continua restrita só pelo
  período — como antes, o período já é de uma unidade).
- `Aluno.ativo` na definição é exigência do MER §8.3 ("Alunos com
  `Aluno.ativo=False` ficam fora das categorias de enturmação").

## 7. Pendências

- **D3b.4:** ALU-008 (e demais indicadores de contagem) ainda não filtram
  `Aluno.ativo` — com a D3b.3 o predicado canônico está acessível pelo módulo
  neutro, falta aplicar nos indicadores do BI.
- Coorte por turno (`_ids_coorte_turno`, `Turma.turno`) — D3b.7.
- Dica de limpeza futura: `docs/D3b_0_desenho.md` §1.7 classificava
  `core.py:167` como "opcional, já correto"; na prática faltava a oferta
  efetiva (migrado e corrigido aqui).
- Avisos `LegacyAPIWarning`/`utcnow` pré-existentes — fora do escopo.

## 8. Resumo do pytest

```
382 passed, 141 warnings in 111.17s (0:01:51)
```

Escopos alterados (dentro do autorizado): `app/services/enturmado.py` (novo),
`app/relatorios/bi_filtros.py` (mover + reexportar),
`app/services/aluno_status.py` (predicado neutro, espelho removido),
`app/models/academico.py` (apenas `alunos_enturmados`),
`app/registros/alunos.py` e `app/registros/core.py` (pontos do Passo 1(a)),
`app/relatorios/shared.py` (filtro de período) e `tests/`. Sem commit.
