# AJ22-C — Próximo Curso + Nível no fechamento do conselho (nível por CURSO)

**Data:** 18/11/2026 · **Branch:** `nova_feature` · **Migration:** `a7b8c9d0e1f2` (reescrita no mesmo id/arquivo; head do código; **pendente de deploy** — produção em `1fdc7c03bdc2`)

> **AJ22-C substitui o AJ22-B antes de qualquer deploy.** O teste do usuário
> mostrou que o nível deve ser segmentado por **CURSO** (cada curso tem sua
> nomenclatura de níveis), não por programa. O banco de desenvolvimento foi
> revertido para `1fdc7c03bdc2` antes desta etapa e a migration
> `a7b8c9d0e1f2` foi **reescrita** — `curso.programa` e `nivel.programa`
> **não existem** em lugar nenhum (migration, modelo, telas, rotas). Nada do
> AJ22-B chegou a produção.

## Decisões (fechadas)

- **F1.** `nivel.curso_id`: FK → `curso`, nullable, `ON DELETE RESTRICT`.
  `nivel.programa` e `curso.programa` removidos; `PROGRAMAS_CURSO` removido
  (sem uso).
- **F2.** Elegibilidade no fechamento: nível **ativo** com
  `nivel.curso_id == proximo_curso_id` e unidade da turma (ou global NULL).
  Valor já gravado inalterado é aceito mesmo inativo e aparece com
  "(inativo)". Nível sem curso (legado) NUNCA aparece até ser vinculado.
- **F3.** Unicidade: índice funcional `uq_nivel_nome_unidade_curso`
  (`nome`, `unidade_id`, `COALESCE(curso_id, 0)`) substitui
  `uq_nivel_nome_unidade`; downgrade com guarda que recusa duplicatas de
  `(nome, unidade_id)` entre cursos.
- **F4.** Curso sem níveis → select Nível desabilitado com "Nível não
  cadastrado"; sem curso → "Não se aplica"; trocar o curso limpa o nível.
- **F5.** Cadastro de níveis (planejamento): campo **Curso** (select de
  cursos ativos da unidade; vazio = "sem curso"); lista "Níveis sem curso"
  no topo; mesmos perfis e isolamento por unidade. Curso inativado depois:
  níveis dele deixam de ser elegíveis para novas escolhas; gravado
  inalterado continua válido.
- **F6.** Modal de Cursos: campo Programa e backend removidos
  (`editar_curso`/`novo_curso` voltaram ao formato anterior ao AJ22-B).
- **F7.** Intocados: `turma_curso.programa`, `Inscricao.nivel`, regras de
  lançamento/AJ19/AJ20/AJ21, `proximo_curso_id` (E1) e o legado
  `opcao_proxima_turma`/`proxima_turma_id` (E4).
- **F8.** Selects de nível fora do fechamento: só `turmas/detalhe.html`
  (2 selects alimentados pelo catálogo `Nivel`) — rótulo passou a
  "Nome — Curso" quando o nível tem curso. `Aluno.nivel`/`Inscricao.nivel`
  são texto livre e não foram tocados.

## Etapa 0 — leitura (mapeamento)

- `proxima_turma_id`/`OpcaoProximaTurma`: único escritor era
  `salvar_fechamento_data`; leitores = resultado do conselho e tela de
  fechamento. Desde o AJ22-B é **legado** (sem UI/escrita; fallback de
  leitura).
- `Nivel`: cadastro em `registros/core.py` (`/planejamento`, aba "niveis",
  POST `tipo_post=nivel` + `editar_nivel`); leitores em
  `registros/turmas.py` (`ver_turma` → `niveis_cadastrados`) e no serviço
  `app/services/proximo_curso.py`.
- `salvar_fechamento_data`: JSON `{oferta_id, dados[]}` com token CSRF;
  validação atômica pré-mutação; trava de conselho concluído preservada;
  `get_or_create_conselho` mantém a criação preguiçosa do AJ20.
