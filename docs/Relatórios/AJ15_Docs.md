# AJ15 — Atualização de documentação

Data: 2026-11-05. Branch de trabalho: `aj15b-docs` (worktree `D:\pautaon-aj15b`), criada a partir da
`nova_feature` integrada em `ecfbb6b`. **Sem push. Commits com caminhos explícitos.**

Tarefa **exclusivamente documental**: **nenhum arquivo de código, teste ou migration foi alterado**
(`git diff --name-only nova_feature..aj15b-docs` devolve só os cinco arquivos deste relatório).
Head Alembic do código segue `c1d2e3f4a5b6`; produção `c4d5e6f7a8b9` (24 revisões pendentes).

Método: leitura prévia do conteúdo ATUAL de cada arquivo e edição incremental (diffs mínimos);
nenhum arquivo foi reescrito por inteiro. Instrução conflitante com o texto atual → manteve-se o
atual e registrou-se a dúvida abaixo.

## Arquivos tocados (commits)

| Commit | Arquivo | O que mudou |
|---|---|---|
| `fc51af5` | `app/models/MER.md` | Cabeçalho/data e nota AJ15; §7.3 com a coluna `user.session_version`; §7.4b com o status real da migration `e1f2a3b4c5d6`; bloco novo no §8.2 (acesso/auditoria da gravação do conselho — AJ7-A/AJ7-D); §8.27 novo (notas de semântica AJ7–AJ13: `/turma` e impressão por papel, regra única do professor sem ficha de aluno, `historico_aluno` temporário, aluno sem `unidade_id` fora de escopo, `Turma.professor_id` vestigial, regra D2); §11 com as linhas que faltavam (`e1f2a3b4c5d6`, `b5c6d7e8f9a0`, `c1d2e3f4a5b6`) e o "Head atual" corrigido para `c1d2e3f4a5b6` com produção em `c4d5e6f7a8b9` + 24 pendentes |
| `0b28505` | `backlog_desenvolvimento.md` | Entrada nova no topo (05/11/2026): concluídos AJ3–AJ14 (uma linha cada), pendências completas (baseline, `e1e3a5b2c333`, `Curso`/AuditoriaMixin, `periodo_letivo.unidade_id`, plano NOT NULL §12.10, CSP report-only, logs de e-mail, assinatura de imagens, Pillow, teste instável da pauta, gerência somente leitura, vocabulário oferta/curso, SEC-04, AJ11 código morto, BI pós-release) e regras de negócio vigentes. **Nenhuma linha existente removida ou reescrita** (51 inserções) |
| `f5b1cf3` | `app/relatorios/indicadores.md` | Glossário novo (cadastro novo vs aluno novo; "ativo" com nome do campo; "Outros" resíduo do classificador; unidade estatística = linhas de lançamento/registro, não pessoas/dias; regra D2); correções editoriais AJ12 §5 (cinco modos de visualização; filtros visíveis = unidade/período/turno com curso/turma/professor só por API; INS-004 com `Inscricao.data_inicio`; TUR-001 = turmas ativas; FRE-005 = taxa ponderada por lançamento; ALU-007 vs DIV-001 com bases distintas e contagem multi-tipo; ALU-004 reforçado); correções AJ14 (INS-006/007 indisponíveis e ocultos da Central; TUR-005/008 por oferta; CRU-002 por resposta preenchida; CRU-005 só com `situacao_final`); §10 de pendências do catálogo (CRU-004 por oferta, ALU-009 turno, TUR-004 aluno distinto, duplicados, DIV-001 vs ALU-007); Sumário e data finais atualizados |
| `19bd022` | `docs/deploy_release.md` | **Arquivo novo** (runbook): janela de manutenção; `pg_dump -Fc` imediatamente antes; cópia do código sem sobrescrever `.env`/`instance/`/`chaves/`; `migrations/` inteira; remoção de arquivos deletados; `pip install -r requirements.txt` (Python 3.14.7); `flask db upgrade` + conferência `flask db current = c1d2e3f4a5b6`; consulta SELECT de alunos ativos sem `unidade_id` + UPDATE manual caso a caso; backfill opcional (`scripts/backfill_unidade_id_nulos.sql`, regerar contagens no dia); reinício do IIS; smoke manual (login, painel, frequência, conselho, cadastro com foto/documento, BI); variáveis de produção (`APP_ENV`, `SESSION_COOKIE_SECURE`, `SECRET_KEY`, `UPLOAD_FOLDER` fora de `static`, sem `GOOGLE_OAUTH_*`); rollback = dump + arquivos antigos, **nunca downgrade**; nota dos 7 valores de `curso.carga_horaria` descartados (o dump guarda) |
| (este commit) | `docs/Relatórios/AJ15_Docs.md` | Este relatório |

