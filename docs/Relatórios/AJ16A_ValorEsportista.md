# AJ16-A — Auditoria do Valor do Esportista

**Data:** 09/11/2026  
**Tipo:** auditoria somente leitura (sem alteração de código, testes, schema ou banco)  
**Objetivo:** mapear a regra atual do “Valor/Postura do Esportista” e planejar a migração do vínculo **por aluno/frequência** para **por aula/oferta em N:N com `registro_aula`**, no mesmo molde dos temas.  
**Banco de referência:** `pautaon` local, revisão Alembic `c1d2e3f4a5b6`.  
**Produção:** dump `instance/backups/pautaon_producao_2026-11-03.dump`, revisão `c4d5e6f7a8b9` (anterior à A1).

---

## 1. Resumo executivo

1. O valor hoje é **um único FK nullable em `frequencia`**: `frequencia.valor_esportista_id` (`app/models/aulas.py:136-145`). O catálogo é `valor_esportista`, com escopo **somente por unidade** (`app/models/pedagogico.py:63-100`).
2. Só existe **um caminho de escrita** do valor: `salvar_frequencia` → `_resolver_valor_esportista` (`app/utils/logica.py:501-546`, `:632-637`, `:804`). A rota `POST /frequencia` apenas orquestra (`app/registros/core.py:221-404`).
3. Só existem **dois leitores de produção**:
   - a tela de lançamento, que lê o valor **por aluno** (`app/utils/logica.py:471-498`; `app/registros/core.py:546-554`; `app/templates/frequencia/lancar.html:279-303`);
   - o bloco “Engajamento da turma”, que agrega **linhas de frequência por oferta** (`app/services/engajamento_turma.py:53-107`; `app/main/dashboard_professor.py:334-343`; `app/templates/dashboard/painel_pedagogico.html:299-332`).
4. Nenhum leitor de pauta impressa, relatório, exportação, BI, diário, ficha/histórico, certificado ou conselho lê a coluna. Os testes de não regressão provam saídas idênticas com e sem valor (`tests/test_valor_esportista_nao_regressao.py:54-124`).
5. A regra V2 é **por aluno**: todo conceito A–D exige valor quando a unidade da turma tem catálogo ativo; a validação roda **antes de qualquer escrita** e, se houver pendência, nada é gravado (`app/utils/logica.py:590-649`, `:734-746`; `app/registros/core.py:388-395`). F/J e aluno sem conceito não exigem; valor inativo já salvo é preservado; valor inativo novo, inexistente ou de outra unidade conta como ausente (`app/utils/logica.py:501-546`).
6. O molde N:N dos temas já existe: tabela `registro_aula_tema` (`app/models/aulas.py:48-67`), relação `RegistroAula.temas` com `secondary`/`lazy='selectin'` (`app/models/aulas.py:230-233`), escrita por substituição do conjunto (`app/utils/logica.py:757-776`) e migration com backfill (`migrations/versions/a8b9c0d1e2f3_registro_aula_multiplos_temas.py:19-40`).
7. **Evidência decisiva nos dados atuais:** o `pautaon` local tem **54 linhas** de frequência com valor, em **6 pares (oferta, data)**; **todos os 6 pares têm mais de um valor distinto** — distribuição: 1 par com 3 valores, 1 com 4, 2 com 5 e 2 com 7. **Nenhum par tem exatamente 1 valor.** Portanto, um único `registro_aula.valor_esportista_id` perderia dados; o N:N na aula é necessário para preservar o conjunto.
8. **Limitação da prova em produção:** o dump de produção está em `c4d5e6f7a8b9`, **antes da A1**. O clone restaurado e migrado até `c1d2e3f4a5b6` tem **zero** valores. Não é possível provar a distribuição de produção enquanto a A1 não estiver aplicada (ou sem um dump posterior à A1).
9. **Recomendação:** criar `registro_aula_valor_esportista` (PK composta, FK `CASCADE` para `registro_aula`, FK `RESTRICT` para `valor_esportista`, índice reverso), ler/gravar o conjunto na aula, manter `frequencia.valor_esportista_id` **congelado** durante a fase 1 como fallback histórico e só removê-lo na fase 2, após verificação. A migração preserva o **conjunto de valores por aula**, mas **não preserva o vínculo valor↔aluno** — essa é a perda inevitável do modelo pedido e precisa ser aceita explicitamente.

---

## 2. Escopo e método

- Auditoria feita em worktree descartável, destacado de `nova_feature` (`0e14fef`), sem nova branch.
- Nenhum arquivo de código, teste, schema ou banco foi alterado. O único arquivo criado é este relatório.
- Clone `pautaon_aj16a_clone` criado a partir do dump de produção, restaurado, migrado até `c1d2e3f4a5b6`, consultado e removido ao final.
- Contagens de `pautaon` e `pautaon_ensaio` foram feitas **somente com `SELECT`**.
- O relatório não contém nomes de alunos, professores, unidades ou quaisquer dados pessoais; apenas contagens, schema e referências de código.

---

## 3. Modelo e schema atuais

### 3.1 Catálogo `valor_esportista`

`app/models/pedagogico.py:63-100`:

| Item | Referência | Observação |
|---|---|---|
| Classe | `app/models/pedagogico.py:63` | `ValorEsportista` |
| Tabela | `app/models/pedagogico.py:81` | `valor_esportista` |
| Índice único funcional | `app/models/pedagogico.py:82-89` | `uix_valor_esportista_nome_unidade` em `(lower(nome), unidade_id)` |
| `id` | `app/models/pedagogico.py:91` | PK |
| `nome` | `app/models/pedagogico.py:92` | `varchar(100)`, NOT NULL |
| `ativo` | `app/models/pedagogico.py:93` | NOT NULL, default `true` |
| `unidade_id` | `app/models/pedagogico.py:94-96` | FK → `unidade.id`, **NOT NULL** |
| `created_at` / `updated_at` | `app/models/pedagogico.py:97-98` | timestamps locais |
| Relação | `app/models/pedagogico.py:100` | `unidade` + backref `valores_esportista` |

**Escopo:** somente por unidade. Não existe valor global; a Visão Global é somente leitura. A criação/edição/inativação exige unidade efetiva (`app/registros/core.py:1040-1079`, `:1350-1402`; `app/registros/shared.py` via `assert_unidade_context`).

### 3.2 Vínculo atual em `frequencia`

`app/models/aulas.py:136-145`:

