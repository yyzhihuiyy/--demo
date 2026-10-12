"""TASK-101 batch 1: real login, idempotent seed, tasks, preparation, assortment, purchases."""
from sqlalchemy.orm import sessionmaker

from app.core.models import SessionRow, TaskRow
from app.core.seed import seed_demo
from helpers import (
    assortment_item, build_isolated_client, get_session, login, post_purchase,
    prepared_session, publish_task, put_assortment, put_preparation, session_of_team,
    task_payload,
)


def test_login_issues_token_and_me_roundtrip(client):
    headers = login(client, "a_host")
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    data = me.json()["data"]
    assert data["username"] == "a_host" and data["role"] == "student" and data["class_id"] == 1
    assert "password" not in data and "password_hash" not in data


def test_login_rejects_wrong_password(client):
    response = client.post("/api/auth/login", json={"username": "a_host", "password": "wrong"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"
    response = client.post("/api/auth/login", json={"username": "ghost", "password": "demo1234"})
    assert response.status_code == 401


def test_seed_is_idempotent(tmp_path):
    client, engine = build_isolated_client(tmp_path)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        seed_demo(db)
        db.commit()
        assert db.query(TaskRow).count() == 1
        assert db.query(SessionRow).count() == 2
        task = db.get(TaskRow, 1)
        assert task.status == "published"
        sessions = db.query(SessionRow).order_by(SessionRow.id).all()
        assert [s.status for s in sessions] == ["preparing", "preparing"]
        assert [m["position"] for m in sessions[0].members_snapshot] == ["host", "control", "service"]
    teacher = login(client, "teacher")
    products = client.get("/api/products", headers=teacher).json()["data"]
    assert len(products) == 8 and products[0]["supplier"] == "助农合作社"
    engine.dispose()


def test_classroom_shape_and_no_secret_fields(client):
    headers = login(client, "a_host")
    data = client.get("/api/classroom", headers=headers).json()["data"]
    assert data["classroom"]["name"] == "直播电商实训一班"
    assert {t["id"] for t in data["teams"]} == {1, 2}
    assert all("password" not in s and s["role"] == "student" for s in data["students"])
    market = client.get("/api/market-sample", headers=headers).json()["data"]
    assert market["source"] == "sample" and market["categories"] and market["audience"]


def test_task_lifecycle_roles_and_session_visibility(client):
    teacher = login(client, "teacher")
    student = login(client, "a_host")
    other = login(client, "b_host")

    denied = client.post("/api/tasks", json=task_payload("学生越权任务"), headers=student)
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "TEACHER_REQUIRED"

    task_id, session_ids = publish_task(client, teacher, "任务流转验证")
    assert len(session_ids) == 2

    student_tasks = client.get("/api/tasks", headers=student).json()["data"]
    assert task_id in {t["id"] for t in student_tasks}

    detail = client.get(f"/api/tasks/{task_id}", headers=student).json()["data"]
    own = [s for s in detail["sessions"] if s["team_id"] == 1]
    assert len(detail["sessions"]) == 1 and own[0]["status"] == "preparing"

    other_detail = client.get(f"/api/tasks/{task_id}", headers=other).json()["data"]
    assert {s["team_id"] for s in other_detail["sessions"]} == {2}

    cross = client.get(f"/api/sessions/{own[0]['id']}", headers=other)
    assert cross.status_code == 403 and cross.json()["error"]["code"] == "SESSION_FORBIDDEN"

    republish = client.post(f"/api/tasks/{task_id}/publish", headers=teacher)
    assert republish.status_code == 409
    edit = client.put(f"/api/tasks/{task_id}", json=task_payload("改"), headers=teacher)
    assert edit.status_code == 409


def test_preparation_save_conflict_and_locking(client):
    teacher = login(client, "teacher")
    student = login(client, "a_host")
    task_id, _ = publish_task(client, teacher, "准备版本验证")
    session_id = session_of_team(client, student, task_id, 1)["id"]

    result = put_preparation(client, student, session_id, 0)
    assert result["version"] == 1 and result["preparation"]["research"]["audience"] == "家庭消费者"

    stale = client.put(
        f"/api/sessions/{session_id}/preparation",
        json={**result["preparation"], "expected_version": 0}, headers=student)
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "PREPARATION_VERSION_CONFLICT"
    assert stale.json()["error"]["details"]["current_version"] == 1

    again = put_preparation(client, student, session_id, 1)
    assert again["version"] == 2

    teacher_write = client.put(
        f"/api/sessions/{session_id}/preparation",
        json={**again["preparation"], "expected_version": 2}, headers=teacher)
    assert teacher_write.status_code == 403
    assert teacher_write.json()["error"]["code"] == "STUDENT_ACTION_REQUIRED"


def test_assortment_purchase_budget_and_idempotency(client):
    teacher = login(client, "teacher")
    student = login(client, "a_host")
    task_id, _ = publish_task(client, teacher, "采购与预算验证")
    session_id = session_of_team(client, student, task_id, 1)["id"]

    put_preparation(client, student, session_id, 0)
    products = put_assortment(client, student, session_id, [
        assortment_item(1, 2990, "traffic", 1),
        assortment_item(2, 3500, "profit", 2),
    ])
    by_product = {p["product_id"]: p for p in products}
    assert by_product[1]["cost_cents"] == 1500 and by_product[1]["stock_qty"] == 0

    duplicate = client.put(f"/api/sessions/{session_id}/assortment", headers=student, json={
        "items": [assortment_item(1, 2990), assortment_item(1, 3500)]})
    assert duplicate.status_code == 422

    response = post_purchase(client, student, session_id, [
        {"session_product_id": by_product[1]["id"], "qty": 20},
        {"session_product_id": by_product[2]["id"], "qty": 10},
    ], key="purchase-1")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["cash_balance_cents"] == 100000 - (20 * 1500 + 10 * 1800)
    after = {p["product_id"]: p for p in data["products"]}
    assert after[1]["purchased_qty"] == 20 and after[1]["stock_qty"] == 20

    replay = post_purchase(client, student, session_id, [
        {"session_product_id": by_product[1]["id"], "qty": 20},
        {"session_product_id": by_product[2]["id"], "qty": 10},
    ], key="purchase-1")
    assert replay.status_code == 200
    assert replay.json()["data"]["cash_balance_cents"] == data["cash_balance_cents"]

    mismatch = post_purchase(client, student, session_id, [
        {"session_product_id": by_product[1]["id"], "qty": 1},
    ], key="purchase-1")
    assert mismatch.status_code == 409 and mismatch.json()["error"]["code"] == "IDEMPOTENCY_MISMATCH"

    over = post_purchase(client, student, session_id, [
        {"session_product_id": by_product[2]["id"], "qty": 500},
    ])
    assert over.status_code == 409 and over.json()["error"]["code"] == "BUDGET_EXCEEDED"
    unchanged = get_session(client, student, session_id)
    assert unchanged["metrics"]["cash_balance_cents"] == data["cash_balance_cents"]
    stock = {p["product_id"]: p for p in unchanged["products"]}
    assert stock[2]["purchased_qty"] == 10

    removal = client.put(f"/api/sessions/{session_id}/assortment", headers=student, json={
        "items": [assortment_item(1, 2990)]})
    assert removal.status_code == 409
    assert removal.json()["error"]["code"] == "PURCHASED_ITEM_REMOVAL"

    unknown = client.put(f"/api/sessions/{session_id}/assortment", headers=student, json={
        "items": [assortment_item(1, 2990), assortment_item(2, 3500), assortment_item(999, 1000)]})
    assert unknown.status_code == 422
    assert unknown.json()["error"]["code"] == "UNKNOWN_PRODUCT"


def test_promotion_budget_constrained_by_purchases(client):
    teacher = login(client, "teacher")
    student = login(client, "a_host")
    task_id, _ = publish_task(client, teacher, "投流预算验证")
    session_id = session_of_team(client, student, task_id, 1)["id"]
    put_preparation(client, student, session_id, 0)
    products = put_assortment(client, student, session_id, [assortment_item(6, 1990)])
    response = post_purchase(client, student, session_id, [
        {"session_product_id": products[0]["id"], "qty": 50}])
    assert response.status_code == 200
    balance = response.json()["data"]["cash_balance_cents"]
    assert balance == 100000 - 50 * 900

    exceed = client.put(
        f"/api/sessions/{session_id}/preparation",
        json={**{"research": {"audience": "a", "competitor_notes": "", "price_notes": "", "selection_reason": "b"},
                "plan": {"theme": "agriculture", "target_audience": "a"},
                "script": [], "promotion": {"channel": "simulated_feed", "budget_cents": balance + 1, "audience": "a"},
                "room": {"theme": "agriculture", "title": "t", "announcement": ""},
                "coupon": {"discount_cents": 0}, "expected_version": 1}},
        headers=student)
    assert exceed.status_code == 409 and exceed.json()["error"]["code"] == "BUDGET_EXCEEDED"


def test_checklist_requires_full_preparation(client):
    teacher = login(client, "teacher")
    student = login(client, "a_host")
    task_id, _ = publish_task(client, teacher, "开播检查验证")
    session_id = session_of_team(client, student, task_id, 1)["id"]

    empty = client.get(f"/api/sessions/{session_id}/checklist", headers=student).json()["data"]
    assert empty["can_start"] is False
    assert {i["key"] for i in empty["items"]} == {"research", "assortment", "script", "promotion", "room"}

    put_preparation(client, student, session_id, 0, research=False, promotion_audience=False,
                    room_title=False)
    partial = client.get(f"/api/sessions/{session_id}/checklist", headers=student).json()["data"]
    failed = {i["key"] for i in partial["items"] if not i["passed"]}
    assert {"research", "assortment", "script", "promotion", "room"} <= failed

    prepared = prepared_session(client, teacher, student, "开播检查完整数据")
    complete = client.get(
        f"/api/sessions/{prepared['session_id']}/checklist", headers=student).json()["data"]
    assert complete["can_start"] is True
    assert all(i["passed"] for i in complete["items"])
