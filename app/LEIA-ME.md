# Reorganização das rotas

## O que mudou

- **`main.py` → pacote `main/`**, seguindo o mesmo padrão do `registros/`:
  - `__init__.py` — cria o `bp` e importa os submódulos.
  - `home.py` — rota `/`.
  - `dashboard.py` — rota `/dashboard`, agora só o roteador por perfil.
  - `dashboard_admin.py` / `dashboard_professor.py` / `dashboard_servico_social.py` — a lógica de cada perfil, isolada.
  - `secretaria.py` — rota `/dashboard/secretaria`.
  - `unidade.py` — rota `/trocar-unidade/<id>`.
  - Removido um bloco `if ...: pass` morto que existia em `dashboard()` (não fazia nada).

- **`relatorios.py` → pacote `relatorios/`**, mesmo padrão:
  - `__init__.py` — cria o `bp_relatorios` (mesmo nome e `url_prefix` de antes) e importa os submódulos.
  - `geral.py` — `/` e `/exportar`.
  - `alunos.py` — `/alunos` e `/relatorio_alunos/exportar`.
  - `conselho.py` — `/conselho`.
  - `shared.py` — `ROLES_RELATORIOS` e a lógica de filtros de aluno (`ler_filtros_alunos` / `aplicar_filtros_alunos`), que antes estava **duplicada** entre `relatorio_alunos` e `exportar_relatorio_alunos`. Agora tem uma única fonte de verdade.

- **`registros/core.py`**: removida a rota `POST /planejamento/configurar-conselho`
  (função `salvar_configuracao_conselho`), que era uma reimplementação duplicada
  da mesma funcionalidade já existente em `planejamento.py` (`POST /configurar-conselho`).
  Mantivemos a versão de `planejamento.py`, que é a que está referenciada no
  restante do código (`url_for('main.salvar_configuracao_conselho')`).
  ⚠️ Se algum template/formulário aponta para `url_for('registros.salvar_configuracao_conselho')`,
  ele precisa ser ajustado para `url_for('planejamento.salvar_configuracao_conselho')` antes do deploy.

- **`mainOLD.py`**: não incluído no pacote — pode ser removido do repositório,
  todo o conteúdo dele já está coberto por `main/` e `relatorios/`.

## O que NÃO mudou (comportamento preservado)

- Nomes de blueprint, `url_prefix` e caminhos de rota são idênticos aos originais
  (validei isso comparando os decorators `@bp.route`/`@bp_relatorios.route` antes/depois).
- Nenhuma regra de negócio, mensagem de flash, template ou query foi alterada —
  só a organização dos arquivos e a extração de código duplicado para `shared.py`.
- Imports "locais" (dentro de função) que existiam no código original foram
  promovidos para o topo dos arquivos onde fazia sentido — isso é só estilo,
  sem efeito no comportamento.

## Como integrar

As rotas **não** ficam mais em `app.routes`. O factory importa os blueprints
diretamente de `app/`:

```python
from app.auth import bp as auth_bp
from app.conselho import bp as conselho_bp
from app.informacao_padrao import bp as informacao_padrao_bp
from app.main import bp as main_bp
from app.registros import bp as registros_bp
from app.registros.servico_social import bp as servico_social_bp
from app.relatorios import bp_relatorios
from app.planejamento import bp_planejamento
```

O serviço de dados institucionais (antes o pacote `app/informacao_padrao/`)
vive em `app/services/informacao_padrao.py`, para não colidir com o módulo
de rotas `app/informacao_padrao.py`.

A pasta `app/routesOLD/` e `app/informacao_padraoOLD/` são cópias de arquivo
da estrutura anterior — não devem ser importadas pelo código ativo.

Confira a ressalva sobre `url_for('registros.salvar_configuracao_conselho')`
acima (o template de planejamento já aponta para `planejamento.*`).
