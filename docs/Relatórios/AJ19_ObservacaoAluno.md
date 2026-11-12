# AJ19 — Observação única por aluno no conselho individual

**Branch:** `aj19-observacao-aluno` (a partir de `nova_feature`, após AJ18-G mergeado) · **Data:** 12/11/2026 · **Sem push, sem merge** · **Sem migration**.

**Escopo:** o lançamento individual do conselho (`/conselho/lancamento` + `/conselho/salvar`) deixa de ter um textarea de observação **por pergunta** e passa a ter **UM** campo "Observações e informações adicionais" por aluno, gravado em `conselho_classe.observacao` (uma observação por aluno × etapa × oferta, dentro da UNIQUE `uix_conselho_oferta`). `conselho_resposta.observacao` deixa de ser lida e escrita — a coluna permanece no schema, sem uso e sem migration.

**Fatos de produção confirmados (11/11/2026):** `conselho_resposta` = 0 linhas e 0 observações; `turma_curso.avaliacao_*` = 0; `conselho_classe` tem 15 linhas vazias ("casca" criada ao abrir o lançamento, etapa FINAL) e **já possuía** a coluna `observacao` (text). Não havia legado a preservar.

---

## 1. Investigação: o que `ConselhoClasse.observacao` significava antes

Varredura em `nova_feature` (`git grep observacao` em `app/` e `app/templates/`):

- **Nenhum escritor e nenhum leitor** de `ConselhoClasse.observacao` existia no código de aplicação — a coluna está no modelo desde a criação da tabela (§7.24), mas nenhuma rota, serviço, template ou relatório a usava. A única exceção é o script manual `scripts/semear_roteiro_manual.py`, que já gravava `conselho.observacao = parecer` com o **mesmo grão** do AJ19 (uma observação por linha aluno/etapa/oferta) — semântica compatível, sem ajuste necessário.
- O uso real de observação no conselho era **outro**: `ConselhoResposta.observacao` (texto livre por aluno × pergunta), escrito e lido apenas por `salvar_conselho`/`lancamento_conselho` (`app/conselho.py`) e devolvido à ficha 360° por `app/relatorios/painel_pedagogico/ficha_aluno.py` (`inicial_obs`/`percurso_obs`).
- Detalhe: `inicial_obs`/`percurso_obs` eram montados no dicionário da ficha, mas **nenhum template os exibia** — ou seja, a observação por pergunta era gravada e devolvida à ficha sem nunca aparecer em tela.

**Conclusão:** `ConselhoClasse.observacao` era uma coluna morta com semântica livre ("observação do conselho daquela linha"), exatamente o grão pedido (aluno/etapa/oferta). Reutilizá-la não sobrescrevia nenhum comportamento existente — decisão registrada aqui conforme pedido do item 1.

## 2. Leitores de observação do conselho — antes e depois

| Leitor | Antes (AJ19-) | Depois (AJ19) |
|---|---|---|
| `conselho/lancamento.html` | textarea `obs_<aluno>_<pergunta>` por pergunta, preenchido de `observacoes_map` (`ConselhoResposta.observacao`) | UM `textarea obs_<aluno>` no fim do card, mesmo estilo de `turma_aval.html` (`obs_turma`); mapa chave = `aluno_id` vindo de `ConselhoClasse.observacao` |
| `salvar_conselho` (`app/conselho.py`) | lia/gravava `ConselhoResposta.observacao` por par aluno×pergunta | grava `ConselhoClasse.observacao`; `ConselhoResposta.observacao` não é mais tocada (nem na criação da linha) |
| Ficha 360° (`app/relatorios/painel_pedagogico/ficha_aluno.py` + `ficha_aluno.html`) | `inicial_obs`/`percurso_obs` por pergunta no dict (nunca renderizados) | `observacao` geral **por etapa** no dict e exibida no template (`pt-obs-conselho`, escapada pelo Jinja) |
| Fechamento (`fechamento.html`, `salvar_fechamento`) | não lia observação | sem alteração — continua sem exibir |
| Painel do conselho (`painel.html`), resultado (`resultado_conselho.html`), impressão (`imprimir_formulario.html`), certificado, BI (`bi_alunos.py`), `conselho_leitura.py` | não liam observação | sem alteração — nenhum exibia observação, então nenhum precisou de ajuste |

O único leitor que **precisava** exibir a observação geral era a ficha 360° (única tela que já recebia o dado); ela foi ajustada. As demais telas nunca mostraram observação do conselho — mantido o comportamento.