- Lista de programas: `_PROGRAMAS_OFERTA`/`PROGRAMAS_CURSO` deixaram de
  existir neste fluxo — o "programa" do nível virou FK para `curso`.

## O que mudou (AJ22-C)

- **Migration `a7b8c9d0e1f2`** (reescrita, `down_revision =
  1fdc7c03bdc2`): cria `nivel.curso_id`, `conselho_classe.proximo_curso_id`
  e `conselho_classe.proximo_nivel_id` (FKs `ON DELETE RESTRICT`) e troca a
  unicidade do nível para `uq_nivel_nome_unidade_curso`. Aditiva, sem
  backfill, idempotente por inspeção; downgrade remove só o que criou,
  com a guarda de duplicatas. **Não cria** `curso.programa` nem
  `nivel.programa`.
- **Modelos:** `Nivel.curso_id` + `curso` relationship (`backref='niveis'`);
  `Curso.programa` removido; `ConselhoClasse` mantém
  `proximo_curso_id`/`proximo_nivel_id` (AJ22-B).
- **Serviço `app/services/proximo_curso.py`:** `niveis_por_curso`,
  `mapa_niveis_por_curso` (lote, 1 consulta), `curso_tem_niveis`,
  `nivel_elegivel`, `nivel_compativel` — tudo por `curso_id`; funções de
  programa removidas.
- **`salvar_fechamento_data`:** validação atômica por curso — nível exige
  próximo curso; curso sem níveis recusa; nível deve ser do curso, ativo,
  da unidade (exceto inalterado já gravado); limpar curso zera nível.
- **Fechamento:** `NIVEL_DATA` embutido como `{curso_id: [...]}` via
  `tojson`; textos curtos ("Nível não cadastrado" / "Não se aplica");
  spans de impressão e payload JSON inalterados.
- **Planejamento:** cadastro/edição de nível com `curso_nivel` (validado:
  curso ativo da unidade); aviso "Níveis sem curso"; modal de Cursos sem
  campo/badge de programa (tabela e JS ajustados).
- **Leitores:** resultado do conselho, ficha 360°, resumo (AJ21) e painel
  exibem "Próximo curso" + "Nível" em lote (`destinos_por_conselho`), com
  fallback legado — sem mudança de comportamento em relação ao AJ22-B.
- **F8:** `turmas/detalhe.html` mostra "Nome — Curso" nos selects de
  nível da turma/oferta (inventário: era o único select de catálogo de
  nível fora do fechamento).

## Arquivos tocados

- `migrations/versions/a7b8c9d0e1f2_aj22_proximo_curso_nivel.py` (reescrita)
- `app/models/pedagogico.py` (`Nivel.curso_id`, `Curso.programa` removido),
  `app/models/conselho.py`, `app/models/MER.md`
- `app/services/proximo_curso.py`
- `app/conselho.py` (GET/POST do fechamento)
- `app/registros/core.py` (cadastro de níveis + modal de cursos),
  `app/registros/turmas.py` (`joinedload` do curso do nível)
- `app/static/js/conselho/conselho.js`,
  `app/static/js/planejamento/planejamento.js`
- `app/templates/conselho/fechamento.html`,
  `app/templates/planejamento/planejamento.html`,
  `app/templates/turmas/detalhe.html`
- `tests/test_aj22_proximo_curso_nivel.py` (reescrito: 43 testes)
- `backlog_desenvolvimento.md`, este relatório

## Riscos e observações

- **Ordem da exceção:** o valor já gravado inalterado é aceito mesmo com o
  nível inativo — leitura literal de F2 (histórico preservado); valores
  novos/alterados seguem as recusas completas.
- **Unidade do nível:** elegível = `unidade_id` da turma **ou** global
  (`NULL`), mesmo critério dos demais leitores de nível.
- **Curso inativado depois de escolhido:** níveis dele deixam de ser
  elegíveis para **novas** escolhas; o já gravado inalterado continua
  valendo (a exceção olha só o nível — o curso inalterado já era aceito
  pelo E1).
