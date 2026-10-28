# A1 — Valores do Esportista (implementação)

**Data:** 28/10/2026
**Escopo:** catálogo "Valores do Esportista" no planejamento + escolha por aluno/aula na pauta de frequência.
**Regra crítica:** o valor é **dado adicional**. Não participa de conceito, presença, falta, justificadas, `total_aulas`, `estats_freq`, pauta impressa, diário de classe, relatórios ou exportações.

## 1. O que foi entregue

| Camada | Entrega |
|---|---|
| Banco | `valor_esportista` (id, nome ≤100, ativo, unidade_id, timestamps) + `frequencia.valor_esportista_id` (nullable, FK `ON DELETE SET NULL`, índice) |
| Migration | `b7c8d9e0f1a2` (revises `8d2e3f4a5b6c`), reversível, sem backfill |
| Cadastro | `POST /planejamento` com `tipo_post="valor"` (campo `nome_valor`), `POST /planejamento/valor/editar/<id>`, `POST /planejamento/valor/inativar/<id>` |
| Pauta | select `postura_aluno_<id>` por aluno, habilitado só em A/B/C/D |
| Persistência | `salvar_frequencia` → `_resolver_valor_esportista` |
| Leitura | `carregar_frequencias_e_valores` (mesma consulta de `frequencia`, `joinedload`) |
| JS | `tratarConceitoAluno` e estado inicial movidos para `static/js/frequencia.js` |
| Abas | pills do Planejamento refletem `?aba=` — salvar mantém a aba e os filtros da lista (§9) |

## 2. Arquivos alterados

**Novos**

- `migrations/versions/b7c8d9e0f1a2_valor_esportista.py`
- `tests/test_valor_esportista.py` (10 testes)
- `tests/test_valor_esportista_lancamento.py` (19 testes)
- `tests/test_valor_esportista_nao_regressao.py` (4 testes)
- `tests/test_valor_esportista_migration.py` (5 testes)
- `tests/test_planejamento_abas.py` (10 testes) — aba ativa e filtros após salvar (§9)

**Modificados**

- `app/models/pedagogico.py` — modelo `ValorEsportista` (+ docstring de módulo)
- `app/models/aulas.py` — coluna/relationship em `Frequencia` + nota A1
- `app/models/__init__.py` — export de `ValorEsportista`
- `app/registros/core.py` — rotas de cadastro, GET do planejamento, GET/POST da pauta; helper `_voltar_planejamento` (§9)
- `app/utils/logica.py` — `carregar_frequencias_e_valores`, `_resolver_valor_esportista`, gravação em `salvar_frequencia`
- `app/templates/planejamento/planejamento.html` — aba/pill/KPIs/formulário; estado ativo por `aba_ativa` (§9)
- `app/templates/frequencia/lancar.html` — select por aluno + `selected`/`disabled`
- `app/static/js/frequencia.js` — `tratarConceitoAluno` + estado inicial
- `app/models/MER.md` — §6.3, §7.5a, §7.19, §8.1, §9.3, §11
- `backlog_desenvolvimento.md` — entrada do dia

## 3. Decisões onde o projeto não tinha convenção

1. **`ValorEsportista.unidade_id` NOT NULL.** `Nivel` aceita `NULL` (legado), mas `Curso`/`CentroCusto` são NOT NULL. Como o valor é criado/gerido dentro de uma unidade, seguiu-se o padrão estrito: sem "valor global" e Visão Global somente leitura.
2. **Unicidade case-insensitive no banco e no backend.** O projeto só tinha UNIQUE simples (`uq_nivel_nome_unidade`). Aqui foi usado índice funcional `lower(nome)` + `unidade_id` **e** validação `func.lower` na rota, para devolver mensagem amigável antes do `IntegrityError` (que também é tratado).
3. **Não apagar com uso.** Não existe convenção de "delete bloqueado" no projeto; a rota `inativar_valor` só alterna `ativo` e o `ON DELETE SET NULL` protege o histórico caso alguém remova pela força.
4. **Leitura do valor junto da frequência.** `carregar_frequencias` tem contrato de 3 valores usado em vários chamadores e no teste de N+1. Em vez de uma segunda consulta, foi criada `carregar_frequencias_e_valores` (4 valores) que reaproveita a leitura de `frequencia` via `joinedload`. Resultado: o teste `test_n1_estats_constante` (limite de 2 consultas em `frequencia`) continua passando sem alteração.
5. **Valor inativo já salvo.** O POST aceita o id inativo **quando é o valor já gravado** (`valor_atual_id`), preservando o histórico ao reabrir e salvar; qualquer outro id inativo é descartado.
6. **Ausência do campo.** Sem `postura_aluno_<id>` (select desabilitado), a coluna não é tocada em alunos sem conceito no POST — o conceito e o valor existentes permanecem.
7. **JS.** O projeto já carregava `static/js/frequencia.js`; o `onchange` inline chamava uma função que vivia em `<script>` no template. A função foi movida para o arquivo estático e o `<script>` inline removido.

