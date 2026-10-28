# M1 — Roteiro de teste manual no navegador + semente para o scratch

**Branch:** `nova_feature` · **HEAD de partida:** `a5b34c8` · **Data:** 28/10/2026
**Escopo:** geração de documento (`docs/Roteiro_Teste_Manual.md`) e script
(`scripts/semear_roteiro_manual.py`). **Nenhuma alteração em `app/`**, nenhuma migration,
nenhum push.

---

## 1. P0 — Estado inicial

| Item | Resultado |
|---|---|
| `git status` | limpo (só arquivos temporários de sondagem, não versionados) |
| Suíte | `722 passed` (baseline, sem CSRF) |
| Alembic | `pautaon` e `pautaon_ensaio` no head `8d2e3f4a5b6c` |

---

## 2. P1 — Como o app escolhe o banco (leitura) e TRAVA

### 2.1 Seleção do banco

- `config.py::_get_database_uri()` devolve `DATABASE_URL` quando presente; o módulo chama
  `load_dotenv()` **sem** `override=True`. Logo: **variável de ambiente vence o `.env`**.
- `run.py` → `create_app(Config)`; `app/__init__.py` inicializa `SQLAlchemy` com essa URI.
- Consequência prática: para rodar no ensaio basta exportar `DATABASE_URL` na sessão do shell.
  O `.env` versionado (banco principal) permanece intacto.

### 2.2 TRAVA

**Não foi acionada.** Rodar o app no scratch **não** exigiu alterar `app/` nem configuração
versionada. Nenhum arquivo fora de `scripts/`, `docs/` e do backlog foi tocado.

### 2.3 Login, perfis e unidade

- `POST /login` recebe `email`, `password` e `csrf_token`; tenta senha local (hash) e, como
  fallback, LDAP/AD. Sucesso → `login_user` + `session["unidade_id"] = user.unidade_id`
  (ou removido quando o usuário não tem unidade) → redirect `main.painel`.
- `first_login=True` (usuário local) força `/trocar-senha`; a semente cria os 5 usuários com
  `first_login=False` e senha local conhecida (`Roteiro!2026`).
- Perfis (`UserRole`): `admin`, `gerencia`, `pedagogico`, `secretaria`, `professor`.
- **Escolha de unidade:** dropdown **Unidade** na sidebar (`app/templates/partials/sidebar.html`),
  visível para `admin` e `gerencia`, apontando para `GET /trocar-unidade/<id>`; `id=0` = **Visão
  Global** (somente leitura). O admin da semente tem `unidade_id = NULL`, então **entra em Visão
  Global** e precisa escolher a unidade para escrever.
- Escritas/impressões passam por `assert_unidade_context`, que responde **403** quando a sessão está
  em Visão Global (`unidade_id is None`).

---

## 3. Como subir o app no scratch

```powershell
# 1) banco de ensaio (pautaon_ensaio já existe e está no head)
$env:DATABASE_URL = "postgresql://usuario:senha@localhost:5432/pautaon_ensaio"

# 2) semente (cria/atualiza o cenário [ROTEIRO])
.\.venv\Scripts\python.exe scripts\semear_roteiro_manual.py

# 3) app
.\.venv\Scripts\python.exe run.py
```

- Confirme na saída/console que o banco é `pautaon_ensaio` (a P4 imprimiu
  `DB efetivo: localhost:5432/pautaon_ensaio`).
- Se a porta `5000` estiver ocupada por outro processo (havia um servidor antigo apontando para o
  banco principal nesta máquina), suba em outra porta (`flask run --port 5055` ou `app.run(port=...)`)
  e ajuste `{BASE}` no roteiro. **Atenção:** um servidor já escutando na porta faz as requisições
  irem para o banco errado e o login "falhar" sem erro no log do ensaio.
- Para voltar ao principal: feche o shell (ou `Remove-Item Env:DATABASE_URL`).

---

## 4. P2 — Semente (`scripts/semear_roteiro_manual.py`)

### 4.1 Garantias

