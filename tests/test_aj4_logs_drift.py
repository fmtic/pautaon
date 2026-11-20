"""AJ4-A — Drift dos rótulos de `log_acao` (varredura AST do código de app).

O filtro de auditoria (`categoria_acao` / `_CATEGORIAS_ACAO` em `app/auth.py`,
AJ1/AJ3-E2) classifica a ação pelo **prefixo do texto**. Se o código passar a
emitir um rótulo que nenhuma prefixação cobre conscientemente, a linha cai em
`outras` em silêncio — foi exatamente o defeito corrigido em `1e39e23`
(`Exclusão de Turma` selado como exclusão na tela, mas filtrado como `outras`).
Este teste fecha essa porta: varre `app/**/*.py` com `ast` (nunca regex) e
compara o que os emissores gravam com as listas congeladas aqui dentro.

Emissores mapeados na Etapa 1 (somente leitura, censo de 01/11/2026):

    | helper                     | posição do rótulo        | chamadas                             |
    |----------------------------|--------------------------|--------------------------------------|
    | `register_security_log()`  | 1º posicional / `action` | 19 literais                          |
    | `LogAcao(acao=...)`        | keyword `acao`           | 3 literais, 2 constantes, 3 repasses |
    | `_gravar_log_background()` | keyword `acao`           | 2 literais (repasse p/ dinâmica)     |

Os rótulos dinâmicos (f-string do `auditoria_listener`, parâmetro repassado em
`disparo_email`) não são resolvidos pelo varredor por design — ficam listados em
`ROTULOS_DINAMICOS_CONHECIDOS` com `arquivo:linha`; dinâmico novo fora da lista
falha.

Nada aqui lê Postgres: `CENSO_REAL` é o censo da E2 do AJ3 (os 30 rótulos da
união de `pautaon` e `pautaon_ensaio`, 31/10/2026, evidência em
`.tmp/acoes_reais.json`) congelado como conjunto, e `CATEGORIA_ESPERADA` é
decisão **humana**, não cálculo — por isso o teste pega mudança silenciosa de
classificação. Nenhum dado pessoal (e-mail, IP, hash, CPF) aparece neste
arquivo: só rótulos, caminhos e linhas.
"""

from __future__ import annotations

import ast
import re
from functools import lru_cache
from pathlib import Path

import pytest

from app.auth import categoria_acao

RAIZ = Path(__file__).resolve().parents[1]
PASTA_APP = RAIZ / "app"

# ---------------------------------------------------------------------------
# Listas congeladas (nenhuma consulta a banco; decisão humana)
# ---------------------------------------------------------------------------

#: Os 30 rótulos distintos da união `pautaon ∪ pautaon_ensaio` no censo de
#: 31/10/2026 (tabela E2 do relatório AJ3; `.tmp/acoes_reais.json`), mais o
#: rótulo novo do AJ7-A (`Alteração de conselho (gestor)`), que entra com
#: decisão humana explícita antes de existir linha nos bancos reais.
CENSO_REAL = frozenset(
    {
        "Acesso Aprovado",
        "Alterar Aluno",
        "Alterar ConselhoClasse",
        "Alterar Inscricao",
        "Alterar RegistroAula",
        "Alterar TemaAula",
        "Alterar Turma",
        "Alterar TurmaCurso",
        "Alteração de Cadastros",
        "Alteração de conselho (gestor)",
        "Aviso de Invasão/Falha",
        "Cadastro Local",
        "Criar Aluno",
        "Criar ConselhoClasse",
        "Criar Inscricao",
        "Criar RegistroAula",
        "Criar TemaAula",
        "Criar Turma",
        "Criar TurmaCurso",
        "Disparo de E-mail",
        "Editar aluno",
        "Erro E-mail",
        "Excluir turma (lógica)",
        "Exclusão de Turma",
        "Informacao Padrao",
        "Logoff",
        "Manutenção",
        "Remoção Grave",
        "Reset de Senha",
        "Sessões revogadas",
        "Troca de Senha",
    }
)

