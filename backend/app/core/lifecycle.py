"""Core module lifecycle: idempotent seeding, restart recovery, single-process simulation loop."""
import asyncio
from contextlib import suppress
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.shared.db import SessionLocal
from app.core.access import now
from app.core.models import SessionRow, TaskRow
from app.core.seed import seed_demo
from app.core.service import append_event, force_end_session

MODULE_STATUS = "active"

_loop_task: asyncio.Task | None = None


def recover_interrupted_sessions(db) -> int:
    recovered = 0
    for session in db.scalars(select(SessionRow).where(SessionRow.status == "live")).all():
        session.status = "paused"
        append_event(db, session.id, "system_recovery", "rule",
                     {"action": "pause", "reason": "service_restart"})
        recovered += 1
    return recovered


def _deadline_over(db) -> None:
    stamp = now()
    for task in db.scalars(select(TaskRow).where(TaskRow.status == "published")).all():
        ends_at = (task.data or {}).get("ends_at")
        if ends_at and stamp >= datetime.fromisoformat(ends_at):
            task.status = "closed"
    for session in db.scalars(select(SessionRow).where(SessionRow.status.in_(["live", "paused"]))).all():
        ends_at = (session.rule_snapshot or {}).get("ends_at")
        if ends_at and stamp >= datetime.fromisoformat(ends_at):
            force_end_session(db, session, "deadline")


def run_simulation_cycle() -> None:
    from app.core.sim import advance_session_tick
    with SessionLocal() as db:
        for session in db.scalars(select(SessionRow).where(SessionRow.status == "live")).all():
            try:
                advance_session_tick(db, session)
                db.commit()
            except IntegrityError:
                db.rollback()
        try:
            _deadline_over(db)
            db.commit()
        except IntegrityError:
            db.rollback()


async def _run_loop() -> None:
    from app.core.rules import SIM_TICK_SECONDS
    while True:
        await asyncio.sleep(SIM_TICK_SECONDS)
        await asyncio.to_thread(run_simulation_cycle)


async def startup() -> None:
    global _loop_task
    with SessionLocal() as db:
        seed_demo(db)
        recover_interrupted_sessions(db)
        db.commit()
    _loop_task = asyncio.get_running_loop().create_task(_run_loop())


async def shutdown() -> None:
    global _loop_task
    if _loop_task is not None:
        _loop_task.cancel()
        with suppress(asyncio.CancelledError):
            await _loop_task
        _loop_task = None
