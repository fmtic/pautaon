# ETAPA B1 — 3 defeitos de produção corrigidos e concomitância alinhada ao MER

Data: 25/10/2026 · Ramo: `Onda4` · Escopo alterado: `app/registros/turmas.py`, `app/templates/turmas/nova_turma.html`, `app/templates/turmas/editar.html`, `tests/test_turma_curso_fase3.py`, `tests/test_filtros_turmas.py` · **Nenhum commit foi feito.**

> Nome do formulário de nova turma: o enunciado cita `app/templates/turmas/nova.html`; o arquivo real em uso pela rota `registros.nova_turma` é **`app/templates/turmas/nova_turma.html`** (`render_template` em `turmas.py:881`). Foi esse que editei.

---

## 1. Leitura prévia (o que foi consultado antes de mexer)

- `docs/T1_relatorio.md` §4.1 (KeyError do ano corrente), §4.2 (concomitância deixou de bloquear), §4.3 (editar_turma descarta programa), §4.4 (/turma/nova sem programa), §5 (decisões), §6 (P1–P9).
- `app/registros/turmas.py`: listagem `turma()` (L402-491 — forzamento de `ano_periodo`, `periodos_por_ano`, badges), `nova_turma()` (L700-884), `editar_turma()` (L1109-1395 — ramos `n_ativas >= 2` e `0/1 oferta`).
- `app/services/turma_curso.py`: `_conflitos_horario_concomitante` (L114-164 — devolve **lista de mensagens**, texto "Horário concomitante com '…'. A oferta foi salva."), `adicionar_oferta` (L311-400 — anexa `oferta.avisos_horario`), `editar_oferta` (L403-451 — idem), `criar_oferta_inicial_da_turma` (L255-308 — exige `turma.programa`), `sincronizar_programa_turma` (L243-252), `_sincronizar_legado` (L221-240).
- `app/models/MER.md` §8.10: L969 (concomitância **permitida**, com aviso), L972 (`Turma.programa` é projeção da oferta principal ativa, "não é editável como dado independente"), L979 (edição com 2+ ofertas grava "apenas nome, período e ordenação"; o programa é derivado), L980 (tela G3: campos somente leitura com aviso), L985 (selects de nome/professor listam a unidade toda independentemente do filtro), L986 (a listagem abre no ano atual).
- `app/templates/turmas/nova_turma.html` (88 linhas), `editar.html` (L71-114 — alerta `n_ofertas >= 2`, bloco do programa, curso), `ofertas.html` (L141-147 e L268-273 — a lista de programas usada na tela de oferta), `listar.html` (L18-42 — badges de ano/período), `app/static/js/turmas/nova.js` (todo protegido contra elementos ausentes; não exige mudança).

---

## 2. Defeito P2 — `KeyError` no ano corrente → 500 em `/turma`

**Causa (confirmada):** `periodos_por_ano` só recebe chaves dos anos de `data_inicio` dos períodos existentes (L440-443), enquanto `anos_periodos = [ano_atual]` é incondicional (L444). O laço `for periodo in periodos_por_ano[ano]:` (L476) arrebentava quando a unidade não tinha período começando no ano corrente.

**Correção:** `periodos_por_ano.get(ano, [])` — o ano corrente continua entrando em `anos_periodos` (e portanto na badge/etiqueta visual e no `ano_selecionado`), apenas sem períodos debaixo. Uma linha; nenhum outro comportamento tocado.

```python
# app/registros/turmas.py, dentro de for idx, ano in enumerate(anos_periodos):
        # O ano corrente é sempre oferecido como etiqueta visual; quando a
        # unidade ainda não cadastrou período nele, `periodos_por_ano` não tem
        # a chave — daí o .get() (defeito P2: KeyError → 500 na virada de ano).
        for periodo in periodos_por_ano.get(ano, []):
```

**Guarda automatizada criada:** `tests/test_filtros_turmas.py::test_rota_listagem_sem_periodo_no_ano_corrente_nao_quebra` — semente com período **somente no ano anterior** e uma turma sem período; exige `200`, exige `ano_periodo=<ano_corrente>` no HTML (a opção visual sobrevive) e exige que a turma sem vínculo não apareça como linha. Sem essa semente, nenhum teste cobria o ramo do KeyError depois do alinhamento da listagem (§9, decisões 1 e 2).

