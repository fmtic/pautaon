# ETAPA H3b — Relatório final

**Concomitância de horário por dia (leitura pela grade)** — 26/10/2026

## 1. Resumo

`_conflitos_horario_concomitante` passou a comparar a **grade por dia**: para cada weekday em comum entre as duas ofertas, compara o intervalo **daquele dia** (sobreposição estrita; adjacência não conflita). Continua sendo **AVISO, nunca bloqueio**, e a **vigência** continua limitando a comparação. As grades das demais ofertas vêm da relação `horarios` (`selectin`) em **uma consulta** — sem N+1. `_parse_dias` foi **removido** (ponte encerrada) e o `TestParseDias` também.

## 2. Commits, suíte e head

| Passo | Commit | Mensagem |
|---|---|---|
| P0 (docs) | `2aca2d1` | `docs: reorganiza docs/ em docs/Relatorios/ (sync Nextcloud) + relatorio H3a` |
| P0 (docstring) | `bbc76ce` | `H3b-P0: corrige docstring de datas_aula_oferta (limite inclusivo, sem mudar comportamento)` |
| P2 | `b2816f6` | `H3b-P2: caracterizacao da concomitancia em grades uniformes (pares + texto exato)` |
| P3 | `ff72ced` | `H3b-P3: concomitancia compara a grade POR DIA (lote, sem N+1) e remove _parse_dias` |
| P4 | `c89865f` | `H3b-P4: testes por dia (nao uniforme, criacao sem grade, N+1) + grade selectin em lote` |
| P6 | `e24fe8d` | `H3b-P6: MER (7.32a, 10, 12.25) e backlog - H3b concluida (concomitancia por dia)` |
| P7 | *(este relatório)* | `H3b-P7: relatorio final` |

- **Suíte:** 522 → **532 passed, 0 falhas** (8 de caracterização + 5 novos − 3 do `TestParseDias`).
- **Ruff:** `ruff check app tests scripts --select F821` limpo.
- **Head Alembic:** `5730d7c594ba` (nenhuma migration nesta etapa).
- **Branch:** `nova_feature`, **sem push**.

## 3. Testes alterados/removidos e por quê

- **Removido:** `tests/test_turma_curso_fase3.py::TestParseDias` (`test_csv_normal`, `test_none`, `test_vazio`) — testava `_parse_dias`, que foi **removido** por não ter mais chamador (só a concomitância o usava). A normalização de tokens já é coberta por `tests/test_dias_semana.py` (conversor único), que segue intacto.
- **Novo:** `tests/test_concomitancia_grade_por_dia.py` — 8 casos de **caracterização** rodados **verdes ANTES** da migração (`b2816f6`) e **idênticos depois** (mesmo par, mesmo texto exato): sobreposição total/parcial, adjacência, dias diferentes, vigência disjunta, edição que cria conflito, dois conflitos em ordem de id e "aviso nunca bloqueia".
- **+5 casos no mesmo arquivo (P4):** grade não uniforme com conflito **só no dia que sobrepõe** (e sem conflito no outro dia), edição que só muda vigência usando a **grade real** da candidata (a projeção escalar estaria NULL), criação sem grade usando a `agenda` recebida (nenhuma oferta criada pela checagem) e **sem N+1** (listener `before_cursor_execute`: **1** statement em `turma_curso_horario` para 3 ofertas).
- Nenhum outro teste precisou mudar: a caracterização uniforme garante que a migração não alterou o texto nem o conjunto de pares.

## 4. Mudanças de texto do aviso

- **Oferta com grade UNIFORME (caso comum/real):** texto **byte a byte igual** ao anterior —
  `Horário concomitante com 'Carpintaria' (Segunda, Quarta, 08:00–12:00). A oferta foi salva.`
- **Oferta com grade NÃO UNIFORME:** agora cita cada **dia em conflito** com o intervalo **daquele dia** —
  `Horário concomitante com 'Carpintaria' (Terça 08:00–10:00; Quinta 14:00–16:00). A oferta foi salva.`
  (antes o código só citava o CSV e um par único, que na projeção não uniforme é NULL — o aviso nem era emitido).
