"""
Script de migração para SEC-01:
Move com segurança todos os arquivos de documentos, laudos e fotos
de 'app/static/uploads' para 'instance/uploads', fechando o acesso
público estático a arquivos confidenciais.

Mantém 'app/static/uploads/informacao_padrao' intacto (logos institucionais públicos).
"""

from pathlib import Path
import shutil
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_UPLOADS = BASE_DIR / "app" / "static" / "uploads"
INSTANCE_UPLOADS = BASE_DIR / "instance" / "uploads"


def migrar_diretorio(subpasta: str) -> tuple[int, int]:
    origem = STATIC_UPLOADS / subpasta
    destino = INSTANCE_UPLOADS / subpasta

    if not origem.exists():
        print(f"[INFO] Pasta de origem não existe: {origem}")
        return 0, 0

    destino.mkdir(parents=True, exist_ok=True)
    total_arquivos = 0
    erros = 0

    for item in origem.rglob("*"):
        if item.is_file():
            rel_path = item.relative_to(origem)
            target_file = destino / rel_path
            target_file.parent.mkdir(parents=True, exist_ok=True)

            try:
                shutil.copy2(item, target_file)
                # Verifica integridade básica por tamanho
                if target_file.stat().st_size == item.stat().st_size:
                    item.unlink()
                    total_arquivos += 1
                    print(f"  [OK] Movido: {rel_path}")
                else:
                    print(f"  [ERRO] Tamanho divergente ao copiar: {rel_path}")
                    erros += 1
            except Exception as e:
                print(f"  [FALHA] Não foi possível mover {rel_path}: {e}")
                erros += 1

    # Remove subdiretórios vazios que restaram na origem
    for dirpath in sorted(origem.glob("**/*"), reverse=True):
        if dirpath.is_dir():
            try:
                dirpath.rmdir()
            except OSError:
                pass

    try:
        origem.rmdir()
        print(f"[OK] Diretório público de origem removido com sucesso: {origem}")
    except OSError:
        pass

    return total_arquivos, erros


def main() -> int:
    print("=" * 60)
    print("Iniciando migração de uploads sensíveis para instance/uploads")
    print("=" * 60)

    total_docs, erros_docs = migrar_diretorio("documentos")
    total_fotos, erros_fotos = migrar_diretorio("fotos")

    print("\n" + "=" * 60)
    print(f"Resultado da migração:")
    print(f"  - Documentos / Laudos / Anexos movidos: {total_docs} (erros: {erros_docs})")
    print(f"  - Fotos de Alunos movidas: {total_fotos} (erros: {erros_fotos})")
    print(f"  - Destino seguro: {INSTANCE_UPLOADS}")
    print("=" * 60)

    if erros_docs > 0 or erros_fotos > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
