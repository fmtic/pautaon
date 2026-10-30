# G1 — Professor obrigatório na oferta + acesso do professor por OFERTA

**Data:** 28/10/2026 · **Branch:** `nova_feature` · **Head Alembic:** `c8d9e0f1a2b3` (sem migration)
**Resultado:** **PARTE B (acesso por oferta) aplicada**; **PARTE A (obrigatoriedade) NÃO aplicada — TRAVA
disparada no P1c**, com números, script de saneamento em dry-run e pedido de decisão.

---

## P0 — estado inicial

- `git status --porcelain -uall`: nenhum arquivo de código modificado; apenas dois arquivos temporários
  **alheios** (`tmpnb_kzdwy`, `tmpu4b2akau`) — não tocados.
- Suíte: **919 passed** (HEAD `0f79c2c`, fechamento da PARTE B anterior).

## P1a — levantamento (somente leitura, principal e ensaio)

Script descartável `.tmp/g1_p1.py` (só `SELECT`; DSN do `.env` com o nome do banco trocado, mascarada).

| Métrica | principal (`pautaon`) | ensaio (`pautaon_ensaio`) |
| --- | --- | --- |
| ofertas (total) | 6 | 12 |
| ofertas **ativas** | 6 | 10 |
| ativas com `professor_id` **NULL** | **4** | **1** |
| …dessas, turma com professor preenchido | **0** | **0** |
| inativas com `professor_id` NULL | 0 | 0 |
| ativas com professor **≠** professor da turma | 0 | 2 |
| turmas ativas sem nenhuma oferta ativa | 0 | 0 |

Detalhe das ofertas ativas sem professor — **todas em turmas também sem professor**:

| Banco | oferta | turma | unidade | inscrições ativas |
| --- | --- | --- | --- | --- |
| principal | 16 | 12 (Turma Alfa) | 3 | 2 |
| principal | 17 | 12 (Turma Alfa) | 3 | 2 |
| principal | 18 | 13 (Turma Gema) | 3 | 1 |
| principal | 19 | 14 (Turma Zeta) | 3 | 0 |
| ensaio | 50 | 34 ([ROTEIRO] Turma Vizinha) | 14 | 1 |

## P1c — TRAVA **DISPARADA** (o que foi e o que não foi feito)

A condição do briefing se cumpriu: **existem ofertas ATIVAS sem professor** (4 no principal, 1 no ensaio).
Por isso **a obrigatoriedade (P2) NÃO foi aplicada** — nem no serviço, nem nos formulários, nem nos templates.
Nenhum arquivo de `services/turma_curso.py`, `turmas.py` ou `ofertas.html` foi alterado nesta tarefa.

### Proposta de saneamento (script com dry-run)

`scripts/saneamento_professor_oferta.py` (novo), **dry-run por padrão**:

- copia `turma.professor_id` **somente** quando a turma tem professor e ele é da **mesma unidade** da turma;
- todo o resto é apenas **listado** para decisão da instituição;
- `--aplicar` só é aceito em banco cujo nome contém `ensaio`, salvo `--autorizar-principal`;
- a DSN vem do `.env` com apenas o nome do banco trocado, via classe de configuração —
  `DATABASE_URL` do shell não é lida nem alterada;
- idempotente (depois de aplicar, o grupo “copiável” fica vazio).

Execuções feitas (nenhuma escrita no principal):

| Comando | Resultado |
| --- | --- |
| `python scripts/saneamento_professor_oferta.py` | 4 ofertas sem professor, **0 copiáveis**, 4 pendentes (16, 17, 18, 19); “dry-run: nada foi alterado.” |
| `... --banco ensaio` | 1 oferta sem professor, 0 copiáveis, 1 pendente (50); dry-run |
| `... --banco ensaio --aplicar` | “nada a aplicar.” (0 escritas) |
| `... --aplicar` (principal) | **RECUSADO** (exit 2) — exige `--autorizar-principal` |

**Conclusão do saneamento:** não há nada a copiar — as cinco ofertas estão em turmas sem professor. A
instituição precisa **indicar o professor de cada uma** (4 no principal, 1 no ensaio) antes de a
obrigatoriedade valer em produção; o script continua útil para o que surgir depois (turma com professor e
oferta sem).

### Decisões que dependem do usuário

1. Indicar o professor das ofertas **16, 17, 18 e 19** (principal) e **50** (ensaio) — ou autorizar o
   saneamento por `--autorizar-principal` depois de definir os professores.
2. Autorizar (ou não) a aplicação do **P2** a seguir: obrigatoriedade no serviço (`ValueError` em português),
   `required` nos formulários, remoção da opção “-- Sem professor --”, aviso "sem professor" na tela de ofertas.
   Observação: enquanto as 5 ofertas acima existirem, elas **só poderão ser salvas com professor** — o que é o
   efeito desejado, mas exige a definição acima.

