"""Per-request user context (set by auth middleware)."""
from contextvars import ContextVar
from typing import Optional

_current_user_id: ContextVar[Optional[int]] = ContextVar('current_user_id', default=None)
_current_is_admin: ContextVar[bool] = ContextVar('current_is_admin', default=False)


def _get_uid() -> int:
    uid = _current_user_id.get()
    if uid is None:
        raise PermissionError("Authentication required")
    return uid


def _is_admin() -> bool:
    return bool(_current_is_admin.get())
