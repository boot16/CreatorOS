"""Structured application logger. Emits key=value pairs, safe for grep + ingestion."""
import logging
import sys
import time
import uuid
from contextvars import ContextVar

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")
user_id_ctx: ContextVar[str] = ContextVar("user_id", default="-")


class ContextFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_ctx.get()
        record.user_id = user_id_ctx.get()
        return True


def _fmt() -> logging.Formatter:
    return logging.Formatter(
        fmt="%(asctime)s level=%(levelname)s request_id=%(request_id)s user_id=%(user_id)s logger=%(name)s msg=%(message)s"
    )


_configured = False


def configure_logging():
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_fmt())
    handler.addFilter(ContextFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    _configured = True


def get_logger(name: str) -> logging.LoggerAdapter:
    configure_logging()
    return logging.getLogger(name)


def new_request_id() -> str:
    rid = uuid.uuid4().hex[:12]
    request_id_ctx.set(rid)
    return rid


def set_user_id(uid: str | None):
    user_id_ctx.set(uid or "-")