---

## 3. Defeito P3 — `/turma/nova` com curso nunca salvava a turma

**Causa (confirmada):** `Turma(programa=None)` (L804, antes) e a rota não lia `programa` do formulário; logo `criar_oferta_inicial_da_turma(nova)` (L824→`turma_curso.py:284`) levantava `ValueError("Toda oferta precisa ter um programa.")`, o `except` fazia rollback e o usuário só via "Não foi possível salvar a turma."

**Correção (3 pontos):**

1. **Coleta + exigência** (`nova_turma`, L809-814): `programa = (request.form.get("programa") or "").strip() or None`; se houver `curso_id` e não houver programa → `flash("Selecione o programa da oferta.", "warning")` + redirect. A checagem vem **depois** da validação do curso (para não trocar uma mensagem específica — "curso inativo/da outra unidade" — por uma genérica) e **antes** do `Turma(...)`, convertendo o erro silencioso em orientação.
2. **Gravação antes da oferta** (L816-819): `programa=programa if curso_id is not None else None`. `criar_oferta_inicial_da_turma` copia `turma.programa` para a oferta e chama `sincronizar_programa_turma`, então o estado final já é a projeção consistente do MER.
3. **Turma sem curso mantém o comportamento atual**: `programa` continua `NULL` (sem oferta, não há de que projetar) mesmo que o navegador envie o campo.

**Template `nova_turma.html`:** adicionada a "Linha 2: Programa da oferta inicial" — `<select name="programa">` com as mesmas opções da tela de oferta (`Profissionalizante`, `Esporte`, `Meio Ambiente`, `Outros`), placeholder "-- Selecione o Programa --" e `form-text` explicando que é exigido quando a turma nasce com curso e que, sem curso, o programa se define na primeira oferta. **Não marquei `required`** porque a tela simplificada não coleta curso (ver §10, pendência D1).

**Fonte única da lista:** criado `_PROGRAMAS_OFERTA` (`turmas.py:170`, ao lado de `_PALETA_BADGES_ANO`) e passado `programas=list(_PROGRAMAS_OFERTA)` nos dois `render_template` de turma que precisam da lista (`nova_turma` e `editar_turma`, este último tinha a lista literal inline na L1106). `ofertas.html` continua com a lista embutida — fora do escopo autorizado.

---

## 4. Defeito P4 — `editar_turma` com 2+ ofertas e a projeção do programa

**MER §8.10 L972/L979:** `Turma.programa` é projeção da oferta principal ativa; no ramo multi-oferta o servidor grava só nome, período e ordenação e "o programa é derivado da oferta principal e não é editado no cadastro da turma".

**Correção no ramo `n_ativas >= 2`** (L1226-1229, antes do `db.session.commit()`):

```python
                # Turma.programa é projeção da oferta principal ativa (MER
                # §8.10) e não é editável de forma independente: reprojeta em
                # vez de ler o campo do formulário (defeito P4).
                sincronizar_programa_turma(turma_obj)
```

Nada de `request.form.get("programa")` nesse ramo — o campo do formulário continua sendo descartado, como antes; o que faltava era a **reprojeção**, que conserta drift (ex.: `Turma.programa` NULL ou velho em turma multi-oferta, que quebrava o filtro `Turma.programa == programa` da listagem, `turmas.py:305`).

**Template `editar.html`:** o campo já era `readonly` e **não tinha `name`** (não havia o que forjar). O que faltava era o aviso do caso multi-oferta:

- no alerta `{% if n_ofertas >= 2 %}`, a frase passou a listar também o **programa** ("edite professor, turno, horários, datas e o **programa** em CURSOS DA TURMA");
- no bloco do programa, `{% if n_ofertas >= 2 %}` acrescenta `tabindex="-1"` (coerência com os outros campos travados da tela) e `form-text` com cadeado: "Somente leitura: com mais de um curso, edite o programa na oferta, em **Cursos da Turma**."; sem 2+ ofertas o texto original ("O programa é definido nos dados da oferta principal.") permanece.

---

## 5. Concomitância (P1 do T1) — 4 testes realinhados ao MER

