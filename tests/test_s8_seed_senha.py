import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_a_modulo_nao_contem_senha_antiga():
    src = open("scripts/semear_roteiro_manual.py", encoding="utf-8").read()
    assert "Roteiro!2026" not in src


def test_b_resolucao_ordem():
    import argparse
    from scripts.semear_roteiro_manual import resolver_senha

    # --senha tem prioridade
    ns = argparse.Namespace(senha="MinhaSenha!123")
    os.environ["ROTEIRO_SENHA"] = "EnvSenha!123"
    s, orig = resolver_senha(ns)
    assert s == "MinhaSenha!123" and orig == "argumento"

    # ambiente
    ns2 = argparse.Namespace(senha=None)
    s2, orig2 = resolver_senha(ns2)
    assert s2 == "EnvSenha!123" and orig2 == "ambiente"

    # gerada
    del os.environ["ROTEIRO_SENHA"]
    ns3 = argparse.Namespace(senha=None)
    s3, orig3 = resolver_senha(ns3)
    assert orig3 == "gerada"
    from app.services.auth_service import validate_password_strength
    assert not validate_password_strength(s3)


def test_c_senha_fraca_recusada():
    from app.services.auth_service import validate_password_strength
    assert validate_password_strength("fraca")  # lista não vazia


def test_d_senha_gerada_atende():
    from app.services.auth_service import generate_secure_random_password, validate_password_strength
    s = generate_secure_random_password(16)
    assert not validate_password_strength(s)
