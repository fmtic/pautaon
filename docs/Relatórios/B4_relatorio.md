# ETAPA B4 — Isolamento de unidade em rotas de escrita (itens 1-12 da auditoria B3)

Data: 2026-10-25 · Ramo: Onda4 (sem commit, por determinação) · Suíte final: **257 passed, 51 warnings in 33.66s** (0 falhas).

Regra aplicada (decisão do responsável, passo 1 da B3): isolamento por unidade vale
para TODOS os perfis, inclusive ADMIN e GERENCIA; a Visão Global é somente leitura.
Em rota de escrita: (a) sem unidade efetiva na sessão → recusa 403; (b) recurso de
outra unidade → 403 para qualquer perfil.

---

## 1. Leitura — item por item (trecho atual → correção proposta)

Confirmadas as duas perguntas do passo 1:
- **Item 10** (centros de custo): os dois guards de `editar_centro_custo` só chamavam
  `assert_unidade_context` quando `unidade_id` não era None (admin/gerência) ou para
  os demais papéis — na Visão Global nenhum assert rodava. **Passa a recusar** com
  `unidade_id is None` (403 via assert).
- **Itens 8, 9, 11, 12** (calendário salvar/remover, turma nova, turma editar): os
  guards `if unidade_id and ...` eram pulados inteiramente na Visão Global.
  **Passam a recusar** quando `unidade_id is None` (8: 403 JSON; 9: 403 via assert;
  11: 403 explícito no POST; 12: guard incondicional — mas ver observação abaixo).

| # | Local (pré-B4) | Situação lida | Correção aplicada |
|---|----------------|---------------|-------------------|
| 1 | `core.py:764-765` criar tema (POST /planejamento) | `if role != ADMIN: assert(...)` — admin isento | assert incondicional + `except HTTPException: raise` (o `try` amplo engolia o 403) |
| 2 | `core.py:889-892` editar_tema | mesmo padrão A; pré-cheque SECRETARIA-None redundante | assert incondicional (recusa None p/ todos); pré-cheque removido (subsumido) |
| 3 | `core.py:935-938` inativar_tema | idem item 2 | idem |
| 4 | `core.py:961-965` editar_nivel | padrão A com `unidade_id` dentro do if | `unidade_id = get_unidade_id(); assert(...)` incondicional |
| 5 | `core.py:988-992` inativar_nivel | idem item 4 | idem |
| 6 | `planejamento.py:47-48` alternar-conselho | `if role != "admin": assert(...)` | assert incondicional |
| 7 | `periodos.py:373-374` periodo_letivo_editar | `if role != "admin": assert(...)` (GET+POST) | assert incondicional |
| 8 | `periodos.py:105-108` calendario_salvar | `if unidade_id and periodo.unidade_id != unidade_id: 403 JSON` — pulava na Visão Global | `if unidade_id is None or ...` → 403 (mantido o corpo JSON da rota) |
| 9 | `periodos.py:206-207` calendario_remover | `if unidade_id and dia.unidade_id != unidade_id: abort(403)` | `assert_unidade_context(dia.unidade_id, unidade_id)` |
| 10 | `periodos.py:725-729` centro_custo editar | dois guards que nunca rodavam com `unidade_id None` p/ admin/gerência | um único `assert_unidade_context(centro.unidade_id, unidade_id)` |
| 11 | `turmas.py:735,747` POST /turma/nova | guards `unidade_id and ...` + criação de `Turma(unidade_id=None)` por admin global | `abort(403)` no POST sem unidade efetiva; guards de período/professor incondicionais |
| 12 | `turmas.py:1214-1216,1284-1285` POST editar_turma (troca de período) | guards `unidade_id and ...` | guards incondicionais (`periodo_obj.unidade_id != unidade_id`) |

Observação item 12: o `assert_unidade_context` no topo de `editar_turma` (L1122, pré-
existente) já recusava Visão Global e turma alheia; a mudança nos guards é
defensiva/higienização — o único estado alcançável antes era o redirect com flash
sem gravação (ver §3, artefato de harness).

