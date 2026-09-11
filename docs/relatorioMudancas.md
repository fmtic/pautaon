### Alterações do dia

- Data da intervenção: 11/09/2026
- Início da correção: 2026-09-11 18:35
- Conclusão da correção: 2026-09-11 18:55

Este complemento resolve a pendência descrita acima e acrescenta ajustes de paridade/robustez encontrados durante a revisão. Para aplicar em outro repositório, siga os passos abaixo após conferir se os arquivos daquele repositório já receberam a primeira parte da funcionalidade.

### Corrigido no repositório em produção

A correção aplicada neste checkout foi a seguinte:

- Removida a falha na template de edição causada por `div` não definida e por um trecho literal `` `n `` no stepper.
- Ajustado o stepper da etapa de edição para incluir a Etapa VI corretamente e evitar que a renderização do formulário quebrasse com erro de template.
- Reativado o carregamento do script de situação escolar na edição, garantindo que campos condicionais e autocomplete funcionem na tela de alteração do aluno.
- Reforçada a lógica de persistência em `app/routes/registros/alunos.py` para limpar a situação escolar vazia, salvar `status`/`status_outro` e limitar o autocomplete a termos com pelo menos 2 caracteres.
- Ajustado `app/static/js/alunos/situacao_escolar.js` para criar sugestões com `document.createElement` e evitar injeção de HTML por nomes vindos do banco.
- Atualizado `app/static/js/alunos/editar.js` para detectar etapas dinamicamente e respeitar a etapa 6 no passo final.


### Resumo do que foi concluído

1. As colunas `status` e `status_outro` foram adicionadas ao modelo `SituacaoEscolar`.
2. A função `_salvar_situacao_escolar(aluno)` passou a salvar `status_escolar` e `status_escolar_outro`.
3. A função `_salvar_situacao_escolar(aluno)` passou a apagar a situação escolar existente quando o formulário da etapa VI é enviado totalmente vazio.
4. O endpoint `/alunos/instituicoes` passou a retornar lista vazia para termos com menos de 2 caracteres.
5. O autocomplete passou a consultar nomes distintos de instituição e ignorar registros com nome nulo.
6. O JavaScript `situacao_escolar.js` deixou de montar botões por `innerHTML` e passou a usar `document.createElement`, reduzindo risco de HTML injetado por nomes cadastrados no banco.
7. A tela `app/templates/alunos/editar.html` recebeu também a Etapa VI: Situação Escolar, preenchendo os campos com dados existentes de `aluno.situacao_escolar`.
8. O arquivo `app/static/js/alunos/editar.js` foi ajustado para detectar etapas dinamicamente, aceitando a nova etapa 6.
9. O script `scripts/migrate_situacao_escolar.py` passou a adicionar `status` e `status_outro` por `ALTER TABLE ... ADD COLUMN` somente quando ausentes.
10. O schema estático `scripts/postgres_schema.sql` recebeu a tabela `situacao_escolar` com as colunas finais e o índice `ix_situacao_escolar_unidade_nome`.

### Arquivos alterados nesta parte

| Arquivo | O que fazer no repositório paralelo |
| --- | --- |
| `app/models.py` | Adicionar `status` e `status_outro` em `SituacaoEscolar`, se ainda não existirem. |
| `app/routes/registros/alunos.py` | Atualizar `_salvar_situacao_escolar` e endurecer o endpoint `/alunos/instituicoes`. |
| `app/static/js/alunos/situacao_escolar.js` | Substituir a renderização do autocomplete por criação segura de elementos DOM. |
| `app/templates/alunos/editar.html` | Adicionar indicador 6, criar a Etapa VI preenchida e carregar `situacao_escolar.js`. |
| `app/static/js/alunos/editar.js` | Trocar o controle fixo de 5 etapas por detecção dinâmica de `.form-step`. |
| `scripts/migrate_situacao_escolar.py` | Tornar a migração aditiva também para colunas novas em tabela já existente. |
| `scripts/postgres_schema.sql` | Incluir `CREATE TABLE situacao_escolar` e `CREATE INDEX ix_situacao_escolar_unidade_nome`. |

### Alterações exatas por arquivo

#### `app/models.py`

No modelo `SituacaoEscolar`, logo após `escolaridade_outro`, adicionar:

```python
status: str = db.Column(db.String(20), nullable=True)
status_outro: str = db.Column(db.String(150), nullable=True)
```

O modelo final esperado deve conter, nesta ordem lógica:

```python
class SituacaoEscolar(db.Model):
    """Situação escolar atual, separada dos documentos digitais legados."""
    __tablename__ = 'situacao_escolar'
    __table_args__ = (
        db.Index('ix_situacao_escolar_unidade_nome', 'unidade_id', 'nome_instituicao'),
    )

    id: int = db.Column(db.Integer, primary_key=True)
    aluno_id: int = db.Column(db.Integer, db.ForeignKey('aluno.id'), nullable=False, unique=True)
    unidade_id: int = db.Column(db.Integer, db.ForeignKey('unidade.id'), nullable=True)
    escolaridade: str = db.Column(db.String(40), nullable=True)
    ensino_superior_periodo: int = db.Column(db.Integer, nullable=True)
    escolaridade_outro: str = db.Column(db.String(150), nullable=True)
    status: str = db.Column(db.String(20), nullable=True)
    status_outro: str = db.Column(db.String(150), nullable=True)
    nome_instituicao: str = db.Column(db.String(200), nullable=True)
    tipo_instituicao: str = db.Column(db.String(20), nullable=True)
    bolsista: bool = db.Column(db.Boolean, default=False, nullable=False)
    tipo_instituicao_outro: str = db.Column(db.String(150), nullable=True)
    turno: str = db.Column(db.String(20), nullable=True)
    turno_outro: str = db.Column(db.String(100), nullable=True)
    created_at: datetime = db.Column(db.DateTime, default=get_local_now, nullable=False)
    updated_at: datetime = db.Column(db.DateTime, default=get_local_now, onupdate=get_local_now, nullable=False)

    aluno = db.relationship('Aluno', back_populates='situacao_escolar')
    unidade = db.relationship('Unidade', backref='situacoes_escolares')
