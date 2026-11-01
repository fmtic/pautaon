"""AJ5-E — Trava da ordem dos campos e dos rótulos do formulário de aluno.

O AJ5-E mexe apenas em layout (classes de grade/gutters, largura, espaçamento
e CSS). Este teste congela a **lista ordenada** de todos os controles de
formulário (`input`/`select`/`textarea`/`button` com `name` ou `id`) e de
todos os `<label>` (com `for` e texto), passo por passo, nas três variantes:

- `novo` com seletor de unidade (usuário global);
- `novo` sem seletor (usuário com unidade fixa);
- `editar` com aluno completo.

O AJ5-E não pode alterar essa lista: mesmo DOM, mesma ordem, mesmos
`name`/`id`, mesmos textos de rótulo. Snapshots em `tests/snapshots/`; para
regenerar (somente em mudança intencional de estrutura, nunca de layout):

    AJ5E_ATUALIZAR_ORDEM=1 pytest tests/test_aj5e_ordem_campos.py

Nenhum dado pessoal real: nomes/CPFs/telefones são fictícios.
"""

import datetime
import json
import os
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path

import pytest

from app import db
from app.models import (
    Aluno,
    EnderecoAluno,
    PerfilDiversidade,
    PerfilSocioeconomico,
    ResponsavelAluno,
    SituacaoEscolar,
    Unidade,
    User,
)
from _helpers import login_as

PASTA_SNAPSHOTS = Path(__file__).resolve().parent / "snapshots"
ATUALIZAR = os.environ.get("AJ5E_ATUALIZAR_ORDEM") == "1"

SNAP_NOVO_COM_UNIDADES = "aj5e_ordem_novo_com_unidades.json"
SNAP_NOVO_SEM_UNIDADES = "aj5e_ordem_novo_sem_unidades.json"
SNAP_EDITAR_COMPLETO = "aj5e_ordem_editar_completo.json"

CONTROLES = frozenset({"input", "select", "textarea", "button"})


