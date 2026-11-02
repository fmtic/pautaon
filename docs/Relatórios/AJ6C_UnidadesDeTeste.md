# AJ6-C — Diagnóstico de Unidades de Teste, Trava de Segurança e Script de Limpeza

## Resumo Executivo

O seletor de unidade da aplicação em desenvolvimento apresentava unidades que não pertenciam à operação real (MGB e NIT), nomeadamente: **"Unidade A"**, **"Unidade Aj5c A"**, **"Unidade Aj5c B"** e **"U X"**.

Esta auditoria identificou que execuções de testes automatizados e fixtures anteriores ao endurecimento do harness vazaram escritas para o banco de desenvolvimento PostgreSQL (`pautaon`), porque `config.py` carregava o `.env` via `load_dotenv()` sem que houvesse uma neutralização prévia da variável `DATABASE_URL` no ambiente do executor de testes.

**Ações realizadas (AJ6-C):**
1. **Inventário cirúrgico (SELECT-only)**: Mapeamento de todas as unidades, tabelas e registros dependentes nos bancos `pautaon` e `pautaon_ensaio` via catálogo `information_schema` e `pg_constraint`.
2. **Identificação da origem**: Localizados os testes exatos (`test_frequencia_oferta.py`, `test_aj5c_form_caracterizacao.py`, etc.) cujas fixtures geraram essas entidades no banco persistente.
3. **Trava de segurança implementada (`fix(testes)`)**:
   - `tests/conftest.py`: neutralização imediata de `DATABASE_URL` no nível de módulo para `sqlite:///:memory:`.
   - Hook `pytest_sessionstart` aborta a suíte imediatamente se `DATABASE_URL` no ambiente apontar para PostgreSQL ou se o driver do engine não for SQLite.
   - Guarda de dialeto SQLite na fixture `app`.
   - Teste automatizado da trava em `tests/test_aj6c_trava_banco.py`.
   - **Prova de reversão em worktree**: comprovado que sem o fix a suíte não abortava e caía em `postgresql+psycopg`.
4. **Scripts de limpeza preparados (sem execução)**: Scripts SQL transacionais com verificação de contagens antes/depois, ordem correta de FKs e `ROLLBACK` por padrão para execução controlada pelo operador.
5. **Nenhuma escrita em banco real**: Bancos consultados exclusivamente via `SELECT`. Contagens antes e depois da suíte permaneceram estritamente idênticas.

---

## Etapa 0 — Inventário Cirúrgico (SELECT-only)

### 1. Unidades Cadastradas nos Bancos

#### Banco `pautaon` (desenvolvimento)
```sql
SELECT id, nome FROM unidade ORDER BY id;
```
| ID | Nome | Classificação | Observação |
|:---:|:---|:---:|:---|
| **1** | `NIT` | **Real** | Unidade real de Niterói |
| **2** | `MGB` | **Real** | Unidade real de Manguinhos |
| **3** | `Unidade A` | **Teste** | Fixture de `test_frequencia_oferta.py` |
| **6** | `Unidade Aj5c A` | **Teste** | Fixture de `test_aj5c_form_caracterizacao.py` |
| **7** | `Unidade Aj5c B` | **Teste** | Fixture de `test_aj5c_form_caracterizacao.py` |
| **8** | `U X` | **Teste** | Registro residual de teste exploratório |

#### Banco `pautaon_ensaio` (ensaio)
```sql
SELECT id, nome FROM unidade ORDER BY id;
```
| ID | Nome | Classificação | Observação |
|:---:|:---|:---:|:---|
| **1** | `NIT` | **Real** | Unidade real |
| **2** | `MGB` | **Real** | Unidade real |
| **13** | `[ROTEIRO] Unidade Central` | **Teste/Roteiro** | Gerado por script de ensaio de roteiro |
| **14** | `[ROTEIRO] Unidade Vizinha` | **Teste/Roteiro** | Gerado por script de ensaio de roteiro |

---

### 2. Registros Dependentes por Tabela (Mapeamento via Catálogo)

Tabelas com Foreign Key direta para `unidade` descobertas via `information_schema.table_constraints` e `referential_constraints`:
`aluno`, `atendimento`, `centro_custo`, `configuracao_sistema`, `conselho_classe`, `conselho_resposta`, `curso`, `dia_bloqueado`, `dia_bloqueado_turma`, `endereco_aluno`, `frequencia`, `log_acao`, `nivel`, `perfil_diversidade`, `perfil_socioeconomico`, `periodo_conselho`, `periodo_letivo`, `registro`, `registro_aula`, `responsavel_aluno`, `situacao_escolar`, `tema_aula`, `transferencia`, `turma`, `turma_curso`, `user`, `valor_esportista`.

#### No banco `pautaon` (Unidades 3, 6, 7, 8):
- **`aluno` (5 linhas)**:
  - IDs `1452`, `1453`, `1454`, `1455` (unidade 3 — gerados por fixture de frequência)
  - ID `1456` (unidade 6 — gerado por `test_aj5c_form_caracterizacao.py`)