| Garantia | Implementação |
|---|---|
| Recusa banco não-ensaio | `_dsn()` lê `DATABASE_URL` (env ou `.env`), troca o banco e aborta se `"ensaio"` não estiver no nome |
| Idempotência | todo objeto é criado/atualizado por chave natural (`nome`/`email`/`(aluno, oferta, data)`); nenhum duplicado em duas execuções |
| `--limpar` | apaga **só** o rótulo `[ROTEIRO]` (usuários `*@roteiro.local`), na ordem das FKs; imprime as contagens restantes |
| Rótulo | todo nome começa com `[ROTEIRO]` (unidade, período, turma, curso, tema, pergunta, aluno) |
| Sem commit no app | o script usa uma `Config` própria com `SQLALCHEMY_DATABASE_URI` do ensaio e `WTF_CSRF_ENABLED=False` |

### 4.2 Cenário criado

- **Unidades:** `[ROTEIRO] Unidade Central` e `[ROTEIRO] Unidade Vizinha` (isolamento).
- **Usuários:** 5 perfis (`admin|gerencia|pedagogico|secretaria|professor .m1@roteiro.local`),
  senha `Roteiro!2026` impressa no final.
- **Períodos:** Vigente (01/08–31/12/2026), Encerrado (01/01–31/07/2026), Vizinha.
- **Cursos/temas/perguntas:** 4 cursos, 3 temas, 5 perguntas de conselho (INICIAL TURMA×2,
  INICIAL ALUNO×2, FINAL ALUNO), 2 opções de próxima turma, 1 centro de custo.
- **Turma A:** 1 oferta (Esporte) com grade Seg/Qua 08:00–10:00 e **frequência legada**
  (`turma_curso_id IS NULL`) — Ana A,A e Bruno F,A.
- **Turma B:** 2 ofertas de **programas diferentes** (Profissionalizante principal Seg/Qua,
  Meio Ambiente Ter/Qui 14:00–16:00) com **conceitos diferentes por oferta**; Carla e Diego
  inscritos nas duas.
- **Turma C:** grade **por dia não uniforme** (Seg 08–10, Qua 08–11, Sex 14–15:30).
- **Turma D:** exclusão lógica com **oferta desativada antes** (Horta fora do marcador) — cenário da
  lixeira/L4.1/L4.2, no período encerrado.
- **Alunos:** 11 no rótulo, incluindo **aluno transferido** (Gabriela A→C + `Transferencia`),
  **aluno desenturmado** (Heitor), **aluno inativo em conflito** (Joao D-inativo) e o aluno da
  unidade vizinha.
- **Diário e conselho:** 4 `RegistroAula` (1 legado + 3 por oferta) e conselho INICIAL concluído na
  B1 (`conselho_concluido=True`) e pendente na Turma A.

### 4.3 Idempotência e `--limpar` (P4)

Duas execuções consecutivas produziram **exatamente as mesmas contagens do rótulo**:

| unidades | usuários | períodos | turmas | ofertas | grade | alunos | inscrições | frequências | diários | conselhos | perguntas |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2 | 5 | 3 | 5 | 7 | 12 | 11 | 14 | 18 | 4 | 4 | 5 |

`--limpar` removeu **23 registros-raiz** e deixou apenas o que já existia no ensaio (2 unidades,
20 usuários, 2 períodos, 8 cursos, 3 turmas, 1154 alunos etc.).

> **O scratch não está vazio.** `pautaon_ensaio` contém dados preexistentes (NIT/MGB). Por isso o
> script separa **contagens do banco inteiro** de **contagens do rótulo**, e o roteiro sempre diz
> qual unidade selecionar antes de conferir números.

### 4.4 Saída do script

Além dos IDs e das contagens, imprime: **datas de aula semeadas**, **senha de cada perfil** e uma
lista de **URLs prontas** (login, unidade, listagem, lixeira, pauta, frequência por oferta,
conselho, histórico, ficha, certificados, relatórios, BI).

---

## 5. P3 — Roteiro

`docs/Roteiro_Teste_Manual.md`, formato `ID | perfil/unidade | URL real | passos | resultado
esperado | marcar`, com as 10 blocos obrigatórios e, em cada bloco, a indicação dos **testes
automatizados** que cobrem o mesmo comportamento e o que é **cobertura nova**.

