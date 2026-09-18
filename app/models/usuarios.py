"""
================================================================================
USUARIOS.PY - Usuários e autenticação
================================================================================

Contém:
    - User : operador humano do sistema (professor, admin, secretaria, etc.)

É referenciado por Turma (professor), ConselhoClasse (instrutor), LogAcao,
além de criadores de Aluno, AgendaServicoSocial, etc.

NOTA ONDA 2B
    A coluna `role` agora tem CHECK constraint (via `__table_args__`), restrita
    ao conjunto canônico definido em `app.models.enums.UserRole`. Valores fora
    desse conjunto são rejeitados pelo banco.
================================================================================
"""

from app.models.base import (
    db, UserMixin, generate_password_hash, check_password_hash,
)
from app.models.enums import UserRole


# Fragmento SQL com os valores válidos de role, montado a partir do enum.
# Mantém a CHECK em sincronia com o Python: se mudar o enum, a constraint
# textual muda junto (mas ainda precisa de migration para aplicar no banco).
_ROLE_VALUES_SQL = ", ".join(f"'{r.value}'" for r in UserRole)


class User(db.Model, UserMixin):
    """
    Usuário do sistema (operador humano).

    Um usuário pode ser:
        - LOCAL: possui `password` (hash Werkzeug) e autentica pelo sistema.
        - AD/LDAP: `is_ad_user=True`, `password=None`; autentica no domínio.
        - GOOGLE: identificado por `google_id`/`google_email`.
        - PENDENTE: `role='pendente'`, aguardando aprovação de um admin.

    Perfis (`role`) conhecidos (ver `app.models.enums.UserRole`):
        'admin', 'pedagogico', 'professor', 'secretaria',
        'servico_social', 'gerencia', 'pendente'.

    Regras:
        - `email` é único globalmente (não é escopado por unidade).
        - `password` é nullable para permitir provisionamento de contas AD
          em bancos PostgreSQL herdados sem quebrar o INSERT.
        - `first_login=True` força troca de senha no primeiro acesso local.
        - `role` tem CHECK constraint — só aceita valores do enum UserRole.
    """
    __tablename__ = 'user'
    __table_args__ = (
        db.CheckConstraint(
            f"role IN ({_ROLE_VALUES_SQL})",
            name='ck_user_role',
        ),
    )

    id: int = db.Column(db.Integer, primary_key=True)
    name: str = db.Column(db.String(100), nullable=False)
    email: str = db.Column(db.String(120), unique=True, nullable=False)

    # Senha local opcional: contas AD/LDAP ficam sem hash local.
    password: str | None = db.Column(db.String(200), nullable=True)

    role: str = db.Column(db.String(20), nullable=False)

    is_active: bool = db.Column(db.Boolean, default=True, nullable=False)
    is_ad_user: bool = db.Column(db.Boolean, default=False, nullable=False)

    unidade_id: int = db.Column(db.Integer, db.ForeignKey('unidade.id'), nullable=True)
    unidade = db.relationship('Unidade', backref='usuarios')

    first_login: bool = db.Column(db.Boolean, default=True)

    # Autenticação federada via Google OAuth
    google_id: str | None = db.Column(db.String(100), unique=True, nullable=True, index=True)
    google_email: str | None = db.Column(db.String(120), nullable=True)

    def set_password(self, password: str) -> None:
        """Gera e persiste o hash Werkzeug da senha local."""
        self.password = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """
        Valida a senha informada contra o hash local.

        Retorna `False` se:
            - o usuário não possui senha local (conta AD/LDAP ou recém-criada);
            - o hash não confere;
            - o hash está corrompido (então o login deve seguir para o provedor
              externo, quando aplicável).
        """
        if not self.password:
            return False
        try:
            return check_password_hash(self.password, password)
        except Exception:
            return False