#: Rótulos que o código EMITE por helper mas que ainda não têm nenhuma linha
#: nos bancos (mesma lista congelada no AJ3-E2; parametrizada para não serem
#: esquecidos quando a primeira linha for gravada). Desde o AJ4-B a asserção 3
#: exige emissor via helper — literatura solta não basta.
ROTULOS_SEM_LINHA = frozenset(
    {
        "Acesso via Google",
        "Alteração da data de entrada na oferta",
        "Cadastro Período Letivo",
        "Desbloqueio de login",
        "Enturmação de aluno na oferta",
        "Gestão de Unidade",
        "Lançamento de frequência ignorado (entrada futura)",
        "Reativação de Turma",
        "Trocar Professor da Oferta",
        "Excluir documento",
        "Vínculo Google",
    }
)

#: Literais congelados que vivem no código SEM ser rótulo de emissor:
#: `DESENTURMADO`/`TRANSFERENCIA` são valores de `motivo_desativacao` e
#: `Excluir aluno` é exemplo da docstring do modelo. Não têm asserção 3
#: (nenhum emissor para guardar); só a classificação congelada (asserção 2)
#: os cobre — separação consciente do AJ4-B.
LITERAIS_NAO_EMITIDOS = frozenset(
    {
        "DESENTURMADO",
        "Excluir aluno",
        "TRANSFERENCIA",
    }
)

#: Universo congelado inteiro (asserções 1, 2 e 4 trabalham sobre ele).
CONGELADOS = CENSO_REAL | ROTULOS_SEM_LINHA | LITERAIS_NAO_EMITIDOS

#: Rótulos do censo que só existem no banco — nenhum emissor no código hoje
#: (herança de versões antigas). Conferidos apenas na classificação congelada;
#: se alguém abrir um emissor para eles, a asserção `SO_NO_BANCO` falha e a
#: migração para `ROTULOS_SEM_LINHA` passa a ser uma decisão consciente.
SO_NO_BANCO = frozenset({"Manutenção"})

#: Rótulo -> categoria. **Decisão humana** (tabela E2 do relatório AJ3, com o
#: `fix(1e39e23)` já aplicado), nunca calculada por `categoria_acao` — é isso
#: que faz o teste pegar a reclassificação silenciosa.
CATEGORIA_ESPERADA = {
    "Acesso Aprovado": "login",
    "Acesso via Google": "outras",
    "Alterar Aluno": "edicao",
    "Alterar ConselhoClasse": "edicao",
    "Alterar Inscricao": "edicao",
    "Alterar RegistroAula": "edicao",
    "Alterar TemaAula": "edicao",
    "Alterar Turma": "edicao",
    "Alterar TurmaCurso": "edicao",
    "Alteração da data de entrada na oferta": "edicao",
    "Alteração de Cadastros": "edicao",
    "Alteração de conselho (gestor)": "edicao",
    "Aviso de Invasão/Falha": "login",
    "Cadastro Local": "login",
    "Cadastro Período Letivo": "outras",
    "Criar Aluno": "criacao",
    "Criar ConselhoClasse": "criacao",
    "Criar Inscricao": "criacao",
    "Criar RegistroAula": "criacao",
    "Criar TemaAula": "criacao",
    "Criar Turma": "criacao",
    "Criar TurmaCurso": "criacao",
    "DESENTURMADO": "outras",
    "Desbloqueio de login": "login",
    "Enturmação de aluno na oferta": "outras",
    "Disparo de E-mail": "outras",
    "Editar aluno": "edicao",
    "Erro E-mail": "outras",
    "Excluir aluno": "exclusao",
    "Excluir documento": "exclusao",
    "Excluir turma (lógica)": "exclusao",
    "Exclusão de Turma": "exclusao",
    "Gestão de Unidade": "outras",
    "Informacao Padrao": "outras",
    "Lançamento de frequência ignorado (entrada futura)": "outras",
    "Logoff": "login",
    "Manutenção": "outras",
    "Reativação de Turma": "outras",
    "Remoção Grave": "exclusao",
    "Reset de Senha": "login",
    "Sessões revogadas": "outras",
    "Troca de Senha": "edicao",
    "Trocar Professor da Oferta": "edicao",
    "TRANSFERENCIA": "outras",
    "Vínculo Google": "outras",
}