## 3. Implementação

### Template (`app/templates/conselho/lancamento.html`)

- Removido o `<textarea name="obs_<aluno>_<pergunta>">` de dentro do loop de perguntas.
- Adicionado, no fim do card de cada aluno (depois do loop de perguntas), bloco idêntico em estilo ao da avaliação coletiva (`turma_aval.html`):

```html
<div class="p-3 bg-white rounded border shadow-sm mt-2">
    <label class="fw-bold mb-2 conselho-pergunta text-uppercase" for="obs_{{ aluno.id }}">
        Observações e informações adicionais
    </label>
    <textarea name="obs_{{ aluno.id }}" id="obs_{{ aluno.id }}"
        class="form-control" rows="4" maxlength="5000"
        placeholder="Digite observações gerais sobre o aluno...">{{ observacoes.get(aluno.id, '') }}</textarea>
</div>
```

`maxlength="5000"` é conveniência de UI; a validação autoritativa é no servidor.

### Normalização (`_normalize_conselho_request`)

- `obs_<aluno_id>` (sufixo integro) → `normalized["observacoes"][aluno_id] = texto.strip()`.
- O parser antigo `obs_<aluno>_<pergunta>` / `observacao_<aluno>_<pergunta>` foi removido — chaves no formato velho são ignoradas.

### Gravação (`salvar_conselho`)

1. **Validação antes de qualquer mutação:** se qualquer `obs_<aluno>` exceder 5000 caracteres, o POST inteiro é recusado (flash de aviso, redirect) — nem respostas nem observações são gravadas.
2. Loop de respostas inalterado, exceto: não lê nem grava `ConselhoResposta.observacao` (a coluna fica `NULL` em linhas novas).
3. Loop novo de observações: para cada `aluno_id` com `obs_` presente no POST, localiza a `ConselhoClasse` em `conselho_map` (aluno × etapa × oferta). Se não existir linha e o texto tiver conteúdo, cria a casca já com `turma_curso_id`/`etapa`/`unidade_id` (mesma regra D5.2 do loop de respostas). `NULL` e `''` contam como o mesmo vazio (`_valor_conselho_mudou`).
4. Auditoria (AJ7-A): mudança de observação entra em `alteracoes[aluno]` com `nomes += {"observacao"}` e detalhe fixo `"observacao: texto alterado"` — **o conteúdo nunca vai ao log**. A observação gravada conta como conteúdo do aluno (`havia_conteudo`), então editar só a observação de um aluno "vazio" gera log de **primeiro preenchimento**, não de alteração.
5. `chaves` da auditoria de respostas passou a ser só `normalized["respostas"]` (observação tem ciclo próprio).

### Leitura (GET `/conselho/lancamento`)

- `observacoes_map = {c.aluno_id: (c.observacao or '') for c in conselhos_etapa}` — chave única por aluno; `or ''` evita o `None` que o Jinja imprimiria (mesma defesa do AJ7-B).

### Perfis

Inalterados: `_exigir_gravacao_conselho()` + `professor_pode_acessar_oferta` + `assert_unidade_context` — admin, pedagógico e professor da oferta gravam; secretaria/gerência/serviço social recebem 403 (coberto por T5 do `test_aj19`).

## 4. Item 6 — o GET do lançamento cria `ConselhoClasse` por aluno (caracterização, sem alteração)

**Onde:** `app/conselho.py`, `lancamento_conselho()` (GET `/conselho/lancamento`), logo após resolver a oferta — o laço `for aluno in alunos:` faz `ConselhoClasse.query.filter_by(turma_curso_id=oferta.id, aluno_id=aluno.id, etapa=etapa).first()` e, se não existir, `db.session.add(ConselhoClasse(...))` + `db.session.commit()`. Ou seja: **basta abrir a tela** para criar uma linha por aluno ativo da oferta naquela etapa — foi assim que nasceram as 15 cascas vazias em produção (etapa FINAL).

**Por quê (hipótese de desenho):** `conselho_resposta.conselho_id` é `NOT NULL` com FK para `conselho_classe`; a casca garante que exista um pai por (aluno, etapa, oferta) antes de qualquer resposta, e a UNIQUE `uix_conselho_oferta` faz o "primeiro que chega cria" ser idempotente. Também dá à tela um `conselho` de referência (`conselhos_etapa[0]`) para datas/etc.

**Riscos:**

