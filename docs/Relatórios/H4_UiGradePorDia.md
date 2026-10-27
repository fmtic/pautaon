# H4 — UI de grade por dia (horário diferente por dia na oferta)

**Data:** 26/10/2026 · **Branch:** `nova_feature` (sem push) · **Revisão Alembic:** head única `5730d7c594ba` (sem migration nova)
**Suíte ao final:** **640 passed**, 0 falhas, sem `deselect` (614 antes da etapa + 26 novos) · **Ruff:** `--select F821` limpo
**Fontes:** MER (§7.32a, §8.10, §10, §12.25), backlog, relatórios H0 (§3 parsing/JS, §4 riscos, §7 H4) e H3e/H3f (inventários) em `docs/Relatórios/`.
**Escopo:** permitir, na criação/edição de turma e de oferta, **horário diferente por dia da semana** (Segunda–Sábado, weekday 0–5, sem domingo), quando fugir da regra geral — modo padrão (grade uniforme, como antes) × modo personalizado ("Horário diferente por dia"). Validação autoritativa no servidor (`definir_grade`); toda gravação de agenda passa por `definir_grade`; os escalares da Turma deixam de ser escritos pela rota — só pela projeção (`sincronizar_projecao_turma`). **Nada de schema, nada de remoção de colunas (H5).**

---

## 1. Commits da etapa

| Hash | Passo | Mensagem (resumo) |
|------|-------|-------------------|
| `318ac3e` | P2 | Contrato do formulário: `grade_do_formulario` única, `agenda=` nos serviços, projeção da Turma só por `sincronizar_projecao_turma`, re-render preenchido nos erros de agenda, bloqueio "2+ ofertas" — 614 passed |
| `d20a794` | P3 | Frontend: módulo compartilhado `grade_horario.js` (dias 0–5 sem domingo, C.H. estimativa, puras), macro `_agenda_macros.html`, `ofertas.html`/`editar.html`/`nova_turma.html` adaptados, `editar.js`/`nova.js` delegando ao módulo — 614 passed |
| `61cf73e` | P4 | Testes: `test_ui_grade_por_dia.py` (13), smoke de leitores com grade variável criada pela UI (7, sem N+1), puras do `grade_horario.js` via node (6, skip documentado) — **640 passed** |
| `d03816c` | P7 | MER (§7.32a, §8.10, §10, §12.25) e backlog — H4 concluída |
| (este) | P8 | Relatório final |

Estado antes da etapa: HEAD `a51109a` (H3f-P8), suíte **614 passed**, scratch recriado de dump novo (P0). Arquivos por commit: P2 `app/registros/turmas.py` + `app/services/turma_curso.py` (+2 testes de contrato); P3 8 arquivos (módulo JS novo, macro nova, 4 templates, 2 JS); P4 3 arquivos de teste novos (939 linhas).

---

## 2. PASSO 1 — Levantamento e checkpoints (nenhum PARE)

- **Checkpoints da spec:**
  - `Turma.hora_inicio`/`hora_fim`/`dias_semana` são **NULLABLE** e **nenhum CHECK/NOT NULL impede escalares NULL** → sem PARE (a projeção de grade não uniforme — dias + NULL — é segura).
  - `adicionar_oferta`, `editar_oferta` e `criar_oferta_inicial_da_turma` **já aceitavam** `agenda=[(weekday, início, fim)]` (H2/H3f) → nada a mudar nos serviços de escrita; só `sincronizar_projecao_turma` (nova) foi criado.
