# AJ20 — ConselhoClasse só nasce no POST (GET do lançamento não escreve mais)

**Data:** 12/11/2026 · **Branch:** `aj20-conselho-lazy` · **Migration:** nenhuma

## Problema

`GET /conselho/lancamento` (`lancamento_conselho`) iterava os alunos ativos da
oferta/etapa e, para cada um sem `ConselhoClasse`, criava a linha e dava
`commit` — **GET com efeito colateral**. Consequências:

- Casca vazia por aluno a cada abertura (origem das 15 linhas vazias de
  produção, etapa FINAL, confirmadas em 11/11/2026).
- Duas aberturas simultâneas podiam estourar `uix_conselho_oferta`
  (`turma_curso_id + aluno_id + etapa`) com 500.
- Ruído em contagens de histórico e auditoria.

## Item 1 — Mapeamento (quem cria / quem assume a linha)

| Ponto | Papel | Antes do AJ20 | Comportamento com linha ausente (depois) |
|---|---|---|---|
| `conselho.py::lancamento_conselho` (GET) | criava casca + commit | 1 linha por aluno ativo da oferta/etapa | **não escreve**; `conselhos_etapa` vazio = formulário em branco; `conselho=None` (variável não usada pelo template) |
| `conselho.py::salvar_conselho` (POST individual) | criava linha sob demanda | `ConselhoClasse(...)` direto | `get_or_create_conselho` com **savepoint**; cria só quando há resposta ou observação com conteúdo |
| `conselho.py::salvar_fechamento_data` (POST fechamento) | criava linha FINAL por aluno | `ConselhoClasse(...)` direto | mesmo helper, etapa FINAL, `data_inicio`/`instrutor_id` do fechamento |
| `conselho_leitura.conselho_do_aluno` / `conselhos_por_oferta` | leitores (histórico, BI, ficha via serviços) | devolviam a casca como se fosse conselho | filtram `~cond_conselho_sem_conteudo()` → casca ≡ ausente |
| `services/turma_curso.py` — `oferta_tem_lancamentos`, `ofertas_com_lancamentos`, guarda de exclusão de turma | contagens/guardas de histórico | casca contava como lançamento | casca não conta (`~cond_conselho_sem_conteudo()`) |
| `relatorios/painel_pedagogico/conselho.py::por_turma` | painel pedagógico por turma/oferta | casca entrava como "total" da etapa | casca excluída da consulta |
| `relatorios/conselho.py` (resultado do conselho, etapa FINAL) | relatório | casca FINAL entrava na lista | casca FINAL excluída |
| `relatorios/painel_pedagogico/ficha_aluno.py::_conselho` | ficha 360° | casca renderizava etapa "em andamento" vazia | **sem filtro**: saída idêntica — `concluido=False`, `data=None`, `situacao_final=None`, `observacao=None` produzem o mesmo HTML da linha ausente |
| `registros/periodos.py` (documento do período / certificado) | leitor FINAL por oferta | `situacao_final=None` → não aprovado | idêntico com linha ausente (`conselho=None` → `situacao=None` → não aprovado) |
| `relatorios/bi_alunos.py` CRU-002/CRU-005 | BI | já exigiam `respostas.any()` / `situacao_final IS NOT NULL` | casca nunca contava — inalterado |
| `avaliar_turma` (avaliação coletiva) | escreve em `TurmaCurso.avaliacao_*` | não cria `ConselhoClasse` | inalterado |

**"Casca"** = `cond_conselho_sem_conteudo()` (`app/services/conselho_leitura.py`):
`concluido=False` **e** `situacao_final IS NULL` **e** `observacao` NULL/vazia
**e** nenhuma `ConselhoResposta` filha. Qualquer sinal de conteúdo faz a linha
contar como real — nada é apagado nem migrado.

## Implementação

- **`get_or_create_conselho`** (`app/conselho.py`): SELECT → se ausente,
  `db.session.begin_nested()` (savepoint) + INSERT + `flush`. `IntegrityError`
  na UNIQUE `uix_conselho_oferta` desfaz só o INSERT e relê a linha vencedora
  — corrida nunca gera 500 (SQLite dos testes e PostgreSQL).
- **GET**: removidos o loop de criação e o `commit`; os mapas de respostas e
  observações simplesmente não têm entrada para alunos sem linha.
- **POST individual**: resposta (`resp_*`) sempre cria a linha do aluno (é
  conteúdo); observação só cria quando o texto tem conteúdo. Datas de
  início/fim do formulário continuam sendo aplicadas às linhas existentes.
- **Fechamento**: cada item validado cria/atualiza a linha FINAL com
  `situacao_final`, `proxima_turma_id`, `concluido=True`, `data_fim` — como
  antes, agora via helper.
- **Leitores**: guarda `~cond_conselho_sem_conteudo()` aplicada em
  `conselho_leitura` (2 funções), `turma_curso` (3 pontos) e
  `painel_pedagogico/conselho.py` e `relatorios/conselho.py`. Casca e linha
  ausente ficam **idênticas** em todos os leitores mapeados.

## Compatibilidade

- SQLite (testes): `begin_nested` = SAVEPOINT real; corrida simulada coberta.
- PostgreSQL: mesmo mecanismo; `IntegrityError` capturado dentro do savepoint
  não envenena a transação externa.
- Sem migration: schema, constraints e as 15 cascas de produção intactas —
  elas passam a ser tratadas como "sem conselho" pelos leitores.

## Testes

`tests/test_aj20_conselho_lazy.py` — 13 testes:

- **(a)** GET não escreve: contagem de `ConselhoClasse` idêntica antes/depois,
  `db.session.new`/`dirty` vazios, duas aberturas seguidas sem erro.
- **(b)** POST sem conteúdo não cria linha.
- **(c)** POST com resposta, com observação e fechamento criam exatamente 1
  linha por aluno/etapa/oferta.
- **(d)** corrida simulada (linha criada entre SELECT e INSERT via patch de
  `_buscar_conselho`) não gera 500 e grava na linha existente.
- **(e)** casca pré-existente funciona como antes (edição normal).
- **(f)** leitores com linha ausente ≡ casca (ficha, painel, contagens,
  resultado).
- **(g)** perfis e 403 inalterados.
- **(h)** número de queries do GET não aumenta (sem N+1 novo).

Testes legados que assumiam "GET cria casca" foram ajustados para a semântica
lazy (`test_conselho_oferta.py`, `test_conselho_professor.py`,
`test_aj19_observacao_aluno.py`, `test_turma_curso_exclusao.py` — a fixture de
histórico passou a semear conselho **com conteúdo**, já que casca não é mais
histórico).

## Verificação

- Direcionados (AJ20 + exclusão + D5 + L4.1 + painel + BI + conselho):
  **94 passed**.
- Suíte completa: **1774 passed, 0 failed** (18min).
- Goldens AJ7D: sem diff fora da região já alterada pelo AJ19 (a tela de
  lançamento não mudou visualmente — só deixou de gravar no GET).
