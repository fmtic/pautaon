# H3e — Dashboard, aluno, conselho, ficha e frequência leem a grade

**Data:** 26/10/2026 · **Branch:** `nova_feature` (sem push) · **Head Alembic:** `5730d7c594ba` (nenhuma migration nova)

## 1. Resumo

Os leitores de **exibição** de dias/horário que ainda liam as colunas escalares
projetadas passaram a ler a **grade da oferta** (`turma_curso_horario`) via o mesmo
`GradeExibicao` do H3d. Para listas por **data** (pendências do dashboard), o par de
horas exibido é o do **weekday daquela data** (`intervalo_do_dia`). Nenhum schema foi
alterado, nenhum formulário/JS foi tocado e nenhuma coluna escalar foi removida.

## 2. Passo 0 — Pré-requisitos

- `git status`: sem arquivos alheios à etapa. O diff de `sistema_indisponivel`
  (template movido para `erros/`) já havia sido commitado pelo usuário em `7779aea`.
- `flask db heads` = **`5730d7c594ba`** (única).
- Commits do H3d presentes (`435c885`, `2635502`, `52ebf9d`, `dd10b85`, `c43e43d`,
  `c182f98`).
- **Suíte com 1 deseleção, por causa externa:** `tests/test_maintenance.py::test_maintenance_blocks_non_admin_users`
  falha com `TemplateNotFound: sistema_indisponivel.html` porque `app/__init__.py`
  (em `enforce_user_access_state`, linha ~101) ainda renderiza o template na raiz,
  enquanto o commit `7779aea` o moveu para `app/templates/erros/`. Nada do H3e toca
  esse caminho; a suíte foi medida com `--deselect` nesse teste.

## 3. Commits

| Hash | Mensagem |
|------|----------|
| `35ee622` | H3e-P2: caracterizacao dos leitores de dias/horario (dashboard, aluno, ficha, conselho, frequencia, transferir) |
| `fff4fdb` | H3e-P3/P4: dashboard, aluno, ficha, conselho, frequencia, transferir, gerenciar e atendimento leem a grade — intervalo_do_dia por data, GradeExibicao em lote e fallback escalar com warning |
| `d176aa8` | H3e-P5: testes dos leitores pela grade (nao uniforme por dia, dashboard por data, multi-oferta, fallback e sem N+1) e medicao deterministica de N+1 do H3d |
| `f099f20` | H3e-P7/P8: MER (7.32a, 8.10, 10, 12.25), backlog e script de ensaio dos leitores pela grade |

## 4. Passo 1 — Leitores classificados

| Leitor | Antes | Classe | Depois |
|--------|-------|--------|--------|
| `main/dashboard_professor.py` — `_horario_oferta`/`_dias_efetivos_da_oferta` | oferta → turma (escalar) | **(b)** | `_horario_entrada`/`_dias_badges` com `GradeExibicao` em lote; ramo legado (turma sem oferta) mantém o escalar |
| `main/dashboard_professor.py` — `_aulas_pendentes` | só datas | **(b)** | cada data recebe `intervalo_do_dia(oferta, data)` (weekday da data) |
| `registros/alunos.py` — histórico (~L901-928) | `turma.dias_semana`/`turma.hora_*` | **(b)** | grade da oferta (`grade.texto_horario`, `grade.dias_texto`) |
| `registros/alunos.py` — `gerenciar`/`transferir` | escalar | **(b)** | `_grade_por_aluno` (lote) e `grade_origem` |
| `registros/atendimentos.py` — atendimento pedagógico | escalar | **(b)** | `_grade_por_aluno` (lote) |
| `relatorios/painel_pedagogico/ficha_aluno.py` — `_dias_horario` | `turma.dias_semana` | **(b)** | `_dias_horario(turma, oferta)` |
| `app/conselho.py` + `conselho/painel.html`/`fechamento.html` | `turma.dias_semana/hora_*` | **(b)** | `grade_oferta_map` / `grade_oferta` |
| `registros/core.py` + `frequencia/lancar.html` (seletor) | `turma.hora_*` por oferta | **(b)** | `grade_oferta.texto_horario_curto` |
| `scripts/diagnostico_carga_horaria.py` | `turma.dias_semana` + `split(",")` | **(b)** | `dias_da_turma` (união da grade) com fallback ao CSV |
| `app/utils/logica.py` — `gerar_datas` | já deriva de `dias_da_turma` (H3a) | **(a)** | — |
| mapas de C.H. (`cargas_*_em_lote`) | H3c | **(a)** | — |
| `turmas/ofertas.html`, `nova.js`, `editar.js` | formulários | **H4** | não tocados |
| `turma.freq_geral` (listagem) | consulta por turma | **(c) fora do escopo** | dívida pré-existente da D3b-2, ver §9 |

**Nenhum leitor do caso (c)** apareceu no escopo do H3e.

## 5. Passo 3 — Serviço

Em `app/services/turma_curso_horario.py`:

- `GradeExibicao` ganhou `dias` (weekdays ordenados), `texto_horario`
  (`"08:00 às 09:30"`) e `texto_horario_curto` (`"08:00–09:30"`); `por_dia_texto`
  continua com o formato do H3d (`"Terça 08:00–10:00; Quinta 14:00–16:00"`).
- `intervalo_do_dia(oferta, data|weekday)` → `(início, fim)` do **weekday** da data,
  lendo a relação `horarios` já carregada; dia fora da grade devolve `None`; oferta
  sem grade cai no par escalar da oferta e, por último, no da turma.
- Tudo em lote: `grades_por_oferta`/`grades_para_exibicao` (relação `selectin`) e
  `dias_das_turmas_em_lote`; **nenhuma consulta por data/oferta**.

## 6. Passo 5 — Testes

- **Novo** `tests/test_leitores_grade_h3e.py`, com **22 casos**:
  - 11 de **caracterização** (texto/tela em grade uniforme), verdes antes da migração;
  - não uniforme por dia no dashboard, conselho (painel e fechamento), histórico,
    ficha, gerenciar, atendimento, transferir e seletor da frequência;
  - dashboard por data: terça `08:00–10:00` e quinta `14:00–16:00`;
  - turma multi-oferta: `dias_da_turma` = união da grade e cada aluno vê a grade da
    **sua** oferta;
  - fallback sem grade: texto escalar + `logger.warning`;
  - sem N+1: consultas a `turma_curso_horario` constantes ao crescer ofertas.
- **Teste existente alterado (com motivo):** `tests/test_impressao_grade_oferta.py`
  (`TestRenderSemN1`). O teste do H3d media dois requests no **mesmo app**, criando
  ofertas entre eles; o segundo request não via as ofertas novas (estado de sessão),
  então passava por **falso-negativo**. Agora cada medição usa um **app novo** com o
  estado final e conta **apenas** SELECTs de `turma_curso_horario` (o contrato do H3d
  é “leituras da grade constantes”). A medição antiga, corrigida, expôs que o
  crescimento vem de `Turma.freq_geral` (N+1 pré-existente da D3b-2), não da grade —
  fora do escopo do H3e.

**Suíte:** **593 passed**, 1 deselected (a falha externa do §2); ruff
`--select F821,F811` limpo nos arquivos tocados.

## 7. Passo 6 — Ensaio no scratch (`pautaon_ensaio`, head `5730d7c594ba`)

`scripts/verificar_h3e_leitores.py` (somente leitura; saída em
`instance/backups/h3e_ensaio.txt`):

```
turmas ativas: 3 | ofertas ativas: 5
leituras comparadas: 160 | divergências inesperadas: 0 | divergências legítimas: 6
```

As 6 divergências legítimas são as ofertas **12** e **13** da turma multi-oferta, que
antes exibiam o par da **Turma** (`Segunda, Quarta · 08:00–11:00`) e agora exibem o
par da **própria oferta** (`Terça · 08:00–09:00` e `Quarta · 10:00–11:00`) — correção
esperada. **0 divergências inesperadas** nas leituras comparadas (dias/horário do
dashboard, aluno, ficha e conselho; intervalo por data de todas as datas esperadas).

## 8. Mudanças de texto na tela

| Tela | Antes | Depois |
|------|-------|--------|
| Dashboard — coluna de horário da turma | `08:00:00 às 09:30:00` | `08:00 às 09:30` |
| Dashboard — pendências | `Data · Turma · Pendentes` (sem hora) | nova coluna **Horário** com `08:00–09:30` (intervalo do **dia da data**) |
| Histórico/gerenciar/atendimento/transferir | `08:00:00 às 09:30:00` | `08:00 às 09:30` (ou por dia) |
| Conselho painel/fechamento | `Segunda, Quarta \| 08:00:00 às 09:30:00` | `Segunda, Quarta \| 08:00 às 09:30` |
| Ficha, frequência, listagem (H3d) | inalterados | inalterados |

A normalização `str(time)` → `HH:MM` é **deliberada** (o H3e reutiliza o formato do
H3d); nenhum outro caractere visível mudou. Em turma multi-oferta, aluno/ficha/conselho
passam a mostrar o par da **oferta** (antes repetiam o da Turma).

## 9. Passo 7 — Inventário para o H5

### (i) Escritas das colunas escalares

| Arquivo:linha | Classe | Ação sugerida no H5 |
|---------------|--------|---------------------|
| `app/services/turma_curso_horario.py:799-825` (`sincronizar_projecao_horario`) | única escrita de `turma_curso.dias_semana/hora_inicio/hora_fim` | remover a função e as 3 colunas |
| `app/services/turma_curso.py:433-435` (`_sincronizar_legado`) | único espelho oferta→`Turma` | remover as 3 atribuições junto com as colunas de `Turma` |
| `app/utils/datetime_parse.py:14` | docstring de exemplo (não executa) | atualizar o exemplo |

