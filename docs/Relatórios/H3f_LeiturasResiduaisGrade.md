# H3f — Leituras residuais de escalares em `turma_curso.py` passam a ler a grade

**Data:** 26/10/2026 · **Branch:** `nova_feature` (sem push) · **Revisão Alembic:** head única `5730d7c594ba` (sem migration nova)
**Suíte ao final:** **614 passed**, 0 falhas, sem `deselect` · **Ruff:** `--select F821,F811` limpo nos arquivos da etapa
**Fontes:** relatório H3e §9 (inventário (i)-(iv)), MER (§7.32a, §10, §12.25), backlog, relatórios H2/H3a–H3e (`docs/Relatórios/`).
**Escopo:** eliminar toda leitura residual de `dias_semana`/`hora_inicio`/`hora_fim` (Turma e TurmaCurso) feita por **serviços** e **templates**, deixando apenas (a) projeção/espelho e (b) fallback para legado sem grade com `logger.warning`. Pré-requisito do H4.

---

## 1. Commits da etapa

| Hash | Passo | Mensagem (resumo) |
|------|-------|-------------------|
| `eaa7c05` | P0 | Fix: `render_template` de `sistema_indisponivel` aponta para `erros/` (templates movidos pelo commit alheio `7779aea`) — commitado **à parte**, como exigido |
| `b5a7a35` | P2 | Caracterização das leituras residuais (mensagens, defaults de `editar_oferta`, herança da 1ª oferta, rótulo do seletor) em grade uniforme |
| `933d403` | P3 | Defaults de `editar_oferta` e checagem de conflito partem da grade; herança e seed legados explícitos com warning; mensagens citam dias da grade |
| `467876c` | P4 | Testes do contrato novo (grade não uniforme preservada, conflito e mensagens pela grade real, herança só para turma sem grade, rótulo só grade) — 20 casos |
| `17c0dad` | P7 | MER (§7.32a, §10, §12.25) e backlog — H3f concluída |
| (este) | P8 | Relatório final |

Estado antes da etapa: HEAD `9337f60` (H3e), suíte completa **594 passed** (P0 verificado antes de qualquer edição).

---

## 2. PASSO 1 — Leituras classificadas

Itens do inventário H3e §9 (iii) confirmados no código atual, mais o que apareceu por grep. **Nenhum caso (c)** — nada de PARE.

| Local | Conteúdo | Classe | Destino |
|-------|----------|--------|---------|
| `turma_curso.py` ~L573-575 (época H3e) | herança da 1ª oferta em `adicionar_oferta` (`turma.dias_semana or…`) | **(b)** | migrado P3 |
| `turma_curso.py` ~L645-647 | defaults de `editar_oferta` a partir dos escalares | **(b)** | migrado P3 |
| `turma_curso.py` ~L660-662 | defaults da checagem de conflito em `editar_oferta` | **(b)** | migrado P3 |
| `turma_curso.py` ~L268 | rótulo do aviso de concomitância (`outra.dias_semana or`) | **(b)** | migrado P3 |
| `turma_curso.py` ~L894 | mensagem do `resolver_oferta_lancamento` (`oferta.dias_semana`) | **(b)** | migrado P3 |
| `turma_curso.py` ~L491-493 | seed de `criar_oferta_inicial_da_turma` a partir da turma legada | **(a)** | permanece (função só roda quando a turma **não tem oferta alguma** — grade impossível); ganhou `logger.warning` explícito no P3 |
| `detalhe.html:254` | rótulo do seletor de enturmação | **(a)/já limpo** | **divergência do inventário**: o "or" escalar foi removido no H3d (`52ebf9d`); nada a fazer |
| `turma_curso.py` L433-435 (época) | `_sincronizar_legado` espelha oferta→Turma | **(a)** | projeção/espelho legítimo |
| fallbacks de `turma_curso_horario.py`/`turma_curso.py` | leituras de escalar só **sem grade** | **(a)** | permanecem (detalhe na §5) |

Extras encontrados por grep além do inventário: `registros/turmas.py` (rota/formulário e fallbacks já classificados no H3d/H3e), `main/dashboard_professor.py` e `relatorios/painel_pedagogico/ficha_aluno.py` (fallbacks do H3e), templates/JS (H4) — todos no conjunto esperado, nenhum leitor (c).

## 3. PASSO 2 — Caracterização (antes de migrar)

Novo `tests/test_leituras_residuais_grade_h3f.py`, classe `TestCaracterizacao` — **9 casos em grade uniforme, verdes no código ANTIGO** (commit `b5a7a35`), fixando:

