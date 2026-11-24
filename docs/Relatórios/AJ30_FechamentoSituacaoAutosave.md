# AJ30 — Fechamento do conselho: situação final única, `NULL` e autosave por linha

**Data:** 24/11/2026 · **Branch:** `nova_feature` · **Migration:** `b8c9d0e1f2a3` (`down_revision = a7b8c9d0e1f2`)
**Head do código:** `b8c9d0e1f2a3` · **Banco principal local (24/11/2026):** `a7b8c9d0e1f2` (AJ22-C já aplicada); falta a AJ30.
**Postura:** mudança cirúrgica; sem commit/push/merge; **nenhuma migration aplicada ao banco principal**.

---

## 1. Objetivo

Fechar o conselho com um vocabulário único no banco e na tela, eliminando rótulos históricos e o fallback enganoso, sem alterar as regras de negócio que usam a situação para incluir/excluir alunos.

| Antes | Depois |
|---|---|
| 6 valores, com `Concluído`, `Participação`, `Reprovado por Falta` | 6 valores canônicos: `Aprovado`, `Participante`, `Reprovado por faltas`, `Desistente`, `Evadido`, `Empregado` |
| `Aprovado` como default visual/impresso quando vazio | "Não definido" na tela (`value=""` → `NULL`) e "—" na impressão |
| Botão "Salvar Fechamento" (lote inteiro) | Autosave da linha alterada, com indicador e retry |
| Nenhum aviso ao encerrar | Confirmação com "N aluno(s) sem situação final definida" |
| "Sem Registro" no resultado e fallback "Aprovado" na impressão | "Não definido" / "—" pela fonte única |

**Regra central:** "Não definido" **nunca é valor gravado**. É `situacao_final IS NULL`. Não existe linha `ConselhoClasse` criada só por abrir a página ou por escolher "Não definido" em aluno que ainda não tem conselho FINAL (AJ20 preservado).

---

## 2. Contagens read-only (antes da mudança)

Executado somente com `SELECT` nos dois bancos locais:

| Banco | Linhas em `conselho_classe` | `situacao_final` preenchido | Valores antigos |
|---|---:|---:|---|
| `pautaon` (principal) | 47 | 0 (100% `NULL`) | nenhum |
| `pautaon_ensaio` (scratch) | 5 | 0 (100% `NULL`) | nenhum |

SQL usado (reutilizável na produção):

```sql
SELECT COALESCE(situacao_final, '(NULL)') AS valor, COUNT(*) AS qtd
FROM conselho_classe
GROUP BY 1
ORDER BY 2 DESC, 1;
```

Consequência: nos bancos conferidos a migration é **somente DDL** (nenhum `UPDATE` efetivo), mas o código dela está preparado para os três renomes caso a produção apresente valores antigos.

---

## 3. Vocabulário e regras de mapeamento

Fonte única: `app/models/enums.py`.

```text
SituacaoFinal.APROVADO              = 'Aprovado'
SituacaoFinal.PARTICIPANTE          = 'Participante'
SituacaoFinal.REPROVADO_POR_FALTAS  = 'Reprovado por faltas'
SituacaoFinal.DESISTENTE            = 'Desistente'
SituacaoFinal.EVADIDO               = 'Evadido'
SituacaoFinal.EMPREGADO             = 'Empregado'
# aliases de NOME (não aparecem na iteração):
PARTICIPACAO -> 'Participante' · REPROVADO_POR_FALTA -> 'Reprovado por faltas'
```

| Valor antigo | Valor novo | Motivo |
|---|---|---|
| `Concluído` | `Aprovado` | Regra de negócio já existente: "Concluído vale como Aprovado" (ficha 360° e certificado). Fundir não muda quem recebe certificado; só remove o rótulo duplicado. |
| `Participação` | `Participante` | Padronização do substantivo; continua favorável para certificado/ficha. |
| `Reprovado por Falta` | `Reprovado por faltas` | Coralização gramatical; continua desfavorável. |
| `NULL` | `NULL` | Ausência não é valor: CHECK continua aceitando `NULL`. |
| `Empregado` | `Empregado` | Já era o valor canônico; **não existe no vocabulário antigo**, por isso o downgrade o recusa. |

