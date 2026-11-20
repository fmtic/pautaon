# AJ18-A — Enturmação com data de entrada do aluno na oferta (auditoria e desenho)

Data: 10/11/2026 · Branch `aj18-a-entrada-oferta` (base `nova_feature` @ `6f37402`) · **Somente leitura — nenhum código alterado**

Requisito: ao enturmar aluno **depois** do início da oferta, o sistema pergunta a
data de entrada do aluno na oferta — (1) hoje, (2) data específica dentro do
período real da oferta, (3) "desde o início" (já frequentava). Com vários alunos,
uma data por aluno. Aulas anteriores à entrada **não aparecem para ele** e **não
entram** em conceitos, faltas, frequência e demais contabilidades; o nome dele
segue na lista. Enturmações existentes = "desde o início" (sem mudança de
comportamento).

---

## 1) Modelo — onde guardar a data

### `Inscricao` — `app/models/matriculas.py:25`

Já existe `data_inicio` (`db.Date`, **NOT NULL**, default `get_local_now().date()`
— `:66-70`), usada hoje como "data da matrícula". **Não serve diretamente** para o
requisito:

- É NOT NULL e preenchida em **toda** inscrição existente → se virasse o corte de
  frequência, todas as enturmações antigas perderiam retroativamente as aulas
  anteriores à matrícula — viola "existentes = desde o início".
- Sua semântica hoje é registro/auditoria (e validação de transferência,
  `alunos.py:1346`), não regra de frequência — nenhum leitor de frequência a
  consulta (verificado: zero usos em `utils/frequencia.py`,
  `services/frequencia_oferta.py`, `services/turma_curso.py`, `registros/core.py`).

**Proposta (aditiva)**: nova coluna nullable, ex.:

```python
data_entrada_oferta = db.Column(db.Date, nullable=True)  # NULL = desde o início
```

- `NULL` = sem corte (comportamento atual para 100% das linhas existentes —
  migration **não precisa backfill**).
- Preenchida só quando a enturmação acontece **depois** do início efetivo da
  oferta **e** o operador escolhe data específica/hoje.
- `Inscricao.turma_curso_id` é **NOT NULL** desde a migration `c3d4e5f6a7b8`
  (confirmado em `_alunos_da_oferta`, `turma_curso.py:1110` e
  `enturmado.py:91`) — a "regra D2" citada no requisito refere-se às **linhas
  `Frequencia.turma_curso_id IS NULL`** (legado pré-Onda 4), que só entram em
  agregados quando a oferta é a única ativa da turma
  (`ofertas_unicas_ativas`, `frequencia_oferta.py:134`). Inscrições legadas com
  `turma_curso_id` NULL **não existem mais** no schema atual.
- **Transferência**: `transferir_aluno` (`alunos.py:~1290-1415`) já coleta
  `data_transferencia` (≥ início da oferta destino, `:1346-1353`) e a grava como
  `data_inicio` da nova `Inscricao` (`:1380`). A nova coluna pode nascer já
  preenchida com a data de transferência (o aluno não frequentava a oferta
  destino) — ver decisão D5 abaixo.

---

## 2) Pontos que criam/reativam inscrição

Somente **dois** pontos criam `Inscricao` no código (grep `Inscricao(` em
`app/`): `app/services/enturmacao.py:84` (função única `enturmar_aluno`) chamada
por:

| # | Rota/fluxo | Arquivo:linha | UI hoje | Onde entra a pergunta |
|---|---|---|---|---|
| 1 | **Enturmar em lote** `POST /turma/enturmar/<id>` | `turmas.py:1617-1707` | Modal "enturmar" na `ver_turma` (`modal=enturmar`, `:1612`); por aluno já existe campo `nivel_{aluno.id}` (`:1671`) | Adicionar `entrada_{aluno.id}` por aluno (date input ou select 3 opções), só renderizado quando `oferta.data_inicio` efetiva < hoje. O GET da turma (`:~1590`) já calcula `ofertas`/`oferta_sel` — expor `entrada_obrigatoria = hoje > inicio_efetivo(oferta_sel)` |
| 2 | **Transferência** `POST .../transferir_aluno` | `alunos.py:~1290-1415` | Já tem `data_transferencia` (date) | Ver D5: default = data de transferência; pergunta extra só se o requisito quiser "desde o início" também aqui |