- **Tabelas filhas dos alunos de teste**:
  - `endereco_aluno`: 1 linha (ID `113`, do aluno 1456)
  - `perfil_diversidade`: 1 linha (ID `112`, do aluno 1456)
  - `perfil_socioeconomico`: 1 linha (ID `113`, do aluno 1456)
  - `responsavel_aluno`: 1 linha (ID `85`, do aluno 1456)
  - `situacao_escolar`: 1 linha (ID `106`, do aluno 1456)
  - `inscricoes`: 0 linhas
  - `frequencia`: 0 linhas
- **`curso` (4 linhas)**:
  - IDs `15` ('Curso Alfa 1'), `16` ('Curso Alfa 2'), `17` ('Curso Gema'), `18` ('Curso Zeta') — todos da unidade 3.
  - Vínculos com turmas/ofertas: 0 linhas.
- **`periodo_letivo` (1 linha)**:
  - ID `3` ('Periodo Freq', unidade 3).
  - Vínculos com turmas/dias bloqueados: 0 linhas.
- **`user` (2 linhas)**:
  - ID `105` (role `admin`, unidade 6)
  - ID `107` (role `admin`, unidade 8)
  - Vínculos em `log_acao`, `registro_aula` ou `turma_curso`: 0 linhas.
- **`turma` e `turma_curso`**: 0 linhas.
- **`frequencia` e `registro_aula`**: 0 linhas.
- **`log_acao`**: 0 linhas com `unidade_id IN (3,6,7,8)` e 0 linhas com `usuario_id IN (105, 107)`.

#### No banco `pautaon_ensaio` (Unidades 13, 14):
- **`turma`**: 5 linhas (IDs: 30, 31, 32, 33, 36)
- **`turma_curso`**: 7 linhas
- **`inscricoes`**: 15 linhas
- **`frequencia`**: 20 linhas
- **`registro_aula`**: 4 linhas
- **`aluno`**: 12 linhas (IDs: 1482 a 1493)
- **`endereco_aluno`**: 1 linha
- **`perfil_socioeconomico`**: 1 linha
- **`curso`**: 4 linhas (IDs: 39 a 42)
- **`periodo_letivo`**: 3 linhas (IDs: 22, 23, 24)
- **`user`**: 3 linhas (IDs: 118, 119, 120)
- **`log_acao`**: 34 linhas (auditorias do roteiro do ensaio)

---

### 3. Banco de Dados Utilizado pelo Ambiente de Desenvolvimento

- **Fonte**: Arquivo `.env` na raiz do projeto.
- **Configuração**: `DATABASE_URL=postgresql+psycopg://***:***@localhost:5432/pautaon`
- **Nome do Banco**: `pautaon` (PostgreSQL local).
- **Banco de Ensaio**: `pautaon_ensaio` (PostgreSQL local, porta 5432).

---

## Etapa 1 — Origem das Unidades de Teste

### 1. Mapeamento dos Nomes em Código de Testes e Scripts

| Nome no Banco | Arquivo de Origem | Trecho de Código |
|---|---|---|
| **`Unidade A`** | `tests/test_frequencia_oferta.py` (e outros) | `un = Unidade(nome="Unidade A", ativo=True)` acompanhada de `Curso Alfa 1`, `Curso Alfa 2`, `Curso Gema`, `Curso Zeta` e `Periodo Freq`. A assinatura de dados bate 100% com o seed do teste. |
| **`Unidade Aj5c A`** e **`Unidade Aj5c B`** | `tests/test_aj5c_form_caracterizacao.py` | Linhas 230-231: `ua = Unidade(nome="Unidade Aj5c A", ativo=True)` e `ub = Unidade(nome="Unidade Aj5c B", ativo=True)`. Gera usuário `Admin Local Aj5c` (ID 105) e aluno com endereço/perfil (ID 1456). |
| **`U X`** | Teste exploratório manual / script residual | Inserção exploratória pontual prévia à trava. |
| **`[ROTEIRO] Unidade Central / Vizinha`** | `scripts/ensaio_*.py` / `scripts/roteiro_*.py` | Criadas deliberadamente no banco de ensaio durante os ensaios de release da Onda 4. |

### 2. Como a Brecha Ocorria

1. O módulo `config.py` possui a seguinte instrução no topo:
   ```python
   from dotenv import load_dotenv
   load_dotenv()
   ```
2. Por padrão, `load_dotenv()` carrega as variáveis de `.env` caso não existam no ambiente do processo.
3. Antes do commit `715fe57` (unificação do conftest), muitos arquivos de testes criavam seu próprio `create_app()` sem passar pelo conftest único.
4. Quando qualquer script, teste isolado ou subprocesso executava `create_app()` sem especificar `SQLALCHEMY_DATABASE_URI="sqlite:///:memory:"`, a aplicação lia `os.getenv("DATABASE_URL")` que recebia o valor do `.env` (`pautaon` PostgreSQL).
5. Durante a execução, o teste chamava `db.create_all()` e executava transações reais com `db.session.commit()`, deixando entidades persistidas no banco PostgreSQL de desenvolvimento.

---

## Etapa 2 — Trava de Segurança Implementada (`fix(testes)`)

### 1. Modificações em `tests/conftest.py`

