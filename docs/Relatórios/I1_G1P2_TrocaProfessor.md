# I1 + G1/P2 + Troca de Professor — relatório das etapas E0–E3

**Data:** 29/10/2026 · **Branch:** `nova_feature` · **Commits:** E1 `ee922c5`, E2 `3af4ee2`, E3 `c9f6cf5` · **Suíte:** 1006 → **1033 passed**, 0 falhas · **Sem push.**

Pedido: completar o G1/P2 (professor obrigatório na oferta), implementar a troca de professor com confirmação e log (opção b), migrar os últimos guardas de acesso de `Turma.professor_id` para a regra por **oferta** (I1) e sanear as ofertas de teste sem professor. Regra vigente documentada em MER §8.12/§8.20/§8.21/§8.22.

---

## E0 — Estado inicial (leitura)

- `git log/diff main vs nova_feature`: o G1/P2 (trava em `_validar_professor`, `required` nos formulários, migration NOT NULL) **não estava em main nem em origem alguma** — nada a mesclar. Implementado na E2.
- Baseline da suíte antes de qualquer mudança: **1006 passed**, 0 falhas.

## E1 — Saneamento das ofertas sem professor (commit `ee922c5`)

- **Vínculos conferidos antes de remover** (inscricoes, frequencia, registro_aula, conselho_classe, turma_curso_horario), por oferta:
  - **Ensaio** — oferta 50 (turma 34): 1 inscrição ativa e 1 item de grade; **zero lançamento** → removida. A turma 34 ficou **sem oferta ativa** (consequência reportada; turma legada intacta).
  - **Principal** — oferta 19 (turma 14 "Turma Zeta", curso 18): **zero vínculos** → removida. A turma 14 ficou sem oferta ativa.
  - **Principal — regra de parada:** ofertas 16 e 17 (turma 12 "Turma Alfa") e 18 (turma 13 "Turma Gema") têm **frequência lançada** (5, 2 e 2 linhas). **Não removidas** — reportado e parado nelas, exatamente como a regra da etapa manda.
- Ferramenta: `scripts/remover_ofertas_sem_lancamento.py` (dry-run por padrão, travado no principal sem `--autorizar-principal`, recusa oferta com lançamento, exige `--remover-inscricoes` quando há matrícula ativa). Backups antes da operação: `instance/backups/pautaon_pre_saneamento_ofertas.sql` e `pautaon_ensaio_pre_saneamento_ofertas.sql`, com contagem de linhas antes/depois.
- **Conferência após o saneamento (refeita na entrega, só SELECT):** nenhuma oferta ativa sem professor no **ensaio**; no **principal** restam as três bloqueadas — 16/17/18 seguem ativas com `professor_id IS NULL` e frequência lançada. **A migration NOT NULL da E2 continua bloqueada por elas.**

## E2 — G1/P2 + troca de professor (commit `3af4ee2`, detalhe em MER §8.21)

- **Serviço** (`app/services/turma_curso.py`): `_validar_professor` recusa vazio com `ValueError` em português (`_PROFESSOR_OBRIGATORIO`) em `adicionar_oferta`, `editar_oferta` e `criar_oferta_inicial_da_turma`. Trocar é permitido; **esvaziar não**. Herança de `turma.professor_id` só no caso legítimo (primeira oferta de turma sem vínculo legado), resolvida antes da validação.
- **Espelhos turma ↔ oferta:** `editar_turma` **não propaga NULL** — só espelha na oferta única quando veio professor; com campo vazio, a oferta (fonte) é quem empresta o valor à turma.
- **Formulários:** `turmas/ofertas.html` e `turmas/editar.html` sem "-- Sem professor --" e com `required`; na turma com 2+ ofertas o campo fica readonly (a edição por turma não decide o professor de cada oferta).
- **Migration NOT NULL: não aplicada** — as ofertas 16/17/18 do principal ainda sem professor bloqueiam (regra da etapa: "se algum banco ainda tiver oferta sem professor, parar e reportar"). `turma_curso.professor_id` continua nullable.
- **Troca com lançamentos (opção b):** `oferta_tem_lancamentos` / `ofertas_com_lancamentos`; POST sem `confirmar_troca_professor=1` volta com flash **sem escrita** (mesmo padrão da limpeza de lançamentos de `turmas.py`); a tela marca as ofertas com lançamento (`data-com-lancamento`). `LogAcao("Trocar Professor da Oferta")` grava **id e nome do anterior e do novo** em `detalhes` parseável, sem alterar o formato das demais entradas do log.
- **Testes:** `tests/test_g1_p2_professor_oferta.py` (vazio recusado no serviço e nos formulários, herança, troca simples, troca com lançamento exige confirmação nas duas rotas, log anterior/novo, editar turma não zera oferta) + ajustes nos arquivos que criavam oferta sem professor. **Suíte 1006 → 1026 passed.**

## E3 — I1: regra por oferta nos guardas restantes (commit `c9f6cf5`, detalhe em MER §8.22)

