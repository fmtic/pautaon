"""Validação das fotos de aluno (S1-08).

O upload aceitava qualquer arquivo: bastava enviar `foto.html` (ou um SVG com
JavaScript dentro) e o arquivo era gravado em `uploads/fotos` e servido por
`/aluno/<id>/foto`. Aqui ficam as regras únicas usadas na gravação
(`registros.shared.salvar_foto`) e na entrega (`registros.alunos.foto_aluno`):

- extensão na whitelist (`jpg`, `jpeg`, `png`, `webp`);
- conteúdo conferido pela **assinatura de bytes** — o Pillow não faz parte do
  `requirements.txt`; quando estiver instalado, ele também abre e valida a
  imagem;
- no máximo 2 MB;
- nome gerado pelo servidor (`aluno_<id>_<uuid>.<ext>`), sem nada do cliente;
- mimetype fixo pela extensão validada na hora de servir, com `nosniff`.
"""

from __future__ import annotations

import os
import uuid

#: Limite de tamanho aceito para a foto (2 MB).
FOTO_MAX_BYTES = 2 * 1024 * 1024

#: Extensões aceitas no nome enviado.
EXTENSOES_PERMITIDAS = frozenset({"jpg", "jpeg", "png", "webp"})

#: Mimetype servido por extensão (nunca o que o navegador declarou).
MIME_POR_EXTENSAO = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
}

#: Usado quando o arquivo antigo tem extensão fora da whitelist.
MIME_DESCONHECIDO = "application/octet-stream"

MSG_EXTENSAO = "Foto não enviada: use um arquivo JPG, JPEG, PNG ou WEBP."
MSG_VAZIA = "Foto não enviada: o arquivo está vazio."
MSG_TAMANHO = "Foto não enviada: o arquivo tem mais de 2 MB."
MSG_CONTEUDO = "Foto não enviada: o conteúdo do arquivo não é uma imagem válida."


def extensao_de(nome: str | None) -> str:
    """Extensão em minúsculas, sem o ponto (`""` quando não há)."""
    _, ext = os.path.splitext(nome or "")
    return ext.lower().lstrip(".")


def tipo_por_assinatura(cabecalho: bytes) -> str | None:
    """Tipo da imagem pelas primeiras bytes: `png`, `jpg`, `webp` ou `None`.

    Assinaturas: PNG `\\x89PNG\\r\\n\\x1a\\n`; JPEG `\\xff\\xd8\\xff`; WEBP
    `RIFF....WEBP`. Qualquer outra coisa (HTML, SVG, PDF, GIF) não é foto.
    """
    if cabecalho.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if cabecalho.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if len(cabecalho) >= 12 and cabecalho[:4] == b"RIFF" and cabecalho[8:12] == b"WEBP":
        return "webp"
    return None


#: Limite de megapixels aceito (bomba de descompressão).
FOTO_MAX_MEGAPIXELS = 25

def _verificar_com_pillow(stream) -> bool | None:
    """`True`/`False` quando o Pillow está instalado; `None` quando não está."""
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        with Image.open(stream) as imagem:
            imagem.verify()
            stream.seek(0)
            with Image.open(stream) as imagem2:
                if imagem2.width * imagem2.height > FOTO_MAX_MEGAPIXELS * 1_000_000:
                    return False
        return True
    except Exception:
        return False
    finally:
        stream.seek(0)


def validar_foto(foto) -> tuple[str | None, str | None]:
    """Valida a foto e devolve `(mensagem_de_erro, extensão_gravada)`.

    A extensão gravada vem do **conteúdo** (`jpg`, `png` ou `webp`), não do que
    o cliente digitou. Nada é gravado aqui.
    """
    extensao = extensao_de(getattr(foto, "filename", ""))
    if extensao not in EXTENSOES_PERMITIDAS:
        return MSG_EXTENSAO, None

    stream = foto.stream
    stream.seek(0, os.SEEK_END)
    tamanho = stream.tell()
    stream.seek(0)
    if tamanho == 0:
        return MSG_VAZIA, None
    if tamanho > FOTO_MAX_BYTES:
        return MSG_TAMANHO, None

    tipo = tipo_por_assinatura(stream.read(32))
    stream.seek(0)
    if tipo is None:
        return MSG_CONTEUDO, None

    if _verificar_com_pillow(stream) is False:
        return MSG_CONTEUDO, None

    return None, tipo


def nome_foto_aluno(aluno_id: int, extensao: str) -> str:
    """Nome gerado pelo servidor: `aluno_<id>_<uuid>.<ext>`."""
    return f"aluno_{aluno_id}_{uuid.uuid4().hex}.{extensao}"


def mimetype_da_foto(nome_arquivo: str) -> str:
    """Mimetype fixo pela extensão do arquivo em disco."""
    return MIME_POR_EXTENSAO.get(extensao_de(nome_arquivo), MIME_DESCONHECIDO)