| Bloco | Casos |
|---|---|
| 1. Login, unidade, Visão Global | 6 |
| 2. CSRF real | 8 |
| 3. Agenda por dia (H4c/H4d) | 10 |
| 4. Frequência por oferta (D3b-2.4) | 8 |
| 5. Listagem, sub-linha e `min_freq` (D3b-2.5) | 9 |
| 6. Conselho (PQ1–PQ4) | 12 |
| 7. Lixeira e reativação (L4/L4.1/L4.2) | 11 |
| 8. Histórico, ficha, certificado, relatório e BI | 13 |
| 9. Permissões (matriz de 34 rotas) | 6 |
| 10. Impressões e exportações | 10 |
| **Total** | **93** |

Todas as rotas, botões e textos citados foram conferidos nos templates
(`turmas/listar.html`, `turmas/turma_lixeira.html`, `turmas/ofertas.html`,
`turmas/_agenda_macros.html`, `frequencia/lancar.html`, `conselho/*.html`,
`periodos/certificado.html`, `relatorios/*.html`, `partials/sidebar.html`).

---

## 6. P4 — Validação executada

### 6.1 HTTP (app no ensaio, admin com a Unidade Central)

Todas as rotas alvo responderam **200** com os dados da semente:
`/login`, `/turma`, `/turmas/lixeira`, `/turma/30/imprimir-pauta`,
`/turma/31/imprimir-pauta?turma_curso=45`, `/turma/30`, `/turma/31/ofertas`,
`/turma/editar/32`, `/frequencia?turma_id=30`, `/conselho`, `/conselho/perguntas`,
`/aluno/1482/historico`, `/relatorios/alunos/1486/ficha`, `/periodo-letivo/relatorio/22`,
`/relatorios/`, `/relatorios/bi`, `/relatorios/painel`, `/alunos`, `/periodo-letivo`.

### 6.2 CSRF (token ligado no ensaio)

| Rota | Sem token | Com token |
|---|---|---|
| `POST /turma/excluir/<id>` | **400** | 302 |
| `POST /turmas/reativar/<id>` | **400** | 302 |
| `POST /turma/oferta/<id>/desativar` | **400** | 302 |
| `POST /conselho/salvar` | **400** | 302 |
| `POST /frequencia` | **400** | 302 |
| `POST /turma/enturmar/<id>` | **400** | 302 |
| `POST /aluno/excluir/<id>` | **400** | 302 |
| `POST /turma/<id>/ofertas/nova` | **400** | 200 (re-render de validação) |

### 6.3 Números: esperado (aritmética da semente) × app

| Indicador | Esperado | App (HTML/JSON) | Situação |
|---|---|---|---|
| Frequência Turma A (legado NULL) | 75,0% (3P/1F) | `75.0%` na listagem; `P: 100` Ana e `50` Bruno na frequência | OK |
| Frequência oferta B1 | 60,0% (3P/2F) | `60.0%` na sub-linha; `P 66.7/33.3` Carla (3 aulas) e `50/50` Diego (2) | OK |
| Frequência oferta B2 | 33,3% (1P/2F) | `33.3%` na sub-linha; `P 0/100` Carla (2) e `100/0` Diego (1) | OK |
| Frequência Turma B (soma) | 50,0% (4P/4F) | `50.0%` | OK |
| Frequência Turma C | 66,7% (2P/1F, 1 J fora) | `66.7%` | OK |
| C.H. Total Turma A | 88h (44×120 min) | `88h` | OK |
| C.H. Total Turma B | 176h (88h + 88h) | `176h` | OK |
| C.H. Total Turma C | 8490 min = 141h30min (22×120+22×180+21×90) | `141h30min` | OK |
| `f_prog` — Esporte / Meio Ambiente / Profissionalizante | 75,0 / 33,3 / 62,5 | `75.0% / 33.3% / 62.5%` | OK |
| `f_turma` — A / B / C | 75,0 / 50,0 / 66,7 | idem | OK |
| Frequência geral (turmas ativas) | 60,0% (9P/6F) | `60.0%` no Resumo, painel pedagógico e Desempenho por Professor | OK |
| BI FRE-009 (por turma) | A 75,0 / B 50,0 / C 66,7 | idem | OK |
| BI FRE-010 (por curso) | Horta 33,3 / Informática 62,5 / Natação 75,0 | idem | OK |
| BI FRE-005 (média global) | **60,0%** (turmas ativas) | **64,7%** | **Achado (ver 6.4)** |
| Alunos por faixa (painel) | ≥90: 2 · 75–89: 0 · <75: 4 | idem | OK |
| Enturmados no período | 7 (`contar_alunos_enturmados`) | painel mostra **6** e **7 novos** | **Achado (ver 6.4)** |
| Painel geral (unidade) | 2 períodos / 3 turmas / 9 alunos / 1 professor | idem | OK |
| Certificados | C.H. por oferta (88h/141h30min) | idem, com **Conselho: Pendente** | OK |

