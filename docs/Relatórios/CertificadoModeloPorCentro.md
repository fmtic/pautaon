# Certificado — modelo (imagem) por centro de custo do período — fase 1

Data: 29/10/2026 · Branch `nova_feature` · Sem push

## 1. Pedido e decisões fechadas

O certificado é emitido na tela **Certificados do período** (`/periodo-letivo/relatorio/<id>`). Turmas de centros de
custo diferentes podem ter **layouts diferentes**, então é preciso subir um **modelo de certificado por centro de
custo de cada período letivo**.

Decisões fechadas com o usuário:

| Tema | Decisão |
|---|---|
| Local do upload | Seção **"Modelos de certificado"** na própria página de Certificados do período |
| Formato | **Imagem PNG/JPG** (PDF exigiria geração no servidor) |
| Cardinalidade | **Um modelo por (período, centro)**; substituir apaga o anterior |
| Centro sem modelo | Nada especial — na vida real toda oferta tem centro; sem fallback/“modelo padrão” |
| Quem envia | Mesmos papéis de Períodos; **professor fora** |
| Limite | **5 MB**, **sem SVG** |
| Texto | O app injeta o texto sobre o modelo (posições fixas no CSS) — **fase 2**, texto ainda não definido |

## 2. Por que não no modal de CRUD do centro de custo

`centro_custo` é o **catálogo da unidade** (`app/models/pedagogico.py:35`), transversal a todos os períodos; o CRUD
(`/centros-custo/*`, `periodos.py`) só conhece `nome`/`ativo`/`unidade_id`, e o modal `#modalCentrosCusto` vive dentro
do formulário do período, mas grava no catálogo. O modelo é do par **(período, centro)**: colocar o upload lá exigiria
escolher o período dentro do modal e criaria dois donos para o mesmo arquivo. A página de Certificados já é do período
e já é o contexto da emissão — é lá que a seção entrou.

Observação de dados: o vínculo período × centro **não é FK** — `periodo_letivo.centro_custo` guarda um **CSV de
nomes**. O upload resolve cada nome contra o catálogo da unidade do período e grava o `centro_custo_id`.

## 3. Modelo de dados (MER §7.4b)

Tabela nova `modelo_certificado` (migration `e1f2a3b4c5d6`, head):

| Coluna | Tipo | Nulo | Observação |
|---|---|---|---|
| id | int | não | PK |
| periodo_letivo_id | int | não | FK → `periodo_letivo` |
| centro_custo_id | int | não | FK → `centro_custo` |
| arquivo | varchar(255) | não | nome no disco |
| nome_original | varchar(255) | sim | usado no download |
| tipo | varchar(60) | sim | `image/png` / `image/jpeg` |
| tamanho | int | sim | bytes |
| created_at / updated_at | timestamp | sim | auditoria |

UNIQUE `uq_modelo_certificado_periodo_centro (periodo_letivo_id, centro_custo_id)`.

Arquivos **fora** do `static`: `UPLOAD_FOLDER/certificados/<periodo_letivo_id>/p<periodo>_c<centro>_<epoch>_<uuid6>.<ext>`.

## 4. Serviço e rotas

`app/services/certificado_modelo.py`

- `centros_do_periodo(periodo)` → lista com `{nome, centro, modelo, no_periodo, ativo}` (ordem alfabética);
- `salvar_modelo(periodo, centro, upload)` → valida (ausente / extensão / vazio / 5 MB), grava, substitui e apaga o
  anterior; `ValueError` em português, sem gravar nada em caso de erro;
- `remover_modelo(periodo, centro)` → apaga linha + arquivo;
- `caminho_modelo(modelo)`; `_limpar_orfaos()` (auto-reparo de sobras).

`app/registros/periodos.py`

| Rota | Método | Papel |
|---|---|---|
| `/periodo-letivo/<id>/certificado-modelo/<centro_id>` | POST | enviar/substituir |
| `/periodo-letivo/<id>/certificado-modelo/<centro_id>/remover` | POST | remover |
| `/periodo-letivo/<id>/certificado-modelo/<centro_id>/arquivo` | GET | pré-visualizar (`?download=1` = anexo) |

Guardas: `_ROLES_PERIODO` (`admin`, `pedagogico`, `secretaria`) + `assert_unidade_context` para não-admin; centro de
outra unidade → **404**; CSRF nos três POSTs.

