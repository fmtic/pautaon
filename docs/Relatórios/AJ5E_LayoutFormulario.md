# AJ5-E — Melhor aproveitamento do formulário de aluno

Data: 01/11/2026 · Branch: `nova_feature` · Base: `5a0f38c` (AJ5-C1)

## 1. Objetivo e escopo

Melhorar o aproveitamento **horizontal** (largura em telas grandes) e
**vertical** (espaço morto, rolagem por passo) do formulário de aluno, sem
mudar:

- a ordem dos campos no DOM;
- os seis passos (`step-1` … `step-6`);
- os campos, `name`, `id`, `for`, valores, placeholders e textos;
- lógica, rotas, JS de comportamento (stepper, foto/webcam, uploads,
  Ver/Excluir) ou models.

A alteração é **somente de apresentação**: classes de grade/gutter/largura/
espaçamento nos templates e CSS em `app/static/css/alunos/editar.css`.
Nenhuma migration, nenhum push, nenhum dado pessoal real.

## 2. Commits

| Ordem | Commit | Assunto |
| --- | --- | --- |
| 1 | `d229704d03d3195ccdefa7c1dc2850e4cef76bc0` | `test(aj5e): trava de ordem dos campos` |
| 2 | `5eaf3f2f81705b3d0600e9a3b822dfde504ddd7c` | `style(alunos): espaçamento e largura do formulário` |
| 3 | (este relatório) | `docs(aj5e): relatório` |

O layout inteiro está **num único commit** (`5eaf3f2`), revertível com
`git revert 5eaf3f2` (ver §9.6).

## 3. Etapa 1 — trava de ordem dos campos

Arquivo novo: `tests/test_aj5e_ordem_campos.py`.

O teste renderiza as três variantes do formulário e extrai, **passo por
passo e em ordem de documento**, a lista de:

- todo controle de formulário (`input`, `select`, `textarea`, `button`) com
  `name` e/ou `id`;
- todo `<label>` (com `for` e texto normalizado).

Cada item é anotado com o passo ancestral (`step-1`…`step-6`); itens fora dos
passos (seletor de unidade, CSRF, botões do rodapé) ficam com `step: null`.
A lista é congelada em JSON:

| Snapshot | Conteúdo |
| --- | --- |
| `tests/snapshots/aj5e_ordem_novo_com_unidades.json` | `novo` com seletor de unidade (admin global) |
| `tests/snapshots/aj5e_ordem_novo_sem_unidades.json` | `novo` sem seletor (admin de unidade) |
| `tests/snapshots/aj5e_ordem_editar_completo.json` | `editar` com aluno completo |

Há ainda `test_ordem_cobre_os_seis_passos`, que falha se a extração perder um
passo, um controle ou (exceto no passo 5, que usa caixas de upload sem
`<label>`) um rótulo.

Hashes (SHA-256, 16 primeiros):

```
168A2E30AB2EF984  aj5e_ordem_editar_completo.json
3D534F55AFFC5D7B  aj5e_ordem_novo_com_unidades.json
EBA13F59C0ADE737  aj5e_ordem_novo_sem_unidades.json
```

Após o layout os três snapshots **não mudaram** — a ordem é idêntica.

### 3.1. Variante "sem `class`/`style`" do canonizador

`tests/test_aj5c_form_caracterizacao.py` ganhou o parâmetro
`sem_classes_estilo` em `canonizar()`/`_serializar()`: ele descarta os
atributos `class` e `style` de **todos** os elementos antes de serializar.

Foram criados três snapshots estruturais novos (hashes idênticos antes e
depois do layout):

| Snapshot | SHA-256 (16) |
| --- | --- |
| `tests/snapshots/aj5e_estrutura_novo_com_unidades.txt` | `5BD6DC110DBB291F` |
| `tests/snapshots/aj5e_estrutura_novo_sem_unidades.txt` | `DE8FADDF07E59A62` |
| `tests/snapshots/aj5e_estrutura_editar_completo.txt` | `435E6D5E62A11305` |

