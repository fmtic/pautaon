"""
Helpers compartilhados de semente para os testes pós-Onda 4.

Duas migrations mudaram o schema e tornaram obrigatórios campos que antes
podiam ficar omissos nas sementes:

    - ``d4e5f6a7b8c9`` (programa obrigatório na oferta): ``TurmaCurso.programa``
      passou a ``nullable=False``. Toda oferta precisa informar um programa.
    - ``c3d4e5f6a7b8`` (inscrição exige oferta): ``Inscricao.turma_curso_id``
      passou a ``nullable=False``. Não existe mais inscrição "sem curso" (NULL);
      o vínculo do aluno é sempre uma oferta concreta ``TurmaCurso``.

Estes dois helpers centralizam os preenchimentos obrigatórios para que as
sementes não repitam o boilerplate nem violem os NOT NULL, mantendo a
finalidade de cada teste.

``nova_oferta`` cria e persiste (add + flush) uma ``TurmaCurso`` com programa
por omissão; aceite ``salvar=False`` apenas para montar o objeto sem gravar
(ex.: quando o teste quer forçar um IntegrityError no commit).

``nova_inscricao`` cria e persiste uma ``Inscricao`` sempre vinculada a uma
oferta (``turma_curso_id`` obrigatório).
"""

from app import db
from app.models import Inscricao, TurmaCurso

#: Programa padrão usado pelas sementes quando o teste não exige um específico.
PROGRAMA_PADRAO = "Programa de Teste"


def nova_oferta(
    turma_id,
    curso_id,
    unidade_id,
    *,
    programa=PROGRAMA_PADRAO,
    ativo=True,
    principal=False,
    salvar=True,
    **campos,
):
    """Cria uma ``TurmaCurso`` com ``programa`` preenchido (NOT NULL)."""
    oferta = TurmaCurso(
        turma_id=turma_id,
        curso_id=curso_id,
        unidade_id=unidade_id,
        programa=programa,
        ativo=ativo,
        principal=principal,
        **campos,
    )
    if salvar:
        db.session.add(oferta)
        db.session.flush()
    return oferta


def nova_inscricao(
    aluno_id,
    turma_id,
    turma_curso_id,
    *,
    ativo=True,
    salvar=True,
    **campos,
):
    """Cria uma ``Inscricao`` vinculada a uma oferta (``turma_curso_id`` NOT NULL)."""
    if turma_curso_id is None:
        raise ValueError(
            "Inscricao exige turma_curso_id (oferta) desde a migration c3d4e5f6a7b8.",
        )
    inscricao = Inscricao(
        aluno_id=aluno_id,
        turma_id=turma_id,
        turma_curso_id=turma_curso_id,
        ativo=ativo,
        **campos,
    )
    if salvar:
        db.session.add(inscricao)
        db.session.flush()
    return inscricao
