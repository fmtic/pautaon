# AJ3 - Fechamento do AJ1 e do AJ2 com testes reais

Data: 31/10/2026 - Branch: nova_feature - Sem push

Escopo: os quatro arquivos de teste criados no AJ1/AJ2 continham apenas `assert True`. Este trabalho substituiu cada placeholder por testes reais, provou que eles **pegam** o defeito/ajuste correspondente (prova de reversão) e fechou a suíte. Nenhuma migration, nenhum comportamento novo de app além do único fix exposto por teste, nenhuma escrita em banco real (`pautaon` e `pautaon_ensaio` só em `SELECT`), nenhum e-mail/IP/hash/CPF impresso em teste ou relatório.

## E0 - Linha de base

- Branch `nova_feature`, HEAD inicial `c40e08d`; árvore limpa.
- Suíte de linha de base (uma corrida, `-q`): **`1222 passed, 693 warnings in 373.85s`** (evidência bruta em `.tmp/aj3_baseline.txt`).
- Placeholders confirmados: os quatro arquivos continham só `assert True` — nada era exercitado.
- Censo de `log_acao.acao` (somente `SELECT DISTINCT acao, COUNT(*)`): 27 ações distintas em `pautaon`, 29 em `pautaon_ensaio`, **30 na união**; gravado em `.tmp/acoes_reais.json` e congelado dentro do teste (os testes não leem Postgres).

## E1 - Serviço Social × Relatórios (`tests/test_aj1_servico_social_relatorios.py`)

Commit ancorado: `8598145` (`ROLES_RELATORIOS` passou a incluir `servico_social`).
Resultado: **`13 passed, 12 warnings in 12.42s`**.

A lista de rotas não é digitada à mão: ela sai de `app.url_map.iter_rules()` filtrando o blueprint `relatorios`, o que torna a paridade uma comparação **exaustiva** — se alguém abrir uma rota nova, ela entra na comparação automaticamente, e sobra `assert "<" not in caminho` para pegar rota sem id de teste.

### Rotas GET do blueprint `relatorios` (13) e status por perfil

| Rota | `servico_social` (A) | `pedagogico` (A) |
|---|---|---|
| `/relatorios/` | 200 | 200 |
| `/relatorios/alunos` | 200 | 200 |
| `/relatorios/alunos/<aluno_id>/ficha` | 200 | 200 |
| `/relatorios/bi` | 200 | 200 |
| `/relatorios/bi/dados` | 200 | 200 |
| `/relatorios/bi/exportar/xlsx` | 400 | 400 |
| `/relatorios/bi/indicador/ALU-008` | 200 | 200 |
| `/relatorios/conselho` | 200 | 200 |
| `/relatorios/exportar` | 200 | 200 |
| `/relatorios/observacoes` | 200 | 200 |
| `/relatorios/painel` | 200 | 200 |
| `/relatorios/painel/busca` | 200 | 200 |
| `/relatorios/relatorio_alunos/exportar` | 302 | 302 |

**Zero divergência** entre os dois perfis nas 13 rotas. O 400 e o 302 são os casos sem parâmetro obrigatório (export do BI sem `codigo`; export de alunos sem seleção) e ocorrem **igualmente** nos dois perfis — paridade é isso, não "tudo 200". Com `?codigo=ALU-008` e `?colunas=nome&colunas=nivel` as duas exportações devolvem XLSX válido (lido pelo zip em memória) para os dois perfis.

Outros achados da E1:

- **Escopo, não tela:** `servico_social` não é perfil global, então `get_unidade_id()` continua forçando a unidade do usuário. Ficha 360° de aluno da unidade B → **404** para os dois perfis; BI pedindo `unidade_id` de B → **403**; painel e diário de bordo de A não exibem os nomes sintéticos de B; o `servico_social` de B não vê os de A.
- **Paridade dos demais perfis:** `gerencia` e `secretaria` com o mesmo comportamento; professor **403** em todas; perfil pendente sem abrir nenhuma rota.
- **Menu:** `/painel` do Serviço Social traz o link de Relatórios; o do professor não.
- **Sem regressão de autenticação:** o conjunto de rotas GET sem `@login_required` continua exatamente as 8 públicas históricas (`/`, `/login`, as 3 do Google, `/politica_privacidade`, `/termos_servico`, `/logout`) — o AJ1 não abriu nada.

