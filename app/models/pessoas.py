"""
================================================================================
PESSOAS.PY - Alunos e dados escolares
================================================================================

Contém:
    - Aluno           : estudante matriculado.
    - SituacaoEscolar : extensão 1:1 do Aluno (dados escolares atuais).

ONDA 3A
    Dez campos que antes viviam em `identificacao_json` viraram colunas reais
    em `Aluno`: dados civis (orgao_rg, nacionalidade, natural_uf/cidade) e
    familiares (nome_mae/cpf_mae, nome_pai/cpf_pai) e de acompanhamento
    (vai_acompanhado_aulas, acompanhante_aulas).

ONDA 3A-BIS
    `escolaridade_json` foi substituído por `documentos_entregues` (JSONB),
    que guarda o mesmo formato `{'doc_entregue': {doc_id: bool}}` mas com
    nome semanticamente correto.

    O JSON antigo `_escolaridade_json` continua existindo como fallback
    até a Onda 3C, quando será removido junto com os demais.
================================================================================
"""

from app.models.base import db, json, datetime, date, get_local_now, JSONType


# =============================================================================
# ALUNO
# =============================================================================

class Aluno(db.Model):
    """
    Estudante matriculado.

    Dados sensíveis (identificação, socioeconômico, diversidade) estão
    gradualmente migrando para colunas e tabelas estruturadas (ver
    `perfis.py`). Durante a Onda 3A, os JSONs originais ainda existem
    como fallback.

    Regras:
        - `matricula` é propriedade derivada: `{id:05d}.{ano_atual}`.
        - `idade` é propriedade calculada em runtime (não persiste).
        - `nome_social` deve prevalecer sobre `nome` em exibições.
        - `foto_path` é o caminho relativo da foto; use a property `foto`.
    """
    __tablename__ = 'aluno'

    id: int = db.Column(db.Integer, primary_key=True)
    nome: str = db.Column(db.String(100), nullable=False)
    nome_social: str = db.Column(db.String(100))
    ativo: bool = db.Column(db.Boolean, default=True, nullable=False)
    data_nascimento: date = db.Column(db.Date)
    foto_path: str = db.Column(db.String(255))

    # --- Onda 3A-bis: JSONB nativo para flags de documentos -------------------
    # Formato: {'doc_entregue': {'doc_aluno': True, 'doc_termo': False, ...}}
    documentos_entregues: dict = db.Column(JSONType, nullable=True)

    # --- JSONs legados (serão removidos na Onda 3C) ---------------------------
    # Acessar sempre via properties `escolaridade_json`, etc. NUNCA pelas
    # colunas `_escolaridade_json`, etc.
    _escolaridade_json: str = db.Column('escolaridade_json', db.Text)
    _identificacao_json: str = db.Column('identificacao_json', db.Text)
    # Legado: objeto JSON com renda_familiar, residente_maior_renda,
    # pessoas_residencia, ocupacao, beneficio_social_status,
    # beneficio_social_nome, meio_transporte e vulnerabilidade_social.
    # A leitura passa por `socioeconomico_json` e cai neste campo apenas
    # enquanto o PerfilSocioeconomico estruturado não existir.
    _socioeconomico_json: str = db.Column('socioeconomico_json', db.Text)
    _diversidade_json: str = db.Column('diversidade_json', db.Text)

    cpf: str = db.Column(db.String(20))
    rg: str = db.Column(db.String(50))
    whatsapp: str = db.Column(db.String(30))
    email: str = db.Column(db.String(120))
    nivel: str = db.Column(db.String(20))

    # --- Onda 3A: campos migrados de `identificacao_json` --------------------
    orgao_rg: str = db.Column(db.String(20))
    nacionalidade: str = db.Column(db.String(50))
    natural_uf: str = db.Column(db.String(2))
    natural_cidade: str = db.Column(db.String(100))
    nome_mae: str = db.Column(db.String(150))
    cpf_mae: str = db.Column(db.String(20))
    nome_pai: str = db.Column(db.String(150))
    cpf_pai: str = db.Column(db.String(20))
    vai_acompanhado_aulas: bool = db.Column(
        db.Boolean, default=False, nullable=False
    )
    acompanhante_aulas: str = db.Column(db.String(150))

    created_by_id: int = db.Column(
        db.Integer, db.ForeignKey('user.id'), nullable=True
    )
    created_by_name: str = db.Column(db.String(100))
    created_at: datetime = db.Column(db.DateTime, default=get_local_now)

    unidade_id: int = db.Column(
        db.Integer, db.ForeignKey('unidade.id'), nullable=True
    )

    # -------------------------------------------------------------------------
    # Properties derivadas
    # -------------------------------------------------------------------------

    @property
    def matricula(self) -> str:
        """Número de matrícula no formato NNNNN.YYYY (id + ano corrente)."""
        if not self.id:
            return None
        return f"{self.id:05d}.{datetime.utcnow().year}"

    @property
    def foto(self) -> str:
        """Alias para `foto_path` (compatibilidade com templates legados)."""
        return self.foto_path

    @property
    def idade(self) -> int:
        """
        Idade atual em anos completos, calculada a partir de `data_nascimento`.
        Retorna 0 se a data não estiver preenchida.
        """
        if not self.data_nascimento:
            return 0
        hoje = date.today()
        return hoje.year - self.data_nascimento.year - (
            (hoje.month, hoje.day)
            < (self.data_nascimento.month, self.data_nascimento.day)
        )

    # -------------------------------------------------------------------------
    # JSON acessors (legado Onda 3A)
    #
    # Padrão: getter devolve dict vazio em caso de None/erro; setter serializa.
    # Estes acessores existem APENAS para fallback durante a transição.
    # Código novo deve usar `app.services.aluno_perfil.get_perfil_completo()`
    # ou os campos diretos em `Aluno` e nas tabelas de `perfis.py`.
    # -------------------------------------------------------------------------

    @property
    def escolaridade_json(self):
        if not self._escolaridade_json:
            return {}
        try:
            return json.loads(self._escolaridade_json)
        except Exception:
            return {}

    @escolaridade_json.setter
    def escolaridade_json(self, value):
        self._escolaridade_json = None if value is None else json.dumps(value)

    @property
    def identificacao_json(self):
        if not self._identificacao_json:
            return {}
        try:
            return json.loads(self._identificacao_json)
        except Exception:
            return {}

    @identificacao_json.setter
    def identificacao_json(self, value):
        self._identificacao_json = None if value is None else json.dumps(value)

    @property
    def socioeconomico_json(self):
        if not self._socioeconomico_json:
            return {}
        try:
            return json.loads(self._socioeconomico_json)
        except Exception:
            return {}

    @socioeconomico_json.setter
    def socioeconomico_json(self, value):
        self._socioeconomico_json = None if value is None else json.dumps(value)

    @property
    def diversidade_json(self):
        if not self._diversidade_json:
            return {}
        try:
            return json.loads(self._diversidade_json)
        except Exception:
            return {}

    @diversidade_json.setter
    def diversidade_json(self, value):
        self._diversidade_json = None if value is None else json.dumps(value)

    # -------------------------------------------------------------------------
    # Relacionamentos
    # -------------------------------------------------------------------------

    unidade = db.relationship('Unidade', backref='alunos_unidade')
    created_by = db.relationship(
        'User', backref='alunos_criados', foreign_keys=[created_by_id]
    )

    situacao_escolar = db.relationship(
        'SituacaoEscolar',
        back_populates='aluno',
        uselist=False,
        cascade='all, delete-orphan',
    )

    # N:N com Turma via tabela de associação `inscricoes`.
    turmas = db.relationship(
        'Turma',
        secondary='inscricoes',
        backref=db.backref('alunos', lazy='dynamic', overlaps='inscricoes,turma'),
        overlaps='inscricoes,turma',
    )

    # -------------------------------------------------------------------------
    # Helpers de documentos (Onda 3A-bis)
    # -------------------------------------------------------------------------

    def documentos_dict(self) -> dict:
        """
        Retorna `{'doc_entregue': {doc_id: bool}}` já normalizado.

        Prefere `documentos_entregues` (JSONB, Onda 3A-bis); cai no JSON
        legado `escolaridade_json` se ainda não houver dado novo.

        Sempre devolve um dict — nunca None — para simplificar templates.
        """
        atual = self.documentos_entregues
        if atual and isinstance(atual, dict):
            return atual
        # Fallback: JSON legado
        legado = self.escolaridade_json or {}
        return legado if isinstance(legado, dict) else {}

    def documento_entregue(self, doc_id: str) -> bool:
        """True se o documento foi marcado como entregue."""
        docs = self.documentos_dict()
        entregues = docs.get('doc_entregue', {}) or {}
        return bool(entregues.get(doc_id, False))


