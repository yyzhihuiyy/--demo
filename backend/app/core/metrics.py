"""Unified metrics summary, start checklist and objective scoring."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.shared.schemas import Checklist, ChecklistItem, Metrics, Preparation, ScoreBreakdown
from app.core.models import CashEntry, EventRow, OrderRow, RefundRow, SessionRow, TickRow, TaskRow
from app.core.dto import preparation_dto


def task_data(task: TaskRow) -> dict:
    return task.data or {}


def compute_metrics(db: Session, session: SessionRow) -> Metrics:
    sid = session.id
    orders = db.scalars(select(OrderRow).where(OrderRow.session_id == sid)).all()
    refunds = db.scalars(select(RefundRow).where(RefundRow.order_id.in_(
        [o.id for o in orders] or [0]))).all() if orders else []
    entries = db.scalars(select(CashEntry).where(CashEntry.session_id == sid)).all()
    events = db.scalars(select(EventRow).where(EventRow.session_id == sid)).all()
    ticks = db.scalars(select(TickRow).where(TickRow.session_id == sid)
                      .order_by(TickRow.tick_index)).all()

    gmv = sum(o.amount_cents for o in orders)
    approved_refunds = [r for r in refunds if r.status == "approved"]
    refund_cents = sum(r.amount_cents for r in approved_refunds)
    net_sales = gmv - refund_cents
    promotion_spend = -sum(e.amount_cents for e in entries if e.kind == "promotion")
    cash_balance = session.initial_budget_cents + sum(e.amount_cents for e in entries)
    sold_cost = sum(o.unit_cost_cents * o.qty for o in orders if o.status != "refunded")
    profit = net_sales - sold_cost - promotion_spend

    order_count = len(orders)
    refunded_order_count = len([o for o in orders if o.status == "refunded"])
    signed_order_count = len([o for o in orders if o.status == "signed"])
    cumulative_entries = sum(int((t.metrics or {}).get("entries", 0)) for t in ticks)
    product_clicks = sum(int((t.metrics or {}).get("clicks", 0)) for t in ticks)
    online_count = int((ticks[-1].metrics or {}).get("entries", 0)) if ticks else 0
    questions = [e for e in events if e.type == "audience_question"]
    replied = {e.payload.get("question_event_id") for e in events
              if e.type == "reply" and e.payload.get("question_event_id") is not None}
    replied_count = len([q for q in questions if q.id in replied])
    violation_count = len([e for e in events if e.type == "violation"])

    conversion = round(order_count / cumulative_entries, 4) if cumulative_entries else None
    reply_rate = round(replied_count / len(questions), 4) if questions else None
    return Metrics(
        gmv_cents=gmv, refund_cents=refund_cents, net_sales_cents=net_sales,
        profit_cents=profit, cash_balance_cents=cash_balance,
        promotion_spend_cents=promotion_spend, order_count=order_count,
        refunded_order_count=refunded_order_count, online_count=online_count,
        cumulative_entries=cumulative_entries, product_clicks=product_clicks,
        audience_question_count=len(questions), replied_question_count=replied_count,
        violation_count=violation_count, signed_order_count=signed_order_count,
        conversion_rate=conversion, reply_rate=reply_rate,
    )


def build_checklist(db: Session, session: SessionRow, task: TaskRow) -> Checklist:
    from app.core.models import SessionProductRow
    prep = Preparation.model_validate(preparation_dto(session))
    sp_rows = db.scalars(select(SessionProductRow).where(
        SessionProductRow.session_id == session.id).order_by(SessionProductRow.sort_order)).all()
    in_stock = [sp for sp in sp_rows if sp.purchased_qty > 0 and sp.stock_qty > 0]
    assortment_ids = {sp.product_id for sp in sp_rows}

    research = prep.research
    script = prep.script
    kinds = {seg.kind for seg in script}
    product_segments_ok = all(
        seg.product_id in assortment_ids
        for seg in script if seg.kind == "product" and seg.product_id is not None)
    script_ok = (
        {"opening", "product", "interaction", "closing"} <= kinds
        and all(seg.text.strip() for seg in script)
        and product_segments_ok
    )
    items = [
        ChecklistItem(key="research", passed=bool(research.audience.strip() and research.selection_reason.strip()),
                      message="完成市场调研：填写目标人群与选品依据",
                      target="research"),
        ChecklistItem(key="assortment", passed=bool(in_stock),
                      message="货盘已保存且至少一件商品完成采购并有库存",
                      target="assortment"),
        ChecklistItem(key="script", passed=script_ok,
                      message="脚本包含开场、讲解、互动、收尾四类非空话术，讲解段关联货盘商品",
                      target="script"),
        ChecklistItem(key="promotion", passed=bool(prep.promotion.audience.strip()),
                      message="填写投流受众（投流预算可为 0）",
                      target="promotion"),
        ChecklistItem(key="room", passed=bool(prep.room.title.strip()),
                      message="填写直播间标题", target="room"),
    ]
    return Checklist(items=items, can_start=all(i.passed for i in items) and session.status == "preparing")


def compute_breakdown(db: Session, session: SessionRow, task: TaskRow,
                      review_data: dict | None) -> tuple[ScoreBreakdown, dict]:
    data = task_data(task)
    weights = data.get("score_weights") or {}
    metrics = compute_metrics(db, session)
    prep = Preparation.model_validate(preparation_dto(session))
    checklist = build_checklist(db, session, task)
    events = db.scalars(select(EventRow).where(EventRow.session_id == session.id)).all()

    prep_ratio = (len([i for i in checklist.items if i.passed]) / len(checklist.items)
                  if checklist.items else 0.0)
    prep_kinds = {seg.kind for seg in prep.script}
    executed_ids = {e.payload.get("script_id") for e in events if e.type == "execute_script"}
    executed_kinds = {seg.kind for seg in prep.script if seg.id in executed_ids}
    script_ratio = (len(executed_kinds & prep_kinds) / len(prep_kinds)) if prep_kinds else 0.0
    process = round(prep_ratio * 50 + script_ratio * 50, 2)

    target_gmv = int(data.get("target_gmv_cents") or 0)
    business = round(max(0.0, min(metrics.net_sales_cents / target_gmv, 1.0)) * 100, 2) if target_gmv else 0.0

    order_evidence = {"order_count": metrics.order_count}
    if metrics.order_count:
        terminal = metrics.signed_order_count + metrics.refunded_order_count
        service_orders = round(terminal / metrics.order_count * 50, 2)
    else:
        service_orders = 0.0
        order_evidence["note"] = "无订单样本，该部分计 0"
    question_evidence = {"question_count": metrics.audience_question_count}
    if metrics.audience_question_count:
        service_questions = round(metrics.replied_question_count / metrics.audience_question_count * 50, 2)
    else:
        service_questions = 0.0
        question_evidence["note"] = "无观众提问样本，该部分计 0"
    service = round(service_orders + service_questions, 2)

    compliance = max(0.0, 100 - 20 * metrics.violation_count)

    analysis = (review_data or {}).get("analysis", "")
    improvements = (review_data or {}).get("improvements", "")
    review = (50 if str(analysis).strip() else 0) + (50 if str(improvements).strip() else 0)

    objective = round(
        process * float(weights.get("process", 25)) / 100
        + business * float(weights.get("business", 25)) / 100
        + service * float(weights.get("service", 20)) / 100
        + compliance * float(weights.get("compliance", 15)) / 100
        + review * float(weights.get("review", 15)) / 100, 2)
    breakdown = ScoreBreakdown(process=process, business=business, service=service,
                                compliance=compliance, review=review,
                                objective_score=objective)
    evidence = {
        "process": {"checklist_passed": len([i for i in checklist.items if i.passed]),
                    "checklist_total": len(checklist.items),
                    "executed_script_kinds": sorted(executed_kinds & prep_kinds)},
        "business": {"net_sales_cents": metrics.net_sales_cents, "target_gmv_cents": target_gmv},
        "service": {"orders": order_evidence, "questions": question_evidence},
        "compliance": {"violation_count": metrics.violation_count},
        "review": {"analysis_filled": bool(str(analysis).strip()),
                   "improvements_filled": bool(str(improvements).strip())},
    }
    return breakdown, evidence


def total_score(objective: float, subjective: float | None) -> float | None:
    if subjective is None:
        return None
    return round(objective * 0.7 + subjective * 0.3, 2)
