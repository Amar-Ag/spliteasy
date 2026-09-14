"""Errors are returned as `{"detail": "<human readable message>"}` so the frontend can show them directly."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    status_code = 400

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class Unauthorized(ApiError):
    status_code = 401


class NotFound(ApiError):
    status_code = 404


class Conflict(ApiError):
    status_code = 409


class Unprocessable(ApiError):
    status_code = 422


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(_: Request, exc: ApiError) -> JSONResponse:
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        first = errors[0] if errors else {}
        location = ".".join(str(part) for part in first.get("loc", ()) if part not in ("body", "query", "path"))
        message = first.get("msg", "Invalid request")
        return JSONResponse(status_code=422, content={"detail": f"{location}: {message}" if location else message})