```python
valor_esportista_id: int = db.Column(
    db.Integer,
    db.ForeignKey(
        'valor_esportista.id', name='fk_frequencia_valor_esportista',
        ondelete='SET NULL',
    ),
    nullable=True,
    index=True,
    comment='FK → valor_esportista (dado adicional do lançamento)',
)
```

Relação ORM: `Frequencia.valor_esportista` (`app/models/aulas.py:165`).

**Semântica:** o valor é atributo de **uma linha de frequência** (aluno + oferta/turma + data), não da aula. É nullable; `ON DELETE SET NULL` preserva o histórico se o catálogo for removido à força. O índice `ix_frequencia_valor_esportista` é criado pela migration (`migrations/versions/b7c8d9e0f1a2_valor_esportista.py:95-97`).

### 3.3 Migration que criou o modelo

`migrations/versions/b7c8d9e0f1a2_valor_esportista.py`:

| Item | Linhas |
|---|---|
| Constantes de nomes | `:39-45` |
| Criação da tabela + índice funcional | `:48-74` |
| Adição da coluna, FK (Postgres) e índice | `:77-97` |
| Remoção da coluna/FK/índice | `:100-109` |
| Remoção da tabela | `:112-114` |
| `upgrade` / `downgrade` | `:117-126` |

**Não há backfill:** registros anteriores à A1 ficam `NULL` (`:17-19`).

### 3.4 Onde o valor **não** existe

Não há coluna de valor em `registro_aula`, `turma_curso`, `turma`, `inscricao`, `conselho_classe` ou qualquer outra tabela. A busca em `app/` por `valor_esportista`, `ValorEsportista`, `postura_aluno`, `valores_esportista`, `valores_por_aluno`, `valor_salvo`, `valor_inativo` retorna apenas:

- catálogo e model (`app/models/pedagogico.py`, `app/models/aulas.py`, `app/models/__init__.py`);
- tela de lançamento e rota (`app/registros/core.py`, `app/templates/frequencia/lancar.html`, `app/static/js/frequencia.js`);
- lógica (`app/utils/logica.py`);
- engajamento (`app/services/engajamento_turma.py`, `app/main/dashboard_professor.py`, `app/templates/dashboard/painel_pedagogico.html`);
- documentação (`app/models/MER.md`).

Nenhum relatório, BI, pauta, exportação, diário, ficha ou conselho aparece nessa busca.

---

## 4. Fluxo de escrita atual

### 4.1 Rota `POST /frequencia`

`app/registros/core.py:221-404`:

| Etapa | Linhas | O que faz |
|---|---|---|
| Permissões | `:228-236` | ADMIN/PEDAGOGICO/PROFESSOR/SECRETARIA no GET; SECRETARIA não escreve |
| Vínculo do professor à oferta | `:238-250` | professor só lança em oferta ativa da turma |
| Validação da data | `:252-257` | data precisa estar no calendário da turma |
| Resolução da oferta | `:259-338` | `resolver_oferta_lancamento`; 2+ ofertas exigem escolha e validação; guarda final por oferta |
| Filtro de alunos da oferta | `:340-386` | remove `aluno_*` e `postura_aluno_*` de alunos fora da pauta da oferta |
| Chamada da lógica | `:388-395` | `salvar_frequencia(form_data)`; captura `PendenciaValorEsportista` e flasha a mensagem |

### 4.2 `salvar_frequencia`

`app/utils/logica.py:652-818`:

| Etapa | Linhas | O que faz |
|---|---|---|
| Parse de turma/data | `:675-704` | normaliza `turma`, `data`, `data_hidden` |
| Parse de temas | `:681-693` | `tema_ids` repetidos; fallback `tema_id`; dedupe |
| Parse de observações/atividades | `:694-696` | textos independentes |
| Resolução da oferta | `:706-714` | `resolver_oferta_lancamento` |
| Alunos da pauta | `:716-725` | join `Inscricao` ativa + `Aluno` ativo |
| Unidade do valor | `:727-732` | unidade da **turma**; fallback `get_unidade_id()` |
| Plano + validação V2 | `:734-746` | `_planejar_frequencia`; se pendente, `PendenciaValorEsportista` antes de qualquer escrita |
| `RegistroAula` existente/novo | `:748-777` | busca por oferta/data ou legado; grava observações, atividades, `tema_id` espelho e `registro.temas` |
| Frequência por aluno | `:779-804` | cria/atualiza `Frequencia`; grava `conceito` e `valor_esportista_id` |
| Commit | `:806-807` | um único commit |
| Rollback/erro | `:809-818` | pendência é re-lançada; demais erros viram `(0, None)` |

### 4.3 Resolução por aluno

`_resolver_valor_esportista` (`app/utils/logica.py:501-546`):

- conceito fora de A/B/C/D → `None` (limpa);
- texto vazio, não numérico ou `<= 0` → `None`;
- id igual ao já salvo (`valor_atual_id`) → preserva mesmo inativo;
- id inexistente ou inativo novo → `None` + warning;
- id de outra unidade → `None` + warning;
- caso contrário → id.

`_planejar_frequencia` (`:590-649`) aplica a pendência:

```python
if exige_valor and conceito in _CONCEITOS_PRESENCA_TEXTO and valor_id is None:
    pendentes.append(aluno)
    continue
```

O plano é `[(aluno, conceito, freq|None, valor_id|None)]` (`:614`, `:647`).

### 4.4 O molde dos temas (N:N já existente)

| Item | Referência | Detalhe |
|---|---|---|
| Tabela associativa | `app/models/aulas.py:48-67` | `registro_aula_tema` |
| PK | `app/models/aulas.py:50-65` | `(registro_aula_id, tema_aula_id)` |
| FK `registro_aula` | `app/models/aulas.py:51-57` | `ON DELETE CASCADE` |
| FK `tema_aula` | `app/models/aulas.py:58-65` | `ON DELETE RESTRICT` |
| Índice reverso | `app/models/aulas.py:66` | `ix_registro_aula_tema_tema` |
| Relação ORM | `app/models/aulas.py:230-233` | `secondary`, `order_by='TemaAula.ordem, TemaAula.id'`, `lazy='selectin'` |
| Escrita | `app/utils/logica.py:757-776` | `registro.temas = TemaAula.query.filter(...).all()` |
| Leitura | `app/utils/logica.py:426-435` | `_resumo_diario`: `[tema.id for tema in diario.temas]`, fallback `tema_id` |
| Migration | `migrations/versions/a8b9c0d1e2f3_registro_aula_multiplos_temas.py:19-40` | cria tabela, índice e backfill de `tema_id` |
| Coluna espelho | `app/models/aulas.py:218` | `tema_id` permanece temporariamente como espelho do primeiro tema |
| Documentação | `app/models/MER.md:806-815` | contrato de leitura e migration |

