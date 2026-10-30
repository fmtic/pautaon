# ETAPA B3 — Isolamento de unidade corrigido em `editar_curso`; suíte 100% verde

Data: 25/10/2026 · Ramo: `Onda4` · Escopo alterado: **apenas `app/registros/core.py`** (função `editar_curso`) · Testes: nenhum alterado · **Nenhum commit foi feito.**

Decisão do responsável que orienta a etapa: **o isolamento por unidade vale para TODOS os perfis, inclusive ADMIN e GERENCIA** (eles escolhem a unidade após o login; Visão Global é **somente leitura**).

---

## 1. Leitura prévia (Passo 1)

- **`editar_curso`** (`app/registros/core.py:599-646`, antes): lista de papéis autorizados (ADMIN/PEDAGOGICO/SECRETARIA/GERENCIA) e, em **L606-607**, `if current_user.role not in (UserRole.ADMIN, UserRole.GERENCIA): assert_unidade_context(...)` — a isenção investigada na B2 (pendência R1): admin com sessão na unidade A recebia **200 e gravava** em curso de outra unidade; sem unidade na sessão, editava qualquer curso.
- **Vizinhas** (mesma blueprint):
  - `listar_cursos` (L513-530) e `listar_cursos_inativos` (L533-552): **filtro por unidade incondicional** (`filter_by(unidade_id=unidade_id)`), `abort(403)` sem unidade na sessão — inclusive para admin.
  - `novo_curso` (L555-596): cria sempre na unidade da sessão; sem unidade → **400** (`'Usuário sem unidade definida.'`).
  - `inativar_curso` (L649-676) e `reativar_curso` (L679-...): `assert_unidade_context(curso.unidade_id, unidade_id)` **sem qualquer isenção de papel** — o modelo a seguir.
- **Teste** `test_cursos_exigem_unidade_e_isolam_cursos_de_outra_unidade` (`tests/test_security_regressions.py:471-495`) + semente `_criar_admin_cursos` (L435-468): admin único, 2 unidades, curso A (un. A) e curso B (un. B), sessão com `unidade_id=A`. Asserções: `POST /cursos/B/editar` → 403 (L482) · `POST /cursos/B/inativar` → 403 · após `sess.pop("unidade_id")`: `GET /cursos` → 403, `POST /cursos/novo` → 400, `POST /cursos/A/editar` → **403** (L492-494), `POST /cursos/A/inativar` → 403.

## 2. Correção (Passo 2) — diff

**`app/registros/core.py` (+4/−2)**, única mudança:

```diff
     unidade_id = get_unidade_id()
     curso = db.get_or_404(Curso, curso_id)
-    if current_user.role not in (UserRole.ADMIN, UserRole.GERENCIA):
-        assert_unidade_context(curso.unidade_id, unidade_id)
+    # ETAPA B3: isolamento por unidade vale para todos os perfis, inclusive
+    # ADMIN/GERENCIA (que escolhem a unidade após o login; Visão Global é
+    # somente leitura). Igual a inativar_curso/reativar_curso.
+    assert_unidade_context(curso.unidade_id, unidade_id)
     if not curso.ativo:
```

Nada mais tocado: a lista de papéis autorizados (L602) permanece (GERENCIA continua podendo editar, antes do 409/400/200), a resposta de sucesso é idêntica, e `assert_unidade_context` já implementa a recusa pedida — `unidade_id is None` (Visão Global sem unidade escolhida) → **403**, exatamente como `inativar`/`reativar`. Sem unidade na sessão, o comportamento de `editar` agora coincide com as vizinhas.

## 3. Testes (Passo 3 + suíte)

- `tests/test_security_regressions.py` isolado: **23 passed** (antes 21/2). O teste de isolamento passou **sem nenhuma alteração de teste** — inclusive as asserções internas de "sem unidade na sessão" (L490-495): com o `assert` unconditional, `POST /cursos/<A>/editar` sem unidade → 403 pelo `unidade_id is None` do `assert_unidade_context`, o que o teste já esperava (nunca precisei tocar o teste; a falha da B2 vinha só da isenção).
- `test_curso_criar_editar_inativar` (edição legítima com sessão na unidade A, admin) continua 200 → a remoção da isenção não quebrou o fluxo normal.
- **Suíte completa:** `$env:PYTHONPATH="."; .\.venv\Scripts\python.exe -m pytest tests -q --tb=line` → **`221 passed, 42 warnings in 27.43s`** — **meta de 0 falhas atingida** (B1: 3 falhas → B2: 1 → B3: 0).
- Lint: `ruff check app/registros/core.py` acusou 16 ocorrências **pré-existentes** (E711/E712 etc. em outros trechos); **zero** nas linhas 600-612 que editei. CRLF/estrutura do arquivo preservados (edição por substituição puntual).

