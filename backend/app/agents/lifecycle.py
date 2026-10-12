"""C registers its models here. No second database, auth implementation or core simulation."""
from app.agents import models  # noqa: F401  ORM models must load before Base.metadata.create_all

MODULE_STATUS = "ready"


async def startup() -> None:
    return None


async def shutdown() -> None:
    return None