- texto exato do aviso: `Horário concomitante com 'Curso A' (Segunda, Quarta, 08:00–12:00). A oferta foi salva.`;
- mensagem do resolver citando `(Segunda, Quarta)`;
- `editar_oferta` só-programa preserva a grade; só-dias herda o par por default (`[(4, 8, 12)]`);
- edição de vigência sem dia comum → sem aviso; com dia comum → aviso uniforme;
- herança da turma sem grade → `[(0, 9, 10)]`; seed legado → `[(0, 9, 10)]`;
- rótulo do seletor: `"Curso A — Manhã 08:00"`.

**Todos os 9 passam idênticos depois da migração** (contrato "sem mudança para grades uniformes" cumprido).

## 4. PASSO 3 — Migração (commit `933d403`)

Tudo em `app/services/turma_curso.py`; **nenhuma gravação nova** fora de `definir_grade`/`sincronizar_projecao_horario`; **sem migration**:

1. **`_defaults_agenda_da_oferta(oferta)`** (helper novo, L285-307): CSV dos dias da grade; par `(ini, fim)` só se **uniforme**, senão `NULL`; sem grade → escalares com `logger.warning` (L303-306). Usado pelos defaults de `editar_oferta` **e** da checagem de conflito.
2. **Herança (`adicionar_oferta`, L603-634)**: `agenda_herdada` prefere `grade_da_oferta` de uma oferta **ativa com grade** da turma (principal se existir); escalares da Turma só quando `agenda_herdada is None` e a turma não tem grade alguma — `logger.warning` (L626-629).
3. **Seed (`criar_oferta_inicial_da_turma`, L519-529)**: caminho legado explícito com `logger.warning` ("Turma %s sem oferta: agenda da 1ª oferta vem dos escalares legados da turma.").
4. **Rótulos**: aviso de concomitância com `weekdays_para_csv(grade_outra)` (L268, sem `outra.dias_semana or`); mensagem do resolver com `weekdays_para_csv(sorted(_dias_set_da_oferta(oferta)))` (L968-975).
5. **Conflito em `editar_oferta`**: `agenda=(itens if itens is not None else (grade_da_oferta(oferta) or None))` — edição sem campos de agenda usa a **grade real**; oferta 100 % legado (grade vazia → `None`) volta a ser checada pelo fallback escalar interno com warning (mudança intencional, alinhada ao contrato de fallback).
6. **Fallback de conflito do `_conflitos_horario_concomitante`** (L365-372): leitura escalar de `outra` só sem grade, com `logger.warning`.

## 5. PASSO 4 — Testes (commit `467876c`)

`test_leituras_residuais_grade_h3f.py` cresceu para **20 casos** (4 classes novas):

- `TestEditarOfertaGradeNaoUniforme` — edição de só-vigência/só-programa preserva a grade não uniforme; triple `None` do formulário atual → `ValueError("ao menos um dia")` com grade **intacta** (antes regrava uniforme a partir de NULL); projeção "envenenada" à mão é ignorada.
- `TestConflitoUsaGradeReal` — aviso por dia `"(Segunda 08:00–10:00)"` (par da outra oferta no dia em conflito) com grades não uniformes; mensagem do resolver cita os dias da grade mesmo com projeção trocada.
- `TestHerancaSoParaTurmaSemGrade` — herança sai da grade de oferta ativa (uniforme e não uniforme); escalares só no estado-limite, com warnings no caplog (`"sem grade"` + `"escalares"`); seed legado com warning.
- `TestRotuloSeletorSoGrade` — grade não uniforme: `"Curso A — Manhã"` presente, sufixos de hora escalares ausentes.

**Testes existentes alterados: NENHUM.** A suíte antiga passou intacta em todos os passos (594 → 603 → 614).

## 6. PASSO 5 — Inventário final (grep exaustivo `\.(dias_semana|hora_inicio|hora_fim)\b`)

### 6.1 `app/` — Python

