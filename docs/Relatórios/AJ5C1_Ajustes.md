# AJ5-C1 — Ajustes do formulário de aluno

Data: 01/11/2026
Branch: `nova_feature`
Base: `64362f1` (suíte-base 1409 passed)

Série de acabamento do AJ5-C, sem migration, sem push e sem escrita em banco
ou storage real. Todos os testes usam SQLite em memória (`tests/conftest.py`).

---

## 1. Checkbox "Não possui acesso a internet"

### Onde é gravado e lido

| Etapa | Caminho | Efeito |
| --- | --- | --- |
| POST | `novo_aluno`/`editar_aluno` → `upsert_endereco(aluno, form)` (`app/services/aluno_perfil.py:164`) | grava `EnderecoAluno.possui_acesso_internet = not b(form['nao_possui_acesso_internet'])` (linha 179) |
| Leitura | `get_perfil_completo` (`:419`) → `get_endereco` (`:311`) | devolve `endereco['possui_acesso_internet']` da tabela `endereco_aluno` (linha 323); fallback `identificacao_json['endereco']` |
| Contrato | `_banco_de` (`app/services/aluno_formulario.py:201`) | inverte de novo: `not end.get('possui_acesso_internet', True)` |
| Template | `_form_aluno.html:312-313` | `{% if v.nao_possui_acesso_internet %}checked{% endif %}` |

Ou seja: o dado **não** fica em `identificacao`; fica no bloco **endereço**
(`EnderecoAluno`). O POST grava o inverso do checkbox e `_banco_de` já lia do
bloco certo.

### Teste de ida e volta

Novo arquivo: `tests/test_aj5c1_internet_roundtrip.py` (3 testes, POST/GET
reais nas rotas):

1. `test_marcado_no_cadastro_abre_marcado_no_editar` — cadastra com o
   checkbox marcado, confere `endereco.possui_acesso_internet is False` e o
   `checked` no GET de edição.
2. `test_desmarcar_no_editar_abre_desmarcado_depois` — edita sem o campo,
   confere o banco (`True`) e o checkbox desmarcado ao reabrir.
3. `test_sem_o_campo_no_post_usa_default` — cadastro sem o campo usa o
   default da coluna (`possui_acesso_internet = True`; checkbox desmarcado).

Resultado com a leitura atual de `v`: **3 passed**. Não houve falha de
round-trip, então **não foi criado commit `fix`** — `_banco_de` ficou como
estava.

### Prova de reversão (worktree, caminho absoluto)

Para provar que o teste não é vazio, foi criado um worktree descartável em
`C:\Users\FMtic\AppData\Local\Temp\opencode\aj5c1-wt` (detached em `455d1c0`)
e, **somente nele**, a linha 201 de `aluno_formulario.py` foi trocada para a
leitura errada `not ident.get('possui_acesso_internet', True)`:

```
FF.  -> 2 failed, 1 passed
```

Falharam exatamente os dois testes de ida e volta (o de default continuou
passando, como esperado). O worktree foi removido com
`git worktree remove --force`; o working tree principal não foi alterado e
nenhum checkout foi feito nele.

---

## 2. Código sem chamador do AJ5-C

### Removido

- `passo_erro` do helper `_render_form_aluno_com_dados`
  (`app/registros/alunos.py`): parâmetro, menção na docstring e o argumento
  passado a `render_template`.
- Script condicional de salto nas cascas:
  - `app/templates/alunos/novo.html` (comentário + bloco `if passo_erro ...`);
  - `app/templates/alunos/editar.html` (idem).

Nenhuma falha atual usa passo diferente de 1; o passo 1 já é o ativo na carga
(`_form_aluno.html:60`).

### Mantido (com justificativa)

- **`goToStep`** — não é o mecanismo removido: continua sendo a navegação dos
  indicadores de passo (`_form_aluno.html:27-32`) e a navegação interna de
  `aluno.js` (`:82`, `:332`, export em `:341`).
- **`foto_url`** — o parâmetro é usado: o helper calcula
  `url_for("registros.foto_aluno", ...)` e `_form_aluno.html:67-68` consome
  `v.foto_url` no preview da foto atual.
- **`app/services/aluno_formulario.py`** — nenhuma função/constante sem uso
  encontrada:
  - `valores_form_aluno`/`catalogos_formulario` são chamados pelas rotas de
    aluno e pelos testes;
  - as 17 chaves produzidas por `catalogos_formulario()` são consumidas pelo
    template (17 usos de `cat.*`);
  - `TIPOS_DEFICIENCIA` alimenta o `assert` de paridade,
    `TIPOS_DEFICIENCIA_EXIBICAO` alimenta o select e os `DOC_*` são usados por
    `valores_form_aluno`;
  - `_TEXTO_CAMPOS`, `_CHECK_CAMPOS`, `_PADROES`, `_cpf_formatado`, `_texto` e
    `_banco_de` têm uso interno.

### Prova de "sem uso" (grep)

```
git grep -n "passo_erro" -- app tests scripts        -> 0 ocorrências
git grep -n "unidades_postra" -- app tests scripts   -> 0 ocorrências
git grep -n "goToStep" -- app/templates/alunos app/static/js/alunos
  -> somente indicadores de passo + navegação interna do aluno.js
```

### Testes ajustados

`tests/test_aj5c_form_rerender.py`: as três asserções `goToStep(1)` (que,
depois da remoção, só provariam que o indicador existe) passaram a verificar o
passo realmente ativo no HTML re-renderizado:

```python
assert 'class="form-step active" id="step-1"' in texto
```

