"""TASK-103 module DTOs. Shared DTOs (AgentConfig/AgentRun/...) stay in app.shared.schemas.

The assignment/version/submission/publication objects are owned by this module; if the
master wants them contract-generated, they must be moved into shared schemas first.
"""
from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field

from app.shared.schemas import DTO, Id, AgentConfig

ShortText = Annotated[str, Field(min_length=1, max_length=200)]
LongText = Annotated[str, Field(min_length=1, max_length=4000)]
RubricItem = Annotated[str, Field(min_length=1, max_length=200)]
VersionNo = Annotated[int, Field(strict=True, ge=1)]


class AgentAssignmentWrite(DTO):
    title: ShortText
    instructions: LongText
    scenario: str = Field(default="", max_length=500)
    rubric: list[RubricItem] = Field(default_factory=list, max_length=12)
    task_id: Id | None = None


class AgentAssignment(AgentAssignmentWrite):
    id: Id
    class_id: Id
    teacher_id: Id
    status: Literal["draft", "published"]
    created_at: datetime
    published_at: datetime | None = None


class AgentDraft(DTO):
    id: Id
    owner_id: Id
    class_id: Id
    current_version_id: Id | None = None
    created_at: datetime
    updated_at: datetime
    config: AgentConfig


class AgentVersion(DTO):
    id: Id
    agent_id: Id
    owner_id: Id
    version_no: VersionNo
    config: AgentConfig
    created_at: datetime


class AgentSaveResult(DTO):
    agent: AgentDraft
    version: AgentVersion


class AgentSubmissionWrite(DTO):
    assignment_id: Id
    version_id: Id
    run_ids: list[Id] = Field(min_length=1, max_length=10)
    improvement_notes: LongText


class AgentSubmission(DTO):
    id: Id
    assignment_id: Id
    owner_id: Id
    version_id: Id
    run_ids: list[int]
    improvement_notes: str
    status: Literal["submitted", "approved", "returned"]
    grade: float | None = None
    comment: str | None = None
    reviewer_id: Id | None = None
    content_snapshot: dict
    submitted_at: datetime
    reviewed_at: datetime | None = None


class AgentSubmissionReview(DTO):
    decision: Literal["approve", "return"]
    grade: float | None = Field(default=None, ge=0, le=100)
    comment: LongText


class AgentPublication(DTO):
    id: Id
    class_id: Id
    submission_id: Id
    version_id: Id
    owner_id: Id
    name: str
    config: AgentConfig
    published_at: datetime


class AgentPublicationPreview(DTO):
    question: LongText
    session_id: Id | None = None