`SITUACAO_FINAL_OPCOES` é a ordem do select; `SITUACOES_FINAIS_FAVORAVEIS = {Aprovado, Participante}` substitui os antigos conjuntos espalhados. `SITUACAO_FINAL_LEGADO` é o único mapa de renomeação (usado pela fronteira e replicado como *snapshot congelado* na migration — migrations não importam código da aplicação).

---

## 4. Inventário antigo × novo × motivo

| Arquivo:linha (antes) | Uso | Antes → Depois | Motivo |
|---|---|---|---|
| `app/models/enums.py:93-113` | enum | 6 valores antigos + 2 aliases → 6 canônicos + aliases de nome | Fonte única; aliases preservam código legado sem poluir a iteração. |
| `app/models/conselho.py:145-146` | docstring do campo | lista antiga → 6 valores + `NULL` = "Não definido" | Documentação do modelo. |
| `app/conselho.py:189-212` | `_normalizar_situacao_final` | aceitava só antigos → aceita novos, mapa legado e nomes do enum | Fronteira de escrita: normaliza antes da validação atômica; vazio → `NULL`. |
| `app/conselho.py:1177-1184,1272-1283` | `fechamento_turma` | sem opções → passa `SITUACAO_FINAL_OPCOES` e as constantes `SITUACAO_FINAL_INDEFINIDA`/`..._IMPRESSAO` | Select e impressão leem a mesma fonte única, inclusive os rótulos de ausência. |
| `app/conselho.py:1286-1511` | `salvar_fechamento_data` | lote `{"dados":[...]}` → uma linha no topo (legado ainda aceito) | Autosave; "Não definido" sem linha existente não cria `ConselhoClasse`. |
| `app/conselho.py:~500` (`index_conselho`) | painel | sem contagem → `pendencias_fechamento` em lote | Aviso antes de encerrar, sem N+1. |
| `app/templates/conselho/fechamento.html:176-196` | select | 6 `<option>` hardcoded, fallback `Aprovado` → option vazia "Não definido" + loop da fonte única, fallback `—` | Fim do default enganoso; nenhum valor antigo na tela. |
| `app/templates/conselho/fechamento.html:~95` | barra de ações | botão `salvarFechamento()` → frase discreta `text-muted small d-print-none` | Autosave; Imprimir/CSV/Voltar intactos. |
| `app/templates/conselho/fechamento.html:~150` | coluna Aluno | sem indicador → `.autosave-indicador` com `aria-live="polite"` | Status por linha sem mudar a ordem das colunas (AJ23/AJ26). |
| `app/static/js/conselho/conselho.js` | `tokenCsrf()` + `salvarFechamento()` | removidos; `confirmarEncerramento(event, N)` acrescentado | Salvamento virou módulo próprio; confirmação usa diálogo do navegador. |
| `app/static/js/conselho/autosave.js` | **novo** | funções puras + debounce/fila/DOM | Testável em node; nenhuma dependência nova. |
| `app/static/css/conselho/conselho.css` | **novo bloco** | estilos do indicador | Área reservada, cores e retry; `d-print-none`. |
| `app/templates/conselho/painel.html:174-188` | encerrar | POST direto → `onsubmit=confirmarEncerramento(...)` | Aviso antes do submit; permite encerrar mesmo assim. |
| `app/registros/periodos.py:558` | certificado | `{"Aprovado","Participação","Concluído"}` → `SITUACOES_FINAIS_FAVORAVEIS` | Mesma regra de inclusão, sem duplicar conjunto. |
| `app/relatorios/painel_pedagogico/ficha_aluno.py:77-82,431-443,704-712` | ficha 360° | conjunto local + `REPROVADO_POR_FALTA` → fonte única + `REPROVADO_POR_FALTAS` | Inclui/exclui os mesmos alunos. |
| `app/relatorios/bi_alunos.py:2871-2872` | BI faixa de renda | `"APROVADO" in str(sit).upper()` → comparação com `SituacaoFinal.APROVADO.value` | Equivalente, sem dependência de texto. |
| `app/relatorios/conselho.py:193-199,282,290-300` | resultado | `or "Sem Registro"` → `SITUACAO_FINAL_INDEFINIDA`; badges pela fonte única | Rótulo correto para `NULL`. |
| `app/templates/relatorios/resultado_conselho.html:277-290` | badges | mapa hardcoded com `REPROVADO_POR_FALTA`/`Sem Registro` → `situacao_badges` | Sem duplicação e sem rótulo enganoso. |
| `app/services/conselho_leitura.py:27-47` | leitura de casca | sem mudança | `NULL` já era tratado como ausente; compatível com AJ20. |
| `migrations/versions/b8c9d0e1f2a3_...py` | **nova** | CHECK antiga → transitória → final | Renomeação segura em PostgreSQL/SQLite. |
| `scripts/postgres_schema.sql:279` | snapshot DDL | mantido com CHECK antiga **de propósito** | Representa o schema pré-migração usado no ensaio; a migration é que o atualiza. |