class _OrdemParser(HTMLParser):
    """Coleta, em ordem de documento, os controles e rótulos do formulário.

    Cada item leva o `step` (`id` do `div.form-step` ancestral) ou `None`
    quando está fora dos passos (seletor de unidade, CSRF, botões do rodapé).
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.itens = []
        self._passo = None
        self._profundidade_div = 0
        self._profundidade_passo = None
        self._label = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "div":
            self._profundidade_div += 1
            classes = (attrs.get("class") or "").split()
            if "form-step" in classes:
                self._passo = attrs.get("id") or ""
                self._profundidade_passo = self._profundidade_div

        if tag == "label":
            item = {
                "step": self._passo,
                "tag": "label",
                "for": attrs.get("for") or "",
                "text": "",
            }
            self.itens.append(item)
            self._label = item
            return

        if tag in CONTROLES:
            nome = attrs.get("name") or ""
            ident = attrs.get("id") or ""
            if nome or ident:
                self.itens.append(
                    {
                        "step": self._passo,
                        "tag": tag,
                        "name": nome,
                        "id": ident,
                    }
                )

    def handle_data(self, data):
        if self._label is not None:
            self._label["text"] += data

    def handle_endtag(self, tag):
        if tag == "label" and self._label is not None:
            self._label["text"] = " ".join(self._label["text"].split())
            self._label = None
        elif tag == "div":
            if (
                self._profundidade_passo is not None
                and self._profundidade_div == self._profundidade_passo
            ):
                self._passo = None
                self._profundidade_passo = None
            self._profundidade_div -= 1


def _extrair_ordem(html: str) -> list:
    parser = _OrdemParser()
    parser.feed(html)
    return parser.itens


def _confrontar(nome: str, atual: list):
    caminho = PASTA_SNAPSHOTS / nome
    if ATUALIZAR:
        PASTA_SNAPSHOTS.mkdir(parents=True, exist_ok=True)
        caminho.write_text(
            json.dumps(atual, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return
    assert caminho.exists(), (
        f"snapshot {nome} ausente — gere com AJ5E_ATUALIZAR_ORDEM=1"
    )
    esperado = json.loads(caminho.read_text(encoding="utf-8"))
    if atual != esperado:
        for i, (item_a, item_e) in enumerate(zip(atual, esperado)):
            if item_a != item_e:
                pytest.fail(
                    f"{nome}: primeira diferença no item {i + 1}:\n"
                    f"  atual:    {item_a!r}\n  snapshot: {item_e!r}"
                )
        pytest.fail(
            f"{nome}: tamanho difere (atual {len(atual)} itens vs "
            f"snapshot {len(esperado)})"
        )


@pytest.fixture
def dados(app):
    """Unidade, admin local, admin global e aluno com todos os blocos."""
    with app.app_context():
        unidade = Unidade(nome="Unidade Aj5e Ordem", ativo=True)
        db.session.add(unidade)
        db.session.flush()

        admin_local = User(
            name="Admin Local Aj5e", email="admin.local.aj5e@example.com",
            role="admin", unidade_id=unidade.id, is_active=True, first_login=False,
        )
        admin_global = User(
            name="Admin Global Aj5e", email="admin.global.aj5e@example.com",
            role="admin", unidade_id=None, is_active=True, first_login=False,
        )
        db.session.add_all([admin_local, admin_global])

        aluno = Aluno(
            nome="Alvo Ordem Aj5e",
            nome_social="Nome Social Aj5e",
            nivel="Básico",
            ativo=True,
            unidade_id=unidade.id,
            cpf="52998224725",
            rg="12.345.678-9",
            orgao_rg="SSP/SP",
            nacionalidade="Brasileira",
            natural_uf="SP",
            natural_cidade="São Paulo",
            nome_mae="Mãe Exemplo Aj5e",
            cpf_mae="52998224725",
            nome_pai="Pai Exemplo Aj5e",
            cpf_pai="52998224725",
            whatsapp="(11) 99999-0001",
            email="aluno.aj5e@example.com",
            data_nascimento=datetime.date(2010, 3, 10),
            vai_acompanhado_aulas=True,
            acompanhante_aulas="Vizinha do Bem",
        )
        db.session.add(aluno)
        db.session.flush()

        db.session.add(EnderecoAluno(
            aluno_id=aluno.id, unidade_id=unidade.id,
            cep="01001-000", rua="Rua Teste Aj5e", numero="123",
            bairro="Bairro Teste", cidade="São Paulo", uf="SP",
            zona="Urbana", possui_acesso_internet=False,
        ))
        db.session.add(ResponsavelAluno(
            aluno_id=aluno.id, unidade_id=unidade.id,
            tipo="Avó", nome="Avó Exemplo Aj5e",
            cpf="52998224725", telefone="(11) 99999-0002",
        ))
        db.session.add(PerfilSocioeconomico(
            aluno_id=aluno.id, unidade_id=unidade.id,
            renda_familiar=Decimal("2500.00"),
            residente_maior_renda="Mãe", pessoas_residencia=4,
            ocupacao="CLT", beneficio_social_status="Sim",
            beneficio_social_nome="Bolsa Família | BPC",
            meio_transporte="Ônibus", vulnerabilidade_social=True,
        ))
        db.session.add(PerfilDiversidade(
            aluno_id=aluno.id, unidade_id=unidade.id,
            genero="Feminino", raca_cor="Parda",
            saude_laudo=True, tipo_deficiencia="Auditiva",
            saude_medicacao="Sim", saude_medicamento_nome="Dipirona",
            saude_observacoes="Observação de saúde Aj5e",
            informacoes_para_professor="Informação ao professor Aj5e",
            autorizacao_imagem=True,
        ))
        db.session.add(SituacaoEscolar(
            aluno_id=aluno.id, unidade_id=unidade.id,
            escolaridade="Ensino superior", ensino_superior_periodo=3,
            status="Outros", status_outro="Afastado temporário",
            nome_instituicao="Escola Exemplo Aj5e",
            tipo_instituicao="Privada", bolsista=True,
            turno="Outros", turno_outro="Madrugada",
        ))
        db.session.commit()
        return {
            "unidade": unidade.id,
            "admin_local": admin_local.id,
            "admin_global": admin_global.id,
            "aluno": aluno.id,
        }


def _render(client, url: str) -> str:
    resposta = client.get(url)
    assert resposta.status_code == 200, f"GET {url} -> {resposta.status_code}"
    return resposta.get_data(as_text=True)


def test_ordem_novo_com_unidades(app, client, dados):
    login_as(client, dados["admin_global"])
    itens = _extrair_ordem(_render(client, "/aluno/novo"))
    _confrontar(SNAP_NOVO_COM_UNIDADES, itens)


def test_ordem_novo_sem_unidades(app, client, dados):
    login_as(client, dados["admin_local"], dados["unidade"])
    itens = _extrair_ordem(_render(client, "/aluno/novo"))
    _confrontar(SNAP_NOVO_SEM_UNIDADES, itens)


def test_ordem_editar_completo(app, client, dados):
    login_as(client, dados["admin_local"], dados["unidade"])
    itens = _extrair_ordem(_render(client, f"/aluno/editar/{dados['aluno']}"))
    _confrontar(SNAP_EDITAR_COMPLETO, itens)


def test_ordem_cobre_os_seis_passos(app, client, dados):
    """Sanidade da extração: passos 1..6 presentes, com controles e rótulos."""
    login_as(client, dados["admin_local"], dados["unidade"])
    itens = _extrair_ordem(_render(client, f"/aluno/editar/{dados['aluno']}"))

    passos = {item["step"] for item in itens if item["step"]}
    assert passos == {f"step-{n}" for n in range(1, 7)}
    for passo in sorted(passos):
        do_passo = [item for item in itens if item["step"] == passo]
        assert any(item["tag"] != "label" for item in do_passo), passo
        # O passo 5 usa caixas de upload com texto próprio, sem <label>.
        if passo != "step-5":
            assert any(item["tag"] == "label" for item in do_passo), passo
