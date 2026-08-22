"""Consistent API error shape.

All handlers should raise AppError (or FastAPI HTTPException).
Response body always has:
    {"error": {"code": "...", "message": "..."}}
"""
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, meta: dict | None = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.meta = meta or {}
        super().__init__(message)


# Well-known codes (extend as needed)
class Codes:
    UNAUTHENTICATED = "UNAUTHENTICATED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    INVALID_INPUT = "INVALID_INPUT"
    RATE_LIMITED = "RATE_LIMITED"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    UPSTREAM_ERROR = "UPSTREAM_ERROR"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    YOUTUBE_NOT_CONNECTED = "YOUTUBE_NOT_CONNECTED"
    NOT_COMPUTED = "NOT_COMPUTED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    DEMO_MODE_ONLY = "DEMO_MODE_ONLY"
    LLM_PARSE_ERROR = "LLM_PARSE_ERROR"


def _envelope(code: str, message: str, meta: dict | None = None):
    body = {"error": {"code": code, "message": message}}
    if meta:
        body["error"]["meta"] = meta
    return body


async def app_error_handler(_request: Request, exc: AppError):
    return JSONResponse(status_code=exc.status_code, content=_envelope(exc.code, exc.message, exc.meta))


async def http_exception_handler(_request: Request, exc: StarletteHTTPException):
    # Map common HTTP codes to error codes
    fallback = {
        401: Codes.UNAUTHENTICATED, 403: Codes.FORBIDDEN,
        404: Codes.NOT_FOUND, 400: Codes.INVALID_INPUT,
        413: Codes.PAYLOAD_TOO_LARGE, 429: Codes.RATE_LIMITED,
    }.get(exc.status_code, "HTTP_ERROR")
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
    return JSONResponse(status_code=exc.status_code, content=_envelope(fallback, detail))


async def validation_error_handler(_request: Request, exc):
    return JSONResponse(status_code=422, content=_envelope(Codes.INVALID_INPUT, "Invalid request payload"))
