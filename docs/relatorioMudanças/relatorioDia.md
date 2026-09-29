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
```

### Limpeza final do mesmo dia (commit `4b4566e`, 22:29)

- Removido o `app/models.py` monolítico (732 linhas), artefato que restava da Onda 1 — a partir daqui o projeto usa exclusivamente o pacote `app/models/`.
- Removidos `app/models.zip` e `app/LEIA-ME.md` (obsoletos).
- Ajustado o `.vscode/settings.json`.

---

### Alterações do dia — 20/09/2026

- Data da intervenção: 20/09/2026
- Commit: `896115c` — segurança: corrige IDOR, CSRF e exposição de arquivos estáticos (23:57)

Auditoria interna de segurança, privacidade e dívidas técnicas (LGPD/ECA) registrada em `docs/checklist_seguranca_dividas_tecnicas.md`, com 11 achados (SEC-01 a SEC-11) remediados neste mesmo commit.

### Principais correções aplicadas

- **SEC-01 (crítica)** — uploads de documentos, laudos e fotos deixam `app/static/uploads/` e passam para `instance/uploads/`; os arquivos agora são servidos por rotas autenticadas (`@login_required` + validação de unidade), eliminando download anônimo por URL previsível.
- **SEC-02 (crítica)** — rotas de exclusão/inativação/desenturmação migradas de `GET` para `POST` com token CSRF (alunos, turmas, unidades, perguntas do conselho, períodos letivos, agendamentos do serviço social); templates convertem links em formulários `POST`.
- **SEC-03 a SEC-05** — interceptor global `enforce_user_access_state` (perfis `pendente`/`first_login`), checagem de perfil (RBAC) nas ações destrutivas e reforço do `assert_unidade_context` (bloqueia unidade nula), fechando IDOR entre unidades.
- **SEC-06** — Google OAuth: exigência de e-mail verificado, restrição por domínio (`GOOGLE_OAUTH_ALLOWED_DOMAINS`) e bloqueio de vinculação automática quando já existe conta local com senha.
- **SEC-07** — troca de senha passa a exigir a senha atual (fora do fluxo de primeiro acesso).
- **SEC-08** — histórico de brute-force persistido em banco (`ConfiguracaoSistema`), sem perda de estado em reinicializações multi-worker; `ProxyFix` aplicado para leitura do IP real atrás de proxy reverso.
- **SEC-09 a SEC-11** — `SESSION_COOKIE_SECURE` corrigida; cabeçalhos de segurança (`X-Frame-Options`, `HSTS`, `X-Content-Type-Options`, `Referrer-Policy`) via `after_request`; mensagens de erro deixam de vazar detalhes internos do banco.
- `_get_upload_root` centraliza o diretório de uploads via `UPLOAD_FOLDER` (`instance/`).
- Arquivos de upload de desenvolvimento removidos do repositório.

### Novos scripts, testes e documentação

- `scripts/migrar_uploads_para_instance.py` — migração dos arquivos físicos legados para a pasta protegida.
- `scripts/verificar_sec01.py` — verificação automatizada do SEC-01.
- `tests/test_security_regressions.py` e `tests/test_sec01_uploads.py` — regressões de segurança; configuração do pytest no `pyproject.toml`.
- `docs/checklist_seguranca_dividas_tecnicas.md` — novo documento-âncora da auditoria.

### Arquivos alterados nesta parte

| Arquivo | Natureza da mudança |
| --- | --- |
| `app/__init__.py` | Interceptor global de acesso + cabeçalhos de segurança + `ProxyFix` |
| `app/auth.py` | CSRF no admin, brute-force em banco, senha atual obrigatória, OAuth endurecido |
| `app/registros/alunos.py`, `atendimentos.py`, `core.py`, `periodos.py`, `servico_social.py`, `shared.py` | Uploads protegidos, `POST`+CSRF, RBAC e isolamento de unidade |
| `config.py` | `UPLOAD_FOLDER`, `GOOGLE_OAUTH_ALLOWED_DOMAINS`, cookie seguro |
| `app/templates/**` | Links de mutação convertidos em formulários `POST` com `csrf_token` |
| `docs/checklist_seguranca_dividas_tecnicas.md` | Novo |
| `scripts/migrar_uploads_para_instance.py`, `scripts/verificar_sec01.py` | Novos |
| `tests/test_security_regressions.py`, `tests/test_sec01_uploads.py` | Novos |
| `pyproject.toml` | Configuração do pytest |
| `app/static/uploads/**` | Arquivos de desenvolvimento removidos do versionamento |

---

### Alterações do dia — 21/09/2026

- Data da intervenção: 21/09/2026 (sessão da madrugada)
- Commits: `0b19c7a` (00:16) e `35439c7` (00:25)

### README e robustez do login (`0b19c7a`)

- `README.md` reescrito e ampliado.
- Login deixa de quebrar em falha de banco: a consulta de usuário é protegida e exibe "Sistema temporariamente indisponível" em vez de erro 500.
- Persistência do histórico de tentativas falhas com fallback silencioso em memória (se o banco falhar, a proteção em memória segue ativa na instância).
- Error handler global ampliado de `OperationalError` para `SQLAlchemyError` (tela `sistema_indisponivel.html` em 503).

### Nomenclatura de "dashboard" para "Painel" (`35439c7`)

- Renomeação de dashboard → Painel na nomenclatura interna e nos textos: endpoint `main.painel` (antes `main.dashboard`), redirecionamentos, docstrings e templates. Sem mudança de comportamento.

### Arquivos alterados nesta parte

| Arquivo | Natureza da mudança |
| --- | --- |
| `README.md` | Reescrito e ampliado |
| `app/auth.py` | Login resiliente a falha de banco; fallback do rate limit em memória |
| `app/__init__.py` | Error handler ampliado (`SQLAlchemyError`) |
| `app/main/__init__.py`, `dashboard.py`, `secretaria.py`, `unidade.py`, `app/registros/core.py`, `app/registros/servico_social.py` | Renomeação dashboard → Painel |
| `app/templates/base.html`, `app/templates/dashboard/index.html` | Textos "Painel" |

---

### Alterações do dia — 22/09/2026

- Data da intervenção: 22/09/2026
- Commit: `f66a731` — Etapa VI do cadastro do aluno + relatório de exportação de alunos (21:56)

### Etapa VI — perfil socioeconômico e diversidade

- `perfil_socioeconomico.renda_familiar`: `varchar(50)` (faixa textual) → `numeric(12,2)` (valor mensal em reais); faixas antigas descartadas na conversão, sem estimativa retroativa.
- `perfil_socioeconomico.beneficio_social_nome`: `varchar(100)` → `text` (vários programas unidos por ` | `).
- `perfil_diversidade.tipo_deficiencia`: nova coluna (`varchar(30)`), restrita ao catálogo do serviço.
- `app/services/aluno_perfil.py`: normalizador `money()` (formato brasileiro → `Decimal`), cálculo de `renda_per_capita()` em runtime (não persistido) e validação/limpeza de `tipo_deficiencia` (mantido apenas com `saude_laudo`).
- Cadastro e edição (`novo.html`, `editar.html`, `registros/alunos.py`) passam a gravar os novos campos; JS ajustado (unificado no dia seguinte).
- Migrations novas: `3b7c9d1e4f20` (renda + tipo_deficiencia) e `4c8e2f7a1b30` (programas sociais).

### Relatório de exportação de alunos

- Filtros gerais na tela: Data Inicial, Data Final e Período Letivo.
- Nova coluna "Data da Matrícula" (usa `created_at`) disponível para seleção e exportação.
- Exportação passa a ser ordenada por nome.

### Infraestrutura e documentação

- `config.py`: `_get_database_uri()` normaliza `DATABASE_URL` SQLite (caminhos relativos do Windows e prefixo `instance/`).
- `scripts/postgres_schema.sql` atualizado com as colunas novas e `scripts/create_postgres_schema.py` ajustado.
- `MER.md`: dicionário de dados atualizado (renda numérica, `beneficio_social_nome` texto, `tipo_deficiencia`).
- `docs/manual_programas_sociais.md` criado; `tests/test_aluno_perfil.py` ampliado.
- Observação: `instance/database.db.bak` (backup do SQLite, 270 KB) entrou por engano no commit e ainda aguarda a remoção do versionamento.

### Arquivos alterados nesta parte

| Arquivo | Natureza da mudança |
| --- | --- |
| `app/models/perfis.py`, `pessoas.py` | Novas colunas e documentação do JSON legado |
| `migrations/versions/3b7c9d1e4f20_*.py`, `4c8e2f7a1b30_*.py` | Novas migrations (Onda 3B-bis) |
| `app/services/aluno_perfil.py` | `money()`, `renda_per_capita()`, `tipo_deficiencia()` |
| `app/registros/alunos.py` | Persistência da Etapa VI |
| `app/templates/alunos/novo.html`, `editar.html`, `impressao.html`, `gerenciar.html` | Campos novos da Etapa VI |
| `app/static/js/alunos/aluno_form.js`, `novo.js`, `editar.js` | Máscaras e validações dos campos novos |
| `app/relatorios/alunos.py`, `app/templates/relatorios/relatorio_alunos.html` | Filtros gerais, coluna Data da Matrícula, ordenação por nome |
| `config.py` | `_get_database_uri()` |
| `scripts/postgres_schema.sql`, `scripts/create_postgres_schema.py` | Schema atualizado |
| `docs/manual_programas_sociais.md` | Novo |
| `tests/test_aluno_perfil.py` | Ampliado |
| `app/models/MER.md` | Dicionário atualizado |

---

### Alterações do dia — 23/09/2026

- Data da intervenção: 23/09/2026
- Commits: `ef933b8` (11:36) e `dba5464` (19:13)

### Unificação do JS do formulário do aluno (`ef933b8`)

- Lógica consolidada em dois arquivos: `aluno_utils.js` (máscaras, CPF, CEP, IBGE, webcam, data de emissão) e `aluno.js` (stepper, toggles, validações, renda, idade, situação escolar, autocomplete de instituições).
- Arquivos antigos (`aluno_form.js`, `calcularIdade.js`, `situacao_escolar.js`, `novo.js`, `editar.js`, `historico.js`) preservados como `*OLD.js`.
- Corrigido listener `DOMContentLoaded` aninhado que impedia restaurar o estado do acompanhante quando o formulário voltava com erro do backend.
- Corrigido `SyntaxError` no `editar.html` (delimitadores Jinja inválidos `{ { ... } }`); handlers inline exportados em `window` (`toggleOutroAcompanhante`).
- `transferir.js` refatorado (versão anterior em `transferirOLD.js`).

### Unidade de cadastro obrigatória para usuário global (`dba5464`)

- Usuário global (sem unidade ativa) passa a escolher explicitamente a unidade de destino ao cadastrar aluno — select obrigatório no Step 1 de `novo.html`.
- Backend (`novo_aluno`) resolve a unidade em duas vias: contexto ativo ou `unidade_id` do formulário (validado); impede a criação de aluno órfão (`unidade_id=None`), que não aparecia em nenhuma listagem.
- `aluno.js`: validação do stepper agora considera campos `[required]` visíveis (o botão PRÓXIMO não é submit, então o HTML5 sozinho não bloqueava).

### Arquivos alterados nesta parte

| Arquivo | Natureza da mudança |
| --- | --- |
| `app/static/js/alunos/aluno.js`, `aluno_utils.js` | Novos (JS unificado) |
| `app/static/js/alunos/*OLD.js` | Versões antigas preservadas |
| `app/static/js/alunos/transferir.js`, `transferirOLD.js` | Refatorado + backup |
| `app/templates/alunos/novo.html`, `editar.html`, `historico.html` | Novo carregamento de scripts; select de unidade |
| `app/registros/alunos.py` | Unidade de cadastro obrigatória no `novo_aluno` |

---

### Alterações do dia — 27/09/2026

- Data da intervenção: 27/09/2026
- Commit: `d1217ea` — novos relatórios e combinações de dados (Central de BI) (01:45)

### Central de BI

- Novo módulo em camadas: `catalogo.py` (indicadores, dimensões e tipos de resultado — sem acesso a banco), `bi.py` (execução/despacho por código), `bi_alunos.py` (cálculos) e `bi_routes.py` (rotas).
- Rotas novas: `/relatorios/bi` (Central de BI), `/relatorios/bi/dados` (API JSON para gráfico dinâmico por dimensão), `/relatorios/bi/indicador/<codigo>` (JSON) e `/relatorios/bi/exportar` (placeholder 501, previsto com openpyxl).
- Indicadores implementados: ALU-001 a ALU-004, ALU-007 a ALU-010 e INS-001 a INS-005 (último: `bi_alunos.inscricoes_desativadas`). ALU-005 (sexo) e ALU-006 (faixa etária) estão no catálogo e mapeados nas dimensões, mas ainda sem função de cálculo.
- Nova tela `relatorios/bi.html` + `bi.css` e item "Central de BI" no menu de Relatórios.

### Cabeçalho e layout global

- `base.html`: badge de versão (`v{{ app_version }} · {{ app_stage }}`) e rodapé com versão — dependem de `app/version.py`, ainda não criado (referência registrada em comentário no template; renderizam vazio até então).
- Estados `active` nos itens do menu, correções de layout (body flex, footer, viewport) e `lang="pt-BR"`.
- Versão anterior do layout preservada em `baseOLD.html`.

### Preservação e documentação

- Pacote antigo de relatórios copiado para `app/relatoriosOLD/` (`alunos.py`, `conselho.py`, `geral.py`, `shared.py`) como backup; os arquivos originais seguem ativos em `app/relatorios/`.
- Novo `docs/relatorioMudanças/relatorios.md`: catálogo de indicadores (ALU, INS, FRE, TUR) e regra metodológica dimensão × métrica; Parte 2 prevista (pedagógico: aulas, avaliações, conselho, aprovação/evasão).
- `MER.md`: normalização de fim de linha (sem mudanças relevantes de conteúdo).

### Arquivos alterados nesta parte

| Arquivo | Natureza da mudança |
| --- | --- |
| `app/relatorios/catalogo.py`, `bi.py`, `bi_alunos.py`, `bi_routes.py` | Novos (motor BI) |
| `app/relatorios/__init__.py` | Registro do `bi_routes` |
| `app/templates/relatorios/bi.html`, `app/static/css/relatorios/bi.css` | Novos (Central de BI) |
| `app/templates/base.html`, `baseOLD.html` | Badge de versão, active states, layout + backup |
| `app/relatoriosOLD/**` | Backup do pacote antigo |
| `docs/relatorioMudanças/relatorios.md` | Novo (catálogo de indicadores) |
| `app/models/MER.md` | Normalização de fim de linha |

**### Alterações do dia — 28/09/2026**

* Data da intervenção: 28/09/2026

Sessão de continuidade do desenvolvimento da **Central de BI**, com foco na categoria **AUL — Aulas**. A implementação seguiu o padrão já estabelecido para ALU, INS, FRE e TUR, mantendo separação entre catálogo, execução e cálculos.

**### Central de BI — Indicadores de aulas**

Foram implementados e validados os indicadores **AUL-001 a AUL-005**:

| Indicador   | Descrição                  | Resultado validado |
| ----------- | -------------------------- | -----------------: |
| **AUL-001** | Total de aulas registradas |                 71 |
| **AUL-002** | Aulas por turma            |                 71 |
| **AUL-003** | Aulas por período          |                 71 |
| **AUL-004** | Aulas por professor        |                 71 |
| **AUL-005** | Aulas por curso            |                 71 |

**### AUL-001 — Total de aulas registradas**

* Criado o indicador no catálogo.
* Implementada a função `total_aulas_registradas()`.
* A consulta utiliza `RegistroAula` como origem.
* O vínculo com unidade acadêmica é realizado por `Turma.unidade_id`, pois `RegistroAula.unidade_id` possui registros nulos no conjunto de dados atual.
* Implementados filtros por unidade, período letivo, curso, turma, professor e intervalo de datas.
* Resultado geral validado: **71 aulas**.
* Filtros individuais validados com os dados existentes.

**### AUL-002 — Aulas por turma**

* Criado o indicador no catálogo.

* Implementada a função `aulas_por_turma()`.

* Agrupamento realizado por turma.

* Implementados filtros por unidade, período letivo, curso, turma, professor e intervalo de datas.

* Resultado validado:

  * `01 - Natação`: 19
  * `10 - Intermediário Dingue T1`: 22
  * `Fibra de vidro`: 10
  * `Mecânica de Popa`: 20

* Total: **71 aulas**.

* Validação catálogo × execução concluída.

**### AUL-003 — Aulas por período**

* Criado o indicador no catálogo.

* Implementada a função `aulas_por_periodo()`.

* Agrupamento realizado por `PeriodoLetivo`.

* Implementados filtros por unidade, período letivo, curso, turma, professor e intervalo de datas.

* Resultado validado:

  * `2026.1`: 71 aulas

* Validação catálogo × execução concluída.

**### AUL-004 — Aulas por professor**

* Criado o indicador no catálogo.

* Implementada a função `aulas_por_professor()`.

* Agrupamento realizado por professor (`User`).

* Durante a implementação foi corrigida a utilização do atributo do modelo `User`: o campo correto é `User.name`, e não `User.nome`.

* Implementados filtros por unidade, período letivo, curso, turma, professor e intervalo de datas.

* Resultado validado:

  * Arilton Novaes: 19
  * Daniel Bezerra: 22
  * Jaqueline Santuchi: 10
  * Luciano Campos: 20

* Total: **71 aulas**.

* Validação catálogo × execução concluída.

**### AUL-005 — Aulas por curso**

* Criado o indicador no catálogo.

* Implementada a função `aulas_por_curso()`.

* Agrupamento realizado por curso (`Curso`).

* Implementados filtros por unidade, período letivo, curso, turma, professor e intervalo de datas.

* Resultado validado:

  * Fibra de vidro: 10
  * Mecânica de Popa: 20
  * Natação: 19
  * Vela Dingue: 22

* Total: **71 aulas**.

* Validação catálogo × execução concluída.

**### Registro dos componentes alterados**

| Arquivo                            | Natureza da mudança                                                                           |
| ---------------------------------- | --------------------------------------------------------------------------------------------- |
| `app/relatorios/catalogo.py`       | Inclusão dos indicadores AUL-001 a AUL-005                                                    |
| `app/relatorios/bi_alunos.py`      | Implementação dos cálculos AUL-001 a AUL-005                                                  |
| `app/relatorios/bi.py`             | Registro dos indicadores AUL-001 a AUL-005 no despacho de execução                            |
| `app/relatorios/bi_routes.py`      | Ajuste da rota `/bi` para organizar indicadores por categoria e disponibilizá-los ao template |
| `app/templates/relatorios/bi.html` | Nova estrutura inicial para seleção e futura exibição dos indicadores                         |

**### Validações realizadas**

Foram realizados testes diretos das funções e testes através de `executar_indicador()`.

Foram validados, conforme aplicável:

* execução sem filtros;
* filtro por unidade;
* filtro por período letivo;
* filtro por curso;
* filtro por turma;
* filtro por professor;
* filtro por intervalo de datas;
* consistência entre catálogo e função executora.

Os cinco indicadores AUL implementados permanecem consistentes com os dados atualmente registrados no banco.

**### Estado ao final da sessão**

A categoria **AUL — Aulas** possui atualmente os indicadores **AUL-001 a AUL-005 implementados, registrados no catálogo, conectados ao mecanismo de execução e validados**.

A evolução da interface da Central de BI foi iniciada, porém sua implementação funcional foi deliberadamente deixada em espera para priorizar a conclusão dos indicadores AUL.