**Não são situação final** e foram preservados: `auth.py:410` ("Acesso Aprovado"), `templates/conselho/painel.html:112` (badge do flag `conselho_concluido`), `templates/periodos/certificado.html:182` (ícone "Concluído"), `templates/turmas/carga_horaria_curso.html` ("Períodos Concluídos"), comentários históricos em `registros/periodos.py:533`.

---

## 5. Comportamento implementado

### 5.1 Fechamento e impressão

- `fechamento_turma` passa `situacoes_finais=SITUACAO_FINAL_OPCOES` e as constantes de ausência ao template. A primeira option é `<option value="">Não definido</option>`; as seis seguintes vêm da fonte única, na ordem.
- Nenhuma opção vem selecionada por padrão: sem `ConselhoClasse`, o navegador mantém a primeira (vazia). Não há `selected` fixo em `Aprovado`.
- Escolher "Não definido" envia `situacao: ""`, normalizado para `NULL`. Sem linha FINAL, a rota não chama `get_or_create_conselho`; com linha existente, limpa o campo e preserva histórico/respostas.
- Span de impressão mostra `item.conselho.situacao_final or situacao_indefinida_impressao` (`SITUACAO_FINAL_INDEFINIDA_IMPRESSAO = '—'`). O JS de sincronização (`conselho.js`) usa `textoImpressaoSituacao` da fonte única do autosave: ao escolher "Não definido", o span impresso mostra "—", nunca o rótulo da option.

### 5.2 Autosave por linha

- Removidos o botão "Salvar Fechamento", a função `salvarFechamento()` e o `alert` de sucesso. Permanecem **Imprimir**, **Exportar .CSV** e **Voltar**.
- Frase discreta: `As alterações são salvas automaticamente.` (`text-muted small d-print-none`).
- Eventos `change` nos três selects disparam o envio daquela linha:
  `POST /conselho/fechamento/<turma_id>/salvar` com
  `{"oferta_id", "aluno_id", "situacao", "proximo_curso_id", "proximo_nivel_id"}` e header `X-CSRFToken`.
- Servidor mantém a validação atômica: qualquer erro (situação inválida, curso inativo/de outra unidade, nível incompatível) faz rollback e retorna `{"success":false,"message":"..."}`; nada é alterado. Trocar curso sem nível limpa o nível no mesmo POST.
- Debounce de 300 ms; fila **por linha**: no máximo um envio em voo e um estado pendente; alterações seguidas valem o último estado; linhas diferentes nunca se bloqueiam.
- Indicador na coluna Aluno (área reservada, sem mudar colunas): `⟳ Salvando…` → `✓ Salvo` (some em ~2 s) → `⚠ Erro ao salvar`. A mensagem do servidor aparece em `title`/`aria-label` e o botão "tentar novamente" refaz o último payload. `role="status"`, `aria-live="polite"`, `aria-atomic="true"`, sem roubar foco.
- `beforeunload` avisa se há envio pendente ou erro não resolvido.

### 5.3 Encerrar conselho

