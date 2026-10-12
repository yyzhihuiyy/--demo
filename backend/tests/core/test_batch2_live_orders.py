"""TASK-101 batch 2: control transitions, live actions, simulation, orders, fulfillment."""
from sqlalchemy.orm import sessionmaker

from app.core import sim
from app.core.lifecycle import recover_interrupted_sessions
from app.core.models import CashEntry, EventRow, OrderRow, SessionProductRow, SessionRow
from app.core.service import force_end_session, live_elapsed_seconds
from helpers import (
    act, build_isolated_client, control, get_session, live_state, login,
    prepared_session, publish_task, put_preparation, session_of_team, start_live,
)


def test_control_transitions_and_promotion_charged_once(client):
    teacher = login(client, "teacher")
    student = login(client, "a_host")
    prepared = prepared_session(client, teacher, student, "控制流转任务")
    sid = prepared["session_id"]

    before = get_session(client, student, sid)["metrics"]["cash_balance_cents"]
    assert before == 100000 - (20 * 1500 + 10 * 900)

    data = start_live(client, student, sid)
    assert data["status"] == "live"
    assert data["metrics"]["cash_balance_cents"] == before - 1000

    assert control(client, student, sid, "start").status_code == 409
    assert control(client, student, sid, "pause").status_code == 200
    assert live_state(client, student, sid)["status"] == "paused"
    assert control(client, student, sid, "resume").status_code == 200
    assert live_state(client, student, sid)["status"] == "live"
    assert control(client, student, sid, "end").status_code == 200

    response = control(client, student, sid, "start")
    assert response.status_code == 409 and response.json()["error"]["code"] == "SESSION_NOT_PREPARING"

    detail = get_session(client, student, sid)
    assert detail["session"]["status"] == "ended"
    assert detail["session"]["started_at"] and detail["session"]["ended_at"]
    assert detail["session"]["live_elapsed_seconds"] >= 0
    assert detail["metrics"]["cash_balance_cents"] == before - 1000

    teacher_control = control(client, teacher, sid, "pause")
    assert teacher_control.status_code == 403
    assert teacher_control.json()["error"]["code"] == "STUDENT_ACTION_REQUIRED"


def test_start_requires_checklist(client):
    teacher = login(client, "teacher")
    student = login(client, "a_host")
    task_id, _ = publish_task(client, teacher, "开播门槛任务")
    sid = session_of_team(client, student, task_id, 1)["id"]
    put_preparation(client, student, sid, 0, research=False, promotion_audience=False,
                    room_title=False)

    response = control(client, student, sid, "start")
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "CHECKLIST_FAILED"
    assert body["error"]["details"]["items"]

    prepared = prepared_session(client, teacher, student, "开播门槛完整任务")
    assert control(client, student, prepared["session_id"], "start").status_code == 200


def test_live_actions_validation_and_compliance(client):
    teacher = login(client, "teacher")
    student = login(client, "a_host")
    prepared = prepared_session(client, teacher, student, "直播操作任务")
    sid = prepared["session_id"]

    blocked = act(client, student, sid, "speech", {"text": "还没开播"})
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "SESSION_NOT_LIVE"

    start_live(client, student, sid)
    first = prepared["products"][0]

    selected = act(client, student, sid, "select_product",
                   {"session_product_id": first["id"]})
    assert selected.status_code == 200
    state = live_state(client, student, sid)
    assert state["current_product"]["id"] == first["id"]
    assert selected.json()["data"]["state_version"] == state["latest_event_id"]

    assert act(client, student, sid, "select_product",
               {"session_product_id": 99999}).status_code == 404
    assert act(client, student, sid, "speech", {"text": "  "}).status_code == 422

    ok = act(client, student, sid, "speech", {"text": "欢迎来到助农直播间，产地直采"})
    assert ok.status_code == 200
    violation = act(client, student, sid, "speech", {"text": "咱家是全网最低价，不信你去比"})
    assert violation.status_code == 200
    events = client.get(f"/api/sessions/{sid}/events", headers=student).json()["data"]
    violations = [e for e in events if e["type"] == "violation"]
    assert len(violations) == 1
    assert violations[0]["source"] == "rule" and "全网最低" in violations[0]["payload"]["hits"]

    assert act(client, student, sid, "announcement", {"text": ""}).status_code == 422
    assert act(client, student, sid, "announcement", {"text": "今晚新公告：整点抽奖"}).status_code == 200
    assert get_session(client, student, sid)["preparation"]["room"]["announcement"] == "今晚新公告：整点抽奖"

    assert act(client, student, sid, "issue_coupon").status_code == 200
    again = act(client, student, sid, "issue_coupon")
    assert again.status_code == 409 and again.json()["error"]["code"] == "COUPON_ALREADY_ISSUED"

    assert act(client, student, sid, "execute_script", {"script_id": "opening"}).status_code == 200
    repeat = act(client, student, sid, "execute_script", {"script_id": "opening"})
    assert repeat.status_code == 409 and repeat.json()["error"]["code"] == "SCRIPT_ALREADY_EXECUTED"
    assert act(client, student, sid, "execute_script", {"script_id": "nope"}).status_code == 404
    assert act(client, student, sid, "reply", {"question_event_id": 1, "text": "x"}).status_code == 404


