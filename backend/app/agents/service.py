"""TASK-103 business services. Ownership of agent_id/version_id/run_ids/session_id is always
verified server-side; client-supplied ids are never trusted. Runs only write agent-module
tables — never core orders/refunds/events/danmaku."""
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents import schemas as agent_schemas
from app.agents.llm import ModelAdapter, build_messages, rule_reply
from app.agents.models import (
    AgentAssignmentRow,
    AgentPublicationRow,
    AgentRow,
    AgentRunRow,
    AgentSubmissionRow,
    AgentVersionRow,
)
from app.shared.auth import get_authorized_session_context, require_teacher_for_class
from app.shared.errors import AppError
from app.shared.schemas import AgentConfig, AgentRun, AgentRunRequest, KnowledgeCard, SessionContext, User


def now() -> datetime:
    return datetime.now(timezone.utc)


# ---------- mapping helpers ----------

def assignment_dto(row: AgentAssignmentRow) -> agent_schemas.AgentAssignment:
    return agent_schemas.AgentAssignment(
        id=row.id, class_id=row.class_id, teacher_id=row.teacher_id, task_id=row.task_id,
        title=row.title, instructions=row.instructions, scenario=row.scenario,
        rubric=list(row.rubric or []), status=row.status,
        created_at=row.created_at, published_at=row.published_at,
    )


def draft_dto(row: AgentRow) -> agent_schemas.AgentDraft:
    return agent_schemas.AgentDraft(
        id=row.id, owner_id=row.owner_id, class_id=row.class_id,
        current_version_id=row.current_version_id, created_at=row.created_at,
        updated_at=row.updated_at,
        config=AgentConfig(name=row.name, duties=row.duties, boundaries=row.boundaries,
                           instructions=row.instructions,
                           knowledge_cards=[KnowledgeCard.model_validate(card) if isinstance(card, dict) else card
                                            for card in (row.knowledge_cards or [])]),
    )


def version_dto(row: AgentVersionRow) -> agent_schemas.AgentVersion:
    return agent_schemas.AgentVersion(
        id=row.id, agent_id=row.agent_id, owner_id=row.owner_id, version_no=row.version_no,
        config=AgentConfig.model_validate(row.config), created_at=row.created_at,
    )


def run_dto(row: AgentRunRow) -> AgentRun:
    return AgentRun(
        id=row.id, owner_id=row.owner_id, agent_id=row.agent_id, version_id=row.version_id,
        config_snapshot=AgentConfig.model_validate(row.config_snapshot), question=row.question,
        session_id=row.session_id, context_snapshot=dict(row.context_snapshot or {}),
        context_sources=list(row.context_sources or []), output=row.output, source=row.source,
        model=row.model, duration_ms=row.duration_ms or 0, status=row.status,
        error=row.error, created_at=row.created_at,
    )


def submission_dto(row: AgentSubmissionRow) -> agent_schemas.AgentSubmission:
    return agent_schemas.AgentSubmission(
        id=row.id, assignment_id=row.assignment_id, owner_id=row.owner_id, version_id=row.version_id,
        run_ids=list(row.run_ids or []), improvement_notes=row.improvement_notes, status=row.status,
        grade=row.grade, comment=row.comment, reviewer_id=row.reviewer_id,
        content_snapshot=dict(row.content_snapshot or {}), submitted_at=row.submitted_at,
        reviewed_at=row.reviewed_at,
    )


def publication_dto(row: AgentPublicationRow, version: AgentVersionRow) -> agent_schemas.AgentPublication:
    return agent_schemas.AgentPublication(
        id=row.id, class_id=row.class_id, submission_id=row.submission_id, version_id=row.version_id,
        owner_id=row.owner_id, name=str(row.config_name), config=AgentConfig.model_validate(version.config),
        published_at=row.published_at,
    )


# ---------- assignments (teacher) ----------

def list_assignments(db: Session, user: User) -> list[agent_schemas.AgentAssignment]:
    if user.role == "teacher":
        rows = db.scalars(select(AgentAssignmentRow).where(AgentAssignmentRow.teacher_id == user.id)
                          .order_by(AgentAssignmentRow.id.desc())).all()
    else:
        rows = db.scalars(select(AgentAssignmentRow).where(
            AgentAssignmentRow.class_id == user.class_id,
            AgentAssignmentRow.status == "published").order_by(AgentAssignmentRow.id.desc())).all()
    return [assignment_dto(row) for row in rows]


