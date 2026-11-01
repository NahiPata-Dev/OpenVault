import json

import pytest

from app.services.ai_provider import AIProviderError, AIProviderNotConfigured, complete_chat


def test_chat_provider_requires_server_side_api_key(monkeypatch):
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    with pytest.raises(AIProviderNotConfigured):
        complete_chat([{"role": "user", "content": "Help me plan."}])


def test_chat_provider_sends_configured_model_request(monkeypatch):
    monkeypatch.setenv("AI_API_KEY", "test-key")
    monkeypatch.setenv("AI_BASE_URL", "https://llm.example.test/v1/")
    monkeypatch.setenv("AI_MODEL", "test-chat-model")
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return json.dumps(
                {"choices": [{"message": {"content": "{\"reply\":\"Ready\"}"}}]}
            ).encode()

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["authorization"] = request.get_header("Authorization")
        captured["payload"] = json.loads(request.data)
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("app.services.ai_provider.urlopen", fake_urlopen)
    response = complete_chat([{"role": "user", "content": "Help me plan."}])

    assert response == '{"reply":"Ready"}'
    assert captured["url"] == "https://llm.example.test/v1/chat/completions"
    assert captured["authorization"] == "Bearer test-key"
    assert captured["payload"]["model"] == "test-chat-model"
    assert captured["payload"]["messages"] == [
        {"role": "user", "content": "Help me plan."}
    ]
    assert captured["timeout"] == 30


def test_openrouter_key_uses_openrouter_defaults(monkeypatch):
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_SITE_URL", "https://openvault.example.test")
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return b'{"choices":[{"message":{"content":"{\\"reply\\":\\"Ready\\"}"}}]}'

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["model"] = json.loads(request.data)["model"]
        captured["referer"] = request.get_header("Http-referer")
        return FakeResponse()

    monkeypatch.setattr("app.services.ai_provider.urlopen", fake_urlopen)
    complete_chat([{"role": "user", "content": "Help me plan."}])

    assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert captured["model"] == "openai/gpt-4o-mini"
    assert captured["referer"] == "https://openvault.example.test"


def test_provider_rejects_non_tls_remote_endpoints(monkeypatch):
    monkeypatch.setenv("AI_API_KEY", "test-key")
    monkeypatch.setenv("AI_BASE_URL", "http://remote.example.test/v1")

    with pytest.raises(AIProviderError):
        complete_chat([{"role": "user", "content": "Help me plan."}])