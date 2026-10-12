"""S4-03/S4-04: preview runs use the current form config, save snapshots, label the real
source (model/rule), honor session authorization, and never write core business data."""
from agent_helpers import QUESTION_CONSULT, CONFIG_A, CONFIG_B, create_agent, run_preview, save_version
from conftest import FakeModelAdapter, auth, core_counts, seed_core_world


def test_run_success_records_model_source_and_snapshot(client, app, student_token):
    fake = FakeModelAdapter(output="您好，脐橙是当季鲜果，5 斤装约 12～15 个。")
    app.state.model_adapter = fake
    agent = create_agent(client, student_token, CONFIG_A)
    response = run_preview(client, student_token, CONFIG_A, QUESTION_CONSULT, agent_id=agent["id"])
    assert response.status_code == 200, response.text
    run = response.json()["data"]
    assert run["status"] == "succeeded"
    assert run["source"] == "model"
    assert run["model"] == "fake-model"
    assert run["duration_ms"] == 6
    assert run["config_snapshot"] == CONFIG_A
    assert run["output"] == "您好，脐橙是当季鲜果，5 斤装约 12～15 个。"
    assert run["version_id"] is None  # unsaved-form runs are not bound to a version
    assert run["context_sources"] == [f"config:agent:{agent['id']}:current_form", "config:knowledge_cards"]
    assert len(fake.calls) == 1
    messages = fake.calls[0]
    assert messages[-1]["content"] == QUESTION_CONSULT
    joined = "\n".join(m["content"] for m in messages)
    assert CONFIG_A["boundaries"] in joined
    assert "商品知识卡" in joined


def test_run_without_model_configuration_falls_back_to_rule(client, app, student_token):
    app.state.model_adapter = None  # hermetic "not configured"
    response = run_preview(client, student_token, CONFIG_A, QUESTION_CONSULT)
    assert response.status_code == 200, response.text
    run = response.json()["data"]
    assert run["status"] == "failed"
    assert run["source"] == "rule"
    assert run["model"] is None
    assert "未配置" in run["error"]
    assert "规则演示回复" in run["output"]
    assert "source=rule" in run["output"]


def test_run_adapter_failure_is_recorded_and_never_faked_as_model(client, app, student_token):
    app.state.model_adapter = FakeModelAdapter(error="模型服务返回 HTTP 503")
    response = run_preview(client, student_token, CONFIG_A, QUESTION_CONSULT)
    assert response.status_code == 200, response.text
    run = response.json()["data"]
    assert run["status"] == "failed"
    assert run["source"] == "rule"
    assert run["model"] == "fake-model"
    assert run["error"] == "模型服务返回 HTTP 503"
    assert "规则演示回复" in run["output"]


def test_run_uses_current_form_config_not_last_saved_version(client, app, student_token):
    app.state.model_adapter = FakeModelAdapter()
    agent = create_agent(client, student_token, CONFIG_A)
    save_version(client, student_token, agent["id"], CONFIG_A)
    response = run_preview(client, student_token, CONFIG_B, QUESTION_CONSULT, agent_id=agent["id"])
    assert response.status_code == 200
    run = response.json()["data"]
    assert run["config_snapshot"] == CONFIG_B  # preview always uses the submitted form content


def test_run_with_authorized_session_context(client, app, session_factory, student_token):
    app.state.model_adapter = FakeModelAdapter()
    seed_core_world(session_factory)
    response = run_preview(client, student_token, CONFIG_A, QUESTION_CONSULT, session_id=1)
    assert response.status_code == 200, response.text
    run = response.json()["data"]
    assert run["session_id"] == 1
    assert run["context_snapshot"]["products"][0]["title"] == "赣南脐橙 5斤装"
    assert run["context_snapshot"]["recent_questions"][0]["payload"]["text"] == "什么时候发货？"
    assert "session:1:authorized_products" in run["context_sources"]


def test_run_rejects_foreign_session_and_missing_session(client, app, session_factory,
                                                         student_token, other_student_token,
                                                         other_class_student_token):
    app.state.model_adapter = FakeModelAdapter()
    seed_core_world(session_factory)
    forbidden = run_preview(client, other_student_token, CONFIG_A, QUESTION_CONSULT, session_id=1)
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "SESSION_FORBIDDEN"

    other_class = run_preview(client, other_class_student_token, CONFIG_A, QUESTION_CONSULT, session_id=1)
    assert other_class.status_code == 403

    missing = run_preview(client, student_token, CONFIG_A, QUESTION_CONSULT, session_id=999)
    assert missing.status_code == 404


def test_run_writes_no_core_business_data(client, app, session_factory, student_token):
    app.state.model_adapter = FakeModelAdapter()
    seed_core_world(session_factory)
    before = core_counts(session_factory)
    for question in ("咨询一下发货时间", "售后要求退款"):
        response = run_preview(client, student_token, CONFIG_A, question, session_id=1)
        assert response.status_code == 200
    assert core_counts(session_factory) == before  # preview only writes its own run records


def test_runs_are_owner_scoped_and_require_agent_ownership(client, app, student_token, other_student_token):
    app.state.model_adapter = FakeModelAdapter()
    agent = create_agent(client, student_token, CONFIG_A)
    assert run_preview(client, student_token, CONFIG_A, QUESTION_CONSULT, agent_id=agent["id"]).status_code == 200

    foreign = run_preview(client, other_student_token, CONFIG_A, QUESTION_CONSULT, agent_id=agent["id"])
    assert foreign.status_code == 403

    mine = client.get("/api/agent-runs", headers=auth(student_token))
    assert mine.status_code == 200
    assert len(mine.json()["data"]) == 1
    theirs = client.get("/api/agent-runs", headers=auth(other_student_token))
    assert theirs.status_code == 200
    assert theirs.json()["data"] == []
