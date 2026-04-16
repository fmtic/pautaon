from __future__ import annotations

import argparse
import logging
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List

from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

from app import create_app
from app.models import Aluno, DiaBloqueado, Frequencia, Inscricao, Turma, User
from app.utils.logica import gerar_datas


LOGGER = logging.getLogger("notificador_pauta")
VALID_CONCEITOS = ("A", "B", "C", "D", "F", "J")


@dataclass
class ProfessorPendencia:
    nome: str
    email: str
    aulas_pendentes: int = 0
    lancamentos_faltantes: int = 0
    turmas: set[str] | None = None

    def __post_init__(self) -> None:
        if self.turmas is None:
            self.turmas = set()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Notifica professores com pauta de frequencia pendente quando "
            "data_da_aula + N dias for atingida."
        )
    )
    parser.add_argument("--dry-run", action="store_true", help="Nao envia mensagens, apenas simula.")
    parser.add_argument("--days-delay", type=int, default=None, help="Dias de atraso para notificar.")
    parser.add_argument(
        "--log-level",
        default=os.getenv("NOTIFICADOR_LOG_LEVEL", "INFO"),
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
    )
    return parser.parse_args()


def as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def mask_email(email: str) -> str:
    if "@" not in email:
        return "***"
    user, domain = email.split("@", 1)
    if len(user) <= 2:
        return f"{user[0]}***@{domain}" if user else f"***@{domain}"
    return f"{user[:2]}***@{domain}"


def load_scopes() -> List[str]:
    scopes_raw = os.getenv(
        "GOOGLE_CHAT_SCOPES",
        "https://www.googleapis.com/auth/chat.messages.create,https://www.googleapis.com/auth/chat.spaces",
    )
    scopes = [item.strip() for item in scopes_raw.split(",") if item.strip()]
    if not scopes:
        raise ValueError("GOOGLE_CHAT_SCOPES vazio.")
    return scopes


def build_chat_service():
    key_file = os.getenv("GOOGLE_CHAT_SERVICE_ACCOUNT_FILE") or os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
    if not key_file:
        raise ValueError("Defina GOOGLE_CHAT_SERVICE_ACCOUNT_FILE ou GOOGLE_SERVICE_ACCOUNT_FILE.")
    if not os.path.exists(key_file):
        raise FileNotFoundError(f"Arquivo de credencial nao encontrado: {key_file}")

    creds = service_account.Credentials.from_service_account_file(key_file, scopes=load_scopes())
    return build("chat", "v1", credentials=creds)


def get_blocked_dates_for_turma(turma: Turma) -> set[str]:
    if not turma.periodo_letivo_id:
        return set()
    dias = DiaBloqueado.query.filter_by(periodo_letivo_id=turma.periodo_letivo_id).all()
    return {d.data.strftime("%Y-%m-%d") for d in dias}


def get_aluno_ids_ativos(turma_id: int) -> List[int]:
    rows = (
        Aluno.query.join(Inscricao)
        .filter(
            Inscricao.turma_id == turma_id,
            Inscricao.ativo == True,  # noqa: E712
            Aluno.ativo == True,  # noqa: E712
        )
        .all()
    )
    return [aluno.id for aluno in rows]


def faltantes_no_dia(turma_id: int, data_aula: str, aluno_ids: List[int]) -> int:
    if not aluno_ids:
        return 0
    lancados = (
        Frequencia.query.filter(
            Frequencia.turma_id == turma_id,
            Frequencia.data == data_aula,
            Frequencia.aluno_id.in_(aluno_ids),
            Frequencia.conceito.isnot(None),
            Frequencia.conceito != "",
            Frequencia.conceito.in_(VALID_CONCEITOS),
        ).count()
    )
    return max(len(aluno_ids) - lancados, 0)


