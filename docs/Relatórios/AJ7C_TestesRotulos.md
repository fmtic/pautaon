# AJ7-C — suíte verde no HEAD (rótulos de UI)

Base: `nova_feature` em `90ee9ef`. Escopo: **somente testes**.
Sem migration, sem push, sem alteração de UI e sem escrita em banco real.
Os arquivos de terceiros (`rss`, `ticker`, `notificador`, `config.py`,
`requirements.txt`, `chaves/`) não foram tocados; `git status --porcelain`
estava vazio no início.

---

## 1. Confirmação dos commits de rótulo

### `4da2433` — turma/oferta → curso

`git show` confirma a mudança intencional em
`app/templates/conselho/informacoes.html`:

- `Ofertas Pendentes (Conselho Final)` → `Cursos Pendentes (Conselho Final)`;
- `{{ ofertas_total }} ofertas ativas` → `{{ ofertas_total }} cursos ativos`.

O mesmo commit renomeia `Selecionar Turma` → `Selecionar Curso` no
lançamento. Nenhum teste foi atualizado. A UI ficou completa para esse rótulo
(não sobrou `Ofertas Pendentes` em `app/`); o teste é que ficou velho.

### `b3b3088` — `varia` → `variável`

`git show` confirma a troca intencional em cinco arquivos de UI
(`editar.js`, `grade_horario.js`, `imprimir_listar_turma.html`, `listar.html`,
`ofertas.html`), todos com o rótulo acentuado **`variável`**. Não sobrou
`varia` como rótulo em `app/`.

O commit tentou atualizar os testes, mas gravou `variavel` **sem acento** em
dois asserts de HTML cru — exatamente os dois que falhavam. O terceiro assert
já usava `variável` sobre texto normalizado e passava. O roteiro manual também
ficou parcial: B3-02 foi atualizado, B3-03 continua com `varia`.

---

## 2. Varredura do rótulo antigo

| Ocorrência | Situação |
|---|---|
| `tests/test_d5_encerramento.py:207` — `Ofertas Pendentes` | teste desatualizado (corrigido aqui) |
| `tests/test_h4_leitores_grade_variavel_smoke.py:213` — `>variavel<` | teste desatualizado (corrigido aqui) |
| `tests/test_impressao_grade_oferta.py:307` — `variavel` | teste desatualizado (corrigido aqui) |
| `tests/test_impressao_grade_oferta.py:317` — `variavel not in` | passava por acidente; alinhado ao rótulo novo |
| `docs/Roteiro_Teste_Manual.md:149` (B3-03) | manual ainda diz `varia`; não é teste |
| Relatórios históricos (`H3d`, `H4`, `H0`, `AJ7A`, `AJ7B`) | citações históricas; não são testes |

Nenhum template contém `Ofertas Pendentes` nem o rótulo `varia` (sem acento).
As demais ocorrências de `variavel` em `tests/` são nomes de funções/variáveis
(`_seed(variavel=...)`), sem asserção de texto.

---

## 3. Alterações (somente testes)

| Arquivo | Antes | Depois |
|---|---|---|
| `tests/test_d5_encerramento.py:207` | `Ofertas Pendentes` | `Cursos Pendentes (Conselho Final)` |
| `tests/test_h4_leitores_grade_variavel_smoke.py:213` | `>variavel<` | `>variável<` |
| `tests/test_impressao_grade_oferta.py:307` | `variavel` | `variável` |
| `tests/test_impressao_grade_oferta.py:317` | `variavel not in` | `variável not in` |

Nenhuma UI foi revertida.

---

## 4. Inconsistências de rótulo (listadas, não corrigidas)

- `app/templates/conselho/painel.html:86` ainda diz
  `Mostrando N ofertas ativas`, enquanto `informacoes.html` passou a dizer
  `cursos ativos` — mesmo conceito, vocabulário diferente entre telas.
- Mensagens de `app/conselho.py` misturam `oferta` e `curso`
  (ex.: linhas 789 e 794).
- `docs/Relatórios/D5_3_relatorio.md` diz “Cursos Pendentes” mas descreve
  “total de ofertas ativas”.
- `docs/Roteiro_Teste_Manual.md` B3-03 ainda usa `varia` (B3-02 já usa
  `variável`).

---

## 5. Validação

```text
python -m pytest \
  tests/test_d5_encerramento.py::test_informacoes_conta_ofertas_pendentes \
  "tests/test_h4_leitores_grade_variavel_smoke.py::TestLeitoresSemErroComGradeVariavel::test_detalhe_impressao_e_tela_de_cursos" \
  "tests/test_impressao_grade_oferta.py::TestTextoGradeNaoUniforme::test_sublinha_multi_mostra_varia_na_oferta_nao_uniforme" \
  "tests/test_impressao_grade_oferta.py::TestTextoGradeNaoUniforme::test_impressao_uniforme_nao_diz_varia" -q
4 passed

python -m ruff check --select F821,F811,F841,F401 \
  tests/test_d5_encerramento.py \
  tests/test_h4_leitores_grade_variavel_smoke.py \
  tests/test_impressao_grade_oferta.py
All checks passed!

python -m pytest -q
1578 passed, 896 warnings in 1056.72s (0:17:36)
```

**0 failed, 0 skipped** — nenhum teste pulado.

---

## 6. Bancos reais (SELECT-only, antes × depois)

Script `.tmp/aj7c_audit.py`, conexão `read_only`, apenas contagens.

| Contagem | `pautaon` antes | depois | `pautaon_ensaio` antes | depois |
|---|---:|---:|---:|---:|
| `aluno` | 1155 | 1155 | 1166 | 1166 |
| `turma` | 3 | 3 | 8 | 8 |
| `turma_curso` | 4 | 4 | 12 | 12 |
| `conselho_classe` | 45 | 45 | 5 | 5 |
| `conselho_resposta` | 78 | 78 | 6 | 6 |
| `log_acao` | 1198 | 1198 | 1747 | 1747 |

Nenhuma diferença esperada: esta tarefa só altera asserts de teste; a suíte
roda em SQLite e o script de auditoria é estritamente de leitura.

---

## 7. Commit

| Commit | Conteúdo | Hash |
|---|---|---|
| `test(aj7c): alinha asserts aos rotulos atuais de UI` | os 3 arquivos de teste acima | `fc1c9ee9c084eab09fd85aebb12e64d0548ecc34` |
| `docs(aj7c): relatorio curto dos testes de rotulos` | este relatório | hash do commit que contém este arquivo (`git log -1 -- "docs/Relatórios/AJ7C_TestesRotulos.md"`) |

Sem push. O commit de docs não registra o próprio hash.