def _validate_assignment_task(db: Session, task_id: int, class_id: int) -> None:
    from app.core.models import TaskRow  # read-only check; core tables are never written here
    task = db.get(TaskRow, task_id)
    if task is None:
        raise AppError(422, "TASK_NOT_FOUND", "关联的经营任务不存在")
    if task.class_id != class_id:
        raise AppError(403, "CLASS_FORBIDDEN", "不能关联其他班级的任务")


def create_assignment(db: Session, user: User, payload: agent_schemas.AgentAssignmentWrite
                      ) -> agent_schemas.AgentAssignment:
    require_teacher_for_class(user, user.class_id)
    if payload.task_id is not None:
        _validate_assignment_task(db, payload.task_id, user.class_id)
    row = AgentAssignmentRow(class_id=user.class_id, teacher_id=user.id, task_id=payload.task_id,
                             title=payload.title, instructions=payload.instructions,
                             scenario=payload.scenario, rubric=list(payload.rubric),
                             status="draft", created_at=now())
    db.add(row)
    db.commit()
    return assignment_dto(row)


def _owned_assignment(db: Session, user: User, assignment_id: int) -> AgentAssignmentRow:
    row = db.get(AgentAssignmentRow, assignment_id)
    if row is None:
        raise AppError(404, "ASSIGNMENT_NOT_FOUND", "作业不存在")
    if row.teacher_id != user.id:
        raise AppError(403, "ASSIGNMENT_FORBIDDEN", "只能操作本人布置的作业")
    return row


def update_assignment(db: Session, user: User, assignment_id: int,
                      payload: agent_schemas.AgentAssignmentWrite) -> agent_schemas.AgentAssignment:
    row = _owned_assignment(db, user, assignment_id)
    if row.status != "draft":
        raise AppError(409, "ASSIGNMENT_NOT_DRAFT", "作业已发布，内容已冻结")
    if payload.task_id is not None:
        _validate_assignment_task(db, payload.task_id, row.class_id)
    row.title, row.instructions, row.scenario = payload.title, payload.instructions, payload.scenario
    row.rubric, row.task_id = list(payload.rubric), payload.task_id
    db.commit()
    return assignment_dto(row)


def publish_assignment(db: Session, user: User, assignment_id: int) -> agent_schemas.AgentAssignment:
    row = _owned_assignment(db, user, assignment_id)
    if row.status != "draft":
        raise AppError(409, "ASSIGNMENT_ALREADY_PUBLISHED", "作业已发布")
    row.status, row.published_at = "published", now()
    db.commit()
    return assignment_dto(row)


# ---------- drafts & versions (students) ----------

def list_drafts(db: Session, user: User) -> list[agent_schemas.AgentDraft]:
    rows = db.scalars(select(AgentRow).where(AgentRow.owner_id == user.id)
                      .order_by(AgentRow.id.desc())).all()
    return [draft_dto(row) for row in rows]


def create_draft(db: Session, user: User, config: AgentConfig) -> agent_schemas.AgentDraft:
    row = AgentRow(owner_id=user.id, class_id=user.class_id, name=config.name,
                   duties=config.duties, boundaries=config.boundaries,
                   instructions=config.instructions,
                   knowledge_cards=[card.model_dump() for card in config.knowledge_cards],
                   created_at=now(), updated_at=now())
    db.add(row)
    db.commit()
    return draft_dto(row)


def _owned_draft(db: Session, user: User, agent_id: int) -> AgentRow:
    row = db.get(AgentRow, agent_id)
    if row is None:
        raise AppError(404, "AGENT_NOT_FOUND", "智能体草稿不存在")
    if row.owner_id != user.id:
        raise AppError(403, "AGENT_FORBIDDEN", "只能操作本人的智能体草稿")
    return row


def save_draft_version(db: Session, user: User, agent_id: int, config: AgentConfig
                       ) -> agent_schemas.AgentSaveResult:
    row = _owned_draft(db, user, agent_id)
    row.name, row.duties = config.name, config.duties
    row.boundaries, row.instructions = config.boundaries, config.instructions
    row.knowledge_cards = [card.model_dump() for card in config.knowledge_cards]
    row.updated_at = now()
    next_no = (db.scalar(select(func.max(AgentVersionRow.version_no))
                         .where(AgentVersionRow.agent_id == agent_id)) or 0) + 1
    version = AgentVersionRow(agent_id=agent_id, owner_id=user.id, version_no=next_no,
                              config=config.model_dump(), created_at=now())
    db.add(version)
    db.flush()
    row.current_version_id = version.id
    db.commit()
    return agent_schemas.AgentSaveResult(agent=draft_dto(row), version=version_dto(version))


