from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select

from app.models import AccountProfile, Resource, ResourcePolicy, User
from app.schemas import ResourceMatchResult
from app.seed import DEMO_USER_IDS, RESOURCE_IDS
from app.services.ai_provider import validate_provider_result
from app.services.auth import hash_password
from tests.conftest import login


def test_resource_memory_counts_reconcile_with_seed_rows(requester_login):
    now = datetime.now(timezone.utc)
    response = requester_login.get(
        f"/api/resources/{RESOURCE_IDS['camera']}/memory",
        params={
            "from": (now - timedelta(days=1)).isoformat(),
            "to": (now + timedelta(days=10)).isoformat(),
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    metrics = body["metrics"]
    assert metrics["scheduled_hours"] == 1
    assert metrics["waitlist_demand"] == {"requests": 1, "hours": 1}
    assert body["demo_data"] is True
    assert body["label"] == "DEMO DATA — not live institutional statistics"


def test_memory_recommendations_reference_training_and_supervisor_sources(requester_login):
    now = datetime.now(timezone.utc)
    start = now + timedelta(days=10)
    end = start + timedelta(hours=1)
    with requester_login.app.state.session_factory() as session:
        policy = session.scalar(
            select(ResourcePolicy).where(
                ResourcePolicy.resource_id == RESOURCE_IDS["oscilloscope"]
            )
        )
        policy.structured_requirements = {
            "training_codes": ["NEW_TRAINING"],
            "supervisor_required": False,
            "supervised_windows": [],
        }
        session.commit()

    request_ids = []
    for account in ("requester_a", "requester_b"):
        login(requester_login, account)
        submitted = requester_login.post(
            "/api/requests",
            json={
                "resource_id": RESOURCE_IDS["oscilloscope"],
                "purpose": "project",
                "start_at": start.isoformat(),
                "end_at": end.isoformat(),
            },
        )
        assert submitted.status_code == 201, submitted.text
        request_ids.append(submitted.json()["request"]["id"])

    with requester_login.app.state.session_factory() as session:
        policy = session.scalar(
            select(ResourcePolicy).where(
                ResourcePolicy.resource_id == RESOURCE_IDS["oscilloscope"]
            )
        )
        policy.structured_requirements = {
            "training_codes": [],
            "supervisor_required": True,
            "supervised_windows": [],
        }
        session.commit()
    supervised_ids = []
    for account in ("requester_a", "requester_b"):
        login(requester_login, account)
        submitted = requester_login.post(
            "/api/requests",
            json={
                "resource_id": RESOURCE_IDS["oscilloscope"],
                "purpose": "project",
                "start_at": (start + timedelta(days=1)).isoformat(),
                "end_at": (end + timedelta(days=1)).isoformat(),
            },
        )
        assert submitted.status_code == 201, submitted.text
        supervised_ids.append(submitted.json()["request"]["id"])

    memory = requester_login.get(
        f"/api/resources/{RESOURCE_IDS['oscilloscope']}/memory",
        params={
            "from": (now - timedelta(days=1)).isoformat(),
            "to": (now + timedelta(days=11)).isoformat(),
        },
    )
    assert memory.status_code == 200, memory.text
    by_code = {item["recommendation_code"]: item for item in memory.json()["recommendations"]}
    training = by_code["training_backlog"]
    supervised = by_code["supervised_slot_shortage"]
    assert training["source_counts"] == {"distinct_users": 2, "requests": 2}
    assert set(training["source_record_references"]["request_ids"]) == set(request_ids)
    assert supervised["source_counts"]["requests"] == 2
    assert set(supervised["source_record_references"]["request_ids"]) == set(supervised_ids)


def test_overdue_maintenance_hold_recommendation_is_source_linked(requester_login):
    response = requester_login.get(
        f"/api/resources/{RESOURCE_IDS['maintenance']}/memory"
    )
    assert response.status_code == 200, response.text
    recommendation = next(
        item
        for item in response.json()["recommendations"]
        if item["recommendation_code"] == "maintenance_hold_review"
    )
    assert recommendation["source_counts"]["maintenance_holds"] == 1
    assert recommendation["source_record_references"]["audit_event_ids"]
    assert "does not release" in recommendation["text"]


def test_deterministic_matching_and_hallucinated_id_fallback(requester_login):
    with requester_login.app.state.session_factory() as session:
        profile = session.get(AccountProfile, DEMO_USER_IDS["requester_a"])
        profile.intended_use = "Soldering electronics"
        session.commit()

    response = requester_login.post(
        "/api/ai/match",
        json={
            "goal": "electronics",
            "constraints": {"categories": ["electronics"], "capabilities": []},
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    returned_ids = {item["resource_id"] for item in body["candidates"]}
    assert RESOURCE_IDS["oscilloscope"] in returned_ids
    assert body["candidates"][0]["resource_id"] == RESOURCE_IDS["bench"]
    assert "fits your profile" in body["candidates"][0]["explanation"]
    assert body["source"] == "deterministic"
    assert "suggestions only" in body["disclosure"]

    fallback = ResourceMatchResult(
        criteria={"categories": [], "capabilities": []},
        candidates=[],
        source="deterministic",
        disclosure="Deterministic fallback.",
    )
    invalid_provider_result = {
        "criteria": {"categories": [], "capabilities": []},
        "candidates": [
            {
                "resource_id": str(uuid4()),
                "explanation": "Unknown resource invented by provider.",
            }
        ],
        "source": "ai",
        "disclosure": "Provider result.",
    }
    checked = validate_provider_result(invalid_provider_result, returned_ids, fallback)
    assert checked.source == "deterministic_fallback"
    assert checked.candidates == []


def test_resource_matching_uses_whole_terms_not_substrings(requester_login):
    response = requester_login.post(
        "/api/ai/match",
        json={"goal": "scope", "constraints": {}},
    )

    assert response.status_code == 200, response.text
    assert response.json()["candidates"] == []

    variant_response = requester_login.post(
        "/api/ai/match",
        json={"goal": "3D-printed prototype", "constraints": {}},
    )

    assert variant_response.status_code == 200, variant_response.text
    assert RESOURCE_IDS["printer"] in {
        item["resource_id"] for item in variant_response.json()["candidates"]
    }


def test_resource_matching_accepts_typos_and_multilingual_queries(requester_login):
    typo_response = requester_login.post(
        "/api/ai/match",
        json={"goal": "elctronics lab", "constraints": {}},
    )
    hindi_response = requester_login.post(
        "/api/ai/match",
        json={"goal": "मुझे इलेक्ट्रॉनिक्स प्रयोगशाला चाहिए", "constraints": {}},
    )
    spanish_response = requester_login.post(
        "/api/ai/match",
        json={"goal": "Necesito una impresora para un prototipo", "constraints": {}},
    )
    french_response = requester_login.post(
        "/api/ai/match",
        json={"goal": "Je cherche le laboratoire d'électronique", "constraints": {}},
    )

    for response in (typo_response, hindi_response, spanish_response, french_response):
        assert response.status_code == 200, response.text
    for response in (typo_response, hindi_response, french_response):
        candidate_ids = {item["resource_id"] for item in response.json()["candidates"]}
        assert RESOURCE_IDS["bench"] in candidate_ids
        assert RESOURCE_IDS["oscilloscope"] in candidate_ids
    assert RESOURCE_IDS["printer"] in {
        item["resource_id"] for item in spanish_response.json()["candidates"]
    }


def test_demo_reset_reseeds_only_demo_rows_and_is_admin_only(client):
    with client.app.state.session_factory() as session:
        session.add(
            User(
                id=str(uuid4()),
                display_name="Non-demo Observer",
                role="requester",
                organization_id="northstar-engineering-lab-demo",
                is_demo=False,
                password_hash=hash_password("non-demo-secret"),
            )
        )
        session.commit()
    login(client, "requester_a")
    denied = client.post(
        "/api/admin/demo-reset", json={"confirmation": "RESET_DEMO_DATA"}
    )
    assert denied.status_code == 403

    login(client, "institution_admin")
    reset = client.post(
        "/api/admin/demo-reset", json={"confirmation": "RESET_DEMO_DATA"}
    )
    assert reset.status_code == 200, reset.text
    assert reset.json()["ok"] is True
    with client.app.state.session_factory() as session:
        assert session.get(User, DEMO_USER_IDS["requester_a"]) is not None
        non_demo = session.scalar(
            select(User).where(User.display_name == "Non-demo Observer")
        )
        assert non_demo is not None and not non_demo.is_demo
        resources = session.scalars(
            select(Resource).where(Resource.is_demo.is_(True))
        ).all()
        assert len(resources) == 6


def test_demo_reset_disabled_outside_restricted_environment(manager_login):
    login(manager_login, "institution_admin")
    manager_login.app.state.demo_mode = False
    response = manager_login.post(
        "/api/admin/demo-reset", json={"confirmation": "RESET_DEMO_DATA"}
    )
    assert response.status_code == 403
