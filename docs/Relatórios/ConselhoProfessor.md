# Conselho de classe — lançamento pelo professor (29/10/2026)

## Pedido

O professor precisa lançar o conselho de classe: responder as perguntas **individuais** (por aluno) e as **da oferta** (turma). O acesso deve sair de `Conselho > Painel de Turmas`, listando **somente as ofertas ativas em que ele é o professor**, e permitir apenas lançamento — fechar o conselho e mexer nas perguntas continuam fora do perfil.

## Decisões fechadas com o usuário

| Tema | Decisão |
|---|---|
| Escopo | **Professor da OFERTA** (`turma_curso.professor_id`), **sem** herdar o professor da turma — regra PARTE B/G1, a mesma da pauta/I1 |
| Oferta encerrada (`conselho_concluido`) | **Bloqueia** o lançamento do professor (somente leitura) |
| Etapa "Parcial" | Não existe: a etapa é **PERCURSO** e a UI mostra "Percurso"; o enum (`INICIAL`/`PERCURSO`/`FINAL`) não mudou |
| "Situação Final do Aluno" / "Encerrar conselho" | **Ocultar no painel + 403 na rota** |

## O que já existia (e foi reaproveitado)

- Painel por oferta: `index_conselho` + `ofertas_do_painel_conselho` (D5.3).
- Lançamento individual: `lancamento_conselho` (cria `ConselhoClasse` por oferta/aluno/etapa) + `salvar_conselho` (grava `ConselhoResposta`), com o padrão 0/1/2+ ofertas.
- Conselho da oferta: `avaliar_turma` já era "feito pelo professor", gravando em `TurmaCurso.avaliacao_*`; o link já sai do `lancamento.html`.
- Encerrar/reabrir: `planejamento.alternar_conselho` **já era 403** para professor.

**Nenhuma migration, tabela ou coluna nova.**

## O que mudou

### Menu

`base.html` (fonte real do sidebar) passou a incluir `professor` no bloco **Conselho**, exibindo **apenas Painel de Turmas**; `Data-Informações` e `Gerenciar Perguntas` continuam restritos a admin/pedagógico/gerência/secretaria. ~~O `partials/sidebar.html` **não é incluído por nenhum template** (partial legado) e foi mantido alinhado para não divergir.~~ — **resolvido em 29/10/2026 (T3):** o partial foi removido (menu único em `base.html`; MER §8.19, `docs/Relatórios/MenuUnicoSidebarLegado.md`).

### Escopo por oferta

- `services/turma_curso.py` → `ofertas_do_painel_conselho(professor_id=...)` usa `condicao_professor_da_oferta` (sem `or_` com `Turma.professor_id`).
- `conselho.py` → `_resolver_oferta_conselho(turma, oferta_id, professor_id)` filtra as ofertas ativas pelo professor antes de decidir 0/1/2+.
- `lancamento_conselho` lista **turmas onde ele tem oferta ativa** (join `turma_curso`) e responde **403** para turma fora do escopo.
- `_guarda_oferta_explicita_do_professor` responde **403** quando o `?oferta_sel=` / `turma_curso_id` aponta oferta ativa de outro professor (usado no GET/POST do lançamento e na avaliação).
- `avaliar_turma` deixou de checar `turma.professor_id` e passou a checar a **oferta**.

Consequências deliberadas: o professor da turma que não está na oferta **perde** o acesso; o professor da oferta **ganha**, mesmo sem ser professor da turma.

### Oferta encerrada

`_bloqueio_oferta_encerrada` intercepta antes de qualquer escrita:
- GET do lançamento → flash + volta ao painel **sem criar** `ConselhoClasse`;
- POST `salvar` e `avaliar_turma` → flash + retorno, **sem gravar**.

### Fechamento e gestão

- `fechamento_turma` (GET) → **403** para professor.
- `salvar_fechamento_data` (POST JSON) → **403** com `{"success": false}`.
- No painel, o professor não vê **Situação Final do Aluno** nem o form **Encerrar/Reabrir conselho**.