**Observação importante:** o molde dos temas **não tem `unidade_id` na tabela associativa**. O escopo é validado na aplicação, pelo vínculo com `registro_aula`/`turma` e pela seleção de temas do curso. O mesmo padrão pode ser usado para valores, com validação explícita de unidade no write.

---

## 5. Regra de obrigatoriedade atual (V2)

### 5.1 Servidor

`app/utils/logica.py`:

| Item | Linhas | Regra |
|---|---|---|
| `unidade_tem_valores_ativos` | `:575-587` | `EXISTS` de `valor_esportista.ativo` na unidade; `unidade_id=None` olha o catálogo global |
| `_planejar_frequencia` | `:590-649` | pendência = conceito A–D + `valor_id is None` + `exige_valor` |
| `PendenciaValorEsportista` | `:549-559` | exceção carrega a lista de alunos |
| `mensagem_valor_obrigatorio` | `:562-572` | até 10 nomes + “e mais N”; “Nada foi salvo.” |
| Chamada | `:734-746` | `exige_valor=unidade_tem_valores_ativos(valor_unidade_id)`; se pendente, nada é gravado |
| Rota | `app/registros/core.py:388-395` | flash + redirect para a mesma turma/data/oferta |

**Condições exatas:**

- Vale para **qualquer data**, inclusive registro histórico reescrito.
- A unidade considerada é a **unidade da turma**, com fallback para a unidade da sessão (`app/utils/logica.py:727-732`).
- **Exceção:** unidade sem nenhum valor ativo → a regra não se aplica.
- **F e J:** não exigem e limpam o valor (`_resolver_valor_esportista` retorna `None`).
- **Aluno sem conceito:** não entra no plano; a linha existente fica intocada (`:611-612`, `:617-620`).
- **Valor inativo já salvo:** preservado (`:529-530`).
- **Valor inativo novo, inexistente ou de outra unidade:** conta como ausente e, com catálogo ativo, gera pendência (`:535-545`).
- **Nada é gravado antes da validação:** nem conceitos, nem `registro_aula` (temas/observações/atividades).

### 5.2 Cliente

`app/templates/frequencia/lancar.html`:

| Item | Linhas | Regra |
|---|---|---|
| Aviso de catálogo ausente | `:52-58` | só para ADMIN/PEDAGOGICO/SECRETARIA |
| Atributo do form | `:60-61` | `data-valor-obrigatorio="1"` só quando há valores ativos |
| Select por aluno | `:279-303` | `postura_aluno_<id>`; `disabled` fora de A–D, aluno transferido ou readonly; `required` quando A–D e há catálogo |
| Valor inativo salvo | `:296-298` | opção extra “(inativo)” selecionada |

`app/static/js/frequencia.js`:

| Item | Linhas | Regra |
|---|---|---|
| `CONCEITOS_PRESENCA` | `:15` | A/B/C/D |
| `exigeValorEsportista` | `:18-20` | A–D |
| `valorEsportistaPendente` | `:26-28` | catálogo ativo + A–D + sem valor |
| `tratarConceitoAluno` | `:73-86` | habilita/limpa/`required` por aluno |
| `validarPendencias` | `:88-104` | percorre `select[id^="postura_"]` |
| Submit/invalid | `:141-162` | bloqueia submit e destaca pendências |

### 5.3 Consequência para o modelo N:N

A regra atual não é “a aula precisa de um valor”; é “**cada aluno com presença** precisa do seu valor”. Ao mover para a aula, a regra precisa ser redefinida. A proposta deste relatório é:

> Se a unidade da turma tem catálogo ativo e **ao menos um aluno** da pauta tem conceito A–D, a aula precisa de **ao menos um valor** selecionado. Sem presença (todos F/J ou sem conceito), a obrigatoriedade não se aplica.

Essa decisão muda a mensagem, o template e o JS; ver §12 e §14.

---

## 6. Inventário completo de leitores

### 6.1 Leitores de produção

| # | Leitor | Arquivo:linha | O que lê | Impacto da migração |
|---|---|---|---|---|
| 1 | Tela de lançamento — conceitos + valores por aluno | `app/utils/logica.py:391-423` (`_ler_registros_aula`), `:471-498` (`carregar_frequencias_e_valores`) | `Frequencia.valor_esportista` via `joinedload`; devolve `{aluno_id: ValorEsportista}` | **Muda o contrato**: passa a devolver o conjunto da aula (`list[ValorEsportista]`), com fallback na coluna antiga |
| 2 | Rota GET da pauta | `app/registros/core.py:546-554` | chama `carregar_frequencias_e_valores` e recebe `valores_por_aluno` | Passa a receber `valores_aula`/`valores_selecionados` |
| 3 | Template da pauta | `app/templates/frequencia/lancar.html:279-303` | select por aluno (`postura_aluno_<id>`) | Vira grupo único de checkboxes/select múltiplo (`valor_ids`) |
| 4 | Catálogo de valores — GET do planejamento | `app/registros/core.py:1173-1178`, `:1195-1211`; `app/templates/planejamento/planejamento.html:538-609` | lista `ValorEsportista` da unidade, ativo/inativo | **Não muda** (catálogo continua igual) |
| 5 | Catálogo de valores — escrita | `app/registros/core.py:1040-1079` (criar), `:1350-1382` (editar), `:1385-1402` (inativar) | `ValorEsportista` | **Não muda** |
| 6 | Opções do seletor da pauta | `app/registros/core.py:606-617` | `ValorEsportista` ativos da unidade da turma | **Não muda** (mesmo catálogo; o que muda é o controle de seleção) |
| 7 | Engajamento da turma | `app/services/engajamento_turma.py:53-107`; `app/main/dashboard_professor.py:334-343` | `Frequencia JOIN ValorEsportista` por `valor_esportista_id`, agrupado por oferta | **Muda a consulta**: passa a agregar vínculos `registro_aula_valor_esportista` por aula/oferta |
| 8 | Template do engajamento | `app/templates/dashboard/painel_pedagogico.html:299-332` | `engajamento.itens`, `engajamento.total` | **Muda o rótulo** de “registros de presença com valor” para “aulas com valor” (ou equivalente) |
| 9 | Validação de obrigatoriedade | `app/utils/logica.py:575-649`; `app/registros/core.py:388-395` | conceitos + valor por aluno | **Muda para nível de aula**; mensagem e fluxo de erro |
| 10 | JS da pauta | `app/static/js/frequencia.js:15-28`, `:73-104`, `:124-162` | selects `postura_<id>` | **Muda para validação do grupo de valores da aula** |

