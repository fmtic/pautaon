# ETAPA H2 — Relatório final (escritores da grade por dia)

Contexto de partida: H1 concluída (branch `nova_feature`, head `5730d7c594ba`, 458 passed).
Fontes consultadas: MER (§7.32, §7.32a), backlog, H0 (§2 escritores, §4 riscos 2/10, §6), relatório H1.
Decisões fechadas pelo responsável: retroatividade sem versionamento; domínio dos dias 0–5 (domingo rejeitado); grade nunca parcial (todo dia com início e fim, fim > início); bloqueio de agenda na Turma por **uniformidade da grade**, aplicado no POST além do controle visual.

---

## 1. Commits (branch `nova_feature`, sem push)

| Hash | Passo | Mensagem (resumo) |
|---|---|---|
| `6106225` | — | docs: relatório final da ETAPA H1 (abertura da sessão) |
| `a028cce` | P2 | `definir_grade` valida o contrato H2 (grade não vazia, dias 0–5 sem domingo, todo dia com início e fim, fim > início, mensagens por dia, idempotência sem escrita); testes H1 do serviço ajustados ao contrato novo |
| `52628b9` | P3 | escritores de oferta passam pelo `definir_grade` na mesma transação + UI (bloqueio por uniformidade, aviso de retroatividade) |
| `fa2e957` | P4 | testes do contrato `definir_grade` e dos escritores da grade (`test_definir_grade.py`, `test_turma_curso_horario_escritores.py`) |
| `a871561` | P5 | MER (§7.32a, §10, §12.25) e backlog atualizados para a H2 concluída |

## 2. Suíte e head

- **489 passed**, 0 falhas (P0: 458 → P2: 463 → P4/P5: 489).
- `ruff check app tests --select F821` limpo.
- Head `5730d7c594ba` aplicada no **banco principal** e no scratch; `flask db heads` devolve apenas esse hash.
- Árvore de trabalho limpa; nenhum script temporário sobrou (`tmp_h2_*.py` apagados); nenhuma sessão do principal foi derrubada (no principal apenas `flask db upgrade`; o `DROP DATABASE ... WITH (FORCE)` foi usado só no scratch).

## 3. Por passo

- **P0 (pré-requisito, autorizado):** backup `instance/backups/pautaon_pre_H1.sql` restaurado UMA vez no scratch (prova de restore ok); `flask db upgrade` no principal; conferência: head `5730d7c594ba`, 8 linhas / 5 ofertas, `dias_semana` varchar(80), `max(length(dias_semana))` = 15; **consulta de conformidade 100%** — nenhuma oferta sem dia, nenhum dia sem `hora_inicio`/`hora_fim`, nenhum domingo, nenhum `fim <= início` (nada a reportar/corrigir); scratch `pautaon_ensaio` recriado na head nova; suíte 458 verde antes de editar código.
- **P1 (leitura):** escritores confirmados exatamente na lista do protocolo — `adicionar_oferta`, `editar_oferta`, `criar_oferta_inicial_da_turma`, `_sincronizar_legado`, `nova_turma`, `editar_turma` POST, `_dados_oferta_form`, `turma_oferta_nova/editar`, parser `utils/datetime_parse.py` — e **nenhum ponto extra** gravando `dias_semana`/`hora_*` de Turma ou TurmaCurso. "Domingo" já não existia em nenhuma opção de formulário/template/rota (confirmado por grep).
- **P2 (validação central):** `definir_grade` recusa grade vazia, dia fora de 0–5, domingo (mensagem própria), dia duplicado, hora ausente e `fim <= início` — sempre com mensagem em português citando o dia; validação **antes** de qualquer alteração (atômico); idempotência real: reaplicar a mesma grade é no-op com zero escrita (provado por listener). `grade_a_partir_do_legado` (ponte CSV+par → grade uniforme, `None` se incompleta) criado na camada do serviço.
- **P3 (escritores + UI):**
  - `criar_oferta_inicial_da_turma` e `adicionar_oferta`: herança da Turma só preenche a grade se **completa**; senão `ValueError` com a mensagem única `_AGENDA_INCOMPLETA` (nunca grade parcial); a oferta nasce sem kwargs escalares e a projeção é gravada pelo `definir_grade`.
  - `editar_oferta`: aceita campos de agenda, mescla com os valores vigentes, exige grade efetiva completa e recalcula os avisos de concomitância com a grade nova (`_conflitos_horario_concomitante` inalterado — H3).
  - `_sincronizar_legado`: permanece a única chamada que espelha oferta→Turma, agora alimentada pela projeção — nenhuma gravação paralela de escalares.
  - `nova_turma`/`editar_turma`: continuam enviando "mesmo horário em todos os dias" (uniforme), convertido em grade pelo serviço; sem UI de grade variável (H4). `nova_turma` trata `ValueError` com rollback + flash.
  - `editar_turma` POST: se a grade da oferta ativa **não é uniforme**, os campos de agenda da Turma são ignorados com flash claro, e o espelho da oferta única muda de `setattr` para `definir_grade`; `editar.html` troca o critério de bloqueio de "≥2 ofertas" por `agenda_bloqueada` (≥2 ofertas **OU** oferta única não uniforme).
  - `ofertas.html`: aviso de retroatividade — "A alteração de dias e horários vale para **todo o período da oferta**, inclusive aulas já lançadas."
  - Leitores não tocados; grade não uniforme não é criaível pela UI (só serviço/teste, H4).
