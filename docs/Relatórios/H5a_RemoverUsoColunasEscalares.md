# H5a — Remover todo uso das colunas escalares de agenda (sem mexer no schema)

**Data:** 26/10/2026 · **Branch:** `nova_feature` (sem push) · **Head Alembic:** `5730d7c594ba` (sem migration)
**Escopo:** a partir do H5a, a grade `turma_curso_horario` é a **única fonte de agenda**. Nenhum código de `app/` ou `scripts/` lê ou escreve `Turma.dias_semana/hora_inicio/hora_fim` nem `TurmaCurso.dias_semana/hora_inicio/hora_fim`. As seis colunas continuam no banco e nos modelos apenas até a remoção física (**H5b**). Sem schema, sem migration, sem derrubar sessões do principal.

**Decisões aplicadas:** dias 0–5; toda oferta nasce com dia e hora; turma sem oferta **não tem agenda** (a agenda nasce com a oferta); **sem fallback de legado**; sem schema.

---

## 1. Commits

| Commit | Conteúdo |
|---|---|
| `9a3ae35` | H5a-P2/P3 — remove projeção/espelho/fallbacks e leituras escalares de `app/` e `scripts/`; adapta `diagnostico_carga_horaria.py`; apaga `verificar_h3c_ch.py`/`verificar_h3d_filtros.py`/`verificar_h3e_leitores.py`. |
| `f0891a0` | H5a-P4 — helper único de agenda em `tests/_helpers.py`, migração de fixtures/payloads, conversão/remoção dos testes de projeção/fallback e guarda AST `test_guarda_colunas_escalares_h5a.py`. |
| (commit de docs) | H5a-P7/P8 — MER (§7.32a, §8.10, §10, §12.25), backlog e este relatório. |

O ensaio no scratch e a prova por remoção **não** foram commitados como código; os scripts temporários foram apagados.

---

## 2. Pré-requisitos e preflight (PASSO 0)

- `flask db heads` = **`5730d7c594ba (head)`**.
- Suíte de partida (H4): **640 passed**.
- Preflight **somente leitura** no principal (`default_transaction_read_only=on`, sem derrubar sessões):

```
(i) ofertas de QUALQUER status sem nenhuma linha de grade: 0
(ii) ofertas com escalares preenchidos e grade diferente da projeção:
     5 ofertas com escalares | divergentes: 0
(iii) turmas sem oferta com escalares preenchidos: 0
(iv) linhas de grade com dia 6 (domingo): 0
contexto: 3 turmas, 5 ofertas, 8 linhas de grade, 3 turmas c/ dias_semana
```

Nenhum PARE: (i), (ii) e (iv) = 0; (iii) = 0. Preflight repetido ao final com os mesmos números — principal intocado.

---

## 3. Inventário final (PASSO 1) e o que saiu

Grep exaustivo de `dias_semana`/`hora_inicio`/`hora_fim` em `app/`, `scripts/`, templates, JS e tests, com classificação. **Nenhum acesso às seis colunas mapeadas restou em `app/`/`scripts/`** (o guarda AST abaixo é a prova automatizada).

### 3.1 O que foi removido/convertido em `app/`

