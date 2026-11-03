# AJ7-D — Restrição de gravação do conselho por papel

Base: branch `nova_feature`, iniciada limpa. Sem migration, sem push e sem
escrita nos bancos reais. A auditoria dos bancos usou exclusivamente consultas
`SELECT`, com transações PostgreSQL em modo read-only.

## 1. Regra implementada

`POST /conselho/salvar` e `POST /turma/<id>/avaliacao` aceitam somente:

- `admin`;
- `pedagogico`;
- `professor` autorizado para a oferta por
  `professor_pode_acessar_oferta`.

Os demais papéis recebem 403 antes da busca da turma/recurso. O POST coletivo
faz essa verificação sem restringir o GET correspondente. Para professor, a
oferta também é validada pela regra central já existente. Permanecem as
negações 403 para oferta alheia e o isolamento por unidade D5.2/B4.

Não foram alterados fechamento (`salvar_fechamento_data`), perguntas nem
períodos do conselho.

## 2. UI e snapshots

Os controles de salvar são ocultados somente para papéis sem permissão de
gravação. Para admin, pedagógico e professor da oferta, o HTML completo das
duas telas permaneceu idêntico aos snapshots anteriores (CSRF normalizado):

| Papel | Lançamento individual | Avaliação coletiva |
|---|---|---|
| Admin | `1c013cd832d641d87bfa1e4f777d72235c8ec328ec4a0856a1a171885bbb04a9` | `6473f3dab8a56bf38b00692fab76586ed6e6ebcf292847263b9b19e1acc3bd0d` |
| Pedagógico | `4b43320b3e39d0790f9b970a05fbba7bd161746f89aac8c040f3988d834909c6` | `de2bd75798f5cbcaab1c595d2e6b9a6ce34357cfebd3d7e861f3a1f1fb663dc1` |
| Professor da oferta | `3309d45b117e33953a0be53da2d4d1b6e6b27e9b35ba81c4125ee735b8225553` | `0f9b05e95fc2c3e0ce9e3a50d7011a656231c95ab58eb90a082d085f4fe065c4` |

Templates tocados:

- `app/templates/conselho/lancamento.html:174` — botão “Salvar Tudo”.
- `app/templates/conselho/turma_aval.html:97` — botão “Salvar Avaliação”.

## 3. Testes e premissas atualizadas

`tests/test_aj7d_gravacao_conselho.py` cobre a matriz de papéis × POSTs, os
GETs, redirects de anônimo para login, contagem de linhas em todas as tabelas
nas negações e os snapshots HTML. Os POSTs admin/pedagógico continuam
disparando o helper AJ7-A; o POST do professor da oferta não o dispara.

Na reversão em worktree (`D:\pautaon-aj7d-reversao-145428c`), antes do fix, os
testes novos apresentaram **12 falhas esperadas e 20 passagens**. O worktree foi
removido após a validação.

A descrição no topo de `tests/test_aj7a_conselho_auditoria.py` foi corrigida:
ela dizia que qualquer papel não-professor poderia editar e gerar log; agora
reflete admin/pedagógico e explicita que gerência, secretaria e serviço social
não gravam. Não foi encontrado teste existente que de fato afirmasse que esses
três papéis podiam executar esses dois POSTs. Testes de gestão de períodos e
fechamento não foram alterados, pois são escopo excluído.

Validações direcionadas:

- AJ7-D, AJ7-A, oferta/professor/UI e matrizes AJ6-B6/B7: **128 passaram**;
  os testes `test_aj6b6_matriz_rotas_professor.py` e
  `test_aj6b7_complemento.py` permaneceram verdes.
- Isolamento por unidade e endurecimento D5: **46 passaram**.
- Ruff `F821,F811,F841,F401` nos arquivos Python alterados: **All checks passed**.

Suíte completa (uma execução): **1610 passaram, 0 falharam, 0 pulados**, 896
warnings, em 933 s. Lista de skips: **nenhum**.

## 4. Auditoria dos bancos reais (antes × depois)

Contagens agregadas, sem nomes:

| Banco | Tabela | Antes | Depois |
|---|---|---:|---:|
| `pautaon` | `conselho_resposta` | 78 | 78 |
| `pautaon` | `conselho_classe` | 45 | 45 |
| `pautaon` | `turma_curso` | 4 | 4 |
| `pautaon` | `log_acao` | 1198 | 1198 |
| `pautaon_ensaio` | `conselho_resposta` | 6 | 6 |
| `pautaon_ensaio` | `conselho_classe` | 5 | 5 |
| `pautaon_ensaio` | `turma_curso` | 12 | 12 |
| `pautaon_ensaio` | `log_acao` | 1747 | 1747 |

Autoria em `conselho_resposta` (`autor_id → user.role`): as **78** respostas
em `pautaon` e as **6** em `pautaon_ensaio` estão sem autor associado; não é
possível atribuí-las a papéis. Para os papéis conhecidos, a contagem atribuível
é zero.

`TurmaCurso` tem auditoria do último editor da linha, não histórico por campo.
Entre as linhas que atualmente têm alguma `avaliacao_*` preenchida, o último
editor é `professor` em uma linha de `pautaon` e `admin` em uma linha de
`pautaon_ensaio`. Isso não prova quem alterou especificamente os campos de
avaliação. Os logs genéricos `Alterar TurmaCurso` também não identificam o
campo alterado: por papel atual do autor, foram `admin=25`, `professor=1` e
`secretaria=9` em `pautaon`; em `pautaon_ensaio`, `sem autor=46`, `admin=105`,
`pedagogico=2` e `secretaria=6`. Esses registros demonstram alterações gerais
de `TurmaCurso`, não que secretaria tenha alterado `avaliacao_*`.

As contagens antes/depois são idênticas. Não houve diferença em `log_acao`:
testes usam SQLite em memória e nenhuma operação de escrita foi executada nos
bancos reais.

## 5. Commits

| Escopo | Commit |
|---|---|
| Testes AJ7-D e descrição AJ7-A | `145428c09baad499fa9c4676c8e4b84dd2ec30ed` |
| Asserção explícita do redirect anônimo para login | `5ebd1d08d63bd465d25abe8397722df97a33f74f` |
| Fix das guardas e UI | `fc52d3235aa788fe0d982250373250e581805037` |
| Relatório | hash consultável com `git log -1 -- docs/Relatórios/AJ7D_GravacaoConselho.md` após o commit |

Sem push.