`tests/test_turma_curso_fase3.py`: os 4 testes que exigiam bloqueio foram reescritos para a regra vigente (MER §8.10 L969: **grava + aviso**) e renomeados; o docstring do módulo passou a declarar a regra correta (antes dizia "cursos da mesma turma **não podem** ter aulas no mesmo dia e horário").

| Antes | Depois | O que afirma agora |
|---|---|---|
| `test_adicionar_oferta_sobreposicao_total_bloqueada` | `test_adicionar_oferta_sobreposicao_total_com_aviso` | `o2.id is not None`, **2 ofertas ativas** no banco, `o2.avisos_horario` não vazio, todos os avisos contêm "concomitante", o primeiro menciona o curso "Carpintaria"; e `o1.avisos_horario == []` |
| `test_adicionar_oferta_sobreposicao_parcial_bloqueada` | `test_adicionar_oferta_sobreposicao_parcial_com_aviso` | idem para sobreposição parcial (Segunda 08–12 × Segunda 10–14) |
| `test_editar_oferta_cria_conflito_bloqueado` | `test_editar_oferta_cria_conflito_com_aviso` | criação das duas ofertas sem aviso (`o1/o2.avisos_horario == []`), edição para "Segunda" **persiste** (`o2.dias_semana == "Segunda"`), `o2.avisos_horario` com "concomitante", 2 ofertas ativas |
| `test_rota_oferta_nova_conflito_rejeitada` | `test_rota_oferta_nova_conflito_com_aviso` | `POST /turma/<id>/ofertas/nova` → 200 (follow_redirects), "concomitante" no HTML (**flash** emitido por `turmas.py:1579-1580`), e **`ativas == 2`** (a oferta foi gravada) |

Nenhuma asserção foi enfraquecida além do necessário: onde antes se esperava `ValueError`, agora se espera o par *gravado + aviso produzido*, usando a API real (`oferta.avisos_horario` na camada de serviço, `flash` na rota). Os demais testes do arquivo (adjacência, dias diferentes, vigência disjunta, sem horário, remoção de conflito) ficaram intactos.

**Consequência registrada:** com essa decisão, não existe mais guarda automatizada contra oferta sobreposta além da verificação de que **o aviso é emitido**. Isso é coerente com o MER, mas significa que sobreposição total é gravável — ver §10, pendência D2.

---

## 6. Diff por arquivo

Legenda: **+n/−n** = linhas do diff do arquivo (somente o que mudei nesta etapa).

1. **`app/registros/turmas.py` (+24/−4)** — 4 blocos:
   - L170: constante `_PROGRAMAS_OFERTA` (mesma lista da tela de oferta) + comentário ligando ao MER §8.10.
   - L476-479 (P2): `periodos_por_ano[ano]` → `.get(ano, [])` com comentário.
   - L809-819 (P3): coleta/validação de `programa`, grava condicional em `Turma(...)`.
   - L879 e L886: `programas=list(_PROGRAMAS_OFERTA)` no `render_template` de `nova_turma.html`.
   - L1123 (higiene): `programas` de `editar_turma` passa a usar a constante (mesmo valor de antes, lista literal removida).
   - L1226-1229 (P4): `sincronizar_programa_turma(turma_obj)` no ramo `n_ativas >= 2`, antes do commit.
2. **`app/templates/turmas/nova_turma.html` (+16/−0)** — bloco "Linha 2: Programa da oferta inicial" (`<select name="programa">` iterando `programas`, placeholder, `form-text`).
3. **`app/templates/turmas/editar.html` (+9/−2)** — alerta 2+ ofertas menciona o programa; bloco do programa com `tabindex="-1"` e aviso de cadeado no caso 2+, texto original preservado nos outros casos.
4. **`tests/test_turma_curso_fase3.py` (+62/−45)** — docstring do módulo + os 4 testes de §5 (renomeados e reescritos).
5. **`tests/test_filtros_turmas.py` (+90/−5)** — 3 mudanças de semente/marcador e 1 teste novo, explicados em §9 (decisões 1 a 3):
   - imports: `date`, `PeriodoLetivo`, `get_local_now`;
   - helper `_linha(body, turma_id)` (mesmo padrão de `test_turma_curso_lista.py`, T1 §3.14);
   - `_criar_turmas()`: período letivo do **ano corrente** (`data_inicio=15/01`, `data_fim=15/12`) e as 3 turmas vinculadas a ele;
   - `test_rota_listagem_aplica_filtro_nome`: asserções de substring global → `_linha(...)`;
   - **novo** `test_rota_listagem_sem_periodo_no_ano_corrente_nao_quebra` + semente `_seed_unidade_periodo_passado(app)`.

