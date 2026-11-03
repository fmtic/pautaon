# AJ7-A — auditoria da edição do conselho individual por gestor

Ramificação `nova_feature`. Base de partida: HEAD `927d77a`.
Escopo: registrar em `log_acao` a edição das respostas do conselho **individual
(por aluno)** quando quem edita **não é o professor da oferta**.
Sem migration, sem mudança de UI e sem push.
**Nenhuma escrita nos bancos reais**: `pautaon` e `pautaon_ensaio` foram lidos
em transação `read_only`, somente `SELECT`; as provas usam SQLite em memória
com nomes sintéticos.

---

## 1. Regra implementada

Quando um usuário autenticado salva o conselho individual de uma oferta:

- se `current_user.id == TurmaCurso.professor_id` da oferta → **nada novo** é
  gravado (o professor da oferta continua sem log de gestor);
- se o editor é qualquer outro usuário **e** ao menos um valor mudou em
  relação ao que estava gravado → **um** `LogAcao` por aluno, com rótulo
  próprio, autor, aluno, oferta, professor da oferta, papel do editor e nomes
  dos campos alterados;
- salvamento sem mudança (inclusive regravar `NULL` onde já era vazio) →
  **nenhum** log;
- primeiro preenchimento feito por quem não é o professor → o mesmo rótulo,
  com `tipo=preenchimento` (em vez de `tipo=alteracao`).

O comportamento de gravação e de autoria (F1) do conselho não foi alterado: o
helper apenas observa o que já ia ser gravado. O golden A9 confirma tela e
dados idênticos no salvamento sem mudança.

---

## 2. Descoberta (antes da alteração)

Varredura de todos os pontos de `app/` que gravam resposta/avaliação/fechamento
do conselho. A autorização foi lida nas próprias rotas (`app/conselho.py`).

| Ponto | O que grava | Quem executa | Listener genérico? |
|---|---|---|---|
| `GET /conselho/lancamento` — `lancamento_conselho` | cria `ConselhoClasse` vazio por aluno da oferta, se ainda não existir | admin, pedagógico e gerência (todas as turmas da unidade); professor (só ofertas ativas dele); demais papéis caem no ramo do professor e, sem oferta própria, não listam turma | **Sim**, `Criar ConselhoClasse` por linha, com autor/unidade, mas `detalhes = repr(obj)` |
| `POST /conselho/salvar` — `salvar_conselho` | `ConselhoResposta.resposta` e `.observacao` por aluno/pergunta; autor F1; cria `ConselhoClasse` faltante; atualiza datas do conselho | qualquer autenticado da unidade (isolamento D5.2/B4); professor só na própria oferta (outro professor = 403); admin, pedagógico e gerência pela UI; secretaria e serviço social alcançáveis por POST direto, mas não listam turma na tela | **Não** para a resposta (`ConselhoResposta` não herda `AuditoriaMixin`); **sim** para `ConselhoClasse` criado/alterado, sem campos nem valores |
| `GET/POST /turma/<id>/avaliacao` — `avaliar_turma` | JSON coletivo em `TurmaCurso.avaliacao_{inicial,percurso,final}` (perguntas `TURMA`) | qualquer autenticado da unidade; professor escopado às ofertas dele (403 sem oferta própria) | **Sim**, `Criar/Alterar TurmaCurso` (mixin), mas `repr` genérico, sem campos/valores. É avaliação coletiva, fora da regra individual |
| `POST /conselho/fechamento/<turma_id>/salvar` — `salvar_fechamento_data` | `ConselhoClasse.situacao_final`, `proxima_turma_id`, `concluido`, `data_fim`; cria o conselho FINAL | professor = 403; admin, pedagógico, gerência, secretaria e serviço social | **Sim**, `Criar/Alterar ConselhoClasse` (`repr`), sem campos. Não é resposta individual; fora da regra |
| `POST /conselho/pergunta/salvar` e `POST /conselho/pergunta/excluir/<id>` | `PerguntaConselho` (texto, opções, etapa, tipo, ativo) | admin, pedagógico, gerência | **Não** (modelo sem `AuditoriaMixin`) |
| `POST /api/conselho-periodo` e `DELETE /api/conselho-periodo/<id>` | `PeriodoConselho` | admin, pedagógico, gerência, secretaria (`_ROLES_PERIODOS_CONSELHO`) | **Não** (modelo sem `AuditoriaMixin`) |

