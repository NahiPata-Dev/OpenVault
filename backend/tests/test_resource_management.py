from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, inspect, select

from app.database import build_engine, migrate_legacy_resource_schema
from app.models import (
    AccessContract,
    AuditEvent,
    Booking,
    Resource,
    ResourcePolicy,
    ResourceRequest,
    TrainingRecord,
    User,
)
from app.seed import RESOURCE_IDS, SEED_OBJECT_IDS
from app.services.auth import hash_password
from tests.conftest import login


def test_seed_has_detailed_resources_and_deterministic_sample_records(client):
    with client.app.state.session_factory() as session:
        resources = session.scalars(select(Resource).where(Resource.is_demo.is_(True))).all()
        historical_bookings = session.scalar(
            select(func.count(Booking.id)).where(
                Booking.is_demo.is_(True),
                Booking.start_at < datetime.now(timezone.utc),
                Booking.start_at >= datetime.now(timezone.utc) - timedelta(days=30),
            )
        )
        assert historical_bookings == 25
        assert session.scalar(
            select(func.count(TrainingRecord.id)).where(TrainingRecord.is_demo.is_(True))
        ) == 8
        assert session.scalar(
            select(func.count(AuditEvent.id)).where(AuditEvent.is_demo.is_(True))
        ) == 12
        assert len(resources) == 6
        for resource in resources:
            assert "Sample data" in resource.short_summary
            assert resource.description
            assert resource.building and resource.room and resource.address_note
            assert resource.weekly_operating_hours
            assert resource.capacity or resource.quantity
            assert resource.allowed_uses
            assert resource.usage_rules and resource.safety_notes
            assert resource.accessories_included and resource.condition_notes

        competing = session.scalars(
            select(ResourceRequest).where(
                ResourceRequest.id.in_(
                    [
                        SEED_OBJECT_IDS["request:pending"],
                        SEED_OBJECT_IDS["request:competing"],
                        SEED_OBJECT_IDS["request:competing-c"],
                    ]
                )
            )
        ).all()
        assert len(competing) == 3
        assert len({(row.start_at, row.end_at) for row in competing}) == 1
        waitlisted = session.get(ResourceRequest, SEED_OBJECT_IDS["request:waitlisted"])
        decision = waitlisted.decisions[0]
        assert decision.outcome == "waitlisted"
        assert decision.explanation


