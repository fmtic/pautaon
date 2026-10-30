# PARTE B — Pauta impressa e I1 por OFERTA (sem herança do professor da turma)

**Data:** 28/10/2026 · **Branch:** `nova_feature` · **Head Alembic:** `c8d9e0f1a2b3` (sem migration)
**Suíte:** 904 → **919 passed** (15 novos, 0 falhas) · **Commit de código:** guarda por oferta (serviço + rota +
testes); **commit de docs:** MER, backlog e este relatório.

---

## P0 — estado inicial

- `git status --porcelain`: nenhum arquivo de código modificado. Dois arquivos **não rastreados e alheios**
  (`tmp7fqu8q21`, `tmpuzyvmzse`) permanecem intocados (não são do escopo).
- Suíte: **904 passed** (fechamento do I1).

## P0-B — levantamento (somente leitura, principal e ensaio)

Script descartável `.tmp/b_p0b.py` (apenas `SELECT`, DSN do `.env` com o nome do banco trocado para o ensaio;
alvo mascarado na saída).

| Métrica (ofertas ATIVAS) | principal (`pautaon`) | ensaio (`pautaon_ensaio`) |
| --- | --- | --- |
| ofertas ativas | 6 | 10 |
| `professor_id IS NULL` | 4 | 1 |
| NULL **com** professor da turma preenchido | **0** | **0** |
| ofertas ativas em turma **sem** professor | 4 | 1 |
| professor ≠ professor da turma | 0 | 2 |
| professor == professor da turma | 2 | 7 |

Detalhe do principal: ofertas 16/17 (turma 12) e 18 (turma 13), 19 (turma 14) sem professor — e as quatro
turmas também estão **sem** professor. Detalhe do ensaio: oferta 50 (turma 34, turma sem professor) e ofertas
12/13 (turma 9, professores 88/89 × turma 93).

### TRAVA 1 — dispararia?

**Não.** `null_com_professor_da_turma = 0` nos dois bancos: nenhuma oferta ativa sem professor tem professor
de turma que hoje imprime ou vê o modal por herança. No ensaio, as ofertas 12/13 **perdem** o acesso do
professor 93 (professor da turma) — é exatamente o comportamento-alvo, porque ele não é o professor
cadastrado delas.

### Como o formulário/serviço de oferta trata o professor

- `_validar_professor` (`services/turma_curso.py`): **opcional** — sem id devolve `None`; com id, exige
  `role == "professor"` e a unidade da turma.
- `criar_oferta_inicial_da_turma`: a oferta inicial **copia** `turma.professor_id`.
- `adicionar_oferta`: usa o professor enviado; herda da turma **só** quando a turma não tem curso legado
  (`professor_id = professor_id or turma.professor_id`).
- `editar_turma`: com **oferta única**, propaga `turma.professor_id` para a oferta (`turmas.py:1945`).
- `editar_oferta`: valida quando o campo vem no formulário e **pode limpar** (NULL).

### Leitura de `imprimir_pauta` (antes)

Guarda: perfil `admin/pedagogico/secretaria` **ou** `professor` (senão 403) → `assert_unidade_context` →
**professor só na própria turma** (`turma.professor_id == current_user.id`). Resolução da oferta:
`turma_curso` na querystring; 0 ofertas → legado por turma; 1 → automática; 2+ → exige `turma_curso` (flash +
redirect). Modos: folha por mês (`datas_por_mes`), lista de alunos por oferta **somente com 2+ ofertas** (com
1 oferta vem da turma) e linha “Outras ofertas” por aluno (todas as ofertas ativas da turma).

### TRAVA 2 — o modo “demais ofertas enturmadas” exigiria alunos de outras ofertas?

**Não.** A pauta usa `_alunos_da_oferta(turma_id, oferta_id)` (inscrições ativas **na oferta**); para o
professor passei a usá-la também com 1 oferta ativa. A linha “Outras ofertas” é metadado (nome de curso) e foi
**ocultada** para professor — a alternativa preferida do briefing. Nada a reportar como bloqueio.

### Inventário (somente listado; NÃO alterado)

**Guardas de acesso do professor por `turma.professor_id`:**

- `app/registros/turmas.py:1376` — `ver_turma`
- `app/registros/turmas.py:2642` — `ver_observacoes`
- ~~`app/registros/turmas.py:2692` — `imprimir_pauta`~~ → **alterado nesta parte**
- `app/registros/core.py:220` — painel do professor (lista de turmas)
- `app/registros/core.py:276` — `POST /frequencia`
- `app/registros/core.py:403` — `GET /frequencia` (lista de turmas)
- `app/conselho.py:229` — lançamento do conselho
- `app/conselho.py:475` — painel do conselho
- `app/conselho.py:906` — `avaliar_turma`
- `app/registros/alunos.py:887` — histórico do aluno
- `app/registros/alunos.py:1322` — foto do aluno

**Leitores de “professor efetivo” com herança (COALESCE):**

- `app/registros/turmas.py:562-576` — filtro por professor da listagem de turmas
- `app/services/turma_curso.py:151-155` — `ofertas_do_painel_conselho(professor_id)`
- `app/services/turma_curso.py:166` — `"professor": oferta.professor or oferta.turma.professor`
- `app/templates/frequencia/imprimir_pauta.html:213-214` — cabeçalho “Professor:” da folha

O dashboard do professor **já** é por oferta (`app/main/dashboard_professor.py:163-206`, com ramo legado para
turma sem oferta ativa). Todos registrados no backlog como pendência de alinhamento.

