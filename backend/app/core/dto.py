"""ORM row to public DTO mapping helpers."""
from app.shared.schemas import (
    Grade, Order, Preparation, Product, Refund, Review, SessionProduct,
    Task, Team, TrainingEvent, TrainingSession, User,
)
from app.core.models import (
    Account, EventRow, GradeRow, OrderRow, ProductRow, RefundRow,
    ReviewRow, SessionRow, SessionProductRow, TeamRow, TaskRow,
)


def user_dto(row: Account) -> dict:
    return User.model_validate(row).model_dump(mode="json")


def team_dto(row: TeamRow) -> dict:
    return Team.model_validate(row).model_dump(mode="json")


def task_dto(row: TaskRow) -> dict:
    payload = {**(row.data or {}), "id": row.id, "class_id": row.class_id,
               "teacher_id": row.teacher_id, "status": row.status}
    return Task.model_validate(payload).model_dump(mode="json")


def product_dto(row: ProductRow) -> dict:
    return Product.model_validate({**(row.data or {}), "id": row.id}).model_dump(mode="json")


def session_dto(row: SessionRow) -> dict:
    return TrainingSession.model_validate({
        "id": row.id, "task_id": row.task_id, "team_id": row.team_id,
        "status": row.status, "rule_snapshot": row.rule_snapshot or {},
        "preparation_version": row.preparation_version,
        "initial_budget_cents": row.initial_budget_cents,
        "started_at": row.started_at, "ended_at": row.ended_at,
        "live_elapsed_seconds": row.live_elapsed_seconds,
        "current_product_id": row.current_product_id,
    }).model_dump(mode="json")


def session_product_dto(row: SessionProductRow) -> dict:
    return SessionProduct.model_validate(row).model_dump(mode="json")


def order_dto(row: OrderRow) -> dict:
    return Order.model_validate(row).model_dump(mode="json")


def refund_dto(row: RefundRow) -> dict:
    return Refund.model_validate(row).model_dump(mode="json")


def event_dto(row: EventRow) -> dict:
    return TrainingEvent.model_validate(row).model_dump(mode="json")


def review_dto(row: ReviewRow) -> dict | None:
    if row is None:
        return None
    payload = {**(row.data or {}), "id": row.id, "session_id": row.session_id}
    return Review.model_validate(payload).model_dump(mode="json")


def grade_dto(row: GradeRow) -> dict | None:
    if row is None:
        return None
    payload = {**(row.data or {}), "id": row.id, "session_id": row.session_id}
    return Grade.model_validate(payload).model_dump(mode="json")


def preparation_dto(session: SessionRow) -> dict:
    return Preparation.model_validate(session.preparation or {}).model_dump(mode="json")