def coletar_pendencias(days_delay: int, hoje: date) -> Dict[str, ProfessorPendencia]:
    pendencias: Dict[str, ProfessorPendencia] = {}
    turmas = (
        Turma.query.join(User, Turma.professor_id == User.id)
        .filter(
            Turma.ativo == True,  # noqa: E712
            Turma.professor_id.isnot(None),
            User.role == "professor",
            User.is_active == True,  # noqa: E712
        )
        .all()
    )
    LOGGER.info("Turmas elegiveis para analise: %d", len(turmas))

    for turma in turmas:
        fim_turma = parse_date(turma.data_fim)
        if fim_turma is None:
            LOGGER.warning("Turma %s ignorada por data_fim invalida.", turma.id)
            continue
        if hoje > fim_turma:
            # A turma encerrou: nao notificar fora da janela de vigencia.
            continue

        blocked_dates = get_blocked_dates_for_turma(turma)
        datas_aula = gerar_datas(turma, incluir_futuro=False, blocked_dates=blocked_dates)
        if not datas_aula:
            continue

        aluno_ids = get_aluno_ids_ativos(turma.id)
        if not aluno_ids:
            continue

        for data_aula_str in datas_aula:
            data_aula = parse_date(data_aula_str)
            if data_aula is None:
                continue

            data_notificacao = data_aula + timedelta(days=days_delay)
            if hoje < data_notificacao:
                continue

            faltantes = faltantes_no_dia(turma.id, data_aula_str, aluno_ids)
            if faltantes <= 0:
                continue

            professor = turma.professor
            if not professor or not professor.email:
                continue

            item = pendencias.get(professor.email)
            if item is None:
                item = ProfessorPendencia(nome=professor.name, email=professor.email)
                pendencias[professor.email] = item

            item.aulas_pendentes += 1
            item.lancamentos_faltantes += faltantes
            item.turmas.add(turma.nome)

    return pendencias


def montar_mensagem(prof: ProfessorPendencia, days_delay: int) -> str:
    qtd_turmas = len(prof.turmas or [])
    turmas = ", ".join(sorted(prof.turmas or []))
    return (
        f"Ola {prof.nome}, identificamos pendencias de frequencia no PautaON.\n\n"
        f"- Aulas pendentes: {prof.aulas_pendentes}\n"
        f"- Lancamentos faltantes (alunos/dias): {prof.lancamentos_faltantes}\n"
        f"- Turmas impactadas: {qtd_turmas} ({turmas})\n"
        f"- Regra aplicada: data da aula + {days_delay} dias\n\n"
        "Por favor, regularize os lancamentos de frequencia."
    )


def resolve_dm_space(service, email: str) -> str | None:
    user_resource = f"users/{email}"
    try:
        resp = service.spaces().findDirectMessage(name=user_resource).execute()
        return resp.get("name")
    except Exception:
        LOGGER.exception("Falha ao resolver DM para %s", mask_email(email))
        return None


def enviar_notificacoes(service, pendencias: Dict[str, ProfessorPendencia], days_delay: int, dry_run: bool) -> int:
    enviados = 0
    for email, prof in pendencias.items():
        mensagem = montar_mensagem(prof, days_delay)
        if dry_run:
            LOGGER.info(
                "[DRY-RUN] Notificacao para %s | aulas=%d | faltantes=%d",
                mask_email(email),
                prof.aulas_pendentes,
                prof.lancamentos_faltantes,
            )
            continue

        dm_space = resolve_dm_space(service, email)
        if not dm_space:
            continue

        try:
            service.spaces().messages().create(parent=dm_space, body={"text": mensagem}).execute()
            enviados += 1
            LOGGER.info("Mensagem enviada para %s", mask_email(email))
        except Exception:
            LOGGER.exception("Falha ao enviar mensagem para %s", mask_email(email))
    return enviados


def main() -> int:
    load_dotenv()
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    days_delay = args.days_delay
    if days_delay is None:
        days_delay = int(os.getenv("NOTIFICADOR_DIAS_ATRASO", "7"))
    if days_delay < 0:
        raise ValueError("NOTIFICADOR_DIAS_ATRASO nao pode ser negativo.")

    dry_run = args.dry_run or as_bool(os.getenv("NOTIFICADOR_DRY_RUN"), default=False)
    LOGGER.info("Iniciando notificador | days_delay=%d | dry_run=%s", days_delay, dry_run)

    app = create_app()
    with app.app_context():
        pendencias = coletar_pendencias(days_delay=days_delay, hoje=date.today())
        LOGGER.info("Professores com pendencias: %d", len(pendencias))
        if not pendencias:
            return 0

        service = None if dry_run else build_chat_service()
        enviados = enviar_notificacoes(service, pendencias, days_delay, dry_run)
        LOGGER.info("Execucao finalizada | mensagens_enviadas=%d", enviados)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())