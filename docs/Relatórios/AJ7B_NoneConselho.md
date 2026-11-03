# AJ7-B — bug do literal "None" nos campos de texto do conselho

Ramificação `nova_feature`. Base de partida: HEAD `ae27702`.
Escopo: conselho individual (por aluno), avaliação coletiva, impressão,
painel, fechamento e resultado do conselho. Sem migration e sem push.
**Nenhuma escrita nos bancos reais**: `pautaon` e `pautaon_ensaio` foram
lidos em transação `read_only`, somente `SELECT`; as provas de renderização
e gravação usam SQLite em memória com nomes sintéticos.

---

## 1. Sintoma e causa raiz

Sintoma relatado: no lançamento do conselho individual, **todos** os campos
de Observação apareciam com o texto literal `None`.

Causa raiz, confirmada por teste que falha no código anterior:

1. `lancamento_conselho` montava os mapas com o valor **cru** da coluna:

   ```python
   respostas_map  = {f"{r.aluno_id}_{r.pergunta_id}": r.resposta   for r in respostas_db}
   observacoes_map = {f"{r.aluno_id}_{r.pergunta_id}": r.observacao for r in respostas_db}
   ```

2. O template usa `mapa.get(chave, '')`. O default `''` do `.get()` só vale
   para **chave ausente**. Quando a linha existe e a coluna é `NULL`, o `.get`
   devolve `None` e o Jinja imprime `None`.
3. Como `conselho_resposta.observacao` nasceu depois do formulário original
   e está `NULL` em **todas** as linhas existentes, o sintoma atinge todos os
   alunos de uma vez — exatamente o relato.

Commit introdutor: `f3d2b15` (`fix(conselho): separa resposta e observacao no
lancamento (AJ2 bloco A)`, 31/10/2026). Antes dele o formulário tinha um único
textarea (`resp_...`) alimentado pelo mesmo mapa cru; o campo Observação
separado e o segundo mapa são deste commit. A varredura de `git blame`
mostra as linhas 139/155/162 de `conselho/lancamento.html` atribuídas a
`f3d2b15`.

O mesmo padrão apareceu em outros dois pontos, cobertos pela varredura:

| Ponto | Campo opcional | Efeito antes |
|---|---|---|
| `conselho/lancamento.html` | `Turma.programa` no `DISTINCT` do filtro | `<option value="None">None</option>` |
| `conselho/fechamento.html` | `Turma.programa` e `Aluno.nivel` | `None` no cabeçalho/linha do aluno |
| `conselho/painel.html` | `Turma.ordenacao` | `None. Turma ...` |

`turma_aval.html` já estava correto: `_get_turma_avaliacao_respostas` filtra
valores falsos e devolve somente strings. `relatorios/resultado_conselho.html`
também já normaliza `programa`, `professor`, `nivel` e `próxima turma` na
rota.

---

## 2. Correção (ponto raiz + pontos afetados)

| Arquivo | Mudança |
|---|---|
| `app/conselho.py` | `respostas_map`/`observacoes_map` passam a usar `(valor or '')`; `lista_programas` descarta `NULL` do `DISTINCT` |
| `conselho/fechamento.html` | `turma.programa or '—'`; `item.obj.nivel or '—'` |
| `conselho/painel.html` | `turma.ordenacao if turma.ordenacao is not none else '—'` (preserva o valor `0`) |

A correção não muda a semântica de campos não textuais: `ordenacao` usa
teste explícito de `None` (não `or`, que transformaria `0` em `—`); os
demais são textos, onde `or '—'` é o idioma já usado no projeto.

Nenhum campo de resposta foi alterado no banco. O valor vazio continua
chegando ao salvamento como `''`, como antes do bug; `NULL` e `''` nunca são
convertidos em `"None"`.

---

## 3. Varredura dos templates/rotas do conselho

| Arquivo | Campo de texto opcional | Situação |
|---|---|---|
| `conselho/lancamento.html` | `respostas`/`observacoes` | corrigido no ponto raiz (rota) |
| `conselho/lancamento.html` | `Turma.programa` (opções do filtro) | corrigido na rota |
| `conselho/turma_aval.html` | `respostas` (JSON da oferta) | já correto (filtro de valores falsos) |
| `conselho/fechamento.html` | `Turma.programa`, `Aluno.nivel` | corrigido no template |
| `conselho/painel.html` | `Turma.ordenacao` | corrigido no template |
| `conselho/informacoes.html` | `PeriodoConselho.nome`, período, datas | colunas `NOT NULL`; sem risco |
| `conselho/imprimir_formulario.html` | perguntas/textos fixos | sem campo opcional de banco |
| `relatorios/resultado_conselho.html` | programa/professor/nível/próxima turma | já normalizado na rota |
| `conselho/perguntas.html` | `opcoes` | já usa `p.opcoes or ''` |

