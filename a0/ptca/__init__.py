"""
a0.ptca — PTCA / PCTA / PCNA / Jury / Guardian architecture module.

Primary public API:
    assemble_system() -> SystemStack
    SystemStack        (the fully assembled architecture dataclass)
"""

from .assembly import assemble_system
from .types import SystemStack

__all__ = ["assemble_system", "SystemStack"]