## Brechas fechadas no caminho

- `salvar_conselho` **não tinha** guarda de dono (qualquer logado gravava em qualquer oferta que passasse pela unidade).
- `fechamento_turma`/`salvar_fechamento_data` **não tinham** role guard — só a unidade. A URL direta alcançava a tela; agora 403.

## Testes

`tests/test_conselho_professor.py` — **15 testes**:

1. menu do professor (Painel presente; Data-Informações/Configurar Perguntas/Situação Final/Encerrar ausentes);
2. painel lista só a oferta dele mesmo sem ser professor da turma;
3. painel não herda o professor da turma (oferta da P1 na turma da P2);
4. admin vê tudo e mantém os botões de gestão;
5. lançamento abre a própria oferta e cria os conselhos;
6. 403 em oferta de outro professor (sem criar linhas);
7. 403 em turma sem oferta dele;
8. POST grava na própria oferta (`ConselhoResposta` + `turma_curso_id` correto);
9. POST em oferta alheia → 403 sem gravar;
10. oferta encerrada bloqueia o GET sem criar conselhos;
11. oferta encerrada bloqueia o POST sem gravar;
12. fechamento GET/POST 403 para professor;
13. fechamento continua 200 para admin;
14. avaliação da oferta abre/grava as perguntas TURMA;
15. avaliação recusa oferta alheia e turma sem oferta dele.

**Nenhum teste existente precisou de ajuste.**

Regressão dirigida (conselho, segurança, D5, harness de perfis): 77 passed.
Suíte completa: **981 → 996** testes coletados (**994 passed + 2 failed** — as duas falhas eram do `dashboard/professor.html`, alterado no working tree por terceiros, `aulas_pendentes[:5] → [:2]`; com o arquivo do HEAD as 9 do dashboard passam). Resolvido depois no commit `e5428c2`, que commitou a alteração, corrigiu o aviso do rodapé e ajustou os 2 testes: **996 passed, 0 failed**.

## Ensaio (`pautaon_ensaio`, desfeito)

Professor **Rosana Antunes** (id 88), oferta 15, turma 11 — dados que já existiam no ensaio, nada foi semeado. CSRF desligado **só no driver**; rotas e guardas reais.

- `GET /conselho` → 200, lista a oferta dela, sem "Configurar Perguntas" e sem "Situação Final do Aluno";
- `GET /conselho/lancamento?turma=11&etapa=…&oferta_sel=15` → 200 com o 1º aluno; sem "Data-Informações" no menu;
- `POST /conselho/salvar` → 302 e **1** resposta gravada na oferta;
- `GET /conselho/fechamento/11` → **403**; `POST …/salvar` → **403**; `GET /conselho/perguntas` → **403**;
- limpeza conferida: **0** respostas `[ENSAIO]` e conselhos de volta ao conjunto anterior (ids comparados antes/depois). Banco principal intocado.

## Pendências e observações

- `flask db upgrade` no principal **aplicado em 29/10/2026** (`e1f2a3b4c5d6`, modelo de certificado) — era independente desta entrega: backup em `instance/backups/pautaon_pre_modelo_certificado.sql`, 36 tabelas/2947 linhas idênticas antes e depois, estrutura conferida e `downgrade` + `upgrade` validados.
- ~~O `partials/sidebar.html` é legado; vale decidir depois se é removido ou passa a ser o único menu.~~ — **RESOLVIDO em 29/10/2026 (T3):** o partial foi **removido** e o menu de `base.html` é o único (MER §8.19).
- G1/P2 (professor obrigatório na oferta) segue parado na TRAVA.
- A edição de terceiros em `app/templates/dashboard/professor.html` não fazia parte desta entrega; ficou no working tree e depois foi commitada em `e5428c2` (limite de 2 linhas, aviso do rodapé coerente e 2 testes ajustados).
