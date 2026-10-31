# Roteiro de Teste Manual — pautaON (M1)

**Branch:** `nova_feature` · **HEAD de partida:** `a5b34c8` (banco no `8d2e3f4a5b6c`) · **Data:** 28/10/2026
**Objetivo:** cobrir o que a suíte automatizada **não** cobre — navegador real, CSRF ligado,
JavaScript da agenda, impressão e leitura visual dos números. A suíte (722 passed) roda com
`WTF_CSRF_ENABLED=False` e sem browser; este roteiro é a cobertura complementar.

> **Como preencher:** em cada caso, marque `OK`, `Falhou` ou `Obs.` e escreva a observação.
> Divergência de número é **achado** — registre, não corrija no meio do teste.

---

## 0. Preparação

### 0.1 Semente (banco de ensaio)

```powershell
# 1) estado limpo do rótulo (opcional, mas recomendado antes do ciclo completo)
.\.venv\Scripts\python.exe scripts\semear_roteiro_manual.py --limpar

# 2) semear (idempotente: pode rodar 2x sem duplicar)
.\.venv\Scripts\python.exe scripts\semear_roteiro_manual.py
```

O script **recusa** banco cujo nome não contenha `ensaio` (lê `DATABASE_URL` do ambiente ou do
`.env` e troca o banco; padrão `pautaon_ensaio`, alterável com `--db`).
A saída imprime: IDs criados, **usuários com senha**, **datas de aula** e **URLs prontas**.

### 0.2 Subir o app apontando para o ensaio

```powershell
$env:DATABASE_URL = "postgresql://usuario:senha@localhost:5432/pautaon_ensaio"
.\.venv\Scripts\python.exe run.py
```

`config._get_database_uri()` lê `DATABASE_URL` e o `load_dotenv()` **não sobrescreve** variável de
ambiente — logo o `.env` versionado continua apontando para o banco principal e **nada em `app/`
ou em configuração versionada precisa ser alterado**. Se o app não escutar em `5000`, ajuste a
porta no `run.py` (ou use `flask run --port 5055`) e troque `{BASE}` nos casos abaixo.

### 0.3 Credenciais (todas com a senha `[senha definida pelo seed / ROTEIRO_SENHA]`)

| Perfil | E-mail |
|---|---|
| admin | `admin.m1@roteiro.local` |
| gerência | `gerencia.m1@roteiro.local` |
| pedagógico | `pedagogico.m1@roteiro.local` |
| secretaria | `secretaria.m1@roteiro.local` |
| professor | `professor.m1@roteiro.local` |

### 0.4 IDs da execução de referência (28/10/2026)

A semente imprime os IDs a cada execução; **após `--limpar` eles mudam**. Se os IDs abaixo não
existirem no seu banco, use os impressos pelo script.

| Objeto | ID | Objeto | ID |
|---|---|---|---|
| Unidade Central | 13 | Turma A (oferta única) | 30 / oferta 44 |
| Unidade Vizinha | 14 | Turma B (2 ofertas) | 31 / ofertas 45 (Profissionalizante) e 46 (Meio Ambiente) |
| Período Vigente (01/08–31/12/2026) | 22 | Turma C (grade variável) | 32 / oferta 47 |
| Período Encerrado (01/01–31/07/2026) | 23 | Turma D (lixeira) | 33 / ofertas 48 (marcador) e 49 (desativada antes) |
| Período Vizinha | 24 | Turma Vizinha | 34 / oferta 50 |

Alunos: Ana A1 `1482` · Bruno A2 `1483` · Carla B1 `1484` · Diego B2 `1485` · Elisa C1 `1486` ·
Fabio C2 `1487` · Gabriela Transf `1488` · Heitor Desent `1489` · Inacia D-ativa `1490` ·
Joao D-inativo `1491` · Aluno Vizinha `1492`.
Datas com aula: A legado `03/08` e `10/08` · B1 `03/08`, `10/08`, `17/08` · B2 `04/08`, `11/08` ·
C `05/08`, `12/08` · D `05/01`, `12/01`.

### 0.5 Cenário (o que esperar da semente)

| Turma | Ofertas | Frequência semeada | C.H. Total |
|---|---|---|---|
| A — Oferta Única (Esporte) | 1 (Natação) | **legado NULL**: Ana A,A; Bruno F,A → 3P/1F = **75,0%** | **88h** |
| B — Dois Cursos | 2: Informática (Profissionalizante, principal) e Horta (Meio Ambiente) | B1: Carla A,A,F e Diego A,F → 3P/2F = **60,0%**; B2: Diego A e Carla F,F → 1P/2F = **33,3%**; turma = 4P/4F = **50,0%** | **176h** (88h + 88h) |
| C — Grade Variável | 1 (Informática) | Elisa A,B e Fabio J,F → 2P/1F (1 J fora) = **66,7%** | **141h30min** (22×120 + 22×180 + 21×90 min) |
| D — Excluída (lixeira) | 2 (Informática, Horta) | Inacia A,C no período encerrado (100%) | — |

---

### 0.6 Ordem de execução e restauração do cenário

- Execute os blocos **na ordem** (1 → 10). Os blocos 2, 3, 6 e 7 **criam/excluem/alteram** dados.
- Depois dos casos marcados com **[restaurar]**, rode a semente novamente
  (`.venv/Scripts/python.exe scripts/semear_roteiro_manual.py`) antes de seguir — ela é
  idempotente e devolve o cenário ao estado descrito em §0.5.
- Casos que só leem (blocos 1, 5, 8, 9, 10) podem ser repetidos sem restaurar.

---

## Bloco 1 — Login, escolha de unidade e Visão Global

**Cobertura automatizada:** `tests/test_security_regressions.py::test_local_login_succeeds_with_audited_turma_model`,
`tests/test_dashboard.py::test_dashboard_filtra_periodos_ativos_pela_unidade_selecionada`,
`tests/test_isolamento_unidade_escrita.py::test_admin_sem_unidade_nao_edita_turma`.
**Lacuna (cobertura nova):** navegação pelo dropdown, mensagem visual da Visão Global, redirect de
`/painel` por perfil.

