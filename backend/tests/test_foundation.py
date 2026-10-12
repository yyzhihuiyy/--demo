import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.main import create_app
from app.shared.db import Base, PlatformMetadata, create_db_engine
from app.shared.schemas import PurchaseItem, ScoreWeights, TaskWrite


@pytest.fixture
def client():
    with TestClient(create_app()) as client:
        yield client


def test_health_reports_real_database_without_secrets(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["database"] == "ok"
    assert data["contract_version"] == "1.1"
    assert "key" not in data and "token" not in data


def test_missing_auth_is_denied(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


def test_invalid_login_body_does_not_echo_secret(client):
    response = client.post("/api/auth/login", json={"username": "", "password": "DO_NOT_ECHO"})
    assert response.status_code == 422
    assert "DO_NOT_ECHO" not in response.text
    assert "fields" in response.json()["error"]["details"]


def test_sqlite_persists_and_rolls_back(tmp_path):
    url = "sqlite:///" + str(tmp_path / "durable.db")
    engine = create_db_engine(url)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(PlatformMetadata(key="test", value="persisted"))
        db.commit()
        db.add(PlatformMetadata(key="rolled_back", value="no"))
        db.flush()
        db.rollback()
    engine.dispose()
    reopened = create_db_engine(url)
    with Session(reopened) as db:
        assert db.get(PlatformMetadata, "test").value == "persisted"
        assert db.get(PlatformMetadata, "rolled_back") is None
        assert db.execute(text("PRAGMA foreign_keys")).scalar() == 1
    reopened.dispose()


def test_financial_quantity_and_weight_validation():
    with pytest.raises(ValidationError):
        PurchaseItem(session_product_id=1, qty=-1)
    with pytest.raises(ValidationError):
        PurchaseItem(session_product_id=1, qty=1.5)
    with pytest.raises(ValidationError):
        ScoreWeights(process=100)
    assert sum(ScoreWeights().model_dump().values()) == 100


def test_task_requires_ordered_timezone_dates():
    with pytest.raises(ValidationError):
        TaskWrite(title="demo", starts_at="2026-10-12T10:00:00", ends_at="2026-10-12T11:00:00")
    with pytest.raises(ValidationError):
        TaskWrite(title="demo", starts_at="2026-10-12T11:00:00Z", ends_at="2026-10-12T10:00:00Z")
