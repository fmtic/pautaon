# MER — Modelo Entidade-Relacionamento

> Documento vivo do esquema do banco de dados. **Atualize sempre que criar,
> alterar ou remover uma tabela/coluna.** Cada alteração deve vir acompanhada
> da migration correspondente.

**Última atualização:** 2026-10-21 — Sincronizado com `app/models/` (19 arquivos) e `migrations/versions/` (18 revisões): cadeia de migrations (§11) corrigida e ressalvas registradas (§11.1) — dois heads, `47ae52f8da90` inexistente, `tipo_deficiencia` sem migration ativa, `documentos_entregues` como JSON; mixins `SoftDeleteMixin`/`TenantMixin`/`AuditoriaMixin`; `curso.carga_horaria` removida (`d1e2f3a4b5c6`); `periodo_letivo.unidade_id` nullable (TenantMixin); enumerações (§7.31).

---

## Sumário

 1. [Visão geral](#1-vis%C3%A3o-geral)
 2. [Estrutura do pacote de modelos](#2-estrutura-do-pacote-de-modelos)
 3. [Glossário](#3-gloss%C3%A1rio)
 4. [Multitenancy](#4-multitenancy)
 5. [Mapa de domínios](#5-mapa-de-dom%C3%ADnios)
 6. [Diagramas ER por domínio](#6-diagramas-er-por-dom%C3%ADnio)
 7. [Dicionário de dados](#7-dicion%C3%A1rio-de-dados)
 8. [Regras de negócio transversais](#8-regras-de-neg%C3%B3cio-transversais)
 9. [Convenções de código](#9-conven%C3%A7%C3%B5es-de-c%C3%B3digo)
10. [Histórico de ondas](#10-hist%C3%B3rico-de-ondas)
11. [Referência cruzada com migrations](#11-refer%C3%AAncia-cruzada-com-migrations)
12. [Dívida técnica e roadmap](#12-d%C3%ADvida-t%C3%A9cnica-e-roadmap)

---

## 1. Visão geral

O sistema é um **ERP socioeducativo** multitenant, organizado em torno de
**unidades** (tenants). Cada unidade possui:

- Usuários próprios (professores, pedagogia, secretaria).
- Catálogo próprio de cursos, níveis e turmas.
- Períodos letivos, calendário e conselhos de classe.
- Alunos, seus perfis estruturados (socioeconômico, diversidade, endereço, responsáveis) e atendimentos.

**Banco:** PostgreSQL (produção) / SQLite (testes locais).
**ORM:** SQLAlchemy via Flask-SQLAlchemy.
**Migrations:** Alembic via Flask-Migrate.
**Fonte de verdade do código:** `app/models/` (pacote).
**Fonte de verdade do esquema:** este documento.

### Ajustes de arquitetura ativos

- `SoftDeleteMixin` (coluna `ativo`) e `TenantMixin` (coluna `unidade_id`, FK → `unidade.id`, **nullable por padrão**) ficam em `app/models/base.py`. O `AuditoriaMixin` (colunas `updated_by_id`, `updated_by_name` e `updated_at`) fica em `app/models/auditoria_mixin.py`.
- Os atributos herdados dos mixins são compartilhados e **não** precisam ser repetidos em cada classe. Uso atual:

| Mixin             | Modelos que o herdam                                                                                                                                             |
|-------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `SoftDeleteMixin` | `PeriodoLetivo`, `Turma`, `TemaAula`, `Inscricao`, `PerguntaConselho`, `OpcaoProximaTurma`                                                                       |
| `TenantMixin`     | `PeriodoLetivo`, `Turma`, `TemaAula`, `Transferencia` (redeclara `unidade_id` como NOT NULL), `Frequencia`, `RegistroAula`, `ConselhoClasse`, `ConselhoResposta` |
| `AuditoriaMixin`  | `Turma`, `TemaAula`, `Inscricao`, `RegistroAula`, `ConselhoClasse`                                                                                               |

- `Aluno` **não** usa mixins: declara manualmente `ativo`, `unidade_id` e as colunas de auditoria de criação e edição (Onda 3B-ter).
- A auditoria automática é registrada ao iniciar a app em `app/__init__.py`, importando `app.models.auditoria_listener` dentro de `_register_auditoria_listener`.
- `Turma.professor` usa `foreign_keys=[professor_id]` para evitar colisão com `updated_by_id` herdado de `AuditoriaMixin`; `RegistroAula.instrutor` também declara `foreign_keys` pelo mesmo motivo.

---

## 2. Estrutura do pacote de modelos

```text
app/models/
├── __init__.py            # Reexporta os modelos (compatibilidade). NÃO reexporta
│                          # enums nem mixins
├── base.py                # Imports, JSONType e mixins SoftDeleteMixin/TenantMixin
│                          # (não define modelos)
├── enums.py               # Enumerações + conjuntos derivados
├── auditoria_mixin.py     # AuditoriaMixin (updated_by_id, updated_by_name, updated_at)
├── auditoria_listener.py  # Listener before_flush: preenche auditoria + grava LogAcao
├── organizacao.py         # Unidade, ConfiguracaoSistema
├── usuarios.py            # User
├── pedagogico.py          # Curso, Nivel
├── academico.py           # PeriodoLetivo, Turma, TemaAula
├── pessoas.py             # Aluno, SituacaoEscolar
├── perfis.py              # EnderecoAluno, ResponsavelAluno,
│                          # PerfilSocioeconomico, PerfilDiversidade
├── matriculas.py          # Inscricao, Transferencia
├── calendario.py          # DiaBloqueado, DiaBloqueadoTurma
├── aulas.py               # Frequencia, RegistroAula
├── conselho.py            # PeriodoConselho, PerguntaConselho,
│                          # OpcaoProximaTurma, ConselhoClasse, ConselhoResposta
├── atendimento.py         # Atendimento
├── servico_social.py      # AgendaServicoSocial, RespostaFormulario
├── auditoria.py           # LogAcao
└── legado.py              # Registro
```

### Camada de serviços relacionada

```text
app/services/
├── aluno_perfil.py        # Centraliza leitura/escrita dos perfis do Aluno
│                          # (Onda 3B). Todo acesso a endereço/responsável/
│                          # socioeconômico/diversidade passa por aqui.
├── auth_service.py
├── bootstrap.py
└── calendar_service.py
```

### Regras de importação

1. Código **fora** do pacote importa os **modelos** sempre de `app.models`. Enums e mixins **não** são reexportados por `__init__.py`: importar de `app.models.enums`, `app.models.base` e `app.models.auditoria_mixin`.
2. Código **dentro** do pacote importa pelo caminho completo (ex.: `from app.models.pessoas import Aluno`).
3. Dentro de **métodos**, usar import local para evitar ciclos.
4. Ao ler/escrever dados de perfil do aluno, usar **sempre** `app.services.aluno_perfil` — nunca acessar `aluno.*_json` direto.
5. Novos modelamentos de tenant/soft-delete devem preferir herdar de `TenantMixin` e `SoftDeleteMixin` em vez de redeclarar campos duplicados; entidades editadas por usuários devem herdar também `AuditoriaMixin`.

### Auditoria automática

A auditoria é composta por duas peças:

1. **`AuditoriaMixin`** (`app/models/auditoria_mixin.py`) — adiciona `updated_by_id` (FK → `user.id`, `ON DELETE SET NULL`), `updated_by_name` (snapshot, `varchar(100)`) e `updated_at` (`default` e `onupdate` = `get_local_now`), além do relacionamento `updated_by` (→ `User`, `lazy='joined'`). FK e relationship são declarados via `@declared_attr` (exigência do SQLAlchemy 2.x).
2. **Listener `before_flush`** (`app/models/auditoria_listener.py`) — registrado em `db.session` quando o módulo é importado (feito no bootstrap da app, ver §1).

Comportamento do listener (conforme o código):

- Considera os objetos de `session.new` + `session.dirty` que possuam o atributo `updated_by_id`. A detecção é por `hasattr`, **não** por herança do mixin — portanto `Aluno` também é coberto.
- Preenche `updated_by_id` e `updated_by_name` com o `current_user` (ou `NULL` se não autenticado) e `updated_at = db.func.now()`.
- Cria um `LogAcao` por objeto: `acao` = `Criar <Classe>` (objeto novo) ou `Alterar <Classe>`; `detalhes` = `repr(obj)`; `ip` = `request.remote_addr` (apenas em contexto de request); `usuario_id`, `usuario_nome` e `unidade_id` vêm do `current_user`.
- **Não trata DELETE** (`session.deleted`): exclusões físicas, inclusive cascatas `delete-orphan`, não geram `LogAcao`; a premissa é o soft delete via `ativo=False`.
- Pontos de atenção em §12.11.

---

## 3. Glossário

| Termo                    | Significado                                                                                                                                                 |
|--------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Unidade**              | Tenant do sistema. Fronteira de isolamento de dados.                                                                                                        |
| **Turma**                | Agrupamento operacional de alunos em um curso/período.                                                                                                      |
| **Inscrição**            | Vínculo N:N entre Aluno e Turma, com histórico.                                                                                                             |
| **Conceito**             | Código de presença/falta: A/B/C/D (presente), F (falta), J (justificada).                                                                                   |
| **Conselho de Classe**   | Reunião colegiada que avalia aluno/turma por etapa.                                                                                                         |
| **Etapa**                | Momento do conselho: INICIAL, PERCURSO, FINAL.                                                                                                              |
| **Tema de Aula**         | Tópico macro do planejamento pedagógico.                                                                                                                    |
| **Dia bloqueado**        | Data sem aula em um período letivo (feriado, etc.).                                                                                                         |
| **Perfil do aluno**      | Dados complementares (endereço, responsável, socioeconômico, diversidade) em tabelas 1:1 ou 1:N com `Aluno`.                                                |
| **Documentos entregues** | Flags JSONB em `Aluno.documentos_entregues` indicando quais documentos foram anexados.                                                                      |
| **C.H. (carga horária)** | Calculada em `Turma`, em minutos: `carga_horaria_aula` = `hora_fim − hora_inicio`; `carga_horaria_total` = aula × `dias_aula_efetivos()`. Não é persistida. |
| **Mixin de auditoria**   | `AuditoriaMixin`: colunas `updated_by_id`, `updated_by_name` e `updated_at`, preenchidas pelo listener `before_flush`.                                      |

---

## 4. Multitenancy

A coluna `unidade_id` aparece em quase todas as tabelas de negócio.

Regras:

1. **Toda consulta de listagem deve filtrar por** `unidade_id` do usuário logado, exceto para o perfil `admin` global.
2. `Unidade` **não** é apagada se houver registros dependentes (integridade).
3. `User.email` é único **globalmente** (não por unidade).
4. `ConfiguracaoSistema.unidade_id = NULL` significa configuração **global**.
5. `Nivel.nome` é único **por unidade** (`uq_nivel_nome_unidade`: `nome` + `unidade_id`).
6. As tabelas de perfil do aluno (`endereco_aluno`, `responsavel_aluno`, `perfil_socioeconomico`, `perfil_diversidade`) herdam `unidade_id` do aluno no momento da criação.
7. `TenantMixin.unidade_id` é **nullable** por padrão (compatibilidade com registros globais/legados). Tabelas que o tornam NOT NULL: `curso`, `transferencia`, `dia_bloqueado` e `periodo_conselho`.
8. Tabelas **sem** `unidade_id`: `inscricoes`, `conselho_pergunta`, `opcao_proxima_turma`, `agenda_servico_social` e `respostas_formulario`. Quando necessário, o escopo é derivado por join (ex.: `inscricoes.turma_id → turma.unidade_id`).

---

## 5. Mapa de domínios

| Módulo               | Domínio                    | Entidades                                                                                        |
|----------------------|----------------------------|--------------------------------------------------------------------------------------------------|
| `organizacao`        | Estrutura Organizacional   | `Unidade`, `ConfiguracaoSistema`                                                                 |
| `base`               | Mixins de modelo           | `SoftDeleteMixin`, `TenantMixin`                                                                 |
| `usuarios`           | Usuários e Autenticação    | `User`                                                                                           |
| `pedagogico`         | Cadastros Pedagógicos      | `Curso`, `Nivel`                                                                                 |
| `academico`          | Estrutura Acadêmica        | `PeriodoLetivo`, `Turma`, `TemaAula`                                                             |
| `pessoas`            | Pessoas                    | `Aluno`, `SituacaoEscolar`                                                                       |
| `perfis`             | Perfis do Aluno            | `EnderecoAluno`, `ResponsavelAluno`, `PerfilSocioeconomico`, `PerfilDiversidade`                 |
| `matriculas`         | Matrículas e Movimentações | `Inscricao`, `Transferencia`                                                                     |
| `calendario`         | Calendário Acadêmico       | `DiaBloqueado`, `DiaBloqueadoTurma`                                                              |
| `aulas`              | Frequência e Aulas         | `Frequencia`, `RegistroAula`                                                                     |
| `conselho`           | Conselho de Classe         | `PeriodoConselho`, `PerguntaConselho`, `OpcaoProximaTurma`, `ConselhoClasse`, `ConselhoResposta` |
| `atendimento`        | Atendimento                | `Atendimento`                                                                                    |
| `servico_social`     | Serviço Social             | `AgendaServicoSocial`, `RespostaFormulario`                                                      |
| `auditoria`          | Auditoria                  | `LogAcao`                                                                                        |
| `auditoria_mixin`    | Mixin de Auditoria         | `AuditoriaMixin`                                                                                 |
| `auditoria_listener` | Listener de Auditoria      | — (evento `before_flush`)                                                                        |
| `legado`             | Legado                     | `Registro`                                                                                       |

---

## 6. Diagramas ER por domínio

### 6.1 Núcleo organizacional e usuários

```mermaid
erDiagram
    UNIDADE ||--o{ USER : possui
    UNIDADE ||--o{ CONFIGURACAO_SISTEMA : parametriza
    UNIDADE ||--o{ CURSO : catalogo
    UNIDADE |o--o{ NIVEL : catalogo
    UNIDADE ||--o{ PERIODO_LETIVO : organiza
    UNIDADE ||--o{ TURMA : agrupa
    UNIDADE ||--o{ ALUNO : matricula
```

### 6.2 Estrutura acadêmica

```mermaid
erDiagram
    PERIODO_LETIVO ||--o{ TURMA : contem
    CURSO          ||--o{ TURMA : oferta
    CURSO          ||--o{ TEMA_AULA : planeja
    USER           ||--o{ TURMA : leciona
    TURMA          ||--o{ REGISTRO_AULA : registra
    TEMA_AULA      ||--o{ REGISTRO_AULA : tema
```

### 6.3 Alunos, matrículas e frequência

```mermaid
erDiagram
    ALUNO ||--o| SITUACAO_ESCOLAR : detalha
    ALUNO ||--o{ INSCRICAO : possui
    TURMA ||--o{ INSCRICAO : recebe
    ALUNO ||--o{ FREQUENCIA : registra
    TURMA ||--o{ FREQUENCIA : pauta
    ALUNO ||--o{ TRANSFERENCIA : movimenta
```

### 6.4 Perfil do aluno (Onda 3A/3B)

```mermaid
erDiagram
    ALUNO ||--o| ENDERECO_ALUNO : "1:1"
    ALUNO ||--o{ RESPONSAVEL_ALUNO : "1:N"
    ALUNO ||--o| PERFIL_SOCIOECONOMICO : "1:1"
    ALUNO ||--o| PERFIL_DIVERSIDADE : "1:1"
    ALUNO ||--o{ ATENDIMENTO : recebe
```

### 6.5 Conselho de classe

```mermaid
erDiagram
    PERIODO_LETIVO ||--o{ PERIODO_CONSELHO : agenda
    PERIODO_CONSELHO ||--o{ CONSELHO_CLASSE : contem
    TURMA ||--o{ CONSELHO_CLASSE : avalia
    ALUNO ||--o{ CONSELHO_CLASSE : avaliado
    CONSELHO_CLASSE ||--o{ CONSELHO_RESPOSTA : possui
    PERGUNTA_CONSELHO ||--o{ CONSELHO_RESPOSTA : responde
    OPCAO_PROXIMA_TURMA ||--o{ CONSELHO_CLASSE : destino
```

### 6.6 Serviço social, atendimento e auditoria

```mermaid
erDiagram
    ALUNO ||--o{ ATENDIMENTO : recebe
    ALUNO ||--o{ RESPOSTA_FORMULARIO : responde
    USER  ||--o{ AGENDA_SERVICO_SOCIAL : cria
    USER  ||--o{ LOG_ACAO : gera
```

### 6.7 Auditoria de edição (`updated_by`)

```mermaid
erDiagram
    USER |o--o{ TURMA : "updated_by"
    USER |o--o{ TEMA_AULA : "updated_by"
    USER |o--o{ INSCRICAO : "updated_by"
    USER |o--o{ REGISTRO_AULA : "updated_by"
    USER |o--o{ CONSELHO_CLASSE : "updated_by"
    USER |o--o{ ALUNO : "created_by / updated_by"
```

As cinco primeiras relações vêm do `AuditoriaMixin` (`ON DELETE SET NULL`, conforme `a9f3c8e2d1b7`). `Aluno` declara `created_by_id` e `updated_by_id` manualmente: no modelo as FKs não têm `ondelete`, mas a migration `f1a2b3c4d5e6` cria `fk_aluno_updated_by_id` com `ON DELETE SET NULL` (somente PostgreSQL).

---

## 7. Dicionário de dados

> Tipos lógicos. `NOT NULL` indicado explicitamente. Defaults descritos
> quando relevantes.
>
> Tabelas que usam mixins trazem a linha **Mixins** logo abaixo do título (`SoftDeleteMixin` → `ativo`; `TenantMixin` → `unidade_id`; `AuditoriaMixin` → `updated_by_id`, `updated_by_name`, `updated_at`).

### 7.1 `unidade`

| Coluna | Tipo         | Nulo | Default | Descrição       |
|--------|--------------|------|---------|-----------------|
| id     | int          | não  | auto    | PK              |
| nome   | varchar(100) | não  | —       | Nome da unidade |
| ativo  | bool         | não  | true    | Soft delete     |

### 7.2 `configuracao_sistema`

| Coluna     | Tipo         | Nulo | Default | Descrição                |
|------------|--------------|------|---------|--------------------------|
| id         | int          | não  | auto    | PK                       |
| chave      | varchar(50)  | não  | —       | Chave (única por escopo) |
| valor      | varchar(100) | sim  | —       | Valor serializado        |
| descricao  | varchar(255) | sim  | —       | Texto explicativo        |
| unidade_id | int          | sim  | —       | NULL = global            |

**Índices únicos parciais:** `ix_config_chave_global` (`chave WHERE unidade_id IS NULL`), `ix_config_chave_unidade` (`chave, unidade_id WHERE unidade_id IS NOT NULL`).

### 7.3 `user`

| Coluna       | Tipo         | Nulo | Default | Descrição                    |
|--------------|--------------|------|---------|------------------------------|
| id           | int          | não  | auto    | PK                           |
| name         | varchar(100) | não  | —       | Nome completo                |
| email        | varchar(120) | não  | —       | **UNIQUE** global            |
| password     | varchar(200) | sim  | —       | Hash Werkzeug; NULL para AD  |
| role         | varchar(20)  | não  | —       | Valor canônico em `UserRole` |
| is_active    | bool         | não  | true    | Conta ativa                  |
| is_ad_user   | bool         | não  | false   | Autenticação por domínio     |
| unidade_id   | int          | sim  | —       | FK → unidade                 |
| first_login  | bool         | sim  | true    | Força troca de senha         |
| google_id    | varchar(100) | sim  | —       | **UNIQUE**, indexado         |
| google_email | varchar(120) | sim  | —       | E-mail Google                |

**CHECK:** `ck_user_role` — restringe `role` aos valores de `UserRole`.

### 7.4 `curso`

| Coluna     | Tipo         | Nulo | Default | Descrição     |
|------------|--------------|------|---------|---------------|
| id         | int          | não  | auto    | PK            |
| nome       | varchar(150) | não  | —       | Nome do curso |
| descricao  | varchar(300) | sim  | —       | Descrição     |
| ativo      | bool         | não  | true    | Soft delete   |
| unidade_id | int          | não  | —       | FK → unidade  |
| created_at | timestamp    | sim  | now     | Auditoria     |

> **Removido:** `carga_horaria` (migration `d1e2f3a4b5c6`, rotulada "Onda 3C"). A C.H. agora é calculada por turma (§7.7).
>
> **Divergência modelo × banco:** a migration `a9f3c8e2d1b7` também criou `updated_by_id`, `updated_by_name` e `updated_at` em `curso`, mas `Curso` **não** herda `AuditoriaMixin`; essas colunas existem no banco e não estão mapeadas (ver §11.1, item 3).

### 7.5 `nivel`

| Coluna     | Tipo         | Nulo | Default | Descrição         |
|------------|--------------|------|---------|-------------------|
| id         | int          | não  | auto    | PK                |
| nome       | varchar(100) | não  | —       | Único por unidade |
| ativo      | bool         | não  | true    | Soft delete       |
| unidade_id | int          | sim  | —       | FK → unidade      |

**UNIQUE:** (`nome`, `unidade_id`) via `uq_nivel_nome_unidade`. Níveis de unidades diferentes podem ter o mesmo nome; níveis legados sem unidade mantêm `unidade_id = NULL`. No PostgreSQL, `NULL` não colide em UNIQUE; logo a restrição não impede nomes duplicados entre níveis legados sem unidade.

### 7.6 `periodo_letivo`

**Mixins:** `SoftDeleteMixin`, `TenantMixin` (`unidade_id` **nullable**). Sem `AuditoriaMixin`.

| Coluna            | Tipo         | Nulo | Default  | Descrição                     |
|-------------------|--------------|------|----------|-------------------------------|
| id                | int          | não  | auto     | PK                            |
| nome              | varchar(150) | não  | —        | Nome                          |
| data_inicio       | date         | não  | —        | Início                        |
| data_fim          | date         | não  | —        | Fim                           |
| centro_custo      | varchar(150) | sim  | —        | Centro de custo               |
| estimativa_alunos | int          | não  | 0        | Planejamento                  |
| ativo             | bool         | não  | true     | Soft delete (SoftDeleteMixin) |
| unidade_id        | int          | sim  | —        | FK → unidade (TenantMixin)    |
| created_at        | timestamp    | sim  | now      | Auditoria                     |
| updated_at        | timestamp    | sim  | onupdate | Auditoria                     |

**Derivados (não persistidos):** `nome_exibicao` (property: `"<unidade> <nome>"`) e `alunos_enturmados()` (alunos únicos com alguma turma do período via `Aluno.turmas`; **não** filtra `Inscricao.ativo` nem `Aluno.ativo` — para as categorias oficiais de enturmação, ver §8.3).

### 7.7 `turma`

**Mixins:** `SoftDeleteMixin`, `TenantMixin`, `AuditoriaMixin`.

| Coluna              | Tipo             | Nulo | Default      | Descrição                                        |
|---------------------|------------------|------|--------------|--------------------------------------------------|
| id                  | int              | não  | auto         | PK                                               |
| nome                | varchar(100)     | não  | —            | Nome                                             |
| ativo               | bool             | não  | true         | Soft delete                                      |
| **data_inicio**     | **date**         | sim  | —            | Início (Onda 2A)                                 |
| **data_fim**        | **date**         | sim  | —            | Fim (Onda 2A)                                    |
| **hora_inicio**     | **time**         | sim  | —            | Hora (Onda 2A)                                   |
| **hora_fim**        | **time**         | sim  | —            | Hora (Onda 2A)                                   |
| dias_semana         | varchar(20)      | sim  | —            | CSV (ex.: "Segunda,Quarta")                      |
| programa            | varchar(50)      | sim  | —            | Esporte, Profissionalizante…                     |
| turno               | varchar(20)      | sim  | —            | Manhã, Tarde, Noite                              |
| centro_custo        | varchar(150)     | sim  | —            | —                                                |
| ordenacao           | int              | sim  | —            | Ordem de exibição                                |
| unidade_id          | int              | sim  | —            | FK → unidade                                     |
| periodo_letivo_id   | int              | sim  | —            | FK → periodo_letivo                              |
| curso_id            | int              | sim  | —            | FK → curso                                       |
| professor_id        | int              | sim  | —            | FK → user                                        |
| avaliacao_inicial   | text             | sim  | —            | Parecer                                          |
| avaliacao_percurso  | text             | sim  | —            | Parecer                                          |
| avaliacao_final     | text             | sim  | —            | Parecer                                          |
| conselho_concluido  | bool             | não  | false        | Flag de encerramento                             |
| **updated_by_id**   | **int**          | sim  | —            | FK → user, `ON DELETE SET NULL` (AuditoriaMixin) |
| **updated_by_name** | **varchar(100)** | sim  | —            | Snapshot do editor (AuditoriaMixin)              |
| **updated_at**      | **timestamp**    | sim  | now/onupdate | Última modificação (AuditoriaMixin)              |

**Derivados (não persistidos):** `freq_geral` (§8.1); `alunos_ativos_count` (alunos com `Aluno.ativo=True` vinculados via `inscricoes`, sem filtrar `Inscricao.ativo`); `dias_aula_efetivos()` (via `app.utils.logica.calcular_dias_aula_turma`); `carga_horaria_aula` (minutos = `hora_fim − hora_inicio`; `None` se faltar hora ou `hora_fim <= hora_inicio`); `carga_horaria_total` (minutos = `carga_horaria_aula × dias_aula_efetivos()`; `None` se indefinido); `Turma.get_ativas()` (turmas com `ativo=True`, por nome).

### 7.8 `tema_aula`

**Mixins:** `SoftDeleteMixin`, `TenantMixin`, `AuditoriaMixin`.

| Coluna              | Tipo             | Nulo | Default      | Descrição                                        |
|---------------------|------------------|------|--------------|--------------------------------------------------|
| id                  | int              | não  | auto         | PK                                               |
| curso_id            | int              | sim  | —            | FK → curso                                       |
| turma_id            | int              | sim  | —            | LEGADO — FK → turma                              |
| unidade_id          | int              | sim  | —            | FK → unidade                                     |
| titulo              | varchar(200)     | sim  | —            | Título                                           |
| programa            | varchar(50)      | sim  | —            | Programa                                         |
| ativo               | bool             | não  | true         | Soft delete                                      |
| **data**            | **date**         | sim  | —            | Data (Onda 2A)                                   |
| ordem               | int              | não  | 0            | Sequência didática                               |
| **updated_by_id**   | **int**          | sim  | —            | FK → user, `ON DELETE SET NULL` (AuditoriaMixin) |
| **updated_by_name** | **varchar(100)** | sim  | —            | Snapshot do editor (AuditoriaMixin)              |
| **updated_at**      | **timestamp**    | sim  | now/onupdate | Última modificação (AuditoriaMixin)              |

### 7.9 `aluno`

**Mixins:** nenhum. `ativo`, `unidade_id` e a auditoria de criação/edição são declarados manualmente.

| Coluna                    | Tipo             | Nulo | Default | Descrição                                                     |
|---------------------------|------------------|------|---------|---------------------------------------------------------------|
| id                        | int              | não  | auto    | PK                                                            |
| nome                      | varchar(100)     | não  | —       | Nome civil                                                    |
| nome_social               | varchar(100)     | sim  | —       | Nome social (preferir em UI)                                  |
| ativo                     | bool             | não  | true    | Soft delete                                                   |
| data_nascimento           | date             | sim  | —       | —                                                             |
| foto_path                 | varchar(255)     | sim  | —       | Caminho relativo                                              |
| **documentos_entregues**  | **jsonb**        | sim  | —       | Flags de documentos (Onda 3A-bis)                             |
| escolaridade_json         | text             | sim  | —       | **LEGADO** — fallback (Onda 3C)                               |
| identificacao_json        | text             | sim  | —       | **LEGADO** — fallback (Onda 3C)                               |
| socioeconomico_json       | text             | sim  | —       | **LEGADO** — fallback (Onda 3C)                               |
| diversidade_json          | text             | sim  | —       | **LEGADO** — fallback (Onda 3C)                               |
| cpf                       | varchar(20)      | sim  | —       | —                                                             |
| rg                        | varchar(50)      | sim  | —       | —                                                             |
| whatsapp                  | varchar(30)      | sim  | —       | —                                                             |
| email                     | varchar(120)     | sim  | —       | —                                                             |
| nivel                     | varchar(20)      | sim  | —       | Básico / Intermediário / Avançado                             |
| **orgao_rg**              | varchar(20)      | sim  | —       | Onda 3A                                                       |
| **nacionalidade**         | varchar(50)      | sim  | —       | Onda 3A                                                       |
| **natural_uf**            | varchar(2)       | sim  | —       | Onda 3A                                                       |
| **natural_cidade**        | varchar(100)     | sim  | —       | Onda 3A                                                       |
| **nome_mae**              | varchar(150)     | sim  | —       | Onda 3A                                                       |
| **cpf_mae**               | varchar(20)      | sim  | —       | Onda 3A                                                       |
| **nome_pai**              | varchar(150)     | sim  | —       | Onda 3A                                                       |
| **cpf_pai**               | varchar(20)      | sim  | —       | Onda 3A                                                       |
| **vai_acompanhado_aulas** | bool             | não  | false   | Onda 3A                                                       |
| **acompanhante_aulas**    | varchar(150)     | sim  | —       | Onda 3A                                                       |
| created_by_id             | int              | sim  | —       | FK → user                                                     |
| created_by_name           | varchar(100)     | sim  | —       | Snapshot                                                      |
| created_at                | timestamp        | sim  | now     | Auditoria                                                     |
| **updated_by_id**         | **int**          | sim  | —       | FK → user; `SET NULL` na migration, sem `ON DELETE` no modelo |
| **updated_by_name**       | **varchar(100)** | sim  | —       | Snapshot (Onda 3B-ter)                                        |
| **updated_at**            | **timestamp**    | sim  | —       | Preenchido na 1ª edição (Onda 3B-ter)                         |
| unidade_id                | int              | sim  | —       | FK → unidade                                                  |

> **Nota (auditoria automática):** `Aluno` não herda `AuditoriaMixin`, mas possui `updated_by_id`; por isso o listener `before_flush` (§2) também o processa — preenche `updated_*` e grava `LogAcao` inclusive na **inclusão**. A regra "`updated_at` permanece NULL até a 1ª edição" vale apenas sem o listener ativo.

**Formato de** `documentos_entregues`**:**

```json
{"doc_entregue": {"doc_aluno": true, "doc_termo": false, ...}}
```

**Properties derivadas:** `matricula`, `foto`, `idade`, `*_json`, `documentos_dict()`, `documento_entregue(doc_id)`.

### 7.10 `situacao_escolar`

| Coluna                  | Tipo         | Nulo | Default      | Descrição               |
|-------------------------|--------------|------|--------------|-------------------------|
| id                      | int          | não  | auto         | PK                      |
| aluno_id                | int          | não  | —            | **UNIQUE** — FK → aluno |
| unidade_id              | int          | sim  | —            | FK → unidade            |
| escolaridade            | varchar(40)  | sim  | —            | —                       |
| ensino_superior_periodo | int          | sim  | —            | —                       |
| escolaridade_outro      | varchar(150) | sim  | —            | Quando "Outros"         |
| status                  | varchar(20)  | sim  | —            | —                       |
| status_outro            | varchar(150) | sim  | —            | Quando "Outros"         |
| nome_instituicao        | varchar(200) | sim  | —            | Indexado com unidade    |
| tipo_instituicao        | varchar(20)  | sim  | —            | —                       |
| bolsista                | bool         | não  | false        | —                       |
| tipo_instituicao_outro  | varchar(150) | sim  | —            | Quando "Outro"          |
| turno                   | varchar(20)  | sim  | —            | —                       |
| turno_outro             | varchar(100) | sim  | —            | Quando "Outros"         |
| created_at              | timestamp    | não  | now          | Auditoria               |
| updated_at              | timestamp    | não  | now/onupdate | Auditoria               |

**Índice:** `ix_situacao_escolar_unidade_nome` (`unidade_id`, `nome_instituicao`).

### 7.11 `endereco_aluno` (Onda 3A)

| Coluna                 | Tipo         | Nulo | Default      | Descrição               |
|------------------------|--------------|------|--------------|-------------------------|
| id                     | int          | não  | auto         | PK                      |
| aluno_id               | int          | não  | —            | **UNIQUE** — FK → aluno |
| unidade_id             | int          | sim  | —            | FK → unidade            |
| cep                    | varchar(10)  | sim  | —            | —                       |
| rua                    | varchar(200) | sim  | —            | —                       |
| numero                 | varchar(20)  | sim  | —            | —                       |
| bairro                 | varchar(100) | sim  | —            | —                       |
| cidade                 | varchar(100) | sim  | —            | —                       |
| uf                     | varchar(2)   | sim  | —            | —                       |
| zona                   | varchar(20)  | sim  | —            | Urbana / Rural / Outro  |
| possui_acesso_internet | bool         | não  | true         | —                       |
| created_at             | timestamp    | sim  | now          | Auditoria               |
| updated_at             | timestamp    | sim  | now/onupdate | Auditoria               |

### 7.12 `responsavel_aluno` (Onda 3A)

| Coluna     | Tipo         | Nulo | Default      | Descrição               |
|------------|--------------|------|--------------|-------------------------|
| id         | int          | não  | auto         | PK                      |
| aluno_id   | int          | não  | —            | FK → aluno              |
| unidade_id | int          | sim  | —            | FK → unidade            |
| tipo       | varchar(30)  | sim  | —            | Pai / Mãe / Avô/Avó / … |
| nome       | varchar(150) | sim  | —            | —                       |
| cpf        | varchar(20)  | sim  | —            | —                       |
| telefone   | varchar(30)  | sim  | —            | —                       |
| created_at | timestamp    | sim  | now          | Auditoria               |
| updated_at | timestamp    | sim  | now/onupdate | Auditoria               |

**Relação:** 1:N com `Aluno`. O formulário atual coleta 1; o schema aceita N.

### 7.13 `perfil_socioeconomico` (Onda 3A)

| Coluna                  | Tipo          | Nulo | Default      | Descrição                                              |
|-------------------------|---------------|------|--------------|--------------------------------------------------------|
| id                      | int           | não  | auto         | PK                                                     |
| aluno_id                | int           | não  | —            | **UNIQUE** — FK → aluno                                |
| unidade_id              | int           | sim  | —            | FK → unidade                                           |
| renda_familiar          | numeric(12,2) | sim  | —            | Renda familiar mensal em reais                         |
| residente_maior_renda   | varchar(50)   | sim  | —            | Aluno / Pai / Mãe / …                                  |
| pessoas_residencia      | int           | sim  | —            | Nº moradores                                           |
| ocupacao                | varchar(50)   | sim  | —            | Estudante / CLT / …                                    |
| beneficio_social_status | varchar(20)   | sim  | —            | Sim / Não                                              |
| beneficio_social_nome   | text          | sim  | —            | Nomes dos programas, separados internamente por ` \| ` |
| meio_transporte         | varchar(30)   | sim  | —            | Ônibus / Bicicleta / …                                 |
| vulnerabilidade_social  | bool          | não  | false        | —                                                      |
| created_at              | timestamp     | sim  | now          | Auditoria                                              |
| updated_at              | timestamp     | sim  | now/onupdate | Auditoria                                              |

**Notas (Etapa VI, 2026-09-22):**

- `renda_familiar` é valor mensal em reais; a renda per capita é derivada em
  runtime (`renda_per_capita()`) e não é persistida.
- `beneficio_social_nome` só é preenchido quando `beneficio_social_status =
  'Sim'` (vários programas unidos por ` | `).

### 7.14 `perfil_diversidade` (Onda 3A)

| Coluna                     | Tipo         | Nulo | Default      | Descrição                                                                       |
|----------------------------|--------------|------|--------------|---------------------------------------------------------------------------------|
| id                         | int          | não  | auto         | PK                                                                              |
| aluno_id                   | int          | não  | —            | **UNIQUE** — FK → aluno                                                         |
| unidade_id                 | int          | sim  | —            | FK → unidade                                                                    |
| genero                     | varchar(30)  | sim  | —            | —                                                                               |
| raca_cor                   | varchar(30)  | sim  | —            | —                                                                               |
| saude_laudo                | bool         | não  | false        | PCD                                                                             |
| tipo_deficiencia           | varchar(30)  | sim  | —            | Motora/Física, Auditiva, Psicossocial, Intelectual/Mental, Visual, Outro ou TEA |
| saude_medicacao            | varchar(5)   | sim  | —            | Sim / Não                                                                       |
| saude_medicamento_nome     | varchar(150) | sim  | —            | —                                                                               |
| saude_observacoes          | text         | sim  | —            | —                                                                               |
| informacoes_para_professor | text         | sim  | —            | —                                                                               |
| autorizacao_imagem         | bool         | não  | false        | —                                                                               |
| created_at                 | timestamp    | sim  | now          | Auditoria                                                                       |
| updated_at                 | timestamp    | sim  | now/onupdate | Auditoria                                                                       |

**Nota:** `tipo_deficiencia` é restrito ao catálogo `TIPOS_DEFICIENCIA` do
serviço e só é mantido enquanto `saude_laudo = true`.

### 7.15 `inscricoes`

**Mixins:** `SoftDeleteMixin`, `AuditoriaMixin`. Sem `TenantMixin`: a tabela **não possui** `unidade_id`.

| Coluna              | Tipo             | Nulo | Default      | Descrição                                        |
|---------------------|------------------|------|--------------|--------------------------------------------------|
| id                  | int              | não  | auto         | PK                                               |
| aluno_id            | int              | não  | —            | FK → aluno                                       |
| turma_id            | int              | não  | —            | FK → turma                                       |
| nivel               | varchar(30)      | sim  | —            | Nível na turma                                   |
| ativo               | bool             | não  | true         | Vínculo atual                                    |
| data_inicio         | date             | não  | now          | Início                                           |
| data_desativacao    | timestamp        | sim  | —            | Quando desativado                                |
| motivo_desativacao  | varchar(50)      | sim  | —            | Motivo                                           |
| **updated_by_id**   | **int**          | sim  | —            | FK → user, `ON DELETE SET NULL` (AuditoriaMixin) |
| **updated_by_name** | **varchar(100)** | sim  | —            | Snapshot do editor (AuditoriaMixin)              |
| **updated_at**      | **timestamp**    | sim  | now/onupdate | Última modificação (AuditoriaMixin)              |

> Múltiplas linhas com o mesmo (aluno, turma) são permitidas por design —
> histórico de ativação/desativação.

### 7.16 `transferencia`

**Mixins:** `TenantMixin`, com `unidade_id` redeclarado na classe como NOT NULL (sobrescreve o `nullable=True` do mixin).

| Coluna             | Tipo      | Nulo | Default | Descrição    |
|--------------------|-----------|------|---------|--------------|
| id                 | int       | não  | auto    | PK           |
| aluno_id           | int       | não  | —       | FK → aluno   |
| turma_origem_id    | int       | não  | —       | FK → turma   |
| turma_destino_id   | int       | não  | —       | FK → turma   |
| data_transferencia | timestamp | não  | now     | —            |
| observacoes        | text      | sim  | —       | —            |
| unidade_id         | int       | não  | —       | FK → unidade |

### 7.17 `dia_bloqueado`

| Coluna            | Tipo         | Nulo | Default | Descrição                           |
|-------------------|--------------|------|---------|-------------------------------------|
| id                | int          | não  | auto    | PK                                  |
| data              | date         | não  | —       | Dia bloqueado                       |
| **tipo**          | **enum**     | não  | —       | `tipo_dia_bloqueado_enum` (Onda 2B) |
| descricao         | varchar(200) | sim  | —       | —                                   |
| periodo_letivo_id | int          | não  | —       | FK → periodo_letivo                 |
| unidade_id        | int          | não  | —       | FK → unidade                        |
| criado_por_id     | int          | sim  | —       | FK → user                           |
| created_at        | timestamp    | sim  | now     | —                                   |

### 7.18 `dia_bloqueado_turma`

| Coluna        | Tipo      | Nulo | Default | Descrição    |
|---------------|-----------|------|---------|--------------|
| id            | int       | não  | auto    | PK           |
| turma_id      | int       | não  | —       | FK → turma   |
| **data**      | **date**  | não  | —       | Onda 2A      |
| unidade_id    | int       | sim  | —       | FK → unidade |
| criado_por_id | int       | sim  | —       | FK → user    |
| created_at    | timestamp | sim  | now     | —            |

**UNIQUE** (`turma_id`, `data`) via `uix_dia_bloqueado_turma`.

### 7.19 `frequencia`

**Mixins:** `TenantMixin`.

| Coluna       | Tipo     | Nulo | Default | Descrição                            |
|--------------|----------|------|---------|--------------------------------------|
| id           | int      | não  | auto    | PK                                   |
| aluno_id     | int      | não  | —       | FK → aluno                           |
| turma_id     | int      | não  | —       | FK → turma                           |
| **data**     | **date** | não  | —       | Onda 2A                              |
| **conceito** | **enum** | sim  | —       | `conceito_frequencia_enum` (Onda 2B) |
| unidade_id   | int      | sim  | —       | FK → unidade                         |

**UNIQUE** (`aluno_id`, `turma_id`, `data`) via `uix_frequencia_aluno_turma_data`.
**Índices:** `ix_frequencia_turma_data` (`turma_id`, `data`), `ix_frequencia_aluno_data` (`aluno_id`, `data`).
**Property híbrida:** `presente` (A/B/C/D).

### 7.20 `registro_aula`

**Mixins:** `TenantMixin`, `AuditoriaMixin`.

| Coluna              | Tipo             | Nulo | Default      | Descrição                                        |
|---------------------|------------------|------|--------------|--------------------------------------------------|
| id                  | int              | não  | auto         | PK                                               |
| turma_id            | int              | não  | —            | FK → turma                                       |
| **data**            | **date**         | não  | —            | Onda 2A                                          |
| tema_id             | int              | sim  | —            | FK → tema_aula                                   |
| observacoes         | text             | sim  | —            | —                                                |
| instrutor_id        | int              | sim  | —            | FK → user                                        |
| created_at          | timestamp        | sim  | now          | —                                                |
| unidade_id          | int              | sim  | —            | FK → unidade                                     |
| **updated_by_id**   | **int**          | sim  | —            | FK → user, `ON DELETE SET NULL` (AuditoriaMixin) |
| **updated_by_name** | **varchar(100)** | sim  | —            | Snapshot do editor (AuditoriaMixin)              |
| **updated_at**      | **timestamp**    | sim  | now/onupdate | Última modificação (AuditoriaMixin)              |

### 7.21 `periodo_conselho`

| Coluna            | Tipo         | Nulo | Default | Descrição           |
|-------------------|--------------|------|---------|---------------------|
| id                | int          | não  | auto    | PK                  |
| nome              | varchar(100) | não  | —       | —                   |
| data_inicio       | date         | não  | —       | —                   |
| data_fim          | date         | não  | —       | —                   |
| conselho_final    | bool         | não  | false   | Encerramento        |
| periodo_letivo_id | int          | não  | —       | FK → periodo_letivo |
| unidade_id        | int          | não  | —       | FK → unidade        |

### 7.22 `conselho_pergunta`

**Mixins:** `SoftDeleteMixin`. A tabela **não possui** `unidade_id`.

| Coluna    | Tipo     | Nulo | Default | Descrição                       |
|-----------|----------|------|---------|---------------------------------|
| id        | int      | não  | auto    | PK                              |
| **etapa** | **enum** | sim  | —       | `etapa_conselho_enum` (Onda 2B) |
| **tipo**  | **enum** | sim  | ALUNO   | `tipo_pergunta_enum` (Onda 2B)  |
| texto     | text     | não  | —       | —                               |
| opcoes    | text     | sim  | —       | Alternativas serializadas       |
| ativo     | bool     | não  | true    | Soft delete                     |

### 7.23 `opcao_proxima_turma`

**Mixins:** `SoftDeleteMixin`. A tabela **não possui** `unidade_id`.

| Coluna | Tipo         | Nulo | Default | Descrição |
|--------|--------------|------|---------|-----------|
| id     | int          | não  | auto    | PK        |
| nome   | varchar(100) | não  | —       | —         |
| ativo  | bool         | não  | true    | —         |

### 7.24 `conselho_classe`

**Mixins:** `TenantMixin`, `AuditoriaMixin`.

| Coluna              | Tipo             | Nulo | Default      | Descrição                                        |
|---------------------|------------------|------|--------------|--------------------------------------------------|
| id                  | int              | não  | auto         | PK                                               |
| turma_id            | int              | não  | —            | FK → turma                                       |
| aluno_id            | int              | não  | —            | FK → aluno                                       |
| **etapa**           | **enum**         | não  | —            | `etapa_conselho_enum` (Onda 2B)                  |
| data_inicio         | date             | sim  | —            | —                                                |
| data_fim            | date             | sim  | —            | —                                                |
| concluido           | bool             | não  | false        | —                                                |
| instrutor_id        | int              | sim  | —            | FK → user                                        |
| observacao          | text             | sim  | —            | —                                                |
| situacao_final      | varchar(30)      | sim  | —            | Valor canônico em `SituacaoFinal`                |
| proxima_turma_id    | int              | sim  | —            | FK → opcao_proxima_turma                         |
| unidade_id          | int              | sim  | —            | FK → unidade                                     |
| **updated_by_id**   | **int**          | sim  | —            | FK → user, `ON DELETE SET NULL` (AuditoriaMixin) |
| **updated_by_name** | **varchar(100)** | sim  | —            | Snapshot do editor (AuditoriaMixin)              |
| **updated_at**      | **timestamp**    | sim  | now/onupdate | Última modificação (AuditoriaMixin)              |

**UNIQUE** (`turma_id`, `aluno_id`, `etapa`) via `uix_conselho_turma_aluno_etapa`.
**CHECK:** `ck_conselho_situacao_final` — restringe `situacao_final` aos valores de `SituacaoFinal`.

### 7.25 `conselho_resposta`

**Mixins:** `TenantMixin`.

| Coluna      | Tipo | Nulo | Default | Descrição              |
|-------------|------|------|---------|------------------------|
| id          | int  | não  | auto    | PK                     |
| conselho_id | int  | não  | —       | FK → conselho_classe   |
| aluno_id    | int  | não  | —       | FK → aluno             |
| pergunta_id | int  | não  | —       | FK → conselho_pergunta |
| resposta    | text | sim  | —       | —                      |
| observacao  | text | sim  | —       | —                      |
| unidade_id  | int  | sim  | —       | FK → unidade           |

### 7.26 `atendimento`

| Coluna            | Tipo         | Nulo | Default      | Descrição         |
|-------------------|--------------|------|--------------|-------------------|
| id                | int          | não  | auto         | PK                |
| aluno_id          | int          | não  | —            | FK → aluno        |
| setor             | varchar(50)  | não  | pedagogico   | **LEGADO**        |
| data_atendimento  | date         | não  | —            | —                 |
| resumo            | varchar(255) | sim  | —            | —                 |
| dados             | jsonb        | não  | {}           | Conteúdo variável |
| atendido_por_id   | int          | sim  | —            | FK → user         |
| atendido_por_nome | varchar(150) | sim  | —            | Snapshot          |
| unidade_id        | int          | sim  | —            | FK → unidade      |
| created_at        | timestamp    | sim  | now          | —                 |
| updated_at        | timestamp    | sim  | now/onupdate | —                 |

### 7.27 `agenda_servico_social`

| Coluna               | Tipo         | Nulo | Default | Descrição      |
|----------------------|--------------|------|---------|----------------|
| id                   | int          | não  | auto    | PK             |
| titulo               | varchar(200) | não  | —       | —              |
| categoria            | varchar(100) | não  | —       | —              |
| data                 | date         | não  | —       | —              |
| hora                 | varchar(5)   | não  | —       | HH:MM          |
| localizacao          | varchar(255) | sim  | —       | —              |
| descricao            | text         | sim  | —       | —              |
| google_event_id      | varchar(255) | sim  | —       | ID no Google   |
| participantes_emails | text         | sim  | —       | CSV de e-mails |
| user_id              | int          | não  | —       | FK → user      |
| data_criacao         | timestamp    | sim  | now     | —              |

### 7.28 `respostas_formulario`

| Coluna          | Tipo        | Nulo | Default      | Descrição     |
|-----------------|-------------|------|--------------|---------------|
| id              | int         | não  | auto         | PK            |
| tipo_formulario | varchar(50) | não  | —            | Identificador |
| aluno_id        | int         | sim  | —            | FK → aluno    |
| usuario_id      | int         | não  | —            | FK → user     |
| dados           | jsonb       | não  | —            | Respostas     |
| created_at      | timestamp   | sim  | now          | —             |
| updated_at      | timestamp   | sim  | now/onupdate | —             |

### 7.29 `log_acao`

| Coluna       | Tipo         | Nulo | Default | Descrição     |
|--------------|--------------|------|---------|---------------|
| id           | int          | não  | auto    | PK            |
| data_hora    | timestamp    | sim  | now     | —             |
| usuario_id   | int          | sim  | —       | FK → user     |
| usuario_nome | varchar(100) | sim  | —       | Snapshot      |
| acao         | varchar(255) | sim  | —       | Texto da ação |
| detalhes     | text         | sim  | —       | Contexto      |
| ip           | varchar(50)  | sim  | —       | IP de origem  |
| unidade_id   | int          | sim  | —       | FK → unidade  |

### 7.30 `registro` (LEGADO)

| Coluna      | Tipo         | Nulo | Default | Descrição           |
|-------------|--------------|------|---------|---------------------|
| id          | int          | não  | auto    | PK                  |
| educador_id | int          | não  | —       | FK → user           |
| turma       | varchar(100) | sim  | —       | Nome (string livre) |
| mes         | varchar(20)  | sim  | —       | —                   |
| turno       | varchar(20)  | sim  | —       | —                   |
| dados_json  | text         | sim  | —       | JSON cru            |
| criado_em   | timestamp    | sim  | now     | —                   |
| unidade_id  | int          | sim  | —       | FK → unidade        |

### 7.31 Enumerações e constantes (`app/models/enums.py`)

| Enum                 | Persistência                                       | Valores                                                                                    |
|----------------------|----------------------------------------------------|--------------------------------------------------------------------------------------------|
| `ConceitoFrequencia` | ENUM nativo `conceito_frequencia_enum`             | `A`, `B`, `C`, `D` (presença), `F` (falta), `J` (justificada)                              |
| `TipoDiaBloqueado`   | ENUM nativo `tipo_dia_bloqueado_enum`              | `FERIADO`, `ATIVIDADE_PEDAGOGICA`, `REUNIAO_PAIS`, `ATIVIDADE_INTERNA`, `MANUTENCAO`       |
| `EtapaConselho`      | ENUM nativo `etapa_conselho_enum`                  | `INICIAL`, `PERCURSO`, `FINAL`                                                             |
| `TipoPergunta`       | ENUM nativo `tipo_pergunta_enum`                   | `TURMA`, `ALUNO`                                                                           |
| `UserRole`           | `varchar(20)` + CHECK `ck_user_role`               | `admin`, `pedagogico`, `professor`, `secretaria`, `servico_social`, `gerencia`, `pendente` |
| `SituacaoFinal`      | `varchar(30)` + CHECK `ck_conselho_situacao_final` | `Aprovado`, `Reprovado por Falta`, `Desistente`, `Evadido`, `Participação`, `Concluído`    |
| `StatusAluno`        | **não persistido** (derivado, §8.3)                | `NOVO`, `RENOVADO`, `RETORNANTE`, `EM_JANELA`, `NAO_RENOVADO`, `DESENTURMADO`, `OUTROS`    |

**Constantes:** `JANELA_RENOVACAO_DIAS = 14`; `CONCEITOS_PRESENCA` = {A, B, C, D}; `CONCEITOS_CONTABEIS` = presença + F; `ETAPAS_ORDEM` = (INICIAL, PERCURSO, FINAL); `ETAPA_PARA_CAMPO_AVALIACAO` mapeia a etapa para `Turma.avaliacao_inicial` / `avaliacao_percurso` / `avaliacao_final`.

---

## 8. Regras de negócio transversais

### 8.1 Frequência

- Conceitos A/B/C/D = presença.
- F = falta. J = justificada (não entra no denominador).
- Fórmula: `freq = presentes / (presentes + faltas) * 100`.
- Implementação (`Turma.freq_geral`): arredonda a 1 casa decimal e retorna `0.0` quando não há registros contáveis; registros com `conceito` nulo (coluna nullable) não entram na conta.

### 8.2 Conselho de Classe

- Etapas: INICIAL, PERCURSO, FINAL.
- `conselho_final=True` marca o conselho que define situação final.
- `situacao_final` só deve ser preenchida quando `concluido=True`.

### 8.3 Inscrição

- Um aluno pode ter **múltiplas linhas** em `inscricoes` para a mesma turma (histórico de ativação/desativação).
- Sempre considerar `ativo=True` como o vínculo atual.
- O status do aluno por período é **derivado do histórico**, não persistido, e sua regra fica em `app.services.aluno_status`.
- `Aluno.ativo` indica situação cadastral e não determina enturmação. Alunos com `Aluno.ativo=False` ficam fora das categorias de enturmação.
- O período da inscrição é obtido por `Inscricao.turma_id -> Turma.periodo_letivo_id`. P-1 é o período imediatamente anterior da mesma unidade, ordenado por `data_inicio`.
- Para D igual a hoje, `enturmado_em(P, D)` exige inscrição ativa. Para D passado, exige `data_inicio <= D` e `data_desativacao` nula ou posterior a D. A primeira enturmação em P é a menor `Inscricao.data_inicio` do aluno nesse período.
- A janela de renovação termina em `P.data_inicio + 14 dias`, inclusive. O prazo é centralizado em `JANELA_RENOVACAO_DIAS`, em `app.models.enums`.
- Categorias por aluno em P: **Novo** (enturmado em P sem histórico anterior), **Renovado** (teve em P-1 e primeira enturmação em P até o fim da janela), **Retornante** (enturmado em P com histórico anterior, mas não Renovado), **Em janela** e **Não renovado** (teve em P-1, ainda sem enturmação em P, respectivamente dentro ou após a janela), **Desenturmado** (teve inscrição em P, mas não está enturmado em D) e **Outros** (sem enturmação em P ou P-1).
- As categorias são exclusivas; Desenturmado prevalece quando houve inscrição em P sem vínculo vigente em D. Transferências e múltiplas inscrições no mesmo período contam uma vez por aluno.
- Total enturmado em P e D corresponde a Novo + Renovado + Retornante. Aluno não enturmado no período é cadastralmente ativo e não está enturmado em P e D.

### 8.4 Calendário

- `DiaBloqueado` afeta **todas** as turmas do período letivo.
- `DiaBloqueadoTurma` cria **exceção**: a turma tem aula naquele dia.

### 8.5 Aluno

- `matricula` = `{id:05d}.{ano_atual}` — sempre derivada, nunca persistida.
- `idade` = calculada em runtime a partir de `data_nascimento`.
- `nome_social` deve prevalecer sobre `nome` em todas as telas e relatórios.

### 8.6 Perfil do Aluno (Onda 3A/3B + Etapa VI)

- **Toda leitura/escrita** dos dados de perfil passa por `app.services.aluno_perfil`. Nunca acessar `aluno.*_json` direto fora do módulo de serviço.
- Os JSONs legados (`_identificacao_json`, etc.) são **fallback de leitura** durante a transição. O código novo **não escreve** neles.
- `upsert_endereco`, `upsert_responsavel`, `upsert_perfil_socioeconomico`, `upsert_perfil_diversidade` criam/atualizam os registros a partir do `request.form`. NÃO commitam — quem chama é responsável pelo commit.
- `get_perfil_completo(aluno)` retorna um dict com todas as seções (identificação, endereço, responsável, socioeconômico, diversidade) já resolvido, com fallback. É o ponto de entrada para templates e rotas.
- `Aluno.documentos_dict()` e `Aluno.documento_entregue(doc_id)` são os acessores de `documentos_entregues` — usam o JSONB novo, caindo no `escolaridade_json` legado se necessário.
- `money()` normaliza valores monetários brasileiros (`1.234,56`, `R$ 250,00`) para `Decimal` com 2 casas; valores negativos ou inválidos levantam `ValueError`.
- `renda_per_capita()` devolve `None` quando falta renda ou nº de moradores e recusa `pessoas_residencia <= 0`.
- `upsert_perfil_socioeconomico` zera `beneficio_social_nome` quando o status não é 'Sim'.
- `upsert_perfil_diversidade` valida `tipo_deficiencia` contra o catálogo e o zera quando `saude_laudo = False`.

### 8.7 Atendimento

- Campo `setor` **não deve ser usado** em novas features (legado).
- O fluxo atual é exclusivamente pedagógico.

### 8.8 Multitenancy nos perfis

- As tabelas de perfil herdam `unidade_id` do aluno no momento da criação.
- Consultas por unidade devem filtrar tanto por `Aluno.unidade_id` quanto pelas tabelas de perfil (embora na prática o vínculo já garanta).

### 8.9 Planejamento pedagógico

- `admin`, `pedagogico` e `secretaria` podem acessar o planejamento e manter cursos, temas, níveis e executar operações de conselho.
- Cursos, temas, níveis e turmas alvo devem pertencer à unidade efetiva dos perfis não administrativos; `secretaria` sem unidade efetiva é bloqueada.
- Os parâmetros de data do conselho ficam em `ConfiguracaoSistema` como configuração global e exigem unidade efetiva para `secretaria`.
- `Curso` **não possui** carga horária. A C.H. é calculada por turma, em minutos (`Turma.carga_horaria_aula` e `Turma.carga_horaria_total`); para exibição usar `formatar_ch()` de `app.utils.formatters`.

---

## 9. Convenções de código

### 9.1 Estrutura do pacote

- Um arquivo por domínio (ver §2).
- `__init__.py` reexporta **todos os modelos** — é o ponto de entrada público para modelos. Enums e mixins não são reexportados (ver §2, regra 1).
- `base.py` centraliza imports, `JSONType` e os mixins `SoftDeleteMixin`/`TenantMixin`; `AuditoriaMixin` fica em `auditoria_mixin.py`.
- `enums.py` centraliza enums + constantes derivadas.

### 9.2 Nomenclatura

- Tabelas em **português**, plural quando coleção.
- Colunas em **snake_case**.
- FKs: `<entidade>_id`.
- Backrefs existentes **não devem ser renomeados sem migration**.

### 9.3 Boas práticas

- Não colocar lógica de negócio pesada nos models — preferir services.
- Preferir `back_populates` em código novo.
- Entidades novas: herdar `TenantMixin`/`SoftDeleteMixin` (e `AuditoriaMixin` quando houver edição por usuários) em vez de redeclarar `unidade_id`, `ativo` e `updated_*`.
- Em mixins com `ForeignKey` ou `relationship`, usar `@declared_attr` (SQLAlchemy 2.x).
- Se um modelo com `AuditoriaMixin` tiver outra FK para `user.id`, o relacionamento correspondente deve declarar `foreign_keys=` explicitamente (ex.: `Turma.professor`, `RegistroAula.instrutor`).
- Novas colunas de data/hora devem usar tipos nativos (`Date`, `Time`).
- Novos enums devem usar `db.Enum` ou constantes, não strings soltas.
- **Novos campos JSON** só com justificativa clara. Prefira colunas/tabelas.
- **Toda leitura/escrita de perfil do aluno** via `services.aluno_perfil`.
- Nunca interpolar Jinja com espaço entre chaves (`{ { } }`) — só `{{ }}`.

---

## 10. Histórico de ondas

### Onda 1 — Modularização + integridade + JSONB

- Pacote `app/models/` criado (antes era `models.py` monolítico).
- UNIQUE constraints em `frequencia`, `conselho_classe`.
- Índices em `frequencia` (turma+data, aluno+data).
- `db.JSON` → JSONB em `atendimento.dados` e `respostas_formulario.dados`.
- `ConfiguracaoSistema`: dois índices únicos parciais (global + por unidade).
- Correção do bug `Inscricao.data_inicio` (UTC → local, datetime → date).

### Onda 2A — Datas/horas nativas

- `Turma.data_inicio`, `data_fim`, `hora_inicio`, `hora_fim` → `Date`/`Time`.
- `Frequencia.data`, `RegistroAula.data` → `Date`.
- `DiaBloqueadoTurma.data`, `TemaAula.data` → `Date`.
- Criado `app/utils/datetime_parse.py` (`parse_date`, `parse_time`, `parse_datetime`).

### Onda 2B — Enums + CHECK

- Enums nativos no Postgres: `conceito_frequencia_enum`, `tipo_dia_bloqueado_enum`, `etapa_conselho_enum`, `tipo_pergunta_enum`.
- CHECK constraints: `ck_user_role`, `ck_conselho_situacao_final`.
- Criado `app/models/enums.py`.
- Refatoração de strings literais → constantes dos enums em todo o código.

### Onda 3A — Tabelas de perfil do Aluno

- Criadas `endereco_aluno` (1:1), `responsavel_aluno` (1:N), `perfil_socioeconomico` (1:1), `perfil_diversidade` (1:1).
- Adicionadas 10 colunas em `aluno`: `orgao_rg`, `nacionalidade`, `natural_uf`, `natural_cidade`, `nome_mae`, `cpf_mae`, `nome_pai`, `cpf_pai`, `vai_acompanhado_aulas`, `acompanhante_aulas`.
- Backfill a partir dos JSONs legados.
- **Nada foi removido** — JSONs continuam como fallback.

### Onda 3A-bis — `documentos_entregues`

- Adicionada coluna `aluno.documentos_entregues` (JSONB).
- Backfill a partir de `escolaridade_json`.

### Onda 3B — Migração de código

- Criado `app/services/aluno_perfil.py` (upserts + leituras com fallback).
- `registros/alunos.py` refatorado: cadastro e edição escrevem nas tabelas novas e nas colunas novas; `documentos_entregues` substitui o JSONB antigo.
- `relatorios/geral.py`, `relatorios/alunos.py`, `relatorios/shared.py` refatorados para usar JOINs nas tabelas novas.
- `registros/servico_social.py` usa `get_perfil_completo`.
- Templates `editar.html`, `impressao.html`, `atendimento_pedagogico.html`, `gerenciar.html` refatorados para usar `perfil` injetado pela rota.

### Onda 3B-bis — Etapa VI do cadastro do aluno (2026-09-22)

- `perfil_socioeconomico.renda_familiar`: `varchar(50)` (faixa textual) → `numeric(12,2)` (valor mensal em reais); faixas antigas descartadas na conversão, sem estimativa retroativa.
- `perfil_socioeconomico.beneficio_social_nome`: `varchar(100)` → `text` (vários programas unidos por ` | `).
- `perfil_diversidade.tipo_deficiencia`: nova coluna `varchar(30)`, restrita ao catálogo `TIPOS_DEFICIENCIA` do serviço. ⚠️ A criação da coluna está **comentada** na migration `3b7c9d1e4f20` e nenhuma outra migration a cria (ver §11.1, item 4).
- `app/services/aluno_perfil.py`: normalizador `money()`, cálculo de `renda_per_capita()` em runtime e validação `tipo_deficiencia()`.

### Onda 3B-ter — Auditoria de edição em `aluno` (2026-09-27)

- Adicionadas colunas `updated_by_id` (FK → user), `updated_by_name` (snapshot) e `updated_at` (timestamp) em `aluno`.
- Migration `f1a2b3c4d5e6` (FK `fk_aluno_updated_by_id`, `ON DELETE SET NULL`, só PostgreSQL). A migration `e1e3a5b2c333` repete as mesmas colunas (§11.1, item 2).
- `editar_aluno` grava esses campos a cada `POST` bem-sucedido.
- `editar_aluno` registra `LogAcao` com `acao='Editar aluno'` e `detalhes='aluno_id=N nome="..."'`.
- Permite rastrear retroativamente quem editou cada aluno consultando `aluno.updated_by_name` ou filtrando `log_acao` por `acao='Editar aluno'`.

### Ajustes de 2026-10 — mixins, auditoria automática, níveis e C.H.

- **Mixins:** `SoftDeleteMixin` e `TenantMixin` implementados em `base.py` e adotados por `PeriodoLetivo`, `Turma`, `TemaAula`, `Inscricao`, `Transferencia`, `Frequencia`, `RegistroAula`, `ConselhoClasse`, `ConselhoResposta`, `PerguntaConselho` e `OpcaoProximaTurma` (ver §1).
  - Efeito no esquema: `periodo_letivo.unidade_id` passa a ser **nullable** (antes documentado como NOT NULL).
- **Auditoria automática:** `AuditoriaMixin` (`auditoria_mixin.py`) adiciona `updated_by_id`, `updated_by_name` e `updated_at` em `turma`, `tema_aula`, `inscricoes`, `registro_aula` e `conselho_classe`; o listener `before_flush` (`auditoria_listener.py`) preenche as colunas e grava `LogAcao`. Migration: `a9f3c8e2d1b7`, que também cria as colunas em `curso` (sem mapeamento no modelo).
- **Níveis:** `nivel` passa a ter UNIQUE (`nome`, `unidade_id`) em vez de unicidade global (`c4d5e6f7a8b9`).
- **Carga horária calculada:** `curso.carga_horaria` removida do modelo e do banco (`d1e2f3a4b5c6`); `Turma.carga_horaria_aula` e `Turma.carga_horaria_total` (minutos) passam a ser properties calculadas. O código e a migration rotulam essa mudança como "Onda 3C", mas ela **não** é a Onda 3C de remoção dos JSONs legados descrita abaixo, que segue pendente.
- **Correções de schema:** `5a676f37b9a3` converte de fato `VARCHAR → DATE/TIME/ENUM` no PostgreSQL (o `batch_alter_table` das Ondas 2A/2B não convertia) e garante índices únicos de `frequencia` e `conselho_classe`; `b7c1d2e3f4a5` recria a sequência/default de `inscricoes.id` (drift de dump antigo).

### Onda 3C — Pendente (~2 semanas)

- Dropar os 4 JSONs de `Aluno`.
- Remover properties correspondentes em `pessoas.py`.
- Remover blocos `# FALLBACK` em `aluno_perfil.py`.
- Atualizar este MER.

---

## 11. Referência cruzada com migrations

| Hash           | Revises        | Descrição                                                    | Estado  |
|----------------|----------------|--------------------------------------------------------------|---------|
| `6a8df39d`     | —              | Google OAuth2 em User (**raiz** do histórico Alembic)        | ✅       |
| `a1b2c3d4`     | `6a8df39d`     | Tabela de atendimentos                                       | ✅       |
| `7aa724d05691` | `a1b2c3d4`     | Ajustes em atendimento + tamanho de `google_id`              | ✅       |
| `b2c3d4e5`     | `7aa724d05691` | Campo `ordem` em TemaAula                                    | ✅       |
| `99f0996802e6` | `b2c3d4e5`     | Período de conselho                                          | ✅       |
| `26e459a7e00a` | `99f0996802e6` | Inscricao com PK própria                                     | ✅       |
| `73f922fd358f` | `26e459a7e00a` | **Onda 1**: integridade + JSONB                              | ✅       |
| `a1bbf3c29231` | `73f922fd358f` | **Onda 2A**: datas/horas nativas                             | ⚠️ 6    |
| `ef4e5af7e876` | `a1bbf3c29231` | **Onda 2B**: enums + CHECK                                   | ⚠️ 6    |
| `5ae559bc9d87` | `ef4e5af7e876` | **Onda 3A**: tabelas de perfil                               | ✅       |
| `29a29fdbc2aa` | `5ae559bc9d87` | **Onda 3A-bis**: `documentos_entregues`                      | ⚠️ 5    |
| `3b7c9d1e4f20` | `29a29fdbc2aa` | **Onda 3B-bis**: renda mensal (`tipo_deficiencia` comentado) | ⚠️ 4    |
| `4c8e2f7a1b30` | `3b7c9d1e4f20` | **Onda 3B-bis**: programas sociais                           | ✅       |
| `f1a2b3c4d5e6` | `4c8e2f7a1b30` | **Onda 3B-ter**: auditoria de edição em `aluno`              | ✅       |
| `e1e3a5b2c333` | `f1a2b3c4d5e6` | Colunas de auditoria em `aluno` (repete `f1a2b3c4d5e6`)      | ⚠️ 2    |
| `a9f3c8e2d1b7` | `e1e3a5b2c333` | `AuditoriaMixin`: colunas de auditoria em 6 tabelas          | ⚠️ 3    |
| `c4d5e6f7a8b9` | `a9f3c8e2d1b7` | Níveis únicos por unidade (**ponto de bifurcação**)          | ✅       |
| `5a676f37b9a3` | `c4d5e6f7a8b9` | Fix Onda 2A/2B: conversão real de tipos + índices            | ⚠️ 1, 6 |
| `b7c1d2e3f4a5` | `5a676f37b9a3` | Fix sequência de `inscricoes.id` (**head**)                  | ⚠️ 1    |
| `d1e2f3a4b5c6` | `c4d5e6f7a8b9` | **Onda 3C**: remove `curso.carga_horaria` (**head**)         | ⚠️ 1    |

> **Estado:** ✅ = registrada em `migrations/versions/` sem ressalvas; ⚠️ *n* = registrada com a ressalva *n* de §11.1. O estado reflete os arquivos, não o `alembic_version` de cada banco.

> Consulte `flask db history` para confirmar a cadeia em execução. Toda
> migration deve ter `revision` e `down_revision` preenchidos com hashes
> reais — **nunca** deixar `<hash>` literal.

### 11.1 Ressalvas das migrations registradas

1. **Dois heads.** `c4d5e6f7a8b9` tem dois filhos: `5a676f37b9a3` (→ `b7c1d2e3f4a5`) e `d1e2f3a4b5c6`. Heads atuais: `b7c1d2e3f4a5` e `d1e2f3a4b5c6`; `flask db upgrade` falha com "Multiple head revisions". Ação: `flask db merge -m "merge heads" b7c1d2e3f4a5 d1e2f3a4b5c6` (ou reapontar o `down_revision` de `d1e2f3a4b5c6` para `b7c1d2e3f4a5`, se ainda não aplicada em nenhum banco). O cabeçalho de `d1e2f3a4b5c6` traz `Create Date: 2026-10-27`, posterior à data do arquivo (2026-10-21).
2. **`e1e3a5b2c333` duplica `f1a2b3c4d5e6`.** Ambas fazem `add_column` de `aluno.updated_by_id`, `updated_by_name` e `updated_at` e criam `fk_aluno_updated_by_id`; em um banco novo, a segunda falha por coluna duplicada. Ação: tornar `e1e3a5b2c333` idempotente ou removê-la (apontando `a9f3c8e2d1b7` para `f1a2b3c4d5e6`) — esta última só se nenhum banco tiver `e1e3a5b2c333` em `alembic_version`.
3. **`a9f3c8e2d1b7` inclui `curso`.** Cria as colunas de auditoria em `turma`, `tema_aula`, `registro_aula`, `curso`, `conselho_classe` e `inscricoes`; porém `Curso` não herda `AuditoriaMixin` (pelas migrations, o banco terá três colunas a mais que o modelo). Além disso, o modelo `Aluno` declara a FK `updated_by_id` sem `ondelete`, enquanto a migration cria `ON DELETE SET NULL`. Ação: herdar o mixin em `Curso` (ou dropar as colunas) e alinhar o `ondelete` em `Aluno`.
4. **`perfil_diversidade.tipo_deficiencia` sem migration.** Em `3b7c9d1e4f20` o `add_column` está comentado, o `downgrade` tenta dropar a coluna e nenhuma outra revisão a cria — modelo e MER a possuem. Ação: nova migration com `add_column` (checando existência).
5. **`aluno.documentos_entregues` é criado como `JSON`, não `JSONB`.** `29a29fdbc2aa` usa `sa.JSON()` genérico (no SQLite, pula a criação) e nenhuma revisão posterior altera o tipo; o modelo usa `JSONType` (JSONB no PostgreSQL). Ação: migration `alter_column` para JSONB (`postgresql_using="documentos_entregues::jsonb"`).
6. **Ondas 2A/2B só convertidas em `5a676f37b9a3`.** O `batch_alter_table` de `a1bbf3c29231`/`ef4e5af7e876` não converteu os tipos no PostgreSQL; `5a676f37b9a3` faz `ALTER COLUMN ... TYPE ... USING` (não é idempotente: tende a falhar se as colunas já forem `DATE`/`TIME`) e cria `uix_frequencia_aluno_turma_data` e `uix_conselho_turma_aluno_etapa` com `CREATE UNIQUE INDEX IF NOT EXISTS` — no-op se as constraints de `73f922fd358f` já existirem. Ambas são no-op no SQLite.
7. **`47ae52f8da90` não consta em `versions/`.** A linha "Ajustes de auditoria em Turma/TemaAula" listada em revisões anteriores deste MER foi removida; a migration de auditoria registrada é `a9f3c8e2d1b7`. Se algum banco tiver `47ae52f8da90` em `alembic_version`, o Alembic não localizará a revisão.
8. **Alterações de modelo sem migration.** Nenhuma revisão altera `periodo_letivo`: a mudança de `unidade_id` para nullable via `TenantMixin` (§12.10) não tem migration, nem as alterações de `comment=` das colunas dos mixins.
9. **Inconsistências de cabeçalho (sem efeito na cadeia).** `b2c3d4e5` documenta `Revises: a1b2c3d4`, mas o `down_revision` real é `7aa724d05691`; `7aa724d05691` tem nome de arquivo "add google_id and google_email", porém ajusta `atendimento` e o tamanho de `google_id` (`google_email` é criado em `6a8df39d`). Não existe migration-base: o schema inicial é anterior ao Alembic.

---

## 12. Dívida técnica e roadmap

### 12.1 Datas/horas como string

**Status:** resolvido na Onda 2A. Todas as colunas convertidas.

### 12.2 `backref` em vez de `back_populates`

**Onde:** maioria dos relacionamentos.
**Impacto:** dificulta leitura e refatoração.
**Plano:** migração gradual, mantendo os mesmos nomes de backref.

### 12.3 Adoção parcial dos mixins

**Status:** implementado parcialmente. `SoftDeleteMixin` e `TenantMixin` existem em `base.py`; `AuditoriaMixin` existe em `auditoria_mixin.py` (ver §1 e §2).
**Pendente:**

- Modelos que ainda redeclaram `ativo` e/ou `unidade_id` manualmente: `Unidade`, `Curso`, `Nivel`, `Aluno`, `SituacaoEscolar`, `EnderecoAluno`, `ResponsavelAluno`, `PerfilSocioeconomico`, `PerfilDiversidade`, `User`, `ConfiguracaoSistema`, `DiaBloqueado`, `DiaBloqueadoTurma`, `PeriodoConselho`, `Atendimento`, `LogAcao` e `Registro`.
- `Aluno` mantém colunas de auditoria manuais (FK sem `ondelete` no modelo, embora o banco tenha `SET NULL`; `updated_at` sem default) em vez do `AuditoriaMixin`.
- `created_at`/`updated_at` continuam repetidos por modelo; o `TimestampMixin` citado no docstring de `base.py` **não foi implementado**.

### 12.4 JSONs legados em `Aluno`

**Onde:** `_escolaridade_json`, `_identificacao_json`,
`_socioeconomico_json`, `_diversidade_json`.
**Status:** a serem removidos na Onda 3C.

`_socioeconomico_json` é uma coluna `text` que contém um objeto JSON legado
com as chaves `renda_familiar`, `residente_maior_renda`,
`pessoas_residencia`, `ocupacao`, `beneficio_social_status`,
`beneficio_social_nome`, `meio_transporte` e `vulnerabilidade_social`.
O acesso deve ser feito pela propriedade `Aluno.socioeconomico_json`; o
serviço `app.services.aluno_perfil` usa esse JSON somente como fallback quando
`PerfilSocioeconomico` ainda não existe. Dados novos devem ser gravados na
tabela estruturada, e não duplicados nesse JSON.

### 12.5 `Turma.dias_semana` como CSV

**Onde:** coluna `varchar(20)` com nomes separados por vírgula.
**Impacto:** dificulta "quantas turmas têm aula na sexta".
**Plano futuro:** tabela `turma_dia_semana (turma_id, dia)`.

### 12.6 `AgendaServicoSocial.participantes_emails` como CSV

**Plano futuro:** tabela `participante_evento`.

### 12.7 Unicidade do nome de `Nivel`

**Status:** resolvido pela migration `c4d5e6f7a8b9`, que substitui a unicidade global por UNIQUE (`nome`, `unidade_id`).

### 12.8 `Atendimento.setor` legado

**Status:** sem uso no fluxo atual. Pode ser dropado em onda futura.

### 12.9 `Registro` (modelo legado)

**Status:** mantido apenas para leitura histórica. Não usar em código novo.

### 12.10 `unidade_id` nullable em `periodo_letivo` (via `TenantMixin`)

**Onde:** `PeriodoLetivo` (documentado como NOT NULL até a revisão anterior deste MER).
**Impacto:** o modelo aceita períodos sem unidade, o que contradiz a regra de isolamento (§4); se o banco ainda estiver NOT NULL, há divergência modelo × schema.
**Plano:** decidir entre sobrescrever `unidade_id` com `nullable=False` no modelo (como em `Transferencia`) ou criar a migration correspondente — nenhuma revisão registrada em `versions/` altera `periodo_letivo` (§11.1, item 8).

### 12.11 Pontos de atenção da auditoria automática

- Detecção por `hasattr(obj, 'updated_by_id')`: `Aluno` é auditado pelo listener **e** por `LogAcao(acao='Editar aluno')` em `editar_aluno` (possível duplicidade de logs).
- O listener grava `updated_at = db.func.now()` (relógio do servidor de banco), enquanto o `default`/`onupdate` das colunas usa `get_local_now` (fuso da aplicação) — risco de horários inconsistentes.
- O listener também preenche `updated_*` em INSERTs, contrariando os docstrings de `AuditoriaMixin` e `Aluno` ("NULL até a primeira edição"); no mixin, o próprio `default=get_local_now` já preenche a coluna na inclusão.
- DELETE físico não é auditado (só `session.new` e `session.dirty` são processados).
- `AuditoriaMixin.updated_by` usa `lazy='joined'`: toda consulta dos 5 modelos auditados faz JOIN com `user`.

### 12.12 Integridade da cadeia de migrations e drift modelo × banco

**Onde:** `migrations/versions/` (ver §11.1).
**Impacto:** dois heads impedem `flask db upgrade`; `e1e3a5b2c333` quebra a criação de bancos novos; `tipo_deficiencia`, o tipo de `documentos_entregues` e as colunas de auditoria de `curso` divergem entre modelo e banco.
**Plano:** executar as ações do §11.1 (merge dos heads, idempotência de `e1e3a5b2c333`, migrations corretivas) antes da Onda 3C de remoção dos JSONs.

---

## Apêndice A — Como ler/escrever perfil do aluno

```python
from app.services.aluno_perfil import (
    get_perfil_completo,        # leitura completa (fallback incluso)
    get_endereco,                # leitura individual
    get_responsavel_principal,
    get_perfil_socioeconomico,
    get_perfil_diversidade,
    get_identificacao,
    upsert_endereco,             # escrita a partir do request.form
    upsert_responsavel,
    upsert_perfil_socioeconomico,
    upsert_perfil_diversidade,
)

# Leitura
perfil = get_perfil_completo(aluno)
endereco = perfil["endereco"]     # dict já resolvido

# Escrita
upsert_endereco(aluno, request.form)
upsert_responsavel(aluno, request.form)
# … (commit fica a cargo de quem chama)
```

## Apêndice B — Como acessar documentos entregues

```python
aluno.documentos_dict()
# → {'doc_entregue': {'doc_aluno': True, 'doc_termo': False, ...}}

aluno.documento_entregue('doc_laudo')
# → True / False
```

Em template Jinja:

```jinja
{% if aluno.documento_entregue('doc_aluno') %}✓{% endif %}
```

## Apêndice C — Declarando um modelo com os mixins

```python
from app.models.base import db, SoftDeleteMixin, TenantMixin
from app.models.auditoria_mixin import AuditoriaMixin


class MinhaEntidade(SoftDeleteMixin, TenantMixin, AuditoriaMixin, db.Model):
    __tablename__ = 'minha_entidade'

    id = db.Column(db.Integer, primary_key=True)
    # `ativo`, `unidade_id`, `updated_by_id`, `updated_by_name` e `updated_at`
    # já vêm dos mixins; o listener before_flush preenche a auditoria.
```