## 2. Diff por rota (arquivos alterados)

Somente os pontos acima foram tocados; nenhuma rota de leitura, nenhum item 13-21,
nenhum perfil autorizado alterado, nenhuma resposta de sucesso alterada.

- `app/registros/core.py` — 5 rotas (criar tema; editar/inativar tema; editar/
  inativar nível) + import `HTTPException` + cláusula `except HTTPException: raise`
  no POST /planejamento (sem ela o 403 virava flash+302 — ver §4 decisões).
- `app/planejamento.py` — `alternar_conselho`: assert incondicional.
  `salvar_configuracao_conselho` (configurar-conselho) **não foi tocado**, por
  determinação (configuração global pelo MER).
- `app/registros/periodos.py` — `periodo_letivo_editar`, `calendario_salvar`,
  `calendario_remover`, `editar_centro_custo`.
- `app/registros/turmas.py` — `nova_turma` (abort 403 no POST sem unidade; guards de
  período e professor incondicionais) e `editar_turma` (guards de troca de período
  incondicionais, dois ramos).

## 3. Testes

Novo arquivo `tests/test_isolamento_unidade_escrita.py` — 36 testes, um usuário por
teste (T1 §5.6: `test_client()` próprio, sessão fixada uma única vez via
`sess["_user_id"]`/`sess["unidade_id"]`, sem trocar usuário no meio). Semente comum
com duas unidades (A/B) e recurso espelhado em cada lado. Cobertura por família:

- **curso (T4 gerência)**: gerência na unidade A não edita curso B (403 + nada
  gravado); gerência sem unidade é recusada (403); gerência na unidade correta
  edita (200).
- **tema**: criar em curso B → 403 + `TemaAula` inexistente; criar sem unidade →
  403; criar no curso A → 302 + tema com `unidade_id` A; editar/inativar tema B →
  403 + título/ativo intactos; sem unidade → 403; editar+inativar o tema A → 302
  com gravação.
- **nível**: editar/inativar B → 403 + nada gravado; sem unidade → 403; A → 302.
- **período letivo**: editar B → 403 + nome intacto; sem unidade → 403; A → 302 +
  nome/estimativa gravados.
- **calendário**: salvar sobre período B → 403 JSON e o DELETE em lote não roda
  (dia B intacto); sem unidade → 403; período A → 200 com substituição dos dias
  (unidade da linha gravada = A); remover dia B → 403 + dia existe; sem unidade →
  403; dia A → 200 + removido.
- **centro de custo**: editar B → 403 + nome intacto; sem unidade → 403; A → 200.
- **turma nova**: período B com sessão A → 302 e nenhuma turma criada; sem unidade
  → **403** (antes criaria `Turma(unidade_id=None)`); período A → 302 + turma com
  unidade A.
- **turma editar**: turma B → 403; sem unidade → 403; tentativa de mover turma A
  para período B → 302 com **nada gravado**; edição correta → 302 + nome gravado.
- **alternar-conselho**: turma B → 403 + flag intacta; sem unidade → 403;
  turma A → 302 + flag alternada.

**Artefato de harness descoberto e tratado** (não é bug de produção): no POST
editar_turma com período cross-unidade, o `db.session.get(PeriodoLetivo, ...)` do
guard dispara **autoflush** das atribuições pendentes (`nome`, `periodo_letivo_id`)
antes do `return redirect` — sem commit. No fixture SQLite `:memory:` com StaticPool
e AppContext do fixture ainda aberto, o teste enxerga esse flush não commitado na
mesma conexão (leu 2 em vez de 1). Sonda temporária confirmou que, feito
`db.session.remove()` **na sessão ativa do fixture** (não em contexto aninhado novo),
o rollback restaura os valores. O teste de não-movimentação usa esse padrão, com
comentário. Arquivo de sonda apagado.

## 4. Decisões