def list_draft_versions(db: Session, user: User, agent_id: int) -> list[agent_schemas.AgentVersion]:
    row = db.get(AgentRow, agent_id)
    if row is None:
        raise AppError(404, "AGENT_NOT_FOUND", "智能体草稿不存在")
    if row.owner_id != user.id:
        # Teachers may only read versions that appear in a submitted assignment of their class.
        if user.role != "teacher" or row.class_id != user.class_id:
            raise AppError(403, "AGENT_FORBIDDEN", "无权读取该智能体的版本历史")
        version_ids = db.scalars(select(AgentVersionRow.id).where(AgentVersionRow.agent_id == agent_id)).all()
        linked = db.scalar(select(AgentSubmissionRow.id).where(
            AgentSubmissionRow.version_id.in_(version_ids)).limit(1)) if version_ids else None
        if linked is None:
            raise AppError(403, "AGENT_FORBIDDEN", "教师只能读取已提交作业涉及的版本历史")
    rows = db.scalars(select(AgentVersionRow).where(AgentVersionRow.agent_id == agent_id)
                      .order_by(AgentVersionRow.version_no.desc())).all()
    return [version_dto(row) for row in rows]


# ---------- runs (preview) ----------

def _save_run(db: Session, *, owner: User, agent_id: int | None, version_id: int | None,
              config: AgentConfig, question: str, session_id: int | None,
              context: SessionContext | None, adapter: ModelAdapter | None,
              config_source: str) -> AgentRun:
    if adapter is None:
        source, status, error = "rule", "failed", "模型服务未配置（需要 LLM_BASE_URL、LLM_API_KEY、LLM_MODEL）"
        output, model, duration_ms = rule_reply(config, question, context), None, 0
    else:
        call = adapter.invoke(build_messages(config, question, context))
        model, duration_ms = call.model, call.duration_ms
        if call.error is None and call.output:
            source, status, error, output = "model", "succeeded", None, call.output
        else:
            source, status = "rule", "failed"
            error = call.error or "模型调用失败"
            output = rule_reply(config, question, context)
    sources = [config_source, "config:knowledge_cards"]
    snapshot: dict = {}
    if context is not None:
        sources = sources + list(context.sources)
        snapshot = {
            "session_id": context.session_id,
            "class_id": context.class_id,
            "team_id": context.team_id,
            "products": [product.model_dump(mode="json") for product in context.products],
            "recent_questions": [event.model_dump(mode="json") for event in context.recent_questions],
        }
    row = AgentRunRow(owner_id=owner.id, agent_id=agent_id, version_id=version_id,
                      config_snapshot=config.model_dump(), question=question,
                      session_id=session_id, context_snapshot=snapshot,
                      context_sources=sources, output=output, source=source, model=model,
                      duration_ms=duration_ms, status=status, error=error, created_at=now())
    db.add(row)
    db.commit()
    return run_dto(row)


def create_run(db: Session, user: User, payload: AgentRunRequest, adapter: ModelAdapter | None) -> AgentRun:
    agent_id = payload.agent_id
    if agent_id is not None:
        _owned_draft(db, user, agent_id)  # runs reference the draft but never trust its saved config
    context = None
    if payload.session_id is not None:
        context = get_authorized_session_context(user, payload.session_id, db)
    config_source = f"config:agent:{agent_id}:current_form" if agent_id is not None else "config:unsaved_form"
    return _save_run(db, owner=user, agent_id=agent_id, version_id=None, config=payload.config,
                     question=payload.question, session_id=payload.session_id, context=context,
                     adapter=adapter, config_source=config_source)