Total: **5 arquivos, +201/−56 linhas.** Zero alterações em `migrations/`, `app/services/`, BI, enturmação, desenturmação, transferência, conselho ou `docs/` (exceto este relatório). Formatação CRLF preservada nos 5 arquivos (verificado por contagem de `\r\n` = nº de linhas). Lint: ruff nos 3 arquivos `.py` acusou apenas ocorrências pré-existentes (`E711/E712` em `turmas.py`, `I001` em blocos de import não tocados, `B007` no laço `for idx, ano` que já existia, `F841` em `test_editar_oferta_remove_conflito_permite`, não tocado) — **nenhum diagnóstico novo em linha minha**.

---

## 7. Testes

Comando (PowerShell, raiz do repositório):

```powershell
$env:PYTHONPATH="."
.\.venv\Scripts\python.exe -m pytest tests -q --tb=line
```

| Momento | Passed | Failed |
|---|---|---|
| partida (antes desta etapa) | 210 | 10 |
| após B1 | **218** | **3** |

Contagem por arquivo dos arquivos tocados/relacionados:

| Arquivo | Resultado |
|---|---|
| test_filtros_turmas.py | **17 passed** (16 antigos + 1 novo) |
| test_turma_curso_fase3.py | **20 passed** (antes 16 + 4 falhas) |
| test_turma_curso_fase4.py | **23 passed** (antes 21 + 2 falhas) |
| test_turma_curso_lista.py | 9 passed |
| test_turma_curso_edicao.py | 11 passed, **1 failed** (`test_edicao_duas_ofertas_ignora_campos_de_oferta` — Pare, §8) |
| test_security_regressions.py | 21 passed, **2 failed** (`/cursos`, preexistentes — P6 do T1, fora deste escopo) |

**Linha de resumo do pytest:** `3 failed, 218 passed, 42 warnings in 33.36s`

Os 7 defeitos/realinhamentos previstos (P2, P3, P4, 4×concomitância) fecharam 8 falhas; a meta de "só as 2 falhas de `/cursos`" **não** foi alcançada porque uma delas é a que mandei parar e reportar (§8).

Smoke manual de renderização (fechado ao final, sem deixar arquivos): `GET /turma/nova` → 200 com o `<select name="programa">` e as 4 opções; `GET /turma/editar/<turma com 2 ofertas>` → 200, programa `readonly`, aviso "edite o programa na oferta" presente e **nenhum** `name="programa"` no formulário.

---

## 8. Onde PAREI (premissa de teste em conflito com o MER)

**`tests/test_turma_curso_edicao.py::test_edicao_duas_ofertas_ignora_campos_de_oferta`** (L236-261) afirma, no ramo de 2+ ofertas:

```python
        # Nome/programa gravados:
        assert turma.nome == "T edit NOVA"
        assert turma.programa == "Esporte"     # ← valor vindo do formulário
```

Isso **contradiz** o MER §8.10: L972 ("`Turma.programa` é uma projeção derivada da oferta principal ativa … não é editável como dado independente") e L979 ("[com 2+ ofertas] grava apenas nome, período e ordenação. O programa é derivado da oferta principal e não é editado no cadastro da turma"), que é exatamente o que o passo 4 desta etapa mandou implementar ("Não grave programa vindo do formulário nesse ramo").

Com a correção, a semente (oferta principal com `programa="Teste"`) projeta `"Teste"` e a asserção falha: `assert 'Teste' == 'Esporte'`. **Não adaptei o teste nem a asserção**, por ordem expressa do passo 6. Também não editei o docstring do arquivo (L9: "só nome/programa gravam") nem o comentário do bloco (L235), que repetem a mesma premissa.