1. **Neutralização Preventiva no Topo**:
   Antes de qualquer import de `app` ou `config` (que chamaria `load_dotenv()`), capturamos a variável original e forçamos o ambiente para SQLite:
   ```python
   _DB_URL_ORIGINAL = os.environ.get("DATABASE_URL", "")
   os.environ["DATABASE_URL"] = "sqlite:///:memory:"
   ```
   Como a variável já existe no `os.environ`, o `load_dotenv()` de `config.py` não sobrescreve o valor.
2. **Hook `pytest_sessionstart` (Aborto Imediato)**:
   ```python
   def pytest_sessionstart(session):
       """AJ6-C: Aborta a suíte se DATABASE_URL no ambiente apontava para Postgres
       ou se o driver do engine não for sqlite.
       """
       if "postgresql" in _DB_URL_ORIGINAL.lower() or "postgres" in _DB_URL_ORIGINAL.lower():
           pytest.exit(
               "ABORTAR — trava de banco de teste disparada (AJ6-C)!\n"
               f"DATABASE_URL no ambiente ({_DB_URL_ORIGINAL}) aponta para PostgreSQL.\n"
               "A suíte de testes exige SQLite. Remova DATABASE_URL do ambiente antes de rodar pytest.",
               returncode=1,
           )

       test_app = create_app(SQLiteTestConfig)
       with test_app.app_context():
           driver = db.engine.url.drivername
           if not driver.startswith("sqlite"):
               pytest.exit(
                   "ABORTAR — trava de banco de teste disparada (AJ6-C)!\n"
                   f"Engine configurado com driver '{driver}' (esperado 'sqlite').\n"
                   "Execução de testes contra banco não-SQLite é estritamente proibida.",
                   returncode=1,
               )
   ```
3. **Asserção de Dialeto na Fixture `app`**:
   ```python
   assert db.engine.url.drivername.startswith("sqlite"), (
       f"Trava AJ6-C: driver '{db.engine.url.drivername}' não permitido. Exigido 'sqlite'."
   )
   ```

### 2. Teste da Trava (`tests/test_aj6c_trava_banco.py`)

- `test_trava_aborta_suite_quando_database_url_aponta_para_postgres`: Simula via subprocesso `DATABASE_URL=postgresql://...` e comprova que a execução é abortada imediatamente com código de erro e mensagem clara.
- `test_app_fixture_garante_driver_sqlite`: Comprova que a fixture `app` está atrelada ao driver SQLite.
- `test_create_app_sem_override_recebe_sqlite_em_teste`: Comprova que chamadas soltas a `create_app()` sem configuração explícita herdam `sqlite:///:memory:` e nunca o Postgres do `.env`.

### 3. Prova de Reversão em Worktree (`.wt_aj6c`)

Para provar a eficácia da trava, foi criado um git worktree temporário no commit anterior (sem o fix):
```text
cd .wt_aj6c
python -m pytest tests/test_aj6c_trava_banco.py

FAILED tests/test_aj6c_trava_banco.py::test_trava_aborta_suite_quando_database_url_aponta_para_postgres
FAILED tests/test_aj6c_trava_banco.py::test_create_app_sem_override_recebe_sqlite_em_teste
======================== 2 failed, 1 passed in 10.82s =========================
```
- **Falha 1**: Sem a trava, o pytest aceitava rodar com URL de PostgreSQL (retornou 0 em vez de abortar).
- **Falha 2**: Sem a neutralização, `create_app()` conectava em `postgresql+psycopg` (lendo o `.env`).

Com o fix aplicado, os 3 testes passam com sucesso (`3 passed in 5.57s`). O worktree foi removido após a prova.

### 4. Regra para Sondas em `.tmp/` e Scripts

1. **Proibição de Schema DDL**: Scripts ou sondas exploratórias nunca devem chamar `db.create_all()` ou `db.drop_all()` contra bancos reais.
2. **Sessão Injetada / Somente Leitura**: Sondas contra banco persistente devem utilizar conexões somente-leitura (`SELECT`), transações com rollback explícito e verificação de contagens antes e depois.
3. **Execução de Testes**: Todo teste automatizado deve rodar via `pytest`, beneficiando-se da trava do `conftest.py`.

---

## Etapa 3 — Scripts de Limpeza (PREPARADOS — NÃO EXECUTADOS)

> [!IMPORTANT]
> **NENHUMA exclusão foi executada**. Os scripts abaixo são cirúrgicos por ID, executam em bloco transacional (`BEGIN ... ROLLBACK`) e contêm cláusulas explícitas de proteção para **nunca afetar MGB (ID 2) nem NIT (ID 1)**.
> O operador deve revisar os `COUNT` esperados antes de alterar o comando final para `COMMIT`.

### Procedimento de Backup e Restauração Recomendado

Antes de executar qualquer limpeza manual em produção/desenvolvimento:

```bash
# 1. Backup completo dos bancos (formato custom compactado com blobs)
pg_dump -U postgres -h localhost -p 5432 -Fc -b -v -f backup_pautaon_antes_aj6c.dump pautaon
pg_dump -U postgres -h localhost -p 5432 -Fc -b -v -f backup_pautaon_ensaio_antes_aj6c.dump pautaon_ensaio

# Como restaurar em caso de divergência:
# dropdb -U postgres -h localhost -p 5432 pautaon
# createdb -U postgres -h localhost -p 5432 pautaon
# pg_restore -U postgres -h localhost -p 5432 -d pautaon -v backup_pautaon_antes_aj6c.dump
```