- **Lógica ATUAL do C.H. no JS (documentada antes de mexer):** `nova.js`/`editar.js`/JS inline de `ofertas.html` replicavam o mesmo cálculo — `(fim − início)` do **par único** × nº de dias marcados × **semanas entre data_inicio e data_fim** (`round`), com premissas: **sem** desconto de dias bloqueados/feriados, **sem** consideração de período (usa as datas do form como estão), mapa de dias via `getDay()` JS (**domingo = 0**) — o mapa antigo tratava o índice 0 como Domingo, incoerente com o Python (0 = Segunda).
- **Mapa de dias real (servidor):** weekday Python 0–5 (Segunda–Sábado); `definir_grade` recusa domingo; o CHECK `ck_tch_dia` do banco permanece 0–6 (tolerância ao legado — NÃO mudado).
- **Outros formulários que enviam dias/horas:** inventário exaustivo por grep — além dos três (nova_turma, editar_turma, ofertas), só `test_isolamento_unidade_escrita.py` monta payload de `nova_turma` diretamente (ajustado no P2). Nenhum outro writer de agenda existe.
- **Desvios aprovados (P1 → decisão do responsável):**
  1. Serviços já aceitavam `agenda=` — P2 só conecta o parsing, não altera assinaturas;
  2. A tela **nova_turma atual não expõe agenda** — o contrato é o mesmo, erros de agenda viram flash + redirect, e a grade segue para a **oferta inicial** via `criar_oferta_inicial_da_turma(agenda=)`; o por dia é editado em Cursos da Turma;
  3. Criado `sincronizar_projecao_turma` (a rota não tem mais fonte direta dos escalares da Turma com oferta única);
  4. JS testado via `node -e` com skip documentado (repo sem suíte JS própria/CI).

---

## 3. Contrato do formulário (PASSO 2)

**Parsing única `grade_do_formulario(form)`** (`app/registros/turmas.py`) usada por `nova_turma`, `editar_turma` e as duas rotas de oferta:

| Campo | Função |
|-------|--------|
| `dias_semana` (repetido) | checkbox de dia — valor = **weekday 0–5** numérico ou **nome legado** ("Segunda", "Quarta-feira"… via `_token_weekday`) |
| `hora_inicio`/`hora_fim` | **par padrão** (modo padrão: replicado nos dias marcados; no personalizado serve de pré-preenchimento) |
| `horario_por_dia` | interruptor do modo personalizado (`1/on/true/sim/yes`) |
| `hora_inicio_<w>`/`hora_fim_<w>` (w = 0–5) | par **por dia**; campos de dias **não marcados são ignorados** |

Retorno: `{por_dia, dias, hora_inicio, hora_fim, itens, erro}` — `itens` = `[(weekday, início, fim)]` pronto para o `agenda=` dos serviços (`None` quando `erro`). **Mensagens de erro** (autoritativo confirmado no `definir_grade`):

- `"Domingo não é dia de aula — use segunda a sábado."` / `"Dia de aula inválido: “{bruto}”. Use segunda a sábado."`
- `"O fim do horário deve ser maior que o início."` (modo padrão)
- `"Informe o horário de início e de fim da {nome}."` / `"O horário da {nome} deve terminar depois de começar."` (por dia)
- `_AGENDA_INCOMPLETA` (sem dias e sem par) → **não** é erro de tela: mantém o caminho de herança/fallback do serviço (compatibilidade com payloads antigos).

**Comportamento por rota:**
- Rotas de oferta (`turma_oferta_nova`/`turma_oferta_editar`): erro ⇒ rollback + flash + **HTTP 200** com `_render_ofertas(rascunho, oferta_aberta)` — formulário volta **preenchido** (inclusive modo personalizado aberto e collapse reaberto via `window.ofertaAberta`); ValueError do `definir_grade` (ex.: concomitância interna) segue o mesmo caminho.
- `nova_turma`: erro de agenda ⇒ flash + redirect (302) — a tela não tem agenda; com grade válida, `agenda=grade["itens"]` vai para `criar_oferta_inicial_da_turma` e a Turma recebe escalares **só por projeção**.
- `editar_turma` POST: `mudou_agenda` = `sorted(grade["itens"])` × `grade_da_oferta` — com **1 oferta** grava via `definir_grade` da oferta única + `sincronizar_projecao_turma` (nada de escalar direto); com **0 ofertas** escreve os escalares na Turma (único caso restante); com **2+ ofertas** (`agenda_bloqueada`) mantém o bloqueio no POST (só nome/período/ordenação). **Decisão H4:** o critério de bloqueio é apenas **"2+ ofertas"** — turma com 1 oferta não uniforme é **editável** pelo mesmo componente (o bloqueio por uniformidade do H2 foi substituído).
- Edição de oferta com grade **não uniforme** abre o formulário já em **modo personalizado** (via `_estado_agenda_da_grade`, que detecta >1 par).