- **Semântica:** o conflito agora existe apenas no(s) dia(s) em que os intervalos realmente se sobrepõem. Antes bastava haver **qualquer dia em comum** e qualquer sobreposição do par único (mesmo que em outro dia).
- **Domingo:** domínio é **0–5**; eventual "Domingo" no CSV legado **não é comparado** (nenhuma oferta real tem domingo).

## 5. Desvios e decisões de execução

- **Lote via relação `selectin` (não `grades_em_lote`):** o teste de N+1 mostrou que `TurmaCurso.query(...)` já carrega `horarios` em **1 consulta** (selectin) e que `grades_em_lote` adicionava um **2º** statement. Como a grade já está em memória, `grade_da_oferta` (serviço) é usada sem consulta extra — resultado: **1 statement** e nenhum risco de `noload` mascarar a relação na sessão.
- **`editar_turma` POST não precisou de mudança:** nesse caminho a agenda da oferta única é **uniforme por construção** (grade não uniforme é ignorada no POST desde o H2), então o trio escalar segue suficiente.
- **`editar_oferta` passa a candidata explícita:** `agenda=itens` quando a agenda veio no `dados`; caso contrário `grade_da_oferta(oferta)` (edição só de vigência compara a grade **real**).
- **Validação do banco scratch:** `make_url(...).set(database=...)` re-renderiza a DSN e **quebra a autenticação** quando a senha tem caracteres percent-encoded; o script temporário trocou só o nome do banco na string crua. Script **apagado** ao final.
- **Reorganização `docs/ → docs/Relatórios/`** (sincronismo Nextcloud) foi commitada **isolada**, só documentação, após grep confirmar que nenhum código abre `docs/` — apenas menções textuais em docstrings (ficaram apontando para o caminho antigo; sem impacto funcional). O Nextcloud também renomeou o relatório anterior (`H3a_Leitores_de_ agenda.md` → `H3a_Leitores_de_agenda.md`), sem espaço.

## 6. Ensaio no scratch PostgreSQL (P5)

- Banco `pautaon_ensaio`, head `5730d7c594ba`, **5 ofertas ativas**, **8 linhas** de grade.
- Comparação **oferta a oferta**, ANTIGO (colunas escalares) × NOVO (grade por dia): **0 divergências**.
- 2 pares conflitantes reais, com texto **idêntico** antes/depois:
  - `Mecânica de motores de popa` ↔ `Informática` (quarta, 10:00–11:00);
  - `Informática` ↔ `Mecânica de motores de popa` (Segunda, Quarta, 08:00–11:00).

## 7. O que NÃO mudou

- **C.H.** total/por aula — segue o caminho anterior (H3c).
- **Filtros, listagem e impressão** — seguem escalares (H3c/H3d).
- **Telas/templates** e **exibição de hora** — inalterados (H3e/H4).
- **Vigência** continua limitando a comparação; **concomitância continua aviso**, nunca bloqueio.
- **Schema** intacto (head `5730d7c594ba`); nenhuma coluna ou projeção tocada.

## 8. Perguntas abertas

1. **Formato do aviso não uniforme** — o formato `Terça 08:00–10:00; Quinta 14:00–16:00` é aceitável ou prefere agrupar dias com o mesmo intervalo?
2. **Granularidade do aviso** — hoje é **um aviso por oferta conflitante** (com os dias listados). Manter assim ou um aviso por par/dia?
3. **Domingo no legado** — ignorado por estar fora do domínio 0–5; se a instituição passar a usar domingo, revisar o domínio e o `ck_tch_dia` (pergunta aberta desde a H2).
4. **Intervalo da candidata** — o texto cita o intervalo **da outra** oferta (como antes). Incluir também o da candidata naquele dia?

**Status: H3b concluída.** Restam H3c–H3e (C.H., filtros/listagem, hora/exibição), H4 (UI por dia) e H5 (drop das colunas de projeção).