### 6.2 Leitores que **não** leem o valor (confirmado)

A busca em `app/` não encontrou `valor_esportista`/`ValorEsportista` em:

- pauta impressa (`app/registros/turmas.py`, template de impressão);
- relatórios de frequência e exportação XLSX (`app/relatorios/*`);
- BI (`app/relatorios/bi_*.py`);
- diário/observações (`app/relatorios/observacoes.py`, `app/registros/turmas.py:2878-2882`);
- ficha/histórico do aluno (`app/relatorios/painel_pedagogico/ficha_aluno.py`);
- certificados;
- conselho de classe (`app/conselho.py`).

Os testes de não regressão comparam HTML/XLSX com e sem valor e confirmam a igualdade (`tests/test_valor_esportista_nao_regressao.py:54-124`). Isso reduz muito o risco de regressão funcional da migração: o valor é um dado adicional isolado.

### 6.3 Observação sobre `joinedload` e N+1

`_ler_registros_aula` carrega `Frequencia.valor_esportista` na mesma consulta (`app/utils/logica.py:401-419`). A A1 preservou a contagem de consultas da pauta; o teste `tests/test_d3b2_4_estatisticas.py:53` (`test_n1_estats_constante`) é o guarda-corpo. Na migração, o `selectin` de `RegistroAula.valores` deve manter o custo constante (uma consulta adicional no máximo, não por aluno).

---

## 7. Inventário de testes

Contagem por **funções `def test_`**; alguns arquivos usam `parametrize`, então o número de casos executados é maior (indicado quando relevante).

| Arquivo | Funções | Cobertura relacionada ao valor |
|---|---:|---|
| `tests/test_valor_esportista.py` | 10 | CRUD do catálogo, permissões, CSRF, isolamento por unidade, Visão Global, aba/KPI (`:92-213`) |
| `tests/test_valor_esportista_lancamento.py` | 17 | Persistência A–D, limpeza em F/J, valor de outra unidade/inativo/inexistente, inativo já salvo, readonly, transferido, duas ofertas, estatísticas, estado do select (`:130-369`) |
| `tests/test_valor_esportista_nao_regressao.py` | 4 | Pauta impressa, relatório de frequência, XLSX e registro antigo sem valor (`:54-124`) |
| `tests/test_valor_esportista_migration.py` | 5 | Upgrade/downgrade com dados, unicidade sem case, reaplicação, DDL Postgres (`:162-310`) |
| `tests/test_valor_obrigatorio.py` | 14 (26 casos) | Regra V2 no servidor, exceções, inativo, inválido, mensagem, duas ofertas, estatísticas, secretaria (`:190-462`) |
| `tests/test_valor_obrigatorio_ui.py` | 11 (12 casos) | `required`/`disabled` no select, aviso, funções puras do JS (`:91-192`) |
| `tests/test_valor_obrigatorio_caracterizacao.py` | 2 (4 casos) | Antigo × novo: A–D sem valor e valor inválido (`:42-55`) |
| `tests/test_v3b_engajamento_turma.py` | 18 | Ordenação, empate, <3, vazio, percentual, isolamento de oferta, legado D2, inativo, layout, escape, sem nome de aluno, filtro, permissões (`:185-418`) |
| `tests/test_planejamento_abas.py` | 10 | Aba Valores após criar/editar/inativar (`:76-134`, `:205-219`) |
| `tests/test_lancar_template_estrutura.py` | 2 | Estrutura do template e textos (`:88-106`) |
| `tests/test_f1_autor_lancamento.py` | 12 | Regravar o mesmo conceito ou mexer só no valor **não** troca o autor (`:184-208`) |
| `tests/test_d3b2_4_estatisticas.py` | 1 relevante | `test_n1_estats_constante` — guarda de N+1 da pauta (`:53`) |
| `tests/test_frequencia_oferta.py` | 1 relevante | Contrato de `carregar_frequencias` sempre devolver lista de temas (`:487-501`) |

**Impacto esperado:** os testes de catálogo, migration e não regressão continuam válidos com ajustes pequenos. Os testes de lançamento, obrigatoriedade, UI e engajamento precisam ser reescritos para o contrato por aula. O teste de autor (F1) continua relevante: alterar só o valor não deve trocar o autor.

---

## 8. Documentação, MER e backlog

| Documento | Referência | Conteúdo |
|---|---|---|
| MER — catálogo | `app/models/MER.md:424-439` | §7.5a `valor_esportista` |
| MER — frequência | `app/models/MER.md:750-776` | §7.19 `frequencia`, incluindo `valor_esportista_id` e a regra V2 |
| MER — diário | `app/models/MER.md:780-806` | §7.20 `registro_aula`; temas múltiplos e coluna espelho |
| MER — tabela de temas | `app/models/MER.md:808-815` | §7.20.1 `registro_aula_tema` |
| MER — regra transversal | `app/models/MER.md:1067-1075` | §8.1 frequência, valor adicional e obrigatoriedade |
| MER — engajamento | `app/models/MER.md:1249-1258` | §8.13 V3b |
| MER — migrations | `app/models/MER.md:1743` (A1), `:1749-1751` (head e produção) | `b7c8d9e0f1a2`; head `c1d2e3f4a5b6`; produção `c4d5e6f7a8b9` |
| Backlog — V2 | `backlog_desenvolvimento.md:321-328` | regra obrigatória, cliente, escopo, testes |
| Backlog — A1 | `backlog_desenvolvimento.md:356-369` | cadastro, lançamento, banco, testes |
| Relatório A1 | `docs/Relatórios/A1_ValoresDoEsportista.md:9-18`, `:24-42` | entrega, arquivos, decisões |
| Relatório V2 | `docs/Relatórios/V2_ValorObrigatorio.md:55-80` | implementação e testes antigo × novo |
| Relatório V3b | `docs/Relatórios/V3b_EngajamentoTurma.md:55-79` | serviço, consulta e template do engajamento |
| Prova de produção | `docs/Relatórios/AJ9B_ProvaProducao.md:119`, `:183`, `:251` | `valor_esportista` inexistente/0 no dump pré-A1 |
| Verificação | `docs/Relatórios/AJ13_Verificacao.md:135` | contagem 8 → 8 no banco local |

**Observação:** o MER já registra que a produção está em `c4d5e6f7a8b9` (`app/models/MER.md:1751`), coerente com o dump. A A1 pode ainda não estar aplicada na produção real.

---

## 9. Dados reais

### 9.1 Procedimento do clone