**Projeção (nova, `app/services/turma_curso.py`):** `sincronizar_projecao_turma(turma)` espelha em `Turma.dias_semana/hora_inicio/hora_fim` a **projeção da oferta única ativa** (uniforme: dias + par; não uniforme: dias + NULL); devolve `False` sem alterar nada com 0 ou 2+ ofertas. Roda **depois** de `definir_grade`.

---

## 4. Frontend (PASSO 3)

- **`app/static/js/turmas/grade_horario.js`** (novo, ~365 linhas) — **substitui os três mapas de dia** (`nova.js`, `editar.js`, JS inline de `ofertas.html`):
  - puras exportadas (também para teste em node): `getDayParaWeekday = (getDay()+6)%7`, `weekdayValido` (0–5), `duracaoDiaMinutos`, `ocorrenciasWeekday` (inclusive nas bordas; weekday inválido → 0), `estimarCHMinutos` (`Σ duração_dia × ocorrências`), `formatarCH` (`"1h"`, `"1h30min"`, `"—"`), `montarItensGrade(form)`, `serializarGrade`/`deserializarGrade` (formato `"w:HH:MM-HH:MM|..."`, idêntico ao `_serializar_estado_agenda` do servidor);
  - `initGrade(form, {getDatas, bloqueado})`: switch `[data-grade-switch]`, blocos `[data-grade-dia]`, pré-preenchimento dos pares por dia com o par padrão, **confirmação ao desligar** com valores diferentes ("perde as diferenças"), C.H. recalculada no carregamento e a cada mudança, rotulada **"(estimativa — valor autoritativo é o do servidor)"**; `"varia"` quando durações diferentes;
  - acessibilidade: labels por dia ("Início — Quarta"), fluxo de teclado natural (inputs são `<input type="time">` nativos com `label for`), erros inline junto ao campo (servidor); sem domingo em nenhum mapa.
- **`app/templates/turmas/_agenda_macros.html`** (novo): macro `agenda_campos(estado, prefix, com_switch, bloqueada)` — checkboxes `name="dias_semana"` com `data-weekday`, interruptor `horario_por_dia`, pares `hora_inicio_<w>`/`hora_fim_<w>`, mensagem de erro do estado. Prefixos por formulário (`novo…`, `ed<id>…`, `agenda…` na turma) para conviverem na mesma página.
- **Templates/JS adaptados:** `ofertas.html` (tabela lendo `GradeExibicao` — badge **"varia"** — forms de nova/editação com a macro + `getDatas` do próprio form), `editar.html` (macro com `estado_agenda`, par padrão pré-preenchido, `window.gradeOriginal`, readonly só 2+ ofertas — removidos o hidden `original_dias_semana` e o branch readonly de não-uniforme com 1 oferta), `nova_turma.html` (carrega o módulo), `editar.js` reescrito (`initGrade` quando editável; estimativa somente-leitura quando bloqueada; `handleSubmit` compara `serializarGrade(montarItensGrade(form))` × `gradeOriginal` — ou datas mudadas — para a confirmação de limpeza de lançamentos), `nova.js` reescrito (sem funções duplicadas).
- Node `--check` limpo nos dois JS; teste inline do contrato (serializar/desserializar) no P3.

---

## 5. Testes (PASSO 4) — suíte 614 → 640

