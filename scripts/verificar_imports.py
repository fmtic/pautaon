import importlib
import pkgutil
import sys
from pathlib import Path

# Permite executar tanto `python scripts/verificar_imports.py` quanto
# `python -m scripts.verificar_imports`: o diretório raiz precisa entrar no
# sys.path quando o arquivo é chamado diretamente.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app  # noqa: E402

falhas = 0
for m in pkgutil.walk_packages(app.__path__, "app."):
    try:
        importlib.import_module(m.name)
    except Exception as e:
        falhas += 1
        print(f"FALHOU {m.name}: {type(e).__name__}: {e}")

print("tudo importa" if not falhas else f"{falhas} módulo(s) com erro")
raise SystemExit(1 if falhas else 0)
