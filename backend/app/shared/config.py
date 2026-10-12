from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_ROOT / ".env", override=False)


@dataclass(frozen=True)
class Settings:
    database_url: str
    cors_origins: tuple[str, ...]
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    llm_timeout_seconds: float

    @property
    def llm_configured(self) -> bool:
        return all((self.llm_base_url, self.llm_api_key, self.llm_model))


def get_settings() -> Settings:
    url = os.getenv("DATABASE_URL", "sqlite:///./data/platform.db")
    if url.startswith("sqlite:///./"):
        url = "sqlite:///" + str(BACKEND_ROOT / url.removeprefix("sqlite:///./"))
    return Settings(
        database_url=url,
        cors_origins=tuple(x.strip() for x in os.getenv(
            "CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173"
        ).split(",") if x.strip()),
        llm_base_url=os.getenv("LLM_BASE_URL", "").rstrip("/"),
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        llm_model=os.getenv("LLM_MODEL", ""),
        llm_timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "20")),
    )