| Arquivo | Casos | Cobre |
|---------|-------|-------|
| `tests/test_ui_grade_por_dia.py` | 13 | modo padrão (idêntico ao comportamento atual); personalizado cria **não uniforme** em nova_turma/oferta nova/oferta editada; projeção da Turma (dias + NULL); turma 1 oferta não uniforme **editável**; editar_turma grava via grade (1 oferta) e mantém bloqueio (2 ofertas) no POST; erros (fim ≤ início, dia sem hora, domingo) com **re-render 200 preenchido** (switch checked, valor digitado preservado); hora em dia não marcado **ignorada**; **idempotência** de reenvio |
| `tests/test_h4_leitores_grade_variavel_smoke.py` | 7 | oferta NÃO uniforme criada por **POST real da UI**; todos os leitores migrados (listagem + filtros dia+hora na **mesma linha** (positivo e negativo), detalhe, impressão, tela de cursos com badge "varia", C.H. oferta==turma, concomitância com `agenda=`, dashboard por data nas duas faixas, `/alunos` seletor, atendimentos, histórico, ficha, conselho + fechamento, transferência, frequência + relatório) **sem erro e com o texto por dia**; **sem N+1 de grade** (contador `before_cursor_execute` estável) |
| `tests/test_grade_horario_js.py` | 6 | funções puras do módulo em `node -e` (conversão `(getDay()+6)%7` sem domingo, durações, ocorrências, C.H. estimativa, formatação, serialização/tolerância do inverso); **skip documentado** sem node (repo sem suíte JS/CI própria — ambiente de dev tem node v24) |

**Testes existentes alterados (e por quê — mudança de contrato do formulário, esperada):**
- `tests/test_isolamento_unidade_escrita.py` — payload de `nova_turma` com `dias_semana` passou a exigir o par `hora_inicio`/`hora_fim` (dia marcado sem par é erro do contrato novo);
- `tests/test_turma_curso_horario_escritores.py` — `test_editar_turma_post_nao_sobrescreve_grade_nao_uniforme` → `test_editar_turma_post_substitui_grade_nao_uniforme`: reflete a **decisão H4** (1 oferta: POST editável substitui a grade; o bloqueio por uniformidade do H2 foi substituído pelo critério "2+ ofertas").

Nenhum outro teste existente foi tocado; as falhas encontradas durante o desenvolvimento dos novos testes (concomitância = 1 mensagem por oferta concorrente; dashboard sem dias já lançados; `/frequencia_relatorio` restrito ao papel pedagógico) eram **expectativas erradas do teste**, não bugs — corrigidas no próprio teste.

---

## 6. Ensaio no scratch (PASSO 5) — registrado

Banco: `pautaon_ensaio` (recriado no P0 de dump novo do principal, head `5730d7c594ba` verificada). App montado com `DATABASE_URL` do scratch (principal intocado, nenhuma sessão derrubada); test client autenticado como usuário real do scratch (pedagógico MGB, unidade 2); CSRF desabilitado apenas no config do ensaio (mesma parsing/validação da UI real). Alvo: **turma 10 «Informática» (real), oferta 14** (uniforme Segunda, Quarta 14:00–17:00, vigência 2026-08-03 a 2026-12-10).

Saída registrada (script temporário, apagado após o uso):

