from app.models import ConfiguracaoSistema


MANUTENCAO_CONFIG_KEY = "manutencao_ativa"


def is_maintenance_enabled() -> bool:
    config = ConfiguracaoSistema.query.filter_by(
        chave=MANUTENCAO_CONFIG_KEY,
        unidade_id=None,
    ).first()
    return bool(config and (config.valor or "").strip().lower() == "true")
