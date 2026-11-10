"""AJ18-B — fonte única de data de entrada do aluno na oferta.

Fornece:
- vigencia_efetiva(oferta): (inicio, fim) herdando da turma quando NULL.
- data_entrada_efetiva(inscricao): piso de frequência (NULL = desde o início).
- aula_conta_para_aluno(inscricao, data): corte por data de entrada.
- datas_esperadas_do_aluno(inscricao, oferta, ...): calendário cortado.
- parse_escolha_entrada(valor, oferta, hoje): interpreta "hoje"/"inicio"/YYYY-MM-DD.
- validar_entrada_na_vigencia(entrada, oferta): valida janela D2.
"""
from __future__ import annotations

from datetime import date

from app.services.turma_curso import datas_aula_oferta


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
