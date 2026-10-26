# Relatório — Etapa M1.1: Enturmação por oferta

Data: 24/10/2026 · Atualizado após tornar obrigatório o vínculo do aluno com uma oferta.

## Estado atual

O vínculo acadêmico efetivo é a inscrição do aluno em uma oferta (`Inscricao.turma_curso_id`). Uma turma pode agrupar várias ofertas e o mesmo aluno pode ter uma inscrição ativa em cada uma. Não há mais adoção de inscrição sem oferta.

### Ajustes posteriores à M1.1

- `turma_curso_id` passou a ser obrigatório no modelo e no banco. A migration `c3d4e5f6a7b8_inscricao_exige_oferta.py` também cria unicidade parcial para impedir duas inscrições ativas do mesmo aluno na mesma oferta.
- A enturmação cria o vínculo na oferta escolhida; a duplicidade é verificada por aluno e oferta. A consulta da lista de disponíveis compara o ID da oferta com `=` (corrigindo o SQL PostgreSQL inválido com `IS`).
- A ficha mostra cada oferta do aluno uma só vez por turma, com ações próprias para transferir ou desenturmar aquele vínculo. A contagem da turma considera pessoas, não linhas de inscrição.
- A transferência exige a oferta de origem e a oferta de destino. Ela encerra somente o vínculo escolhido e cria a inscrição na oferta de destino. Quando a origem não vem informada pela tela geral de alunos, o sistema permite selecioná-la.
- A desenturmação remove ou inativa somente a inscrição da oferta selecionada; inscrições do aluno em outras ofertas permanecem ativas.
- A criação de uma nova oferta deixou de tentar adotar inscrições sem oferta.

### Base de teste e migration

Foi removida a turma `Teste de turma novo centro de custo` (id 6) e suas 7 inscrições. Antes da exclusão, confirmei que a turma não tinha frequências, diários, registros de conselho ou transferências. Não havia outras inscrições com `turma_curso_id` nulo.

A migration foi aplicada à base PostgreSQL `pautaon`. Conferências após a migração: revisão `c3d4e5f6a7b8`, zero inscrições sem oferta, zero duplicatas ativas por aluno/oferta e turma de teste ausente.

### Verificações desta atualização

- `git diff --check` → sem erros.
- AST dos arquivos Python alterados → sintaxe válida.
- Templates de transferência, seleção de oferta e ficha da turma → compilam.
- **Suíte de testes não executada nesta atualização.** Os resultados de testes registrados na seção histórica abaixo são da versão anterior à coluna obrigatória e não atestam o estado atual. Os cenários M1.1 que criam inscrições `NULL` precisam ser readequados antes de usar essa suíte como validação.

### Pendência conhecida

Desativar uma oferta ainda não encerra automaticamente as inscrições ativas ligadas a ela. O vínculo continua identificado corretamente, mas a política para essas inscrições deve ser definida em uma etapa própria.

---

## Histórico da M1.1 anterior (supersedido pela atualização acima)

O conteúdo abaixo registra o comportamento e as verificações da primeira versão da M1.1, quando inscrições sem oferta ainda eram aceitas. Ele foi preservado como histórico; não descreve o estado atual do código ou do banco.

Registro original, 24/10/2026 · Escopo: `enturmar_alunos` (`app/registros/turmas.py`), `scripts/verificar_onda4_m1.py` e `tests/test_enturmacao_oferta.py`. Naquela etapa, desenturmação e transferência ficaram fora do escopo. Sem commit.

---

## Passo 1 — Leitura (como era, antes de alterar)

Arquivo: `app/registros/turmas.py`, rota `enturmar_alunos(turma_id)` (`POST /turma/enturmar/<int:turma_id>`), faixa L644-737.