| ID | Perfil / unidade | URL | Passos | Resultado esperado | Marcar |
|---|---|---|---|---|---|
| B1-01 | admin / — | `{BASE}/login` | 1. Informar `admin.m1@roteiro.local` e `[senha definida pelo seed / ROTEIRO_SENHA]` 2. Clicar em **ACESSAR SISTEMA** | Redireciona para `/painel`. O admin da semente **não tem unidade**, então entra em **Visão Global** e os cards somam o banco inteiro (no scratch de referência: Períodos Ativos 5, Turmas ativas 7, Alunos ativos 1164 — inclui dados preexistentes do banco de ensaio) | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B1-02 | admin / — | `{BASE}/login` | 1. Senha errada 2. Enviar | Permanece no login com a mensagem **Credenciais recusadas pelo domínio e banco de dados.** A tentativa entra na auditoria (Aviso de Invasão/Falha) e conta para o rate limit | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B1-03 | admin / — | `{BASE}/painel` | 1. No menu lateral, seção **Unidade**, abrir o dropdown 2. Escolher **[ROTEIRO] Unidade Central** 3. Voltar ao **Painel Geral** | Badge do topo passa a mostrar `[ROTEIRO] Unidade Central`; os cards passam a refletir só a unidade: **Períodos Ativos 2**, **Turmas ativas 3**, **Alunos ativos 9**, **Professores 1** | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B1-04 | admin / Unidade Central | `{BASE}/turma` | 1. Conferir a listagem 2. Clicar em **Imprimir** e **Lixeira** | As 3 turmas do cenário aparecem (A, B, C) e a **Turma D** não aparece (está na lixeira). **Imprimir** e **Lixeira** abrem sem 500 | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B1-05 | admin / Visão Global | `{BASE}/trocar-unidade/0` | 1. Escolher **Visão Global** 2. Abrir `/turma` 3. Clicar no ícone de **editar** de uma turma | A listagem responde 200 e mostra as turmas de **todas** as unidades (A, B, C e a **Turma Vizinha**); ao abrir detalhe/ofertas/editar/pauta o sistema responde **403** (exige unidade escolhida). Para editar, escolha uma unidade | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B1-06 | admin / Unidade Vizinha | `{BASE}/trocar-unidade/14` | 1. Trocar para **[ROTEIRO] Unidade Vizinha** 2. Abrir `/turma` 3. Abrir `/alunos` | Só aparece a **[ROTEIRO] Turma Vizinha - Oferta Unica** e o **Aluno Vizinha**; nenhuma turma/aluno da Unidade Central | ☐ OK ☐ Falhou ☐ Obs. ___ |

---

## Bloco 2 — CSRF real (token obrigatório)

A suíte roda com CSRF desligado; **este bloco é cobertura nova** exceto B2-02.
Para testar "sem token": abra o formulário, use o DevTools → *Network* → **Copy as cURL**, apague o
campo `csrf_token` e reenvie (ou altere o HTML removendo o `input`).

**Cobertura automatizada:** `tests/test_conselho_ui.py::test_fechamento_exige_csrf_e_aceita_com_token`
(único POST com CSRF exercitado pela suíte).
**Lacuna:** todos os demais formulários abaixo.

| ID | Perfil / unidade | URL | Passos | Resultado esperado | Marcar |
|---|---|---|---|---|---|
| B2-01 | admin / Central | `{BASE}/conselho/lancamento?turma=31&etapa=INICIAL&oferta_sel=45` | 1. Alterar a resposta de **Carla B1** 2. **Salvar Tudo** 3. Repetir sem o `csrf_token` | Com token: salva e volta ao painel com mensagem de sucesso. Sem token: **400 Bad Request** (*The CSRF token is missing*) e **nada** gravado | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B2-02 | admin / Central | `{BASE}/conselho` | 1. No card da Turma B/Informática clicar em **Encerrar conselho da oferta** 2. Repetir sem token | Com token: badge muda para **Concluído**. Sem token: **400** e o badge continua **Pendente** | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B2-03 | admin / Central | `{BASE}/frequencia?turma_id=30&data=2026-08-03` | 1. Marcar **J** para **Bruno A2** 2. **Salvar** 3. Repetir sem token | Com token: grava J e as **Estatísticas Rápidas** mudam. Sem token: **400**, sem gravação | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B2-04 | admin / Central | `{BASE}/turma` | 1. Na Turma C clicar na lixeira (**Excluir**) 2. Confirmar 3. Repetir sem token **[restaurar]** — a Turma C sai do cenário | Com token: turma sai da listagem (vai para a lixeira). Sem token: **400** e a turma permanece | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B2-05 | admin / Central | `{BASE}/turmas/lixeira` | 1. Marcar **Confirmar período encerrado** 2. **Reativar** 3. Repetir sem token | Com token: turma reativada. Sem token: **400**, turma continua na lixeira | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B2-06 | admin / Central | `{BASE}/turma/31/ofertas` | 1. No curso **Horta** clicar em **Remover curso da turma** (ícone) 2. Confirmar 3. Repetir sem token **[restaurar]** | Com token: oferta fica **Inativo**. Sem token: **400**, oferta continua ativa | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B2-07 | admin / Central | `{BASE}/alunos` | 1. Localizar **Heitor Desent** 2. Excluir pelo ícone de ação 3. Repetir sem token | Com token: exclusão/inativação processada. Sem token: **400**, aluno intacto | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B2-08 | admin / Central | `{BASE}/turma/30` | 1. Selecionar **Heitor Desent** em **Enturmar Alunos** 2. **ENTURMAR SELECIONADOS** 3. Repetir sem token | Com token: aluno enturmado. Sem token: **400**, nada muda | ☐ OK ☐ Falhou ☐ Obs. ___ |

> Verificado na P4 por HTTP: as 8 rotas acima respondem **400 sem token** e a validação de
> token aceita requisições legítimas (302/200) quando o token é enviado.

---

## Bloco 3 — Agenda por dia (H4c/H4d)

**Cobertura automatizada:** `tests/test_ui_grade_por_dia.py` (render do interruptor, modo
personalizado, erro de domingo/horário), `tests/test_definir_grade.py` (validação do serviço),
`tests/test_grade_horario_js.py` (**JS** por `node`: conversão de dia, C.H., espelhamento do padrão),
`tests/test_carga_horaria_oferta_variavel.py` (C.H. por dia),
`tests/test_impressao_grade_oferta.py::TestTextoGradeNaoUniforme`.
**Lacuna:** interação real no navegador (o teste de JS não abre a página).

