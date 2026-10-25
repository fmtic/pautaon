# D5.2 — Escrita do conselho por oferta (rotas e telas de lançamento, fechamento e avaliação coletiva)

**Status:** concluída. Suíte completa: `320 passed, 65 warnings in 44.74s` (0 falhas; meta ≥297). Sem commit.
**Fontes:** docs/D5_0_desenho.md (§1.2, §2, D5.2), docs/D5_1_relatorio.md. Decisões do responsável: Q1 (pareceres coletivos em `turma_curso.avaliacao_*`), Q4 (situacao_final/proxima_turma_id por oferta), Q5 (respostas tipo TURMA unificadas no JSON por oferta).

> ⚠️ **AVISO DE DEPLOY: NÃO deve haver deploy entre a D5.2 e a D5.4.** A escrita passa a gravar por oferta (`turma_curso_id`, `TurmaCurso.avaliacao_*`, frequência por oferta), mas as LEITURAS (painel/informacoes, BI, relatórios, ficha do aluno, histórico, certificado) ainda consultam os campos legados da turma até D5.3/D5.4. Um deploy no meio da série exibiria dados novos invisíveis nas telas de leitura.

---

## 1. Passo 1 — Leitura prévia (com arquivo:linha)

Números de linha citados desta seção são da versão ANTES da edição (HEAD 44fbef8), salvo indicação.

### (a) app/conselho.py

- **`lancamento_conselho` (L237)** — GET `/conselho/lancamento?turma=&etapa=`: resolvia turma/etapa globais (sem oferta), buscava alunos por `Inscricao.turma_id == turma` (sem distinct por oferta) e fazia *upsert* de um `ConselhoClasse` por (turma, aluno, etapa) SEM `turma_curso_id`. Sem qualquer checagem de unidade (B3/B4 ausente). Renderizava `conselho/lancamento.html` — template que era um *stub*: o loop de alunos estava comentado, logo o formulário de lançamento na prática não emitia linhas de resposta.
- **`salvar_conselho` (L349)** — POST `/conselho/salvar`: buscava `conselhos_turma = ConselhoClasse.query.filter_by(turma_id=..., etapa=...)` (L361) e despachava respostas nos **dois gravadores paralelos**:
  - tipo ALUNO (`resp_<aluno>_<pergunta>`): gravava `ConselhoResposta` por (conselho, aluno, pergunta) — caminho que funcionava;
  - **tipo TURMA (`resp_turma_<pergunta>`, ramificado em `_normalize_conselho_request` L101-104)**: para essas chaves o loop definia `aluno_id = None` e caía em `conselho = conselho_map.get(aluno_id) or conselhos_turma[0]` (L395), inserindo `ConselhoResposta(conselho_id=..., aluno_id=None, ...)`.
  - **CONCLUSÃO sobre o gravador TURMA: ele NUNCA funcionou — e, se funcionasse, FALHARIA; hoje é código morto na prática.** `ConselhoResposta.aluno_id` é `nullable=False` (app/models/conselho.py L233), então qualquer submissão com `resp_turma_*` estouraria `IntegrityError` no `db.session.commit()` e a requisição inteira seria perdida. Na prática o erro nem chega a ocorrer porque nenhum consumidor emite esses campos: o `lancamento.html` (stub) não renderiza o input, e o modal de `turmas/detalhe.html` envia campos `resposta_<pid>`, prefixo que o parser `_normalize` ignora (não bate com `resp_`). Ou seja: gravador paralelo = ramo morto + latentemente quebrado; as respostas tipo TURMA do conselho não tinham destino real algum. Removido conforme Passo 3; agora vivem no JSON da oferta (Q5/D5.0), via `avaliar_turma`.
- **`fechamento_turma` (L427)** — GET `/conselho/fechamento/<turma_id>`: lista de "próximas turmas" **hardcoded** (L443-448: "Vela-Básico", "Canoagem-Básica", "Windsurf-Avançado", "Outro"...) enviada ao template por NOME (sem id); estatísticas de frequência agregavam `Frequencia.query.filter_by(aluno_id, turma_id)` (L452) — mistura ofertas; sem isolamento de unidade; sem noção de oferta.
- **`salvar_fechamento_data` (L477)** — rota `POST /fechamento/<turma_id>/salvar` (L477): **a rota nunca casava com o front-end** — o `salvarFechamento()` do conselho.js (L208-228 do HEAD) fazia `fetch(window.location.pathname + "/salvar")` a partir de `/conselho/fechamento/<id>` → `/conselho/fechamento/<id>/salvar`, que **não existia** (404); e ainda lia `#tabelaDados` (L209), id inexistente no template (a tabela real não tinha esse id) e `<tr>` sem `data-aluno-id`, o que produziria payload vazio mesmo se a rota existisse. Fechamento por JS estava, portanto, duplamente quebrado.
- **`avaliar_turma` (L527)** — GET/POST `/turma/<id>/avaliacao`: gravava/lia o JSON das perguntas tipo TURMA em `Turma.avaliacao_inicial/percurso/final` (ignorando Q1); sem oferta; sem isolamento B4.
- **`index_conselho` (L122) e `informacoes` (L572)** — painéis de leitura: `turmas_pendentes` guiado por `Turma.conselho_concluido`; **não alterados** nesta etapa (ponte da flag da turma mantém compatibilidade; migração de leitura é D5.3/D5.4).

