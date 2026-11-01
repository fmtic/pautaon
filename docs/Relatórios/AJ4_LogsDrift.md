# AJ4-A - Teste de drift dos rótulos de `log_acao`

Data: 01/11/2026 - Branch: nova_feature - Sem push

Escopo: o filtro de auditoria (`categoria_acao` / `_CATEGORIAS_ACAO` em `app/auth.py`, AJ1/AJ3-E2) classifica a ação pelo prefixo do texto; o `fix(1e39e23)` nasceu exatamente disso — `Exclusão de Turma` caiu em `outras` em silêncio. Este trabalho fecha a porta com `tests/test_aj4_logs_drift.py`: varre `app/**.py` com `ast` e falha quando um rótulo novo aparece sem classificação consciente, quando um rótulo congelado some do código, ou quando a categoria decidida por humano deixa de bater. Nenhuma migration, nenhum comportamento de app alterado (nenhum `fix(...)` foi necessário — nenhum defeito novo foi exposto), nenhuma escrita em banco real (`pautaon` e `pautaon_ensaio` só tiveram os `SELECT` do censo original do AJ3; o teste nem lê Postgres), nenhum e-mail/IP/hash/CPF em teste ou relatório.

## E0 - Linha de base

- Branch `nova_feature`, HEAD inicial `ef98f7f`; `git status --porcelain` limpo de arquivos de app (só prompts untracked em `docs/prompts/`).
- Suíte de referência: **1308 passed** (AJ3-E6, `.tmp/aj3_suite_final.txt`).
- Convenções seguidas desde já (regra de guarda do AJ3): prova de reversão **exclusivamente via `git worktree`**; `git status --porcelain` antes de qualquer `git checkout <rev> -- arquivo`.

## E1 - Descoberta dos emissores (somente leitura)

Comando semente: `grep -rnE "LogAcao\(|def register_[a-z_]*log|def registrar_[a-z_]*" app --include=*.py`, seguido da leitura de cada gravador. Três famílias recebem o rótulo:

| Helper | Assinatura / posição do rótulo | Definição | Chamadas no app |
|---|---|---|---|
| `register_security_log` | `(action, details="")` — 1º posicional (ou keyword `action`) | `app/services/auth_service.py:79` | **19 literais**: `auth.py` ×14, `registros/turmas.py` ×2, `registros/periodos.py` ×1, `informacao_padrao.py` ×1, `services/sessao.py` ×1; + repasse interno `acao=action` (linha 87) |
| `LogAcao(acao=…)` | keyword `acao` | modelo `app/models/auditoria.py` | **3 literais** (`Desbloqueio de login` ×2 em `auth.py`, `Editar aluno` em `registros/alunos.py`), **2 constantes de módulo** (`ACAO_TROCA_PROFESSOR_OFERTA`, `ACAO_EXCLUSAO_LOGICA_TURMA` em `services/turma_curso.py`), **1 dinâmica** (`acao=acao` do listener `before_flush`) |
| `_gravar_log_background` | keyword `acao` | `app/utils/disparo_email.py:8` | **2 literais** (`Disparo de E-mail`, `Erro E-mail` nas linhas 34/44) + repasse `acao=acao` (linha 15) |

Classificação dos rótulos encontrados: **22 resolvidos** (literais + constantes), **3 dinâmicos** não resolvidos por design, 14 rótulos do censo (`Criar X`/`Alterar X`) que só existem via listener, e `Manutenção` — presente no banco, **sem emissor no código** (rótulo legado).

Os dois `registrar_*` de `relatorios/painel_pedagogico/periodo.py` e `registrar_atendimento` de `registros/atendimentos.py` aparecem no grep por nome mas **não gravam `LogAcao`** — ficam fora do varredor.

## E2 - O teste (`tests/test_aj4_logs_drift.py`)

Resultado: **`57 passed in 5.69s`**. Varredura 100% `ast` (nunca regex) dos 102 `.py` de `app/`, ignorando `__pycache__`; uma passada por processo (`lru_cache`); nada de Postgres.

Listas congeladas dentro do teste:

