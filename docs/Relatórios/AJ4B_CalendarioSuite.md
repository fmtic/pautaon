# AJ4-B — Calendário da suíte: datas determinísticas

**Data:** 01/11/2026 · **Branch:** `nova_feature` · **Base:** `f0ce610` (suíte com 14 falhas de calendário: `test_f1_autor_lancamento` ×10, `test_turma_curso_fase4_dash` ×3, `test_v3a_datas_lancadas` ×1)

Objetivo: tornar a suíte verde e determinística, provando antes se a causa era mesmo o relógio do sistema e se há bug real de runtime por trás. Regras mantidas: sem migration, sem escrita em banco real, sem push; reversões só em `git worktree`; relatório em arquivo NOVO (relatórios AJ3/AJ4 intocados).

## E1 — Causa provada (worktree, somente leitura)

Worktree destacado em `f0ce610` (`.tmp/aj4b_wt`), plugin de pytest com **freezegun** (instalado via `pip --target .tmp/aj4b_pkgs`, sem tocar no `.venv`; o congelamento precisa ocorrer em `pytest_configure` e depois de um `import pandas` prévio — congelar durante o import do pandas estoura a pilha no Windows). Os módulos de teste calculam `HOJE` em nível de módulo, antes de qualquer fixture; o plugin congela o processo inteiro antes da coleta.

| "Hoje" do sistema | Resultado nos 3 arquivos |
|---|---|
| data real (dom 01/11) | **14 failed, 15 passed** |
| congelado 31/10 (sáb) | **29 passed** |
| congelado 01/11 (dom) | **14 failed, 15 passed** |
| congelado 02/11 (seg) | **29 passed** |

Evidências: `.tmp/aj4b_causa_real.txt`, `.tmp/aj4b_causa_20261031.txt`, `.tmp/aj4b_causa_20261101.txt`, `.tmp/aj4b_causa_20261102.txt`. Causa confirmada — **não é regressão**: as 14 falhas são função exclusiva do dia da semana/da semana do mês do relógio real. Os três mecanismos:

- **f1 (×10):** a semente ancora o período em `hoje.replace(day=1)` e a grade é seg–sex; quando o dia 1 cai no fim de semana e "hoje" é esse dia, a janela `[dia 1 .. hoje]` não tem nenhum dia de aula → `carregar_contexto_turma(...)["datas"]` é `[]` → `IndexError` na **linha 116 do teste**.
- **fase4_dash (×3):** `DIA_HOJE = _DIAS[HOJE.weekday()]`; domingo não é dia de aula (a grade do domínio aceita 0–5 — `itens_grade` descarta domingo) → oferta semeada "sem grade" → 0 pendências ≠ 1/2 esperadas.
- **v3a (×1):** `test_z_zero_quando_tudo_lancado` usa janela `HOJE ± 3` com grades "Segunda, Quarta"/"Terça, Quinta"; num domingo a janela não tem segunda nem quarta ≤ hoje → a própria asserção-guarda do teste falha ("a semente precisa de ao menos uma aula até hoje").

## E2 — Runtime: `datas == []` derruba alguma rota?

**Não.** Todos os consumidores de `carregar_contexto_turma(...)["datas"]` tratam a lista vazia:

- `POST /frequencia` (`app/registros/core.py:271`): `data_post not in contexto.get('datas', [])` → flash + redirect, sem índice;
- `GET /frequencia` (`app/registros/core.py:483`): cai em `datas_calendario[-1] if datas_calendario else None`;
- pauta de impressão (`app/registros/turmas.py:2962`): `freq_filtros = [...] if datas_date else None`;
- painel pedagógico (`app/relatorios/painel_pedagogico/rota.py:206`): `candidatas[0] if candidatas else None`;
- template `frequencia/lancar.html`: bloco `{% if datas %}`.

O `IndexError` existia **só no código de teste**. Sem bug de runtime → **nenhum commit `fix(...)`**.

## E3 — Testes determinísticos (`hoje_fixo`)

- **Fixture único** `hoje_fixo` em `tests/conftest.py`: congela o relógio do app patcheando apenas os dois globais `datetime` por onde o "hoje" entra — `app.utils.timezone` (fonte de todo `get_local_now`, inclusive dos alias já importados, porque o corpo consulta o global na chamada) e `app.utils.logica` (corte `min(fim, datetime.now())` de `gerar_datas`). Revertido pelo `monkeypatch` ao fim de cada teste; `app/**` intocado.
- **Dia de referência** = `hoje_ref()` (`tests/_helpers.py`): env `AJ4B_HOJE` (ISO) com default fixo **2026-10-29 (quinta)**. `dia_de_aula_ate(ref, permite_sabado=)` devolve o último dia de aula ≤ ref — domingo nunca ancora semente.
- **Os 3 arquivos** passaram `pytestmark = usefixtures("hoje_fixo")` e trocaram o "hoje" do sistema pelo par ref/aula: f1 (`_cenario` ancora em `dia_de_aula_ate(hoje_ref())`), fase4 (`HOJE`/`DIA_HOJE` idem com `permite_sabado=True`; `DIA_OUTRO` pula domingo), v3a (`HOJE = dia_de_aula_ate(hoje_ref())`).

