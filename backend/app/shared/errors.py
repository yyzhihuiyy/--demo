from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict | None = None):
        self.status = status
        self.code = code
        self.message = message
        self.details = details or {}


def success(data: Any) -> dict:
    return {"data": data}


def error_response(status: int, code: str, message: str, details: dict | None = None):
    return JSONResponse(status_code=status, content={"error": {
        "code": code, "message": message, "details": details or {},
    }})


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError):
        return error_response(exc.status, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_: Request, exc: RequestValidationError):
        # Never echo raw input: a validation failure may include credentials.
        fields = [{"path": list(e["loc"]), "message": e["msg"], "type": e["type"]}
                  for e in exc.errors()]
        return error_response(422, "VALIDATION_ERROR", "输入格式不正确", {"fields": fields})

    @app.exception_handler(HTTPException)
    async def handle_http(_: Request, exc: HTTPException):
        return error_response(exc.status_code, "HTTP_ERROR", str(exc.detail))