- **SQLite:** FKs e a troca da unicidade por reconstrução de tabela são
  exercitadas nos testes; no PostgreSQL (produção) o caminho real emite
  `ALTER TABLE`/`CREATE INDEX` diretos.
- Produção não tem conselhos respondidos (só cascas) — nenhum dado
  existente muda de sentido; `proximo_curso_id`/`proximo_nivel_id` nascem
  NULL e `nivel.curso_id` nasce NULL (níveis existentes viram "sem curso"
  até serem vinculados no cadastro).

## Inventário F8 — selects de nível fora do fechamento

| Local | Tipo | Ação |
|---|---|---|
| `turmas/detalhe.html` (status do aluno + enturmação) | `<select>` do catálogo `Nivel` | rótulo "Nome — Curso" |
| `planejamento.html` (aba níveis) | cadastro/edição | campo `curso_nivel` |
| `Aluno.nivel` / `Inscricao.nivel` | texto livre (não usa catálogo) | intocado (F7) |
| `historico.html` | exibição de texto | intocado |

Nenhum outro select consome `Nivel` fora do fechamento.

## Protocolo de deploy da migration (PostgreSQL)

1. **Backup:** `pg_dump -Fc pautaon > pautaon_pre_aj22c_$(date +%Y%m%d_%H%M).dump`
   (ou o procedimento de backup usual do projeto).
2. **Ensaio primeiro** (se houver banco de ensaio): `flask db upgrade` →
   conferir head `a7b8c9d0e1f2` → `\d nivel`, `\d curso`,
   `\d conselho_classe` → ensaio de downgrade
   `flask db downgrade 1fdc7c03bdc2` (deve passar; **falha** se houver
   duplicata de `(nome, unidade_id)` entre cursos — guarda F3) →
   `flask db upgrade` de novo.
3. **Produção:** deploy do código + `flask db upgrade`; conferir
   `flask db heads` = `a7b8c9d0e1f2` e `alembic_version`.
4. **Verificação pós-deploy:**

```sql
-- colunas novas (esperado: nivel.curso_id + as duas de conselho_classe;
-- curso.programa e nivel.programa NÃO devem existir)
SELECT table_name, column_name, data_type, is_nullable
  FROM information_schema.columns
 WHERE (table_name = 'nivel' AND column_name = 'curso_id')
    OR (table_name = 'conselho_classe'
        AND column_name IN ('proximo_curso_id','proximo_nivel_id'))
    OR (table_name IN ('curso','nivel') AND column_name = 'programa')
 ORDER BY table_name, column_name;

-- unicidade funcional do nível ativa e constraint antiga ausente
SELECT indexname, indexdef FROM pg_indexes
 WHERE tablename = 'nivel' AND indexname = 'uq_nivel_nome_unidade_curso';
SELECT conname FROM pg_constraint
 WHERE conrelid = 'nivel'::regclass AND conname = 'uq_nivel_nome_unidade';

-- FKs (curso do nível + destino do conselho, ON DELETE RESTRICT)
SELECT conrelid::regclass AS tabela, conname, pg_get_constraintdef(oid)
  FROM pg_constraint
 WHERE contype = 'f'
   AND (conname IN ('fk_nivel_curso','fk_conselho_classe_proximo_curso',
                    'fk_conselho_classe_proximo_nivel')
        OR pg_get_constraintdef(oid) ILIKE '%proximo_%');

-- sanidade de dados (esperado: tudo NULL — sem backfill)
SELECT COUNT(*) FROM nivel WHERE curso_id IS NOT NULL;
SELECT COUNT(*) FROM conselho_classe WHERE proximo_curso_id IS NOT NULL;
SELECT COUNT(*) FROM conselho_classe WHERE proximo_nivel_id IS NOT NULL;
```

5. **Rollback:** `flask db downgrade 1fdc7c03bdc2` (remove só o que a
   migration criou; a guarda recusa se já existirem níveis duplicados por
   `(nome, unidade_id)` entre cursos — nesse caso renomear antes).
   Nada é migrado de/para `opcao_proxima_turma`.

