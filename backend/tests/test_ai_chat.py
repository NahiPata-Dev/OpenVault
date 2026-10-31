import json

from app.seed import RESOURCE_IDS


def test_ai_chat_reports_missing_provider_configuration(client, monkeypatch):
    monkeypatch.setattr("app.api.ai.ai_provider_configured", lambda: False)

    status = client.get("/api/ai/status")
    response = client.post(
        "/api/ai/chat",
        json={"messages": [{"role": "user", "content": "Help me plan a prototype."}]},
    )

    assert status.json() == {"available": False}
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ai_not_configured"


def test_ai_chat_uses_model_reply_and_only_returns_retrieved_resources(
    requester_login, monkeypatch
):
    captured = {}
    monkeypatch.setattr("app.api.ai.ai_provider_configured", lambda: True)

    def fake_complete_chat(messages):
        captured["messages"] = messages
        return json.dumps(
            {
                "reply": "The printer could fit. Check its material rules first.",
                "resource_ids": [RESOURCE_IDS["printer"], "untrusted-resource-id"],
            }
        )

    monkeypatch.setattr("app.api.ai.complete_chat", fake_complete_chat)
    response = requester_login.post(
        "/api/ai/chat",
        json={
            "messages": [
                {"role": "user", "content": "I want a 3D printer for a prototype."}
            ]
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "ai"
    assert "Check its material rules" in body["reply"]
    assert [resource["resource_id"] for resource in body["resources"]] == [
        RESOURCE_IDS["printer"]
    ]
    system_context = captured["messages"][0]["content"]
    assert "profile_intended_use" in system_context
    assert "Fabrication Bay" in system_context


def test_anonymous_ai_chat_can_plan_without_catalog_resources(client, monkeypatch):
    monkeypatch.setattr("app.api.ai.ai_provider_configured", lambda: True)
    monkeypatch.setattr(
        "app.api.ai.complete_chat",
        lambda _messages: '{"reply":"What result do you want to produce?","resource_ids":[]}',
    )

    response = client.post(
        "/api/ai/chat",
        json={"messages": [{"role": "user", "content": "I am planning a project."}]},
    )

    assert response.status_code == 200, response.text
    assert response.json()["reply"] == "What result do you want to produce?"
    assert response.json()["resources"] == []