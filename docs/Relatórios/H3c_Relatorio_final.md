# ETAPA H3c — Relatório final

**Carga horária por ocorrência da grade (fechamento, validação e ensaio)** — 26/10/2026

## 1. Resumo

A C.H. deixou de sair do par escalar e passou a sair da **grade**:

- **Oferta:** `carga_horaria_aula` = duração **uniforme** da grade (`None` quando os dias têm durações diferentes); `carga_horaria_total` = soma da duração do dia em **cada ocorrência** esperada (vigência + bloqueios + exceções por turma).
- **Turma:** `carga_horaria_total` = **tempo físico** — por data, os intervalos das ofertas **ativas** são **unidos** (sobreposição conta uma vez, intervalos disjuntos somam). `carga_horaria_aula`/`min_ch_aula` da turma vêm da **oferta principal**.
- **Coerência filtro × exibição:** `min_ch_total` compara **o mesmo número que a lista mostra** (total da turma), não mais o total da principal; `min_ch_aula` continua na **menor duração semanal**.
- **Lote:** ofertas, grade e bloqueios são lidos em poucas consultas — a C.H. não faz consulta por oferta/data.

## 2. Commits, suíte e head

| Passo | Conteúdo |
|---|---|
| P1/P2 | serviço `CargaOferta`/`CargaTurma` + `cargas_horarias_*_em_lote`, domínio (aula uniforme, total por ocorrência, tempo físico da turma), `datas_esperadas_oferta(hoje=None)`, propriedades delegando ao serviço |
| P2b | `pos_filtrar_turmas`: `min_ch_total` usa o total da turma (mesmo valor exibido); `min_ch_aula` inalterado; `CargaTurma.principal_total` removido |
| P3 | listagem (`turma`, `imprimir_centros_custo_turmas`, `carga_horaria_turmas`), impressão (`imprimir_listar_turma.html`), certificado por oferta (`periodos.py`) e propriedades (`academico.py`) |
| P4 | `tests/test_carga_horaria_oferta_variavel.py` (novo) + ajuste de contrato em `tests/test_turma_curso_lista.py` |
| P5 | `scripts/verificar_h3c_ch.py` + ensaio no scratch `pautaon_ensaio` |
| P6 | MER (§7.32a, §8.10, §10, §12.25) e backlog |

- **Suíte:** 532 → **537 passed, 0 falhas** (5 casos novos).
- **Ruff:** `ruff check app tests scripts --select F821,F811` limpo.
- **Head Alembic:** `5730d7c594ba` (nenhuma migration nesta etapa).
- **Branch:** `nova_feature`, **sem push**.

## 3. Limpeza e código morto

- `print()` de diagnóstico removidos do teste de N+1 (`test_carga_horaria_oferta_variavel.py`).
- **Removidos por não terem leitor** (sobras do rascunho): `CargaTurma.principal_total`, `carga_por_dia`, `menor_duracao_semanal` e uma **segunda definição** de `duracao_do_dia` (F811 — a primeira, do H1, é a que vale).

## 4. Coerência filtro × exibição (P2b)

Antes, na turma com 2+ ofertas, o filtro `min_ch_total` usava `principal_total` enquanto a coluna exibia o total da turma — filtrar por 100h mostrava uma turma de 145h. Agora:

| Cenário (T3 do teste de lista) | Valor |
|---|---|
| C.H. total da turma (exibida) | **145h** (8.700 min) |
| C.H. total da principal | 82h (4.920 min) |
| `min_ch_total=100` | T3 **permanece** (antes sumia) |
| `min_ch_total=146` | T3 **sai** |

Cobertura: `test_min_ch_total_usa_total_da_turma_exibido_na_lista` (compara o limiar com `formatar_ch` do total da turma, provando que filtro e exibição usam o mesmo número) e, no arquivo novo, `pos_filtrar_turmas` com 4,5h/5h/5,01h numa turma de 300 min (principal = 240 min).

## 5. Checagens de escopo (P3)

- **`app/templates/turmas/listar.html`** — diff com **duas** mudanças de fonte de C.H. (célula comentada de "C.H. aula" e as duas colunas da sub-linha de ofertas) + newline no fim do arquivo. **Nenhuma** mudança de exibição de horário/dia (o bloco de horário da sub-linha continua lendo `o.hora_inicio or turma.hora_inicio` — H3e).
- **`app/registros/periodos.py`** — só a C.H. do certificado mudou (passa a usar a C.H. da **oferta**, sem cair para o agregado da turma) + import/`carga_oferta_map` em lote. Nenhuma mudança de horário/dia.
- **`app/templates/turmas/imprimir_listar_turma.html`** — a coluna de C.H. aula passou a ler `carga_oferta_map` (mapa já montado pela rota e antes sem uso); evita 1 consulta por linha. Horário/dia da impressão: inalterados.
- **`tests/test_turma_curso_lista.py`** — contrato: `t3.carga_horaria_total` **2520 → 8700** (tempo físico: 4.920 + 3.780, sem sobreposição) e `min_ch_total` passa a selecionar pelo total da turma (145h) em vez da principal (82h); o teste antes chamado `test_min_ch_total_usa_oferta_principal` virou `test_min_ch_total_usa_total_da_turma_exibido_na_lista`.
- **Consumidores extras classificados:**

