"""S4-02: draft config editing and immutable version history with ownership checks."""
from agent_helpers import CONFIG_A, CONFIG_B, create_agent, save_version
from conftest import auth


def test_create_agent_and_save_two_immutable_versions(client, student_token):
    agent = create_agent(client, student_token, CONFIG_A)
    assert agent["config"]["name"] == CONFIG_A["name"]
    assert agent["current_version_id"] is None

    first = save_version(client, student_token, agent["id"], CONFIG_A)
    assert first["version"]["version_no"] == 1
    assert first["version"]["config"] == CONFIG_A
    assert first["agent"]["current_version_id"] == first["version"]["id"]

    second = save_version(client, student_token, agent["id"], CONFIG_B)
    assert second["version"]["version_no"] == 2

    response = client.get(f"/api/agents/{agent['id']}/versions", headers=auth(student_token))
    assert response.status_code == 200
    versions = response.json()["data"]
    assert [v["version_no"] for v in versions] == [2, 1]
    assert versions[1]["config"] == CONFIG_A  # old version stays immutable


def test_save_rejects_other_owner(client, student_token, other_student_token):
    agent = create_agent(client, student_token, CONFIG_A)
    response = client.put(f"/api/agents/{agent['id']}", json=CONFIG_B, headers=auth(other_student_token))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "AGENT_FORBIDDEN"


def test_unknown_agent_returns_404(client, student_token):
    response = client.put("/api/agents/999", json=CONFIG_A, headers=auth(student_token))
    assert response.status_code == 404
    response = client.get("/api/agents/999/versions", headers=auth(student_token))
    assert response.status_code == 404


def test_empty_agent_name_rejected(client, student_token):
    response = client.post("/api/agents", json={"name": "", "duties": "x", "boundaries": "x",
                                                "instructions": "x"}, headers=auth(student_token))
    assert response.status_code == 422


def test_versions_hidden_from_other_students_and_drafts_are_private(client, student_token, other_student_token):
    agent = create_agent(client, student_token, CONFIG_A)
    save_version(client, student_token, agent["id"], CONFIG_A)

    response = client.get(f"/api/agents/{agent['id']}/versions", headers=auth(other_student_token))
    assert response.status_code == 403

    listing = client.get("/api/agents", headers=auth(other_student_token))
    assert listing.status_code == 200
    assert listing.json()["data"] == []