- `index_conselho` calcula, em **duas consultas para todas as ofertas da página** (sem N+1), os pares `(oferta, aluno)` com inscrição ativa cujo conselho FINAL não tem `situacao_final` preenchido — inclui aluno sem linha.
- `painel.html` passa essa contagem a `confirmarEncerramento(event, N)` no `onsubmit` do formulário existente:
  - `N > 0`: "N aluno(s) sem situação final definida. Deseja encerrar o conselho mesmo assim?"
  - `N = 0`: confirmação padrão.
- O usuário **pode encerrar mesmo assim**. A rota `planejamento.alternar_conselho` e o flag `TurmaCurso.conselho_concluido` não foram alterados.
- **Comportamento de conselho encerrado preservado:** não foi criada restrição nova de edição no fechamento; a única trava no POST continua sendo a de perfil (professor recebe 403 em `/conselho/fechamento/.../salvar`). Documentar, não endurecer.

---

## 6. Testes

| Arquivo | Cobertura |
|---|---|
| `tests/test_aj30_situacao_final.py` | fonte única; select vazio e impressão "—"; POST de uma linha para cada um dos 6 valores; vazio → `NULL` sem criar linha; inválido com rollback preservando curso/nível; normalização legada; badges "Não definido"; aviso de encerramento em lote. |
| `tests/test_aj30_migration.py` | upgrade/downgrade em SQLite (CHECK transitória, 3 renomes, CHECK final, NULL, repetição segura), pré-checagem read-only abortando sem escrita, guarda `Empregado` listando `aluno_id`. |
| `tests/test_aj30_autosave_js.py` | funções puras em node (`criarFila`, `agendar`, `finalizar`, `payloadDaLinha`, `estadoIndicador`, `textoImpressaoSituacao`, `mensagemErro`, tempos 300/2000 ms); skip documentado se node ausente. |
| `tests/test_aj25_botoes_fechamento.py` | ajustado: botão Salvar ausente, frase de autosave presente, Imprimir/CSV/Voltar intactos. |
| `tests/test_conselho_ui.py` | select agora espera `[""] + SITUACAO_FINAL_OPCOES` e rejeita valores antigos. |
| `tests/test_aj20_conselho_lazy.py` | `test_t3c`: antes esperava 2 linhas FINAL (inclusive uma vazia); agora espera 1 — vazio não cria linha. |
| `tests/test_bi_oferta.py`, `tests/test_bi_indicadores.py` | semente `Reprovado por Falta` → `Reprovado por faltas`; a CHECK nova recusa o rótulo antigo. |
| `tests/test_conselho_oferta.py` | `test_fechar_salvar_situacao_invalida_recusa_tudo` usava `EMPREGADO` como "inválido"; com a AJ30 esse nome virou alias válido do enum, então o teste passou a usar `SITUACAO_INEXISTENTE` (a intenção — recusar valor desconhecido — permanece). |
| `tests/test_conselho_ui.py` | esclarecido que `EMPREGADO` não deve aparecer como rótulo de option (o canônico é `Empregado`); os três rótulos antigos continuam proibidos. |
| `tests/test_aj29_nome_pdf_js.py` | ajuste **não relacionado à AJ30**: o teste fixava `2026-11-23` no `{data}` e quebrava à mudança de dia; agora compara com `P.dataLocal()`. |

**Antigo × novo × motivo nos testes:** `['Aprovado','Reprovado por Falta',...,'Concluído']` → `[''] + 6 canônicos` (nova option de ausência); `salvarFechamento()` → frase/JS de autosave (botão removido); `"Sem Registro"` → `"Não definido"` (rótulo correto); migração sem testes → up/down em SQLite (segurança de deploy).

Verificação estática escopo AJ30: `ruff check` passou nos arquivos novos/diretamente da mudança (`tests/test_aj30_*.py`, `migrations/versions/b8c9d0e1f2a3_*.py`); `git diff --check` sem erros de whitespace. Avisos `ruff` preexistentes em arquivos de aplicação não foram "limpos" fora do escopo cirúrgico; o JS puro é validado pela suíte node acima.