`test_variante_sem_classes_remove_class_e_style` é a sanidade do próprio
canonizador: garante que a variante realmente remove `class`/`style` (sem isso
uma mudança de layout passaria despercebida).

## 4. Etapa 2 — layout aplicado

### 4.1. Casca (`novo.html` e `editar.html`)

| Antes | Depois |
| --- | --- |
| `container py-4` | `container py-3 py-lg-4 aluno-form-shell` |
| `col-lg-10` | `col-12` |
| cabeçalho `mb-4` | cabeçalho `mb-3` |

`aluno-form-shell` (em `editar.css`) sobe o limite de leitura de 1320px
(limite padrão do `.container` do Bootstrap) para **1400px**. Com a coluna
deixando de descartar 2/12 da largura, o cartão passou de ~1076px para
~1376px em 1920px de viewport. Abaixo de `lg` o padding vertical cai
(`py-3`) para não empurrar o formulário.

### 4.2. Por passo

Legenda: todas as mudanças abaixo são **apenas `class`**; nenhum elemento,
atributo, texto ou ordem foi criado/removido/movido.

**Passo 1 — Identificação**

- linha externa e linha interna: `row g-3` → `row g-3 gx-lg-4`
  (gutter horizontal maior em `lg+`, vertical mantido);
- título: `mb-4` → `mb-3 mb-lg-4`.
- A coluna da foto (`col-md-3`) foi **mantida** (ver §5).

**Passo 2 — Filiação e responsável**

- `row g-3` → `row g-3 gx-lg-4`;
- `col-md-6 border-end pe-4` → `col-md-6 border-end pe-md-4 pe-0`;
- `col-md-6 ps-4` → `col-md-6 ps-md-4 ps-0`
  (no empilhamento de telas pequenas o recuo lateral não faz mais sentido).

**Passo 3 — Endereço e contato**

- `row g-3` → `row g-3 gx-lg-4`;
- bloco de contato: `mt-4` → `mt-3 mt-lg-4`;
- os quatro campos do contato (WhatsApp, telefone do responsável, e-mail e
  o switch "não possui acesso") passam de `col-md-4` para
  `col-md-4 col-xl-3`, ficando **numa única linha em `xl`** em vez de o
  switch cair sozinho na linha seguinte. Altura do passo: **428px → 380px**
  (-48px) em 1920 e 1366.

**Passo 4 — Situação escolar**

- `row g-3` → `row g-3 gx-lg-4`;
- `status-outro`: `col-md-6` → `col-md-6 col-xl-3`;
- `instituicao-outro`: `col-md-6` → `col-md-6 col-xl-5`;
- `turno`: `col-md-4` → `col-md-4 col-xl-3`.

Em `xl`, as linhas condicionais fecham em 12 colunas
(`3+3+6` e `4+5+3`) em vez de "quebrarem" com buraco à direita. Em `md`
continua exatamente como antes.

**Passo 5 — Documentação digital**

- a grade (`row g-4` / `col-md-4`) foi mantida: com 3 documentos por linha o
  espaçamento já era o maior do formulário;
- as caixas de upload (documentos e laudo) ganharam `h-100`, para ficarem
  com a **mesma altura** quando o conteúdo de uma delas cresce (botões
  Ver/Excluir).

**Passo 6 — Perfil e saúde**

- `row g-3` → `row g-3 gx-lg-4` (linha principal e linha interna do bloco de
  saúde);
- bloco de saúde: `mt-4` → `mt-3 mt-lg-4`;
- termo de imagem: `mt-4` → `mt-3 mt-lg-4`;
- as colunas (`col-md-4`, `col-md-6`, `col-md-12`) foram mantidas — ver §5.

### 4.3. `app/static/css/alunos/editar.css`

| Regra | Antes | Depois |
| --- | --- | --- |
| `.stepper-container` | `margin-bottom: 2rem` | `margin-bottom: 1.5rem`; em `md+`: `position: sticky; top: var(--topbar-height, 56px); z-index: 5`, fundo do body e `padding` vertical de 0.5rem |
| `.container.aluno-form-shell` | — | `max-width: 1400px` |
| `.form-step > h4` | — | `font-size: 1.15rem` |
| `.form-label` | `0.75rem`, `margin-bottom: .25rem` | `0.8rem`, `line-height: 1.3`, `margin-bottom: .375rem` |
| cartão | `p-4 mb-4` (template) | `p-3 p-lg-4 mb-3 mb-lg-4` (template) |

