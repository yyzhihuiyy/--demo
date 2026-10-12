"""Core-owned persistent business models; JSON stores versioned editable DTOs."""
from sqlalchemy import ForeignKey, JSON, String, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.shared.db import Base


class Account(Base):
    __tablename__ = 'core_accounts'
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True)
    password_hash: Mapped[str]
    role: Mapped[str]
    class_id: Mapped[int]
    active: Mapped[bool] = mapped_column(default=True)


class Token(Base):
    __tablename__ = 'core_tokens'
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('core_accounts.id'))
    expires_at: Mapped[str]


class Classroom(Base):
    __tablename__ = 'core_classrooms'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    teacher_id: Mapped[int] = mapped_column(ForeignKey('core_accounts.id'))


class TeamRow(Base):
    __tablename__ = 'core_teams'
    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int]
    name: Mapped[str]
    members: Mapped[list] = mapped_column(JSON, default=list)


class TaskRow(Base):
    __tablename__ = 'core_tasks'
    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int]
    teacher_id: Mapped[int] = mapped_column(ForeignKey('core_accounts.id'))
    status: Mapped[str] = mapped_column(default='draft')
    data: Mapped[dict] = mapped_column(JSON)


class ProductRow(Base):
    __tablename__ = 'core_products'
    id: Mapped[int] = mapped_column(primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)


class SessionRow(Base):
    __tablename__ = 'core_sessions'
    __table_args__ = (UniqueConstraint('task_id', 'team_id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey('core_tasks.id'))
    team_id: Mapped[int] = mapped_column(ForeignKey('core_teams.id'))
    status: Mapped[str] = mapped_column(default='preparing')
    rule_snapshot: Mapped[dict] = mapped_column(JSON)
    members_snapshot: Mapped[list] = mapped_column(JSON)
    preparation: Mapped[dict] = mapped_column(JSON)
    preparation_version: Mapped[int] = mapped_column(default=0)
    initial_budget_cents: Mapped[int]
    started_at: Mapped[str | None]
    ended_at: Mapped[str | None]
    live_elapsed_seconds: Mapped[int] = mapped_column(default=0)
    current_product_id: Mapped[int | None]
    tick_index: Mapped[int] = mapped_column(default=0)
    coupon_active: Mapped[bool] = mapped_column(default=False)


class SessionProductRow(Base):
    __tablename__ = 'core_session_products'
    __table_args__ = (UniqueConstraint('session_id', 'product_id'), CheckConstraint('stock_qty >= 0'), CheckConstraint('purchased_qty >= 0'))
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey('core_sessions.id'))
    product_id: Mapped[int] = mapped_column(ForeignKey('core_products.id'))
    positioning: Mapped[str]
    selling_points: Mapped[str]
    sale_price_cents: Mapped[int]
    sort_order: Mapped[int]
    title: Mapped[str]
    cost_cents: Mapped[int]
    purchased_qty: Mapped[int] = mapped_column(default=0)
    stock_qty: Mapped[int] = mapped_column(default=0)


class CashEntry(Base):
    __tablename__ = 'core_cash_entries'
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey('core_sessions.id'))
    kind: Mapped[str]
    amount_cents: Mapped[int]
    reference_type: Mapped[str]
    reference_id: Mapped[int | None]
    created_at: Mapped[str]


class EventRow(Base):
    __tablename__ = 'core_events'
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey('core_sessions.id'))
    type: Mapped[str]
    actor_id: Mapped[int | None] = mapped_column(ForeignKey('core_accounts.id'))
    source: Mapped[str]
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str]


class TickRow(Base):
    __tablename__ = 'core_ticks'
    __table_args__ = (UniqueConstraint('session_id', 'tick_index'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey('core_sessions.id'))
    tick_index: Mapped[int]
    metrics: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str]


class OrderRow(Base):
    __tablename__ = 'core_orders'
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey('core_sessions.id'))
    session_product_id: Mapped[int] = mapped_column(ForeignKey('core_session_products.id'))
    buyer_label: Mapped[str]
    qty: Mapped[int]
    unit_cost_cents: Mapped[int]
    unit_sale_cents: Mapped[int]
    discount_cents: Mapped[int]
    amount_cents: Mapped[int]
    status: Mapped[str] = mapped_column(default='pending_shipment')
    created_at: Mapped[str]


class RefundRow(Base):
    __tablename__ = 'core_refunds'
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey('core_orders.id'), unique=True)
    reason: Mapped[str]
    status: Mapped[str] = mapped_column(default='pending')
    handler_id: Mapped[int | None] = mapped_column(ForeignKey('core_accounts.id'))
    handling_note: Mapped[str] = mapped_column(default='')
    amount_cents: Mapped[int]


class ReviewRow(Base):
    __tablename__ = 'core_reviews'
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey('core_sessions.id'), unique=True)
    data: Mapped[dict] = mapped_column(JSON)


class GradeRow(Base):
    __tablename__ = 'core_grades'
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey('core_sessions.id'), unique=True)
    data: Mapped[dict] = mapped_column(JSON)


class CompetitionRow(Base):
    __tablename__ = 'core_competitions'
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey('core_tasks.id'), unique=True)
    title: Mapped[str]
    status: Mapped[str] = mapped_column(default='draft')
    rule_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    published_at: Mapped[str | None]


class IdempotencyRow(Base):
    __tablename__ = 'core_idempotency'
    __table_args__ = (UniqueConstraint('user_id', 'action', 'key'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('core_accounts.id'))
    action: Mapped[str]
    key: Mapped[str]
    payload_hash: Mapped[str]
    response: Mapped[dict] = mapped_column(JSON)
