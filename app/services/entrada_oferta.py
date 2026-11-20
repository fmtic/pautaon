"""AJ18-B — fonte única de data de entrada do aluno na oferta.

Fornece:
- vigencia_efetiva(oferta): (inicio, fim) herdando da turma quando NULL.
- data_entrada_efetiva(inscricao): piso de frequência (NULL = desde o início).
- aula_conta_para_aluno(inscricao, data): corte por data de entrada.
- datas_esperadas_do_aluno(inscricao, oferta, ...): calendário cortado.
- parse_escolha_entrada(valor, oferta, hoje): interpreta "hoje"/"inicio"/YYYY-MM-DD.
- validar_entrada_na_vigencia(entrada, oferta): valida janela D2.
- alterar_entrada(inscricao, escolha, hoje, ...): corrige a data de entrada sem
  desenturmar (AJ18-E) e, opcionalmente, remove as frequências anteriores
  (AJ18-F), exigindo confirmação quando elas são mantidas.
"""
from __future__ import annotations

from datetime import date
from typing import NamedTuple

from app.services.turma_curso import datas_aula_oferta


class EntradaComLinhasAnteriores(ValueError):
    """A nova entrada deixaria frequências já gravadas antes do piso do aluno.

    Carrega a ``quantidade`` e o intervalo (``data_min``/``data_max``) para o
    chamador avisar o usuário e só prosseguir com confirmação explícita.
    Nenhuma linha é apagada ou alterada neste caminho (D4).
    """

    def __init__(
        self,
        quantidade: int,
        data_min: date | None = None,
        data_max: date | None = None,
    ):
        self.quantidade = quantidade
        self.data_min = data_min
        self.data_max = data_max
        super().__init__(
            f"Existem {quantidade} frequência(s) deste aluno nesta oferta em "
            "datas anteriores à nova entrada. Confirme a alteração para "
            "mantê-las ou escolha removê-las."
        )


class ResultadoAlteracaoEntrada(NamedTuple):
    """Resultado de ``alterar_entrada`` (AJ18-E/AJ18-F)."""

    anterior: date | None
    nova: date | None
    removidas: int = 0
    removidas_ini: date | None = None
    removidas_fim: date | None = None
    anteriores: int = 0
    anteriores_ini: date | None = None
    anteriores_fim: date | None = None


def vigencia_efetiva(oferta) -> tuple[date | None, date | None]:
    """Início e fim efetivos da oferta, herdando NULLs da turma."""
    inicio = oferta.data_inicio
    fim = oferta.data_fim
    turma = getattr(oferta, "turma", None)
    if inicio is None and turma is not None:
        inicio = turma.data_inicio
    if fim is None and turma is not None:
        fim = turma.data_fim
    return inicio, fim


def inicio_efetivo(oferta) -> date | None:
    return vigencia_efetiva(oferta)[0]


def fim_efetivo(oferta) -> date | None:
    return vigencia_efetiva(oferta)[1]


def data_entrada_efetiva(inscricao) -> date | None:
    """Piso de frequência do aluno na oferta. None = sem corte (desde o início)."""
    return getattr(inscricao, "data_entrada_oferta", None)


def aula_conta_para_aluno(inscricao, data: date) -> bool:
    """A aula `data` entra nas contabilidades do aluno nesta inscrição?"""
    entrada = data_entrada_efetiva(inscricao)
    return entrada is None or data >= entrada


def datas_esperadas_do_aluno(inscricao, oferta, *, limite=None, blocked=None) -> list[date]:
    """Calendário da oferta cortado no piso do aluno (para denominadores)."""
    datas = datas_aula_oferta(oferta, limite=limite, blocked=blocked)
    entrada = data_entrada_efetiva(inscricao)
    if entrada is None:
        return datas
    return [d for d in datas if d >= entrada]