```

Alerta: se a classe `Aluno` ainda não tiver o relacionamento 1:1, adicionar:

```python
situacao_escolar = db.relationship(
    'SituacaoEscolar',
    back_populates='aluno',
    uselist=False,
    cascade='all, delete-orphan',
)
```

#### `app/routes/registros/alunos.py`

Garantir que há import de `jsonify` e `SituacaoEscolar`:

```python
from flask import jsonify
from app.models import SituacaoEscolar
```

Atualizar `_salvar_situacao_escolar(aluno)` para:

```python
def _salvar_situacao_escolar(aluno: Aluno) -> None:
    nome = (request.form.get('nome_instituicao') or '').strip() or None
    campos_situacao = (
        'escolaridade',
        'status_escolar',
        'tipo_instituicao',
        'turno_escolar',
        'nome_instituicao',
    )
    form_tem_situacao = any(campo in request.form for campo in campos_situacao)
    tem_conteudo = any((
        request.form.get('escolaridade'),
        request.form.get('status_escolar'),
        request.form.get('tipo_instituicao'),
        request.form.get('turno_escolar'),
        nome,
    ))
    if not tem_conteudo:
        if form_tem_situacao and aluno.situacao_escolar:
            db.session.delete(aluno.situacao_escolar)
        return

    situacao = aluno.situacao_escolar or SituacaoEscolar(aluno=aluno)
    situacao.unidade_id = aluno.unidade_id
    situacao.escolaridade = request.form.get('escolaridade')
    periodo = request.form.get('ensino_superior_periodo', type=int)
    situacao.ensino_superior_periodo = periodo if situacao.escolaridade == 'Ensino superior' and periodo in range(1, 11) else None
    situacao.escolaridade_outro = (request.form.get('escolaridade_outro') or '').strip() if situacao.escolaridade == 'Outros' else None
    situacao.status = request.form.get('status_escolar')
    situacao.status_outro = (
        (request.form.get('status_escolar_outro') or '').strip() or None
        if situacao.status == 'Outros' else None
    )
    situacao.nome_instituicao = nome
    situacao.tipo_instituicao = request.form.get('tipo_instituicao')
    situacao.bolsista = bool(request.form.get('bolsista')) if situacao.tipo_instituicao == 'Privada' else False
    situacao.tipo_instituicao_outro = (request.form.get('tipo_instituicao_outro') or '').strip() if situacao.tipo_instituicao == 'Outro' else None
    situacao.turno = request.form.get('turno_escolar')
    situacao.turno_outro = (request.form.get('turno_escolar_outro') or '').strip() if situacao.turno == 'Outros' else None
    db.session.add(situacao)