- `CENSO_REAL` — os **30** rótulos da união `pautaon ∪ pautaon_ensaio` (tabela E2 do relatório AJ3, censo de 31/10/2026, `.tmp/acoes_reais.json`).
- `ROTULOS_SEM_LINHA` — os **10** rótulos emitidos sem linha nos bancos (Acesso via Google, Cadastro Período Letivo, DESENTURMADO, Desbloqueio de login, Excluir aluno, Gestão de Unidade, Reativação de Turma, Trocar Professor da Oferta, TRANSFERENCIA, Vínculo Google).
- `CATEGORIA_ESPERADA` — dict rótulo → categoria para os **40**, com categoria **decidida por humano** (a tabela E2 congelada, já com o `1e39e23`): é o que pega reclassificação silenciosa do dicionário.
- `SO_NO_BANCO` — `{Manutenção}`: conferido apenas na asserção 2; se ganhar emissor, o teste exige migração consciente para `ROTULOS_SEM_LINHA`.
- `ROTULOS_DINAMICOS_CONHECIDOS` — os 3 repasses com `arquivo:linha` e padrão: `auditoria_listener.py:70` (f-strings `Criar <Modelo>`/`Alterar <Modelo>`), `auth_service.py:87` e `disparo_email.py:15` (parâmetros repassados; os literais dos chamadores já caem na asserção 1).

Asserções (as 5 do prompt + 3 de consistência):

1. **`test_rotulo_novo_do_codigo_falha`** — todo rótulo literal/constante dos helpers está em `CENSO_REAL | ROTULOS_SEM_LINHA`; novo → falha com "classifique em CATEGORIA_ESPERADA". Parte dinâmica: `test_dinamico_novo_fora_da_lista_falha` confere os dinâmicos **nos dois lados** (novo fora da lista falha; congelado que sumiu de linha também falha).
2. **`test_classificacao_congelada`** (40 parâmetros) — `categoria_acao(rotulo) == CATEGORIA_ESPERADA[rotulo]` para todos os congelados, incluindo `SO_NO_BANCO`.
3. **`test_rotulo_sem_linha_ainda_existe_no_codigo`** (10 parâmetros) — o rótulo congelado ainda aparece no código (resolvido como rótulo de helper **ou** string literal em qualquer ponto de `app/**.py` — é o caso de `DESENTURMADO`/`TRANSFERENCIA`, motivos de desativação, e `Excluir aluno`, exemplo da docstring do modelo; herdado assim do AJ3-E2). Sumiu → falha pedindo remoção consciente.
4. **`test_outras_exige_decisao_explicita`** — `CATEGORIA_ESPERADA` cobre o universo congelado inteiro, e nenhum rótulo recém-emitido entra sem classificação explícita: **nada é `outras` por omissão**.
5. **`test_scanner_varre_o_app_inteiro`** — sanidade do varredor: ≥ 90 arquivos e os 22 rótulos medidos hoje; se o scanner quebrar, o teste falha aqui em vez de passar vazio.
- **`test_so_no_banco_nao_ganhou_emissor_sem_querer`** e **`test_somente_criar_alterar_sao_do_listener`** / **`test_listas_congeladas_sem_sobreposicao`** — invariantes das próprias listas (anti-ioiô).

## E3 - Prova de reversão (em `git worktree`, como manda a regra do AJ3)

Método: `git worktree add .tmp/aj4_wt --detach` em HEAD `ef98f7f`, cópia só do arquivo de teste, mutações **dentro do worktree**; base no worktree: **`57 passed`** (`.tmp/aj4_reversao_base.txt`). Antes da reversão (c), `git log 1e39e23..HEAD -- app/auth.py` confirmou que o arquivo não foi tocado depois do fix — reversão limpa.

