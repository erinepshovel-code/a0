import os
import hmac
import hashlib
import logging
from typing import Optional

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger(__name__)

SESSION_COOKIE = "a0p_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 7  # 7 days


def _get_secret() -> str:
    s = os.environ.get("SESSION_SECRET", "")
    if not s:
        raise RuntimeError("SESSION_SECRET env var is required")
    return s


def _derive_access_key() -> str:
    """
    Derive a short, human-readable access key from SESSION_SECRET.
    Format: XXXX-XXXX (8 hex chars, uppercase).
    """
    custom_key = os.environ.get("OPERATOR_KEY", "")
    if custom_key:
        return custom_key
    secret = _get_secret()
    digest = hmac.new(secret.encode(), b"a0p-operator-access-v1", hashlib.sha256).hexdigest()
    code = digest[:8].upper()
    return f"{code[:4]}-{code[4:]}"


def get_access_key() -> str:
    return _derive_access_key()


def verify_access_key(provided: str) -> bool:
    expected = _derive_access_key()
    provided_clean = provided.replace("-", "").upper()
    expected_clean = expected.replace("-", "").upper()
    return hmac.compare_digest(provided_clean, expected_clean)


def make_session_cookie(user_info: dict) -> str:
    s = URLSafeTimedSerializer(_get_secret())
    return s.dumps(user_info, salt="a0p-auth-v1")


def read_session_cookie(cookie_value: str) -> Optional[dict]:
    try:
        s = URLSafeTimedSerializer(_get_secret())
        return s.loads(cookie_value, salt="a0p-auth-v1", max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


class ReplitAuthMiddleware(BaseHTTPMiddleware):
    """
    Inject Replit-style auth headers from a signed session cookie.
    Also accepts native x-replit-user-id headers when running behind
    Replit's proxy (deployed / webview mode).
    """

    async def dispatch(self, request: Request, call_next):
        if not request.headers.get("x-replit-user-id"):
            session_cookie = request.cookies.get(SESSION_COOKIE)
            if session_cookie:
                user = read_session_cookie(session_cookie)
                if user:
                    extra = [
                        (b"x-replit-user-id", str(user.get("id", "")).encode()),
                        (b"x-replit-user-email", (user.get("email") or "").encode()),
                        (b"x-replit-user-name", (user.get("firstName") or "Operator").encode()),
                        (b"x-replit-user-profile-image",
                         (user.get("profileImageUrl") or "").encode()),
                    ]
                    request.scope["headers"] = list(request.scope.get("headers", [])) + extra
        return await call_next(request)
