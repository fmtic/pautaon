"""AJ5-C — Teste de caracterização do formulário de aluno (trava da refatoração).

A refatoração do AJ5-C (parcial único `_form_aluno.html` + contrato `v`) é
**sem mudança visual**. Esta família congela o HTML renderizado das três
variantes do formulário no HEAD atual:

- `novo` com seletor de unidade (usuário global sem contexto);
- `novo` sem seletor de unidade (usuário vinculado à unidade);
- `editar` com um aluno semeado com TODOS os blocos preenchidos
  (identificação, endereço, socioeconômico, diversidade, responsável,
  situação escolar, documentos entregues, benefícios com `|`,
  acompanhante "Outro" e foto).

O HTML é canonizado antes da comparação (atributos ordenados, whitespace
colapsado, tokens de CSRF removidos, matrícula anonimizada), de forma que
formatação de template não conta — apenas estrutura, valores e textos.
Snapshots em `tests/snapshots/`; regenerar com `AJ5C_ATUALIZAR_SNAPSHOTS=1`.

Nenhum dado pessoal real: nomes/CPFs/telefones são fictícios.
"""

import datetime
import os
import re
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
ATUALIZAR_SNAPSHOTS = os.environ.get("AJ5C_ATUALIZAR_SNAPSHOTS") == "1"

#: Tag que o serializer emite no lugar do `<!DOCTYPE html>`.
DOCTYPE = "[doctype html]"

#: Tags sem fechamento na sintaxe HTML.
VOID = frozenset(
    "area base br col embed hr img input link meta param source track wbr".split()
)

#: `#NNNNN.AAAA`: a matrícula embute o ano corrente (`datetime.utcnow()`), e o
#: `novo.html` hoje carrega o `2026` fixo no badge. Anonimizar para o snapshot
#: continuar válido em qualquer ano.
RE_MATRICULA = re.compile(r"#(\d{5})\.(\d{4})")


# =============================================================================
# CANONIZADOR DE HTML
# =============================================================================


class _Elemento:
    """Nó da árvore: tag, atributos ordenáveis e filhos (elementos ou texto)."""

    __slots__ = ("tag", "attrs", "filhos")

    def __init__(self, tag, attrs=None):
        self.tag = tag
        self.attrs = dict(attrs or {})
        self.filhos = []


