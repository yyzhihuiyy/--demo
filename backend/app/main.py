from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core import lifecycle as core_lifecycle
from app.agents import lifecycle as agent_lifecycle
from app.core.router import router as core_router
from app.agents.router import router as agent_router
from app.shared.config import get_settings
from app.shared.db import Base, PlatformMetadata, SessionLocal, engine
from app.shared.errors import install_error_handlers, success
from app.shared.schemas import Envelope, Health


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Both module imports above must register their models before create_all.
    Base.metadata.create_all(engine)
    with SessionLocal.begin() as db:
        if db.get(PlatformMetadata, "contract_version") is None:
            db.add(PlatformMetadata(key="contract_version", value="1.1"))
    await core_lifecycle.startup()
    try:
        await agent_lifecycle.startup()
        try:
            yield
        finally:
            await agent_lifecycle.shutdown()
    finally:
        await core_lifecycle.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(title="直播运营虚拟仿真实训平台", version="0.1.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=list(get_settings().cors_origins),
                       allow_methods=["*"], allow_headers=["*"])
    install_error_handlers(app)
    app.include_router(core_router, prefix="/api")
    app.include_router(agent_router, prefix="/api")

    @app.get("/api/health", response_model=Envelope[Health], tags=["platform"])
    def health():
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return success(Health(status="ok", database="ok", contract_version="1.1",
                              modules={"core": core_lifecycle.MODULE_STATUS,
                                       "agents": agent_lifecycle.MODULE_STATUS},
                              model_configured=get_settings().llm_configured))

    return app


app = create_app()
