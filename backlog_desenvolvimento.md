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

- **D3b-2/J3 — frequência e relatórios ainda por `turma_id`:** frequência/diário do ramo legado (`app/utils/logica.py`, `app/utils/frequencia.py`), `Turma.freq_geral` (property que soma as ofertas), `Frequencia.agregar_por_turma` (painel pedagógico), BI de frequência (`frequencia_por_turma`/`frequencia_por_curso` e vizinhos em `bi_alunos.py`), `calcular_frequencias_relatorio` (relatórios) e `freq_geral` na listagem de turmas/BI. ALU-009/ALU-010 ainda não aplicam `cond_inscricao_enturmada`; o BI ainda lê `Turma.programa` (projeção) em vez de `turma_curso.programa`.
  - Estatísticas do GET `/frequencia` (`app/registros/core.py`) agregam oferta e legado **sem separar por oferta**.
  - `excluir_turma` e a limpeza de lançamentos em `editar_turma` apagam por `turma_id`, alcançando as linhas de **todas as ofertas**.
- **Fases 5–7 da Onda 4 (a redefinir):** autorização por professor da oferta, turno e centro de custo por oferta, transferências avançadas. Fases 8–9 e NOT NULL final (`c3d4e5f6a7b8` + `d4e5f6a7b8c9`) **concluídas**.
- **`Transferencia`:** decidir se a tabela passa a registrar a oferta de origem/destino (hoje só `turma_origem_id`/`turma_destino_id`; rastrear exige `Inscricao`).
- **`turma_lixeira`:** GET `/turmas/lixeira` renderiza `turma_lixeira.html` inexistente; não há rota para **reativar** turma desativada.
- **Frequencia/RegistroAula legados com `turma_curso_id IS NULL`:** backfill definitivo **sem fase designada** (a antiga Fase 9 tratava só do NOT NULL de `inscricoes`); as rotas atuais preservam `IS NULL` de propósito. Consequências: turma sem oferta que lança frequência e depois ganha a primeira oferta perde a visão por oferta e relançar o dia cria linha duplicada; turma que desativa todas as ofertas deixa de mostrar o histórico por oferta na tela legada.
- **Dívida de migrations (§11.1, itens 2–6 e 8 do MER).**
- **Dump autêntico** para um novo ensaio P1/B5 (não há produção real; o banco local veio de dump antigo — B5-P2).
- **B5-P1 — corrigir `migrations/env.py`:** `flask db upgrade`/`flask_migrate.upgrade()` **engolem** o `RuntimeError` das checagens (passam por `catch_errors`, que faz `sys.exit(1)`) e o `fileConfig` do `env.py` desabilita os loggers; pendente `fileConfig(..., disable_existing_loggers=False)`. Até lá, a mensagem só aparece chamando `alembic.command.upgrade` direto (helper do ensaio D5.5).
- **Teste manual no navegador:** fluxos de conselho (lançamento, fechamento com CSRF, avaliação coletiva, seletor de oferta da ficha 360°) e relatórios/painel — a suíte roda com CSRF desligado.
- **`conftest.py` único (P7, MER §12.16).**
- **Duplicação de `cond_oferta_efetiva` (M4, MER §12.13).**
- **`ofertas.html` com lista de programas embutida (D6, MER §12.14).**
- **`TurmaCurso.avisos_horario` transiente (D7, MER §12.15).**
- **Onda 3C:** dropar os JSONs legados de `Aluno` (MER §10).
- **Resíduos do conselho (MER §12.19–§12.24):** `Turma.avaliacao_*` (legado, remover após conferir dump autêntico), `turma_conselho_concluido()` sem leitor no código de aplicação, painel por período omite turma sem frequência lançada, `agregar_por_turma` agrega por `turma_id`, N+1 residual do histórico e CSRF/UX do fechamento sem teste de navegador.

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

- `turma_lixeira` (GET `/turmas/lixeira`) renderiza `turma_lixeira.html`, que **não existe**; não há rota para **reativar** turma desativada.
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
