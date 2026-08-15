"""Unit tests for configuration loading and validation."""

from packages.common.config import Settings, get_settings


def test_default_settings():
    """Verify default application settings match specifications."""
    settings = Settings()
    assert settings.environment == "development"
    assert settings.api_port == 8000
    assert settings.simulator_default_seed == 42
    assert "tracemind" in settings.database_url


def test_get_settings_cached():
    """Verify get_settings returns a singleton cached instance."""
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