### (b) app/planejamento.py — `alternar_conselho` (L41)

POST `/turma/alternar-conselho/<turma_id>`: toggleava apenas `Turma.conselho_concluido`, com isolamento B4 (`assert_unidade_context`). Não tocava oferta. Passa a alternar `TurmaCurso.conselho_concluido` da oferta e sincronizar o flag da turma como ponte (Passo 6).

### (c) Templates e JS

- `conselho/lancamento.html`: stub (loop de alunos comentado); sem campo de oferta; botão `#modalAvaliacaoTurma` sem handler (morto).
- `conselho/fechamento.html`: tabela sem id estável, `<tr>` sem `data-aluno-id`, selects de situação/ próxima turma enviando rótulos livres (códigos fora do CHECK: `APROVADO` vs valor do enum `Aprovado`; `EMPREGADO` nem existe em `SituacaoFinal` — app/models/enums.py L100-105).
- `conselho/turma_aval.html`: formulário das perguntas tipo TURMA da turma; sem oferta.
- `conselho/painel.html`: leitura por flag da turma — sem alteração (D5.3).
- `turmas/detalhe.html` (L349-374): dropdown "Conselho" sem oferta; modal de avaliação enviava `resposta_<pid>` (ignorado pelo parser).
- `static/js/conselho/conselho.js`: `salvarFechamento()` — ver (a): rota e seletores quebrados.
- `static/js/app.js`: `abrirModalConselho(etapa)` — não levava oferta.

### (d) Padrão de oferta (M1)

- `ofertas_ativas(turma_id)` — app/services/turma_curso.py L46-53: `TurmaCurso.query.filter_by(turma_id, ativo=True).order_by(id)`.
- Seletor `?oferta_sel=` já usado em `ver_turma`/enturmar (app/registros/turmas): 1 oferta → uso direto; 2+ exige escolha; 0 recusa. Adotado aqui.

### (e) Testes existentes

- Nenhum teste exercitava as rotas HTTP de conselho (lançamento/fechamento/avaliação).
- `tests/test_isolamento_unidade_escrita.py::test_admin_alterna_conselho_da_turma_correta` (B4) exercitava `alternar-conselho` numa turma **sem oferta** — cena que a regra nova recusa; atualizado no Passo 8 (ver §4) sem alterar a finalidade (isolamento/admin na turma correta).

---

## 2. O que foi implementado (diff por arquivo)

`git diff --stat` (sem commit): **9 arquivos alterados + 1 novo — 540 inserções, 110 remoções.** Escopo estrito ao autorizado.