| ID | Perfil / unidade | URL | Passos | Resultado esperado | Marcar |
|---|---|---|---|---|---|
| B3-01 | admin / Central | `{BASE}/turma/editar/32` | 1. Abrir a Turma C 2. Observar **Dias da semana** e o interruptor **Horário por dia** | Dias **Segunda**, **Quarta** e **Sexta** marcados (sem **Domingo** na lista); interruptor **ligado**; linhas Segunda 08:00–10:00, Quarta 08:00–11:00, Sexta 14:00–15:30; **C.H. Total** = **141h30min** | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B3-02 | admin / Central | `{BASE}/turma/32/ofertas` | 1. Observar a coluna **Dias / Horários** da oferta 2. Clicar no lápis (**Editar oferta**) | Texto com os três pares por dia e selo **varia**; o formulário abre já em modo personalizado | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B3-03 | admin / Central | `{BASE}/turma/32/ofertas` | 1. Em **Adicionar curso à turma** escolher curso, **Programa** 2. Marcar **Segunda** e **Quarta** 3. Ligar **Horário por dia** 4. Seg 08:00–10:00 e Qua 08:00–11:00 5. **Salvar curso** **[restaurar]** — a C.H. da Turma C muda | Oferta criada; sub-linha/lista mostra **varia** e os dois pares; **C.H. por Aula** mostra `varia` e a **C.H. Total** soma as durações por dia | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B3-04 | admin / Central | `{BASE}/turma/32/ofertas` | 1. Marcar os seis dias (Seg a Sáb) 2. Mesmo horário 08:00–09:00 3. Salvar **[restaurar]** | Grava 6 dias; **não existe checkbox de domingo**; a listagem exibe `Seg. Ter. Qua. Qui. Sex. Sáb.` | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B3-05 | admin / Central | `{BASE}/turma/32/ofertas` | 1. Ligar **Horário por dia** 2. Na **Quarta** colocar início 10:00 e fim 08:00 3. Salvar | Erro na tela: **Horário inválido no dia Quarta: hora_fim (08:00) deve ser maior que hora_inicio (10:00).** Nada é gravado e o formulário volta preenchido | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B3-06 | admin / Central | `{BASE}/turma/32/ofertas` | 1. Marcar **Terça** e deixar as horas vazias 2. Salvar | Erro: **Falta horário no dia Terça: toda aula precisa de hora de início e de término.** | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B3-07 | admin / Central | `{BASE}/turma/32/ofertas` | 1. Desmarcar todos os dias 2. Salvar | Erro: **A grade não pode ficar vazia: selecione ao menos um dia de aula.** | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B3-08 | admin / Central | `{BASE}/turma/32/ofertas` | 1. Marcar 2 dias e preencher o par padrão **Mesmo horário para os dias marcados** 2. Ligar **Horário por dia** 3. Voltar ao modo padrão | Com o interruptor desligado, os dias exibem **igual ao padrão** e o par padrão vale para todos; com 1 dia o interruptor fica **desabilitado** com o texto *Marque 2 ou mais dias para definir horários diferentes.* | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B3-09 | admin / Central | `{BASE}/turma/32/ofertas` | 1. Antes de salvar, observar o bloco **C.H. por Aula** / **C.H. Total Estimada** ao trocar dias e horas | Os valores recalculam em tempo real (JS) e batem com o cálculo manual (ex.: 2 dias de 2h em 22 ocorrências = 88h). O aviso *(dias bloqueados não descontados aqui)* permanece | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B3-10 | admin / Central | `{BASE}/turma/editar/30` | 1. Abrir a Turma A (1 oferta uniforme) 2. Alterar o par para 08:00–11:00 3. Salvar 4. Voltar a 08:00–10:00 | A grade uniforme da oferta é atualizada e a **C.H. Total** da turma muda na listagem (88h → 132h e volta); **nenhum domingo** é oferecido | ☐ OK ☐ Falhou ☐ Obs. ___ |

---

## Bloco 4 — Frequência por oferta

**Cobertura automatizada:** `tests/test_d3b2_4_estatisticas.py` (estatísticas por oferta A×B e
legado inalterado), `tests/test_frequencia_oferta.py::test_percentuais_distintos_por_oferta_para_o_mesmo_aluno`,
`tests/test_datas_aula_oferta_grade.py` (datas por grade).
**Lacuna:** render real dos `P/F/J` no navegador e o salvamento com CSRF (B2-03).

| ID | Perfil / unidade | URL | Passos | Resultado esperado | Marcar |
|---|---|---|---|---|---|
| B4-01 | admin / Central | `{BASE}/frequencia?turma_id=31` | 1. Selecionar a **Turma B** 2. Não escolher curso | Aparece o bloco **Curso da oferta** com a mensagem **Selecione o curso para carregar a pauta.** Nenhum aluno é listado | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B4-02 | admin / Central | `{BASE}/frequencia?turma_id=31&turma_curso=45&data=2026-08-03` | 1. Escolher a oferta **Informática** e a data **03/08/2026** | **Carla B1**: `P: 66.7% F: 33.3% J: 0 (3 aulas)` · **Diego B2**: `P: 50.0% F: 50.0% J: 0 (2 aulas)`; botões A B C D F J com o conceito do dia marcado | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B4-03 | admin / Central | `{BASE}/frequencia?turma_id=31&turma_curso=46&data=2026-08-04` | 1. Trocar para a oferta **Horta** (data 04/08/2026) | **Carla B1**: `P: 0.0% F: 100.0% (2 aulas)` · **Diego B2**: `P: 100.0% F: 0.0% (1 aulas)` — os números **mudam ao trocar de oferta** (D3b-2.4) | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B4-04 | admin / Central | `{BASE}/frequencia?turma_id=30&data=2026-08-03` | 1. Abrir a Turma A (oferta única, legado NULL) | Sem seletor de curso (oferta resolvida automaticamente); **Ana A1** `P: 100.0% (2 aulas)` e **Bruno A2** `P: 50.0% (2 aulas)` — legado **inalterado** e incluído | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B4-05 | admin / Central | `{BASE}/frequencia?turma_id=30&data=2026-08-03` | 1. Marcar **J** para **Bruno A2** 2. **Salvar** 3. Recarregar | O J aparece selecionado ao recarregar; as estatísticas recalculam (J sai do denominador e aparece em **J:**); o **Diário da turma** registra a observação/tema da aula | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B4-06 | admin / Central | `{BASE}/frequencia?turma_id=32&data=2026-08-05` | 1. Abrir a Turma C em 05/08/2026 | **Elisa C1** `P: 100.0% (2 aulas)` (A e B) e **Fabio C2** `P: 0.0% F: 100.0% (1 aulas)` com **1 J** contabilizada à parte | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B4-07 | admin / Central | `{BASE}/frequencia?turma_id=31&turma_curso=45&data=2026-08-03` | 1. Trocar a **Data da Aula** para 10/08 mantendo a oferta | A URL preserva `turma_curso=45`; os alunos e as estatísticas continuam os da oferta Informática; nenhum 500 com data fora da grade | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B4-08 | professor / Central | `{BASE}/frequencia?turma_id=31&turma_curso=45&data=2026-08-03` | 1. Entrar como `professor.m1@roteiro.local` 2. Abrir a frequência da Turma B | Tela 200; `Salvar` disponível (não é modo visualização). A **Turma Vizinha** não aparece na lista de turmas do professor | ☐ OK ☐ Falhou ☐ Obs. ___ |

