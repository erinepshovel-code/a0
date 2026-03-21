"""Omega — private cognitive core.

Omega thinks. Omega does not emit outward directly.
"""
from __future__ import annotations

from typing import Any

from ._base import PrivateCore


class Omega(PrivateCore):
    """Tertiary private cognitive core."""

    name = "omega"

    def _process(self, stimulus: Any) -> Any:
        return {"core": self.name, "processed": True, "stimulus_type": type(stimulus).__name__}