# =============================================================================
# SITUAÇÃO ESCOLAR
# =============================================================================

class SituacaoEscolar(db.Model):
    """
    Situação escolar atual do aluno (extensão 1:1 de `aluno`).

    Separada de `Aluno` para:
        - manter o cadastro principal leve;
        - permitir versionamento futuro sem inflar a tabela `aluno`;
        - tirar do JSON legado os dados escolares.

    Campos com finalidade "Outro":
        - `escolaridade_outro`, `status_outro`, `tipo_instituicao_outro`,
          `turno_outro` só são preenchidos quando o valor canônico é 'Outro'.

    Regras:
        - Um aluno tem no máximo UMA situação escolar (unique em aluno_id).
        - `updated_at` é atualizado automaticamente pelo SQLAlchemy.
    """
    __tablename__ = 'situacao_escolar'
    __table_args__ = (
        db.Index(
            'ix_situacao_escolar_unidade_nome',
            'unidade_id', 'nome_instituicao',
        ),
    )

    id: int = db.Column(db.Integer, primary_key=True)
    aluno_id: int = db.Column(
        db.Integer, db.ForeignKey('aluno.id'), nullable=False, unique=True
    )
    unidade_id: int = db.Column(
        db.Integer, db.ForeignKey('unidade.id'), nullable=True
    )

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

    created_at: datetime = db.Column(
        db.DateTime, default=get_local_now, nullable=False
    )
    updated_at: datetime = db.Column(
        db.DateTime, default=get_local_now, onupdate=get_local_now, nullable=False
    )

    aluno = db.relationship('Aluno', back_populates='situacao_escolar')
    unidade = db.relationship('Unidade', backref='situacoes_escolares')