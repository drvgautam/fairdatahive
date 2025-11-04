from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    """Base structured application error with machine readable code."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    error_code: str = "app_error"

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: str | None = None,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if error_code is not None:
            self.error_code = error_code
        self.details = details


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "not_found"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    error_code = "conflict"


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "forbidden"


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "unauthorized"


class ValidationError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "validation_error"


class GoneError(AppError):
    status_code = status.HTTP_410_GONE
    error_code = "gone"


class PublishGuardError(ValidationError):
    error_code = "publish_guard_failed"


def _is_json_serializable(value: Any) -> bool:
    if value is None or isinstance(value, (str, int, float, bool)):
        return True
    if isinstance(value, (list, tuple)):
        return all(_is_json_serializable(v) for v in value)
    if isinstance(value, dict):
        return all(
            isinstance(k, str) and _is_json_serializable(v) for k, v in value.items()
        )
    return False


def _error_response(
    error_code: str,
    message: str,
    status_code: int,
    details: Any = None,
    request_id: str | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "error": error_code,
        "message": message,
        "request_id": request_id or str(uuid.uuid4()),
        "docs_url": f"/docs#errors/{error_code}",
    }
    if details is not None:
        body["details"] = details
    return JSONResponse(status_code=status_code, content=body)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return _error_response(
            exc.error_code, exc.message, exc.status_code, exc.details
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        _: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        code = {
            401: "unauthorized",
            403: "forbidden",
            404: "not_found",
            409: "conflict",
            410: "gone",
            422: "validation_error",
        }.get(exc.status_code, "error")
        if isinstance(exc.detail, str):
            message = exc.detail
            details = None
        elif isinstance(exc.detail, dict):
            message = str(exc.detail.get("message", exc.detail))
            details = exc.detail
        else:
            message = str(exc.detail)
            details = exc.detail if _is_json_serializable(exc.detail) else str(exc.detail)
        return _error_response(code, message, exc.status_code, details)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            "validation_error",
            "Request validation failed.",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=exc.errors(),
        )
