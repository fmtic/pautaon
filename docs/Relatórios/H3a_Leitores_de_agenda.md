# ETAPA H3a — Relatório Final

**Leitores de agenda e validação passam a ler a grade** — 26/10/2026

## 1. Resumo
Os **leitores de dias/horário** do grupo *agenda/validação* passaram a consumir a **grade** (`turma_curso_horario`) via o serviço, em **lote e sem N+1**, em vez do CSV escalar. A **Turma passou a DERIVAR** seus dias da união das ofertas ativas (sem ler `Turma.dias_semana`). Equivalência **provada por três vias**; nenhum comportamento visível para dados reais.

## 2. Commits, suíte e head
| Passo | Commit | Conteúdo |
|-------|--------|----------|
| P0 | `4e3f44c` | Guarda anti-`create_all` em PostgreSQL + backup `pautaon_pos_H2.sql` |
| P2/P3 | `00502fc` | Serviço `dias_da_oferta`/`dias_por_ofertas`/`dias_da_turma` + migração dos leitores |
| P4 | `80eae75` | Testes novos dos leitores por grade + equivalência |
| P6 | `6d5a675` | MER (§7.32a, §10, §12.25) + backlog |

- **Suíte:** 489 → **522 passed, 0 falhas** (+33 testes novos).
- **Ruff:** `ruff check app tests scripts --select F821` limpo.
- **Head:** `nova_feature` @ `6d5a675`; nenhuma migration nova (base segue `5730d7c594ba`); **sem push**.

## 3. Leitores migrados (P1→P3)
- `turma_curso.py`: `_data_bate_dias_semana(oferta, data)` lê a grade; novo `_dias_set_da_oferta` (fonte grade → **fallback** CSV via `csv_para_weekdays` + `logger.warning` de tokens desconhecidos); `datas_aula_oferta`/`datas_esperadas_oferta` e `resolver_oferta_lancamento` leem dias pela grade — **vigência, dias bloqueados e regra de oferta única INALTERADOS**; removido `_NOMES_DIA_SEMANA`.
- `logica.gerar_datas`: removeu `mapa_dias`; deriva de `dias_da_turma` (união das ofertas ativas) com fallback ao conversor.
- Frequência/pendências/dashboard herdam via `datas_esperadas_oferta` — **sem consulta por data/oferta**.
- **P1 sem leitores extras** além da lista do protocolo.

## 4. Testes que mudaram de contrato (listados com motivo)
- **`test_data_bate_dias_semana_acento_espace_variante`** (fase4) — reancorado à grade: assinatura mudou de `(csv, data)` para `(oferta, data)`. **Previsto** em H1 §5. Foi a **única** falha ao migrar (488/489), evidência empírica de equivalência.
- **`TestParseDias`** (fase3) — **NÃO quebrou**: `_parse_dias` sobrevive como ponte.

## 5. Ensaio Postgres + BI (P5)
- Scratch `pautaon_ensaio` (head `5730d7c594ba`, 8 linhas / 5 ofertas): datas esperadas **CSV antigo × grade novo = 0 divergências** nas 5 ofertas reais.
- BI **FRE-009 / AUL-002 / ALU-009 idênticos** Postgres × SQLite espelhado.

## 6. Desvios / decisões de execução
- **`_parse_dias` não foi removido** — ainda tem chamador (`_conflitos_horario_concomitante`, grupo concomitância = H3d). Mantido **só como ponte** marcada, conforme a cláusula "senão deixar só como ponte" do P3.
- **Limite de `datas_aula_oferta` é INCLUSIVO** no código (`<=`), apesar do docstring dizer "exclusivo" — comportamento **não alterado** (fora do escopo de leitura de dias).
- **Fallback CSV** mantido para ofertas/turmas 100 % legado (sem grade) — mantém equivalência até o H5.
- **Guardas `create_all`** (bootstrap + create_postgres_schema) adicionadas no P0 para fechar o vetor da órfã da H1.
- **Renomeação de `docs/`** (vários `D docs/*.md` + `?? docs/Relatórios/` no `git status`): artefato de **sincronismo Nextcloud** (a pasta inteira foi movida para `Relatórios/` externamente), **fora do escopo** — **não commitei**. O commit P6 tocou só MER + backlog.

## 7. Confirmação do que NÃO mudou
**C.H. total** (fica no H3b), **concomitância** (`_conflitos_horario_concomitante` ainda por `_parse_dias`, H3d), **filtros/listagem**, **telas** e **exibição de hora** (H3e/H4) — **inalterados**. Só a leitura de **dias/validação de agenda** migrou para a grade.

## 8. Perguntas abertas
1. Apertar `ck_tch_dia` do banco de 0–6 para 0–5 (exigiria migration de revisão + limpeza de legado com domingo) — ainda em aberto desde a H2.
2. Ao remover a ponte (`_parse_dias`) no H3d, confirmar que nenhum outro leitor de CSV de dias restou.
3. Reorganização `docs/Relatórios/` do Nextcloud: deve ser commiteada à parte, em ação própria de higiene de docs?

**Status: H3a concluída.** Restam H3b–H3e (C.H., concomitância, hora/exibição), H4 (UI por dia) e H5 (drop das colunas de projeção).
