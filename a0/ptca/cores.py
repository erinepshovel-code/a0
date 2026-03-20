"""
a0/ptca/cores.py — factory functions for each core type.

Spec constants (working freeze 2026-03-20):
    Live cores    (Phi, Psi, Omega): 53 seeds × 7 circles × 7 tensors
    Memory core                    : 17 seeds × 7 circles × 9 tensors
    Guardian core                  : 29 seeds total
        25 functional seeds G_k^f:
            circles: variable (count still open)
            inward face per circle: 5 tensors
            outward face per circle: 9 tensors
        4 sentinel seeds G_k^s:
            circles: variable (count still open)
            per circle: 11 Γ-typed tensors
                Γ₁–Γ₄ structural | Γ₅–Γ₈ executable | Γ₉–Γ₁₁ integrity

    Hard rules (canon-locked):
        functional seeds CANNOT write Γ tensors
        Γ updates require unanimous 4-sentinel consent + Meta-13 signature
"""

from __future__ import annotations

from typing import List

from .types import (
    Circle,
    CircularTensor,
    Core,
    GuardianTensorTopology,
    PhononField,
    Seed,
    SentinelCode,
    Tensor,
)

# ─────────────────────────────────────────────────────────────────────────────
# Spec constants
# ─────────────────────────────────────────────────────────────────────────────

LIVE_SEEDS = 53
LIVE_CIRCLES = 7
LIVE_TENSORS = 7
JURY_SEEDS_PER_CORE = 4          # seeds 0–3 in each live core are sentinel seeds

MEM_SEEDS = 17
MEM_CIRCLES = 7
MEM_TENSORS = 9                  # 7 standard + phase_variance + spin_variance

GUARD_SEEDS = 29
GUARD_FUNCTIONAL_SEEDS = 25      # G_k^f
GUARD_SENTINEL_SEEDS = 4         # G_k^s
GUARD_CIRCLES = 0                # variable — circle count still open
GUARD_INWARD_TENSORS = 5         # per functional circle inward face
GUARD_OUTWARD_TENSORS = 9        # per functional circle outward face
GUARD_SENTINEL_TENSORS = 11      # Γ₁–Γ₁₁ per sentinel circle

# Γ tensor layout (index 0-based): structural × 4, executable × 4, integrity × 3
GAMMA_LAYOUT: List[str] = (
    ["structural"] * 4 +    # Γ₁–Γ₄
    ["executable"] * 4 +    # Γ₅–Γ₈
    ["integrity"]  * 3      # Γ₉–Γ₁₁
)

# Topology singletons (shared across all seeds of each kind)
_FUNCTIONAL_TOPOLOGY = GuardianTensorTopology(
    inward_count=GUARD_INWARD_TENSORS,
    outward_count=GUARD_OUTWARD_TENSORS,
)
_SENTINEL_TOPOLOGY = GuardianTensorTopology(
    gamma_count=GUARD_SENTINEL_TENSORS,
    gamma_layout=GAMMA_LAYOUT,
)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_tensors(circle_id: str, count: int, start_standard: int = 0) -> List[Tensor]:
    """Build *count* Tensor objects for a circle.

    The last (count - start_standard) entries in a memory circle get
    non-standard tensor_types; for live/guardian cores every tensor is standard.
    """
    tensors = []
    for i in range(count):
        if i == count - 2 and count == MEM_TENSORS:
            t_type = "phase_variance"
        elif i == count - 1 and count == MEM_TENSORS:
            t_type = "spin_variance"
        else:
            t_type = "standard"
        tensors.append(Tensor(
            id=f"{circle_id}:t{i}",
            circle_id=circle_id,
            tensor_type=t_type,
        ))
    return tensors


def _make_circles(seed_id: str, n_circles: int, n_tensors: int) -> List[Circle]:
    circles = []
    for c in range(n_circles):
        cid = f"{seed_id}:c{c}"
        circles.append(Circle(
            id=cid,
            seed_id=seed_id,
            tensors=_make_tensors(cid, n_tensors),
        ))
    return circles


# ─────────────────────────────────────────────────────────────────────────────
# Public factories
# ─────────────────────────────────────────────────────────────────────────────

def build_live_core(family: str) -> Core:
    """Build one private PTCA live core (Phi, Psi, or Omega).

    53 seeds × 7 circles × 7 tensors.
    Seeds 0–3 are marked as sentinel seeds with shared + unique codes.
    """
    family = family.lower()
    seeds: List[Seed] = []
    for s in range(LIVE_SEEDS):
        seed_id = f"{family}:s{s}"
        is_sentinel = s < JURY_SEEDS_PER_CORE
        sentinel_code = (
            SentinelCode(
                shared_code=family,
                unique_code=f"{family}_{s}",
            )
            if is_sentinel
            else None
        )
        seeds.append(Seed(
            id=seed_id,
            core_id=family,
            circles=_make_circles(seed_id, LIVE_CIRCLES, LIVE_TENSORS),
            sentinel_code=sentinel_code,
        ))
    return Core(name=family, core_type="live", seeds=seeds)


def build_memory_core() -> Core:
    """Build the shared memory core.

    17 seeds × 7 circles × 9 tensors.
    Tensors 7 and 8 of every circle carry phase_variance and spin_variance.
    """
    seeds: List[Seed] = []
    for s in range(MEM_SEEDS):
        seed_id = f"memory:s{s}"
        seeds.append(Seed(
            id=seed_id,
            core_id="memory",
            circles=_make_circles(seed_id, MEM_CIRCLES, MEM_TENSORS),
        ))
    return Core(name="memory", core_type="memory", seeds=seeds)


def build_guardian_core() -> Core:
    """Build the Guardian core.

    29 seeds × 0 circles (provisional — circle count still open) × 5 tensors.
    When the circle count is frozen, update GUARD_CIRCLES and re-assemble.
    """
    seeds: List[Seed] = []
    for s in range(GUARD_SEEDS):
        seed_id = f"guardian:s{s}"
        seeds.append(Seed(
            id=seed_id,
            core_id="guardian",
            circles=_make_circles(seed_id, GUARD_CIRCLES, GUARD_TENSORS),
        ))
    return Core(name="guardian", core_type="guardian", seeds=seeds)


def build_phonon_field() -> PhononField:
    """Build the shared phonon / PCTA transport field.

    Connects Phi / Psi / Omega without mixing their private seed geometries.
    Circular tensor machinery initialised to identity state (θ=0, r=1).
    """
    return PhononField(
        circular_tensor=CircularTensor(
            theta=0.0,
            r=1.0,
            ell=0.0,
            A_k=[],
            H_k=[],
            P_k=[],
        ),
        connected_cores=["phi", "psi", "omega"],
    )