## 4. Divergências de nomenclatura no pedido

- O pedido cita `app/templates/frequencia/frequencia.html`; o arquivo real é `app/templates/frequencia/lancar.html` (é o template renderizado por `registros.frequencia`).
- O pedido cita `app/routes/registros*`; o blueprint `registros` está em `app/registros/` (`core.py`, `alunos.py`, etc.).
- O pedido cita um atributo `percentuais`/`estats_freq`; no código o objeto é `aluno.estats_freq` (com `.presenca`, `.falta`, `.justificada`, `.justificadas`, `.total_aulas`), montado na rota a partir de `calcular_estatisticas_frequencia`.

## 5. Testes

**Baseline (antes):** 735 passed, 0 falhas.
**Depois da feature:** 773 passed, 0 falhas (735 + 38 novos). **Nenhum teste existente foi alterado.**
**Total final (com a correção de abas, §9):** **783 passed** (773 + 10).

Cobertura por arquivo:

- `test_valor_esportista.py` — cria/edita/inativa/reativa; nome vazio, duplicado sem case, >100; renomeação duplicada recusada; professor 403; CSRF real 400; isolamento por unidade (não vê, não edita, não inativa); Visão Global não cria; KPI/aba/pill com painel dentro de `.tab-content` (verificação estrutural com `HTMLParser`).
- `test_valor_esportista_lancamento.py` — persiste em A/B/C/D; F e J limpam; valor com F/J/sem conceito ignorado; outra unidade/inexistente ignorados sem derrubar a pauta; inativo já salvo preservado no GET (`(inativo)`) e no POST; sem campo não apaga conceito; secretaria 403 e `select` `disabled`; aluno transferido não recebe nada; duas ofertas gravam na oferta correta; `estats_freq` idêntico com e sem valor; estado inicial do `select` (disabled/enabled).
- `test_valor_esportista_nao_regressao.py` — pauta completa e do mês idênticas; `frequencia_relatorio` idêntico; XLSX de `/relatorios/exportar` idêntico (comparação do pacote OOXML, sem `openpyxl`); registro antigo com `NULL` carrega.
- `test_valor_esportista_migration.py` — upgrade preserva linhas/conceitos e não faz backfill; unicidade sem case; downgrade remove só a feature; reaplicar upgrade após downgrade; DDL do PostgreSQL (`MockEngine`) com `ON DELETE SET NULL` e downgrade sem apagar dados.

## 6. Bugs adjacentes encontrados (não corrigidos)

- `app/templates/frequencia/lancar.html` tem **um `<div>` sem fechamento** (31 aberturas × 30 fechamentos). Já era assim no `HEAD` — o defeito não foi introduzido por esta feature.
- `tmpo89fzd1t` (arquivo vazio) na raiz do projeto: artefato de execução de teste, não rastreado pelo git.
- `docs/erros MD/Erro.md` está deletado no working tree (não por esta feature) e `app/templates/periodos/calendario.html` tem alteração pré-existente fora do escopo.
- `ruff check` do repositório acusa ressalvas pré-existentes de `F401`; `F821`/`F811` estão limpos em `app`, `tests` e `migrations`.

## 7. Como validar manualmente

1. Login como admin/pedagógico da unidade → **Planejamento → aba Valores** → criar, renomear e inativar.
2. Abrir `Frequência`, escolher turma e data: o select do aluno começa desabilitado.
3. Marcar A/B/C/D → select habilita; escolher valor → **Salvar** → reabrir e conferir o `selected`.
4. Trocar para F ou J → select desabilita e o valor é limpo ao salvar.
5. Conferir que os cartões de presença/falta/aulas e a pauta impressa não mudam.

## 8. Aplicação da migration no banco principal (28/10/2026)

**Sintoma (app contra o banco `pautaon`):**

```
sqlalchemy.exc.ProgrammingError: (psycopg.errors.UndefinedTable)
relação "valor_esportista" não existe
[SQL: SELECT valor_esportista.id ... FROM valor_esportista ORDER BY lower(valor_esportista.nome)]
```

**Causa:** a app roda com o `DATABASE_URL` do `.env` (banco `pautaon`), que ainda estava na revisão `8d2e3f4a5b6c` — a migration `b7c8d9e0f1a2` não havia sido aplicada. Não era defeito de código: o modelo já esperava a tabela.

**Procedimento executado**

1. **Backup do principal** (antes de qualquer DDL): `instance/backups/pautaon_pre_A1_valores_esportista.sql` (550 KB, `pg_dump` exit 0).
2. **Ensaio primeiro** (`pautaon_ensaio`, PostgreSQL real): upgrade `8d2e3f4a5b6c → b7c8d9e0f1a2`; conferência de tabela, coluna, FK e índices; **downgrade** `b7c8d9e0f1a2 → 8d2e3f4a5b6c`; **re-upgrade** — ciclo completo sem erro, provando a reversibilidade no dialeto de produção.
3. **Principal:** `flask db upgrade` → `Running upgrade 8d2e3f4a5b6c -> b7c8d9e0f1a2`.