## 4. Auditoria (Passo 4) — SOMENTE LEITURA: isenções de unidade para ADMIN/GERENCIA em rotas de escrita

Nenhuma das linhas abaixo foi corrigida. Padrões encontrados: **(A)** `if role != ADMIN: assert_unidade_context(...)` (isenção explícita) · **(B)** `if unidade_id and obj.unidade_id != unidade_id:` / `unidade_id is not None` — filtro **condicional ao contexto**, que só admin/gerência podem deixar vazio (`get_unidade_id` devolve None apenas para eles, `app/utils/logica.py:179-192`) · **(C)** recursos sem dimensão de unidade ou gestão global.

| # | Arquivo:linha | Rota (método) | Padrão | Classificação |
|---|---|---|---|---|
| 1 | `app/registros/core.py:764-765` | `POST /planejamento` (criar TemaAula) | A — admin cria tema em curso de qualquer unidade | **Suspeito** — mesmo vício do `editar_curso` corrigido; tema herda `unidade_id` do curso |
| 2 | `app/registros/core.py:889-892` | `POST /planejamento/tema/editar/<id>` | A | **Suspeito** |
| 3 | `app/registros/core.py:935-938` | `POST /planejamento/tema/inativar/<id>` | A | **Suspeito** |
| 4 | `app/registros/core.py:961-965` | `POST /planejamento/nivel/editar/<id>` | A — Nivel **tem** `unidade_id` (criação em `core.py:736-748` usa a unidade da sessão) | **Suspeito** |
| 5 | `app/registros/core.py:988-992` | `POST /planejamento/nivel/inativar/<id>` | A | **Suspeito** |
| 6 | `app/planejamento.py:47-48` | `POST /turma/alternar-conselho/<turma_id>` | A — admin altera flag de conselho de turma de qualquer unidade | **Suspeito** |
| 7 | `app/registros/periodos.py:373-374` | `GET+POST /periodo-letivo/editar/<id>` (grava no POST L377+) | A | **Suspeito** |
| 8 | `app/registros/periodos.py:105-108` | `POST /planejamento/calendario/salvar` (upsert em lote de DiaBloqueado) | B — sem unidade na sessão (possível só p/ admin/gerência), edita período de qualquer unidade | **Suspeito** |
| 9 | `app/registros/periodos.py:206-207` | `POST /planejamento/calendario/remover/<dia_id>` | B | **Suspeito** |
| 10 | `app/registros/periodos.py:725-729` | `POST /centros-custo/<id>/editar` | B disfarçado: para admin/gerência o assert só roda `if unidade_id is not None` → Visão Global edita qualquer centro | **Suspeito** — o comentário L728 diz "permite admin/gerencia apenas se o centro pertencer à unidade do contexto", mas a condição não cobre unidade ausente |
| 11 | `app/registros/turmas.py:735,747` | `POST /turma/nova` (validação de período/professor) | B — guards `(unidade_id and ...)`; admin global vincula período/professor de outra unidade (e a turma nasce `unidade_id=None`, L830) | **Suspeito** (subproduto: turma órfã de unidade) |
| 12 | `app/registros/turmas.py:1214-1216,1284-1285` | `POST /turma/editar/<id>` (troca de período) | B — mesmo padrão | **Suspeito** |
| 13 | `app/registros/periodos.py:41-43` (`_check_calendario_access`) | helper usado pelas rotas de calendário | A apenas p/ checagem *sessão × usuário* (não é isolamento de recurso) | **Intencional** — admin/gerência escolhem a unidade na sessão; a checagem de recurso é a linha 8/9 acima |
| 14 | `app/registros/periodos.py:308-311` | `POST /periodo-letivo/novo` | A apenas p/ checagem sessão × usuário; o recurso é criado **na unidade da sessão** | **Intencional** — mesmo racional do `novo_curso` |
| 15 | `app/auth.py:512-864` (`/admin/cadastrar`, `/usuarios/editar|resetar|excluir`, `/admin/unidades/cadastrar|editar|alternar`, `/admin/logs/limpar-antigos`, `/admin/manutencao/toggle`) | POST de administração | sem filtro por unidade | **Intencional** — recursos são usuários/unidades/config global (entidades de domínio global, não possuem unidade-mãe que se isolate por sessão); painel já é gated `role != ADMIN → 403` |
| 16 | `app/informacao_padrao.py:16-29` | `POST /admin/informacao-padrao` | sem filtro por unidade | **Intencional** — dados institucionais únicos do sistema |
| 17 | `app/conselho.py:187-225` (`salvar_pergunta`, `excluir_pergunta`; inclui GERENCIA) | POST | sem filtro por unidade | **Intencional** — `PerguntaConselho` é banco **global** de perguntas (sem `unidade_id` no modelo, `app/models/conselho.py:64-74`) |
| 18 | `app/registros/atendimentos.py:380,431` | POST editar/excluir Atendimento | `role != "admin"` isenta só o check **autor do registro** | **Intencional** — isenção de *propriedade*, não de unidade (o isolamento por unidade do atendimento é outro check, presente) |
| 19 | `app/main/unidade.py:14` | `trocar_unidade` | gated a admin/gerência | **Intencional** — é exatamente o mecanismo "escolher unidade após o login" previsto na decisão |
| 20 | `app/utils/logica.py:179-192` | `get_unidade_id` | ADMIN/GERENCIA podem ficar com unidade None | **Intencional** (mecanismo da Visão Global) — mas é o que torna os padrões B acima alcançáveis só por eles |
| 21 | `app/planejamento.py:15` | `POST /configurar-conselho` | admin dispensado de ter unidade | **Suspeito (menor)** — as datas de conselho são gravadas em `ConfiguracaoSistema` via `filter_by(chave=...)` **sem escopo de unidade** (L24), embora o modelo tenha dimensão `unidade_id` (cf. `auth.py:794-796`); hoje é global por omissão, não por regra escrita |