def test_simulation_orders_stock_coupon_and_reply(tmp_path):
    client, engine = build_isolated_client(tmp_path)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    teacher = login(client, "teacher")
    student = login(client, "a_host")
    prepared = prepared_session(client, teacher, student, "仿真推进任务")
    sid = prepared["session_id"]
    start_live(client, student, sid)
    assert act(client, student, sid, "select_product",
               {"session_product_id": prepared["products"][0]["id"]}).status_code == 200
    assert act(client, student, sid, "issue_coupon").status_code == 200

    with factory() as db:
        session = db.get(SessionRow, sid)
        ticks = 0
        while ticks < 100 and (db.query(OrderRow).count() == 0
                               or db.query(EventRow).filter_by(
                                   session_id=sid, type="audience_question").count() == 0):
            sim.advance_session_tick(db, session)
            db.commit()
            ticks += 1
        assert db.query(OrderRow).count() >= 1

        orders = db.query(OrderRow).order_by(OrderRow.id).all()
        first = orders[0]
        assert first.discount_cents == 100
        assert first.amount_cents == first.qty * first.unit_sale_cents - 100
        assert first.amount_cents >= 1
        for order in orders[1:]:
            assert order.discount_cents == 0

        gmv_cash = db.query(CashEntry).filter_by(session_id=sid, kind="gmv").all()
        assert sum(e.amount_cents for e in gmv_cash) == sum(o.amount_cents for o in orders)

        for sp in db.query(SessionProductRow).filter_by(session_id=sid).all():
            assert sp.stock_qty >= 0
            sold = sum(o.qty for o in orders if o.session_product_id == sp.id)
            assert sold <= sp.purchased_qty

        assert session.coupon_active is False
        from app.core.models import TickRow
        assert db.query(TickRow).filter_by(session_id=sid).count() == session.tick_index
        questions = db.query(EventRow).filter_by(session_id=sid, type="audience_question").all()
        assert len(questions) >= 1

    metrics = get_session(client, student, sid)["metrics"]
    assert metrics["order_count"] == len(orders)
    assert metrics["gmv_cents"] == sum(o.amount_cents for o in orders)
    assert metrics["cumulative_entries"] > 0
    assert metrics["product_clicks"] > 0
    assert metrics["conversion_rate"] == round(len(orders) / metrics["cumulative_entries"], 4)

    question_id = questions[0].id
    reply = act(client, student, sid, "reply", {"question_event_id": question_id, "text": "48 小时内发货"})
    assert reply.status_code == 200
    duplicated = act(client, student, sid, "reply", {"question_event_id": question_id, "text": "再答一次"})
    assert duplicated.status_code == 409 and duplicated.json()["error"]["code"] == "ALREADY_REPLIED"
    refreshed = get_session(client, student, sid)["metrics"]
    assert refreshed["replied_question_count"] == 1
    assert refreshed["reply_rate"] == round(1 / len(questions), 4)

    assert control(client, student, sid, "pause").status_code == 200
    with factory() as db:
        session = db.get(SessionRow, sid)
        before_ticks = session.tick_index
        assert sim.advance_session_tick(db, session) is None
        db.commit()
        assert session.tick_index == before_ticks
    assert live_state(client, student, sid)["status"] == "paused"
    engine.dispose()


