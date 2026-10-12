"""Safe configuration check; --probe sends one minimal request when configured."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
import httpx
from app.shared.config import get_settings

parser = argparse.ArgumentParser()
parser.add_argument("--probe", action="store_true")
args = parser.parse_args()
settings = get_settings()
missing = [name for name, value in [("LLM_BASE_URL", settings.llm_base_url),
           ("LLM_API_KEY", settings.llm_api_key), ("LLM_MODEL", settings.llm_model)] if not value]
if missing:
    print(json.dumps({"status": "not_configured", "missing": missing, "probe_sent": False}))
    sys.exit(2)
if not args.probe:
    print(json.dumps({"status": "configured_unverified", "probe_sent": False}))
    sys.exit(0)

started = time.monotonic()
try:
    # Compatible chat-completions protocol. BASE_URL must include the provider's API prefix.
    response = httpx.post(settings.llm_base_url + "/chat/completions",
        headers={"Authorization": "Bearer " + settings.llm_api_key},
        json={"model": settings.llm_model, "messages": [{"role": "user", "content": "Reply with OK."}]},
        timeout=settings.llm_timeout_seconds)
    response.raise_for_status()
    output = response.json()["choices"][0]["message"]["content"]
    if not isinstance(output, str) or not output.strip():
        raise ValueError("empty output")
    print(json.dumps({"status": "connected", "probe_sent": True,
                      "duration_ms": round((time.monotonic()-started)*1000)}))
except httpx.HTTPStatusError as exc:
    # Never dump response bodies or exception URLs; provider errors can echo credentials.
    print(json.dumps({"status": "failed", "kind": "http_error", "http_status": exc.response.status_code}))
    sys.exit(1)
except Exception as exc:
    print(json.dumps({"status": "failed", "kind": type(exc).__name__}))
    sys.exit(1)
