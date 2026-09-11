import sys
import os

# Ensure project root is on sys.path so `import app` works when running from scripts/
proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, proj_root)

from app import create_app

app = create_app()

with app.app_context():
    from app.utils.errors import log_error_code

    try:
        raise RuntimeError("Synthetic test error for logging code generation")
    except Exception as e:
        code = log_error_code(e, location='scripts.synthetic_test', hint='unknown')
        print('Generated code:', code)