1. Worktree descartável criado a partir de `nova_feature` (`0e14fef`), sem branch nova.
2. Banco `pautaon_aj16a_clone` criado no PostgreSQL local.
3. Dump `instance/backups/pautaon_producao_2026-11-03.dump` restaurado no clone.
4. `flask db upgrade` executado até `c1d2e3f4a5b6`.
5. Consultas somente leitura executadas.
6. Clone removido; confirmado `count(*) = 0` em `pg_database` para `pautaon_aj16a_clone`.

### 9.2 Contagens do clone (dump de produção)

| Consulta | Resultado |
|---|---:|
| (a) linhas de `frequencia` com `valor_esportista_id` não nulo | **0** |
| (b) pares distintos `(turma_curso_id, data)` com algum valor | **0** |
| (c) pares com **mais de 1** valor distinto | **0** |
| (d) pares com **exatamente 1** valor distinto | **0** |
| (e) linhas em `valor_esportista` | **0** |
| Total de `frequencia` | **130** |
| Linhas de `frequencia` com `turma_curso_id IS NULL` | **0** |

**Interpretação:** o dump é anterior à A1 (`c4d5e6f7a8b9`), então zero é o esperado. O clone **não** serve para dimensionar a distribuição de produção do valor.

### 9.3 Contagens do `pautaon` local (pós-A1)

Revisão `c1d2e3f4a5b6`:

| Consulta | Resultado |
|---|---:|
| (a) linhas de `frequencia` com valor | **54** |
| (b) pares distintos `(turma_curso_id, data)` com valor | **6** |
| (c) pares com mais de 1 valor distinto | **6** |
| (d) pares com exatamente 1 valor distinto | **0** |
| (e) linhas em `valor_esportista` | **8** |
| Total de `frequencia` | **77** |
| Linhas com valor e `turma_curso_id IS NULL` | **0** |

Distribuição de valores distintos por par:

| Valores distintos no par | Quantidade de pares |
|---:|---:|
| 3 | 1 |
| 4 | 1 |
| 5 | 2 |
| 7 | 2 |

**Verificações de integridade para o backfill local:**

| Consulta | Resultado |
|---|---:|
| Pares com valor que possuem `RegistroAula` correspondente | **6 de 6** |
| `RegistroAula` duplicados por `(turma_curso_id, data)` | **0** |
| Total de `registro_aula` | **7** |
| `registro_aula` com `turma_curso_id` não nulo | **7** |

### 9.4 `pautaon_ensaio`

Revisão `c1d2e3f4a5b6`; todas as contagens (a)–(e) iguais a **0**; total de `frequencia` = **20**.

### 9.5 Leitura dos dados

- Os dados locais provam que **um valor por aula não representa a realidade**: todos os 6 pares têm de 3 a 7 valores distintos.
- O N:N na aula preserva o **conjunto** de valores por aula, mas **não** preserva qual aluno recebeu qual valor. Essa informação existe hoje em `frequencia.valor_esportista_id` e será perdida se a coluna for removida.
- No banco local, o backfill é tecnicamente seguro: todos os pares têm diário e não há diário duplicado. Em produção, isso ainda precisa ser verificado após a A1.

---

## 10. Modelo N:N proposto

### 10.1 Nome e forma

**Tabela:** `registro_aula_valor_esportista` (alternativa aceitável: `registro_aula_valor`).  
**Motivo:** segue o padrão `registro_aula_tema`, deixa explícito o domínio e evita ambiguidade com “valor” genérico.

```sql
CREATE TABLE registro_aula_valor_esportista (
    registro_aula_id     INTEGER NOT NULL,
    valor_esportista_id  INTEGER NOT NULL,
    CONSTRAINT pk_registro_aula_valor_esportista
        PRIMARY KEY (registro_aula_id, valor_esportista_id),
    CONSTRAINT fk_registro_aula_valor_esportista_registro
        FOREIGN KEY (registro_aula_id)
        REFERENCES registro_aula(id) ON DELETE CASCADE,
    CONSTRAINT fk_registro_aula_valor_esportista_valor
        FOREIGN KEY (valor_esportista_id)
        REFERENCES valor_esportista(id) ON DELETE RESTRICT
);

CREATE INDEX ix_registro_aula_valor_esportista_valor
    ON registro_aula_valor_esportista (valor_esportista_id);
```

**Decisões:**

| Decisão | Escolha | Justificativa |
|---|---|---|
| PK | composta `(registro_aula_id, valor_esportista_id)` | semântica de conjunto; impede duplicata; mesmo molde de `registro_aula_tema` |
| FK `registro_aula` | `ON DELETE CASCADE` | excluir o diário remove os vínculos; consistente com temas. **Risco:** hoje o valor sobrevive à exclusão do diário; isso muda |
| FK `valor_esportista` | `ON DELETE RESTRICT` | protege o catálogo; a aplicação só inativa, nunca apaga. Se um script tentar apagar valor em uso, falha explicitamente |
| Índice reverso | `valor_esportista_id` | agregações “quantas aulas usaram o valor X” e o engajamento |
| `unidade_id` na associativa | **não** | derivado de `registro_aula`/`turma`; validação de unidade fica na aplicação, como nos temas |
| `created_at`/autor | **não** | o molde de temas não tem; o `RegistroAula` já tem `instrutor_id` e auditoria |

### 10.2 Modelo SQLAlchemy (esboço, não implementado)

```python
# app/models/aulas.py
registro_aula_valor_esportista = db.Table(
    'registro_aula_valor_esportista',
    db.Column(
        'registro_aula_id', db.Integer,
        db.ForeignKey(
            'registro_aula.id',
            name='fk_registro_aula_valor_esportista_registro',
            ondelete='CASCADE',
        ),
        primary_key=True,
    ),
    db.Column(
        'valor_esportista_id', db.Integer,
        db.ForeignKey(
            'valor_esportista.id',
            name='fk_registro_aula_valor_esportista_valor',
            ondelete='RESTRICT',
        ),
        primary_key=True,
    ),
    db.Index(
        'ix_registro_aula_valor_esportista_valor',
        'valor_esportista_id',
    ),
)

class RegistroAula(...):
    ...
    valores = db.relationship(
        'ValorEsportista',
        secondary=registro_aula_valor_esportista,
        order_by='ValorEsportista.nome',
        lazy='selectin',
    )
```

**Alternativa:** manter `Frequencia.valor_esportista_id` como histórico por aluno e adicionar o N:N apenas para novas escritas. Nesse caso, a fase 2 **não** remove a coluna; ela vira legado somente leitura. Essa é a única forma de preservar o vínculo aluno↔valor.

