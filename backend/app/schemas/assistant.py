from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AssistantModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AssistantChatRequest(AssistantModel):
    message: str = Field(min_length=1, max_length=500)
    conversation_id: UUID | None = None

    @model_validator(mode="after")
    def message_is_not_blank(self):
        if not self.message.strip():
            raise ValueError("message must not be blank")
        return self


class AssistantSuggestion(AssistantModel):
    resource_id: UUID
    reason: str = Field(min_length=1, max_length=240)


class AssistantEligibilityItem(AssistantModel):
    requirement: str = Field(min_length=1, max_length=240)
    status: Literal["pass", "fail"]
    next_action: str = Field(min_length=1, max_length=500)


class AssistantResourceEligibility(AssistantModel):
    resource_id: UUID
    items: list[AssistantEligibilityItem]


class AssistantDraftRequest(AssistantModel):
    resource_id: UUID
    start: datetime
    end: datetime
    purpose: str = Field(min_length=1, max_length=2000)
    allowed_use: Literal["project", "coursework", "research"]

    @model_validator(mode="after")
    def valid_interval(self):
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("draft timestamps must include a timezone")
        if self.end <= self.start:
            raise ValueError("draft end must be later than start")
        return self


class AssistantChatResponse(AssistantModel):
    reply_text: str
    suggestions: list[AssistantSuggestion]
    eligibility: list[AssistantResourceEligibility]
    draft_request: AssistantDraftRequest | None
    quick_actions: list[str]
    source: Literal["model", "rules"]
    request_id: str = Field(min_length=1, max_length=100)


class AssistantModelIntent(AssistantModel):
    intent: Literal[
        "find_resources",
        "explain_requirements",
        "check_eligibility",
        "show_alternatives",
        "explain_request",
        "prepare_draft",
    ]
    resource_ids: list[UUID] = Field(default_factory=list, max_length=30)
    reply_text: str | None = Field(default=None, max_length=1000)