- **P4 (testes novos):** 26 casos — `tests/test_definir_grade.py` (15: domínio 0–5 parametrizado aceito, domingo rejeitado mesmo sobre grade válida, mensagens citando o dia em cada violação, atomicidade em nível de banco com releitura pós-rollback, validação antes da idempotência) e `tests/test_turma_curso_horario_escritores.py` (11: oferta inicial com projeção, herança incompleta rejeitada sem escrita, adicionar com/sem agenda, só-domingo rejeitado, editar substitui grade e reprojeta, agenda incompleta preserva anterior, projeção não uniforme NULL preservada pelos escritores, POST editar_turma ignora agenda não uniforme (flash) e espelha uniforme, escrita limitada sem N+1 de escrita).
- **P5 (documentação):** MER §7.32a ganhou o bloco "Regras (decisões fechadas do H2 — escrita)"; §10 tem a entrada "H2 — Escritores da grade por dia"; §12.25 marca H2 concluída, adiciona o item de conflitos por grade à H3 e registra a aplicação no principal + pergunta aberta do CHECK; backlog com o bloco "Alterações do dia — H2".

## 4. Estado dos bancos

- **Principal `pautaon`:** head `5730d7c594ba`, grade 8 linhas / 5 ofertas, conformidade total, nenhum dado corrigido à mão (não havia do que corrigir). Tabela órfã vazia `turma_curso_horario` (resquício de `db.create_all()` acidental) dropada **antes** do upgrade, com guarda "só dropa se 0 linhas" e autorização explícita do responsável.
- **Scratch `pautaon_ensaio`:** recriado do dump de pré-H1, órfã removida, upgradeado à head nova, 8 linhas — pronto para a H3.

## 5. Testes existentes alterados (apenas por mudança de contrato — todos listados)

