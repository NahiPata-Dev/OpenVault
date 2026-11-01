from datetime import date, datetime
import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class DemoAccountRead(APIModel):
    id: UUID
    display_name: str
    role: str


class DemoAccountsRead(APIModel):
    accounts: list[DemoAccountRead]


class DemoLoginRequest(APIModel):
    account_id: UUID
    password: str = Field(min_length=1, max_length=256)


class UserRead(APIModel):
    id: UUID
    display_name: str
    role: str
    organization_id: str
    is_demo: bool


class DemoLoginResponse(APIModel):
    user: UserRead


JudgeRole = Literal["requester", "manager", "auditor"]


class JudgeLoginRequest(APIModel):
    role: JudgeRole


class AuthSessionRead(APIModel):
    user: UserRead | None
    judge_mode: bool
    judge_login_available: bool
    available_judge_roles: list[JudgeRole]


class AccountRegister(APIModel):
    full_name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=10, max_length=256)
    organization_name: str | None = Field(default=None, max_length=200)
    intended_use: str | None = Field(default=None, max_length=2000)

    @field_validator("full_name", mode="before")
    @classmethod
    def normalize_full_name(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        if not isinstance(value, str):
            return value
        email = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise ValueError("email must be a valid email address")
        return email

    @field_validator("password")
    @classmethod
    def require_non_numeric_password(cls, value: str) -> str:
        if value.isdigit():
            raise ValueError("password must not contain only digits")
        return value

    @field_validator("organization_name", "intended_use", mode="before")
    @classmethod
    def normalize_optional_text(cls, value):
        return value.strip() or None if isinstance(value, str) else value


class AccountLogin(APIModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        if not isinstance(value, str):
            return value
        email = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise ValueError("email must be a valid email address")
        return email


class AccountRead(APIModel):
    id: UUID
    full_name: str
    email: str | None
    organization_name: str | None
    phone: str | None
    intended_use: str | None
    role: str
    status: Literal["active", "inactive"]


class AccountPatch(APIModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    organization_name: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=40)
    intended_use: str | None = Field(default=None, max_length=2000)

    @field_validator("full_name", mode="before")
    @classmethod
    def normalize_full_name(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("organization_name", "phone", "intended_use", mode="before")
    @classmethod
    def normalize_optional_text(cls, value):
        return value.strip() or None if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_full_name(self):
        if "full_name" in self.model_fields_set and self.full_name is None:
            raise ValueError("full_name cannot be null")
        return self


class ChangePassword(APIModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=10, max_length=256)

    @field_validator("new_password")
    @classmethod
    def require_non_numeric_password(cls, value: str) -> str:
        if value.isdigit():
            raise ValueError("password must not contain only digits")
        return value


class OwnerApplicationCreate(APIModel):
    organization: str = Field(min_length=1, max_length=200)
    role_in_organization: str = Field(min_length=1, max_length=160)
    reason: str = Field(min_length=1, max_length=2000)
    resources_to_list: str = Field(min_length=1, max_length=2000)

    @field_validator(
        "organization", "role_in_organization", "reason", "resources_to_list"
    )
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value


class OwnerApplicationDecision(APIModel):
    outcome: Literal["approved", "rejected"]
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("reason must not be blank")
        return value


class OwnerApplicationRead(APIModel):
    id: UUID
    applicant_id: UUID
    applicant_name: str
    applicant_email: str | None
    organization: str
    role_in_organization: str
    reason: str
    resources_to_list: str
    status: Literal["pending", "approved", "rejected"]
    decision_reason: str | None
    decided_by: UUID | None
    created_at: datetime
    decided_at: datetime | None


class OwnerApplicationResponse(APIModel):
    application: OwnerApplicationRead | None


class AdminUserRead(APIModel):
    id: UUID
    full_name: str
    email: str | None
    organization_name: str | None
    role: str
    status: Literal["active", "inactive"]
    is_demo: bool


class WeeklyWindow(APIModel):
    weekday: int = Field(ge=1, le=7)
    start: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    end: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")

    @model_validator(mode="after")
    def end_after_start(self):
        if self.end <= self.start:
            raise ValueError("end must be later than start")
        return self


def _validate_weekly_windows(windows: list[WeeklyWindow], field_name: str) -> None:
    by_day: dict[int, list[WeeklyWindow]] = {}
    for window in windows:
        by_day.setdefault(window.weekday, []).append(window)
    for day_windows in by_day.values():
        day_windows.sort(key=lambda window: window.start)
        if any(
            current.start < previous.end
            for previous, current in zip(day_windows, day_windows[1:])
        ):
            raise ValueError(f"{field_name} windows must not overlap.")


ResourceStatus = Literal["active", "maintenance_hold", "retired"]
AllowedUse = Literal["project", "coursework", "research"]


def _trim_text_list(values: list[str] | None) -> list[str] | None:
    if values is None:
        return None
    cleaned = [item.strip() for item in values]
    if any(not item for item in cleaned):
        raise ValueError("List entries must not be blank")
    if len({item.casefold() for item in cleaned}) != len(cleaned):
        raise ValueError("List entries must not contain duplicates")
    return cleaned


class ResourceCreate(APIModel):
    name: str = Field(min_length=1, max_length=160)
    category: str = Field(min_length=1, max_length=80)
    short_summary: str = Field(default="", max_length=400)
    description: str = Field(default="", max_length=8000)
    capability_tags: list[str] = Field(default_factory=list, max_length=100)
    location: str = Field(default="", max_length=160)
    city: str = Field(default="", max_length=100)
    area: str = Field(default="", max_length=120)
    id_required: str = Field(default="Institution ID card", max_length=160)
    building: str = Field(default="", max_length=160)
    room: str = Field(default="", max_length=80)
    address_note: str = Field(default="", max_length=1000)
    operating_hours: list[WeeklyWindow] = Field(default_factory=list, max_length=21)
    weekly_operating_hours: list[WeeklyWindow] | None = Field(default=None, max_length=21)
    capacity: int | None = Field(default=None, ge=1, le=100_000)
    quantity: int | None = Field(default=None, ge=1, le=100_000)
    allowed_uses: list[AllowedUse] | None = Field(default=None, min_length=1, max_length=3)
    who_can_use: list[str] = Field(default_factory=list, max_length=30)
    required_training: list[str] = Field(default_factory=list, max_length=50)
    supervision_required: bool = False
    supervised_windows: list[WeeklyWindow] = Field(default_factory=list, max_length=21)
    usage_rules: list[str] = Field(default_factory=list, max_length=50)
    safety_notes: list[str] = Field(default_factory=list, max_length=50)
    max_session_hours: float | None = Field(default=None, gt=0, le=168)
    advance_booking_window: int | None = Field(
        default=None, ge=0, le=365, description="Maximum advance booking in days."
    )
    cancellation_cutoff: float = Field(
        default=2, ge=0, le=720, description="Cancellation cutoff before start, in hours."
    )
    accessories_included: list[str] = Field(default_factory=list, max_length=50)
    condition_notes: str = Field(default="", max_length=2000)
    access_model: str = Field(
        default="free for members; no payments are processed", max_length=160
    )
    status: ResourceStatus = "active"
    hold_reason: str | None = Field(default=None, max_length=2000)
    hold_review_date: date | None = None
    max_duration_minutes: int | None = Field(default=None, gt=0, le=10080)
    exclusive_booking: bool = True
    policy_change_reason: str | None = Field(default=None, min_length=1, max_length=2000)

    @model_validator(mode="after")
    def validate_resource(self):
        if self.weekly_operating_hours is not None:
            if self.operating_hours and self.operating_hours != self.weekly_operating_hours:
                raise ValueError("operating_hours and weekly_operating_hours must match when both are supplied")
            self.operating_hours = self.weekly_operating_hours
        if self.capacity is not None and self.quantity is not None:
            raise ValueError("Provide capacity or quantity, not both")
        if self.status == "maintenance_hold":
            if self.hold_review_date is None:
                raise ValueError("hold_review_date is required for a maintenance hold")
            if not self.hold_reason:
                raise ValueError("hold_reason is required for a maintenance hold")
        if self.status != "maintenance_hold" and self.hold_reason:
            raise ValueError("hold_reason is only valid for a maintenance hold")
        if self.supervision_required and not self.supervised_windows:
            raise ValueError("supervised_windows are required when supervision_required is true")
        _validate_weekly_windows(self.operating_hours, "operating_hours")
        _validate_weekly_windows(self.supervised_windows, "supervised_windows")
        if (
            self.max_session_hours is not None
            and self.max_duration_minutes is not None
            and round(self.max_session_hours * 60) != self.max_duration_minutes
        ):
            raise ValueError("max_session_hours and max_duration_minutes must match.")
        if self.allowed_uses is not None and not self.policy_change_reason:
            raise ValueError("policy_change_reason is required when activating an initial policy")
        return self

    @property
    def resolved_operating_hours(self) -> list[WeeklyWindow]:
        return self.operating_hours

    @field_validator(
        "capability_tags",
        "who_can_use",
        "required_training",
        "usage_rules",
        "safety_notes",
        "accessories_included",
    )
    @classmethod
    def normalize_lists(cls, values):
        return _trim_text_list(values)

    @field_validator(
        "name",
        "category",
        "short_summary",
        "description",
        "location",
        "city",
        "area",
        "id_required",
        "building",
        "room",
        "address_note",
        "condition_notes",
        "access_model",
        mode="before",
    )
    @classmethod
    def trim_resource_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("hold_reason", mode="before")
    @classmethod
    def trim_hold_reason(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("policy_change_reason", mode="before")
    @classmethod
    def normalize_optional_policy_change_reason(cls, value):
        return value.strip() or None if isinstance(value, str) else value


class ResourcePatch(APIModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    category: str | None = Field(default=None, min_length=1, max_length=80)
    short_summary: str | None = Field(default=None, max_length=400)
    description: str | None = Field(default=None, max_length=8000)
    capability_tags: list[str] | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=160)
    city: str | None = Field(default=None, max_length=100)
    area: str | None = Field(default=None, max_length=120)
    id_required: str | None = Field(default=None, max_length=160)
    building: str | None = Field(default=None, max_length=160)
    room: str | None = Field(default=None, max_length=80)
    address_note: str | None = Field(default=None, max_length=1000)
    operating_hours: list[WeeklyWindow] | None = Field(default=None, max_length=21)
    weekly_operating_hours: list[WeeklyWindow] | None = Field(default=None, max_length=21)
    capacity: int | None = Field(default=None, ge=1, le=100_000)
    quantity: int | None = Field(default=None, ge=1, le=100_000)
    allowed_uses: list[AllowedUse] | None = Field(default=None, min_length=1, max_length=3)
    who_can_use: list[str] | None = Field(default=None, max_length=30)
    required_training: list[str] | None = Field(default=None, max_length=50)
    supervision_required: bool | None = None
    supervised_windows: list[WeeklyWindow] | None = Field(default=None, max_length=21)
    usage_rules: list[str] | None = Field(default=None, max_length=50)
    safety_notes: list[str] | None = Field(default=None, max_length=50)
    max_session_hours: float | None = Field(default=None, gt=0, le=168)
    advance_booking_window: int | None = Field(default=None, ge=0, le=365)
    cancellation_cutoff: float | None = Field(
        default=None, ge=0, le=720, description="Cancellation cutoff before start, in hours."
    )
    accessories_included: list[str] | None = Field(default=None, max_length=50)
    condition_notes: str | None = Field(default=None, max_length=2000)
    access_model: str | None = Field(default=None, max_length=160)
    status: ResourceStatus | None = None
    hold_reason: str | None = Field(default=None, max_length=2000)
    hold_review_date: date | None = None
    max_duration_minutes: int | None = Field(default=None, gt=0, le=10080)
    exclusive_booking: bool | None = None
    policy_change_reason: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def validate_patch(self):
        if self.weekly_operating_hours is not None:
            if self.operating_hours is not None and self.operating_hours != self.weekly_operating_hours:
                raise ValueError("operating_hours and weekly_operating_hours must match when both are supplied")
            self.operating_hours = self.weekly_operating_hours
        if self.capacity is not None and self.quantity is not None:
            raise ValueError("Provide capacity or quantity, not both")
        if self.supervision_required is True and self.supervised_windows == []:
            raise ValueError("supervised_windows are required when supervision_required is true")
        for field_name in (
            "name",
            "category",
            "short_summary",
            "description",
            "capability_tags",
            "location",
            "city",
            "area",
            "id_required",
            "building",
            "room",
            "address_note",
            "operating_hours",
            "weekly_operating_hours",
            "allowed_uses",
            "who_can_use",
            "required_training",
            "supervision_required",
            "supervised_windows",
            "usage_rules",
            "safety_notes",
            "cancellation_cutoff",
            "accessories_included",
            "condition_notes",
            "status",
            "exclusive_booking",
        ):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null.")
        if self.operating_hours is not None:
            _validate_weekly_windows(self.operating_hours, "operating_hours")
        if self.supervised_windows is not None:
            _validate_weekly_windows(self.supervised_windows, "supervised_windows")
        if (
            self.max_session_hours is not None
            and self.max_duration_minutes is not None
            and round(self.max_session_hours * 60) != self.max_duration_minutes
        ):
            raise ValueError("max_session_hours and max_duration_minutes must match.")
        if "status" in self.model_fields_set and self.status == "maintenance_hold":
            if "hold_reason" not in self.model_fields_set and "hold_review_date" not in self.model_fields_set:
                return self
            if self.hold_reason == "":
                raise ValueError("hold_reason is required for a maintenance hold")
        if self.status in {"active", "retired"} and self.hold_reason:
            raise ValueError("hold_reason is only valid for a maintenance hold")
        return self

    @field_validator(
        "capability_tags",
        "who_can_use",
        "required_training",
        "usage_rules",
        "safety_notes",
        "accessories_included",
    )
    @classmethod
    def normalize_lists(cls, values):
        return _trim_text_list(values)

    @field_validator(
        "name",
        "category",
        "short_summary",
        "description",
        "location",
        "city",
        "area",
        "id_required",
        "building",
        "room",
        "address_note",
        "condition_notes",
        "access_model",
        mode="before",
    )
    @classmethod
    def trim_resource_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("hold_reason", mode="before")
    @classmethod
    def trim_hold_reason(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("policy_change_reason")
    @classmethod
    def normalize_policy_change_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("policy_change_reason must not be blank")
        return value


ResourceCreate.model_rebuild()
ResourcePatch.model_rebuild()


class ResourcePolicyRead(APIModel):
    id: UUID
    resource_id: UUID
    version: int
    structured_requirements: dict
    allowed_uses: list[str]
    priority_policy: dict
    effective_at: datetime | None
    approved_by: UUID | None
    activation_reason: str | None
    is_demo: bool


class ResourceRead(APIModel):
    id: UUID
    owner_id: UUID
    name: str
    category: str
    short_summary: str
    description: str
    capability_tags: list[str]
    location: str
    organization_id: str
    organization_name: str
    city: str
    area: str
    organization_type: str
    id_required: str
    building: str
    room: str
    address_note: str
    status: str
    hold_reason: str | None
    hold_review_date: date | None
    operating_hours: list[WeeklyWindow]
    weekly_operating_hours: list[WeeklyWindow]
    capacity: int | None
    quantity: int | None
    allowed_uses: list[AllowedUse]
    who_can_use: list[str]
    required_training: list[str]
    supervision_required: bool
    supervised_windows: list[WeeklyWindow]
    usage_rules: list[str]
    safety_notes: list[str]
    max_session_hours: float | None
    advance_booking_window: int | None
    cancellation_cutoff: float
    accessories_included: list[str]
    condition_notes: str
    access_model: str
    max_duration_minutes: int | None
    exclusive_booking: bool
    is_demo: bool


class ReadinessBlocker(APIModel):
    code: str
    message: str
    next_action: str
    requirement_codes: list[str] | None = None


class ReadinessRead(APIModel):
    ready: bool
    blockers: list[ReadinessBlocker]


class ResourceListItem(APIModel):
    id: UUID
    name: str
    category: str
    short_summary: str
    description: str
    capability_tags: list[str]
    location: str
    organization_id: str
    organization_name: str
    city: str
    area: str
    organization_type: str
    id_required: str
    building: str
    room: str
    capacity: int | None
    quantity: int | None
    status: str
    supervision_required: bool
    required_training: list[str]
    operating_hours: list[WeeklyWindow]
    weekly_operating_hours: list[WeeklyWindow]
    readiness: ReadinessRead
    next_availability: datetime | None


class ResourceListResponse(APIModel):
    items: list[ResourceListItem]
    total: int


class PublicSummaryCity(APIModel):
    city: str
    resource_count: int
    organization_count: int


class PublicSummaryResponse(APIModel):
    cities: list[PublicSummaryCity]
    categories: list[str]


class EligibilityChecklistItem(APIModel):
    requirement: str
    code: str | None = None
    passed: bool
    message: str
    next_action: str


class ResourceResponse(APIModel):
    resource: ResourceRead
    active_policy: ResourcePolicyRead | None = None
    readiness: ReadinessRead
    eligibility_checklist: list[EligibilityChecklistItem]


class ErrorDetail(APIModel):
    code: str
    message: str


class ErrorBody(APIModel):
    code: str
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)
    request_id: str


class ErrorResponse(APIModel):
    error: ErrorBody


class ResourceRequestCreate(APIModel):
    resource_id: UUID
    purpose: str = Field(min_length=1, max_length=2000)
    start_at: datetime
    end_at: datetime
    assistant_draft: bool = False

    @model_validator(mode="after")
    def valid_interval(self):
        if self.start_at.tzinfo is None or self.end_at.tzinfo is None:
            raise ValueError("start_at and end_at must include a timezone")
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be later than start_at")
        return self


class DecisionCreate(APIModel):
    outcome: Literal["approved", "rejected", "waitlisted"]
    reason: str = Field(min_length=1, max_length=2000)
    override_reason: str | None = Field(default=None, max_length=2000)


class PolicyDraftCreate(APIModel):
    structured_requirements: dict
    allowed_uses: list[Literal["project", "coursework", "research"]]
    priority_policy: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_policy(self):
        requirements = self.structured_requirements
        if set(requirements) != {
            "training_codes",
            "supervisor_required",
            "supervised_windows",
        }:
            raise ValueError("structured_requirements has an invalid shape")
        if not isinstance(requirements["training_codes"], list) or not all(
            isinstance(code, str) and code for code in requirements["training_codes"]
        ):
            raise ValueError("training_codes must contain non-empty strings")
        if not isinstance(requirements["supervisor_required"], bool):
            raise ValueError("supervisor_required must be a boolean")
        if not isinstance(requirements["supervised_windows"], list):
            raise ValueError("supervised_windows must be a list")
        if not self.allowed_uses:
            raise ValueError("allowed_uses must not be empty")
        return self


class PolicyActivate(APIModel):
    reason: str = Field(min_length=1, max_length=2000)


class TrainingRecordCreate(APIModel):
    user_id: UUID
    requirement_code: str = Field(min_length=1, max_length=100)
    status: Literal["valid", "expired", "revoked"]
    valid_from: datetime
    valid_to: datetime | None = None

    @model_validator(mode="after")
    def valid_dates(self):
        if self.valid_from.tzinfo is None:
            raise ValueError("valid_from must include a timezone")
        if self.valid_to is not None and self.valid_to.tzinfo is None:
            raise ValueError("valid_to must include a timezone")
        if self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ValueError("valid_to must be later than valid_from")
        return self


class ConditionChecklist(APIModel):
    physical_condition: Literal["ok", "minor_wear", "damaged"]
    accessories_complete: Literal["yes", "no"]
    functional_test: Literal["works", "issue"]
    notes: str | None = Field(default=None, max_length=2000)


class EvidenceMetadata(APIModel):
    file_name: str = Field(min_length=1, max_length=255)
    note: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def metadata_only(self):
        if "/" in self.file_name or "\\" in self.file_name or "://" in self.file_name:
            raise ValueError("file_name must be a name only, not a path or URL")
        return self


class HandoverCreate(APIModel):
    checklist_version: str = Field(min_length=1, max_length=40)
    condition: ConditionChecklist
    evidence_references: list[EvidenceMetadata] = Field(default_factory=list, max_length=50)


class IncidentCreate(APIModel):
    category: Literal["damage", "missing_part", "malfunction", "late_return", "other"]
    description: str = Field(min_length=1, max_length=2000)


class IncidentResponseCreate(APIModel):
    message: str = Field(min_length=1, max_length=2000)


class IncidentResolve(APIModel):
    outcome: Literal["resolved", "dismissed"]
    rationale: str = Field(min_length=1, max_length=2000)


class IncidentReview(APIModel):
    status: Literal["information_requested", "under_review"]
    reason: str = Field(min_length=1, max_length=2000)


class MatchConstraints(APIModel):
    categories: list[str] = Field(default_factory=list, max_length=20)
    capabilities: list[str] = Field(default_factory=list, max_length=50)
    available_from: datetime | None = None
    available_to: datetime | None = None

    @model_validator(mode="after")
    def valid_availability(self):
        if (self.available_from is None) != (self.available_to is None):
            raise ValueError("available_from and available_to must be provided together")
        if self.available_from and self.available_to:
            if self.available_from.tzinfo is None or self.available_to.tzinfo is None:
                raise ValueError("availability timestamps must include a timezone")
            if self.available_to <= self.available_from:
                raise ValueError("available_to must be later than available_from")
        return self


class ResourceMatchRequest(APIModel):
    goal: str = Field(min_length=1, max_length=2000)
    constraints: MatchConstraints = Field(default_factory=MatchConstraints)


class MatchCandidate(APIModel):
    resource_id: UUID
    explanation: str = Field(min_length=1, max_length=1000)


class MatchCriteria(APIModel):
    categories: list[str]
    capabilities: list[str]


class ResourceMatchResult(APIModel):
    criteria: MatchCriteria
    candidates: list[MatchCandidate]
    source: Literal["deterministic", "ai", "deterministic_fallback"]
    disclosure: str


class AIChatMessage(APIModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class AIChatRequest(APIModel):
    messages: list[AIChatMessage] = Field(min_length=1, max_length=16)

    @model_validator(mode="after")
    def last_message_must_be_user(self):
        if self.messages[-1].role != "user":
            raise ValueError("The latest chat message must be from the user")
        return self


class AIChatResource(APIModel):
    resource_id: UUID
    name: str
    location: str
    ready: bool
    explanation: str


class AIChatResponse(APIModel):
    reply: str = Field(min_length=1, max_length=5000)
    resources: list[AIChatResource] = Field(max_length=5)
    source: Literal["ai"]
    disclosure: str


class DiscoveryFeedbackCreate(APIModel):
    is_helpful: bool


class DemoResetRequest(APIModel):
    confirmation: str = Field(min_length=1, max_length=40)
