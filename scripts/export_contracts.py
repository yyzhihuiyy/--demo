"""Run with backend/.venv/bin/python from project root."""
import inspect
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from pydantic.json_schema import models_json_schema
from app.shared import schemas

models = [cls for _, cls in inspect.getmembers(schemas, inspect.isclass)
          if cls.__module__ == schemas.__name__ and issubclass(cls, schemas.DTO) and cls is not schemas.DTO]
mapping, schema = models_json_schema([(cls, "validation") for cls in models])
schema["anyOf"] = [mapping[(cls, "validation")] for cls in models]
schema["title"] = "PlatformContracts"
path = ROOT / "frontend/src/shared/contracts.schema.json"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n")
print(f"Exported {len(models)} shared DTOs")