| Arquivo | Símbolo | Classe | Ação |
|---|---|---|---|
| `app/services/turma_curso_horario.py` | `sincronizar_projecao_horario` | escrita (projeção) | removida |
| `app/services/turma_curso_horario.py` | `duracao_escalar_oferta`, `_duracao_turma_escalar` | fallback | removidos |
| `app/services/turma_curso_horario.py` | ramos “sem grade → escalar” em `carga_horaria_total_oferta`, `cargas_horarias_ofertas_em_lote`, `cargas_horarias_turmas_em_lote`, `intervalo_do_dia`, `grade_para_exibicao`, `dias_das_turmas_em_lote` | leitura/fallback | removidos; sem grade → `logger.error`/`None`/texto vazio |
| `app/services/turma_curso_horario.py` | `condicao_turma_com_grade` e o `or_` do `filtro_por_dia_horario` | fallback (filtros) | removidos; filtro lê só `EXISTS` na grade |
| `app/services/turma_curso_horario.py` | `grade_a_partir_do_legado` | conversão de escalares | removida (sem uso) |
| `app/services/turma_curso.py` | `sincronizar_projecao_turma`, `_defaults_agenda_da_oferta`, `_dias_efetivos_da_oferta` | escrita/leitura | removidos (substituídos por `_agenda_da_oferta`/grade) |
| `app/services/turma_curso.py` | 3 atribuições de agenda em `_sincronizar_legado` | escrita (espelho) | removidas; demais espelhos (curso/professor/turno/datas/centro/programa) mantidos |
| `app/services/turma_curso.py` | herança/seed em `adicionar_oferta` e `criar_oferta_inicial_da_turma` | leitura (fallback) | removida; sem `agenda` → `ValueError` de agenda incompleta |
| `app/services/turma_curso.py` | `editar_oferta` aceitando `dias_semana`/`hora_inicio`/`hora_fim` | formulário/serviço | passa a **recusar** o trio escalar; agenda só por `agenda=` |
| `app/registros/turmas.py` | escrita direta de agenda no POST `editar_turma` (0/1 oferta) e `sincronizar_projecao_turma` | escrita | removida; 0 ofertas não tem agenda (campos somem/ignorados); 1 oferta só `definir_grade`; 2+ bloqueado |
| `app/registros/turmas.py` | `_estado_agenda_da_grade` com escalares, comparador escalar dos filtros | formulário/fallback | removidos; estado vem só da grade; token de dia inválido → `false()` |
| `app/registros/turmas.py` | `_resumo_ofertas` fallback CSV | leitura | removido; dias só da grade (oferta sem grade não contribui) |
| `app/main/dashboard_professor.py` | `_dias_badges(turma=...)`, `_horario_entrada(turma=...)`, intervalo escalar das pendências | leitura/fallback | removidos; sem grade → sem badges/horário |
| `app/relatorios/painel_pedagogico/ficha_aluno.py` | `_dias_horario` fallback da Turma | leitura | removido; sem oferta → `—` |
| `app/utils/logica.py` | `gerar_datas` fallback `csv_para_weekdays(turma.dias_semana)` | leitura/fallback | removido; sem dias na grade → lista vazia |
| `app/templates/turmas/listar.html` | fallback `turma.hora_inicio/hora_fim` | exibição | removido; sem grade → `--:--` |
| `app/templates/turmas/ofertas.html` | fallback `oferta.dias_semana/hora_*` | exibição/formulário | removido; sem grade → `—`; inputs sem valor escalar |
| `app/templates/conselho/fechamento.html` | fallback `turma.dias_semana/hora_*` | exibição | removido; sem oferta escolhida → `—` |
| `app/templates/turmas/editar.html` | campos/hidden de agenda com 0 ofertas e hidden escalar com 2+ | formulário | 0 ofertas: bloco informativo, sem campos; 2+ : readonly sem `name` escalar |

### 3.2 O que permanece (legítimo)

| Arquivo:linha | Classe | Ação/motivo |
|---|---|---|
| `app/models/academico.py:126-130` (Turma) e `:317-319` (TurmaCurso) | declaração das colunas | permanecem no schema/modelos **até o H5b**; comentário “LEGADO (H5a), não leia nem escreva” |
| `migrations/versions/5730d7c594ba_...py` | migration histórica | lê os escalares no backfill H1; tem conversor próprio, **não importa** código removido |
| `app/utils/dias_semana.py` | conversor único | permanece; usado por formulários/serviços (não acessa modelos) |
| `app/registros/turmas.py:112-320` | `grade_do_formulario`/`_estado_agenda*` | nomes `dias_semana`/`hora_inicio`/`hora_fim` são **campos HTTP**, não atributos mapeados |
| `app/services/turma_curso.py:225,296,349,605`; `app/services/turma_curso_horario.py:126-136,154,180,201,290,317-321,365,442-451,591-647,673,794` | linhas da grade (`l`/`linha`/`item`) e DTO `Linha`/`GradeExibicao` | atributos homônimos de **`TurmaCursoHorario`/DTO**, não das seis colunas |
| templates/JS | `grade_*` (`GradeExibicao`) | exibem a grade; nenhum `turma.*`/`oferta.*` escalar (guarda complementar) |
| `tests/test_turma_curso_horario_migration.py:92-129` | teste da migration | grava escalares por **SQL direto** e recria as colunas no SQLite via DDL; não usa o modelo como intermediário |