Resultado da suíte completa (execução final, após todas as correções): **`2004 passed, 1239 warnings in 852.77s (0:14:12)`**, `EXIT=0` (SQLite, Python 3.14). Os 1239 avisos são preexistentes (SQLAlchemy `Query.get()`, `datetime.utcnow()`, reflexão de índice expressivo etc.), não regressões da AJ30. Conferição adicional: `52 passed` nos arquivos diretamente afetados (`test_conselho_oferta.py`, `test_conselho_ui.py`, `test_aj30_*.py`); node disponível, então os testes JS puro rodaram (não houve skip).

---

## 7. Migration — segurança e verificação

Arquivo: `migrations/versions/b8c9d0e1f2a3_aj30_situacao_final_vocabulario.py`.

1. `upgrade()` usa `op.get_bind()` e inspeção de schema; se a tabela não existe, retorna.
2. **Pré-checagem somente leitura:** `SELECT situacao_final, COUNT(*), MIN(id) ... WHERE situacao_final IS NOT NULL AND situacao_final NOT IN (...)`; qualquer valor fora do mapa antigo+novo aborta antes de qualquer DDL/DML, com valor, quantidade e primeiro id.
3. **CHECK transitória** com antigos + novos (necessária porque o PostgreSQL valida cada `UPDATE`; no SQLite o `batch_alter_table(recreate="always")` reconstrói a tabela).
4. Três `UPDATE` parametrizados.
5. **CHECK final** com os 6 valores canônicos e `NULL`.
6. Repetir `upgrade()` é seguro: a inspeção constata o estado final e não reescreve nada.
7. `downgrade()` recusa `Empregado` (lista `aluno_id`), aborta valores fora do mapa, aplica os renomes inversos e recria a CHECK antiga. **Perda documentada:** um `Aprovado` pré-AJ30 volta como `Concluído` (a migration não distingue o antigo `Concluído` do antigo `Aprovado`); por isso o downgrade é uma emergência, não um "desfazer" neutro.

Validação local: suíte de migração em SQLite (acima) + reflection da CHECK antes/depois. Nenhum banco principal foi alterado.

**Ensaio em PostgreSQL 18 (scratch `pautaon_ensaio`):** backup prévio `C:\Backups\pautaon\pautaon_ensaio_pre_AJ30_20261124_001607.dump` (228.402 bytes, `pg_dump -Fc` do PostgreSQL 18); o scratch estava em `c1d2e3f4a5b6` com 5 linhas `NULL` e a CHECK antiga, e recebeu a cadeia até `b8c9d0e1f2a3`. CHECK final refletida com exatamente os 6 valores canônicos + `NULL`; contagem inalterada (5 × `NULL`); colunas da AJ22 preservadas. Teste da guarda: ao gravar `Empregado` em uma linha, o downgrade abortou com `Downgrade AJ30 recusado: há 1 aluno(s) com situacao_final='Empregado' (ids: 1484) ...`; após limpar o valor, downgrade até `a7b8c9d0e1f2` recriou a CHECK antiga e o re-upgrade voltou ao head. Banco principal `pautaon` **intacto**.

---

## 8. Protocolo de deploy (PostgreSQL 18)

> **Não aplicar no banco principal sem backup e sem a conferência read-only.** O banco principal local está em `a7b8c9d0e1f2` (AJ22-C, 47 linhas `NULL`, CHECK antiga); o deploy precisa aplicar **somente a AJ30** (`b8c9d0e1f2a3`). Se outro ambiente ainda estiver em `1fdc7c03bdc2`, aplicar antes a AJ22-C, usando o mesmo backup.

### 8.1 Antes — conferência read-only

```powershell
$env:PGPASSWORD = '<senha do .env>'
$PSQL = 'C:\Program Files\PostgreSQL\18\bin\psql.exe'
$DSN  = 'postgresql://<usuario>@localhost:5432/pautaon'

#Estado atual do schema
& $PSQL $DSN -c 'SELECT version_num FROM alembic_version;'
& $PSQL $DSN -c "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = 'ck_conselho_situacao_final';"

#Contagem por valor (DEVE mostrar só '(NULL)' nos bancos conferidos)
& $PSQL $DSN -c @"
SELECT COALESCE(situacao_final, '(NULL)') AS valor, COUNT(*) AS qtd
FROM conselho_classe
GROUP BY 1
ORDER BY 2 DESC, 1;
"@
```

