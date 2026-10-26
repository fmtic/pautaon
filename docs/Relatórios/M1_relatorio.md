# Relatório — Etapa M1: Enturmação por curso (oferta)

Data: 24/10/2026 · Escopo autorizado: rota/serviço de enturmação, `adicionar_oferta`, template de enturmação, lista de alunos de `detalhe.html`, `tests/test_enturmacao_oferta.py` (novo) e — liberado pelo responsável em perguntei — semente de `tests/test_security_regressions.py`. Sem commit.

---

## 1. Resultado da leitura (passo 1)

**Rota que cria a inscrição (enturmar aluno):**
- `app/registros/turmas.py` — `enturmar_alunos(turma_id)`, `POST /turma/enturmar/<int:turma_id>` (antes da etapa em L604-663; hoje L644-737).
- Criava `Inscricao(aluno_id, turma_id, nivel, ativo=True, data_inicio=hoje)` **sem gravar `turma_curso_id`** (ficava NULL).
- **Duplicidade antes:** bloqueava por **aluno + turma** (`filter_by(aluno_id, turma_id, ativo=True)`), independentemente de oferta.
- **Perfis:** ADMIN, PEDAGOGICO, SECRETARIA, GERENCIA (403 fora disso); isolamento por unidade via `get_unidade_id()` + `assert_unidade_context(turma_obj.unidade_id, unidade_id)` — mantidos como estavam.

**Como lista os alunos disponíveis:**
- `ver_turma(id)` (`app/registros/turmas.py` L547) consultava `Aluno` ativos da unidade **sem** qualquer filtro por oferta, e passava `alunos_sem_turma` ao template.

**Template de enturmação:** não existe página separada — o modal "Enturmar alunos" está dentro de `app/templates/turmas/detalhe.html` (ficha da turma), com checkbox por aluno e botão de envio do form para `/turma/enturmar/<id>`.

**Chamadores da rota/função de gravação:**
- A **única** rota que POSTa em `/turma/enturmar/...` é o modal de `detalhe.html`.
- `transferir_aluno` (`app/registros/alunos.py` L926) **não** chama `enturmar_alunos` nem a mesma função de gravação: cria seu próprio `Inscricao(...)` inline (L1037, com `turma_curso_id` NULL). O alerta de "PARE" do passo 1 (função de gravação compartilhada) **não disparou**; transferência ficou intacta.
- Imports de alunos não criam inscrições.

---

## 2. Diff resumido (arquivo → função/alteração)

| Arquivo | Função / bloco | O que mudou |
|---|---|---|
| `app/registros/turmas.py` | `enturmar_alunos` | Regras 0/1/2+ ofertas na resolução de `oferta_id`; flash exato para 0 ofertas; exigência e validação de `turma_curso_id` com 2+ (precisa estar em `ofertas_ativas(turma)` → pertence à turma, está ativa, unidade implícita pela turma); duplicidade agora por **aluno + turma + oferta**; grava `turma_curso_id` na inscrição |
| `app/registros/turmas.py` | `ver_turma` | Resolve `ofertas_lista`/`oferta_sel` (1→ela; 2+→`?oferta_sel=` com fallback na primeira; 0→None); lista de disponíveis passa a excluir só quem já tem inscrição **ativa naquela oferta**; monta `cursos_por_aluno` (curso de cada matriculado, por oferta); repassa `ofertas`, `oferta_sel`, `cursos_por_aluno`, `abrir_modal_enturmar` ao template |
| `app/registros/turmas.py` | `turma_oferta_nova` | Flash extra informando quantas inscrições NULL ativas foram vinculadas (`oferta.inscricoes_vinculadas`) |
| `app/services/turma_curso.py` | `adicionar_oferta` | Captura `Inscricao` **ativas com `turma_curso_id` NULL** da turma e as ofertas ativas **antes** da criação; na mesma transação vincula as NULL ao destino inequívoco (1 oferta pré-existente → ela; 0 → a nova oferta; 2+ → não mexe); inativas intocadas; marcador transitório `inscricoes_vinculadas` |
| `app/templates/turmas/detalhe.html` | Modal de enturmação | 2+ ofertas: `<select name="turma_curso_id">` com **nome, turno e horário** da oferta antes da lista, recarregando com `?oferta_sel=&modal=enturmar` (lista de disponíveis reage à escolha; modal reabre via JS); 0 ofertas: aviso fixo no modal e botão desabilitado; envio sem escolha em 2+ é barrado no servidor |
| `app/templates/turmas/detalhe.html` | Lista de matriculados | Com 2+ ofertas, selo com o nome do curso de cada aluno (aluno em dois cursos aparece com os dois selos) |
| `tests/test_enturmacao_oferta.py` | (novo) | 11 cenários do passo 6 |
| `tests/test_security_regressions.py` | Semente de `test_perfis_autorizados_podem_enturmar_na_propria_unidade` | Turma da semente ganhou 1 oferta ativa (Curso "Natação") — liberação explícita do responsável via pergunta |