def list_runs(db: Session, user: User, *, agent_id: int | None = None,
              submission_id: int | None = None, limit: int = 50) -> list[AgentRun]:
    if submission_id is not None:
        submission = db.get(AgentSubmissionRow, submission_id)
        if submission is None:
            raise AppError(404, "SUBMISSION_NOT_FOUND", "提交记录不存在")
        assignment = db.get(AgentAssignmentRow, submission.assignment_id)
        is_owner = submission.owner_id == user.id
        is_teacher = user.role == "teacher" and assignment is not None and assignment.teacher_id == user.id
        if not (is_owner or is_teacher):
            raise AppError(403, "SUBMISSION_FORBIDDEN", "无权读取该提交的运行记录")
        rows = db.scalars(select(AgentRunRow).where(AgentRunRow.id.in_(submission.run_ids or []))
                          .order_by(AgentRunRow.id)).all()
        return [run_dto(row) for row in rows]
    query = select(AgentRunRow).where(AgentRunRow.owner_id == user.id)
    if agent_id is not None:
        _owned_draft(db, user, agent_id)
        query = query.where(AgentRunRow.agent_id == agent_id)
    rows = db.scalars(query.order_by(AgentRunRow.id.desc()).limit(limit)).all()
    return [run_dto(row) for row in rows]


# ---------- submissions ----------

def _published_assignment_for_student(db: Session, user: User, assignment_id: int) -> AgentAssignmentRow:
    row = db.get(AgentAssignmentRow, assignment_id)
    if row is None:
        raise AppError(404, "ASSIGNMENT_NOT_FOUND", "作业不存在")
    if row.class_id != user.class_id:
        raise AppError(403, "ASSIGNMENT_FORBIDDEN", "只能提交本班作业")
    if row.status != "published":
        raise AppError(409, "ASSIGNMENT_NOT_PUBLISHED", "作业尚未发布，不能提交")
    return row


def create_submission(db: Session, user: User, payload: agent_schemas.AgentSubmissionWrite
                      ) -> agent_schemas.AgentSubmission:
    if user.role != "student":
        raise AppError(403, "STUDENT_ONLY", "作业提交仅限学生账号")
    assignment = _published_assignment_for_student(db, user, payload.assignment_id)
    version = db.get(AgentVersionRow, payload.version_id)
    if version is None:
        raise AppError(404, "VERSION_NOT_FOUND", "配置版本不存在")
    if version.owner_id != user.id:
        raise AppError(403, "VERSION_FORBIDDEN", "只能提交本人的配置版本")
    runs: list[AgentRunRow] = []
    for run_id in payload.run_ids:
        run = db.get(AgentRunRow, run_id)
        if run is None:
            raise AppError(404, "RUN_NOT_FOUND", f"运行记录 #{run_id} 不存在")
        if run.owner_id != user.id:
            raise AppError(403, "RUN_FORBIDDEN", "不能引用他人的运行记录")
        runs.append(run)
    active = db.scalar(select(AgentSubmissionRow).where(
        AgentSubmissionRow.assignment_id == assignment.id,
        AgentSubmissionRow.owner_id == user.id,
        AgentSubmissionRow.status == "submitted").limit(1))
    if active is not None:
        raise AppError(409, "SUBMISSION_ALREADY_ACTIVE", "该作业已有待评审的提交，请等待教师处理")
    qualifying = [run for run in runs
                  if run.status == "succeeded" and run.source == "model"
                  and run.config_snapshot == version.config]
    if not qualifying:
        raise AppError(409, "MODEL_RUN_REQUIRED", (
            "选定运行记录中缺少与该版本配置完全一致的成功真实模型预演"
            "（source=model 且 status=succeeded）；请先完成真实模型预演后再提交，"
            "规则演示回复不能替代。"))
    content = {
        "assignment": {"id": assignment.id, "title": assignment.title,
                       "scenario": assignment.scenario, "rubric": list(assignment.rubric or [])},
        "config": version.config,
        "runs": [run_dto(run).model_dump(mode="json") for run in runs],
    }
    row = AgentSubmissionRow(assignment_id=assignment.id, owner_id=user.id, version_id=version.id,
                            run_ids=list(payload.run_ids), improvement_notes=payload.improvement_notes,
                            status="submitted", content_snapshot=content, submitted_at=now())
    db.add(row)
    db.commit()
    return submission_dto(row)


def list_submissions(db: Session, user: User, *, assignment_id: int | None = None
                     ) -> list[agent_schemas.AgentSubmission]:
    query = select(AgentSubmissionRow)
    if user.role == "teacher":
        own_assignments = select(AgentAssignmentRow.id).where(AgentAssignmentRow.teacher_id == user.id)
        query = query.where(AgentSubmissionRow.assignment_id.in_(own_assignments))
    else:
        query = query.where(AgentSubmissionRow.owner_id == user.id)
    if assignment_id is not None:
        query = query.where(AgentSubmissionRow.assignment_id == assignment_id)
    rows = db.scalars(query.order_by(AgentSubmissionRow.id.desc())).all()
    return [submission_dto(row) for row in rows]


