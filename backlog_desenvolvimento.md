### Alterações do dia — 30/10/2026 (S1 — execução do Prompt A: E1 a E7)

- **E1 (S1-01/S1-02):** `config.py` sem fallback de `SECRET_KEY`; `validar_configuracao` chamada por `create_app` recusa chave ausente, vazia, `dev-key*` ou com menos de 32 caracteres em qualquer `APP_ENV`, com mensagem que ensina `secrets.token_urlsafe(48)`. `DEBUG` agora é `False` por padrão e só liga com `FLASK_DEBUG=true` **e** `APP_ENV=development`; `DEBUG` em produção falha na inicialização. `APP_ENV` é a chave oficial e `FLASK_ENV` ficou como alias legado. `run.py` usa `app/utils/execucao.escolher_bind_dev`: debug só em `127.0.0.1`, `development` sem debug em `0.0.0.0`, outros ambientes recusam o servidor embarcado (mensagem para waitress/gunicorn/IIS). `.env.example` atualizado. **53** arquivos de teste ganharam `SECRET_KEY` explícita (a suíte deixou de depender do `.env`); 19 testes novos em `test_s1_config_endurecimento.py`. Suíte **1054 → 1073**.

- **E2 (S1-04):** `app/main/rota_disparo_email.py` **removido** e o import tirado de `app/main/__init__.py`; `main.teste_email` saiu do `url_map` (207 → 206). `GET /teste-email` → 404 para anônimo e autenticado. Nenhum template/teste/script usava a rota (restam só menções históricas no relatório S1 e em entradas antigas do backlog). 3 testes em `test_s1_teste_email_removido.py`.

- **E3 (S1-05):** `/informacoes`, `POST /api/conselho-periodo` e `DELETE /api/conselho-periodo/<id>` exigem `admin`/`pedagogico`/`gerencia`/`secretaria` (mesma lista da navegação); professor 403. `@csrf.exempt` removido das duas rotas e `X-CSRFToken` enviado nos `fetch` de `conselho/informacoes.html`. A unidade do conselho passou a ser validada com `assert_unidade_context` na edição e na exclusão (**antes era filtrada na consulta e devolvia 404**; agora 403 quando é de outra unidade, 404 quando não existe). 14 testes em `test_s1_conselho_periodos.py`.

### Alterações do dia — 30/10/2026 (S1 — análise de segurança)

- **Natureza:** somente análise; **nenhum código de aplicação alterado**. Relatório `docs/Relatórios/S1_AnaliseSeguranca.md` (matriz de 207 rotas, 24 achados, o que está correto, o que não é verificável e ordem de correção).
- **Método:** leitura de código, inventário `url_map` + AST (decoradores e checagem de papel), varredura de padrões (`text(f)`, `|safe`, `csrf.exempt`, uploads, segredos), sondagem com `app.test_client()` contra `pautaon_ensaio` (login HTTP real dos usuários `[ROTEIRO]`, sem bind no AD) e auditoria do histórico Git. Escritas no ensaio limitadas a `log_acao` e `login_attempts:*`, listadas por id e removidas (1485/13 → 1485/13).
- **Críticos:** `SECRET_KEY` com fallback fixo (`config.py:49-53`, o `.env` atual traz `FLASK_ENV=development`); `FLASK_DEBUG=true` (debugger do Werkzeug e páginas de erro detalhadas); **bancos SQLite e `error.log.1` com dados pessoais no histórico Git** (`instance/database.db`, `instance/database.db.bak`, `instance/backups/database-antes-initdb-2026-09-29.db`, `instance/error.log.1`) — incidente LGPD que exige `git filter-repo` e rotação de segredos.
- **Altos:** `/teste-email` público (envia e-mail para qualquer destinatário, sem login); `POST/DELETE /api/conselho-periodo` com `@csrf.exempt` e **sem checagem de papel**; logout não invalida a sessão no servidor (cookie copiado continua autenticando — provado).
- **Médios:** XSS armazenado no nome do período de conselho (`conselho/informacoes.html:63`); upload de foto de aluno sem validação servido inline; cookie sem `Secure`/HSTS fora de `production`; ausência de `Cache-Control: no-store`; rate limit só por IP (NAT e `X-Forwarded-For`); enumeração de usuários por tempo (~120 ms × ~19 ms); senha inicial em texto claro por e-mail; ausência de CSP; `ProxyFix` incondicional.
- **Verificado e correto:** isolamento de unidade nas leituras e escritas (ficha 404, histórico/foto/BI/admin 403), nenhuma rota pública de arquivo, CSRF global com `X-CSRFToken` nos `fetch`, nenhum `text(f)` em `app/`, `ilike` parametrizado, autoescape ativo e `tojson|safe` seguro, sem CORS, LDAP com bind direto (sem bind anônimo e sem filtro construído com entrada) e TLS com `CERT_REQUIRED`, Google com `state`/`email_verified`/domínio/vínculo com senha, `.env` fora do versionamento atual.
- **Pendências (ordem sugerida no §6 do relatório):** 1) `SECRET_KEY`/`DEBUG`; 2) histórico Git + rotação; 3) `/teste-email`; 4) papel + CSRF no conselho; 5) invalidação de sessão; 6) XSS e upload de foto; 7) cabeçalhos (cache/CSP/Secure/HSTS/ProxyFix); 8) rate limit e tempo de login; 9) política de senha no cadastro; 10) baixos; 11) revisão LGPD de dados sensíveis.
- **Sem migration, sem push.** Suíte mantida em **1054 passed**; ruff `F821/F811/F841` limpo.

### Alterações do dia — 30/10/2026 (L5 — turmas sem oferta e resíduos do harness)

- **E0 (leitura):** inventário por FK dinâmica (`pg_constraint` → `turma`) e por nome de coluna nos dois bancos. Principal: turmas 12 (Alfa), 13 (Gema) e 14 (Zeta) ativas, unidade 3, **zero ofertas**, zero inscrições/registro de aula/conselho/transferência/dia bloqueado — só `frequencia` na 13, com **2 linhas legadas** (ids 23 e 24, aluno 1455, 04 e 05/03/2026, autor NULL). Ensaio: turma 34 sem **nenhum** vínculo. `log_acao` não tem FK para `turma` (guarda texto). Bate com o esperado.
- **E1:** remoção **física** das quatro turmas + as 2 frequências legadas — `scripts/limpar_turmas_sem_oferta.py` (dry-run padrão, backup automático no `--aplicar`, `--autorizar-principal` para o principal, recusa turma com oferta/vínculo inesperado e valida o delta antes do commit). Ensaio primeiro: `turma` 8→7, demais contagens idênticas. Principal depois: `turma` 5→2 e `frequencia` 54→52, demais idênticas (`inscricoes` 13, `registro_aula` 4, `conselho_classe` 39, `conselho_resposta` 78, `log_acao` 1014). Backups `pautaon_pre_limpeza_turmas.sql` e `pautaon_ensaio_pre_limpeza_turmas.sql`. Zero turma ativa sem oferta ativa nos dois bancos (MER §12.27).

- **E2:** `tests/conftest.py` único (novo): `app` (14 arquivos), `client` (14) e `app_com_servidor` (3, via wrapper) — censo por AST deu **58 definições em 15 grupos**; migrou só o idêntico, **27 variantes ficaram locais** por divergirem (config inline, sem CSRF desligado, `UPLOAD_FOLDER` temporário, app de migrations). **44** imports cruzados de fixture ajustados. Teste do H4 passou a usar rota restrita para discriminar a identidade (professor → `/conselho/fechamento` 403; pedagógico → `/frequencia_relatorio` 200; `coord` → 403). Suíte **1054 passed** (mesmo total), ruff `F821/F811/F841` limpo, `F401` em `tests` 37→11.

### Alterações do dia — 30/10/2026 (F1 — autor do lançamento em frequência e conselho)

- **Pedido:** registrar o autor em `frequencia` e `conselho_resposta` — sempre o **último** usuário que salvou a linha (sem campo de autor original), histórico antigo NULL e contextos sem usuário (scripts/seeds) NULL. Sem exibição, relatório, BI, impressão ou permissão.
- **E0 (leitura):** inventário de quem grava nas duas tabelas. `frequencia`: `utils/logica.py::salvar_frequencia` (único caminho do `POST /frequencia`, com `current_user`), `scripts/semear_roteiro_manual.py::_frequencia`, `scripts/ensaio_l4_1_reativacao.py`, `scripts/verificar_sinal_updated_at.py` e sementes de teste (sem usuário); `tests`/`scripts/remover_ofertas_sem_lancamento.py` e `registros/turmas.py:1943` só apagam. Transferência (`alunos.py::transferir_aluno`) e desenturmação **não** tocam `frequencia`. `conselho_resposta`: só `conselho.py::salvar_conselho` (`avaliar_turma` grava `TurmaCurso.avaliacao_*`; o fechamento grava `ConselhoClasse`). `AuditoriaMixin`/`TenantMixin` não cobriam as duas tabelas porque elas herdam **apenas** `TenantMixin` — sem `updated_by_id`, o listener `before_flush` as ignora.
- **E1:** `autor_id` (FK → `user`, `ON DELETE SET NULL`, **sem índice**) + `autor_nome` (varchar(100), snapshot) nas duas tabelas; migration aditiva e idempotente `c9d0e1f2a3b4` (`f36f803`). Backup `pautaon_pre_autor_lancamento.sql`/`pautaon_ensaio_pre_autor_lancamento.sql`; ensaio primeiro (up → `\d` → down → up), depois o principal; head `c9d0e1f2a3b4` nos dois. Contagens intactas: principal 54/78 e ensaio 18/5, zero linhas com autor preenchido.
- **E2:** helper único `app/utils/autor.py::autor_do_lancamento` (None/None sem request). `salvar_frequencia` grava o autor na criação e troca só quando o **conceito** muda; `salvar_conselho` grava na criação e troca só quando o **texto** muda (`9693f3e`). Nenhuma consulta nova por linha no POST.
- **E3:** `tests/test_f1_autor_lancamento.py` (12) — criação, troca por outro usuário, regravação idêntica, histórico NULL/200, FK `SET NULL` + linha sobrevivendo à exclusão do usuário, contexto sem usuário e ≤1 SELECT em `user` no POST com 3 alunos. Ensaio na oferta 45 do `pautaon_ensaio` (semente M1): autor do professor → troca para o admin → mantido na regravação idêntica; `SET NULL` real conferido; banco devolvido ao estado original (18/5/4). **Suíte 1042 → 1054 passed**.
- **Pendências (MER §12.26):** (1) exibir o autor em tela — falta definir **quem pode ver**; (2) autor original se perde a cada reedição (decisão atual) — histórico completo exigiria tabela de auditoria; (3) `registro_aula.instrutor_id` continua sobrescrito a cada salvamento, sem snapshot do nome.
- **Relatório:** `docs/Relatórios/F1_AutorLancamento.md`.

### Alterações do dia — 30/10/2026 (fechamento G1/P2 — E0 a E5)

- **E0:** suíte verde no working tree (**1042 passed**; 1033 da linha de base + 9 do `test_g1p2_links_impressao.py`); commits por assunto `53d6f2e` (G1-4 links), `9ed074b` (topbar 56px), `49aa982` (README) e `d91969a` (interpretador do VS Code). O rename “Diário de Observações”→“Diário de Bordo” já estava em `9652adc`. Cinco arquivos revertidos pela sincronização do Nextcloud foram restaurados do HEAD antes da E0 (backup em `.tmp/revert_bak/`).
- **E1/E2:** já aplicados em 29/10 (`ee922c5`, `59880c3`, `3af4ee2`, `434c53f`; MER §8.23) e reconferidos por SELECT em 30/10: zero ofertas com `professor_id` NULL, `turma_curso.professor_id` com `is_nullable = NO` e head `d6e7f8a9b0c1` nos dois bancos.
- **E3:** links de impressão explícitos (`lancar.html`/`detalhe.html`) — item (4) do G1 resolvido (código `53d6f2e`, docs `a0a5926`).
- **E4:** harness — 38 arquivos e 50 blocos de login local migrados para `login_as` (`d744693`; seção do harness acima).
- **E5:** merge local sem push — `a24574b` (nova_feature ← main), `37b2042` (main ← nova_feature, `--no-ff`) e `484cbcf` (higiene: `tmpfldc2ofh` vazio). Relatório: `docs/Relatórios/G1P2_Fechamento_NotNull.md`.

### Alterações do dia — 29/10/2026 (E1-2ª rodada — saneamento das ofertas 16, 17 e 18 com lançamentos)

- **Pedido:** decisão do usuário — as três ofertas do principal bloqueadas na rodada anterior (frequência lançada) são **dados de teste**: remover as ofertas junto com os lançamentos vinculados (frequencia, registro_aula, conselho_classe/conselho_resposta, inscrições e grade), **somente** as linhas com `turma_curso_id` em 16/17/18; legados com `turma_curso_id IS NULL` intocáveis.
- **Ferramenta:** `scripts/remover_ofertas_sem_lancamento.py` estendido com `--remover-lancamentos` (mantidos dry-run por padrão, trava do principal com `--autorizar-principal`, backups em `instance/backups/` e contagens antes/depois). Backup antes da operação: `pautaon_pre_saneamento_ofertas_2.sql`.
- **Removido (principal):** oferta 16 (turma 12, frequencia 5, inscrições 2), 17 (turma 12, frequencia 2, inscrições 2) e 18 (turma 13, frequencia 2, inscrição 1). Contagens: frequencia 63→54 (−9), inscricoes 18→13 (−5), turma_curso 5→2 (−3); registro_aula/conselho_classe/conselho_resposta/turma_curso_horario sem alteração (zero vínculo). As turmas 12 e 13 ficam **sem oferta ativa** (juntam-se à 14 da rodada anterior).
- **Conferência (SELECT, os dois bancos):** zero ofertas sem professor — **ativas ou inativas** — no principal e no ensaio; frequencia legada NULL preservada (2 linhas na turma 13 no principal; 4 na turma 30 no ensaio). **Item (3) do G1 destravado: a migration NOT NULL passa a ser aplicável (E2).**
- Sem migration nesta etapa; suíte inalterada (1033 passed no pré-commit da rodada).

### Alterações do dia — 29/10/2026 (G1/P2 — professor obrigatório na oferta e troca com confirmação e log)

- **Pedido:** E2 da rodada de quatro etapas (E0 leitura, E1 saneamento, E2 G1/P2 + troca, E3 I1). Serviço com professor obrigatório em `adicionar_oferta` e `editar_oferta` (`ValueError` em português; trocar é permitido, esvaziar não), herança de `turma.professor_id` na criação e os espelhos oferta↔turma revisados (`turmas.py:1844`, `:1945` — **editar a turma não pode propagar NULL**), formulários sem “-- Sem professor --” com `required`, migration `NOT NULL` **somente** após o saneamento da E1 conferido nos dois bancos, troca com lançamentos exigindo confirmação (mesmo padrão do bloco de limpeza de lançamentos, `turmas.py:1819-1835`) e `log_acao` com o professor anterior e o novo (nomes e ids) **sem alterar o formato das demais entradas**.
- **Serviço** (`app/services/turma_curso.py`): `_validar_professor` devolve a mensagem única `_PROFESSOR_OBRIGATORIO` (“Selecione o professor responsável: toda oferta precisa de um professor.”) para vazio, id inexistente e professor de outra unidade; `adicionar_oferta` resolve a herança **antes** da validação (só herda `turma.professor_id` quando a turma não tem curso legado — o mesmo critério do espelho `_sincronizar_legado`), `criar_oferta_inicial_da_turma` exige professor da turma, e `editar_oferta` valida **antes** de qualquer `setattr` — esvaziar nunca grava.
- **Espelhos:** `editar_turma` só propaga `turma.professor_id` à oferta única quando ele existe; se a turma chegar sem professor, recebe o da oferta de volta (branch `elif`), de modo que nenhum caminho grava NULL em `turma_curso.professor_id`. `turma_oferta_editar` e `editar_turma` registram a troca (anterior e novo) antes de gravar.
- **Formulários:** `turmas/ofertas.html` (edição e nova) e `turmas/editar.html` sem “-- Sem professor --”, com `required`, label `Professor *` e texto de ajuda; no editar a turma o `required` vale para oferta única (com 2+ o campo permanece readonly+hidden, porque a edição por turma não decide professor por oferta).
- **Migration NÃO aplicada:** a regra de parada da E1 vale — restam **3 ofertas ativas sem professor no principal (16, 17 e 18)**, preservadas porque têm frequência lançada. `turma_curso.professor_id` continua `is_nullable = YES`; a obrigatoriedade é de **serviço e formulário**, não de schema. Precisa de decisão sobre o lançamento existente (reatribuir antes do `NOT NULL`) — nenhuma migration foi criada nem executada.
- **Confirmação da troca:** replicado o padrão de `limpar_lancamentos` — hidden `confirmar_troca_professor` que o JS da tela (`app/static/js/turmas/editar.js` e o bloco de `ofertas.html`) só liga após `window.confirm`, e **somente** onde há lançamento: a tela marca cada select com `data-professor-original` e `data-com-lancamento`, alimentado por `ofertas_com_lancamentos(ids)` (três consultas `DISTINCT` em lote sobre `frequencia`, `registro_aula`, `conselho_classe`). Troca sem lançamento salva direto; POST forjado sem o marcador recebe flash de aviso, redirect/rollback e o professor fica intacto.
- **Log:** entrada nova `LogAcao(acao="Trocar Professor da Oferta")` com `detalhes` em par único parseável — `oferta_id=N anterior_id=ID|none anterior_nome="..." novo_id=ID novo_nome="..."` (`formatar_detalhe_troca_professor` / `parsear_detalhe_troca_professor` + `_PADRAO_TROCA_PROFESSOR`). **Formato das demais entradas inalterado** — inclusive as `Alterar TurmaCurso` antigas, que seguem com `repr(obj)` sem valor anterior (T0-c).
- **Testes:** novo `tests/test_g1_p2_professor_oferta.py` (**20**) cobre recusa no serviço (`adicionar_oferta`, `editar_oferta`, `criar_oferta_inicial_da_turma`) e no formulário, herança da primeira oferta, round-trip do `detalhes`, troca simples, troca com lançamento exigindo confirmação (professor intacto e log zero até o marcador), troca para o mesmo professor sem log, o log com anterior e novo, editar a turma sem zera a oferta, a tela sem “-- Sem professor --”/com `required` e a sinalização `data-com-lancamento`. Ajustados 6 arquivos cuja semente criava oferta sem professor: `test_turma_curso_fase2` (14), `_fase3` (17), `_fase4` (24, com assert novo de que a oferta inicial herda o professor), `_horario_escritores`, `test_leituras_residuais_grade_h3f` (18) e `test_concomitancia_grade_por_dia` (13) — antigo × novo × motivo no relatório da rodada.
- **Suíte:** baseline **1006** → **1026 passed, 0 failed** (+20). Ruff `F821, F811, F841` em `app tests scripts`: limpo. **Sem migration**; banco principal só lido (`SELECT`); nenhum ensaio nesta etapa.
- Docs: MER §7 (professor da oferta reescrito), §8.20 (duas atualizações como histórico) e §8.21 (nova); pendências G1 (1)(2)(3)(5) reescritas abaixo; relatório `docs/Relatórios/I1_G1P2_TrocaProfessor.md`.

### Alterações do dia — 29/10/2026 (I1/T0 — regra por oferta nos guardas restantes: verificação e higiene)

- **Pedido:** T1 (migrar `ver_turma`, `ver_observacoes`, `/frequencia` e o `detalhe.html` para a regra da oferta) precedida de P0 (G1/P2 aplicado?) e T0 (verificação a–e, só leitura); T2 de higiene (2 F401 em `app/registros/core.py` + 9 F841 em `tests/`). Um commit por etapa.
- **P0 — FALHOU, T1 não implementada:** no principal, 6 ofertas ativas e **4 sem professor** (16 e 17 na turma 12, 18 na 13, 19 na 14 — as turmas também sem professor: `scripts/saneamento_professor_oferta.py` em dry-run acha *0 copiáveis, 4 pendentes de decisão*); `turma_curso.professor_id` segue `is_nullable = YES`; `_validar_professor` (`app/services/turma_curso.py:402-414`) aceita vazio e os formulários mantêm “-- Sem professor --” sem `required` (`turmas/ofertas.html:112`, `:238`; `turmas/editar.html:174`). Como a regra por oferta é **sem herança** e “oferta sem professor não libera nada”, migrar as guardas agora **tiraria** o acesso desses professores — parada reportada; entregue T0 + T2.
- **T0 (respostas, só leitura):** (a) trocar o professor é permitido por duas rotas (`turma_oferta_editar`, `app/registros/turmas.py:2194-2225`; `editar_turma` com espelho na oferta única, `:1844`/`:1945`) e **pode ficar vazio**; a confirmação de `:1819-1835` só cobre agenda e datas, não a troca. (b) `frequencia` **não tem autor**; `registro_aula.instrutor_id` é **sobrescrito** a cada salvamento (`app/utils/logica.py:744`); `conselho_classe.instrutor_id` só na criação; `conselho_resposta` não tem `turma_curso_id` nem autor. (c) a troca gera `LogAcao` (32 linhas `Alterar TurmaCurso` no principal), mas `detalhes=repr(obj)` → `<TurmaCurso 14>`: **sem o valor anterior**. (d) a decisão da medicação é de **conteúdo** da pauta, não de quem lança — o `/frequencia` não depende dela (o que barra a T1 é o P0). (e) guardas ainda em `Turma.professor_id`: `ver_turma` `turmas.py:1374-1378`, `ver_observacoes` `:2640-2644`, `POST /frequencia` `core.py:256-259`, `GET /frequencia` `core.py:382-399`, `historico_aluno` `alunos.py:881-893`, `/aluno/<id>/foto` `:1316-1327`; já por oferta: `imprimir_pauta`, I1, painel do professor e conselho.
- **Consequência registrada para a T1 (não implementada):** ao migrar, o professor da oferta sem ser o da turma **ganha** acesso e o professor da turma **sem oferta ativa onde leciona perde**; hoje nenhum link do `detalhe.html` leva a 403 porque a página e os alvos usam o mesmo critério — migrar `ver_turma` isolado criaria link para 403, daí migrar os três juntos e filtrar os links por oferta. Ensaio da oferta 45 não executado: nada a validar.
- **T2 — higiene (commit `72e9d40`):** caíram `RegistroAula` e `User` (F401) do import de `app/registros/core.py` — nenhuma outra ocorrência no módulo, e `app/registros/__init__.py` só importa submódulos de rotas — e 9 atribuições F841 em 6 arquivos de `tests/`, **mantendo a chamada** que prepara o cenário (`_base`, `_ids`, `_oferta_com_curso`, `adicionar_oferta`) e reduzindo o desempacotamento em `test_transferencia_oferta`. Fora do escopo: os 87 F401 restantes (re-exports de `app/models/__init__.py` e scripts).
- **Testes:** nenhum teste novo nem ajustado nesta rodada (T1 parada). Os 6 arquivos tocados, isolados: **53 passed**. Suíte completa: baseline **1006** → **1006 passed, 0 failed** (347 s) — mesmo total, sem mudança de comportamento. Ruff `F821, F811, F841` em `app tests scripts`: limpo; `F401` em `core.py`: limpo.
- **Sem migration**, banco apenas lido (`SELECT`); nenhum ensaio executado. Docs: MER §8.20; relatório `docs/Relatórios/I1_RegraPorOferta_Higiene.md`.

### Alterações do dia — 29/10/2026 (Painel do professor — rota legada unificada em `main.painel`)

- **Pedido:** aplicar a **solução B** da entrega anterior (logo abaixo), seguindo o mesmo processo.
- **P1 (o que a rota legada era):** conferido por leitura do template que `dashboard/professor.html` **não lê** `turmas`, `lista_programas`, `programa_ativo` nem `is_readonly` — dos valores montados pela rota legada só `total_alunos` chegava a um card, e a página vinha mesmo assim com “Minhas Turmas” 0 e sem os cards laterais. Não havia o que preservar.
- **Aplicado:** `registros.painel_professor` (`app/registros/core.py`) virou `redirect(url_for('main.painel'))`; saíram ~60 linhas de montagem e os dois imports que só ela usava (`joinedload`, `cond_inscricao_enturmada`). A URL antiga continua existindo (sem 404 para favoritos/links externos). Último ponteiro interno: o card **“Abrir pauta”** do Painel Geral (`dashboard/index.html`) apontava para `/professor/painel` (beco sem saída para o gestor) e foi apontado para `registros.frequencia`, a própria pauta.
- **Mudança de comportamento assumida:** quem roteia o destino é `main.painel` — professor vê o painel completo, admin/gerência/pedagógico o painel gerencial, secretaria o seu, `pendente` a aguardando aprovação; papel desconhecido dá **403** (antes a rota legada dava flash e redirecionava para o mesmo `main.painel`). É a coerência com o menu lateral.
- **Testes:** novo `tests/test_painel_professor_legado.py` (**4**) — redirect do professor com painel completo ao seguir, redirect para o painel do perfil do gestor, exigência de login, Painel Geral sem referência à rota legada. Ajustados 2 testes de `tests/test_enturmado.py` que esperavam 200 e o número “Meus Alunos” na rota legada: passam a testar o contrato do redirect, com o número **4** mantido na definição única (`app.services.enturmado`) que alimentava aquela montagem; a docstring de caracterização (antes 5 → depois 4) foi preservada. Regressão dirigida: **66 passed**.
- **Suíte:** 996 → **1000 passed, 0 failed**. Ruff `app` (F821, F811, F841) limpo. **Sem migration**, sem tabela nova, sem alteração de dados.
- Docs: MER §8.18 (§8.17 atualizado como histórico); relatório `docs/Relatórios/PainelProfessorRotaUnificada.md`; `PainelProfessorRotaVoltar.md` e `DIARIO_ObservacoesAcesso.md` §6 com a pendência da solução B encerrada.

### Alterações do dia — 29/10/2026 (Painel do professor — pendências em 2 linhas e botão "Voltar" do conselho)

- **Pedido:** no `conselho/turma_aval.html`, o botão **Voltar ao Painel** abria o painel do professor **sem os dados**, enquanto o **Painel Geral** da lateral mostrava tudo; analisar a rota antes de corrigir.
- **P1 (diagnóstico):** não era rota quebrada — são **duas rotas para o mesmo template**. `main.painel` (`/painel` → `render_dashboard_professor`) passa `entradas`, `aulas_pendentes` e `dias_bloqueados`; `registros.painel_professor` (`/professor/painel`, `registros/core.py:194`) passa `turmas`, `total_alunos`, `lista_programas`, `programa_ativo` e `is_readonly`. O template itera `entradas` e usa os outros dois blocos: com a rota legada, “Minhas Turmas” sai **0**, a tabela mostra “Nenhuma turma vinculada” e os cards laterais não renderizam. O `total_alunos` também difere (regra por `Turma.professor_id`, pré-oferta).
- **Solução A aplicada (menor risco):** `conselho/turma_aval.html` e os dois redirects de `avaliar_turma` (`conselho.py` — turma sem oferta ativa e pós-POST de “Salvar Avaliação”) passam a usar `main.painel`.
- **Solução B (registrada como pendência naquela entrega, aplicada no mesmo dia):** transformar `registros.painel_professor` em redirect para `main.painel` e remover a montagem duplicada. Exigia ajustar `tests/test_enturmado.py` (2 asserções esperavam 200 e o número em “Meus Alunos” na rota legada) e decidir o destino de admin/pedagógico/secretaria. Ver a seção “Painel do professor — rota legada unificada” acima e o MER §8.18.
- **Testes:** 3 asserções novas em testes existentes (`test_conselho_professor::test_avaliacao_da_oferta_abre_e_grava_para_o_professor` — link `/painel` no GET e `Location` no POST; `test_conselho_oferta::test_avaliar_turma_sem_oferta_recusa` — `Location` `/painel`). Regressão dirigida do conselho: **53 passed**. Nenhum arquivo de teste novo.
- **Card “Frequências Pendentes” (tarefa que estava no working tree, commit `e5428c2`):** limite de **2 linhas** (`limite_pendentes`) reaproveitado no aviso do rodapé — antes o rodapé calculava sobre 5 e informava errado quantos dias ficaram ocultos; 2 testes de dashboard ajustados ao novo contrato. Suíte: **996 passed, 0 failed**.
- Docs: MER §8.17; relatório `docs/Relatórios/PainelProfessorRotaVoltar.md`.

### Alterações do dia — 29/10/2026 (Conselho — lançamento pelo professor: painel e escopo por oferta)

- **Pedido:** o professor lançar o conselho de classe (individual por aluno e da oferta), acessando `Conselho > Painel de Turmas` com apenas as ofertas ativas dele; sem acesso a fechamento nem à gestão.
- **Decisões fechadas:** escopo = **professor da OFERTA** (`turma_curso.professor_id`, sem herdar o professor da turma — regra PARTE B/G1); oferta **encerrada bloqueia** o lançamento do professor; “Parcial” era engano — a etapa é **PERCURSO** e a UI mostra “Percurso”; “Situação Final do Aluno” e “Encerrar conselho” = **ocultos + 403**.
- **Já existia (reaproveitado):** painel por oferta (`ofertas_do_painel_conselho`), lançamento/criação de `ConselhoClasse` por (oferta, aluno, etapa), avaliação coletiva da oferta (`avaliar_turma` → `TurmaCurso.avaliacao_*`) e `alternar_conselho` já 403 para professor. **Sem migration.**
- **Mudanças:** sidebar (`base.html`; `partials/sidebar.html` era legado e ficou alinhado — **removido em 29/10/2026 na T3, menu único**, ver seção da T3 e MER §8.19), `painel.html` (sem fechamento/encerrar; “Lançar Percurso”), `conselho.py` (`_resolver_oferta_conselho(..., professor_id)`, `_escopo_professor`, `_guarda_oferta_explicita_do_professor`, `_bloqueio_oferta_encerrada`; lista de turmas por oferta; 403 em fechamento/`salvar_fechamento_data`; escopo na avaliação) e `services/turma_curso.py` (filtro do painel via `condicao_professor_da_oferta`).
- **Brechas fechadas:** `salvar_conselho` não tinha guarda de dono; `fechamento_turma`/`salvar_fechamento_data` não tinham role guard (URL direta alcançava a tela).
- **Testes:** `tests/test_conselho_professor.py` (**15**) — menu, escopo nos dois sentidos (sem herança), 403 em oferta alheia/turma sem oferta, gravação na própria oferta, oferta encerrada (GET sem criar + POST sem gravar), fechamento 403 (GET/JSON), avaliação da oferta e admin sem regressão. **Nenhum teste existente alterado.**
- **Suíte:** 981 → **996** (+15); resultado **994 passed + 2 failed** — as duas falhas eram do `dashboard/professor.html` (edição não commitada de terceiros, `aulas_pendentes[:5] → [:2]`), não desta entrega. **Resolvido depois, no commit `e5428c2`** (ver a seção do painel do professor em 29/10/2026): a suíte voltou a **996 passed, 0 failed**.
- **Ensaio (`pautaon_ensaio`, desfeito):** professora Rosana Antunes (id 88), oferta 15 / turma 11 — painel lista a oferta dela e esconde gestão/fechamento; lançamento abre com o 1º aluno; POST grava 1 resposta; fechamento, salvar-fechamento e perguntas 403; limpeza conferida (0 respostas `[ENSAIO]`, conselhos de volta ao estado anterior). Principal intocado.

### Alterações do dia — 29/10/2026 (Certificado — modelo (imagem) por centro de custo do período: fase 1, upload)