---

## Bloco 5 — Listagem de turmas (freq = soma, sub-linha, `min_freq`)

**Cobertura automatizada:** `tests/test_d3b2_2_listagem_caracterizacao.py`,
`tests/test_d3b2_5_min_freq.py` (soma × principal), `tests/test_turma_curso_lista.py`
(selo/sublinha/filtros), `tests/test_filtros_turmas.py`, `tests/test_d3b2_2_n1_freq_geral.py`
(sem N+1).
**Lacuna:** valor na tela e sensação de desempenho no navegador.

| ID | Perfil / unidade | URL | Passos | Resultado esperado | Marcar |
|---|---|---|---|---|---|
| B5-01 | admin / Central | `{BASE}/turma` | 1. Localizar a Turma A | Badge de alunos **2**, frequência **75.0%** (verde), dias **Seg. Qua.**, horário **08:00 - 10:00**, **C.H. Total 88h** | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B5-02 | admin / Central | `{BASE}/turma` | 1. Na Turma B, clicar no botão de expandir (**chevron**) | Selo **2 cursos**; linha da turma: **50.0%** (amarelo) e **C.H. Total 176h**; sub-linha com **Informática** (principal, **Segunda, Quarta**, 2h, 88h, **60.0%**) e **Horta** (**Terça, Quinta**, 2h, 88h, **33.3%**) | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B5-03 | admin / Central | `{BASE}/turma` | 1. Localizar a Turma C | Frequência **66.7%**; dias **Seg. Qua. Sex.**; horário **Segunda 08:00–10:00; Quarta 08:00–11:00; Sexta 14:00–15:30**; **C.H. Total 141h30min** | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B5-04 | admin / Central | `{BASE}/turma?min_freq=70` | 1. Abrir **Filtros de Busca** 2. Preencher **Freq. Mínima (%)** = 70 3. **Filtrar** | Só a **Turma A** (75.0%) aparece — a comparação usa a **soma da turma**, não a principal (D3b-2.5) | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B5-05 | admin / Central | `{BASE}/turma?min_freq=60` | 1. Repetir com 60 | Aparecem **A** (75.0%) e **C** (66.7%); a **B** (50.0%) fica de fora | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B5-06 | admin / Central | `{BASE}/turma?min_freq=76` | 1. Repetir com 76 | Nenhuma linha: **Nenhuma turma encontrada com os filtros aplicados.** | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B5-07 | admin / Central | `{BASE}/turma?programa=Esporte` | 1. Filtrar **Programa** = Esporte 2. Repetir com **Meio Ambiente** | Esporte: só a **Turma A**. Meio Ambiente: **nenhuma** — o filtro usa a projeção `Turma.programa` (a B projeta *Profissionalizante*, da principal), **observação de usabilidade**, não erro | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B5-08 | admin / Central | `{BASE}/turma?dia=Terça` | 1. Filtrar **Dia da Semana** = Terça 2. Repetir com **Turno** = Tarde | Dia Terça: só a **Turma B** (a Horta tem aula na terça). Turno Tarde: só a **Turma B** | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B5-09 | admin / Central | `{BASE}/turma` | 1. Cronometrar o carregamento com as 8 turmas do banco 2. Rolar a tabela e expandir a Turma B | Resposta perceptivelmente rápida (sem espera visível); expandir/recolher não recarrega a página; **não há paginação** nesta tela (ordem por `#ordenação` e nome) | ☐ OK ☐ Falhou ☐ Obs. ___ |

---

## Bloco 6 — Conselho de Classe (PQ1–PQ4)

**Cobertura automatizada:** `tests/test_conselho_ui.py` (CSRF do fechamento, grid aluno×pergunta,
enum de situação, impressão), `tests/test_conselho_oferta.py` (escolha de oferta, gravação por
oferta, fechamento), `tests/test_d5_encerramento.py` (status derivado, certificado),
`tests/test_d5_leitores.py`, `tests/test_d5_schema.py`.
**Lacuna:** interação na tela (numeração, edição inline, impressão no navegador).

