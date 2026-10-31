from datetime import date, datetime, time, timedelta, timezone
import re
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

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
    Organization,
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
ORGANIZATIONS = (
    (
        "northstar",
        ORG_ID,
        "Northstar Engineering Lab (Sample)",
        "Engineering lab",
        "Hyderabad",
        "Gachibowli",
    ),
    (
        "uppal",
        str(uuid5(NAMESPACE, "organization:uppal-circuit-forge")),
        "Uppal Circuit & Fabrication House (Sample)",
        "Makerspace",
        "Hyderabad",
        "Uppal",
    ),
    (
        "bengaluru",
        str(uuid5(NAMESPACE, "organization:bengaluru-vertex-workshop")),
        "Bengaluru Vertex Workshop Collective (Sample)",
        "Innovation workshop",
        "Bengaluru",
        "Electronic City",
    ),
    (
        "chennai",
        str(uuid5(NAMESPACE, "organization:chennai-bluefern-house")),
        "Chennai Bluefern Applied Science House (Sample)",
        "Applied science lab",
        "Chennai",
        "OMR",
    ),
    (
        "pune",
        str(uuid5(NAMESPACE, "organization:pune-copperleaf-yard")),
        "Pune Copperleaf Innovation Yard (Sample)",
        "Innovation lab",
        "Pune",
        "Hinjewadi",
    ),
    (
        "mumbai",
        str(uuid5(NAMESPACE, "organization:mumbai-lanternfish-studio")),
        "Mumbai Lanternfish Prototype Studio (Sample)",
        "Prototype studio",
        "Mumbai",
        "Powai",
    ),
    (
        "noida",
        str(uuid5(NAMESPACE, "organization:noida-copperkite-commons")),
        "Noida Copperkite Engineering Commons (Sample)",
        "Engineering commons",
        "Delhi NCR",
        "Noida",
    ),
    (
        "kolkata",
        str(uuid5(NAMESPACE, "organization:kolkata-monsoon-circuit")),
        "Kolkata Monsoon Circuit Works (Sample)",
        "Electronics workshop",
        "Kolkata",
        "Salt Lake",
    ),
)
ORGANIZATION_IDS = {row[0]: row[1] for row in ORGANIZATIONS}
EXTENDED_USER_SPECS = (
    ("uppal_manager", "Meera Nair", "lab_manager", "uppal", "Fabrication", "Lab Manager"),
    ("uppal_r1", "Aarav Kulkarni", "requester", "uppal", "Mechanical Engineering", "B.Tech Year 2"),
    ("uppal_r2", "Ishita Rao", "requester", "uppal", "Product Design", "B.Des Year 3"),
    ("uppal_r3", "Kabir Menon", "requester", "uppal", "Electronics", "B.Tech Year 4"),
    ("uppal_r4", "Tara Iyer", "requester", "uppal", "Robotics", "B.Tech Year 1"),
    ("bengaluru_manager", "Devika Shetty", "lab_manager", "bengaluru", "Digital Systems", "Lab Manager"),
    ("bengaluru_r1", "Rohan Deshmukh", "requester", "bengaluru", "Computer Engineering", "B.Tech Year 3"),
    ("bengaluru_r2", "Ananya Bose", "requester", "bengaluru", "Product Design", "B.Des Year 2"),
    ("bengaluru_r3", "Vikram Sethi", "requester", "bengaluru", "Mechatronics", "B.Tech Year 4"),
    ("bengaluru_r4", "Nisha Pillai", "requester", "bengaluru", "Computer Science", "M.Tech Year 1"),
    ("chennai_manager", "Arjun Narayanan", "lab_manager", "chennai", "Applied Physics", "Lab Manager"),
    ("chennai_r1", "Kavya Krishnan", "requester", "chennai", "Electronics", "B.E. Year 2"),
    ("chennai_r2", "Aditya Ghosh", "requester", "chennai", "Biomedical Engineering", "B.Tech Year 3"),
    ("chennai_r3", "Sana Qureshi", "requester", "chennai", "Mechanical Engineering", "B.E. Year 4"),
    ("chennai_r4", "Neel Chatterjee", "requester", "chennai", "Media Technology", "B.Sc. Year 2"),
    ("pune_manager", "Pooja Bhat", "lab_manager", "pune", "Prototyping", "Lab Manager"),
    ("pune_r1", "Siddharth Patil", "requester", "pune", "Mechanical Engineering", "B.E. Year 3"),
    ("pune_r2", "Rituja Shah", "requester", "pune", "Industrial Design", "B.Des Year 4"),
    ("pune_r3", "Farhan Shaikh", "requester", "pune", "Electronics", "M.Tech Year 1"),
    ("pune_r4", "Maya Reddy", "requester", "pune", "Energy Systems", "B.Tech Year 2"),
    ("mumbai_manager", "Karan Bhandari", "lab_manager", "mumbai", "Media and Fabrication", "Lab Manager"),
    ("mumbai_r1", "Aditi Venkatesh", "requester", "mumbai", "Electrical Engineering", "B.Tech Year 2"),
    ("mumbai_r2", "Manav Lal", "requester", "mumbai", "Film and Media", "B.A. Year 3"),
    ("mumbai_r3", "Zoya Merchant", "requester", "mumbai", "Robotics", "B.Tech Year 4"),
    ("mumbai_r4", "Pranav Dutta", "requester", "mumbai", "Computer Science", "M.Sc. Year 1"),
    ("noida_manager", "Simran Kaur", "lab_manager", "noida", "Engineering Systems", "Lab Manager"),
    ("noida_r1", "Yash Tiwari", "requester", "noida", "Electronics", "B.Tech Year 2"),
    ("noida_r2", "Diya Mukherjee", "requester", "noida", "Computer Science", "B.Tech Year 3"),
    ("noida_r3", "Harsh Vardhan", "requester", "noida", "Aerospace Engineering", "B.Tech Year 4"),
    ("noida_r4", "Nandini Kapoor", "requester", "noida", "Industrial Design", "B.Des Year 2"),
    ("kolkata_manager", "Sreya Banerjee", "lab_manager", "kolkata", "Electronics", "Lab Manager"),
    ("kolkata_r1", "Ishan Das", "requester", "kolkata", "Electrical Engineering", "B.Tech Year 2"),
    ("kolkata_r2", "Mitali Roy", "requester", "kolkata", "Physics", "M.Sc. Year 1"),
    ("kolkata_r3", "Rahul Sen", "requester", "kolkata", "Mechanical Engineering", "B.E. Year 3"),
)
EXTENDED_USER_IDS = {
    spec[0]: str(uuid5(NAMESPACE, f"user:{spec[0]}")) for spec in EXTENDED_USER_SPECS
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
            for index in range(1, 119)
        },
        **{
            f"booking:history-{index:02d}": str(
                uuid5(NAMESPACE, f"booking:history-{index:02d}")
            )
            for index in range(1, 119)
        },
        **{
            f"training:sample-{index:02d}": str(
                uuid5(NAMESPACE, f"training:sample-{index:02d}")
            )
            for index in range(1, 79)
        },
        **{
            f"audit:sample-{index:02d}": str(
                uuid5(NAMESPACE, f"audit:sample-{index:02d}")
            )
            for index in range(2, 61)
        },
        **{
            f"request:pending-extra-{index:02d}": str(
                uuid5(NAMESPACE, f"request:pending-extra-{index:02d}")
            )
            for index in range(1, 8)
        },
        **{
            f"request:waitlisted-extra-{index:02d}": str(
                uuid5(NAMESPACE, f"request:waitlisted-extra-{index:02d}")
            )
            for index in range(2, 4)
        },
        **{
            f"decision:waitlisted-extra-{index:02d}": str(
                uuid5(NAMESPACE, f"decision:waitlisted-extra-{index:02d}")
            )
            for index in range(2, 4)
        },
        **{
            f"incident:sample-{index:02d}": str(
                uuid5(NAMESPACE, f"incident:sample-{index:02d}")
            )
            for index in range(2, 5)
        },
        **{
            f"handover:sample-{index:02d}-{stage.lower()}": str(
                uuid5(NAMESPACE, f"handover:sample-{index:02d}-{stage.lower()}")
            )
            for index in range(2, 5)
            for stage in ("IN", "OUT")
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
    ("printer", "3D Printer", "fabrication", ["3d printing", "prototyping"], "Fabrication Bay", "active", None, ["3D_PRINTER_OPERATION_3DP_101"]),
    ("camera", "Camera Kit", "media", ["video", "photography"], "Media Store", "active", None, ["MEDIA_KIT_CHECKOUT_MKC_101"]),
    ("oscilloscope", "Oscilloscope Training Station", "electronics", ["oscilloscope", "measurement"], "Electronics Lab", "active", None, ["OSCILLOSCOPE_SAFETY"]),
    ("bench", "Electronics Bench", "electronics", ["soldering", "measurement"], "Electronics Lab", "active", None, ["SOLDERING_SAFETY_SSS_101"]),
    ("room", "Meeting / Project Room", "space", ["teamwork", "project work"], "Uppal Learning Commons", "active", None, ["PROJECT_ROOM_ACCESS_PRA_100"]),
    ("maintenance", "Maintenance Hold Resource", "equipment", ["maintenance demonstration"], "Service Bay", "maintenance_hold", date.today() - timedelta(days=1), ["MACHINE_SAFETY_INSPECTION_MSI_101"]),
)
DEMO_RESOURCE_DETAILS = {
    "printer": {
        "short_summary": "Sample data — enclosed FDM printer for prototypes and fixtures.",
        "description": "Sample data. This fictional enclosed fused-deposition printer supports approved academic prototypes and fixtures. Members use institution-approved filament and record the selected material before a print begins. The lab team checks the nozzle and build plate between sessions.",
        "building": "Northstar Engineering Center",
        "room": "F-104",
        "id_required": "Student ID card or institution letter",
        "address_note": "Use the west entrance and check in at the fabrication desk. Operating hours are local India Standard Time (IST).",
        "capacity": 1,
        "quantity": None,
        "allowed_uses": ["project", "coursework", "research"],
        "who_can_use": ["Northstar students", "Northstar staff", "External startups with an institution letter"],
        "required_training": ["3D Printer Operation 3DP-101"],
        "supervision_required": False,
        "supervised_windows": [],
        "usage_rules": ["Use approved filament only", "Remove completed prints before checkout", "Record the material and print profile before starting", "Keep the enclosure closed during operation"],
        "safety_notes": ["Keep the enclosure closed while printing", "Do not touch the heated bed"],
        "max_session_hours": 4,
        "advance_booking_window": 30,
        "cancellation_cutoff": 2,
        "accessories_included": ["Build plate", "Filament guide"],
        "condition_notes": "Sample data. No damage reported; inspect nozzle and build plate before use.",
    },
    "camera": {
        "short_summary": "Sample data — shared camera and audio kit for project documentation.",
        "description": "Sample data. This fictional camera kit contains a mirrorless body, standard lens, tripod, and basic audio accessories. It is intended for institution projects, coursework, and approved startup documentation. A staff member checks the sealed kit at collection and return.",
        "building": "Northstar Media Annex",
        "room": "M-012",
        "id_required": "Institution ID card",
        "address_note": "Collect and return the sealed kit at the media checkout counter. Operating hours are local India Standard Time (IST).",
        "capacity": None,
        "quantity": 2,
        "allowed_uses": ["project", "coursework", "research"],
        "who_can_use": ["Northstar students", "Northstar staff", "External startups with an institution letter"],
        "required_training": ["Media Kit Checkout MKC-101"],
        "supervision_required": False,
        "supervised_windows": [],
        "usage_rules": ["Return all listed accessories", "Do not leave equipment unattended", "Keep the kit inside its protective case while moving", "Report battery or lens faults at checkout"],
        "safety_notes": ["Use the neck strap while handheld", "Keep equipment dry"],
        "max_session_hours": 8,
        "advance_booking_window": 45,
        "cancellation_cutoff": 4,
        "accessories_included": ["Standard lens", "Tripod", "Microphone", "Battery"],
        "condition_notes": "Sample data. Lenses are clean and the kit is checked at each return.",
    },
    "oscilloscope": {
        "short_summary": "Sample data — supervised electronics measurement station.",
        "description": "Sample data. This fictional oscilloscope bench supports low-voltage electronics measurement and coursework. Users inspect probes and leads before connecting a circuit. A trained lab supervisor remains present throughout each session.",
        "building": "Northstar Engineering Center",
        "room": "E-208",
        "id_required": "Student ID card; staff ID for employees",
        "address_note": "Ask the electronics lab desk to unlock the instrument cabinet. Operating hours are local India Standard Time (IST).",
        "capacity": 1,
        "quantity": None,
        "allowed_uses": ["project", "coursework", "research"],
        "who_can_use": ["Trained Northstar students", "Northstar engineering staff", "External startups with an institution letter"],
        "required_training": ["Oscilloscope Safety OSC-101"],
        "supervision_required": True,
        "supervised_windows": [
            {"weekday": weekday, "start": "00:00", "end": "23:59"}
            for weekday in range(1, 8)
        ],
        "usage_rules": ["Use only within rated input limits", "Return probes to the marked drawer", "Complete the OSC-101 induction before connecting a circuit", "Keep the instrument cabinet locked when unattended"],
        "safety_notes": ["Never connect mains voltage", "Inspect probes before each session"],
        "max_session_hours": 3,
        "advance_booking_window": 21,
        "cancellation_cutoff": 2,
        "accessories_included": ["Passive probes", "Ground leads", "Test leads"],
        "condition_notes": "Sample data. Calibration label is current in this fictional demo.",
    },
    "bench": {
        "short_summary": "Sample data — shared electronics bench for low-voltage assembly.",
        "description": "Sample data. This fictional ESD-protected bench provides soldering and measurement tools for approved low-voltage work. Users operate the fume extractor and return hand tools to the shadow board. Staff inspect the bench after each session.",
        "building": "Northstar Engineering Center",
        "room": "E-204",
        "id_required": "Student ID card or institution letter",
        "address_note": "Use the marked ESD station and return tools to the shadow board. Operating hours are local India Standard Time (IST).",
        "capacity": 1,
        "quantity": None,
        "allowed_uses": ["project", "coursework", "research"],
        "who_can_use": ["Northstar students", "Northstar staff", "External startups with an institution letter"],
        "required_training": ["Soldering Safety SSS-101"],
        "supervision_required": False,
        "supervised_windows": [],
        "usage_rules": ["Use the fume extractor when soldering", "Leave the bench clear", "Complete the SSS-101 induction before using the iron", "Disconnect and cool tools before storage"],
        "safety_notes": ["Wear eye protection", "Do not work on energized circuits"],
        "max_session_hours": 4,
        "advance_booking_window": 30,
        "cancellation_cutoff": 2,
        "accessories_included": ["Soldering station", "ESD mat", "Hand tools"],
        "condition_notes": "Sample data. Fume extractor and ESD mat passed the fictional daily check.",
    },
    "room": {
        "short_summary": "Sample data — bookable project room for small working groups.",
        "description": "Sample data. This fictional collaborative room supports project meetings, design reviews, and coursework planning. Teams can use the display and whiteboard for shared work. Users leave the furniture and surfaces ready for the next group.",
        "building": "Uppal Learning Commons",
        "room": "L-301",
        "id_required": "Institution ID card",
        "address_note": "Room is on the third floor beside the project studios in Uppal. Operating hours are local India Standard Time (IST).",
        "capacity": 8,
        "quantity": None,
        "allowed_uses": ["project", "coursework", "research"],
        "who_can_use": ["Uppal institution students", "Uppal institution staff", "External startups with an institution letter"],
        "required_training": ["Project Room Access PRA-100"],
        "supervision_required": False,
        "supervised_windows": [],
        "usage_rules": ["Leave the room ready for the next group", "Keep discussions at a considerate volume", "Complete PRA-100 orientation before first use", "Return the display remote and speaker to the marked shelf"],
        "safety_notes": ["Keep the exit clear", "Report damaged furniture to the desk"],
        "max_session_hours": 4,
        "advance_booking_window": 60,
        "cancellation_cutoff": 1,
        "accessories_included": ["Display", "Whiteboard", "Conference speaker"],
        "condition_notes": "Sample data. Furniture and display are in serviceable condition.",
    },
    "maintenance": {
        "short_summary": "Sample data — equipment temporarily held for a scheduled inspection.",
        "description": "Sample data. This fictional demonstration resource is unavailable while a safety inspection is reviewed. A service note records the inspection concern and the next review date. The hold remains in place until an authorized manager clears it.",
        "building": "Northstar Engineering Center",
        "room": "S-001",
        "id_required": "Staff ID or institution letter",
        "address_note": "Not available for collection while the hold is active. Operating hours are local India Standard Time (IST).",
        "capacity": 1,
        "quantity": None,
        "allowed_uses": ["project", "coursework", "research"],
        "who_can_use": ["Northstar students", "Northstar staff", "External startups with an institution letter"],
        "required_training": ["Machine Safety Inspection MSI-101"],
        "supervision_required": False,
        "supervised_windows": [],
        "usage_rules": ["Do not reserve or operate while on hold", "Contact the lab manager for a status update", "Keep the marked inspection area clear", "Resume use only after an authorized manager clears the hold"],
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
        if has_existing_data:
            if not force:
                return
            reset_demo_data(session)

        password_hash = hash_password(demo_password)
        session.add_all(
            Organization(
                id=organization_id,
                name=name,
                type=organization_type,
                city=city,
                area=area,
                is_demo=True,
            )
            for _key, organization_id, name, organization_type, city, area in ORGANIZATIONS
        )
        users = {
            key: User(
                id=DEMO_USER_IDS[key],
                display_name=label,
                role=role,
                organization_id=ORG_ID,
                department={
                    "requester_a": "Mechanical Engineering",
                    "requester_b": "Electronics",
                    "requester_c": "Computer Engineering",
                    "lab_manager": "Fabrication",
                    "institution_admin": "Institution Administration",
                    "judge_auditor": "Independent Review",
                }[key],
                designation={
                    "requester_a": "B.Tech Year 3",
                    "requester_b": "B.Tech Year 2",
                    "requester_c": "M.Tech Year 1",
                    "lab_manager": "Lab Manager",
                    "institution_admin": "Institution Administrator",
                    "judge_auditor": "Judge Auditor",
                }[key],
                is_demo=True,
                password_hash=password_hash,
            )
            for key, label, role in DEMO_USERS
        }
        users["uppal_manager"] = User(
            id=EXTENDED_USER_IDS["uppal_manager"],
            display_name="Meera Nair",
            role="lab_manager",
            organization_id=ORGANIZATION_IDS["uppal"],
            department="Fabrication",
            designation="Lab Manager",
            is_demo=True,
            password_hash=password_hash,
        )
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
                owner_id=(
                    EXTENDED_USER_IDS["uppal_manager"]
                    if key == "room"
                    else DEMO_USER_IDS["lab_manager"]
                ),
                name=name,
                category=category,
                capability_tags=tags,
                location=location,
                city="Hyderabad",
                area="Uppal" if key == "room" else "Gachibowli",
                status=status,
                hold_review_date=hold_date,
                weekly_operating_hours=open_hours,
                max_duration_minutes=round(
                    DEMO_RESOURCE_DETAILS[key]["max_session_hours"] * 60
                ),
                exclusive_booking=True,
                access_model="free for members; no payments are processed",
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
                approved_by=resource.owner_id,
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
        session.flush()
        _seed_extended_demo_data(
            session,
            now,
            resources,
            policies,
            users,
            password_hash,
        )
        session.commit()


def _seed_extended_demo_data(
    session: Session,
    now: datetime,
    resources: dict[str, Resource],
    policies: dict[str, ResourcePolicy],
    users: dict[str, User],
    password_hash: str,
) -> None:
    organization_rows = {row[0]: row for row in ORGANIZATIONS}
    manager_keys = {"northstar": "lab_manager"}
    requester_keys: dict[str, list[str]] = {
        "northstar": ["requester_a", "requester_b", "requester_c"]
    }
    extended_users: dict[str, User] = {}
    for key, name, role, organization_key, department, designation in EXTENDED_USER_SPECS:
        user = users.get(key) or User(
            id=EXTENDED_USER_IDS[key],
            display_name=name,
            role=role,
            organization_id=ORGANIZATION_IDS[organization_key],
            department=department,
            designation=designation,
            is_demo=True,
            password_hash=password_hash,
        )
        extended_users[key] = user
        if role == "lab_manager":
            manager_keys[organization_key] = key
        else:
            requester_keys.setdefault(organization_key, []).append(key)
    session.add_all(extended_users.values())
    session.flush()

    course_by_key = {
        "laser": "Laser Safety Induction LSI-101",
        "laser_noida": "Laser Marking Safety LMI-102",
        "cnc": "CNC Router Operation CRO-201",
        "rework": "Soldering and Rework Safety SRS-110",
        "gpu": "GPU Cluster Access GCA-101",
        "pcb": "PCB Prototyping Safety PPS-120",
        "pcb_kolkata": "PCB Prototyping Safety PPS-120",
        "vr": "VR Studio Orientation VSO-105",
        "microscope": "Fluorescence Microscope Handling FMH-101",
        "utm": "Universal Testing Machine Safety UTM-101",
        "solar": "Solar Bench Electrical Safety SBES-102",
        "scanner": "3D Scanner Orientation 3DS-101",
        "wind": "Wind Tunnel Tabletop Safety WTS-108",
        "wind_kolkata": "Wind Tunnel Demonstration Safety WTD-101",
        "library": "Electronics Component Library Induction ECLI-100",
        "podcast": "Podcast Studio Orientation PSO-103",
        "seminar": "Seminar Hall Equipment Induction SHE-100",
        "drone": "Drone Cage Safety DCS-101",
        "scope": "Oscilloscope Safety OSC-101",
        "printer_farm": "3D Printer Farm Operation 3DP-101",
        "project_room": "Project Room Access PRA-100",
    }
    id_required_by_key = {
        "laser": "Student ID card and institution letter for external startups",
        "cnc": "Student ID card or staff ID",
        "rework": "Student ID card; staff ID for employees",
        "gpu": "Institution ID card or approved startup institution letter",
        "pcb": "Student ID card or staff ID",
        "vr": "Institution ID card",
        "microscope": "Student ID card and verified training record",
        "utm": "Staff ID or student ID with supervisor approval",
        "solar": "Student ID card or institution letter",
        "scanner": "Institution ID card",
        "wind": "Student ID card",
        "library": "Student ID card or staff ID",
        "podcast": "Institution ID card or startup institution letter",
        "seminar": "Staff ID or institution event letter",
        "drone": "Student ID card and drone cage induction record",
        "laser_noida": "Student ID card or approved institution letter",
        "project_room": "Institution ID card",
        "scope": "Student ID card and OSC-101 training record",
        "pcb_kolkata": "Student ID card or staff ID",
        "printer_farm": "Institution ID card and 3DP-101 training record",
        "wind_kolkata": "Student ID card or staff ID",
    }
    resource_specs = (
        ("uppal", "laser", "CO2 Laser Cutter", "laser cutting", ["laser", "sheet cutting"], "Uppal Fabrication Block", "F-12", "Cuts approved sheet stock for fixtures and enclosure panels.", "active", None, None),
        ("uppal", "cnc", "CNC Router", "cnc machining", ["cnc", "wood", "plastic"], "Uppal Fabrication Block", "F-14", "Machines wood and approved plastics into flat prototype components.", "active", None, None),
        ("uppal", "rework", "Soldering and Rework Station", "electronics", ["soldering", "rework"], "Uppal Electronics Wing", "E-03", "Supports through-hole assembly, hot-air rework, and low-voltage prototype repair.", "active", None, None),
        ("bengaluru", "gpu", "GPU Workstation", "compute", ["gpu", "machine learning", "rendering"], "Vertex Computing Studio", "C-08", "Provides reserved GPU time for student projects, simulations, and approved startup prototypes.", "active", None, None),
        ("bengaluru", "pcb", "PCB Prototyping Station", "electronics", ["pcb", "prototyping"], "Vertex Electronics Lab", "E-21", "Supports small-batch board milling, drilling, and inspection for low-voltage circuits.", "active", None, None),
        ("bengaluru", "vr", "VR and AR Studio", "immersive media", ["vr", "ar", "spatial design"], "Vertex Media Studio", "M-05", "Provides a tracked room and headsets for interactive learning and product visualization.", "active", None, None),
        ("chennai", "microscope", "Fluorescence Microscope", "microscopy", ["fluorescence", "imaging"], "Bluefern Life Sciences Block", "L-11", "Supports supervised fluorescence imaging of prepared samples for teaching and research.", "maintenance_hold", "The illumination module is awaiting a replacement filter.", date.today() + timedelta(days=10)),
        ("chennai", "utm", "Mechanical Testing Machine (UTM)", "mechanical testing", ["utm", "materials"], "Bluefern Materials Lab", "M-07", "Measures tensile and compression behavior of approved material coupons.", "active", None, None),
        ("chennai", "solar", "Solar Test Bench", "energy", ["solar", "photovoltaics"], "Bluefern Energy Terrace", "S-02", "Compares small photovoltaic modules under a calibrated indoor lamp and outdoor reference readings.", "active", None, None),
        ("pune", "scanner", "3D Scanner", "3d scanning", ["3d scan", "reverse engineering"], "Copperleaf Design Hall", "D-16", "Captures non-sensitive object geometry for inspection and digital fabrication workflows.", "active", None, None),
        ("pune", "wind", "Wind-Tunnel Tabletop Unit", "fluid dynamics", ["wind tunnel", "aerodynamics"], "Copperleaf Applied Mechanics Lab", "A-04", "Demonstrates airflow behavior around small models with a guarded tabletop tunnel.", "active", None, None),
        ("pune", "library", "Electronics Component Library", "electronics library", ["components", "inventory"], "Copperleaf Electronics Library", "E-02", "Provides supervised checkout of labeled passive, analog, and microcontroller components.", "active", None, None),
        ("mumbai", "podcast", "Podcast and Video Studio", "media production", ["podcast", "video", "audio"], "Lanternfish Media Wing", "V-09", "Provides an acoustically treated room for interviews, demonstrations, and project videos.", "active", None, None),
        ("mumbai", "seminar", "Seminar Hall", "learning space", ["seminar", "presentation"], "Lanternfish Commons", "H-01", "Hosts project reviews, workshops, and small public-interest technology sessions.", "active", None, None),
        ("mumbai", "drone", "Drone Flight Cage", "aerial robotics", ["drone", "robotics"], "Lanternfish Robotics Annex", "R-03", "Provides an enclosed netted area for low-speed indoor flight testing and control practice.", "maintenance_hold", "A net panel needs inspection after a routine facilities check.", date.today() + timedelta(days=21)),
        ("noida", "laser_noida", "Fiber Laser Marking Unit", "laser cutting", ["laser", "marking", "engraving"], "Copperkite Fabrication Wing", "F-06", "Marks approved metal and polymer coupons for traceable engineering prototypes.", "active", None, None),
        ("noida", "project_room", "Project Room", "learning space", ["teamwork", "project"], "Copperkite Commons", "P-10", "Provides a reservable room for design reviews, team planning, and collaborative coursework.", "active", None, None),
        ("noida", "scope", "Oscilloscope and Spectrum Analyser Bench", "electrical testing", ["oscilloscope", "spectrum analyser"], "Copperkite Instrument Lab", "I-12", "Supports supervised signal measurement and low-voltage RF characterization.", "active", None, None),
        ("kolkata", "pcb_kolkata", "PCB Prototyping Station", "electronics", ["pcb", "prototyping"], "Monsoon Electronics Block", "E-15", "Supports single-sided board preparation, drilling, and visual inspection for coursework.", "active", None, None),
        ("kolkata", "printer_farm", "3D Printer Farm", "fabrication", ["3d printing", "prototyping"], "Monsoon Fabrication Studio", "F-08", "Provides a small supervised bank of enclosed FDM printers for fixtures and demonstrator parts.", "active", None, None),
        ("kolkata", "wind_kolkata", "Wind-Tunnel Demonstration Table", "fluid dynamics", ["wind tunnel", "demonstration"], "Monsoon Applied Science Lab", "A-02", "Demonstrates airflow and drag using small models and a guarded tabletop fan unit.", "active", None, None),
    )
    training_code_by_key: dict[str, str] = {}
    organization_key_by_id = {
        organization_id: key for key, organization_id in ORGANIZATION_IDS.items()
    }
    resource_organizations = {
        key: organization_key_by_id[resource.owner.organization_id]
        for key, resource in resources.items()
    }
    extra_resource_rows: list[Resource] = []
    extra_policy_rows: list[ResourcePolicy] = []
    supervised_windows = [
        {"weekday": weekday, "start": "09:00", "end": "17:00"}
        for weekday in range(1, 7)
    ]
    operating_hours = [
        {"weekday": weekday, "start": "09:00", "end": "18:00"}
        for weekday in range(1, 7)
    ]
    access_models = (
        "free for members; no payments are processed",
        "sponsored access; no payments are processed",
        "credit-based access display only; no payments are processed",
    )
    for index, spec in enumerate(resource_specs):
        (
            organization_key,
            key,
            name,
            category,
            tags,
            building,
            room,
            purpose,
            status,
            hold_reason,
            hold_review_date,
        ) = spec
        _org_key, org_id, org_name, _org_type, city, area = organization_rows[organization_key]
        manager_key = manager_keys[organization_key]
        course = course_by_key[key]
        code = re.sub(r"[^A-Z0-9]+", "_", course.upper()).strip("_")[:100]
        training_code_by_key[key] = code
        supervised = key not in {"gpu", "vr", "library", "podcast", "seminar", "project_room"}
        resource_id = str(uuid5(NAMESPACE, f"resource:{key}"))
        owner_id = (
            DEMO_USER_IDS[manager_key]
            if manager_key in DEMO_USER_IDS
            else EXTENDED_USER_IDS[manager_key]
        )
        description = (
            f"This fictional {name.lower()} supports {purpose.lower()} "
            f"at {org_name.replace(' (Sample)', '')}. "
            "Users follow the posted operating procedure and record any setup changes before the session. "
            "Institution staff inspect the equipment and shared accessories between bookings."
        )
        detail = Resource(
            id=resource_id,
            owner_id=owner_id,
            name=name,
            category=category,
            short_summary=f"Sample data — {purpose}",
            description=description,
            capability_tags=tags,
            location=f"{building}, Room {room}",
            city=city,
            area=area,
            id_required=id_required_by_key[key],
            building=building,
            room=room,
            address_note=(
                f"{area}, {city}; check in at the {building} reception desk. "
                "Operating hours are local India Standard Time (IST)."
            ),
            status=status,
            hold_reason=hold_reason,
            hold_review_date=hold_review_date,
            weekly_operating_hours=operating_hours,
            capacity=1,
            quantity=None,
            allowed_uses=["project", "coursework", "research"],
            who_can_use=[
                f"{org_name} students",
                f"{org_name} staff",
                "External startups with an institution letter",
            ],
            required_training=[course],
            supervision_required=supervised,
            supervised_windows=supervised_windows if supervised else [],
            usage_rules=[
                "Use the equipment only for the approved booking purpose.",
                "Complete the named induction before operating the equipment.",
                "Keep the work area clear and return shared accessories after use.",
                "Record faults or incomplete kits with the lab manager before checkout.",
            ],
            safety_notes=[
                "Follow posted isolation, guarding, and personal protective equipment instructions.",
                "Stop work and notify the lab manager if a safety control or instrument behaves unexpectedly.",
                "Do not bypass interlocks or use equipment outside its stated rating.",
            ],
            max_session_hours=4,
            advance_booking_window=30,
            cancellation_cutoff=2,
            accessories_included=["Operating guide", "Standard fixture set", "Checkout checklist"],
            condition_notes=(
                "Sample data. Routine inspection is recorded; report any change in condition at check-in."
                if status == "active"
                else f"Sample data. {hold_reason} Review date: {hold_review_date.isoformat()}."
            ),
            max_duration_minutes=240,
            exclusive_booking=True,
            access_model=access_models[index % len(access_models)],
            is_demo=True,
        )
        extra_resource_rows.append(detail)
        resource_organizations[key] = organization_key
        policy_id = str(uuid5(NAMESPACE, f"policy:{key}"))
        policy = ResourcePolicy(
            id=policy_id,
            resource_id=resource_id,
            version=1,
            structured_requirements={
                "training_codes": [code],
                "supervisor_required": supervised,
                "supervised_windows": supervised_windows if supervised else [],
            },
            allowed_uses=["project", "coursework", "research"],
            priority_policy={},
            effective_at=now,
            approved_by=detail.owner_id,
            activation_reason="Initial fictional sample policy activation.",
            is_demo=True,
        )
        extra_policy_rows.append(policy)
        resources[key] = detail
        policies[key] = policy

    session.add_all(extra_resource_rows)
    session.flush()
    session.add_all(extra_policy_rows)
    session.flush()

    all_users = {**users, **extended_users}
    all_requesters = [
        key
        for key, person in all_users.items()
        if person.role == "requester"
    ]
    base_training_codes = (
        "3D_PRINTER_OPERATION_3DP_101",
        "MEDIA_KIT_CHECKOUT_MKC_101",
        "SOLDERING_SAFETY_SSS_101",
        "PROJECT_ROOM_ACCESS_PRA_100",
    )
    session.add_all(
        TrainingRecord(
            id=SEED_OBJECT_IDS[f"training:sample-{index:02d}"],
            user_id=all_users[user_key].id,
            requirement_code=code,
            status="valid",
            verified_by=DEMO_USER_IDS["lab_manager"],
            valid_from=now - timedelta(days=30),
            valid_to=now + timedelta(days=180),
            is_demo=True,
        )
        for index, (user_key, code) in enumerate(
            (
                (requester_key, code)
                for requester_key in ("requester_a", "requester_b", "requester_c")
                for code in base_training_codes
            ),
            start=7,
        )
    )
    all_training_codes = list(dict.fromkeys((*base_training_codes, *training_code_by_key.values())))
    training_statuses = ("valid", "valid", "expired", "revoked")
    extra_training = []
    for index in range(19, 79):
        user_key = all_requesters[(index - 19) % len(all_requesters)]
        organization_key = next(
            key for key in ORGANIZATION_IDS
            if ORGANIZATION_IDS[key] == all_users[user_key].organization_id
        )
        verified_by_key = manager_keys[organization_key]
        verified_by = (
            DEMO_USER_IDS[verified_by_key]
            if verified_by_key in DEMO_USER_IDS
            else EXTENDED_USER_IDS[verified_by_key]
        )
        status = training_statuses[(index - 19) % len(training_statuses)]
        if status == "expired":
            valid_to = now - timedelta(days=1 + index % 20)
        elif status == "revoked":
            valid_to = None
        elif organization_key == "northstar":
            valid_to = now + timedelta(days=180)
        elif index % 5 == 0:
            valid_to = now + timedelta(days=1 + index % 25)
        else:
            valid_to = now + timedelta(days=180)
        extra_training.append(
            TrainingRecord(
                id=SEED_OBJECT_IDS[f"training:sample-{index:02d}"],
                user_id=all_users[user_key].id,
                requirement_code=all_training_codes[(index - 19) % len(all_training_codes)],
                status=status,
                verified_by=verified_by,
                valid_from=now - timedelta(days=90),
                valid_to=valid_to,
                is_demo=True,
            )
        )
    session.add_all(extra_training)
    session.flush()

    resource_keys = list(resources)
    history_rows: list[tuple[int, ResourceRequest, Booking, str, datetime, datetime]] = []
    incident_categories = {24: "missing_part", 25: "malfunction", 26: "late_return"}
    incident_resources = {24: "microscope", 25: "utm", 26: "drone"}

    def history_resource_key(index: int) -> str:
        return incident_resources.get(
            index, resource_keys[(index - 24) % len(resource_keys)]
        )

    for index in range(24, 119):
        resource_key = history_resource_key(index)
        organization_key = resource_organizations.get(resource_key, "northstar")
        organization_requesters = requester_keys[organization_key]
        requester_key = organization_requesters[
            (index - 24) % len(organization_requesters)
        ]
        days_ago = ((index - 24) % 29) + 1
        local_now = now.astimezone(ZoneInfo("Asia/Kolkata"))
        local_start = (local_now - timedelta(days=days_ago)).replace(
            hour=9 + (index % 8),
            minute=0,
            second=0,
            microsecond=0,
        )
        start = local_start.astimezone(timezone.utc)
        end = start + timedelta(hours=1)
        if index in incident_categories:
            booking_status = "INCIDENT_REVIEW"
        elif index % 5 == 0:
            booking_status = "CANCELLED"
        elif index % 6 == 0:
            booking_status = "NO_SHOW"
        else:
            booking_status = "CLOSED"
        request_status = {
            "CLOSED": "CLOSED",
            "CANCELLED": "CANCELLED",
            "NO_SHOW": "APPROVED",
            "INCIDENT_REVIEW": "INCIDENT_REVIEW",
        }[booking_status]
        request_id = SEED_OBJECT_IDS[f"request:history-{index:02d}"]
        row = ResourceRequest(
            id=request_id,
            requester_id=all_users[requester_key].id,
            resource_id=resources[resource_key].id,
            purpose="coursework",
            start_at=start,
            end_at=end,
            status=request_status,
            created_at=start - timedelta(days=4),
            idempotency_key=None,
            is_demo=True,
        )
        session.add(row)
        history_rows.append((index, row, None, booking_status, start, end))
    session.flush()
    finalized_history: list[tuple[int, ResourceRequest, Booking, str, datetime, datetime]] = []
    for index, request_row, _booking, booking_status, start, end in history_rows:
        resource_key = history_resource_key(index)
        organization_key = resource_organizations.get(resource_key, "northstar")
        manager_key = manager_keys[organization_key]
        manager_id = (
            DEMO_USER_IDS[manager_key]
            if manager_key in DEMO_USER_IDS
            else EXTENDED_USER_IDS[manager_key]
        )
        booking = Booking(
            id=SEED_OBJECT_IDS[f"booking:history-{index:02d}"],
            request_id=request_row.id,
            start_at=start,
            end_at=end,
            status=booking_status,
            approved_by=manager_id,
            version=1,
            is_demo=True,
        )
        session.add(booking)
        finalized_history.append(
            (index, request_row, booking, booking_status, start, end)
        )
    session.flush()

    good_condition = {
        "physical_condition": "ok",
        "accessories_complete": "yes",
        "functional_test": "works",
        "notes": None,
    }
    for index, request_row, booking, _status, start, end in finalized_history:
        category = incident_categories.get(index)
        if category is None:
            continue
        details = {
            "missing_part": (
                "A listed adapter was absent at return; the checkout list is under review.",
                {"physical_condition": "ok", "accessories_complete": "no", "functional_test": "works", "notes": "Synthetic missing-part report for review."},
            ),
            "malfunction": (
                "The instrument reported an intermittent fault during the final check.",
                {"physical_condition": "ok", "accessories_complete": "yes", "functional_test": "issue", "notes": "Synthetic malfunction report for review."},
            ),
            "late_return": (
                "The kit was returned after the reserved end time; no blame is assigned.",
                {"physical_condition": "ok", "accessories_complete": "yes", "functional_test": "works", "notes": "Synthetic late-return report for review."},
            ),
        }[category]
        for stage, condition, created_at in (
            ("IN", good_condition, start),
            (
                "OUT",
                details[1],
                end + timedelta(minutes=20) if category == "late_return" else end,
            ),
        ):
            session.add(
                HandoverReport(
                    id=SEED_OBJECT_IDS[f"handover:sample-{index - 22:02d}-{stage.lower()}"],
                    booking_id=booking.id,
                    stage=stage,
                    checklist_version="northstar-condition-v1",
                    condition=condition,
                    notes=condition.get("notes"),
                    evidence_references=[],
                    actor_id=request_row.requester_id,
                    created_at=created_at,
                    idempotency_key=None,
                    is_demo=True,
                )
            )
        session.add(
            Incident(
                id=SEED_OBJECT_IDS[f"incident:sample-{index - 22:02d}"],
                booking_id=booking.id,
                reporter_id=request_row.requester_id,
                category=category,
                description=details[0],
                status="UNDER_REVIEW",
                responses=[],
                resolution=None,
                reviewer_id=None,
                created_at=end + (timedelta(minutes=20) if category == "late_return" else timedelta(0)),
                updated_at=end + (timedelta(minutes=20) if category == "late_return" else timedelta(0)),
                is_demo=True,
            )
        )

    pending_resource_keys = [
        "laser", "gpu", "cnc", "pcb", "solar", "scanner", "scope"
    ]
    for index, resource_key in enumerate(pending_resource_keys, start=1):
        organization_key = resource_organizations[resource_key]
        requester_key = requester_keys[organization_key][index % len(requester_keys[organization_key])]
        start = now + timedelta(days=5 + index, hours=2)
        resource = resources[resource_key]
        session.add(
            ResourceRequest(
                id=SEED_OBJECT_IDS[f"request:pending-extra-{index:02d}"],
                requester_id=all_users[requester_key].id,
                resource_id=resource.id,
                purpose="research",
                start_at=start,
                end_at=start + timedelta(hours=1),
                status="PENDING_REVIEW",
                created_at=now - timedelta(hours=index),
                idempotency_key=None,
                is_demo=True,
            )
        )

    for index, requester_key, organization_key, resource_key in (
        (2, "bengaluru_r1", "bengaluru", "gpu"),
        (3, "uppal_r2", "uppal", "laser"),
    ):
        start = now + timedelta(days=8, hours=3)
        request_row = ResourceRequest(
            id=SEED_OBJECT_IDS[f"request:waitlisted-extra-{index:02d}"],
            requester_id=all_users[requester_key].id,
            resource_id=resources[resource_key].id,
            purpose="project",
            start_at=start,
            end_at=start + timedelta(hours=1),
            status="WAITLISTED",
            created_at=now - timedelta(minutes=10 * index),
            idempotency_key=None,
            is_demo=True,
        )
        session.add(request_row)
        manager_key = manager_keys[organization_key]
        manager_id = (
            DEMO_USER_IDS[manager_key]
            if manager_key in DEMO_USER_IDS
            else EXTENDED_USER_IDS[manager_key]
        )
        session.add(
            AllocationDecision(
                id=SEED_OBJECT_IDS[f"decision:waitlisted-extra-{index:02d}"],
                request_id=request_row.id,
                decision_sequence=1,
                policy_version=policies[resource_key].id,
                outcome="waitlisted",
                explanation_code="capacity_waitlist",
                explanation=(
                    "DEMO DATA — this high-demand slot is full; the request is "
                    "waitlisted pending cancellation or manager review."
                ),
                inputs_snapshot={
                    "demo_data": True,
                    "resource_name": resources[resource_key].name,
                    "algorithm_version": "1",
                },
                reviewer_override=None,
                reviewer_id=manager_id,
                created_at=now - timedelta(minutes=10 * index),
                is_demo=True,
            )
        )

    session.flush()
    held_rows = [
        row for row in extra_resource_rows if row.status == "maintenance_hold"
    ]
    for index, resource in enumerate(held_rows, start=13):
        manager_id = resource.owner_id
        session.add(
            AuditEvent(
                id=SEED_OBJECT_IDS[f"audit:sample-{index:02d}"],
                actor_id=manager_id,
                entity_type="resource",
                entity_id=resource.id,
                action="resource.maintenance_hold_set",
                timestamp=now - timedelta(days=3),
                request_id=None,
                correlation_id=None,
                before_summary={"status": "active"},
                after_summary={
                    "status": "maintenance_hold",
                    "reason": resource.hold_reason,
                    "review_date": resource.hold_review_date.isoformat(),
                    "demo_data": True,
                },
                previous_hash=None,
                hash=None,
                is_demo=True,
            )
        )
    for offset, (index, request_row, booking, status, start, end) in enumerate(
        finalized_history[:46],
        start=15,
    ):
        resource_key = history_resource_key(index)
        organization_key = resource_organizations.get(resource_key, "northstar")
        manager_key = manager_keys[organization_key]
        manager_id = (
            DEMO_USER_IDS[manager_key]
            if manager_key in DEMO_USER_IDS
            else EXTENDED_USER_IDS[manager_key]
        )
        action, entity_type, entity_id = {
            "CLOSED": ("booking.closed", "booking", booking.id),
            "CANCELLED": ("request.cancelled", "request", request_row.id),
            "NO_SHOW": ("booking.no_show", "booking", booking.id),
            "INCIDENT_REVIEW": ("booking.incident_review_opened", "booking", booking.id),
        }[status]
        session.add(
            AuditEvent(
                id=SEED_OBJECT_IDS[f"audit:sample-{offset:02d}"],
                actor_id=manager_id,
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                timestamp=end,
                request_id=None,
                correlation_id=None,
                before_summary={"status": "CONFIRMED"},
                after_summary={"status": status, "demo_data": True},
                previous_hash=None,
                hash=None,
                is_demo=True,
            )
        )


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
        Organization,
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
