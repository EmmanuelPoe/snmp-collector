import pytest

# config is imported inside tests (not at module top): the autouse patch_settings
# fixture must set MANAGER_API_KEY before config.Settings() is constructed.


def test_strong_key_passes(monkeypatch):
    import config

    monkeypatch.setattr(config.settings, "manager_api_key", "a-strong-unique-secret-123")
    config.check_required_secrets()  # no raise


def test_placeholder_key_rejected(monkeypatch):
    import config

    monkeypatch.setattr(config.settings, "manager_api_key", "change-me-in-production")
    with pytest.raises(RuntimeError, match="MANAGER_API_KEY"):
        config.check_required_secrets()


def test_short_key_rejected(monkeypatch):
    import config

    monkeypatch.setattr(config.settings, "manager_api_key", "short")
    with pytest.raises(RuntimeError, match="at least"):
        config.check_required_secrets()
