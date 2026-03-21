"""Psi — private cognitive core.

Psi thinks. Psi does not emit outward directly.
"""
from __future__ import annotations

from typing import Any

from ._base import PrivateCore


class Psi(PrivateCore):
    """Secondary private cognitive core."""

    name = "psi"

    def _process(self, stimulus: Any) -> Any:
        return {"core": self.name, "processed": True, "stimulus_type": type(stimulus).__name__}
