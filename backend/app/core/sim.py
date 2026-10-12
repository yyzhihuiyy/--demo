"""Deterministic rule-based live simulation; one tick advances one live session."""
import random

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.shared.schemas import Preparation
from app.core.models import EventRow, OrderRow, ProductRow, SessionRow, SessionProductRow, TickRow
from app.core.rules import (
    BUYER_LABELS, BUY_FROM_CLICK_RATIO, BUY_PROB_MAX, BUY_PROB_MIN,
    CLICK_PROB_BASE, CLICK_PROB_MAX, CLICK_PROB_MIN, COUPON_BUY_MULTIPLIER,
    ENTRY_BASE_MAX, ENTRY_BASE_MIN, INTERACTION_CAP, MIN_PAY_CENTS,
    ORDER_QTY_CHOICES, PRICE_FACTOR_MAX, PRICE_FACTOR_MIN, PROMOTION_ENTRY_BONUS,
    QUESTION_PROB_PER_TICK, REPLY_INTERACTION_WEIGHT, SIM_SEED,
    SPEECH_INTERACTION_WEIGHT, AUDIENCE_QUESTIONS,
)
from app.core.service import add_cash, append_event, now, deadline_passed, force_end_session


def _reference_price(db: Session, product_id: int) -> int:
    row = db.get(ProductRow, product_id)
    if row is None:
        return 0
    return int((row.data or {}).get("reference_price_cents", 0))


def advance_session_tick(db: Session, session: SessionRow) -> dict | None:
    if session.status != "live":
        return None
    if deadline_passed(session):
        force_end_session(db, session, "deadline")
        return None
    next_index = session.tick_index + 1
    rng = random.Random(f"{SIM_SEED}:{session.id}:{next_index}")
    rule = session.rule_snapshot or {}
    heat = float(rule.get("market_heat", 1) or 1)
    difficulty = float(rule.get("difficulty", 1) or 1)
    preparation = Preparation.model_validate(session.preparation or {})
    promotion_budget = preparation.promotion.budget_cents
    coupon_cents = preparation.coupon.discount_cents

    events = db.scalars(select(EventRow).where(EventRow.session_id == session.id)).all()
    speeches = len([e for e in events if e.type == "speech"])
    replies = len([e for e in events if e.type == "reply"])

    entries = max(0, int(rng.randint(ENTRY_BASE_MIN, ENTRY_BASE_MAX) * heat / difficulty)
                  + (PROMOTION_ENTRY_BONUS if promotion_budget > 0 else 0))

    clicks = 0
    orders = 0
    current = db.get(SessionProductRow, session.current_product_id) \
        if session.current_product_id is not None else None
    if current is not None and current.stock_qty > 0:
        reference = _reference_price(db, current.product_id) or current.cost_cents * 2
        price_ratio = current.sale_price_cents / max(1, reference)
        price_factor = min(PRICE_FACTOR_MAX, max(PRICE_FACTOR_MIN, 1.6 - 0.6 * price_ratio))
        interaction_factor = (1
                              + SPEECH_INTERACTION_WEIGHT * min(speeches, INTERACTION_CAP)
                              + REPLY_INTERACTION_WEIGHT * min(replies, INTERACTION_CAP))
        click_prob = min(CLICK_PROB_MAX, max(
            CLICK_PROB_MIN, CLICK_PROB_BASE * price_factor * interaction_factor))
        clicks = sum(1 for _ in range(entries) if rng.random() < click_prob)
        buy_prob = min(BUY_PROB_MAX, max(
            BUY_PROB_MIN,
            click_prob * BUY_FROM_CLICK_RATIO * (COUPON_BUY_MULTIPLIER if session.coupon_active else 1)))
        for _ in range(clicks):
            if current.stock_qty <= 0 or rng.random() >= buy_prob:
                continue
            qty = min(rng.choice(ORDER_QTY_CHOICES), current.stock_qty)
            gross = qty * current.sale_price_cents
            if session.coupon_active and coupon_cents > 0:
                amount = max(MIN_PAY_CENTS, gross - coupon_cents)
                discount = gross - amount
                session.coupon_active = False
            else:
                amount, discount = gross, 0
            order = OrderRow(session_id=session.id, session_product_id=current.id,
                             buyer_label=rng.choice(BUYER_LABELS), qty=qty,
                             unit_cost_cents=current.cost_cents,
                             unit_sale_cents=current.sale_price_cents,
                             discount_cents=discount, amount_cents=amount,
                             status="pending_shipment", created_at=now().isoformat())
            db.add(order)
            db.flush()
            current.stock_qty -= qty
            add_cash(db, session.id, "gmv", amount, "order", order.id)
            append_event(db, session.id, "order", "rule", {
                "order_id": order.id, "session_product_id": current.id,
                "title": current.title, "buyer_label": order.buyer_label,
                "qty": qty, "amount_cents": amount, "discount_cents": discount,
                "factors": {
                    "price_ratio": round(price_ratio, 3),
                    "price_factor": round(price_factor, 3),
                    "interaction_factor": round(interaction_factor, 3),
                    "coupon_used": discount > 0,
                    "promotion": promotion_budget > 0,
                },
            })
            orders += 1

    question = None
    if rng.random() < QUESTION_PROB_PER_TICK:
        question = append_event(db, session.id, "audience_question", "rule",
                                 {"question": rng.choice(AUDIENCE_QUESTIONS)}).payload

    db.add(TickRow(session_id=session.id, tick_index=next_index,
                   metrics={"entries": entries, "clicks": clicks, "orders": orders,
                            "question": question is not None, "online": entries},
                   created_at=now().isoformat()))
    session.tick_index = next_index
    db.flush()
    return {"tick_index": next_index, "entries": entries, "clicks": clicks, "orders": orders}