def parse_escolha_entrada(valor, oferta, hoje: date):
    """Converte valor do formulário em (data_entrada_oferta, rotulo_log).

    Aceita: "inicio"/"desde_inicio" -> (None, "desde o início"),
            "hoje" -> (hoje, "hoje"),
            "YYYY-MM-DD" -> (date, "YYYY-MM-DD").
    Levanta ValueError com mensagem clara em caso inválido.
    """
    if valor is None:
        raise ValueError("Selecione a data de entrada do aluno na oferta.")
    valor = str(valor).strip()
    if valor in ("inicio", "desde_inicio"):
        return None, "desde o início"
    if valor == "hoje":
        return validar_entrada_na_vigencia(hoje, oferta, rotulo="hoje")
    try:
        entrada = date.fromisoformat(valor)
    except Exception as exc:
        raise ValueError("Data de entrada inválida.") from exc
    return validar_entrada_na_vigencia(entrada, oferta)


def validar_entrada_na_vigencia(entrada: date, oferta, rotulo: str | None = None):
    """Valida D2: entrada dentro de [início efetivo, fim efetivo] da oferta.

    Retorna (entrada, rotulo_log). Levanta ValueError se fora da janela ou se
    a vigência efetiva não estiver definida.
    """
    ini, fim = vigencia_efetiva(oferta)
    if ini is None or fim is None:
        raise ValueError(
            "A oferta não possui vigência definida para validar a data de entrada."
        )
    if entrada < ini or entrada > fim:
        raise ValueError(
            f"A data de entrada ({entrada.strftime('%d/%m/%Y')}) deve estar entre "
            f"{ini.strftime('%d/%m/%Y')} e {fim.strftime('%d/%m/%Y')}."
        )
    if rotulo is None:
        rotulo = entrada.isoformat()
    return entrada, rotulo


def _condicoes_frequencias_anteriores(inscricao, entrada: date):
    """Filtros SQL das frequências do aluno anteriores a ``entrada``.

    Usa a MESMA resolução de oferta/legado D2 dos leitores: quando a oferta é a
    única ativa da turma, linhas com ``turma_curso_id`` NULL também contam como
    dela (``ofertas_unicas_ativas``). A remoção (AJ18-F) usa exatamente estas
    condições, então nunca alcança outra oferta nem outro aluno.
    """
    from sqlalchemy import and_, or_

    from app.models import Frequencia
    from app.services.frequencia_oferta import ofertas_unicas_ativas

    oferta = getattr(inscricao, "turma_curso", None)
    if oferta is None:
        return None

    escopo = [Frequencia.turma_curso_id == oferta.id]
    if oferta.id in ofertas_unicas_ativas([oferta.id]):
        escopo = [
            or_(
                Frequencia.turma_curso_id == oferta.id,
                and_(
                    Frequencia.turma_curso_id.is_(None),
                    Frequencia.turma_id == inscricao.turma_id,
                ),
            )
        ]

    return [
        Frequencia.aluno_id == inscricao.aluno_id,
        Frequencia.data < entrada,
        Frequencia.conceito.isnot(None),
        *escopo,
    ]


def resumo_frequencias_anteriores(inscricao, entrada: date):
    """``(quantidade, data_min, data_max)`` das frequências anteriores.

    Uma única consulta agregada; ``(0, None, None)`` quando não há oferta ou
    linhas. Somente leitura — nenhuma linha é apagada ou alterada.
    """
    from sqlalchemy import func

    from app.models import Frequencia

    condicoes = _condicoes_frequencias_anteriores(inscricao, entrada)
    if not condicoes:
        return 0, None, None

    quantidade, data_min, data_max = (
        Frequencia.query.with_entities(
            func.count(Frequencia.id),
            func.min(Frequencia.data),
            func.max(Frequencia.data),
        )
        .filter(*condicoes)
        .one()
    )
    return int(quantidade or 0), data_min, data_max


