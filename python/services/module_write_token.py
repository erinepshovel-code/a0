"""Single-use write confirmation tokens for ws_modules mutations.

Every create / update / delete / swap operation on a ws module must supply a
valid write token obtained from GET /api/v1/ws/modules/{id}/write-token.
Tokens are:
  - Server-side only (never persisted to DB)
  - Single-use: consumed the moment they are validated
  - TTL-bound: expire after TOKEN_TTL_SECONDS regardless of use
  - Bound to a specific (module_id, user_id) pair so they cannot be reused
    across targets or replayed by a different session

The "new" sentinel module_id is used when creating a brand-new module.
"""

import secrets
import time
from typing import Optional

TOKEN_TTL_SECONDS = 120

_store: dict[str, dict] = {}


def issue_token(module_id: str, user_id: str) -> str:
    """Issue a fresh single-use write token bound to (module_id, user_id)."""
    _purge_expired()
    token = secrets.token_urlsafe(32)
    _store[token] = {
        "module_id": str(module_id),
        "user_id": str(user_id),
        "expires_at": time.monotonic() + TOKEN_TTL_SECONDS,
    }
    return token


def consume_token(token: str, module_id: str, user_id: str) -> bool:
    """Validate and consume a write token.

    Returns True if the token is valid for the given (module_id, user_id) pair.
    Always removes the token from the store after the first attempted use,
    whether or not it matched — there is no retry on a rejected token.
    """
    _purge_expired()
    entry = _store.pop(token, None)
    if entry is None:
        return False
    if entry["module_id"] != str(module_id):
        return False
    if entry["user_id"] != str(user_id):
        return False
    return True


def _purge_expired() -> None:
    now = time.monotonic()
    expired = [k for k, v in _store.items() if v["expires_at"] < now]
    for k in expired:
        del _store[k]
