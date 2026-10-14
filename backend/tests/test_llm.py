from types import SimpleNamespace

from app import llm
from app.config import get_settings


class FakeCompletions:
    def __init__(self):
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content="ok [1]"), finish_reason="stop")
            ],
            usage=SimpleNamespace(prompt_tokens=120, completion_tokens=8),
        )


def test_chat_sends_the_configured_model_and_cost_limits(monkeypatch):
    completions = FakeCompletions()
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    settings = get_settings()
    monkeypatch.setattr(settings, "llm_model", "gpt-4o-mini")
    monkeypatch.setattr(settings, "llm_base_url", "https://api.openai.com/v1")
    monkeypatch.setattr(llm, "_client", lambda: client)

    result = llm.chat([{"role": "user", "content": "hi"}])

    assert completions.kwargs["model"] == "gpt-4o-mini"
    assert completions.kwargs["max_completion_tokens"] == settings.max_completion_tokens
    assert "max_tokens" not in completions.kwargs
    assert completions.kwargs["temperature"] == 0
    assert (result.text, result.total_tokens) == ("ok [1]", 128)


def test_ollama_gets_max_tokens_because_it_ignores_max_completion_tokens(monkeypatch):
    completions = FakeCompletions()
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    monkeypatch.setattr(get_settings(), "llm_base_url", "http://localhost:11434/v1")
    monkeypatch.setattr(llm, "_client", lambda: client)

    llm.chat([{"role": "user", "content": "hi"}])

    assert completions.kwargs["max_tokens"] == get_settings().max_completion_tokens
    assert "max_completion_tokens" not in completions.kwargs


def test_client_points_at_the_configured_base_url(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "llm_base_url", "https://api.openai.com/v1")
    llm._client.cache_clear()
    try:
        assert str(llm._client().base_url).startswith("https://api.openai.com/v1")
    finally:
        llm._client.cache_clear()
