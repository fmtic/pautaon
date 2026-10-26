# H0 — Levantamento somente leitura: horário por dia na oferta

**Escopo:** leitura do código e da documentação, execução das verificações permitidas e nenhuma edição de código ou migration.

## 1. Linha de base

- **Alembic:** `flask db heads` e `flask db current` retornaram uma única head, `a8b9c0d1e2f3`; o banco está nessa mesma revisão.
- **Suíte:** **400 passed, 0 failed**, com 142 avisos, principalmente sobre `Query.get()` e `datetime.utcnow()`.
- **Ruff:** `ruff check --no-cache app --select F821` passou. A execução sem `--no-cache` falhou porque o sandbox bloqueou a escrita em `.ruff_cache`.
- **`migrations/env.py`:** `fileConfig(config.config_file_name)` aparece na linha 22 sem `disable_existing_loggers=False`. Portanto, o ponto B5-P1 registrado no backlog continua pendente.
- **MER:** a revisão Alembic confere com a head. O cabeçalho do MER ainda indica última atualização em 25/10/2026, mas há um complemento datado de 26/10/2026; a metadata superior não foi totalmente alinhada.

## 2. Leitores e escritores

A tabela reúne os usos encontrados de dias e horários da oferta e, onde a oferta herda campos, da turma. Linhas com vários locais no mesmo arquivo estão agrupadas. “Indireto” significa que a função delega a um serviço ou propriedade que consome a agenda.