### 10.3 Invariantes

1. Um `RegistroAula` pode ter 0..N valores.
2. Um valor pode estar em 0..N aulas.
3. Não há duplicata do mesmo par (PK).
4. Todo valor vinculado deve pertencer à unidade da turma/oferta do `RegistroAula`; a aplicação valida no write.
5. Valor inativo **já vinculado** continua sendo exibido e contado; valor inativo **novo** é recusado.
6. A ordem de exibição é estável (nome ou id).
7. A exclusão do `RegistroAula` remove os vínculos (CASCADE); a exclusão do valor é restrita (RESTRICT).

---

## 11. Migração em duas fases

### 11.1 Fase 0 — preflight somente leitura

Antes de qualquer DDL, rodar no banco alvo:

```sql
-- 1. Volume e distribuição atuais
SELECT count(*) FROM frequencia WHERE valor_esportista_id IS NOT NULL;
SELECT count(*) FROM (
  SELECT DISTINCT turma_curso_id, data
  FROM frequencia WHERE valor_esportista_id IS NOT NULL
) t;
SELECT turma_curso_id, data, count(DISTINCT valor_esportista_id) AS n
FROM frequencia WHERE valor_esportista_id IS NOT NULL
GROUP BY turma_curso_id, data
ORDER BY n DESC;

-- 2. Pares com valor mas sem RegistroAula (não backfilláveis)
SELECT count(*) FROM (
  SELECT DISTINCT f.turma_curso_id, f.data
  FROM frequencia f
  WHERE f.valor_esportista_id IS NOT NULL
    AND f.turma_curso_id IS NOT NULL
    AND NOT EXISTS (
      SELECT 1 FROM registro_aula r
      WHERE r.turma_curso_id = f.turma_curso_id AND r.data = f.data
    )
) t;

-- 3. RegistroAula duplicado por (oferta, data)
SELECT turma_curso_id, data, count(*) AS n
FROM registro_aula
WHERE turma_curso_id IS NOT NULL
GROUP BY turma_curso_id, data
HAVING count(*) > 1;

-- 4. Valores usados de unidade diferente da aula
SELECT count(*)
FROM frequencia f
JOIN registro_aula r
  ON r.turma_curso_id = f.turma_curso_id AND r.data = f.data
JOIN turma t ON t.id = r.turma_id
JOIN valor_esportista v ON v.id = f.valor_esportista_id
WHERE v.unidade_id <> t.unidade_id;

-- 5. Legado com valor (turma_curso_id IS NULL)
SELECT count(*) FROM frequencia
WHERE valor_esportista_id IS NOT NULL AND turma_curso_id IS NULL;
```

**Critérios de bloqueio para a fase 2:**

- pares com valor e sem `RegistroAula` > 0;
- `RegistroAula` duplicado por `(oferta, data)` > 0;
- valores de unidade divergente > 0;
- legado com valor > 0 sem tratamento definido.

### 11.2 Fase 1 — expandir e backfillar

**Migration (aditiva, reversível):**

1. Criar `registro_aula_valor_esportista` e o índice reverso.
2. Backfill dos vínculos de oferta:

```sql
INSERT INTO registro_aula_valor_esportista
    (registro_aula_id, valor_esportista_id)
SELECT DISTINCT r.id, f.valor_esportista_id
FROM frequencia f
JOIN registro_aula r
  ON r.turma_curso_id = f.turma_curso_id
 AND r.data = f.data
WHERE f.valor_esportista_id IS NOT NULL
  AND f.turma_curso_id IS NOT NULL
ON CONFLICT DO NOTHING;
```

3. Backfill do legado:

```sql
INSERT INTO registro_aula_valor_esportista
    (registro_aula_id, valor_esportista_id)
SELECT DISTINCT r.id, f.valor_esportista_id
FROM frequencia f
JOIN registro_aula r
  ON r.turma_id = f.turma_id
 AND r.data = f.data
 AND r.turma_curso_id IS NULL
WHERE f.valor_esportista_id IS NOT NULL
  AND f.turma_curso_id IS NULL
ON CONFLICT DO NOTHING;
```

**Se houver `RegistroAula` duplicado por par:** escolher um canônico (`MIN(r.id)`) e registrar os pares afetados; não criar vínculos em todos os diários duplicados, para não inflar o engajamento. Exemplo portátil com `ROW_NUMBER()`:

```sql
WITH candidatos AS (
  SELECT f.turma_curso_id, f.data, f.valor_esportista_id,
         r.id AS registro_aula_id,
         ROW_NUMBER() OVER (
           PARTITION BY f.turma_curso_id, f.data, f.valor_esportista_id
           ORDER BY r.id
         ) AS rn
  FROM frequencia f
  JOIN registro_aula r
    ON r.turma_curso_id = f.turma_curso_id AND r.data = f.data
  WHERE f.valor_esportista_id IS NOT NULL
    AND f.turma_curso_id IS NOT NULL
)
INSERT INTO registro_aula_valor_esportista
    (registro_aula_id, valor_esportista_id)
SELECT registro_aula_id, valor_esportista_id
FROM candidatos
WHERE rn = 1
ON CONFLICT DO NOTHING;
```

**Se houver par com valor e sem `RegistroAula`:** **não** criar diário artificial automaticamente. Manter o valor antigo na coluna congelada e registrar a pendência. A fase 2 só pode ocorrer quando esse número for zero (ou quando a decisão de produto aceitar a perda).

**Aplicação na fase 1:**

- **Leitura:** preferir `RegistroAula.valores`. Se o conjunto novo estiver vazio, fazer fallback na coluna antiga: agrupar `frequencia.valor_esportista_id` distintos do par e exibir como selecionados.
- **Escrita:** gravar **somente** no N:N. A coluna antiga fica **congelada** (não é mais escrita). Isso evita divergência e deixa claro que o novo modelo é a fonte.
- **Validação:** valores selecionados precisam existir, estar ativos (ou já vinculados àquela aula) e pertencer à unidade da turma.
- **Temas:** o padrão de substituição do conjunto (`registro.valores = ...`) é o mesmo de `registro.temas`.
- **Engajamento:** ler do N:N, com escopo por `RegistroAula` (oferta/data) e regra D2 para legado.
- **Template/JS:** grupo único de valores da aula; a validação de obrigatoriedade passa a ser da aula.

**Verificação pós-backfill:**

