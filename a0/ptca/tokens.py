"""
a0/ptca/tokens.py — seed token layer.

Tokens live permanently in the memory core.
Each live seed has exactly one corresponding seed token in the memory core.

Token structure per live seed:
    SeedToken
    └── TokenCircle   (1 per seed)
        └── token_tensors[0..6]   (7 ids — one tracking each of the 7 live-seed circles)

Total tokens: 3 live cores × 53 seeds = 159

Token custody is traded/checked among the 12 jury sentinels when a seed is
checked; the 13th meta-sentinel integrates from token-derived seed state.
"""

from __future__ import annotations

from typing import List

from .types import Core, Seed, SeedToken, TokenCircle


def build_token_for_seed(seed: Seed) -> SeedToken:
    """Build the memory-resident token identity for one live seed.

    The token_tensors list contains 7 ids — one for each of the
    seed's 7 live-core circles.
    """
    token_circle_id = f"tok:{seed.id}"
    token_tensors = [
        f"tok:{circle.id}"
        for circle in seed.circles
    ]
    return SeedToken(
        seed_id=seed.id,
        token_circle=TokenCircle(
            id=token_circle_id,
            seed_id=seed.id,
            token_tensors=token_tensors,
        ),
    )


def build_all_tokens(live_cores: List[Core]) -> List[SeedToken]:
    """Build one seed token for every seed in every live core.

    live_cores should be [phi, psi, omega] in the standard order.
    Returns 159 SeedToken objects (3 × 53).
    """
    tokens: List[SeedToken] = []
    for core in live_cores:
        for seed in core.seeds:
            tokens.append(build_token_for_seed(seed))
    return tokens
