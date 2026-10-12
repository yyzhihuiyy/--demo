"""Shared core service helpers: ownership guards, events, cash entries, sessions, idempotency."""
import hashlib
import hmac
import secrets
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.shared.errors import AppError
from app.shared.schemas import User
from app.core.access import now
from app.core.models import (
    CashEntry, EventRow, IdempotencyRow, SessionRow, TeamRow, TaskRow,
)
from app.core.rules import RULES_VERSION, SIM_SEED, SIM_VERSION


def get_task(db: Session, task_id: int) -> TaskRow:
    row = db.get(TaskRow, task_id)
    if row is None:
        raise AppError(404, "TASK_NOT_FOUND", "任务不存在")
    return row


def require_teacher(user: User) -> None:
    if user.role != "teacher":
        raise AppError(403, "TEACHER_REQUIRED", "仅教师可执行该操作")


def require_task_teacher(user: User, task: TaskRow) -> None:
    require_teacher(user)
    if task.teacher_id != user.id or task.class_id != user.class_id:
        raise AppError(403, "TASK_FORBIDDEN", "无权操作该任务")


def append_event(db: Session, session_id: int, type_: str, source: str,
                 payload: dict, actor_id: int | None = None) -> EventRow:
    row = EventRow(session_id=session_id, type=type_, actor_id=actor_id, source=source,
                   payload=payload, created_at=now().isoformat())
    db.add(row)
    db.flush()
    return row


def add_cash(db: Session, session_id: int, kind: str, amount_cents: int,
            reference_type: str, reference_id: int | None = None) -> CashEntry:
    row = CashEntry(session_id=session_id, kind=kind, amount_cents=amount_cents,
                    reference_type=reference_type, reference_id=reference_id,
                    created_at=now().isoformat())
    db.add(row)
    db.flush()
    return row


def build_rule_snapshot(task: TaskRow) -> dict:
    data = task.data or {}
    return {
        "rules_version": data.get("rules_version", RULES_VERSION),
        "sim_version": SIM_VERSION,
        "sim_seed": SIM_SEED,
        "market_heat": data.get("market_heat", 1),
        "difficulty": data.get("difficulty", 1),
        "score_weights": data.get("score_weights"),
        "starts_at": data.get("starts_at"),
        "ends_at": data.get("ends_at"),
        "target_gmv_cents": data.get("target_gmv_cents"),
        "initial_budget_cents": data.get("initial_budget_cents"),
    }


def create_session_for_team(db: Session, task: TaskRow, team: TeamRow) -> SessionRow:
    from app.shared.schemas import Preparation
    preparation = Preparation().model_dump(mode="json")
    row = SessionRow(task_id=task.id, team_id=team.id, status="preparing",
                     rule_snapshot=build_rule_snapshot(task),
                     members_snapshot=[{"user_id": m["user_id"], "position": m["position"]}
                                       for m in (team.members or [])],
                     preparation=preparation, preparation_version=0,
                     initial_budget_cents=(task.data or {}).get("initial_budget_cents", 0),
                     current_product_id=None)
    db.add(row)
    db.flush()
    return row


def session_purchase_cost(db: Session, session_id: int) -> int:
    rows = db.scalars(select(CashEntry).where(
        CashEntry.session_id == session_id, CashEntry.kind == "purchase")).all()
    return -sum(r.amount_cents for r in rows)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000)
    return f"pbkdf2_sha256$200000${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, rounds, salt, expected = stored.split("$")
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(),
                                     bytes.fromhex(salt), int(rounds))
        return hmac.compare_digest(digest.hex(), expected)
    except (ValueError, TypeError):
        return False


def idempotent_response(db: Session, user: User, action: str, key: str | None,
                        payload_hash: str) -> dict | None:
    if not key:
        return None
    row = db.scalars(select(IdempotencyRow).where(
        IdempotencyRow.user_id == user.id, IdempotencyRow.action == action,
        IdempotencyRow.key == key)).first()
    if row is None:
        return None
    if row.payload_hash != payload_hash:
        raise AppError(409, "IDEMPOTENCY_MISMATCH", "同一幂等键的请求内容不一致")
    return row.response


def remember_idempotent(db: Session, user: User, action: str, key: str | None,
                       payload_hash: str, response: dict) -> None:
    if not key:
        return
    db.add(IdempotencyRow(user_id=user.id, action=action, key=key,
                          payload_hash=payload_hash, response=response))
    db.flush()


def fingerprint(payload) -> str:
    return hashlib.sha256(repr(payload).encode()).hexdigest()