Se aparecer qualquer valor fora de
`Aprovado | Participante | Reprovado por faltas | Desistente | Evadido | Empregado | Concluído | Participação | Reprovado por Falta`,
**pare**: a migration vai abortar de propósito. Regularize o dado ou amplie o mapa com revisão.

### 8.2 Backup (pg_dump 18)

```powershell
$PGBACKUP = 'C:\Program Files\PostgreSQL\18\bin\pg_dump.exe'
$PASTA    = 'C:\Backups\pautaon'
$ARQ      = Join-Path $PASTA ("pautaon_pre_AJ30_{0}.dump" -f (Get-Date -Format 'yyyyMMdd_HHmmss'))
New-Item -ItemType Directory -Force -Path $PASTA | Out-Null
& $PGBACKUP $DSN -Fc -f $ARQ
if ($LASTEXITCODE -ne 0) { throw 'Backup falhou — NÃO aplicar a migration.' }
Get-Item $ARQ | Select-Object FullName, Length, LastWriteTime
```

### 8.3 Aplicar

```powershell
# na raiz do projeto, com o .env de produção
.\.venv\Scripts\python.exe -m flask db current
.\.venv\Scripts\python.exe -m flask db heads      # b8c9d0e1f2a3
.\.venv\Scripts\python.exe -m flask db upgrade b8c9d0e1f2a3
```

### 8.4 Verificar depois

```powershell
& $PSQL $DSN -c 'SELECT version_num FROM alembic_version;'   # b8c9d0e1f2a3
& $PSQL $DSN -c "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = 'ck_conselho_situacao_final';"
& $PSQL $DSN -c @"
SELECT COALESCE(situacao_final, '(NULL)') AS valor, COUNT(*) AS qtd
FROM conselho_classe
GROUP BY 1
ORDER BY 2 DESC, 1;
"@
```

Esperado: `NULL` continua presente; `Concluído`, `Participação` e `Reprovado por Falta` **não aparecem**; `Participante` e `Reprovado por faltas` aparecem apenas se existiam dados antigos. Conferir também na tela que a primeira opção é "Não definido" e que o indicador de autosave aparece ao alterar uma linha.

### 8.5 Downgrade (somente emergência)

```powershell
# Antes: não pode haver 'Empregado' — a migration recusa e lista os aluno_id
& $PSQL $DSN -c "SELECT aluno_id, id FROM conselho_classe WHERE situacao_final = 'Empregado' ORDER BY aluno_id;"

.\.venv\Scripts\python.exe -m flask db downgrade a7b8c9d0e1f2
```

Atenção: o downgrade **não consegue distinguir** um antigo `Concluído` de um antigo `Aprovado`; ele transforma todo `Aprovado` em `Concluído` e todo `Participante` em `Participação`, recriando a CHECK antiga.

### 8.6 Reversão pelo backup

Se o downgrade não for suficiente (ou a CHECK antiga não puder ser recriada), restaurar o dump do item 8.2 em ambiente de recuperação e validar antes de substituir o principal:

```powershell
$PGRESTORE = 'C:\Program Files\PostgreSQL\18\bin\pg_restore.exe'
& $PGRESTORE --clean --if-exists --no-owner --no-privileges -d $DSN $ARQ
```

Somente depois de conferir contagens e `alembic_version` no restaurado é que a operação de reversão é considerada concluída.

---

## 9. Ambiente e ensaio