## Verificação

- `tests/test_aj22_proximo_curso_nivel.py`: **43 passed** (reescrito para
  AJ22-C: migration up/down/idempotência/guarda, regras por curso,
  atomicidade, unicidade, tela/defaults/JSON, cadastros por perfil,
  rótulo "Nome — Curso", leitores e N+1).
- Direcionados conselho/AJ19/AJ20/AJ21/AJ7/oferta/UI/h5b/d5: **95 +
  43 passed**.
- Suíte completa: **1857 passed, 0 failed** (base 1852 + 5 líquidos — o
  arquivo AJ22 passou de 38 para 43 testes).
- `tests/test_conselho_oferta.py`: dois `Curso(programa=...)` legados do
  AJ22-B removidos (a coluna não existe mais).
- `ruff --select F821,F811,F841` limpo nos arquivos Python tocados;
  `git diff --check` limpo.

---

# Adendo AJ22-D — Níveis agrupados por curso e ordenados A-Z (apresentação)

**Escopo:** somente apresentação. **Sem migration, sem schema, sem regras de
gravação** — a migration `a7b8c9d0e1f2` e o head do Alembic continuam os
mesmos do AJ22-C; fechamento, leitores, cadastro/edição de níveis, perfis,
isolamento por unidade e validações não mudaram.

## O que mudou

- **Helper único** `app/utils/ordenacao.py`: `chave_ordenacao()` normaliza
  (`NFD` → remove marcas diacríticas → `casefold`), `agrupar_niveis_por_curso()`
  monta os blocos e `ordenar_niveis()` devolve a lista plana na mesma ordem.
  Desempate sempre por `id`, então "avançado" e "Avançado" ficam juntos
  sem depender do collation do PostgreSQL.
- **Aba "Níveis" do planejamento** (`app/registros/core.py` +
  `planejamento.html`): o aviso "Níveis sem curso" permanece no topo e agora
  lista os nomes em A-Z; abaixo, um bloco por curso com **nome do curso e
  contagem** no cabeçalho (`N nível/is`), cursos em A-Z e níveis em A-Z
  dentro de cada bloco. Curso sem nível não gera bloco. Nível inativo
  continua visível com "INATIVO" e vai **no fim do bloco** do seu curso.
  O select de Curso do cadastro/edição também usa a chave normalizada.
- **Selects de `turmas/detalhe.html`** (ficha do aluno + enturmação):
  mesmos valores (`Nome`) e rótulos "Nome — Curso" do AJ22-C; a ordem passa
  a ser **curso A-Z → nível A-Z**, com os níveis **sem curso primeiro**
  (antes não havia agrupamento: `ORDER BY nivel.nome` do banco; a posição
  "sem curso" primeiro é preservada porque a chave do grupo vazia sorts
  antes de qualquer nome). A consulta mantém `joinedload(Nivel.curso)` —
  nenhuma consulta extra por nível.

## Arquivos tocados (AJ22-D)

- `app/utils/ordenacao.py` (novo)
- `app/registros/core.py`, `app/templates/planejamento/planejamento.html`
- `app/registros/turmas.py` (`ordenar_niveis` no `niveis_cadastrados`;
  `detalhe.html` intocado — já trazia o rótulo do AJ22-C)
- `tests/test_aj22d_ordenacao_niveis.py` (novo, 7 testes)
- `backlog_desenvolvimento.md`, este adendo

## Verificação (AJ22-D)

- `tests/test_aj22d_ordenacao_niveis.py`: **7 passed** — acentos/caixa
  mista, agrupamento com contagem e ordem A-Z dos blocos, "sem curso" no
  topo, curso vazio sem bloco, inativos no fim com etiqueta, ordem/valores
  dos selects da turma e contagem de queries constante com 2×7 níveis.
- Regressão: `tests/test_aj22_proximo_curso_nivel.py` **43 passed**.
- Suíte completa: **1864 passed, 0 failed** (base 1857 + 7 novos testes;
  1161 warnings conhecidos/preexistentes).
