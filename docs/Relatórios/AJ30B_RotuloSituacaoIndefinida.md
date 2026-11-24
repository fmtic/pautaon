# AJ30-B — Rótulo da situação final não definida

**Data:** 24/11/2026 · **Branch:** `nova_feature` · **Migration:** nenhuma · **Head do código:** `b8c9d0e1f2a3` (inalterado)
**Postura:** mudança somente de rótulo; sem commit/push/merge; sem tocar em schema, rota, consulta, regra, permissão, `aplicar_deploy.ps1`, `empacotar_deploy.ps1` ou `deploy_pacotes/`.

---

## 1. Objetivo e decisão

Na AJ30, o ausente era exibido como `Não definido` na tela e no badge, mas como `—` na impressão, com duas constantes (`SITUACAO_FINAL_INDEFINIDA` e `SITUACAO_FINAL_INDEFINIDA_IMPRESSAO`). A AJ30-B **troca apenas o rótulo**: passa a ser `—` em tela, impressão e leitores, com **uma** fonte única.

| Antes (AJ30) | Depois (AJ30-B) |
|---|---|
| Primeira option `Não definido`, `value=""` | Primeira option `—`, `value=""` |
| Badge do resultado `Não definido` | Badge do resultado `—` |
| Impressão `—` (constante separada) | Impressão `—` (mesma constante da tela) |
| JS com literal `—` e comentário `Não definido` | JS recebe o rótulo da página por `data-rotulo-ausente` |

**Decisão:** `SITUACAO_FINAL_INDEFINIDA = '—'` em `app/models/enums.py` é a única fonte do rótulo. A constante de impressão foi removida; o badge reusa a mesma constante e o JS a recebe pelo DOM. Nenhum valor canônico, CHECK, migration, POST ou comportamento de autosave mudou.

---

## 2. Inventário (antes da troca)

Busca read-only em `app/` e `tests/`, excluindo `*.md`, com `git grep` sensível e insensível a maiúsculas. Classificação: **(a)** rótulo da situação final; **(b)** não é situação final.

### (a) Rótulo da situação final — trocado

| `arquivo:linha` (antes) | Natureza |
|---|---|
| `app/models/enums.py:98-99` | docstring do enum: ausente descrito como `Não definido` na tela / `—` na impressão |
| `app/models/enums.py:117` | comentário da option de ausência |
| `app/models/enums.py:138` | comentário dos badges |
| `app/models/enums.py:146` | literal do badge `''` |
| `app/models/enums.py:162-163` | duas constantes de ausência |
| `app/conselho.py:198` | docstring do normalizador |
| `app/conselho.py:1188-1189`, `1285-1286` | passagem de duas constantes ao template |
| `app/conselho.py:1477` | comentário da regra AJ20 no POST |
| `app/models/conselho.py:147` | docstring da coluna `situacao_final` |
| `app/static/js/conselho/autosave.js:110-112` | comentário e literal `—` em `textoImpressaoSituacao` |
| `app/static/js/conselho/conselho.js:171-178` | comentário e fallback `—` em `sincronizarSpans` |
| `app/templates/conselho/fechamento.html:177-189` | comentário, primeira option e span de impressão |
| `app/relatorios/conselho.py:283`, `:319` | uso da constante e contexto dos badges |
| `app/templates/relatorios/resultado_conselho.html:277-282` | comentário e badge de ausência |
| `tests/test_aj30_situacao_final.py:5,7,9,140,147,156,199,244,261` | docstring, nomes, asserts e comentários do rótulo antigo |
| `tests/test_conselho_ui.py:127` | comentário da primeira option |
| `tests/test_aj30_autosave_js.py:62` | harness node com `Não definido` como `rotulo` |
| `tests/test_aj20_conselho_lazy.py:212` | comentário da regra de vazio → `NULL` |

### (b) Não é situação final — preservado

| `arquivo:linha` | Natureza |
|---|---|
| `app/templates/conselho/fechamento.html:89,91` | `Horário não definido` (grade da oferta) |
| `app/templates/conselho/lancamento.html:60` | `Programa não definido` |
| `app/templates/conselho/painel.html:123,140` | `Programa não definido` / `Horário não definido` |
| `app/registros/turmas.py:1444` | regra de ocultar centro de custo alheio |
| `app/templates/turmas/detalhe.html:11,16,19` | curso principal e centro de custo |
| `app/templates/turmas/editar.html:96` | curso principal |
| `app/templates/turmas/listar.html:322` | centro de custo |
| `tests/snapshots/aj6b5_lista_pedagogico.txt:1`, `aj6b5_lista_secretaria.txt:1`, `aj6b6_admin_registros_ver_turma.txt:1` | colunas C. de Custos / Curso principal nos snapshots |

O teste `test_rotulo_antigo_so_existe_nos_casos_b` verifica os dois lados: os quatro arquivos (b) ainda contêm o texto antigo e nenhum outro `.py`/`.html`/`.js` de `app/` o contém.

---

## 3. Trocas ocorrência por ocorrência

