"""
a0/ptca/assembly.py — single entry point that wires the full system stack.

    stack = assemble_system()

The returned SystemStack is the complete assembled architecture ready for
use by the router, jury adjudication, and Guardian enforcement.
"""

from __future__ import annotations

from .cores import (
    build_guardian_core,
    build_live_core,
    build_memory_core,
    build_phonon_field,
)
from .jury import build_jury, build_meta_sentinel
from .tokens import build_all_tokens
from .types import SystemStack


def assemble_system() -> SystemStack:
    """Assemble and return the complete PTCA / PCTA / PCNA system stack.

    Build order:
        1. Three private live cores (Phi, Psi, Omega)
        2. Shared phonon / PCTA transport field
        3. Memory core
        4. Guardian core
        5. Jury (12 sentinels extracted from live cores)
        6. Meta-sentinel (integrated 13th)
        7. Seed tokens (one per live seed, 159 total)
    """
    phi = build_live_core("phi")
    psi = build_live_core("psi")
    omega = build_live_core("omega")
    phonon_field = build_phonon_field()
    memory = build_memory_core()
    guardian = build_guardian_core()
    jury = build_jury(phi, psi, omega)
    meta_sentinel = build_meta_sentinel(jury)
    tokens = build_all_tokens([phi, psi, omega])

    return SystemStack(
        phi=phi,
        psi=psi,
        omega=omega,
        phonon_field=phonon_field,
        memory=memory,
        guardian=guardian,
        jury=jury,
        meta_sentinel=meta_sentinel,
        tokens=tokens,
    )