O stepper fica preso **abaixo do topbar fixo** (56px, variável
`--topbar-height`) e com `z-index: 5`, abaixo do topbar (`1030`); é só CSS,
sem tocar no `goToStep`. Abaixo de `md` ele continua estático, para não
consumir altura em telas pequenas.

Nenhuma regra nova ficou sem uso: `aluno-form-shell` é usada pelas duas
cascas, `.form-step > h4` pelos seis títulos e o bloco `sticky` pelo
`.stepper-container`. Não havia regra antiga a remover: todas as regras
existentes continuam em uso (`.form-step`, `.pdf-upload-box`,
`.webcam-*`, `.step-item`, etc.).

## 5. O que NÃO foi aplicado por risco de reordenar/estruturar

Estas ideias foram avaliadas e descartadas de propósito:

1. **Passo 2 em 4 colunas** (Nome/CPF da mãe e do pai lado a lado): exigiria
   novos `div` de linha/coluna, mudando a **estrutura do DOM** (os snapshots
   `aj5e_estrutura_*` deixariam de bater). Não aplicado.
2. **Passo 6 em 4 colunas** (`col-md-4` → `col-xl-3`): o bloco "Qual
   programa?" (tags + `input-group` + botão) ficaria estreito e os campos
   condicionais mudariam de linha conforme o estado. Não aplicado; o passo 6
   ganhou largura pela casca e pelos gutters.
3. **Coluna da foto do passo 1 menor em `xl`** (`col-md-3` → `col-xl-2`):
   os botões "Carregar"/"Tirar Foto" são `w-100` e ficariam apertados. Não
   aplicado.
4. **Passo 5 com 4 documentos por linha em `xl`** (`col-xl-3`): com 3
   documentos a linha ficaria com um buraco. Não aplicado.
5. **Mudar `form-control-lg` do passo 3 ou o tamanho de fonte dos inputs**:
   alteraria altura de todos os campos e a comparação de densidade sem
   necessidade. Não aplicado.
6. **Reordenar qualquer campo para "preencher" linhas**: proibido pelo
   escopo. As colunas de `md` foram preservadas; só `xl` foi ajustado.

## 6. Etapa 3 — evidência visual

Método (scripts locais em `.tmp/aj5e/`, **não versionados** — `.tmp/` está no
`.gitignore`):

1. `capturar.py` cria o app com SQLite em memória, semeia unidade, admin e um
   aluno **fictício completo** (todos os blocos, sem `foto_path` para o
   placeholder), loga com o test client e baixa `GET /aluno/editar/<id>`.
2. No HTML salvo, `/static/...` é reescrito para
   `file:///D:/pautaon/app/static/...`.
3. Só na cópia de captura é injetado um `<style>` que isola o passo:
   `.form-step { display: none !important; } #step-N { display: block !important; }`.
4. Edge headless (`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`)
   com `--headless=new --disable-gpu --hide-scrollbars --virtual-time-budget=4000
   --screenshot=... --window-size=W,H`.

O CSS de isolamento do passo é **só da captura**; o repositório não tem
nenhum CSS de captura. As imagens **não são commitadas**.

Viewport usada (mesma para antes e depois, por largura):

| Largura | Altura da viewport |
| --- | --- |
| 1920 | 1300 |
| 1366 | 1500 |
| 768 | 2600 |

Arquivos em `.tmp/aj5e/` (36 PNGs):

