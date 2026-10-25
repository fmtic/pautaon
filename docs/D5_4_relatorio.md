# ETAPA D5.4 — Leitores do conselho por oferta

**Escopo:** ficha 360°, histórico do aluno, painel pedagógico (por turma e
resultado do conselho) e certificado passam a ler o conselho pela OFERTA
(`ConselhoClasse.turma_curso_id`). BI (CRU-002/CRU-005) **não** foi alterado.
Sem commit. Nenhum modelo, migration ou rota de escrita tocada.

Fontes: `docs/D5_0_desenho.md` (§1.5, §1.6, D5.4), `D5_1`, `D5_2`, `D5_3`.

---

## 1. Leitura do passo 1 (antes de alterar)

### (a) Histórico do aluno
- `app/registros/alunos.py:830` `historico_aluno`: montava uma linha por
  `Inscricao`, mas o conselho vinha de `ConselhoClasse.query.filter_by(turma_id=…, aluno_id=…, etapa=…)`
  e a frequência de `Frequencia.turma_id` — duas ofertas da mesma turma
  colapsavam no mesmo status; colunas `inicial`/`percurso` não existiam.
- `app/templates/alunos/historico.html:72-121`: tabela única, coluna
  “Situação Final” só com o FINAL.

### (b) Ficha 360° (`app/relatorios/painel_pedagogico/ficha_aluno.py`)
- `:311` `_conselho(aluno_id)` filtrava por `turma_id` (todas as ofertas
  juntas); `:399` `_sinais` ignorava o conselho na prática (nenhum sinal de
  situação final); `:563` `_percurso` trazia a situação de
  `_situacao_por_turma`, que usava `SituacaoFinal.REPROVADO` — valor
  **inexistente** no enum (bug latente).
- `app/templates/relatorios/ficha_aluno.html:453-522`: card do conselho sem
  identificação da oferta.

### (c) Painel por turma (`app/relatorios/painel_pedagogico/conselho.py`)
- `por_turma` agregava por `turma_id` e, ao montar o rótulo da pergunta,
  usava `p.enunciado`: `PerguntaConselho` tem **`texto`** — `AttributeError`
  sempre que havia respostas (bug latente que quebrava a página).
- Consumidores: `turma.py:70-141` e `templates/relatorios/painel_pedagogico.html:456-502`.

### (d) Resultado do conselho (`app/relatorios/conselho.py`)
- Consultava `ConselhoClasse.turma_id.in_(turmas)` e `Inscricao/Frequencia`
  por `turma_id` → uma tabela misturando cursos; sem seletor de oferta.
- `templates/relatorios/resultado_conselho.html` e … **`static/js/relatorios/resultado_conselho.js` não existe**
  no repositório (o template não referencia script algum). Nada a alterar.

### (e) Certificado (`app/registros/periodos.py:521`)
- Loop **por TURMA**; alunos via `Aluno.query.join(Inscricao)` filtrado por
  `Inscricao.turma_id`; conselho FINAL buscado por `(turma_id, aluno_id)`
  (~L551-555) e o ícone Concluído/Pendente vinha do derivado da turma
  (`turma_conselho_concluido`, ~L577).
- `templates/periodos/certificado.html:45-101`: uma linha por item de
  `d.cursos`; `:108-149` páginas de certificado por aluno aprovado.

### (f) BI
- `bi_alunos.alunos_raca_conselho` (`:2517-2563`, CRU-002): junta
  `PerfilDiversidade` por `aluno_id`, agrupa por `raca_cor` e conta
  `count(distinct aluno_id)`.
- `bi_alunos.desempenho_conselho_por_renda` (`:2667-2735`, CRU-005): junta
  `PerfilSocioeconomico`, itera **linhas** `(situacao_final, renda_familiar)`
  e incrementa a faixa — não deduplica aluno.
- O join em `Turma` só ocorre quando há filtro de período/curso/turma/professor;
  ambos filtram por `ConselhoClasse.unidade_id`.

### (g) Outros leitores de `ConselhoClasse` em `app/` (classificação)