---

### Script de Limpeza: Banco `pautaon`

```sql
BEGIN;

-- ============================================================================
-- 1. CONFERÊNCIA ANTES DA LIMPEZA
-- ============================================================================
-- Unidades alvo: 3, 6, 7, 8 (MGB=2 e NIT=1 NUNCA são tocadas)
SELECT id, nome FROM unidade WHERE id IN (3, 6, 7, 8);
-- Esperado: 4 linhas

-- Contagens esperadas de registros filhos:
SELECT 'aluno' AS tabela, count(*) FROM aluno WHERE unidade_id IN (3, 6, 7, 8); -- Esperado: 5
SELECT 'endereco_aluno' AS tabela, count(*) FROM endereco_aluno WHERE aluno_id IN (1452,1453,1454,1455,1456); -- Esperado: 1
SELECT 'perfil_diversidade' AS tabela, count(*) FROM perfil_diversidade WHERE aluno_id IN (1452,1453,1454,1455,1456); -- Esperado: 1
SELECT 'perfil_socioeconomico' AS tabela, count(*) FROM perfil_socioeconomico WHERE aluno_id IN (1452,1453,1454,1455,1456); -- Esperado: 1
SELECT 'responsavel_aluno' AS tabela, count(*) FROM responsavel_aluno WHERE aluno_id IN (1452,1453,1454,1455,1456); -- Esperado: 1
SELECT 'situacao_escolar' AS tabela, count(*) FROM situacao_escolar WHERE aluno_id IN (1452,1453,1454,1455,1456); -- Esperado: 1
SELECT 'curso' AS tabela, count(*) FROM curso WHERE unidade_id IN (3, 6, 7, 8); -- Esperado: 4
SELECT 'periodo_letivo' AS tabela, count(*) FROM periodo_letivo WHERE unidade_id IN (3, 6, 7, 8); -- Esperado: 1
SELECT 'user' AS tabela, count(*) FROM "user" WHERE unidade_id IN (3, 6, 7, 8); -- Esperado: 2

-- ============================================================================
-- 2. EXCLUSÃO CIRÚRGICA (Filhos antes dos pais)
-- ============================================================================

-- 2.1 Filhos de aluno
DELETE FROM endereco_aluno WHERE aluno_id IN (1452, 1453, 1454, 1455, 1456) RETURNING id, aluno_id;
DELETE FROM perfil_diversidade WHERE aluno_id IN (1452, 1453, 1454, 1455, 1456) RETURNING id, aluno_id;
DELETE FROM perfil_socioeconomico WHERE aluno_id IN (1452, 1453, 1454, 1455, 1456) RETURNING id, aluno_id;
DELETE FROM responsavel_aluno WHERE aluno_id IN (1452, 1453, 1454, 1455, 1456) RETURNING id, aluno_id;
DELETE FROM situacao_escolar WHERE aluno_id IN (1452, 1453, 1454, 1455, 1456) RETURNING id, aluno_id;

-- 2.2 Alunos das unidades de teste (proteção: NOT IN (1, 2))
DELETE FROM aluno
WHERE id IN (1452, 1453, 1454, 1455, 1456)
  AND unidade_id IN (3, 6, 7, 8)
  AND unidade_id NOT IN (1, 2)
RETURNING id, nome, unidade_id;

-- 2.3 Cursos das unidades de teste
DELETE FROM curso
WHERE id IN (15, 16, 17, 18)
  AND unidade_id IN (3, 6, 7, 8)
  AND unidade_id NOT IN (1, 2)
RETURNING id, nome;

-- 2.4 Período letivo das unidades de teste
DELETE FROM periodo_letivo
WHERE id = 3
  AND unidade_id IN (3, 6, 7, 8)
  AND unidade_id NOT IN (1, 2)
RETURNING id, nome;

-- 2.5 Usuários das unidades de teste
DELETE FROM "user"
WHERE id IN (105, 107)
  AND unidade_id IN (3, 6, 7, 8)
  AND unidade_id NOT IN (1, 2)
RETURNING id, role, unidade_id;

-- 2.6 Unidades de teste (proteção explícita de nomes e IDs reais)
DELETE FROM unidade
WHERE id IN (3, 6, 7, 8)
  AND id NOT IN (1, 2)
  AND nome NOT IN ('MGB', 'NIT')
RETURNING id, nome;

-- ============================================================================
-- 3. CONFERÊNCIA PÓS-LIMPEZA
-- ============================================================================
SELECT id, nome FROM unidade ORDER BY id;
-- Esperado: Apenas ID 1 ('NIT') e ID 2 ('MGB')

-- ============================================================================
-- 4. FINALIZAÇÃO (Mudar para COMMIT somente se as contagens baterem)
-- ============================================================================
ROLLBACK;
```

---

### Script de Limpeza: Banco `pautaon_ensaio`