## 3. Testes (`tests/test_enturmacao_oferta.py`)

1 oferta grava sem escolha · 0 ofertas recusa e não grava · 2 ofertas sem escolha recusa · 2 ofertas com escolha grava na apontada · oferta de outra turma recusada · oferta desativada recusada · mesmo aluno nas duas ofertas permitido (2 inscrições ativas) · duplicata na mesma oferta recusada · `adicionar_oferta` vincula NULL ativas à oferta pré-existente (inativa fica NULL; marcador == 1) · enturmado aparece em `_alunos_da_oferta` da oferta correta e não na outra · usuário de outra unidade → 403.

## 4. Decisões que tomei sozinho

- **Seletor com reload + reabertura do modal** (`?oferta_sel=&modal=enturmar`): a lista de disponíveis é renderizada no servidor; optei por GET em vez de AJAX para não tocar outros arquivos.
- **Oferta desativada ou de outra turma** reusa o mesmo flash de "Selecione o curso (oferta)…", pois `ofertas_ativas()` já filtra ativa+da-turma — validação única, sem mensagem nova.
- **Vínculo NULL em `adicionar_oferta` só com destino inequívoco**: com 2+ ofertas pré-existentes não altero inscrição nenhuma (vincular à "principal" seria escolha arbitrária do sistema sobre dados de legado).
- **Aluno com inscrição NULL ativa continua "disponível"** na oferta escolhida (o filtro de disponíveis é por oferta); se for enturmado de novo na mesma oferta, a duplicidade por aluno+oferta+ativa evita 2 linhas iguais — o que sobra é a NULL de legado, já coberta por `_alunos_da_oferta(incluir_inscricoes_null=)` (pendência registrada no backlog: relançar duplica).
- **Flash de sucesso** manteve o texto original (não menciona o curso) para não quebrar expectativas de testes/templates existentes.
- **Semente do teste de segurança**: como a Regra #2 faria o teste fora-do-escopo falhar, **parei e perguntei**; resposta autorizou dar 1 oferta à turma da semente (edição mínima, sem mudar a finalidade do teste de isolamento por unidade).

## 5. Pendências que vi (não corrigidas)

- **Desenturmar com aluno em 2 ofertas:** `desenturmar_aluno` ainda age por **aluno + turma** e pega a primeira inscrição ativa (`.first()`) — com o aluno em duas ofertas, desenturma apenas uma e não há como escolher qual na tela.
- **Inscrições de oferta desativada:** ficam ativas apontando para oferta inativa; somem da leitura por oferta (`_alunos_da_oferta` strict; NULL-legacy só aparece quando há exatamente 1 oferta ativa) e `desativar_oferta` não trata as inscrições dos alunos.
- **Transferência entre turmas/ofertas:** `transferir_aluno` (alunos.py L1037) cria a nova inscrição com `turma_curso_id` NULL e desativa a antiga **sem migrar a oferta** — fora do escopo M1; com 2+ ofertas na turma destino o transferido fica NULL (e some das fichas por oferta).
- **Importação/admissão:** `nova_inscricao` em `transferir_aluno` é o único outro ponto que cria inscrição; fluxos de importação não criam inscrições, mas qualquer futuro enturmamento em massa precisará aplicar a mesma regra de oferta.
- **Mensagem de sucesso do enturmar** não informa em qual curso os alunos entraram.

## 6. Verificação

- `python -c "from app import create_app; create_app()"` → OK.
- `pytest tests/test_enturmacao_oferta.py tests/test_pauta_professor.py -q` → **13 passed**.
- Suíte completa — linha de resumo:

```
2 failed, 211 passed, 39 warnings in 31.34s
```

  As 2 falhas são as preexistentes de `/cursos` (`test_cursos_exigem_unidade_e_isolam_cursos_de_outra_unidade` e `test_curso_criar_editar_inativar_e_validar_carga_horaria`); nenhuma nova.
- `ruff`: arquivo de teste novo sem avisos; turmas.py voltou à contagem baseline (21) após trocar `== True` por `.is_(True)` nas linhas novas; os demais avisos dos arquivos tocados são preexistentes (I001/E712/F811 históricos de bi_alunos/turma_curso).
