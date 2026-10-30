# ruff: noqa: F811
"""A1 — não regressão das saídas existentes com o Valor do Esportista.

O valor é um dado ADICIONAL: pauta impressa (mês e completa), relatório de
frequência e exportação XLSX precisam produzir exatamente a mesma saída com e
sem valor preenchido. Também cobre registro antigo (valor NULL).
"""

from io import BytesIO
from zipfile import ZipFile

from _helpers import login_as
from test_valor_esportista_lancamento import _cenario, _post

from app import db
from app.models import Frequencia, User


def _login_pedagogico(app, client, ids):
    with app.app_context():
        pedagogico = User(
            name="Pedagógico A1V", email="ped.a1v@x.com", role="pedagogico",
            first_login=False, unidade_id=ids["un"],
        )
        pedagogico.set_password("SenhaLocal!123")
        db.session.add(pedagogico)
        db.session.commit()
        ped_id = pedagogico.id
    login_as(client, ped_id, ids["un"])


def _pauta(client, ids, mes=None):
    url = f"/turma/{ids['turma']}/imprimir-pauta"
    if mes:
        url += f"?mes={mes}"
    resposta = client.get(url)
    assert resposta.status_code == 200
    return resposta.get_data(as_text=True)


def _anular_valor(app, aluno_id):
    """Simula registro antigo/sem valor: anula a coluna direto no banco.

    Desde a V2 o caminho HTTP não produz mais A–D com valor NULL (é
    pendência), então a comparação "com e sem valor" é feita anulando a coluna
    fora da rota — que é exatamente o estado dos registros anteriores à A1.
    """
    with app.app_context():
        linha = Frequencia.query.filter_by(aluno_id=aluno_id).first()
        linha.valor_esportista_id = None
        db.session.commit()


def test_pauta_impressa_identica_com_e_sem_valor(app, client):
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])
    _post(client, ids, conceito="A", valor_id=ids["ativo"])

    mes = ids["data"][5:7]
    completa_com = _pauta(client, ids)
    mes_com = _pauta(client, ids, mes=mes)

    _anular_valor(app, ids["aluno"])

    assert _pauta(client, ids) == completa_com
    assert _pauta(client, ids, mes=mes) == mes_com


def test_relatorio_de_frequencia_identico(app, client):
    ids = _cenario(app)
    _login_pedagogico(app, client, ids)
    _post(client, ids, conceito="A", valor_id=ids["ativo"])

    url = f"/frequencia_relatorio?turma={ids['turma']}"
    # Consome o flash "Frequência salva com sucesso!" antes de comparar.
    client.get(url)
    com_valor = client.get(url)
    assert com_valor.status_code == 200

    _anular_valor(app, ids["aluno"])

    sem_valor = client.get(url)
    assert sem_valor.status_code == 200
    assert sem_valor.get_data(as_text=True) == com_valor.get_data(as_text=True)


def _abas_xlsx(resposta):
    """Conteúdo XML das planilhas (sem `docProps`, que carrega o horário).

    `openpyxl` não é dependência do projeto (só `xlsxwriter`, para escrever),
    então a comparação é feita no próprio pacote OOXML.
    """
    assert resposta.status_code == 200
    with ZipFile(BytesIO(resposta.data)) as pacote:
        return {
            nome: pacote.read(nome)
            for nome in pacote.namelist()
            if nome.startswith("xl/")
        }


def test_exportacao_xlsx_identica(app, client):
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])
    _post(client, ids, conceito="A", valor_id=ids["ativo"])
    com_valor = _abas_xlsx(client.get("/relatorios/exportar"))

    _anular_valor(app, ids["aluno"])
    sem_valor = _abas_xlsx(client.get("/relatorios/exportar"))

    assert com_valor == sem_valor
    assert com_valor.get("xl/sharedStrings.xml")  # pelo menos uma aba com texto


def test_registro_antigo_sem_valor_carrega(app, client):
    """Linha anterior à A1 (valor NULL) continua abrindo a pauta e o histórico."""
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])
    _post(client, ids, conceito="B", valor_id=ids["ativo"])
    _anular_valor(app, ids["aluno"])

    with app.app_context():
        linha = Frequencia.query.filter_by(aluno_id=ids["aluno"]).first()
        assert linha.valor_esportista_id is None

    resposta = client.get(
        f"/frequencia?turma_id={ids['turma']}&data={ids['data']}"
    )
    assert resposta.status_code == 200
    assert "Aluno A1V" in resposta.get_data(as_text=True)