- **SQLite:** suíte completa do pytest (banco de teste em memória/arquivo temporário) — sem tocar em arquivos do projeto.
- **PostgreSQL scratch `pautaon_ensaio`:** mesmo DSN do `.env` trocando apenas o database; backup prévio com o mesmo `pg_dump` 18; migration aplicada e revertida no scratch, nunca no `pautaon`.
- **Navegador real (Chromium do OpenCode, servidor Flask local com SQLite isolado):** select abre em "Não definido" seguido dos 6 valores canônicos; alterar situação/curso/nível gerou `⟳ Salvando… → ✓ Salvo` (some em ~2 s) e um único POST por linha com o payload `{oferta_id, aluno_id, situacao, proximo_curso_id, proximo_nivel_id}` (conferido no corpo da requisição, status 200); falha de rede simulada por `fetch` rejeitado mostrou `⚠ Erro ao salvar` com `title`/`aria-label` e botão "tentar novamente", que reenviou e salvou; após recarregar, os valores persistiram; escolher "Não definido" gravou `NULL` e o span de impressão passou a mostrar "—" (corrigido o JS de sincronização, que antes copiava o rótulo da option); ao encerrar, o diálogo exibiu "1 aluno(s) sem situação final definida. Deseja encerrar o conselho mesmo assim?", cancelar não submeteu e aceitar encerrou — e o fechamento continuou editável com conselho encerrado (nenhuma restrição nova).
- **Não tocados:** `aplicar_deploy.ps1`, `empacotar_deploy.ps1`, `deploy_pacotes/AJ29_20261123_2316/...` (cópia de deploy antiga), arquivos não rastreados pré-existentes.

---

## 10. Resumo de entrega

- 1 migration nova (`b8c9d0e1f2a3`), head do código atualizado em `app/models/MER.md` e `backlog_desenvolvimento.md`.
- Fonte única de vocabulário em `app/models/enums.py`; nenhuma lista/map duplicado em templates ou leitores.
- Autosave por linha com indicador acessível, retry e aviso de saída; sem botão de salvar em lote.
- Aviso de pendências antes de encerrar conselho, em lote, sem alterar o comportamento de conselho encerrado.
- Testes Python + JS + migration cobrindo o contrato; documentação e protocolo de deploy acima.

`git diff --stat` (arquivos rastreados; os arquivos novos da AJ30 estão listados logo abaixo por serem untracked):

```text
 app/conselho.py                                  | 103 ++++++++++++++++++-----
 app/models/MER.md                                |  25 +++---
 app/models/conselho.py                           |   5 +-
 app/models/enums.py                              |  68 +++++++++++++--
 app/registros/periodos.py                        |   5 +-
 app/relatorios/bi_alunos.py                      |   6 +-
 app/relatorios/conselho.py                       |   6 +-
 app/relatorios/painel_pedagogico/ficha_aluno.py  |  12 ++-
 app/static/css/conselho/conselho.css             |  34 ++++++++
 app/static/js/conselho/conselho.js               |  97 +++++----------------
 app/templates/conselho/fechamento.html           |  33 +++++---
 app/templates/conselho/painel.html               |   7 ++
 app/templates/relatorios/resultado_conselho.html |  18 ++--
 backlog_desenvolvimento.md                       |   6 ++
 tests/test_aj20_conselho_lazy.py                 |   9 +-
 tests/test_aj25_botoes_fechamento.py             |  20 ++---
 tests/test_aj29_nome_pdf_js.py                   |   7 +-
 tests/test_bi_indicadores.py                     |   2 +-
 tests/test_bi_oferta.py                          |   2 +-
 tests/test_conselho_oferta.py                    |   4 +-
 tests/test_conselho_ui.py                        |  12 ++-
 21 files changed, 311 insertions(+), 170 deletions(-)
```

Novos (untracked) desta entrega: `app/static/js/conselho/autosave.js`, `migrations/versions/b8c9d0e1f2a3_aj30_situacao_final_vocabulario.py`, `tests/test_aj30_autosave_js.py`, `tests/test_aj30_migration.py`, `tests/test_aj30_situacao_final.py`, `docs/Relatórios/AJ30_FechamentoSituacaoAutosave.md`. Permaneçam intocados os untracked pré-existentes `aplicar_deploy.ps1`, `empacotar_deploy.ps1` e `deploy_pacotes/`. Nenhum commit/push/merge foi feito.
