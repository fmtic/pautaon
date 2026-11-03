# AJ6-B7 — Complemento da matriz de rotas do professor

Ramificação: `nova_feature`. Base de partida: HEAD `107a64c` (docs AJ6-B6).
Escopo: fechar as quatro lacunas que o AJ6-B6 deixou em aberto na matriz de
rotas do papel **professor**. Sem migration, sem push, **nenhuma escrita no
banco real** (apenas `SELECT`); testes com SQLite em memória, relógio
congelado e **nomes sintéticos**. Nada foi commitado a partir de arquivos
modificados por terceiros — os commits usam **caminhos explícitos**.

Regra de negócio (responsável, vigente desde o AJ6-B3/B4): o professor só
acessa o inerente às **suas ofertas** (REGRA ÚNICA `ofertas_do_professor` /
`professor_pode_acessar_oferta` / `condicao_professor_da_oferta`) e **nunca**
a ficha do aluno.

---

## 0. Guardas reaplicadas neste trabalho (resumo)

| Arquivo | Mudança | Antes | Depois |
|---|---|---|---|
| `app/registros/servico_social.py` | `excluir_agendamento` recebe guarda por role já existente no blueprint | `responsavel_id` (atributo **inexistente**) → **500** para todo papel fora de (admin, servico_social); 404 mascarava com id ausente | `abort(403)` para fora de (admin, servico_social) — professor negado de forma limpa |
| `app/registros/core.py` | Rota morta `/form` **removida** + irmãs `editar`/`excluir` reencaixadas no painel canônico | renderizava `form.html` **inexistente** (500 até para pedagógico); zero chamadores | rota fora do `url_map`; travada por teste |
| `tests/test_aj6b6_matriz_rotas_professor.py` | Trava do `/form` ajustada de "guarda por role" para "rota removida" | testava 403 da guarda | `test_form_rota_morta_removida` (não volta) |

Entregas: `fix(aj6b7)` e `test(aj6b7)` (hashes ao final) e este relatório.

---

## 1. Varredura de métodos (DELETE / PUT / PATCH)

O inventário dinâmico do AJ6-B6 só chamava GET/POST. Este complemento varre
**todos os métodos** registrados no `url_map`.

**Resultado estático (fonte: `app.url_map` + grep de `methods=` no código):**
existe **exatamente um** endpoint com método fora de GET/POST em toda a
aplicação:

| Endpoint | Rota | Métodos extras | Na allowlist? |
|---|---|---|---|
| `conselho.deletar_periodo_conselho` | `/api/conselho-periodo/<int:conselho_id>` | `DELETE` | não |

Não há **nenhum** endpoint `PUT` ou `PATCH` na aplicação (verificado por varredura
do `url_map` e por `grep` de `methods=[...]` em `app/`). Toda rota de escrita
usa POST (padrão Flask-Login/HTML form deste projeto).

**Resultado dinâmico para o professor** (teste
`test_deletar_periodo_conselho_delete_negado_ao_professor`): com a **janela de
conselho EXISTENTE** na semente (não 404 de recurso ausente), o `DELETE` do
professor recebe **403** — a negação vem de
`_exigir_gestao_periodos_conselho` (`app/conselho.py:81-82`), chamado em
`app/conselho.py:1234`, porque `professor` não está em
`_ROLES_PERIODOS_CONSELHO` (`app/conselho.py:71-76`). A contagem de linhas de
`periodo_conselho` não muda (detector do item 3).

O método exótico fica **travado** contra regressão:
`test_unico_endpoint_fora_de_get_post` falha se qualquer endpoint novo
introduzir DELETE/PUT/PATCH fora do conjunto conhecido (só
`conselho.deletar_periodo_conselho`), forçando decisão consciente.

---

## 2. Semente com recursos reais (fim do 404 que mascarava falta de guarda)

O AJ6-B6 admitiu: vários "403" e "404" vieram de o professor nem chegar à
guarda (recurso inexistente devolvia 404 antes). Este complemento **semeia os
recursos existentes** e repete a varredura; o professor precisa receber **403**
(nunca 404 de ausência, nunca 2xx). A semente B7 (`_seed_b7`) acrescenta à
semente B6: `AgendaServicoSocial` (próprio **e** alheio), `PeriodoConselho`,
`CentroCusto` da unidade e usa as OFERTAS/turmas/alunos já existentes.