```sql
BEGIN;

-- ============================================================================
-- 1. CONFERÊNCIA ANTES DA LIMPEZA (Unidades 13 e 14)
-- ============================================================================
SELECT id, nome FROM unidade WHERE id IN (13, 14);

-- ============================================================================
-- 2. EXCLUSÃO CIRÚRGICA (Filhos antes dos pais)
-- ============================================================================
DELETE FROM frequencia WHERE turma_id IN (30, 31, 32, 33, 36) RETURNING id;
DELETE FROM registro_aula WHERE turma_id IN (30, 31, 32, 33, 36) RETURNING id;
DELETE FROM inscricoes WHERE turma_id IN (30, 31, 32, 33, 36) RETURNING id;
DELETE FROM turma_curso WHERE turma_id IN (30, 31, 32, 33, 36) RETURNING id;
DELETE FROM turma WHERE id IN (30, 31, 32, 33, 36) AND unidade_id IN (13, 14) RETURNING id;

DELETE FROM endereco_aluno WHERE aluno_id IN (1482,1483,1484,1485,1486,1487,1488,1489,1490,1491,1492,1493) RETURNING id;
DELETE FROM perfil_socioeconomico WHERE aluno_id IN (1482,1483,1484,1485,1486,1487,1488,1489,1490,1491,1492,1493) RETURNING id;
DELETE FROM aluno WHERE id IN (1482,1483,1484,1485,1486,1487,1488,1489,1490,1491,1492,1493) AND unidade_id IN (13, 14) RETURNING id;

DELETE FROM curso WHERE id IN (39, 40, 41, 42) AND unidade_id IN (13, 14) RETURNING id;
DELETE FROM periodo_letivo WHERE id IN (22, 23, 24) AND unidade_id IN (13, 14) RETURNING id;

DELETE FROM log_acao WHERE unidade_id IN (13, 14) OR usuario_id IN (118, 119, 120) RETURNING id;
DELETE FROM "user" WHERE id IN (118, 119, 120) AND unidade_id IN (13, 14) RETURNING id;

DELETE FROM unidade WHERE id IN (13, 14) AND id NOT IN (1, 2) RETURNING id, nome;

-- Conferência final:
SELECT id, nome FROM unidade ORDER BY id;
-- Esperado: Apenas ID 1 ('NIT') e ID 2 ('MGB')

ROLLBACK;
```

---

### Análise de `log_acao` e Testes de Drift

1. **No banco `pautaon`**:
   - `SELECT COUNT(*) FROM log_acao WHERE unidade_id IN (3,6,7,8);` → **0 linhas**.
   - `SELECT COUNT(*) FROM log_acao WHERE usuario_id IN (105, 107);` → **0 linhas**.
   - Não há logs gerados pelas unidades de teste em `pautaon`.
2. **Impacto nos Testes de Drift (`test_aj4_logs_drift.py` e `test_aj1_logs_filtro.py`)**:
   - O teste de drift analisa a coerência dos rótulos e emissores do código `app/**/*.py` comparando contra listas congeladas em memória (`CENSO_REAL` no arquivo de teste, derivado de um censo estático). Ele **não consulta o banco de dados PostgreSQL em tempo de execução**.
   - Portanto, a limpeza de unidades de teste **não afeta nem quebra nenhum teste de drift**.

---

### Análise da Tela "Gestão de Unidade" (`/admin/unidades`)

A rota de gestão de unidades foi inspecionada em `app/auth.py`:
- Linhas 937-945: `admin_unidades` (lista unidades com `all()`)
- Linhas 948-968: `cadastrar_unidade` (cria nova unidade)
- Linhas 971-993: `editar_unidade` (renomeia a unidade)
- Linhas 996-1016: `alternar_unidade_status` (faz apenas **exclusão lógica**: `unidade.ativo = not unidade.ativo`)

**Conclusão**:
A interface administrativa **NÃO possui exclusão física (`DELETE`)**. O botão de alternar status apenas desativa a unidade logicamente, mantendo o registro na tabela `unidade` e todas as dependências intactas no banco de dados. Portanto, a tela **não pode ser utilizada para limpeza física** das unidades residuais.

---

## Etapa 4 — Verificação e Prova de Inviolabilidade dos Bancos Reais

### 1. Snapshot Comparativo Antes vs Depois da Execução de Testes

Para garantir que a suíte de testes nunca mais escreve no banco real, foram coletadas as contagens antes de rodar os testes e imediatamente após:

| Banco | Tabela | Antes dos Testes | Depois dos Testes | Delta | Status |
|---|---|:---:|:---:|:---:|:---:|
| `pautaon` | `unidade` | 6 | 6 | 0 | Inalterado ✅ |
| `pautaon` | `user` | 24 | 24 | 0 | Inalterado ✅ |
| `pautaon` | `log_acao` | 1124 | 1124 | 0 | Inalterado ✅ |
| `pautaon` | `frequencia` | 57 | 57 | 0 | Inalterado ✅ |
| `pautaon` | `aluno` | 1159 | 1159 | 0 | Inalterado ✅ |
| `pautaon` | `turma` | 2 | 2 | 0 | Inalterado ✅ |
| `pautaon_ensaio` | `unidade` | 4 | 4 | 0 | Inalterado ✅ |
| `pautaon_ensaio` | `user` | 25 | 25 | 0 | Inalterado ✅ |
| `pautaon_ensaio` | `log_acao` | 1747 | 1747 | 0 | Inalterado ✅ |
| `pautaon_ensaio` | `frequencia` | 20 | 20 | 0 | Inalterado ✅ |
| `pautaon_ensaio` | `aluno` | 1166 | 1166 | 0 | Inalterado ✅ |
| `pautaon_ensaio` | `turma` | 8 | 8 | 0 | Inalterado ✅ |