- Sem alteração de migration/head; `git diff --check` e
  `ruff --select F821,F811,F841` limpos nos arquivos tocados.

## Adendo AJ22-E — Select de nível no modal de enturmação restrito ao curso da oferta

**Data:** 19/11/2026 · **Branch:** `nova_feature` · **Migration:** nenhuma

### Motivação

No AJ22-C, o catálogo `Nivel` passou a pertencer a um curso (`nivel.curso_id`), e no AJ22-D os níveis foram ordenados A-Z por curso. No entanto, ao enturmar alunos em `turmas/detalhe.html` (`#modalEnturmar`), o `<select name="nivel_{{ a.id }}">` ainda iterava sobre a lista global de níveis da unidade (`niveis_cadastrados`), disponibilizando opções de todos os cursos para a oferta que estava sendo enturmada.

O usuário solicitou que apenas os níveis do curso da oferta em que o aluno está sendo enturmado fossem exibidos no select.

### Implementação

1. **Backend (`app/registros/turmas.py` — `ver_turma`):**
   - A partir de `niveis_cadastrados` (que já carrega os níveis ativos com `joinedload(Nivel.curso)` e ordenação A-Z), deriva em memória:
     ```python
     niveis_oferta_sel = (
         [n for n in niveis_cadastrados if n.curso_id == oferta_sel.curso_id]
         if oferta_sel is not None
         else []
     )
     ```
   - Passa `niveis_oferta_sel` para o contexto do `render_template`. Nenhuma consulta adicional ao banco.

2. **Template (`app/templates/turmas/detalhe.html`):**
   - No `#modalEnturmar`, substitui a iteração `niveis_cadastrados` por `niveis_oferta_sel`.
   - Como todos os níveis do select pertencem exclusivamente ao curso selecionado, o rótulo da opção foi simplificado para `{{ nivel.nome }}` (sem redundância de sufixo `— Curso`).
   - "Não se aplica" permanece como primeira opção (padrão).
   - Se o curso não tem níveis cadastrados, o select exibe unicamente "Não se aplica".

3. **Defesa em profundidade no POST (`app/registros/turmas.py` — `enturmar_alunos`):**
   - Antes do loop de alunos, obtém os nomes dos níveis válidos do curso da oferta:
     ```python
     niveis_curso_nomes = {
         n.nome
         for n in Nivel.query.filter(
             Nivel.curso_id == oferta_sel.curso_id,
             (Nivel.unidade_id == turma_obj.unidade_id) | (Nivel.unidade_id == None),
             Nivel.ativo == True,
         ).all()
     }
     ```
   - Se o valor recebido no formulário não pertencer a esse conjunto, é sanitizado para `None` (não grava nível de outro curso).

### Arquivos tocados (AJ22-E)

- `app/registros/turmas.py` (`niveis_oferta_sel` em `ver_turma` e sanitização em `enturmar_alunos`)
- `app/templates/turmas/detalhe.html` (iteração `niveis_oferta_sel` no `#modalEnturmar`)
- `tests/test_aj22e_nivel_enturmar.py` (novo: 6 testes)
- `backlog_desenvolvimento.md`, este relatório, `app/models/MER.md`

### Verificação (AJ22-E)

- `tests/test_aj22e_nivel_enturmar.py`: **6 passed** (filtro por oferta A/B, curso sem níveis, turma de oferta única, gravação válida no aluno e inscrição, sanitização de nível de outro curso e opção "Não se aplica").
- Regressões: `tests/test_aj22d_ordenacao_niveis.py` (**7 passed**) e `tests/test_aj22_proximo_curso_nivel.py` (**43 passed**). Total de 56 testes AJ22 verdes.

---

## Adendo AJ22-F — Níveis recolhíveis por curso + nível atual do aluno enturmado

**Data:** 19/11/2026 · **Branch:** `nova_feature` · **Migration:** nenhuma · **Schema:** inalterado

### Motivação