**Tabela dos "sem guarda de role" do AJ6-B6 — linha real que nega ao professor,
ou correção aplicada.** Todos validados por
`test_recurso_existente_negado_por_role` sobre **recurso existente**:

| # | Endpoint | Nega em (arquivo:linha) | Mecanismo | B7 (recurso existente) |
|---|---|---|---|---|
| 1 | `auth.trocar_senha` | — | allowlist (senha própria) | legítimo (200) |
| 2 | `conselho.index_conselho` | escopo interno por oferta | allowlist | legítimo |
| 3 | `conselho.informacoes` | `app/conselho.py:1128` → `:81-82` | `_exigir_gestao_periodos_conselho` (`_ROLES_PERIODOS_CONSELHO` s/ professor, `:71-76`) | 403 |
| 4 | `conselho.salvar_periodo_conselho` | `app/conselho.py:1151` → `:81-82` | idem | 403 |
| 5 | `conselho.deletar_periodo_conselho` | `app/conselho.py:1234` → `:81-82` | idem (DELETE) | 403 |
| 6 | `conselho.salvar_fechamento_data` | `app/conselho.py:957-961` | `if role==PROFESSOR: return 403` | 403 |
| 7 | `registros.buscar_instituicoes` | `app/registros/alunos.py:305-311` | tupla de roles s/ professor (fix AJ6-B6) | 403 |
| 8 | `registros.form` | — | **REMOVIDA** (código morto — item 4) | fora do `url_map` |
| 9 | `registros.painel_professor` | `app/registros/core.py:215` | redirect de negação (sem corpo) | 302 |
| 10 | `registros.turma_listar` | `app/registros/turmas.py:726-729` | `turma()` abort (AJ6-B5) | 403 |
| 11 | `registros.turma_ofertas` | `app/registros/turmas.py:2156-2157` | `_turma_para_ofertas` abort | 403 |
| 12 | `registros.turma_oferta_nova` | `app/registros/turmas.py:2156-2157` | idem | 403 |
| 13 | `registros.turma_oferta_editar` | `app/registros/turmas.py:2156-2157` | idem (via `oferta.turma_id`) | 403 |
| 14 | `registros.turma_oferta_principal` | `app/registros/turmas.py:2156-2157` | idem | 403 |
| 15 | `registros.turma_oferta_desativar` | `app/registros/turmas.py:2156-2157` | idem | 403 |
| 16 | `registros.ver_documento_aluno` | `app/registros/alunos.py:1427-1435` | `allowed_roles` em runtime (s/ professor) | 403 |
| 17 | `registros.enviar_modelo_certificado` | `app/registros/periodos.py:635-636` | `_periodo_para_modelo_certificado` (`_ROLES_PERIODO`, `:40`) | 403 |
| 18 | `registros.remover_modelo_certificado` | `app/registros/periodos.py:635-636` | idem | 403 |
| 19 | `registros.arquivo_modelo_certificado` | `app/registros/periodos.py:635-636` | idem | 403 |
| 20 | `relatorios.bi_api_dados` | `app/relatorios/bi_routes.py:93-94` | `ROLES_RELATORIOS` (`shared.py:24`, s/ professor) | 403 |
| 21 | `relatorios.bi_indicador` | `app/relatorios/bi_routes.py:303-304` | idem | 403 |
| 22 | `servico_social.excluir_agendamento` | `app/registros/servico_social.py:134-135` | **CORRIGIDA B7** (ver §2.1) | 403 |

Prioridades do enunciado tratadas em detalhe:

### 2.1 `servico_social.excluir_agendamento` (prioridade) — antes/depois

**Antes** (`app/registros/servico_social.py`, guarda SEC-04 legada):

```python
agendamento = AgendaServicoSocial.query.get_or_404(id)
# SEC-04: Apenas o autor, admin ou servico_social podem excluir
if current_user.role not in (UserRole.ADMIN, UserRole.SERVICO_SOCIAL) \
        and agendamento.responsavel_id != current_user.id:
    abort(403)
```