| Arquivo:linha | Função ou componente | L/E | Resumo | Grupo |
|---|---|---:|---|---|
| `app/models/academico.py:108–115` | `Turma` | L/E | Armazena a agenda legada da turma: dias CSV e um par de horários. | outro |
| `app/models/academico.py:143–162` | `Turma.freq_geral`, `freq_geral_oferta` | L | Não usam dias/horas diretamente; são propriedades de frequência citadas no levantamento por contexto. | outro |
| `app/models/academico.py:202–240` | `Turma.dias_aula_efetivos`, `carga_horaria_aula`, `carga_horaria_total` | L | A contagem de dias depende da agenda da turma; a carga horária total multiplica uma duração única pelo total de dias. | C.H. |
| `app/models/academico.py:308–312` | `TurmaCurso` | L/E | Armazena a agenda atual da oferta em três campos escalares: CSV de dias e um único par de horários. | outro |
| `app/models/academico.py:345–384` | `TurmaCurso.carga_horaria_aula`, `carga_horaria_total` | L | Usa horário da oferta e fallback campo a campo para `Turma`; calcula duração única × aulas esperadas. | C.H. |
| `app/services/turma_curso.py:192–196, 219–266` | `_parse_dias`, `_conflitos_horario_concomitante` | L | Interpreta dias CSV; compara uma faixa única de horas entre ofertas, apenas se houver dia em comum e vigências sobrepostas. O conflito gera aviso, não bloqueio. | concomitância |
| `app/services/turma_curso.py:326–341` | `_sincronizar_legado` | E | Projeta os campos escalares da oferta de volta para `Turma`. | outro |
| `app/services/turma_curso.py:360–412` | `criar_oferta_inicial_da_turma` | L/E | Cria oferta inicial copiando dias e horas da turma. | escritores |
| `app/services/turma_curso.py:416–501` | `adicionar_oferta` | L/E | Recebe agenda, herda campos da turma se vazios e grava o par único de horários. | escritores |
| `app/services/turma_curso.py:508–552` | `editar_oferta` | L/E | Calcula conflitos com dias e horas escalares e grava os campos alterados. | escritores/concomitância |
| `app/services/turma_curso.py:648–664, 676–741` | `_data_bate_dias_semana`, `resolver_oferta_lancamento` | L | Com oferta explicitamente escolhida, verifica se a data cai em um dos dias cadastrados. A resolução automática de oferta única mantém as regras de validação existentes. | pauta/validação |
| `app/services/turma_curso.py:817–881` | `_dias_efetivos_da_oferta`, `datas_aula_oferta`, `datas_esperadas_oferta` | L | Resolve dias da oferta com fallback para a turma e gera as datas de aula, respeitando vigência e dias bloqueados. | pauta/validação |
| `app/services/turma_curso.py` | `_alunos_da_oferta` | — | Não lê dias ou horas; seleciona alunos da oferta. | outro |
| `app/registros/turmas.py:186–203` | agregação das linhas de turma | L | Une dias das ofertas; sem ofertas ativas, usa dias da turma. Faz `split` direto e não normaliza tokens. | filtros/listagem |
| `app/registros/turmas.py:213–331` | `aplicar_filtros_turmas` | L | Filtro por dia usa `COALESCE(oferta, turma)` e busca textual; filtro de horário compara com a hora de início escalar. | filtros/listagem |
| `app/registros/turmas.py:338–379` | `pos_filtrar_turmas` | L | Aplica limites de carga horária usando `carga_horaria_aula/total`; para várias ofertas usa a principal. | C.H./filtros |
| `app/registros/turmas.py:713–856` | `nova_turma` | L/E | Recebe dias e horas da turma; cria a oferta inicial a partir desses campos. | escritores |
| `app/registros/turmas.py:1127–1402` | `editar_turma` — GET/POST, G2/G3 | L/E | Edita agenda da turma; com uma oferta ativa, espelha os campos nela; com várias, há campos de oferta bloqueados. A regra atual de bloqueio usa número de ofertas, não uniformidade da agenda. | escritores/projeção |
| `app/registros/turmas.py:1489–1524` | `_dados_oferta_form` | L | Lê dias repetidos do formulário como CSV e lê um par de horários. Monta o payload usado pelas rotas de oferta. | escritores |
| `app/registros/turmas.py:1532–1618` | `turma_ofertas`, `turma_oferta_nova`, `turma_oferta_editar` | L/E | Exibe, adiciona e edita a agenda escalar por meio de `adicionar_oferta`/`editar_oferta`. | telas/escritores |
| `app/registros/turmas.py:1730–1982` | `carga_horaria_turmas` | L | Agrega C.H. por turma/curso; a propriedade da oferta ainda depende da multiplicação de duração única × aulas. | C.H./relatórios |
| `app/registros/turmas.py:2002–2110` | `ver_observacoes`, `imprimir_pauta` | L indireto | Observações não exibem horários; a pauta impressa usa a agenda por oferta para gerar datas de aula. | telas/impressões |
| `app/registros/core.py:257–300, 385` | `frequencia` — POST/GET | L indireto | Valida a data via `resolver_oferta_lancamento` e carrega o diário/frequências; não lê o par de horas diretamente. | frequência |
| `app/utils/logica.py:229–266` | `calcular_dias_aula_turma` | L | Converte dias da turma em índices semanais e conta datas dentro do período, descontando bloqueios. | pauta/validação |
| `app/utils/datetime_parse.py:14` | parser de formulário da turma | E | Atribui `hora_inicio` à turma a partir do formulário. | escritores |
| `app/utils/frequencia.py:106–174` | `contar_pendencias_frequencia`, `_pendencias_por_ofertas` | L indireto | Calcula pendências por meio de `datas_esperadas_oferta`. | frequência/dashboard |
| `app/main/dashboard_professor.py:28–38, 41–85, 166–175, 200–222` | `_horario_oferta`, `_aulas_pendentes` e listagens | L | Resolve um par de horas por oferta com fallback para turma; cria datas pendentes e exibe dias/horas. | frequência/dashboard |
| `app/services/estatisticas_professor.py:309–310` | estatísticas pedagógicas | L indireto | Calcula aulas esperadas por `datas_esperadas_oferta`; não lê hora do dia diretamente. | BI/relatórios |
| `app/registros/alunos.py:901–928` | resumo de oferta no contexto do aluno | L | Apresenta dias e um par de horas, com fallback para turma. | ficha/histórico |
| `app/registros/periodos.py:581–583` | certificado/relatório de período | L indireto | Usa C.H. total da oferta e, quando não disponível, a da turma. | BI/relatórios |
| `app/relatorios/painel_pedagogico/ficha_aluno.py:147–152` | formatação do vínculo da turma | L | Exibe agenda escalar da turma. | ficha/histórico |
| `app/templates/turmas/ofertas.html:48–50, 116–167, 280–343, 395–451` | listagem, edição, criação e JS inline | L/E | Mostra e edita um par de horários; o cálculo JS multiplica duração única pelos dias selecionados. | telas |
| `app/templates/turmas/editar.html:10, 183–224` | edição da turma | L/E | Mostra dias e horas da turma; bloqueia horários somente quando existem pelo menos duas ofertas. | telas |
| `app/static/js/turmas/nova.js:16–17, 78–101, 182` | cálculo de C.H. da turma nova | L | Calcula uma duração e multiplica pela quantidade de dias. | telas |
| `app/static/js/turmas/editar.js:8–20, 44, 95–121, 191` | cálculo de C.H. da turma editada | L | Recalcula usando um par de horários e os dias selecionados; tem mapa próprio de dias. | telas |
| `app/templates/turmas/listar.html:334–354, 406–414` e `listar copy.html:340–360, 412–420` | listagem | L | Exibe um horário para turma/oferta e C.H. por aula e total. O arquivo `listar copy.html` também contém a suposição, embora pareça cópia. | telas/listagem |
| `app/templates/turmas/detalhe.html:103–109, 245` | detalhe da turma | L | Exibe os dias e um intervalo; inclui sumário de horário por oferta. | telas |
| `app/templates/turmas/imprimir_listar_turma.html:86–99` | impressão da listagem | L | Resolve um único intervalo por oferta, com fallback para turma. | impressão |
| `app/templates/frequencia/lancar.html:85–86` | seletor de oferta da pauta | L | Mostra o intervalo único da oferta selecionada. | frequência |
| `app/templates/conselho/painel.html:90–98`, `conselho/fechamento.html:57–58` | conselho | L | Mostra agenda escalar da oferta ou da turma. | conselho |
| `app/templates/dashboard/professor.html:88–89` | dashboard do professor | L | Mostra o par de horas da aula. | dashboard |
| `app/templates/alunos/gerenciar.html:275–276, 303–304`, `atendimento_pedagogico.html:91`, `transferir.html:42–45, 126–127` | dados auxiliares do aluno | L | Exibe dias/horas da turma. Esses dados dependem da projeção para a turma quando há oferta. | ficha/telas |

