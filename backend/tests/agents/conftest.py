"""Shared fixtures for TASK-103 tests.

Hermetic by design: a temp SQLite engine replaces request sessions via dependency
override, and the model adapter is injected through `app.state.model_adapter`
(adapter = success/failure fake, None = not configured). Real login and a real
model service are never required here.
"""
import hashlib
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.agents import models as agent_models  # noqa: F401  tables must exist
from app.agents.llm import ModelCall
from app.core import models as core_models  # noqa: F401  read-only, for access adapter and fixtures
from app.main import create_app
from app.shared.db import Base, create_db_engine, get_db


class FakeModelAdapter:
    def __init__(self, output="模拟模型回复：已按平台政策为您登记售后，请留意站内通知。", error=None):
        self.output = output
        self.error = error
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        return ModelCall(output=None if self.error else self.output,
                         model="fake-model", duration_ms=6, error=self.error)


@pytest.fixture
def engine(tmp_path):
    engine = create_db_engine("sqlite:///" + str(tmp_path / "agents.db"))
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session_factory(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def app(session_factory):
    application = create_app()

    def override_get_db():
        with session_factory() as db:
            try:
                yield db
            except Exception:
                db.rollback()
                raise

    application.dependency_overrides[get_db] = override_get_db
    return application


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def teacher_token(session_factory):
    return make_account(session_factory, 101, "agent_teacher", "teacher", class_id=1)


@pytest.fixture
def student_token(session_factory):
    return make_account(session_factory, 102, "agent_student_a", "student", class_id=1)


@pytest.fixture
def other_student_token(session_factory):
    return make_account(session_factory, 103, "agent_student_b", "student", class_id=1)


@pytest.fixture
def other_class_student_token(session_factory):
    return make_account(session_factory, 104, "agent_student_c2", "student", class_id=2)


@pytest.fixture
def classmate_token(session_factory):
    """Same class but never a team member: must not read other teams' session context."""
    return make_account(session_factory, 105, "agent_student_d1", "student", class_id=1)


def make_account(session_factory, user_id, username, role, class_id):
    """Seeds account + token rows directly; never touches the real login endpoint."""
    token = f"test-token-{username}"
    with session_factory() as db:
        db.add(core_models.Account(id=user_id, username=username, password_hash="not-used",
                                   role=role, class_id=class_id, active=True))
        db.add(core_models.Token(digest=hashlib.sha256(token.encode()).hexdigest(),
                                 user_id=user_id,
                                 expires_at=(datetime.now(timezone.utc) + timedelta(hours=6)).isoformat()))
        db.commit()
    return token


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def seed_core_world(session_factory, *, teacher_id=101, student_id=102, class_id=1, extra_members=()):
    """Minimal read-only core rows so the shared access adapter can authorize a session."""
    needed = {"teacher": [teacher_id], "student": [student_id, *extra_members]}
    with session_factory() as db:
        existing = {row_id for ids in needed.values() for row_id in ids
                    if db.get(core_models.Account, row_id) is not None}
    for role, ids in needed.items():
        for row_id in ids:
            if row_id not in existing:
                make_account(session_factory, row_id, f"seed_{role}_{row_id}", role, class_id)
    ends_at = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    members = [{"user_id": student_id, "position": "host"}]
    members += [{"user_id": user_id, "position": "service"} for user_id in extra_members]
    with session_factory() as db:
        # Flush in dependency order: without relationship() edges the unit of work
        # does not topologically sort tables across plain ForeignKey constraints.
        db.add(core_models.TeamRow(id=1, class_id=class_id, name="一小组", members=members))
        db.add(core_models.TaskRow(id=1, class_id=class_id, teacher_id=teacher_id,
                                  status="published", data={"title": "助农直播实训"}))
        db.flush()
        db.add(core_models.SessionRow(id=1, task_id=1, team_id=1, status="preparing",
                                      rule_snapshot={"ends_at": ends_at},
                                      members_snapshot=members,
                                      preparation={}, preparation_version=0,
                                      initial_budget_cents=100000))
        db.flush()
        db.add(core_models.ProductRow(id=1, data={"title": "赣南脐橙 5斤装"}))
        db.flush()
        db.add(core_models.SessionProductRow(id=1, session_id=1, product_id=1,
                                             positioning="traffic", selling_points="产地直采、当季鲜果",
                                             sale_price_cents=2990, sort_order=1,
                                             title="赣南脐橙 5斤装", cost_cents=1500))
        db.flush()
        db.add(core_models.EventRow(id=1, session_id=1, type="audience_question", actor_id=None,
                                    source="rule", payload={"text": "什么时候发货？"},
                                    created_at=datetime.now(timezone.utc).isoformat()))
        db.commit()


def core_counts(session_factory):
    with session_factory() as db:
        return {
            "events": db.query(core_models.EventRow).count(),
            "orders": db.query(core_models.OrderRow).count(),
            "refunds": db.query(core_models.RefundRow).count(),
            "cash": db.query(core_models.CashEntry).count(),
        }