**Migradas** de `Turma.professor_id` para `condicao_professor_da_oferta` / `professor_da_oferta` (+ helper novo `professor_de_alguma_oferta_ativa`):

| Guarda | Onde estava | Agora |
| --- | --- | --- |
| `ver_turma` | `turmas.py:1374` | alguma oferta ativa da turma com ele como professor (`turmas.py:1395`) |
| `ver_observacoes` (Diário de Bordo) | `turmas.py:2640` | idem (`:2729`); com `?turma_curso=` restrito à oferta apontada |
| `POST /frequencia` | `core.py:256` | idem (`core.py:263`) |
| `GET /frequencia` | `core.py:382` | lista de ofertas do professor por condição (`core.py:399`) |
| `historico_aluno` | `alunos.py:881` | inscrição qualificada com `condicao_professor_da_oferta` (`:892`) |
| `/aluno/<id>/foto` | `alunos.py:1316` | idem (`:1332`) |

`assert_unidade_context` e os papéis de gestão/admin mantidos em todas. **Medicação na pauta não entrou** (decisão de conteúdo, pendente com a instituição).

- **detalhe.html:** links de pauta e Diário saem **por oferta** (`?turma_curso=<id>`); para professor, `ver_turma` passa `ofertas_do_professor` e o template só linka as ofertas dele — **nenhum link leva a 403**. Admin/gestão veem todas.
- **Efeito (ganha/perde):** professor **da oferta** sem ser o da turma **ganha** pauta, Diário, histórico e foto; professor **da turma sem oferta própria perde** (403; no `GET /frequencia`, 302 + flash "não tem permissão"). Observação do ensaio: turma com duas ofertas do mesmo professor mantém o acesso enquanto ele lecionar **qualquer** oferta ativa dela — regra correta.
- **Backlog:** linha da regra do I1 (`:134`) dizia `coalesce(turma_curso.professor_id, turma.professor_id)`; corrigida para a regra vigente sem herança (anotação "29/10 — correção da regra vigente").
- **Testes:** `tests/test_i1_guardas_por_oferta.py` (+7: ganha, perde, gestão/admin, troca transfere pauta/Diário/histórico/foto — novo 200, antigo 403 —, detalhe do professor só com ofertas dele e todos os links 200, detalhe do admin, detalhe pós-troca). Ajustado `test_v3a_imprimir_coerente.py` (antigo × novo × motivo: turma legada sem oferta ativa → recusa de acesso, não mais botão oculto). **Suíte 1026 → 1033 passed**, ruff `F821/F811/F841` limpo.
- **Ensaio (pautaon_ensaio, semente M1, desfeito):** troca do professor da **oferta 45** (turma 31) pelas rotas reais — antes: original 200 / candidato 403; depois: original 403 / candidato 200; restauração conferida (45/46 → professor 120, professor temporário excluído, `RESULTADO: OK`). Banco principal apenas lido (SELECT) fora da E1.

## O que ficou em `Turma.professor_id`

- **Schema:** a coluna continua (removê-la é onda própria, com migration e leitura de dump). Os **espelhos de escrita** turma ↔ oferta permanecem (`turma_curso.py:444/:521/:594`, `turmas.py:1844/:1945`) — agora NULL-safe.
- **Filtros/dropdowns com COALESCE** (não são regra de acesso, por decisão do inventário §8.20): listagem de turmas (`turmas.py:562-573`, `:2447-2599`), `bi_alunos.py`, `relatorios/observacoes.py:133`, `conselho.py:292`, contagem do `dashboard_admin.py:34`.
- **Ramo legado do painel** para turma sem oferta ativa (`main/dashboard_professor.py:200`) e a guarda de turma do **conselho de lançamento** quando sem oferta.
- **Cabeçalho "Professor:" da pauta impressa** (exibição, não acesso).

## Pendências restantes

1. **Reatribuir o professor das ofertas 16, 17 e 18** (principal, com frequência lançada) — sem isso a **migration NOT NULL** de `turma_curso.professor_id` continua bloqueada.
2. **Autor em `frequencia`:** a tabela não tem coluna de autor; `registro_aula.instrutor_id` é sobrescrito a cada salvamento — a troca de professor não preserva quem lançou. Decisão de modelagem pendente.
3. **Medicação na pauta:** decisão de conteúdo com a instituição (expor ou não ao professor da oferta); nada mudou no comportamento.
4. **87 F401 globais** (imports sem uso) — higiene fora do escopo das etapas; a E3 manteve limpos só `F821/F811/F841`.
5. **Links de impressão sem `turma_curso`** (`lancar.html`, `detalhe.html` — item G1-4 do backlog) e migração das **demais telas** do inventário P1 para a regra por oferta (decisão futura).
6. **Harness:** migrar os 26 arquivos com login local para `login_as` (a armadilha `g._login_user` voltou a aparecer nos testes da E3 — documentada em MER §8.22).