| Arquivo | O que mudou | Por quê |
|---|---|---|
| `tests/test_turma_curso_horario_servico.py` (P2, `a028cce`) | Casos "dia sem horário" passaram a ser semeados via modelo direto (`_semeiar_linhas_legado` + expire da relação); parametrize de recusas ganhou `[]`, domingo e par ausente; `test_projecao_seis_dias_cabem_em_80` agora asserta CSV de 6 dias; +2 testes (recusa domingo, idempotência sem escrita) | O contrato de escrita do `definir_grade` mudou (H2); a tolerância a linhas sem horário continua só para **leitores** de legado |
| `tests/test_turma_curso_fase2.py` (P3, `52628b9`) | Fixture `base`: Turma nasce com agenda completa (Segunda 09–10); chamadas de 2ª/3ª oferta em 5 testes passaram a enviar `dias_semana`/`hora_inicio`/`hora_fim`; POST da rota "segunda oferta" envia agenda | Desde o H2 toda oferta exige grade completa; após a 1ª oferta a turma tem vínculo e a herança não se aplica |
| `tests/test_turma_curso_fase3.py` (P3, `52628b9`) | `test_adicionar_oferta_sem_horario_pula_validacao` → `test_adicionar_oferta_sem_agenda_completa_e_rejeitada` (assert `ValueError` + nada gravado); bullet do cabeçalho atualizado | O contrato antigo ("sem horário pula validação") foi extinto pela decisão "sem par incompleto, sem dia sem hora" |
| `tests/test_turma_curso_fase4.py` (P3, `52628b9`) | `_post_nova_turma` envia `hora_inicio`/`hora_fim`; fixture do teste de idempotência da oferta inicial ganha dias/hora; 2ª oferta do teste "turma encerrada" recebe agenda explícita | A oferta inicial agora exige agenda completa na turma (herança nunca parcial) |

Nenhum outro teste existente foi tocado; todos os demais 460+ passaram sem alteração.

## 6. Desvios do protocolo (nenhum bloqueante)

1. **Achado no P0 (parada + autorização):** o banco principal estava em estado híbrido — a tabela `turma_curso_horario` já existia, **vazia**, criada por um `db.create_all()` acidental durante o dev da H1, com constraints idênticas ao MODELO (não à migration) e `dias_semana` ainda varchar(20), com `alembic_version` em `a8b9c0d1e2f3`. Reportei ao responsável; autorizado "dropar e upgrade", a órfã vazia foi removida com guarda e o upgrade seguiu limpo. A prova de restore do backup no scratch foi o que expôs o problema (o dump já continha a órfã).
2. **Critério de bloqueio no `editar.html`:** implementado como flag composta `agenda_bloqueada` = "≥2 ofertas **OU** oferta única com grade não uniforme", em vez de substituir literalmente um critério pelo outro — o bloqueio de múltiplas ofertas é regra existente (G2/G3) e foi preservado; o critério novo de uniformidade foi acrescentado, cumprindo a decisão.
3. **"Remover domingo das opções":** no-op — nenhum formulário, template ou rota oferecia domingo (a lista da rota já era segunda–sábado). Registrado em P1.
4. **`test_definir_grade.py` × arquivo do serviço:** leve sobreposição intencional; o novo arquivo foca os eixos exigidos pelo protocolo P4 que o do serviço não cobria em nível de banco (mensagens por dia, releitura pós-rollback, validação antes da idempotência).

## 7. Perguntas abertas

- **Apertar o CHECK `ck_tch_dia` de 0–6 para 0–5**: o serviço já recusa domingo, mas o banco tolera por legado. Uma revisão futura exigiria migration com checagem de eventual linha com dia 6 (hoje: zero no principal). Registrado na §12.25.
- **Espelho na Turma com grade não uniforme:** a projeção deixa `oferta.hora_inicio/fim` NULL, e o `_sincronizar_legado` replicaria NULL na Turma — como a tela da Turma deve exibir agenda não uniforme é decisão de H3/H5.
- **Concomitância por dia (`_conflitos_horario_concomitante`)** ainda lê os escalares; com grade não uniforme o par escalar é NULL e a detecção fica conservadora. Já agendado na H3 (§12.25 atualizado).

## 8. Confirmação: nenhum leitor mudou

Carga horária (`calcular_dias_aula_turma`, painéis), pendências, validação de dia de lançamento (`_data_bate_dias_semana`), listagens (splits de `dias_semana`), BI, painel pedagógico, conselho e `_conflitos_horario_concomitante` continuam lendo as colunas escalares de `Turma`/`TurmaCurso` — que permanecem corretas porque agora são escritas exclusivamente por `sincronizar_projecao_horario`, alimentado pela grade. As únicas mudanças de interface foram nas duas telas de **escrita** (`editar.html`, `ofertas.html`), no contexto da rota `editar_turma` e no tratamento de `ValueError` em `nova_turma`.
