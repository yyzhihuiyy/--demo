"""Fulfillment, submitted review snapshots, grading and competition read models."""
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select, text

from app.shared.auth import CurrentUser
from app.shared.db import DbSession
from app.shared.errors import AppError, success
from app.shared.schemas import CompetitionCreate, GradeWrite, ReviewWrite
from app.core import dto, metrics, service
from app.core.access import check_session_access, now
from app.core.models import (
    CompetitionRow, GradeRow, OrderRow, RefundRow, ReviewRow,
    SessionProductRow, SessionRow, TaskRow, TeamRow,
)

router = APIRouter(tags=["core"])


class RefundWrite(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class RefundDecision(BaseModel):
    decision: Literal["approve", "reject"]
    handling_note: str = Field(min_length=1, max_length=2000)


def _serialize_write(db):
    # SQLite reserves its writer before reading mutable financial/terminal state.
    db.execute(text("BEGIN IMMEDIATE"))


def _ended_student(db, user, session_id):
    session = check_session_access(user, session_id, db, write=True)
    if session.status != "ended":
        raise AppError(409, "SESSION_NOT_ENDED", "请先结束直播，再处理履约和复盘")
    return session


def _order(db, order_id):
    row = db.get(OrderRow, order_id)
    if row is None:
        raise AppError(404, "ORDER_NOT_FOUND", "订单不存在")
    return row


@router.get("/sessions/{session_id}/refunds")
def list_refunds(session_id: int, user: CurrentUser, db: DbSession):
    check_session_access(user, session_id, db)
    rows = db.scalars(select(RefundRow).join(OrderRow).where(
        OrderRow.session_id == session_id).order_by(RefundRow.id)).all()
    return success([dto.refund_dto(row) for row in rows])


@router.post("/orders/{order_id}/refunds")
def create_refund(order_id: int, payload: RefundWrite, user: CurrentUser, db: DbSession):
    _serialize_write(db)
    order = _order(db, order_id)
    _ended_student(db, user, order.session_id)
    existing = db.scalar(select(RefundRow).where(RefundRow.order_id == order_id))
    if existing is not None:
        return success(dto.refund_dto(existing))
    if order.status != "pending_shipment":
        raise AppError(409, "ORDER_STATUS_INVALID", "仅未发货订单可以申请整单退款")
    if not payload.reason.strip():
        raise AppError(422, "REASON_REQUIRED", "请填写退款原因")
    row = RefundRow(order_id=order_id, reason=payload.reason.strip(),
                    amount_cents=order.amount_cents)
    db.add(row)
    db.flush()
    service.append_event(db, order.session_id, "refund_requested", "manual",
                         {"order_id": order_id, "refund_id": row.id}, user.id)
    db.commit()
    return success(dto.refund_dto(row))


@router.post("/refunds/{refund_id}/resolve")
def resolve_refund(refund_id: int, payload: RefundDecision, user: CurrentUser, db: DbSession):
    _serialize_write(db)
    row = db.get(RefundRow, refund_id)
    if row is None:
        raise AppError(404, "REFUND_NOT_FOUND", "退款工单不存在")
    order = _order(db, row.order_id)
    session = _ended_student(db, user, order.session_id)
    target = "approved" if payload.decision == "approve" else "rejected"
    if row.status != "pending" and row.status != target:
        raise AppError(409, "REFUND_RESOLVED", "工单已处理，不能改变处理结果")
    if row.status == "pending":
        if order.status != "pending_shipment":
            raise AppError(409, "ORDER_STATUS_INVALID", "订单已发货，不能处理未发货退款")
        if not payload.handling_note.strip():
            raise AppError(422, "NOTE_REQUIRED", "请填写处理说明")
        row.status, row.handler_id = target, user.id
        row.handling_note = payload.handling_note.strip()
        if target == "approved":
            order.status = "refunded"
            db.get(SessionProductRow, order.session_product_id).stock_qty += order.qty
            service.add_cash(db, session.id, "refund", -row.amount_cents, "refund", row.id)
        service.append_event(db, session.id, "refund_resolved", "manual",
                             {"refund_id": row.id, "decision": payload.decision,
                              "handling_note": row.handling_note}, user.id)
    db.commit()
    return success({"refund": dto.refund_dto(row), "order": dto.order_dto(order),
                    "metrics": metrics.compute_metrics(db, session).model_dump(mode="json")})


def _review_detail(db, session):
    review = db.scalar(select(ReviewRow).where(ReviewRow.session_id == session.id))
    grade = db.scalar(select(GradeRow).where(GradeRow.session_id == session.id))
    data = review.data if review else {}
    if data.get("metrics_snapshot") and data.get("objective_breakdown"):
        summary, breakdown = data["metrics_snapshot"], data["objective_breakdown"]
    else:
        summary = metrics.compute_metrics(db, session).model_dump(mode="json")
        score, evidence = metrics.compute_breakdown(db, session, service.get_task(db, session.task_id), data)
        breakdown = {**score.model_dump(mode="json"), "evidence": evidence}
    return {"review": dto.review_dto(review), "metrics": summary,
            "breakdown": breakdown, "grade": dto.grade_dto(grade)}


@router.get("/sessions/{session_id}/review")
def read_review(session_id: int, user: CurrentUser, db: DbSession):
    return success(_review_detail(db, check_session_access(user, session_id, db)))


@router.put("/sessions/{session_id}/review")
def save_review(session_id: int, payload: ReviewWrite, user: CurrentUser, db: DbSession):
    _serialize_write(db)
    _ended_student(db, user, session_id)
    row = db.scalar(select(ReviewRow).where(ReviewRow.session_id == session_id))
    if row is None:
        row = ReviewRow(session_id=session_id, data={})
        db.add(row)
    row.data = {**payload.model_dump(), "status": "draft", "source": "rule"}
    db.commit()
    return success(dto.review_dto(row))


@router.post("/sessions/{session_id}/review/submit")
def submit_review(session_id: int, user: CurrentUser, db: DbSession):
    _serialize_write(db)
    session = check_session_access(user, session_id, db)
    if user.role != "student":
        raise AppError(403, "STUDENT_ACTION_REQUIRED", "请由本组学生提交复盘")
    row = db.scalar(select(ReviewRow).where(ReviewRow.session_id == session_id))
    if session.status in ("submitted", "graded") and row is not None:
        return success(dto.review_dto(row))
    _ended_student(db, user, session_id)
    unfinished = db.scalar(select(OrderRow.id).where(
        OrderRow.session_id == session_id, OrderRow.status.notin_(["signed", "refunded"])))
    pending = db.scalar(select(RefundRow.id).join(OrderRow).where(
        OrderRow.session_id == session_id, RefundRow.status == "pending"))
    if unfinished is not None or pending is not None:
        raise AppError(409, "FULFILLMENT_INCOMPLETE", "请先完成全部订单签收或退款，并处理待办售后")
    if row is None or not all(str(row.data.get(key, "")).strip() for key in ("analysis", "improvements")):
        raise AppError(409, "REVIEW_INCOMPLETE", "请填写并保存复盘分析和改进措施")
    detail = _review_detail(db, session)
    row.data = {**row.data, "status": "submitted", "metrics_snapshot": detail["metrics"],
                "objective_breakdown": detail["breakdown"], "rule_snapshot": session.rule_snapshot,
                "submitted_at": now().isoformat()}
    session.status = "submitted"
    service.append_event(db, session_id, "review_submitted", "manual", {"review_id": row.id}, user.id)
    db.commit()
    return success(dto.review_dto(row))


@router.post("/sessions/{session_id}/grade")
def grade_session(session_id: int, payload: GradeWrite, user: CurrentUser, db: DbSession):
    _serialize_write(db)
    session = check_session_access(user, session_id, db)
    service.require_task_teacher(user, service.get_task(db, session.task_id))
    existing = db.scalar(select(GradeRow).where(GradeRow.session_id == session_id))
    if existing is not None:
        return success(dto.grade_dto(existing))
    review = db.scalar(select(ReviewRow).where(ReviewRow.session_id == session_id))
    if session.status != "submitted" or review is None:
        raise AppError(409, "REVIEW_NOT_SUBMITTED", "学生提交复盘后才能评分")
    if not payload.comment.strip():
        raise AppError(422, "COMMENT_REQUIRED", "请填写教师评语")
    objective = review.data["objective_breakdown"]["objective_score"]
    row = GradeRow(session_id=session_id, data={
        **payload.model_dump(), "teacher_id": user.id, "objective_score": objective,
        "total_score": metrics.total_score(objective, payload.subjective_score),
        "rules_version": review.data["rule_snapshot"]["rules_version"], "graded_at": now().isoformat(),
    })
    db.add(row)
    review.data = {**review.data, "status": "graded"}
    session.status = "graded"
    db.commit()
    return success(dto.grade_dto(row))


def _sessions(db, task):
    return db.scalars(select(SessionRow).where(SessionRow.task_id == task.id).order_by(SessionRow.team_id)).all()


def _display_status(session):
    if session.status not in ("submitted", "graded") and service.deadline_passed(session):
        return "overtime"
    return session.status


def _comparison(db, task):
    teams = []
    for session in _sessions(db, task):
        detail = _review_detail(db, session)
        products = db.scalars(select(SessionProductRow).where(
            SessionProductRow.session_id == session.id).order_by(SessionProductRow.sort_order)).all()
        teams.append({"team_id": session.team_id, "team_name": db.get(TeamRow, session.team_id).name,
                      "session_id": session.id, "status": _display_status(session),
                      "preparation": dto.preparation_dto(session),
                      "products": [dto.session_product_dto(p) for p in products],
                      "metrics": detail["metrics"], "breakdown": detail["breakdown"], "grade": detail["grade"],
                      "evidence_links": [{"kind": kind, "label": label, "session_id": session.id}
                                         for kind, label in [("events", "过程证据"), ("orders", "订单记录"), ("review", "复盘成绩")]]})
    return teams


@router.get("/tasks/{task_id}/comparison")
def compare_task(task_id: int, user: CurrentUser, db: DbSession):
    task = service.get_task(db, task_id)
    service.require_task_teacher(user, task)
    return success({"task": dto.task_dto(task), "teams": _comparison(db, task)})


def _competition_dto(db, row):
    sessions = _sessions(db, service.get_task(db, row.task_id))
    finished = bool(sessions) and all(s.status == "graded" for s in sessions)
    return {"id": row.id, "task_id": row.task_id, "title": row.title,
            "status": "finished" if finished else row.status,
            "rule_snapshot": row.rule_snapshot, "published_at": row.published_at}


def _competition(db, user, competition_id):
    row = db.get(CompetitionRow, competition_id)
    if row is None:
        raise AppError(404, "COMPETITION_NOT_FOUND", "竞赛不存在")
    task = service.get_task(db, row.task_id)
    if task.class_id != user.class_id or (user.role != "teacher" and row.status == "draft"):
        raise AppError(403, "COMPETITION_FORBIDDEN", "无权查看该竞赛")
    if user.role == "teacher":
        service.require_task_teacher(user, task)
    return row, task


@router.post("/competitions")
def create_competition(payload: CompetitionCreate, user: CurrentUser, db: DbSession):
    _serialize_write(db)
    task = service.get_task(db, payload.task_id)
    service.require_task_teacher(user, task)
    if task.status != "draft":
        raise AppError(409, "TASK_LOCKED", "请在发布任务前创建竞赛")
    if len(service.task_team_ids(task)) < 2:
        raise AppError(409, "COMPETITION_TEAMS_REQUIRED", "竞赛至少需要两个小组")
    row = db.scalar(select(CompetitionRow).where(CompetitionRow.task_id == task.id))
    if row is None:
        row = CompetitionRow(task_id=task.id, title=payload.title, rule_snapshot={})
        db.add(row)
        db.commit()
    return success(_competition_dto(db, row))


@router.get("/competitions")
def list_competitions(user: CurrentUser, db: DbSession):
    query = select(CompetitionRow).join(TaskRow).where(TaskRow.class_id == user.class_id)
    if user.role == "teacher":
        query = query.where(TaskRow.teacher_id == user.id)
    else:
        query = query.where(CompetitionRow.status != "draft")
    return success([_competition_dto(db, row) for row in db.scalars(query.order_by(CompetitionRow.id)).all()])


@router.get("/competitions/{competition_id}/comparison")
def compare_competition(competition_id: int, user: CurrentUser, db: DbSession):
    row, task = _competition(db, user, competition_id)
    service.require_task_teacher(user, task)
    return success({"competition": _competition_dto(db, row), "teams": _comparison(db, task)})


@router.get("/competitions/{competition_id}/leaderboard")
def leaderboard(competition_id: int, user: CurrentUser, db: DbSession,
                stage: Literal["provisional", "final"] = "provisional"):
    row, task = _competition(db, user, competition_id)
    entries, pending = [], []
    for session in _sessions(db, task):
        detail = _review_detail(db, session)
        grade = detail["grade"]
        entry = {"team_id": session.team_id, "team_name": db.get(TeamRow, session.team_id).name,
                 "session_id": session.id, "status": _display_status(session), "metrics": detail["metrics"],
                 "objective_score": detail["breakdown"]["objective_score"],
                 "subjective_score": grade["subjective_score"] if grade else None,
                 "total_score": grade["total_score"] if grade else None}
        (pending if stage == "final" and grade is None else entries).append(entry)
    score_key = "total_score" if stage == "final" else "objective_score"
    entries.sort(key=lambda e: (-e[score_key], -e["metrics"]["net_sales_cents"],
                               e["metrics"]["violation_count"], e["team_id"]))
    rules = row.rule_snapshot or service.build_rule_snapshot(task)
    return success({"stage": stage, "rules_version": rules["rules_version"],
                    "score_weights": rules["score_weights"], "deadline": rules["ends_at"],
                    "entries": entries, "pending_entries": pending})
