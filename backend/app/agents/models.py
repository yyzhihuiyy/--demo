"""Agent-module owned tables. Core business tables are never written here (read-only checks)."""
from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.db import Base


class AgentAssignmentRow(Base):
    __tablename__ = "agent_assignments"
    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int]
    teacher_id: Mapped[int] = mapped_column(ForeignKey("core_accounts.id"))
    task_id: Mapped[int | None]
    title: Mapped[str] = mapped_column(String(200))
    instructions: Mapped[str] = mapped_column(Text)
    scenario: Mapped[str] = mapped_column(String(500), default="")
    rubric: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(default="draft")
    created_at: Mapped[str] = mapped_column(DateTime)
    published_at: Mapped[str | None] = mapped_column(DateTime)


class AgentRow(Base):
    __tablename__ = "agent_drafts"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("core_accounts.id"))
    class_id: Mapped[int]
    current_version_id: Mapped[int | None]
    name: Mapped[str] = mapped_column(String(200))
    duties: Mapped[str] = mapped_column(Text)
    boundaries: Mapped[str] = mapped_column(Text)
    instructions: Mapped[str] = mapped_column(Text)
    knowledge_cards: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[str] = mapped_column(DateTime)
    updated_at: Mapped[str] = mapped_column(DateTime)


class AgentVersionRow(Base):
    __tablename__ = "agent_versions"
    __table_args__ = (UniqueConstraint("agent_id", "version_no"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agent_drafts.id"))
    owner_id: Mapped[int] = mapped_column(ForeignKey("core_accounts.id"))
    version_no: Mapped[int] = mapped_column(default=1)
    config: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(DateTime)


class AgentRunRow(Base):
    __tablename__ = "agent_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("core_accounts.id"))
    agent_id: Mapped[int | None] = mapped_column(ForeignKey("agent_drafts.id"))
    version_id: Mapped[int | None] = mapped_column(ForeignKey("agent_versions.id"))
    config_snapshot: Mapped[dict] = mapped_column(JSON)
    question: Mapped[str] = mapped_column(Text)
    session_id: Mapped[int | None]
    context_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    context_sources: Mapped[list] = mapped_column(JSON, default=list)
    output: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(10))
    model: Mapped[str | None] = mapped_column(String(200))
    duration_ms: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(default="running")
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(DateTime)


class AgentSubmissionRow(Base):
    __tablename__ = "agent_submissions"
    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("agent_assignments.id"))
    owner_id: Mapped[int] = mapped_column(ForeignKey("core_accounts.id"))
    version_id: Mapped[int] = mapped_column(ForeignKey("agent_versions.id"))
    run_ids: Mapped[list] = mapped_column(JSON, default=list)
    improvement_notes: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(default="submitted")
    grade: Mapped[float | None] = mapped_column(nullable=True)
    comment: Mapped[str | None] = mapped_column(Text)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("core_accounts.id"))
    content_snapshot: Mapped[dict] = mapped_column(JSON)
    submitted_at: Mapped[str] = mapped_column(DateTime)
    reviewed_at: Mapped[str | None] = mapped_column(DateTime)


class AgentPublicationRow(Base):
    __tablename__ = "agent_publications"
    __table_args__ = (UniqueConstraint("class_id", "version_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int]
    submission_id: Mapped[int] = mapped_column(ForeignKey("agent_submissions.id"))
    version_id: Mapped[int] = mapped_column(ForeignKey("agent_versions.id"))
    owner_id: Mapped[int] = mapped_column(ForeignKey("core_accounts.id"))
    config_name: Mapped[str] = mapped_column(String(200), default="")
    published_at: Mapped[str] = mapped_column(DateTime)
