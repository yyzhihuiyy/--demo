"""S4-01/S4-06/S4-07/S4-08: assignment publish, submission with required model run,
teacher review, class publication of an immutable version, and access control."""
from agent_helpers import (
    CONFIG_A, CONFIG_B, QUESTION_CONSULT, create_agent, create_and_publish_assignment,
    run_preview, save_version, submit_work,
)
from conftest import FakeModelAdapter, auth, seed_core_world


def test_teacher_creates_updates_publishes_assignment(client, teacher_token, student_token):
    created = client.post("/api/agent-assignments", json={
        "title": "设计一名客服智能体", "instructions": "完成边界与知识卡设计。",
        "scenario": "助农直播客服", "rubric": ["边界遵守", "依据使用"],
    }, headers=auth(teacher_token))
    assert created.status_code == 200, created.text
    assignment = created.json()["data"]
    assert assignment["status"] == "draft"

    updated = client.put(f"/api/agent-assignments/{assignment['id']}", json={
        "title": "设计一名客服智能体（修订）", "instructions": "完成边界与知识卡设计，完成预演。",
        "scenario": "助农直播客服与售后", "rubric": ["边界遵守", "依据使用", "语气"],
    }, headers=auth(teacher_token))
    assert updated.status_code == 200

    # students do not see drafts
    hidden = client.get("/api/agent-assignments", headers=auth(student_token))
    assert hidden.json()["data"] == []

    published = client.post(f"/api/agent-assignments/{assignment['id']}/publish", headers=auth(teacher_token))
    assert published.status_code == 200
    assert published.json()["data"]["status"] == "published"

    visible = client.get("/api/agent-assignments", headers=auth(student_token))
    assert [item["id"] for item in visible.json()["data"]] == [assignment["id"]]

    # publishing or editing again is rejected
    assert client.post(f"/api/agent-assignments/{assignment['id']}/publish",
                       headers=auth(teacher_token)).status_code == 409
    assert client.put(f"/api/agent-assignments/{assignment['id']}",
                     json={"title": "x", "instructions": "y"},
                     headers=auth(teacher_token)).status_code == 409


def test_assignment_ownership_and_task_link_validation(client, teacher_token, student_token):
    response = client.post("/api/agent-assignments", json={"title": "t", "instructions": "i"},
                           headers=auth(student_token))
    assert response.status_code == 403

    bogus_task = client.post("/api/agent-assignments", json={
        "title": "t", "instructions": "i", "task_id": 999}, headers=auth(teacher_token))
    assert bogus_task.status_code == 422
    assert bogus_task.json()["error"]["code"] == "TASK_NOT_FOUND"


def _prepare_submission_ready_state(client, app, teacher_token, student_token, config=CONFIG_A):
    app.state.model_adapter = FakeModelAdapter()
    agent = create_agent(client, student_token, config)
    saved = save_version(client, student_token, agent["id"], config)
    run = run_preview(client, student_token, config, QUESTION_CONSULT, agent_id=agent["id"])
    assert run.status_code == 200
    assignment = create_and_publish_assignment(client, teacher_token)
    return agent, saved["version"], run.json()["data"], assignment


def test_submission_freezes_content_and_requires_matching_model_run(client, app, teacher_token, student_token):
    agent, version, run, assignment = _prepare_submission_ready_state(client, app, teacher_token, student_token)

    response = submit_work(client, student_token, assignment["id"], version["id"], [run["id"]])
    assert response.status_code == 200, response.text
    submission = response.json()["data"]
    assert submission["status"] == "submitted"
    assert submission["run_ids"] == [run["id"]]
    assert submission["content_snapshot"]["config"] == CONFIG_A
    assert submission["content_snapshot"]["runs"][0]["id"] == run["id"]
    assert submission["content_snapshot"]["assignment"]["title"] == assignment["title"]

    # a second active submission for the same assignment is rejected
    duplicate = submit_work(client, student_token, assignment["id"], version["id"], [run["id"]])
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "SUBMISSION_ALREADY_ACTIVE"


def test_submission_blocked_without_successful_model_run(client, app, teacher_token, student_token):
    agent = create_agent(client, student_token, CONFIG_A)
    saved = save_version(client, student_token, agent["id"], CONFIG_A)
    assignment = create_and_publish_assignment(client, teacher_token)

    app.state.model_adapter = None  # model not configured -> rule fallback run
    rule_run = run_preview(client, student_token, CONFIG_A, QUESTION_CONSULT, agent_id=agent["id"])
    assert rule_run.json()["data"]["source"] == "rule"
    blocked = submit_work(client, student_token, assignment["id"], saved["version"]["id"],
                          [rule_run.json()["data"]["id"]])
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "MODEL_RUN_REQUIRED"

    # a run with different config does not qualify either
    app.state.model_adapter = FakeModelAdapter()
    mismatch_run = run_preview(client, student_token, CONFIG_B, QUESTION_CONSULT, agent_id=agent["id"])
    mismatched = submit_work(client, student_token, assignment["id"], saved["version"]["id"],
                             [mismatch_run.json()["data"]["id"]])
    assert mismatched.status_code == 409

    # after a successful matching model run the submission is accepted
    good_run = run_preview(client, student_token, CONFIG_A, QUESTION_CONSULT, agent_id=agent["id"])
    ok = submit_work(client, student_token, assignment["id"], saved["version"]["id"],
                     [good_run.json()["data"]["id"]])
    assert ok.status_code == 200


