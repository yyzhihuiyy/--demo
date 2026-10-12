"""Core business routes; /api prefix is added by the main entry."""
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.shared.auth import CurrentUser, DbSession
from app.shared.errors import AppError, success
from app.shared.schemas import (
    ActionRequest, AssortmentWrite, ControlRequest, Envelope, LoginRequest,
    LoginResponse, Preparation, PreparationWrite, PurchaseRequest, TaskWrite,
    TeamMember, User,
)
from app.core import dto, metrics, service
from app.core.access import check_session_access, now
from app.core.models import (
    Account, Classroom, CompetitionRow, EventRow, OrderRow, ProductRow,
    RefundRow, SessionProductRow, SessionRow, TeamRow, TaskRow, Token,
)
from app.core.rules import FORBIDDEN_TERMS, RULES_VERSION, TOKEN_TTL_HOURS
from app.core.seed import market_sample
from app.core.service import get_task, require_task_teacher, require_teacher

router = APIRouter(tags=["core"])


class TeamWrite(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    members: list[TeamMember] = Field(min_length=1)


@router.post("/auth/login")
def login(payload: LoginRequest, db: DbSession):
    account = db.scalars(select(Account).where(Account.username == payload.username)).first()
    if account is None or not service.verify_password(payload.password, account.password_hash):
        raise AppError(401, "INVALID_CREDENTIALS", "用户名或密码不正确")
    if not account.active:
        raise AppError(403, "ACCOUNT_DISABLED", "账号已停用")
    token = secrets.token_hex(32)
    db.add(Token(digest=hashlib.sha256(token.encode()).hexdigest(), user_id=account.id,
                 expires_at=(now() + timedelta(hours=TOKEN_TTL_HOURS)).isoformat()))
    db.commit()
    return success(LoginResponse(token=token, user=User.model_validate(account)))


@router.get("/auth/me", response_model=Envelope[User])
def me(user: CurrentUser):
    return success(user)


@router.get("/classroom")
def classroom(user: CurrentUser, db: DbSession):
    room = db.get(Classroom, user.class_id)
    if room is None:
        raise AppError(404, "CLASSROOM_NOT_FOUND", "班级不存在")
    teams = db.scalars(select(TeamRow).where(TeamRow.class_id == user.class_id)
                       .order_by(TeamRow.id)).all()
    students = db.scalars(select(Account).where(Account.class_id == user.class_id,
                                                Account.role == "student")
                          .order_by(Account.id)).all()
    return success({
        "classroom": {"id": room.id, "name": room.name, "teacher_id": room.teacher_id},
        "teams": [dto.team_dto(t) for t in teams],
        "students": [dto.user_dto(s) for s in students],
    })


def _validate_team_members(db, class_id: int, members: list[TeamMember]) -> None:
    for member in members:
        account = db.get(Account, member.user_id)
        if account is None or account.role != "student" or account.class_id != class_id:
            raise AppError(422, "MEMBER_INVALID", f"成员 {member.user_id} 不是本班学生")
    if len({m.user_id for m in members}) != len(members):
        raise AppError(422, "MEMBER_DUPLICATED", "小组成员不能重复")


@router.post("/teams")
def create_team(payload: TeamWrite, user: CurrentUser, db: DbSession):
    require_teacher(user)
    _validate_team_members(db, user.class_id, payload.members)
    row = TeamRow(class_id=user.class_id, name=payload.name,
                  members=[m.model_dump() for m in payload.members])
    db.add(row)
    db.commit()
    return success(dto.team_dto(row))


@router.put("/teams/{team_id}")
def update_team(team_id: int, payload: TeamWrite, user: CurrentUser, db: DbSession):
    require_teacher(user)
    row = db.get(TeamRow, team_id)
    if row is None or row.class_id != user.class_id:
        raise AppError(404, "TEAM_NOT_FOUND", "小组不存在")
    _validate_team_members(db, user.class_id, payload.members)
    for task in db.scalars(select(TaskRow).where(TaskRow.class_id == user.class_id,
                                                 TaskRow.status != "draft")).all():
        if team_id in service.task_team_ids(task):
            raise AppError(409, "TEAM_LOCKED", "小组已参加发布任务，成员已冻结")
    row.name = payload.name
    row.members = [m.model_dump() for m in payload.members]
    db.commit()
    return success(dto.team_dto(row))


def _validate_task_teams(db, class_id: int, team_ids: list[int]) -> None:
    if not team_ids:
        return
    if len(set(team_ids)) != len(team_ids):
        raise AppError(422, "TEAM_DUPLICATED", "任务小组不能重复")
    for team_id in team_ids:
        team = db.get(TeamRow, team_id)
        if team is None or team.class_id != class_id:
            raise AppError(422, "TEAM_INVALID", f"小组 {team_id} 不属于本班级")
        if not team.members:
            raise AppError(422, "TEAM_EMPTY", f"小组 {team_id} 没有成员")


@router.get("/tasks")
def list_tasks(user: CurrentUser, db: DbSession):
    query = select(TaskRow).where(TaskRow.class_id == user.class_id).order_by(TaskRow.id)
    if user.role != "teacher":
        query = query.where(TaskRow.status != "draft")
    rows = db.scalars(query).all()
    return success([dto.task_dto(r) for r in rows])


@router.post("/tasks")
def create_task(payload: TaskWrite, user: CurrentUser, db: DbSession):
    require_teacher(user)
    _validate_task_teams(db, user.class_id, payload.team_ids)
    if now() >= payload.ends_at:
        raise AppError(422, "TASK_EXPIRED", "任务截止时间必须晚于当前时间")
    data = payload.model_dump(mode="json")
    data["rules_version"] = RULES_VERSION
    row = TaskRow(class_id=user.class_id, teacher_id=user.id, status="draft", data=data)
    db.add(row)
    db.commit()
    return success(dto.task_dto(row))


@router.get("/tasks/{task_id}")
def get_task_detail(task_id: int, user: CurrentUser, db: DbSession):
    task = get_task(db, task_id)
    if task.class_id != user.class_id:
        raise AppError(403, "TASK_FORBIDDEN", "无权查看该任务")
    if user.role != "teacher" and task.status == "draft":
        raise AppError(404, "TASK_NOT_FOUND", "任务不存在")
    query = select(SessionRow).where(SessionRow.task_id == task.id).order_by(SessionRow.team_id)
    if user.role != "teacher":
        team_ids = [t.id for t in db.scalars(select(TeamRow).where(TeamRow.class_id == user.class_id)).all()
                    if any(m["user_id"] == user.id for m in (t.members or []))]
        query = query.where(SessionRow.team_id.in_(team_ids or [0]))
    sessions = db.scalars(query).all()
    return success({"task": dto.task_dto(task),
                    "sessions": [dto.session_dto(s) for s in sessions]})


@router.put("/tasks/{task_id}")
def update_task(task_id: int, payload: TaskWrite, user: CurrentUser, db: DbSession):
    task = get_task(db, task_id)
    require_task_teacher(user, task)
    if task.status != "draft":
        raise AppError(409, "TASK_LOCKED", "任务已发布，不能再编辑")
    _validate_task_teams(db, task.class_id, payload.team_ids)
    if now() >= payload.ends_at:
        raise AppError(422, "TASK_EXPIRED", "任务截止时间必须晚于当前时间")
    data = payload.model_dump(mode="json")
    data["rules_version"] = RULES_VERSION
    task.data = data
    db.commit()
    return success(dto.task_dto(task))


@router.post("/tasks/{task_id}/publish")
def publish_task(task_id: int, user: CurrentUser, db: DbSession):
    task = get_task(db, task_id)
    require_task_teacher(user, task)
    if task.status != "draft":
        raise AppError(409, "TASK_LOCKED", "任务已发布或已结束")
    if not service.task_team_ids(task):
        raise AppError(422, "TEAMS_REQUIRED", "发布前请先选择参赛小组")
    _validate_task_teams(db, task.class_id, service.task_team_ids(task))
    if now() >= _task_ends_at(task):
        raise AppError(409, "TASK_EXPIRED", "任务已过期，不能发布")
    session_ids = service.publish_task_sessions(db, task)
    competition = db.scalars(select(CompetitionRow).where(CompetitionRow.task_id == task.id)).first()
    if competition is not None and competition.status == "draft":
        competition.status = "published"
        competition.published_at = now().isoformat()
        competition.rule_snapshot = service.build_rule_snapshot(task)
    db.commit()
    return success({"task": dto.task_dto(task), "session_ids": session_ids})


def _task_ends_at(task: TaskRow) -> datetime:
    return datetime.fromisoformat((task.data or {})["ends_at"])


@router.get("/products")
def list_products(user: CurrentUser, db: DbSession):
    rows = db.scalars(select(ProductRow).order_by(ProductRow.id)).all()
    return success([dto.product_dto(r) for r in rows])


@router.get("/market-sample")
def get_market_sample(user: CurrentUser):
    return success(market_sample())


def _session_products(db, session_id: int) -> list[SessionProductRow]:
    return db.scalars(select(SessionProductRow).where(
        SessionProductRow.session_id == session_id)
        .order_by(SessionProductRow.sort_order, SessionProductRow.id)).all()


@router.get("/sessions/{session_id}")
def session_detail(session_id: int, user: CurrentUser, db: DbSession):
    session = check_session_access(user, session_id, db)
    task = get_task(db, session.task_id)
    status = session.status
    return success({
        "session": dto.session_dto(session),
        "preparation": dto.preparation_dto(session),
        "products": [dto.session_product_dto(sp) for sp in _session_products(db, session_id)],
        "metrics": metrics.compute_metrics(db, session).model_dump(mode="json"),
        "capabilities": {
            "edit_preparation": status == "preparing",
            "edit_assortment": status == "preparing",
            "purchase": status == "preparing",
            "checklist": status == "preparing",
            "control": status in ("preparing", "live", "paused"),
            "live_actions": status in ("live", "paused"),
            "fulfill_orders": status == "ended",
            "edit_review": status == "ended",
            "submit_review": status == "ended",
        },
    })


def _require_status(session, allowed: tuple[str, ...], code: str, message: str):
    if session.status not in allowed:
        raise AppError(409, code, message)
    return session


@router.put("/sessions/{session_id}/preparation")
def save_preparation(session_id: int, payload: PreparationWrite,
                     user: CurrentUser, db: DbSession):
    session = check_session_access(user, session_id, db, write=True)
    _require_status(session, ("preparing",), "SESSION_NOT_PREPARING",
                    "仅准备阶段可编辑准备内容")
    if payload.expected_version != session.preparation_version:
        raise AppError(409, "PREPARATION_VERSION_CONFLICT",
                       "准备内容已被组员更新，请刷新后重试",
                       {"current_version": session.preparation_version})
    catalog_ids = set(db.scalars(select(ProductRow.id)).all())
    for segment in payload.script:
        if segment.product_id is not None and segment.product_id not in catalog_ids:
            raise AppError(422, "UNKNOWN_PRODUCT", f"脚本引用的商品 {segment.product_id} 不存在")
    purchase_cost = service.session_purchase_cost(db, session_id)
    if purchase_cost + payload.promotion.budget_cents > session.initial_budget_cents:
        raise AppError(409, "BUDGET_EXCEEDED",
                       "投流预算超出剩余可用资金",
                       {"purchase_cost_cents": purchase_cost,
                        "promotion_budget_cents": payload.promotion.budget_cents,
                        "initial_budget_cents": session.initial_budget_cents})
    preparation = payload.model_dump(mode="json", exclude={"expected_version"})
    session.preparation = preparation
    session.preparation_version += 1
    db.commit()
    return success({"preparation": preparation, "version": session.preparation_version})


@router.put("/sessions/{session_id}/assortment")
def save_assortment(session_id: int, payload: AssortmentWrite,
                    user: CurrentUser, db: DbSession):
    session = check_session_access(user, session_id, db, write=True)
    _require_status(session, ("preparing",), "SESSION_NOT_PREPARING",
                    "仅准备阶段可编辑货盘")
    items = payload.items
    if len({item.product_id for item in items}) != len(items):
        raise AppError(422, "PRODUCT_DUPLICATED", "货盘内商品不能重复")
    existing = {sp.product_id: sp for sp in _session_products(db, session_id)}
    keep_ids = {item.product_id for item in items}
    for product_id, sp in existing.items():
        if product_id not in keep_ids and sp.purchased_qty > 0:
            raise AppError(409, "PURCHASED_ITEM_REMOVAL",
                           f"商品「{sp.title}」已采购，不能从货盘移除")
    for item in items:
        product = db.get(ProductRow, item.product_id)
        if product is None:
            raise AppError(422, "UNKNOWN_PRODUCT", f"商品 {item.product_id} 不存在")
        sp = existing.get(item.product_id)
        if sp is None:
            db.add(SessionProductRow(
                session_id=session_id, product_id=item.product_id,
                positioning=item.positioning, selling_points=item.selling_points,
                sale_price_cents=item.sale_price_cents, sort_order=item.sort_order,
                title=product.data["title"], cost_cents=product.data["cost_cents"],
                purchased_qty=0, stock_qty=0))
        else:
            sp.positioning = item.positioning
            sp.selling_points = item.selling_points
            sp.sale_price_cents = item.sale_price_cents
            sp.sort_order = item.sort_order
    for product_id, sp in list(existing.items()):
        if product_id not in keep_ids:
            db.delete(sp)
    db.commit()
    return success({"products": [dto.session_product_dto(sp)
                                 for sp in _session_products(db, session_id)]})


@router.post("/sessions/{session_id}/purchases")
def create_purchase(session_id: int, payload: PurchaseRequest, user: CurrentUser, db: DbSession,
                    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None):
    session = check_session_access(user, session_id, db, write=True)
    _require_status(session, ("preparing",), "SESSION_NOT_PREPARING",
                    "仅准备阶段可追加采购")
    action = f"session:{session_id}:purchase"
    body = payload.model_dump(mode="json")
    replay = service.idempotent_response(db, user, action, idempotency_key,
                                          service.fingerprint(body))
    if replay is not None:
        return success(replay)
    sp_rows = {sp.id: sp for sp in _session_products(db, session_id)}
    for item in payload.items:
        if item.session_product_id not in sp_rows:
            raise AppError(422, "SESSION_PRODUCT_INVALID",
                           f"货盘项 {item.session_product_id} 不属于本场次")
    cost = sum(sp_rows[i.session_product_id].cost_cents * i.qty for i in payload.items)
    purchase_cost = service.session_purchase_cost(db, session_id)
    preparation = Preparation.model_validate(session.preparation or {})
    promotion_budget = preparation.promotion.budget_cents
    if purchase_cost + promotion_budget + cost > session.initial_budget_cents:
        raise AppError(409, "BUDGET_EXCEEDED", "采购金额超出预算",
                       {"purchase_cost_cents": purchase_cost + cost,
                        "promotion_budget_cents": promotion_budget,
                        "initial_budget_cents": session.initial_budget_cents})
    for item in payload.items:
        sp = sp_rows[item.session_product_id]
        sp.purchased_qty += item.qty
        sp.stock_qty += item.qty
        service.add_cash(db, session_id, "purchase", -(sp.cost_cents * item.qty),
                         "session_product", sp.id)
    products = [dto.session_product_dto(sp) for sp in _session_products(db, session_id)]
    cash_balance = metrics.compute_metrics(db, session).cash_balance_cents
    response = {"products": products, "cash_balance_cents": cash_balance}
    service.remember_idempotent(db, user, action, idempotency_key,
                                service.fingerprint(body), response)
    db.commit()
    return success(response)


@router.get("/sessions/{session_id}/checklist")
def session_checklist(session_id: int, user: CurrentUser, db: DbSession):
    session = check_session_access(user, session_id, db)
    task = get_task(db, session.task_id)
    checklist = metrics.build_checklist(db, session, task)
    return success(checklist.model_dump(mode="json"))


def _student_session(user: CurrentUser, session_id: int, db: DbSession):
    session = check_session_access(user, session_id, db)
    if user.role == "teacher":
        raise AppError(403, "STUDENT_ACTION_REQUIRED", "经营操作须由本组学生完成")
    return session


def _latest_event_id(db, session_id: int) -> int:
    return db.scalar(select(func.max(EventRow.id)).where(EventRow.session_id == session_id)) or 0


@router.post("/sessions/{session_id}/control")
def session_control(session_id: int, payload: ControlRequest, user: CurrentUser, db: DbSession):
    session = _student_session(user, session_id, db)
    if session.status in ("submitted", "graded"):
        raise AppError(409, "SESSION_LOCKED", "场次已提交，经营数据已锁定")
    task = get_task(db, session.task_id)
    service.control_session(db, session, task, payload.action, user.id)
    db.commit()
    return success({"status": session.status,
                    "metrics": metrics.compute_metrics(db, session).model_dump(mode="json")})


@router.post("/sessions/{session_id}/actions")
def session_action(session_id: int, payload: ActionRequest, user: CurrentUser, db: DbSession):
    session = check_session_access(user, session_id, db, write=True)
    preparation = Preparation.model_validate(session.preparation or {})
    type_ = payload.type
    body = payload.payload or {}

    if type_ == "select_product":
        _require_status(session, ("live", "paused"), "SESSION_NOT_ACTIVE",
                        "仅直播中或暂停时可切换讲解商品")
        sp = db.get(SessionProductRow, body.get("session_product_id"))
        if sp is None or sp.session_id != session_id:
            raise AppError(404, "SESSION_PRODUCT_NOT_FOUND", "讲解商品不在本场货盘")
        session.current_product_id = sp.id
        event = service.append_event(db, session_id, "select_product", "manual",
                                     {"session_product_id": sp.id, "title": sp.title}, user.id)
    elif type_ == "issue_coupon":
        _require_status(session, ("live",), "SESSION_NOT_LIVE", "仅直播中可发放优惠券")
        issued = db.scalars(select(EventRow.id).where(
            EventRow.session_id == session_id, EventRow.type == "issue_coupon")).first()
        if issued is not None:
            raise AppError(409, "COUPON_ALREADY_ISSUED", "本场优惠券只能发放一次")
        session.coupon_active = True
        event = service.append_event(db, session_id, "issue_coupon", "manual",
                                     {"discount_cents": preparation.coupon.discount_cents}, user.id)
    elif type_ == "announcement":
        _require_status(session, ("live",), "SESSION_NOT_LIVE", "仅直播中可更新公告")
        text = str(body.get("text", "")).strip()
        if not text:
            raise AppError(422, "EMPTY_TEXT", "公告内容不能为空")
        preparation.room.announcement = text
        session.preparation = preparation.model_dump(mode="json")
        event = service.append_event(db, session_id, "announcement", "manual",
                                     {"text": text}, user.id)
    elif type_ == "speech":
        _require_status(session, ("live",), "SESSION_NOT_LIVE", "仅直播中可推送口播")
        text = str(body.get("text", "")).strip()
        if not text:
            raise AppError(422, "EMPTY_TEXT", "口播内容不能为空")
        event = service.append_event(db, session_id, "speech", "manual",
                                     {"text": text}, user.id)
        hits = [term for term in FORBIDDEN_TERMS if term in text]
        if hits:
            service.append_event(db, session_id, "violation", "rule",
                                 {"hits": hits, "text": text,
                                  "message": "口播包含教学合规禁用词，已记录违规证据"}, None)
    elif type_ == "reply":
        _require_status(session, ("live",), "SESSION_NOT_LIVE", "仅直播中可回复观众")
        text = str(body.get("text", "")).strip()
        if not text:
            raise AppError(422, "EMPTY_TEXT", "回复内容不能为空")
        question = db.get(EventRow, body.get("question_event_id"))
        if question is None or question.session_id != session_id or question.type != "audience_question":
            raise AppError(404, "QUESTION_NOT_FOUND", "须引用本场的观众咨询")
        answered = db.scalars(select(EventRow.payload).where(
            EventRow.session_id == session_id, EventRow.type == "reply")).all()
        if question.id in [p.get("question_event_id") for p in answered]:
            raise AppError(409, "ALREADY_REPLIED", "该咨询已有回复")
        event = service.append_event(db, session_id, "reply", "manual",
                                     {"question_event_id": question.id, "text": text,
                                      "question": (question.payload or {}).get("question", "")},
                                     user.id)
    elif type_ == "execute_script":
        _require_status(session, ("live",), "SESSION_NOT_LIVE", "仅直播中可执行脚本")
        script_id = body.get("script_id")
        segment = next((seg for seg in preparation.script if seg.id == script_id), None)
        if segment is None:
            raise AppError(404, "SCRIPT_NOT_FOUND", "脚本段落不存在")
        executed = db.scalars(select(EventRow.payload).where(
            EventRow.session_id == session_id, EventRow.type == "execute_script")).all()
        if script_id in [p.get("script_id") for p in executed]:
            raise AppError(409, "SCRIPT_ALREADY_EXECUTED", "该脚本段落已执行")
        event = service.append_event(db, session_id, "execute_script", "manual",
                                     {"script_id": segment.id, "kind": segment.kind,
                                      "text": segment.text}, user.id)
    else:
        raise AppError(422, "ACTION_TYPE_INVALID", "不支持的直播操作")
    db.commit()
    return success({"event": dto.event_dto(event),
                    "state_version": _latest_event_id(db, session_id)})


@router.get("/sessions/{session_id}/live-state")
def session_live_state(session_id: int, user: CurrentUser, db: DbSession):
    session = check_session_access(user, session_id, db)
    current = db.get(SessionProductRow, session.current_product_id) \
        if session.current_product_id is not None else None
    return success({
        "status": session.status,
        "current_product": dto.session_product_dto(current) if current else None,
        "metrics": metrics.compute_metrics(db, session).model_dump(mode="json"),
        "latest_event_id": _latest_event_id(db, session_id),
    })


@router.get("/sessions/{session_id}/events")
def session_events(session_id: int, user: CurrentUser, db: DbSession,
                   after_id: int = 0, limit: int = 100):
    session = check_session_access(user, session_id, db)
    limit = max(1, min(limit, 500))
    rows = db.scalars(select(EventRow).where(
        EventRow.session_id == session_id, EventRow.id > after_id)
        .order_by(EventRow.id).limit(limit)).all()
    return success([dto.event_dto(r) for r in rows])


@router.get("/sessions/{session_id}/orders")
def session_orders(session_id: int, user: CurrentUser, db: DbSession,
                   status: str | None = None):
    session = check_session_access(user, session_id, db)
    query = select(OrderRow).where(OrderRow.session_id == session_id).order_by(OrderRow.id)
    if status is not None:
        query = query.where(OrderRow.status == status)
    return success([dto.order_dto(r) for r in db.scalars(query).all()])


def _order_for_fulfillment(db, user: CurrentUser, order_id: int):
    order = db.get(OrderRow, order_id)
    if order is None:
        raise AppError(404, "ORDER_NOT_FOUND", "订单不存在")
    session = check_session_access(user, order.session_id, db, write=True)
    if session.status != "ended":
        raise AppError(409, "SESSION_NOT_ENDED", "直播结束后才能处理订单履约")
    return order


@router.post("/orders/{order_id}/ship")
def ship_order(order_id: int, user: CurrentUser, db: DbSession):
    order = _order_for_fulfillment(db, user, order_id)
    if order.status != "pending_shipment":
        raise AppError(409, "ORDER_STATUS_INVALID", "仅待发货订单可发货")
    pending = db.scalars(select(RefundRow).where(
        RefundRow.order_id == order.id, RefundRow.status == "pending")).first()
    if pending is not None:
        raise AppError(409, "REFUND_PENDING", "该订单有待处理退款，不能发货")
    order.status = "shipped"
    db.commit()
    return success(dto.order_dto(order))


@router.post("/orders/{order_id}/sign")
def sign_order(order_id: int, user: CurrentUser, db: DbSession):
    order = _order_for_fulfillment(db, user, order_id)
    if order.status != "shipped":
        raise AppError(409, "ORDER_STATUS_INVALID", "仅已发货订单可签收")
    order.status = "signed"
    db.commit()
    return success(dto.order_dto(order))


from app.core.closeout import router as closeout_router
router.include_router(closeout_router)