**Prova** (evidências `.tmp/aj4b_prova_*.txt`): os 3 arquivos = **29 passed** nas quatro condições — data real do sistema (dom 01/11) **e** `AJ4B_HOJE` em 31/10, 01/11, 02/11.

## E4 — Ajuste do AJ4-A: literais não emitidos à parte

`tests/test_aj4_logs_drift.py` separa `ROTULOS_SEM_LINHA` (7 — emitidos por helper: `Acesso via Google`, `Cadastro Período Letivo`, `Desbloqueio de login`, `Gestão de Unidade`, `Reativação de Turma`, `Trocar Professor da Oferta`, `Vínculo Google`) de `LITERAIS_NAO_EMITIDOS` (3 — `DESENTURMADO`, `Excluir aluno`, `TRANSFERENCIA`, que só vivem como literal solto/motivo de desativação/docstring). A **asserção 3 do primeiro grupo exige emissor via helper** (rótulo resolvido no AST, não "qualquer string"); o segundo grupo só passa pela classificação congelada (asserção 2). Universo `CONGELADOS = CENSO ∪ SEM_LINHA ∪ LITERAIS` = 40 inalterado; teste fica com **54** (−3 parâmetros da asserção 3).

Sondagens de reversão reaplicadas em worktree (evidências `.tmp/aj4b_reversao_{base,a,b,c}.txt`; base 54 passed):

| Sondagem | Falhas esperadas | Resultado |
|---|---|---|
| (a) rótulo fictício `Drift Fake AJ4-B` num `register_security_log` | asserções 1 e 4 | 2 failed ✓ |
| (b) emissor `Reativação de Turma` trocado por outro congelado | asserção 3 + sanidade do varredor | 2 failed ✓ |
| (c) `git checkout 1e39e23~1 -- app/auth.py` | só `test_classificacao_congelada[Exclusão de Turma]` | 1 failed ✓ |

A sonda (b) mudou de alvo: `TRANSFERENCIA` agora é literal não emitido (sem asserção 3 por construção) — o equivalente fiel é sumir com o **emissor** de um rótulo do grupo 1, que a asserção 3 endurecida pega.

## Verificação final

- Suíte completa: **1362 passed, 0 failed** (1308 da base AJ3 + 54 do drift — o "1365" do prompt desconta os 3 parâmetros removidos em E4). Evidência: `.tmp/aj4b_suite_final.txt`.
- `ruff check --select F821,F811,F841` nos 6 arquivos de teste: limpo.
- `git worktree list`: só o repositório principal; árvore limpa; **sem push**.

## Incidente de guarda (registrado por honestidade)

A sonda (b) foi aplicada uma vez com cwd errado e mutou `app/registros/turmas.py` **na árvore principal** (troca de uma string literal). Detectado no `git status` seguinte e revertido com `git restore app/registros/turmas.py` antes de qualquer commit; a árvore principal nunca levou essa mutação para o histórico. Refeita no worktree com caminho absoluto.

## Commits

| Hash | Conteúdo |
|---|---|
| `85bebdc` `test(aj4b): datas determinísticas` | conftest + `_helpers` + os 3 arquivos de teste |
| `c3fa523` `test(aj4): separa literais não emitidos` | `tests/test_aj4_logs_drift.py` |
| (este) `docs(aj4b): relatório` | este arquivo, backlog, MER §7.29 |

## Pendências

Nenhuma criada por este trabalho. A pendência "AJ4-B — flakiness de calendário" registrada no AJ4-A está **encerrada** por este entregável. Pendências antigas seguem valendo (Ajuste 4, Central de BI, cadastro de aluno).

## Procedimento (dia que quebrar de novo)

1. Rode os 3 arquivos com `AJ4B_HOJE` fixo em outra data — se passar, a semente está ancorada no ref, não no sistema.
2. Precisa de um "hoje" real para algum teste novo? Use o fixture `hoje_fixo` + `hoje_ref()`/`dia_de_aula_ate()`; nunca `date.today()`/`get_local_now()` em nível de módulo.
3. Rótulo/dinâmico novo de `log_acao`? Vale o procedimento do AJ4-A (MER §7.29): classificação humana em `CATEGORIA_ESPERADA`; emissor no grupo certo (`ROTULOS_SEM_LINHA` se via helper, `LITERAIS_NAO_EMITIDOS` se só literatura).
