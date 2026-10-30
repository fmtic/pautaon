"""Sementes compartilhadas dos testes do I1 (informações do aluno ao professor).

Universo único: 2 unidades, 7 perfis, 3 turmas e 4 ofertas. As turmas/ofetas
cobrem, cada uma, uma condição da regra de acesso:

    T1/O1 — qualificada para `prof` (oferta e turma dele);
    T1/O2 — mesma turma, oferta de `outro` (aluno não inscrito);
    T2/O3 — outra turma de `outro`;
    T3/O4 — turma da `un`, oferta do professor da `un2` (isola a unidade).

`dias_fim` negativo = período encerrado com a inscrição ainda ativa.
"""

from datetime import time, timedelta

from _helpers import nova_inscricao, nova_oferta

from app import db
from app.models import (
    Aluno,
    Curso,
    Inscricao,
    PerfilDiversidade,
    PeriodoLetivo,
    Turma,
    Unidade,
    User,
)
from app.utils.timezone import get_local_now

GRADE = dict(
    dias_semana="Segunda, Terça, Quarta, Quinta, Sexta",
    hora_inicio=time(8),
    hora_fim=time(10),
)


def _usuario(nome, email, role, unidade_id):
    user = User(name=nome, email=email, role=role, first_login=False,
                unidade_id=unidade_id)
    user.set_password("SenhaLocal!123")
    return user


def _turma(nome, unidade_id, periodo, professor_id, inicio, fim):
    return Turma(
        nome=nome, unidade_id=unidade_id, periodo_letivo_id=periodo.id,
        professor_id=professor_id, ativo=True,
        data_inicio=inicio, data_fim=fim,
    )


def seed(app, *, alunos=1, dias_inicio=-30, dias_fim=30):
    """Monta o universo do I1 e devolve os ids (ver docstring do módulo)."""
    hoje = get_local_now().date()
    with app.app_context():
        un = Unidade(nome="Unidade I1", ativo=True)
        un2 = Unidade(nome="Unidade I1 — outra", ativo=True)
        db.session.add_all([un, un2])
        db.session.flush()

        prof = _usuario("Professor I1", "prof.i1@x.com", "professor", un.id)
        outro = _usuario("Professor Outro I1", "outro.i1@x.com", "professor", un.id)
        prof_un2 = _usuario("Professor Un2 I1", "pun2.i1@x.com", "professor", un2.id)
        admin = _usuario("Admin I1", "admin.i1@x.com", "admin", un.id)
        pedagogico = _usuario("Pedagógico I1", "ped.i1@x.com", "pedagogico", un.id)
        secretaria = _usuario("Secretaria I1", "sec.i1@x.com", "secretaria", un.id)
        gerencia = _usuario("Gerência I1", "ger.i1@x.com", "gerencia", un.id)
        servico_social = _usuario(
            "Serviço Social I1", "ss.i1@x.com", "servico_social", un.id,
        )
        db.session.add_all([
            prof, outro, prof_un2, admin, pedagogico, secretaria, gerencia,
            servico_social,
        ])
        db.session.flush()

        inicio = hoje + timedelta(days=dias_inicio)
        fim = hoje + timedelta(days=dias_fim)
        periodo = PeriodoLetivo(
            nome="P I1", data_inicio=inicio, data_fim=fim,
            unidade_id=un.id, ativo=True,
        )
        db.session.add(periodo)
        db.session.flush()

        t1 = _turma("Turma I1", un.id, periodo, prof.id, inicio, fim)
        t2 = _turma("Turma Outro I1", un.id, periodo, outro.id, inicio, fim)
        t3 = _turma("Turma Un2 I1", un.id, periodo, None, inicio, fim)
        db.session.add_all([t1, t2, t3])
        db.session.flush()

        cursos = [
            Curso(nome=f"Curso I1 {i}", unidade_id=un.id, ativo=True)
            for i in range(4)
        ]
        db.session.add_all(cursos)
        db.session.flush()

        o1 = nova_oferta(
            t1.id, cursos[0].id, un.id, principal=True,
            professor_id=prof.id, **GRADE,
        )
        o2 = nova_oferta(
            t1.id, cursos[1].id, un.id, principal=False,
            professor_id=outro.id, **GRADE,
        )
        o3 = nova_oferta(
            t2.id, cursos[2].id, un.id, principal=True,
            professor_id=outro.id, **GRADE,
        )
        o4 = nova_oferta(
            t3.id, cursos[3].id, un.id, principal=True,
            professor_id=prof_un2.id, **GRADE,
        )

        ids_alunos = []
        for indice in range(alunos):
            aluno = Aluno(
                nome=f"Aluno I1 {indice}", unidade_id=un.id, ativo=True,
            )
            db.session.add(aluno)
            db.session.flush()
            nova_inscricao(aluno.id, t1.id, o1.id)
            ids_alunos.append(aluno.id)

        db.session.commit()
        return {
            "un": un.id,
            "un2": un2.id,
            "prof": prof.id,
            "outro": outro.id,
            "prof_un2": prof_un2.id,
            "admin": admin.id,
            "pedagogico": pedagogico.id,
            "secretaria": secretaria.id,
            "gerencia": gerencia.id,
            "servico_social": servico_social.id,
            "periodo": periodo.id,
            "t1": t1.id,
            "t2": t2.id,
            "t3": t3.id,
            "o1": o1.id,
            "o2": o2.id,
            "o3": o3.id,
            "o4": o4.id,
            "aluno": ids_alunos[0],
            "alunos": ids_alunos,
        }