A lista de dias efetiva também é usada indiretamente por `dashboard_professor.py`, `utils/frequencia.py`, `estatisticas_professor.py`, lançamento de frequência e impressão de pauta. `core.py` e `ver_observacoes` não leem as colunas de hora diretamente.

## 3. Parsing de dias

Encontrei duas conversões backend de CSV para dias, além de consumidores que apenas dividem o texto:

1. `app/services/turma_curso.py:192–196`, `_parse_dias`: separa por vírgula, remove espaços externos e passa para minúsculas. **Não remove acentos**.
2. `app/services/turma_curso.py:653–664`, `_data_bate_dias_semana`: usa `_parse_dias` e aceita nomes com e sem `-feira`, mas conserva acentos.
3. `app/utils/logica.py:229–252`, dentro de `calcular_dias_aula_turma`: usa dicionário próprio para dias como “Segunda” e formas “Segunda-feira”.
4. `app/registros/turmas.py:186–203` une dias por `split` e comparação literal, sem normalização.
5. `scripts/diagnostico_carga_horaria.py:48–110` mantém outra lista e separa tokens sem normalizá-los. É um diagnóstico da agenda da turma, não da oferta.
6. No frontend, `turmas/ofertas.html:406–431`, `static/js/turmas/nova.js:78–101` e `editar.js:95–121` têm mapas próprios. O JS da oferta remove acentos e usa abreviações internas.

Os formulários servem nomes completos em português com acentos (“Terça”, “Sábado”). A forma minúscula aparece no parser backend; as formas `-feira` são aceitas nas duas rotinas de data. Abreviações como “Seg.” e “Ter.” aparecem para exibição em `registros/turmas.py:95`, não como tokens de entrada conhecidos do parser backend. Há fixtures de teste com `"Terca"` sem acento; o parser de oferta não remove acentos, então esse token não é equivalente ao `"Terça"` esperado.

