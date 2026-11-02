# AJ6-B4 — fechamento da série de autorização por OFERTA

Etapa que fecha a série AJ6-B na branch `nova_feature`, base `5820fa0` (HEAD do
fechamento documental AJ3–AJ6). Sem migration, sem push, **nenhuma escrita em
banco real** (somente SELECT), nomes sintéticos em teste, reversão provada em
`git worktree` com caminho absoluto, sem código morto.

Toda a etapa usa a **mesma regra central** do ciclo —
`ofertas_do_professor` / `professor_pode_acessar_oferta`
(`app/services/aluno_info_professor.py`) — **sem nova predicação de acesso**.

| # | Rota/arquivo | Vazamento | Correo |
|---|--------------|-----------|--------|
| 0 | `test_aj6b3_snapshot_nao_professor.py` | teste `skip` (script manual, não asseria) | convertido em snapshot **golden** que roda sempre |
| 1 | `historico_aluno` (`alunos.py`) | professor via o histórico de **todas** as inscrições do aluno | lista só inscrições em ofertas dele |
| 2 | GET `/frequencia` (`core.py`) | sob `exigir_escolha` o calendário era a união de **todas** as ofertas | datas/meses zerados |
| 3 | `detalhe.html` / `ver_turma` | "Centro de custo compartilhado" da oferta principal alheia saía (valor ou "Não definido") | campo ocultado para o professor |
| 4 | `/turma` (lista) | — | **NÃO tocado** (decisão do responsável pendente) |

---

## 0. Pendência do AJ6-B3 — o `1 skipped`

**Identificação.** `pytest -rs` aponta o skip em
`tests/test_aj6b3_snapshot_nao_professor.py::test_snapshot_ver_turma_nao_professor`.
Motivo: o teste tinha um `@pytest.mark.skipif` que exigia a variável de ambiente
`AJ6B3_SNAP=antes|depois`. Sem ela (a suíte normal), o teste era **ignorado**. Era,
de fato, do `test_aj6b3_snapshot_nao_professor`. O corpo, além disso, só
**escrevia arquivos** em `.tmp/` — nunca comparava nada, ou seja, mesmo quando
rodava não asseria.

**Contagem.** A suíte do AJ6-B3 fechou em `1495 passed / 1 skipped`; a base
anterior era `1484 passed / 0 skipped`. O `+1 skipped` é exatamente este teste
(são arquivos de teste novos adicionados no ciclo, daí também o aumento de
`passed`).

**Correção (converter para rodar de verdade).** Removido o `skipif`; o teste
agora é um **golden** no padrão já consolidado da suíte (o mesmo de `AJ5-C`:
comparação contra snapshot canônico em `tests/snapshots/`, regenerável com uma
variável — aqui `AJ6B4_ATUALIZAR_SNAPSHOTS=1`). Para cada um dos 5 perfis
não-professor (`admin`, `pedagógico`, `secretaria`, `gerência`, `serviço social`)
e cada turma da semente, o HTML normalizado de `/turma/<id>` (sem `class=`, sem
CSRF, whitespace colapsado) é comparado com o arquivo
`tests/snapshots/aj6b3_<perfil>_<turma>.txt`. 10 snapshots commitados.

**Prova de que detecta mudança.** Adulterou-se um golden (trocou `Turma Um` por
`TURMA-UM-MUTADO` em `aj6b3_admin_t1.txt`) e o teste **falhou**; o golden foi
restaurado e o teste voltou a passar. Também se rodou a comparação duas vezes
seguidas com saída idêntica (**determinístico**, graças ao `hoje_fixo`).

**Reversão (o oposto também vale).** No worktree em `5820fa0` (sem o fix) o
snapshot **passou**: a saída não-professor é idêntica antes/depois das correções
dos itens 1–3 (todas atuam só no ramo `role == PROFESSOR`). É a prova de que os
fixes não mexeram na visão dos demais perfis.

**Hashes dos 4 commits do AJ6-B3** (para referência):

| Commit | Tipo | Sumário |
|--------|------|---------|
| `4fde802` | test | escopo de oferta na ficha da turma e dashboard sem fallback |
| `75aa849` | fix(ver_turma) | restringe payload/HTML às ofertas do professor |
| `be7349b` | fix(dashboard) | remove fallback `Turma.professor_id` |
| `18f576e` | docs | relatório do escopo de oferta em ver_turma e dashboard |

---

## 1. `historico_aluno` — inscrições só das ofertas do professor

**Rota:** `historico_aluno` (`app/registros/alunos.py`, a partir de ~1001). A
régua de entrada (professor com **qualquer** oferta ativa com inscrição do
aluno) fica **inalterada**. O vazamento estava na lista: ela buscava **todas** as
inscrições do aluno (`Inscricao.query.filter_by(aluno_id=...)`) e renderizava uma
linha por inscrição — inclusive as de ofertas/turmas que o professor não
leciona, expondo o curso e o **nome de outro professor**.

