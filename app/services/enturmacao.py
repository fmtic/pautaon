"""ETAPA M2 — Serviço único de criação de inscrição (enturmação por oferta).

Concentra, num só ponto, as regras que estavam duplicadas nas rotas
``registros.enturmar_alunos`` (app/registros/turmas.py) e
``registros.transferir_aluno`` (app/registros/alunos.py):

    - resolução 0/1/2+ ofertas ativas da turma;
    - validação da oferta escolhida (ativa e pertencente à turma);
    - checagem de duplicidade (inscrição ativa do mesmo aluno na mesma
      oferta — espelho do índice único ``uix_inscricao_ativa_aluno_oferta``);
    - criação da ``Inscricao`` com ``data_inicio``.

O serviço **não commita** — quem controla a transação é a rota (ou o
serviço de nível superior). Erros de regra levantam ``ValueError`` com as
mesmas mensagens que as rotas exibem hoje em flash, permitindo que cada
rota preserve seu comportamento/UX atual.
"""

from datetime import date

from app.database import db
from app.models import Inscricao
from app.services.turma_curso import ofertas_ativas

#: Turma sem nenhuma oferta ativa não recebe aluno (Etapa M1).
MSG_TURMA_SEM_OFERTA = (
    "Esta turma ainda não tem curso. Cadastre um curso em "
    "Cursos da Turma antes de enturmar alunos."
)

#: Oferta não escolhida ou inválida (inativa / de outra turma). A rota
#: ``enturmar_alunos`` mostra exatamente esta mensagem em 2+ ofertas sem
#: escolha válida; o serviço a reutiliza para qualquer oferta inválida.
MSG_SELECIONE_OFERTA = (
    "Selecione o curso (oferta) em que os alunos serão enturmados."
)

#: Já existe inscrição ativa do aluno na oferta. ``enturmar_alunos`` trata
#: duplicata como salto silencioso (sem flash); a comparação é feita pela
#: constante, não por texto solto.
MSG_JA_ENTURMADO = "O aluno já está enturmado nessa oferta."


def enturmar_aluno(aluno, turma, oferta_id=None, *, nivel=None, data_inicio=None):
    """Cria a ``Inscricao`` do aluno na oferta da turma. NÃO commita.

    Regras (as mesmas das rotas desde a Etapa M1):
        - 0 ofertas ativas na turma → ``ValueError(MSG_TURMA_SEM_OFERTA)``.
        - ``oferta_id`` omitido: só é aceito quando a turma tem exatamente
          1 oferta ativa (que passa a ser a escolhida); com 2+, exige
          escolha → ``ValueError(MSG_SELECIONE_OFERTA)``.
        - ``oferta_id`` informado: precisa apontar para oferta ATIVA e da
          MESMA turma (resolvida via ``ofertas_ativas(turma.id)``, que já
          filtra por ativo e por turma) → caso contrário,
          ``ValueError(MSG_SELECIONE_OFERTA)``.
        - duplicidade: inscrição ativa do aluno na mesma oferta →
          ``ValueError(MSG_JA_ENTURMADO)`` (rede de segurança além do
          índice único parcial).

    Retorna a ``Inscricao`` criada (já adicionada à sessão, sem flush/commit).
    """
    ofertas = ofertas_ativas(turma.id)
    if not ofertas:
        raise ValueError(MSG_TURMA_SEM_OFERTA)

    if oferta_id is None:
        if len(ofertas) != 1:
            raise ValueError(MSG_SELECIONE_OFERTA)
        oferta = ofertas[0]
    else:
        oferta = next((o for o in ofertas if o.id == oferta_id), None)
        if oferta is None:
            raise ValueError(MSG_SELECIONE_OFERTA)

    duplicada = Inscricao.query.filter_by(
        aluno_id=aluno.id,
        turma_id=turma.id,
        turma_curso_id=oferta.id,
        ativo=True,
    ).first()
    if duplicada:
        raise ValueError(MSG_JA_ENTURMADO)

    inscricao = Inscricao(
        aluno_id=aluno.id,
        turma_id=turma.id,
        turma_curso_id=oferta.id,
        nivel=nivel,
        ativo=True,
        # Usa fuso local em vez de UTC, alinhado com o default do modelo.
        data_inicio=data_inicio or date.today(),
    )
    db.session.add(inscricao)
    return inscricao