| Local | Situação |
|---|---|
| `app/registros/alunos.py:830` (histórico) | **migrado** para o serviço de leitura por oferta |
| `app/relatorios/painel_pedagogico/ficha_aluno.py:316` | **migrado** (filtra `turma_curso_id`; sem oferta → vazio) |
| `app/relatorios/painel_pedagogico/conselho.py:67` | **migrado** (`turma_id.in_` + `turma_curso_id IS NOT NULL`) |
| `app/relatorios/conselho.py:76` | **migrado** (`turma_curso_id.in_(ofertas)`) |
| `app/registros/periodos.py:521` (certificado) | **migrado** (`turma_curso_id` + aluno + etapa) |
| `app/relatorios/bi_alunos.py:2529` / `:2679` | **mantido por decisão** (CRU-002/CRU-005 usam `unidade_id` e, opcionalmente, `turma_id` só para escopo) |
| `app/services/turma_curso.py:207` (`turma_tem_historico`) | **mantido**: a definição é “qualquer linha ligada à turma” (proteção de exclusão), `turma_id` é denormalizado e sempre preenchido; fora do escopo |
| `app/conselho.py` (lançamento/fechamento/avaliação) | rota de **escrita** — fora do escopo da D5.4 |
| `scripts/verificar_onda4_d5.py` | script de verificação: lista os conselhos com `turma_curso_id NULL` |
| `app/registros/turmas.py:1679` | apenas comentário (exclusão lógica) |

---

## 2. Diff por arquivo

### `app/services/conselho_leitura.py` (**novo**, 131 linhas)
- `conselho_do_aluno(aluno_id, turma_curso_id, etapa)` — `None` quando aluno
  ou oferta é `None` (legado nunca é adotado).
- `conselhos_por_oferta(pares_aluno_oferta, etapas=None)` — **uma** consulta
  (`or_` de `and_(aluno_id, turma_curso_id)`); ignora pares com `None`;
  devolve `{(aluno_id, turma_curso_id, etapa): ConselhoClasse}`.
- `mapa_por_aluno_oferta` (filtro por etapa), `ofertas_do_grupo`
  (`joinedload` de curso/turma) e `rotulo_oferta` (“Turma — Curso”).
- Sem qualquer leitura de `Turma.conselho_concluido` ou `Turma.avaliacao_*`.

### `app/registros/alunos.py` (`historico_aluno`)
- Uma linha por **inscrição** (aluno × oferta); conselhos em lote por oferta;
  frequência por `aluno + turma + turma_curso_id` (evita somar frequência de
  outras turmas quando a inscrição é legada); curso/professor/dias/horário/
  datas vêm da oferta com fallback para a turma.
- Novos campos `curso`, `status_inicial`, `status_percurso`.
- `app/templates/alunos/historico.html:113-115`: mostra `I: … · P: …` sob a
  situação final.

### `app/relatorios/painel_pedagogico/ficha_aluno.py`
- `_frequencia(..., oferta=None)`: filtra `turma_curso_id` (aluno **e**
  agregado da turma).
- `_conselho(aluno_id, oferta=None)`: só a oferta; sem oferta → vazio.
- `_sinais`: novo sinal “Situação final na oferta: X” quando a situação mais
  recente (FINAL > PERCURSO > INICIAL) não é favorável.
- `_percurso`: `_situacao_por_oferta(aluno_id, insc.turma_curso_id)` (corrige
  `SituacaoFinal.REPROVADO` → `REPROVADO_POR_FALTA`) e coluna `curso`.
- `_resolver_inscricao`: com 2+ inscrições na MESMA turma honra
  `?oferta_sel=` (rota entrega apenas “a primeira”; ver Pendências).
- `_identidade(..., status)`: status agora vem de
  `services.aluno_status.status_alunos` (ver Decisões).
- `montar`: expõe `oferta` no contexto.
- `app/templates/relatorios/ficha_aluno.html:238,459,575`: curso da oferta na
  identidade, no card do conselho e no percurso.

### `app/relatorios/painel_pedagogico/conselho.py`
- `por_turma` agrega **por oferta** (`(turma_id, turma_curso_id)`), ignora
  `turma_curso_id IS NULL`, carrega ofertas com `joinedload` e devolve
  `{turma_id: {…agregado…, "ofertas": [{turma_curso_id, rotulo, …}]}}`
  (mantendo os agregados no nível da turma para compatibilidade).
- **Correção:** `p.enunciado` → `p.texto`.
- `app/relatorios/painel_pedagogico/turma.py:134-142`: `conselho_ofertas`.
- `app/templates/relatorios/painel_pedagogico.html:456-502`: os dois cards
  (“Conselho de classe” e “Respostas do conselho”) iteram as ofertas com
  rótulo “Turma — Curso”; `:406` passou a usar `vt.semanas_iso` (ver Decisões).

### `app/relatorios/conselho.py` (resultado do conselho)
- `_resolver_ofertas` (padrão M1): turma sem oferta ativa → recusa com aviso;
  1 oferta → usa direto; 2+ → exige `?oferta_sel=` válido (sem escolha, a
  tabela não é preenchida — só o seletor).