```

Garantir chamadas:

```python
db.session.add(novo)
db.session.flush()
_salvar_situacao_escolar(novo)
```

No POST de edição, chamar antes do `commit`:

```python
_salvar_situacao_escolar(aluno)
```

Atualizar o endpoint para:

```python
@bp.route('/alunos/instituicoes')
@login_required
def buscar_instituicoes():
    termo = (request.args.get('q') or '').strip()
    if len(termo) < 2:
        return jsonify([])

    consulta = (
        db.session.query(SituacaoEscolar.nome_instituicao)
        .filter(SituacaoEscolar.nome_instituicao.isnot(None))
        .filter(SituacaoEscolar.nome_instituicao.ilike(f'%{termo}%'))
        .distinct()
    )
    unidade_id = get_unidade_id()
    if unidade_id:
        consulta = consulta.filter(SituacaoEscolar.unidade_id == unidade_id)
    return jsonify([
        nome for (nome,) in consulta.order_by(SituacaoEscolar.nome_instituicao).limit(10)
    ])
```

Alerta: `ilike` funciona em PostgreSQL e costuma funcionar via SQLAlchemy em SQLite, mas testar no banco real do projeto paralelo.

#### `app/static/js/alunos/situacao_escolar.js`

O arquivo final deve ficar assim:

```javascript
window.toggleSituacaoEscolar = function () {
  const escolaridade = document.getElementById('escolaridade')?.value;
  const tipo = document.getElementById('tipo_instituicao')?.value;
  const turno = document.getElementById('turno_escolar')?.value;
  const status = document.getElementById('status_escolar')?.value;
  document.getElementById('status-outro')?.classList.toggle('d-none', status !== 'Outros');
  document.getElementById('periodo-superior')?.classList.toggle('d-none', escolaridade !== 'Ensino superior');
  document.getElementById('escolaridade-outro')?.classList.toggle('d-none', escolaridade !== 'Outros');
  document.getElementById('bolsista-div')?.classList.toggle('d-none', tipo !== 'Privada');
  document.getElementById('instituicao-outro')?.classList.toggle('d-none', tipo !== 'Outro');
  document.getElementById('turno-outro')?.classList.toggle('d-none', turno !== 'Outros');
};

document.addEventListener('DOMContentLoaded', () => {
  const input = document.getElementById('nome_instituicao');
  const lista = document.getElementById('sugestoes-instituicao');
  input?.addEventListener('input', async () => {
    if (!lista) return;
    if (input.value.trim().length < 2) return lista.classList.add('d-none');

    try {
      const response = await fetch(`/alunos/instituicoes?q=${encodeURIComponent(input.value)}`);
      if (!response.ok) throw new Error('Falha ao buscar instituições');
      const nomes = await response.json();

      lista.replaceChildren();
      nomes.forEach(nome => {
        const botao = document.createElement('button');
        botao.type = 'button';
        botao.className = 'list-group-item list-group-item-action';
        botao.textContent = nome;
        botao.addEventListener('click', () => {
          input.value = nome;
          lista.classList.add('d-none');
        });
        lista.appendChild(botao);
      });
      lista.classList.toggle('d-none', !nomes.length);
    } catch {
      lista.classList.add('d-none');
    }
  });
  window.toggleSituacaoEscolar();
});
```

#### `app/templates/alunos/editar.html`

Adicionar no topo, junto aos outros `set`:

```jinja
{% set sit = aluno.situacao_escolar %}
```

No stepper, adicionar:

```html
<div class="step-item" id="step-indicator-6" onclick="goToStep(6)">6</div>
```

Depois do bloco `step-5`, antes do fechamento do card de etapas, adicionar um bloco `step-6` equivalente ao cadastro novo, mas com valores preenchidos. O bloco implementado neste repositório usa:

```jinja
{% set escolaridade_atual = sit.escolaridade if sit else '' %}
{% set status_atual = sit.status if sit else '' %}
{% set tipo_atual = sit.tipo_instituicao if sit else '' %}
{% set turno_atual = sit.turno if sit else '' %}
```

E preenche inputs textuais com expressões seguras contra `None`, por exemplo:

```jinja
value="{{ (sit.nome_instituicao if sit else '') or '' }}"
```

Também carregar o JS antes do `editar.js`:

```jinja
<script src="{{ url_for('static', filename='js/alunos/situacao_escolar.js') }}"></script>
<script src="{{ url_for('static', filename='js/alunos/editar.js') }}"></script>
```

Alerta: se o template de edição do repositório paralelo tiver estrutura diferente, não colar cegamente o bloco; inserir dentro do mesmo card das etapas para o `editar.js` encontrar `.form-step`.

#### `app/static/js/alunos/editar.js`

Substituir estruturas fixas de 5 etapas por detecção dinâmica:

```javascript
const stepIds = Array.from(document.querySelectorAll('.form-step'))
    .map(step => Number(step.id.replace('step-', '')))
    .filter(Number.isInteger)
    .sort((a, b) => a - b);