**Fix.** Depois de carregar as inscrições, para `role == PROFESSOR` filtra-se a
lista pela **regra única** `ofertas_do_professor` (que envolve
`professor_pode_acessar_oferta`), sobre os objetos `TurmaCurso` já carregados
via `joinedload` (sem consulta nova):

```python
if current_user.role == UserRole.PROFESSOR:
    from app.services.aluno_info_professor import ofertas_do_professor
    ofertas_dele = {
        o.id for o in ofertas_do_professor(
            current_user,
            {insc.turma_curso for insc in inscricoes if insc.turma_curso is not None},
        )
    }
    inscricoes = [
        insc for insc in inscricoes
        if insc.turma_curso_id is not None and insc.turma_curso_id in ofertas_dele
    ]
```

Downstream (`conselhos_por_oferta`, `grades_para_exibicao`,
`frequencias_aluno_por_inscricao`, o laço `dados`) opera sobre `inscricoes` já
filtrado. Demais perfis: lista inteira, guarda de role + unidade **inalterada**.

**Testes** (matriz, `test_aj6b4_fechamento_oferta.py`):

- `test_item1_professor_ve_soa_inscricao_na_oferta_dele` — pA vê só a oferta A.
- `test_item1_aluno_em_a_e_b_pa_nao_ve_b_nem_pb` — aluno inscrito em A (pA) e B
  (pB): pA **não** vê o curso B nem o nome "Professor Bravo".
- `test_item1_admin_ve_todas_as_inscricoes` — admin vê A e B e os dois
  professores (contraponto: o filtro só vale para professor).

**Reversão.** No worktree (código antigo) os dois testes de professor **falham**
com `vaza oferta de outra turma/professor` / `vaza o nome de outro professor`; o
de admin passa. Com o fix, os três passam.

---

## 2. GET `/frequencia` — `exigir_escolha` sem calendário vazio de oferta alheia

**Rota:** `frequencia` (`app/registros/core.py`, ~432–546). Quando o professor
tem **2+ ofertas próprias e nenhuma escolhida** (`exigir_escolha`), o código já
zerava `alunos`/`temas`, mas `datas`/`meses` vinham de `carregar_contexto_turma`
= agenda **da turma inteira** (união de todas as ofertas, inclusive as que ele
não leciona).

**Estado dos links (diagnóstico).** A sonda mostrou que, sob `exigir_escolha`,
**nenhum link de `imprimir_pauta` é gerado** — a guarda `pode_imprimir_pauta and
not exigir_escolha` (G1-4, `lancar.html:16`) já esconde o popover inteiro, e o
`pode_imprimir_pauta` é `False` para professor sem oferta escolhida
(`core.py:671-679`). Ou seja, **não havia link que desse 403** hoje; a regra do
`imprimir_pauta` (sem `turma_curso` → pega `ofertas[0]`, menor id → 403 se não é
dele, `turmas.py:2910-2916`) nunca era alcançada por link da tela. O resíduo era
o **seletor de datas** enumerando dias de ofertas alheias.

**Fix.** Zerar `datas` e `meses` **só no ramo do professor** sob `exigir_escolha`,
alinhado ao texto da tarefa ("2+ ofertas **próprias**") e consistente com
`alunos`/`temas` já zerados. Importante: `exigir_escolha` também vale para
admin/pedagógico (2+ ofertas da turma, nenhuma escolhida) — nesses perfis a rota
**não vaza oferta alheia** (não há restrição por professor) e a decisão V3a
explícita é **manter a união** da turma, coberta por
`test_seletor_data_oferta.py::test_sem_oferta_escolhida_seletor_segue_com_uniao`.
Por isso o zeramento é condicionado a `role == PROFESSOR`, não a `exigir_escolha`
a secas:

```python
if exigir_escolha:
    ctx['alunos'] = []
    ctx['temas'] = []
    if current_user.role == UserRole.PROFESSOR:
        ctx['datas'] = []
        ctx['meses'] = []
```

Zeramento restrito ao **professor** em `exigir_escolha`; admin/pedagógico etc.
em `exigir_escolha` seguem com a união da turma (V3a) e o caso "oferta
escolhida/única" fica inalterado para todos (a escolha da oferta reabre o
calendário pela oferta).

**Testes.**

- `test_item2_exigir_escolha_gera_zero_link_de_impressao` — pA em T2 (D+E,
  nenhuma escolhida): 200, "Selecione o curso" presente, **nenhum** `Pauta de` /
  `imprimir-pauta` no HTML.
- `test_item2_exigir_escolha_zera_datas_e_meses` — nenhum `<option>` de data
  ISO no seletor; aparece "Nenhuma aula disponível".
- `test_item2_apos_escolher_oferta_calendario_voltou` — escolhida a oferta D, o
  calendário reaparece e **todo** link de impressão leva `turma_curso` (o que
  prova que nenhum link sai sem o parâmetro e, portanto, nenhum dá 403).

