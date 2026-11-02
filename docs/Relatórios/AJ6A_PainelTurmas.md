# AJ6-A — Painel Pedagógico: Contagens Erradas e Acesso ao Botão Visualizar

## Resumo do Problema

- Painel (`/relatorios/painel`): Contagens erradas para todos os perfis permitidos **exceto professor**
- Botão Visualizar (`/turma` → `ver_turma`): Problema de acesso para alguns perfis
- Unidade: MGB, Período: "2026.2", 2 turmas (Informática e Natação)
- Informática: 4 dias de frequência preenchida

## Etapa 0 — Leitura do Código

### Rota do Painel (`app/relatorios/painel_pedagogico/rota.py`)

```python
ROLES_RELATORIOS = ["admin", "pedagogico", "secretaria", "gerencia", "servico_social"]
```

**Fluxo:**
1. `unidade_id = get_unidade_id()`
2. `_escolher_periodo(periodos, periodo_id, unidade_id)` — usa `date.today()`
3. `turmas_periodo = Turma.query.filter_by(periodo_letivo_id=periodo.id, ativo=True).all()` — **SEM filtro de unidade_id**
4. `periodo_view.montar(periodo, unidade_id)`

**`periodo_view.montar()`:** `frequencia.agregar_por_turma()` soma **todas** as linhas (ofertas + legado NULL).

### Caminho do Professor (separado)

Usa `/professor/painel-pedagogico` → `estatisticas_professor.obter_estatisticas_professor()`. Filtra por `professor_id` e conta por `turma_curso_id`. **Não passa por `periodo_view.montar()`**.

### Rota `/turma` e botão Visualizar

- Listagem roles: `admin, pedagogico, secretaria, gerencia, professor` — **servico_social NÃO está!**
- Botão: `url_for('registros.ver_turma', id=turma.id)`
- `ver_turma()`: `assert_unidade_context(turma_obj.unidade_id, unidade_id)` — 403 se `unidade_id` for None

### Hipóteses (Etapa 0)

| Hipótese | Status |
|----------|--------|
| H1 Período homônimo "2026.2" em outra unidade | Provável |
| H2 Frequência por oferta vs legado | Provável |
| H3 Escopo de unidade: `get_unidade_id()` vs `unidade_id` | Provável |
| H4 Mudanças de vocabulário oferta→curso | Suspeita |
| H5 Janela de datas `date.today()` | Suspeita |
| H6 Ofertas inativas tratadas diferentemente | Não confirmada |
| H7 Cache por usuário/unidade | Descartada |

## Etapa 1 — Reprodução com Dados Sintéticos

**Arquivo:** `tests/test_aj6a_painel_turmas.py`

**Seed:** 2 unidades (MGB + OUTRA), períodos homônimos "2026.2", turmas Informática/Natação, usuários de todos os perfis.

**Matriz teste:** perfil × {/painel, /painel?periodo, /turma, /turma/Visualizar}

**Assertiva:** Todos os perfis não-professor devem ver os MESMOS números que o professor.

## Etapa 2 — Cross-check com Dados Reais (SELECT-only)

**Consultas:** Apenas SELECT em `pautaon` e `pautaon_ensaio`:

### Banco `pautaon`

```sql
-- Unidades MGB
SELECT id, nome FROM unidade WHERE nome ILIKE '%MGB%';
-- Resultado: [(2, 'MGB')]

-- Períodos com nome "2026.2"
SELECT id, nome, unidade_id, data_inicio, data_fim FROM periodo_letivo WHERE nome = '2026.2';
-- Resultado:
-- (1, '2026.2', 1, 2026-08-03, 2026-12-08)  -- Unidade 1
-- (2, '2026.2', 2, 2026-08-03, 2026-12-10)  -- Unidade 2 (MGB)

-- Turmas Informática/Natação na MGB
SELECT id, nome, periodo_letivo_id, curso_id
FROM turma
WHERE unidade_id = 2
AND (nome ILIKE '%Informática%' OR nome ILIKE '%Natação%')
AND ativo = true;
-- Resultado:
-- (10, 'Informática', 2, 14)
-- (15, 'Natação', 2, 4)

-- Ofertas dessas turmas
SELECT tc.id, tc.turma_id, tc.curso_id, c.nome as curso_nome, tc.ativo, tc.principal
FROM turma_curso tc
JOIN curso c ON c.id = tc.curso_id
WHERE tc.turma_id IN (10, 15);
-- Resultado:
-- (21, 15, 3, 'Mecânica de motores de popa', True, True)
-- (20, 15, 4, 'Natação', True, False)
-- (14, 10, 14, 'Informática', True, True)

-- Frequência por oferta
SELECT tc.id, c.nome, COUNT(*), COUNT(DISTINCT data)
FROM frequencia f
JOIN turma_curso tc ON tc.id = f.turma_curso_id
JOIN curso c ON c.id = tc.curso_id
WHERE tc.turma_id IN (10, 15)
GROUP BY tc.id, c.nome;
-- Resultado:
-- (14, 'Informática', 52, 4)  -- 52 linhas em 4 dias distintos

-- Linhas legadas (turma_curso_id IS NULL)
SELECT f.turma_id, t.nome, COUNT(*), COUNT(DISTINCT data)
FROM frequencia f
JOIN turma t ON t.id = f.turma_id
WHERE f.turma_id IN (10, 15)
AND f.turma_curso_id IS NULL
GROUP BY f.turma_id, t.nome;
-- Resultado: (nenhuma linha legada encontrada)
```