### 3.3 Certificado, painéis agregados, BI e exportações

Confirmado por grep: `app/relatorios/*`, `app/relatorios/painel_pedagogico/*`, `app/registros/periodos.py` (certificado) e exportações **não acessam** `.dias_semana`/`.hora_inicio`/`.hora_fim` de Turma/TurmaCurso. Eles leem a grade/ofeta ou não tratam de agenda.

---

## 4. Escritores e leitores removidos (PASSOS 2–3)

- **Escritores:** `sincronizar_projecao_horario`, `sincronizar_projecao_turma`, as 3 atribuições de `_sincronizar_legado`, a escrita direta no POST de `editar_turma` e o seed/herança a partir dos escalares. A única escrita de agenda restante é `definir_grade` (na oferta).
- **Leitores/fallbacks:** todos os ramos “sem grade → escalar” viraram **estado inválido**: `logger.error` no serviço e “sem horário”/`—` na tela. Oferta ativa sem grade não contribui dias/C.H.; turma sem oferta não tem agenda.
- **`editar_turma`:** com **0 ofertas** os campos de agenda não aparecem e o POST os ignora (bloco informativo “a agenda é definida em Cursos da Turma”); com **1 oferta** grava só via `definir_grade`; com **2+** mantém o bloqueio (readonly, sem hidden escalar).
- **Scripts:** `verificar_h3c_ch.py`, `verificar_h3d_filtros.py` e `verificar_h3e_leitores.py` **removidos** (ensaios históricos comparavam “ANTES” escalar × grade). `diagnostico_carga_horaria.py` **adaptado**: dias pela união da grade; sem grade imprime “— (sem oferta ativa com grade)”.
- **Migrations:** nenhuma importa o código removido; a H1 segue intacta e não foi alterada.

---

## 5. Testes (PASSO 4)

### 5.1 Helper único

`tests/_helpers.py` concentra a agenda:

- `itens_grade(dias_semana, hora_inicio, hora_fim)` — CSV + par → `[(weekday, ini, fim)]` (0–5);
- `aplicar_grade(oferta, ...)` — grava via `definir_grade`;
- `grade_atual(oferta)` — leitura auxiliar da grade;
- `nova_oferta(..., dias_semana=, hora_inicio=, hora_fim= | grade=)` — converte para grade; **o construtor do modelo nunca recebe as colunas**.

### 5.2 Fixtures/payloads migrados

Todos os construtores `Turma(...)`/`TurmaCurso(...)` dos testes deixaram de passar as seis colunas (varredura AST manual + script). Onde a agenda importa (C.H., datas, exibição, filtros, dashboard), a grade é criada explicitamente. Testes que usam payloads HTTP com `dias_semana`/`hora_inicio`/`hora_fim` continuam válidos: são **campos de formulário**, não colunas.

### 5.3 Testes removidos/convertidos e motivo