```
ANTES: oferta 14 da turma «Informática» — dias Segunda, Quarta, 14:00–17:00,
       vigência 2026-08-03 a 2026-12-10, uniforme=True

POST /turma/oferta/14/editar (modo personalizado: Seg 08:00–11:00, Qua 14:00–17:00) -> HTTP 302
DEPOIS grade: [(0, '08:00:00', '11:00:00'), (2, '14:00:00', '17:00:00')]
  uniforme=False | carga_horaria_aula(oferta)=None
C.H.: bloqueios no período=5 (07/09, 12/10, 02/11, 15/11, 20/11)
  datas esperadas=35 | ocorrências Seg=16 Qua=19
  cálculo independente=6300 min | oferta.carga_horaria_total=6300 | turma.carga_horaria_total=6300

LEITORES: [OK] GET /turma (exibe por dia)
          [OK] GET /turma?dia=Quarta&horario_inicio=14:00 (casa na mesma linha)
          [OK] GET /turma?dia=Segunda&horario_inicio=14:00 (NÃO casa — par do dia)
          [OK] GET /turma/10 (detalhe) · /imprimir-pauta · /turma/10/ofertas
               (badge "varia" + switch aberto + texto por dia)
          [OK] GET /turmas/carga-horaria
          [OK] GET /alunos (data-turma-horario por dia) · histórico · ficha 360°
               (?turma_id=10&oferta_sel=…) · /aluno/transferir (seletor)
          [OK] GET /conselho · /conselho/fechamento/10
          [OK] GET /frequencia?turma_id=10 · /frequencia_relatorio?turma=10
          [OK] GET /dashboard (professor 90): pendências 03/08 08:00–11:00 e
               05/08 14:00–17:00 — cada weekday com o SEU intervalo
N+1: consultas a turma_curso_horario na listagem: 3 → 3 (estável)

RESULTADO: OK — sem falhas
```

- **Idempotência provada no scratch:** o ensaio foi executado duas vezes (a primeira esbarrou no CSRF do ambiente de produção espelhado); o **reenvio** do mesmo formulário não alterou a grade nem o C.H. (segunda execução: `ANTES` já não uniforme → `DEPOIS` idêntico).
- Escalar observado (fora do caminho H4, **sem efeito em nenhum leitor**): `Turma.dias_semana` da turma 10 permaneceu o valor legado ("Segunda") — a projeção para a Turma só roda nas rotas de turma (`editar_turma`/`nova_turma`), não na edição de oferta; a listagem/filtros/detalhe não leem essa coluna (leem a grade), e no `editar_turma` a projeção a reconcilia. Registrado como **pergunta aberta para o H5**.
- Scratch **recriado** de dump novo após o ensaio (verificação: head `5730d7c594ba`, oferta 14 de volta uniforme, 8 linhas de grade nas 5 ofertas); scripts temporários apagados.

---

## 7. Checklist manual no navegador (PASSO 6 — para o responsável)

Pré-requisito: sessão em ambiente com a branch; unit MGB (ou a unidade da turma de teste). A suíte roda sem CSRF — **no navegador o token está ativo** e nenhuma tela nova o esqueceu (os formulários usam o mesmo `<form>` existente).

1. **Modo padrão (comportamento atual):** `/turma/10/ofertas` → editar a oferta → **sem** ligar o interruptor → Segunda+Quarta, 08:00–11:00 → salvar. A tela de cursos deve mostrar `Segunda, Quarta` e `08:00 - 11:00` (texto antigo, byte a byte) e "C.H. por aula" com valor único (sem "varia").
2. **Modo personalizado:** mesma oferta → ligar **"Horário diferente por dia"** → os dias marcados abrem cada um com seu par pré-preenchido (08:00–11:00) → mudar Quarta para 14:00–17:00 → salvar. A lista `/turma` deve mostrar `Segunda 08:00–11:00; Quarta 14:00–17:00`, a coluna C.H. por aula **"varia"** (detalhe no `title`), e a tela de cursos reabrir **já em modo personalizado** com os valores.
3. **Filtro por dia+hora na mesma linha:** `/turma?dia=Segunda&horario_inicio=14:00` **não** retorna a turma; `dia=Quarta&horario_inicio=14:00` retorna.
4. **Personalizado → padrão:** desligar o interruptor com horários diferentes ⇒ o navegador pede confirmação ("perde as diferenças"); aceitar ⇒ par único replicado; a C.H. estimativa do form acompanha; o valor exibido na listagem (servidor) continua correto.
5. **Erro de intervalo:** Quarta 14:00–13:00 → salvar ⇒ a página volta **200** com a mensagem "O horário da Quarta deve terminar depois de começar." junto ao campo, **modo personalizado ainda aberto** e os valores digitados preservados; nada gravado (reabrir a oferta mostra a grade antiga).
6. **Dia marcado sem hora / domingo:** marcar Sexta sem preencher ⇒ "Informe o horário de início e de fim da Sexta-feira." (mesmo re-render). Domingo não existe em nenhuma opção (Segunda–Sábado).
7. **Turma com 1 oferta não uniforme é editável:** `/turma/editar/10` com a grade do item 2 ⇒ **sem** o aviso "Somente leitura", componente por dia presente e aberto; salvar e conferir que a oferta recebeu a grade nova e a listagem reflete.
8. **Turma com 2+ ofertas bloqueada:** turma multi-oferta (ex.: 9) ⇒ `/turma/editar/9` mantém os campos de agenda **somente leitura** com aviso no topo; um POST forjado com agenda não altera oferta nem Turma.
9. **Retroatividade (aviso existente):** ao salvar a mudança de grade, permanece o aviso de que vale para todo o período, inclusive aulas já lançadas; o dashboard do professor passa a mostrar cada data **com o intervalo do seu weekday**.