### 2.1 O que o listener já registra — e o que falta

O listener `before_flush` (`app/models/auditoria_listener.py`) só enxerga
objetos com `updated_by_id`. `ConselhoResposta` tem `autor_id`/`autor_nome`
(snapshot F1), mas **não** herda `AuditoriaMixin`; logo, editar a resposta de
um aluno não gera nenhuma linha automática.

Provado por teste:

- **A0** edita uma resposta existente como admin e confirma que **não** existe
  log `Criar/Alterar ConselhoResposta`; depois da implementação, o único log
  dessa edição é o do helper.
- **A0b** usa um aluno ainda sem `ConselhoClasse`: o primeiro salvamento cria
  a linha e o listener grava `Criar ConselhoClasse` com `usuario_id` e
  `unidade_id`, mas `detalhes` é o `repr` padrão do objeto — sem `aluno_id`,
  `turma_curso_id`, `professor_id`, `campos` ou valores. É exatamente a
  informação que faltava.

Antes desta tarefa, portanto, o cenário “admin altera a resposta de um aluno
já existente” produzia **zero** linhas em `log_acao`; a criação de conselhos
(no GET ou no primeiro salvamento) produzia uma linha genérica por aluno, sem
como saber o que mudou.

---

## 3. Implementação

### 3.1 Rótulo e classificação

`app/conselho.py`:

```python
ACAO_EDICAO_CONSELHO_GESTOR = "Alteração de conselho (gestor)"
```

O prefixo `Alteração` já é classificado como `edicao` por
`_CATEGORIAS_ACAO` (`app/auth.py`), então o filtro de `/admin/logs` mostra a
linha em “Edição” sem precisar de nova categoria.

### 3.2 Helper único no ponto de gravação

`_registrar_log_conselho_gestor` (`app/conselho.py:209`) é chamado **uma vez
por aluno** em `salvar_conselho` (`app/conselho.py:1004`). Ele:

- retorna sem gravar se o editor é o professor da oferta
  (`current_user.id == oferta.professor_id`, com `professor_id` não nulo);
- retorna sem gravar se nenhum campo mudou;
- grava `register_security_log(ACAO_EDICAO_CONSELHO_GESTOR, detalhes,
  unidade_id=unidade_id, commit=False)`;
- monta `detalhes` no formato:

```text
aluno_id=<id> turma_curso_id=<id> professor_id=<id da oferta> usuario_id=<id>
papel=<admin|pedagogico|...> tipo=<alteracao|preenchimento>
campos=<nomes separados por vírgula>
[; resposta[p<id>]: '<anterior>' -> '<novo>']
[; observacao[p<id>]: texto alterado]
```

- valores `anterior -> novo` aparecem **somente** quando `PerguntaConselho`
  tem `opcoes` (campo de escolha/enumerado);
- resposta livre e observação entram apenas como `texto alterado`, nunca com
  o conteúdo;
- vazio é impresso como `(vazio)` para não confundir com a string `"None"`.

### 3.3 Detecção de mudança e “preenchimento”

Antes do laço de gravação, `salvar_conselho` carrega em lote as respostas da
oferta/etapa e monta `(aluno_id, pergunta_id) -> ConselhoResposta`, além de
`havia_conteudo[aluno_id]`. A comparação usa `_valor_conselho_mudou`, que trata
`NULL` e `''` como o mesmo “sem valor”. Isso evita log em regravação vazia sem
alterar a atribuição de autor do F1 (que continua comparando o valor cru).

`tipo=preenchimento` é emitido quando o aluno não tinha **nenhum** conteúdo
não vazio antes e o salvamento passou a ter conteúdo. Caso contrário, a
edição é `tipo=alteracao`.

### 3.4 Atomicidade

`register_security_log` (`app/services/auth_service.py:79`) ganhou dois
parâmetros **keyword-only**:

- `unidade_id: int | None = None` — chamadas antigas continuam idênticas;
- `commit: bool = True` — o conselho usa `commit=False` para que o log entre
  na mesma transação das respostas (o `db.session.commit()` do fim de
  `salvar_conselho` sela os dois juntos).

Nenhuma outra chamada de `register_security_log` foi alterada.

### 3.5 O que fica fora (documentado, sem mudança)

