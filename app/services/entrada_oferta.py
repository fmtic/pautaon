"""AJ18-B — fonte única de data de entrada do aluno na oferta.

Fornece:
- vigencia_efetiva(oferta): (inicio, fim) herdando da turma quando NULL.
- data_entrada_efetiva(inscricao): piso de frequência (NULL = desde o início).
- aula_conta_para_aluno(inscricao, data): corte por data de entrada.
- datas_esperadas_do_aluno(inscricao, oferta, ...): calendário cortado.
- parse_escolha_entrada(valor, oferta, hoje): interpreta "hoje"/"inicio"/YYYY-MM-DD.
- validar_entrada_na_vigencia(entrada, oferta): valida janela D2.
- alterar_entrada(inscricao, escolha, hoje): corrige a data de entrada sem
  desenturmar (AJ18-E), exigindo confirmação quando há frequência anterior.
"""
from __future__ import annotations

from datetime import date

from app.services.turma_curso import datas_aula_oferta


class EntradaComLinhasAnteriores(ValueError):
    """A nova entrada deixaria frequências já gravadas antes do piso do aluno.

    Carrega a ``quantidade`` de linhas para o chamador avisar o usuário e só
    prosseguir com confirmação explícita. Nenhuma linha é apagada ou alterada
    (D4).
    """

    def __init__(self, quantidade: int):
        self.quantidade = quantidade
        super().__init__(
            f"Existem {quantidade} frequência(s) deste aluno nesta oferta em "
            "datas anteriores à nova entrada. Confirme a alteração para "
            "mantê-las."
        )


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


def contar_frequencias_anteriores(inscricao, entrada: date) -> int:
    """Quantas frequências do aluno na oferta têm data anterior a ``entrada``.

    Usa a MESMA resolução de oferta/legado D2 dos leitores: quando a oferta é a
    única ativa da turma, linhas com ``turma_curso_id`` NULL também contam como
    dela (``ofertas_unicas_ativas``). Somente leitura — nenhuma linha é apagada
    ou alterada (D4).
    """
    from sqlalchemy import and_, or_

    from app.models import Frequencia
    from app.services.frequencia_oferta import ofertas_unicas_ativas

    oferta = getattr(inscricao, "turma_curso", None)
    if oferta is None:
        return 0

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

    return (
        Frequencia.query.filter(
            Frequencia.aluno_id == inscricao.aluno_id,
            Frequencia.data < entrada,
            Frequencia.conceito.isnot(None),
            *escopo,
        ).count()
    )


def alterar_entrada(inscricao, escolha, hoje: date, *, confirmar: bool = False):
    """Corrige ``data_entrada_oferta`` de uma inscrição já existente. NÃO commita.

    Reutiliza exatamente a interpretação e a validação do enturmar
    (``parse_escolha_entrada``/``validar_entrada_na_vigencia`` e a vigência
    efetiva da oferta). Devolve ``(anterior, nova)``.

    Regras:
        - ``"inicio"`` grava NULL (desde o início);
        - oferta ainda não iniciada só aceita NULL — data específica
          (inclusive "hoje") é recusada, como no enturmar;
        - escolha igual ao valor atual é no-op (não altera, não gera log);
        - avançar a data (ou sair de NULL) com frequências já gravadas antes da
          nova entrada exige ``confirmar=True``; sem isso levanta
          ``EntradaComLinhasAnteriores`` com a quantidade. As linhas não são
          apagadas nem alteradas (D4);
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
        return anterior, nova

    avanca = nova is not None and (anterior is None or nova > anterior)
    if avanca and not confirmar:
        quantidade = contar_frequencias_anteriores(inscricao, nova)
        if quantidade:
            raise EntradaComLinhasAnteriores(quantidade)

    inscricao.data_entrada_oferta = nova
    return anterior, nova
