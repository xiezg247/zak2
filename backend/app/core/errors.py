"""领域异常：由 service 抛出，api/errors 映射为 HTTP JSON。"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    status_code: int = 500

    def __init__(self, message: str, *, detail: Any | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = message if detail is None else detail


class NotFound(AppError):
    status_code = 404


class ValidationFailed(AppError):
    status_code = 400


class Unauthorized(AppError):
    status_code = 401


class Forbidden(AppError):
    status_code = 403


class RateLimited(AppError):
    status_code = 429


class UpstreamFailed(AppError):
    status_code = 502


class Conflict(AppError):
    status_code = 409


class Unavailable(AppError):
    status_code = 503