## P1b — como a oferta nasce e é editada hoje

| Caminho | Professor hoje |
| --- | --- |
| `criar_oferta_inicial_da_turma` (oferta criada junto com a turma) | **copia** `turma.professor_id` — que pode ser `NULL` (turma nova não envia professor) |
| `adicionar_oferta` (cadastro incremental) | **opcional** (`_validar_professor` devolve `None`); herda da turma só quando a turma não tem curso legado |
| `editar_oferta` | valida quando o campo vem; **aceita NULL** (pode esvaziar) |
| `editar_turma` com **oferta única** | propaga `turma.professor_id` para a oferta (`turmas.py:1945`) |

Formulários:

- `turmas/nova_turma.html`: **não tem campo de professor** → turma nasce com `professor_id` NULL e a oferta
  inicial também.
- `turmas/editar.html:171-176`: `select name="professor_id"` com `-- Sem professor atribuído --`, **sem**
  `required` (há também um hidden com o valor atual).
- `turmas/ofertas.html:111-112` (edição) e `:237-238` (nova oferta): `-- Sem professor --`, **sem** `required`.

**Turma com 0 ofertas ativas:** o lançamento legado continua funcionando (`GET/POST /frequencia` sem oferta);
a impressão legada funciona para admin/pedagógico/secretaria e, desde a PARTE B, responde **403** para
professor (não há oferta da qual ele seja o professor). Não há, hoje, turma ativa sem nenhuma oferta ativa
(0 em ambos os bancos).

## P1d — `imprimir_pauta` e os links da interface

Guarda (já por oferta desde a PARTE B, confirmada aqui): `assert_unidade_context` → resolução da oferta →
`professor_da_oferta(oferta, current_user)` (só `turma_curso.professor_id`). O que cada modo imprime: folha
por mês a partir da grade da oferta, alunos **da oferta**, “Outras ofertas” oculta para professor.

**A interface gera link sem `turma_curso`?** Sim, em dois lugares:

- `app/templates/frequencia/lancar.html:24` e `:35` — `url_for(..., **({'turma_curso': tc} if tc else {}))`;
  com 2+ ofertas e **nenhuma escolhida** (`oferta_atual` nulo / `exigir_escolha`), o link sai **sem** o
  parâmetro.
- `app/templates/turmas/detalhe.html:53` e `:63` — pauta mensal / completa **sem** `turma_curso`; esse ramo só
  aparece quando a turma tem **0 ou 1** oferta ativa (com 2+ o menu lista um link por oferta, `:45`, com o
  parâmetro).

Consequência da regra do P3 (sem parâmetro = **menor id**): em turma com 2+ ofertas, o professor que não leciona
a de menor id recebe **403** se clicar no link da `lancar.html` antes de escolher o curso. O caminho normal
(escolher a oferta no filtro e então imprimir, ou o menu do detalhe da turma com 2+ ofertas) continua correto.
Ajustar esses dois templates para não oferecer impressão sem oferta é melhoria de UI pendente (registrada no
backlog) — não foi feita para não ampliar o escopo.

## P1e — inventário de guardas e leitores (listado; não alterado)

**Guardas de acesso do professor por `turma.professor_id` (fora do escopo; alinhamento pendente):**
`ver_turma` (`registros/turmas.py:1376`), `ver_observacoes` (`:2642`), `GET/POST /frequencia` e painel do
professor (`registros/core.py:220`, `:276`, `:403`), conselho (`conselho.py:229`, `:475`, `:906`), histórico do
aluno (`registros/alunos.py:887`) e foto (`:1322`).

**Leitores com “professor efetivo” e herança (COALESCE):** filtro por professor da listagem
(`registros/turmas.py:562-576`), `ofertas_do_painel_conselho` (`services/turma_curso.py:151-155`) e o nome do
professor na oferta (`:166`), cabeçalho “Professor:” da pauta (`templates/frequencia/imprimir_pauta.html:213-214`).
O dashboard do professor já é por oferta (`main/dashboard_professor.py:163-206`).

## P3 — PARTE B aplicada (delta do G1)

A guarda por oferta veio da PARTE B. O G1 mudou **só a resolução da oferta sem `turma_curso`**:

```python
if current_user.role == UserRole.PROFESSOR:
    if turma_curso_id is not None:
        oferta = next((o for o in ofertas if o.id == turma_curso_id), None)
    else:
        oferta = ofertas[0] if ofertas else None   # 1 → ela; 2+ → menor id
    if not professor_da_oferta(oferta, current_user):
        abort(403)
```