**Mapeamento numérico:** Python `date.weekday()` usa segunda=0; JavaScript `Date.getDay()` usa domingo=0. O mapa do frontend atual converte para `getDay()`. O formato proposto 0–6 é compatível com Python, mas não deve ser passado diretamente ao JS sem conversão.

Recomendo um conversor backend único para tokens de legado → weekday 0–6, com aliases explícitos e testes. Na tabela nova, guardar o número canônico; não persistir nomes localizados.

## 4. Pontos de risco, por gravidade

1. **Carga horária total incorreta com durações diferentes.** `TurmaCurso.carga_horaria_total` (`academico.py:367–384`) e os cálculos JS (`nova.js:89–101`, `editar.js:121` e `ofertas.html:415–431`) multiplicam uma duração única pela quantidade de aulas. Para a grade proposta, o total deve somar as durações das datas previstas; um dia sem horário torna o total desconhecido conforme a decisão assumida.
2. **Edição da turma pode sobrescrever a grade da oferta.** `registros/turmas.py:1365–1378` espelha campos da turma para a oferta única. `editar.html:220–224` só bloqueia horários com duas ou mais ofertas. A regra H0 de bloquear agenda de turma quando a grade da oferta não é uniforme conflita com esse comportamento atual e precisa ser aplicada também ao POST, não só ao controle visual.
3. **Projeções escalares podem mentir ou truncar.** `_sincronizar_legado` (`turma_curso.py:326–341`) copia a agenda da oferta para `Turma`. A proposta de deixar as horas projetadas em NULL se não forem uniformes evita parte do problema, mas **`dias_semana` é `varchar(20)`**, curto para representar todos os sete dias com nomes completos e vírgulas. Isso precisa ser resolvido na projeção (formato compacto ou ampliação controlada da coluna).
4. **Backfill pode combinar dados incompletos.** A herança atual é campo a campo: início da oferta pode herdar fim da turma ou vice-versa (`academico.py:353–357`). A migration proposta com `COALESCE(oferta, turma)` reproduz isso, mas pode criar intervalos incompletos. Não consultei as linhas do banco; um preflight precisa listar tokens desconhecidos, dias sem horas e pares incompletos antes do DDL.
5. **Concomitância compara um intervalo geral.** `_conflitos_horario_concomitante` (`turma_curso.py:219–266`) não consegue detectar corretamente horários diferentes por dia; precisa comparar cada weekday em comum e seu intervalo.
6. **Filtros escalares ficam ambíguos.** `aplicar_filtros_turmas` (`turmas.py:319–331`) usa `COALESCE` e igualdade sobre hora de início. O filtro deve consultar as linhas de horário; se dia e hora forem filtros simultâneos, ambos devem casar com a mesma linha diária.
7. **Telas exibem um único intervalo.** Listagem, detalhe, impressão, conselho, dashboard, pauta e telas do aluno ainda exibem um par de horas. Em uma agenda não uniforme, cada tela precisa exibir a grade ou indicar “varia”.
8. **C.H. por aula não tem mais um valor único.** A decisão `min_ch_aula` usa a menor duração semanal, o que resolve o filtro, mas a coluna de apresentação “C.H. por aula” deve indicar variação ou listar duração por dia; não deve exibir um valor médio implícito.
9. **Relações carregadas podem causar N+1.** A listagem de turmas carrega ofertas por `selectinload` (`turmas.py` na montagem de `stmt_base`) e calcula `carga_horaria_total` para cada oferta (`:508–517`, `:642–646`). A propriedade de cada oferta chama a agenda e os dias bloqueados. Uma relação `horarios` com lazy loading adicionaria consultas por oferta; o serviço deve carregar grades em lote e reutilizar bloqueios. `pos_filtrar_turmas` (`:338–379`) também calcula C.H. durante iteração. Dashboards e pendências percorrem ofertas e datas (`dashboard_professor.py:85, 222`; `utils/frequencia.py:155–174`), portanto o serviço de grade deve evitar consultas por data/oferta.
10. **Compatibilidade com criação/edição da oferta.** `adicionar_oferta`, `editar_oferta` e `criar_oferta_inicial_da_turma` aceitam o par escalar. Todos os escritores precisam passar a chamar o serviço único; não deve haver gravação paralela fora dele.