Fora do escopo pedido (rotas de **leitura** com o mesmo padrão B, registradas sem tabela): `core.py:143-151` (turmas do programa), `periodos.py:54,232` (calendario GET/export), `relatorios/bi_routes.py:64-66` (BI restringe não-admin sem unidade; admin/gerência enxergam global) — coerentes com "Visão Global é somente leitura".

## 5. Decisões que tomei sozinho

1. **Usei `assert_unidade_context` cru** (sem escrever `if unidade_id is None: abort(403)` antes): a função já recusa `unidade_id None` com 403 — mantém `editar` literalmente igual a `inativar`/`reativar`, como ordenado.
2. **Não toquei o teste**, ainda que ele estivesse falhando desde a B1: era a bandeira exatamente deste defeito, e sem alteração ele a desliga sozinho.
3. **Não propaguei a correção** para os 12 itens "suspeitos" da auditoria — ordem expressa do passo 4 (auditoria somente leitura).
4. **Classifiquei os padrões A/B do lado das rotas de escrita** apenas quando o recurso **tem** dimensão de unidade (tema, nível, período, centro, turma); onde o recurso é global por projeto (pergunta de conselho, unidade, usuário, informação padrão), a ausência de filtro é intencional.

## 6. Pendências

| # | Pendência | Onde | Tipo | Prioridade |
|---|---|---|---|---|
| T1 | **12 pontos "suspeitos" da tabela §4** replicam o vício de `editar_curso` agora corrigido (isenção/condicionalidade de unidade em escritas cross-unit para admin/gerência, violando "Visão Global é somente leitura"). Recomendo uma etapa de correção em lote (padrão A: condicionar a nada; padrão B: recusar quando `unidade_id is None` em POST) + testes de regressão análogos ao de `/cursos`. | `core.py`, `periodos.py`, `planejamento.py`, `turmas.py` (itens 1-12) | Segurança | **Alta** |
| T2 | `POST /turma/nova` por admin **sem unidade na sessão** cria `Turma(unidade_id=None)` (L830) — subproduto do item 11; decidir se a rota exige unidade mesmo para admin. | `app/registros/turmas.py:830` | Defeito/dívida | Média |
| T3 | `configurar-conselho` grava datas sem escopo de unidade (item 21): confirmar se a regra é global (aí o modelo está certo e o gate de unidade é cosmético) ou por unidade (aí falta `unidade_id` no upsert). | `app/planejamento.py:15-30` | Regra a confirmar | Média |
| T4 | Testes de `/cursos` cobrem o novo comportamento só para ADMIN (seed usa admin); um caso análogo para **gerencia** (hoje também sem isenção em `editar_curso`, papel permitido na lista L602) daria simetria total. | `tests/test_security_regressions.py:435-495` | Dívida de teste | Baixa |
| T5 | Persistem da B2: R2 (resíduo `programas` no render de nova_turma), D3/R4 da B1 (turma sem período some na listagem), P7/T1-conftest (armadilha §5.6 para testes futuros). | vário | Dívida | Baixa→Média |

**Estado da suíte ao final da B3: `221 passed, 42 warnings in 27.43s` — 0 falhas. Nenhum commit feito; nenhuma outra linha de `app/` alterada além de `editar_curso`.**