### 6.4 Divergências e achados

1. **Histórico do aluno ignora a frequência legada.** Ana A1: listagem `75.0%` e pauta com as
   aulas, mas `/aluno/1482/historico` mostra **0 aulas / 0.0%**. É a pendência conhecida do legado
   NULL sem backfill; o leitor por oferta não inclui linhas `turma_curso_id IS NULL`. **Não
   corrigido** (fora do escopo M1).
2. **`I: None` no histórico.** A coluna de situação imprime `None` quando não há status inicial.
3. **BI FRE-005 × Resumo.** `FRE-005` retorna **64,7%** porque `_base_frequencia` não filtra turma
   ativa e soma a **Turma D** (11P/6F); `FRE-009`, `FRE-010` e o Resumo usam 9P/6F = **60,0%**.
   Inconsistência interna do BI, registrada como achado.
4. **Painel pedagógico com dois números para "enturmados".** O bloco mostra **6** no número grande
   e **7 novos** na linha de detalhe (status do aluno × inscrições do período).
5. **Filtro *Programa* da listagem** usa a projeção `Turma.programa`; por isso **Meio Ambiente não
   encontra a Turma B** (possui a oferta, mas projeta Profissionalizante). Observação de usabilidade.
6. **Pauta em Visão Global = 403.** Admin sem unidade recebe 403 em `/turma/<id>/imprimir-pauta`
   (e em detalhe/ofertas/editar) por `assert_unidade_context`. Comportamento intencional, mas o
   roteiro precisa orientar a escolher a unidade antes de imprimir.
7. **Porta 5000 ocupada** por um servidor antigo apontando para o banco principal: durante a P4 as
   requisições "não chegavam" ao processo do ensaio (login recusado, log de falha gravado no banco
   principal). A validação foi refeita em `127.0.0.1:5055`. Registro operacional, não defeito do app.

Nenhuma outra divergência entre a aritmética independente e o app foi encontrada.

---

## 7. Validação final

| Item | Resultado |
|---|---|
| Semente rodada 2× seguidas | contagens do rótulo idênticas |
| `--limpar` | remove só o rótulo; restam apenas os dados preexistentes do ensaio |
| App no scratch (HTTP) | login, listagem, lixeira e pauta = **200** |
| CSRF | **400** sem token nas 8 rotas; token aceito nas rotas legítimas |
| Suíte completa | `722 passed` |
| `ruff check scripts/semear_roteiro_manual.py` (projeto) | *All checks passed* |
| `ruff --select F821,F811` | *All checks passed* |
| `git diff --check` | sem erros de whitespace |

**Commits (sem push):** `semente` (script) e `roteiro` (documento + este relatório + backlog).

> **Nota sobre o working tree:** durante a execução apareceram mudanças **não atribuídas a M1** em
> `app/templates/frequencia/lancar.html`, `app/templates/planejamento/planejamento.html` e no
> arquivo novo `app/templates/frequencia/lancar copy.html` (reformatação de HTML, provavelmente de
> formatador do editor). Elas **não** foram tocadas nem commitadas por esta tarefa; o commit do
> roteiro adiciona apenas `scripts/`, `docs/` e `backlog_desenvolvimento.md`.

---

## 8. O que fica para o dono da máquina

- Selecionar a **Unidade Central** antes de qualquer caso de escrita/impressão (o admin entra em
  Visão Global).
- Rodar a semente novamente depois do Bloco 7 para restaurar a Turma D na lixeira.
- Quando finalizar a bateria, `--limpar` (ou `DROP` do conteúdo do ensaio, se preferir) e conferir
  que o banco principal nunca foi tocado.