## 5. Conflitos com as decisões/desenho

- **Convenção numérica:** a decisão `weekday()` 0–6 é clara no backend, mas diverge de `Date.getDay()` no JS atual. É um ponto de conversão obrigatório, não um conflito insolúvel.
- **Domingo:** o modelo/proposta comporta 0–6, mas o formulário de ofertas e `registros/turmas.py:1562` listam apenas segunda a sábado. A interface atual não permite domingo.
- **Projeção `dias_semana`:** a proposta diz projetar sempre a lista completa em CSV, mas a coluna tem 20 caracteres. Mesmo a grade uniforme pode exceder esse limite.
- **Herança:** a regra proposta `COALESCE(oferta, turma)` é coerente com a implementação atual, que herda início e fim separadamente. É importante materializar todos os dias efetivos antes de parar de consultar os campos da turma.
- **Sem horário:** a decisão permite uma linha sem horas. Se apenas um dos extremos estiver preenchido, a regra não foi definida; o modelo atual permite campos incompletos e retorna C.H. nula. Recomendo validar os extremos em par e rejeitar `fim <= início` quando preenchidos.
- **Edição de turma:** bloquear uma grade não uniforme está de acordo com a decisão 4, mas hoje o sistema usa “duas ou mais ofertas” como critério. Será necessário trocar a condição pelo estado de uniformidade e protegê-la também no backend.
- **`_validar_horario_concomitante`:** o nome citado no levantamento não existe; o serviço atual chama-se `_conflitos_horario_concomitante`.
- **`turmas/nova.html`:** não encontrei esse caminho; a criação usa `turmas/nova_turma.html`, junto de `static/js/turmas/nova.js`.
- A head Alembic `a8b9c0d1e2f3` e o banco atual coincidem. O MER já documenta essa head no complemento de 26/10; a metadata do topo ainda mostra 25/10.

## 6. Decisões pendentes antes de H1

1. **Mudança de grade no meio do período:** a agenda atual é editável, e as datas de frequência não guardam snapshot do horário.
   - Opção A: a grade atual vale retroativamente para todo o período da oferta.
   - Opção B: versionar a grade por vigência ou criar eventos de mudança com data efetiva.
   - **Recomendação:** decidir antes do H1. Se a C.H. histórica ou certificado precisa preservar o horário praticado, usar vigência por versão; caso contrário, registrar explicitamente que a edição recalcula a carga histórica.

2. **Oferta com um único extremo de horário preenchido:**
   - Opção A: permitir e tratar a C.H. como desconhecida.
   - Opção B: exigir ambos os extremos ou ambos NULL.
   - **Recomendação:** B; preflight lista dados existentes incompletos e migration interrompe até serem corrigidos ou resolvidos.

3. **Dia agendado sem horas em uma grade com outros dias completos:**
   - Opção A: C.H. total da oferta fica `None`.
   - Opção B: somar os dias com horas e marcar o total como parcial.
   - **Recomendação:** A para evitar subcontagem silenciosa; exibir quais dias estão sem horário.

4. **Domingo:**
   - Opção A: manter formulário segunda–sábado.
   - Opção B: oferecer os sete dias, coerente com 0–6.
   - **Recomendação:** B se domingo é um dia válido para a instituição; caso não seja, restringir o domínio formalmente a 0–5.

5. **Par horário atravessando meia-noite:** o código atual considera `fim <= início` inválido.
   - Opção A: manter aulas no mesmo dia.
   - Opção B: suportar aulas noturnas com fim no dia seguinte.
   - **Recomendação:** A nesta mudança, a menos que haja oferta que atravesse meia-noite.

## 7. Escopo estimado H1–H3