class _Construtor(HTMLParser):
    """Constrói a árvore tolerante: endtag órfão é ignorado, texto é coletado."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.raiz = _Elemento("[doc]")
        self.pilha = [self.raiz]

    def _abrir(self, tag, attrs):
        no = _Elemento(tag, attrs)
        self.pilha[-1].filhos.append(no)
        return no

    def handle_starttag(self, tag, attrs):
        no = self._abrir(tag, attrs)
        if tag not in VOID:
            self.pilha.append(no)

    def handle_startendtag(self, tag, attrs):
        self._abrir(tag, attrs)

    def handle_endtag(self, tag):
        for i in range(len(self.pilha) - 1, 0, -1):
            if self.pilha[i].tag == tag:
                del self.pilha[i:]
                break

    def handle_data(self, data):
        texto = re.sub(r"\s+", " ", data).strip()
        if texto:
            self.pilha[-1].filhos.append(texto)

    def handle_comment(self, data):
        pass  # comentários não são renderizados ao usuário

    def handle_decl(self, decl):
        self.raiz.filhos.insert(0, DOCTYPE)


def _descartar_attr(tag, nome, valor):
    if valor is not None:
        valor = re.sub(r"\s+", " ", valor).strip()
        # `value=""` em <input> é equivalente a omitir o atributo (mesmo
        # estado vazio). Em <option> NAO: sem `value` o valor passa a ser o
        # texto — a opção vazia "Selecione" perderia o envio vazio.
        if valor == "" and not (nome == "value" and tag == "option"):
            return True
    return False


def _norm_attr(nome, valor):
    """Valor canônico de atributo: `style` é re-joinado e tem o espaço após
    o dois-pontos normalizado (`a: b` == `a:b` — CSS é agnóstico); os demais
    só colapsam whitespace."""
    if valor is None:
        return ""
    valor = re.sub(r"\s+", " ", valor).strip()
    if nome == "style":
        partes = [p.strip() for p in valor.split(";") if p.strip()]
        partes = [re.sub(r"\s*:\s*", ": ", p, count=1) for p in partes]
        return "; ".join(partes)
    return valor


def _serializar(no, nivel=0, linhas=None):
    if linhas is None:
        linhas = []
        if DOCTYPE in no.filhos:
            no.filhos.remove(DOCTYPE)
            linhas.append(DOCTYPE)
    indent = "  " * nivel
    if isinstance(no, str):
        linhas.append(f"{indent}{no}")
        return linhas
    if no.tag == "[doc]":
        for filho in no.filhos:
            _serializar(filho, nivel, linhas)
        return linhas

    attrs = []
    for nome in sorted(no.attrs):
        valor = no.attrs[nome]
        if _descartar_attr(no.tag, nome, valor):
            continue
        valor_norm = _norm_attr(nome, valor)
        if no.tag == "meta" and nome == "content" and "csrf" in no.attrs.get("name", ""):
            valor_norm = "SCRUB"
        if valor_norm == "":
            attrs.append(nome)
        else:
            attrs.append(f'{nome}="{_escapa(valor_norm)}"')
    abre = f"<{no.tag}{' ' + ' '.join(attrs) if attrs else ''}>"
    if no.tag in VOID and not no.filhos:
        linhas.append(f"{indent}{abre}")
        return linhas
    linhas.append(f"{indent}{abre}")
    for filho in no.filhos:
        _serializar(filho, nivel + 1, linhas)
    if no.tag not in VOID:
        linhas.append(f"{indent}</{no.tag}>")
    return linhas


def _escapa(texto):
    return texto.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


def canonizar(html_texto):
    """HTML cru -> texto canônico determinístico (linha a linha)."""
    construtor = _Construtor()
    construtor.feed(html_texto)
    linhas = _serializar(construtor.raiz)
    # Remove inputs de CSRF por completo (linha do input e eventual wrapper não).
    linhas = [
        ln for ln in linhas
        if not (ln.lstrip().startswith("<input") and 'name="csrf_token"' in ln)
    ]
    texto = "\n".join(linhas)
    return RE_MATRICULA.sub("#MATRICULA", texto)


# =============================================================================
# FIXTURES E SEMENTE
# =============================================================================

SNAP_NOVO_COM_UNIDADES = "aj5c_novo_com_unidades.txt"
SNAP_NOVO_SEM_UNIDADES = "aj5c_novo_sem_unidades.txt"
SNAP_EDITAR_COMPLETO = "aj5c_editar_completo.txt"


@pytest.fixture
def dados(app):
    """Semente fictícia: unidades, admins (local e global) e aluno completo."""
    with app.app_context():
        ua = Unidade(nome="Unidade Aj5c A", ativo=True)
        ub = Unidade(nome="Unidade Aj5c B", ativo=True)
        db.session.add_all([ua, ub])
        db.session.flush()

        admin_local = User(
            name="Admin Local Aj5c", email="admin.local.aj5c@example.com",
            role="admin", unidade_id=ua.id, is_active=True, first_login=False,
        )
        admin_global = User(
            name="Admin Global Aj5c", email="admin.global.aj5c@example.com",
            role="admin", unidade_id=None, is_active=True, first_login=False,
        )
        db.session.add_all([admin_local, admin_global])

        aluno = Aluno(
            nome="Alvo Caracterizacao Aj5c",
            nome_social="Nome Social Aj5c",
            nivel="Básico",
            ativo=True,
            unidade_id=ua.id,
            cpf="52998224725",  # CPF de teste consagrado na literatura
            rg="12.345.678-9",
            orgao_rg="SSP/SP",
            nacionalidade="Brasileira",
            natural_uf="SP",
            natural_cidade="São Paulo",
            nome_mae="Mãe Exemplo Aj5c",
            cpf_mae="52998224725",
            nome_pai="Pai Exemplo Aj5c",
            cpf_pai="52998224725",
            whatsapp="(11) 99999-0001",
            email="aluno.aj5c@example.com",
            data_nascimento=datetime.date(2010, 3, 10),
            vai_acompanhado_aulas=True,
            # Valor fora do catálogo -> o template deve reidratar "Outro" +
            # o texto livre no campo acompanhante_aulas_outro.
            acompanhante_aulas="Vizinha do Bem",
            foto_path="fotos/aluno_aj5c.png",
            documentos_entregues={
                "doc_entregue": {"doc_aluno": True, "doc_laudo": True},
            },
        )
        db.session.add(aluno)
        db.session.flush()

        db.session.add(EnderecoAluno(
            aluno_id=aluno.id, unidade_id=ua.id,
            cep="01001-000", rua="Rua Teste Aj5c", numero="123",
            bairro="Bairro Teste", cidade="São Paulo", uf="SP",
            zona="Urbana", possui_acesso_internet=False,
        ))
        db.session.add(ResponsavelAluno(
            aluno_id=aluno.id, unidade_id=ua.id,
            tipo="Avó", nome="Avó Exemplo Aj5c",
            cpf="52998224725", telefone="(11) 99999-0002",
        ))
        db.session.add(PerfilSocioeconomico(
            aluno_id=aluno.id, unidade_id=ua.id,
            renda_familiar=Decimal("2500.00"),
            residente_maior_renda="Mãe", pessoas_residencia=4,
            ocupacao="CLT", beneficio_social_status="Sim",
            beneficio_social_nome="Bolsa Família | BPC",
            meio_transporte="Ônibus", vulnerabilidade_social=True,
        ))
        db.session.add(PerfilDiversidade(
            aluno_id=aluno.id, unidade_id=ua.id,
            genero="Feminino", raca_cor="Parda",
            saude_laudo=True, tipo_deficiencia="Auditiva",
            saude_medicacao="Sim", saude_medicamento_nome="Dipirona",
            saude_observacoes="Observação de saúde Aj5c",
            informacoes_para_professor="Informação ao professor Aj5c",
            autorizacao_imagem=True,
        ))
        db.session.add(SituacaoEscolar(
            aluno_id=aluno.id, unidade_id=ua.id,
            escolaridade="Ensino superior", ensino_superior_periodo=3,
            status="Outros", status_outro="Afastado temporário",
            nome_instituicao="Escola Exemplo Aj5c",
            tipo_instituicao="Privada", bolsista=True,
            turno="Outros", turno_outro="Madrugada",
        ))
        db.session.commit()
        return {
            "unidade_a": ua.id,
            "admin_local": admin_local.id,
            "admin_global": admin_global.id,
            "aluno": aluno.id,
        }


def _render_canonizado(client, url):
    resposta = client.get(url)
    assert resposta.status_code == 200, f"GET {url} -> {resposta.status_code}"
    return canonizar(resposta.get_data(as_text=True))


def _confrontar_snapshot(nome, atual):
    caminho = PASTA_SNAPSHOTS / nome
    if ATUALIZAR_SNAPSHOTS:
        PASTA_SNAPSHOTS.mkdir(parents=True, exist_ok=True)
        caminho.write_text(atual, encoding="utf-8")
        return
    assert caminho.exists(), (
        f"snapshot {nome} ausente — gere com AJ5C_ATUALIZAR_SNAPSHOTS=1"
    )
    esperado = caminho.read_text(encoding="utf-8")
    if atual != esperado:
        # Ajuda a depurar: primeira linha diferente.
        for i, (ln_a, ln_b) in enumerate(zip(atual.splitlines(), esperado.splitlines())):
            if ln_a != ln_b:
                pytest.fail(f"{nome}: primeira diferença na linha {i + 1}:\n"
                            f"  atual:    {ln_a!r}\n  snapshot: {ln_b!r}")
        pytest.fail(f"{nome}: differing length (atual {len(atual.splitlines())} "
                    f"linhas vs snapshot {len(esperado.splitlines())})")


# =============================================================================
# SNAPSHOTS
# =============================================================================


def test_snapshot_novo_com_unidades(app, client, dados):
    """Usuário global (sem contexto de unidade) vê o seletor de unidade."""
    login_as(client, dados["admin_global"])
    _confrontar_snapshot(SNAP_NOVO_COM_UNIDADES, _render_canonizado(client, "/aluno/novo"))


def test_snapshot_novo_sem_unidades(app, client, dados):
    """Usuário vinculado à unidade cadastra direto, sem seletor."""
    login_as(client, dados["admin_local"], dados["unidade_a"])
    _confrontar_snapshot(SNAP_NOVO_SEM_UNIDADES, _render_canonizado(client, "/aluno/novo"))


def test_snapshot_editar_completo(app, client, dados):
    """Edição com todos os blocos preenchidos (reidratação de cada tipo)."""
    login_as(client, dados["admin_local"], dados["unidade_a"])
    _confrontar_snapshot(
        SNAP_EDITAR_COMPLETO,
        _render_canonizado(client, f"/aluno/editar/{dados['aluno']}"),
    )