| ID | Perfil / unidade | URL | Passos | Resultado esperado | Marcar |
|---|---|---|---|---|---|
| B6-01 | admin / Central | `{BASE}/conselho` | 1. Abrir o painel 2. Observar os cards | Um card por **oferta ativa de turma ativa** (A, B/Informática, B/Horta, C); **B/Informática** com badge **Concluído**, as demais **Pendente**; rodapé **Mostrando 4 ofertas ativas** | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B6-02 | admin / Central | `{BASE}/conselho/lancamento?turma=31&etapa=INICIAL&oferta_sel=45` | 1. Abrir o lançamento da oferta Informática | Perguntas **numeradas** e individuais: **1. [ROTEIRO] Frequencia do aluno no inicio** (botões **A) Suficiente**, **B) Insuficiente**) e **2. [ROTEIRO] Socializacao com o grupo** (**Boa**, **Regular**, **Dificuldade**); um card por aluno (Carla, Diego) **[restaurar após o bloco 6]** | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B6-03 | admin / Central | `{BASE}/conselho/lancamento?turma=31&etapa=INICIAL&oferta_sel=45` | 1. Alterar as respostas de **Carla B1** 2. **Salvar Tudo** 3. Reabrir | Respostas persistidas por aluno; a edição não duplica linhas (uma resposta por pergunta/aluno/oferta) | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B6-04 | admin / Central | `{BASE}/turma/31/avaliacao?oferta_sel=45` | 1. Abrir **Ver Avaliação da Oferta** 2. Conferir a tabela de perguntas coletivas 3. Alterar e **Gravar Avaliação da Oferta** | Título **Avaliação Coletiva da Oferta** com as perguntas TURMA numeradas (1. Como esta o grupo…; 2. Participacao coletiva…) e respostas salvas; gravação reflete no card/`avaliacao_*` da oferta | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B6-05 | admin / Central | `{BASE}/conselho` | 1. Clicar em **Imprimir formulário** 2. Escolher etapa **INICIAL** e quantidade **2** 3. **Preparar impressão** | Abre `/conselho/imprimir?etapa=INICIAL&quantidade=2` com **Conselho de Classe — [ROTEIRO] Unidade Central**, bloco **Avaliação geral da turma** e **Avaliação individual dos alunos** repetida para 2 alunos | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B6-06 | admin / Central | `{BASE}/conselho/lancamento?turma=31&etapa=INICIAL` | 1. Abrir sem escolher oferta | Card azul da turma + aviso **Esta turma tem mais de um curso ativo. Selecione o curso (oferta) acima para abrir o lançamento do conselho daquela oferta.** Nenhum aluno listado | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B6-07 | admin / Central | `{BASE}/conselho/fechamento/31?oferta_sel=45` | 1. Abrir a **Situação Final do Aluno** 2. Conferir a tabela | Cabeçalho com turma/programa/professor/dias; colunas **Conceitos (%)** (A/B/C/D/F/J), **Presença**, **Falta**; selects **Situação Final** (Aprovado, Reprovado por Falta, Desistente, Evadido, Participação, Concluído) e **Próxima Turma**; rodapé de auditoria só na impressão | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B6-08 | admin / Central | `{BASE}/conselho/fechamento/31?oferta_sel=45` | 1. Escolher situação **Aprovado** e **Próxima Turma** para Carla 2. **Salvar Fechamento** 3. Recarregar | A escolha persiste na oferta; a linha continua com os percentuais calculados pela oferta (não mistura a Horta) | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B6-09 | admin / Central | `{BASE}/conselho` | 1. Na oferta **Horta** (Pendente) clicar em **Encerrar conselho da oferta** 2. Clicar de novo em **Reabrir conselho da oferta** | O status alterna **Pendente ↔ Concluído** apenas na oferta clicada; a outra oferta da mesma turma não muda; o card/turma deriva o status das ofertas | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B6-10 | admin / Central | `{BASE}/conselho/perguntas` | 1. **Nova Pergunta** 2. Etapa **PERCURSO**, foco **Individual (Aluno)**, texto e opções 3. **Adicionar** 4. Abrir o lançamento de PERCURSO | A pergunta aparece na lista e no lançamento da etapa PERCURSO; é possível editar e excluir | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B6-11 | admin / Central | `{BASE}/conselho` | 1. Encerrar a oferta **Horta** 2. Abrir `/relatorios/` | **Ofertas Avaliadas** passa de **25.0% (1 de 4)** para **50.0% (2 de 4)** — contagem por oferta, coerente com o painel | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B6-12 | admin / Central | `{BASE}/conselho/fechamento/31` | 1. Abrir o fechamento sem `oferta_sel` | Card **Selecione o curso (oferta)** com o select das ofertas; nenhuma tabela de alunos é exibida enquanto não escolher | ☐ OK ☐ Falhou ☐ Obs. ___ |

---

## Bloco 7 — Lixeira e reativação (L4 / L4.1 / L4.2)

**Cobertura automatizada:** `tests/test_l4_lixeira.py` (permissões, visão global, período encerrado,
idempotência), `tests/test_l4_1_reativacao_ofertas.py::test_p2_oferta_desativada_antes_da_exclusao_nao_reativada`,
`tests/test_l4_1_reativacao_ofertas.py::test_p4_inscricao_transferencia_e_desenturmada_nao_reativadas`,
`tests/test_l4_1_reativacao_ofertas.py::test_p4_perfis_da_lixeira_e_da_reativacao`,
`tests/test_l4_2_programa_reativacao.py` (programa após reativar).
**Lacuna:** ciclo completo no navegador (checkbox, confirmação, reabertura).

> Para **restaurar** o cenário depois de reativar a Turma D, rode novamente a semente: ela
> reaplica a exclusão lógica e o marcador (idempotente para o restante). **[restaurar]** ao final do bloco.

| ID | Perfil / unidade | URL | Passos | Resultado esperado | Marcar |
|---|---|---|---|---|---|
| B7-01 | admin / Central | `{BASE}/turmas/lixeira` | 1. Abrir a lixeira 2. Conferir os cursos da **Turma D** | **Informática** com badge **desativado na exclusão da turma** e **marcado**; **Horta** com badge **desativado antes / origem desconhecida** e **desmarcado**; texto **1 de 2 curso(s) a reativar**; alerta de que curso removido antes continua inativo | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B7-02 | admin / Central | `{BASE}/turmas/lixeira` | 1. Deixar **Confirmar período encerrado** desmarcado 2. **Reativar** | A reativação é recusada (período encerrado exige confirmação) e a turma continua na lixeira | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B7-03 | admin / Central | `{BASE}/turmas/lixeira` | 1. **Desmarcar** o único curso marcado (**Informática**) 2. **Reativar** | Recusa: sem curso selecionado não há reativação (mensagem pedindo escolha explícita) e a turma continua na lixeira | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B7-04 | admin / Central | `{BASE}/turmas/lixeira` | 1. **Marcar apenas Horta** 2. Marcar **Confirmar período encerrado** 3. **Reativar** | Turma sai da lixeira; **Horta** fica ativa; **Informática continua inativa** (não estava no marcador); **Turma.programa passa a "Meio Ambiente"** (L4.2 — projeção da oferta ativa) | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B7-05 | admin / Central | `{BASE}/turma?periodo_letivo_id=23` | 1. (após B7-04) Abrir a listagem do período encerrado | A **Turma D** aparece com a sub-linha mostrando a Horta ativa e a Informática **Inativo** | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B7-06 | admin / Central | `{BASE}/turmas/lixeira` | 1. Rodar a semente novamente 2. Voltar à lixeira 3. Reativar **ambos** os cursos com **Confirmar período encerrado** | As duas ofertas voltam; o programa da turma é o da **principal** (Profissionalizante); a turma não duplica o marcador de exclusão | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B7-07 | admin / Central | `{BASE}/alunos` | 1. Após reativar a turma, abrir **Gerenciar Alunos** 2. Conferir **Inacia D-ativa** e **Joao D-inativo** | **Joao D-inativo** continua **inativo** (a inscrição `DESENTURMADO` não é reativada); **Inacia D-ativa** permanece ativa; nenhuma inscrição em conflito volta silenciosamente | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B7-08 | admin / Central | `{BASE}/turmas/lixeira` | 1. Reativar a mesma turma duas vezes seguidas | A segunda tentativa não duplica ofertas, inscrições nem o marcador (idempotente) | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B7-09 | admin / Central | `{BASE}/admin/logs` | 1. Após reativar, abrir a auditoria | Há registro da reativação com o usuário e a IP da sessão (e o log anterior da exclusão lógica) | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B7-10 | admin / Visão Global | `{BASE}/turmas/lixeira` | 1. Trocar para **Visão Global** 2. Abrir a lixeira | Alerta **Visão Global: somente leitura. Selecione uma unidade para reativar turmas.**, sem botão **Reativar** (texto **Somente leitura**) | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B7-11 | gerência / Central | `{BASE}/turmas/lixeira` | 1. Entrar como `gerencia.m1@roteiro.local` 2. Abrir a lixeira | **403** (o perfil de gerência não tem acesso à lixeira/reativação) | ☐ OK ☐ Falhou ☐ Obs. ___ |