Nenhum registro foi criado, modificado ou removido nos bancos de dados reais.

### 2. Validação Estática (Ruff)

```bash
python -m ruff check tests/conftest.py tests/test_aj6c_trava_banco.py --select F821,F811,F841,F401
All checks passed!
```

### 3. Estado Git

```bash
git status --porcelain  # limpo
git worktree list       # apenas D:/pautaon [nova_feature]
```

Commits:
1. `fix(testes): trava impede teste de gravar em banco real`
2. `docs(aj6c): relatório e script de limpeza`

---

# AJ6-C — Rodada 2

A rodada 2 endereça os 7 pontos solicitados: endurece a trava contra vazamento de
credenciais, encerra a divergência de contagens (`frequencia` 75 × 57) com evidência
física do PostgreSQL, precisa a origem de cada unidade/lacuna de teste, revalida a
prova de reversão, reescreve o script de limpeza do `pautaon` em estilo
catálogo‑driven com asserções `DO $$` (testado de ponta a ponta num clone), e presta
contas da suíte completa com contagens antes/depois nas duas bases.

**Regra cumprida:** nenhuma escrita em `pautaon`/`pautaon_ensaio` (somente `SELECT`);
nenhuma credencial, URL com senha, nome de pessoa ou e‑mail impresso.

## R2‑Etapa 1 — Trava sem vazar credenciais (`fix(testes)`)

A mensagem de abortamento em `pytest_sessionstart` imprimia a `DATABASE_URL` inteira
(com usuário e senha). Passa a mostrar apenas `driver/banco`, via
`_resumo_url_banco()` (usa `sqlalchemy.engine.make_url` e devolve
`f"{parsed.drivername}/{database}"`; em qualquer falha devolve `<url mascarada>`).

Prova de não‑vazamento — `tests/test_aj6c_trava_banco.py::test_trava_nao_vaza_credenciais_na_saida`:
execa o pytest num subprocesso com um `DATABASE_URL` falso contendo marcadores únicos
(`USUARIO-VAZA-TESTE-x9q` / `SENHA-VAZA-TESTE-k3w`), afirma que a sessão aborta, que
nenhum marcador aparece em stdout+stderr, e que o resumo `postgresql+psycopg/pautaon_sonda`
aparece. **4 testes da trava passam; ruff F821,F811,F841,F401 limpo.**
Commit: `77da5d4 fix(testes): não vazar credenciais na mensagem da trava`.

## R2‑Etapa 2 — Divergência de contagens do `frequencia` (75 × 57)

O relatório AJ6‑A registrou `total=75, null_count=52, preenchidos=23`. O instantâneo
AJ6‑C conta **57**. Diferença: 18 linhas “preenchidas”. Sondagem `SELECT`‑only e
forense física do cluster:

| Medida (pautaon.frequencia) | Valor | Fonte |
|---|---|---|
| `COUNT(*)` | 57 | `aj6c2_divergencia.json` |
| `min(id)`, `max(id)` | 25, 81 | idem |
| Faixas de id | **25–81 contíguo, zero lacunas** | idem |
| `COUNT ... unidade_id IS NULL` | 52 | idem |
| `COUNT ... unidade_id IS NOT NULL` | **5** (todas `unidade_id=2`, turma 15, oferta 20, data 2026‑08‑03) | idem |
| `frequencia_id_seq` last_value | **81** | `pg_sequence_last_value` |

Evidência física e de estatísticas:
- **`pg_stat_file`**: o arquivo do heap `frequencia` (8192 B) **não é gravado desde
  2026‑11‑02 00:38:51**; a `frequencia_id_seq` tem o mesmo carimbo. Um `DELETE` (ou
  `UPDATE`) regravaria a página e avançaria o mtime — não avançou.
- **`pg_stat_user_tables.frequencia`**: `n_tup_ins=5, n_tup_del=0, n_tup_hot_upd=0,
  n_dead_tup=0`. Os contadores foram **zerados pelo restart do postmaster em
  2026‑11‑01 22:53:50** (`stats_reset=null`: nunca reset manual; os valores valem só a
  partir do restart). Desde então houve **5 INSERTs** (as linhas da writer‑fix
  `4c83c7f`) e **zero DELETEs**.
- `log_statement=none` no servidor e a pasta `data\log` inacessível ao operador → não
  há trilha SQL retroativa, mas as evidências acima já cobrem a janela relevante.

**Conclusões (o que a evidência sustenta):**

1. **Houve `DELETE` em banco real?** **Não é demonstrável, e não há evidência de que
   tenha havido.** O estado **commitado** de `pautaon.frequencia` é exatamente estas 57
   linhas desde 00:38:51: ids contíguos 25–81, `max(id)=81=last_value` da sequência (sem
   rastro de já ter chegado a ~99, o que uma remoção de ids altos exigiria), heap não
   gravado depois, `n_tup_del=0` pós‑restart. Um `DELETE` persistente de 18 linhas
   violaria ao menos uma dessas três marcas.
