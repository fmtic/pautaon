from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Mapping

from flask import current_app, url_for
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.database import db
from app.models import ConfiguracaoSistema


PREFIX = "informacao_padrao."
MAX_UPLOAD_BYTES = 3 * 1024 * 1024  # 3 MB

TEXT_FIELDS = {
    "nome_instituicao": "Nome da instituicao",
    "cnpj": "CNPJ",
    "endereco": "Endereco",
    "telefones": "Telefones de contato",
}

FILE_FIELDS = {
    "logo_principal_path": {"exts": {".png", ".jpg", ".jpeg", ".webp"}, "label": "Logo principal"},
    "logo_secundaria_path": {"exts": {".png", ".jpg", ".jpeg", ".webp"}, "label": "Logo secundaria"},
    "favicon_path": {"exts": {".png", ".jpg", ".jpeg", ".webp", ".ico"}, "label": "Favicon"},
    "foto_default_aluno_path": {"exts": {".png", ".jpg", ".jpeg", ".webp"}, "label": "Foto padrao do aluno"},
}

DEFAULTS = {
    "nome_instituicao": "pautaON",
    "cnpj": "",
    "endereco": "",
    "telefones": "",
    "logo_principal_path": "img/logo_textual_fundoPreto.png",
    "logo_secundaria_path": "img/logo.png",
    "favicon_path": "img/logo_resumida.png",
    "foto_default_aluno_path": "img/default.png",
}


def _cfg_key(field: str) -> str:
    return f"{PREFIX}{field}"


def _read_field(field: str) -> str:
    config = ConfiguracaoSistema.query.filter_by(chave=_cfg_key(field)).first()
    return (config.valor if config and config.valor is not None else DEFAULTS[field]).strip()


def get_informacao_padrao_values() -> dict[str, str]:
    values: dict[str, str] = {}
    for field in TEXT_FIELDS:
        values[field] = _read_field(field)
    for field in FILE_FIELDS:
        values[field] = _read_field(field)
    return values


def _make_static_url(path: str) -> str:
    return url_for("static", filename=path, _external=False)


def get_informacao_padrao_context() -> dict[str, str]:
    data = get_informacao_padrao_values()
    return {
        **data,
        "logo_principal_url": _make_static_url(data["logo_principal_path"]),
        "logo_secundaria_url": _make_static_url(data["logo_secundaria_path"]),
        "favicon_url": _make_static_url(data["favicon_path"]),
        "foto_default_aluno_url": _make_static_url(data["foto_default_aluno_path"]),
    }


def _upsert_field(field: str, value: str) -> None:
    value = (value or "").strip()
    record = ConfiguracaoSistema.query.filter_by(chave=_cfg_key(field)).first()
    if record:
        record.valor = value
        if not record.descricao:
            record.descricao = TEXT_FIELDS.get(field, FILE_FIELDS.get(field, {}).get("label", "Configuracao"))
        return

    db.session.add(
        ConfiguracaoSistema(
            chave=_cfg_key(field),
            valor=value,
            descricao=TEXT_FIELDS.get(field, FILE_FIELDS.get(field, {}).get("label", "Configuracao")),
            unidade_id=None,
        )
    )


def _validate_cnpj(cnpj_raw: str) -> None:
    if not cnpj_raw:
        return
    digits = re.sub(r"\D", "", cnpj_raw)
    if len(digits) != 14:
        raise ValueError("CNPJ invalido: use 14 digitos (com ou sem pontuacao).")


def _validate_upload_size(upload: FileStorage) -> None:
    pos = upload.stream.tell()
    upload.stream.seek(0, os.SEEK_END)
    size = upload.stream.tell()
    upload.stream.seek(pos)
    if size > MAX_UPLOAD_BYTES:
        raise ValueError(f"Arquivo excede o limite de {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")


def _save_asset(field: str, upload: FileStorage) -> str:
    rules = FILE_FIELDS[field]
    ext = Path(upload.filename or "").suffix.lower()
    if ext not in rules["exts"]:
        allowed = ", ".join(sorted(rules["exts"]))
        raise ValueError(f"{rules['label']}: formato invalido. Permitidos: {allowed}.")

    _validate_upload_size(upload)
    safe_stem = secure_filename(field.replace("_path", ""))
    filename = f"{safe_stem}_{int(time.time())}{ext}"

    uploads_dir = Path(current_app.static_folder) / "uploads" / "informacao_padrao"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    old_rel = _read_field(field)
    old_abs = Path(current_app.static_folder) / old_rel
    if old_abs.exists() and "uploads/informacao_padrao" in old_rel.replace("\\", "/"):
        try:
            old_abs.unlink()
        except OSError:
            current_app.logger.warning("Nao foi possivel remover asset anterior: %s", old_abs)

    upload_path = uploads_dir / filename
    upload.save(upload_path)
    return f"uploads/informacao_padrao/{filename}"


def upsert_informacao_padrao(form: Mapping[str, str], files: Mapping[str, FileStorage]) -> None:
    payload = {field: (form.get(field, "") or "").strip() for field in TEXT_FIELDS}
    _validate_cnpj(payload["cnpj"])

    for field, value in payload.items():
        _upsert_field(field, value)

    for field in FILE_FIELDS:
        upload = files.get(field)
        if upload and upload.filename:
            rel_path = _save_asset(field, upload)
            _upsert_field(field, rel_path)