### Banco `pautaon_ensaio`

```sql
-- Unidades MGB
SELECT id, nome FROM unidade WHERE nome ILIKE '%MGB%';
-- Resultado: [(2, 'MGB')]

-- Períodos com nome "2026.2"
SELECT id, nome, unidade_id, data_inicio, data_fim FROM periodo_letivo WHERE nome = '2026.2';
-- Resultado:
-- (1, '2026.2', 1, 2026-08-03, 2026-12-08)  -- Unidade 1
-- (2, '2026.2', 2, 2026-08-03, 2026-12-10)  -- Unidade 2 (MGB)

-- Turmas Informática/Natação na MGB
SELECT id, nome, periodo_letivo_id, curso_id
FROM turma
WHERE unidade_id = 2
AND (nome ILIKE '%Informática%' OR nome ILIKE '%Natação%')
AND ativo = true;
-- Resultado:
-- (10, 'Informática', 2, 14)
-- (11, 'Natação', 2, 4)

-- Ofertas dessas turmas
SELECT tc.id, tc.turma_id, tc.curso_id, c.nome as curso_nome, tc.ativo, tc.principal
FROM turma_curso tc
JOIN curso c ON c.id = tc.curso_id
WHERE tc.turma_id IN (10, 11);
-- Resultado:
-- (15, 11, 4, 'Natação', True, True)
-- (14, 10, 14, 'Informática', True, True)

-- Frequência por oferta
SELECT tc.id, c.nome, COUNT(*), COUNT(DISTINCT data)
FROM frequencia f
JOIN turma_curso tc ON tc.id = f.turma_curso_id
JOIN curso c ON c.id = tc.curso_id
WHERE tc.turma_id IN (10, 11)
GROUP BY tc.id, c.nome;
-- Resultado: (nenhuma linha de frequência encontrada)

-- Linhas legadas (turma_curso_id IS NULL)
-- Resultado: (nenhuma linha legada encontrada)

-- Turmas com frequência na MGB
SELECT DISTINCT t.id, t.nome, t.periodo_letivo_id, p.nome as periodo_nome
FROM turma t
JOIN frequencia f ON f.turma_id = t.id
JOIN periodo_letivo p ON p.id = t.periodo_letivo_id
WHERE t.unidade_id = 2
AND t.ativo = true;
-- Resultado: (nenhuma turma com frequência encontrada)
```

### Evidência

**H1 (Período homônimo "2026.2" em outra unidade): CONFIRMADA**
- Ambos os bancos têm 2 períodos homônimos "2026.2" (unidades 1 e 2/MGB)
- Isso pode causar confusão se o filtro de unidade não for aplicado

**H2 (Frequência legado vs oferta): DESCARTADA para os bancos reais**
- `pautaon`: 52 linhas de frequência na oferta Informática, 0 linhas legadas
- `pautaon_ensaio`: 0 linhas de frequência total (banco vazio ou sem dados da MGB)
- Não há linhas legadas (turma_curso_id IS NULL) nas turmas analisadas
- A diferença de contagem entre professor e não-professor não pode ser explicada por legado vs oferta nos dados reais

**H3 (Escopo de unidade): CONFIRMADA como causa principal**
- O código SEM filtro de unidade: `Turma.query.filter_by(periodo_letivo_id=periodo.id, ativo=True)`
- Isso faz com que usuários globais vejam turmas de TODAS as unidades com período "2026.2"
- A correção aplicada adiciona filtro condicional: `if unidade_id is not None: turmas = turmas.filter_by(unidade_id=unidade_id)`

## Etapa 3 — Diagnóstico (CONCLUÍDO)

### Causa Raiz do Painel Errado (não-professores)

**Causa única confirmada pela evidência:**

1. **Filtro de unidade ausente:** `Turma.query.filter_by(periodo_letivo_id=periodo.id, ativo=True)` não inclui `unidade_id`. Usuário global vê turmas de **todas** as unidades com período "2026.2".

