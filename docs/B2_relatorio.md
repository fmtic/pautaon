# ETAPA B2 — D4 fechado, campo de programa removido da tela de nova turma, falhas de `/cursos` investigadas

Data: 25/10/2026 · Ramo: `Onda4` · Escopo alterado: `tests/test_turma_curso_edicao.py`, `tests/test_security_regressions.py`, `app/templates/turmas/nova_turma.html` · **Nenhum commit foi feito.**

> `tests/_helpers.py` **não foi alterado** (motivo em §3.4). Nenhuma linha de `app/` fora do template citado foi tocada.

---

## 1. Leitura prévia (Passo 1)

- **`docs/B1_relatorio.md` §8** (Pare da D4): `test_edicao_duas_ofertas_ignora_campos_de_oferta` (L236-261) afirmava `turma.programa == "Esporte"` — valor do formulário — no ramo 2+ ofertas, contra o MER §8.10 L972/L979 (`Turma.programa` é projeção da oferta principal ativa; com 2+ ofertas o cadastro grava só nome/período/ordenação). A correção P4 da B1 (`sincronizar_programa_turma` no ramo 2+, `turmas.py:1226-1229`) fez a semente (oferta principal `programa="Teste"`) projetar `"Teste"` → falha `assert 'Teste' == 'Esporte'`.
- **`docs/B1_relatorio.md` §10**: D1 (campo de programa na tela de nova turma só vale em POSTs com curso; decidir remover/restaurar), D4 (premissa de teste × MER; alta), D5 (as 2 falhas de `/cursos`, `tests/test_security_regressions.py:482,512` — "isolamento de unidade 403→200" e "validação de carga horária 400→200").
- **`tests/test_security_regressions.py`**: fixtures `app`/`client` (L16-35) — app SQLite em memória com `with test_app.app_context(): yield` (o AppContext fica aberto durante o teste; é a armadilha do T1 §5.6). `_criar_admin_cursos` (L437-468): 2 unidades, **um único usuário** `role="admin"` (sem `unidade_id`), 2 cursos (A na unidade A, B na unidade B), sessão injetada com `_user_id` do admin e `unidade_id=unidade_A`. Os 2 testes falhos usam sempre esse mesmo admin — **não há troca de usuário nem segundo cliente dentro do teste**; o que existe no meio do 1º teste é `sess.pop("unidade_id")` (troca de *unidade*, não de usuário).
- **Rotas `/cursos`** (`app/registros/core.py` L513-709): `listar_cursos` (sempre filtra pela unidade da sessão, mesmo para admin), `novo_curso` (trata só `nome`/`descricao`; ignora qualquer outro campo), `editar_curso` (L602 aceita ADMIN/PEDAGOGICO/SECRETARIA/GERENCIA e, em **L606-607, isenta ADMIN e GERENCIA do `assert_unidade_context`**), `inativar_curso`/`reativar_curso` (sem isenção: `assert_unidade_context` incondicional). `get_unidade_id` (`app/utils/logica.py:171-192`): para admin/gerência lê a sessão; para perfis operacionais força a unidade do usuário. `UserRole` é `str`-enum (`app/models/enums.py:77`), então `role="admin"` casa com `UserRole.ADMIN` — os checks de papel funcionam como escritos.
- **Estado do modelo**: `Curso` (`app/models/pedagogico.py:18-31`) **não tem coluna `carga_horaria`** — removida na Onda 3C (migration `d1e2f3a4b5c6`; MER L962: "Curso **não possui** carga horária", L1104). A C.H. é calculada por turma/oferta.

---

## 2. Passo 2 (D4) — `tests/test_turma_curso_edicao.py` (+7/−4)

- **L9-10 (docstring do módulo)**: `- 2+ ofertas: campos de oferta enviados são IGNORADOS; só nome/programa gravam.` → `... só o nome grava na turma — programa é projeção da oferta principal ativa (MER §8.10).`
- **L236 (comentário do bloco)**: `só nome/programa gravam` → `nome grava; programa é projeção`.
- **L247-251 (asserção)**: `assert turma.programa == "Esporte"` → `assert turma.programa == "Teste"` (a projeção da oferta principal da semente), com comentário explicando que o "Esporte" do formulário é descartado.
- **Nenhuma outra asserção tocada** (nome, campos de oferta ignorados na turma, ofertas inalteradas — todas já passavam).

