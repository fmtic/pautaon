### Alterações do dia — 11/09/2026

- Data da intervenção: 11/09/2026
- Início da correção: 2026-09-11 18:35
- Conclusão da correção: 2026-09-11 18:55

Este complemento resolve a pendência descrita acima e acrescenta ajustes de paridade/robustez encontrados durante a revisão. Para aplicar em outro repositório, siga os passos abaixo após conferir se os arquivos daquele repositório já receberam a primeira parte da funcionalidade.

### Corrigido no repositório em produção

A correção aplicada neste checkout foi a seguinte:

- Removida a falha na template de edição causada por `div` não definida e por um trecho literal `` `n `` no stepper.
- Ajustado o stepper da etapa de edição para incluir a Etapa VI corretamente e evitar que a renderização do formulário quebrasse com erro de template.
- Reativado o carregamento do script de situação escolar na edição, garantindo que campos condicionais e autocomplete funcionem na tela de alteração do aluno.
- Reforçada a lógica de persistência em `app/routes/registros/alunos.py` para limpar a situação escolar vazia, salvar `status`/`status_outro` e limitar o autocomplete a termos com pelo menos 2 caracteres.
- Ajustado `app/static/js/alunos/situacao_escolar.js` para criar sugestões com `document.createElement` e evitar injeção de HTML por nomes vindos do banco.
- Atualizado `app/static/js/alunos/editar.js` para detectar etapas dinamicamente e respeitar a etapa 6 no passo final.

### Resumo do que foi concluído

1. As colunas `status` e `status_outro` foram adicionadas ao modelo `SituacaoEscolar`.
2. A função `_salvar_situacao_escolar(aluno)` passou a salvar `status_escolar` e `status_escolar_outro`.
3. A função `_salvar_situacao_escolar(aluno)` passou a apagar a situação escolar existente quando o formulário da etapa VI é enviado totalmente vazio.
4. O endpoint `/alunos/instituicoes` passou a retornar lista vazia para termos com menos de 2 caracteres.
5. O autocomplete passou a consultar nomes distintos de instituição e ignorar registros com nome nulo.
6. O JavaScript `situacao_escolar.js` deixou de montar botões por `innerHTML` e passou a usar `document.createElement`, reduzindo risco de HTML injetado por nomes cadastrados no banco.
7. A tela `app/templates/alunos/editar.html` recebeu também a Etapa VI: Situação Escolar, preenchendo os campos com dados existentes de `aluno.situacao_escolar`.
8. O arquivo `app/static/js/alunos/editar.js` foi ajustado para detectar etapas dinamicamente, aceitando a nova etapa 6.
9. O script `scripts/migrate_situacao_escolar.py` passou a adicionar `status` e `status_outro` por `ALTER TABLE ... ADD COLUMN` somente quando ausentes.
10. O schema estático `scripts/postgres_schema.sql` recebeu a tabela `situacao_escolar` com as colunas finais e o índice `ix_situacao_escolar_unidade_nome`.

### Arquivos alterados nesta parte

| Arquivo | O que fazer no repositório paralelo |
| --- | --- |
| `app/models.py` | Adicionar `status` e `status_outro` em `SituacaoEscolar`, se ainda não existirem. |
| `app/routes/registros/alunos.py` | Atualizar `_salvar_situacao_escolar` e endurecer o endpoint `/alunos/instituicoes`. |
| `app/static/js/alunos/situacao_escolar.js` | Substituir a renderização do autocomplete por criação segura de elementos DOM. |
| `app/templates/alunos/editar.html` | Adicionar indicador 6, criar a Etapa VI preenchida e carregar `situacao_escolar.js`. |
| `app/static/js/alunos/editar.js` | Trocar o controle fixo de 5 etapas por detecção dinâmica de `.form-step`. |
| `scripts/migrate_situacao_escolar.py` | Tornar a migração aditiva também para colunas novas em tabela já existente. |
| `scripts/postgres_schema.sql` | Incluir `CREATE TABLE situacao_escolar` e `CREATE INDEX ix_situacao_escolar_unidade_nome`. |

[... resto da seção de 11/09 permanece igual ...]

---

### Alterações do dia — 17/09/2026

- Data da intervenção: 17/09/2026
- Início: manhã
- Conclusão: fim do dia

Refatoração estrutural em 6 ondas sequenciais. O objetivo foi reduzir dívida técnica acumulada e preparar o sistema para relatórios sobre perfil socioeconômico e de diversidade dos alunos. Cada onda é independente, verificável e reversível.

### Resumo das ondas aplicadas

| Onda | Escopo | Migrations |
| --- | --- | --- |
| **1** | Modularização do `models.py` + integridade + JSONB | `73f922fd358f` |
| **2A** | Datas/horas nativas (fim dos `varchar`) | `a1bbf3c29231` |
| **2B** | Enums nativos + CHECK constraints | `ef4e5af7e876` |
| **3A** | 4 tabelas de perfil do Aluno + 10 colunas | `5ae559bc9d87` |
| **3A-bis** | Coluna `documentos_entregues` (JSONB) | `29a29fdbc2aa` |
| **3B** | Backend + relatórios + templates refatorados | — |

### Onda 1 — Modularização, integridade e JSONB

- Pacote `app/models/` criado (antes era `models.py` monolítico de ~1000 linhas).
- UNIQUE constraints adicionadas: `frequencia (aluno_id, turma_id, data)` e `conselho_classe (turma_id, aluno_id, etapa)`.
- Índices adicionados em `frequencia`: `(turma_id, data)` e `(aluno_id, data)`.
- `db.JSON` → JSONB em `atendimento.dados` e `respostas_formulario.dados`.
- `ConfiguracaoSistema`: dois índices únicos parciais (`ix_config_chave_global`, `ix_config_chave_unidade`).
- Correção do bug `Inscricao.data_inicio` (usava `datetime.utcnow()` em coluna `Date`).
- Criado `scripts/smoke_models.py` — 24 verificações automáticas do pacote de modelos.

### Onda 2A — Datas e horas nativas

- `Turma.data_inicio`, `data_fim`, `hora_inicio`, `hora_fim` → `Date`/`Time`.
- `Frequencia.data`, `RegistroAula.data` → `Date`.
- `DiaBloqueadoTurma.data`, `TemaAula.data` → `Date`.
- Criado `app/utils/datetime_parse.py` com `parse_date`, `parse_time`, `parse_datetime` (tolerantes a `None`/vazio/string).
- 8 arquivos de rota ajustados para converter string → tipo nativo antes de gravar/filtrar.
- Criado `scripts/preflight_onda2a.py` e `scripts/check_onda2a.py`.

### Onda 2B — Enums nativos e CHECK constraints

- Criado `app/models/enums.py` com 6 enums (`ConceitoFrequencia`, `TipoDiaBloqueado`, `EtapaConselho`, `TipoPergunta`, `UserRole`, `SituacaoFinal`) e conjuntos derivados (`CONCEITOS_PRESENCA`, `CONCEITOS_CONTABEIS`, `ETAPAS_ORDEM`).
- Enums nativos no PostgreSQL: `conceito_frequencia_enum`, `tipo_dia_bloqueado_enum`, `etapa_conselho_enum`, `tipo_pergunta_enum`.
- CHECK constraints: `ck_user_role`, `ck_conselho_situacao_final`.
- Refatoração de ~40 strings literais de `role` para `UserRole.*` em `auth.py`, `conselho.py`, `core.py`, `turmas.py`, `dashboard_admin.py`, `relatorios/geral.py`, `bootstrap.py`, `logica.py`.
- Criado `scripts/preflight_onda2b.py` e `scripts/check_onda2b.py`.

### Onda 3A — Tabelas de perfil do Aluno

- Criadas 4 tabelas novas:
  - `endereco_aluno` (1:1 com Aluno).
  - `responsavel_aluno` (1:N com Aluno).
  - `perfil_socioeconomico` (1:1 com Aluno).
  - `perfil_diversidade` (1:1 com Aluno).
- Adicionadas 10 colunas em `aluno`: `orgao_rg`, `nacionalidade`, `natural_uf`, `natural_cidade`, `nome_mae`, `cpf_mae`, `nome_pai`, `cpf_pai`, `vai_acompanhado_aulas`, `acompanhante_aulas`.
- Backfill a partir dos JSONs legados, preservando `unidade_id` e criando registros apenas quando há dado real.
- **Nada foi removido** — os 4 JSONs (`_escolaridade_json`, `_identificacao_json`, `_socioeconomico_json`, `_diversidade_json`) continuam como fallback.
- Criado `scripts/preflight_onda3.py` (mapeamento dos JSONs).

### Onda 3A-bis — Coluna `documentos_entregues`

- Adicionada coluna `aluno.documentos_entregues` (JSONB) no formato `{'doc_entregue': {doc_id: bool}}`.
- Backfill a partir de `escolaridade_json`.
- Adicionados métodos `Aluno.documentos_dict()` e `Aluno.documento_entregue(doc_id)` como acessores.

### Onda 3B — Migração de código

- Criado `app/services/aluno_perfil.py`:
  - `upsert_endereco`, `upsert_responsavel`, `upsert_perfil_socioeconomico`, `upsert_perfil_diversidade` (escrita a partir do `request.form`).
  - `get_perfil_completo`, `get_endereco`, `get_responsavel_principal`, `get_perfil_socioeconomico`, `get_perfil_diversidade`, `get_identificacao` (leitura com fallback nos JSONs).
  - Normalizadores `s()`, `i()`, `b()`.
- `app/registros/alunos.py` refatorado:
  - Cadastro e edição gravam nas tabelas novas via `upsert_*`.
  - Campos civis (`nome_mae`, `orgao_rg`, etc.) gravam direto em `Aluno`.
  - Documentos entregues vão para `documentos_entregues` (JSONB).
  - `editar_aluno` e `imprimir_aluno` passam `perfil=get_perfil_completo(aluno)` para o template.
- `app/relatorios/geral.py`, `app/relatorios/alunos.py`, `app/relatorios/shared.py` refatorados:
  - Filtros usam JOIN nas tabelas novas em vez de JSON path.
  - `_is_pcd` e `_acompanhante` centralizam leitura com fallback.
  - `_contar_por_genero` usa `get_perfil_diversidade`.
- `app/registros/servico_social.py`: `dados_aluno` usa `get_perfil_completo`.
- Templates refatorados:
  - `editar.html` usa `perfil.identificacao`, `perfil.endereco`, `perfil.socioeconomico`, `perfil.diversidade`, `perfil.responsavel`.
  - `impressao.html` idem.
  - `atendimento_pedagogico.html` usa colunas novas com fallback.
  - `gerenciar.html` usa `aluno.documentos_dict()`.
- Corrigido bug de sintaxe JS `{ { X } }` → `{{ X }}` em `editar.html` e `calendario_bloqueados_print.html`.
- `MER.md` atualizado com histórico de ondas, referência cruzada de migrations e apêndices.

### Arquivos alterados nesta parte

| Arquivo | Natureza da mudança |
| --- | --- |
| `app/models/__init__.py`, `base.py`, `enums.py` | Novos (pacote) |
| `app/models/organizacao.py`, `usuarios.py`, `pedagogico.py`, `academico.py`, `pessoas.py`, `perfis.py`, `matriculas.py`, `calendario.py`, `aulas.py`, `conselho.py`, `atendimento.py`, `servico_social.py`, `auditoria.py`, `legado.py` | Novos (pacote) |
| `app/utils/datetime_parse.py` | Novo |
| `app/utils/logica.py`, `app/utils/frequencia.py` | Refatorados |
| `app/services/aluno_perfil.py` | Novo |
| `app/registros/alunos.py`, `core.py`, `turmas.py`, `periodos.py`, `servico_social.py` | Refatorados |
| `app/relatorios/geral.py`, `alunos.py`, `shared.py` | Refatorados |
| `app/main/dashboard_professor.py`, `dashboard_admin.py`, `secretaria.py` | Refatorados |
| `app/auth.py`, `conselho.py` | Refatorados |
| `app/services/bootstrap.py` | Refatorado |
| `app/templates/alunos/editar.html`, `impressao.html`, `gerenciar.html`, `atendimento_pedagogico.html` | Refatorados |
| `app/templates/planejamento/calendario_bloqueados_print.html` | Correção de sintaxe |
| `MER.md` | Atualizado |
| `scripts/smoke_models.py`, `preflight_onda2a.py`, `check_onda2a.py`, `preflight_onda2b.py`, `check_onda2b.py`, `preflight_onda3.py` | Novos |

### Comandos de validação usados

```powershell
# Sobe a app
python -c "from app import create_app; app = create_app(); print('OK')"

# Smoke test (24 verificações)
python scripts\smoke_models.py

# Verificação de cada onda
python scripts\check_onda2a.py
python scripts\check_onda2b.py