- **Pedido:** permitir subir o modelo do certificado para **cada centro de custo de um período letivo** (turmas de centros diferentes têm layouts próprios); decidir o melhor local do upload; o texto do certificado entra depois (nome, curso, C.H. total e frase de aprovado/reprovado).
- **Decisões fechadas com o usuário:** imagem **PNG/JPG** (não PDF); **um modelo por (período, centro)** — substituir apaga o anterior; toda oferta está ligada a um centro na vida real (sem “modelo padrão do período” nem fallback extra); upload pelos mesmos papéis de Períodos (**professor fora**); limite **5 MB** e **sem SVG**; o app injeta o texto sobre o modelo (posições fixas no CSS, como hoje).
- **Local escolhido:** seção **“Modelos de certificado”** na própria página **Certificados do período** (`periodos/certificado.html`) — o modelo é do par (período, centro) e a página já é do período. O modal de CRUD do centro de custo **não** foi usado: ele é o catálogo da **unidade**, transversal aos períodos (exigiria escolher o período dentro do modal).
- **Modelo de dados:** tabela nova `modelo_certificado` (MER §7.4b) com UNIQUE `(periodo_letivo_id, centro_custo_id)`, `arquivo`, `nome_original`, `tipo`, `tamanho`; migration `e1f2a3b4c5d6` (**aplicada no ensaio e, em 29/10/2026, no principal**: backup `instance/backups/pautaon_pre_modelo_certificado.sql`, 36 tabelas/2947 linhas idênticas antes e depois, `\d` conferido e `downgrade` + `upgrade` reaplicados). Arquivos fora do `static`, em `UPLOAD_FOLDER/certificados/<periodo>/`, nome `p<periodo>_c<centro>_<epoch>_<uuid6>.<ext>`.
- **Serviço/rotas:** `app/services/certificado_modelo.py` (`centros_do_periodo`, `salvar_modelo`, `remover_modelo`, `caminho_modelo`) e, em `app/registros/periodos.py`, `enviar_modelo_certificado` (POST), `remover_modelo_certificado` (POST) e `arquivo_modelo_certificado` (GET, inline e `?download=1`). Guardas: `_ROLES_PERIODO` + `assert_unidade_context` para não-admin; centro de outra unidade → 404. Em 29/10/2026 `gerencia` foi incluída em `_ROLES_PERIODO` (decisão do usuário — ver desvio resolvido abaixo).
- **Centros listados:** nomes do CSV `periodo_letivo.centro_custo` resolvidos contra o catálogo da unidade do período; três selos: `fora do catálogo` (sem upload até cadastrar), `fora do período` (modelo de centro que saiu do CSV continua listado/removível) e `inativo` (centro do catálogo inativado).
- **Robustez:** substituir apaga o arquivo anterior; se a remoção falhar (arquivo em uso no Windows), fica log + auto-reparo na próxima gravação/remoção do mesmo par.
- **A emissão do certificado NÃO mudou:** o layout impresso continua o atual. Fase 2 = usar o modelo como fundo e injetar nome/curso/C.H./situação (texto ainda não definido pela instituição).
- **Testes:** `tests/test_certificado_modelo.py` (**24** após o ajuste da gerência: upload/linha/arquivo, substituição apagando o anterior, remoção, PDF recusado, arquivo ausente, limite de 5 MB, 403 para professor, 200/302 para admin/pedagógico/secretaria/gerência, isolamento de unidade (403 para pedagógico e gerência de outra unidade), centro de outra unidade, isolamento entre períodos, preview e download autenticados, 404 sem modelo, página listando os centros do período, modelo enviado, período sem centros, fora do catálogo, inativo e fora do período). Suíte fase 1: **958 → 981 passed**.
- **Ensaio (`pautaon_ensaio`, desfeito):** período `[ROTEIRO] Periodo Vigente` (id 22) + centro `[ROTEIRO] Centro Padrao` (id 10); o CSV do período nasce NULL na semente e foi preenchido **só para o ensaio** (setup por SQL), restaurado ao final. Login `secretaria.m1` (302) → página com a seção e o centro; upload PNG (302, linha `image/png` 70 bytes) → GET do arquivo devolve os mesmos bytes; download como anexo com o nome original; página passa a `Substituir/Baixar/Remover`; substituição por JPG troca a linha e **apaga** o PNG anterior; PDF → flash “Formato inválido” e linha inalterada; remoção → 0 linhas e pasta vazia (levou junto a sobra do ensaio anterior). Banco principal intocado.
- **Desvio registrado — RESOLVIDO em 29/10/2026:** `_ROLES_PERIODO` **não** incluía `gerencia` (a página de Certificados já era assim); o upload seguia a página (professor e gerência 403). **Decisão do usuário:** `gerencia` incluída em `_ROLES_PERIODO` — gerência passa a acessar a página de Certificados, as 3 rotas de modelo de certificado e (efeito colateral da constante compartilhada) novo/editar/ativar/inativar período e o calendário do período; `assert_unidade_context` mantido (gerência de outra unidade 403) e professor continua 403. Testes ajustados: `test_perfis_sem_acesso_nao_enviam` perdeu `gerencia` do parametrize (antes 403, agora 302 — decisão do usuário), `test_perfis_de_periodos_enviam` ganhou `gerencia` e `test_outra_unidade_recebe_403` foi parametrizado com `gerencia_b` (23 → **24** no arquivo).
- Docs: MER §7.4b e §8.15; relatório `docs/Relatórios/CertificadoModeloPorCentro.md`.

### Alterações do dia — 29/10/2026 (T2 — seletor "Data da Aula" filtrado pelo calendário da oferta escolhida)

- **Pedido:** em `GET /frequencia`, com **uma oferta selecionada**, o seletor "Data da Aula" lista **só** as datas do calendário da oferta até hoje (vigência + grade, feriados/dias bloqueados descontados). Sem oferta escolhida em 2+ e turma sem oferta ativa (legado): comportamento atual inalterado (união, sem marcas). `data`-URL fora do calendário da oferta escolhida (troca de oferta) → cair na **data mais recente** da oferta, sem erro. Manter marcas ✔/○, resumo `X de Y · Z` e botão "próxima pendente" (V3a), com Z igual às pendências do dashboard. POST `/frequencia`: não alterar a gravação.
- **Implementação (só no GET; POST intocado):** em `app/registros/core.py`, dentro do bloco `if turma_id:`, quando `oferta_atual is not None and not exigir_escolha`, `ctx['datas']` é substituído por `datas_aula_oferta(oferta_atual, limite=hoje, blocked=_blocked_dates_str(turma))` (a **mesma fonte** de `situacao_datas_oferta`, então marcas/resumo/Z ficam coerentes com o dashboard por construção) e `ctx['meses']` recomposto por `_meses_disponiveis` (helper novo); `data` fora do calendário cai na mais recente. Filtro em memória (grade já em `selectin`), sem consulta por data. **Nenhuma linha do POST foi tocada** — a validação de calendário continua contra a união da turma (superconjunto do calendário de qualquer oferta), logo a data postada segue aceita.
- **Testes:** `tests/test_seletor_data_oferta.py` (**5**, reaproveitam a semente de 2 ofertas de dias disjuntos de `test_v3a_datas_lancadas`): seletor com O1/O2 lista só as datas da escolhida; troca de oferta com data inválida cai na mais recente; sem oferta escolhida segue com a união, sem marcas; marcas+resumo preservados com o filtro; nº de SELECTs constante com vigência maior. **Nenhum teste existente precisou ser ajustado** — a V3a já ancorava as marcas no calendário da oferta; só a **lista de opções** mudou. Suíte completa: **1001 → 1006 passed** (baseline da sessão 1000 antes da T1; T1 +1, T2 +5). Numa primeira rodada a suíte marcou **1 failed** em `test_relatorios_observacoes.py::test_painel_pedagogico_tem_o_botao` — **não é desta entrega nem flake**: era uma **edição de terceiros em andamento** no working tree (o renome "Diário de Observações" → "Diário de Bordo" nos templates e nos testes), que se completou minutos depois; a rodada seguinte ficou **1006 passed, 0 failed**.
- **P6 ensaio (`pautaon_ensaio`, semente M1, **read-only — nada a desfazer**):** turma 31, ofertas 45 (seg/qua) × 46 (ter/qui), professor 120, hoje 29/10, pelas rotas reais via test client — sem escolha → união sem marcas; `?turma_curso=45` → só seg/qua (nenhuma de ter/qui); `?turma_curso=46` → só ter/qui; `?turma_curso=45&data=<qui de 46>` → 200, `selected` cai em `2026-10-28`. POST não enviado (para não escrever); datas de 45/46 confirmadas subconjunto da união. Banco principal intocado.
- **Retrato da V3a (abaixo):** o bullet "a lista de datas é da TURMA / nenhuma data removida" vale apenas para os casos **sem oferta escolhida** e legado; **com oferta escolhida**, a T2 passou a filtrar pelo calendário da oferta.
- Docs: MER §8.14 (bullet da lista de datas); relatório `docs/Relatórios/SeletorDataPorOferta.md`.

### Alterações do dia — 29/10/2026 (T3 — menu único: removido o partial legado `partials/sidebar.html`)

- **Pedido:** resolver a pendência antiga de "dois menus" — remover `app/templates/partials/sidebar.html`, confirmar por grep que nada o inclui/referencia e marcar as pendências "partial legado" como resolvidas. **Sem migration, sem alterar o comportamento do menu por perfil.**
- **P1 (leitura/grep):** o partial **não era incluído nem estendido por nenhum template** (`{% include %}`/`{% extends %}` sobre `partials/` só aparece em `partials/_modal_agendamento.html` → `partials/_campos_agendamento.html` e nos dois painéis que incluem o modal), **não era renderizado por nenhuma rota** e **não era referenciado por nenhum teste**. As **9 ocorrências do nome** eram todas em documentação: MER §8.16, `backlog_desenvolvimento.md`, `ConselhoProfessor.md` (§Menu e §Pendências), `PainelProfessorRotaUnificada.md`, `PainelProfessorRotaVoltar.md`, `M1_RoteiroTesteManual.md` (2×) e `D5_0_desenho.md` (1×). O menu real é o bloco inline de `base.html` (`<aside class="app-sidebar" id="appSidebar">` + `css/sidebar.css` + JS do `toggleSidebar`), que **não foi tocado**.
- **Implementação:** apagado `app/templates/partials/sidebar.html` (155 linhas). Docs: as pendências "partial legado" marcadas como **resolvidas** (MER §8.16 + seção nova **§8.19**, §Menu e §Pendências do `ConselhoProfessor.md`, pendências do `PainelProfessorRotaUnificada.md` e do `PainelProfessorRotaVoltar.md`); `M1_RoteiroTesteManual.md` passou a apontar o seletor de unidade para `base.html` (é lá que ele vive). **`D5_0_desenho.md` mantém a linha do inventário original** — é snapshot de desenho da fase D5, não pendência; reportado aqui.
- **Testes:** `test_conselho_professor.py::test_sidebar_professor_ve_painel_e_nao_ve_itens_restritos` **não** precisa de ajuste — o nome menciona a sidebar, mas o teste lê o corpo de `GET /conselho` (o menu de `base.html`), que nunca veio do partial. Rodados antes e depois, verdes e **sem alteração**: `test_conselho_professor` (15), `test_l4_2_harness_perfis`, `test_conselho_ui`, `test_dashboard_professor_pedagogico` — **28 passed** na linha de base e **28 passed** depois da remoção. Suíte completa: **1006 passed, 0 failed** (nenhum teste a menos, nenhum a mais).
- **Ensaio:** dispensado — mudança de arquivo morto, sem rota/consulta nova; a verificação é a suíte e o grep.
- Docs: MER §8.19 (e §8.16 riscado); relatório `docs/Relatórios/MenuUnicoSidebarLegado.md`.
- **Relatório único das três tarefas da sessão (T1 gerência · T2 seletor · T3 menu), com os gates e as pendências restantes:** `docs/Relatórios/Entrega_T1_T2_T3_29-10-2026.md`.

### Alterações do dia — 29/10/2026 (V3a — datas já lançadas na pauta + botão Imprimir coerente)

- **Pedido:** ver de relance, no seletor "Data da Aula", quais datas já foram lançadas e quais estão pendentes, com resumo e atalho para a próxima pendente; e só mostrar o botão Imprimir quando a impressão é permitida.
- **P1 (leitura) e DIVERGÊNCIAS do enunciado (registradas, não corrigidas):** (a) o seletor **não** lista datas futuras — `carregar_contexto_turma` chama `gerar_datas(turma, incluir_futuro=False)`, que corta em `min(data_fim, hoje)`; logo não existe o estado "futura sem marca" nem "futura já lançada" na tela (a regra foi implementada genericamente e o estado nunca ocorre); (b) a lista de datas é da **TURMA** (`dias_da_turma` = **união** dos dias das ofertas ativas), não da oferta — com 2+ ofertas o seletor mostra datas das duas, e só as que pertencem ao calendário da oferta recebem marca. Nada foi alterado no seletor além das marcas (R1: nenhuma data removida).
- **Definição de "lançada" (R3):** a mesma das pendências do dashboard — `frequencias_lancadas` / `_pendencias_por_ofertas` (`utils/frequencia.py`): data lançada quando **todos** os alunos da pauta da oferta (`_alunos_da_oferta`) têm conceito; legado **D2** (`ofertas_unicas_ativas`) incluído. Aluno sem conceito deixa a data **pendente**; a pauta só grava o que o usuário marcar, então não há divergência entre "salvo na pauta" e a regra do dashboard (todos os alunos da pauta podem receber frequência — `pode_receber_frequencia` é `insc.ativo` da própria oferta).
- **Implementação:** `utils/frequencia.py::situacao_datas_oferta(turma, oferta)` → `{status, lancadas, total_ate_hoje, pendentes, proxima_pendente}`, **uma** consulta agregada por oferta (`GROUP BY data`, `count(distinct aluno)`), sem N+1; `GET /frequencia` monta `situacao_datas`, `dias_abrev` (`weekday_para_abrev`) e `pode_imprimir_pauta`; `lancar.html` marca `✔ dd/mm/aaaa (Dia)` / `○ dd/mm/aaaa (Dia) — pendente`, mostra "X de Y aulas até hoje lançadas · Z pendente(s)" (ou "Todas as aulas até hoje estão lançadas ✔") e o botão "Ir para a próxima pendente" (mesma navegação GET do seletor, some com Z = 0). Sem oferta escolhida em 2+ ofertas: sem marcas e sem resumo.
- **Parte B (commit próprio):** `pode_imprimir_pauta` oculta o bloco Imprimir com 2+ ofertas e nenhuma escolhida (todos os perfis) e, para PROFESSOR, quando ele não é o professor cadastrado da oferta escolhida ou a turma não tem oferta ativa — reutilizando `professor_da_oferta`, sem regra nova. Os links do dropdown já levam `turma_curso` sempre que há oferta. **`turmas/detalhe.html` não foi alterado (R11):** com 2+ ofertas cada link leva a oferta correspondente e o professor recebe 403 nas que não são dele; com 0/1 oferta o link vai sem `turma_curso`, cai na oferta de menor id e também dá 403 quando não é dele.
- **Testes:** `tests/test_v3a_datas_lancadas.py` (**12**: ✔/○/futura, pendente com um aluno sem conceito, Z = 0 com a mensagem, ofertas independentes, D2 com 1 e com 2+ ofertas, Z igual às pendências do dashboard, SELECTs constantes com 2 e 10+ datas, HTML com marcas/resumo/botão, sem oferta escolhida sem marcas, ✔ após POST de salvar, demais campos preservados) e `tests/test_v3a_imprimir_coerente.py` (**5**: visível para o professor da oferta, oculto para outro professor, oculto sem escolha em 2+ ofertas para prof/admin/secretaria, visível para admin/pedagógico/secretaria, oculto em turma sem oferta ativa). **Um teste existente ajustado:** `test_lancar_template_estrutura.py::test_render_nao_perde_textos` — antigo `"Este conteúdo será arquivado no diário de classe"` × novo `"O conteúdo de atividades e observações será arquivado"` × motivo: o `cbbe75a` (reorganização do layout, do próprio repositório) reescreveu o aviso e deixou a suíte vermelha **antes** desta tarefa (commit `5b47bb4`). Suíte: **940 passed + 1 failed em HEAD (falha do `cbbe75a`) → 941 com o fix → 958 passed**.
- **P6 ensaio (`pautaon_ensaio`, desfeito):** semente M1 (turma 31, professor 120). Oferta 45 (seg/qua): pauta 2, 26 aulas até hoje, 2 lançadas, 24 pendentes, ✔ 03/08 e 10/08, ○ 05/08, 12/08, 17/08 (17/08 com só 1 dos 2 alunos); oferta 46 (ter/qui): 1 lançada, 25 pendentes, ✔ 04/08. SQL independente idêntico. Sem oferta escolhida: sem marcas, sem resumo e **sem** botão Imprimir. `POST /frequencia` em 05/08 → a data passa a `✔ 05/08/2026 (Qua)` e o resumo a `3 de 26 · 23 pendente(s)` (SQL: 3). Limpeza: frequências e `registro_aula` da data apagados (turma 31 voltou a 8 linhas); restaram apenas 2 linhas de `log_acao` do próprio acesso/salvamento (log de auditoria não é apagado). Banco principal intocado.
- Docs: MER §8.14; relatório `docs/Relatórios/V3a_DatasLancadas.md`.

### Alterações do dia — 28/10/2026 (V3b — "Engajamento da turma" no Painel Pedagógico do professor)

- **Pedido:** os 3 valores/posturas do esportista mais atribuídos na oferta escolhida no filtro, logo abaixo do gráfico "Evolução de Assiduidade Aula a Aula".
- **P1 (leitura):** o painel é `main.painel_pedagogico_professor` → `render_painel_pedagogico_professor` → `estatisticas_professor.obter_estatisticas_professor` → `dashboard/painel_pedagogico.html`. A aba "Painel Pedagógico" é uma **página própria** (`dashboard/professor.html` é a aba "Visão Geral"), então o bloco entrou em `painel_pedagogico.html` (desvio de caminho registrado no relatório). O filtro `<select name="turma_selecionada">` chama `navegarTurma()` → **GET** `?turma_id=&turma_curso=`; o gráfico usa Chart.js (CDN) alimentado por `{{ evolucao_temporal|tojson }}`.
- **TRAVAs:** (a) **não existe** opção "Todas"/sem oferta: as opções são as entradas do professor e a rota cai em `entradas[0]` quando o parâmetro não casa — nada a perguntar; (b) a rota serve `professor`, `admin`, `gerencia` e `pedagogico` — **guarda atual mantida**, permissões intocadas.
- **Decisão AJAX × GET:** **GET** (o filtro já recarrega a página) — bloco renderizado no servidor, sem endpoint JSON e sem JS novo.
- **Implementação:** `app/services/engajamento_turma.py::valores_mais_atribuidos(turma_id, turma_curso_id, limite=3)` → `{"itens": [{nome, quantidade, percentual}], "total"}` — uma consulta agregada (`GROUP BY valor`), sem N+1 e sem dado por aluno; empate pelo nome; valor inativo já usado conta; percentual sobre o total da oferta; legado **D2** reutilizando `ofertas_unicas_ativas` (linhas `turma_curso_id` NULL só entram na oferta única ativa). Rota: calcula o bloco a partir de `stats["entrada_selecionada"]`. Template: card `#engajamento-turma` entre o gráfico e a tabela de alunos.
- **Testes:** `tests/test_v3b_engajamento_turma.py` (**18**: ordenação, empate, menos de 3, nenhum, percentual com 5 valores, oferta A × B, D2 com 1 e com 2+ ofertas, valor inativo, SELECTs constantes com 2 e 8 valores, posição no HTML, estado vazio, rodapé, escape de `<b>`, nenhum nome de aluno no bloco, troca com o filtro, oferta de outro professor, outra unidade). **Nenhum teste existente alterado.** Suíte: **923 → 941 passed**.
- **P5 ensaio (`pautaon_ensaio`, desfeito):** 3 valores criados por `/planejamento` (secretaria.m1) e frequência lançada por `POST /frequencia` (professor.m1) nas ofertas **45 (B1)** e **46 (B2)** da turma 31, em datas sem nenhum registro. Bloco por HTTP: B1 → `[V3b] Colaboração 2 (66.7%)`, `[V3b] Respeito 1 (33.3%)`, total 3; B2 → `[V3b] Empatia 2 (100.0%)`, total 2; oferta 44 (sem valores) → mensagem de vazio. Contagem SQL independente idêntica. Limpeza: frequências, registros de aula criados e valores removidos — contadores voltaram ao estado anterior (freq com valor `[]`, 2 aulas, 0 valores). Banco principal intocado.
- Docs: MER §8.13; relatório `docs/Relatórios/V3b_EngajamentoTurma.md`.

### Alterações do dia — 28/10/2026 (G1 — professor obrigatório na oferta: TRAVA no P1; acesso por oferta concluído)

- **P1a (leitura):** principal — 6 ofertas ativas, **4 sem professor** (ofertas 16/17 da turma 12, 18 da turma 13, 19 da turma 14), **0** delas com professor da turma preenchido, 0 com professor ≠ da turma, 0 inativas sem professor. Ensaio — 10 ativas, **1 sem professor** (oferta 50/turma 34), 0 com professor da turma, 2 com professor ≠ da turma. **Todas as ofertas sem professor estão em turmas também sem professor.**
- **TRAVA disparada (P1c):** a obrigatoriedade (**PARTE A / P2**) **NÃO foi aplicada** — serviço, formulários e templates de oferta/turma intactos. Proposta entregue como script com dry-run: `scripts/saneamento_professor_oferta.py` (copia `turma.professor_id` só quando a turma tem professor da mesma unidade; lista o resto; `--aplicar` recusado fora de banco de ensaio sem `--autorizar-principal`; DSN do `.env` com o nome do banco trocado, sem tocar `DATABASE_URL`). Execuções: principal dry-run → 4 pendentes, 0 copiáveis; ensaio dry-run → 1 pendente; ensaio `--aplicar` → “nada a aplicar”; principal `--aplicar` → **RECUSADO** (exit 2).
- **P1b:** a oferta nasce **sem** garantia de professor — `criar_oferta_inicial_da_turma` copia `turma.professor_id` (que pode ser NULL; `nova_turma.html` nem tem campo de professor), `adicionar_oferta` aceita vazio (herda da turma só sem curso legado), `editar_oferta` aceita NULL, e os selects de `ofertas.html`/`editar.html` têm “-- Sem professor --” sem `required`.
- **P3 aplicado (acesso por OFERTA):** a guarda por oferta já vinha da PARTE B; o G1 mudou só a resolução **sem `turma_curso`** — 1 oferta ativa → ela; 2+ → a de **menor id**; se não for dele → 403 (antes: caía na oferta dele). A oferta `principal` **não decide acesso** (R2). I1 usa a mesma expressão (`condicao_professor_da_oferta`), sem COALESCE.
- **P1d:** a interface gera link de impressão **sem** `turma_curso` em `frequencia/lancar.html:24,35` (2+ ofertas e nenhuma escolhida) e `turmas/detalhe.html:53,63` (só com 0/1 oferta ativa); com 2+ ofertas o menu do detalhe passa o parâmetro.
- **Testes:** `tests/test_pauta_impressa_por_oferta.py` com **19** (2 ajustados pela regra nova do P3: antigo × novo × motivo no relatório; 4 novos: principal irrelevante, secretaria/pedagógico, outra unidade, período encerrado no I1). **Nenhum outro teste alterado.** Suíte: **919 → 923 passed**.
- **P5:** conferência por HTTP em modo leitura no ensaio (200 na oferta dele com e sem parâmetro; 403 em oferta de outro professor e em oferta sem professor). A parte de escrita (recusa ao criar/editar sem professor) depende do P2. Docs: MER §7.32 (professor da oferta e R2 — ainda nullable), §8.10 e §8.12; relatório `docs/Relatórios/G1_ProfessorDaOferta.md`.

### Alterações do dia — 28/10/2026 (PARTE B — pauta impressa e I1 por OFERTA, sem herança de turma)

- **Decisão (fechada):** "professor da oferta" = **somente** `turma_curso.professor_id == usuário`. A turma é um agregador de ofertas: `turma.professor_id` **não** dá acesso à pauta impressa nem aos dados do aluno (I1). Admin/pedagógico/secretaria (com isolamento por unidade) e o resto das regras: inalterados.
- **P0-B (leitura, principal e ensaio):** principal — 6 ofertas ativas, 4 sem professor, **0** delas com professor da turma preenchido, 0 com professor ≠ da turma, 2 com professor == da turma. Ensaio — 10 ativas, 1 sem professor (turma também sem professor), **2** com professor ≠ do da turma (ofertas 12 e 13 da turma 9, professores 88/89 × turma 93), 7 iguais. **TRAVA não disparou:** nenhuma oferta ativa sem professor tem professor de turma hoje imprimindo/ vendo por herança. No ensaio, as ofertas 12/13 perdem o acesso do professor 93 — comportamento-alvo (ele não é o professor cadastrado delas).
- **Formulário/serviço de oferta:** o professor da oferta é **opcional** (`_validar_professor` devolve `None` sem id). A oferta inicial da turma copia `turma.professor_id` (`criar_oferta_inicial_da_turma`), `adicionar_oferta` herda da turma só quando a turma não tem curso legado, e `editar_turma` propaga o professor para a **oferta única**; `editar_oferta` pode limpar o professor.
- **Pauta impressa (`imprimir_pauta`):** guarda por oferta (403 quando não é o professor cadastrado — inclusive sendo o professor da turma, com oferta sem professor ou sem oferta ativa dele). Sem `turma_curso`: principal se for dele, senão a primeira oferta ativa dele; nenhuma → 403. Para PROFESSOR a lista de alunos é **sempre** `_alunos_da_oferta` (mesmo com uma oferta ativa) e a linha "Outras ofertas" não é impressa. Admin/pedagógico/secretaria mantêm o comportamento (inclusive o flash + redirect com 2+ ofertas sem parâmetro).
- **I1:** `_condicoes_acesso` passou a usar `condicao_professor_da_oferta` (só `turma_curso.professor_id`), com o helper Python `professor_da_oferta` para oferta já carregada — uma única regra compartilhada pela impressão e pelo modal/pauta. Inscrição ativa, aluno ativo, oferta/turma ativas, unidade e período não encerrado continuam iguais.
- **Efeitos esperados (registrados):** professor da turma que não leciona nenhuma oferta ativa perde a impressão e o I1; turma sem oferta ativa (modo legado) → 403 para professor; oferta sem professor → só perfis administrativos imprimem.
- **Testes:** `tests/test_pauta_impressa_por_oferta.py` (15: 200 nas duas ofertas, 403 sem herança/oferta de outro/oferta inativa/oferta sem professor, resolução sem parâmetro, alunos só da oferta, "Outras ofertas" oculta para professor e mantida para admin, redirect do admin preservado, I1 sem herança). **Nenhum teste existente alterado.** Suíte: **904 → 919 passed**. Regra em MER §8.12/§8.10; relatório `docs/Relatórios/ParteB_PautaPorOferta.md`.

### Alterações do dia — 28/10/2026 (I1 — Informações do aluno no modal do professor)

- **Pedido:** o professor da oferta ver, na pauta de frequência, um ícone por aluno com "Quem acompanha?" e "Informações para o professor da turma"; a pauta impressa passa a obedecer à mesma regra; nada muda na ficha, na edição dos campos, nos perfis ou nas permissões existentes.
- **Regra ÚNICA de acesso** (`app/services/aluno_info_professor.py`, usada pelo endpoint, pela pauta e pela impressão): inscrição ativa + aluno ativo + oferta ativa + turma ativa + **professor efetivo da oferta** = usuário + turma na unidade do usuário + **período não encerrado** (`data_fim >= hoje` local; período futuro entra, turma sem período não bloqueia). Basta **uma** inscrição qualificada; professor que não leciona mais ao aluno (inclusive período encerrado com inscrição ativa) não vê. Função em lote para a pauta: **uma** consulta, sem N+1. **(29/10 — correção da regra vigente):** à época foi escrita como `coalesce(turma_curso.professor_id, turma.professor_id)`; a regra vigente é **por oferta, sem herança** — `condicao_professor_da_oferta` (`turma_curso.professor_id == usuário`, MER §8.12). Professor da turma sem oferta própria não vê mais; na E3 (G1/P2+I1) o `coalesce` foi removido também dos guardas restantes (ver_turma, ver_observacoes, GET/POST /frequencia, histórico e foto).
- **Endpoint** `GET /aluno/<id>/info-professor`: 403 para quem não é professor ou não tem inscrição qualificada; 404 para aluno inexistente ou sem nenhum bloco preenchido; 200 com `{aluno_id, nome, acompanhante, instrucoes}` (só os blocos preenchidos) e `Cache-Control: no-store`; **sem log de acesso** (decidido). Idade e **medicação** nunca entram.
- **Pauta de frequência:** ícone `bi bi-chat-left-dots-fill` ao lado do nome **só** para PROFESSOR e **só** para aluno com bloco preenchido; o HTML carrega apenas `data-aluno-id` (nenhum texto do aluno) e `static/js/aluno_info_professor.js` abre o modal "Informações para o professor — <nome>" via fetch, renderizando por `textContent` + `white-space: pre-wrap` (sem HTML ativo, quebras preservadas; 403/404/rede com mensagem).
- **Pauta impressa:** para PROFESSOR, as linhas "Quem acompanha" e "Informações para o professor" só saem dos alunos com inscrição qualificada; demais perfis inalterados e **medicação não passa pela regra**. A guarda de acesso da impressão (`turma.professor_id`) não foi alterada.
- **Sem migration:** os campos já existiam (`aluno.acompanhante_aulas` + flag `vai_acompanhado_aulas`; `perfil_diversidade.informacoes_para_professor`). Testes: `tests/test_info_professor.py` (25), `tests/test_info_professor_pauta.py` (6), `tests/test_info_professor_impressao.py` (3) — **nenhum teste existente alterado** (a caracterização da impressão rodou no worktree de HEAD: 2 passed, inclusive o caso do período encerrado que imprimia). Suíte: **870 → 904 passed**. Regra em MER §8.12; relatório `docs/Relatórios/I1_InfoProfessorModal.md`.

### Alterações do dia — 28/10/2026 (Frequência — Valor/Postura obrigatório para presença)

- **Pedido:** não permitir lançar presença (A–D) sem o Valor/Postura do Esportista, sem que a pauta grave nada pela metade; e limpar o template de frequência (card sem `</div>` e cópia morta do template).
- **Regra (servidor):** `salvar_frequencia` (`app/utils/logica.py`) monta o plano de gravação em `_planejar_frequencia` **antes de qualquer escrita**. Havendo A–D sem valor válido, levanta `PendenciaValorEsportista` e **nada** é gravado — nem conceitos, nem `registro_aula` (temas/observações/atividades). A rota `POST /frequencia` flasha `mensagem_valor_obrigatorio` (até 10 nomes + "e mais N") e volta para a mesma turma/data/oferta.
- **Exceção:** unidade da turma sem **nenhum** valor ativo no catálogo (`unidade_tem_valores_ativos`) — a pauta não trava; a tela mostra "Cadastre os valores no Planejamento" só para ADMIN/PEDAGOGICO/SECRETARIA. Valor **inativo já salvo** continua valendo (`valor_atual_id`); inativo novo, inexistente ou de outra unidade conta como ausente. F, J e aluno sem conceito não exigem (F/J seguem limpando; sem conceito preserva a linha). Vale para qualquer data, inclusive histórico reescrito.
- **Cliente:** `lancar.html` marca `required` no select quando o conceito é A–D (com catálogo) e o form leva `data-valor-obrigatorio` só nesse caso; `frequencia.js` bloqueia o submit com `is-invalid` + mensagem (`#aviso-valor-pendente`) e trata o evento `invalid` do `required` nativo.
- **Limpeza:** `frequencia/lancar.html` fechava o card da pauta só no `</form>` (31 × 30 desde antes de `a5b34c8`) — corrigido antes da regra, com teste de estrutura por `HTMLParser`. A cópia `lancar copy.html`, sem nenhuma referência em `app/`, `tests/` ou `scripts/`, já havia sido removida em `2185afe`.
- **Escopo:** sem migration (coluna continua nullable); nada muda em conceito, P/F/J, `estats_freq`, pauta impressa, relatórios, exportações ou permissões. Testes: `tests/test_valor_obrigatorio.py` (26), `tests/test_valor_obrigatorio_ui.py` (12), `tests/test_valor_obrigatorio_caracterizacao.py` (4, antigo × novo), `tests/test_lancar_template_estrutura.py` (2) e ajustes em `test_valor_esportista_lancamento.py` (5) e `test_valor_esportista_nao_regressao.py` (4). Suíte: **826 → 870 passed**. Regra em MER §7.19/§8.1; relatório `docs/Relatórios/V2_ValorObrigatorio.md`.


### Alterações do dia — 28/10/2026 (Diário de Bordo — visão global com filtros)

- **Pedido:** botão no Painel Pedagógico para abrir o diário com filtros por período letivo, turma, curso (oferta) e professor, restrito a quem já acessa o painel.
- **Entrega:** rota `GET /relatorios/observacoes` (`app/relatorios/observacoes.py`, endpoint `relatorios.observacoes`) com `ROLES_RELATORIOS`; template `turmas/observacoes.html` em `modo_global` (filtros encadeados, badge da turma, aviso de limite de 500); botão no painel levando período e turma selecionados. O fluxo `/turma/<id>/observacoes` continua sem filtros.
- **Escopo:** sem migration e sem mudar conteúdo/regra da tela por turma. Testes: `tests/test_relatorios_observacoes.py` (13). Suíte: **813 → 826 passed**. Detalhes em `docs/Relatórios/REL_ObservacoesFiltros.md`; regra em MER §7.20.