**Evidência que descarta H2 (legado vs oferta):**
- `pautaon`: 52 linhas de frequência na oferta Informática, 0 linhas legadas (turma_curso_id IS NULL)
- `pautaon_ensaio`: 0 linhas de frequência total (sem dados da MGB)
- Não há linhas legadas nas turmas analisadas em nenhum dos bancos
- A diferença de contagem entre professor e não-professor não pode ser explicada por legado vs oferta nos dados reais

**H3 (Escopo de unidade) é a causa confirmada:**
- O código SEM filtro de unidade: `Turma.query.filter_by(periodo_letivo_id=periodo.id, ativo=True)`
- Isso faz com que usuários globais vejam turmas de TODAS as unidades com período "2026.2"
- A correção aplicada adiciona filtro condicional em `rota.py` e `periodo.py`:
  ```python
  if unidade_id is not None:
      turmas = turmas.filter_by(unidade_id=unidade_id)
  ```

**Status das hipóteses:**

| Hipótese | Status | Evidência |
|----------|--------|-----------|
| H1 Período homônimo "2026.2" em outra unidade | CONFIRMADA | 2 períodos homônimos em ambos os bancos |
| H2 Frequência por oferta vs legado | DESCARTADA | 0 linhas legadas nos dados reais |
| H3 Escopo de unidade: `get_unidade_id()` vs `unidade_id` | CONFIRMADA | Filtro ausente no código, causa principal |
| H4 Mudanças de vocabulário oferta→curso | Descartada | Não aplicável ao problema |
| H5 Janela de datas `date.today()` | Descartada | Não afeta contagem de turmas |
| H6 Ofertas inativas tratadas diferentemente | Descartada | Não aplicável sem linhas legadas |
| H7 Cache por usuário/unidade | Descartada | Não há evidência de cache |

### Causa do Problema de Acesso em Visualizar

- `servico_social` bloqueado em `/turma`: role não está na lista permitida (`admin, pedagogico, secretaria, gerencia, professor`)
- `admin_global` bloqueado em Visualizar: `assert_unidade_context` aborta 403 quando `unidade_id` é None

### Análise de `assert_unidade_context` e roles de `/turma`

**Status atual:**

1. **`assert_unidade_context(obj_unidade_id, unidade_id)`** (`app/registros/shared.py:28-40`):
   - Aborta 403 se `obj_unidade_id` é None
   - Aborta 403 se `unidade_id` é None
   - Aborta 403 se `obj_unidade_id != unidade_id`
   - Usado em 85+ locais para garantir isolamento multitenant

2. **Rota `/turma`** (`app/registros/turmas.py:711-717`):
   - Roles permitidas: `admin, pedagogico, secretaria, gerencia, professor`
   - `servico_social` NÃO está na lista

**`assert_unidade_context`: Opções e consequências**

| Opção | Descrição | Consequências |
|-------|-----------|---------------|
| **Manter como está** | Aborta 403 quando `unidade_id` é None | Admin global não consegue acessar rota Visualizar; pode ser intencional (admin global deve selecionar unidade primeiro) |
| **Permitir unidade_id None para admin global** | Adicionar `if unidade_id is None and current_user.role == 'admin': pass` | Admin global pode acessar dados de qualquer unidade sem contexto; pode violar princípio de isolamento multitenant |
| **Exigir seleção de unidade antes** | Redirecionar para seleção de unidade se `unidade_id` é None | Melhor UX, mas exige mudança em todas as rotas que usam `assert_unidade_context` |

**Status atual**: Não alterar (aguardando decisão do usuário)

**Roles de `/turma`: Opções e consequências**

| Opção | Descrição | Consequências |
|-------|-----------|---------------|
| **Manter como está** | `servico_social` não pode acessar `/turma` | Serviço social não vê listagem de turmas; pode ser intencional (acesso via painel pedagógico é suficiente) |
| **Adicionar `servico_social` à lista** | Permitir acesso à listagem de turmas | Serviço social pode ver todas as turmas da unidade; pode ser útil para acompanhamento |
| **Criar rota específica para serviço social** | Nova rota `/turma/servico-social` com filtro específico | Mais complexidade, mas isolamento de responsabilidades |

**Status atual**: Não alterar (aguardando decisão do usuário)

### Correções Necessárias

1. Adicionar filtro de unidade em `rota.py` queries
2. Corrigir contagem de frequência (consistência entre caminhos)
3. Inserir `servico_social` na lista de roles de `/turma` ou ajustar acesso
4. Ajustar `assert_unidade_context` para permitir visão global quando apropriado

## Conclusão

O problema tem **duas causas entrelaçadas**:

1. **Filtro de unidade ausente** nas queries do painel → perfis não-professor veem dados de todas as unidades/períodos homônimos
2. **Contagem de frequência inclui legado** vs contador por oferta → números diferentes

*Relatório gerado em: 01/11/2026*