- `avaliar_turma` grava **avaliação coletiva** da oferta, não resposta
  individual; continua auditada apenas pelo listener (`Alterar TurmaCurso`).
- `salvar_fechamento_data` grava situação final/`concluido`, não resposta
  individual; continua auditada por `Criar/Alterar ConselhoClasse`.
- perguntas e períodos do conselho não são respostas de aluno.

---

## 4. Drift e filtro de `/admin/logs`

`tests/test_aj4_logs_drift.py`:

| Alteração | Efeito |
|---|---|
| `"Alteração de conselho (gestor)"` em `CENSO_REAL` | censo passou de 30 para 31 rótulos; a asserção de tamanho acompanhou |
| `CATEGORIA_ESPERADA["Alteração de conselho (gestor)"] = "edicao"` | fixa a categoria do filtro |
| chave dinâmica `app/services/auth_service.py:87` → `:99` | o corpo de `register_security_log` mudou de linha com os novos parâmetros; o repasse `acao=action` continua sendo dinâmico conhecido |

O teste A8 confirma o comportamento de ponta a ponta: depois de um salvamento
por admin, `GET /admin/logs?acao=edicao` contém o rótulo e
`GET /admin/logs?acao=criacao` não contém.

---

## 5. Testes novos

`tests/test_aj7a_conselho_auditoria.py` — 11 testes, todos em SQLite com nomes
sintéticos:

| Teste | O que prova |
|---|---|
| A0 | `ConselhoResposta` não tem `updated_by_id`; admin editando resposta existente não gera log genérico `ConselhoResposta`; o helper é o único registro |
| A0b | listener registra `Criar ConselhoClasse` com autor/unidade, mas sem aluno/oferta/professor/campos/valores; o helper complementa |
| A1 | admin altera escolha + observação + texto livre → **1** log por aluno, com ids, `papel=admin`, `tipo=alteracao`, `campos=observacao,resposta`, `'Nunca' -> 'Sempre'` e marcadores de texto |
| A2 | pedagógico altera → log com `papel=pedagogico` e a observação marcada |
| A3 | salvamento sem mudança → nenhum log novo |
| A4 | professor da oferta salva → nenhum log do helper (e nenhum genérico, pois a resposta não é auditada) |
| A5 | primeiro preenchimento por admin → `tipo=preenchimento` e `(vazio) -> 'Sempre'` |
| A6 | texto livre (resposta e observação) não aparece em `detalhes`; só `texto alterado` |
| A7 | outro professor continua 403; nada é gravado e nenhum log é criado |
| A8 | filtro de `/admin/logs` exibe o rótulo em `edicao` e não em `criacao` |
| A9 | golden: salvar sem mudança mantém o HTML do lançamento idêntico |

Execuções:

```text
python -m pytest tests/test_aj7a_conselho_auditoria.py -q
11 passed

python -m pytest tests/test_aj4_logs_drift.py tests/test_aj1_logs_filtro.py -q
115 passed

python -m pytest tests/test_aj2_conselho_lancamento.py tests/test_f1_autor_lancamento.py \
  tests/test_conselho_oferta.py tests/test_conselho_professor.py \
  tests/test_conselho_ui.py tests/test_aj7b_conselho_none.py -q
76 passed
```

---

## 6. Reversão em worktree (prova de que os testes pegam o defeito)

Worktree destacado em `927d77a` (código antigo), com **apenas** os dois
arquivos de teste copiados:

```text
python -m pytest tests/test_aj7a_conselho_auditoria.py tests/test_aj4_logs_drift.py -q
9 failed, 59 passed
```

Falham A0, A0b, A1, A2, A5, A6 e A8 (comportamento novo ausente) e os dois
testes de drift (o rótulo novo ainda não existe no código). Passam A3, A4, A7
e A9, que descrevem comportamento **já existente** (sem mudança, professor da
oferta, 403 e golden) — evidência de que a implementação não alterou o
comportamento do conselho.

O worktree foi removido; `git worktree list` final contém apenas
`D:/pautaon`.

---

## 7. Ruff

```text
python -m ruff check --select F821,F811,F841,F401 \
  app/conselho.py app/services/auth_service.py \
  tests/test_aj7a_conselho_auditoria.py tests/test_aj4_logs_drift.py
All checks passed!
```

---

## 8. Suíte completa

```text
python -m pytest -q
3 failed, 1575 passed, 896 warnings in 888.38s (0:14:48)
```

