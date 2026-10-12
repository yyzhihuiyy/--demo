"""Test-writing helpers: fixed configs and small API wrappers shared by agent tests."""
from conftest import auth

CONFIG_A = {
    "name": "助农客服小助手A",
    "duties": "解答农产品咨询，说明价格、库存与发货安排。",
    "boundaries": "只讨论本场商品；不做功效承诺；退款按平台政策登记后人工处理。",
    "instructions": "先确认问题，再依据知识卡回答；投诉先安抚再给处理路径。",
    "knowledge_cards": [
        {"title": "商品知识卡", "content": "赣南脐橙 5 斤装参考价 29.9 元，产地直采、当季鲜果。"},
        {"title": "售后政策卡", "content": "未发货订单可申请整单退款；已发货问题件先登记再人工核实。"},
    ],
}

CONFIG_B = {
    "name": "助农客服小助手B",
    "duties": CONFIG_A["duties"],
    "boundaries": "只讨论本场商品；不做功效承诺；退款按平台政策登记后人工处理；不承诺具体到账时间。",
    "instructions": "先确认问题，再依据知识卡回答；遇到争议先道歉安抚。",
    "knowledge_cards": [
        {"title": "商品知识卡", "content": "赣南脐橙 5 斤装参考价 29.9 元，产地直采、当季鲜果。"},
        {"title": "售后政策卡", "content": "未发货订单可申请整单退款；处理时效以平台公示为准。"},
        {"title": "发货时效卡", "content": "48 小时内发货，偏远地区顺延。"},
    ],
}

QUESTION_CONSULT = "这个脐橙是当季的吗？5 斤装大概有几个，甜不甜？"
QUESTION_DISPUTE = "我收到的大米有漏袋，你们必须马上全额退款，不然我就去投诉！"


def create_agent(client, token, config):
    response = client.post("/api/agents", json=config, headers=auth(token))
    assert response.status_code == 200, response.text
    return response.json()["data"]


def save_version(client, token, agent_id, config):
    response = client.put(f"/api/agents/{agent_id}", json=config, headers=auth(token))
    assert response.status_code == 200, response.text
    return response.json()["data"]


def run_preview(client, token, config, question, *, agent_id=None, session_id=None):
    payload = {"config": config, "question": question}
    if agent_id is not None:
        payload["agent_id"] = agent_id
    if session_id is not None:
        payload["session_id"] = session_id
    return client.post("/api/agent-runs", json=payload, headers=auth(token))


def create_and_publish_assignment(client, teacher, **overrides):
    payload = {
        "title": "设计一名客服智能体",
        "instructions": "完成职责、边界、行为指令与知识卡设计，并用真实模型完成预演。",
        "scenario": "助农直播间客服咨询与售后争议处理",
        "rubric": ["边界遵守：不做越权承诺", "依据使用：引用知识卡", "语气与服务意识"],
    }
    payload.update(overrides)
    created = client.post("/api/agent-assignments", json=payload, headers=auth(teacher))
    assert created.status_code == 200, created.text
    assignment = created.json()["data"]
    published = client.post(f"/api/agent-assignments/{assignment['id']}/publish", headers=auth(teacher))
    assert published.status_code == 200, published.text
    return published.json()["data"]


def submit_work(client, token, assignment_id, version_id, run_ids, notes="优化了售后边界与知识卡。"):
    return client.post("/api/agent-submissions", json={
        "assignment_id": assignment_id, "version_id": version_id,
        "run_ids": run_ids, "improvement_notes": notes,
    }, headers=auth(token))