Estimativa inicial: **aproximadamente 25–35 arquivos** no H1–H4, contando testes e templates; a quantidade final depende das decisões acima.

- **H1 — modelo, migration, serviço, projeção (4–6 arquivos):** modelo/relacionamento, migration e backfill, novo serviço `turma_curso_horario.py`, MER e testes de schema/migração. Centralizar em `grade_da_oferta`, `definir_grade`, `duracao_do_dia`, `grade_uniforme`, `resumo_grade` e `sincronizar_projecao_horario`.
- **H2 — escritores (5–8 arquivos):** `adicionar_oferta`, `editar_oferta`, `criar_oferta_inicial_da_turma`, `nova_turma`, `editar_turma`/G2, `_dados_oferta_form` e rotas de oferta. Todos devem gravar pela mesma transação/serviço; erro de validação não pode deixar grade parcialmente atualizada.
- **H3 — leitores, por grupo (aprox. 15–22 arquivos):**
  1. Agenda e validação: `datas_aula_oferta`, `resolver_oferta_lancamento`, `calcular_dias_aula_turma`, frequência e pendências.
  2. Concomitância: `_conflitos_horario_concomitante` e seus usos em criar/editar.
  3. C.H.: propriedades de `TurmaCurso`, listagens, filtros de carga e `carga_horaria_turmas`.
  4. Filtros/listagem/impressão: `aplicar_filtros_turmas`, resumo de dias, listagem, detalhe e impressão.
  5. Dashboard e registros: agenda do professor, aluno, conselho, ficha/histórico/certificado e BI/relatórios.
  6. Eager loading: carregar grades e dias bloqueados em lote para listagem/dashboard.
- **H4 — liberar interface de grade variável:** ofertas, turma nova e os fluxos de edição. O padrão deve preencher o mesmo horário em todos os dias; o modo personalizado abre campos por weekday. Só liberar depois dos leitores de H3 apresentarem corretamente uma grade não uniforme.
- **H5 — remover colunas antigas:** etapa separada, após confirmar que nenhum leitor ou integração usa os campos escalares. Não misturar essa remoção com o primeiro rollout.

## 8. Testes sugeridos por etapa

Sem criar testes, os nomes/cenários que recomendo:

- **H1:** `test_turma_curso_horario_schema.py` — unicidade por oferta/dia, domínio 0–6, FKs/cascade, checagem de par válido; `test_turma_curso_horario_migration.py` — COALESCE oferta→turma, nomes com acento, dia desconhecido, par incompleto e backfill repetível.
- **H2:** `test_definir_grade.py` — substituir grade inteira sem duplicar, rollback atômico e idempotência; `test_turma_curso_horario_escritores.py` — oferta nova, oferta editada, oferta inicial e edição G2 sem sobrescrever grade não uniforme.
- **H3 agenda/validação:** `test_datas_aula_oferta_grade.py` — weekdays 0–6, vigência e dias bloqueados; `test_resolver_oferta_grade.py` — data em dia agendado/ausente, mantendo explicitamente a regra atual de oferta única.
- **H3 concomitância:** `test_concomitancia_grade_por_dia.py` — mesmo dia/horas sobrepostas, dias diferentes, horários adjacentes e vigência sem interseção; confirmar que continua apenas aviso.
- **H3 C.H.:** `test_carga_horaria_oferta_variavel.py` — soma de duração por ocorrência, dia sem horário, bloqueios e limites min/total.
- **H3 leitores:** `test_filtros_turma_grade.py`, `test_impressao_grade_oferta.py`, `test_dashboard_grade_oferta.py`, `test_ficha_aluno_grade_oferta.py` e `test_projecao_grade_uniforme.py`.
- **H4 UI:** teste da submissão do modo comum e do personalizado, campos por dia, seleção de domingo conforme decisão e erros de intervalo no servidor.

**Resumo do levantamento:** o serviço proposto e a tabela por weekday encaixam na arquitetura, mas C.H., projeções escalares, edição de turma e telas são os pontos de maior impacto. A mudança deve manter os leitores usando um serviço único e tratar a política de alteração histórica antes de abrir a edição de horários diferentes.