## E2 - Filtro de ações em `/admin/logs` (`tests/test_aj1_logs_filtro.py`)

Commits ancorados: `f79c964` (filtro por categoria) + **`1e39e23` (fix desta etapa)**.
Resultado: **`58 passed in 13.12s`**.

**Defeito real exposto por teste** (o único do AJ3): `Exclusão de Turma`, gravada por `registros/turmas.py`, caía em **`outras`** no filtro, embora a própria listagem a pintasse com o selo de exclusão. Corrigido em commit próprio, separando a correção do teste: a categoria passou a `exclusao` e o dicionário `_CATEGORIAS_ACAO` virou **fonte única** do `ilike` aplicado no SQL e do selo exibido — enquanto os dois viverem em lugares diferentes, a tela pode discordar de si mesma.

Regra de classificação (`categoria_acao`, `app/auth.py`): `acao.strip().lower()` comparado com `startswith`, na ordem do dicionário; o que não casa (inclusive texto vazio/`None`) é `outras`.

- `login`: `login`, `logoff`, `logout`, `cadastro local`, `reset de senha`, `desbloqueio de login`, `acesso aprovado`, `aviso de invas`
- `criacao`: `criar`
- `edicao`: `alterar`, `alteração`, `editar`, `trocar`, `troca`
- `exclusao`: `excluir`, `exclusao`, `exclusão`, `remover`, `remoção`
- `outras`: restante

### Tabela de ações reais × categoria (censo de 31/10/2026)

| Ação | Categoria | `pautaon` | `pautaon_ensaio` |
|---|---|---|---|
| Acesso Aprovado | login | 195 | 356 |
| Alterar Aluno | edicao | 278 | 383 |
| Alterar ConselhoClasse | edicao | 0 | 27 |
| Alterar Inscricao | edicao | 0 | 107 |
| Alterar RegistroAula | edicao | 10 | 34 |
| Alterar TemaAula | edicao | 7 | 28 |
| Alterar Turma | edicao | 51 | 142 |
| Alterar TurmaCurso | edicao | 32 | 159 |
| Alteração de Cadastros | edicao | 1 | 2 |
| Aviso de Invasão/Falha | login | 17 | 44 |
| Cadastro Local | login | 15 | 15 |
| Criar Aluno | criacao | 4 | 25 |
| Criar ConselhoClasse | criacao | 39 | 19 |
| Criar Inscricao | criacao | 62 | 89 |
| Criar RegistroAula | criacao | 5 | 15 |
| Criar TemaAula | criacao | 51 | 57 |
| Criar Turma | criacao | 14 | 25 |
| Criar TurmaCurso | criacao | 16 | 32 |
| Disparo de E-mail | outras | 7 | 6 |
| Editar aluno | edicao | 74 | 80 |
| Erro E-mail | outras | 5 | 5 |
| Excluir turma (lógica) | exclusao | 0 | 1 |
| **Exclusão de Turma** | **exclusao** (antes do fix: `outras`) | **8** | **6** |
| Informacao Padrao | outras | 4 | 10 |
| Logoff | login | 114 | 63 |
| Manutenção | outras | 2 | 2 |
| Remoção Grave | exclusao | 6 | 6 |
| Reset de Senha | login | 4 | 3 |
| Sessões revogadas | outras | 1 | 0 |
| Troca de Senha | edicao | 6 | 6 |

Entram também na parametrização **10 rótulos que o código emite mas ainda não têm nenhuma linha** nos dois bancos (`Acesso via Google`, `Cadastro Período Letivo`, `DESENTURMADO`, `Desbloqueio de login`, `Excluir aluno`, `Gestão de Unidade`, `Reativação de Turma`, `Trocar Professor da Oferta`, `TRANSFERENCIA`, `Vínculo Google`) — ficam congelados para não serem esquecidos quando a primeira linha for gravada.

O que os testes cobrem, além da classificação: cada filtro devolve só a própria categoria (conferido linha a linha) com o badge batendo com o criado, travessia de paginação sem repetir nem perder linha (`exclusao` com 28 linhas na semente), `outras` como complemento exato (sem duplicar linha de nenhuma categoria), o href de "Próxima" conservando `acao=<categoria>`, valor inválido (`%`, `_`, `0`, `login criacao`) tratado como "Todas as Ações" sem erro, `EXCLUSAO` em caixa alta funcionando, o `select` reexibindo a opção com `selected`, e os 403 de `pedagogico`/`secretaria`/`professor`/`servico_social` com e sem filtro.

