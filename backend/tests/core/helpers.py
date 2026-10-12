"""Shared helpers for core tests; every client runs on its own isolated SQLite database."""
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.main import create_app
from app.core.seed import seed_demo
from app.shared.db import Base, create_db_engine, get_db

TZ = timezone(timedelta(hours=8))
DEMO_PASSWORD = "demo1234"


def build_isolated_client(tmp_path):
    """App + TestClient bound to a per-test engine; lifespan is intentionally skipped."""
    engine = create_db_engine("sqlite:///" + str(tmp_path / "core.db"))
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        seed_demo(db)
        db.commit()

    def override_get_db():
        with factory() as db:
            try:
                yield db
            except Exception:
                db.rollback()
                raise

    application = create_app()
    application.dependency_overrides[get_db] = override_get_db
    return TestClient(application), engine


def login(client, username, password=DEMO_PASSWORD):
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    token = response.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


def task_payload(title, team_ids=(1, 2), ends_in_hours=48):
    start = datetime.now(TZ)
    return {
        "title": title,
        "description": "测试任务说明",
        "target_audience": "家庭消费者",
        "initial_budget_cents": 100000,
        "target_gmv_cents": 50000,
        "market_heat": 1,
        "difficulty": 1,
        "starts_at": start.isoformat(),
        "ends_at": (start + timedelta(hours=ends_in_hours)).isoformat(),
        "score_weights": {"process": 25, "business": 25, "service": 20, "compliance": 15, "review": 15},
        "team_ids": list(team_ids),
    }


def publish_task(client, teacher_headers, title, team_ids=(1, 2)):
    response = client.post("/api/tasks", json=task_payload(title, team_ids), headers=teacher_headers)
    assert response.status_code == 200, response.text
    task_id = response.json()["data"]["id"]
    response = client.post(f"/api/tasks/{task_id}/publish", headers=teacher_headers)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    return task_id, data["session_ids"]


def session_of_team(client, headers, task_id, team_id):
    response = client.get(f"/api/tasks/{task_id}", headers=headers)
    assert response.status_code == 200, response.text
    for session in response.json()["data"]["sessions"]:
        if session["team_id"] == team_id:
            return session
    raise AssertionError(f"team {team_id} has no session in task {task_id}")


def put_preparation(client, headers, session_id, expected_version, *, research=True,
                    script_product_ids=(1,), promotion_budget=1000, promotion_audience=True,
                      room_title=True, coupon=100):
    research_payload = (
        {"audience": "家庭消费者", "competitor_notes": "同类直播间价格集中在 30-60 元",
         "price_notes": "参考价上下浮动 20% 以内更易转化", "selection_reason": "高频刚需+价格带适中"}
        if research else {"audience": "", "competitor_notes": "", "price_notes": "", "selection_reason": ""}
    )
    script = [
        {"id": "opening", "kind": "opening", "product_id": None, "text": "欢迎来到助农直播间"},
        {"id": "p-1", "kind": "product", "product_id": script_product_ids[0], "text": "产地直采，先讲口感再讲价格"},
        {"id": "interact", "kind": "interaction", "product_id": None, "text": "扣 1 领优惠券"},
        {"id": "closing", "kind": "closing", "product_id": None, "text": "感谢观看，下次再见"},
    ]
    for extra_id, product_id in enumerate(script_product_ids[1:], start=2):
        script.append({"id": f"p-{extra_id}", "kind": "product", "product_id": product_id,
                       "text": "补充讲解段"})
    body = {
        "research": research_payload,
        "plan": {"theme": "agriculture", "target_audience": "家庭消费者"},
        "script": script,
        "promotion": {"channel": "simulated_feed",
                      "budget_cents": promotion_budget,
                      "audience": "关注食品品质的家庭用户" if promotion_audience else ""},
        "room": {"theme": "agriculture",
                 "title": "助农好物专场" if room_title else "",
                 "announcement": "产地直采，品质保障" },
        "coupon": {"discount_cents": coupon},
        "expected_version": expected_version,
    }
    response = client.put(f"/api/sessions/{session_id}/preparation", json=body, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def put_assortment(client, headers, session_id, items):
    body = {"items": items}
    response = client.put(f"/api/sessions/{session_id}/assortment", json=body, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]["products"]


def assortment_item(product_id, price_cents, positioning="profit", sort_order=1):
    return {"product_id": product_id, "positioning": positioning,
            "selling_points": "测试卖点", "sale_price_cents": price_cents, "sort_order": sort_order}


def post_purchase(client, headers, session_id, items, key=None):
    headers = dict(headers)
    if key:
        headers["Idempotency-Key"] = key
    response = client.post(f"/api/sessions/{session_id}/purchases", json={"items": items}, headers=headers)
    return response


def get_session(client, headers, session_id):
    response = client.get(f"/api/sessions/{session_id}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def prepared_session(client, teacher, student, title="直播准备任务", team_id=1):
    """Create a task, publish, and drive one team session to a fully prepared state."""
    task_id, session_ids = publish_task(client, teacher, title)
    session = session_of_team(client, student, task_id, team_id)
    session_id = session["id"]
    version = put_preparation(client, student, session_id, 0)["version"]
    products = put_assortment(client, student, session_id, [
        assortment_item(1, 2990, "traffic", 1),
        assortment_item(6, 1990, "profit", 2),
    ])
    response = post_purchase(client, student, session_id, [
        {"session_product_id": products[0]["id"], "qty": 20},
        {"session_product_id": products[1]["id"], "qty": 10},
    ])
    assert response.status_code == 200, response.text
    return {"task_id": task_id, "session_id": session_id, "version": version,
            "products": response.json()["data"]["products"]}


def control(client, headers, session_id, action):
    return client.post(f"/api/sessions/{session_id}/control",
                       json={"action": action}, headers=headers)


def start_live(client, headers, session_id):
    response = control(client, headers, session_id, "start")
    assert response.status_code == 200, response.text
    return response.json()["data"]


def act(client, headers, session_id, type_, payload=None):
    return client.post(f"/api/sessions/{session_id}/actions",
                       json={"type": type_, "payload": payload or {}}, headers=headers)


def live_state(client, headers, session_id):
    response = client.get(f"/api/sessions/{session_id}/live-state", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def live_session(client, teacher, student, title="直播联调任务"):
    prepared = prepared_session(client, teacher, student, title)
    start_live(client, student, prepared["session_id"])
    return prepared