1. **`except HTTPException: raise` no POST /planejamento (criar tema)**: o `try`
   amplo da rota capturava o `Forbidden` do assert (e o `NotFound` do `get_or_404`)
   e devolvia flash+302 — a recusa ficaria invisível para o cliente. A cláusula é
   o mínimo para o 403 chegar ao chamador; efeito colateral desejável: 404 de curso
   inexistente também passa a ser 404 em vez de erro logado como "interno".
2. **calendario_salvar manteve a resposta JSON 403** (mensagem `Acesso negado a esta
   unidade`): é a linguagem original da rota (chamada via fetch); só o gatilho mudou
   de `unidade_id and ...` para `unidade_id is None or ...`. Nas demais rotas usei
   `assert_unidade_context` cru, como nas vizinhas (recusa None, mismatch e objeto
   ausente com 403).
3. **Pré-cheques `SECRETARIA and unidade_id is None: abort(403)` removidos de
   editar/inativar tema e nível**: redundantes — o assert unconditional agora recusa
   unidade None de qualquer perfil, sem alterar a lista de papéis autorizados.
4. **/turma/nova sem unidade → 403 explícito no topo do POST** (e não flash+redirect):
   a regra (a) do enunciado pede recusa como `assert_unidade_context`; o flash
   manteria a rota capaz de chegar a `Turma(unidade_id=None)` por caminho indireto.
5. **periodo_letivo_editar (GET+POST)**: o assert passa a valer também no GET —
   admin da unidade A não mais *visualiza* o formulário de período B. Igual a
   `editar_turma`/`editar_curso`, que já assertavam no topo para GET e POST.
6. **Classificação de conflitos (passo 4)**: nenhum teste existente conflitou — a
   suíte passou de primeira após as correções (221 → 221). Nenhuma semente precisou
   de unidade extra; não houve conflito de asserção de finalidade (nenhum PARE).
7. **Ruff**: os apontamentos nos arquivos alterados (I001/E712/F401/F841/E402) são
   todos pré-existentes e fora das linhas tocadas; o novo arquivo de testes passa
   limpo. Não "limpei" ruído fora do escopo.

## 5. Pendências (não corrigidas — fora dos itens 1-12 ou por determinação)

- **P1 · criar nível na Visão Global**: POST /planejamento `tipo_post=nivel` usa
  `get_unidade_id()` diretamente; admin/gerência sem unidade grava
  `Nivel(unidade_id=None)` (mesma família do item 11, caminho não auditado).
  Recomendo recusar unidade None nesse ramo.
- **P2 · editar/inativar tema**: o cheque `curso.ativo` roda **antes** do assert de
  unidade — admin A sondando tema de curso B *inativo* recebe 302 (flash) em vez de
  403. Nada é gravado; é apenas ordem de checagem (info-leak mínimo). Inverter se
  quiser 403 estrito.
- **P3 · leitura com padrão B** (fora do escrito desta etapa): `calendario_dias`
  (periodos.py:54), `calendario_exportar` (:232), `core.py:143-151`,
  `bi_routes.py:64-66` etc. — a decisão "Visão Global é somente leitura" permite
  leituras globais? Vale confirmar a intenção de leitura com o responsável.
- **P4 · configurar-conselho** (planejamento.py:10-37): intocado por ordem explícita;
  segue como "suspeito menor" da B3 (sem escopo de unidade).
- **P5 · legados das etapas anteriores**: R2 (resíduo `programas` no render de
  nova_turma), D3 (turma sem período some da listagem), P7 (conftest único para a
  armadilha de harness T1 §5.6 — o achado §3 reforça a necessidade).

## 6. Resumo da execução

- Escopo: `app/registros/core.py`, `app/planejamento.py`, `app/registros/periodos.py`,
  `app/registros/turmas.py` (só os trechos §2), `tests/test_isolamento_unidade_escrita.py`
  (novo). Nenhuma migration, nenhum serviço/BI/enturmação/conselho/docs alterados.
- Nenhum commit efetuado.
- pytest: `257 passed, 51 warnings in 33.66s` (antes da etapa: 221; +36 novos testes,
  0 falhas, 0 testes existentes alterados).