def mais_alunos(app, ids, quantidade):
    """Mais N alunos inscritos na mesma oferta qualificada (sem religar o seed)."""
    with app.app_context():
        novos = []
        for _ in range(quantidade):
            aluno = Aluno(
                nome=f"Aluno I1 extra {len(novos)}",
                unidade_id=ids["un"], ativo=True,
            )
            db.session.add(aluno)
            db.session.flush()
            nova_inscricao(aluno.id, ids["t1"], ids["o1"])
            novos.append(aluno.id)
        db.session.commit()
        return novos


def mudar(app, modelo, registro_id, **campos):
    with app.app_context():
        obj = db.session.get(modelo, registro_id)
        for campo, valor in campos.items():
            setattr(obj, campo, valor)
        db.session.commit()


def conteudo(
    app, aluno_id, *, acompanhante=None, vai=None, instrucoes=None,
    medicacao=None, medicamento=None, nascimento=None,
):
    """Preenche (ou limpa) os campos da ficha que o I1 lê."""
    with app.app_context():
        aluno = db.session.get(Aluno, aluno_id)
        if acompanhante is not None:
            aluno.acompanhante_aulas = acompanhante
        if vai is not None:
            aluno.vai_acompanhado_aulas = vai
        if nascimento is not None:
            aluno.data_nascimento = nascimento

        perfil = PerfilDiversidade.query.filter_by(aluno_id=aluno_id).first()
        if perfil is None:
            perfil = PerfilDiversidade(
                aluno_id=aluno_id, unidade_id=aluno.unidade_id,
            )
            db.session.add(perfil)
        if instrucoes is not None:
            perfil.informacoes_para_professor = instrucoes
        if medicacao is not None:
            perfil.saude_medicacao = medicacao
        if medicamento is not None:
            perfil.saude_medicamento_nome = medicamento
        db.session.commit()


def dois_blocos(app, aluno_id):
    conteudo(
        app, aluno_id,
        acompanhante="Mãe", vai=True,
        instrucoes="Usa óculos e precisa de lugar na frente.",
    )


def desativar_inscricao(app, aluno_id):
    with app.app_context():
        inscricao = Inscricao.query.filter_by(aluno_id=aluno_id).first()
        inscricao.ativo = False
        db.session.commit()


def info(client, aluno_id):
    return client.get(f"/aluno/{aluno_id}/info-professor")


def pauta(client, ids, oferta_id=None):
    """GET da pauta — T1 tem 2 ofertas ativas, então a oferta é explícita."""
    oferta_id = oferta_id or ids["o1"]
    return client.get(
        f"/frequencia?turma_id={ids['t1']}&turma_curso={oferta_id}",
    )


def impressao(client, ids):
    """Impressão da pauta — com 2 ofertas ativas o `turma_curso` é obrigatório."""
    return client.get(
        f"/turma/{ids['t1']}/imprimir-pauta?turma_curso={ids['o1']}",
    )