Estado: **falha conhecida, à espera da sua decisão** — ou o teste passa a esperar `turma.programa == "Teste"` (projeção, conforme o MER), ou alguém decide que o cadastro de turma volta a escrever programa em turma multi-oferta (o que exigiria reescrever o MER §8.10 e reabrir o P4). As demais asserções do mesmo teste (campos de oferta ignorados na turma e nas ofertas) passam.

**Testes de criação de turma:** verifiquei os dois (`test_nova_turma_com_curso_gera_uma_oferta_principal_false` e `test_frequencia_lancada_em_turma_nova_grava_turma_curso_id`, ambos em `test_turma_curso_fase4.py`) e **não** há conflito com o MER — a semente já enviava `programa="Teste"` no `POST /turma/nova`, ou seja, pedia justamente o comportamento que foi implementado. Não precisei alterá-los.

---

## 9. Decisões que tomei sozinho

1. **`test_filtros_turmas.py::test_rota_listagem_aplica_filtro_nome` tinha marcador errado, não defeito de filtro.** Assim que o KeyError sumiu, a rota passou a 200 e o teste falhou em `assert 'Natação Tarde' not in html`. Investiguei o HTML: os `<select>` de "Nome da Turma"/"Professor" listam todas as turmas da unidade (MER §8.10 L985; mesmo falso positivo que o T1 corrigiu em `test_turma_curso_lista.py`, §3.14). Apliquei a mesma solução: `_linha(body, turma_id)` via `href="/turma/<id>"`. A finalidade ("o filtro por nome casa só a turma pedida") permanece a mesma.
2. **Semeei um período do ano corrente nesse arquivo.** Ao trocar o marcador descobri que a listagem não mostrava **linha nenhuma**: a rota força `ano_periodo=ano_atual` quando o usuário não escolhe período (L406-407) e `aplicar_filtros_turmas` exige `Turma.periodo_letivo_id IN (períodos do ano)` (L236-245) — turmas sem período ficam invisíveis. Como medir filtro de nome sobre uma tabela vazia seria teste vazio, vinculei as 3 turmas da semente a um período do ano corrente (estado normal em produção, onde `/turma/nova` exige período desde L719). Isso **não** muda o que o teste mede; o efeito colateral do comportamento padrão ficou registrado como pendência D3 abaixo, com teste próprio que o documenta.
3. **Criei um teste novo** (`test_rota_listagem_sem_periodo_no_ano_corrente_nao_quebra`) porque, com a semente corrigida, nenhum teste mais exercitava o ramo do KeyError — a proteção de regressão do P2 precisa existir, e `tests/` está no escopo autorizado.
4. **Turma sem curso: `programa` continua NULL** mesmo se o navegador enviar o campo. Deriva do MER L972 (sem oferta não há de que projetar) e mantém "comportamento atual" como mandado no passo 3; escrever um programa solto criaria exatamente o dado independente que o MER proíbe.
5. **Não restringi o programa à lista fechada** na validação da rota. O teste de fase 4 envia `programa="Teste"`, que não está entre os quatro valores da tela; impor a lista quebraria o fluxo programático e não tem base no MER (a coluna é `String`). A tela oferece as opções; o servidor só exige não-vazio.
6. **Ordem da validação do programa depois da validação do curso** (e não antes): com curso ausente/inativo da outra unidade a mensagem correta é "Selecione um curso ativo da unidade…", não a do programa; e `test_security_regressions.py::test_nao_permite_vincular_curso_inativo_a_nova_turma` (POST com curso inativo, sem programa) continua rejeitado pelo motivo certo, sem turma criada.
7. **Não marquei `required` no `<select>` de programa da tela de nova turma**, porque a tela simplificada não tem campo de curso; marcá-lo obrigatório quebraria o fluxo "Salvar e incluir cursos" (turma sem curso). Deixei a exigência no servidor, onde o curso aparece. Ver pendência D1.
8. **Extraí `_PROGRAMAS_OFERTA`** em vez de copiar a lista literal para o `nova_turma`: reusa de fato a mesma lista da tela de oferta e elimina a duplicata inline que já existia em `editar_turma`, sem tocar `ofertas.html` (fora do escopo).
9. **Em `editar.html` não adicionei hidden de programa** — o campo não tem `name`, então o ramo 2+ já não recebe nada forjado; só o aviso faltava. Manter readonly global (inclusive para 0/1 oferta) é coerente com L972: em nenhum caso o cadastro de turma escreve programa.
10. **Não mexi no `except Exception` largo de `nova_turma` (L846-850)** nem no de `editar_turma`, embora tenha sido ele que escondeu o P3 atrás de "Não foi possível salvar a turma". Já registra `logger.exception`, então há rastro; mudar política de erro está fora do escopo.