---

## Bloco 8 — Histórico, ficha 360°, certificado, relatório geral e BI

Valores esperados **calculados a partir da semente** (ver §0.5). A P4 comparou cada um com o HTML
do app; divergência encontrada está marcada como **achado**.

**Cobertura automatizada:** `tests/test_d3b2_3_n1_historico.py`,
`tests/test_d5_leitores.py::test_historico_uma_linha_por_inscricao_com_status_da_oferta`,
`tests/test_frequencia_oferta.py::test_ficha_pct_turma_usa_acumulado_da_oferta`,
`tests/test_d3b2_6_fprog.py` e `tests/test_d3b2_7_fprog_d2.py` (`f_prog`),
`tests/test_bi_indicadores.py`, `tests/test_bi_oferta.py`, `tests/test_bi_turma_desativada.py`,
`tests/test_dashboard_professor_pedagogico.py`, `tests/test_painel_periodo.py`.
**Lacuna:** leitura visual dos números (a suíte valida os serviços, não o HTML final).

| ID | Perfil / unidade | URL | Passos | Resultado esperado | Marcar |
|---|---|---|---|---|---|
| B8-01 | admin / Central | `{BASE}/aluno/1482/historico` | 1. Abrir o histórico de **Ana A1** | Ana aparece na Turma A com **0 aulas / 0 presenças / 0.0%**, embora a listagem mostre 75.0% e a pauta inclua as aulas legadas — **achado (legado NULL sem backfill)**. A coluna Situação mostra `I: None · P: —` — **achado de exibição** (None em vez de traço) | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B8-02 | admin / Central | `{BASE}/aluno/1486/historico` | 1. Abrir o histórico de **Elisa C1** | Turma C com **2 aulas**, **2 presenças**, **100.0%**; dias/horário por dia da oferta; **sem** misturar a Turma A | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B8-03 | admin / Central | `{BASE}/aluno/1488/historico` | 1. Abrir o histórico de **Gabriela Transf** | Duas linhas: Turma A marcada **Desligado** (transferência) e Turma C ativa — o histórico preserva a origem | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B8-04 | admin / Central | `{BASE}/relatorios/alunos/1486/ficha` | 1. Abrir a **Ficha 360°** de Elisa | **Frequência 100.0%**, **2 presenças em 2 aulas contábeis**, **Média da turma 66.7%**, **+33 pp**, **Faltas 0**, semana a semana com A/B/J/F na legenda | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B8-05 | admin / Central | `{BASE}/relatorios/alunos/1484/ficha` | 1. Abrir a ficha de **Carla B1** 2. Alternar o seletor de oferta | Carla tem **duas** inscrições na Turma B; o seletor de oferta aparece e a ficha da **Informática** mostra 66.7% (3 aulas) e a da **Horta** 0.0% (2 aulas), sem misturar conselhos | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B8-06 | admin / Central | `{BASE}/periodo-letivo/relatorio/22` | 1. Abrir **Certificados** do período vigente | Ana/Bruno **88h**; Carla e Diego **duas linhas** (Informática 88h e Horta 88h); Elisa/Fabio **141h30min**; coluna **Conselho: Pendente** (não há conselho final) | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B8-07 | admin / Central | `{BASE}/periodo-letivo/relatorio/22` | 1. Clicar em **Emitir** de Elisa | Abre a impressão do **CERTIFICADO DE CONCLUSÃO** apenas para a aluna escolhida, com a unidade e a data de emissão; fechar não altera dados | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B8-08 | admin / Central | `{BASE}/relatorios/` | 1. Conferir **Comunidade Ativa** 2. **Ofertas Avaliadas** 3. **Frequência por Programa** 4. **Frequência por Turma** 5. **Desempenho por Professor** | **9 ALUNOS · 1 PROFS · 3 TURMAS**; **Ofertas Avaliadas 25.0% (1 de 4)**; Programa: **Esporte 75.0%**, **Meio Ambiente 33.3%**, **Profissionalizante 62.5%**; Turma: **A 75.0%**, **B 50.0%**, **C 66.7%**; Professor **60.0%** | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B8-09 | admin / Central | `{BASE}/relatorios/bi/indicador/FRE-005?unidade_id=13` | 1. Executar o indicador **Frequência média** | Retorna **64.7** — **achado**: o BI soma também a frequência da **Turma D (inativa)** (11P/6F); o Resumo/§0.5 usa só turmas ativas (**60.0**, 9P/6F). Registre como divergência, não corrija | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B8-10 | admin / Central | `{BASE}/relatorios/bi/indicador/FRE-009?unidade_id=13` | 1. Executar **Frequência por turma** | **A 75.0**, **B 50.0**, **C 66.7** — a Turma D **não** é listada aqui (inconsistente com B8-09, mesmo achado) | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B8-11 | admin / Central | `{BASE}/relatorios/bi/indicador/FRE-010?unidade_id=13` | 1. Executar **Frequência por curso** | **Horta 33.3**, **Informática 62.5** (soma B1+C: 5P/3F), **Natação 75.0** | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B8-12 | admin / Central | `{BASE}/relatorios/painel` | 1. Abrir o **Painel pedagógico** com o período **Vigente** | **Frequência do período 60.0%**; faixas **≥ 90%: 2 · 75–89%: 0 · < 75%: 4**; desativações **2 (DESENTURMADO 1, TRANSFERENCIA 1)**; sinais: **2 turmas abaixo de 75%** (B 50.0 e C 66.7). **Achado:** o bloco **Alunos enturmados** mostra **6** e logo abaixo **7 novos** (dois números para o mesmo conceito) | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B8-13 | admin / Central | `{BASE}/relatorios/painel?periodo_letivo_id=23` | 1. Trocar o **Período** do painel pedagógico para **[ROTEIRO] Periodo Encerrado** | Painel abre 200 com **Frequência do período 0.0%**, faixas todas em 0 e **Nenhum sinal de atenção detectado no período** (a Turma D está inativa e não entra); sem 500 e sem dados do período vigente | ☐ OK ☐ Falhou ☐ Obs. ___ |