**Reversão.** No worktree, `test_item2_exigir_escolha_zera_datas_e_meses`
**falha** (as datas da união apareciam); os outros dois de item 2 passam (a
proteção de link já existia via G1-4), registrando que a correção de hoje é de
calendário + prova anti-403, não um 403 novo.

**Nota de escopo (primeira suíte completa).** A versão inicial do fix zerava
`datas`/`meses` para qualquer perfil em `exigir_escolha`, o que quebrou
`test_sem_oferta_escolhida_seletor_segue_com_uniao` (admin deve manter a união —
decisão V3a). O fix foi restringido a `role == PROFESSOR`; a suíte final roda
verde com a união do admin preservada e o item 2 do professor zerado.

---

## 3. `detalhe.html` — centro de custo da oferta principal alheia

**Contexto.** O card do topo (`detalhe.html:14`) mostrava
"Centro de custo compartilhado: `oferta_principal.centro_custo` (ou 'Não
definido')". `oferta_principal` vem das ofertas ativas da turma (`turmas.py`),
**não** é escopado ao professor. Quando a principal é de outro professor, a tela
dele ou revela o `centro_custo` alheio, ou — se a principal não tem CC — mostra
"Não definido", que ainda informa que existe uma oferta principal de terceiro.
O relatório do AJ6-B3 (§1.2, M3) tinha deixado isso como aceito; o AJ6-B4
reverte esse julgamento.

**Fix.** O router calcula uma flag pela **regra central** `professor_pode_acessar_oferta`
(demais perfis → `True`, inalterado) e o template oculta o campo inteiro quando a
principal não é do professor:

```python
# turmas.py (ver_turma)
oferta_principal_do_professor = professor_pode_acessar_oferta(
    current_user, oferta_principal
)
```

```jinja
{% if oferta_principal_do_professor %}
<p class="mb-1"><strong>Centro de custo compartilhado:</strong> {{ ... }}</p>
{% endif %}
```

Não se toca em `oferta_principal` em si (o badge "Principal" dos cards continua
por id e, para o professor, os cards já são filtrados por AJ6-B3).

**Testes.**

- `test_item3_professor_nao_ve_cc_de_oferta_principal_alheia` — T3 com principal
  de pB (`centro_custo="CC-SECRETO"`) + oferta de pA: pA entra por adesão (200)
  mas o HTML **não** contém `CC-SECRETO` nem o rótulo "Centro de custo
  compartilhado".
- `test_item3_admin_ve_centro_de_custo_normal` — admin vê o rótulo e o
  `CC-SECRETO` (não-professor inalterado).

**Reversão.** No worktree, o teste do professor **falha** com `vaza centro de
custo da oferta principal alheia`; o de admin passa.

---

## 4. `/turma` (lista) — NÃO tocado

A lista `/turma` (rota `turma`) **não foi alterada** nesta etapa: a decisão do
responsável sobre filtrar ou não a lista por professor continua **pendente**. O
estado atual é o já registrado no backlog como pendência do ciclo
("/turma sem filtro por professor — decisão: manter"). A régua de entrada da
ficha individual (`ver_turma`) continua por oferta (AJ6-B3); o que está em
aberto é apenas a **lista** de turmas para o perfil professor. Registrado aqui
para fechar o item 4 sem mudança de código.

---

## 5. Verificação

- **Reversão em `git worktree`** (caminho absoluto `D:/pautaon/.tmp/aj6b4_wt`,
  em `5820fa0` sem o fix; removido ao final): os testes negativos dos itens 1, 2
  e 3 **falham** no código antigo; os controles (admin/não-professor) e o
  snapshot **passam** → os fixes só alteram o ramo do professor.
- **Ruff** `F821,F811,F841,F401` nos `.py` tocados
  (`alunos.py`, `core.py`, `turmas.py`, os dois testes): **All checks passed!**
- **Suíte completa:** `1504 passed, 0 failed, 0 skipped` em 1365s (0:22:45). O
  `1 skipped` da AJ6-B3 (era o `test_snapshot_ver_turma_nao_professor` sob
  `skipif`) **desapareceu** — o teste agora roda como golden e passa; o salto
  1495 → 1504 é a soma dos testes novos (item 1/2/3) e do snapshot que deixou de
  ser pulado. **Nenhum** teste ficou `SKIPPED` nesta execução.
- **Contagens dos bancos reais** (SELECT-only, `pautaon` e `pautaon_ensaio`,
  18 tabelas + 8 sequências + campos compostos): antes/depois **IDÊNTICAS**
  (`.tmp/aj6b4_counts_before.json` vs `.tmp/aj6b4_counts_after.json`) — as
  correções são só de leitura (ramos `GET`), nenhuma escrita em banco real.
- **`git status`:** limpo ao final (commits `test` → `fix` → `docs`); sem
  migration, sem push, sem worktree residual.