- **Duplicidade hoje:** dentro do laço por aluno, logo após resolver `oferta_id`, a checagem é
  `Inscricao.query.filter_by(aluno_id, turma_id, turma_curso_id=oferta_id, ativo=True).first()` (L705-710). Como casa **aluno + turma + oferta (NÃO-NULL)**, um `continue` só dispara quando já existe inscrição ativa **naquela oferta específica**.
- **Onde nasce a segunda linha:** quando o aluno já tem uma `Inscricao` **ativa com `turma_curso_id` NULL** naquela turma, o `filter_by(turma_curso_id=oferta_id, ...)` **nunca casa** com a linha NULL (NULL ≠ id), então o código segue para `nova_inscricao = Inscricao(...)` e `db.session.add(...)` (L714-723). Resultado: **duas inscrições ativas na mesma turma** — a NULL legada e a recém-criada apontando para a oferta. É exatamente a "segunda linha" que esta etapa elimina.

## Passo 2 — Regra de adoção (diff resumido)

Arquivo: `app/registros/turmas.py` · Função: `enturmar_alunos` (laço de gravação, ~L694-742).

Entre o bloqueio de duplicidade e a criação, inserida a adoção:

- Se, após o teste de duplicidade, o aluno tiver `Inscricao` **ativa** na turma com `turma_curso_id IS NULL` (`filter(turma_curso_id.is_(None), ativo.is_(True)).order_by(Inscricao.id).first()`):
  - vincula `inscricao_null.turma_curso_id = oferta_id` (**sem** tocar `data_inicio`), conta `adotados += 1` e `continue` (não cria outra linha);
  - com 2+ NULL ativas do mesmo aluno, `order_by(Inscricao.id).first()` adota só a **de menor id**; as demais ficam NULL;
  - inscrição **inativa** nunca entra no filtro (`ativo.is_(True)`).
- Sem NULL ativa: segue criando `Inscricao` nova (`criados += 1`).
- `enturmados = adotados + criados` só no flash; **texto do flash inalterado** (`f"{enturmados} aluno(s) inscrito(s) na turma {turma_obj.nome}!"`).
- A regra vale tanto com **1 oferta** quanto com **2+** (a oferta já está resolvida em `oferta_id` antes do laço). Isolamento por unidade/perfis e checagem de duplicidade por aluno+turma+oferta permanecem.

Nada mais mudou na rota. Arquivos fora do escopo: **intocados**.

## Passo 3 — Script `scripts/verificar_onda4_m1.py` (SOMENTE LEITURA)

Padrão de `scripts/verificar_onda4_fase4.py` (`_linha`, exit 0/1, SQL via `text()`, compatível PG/SQLite). Relata:

- **(a)** `Inscricao` ativas com `turma_curso_id` NULL agrupadas por turma, classificadas pelo nº de ofertas ativas da turma: **1 = backfill seguro** (OK) · **2+ = decisão manual** (AVISO) · **0 = turma sem oferta** (AVISO), com resumo por categoria.
- **(b)** duplicatas ativas por `(aluno_id, turma_curso_id)` com `turma_curso_id NOT NULL` — **FALHA** (impacta exit) se houver.
- **(c)** inscrições ativas apontando para **oferta inativa** — **AVISO** (não impacta exit).

Rodada com o banco de destino no PATH:

```
> $env:PYTHONPATH="."; python scripts/verificar_onda4_m1.py
AVISO: turma #6 'Teste de turma novo centro de custo': 7 NULL ativa(s) [2 oferta(s) ativa(s)] → decisão manual (2+ ofertas)
OK: resumo (a): total NULL ativas=7 | backfill seguro=0 | decisão manual=7 | sem oferta=0
AVISO: 7 inscrição(ões) em turma com 2+ ofertas exigem decisão manual do curso (a adoção da M1.1 só ocorre ao enturmar)
OK: nenhuma duplicata ativa por (aluno_id, turma_curso_id)
OK: nenhuma inscrição ativa apontando para oferta inativa

OK: verificações da M1.1 sem violação de integridade.
EXIT=0
```