O atributo `responsavel_id` **não existe** em `AgendaServicoSocial` (a autoria
é `user_id`; ver `app/models/servico_social.py:43`). Consequência real, revelada
ao semear um agendamento existente:

- papel em (admin, servico_social): primeiro operando do `and` é `False` →
  curto-circuita → **permite** (correto);
- **qualquer outro papel** (professor, secretaria, pedagógico, gerência):
  primeiro operando `True` → avalia `agendamento.responsavel_id` →
  **`AttributeError` → 500**, **antes** do `db.session.delete`.

Ou seja: a exceção "autor exclui o próprio" que o SEC-04 pretendia **nunca
funcionou** — todo não-admin/não-social quebrava em 500. O AJ6-B6 viu **404**
porque a semente não tinha agendamento (o `get_or_404` estourava antes da
guarda); o 500 estava mascarado. Não houve exclusão indevida em silêncio —
houve crash. Ainda assim, para a matriz do professor é um **500 = bug**.

**Depois** (guarda por role já existente no blueprint, mesma de `dados_aluno`
`listar_entrevistas`, e mesma semântica 403 de `excluir_atendimento`
`app/registros/atendimentos.py:434-435`):

```python
if current_user.role not in (UserRole.ADMIN, UserRole.SERVICO_SOCIAL):
    abort(403)
agendamento = AgendaServicoSocial.query.get_or_404(id)
```

A negação por role vem **antes** da leitura do recurso: professor → 403 limpo,
sem 500, sem escrever. Testes: `test_recurso_existente_negado_por_role[...
excluir_agendamento-POST-agendamento]` e `[...-agendamento_alheio]`, ambos
também cobertos pelo detector do item 3.

### 2.2 `conselho.deletar_periodo_conselho` (prioridade)

Já tinha guarda de role (via `_exigir_gestao_periodos_conselho`), mas o AJ6-B6
não a exerceu porque o método DELETE estava fora do GET/POST e o id não
existia. B7 semeia a `PeriodoConselho` e prova 403 sobre **recurso existente**
(§1). Sem correção necessária — apenas confirmação.

---

## 3. Detector de escrita (um 3xx não prova negação)

O redirect de negação (302→/painel) e até um 403 não provam, por si, que a
requisição **não escreveu** nada. Este complemento compara, **para cada
requisição do professor fora da allowlist e em qualquer método**, a contagem de
linhas de **todas as tabelas** do `metadata` antes e depois; qualquer movimento
falha.

Implementação: `_contar_tabelas(app)` (`SELECT count(*)` sobre cada tabela,
ignorando `sqlite_master`) e `test_varredura_full_methods_sem_escrita`, que
itera todo o `url_map` como professor e Assert:

- resposta é negação (401/403/404/405 **ou** redirect 3xx), e
- `antes == depois` para **todas** as tabelas.

Com a semente B7, a varredura fecha em **negação sem escrita**. A lista de
redirecionamentos de negação é **fechada e travada** por
`test_redirects_de_negacao_sao_os_conhecidos`: os únicos não-403 fora da
allowlist na semente real são os 302 conhecidos
(`REDIRECIONAM_NEGANDO`: `auth.google_*`, `auth.painel_admin`,
`auth.aguardando_aprovacao`, `main.trocar_unidade`, `registros.painel_professor`,
`servico_social.agendar_entrevista`). Um endpoint novo que passasse a entregar
conteúdo (2xx), dar 5xx ou **mover qualquer linha** quebra a suíte.

---

## 4. Código morto: `registros.form` (/form) — removido

**Prova de ausência de chamadores (grep, quatro superfícies):**

- `url_for('registros.form')` / `url_for('form')`: só as **irmãs internas**
  `registros.editar` e `registros.excluir` (`app/registros/core.py`) — nenhuma
  vinda de template/menu.
- Templates `.html`: **zero** ocorrências de `href`/`action` para `/form` e zero
  `url_for('registros.form'|'form')` (`grep` em `app/templates`, `app/static/js`
  → nada além do próprio módulo `grade_horario.js` que usa `form` como *nome de
  variável* JS, não rota).
- JS: nada aponta para `/form` como URL.
- Menus/navegação: nada.
- Testes: o único era o do AJ6-B6, reescrito aqui.

