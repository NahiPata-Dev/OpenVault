from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class WeeklyWindow(APIModel):
    weekday: int = Field(ge=1, le=7)
    start: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    end: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")

    @model_validator(mode="after")
    def end_after_start(self):
        if self.end <= self.start:
            raise ValueError("end must be later than start")
        return self


class ResourceCreate(APIModel):
    name: str = Field(min_length=1, max_length=160)
    category: str = Field(min_length=1, max_length=80)
    capability_tags: list[str] = Field(default_factory=list, max_length=100)
    location: str = Field(min_length=1, max_length=160)
    status: Literal["active", "maintenance_hold"] = "active"
    hold_review_date: date | None = None
    weekly_operating_hours: list[WeeklyWindow] = Field(max_length=21)
    max_duration_minutes: int | None = Field(default=None, gt=0)
    exclusive_booking: bool = True

    @model_validator(mode="after")
    def hold_requires_review_date(self):
        if self.status == "maintenance_hold" and self.hold_review_date is None:
            raise ValueError("hold_review_date is required for a maintenance hold")
        return self


class ResourcePatch(APIModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    category: str | None = Field(default=None, min_length=1, max_length=80)
    capability_tags: list[str] | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, min_length=1, max_length=160)
    status: Literal["active", "maintenance_hold"] | None = None
    hold_review_date: date | None = None
    weekly_operating_hours: list[WeeklyWindow] | None = Field(default=None, max_length=21)
    max_duration_minutes: int | None = Field(default=None, gt=0)
    exclusive_booking: bool | None = None


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
    capability_tags: list[str]
    location: str
    status: str
    hold_review_date: date | None
    weekly_operating_hours: list[WeeklyWindow]
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
    capability_tags: list[str]
    location: str
    status: str
    weekly_operating_hours: list[WeeklyWindow]
    readiness: ReadinessRead


class ResourceListResponse(APIModel):
    items: list[ResourceListItem]
    total: int


class ResourceResponse(APIModel):
    resource: ResourceRead
    active_policy: ResourcePolicyRead | None = None
    readiness: ReadinessRead


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


class DemoResetRequest(APIModel):
    confirmation: str = Field(min_length=1, max_length=40)