def contar_frequencias_anteriores(inscricao, entrada: date) -> int:
    """Quantas frequências do aluno na oferta têm data anterior a ``entrada``."""
    return resumo_frequencias_anteriores(inscricao, entrada)[0]


def _remover_frequencias_anteriores(inscricao, entrada: date) -> int:
    """Remove as frequências anteriores do aluno na oferta (AJ18-F).

    NÃO commita: a remoção entra na mesma transação da alteração da data.
    Devolve a quantidade efetivamente removida.
    """
    from app.models import Frequencia

    condicoes = _condicoes_frequencias_anteriores(inscricao, entrada)
    if not condicoes:
        return 0
    return Frequencia.query.filter(*condicoes).delete(synchronize_session=False)


def alterar_entrada(
    inscricao,
    escolha,
    hoje: date,
    *,
    confirmar: bool = False,
    remover_anteriores: bool = False,
) -> ResultadoAlteracaoEntrada:
    """Corrige ``data_entrada_oferta`` de uma inscrição já existente. NÃO commita.

    Reutiliza exatamente a interpretação e a validação do enturmar
    (``parse_escolha_entrada``/``validar_entrada_na_vigencia`` e a vigência
    efetiva da oferta).

    Regras:
        - ``"inicio"`` grava NULL (desde o início);
        - oferta ainda não iniciada só aceita NULL — data específica
          (inclusive "hoje") é recusada, como no enturmar;
        - escolha igual ao valor atual é no-op (não altera, não gera log);
        - avançar a data (ou sair de NULL) com frequências já gravadas antes da
          nova entrada exige ``confirmar=True``; sem isso levanta
          ``EntradaComLinhasAnteriores`` com quantidade e intervalo;
        - ``remover_anteriores=True`` remove essas frequências na MESMA
          transação (mesma oferta/aluno, ``data < nova``) e dispensa a
          confirmação. Só vale no avanço com linhas anteriores; nos demais
          casos é ignorado sem erro;
        - mover a data para trás ou para NULL nunca exige confirmação.
    """
    oferta = getattr(inscricao, "turma_curso", None)
    if oferta is None:
        raise ValueError("A inscrição não está vinculada a uma oferta.")

    anterior = data_entrada_efetiva(inscricao)
    valor = "" if escolha is None else str(escolha).strip()

    if valor in ("inicio", "desde_inicio"):
        nova = None
    else:
        inicio, _fim = vigencia_efetiva(oferta)
        if inicio is not None and hoje < inicio:
            raise ValueError(
                "A oferta ainda não iniciou: só é possível registrar "
                '"Desde o início".'
            )
        nova, _rotulo = parse_escolha_entrada(valor, oferta, hoje)

    if nova == anterior:
        return ResultadoAlteracaoEntrada(anterior, nova)

    avanca = nova is not None and (anterior is None or nova > anterior)
    anteriores = 0
    anteriores_ini = None
    anteriores_fim = None
    removidas = 0
    removidas_ini = None
    removidas_fim = None

    if avanca:
        anteriores, anteriores_ini, anteriores_fim = (
            resumo_frequencias_anteriores(inscricao, nova)
        )

    if avanca and anteriores:
        if remover_anteriores:
            if getattr(oferta, "conselho_concluido", False):
                raise ValueError(
                    "Não é possível remover frequências anteriores: "
                    "o conselho desta oferta já foi concluído. "
                    "Mantenha as frequências para avançar a entrada."
                )
            removidas = _remover_frequencias_anteriores(inscricao, nova)
            removidas_ini, removidas_fim = anteriores_ini, anteriores_fim
        elif not confirmar:
            raise EntradaComLinhasAnteriores(
                anteriores, anteriores_ini, anteriores_fim
            )

    inscricao.data_entrada_oferta = nova
    return ResultadoAlteracaoEntrada(
        anterior,
        nova,
        removidas,
        removidas_ini,
        removidas_fim,
        anteriores,
        anteriores_ini,
        anteriores_fim,
    )