### (ii) Leituras de fallback (mantêm o comportamento de legado até o H5)

| Arquivo:linha | Contexto | Ação sugerida |
|---------------|----------|---------------|
| `app/main/dashboard_professor.py:38,230` | `_dias_badges`/entrada de turma sem oferta | virar “sem dados” quando a grade for obrigatória |
| `app/services/turma_curso_horario.py:272,278` | `dias_das_turmas_em_lote` (oferta/turma sem grade) | manter aviso e descartar o CSV |
| `app/services/turma_curso_horario.py:594` | C.H. da turma sem oferta | idem |
| `app/services/turma_curso_horario.py:750` | `grade_para_exibicao` (oferta sem grade) | idem |
| `app/relatorios/painel_pedagogico/ficha_aluno.py:160,165` | `_dias_horario` sem oferta | idem |
| `app/templates/conselho/fechamento.html:62-63` | `{% else %}` do `grade_oferta` | idem |
| `app/templates/turmas/listar.html:340-345` | fallback do par de horas da linha | idem |
| `app/services/turma_curso.py:973-976` (`_dias_efetivos_da_oferta`) | oferta → turma | idem |

### (iii) Leituras residuais (dependem do espelho; não quebram no H5 se migradas)

| Arquivo:linha | Contexto | Ação sugerida |
|---------------|----------|---------------|
| `app/services/turma_curso.py:491-493` | seed de oferta a partir da turma legada | migrar para `grade_da_oferta`/`definir_grade` ou desativar o caminho |
| `app/services/turma_curso.py:573-575` | herança na criação da 1ª oferta | idem |
| `app/services/turma_curso.py:645-647,660-662` | defaults de `editar_oferta` e da checagem de conflito | ler a grade atual (`grade_da_oferta`) |
| `app/services/turma_curso.py:268,894` | rótulos de mensagem (dias/horário) | trocar por `weekdays_para_csv(grade)` |
| `app/templates/turmas/detalhe.html:254` | rótulo do seletor | já lê a grade; só remover o `or` escalar |

### (iv) Legado / ensaios / testes

| Arquivo | Ocorrências | Observação |
|---------|-------------|------------|
| `tests/test_turma_curso_horario_escritores.py` | 22 | fixtures/caracterização da projeção |
| `tests/test_turma_curso_edicao.py` | 18 | payloads dos formulários (H4) |
| `tests/test_turma_curso_horario_servico.py` | 14 | contrato do serviço |
| `tests/test_turma_curso_horario_migration.py` | 11 | backfill/COALESCE |
| `tests/_helpers.py` + `test_definir_grade.py` + `test_turma_curso_fase3/4.py` + `test_datas_aula_oferta_grade.py` + `test_dias_semana.py` | 16 | apoio |
| `scripts/verificar_h3c_ch.py`, `verificar_h3d_filtros.py`, `verificar_h3e_leitores.py` | 30 | ensaios (somente leitura) |
| `scripts/diagnostico_carga_horaria.py` | 3 | migrado no H3e |

## 10. Desvios

1. **Normalização de texto** `str(time)` → `HH:MM` em dashboard, histórico,
   gerenciar, atendimento, transferir e conselho. A caracterização do P2 foi ajustada
   só nesses pontos; é mudança **intencional** (formato único do H3d).
2. **Teste de N+1 do H3d corrigido** (falso-negativo). A medição correta revelou um
   N+1 **pré-existente** em `Turma.freq_geral` (1 consulta por linha da listagem,
   D3b-2) — não é leitura de grade e não foi alterado no H3e; fica registrado para o
   H5.
3. **Turma multi-oferta** passa a mostrar o par **da oferta** no aluno/ficha/conselho
   (antes repetia o da Turma). É a semântica decidida (“dias e horário da
   turma/oferta pela grade”); sinalizada no ensaio como divergência legítima.
4. `app/__init__.py:101` ainda referencia `sistema_indisponivel.html` na raiz —
   consequência do commit alheio `7779aea`; não tocado.

## 11. Perguntas abertas

1. O **certificado** e os **painéis agregados** ainda exibem dias/horários? Não
   entraram no H3e (não estavam na lista do P1); avaliar no H4/H5 se leem por oferta.
2. `Turma.freq_geral`/`freq_geral_oferta` na listagem continuam em N+1 (D3b-2):
   corrigir no H5 ou em etapa própria?
3. Apertar `ck_tch_dia` para 0–5 no banco (o serviço já recusa domingo) — exige
   migration de revisão e limpeza de eventual legado.

## 12. O que NÃO mudou

- **Schema:** nenhuma migration; head `5730d7c594ba`.
- **Formulários e JS:** `turmas/ofertas.html`, `nova.js` e `editar.js` intocados (H4).
- **Colunas escalares:** nada removido; a projeção e o espelho continuam (H5).
- **Regras de negócio:** C.H., concomitância, filtros, vigência e bloqueios
  inalterados.