**Não há outros criadores**: importação (não há importador de alunos→oferta que
crie `Inscricao`), seed/bootstrap (`services/bootstrap.py` não toca em
`Inscricao`), reativação de lixeira (é de **Turma**, `turmas.py:1105` — não
recria inscrição), e **desenturmar não reativa**: `desenturmar_alunos`
(`alunos.py:910-1000`) faz soft-delete (`ativo=False`, motivo
`DESENTURMADO`/`TRANSFERENCIA`) quando há frequência, ou **hard delete** quando
não há — re-enturmação sempre passa por `enturmar_aluno` e cria linha **nova**
(a antiga fica inativa). Logo a "pergunta" cobre reingresso automaticamente.

**Regra de exibição**: só perguntar quando `hoje > início_efetivo` da oferta
(`oferta.data_inicio or turma.data_inicio`, `datas_aula_oferta` já resolve
herança — `turma_curso.py:1146-1150`). Oferta que ainda não começou → todos
"desde o início" (NULL), sem UI extra.

---

## 3) Leitores — como cada um decide hoje as aulas válidas do aluno

**Fato central**: hoje **nenhum** leitor considera `Inscricao.data_inicio` —
a "validação" é apenas `Inscricao.ativo=True` + `Aluno.ativo=True`. Um aluno
enturmado hoje "deve" frequenciar retroativamente todas as aulas já lançadas da
oferta.

### 3a) Lançamento (escrita)

- **GET `/frequencia`** (`core.py:223`+): pauta = `_alunos_da_oferta`
  (`turma_curso.py:1100`, EXISTS em `Inscricao.ativo` por oferta); seletor de
  datas = `datas_aula_oferta(oferta)` (calendário **inteiro** da oferta, sem
  piso por aluno); estatísticas por aluno = `conceitos_frequencia_por_aluno`
  (`frequencia_oferta.py:506`) — conta **todas** as linhas `Frequencia` do
  aluno na turma/oferta; `situacao_datas_oferta` (`utils/frequencia.py:183`)
  marca aula "pendente" quando `lançados < len(pauta)`.
- **POST `/frequencia`** (`core.py:234-402`): filtra campos `aluno_*` pela pauta
  (`permitidos`, `:370-396`); `salvar_frequencia` (`logica.py:653`) monta
  `alunos_post` por JOIN `Inscricao.ativo` (`:724-732`) e `_planejar_frequencia`
  (`:621`) faz upsert por aluno — **sem nenhuma checagem de data de entrada**:
  hoje o professor **pode** lançar conceito para o aluno em aula anterior à
  entrada dele, e o sistema grava.

### 3b) Contagens/expectativas (denominadores)

- `situacao_datas_oferta` (`utils/frequencia.py:183-286`): "completa" =
  `count(distinct aluno_id lançado) >= len(pauta)` — denominador fixo = pauta
  inteira.
- `contar_pendencias_frequencia` / `_pendencias_por_ofertas`
  (`utils/frequencia.py:106-180`): mesma lógica por oferta — pendente quando
  `lancados < len(aluno_ids)`.
- `estatisticas_professor.py:71-130,318-333` (`cobertura_pauta`,
  `aulas_esperadas` via `datas_esperadas_oferta`): aulas esperadas = calendário
  da oferta, alunos = pauta inteira.

### 3c) Percentuais/agregados (leitores de linhas gravadas)

Todos consomem `agregar_por_turma`/`agregar_por_oferta`
(`services/frequencia_oferta.py:181+`) ou consultas diretas a `Frequencia` —
**nenhum filtra por data de entrada**:

