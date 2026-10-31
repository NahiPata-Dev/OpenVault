from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID, uuid5

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base, build_engine, build_session_factory
from app.models import (
    AccountProfile,
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
        "request:competing-c",
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
SEED_OBJECT_IDS.update(
    {
        **{
            f"request:history-{index:02d}": str(
                uuid5(NAMESPACE, f"request:history-{index:02d}")
            )
            for index in range(1, 24)
        },
        **{
            f"booking:history-{index:02d}": str(
                uuid5(NAMESPACE, f"booking:history-{index:02d}")
            )
            for index in range(1, 24)
        },
        **{
            f"training:sample-{index:02d}": str(
                uuid5(NAMESPACE, f"training:sample-{index:02d}")
            )
            for index in range(1, 7)
        },
        **{
            f"audit:sample-{index:02d}": str(
                uuid5(NAMESPACE, f"audit:sample-{index:02d}")
            )
            for index in range(2, 13)
        },
    }
)

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
DEMO_RESOURCE_DETAILS = {
    "printer": {
        "short_summary": "Sample data — enclosed FDM printer for prototypes and fixtures.",
        "description": "Sample data. A fictional enclosed fused-deposition printer for approved academic prototypes. Owners provide material guidance and inspect the machine after use.",
        "building": "Northstar Engineering Center",
        "room": "F-104",
        "address_note": "Use the west entrance and check in at the fabrication desk.",
        "capacity": 1,
        "quantity": None,
        "allowed_uses": ["project", "coursework", "research"],
        "who_can_use": ["Northstar students", "Northstar staff"],
        "required_training": [],
        "supervision_required": False,
        "supervised_windows": [],
        "usage_rules": ["Use approved filament only", "Remove completed prints before checkout"],
        "safety_notes": ["Keep the enclosure closed while printing", "Do not touch the heated bed"],
        "max_session_hours": 4,
        "advance_booking_window": 30,
        "cancellation_cutoff": 2,
        "accessories_included": ["Build plate", "Filament guide"],
        "condition_notes": "Sample data. No damage reported; inspect nozzle and build plate before use.",
    },
    "camera": {
        "short_summary": "Sample data — shared camera and audio kit for project documentation.",
        "description": "Sample data. A fictional camera kit containing a mirrorless body, standard lens, tripod and basic audio accessories for supervised institutional projects.",
        "building": "Northstar Media Annex",
        "room": "M-012",
        "address_note": "Collect and return the sealed kit at the media checkout counter.",
        "capacity": None,
        "quantity": 2,
        "allowed_uses": ["project", "coursework", "research"],
        "who_can_use": ["Northstar students", "Northstar staff"],
        "required_training": [],
        "supervision_required": False,
        "supervised_windows": [],
        "usage_rules": ["Return all listed accessories", "Do not leave equipment unattended"],
        "safety_notes": ["Use the neck strap while handheld", "Keep equipment dry"],
        "max_session_hours": 8,
        "advance_booking_window": 45,
        "cancellation_cutoff": 4,
        "accessories_included": ["Standard lens", "Tripod", "Microphone", "Battery"],
        "condition_notes": "Sample data. Lenses are clean and the kit is checked at each return.",
    },
    "oscilloscope": {
        "short_summary": "Sample data — supervised electronics measurement station.",
        "description": "Sample data. A fictional bench oscilloscope and probe station for low-voltage measurement training and coursework.",
        "building": "Northstar Engineering Center",
        "room": "E-208",
        "address_note": "Ask the electronics lab desk to unlock the instrument cabinet.",
        "capacity": 1,
        "quantity": None,
        "allowed_uses": ["project", "coursework", "research"],
        "who_can_use": ["Trained Northstar students", "Northstar engineering staff"],
        "required_training": ["Oscilloscope Safety"],
        "supervision_required": True,
        "supervised_windows": [
            {"weekday": weekday, "start": "00:00", "end": "23:59"}
            for weekday in range(1, 8)
        ],
        "usage_rules": ["Use only within rated input limits", "Return probes to the marked drawer"],
        "safety_notes": ["Never connect mains voltage", "Inspect probes before each session"],
        "max_session_hours": 3,
        "advance_booking_window": 21,
        "cancellation_cutoff": 2,
        "accessories_included": ["Passive probes", "Ground leads", "Test leads"],
        "condition_notes": "Sample data. Calibration label is current in this fictional demo.",
    },
    "bench": {
        "short_summary": "Sample data — shared electronics bench for low-voltage assembly.",
        "description": "Sample data. A fictional ESD-protected bench with soldering and measurement tools for approved low-voltage work.",
        "building": "Northstar Engineering Center",
        "room": "E-204",
        "address_note": "Use the marked ESD station and return tools to the shadow board.",
        "capacity": 1,
        "quantity": None,
        "allowed_uses": ["project", "coursework", "research"],
        "who_can_use": ["Northstar students", "Northstar staff"],
        "required_training": [],
        "supervision_required": False,
        "supervised_windows": [],
        "usage_rules": ["Use the fume extractor when soldering", "Leave the bench clear"],
        "safety_notes": ["Wear eye protection", "Do not work on energized circuits"],
        "max_session_hours": 4,
        "advance_booking_window": 30,
        "cancellation_cutoff": 2,
        "accessories_included": ["Soldering station", "ESD mat", "Hand tools"],
        "condition_notes": "Sample data. Fume extractor and ESD mat passed the fictional daily check.",
    },
    "room": {
        "short_summary": "Sample data — bookable project room for small working groups.",
        "description": "Sample data. A fictional collaborative room for project meetings, design reviews and coursework planning.",
        "building": "Northstar Learning Commons",
        "room": "L-301",
        "address_note": "Room is on the third floor beside the project studios.",
        "capacity": 8,
        "quantity": None,
        "allowed_uses": ["project", "coursework", "research"],
        "who_can_use": ["Northstar students", "Northstar staff"],
        "required_training": [],
        "supervision_required": False,
        "supervised_windows": [],
        "usage_rules": ["Leave the room ready for the next group", "Keep discussions at a considerate volume"],
        "safety_notes": ["Keep the exit clear", "Report damaged furniture to the desk"],
        "max_session_hours": 4,
        "advance_booking_window": 60,
        "cancellation_cutoff": 1,
        "accessories_included": ["Display", "Whiteboard", "Conference speaker"],
        "condition_notes": "Sample data. Furniture and display are in serviceable condition.",
    },
    "maintenance": {
        "short_summary": "Sample data — equipment temporarily held for a scheduled inspection.",
        "description": "Sample data. A fictional demonstration resource kept unavailable while a safety inspection is reviewed.",
        "building": "Northstar Engineering Center",
        "room": "S-001",
        "address_note": "Not available for collection while the hold is active.",
        "capacity": 1,
        "quantity": None,
        "allowed_uses": ["project", "coursework", "research"],
        "who_can_use": ["Northstar students", "Northstar staff"],
        "required_training": [],
        "supervision_required": False,
        "supervised_windows": [],
        "usage_rules": ["Do not reserve or operate while on hold"],
        "safety_notes": ["Keep clear of the marked inspection area"],
        "max_session_hours": 2,
        "advance_booking_window": 60,
        "cancellation_cutoff": 2,
        "accessories_included": ["Inspection checklist"],
        "condition_notes": "Sample data. Inspection is pending; status changes require manager review.",
        "hold_reason": "Sample data. Scheduled safety inspection is pending.",
    },
}


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

        demo_intents = {
            "requester_a": "Electronics prototyping and measurement projects",
            "requester_b": "Photography, video production and project documentation",
            "requester_c": "Collaborative coursework and team project planning",
            "lab_manager": "Shared equipment maintenance and supervised lab access",
            "institution_admin": "Institution resource readiness and access oversight",
            "judge_auditor": "Reviewing sample resource decisions and audit history",
        }
        session.add_all(
            AccountProfile(
                user_id=user.id,
                email=f"{key}@example.invalid",
                full_name=user.display_name,
                organization_name="Northstar Engineering Lab (DEMO)",
                intended_use=demo_intents[key],
                email_verified=False,
                is_active=True,
                auth_version=0,
            )
            for key, user in users.items()
        )

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
                max_duration_minutes=round(
                    DEMO_RESOURCE_DETAILS[key]["max_session_hours"] * 60
                ),
                exclusive_booking=True,
                is_demo=True,
                **DEMO_RESOURCE_DETAILS[key],
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
                    "supervisor_required": DEMO_RESOURCE_DETAILS[key][
                        "supervision_required"
                    ],
                    "supervised_windows": DEMO_RESOURCE_DETAILS[key][
                        "supervised_windows"
                    ],
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

        training_samples = [
            (
                SEED_OBJECT_IDS["training:requester-a"],
                "requester_a",
                "OSCILLOSCOPE_SAFETY",
                "valid",
                None,
            ),
            (
                SEED_OBJECT_IDS["training:requester-b"],
                "requester_b",
                "OSCILLOSCOPE_SAFETY",
                "valid",
                None,
            ),
            (
                SEED_OBJECT_IDS["training:sample-01"],
                "requester_a",
                "OSCILLOSCOPE_SAFETY",
                "expired",
                now - timedelta(days=1),
            ),
            (
                SEED_OBJECT_IDS["training:sample-02"],
                "requester_a",
                "LASER_SAFETY",
                "revoked",
                None,
            ),
            (
                SEED_OBJECT_IDS["training:sample-03"],
                "requester_c",
                "LASER_SAFETY",
                "valid",
                now + timedelta(days=7),
            ),
            (
                SEED_OBJECT_IDS["training:sample-04"],
                "requester_c",
                "LASER_SAFETY",
                "expired",
                now - timedelta(days=3),
            ),
            (
                SEED_OBJECT_IDS["training:sample-05"],
                "lab_manager",
                "LAB_SUPERVISOR",
                "valid",
                now + timedelta(days=15),
            ),
            (
                SEED_OBJECT_IDS["training:sample-06"],
                "requester_a",
                "LAB_ACCESS",
                "valid",
                now + timedelta(days=60),
            ),
        ]
        session.add_all(
            TrainingRecord(
                id=training_id,
                user_id=DEMO_USER_IDS[user_key],
                requirement_code=requirement,
                status=status,
                verified_by=DEMO_USER_IDS["lab_manager"],
                valid_from=now - timedelta(days=30),
                valid_to=valid_to,
                is_demo=True,
            )
            for training_id, user_key, requirement, status, valid_to in training_samples
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
        add_request(
            "competing-c", "requester_c", "oscilloscope", "PENDING_REVIEW", day_start, day_end
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
        historical_statuses = ["CLOSED"] * 15 + ["CANCELLED"] * 4 + ["NO_SHOW"] * 4
        historical_rows = []
        historical_resources = ["printer", "camera", "oscilloscope", "bench", "room"]
        for index, booking_status in enumerate(historical_statuses, start=1):
            start = now - timedelta(days=index, hours=index % 7)
            end = start + timedelta(hours=1)
            request_status = (
                "CANCELLED" if booking_status == "CANCELLED"
                else "APPROVED" if booking_status == "NO_SHOW"
                else "CLOSED"
            )
            requester_key = ("requester_a", "requester_b", "requester_c")[
                (index - 1) % 3
            ]
            resource_key = historical_resources[(index - 1) % len(historical_resources)]
            historical_request = ResourceRequest(
                id=SEED_OBJECT_IDS[f"request:history-{index:02d}"],
                requester_id=DEMO_USER_IDS[requester_key],
                resource_id=RESOURCE_IDS[resource_key],
                purpose="coursework",
                start_at=start,
                end_at=end,
                status=request_status,
                created_at=start - timedelta(days=2),
                idempotency_key=None,
                is_demo=True,
            )
            session.add(historical_request)
            historical_rows.append(
                (index, historical_request, booking_status, start, end)
            )
        session.flush()
        session.add_all(
            Booking(
                id=SEED_OBJECT_IDS[f"booking:history-{index:02d}"],
                request_id=historical_request.id,
                start_at=start,
                end_at=end,
                status=booking_status,
                approved_by=DEMO_USER_IDS["lab_manager"],
                version=1,
                is_demo=True,
            )
            for index, historical_request, booking_status, start, end in historical_rows
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
        session.add_all(
            AuditEvent(
                id=SEED_OBJECT_IDS[f"audit:sample-{index:02d}"],
                actor_id=DEMO_USER_IDS[
                    ("lab_manager", "requester_a", "requester_b")[index % 3]
                ],
                entity_type="resource",
                entity_id=RESOURCE_IDS[
                    ("printer", "camera", "oscilloscope", "bench", "room")[index % 5]
                ],
                action=(
                    "resource.sample_condition_checked"
                    if index % 2 == 0
                    else "resource.sample_details_reviewed"
                ),
                timestamp=now - timedelta(days=index),
                request_id=None,
                correlation_id=None,
                before_summary={"sample_data": True},
                after_summary={"reviewed": True, "sample_data": True},
                previous_hash=None,
                hash=None,
                is_demo=True,
            )
            for index in range(2, 13)
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
    session.execute(
        delete(AccountProfile).where(AccountProfile.user_id.in_(DEMO_USER_IDS.values()))
    )
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