Resultado: `test_edicao_duas_ofertas_ignora_campos_de_oferta` **passa**; o arquivo fecha 12/12.

## 3. Passo 3 (D1) — `app/templates/turmas/nova_turma.html` (−16)

Removido o bloco "Linha 2: Programa da oferta inicial" (`<select name="programa">` + `form-text`) adicionado na B1. **Rota intacta**, como ordenado: `turmas.py:811-814` continua exigindo programa quando o POST traz `curso_id` (a tela simplificada não coleta curso, portanto o fluxo com curso segue pelo programa/professional via "Cursos da Turma"/fluxo programático). O `programas=programas` no `render_template` (L886) permanece — a Jinja simplesmente não usa a variável; remover exige tocar a rota (fora do escopo) e ficou como resíduo registrado em §6. Como a adição (B1) e a remoção (B2) têm mesmo tamanho, o arquivo voltou byte a byte ao conteúdo de `HEAD` (não aparece em `git status`).

**Confirmação dos testes de criação de turma** (Passo 3): `test_turma_curso_fase4.py` e `test_turma_curso_fase2.py` rodados junto com o arquivo de edição e o de segurança → **71 passed**, incluindo `test_nova_turma_com_curso_gera_uma_oferta_principal_false` e `test_frequencia_lancada_em_turma_nova_grava_turma_curso_id` (POSTs programáticos que já enviam `programa` no form). `test_nao_permite_vincular_curso_inativo_a_nova_turma` (segurança) também passa.

---

## 4. Passo 4 — as 2 falhas de `/cursos`: investigação e conclusão

**Hipótese do vazamento de harness (T1 §5.6) foi testada e descartada para as duas falhas.** Os dois testes usam um único usuário e um único cliente; ainda assim apliquei o método prescrito (requests isolados em contexto novo, app intocado) com uma sonda temporária `tests/test_tmp_probe_cursos_b2.py` (criada, executada e **apagada** ao final), que monta 2 unidades + 2 cursos e dispara cada requisição como **primeira request do cliente**:

| Sonda | Request (1ª do cliente) | Resultado |
|---|---|---|
| 1 | `POST /cursos/<curso_b>/editar` json `{"nome": "Alterado", ...}` — **admin**, sessão unidade A | **200** e `curso_b.nome == 'Alterado'` no banco |
| 2 | mesmo POST — **secretaria** vinculada à unidade A | **403** e `curso_b.nome == 'Curso B'` (intocado) |
| 3 | `POST /cursos/novo` json `{"nome": "Carga inválida", "carga_horaria": "inválida"}` — admin | **200**, curso **criado**, `hasattr(curso, "carga_horaria") is False` |

### 4.1 Falha de isolamento (`assert 200 == 403`, L482) — **defeito real; Pare**

A causa **não** é o harness: a sonda 1 reproduz 200+gravação na primeira request, com o usuário certo (admin). É comportamento deliberado da rota: `editar_curso` (`core.py:606-607`) **isenta ADMIN e GERENCIA** do `assert_unidade_context`. A sonda 2 prova que o isolamento funciona para os papéis operacionais.

- **Reprodução mínima**: app com unidade A e B, `admin` logado com `sessão.unidade_id = A`; `POST /cursos/<id do curso B>/editar` com `{"nome": "Alterado"}` → esperado pelo teste: **403**; obtido: **200** e o curso B **é renomeado** no banco.
- **A rota vaza dados de outra unidade?** **Escreve**, sim: altera `nome`/`descricao` de curso de outra unidade (e o JSON da resposta ecoa esses dados da outra unidade — vazamento de leitura menor, só dos campos do próprio curso). **Não lista**: `GET /cursos` continua filtrado pela unidade da sessão mesmo para admin (L522), e `inativar`/`reativar` **não** têm a isenção — ou seja, a rota está **inconsistente com as vizinhas**. Há um segundo ponto da mesma divergência dentro do próprio teste: L493-494 (sem `unidade_id` na sessão, editar curso da própria "unidade" espera 403) também não é alcançada hoje porque o teste morre em L482.
- **Conforme a ordem (b): PAREI, não corrigi o app e não alterei o teste.** Ele permanece **fallando de propósito** como bandeira do defeito. Exige sua decisão de negócio: (i) admin/gerência *pode* editar curso cross-unit (aí o teste e a inconsistência com `inativar`/`listar` é que devem ser revista) ou (ii) o isolamento vale para todos (aí se remove a isenção em `core.py:606-607`).