| Leitor | Arquivo:linha | O que conta |
|---|---|---|
| `Turma.freq_geral` / `freq_geral_oferta` | `models/academico.py` → `frequencia_oferta.py` | % global por turma/oferta (presentes/(presentes+faltas)) |
| Filtro `min_freq` da lista de turmas | `registros/turmas.py:637-700` | `pct_turma` agregado |
| Painel pedagógico turma/período/ficha | `relatorios/painel_pedagogico/{turma,periodo,ficha_aluno,frequencia}.py` | `por_aluno` (lista data+conceito), `%` por aluno, faixas, quebra semanal (`semanal()` usa as mesmas linhas) |
| Histórico do aluno | `registros/alunos.py:1056-1176` → `frequencias_aluno_por_inscricao` (`frequencia_oferta.py:419`) | totais por inscrição (presenças/faltas/J/%) |
| Dashboard professor / secretaria | `main/dashboard_professor.py:60-263`, `main/secretaria.py`, `services/estatisticas_professor.py` | pendências, cobertura de pauta, contagens por oferta |
| GET `/frequencia` stats | `core.py:~598` → `conceitos_frequencia_por_aluno` | % exibido por aluno na tela de lançamento |
| Relatório/datas lançadas | `core.py:739` `frequencia_relatorio` → `relatorio.html` | lista data+conceitos lançados |
| Pauta impressa | `core.py:689` `pode_imprimir_pauta` → template de impressão | lista alunos da oferta |
| BI ALU/TUR/CRU | `relatorios/bi_alunos.py:54-140` (`_base_frequencia`, `_totais_por_aluno`) e métricas de inscrição (`inscricoes_*`, `:817-1050`) | contagens de linhas `Frequencia` por oferta/curso/turma + contagens de `Inscricao` |
| Conselho | `conselho.py` (refs `:708-710,856-858,1085+`), `relatorios/conselho.py`, `services/conselho_leitura.py` | consome agregados de frequência/ofertas |
| Certificado/engajamento | `models/certificado.py`, `services/certificado_modelo.py`, `services/engajamento*` | consomem os mesmos agregados/`por_aluno` |

Ponto-chave: os agregados (`agregar_*`) fazem `GROUP BY aluno_id, conceito` em
`Frequencia` **sem join em `Inscricao`** — uma linha gravada antes da entrada
entraria no percentual do aluno. O bloqueio na **escrita** (§4) impede linhas
novas; linhas **já existentes** (lançadas antes da enturmação ou por bug) só são
excluídas se os leitores filtrarem por data.

---

## 4) Proposta — função única e plano de migração

### Função única proposta

```python
# app/services/enturmacao.py (ou novo app/services/entrada_oferta.py)

def data_entrada_efetiva(inscricao) -> date | None:
    """Piso de frequência do aluno na oferta.
    None = sem corte (desde o início)."""
    return inscricao.data_entrada_oferta  # NULL -> None

def aula_conta_para_aluno(inscricao, data: date) -> bool:
    """A aula `data` entra nas contabilidades do aluno nesta inscrição?"""
    entrada = data_entrada_efetiva(inscricao)
    return entrada is None or data >= entrada

def datas_esperadas_do_aluno(inscricao, oferta, *, limite=None, blocked=None) -> list[date]:
    """Calendário da oferta cortado no piso do aluno (para denominadores:
    pendências, cobertura de pauta, % de 'aulas esperadas')."""
    datas = datas_aula_oferta(oferta, limite=limite, blocked=blocked)
    entrada = data_entrada_efetiva(inscricao)
    return [d for d in datas if entrada is None or d >= entrada] if entrada else datas
```

Dois usos distintos, ambos cobertos:

1. **Expectativa/denominador** (o que o aluno *deveria* ter):
   `datas_esperadas_do_aluno` alimenta `situacao_datas_oferta`,
   `_pendencias_por_ofertas`, `estatisticas_professor` — hoje comparam
   `lançados < len(pauta)`; passam a comparar por data:
   `lançados_na_data >= #{alunos com entrada <= data}`.
2. **Leitura de lançamentos** (o que foi gravado): agregados precisam excluir
   linhas `Frequencia.data < entrada`. Como `agregar_*` não faz join com
   `Inscricao`, a migração é por **join adicional**:
   `Frequencia ⋈ Inscricao ON (aluno_id, turma_curso_id)` +
   `Frequencia.data >= coalesce(inscricao.data_entrada_oferta, date.min)` —
   com cuidado na regra D2 (linhas `turma_curso_id IS NULL` não têm inscrição
   correspondente → permanecem "desde o início", coerente com legado).

   Alternativa mais barata (recomendada como primeira etapa): **bloquear na
   escrita** (POST nunca grava antes da entrada) + **não** filtrar agregados —
   linhas pré-existentes continuam contadas. É a opção que preserva 100% dos
   números atuais e atende o requisito na prática, porque após o bloqueio não
   nascem linhas fora da janela. A filtragem na leitura vira etapa posterior se
   o requisito exigir excluir também o histórico já gravado (ver D4).

