from sqlalchemy import select

from app.models import DiscoveryFeedback


def test_resource_matching_feedback_is_saved_without_prompt(requester_login):
    response = requester_login.post(
        "/api/feedback",
        json={"is_helpful": False},
    )

    assert response.status_code == 201, response.text
    feedback_id = response.json()["feedback"]["id"]
    with requester_login.app.state.session_factory() as session:
        feedback = session.scalar(
            select(DiscoveryFeedback).where(DiscoveryFeedback.id == feedback_id)
        )
        assert feedback is not None
        assert feedback.is_helpful is False
        assert feedback.user_id is not None
        assert feedback.created_at is not None


def test_resource_matching_feedback_requires_sign_in(client):
    response = client.post("/api/feedback", json={"is_helpful": True})

    assert response.status_code == 401