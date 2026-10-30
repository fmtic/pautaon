# Abas persistentes (Planejamento e Conselho de Perguntas)

**Data:** 28/10/2026
**Escopo:** manter a aba ativa (e o contexto da lista) após qualquer escrita nas duas telas com abas do sistema.
**Natureza:** somente UI/rotas de retorno. **Nenhuma migration, tabela, coluna, permissão ou regra de negócio foi alterada.**

## 1. Problema

As abas são componentes client-side do Bootstrap (`data-bs-toggle`), então o estado "aba ativa" existia apenas no DOM. Toda escrita terminava em `redirect(url_for(...))` para a rota "limpa", e o template reabria sempre na primeira aba:

| Tela | Abas | Antes |
|---|---|---|
| Planejamento (`registros.planejamento`) | Temas · Valores do Esportista · Níveis | Sempre Temas |
| Conselho de Perguntas (`conselho.gerenciar_perguntas`) | Etapa: Inicial · Percurso · Final, com foco Geral (Turma) · Individual (Aluno) | Sempre Inicial + Turma |

Levantamento: `data-bs-toggle="pill"` só aparece em `planejamento/planejamento.html`; `data-bs-toggle="tab"` só em `conselho/perguntas.html`. Não há outra tela com abas no sistema.

## 2. Contrato do padrão

1. O estado ativo vive na **querystring**, validado no servidor por whitelist.
2. Cada formulário de escrita envia a origem em hidden (ou o dado que define a aba, no caso de "salvar pergunta").
3. Um helper de retorno monta o `redirect` com a querystring; valor inválido/ausente cai na aba padrão, reproduzindo o comportamento antigo.
4. O `GET` valida os parâmetros e passa a variável de aba ativa ao template, que aplica `active`/`show active`.
5. Nada de `session`, `localStorage`, hash (`#`) ou JavaScript novo — a URL reflete a tela, permite favoritar e é testável em pytest.

## 3. Planejamento (já entregue)

`?aba=temas|valores|niveis`; helper `_voltar_planejamento()` (`app/registros/core.py`); os 3 formulários da aba Temas também devolvem `curso_id`, `q` e `page`. Detalhe completo em `docs/Relatórios/A1_ValoresDoEsportista.md` (§9).

## 4. Conselho de Perguntas

**Parâmetros:** `?etapa=inicial|percurso|final` e `?foco=turma|aluno`. Defaults: `inicial` + `turma` (idêntico ao comportamento anterior).

**Rotas (`app/conselho.py`)**

- `_aba_pergunta_etapa()` / `_aba_pergunta_foco()` — normalizam e validam (qualquer outro valor → `None`).
- `_voltar_perguntas(etapa=None, foco=None)` — usa os argumentos explícitos; sem eles, lê `aba_etapa`/`aba_foco` do formulário; monta `url_for('conselho.gerenciar_perguntas', etapa=..., foco=...)`.
- `gerenciar_perguntas` (GET) — calcula `etapa_ativa` e `foco_ativo` e envia ao template.
- `salvar_pergunta` (POST) — volta para a aba **da pergunta gravada** (`etapa`/`tipo` escolhidos no modal), e não para a aba de onde o modal foi aberto. Se o usuário move a pergunta de etapa/foco, ele vê o resultado no lugar certo.
- `excluir_pergunta` (POST) — volta para a aba de origem, enviada em hidden pela linha da tabela.

**Template (`app/templates/conselho/perguntas.html`)**

- Abas de etapa: `{% if etapa_ativa == etapa_id %}active{% endif %}` / `show active` no painel.
- Pills de foco: `{% if foco_ativo == 'turma' %}...{% endif %}` e `aluno`; painéis `show active` correspondentes.
- Formulários de exclusão (nas tabelas Turma e Aluno) recebem `aba_etapa`/`aba_foco` com os valores da própria pergunta (`p.etapa.value|lower`, `p.tipo.value|lower`).

## 5. Arquivos alterados

- `app/registros/core.py` — `_voltar_planejamento()` e `aba_ativa` no GET (etapa anterior).
- `app/templates/planejamento/planejamento.html` — pills/painéis condicionais + hiddens (etapa anterior).
- `app/conselho.py` — helpers `_aba_pergunta_etapa`/`_aba_pergunta_foco`/`_voltar_perguntas`, `etapa_ativa`/`foco_ativo` no GET e retorno de salvar/excluir.
- `app/templates/conselho/perguntas.html` — etapa/foco condicionais + hiddens de exclusão.
- `tests/test_planejamento_abas.py` (10 testes) e `tests/test_conselho_perguntas_abas.py` (8 testes).
- `app/models/MER.md` §9.3 e cabeçalho; `backlog_desenvolvimento.md`.

## 6. Decisões

1. **Querystring em vez de sessão/localStorage** — determinístico, testável e sem estado implícito entre requisições (alternativas C e D foram descartadas na análise).
2. **Sem fragmento (`#tab...`)** — o hash não chega ao servidor e exigiria JS para ativar a aba; a querystring mantém o render no servidor.
3. **Salvar pergunta → aba do dado salvo** (e não a de origem): o modal permite trocar etapa/foco; voltar para a origem esconderia o resultado da edição.
4. **Excluir pergunta → aba de origem** (hidden na linha): a exclusão não muda etapa/foco, então o usuário permanece no contexto em que estava.
5. **Whitelist em todas as leituras** — `etapa`/`foco`/`aba` nunca são repassados crus para a URL nem para o template.
6. **Compatibilidade** — `GET /conselho/perguntas` e `GET /planejamento` sem parâmetros renderizam exatamente como antes; testes existentes não mudaram.

## 7. Testes

`tests/test_conselho_perguntas_abas.py` (8): salvar nova pergunta abre a aba da pergunta (Percurso/Aluno); editar move para a nova aba (Final/Turma); excluir volta para a origem e a pergunta some; excluir sem contexto usa o padrão; `?etapa=&foco=` válidos abrem a aba; valores inválidos e ausência caem em `inicial`/`turma`; professor recebe 403 no GET e no POST.

**Suíte:** 783 → **791 passed**, 0 falhas. Nenhum teste existente foi alterado (`test_conselho_ui.py` e `test_conselho_oferta.py` continuam verdes).

## 8. Limitações / observações

- `ruff check` aponta `I001` no bloco de imports de `app/conselho.py` e `F401` em `app/registros/core.py` — **pré-existentes**, fora do escopo; `F821`/`F811` estão limpos.
- A aba ativa não sobrevive a mudanças manuais de URL sem os parâmetros: nesse caso o padrão (`inicial`/`turma`, `temas`) é aplicado de propósito.
- Se uma nova tela ganhar abas com formulários, deve seguir o contrato da §2 e registrar a convenção em MER §9.3.

## 9. Como validar manualmente

1. Conselho → Gerenciar Perguntas → aba **Percurso** + **Individual (Aluno)** → *Nova Pergunta* (etapa Percurso, foco Aluno) → salvar: a tela volta nessa aba com a pergunta listada.
2. Editar a mesma pergunta para **Final/Turma** → salvar: a tela abre em Final + Geral.
3. Excluir uma pergunta pela aba Final + Individual → a tela permanece nessa aba.
4. Abrir `/conselho/perguntas?etapa=final&foco=aluno` direto: a aba correta vem ativa.
5. Repetir o roteiro do Planejamento (ver `A1_ValoresDoEsportista.md` §9).