## 5. Tela

Seção `#modelos-certificado` (`no-print`), acima da tabela de conferência:

- linha por centro do período: nome + selo (`fora do catálogo`, `fora do período`, `inativo`), miniatura do modelo,
  nome original/tamanho, data da última troca;
- ações: **Enviar/Substituir** (form `multipart/form-data` na própria linha, `accept` restrito), **Baixar** e
  **Remover** (com confirmação);
- período sem centros: aviso apontando para **Períodos → Centros de Custo**;
- nome fora do catálogo: linha visível, sem upload, com instrução de cadastrar o centro;
- modelo de centro que saiu do CSV: continua listado como `fora do período` e pode ser removido.

## 6. Testes (`tests/test_certificado_modelo.py`, 23, nenhum existente alterado)

Upload/linha/arquivo no disco · substituição apaga o anterior (1 linha, 1 arquivo) · remoção apaga linha e arquivo ·
PDF recusado (flash + nada gravado) · arquivo ausente · limite de 5 MB (mensagem) · **403** para professor **e
gerência** · **200** para admin/pedagógico/secretaria · isolamento de unidade (403) · centro de outra unidade (404) ·
modelos isolados por período · preview devolve os bytes e `image/png` · `?download=1` como anexo com o nome original ·
404 sem modelo · página lista os centros do período (e não os de outra unidade) · página mostra o modelo enviado ·
período sem centros (aviso) · centro fora do catálogo · centro inativo marcado · modelo `fora do período` continua
listado.

Suíte: **958 → 981 passed**.

## 7. Ensaio (`pautaon_ensaio`, desfeito)

- **Alvo conferido:** `host=localhost`, `database=pautaon_ensaio`, head antes/depois `e1f2a3b4c5d6`; migration aplicada
  **somente no ensaio** via Alembic programático com a app apontada para o ensaio (nenhum `DATABASE_URL` de sessão).
- **Setup:** período `[ROTEIRO] Periodo Vigente` (id 22) nasce com `centro_custo = NULL`; para o ensaio o CSV recebeu
  `[ROTEIRO] Centro Padrao` (id 10) por SQL e foi **restaurado** ao final. Toda a funcionalidade foi exercitada pelas
  rotas reais (`secretaria.m1`, login 302).
- **Resultados:** seção presente com o centro · upload PNG → 302, linha `image/png` 70 bytes, arquivo no disco ·
  `GET /arquivo` → 200 `image/png` com os mesmos 70 bytes · `?download=1` → `attachment; filename=modelo.png` · página
  passa a `Substituir/Baixar/Remover` · substituição por JPG → 1 linha nova e **PNG anterior apagado** · PDF → 302 com
  flash "Formato inválido" e linha inalterada · remoção → 0 linhas e pasta vazia.
- **Limpeza:** linhas removidas, CSV do período restaurado (`NULL`), pasta apagada. Banco principal **intocado**.

## 8. Desvios, achados e pendências

1. **Papéis:** o pedido citou "admin/gerência/pedagógico/secretaria", mas `_ROLES_PERIODO` (usado pela própria página
   de Certificados) **não inclui `gerencia`** — o upload segue a página: gerência e professor recebem **403**. Se
   gerência precisar enviar, é uma linha em `_ROLES_PERIODO` (afeta também o acesso à página).
2. **Pré-requisito da fase 2:** a lista de certificados (`periodos.py`, laço de inscrições) **não carrega a oferta nem
   o centro de custo** em cada linha (`item` = turma/curso/nível/situação/concluído/carga). Para aplicar o modelo por
   centro na impressão, essa listagem precisa passar `item["oferta"]`/`item["centro_custo"]` e o CSS de impressão
   precisa de `@page A4` + fundo por page-break. Nada disso foi feito agora (fora do escopo da fase 1).
3. **Migration no principal:** a tabela existe só no ensaio. O principal precisa de `flask db upgrade` (após backup)
   antes do deploy desta funcionalidade.
4. **Windows / arquivo em uso:** se o arquivo antigo estiver aberto no momento da substituição (ex.: download em
   andamento), a remoção falha e fica registrada em log; a sobra é apagada na próxima gravação ou remoção do mesmo par.
5. **Ativos não versionados:** `instance/uploads/certificados/` é criado sob demanda e está fora do git (mesmo padrão
   dos demais uploads).