---

## 4. Dados reais (SELECT-only)

Auditoria executada em `pautaon` e `pautaon_ensaio` com conexão
`read_only`, sem `UPDATE`/`INSERT`/`DELETE`. Campos verificados:
`conselho_resposta.resposta`, `conselho_resposta.observacao`,
`conselho_classe.observacao`, `turma_curso.avaliacao_{inicial,percurso,final}`
e `turma.avaliacao_{inicial,percurso,final}` (legado). A busca considera
`btrim(campo) = 'None'` e, nos campos JSON, valor `"None"`.

| Banco | `conselho_resposta` | `conselho_classe` | `turma_curso` | `turma` | Linhas com texto exatamente `None` |
|---|---:|---:|---:|---:|---:|
| `pautaon` | 78 | 45 | 4 | 3 | **0** |
| `pautaon_ensaio` | 6 | 5 | 12 | 8 | **0** |

Distribuição de `conselho_resposta`:

| Banco | `observacao IS NULL` | `observacao = ''` | `observacao` com texto | `resposta IS NULL` | total |
|---|---:|---:|---:|---:|---:|
| `pautaon` | 78 | 0 | 0 | 0 | 78 |
| `pautaon_ensaio` | 6 | 0 | 0 | 0 | 6 |

Conclusão: **nenhum dado real está contaminado hoje**. O formulário exibia
`None`, mas os bancos ainda não tinham recebido a string literal — o risco
existia a partir do próximo “Salvar Tudo” sem edição. Nenhuma correção de
dado foi executada.

### 4.1 Script preventivo

`scripts/saneamento_conselho_none.sql`:

- começa com `BEGIN` e termina em `ROLLBACK` por padrão (o `COMMIT` está
  comentado);
- valida contagens esperadas em `DO $$ ... RAISE EXCEPTION` **antes** de
  qualquer `UPDATE` (hoje: 0 em todos os campos, inclusive JSON);
- saneia somente campo cujo conteúdo é **apenas** `None`
  (`btrim(campo) = 'None'`), voltando para `NULL`; não toca em texto real nem
  em JSON com respostas válidas;
- cobre `conselho_resposta`, `conselho_classe`, `turma_curso` e, por
  completude, os campos legados `turma.avaliacao_*`;
- tem conferência pós-saneamento e `RETURNING` de ids/unidade para auditoria.

Execução: somente após backup, pelo responsável; trocar `ROLLBACK` por
`COMMIT` apenas depois de conferir as contagens.

---

## 5. Testes

Arquivo novo: `tests/test_aj7b_conselho_none.py` (SQLite do fixture `app`,
nomes sintéticos, sem banco real).

| Teste | Cobertura |
|---|---|
| A1 | lançamento com `observacao` NULL, `''` e preenchida; nenhum `None`/`value="None"` no HTML |
| A2 | round-trip: reenviar o HTML renderizado com NULL **não** grava `"None"`; resposta preenchida é preservada |
| A3 | golden da tela totalmente preenchida: conteúdo exato igual antes/depois e determinístico |
| A4 | avaliação coletiva (`turma_aval`) sem `None` |
| A5 | trava estática: novos `.get(` de mapas de texto exigem teste novo |
| A6 | fechamento sem `None` em `Turma.programa`/`Aluno.nivel` |
| A7 | painel sem `None.` em `Turma.ordenacao` |

Resultado após a correção: **7 passed**.

### 5.1 Prova de reversão (worktree)

Worktree temporário em `D:\pautaon\.tmp\aj7b_wt_final`, destacado de
`ae27702` (somente o teste novo foi copiado). Resultado no código antigo:

```
FAILED test_a1_lancamento_nao_renderiza_none_em_campo_nulo
FAILED test_a2_roundtrip_salva_o_que_o_html_mostra_sem_none
FAILED test_a6_fechamento_sem_none_em_campos_opcionais
FAILED test_a7_painel_sem_none_na_ordenacao
4 failed, 3 passed
```

Os 3 que passam no código antigo são os contratos que já estavam corretos
(A3 golden preenchido, A4 avaliação coletiva, A5 varredura estática). O
worktree foi removido; `git worktree list` voltou a mostrar apenas
`D:/pautaon`.

### 5.2 Regressão do conselho

- `tests/test_aj7b_conselho_none.py` + `test_conselho_oferta.py` +
  `test_conselho_professor.py` + `test_conselho_ui.py`: **52 passed**.
- `test_aj2_conselho_lancamento.py` + `test_conselho_perguntas_abas.py` +
  `test_s1_conselho_periodos.py` + `test_s1_conselho_xss.py`: **38 passed**.
- Total dos 8 arquivos de conselho: **90 passed**.