| Passo | 1920 antes/depois | 1366 antes/depois | 768 antes/depois |
| --- | --- | --- | --- |
| 1 | `antes_passo1_1920.png` (106 KB) / `depois_passo1_1920.png` (105 KB) | `antes_passo1_1366.png` (105 KB) / `depois_passo1_1366.png` (104 KB) | `antes_passo1_768.png` (67 KB) / `depois_passo1_768.png` (68 KB) |
| 2 | `antes_passo2_1920.png` (104 KB) / `depois_passo2_1920.png` (104 KB) | `antes_passo2_1366.png` (103 KB) / `depois_passo2_1366.png` (101 KB) | `antes_passo2_768.png` (66 KB) / `depois_passo2_768.png` (66 KB) |
| 3 | `antes_passo3_1920.png` (94 KB) / `depois_passo3_1920.png` (94 KB) | `antes_passo3_1366.png` (94 KB) / `depois_passo3_1366.png` (92 KB) | `antes_passo3_768.png` (58 KB) / `depois_passo3_768.png` (57 KB) |
| 4 | `antes_passo4_1920.png` (93 KB) / `depois_passo4_1920.png` (93 KB) | `antes_passo4_1366.png` (92 KB) / `depois_passo4_1366.png` (91 KB) | `antes_passo4_768.png` (57 KB) / `depois_passo4_768.png` (56 KB) |
| 5 | `antes_passo5_1920.png` (107 KB) / `depois_passo5_1920.png` (104 KB) | `antes_passo5_1366.png` (102 KB) / `depois_passo5_1366.png` (102 KB) | `antes_passo5_768.png` (64 KB) / `depois_passo5_768.png` (65 KB) |
| 6 | `antes_passo6_1920.png` (129 KB) / `depois_passo6_1920.png` (130 KB) | `antes_passo6_1366.png` (134 KB) / `depois_passo6_1366.png` (134 KB) | `antes_passo6_768.png` (95 KB) / `depois_passo6_768.png` (97 KB) |

### 6.1. Medição objetiva da geometria

Como este agente não interpreta a imagem, a evidência quantitativa foi
medida **no próprio navegador** (`medir.py` injeta um script na cópia de
captura e lê `getBoundingClientRect()` via `--dump-dom`; resultado em
`.tmp/aj5e/geometria.txt`):

| Largura | Cartão antes → depois | Início do passo 1 antes → depois | Fim do stepper antes → depois |
| --- | --- | --- | --- |
| 1920 | 1076px → **1376px** (+27,9%) | 311px → 279px (-32px) | 229px → 221px |
| 1366 | 820px → **989px** (+20,6%) | 310px → 278px (-32px) | 229px → 221px |
| 768 | 516px → **651px** (+26,2%) | 292px → 237px (-55px) | 211px → 195px |

Altura do conteúdo por passo (`step` top→bottom, em px):

| Passo | 1920 antes → depois | 1366 antes → depois | 768 antes → depois |
| --- | --- | --- | --- |
| 1 | 351 → 351 | 351 → 351 | 1255 → **1247** |
| 2 | 479 → 479 | 479 → 479 | 814 → **806** |
| 3 | 428 → **380** | 428 → **380** | 904 → **888** |
| 4 | 429 → 429 | 429 → 429 | 737 → **729** |
| 5 | 397 → 397 | 397 → 397 | 984 → 984 |
| 6 | 1007 → 1007 | 1007 → 1007 | 1641 → **1598** |

Leitura: em telas largas os passos já eram "rasos" (a grade não mudou de
linhas); o ganho ali é **horizontal** (+20% a +28% de largura útil) e de
**posição inicial** (conteúdo começa 32px mais alto). O passo 3 ganha uma
linha inteira em `xl`. Em 768 todos os passos encurtaram (paddings do cartão
e do stepper). O passo 6 em 768 ganhou mais (-43px) porque o bloco de saúde
deixou de somar margem dupla.

O diff de pixels entre antes/depois (`.tmp/aj5e/metricas.txt`) ficou entre
**9% e 33%** da imagem em todos os pares — confirma que a mudança é visível
em todos os 18 pares, sem imagem em branco.

## 7. Etapa 4 — verificação

### 7.1. Ordem dos campos

`python -m pytest tests/test_aj5e_ordem_campos.py` → **4 passed**.
Os três JSON de ordem não mudaram.

### 7.2. Estrutura sem `class`/`style`