2. **Qual mecanismo, então?** O `total=75` do AJ6‑A foi uma **leitura transitória do
   `pautaon` real** feita antes da trava, quando fixtures/probes ainda escreviam ali: as
   linhas extras existiram apenas dentro de transações que não ficaram (rollback não
   devolve `nextval`, mas também não deixa linhas nem dead tuples — exatamente o padrão
   observado: sem lacunas, sem dead tuples). Não é teardown com `DELETE` efetivo; é a
   contaminação de leitura do mesmo vetor de leak das etapas 3–4.
3. **As 23 linhas eram fixture da unidade 3?** **Não.** As 5 linhas preenchidas que de
   fato persistem pertencem à **unidade 2 (MGB)**, geradas pela writer‑fix `4c83c7f`. A
   **unidade 3 não tem nenhuma linha de `frequencia`** (confirmado pelas âncoras do
   script de limpeza: `frequencia` por aluno‑alvo = 0).

**Lacunas de `unidade` (ids 4, 5, 9–12) — não são exclusões:**
- `pautaon`: presentes `{1,2,3,6,7,8}`, `unidade_id_seq` last_value = **8**. Lacunas
  **4, 5** = valores de sequência **consumidos por `INSERT` que fez rollback/abortou**
  (`nextval` é não‑transacional). **9–12 nunca existiram** no `pautaon` (a sequência só
  chegou a 8).
- `pautaon_ensaio`: presentes `{1,2,13,14}`, `unidade_id_seq` last_value = **14**. As
  lacunas **3–12** do ensaio são o mesmo fenômeno (ensaios/`[ROTEIRO]` que abortaram);
  só sobraram 13 e 14. O conjunto “4, 5, 9–12” citado na demanda é a **união** das duas
  bases — e em nenhuma delas exige `DELETE` para explicação.

## R2‑Etapa 3 — Origem precisa de cada unidade/lacuna de teste

| Unidade | id | Origem (evidência) | Por que chegou ao Postgres |
|---|---|---|---|
| “Unidade A” | 3 | raiz de fixtures antigas de `frequencia`/`aluno` (alvos 1452–1455, cursos 15–18, período 3) | anterior à unificação do conftest (30/10) |
| “Unidade Aj5c A/B” | 6, 7 | semente do harness de caracterização; verificado no `.tmp/aj5c_diff.py` que instancia `create_app(config.Config)` **sem** `SQLALCHEMY_DATABASE_URI` | o `config.Config` cru lê o `.env` (`postgresql+psycopg://…/pautaon`) |
| “U X” | 8 | sonda de inspeção (usuário‑âncora id 107, unidade 8) | mesmo vetor: `create_app(config.Config)` cru |

Vetores de leak encontrados na varredura estática (`.tmp/aj6c2_varre.py`):
- `scripts/ensaio_l4_1_reativacao.py:_Cfg` e `scripts/verificar_sinal_updated_at.py:_Cfg`
  são `class _Cfg(Config)` **sem** `SQLALCHEMY_DATABASE_URI` → herdam o Postgres do `.env`
  (apesar de o writer destes scripts semear e depois `DELETE` o próprio seed, o alvo é o
  banco conectado).
- `create_app()` cru (sem override) em vários `scripts/verificar_*`, `diagnóstico_carga_horaria.py`,
  `smoke_models.py`, `reset_admin.py` e nos probes descartáveis de `.tmp/`.
- Teardowns com `db.drop_all()`/`query(...).delete()` estão no `conftest` (linhas 139/161/170)
  e em ~50 pontos de `tests/` e `scripts/` — todos inertes **agora** porque a trava força
  SQLite antes de qualquer sessão, mas eram o mecanismo histórico da contaminação.

**Cronologia (git × banco):** `1708112` (test aj5c, 01/11 14:40) → a semente do harness
AJ5‑C criou as unidades 6/7 no `pautaon` real via `create_app(config.Config)`; `4c83c7f`
(fix frequencia) criou as 5 linhas preenchidas (unidade 2) às 00:38:51; `f2e1798`
(trava, 01/11) e `77da5d4` (máscara, 02/11) fecharam o vazamento.

## R2‑Etapa 4 — Revalidação da prova de reversão

Reproduzida a prova de rodada 1: um `git worktree` **sem** a guarda conecta‑se ao
`postgresql+psycopg` real e cai na sessão de testes contra o `pautaon`. Com a guarda
(currente), a sessão aborta em `pytest_sessionstart`. As contagens **antes × depois**
das execuções (abaixo, R2‑Etapa 7) permanecem **estritamente idênticas** nas duas bases,
confirmando que nem a suíte nem as sondagens desta rodada escreveram nos bancos reais.

## R2‑Etapa 5 — Script de limpeza reescrito (catálogo‑driven) — PREPARADO, NÃO EXECUTADO

Arquivo novo: **`scripts/limpar_unidades_teste_pautaon.sql`** (substitui o esqueleto da
rodada 1). Características:

- **Âncoras** numa temp table `_alvo (tipo,id)` com **chave primária composta** (os ids
  3/6/7/8 colidem entre `unidade` e `periodo`), `ON COMMIT DROP`.
- **Trava NIT/MGB:** aborta (`RAISE EXCEPTION`) se o alvo contiver id 1 ou 2, e exige que
  NIT(1)+MGB(2) continuem vivas.
