from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID, uuid5

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base, build_engine, build_session_factory
from app.models import (
    AccessContract,
    AllocationDecision,
    AuditEvent,
    Booking,
    HandoverReport,
    Incident,
    Notification,
    Resource,
    ResourcePolicy,
    ResourceRequest,
    TrainingRecord,
    User,
)
from app.services.auth import hash_password

ORG_ID = "northstar-engineering-lab-demo"
NAMESPACE = UUID("e0766f91-0ec2-4d61-9a65-e3e7935b9084")
DEMO_USER_IDS = {
    "requester_a": str(uuid5(NAMESPACE, "user:requester-a")),
    "requester_b": str(uuid5(NAMESPACE, "user:requester-b")),
    "requester_c": str(uuid5(NAMESPACE, "user:requester-c")),
    "lab_manager": str(uuid5(NAMESPACE, "user:lab-manager")),
    "institution_admin": str(uuid5(NAMESPACE, "user:institution-admin")),
    "judge_auditor": str(uuid5(NAMESPACE, "user:judge-auditor")),
}
RESOURCE_IDS = {
    "printer": str(uuid5(NAMESPACE, "resource:3d-printer")),
    "camera": str(uuid5(NAMESPACE, "resource:camera-kit")),
    "oscilloscope": str(uuid5(NAMESPACE, "resource:oscilloscope-training-station")),
    "bench": str(uuid5(NAMESPACE, "resource:electronics-bench")),
    "room": str(uuid5(NAMESPACE, "resource:meeting-project-room")),
    "maintenance": str(uuid5(NAMESPACE, "resource:maintenance-hold")),
}
SEED_OBJECT_IDS = {
    name: str(uuid5(NAMESPACE, name))
    for name in (
        "policy:printer",
        "policy:camera",
        "policy:oscilloscope",
        "policy:bench",
        "policy:room",
        "policy:maintenance",
        "training:requester-a",
        "training:requester-b",
        "request:completed",
        "request:pending",
        "request:competing",
        "request:waitlisted",
        "request:upcoming",
        "request:incident",
        "booking:completed",
        "booking:upcoming",
        "booking:incident",
        "contract:completed",
        "contract:upcoming",
        "contract:incident",
        "handover:completed-in",
        "handover:completed-out",
        "handover:incident-in",
        "handover:incident-out",
        "decision:waitlisted",
        "incident:condition-discrepancy",
        "audit:maintenance-hold",
        "notification:pending-decision",
    )
}

DEMO_USERS = (
    ("requester_a", "Requester A", "requester"),
    ("requester_b", "Requester B", "requester"),
    ("requester_c", "Requester C", "requester"),
    ("lab_manager", "Lab Manager", "lab_manager"),
    ("institution_admin", "Institution Admin", "institution_admin"),
    ("judge_auditor", "Judge Auditor", "auditor"),
)

DEMO_RESOURCES = (
    ("printer", "3D Printer", "fabrication", ["3d printing", "prototyping"], "Fabrication Bay", "active", None, []),
    ("camera", "Camera Kit", "media", ["video", "photography"], "Media Store", "active", None, []),
    ("oscilloscope", "Oscilloscope Training Station", "electronics", ["oscilloscope", "measurement"], "Electronics Lab", "active", None, ["OSCILLOSCOPE_SAFETY"]),
    ("bench", "Electronics Bench", "electronics", ["soldering", "measurement"], "Electronics Lab", "active", None, []),
    ("room", "Meeting / Project Room", "space", ["teamwork", "project work"], "Northstar Lab", "active", None, []),
    ("maintenance", "Maintenance Hold Resource", "equipment", ["maintenance demonstration"], "Service Bay", "maintenance_hold", date.today() - timedelta(days=1), []),
)