### 4.2 Falha de carga horária (`assert 200 == 400`, L512) — **premissa obsoleta do teste; corrigido só o teste**

Também não é harness (sonda 3: primeira request, mesmo resultado). Mas **não é defeito da rota**: `Curso.carga_horaria` foi **removida do modelo e do banco na Onda 3C** (`d1e2f3a4b5c6`; MER L962/L1104) — a rota corretaamente não valida nem persiste um campo que não existe mais, e a resposta do editar sequer tem a chave `carga_horaria` (o teste KeyError-aria na L520 se a L512 passasse). O teste é que nasceu antes/à margem da migração.

Correção em `tests/test_security_regressions.py` (+12/−8), somente neste teste:
- renomeado `test_curso_criar_editar_inativar_e_validar_carga_horaria` → **`test_curso_criar_editar_inativar`**, com comentário citando a Onda 3C/MER;
- removido o POST "Carga inválida" com `assert 400` (manter 400 exigiria alterar a rota — proibido);
- no lugar, travado o contrato real: `carga_horaria` no payload é **descartado** (`assert not hasattr(curso, "carga_horaria")`);
- `assert response.json["carga_horaria"] == 60` → `assert response.json["success"] is True` (a chave não existe na resposta da rota).

### 4.3 `tests/_helpers.py` — por que não foi tocado

A extração do padrão de isolamento só seria útil no cenário (a) (testes que trocam de usuário no mesmo teste). A varredura de §5 não encontrou **nenhum** caso desses; os 2 testes de `/cursos` usam um usuário só. Não há padrão a extrair — nenhum benefício em mexer no arquivo.

---

## 5. Varredura: testes que trocam de usuário dentro do mesmo teste

Método: script AST temporário (`_scan_b2.py`, apagado) sobre `tests/test_*.py`, contando **por função de teste**: atribuições a `["_user_id"]`, chamadas diretas de `test_client()`/`login_user()`/POST `/login`, e chamadas de helpers de módulo que montam identidade transitivamente (`_loga`, `_lista`, `_post_edit`, `_get_edicao`, `_post_nova_turma`, `_criar_admin_cursos`, `_client_admin` etc.), com threshold "identidade estabelecida 2+ vezes".

- **Zero funções** com ≥2 atribuições de `_user_id` (a forma canônica de troca de usuário).
- 9 candidatos sinalizados, **todos inspecionados e inocentados** — são re-login do **mesmo** usuário em cliente novo (nada de vazamento; a identidade medida é a correta):
  - `test_bi_indicadores.py::test_indicadores_de_status_isolam_unidade_do_usuario_na_rota` (1 cliente + forja de sessão do mesmo pedagógico);
  - `test_pauta_professor.py::test_professor_pauta_mostra_somente_alunos_da_turma_associada` e `::test_professor_nao_acessa_pauta_de_turma_de_outro_professor` (idem, mesmo professor; o "outro professor" nunca loga);
  - `test_turma_curso_edicao.py::test_edicao_uma_oferta_com_lancamentos_exige_confirmacao` e `::test_g3_oferta_desativada_e_ativa_hidden_e_ativa_e_nome_aceito` (`_post_edit`/`_get_edicao` 2× com o mesmo `resp`);
  - `test_turma_curso_fase3.py::test_rota_oferta_nova_conflito_com_aviso` (cliente + sessão do mesmo admin);
  - `test_turma_curso_fase4.py::test_frequencia_lancada_em_turma_nova_grava_turma_curso_id` (`_post_nova_turma` + `_loga`, mesmo `resp`);
  - `test_turma_curso_lista.py::test_filtro_turno_e_dia_da_segunda_oferta_encontram_turma` e `::test_min_ch_total_usa_oferta_principal` (`_lista` 2×, mesmo `resp`).
- `test_transferencia_oferta.py`/`test_enturmacao_oferta.py` já seguem o padrão "um usuário por teste" que o T1 §5.6 estabeleceu.

**Conclusão: a suíte não contém, hoje, teste que troque de usuário dentro do mesmo teste.** A armadilha do §5.6 permanece relevante só para testes *futuros* (e a pendência P7 do T1 — conftest único — continua aberta).

---