## Implementação

### `app/services/aluno_info_professor.py` — regra única

```python
def condicao_professor_da_oferta(user_id):
    """A ÚNICA expressão de "professor da oferta" (PARTE B): sem herança."""
    return TurmaCurso.professor_id == user_id

def professor_da_oferta(oferta, usuario) -> bool:      # mesma regra, objeto em memória
    ...
```

`_condicoes_acesso` passou de `func.coalesce(TurmaCurso.professor_id, Turma.professor_id) == user.id` para
`condicao_professor_da_oferta(user.id)`. O `func` saiu do módulo. O resto da regra (inscrição ativa, aluno
ativo, oferta/turma ativas, unidade, período não encerrado) **não mudou**.

### `app/registros/turmas.py` — `imprimir_pauta`

- A guarda `turma.professor_id != current_user.id` foi **removida**; a oferta é resolvida **antes** de decidir.
- Professor: com `turma_curso` → a oferta é essa e precisa ser dele; sem parâmetro → a principal se for dele,
  senão a primeira oferta ativa dele; em qualquer caso, `professor_da_oferta(oferta, current_user)` falso ⇒
  **403** (inclui oferta inexistente/inativa, oferta sem professor e turma sem oferta ativa dele).
- Lista de alunos: `_alunos_da_oferta` também quando há **uma** oferta ativa (só inscritos na oferta dele).
- Linha “Outras ofertas” (query `outras_ofertas_por_aluno`) **não roda** para professor ⇒ bloco não é impresso.
- Admin/pedagógico/secretaria: **código antigo preservado** (0/1/2+ ofertas, flash + redirect, “Outras
  ofertas”, header “Professor:” com fallback).

## Comportamento antes × depois (professor)

| Caso | Antes | Depois |
| --- | --- | --- |
| É o professor da oferta (e não o da turma) | 403 | **200** |
| É o professor da turma, mas não da oferta | 200 | **403** |
| Oferta sem professor (ele é o da turma) | 200 | **403** |
| Turma sem oferta ativa (modo legado) | 200 | **403** |
| 2+ ofertas sem `turma_curso`, principal de outro | flash + redirect | **imprime a primeira oferta ativa dele** |
| 2+ ofertas sem `turma_curso`, não leciona nenhuma | flash + redirect | **403** |
| Alunos listados | por oferta só com 2+ ofertas | **sempre por oferta** |
| “Outras ofertas” | exibida | **oculta** |
| Admin/pedagógico/secretaria | — | inalterados |

## Testes

`tests/test_pauta_impressa_por_oferta.py` (**15**), cenário com `turma.professor_id = prof_c` (não leciona) e
ofertas de `prof_a` (principal) e `prof_b`:

- 200 nas duas ofertas próprias (alunos e curso corretos; alunos das outras ofertas ausentes);
- 403: professor da turma sem oferta, oferta de outro professor, oferta inativa, oferta sem professor (admin
  200 no mesmo caso);
- resolução sem parâmetro: principal quando é dele, primeira ativa dele quando não é;
- alunos somente da oferta com **uma** oferta ativa;
- “Outras ofertas” oculta para professor e preservada para admin; redirect do admin com 2+ ofertas sem
  parâmetro mantido;
- I1 sem herança: professor da turma → 403 no endpoint; professor da oferta (sem ser o da turma) → 200 e as
  linhas de acompanhante/instruções na impressão.

**Testes existentes ajustados: nenhum** (os testes de impressão já usavam ofertas com professor cadastrado;
rodei `test_pauta_professor.py`, `test_info_professor*.py`, `test_impressao_grade_oferta.py`,
`test_turma_curso_fase4.py`, `test_valor_esportista_nao_regressao.py` e `test_valor_obrigatorio.py` antes da
suíte completa: 104 passed).

## Ensaio (`pautaon_ensaio`, somente leitura — sem escritas)

`professor.m1@roteiro.local` (id 120, unidade 13):

| Requisição | Resultado |
| --- | --- |
| `GET /turma/30/imprimir-pauta?turma_curso=44` (oferta dele) | **200** |
| `GET /turma/30/imprimir-pauta` (sem parâmetro, única oferta ativa) | **200** |
| `GET /turma/9/imprimir-pauta?turma_curso=12` (oferta de outro professor, turma 9 unidade 2) | **403** |
| `GET /turma/34/imprimir-pauta?turma_curso=50` (oferta sem professor, turma 34 unidade 14) | **403** |

Na unidade 13 as quatro ofertas ativas (44–47) são **todas** do professor 120, então o ensaio não tem
“oferta alheia na mesma unidade” para isolar a guarda por oferta — esse caso está coberto pelos testes
automatizados (mesma unidade, professores diferentes). Nenhum dado foi criado, alterado ou apagado; banco
principal intocado.

## Efeitos e pendências registradas (backlog)

1. Professor da turma que não leciona nenhuma oferta ativa perde impressão e I1 (decisão).
2. Turma sem oferta ativa → professor recebe 403 na impressão.
3. O botão “Imprimir” da pauta de frequência continua visível para a oferta selecionada; se não for dele, o
   servidor responde 403 — esconder/desabilitar o botão é melhoria de UI pendente.
4. Herança de `turma.professor_id` permanece nas demais guardas/leitores (inventário acima) — alinhamento
   futuro, fora do escopo desta parte.