def test_submission_rejects_foreign_versions_and_runs(client, app, teacher_token, student_token, other_student_token):
    _, version, run, assignment = _prepare_submission_ready_state(client, app, teacher_token, student_token)
    foreign_version = submit_work(client, other_student_token, assignment["id"], version["id"], [run["id"]])
    assert foreign_version.status_code == 403

    other_agent = create_agent(client, other_student_token, CONFIG_A)
    other_saved = save_version(client, other_student_token, other_agent["id"], CONFIG_A)
    foreign_run = submit_work(client, other_student_token, assignment["id"],
                              other_saved["version"]["id"], [run["id"]])
    assert foreign_run.status_code == 403

    unpublished = client.post("/api/agent-assignments", json={"title": "t", "instructions": "i"},
                              headers=auth(teacher_token)).json()["data"]
    assert submit_work(client, student_token, unpublished["id"],
                       other_saved["version"]["id"], [run["id"]]).status_code == 409


def test_teacher_reviews_submissions_and_student_cannot(client, app, teacher_token, student_token):
    _, version, run, assignment = _prepare_submission_ready_state(client, app, teacher_token, student_token)
    submit_work(client, student_token, assignment["id"], version["id"], [run["id"]])

    listing = client.get(f"/api/agent-submissions?assignment_id={assignment['id']}",
                        headers=auth(teacher_token))
    assert listing.status_code == 200
    assert [s["status"] for s in listing.json()["data"]] == ["submitted"]

    student_list = client.get("/api/agent-submissions", headers=auth(student_token))
    assert [s["assignment_id"] for s in student_list.json()["data"]] == [assignment["id"]]

    forbidden = client.post(f"/api/agent-submissions/{listing.json()['data'][0]['id']}/review", json={
        "decision": "approve", "grade": 90, "comment": "好"}, headers=auth(student_token))
    assert forbidden.status_code == 403

    missing_grade = client.post(f"/api/agent-submissions/{listing.json()['data'][0]['id']}/review", json={
        "decision": "approve", "comment": "缺少分数"}, headers=auth(teacher_token))
    assert missing_grade.status_code == 422

    approved = client.post(f"/api/agent-submissions/{listing.json()['data'][0]['id']}/review", json={
        "decision": "approve", "grade": 88, "comment": "边界清晰，依据使用得当。"},
        headers=auth(teacher_token))
    assert approved.status_code == 200
    assert approved.json()["data"]["status"] == "approved"
    assert approved.json()["data"]["grade"] == 88

    again = client.post(f"/api/agent-submissions/{listing.json()['data'][0]['id']}/review", json={
        "decision": "return", "comment": "x"}, headers=auth(teacher_token))
    assert again.status_code == 409


def test_returned_submission_can_be_resubmitted_and_old_records_kept(client, app, teacher_token, student_token):
    agent, version, run, assignment = _prepare_submission_ready_state(client, app, teacher_token, student_token)
    first = submit_work(client, student_token, assignment["id"], version["id"], [run["id"]]).json()["data"]

    returned = client.post(f"/api/agent-submissions/{first['id']}/review", json={
        "decision": "return", "comment": "售后边界仍不够明确，请补充知识卡后重提。"},
        headers=auth(teacher_token))
    assert returned.status_code == 200
    assert returned.json()["data"]["status"] == "returned"

    # student improves the same draft, saves a new version and runs again
    saved = save_version(client, student_token, agent["id"], CONFIG_B)
    new_run = run_preview(client, student_token, CONFIG_B, "售后退款怎么办", agent_id=agent["id"])
    second = submit_work(client, student_token, assignment["id"], saved["version"]["id"],
                         [new_run.json()["data"]["id"]], notes="补充了售后边界与发货时效卡。")
    assert second.status_code == 200

    history = client.get("/api/agent-submissions", headers=auth(student_token)).json()["data"]
    assert [s["id"] for s in history] == [second.json()["data"]["id"], first["id"]]
    assert history[1]["status"] == "returned"  # old submission is preserved