| Caso (professor) | PARTE B | G1 |
| --- | --- | --- |
| Sem parâmetro, 1 oferta ativa (dele) | 200 | 200 |
| Sem parâmetro, 2+ ofertas, menor id **é dele** | 200 | 200 |
| Sem parâmetro, 2+ ofertas, menor id **não é dele** | 200 (usava a dele) | **403** |
| Oferta principal de outro professor | irrelevante | **irrelevante (R2)** |

O restante segue igual: 403 quando não é o professor cadastrado (inclusive sendo o professor da turma, oferta
sem professor ou turma sem oferta ativa dele); alunos sempre por oferta; “Outras ofertas” oculta para
professor; admin/pedagógico/secretaria inalterados. O I1 usa a mesma expressão
(`condicao_professor_da_oferta`) — nada a mudar no serviço do I1 nesta tarefa.

## P4 — testes

`tests/test_pauta_impressa_por_oferta.py`: **19 testes** (era 15).

**Ajustados (2) — antigo × novo × motivo:**

| Antigo | Novo | Motivo |
| --- | --- | --- |
| `test_sem_parametro_usa_a_primeira_oferta_ativa_do_professor` (professor B, sem parâmetro → 200 na oferta dele) | `test_sem_parametro_da_oferta_de_menor_id_de_outro_recebe_403` (professor B → **403**) | G1/P3: sem parâmetro vale a oferta de **menor id**, não “a do professor” |
| `test_sem_parametro_prefere_a_principal_quando_e_dele` (principal decidia a escolha) | `test_sem_parametro_usa_a_oferta_de_menor_id_quando_e_dele` (professor A, dono da menor id → 200) | R2: `principal` não decide mais nada; o 200 vem do menor id |

**Novos (4):**

- `test_oferta_principal_nao_altera_acesso` — troca a `principal` para a O2 e verifica que nada muda (A: O1
  200 / O2 403 / sem parâmetro 200; B: O2 200 / O1 403 / sem parâmetro 403).
- `test_secretaria_e_pedagogico_inalterados` — ambos imprimem qualquer oferta (200).
- `test_professor_de_outra_unidade_recebe_403` — isolamento por unidade.
- `test_i1_periodo_encerrado_continua_bloqueado` — endpoint 403 e linhas de acompanhante/instruções fora da
  impressão.

Nenhum outro teste existente precisou mudar (2 mudanças ≤ 10). Suíte: **923 passed**.

## P5 — ensaio (somente leitura)

Parte de escrita do P5 (criar/editar oferta sem professor ⇒ recusa) **não se aplica**: depende do P2, que está
bloqueado pela TRAVA. A conferência por HTTP foi feita em modo leitura, com a semente do M1
(`professor.m1@roteiro.local`, id 120, unidade 13):

| Requisição | Resultado |
| --- | --- |
| `GET /turma/30/imprimir-pauta?turma_curso=44` (oferta dele) | 200 |
| `GET /turma/30/imprimir-pauta` (sem parâmetro; única ativa = 44, menor id) | 200 |
| `GET /turma/9/imprimir-pauta?turma_curso=12` (oferta de outro professor) | 403 |
| `GET /turma/9/imprimir-pauta?turma_curso=13` (oferta de outro professor) | 403 |
| `GET /turma/34/imprimir-pauta?turma_curso=50` (oferta **sem professor**) | 403 |

Na unidade 13 as quatro ofertas ativas (44–47) são todas do professor 120 e a turma 9 (professor 93) está em
outra unidade — o par “professor da turma ≠ professor da oferta na MESMA unidade” não existe na semente; esse
caso está coberto pelos testes automatizados. Nenhuma escrita foi feita; principal intocado.

## Desvios e pendências

1. **P2 (obrigatoriedade) não aplicado** — TRAVA do P1c (`4` ofertas ativas sem professor no principal, `1` no
   ensaio, todas em turmas sem professor). Script de saneamento entregue em dry-run.
2. **Script novo fora da lista de escopo** (`scripts/saneamento_professor_oferta.py`) — pedido explicitamente
   pelo item P1c da própria tarefa.
3. **Links de impressão sem `turma_curso`** em `lancar.html:24,35` e `detalhe.html:53,63` — reportado no P1d;
   com 2+ ofertas o professor pode receber 403 se clicar antes de escolher o curso.
4. **Herança remanescente** nas guardas por turma e nos leitores com COALESCE (inventário do P1e) — alinhamento
   futuro, junto com a listagem de turmas e o painel do conselho.
5. **NOT NULL no banco** segue pendente (schema `nullable=True`): só depois do saneamento completo.