def review_submission(db: Session, user: User, submission_id: int,
                       payload: agent_schemas.AgentSubmissionReview) -> agent_schemas.AgentSubmission:
    row = db.get(AgentSubmissionRow, submission_id)
    if row is None:
        raise AppError(404, "SUBMISSION_NOT_FOUND", "提交记录不存在")
    assignment = db.get(AgentAssignmentRow, row.assignment_id)
    if user.role != "teacher" or assignment is None or assignment.teacher_id != user.id:
        raise AppError(403, "SUBMISSION_FORBIDDEN", "只有布置该作业的教师可以评审")
    if row.status != "submitted":
        raise AppError(409, "SUBMISSION_NOT_REVIEWABLE", "该提交已评审或已上架")
    if payload.decision == "approve" and (payload.grade is None or not payload.comment):
        raise AppError(422, "REVIEW_FIELDS_REQUIRED", "批准前必须填写分数与评语")
    if payload.decision == "return" and not payload.comment:
        raise AppError(422, "REVIEW_FIELDS_REQUIRED", "退回前必须填写评语")
    row.status = "approved" if payload.decision == "approve" else "returned"
    row.grade, row.comment = payload.grade, payload.comment
    row.reviewer_id, row.reviewed_at = user.id, now()
    db.commit()
    return submission_dto(row)


# ---------- publications ----------

def publish_submission(db: Session, user: User, submission_id: int) -> agent_schemas.AgentPublication:
    row = db.get(AgentSubmissionRow, submission_id)
    if row is None:
        raise AppError(404, "SUBMISSION_NOT_FOUND", "提交记录不存在")
    assignment = db.get(AgentAssignmentRow, row.assignment_id)
    if user.role != "teacher" or assignment is None or assignment.teacher_id != user.id:
        raise AppError(403, "SUBMISSION_FORBIDDEN", "只有布置该作业的教师可以上架")
    if row.status != "approved":
        raise AppError(409, "SUBMISSION_NOT_APPROVED", "只有评审通过的提交可以上架到班级")
    existing = db.scalar(select(AgentPublicationRow).where(
        AgentPublicationRow.class_id == assignment.class_id,
        AgentPublicationRow.version_id == row.version_id).limit(1))
    if existing is not None:
        return publication_dto(existing, db.get(AgentVersionRow, existing.version_id))
    version = db.get(AgentVersionRow, row.version_id)
    if version is None:
        raise AppError(404, "VERSION_NOT_FOUND", "配置版本不存在")
    publication = AgentPublicationRow(class_id=assignment.class_id, submission_id=row.id,
                                       version_id=row.version_id, owner_id=row.owner_id,
                                       config_name=version.config.get("name", ""), published_at=now())
    db.add(publication)
    db.commit()
    return publication_dto(publication, version)


def list_publications(db: Session, user: User) -> list[agent_schemas.AgentPublication]:
    rows = db.scalars(select(AgentPublicationRow).where(AgentPublicationRow.class_id == user.class_id)
                      .order_by(AgentPublicationRow.published_at.desc())).all()
    result = []
    for row in rows:
        version = db.get(AgentVersionRow, row.version_id)
        if version is not None:
            result.append(publication_dto(row, version))
    return result


def preview_publication(db: Session, user: User, publication_id: int,
                        payload: agent_schemas.AgentPublicationPreview,
                        adapter: ModelAdapter | None) -> AgentRun:
    publication = db.get(AgentPublicationRow, publication_id)
    if publication is None:
        raise AppError(404, "PUBLICATION_NOT_FOUND", "上架智能体不存在")
    if publication.class_id != user.class_id:
        raise AppError(403, "PUBLICATION_FORBIDDEN", "只能试用本班上架的智能体版本")
    version = db.get(AgentVersionRow, publication.version_id)
    if version is None:
        raise AppError(404, "VERSION_NOT_FOUND", "配置版本不存在")
    config = AgentConfig.model_validate(version.config)  # config comes from the immutable version only
    context = None
    if payload.session_id is not None:
        context = get_authorized_session_context(user, payload.session_id, db)
    return _save_run(db, owner=user, agent_id=None, version_id=publication.version_id,
                     config=config, question=payload.question, session_id=payload.session_id,
                     context=context, adapter=adapter,
                     config_source=f"config:publication_version:{publication.version_id}")
