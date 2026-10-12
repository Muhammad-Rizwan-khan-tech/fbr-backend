"""Execution context shared by the API, workers and the logging system.

Values are stored in ``contextvars`` so they follow the current request (asyncio
task / thread) or the current worker job and are automatically attached to every
structured log record and to audit entries.
"""
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Dict, Iterator, Optional

_FIELDS = (
    "request_id",
    "correlation_id",
    "tenant_id",
    "user_id",
    "invoice_id",
    "submission_id",
    "job_id",
)

_vars: Dict[str, ContextVar] = {name: ContextVar(f"ctx_{name}", default=None) for name in _FIELDS}


def new_id() -> str:
    return str(uuid.uuid4())


def get(name: str) -> Optional[str]:
    return _vars[name].get()


def set_values(**values: Optional[str]) -> None:
    for key, value in values.items():
        if key not in _vars:
            raise KeyError(f"Unknown context field: {key}")
        _vars[key].set(value)


def snapshot() -> Dict[str, Optional[str]]:
    return {name: var.get() for name, var in _vars.items()}


def get_correlation_id() -> str:
    """Return the active correlation id, creating one if none is active."""
    value = _vars["correlation_id"].get()
    if not value:
        value = new_id()
        _vars["correlation_id"].set(value)
    return value


@contextmanager
def bind(**values: Optional[str]) -> Iterator[None]:
    """Temporarily bind context values (used by worker jobs)."""
    tokens = []
    try:
        for key, value in values.items():
            if key not in _vars:
                raise KeyError(f"Unknown context field: {key}")
            tokens.append((_vars[key], _vars[key].set(value)))
        yield
    finally:
        for var, token in reversed(tokens):
            var.reset(token)


class ExecutionContext:
    @property
    def request_id(self) -> ContextVar:
        return _vars["request_id"]

    @property
    def correlation_id(self) -> ContextVar:
        return _vars["correlation_id"]

    @property
    def tenant_id(self) -> ContextVar:
        return _vars["tenant_id"]

    @property
    def user_id(self) -> ContextVar:
        return _vars["user_id"]

    @property
    def invoice_id(self) -> ContextVar:
        return _vars["invoice_id"]

    @property
    def submission_id(self) -> ContextVar:
        return _vars["submission_id"]

    @property
    def job_id(self) -> ContextVar:
        return _vars["job_id"]


execution_context = ExecutionContext()

