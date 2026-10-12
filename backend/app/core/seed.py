"""Idempotent demo seeding from backend/fixtures/demo.json."""
import json
from datetime import timedelta
from pathlib import Path
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.access import now
from app.core.models import Account, Classroom, ProductRow, TeamRow, TaskRow
from app.core.rules import RULES_VERSION
from app.core.service import create_session_for_team, hash_password

FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "demo.json"


def load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def market_sample() -> dict:
    return load_fixture()["market_sample"]


def _seed_users(db: Session, fixture: dict) -> None:
    demo_password = fixture["demo_password"]
    for item in fixture["users"]:
        existing = db.scalars(select(Account).where(Account.username == item["username"])).first()
        if existing is not None:
            continue
        row = Account(id=item["id"], username=item["username"],
                      password_hash=hash_password(demo_password),
                      role=item["role"], class_id=item["class_id"], active=True)
        db.add(row)
    db.flush()


def _seed_classroom(db: Session, fixture: dict) -> None:
    item = fixture["classroom"]
    if db.get(Classroom, item["id"]) is None:
        db.add(Classroom(id=item["id"], name=item["name"], teacher_id=item["teacher_id"]))
    db.flush()


def _seed_teams(db: Session, fixture: dict) -> None:
    for item in fixture["teams"]:
        if db.get(TeamRow, item["id"]) is None:
            db.add(TeamRow(id=item["id"], class_id=item["class_id"], name=item["name"],
                           members=item["members"]))
    db.flush()


def _seed_products(db: Session, fixture: dict) -> None:
    for item in fixture["products"]:
        if db.get(ProductRow, item["id"]) is None:
            payload = {k: v for k, v in item.items() if k != "id"}
            db.add(ProductRow(id=item["id"], data=payload))
    db.flush()


def _seed_demo_task(db: Session, fixture: dict) -> None:
    count = db.scalar(select(func.count()).select_from(TaskRow))
    if count:
        return
    defaults = dict(fixture["task_defaults"])
    starts_at = now()
    ends_at = starts_at + timedelta(days=14)
    data = {
        "title": defaults["title"],
        "description": "助农直播完整链路实训：市场调研、货盘采购、开播互动、履约售后与复盘评分。",
        "target_audience": defaults["target_audience"],
        "initial_budget_cents": defaults["initial_budget_cents"],
        "target_gmv_cents": defaults["target_gmv_cents"],
        "market_heat": defaults["market_heat"],
        "difficulty": defaults["difficulty"],
        "score_weights": defaults["score_weights"],
        "starts_at": starts_at.isoformat(),
        "ends_at": ends_at.isoformat(),
        "rules_version": RULES_VERSION,
        "team_ids": [team["id"] for team in fixture["teams"]],
    }
    task = TaskRow(id=1, class_id=fixture["classroom"]["id"],
                   teacher_id=fixture["classroom"]["teacher_id"],
                   status="published", data=data)
    db.add(task)
    db.flush()
    for team_id in data["team_ids"]:
        team = db.get(TeamRow, team_id)
        if team is not None:
            create_session_for_team(db, task, team)
    db.flush()


def seed_demo(db: Session) -> None:
    fixture = load_fixture()
    _seed_users(db, fixture)
    _seed_classroom(db, fixture)
    _seed_teams(db, fixture)
    _seed_products(db, fixture)
    _seed_demo_task(db, fixture)