**O template não existe:** `render_template('form.html', ...)` procura
`form.html` na **raiz** de `templates/`. Só existe `periodos/form.html` e
`alunos/editar.html`/`turmas/editar.html` (`Glob` confirmado); **não há
`templates/form.html`**. Portanto até o pedagógico (único papel liberado pela
guarda do AJ6-B6) caía em **500 TemplateNotFound**. Rota sem chamadores +
template inexistente = **código morto**.

**Ação (não havia chamador externo, então prossegui com a remoção, como pede o
enunciado):**

- Rota `/form` (`def form`) **removida** de `app/registros/core.py`;
- `registros.editar` e `registros.excluir`, que redirecionavam para
  `registros.form`, passaram a redirecionar para `main.painel` (mesmo destino do
  POST de `form` quando ele "funcionava");
- `import json` (usado só pelo corpo removido) retirado; cabeçalho do módulo
  atualizado;
- Trava `test_form_rota_morta_removida` garante que `registros.form` não volta
  ao `url_map`.

Reversão (§6) prova que, com a rota restaurada, a trava e o detector falham.

---

## 5. `historico_aluno` — exposição campo a campo ao professor (só reportar)

Rota `registros.historico_aluno` (`app/registros/alunos.py:1011`) está na
allowlist por decisão vigente do responsável. Renderiza
`app/templates/alunos/historico.html` (133 linhas). O **cabeçalho** e o bloco
**Identificação** misturam dado cadastral com histórico; a **tabela** é
estritamente histórico da oferta. **Nada foi alterado.**

### 5.1 Identificação do aluno (dado CADASTRAL — exposto)

| Campo | Linha do template | Variável | Natureza |
|---|---|---|---|
| Nome completo | `historico.html:46` | `{{ aluno.nome }}` | **cadastral** |
| Nome social | `historico.html:50` | `{{ aluno.nome_social }}` (dentro de `{% if aluno.nome_social %}` em `:48`) | **cadastral** |
| Matrícula | `historico.html:56` | `{{ aluno.matricula }}` | **cadastral** |
| Data de cadastro | `historico.html:60` | `{{ data_cadastro }}` (= `aluno.created_at`, montado em `alunos.py:1179-1181`) | **cadastral** (metadata do cadastro) |
| Unidade do aluno | `historico.html:32` | `{{ aluno.unidade.nome }}` | cadastral (não sensível) |
| Quem emitiu / quando | `historico.html:36,37` | `current_user.name`, `agora` | do próprio professor, não do aluno |
| Logo / nome instituição | `historico.html:27,30,127` | `informacao_padrao.*` | institucional |

### 5.2 Histórico por OFERTA (legítimo da regra por oferta)

Cada linha da tabela vem do dicionário `dados` montado em
`app/registros/alunos.py:1132-1176`, já filtrado por
`ofertas_do_professor` (`alunos.py:1068-1081` — o professor só vê inscrições nas
**suas** ofertas):

| Campo | Linha do template | Variável | Origem |
|---|---|---|---|
| Período letivo | `historico.html:92` | `h.periodo` | `turma.periodo_letivo.nome_exibicao` (`alunos.py:1144`) |
| Datas início/fim | `historico.html:95` | `h.data_inicio`, `h.data_fim` | oferta/turma (`:1150-1155`) |
| Turma | `historico.html:99` | `h.turma` | `turma.nome` (`:1134`) |
| Curso | `historico.html:100` | `h.curso` | `oferta.curso.nome` (`:1135-1138`) |
| Professor | `historico.html:101` | `h.professor` | `oferta.professor`/`turma.professor` (`:1143`) |
| Dias / Horário | `historico.html:102` | `h.dias`, `h.horario` | grade da oferta (`:1145-1149`) |
| Nível | `historico.html:103` | `h.nivel` | `insc.nivel`/`aluno.nivel` (`:1156`) |
| Aulas, Presenças, Faltas, Justificadas, % | `historico.html:104-110` | `h.total_aulas`, `h.presencas`, `h.faltas`, `h.justificadas`, `h.pct_presenca` | estatísticas de frequência (`:1157-1161`) |
| Situação final / Inicial / Percurso | `historico.html:112-114` | `h.situacao_final`, `h.status_inicial`, `h.status_percurso` | conselho por oferta (`:1165-1173`) |
| Vínculo ativo/desligado | `historico.html:116` | `h.ativo` | `insc.ativo` (`:1174`) |