const lastStepId = stepIds[stepIds.length - 1] || 1;
```

Em `updateStepper`, iterar até 6 e esconder indicador sem etapa:

```javascript
for (let i = 1; i <= 6; i++) {
    const indicator = document.getElementById(`step-indicator-${i}`);
    if (!indicator) continue;

    const hasStep = stepIds.includes(i);
    indicator.classList.toggle('d-none', !hasStep);
    if (!hasStep) continue;

    ...
}
```

Trocar a condição de submit para:

```javascript
if (currentStep === lastStepId) {
```

Atualizar navegação para buscar elementos por id dinamicamente:

```javascript
function goToStep(n) {
    if (n === currentStep || !stepIds.includes(n)) return;
    document.getElementById(`step-${currentStep}`)?.classList.remove('active');
    currentStep = n;
    document.getElementById(`step-${currentStep}`)?.classList.add('active');
    updateStepper();
    window.scrollTo(0, 0);
}

function nextStep(n) {
    const currentIndex = stepIds.indexOf(currentStep);
    const nextStepId = stepIds[currentIndex + n];
    if (!nextStepId) return;

    document.getElementById(`step-${currentStep}`)?.classList.remove('active');
    currentStep = nextStepId;
    document.getElementById(`step-${currentStep}`)?.classList.add('active');
    updateStepper();
    window.scrollTo(0, 0);
}
```

#### `scripts/migrate_situacao_escolar.py`

Substituir o script simples por uma migração aditiva:

```python
"""Migração aditiva da situação escolar; segura para SQLite e PostgreSQL."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from app.database import db
from sqlalchemy import inspect, text
from app.models import SituacaoEscolar


def add_column_if_missing(table_name: str, column_name: str, column_type: str) -> bool:
    inspector = inspect(db.engine)
    existing_columns = {column['name'] for column in inspector.get_columns(table_name)}
    if column_name in existing_columns:
        return False

    with db.engine.begin() as connection:
        connection.execute(text(f'ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}'))
    return True


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        SituacaoEscolar.__table__.create(db.engine, checkfirst=True)
        added_columns = [
            name for name, column_type in (
                ('status', 'VARCHAR(20)'),
                ('status_outro', 'VARCHAR(150)'),
            )
            if add_column_if_missing('situacao_escolar', name, column_type)
        ]
        if added_columns:
            print(f"Colunas adicionadas em situacao_escolar: {', '.join(added_columns)}.")
        else:
            print('Tabela situacao_escolar criada ou já existente; nenhum dado foi alterado.')
```

Alerta: este script não apaga dados. Mesmo assim, rodar backup antes em produção, porque qualquer `ALTER TABLE` é alteração estrutural.

#### `scripts/postgres_schema.sql`

Se o repositório paralelo usa esse arquivo para provisionar bancos novos, adicionar após a criação da tabela `aluno`:

```sql
CREATE TABLE situacao_escolar (
	id SERIAL NOT NULL,
	aluno_id INTEGER NOT NULL,
	unidade_id INTEGER,
	escolaridade VARCHAR(40),
	ensino_superior_periodo INTEGER,
	escolaridade_outro VARCHAR(150),
	status VARCHAR(20),
	status_outro VARCHAR(150),
	nome_instituicao VARCHAR(200),
	tipo_instituicao VARCHAR(20),
	bolsista BOOLEAN NOT NULL,
	tipo_instituicao_outro VARCHAR(150),
	turno VARCHAR(20),
	turno_outro VARCHAR(100),
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (aluno_id),
	FOREIGN KEY(aluno_id) REFERENCES aluno (id),
	FOREIGN KEY(unidade_id) REFERENCES unidade (id)
);

CREATE INDEX ix_situacao_escolar_unidade_nome ON situacao_escolar (unidade_id, nome_instituicao);
```

### Comandos de validação usados neste repositório

Use estes comandos no repositório paralelo depois de aplicar:

```powershell
python -c "from pathlib import Path; [compile(Path(p).read_text(encoding='utf-8'), p, 'exec') for p in ['app/models.py','app/routes/registros/alunos.py','scripts/migrate_situacao_escolar.py']]; print('Python syntax OK')"
python -c "from pathlib import Path; from jinja2 import Environment; env=Environment(); [env.parse(Path(p).read_text(encoding='utf-8')) for p in ['app/templates/alunos/novo.html','app/templates/alunos/editar.html']]; print('Jinja syntax OK')"
node --check app/static/js/alunos/situacao_escolar.js
node --check app/static/js/alunos/editar.js
git diff --check
```

Observação: `python -m py_compile ...` falhou neste ambiente por permissão no diretório `app/__pycache__`, então foi usada compilação em memória via `compile()`. Se o outro ambiente permitir escrita em `__pycache__`, `py_compile` também pode ser usado.

### Comando obrigatório antes de usar em banco existente

```powershell
python scripts\migrate_situacao_escolar.py
```

Alerta de quebra: sem essa migração, a aplicação pode falhar ao salvar aluno novo, editar aluno ou carregar objetos que dependam das colunas novas de `situacao_escolar`.

### Riscos e pontos para o outro Codex revisar

- Conferir se o repositório paralelo possui outras migrações Alembic. Se possuir, talvez seja melhor criar uma revision Alembic equivalente em vez de depender apenas do script manual.
- Confirmar se `get_unidade_id()` tem o mesmo comportamento. O autocomplete filtra por unidade somente quando `unidade_id` existe.
- Conferir se `editar.html` já recebeu outras mudanças locais. O bloco da Etapa VI deve ser integrado sem apagar alterações paralelas.
- Testar manualmente: criar aluno com status `Outros`, editar esse aluno, trocar status para `Cursando`, salvar e confirmar que `status_outro` fica nulo.
- Testar limpar todos os campos da Etapa VI na edição. O comportamento esperado agora é remover o registro `situacao_escolar` daquele aluno.
- Após deploy, recarregar navegador com `Ctrl + F5`, porque `situacao_escolar.js` é novo/alterado e pode ficar em cache.

---

## Revisão de consistência local — 11/09/2026

Esta revisão comparou o complemento acima com o código existente neste repositório. As orientações propostas pelo outro agente são tecnicamente adequadas como **estado final desejado**, sobretudo por melhorar segurança do autocomplete, idempotência da migração e manutenção do stepper. Elas não devem, contudo, ser interpretadas como já aplicadas integralmente neste checkout.

### Complementos que fazem sentido manter

- Persistir `status` e `status_outro` no modelo e na rotina de salvamento.
- Tornar a migração capaz de adicionar colunas em uma tabela `situacao_escolar` já existente.
- Retornar vazio antes de dois caracteres, ignorar nomes nulos e usar valores distintos no autocomplete.
- Criar as sugestões com `document.createElement` e `textContent`, em vez de interpolar nomes do banco em `innerHTML`.
- Calcular as etapas dinamicamente em `editar.js`, evitando nova manutenção manual quando outra etapa for criada.
- Disponibilizar toda a Etapa VI na tela de edição, com valores previamente salvos e campos condicionais equivalentes aos do cadastro novo.

### Divergências identificadas neste checkout

1. `app/models.py` já contém `status` e `status_outro`, mas o relatório anterior ainda os apresentava como pendência inicial. A pendência foi resolvida no modelo.
2. `scripts/migrate_situacao_escolar.py` ainda está no formato simples de `create(..., checkfirst=True)`. Portanto, em uma base que criou a tabela antes dos campos de status, ele **não** adicionará `status` e `status_outro`; a versão aditiva completa descrita no complemento continua necessária.
3. `scripts/postgres_schema.sql` não consta entre as mudanças locais observadas. A afirmação de que ele recebeu a tabela e o índice deve ser tratada como instrução para aplicação futura, e não como fato deste checkout.
4. A etapa VI de edição foi iniciada, mas precisa ser revisada antes de produção: ela deve manter as variáveis Jinja existentes do template, apresentar também `tipo_instituicao_outro` e `turno_outro`, carregar `situacao_escolar.js` antes de `editar.js` e não conter texto literal de escape como `` `n `` no HTML.
5. O endpoint atual do autocomplete ainda não incorpora todas as proteções descritas no complemento (mínimo de dois caracteres, `isnot(None)`, `distinct()` e renderização segura no cliente).

### Ordem recomendada para concluir com segurança

1. Corrigir e testar a Etapa VI da edição com um aluno sem situação escolar e outro com todas as opções “Outros”.
2. Substituir a migração simples pela versão aditiva do complemento e executá-la uma única vez por ambiente.
3. Aplicar as melhorias do endpoint e do JavaScript do autocomplete.
4. Atualizar `scripts/postgres_schema.sql` somente se ele for usado para provisionar novas bases PostgreSQL.
5. Executar testes de criação, edição, autocomplete e limpeza da Etapa VI; em seguida, fazer `Ctrl + F5` no navegador após o deploy.

Com essa distinção, o complemento do outro agente pode ser utilizado como roteiro de finalização, sem ocultar as diferenças entre o estado documentado e o código efetivamente presente neste repositório.