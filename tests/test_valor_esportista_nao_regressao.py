# ruff: noqa: F811
"""AJ16-B — não regressão das saídas existentes com o valor do esportista.

O valor é um dado ADICIONAL da AULA: pauta impressa (mês e completa), relatório
de frequência e exportação XLSX precisam produzir exatamente a mesma saída com
e sem valores registrados. Também cobre aula antiga sem nenhum valor.
"""

from io import BytesIO
from zipfile import ZipFile

from _helpers import login_as
from _valor_aula import cenario, post, valores_da_aula

from app import db
from app.models import RegistroAula, User


def _login_pedagogico(app, client, ids):
    with app.app_context():
        pedagogico = User(
            name="Pedagógico AJ16B", email="ped.aj16b@x.com", role="pedagogico",
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


def _limpar_valores_da_aula(app):
    """Simula aula anterior ao AJ16-B: nenhum valor vinculado."""
    with app.app_context():
        diario = RegistroAula.query.first()
        if diario is not None:
            diario.valores = []
            db.session.commit()


def test_pauta_impressa_identica_com_e_sem_valor(app, client):
    ids = cenario(app)
    login_as(client, ids["admin"], ids["un"])
    post(client, ids, {ids["aluno"]: "A"}, [ids["valores"]["ativo"]])

    mes = ids["data"][5:7]
    completa_com = _pauta(client, ids)
    mes_com = _pauta(client, ids, mes=mes)

    _limpar_valores_da_aula(app)

    assert _pauta(client, ids) == completa_com
    assert _pauta(client, ids, mes=mes) == mes_com


def test_relatorio_de_frequencia_identico(app, client):
    ids = cenario(app)
    _login_pedagogico(app, client, ids)
    post(client, ids, {ids["aluno"]: "A"}, [ids["valores"]["ativo"]])

    url = f"/frequencia_relatorio?turma={ids['turma']}"
    # Consome o flash "Frequência salva com sucesso!" antes de comparar.
    client.get(url)
    com_valor = client.get(url)
    assert com_valor.status_code == 200

    _limpar_valores_da_aula(app)

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
    ids = cenario(app)
    login_as(client, ids["admin"], ids["un"])
    post(client, ids, {ids["aluno"]: "A"}, [ids["valores"]["ativo"]])
    com_valor = _abas_xlsx(client.get("/relatorios/exportar"))

    _limpar_valores_da_aula(app)
    sem_valor = _abas_xlsx(client.get("/relatorios/exportar"))

    assert com_valor == sem_valor
    assert com_valor.get("xl/sharedStrings.xml")  # pelo menos uma aba com texto


def test_registro_antigo_sem_valor_carrega(app, client):
    """Aula anterior ao AJ16-B (sem valores) continua abrindo a pauta."""
    ids = cenario(app)
    login_as(client, ids["admin"], ids["un"])
    post(client, ids, {ids["aluno"]: "B"}, [ids["valores"]["ativo"]])
    _limpar_valores_da_aula(app)

    assert valores_da_aula(app, ids) == []

    resposta = client.get(
        f"/frequencia?turma_id={ids['turma']}&data={ids['data']}"
    )
    assert resposta.status_code == 200
    assert "Aluno AJ16B" in resposta.get_data(as_text=True)
