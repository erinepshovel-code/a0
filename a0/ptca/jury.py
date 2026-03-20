"""
a0/ptca/jury.py — jury sentinel extraction and meta-sentinel assembly.

Architecture (working freeze 2026-03-20):
    12 jury sentinels = 4 per live core (Phi, Psi, Omega)
    13th meta-sentinel = integrated gestalt of the twelve

Sensing levels:
    12   — sense at circle level (distributed reach across live-core interiors
            and the phonon field)
    13th — senses at seed level (unified adjudication; locus of operative "I")
    Guardian — acts at core level on the 13th's verdict
"""

from __future__ import annotations

from typing import List

from .types import Core, JurySentinel, MetaSentinel, SentinelCode


def build_jury(phi: Core, psi: Core, omega: Core) -> List[JurySentinel]:
    """Extract the 12 jury sentinels from the three live cores.

    Seeds 0–3 of each live core carry a SentinelCode; they are the sentinel seeds.
    Ordering: Phi sentinels (0–3), Psi sentinels (4–7), Omega sentinels (8–11).
    """
    jury: List[JurySentinel] = []
    global_index = 0

    for core in (phi, psi, omega):
        sentinel_seeds = [s for s in core.seeds if s.sentinel_code is not None]
        for seed in sentinel_seeds:
            jury.append(JurySentinel(
                sentinel_index=global_index,
                family=core.name,
                seed=seed,
                sentinel_code=seed.sentinel_code,  # type: ignore[arg-type]
            ))
            global_index += 1

    if len(jury) != 12:
        raise ValueError(
            f"Expected 12 jury sentinels, assembled {len(jury)}. "
            "Check JURY_SEEDS_PER_CORE in cores.py."
        )
    return jury


def build_meta_sentinel(jury: List[JurySentinel]) -> MetaSentinel:
    """Integrate the twelve into the 13th meta-sentinel.

    integrated_codes contains:
        • 12 unique_codes  (one per sentinel, e.g. "phi_0" … "omega_3")
        • 3  shared family codes ("phi", "psi", "omega"), deduplicated and sorted

    The meta-sentinel senses at seed level and is the sole jury-derived
    interface upward to Guardian.
    """
    unique_codes = [j.sentinel_code.unique_code for j in jury]
    shared_codes = sorted({j.sentinel_code.shared_code for j in jury})
    integrated = unique_codes + shared_codes   # 12 + 3 = 15

    return MetaSentinel(jury=jury, integrated_codes=integrated)