| Local | Classe | Ação |
|---|---|---|
| `app/registros/core.py:655` | **(b)** consome via propriedade | Nenhuma — `t.carga_horaria_total` já herda o tempo físico (resposta AJAX de editar curso) |
| `app/registros/turmas.py` `_conflitos_horario_concomitante` | **(c)** não é C.H. | Nenhuma — grupo concomitância, migrado no H3b |
| `app/utils/formatters.py:11` | **(c)** não é C.H. | Nenhuma — docstring de `formatar_ch` (formatação, agnóstica à fonte) |

## 6. N+1: o que a etapa garante

- Consultas de **grade** (`turma_curso_horario`) e de **bloqueios** (`dia_bloqueado`/`dia_bloqueado_turma`) são **constantes** com 2 ou 6 ofertas na listagem; a página `/turmas/carga-horaria` fica **idêntica** (28 statements antes e depois).
- A sub-linha de ofertas ainda faz **1 consulta de frequência por linha** (`freq_geral_oferta`) — **dívida da Etapa K**, já registrada em §8.10 do MER, fora do escopo do H3c; por isso o teste de N+1 mede as fontes de C.H. e limita o crescimento total da listagem a esse N+1 conhecido.

## 7. Ensaio no scratch PostgreSQL (P5)

Banco `pautaon_ensaio`, head `5730d7c594ba`, **3 turmas / 5 ofertas ativas / 8 linhas de grade**. Script `scripts/verificar_h3c_ch.py` (somente leitura; saída em `instance/backups/h3c_ensaio.txt`), exit 0.

| turma | ofertas | antigo | novo | principal | soma | causa |
|---|---|---|---|---|---|---|
| **9** | 3 | **162h** (9.720 min) | **112h** (6.720 min) | 105h | 131h | sobreposição deduplicada + escalar da turma aplicado a dias de 1h |
| 10 | 1 (uniforme) | 105h | 105h | — | — | antigo == novo |
| 11 | 1 (uniforme) | 70h | 70h | — | — | antigo == novo |

- **Turma 9 — mudou (9.720 → 6.720 min):** o cálculo antigo pegava o par escalar da **turma** (3h, Seg/Qua 08:00–11:00) e multiplicava pelos **54 dias da união** (Seg + Qua + Ter), cobrando 3h também nas terças, que só têm 1h. O tempo físico soma as ofertas reais (105h + 7h + 19h = **131h**) e deduplica **19h** de sobreposição (quarta 10:00–11:00, dentro de 08:00–11:00).
- **Invariante verificada:** `principal (105h) ≤ novo (112h) ≤ soma (131h)` ✓. Turmas de 1 oferta uniforme: `antigo == novo` (nenhuma divergência — critério de PARADA não acionado).
- **Ofertas reais — antes × depois (idênticas):**

| oferta | turma | aula ant. | aula dep. | total ant. | total dep. | grade |
|---|---|---|---|---|---|---|
| 11 | 9 | 3h | 3h | 105h | 105h | Seg, Qua · 08:00-11:00 |
| 12 | 9 | 1h | 1h | 7h | 7h | Ter · 08:00-09:00 |
| 13 | 9 | 1h | 1h | 19h | 19h | Qua · 10:00-11:00 |
| 14 | 10 | 3h | 3h | 105h | 105h | Seg, Qua · 14:00-17:00 |
| 15 | 11 | 2h | 2h | 70h | 70h | Seg, Ter · 13:00-15:00 |

## 8. O que NÃO mudou

- **Exibição de hora/dia** (sub-linha, impressão, detalhe) — segue na projeção escalar, correta enquanto a grade é uniforme (H3d/H3e).
- **Filtros** por professor/turno/dia/horário e a regra de **vigência**.
- **Turmas de 1 oferta uniforme:** C.H. idêntica à anterior (provado no ensaio).
- **Schema** intacto (head `5730d7c594ba`) e nenhuma migration nova.

## 9. Perguntas abertas

1. **`min_ch_aula` na turma multi-oferta** continua na menor duração **da principal**. Deve passar a considerar todas as ofertas (mínimo global) ou manter?
2. **Certificado:** hoje mostra a C.H. da **oferta**. Se a instituição quiser o tempo físico da turma no certificado de turma multi-oferta, é uma decisão de produto (mudaria o número emitido).
3. **N+1 da frequência** na sub-linha (§8.10 do MER) — vale um lote de `agregar_por_oferta` numa etapa curta?
4. **Arredondamento:** a C.H. total agora pode ter minutos quebrados (ex.: 112h em 60 min). Manter `formatar_ch` como está (h + min) está bom?

**Status: H3c concluída.** Restam H3d (filtros/listagem/impressão pela grade), H3e (hora/exibição), H4 (UI por dia) e H5 (drop das colunas de projeção).