#: Rótulos dinâmicos que o varredor **não** resolve, congelados com
#: `arquivo:linha` (a linha do valor passado ao helper) e o padrão emitido.
#: Um dinâmico novo fora desta lista é falha — exige decisão humana explícita.
ROTULOS_DINAMICOS_CONHECIDOS = {
    "app/models/auditoria_listener.py:70": (
        "acao=acao de `before_flush` — f-strings `Criar <Modelo>` (linha 61) "
        "e `Alterar <Modelo>` (linha 63), resolvidas apenas em runtime"
    ),
    "app/services/auth_service.py:99": (
        "acao=action dentro do corpo de `register_security_log` — repasse do "
        "parâmetro; as 19 chamadas pelo nome do helper passam literais, já "
        "cobertos pela asserção 1"
    ),
    "app/utils/disparo_email.py:15": (
        "acao=acao de `_gravar_log_background` — repasse do parâmetro; as "
        "chamadas nas linhas 34/44 passam os literais `Disparo de E-mail` e "
        "`Erro E-mail`, já cobertos pela asserção 1"
    ),
}

#: Rótulos literais/constantes resolvidos no código em 01/11/2026 (tabela da
#: Etapa 1). Sanidade do varredor: se a varredura quebrar (mudou helper, mudou
#: assinatura), o teste falha aqui em vez de passar vazando o drift.
ROTULOS_RESOLVIDOS_ESPERADOS = frozenset(
    {
        "Acesso Aprovado",
        "Acesso via Google",
        "Alteração de Cadastros",
        "Aviso de Invasão/Falha",
        "Cadastro Local",
        "Cadastro Período Letivo",
        "Desbloqueio de login",
        "Disparo de E-mail",
        "Editar aluno",
        "Erro E-mail",
        "Exclusão de Turma",
        "Excluir turma (lógica)",
        "Gestão de Unidade",
        "Informacao Padrao",
        "Logoff",
        "Remoção Grave",
        "Reativação de Turma",
        "Reset de Senha",
        "Sessões revogadas",
        "Troca de Senha",
        "Trocar Professor da Oferta",
        "Vínculo Google",
    }
)

#: Arquivos `.py` varridos em `app/` (102 no censo de entrada; margem para
#: o teste não quebrar por puro crescimento do app).
MIN_ARQUIVOS_VARRIDOS = 90

# ---------------------------------------------------------------------------
# Varredura AST (Etapa 2: `ast`, nunca regex)
# ---------------------------------------------------------------------------

#: helper -> (índice do posicional do rótulo ou None, nome do keyword).
#: Assinaturas conferidas na Etapa 1 (`auth_service.py:79`,
#: `disparo_email.py:8` e o construtor do modelo `LogAcao`).
_HELPERS_ROTULO = {
    "register_security_log": (0, "action"),
    "_gravar_log_background": (None, "acao"),
    "LogAcao": (None, "acao"),
}

_RE_CONSTANTE = re.compile(r"^[A-Z][A-Z0-9_]{1,}$")


class _Resultado:
    """Acúmulo da varredura completa de `app/`."""

    def __init__(self) -> None:
        self.resolvidos: dict[str, list[str]] = {}  # rótulo -> [arquivo:linha]
        self.dinamicos: dict[str, str] = {}          # arquivo:linha -> tipo do valor
        self.strings: set[str] = set()               # toda string literal do app
        self.arquivos = 0

    def registrar(self, rotulo: str, local: str) -> None:
        self.resolvidos.setdefault(rotulo, []).append(local)


def _arquivos_app() -> list[Path]:
    return sorted(
        p for p in PASTA_APP.rglob("*.py") if "__pycache__" not in p.parts
    )