### Alterações do dia — 28/10/2026 (Diário de Bordo — acesso e navegação)

- **Problema:** a página `/turma/<id>/observacoes` não tinha nenhum link na interface (só URL manual) e `ver_observacoes` aceitava qualquer professor para qualquer turma — sem vínculo com a turma e sem escopo de unidade.
- **Correção:** a rota passou a aplicar as mesmas guardas de `ver_turma`/`imprimir_pauta` (`Turma.get_or_404` → `assert_unidade_context` → professor só nas próprias turmas); botão de diário no painel do professor (`/painel`) e no detalhe da turma; "Voltar" do diário aponta para `main.painel`.
- **Escopo:** sem migration e sem mudança de conteúdo da listagem. Testes: `tests/test_diario_observacoes_acesso.py` (8). Suíte: **805 → 813 passed**, nenhum teste existente alterado. Detalhes em `docs/Relatórios/DIARIO_ObservacoesAcesso.md`; regra de acesso em MER §7.20.

### Alterações do dia — 28/10/2026 (Frequência — Atividades da aula)

- **Pedido:** novo campo de texto "Atividades da aula" na tela de frequência, igual ao Observações da Aula.
- **Entrega:** `registro_aula.atividades` (TEXT, nullable, migration `c8d9e0f1a2b3`, **aplicada no principal em 28/10/2026** após backup) e segundo textarea no **mesmo card** da coluna direita (`lancar.html`), acima das observações. `salvar_frequencia` grava os dois campos de forma independente; `carregar_frequencias_e_valores` devolve 5 valores e `carregar_frequencias` mantém os 3 atuais.
- **Diário de Bordo:** passou a listar aulas com atividades **ou** observações e a exibir as duas seções. No caminho, corrigido bug pré-existente: `registro.data` é `date` e o template fazia slicing de string (`TypeError` → HTTP 500).
- **Escopo:** nada de frequência, estatísticas, pauta impressa, BI ou relatórios mudou. Testes: `tests/test_atividades_aula.py` (14). Suíte: **791 → 805 passed**, nenhum teste existente alterado. Detalhes em `docs/Relatórios/FREQ_AtividadesDaAula.md`; schema em MER §7.20/§11.

### Alterações do dia — 28/10/2026 (Conselho de Perguntas — etapa/foco preservados)

- **Problema:** em *Conselho → Gerenciar Perguntas*, salvar ou excluir uma pergunta reabria sempre a aba **Inicial + Geral (Turma)**. As abas (3 etapas × 2 focos) viviam só no DOM e as duas rotas de escrita redirecionavam para a rota limpa.
- **Solução (mesmo padrão do Planejamento):** `?etapa=inicial|percurso|final&foco=turma|aluno` na querystring; helpers `_aba_pergunta_etapa()`/`_aba_pergunta_foco()`/`_voltar_perguntas()` em `app/conselho.py` (whitelist); `gerenciar_perguntas` calcula `etapa_ativa`/`foco_ativo` e `perguntas.html` marca abas/pills/painéis. **Salvar** volta para a aba da pergunta gravada (etapa + foco escolhidos no modal); **excluir** volta para a aba de origem via hidden `aba_etapa`/`aba_foco`. Sem JS, sem sessão e sem fragmento; `GET /conselho/perguntas` sem parâmetro continua em Inicial/Turma.
- **Escopo:** nenhuma permissão, CSRF, modelo ou regra mudou. Testes: `tests/test_conselho_perguntas_abas.py` (8). Suíte: **783 → 791 passed**, nenhum teste existente alterado. Padrão documentado em MER §9.3 e em `docs/Relatórios/UI_AbasPersistentes.md`.

### Alterações do dia — 28/10/2026 (Planejamento — aba ativa após salvar)

- **Problema:** toda escrita no Planejamento (criar/editar/inativar tema, nível ou valor) recarregava a página na aba **Temas**. As pills do Bootstrap viviam só no DOM e as 11 saídas de escrita faziam `redirect(url_for('registros.planejamento'))`, com o template marcando Temas como ativa de forma fixa.
- **Solução (A — querystring + servidor):** helper `_voltar_planejamento()` em `app/registros/core.py` lê o hidden `aba` (`temas|valores|niveis`, whitelist) e o contexto da lista (`filtro_curso`, `filtro_q`, `filtro_page`) e devolve `/planejamento?aba=...`; `GET /planejamento` calcula `aba_ativa` (default `temas`) e `planejamento.html` marca pill/painel ativos. Os 9 formulários ganham o hidden `aba`; os 3 formulários da aba Temas carregam também os filtros da lista. Sem JS adicional, sem sessão e sem fragmento.
- **Escopo:** nenhuma rota, permissão, CSRF ou regra mudou; `GET /planejamento` sem parâmetro continua abrindo Temas. Testes: `tests/test_planejamento_abas.py` (10). Suíte: **773 → 783 passed**, nenhum teste existente alterado. Convenção registrada em MER §9.3; detalhes em `docs/Relatórios/A1_ValoresDoEsportista.md` (§9).

### Alterações do dia — 28/10/2026 (A1 — Valores do Esportista)

- **Cadastro no planejamento:** nova aba **Valores do Esportista** em `planejamento/planejamento.html` (pill `#pill-valores` → `#tabValores` dentro do `.tab-content`, KPI em `col-6 col-xl-3`), gerenciada pelos mesmos perfis de temas/níveis. Rotas no blueprint `registros`: `planejamento` (POST `tipo_post="valor"`, campo `nome_valor`), `editar_valor` e `inativar_valor` (toggle ativo/inativo — **nunca** apaga). Escopo por unidade: nome único por unidade sem diferenciar maiúsculas (`uix_valor_esportista_nome_unidade` em `lower(nome)`+`unidade_id`, com validação prévia em `func.lower` e mensagem amigável); Visão Global não escreve.
- **Lançamento na pauta:** `frequencia/lancar.html` ganha o select `postura_aluno_<id>` por aluno, populado com `valores_esportista_ativos` no escopo da unidade da turma; fica `disabled` fora de A/B/C/D, para aluno transferido e no modo visualização (secretaria). `tratarConceitoAluno` (agora em `static/js/frequencia.js`, com estado inicial no `DOMContentLoaded`) habilita/limpa o select ao trocar o conceito. Valor inativo já lançado é reexibido como opção extra `(inativo)`.
- **Regra crítica:** o valor é **dado adicional** — não entra em conceito, presença, falta, justificadas, `total_aulas`, `estats_freq`, pauta impressa, diário, relatório ou exportação. Só é gravado com conceito A–D; F/J/vazio/sem frequência gravam `NULL`; campo ausente (`select` desabilitado) não altera a linha; valor inexistente/de outra unidade/inativo (que não era o salvo) é ignorado sem derrubar o restante da pauta.
- **Banco:** tabela `valor_esportista` e coluna `frequencia.valor_esportista_id` (FK `ON DELETE SET NULL`, índice), **sem backfill** — registros anteriores ficam `NULL`. Migration `b7c8d9e0f1a2` (head novo), reversível: o downgrade remove índice/FK/coluna e a tabela, preservando todas as linhas de `frequencia`. Leitura do valor usa a **mesma** consulta de `frequencia` (`carregar_frequencias_e_valores` com `joinedload`), mantendo a contagem de consultas da pauta (teste de N+1 do D3b-2.4 segue passando sem ajuste).
- **Testes:** 38 novos — `tests/test_valor_esportista.py` (10: cadastro, permissões, CSRF real, isolamento por unidade, renderização da aba/KPI), `tests/test_valor_esportista_lancamento.py` (19: persistência A–D, limpeza em F/J, rejeições, inativo salvo, `is_readonly`, transferido, duas ofertas, estado do `select`), `tests/test_valor_esportista_nao_regressao.py` (4: pauta completa e do mês, relatório de frequência e XLSX idênticos com/sem valor, registro antigo `NULL`) e `tests/test_valor_esportista_migration.py` (5: upgrade/downgrade com dados, unicidade sem case, reaplicação e DDL do PostgreSQL via `MockEngine`). **Nenhum teste existente foi alterado.**
- **Estado da suíte ao final de A1-Valores: 773 passed**, 0 falhas (735 + 38); head `b7c8d9e0f1a2`; sem push. Regras em MER §7.5a, §7.19 e §8.1; relatório `docs/Relatórios/A1_ValoresDoEsportista.md`.

### Alterações do dia — 28/10/2026 (A1 — achados 1, 2 e 3 do M1 corrigidos)

- **A1-1 — histórico aplica a regra D2 do legado (`45a1312`):** `frequencias_aluno_por_inscricao` (`app/services/frequencia_oferta.py`) lia **exatamente** (`turma_id`, `turma_curso_id`) e mostrava 0,0% na inscrição de turma cuja frequência estava no legado NULL, enquanto a listagem mostrava 75,0%. Passa a usar a mesma regra D2 de `agregar_por_oferta` (helper `ofertas_unicas_ativas`): o legado entra **só** na oferta única ativa da turma, não entra em turma com 2+ ofertas ativas (ou sem oferta ativa) e o par legado `(turma, None)` continua lendo só NULL. Continua **uma** consulta agregada de frequência (sem N+1) e o resultado não carrega mais objetos ORM da tabela `frequencia`. Sem migration; regra em MER §8.1.
- **A1-2 — `I: None` no histórico (`1a9bfda`):** o dicionário da tela montava `status_inicial` como `c_inicial.situacao_final if c_inicial else "—"`; conselho existente com `situacao_final` NULL (lançamento aberto, estado da semente M1) imprimia "None". Inicial, percurso e final passam a cair em "—" também nesse caso (mesmo contrato das demais telas) e o bloco `I/P` some quando ambos são ausentes.
- **A1-3 — BI e turma excluída logicamente (`71e5991`):** `_base_frequencia` e `_base_registro_aula` (`app/relatorios/bi_alunos.py`) somavam lançamentos de `Turma.ativo = False`, divergindo de Resumo, `FRE-009`, `FRE-010` e painel pedagógico (que já filtram). As duas bases passam a fazer **um** join em `turma` com `turma.ativo IS TRUE`; afetados `FRE-001`–`FRE-008`, `CRU-001` e `AUL-001/002/003/006/007/008`. No ensaio, `FRE-005` passa de **64,7%** (11P/6F, somando a turma na lixeira) para **60,0%** (9P/6F). Nenhum outro critério mudou; filtro explícito por turma excluída devolve 0. Regra em MER §8.10.
- **A1-4/A1-5 — somente leitura:** "Alunos enturmados 6 × 7 novos" e filtro *Programa* pela oferta secundária foram mapeados e ficaram em **Pendências abertas** com a proposta de correção (sem alteração de código).
- **Testes:** 13 novos em `tests/test_a1_historico_legado_d2.py` (6), `tests/test_a1_historico_status_ausente.py` (1) e `tests/test_a1_bi_turma_ativa.py` (6); **nenhum teste existente precisou ser ajustado** (o de equivalência do D3b-2.3 usa turma de 2 ofertas, onde a D2 não muda nada, e o de N+1 continua vendo 1 consulta em `frequencia`). Relatório `docs/Relatórios/A1_AchadosM1.md`.
- **Estado da suíte ao final de A1: 735 passed**, 0 falhas (722 + 13); head `8d2e3f4a5b6c` (sem migration); sem push.

### Alterações do dia — 28/10/2026 (M1 — roteiro de teste manual + semente do scratch)

- **M1 — roteiro manual (`docs/Roteiro_Teste_Manual.md`):** 93 casos em 10 blocos (login/unidade/Visão Global, CSRF real, agenda por dia H4c/H4d, frequência por oferta D3b-2.4, listagem/`min_freq` D3b-2.5, conselho PQ1–PQ4, lixeira/reativação L4/L4.1/L4.2, histórico/ficha/certificado/relatório/BI, matriz de permissões, impressões/exportações). Cada bloco indica os testes automatizados que cobrem o mesmo comportamento e o que é cobertura nova. Todas as rotas, botões e textos foram conferidos nos templates.
- **M1 — semente (`scripts/semear_roteiro_manual.py`):** idempotente (duas execuções → mesmas contagens do rótulo), recusa banco sem "ensaio" no nome, `--limpar` remove só o rótulo `[ROTEIRO]`. Cria unidade + vizinha, 5 perfis (senha `Roteiro!2026`), 1 período vigente + 1 encerrado, 4 cursos, turma A (1 oferta + frequência **legada NULL**), turma B (2 ofertas de programas diferentes, conceitos diferentes por oferta), turma C (grade por dia não uniforme), turma D na lixeira com oferta desativada **antes**, aluno transferido, aluno desenturmado e aluno inativo em conflito. Imprime IDs, datas, senhas e URLs prontas.
- **M1 — P4 (HTTP no ensaio):** login, listagem, lixeira e pauta = 200; CSRF real **400 sem token** nas 8 rotas de escrita testadas e token aceito nas legítimas; matriz de 34 rotas × 5 perfis medida sem seguir redirect. Números do bloco 8 batem com a aritmética independente (75,0/60,0/33,3/50,0/66,7; 88h/176h/141h30min; `f_prog` 75,0/33,3/62,5).
- **M1 — achados (não corrigidos):** BI `FRE-005` = **64,7%** inclui frequência de turma inativa (o Resumo/`FRE-009` usam 60,0%); painel pedagógico mostra **6** em "Alunos enturmados" e **7 novos**; histórico exibe `I: None`; filtro *Programa* da listagem não encontra a turma pela oferta secundária (projeção). O legado NULL sem backfill continua invisível no histórico do aluno (Ana 0,0% × listagem 75,0%) — reconfirmado.
- **Estado da suíte ao final de M1: 722 passed**, 0 falhas; head `8d2e3f4a5b6c` (sem migration); sem push. Relatório `docs/Relatórios/M1_RoteiroTesteManual.md`.

### Alterações do dia — 28/10/2026 (L4.2 — programa na reativação + auditoria do harness)

- **L4.2 — `Turma.programa` na reativação:** `reativar_turma` (`app/services/turma_curso.py`) devolvia turma e ofertas à vida **sem reprojetar** `Turma.programa`. Como a projeção é derivada da **oferta principal ativa** (MER §8.10), reativar só uma oferta que **não** era a principal (checkbox da lixeira, L4.1) deixava a turma exibindo o programa de um curso que não voltou; e uma projeção já suja nunca era corrigida. Correção: uma chamada a `sincronizar_programa_turma(turma)` ao final do serviço, na **mesma transação** (sem commit — a rota continua dona do commit) e **só quando ao menos uma oferta é reativada** (turma sem ofertas é estado legado e não pode perder o programa que alimenta listagem/filtros). Sem migration. Regra em MER §8.10; testes em `tests/test_l4_2_programa_reativacao.py` (7: reativar A+B, reativar só B nas duas origens possíveis, projeção desatualizada, recusa atômica sem tocar o programa, turma sem oferta mantém o programa, serviço reprojeta sem commit). Resultado: **antes** 4 dos 7 falhavam (`X` em vez de `Y` / `PROGRAMA ANTIGO` em vez de `X`); **depois** 7/7.
- **L4.2 — auditoria do harness (perfis no mesmo teste):** varredura AST + grep de todo `tests/`. **49** atribuições de `_user_id` em **26** arquivos; **uma única** função troca de perfil na mesma função — `test_h4_leitores_grade_variavel_smoke.py::test_aluno_ficha_atendimento_conselho_frequencia_seletor` (coord → prof → pedag), classificada **(a) funciona**: aquele módulo cria o app no próprio teste e **não** mantém AppContext aberto, então cada request tem seu `g`. **Nenhuma ocorrência de (b)/(c)** — os 403 de perfil da suíte são exercitados de verdade hoje. A armadilha `g`/`flask_login` (fixture com AppContext preso faz o 2º perfil agir como o 1º) foi **reproduzida** em teste mínimo (`tests/test_l4_2_harness_perfis.py`, 3 testes) e o helper padrão **`login_as(client, user, unidade_id=None)`** foi adicionado a `tests/_helpers.py` limpando `g._login_user` — **sem alterar nenhum teste existente** (722 passed). Relatório: `docs/Relatórios/L4_2_ProgramaReativacaoEAuditoriaHarness.md`.
- **Estado da suíte ao final de L4.2: 722 passed**, 0 falhas (712 + 10 novos); head `8d2e3f4a5b6c` (sem migration); sem push.

### Alterações do dia — 27/10/2026 (L4/L4.1 — lixeira de turmas e reativação seletiva)

- **L4 (`7a7edd0`):** `/turmas/lixeira` corrigida (template `turmas/turma_lixeira.html` criado, rota GET consertada) e POST `/turmas/reativar/<id>` adicionado. `reativar_turma` (`app/services/turma_curso.py`) devolve turma + ofertas desativadas + inscrições elegíveis (motivo `TURMA_DESATIVADA`, sem conflito, aluno ativo), respeita a regra do principal (2+ ativas → exatamente 1) e exige confirmação para período encerrado; LogAcao gravado; contagens em lote (sem N+1).
- **L4.1 — regra de ofertas elegíveis:** a versão do L4 reativava **todas** as ofertas inativas da turma, ressuscitando oferta removida do curso **antes** da exclusão (`desativar_oferta`) e arriscando violação de `uix_turma_curso_principal`. Passa a reativar só as desativadas **junto com a turma**, pelo **LogAcao-marcador** gravado na mesma transação do `excluir_turma` (`acao="Excluir turma (lógica)"`, `detalhes="turma_id=N ofertas=[ids] inscricoes=[ids]"` com só as ofertas então ativas). `updated_at` foi descartado como sinal (o listener de auditoria o reescreve também nas ofertas já inativas). Lixeira ganha checkbox por oferta inativa ("desativado na exclusão da turma" × "desativado antes / origem desconhecida"), pré-visualização pela **mesma regra** do serviço e SELECTs constantes; recusas atômicas (nenhuma oferta marcada, oferta de outra turma, violação do principal) sem alteração parcial. **Sem migration.** Regra em MER §8.10; evidência e testes em `docs/Relatórios/L4_1_ReativacaoOfertasElegiveis.md`.
- **Testes e ensaio:** `tests/test_l4_1_reativacao_ofertas.py` (19: caracterização do defeito + variante do principal trocado, oferta desativada antes permanece inativa, transferências/desenturmação manual não reativadas, aluno inativo preservado, recusa sem parcial, lançamentos/diário/conselho intactos, SELECTs constantes com 2 e 6 turmas, perfis com professor 403) e `scripts/ensaio_l4_1_reativacao.py` (ciclo completo pelas rotas reais, fingerprints das tabelas imutáveis e limpeza; aprovado em SQLite e no scratch PostgreSQL `pautaon_ensaio`).
- **Estado da suíte ao final de L4.1: 712 passed**, 0 falhas; head `8d2e3f4a5b6c` (sem migration); sem push.

### Alterações do dia — 27/10/2026 (Conselho — Gerenciar Perguntas)

### Alterações do dia — 27/10/2026 (D3b-2.0–2.6 — frequência/diário por oferta)

- **D3b-2.0:** mapa da frequência/diário por oferta (somente leitura): inventário P1 de ~40 pontos, dados reais P2 (0 lançamentos nos bancos locais), decisões D1–D6, plano D3b-2.1…2.7. Relatório `docs/Relatórios/D3b2_0_MapaFrequenciaPorOferta.md`. Commit `643d025`.
- **D3b-2.1:** limpeza do working tree (commits 8da6655, b719a1a, 730822f, 40956a3); remoção dos 3 tmp*. Relatório `D3b2_1_LimpezaWorkingTree.md`.
- **D3b-2.2:** remoção de N+1 de `freq_geral`/`freq_geral_oferta` na listagem: mapas `freq_geral_turmas_em_lote`/`freq_geral_ofertas_em_lote` (1 consulta cada); `pos_filtrar_turmas` batch para `min_freq`. Suíte 665. Commit `ed9a088`.
- **D3b-2.3:** remoção de N+1 de frequência no histórico do aluno: `frequencias_aluno_por_inscricao` (1 consulta). Suíte 669. Commit `42cd2ad`.
- **D3b-2.4:** estatísticas do GET `/frequencia` por oferta em turma com 2+ ofertas (legado NULL não entra). Suíte 673. Commit `344ad9f`.
- **D3b-2.5:** `min_freq` coerente com a frequência exibida (D7: compara a soma da turma). Suíte 678. Commit `4c307a8`.
- **D3b-2.6:** `f_prog` por `TurmaCurso.programa` (regra D2 do legado). Suíte 681. Commit ` (implementação + docs)`.
- **Decisões D1–D7 (D3b-2.0):** D1 contrato por leitor (turma=soma vs por oferta); D2 legado NULL (regra D2, backfill só inequívoco); D3 limpeza por oferta; D4 estatísticas por oferta; D5 N+1; D6 ALU-009/010 (já aplicavam) + f_prog por oferta; D7 min_freq compara o valor exibido.
- **Estado da suíte ao final da D3b-2.7: 684 passed**, 0 falhas; head `8d2e3f4a5b6c` (sem migration); sem push.


- **PQ1 — Numeração e lettering das perguntas:** cada pergunta passa a exibir número sequencial (1, 2, 3…) reiniciando por aba (etapa + tipo) e cada opção de resposta recebe letra (A, B, C…), facilitando a referência para quem cadastra e para quem responde. Implementado **sem migration e sem campo novo**: ordenação estável por `id` nas três consultas de `app/conselho.py` (`gerenciar_perguntas` L290, lançamento L489, turma_aval L845) e `loop.index`/`loop.index0` (com `selectattr('tipo','equalto',…)` para o índice bater por aba) nos templates `conselho/perguntas.html`, `conselho/lancamento.html` e `conselho/turma_aval.html`. A letra é só exibição — o valor persistido continua o texto puro da opção e `opcoes` segue separado por `" | "`, sem impacto em `ConselhoResposta` histórico.
- **PQ2 — Reparo do botão de edição de pergunta:** o `onclick` embutia os valores "crus" numa string JS dentro do atributo HTML. Com a Onda 2B, `str(EtapaConselho.INICIAL)` → `"EtapaConselho.INICIAL"` e `str(TipoPergunta.TURMA)` → `"TipoPergunta.TURMA"`, então os `<select>` de Etapa/Foco não pré-preenchiam; texto com aspa simples quebrava o clique; e pergunta dissertativa (`opcoes=None`) carregava uma opção fantasma "None". Correção: dados movidos para atributos `data-*` (autoescapados pelo Jinja) usando `.value` dos enums e `or ''` para nulo em `conselho/perguntas.html`; `editarPergunta(btn)` passa a ler `btn.dataset` e `adicionarCampoResposta` cria o `<input>` via propriedade `.value` (não interpolado no HTML) em `static/js/conselho/conselho.js`. Sem mudança em banco nem no valor persistido.

- **PQ3 — Melhoria visual da tabela de perguntas (Gerenciar Perguntas):** as duas tabelas (Turma/Aluno) passaram a `table-layout: fixed` com larguras de coluna (Pergunta 55% · Opções 35% · Ações 96px fixo) e `overflow-wrap: anywhere` nas células, no `conselho/perguntas.html`. A pergunta completa é exibida quebrando linha, as opções ficam no lado oposto e a coluna de Ações permanece sempre dentro do campo de visão, **sem barra de rolagem horizontal**. Só CSS/markup — sem mudança de dados.
  - **PQ3.1 (refino):** os badges de opção (frases longas) eram itens de flexbox que não encolhiam, estouravam a célula e **sobrepunham a coluna Ações**; adicionado `.table-perguntas .badge { white-space: normal; overflow-wrap: anywhere; word-break: break-word; max-width: 100%; height: auto; }` para o texto da opção quebrar dentro da coluna.

**Estado da suíte ao final de PQ1+PQ2+PQ3: 659 passed, 0 falhas.**
- **PQ4 — Formulário de impressão do Conselho:** adicionado o botão **Imprimir formulário** ao lado de **Configurar Perguntas** no painel (`app/templates/conselho/painel.html`). A configuração é feita em modal, com uma etapa por impressão (Inicial, Percurso ou Final) e quantidade de alunos (1–100; padrão 12). A rota `GET /conselho/imprimir` (`app/conselho.py`) valida perfil, etapa e quantidade, busca somente perguntas ativas da etapa e separa perguntas gerais (impressas uma vez) das individuais (repetidas para cada aluno). O documento (`app/templates/conselho/imprimir_formulario.html`) tem identificação e respostas em branco e segue o padrão institucional da pauta de frequência (cabeçalho, paisagem, tabelas e controles ocultos na impressão). Sem alterações no modelo ou migrations. Cobertura em `tests/test_conselho_ui.py`: seleção/conteúdo e repetição para 12 alunos, exclusão de perguntas inativas/de outras etapas, validação de entrada e autorização. **Validação desta entrega: 30 testes de Conselho passaram; Ruff passou no arquivo de testes; `git diff --check` sem erros.** Ruff em `app/conselho.py` mantém alertas de estilo preexistentes.

### Alterações do dia — 25/10/2026 (Onda 4 pós-Fase 4)

- **T1:** Reparo da suíte (120F→210P); `tests/_helpers.py`; 8 testes de transferência; 4 bugs reportados.
- **P1:** Ensaio upgrade scratch (5 cenários); `scripts/preparar_deploy_onda4.py`; dump autêntico ausente.
- **B1:** P2 KeyError, P3 nova turma programa, P4 reprojeção 2+ ofertas; concomitância realinhada (4 testes); `\_PROGRAMAS_OFERTA`. 218P.
- **B2:** D4 fechado; bloco programa removido de `nova_turma.html`; investigação falha `/cursos`. 220P/1F.
- **B3:** `editar_curso` — isolamento para todos; suíte verde. 221P.
- **B4:** Isolamento em 12 rotas de escrita; `test_isolamento_unidade_escrita.py` (36 testes). 257P.
- **B5:** Migrations c3d4/d4e5 endurecidas (checagens + COALESCE); ensaios A–E. 257P.
- **B6:** Criar nível Visão Global recusada; D3 (turma sem período); R2 limpo; código morto NULL inscrição removido. 262P.
- **M1 (24/10):** Enturmação por oferta: `enturmar_alunos` grava `turma_curso_id`; regras 0/1/2+ ofertas (0 recusa; 1 auto; 2+ exige escolha validada em `ofertas_ativas`); duplicidade por aluno+turma+oferta; `ver_turma` com `?oferta_sel=&modal=enturmar`, disponíveis por oferta e selos de curso (`cursos_por_aluno`); `adicionar_oferta` vinculava NULL ativas; 11 testes em `test_enturmacao_oferta.py`; semente `test_security_regressions` ganhou 1 oferta. 211P/2F.
- **M1.1 (24/10):** Adoção de `Inscricao` NULL ativa ao enturmar (menor id; `data_inicio` preservado); `scripts/verificar_onda4_m1.py` (somente leitura, ainda presente); +6 testes (17 total). **A adoção NULL em `enturmar_alunos` e em `adicionar_oferta` foi tornada obsoleta pelo NOT NULL de `c3d4e5f6a7b8` e removida na T1** (7 testes eliminados; restam 13).
- **M2:** `app/services/enturmacao.py`; desenturmar por oferta; `test_desenturmacao_oferta.py` (16). 278P.
- **M4:** Guarda desativar_oferta; `cond_oferta_efetiva()`; `test_desativar_oferta.py` (13). 291P.
- **L1:** Limpeza: `detalhe copy.html`, `_contagem_inscricoes_sem_curso`, “sem curso definido”, rodapé teste. A2 mantido. Sync MER + backlog.
- **L2 (só docs):** M1/M1.1 restaurados e reescritos; MER §2 com os serviços atuais, §7.16 com a nota da transferência; “Pendências abertas” reorganizadas.
- **D5.0:** Desenho do conselho por oferta (somente leitura): mapa do código, colunas/UNIQUE propostas, plano em duas migrations (D5-A aditiva, D5-B endurecimento) e decisões Q1/Q4/Q5. 291P.
- **D5.1:** Migration `e5f6a7b8c9d0` (aditiva): `conselho_classe.turma_curso_id` nullable + FK RESTRICT; `uix_conselho_legado`/`uix_conselho_oferta` (parciais) e `ix_conselho_turma_curso`; remove a UNIQUE antiga; `turma_curso.conselho_concluido` + `avaliacao_*`; backfill só inequívoco. `tests/test_d5_schema.py` (6), `scripts/verificar_onda4_d5.py`, ensaio A–E. 297P.
- **D5.2:** Escrita por oferta (lançamento, fechamento JSON com `situacao_final`/`proxima_turma_id` e catálogo `OpcaoProximaTurma`, avaliação coletiva em `turma_curso.avaliacao_*`); padrão M1 0/1/2+; ponte `Turma.conselho_concluido` em `alternar_conselho`. `tests/test_conselho_oferta.py`. 320P.
- **D5.2b:** Quatro defeitos de tela (grade de lançamento, modal inerte, fechamento sem CSRF, select fora do enum). `tests/test_conselho_ui.py` (4). 324P.
- **D5.3:** Encerramento/contagens por oferta: `turma_conselho_concluido()` (derivado), `contar_ofertas_conselho()`, painel/informações/métricas e certificado por oferta. `tests/test_d5_encerramento.py` (13). 337P.
- **D5.4:** Leitores por oferta: `app/services/conselho_leitura.py` (lote, sem N+1); histórico, ficha 360°, painel por turma (`p.texto`), resultado do conselho e certificado; 5 bugs latentes pré-existentes corrigidos. `tests/test_d5_leitores.py` (12). **As leituras passaram a fechar por oferta — a restrição de publicação aberta na D5.2 foi encerrada aqui** (o relatório D5.4 ainda registrava “só fecha na D5.5”; com a D5.5 aplicada, escrita e leitura estão integralmente por oferta). 349P.
- **B7:** `_montar_turma_linha` implementada na visão por período do painel pedagógico — a função era chamada desde `1c8604c` e **nunca existiu** (a rota respondia `NameError`); `ruff check app --select F821` limpo; `tests/test_painel_periodo.py` (3). 352P.
- **D5.5:** Endurecimento: `f6a7b8c9d0e1` (pré-checagens (i)–(iv) num único `RuntimeError`, `turma_curso_id` NOT NULL, drop `uix_conselho_legado`, drop `turma.conselho_concluido`, downgrade com guarda/repopulação); modelos e ponte removidos; `ETAPA_PARA_CAMPO_AVALIACAO` único; órfãos (`periodos/conselhos.js`, `conselho/relatorio.html`, import `PerguntaConselho`); seção G bloqueante em `preparar_deploy_onda4.py`; seletor `?oferta_sel=` na ficha 360°; `tests/test_d5_endurecimento.py` (7); ensaio A–E. 359P.

**Estado da suíte ao final de L1: 291 passed, 0 falhas** (histórico). **Ao final da D5.5: 359 passed, 0 falhas.**

### Pendências abertas (pós-L3)

