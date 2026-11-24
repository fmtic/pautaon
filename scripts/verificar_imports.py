import importlib
import pkgutil

import app

falhas = 0
for m in pkgutil.walk_packages(app.__path__, "app."):
    try:
        importlib.import_module(m.name)
    except Exception as e:
        falhas += 1
        print(f"FALHOU {m.name}: {type(e).__name__}: {e}")

print("tudo importa" if not falhas else f"{falhas} módulo(s) com erro")
raise SystemExit(1 if falhas else 0)