Docstring/comentários atualizados para "abre no passo 1, o passo ativo padrão
da carga".

---

## 3. Renomeação

`unidades_postra` → **`unidades_disponiveis`** em `app/registros/alunos.py`
(6 ocorrências: definição no topo do POST, 4 chamadas de re-render e o
comentário). Nenhuma referência restante no código.

---

## 4. Verificação

| Verificação | Resultado |
| --- | --- |
| Snapshots de caracterização (`test_aj5c_form_caracterizacao.py`) | **3/3 passed, sem diferença** — nenhum snapshot regenerado |
| Suíte completa (`pytest -q`) | **1412 passed, 0 failed** (1409 + 3 novos), 12m07s |
| `ruff check --select F821,F811,F841,F401 app tests scripts migrations` | **71 erros, todos F401**; 0 F821/F811/F841; nenhum nos arquivos tocados pela série |

Os snapshots não mudam porque congelam apenas os GETs (`novo`/`editar`); o
script removido só existia no caminho de falha do POST.

### F401 pré-existentes (fora do escopo, não corrigidos)

| Arquivo | Imports não usados |
| --- | --- |
| `app/__init__.py` | `current_app`, `session` |
| `app/auth.py` | `json`, `hashlib`, `unidecode` |
| `app/extensions.py` | `db` |
| `app/main/__init__.py` | `home`, `dashboard`, `secretaria`, `unidade` |
| `app/models/certificado.py` | `datetime` |
| `app/models/conselho.py` | `datetime`, `get_local_now` |
| `app/models/pedagogico.py` | `datetime` |
| `app/models/seguranca.py` | `datetime` |
| `app/models/servico_social.py` | `datetime`, `date` |
| `app/registros/atendimentos.py` | `date`, `flash`, `redirect`, `and_` |
| `app/relatorios/bi_alunos.py` | `case`, `cast`, `Integer` |
| `app/relatorios/painel_pedagogico/helpers.py` | `LIMIAR_ATENCAO`, `LIMIAR_CRITICO` |
| `app/relatorios/painel_pedagogico/turma.py` | `LIMIAR_CRITICO` |
| `app/relatorios/shared.py` | `Aluno` |
| `app/services/estatisticas_professor.py` | `List`, `func`, `db`, `Curso`, `CONCEITOS_PRESENCA`, `ConceitoFrequencia`, `ofertas_ativas` |
| `app/utils/errors.py` | `traceback` |
| `app/utils/logica.py` | `CONCEITOS_CONTABEIS`, `get_local_now` |
| `app/utils/xlsx.py` | `pandas` |
| `migrations/versions/29a29fdbc2aa_...py` | `postgresql` |
| `migrations/versions/5a676f37b9a3_...py` | `postgresql` |
| `migrations/versions/b02f2051bc1e_...py` | `op`, `sa` |
| `scripts/create_postgres_schema.py` | `create_app` |
| `scripts/smoke_models.py` | `SituacaoEscolar`, `Atendimento`, `RegistroAula`, `ConselhoClasse`, `DiaBloqueado`, `TemaAula`, `Curso`, `Nivel`, `Unidade`, `ConfiguracaoSistema`, `Transferencia` |
| `scripts/verificar_sec01.py` | `db`, `Aluno`, `Atendimento` |
| `tests/test_d5_schema.py` | `time` |
| `tests/test_enturmacao_oferta.py` | `time` |
| `tests/test_guarda_colunas_escalares_h5a.py` | `pytest` |
| `tests/test_reset_senha_aleatoria.py` | `pytest`, `session`, `UserRole` |
| `tests/test_s1_sessao.py` | `pytest` |
| `tests/test_transferencia_oferta.py` | `time` |
| `tests/test_turma_curso_edicao.py` | `pytest` |
| `tests/test_turma_curso_exclusao.py` | `time` |
| `tests/test_turma_curso_fase2.py` | `TurmaCurso` |
| `tests/test_turma_curso_horario_migration.py` | `TurmaCurso` |
| `tests/test_turma_curso_horario_schema.py` | `text` |

---

## 5. Commits

| Commit | Mensagem |
| --- | --- |
| `215e026` | `test(aj5c1): round-trip do checkbox de internet` |
| `455d1c0` | `refactor(alunos): remove codigo sem chamador do formulario` |
| (este relatório) | `docs(aj5c1): relatorio` |

Sem push. Nenhuma migration criada. A deleção pré-existente
`docs/prompts/Ajustes_Pontuais.md` permanece fora dos commits.

---

## 6. Observações e pendências

- **Docs históricos ainda citam o mecanismo removido** (não alterados):
  `backlog_desenvolvimento.md:1569` e
  `docs/Relatórios/AJ5C_FormularioAluno.md:44,89` descrevem
  `passo_erro`/`unidades_postra` como estavam no AJ5-C. São registros da série
  anterior; este relatório documenta o estado atual. O MER não menciona o
  `passo_erro`, então não precisa de ajuste.
- **Default do POST**: campo ausente → `b(None) = False` →
  `possui_acesso_internet = True` (mesmo default da coluna em
  `app/models/perfis.py:58`). Comportamento coberto pelo teste 3.
- **`upsert_endereco`** só evita criar/atualizar a linha quando todos os
  campos de endereço estão vazios **e** `possui_acesso_internet` é `True`
  (`aluno_perfil.py:182-186`). O formulário real sempre envia `zona`
  (default `Urbana`), então o caso não ocorre no fluxo de tela; nenhuma
  mudança feita.
- Os 71 F401 listados acima são dívida anterior à série e ficaram fora do
  escopo, conforme a regra de corrigir apenas o código tocado.
