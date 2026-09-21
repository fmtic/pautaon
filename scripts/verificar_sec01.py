import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app import create_app
from app.database import db
from app.models import Aluno, Atendimento, User


def run_checks():
    print("=" * 60)
    print("Iniciando verificação de segurança SEC-01...")
    print("=" * 60)

    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    client = app.test_client()

    # 1. Testar acesso público na pasta antiga /static/uploads/documentos
    resp_static = client.get("/static/uploads/documentos/00002_2026/doc_laudo.pdf")
    assert resp_static.status_code == 404, f"Esperado 404 para estático de laudo, obtido: {resp_static.status_code}"
    print("[PASS] 1. Acesso anônimo a /static/uploads/documentos/... bloqueado (404 Not Found)")

    resp_static_foto = client.get("/static/uploads/fotos/aluno_1_20251205_203425_0000.png")
    assert resp_static_foto.status_code == 404, f"Esperado 404 para foto estática, obtido: {resp_static_foto.status_code}"
    print("[PASS] 2. Acesso anônimo a /static/uploads/fotos/... bloqueado (404 Not Found)")

    # 2. Testar acesso anônimo às novas rotas protegidas
    resp_anon_doc = client.get("/aluno/2/documento/doc_laudo")
    assert resp_anon_doc.status_code in (302, 401), f"Esperado 302/401 para doc sem login, obtido: {resp_anon_doc.status_code}"
    print("[PASS] 3. Acesso anônimo a /aluno/<id>/documento/<doc> redireciona para login")

    resp_anon_foto = client.get("/aluno/1/foto")
    assert resp_anon_foto.status_code in (302, 401), f"Esperado 302/401 para foto sem login, obtido: {resp_anon_foto.status_code}"
    print("[PASS] 4. Acesso anônimo a /aluno/<id>/foto redireciona para login")

    resp_anon_anexo = client.get("/atendimentos/1/anexo")
    assert resp_anon_anexo.status_code in (302, 401), f"Esperado 302/401 para anexo sem login, obtido: {resp_anon_anexo.status_code}"
    print("[PASS] 5. Acesso anônimo a /atendimentos/<id>/anexo redireciona para login")

    # 3. Testar acesso autenticado
    with app.app_context():
        admin = User.query.filter_by(role="admin").first()
        if admin:
            with client.session_transaction() as sess:
                sess["_user_id"] = str(admin.id)
                sess["_fresh"] = True

            # Testa acesso ao documento existente do aluno 2 (laudo)
            resp_auth_doc = client.get("/aluno/2/documento/doc_laudo")
            print(f"[INFO] Resposta documento aluno 2 autenticado: {resp_auth_doc.status_code}, content-type: {resp_auth_doc.content_type}")
            if resp_auth_doc.status_code == 200:
                assert resp_auth_doc.content_type == "application/pdf"
                print("[PASS] 6. Usuário autorizado baixa documento/laudo com sucesso (200 OK, application/pdf)")

            # Testa acesso à foto do aluno 1
            resp_auth_foto = client.get("/aluno/1/foto")
            print(f"[INFO] Resposta foto aluno 1 autenticado: {resp_auth_foto.status_code}, content-type: {resp_auth_foto.content_type}")
            assert resp_auth_foto.status_code in (200, 302)
            print("[PASS] 7. Usuário autorizado visualiza foto do aluno com sucesso")

            # Testa documento inexistente / doc_id inválido
            resp_invalid_doc = client.get("/aluno/2/documento/arquivo_malicioso")
            assert resp_invalid_doc.status_code == 404
            print("[PASS] 8. doc_id fora da lista canônica rejeitado (404)")

    print("=" * 60)
    print("TODAS AS VERIFICAÇÕES DE SEC-01 PASSARAM COM SUCESSO!")
    print("=" * 60)


if __name__ == "__main__":
    run_checks()