Com o catálogo de níveis por curso (AJ22-C) e a ordenação/agrupamento A-Z (AJ22-D), a aba "Níveis" do planejamento passou a acumular um bloco por curso. A listagem longa dificultava a localização de um nível. Em paralelo, o select da ficha do aluno enturmado (AJ22-E) filtrava corretamente por curso da oferta, mas valores antigos de texto livre — ou de outro curso — não tinham opção correspondente: abrir e salvar o select acabava apagando o dado.

### Implementação

1. **Blocos recolhíveis (`app/templates/planejamento/planejamento.html`, CSS e JS):**
   - Cada bloco de curso usa o `collapse` do Bootstrap 5.3.8 já carregado em `base.html`: cabeçalho com `role="button"`, `tabindex="0"`, `data-bs-toggle="collapse"`, `data-bs-target`, `aria-expanded`, `aria-controls` e chevron; as linhas ficam em um `<tbody id="nivel-grupo-<curso>">` separado do cabeçalho.
   - Estado inicial recolhido; "sem curso" (aviso e bloco) sempre aberto. Botões **Expandir todos** / **Recolher todos** acima da tabela; o JS também trata Enter/Espaço no cabeçalho.
   - Progressive enhancement: todas as linhas estão no HTML e um `<noscript>` força `display: table-row-group` nos blocos recolhidos (e esconde os botões que dependem de JS).
   - Ordenação A-Z, contagens, inativos no fim e agrupamento do AJ22-D preservados.

2. **Reabertura sem JS (`app/registros/core.py`):** `_voltar_planejamento` ganhou `nivel_grupo` (whitelist: só id numérico). Criação, edição (curso resultante) e ativação/inativação passam o curso do nível; o GET valida o parâmetro e o template já renderiza `collapse show` + `aria-expanded="true"` naquele bloco. Nível sem curso não gera parâmetro — o aviso já fica aberto.

3. **Select do aluno enturmado (`app/templates/turmas/detalhe.html`, `app/registros/alunos.py`):** o valor de `inscricao_aluno.nivel or aluno.nivel` é renderizado como primeira opção `valor (atual)` (mesmo fora do catálogo/de outro curso); a listagem restante continua sendo apenas `niveis_por_curso_id.get(oferta.curso_id, [])`. `atualizar_nivel_aluno` consulta a inscrição antes da sanitização e aceita o valor enviado quando ele é igual ao valor atual; qualquer valor **novo** fora do curso continua sendo sanitizado para `None`, como em `enturmar_alunos`. `Inscricao.nivel` permanece `String(30)` de texto livre.

### Arquivos tocados (AJ22-F)

- `app/templates/planejamento/planejamento.html`, `app/static/js/planejamento/planejamento.js`, `app/static/css/planejamento/planejamento.css`
- `app/registros/core.py`, `app/registros/alunos.py`, `app/templates/turmas/detalhe.html`
- `tests/test_aj22f_niveis_colapsiveis.py`, `tests/test_aj22f_nivel_aluno_enturmado.py` (novos)
- `tests/test_aj22_proximo_curso_nivel.py` e `tests/test_aj22d_ordenacao_niveis.py` (testes de select ajustados ao contrato AJ22-E)
- `tests/snapshots/aj6b3_*.txt` e `tests/snapshots/aj6b6_admin_registros_ver_turma.txt` (golden do HTML de `/turma` regenerado: AJ22-E acrescentou o hidden `turma_curso_id` ao form do nível)
- `backlog_desenvolvimento.md`, `app/models/MER.md`, este relatório

### Verificação (AJ22-F)

- Novos testes: **18 passed** (9 de collapse/ARIA/reabertura/N+1 de níveis e 9 de nível atual do aluno/preservação no POST/N+1 de alunos).
- Regressões: AJ22 (**43**), AJ22-D (**7**) e AJ22-E (**11**) verdes.
- Suíte completa: **1893 passed, 0 failed** (base 1875 — já com os 11 do AJ22-E — + 18 novos). `ruff --select F821,F811,F841`, `git diff --check` limpos; nenhuma migration/head alterado.