O script **não altera dados** e não faz o backfill — apenas expõe o passivo legado (aqui, 7 NULL ativas numa turma de 2 ofertas, que a adoção resolve de forma incremental quando a secretaria enturma).

## Passo 4 — Testes (`tests/test_enturmacao_oferta.py`, +6)

- `test_adota_null_ativa_com_uma_oferta` — 1 oferta + NULL ativa: 1 linha só, vinculada à oferta, `data_inicio` preservado.
- `test_adota_null_ativa_com_duas_ofertas` — 2 ofertas + escolha: adota na oferta escolhida (1 linha, `data_inicio` preservado).
- `test_nao_adota_null_inativa` — NULL **inativa**: cria linha nova; a inativa permanece NULL/inativa.
- `test_adota_apenas_menor_id_entre_duas_null` — 2 NULL ativas: adota a de **menor id**; a outra continua NULL.
- `test_sem_null_cria_normalmente` — sem NULL: cria nova, `data_inicio = hoje`.
- `test_duplicata_recusada_apos_adocao` — regressão: após adotar, novo POST na mesma oferta é barrado (1 linha).

Helper `_null_ativa(...)` adicionado ao arquivo. Nenhum teste fora do escopo quebrou.

## Decisões que tomei sozinho

- **Escopo mínimo na adoção:** só preencho `turma_curso_id`. **Não** replico o `nivel` do formulário na linha adotada (a instrução pede preservar a linha; `data_inicio` é citado explicitamente, `nivel` não). O `aluno.nivel` continua sendo aplicado antes do laço como hoje. Se a secretaria precisar alterar o nível da inscrição adotada, isso é edição de inscrição, não enturmação.
- **`enturmados = adotados + criados`** no flash: mantém o texto atual, mas o número passa a refletir tanto adoções quanto criações (ambos "entraram na oferta" nesta requisição). Aluno que bate na duplicidade (já ativo na oferta) não entra na contagem (comportamento prévio preservado).
- **Ordem de verificação:** duplicidade (aluno+turma+oferta) **antes** da adoção. Assim, se já existe linha ativa na oferta, não se toca em NULL alguma.
- **Classificação de exit no script:** apenas **(b) duplicatas** é FALHA (corrupção real); (a) e (c) são AVISO (passivo de dados/legado), coerente com o padrão do fase4.

## Pendências que vi (não corrigidas)

- **Backfill em massa não é feito por esta etapa:** as 7 NULL ativas da turma #6 (2 ofertas) só serão vinculadas conforme a secretaria enturmar cada aluno (ou por um script de backfill dedicado, com decisão manual do curso). Com 2+ ofertas a adoção precisa de escolha explícita de oferta.
- **Desenturmação com o aluno em 2 ofertas** continua agindo por aluno+turma (`.first()`), herdado da M1 — fora do escopo M1.1.
- **Inscrições de oferta desativada** (item (c)) continuam apontando para oferta inativa; `desativar_oferta` não as trata.
- **Transferência entre turmas/ofertas** (`transferir_aluno`, alunos.py L1037) cria inscrição com `turma_curso_id` NULL e **não** adota nem migra oferta; não se beneficia da nova regra de adoção (rotas distintas).

## Verificação

- `pytest tests/test_enturmacao_oferta.py -q` → **17 passed** (11 da M1 + 6 novos).
- `pytest -q` (suíte completa):

```
2 failed, 217 passed, 46 warnings in 28.73s
```

  As 2 falhas são as preexistentes de `/cursos`; **nenhuma nova**.
- `ruff check` nos arquivos novos (`test_enturmacao_oferta.py`, `verificar_onda4_m1.py`) → **All checks passed**; as linhas editadas de `enturmar_alunos` (faixa 644-745) não adicionam avisos. Os 19 avisos restantes em `turmas.py` são pré-existentes, de outras funções.
- Script → **EXIT=0** (sem violação de integridade no banco local).
