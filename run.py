import sys

from app import create_app
from app.utils.execucao import escolher_bind_dev

app = create_app()

if __name__ == "__main__":
    try:
        host, porta, debug = escolher_bind_dev(app.config)
    except RuntimeError as erro:
        print(erro, file=sys.stderr)
        raise SystemExit(1)
    app.run(host=host, port=porta, debug=debug)