- Conselhos: `etapa == "FINAL"` e `turma_curso_id.in_(ofertas)`.
- Aluno, inscrição e frequência carregados **em lote** por oferta
  (`Inscricao.turma_curso_id`, `Frequencia.turma_curso_id`) — sem N+1 e sem
  usar `ConselhoClasse.aluno` (relationship inexistente).
- Isolamento: períodos e turmas filtrados pela unidade da sessão.
- `templates/relatorios/resultado_conselho.html:78-112`: seletor de oferta +
  alerta; `:137-140` rótulo “Ofertas”; `:196-198` curso sob o nome da turma.

### `app/registros/periodos.py` (certificado)
- O loop externo continua **por turma** (é o caminho para enumerar as
  inscrições do período), mas cada linha agora é a INSCRIÇÃO: dedupe por
  `(aluno, oferta)`, conselho FINAL por `(turma_curso_id, aluno_id, "FINAL")`,
  `concluido = bool(oferta.conselho_concluido)` e `curso = oferta.curso or turma.curso`.
- Carga horária: da oferta, com fallback para a da turma.
- **Efeito no documento impresso:** o layout não muda. A tabela ganha uma
  linha por curso cursado (mesmo `rowspan` do aluno/matrícula/botão Emitir) e
  a área de impressão gera **uma página de certificado por oferta aprovada**
  do aluno (`cert-break` já existente) — antes o aluno com dois cursos
  aprovados na mesma turma aparecia uma única vez.

---

## 3. Testes (`tests/test_d5_leitores.py`, 12 novos, um usuário por teste)

1. `test_servico_lote_uma_consulta_por_oferta_ignora_null` — lote devolve
   `(aluno, oferta, etapa)`, ignora pares com `None` e legado NULL; conta
   `SELECT … conselho_classe` = **1** via `before_cursor_execute`;
   `conselho_do_aluno(..., None, ...) is None`.
2. `test_historico_uma_linha_por_inscricao_com_status_da_oferta` — aluno em
   2 ofertas → 2 linhas, cada uma com o FINAL da própria oferta (`Aprovado`
   vs `Evadido`), `I:` presente; legado `Reprovado por Falta` não aparece.
3. `test_historico_frequencia_da_inscricao_nao_mistura_turmas` — frequência
   de outra turma não entra na linha da inscrição.
4. `test_ficha_por_oferta_nao_mistura_conselhos` — `?oferta_sel=` escolhe a
   inscrição; curso e sinal (“Situação final na oferta: Evadido”) vêm só dela.
5. `test_painel_por_turma_agrega_por_oferta_e_usa_texto_da_pergunta` — serviço
   (2 ofertas, `perguntas[…] == texto`) **e** página
   `/relatorios/painel` com respostas registradas (reproduz o bug do
   `enunciado`).
6. `test_painel_ignora_conselho_legado_null`.
7. `test_resultado_2_ofertas_exige_escolha_e_usa_dados_da_oferta` — sem
   `oferta_sel` só o seletor; com cada oferta, apenas os alunos/frequência
   dela (`100.0%` vs `0.0%`).
8. `test_resultado_uma_oferta_usa_direto`.
9. `test_resultado_turma_sem_oferta_ativa_recusa_com_aviso`.
10. `test_certificado_uma_linha_por_inscricao_e_icone_da_oferta` — 2 linhas
    para o aluno em 2 ofertas; ícone de `TurmaCurso.conselho_concluido`
    (oferta 0 concluída, oferta 1 pendente) mesmo com
    `Turma.conselho_concluido = False`.
11. `test_bi_cru002_conta_aluno_distinto_e_cru005_conta_por_situacao` —
    **caracterização**: CRU-002 = 1 (aluno distinto); CRU-005 = 2 na faixa
    (1 aprovado + 1 outro, regra documentada no docstring do teste).
12. `test_isolamento_outra_unidade_nao_le_conselhos_da_unidade_a` —
    histórico 403, ficha 404 e resultado sem linhas com a sessão em outra
    unidade.

Suíte completa: **`349 passed, 78 warnings in 51.31s`** (meta ≥ 337; os 337
anteriores continuam verdes). `ruff` nos arquivos da etapa: só restam os 2
achados pré-existentes (`alunos.py:380` E712, `periodos.py:608` E402).

---

## 4. Decisões tomadas sozinho