**Nenhum skip** (`0 skipped`). Os 3 testes que falham já falhavam na base
`927d77a`, sem nenhuma alteração desta tarefa — comprovado rodando os mesmos
três em um worktree limpo no HEAD:

```text
3 failed, 4 warnings in 2.51s
```

| Teste pré-existente | Assunto |
|---|---|
| `test_d5_encerramento.py::test_informacoes_conta_ofertas_pendentes` | texto “Ofertas Pendentes” na tela de informações |
| `test_h4_leitores_grade_variavel_smoke.py::...::test_detalhe_impressao_e_tela_de_cursos` | rótulo `>variavel<` na tela de cursos |
| `test_impressao_grade_oferta.py::...::test_sublinha_multi_mostra_varia_na_oferta_nao_uniforme` | rótulo `variavel` na listagem impressa |

São divergências de rótulo de tarefas anteriores (a tela imprime `variável`,
com acento, enquanto o teste espera `variavel`), sem relação com conselho ou
auditoria. Os 11 testes do AJ7-A passam dentro da suíte completa.

---

## 9. Bancos reais (SELECT-only, antes × depois)

Script `.tmp/aj7a_audit.py`, conexão `read_only`, apenas contagens — sem
detalhes, usuários, nomes ou hashes.

| Contagem | `pautaon` antes | `pautaon` depois | `pautaon_ensaio` antes | `pautaon_ensaio` depois |
|---|---:|---:|---:|---:|
| `conselho_resposta` | 78 | 78 | 6 | 6 |
| `conselho_classe` | 45 | 45 | 5 | 5 |
| `turma_curso` | 4 | 4 | 12 | 12 |
| `turma` | 3 | 3 | 8 | 8 |
| `log_acao` total | 1198 | 1198 | 1747 | 1747 |
| `log_acao` com o rótulo novo | 0 | 0 | 0 | 0 |
| `Criar ConselhoClasse` | 45 | 45 | 19 | 19 |
| `Alterar ConselhoClasse` | 0 | 0 | 27 | 27 |
| `Alterar TurmaCurso` | 35 | 35 | 159 | 159 |

Nenhuma diferença. Os testes desta tarefa rodam em SQLite em memória; o código
novo só grava em `log_acao` quando o fluxo real de salvamento é exercitado, e
o script de auditoria é estritamente de leitura. Por isso os totais reais
permanecem iguais, inclusive o rótulo novo com **zero** linhas (ainda não
houve edição de conselho por gestor nesses bancos após o deploy do código).

Distribuição de referência: no `pautaon`, há exatamente 45 linhas
`Criar ConselhoClasse` para 45 linhas de `conselho_classe`, coerente com a
criação genérica pelo listener; no `pautaon_ensaio`, 19 criações para 5 linhas
atuais — o log é histórico e não um espelho do estado atual.

---

## 10. Commits

Sem push. Base: `927d77a`.

| Commit | Conteúdo | Hash |
|---|---|---|
| `test(aj7a): cobre auditoria da edicao do conselho por gestor` | `tests/test_aj7a_conselho_auditoria.py` (11 testes) e o rótulo novo no censo de drift | `97e3e0367f0eb9b4a8b4e4c0d4a023058fe02525` |
| `feat(conselho): registra edicao do conselho por gestor em log_acao` | helper/chamada em `app/conselho.py`; `unidade_id`/`commit` em `register_security_log` | `51a2f74afad87129a81f538bc3de15fdac4ff08e` |
| `docs(aj7a): relatorio da auditoria do conselho por gestor` | este relatório | hash do commit que contém este arquivo (`git log -1 -- "docs/Relatórios/AJ7A_AuditoriaConselho.md"`) |

O commit de docs não pode registrar o próprio hash sem se alterar; os dois
hashes de código acima identificam a implementação e a sua prova.

---

## 11. Conclusão

- A edição do conselho individual por quem não é o professor da oferta passa a
  deixar rastro em `log_acao`, com **um** registro por aluno e sem conteúdo de
  texto livre.
- O professor da oferta não gera o log do helper; salvar sem mudança também
  não gera.
- O rótulo novo é `edicao` no filtro de `/admin/logs` e está congelado no
  teste de drift.
- Sem migration, sem mudança de UI, sem alteração de comportamento de
  gravação do conselho e sem push.