---

## Bloco 9 — Permissões por perfil (matriz)

Matriz medida na P4 por HTTP, **sem seguir redirect** (código real), com a unidade
**[ROTEIRO] Unidade Central** selecionada. `302` = redirecionamento por perfil; `403` = negado.

| Rota (URL) | admin | gerência | pedagógico | secretaria | professor |
|---|---|---|---|---|---|
| `/painel` | 200 | 200 | 200 | 302 → `/painel/secretaria` | 200 |
| `/turma` (listagem) | 200 | 200 | 200 | 200 | 200 |
| `/turma/30` (detalhe) | 200 | 200 | 200 | 200 | 200 |
| `/turma/31/ofertas` | 200 | 200 | 200 | 200 | **403** |
| `/turma/editar/32` | 200 | **403** | 200 | 200 | **403** |
| `/turma/nova` | 200 | 200 | 200 | 200 | **403** |
| `/turmas/lixeira` | 200 | **403** | 200 | 200 | **403** |
| `/turma/30/imprimir-pauta` | 200 | **403** | 200 | 200 | 200 |
| `/turmas/carga-horaria` | 200 | 200 | 200 | 200 | **403** |
| `/frequencia?turma_id=30` | 200 | **403** | 200 | 200 | 200 |
| `/frequencia_relatorio` | **403** | **403** | 200 | **403** | **403** |
| `/conselho` | 200 | 200 | 200 | 200 | 200 |
| `/conselho/perguntas` | 200 | 200 | 200 | **403** | **403** |
| `/conselho/lancamento?turma=31&etapa=INICIAL&oferta_sel=45` | 200 | 200 | 200 | 200 | 200 |
| `/conselho/fechamento/31?oferta_sel=45` | 200 | 200 | 200 | 200 | 200 |
| `/conselho/imprimir?etapa=INICIAL&quantidade=2` | 200 | 200 | 200 | **403** | **403** |
| `/alunos` | 200 | 200 | 200 | 200 | **403** |
| `/aluno/1482/historico` | 200 | 200 | 200 | 200 | 200 |
| `/periodo-letivo` | 200 | 200 | 200 | 200 | **403** |
| `/periodo-letivo/relatorio/22` | 200 | **403** | 200 | 200 | **403** |
| `/centros-custo` | 200 | 200 | 200 | 200 | **403** |
| `/cursos` | 200 | **403** | 200 | 200 | **403** |
| `/relatorios/` | 200 | 200 | 200 | 200 | **403** |
| `/relatorios/alunos` | 200 | 200 | 200 | 200 | **403** |
| `/relatorios/bi` | 200 | 200 | 200 | 200 | **403** |
| `/relatorios/painel` | 200 | 200 | 200 | 200 | **403** |
| `/relatorios/alunos/1486/ficha` | 200 | 200 | 200 | 200 | **403** |
| `/relatorios/conselho` | 200 | 200 | 200 | 200 | **403** |
| `/admin/painel` | 200 | 302 | 302 | 302 | 302 |
| `/admin/unidades` | 200 | **403** | **403** | **403** | **403** |
| `/admin/logs` | 200 | **403** | **403** | **403** | **403** |
| `/professor/painel` | 200 | 302 | 200 | 200 | 200 |
| `/professor/painel-pedagogico` | 200 | 200 | 200 | **403** | 200 |
| `/painel/secretaria` | 200 | 200 | 200 | 200 | **403** |

**admin sem unidade (Visão Global):** `/turma` 200, `/turmas/lixeira` 200, `/frequencia` 200, mas
`/turma/30`, `/turma/31/ofertas`, `/turma/editar/32` e `/turma/30/imprimir-pauta` **403**.

**Cobertura automatizada:** `tests/test_l4_1_reativacao_ofertas.py::test_p4_perfis_da_lixeira_e_da_reativacao`,
`tests/test_conselho_oferta.py::test_isolamento_lancamento_outra_unidade_403`,
`tests/test_conselho_ui.py::test_impressao_conselho_exige_perfil_autorizado`,
`tests/test_security_regressions.py` (rotas mutantes × GET, histórico de professor alheio),
`tests/test_isolamento_unidade_escrita.py` (matriz de escrita por unidade).
**Lacuna:** a matriz GET completa e o comportamento de `/relatorios/*` por perfil.

| ID | Perfil / unidade | URL | Passos | Resultado esperado | Marcar |
|---|---|---|---|---|---|
| B9-01 | os 5 perfis | matriz acima | 1. Entrar com cada usuário 2. Escolher a Unidade Central 3. Abrir as rotas da matriz | Os códigos batem com a tabela; `403` mostra a página de erro (sem dados) e `302` leva ao painel do perfil | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B9-02 | admin / Visão Global | `{BASE}/turma/30` | 1. Sem unidade, abrir detalhe/ofertas/editar/pauta | **403** com mensagem de contexto de unidade; a listagem continua 200 | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B9-03 | professor / Central | `{BASE}/turma` | 1. Abrir a listagem como professor 2. Clicar nos ícones de visualizar/editar | Vê a listagem e o detalhe; **Editar** e **Lixeira** respondem 403 e não há botões de escrita (nem **Nova Turma**) | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B9-04 | gerência / Central | `{BASE}/turma/editar/32` | 1. Tentar editar a Turma C 2. Tentar a pauta | **403** nas duas; a listagem é acessível. O perfil de gerência é leitura/gestão de unidade, sem edição de turma | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B9-05 | secretaria / Central | `{BASE}/conselho/perguntas` | 1. Abrir perguntas e impressão do conselho | **403**; o lançamento/fechamento continuam 200. Em `/frequencia` a secretaria entra em **Modo visualização — sem permissão para lançar frequência** | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B9-06 | professor / Central | `{BASE}/turma/30/imprimir-pauta` | 1. Abrir a pauta da Turma A (turma do professor do cenário) | 200 e a pauta lista **somente** os alunos da turma associada; outra turma de outro professor responde 403 | ☐ OK ☐ Falhou ☐ Obs. ___ |

