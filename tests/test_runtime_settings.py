from evalops.runtime import ApiType, configure, settings


def test_configure_uses_gemini_env_names(monkeypatch):
    monkeypatch.delenv("EVALOPS_DISABLE_LLM", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "key")
    monkeypatch.setenv("MODEL", "gemini-test")

    configure()

    assert settings().api_type == ApiType.GOOGLE
    assert settings().api_key == "key"
    assert settings().model == "gemma-4-31b-it"


def test_configure_stores_prompt_template_paths(tmp_path):
    configure(PROMPT_TEMPLATES_PATH=[tmp_path])

    assert settings().prompt_templates_path == [tmp_path]