`python -m pytest tests/test_aj5c_form_caracterizacao.py` → **7 passed**.
Os três `aj5e_estrutura_*.txt` têm exatamente os mesmos hashes de antes do
layout (§3.1): nenhum elemento, atributo, texto ou ordem mudou.

### 7.3. Snapshots de caracterização (com classes)

Três arquivos mudaram — **esperado e justificado**, pois congelam as classes:

- `tests/snapshots/aj5c_novo_com_unidades.txt`
- `tests/snapshots/aj5c_novo_sem_unidades.txt`
- `tests/snapshots/aj5c_editar_completo.txt`

Cada um teve 74 linhas alteradas (37 pares antes/depois), todas diferenças de
`class` (casca, stepper, cartão, títulos, `gx-lg-4`, `pe-md-4`/`ps-md-4`,
`col-xl-*`, `h-100`, `mt-*`). Verificação mecânica: das **222 linhas**
alteradas nos três snapshots, **todas** contêm `class=` (nenhuma linha sem
classe mudou). A prova de que **só** classes mudaram é a variante sem
`class`/`style` do §7.2, que ficou idêntica.

### 7.4. Suíte completa

`python -m pytest -q` → **1420 passed** (base anterior: 1412; +8 testes do
AJ5-E), 770 warnings, ~13min51s.

### 7.5. Ruff

`ruff check --select F821,F811,F841,F401` nos dois arquivos de teste do
AJ5-E → **All checks passed!** (nenhum `F401` novo; os 71 `F401`
pré-existentes estão fora dos arquivos tocados).

### 7.6. Reversão provada em worktree

Em um worktree temporário (`D:\pautaon\.tmp\aj5e\wt_revert`, criado a partir
de `5eaf3f2`), `git revert --no-commit 5eaf3f2` reaplicou o estado anterior
nos 7 arquivos e os testes de ordem + caracterização passaram (**11 passed**).
O worktree foi removido depois; nenhum efeito no repositório principal.

### 7.7. `git status`

Limpo, exceto a deleção **pré-existente** e fora de escopo
` D docs/prompts/Ajustes_Pontuais.md`, que não foi tocada nem commitada.

## 8. Comportamentos preservados

- **Stepper**: mesmos `id`, `onclick` e `goToStep`; a mudança é só
  `position: sticky` em `md+` e margens.
- **Foto/webcam**: mesmos botões, `input type=file`, `previewImage`,
  `abrirWebcam`, modal e CSS da webcam intactos.
- **Uploads**: mesmos `input type=file`, `onclick`, `updateFileName`;
  apenas `h-100` para alinhar as caixas.
- **Ver/Excluir**: mesmos links, `form` externo, confirmação e permissões
  (`pode_doc`); apenas o alinhamento da caixa mudou.
- **Campos condicionais** (`d-none`): mesmas condições Jinja, sem tocar no
  JS que as alterna.

## 9. Riscos e limitações

1. A largura útil em 1920 chega a ~1376px. É o limite escolhido para leitura
   de formulário (1400px de casca); não usei `container-fluid` para não
   esticar campos em monitores ultrawide.
2. O stepper sticky ocupa ~22px ao rolar. Em `md+` ele fica abaixo do topbar;
   em telas pequenas continua estático de propósito.
3. As capturas usam Edge headless com viewport fixa (não página inteira).
   Para passos mais altos que a viewport (passo 6 em 768), a imagem mostra o
   topo do passo; a altura real está na tabela de geometria.
4. Este agente não inspeciona visualmente os PNGs; a conferência humana deve
   usar os arquivos de `.tmp/aj5e/`.

## 10. Como reproduzir as capturas

```powershell
# na raiz D:\pautaon (scripts locais, ignorados pelo git)
python .tmp\aj5e\capturar.py antes    # antes de aplicar o layout
python .tmp\aj5e\capturar.py depois   # com o layout aplicado
python .tmp\aj5e\medir.py             # geometria via --dump-dom
python .tmp\aj5e\metricas.py          # diff de pixels
```

`capturar.py` sempre renderiza o estado **atual** do working tree. Para
reproduzir o "antes" depois do commit, use um worktree em `5a0f38c` (ou em
`d229704`, que só adiciona testes).