```sql
-- Conjunto antigo por par (distinct) deve ser igual ao novo
WITH antigo AS (
  SELECT turma_curso_id, data, valor_esportista_id
  FROM frequencia
  WHERE valor_esportista_id IS NOT NULL AND turma_curso_id IS NOT NULL
  GROUP BY turma_curso_id, data, valor_esportista_id
),
novo AS (
  SELECT r.turma_curso_id, r.data, rave.valor_esportista_id
  FROM registro_aula_valor_esportista rave
  JOIN registro_aula r ON r.id = rave.registro_aula_id
  WHERE r.turma_curso_id IS NOT NULL
)
SELECT 'faltando_no_novo', count(*) FROM (
  SELECT * FROM antigo EXCEPT SELECT * FROM novo
) t
UNION ALL
SELECT 'sobrando_no_novo', count(*) FROM (
  SELECT * FROM novo EXCEPT SELECT * FROM antigo
) t;
```

Resultado esperado: `0` e `0` (para os pares backfilláveis).

### 11.3 Fase 2 — contrair e remover a coluna antiga

Pré-condições:

1. Fase 1 em produção há pelo menos um ciclo de uso.
2. Preflight da §11.1 sem bloqueios.
3. Verificação da §11.2 com `0` e `0`.
4. Nenhum código lendo `Frequencia.valor_esportista_id` (grep + testes).
5. Backup do banco (ou tabela de retenção com `frequencia.id`, `aluno_id`, `turma_curso_id`, `data`, `valor_esportista_id`) guardado para rollback.

Migration de contração:

1. `DROP INDEX ix_frequencia_valor_esportista`.
2. `ALTER TABLE frequencia DROP CONSTRAINT fk_frequencia_valor_esportista`.
3. `ALTER TABLE frequencia DROP COLUMN valor_esportista_id`.
4. Remover `Frequencia.valor_esportista` do modelo.
5. Remover o fallback de leitura e o parsing legado.

**Rollback:** o downgrade da fase 2 recria a coluna, mas **não** consegue restaurar o vínculo aluno↔valor, porque essa informação não existe no N:N. O downgrade só é seguro com a tabela de retenção/backup. Documentar isso explicitamente no docstring da migration.

### 11.4 Revisão Alembic

- A nova migration entra **depois do head atual** `c1d2e3f4a5b6` (`app/models/MER.md:1749-1751`).
- A produção está em `c4d5e6f7a8b9`; há 24 revisões pendentes até o head atual. A migration do valor deve ser escrita para rodar nessa cadeia, sem assumir que a A1 já está aplicada em produção.
- Fase 1 e fase 2 devem ser **duas migrations separadas** (ou uma migration com `downgrade` que só remove a tabela nova), para permitir o intervalo de verificação.

---

## 12. Impacto por arquivo

| Arquivo | Mudança | Fase |
|---|---|---|
| `app/models/aulas.py` | Adicionar `registro_aula_valor_esportista` e `RegistroAula.valores`; manter a coluna antiga | 1 |
| `app/models/aulas.py` | Remover `Frequencia.valor_esportista_id` e `Frequencia.valor_esportista` | 2 |
| `app/models/pedagogico.py` | Ajustar docstring do catálogo (o valor deixa de ser “por aluno”); sem mudança de schema | 1 |
| `app/models/__init__.py` | Nenhuma mudança obrigatória (a tabela associativa não é exportada) | — |
| `app/utils/logica.py` | `_ler_registros_aula`: ler `RegistroAula.valores`; fallback na coluna antiga | 1 |
| `app/utils/logica.py` | `carregar_frequencias_e_valores`: devolver `valores_aula` (lista) em vez de `{aluno_id: valor}` | 1 |
| `app/utils/logica.py` | Substituir `_resolver_valor_esportista` por resolução/validação de lista; `_planejar_frequencia` deixa de resolver valor por aluno | 1 |
| `app/utils/logica.py` | `salvar_frequencia`: parse de `valor_ids`, validação antes da escrita e `registro.valores = ...` | 1 |
| `app/utils/logica.py` | Remover fallback/coluna antiga | 2 |
| `app/registros/core.py` | `POST`: parse de `valor_ids`; manter filtro de alunos; a pendência agora é da aula | 1 |
| `app/registros/core.py` | `GET`: passar `valores_aula`/`valores_selecionados`; manter `valores_esportista_ativos` | 1 |
| `app/registros/core.py` | Remover parsing de `postura_aluno_*` e fallback | 2 |
| `app/templates/frequencia/lancar.html` | Trocar o select por aluno por um grupo único de valores (checkboxes `valor_ids` ou select múltiplo), ao lado dos temas | 1 |
| `app/templates/frequencia/lancar.html` | Remover o bloco antigo | 2 |
| `app/static/js/frequencia.js` | Validação da aula: “há A–D e nenhum valor marcado”; remover lógica por aluno | 1 |
| `app/services/engajamento_turma.py` | Agregar `registro_aula_valor_esportista` + `RegistroAula`, com escopo por oferta e D2 | 1 |
| `app/main/dashboard_professor.py` | Sem mudança de assinatura; apenas consome o serviço | 1 |
| `app/templates/dashboard/painel_pedagogico.html` | Ajustar rótulo/rodapé para “aulas com valor” | 1 |
| `app/models/MER.md` | Nova seção da tabela, §7.19/§7.20/§8.1/§8.13 e tabela de migrations | 1/2 |
| `backlog_desenvolvimento.md` | Registrar a migração e as decisões | 1/2 |
| `docs/Relatórios/` | Relatório de implementação futura | 1/2 |
| `tests/test_valor_esportista_lancamento.py` | Reescrever para o contrato por aula | 1 |
| `tests/test_valor_obrigatorio.py` | Reescrever a regra para nível de aula | 1 |
| `tests/test_valor_obrigatorio_ui.py` | Reescrever o teste do JS/template | 1 |
| `tests/test_valor_obrigatorio_caracterizacao.py` | Nova caracterização antigo × novo (por aluno × por aula) | 1 |
| `tests/test_valor_esportista_nao_regressao.py` | Ajustar o preparo dos dados; as comparações de saída continuam | 1 |
| `tests/test_v3b_engajamento_turma.py` | Trocar a semente de linhas de frequência por vínculos de aula | 1 |
| `tests/test_planejamento_abas.py` | Sem mudança de comportamento; revisar se o catálogo mudou | — |
| `tests/test_lancar_template_estrutura.py` | Atualizar o contexto fake (`valores_aula`) | 1 |
| `tests/test_f1_autor_lancamento.py` | Continua válido; só o preparo do valor muda | 1 |
| `tests/test_d3b2_4_estatisticas.py` | Continua como guarda de N+1 | 1 |

---