- **GET com efeito colateral:** criar/commitar em GET viola a semântica HTTP — prefetch de browser, retry, crawler ou duplo clique podem disparar escritas; não há CSRF porque "não deveria" escrever.
- **Linhas-fantasma:** aluno desenturmado depois mantém a casca; contagens de "conselho existe" e o `havia_conteudo`/auditoria passam a ver linhas que nunca tiveram conteúdo.
- **Ruído de auditoria:** `ConselhoClasse` tem `AuditoriaMixin` — cada criação vira `updated_by/at` de quem apenas *abriu* a tela.
- **Acoplamento:** o AJ19 aumenta o custo da casca, porque agora ela também é a portadora da observação — uma linha criada por acidente já é "o lugar" onde a observação vai morar.

**Não alterado nesta etapa** (conforme instrução). Alternativas futuras: criação preguiçosa só no POST (o `salvar_conselho` já sabe criar a linha quando há conteúdo), ou criação explícita por ação do usuário. O comportamento está **caracterizado** em `test_t10` do `tests/test_aj19_observacao_aluno.py`.

## 5. Testes

`tests/test_aj19_observacao_aluno.py` (novo, 408 linhas, 10 testes):

- **T1** GET: exatamente um `obs_<aluno>` por aluno, nenhum `obs_<aluno>_<pergunta>`, rótulo e `maxlength=5000` presentes.
- **T2** POST grava em `ConselhoClasse.observacao` e o GET devolve por aluno; `ConselhoResposta.observacao` permanece `NULL`.
- **T3** aluno sem observação fica vazio e não contamina o outro.
- **T4** isolamento por etapa (INICIAL × FINAL) e por oferta (2 ofertas, 1 aluno em cada).
- **T5** perfis: admin/pedagógico/professor gravam; secretaria/gerência/serviço social → 403 sem gravar.
- **T6** limite: 5000 caracteres aceita; 5001 recusa o POST inteiro sem gravar nada (respostas inclusive).
- **T7** escape: `<script>` na observação sai escapado no lançamento e na ficha 360°.
- **T8** ficha 360° exibe a observação geral por etapa.
- **T9** `ConselhoResposta.observacao` permanece `NULL` após gravações.
- **T10** caracterização do GET criando as cascas (item 6).

Testes existentes ajustados ao novo contrato:

- `test_aj2_conselho_lancamento.py` — helpers e asserts migrados de `obs_<a>_<p>`/`ConselhoResposta.observacao` para `obs_<a>`/`ConselhoClasse.observacao`.
- `test_aj7a_conselho_auditoria.py` — seed passa a gravar a observação em `ConselhoClasse`; asserts de log atualizados (o listener genérico de `AuditoriaMixin` agora também registra a `ConselhoClasse` dirty pela observação — comportamento correto e coberto).
- `test_aj7b_conselho_none.py` — mesmos ajustes de campo.
- `test_aj7d_gravacao_conselho.py` — **goldens do AJ7D**: somente os hashes das telas **individuais** mudaram (admin/pedagógico/professor); as **coletivas** permaneceram idênticas — diff confinado à região da observação.

**Resultados:** direcionados (AJ19 + AJ2 + AJ7-A + AJ7-B + AJ7-D): **79 passed**. Suíte completa: **1758 passed, 0 failed** (22min25s). `ruff check` limpo no arquivo de teste novo; `app/conselho.py` mantém apenas os E712 pré-existentes do codebase (nenhum introduzido).

## 6. Documentação

- `app/models/MER.md`: §7.24 (`conselho_classe.observacao` descrita), §7.25 (`conselho_resposta.observacao` marcada como sem uso, coluna preservada), §8.2 (nova regra AJ19), cabeçalho de complemento e "Última atualização".
- `backlog_desenvolvimento.md`: nova entrada do dia.
- **Sem migration** — nenhuma revisão Alembic criada; `conselho_resposta.observacao` e `conselho_classe.observacao` já existem.

## 7. Pendências / decisões em aberto

- **Item 6 (GET que cria linhas)** ficou como caracterização — decidir depois se vale virar tarefa própria (criação preguiçosa no POST).
- `conselho_resposta.observacao` permanece no schema sem uso; remoção física fica para uma etapa futura com dump autêntico (mesmo critério dos resíduos legados do §8.2).
- Fechamento/painel/resultado/certificado seguem **sem** exibir a observação geral — se o produto quiser a observação do aluno na ata de fechamento ou no certificado, é decisão nova.