### app/conselho.py (+~450 linhas alteradas)
- Helpers novos: `_resolver_oferta_conselho` (L53, M1 0/1/2+), `_escolha_fora_das_ativas` (L74 — id explícito que não bate com as ativas é recusado **mesmo com 1 oferta**), `_normalizar_situacao_final` (L84 — `APROVADO→'Aprovado'` etc. por nome do enum, alias `PARTICIPANTE→'Participação'`, `ValueError` para desconhecidos como `EMPREGADO`).
- `_normalize_conselho_request`: ramo `resp_turma_` REMOVIDO — só respostas tipo ALUNO.
- `lancamento_conselho` (L310): `?oferta_sel=` validado contra `ofertas_ativas`; 0 ofertas → flash claro + volta; 2+ sem escolha → render com seletor e **nada criado/listado**; oferta fora das ativas → recusa sem gravar; alunos via `Inscricao.turma_curso_id == oferta.id` + `ativo` + `distinct`; todo `ConselhoClasse` novo nasce com `turma_curso_id` (e `turma_id` coerente); isolamento B4 adicionado.
- `salvar_conselho` (L465): oferta pelo POST (`turma_curso_id`) validada; conselhos buscados `filter_by(turma_curso_id=oferta.id, etapa=...)`; conjunto de alunos da oferta — resposta de aluno **sem inscrição ativa na oferta é ignorada**; grava apenas `ConselhoResposta` tipo ALUNO (gravador TURMA morto eliminado); redirect preserva `oferta_sel`.
- `fechamento_turma` (L587): por oferta (mesma política M1); lista = alunos da oferta; estatísticas via `Frequencia.turma_curso_id == oferta.id`; próximas turmas agora do **catálogo `OpcaoProximaTurma` (ativos, ordem por nome)** com `value=opt.id`; `data-oferta-id`/`data-aluno-id` na tabela; isolamento B4.
- `salvar_fechamento_data` (L668-670): **rota realinhada ao JS** para `/conselho/fechamento/<turma_id>/salvar`; recebe JSON `{oferta_id, dados:[{aluno_id, situacao, proxima_turma_id}]}`; oferta validada (inativa/outra turma → `success:false`); **validação atômica** (situação inválida → rollback, nada é gravado); cria/atualiza `ConselhoClasse` etapa FINAL por aluno DA OFERTA com `situacao_final` normalizada, `proxima_turma_id` (id do catálogo) e `concluido=True`; isolamento B4.
- `avaliar_turma` (L761): lê/grava o JSON tipo TURMA (mesma codificação `_build_turma_avaliacao_payload`) em **`TurmaCurso.avaliacao_inicial/percurso/final` da oferta** — nunca mais `Turma.avaliacao_*`; oferta via `oferta_sel`/`turma_curso_id` com política M1; mapa etapa→campo mantido LOCAL (uso de `ETAPA_PARA_CAMPO_AVALIACAO` fica para D5.5); isolamento B4; link/título viram "Avaliação da oferta".
- Nota de cabeçalho D5.2 registrada no módulo.

### app/planejamento.py (+40)
- `alternar_conselho` (L42): valida oferta contra a turma (M1 + id explícito inválido recusado); alterna `TurmaCurso.conselho_concluido` (L86); **sincroniza** `Turma.conselho_concluido = all(ofertas ativas concluídas)` (L90) — ponte até D5.3; turma sem oferta ativa → flash + redirect; isolamento B4 preservado.

### Templates
- `conselho/lancamento.html` (+38/-…): seletor `oferta_sel` (2+ ofertas), hidden `etapa` no GET e `turma_curso_id` no POST, card "Curso:" da oferta, botão morto `#modalAvaliacaoTurma` substituído por link "Ver Avaliação da Oferta" (com `oferta_sel` quando há oferta).
- `conselho/fechamento.html` (+35): seletor de oferta (cena exigir_escolha), `#tabelaFechamento` com `data-oferta-id`, `<tr data-aluno-id>`, select de próxima turma preenchido pelo catálogo (`value=opt.id` + opção "—").
- `conselho/turma_aval.html` (+33): títulos "Avaliação Coletiva da Oferta", seletor de oferta, hidden `turma_curso_id`, onchange também para `oferta_sel`.
- `turmas/detalhe.html` (+15): links do dropdown de conselho com `&oferta_sel=<id>` (com 1 oferta o link pode omitir — usado `oferta_sel or ofertas[0] if única`); modal com hidden `turma_curso_id` `#inputOfertaConselho`.
- `conselho/painel.html`: **inalterado** (leitura é D5.3).

### JS
- `static/js/conselho/conselho.js` (+16/-…): `salvarFechamento()` passa a ler `#tabelaFechamento`/`data-oferta-id`/`tr[data-aluno-id]` e postar em `window.location.pathname + "/salvar"` com `oferta_id` no body — consertando o 404/`#tabelaDados` legado.
- `static/js/app.js` (+9): `abrirModalConselho(etapa, ofertaId)` preenche `#inputOfertaConselho`.

---

## 3. Testes

### Novo: tests/test_conselho_oferta.py — 23 testes (um usuário por teste; um usuário por arquivo-teste é a regra; cada teste cria seu próprio setup)
Sem oferta recusa (lancamento/avaliar/alternar); oferta única usa direto e vincula `turma_curso_id`; 2+ exigem escolha (GET sem escolha não cria nada; com `oferta_sel` cria na oferta escolhida); oferta de outra turma recusada sem gravar; salvar recusa oferta inativa ("1+1i"); salvar grava só ALUNO e ignora chaves TURMA (**prova da remoção do gravador**: 1 `ConselhoResposta`, nada em `resp_turma_*`); aluno sem inscrição na oferta é ignorado; aluno em 2 ofertas → 2 conselhos independentes; linha legada NULL intocada pelo fluxo por oferta; avaliação grava `TurmaCurso.avaliacao_inicial` (JSON por pergunta) e não toca `Turma.avaliacao_*`; avaliação 2 ofertas sem escolha não grava; fechamento lista só alunos da oferta + catálogo por id + `data-oferta-id`; frequência do fechamento filtrada por oferta (100% na oferta A, 0% na B para o mesmo aluno); fechar/salvar grava `situacao_final='Aprovado'`/`proxima_turma_id`/`concluido` na oferta correta e ignora aluno de fora; situação `EMPREGADO` → recusa atômica (zero linhas); oferta inativa no salvar → recusa; `alternar_conselho` 1 oferta sincroniza nos dois sentidos; 2 ofertas — turma só conclui quando todas; alternar sem escolha/sem oferta recusa; isolamento: outra unidade → 403 no lançamento; admin sem unidade (Visão Global) → 403 em lançamento GET, alternar POST e fechar/salvar POST.