---

## 10. Pendências

| # | Pendência | Onde | Tipo | Prioridade |
|---|---|---|---|---|
| D1 | A tela de nova turma foi simplificada (só nome + período) e não coleta curso, mas a rota continua aceitando `curso_id`/`turno`/`dias`/horários. O novo campo de programa só tem efeito em POSTs que levem curso. Decidir: **restaurar o select de curso na tela** (e aí o programa passa a ser `required` de verdade) **ou remover o campo da tela** e manter a rota alimentada apenas pelo fluxo programático/ofertas. | `app/templates/turmas/nova_turma.html`, `turmas.py:700-884` | UI/dívida | Média |
| D2 | A decisão P1 do T1 foi resolvida **no sentido do MER** (grava com aviso). Consequência: não há bloqueio de sobreposição em lugar algum — a única guarda é o aviso. Se algum dia se quiser bloqueio, é mudança de regra de negócio (e do MER L969), não de teste. | `app/services/turma_curso.py:347,422`, `MER.md §8.10` | Negócio (registrada) | — |
| D3 | **Comportamento revelado ao corrigir o P2:** com o filtro padrão do ano corrente, **turma sem `periodo_letivo_id` (ou cujo período não começa no ano filtrado) não aparece na listagem** — "Nenhuma turma encontrada". É o estado de qualquer turma legada avulsa. Não alterei (fora do escopo do passo 2, que pedia só o `.get()`), e o novo teste documenta o efeito. Decidir se o default deve incluir turmas sem período. | `turmas.py:402-407` + `aplicar_filtros_turmas` L236-245 | Defeito/dívida (a confirmar por você) | Alta — usuário pode "perder" turmas na tela |
| D4 | `test_edicao_duas_ofertas_ignora_campos_de_oferta` (e o docstring/comentário do arquivo) pressupõem que o cadastro grava `programa` em turma multi-oferta — conflito direto com MER §8.10 L972/L979. **Parei e reportei** conforme o passo 6; a falha é a única desta etapa além das 2 de `/cursos`. | `tests/test_turma_curso_edicao.py:236-261` (e L9, L235) | Premissa de teste × MER | Alta — exige sua decisão |
| D5 | As 2 falhas preexistentes de `/cursos` permanecem (isolamento de unidade `403→200` e validação de carga horária `400→200`). É o item **P6 do T1**, de segurança/validação, e nada tem a ver com esta etapa. | `tests/test_security_regressions.py:482,512` | Defeito | Alta |
| D6 | `ofertas.html` continua com a lista de programas embutida no template (2×), agora divergindo da fonte única `_PROGRAMAS_OFERTA`; unificar exige tocar `app/templates/turmas/ofertas.html`, fora do escopo autorizado. | `app/templates/turmas/ofertas.html:143,270` | Dívida | Baixa |
| D7 | `TurmaCurso.avisos_horario` é atributo **transiente** anexado pela camada de serviço (não é coluna); qualquer consumidor que recarregue a oferta perde os avisos. Os testes agora dependem de ler o objeto retornado na hora. Vale documentar no MER ou devolver `(oferta, avisos)` explicitamente. | `app/services/turma_curso.py:399,450` | Dívida/API | Baixa/Média |
| D8 | Itens do T1 **não tratados** por estarem fora do escopo desta etapa: P5 (código morto do NULL em `bi_filtros`/`_alunos_da_oferta`), P7 (conftest/unificação de fixtures), P8 (marcação por substring em `test_linha_multi_mostra_dois_professores_e_uniao_de_dias`), P9 (remoção, no working tree, de `docs/M1_relatorio.md`, `docs/M1_1_relatorio.md` e `docs/checklist_seguranca_dividas_tecnicas.md` — continuam íntegros em `HEAD`; nada foi tocado por mim). | vário | Dívida | Baixa→Média |