---

## 8. Mudanças de texto/tela

- Três telas ganham o interruptor **"Horário diferente por dia"** + blocos por dia com labels completos ("Início — Quarta") e erros inline; nenhum texto antigo de grade **uniforme** mudou (caracterizado nos testes e no ensaio).
- C.H. no form passa a ser rotulada **estimativa** ("valor autoritativo é o do servidor"); antes era apresentada como valor.
- Tela de cursos: coluna de horário por dia quando não uniforme + badge **"varia"** (já calculados pelo H3d; o H4 só migrou a **tabela/formulários** que ainda liam projeção/JS próprio).
- `editar.html`: removido o branch "somente leitura" para turma de **1 oferta não uniforme** (decisão H4) e o hidden `original_dias_semana` (a comparação passou a usar `window.gradeOriginal` serializado).
- `nova_turma`: nenhuma mudança visível de tela (a tela não expõe agenda; aceita o contrato por POST para a oferta inicial).

## 9. Desvios e Perguntas abertas

**Desvios (todos aprovados no P1):** §2 acima — `agenda=` já existia nos serviços; tela nova_turma sem agenda; criação de `sincronizar_projecao_turma`; teste JS via node com skip documentado.

**Perguntas abertas (para H5/deploy):**
1. Apertar `ck_tch_dia` do banco para 0–5 (exige migration de revisão + checagem de legado com dia 6) — permanece de §12.25.
2. `Turma.dias_semana/hora_inicio/hora_fim` podem ficar **defasadas** quando a agenda muda pela tela de **oferta** (a projeção só roda nas rotas de turma) — invisível para todos os leitores migrados (nenhum lê a coluna com grade presente); no H5, ao remover as colunas, a pergunta morre — conferir se algo ainda as lê antes do drop (inventário H3f §5).
3. Certificado e painéis agregados leem por oferta? (adiado H3e → avaliar no H5).
4. UX de "desligar o interruptor" usa `confirm()` do navegador — padronizar com os modais existentes? (fora do escopo H4).

## 10. O que NÃO mudou

- **Schema:** nenhuma migration; head segue `5730d7c594ba`; as colunas escalares de `turma_curso`/`turma` permanecem (remoção = H5).
- **CHECKs:** `ck_tch_dia` continua 0–6 no banco (domínio 0–5 é regra do serviço/formulário); `ck_tch_par`/`ck_tch_fim_maior`/`uix_turma_curso_horario_dia` intactos.
- **Escritores:** `definir_grade` continua a única gravação de agenda; `sincronizar_projecao_horario` o único escritor da projeção da oferta (a nova `sincronizar_projecao_turma` apenas **copia a projeção** para a Turma — não inventa valores).
- **Fallbacks de legado** (oferta/turma sem grade → colunas escalares com `logger.warning`): inalterados.
- **Regras de validação do servidor**, aviso de retroatividade, concomitância como **aviso nunca bloqueio**, isolamento por unidade, permissões: inalterados.
- Banco **principal**: nenhum toque além dos dumps de leitura; sessões não derrubadas.
