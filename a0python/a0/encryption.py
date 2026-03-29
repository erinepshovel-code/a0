"""Internal encryption for a0 persistent state.

Uses Fernet (AES-128-CBC + HMAC-SHA256) when A0_MEMORY_KEY is set.
Falls back to plaintext transparently when the key is absent or
the cryptography package is not installed — existing deployments
keep working with zero changes.

Generate a key (run once, store in Replit Secrets or .env):

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Set in .env or Replit Secrets:

    A0_MEMORY_KEY=<output above>

What is encrypted:
    state/memory.json      — jury-adjudicated cognitive state
    logs/{task_id}.jsonl   — per-request event log lines

What stays plaintext (low sensitivity):
    logs/{task_id}_provenance.json — hashes + types + timestamps only
    state/a0_state.json            — last_model string only
"""
from __future__ import annotations

import os
from typing import Optional


def _load_fernet() -> Optional[object]:
    """Return a Fernet instance if key + library are available, else None."""
    key = os.environ.get("A0_MEMORY_KEY", "").strip()
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet  # type: ignore[import]
        return Fernet(key.encode())
    except Exception:
        return None


# Module-level singleton — key is read once at import time.
_fernet = _load_fernet()


def is_active() -> bool:
    """True when encryption is on (key present + cryptography installed)."""
    return _fernet is not None


def encrypt(plaintext: str) -> str:
    """Encrypt a UTF-8 string. Returns ciphertext string or original if inactive."""
    if _fernet is None:
        return plaintext
    token: bytes = _fernet.encrypt(plaintext.encode("utf-8"))
    return token.decode("ascii")


def decrypt(ciphertext: str) -> str:
    """Decrypt a ciphertext string. Returns plaintext or original if inactive."""
    if _fernet is None:
        return ciphertext
    try:
        plain: bytes = _fernet.decrypt(ciphertext.encode("ascii"))
        return plain.decode("utf-8")
    except Exception:
        # Tolerate legacy plaintext files written before encryption was enabled.
        return ciphertext