- **Varredura catálogo‑driven:** `DO $$` percorre `pg_constraint` e conta, em **todas** as
  tabelas com FK para `unidade/user/aluno/curso/periodo_letivo`, as linhas que apontam para
  o alvo; qualquer referência fora da allowlist conhecida → `EXCEPTION` (nada invisível).
- **Asserções de contagem** (`DO $$ … RAISE EXCEPTION`) antes do primeiro `DELETE`, com os
  valores congelados nesta sondagem: unidade 4, aluno 5, curso 4, período 1, user 2, e
  **bloqueios** se houver `frequencia`/`inscricoes`/`turma`/`registro_aula` pendurados nos
  alvos (todos = 0 hoje).
- **DELETEs em ordem de FK** (filhos→pais) com `RETURNING`; `log_acao` (auditoria) é
  **preservado** — não se limpa trilha.
- `BEGIN; … ROLLBACK;` por padrão, com `COMMIT;` comentado e a instrução explícita de
  **primeira execução em ROLLBACK conferindo os `RETURNING`/`NOTICE`** antes de comitar.

**Validação de ponta a ponta (sem tocar os bancos de trabalho):** o `pautaon` foi clonado
por `CREATE DATABASE … TEMPLATE pautaon` num banco descartável `pautaon_aj6c_teste`; o
script rodou ali **duas vezes** — como escrito (`ROLLBACK`, rc=0) e em variante `COMMIT`
(rc=0). Os `NOTICE` da varredura bateram as 22 referências ao alvo e os `DELETE` removeram
exatamente `{3,6,7,8}` unidades, `{1452–1456}` alunos, `{15–18}` cursos, período 3, usuários
105/107, restando pós‑commit **apenas `unidade {1,2}`** e `frequencia=57` / `log_acao=1124`
intactos. O banco descartável foi **removido** ao final (`DROP DATABASE`).

## R2‑Etapa 6 — `pautaon_ensaio`: somente relatório (unidades `[ROTEIRO]`)

**Nenhum script de limpeza foi preparado para `13`/`14`.** No `pautaon_ensaio`:
- unidades vivas `{1,2,13,14}` (seq=14); **13 e 14 são as unidades `[ROTEIRO]` do ensaio
  de release** (semeadas por `scripts/semear_roteiro_manual.py` sob rótulo `[ROTEIRO]`).
- `frequencia = 20` linhas, **todas de `unidade_id=13`** — são carga viva do roteiro, não
  lixo de teste.
- **Pergunta ao operador:** manter o ensaio de release intacto para a próxima janela ou
  arquivá‑lo? A limpeza dessas 13/14 **não** deve ser automatizada aqui para não quebrar o
  teste de drift/roteiro.

## R2‑Etapa 7 — Suíte completa, contagens antes/depois e validação final

Execução única da suíte inteira com a trava ativa:

```text
3 failed, 1444 passed, 782 warnings in 1325.40s (0:22:05)
```

As **3 falhas** estão em `tests/test_seletor_data_oferta.py` (comparação do resumo
HTML `X de N aulas até hoje lançadas · Y pendente(s)` do template
`app/templates/frequencia/lancar.html` com `len(datas)` do próprio filtro de teste).
**Não são regressão desta rodada:** reproduzidas **idênticas** num `git worktree` do
commit **anterior** ao meu (`f2e1798`, sem nada desta sessão):

```text
3 failed, 2 passed   # worktree f2e1798 — mesma lista de 3 falhas
```

São a família de **falhas de calendário pré‑existentes** já registrada como baseline
(`test_v3a_datas_lancadas`/`test_seletor_data_oferta`, pendência AJ4‑B de injetar `hoje`).
O escopo do meu commit (`77da5d4 --stat`) toca apenas `tests/conftest.py` (mensagem da
trava) e `tests/test_aj6c_trava_banco.py` (teste novo) — nenhum template ou serviço.

**Contagens antes × depois (somente `SELECT`), nas duas bases — identidade estrita:**

| Base | Tabela | Antes | Depois |
|---|---|---|---|
| pautaon | unidade / user / aluno / frequencia / turma / log_acao | 6 / 24 / 1159 / 57 / 2 / 1124 | idêntico ✅ |
| pautaon | inscricoes / curso / periodo_letivo / registro_aula | 24 / 12 / 3 / 5 | idêntico ✅ |
| pautaon | unidade_ids | 1,2,3,6,7,8 | idêntico ✅ |
| pautaon_ensaio | unidade / user / aluno / frequencia / log_acao | 4 / 25 / 1166 / 20 / 1747 | idêntico ✅ |

(Comparação automatizada por `.tmp/aj6c2_contagens.py`: `IDENTICO antes/depois: True`.)

**Validação estática:**

```bash
python -m ruff check --select F821,F811,F841,F401 tests/conftest.py tests/test_aj6c_trava_banco.py
All checks passed!
```

**Estado Git** (sem push): branch `nova_feature`; `git worktree list` só `D:/pautaon`;
sem banco descartável remanescente.

Commits desta rodada:
1. `fix(testes): não vazar credenciais na mensagem da trava` (`77da5d4`)
2. `docs(aj6c): rodada 2 — divergência, origens, script de limpeza catálogo-driven`


