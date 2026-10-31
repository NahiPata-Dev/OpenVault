from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("organization_id", "display_name"),
        Index("ix_users_organization_role", "organization_id", "role"),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(120), nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)

    resources: Mapped[list["Resource"]] = relationship(
        back_populates="owner", foreign_keys="Resource.owner_id"
    )
    training_records: Mapped[list["TrainingRecord"]] = relationship(
        back_populates="user", foreign_keys="TrainingRecord.user_id"
    )
    requests: Mapped[list["ResourceRequest"]] = relationship(
        back_populates="requester", foreign_keys="ResourceRequest.requester_id"
    )
    notifications: Mapped[list["Notification"]] = relationship(back_populates="recipient")


class AccountProfile(Base):
    __tablename__ = "account_profiles"
    __table_args__ = (
        UniqueConstraint("email"),
        Index("ix_account_profiles_active", "is_active"),
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    organization_name: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(40))
    intended_use: Mapped[str | None] = mapped_column(Text)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    auth_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class OwnerApplication(Base):
    __tablename__ = "owner_applications"
    __table_args__ = (
        Index("ix_owner_applications_status_created", "status", "created_at"),
        Index("ix_owner_applications_applicant_created", "applicant_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    applicant_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    organization: Mapped[str] = mapped_column(String(200), nullable=False)
    role_in_organization: Mapped[str] = mapped_column(String(160), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    resources_to_list: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    decision_reason: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    __table_args__ = (
        Index("ix_login_attempts_account_time", "account_key", "failed_at"),
        Index("ix_login_attempts_ip_time", "ip_key", "failed_at"),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    account_key: Mapped[str] = mapped_column(String(64), nullable=False)
    ip_key: Mapped[str] = mapped_column(String(64), nullable=False)
    failed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DiscoveryFeedback(Base):
    __tablename__ = "discovery_feedback"
    __table_args__ = (Index("ix_discovery_feedback_user_created", "user_id", "created_at"),)

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    is_helpful: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Resource(Base):
    __tablename__ = "resources"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'maintenance_hold', 'retired')",
            name="ck_resources_status",
        ),
        CheckConstraint(
            "status != 'maintenance_hold' OR hold_review_date IS NOT NULL",
            name="ck_resources_hold_review_date",
        ),
        CheckConstraint(
            "max_duration_minutes IS NULL OR max_duration_minutes > 0",
            name="ck_resources_positive_max_duration",
        ),
        Index("ix_resources_category_status", "category", "status"),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    short_summary: Mapped[str] = mapped_column(String(400), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    capability_tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    location: Mapped[str] = mapped_column(String(160), nullable=False)
    building: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    room: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    address_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    hold_reason: Mapped[str | None] = mapped_column(Text)
    hold_review_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    weekly_operating_hours: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    capacity: Mapped[int | None] = mapped_column(Integer)
    quantity: Mapped[int | None] = mapped_column(Integer)
    allowed_uses: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    who_can_use: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    required_training: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    supervision_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    supervised_windows: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    usage_rules: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    safety_notes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    max_session_hours: Mapped[float | None] = mapped_column(Float)
    advance_booking_window: Mapped[int | None] = mapped_column(Integer)
    cancellation_cutoff: Mapped[float] = mapped_column(Float, nullable=False, default=2)
    accessories_included: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    condition_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    max_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exclusive_booking: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    owner: Mapped[User] = relationship(back_populates="resources", foreign_keys=[owner_id])
    policies: Mapped[list["ResourcePolicy"]] = relationship(back_populates="resource")
    requests: Mapped[list["ResourceRequest"]] = relationship(back_populates="resource")


class ResourcePolicy(Base):
    __tablename__ = "resource_policies"
    __table_args__ = (
        UniqueConstraint("resource_id", "version"),
        Index("ix_resource_policies_effective", "resource_id", "effective_at"),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    structured_requirements: Mapped[dict] = mapped_column(JSON, nullable=False)
    allowed_uses: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    priority_policy: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    activation_reason: Mapped[str | None] = mapped_column(Text)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    resource: Mapped[Resource] = relationship(back_populates="policies")


class TrainingRecord(Base):
    __tablename__ = "training_records"
    __table_args__ = (
        Index(
            "ix_training_user_requirement_status_validity",
            "user_id",
            "requirement_code",
            "status",
            "valid_to",
        ),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    requirement_code: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    verified_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    user: Mapped[User] = relationship(
        back_populates="training_records", foreign_keys=[user_id]
    )


class ResourceRequest(Base):
    __tablename__ = "resource_requests"
    __table_args__ = (
        UniqueConstraint("requester_id", "idempotency_key"),
        Index("ix_requests_resource_interval_status", "resource_id", "start_at", "end_at", "status"),
        Index("ix_requests_requester_created", "requester_id", "created_at"),
        CheckConstraint("end_at > start_at", name="ck_requests_valid_interval"),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    requester_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id"), nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(160))
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    requester: Mapped[User] = relationship(back_populates="requests", foreign_keys=[requester_id])
    resource: Mapped[Resource] = relationship(back_populates="requests")
    decisions: Mapped[list["AllocationDecision"]] = relationship(back_populates="request")
    booking: Mapped["Booking | None"] = relationship(back_populates="request", uselist=False)


class AllocationDecision(Base):
    __tablename__ = "allocation_decisions"
    __table_args__ = (
        UniqueConstraint("request_id", "decision_sequence"),
        Index("ix_decisions_reviewer_created", "reviewer_id", "created_at"),
        Index("ix_decisions_policy_outcome", "policy_version", "outcome"),
        Index("ix_decisions_request_created", "request_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    request_id: Mapped[str] = mapped_column(ForeignKey("resource_requests.id"), nullable=False)
    decision_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    policy_version: Mapped[str] = mapped_column(ForeignKey("resource_policies.id"), nullable=False)
    outcome: Mapped[str] = mapped_column(String(24), nullable=False)
    explanation_code: Mapped[str] = mapped_column(String(100), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    inputs_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    reviewer_override: Mapped[dict | None] = mapped_column(JSON)
    reviewer_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    request: Mapped[ResourceRequest] = relationship(back_populates="decisions")


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        UniqueConstraint("request_id"),
        CheckConstraint("end_at > start_at", name="ck_bookings_valid_interval"),
        Index("ix_bookings_status_interval", "status", "start_at", "end_at"),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    request_id: Mapped[str] = mapped_column(ForeignKey("resource_requests.id"), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    approved_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    request: Mapped[ResourceRequest] = relationship(back_populates="booking")
    contracts: Mapped[list["AccessContract"]] = relationship(back_populates="booking")
    handover_reports: Mapped[list["HandoverReport"]] = relationship(back_populates="booking")
    incidents: Mapped[list["Incident"]] = relationship(back_populates="booking")


class AccessContract(Base):
    __tablename__ = "access_contracts"
    __table_args__ = (
        UniqueConstraint("booking_id", "version"),
        Index("ix_contracts_booking_version", "booking_id", "version"),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    booking_id: Mapped[str] = mapped_column(ForeignKey("bookings.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    request_id: Mapped[str] = mapped_column(ForeignKey("resource_requests.id"), nullable=False)
    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id"), nullable=False)
    requester_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    approver_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_purpose: Mapped[str] = mapped_column(Text, nullable=False)
    policy_version_id: Mapped[str] = mapped_column(ForeignKey("resource_policies.id"), nullable=False)
    requirements_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    supervision_requirement: Mapped[bool] = mapped_column(Boolean, nullable=False)
    permitted_use: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    checkin_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    checkout_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    condition_checklist_version: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    booking: Mapped[Booking] = relationship(back_populates="contracts")


class HandoverReport(Base):
    __tablename__ = "handover_reports"
    __table_args__ = (
        UniqueConstraint("booking_id", "stage"),
        UniqueConstraint("actor_id", "idempotency_key"),
        Index("ix_handover_actor_created", "actor_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    booking_id: Mapped[str] = mapped_column(ForeignKey("bookings.id"), nullable=False)
    stage: Mapped[str] = mapped_column(String(8), nullable=False)
    checklist_version: Mapped[str] = mapped_column(String(40), nullable=False)
    condition: Mapped[dict] = mapped_column(JSON, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    evidence_references: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(160))
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    booking: Mapped[Booking] = relationship(back_populates="handover_reports")


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        Index("ix_incidents_status_created", "status", "created_at"),
        Index("ix_incidents_booking", "booking_id"),
        Index("ix_incidents_reporter", "reporter_id"),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    booking_id: Mapped[str] = mapped_column(ForeignKey("bookings.id"), nullable=False)
    reporter_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    responses: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    resolution: Mapped[dict | None] = mapped_column(JSON)
    reviewer_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    booking: Mapped[Booking] = relationship(back_populates="incidents")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_entity_time", "entity_type", "entity_id", "timestamp"),
        Index("ix_audit_actor_time", "actor_id", "timestamp"),
        Index("ix_audit_correlation", "correlation_id"),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(100))
    correlation_id: Mapped[str | None] = mapped_column(String(100))
    before_summary: Mapped[dict | None] = mapped_column(JSON)
    after_summary: Mapped[dict | None] = mapped_column(JSON)
    previous_hash: Mapped[str | None] = mapped_column(String(128))
    hash: Mapped[str | None] = mapped_column(String(128))
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint(
            "recipient_id",
            "type",
            "related_entity_type",
            "related_entity_id",
        ),
        Index("ix_notifications_recipient_read_created", "recipient_id", "read_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    recipient_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(80), nullable=False)
    related_entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    related_entity_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    recipient: Mapped[User] = relationship(back_populates="notifications")