- **D3b-2/J3 — frequência e relatórios por turma_id (parcialmente resolvido em D3b-2.0–2.6):** ramo legado ainda lê por `turma_id` (`app/utils/logica.py`, `app/utils/frequencia.py`); `Turma.freq_geral` (soma das ofertas, decisão D1) e `agregar_por_turma` (painel pedagógico, decisão D1) mantidos como visão por turma; BI `frequencia_por_turma` e indicadores de conselho (CRU-002/CRU-005) ainda filtram pela turma. **Resolvido:** N+1 de `freq_geral`/`freq_geral_oferta` na listagem (D3b-2.2); N+1 do histórico (D3b-2.3); estatísticas do GET `/frequencia` por oferta em 2+ ofertas (D3b-2.4); `min_freq` coerente com o valor exibido (D3b-2.5, D7); `f_prog` por `TurmaCurso.programa` (D3b-2.6); ALU-009/ALU-010 já aplicam `cond_inscricao_enturmada`. **Ainda pendente:** legado NULL sem backfill (decisão D2 — só regra D2); BI que ainda lê `Turma.programa` (projeção) em outros pontos (listagem, filtros, conselho) — fora do escopo da D3b-2.6; `excluir_turma`/limpeza de lançamentos em `editar_turma` ainda apagam por `turma_id` (D3).
- **Fases 5–7 da Onda 4 (a redefinir):** autorização por professor da oferta, turno e centro de custo por oferta, transferências avançadas. Fases 8–9 e NOT NULL final (`c3d4e5f6a7b8` + `d4e5f6a7b8c9`) **concluídas**.
- **`Transferencia`:** decidir se a tabela passa a registrar a oferta de origem/destino (hoje só `turma_origem_id`/`turma_destino_id`; rastrear exige `Inscricao`).
- **Frequencia/RegistroAula legados com `turma_curso_id IS NULL`:** backfill definitivo **sem fase designada** (a antiga Fase 9 tratava só do NOT NULL de `inscricoes`); as rotas atuais preservam `IS NULL` de propósito. Consequências: turma sem oferta que lança frequência e depois ganha a primeira oferta perde a visão por oferta e relançar o dia cria linha duplicada; turma que desativa todas as ofertas deixa de mostrar o histórico por oferta na tela legada.
- **Dívida de migrations (§11.1, itens 2–6 e 8 do MER).**
- **Dump autêntico** para um novo ensaio P1/B5 (não há produção real; o banco local veio de dump antigo — B5-P2).
- **B5-P1 — corrigir `migrations/env.py`:** `flask db upgrade`/`flask_migrate.upgrade()` **engolem** o `RuntimeError` das checagens (passam por `catch_errors`, que faz `sys.exit(1)`) e o `fileConfig` do `env.py` desabilita os loggers; pendente `fileConfig(..., disable_existing_loggers=False)`. Até lá, a mensagem só aparece chamando `alembic.command.upgrade` direto (helper do ensaio D5.5).
- **Teste manual no navegador:** roteiro em `docs/Roteiro_Teste_Manual.md` (M1, 93 casos) + semente `scripts/semear_roteiro_manual.py` para o ensaio. Cobre o que a suíte não cobre: CSRF ligado em todos os formulários de escrita, agenda por dia no navegador, impressão/exportação e leitura visual dos números. **Achados da M1 corrigidos na A1:** `FRE-005` incluía turma inativa (agora 60,0%), `I: None` no histórico (agora "—") e legado NULL invisível no histórico (regra D2). **Achados abertos (análise na A1):** item abaixo.
- **A1-4 — painel pedagógico: "Alunos enturmados" 6 × "7 novos" (proposta, sem alteração):** o KPI grande é `vp.totais.alunos` = `_Acumulado.alunos`, somado de `len(info.por_aluno)` de `frequencia.agregar_por_turma`, que só inclui aluno **com linha de frequência**; o extra "%d novos" vem de `status_alunos_para_bi` (inscrição ativa + turma ativa + oferta efetiva), base correta de "enturmado". Na semente a diferença é 1 aluno transferido para a Turma C **sem nenhum lançamento** (7 enturmados × 6 na pauta) — logo "6 ... 7 novos" é impossível e o rótulo induz ao erro. **Proposta:** trocar o big number pela contagem canônica (`contar_alunos_enturmados(periodo_letivo_id=...)` ou `len(enturmados_ids)` restrito às turmas do período, `app/services/enturmado.py`) e, se o número da pauta for útil, expô-lo à parte como "alunos com frequência lançada"; teste novo: aluno enturmado sem lançamento conta no KPI. Não altera a visão por período (que de propósito omite turma sem frequência).
- **A1-5 — filtro *Programa* usa a projeção `Turma.programa` (proposta, sem alteração):** `aplicar_filtros_turmas` (`app/registros/turmas.py`, `stmt.where(Turma.programa == programa)`) e o painel do professor (`app/registros/core.py`, mesma coluna) casam só a oferta principal; a turma com oferta secundária de outro programa (semente: Turma B, *Esporte* principal + *Meio Ambiente*) some do filtro *Meio Ambiente*. **Proposta:** usar o helper que professor/turno já usam — `_filtro_por_oferta(func.coalesce(TurmaCurso.programa, Turma.programa) == programa, Turma.programa == programa)` — isto é, `EXISTS` em oferta ATIVA, sem duplicar linhas da turma, com fallback à coluna congelada quando não há oferta ativa. **Impactos:** (a) opções do select continuam hardcoded em `turmas/listar.html` (Profissionalizante/Esporte/Meio Ambiente/Outros) — nenhuma opção nova; (b) a contagem da listagem passa a incluir a turma em cada programa que qualquer oferta ativa declare (turma multi-programa aparece nos dois filtros); (c) a impressão de centros de custo (`/turmas/centros-custo/imprimir`) respeita os mesmos filtros — a turma passa a aparecer no grupo de centro quando o filtro de programa casar por oferta; (d) `Turma.programa` continua sendo a projeção exibida na coluna, sem alteração. Testes que mudariam: `tests/test_filtros_turmas.py::test_filtra_por_programa` (hoje fixa `Turma.programa`), além de um novo caso "2 ofertas, programas diferentes" (esperado: casa nos dois).
- **Duplicação de `cond_oferta_efetiva` (M4, MER §12.13).**
- **`ofertas.html` com lista de programas embutida (D6, MER §12.14).**
- **`TurmaCurso.avisos_horario` transiente (D7, MER §12.15).**
- **Onda 3C:** dropar os JSONs legados de `Aluno` (MER §10).
- **Resíduos do conselho (MER §12.19–§12.24):** `Turma.avaliacao_*` (legado, remover após conferir dump autêntico), `turma_conselho_concluido()` sem leitor no código de aplicação, painel por período omite turma sem frequência lançada, `agregar_por_turma` agrega por `turma_id`, N+1 residual do histórico e CSRF/UX do fechamento sem teste de navegador.
- **Harness — troca de perfil no mesmo teste (auditoria L4.2, 28/10/2026):** o fixture `app` mantém um `app_context` aberto durante o teste; como `flask.g` vive no AppContext, o `_login_user` cacheado pelo Flask-Login sobrevive e trocar só o `_user_id` da sessão **não troca o usuário** (o 2º perfil age como o 1º; um assert de 403 passaria por engano). Helper padrão já disponível: `tests/_helpers.py::login_as(client, user, unidade_id=None)` (limpa `g._login_user`). **Ocorrências encontradas na varredura completa (única):** `tests/test_h4_leitores_grade_variavel_smoke.py::test_aluno_ficha_atendimento_conselho_frequencia_seletor` (3 identidades; classe **a** — funciona, o módulo não prende AppContext). **Mesmo usuário repetido (não é troca de perfil):** `tests/test_leitores_grade_h3e.py::test_conselho_painel_e_fechamento_por_dia` e `tests/test_ui_grade_por_dia.py::test_erro_domingo_rejeitado`. **RESOLVIDO em 30/10/2026 (E4):** os **38** arquivos com login local (**50** blocos) passaram a chamar `login_as` — nenhuma atribuição direta de `_user_id` restou em `tests/` fora de `_helpers.py` e do `_login_inline` de `test_l4_2_harness_perfis.py` (que caracteriza a armadilha de propósito). Suíte completa: **1042 passed** (mesmo total). **Pendente:** só o `conftest.py` único (MER §12.16) e trocar os asserts de 200 do teste do H4 por uma rota restrita, para que a identidade seja discriminadora.
- **I1 — DECISÃO PENDENTE COM A INSTITUIÇÃO (medicação na pauta, 28/10/2026):** "Medicação regular" informada como "sim" é impressa na pauta para **qualquer** professor com acesso à pauta da turma (inclusive de períodos encerrados, via URL). Verificar se há necessidade de expor a medicação ao professor da oferta — nem toda medicação precisa ser conhecida por ele. Se não houver, retirar da pauta; se houver só em parte, a secretaria informa o necessário no campo "Informações para o professor da turma", que está sob a regra de acesso do I1. **Nada muda no comportamento da medicação enquanto a decisão não for tomada.** **Conferido em T0-d (29/10/2026):** a pendência é de **conteúdo** do que a pauta exibe, não de **quem pode lançar** — logo não condiciona a migração do `/frequencia` (o que barra a T1 é a obrigatoriedade do professor, item G1 abaixo).
- **I1 — outras telas em que o professor vê o nome do aluno (inventário da P1; NÃO alteradas):** detalhe da turma (`turmas/detalhe.html`), painel do professor (`dashboard/professor.html` + `registros.core.painel_professor`), Diário de Bordo por turma e na visão global (`turmas/observacoes.html`), conselho — lançamento e painel (`conselho/lancamento.html`, `app/conselho.py`), histórico do aluno (`alunos/historico.html`), foto do aluno (`/aluno/<id>/foto`), atendimento pedagógico, `alunos/gerenciar.html`, transferência (`alunos/transferir.html`), relatórios/BI. Todas usam guarda **por turma** (`Turma.professor_id`) ou por perfil, nenhuma exibe acompanhante/instruções hoje — a única tela que exibe é a pauta impressa, agora sob a regra do §8.12, e o modal novo da pauta de frequência. Migrar as demais para a regra por oferta do I1 é decisão futura.
- **G1 — PENDÊNCIAS ABERTAS:** (1) ~~indicar o professor das ofertas 16, 17 e 18~~ — **RESOLVIDO em 29/10/2026 (E1 2ª rodada, seção no topo):** decisão do usuário = dados de teste; as três foram **removidas com os lançamentos** (frequencia −9, inscrições −5) pelo removedor com `--remover-lancamentos`; na 1ª rodada (commit `ee922c5`) já tinham saído a 19 (principal) e a 50 (ensaio); (2) **APLICADO em 29/10/2026 (E2)** — `ValueError` em português no serviço (`criar_oferta_inicial_da_turma`, `adicionar_oferta`, `editar_oferta`) com a mensagem única `_PROFESSOR_OBRIGATORIO`, `required` + remoção de “-- Sem professor --” em `turmas/ofertas.html` e no cadastro/edição de turma, POST forjado recusado, troca com lançamento exigindo confirmação e `log_acao` com anterior e novo (MER §8.21); o “aviso sem professor” para oferta legada perdeu o objeto: com o NOT NULL de (3) não pode existir oferta sem professor; (3) **NOT NULL no banco** — **APLICADO em 29/10/2026 (E2 desta rodada)**: migration `d6e7f8a9b0c1` aplicada nos dois bancos pelo protocolo (backup, upgrade/downgrade/upgrade, `\d` conferido; head `d6e7f8a9b0c1` em ambos); destravada pela 2ª rodada do saneamento; teste de recusa no banco em `tests/test_notnull_professor_oferta.py` (MER §8.23); (4) ~~**links de impressão sem `turma_curso`**~~ — **RESOLVIDO em 30/10/2026 (G1-4, commit `53d6f2e`):** `lancar.html` só oferta impressão com `pode_imprimir_pauta and not exigir_escolha` (2+ ofertas sem escolha não mostram botão nem link) e todo href publicado leva `turma_curso`; `detalhe.html` linka por oferta (professor só as dele; 2+ uma por oferta; 1 explícita; 0 legado sem parâmetro) — nenhum link cai em 403; testes `tests/test_g1p2_links_impressao.py` (9); (5) **alinhar a herança remanescente** (listagem de turmas, painel do conselho, `ver_turma`, `ver_observacoes`, `/frequencia`, conselho, histórico e foto do aluno — inventário arquivo:linha no item da PARTE B) — **T0-e conferido em 29/10/2026** (MER §8.20 e `docs/Relatórios/I1_RegraPorOferta_Higiene.md`): restam como guarda por turma `ver_turma` (`turmas.py:1374-1378`), `ver_observacoes` (`:2640-2644`), `POST`/`GET /frequencia` (`core.py:256-259` e `:382-399`), histórico (`alunos.py:881-893`) e foto (`:1316-1327`); `imprimir_pauta`, I1, painel do professor e conselho já usam a oferta, e listagem/BI/relatórios são **filtros** (COALESCE), não acesso; **a herança na criação da oferta foi alinhada na E2** (só herda `turma.professor_id` sem curso legado, antes da validação) e os **espelhos turma↔oferta não propagam NULL** — a T1/**E3** já não está bloqueada por (2) (a obrigatoriedade vigora desde a E2); o que resta do item (1) são 3 ofertas sem professor, e a perda de acesso de quem só tinha por herança é o comportamento-alvo da regra sem herança (§8.12); (6) decisão da **medicação** na pauta (pendente do I1).
- **PARTE B — herança de `turma.professor_id` que AINDA EXISTE (alinhamento pendente):** guardas de acesso por turma — `ver_turma` (`registros/turmas.py:1376`), `ver_observacoes` (`:2642`), `frequencia` GET/POST e painel do professor (`registros/core.py:220`, `:276`, `:403`), conselho (painel `conselho.py:475`, lançamento `:229`, `avaliar_turma` `:906`), histórico do aluno (`registros/alunos.py:887`) e foto (`:1322`). **Linhas conferidas em 29/10/2026** (T0-e): POST `/frequencia` = `core.py:256-259`, GET `/frequencia` = `:382-399`; o painel do professor **não é mais** leitor de `turma.professor_id` — a rota legada redireciona para `main.painel` e o painel usa a oferta (`main/dashboard_professor.py:168`, com ramo legado em `:200`); o conselho de lançamento já filtra por oferta (`conselho.py:526`). Leitores com "professor efetivo" (COALESCE) — filtro por professor da listagem de turmas (`registros/turmas.py:562-576`), `ofertas_do_painel_conselho`/`professor` (`services/turma_curso.py:151-155` e `:166`) e o cabeçalho "Professor:" da pauta impressa (`templates/frequencia/imprimir_pauta.html:213-214`). O dashboard do professor já é por oferta (`main/dashboard_professor.py:163-206`, com ramo legado para turma sem oferta ativa). **Não alterados nesta parte, por decisão.**
- **PARTE B — botão "Imprimir" da pauta de frequência:** `frequencia/lancar.html` mostra o botão para a oferta selecionada; um professor que abre a pauta da turma por outro caminho pode clicar numa oferta que não leciona e receber 403 do servidor. Esconder/desabilitar o botão por oferta é melhoria de UI pendente (a guarda do servidor está correta).

---

### Alterações do dia — 24/10/2026

- A impressão de pauta foi organizada por mês, com uma folha para cada mês e logo secundária em todas elas. A folha identifica unidade e período letivo, oferece a lista de alunos por oferta (principal ou demais ofertas, conforme a opção), e inclui idade e dados relevantes para o professor: acompanhante, medicação regular quando informada como sim e instruções pedagógicas cadastradas.
- Os campos de data da grade de presença tiveram a largura reduzida e a fonte do conteúdo da coluna Aluno foi ligeiramente ampliada para facilitar o preenchimento manual.
- No Painel Geral, os quatro indicadores ficaram reunidos em uma grade de duas colunas, com Períodos Ativos sempre na primeira posição. Em telas estreitas, a grade se reorganiza em coluna.
- A listagem de turmas ganhou filtros de período letivo e centro de custo. Sem período específico, abre no ano atual; as badges rápidas exibem o ano atual e o anterior quando este tiver períodos. O seletor mantém disponíveis todos os períodos cadastrados, inclusive históricos e futuros.
- As opções de Nome da Turma e Professor passaram a vir de todas as turmas/ofertas ativas da unidade, sem serem reduzidas pelos filtros atuais; no professor, considera-se o docente efetivo da oferta com fallback para o professor da turma. Centro de custo usa o catálogo ativo da unidade.
- A impressão em `app/templates/turmas/imprimir_listar_turma.html` respeita os filtros da listagem, mantém a hierarquia centro → turma → ofertas e identifica no cabeçalho o período, todos os períodos do ano ou "Todos", além do usuário e data/hora de emissão.
- `app/templates/alunos/historico.html` passou a mostrar usuário e data/hora de emissão no cabeçalho, usando o horário local fornecido pela rota; os dados deixaram de ser duplicados no rodapé.
- Documentação do MER e dos comentários/docstrings dos arquivos de código alterados foi conferida e alinhada ao comportamento implementado. Validação realizada: sintaxe Python/Jinja e `git diff --check`; suíte de testes não executada.

---

### Alterações do dia — 23/10/2026

- Conclusão: Etapas F, G2, G3, I, J2, K e K2 da Onda 4 (Fase 4) implementadas e validadas; centros de custo no formulário de períodos corrigidos (CSRF + sincronização das checkboxes); coluna `turma_curso.programa` adicionada (migration `a1b2c3d4e5f6`) e schema drift corrigido via `flask db upgrade`; alterações ainda não commitadas.

### Etapa F — oferta criada junto com a turma

- `app/services/turma_curso.py`: `criar_oferta_inicial_da_turma` — ao gravar uma turma **com curso**, a oferta inicial é criada na **mesma transação** de `nova_turma`; copia professor, turno, dias, horários, datas, centro de custo e unidade da turma; `principal=false`; idempotente (não duplica se já houver oferta); não commita. Turma sem curso não gera oferta.
- `scripts/verificar_onda4_fase4.py`: nova checagem **"turma ativa com curso e sem oferta"** (emite aviso, sem alterar dados).

### G2 — `editar_turma` por número de ofertas ativas

- Regras no POST de `editar_turma` conforme a contagem de `ofertas_ativas(id)`: **0** = fluxo atual; **exatamente 1** = grava os campos de agenda na turma **e espelha na oferta** em transação única, com `_validar_horario_concomitante(..., exclude_oferta_id=...)` e recusa de troca de curso; **2+** = descarta curso/professor/turno/dias/horários/datas/centro vindos do formulário e grava só nome/programa/período/ordenação, sem disparar a limpeza de lançamentos.
- **Correção do ramo sem oferta:** `curso_id` vazio **não apaga** mais o `curso_id` da turma (a ausência do campo não é tratada como limpa).
- **Rollback antes do flash** quando a validação de concomitância falha (`ValueError` → `db.session.rollback()` e só então flash/redirect), preservando turma e oferta.

### G3 — tela de edição de turma

- GET de `editar_turma` injeta `ofertas` (`ofertas_ativas(id)`) e `n_ofertas`; novo bloco **"Cursos desta turma"** com botão **"Adicionar curso"** (→ `registros.turma_ofertas`) aparece com ≥1 oferta.
- Com **1 oferta**, o curso é exibido **pela oferta ativa** (`ofertas[0]`) e enviado em campo oculto `curso_id` (somente leitura); com **2+**, os campos de oferta ficam **bloqueados** (readonly + hidden) com aviso no topo.
- `app/static/js/turmas/editar.js`: com 2+ ofertas (`window.turmaOfertasBloqueadas`) **não pede confirmação de limpeza** nem dispara recálculo de C.H.; guardas para selects/checkboxes ausentes.

### I — exclusão de turma (física ou lógica)

- `app/services/turma_curso.py`: `turma_tem_historico` — verifica se existe Frequencia, RegistroAula, ConselhoClasse ou Transferencia ligada à turma (por `turma_id` ou por `turma_curso_id` das ofertas).
- `app/registros/turmas.py`: `excluir_turma` — **sem histórico**: exclusão física (inscrições, DiaBloqueadoTurma, ofertas, turma; TemaAula tem `turma_id` liberado) + `LogAcao`; **com histórico**: exclusão lógica (turma, ofertas e inscrições ativas viram `ativo=False`, inscrições com `data_desativacao` + motivo `TURMA_DESATIVADA`); lançamentos preservados; aluno permanece ativo e disponível para nova enturmação.
- `app/registros/turmas.py`: constante `MOTIVO_INSCRICAO_TURMA_DESATIVADA = "TURMA_DESATIVADA"` (token CAIXA-ALTA, sem acento, alinhado a `TRANSFERENCIA`).

### J2 — contagens do BI e turma desativada

- `app/relatorios/bi_filtros.py`: `cond_inscricao_enturmada` — inscrição conta quando turma ativa e ligada a oferta ativa (por `turma_curso_id`), ou `turma_curso_id` NULL numa turma com exatamente 1 oferta ativa.
- `app/relatorios/bi_alunos.py`: filtros de turma ativa e uso do helper em `alunos_por_unidade`, `inscricoes_por_curso`, `frequencia_por_turma/curso`, `total_turmas`, `media_alunos_por_turma`, `turmas_por_curso/periodo/unidade/professor`. `alunos_por_curso` e `alunos_por_turma` (ALU-009/ALU-010) usam **apenas** `Turma.ativo`; o helper `cond_inscricao_enturmada` será aplicado neles na J3, depois de dar oferta às turmas das sementes de teste.
- **Efeito retroativo do status:** desativar uma turma pode alterar o status do aluno em **períodos passados** (o histórico em `aluno_status.py` ignora turma desativada).
- **Média por turma:** `media_alunos_por_turma` conta **linhas de inscrição ativas**, não alunos distintos — aluno com 2 inscrições que contam é contado 2 vezes.
- `app/services/aluno_status.py`: coorte e histórico ignoram turma desativada, evitando inflar DESENTURMADO.
- `tests/test_bi_turma_desativada.py`: cenário central e regressão.

### K — C.H. por oferta e listagem por oferta (K2)

- `app/models/academico.py`: `TurmaCurso.carga_horaria_aula` e `carga_horaria_total` (minutos), herdando horários da turma quando a oferta não define os próprios; nota de otimização em `Turma.freq_geral_oferta`.
- `app/services/turma_curso.py`: `datas_aula_oferta` (extraída de `datas_esperadas_oferta`, com teto opcional) e `criar_oferta_inicial_da_turma` (já documentada em Etapa F).
- `app/registros/turmas.py`: `aplicar_filtros_turmas`/`pos_filtrar_turmas` agregam professores/turnos/dias das ofertas ativas; filtros professor/turno/dia/horário por COALESCE(oferta→turma) com fallback só sem oferta ativa; `min_freq`/`min_ch_aula`/`min_ch_total` sobre a oferta principal com 2+ ofertas; `_ofertas_ativas_da_turma`/`_oferta_principal`/`_resumo_ofertas`; tolerância a objetos sem `ofertas_curso`.
- `app/templates/turmas/listar.html`: selo/sub-linha só com 2+ ofertas; filtros Nome da Turma e Professor viraram `<select>` derivados de todas as turmas/ofertas ativas da unidade, independentemente dos filtros atuais; o professor listado é o efetivo da oferta, com fallback para o professor da turma.
- **Atualização de 24/10/2026:** incluídos filtros de período e centro de custo; ano atual como padrão, badges rápidas do ano atual e anterior, seletor com períodos históricos/futuros e impressão hierárquica que respeita os filtros e informa o período no cabeçalho.
- `tests/test_turma_curso_lista.py`: GET 0/1/2 ofertas, agregação, filtros por oferta, C.H. manual com bloqueio, `datas_esperadas_oferta` inalterada.

### Correções de legado e regras de vigência

- **Caminho legado da frequência:** `salvar_frequencia` e `carregar_frequencias` tratam o lançamento legado por `turma_curso_id IS NULL` tanto na **leitura** quanto na **gravação**, sem sobrescrever a linha de uma oferta no mesmo dia.
- **Oferta em turma em andamento:** `adicionar_oferta` sem `data_inicio`, em turma já iniciada e viva que já tem outra oferta, recebe **a data de hoje** (precede a herança).

### Validação manual na tela

- **Espelhamento confirmado:** ao editar a turma com oferta única, o **professor da oferta acompanha a turma** (gravado nos dois lados na mesma transação).
- **Campos bloqueados:** na turma com **2 ofertas**, os campos de oferta ficam somente leitura e o POST forjado é descartado pelo servidor.
- **Etapa F confirmada:** a turma "Básico Optimist" nasceu com oferta (curso, professor, turno, dias e horários copiados).
- Exclusão (I), lista por oferta (K2) e contagens do BI (J2) validadas **apenas por testes automatizados**; falta conferência na tela.

### Testes e verificações

- `tests/test_turma_curso_edicao.py`: cenários de G2 (espelhamento, recusa de troca de curso, 2+ ofertas, rollback) e G3 (GET 0/1/2 ofertas; hidden `curso_id` pela oferta ativa; sem bloco com 0 ofertas; readonly com 2+; oferta desativada A + ativa B → hidden vale B e edição do nome é aceita).
- `tests/test_turma_curso_exclusao.py`: exclusão física (sem histórico) e lógica (com histórico), preservação de lançamentos, aluno disponível para nova enturmação, isolamento por unidade.
- `tests/test_bi_turma_desativada.py`: contagens do BI com turma desativada e inscrições enturmadas em oferta.
- `tests/test_turma_curso_lista.py`: listagem por oferta, agregação, filtros por COALESCE, C.H. por oferta.
- `tests/test_filtros_turmas.py`: filtros da listagem (incluindo seleção de Nome da Turma e Professor).
- Suíte completa: **200 aprovados**, com as **2 falhas preexistentes** de `/cursos` (`2 failed, 200 passed`).

### Arquivos principais

`app/registros/turmas.py` (`nova_turma`, `editar_turma` GET/POST, `excluir_turma`, `aplicar_filtros_turmas`/`pos_filtrar_turmas`), `app/services/turma_curso.py` (`criar_oferta_inicial_da_turma`, `turma_tem_historico`, `datas_aula_oferta`), `app/models/academico.py` (`TurmaCurso.carga_horaria_aula/total`), `app/relatorios/bi_alunos.py`, `app/relatorios/bi_filtros.py` (`cond_inscricao_enturmada`), `app/services/aluno_status.py`, `app/templates/turmas/editar.html`, `app/templates/turmas/listar.html`, `app/static/js/turmas/editar.js`, `scripts/verificar_onda4_fase4.py`, `tests/test_turma_curso_edicao.py`, `tests/test_turma_curso_exclusao.py`, `tests/test_bi_turma_desativada.py`, `tests/test_turma_curso_lista.py`, `tests/test_filtros_turmas.py`, `app/models/MER.md` e este `backlog_desenvolvimento.md`.

### Pendências e decisões abertas

- `turma_lixeira` (GET `/turmas/lixeira`): resolvido em L4 — template criado e rota de reativação adicionada.
- **J3:** atribuição por curso no BI pelo **curso da oferta**; `Turma.programa` ainda é lido no BI e na lista (o programa já existe na oferta, `turma_curso.programa`).
- `excluir_turma` e a limpeza de lançamentos em `editar_turma` apagam por `turma_id`, alcançando as linhas de **todas as ofertas**.
- Estatísticas do GET `/frequencia` (`core.py` ~L396-400) agregam oferta e legado **sem separar por oferta**.
- Turma sem oferta que lança frequência e depois ganha a **primeira oferta**: registros com `turma_curso_id` NULL deixam de aparecer na tela por oferta, e relançar o mesmo dia cria **linha duplicada** (turmas novas já nascem com oferta — Etapa F).
- Turma que **desativa todas as ofertas** deixa de mostrar, na tela legada, o histórico lançado por oferta.
- Decisões do responsável **não implementadas**: aluno só é enturmado em curso (oferta); turma sem curso não recebe alunos nem lançamento; cadastro de turma em dois passos (criar a turma, depois "informar cursos agora? Sim/Agora não"); turno é por curso, pré-preenchido pela turma; EAD e Outros descartados.

---

### Alterações do dia — 22/10/2026

- Data da intervenção: 22/10/2026
- Conclusão: implementado e validado; alterações de ciclo de vida dos cursos e da Onda 4 (Fases 0–4) ainda não commitadas.

### Carga horária por turma e catálogo de cursos

- Removida a carga horária própria do curso; o cálculo passa a ser derivado por turma, a partir de horários, datas, dias da semana e bloqueios do calendário.
- Criado `app/utils/formatters.py` com `formatar_ch()` para apresentar minutos em formato legível.
- `app/models/academico.py` e `app/models/pedagogico.py`: ajustados os modelos e relacionamentos para calcular/exibir a carga horária por turma; a carga horária não é mais um atributo editável do curso.
- Criada a migration `d1e2f3a4b5c6_onda3c_drop_curso_carga_horaria.py` para remover a coluna legada de carga horária do curso.
- `app/registros/turmas.py`: adicionados cálculos de carga horária, filtros e dados do catálogo, com separação entre turmas de períodos vigentes e concluídos e suporte ao escopo de unidade.
- `app/templates/turmas/nova.html`, `editar.html` e `app/static/js/turmas/nova.js`, `editar.js`: incluída estimativa da carga horária durante o preenchimento; na edição, alterações de datas, dias ou horários são sinalizadas, e inconsistências são comunicadas.
- `app/templates/turmas/listar.html`: incluídas colunas de carga horária por aula e total.
- `app/registros/periodos.py` e `app/templates/periodos/certificado.html`: certificados passam a exibir a carga horária total formatada em vez dos minutos brutos.
- `app/templates/turmas/carga_horaria_curso.html` e `app/static/css/turmas/carga_horaria_curso.css`: criado o catálogo com filtros, temas, dados de professores/conclusão e apresentação para impressão.
- `app/templates/planejamento/planejamento.html`: links para consultar turmas e carga horária a partir dos cursos e temas.
- Criados testes para formatador, cálculos de carga horária, filtros e catálogo: `tests/test_carga_horaria.py`, `tests/test_carga_horaria_curso.py` e `tests/test_filtros_turmas.py`.
- Criado `docs/Plano_Acao_Carga_Horaria.md` com o escopo e as etapas de implementação.

### Modo de manutenção do sistema

- `app/services/maintenance.py`: centralizado o estado global persistido em `ConfiguracaoSistema` sob a chave `manutencao_ativa`.
- `app/auth.py`: adicionada rota POST administrativa para ativar/desativar a manutenção e disponibilizar seu estado na tela de auditoria.
- `app/templates/admin/logs.html`: adicionado painel de status e controle com proteção CSRF.
- `app/__init__.py`: durante a manutenção, usuários não administradores recebem `sistema_indisponivel.html` com HTTP 503; administradores mantêm acesso para poder desativá-la.
- `tests/test_maintenance.py`: cobertura de ativação, desativação, bloqueio de usuários e autorização administrativa.

### Ciclo de vida de cursos e preservação do histórico

- No modal de cursos, substituída a ação ambígua “Excluir” por “Inativar”. A operação continua sendo lógica: o registro do curso e os vínculos de turmas/temas permanecem no banco.
- Cursos inativos deixam de aparecer no planejamento operacional, nos filtros de temas e nas opções de novas turmas. A criação de temas vinculados a cursos inativos é rejeitada no servidor.
- Temas não são inativados em cascata: seu estado e conteúdo são preservados. Ao reativar o curso, seus temas ativos voltam a ficar disponíveis.
- O modal apresenta cursos ativos e inativos em listas separadas; cursos inativos podem ser reativados. A lista geral de cursos continua retornando apenas ativos.
- Na edição de turma, o vínculo existente a um curso já inativo pode ser mantido, sem permitir vinculá-lo a uma turma diferente. Cursos inativos não podem ser escolhidos para novas turmas.
- Ao mudar o nome do curso, o modal pede confirmação e informa que a alteração repercute nas turmas vinculadas, inclusive em períodos encerrados e em futuras emissões de certificados.
- Atualizados `app/registros/core.py`, `app/registros/turmas.py`, `app/static/js/planejamento/planejamento.js`, `app/templates/planejamento/planejamento.html` e `app/templates/turmas/editar.html`.
- `tests/test_security_regressions.py`: adicionados testes para preservação/reativação dos temas e rejeição de novos vínculos com cursos inativos.

### Ajustes adicionais no commit do dia

- `app/__init__.py`: registrado o filtro Jinja `formatar_ch`.
- `app/models/MER.md` e modelos relacionados atualizados para refletir a estrutura e os campos acadêmicos revisados.
- Ajustados formulários/templates de login, troca de senha, termos, certificado e telas de turmas/planejamento.
- Removidos arquivos JavaScript legados de alunos e um backup de banco obsoleto versionado; removida a configuração `.continue/mcpServers/new-mcp-server.yaml`.
- `backlog.md` recebeu o registro da entrega de carga horária no commit do dia; esta entrada documenta a consolidação em `backlog_desenvolvimento.md`.

### Centros de custo no formulário de períodos (23/10/2026)

- `app/models/pedagogico.py`: criado `CentroCusto` (tabela `centro_custo`) como catálogo de centros de custo por unidade, com unicidade (`nome`, `unidade_id`) e soft delete.
- `migrations/versions/d2e3f4a5b6c7_centro_custo.py`: cria a tabela e faz backfill a partir das colunas CSV `centro_custo` de `periodo_letivo`, `turma` e `turma_curso`.
- `app/registros/periodos.py`: endpoints `/centros-custo` para listar, criar, editar, inativar e reativar; edição propaga o novo nome via `_propagar_centro_custo`; impacto informado antes da confirmação.
- `app/static/js/periodos/centros_custo.js`: reescrito para ler `csrf_token` de `#periodoForm`, enviar `X-CSRFToken` em todos os POSTs, tratar erros de rede/JSON e sincronizar as checkboxes do formulário após criar/editar/inativar/reativar (incluindo criação dinâmica do container quando ausente).
- `app/templates/periodos/form.html`: integra o modal de centros de custo ao formulário de períodos e mantém o token CSRF disponível para o JavaScript.
- `app/models/MER.md`: documentada a tabela `centro_custo`, a relação com `unidade` e a regra de propagação (§7.4a, §8.11).

### Programa na oferta (`turma_curso.programa`) — 23/10/2026

- `app/models/academico.py`: `TurmaCurso` ganha a coluna `programa` (varchar(50), nullable) — programa passa a ser atributo também da oferta, além de permanecer em `Turma` (agrupador).
- `migrations/versions/a1b2c3d4e5f6_programa_oferta.py`: adiciona a coluna `programa` em `turma_curso` e faz backfill a partir de `turma.programa`.
- Correção de schema drift: o banco local estava na revisão `d2e3f4a5b6c7` e não possuía a coluna, causando `sqlalchemy.exc.ProgrammingError: coluna turma_curso.programa não existe` na query `TurmaCurso.query.filter_by(turma_id=6, ativo=True)`. Aplicado `flask db upgrade` (head `a1b2c3d4e5f6`); coluna confirmada em `information_schema`; query validada. Backup do banco salvo em `%TEMP%\pautaon_pre_programa.dump`.
- `app/models/MER.md`: documentada a coluna em §7.32, a regra em §8.10 e a migration em §11 (head atual `a1b2c3d4e5f6`); contagem atualizada para 26 revisões.

---


### Testes e verificações

- Testes de manutenção: **4 aprovados**.
- Testes focados do ciclo de vida do curso e dos temas: **3 aprovados**.
- Teste do catálogo/carga horária: **1 aprovado**.
- `node --check` para `app/static/js/planejamento/planejamento.js`, `compileall` dos módulos Python alterados e `git diff --check`: aprovados.
- Na suíte completa `tests/test_security_regressions.py`, permaneceram 2 falhas em assertions preexistentes relacionadas a isolamento entre unidades e carga horária, já observadas antes das alterações de 22/10.

### Onda 4 — Múltiplos cursos por turma: Fases 0–4

- Escopo aprovado pelo responsável: especificação de 390 linhas (turma como agrupador lógico, oferta `TurmaCurso`, plano de 9 fases). Fase 0 (higiene de migrations) e Fase 1 (modelo + migration com backfill) executadas nesta data; demais fases seguem o plano.
- **Fase 0 — heads unificadas:** existiam dois heads Alembic (`b7c1d2e3f4a5` e `d1e2f3a4b5c6`), que faziam `flask db upgrade` falhar. Criada a revision de merge `b02f2051bc1e` e aplicado upgrade completo no PostgreSQL local.
- **Fase 0 — drift de banco:** o banco local (restaurado de dump sem stamp) tinha o ramo `5a676f37b9a3` parcialmente aplicado (colunas já em DATE/TIME e sequência existente, mas ENUMs ainda em VARCHAR). A revision foi tornada **idempotente** com guards por `pg_attribute` (`_tipo_atual`/`_alterar_tipo`) antes de cada conversão; valores ENUM/CAST verificados como seguros antes da execução.
- **Fase 1 — modelo:** criado `TurmaCurso` em `app/models/academico.py` (tabela `turma_curso`): `UNIQUE(turma_id, curso_id)`, índice único parcial do `principal` (máximo um curso principal por turma ativa; `postgresql_where` + `sqlite_where`), atributos próprios de professor/turno/dias/horários/datas/centro de custo (NULL = compartilhado da turma). `Inscricao` ganhou `turma_curso_id` (nullable na transição) com relacionamento `turma_curso` — backref `inscricoes_oferta` **sem cascade** para proteger histórico de matrícula. Export em `app/models/__init__.py`.
- **Fase 1 — migration:** `311d554dfd6e` (down_revision `b02f2051bc1e`) cria tabela/índices, adiciona a coluna em `inscricoes` e executa **backfill portável em SQL puro**: uma oferta por turma legada com curso (atributos copiados da turma, `principal=false`) e vínculo das inscrições à oferta; reforço idempotente da sequência `turma_curso_id_seq` (lição de `inscricoes.id`). O autogenerate propôs DROP das colunas de auditoria de `curso` e ~10 alter comments (drift pré-existente) — removidos manualmente da revision e registrados como dívida para uma sincronia dedicada.
- **Fase 1 — verificação:** criado `scripts/verificar_onda4_fase1.py` (padrão `verificar_sec01.py`), executado no PG local: 3 turmas com curso → 3 ofertas, 0 inscrições órfãs, 0 duplicatas, no máximo 1 principal por turma, 0 divergências com o legado — exit 0.
- **Fase 1 — testes:** criados `tests/test_turma_curso.py` (7 cenários: oferta única, repetição bloqueada pelo UNIQUE, mesmo curso em turmas distintas, principal por turma via índice parcial, inscrição↔oferta). Corrigidos fixture obsoleto de `tests/test_carga_horaria.py` (agora usa `SQLiteTestConfig` como os demais testes) e `formatar_ch` para valores negativos (retorna "—", conforme docstring). Também atualizado `test_calcular_dias_com_bloqueios` para a API pós-Onda 2B de `DiaBloqueado` (`tipo`/`descricao`/`periodo_letivo_id`).
- Suíte completa após as fases: **97 aprovados**, restando apenas as 2 falhas preexistentes de `/cursos` já listadas acima (existem em HEAD, fora do escopo da Onda 4).
- **Fase 2 — serviço de regras:** criado `app/services/turma_curso.py` com cadastro incremental (`adicionar_oferta`), edição (`editar_oferta`), `definir_principal` em swap atômico, `desativar_oferta` com guarda (impede ficar 2+ ativas sem principal) e validação do `UNIQUE` pleno — o banco também bloqueia reofertar curso cuja oferta foi desativada (histórico); o serviço antecipa a regra com mensagem clara. Principal obrigatório ao passar a ter 2+ ofertas; opcional na oferta única. Espelhamento legado apenas em turma sem curso legado com oferta única — sem dual-write nas turmas do backfill.
- **Fase 2 — rotas/UI:** novas rotas em `app/registros/turmas.py` (`/turma/<id>/ofertas`, `…/ofertas/nova`, `/turma/oferta/<id>/editar|principal|desativar`, perfis admin/pedagógico/secretaria com isolamento por unidade) e a tela `app/templates/turmas/ofertas.html` (lista de ofertas com principal/professor/turno/horários/vigência/centro de custo, edição inline, formulário incremental com o aviso "Deseja adicionar outro curso?" após salvar). Botão "CURSOS DA TURMA" adicionado à ficha em `detalhe.html`.
- **Fase 2 — testes:** `tests/test_turma_curso_fase2.py` (14 cenários: serviço + rotas). Suíte completa: **111 aprovados**, apenas as 2 falhas preexistentes de `/cursos` permanecem.
- Documentação: `app/models/MER.md` sincronizado (§7.32 nova tabela, §8.10 regras da Onda 4, §10 histórico, §11/§11.1 cadeia e ressalva 1 resolvida, §12.12 dívida parcial).
- **Fix de migration (PG):** `8c4e1f9a7d32` adiciona as três colunas do `AuditoriaMixin` (`updated_by_id`/`updated_by_name`/`updated_at`) que faltavam em `turma_curso` no PostgreSQL (a revision original `311d554dfd6e` omitiu-os da `create_table`). Guards idempotentes por `sa.inspect(bind)`; FK `ON DELETE SET NULL` no PG.
- **Fase 3 — concomitância de horários (§5):** implementada em `_validar_horario_concomitante` (`app/services/turma_curso.py`). Detecção por tripla condição: dias em comum (CSV parseado e normalizado) + sobreposição estrita de horário (adjacência permitida) + vigências interceptam (NULL = aberto). Chamada por `adicionar_oferta` e `editar_oferta` (esta última com `exclude_oferta_id` para ignorar a própria). `ValueError` com mensagem indicando o curso conflitante.
- **Fase 3 — testes:** `tests/test_turma_curso_fase3.py` (20 cenários: unitários de `_parse_dias`/`_sobreposicao_horario`/`_sobreposicao_vigencia`, serviço sobreposição total/parcial/dias distintos/vigência disjunta/adjacência/sem dados, edição cria/remove conflito, rota POST com conflito → flash). Suíte completa: **131 aprovados**, 2 falhas preexistentes.
- **Fase 4 — frequência e diário por oferta:** migration `e7f3a1b9c4d5` (down_revision `8c4e1f9a7d32`) adiciona `turma_curso_id` (nullable FK) a `frequencia` e `registro_aula`, **substitui** o UNIQUE legado `uix_frequencia_aluno_turma_data` pelos índices únicos **parciais** `uix_freq_legado` (`aluno_id`,`turma_id`,`data` WHERE `turma_curso_id IS NULL`) e `uix_freq_oferta` (`aluno_id`,`turma_curso_id`,`data` WHERE NOT NULL), cria `ix_frequencia_turma_curso_data`/`ix_registro_aula_turma_curso_data` e faz backfill apenas em turmas com oferta única. Em `app/services/turma_curso.py`: `resolver_oferta_lancamento` (oferta única escolhida sem validação extra; 2+ ofertas exige escolha e valida vigência/dia/tema), `datas_esperadas_oferta` (agenda por oferta) e `_alunos_da_oferta` (pauta por oferta com `EXISTS`, sem duplicar aluno). Leitores/escritores em `app/utils/logica.py` (`salvar_frequencia`/`carregar_frequencias`), `app/utils/frequencia.py` (`contar_pendencias_frequencia`/`_pendencias_por_ofertas`), `app/main/dashboard_professor.py` (`_aulas_pendentes`) e rotas/templates (`core.py`, `turmas.py`, `lancar.html`, `imprimir_pauta.html`, `detalhe.html`, `professor.html`). Regra "turma em andamento" em `adicionar_oferta` (grava hoje quando a 2ª+ oferta entra em turma já iniciada e viva; flash na rota). "Hoje" local via `get_local_now().date()` nos caminhos novos.
- **Fase 4 — correção do caminho legado:** `salvar_frequencia` e `carregar_frequencias`, no ramo legado (`turma_curso_id IS NULL`), passaram a filtrar `turma_curso_id IS NULL` em `Frequencia` e `RegistroAula`; assim um lançamento legado (turma sem oferta ativa) não reaproveita/sobrescreve a linha de uma oferta (mesmo `turma_id`/`data`). O ramo por oferta permanece inalterado.
- **Fase 4 — testes e verificação:** `tests/test_turma_curso_fase4.py` (cenários a–i: resolver sem validação na oferta única, segunda oferta não sobrescreve, legado não duplica/não confunde com oferta, `_data_bate_dias_semana` com acento/variante, vigência/dia/tema no resolver, filtro de aluno fora da pauta, inscrições NULL com 1 vs 2+ ofertas) e `tests/test_turma_curso_fase4_dash.py`; `scripts/verificar_onda4_fase4.py` (só leitura, exit 0/1: colunas, índices únicos parciais, ausência do UNIQUE antigo, FKs, ofertas inconsistentes, turmas 2+ sem principal). Suíte completa: **155 aprovados**, apenas as 2 falhas preexistentes de `/cursos`.
- **Pendências da Onda 4 (registro histórico de 22/10; status atualizado na L3):** Fases 5–7 — autorização por professor ofertado (§8), turno por curso e centro de custo compartilhado/individual (§9), transferências por oferta (§10), certificados/indicadores (§12). **Fases 8–9 e NOT NULL final em `inscricoes.turma_curso_id` aplicadas** (`c3d4e5f6a7b8` T1 + `d4e5f6a7b8c9` B5). **D5 conselho — CONCLUÍDO (D5.1–D5.5, 24–25/10/2026)**; ver §8.2/§12.18 do MER. **D3b-2 (reduzido):** ficha do aluno e histórico já são por oferta (D5.4); permanecem por `turma_id` a frequência/diário do ramo legado, o BI de frequência, `freq_geral` (listagem de turmas e BI) e os relatórios. Com 2+ ofertas a ficha da turma deixou de oferecer a **pauta mensal** (só "Pauta Completa" por oferta). Resta um `date.today()` em `app/main/dashboard_professor.py` (~linha 123, `render_dashboard_professor`). **Consequência da correção do legado:** `carregar_frequencias` no caminho legado passou a filtrar `turma_curso_id IS NULL`; registros de ofertas desativadas não aparecem na tela legada. Colunas legadas de `Turma` mantidas com compatibilidade controlada (§14).

### Arquivos principais

`app/services/maintenance.py`, `app/auth.py`, `app/__init__.py`, `app/registros/core.py`, `app/registros/turmas.py`, `app/registros/periodos.py`, `app/models/academico.py`, `app/models/pedagogico.py`, `app/utils/formatters.py`, `app/static/js/planejamento/planejamento.js`, `app/static/js/turmas/nova.js`, `app/static/js/turmas/editar.js`, `app/templates/admin/logs.html`, `app/templates/planejamento/planejamento.html`, `app/templates/turmas/nova.html`, `app/templates/turmas/editar.html`, `app/templates/turmas/listar.html`, `app/templates/turmas/carga_horaria_curso.html`, `app/templates/periodos/certificado.html`, `migrations/versions/d1e2f3a4b5c6_onda3c_drop_curso_carga_horaria.py`, `tests/test_maintenance.py`, `tests/test_carga_horaria.py`, `tests/test_carga_horaria_curso.py`, `tests/test_filtros_turmas.py` e `tests/test_security_regressions.py`.

Onda 4 (Fases 0 e 1): `app/models/academico.py`, `app/models/matriculas.py`, `app/models/__init__.py`, `app/utils/formatters.py`, `migrations/versions/5a676f37b9a3_...py` (idempotência), `migrations/versions/b02f2051bc1e_merge_heads_onda3c_inscricoes_seq.py`, `migrations/versions/311d554dfd6e_onda4_fase1_turmacurso_inscricao_turma_.py`, `scripts/verificar_onda4_fase1.py`, `tests/test_turma_curso.py`, `tests/test_carga_horaria.py` e `app/models/MER.md`.

Onda 4 (Fase 2): `app/services/turma_curso.py`, `app/registros/turmas.py`, `app/templates/turmas/ofertas.html`, `app/templates/turmas/detalhe.html` e `tests/test_turma_curso_fase2.py`.

Onda 4 (Fix PG + Fase 3): `migrations/versions/8c4e1f9a7d32_onda4_fase1_fix_turma_curso_updated_by_id.py`, `app/services/turma_curso.py` e `tests/test_turma_curso_fase3.py`.

Onda 4 (Fase 4): `migrations/versions/e7f3a1b9c4d5_onda4_fase4_turma_curso_id_frequencia.py`, `app/services/turma_curso.py`, `app/utils/logica.py`, `app/utils/frequencia.py`, `app/main/dashboard_professor.py`, `app/registros/core.py`, `app/registros/turmas.py`, templates (`frequencia/lancar.html`, `frequencia/imprimir_pauta.html`, `turmas/detalhe.html`, `dashboard/professor.html`), `scripts/verificar_onda4_fase4.py`, `tests/test_turma_curso_fase4.py`, `tests/test_turma_curso_fase4_dash.py` e `app/models/MER.md`.

---

### Alterações do dia — 21/10/2026

- Data da intervenção: 21/10/2026
- Conclusão: concluído

Implementação completa da exibição de carga horária calculada em tempo real em formulários, listagens e certificados, com correção de bugs no template de relatório de carga horária.

### Etapa 1 — Limpeza do modal de Cursos

- Confirmado que o modal de cursos em `planejamento.html` não possui campo de carga horária (somente exibição calculada).
- A coluna "C.H. Total" na tabela do modal usa `cargas_curso.get(c.id)` como informação calculada somente leitura.
- Nenhuma alteração necessária em `pedagogico.py` ou `core.py` (sem referências residuais a `carga_horaria` como campo de entrada).

### Etapa 2 — Exibição de C.H. calculada no formulário de Turma

- `nova.html`: Bloco informativo já implementado com exibição de C.H. por Aula e C.H. Total Estimada em tempo real.
- `nova.js`: Lógica de cálculo já implementada com listeners nos campos de horário, dias e datas.
- `editar.html`: Bloco informativo adicionado (linhas 154-169) com estilo `alert-info`.
- `editar.js`: Expandido para incluir lógica de recálculo de C.H. (funções `horaParaMinutos`, `formatarCH`, `contarDiasAula`, `recalcularCH`) e detecção de mudança de horário na confirmação (`handleSubmit`).
- Mensagem de confirmação atualizada para incluir recálculo de carga horária.

### Etapa 3 — C.H. Aula e Total na listagem de Turmas

- `listar.html`: Adicionadas duas colunas na tabela: "C.H./Aula" e "C.H. Total" (após coluna "Horário").
- `turmas.py` (função `turma`): `formatar_ch` adicionado ao contexto do template.

### Etapa 4 — Certificado com C.H. formatada corretamente

- `periodos.py`: Import `formatar_ch` adicionado.
- `periodos.py` (`periodo_letivo_relatorio_certificado`): `carga_total` convertido para string formatada via `formatar_ch(turma.carga_horaria_total)` antes de passar ao template.
- `certificado.html`: Ajustado para exibir `{{ item.carga_total }}` (já formatado) em vez de `{{ item.carga_total ~ 'h' }}`.

### Etapa 5 — Correção e completude do template carga_horaria_curso.html

- `turmas.py` (`carga_horaria_turmas`): Adicionado suporte ao filtro `unidade_id` para usuários globais (admin/gerência). Usuários locais continuam com filtro fixo via `get_unidade_id()`.
- `turmas.py`: Lista de todas as unidades, períodos, professores e cursos passada ao template para usuários globais.
- `carga_horaria_curso.html`: Reescrito completamente:
  - Cabeçalho atualizado com título "Carga Horária por Curso/Turma" e botão "Ir para CRUD de Cursos".
  - Filtros corrigidos: Unidade (somente para admin/gerência), Período Letivo, Professor, Curso.
  - Tabela com colunas: #, Turma, Curso, Professor, Período, Dias/Semana, Horário, C.H. Aula, C.H. Total.
  - Botão de impressão (`window.print()`) com CSS para ocultar filtros e botões na impressão.

### Etapa 6 — Aviso de inconsistência na edição de turma

- `editar.js`: Mensagem de confirmação expandida para incluir horário na detecção de alterações.
- `turmas.py` (`editar_turma`): Após commit bem-sucedido, verificação de inconsistências:
  - Se `dias_semana` definido mas `carga_horaria_total` é `None` → flash de aviso sobre horário ausente.
  - Se `dias_semana` definido, datas definidas, mas `dias_aula_efetivos()` retorna 0 → flash de aviso sobre 0 dias de aula.
  - Em caso de inconsistência, redireciona de volta para a tela de edição em vez da listagem.

### Etapa 7 — Testes, documentação e backlog

- `test_carga_horaria.py` (novo): Testes unitários para:
  - `formatar_ch()`: 60 min → "1h", 90 min → "1h30min", 1800 min → "30h", None → "—", 0 → "—".
  - `Turma.carga_horaria_aula`: com e sem horários, hora_fim ≤ hora_inicio.
  - `Turma.carga_horaria_total`: com dias_semana, datas e horários válidos/inválidos.
  - `calcular_dias_aula_turma()`: turma sem datas, turma com todos os dias bloqueados.
- Docstrings revisadas em `turmas.py` (função `carga_horaria_turmas`) e `academico.py` (properties já existem).
- `backlog.md`: Entrada adicionada documentando as mudanças desta implementação.

### Arquivos principais

`app/templates/turmas/nova.html`, `app/templates/turmas/editar.html`, `app/static/js/turmas/nova.js`, `app/static/js/turmas/editar.js`, `app/templates/turmas/listar.html`, `app/registros/turmas.py`, `app/registros/periodos.py`, `app/templates/periodos/certificado.html`, `app/templates/turmas/carga_horaria_curso.html`, `tests/test_carga_horaria.py` e `backlog.md`.

### Reformulação de `carga_horaria_curso.html` — Catálogo de Cursos, Corpo Docente Concluído e Presença em Turmas

- **Motivação:** Em vez de uma listagem operacional de turmas individuais, a tela passou a focar no catálogo de Cursos, agregando dados pedagógicos (descrição, temas), histórico de professores que concluíram o período letivo e métrica percentual de frequência do curso nas turmas encerradas.
- **`app/registros/turmas.py` (`carga_horaria_turmas`):**
  - Mantidos os filtros de Unidade (para usuários com papéis globais `admin`/`gerencia`), Período Letivo, Professor e Curso.
  - Quando os filtros de período letivo ou professor são informados, a busca filtra diretamente os cursos com turmas ativas vinculadas a esses critérios.
  - Consulta os temas associados de cada curso (`TemaAula` ativos ordenados por `ordem`).
  - Lista os professores associados às turmas ativas do curso/período.
  - Calcula o percentual de turmas do curso sobre o total de turmas no escopo dos filtros ($\frac{\text{turmas do curso}}{\text{total de turmas}} \times 100$).
- **`app/templates/turmas/carga_horaria_curso.html`:**
  - Reformulada a tabela para uma apresentação limpa por Curso (Nome, badges com ID e total de temas).
  - Coluna de temas com lista expansível (*accordion*) que exibe os primeiros 3 temas e oculta os excedentes para leitura ágil.
  - Badges verdes com ícone de professor para docentes que concluíram períodos letivos.
  - Indicador visual em barra de progresso com porcentagem e contadores de turmas concluídas.
- **Arquivos alterados:** `app/registros/turmas.py`, `app/templates/turmas/carga_horaria_curso.html`.

---

### Links de curso em `planejamento.html` → `carga_horaria_curso.html`

- **Motivação:** O nome do curso na página de planejamento não levava a lugar nenhum; o relatório de carga horária por curso existia mas só era acessível via menu lateral.
- **`planejamento.html` — tabela de Temas:** O badge da coluna "Curso" passou a ser uma âncora `<a>` com `href="{{ url_for('registros.carga_horaria_turmas', curso_id=tema.curso_id) }}"`. O estilo visual (badge colorido) foi preservado; o `<span>` foi convertido para `<a>` mantendo as mesmas classes CSS.
- **`planejamento.html` — modal Cursos da Unidade:** A célula com o nome do curso na tabela `#tabelaCursos` passou a ser um link com `target="_blank"` e ícone `bi-box-arrow-up-right`, indicando visualmente que abre em nova aba sem fechar o modal.
- **`carga_horaria_curso.html` — cabeçalho contextual:** Quando a página recebe `?curso_id=N`, o título passa a exibir "Turmas do Curso: **<nome>**" em vez do genérico "Carga Horária por Curso/Turma". Um subtítulo com "Filtrado por curso — ver todos" permite voltar à visão completa. O lookup do nome é feito via `cursos | selectattr('id', 'equalto', curso_id) | first` (Jinja2 3.x, sem dependências extras).
- **Sem nova rota:** A rota existente `GET /turmas/carga-horaria` já aceitava `?curso_id=` como filtro — bastou gerar o link com o parâmetro correto via `url_for`. Nenhum código Python foi alterado.
- **Arquivos alterados:** `app/templates/planejamento/planejamento.html`, `app/templates/turmas/carga_horaria_curso.html`.

### Correção de bug — Colunas de auditoria ausentes em `inscricoes`, `curso` e `conselho_classe`

- **Sintoma:** `sqlalchemy.exc.ProgrammingError: coluna inscricoes.updated_by_id não existe` ao tentar enturmar um aluno.
- **Causa raiz:** A migration `a9f3c8e2d1b7` (`add_audit_columns_core_tables`) nunca foi executada contra o banco de dados restaurado de dump antigo. O registro em `alembic_version` apontava para `c4d5e6f7a8b9` (filho de `a9f3c8e2d1b7`), fazendo o Alembic acreditar que a migration já estava aplicada — mas as colunas não existiam de fato.
- **Diagnóstico:** Inspecionadas as colunas reais da tabela `inscricoes` via `SQLAlchemy.inspect`; confirmado que `updated_by_id`, `updated_by_name` e `updated_at` estavam ausentes. Mesma situação detectada em `curso` e `conselho_classe`; `turma`, `tema_aula` e `registro_aula` já estavam corretas.
- **Correção aplicada:** Script pontual executou `ALTER TABLE … ADD COLUMN` diretamente no banco para as três tabelas afetadas, replicando exatamente o DDL da migration:
  - `updated_by_id INTEGER REFERENCES "user"(id) ON DELETE SET NULL`
  - `updated_by_name VARCHAR(100)`
  - `updated_at TIMESTAMP`
- **Impacto:** Nenhuma alteração de código — apenas ajuste de schema. O `alembic_version` permanece em `c4d5e6f7a8b9` (consistente com o estado esperado). A funcionalidade de enturmar alunos voltou a operar normalmente.

---

### Alterações do dia — 20/10/2026

- Data da intervenção: 20/10/2026
- Conclusão: concluído
- Commits: `76dcece` (00:36), `cc83ff0` (00:59), `6bc7571` (10:43), `c75bf49` (10:50), `f944adf` (11:43), `5e0a4ec` (14:49) e `b31f0f4` (15:07)

Refatoração visual da interface, ajustes no planejamento pedagógico e criação das páginas de Termos de Serviço e Política de Privacidade.

### Identidade visual e UX (`76dcece` e `cc83ff0`)

- Refatoração abrangente da interface para garantir consistência visual, responsividade e UX em múltiplos módulos: Painel (`dashboard/index`, `professor`, `secretaria`), Relatórios (`geral`, `relatorio_alunos`), Conselho (`perguntas` + `conselho.js`) e transições de atendimento.
- Removido o backup obsoleto `dashboard/indexOLD.html`.
- Ajustes de suporte em `app/main/secretaria.py` e `app/registros/turmas.py`.
- Painel de administração de usuários (`admin/painel_admin.html`) alinhado à nova identidade visual, com melhoria na usabilidade da listagem; ajustes em `informacao_padrao` (rota e template).

### Planejamento pedagógico (`6bc7571`, `c75bf49` e `f944adf`)

- Paginação criada para as listas de cursos e temas.
- Corrigida a exibição da `carga_horaria` no modal de Cursos.
- Reformulado o modal de Dias Bloqueados e concluída a impressão de temas com o novo template `impressao_temas.html` (+ CSS/JS dedicados).
- Visualização e exportação de dias sem aula agora consideram apenas os dias dentro do intervalo do período letivo correspondente (`registros/core.py` e `registros/periodos.py`).

### Termos de Serviço e Política de Privacidade (`5e0a4ec` e `b31f0f4`)

- Criadas as rotas `/termos_servico` e `/politica_privacidade` em `app/main/home.py`, com conversor simples de Markdown para HTML (`_simple_markdown_to_html`, sem dependências externas).
- Novos templates `app/templates/termos/termos_servico.html` e `app/templates/termos/politica_privacidade.html`, com card de documento, caixas de aviso/contato e bloqueio de cópia/print/F12.
- `login.html` atualizado para expor os links de Termos de Serviço e Política de Privacidade.
- Política de Privacidade formatada no mesmo padrão dos Termos, com o texto da política incorporado diretamente ao template (fonte: `app/static/uploads/politica_de_privacidade_pautaon.md`).

### Arquivos principais

`app/main/home.py`, `app/templates/termos/termos_servico.html`, `app/templates/termos/politica_privacidade.html`, `app/templates/login.html`, `app/templates/admin/painel_admin.html`, `app/templates/dashboard/{index,professor,secretaria}.html`, `app/templates/relatorios/{geral,relatorio_alunos}.html`, `app/templates/conselho/perguntas.html`, `app/planejamento` (templates/JS/CSS de planejamento e impressão de temas), `app/registros/core.py` e `app/registros/periodos.py`.

### Injeção do backup antigo no ambiente local (operação)

- Restaurado o dump `backup_20261020_204018.sql` (pg_dump 17.2) no PostgreSQL local (servidor 18.6), banco `pautaon`.
- Como o dump não traz `DROP`/`CREATE DATABASE`, o banco foi recriado vazio antes do import (`DROP`/`CREATE DATABASE pautaon`), executado com `ON_ERROR_STOP=1` e seguido de `ANALYZE`.
- Backup de segurança do estado local gerado antes da operação em `instance/backups/local_antes_do_inject_20261020.sql`.
- Verificação pós-import: `alembic_version=c4d5e6f7a8b9`; usuarios=18, cursos=11, turmas=1, alunos=1154. Observação: o dump contém apenas o banco — `instance/uploads/` (fotos/documentos) precisa ser copiado à parte.

### BI — análise da Central de Indicadores (análise)

- Mapeado o fluxo UI → rotas (`bi_routes.py`) → executor (`bi.py`) → funções (`bi_alunos.py`). Constatado que a UI expõe só 3 filtros (Período, Unidade, Turno), enquanto as funções aceitam 7.
- Filtro `turno` é funcional apenas nos indicadores baseados em status; nos demais é descartado silenciosamente por `inspect.signature` (filtro decorativo). `curso_id`/`turma_id`/`professor_id`/`data_*` são parâmetros mortos (a UI não os envia).
- Semântica divergente de "Todos"/período vigente entre indicadores de status e de query; `INS-006`/`INS-007` constam no catálogo mas não são implementados, gerando erro 400 com mensagem enganosa.
- Identificada **falha crítica de restrição por unidade**: `_escopar_unidade_status` só impunha escopo ao subconjunto `INDICADORES_STATUS_ALUNO`; os demais ~50 indicadores confiavam no `unidade_id` vindo da querystring, permitindo leitura entre unidades (IDOR) e visão global ao selecionar "Todas".

### BI — correção de restrição por unidade (`app/relatorios/bi_routes.py`)

- Guardião único `_escopar_unidade(filtros)` passa a impor `unidade_id = get_unidade_id()` a **todos** os indicadores. Unidade alheia ou ausente sem vínculo → `403`; "Todas"/`None` é forçado para a própria unidade do usuário.
- Preservado o bypass global de `admin`/`gerencia` via constante `_ROLES_GLOBAIS_BI`. Removido o import órfão de `INDICADORES_STATUS_ALUNO`; atualizados os 2 pontos de chamada.
- Mudança contida na camada de rota: `get_unidade_id` (uso global) e as funções de `bi_alunos.py`/`executar_indicador` ficaram intocados. Confirmado que as funções filtram de fato por `unidade_id`, então a correção não é no-op.
- Sem regressão: os testes de BI já falhavam antes pelo listener de auditoria (`flush` de ORM sem `current_user` no setup), não pela alteração. Lógica validada com 8 cenários sob mock. Verificado no banco que nenhum papel restrito (2 pedagógico, 5 secretaria) tem `unidade_id` nulo — risco de lockout nulo.

### BI — encadeamento dos filtros Unidade → Período (`app/templates/relatorios/bi.html`)

- Filtros reordenados para **Unidade → Período Letivo → Turno**.
- Cada `<option>` de período agora carrega `data-unidade`; um listener `change` na unidade repopula o seletor de período exibindo apenas os períodos daquela unidade.
- "Todos" do período passa a significar "Todos os períodos desta unidade"; com Unidade="Todas" a lista volta a ser completa. Trocar de unidade reseta automaticamente um período incompatível — elimina combinações inválidas (corretamente, já que o backend protegia mas devolvia 400/vazio).
- Mesmos `id`s preservados, então as leituras em `btnExecutar` e `btnExportarXlsx` seguem funcionando. Sintaxe Jinja2 validada (`JINJA_OK`).

### Análises complementares (sem alteração de código)

- Estudo de impacto para permitir C.H. de aula em horas + minutos (incrementos de 15 min) e o reflexo no cálculo da C.H. Total e na exposição do certificado. Recomendação: armazenar minutos como inteiro (Opção A) para preservar exatidão, com formatador único, migração `horas × 60` e ajustes em rotas/UI/certificado.

### Notificações por e-mail (criação de usuário e reset de senha)

- Novo módulo `app/utils/disparo_email.py` com `send_email()`/`send_async_email()`: dispara e-mails em uma `Thread` em background (assíncrono, sem travar a requisição), usando `Flask-Mail` (nova extensão `mail` registrada em `app/extensions.py` e inicializada em `app/__init__.py`).
- `config.py` ganhou as chaves SMTP (`MAIL_SERVER`, `MAIL_PORT`, `MAIL_USE_TLS`/`MAIL_USE_SSL`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_DEFAULT_SENDER`) lidas de `.env` (`smtp.gmail.com:587`, TLS, conta Google Workspace).
- `auth.cadastrar_usuario` (POST `/admin/cadastrar`) agora renderiza `emails/novo_usuario.html` (nome, e-mail e senha temporária) e chama `send_email()` logo após o `commit()`/`register_security_log("Cadastro Local", ...)`.
- `auth.resetar_senha` agora renderiza `emails/senha_redefinida.html` (nome e nova senha temporária) e chama `send_email()` logo após o `register_security_log("Reset de Senha", ...)`.
- Templates criados em `app/templates/emails/`: `base_email.html` (layout compartilhado), `novo_usuario.html` e `senha_redefinida.html` — todos avisando que a troca de senha é obrigatória no primeiro acesso.
- Falha de envio de e-mail: `send_async_email()` captura a exceção, grava `app.logger.error(...)` e registra um `LogAcao` com `acao="Erro E-mail"` (via `_gravar_log_background()`, seguro dentro da thread com `app.app_context()`), além de disparar automaticamente um e-mail de alerta para `ADMIN_EMAIL` (novo, em `config.py`/`.env`) através de `_notificar_admin_sobre_falha()` — sem recursão infinita, controlado pelo flag `is_alert_email`.
- Sucesso no envio também é registrado em `LogAcao` com `acao="Disparo de E-mail"`.
- Rota de teste criada: `GET /main/teste-email?para=...` (`app/main/rota_disparo_email.py`) para validar a integração SMTP fora do fluxo de cadastro/reset, respondendo em JSON.
- O contexto do usuário atual (`id`/`nome`/`unidade_id`/IP) é capturado ANTES de abrir a thread (dentro do request ativo), pois `current_user`/`request` não existem fora do contexto de requisição — evita repetir o mesmo tipo de erro já documentado no listener de auditoria.
- Pendência de deploy: `Flask-Mail==0.10.0` está instalado no `.venv` local, mas ainda não foi adicionado ao `requirements.txt` — precisa entrar antes de um novo deploy, senão o `import flask_mail` falhará no servidor.
- Status: ainda não commitado (working tree) — `app/utils/disparo_email.py`, `app/main/rota_disparo_email.py` e `app/templates/emails/` constam como não rastreados no `git status`; `app/auth.py`, `config.py`, `app/extensions.py`, `app/__init__.py` e `app/main/__init__.py` estão modificados aguardando commit.

### Arquivos principais (neste acréscimo)

`app/relatorios/bi_routes.py`, `app/templates/relatorios/bi.html`, `app/utils/disparo_email.py`, `app/main/rota_disparo_email.py`, `app/templates/emails/{base_email,novo_usuario,senha_redefinida}.html`, `app/auth.py`, `app/extensions.py`, `app/__init__.py`, `app/main/__init__.py` e `config.py`. Alterações ainda não commitadas (working tree).

---

### Alterações do dia — 19/10/2026

- Data da intervenção: 19/10/2026
- Conclusão: concluído

Atualizações realizadas no planejamento pedagógico:

- Acesso liberado para `secretaria` em `/planejamento`, nos CRUDs de cursos, temas e níveis e nas operações de conselho, com validação da unidade nos registros e turmas alvo.
- Corrigida a resposta dos endpoints de cursos para retornar `carga_horaria` após criação e na listagem, permitindo que a interface exiba o valor gravado.
- A unicidade de `Nivel.nome` passou a ser por unidade. A migration `c4d5e6f7a8b9_niveis_unicos_por_unidade` remove a restrição global e cria UNIQUE (`nome`, `unidade_id`).
- Adicionada mensagem específica para tentativa de cadastrar um nível que já existe na mesma unidade.
- Migration aplicada ao banco configurado; `flask db current` confirmou `c4d5e6f7a8b9 (head)`.
- Incluída regressão para acesso de secretaria ao conselho na própria unidade e bloqueio de outra unidade. A execução automatizada não foi possível neste ambiente porque `pytest` não está instalado.

Arquivos principais: `app/planejamento.py`, `app/registros/core.py`, `app/models/pedagogico.py`, `migrations/versions/c4d5e6f7a8b9_niveis_unicos_por_unidade.py` e `tests/test_security_regressions.py`.

---

### Alterações do dia — 29/09/2026

- Data da intervenção: 29/09/2026
- Início da correção: 2026-09-29 16:30
- Conclusão da correção: 2026-09-29 16:38

Esta atualização inclui:
- Integração do plugin `chartjs-plugin-datalabels` para exibir percentuais e rótulos nos gráficos da Central de BI (pizza, rosca, barras e linhas).
- Implementação de exportação de relatórios em `.xlsx` via rota `/relatorios/bi/exportar/xlsx` usando `xlsxwriter`.
- Adição de botões de exportação (XLSX e PNG) na interface da Central de BI.
- Atualização da documentação dos indicadores (`app/relatorios/indicadores.md`) com novas categorias (SOC, DIV, ATD, CRU) e detalhes de exportação.
- Atualização do README com seção da Central de BI e detalhes de exportação.

- Data da intervenção: 11/09/2026
- Início da correção: 2026-09-11 18:35
- Conclusão da correção: 2026-09-11 18:55

Este complemento resolve a pendência descrita acima e acrescenta ajustes de paridade/robustez encontrados durante a revisão. Para aplicar em outro repositório, siga os passos abaixo após conferir se os arquivos daquele repositório já receberam a primeira parte da funcionalidade.

### Corrigido no repositório (checkout local)

A correção aplicada neste checkout foi a seguinte:

- Removida a falha na template de edição causada por `div` não definida e por um trecho literal `` `n `` no stepper.
- Ajustado o stepper da etapa de edição para incluir a Etapa VI corretamente e evitar que a renderização do formulário quebrasse com erro de template.
- Reativado o carregamento do script de situação escolar na edição, garantindo que campos condicionais e autocomplete funcionem na tela de alteração do aluno.
- Reforçada a lógica de persistência em `app/routes/registros/alunos.py` para limpar a situação escolar vazia, salvar `status`/`status_outro` e limitar o autocomplete a termos com pelo menos 2 caracteres.
- Ajustado `app/static/js/alunos/situacao_escolar.js` para criar sugestões com `document.createElement` e evitar injeção de HTML por nomes vindos do banco.
- Atualizado `app/static/js/alunos/editar.js` para detectar etapas dinamicamente e respeitar a etapa 6 no passo final.

### Resumo do que foi concluído

1. As colunas `status` e `status_outro` foram adicionadas ao modelo `SituacaoEscolar`.
2. A função `_salvar_situacao_escolar(aluno)` passou a salvar `status_escolar` e `status_escolar_outro`.
3. A função `_salvar_situacao_escolar(aluno)` passou a apagar a situação escolar existente quando o formulário da etapa VI é enviado totalmente vazio.
4. O endpoint `/alunos/instituicoes` passou a retornar lista vazia para termos com menos de 2 caracteres.
5. O autocomplete passou a consultar nomes distintos de instituição e ignorar registros com nome nulo.
6. O JavaScript `situacao_escolar.js` deixou de montar botões por `innerHTML` e passou a usar `document.createElement`, reduzindo risco de HTML injetado por nomes cadastrados no banco.
7. A tela `app/templates/alunos/editar.html` recebeu também a Etapa VI: Situação Escolar, preenchendo os campos com dados existentes de `aluno.situacao_escolar`.
8. O arquivo `app/static/js/alunos/editar.js` foi ajustado para detectar etapas dinamicamente, aceitando a nova etapa 6.
9. O script `scripts/migrate_situacao_escolar.py` passou a adicionar `status` e `status_outro` por `ALTER TABLE ... ADD COLUMN` somente quando ausentes.
10. O schema estático `scripts/postgres_schema.sql` recebeu a tabela `situacao_escolar` com as colunas finais e o índice `ix_situacao_escolar_unidade_nome`.

### Arquivos alterados nesta parte

| Arquivo | O que fazer no repositório paralelo |
| --- | --- |
| `app/models.py` | Adicionar `status` e `status_outro` em `SituacaoEscolar`, se ainda não existirem. |
| `app/routes/registros/alunos.py` | Atualizar `_salvar_situacao_escolar` e endurecer o endpoint `/alunos/instituicoes`. |
| `app/static/js/alunos/situacao_escolar.js` | Substituir a renderização do autocomplete por criação segura de elementos DOM. |
| `app/templates/alunos/editar.html` | Adicionar indicador 6, criar a Etapa VI preenchida e carregar `situacao_escolar.js`. |
| `app/static/js/alunos/editar.js` | Trocar o controle fixo de 5 etapas por detecção dinâmica de `.form-step`. |
| `scripts/migrate_situacao_escolar.py` | Tornar a migração aditiva também para colunas novas em tabela já existente. |
| `scripts/postgres_schema.sql` | Incluir `CREATE TABLE situacao_escolar` e `CREATE INDEX ix_situacao_escolar_unidade_nome`. |

[... resto da seção de 11/09 permanece igual ...]

---

### Alterações do dia — 17/09/2026

- Data da intervenção: 17/09/2026
- Início: manhã
- Conclusão: fim do dia

Refatoração estrutural em 6 ondas sequenciais. O objetivo foi reduzir dívida técnica acumulada e preparar o sistema para relatórios sobre perfil socioeconômico e de diversidade dos alunos. Cada onda é independente, verificável e reversível.

### Resumo das ondas aplicadas

| Onda | Escopo | Migrations |
| --- | --- | --- |
| **1** | Modularização do `models.py` + integridade + JSONB | `73f922fd358f` |
| **2A** | Datas/horas nativas (fim dos `varchar`) | `a1bbf3c29231` |
| **2B** | Enums nativos + CHECK constraints | `ef4e5af7e876` |
| **3A** | 4 tabelas de perfil do Aluno + 10 colunas | `5ae559bc9d87` |
| **3A-bis** | Coluna `documentos_entregues` (JSONB) | `29a29fdbc2aa` |
| **3B** | Backend + relatórios + templates refatorados | — |

### Onda 1 — Modularização, integridade e JSONB

- Pacote `app/models/` criado (antes era `models.py` monolítico de ~1000 linhas).
- UNIQUE constraints adicionadas: `frequencia (aluno_id, turma_id, data)` e `conselho_classe (turma_id, aluno_id, etapa)`.
- Índices adicionados em `frequencia`: `(turma_id, data)` e `(aluno_id, data)`.
- `db.JSON` → JSONB em `atendimento.dados` e `respostas_formulario.dados`.
- `ConfiguracaoSistema`: dois índices únicos parciais (`ix_config_chave_global`, `ix_config_chave_unidade`).
- Correção do bug `Inscricao.data_inicio` (usava `datetime.utcnow()` em coluna `Date`).
- Criado `scripts/smoke_models.py` — 24 verificações automáticas do pacote de modelos.

### Onda 2A — Datas e horas nativas

- `Turma.data_inicio`, `data_fim`, `hora_inicio`, `hora_fim` → `Date`/`Time`.
- `Frequencia.data`, `RegistroAula.data` → `Date`.
- `DiaBloqueadoTurma.data`, `TemaAula.data` → `Date`.
- Criado `app/utils/datetime_parse.py` com `parse_date`, `parse_time`, `parse_datetime` (tolerantes a `None`/vazio/string).
- 8 arquivos de rota ajustados para converter string → tipo nativo antes de gravar/filtrar.
- Criado `scripts/preflight_onda2a.py` e `scripts/check_onda2a.py`.

### Onda 2B — Enums nativos e CHECK constraints

- Criado `app/models/enums.py` com 6 enums (`ConceitoFrequencia`, `TipoDiaBloqueado`, `EtapaConselho`, `TipoPergunta`, `UserRole`, `SituacaoFinal`) e conjuntos derivados (`CONCEITOS_PRESENCA`, `CONCEITOS_CONTABEIS`, `ETAPAS_ORDEM`).
- Enums nativos no PostgreSQL: `conceito_frequencia_enum`, `tipo_dia_bloqueado_enum`, `etapa_conselho_enum`, `tipo_pergunta_enum`.
- CHECK constraints: `ck_user_role`, `ck_conselho_situacao_final`.
- Refatoração de ~40 strings literais de `role` para `UserRole.*` em `auth.py`, `conselho.py`, `core.py`, `turmas.py`, `dashboard_admin.py`, `relatorios/geral.py`, `bootstrap.py`, `logica.py`.
- Criado `scripts/preflight_onda2b.py` e `scripts/check_onda2b.py`.

### Onda 3A — Tabelas de perfil do Aluno

- Criadas 4 tabelas novas:
  - `endereco_aluno` (1:1 com Aluno).
  - `responsavel_aluno` (1:N com Aluno).
  - `perfil_socioeconomico` (1:1 com Aluno).
  - `perfil_diversidade` (1:1 com Aluno).
- Adicionadas 10 colunas em `aluno`: `orgao_rg`, `nacionalidade`, `natural_uf`, `natural_cidade`, `nome_mae`, `cpf_mae`, `nome_pai`, `cpf_pai`, `vai_acompanhado_aulas`, `acompanhante_aulas`.
- Backfill a partir dos JSONs legados, preservando `unidade_id` e criando registros apenas quando há dado real.
- **Nada foi removido** — os 4 JSONs (`_escolaridade_json`, `_identificacao_json`, `_socioeconomico_json`, `_diversidade_json`) continuam como fallback.
- Criado `scripts/preflight_onda3.py` (mapeamento dos JSONs).

### Onda 3A-bis — Coluna `documentos_entregues`

- Adicionada coluna `aluno.documentos_entregues` (JSONB) no formato `{'doc_entregue': {doc_id: bool}}`.
- Backfill a partir de `escolaridade_json`.
- Adicionados métodos `Aluno.documentos_dict()` e `Aluno.documento_entregue(doc_id)` como acessores.

### Onda 3B — Migração de código

- Criado `app/services/aluno_perfil.py`:
  - `upsert_endereco`, `upsert_responsavel`, `upsert_perfil_socioeconomico`, `upsert_perfil_diversidade` (escrita a partir do `request.form`).
  - `get_perfil_completo`, `get_endereco`, `get_responsavel_principal`, `get_perfil_socioeconomico`, `get_perfil_diversidade`, `get_identificacao` (leitura com fallback nos JSONs).
  - Normalizadores `s()`, `i()`, `b()`.
- `app/registros/alunos.py` refatorado:
  - Cadastro e edição gravam nas tabelas novas via `upsert_*`.
  - Campos civis (`nome_mae`, `orgao_rg`, etc.) gravam direto em `Aluno`.
  - Documentos entregues vão para `documentos_entregues` (JSONB).
  - `editar_aluno` e `imprimir_aluno` passam `perfil=get_perfil_completo(aluno)` para o template.
- `app/relatorios/geral.py`, `app/relatorios/alunos.py`, `app/relatorios/shared.py` refatorados:
  - Filtros usam JOIN nas tabelas novas em vez de JSON path.
  - `_is_pcd` e `_acompanhante` centralizam leitura com fallback.
  - `_contar_por_genero` usa `get_perfil_diversidade`.
- `app/registros/servico_social.py`: `dados_aluno` usa `get_perfil_completo`.
- Templates refatorados:
  - `editar.html` usa `perfil.identificacao`, `perfil.endereco`, `perfil.socioeconomico`, `perfil.diversidade`, `perfil.responsavel`.
  - `impressao.html` idem.
  - `atendimento_pedagogico.html` usa colunas novas com fallback.
  - `gerenciar.html` usa `aluno.documentos_dict()`.
- Corrigido bug de sintaxe JS `{ { X } }` → `{{ X }}` em `editar.html` e `calendario_bloqueados_print.html`.
- `MER.md` atualizado com histórico de ondas, referência cruzada de migrations e apêndices.

### Arquivos alterados nesta parte

| Arquivo | Natureza da mudança |
| --- | --- |
| `app/models/__init__.py`, `base.py`, `enums.py` | Novos (pacote) |
| `app/models/organizacao.py`, `usuarios.py`, `pedagogico.py`, `academico.py`, `pessoas.py`, `perfis.py`, `matriculas.py`, `calendario.py`, `aulas.py`, `conselho.py`, `atendimento.py`, `servico_social.py`, `auditoria.py`, `legado.py` | Novos (pacote) |
| `app/utils/datetime_parse.py` | Novo |
| `app/utils/logica.py`, `app/utils/frequencia.py` | Refatorados |
| `app/services/aluno_perfil.py` | Novo |
| `app/registros/alunos.py`, `core.py`, `turmas.py`, `periodos.py`, `servico_social.py` | Refatorados |
| `app/relatorios/geral.py`, `alunos.py`, `shared.py` | Refatorados |
| `app/main/dashboard_professor.py`, `dashboard_admin.py`, `secretaria.py` | Refatorados |
| `app/auth.py`, `conselho.py` | Refatorados |
| `app/services/bootstrap.py` | Refatorado |
| `app/templates/alunos/editar.html`, `impressao.html`, `gerenciar.html`, `atendimento_pedagogico.html` | Refatorados |
| `app/templates/planejamento/calendario_bloqueados_print.html` | Correção de sintaxe |
| `MER.md` | Atualizado |
| `scripts/smoke_models.py`, `preflight_onda2a.py`, `check_onda2a.py`, `preflight_onda2b.py`, `check_onda2b.py`, `preflight_onda3.py` | Novos |

### Comandos de validação usados

```powershell
# Sobe a app
python -c "from app import create_app; app = create_app(); print('OK')"

# Smoke test (24 verificações)
python scripts\smoke_models.py

# Verificação de cada onda
python scripts\check_onda2a.py
python scripts\check_onda2b.py
```

### Limpeza final do mesmo dia (commit `4b4566e`, 22:29)

- Removido o `app/models.py` monolítico (732 linhas), artefato que restava da Onda 1 — a partir daqui o projeto usa exclusivamente o pacote `app/models/`.
- Removidos `app/models.zip` e `app/LEIA-ME.md` (obsoletos).
- Ajustado o `.vscode/settings.json`.

---

### Alterações do dia — 20/09/2026

- Data da intervenção: 20/09/2026
- Commit: `896115c` — segurança: corrige IDOR, CSRF e exposição de arquivos estáticos (23:57)

Auditoria interna de segurança, privacidade e dívidas técnicas (LGPD/ECA) registrada em `docs/checklist_seguranca_dividas_tecnicas.md`, com 11 achados (SEC-01 a SEC-11) remediados neste mesmo commit.

### Principais correções aplicadas

- **SEC-01 (crítica)** — uploads de documentos, laudos e fotos deixam `app/static/uploads/` e passam para `instance/uploads/`; os arquivos agora são servidos por rotas autenticadas (`@login_required` + validação de unidade), eliminando download anônimo por URL previsível.
- **SEC-02 (crítica)** — rotas de exclusão/inativação/desenturmação migradas de `GET` para `POST` com token CSRF (alunos, turmas, unidades, perguntas do conselho, períodos letivos, agendamentos do serviço social); templates convertem links em formulários `POST`.
- **SEC-03 a SEC-05** — interceptor global `enforce_user_access_state` (perfis `pendente`/`first_login`), checagem de perfil (RBAC) nas ações destrutivas e reforço do `assert_unidade_context` (bloqueia unidade nula), fechando IDOR entre unidades.
- **SEC-06** — Google OAuth: exigência de e-mail verificado, restrição por domínio (`GOOGLE_OAUTH_ALLOWED_DOMAINS`) e bloqueio de vinculação automática quando já existe conta local com senha.
- **SEC-07** — troca de senha passa a exigir a senha atual (fora do fluxo de primeiro acesso).
- **SEC-08** — histórico de brute-force persistido em banco (`ConfiguracaoSistema`), sem perda de estado em reinicializações multi-worker; `ProxyFix` aplicado para leitura do IP real atrás de proxy reverso.
- **SEC-09 a SEC-11** — `SESSION_COOKIE_SECURE` corrigida; cabeçalhos de segurança (`X-Frame-Options`, `HSTS`, `X-Content-Type-Options`, `Referrer-Policy`) via `after_request`; mensagens de erro deixam de vazar detalhes internos do banco.
- `_get_upload_root` centraliza o diretório de uploads via `UPLOAD_FOLDER` (`instance/`).
- Arquivos de upload de desenvolvimento removidos do repositório.

### Novos scripts, testes e documentação

- `scripts/migrar_uploads_para_instance.py` — migração dos arquivos físicos legados para a pasta protegida.
- `scripts/verificar_sec01.py` — verificação automatizada do SEC-01.
- `tests/test_security_regressions.py` e `tests/test_sec01_uploads.py` — regressões de segurança; configuração do pytest no `pyproject.toml`.
- `docs/checklist_seguranca_dividas_tecnicas.md` — novo documento-âncora da auditoria.

### Arquivos alterados nesta parte

| Arquivo | Natureza da mudança |
| --- | --- |
| `app/__init__.py` | Interceptor global de acesso + cabeçalhos de segurança + `ProxyFix` |
| `app/auth.py` | CSRF no admin, brute-force em banco, senha atual obrigatória, OAuth endurecido |
| `app/registros/alunos.py`, `atendimentos.py`, `core.py`, `periodos.py`, `servico_social.py`, `shared.py` | Uploads protegidos, `POST`+CSRF, RBAC e isolamento de unidade |
| `config.py` | `UPLOAD_FOLDER`, `GOOGLE_OAUTH_ALLOWED_DOMAINS`, cookie seguro |
| `app/templates/**` | Links de mutação convertidos em formulários `POST` com `csrf_token` |
| `docs/checklist_seguranca_dividas_tecnicas.md` | Novo |
| `scripts/migrar_uploads_para_instance.py`, `scripts/verificar_sec01.py` | Novos |
| `tests/test_security_regressions.py`, `tests/test_sec01_uploads.py` | Novos |
| `pyproject.toml` | Configuração do pytest |
| `app/static/uploads/**` | Arquivos de desenvolvimento removidos do versionamento |

---

### Alterações do dia — 21/09/2026

- Data da intervenção: 21/09/2026 (sessão da madrugada)
- Commits: `0b19c7a` (00:16) e `35439c7` (00:25)

### README e robustez do login (`0b19c7a`)

- `README.md` reescrito e ampliado.
- Login deixa de quebrar em falha de banco: a consulta de usuário é protegida e exibe "Sistema temporariamente indisponível" em vez de erro 500.
- Persistência do histórico de tentativas falhas com fallback silencioso em memória (se o banco falhar, a proteção em memória segue ativa na instância).
- Error handler global ampliado de `OperationalError` para `SQLAlchemyError` (tela `sistema_indisponivel.html` em 503).

### Nomenclatura de "dashboard" para "Painel" (`35439c7`)

- Renomeação de dashboard → Painel na nomenclatura interna e nos textos: endpoint `main.painel` (antes `main.dashboard`), redirecionamentos, docstrings e templates. Sem mudança de comportamento.

### Arquivos alterados nesta parte

| Arquivo | Natureza da mudança |
| --- | --- |
| `README.md` | Reescrito e ampliado |
| `app/auth.py` | Login resiliente a falha de banco; fallback do rate limit em memória |
| `app/__init__.py` | Error handler ampliado (`SQLAlchemyError`) |
| `app/main/__init__.py`, `dashboard.py`, `secretaria.py`, `unidade.py`, `app/registros/core.py`, `app/registros/servico_social.py` | Renomeação dashboard → Painel |
| `app/templates/base.html`, `app/templates/dashboard/index.html` | Textos "Painel" |

---

### Alterações do dia — 22/09/2026

- Data da intervenção: 22/09/2026
- Commit: `f66a731` — Etapa VI do cadastro do aluno + relatório de exportação de alunos (21:56)

### Etapa VI — perfil socioeconômico e diversidade

- `perfil_socioeconomico.renda_familiar`: `varchar(50)` (faixa textual) → `numeric(12,2)` (valor mensal em reais); faixas antigas descartadas na conversão, sem estimativa retroativa.
- `perfil_socioeconomico.beneficio_social_nome`: `varchar(100)` → `text` (vários programas unidos por ` | `).
- `perfil_diversidade.tipo_deficiencia`: nova coluna (`varchar(30)`), restrita ao catálogo do serviço.
- `app/services/aluno_perfil.py`: normalizador `money()` (formato brasileiro → `Decimal`), cálculo de `renda_per_capita()` em runtime (não persistido) e validação/limpeza de `tipo_deficiencia` (mantido apenas com `saude_laudo`).
- Cadastro e edição (`novo.html`, `editar.html`, `registros/alunos.py`) passam a gravar os novos campos; JS ajustado (unificado no dia seguinte).
- Migrations novas: `3b7c9d1e4f20` (renda + tipo_deficiencia) e `4c8e2f7a1b30` (programas sociais).

### Relatório de exportação de alunos

- Filtros gerais na tela: Data Inicial, Data Final e Período Letivo.
- Nova coluna "Data da Matrícula" (usa `created_at`) disponível para seleção e exportação.
- Exportação passa a ser ordenada por nome.

### Infraestrutura e documentação

- `config.py`: `_get_database_uri()` normaliza `DATABASE_URL` SQLite (caminhos relativos do Windows e prefixo `instance/`).
- `scripts/postgres_schema.sql` atualizado com as colunas novas e `scripts/create_postgres_schema.py` ajustado.
- `MER.md`: dicionário de dados atualizado (renda numérica, `beneficio_social_nome` texto, `tipo_deficiencia`).
- `docs/manual_programas_sociais.md` criado; `tests/test_aluno_perfil.py` ampliado.
- Observação: `instance/database.db.bak` (backup do SQLite, 270 KB) entrou por engano no commit e ainda aguarda a remoção do versionamento.

### Arquivos alterados nesta parte

| Arquivo | Natureza da mudança |
| --- | --- |
| `app/models/perfis.py`, `pessoas.py` | Novas colunas e documentação do JSON legado |
| `migrations/versions/3b7c9d1e4f20_*.py`, `4c8e2f7a1b30_*.py` | Novas migrations (Onda 3B-bis) |
| `app/services/aluno_perfil.py` | `money()`, `renda_per_capita()`, `tipo_deficiencia()` |
| `app/registros/alunos.py` | Persistência da Etapa VI |
| `app/templates/alunos/novo.html`, `editar.html`, `impressao.html`, `gerenciar.html` | Campos novos da Etapa VI |
| `app/static/js/alunos/aluno_form.js`, `novo.js`, `editar.js` | Máscaras e validações dos campos novos |
| `app/relatorios/alunos.py`, `app/templates/relatorios/relatorio_alunos.html` | Filtros gerais, coluna Data da Matrícula, ordenação por nome |
| `config.py` | `_get_database_uri()` |
| `scripts/postgres_schema.sql`, `scripts/create_postgres_schema.py` | Schema atualizado |
| `docs/manual_programas_sociais.md` | Novo |
| `tests/test_aluno_perfil.py` | Ampliado |
| `app/models/MER.md` | Dicionário atualizado |

---

### Alterações do dia — 23/09/2026

- Data da intervenção: 23/09/2026
- Commits: `ef933b8` (11:36) e `dba5464` (19:13)

### Unificação do JS do formulário do aluno (`ef933b8`)

- Lógica consolidada em dois arquivos: `aluno_utils.js` (máscaras, CPF, CEP, IBGE, webcam, data de emissão) e `aluno.js` (stepper, toggles, validações, renda, idade, situação escolar, autocomplete de instituições).
- Arquivos antigos (`aluno_form.js`, `calcularIdade.js`, `situacao_escolar.js`, `novo.js`, `editar.js`, `historico.js`) preservados como `*OLD.js`.
- Corrigido listener `DOMContentLoaded` aninhado que impedia restaurar o estado do acompanhante quando o formulário voltava com erro do backend.
- Corrigido `SyntaxError` no `editar.html` (delimitadores Jinja inválidos `{ { ... } }`); handlers inline exportados em `window` (`toggleOutroAcompanhante`).
- `transferir.js` refatorado (versão anterior em `transferirOLD.js`).

### Unidade de cadastro obrigatória para usuário global (`dba5464`)

- Usuário global (sem unidade ativa) passa a escolher explicitamente a unidade de destino ao cadastrar aluno — select obrigatório no Step 1 de `novo.html`.
- Backend (`novo_aluno`) resolve a unidade em duas vias: contexto ativo ou `unidade_id` do formulário (validado); impede a criação de aluno órfão (`unidade_id=None`), que não aparecia em nenhuma listagem.
- `aluno.js`: validação do stepper agora considera campos `[required]` visíveis (o botão PRÓXIMO não é submit, então o HTML5 sozinho não bloqueava).

### Arquivos alterados nesta parte

| Arquivo | Natureza da mudança |
| --- | --- |
| `app/static/js/alunos/aluno.js`, `aluno_utils.js` | Novos (JS unificado) |
| `app/static/js/alunos/*OLD.js` | Versões antigas preservadas |
| `app/static/js/alunos/transferir.js`, `transferirOLD.js` | Refatorado + backup |
| `app/templates/alunos/novo.html`, `editar.html`, `historico.html` | Novo carregamento de scripts; select de unidade |
| `app/registros/alunos.py` | Unidade de cadastro obrigatória no `novo_aluno` |

---

### Alterações do dia — 27/09/2026

- Data da intervenção: 27/09/2026
- Commit: `d1217ea` — novos relatórios e combinações de dados (Central de BI) (01:45)

### Central de BI

- Novo módulo em camadas: `catalogo.py` (indicadores, dimensões e tipos de resultado — sem acesso a banco), `bi.py` (execução/despacho por código), `bi_alunos.py` (cálculos) e `bi_routes.py` (rotas).
- Rotas novas: `/relatorios/bi` (Central de BI), `/relatorios/bi/dados` (API JSON para gráfico dinâmico por dimensão), `/relatorios/bi/indicador/<codigo>` (JSON) e `/relatorios/bi/exportar` (placeholder 501, previsto com openpyxl).
- Indicadores implementados: ALU-001 a ALU-004, ALU-007 a ALU-010 e INS-001 a INS-005 (último: `bi_alunos.inscricoes_desativadas`). ALU-005 (sexo) e ALU-006 (faixa etária) estão no catálogo e mapeados nas dimensões, mas ainda sem função de cálculo.
- Nova tela `relatorios/bi.html` + `bi.css` e item "Central de BI" no menu de Relatórios.

### Cabeçalho e layout global

- `base.html`: badge de versão (`v{{ app_version }} · {{ app_stage }}`) e rodapé com versão — dependem de `app/version.py`, ainda não criado (referência registrada em comentário no template; renderizam vazio até então).
- Estados `active` nos itens do menu, correções de layout (body flex, footer, viewport) e `lang="pt-BR"`.
- Versão anterior do layout preservada em `baseOLD.html`.

### Preservação e documentação

- Pacote antigo de relatórios copiado para `app/relatoriosOLD/` (`alunos.py`, `conselho.py`, `geral.py`, `shared.py`) como backup; os arquivos originais seguem ativos em `app/relatorios/`.
- Novo `docs/relatorioMudanças/relatorios.md`: catálogo de indicadores (ALU, INS, FRE, TUR) e regra metodológica dimensão × métrica; Parte 2 prevista (pedagógico: aulas, avaliações, conselho, aprovação/evasão).
- `MER.md`: normalização de fim de linha (sem mudanças relevantes de conteúdo).

### Arquivos alterados nesta parte

| Arquivo | Natureza da mudança |
| --- | --- |
| `app/relatorios/catalogo.py`, `bi.py`, `bi_alunos.py`, `bi_routes.py` | Novos (motor BI) |
| `app/relatorios/__init__.py` | Registro do `bi_routes` |
| `app/templates/relatorios/bi.html`, `app/static/css/relatorios/bi.css` | Novos (Central de BI) |
| `app/templates/base.html`, `baseOLD.html` | Badge de versão, active states, layout + backup |
| `app/relatoriosOLD/**` | Backup do pacote antigo |
| `docs/relatorioMudanças/relatorios.md` | Novo (catálogo de indicadores) |
| `app/models/MER.md` | Normalização de fim de linha |

**### Alterações do dia — 28/09/2026**

* Data da intervenção: 28/09/2026

Sessão de continuidade do desenvolvimento da **Central de BI**, com foco na categoria **AUL — Aulas**. A implementação seguiu o padrão já estabelecido para ALU, INS, FRE e TUR, mantendo separação entre catálogo, execução e cálculos.

**### Central de BI — Indicadores de aulas**

Foram implementados e validados os indicadores **AUL-001 a AUL-005**:

| Indicador   | Descrição                  | Resultado validado |
| ----------- | -------------------------- | -----------------: |
| **AUL-001** | Total de aulas registradas |                 71 |
| **AUL-002** | Aulas por turma            |                 71 |
| **AUL-003** | Aulas por período          |                 71 |
| **AUL-004** | Aulas por professor        |                 71 |
| **AUL-005** | Aulas por curso            |                 71 |

**### AUL-001 — Total de aulas registradas**

* Criado o indicador no catálogo.
* Implementada a função `total_aulas_registradas()`.
* A consulta utiliza `RegistroAula` como origem.
* O vínculo com unidade acadêmica é realizado por `Turma.unidade_id`, pois `RegistroAula.unidade_id` possui registros nulos no conjunto de dados atual.
* Implementados filtros por unidade, período letivo, curso, turma, professor e intervalo de datas.
* Resultado geral validado: **71 aulas**.
* Filtros individuais validados com os dados existentes.

**### AUL-002 — Aulas por turma**

* Criado o indicador no catálogo.

* Implementada a função `aulas_por_turma()`.

* Agrupamento realizado por turma.

* Implementados filtros por unidade, período letivo, curso, turma, professor e intervalo de datas.

* Resultado validado:

  * `01 - Natação`: 19
  * `10 - Intermediário Dingue T1`: 22
  * `Fibra de vidro`: 10
  * `Mecânica de Popa`: 20

* Total: **71 aulas**.

* Validação catálogo × execução concluída.

**### AUL-003 — Aulas por período**

* Criado o indicador no catálogo.

* Implementada a função `aulas_por_periodo()`.

* Agrupamento realizado por `PeriodoLetivo`.

* Implementados filtros por unidade, período letivo, curso, turma, professor e intervalo de datas.

* Resultado validado:

  * `2026.1`: 71 aulas

* Validação catálogo × execução concluída.

**### AUL-004 — Aulas por professor**

* Criado o indicador no catálogo.

* Implementada a função `aulas_por_professor()`.

* Agrupamento realizado por professor (`User`).

* Durante a implementação foi corrigida a utilização do atributo do modelo `User`: o campo correto é `User.name`, e não `User.nome`.

* Implementados filtros por unidade, período letivo, curso, turma, professor e intervalo de datas.

* Resultado validado:

  * Arilton Novaes: 19
  * Daniel Bezerra: 22
  * Jaqueline Santuchi: 10
  * Luciano Campos: 20

* Total: **71 aulas**.

* Validação catálogo × execução concluída.

**### AUL-005 — Aulas por curso**

* Criado o indicador no catálogo.

* Implementada a função `aulas_por_curso()`.

* Agrupamento realizado por curso (`Curso`).

* Implementados filtros por unidade, período letivo, curso, turma, professor e intervalo de datas.

* Resultado validado:

  * Fibra de vidro: 10
  * Mecânica de Popa: 20
  * Natação: 19
  * Vela Dingue: 22

* Total: **71 aulas**.

* Validação catálogo × execução concluída.

**### Registro dos componentes alterados**

| Arquivo                            | Natureza da mudança                                                                           |
| ---------------------------------- | --------------------------------------------------------------------------------------------- |
| `app/relatorios/catalogo.py`       | Inclusão dos indicadores AUL-001 a AUL-005                                                    |
| `app/relatorios/bi_alunos.py`      | Implementação dos cálculos AUL-001 a AUL-005                                                  |
| `app/relatorios/bi.py`             | Registro dos indicadores AUL-001 a AUL-005 no despacho de execução                            |
| `app/relatorios/bi_routes.py`      | Ajuste da rota `/bi` para organizar indicadores por categoria e disponibilizá-los ao template |
| `app/templates/relatorios/bi.html` | Nova estrutura inicial para seleção e futura exibição dos indicadores                         |

**### Validações realizadas**

Foram realizados testes diretos das funções e testes através de `executar_indicador()`.

Foram validados, conforme aplicável:

* execução sem filtros;
* filtro por unidade;
* filtro por período letivo;
* filtro por curso;
* filtro por turma;
* filtro por professor;
* filtro por intervalo de datas;
* consistência entre catálogo e função executora.

Os cinco indicadores AUL implementados permanecem consistentes com os dados atualmente registrados no banco.

**### Estado ao final da sessão**

A categoria **AUL — Aulas** possui atualmente os indicadores **AUL-001 a AUL-005 implementados, registrados no catálogo, conectados ao mecanismo de execução e validados**.

A evolução da interface da Central de BI foi iniciada, porém sua implementação funcional foi deliberadamente deixada em espera para priorizar a conclusão dos indicadores AUL.

---

### Alterações do dia — 02/10/2026

- Data da intervenção: 02/10/2026
- Escopo: conceito de status do aluno por período, alinhamento dos indicadores da Central de BI, bootstrap inicial, troca de senha e documentação de referência.

### Status do aluno por período — Etapas 1 e 2

- Criado `app/services/aluno_status.py` como ponto central da classificação derivada; o status não é persistido no banco.
- Criados `StatusAluno` e `JANELA_RENOVACAO_DIAS` em `app/models/enums.py`; a janela de renovação é de 14 dias, inclusiva.
- Implementadas as categorias Novo, Renovado, Retornante, Em janela, Não renovado, Desenturmado e Outros, respeitando `Aluno.ativo` como situação cadastral e `Inscricao` como histórico de enturmação.
- Implementada classificação individual e em lote, seleção de P-1 da mesma unidade, reconstrução para datas passadas e deduplicação por aluno.
- No BI, sem período explícito, o serviço usa o período ativo vigente em cada unidade; períodos sobrepostos são resolvidos pelo início mais recente.
- O filtro de turno define a coorte pelas inscrições em P ou P-1; a classificação usa o histórico completo. As rotas dos indicadores de status impõem a unidade efetiva dos perfis locais.
- Adicionados ALU-011 a ALU-018: enturmados, não enturmados, novos no período, renovados, retornantes, não renovados, em janela e desenturmados.
- Atualizados `app/models/MER.md` (§8.3) e, após validação da Etapa 2, os registros dos novos indicadores em `app/relatorios/indicadores.md`.
- Sem novas tabelas ou migrations para o status.

### Revisão de indicadores existentes — Etapa 3

- **ALU-001:** redefinido como total de alunos com `Aluno.ativo=True` no escopo do período; teste de consistência exige `ALU-001 = ALU-011 + ALU-012`.
- **ALU-002/ALU-003:** mantido o significado cadastral (`Aluno.ativo=True/False`); rótulos clarificados para “Alunos com cadastro ativo/inativo”.
- **ALU-004:** redefinido e validado como “Novos cadastros”, usando `Aluno.created_at` no intervalo do período, sem exigir enturmação. Registros com `created_at` nulo ficam fora. ALU-013 continua representando Novo por primeira enturmação.
- **ALU-005/ALU-006:** validados como distribuição dos alunos enturmados em P/D por gênero e faixa etária.
- **ALU-007:** validado como alunos PCD enturmados, usando perfil estruturado ou fallback legado.
- **ALU-008:** validado como total cadastral por unidade, sem mudança de população.
- **ALU-009:** validado como alunos com inscrição ativa em P/D agrupados por curso.
- **ALU-010:** implementado como alunos com cadastro e inscrição ativos em P/D agrupados por turma; aguarda validação manual dos números. A descrição correspondente ainda não foi atualizada em `indicadores.md`.
- A nova etapa “Período = Todos” e série histórica por período não foi iniciada; depende da conclusão e validação da Etapa 3.

### Banco e bootstrap administrativo

- Conexão estabelecida com PostgreSQL `pautaon`, schema `public`.
- Criadas/confirmadas 30 tabelas a partir dos models, sem migration. No último levantamento: 2 unidades, 0 períodos e 0 alunos; não há dados reais para amostrar os indicadores.
- Executado o comando CLI `seed-admin` usando as configurações locais. Confirmada a existência de um administrador ativo com `first_login=True`; a senha não é registrada neste relatório.
- Esclarecido que o bootstrap é explícito pelo comando CLI e não é executado automaticamente por `run.py`.

### Segurança dos testes e troca de senha

- Corrigidos os fixtures de `tests/test_aluno_status.py`, `tests/test_bi_indicadores.py`, `tests/test_sec01_uploads.py` e `tests/test_security_regressions.py` para passar uma configuração SQLite à factory antes de inicializar a engine e afirmar o dialeto antes de `drop_all()`.
- A correção evita que a suíte use ou remova o schema PostgreSQL configurado no `.env`.
- Corrigida a visibilidade de senha em `app/templates/trocar_senha.html` e `app/static/js/senha_trocaSenha.js`: os seletores agora usam `data-target` para cada campo, alternam ícone/estado acessível e incluem senha atual, nova e confirmação.

### Wiki do sistema

- Criado `docs/wi.md` como índice de referência do sistema: conceitos, perfis, arquitetura, execução local, banco, testes, BI, operação e links para manuais existentes.
- A wiki informa que o modo histórico “Todos” ainda está planejado e não está implementado.

### Testes e verificações

- Suíte completa: **29 testes aprovados**, com 4 avisos de depreciação já existentes (`Query.get()` e `datetime.utcnow()`).
- Testes focados de status e BI executados durante cada etapa.
- Diagnósticos de código sem erros nos arquivos verificados.
- `git diff --check` sem erros de whitespace; o Git reportou apenas avisos de normalização LF/CRLF em arquivos do worktree.

### Estado ao final da sessão

- Etapas 1 e 2 validadas.
- Etapa 3 avançou até ALU-010; os indicadores ALU-001 a ALU-009 foram validados e documentados conforme as decisões recebidas.
- ALU-010 está implementado e testado, mas aguarda validação explícita dos números antes da atualização documental e do avanço para INS-001.
- A série histórica “Todos” permanece pausada até a conclusão de toda a Etapa 3.

### Alterações do dia — 03/10/2026

- Data da intervenção: 03/10/2026
- Início da correção: 2026-10-03 00:30
- Conclusão da correção: 2026-10-03 01:10

Esta atualização inclui:
- Implementação de um sistema global de auditoria para ações no banco de dados.
- Criação de `AuditoriaMixin` (app/models/auditoria_mixin.py) que inclui as colunas `updated_by_id`, `updated_by_name` e `updated_at`.
- Aplicação do mixin às tabelas `Turma`, `TemaAula`, `RegistroAula`, `Curso`, `ConselhoClasse` e `Inscricao` (além da tabela `Aluno` tratada anteriormente).
- Criação do `AuditoriaListener` (`app/models/auditoria_listener.py`) que preenche os campos automaticamente e adiciona um `LogAcao` (INSERT/UPDATE/DELETE).
- Resolução de problema com `__allow_unmapped__ = True` e `@declared_attr` (necessário no SQLAlchemy 2.x).
- Criação e estruturação dos mixins pendentes: `SoftDeleteMixin` (para a coluna `ativo`) e `TenantMixin` (para a coluna `unidade_id`) inseridos no arquivo `app/models/base.py`. Estes mixins foram aplicados de forma bem-sucedida, simplificando os modelos de `academico.py`, `pedagogico.py`, `matriculas.py`, `conselho.py` e `aulas.py`.
- Adicionada configuração `alembic.ini` e migração de banco `a9f3c8e2d1b7` que insere as colunas nas tabelas supracitadas.
- Atualização do arquivo `docs/wiki.md` e `app/models/MER.md` refletindo essas modernizações (resolvendo o item 12.3 da dívida técnica).


### Alterações do dia — 26/10/2026

- **Vários temas por aula:** pauta atualizada para selecionar e gravar vários temas no mesmo `RegistroAula`; validação rejeita temas inexistentes ou incompatíveis com o curso da oferta. Observações, estatísticas docentes e BI foram adaptados; BI conta aulas distintas por tema.
- Migration `a8b9c0d1e2f3` aplicada ao PostgreSQL local: revisão atualizada de `f6a7b8c9d0e1` para `a8b9c0d1e2f3`. A tabela associativa foi criada; a conferência encontrou 0 registros antigos com tema sem vínculo migrado (o banco continha 0 associações a migrar).
- Testes focados: `tests/test_turma_curso_fase4.py` e `tests/test_pauta_professor.py` — **26 aprovados**. Incluído teste de integração com dois temas no mesmo registro.


### Alterações do dia — 26/10/2026 (H1 — horário por dia na oferta)

- **H1-P0a (B5-P1):** `migrations/env.py` agora chama `fileConfig(..., disable_existing_loggers=False)` — provado no scratch com migration descartável: o `flask db upgrade` exibe o `RuntimeError` das checagens (antes engolia só com exit 1). MER §12.17 atualizado.
- **H1-P0b:** removido `app/templates/turmas/listar copy.html` (grep sem referências).
- **H1-P1:** conversor único `app/utils/dias_semana.py` (weekday 0–6, nomes canônicos, `-feira`, abreviações, com/sem acento; desconhecido → `None`). Parsers antigos intocados até o H3. `tests/test_dias_semana.py` (15).
- **H1-P2/P3:** modelo `TurmaCursoHorario` (`turma_curso_horario`: UNIQUE oferta+dia, CHECKs domínio 0–6/par/`fim>início`, FK CASCADE) + migration `5730d7c594ba` (aditiva; `dias_semana` → varchar(80); pré-checagens (i)–(v) num único `RuntimeError`; backfill herança campo a campo COALESCE oferta→turma, idempotente; downgrade recusa grade não uniforme e não reduz o varchar).
- **H1-P4:** serviço `app/services/turma_curso_horario.py` — `grade_da_oferta`, `grades_em_lote` (sem N+1), `definir_grade` (átomo, mensagens em português), `duracao_do_dia`, `grade_uniforme`, `resumo_grade`, `sincronizar_projecao_horario` (único ponto de projeção a partir do H2). Nenhuma função commita.
- **H1-P5:** `test_turma_curso_horario_schema.py` (9), `test_turma_curso_horario_servico.py` (20), `test_turma_curso_horario_migration.py` (14) + helper `grade_a_partir_do_legado` em `tests/_helpers.py` (será usado no H2/H3).
- **H1-P6:** ensaio A–E no scratch `pautaon_ensaio` (dump do banco local): upgrade limpo; dados reais 5 ofertas → 8 linhas, 0 divergências `resumo_grade` × colunas antigas, `max(length(dias_semana))`=15; checagens (i)–(v) cada uma em falha visível; downgrade uniforme + re-upgrade; idempotência. **Migration NÃO aplicada no banco principal** (aguarda backup + autorização).
- **Comportamento visível:** NENHUM — etapa puramente aditiva (H2–H5 pendentes; MER §12.25).
- Suíte ao final da H1: **458 passed**, 0 falhas; head única `5730d7c594ba`; `ruff check app --select F821` limpo.

### Alterações do dia — 26/10/2026 (H2 — escritores da grade por dia)

- **H2-P0 (autorizado):** migration `5730d7c594ba` aplicada ao **banco principal**: backup `pautaon_pre_H1.sql` restaurado no scratch (prova), descoberta e remoção de tabela órfã vazia (`turma_curso_horario` criada por `create_all` acidental no dev H1, com guarda "só dropa se 0 linhas"), upgrade limpo (8 linhas / 5 ofertas, varchar(80)), consulta de conformidade 100% (sem oferta sem dia, sem dia sem hora, sem domingo, sem `fim<=início`), scratch na head nova, suíte 458 verde antes do código.
- **H2-P1:** mapeamento dos escritores confirmado sem extras (oferta inicial, adicionar/editar, `_sincronizar_legado`, `nova_turma`/`editar_turma` POST, `_dados_oferta_form`, `turma_oferta_nova/editar`, `datetime_parse`); "Domingo" já não existia nas opções de formulário.
- **H2-P2:** `definir_grade` aplica o contrato H2 — recusa grade vazia, dia fora de 0–5, domingo, duplicata, hora ausente, `fim<=início`; mensagens em português citando o dia; validação antes de qualquer escrita; idempotência real (mesma grade = zero escrita). Commits `a028cce`.
- **H2-P3:** escritores gravam via `definir_grade` na mesma transação; herança da Turma só com agenda completa (senão `ValueError` — nunca grade parcial); `editar_oferta` aceita agenda por dia e recalcula avisos com a grade nova; POST `editar_turma` ignora campos de agenda quando a grade da oferta ativa única **não é uniforme** (flash) — critério por uniformidade, não por nº de ofertas; `editar.html` com `agenda_bloqueada`; `ofertas.html` com aviso de retroatividade ("vale para todo o período da oferta, inclusive aulas já lançadas"). Commit `52628b9`.
- **H2-P4:** novos `tests/test_definir_grade.py` (15 casos: domínio 0–5 parametrizado, mensagens por dia, atomicidade nível-banco, validação antes da idempotência) e `tests/test_turma_curso_horario_escritores.py` (11 casos: oferta inicial, herança incompleta rejeitada, adicionar/editar, projeção uniforme/NULL, POST editar_turma não uniforme ignorado / uniforme espelhado, escrita sem N+1). Ajustes de contrato: `test_turma_curso_fase2/3/4` (fixtures/chamadas sem agenda completa passaram a enviar dias/hora; "sem horário pula validação" → "sem agenda completa é rejeitada"). Commit `fa2e957`.
- **Comportamento visível:** edição de oferta avisa retroatividade; agenda da Turma bloqueada por grade não uniforme; ofertas sem agenda completa não podem mais ser criadas (validação clara). Leitores inalterados (H3); grade não uniforme ainda não criaível pela UI (H4).
- Suíte ao final da H2: **489 passed**, 0 falhas; head `5730d7c594ba` aplicada no principal; `ruff check app tests --select F821` limpo. Pergunta aberta: apertar `ck_tch_dia` para 0–5 numa revisão futura (MER §12.25).

### Alterações do dia — 26/10/2026 (H3a — leitores de agenda/validação leem a grade)

- **H3a-P0 (proteção + backup):** grep `create_all` achou dois caminhos de risco ao principal — `app/services/bootstrap.py::initialize_database` (CLI `flask init-db`) e `scripts/create_postgres_schema.py::create_tables_in_database` (lê `DATABASE_URL`); ambos ganharam guarda que **recusa PostgreSQL** sem `PAUTAON_ALLOW_CREATE_ALL=1` (evolução do principal é só `flask db upgrade`); `create_all` em testes está preso a SQLite in-memory (seguro). Novo `pg_dump` do principal em `instance/backups/pautaon_pos_H2.sql`. Suíte 489 verde antes de editar. Commit `4e3f44c`.
- **H3a-P1 (leitura, sem editar):** confirmados os leitores do grupo agenda/validação — `_parse_dias`, `_data_bate_dias_semana`, `_dias_efetivos_da_oferta`, `datas_aula_oferta`, `datas_esperadas_oferta`, `resolver_oferta_lancamento` (turma_curso.py); `calcular_dias_aula_turma`/`gerar_datas` (logica.py); `contar_pendencias_frequencia`/`_pendencias_por_ofertas` (frequencia.py); `_aulas_pendentes`/`_horario_oferta` (dashboard_professor, só DATAS); `estatisticas_professor.py:309-310`. **Sem leitores fora da lista.** Após migrar, único chamador remanescente de `_parse_dias` = `_conflitos_horario_concomitante` (grupo concomitância, H3d).
- **H3a-P2 (serviço, lote):** `app/services/turma_curso_horario.py` ganha `dias_da_oferta(id)` (uma consulta), `dias_por_ofertas(ids)` (lote, **sem N+1** — reusa `grades_em_lote`; prova via listener `before_cursor_execute`: 1 statement para K ofertas) e `dias_da_turma(id)` = **união das ofertas ATIVAS** (uma consulta; Turma passa a DERIVAR dias, sem ler `Turma.dias_semana`). Commit `00502fc`.
- **H3a-P3 (migrar leitores):** `_data_bate_dias_semana` agora recebe a **oferta** e testa `data.weekday()` contra a grade (novo `_dias_set_da_oferta`: fonte grade, **fallback** controlado ao CSV via `csv_para_weekdays` quando não há grade, `logger.warning` para tokens desconhecidos); `datas_aula_oferta`/`datas_esperadas_oferta` e `resolver_oferta_lancamento` leem dias pela grade (**mantendo** vigência, dias bloqueados e regra de oferta única INALTERADOS); `logica.gerar_datas` removeu `mapa_dias` e deriva de `dias_da_turma`; frequência/pendências/dashboard herdam via `datas_esperadas_oferta` (sem consulta por data/oferta); `_parse_dias` mantido **só como ponte** (tem chamador de concomitância); removido `_NOMES_DIA_SEMANA`. Commit `00502fc`.
- **H3a-P4 (testes):** novos `tests/test_datas_aula_oferta_grade.py` (25: weekdays 0–5, vigência, dias bloqueados, **grade não uniforme** — dias da oferta ≠ dias da turma antiga, oferta sem linhas → fallback CSV, N+1 lote, **equivalência** grade == caminho antigo CSV) e `tests/test_resolver_oferta_grade.py` (8: dia agendado/ausente, domingo recusado, regra de oferta única preservada). Único teste que muda de contrato: `test_data_bate_dias_semana_acento_espace_variante` (fase4) reancorado à grade — assinatura mudou de `(csv, data)` para `(oferta, data)` (previsto em H1 §5). `TestParseDias` (fase3) **não** quebrou (ponte sobrevive). Commit `80eae75`.
- **H3a-P5 (ensaio + BI):** scratch `pautaon_ensaio` na head `5730d7c594ba` (8 linhas / 5 ofertas): datas esperadas por oferta **CSV antigo × grade novo = 0 divergências** nas 5 ofertas reais; indicadores BI **FRE-009/AUL-002/ALU-009 idênticos** Postgres × SQLite espelhado.
- **Comportamento visível:** NENHUM para dados reais (equivalência provada); grade não uniforme agora é lida corretamente pelas datas de aula. **NÃO mudaram:** C.H. total, concomitância (`_conflitos_horario_concomitante` ainda por `_parse_dias`), filtros/listagem, telas e exibição de hora (H3e/H4).
- Suíte ao final da H3a: **522 passed**, 0 falhas; head `5730d7c594ba` (sem migration nova); `ruff check app tests --select F821` limpo. Commits `4e3f44c`/`00502fc`/`80eae75` (branch `nova_feature`, sem push). Restam H3b–H3e (C.H., concomitância, hora/exibição), H4 (UI) e H5 (drop das colunas de projeção).

### Alterações do dia — 26/10/2026 (H3b — concomitância por dia, leitura pela grade)

- **H3b-P0 (higiene):** reorganização `docs/ → docs/Relatórios/` commitada **isolada** (só documentação; grep não achou código que abra `docs/`, só menções em docstrings); docstring de `datas_aula_oferta` corrigido — `limite` é **INCLUSIVO** (sem mudar comportamento). Suíte 522 verde antes de editar. Commits `2aca2d1` (docs) e `bbc76ce` (docstring).
- **H3b-P1 (leitura):** grupo confirmado **sem extras** — `_conflitos_horario_concomitante` e seus 3 chamadores (`adicionar_oferta`, `editar_oferta`, espelho do `editar_turma` POST); `_parse_dias` só era usado por ele (e `TestParseDias`). Nenhum outro leitor de dias/horas no grupo.
- **H3b-P2 (caracterização ANTES):** `tests/test_concomitancia_grade_por_dia.py` com 8 casos de **grades uniformes** fixando par + **texto exato** do aviso, adjacência/dias diferentes/vigência disjunta sem aviso, dois conflitos em ordem de id e aviso nunca bloqueante. Rodados verdes **antes** da migração. Commit `b2816f6`.
- **H3b-P3 (migrar):** comparação **POR DIA** (weekday em comum → sobreposição estrita do intervalo do dia; `fim = início` adjacente não conflita; vigência limitando inalterada); grades das outras ofertas via relação `horarios` **selectin** (uma consulta, **sem N+1**), fallback CSV para oferta 100 % legado; nova `agenda` da candidata (criação sem linhas / edição só de vigência usa a grade real); mensagem cita os dias em conflito mantendo o formato anterior quando a outra é uniforme; **`_parse_dias` e `TestParseDias` removidos**. Commit `ff72ced`.
- **H3b-P4 (testes):** +5 casos no arquivo novo — grade não uniforme com conflito só no dia que sobrepõe (e sem conflito no outro), edição só de vigência usando a grade real, criação sem grade usando `agenda`, e **sem N+1** (1 statement em `turma_curso_horario`). **532 passed**, ruff F821 limpo. Commit `c89865f`.
- **H3b-P5 (ensaio):** scratch `pautaon_ensaio` na head `5730d7c594ba` (8 linhas / 5 ofertas): avisos **escalar antigo × grade novo** oferta a oferta = **0 divergências** (2 pares conflitantes com texto idêntico).
- **Comportamento visível:** aviso agora cita o(s) dia(s) em conflito quando a outra oferta tem grade **não uniforme**; para grades uniformes o texto é **idêntico** ao anterior (caracterizado). **NÃO mudaram:** C.H. total, filtros/listagem/impressão, telas e exibição de hora (H3c–H3e/H4).
- Suíte ao final da H3b: **532 passed**, 0 falhas; head `5730d7c594ba` (sem migration nova); `ruff check app tests scripts --select F821` limpo. Commits `2aca2d1`/`bbc76ce`/`b2816f6`/`ff72ced`/`c89865f` (branch `nova_feature`, sem push). Restam H3c–H3e (C.H., filtros/listagem, hora/exibição), H4 (UI) e H5 (drop das colunas de projeção).

### Alterações do dia — 26/10/2026 (H3c — C.H. por ocorrência da grade)

- **H3c-P1 (serviço):** `app/services/turma_curso_horario.py` ganhou `CargaOferta`/`CargaTurma`, `cargas_horarias_ofertas_em_lote(ofertas, bloqueios=None)`, `cargas_horarias_turmas_em_lote(turmas)` e `carga_horaria_total_turma(turma)`. Leitura em **lote** (ofertas + grade via `selectinload`, bloqueios do período e `dia_bloqueado_turma`) — nenhuma consulta por oferta/data; oferta sem grade cai no escalar legado com `logger.warning`. Removido código morto que sobrou do rascunho: `CargaTurma.principal_total`, `carga_por_dia`, `menor_duracao_semanal` e uma **definição duplicada** de `duracao_do_dia` (F811).
- **H3c-P2 (domínio):** C.H. **aula** da oferta = duração **uniforme** da grade (`None` se não uniforme); C.H. **total** da oferta = soma da duração do dia em **cada ocorrência** esperada (vigência + bloqueios); C.H. **total** da turma = **tempo físico** (por data, **união** dos intervalos das ofertas ativas; sobreposição uma vez, disjuntos somam); a turma herda `aula`/`min_ch_aula` da oferta principal. `datas_esperadas_oferta` aceita `hoje=None` (toda a vigência). `Turma`/`TurmaCurso.carga_horaria_aula/total` agora **delegam** ao serviço. **Migration: nenhuma** (head segue `5730d7c594ba`).
- **H3c-P2b (coerência filtro × exibição):** `pos_filtrar_turmas` passou a comparar `min_ch_total` com o **mesmo valor exibido** na coluna de C.H. total (total da turma) — antes usava `principal_total` na turma 2+ ofertas, o que fazia o filtro divergir do número na tela; `min_ch_aula` segue na menor duração semanal (principal). Coberto por teste no arquivo novo e em `test_turma_curso_lista`.
- **H3c-P3 (consumidores):** listagem (`registros/turmas.py`: `turma`, `imprimir_centros_custo_turmas`, `carga_horaria_turmas`), impressão (`turmas/imprimir_listar_turma.html` lendo o mapa em lote — evita 1 consulta por linha), certificado por oferta (`registros/periodos.py`: C.H. da **oferta**, sem substituir pelo agregado da turma) e as propriedades em `models/academico.py`. **Escopo conferido por diff:** `listar.html` e `periodos.py` mudaram **só a fonte dos números de C.H.** — nada de exibição de horário/dia (H3d/H3e); a única mudança extra em `listar.html` é o newline no fim do arquivo. Extras classificados: `core.py:655` **(b)** herda via `Turma.carga_horaria_total`; `turmas.py` `_conflitos_horario_concomitante` **(c)** grupo concomitância (H3b); `utils/formatters.py:11` **(c)** docstring de `formatar_ch`.
- **H3c-P4 (testes):** novo `tests/test_carga_horaria_oferta_variavel.py` (5 casos: soma por ocorrência com vigência/bloqueio, união × disjunção na turma, turma de 1 oferta uniforme igualando a oferta, coerência `min_ch_aula`/`min_ch_total` e **sem N+1** — consultas de grade/bloqueio **constantes** com 2 ou 6 ofertas; a frequência por linha da sub-linha continua 1 consulta/oferta, dívida da Etapa K registrada em §8.10 do MER). Contratos ajustados em `tests/test_turma_curso_lista.py`: `t3.carga_horaria_total` **2520 → 8700** (tempo físico) e `min_ch_total` passa a selecionar pelo total da turma (**145h**), não pela principal (**82h**).
- **H3c-P5 (ensaio no scratch):** script novo `scripts/verificar_h3c_ch.py` (somente leitura, head esperada `5730d7c594ba`), saída em `instance/backups/h3c_ensaio.txt`. Turma **9** (3 ofertas): **9.720 min (162h) → 6.720 min (112h)** — antes o par escalar da turma (3h) era multiplicado pelos 54 dias da **união** (Seg/Qua/Ter), cobrando 3h nas terças de 1h; agora soma as ofertas (105h + 7h + 19h = 131h) e deduplica **19h** de sobreposição na quarta 10:00–11:00. `principal (105h) ≤ novo (112h) ≤ soma (131h)` ✓. Turmas **10** e **11** (1 oferta uniforme): **antigo == novo** (105h e 70h). As **5 ofertas** reais mantiveram C.H. aula e total **idênticas** antes × depois.
- **Comportamento visível:** a C.H. total das turmas **multi-oferta** passa a ser o tempo físico (pode diminuir — caso da turma 9) e o filtro `min_ch_total` passa a usar esse número; turmas de **1 oferta uniforme não mudam** (provado no ensaio). **NÃO mudaram:** exibição de hora/dia (H3d/H3e), filtros por professor/turno/dia/horário, vigência e concomitantia.
- Suíte ao final da H3c: **537 passed**, 0 falhas; head `5730d7c594ba` (sem migration nova); `ruff check app tests scripts --select F821,F811` limpo (branch `nova_feature`, sem push). Restam H3d (filtros/listagem/impressão pela grade), H3e (hora/exibição), H4 (UI) e H5 (drop das colunas de projeção).

### Alterações do dia — 26/10/2026 (H3d — filtros, listagem, detalhe e impressão leem a grade)

- **H3d-P1 (leitura e classificação):** leitores de dias/horários do grupo `registros/turmas.py` classificados. **(b) calculavam por conta própria → migrados:** `_resumo_ofertas` (split do CSV), `aplicar_filtros_turmas` (dois `EXISTS` independentes com COALESCE), `listar.html` (coluna de horário da turma + sub-linha), `detalhe.html` (card e rótulo do seletor de enturmação), `imprimir_listar_turma.html` (par de horas e dias). **(a) herdam via serviço/propriedade:** mapas de C.H. em lote (H3c), `_ofertas_ativas_da_turma`/`_oferta_principal`, `resumo.dias_abreviados`. **(c) semântica diferente: nenhum.** Fora do escopo e adiada: a **tabela** de `turmas/ofertas.html` (tela de edição — H4). Semântica ATUAL do filtro de horário documentada: **igualdade na hora de INÍCIO**, não faixa.
- **H3d-P2 (caracterização ANTES):** novos `tests/test_filtros_turma_grade.py` (12 casos) e `tests/test_impressao_grade_oferta.py` (7 casos), fixando dia/horário/dia+horário em grades uniformes, oferta sem grade, turma sem oferta, token inválido e o **texto exato** da linha/sub-linha/detalhe/impressão. Passaram **idênticos** depois da migração. Commit `435c885`.
- **H3d-P3 (serviço):** `app/services/turma_curso_horario.py` ganhou `GradeExibicao`, `grades_por_oferta(ofertas)`, `dias_das_turmas_em_lote(turmas, grades=None)`, `condicao_turma_com_grade()`, `condicao_grade(dia, hora)`, `filtro_por_dia_horario(...)` e `grade_para_exibicao`/`grades_para_exibicao(ofertas, cargas, grades)`. Um único `EXISTS` em `turma_curso_horario` (oferta ativa) exige **dia e hora na MESMA linha**; fallback escalar só para turma sem oferta com grade. `CargaTurma.min_ch_aula` passou a ser o **menor valor entre TODAS as ofertas ativas** (antes: só a principal). Tudo em **lote** — sem N+1. Commit `2635502`.
- **H3d-P4 (migração):** `_resumo_ofertas` deriva dias da união das grades (fallback CSV); `aplicar_filtros_turmas` usa `filtro_por_dia_horario` (`logger.warning` para token de dia desconhecido); `turma()`, `imprimir_centros_custo_turmas` e `ver_turma` montam `grade_oferta_map` em lote (`selectinload(TurmaCurso.horarios)`); os três templates exibem a grade — **uniforme = texto anterior**, **não uniforme = por dia** (`"Terça 08:00–10:00; Quinta 14:00–16:00"`) e a coluna **"C.H. por aula" = "varia"** com a lista por dia no `title`. `_ORDEM_DIAS`/`_ABREVIACAO_DIAS` removidos. **Migration: nenhuma** (head segue `5730d7c594ba`). Commit `52ebf9d`.
- **H3d-P5 (testes):** +9 casos em `test_filtros_turma_grade.py` (grade não uniforme: filtro por dia/horário, **dia+horário na mesma linha**, fallback escalar, agregação; `min_ch_aula` global e seu filtro; consultas de grade constantes ao crescer turmas) e +7 em `test_impressao_grade_oferta.py` (texto por dia na linha/detalhe/impressão, `"varia"` na sub-linha multi e na impressão, uniforme sem `"varia"`, consultas constantes na listagem e no detalhe). **Nenhum teste existente foi alterado.** Commit `dd10b85`.
- **H3d-P6 (ensaio no scratch):** script novo `scripts/verificar_h3d_filtros.py` (somente leitura, head esperada `5730d7c594ba`), saída em `instance/backups/h3d_ensaio.txt`. **8 combinações reais** (dia, hora de início das 8 linhas de grade): **0 divergências**. Varredura de **48 combinações** (6 dias × 8 horários): **2 remoções** de falso-positivo (`Segunda + 10:00` e `Terça + 10:00`, que só existe na quarta) e **0 adições**. Agregação de dias **idêntica** nas 3 turmas. `min_ch_aula` da turma 9: **60 min** (antes 180, da principal); turmas 10/11 inalteradas.
- **Comportamento visível:** filtro **dia + horário** deixa de retornar turmas em que os critérios casavam em **ofertas/linhas diferentes** (só remoções); `min_ch_aula` das turmas multi-oferta passa a considerar **todas** as ofertas (pode ficar menor); telas mostram a grade **por dia** quando não uniforme e `"varia"` na C.H. por aula. **NÃO mudaram:** dashboard, ficha do aluno, conselho, certificado (H3e), formulários e JS de edição (H4), schema.
- Suíte ao final da H3d: **571 passed** (572 no total; o `test_maintenance::test_maintenance_blocks_non_admin_users` falha por causa de um diff **não commitado e alheio ao H3d** — ver o relatório), head `5730d7c594ba` (sem migration nova); `ruff check --select F821,F811,F401` limpo (branch `nova_feature`, sem push). Restam H3e (hora/exibição), H4 (UI) e H5 (drop das colunas de projeção).

### Alterações do dia — 26/10/2026 (H3e — dashboard, aluno, conselho, ficha e frequência leem a grade)

- **H3e-P1 (leitura e classificação):** todo leitor restante de dias/horário levantado por grep (`dias_semana`, `hora_inicio`, `hora_fim`, `split(",")`). **(b) liam o escalar por conta própria → migrados:** `_horario_oferta`/`_dias_efetivos_da_oferta` e pendências (`dashboard_professor.py`), histórico do aluno (`registros/alunos.py`), `_dias_horario` (`ficha_aluno.py`), painel/fechamento (`conselho.py` + templates), seletor da frequência (`core.py` + `lancar.html`), `gerenciar`/`atendimento_pedagogico`/`transferir` (rotas + templates) e `scripts/diagnostico_carga_horaria.py`. **(a) herdam via serviço/propriedade:** `gerar_datas` (H3a) e mapas de C.H. (H3c). **(c) semântica diferente: nenhum.** Fora do escopo: `turmas/ofertas.html`, `nova.js`, `editar.js` (H4).
- **H3e-P2 (caracterização ANTES):** `tests/test_leitores_grade_h3e.py` com 11 casos fixando o texto de cada tela/função em grade uniforme; textos reais também capturados no scratch. Commit `35ee622`.
- **H3e-P3 (serviço):** `GradeExibicao` ganhou `dias`, `texto_horario` (`"08:00 às 09:30"`) e `texto_horario_curto` (`"08:00–09:30"`); `intervalo_do_dia(oferta, data|weekday)` devolve o par do **weekday da data** lendo a relação já carregada (sem consulta por data/oferta) e cai no escalar da oferta/turma quando não há grade.
- **H3e-P4 (migração):** dashboard (resumo por `GradeExibicao`; pendências com a nova coluna **Horário** vinda de `intervalo_do_dia`), aluno (histórico + `_grade_por_aluno` em lote para `gerenciar`/`atendimento`; `transferir` com `grade_origem`), ficha (`_dias_horario(turma, oferta)`), conselho (painel/fechamento com `grade_oferta_map` e `selectinload` em `ofertas_do_painel_conselho`), frequência (seletor) e script de diagnóstico (dias pela união da grade). Fallback escalar com `logger.warning`. **Migration: nenhuma** (head segue `5730d7c594ba`).
- **H3e-P5 (testes):** `test_leitores_grade_h3e.py` com **22 casos** (não uniforme por dia em todas as telas; dashboard por data — terça 08:00–10:00 e quinta 14:00–16:00; turma multi-oferta derivando dias da grade; fallback sem grade com warning; consultas de grade constantes ao crescer ofertas). **Teste existente alterado:** `test_impressao_grade_oferta.py::TestRenderSemN1` — media dois requests no mesmo app e o segundo não via as ofertas novas (falso-negativo); agora mede apps novos com o estado final e conta **apenas** SELECTs de `turma_curso_horario` (o N+1 de `Turma.freq_geral` é pré-existente da D3b-2 e não entra na conta).
- **H3e-P6 (ensaio no scratch):** `scripts/verificar_h3e_leitores.py` (somente leitura, head esperada `5730d7c594ba`). **3 turmas, 5 ofertas reais, 160 leituras** de dashboard/aluno/ficha/conselho: **0 divergências inesperadas**; **6 legítimas** (ofertas 12 e 13 da turma multi-oferta, que antes repetiam o par da Turma).
- **Comportamento visível:** dashboard ganha a coluna **Horário** nas pendências (intervalo do dia da data); telas de aluno/ficha/conselho mostram a grade **por dia** quando não uniforme e o par **da oferta** em turma multi-oferta; onde saía `str(time)` cru (`"08:00:00"`) agora sai `"08:00"`. **NÃO mudaram:** formulários, JS, `turmas/ofertas.html`, schema e nenhuma coluna escalar foi removida (H5).
- Suíte ao final da H3e: **593 passed** (594 no total; `test_maintenance::test_maintenance_blocks_non_admin_users` segue deselecionado pelo template movido para `erros/` no commit alheio `7779aea`), head `5730d7c594ba` (sem migration nova); `ruff check --select F821,F811` limpo (branch `nova_feature`, sem push). Restam H4 (UI) e H5 (drop das colunas de projeção).

### Alterações do dia — 26/10/2026 (H3f — leituras residuais de escalares em `turma_curso.py` passam a ler a grade)

- **H3f-P0 (pré-requisitos):** correção pendente do `render_template` de `sistema_indisponivel` commitada à parte (`eaa7c05`); heads `5730d7c594ba`; suíte completa **sem deselect = 594 passed** (o template movido em `7779aea` já estava no caminho `erros/`).
- **H3f-P1 (leitura e classificação):** itens (iii) do H3e §9 confirmados. **(b) migrados:** defaults de `editar_oferta` e da checagem de conflito, herança da 1ª oferta em `adicionar_oferta`, rótulo do aviso de concomitância e mensagem do `resolver_oferta_lancamento`. **(a) legítimos:** seed do `criar_oferta_inicial_da_turma` (só roda sem oferta alguma), `_sincronizar_legado`, fallbacks de `turma_curso_horario.py`; `detalhe.html:254` **já limpo desde o H3d** (`52ebf9d`) — inventário do H3e desatualizado. **(c) nenhum.**
- **H3f-P2 (caracterização ANTES):** `tests/test_leituras_residuais_grade_h3f.py` com 9 casos em grade uniforme (textos exatos, defaults, herança, seed, rótulo do seletor) — verdes antes da migração. Commit `b5a7a35`.
- **H3f-P3 (migração):** novo `_defaults_agenda_da_oferta` (defaults da grade atual: CSV dos dias; par só se uniforme); herança com `agenda_herdada` (grade de oferta ativa com grade; escalares só sem nenhuma grade, com `logger.warning`); warning no seed legado; rótulos via `weekdays_para_csv` da grade; checagem em edição sem agenda usa `grade_da_oferta(oferta) or None` (oferta 100 % legado volta a ser checada pelo fallback). Nenhuma gravação nova fora de `definir_grade`. **Migration: nenhuma.** Commit `933d403`.
- **H3f-P4 (testes):** +11 casos (**20 total** no arquivo): grade não uniforme preservada em edições de vigência/programa (projeção envenenada ignorada); conflito usa a grade real (aviso por dia); mensagem do resolver cita dias da grade; herança só para turma sem grade (estado-limite montado à mão — `_sincronizar_legado` espelha `curso_id` na 1ª oferta); warnings no caplog; rótulo do seletor só com grade. **Nenhum teste existente alterado.** **614 passed.** Commit `467876c`.
- **H3f-P5 (inventário final):** grep exaustivo das 3 colunas — em `app/` restam apenas projeção/espelho, fallbacks com warning e formulários/JS (`editar_turma`/`editar.html`/`ofertas.html`/`editar.js`/`nova.js` — H4); templates de listagem/fechamento têm só fallbacks `{% else %}`. Tabela arquivo:linha em `docs/Relatórios/H3f_LeiturasResiduaisGrade.md` (ação para o H5).
- **H3f-P6 (ensaio no scratch):** dry-run de `editar_oferta` (só programa + só vigência) nas **5 ofertas reais** do `pautaon_ensaio` (head `5730d7c594ba`) com COMMIT da Session interceptado (savepoint) e rollback total: grade (8 linhas), projeção das ofertas e espelho das turmas **idênticos** antes × depois — **0 divergências**; verificação externa por SQL confirmou banco intacto.
- **Comportamento visível:** NENHUM para grades uniformes (caracterização idêntica); com grade **não uniforme**, editar oferta pelo formulário atual passa a **recusar** mudança de dias/horas (`ValueError` "ao menos um dia") em vez de **regravar a grade uniforme a partir de NULL** — preserva a grade. **NÃO mudaram:** formulários, JS, `turmas/ofertas.html`, schema; nenhuma coluna escalar removida (H5).
- Suíte ao final da H3f: **614 passed**, 0 falhas, head `5730d7c594ba` (sem migration nova); `ruff check --select F821,F811` limpo (branch `nova_feature`, sem push). Restam H4 (UI por dia — pré-requisito cumprido) e H5 (drop das colunas de projeção).

### Alterações do dia — 26/10/2026 (H4 — UI de grade por dia: horário diferente por dia na turma e na oferta)

- **H4-P0 (pré-requisitos):** scratch `pautaon_ensaio` recriado a partir de pg_dump **novo** do principal (sem derrubar sessões do principal); heads `5730d7c594ba`; suíte **614 passed** antes de editar.
- **H4-P1 (leitura):** contract checkpoints OK — escalares de `Turma` NULLABLE sem CHECK impeditiva (nenhum PARE); serviços de oferta já aceitavam `agenda=`; `nova_turma` não tem agenda na tela (desvio aprovado: grade vai só para a oferta inicial por caminho legado); C.H. do JS documentada (par único × dias × semanas; `getDay()` domingo=0 — mapa antigo).
- **H4-P2 (contrato backend):** parsing única `grade_do_formulario(form)` (`registros/turmas.py`) para `nova_turma`/`editar_turma`/rotas de oferta — `dias_semana` (weekday 0–5), par padrão, flag `horario_por_dia`, pares `hora_inicio_<w>`/`hora_fim_<w>`; dias não marcados ignorados; nomes legados aceitos; domingo recusado. Helpers `_estado_agenda*` + `_serializar_estado_agenda`: erro de agenda vira flash e o formulário **volta preenchido** (modo personalizado aberto; HTTP 200 nas rotas de oferta; em `nova_turma`, flash + redirect). `sincronizar_projecao_turma` (nova, `turma_curso.py`): escalares da Turma só pela projeção da oferta única (não uniforme → dias + NULL); `editar_turma` deixa de escrever agenda direto com 1+ oferta. **Decisão:** bloqueio da edição volta ao critério **"2+ ofertas"** — turma com 1 oferta não uniforme é editável. **Testes existentes alterados (contrato esperado):** payload em `test_isolamento_unidade_escrita.py` e teste de bloqueio em `test_turma_curso_horario_escritores.py` (uniformidade do H2 → substituição com 1 oferta no H4; renomeado). Commit `318ac3e`.
- **H4-P3 (frontend):** módulo compartilhado `static/js/turmas/grade_horario.js` — substitui os três mapas de dia (`nova.js`, `editar.js`, JS inline de `ofertas.html`); `(getDay()+6)%7`, segunda–sábado; `initGrade` (interruptor "Horário diferente por dia", pré-preenchimento com o par padrão, confirmação ao desligar com valores diferentes); puras exportadas p/ teste; C.H. no JS vira **estimativa** (`Σ duração × ocorrências`, rotulada — autoritativo é o servidor). Macro `agenda_campos` (`_agenda_macros.html`) com labels por dia ("Início — Quarta"), erro inline, teclado; `editar.html`/`nova_turma.html`/`ofertas.html` migrados; tabela de ofertas lê `GradeExibicao` (badge **"varia"**); `editar.js` compara `serializarGrade` × `gradeOriginal` para a confirmação de limpeza. Commit `d20a794`.
- **H4-P4 (testes):** novos `tests/test_ui_grade_por_dia.py` (13: modo padrão igual ao atual; personalizado cria não uniforme em nova_turma/oferta nova/oferta editada; editar_turma 1 oferta grava via grade com projeção; 2+ ofertas mantém bloqueio; erros com re-render preenchido; hora em dia não marcado ignorada; idempotência), `tests/test_h4_leitores_grade_variavel_smoke.py` (7: oferta não uniforme criada por POST real da UI + todos os leitores migrados sem erro e com texto por dia; filtros dia+hora na mesma linha; concomitância; C.H. oferta==turma; dashboard por data; seletor/ficha/conselho/frequência/transferir; sem N+1) e `tests/test_grade_horario_js.py` (6: funções puras via node, skip documentado sem node — repo sem suíte JS própria). **640 passed**, ruff F821 limpo. Commit `61cf73e`.
- **H4-P5 (ensaio no scratch):** turma 10 «Informática» (MGB, real), oferta 14 tornada NÃO uniforme pela UI (Seg 08:00–11:00 + Qua 14:00–17:00): **18 leitores OK** (listagem+2 filtros+d Negativo, detalhe, impressão, cursos, C.H., alunos/histórico/ficha/transferir, conselho/fechamento, frequência/relatório, dashboard do professor nas duas faixas por weekday), C.H. oferta == turma == **6.300 min == cálculo independente** (Seg 16 + Qua 19 ocorrências × 180 min, 5 bloqueios do período descontados); projeção da oferta correta (dias "Segunda, Quarta", par NULL); badge "varia" + switch aberto na tela de cursos; **sem N+1** (3→3 consultas de grade); reenvio idempotente. Scratch **recriado** de dump novo após o ensaio; script temporário apagado. Principal intocado.
- **Comportamento visível:** turmas/ofertas ganham o interruptor "Horário diferente por dia" (erros por dia, labels, C.H. estimativa); turma com 1 oferta não uniforme volta a ser editável (antes bloqueada por uniformidade — decisão H4); grade uniforme mantém o comportamento idêntico ao atual. **NÃO mudaram:** schema (head `5730d7c594ba`), colunas escalares (H5), `ck_tch_dia` (0–6 no banco), fallbacks de legado, escritores (`definir_grade`/`sincronizar_projecao_horario`).
- Suíte ao final da H4: **640 passed**, 0 falhas, head `5730d7c594ba` (sem migration nova); `ruff check --select F821` limpo (branch `nova_feature`, sem push). Commits `318ac3e`/`d20a794`/`61cf73e`. Resta H5 (drop das colunas de projeção). Perguntas abertas: apertar `ck_tch_dia` para 0–5 (migration futura); certificado/painéis agregados leem por oferta? (H5); espelhos de agenda em `Turma` removidos junto ou depois das colunas da oferta (H5).

### Alterações do dia — 26/10/2026 (H5a — agenda só na grade; colunas escalares sem uso)

- **H5a-P0 (pré-requisitos/preflight):** head `5730d7c594ba`; suíte de partida **640 passed**. Preflight SOMENTE LEITURA no principal (transação `read_only`): (i) ofertas de qualquer status sem grade = **0**; (ii) ofertas com escalares e grade divergente da projeção = **0** (5 com escalares); (iii) turmas sem oferta com escalares = **0**; (iv) linhas de grade com dia 6 = **0**; contexto 3 turmas/5 ofertas/8 linhas. Nenhum PARE.
- **H5a-P1 (inventário):** grep exaustivo das 6 colunas em `app/`, `scripts/`, templates, JS e tests; confirmado que certificado/painéis agregados/BI/exportações não leem as colunas de agenda (leem a grade/ofeta). Nenhuma migration importa `app.utils.dias_semana` nem o código removido (a migration H1 tem conversor próprio); o conversor permanece (formulários/serviços).
- **H5a-P2/P3 (remoção):** removidos `sincronizar_projecao_horario`, `sincronizar_projecao_turma`, `grade_a_partir_do_legado`, `duracao_escalar_oferta`, `condicao_turma_com_grade`, `_dias_efetivos_da_oferta` e as 3 atribuições de agenda de `_sincronizar_legado`; todos os ramos “sem grade → escalar” viraram estado inválido (`logger.error` + “sem horário”). `editar_turma`: 0 ofertas não tem agenda (campos somem/ignorados), 1 oferta grava só por `definir_grade`, 2+ mantém bloqueio. `criar_oferta_inicial_da_turma`/`adicionar_oferta` não herdam mais escalares; `editar_oferta` recusa o trio escalar. Scripts `verificar_h3c_ch.py`/`h3d_filtros.py`/`h3e_leitores.py` removidos; `diagnostico_carga_horaria.py` adaptado à grade. **Sem schema/migration.**
- **H5a-P4 (testes):** `tests/_helpers.py` com `aplicar_grade`/`itens_grade`/`grade_atual`; fixtures e payloads migrados para a grade (sem escrever escalares no construtor). Testes que só caracterizavam projeção/fallback foram removidos ou convertidos (5 de `sincronizar_projecao_horario` em `test_turma_curso_horario_servico.py`; 7 antigos de `test_carga_horaria.py` → 5 pela grade; 2 de `test_datas_aula_oferta_grade.py` → 1; 2 de `tests/test_leitores_grade_h3e.py`; 5 de `test_filtros_turma_grade.py`; 2 de `test_impressao_grade_oferta.py`; 11→9 em `test_leituras_residuais_grade_h3f.py`; 6 renomeados em `test_turma_curso_horario_escritores.py`; 1 em `test_turma_curso_fase4.py` — motivos no relatório). Nova guarda AST `tests/test_guarda_colunas_escalares_h5a.py` (app/scripts + templates/JS). **632 passed**; `ruff F821` limpo.
- **H5a-P5 (prova por remoção):** removidas temporariamente as 6 colunas dos modelos `Turma`/`TurmaCurso`: suíte **632 passed** e smoke de **18 rotas** sem 500 (também com oferta sem grade e turma sem oferta). O teste histórico da migration passou a recriar as colunas legadas por DDL no SQLite (independe do modelo). Modelos restaurados e suíte repetida: **632 passed**.
- **H5a-P6 (ensaio no scratch):** `pautaon_ensaio` recriado de dump novo do principal (head `5730d7c594ba`, 3 turmas/5 ofertas/8 linhas); **48 verificações, 0 divergências** — 5 ofertas e 3 turmas, C.H. oferta 14 = **6.300 min** (idêntica ao H4), projeção × grade idêntica nas 5 ofertas, leitores (listagem+filtros, detalhe, impressão, cursos, C.H., dashboard, aluno/histórico/ficha, conselho/fechamento, frequência) sem 500. Principal intocado; scratch pode ser recriado.
- **Comportamento visível:** em grades uniformes, nenhum texto/valor muda. Oferta ativa **sem grade** (estado inválido) deixa de exibir o valor escalar e passa a mostrar “sem horário”/`—`; turma sem oferta não tem agenda. **NÃO mudaram:** schema, migrations, CHECKs/UNIQUEs (`ck_tch_dia` segue 0–6 no banco), head `5730d7c594ba`; as 6 colunas continuam no banco/modelos até o **H5b** (drop físico).
- Suíte ao final da H5a: **632 passed**, 0 falhas; head `5730d7c594ba` (sem migration); `ruff F821` limpo; branch `nova_feature`, sem push. Commits `9a3ae35` (app/scripts) e `f0891a0` (testes) + commits de MER/backlog/relatório. **Resta H5b** (remoção física das colunas). Relatório: `docs/Relatórios/H5a_RemoverUsoColunasEscalares.md`.

### Alterações do dia - 26/10/2026 (H5b — drop físico das colunas escalares; CHECK 0–5)

- **H5b-P0 (preflight somente leitura no principal):** head `5730d7c594ba`, 3 turmas / 5 ofertas / 8 linhas de grade; 0 linhas com dia 6; 0 ofertas (qualquer status) sem grade; as 6 colunas presentes e **sem** constraints, índices, defaults, views, triggers, functions ou dependências `pg_depend`. Backup `instance/backups/pautaon_pre_H5b.sql` (SHA256 `C5D5398354267EC66AF99C7B61BAC39063A9C4F515708E75E81021C72CCB5258`) com restore provado no scratch. Principal intocado.
- **H5b-A (migration `7c1d2e3f4a5b`):** aperta `ck_tch_dia` de 0–6 para **0–5**. Pré-checagem read-only lista ids se houver dia 6 e aborta sem DDL; drop/recreate do CHECK nomeado; downgrade volta a 0–6.
- **H5b-B (migration `8d2e3f4a5b6c`):** dropa as 6 colunas (`turma`/`turma_curso`), com pré-checagem read-only que recusa oferta sem grade (qualquer status) listando ids; drop idempotente por coluna. Modelos `Turma`/`TurmaCurso` perdem as declarações e `TurmaCursoHorario` documenta 0–5. Downgrade recria `VARCHAR(80)`/`TIME` e reconstrói a projeção: oferta uniforme = CSV canônico + par; não uniforme = dias + horas NULL; turma com 1 oferta ativa espelha a oferta; 0 ou 2+ = NULL. Perda documentada (horários por dia não cabem no par escalar).
- **H5b-P4 (testes):** `tests/test_h5b_migrations.py` (7: dia 6 recusado; 0 e 5 aceitos; drop idempotente; oferta sem grade recusada; downgrade uniforme/espelho, não uniforme, 0 e 2+ ofertas, re-upgrade); `test_turma_curso_horario_schema.py` atualizado para 0–5. **641 passed**, `ruff F821` limpo.
- **H5b-P6 (ensaio no scratch `pautaon_ensaio`):** migration A+B aplicada (head `8d2e3f4a5b6c`); snapshot antes/depois com **61 comparações e 0 divergências** (contagens, serviços, C.H. oferta 14 = 6.300 min e ~49 leitores HTTP); smoke de escrita no head (turma sem oferta + primeira oferta com grade via POST real, C.H. 2.280 min, limpeza). Downgrade comparado ao dump: ofertas 11–15 idênticas; turma 11 idêntica; turma 10 reconstruída como Seg/Qua (o dump estava **estagnado** em Segunda) e turma 9 com 3 ofertas = NULL (perda pela regra 2+). Re-upgrade limpo; colunas ausentes, dados 3/5/8. Scratch deixado na head; principal intocado **no ensaio** (aplicado em 27/10/2026 — entrada seguinte).
- **Comportamento visível:** nenhum texto/valor muda em grades uniformes; a agenda continua sendo a grade. **Aplicação no principal feita em 27/10/2026** (entrada seguinte); relatório `docs/Relatórios/H5b_DropColunasEscalaresCheck.md`.
- Suíte ao final da H5b: **641 passed**, 0 falhas; head `8d2e3f4a5b6c`; `ruff F821` limpo; branch `nova_feature`, sem push. Principal mantido em `5730d7c594ba` até a autorização de 27/10/2026.

### Alterações do dia - 27/10/2026 (H5b — aplicação no banco principal)

- **Autorização e preflight final (somente leitura):** head `5730d7c594ba`; 3 turmas / 5 ofertas / 8 linhas de grade; 0 dia 6; 0 oferta (qualquer status) sem grade; 6 colunas presentes e **sem** constraints, índices, defaults, views, triggers, functions, `pg_depend` ou policies; nenhuma outra sessão ativa no banco `pautaon`. Nenhum PARE.
- **Backup de rollback:** `instance/backups/pautaon_pre_H5b_final.sql`, **549.114 bytes**, SHA256 `FB1D89FA48D96CDE6948CCCEF8FE450BF09CF9C5113B5DCA407C71AA4DBF6CAF`, gerado em 27/10/2026 00:04:37 (`pg_dump` plain, `--clean --if-exists`, returncode 0, 35 tabelas). É o **rollback preferido**.
- **Upgrade:** `flask db upgrade` em 27/10/2026 00:04:55, **exit 0**, aplicou `5730d7c594ba → 7c1d2e3f4a5b → 8d2e3f4a5b6c`. Nenhuma correção manual e nenhum downgrade.
- **Conferência:** head `8d2e3f4a5b6c`; `ck_tch_dia` = `CHECK (((dia_semana >= 0) AND (dia_semana <= 5)))`; 6 colunas ausentes (`turma` 19 e `turma_curso` 20 colunas); **3 turmas / 5 ofertas / 8 linhas de grade**; 0 oferta sem grade; 0 dia 6.
- **Dump pós-upgrade:** `instance/backups/pautaon_pos_H5b.sql`, **548.564 bytes**, SHA256 `69021097A2376E915E4FB3438A5C51D104E779FAEB6D6B0FA2E271151701A42D`; `COPY` de `turma`/`turma_curso` sem as 6 colunas e CHECK 0–5 presente.
- **Smoke de UI GET-only no app vivo** (`http://127.0.0.1:5000`, usuário 24, `pedagogico`/unidade 2): **34/35 rotas 200**, cobrindo listagem/filtros de dia e horário, detalhe, ofertas, impressão de pauta/centros de custo, C.H., dashboard/painel, aluno/ficha, conselho, frequência e relatórios. Único 500: `/turmas/lixeira` (`TemplateNotFound: turma_lixeira.html`), **pré-existente e fora do H5b** (rota e `render_template` desde `14f5e47`; o template nunca existiu no repositório). Fingerprints de `aluno`, `turma`, `turma_curso`, `turma_curso_horario`, `inscricoes`, `frequencia`, `registro_aula` e `conselho_classe` **idênticos antes/depois**.
- **Sessões/app:** os 4 processos `run.py` e o listener `0.0.0.0:5000` **não foram parados**; o app respondeu aos GETs com o schema novo, sem reinício.
- **Rollback:** restaurar `pautaon_pre_H5b_final.sql` e voltar o código a `dd38d35` (preferido). `flask db downgrade 7c1d2e3f4a5b` só por decisão explícita — usar a revisão explícita, pois `downgrade -1` falha neste shell/Click. Resultado aceito do downgrade: ofertas 11–15 exatas, turma 10 defasada no dump, turma 9 NULL pela regra 2+.
- **Estado:** principal e scratch na head `8d2e3f4a5b6c`; **641 passed**; `ruff F821` limpo; branch `nova_feature`, **sem push e sem merge**. Relatório atualizado: `docs/Relatórios/H5b_DropColunasEscalaresCheck.md`.

### Alterações do dia - 27/10/2026 (H4c — layout unificado linha por dia; H4d — fechamento das lacunas do H4c)

- **H4c (commit `58eb924`; entrada escrita só agora, junto com a H4d):** unificação das três telas de agenda em componente único — macro `turmas/_agenda_macros.html` com par padrão **dentro** da macro, uma linha por dia (botões de alternância + horários ao lado), interruptor "Horário por dia" habilitado só com **2+ dias**, volta automática ao padrão ao desmarcar até 1 dia (par do dia restante vira o padrão), par padrão **visível mas esmaecido/desabilitado** no modo personalizado, CSS `grade_horario.css`. Servidor inalterado; +3 testes de endurecimento (POST nos dois modos, ignorância do campo do modo oposto, `horario_por_dia=1` com 1 dia aceito). Suíte 641→**644 passed**. Relatório: `docs/Relatórios/H4c_LayoutGradeDias.md` (o H4b foi iniciado e substituído pelo H4c, sem commit).
- **H4d-P0 (pré-requisitos, somente leitura):** suíte 644 verde; head única `8d2e3f4a5b6c`; `flask db current` no **principal** = `8d2e3f4a5b6c (head)`; scratch `pautaon_ensaio` = `8d2e3f4a5b6c` (consulta SQL direta, DSN com troca só do nome do banco). **Nenhuma migration aplicada** nesta etapa.
- **H4d-P1 (render do servidor — lacuna "Render do servidor: não testado" do H4c):** +6 testes em `tests/test_ui_grade_por_dia.py` via test client, asserções por seletor/atributo (regex estável; repo sem BeautifulSoup), nos três formulários (nova oferta, editar oferta, editar turma com 1 oferta): uniforme 2+ dias (padrão ativo, por dia desabilitado/esmaecido, interruptor habilitado e desligado); 0 e 1 dia (interruptor desabilitado + texto de apoio via `aria-describedby`); NÃO uniforme (abre personalizado, par padrão VISÍVEL sem `d-none` mas esmaecido/desabilitado, campos ativos nos dias marcados, desabilitados nos desmarcados); re-render de erro em personalizado com estado e valores preservados.
- **H4d-P2 (JS via node + refactor registrado):** o handler do interruptor não tinha função pura para a transição — extraídas `estadoLinha`, `parPadraoAposVolta` e `valorEspelhado` em `static/js/turmas/grade_horario.js` (**sem mudança de comportamento**; o DOM passa a chamá-las) e exportadas no objeto `GradeHorario`; +6 testes em `tests/test_grade_horario_js.py` (0/1/2+ dias do interruptor; volta ao padrão: par do dia restante vira o padrão, campo vazio mantém o atual, 0 dias mantém o último par; espelhamento do padrão; estado de linha por modo/marcação). Skip documentado quando node ausente no PATH (padrão do arquivo; node presente no dev).
- **H4d-P3 (docs):** MER §8.10 com o bullet das regras de UX do componente (componente único, estados, regra 2+ dias, volta automática, par padrão esmaecido e não oculto, campos desabilitados não enviados) e cabeçalho atualizado; esta entrada do backlog (H4c + H4d); removido `docs/Relatórios/H4b_SubstituidoPorH4c.md` (git rm — H4b nunca commitado e a substituição já registrada na seção própria do relatório H4c); relatório novo `docs/Relatórios/H4d_FechamentoLacunasH4c.md` (inclui o registro do refactor e dos desvios).
- **Comportamento visível:** NENHUM — etapa de testes, documentação e verificação; única mudança de código é o refactor puro autorizado do `grade_horario.js`.
- Suíte ao final da H4d: **656 passed**, 0 falhas; head `8d2e3f4a5b6c` (sem migration); `ruff check app tests scripts --select F821,F811` limpo (F401: ocorrências pré-existentes em arquivos alheios, fora do escopo); branch `nova_feature`, sem push.

### Correção de bug — TypeError nos temas da pauta de frequência (27/10/2026)

- **Sintoma:** `GET /frequencia?turma_id=<turma>&data=<dia>` derrubava a tela com 500 `TypeError: argument of type 'NoneType' is not a container or iterable` em `app/templates/frequencia/lancar.html:127` (`{% if tema.id in tema_selecionado %}`).
- **Gatilho:** o estado **mais comum** da pauta — dia ainda não lançado (sem `RegistroAula`) em turma cujo curso da oferta tem 1+ `TemaAula` ativo. Sem tema planejado o loop não executa e a tela abria normalmente, o que atrasou a detecção. Segundo caminho: `?data=` presente e não parseável (`parse_date` só aceita `YYYY-MM-DD`).
- **Causa raiz:** `carregar_frequencias` (`app/utils/logica.py`) montava a lista de temas **só dentro do `if diario:`**; nos demais caminhos devolvia o valor inicial `None` (resquício da era do tema único, assim como a anotação `Optional[int]` e o `:return:` do docstring). Regressão da adoção de temas múltiplos (`a8b9c0d1e2f3`): o template trocou `==` (tolera `None`) por `in` (exige sequência), mas o leitor não acompanhou o contrato.
- **Correção (2 camadas):** contrato na origem — `tema_selecionado: List[int] = []`, todos os `return` devolvem sequência (inclusive o early-return), assinatura `Tuple[Dict[int, str], List[int], str]` e docstring atualizados; e guarda redundante na visão — `tema_selecionado=tema_sel or []` (`app/registros/core.py`). Não há outro chamador de `carregar_frequencias` no app; o fallback no espelho `diario.tema_id` (linhas legadas) foi preservado.
- **Testes:** +3 em `tests/test_frequencia_oferta.py` — GET do dia sem diário com tema ativo, GET com `data=DD/MM/AAAA` e asserção direta do contrato da função nos dois caminhos. Helpers `_tema_da_oferta`/`_linha_do_tema` afirmam que o loop de temas **executou** e que o checkbox chega **desmarcado** (sem isso o teste passaria mesmo com o bug, porque `temas` vazio nunca entra no `{% if %}`). Os três foram validados contra o código antigo (revertido temporariamente): falham com o `TypeError` original.
- **Escopo:** nenhuma migration (head `8d2e3f4a5b6c`); nenhum comportamento alterado para diários já lançados; `ruff` sem achados novos nos 3 arquivos (só I001/F401 pré-existentes em linhas intocadas). Docs: MER §7.20 (contrato de leitura da pauta) e §10 (nota de correção no item dos temas múltiplos).
- Suíte ao final: **659 passed**, 0 falhas (656 → +3).