def test_publish_approved_submission_and_class_preview(client, app, teacher_token, student_token, other_student_token):
    agent, version, run, assignment = _prepare_submission_ready_state(client, app, teacher_token, student_token)
    submission = submit_work(client, student_token, assignment["id"], version["id"], [run["id"]]).json()["data"]

    not_approved = client.post(f"/api/agent-submissions/{submission['id']}/publish",
                               headers=auth(teacher_token))
    assert not_approved.status_code == 409

    client.post(f"/api/agent-submissions/{submission['id']}/review", json={
        "decision": "approve", "grade": 92, "comment": "通过"}, headers=auth(teacher_token))
    publication = client.post(f"/api/agent-submissions/{submission['id']}/publish",
                               headers=auth(teacher_token))
    assert publication.status_code == 200, publication.text
    published = publication.json()["data"]
    assert published["config"] == CONFIG_A
    assert published["version_id"] == version["id"]

    # classmates see the publication and can preview the fixed version
    shelf = client.get("/api/agent-publications", headers=auth(other_student_token))
    assert [item["id"] for item in shelf.json()["data"]] == [published["id"]]

    preview = client.post(f"/api/agent-publications/{published['id']}/preview", json={
        "question": "橙子甜不甜，现在买有优惠吗？"}, headers=auth(other_student_token))
    assert preview.status_code == 200, preview.text
    preview_run = preview.json()["data"]
    assert preview_run["owner_id"] == 103  # the tryer, not the author
    assert preview_run["version_id"] == published["version_id"]
    assert preview_run["config_snapshot"] == CONFIG_A
    assert preview_run["source"] == "model"
    assert preview_run["context_sources"][0] == f"config:publication_version:{published['version_id']}"

    # the author keeps editing the same draft without affecting the published immutable version
    save_version(client, student_token, agent["id"], CONFIG_B)
    shelf_after = client.get("/api/agent-publications", headers=auth(other_student_token)).json()["data"]
    assert shelf_after[0]["config"] == CONFIG_A


def test_publication_access_control_and_teacher_runs_reading(client, app, teacher_token,
                                                             student_token, other_class_student_token):
    _, version, run, assignment = _prepare_submission_ready_state(client, app, teacher_token, student_token)
    submission = submit_work(client, student_token, assignment["id"], version["id"], [run["id"]]).json()["data"]
    client.post(f"/api/agent-submissions/{submission['id']}/review", json={
        "decision": "approve", "grade": 90, "comment": "通过"}, headers=auth(teacher_token))
    published = client.post(f"/api/agent-submissions/{submission['id']}/publish",
                            headers=auth(teacher_token)).json()["data"]

    empty = client.get("/api/agent-publications", headers=auth(other_class_student_token))
    assert empty.json()["data"] == []

    foreign_preview = client.post(f"/api/agent-publications/{published['id']}/preview", json={
        "question": "你好"}, headers=auth(other_class_student_token))
    assert foreign_preview.status_code == 403

    # teacher reads the submitted run records through the submission authorization
    runs = client.get(f"/api/agent-runs?submission_id={submission['id']}", headers=auth(teacher_token))
    assert runs.status_code == 200
    assert [item["id"] for item in runs.json()["data"]] == [run["id"]]
    denied = client.get(f"/api/agent-runs?submission_id={submission['id']}",
                        headers=auth(other_class_student_token))
    assert denied.status_code == 403


def test_publication_preview_with_session_context_authorized_only(client, app, session_factory,
                                                                  teacher_token, student_token,
                                                                  other_student_token, classmate_token):
    app.state.model_adapter = FakeModelAdapter()
    seed_core_world(session_factory, extra_members=(103,))
    _, version, run, assignment = _prepare_submission_ready_state(client, app, teacher_token, student_token)
    submission = submit_work(client, student_token, assignment["id"], version["id"], [run["id"]]).json()["data"]
    client.post(f"/api/agent-submissions/{submission['id']}/review", json={
        "decision": "approve", "grade": 90, "comment": "通过"}, headers=auth(teacher_token))
    published = client.post(f"/api/agent-submissions/{submission['id']}/publish",
                            headers=auth(teacher_token)).json()["data"]

    preview = client.post(f"/api/agent-publications/{published['id']}/preview", json={
        "question": "这个橙子还有库存吗？", "session_id": 1}, headers=auth(other_student_token))
    assert preview.status_code == 200, preview.text
    assert preview.json()["data"]["context_snapshot"]["products"][0]["title"] == "赣南脐橙 5斤装"

    # same-class student outside the team may see the publication but not that session
    unauthorized = client.post(f"/api/agent-publications/{published['id']}/preview", json={
        "question": "你好", "session_id": 1}, headers=auth(classmate_token))
    assert unauthorized.status_code == 403
    assert unauthorized.json()["error"]["code"] == "SESSION_FORBIDDEN"  # no fallback to other data