### 5.3 Dados cadastrais/sensíveis que **NÃO** aparecem

Confirmado por leitura do template: **não** são expostos ao professor em
`historico_aluno` — `data_nascimento`/`idade`, endereço (`rua/bairro/cidade`),
contato (`whatsapp`/telefone/e-mail), responsáveis (`nome_mae`/`nome_pai`/
responsável), `documentos_entregues`, laudo/`diversidade_json`,
`informacoes_para_professor`. A ficha 360 continua fora do alcance do professor
(rotas `editar_aluno`/`transferir_aluno`/`ver_documento_aluno`/`dados_aluno`
todas negadas no §2). **Ponto de atenção para reavaliação do responsável:** o
bloco Identificação expõe `nome`, `nome_social` e `matricula` (cadastrais) — é o
único ponto em que esta página toca a ficha; a tabela em si é 100% histórico da
oferta. Não alterado (item 5 é só-reportar).

---

## 6. Verificação final real

### 6.1 Suíte completa em worktree isolado (árvore limpa, sem churn de terceiros)

Medição autoritativa em `git worktree` **detachado no HEAD final** (`1ed4ab5`),
com a pasta `instance/uploads/` recriada (só `instance/.gitkeep` é rastreado no
git; sem ela, `test_nada_gravado_no_disco_na_falha` geraria 1 skip).

**Resultado medido: `1559 passed, 0 failed, 0 skipped`** (895 avisos de
`LegacyAPIWarning`/depreciação, alheios a este trabalho) em 1449.67s. A
recriação de `instance/uploads/` eliminou o único skip possível: a suíte roda
**sem nenhum test pulado** na árvore isolada.

**Nota sobre a árvore de trabalho:** há um **processo/agente concorrente**
editando `d:/pautaon` simultaneamente. Durante esta tarefa o `git status`
cresceu (apareceram, entre outros, `app/templates/conselho/informacoes.html`,
`app/static/css/alunos/historico.css`, `docs/Relatórios/D5_3_relatorio.md`,
`app/models/rss.py`, `app/utils/rss.py`, `app/static/js/utils/`,
`app/templates/utils/`) **sem nenhuma ação deste trabalho**. Na suíte rodada na
**árvore poluída**, três testes falharam — todos por churn de terceiros, não
por este trabalho:

- `test_d5_encerramento::test_informacoes_conta_ofertas_pendentes` — o terceiro
  alterou `conselho/informacoes.html` (sumiu o texto "Ofertas Pendentes");
- `test_h4_leitores_grade_variavel_smoke` e `test_impressao_grade_oferta` — os
  dois arquivos de teste já estavam modificados por terceiros no `git status`
  inicial.

Por isso o número confiável vem do **worktree isolado** (só arquivos
commitados). O churn de terceiros foi deixado **intacto** (nem commitado, nem
revertido).

### 6.2 Reversão dos testes novos (worktree)

Em um worktree no HEAD final, os **arquivos de app do fix** foram revertidos ao
pré-fix (`git checkout 107a64c -- core.py servico_social.py`) mantendo os
testes. Resultado esperado e obtido:

- `test_recurso_existente_negado_por_role[servico_social.excluir_agendamento-POST-agendamento]`
  → **FAIL** (500 no lugar de 403);
- `...[agendamento_alheio]` → **FAIL** (500);
- `test_varredura_full_methods_sem_escrita` → **FAIL**
  (`servico_social.excluir_agendamento POST: status 500`);
- `test_form_rota_morta_removida` → **FAIL** (`registros.form` volta ao mapa).

`4 failed, 26 passed` — prova de que os fixes são necessários. Worktree removido
(`git worktree remove`) ao final.

### 6.3 ruff (F821,F811,F841,F401) nos arquivos tocados

Comando: `ruff check --select F821,F811,F841,F401` sobre os quatro arquivos
alcancados por este trabalho (`app/registros/core.py`,
`app/registros/servico_social.py`, `tests/test_aj6b6_matriz_rotas_professor.py`,
`tests/test_aj6b7_complemento.py`).

