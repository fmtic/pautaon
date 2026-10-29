"""Modelo do certificado por centro de custo do período letivo.

Fase 1 (upload/CRUD): guarda uma imagem PNG/JPG por par
(período letivo, centro de custo) — o par é único e substituir apaga o
arquivo anterior. O uso do modelo como fundo do certificado impresso é da
fase seguinte (o texto do certificado ainda vai ser definido).

Convenções:
    - Arquivos fora do `static`, em `UPLOAD_FOLDER/certificados/<periodo_id>/`,
      servidos só por rota autenticada (`arquivo_modelo_certificado`).
    - "Centros do período" vêm do CSV `periodo_letivo.centro_custo` (nomes),
      resolvidos contra o catálogo `centro_custo` da unidade do período.
      Modelos de centros que saíram do CSV continuam listados (removíveis)
      com `no_periodo=False`.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from uuid import uuid4

from flask import current_app

from app.database import db
from app.models import CentroCusto, ModeloCertificado

#: 5 MB — limite do upload do modelo (mesma ordem de grandeza dos demais assets).
MAX_BYTES = 5 * 1024 * 1024

#: Extensão aceita -> mimetype gravado. SVG fica de fora de propósito (XSS).
EXTENSOES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


def _raiz_uploads() -> Path:
    """Diretório base de uploads (`UPLOAD_FOLDER`, padrão instance/uploads)."""
    pasta = current_app.config.get("UPLOAD_FOLDER")
    if pasta:
        return Path(pasta)
    return Path(current_app.instance_path) / "uploads"


def _pasta_modelos(periodo_letivo_id: int) -> Path:
    """Pasta do período, sempre contida na raiz de uploads (sem traversal)."""
    raiz = _raiz_uploads().resolve()
    destino = (raiz / "certificados" / str(int(periodo_letivo_id))).resolve()
    if raiz not in destino.parents and destino != raiz:
        raise ValueError("Caminho de upload inválido.")
    return destino


def _tamanho(upload) -> int:
    posicao = upload.stream.tell()
    upload.stream.seek(0, os.SEEK_END)
    tamanho = upload.stream.tell()
    upload.stream.seek(posicao)
    return tamanho


def _nomes_do_periodo(periodo) -> list[str]:
    """Nomes de centro de custo escolhidos no período (CSV), sem repetição."""
    nomes: list[str] = []
    vistos: set[str] = set()
    for bruto in (getattr(periodo, "centro_custo", None) or "").split(","):
        nome = bruto.strip()
        if not nome:
            continue
        chave = nome.casefold()
        if chave in vistos:
            continue
        vistos.add(chave)
        nomes.append(nome)
    return nomes


def modelo_de(periodo, centro) -> ModeloCertificado | None:
    """Modelo vigente do par (período, centro de custo), se houver."""
    if periodo is None or centro is None:
        return None
    return ModeloCertificado.query.filter_by(
        periodo_letivo_id=periodo.id, centro_custo_id=centro.id
    ).first()


def centros_do_periodo(periodo) -> list[dict]:
    """Centros de custo do período com o modelo vigente de cada um.

    Cada item: ``{"nome", "centro", "modelo", "no_periodo", "ativo"}``.
    ``centro`` é ``None`` quando o nome do CSV não existe no catálogo da
    unidade (não é possível enviar modelo até o cadastro ser corrigido).
    """
    if periodo is None:
        return []

    catalogo = {
        (centro.nome or "").strip(): centro
        for centro in CentroCusto.query.filter(
            CentroCusto.unidade_id == periodo.unidade_id
        ).all()
    }
    catalogo_casefold = {
        nome.casefold(): centro for nome, centro in catalogo.items()
    }
    modelos = {
        modelo.centro_custo_id: modelo
        for modelo in ModeloCertificado.query.filter_by(
            periodo_letivo_id=periodo.id
        ).all()
    }

    linhas: list[dict] = []
    vistos: set[int] = set()
    for nome in _nomes_do_periodo(periodo):
        centro = catalogo.get(nome) or catalogo_casefold.get(nome.casefold())
        if centro is None:
            linhas.append({
                "nome": nome, "centro": None, "modelo": None,
                "no_periodo": True, "ativo": None,
            })
            continue
        vistos.add(centro.id)
        linhas.append({
            "nome": centro.nome, "centro": centro,
            "modelo": modelos.get(centro.id),
            "no_periodo": True, "ativo": bool(centro.ativo),
        })

    # Modelos de centros que deixaram de compor o período: continuam visíveis
    # (nada desaparece em silêncio) e podem ser removidos.
    for centro_id, modelo in modelos.items():
        if centro_id in vistos:
            continue
        centro = modelo.centro_custo
        linhas.append({
            "nome": centro.nome if centro is not None else f"Centro #{centro_id}",
            "centro": centro,
            "modelo": modelo,
            "no_periodo": False,
            "ativo": bool(centro.ativo) if centro is not None else None,
        })

    linhas.sort(key=lambda item: (item["nome"] or "").casefold())
    return linhas


def salvar_modelo(periodo, centro, upload) -> ModeloCertificado:
    """Grava (ou substitui) o modelo do par e apaga o arquivo anterior.

    Levanta ``ValueError`` com mensagem em português para arquivo ausente,
    formato inválido, arquivo vazio ou acima de ``MAX_BYTES`` — nada é gravado
    em caso de erro.
    """
    if periodo is None or centro is None:
        raise ValueError("Centro de custo inválido para este período.")
    if upload is None or not (upload.filename or "").strip():
        raise ValueError("Selecione o arquivo do modelo (PNG ou JPG).")

    extensao = Path(upload.filename).suffix.lower()
    if extensao not in EXTENSOES:
        permitidos = ", ".join(sorted(EXTENSOES))
        raise ValueError(
            f"Formato inválido. Envie uma imagem ({permitidos})."
        )

    tamanho = _tamanho(upload)
    if tamanho <= 0:
        raise ValueError("O arquivo enviado está vazio.")
    if tamanho > MAX_BYTES:
        raise ValueError(
            f"Arquivo com {tamanho / (1024 * 1024):.1f} MB excede o limite "
            f"de {MAX_BYTES // (1024 * 1024)} MB."
        )

    pasta = _pasta_modelos(periodo.id)
    pasta.mkdir(parents=True, exist_ok=True)

    modelo = modelo_de(periodo, centro)
    arquivo_anterior = modelo.arquivo if modelo is not None else None

    novo_arquivo = (
        f"p{periodo.id}_c{centro.id}_{int(time.time())}_{uuid4().hex[:6]}{extensao}"
    )
    upload.save(str(pasta / novo_arquivo))

    if modelo is None:
        modelo = ModeloCertificado(
            periodo_letivo_id=periodo.id, centro_custo_id=centro.id,
        )
        db.session.add(modelo)
    modelo.arquivo = novo_arquivo
    modelo.nome_original = (upload.filename or "")[:255]
    modelo.tipo = EXTENSOES[extensao]
    modelo.tamanho = tamanho

    if arquivo_anterior and arquivo_anterior != novo_arquivo:
        _apagar_arquivo(pasta, arquivo_anterior)
    # Auto-reparo: sobras de substituições anteriores (ex.: arquivo em uso no
    # Windows no momento da troca) saem na próxima gravação do mesmo par.
    _limpar_orfaos(pasta, periodo.id, centro.id, manter=novo_arquivo)

    return modelo


def remover_modelo(periodo, centro) -> bool:
    """Apaga o modelo do par (linha + arquivo). ``False`` se não havia modelo."""
    modelo = modelo_de(periodo, centro)
    if modelo is None:
        return False
    try:
        _apagar_arquivo(_pasta_modelos(periodo.id), modelo.arquivo)
    except ValueError:
        current_app.logger.warning(
            "Modelo de certificado com caminho inválido: %s", modelo.arquivo
        )
    db.session.delete(modelo)
    try:
        _limpar_orfaos(_pasta_modelos(periodo.id), periodo.id, centro.id)
    except ValueError:
        pass
    return True


def caminho_modelo(modelo) -> Path | None:
    """Caminho absoluto do arquivo do modelo (``None`` se fora da raiz)."""
    if modelo is None or not modelo.arquivo:
        return None
    try:
        caminho = _pasta_modelos(modelo.periodo_letivo_id) / modelo.arquivo
    except ValueError:
        return None
    return caminho if caminho.is_file() else None


def _limpar_orfaos(
    pasta: Path, periodo_letivo_id: int, centro_custo_id: int,
    manter: str | None = None,
) -> None:
    """Apaga arquivos do par que não são o modelo vigente (auto-reparo)."""
    if not pasta.is_dir():
        return
    prefixo = f"p{int(periodo_letivo_id)}_c{int(centro_custo_id)}_"
    for caminho in pasta.glob(f"{prefixo}*"):
        if manter and caminho.name == manter:
            continue
        _apagar_arquivo(pasta, caminho.name)


def _apagar_arquivo(pasta: Path, nome_arquivo: str) -> None:
    """Remove o arquivo do modelo, ignorando ausência e falhas de I/O."""
    if not nome_arquivo:
        return
    caminho = (pasta / os.path.basename(nome_arquivo))
    try:
        if caminho.is_file():
            caminho.unlink()
    except OSError:
        current_app.logger.warning("Não foi possível apagar %s", caminho)