| Arquivo:Linha | Função/símbolo | Classe | Ação para o H5 |
|---|---|---|---|
| `services/turma_curso.py:462-464` | `_sincronizar_legado` (escrita espelho) | projeção/espelho | manter até H5 (drop junto das colunas) |
| `services/turma_curso.py:300` | `_defaults_agenda_da_oferta` (`l.*` de Linha) | atributo de Linha | nenhuma |
| `services/turma_curso.py:307` | fallback sem grade (warning L303) | **fallback c/ warning** | remover no H5 |
| `services/turma_curso.py:362` | conflito, grade da outra (`l.*`) | atributo de Linha | nenhuma |
| `services/turma_curso.py:372` | fallback escalar da outra (warning L367) | **fallback c/ warning** | remover no H5 |
| `services/turma_curso.py:529` | seed `criar_oferta_inicial_da_turma` (warning L524) | **fallback c/ warning** | remover no H5 (ou manter p/ turma 100 % legado sem oferta) |
| `services/turma_curso.py:624` | herança `agenda_herdada` (l.*` da grade) | grade | nenhuma |
| `services/turma_curso.py:632-634` | herança escalares da turma (warning L628) | **fallback c/ warning** | remover no H5 |
| `services/turma_curso.py:877→1052-1059` | `_dias_set_da_oferta` → `_dias_efetivos_da_oferta` (warning no chamador L880) | **fallback c/ warning** | remover no H5 |
| `services/turma_curso_horario.py:811,821-825` | `sincronizar_projecao_horario` (**único escritor da projeção**) | projeção | alvo do drop no H5 |
| `services/turma_curso_horario.py:272,278` | `dias_da_turma` fallback (warnings L268/274) | **fallback c/ warning** | remover no H5 |
| `services/turma_curso_horario.py:371-374` | `duracao_escalar_oferta` (chamadores warns L390/L494) | **fallback c/ warning** | remover no H5 |
| `services/turma_curso_horario.py:503-506` | `cargas_horarias_ofertas_em_lote` ramo legado (warn L494) | **fallback c/ warning** | remover no H5 |
| `services/turma_curso_horario.py:594` | `dias_por_ofertas_em_lote` sem ofertas (warn L588) | **fallback c/ warning** | remover no H5 |
| `services/turma_curso_horario.py:651-658` | `intervalo_do_dia` fallback (warn no chamador) | **fallback c/ warning** | remover no H5 |
| `services/turma_curso_horario.py:749-756` | `grade_para_exibicao` fallback (warn L745) | **fallback c/ warning** | remover no H5 |
| `services/turma_curso_horario.py` demais L (126-136,154-201,311,342-346,358,398,445*,479-488,646-648,680-712,737,915) | atributos de `Linha`/`TurmaCursoHorario` e docstrings (*`duracao_do_dia(turma)` recebe par já resolvido) | não é leitura da coluna | nenhuma |
| `utils/logica.py:236-242` | `gerar_datas` fallback CSV (warning L238) | **fallback c/ warning** | remover no H5 |
| `main/dashboard_professor.py:38,48-50,135-136,230` | resumo/pendências/exibição sem grade/oferta (H3e) | **fallback** | remover no H5; ver pergunta aberta |
| `relatorios/painel_pedagogico/ficha_aluno.py:160-165` | `_dias_horario` sem oferta (vínculo legado, H3e) | **fallback** | remover no H5; ver pergunta aberta |
| `registros/turmas.py:210-216` | `_resumo_ofertas` fallback CSV (docstring L195-196) | **fallback** | remover no H5 |
| `registros/turmas.py:337-354` | comparador escalar do filtro (fallback só turma sem oferta com grade, H3d) | **fallback** | retirar a ramificação no H5 |
| `registros/turmas.py:1244-1307,1382-1384,1485-1487,1512-1519` | rota `editar_turma` GET/POST: leitura p/ preencher formulário e **escrita direta dos escalares da Turma** (POST L1381-1384, só com 0/1 oferta e `agenda_ignorada` False) | **formulário (H4)** | H4 reescreve via grade; H5 dropa as colunas |
| `registros/alunos.py:951` · `utils/datetime_parse.py:14` | comentário de docstring | não-executável | nenhuma |

### 6.2 Templates

| Arquivo:Linha | Uso | Classe | Ação |
|---|---|---|---|
| `turmas/listar.html:341-343` | fallback `{% else %}` do horário da linha (grade primeiro) | **fallback** | H5 |
| `conselho/fechamento.html:62-63` | fallback do cabeçalho sem oferta escolhida (2+ cursos) | **fallback** | H4/H5 |
| `turmas/editar.html:10,183-184,193,224,228` | hidden/readonly/checkboxes/inputs `time` da **turma** | **formulário** | **H4** (não tocado) |
| `turmas/ofertas.html:48-50,117,122,167` | coluna de dias/horas (projeção) e inputs/checkboxes do form de **oferta** | **formulário/projeção** | **H4** (não tocado) |
| `detalhe.html:112-114`, `imprimir_listar_turma.html:99`, `atendimento_pedagogico.html:92`, `listar.html:416-417`, `detalhe.html:254` | atributos de `GradeExibicao`/`Linha` (não são as colunas) | exibição por grade | nenhuma |

### 6.3 JS e scripts

| Arquivo | Uso | Classe | Ação |
|---|---|---|---|
| `static/js/turmas/editar.js` (L8,16-17,44,104-111,191), `nova.js` (L16-17,101,182) | campos do formulário de agenda da turma | **JS (H4)** | não tocado |
| `scripts/verificar_h3c_ch.py`, `verificar_h3d_filtros.py`, `verificar_h3e_leitores.py` | ensaios comparativos das etapas (leem escalar como "ANTES" documentado) | ensaio histórico | manter como está; H5 não precisa |
| `scripts/diagnostico_carga_horaria.py:42,87-88` | fallback CSV rotulado (H3e) | fallback | opcional no H5 |

**Conclusão do inventário:** em `app/` restam exatamente **projeção (`sincronizar_projecao_horario`), espelho (`_sincronizar_legado`), fallbacks de legado sem grade e formulários/JS da rota `editar_turma` (H4)** — o conjunto esperado pela spec.

## 7. PASSO 6 — Ensaio de dry-run no scratch Postgres

Banco: `pautaon_ensaio` (local, head `5730d7c594ba` verificada pelo script) — **3 turmas, 5 ofertas reais, 8 linhas de grade**, todas uniformes.

Método: para cada oferta ativa, `editar_oferta` duas vezes (mudança inócua de `programa`; depois só `data_fim`), com o **COMMIT da Session interceptado** (vira `SAVEPOINT` no mesmo cursor) e `rollback` total + `expunge_all` ao final; fotografia comparada: **grade (`turma_curso_horario`), projeção das ofertas e espelho das turmas**.

**Resultado: 0 divergências** — grade resultante == atual em todas as 5 ofertas. Verificação **externa** por SQL confirmou o banco intacto (0 linhas com marcador do ensaio; vigências/programas originais).

Percalço registrado (ver §8): a 1ª tentativa usou `rollback` simples — como `editar_oferta` comita por dentro, os COMMITs **vazaram** para o scratch. O ensaio foi refeito com a interceptação; o scratch foi restaurado ao estado exato (verificação por SQL) antes da nova rodada.

## 8. Desvios

1. **`detalhe.html:254` já estava limpo** — o "or" escalar saiu no H3d (`52ebf9d`); o inventário H3e §9 (iii) estava desatualizado. Sem ação necessária.
2. **Vazamento no 1º ensaio (P6)**: ver §7 — corrigido com interceptação de commit; scratch restaurado (marcador removido; `data_fim` da oferta 12 voltando ao dia único 2026-10-24). Nenhum dado do **principal** foi tocado.
3. **Mudança intencional de comportamento (fora de grade uniforme)**: (i) `editar_oferta` com grade **não uniforme** + formulário atual → `ValueError` e grade **intacta** (antes: regravação uniforme a partir de NULL — o bug que a etapa fecha); (ii) checagem de conflito voltou a ocorrer para oferta 100 % legado ao editar vigência (`agenda=None` → fallback escalar interno) — antes silenciada desde o H3b.
4. **Aviso por dia do H3b preservado**: o segmento cita o par **da outra oferta** no dia em conflito (ex.: `"(Segunda 08:00–10:00)"`), não o da oferta editada.

## 9. Perguntas abertas

1. `dashboard_professor.py` e `ficha_aluno.py` têm reads escalares em **fallbacks de turma sem oferta/vínculo legado** sem `logger.warning` próprio (ramos do H3e, documentados). Aceito como está; se o H5 exigir rastreabilidade total de leitura legado, padronizar com os demais.
2. POST `editar_turma` ainda **escreve** os escalares da Turma diretamente (L1381-1384, fluxo 0/1 oferta). É da Turma (não da oferta) e é o território do **H4** — migrar para `definir_grade` da oferta única + projeção automática; decidir no H4 se o espelho em Turma sobrevive até o H5.
3. `ofertas.html:48-50` (lista de ofertas) mostra a **projeção** da oferta — inofensivo para grades uniformes; com H4, passar a ler `GradeExibicao` como no H3d.
4. CHECK `ck_tch_dia` 0–6 × domínio do serviço 0–5 (herdado do H2) — segue para decisão futura de migration.

## 10. O que NÃO mudou

- **Formulários e JS**: `editar.html`, `ofertas.html`, `editar.js`, `nova.js`, rota `editar_turma` — intocados (H4).
- **`turmas/ofertas.html`** — intocado (H4).
- **Schema**: nenhuma migration; head segue `5730d7c594ba`; nenhuma coluna removida (H5).
- **Escrita**: continua exclusiva de `definir_grade` (grade) + `sincronizar_projecao_horario` (projeção) + `_sincronizar_legado` (espelho) + POST `editar_turma` (escalares da Turma, H4).
- **Comportamento para grades uniformes**: byte a byte idêntico (9 casos de caracterização verdes antes e depois).
- **Testes existentes**: nenhum alterado; **nenhuma sessão do banco principal derrubada**; scripts temporários do ensaio apagados ao final.

**Relatórios anteriores:** `H3e_LeitoresDashboardAlunoConselhoGrade.md` §9 (fonte dos itens (iii)), `H3d_FiltrosListagemGrade.md`, `H3c_Relatorio_final.md`, `H3b_Relatorio_final.md`, `H3a_Leitores_de_agenda.md`, `H2_Relatório_final.md`, `H1_Relatório_final.md`.
