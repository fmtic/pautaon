"""Helpers compartilhados dos testes AJ16-B (valor do esportista na AULA)."""

from datetime import time, timedelta

from sqlalchemy import func
from werkzeug.datastructures import MultiDict

from _helpers import nova_inscricao, nova_oferta

from app import db
from app.models import (
    Aluno,
    Curso,
    Frequencia,
    PeriodoLetivo,
    RegistroAula,
    Turma,
    Unidade,
    User,
    ValorEsportista,
    registro_aula_valor_esportista,
)
from app.utils.logica import carregar_contexto_turma, get_local_now


def cenario(
    app,
    *,
    alunos=1,
    ofertas=1,
    com_valores=True,
    com_inativo=True,
):
    """Unidade + período + turma + N ofertas + alunos + catálogo de valores."""
    hoje = get_local_now().date()
    with app.app_context():
        un = Unidade(nome="Unidade AJ16B", ativo=True)
        un_b = Unidade(nome="Unidade AJ16B B", ativo=True)
        db.session.add_all([un, un_b])
        db.session.flush()

        admin = User(
            name="Admin AJ16B", email="admin.aj16b@x.com", role="admin",
            first_login=False, unidade_id=un.id,
        )
        admin.set_password("SenhaLocal!123")
        professor = User(
            name="Prof AJ16B", email="prof.aj16b@x.com", role="professor",
            first_login=False, unidade_id=un.id,
        )
        professor.set_password("SenhaLocal!123")
        db.session.add_all([admin, professor])
        db.session.flush()

        periodo = PeriodoLetivo(
            nome="P AJ16B",
            data_inicio=hoje - timedelta(days=30),
            data_fim=hoje + timedelta(days=30),
            unidade_id=un.id,
            ativo=True,
        )
        db.session.add(periodo)
        db.session.flush()

        turma = Turma(
            nome="Turma AJ16B", turno="Manhã",
            data_inicio=periodo.data_inicio, data_fim=periodo.data_fim,
            periodo_letivo_id=periodo.id, unidade_id=un.id, ativo=True,
        )
        db.session.add(turma)
        db.session.flush()

        ids_ofertas = []
        for indice in range(ofertas):
            curso = Curso(
                nome=f"Curso AJ16B {indice}", unidade_id=un.id, ativo=True,
            )
            db.session.add(curso)
            db.session.flush()
            ids_ofertas.append(
                nova_oferta(
                    turma.id, curso.id, un.id, principal=(indice == 0),
                    professor_id=professor.id,
                    dias_semana="Segunda, Terça, Quarta, Quinta, Sexta",
                    hora_inicio=time(8), hora_fim=time(10),
                ).id
            )

        ids_alunos = []
        for indice in range(alunos):
            aluno = Aluno(
                nome=f"Aluno AJ16B {indice}", unidade_id=un.id, ativo=True,
            )
            db.session.add(aluno)
            db.session.flush()
            nova_inscricao(aluno.id, turma.id, ids_ofertas[0])
            if ofertas >= 2:
                nova_inscricao(aluno.id, turma.id, ids_ofertas[1])
            ids_alunos.append(aluno.id)

        valores = {}
        if com_valores:
            ativo = ValorEsportista(
                nome="Alegria", unidade_id=un.id, ativo=True,
            )
            outro = ValorEsportista(
                nome="Foco", unidade_id=un.id, ativo=True,
            )
            db.session.add_all([ativo, outro])
            db.session.flush()
            valores = {"ativo": ativo.id, "outro": outro.id}
            if com_inativo:
                inativo = ValorEsportista(
                    nome="Disciplina", unidade_id=un.id, ativo=False,
                )
                db.session.add(inativo)
                db.session.flush()
                valores["inativo"] = inativo.id
        externo = ValorEsportista(
            nome="Externo", unidade_id=un_b.id, ativo=True,
        )
        db.session.add(externo)
        db.session.flush()
        valores["externo"] = externo.id

        db.session.commit()
        return {
            "un": un.id,
            "un_b": un_b.id,
            "admin": admin.id,
            "professor": professor.id,
            "turma": turma.id,
            "ofertas": ids_ofertas,
            "alunos": ids_alunos,
            "aluno": ids_alunos[0],
            "valores": valores,
            "data": carregar_contexto_turma(turma.id)["datas"][0],
        }


def post(client, ids, conceitos=None, valor_ids=None, extras=None):
    """POST /frequencia; `valor_ids` é o conjunto da AULA (campo repetido)."""
    dados = [("turma", str(ids["turma"])), ("data", ids["data"])]
    for aluno_id, conceito in (conceitos or {}).items():
        if conceito is not None:
            dados.append((f"aluno_{aluno_id}", conceito))
    if valor_ids is not None:
        dados.extend(("valor_ids", str(v)) for v in valor_ids)
    for chave, valor in (extras or {}).items():
        dados.append((chave, str(valor)))
    return client.post(
        "/frequencia", data=MultiDict(dados), follow_redirects=False,
    )


def url_pauta(ids, oferta_id=None):
    url = f"/frequencia?turma_id={ids['turma']}&data={ids['data']}"
    if oferta_id:
        url += f"&turma_curso={oferta_id}"
    return url


def corpo_pauta(client, ids, oferta_id=None):
    return client.get(url_pauta(ids, oferta_id)).get_data(as_text=True)


def linha(app, aluno_id):
    with app.app_context():
        return Frequencia.query.filter_by(aluno_id=aluno_id).first()


def registro(app, ids, oferta_idx=0):
    with app.app_context():
        query = RegistroAula.query
        if oferta_idx is None:
            query = query.filter_by(
                turma_id=ids["turma"], turma_curso_id=None,
            )
        else:
            query = query.filter_by(
                turma_curso_id=ids["ofertas"][oferta_idx],
            )
        return query.first()


def valores_da_aula(app, ids, oferta_idx=0):
    """Ids ordenados dos valores vinculados à aula (None se não há diário)."""
    with app.app_context():
        query = RegistroAula.query
        if oferta_idx is None:
            query = query.filter_by(
                turma_id=ids["turma"], turma_curso_id=None,
            )
        else:
            query = query.filter_by(
                turma_curso_id=ids["ofertas"][oferta_idx],
            )
        diario = query.first()
        if diario is None:
            return None
        return sorted(valor.id for valor in diario.valores)


def contagens(app):
    """(frequencia, registro_aula, vínculos de valor) — prova de atomicidade."""
    with app.app_context():
        return (
            Frequencia.query.count(),
            RegistroAula.query.count(),
            db.session.query(func.count())
            .select_from(registro_aula_valor_esportista)
            .scalar(),
        )


def definir_valores(app, ids, valor_ids, oferta_idx=0, *, data=None):
    """Cria/atualiza o diário da aula com o conjunto de valores informado."""
    from datetime import date as _date

    with app.app_context():
        if oferta_idx is None:
            diario = RegistroAula.query.filter_by(
                turma_id=ids["turma"], turma_curso_id=None,
            ).first()
            turma_curso_id = None
        else:
            turma_curso_id = ids["ofertas"][oferta_idx]
            diario = RegistroAula.query.filter_by(
                turma_curso_id=turma_curso_id,
            ).first()
        if diario is None:
            diario = RegistroAula(
                turma_id=ids["turma"],
                turma_curso_id=turma_curso_id,
                data=data or _date.fromisoformat(ids["data"]),
                unidade_id=ids["un"],
            )
            db.session.add(diario)
        diario.valores = list(
            ValorEsportista.query.filter(ValorEsportista.id.in_(valor_ids)).all()
        )
        db.session.commit()
        return diario.id