## 6. Decisões que tomei sozinho

1. **Deixei `test_cursos_exigem_unidade_e_isolam_cursos_de_outra_unidade` falhando**, como manda a alínea (b) do passo 4: é defeito real na rota e a falha é a bandeira. Não "comentei" nem "skippei" o teste.
2. **Classifiquei a falha da carga horária como premissa obsoleta de teste** (nem harness, nem app): evidência direta no modelo (`Curso` sem coluna), na migration `d1e2f3a4b5c6` e no MER L962. Corrigi só o teste, travando o comportamento real da rota em vez de apagar silenciosamente a cobertura.
3. **Renomeei o teste de carga** (sufixo `_e_validar_carga_horaria` era uma mentira após a Onda 3C).
4. **Não usei `pytest.mark.xfail`** na falha de isolamento: obscurece o defeito e some quando a rota for corrigida por acidente; a falha explícita é o sinal pedido.
5. **Mantive o `programas` no `render_template` de `nova_turma`** (rota intocável por ordem expressa); o template novo simplesmente ignora a variável. Resíduo inofensivo — ver pendência R2.

## 7. Pendências

| # | Pendência | Onde | Tipo | Prioridade |
|---|---|---|---|---|
| R1 | **Defeito real `/cursos`**: `editar_curso` isenta ADMIN/GERENCIA do isolamento de unidade, divergindo de `listar_cursos`/`inativar`/`reativar`. Administrador com sessão em A **escreve** (e ecoa) curso de B. Decidir a regra (negócio) e então corrigir a rota *ou* o teste. Reprodução em §4.1. | `app/registros/core.py:606-607`, `tests/test_security_regressions.py:471-495` | Segurança/defeito | **Alta — única falha da suíte** |
| R2 | Resíduo da remoção do bloco D1: `programas=list(_PROGRAMAS_OFERTA)` (L879/886) continua sendo passado a um template que não o usa; e a rota exige programa em POST com curso sem que a tela o ofereça (fluxo só programático). Limpar quando for autorizado tocar a rota. | `app/registros/turmas.py:879,886` | Dívida | Baixa |
| R3 | Reabrindo a D1 da B1 com o desfecho B2: a tela de nova turma voltou ao estado simplificado (nome+período); quem cria turma **pela tela** nunca passa curso na primeira oferta — o curso/programa entram depois, em "Cursos da Turma". Se quiser criação com curso direto na tela, é nova UI (não decidida aqui). | `app/templates/turmas/nova_turma.html` | UX (registrada) | — |
| R4 | Da B1, permanecem: D3 (turma sem período some na listagem com filtro default do ano), D5→agora R1, D6 (lista de programas duplicada em `ofertas.html`), D7 (avisos transientes), D8/P7 (conftest único para matar a armadilha §5.6 em testes futuros). | vário | Dívida | como na B1 |
| R5 | Lint pré-existente, não tocado: `I001` (ordenação de imports, `test_security_regressions.py:1-9`) e `F401` (`import pytest` não usado, `test_turma_curso_edicao.py:18`). Nenhum diagnóstico novo nas minhas linhas. | `tests/` | Dívida | Baixa |

---

## 8. Testes

Comando (PowerShell, raiz do repositório):

```powershell
$env:PYTHONPATH="."
.\.venv\Scripts\python.exe -m pytest tests -q --tb=line
```

| Momento | Passed | Failed |
|---|---|---|
| partida (fim da B1) | 218 | 3 |
| após B2 | **220** | **1** |

**Linha de resumo do pytest:** `1 failed, 220 passed, 42 warnings in 27.55s`

A falha restante é `test_security_regressions.py::test_cursos_exigem_unidade_e_isolam_cursos_de_outra_unidade` — **defeito real da rota R1, mantido como bandeira por ordem do passo 4(b)**. Contagem por arquivo dos tocados: `test_turma_curso_edicao.py` 12 passed · `test_security_regressions.py` 21 passed, 1 failed · criação de turma (`fase4`/`fase2`): todos passed. Sonda temporária e script de varredura foram executados e apagados; `git status` não mostra resíduo meu fora dos 3 arquivos do escopo (o template de nova turma voltou ao conteúdo de `HEAD` pela simetria +16/−16 com a B1). CRLF preservado nos 3 arquivos (contagem de `\r\n` = nº de linhas). Nenhum commit feito.