1. **Bugs latentes pré-existentes, bloqueantes para os leitores — corrigidos**
   (todos introduzidos antes da D5.4, nenhum altera regra de negócio):
   - `ficha_aluno._identidade` usava `inscricao.status_aluno`, campo
     inexistente → `AttributeError` (a ficha respondia 500 para qualquer aluno
     enturmado). Substituído pelo status derivado de
     `services.aluno_status.status_alunos` (período da turma quando existe).
   - `ficha_aluno._frequencia` fazia `pres_acum += 1` / `falt_acum += 1` em
     variáveis nunca inicializadas → `NameError` com qualquer frequência.
   - `templates/relatorios/painel_pedagogico.html:406` fazia
     `vt.semanas|map(attribute="isoformat")|tojson`; em Jinja 3.1 o `map`
     devolve os *métodos* → `TypeError` (visão por turma sempre 500). Passou a
     usar `vt.semanas_iso`, já preparado por `turma.py`.
   - `relatorios/conselho.py` usava `cons.aluno`, relationship inexistente
     (o `ConselhoClasse` só tem `turma`/`oferta`/`unidade`) → 500 sempre que
     havia conselho FINAL. Agora aluno/inscrição/frequência vêm em lote.
2. **Seletor da ficha dentro do serviço.** `rota.py` (que entrega a inscrição)
   está fora do escopo autorizado; `_resolver_inscricao` lê `?oferta_sel=`
   quando há 2+ inscrições na mesma turma, para a ficha não depender da ordem
   do `first()`. Não cria seletor visual — fica como pendência.
3. **Resultado com 2+ ofertas e sem escolha:** mostrar apenas o seletor (não
   preencher a tabela com todos os cursos), coerente com o padrão M1 dos
   lançamentos.
4. **Histórico:** frequência filtrada também por `turma_id` para que uma
   inscrição legada (`turma_curso_id NULL`) não some a frequência de outras
   turmas; situação de etapa inexistente continua `—`.
5. **Certificado:** mantido o `rowspan` e o agrupamento por aluno; dedupe por
   `(aluno, oferta)` para inscrições duplicadas não repetirem o curso.
6. **BI intocado.** O teste só caracteriza o comportamento atual (CRU-002
   distinto; CRU-005 por linha/situação) — não houve divergência que
   exigisse parar.
7. **Limpeza de lint nos arquivos tocados**: imports órfãos removidos
   (`turma_conselho_concluido` em `periodos.py`, `ConselhoResposta`/
   `PeriodoConselho`/`field`/`classe_tendencia` em `ficha_aluno.py`,
   `date`/`timedelta`/`coorte` em `turma.py`) e blocos reordenados por
   `ruff --fix`; nenhuma mudança de comportamento.

---

## 5. Pendências

1. **Conselhos legados (`turma_curso_id NULL`)** não são exibidos por leitor
   algum (decisão D5.4). A lista — com a classificação “2+ ofertas”, “turma sem
   oferta”, “sem inscrição” e “concluídos/com situação” — está em
   `scripts/verificar_onda4_d5.py` e precisa de resolução manual **antes da
   D5.5**.
2. **Leitores que ainda usam `turma_id` por definição/escopo:**
   `bi_alunos.alunos_raca_conselho` (`:2529-2544`) e
   `bi_alunos.desempenho_conselho_por_renda` (`:2679-2695`) — decisão de não
   alterar o BI nesta etapa; `services/turma_curso.py:207`
   (`turma_tem_historico`) — a checagem é “qualquer linha da turma”;
   `app/conselho.py` — rotas de escrita (D5.2/D5.2b), fora do escopo.
3. **Ficha 360° sem seletor visual de oferta.** O serviço aceita
   `?oferta_sel=`, mas `rota.py:195-219` escolhe a inscrição com `.first()` e o
   template não oferece a escolha. Ajuste depende de liberar
   `app/relatorios/painel_pedagogico/rota.py`.
4. **`Turma.conselho_concluido`** continua sendo escrita como ponte
   (`alternar_conselho`); nenhum leitor desta etapa a consulta. Remoção prevista
   para a D5.5.
5. **`static/js/relatorios/resultado_conselho.js` não existe** no repositório
   (e o template não o referencia). Nada foi criado; se o arquivo for
   reintroduzido, precisa considerar o novo seletor de oferta.
6. **N+1 residual aceitável:** o histórico faz uma consulta de frequência por
   inscrição (poucas por aluno). Os conselhos são sempre em lote.
7. Continua valendo o combinado das etapas anteriores: **não publicar entre a
   D5.2 e a D5.4** (contrato de escrita e leitura só fecha na D5.5).

---

## 6. Resumo do pytest

```
349 passed, 78 warnings in 51.31s
```