Resultado: **`All checks passed!`** — nenhum nome indefinido (F821), nenhuma
redefinição (F811), nenhuma variável local não usada (F841) e nenhum import
não usado (F401), inclusive após a retirada de `import json` do `core.py`.

### 6.4 Contagens do banco real (SELECT puro, antes/depois)

Duas leituras com `psycopg` em `conn.read_only=True` (qualquer escrita estoura).
O AJ6-B7 **não escreve** no banco real — as contagens são **idênticas**.

| Tabela | ANTES | DEPOIS |
|---|---|---|
| unidade | 2 | 2 |
| user | 22 | 22 |
| periodo_letivo | 2 | 2 |
| turma | 3 | 3 |
| curso | 9 | 9 |
| turma_curso | 4 | 4 |
| aluno | 1155 | 1155 |
| inscricoes | 32 | 32 |
| registro_aula | 6 | 6 |
| frequencia | 64 | 64 |
| conselho_classe | 45 | 45 |
| conselho_resposta | 78 | 78 |
| agenda_servico_social | 0 | 0 |
| periodo_conselho | 1 | 1 |
| centro_custo | 6 | 6 |
| modelo_certificado | 0 | 0 |
| log_acao | 1193 | 1193 |
| log_acao max_id | 1523 | 1523 |
| log_acao com rótulo AJ6B7 | 0 | 0 |

**Delta zero em todas as tabelas**; nenhum `log_acao` atribuível a este trabalho
(nenhum rótulo sintético `AJ6B7` no banco real). As sementes dos novos recursos
(`agenda_servico_social`, `periodo_conselho`, `centro_custo`,
`modelo_certificado`) vivem só no SQLite em memória dos testes — por isso o
banco real mostra `agenda_servico_social=0`/`modelo_certificado=0` e
`periodo_conselho=1` **inalterados**.

### 6.5 Commits (caminhos explícitos) e hashes

Commits AJ6-B6 (referência):

- `d4d03d7` fix(aj6b6)
- `bddea97` test(aj6b6)
- `107a64c` docs(aj6b6)

Commits AJ6-B7:

- `b9a6ca5` fix(aj6b7): `app/registros/core.py`,
  `app/registros/servico_social.py`, `tests/test_aj6b6_matriz_rotas_professor.py`
- `1ed4ab5` test(aj6b7): `tests/test_aj6b7_complemento.py`
- docs(aj6b7): este relatório (`docs/Relatórios/AJ6B7_Complemento.md`) —
  hash atribuído no momento deste commit, pai imediato de `1ed4ab5`

`git log --oneline` da série (base → topo):

```
<docs-aj6b7>  docs(aj6b7): relatorio complemento da matriz de rotas do professor
1ed4ab5       test(aj6b7): metodos exoticos, semente real, detector de escrita e travas
b9a6ca5       fix(aj6b7): guarda real em excluir_agendamento e remocao da rota morta /form
107a64c       docs(aj6b6): relatorio da matriz de rotas do professor
bddea97       test(aj6b6): matriz de rotas do professor, allowlist-trava e snapshot golden
d4d03d7       fix(aj6b6): fecha rotas que o professor alcancava por omissao
```

---

## 7. Testes novos (entregável)

`tests/test_aj6b7_complemento.py`:

- `test_unico_endpoint_fora_de_get_post` — inventário de métodos (item 1);
- `test_deletar_periodo_conselho_delete_negado_ao_professor` — DELETE 403 com
  janela existente + detector (itens 1–3);
- `test_recurso_existente_negado_por_role` (parametrizado, 25 casos) — negação
  por role sobre **recurso existente** para as rotas do §2 + detector (itens 2–3);
- `test_varredura_full_methods_sem_escrita` — detector de escrita global
  (item 3);
- `test_redirects_de_negacao_sao_os_conhecidos` — lista fechada de 302 de
  negação (item 3).

Mais a trava ajustada no arquivo do AJ6-B6:
`test_form_rota_morta_removida` (item 4).

Nomes sintéticos, SQLite em memória, `hoje_fixo`, sem dados pessoais.