### Plano de migração dos leitores (etapas)

- **AJ18-B — modelo + enturmação**: coluna + migration aditiva; parâmetro
  `data_entrada` em `enturmar_aluno`; coleta por aluno nas rotas
  `enturmar_alunos` (batch, `entrada_{id}`) e `transferir_aluno`; validações de
  §5.
- **AJ18-C — escritores**: em `core.py` POST `/frequencia`, remover do form os
  campos `aluno_*` cujo `data_entrada_oferta > data_alvo` (mesmo padrão do
  filtro `permitidos` de `:370-396`); em `salvar_frequencia`, ignorar conceitos
  de alunos cuja entrada é posterior à data (defesa em profundidade).
- **AJ18-C2 — denominadores**: `situacao_datas_oferta`,
  `_pendencias_por_ofertas`, `estatisticas_professor.cobertura_pauta` passam a
  usar `datas_esperadas_do_aluno`/contagem por data.
- **AJ18-C3 — agregados (opcional/decisão D4)**: join `Inscricao` em
  `agregar_por_turma`/`agregar_por_oferta`/`frequencias_aluno_por_inscricao`/
  `conceitos_frequencia_por_aluno`/`_base_frequencia` (BI).
- **AJ18-D — UI**: modal de enturmação com data por aluno; indicação visual na
  pauta/lancamento (badge "entra em dd/mm" ou exclusão da grade de lançamento
  para datas anteriores — decisão D6).

---

## 5) Validações propostas

- **Janela**: `entrada` ∈ `[início_efetivo_oferta, fim_efetivo_oferta]` —
  `oferta.data_inicio or turma.data_inicio` até `oferta.data_fim or
  turma.data_fim` (mesma herança de `datas_aula_oferta`, `turma_curso.py:1146`).
  Fora → erro/flash, sem gravar.
- **Dia de aula?**: recomendo **não exigir** que a entrada caia em dia de grade —
  o aluno pode entrar numa quarta e a primeira aula dele ser sexta; o corte é
  por data, não por "aula marcada". (Alternativa: aceitar qualquer data da
  janela — mais simples e previsível.)
- **Data futura**: recomendo **permitir** (aluno pré-matriculado com entrada
  agendada) — o corte simplesmente começa a valer na data. Se preferirem
  restringir a `<= hoje`, é uma linha a mais na validação. **Decisão do usuário.**
- **Frequência pré-existente**: se já houver linhas `Frequencia` do aluno em
  datas `< nova_entrada` (ex.: correção retroativa de enturmação), opções:
  (a) ignorar/contar mesmo assim (simples); (b) bloqueiar a gravação da entrada
  com aviso "existem N lançamentos anteriores"; (c) apagar/mover as linhas
  (destrutivo — não recomendo sem confirmação). **Decisão do usuário** — sugiro
  (a) na v1 com log, pois o caso é raro.
- **Edição posterior da data de entrada**: hoje **não existe** rota de edição
  de `Inscricao` (só criar/desenturmar/transferir). Se for criada, revalidar a
  janela e decidir se retroceder a entrada "reabre" aulas já fechadas —
  recomendo permitir com revalidação simples e sem tocar em `Frequencia`
  gravada (mesma política do item anterior).
- **"Desde o início"** = gravar `NULL` explicitamente (não a data do início da
  oferta) — mantém a distinção "sem corte" vs "corte coincidente".

---

## 6) Riscos, estimativa e testes

### Riscos

1. **Números históricos**: sem filtro na leitura (opção barata do §4), totais de
   turmas com alunos "entrada tardia" ficam levemente diferentes do ideal —
   ex.: `%` do aluno inclui só o que foi gravado (correto na prática, pois a
   escrita bloqueia), mas `por_aluno` no painel pedagógico ainda lista linhas
   pré-entrada se existirem.