## Dúvidas e conflitos encontrados (texto atual mantido)

1. **AJ14 não está no Git.** O relatório `docs/Relatórios/AJ14_BI.md` e as correções do BI existem
   apenas como **arquivos não commitados no worktree `D:\pautaon-aj14`** (branch `aj14-bi` está no mesmo
   commit de `nova_feature`, sem os commits das correções). Documentei o AJ14 no catálogo e no backlog
   **como descrito no relatório/código não commitado**; se as correções vierem a mudar ou não serem
   integradas, o catálogo precisa ser realinhado.
2. **MER §8.2 (linha "BI")** diz que CRU-002/CRU-005 filtram "por **turma**" e que "BI não foi migrado
   para oferta" (decisão D5.4) — conflita com o catálogo atual (filtros pela OFERTA do conselho).
   Mantive o texto atual do MER e registro aqui a dúvida: a linha do §8.2 parece não ter acompanhado
   `e5f6a7b8c9d0`/AJ12; decidir na próxima revisão do MER.
3. **TUR-001**: o catálogo antigo descrevia "total geral de turmas", mas a implementação conta turmas
   **ativas**. Ajustei a **descrição** para casar com o código (opção do AJ12 §5); a alternativa
   (mudar a implementação para incluir inativas) continua decisão de negócio em aberto — registrada no
   próprio item e na seção de duplicados.
4. **AJ11 não tem commit no Git** (`git log --all --grep AJ11` vazio). Tratei-a como concluída no
   formato de análise (sem remoção de código), com achados nas pendências, usando a entrada de 02/11
   do backlog e a descrição atual da tarefa.
5. **Branch `aj15-docs` (tentativa anterior, 4 commits não integrados)** existe no repositório. Não a
   mesclei, reverti nem apaguei; esta entrega é nova a partir de `nova_feature` integrada. Decidir o
   destino da branch antiga (provável descarte).
6. **`SESSION_COOKIE_SECURE`**: a tarefa pede "true se HTTPS"; o app já é Secure **por padrão** desde
   o S1-E1 (desliga só com `APP_ENV=development` declarado). O runbook registra o padrão e a condição.
7. **Grelha de anchors do sumário do indicadores.md**: a entrada nova nº 10 usa anchor gerado à mão;
   renderizadores diferentes podem não casar exatamente (o corpo da seção está correto).

## Âncoras de schema verificadas (fontes: `migrations/versions/` e modelos)

- Cadeia única, head `c1d2e3f4a5b6`; produção `c4d5e6f7a8b9` → exatamente **24 revisões** até o head
  (confere com AJ9-C). Script de traçamento em `.tmp/aj15b_chain.py`.
- `turma_curso`: `professor_id` NOT NULL (`d6e7f8a9b0c1`), `conselho_concluido` NOT NULL default false
  (`e5f6a7b8c9d0`/`f6a7b8c9d0e1`); `turma_curso_horario` (`5730d7c594ba`, CHECK 0–5 `7c1d2e3f4a5b`);
  colunas removidas: `curso.carga_horaria` (`d1e2f3a4b5c6`), `turma.conselho_concluido`
  (`f6a7b8c9d0e1`), escalares de agenda em `turma`/`turma_curso` (`8d2e3f4a5b6c`); `unidade_id` em
  `conselho_classe`/`frequencia`/`registro_aula` (TenantMixin, §7.19/§7.20/§7.24); regra D2 (§8.1);
  `Turma.professor_id` vestigial (§8.26).

## Validações

- `git diff --name-only nova_feature..aj15b-docs` = apenas os 5 arquivos documentais.
- Nenhum `git add .` — todos os commits com caminhos explícitos.
- Worktree principal `D:\pautaon` intacto (o relatório AJ14_BI.md não commitado do usuário não foi tocado).
- Sem push; branch preservada para revisão e mesclagem posterior.
