"""
================================================================================
MODELS - Ponto de entrada do pacote
================================================================================

Reexporta TODOS os modelos do sistema. Código externo deve continuar fazendo:

    from app.models import Aluno, Turma, User, ...

Isso preserva compatibilidade com o `models.py` antigo. NUNCA importe um modelo
por caminho interno (ex.: `app.models.pessoas.Aluno`) fora do próprio pacote —
use sempre este ponto de entrada.

MAPA DE MÓDULOS
---------------
    base             -> imports e convenções (não define modelos)
    enums            -> Enumerações de domínio
    organizacao      -> Unidade, ConfiguracaoSistema
    usuarios         -> User
    pedagogico       -> Curso, Nivel
    academico        -> PeriodoLetivo, Turma, TemaAula
    pessoas          -> Aluno, SituacaoEscolar
    perfis           -> EnderecoAluno, ResponsavelAluno,
                        PerfilSocioeconomico, PerfilDiversidade  (Onda 3A)
    matriculas       -> Inscricao, Transferencia
    calendario       -> DiaBloqueado, DiaBloqueadoTurma
    aulas            -> Frequencia, RegistroAula
    conselho         -> PeriodoConselho, PerguntaConselho, OpcaoProximaTurma,
                        ConselhoClasse, ConselhoResposta
    atendimento      -> Atendimento
    servico_social   -> AgendaServicoSocial, RespostaFormulario
    auditoria        -> LogAcao
    legado           -> Registro  (NÃO usar em código novo)
================================================================================
"""

# A ordem abaixo segue a dependência conceitual entre domínios.
from app.models.organizacao import Unidade, ConfiguracaoSistema
from app.models.usuarios import User
from app.models.pedagogico import Curso, Nivel
from app.models.academico import PeriodoLetivo, Turma, TemaAula
from app.models.pessoas import Aluno, SituacaoEscolar
from app.models.perfis import (
    EnderecoAluno,
    ResponsavelAluno,
    PerfilSocioeconomico,
    PerfilDiversidade,
)
from app.models.matriculas import Inscricao, Transferencia
from app.models.calendario import DiaBloqueado, DiaBloqueadoTurma
from app.models.aulas import Frequencia, RegistroAula
from app.models.conselho import (
    PeriodoConselho,
    PerguntaConselho,
    OpcaoProximaTurma,
    ConselhoClasse,
    ConselhoResposta,
)
from app.models.atendimento import Atendimento
from app.models.servico_social import AgendaServicoSocial, RespostaFormulario
from app.models.auditoria import LogAcao
from app.models.legado import Registro


__all__ = [
    # Organização
    'Unidade', 'ConfiguracaoSistema',
    # Usuários
    'User',
    # Pedagógico
    'Curso', 'Nivel',
    # Acadêmico
    'PeriodoLetivo', 'Turma', 'TemaAula',
    # Pessoas
    'Aluno', 'SituacaoEscolar',
    # Perfis (Onda 3A)
    'EnderecoAluno', 'ResponsavelAluno',
    'PerfilSocioeconomico', 'PerfilDiversidade',
    # Matrículas
    'Inscricao', 'Transferencia',
    # Calendário
    'DiaBloqueado', 'DiaBloqueadoTurma',
    # Aulas
    'Frequencia', 'RegistroAula',
    # Conselho
    'PeriodoConselho', 'PerguntaConselho', 'OpcaoProximaTurma',
    'ConselhoClasse', 'ConselhoResposta',
    # Atendimento
    'Atendimento',
    # Serviço Social
    'AgendaServicoSocial', 'RespostaFormulario',
    # Auditoria
    'LogAcao',
    # Legado
    'Registro',
]