| Sondagem | Resultado |
|---|---|
| (a) `register_security_log("Drift Fake AJ4-A", …)` em módulo novo | **2 falham, 55 passam** — asserção 1 (rótulo novo) + asserção 4 (`outras` por omissão) (`.tmp/aj4_reversao_a.txt`) |
| (b) trocar a única string `"TRANSFERENCIA"` do código (`alunos.py:1218`) | **falha exatamente 1** — a asserção 3 do parâmetro `TRANSFERENCIA` (`.tmp/aj4_reversao_b.txt`) |
| (c) `git checkout 1e39e23^ -- app/auth.py` (revirar o fix) | **falha exatamente 1** — `test_classificacao_congelada[Exclusão de Turma]`: `categoria_acao` volta a dizer `outras` contra a decisão humana `exclusao` (`.tmp/aj4_reversao_c.txt`) |

Escolhas de sondagem para não contaminar: (b) usou `TRANSFERENCIA` porque não é argumento de helper — mexer nele derruba **só** a asserção 3; os worktrees foram removidos ao final (`git worktree list` só com o repo principal) e a árvore de trabalho nunca foi tocada.

## E4 - Verificação

- `pytest tests/test_aj4_logs_drift.py -q`: **57 passed** • `pytest tests/test_aj1_logs_filtro.py -q`: **58 passed** (sem regressão no censo congelado).
- `ruff check --select F821,F811,F841 app tests scripts migrations`: **All checks passed!**
- Suíte completa, uma corrida (`.tmp/aj4_suite_final.txt`): **1365 coletados (1308 + 57), 1351 passed, 14 failed**.
- **Achei 14 falhas que não são deste trabalho**: `test_f1_autor_lancamento` (×10), `test_turma_curso_fase4_dash` (×3) e `test_v3a_datas_lancadas` (×1) falham **também no HEAD limpo `ef98f7f` sem nenhuma mudança minha** — reproduzido em worktree separado (`.tmp/aj4_falhas_head.txt`, as mesmas 14). Sintoma: `IndexError` em `carregar_contexto_turma(...)["datas"][0]`; `gerar_datas` (`app/utils/logica.py`) deriva os dias da grade da oferta e **corta em `hoje`** — sensibilidade de calendário na virada 31/10 → 01/11 (domingo/início de mês). Por regra (defeito exposto → parar e reportar; correção em `fix(...)` próprio à parte), **nada foi corrigido aqui**; registrado como pendência **AJ4-B** no backlog.
- Após os commits, nova corrida do arquivo AJ4 no HEAD final: **57 passed**.

## Alterações externas

`git status` durante todo o trabalho mostrou apenas arquivos untracked de `docs/prompts/` (prompts do usuário) — nenhuma edição externa em arquivo de app; a guarda Nextcloud não precisou intervir. Nenhum push foi feito por este trabalho.

## Commits do AJ4-A

| Hash | Tipo | Conteúdo |
|---|---|---|
| `9482c95` | test(aj4) | `tests/test_aj4_logs_drift.py` (57) com listas congeladas e prova de reversão |
| `468c4d6` | docs(aj3) | Aritmética da E6, guarda Nextcloud no relatório AJ3; MER §7.29 e backlog (AJ4-A) |
| (este) | docs(aj4) | Este relatório |

## Pendências

- **AJ4-B (nova)** — flakiness de calendário nos três arquivos citados (`gerar_datas`/janelas de "hoje"); exigir semente com data fixa (congelar o `datetime.now` ou parâmetro `hoje`), sem mudar comportamento de runtime.
- Ajuste 4 — Resumo/primeira vista: cards Painel do Conselho, Desempenho por Professor, Frequência por Turma.
- Central de BI: página explicando cada indicador e como é calculado (auditoria e guia de uso), acessível a quem entra na Central.
- Cadastro de aluno: aproveitar melhor a área do formulário de novo aluno (mudança crítica, todo o resto depende dessa entrada) e permitir **excluir** documento entregue, não só fazer upload.

## Procedimento (o ponto do teste)

**Rótulo novo de log → atualizar `CATEGORIA_ESPERADA`** (decisão humana: login / criacao / edicao / exclusao / outras) e a lista de congelados (`CENSO_REAL` ou `ROTULOS_SEM_LINHA`). Dinâmico novo → `ROTULOS_DINAMICOS_CONHECIDOS` com `arquivo:linha` e padrão. O teste foi desenhado para que **nenhuma dessas entradas possa ser preenchida por omitir**: cair em `outras` exige linha explícita.