def _constantes_de_modulo(árvore: ast.Module) -> dict[str, str]:
    """Nomes em MAIÚSCULAS atribuídos a literal string no corpo do módulo."""
    constantes: dict[str, str] = {}
    for nodo in árvore.body:
        if not isinstance(nodo, ast.Assign) or len(nodo.targets) != 1:
            continue
        alvo = nodo.targets[0]
        if (
            isinstance(alvo, ast.Name)
            and _RE_CONSTANTE.match(alvo.id)
            and isinstance(nodo.value, ast.Constant)
            and isinstance(nodo.value.value, str)
        ):
            constantes[alvo.id] = nodo.value.value
    return constantes


class _Varredor(ast.NodeVisitor):
    """Uma passada por módulo: rótulos dos helpers + todas as strings."""

    def __init__(self, arquivo_rel: str, resultado: _Resultado):
        self.arquivo_rel = arquivo_rel
        self.resultado = resultado
        self.constantes: dict[str, str] = {}

    def _local(self, nodo: ast.AST) -> str:
        return f"{self.arquivo_rel}:{nodo.lineno}"

    def visit_Call(self, chamada: ast.Call):
        nome = None
        if isinstance(chamada.func, ast.Name):
            nome = chamada.func.id
        elif isinstance(chamada.func, ast.Attribute):
            nome = chamada.func.attr
        espec = _HELPERS_ROTULO.get(nome or "")
        if espec is not None:
            pos, keyword = espec
            expr = None
            for kw in chamada.keywords:
                if kw.arg == keyword:
                    expr = kw.value
                    break
            if expr is None and pos is not None and len(chamada.args) > pos:
                expr = chamada.args[pos]
            if expr is not None:
                if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
                    self.resultado.registrar(expr.value, self._local(chamada))
                elif isinstance(expr, ast.Name) and expr.id in self.constantes:
                    self.resultado.registrar(
                        self.constantes[expr.id], self._local(chamada)
                    )
                else:
                    # Dinâmico: congela arquivo:linha do VALOR (não da chamada).
                    chave = self._local(expr)
                    self.resultado.dinamicos[chave] = type(expr).__name__
        self.generic_visit(chamada)

    def visit_Constant(self, nodo: ast.Constant):
        if isinstance(nodo.value, str):
            self.resultado.strings.add(nodo.value)
        self.generic_visit(nodo)


def _escanear_app() -> _Resultado:
    resultado = _Resultado()
    for arquivo in _arquivos_app():
        rel = arquivo.relative_to(RAIZ).as_posix()
        árvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        varredor = _Varredor(rel, resultado)
        varredor.constantes = _constantes_de_modulo(árvore)
        varredor.visit(árvore)
        resultado.arquivos += 1
    return resultado


@lru_cache(maxsize=1)
def _escaneamento() -> _Resultado:
    """Varredura única por processo: nada aqui toca em banco nenhum."""
    return _escanear_app()


# ---------------------------------------------------------------------------
# Asserções
# ---------------------------------------------------------------------------

def test_scanner_varre_o_app_inteiro():
    """Asserção 5 — sanidade do varredor: a varredura não pode quebrar em silêncio.

    Se alguém renomear `register_security_log`, mudar a assinatura ou quebrar o
    parser, o resultado desabaria e os testes abaixo passariam vazios — este
    segura o piso: no mínimo os rótulos medidos na Etapa 1 e os arquivos do
    censo de entrada.
    """
    esc = _escaneamento()
    assert esc.arquivos >= MIN_ARQUIVOS_VARRIDOS, (
        f"[AJ4-A] varredor achou {esc.arquivos} arquivos; esperado >= "
        f"{MIN_ARQUIVOS_VARRIDOS} — o scanner quebrou?"
    )
    faltando = ROTULOS_RESOLVIDOS_ESPERADOS - set(esc.resolvidos)
    assert not faltando, (
        f"[AJ4-A] o varredor deixou de encontrar rótulos que existiam em "
        f"01/11/2026: {sorted(faltando)} — helper/assinatura mudou?"
    )


