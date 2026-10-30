"""
Helpers compartilhados de semente para os testes pós-Onda 4.

Duas migrations mudaram o schema e tornaram obrigatórios campos que antes
podiam ficar omissos nas sementes:

    - ``d4e5f6a7b8c9`` (programa obrigatório na oferta): ``TurmaCurso.programa``
      passou a ``nullable=False``. Toda oferta precisa informar um programa.
    - ``c3d4e5f6a7b8`` (inscrição exige oferta): ``Inscricao.turma_curso_id``
      passou a ``nullable=False``. Não existe mais inscrição "sem curso" (NULL);
      o vínculo do aluno é sempre uma oferta concreta ``TurmaCurso``.

H5a (agenda só na grade): as sementes NÃO escrevem mais as colunas escalares
``dias_semana``/``hora_inicio``/``hora_fim`` de ``Turma``/``TurmaCurso``. Este
módulo concentra o caminho único para montar a agenda de uma oferta:

``aplicar_grade(oferta, dias_semana, hora_inicio, hora_fim)`` → grava a grade
uniforme equivalente (CSV de dias + par único) via ``definir_grade``.

``nova_oferta(..., dias_semana=..., hora_inicio=..., hora_fim=...)`` continua
aceitando o trio por compatibilidade, mas o converte em grade — o construtor
do modelo nunca recebe as colunas escalares.

``nova_inscricao`` cria e persiste uma ``Inscricao`` sempre vinculada a uma
oferta (``turma_curso_id`` obrigatório).

``nova_oferta`` exige professor (G1/P2, ``d6e7f8a9b0c1``): quem não passa
``professor_id=`` reusa o ``professor_semente`` da unidade.

``login_as`` fixa a identidade do ``test_client`` e **descarta o cache do
Flask-Login em ``g``** — necessário quando o teste troca de perfil no meio.
"""

from flask import g, has_app_context

from app import db
from app.models import Inscricao, TurmaCurso, User
from app.services.turma_curso_horario import definir_grade, grade_da_oferta
from app.utils.dias_semana import csv_para_weekdays

#: Programa padrão usado pelas sementes quando o teste não exige um específico.
PROGRAMA_PADRAO = "Programa de Teste"


def login_as(client, user, unidade_id=None):
    """Loga `user` (id ou objeto) no `client` e invalida o cache de `g`.

    O fixture `app` da suíte mantém um app context aberto durante o teste e o
    Flask reutiliza esse AppContext em cada request; como `flask.g` vive no
    AppContext, o `_login_user` cacheado pelo Flask-Login vaza para as
    requisições seguintes e trocar só o `_user_id` da sessão **não** troca o
    usuário (o segundo cliente age como o primeiro). Em produção cada request
    empurra seu próprio AppContext, então não é bug de aplicação.

    Este helper é o caminho único para quem precisa de mais de um perfil na
    mesma função: limpa `g._login_user` (o próximo request recarrega o usuário
    pela sessão) e grava a sessão. Testes com um único usuário continuam
    usando seus helpers locais — o resultado deles não muda.
    """
    if has_app_context():
        g.pop("_login_user", None)
    with client.session_transaction() as sess:
        sess["_user_id"] = str(getattr(user, "id", user))
        sess["_fresh"] = True
        if unidade_id is not None:
            sess["unidade_id"] = unidade_id


def professor_semente(unidade_id=None, *, email="prof.semente@x.com", nome="Prof Semente"):
    """Garante um ``User`` professor e devolve a linha (idempotente por email).

    G1/P2 (``d6e7f8a9b0c1``): ``turma_curso.professor_id`` é NOT NULL — sementes
    que criam mais de uma oferta por teste usam este professor compartilhado em
    vez de criar um por oferta (o email é único globalmente).
    """
    prof = User.query.filter_by(email=email).first()
    if prof is None:
        prof = User(
            name=nome, email=email, role="professor",
            first_login=False, unidade_id=unidade_id,
        )
        db.session.add(prof)
        db.session.flush()
    return prof


def itens_grade(dias_semana, hora_inicio, hora_fim):
    """``[(weekday, início, fim)]`` de um CSV de dias + par único (uniforme).

    Descarta domingo (fora do domínio gravável 0–5) e devolve lista vazia
    quando falta dia ou horário — o chamador decide (normalmente erro de
    contrato, já que toda oferta tem agenda completa desde o H2).
    """
    dias = [d for d in csv_para_weekdays(dias_semana) if 0 <= d <= 5]
    if not dias or hora_inicio is None or hora_fim is None:
        return []
    return [(d, hora_inicio, hora_fim) for d in sorted(set(dias))]


def aplicar_grade(
    oferta,
    dias_semana,
    hora_inicio,
    hora_fim,
    *,
    salvar=True,
):
    """Grava na oferta a grade uniforme equivalente ao CSV + par informado.

    Substitui o antigo hábito de semear ``dias_semana``/``hora_inicio``/
    ``hora_fim`` no construtor do modelo (H5a: a grade é a única fonte).
    Devolve os itens aplicados; não faz commit (só ``flush`` opcional).
    """
    itens = itens_grade(dias_semana, hora_inicio, hora_fim)
    if itens:
        definir_grade(oferta, itens)
    if salvar:
        db.session.flush()
    return itens


def grade_atual(oferta):
    """Itens ``(dia, início, fim)`` da grade da oferta (leitura auxiliar)."""
    return [
        (l.dia_semana, l.hora_inicio, l.hora_fim) for l in grade_da_oferta(oferta)
    ]


def nova_oferta(
    turma_id,
    curso_id,
    unidade_id,
    *,
    programa=PROGRAMA_PADRAO,
    ativo=True,
    principal=False,
    salvar=True,
    professor_id=None,
    dias_semana=None,
    hora_inicio=None,
    hora_fim=None,
    grade=None,
    **campos,
):
    """Cria uma ``TurmaCurso`` com ``programa`` e ``professor_id`` preenchidos.

    A agenda NUNCA vai para o construtor: ``dias_semana``/``hora_inicio``/
    ``hora_fim`` (ou ``grade=[(dia, início, fim), ...]``) viram linhas de
    ``turma_curso_horario`` via ``definir_grade`` (H5a).

    Aceita ``salvar=False`` apenas para montar o objeto sem gravar (ex.: quando
    o teste quer forçar um IntegrityError no commit).

    ``professor_id`` (G1/P2, migration `d6e7f8a9b0c1`):
    antigo × novo × motivo — antes a semente podia omitir o professor (coluna
    nullable, estado que só existia como dado de teste); agora a coluna é
    NOT NULL no schema e no modelo. Quem não informa o professor reusa o
    `professor_semente` da unidade (idempotente por email) — sementes que
    exigem um professor específico passam `professor_id=` explicitamente.
    """
    if professor_id is None:
        professor_id = campos.pop("professor_id", None)
    else:
        campos.pop("professor_id", None)
    if professor_id is None:
        professor_id = professor_semente(unidade_id).id
    oferta = TurmaCurso(
        turma_id=turma_id,
        curso_id=curso_id,
        unidade_id=unidade_id,
        programa=programa,
        professor_id=professor_id,
        ativo=ativo,
        principal=principal,
        **campos,
    )
    if not salvar:
        return oferta
    db.session.add(oferta)
    db.session.flush()
    itens = list(grade) if grade is not None else itens_grade(
        dias_semana, hora_inicio, hora_fim
    )
    if itens:
        definir_grade(oferta, itens)
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