| Arquivo | Antes → depois | Motivo |
|---|---|---|
| `test_turma_curso_horario_servico.py` | −5 testes `test_projecao_*` | caracterizavam `sincronizar_projecao_horario`, removida no H5a |
| `test_carga_horaria.py` | −7 → +5 | testes da Turma com escalares no construtor (fallback) convertidos para turma+oferta+grade; `hora_fim <= início` não é representável na grade (CHECK/`definir_grade` já cobre) |
| `test_datas_aula_oferta_grade.py` | −2 → +1 | “oferta sem grade cai no CSV projetado” e “nem CSV” viraram um único “sem grade não gera datas” |
| `test_filtros_turma_grade.py` | −5 → +5 | caracterização do fallback escalar (turma sem oferta/oferta sem grade) convertida para “não casa filtro algum” |
| `test_impressao_grade_oferta.py` | −2 → +2 | texto de fallback escalar virou “sem horário”/“sem agenda” |
| `test_leitores_grade_h3e.py` | −2 → +2 | dashboard/aluno com fallback escalar viraram “não usa escalar” (mostra ausência) |
| `test_leituras_residuais_grade_h3f.py` | −11 → +9 | casos de herança/seed/defaults por escalar foram substituídos por contrato `agenda=`/grade; testes de projeção envenenada perderam objeto |
| `test_turma_curso_horario_escritores.py` | −6 → +6 | nomes/asserções “reprojeta”/“espelha projeção” viraram “grava via grade”/“não corrompe grade” |
| `test_turma_curso_fase4.py` | −1 → +1 | “legado lança duas vezes” virou “0 ofertas ativas: sem agenda não há calendário” |
| `tests/test_guarda_colunas_escalares_h5a.py` | **+2** | guarda nova (AST em `app/`+`scripts/` e regex em templates/JS) |

Testes novos de contrato H5a incluem: `editar_oferta` recusa escalares; `adicionar_oferta`/seed sem agenda → `ValueError`; seed com agenda grava grade; turma sem oferta não tem agenda/C.H.; oferta sem grade não casa filtros nem gera datas.

### 5.4 Guarda AST

`tests/test_guarda_colunas_escalares_h5a.py` percorre `app/**/*.py` e `scripts/**/*.py` e falha em qualquer `Attribute` `.dias_semana/.hora_inicio/.hora_fim` cuja base não seja uma linha de grade (`l`, `linha`, `item`), a própria coluna `TurmaCursoHorario` ou o `self` dos DTOs `Linha`/`GradeExibicao`. Guarda complementar em `.html`/`.js`: proíbe `turma.*`, `turma_obj.*`, `oferta.*` e `oferta_<algo>.*` com esses nomes; `grade_*` continua permitido.

**Suíte final: 632 passed, 0 falhas** (`640` antes; ver §5.3 para as remoções/conversões). `ruff check --select F821` limpo.

---

## 6. Prova por remoção (PASSO 5)

Procedimento no working tree (não commitado):

1. Removidas as 6 declarações `db.Column` de `Turma`/`TurmaCurso` em `app/models/academico.py` (backup local do arquivo).
2. Suíte completa: **14 falhas iniciais**, todas em `tests/test_turma_curso_horario_migration.py`, porque o teste criava o SQLite por `db.create_all()` e o backfill H1 escreve as colunas por SQL direto. Ajuste **no teste**: `_garantir_colunas_legadas()` recria as 3 colunas por DDL no SQLite quando o modelo não as declara — o teste da migration passa a independer do modelo (útil para o H5b), sem tocar schema/migration.
3. Ainda apareceram leitores **em testes** (asserts `turma.hora_inicio`/`dias_semana` em `test_turma_curso_edicao.py`/`test_ui_grade_por_dia.py` e um `_oferta(..., dias_semana=...)`): removidos; a verificação de “não escreveu” passou a ser a própria grade + guarda.
4. Reexecução: **632 passed** com as colunas fora dos modelos.
5. Smoke de UI (test client, SQLite novo, 18 rotas): `/dashboard`, `/turma`, `/turma/<id>`, `/turma/<id>/ofertas`, `/turma/editar/<id>`, `/turma/<id>/sem oferta`, `/alunos`, histórico, atendimentos, transferir, `/frequencia`, ficha, `/conselho` — **0 respostas 500**, incluindo oferta sem grade e turma sem oferta.
6. Modelos restaurados (hash idêntico ao backup) e suíte repetida: **632 passed**.

Resultado: **nenhum leitor/escritor de app/scripts restante**; as únicas dependências das colunas são a migration histórica e a declaração dos modelos (H5b).

---

## 7. Ensaio no scratch Postgres (PASSO 6)

- `pautaon_ensaio` **recriado de dump novo do principal** (`pg_dump` read-only, `dropdb --force`/`createdb`/`pg_restore` apenas no scratch), head verificada `5730d7c594ba`, 3 turmas/5 ofertas/8 linhas. Principal intocado.
- App montado com `DATABASE_URL` do scratch; test client autenticado como pedagógico real **MGB (usuário 24, unidade 2)**; CSRF desabilitado só no config do ensaio.
- **5 ofertas reais / 3 turmas**, leitura e valores:

```
oferta 11 (turma 9 Mecânica de popa): Seg/Qua 08:00–11:00 — C.H. 6.300 min
oferta 12 (turma 9): Ter 08:00–09:00 — 420 min
oferta 13 (turma 9): Qua 10:00–11:00 — 1.140 min
oferta 14 (turma 10 Informática): Seg/Qua 14:00–17:00 — 6.300 min
oferta 15 (turma 11 Natação): Seg/Ter 13:00–15:00 — 4.200 min
turmas: 9 → 6.720 min; 10 → 6.300 min; 11 → 4.200 min
```

- Projeção escalar × grade: **idênticas nas 5 ofertas** (0 divergências).
- **48 verificações** (valores, C.H. e leitores HTTP): listagem+filtros, detalhe, impressão, cursos, C.H., dashboard, aluno/histórico/ficha, conselho/fechamento, frequência. **0 divergências** em relação ao H4; C.H. da oferta 14 = **6.300 min**, igual ao H4.
- **Filtros da listagem:** 15 combinações (dia, horário de início, dia+horário na mesma linha) cobrindo as 5 ofertas; todas encontraram a turma correta (0 falhas).
- Rotas de edição de oferta são POST-only (`GET` → 405 esperado); não houve 500. Scratch pode ser recriado; principal intocado.

---

## 8. Desvios e perguntas abertas

1. **Teste da migration:** precisou recriar as colunas legadas por DDL no SQLite (`_garantir_colunas_legadas`). Não é mudança de schema/migration; é o teste histórico deixando de depender do modelo atual, necessário para o H5b.
2. **`test_carga_horaria.py`:** o caso “fim ≤ início” foi removido em vez de convertido — a grade não representa esse estado (`definir_grade`/CHECK já recusam); os demais casos foram convertidos para turma+oferta+grade.
3. **Oferta sem grade** agora é **estado inválido explícito** (`logger.error` + “sem horário”): antes exibia o valor escalar. É a mudança visível intencional do H5a; no principal não há oferta sem grade (preflight (i)=0).
4. **Turma sem oferta** não mostra mais dias/horário (antes lia a coluna). No principal não há turma sem oferta com escalares (preflight (iii)=0); turmas sem oferta passam a exibir ausência de agenda.
5. **Perguntas para o H5b:** (a) apertar `ck_tch_dia` de 0–6 para 0–5 na mesma migration do drop? (b) remover também `Turma.dias_semana/hora_*` junto com as da oferta? (c) o teste da migration H1 deve ser mantido com DDL manual ou aposentado após o drop? (d) `app/utils/dias_semana.py` permanece (formulários/serviços), independentemente do drop.

---

## 9. O que NÃO mudou

- **Schema:** nenhuma migration; head **`5730d7c594ba`**; as 6 colunas continuam no banco e nos modelos.
- **Migrations:** `5730d7c594ba` e anteriores intactas; nenhuma importa código removido.
- **CHECKs/UNIQUEs:** `ck_tch_dia` segue 0–6 no banco (serviço recusa domingo); UNIQUE/CHECKs de `turma_curso_horario` intactos.
- **Contrato da grade:** `definir_grade` continua a única escrita; dias 0–5, par completo, `fim > início`, sem duplicata.
- **Principal:** intocado, nenhuma sessão derrubada; preflight repetido no fim com 0/0/0/0.
- **Rotas/telas em grades uniformes:** mesmos textos/valores do H4; a única diferença é a ausência de fallback para os estados inválidos (oferta sem grade/turma sem oferta).

---

## 10. Reprodução rápida

```
flask db heads                      # 5730d7c594ba
pytest -q                           # 632 passed
ruff check app scripts tests --select F821
```

Prova por remoção (manual, não commitada): apagar as 6 declarações em `app/models/academico.py`, rodar `pytest -q` e o smoke de rotas; restaurar o arquivo e repetir a suíte.