def test_rotulo_novo_do_codigo_falha():
    """Asserção 1: todo rótulo literal/constante emitido está congelado.

    Rótulo novo em `register_security_log`/`LogAcao`/`_gravar_log_background`
    só é permitido depois de entrar em `CENSO_REAL` (linha no banco) ou
    `ROTULOS_SEM_LINHA` (recém-emitido) — e com decisão explícita em
    `CATEGORIA_ESPERADA` (ver asserção 4).
    """
    esc = _escaneamento()
    congelados = CONGELADOS
    novos = sorted(set(esc.resolvidos) - congelados)
    assert not novos, (
        f"[AJ4-A] rótulo(s) novo(s) de `log_acao` sem classificação "
        f"consciente: {novos}\n"
        f"  locais: {[esc.resolvidos[r] for r in novos]}\n"
        f"  → classifique em CATEGORIA_ESPERADA e acrescente a "
        f"ROTULOS_SEM_LINHA (ou CENSO_REAL, se já houver linha nos bancos)."
    )


def test_dinamico_novo_fora_da_lista_falha():
    """Asserção 1 (parte dinâmica): f-string/variável nova como rótulo é drift.

    O pool de rótulos dinâmicos só cresce com decisão humana: a entrada nova
    vai para `ROTULOS_DINAMICOS_CONHECIDOS` com `arquivo:linha` e o padrão.
    Sumir da lista também é decisão: por isso a igualdade é conferida dos dois
    lados.
    """
    esc = _escaneamento()
    desconhecidos = sorted(set(esc.dinamicos) - set(ROTULOS_DINAMICOS_CONHECIDOS))
    assert not desconhecidos, (
        f"[AJ4-A] rótulo dinâmico novo em {desconhecidos} "
        f"(tipos: {[esc.dinamicos[d] for d in desconhecidos]}). "
        f"Dinâmico não se resolve no AST: acrescente a "
        f"ROTULOS_DINAMICOS_CONHECIDOS com o padrão emitido, ou passe a "
        f"gravar literal/constante."
    )
    sumidos = sorted(set(ROTULOS_DINAMICOS_CONHECIDOS) - set(esc.dinamicos))
    assert not sumidos, (
        f"[AJ4-A] o dinâmico congelado {sumidos} não foi mais encontrado — "
        f"mudou de linha ou deixou de existir; atualize a lista."
    )


@pytest.mark.parametrize("rotulo", sorted(CONGELADOS))
def test_classificacao_congelada(rotulo):
    """Asserção 2: a categoria decidida por humano é a que `categoria_acao` devolve.

    Vale para todo o censo (inclusive o `SO_NO_BANCO`), os rótulos emitidos
    sem linha e os `LITERAIS_NAO_EMITIDOS` — é a guarda contra
    reclassificação silenciosa do dicionário `_CATEGORIAS_ACAO` (o defeito
    do `1e39e23`, em forma de teste).
    """
    assert categoria_acao(rotulo) == CATEGORIA_ESPERADA[rotulo], (
        f"[AJ4-A] `{rotulo}` agora é classificada como "
        f"'{categoria_acao(rotulo)}', mas a decisão humana congelada é "
        f"'{CATEGORIA_ESPERADA[rotulo]}' — mudou `_CATEGORIAS_ACAO`?"
    )


@pytest.mark.parametrize("rotulo", sorted(ROTULOS_SEM_LINHA))
def test_rotulo_sem_linha_ainda_existe_no_codigo(rotulo):
    """Asserção 3: o que foi congelado como "emite, mas sem linha" não pode sumir.

    Desde a separação do AJ4-B a existência exigida é a de **emissor**: o
    rótulo tem de estar resolvido como rótulo de helper
    (`register_security_log`/`LogAcao`/`_gravar_log_background`) — string
    solta em qualquer lugar do arquivo não basta mais (os literais puros
    moram em `LITERAIS_NAO_EMITIDOS` e só passam pela asserção 2). Se o
    emissor deixou de existir (ou o texto mudou), a entrada envelheceu:
    remova de `ROTULOS_SEM_LINHA`/`CATEGORIA_ESPERADA` numa decisão
    consciente.
    """
    esc = _escaneamento()
    assert rotulo in esc.resolvidos, (
        f"[AJ4-A] `{rotulo}` não é mais resolvido como rótulo de emissor em "
        f"app/**.py — o emissor sumiu; remova da lista (com decisão humana)."
    )