## E3 - Lançamento do conselho (`tests/test_aj2_conselho_lancamento.py`)

Commit ancorado: `f3d2b15`. Resultado: **`12 passed in 6.05s`**. Nenhum defeito novo exposto — nenhum `fix(...)` nesta etapa.

- **Resposta e observação separadas:** a alternativa clicada marca o `hidden` `resp_<aluno>_<pergunta>` e **não escreve** no `textarea` `obs_<aluno>_<pergunta>`. O teste lê o HTML renderizado com expressões próprias (`_OBS_TA`, `_RESP_HIDDEN`, `_MARCA_OPCAO`) e exige que **exatamente uma** alternativa apareça marcada — na abertura sem lançamento, **nenhuma**.
- **Semântica de gravação de `salvar_conselho`:** chave `obs_` ausente do POST **preserva** o texto; chave `obs_` presente e vazia **limpa**; `resposta` e `observacao` são gravadas em campos distintos de `conselho_resposta`; o autor (F1) só troca quando o conteúdo muda.
- **Contraste (número exato):** o enunciado das perguntas usa `--conselho-pergunta-cor: #0a3d62`. A razão de contraste calculada sobre `#ffffff`, pela fórmula de luminância relativa da WCAG 2.x (canal sRGB com `/12.92` abaixo de `0.03928` e `((v+0.055)/1.055)**2.4` acima; `L = 0.2126R + 0.7152G + 0.0722B`; `(L1+0.05)/(L2+0.05)`) é **11,31:1** — o teste imprime `[AJ3-E3] contraste #0a3d62 sobre #ffffff: 11.31:1` e exige `>= 4.5`.
- **O JS é testado de verdade:** o handler real extraído de `static/js/conselho/conselho.js` roda em **Node v24.19.0** contra um DOM mínimo, com skip documentado quando não há `node`. As asserts: o hidden recebe `Sempre`, o `textarea` de observação sai **inalterado**, e o botão ganha `active`/`fw-bold`.

## E4 - Select de período do painel pedagógico (`tests/test_aj2_painel_periodo_select.py`)

Commit ancorado: `9794165` (feature: `nome_exibicao` + `joinedload`). Resultado: **`7 passed in 4.96s`**. Sem `fix(...)`.

- Dois períodos **homônimos** em unidades diferentes seguem duas opções e cada rótulo traz o prefixo da unidade; período sem unidade mostra só o nome, sem espaço sobrando.
- `value` continua o id e `?periodo_letivo_id=` devolve **um único** `selected`, que acompanha a troca da querystring.
- **T3 lido do banco:** todos os rótulos são comparados com `html.escape(p.nome_exibicao, quote=False)` de `PeriodoLetivo.query.all()` — quem voltar a usar `p.nome` puro quebra.
- Nome de unidade com `<b>` sai **escapado** no `<option>`, sem injetar markup.
- **Custo medido** com listener `before_cursor_execute` em apps novos (3 e 12 períodos): **18 SELECTs nos dois cenários** — não cresce com o número de períodos — e a consulta que lista os períodos já traz `JOIN unidade`, provando o `joinedload` (o teste isola essa consulta pelo `ORDER BY periodo_letivo.data_inicio desc` sem `LIMIT`, para não confundir com a consulta paginada do BI).
- Escopo intacto: `pedagogico` de A vê só os períodos de A (com o prefixo e o `selected` de A); `admin`/`pedagogico`/`secretaria`/`servico_social` com 200; professor 403; anônimo redireciona.

## E5 - Prova de reversão

Método: para cada arquivo, reverter **só os arquivos de app** do commit correspondente (`git checkout <hash>^ -- <arquivos>`), rodar o teste, restaurar (`git checkout HEAD -- <arquivos>`) e conferir `git status` limpo. Antes, `git log <fix>..HEAD -- <arquivos>` confirmou que nenhum dos arquivos foi tocado depois do ajuste — a reversão é limpa.

