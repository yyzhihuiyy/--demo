from collections.abc import Generator
from pathlib import Path
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine, event, String
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.shared.config import get_settings


class Base(DeclarativeBase):
    pass


class PlatformMetadata(Base):
    __tablename__ = "platform_metadata"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(String(500))


def create_db_engine(url: str):
    parsed = make_url(url)
    if parsed.get_backend_name() != "sqlite":
        raise ValueError("MVP supports SQLite only")
    if parsed.database and parsed.database != ":memory:":
        Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 10})

    @event.listens_for(engine, "connect")
    def configure_connection(connection, _):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=10000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    return engine


engine = create_db_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Request-scoped session; business services explicitly commit their transaction."""
    with SessionLocal() as db:
        try:
            yield db
        except Exception:
            db.rollback()
            raise


DbSession = Annotated[Session, Depends(get_db)]