def test_outras_exige_decisao_explicita():
    """Asserção 4: nada é 'outras' por omissão.

    `categoria_acao` devolve `outras` para o que não casa — justamente o buraco
    por onde o drift escapa. Então: (a) `CATEGORIA_ESPERADA` cobre o universo
    congelado inteiro; (b) todo rótulo novo que o varredor achar e que caia em
    `outras` precisa de linha explícita no dicionário antes de qualquer teste
    passar.
    """
    congelados = CONGELADOS
    assert set(CATEGORIA_ESPERADA) == congelados, (
        "[AJ4-A] CATEGORIA_ESPERADA e o universo congelado divergem: "
        f"só no dicionário: {sorted(set(CATEGORIA_ESPERADA) - congelados)}; "
        f"só nas listas: {sorted(congelados - set(CATEGORIA_ESPERADA))}."
    )
    esc = _escaneamento()
    por_omissao = sorted(
        r for r in set(esc.resolvidos) - set(CATEGORIA_ESPERADA)
        if categoria_acao(r) == "outras"
    )
    assert not por_omissao, (
        f"[AJ4-A] rótulo(s) novo(s) caindo em 'outras' por omissão: "
        f"{por_omissao} — classe explicitamente em CATEGORIA_ESPERADA."
    )


def test_so_no_banco_nao_ganhou_emissor_sem_querer():
    """Consistência do `SO_NO_BANCO`: rótulo legadíssimo sem emissor hoje.

    Se alguém começar a gravar `Manutenção` de novo, a linha deixa de ser
    herança: migre o rótulo para `ROTULOS_SEM_LINHA` conscientemente.
    """
    esc = _escaneamento()
    com_emissor = sorted(SO_NO_BANCO & set(esc.resolvidos))
    assert not com_emissor, (
        f"[AJ4-A] {com_emissor} agora têm emissor no código "
        f"({[esc.resolvidos[r] for r in com_emissor]}) — não são mais "
        f"`SO_NO_BANCO`; mova para ROTULOS_SEM_LINHA."
    )
    assert SO_NO_BANCO <= CENSO_REAL


def test_listas_congeladas_sem_sobreposicao():
    """Invariantes das listas congeladas (anti-ioiô no próprio teste)."""
    conjuntos = (CENSO_REAL, ROTULOS_SEM_LINHA, LITERAIS_NAO_EMITIDOS)
    for i, a in enumerate(conjuntos):
        for b in conjuntos[i + 1:]:
            assert not (a & b), (
                "[AJ4-A] rótulo em duas listas congeladas ao mesmo tempo: "
                f"{sorted(a & b)}."
            )
    assert len(CENSO_REAL) == 31 and len(ROTULOS_SEM_LINHA) == 11
    assert len(LITERAIS_NAO_EMITIDOS) == 3


def test_somente_criar_alterar_sao_do_listener():
    """Os 14 `Criar X`/`Alterar X` do censo não são literais — vêm do listener.

    Se um deles aparecesse resolvido como literal no varredor, alguém estaria
    duplicando à mão o que o `before_flush` gera; se outro rótulo do censo
    ficasse sem emissor (nem literal, nem dinâmico, não é mais `SO_NO_BANCO`),
    o congelamento envelheceu.
    """
    esc = _escaneamento()
    sem_emissor_literal = sorted(
        r for r in CENSO_REAL
        if r not in esc.resolvidos and r not in SO_NO_BANCO
    )
    assert all(r.startswith(("Criar ", "Alterar ")) for r in sem_emissor_literal), (
        f"[AJ4-A] rótulo do censo sem emissor literal/constante e fora do "
        f"padrão do listener: "
        f"{[r for r in sem_emissor_literal if not r.startswith(('Criar ', 'Alterar '))]}"
    )
    do_listener = sorted(
        r for r in CONGELADOS
        if r.startswith(("Criar ", "Alterar "))
    )
    assert do_listener == sem_emissor_literal, (
        "[AJ4-A] a família Criar/Alterar mudou de natureza (literal vs. "
        "listener) — reconfira a tabela da Etapa 1."
    )