def publish_task_sessions(db: Session, task: TaskRow) -> list[int]:
    session_ids: list[int] = []
    for team_id in (task.data or {}).get("team_ids", []):
        team = db.get(TeamRow, team_id)
        if team is None or team.class_id != task.class_id:
            raise AppError(422, "TEAM_INVALID", f"小组 {team_id} 不属于本班级")
        existing = db.scalars(select(SessionRow).where(
            SessionRow.task_id == task.id, SessionRow.team_id == team.id)).first()
        session_ids.append(existing.id if existing else create_session_for_team(db, task, team).id)
    task.status = "published"
    db.flush()
    return session_ids


def task_team_ids(task: TaskRow) -> list[int]:
    return list((task.data or {}).get("team_ids", []))


def session_ends_at(session: SessionRow) -> datetime:
    return datetime.fromisoformat((session.rule_snapshot or {}).get("ends_at"))


def deadline_passed(session: SessionRow) -> bool:
    return now() >= session_ends_at(session)


def live_elapsed_seconds(db: Session, session: SessionRow) -> int:
    rows = db.scalars(select(EventRow).where(
        EventRow.session_id == session.id,
        EventRow.type.in_(("control", "system_recovery"))).order_by(EventRow.id)).all()
    total = 0.0
    anchor: datetime | None = None
    for row in rows:
        action = (row.payload or {}).get("action")
        stamp = datetime.fromisoformat(row.created_at)
        if action in ("start", "resume"):
            anchor = stamp
        elif action in ("pause", "end") and anchor is not None:
            total += (stamp - anchor).total_seconds()
            anchor = None
    if anchor is not None and session.status == "live":
        total += (now() - anchor).total_seconds()
    return int(total)


def control_session(db: Session, session: SessionRow, task: TaskRow,
                    action: str, actor_id: int | None) -> None:
    from app.core.metrics import build_checklist
    from app.shared.schemas import Preparation
    if action == "start":
        if session.status != "preparing":
            raise AppError(409, "SESSION_NOT_PREPARING", "仅准备完成的场次可开始直播")
        if deadline_passed(session):
            raise AppError(409, "DEADLINE_PASSED", "任务已截止，不能开始直播")
        checklist = build_checklist(db, session, task)
        if not checklist.can_start:
            raise AppError(409, "CHECKLIST_FAILED", "开播检查未通过，请完成缺失项",
                            {"items": [i.model_dump() for i in checklist.items if not i.passed]})
        preparation = Preparation.model_validate(session.preparation or {})
        promoted = db.scalars(select(CashEntry).where(
            CashEntry.session_id == session.id,
            CashEntry.kind == "promotion")).first()
        if preparation.promotion.budget_cents > 0 and promoted is None:
            add_cash(db, session.id, "promotion", -preparation.promotion.budget_cents,
                     "promotion_plan", None)
        session.status = "live"
        session.started_at = now().isoformat()
        append_event(db, session.id, "control", "manual", {"action": "start"}, actor_id)
    elif action == "pause":
        if session.status != "live":
            raise AppError(409, "SESSION_NOT_LIVE", "仅直播中可暂停")
        session.status = "paused"
        append_event(db, session.id, "control", "manual", {"action": "pause"}, actor_id)
        session.live_elapsed_seconds = live_elapsed_seconds(db, session)
    elif action == "resume":
        if session.status != "paused":
            raise AppError(409, "SESSION_NOT_PAUSED", "仅已暂停场次可恢复")
        if deadline_passed(session):
            raise AppError(409, "DEADLINE_PASSED", "任务已截止，不能恢复直播")
        session.status = "live"
        append_event(db, session.id, "control", "manual", {"action": "resume"}, actor_id)
    elif action == "end":
        if session.status not in ("live", "paused"):
            raise AppError(409, "SESSION_NOT_ACTIVE", "直播未开始或已结束")
        session.status = "ended"
        session.ended_at = now().isoformat()
        append_event(db, session.id, "control", "manual", {"action": "end"}, actor_id)
        session.live_elapsed_seconds = live_elapsed_seconds(db, session)
    else:
        raise AppError(422, "ACTION_INVALID", "不支持的控制操作")


def force_end_session(db: Session, session: SessionRow, reason: str) -> None:
    if session.status not in ("live", "paused"):
        return
    session.status = "ended"
    session.ended_at = now().isoformat()
    append_event(db, session.id, "control", "rule", {"action": "end", "reason": reason})
    session.live_elapsed_seconds = live_elapsed_seconds(db, session)


__all__ = [
    "add_cash", "append_event", "build_rule_snapshot", "control_session",
    "create_session_for_team", "deadline_passed", "fingerprint", "force_end_session",
    "get_task", "hash_password", "idempotent_response", "live_elapsed_seconds",
    "publish_task_sessions", "require_task_teacher", "require_teacher",
    "remember_idempotent", "session_ends_at", "session_purchase_cost",
    "task_team_ids", "verify_password",
]