def test_resource_search_details_and_manager_policy_versioning(manager_login):
    camera_id = RESOURCE_IDS["camera"]
    before_response = manager_login.get(f"/api/resources/{camera_id}")
    assert before_response.status_code == 200, before_response.text
    before = before_response.json()
    assert before["resource"]["short_summary"].startswith("Sample data")
    assert before["eligibility_checklist"]
    assert manager_login.get(
        "/api/resources",
        params={"supervised": "true", "training_required": "true"},
    ).json()["total"] == 1

    with manager_login.app.state.session_factory() as session:
        contract = session.scalar(
            select(AccessContract).where(
                AccessContract.policy_version_id == SEED_OBJECT_IDS["policy:camera"]
            )
        )
        contract_id = contract.id
        snapshot = contract.requirements_snapshot

    updated = manager_login.patch(
        f"/api/resources/{camera_id}",
        json={
            "short_summary": "Sample data — manager-edited camera kit.",
            "policy_change_reason": "Updated the sample catalog description.",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["resource"]["short_summary"].startswith("Sample data")
    assert updated.json()["active_policy"]["version"] == 2
    with manager_login.app.state.session_factory() as session:
        contract = session.get(AccessContract, contract_id)
        assert contract.requirements_snapshot == snapshot
        versions = session.scalars(
            select(ResourcePolicy)
            .where(ResourcePolicy.resource_id == camera_id)
            .order_by(ResourcePolicy.version)
        ).all()
        assert [row.version for row in versions] == [1, 2]
        activation = session.scalar(
            select(AuditEvent).where(
                AuditEvent.entity_type == "resource_policy",
                AuditEvent.entity_id == versions[1].id,
            )
        )
        assert activation.after_summary["reason"] == "Updated the sample catalog description."


def test_manager_cannot_edit_another_managers_resource(manager_login):
    owner_id = str(uuid4())
    resource_id = str(uuid4())
    with manager_login.app.state.session_factory() as session:
        session.add(
            User(
                id=owner_id,
                display_name="Other Manager",
                role="lab_manager",
                organization_id="northstar-engineering-lab-demo",
                is_demo=False,
                password_hash=hash_password("other-manager-password"),
            )
        )
        session.add(
            Resource(
                id=resource_id,
                owner_id=owner_id,
                name="Other manager's resource",
                category="equipment",
                location="Northstar",
                weekly_operating_hours=[],
            )
        )
        session.commit()
    response = manager_login.patch(
        f"/api/resources/{resource_id}",
        json={
            "name": "Unauthorized edit",
            "policy_change_reason": "Test manager scope enforcement.",
        },
    )
    assert response.status_code == 403


def test_resource_checklist_reports_duration_and_advance_window(client):
    login(client, "requester_a")
    start = datetime.now(timezone.utc) + timedelta(days=100)
    response = client.get(
        f"/api/resources/{RESOURCE_IDS['camera']}",
        params={
            "start_at": start.isoformat(),
            "end_at": (start + timedelta(hours=9)).isoformat(),
            "purpose": "project",
        },
    )
    assert response.status_code == 200, response.text
    checks = {item["requirement"]: item for item in response.json()["eligibility_checklist"]}
    assert checks["Maximum session duration"]["code"] == "duration_exceeded"
    assert checks["Maximum session duration"]["passed"] is False
    assert checks["Advance booking window"]["code"] == "advance_booking_window"
    assert checks["Advance booking window"]["passed"] is False


def test_requester_and_manager_dashboards_show_scoped_items(client):
    login(client, "requester_a")
    requester = client.get("/api/dashboard/requester")
    assert requester.status_code == 200, requester.text
    assert requester.json()["summary"]["open_incidents"] == 1
    assert len(requester.json()["next_items"]) <= 5

    login(client, "lab_manager")
    manager = client.get("/api/dashboard/manager")
    assert manager.status_code == 200, manager.text
    assert manager.json()["summary"]["pending_requests"] == 4
    assert manager.json()["summary"]["open_incidents"] == 1
    assert manager.json()["summary"]["expiring_training"] == 2
    assert len(manager.json()["next_items"]) <= 5


def test_legacy_sqlite_resource_table_is_upgraded(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'legacy-resources.db'}"
    engine = build_engine(database_url)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE resources (
                id CHAR(32) NOT NULL PRIMARY KEY,
                owner_id CHAR(32) NOT NULL,
                name VARCHAR(160) NOT NULL,
                category VARCHAR(80) NOT NULL,
                capability_tags JSON NOT NULL,
                location VARCHAR(160) NOT NULL,
                status VARCHAR(32) NOT NULL,
                hold_review_date DATE,
                weekly_operating_hours JSON NOT NULL,
                max_duration_minutes INTEGER,
                exclusive_booking BOOLEAN NOT NULL,
                is_demo BOOLEAN NOT NULL,
                CONSTRAINT ck_resources_status
                    CHECK (status IN ('active', 'maintenance_hold')),
                CONSTRAINT ck_resources_hold_review_date
                    CHECK (status != 'maintenance_hold' OR hold_review_date IS NOT NULL),
                CONSTRAINT ck_resources_positive_max_duration
                    CHECK (max_duration_minutes IS NULL OR max_duration_minutes > 0)
            )
            """
        )
    migrate_legacy_resource_schema(engine)
    columns = {column["name"] for column in inspect(engine).get_columns("resources")}
    assert "short_summary" in columns
    assert "advance_booking_window" in columns
    with engine.connect() as connection:
        schema = connection.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='resources'"
        ).scalar_one()
    assert "'retired'" in schema
    engine.dispose()
