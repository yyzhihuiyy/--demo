from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.access import now
from app.core.models import SessionRow
from app.core.sim import advance_session_tick
from app.shared.schemas import CompetitionComparison, Leaderboard, ReviewDetail
from helpers import (
    act, assortment_item, build_isolated_client, control, login, post_purchase,
    put_assortment, put_preparation, task_payload,
)


def result(response):
    assert response.status_code == 200, response.text
    return response.json()["data"]


def prepare(client, student, sid):
    put_preparation(client, student, sid, 0)
    products = put_assortment(client, student, sid, [
        assortment_item(1, 2990, "traffic"),
        assortment_item(6, 3990, "profit", 2),
        assortment_item(8, 12900, "image", 3),
    ])
    result(post_purchase(client, student, sid, [{"session_product_id": p["id"], "qty": 5} for p in products]))
    result(control(client, student, sid, "start"))
    result(act(client, student, sid, "select_product", {"session_product_id": products[0]["id"]}))


def test_two_team_demo_refund_review_grade_and_competition(tmp_path):
    client, engine = build_isolated_client(tmp_path)
    teacher, a, b = [login(client, name) for name in ("teacher", "a_host", "b_host")]
    task = result(client.post("/api/tasks", headers=teacher, json=task_payload("四场景演示回归")))
    competition = result(client.post("/api/competitions", headers=teacher,
                                     json={"task_id": task["id"], "title": "两组策略竞赛"}))
    sids = result(client.post(f'/api/tasks/{task["id"]}/publish', headers=teacher))["session_ids"]
    assert len(sids) == 2
    for student, sid in zip((a, b), sids):
        prepare(client, student, sid)
        with Session(engine) as db:
            session = db.get(SessionRow, sid)
            for _ in range(100):
                advance_session_tick(db, session)
            db.commit()
        result(control(client, student, sid, "end"))
        orders = result(client.get(f"/api/sessions/{sid}/orders", headers=student))
        assert len(orders) >= 2
        refund_order = orders[0]
        refund = result(client.post(f'/api/orders/{refund_order["id"]}/refunds', headers=student,
                                    json={"reason": "演示未发货整单退款"}))
        blocked = client.post(f'/api/orders/{refund_order["id"]}/ship', headers=student)
        assert blocked.status_code == 409
        data = {"analysis": "比较货盘与互动效果", "improvements": "优化话术并及时回复"}
        result(client.put(f"/api/sessions/{sid}/review", headers=student, json=data))
        assert client.post(f"/api/sessions/{sid}/review/submit", headers=student).status_code == 409
        resolve_url = f'/api/refunds/{refund["id"]}/resolve'
        decision = {"decision": "approve", "handling_note": "未发货，确认退款"}
        first = result(client.post(resolve_url, headers=student, json=decision))
        repeated = result(client.post(resolve_url, headers=student, json=decision))
        assert first == repeated  # money and stock change only once
        for order in orders[1:]:
            result(client.post(f'/api/orders/{order["id"]}/ship', headers=student))
            result(client.post(f'/api/orders/{order["id"]}/sign', headers=student))
        submitted = result(client.post(f"/api/sessions/{sid}/review/submit", headers=student))
        assert submitted["status"] == "submitted"
        assert result(client.post(f"/api/sessions/{sid}/review/submit", headers=student)) == submitted
        assert client.put(f"/api/sessions/{sid}/review", headers=student, json=data).status_code == 409
        grade = result(client.post(f"/api/sessions/{sid}/grade", headers=teacher,
                                   json={"subjective_score": 85, "comment": "流程完整，继续优化话术"}))
        assert grade["total_score"] == round(grade["objective_score"] * .7 + 85 * .3, 2)
        detail = result(client.get(f"/api/sessions/{sid}/review", headers=student))
        ReviewDetail.model_validate(detail)
        assert detail["metrics"] == submitted["metrics_snapshot"]
        assert detail["metrics"]["refund_cents"] == refund_order["amount_cents"]
        assert detail["grade"]["total_score"] == grade["total_score"]
        final = result(client.get(f'/api/competitions/{competition["id"]}/leaderboard?stage=final', headers=teacher))
        Leaderboard.model_validate(final)
        if sid == sids[0]:
            assert len(final["entries"]) == len(final["pending_entries"]) == 1
    comparison = result(client.get(f'/api/competitions/{competition["id"]}/comparison', headers=teacher))
    CompetitionComparison.model_validate(comparison)
    assert comparison["competition"]["status"] == "finished"
    assert len(comparison["teams"]) == len(final["entries"]) == 2
    assert not final["pending_entries"]
    assert client.get(f'/api/competitions/{competition["id"]}/comparison', headers=a).status_code == 403
    assert client.get(f'/api/sessions/{sids[1]}/review', headers=a).status_code == 403
    assert client.post(f'/api/sessions/{sids[0]}/grade', headers=a,
                       json={"subjective_score": 100, "comment": "越权"}).status_code == 403
    assert client.get(f'/api/competitions/{competition["id"]}/leaderboard', headers=a).status_code == 200
    client.close()
    engine.dispose()


def test_deadline_stops_simulation_and_closes_paused_session(tmp_path):
    from app.core.lifecycle import _deadline_over
    client, engine = build_isolated_client(tmp_path)
    with Session(engine) as db:
        session = db.scalar(select(SessionRow))
        session.status = "live"
        session.rule_snapshot = {**session.rule_snapshot, "ends_at": (now() - timedelta(seconds=1)).isoformat()}
        db.commit()
        tick = session.tick_index
        assert advance_session_tick(db, session) is None
        assert session.tick_index == tick
        assert session.status == "ended"
        session.status = "paused"
        db.commit()
        _deadline_over(db)
        assert session.status == "ended"
    client.close()
    engine.dispose()