**Conferência no `pautaon` (SQL direto, não apenas `flask db current`)**

| Verificação | Resultado |
|---|---|
| `alembic_version` | `b7c8d9e0f1a2` |
| `to_regclass('public.valor_esportista')` | `valor_esportista` |
| `frequencia.valor_esportista_id` | existe, nullable |
| FK | `fk_frequencia_valor_esportista ... ON DELETE SET NULL` |
| índices | `ix_frequencia_valor_esportista`, `uix_valor_esportista_nome_unidade` |
| `frequencia` | **24 linhas**, 0 com valor (sem backfill) |
| `valor_esportista` | 0 linhas (catálogo começa vazio) |

**Incidente durante a operação (registrado para não repetir):** o primeiro `flask db upgrade` foi executado com `$env:DATABASE_URL` ainda apontando para `pautaon_ensaio` — variável definida em comandos anteriores e **persistida na sessão** do PowerShell. O comando terminou sem erro (o ensaio já estava no head) e o `flask db current` “confirmou” o banco errado. Correção: redefinir `$env:DATABASE_URL` a partir do `.env` no mesmo comando, imprimir o alvo mascarado e validar o resultado por consulta SQL independente em `alembic_version`/`information_schema`. Nenhum DDL foi aplicado no principal antes dessa correção.

**Pós-condições:** schema do principal na head; linhas históricas de `frequencia` intactas com valor `NULL`; app volta a renderizar Planejamento e Frequência sem reiniciar código (só recarregar a página/reciclar o worker, se houver pool antigo).

## 9. Aba ativa após salvar no Planejamento (UX)

**Sintoma:** qualquer escrita no Planejamento (criar/editar/inativar tema, nível ou valor) recarregava a página na aba **Temas**, independentemente da aba usada.

**Causa:** as pills do Bootstrap vivem só no DOM (`data-bs-target`), nunca na URL; as 11 saídas de escrita faziam `redirect(url_for('registros.planejamento'))` e o template tinha `active`/`show active` fixos em Temas. O defeito era anterior à feature de Valores (atingia temas e níveis).

**Solução adotada (A — querystring + render no servidor):**

- Helper `_voltar_planejamento()` (`app/registros/core.py`) substitui os 11 `redirect(...)`: lê o hidden `aba` e o contexto da lista (`filtro_curso`, `filtro_q`, `filtro_page`) **sempre por whitelist/validação**; aba inválida → redirect limpo para a aba padrão (Temas).
- `GET /planejamento` calcula `aba_ativa` a partir de `?aba=` (`temas|valores|niveis`, default `temas`) e passa ao template.
- `planejamento.html`: pills e painéis recebem `active`/`show active` conforme `aba_ativa`; os 9 formulários (criar/editar/inativar de tema, nível e valor) ganham o hidden `aba`; os 3 da aba Temas também carregam os filtros da lista.
- Sem JavaScript adicional, sem estado em sessão e sem fragmento na URL — a URL passa a refletir a aba (`/planejamento?aba=valores`), o que também permite favoritar.

**Escopo preservado:** nenhuma rota, permissão, CSRF ou regra de negócio mudou; o comportamento de `GET /planejamento` sem parâmetro continua idêntico (aba Temas).

**Arquivos alterados**

- `app/registros/core.py` — helper `_voltar_planejamento()` (substitui os 11 redirects) e `aba_ativa` no GET.
- `app/templates/planejamento/planejamento.html` — pills/painéis condicionais, hidden `aba` nos 9 formulários e `filtro_curso`/`filtro_q`/`filtro_page` nos 3 da aba Temas.
- `tests/test_planejamento_abas.py` — 10 testes novos.
- `app/models/MER.md` §9.3 e `backlog_desenvolvimento.md` — convenção e diário.

**Interação com a feature:** o formulário de criação de valor já envia `aba=valores`; por isso, cadastrar um valor agora retorna à aba Valores do Esportista, e não mais à aba Temas.

**Replicação:** o mesmo padrão foi aplicado às abas do Conselho de Perguntas (`?etapa=...&foco=...`), com convenção em MER §9.3 e relatório próprio em `docs/Relatórios/UI_AbasPersistentes.md`.

**Testes:** `tests/test_planejamento_abas.py` (10) — criar/editar/inativar nas três abas devolve `?aba=` correto e só a pill/painel da aba fica ativo; criar tema mantém redirect limpo; filtros `curso_id`/`q`/`page` voltam aplicados; `?aba=inválida` e ausência caem em Temas. Suíte: **773 → 783 passed**, nenhum teste existente alterado.