## 13. Critérios de aceite para a implementação futura

1. **Catálogo:** criar/editar/inativar valor continua igual; nome único por unidade sem case; Visão Global somente leitura.
2. **Leitura da pauta:** valores da aula aparecem marcados; valores antigos (sem N:N) aparecem via fallback; nenhum dado por aluno é exibido à toa.
3. **Escrita:** A–D com catálogo ativo e nenhum valor selecionado → 302, mensagem e **nenhuma** gravação (conceitos, diário, temas, valores).
4. **Escrita:** A–D com valores selecionados → conceitos + `RegistroAula` + vínculos N:N no mesmo commit.
5. **Substituição:** reeditar a aula substitui o conjunto de valores (não acumula duplicatas); dedupe no servidor.
6. **Inativo:** valor inativo já vinculado continua exibido e contado; valor inativo novo é recusado; valor de outra unidade é recusado.
7. **F/J/sem conceito:** a obrigatoriedade não se aplica; a política de manter/limpar valores deve ser a decidida em §14.
8. **Engajamento:** conta vínculos de aula, respeita oferta e D2; não mostra dado por aluno; rótulo/rodapé coerentes.
9. **Não regressão:** pauta impressa, relatório de frequência, XLSX, BI, diário, ficha/histórico, certificado e conselho permanecem idênticos com e sem valor.
10. **Performance:** a pauta não ganha N+1; o engajamento continua em uma consulta agregada.
11. **Migration fase 1:** upgrade/downgrade preservam a coluna antiga e todos os dados; backfill idempotente; verificação `0/0`.
12. **Migration fase 2:** só roda com preflight limpo; downgrade documenta a perda do vínculo aluno↔valor; retenção/backup disponível.
13. **Grep final:** nenhuma referência a `Frequencia.valor_esportista_id`/`Frequencia.valor_esportista` no código após a fase 2.

---

## 14. Decisões pendentes (produto/negócio)

1. **Perda do vínculo aluno↔valor:** o pedido é mover para a aula. Isso aceita que o histórico por aluno deixe de existir? Se **não**, a alternativa é manter a coluna antiga como histórico somente leitura (fase 2 não remove) e usar o N:N apenas para novas escritas.
2. **Escopo da obrigatoriedade:** “pelo menos um valor por aula com qualquer A–D” ou “um valor por aluno com A–D”? A primeira é a única compatível com o N:N na aula; a segunda exigiria manter o vínculo por aluno.
3. **Aula sem presença:** se todos forem F/J ou não houver conceito, os valores selecionados devem ser **preservados** (histórico do conteúdo) ou **limpos** (regra atual limpa por aluno)? Recomendação: preservar, porque o valor descreve a aula, não a presença.
4. **Valor inativo:** permitir manter no conjunto se já vinculado (recomendado) e recusar novo inativo. Confirmar.
5. **Engajamento:** o rótulo “Baseado em N registros de presença com valor” deixa de ser verdadeiro; trocar para “Baseado em N aulas com valor” e confirmar se o percentual deve ser sobre aulas ou sobre vínculos.
6. **Exclusão de diário:** com `CASCADE`, excluir o `RegistroAula` apaga os vínculos de valor. Hoje o valor por aluno sobrevive. Confirmar se é aceitável; se não, usar `RESTRICT` ou mover os vínculos antes da exclusão.
7. **Diário duplicado por (oferta, data):** não há unique constraint; o backfill precisa escolher um canônico. Confirmar se a fase 1 deve também criar um índice único parcial (após limpeza) ou apenas registrar o problema.
8. **Par com valor e sem diário:** manter o valor antigo congelado e bloquear a fase 2 até resolver, ou criar `RegistroAula` mínimo? Recomendação: não criar diário artificial; bloquear a fase 2.
9. **Legado `turma_curso_id IS NULL`:** o backfill por `turma_id`/`data` só é seguro quando a oferta é única/legada. Confirmar a regra D2 para valores (a mesma de frequência/engajamento).

---

## 15. Conclusão

A regra atual é pequena e bem isolada: um catálogo por unidade, um FK nullable em `frequencia`, um caminho de escrita, dois leitores de produção e uma regra de obrigatoriedade por aluno. O molde N:N dos temas já cobre todos os padrões necessários (tabela associativa, PK composta, FKs, `lazy='selectin'`, substituição do conjunto, backfill e coluna espelho temporária).

A migração é viável, mas **não é uma troca mecânica**: o valor deixa de ser um atributo do aluno e passa a ser um atributo da aula. Os dados locais mostram que essa mudança preserva o conjunto (3–7 valores por aula), mas perde o vínculo valor↔aluno. A obrigatoriedade e o engajamento precisam ser redefinidos nesse novo nível. A produção ainda está antes da A1, então a distribuição real só poderá ser medida depois da A1 (ou com um dump posterior).

O caminho recomendado é: **fase 1 aditiva** (tabela N:N + backfill + leitura nova com fallback + escrita só no N:N, coluna antiga congelada), **verificação** e, só então, **fase 2** (remoção da coluna), com retenção/backup e documentação explícita da perda do vínculo por aluno.

---

## Apêndice A — Referências rápidas

- Modelo do catálogo: `app/models/pedagogico.py:63-100`.
- FK atual: `app/models/aulas.py:136-145`; relação: `:165`.
- Tabela/relação de temas: `app/models/aulas.py:48-67`, `:230-233`.
- Escrita: `app/utils/logica.py:501-546`, `:590-649`, `:652-818`.
- Leitura da pauta: `app/utils/logica.py:391-423`, `:471-498`.
- Rota: `app/registros/core.py:221-404`, `:546-554`, `:606-617`, `:675-699`.
- Template da pauta: `app/templates/frequencia/lancar.html:52-61`, `:167-185`, `:279-303`.
- JS: `app/static/js/frequencia.js:15-28`, `:73-104`, `:124-162`.
- Engajamento: `app/services/engajamento_turma.py:53-107`; `app/main/dashboard_professor.py:334-343`; `app/templates/dashboard/painel_pedagogico.html:299-332`.
- Migrations: `migrations/versions/b7c8d9e0f1a2_valor_esportista.py:39-126`; `migrations/versions/a8b9c0d1e2f3_registro_aula_multiplos_temas.py:19-45`.
- MER: `app/models/MER.md:424-439`, `:750-776`, `:780-815`, `:1067-1075`, `:1249-1258`, `:1743`, `:1749-1751`.
- Backlog: `backlog_desenvolvimento.md:321-328`, `:356-369`.
- Testes: ver §7.
- Dados: ver §9.
