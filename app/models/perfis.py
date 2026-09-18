"""
================================================================================
PERFIS.PY - Tabelas auxiliares do aluno (endereço, responsável, perfis)
================================================================================

Criado na Onda 3A. Contém dados que estavam em JSONs do `Aluno` e que agora
têm estrutura própria para permitir consultas, relatórios e extrações.

Tabelas:
    - EnderecoAluno         : 1:1 com Aluno
    - ResponsavelAluno      : 1:N com Aluno
    - PerfilSocioeconomico  : 1:1 com Aluno
    - PerfilDiversidade     : 1:1 com Aluno

Todas as tabelas têm `unidade_id` para filtragem multitenant, `created_at` e
`updated_at` para auditoria.

Relação com os JSONs antigos:
    Estas tabelas são populadas por backfill a partir de
    `identificacao_json`, `socioeconomico_json` e `diversidade_json`.
    Os JSONs continuam existindo como fallback durante a transição (Onda 3A).
    Serão removidos na Onda 3C.
================================================================================
"""

from app.models.base import db, datetime, get_local_now


class EnderecoAluno(db.Model):
    """
    Endereço residencial do aluno (1:1).

    Separado da tabela `aluno` porque:
        - agrupa 8 campos coesos (cep, rua, número, ...);
        - não é consultado na maioria das listagens de aluno;
        - permite evolução futura para 1:N (endereço atual + anterior) sem
          migração grande — basta remover o UNIQUE.
    """
    __tablename__ = 'endereco_aluno'

    id: int = db.Column(db.Integer, primary_key=True)
    aluno_id: int = db.Column(
        db.Integer, db.ForeignKey('aluno.id'), nullable=False, unique=True
    )
    unidade_id: int = db.Column(
        db.Integer, db.ForeignKey('unidade.id'), nullable=True
    )

    cep: str = db.Column(db.String(10))
    rua: str = db.Column(db.String(200))
    numero: str = db.Column(db.String(20))
    bairro: str = db.Column(db.String(100))
    cidade: str = db.Column(db.String(100))
    uf: str = db.Column(db.String(2))
    zona: str = db.Column(db.String(20))                     # Urbana, Rural, Outro
    possui_acesso_internet: bool = db.Column(
        db.Boolean, default=True, nullable=False
    )

    created_at: datetime = db.Column(db.DateTime, default=get_local_now)
    updated_at: datetime = db.Column(
        db.DateTime, default=get_local_now, onupdate=get_local_now
    )

    aluno = db.relationship(
        'Aluno',
        backref=db.backref('endereco', uselist=False, cascade='all, delete-orphan'),
    )
    unidade = db.relationship('Unidade', backref='enderecos_aluno')


class ResponsavelAluno(db.Model):
    """
    Responsável legal ou contato de emergência do aluno (1:N).

    O formulário atual coleta 1 responsável, mas o schema aceita N.
    Se no futuro um aluno tiver pai e mãe cadastrados, ou responsável +
    contato de emergência, não precisa migrar nada.

    O backfill cria 1 linha por aluno a partir de `identificacao_json`.
    """
    __tablename__ = 'responsavel_aluno'

    id: int = db.Column(db.Integer, primary_key=True)
    aluno_id: int = db.Column(
        db.Integer, db.ForeignKey('aluno.id'), nullable=False
    )
    unidade_id: int = db.Column(
        db.Integer, db.ForeignKey('unidade.id'), nullable=True
    )

    tipo: str = db.Column(db.String(30))                     # Pai, Mãe, Avô, ...
    nome: str = db.Column(db.String(150))
    cpf: str = db.Column(db.String(20))
    telefone: str = db.Column(db.String(30))

    created_at: datetime = db.Column(db.DateTime, default=get_local_now)
    updated_at: datetime = db.Column(
        db.DateTime, default=get_local_now, onupdate=get_local_now
    )

    aluno = db.relationship(
        'Aluno',
        backref=db.backref('responsaveis', cascade='all, delete-orphan'),
    )
    unidade = db.relationship('Unidade', backref='responsaveis_aluno')


class PerfilSocioeconomico(db.Model):
    """
    Perfil socioeconômico do aluno (1:1).

    Migrado de `Aluno.socioeconomico_json` na Onda 3A.

    Campos de baixa cardinalidade (`renda_familiar`, `meio_transporte`)
    permanecem como `str` livre por enquanto. CHECK constraints serão
    adicionadas quando houver massa de dados suficiente para definir
    o conjunto canônico.
    """
    __tablename__ = 'perfil_socioeconomico'

    id: int = db.Column(db.Integer, primary_key=True)
    aluno_id: int = db.Column(
        db.Integer, db.ForeignKey('aluno.id'), nullable=False, unique=True
    )
    unidade_id: int = db.Column(
        db.Integer, db.ForeignKey('unidade.id'), nullable=True
    )

    renda_familiar: str = db.Column(db.String(50))
    residente_maior_renda: str = db.Column(db.String(50))
    pessoas_residencia: int = db.Column(db.Integer)
    ocupacao: str = db.Column(db.String(50))
    beneficio_social_status: str = db.Column(db.String(20))
    beneficio_social_nome: str = db.Column(db.String(100))
    meio_transporte: str = db.Column(db.String(30))
    vulnerabilidade_social: bool = db.Column(
        db.Boolean, default=False, nullable=False
    )

    created_at: datetime = db.Column(db.DateTime, default=get_local_now)
    updated_at: datetime = db.Column(
        db.DateTime, default=get_local_now, onupdate=get_local_now
    )

    aluno = db.relationship(
        'Aluno',
        backref=db.backref('perfil_socioeconomico', uselist=False,
                           cascade='all, delete-orphan'),
    )
    unidade = db.relationship('Unidade', backref='perfis_socioeconomicos')


class PerfilDiversidade(db.Model):
    """
    Perfil de diversidade do aluno (1:1).

    Migrado de `Aluno.diversidade_json` na Onda 3A.

    Contém dados sensíveis (gênero, raça/cor, saúde). Não há camada de
    permissão por campo hoje — todo perfil que vê aluno vê tudo. Decisão
    registrada em ata com a equipe.
    """
    __tablename__ = 'perfil_diversidade'

    id: int = db.Column(db.Integer, primary_key=True)
    aluno_id: int = db.Column(
        db.Integer, db.ForeignKey('aluno.id'), nullable=False, unique=True
    )
    unidade_id: int = db.Column(
        db.Integer, db.ForeignKey('unidade.id'), nullable=True
    )

    genero: str = db.Column(db.String(30))
    raca_cor: str = db.Column(db.String(30))

    saude_laudo: bool = db.Column(db.Boolean, default=False, nullable=False)
    saude_medicacao: str = db.Column(db.String(5))           # Sim / Não
    saude_medicamento_nome: str = db.Column(db.String(150))
    saude_observacoes: str = db.Column(db.Text)

    informacoes_para_professor: str = db.Column(db.Text)
    autorizacao_imagem: bool = db.Column(
        db.Boolean, default=False, nullable=False
    )

    created_at: datetime = db.Column(db.DateTime, default=get_local_now)
    updated_at: datetime = db.Column(
        db.DateTime, default=get_local_now, onupdate=get_local_now
    )

    aluno = db.relationship(
        'Aluno',
        backref=db.backref('perfil_diversidade', uselist=False,
                           cascade='all, delete-orphan'),
    )
    unidade = db.relationship('Unidade', backref='perfis_diversidade')


__all__ = [
    'EnderecoAluno',
    'ResponsavelAluno',
    'PerfilSocioeconomico',
    'PerfilDiversidade',
]