### Atualizado: tests/test_isolamento_unidade_escrita.py (+14)
`test_admin_alterna_conselho_da_turma_correta`: deu à turma a oferta única que o fluxo novo exige (semente via `nova_oferta`) e passou a assertar o flag da OFERTA **e** da turma. Finalidade B4 (admin alternando a turma correta da própria unidade) intacta — apenas a assinatura do cenário acompanhou a rota. Sem conflito de finalidade; não foi necessário parar.

### Suíte completa
```
320 passed, 65 warnings in 44.74s
```

---

## 4. Decisões tomadas autonomamente (fora do literal do enunciado)

1. **Rota do salvar-fechamento movida para `/conselho/fechamento/<turma_id>/salvar`** — único consumidor era o JS, que já apontava para ela (a antiga `/fechamento/...` dava 404). Realinhar ao JS foi a correção de menor risco; nenhum teste/usuário usava a rota morta.
2. **Normalização server-side das situações (`_normalizar_situacao_final`) em vez de mexer no `<select>` do template** — o template enviava `APROVADO`/`EMPREGADO` incompatíveis com o enum/CHECK. Traduzir os códigos válidos preserva a tela (Passo 7 manda não mudar o visual); `EMPREGADO` não tem correspondente no enum → recusa atômica com mensagem, registrada como pendência (ver §5).
3. **Recusa atômica no fechar/salvar** (valida todos os itens antes de mutar qualquer um) — evita estado parcial se um único registro vier inválido.
4. **Catálogo de próximas turmas por ID no `<option>` + opção vazia "—"** — `proxima_turma_id` é FK; gravar nome seria impossível de manter coerente.
5. **`_escolha_fora_das_ativas` recusa id explícito inválido mesmo com 1 oferta** — com uma única ativa o normal é ignorar o parâmetro, mas um id enviado que não bate com a ativa é sinal de manipulação/link velho de outra turma: recusa com flash em vez de redirecionar em silêncio.
6. **Adaptação do teste B4 de `alternar-conselho`** (ver §3) em vez de removê-lo ou recusar a mudança — o enunciado autoriza ajuste de testes "cujas rotas mudaram de parâmetro, sem alterar a finalidade".
7. **`db.session.expire_all()` após criar os conselhos no lançamento** — garante que o `conselho_id` de referência relê a linha já persistida (evita SQLAlchemy identity-map velho no mesmo contexto de request do harness de testes).
8. **Link "Ver Avaliação da Oferta"** no lugar do botão morto `#modalAvaliacaoTurma` — o link era inerte (sem handler); virou navegação real para `avaliar_turma` com `oferta_sel`, atendendo ao "o link vira 'Avaliação da oferta'" do Passo 4 sem redesenhar a tela.

---

## 5. Pendências (para D5.3/D5.4/D5.5)

- **Não há deploy entre D5.2 e D5.4** (ver aviso no topo): leituras antigas × escritas novas.
- D5.3/D5.4 — leituras ainda legadas: `index_conselho`/`painel.html`/`informacoes` (flag da turma), BI, relatórios, ficha do aluno, histórico, certificado, `calcular_metricas_conselho` (usa conselho sem `turma_curso_id`), `excluir_turma`/períodos — todos fora do escopo desta etapa.
- **`EMPREGADO`** continua no `<select>` do fechamento como opção que o servidor recusa; decidir em D5.3 se vira situação válida, mapeia para outra ou sai do template.
- **CSRF no fetch do fechar/salvar**: o POST JSON do conselho.js não envia token e a rota não é exempt — problema legado (a rota antiga estava morta, então nunca apareceu); testar no fluxo real (navegador) na D5.3.
- **`ETAPA_PARA_CAMPO_AVALIACAO`** (enums) não foi usado — mapa etapa→campo continua local em `avaliar_turma`, conforme ordem do Passo 4; adoção é D5.5.
- Retirar a ponte `Turma.conselho_concluido` quando as leituras migrarem (D5.3).