---

## Bloco 10 — Impressões e exportações

**Cobertura automatizada:** `tests/test_pauta_professor.py` (escopo da pauta),
`tests/test_impressao_grade_oferta.py` (texto da grade na listagem/detalhe/impressão),
`tests/test_conselho_ui.py::test_impressao_conselho_configura_etapa_e_quantidade`,
`tests/test_bi_indicadores.py` (JSON dos indicadores; o XLSX não é lido pela suíte),
`tests/test_turma_curso_lista.py` (C.H. total exibida).
**Lacuna:** geração real dos arquivos (Excel/PDF/CSV), paginação da impressão e isolamento por unidade.

| ID | Perfil / unidade | URL | Passos | Resultado esperado | Marcar |
|---|---|---|---|---|---|
| B10-01 | admin / Central | `{BASE}/turma/30/imprimir-pauta` | 1. Abrir a **Pauta Completa** da Turma A 2. Imprimir (Ctrl+P) | Abre sem login extra; cabeçalho com unidade/período; Ana e Bruno; dias Seg/Qua; meses em sequência; **nenhum aluno da Unidade Vizinha**; a prévia não corta colunas | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B10-02 | admin / Central | `{BASE}/turma/31/imprimir-pauta?turma_curso=45` | 1. Abrir a pauta da B/Informática 2. Repetir com `turma_curso=46` | Cada pauta lista **somente** os alunos da oferta escolhida (Carla/Diego em ambas, com conceitos diferentes); nenhuma mistura de oferta | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B10-03 | admin / Central | `{BASE}/turmas/centros-custo/imprimir` | 1. Abrir **Imprimir** na listagem | Documento com **C.H. Total** por turma: A **88h**, B **176h**, C **141h30min**; o layout não quebra ao imprimir | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B10-04 | admin / Central | `{BASE}/planejamento/imprimir-temas` | 1. Abrir a impressão de temas | Lista os temas `[ROTEIRO] Tema Respiracao`, `Planilhas`, `Compostagem`; abre, pagina e não quebra | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B10-05 | admin / Central | `{BASE}/conselho/fechamento/31?oferta_sel=45` | 1. **Imprimir** 2. **Exportar .CSV** | Impressão esconde os botões (`d-print-none`), mantém a tabela e o rodapé de auditoria; o CSV baixa com as colunas de conceitos/presença/situação | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B10-06 | admin / Central | `{BASE}/relatorios/` | 1. **Imprimir** 2. **Exportar Painel** | A impressão mostra todos os blocos do Resumo; o Excel (`/relatorios/exportar`) abre com as abas **Idade por Programa**, **Idade por Turma**, **Freq por Programa**, **Freq por Professor** e **Freq por Turma**, com os valores de §0.5 | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B10-07 | admin / Central | `{BASE}/relatorios/alunos` | 1. Abrir **Exportar Alunos** 2. Exportar | A tela lista os alunos da unidade; o arquivo exportado respeita os filtros e contém apenas alunos da Unidade Central | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B10-08 | admin / Central | `{BASE}/relatorios/bi` | 1. Selecionar **FRE-010 Frequência por curso** 2. **Executar indicador** 3. **Exportar XLSX** 4. **Exportar PNG** | Gráfico/tabela com Horta 33.3, Informática 62.5, Natação 75.0; o XLSX abre com cabeçalho do indicador e 3 linhas; o PNG baixa | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B10-09 | admin / Central | `{BASE}/relatorios/painel` | 1. Abrir a ficha pelo botão **Ficha** de uma turma 2. Imprimir | Ficha 360° do aluno escolhido, sem dados de outra unidade, com o bloco de conselho da oferta correta | ☐ OK ☐ Falhou ☐ Obs. ___ |
| B10-10 | admin / Vizinha | `{BASE}/relatorios/` | 1. Trocar para **Unidade Vizinha** 2. Abrir Resumo, BI, listagem e pauta da Turma Vizinha | Somente dados da vizinha (1 aluno/1 turma); nenhuma turma, aluno ou frequência da Unidade Central aparece em tela ou impressão | ☐ OK ☐ Falhou ☐ Obs. ___ |

---

## Anexo A — Resumo de cobertura

| Bloco | Casos | Automatizado cobre | Cobertura nova (manual) |
|---|---|---|---|
| 1 Login/unidade/Visão Global | 6 | login, dashboard por unidade, escrita sem unidade | dropdown, mensagem visual, redirects por perfil |
| 2 CSRF real | 8 | apenas fechamento do conselho | os 8 formulários com token ligado |
| 3 Agenda por dia (H4c/H4d) | 10 | serviço de grade, render, JS isolado, C.H. | interação no navegador, C.H. na tela |
| 4 Frequência por oferta | 8 | estatísticas por oferta, datas por grade | render dos P/F/J e salvamento real |
| 5 Listagem e `min_freq` | 9 | soma × principal, sem N+1, filtros | valor exibido, desempenho percebido |
| 6 Conselho (PQ1–PQ4) | 12 | gravação por oferta, fechamento, impressão | numeração/edição na tela, ciclo visual |
| 7 Lixeira/reativação (L4/L4.1/L4.2) | 11 | marcador, oferta desativada antes, programa, perfis | ciclo completo com confirmação e checkbox |
| 8 Histórico/ficha/certificado/relatório/BI | 13 | serviços e indicadores | números no HTML (4 achados registrados) |
| 9 Permissões | 6 (matriz 34 rotas) | escritas por unidade, perfis da lixeira | matriz GET completa |
| 10 Impressões e exportações | 10 | texto de grade, escopo da pauta | arquivos gerados (XLSX/CSV/PDF) e paginação |
| **Total** | **93** | | |