2. **Denominador por data**: `situacao_datas_oferta`/pendências hoje usam
   `len(pauta)` fixo; com entrada por aluno o denominador **varia por data** —
   mudança de semântica que afeta dashboards de pendência (uma turma com
   enturmação tardia parecerá "mais pendente" em datas antigas se não for
   tratada — ou "menos", dependendo da direção do ajuste).
3. **Regra D2 (legado `turma_curso_id IS NULL`)**: linhas sem oferta não têm
   inscrição correspondente — ficam "desde o início" por construção; documentar
   que o corte só se aplica a lançamentos por oferta.
4. **Transferência**: aluno transferido no meio da oferta destino — definir se
   `data_entrada_oferta = data_transferencia` sempre (recomendado) ou se a
   pergunta se aplica.
5. **Re-enturmação**: desenturmação com histórico gera nova `Inscricao` — a
   data de entrada é por **inscrição**, não por aluno; dois períodos na mesma
   oferta têm cortes independentes (correto, mas deve constar no relatório).
6. **Performance**: denominadores por data exigem carregar `(aluno_id,
   entrada)` da pauta — volume pequeno (dezenas por oferta), sem risco.

### Estimativa de etapas

- **AJ18-B** (modelo + enturmação + validações): migration + coluna, parâmetro
  no serviço, coleta nos 2 formulários, testes de rota. *Médio* — o serviço
  único (`enturmar_aluno`) concentra a mudança.
- **AJ18-C** (escritores + denominadores): filtro na rota POST e em
  `salvar_frequencia`; ajuste de `situacao_datas_oferta`/pendências/
  `estatisticas_professor`. *Médio* — vários pontos, mas todos com padrão
  já existente (`permitidos`).
- **AJ18-C3** (agregados, se aprovado): join `Inscricao` em 4-5 funções de
  `frequencia_oferta.py` + BI. *Maior* — toca a fonte única de todos os %.
- **AJ18-D** (UI): modal por aluno, badge na pauta, testes de template.
  *Pequeno-médio*.

### Lista de testes sugerida

- Modelo/migration: coluna NULL default; inscrição antiga permanece NULL.
- `enturmar_aluno`: aceita `data_entrada` válida; rejeita fora da janela;
  transferência grava entrada = data_transferência.
- POST `/frequencia`: aluno com entrada > data_alvo tem `aluno_*` ignorado
  (log + não grava `Frequencia`); entrada <= data grava normal.
- GET `/frequencia`: aluno aparece na pauta independente da entrada (nome na
  lista); stats não contam linhas pré-entrada (se C3).
- `situacao_datas_oferta`/pendências: aula anterior à entrada do único aluno
  pendente não conta como pendente por causa dele.
- Regressão: turma sem nenhuma entrada preenchida → números idênticos aos
  atuais (snapshot de % e pendências).

---

## Decisões que dependem do usuário

- **D1 — Coluna**: confirmar `Inscricao.data_entrada_oferta` nullable (NULL =
  desde o início) em vez de reaproveitar `data_inicio` (recomendado: sim —
  `data_inicio` é NOT NULL e já povoada, mudaria retroativamente o
  comportamento).
- **D2 — Janela**: entrada deve estar dentro de `[início, fim]` efetivos da
  oferta? E pode ser futura? (recomendo: sim à janela; futura permitida).
- **D3 — Entrada precisa cair em dia de aula?** (recomendo: não).
- **D4 — Linhas já gravadas antes da entrada**: (a) ignorar — escrita bloqueia
  só daqui pra frente [recomendado v1]; (b) bloquear a enturmação se houver
  lançamentos anteriores; (c) excluir da leitura via join em `Inscricao`
  (mais fiel, mais caro — vira AJ18-C3 obrigatório).
- **D5 — Transferência**: entrada = data de transferência automaticamente, ou
  a mesma pergunta de 3 opções? (recomendado: automático = transferência).
- **D6 — UI na pauta/lancamento**: aluno com entrada futura/tardia aparece na
  lista mas **não** no formulário de lançamento para datas anteriores (recomendo
  sim — evita envio ignorado), ou aparece desabilitado com indicação visual?
- **D7 — Edição da data de entrada**: criar rota de edição agora ou deixar
  para depois? (recomendo: depois — não existe hoje).