def test_orders_fulfillment_after_end(tmp_path):
    client, engine = build_isolated_client(tmp_path)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    teacher = login(client, "teacher")
    student = login(client, "a_host")
    other = login(client, "b_host")
    prepared = prepared_session(client, teacher, student, "履约签收任务")
    sid = prepared["session_id"]
    start_live(client, student, sid)
    act(client, student, sid, "select_product",
        {"session_product_id": prepared["products"][0]["id"]})

    with factory() as db:
        session = db.get(SessionRow, sid)
        ticks = 0
        while db.query(OrderRow).filter_by(session_id=sid).count() < 2 and ticks < 80:
            sim.advance_session_tick(db, session)
            db.commit()
            ticks += 1
        orders = db.query(OrderRow).filter_by(session_id=sid).order_by(OrderRow.id).all()
        assert len(orders) >= 2

    early = client.post(f"/api/orders/{orders[0].id}/ship", headers=student)
    assert early.status_code == 409 and early.json()["error"]["code"] == "SESSION_NOT_ENDED"

    assert control(client, student, sid, "end").status_code == 200
    listing = client.get(f"/api/sessions/{sid}/orders", headers=student).json()["data"]
    assert len(listing) == len(orders)
    pending = client.get(f"/api/sessions/{sid}/orders?status=pending_shipment",
                         headers=student).json()["data"]
    assert len(pending) == len(orders)

    forbidden = client.post(f"/api/orders/{orders[0].id}/ship", headers=other)
    assert forbidden.status_code == 403
    forbidden_teacher = client.post(f"/api/orders/{orders[0].id}/ship", headers=teacher)
    assert forbidden_teacher.status_code == 403

    assert client.post(f"/api/orders/{orders[0].id}/ship", headers=student).status_code == 200
    assert client.post(f"/api/orders/{orders[0].id}/sign", headers=student).status_code == 200
    assert client.post(f"/api/orders/{orders[0].id}/sign", headers=student).status_code == 409
    assert client.post(f"/api/orders/{orders[0].id}/ship", headers=student).status_code == 409

    assert client.post(f"/api/orders/{orders[1].id}/sign", headers=student).status_code == 409
    assert client.post(f"/api/orders/{orders[1].id}/ship", headers=student).status_code == 200

    metrics = get_session(client, student, sid)["metrics"]
    assert metrics["signed_order_count"] == 1
    signed = client.get(f"/api/sessions/{sid}/orders?status=signed",
                        headers=student).json()["data"]
    assert [o["id"] for o in signed] == [orders[0].id]
    engine.dispose()


def test_events_pagination_and_live_state(tmp_path):
    client, engine = build_isolated_client(tmp_path)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    teacher = login(client, "teacher")
    student = login(client, "a_host")
    prepared = prepared_session(client, teacher, student, "事件分页任务")
    sid = prepared["session_id"]
    start_live(client, student, sid)
    act(client, student, sid, "select_product", {"session_product_id": prepared["products"][0]["id"]})
    act(client, student, sid, "speech", {"text": "第一段口播"})
    act(client, student, sid, "speech", {"text": "第二段口播"})

    events = client.get(f"/api/sessions/{sid}/events", headers=student).json()["data"]
    ids = [e["id"] for e in events]
    assert ids == sorted(ids) and len(ids) >= 3
    state = live_state(client, student, sid)
    assert state["latest_event_id"] == ids[-1]

    window = client.get(f"/api/sessions/{sid}/events?after_id={ids[0]}&limit=2",
                        headers=student).json()["data"]
    assert [e["id"] for e in window] == ids[1:3]
    engine.dispose()


def test_recovery_pauses_live_and_force_end_records_rule_event(tmp_path):
    client, engine = build_isolated_client(tmp_path)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    teacher = login(client, "teacher")
    student = login(client, "a_host")
    prepared = prepared_session(client, teacher, student, "恢复与强制结束任务")
    sid = prepared["session_id"]
    start_live(client, student, sid)

    with factory() as db:
        assert recover_interrupted_sessions(db) == 1
        db.commit()
        session = db.get(SessionRow, sid)
        assert session.status == "paused"
        recovery = db.query(EventRow).filter_by(session_id=sid, type="system_recovery").all()
        assert len(recovery) == 1 and recovery[0].payload["action"] == "pause"
        assert recover_interrupted_sessions(db) == 0

        force_end_session(db, session, "deadline")
        db.commit()
        session = db.get(SessionRow, sid)
        assert session.status == "ended" and session.ended_at is not None
        ended = [e for e in db.query(EventRow).filter_by(session_id=sid).all()
                 if e.type == "control" and e.payload.get("action") == "end"]
        assert ended and ended[-1].source == "rule" and ended[-1].payload["reason"] == "deadline"
        assert live_elapsed_seconds(db, session) >= 0
    engine.dispose()


def test_two_team_accounts_share_one_live_session(client):
    teacher = login(client, "teacher")
    host = login(client, "a_host")
    control_user = login(client, "a_control")
    prepared = prepared_session(client, teacher, host, "多账号协作任务")
    sid = prepared["session_id"]
    start_live(client, host, sid)

    chosen = act(client, control_user, sid, "select_product",
                 {"session_product_id": prepared["products"][0]["id"]})
    assert chosen.status_code == 200
    spoken = act(client, host, sid, "speech", {"text": "主播讲解商品卖点"})
    assert spoken.status_code == 200

    events = client.get(f"/api/sessions/{sid}/events", headers=host).json()["data"]
    by_type = {e["type"]: e for e in events}
    assert by_type["select_product"]["actor_id"] != by_type["speech"]["actor_id"]
    assert live_state(client, control_user, sid)["current_product"]["id"] == prepared["products"][0]["id"]