### 5.3 Ruff

```
python -m ruff check --select F821,F811,F841,F401 app/conselho.py tests/test_aj7b_conselho_none.py
All checks passed!
```

---

## 6. Contagens antes/depois dos bancos reais

A auditoria foi executada antes e depois da suíte completa. Como os testes
usam SQLite em memória e a conexão de auditoria é `read_only`, as contagens
são idênticas:

| Banco | `conselho_resposta` | `conselho_classe` | `turma_curso` | `turma` | texto `None` |
|---|---:|---:|---:|---:|---:|
| `pautaon` antes | 78 | 45 | 4 | 3 | 0 |
| `pautaon` depois | 78 | 45 | 4 | 3 | 0 |
| `pautaon_ensaio` antes | 6 | 5 | 12 | 8 | 0 |
| `pautaon_ensaio` depois | 6 | 5 | 12 | 8 | 0 |

---

## 7. Suíte completa

`python -m pytest -q`, execução única após a correção e os testes novos
(registro em `.tmp/aj7b_suite_run.txt`):

```
3 failed, 1563 passed, 896 warnings in 964.08s (0:16:04)
```

**0 skipped** — a suíte não registrou nenhum teste pulado.

As 3 falhas são alheias ao AJ7-B e já existem no HEAD `ae27702`:

| Teste | Motivo | Origem no HEAD |
|---|---|---|
| `test_d5_encerramento.py::test_informacoes_conta_ofertas_pendentes` | espera o rótulo `Ofertas Pendentes`; a tela mostra `Cursos Pendentes (Conselho Final)` | renomeação turma/oferta → curso (`4da2433`) |
| `test_h4_leitores_grade_variavel_smoke.py::...::test_detalhe_impressao_e_tela_de_cursos` | espera `>variavel<`; a tela mostra `variável` (acentuado) | `b3b3088` |
| `test_impressao_grade_oferta.py::...::test_sublinha_multi_mostra_varia_na_oferta_nao_uniforme` | idem: espera `variavel`, recebe `variável` | `b3b3088` |

Prova de que são pré-existentes: worktree limpo em
`D:\pautaon\.tmp\aj7b_wt_head` destacado de `ae27702` (sem nenhuma mudança
do AJ7-B) roda exatamente esses três testes e reproduz **3 failed** (registro
em `.tmp/aj7b_wt_head_falhas3.txt`). O worktree foi removido em seguida;
`git worktree list` mostra apenas `D:/pautaon`. Nenhum arquivo desses testes
ou das telas envolvidas foi tocado pelo AJ7-B.

---

## 8. Arquivos e commits

Arquivos do AJ7-B:

- `app/conselho.py`
- `app/templates/conselho/fechamento.html`
- `app/templates/conselho/painel.html`
- `tests/test_aj7b_conselho_none.py`
- `scripts/saneamento_conselho_none.sql`
- `docs/Relatórios/AJ7B_NoneConselho.md`

Commits (sem push):

| Commit | Conteúdo | Hash |
|---|---|---|
| `test(aj7b): cobre None nos campos de texto do conselho` | testes A1–A7 (o código antigo falha em 4 deles — §5.1) | `3cfa5493e6dae2ff3f6870dd482befca2710afb9` |
| `fix(conselho): nao renderiza None em campos de texto opcionais` | correção do ponto raiz + `fechamento.html`/`painel.html` | `5248511805957f617d669d5bfa21f43e4281a5a2` |
| `docs(aj7b): relatorio do bug None no conselho` | este relatório e o script de saneamento | hash do commit que contém este arquivo (`git log -1 -- docs/Relatórios/AJ7B_NoneConselho.md`) |

O commit de docs não pode registrar o próprio hash sem se alterar; os dois
hashes de código acima são os que identificam a correção e a sua prova.

---

## 9. Pendências e observações

- A árvore de trabalho **já estava suja** antes deste trabalho, com mudanças
  alheias ao AJ7-B (`app/models/rss.py`, `app/utils/rss.py`,
  `app/templates/utils/gerenciar_ticker.html`, `config.py`,
  `requirements.txt`, `app/models/tricker.py`, `app/utils/tricker.py`,
  `app/templates/utils/ticker.html`, `chaves/`, `scripts/notificador.py`).
  Nada disso foi tocado ou commitado.
- A suíte completa registra **3 falhas pré-existentes** no HEAD, todas de
  rótulo (`Ofertas Pendentes`/`Cursos Pendentes` e `variavel`/`variável`),
  reproduzidas em worktree limpo sem as mudanças do AJ7-B (§7). Nenhum
  arquivo dessas telas/testes foi tocado.
- Nenhuma migration, push ou escrita em `pautaon`/`pautaon_ensaio`.