def seed_database(
    session_factory: sessionmaker[Session],
    demo_password: str = "northstar-demo",
    *,
    force: bool = False,
) -> None:
    with session_factory() as session:
        has_existing_data = any(
            session.execute(select(table).limit(1)).first() is not None
            for table in Base.metadata.sorted_tables
        )
        if has_existing_data and not force:
            return

        password_hash = hash_password(demo_password)
        users = {
            key: User(
                id=DEMO_USER_IDS[key],
                display_name=label,
                role=role,
                organization_id=ORG_ID,
                is_demo=True,
                password_hash=password_hash,
            )
            for key, label, role in DEMO_USERS
        }
        session.add_all(users.values())
        session.flush()

        open_hours = [
            {"weekday": weekday, "start": "00:00", "end": "23:59"}
            for weekday in range(1, 8)
        ]
        resources = {}
        policies = {}
        for key, name, category, tags, location, status, hold_date, training_codes in DEMO_RESOURCES:
            resource = Resource(
                id=RESOURCE_IDS[key],
                owner_id=DEMO_USER_IDS["lab_manager"],
                name=name,
                category=category,
                capability_tags=tags,
                location=location,
                status=status,
                hold_review_date=hold_date,
                weekly_operating_hours=open_hours,
                max_duration_minutes=240,
                exclusive_booking=True,
                is_demo=True,
            )
            resources[key] = resource
            session.add(resource)
        session.flush()

        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        for key, _name, _category, _tags, _location, _status, _hold_date, training_codes in DEMO_RESOURCES:
            policy_id = SEED_OBJECT_IDS[f"policy:{key}"]
            policy = ResourcePolicy(
                id=policy_id,
                resource_id=RESOURCE_IDS[key],
                version=1,
                structured_requirements={
                    "training_codes": training_codes,
                    "supervisor_required": key == "oscilloscope",
                    "supervised_windows": open_hours if key == "oscilloscope" else [],
                },
                allowed_uses=["project", "coursework", "research"],
                priority_policy={},
                effective_at=now,
                approved_by=DEMO_USER_IDS["lab_manager"],
                activation_reason="Initial DEMO seed policy activation.",
                is_demo=True,
            )
            policies[key] = policy
            session.add(policy)

        for key, requirement in (
            ("requester_a", "OSCILLOSCOPE_SAFETY"),
            ("requester_b", "OSCILLOSCOPE_SAFETY"),
        ):
            training_key = f"training:{key.replace('_', '-')}"
            session.add(
                TrainingRecord(
                    id=SEED_OBJECT_IDS[training_key],
                    user_id=DEMO_USER_IDS[key],
                    requirement_code=requirement,
                    status="valid",
                    verified_by=DEMO_USER_IDS["lab_manager"],
                    valid_from=now - timedelta(days=30),
                    valid_to=None,
                    is_demo=True,
                )
            )
        session.flush()

        day_start = (now + timedelta(days=2)).replace(hour=10, minute=0)
        day_end = day_start + timedelta(hours=1)
        old_start = now - timedelta(days=4)
        old_end = old_start + timedelta(hours=1)
        future_start = now + timedelta(days=5)
        future_end = future_start + timedelta(hours=1)

        def add_request(name, requester_key, resource_key, status, start, end):
            request_id = SEED_OBJECT_IDS[f"request:{name}"]
            row = ResourceRequest(
                id=request_id,
                requester_id=DEMO_USER_IDS[requester_key],
                resource_id=RESOURCE_IDS[resource_key],
                purpose="project",
                start_at=start,
                end_at=end,
                status=status,
                created_at=now - timedelta(hours=1),
                idempotency_key=None,
                is_demo=True,
            )
            session.add(row)
            return row

        completed_request = add_request(
            "completed", "requester_a", "bench", "CLOSED", old_start, old_end
        )
        pending_request = add_request(
            "pending", "requester_a", "oscilloscope", "PENDING_REVIEW", day_start, day_end
        )
        add_request(
            "competing", "requester_b", "oscilloscope", "PENDING_REVIEW", day_start, day_end
        )
        waitlisted_request = add_request(
            "waitlisted", "requester_b", "camera", "WAITLISTED", day_start, day_end
        )
        upcoming_request = add_request(
            "upcoming", "requester_b", "camera", "APPROVED", future_start, future_end
        )
        incident_request = add_request(
            "incident", "requester_a", "printer", "INCIDENT_REVIEW", old_start, old_end
        )
        session.flush()

        def add_booking(name, request, status, approver, start, end):
            row = Booking(
                id=SEED_OBJECT_IDS[f"booking:{name}"],
                request_id=request.id,
                start_at=start,
                end_at=end,
                status=status,
                approved_by=approver,
                version=1,
                is_demo=True,
            )
            session.add(row)
            return row

        completed_booking = add_booking(
            "completed",
            completed_request,
            "CLOSED",
            DEMO_USER_IDS["lab_manager"],
            old_start,
            old_end,
        )
        upcoming_booking = add_booking(
            "upcoming",
            upcoming_request,
            "CONFIRMED",
            DEMO_USER_IDS["lab_manager"],
            future_start,
            future_end,
        )
        incident_booking = add_booking(
            "incident",
            incident_request,
            "INCIDENT_REVIEW",
            DEMO_USER_IDS["lab_manager"],
            old_start,
            old_end,
        )
        session.flush()

        def add_contract(name, booking, request, resource_key, status):
            return AccessContract(
                id=SEED_OBJECT_IDS[f"contract:{name}"],
                booking_id=booking.id,
                version=1,
                request_id=request.id,
                resource_id=RESOURCE_IDS[resource_key],
                requester_id=request.requester_id,
                approver_id=DEMO_USER_IDS["lab_manager"],
                start_at=booking.start_at,
                end_at=booking.end_at,
                approved_purpose=request.purpose,
                policy_version_id=policies[resource_key].id,
                requirements_snapshot=policies[resource_key].structured_requirements,
                supervision_requirement=resource_key == "oscilloscope",
                permitted_use=["project", "coursework", "research"],
                checkin_required=True,
                checkout_required=True,
                condition_checklist_version="northstar-condition-v1",
                status=status,
                created_at=now - timedelta(days=5),
                approved_at=now - timedelta(days=5),
                expires_at=booking.end_at,
                is_demo=True,
            )

        session.add_all(
            [
                add_contract("completed", completed_booking, completed_request, "bench", "COMPLETED"),
                add_contract("upcoming", upcoming_booking, upcoming_request, "camera", "ACTIVE"),
                add_contract("incident", incident_booking, incident_request, "printer", "ACTIVE"),
            ]
        )
        good_condition = {
            "physical_condition": "ok",
            "accessories_complete": "yes",
            "functional_test": "works",
            "notes": None,
        }
        discrepant_condition = {
            "physical_condition": "damaged",
            "accessories_complete": "no",
            "functional_test": "issue",
            "notes": "Synthetic discrepancy for human review.",
        }
        session.add_all(
            [
                HandoverReport(
                    id=SEED_OBJECT_IDS["handover:completed-in"],
                    booking_id=completed_booking.id,
                    stage="IN",
                    checklist_version="northstar-condition-v1",
                    condition=good_condition,
                    notes=None,
                    evidence_references=[],
                    actor_id=completed_request.requester_id,
                    created_at=old_start,
                    is_demo=True,
                ),
                HandoverReport(
                    id=SEED_OBJECT_IDS["handover:completed-out"],
                    booking_id=completed_booking.id,
                    stage="OUT",
                    checklist_version="northstar-condition-v1",
                    condition=good_condition,
                    notes=None,
                    evidence_references=[],
                    actor_id=completed_request.requester_id,
                    created_at=old_end,
                    is_demo=True,
                ),
                HandoverReport(
                    id=SEED_OBJECT_IDS["handover:incident-in"],
                    booking_id=incident_booking.id,
                    stage="IN",
                    checklist_version="northstar-condition-v1",
                    condition=good_condition,
                    notes=None,
                    evidence_references=[{"file_name": "before-condition.txt", "note": "DEMO DATA"}],
                    actor_id=incident_request.requester_id,
                    created_at=old_start,
                    is_demo=True,
                ),
                HandoverReport(
                    id=SEED_OBJECT_IDS["handover:incident-out"],
                    booking_id=incident_booking.id,
                    stage="OUT",
                    checklist_version="northstar-condition-v1",
                    condition=discrepant_condition,
                    notes=discrepant_condition["notes"],
                    evidence_references=[{"file_name": "return-condition.txt", "note": "DEMO DATA"}],
                    actor_id=incident_request.requester_id,
                    created_at=old_end,
                    is_demo=True,
                ),
            ]
        )
        session.add(
            AllocationDecision(
                id=SEED_OBJECT_IDS["decision:waitlisted"],
                request_id=waitlisted_request.id,
                decision_sequence=1,
                policy_version=policies["camera"].id,
                outcome="waitlisted",
                explanation_code="capacity_waitlist",
                explanation="Waitlisted for the seeded DEMO scenario.",
                inputs_snapshot={"demo_data": True, "algorithm_version": "1"},
                reviewer_override=None,
                reviewer_id=DEMO_USER_IDS["lab_manager"],
                created_at=now - timedelta(minutes=30),
                is_demo=True,
            )
        )
        session.add(
            Incident(
                id=SEED_OBJECT_IDS["incident:condition-discrepancy"],
                booking_id=incident_booking.id,
                reporter_id=incident_request.requester_id,
                category="damage",
                description="Synthetic return-condition discrepancy; no blame assigned.",
                status="UNDER_REVIEW",
                responses=[],
                resolution=None,
                reviewer_id=None,
                created_at=old_end,
                updated_at=old_end,
                is_demo=True,
            )
        )
        session.add(
            AuditEvent(
                id=SEED_OBJECT_IDS["audit:maintenance-hold"],
                actor_id=DEMO_USER_IDS["lab_manager"],
                entity_type="resource",
                entity_id=RESOURCE_IDS["maintenance"],
                action="resource.maintenance_hold_set",
                timestamp=now - timedelta(days=3),
                request_id=None,
                correlation_id=None,
                before_summary={"status": "active"},
                after_summary={"status": "maintenance_hold", "demo_data": True},
                previous_hash=None,
                hash=None,
                is_demo=True,
            )
        )
        session.add(
            Notification(
                id=SEED_OBJECT_IDS["notification:pending-decision"],
                recipient_id=pending_request.requester_id,
                type="decision",
                related_entity_type="request",
                related_entity_id=pending_request.id,
                read_at=None,
                created_at=now,
                is_demo=True,
            )
        )
        session.commit()


def reset_demo_data(session: Session) -> None:
    for model in (
        Notification,
        Incident,
        HandoverReport,
        AccessContract,
        Booking,
        AllocationDecision,
        ResourceRequest,
        TrainingRecord,
        ResourcePolicy,
        AuditEvent,
        Resource,
        User,
    ):
        session.execute(delete(model).where(model.is_demo.is_(True)))
    session.commit()


def main() -> None:
    import os

    database_url = os.environ.get("DATABASE_URL", "sqlite:///./openvault.db")
    demo_password = os.environ.get("DEMO_PASSWORD", "northstar-demo")
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    seed_database(build_session_factory(engine), demo_password)
    engine.dispose()
    print("Seeded Northstar Engineering Lab (DEMO).")


if __name__ == "__main__":
    main()