- `app/models/enums.py`: constante única definida antes dos badges; `SITUACAO_FINAL_BADGES['']` passou a usar `SITUACAO_FINAL_INDEFINIDA`; `SITUACAO_FINAL_INDEFINIDA_IMPRESSAO` removida. Comentários/docstring passaram a falar em situação `não definida` (conceito) exibida como `—`.
- `app/conselho.py`: import e duas passagens de `situacao_indefinida_impressao` removidos; o template recebe só `situacao_indefinida`. Comentários alinhados ao novo rótulo.
- `app/templates/conselho/fechamento.html`: primeira option virou `{{ situacao_indefinida }}`; span de impressão usa a mesma variável; `data-rotulo-ausente` no select expõe o rótulo ao JS.
- `app/static/js/conselho/autosave.js`: `textoImpressaoSituacao(valor, rotulo, rotuloAusente)` não tem mais literal próprio; o valor ausente vem do argumento.
- `app/static/js/conselho/conselho.js`: `sincronizarSpans()` lê `sel.dataset.rotuloAusente` e repassa à função pura; fallback sem API usa o mesmo valor.
- `app/relatorios/conselho.py` + `app/templates/relatorios/resultado_conselho.html`: contexto passa `situacao_indefinida`; o badge de ausência recebe `title`/`aria-label` e continua com a classe `badge-situacao-nao-definido`.
- Testes: asserts de `("" , "Não definido")` e de `"Não definido" in html` passaram a afirmar `—` / igualdade tela-impressão; harness node passa o rótulo como terceiro argumento.

---

## 4. Preservações

| Item | Estado |
|---|---|
| `situacao_final` vazio / `None` → `NULL` | inalterado (`_normalizar_situacao_final`) |
| Primeira option `value=""` | inalterada |
| 6 valores canônicos e aliases de nome | inalterados |
| `ck_conselho_situacao_final` e migration `b8c9d0e1f2a3` | não tocados; head segue `b8c9d0e1f2a3` |
| POST de uma linha, rollback atômico, limpeza de nível | inalterados |
| Fila por linha, debounce 300 ms, retry, `beforeunload`, indicador | inalterados |
| Aviso `N aluno(s) sem situação final definida` | inalterado |
| Regra AJ20 (vazio não cria `ConselhoClasse`) | inalterada |
| Certificado, BI, ficha 360°, sumário de leitores | inalterados |
| Coluna Próximo Curso (`—`) e demais colunas | inalteradas |
| Casos (b) e snapshots | inalterados |

---

## 5. Acessibilidade (sem mudança visual)

- `aria-label="Situação final"` no `<select>` da coluna Situação Final.
- Primeira option com `title="Situação final não definida"` e `aria-label="Situação final não definida"`.
- Span de impressão e badge do resultado, **somente quando o valor está ausente**, recebem o mesmo `title`/`aria-label`; quando há valor canônico, o texto lido continua sendo o valor.
- O indicador de autosave (`aria-live="polite"`, `title` de erro) permanece como estava.
- Nenhuma classe CSS, cor, largura, ordem de colunas ou comportamento de impressão foi alterado.

---

## 6. Testes: antigo × novo × motivo

| Teste / asserção | Antes | Depois | Motivo |
|---|---|---|---|
| `test_select_abre_nao_definido_e_impressao_usa_traco` | tela `Não definido` × impressão `—` | `test_select_e_impressao_usam_o_mesmo_traco`: option e span `—` | acabar com a diferença tela/impressão |
| `SITUACAO_FINAL_BADGES[""][1]` | `Não definido` | `SITUACAO_FINAL_INDEFINIDA == "—"` | uma fonte única de rótulo |
| `test_resultado_conselho_mostra_nao_definido_e_novos_badges` | `"Não definido" in html` | badge `—` com `title`/`aria-label` | leitura consistente com a tela |
| `test_conselho_ui.py` | comentário `Não definido`; só `value=""` conferido | primeira option `—`, ausência do rótulo antigo, `aria-label`/`title` | cobrir o contrato visual e acessível |
| `test_aj30_autosave_js.py` | `textoImpressaoSituacao('', 'Não definido')` | `textoImpressaoSituacao('', '', '—')` | o JS não deve inventar rótulo |
| `test_aj20_conselho_lazy.py` | comentário `vazio = "Não definido" = NULL` | `vazio/"—" = NULL` | só alinhar a documentação do teste |
| Novo `test_rotulo_antigo_so_existe_nos_casos_b` | — | varre `app/` e limita o texto antigo aos casos (b) | impedir reintrodução do rótulo |

---

## 7. Verificação

- Direcionados: **40 passed** (`test_aj30_situacao_final.py`, `test_conselho_ui.py`, `test_aj20_conselho_lazy.py`, `test_aj30_autosave_js.py`) e **52 passed** (`test_aj30_migration.py`, `test_aj25_botoes_fechamento.py`, `test_conselho_oferta.py`, `test_aj26_resultado_conselho.py`, `test_a1_historico_status_ausente.py`, `test_aj29_nome_pdf_js.py`).
- Suíte node do autosave: executada por `tests/test_aj30_autosave_js.py` (`node -e` sobre `autosave.js`); node disponível, sem skip.
- Suíte completa (execução final): **`2005 passed, 1239 warnings in 1576.85s (0:26:16)`** (SQLite, Python 3.14). Os 1239 avisos são preexistentes (SQLAlchemy `Query.get()`, `datetime.utcnow()`, reflexão de índice expressivo etc.), não regressões da AJ30-B. O total subiu de 2004 para 2005 por causa do novo teste de varredura do rótulo antigo.
- `python -m compileall` nos arquivos Python alterados: sem erros.
- `git diff --check`: sem erros de whitespace.
- `flask db heads`: `b8c9d0e1f2a3` (único; nenhuma migration nova).

---

## 8. Entrega

`git diff --stat` e `git status --short` ao final; nenhum commit, push ou merge. Arquivos de deploy preexistentes não foram tocados.