| Arquivo de teste | Reversão | Sem a correção |
|---|---|---|
| `test_aj1_servico_social_relatorios.py` (13) | `8598145^ -- app/relatorios/shared.py` | **8 falham, 5 passam** (os 5 são as não regressões: professor 403, rotas públicas, escopo) |
| `test_aj1_logs_filtro.py` (58) | `f79c964^ -- app/auth.py app/templates/admin/logs.html` | **`ImportError: cannot import name 'categoria_acao'` na coleta** — os 58 nem rodam |
| `test_aj1_logs_filtro.py` (58) | `1e39e23^ -- app/auth.py` | **9 falham, 49 passam** |
| `test_aj2_conselho_lancamento.py` (12) | `f3d2b15^ -- app/conselho.py + static/js/conselho/conselho.js + templates/conselho/lancamento.html` | **8 falham, 4 passam** (T5, T6a, T6b, T6d — não regressão) |
| `test_aj2_painel_periodo_select.py` (7) | `9794165^ -- app/relatorios/painel_pedagogico/rota.py + templates/relatorios/painel_pedagogico.html` | **6 falham, 1 passa** (T6b, invariante de permissão) |

Reforços feitos **a partir** dessa prova: o T2/T1 do conselho trocaram uma checagem frágil (split em `class="btn btn-xs"`) por `_MARCA_OPCAO` + asserção de "exatamente uma marcada"; e o T5 do painel passou a provar o `JOIN` diretamente, porque na primeira versão ele **passava na reversão** — o template revertido usava `p.nome` e não gerava lazy load, então a contagem de SELECTs sozinha não bastava. Evidências: `.tmp/aj3_e5_e1_sem_fix.txt`, `.tmp/aj3_e5_e2_sem_f79c964.txt`, `.tmp/aj3_reversao_e2_sem_fix.txt`, `.tmp/aj3_e5_e3_sem_f3d2b15.txt`, `.tmp/aj3_reversao_e4_sem_fix.txt`.

## E6 - Verificação final

- Suíte completa, uma corrida: **`1308 passed, 704 warnings in 369.78s (0:06:09)`** (`.tmp/aj3_suite_final.txt`). Linha de base 1222 → **1308** = +86 testes novos (13 + 58 + 12 + 7 = 90 no total dos arquivos; os 4 placeholders já contabilizados na base contribuíam 4, daí o acréscimo líquido de 86). Zero falha, sem rodadas de correção.
- `ruff check --select F821,F811,F841 app tests scripts migrations`: **All checks passed!** (`.tmp/aj3_ruff_final.txt`).

## Alterações externas (guarda Nextcloud)

Duas edições que não eram deste trabalho apareceram na árvore durante a execução e foram tratadas antes de qualquer commit:

1. `app/templates/alunos/transferir.html` (2 linhas de rótulo, "oferta" → "curso"), mtime 23:03:53 — mantido como estava, por decisão do usuário.
2. `app/conselho.py`, `app/templates/turmas/detalhe.html`, `backlog_desenvolvimento.md` (varredura da mesma troca de vocabulário), mtimes 23:05–23:06 — a E5 ia apagar essa edição não commitada com `git checkout HEAD -- app/conselho.py`; o trabalho parou, o usuário commitou como `2fc5b46 "Alterado de oferta para curso"` e só então a E4/E5 seguiram.

Nenhum push foi feito por este trabalho. (O ref `origin/nova_feature` avançou por conta do usuário.)

## Commits do AJ3

| Hash | Tipo | Conteúdo |
|---|---|---|
| `d2934e5` | test(aj1) | `tests/test_aj1_servico_social_relatorios.py` (13) |
| `1e39e23` | **fix(logs)** | `Exclusão de Turma` na categoria `exclusao`; fonte única SQL/selo |
| `410d5bc` | test(aj1) | `tests/test_aj1_logs_filtro.py` (58) com censo congelado |
| `a4a6049` | test(aj2) | `tests/test_aj2_conselho_lancamento.py` (12) |
| `9d935e6` | test(aj2) | `tests/test_aj2_painel_periodo_select.py` (7) |
| (este) | docs | MER, backlog e este relatório |

## Pendências (continuam do AJ1/AJ2)

- Ajuste 4 — Resumo/primeira vista: cards Painel do Conselho, Desempenho por Professor, Frequência por Turma.
- Central de BI: página explicando cada indicador e como é calculado (auditoria e guia de uso), acessível a quem entra na Central.
- Cadastro de aluno: aproveitar melhor a área do formulário de novo aluno (mudança crítica, todo o resto depende dessa entrada) e permitir **excluir** documento entregue, não só fazer upload.
