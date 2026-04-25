from evalops.runtime import ApiType, configure, settings


def test_configure_uses_legacy_env_names(monkeypatch):
    monkeypatch.setenv("LLM_API_TYPE", "openai")
    monkeypatch.setenv("LLM_API_KEY", "key")
    monkeypatch.setenv("MODEL", "gpt-test")

    configure()

    assert settings().api_type == ApiType.OPENAI
    assert settings().api_key == "key"
    assert settings().model == "gpt-test"


def test_configure_accepts_provider_specific_key(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("LLM_API_TYPE", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")

    configure()

    assert settings().api_key == "anthropic-key"
