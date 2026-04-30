"""Contract tests for python.services.spawn_executor.

Each test is referenced from the CONTRACTS block in
python/services/spawn_executor.py. Run via:

    python -m python.tests.contract_runner

These tests touch the real database; they create uuid-prefixed rows
that they own end-to-end and clean up in finally blocks. No mocking
of the executor itself — _claim_one_pending and _execute_one are
called directly so the tests exercise the same code paths the poller
loop runs in production.
"""
from __future__ import annotations

import asyncio
import json
import uuid

from sqlalchemy import text as _sa_text

from ...database import get_session
from ...services.spawn_executor import (
    _claim_one_pending,
    _execute_one,
    _resolve_provider,
    _snapshot_pcna,
    _try_get_primary_pcna,
    _retire_fork_quietly,
)


async def _insert_pending_row(
    *,
    providers: list[str] | None = None,
    task: str = "test task",
    orchestration_mode: str = "single",
) -> str:
    """Insert a 'running' agent_runs row that the executor will pick up."""
    rid = f"test-spawn-{uuid.uuid4()}"
    async with get_session() as s:
        await s.execute(
            _sa_text(
                "INSERT INTO agent_runs "
                "(id, parent_run_id, root_run_id, depth, status, "
                " orchestration_mode, cut_mode, providers, "
                " spawned_by_tool, task_summary) "
                "VALUES (:id, NULL, :id, 0, 'running', :om, 'soft', "
                "        CAST(:p AS jsonb), 'sub_agent_spawn', :task)"
            ),
            {
                "id": rid,
                "om": orchestration_mode,
                "p": json.dumps(providers or ["__nonexistent_provider__"]),
                "task": task,
            },
        )
    return rid


async def _row_status(run_id: str) -> str | None:
    async with get_session() as s:
        r = await s.execute(
            _sa_text("SELECT status FROM agent_runs WHERE id = :id"),
            {"id": run_id},
        )
        row = r.first()
        return None if row is None else str(row[0])


async def _delete_run(run_id: str) -> None:
    async with get_session() as s:
        await s.execute(
            _sa_text("DELETE FROM agent_logs WHERE run_id = :id"),
            {"id": run_id},
        )
        await s.execute(
            _sa_text("DELETE FROM agent_runs WHERE id = :id"),
            {"id": run_id},
        )


async def test_claim_atomic() -> None:
    """Two concurrent claims of the same set succeed once and return None once."""
    rid = await _insert_pending_row()
    try:
        a, b = await asyncio.gather(_claim_one_pending(), _claim_one_pending())
        # At most one claim returned our specific row id; the other
        # returned None or some other row entirely (in case the test
        # DB has other pending rows). The contract is: our row is
        # claimed at most once.
        ours = [r for r in (a, b) if r and r["id"] == rid]
        assert len(ours) == 1, (
            f"expected exactly one claim of {rid}, got {len(ours)}: a={a}, b={b}"
        )
        status = await _row_status(rid)
        assert status == "executing", f"expected 'executing', got {status!r}"
    finally:
        await _delete_run(rid)


async def test_skips_non_running() -> None:
    """A row with status != 'running' is never claimed by the executor."""
    rid = f"test-spawn-{uuid.uuid4()}"
    async with get_session() as s:
        await s.execute(
            _sa_text(
                "INSERT INTO agent_runs "
                "(id, parent_run_id, root_run_id, depth, status, "
                " orchestration_mode, cut_mode, providers, "
                " spawned_by_tool, task_summary) "
                "VALUES (:id, NULL, :id, 0, 'completed', 'single', 'soft', "
                "        '[\"__nonexistent_provider__\"]'::jsonb, "
                "        'sub_agent_spawn', 'already done')"
            ),
            {"id": rid},
        )
    try:
        # Loop a few times since the test DB may have other pending rows
        # the claim consumes first. We just assert ours is never picked.
        for _ in range(5):
            r = await _claim_one_pending()
            if r is None:
                break
            assert r["id"] != rid, (
                f"completed row {rid} was claimed when it should have been skipped"
            )
        status = await _row_status(rid)
        assert status == "completed", (
            f"row status changed unexpectedly: {status!r} (should still be completed)"
        )
    finally:
        await _delete_run(rid)


async def test_marks_failed_on_exception() -> None:
    """When execution raises, the row is marked 'failed' and the poller continues."""
    rid = await _insert_pending_row(
        providers=["__definitely_not_a_real_provider_xyz__"],
        task="this will fail at provider resolution",
    )
    try:
        # Drain other pending rows until we claim ours (so the test is
        # robust to a noisy DB).
        claimed = None
        for _ in range(20):
            r = await _claim_one_pending()
            if r is None:
                break
            if r["id"] == rid:
                claimed = r
                break
            # Not ours — release it back so the test stays clean
            async with get_session() as s:
                await s.execute(
                    _sa_text(
                        "UPDATE agent_runs SET status = 'running' WHERE id = :id"
                    ),
                    {"id": r["id"]},
                )
        assert claimed is not None, f"never claimed our row {rid}"
        # _execute_one MUST NOT raise — it must catch and mark failed
        await _execute_one(claimed)
        status = await _row_status(rid)
        assert status == "failed", (
            f"expected 'failed' after unresolvable provider, got {status!r}"
        )
        # An error event should exist for this run_id
        async with get_session() as s:
            r = await s.execute(
                _sa_text(
                    "SELECT COUNT(*) FROM agent_logs "
                    "WHERE run_id = :id AND event = 'error'"
                ),
                {"id": rid},
            )
            err_count = int(r.scalar_one() or 0)
        assert err_count >= 1, f"expected ≥1 'error' log row for {rid}, got {err_count}"
    finally:
        await _delete_run(rid)


def test_resolve_provider_rejects_empty() -> None:
    """_resolve_provider raises ValueError on empty/malformed providers
    input — no silent default-to-active fallback."""
    try:
        _resolve_provider([])
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError on empty providers list")
    try:
        _resolve_provider("not a list and not json")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError on malformed providers")


def test_snapshot_pcna_shape() -> None:
    """_snapshot_pcna returns the four delta-tracked quantities with
    stable shape so before/after dicts can be subtracted in log payloads.
    Uses a fresh PCNAEngine to avoid depending on global state."""
    from python.engine import PCNAEngine
    p = PCNAEngine()
    snap = _snapshot_pcna(p)
    expected = {"phi", "psi", "omega", "theta_circles"}
    assert set(snap.keys()) == expected, (
        f"snapshot keys drift: got {set(snap.keys())}, expected {expected}"
    )
    assert isinstance(snap["phi"], float), f"phi must be float, got {type(snap['phi'])}"
    assert isinstance(snap["psi"], float), f"psi must be float, got {type(snap['psi'])}"
    assert isinstance(snap["omega"], float), f"omega must be float, got {type(snap['omega'])}"
    assert isinstance(snap["theta_circles"], int), (
        f"theta_circles must be int, got {type(snap['theta_circles'])}"
    )
    # Subtractability — what the merge log payload relies on
    snap2 = _snapshot_pcna(p)
    delta = snap2["phi"] - snap["phi"]
    assert isinstance(delta, float)


def test_merge_helpers_tolerate_no_pcna() -> None:
    """The merge helpers must degrade cleanly when the primary PCNA
    is unreachable. _try_get_primary_pcna returns (engine_or_None,
    error_or_None) — the two-value shape is the contract that lets
    callers log *why* PCNA was missing instead of swallowing it as a
    silent fallback. _retire_fork_quietly must accept None / empty
    name / unknown name without raising."""
    result = _try_get_primary_pcna()
    assert isinstance(result, tuple) and len(result) == 2, (
        f"_try_get_primary_pcna must return 2-tuple, got {type(result)}"
    )
    pri, err = result
    assert pri is None or hasattr(pri, "phi"), (
        f"_try_get_primary_pcna first element wrong shape: {type(pri)}"
    )
    assert err is None or isinstance(err, str), (
        f"_try_get_primary_pcna second element must be str|None: {type(err)}"
    )
    # When pri is None, err must be set; when pri is set, err must be None
    if pri is None:
        assert err, "missing PCNA must be accompanied by explicit error string"
    else:
        assert err is None, f"PCNA reachable but error string set: {err!r}"
    # _retire_fork_quietly must never raise on degraded inputs
    _retire_fork_quietly(None, "")
    _retire_fork_quietly(None, "nonexistent_sub_agent_name")
    _retire_fork_quietly(pri, "")
    _retire_fork_quietly(pri, "definitely_not_a_real_subagent_xyz")


async def test_bandit_round_trip() -> None:
    """Fork=pull, merge=reward — closed loop on PCNA.bandit_state.

    Deterministic: stubs the candidate pool, the cost gate, and the
    PCNA checkpoint+audit-insert sinks so the assertion runs without
    needing a real DB or any provider API key.
    """
    from python.engine import PCNAEngine
    from python.services import spawn_executor as _se
    from python.services.energy_registry import energy_registry

    parent = PCNAEngine()
    assert parent.bandit_state == {}, f"fresh PCNA must start empty: {parent.bandit_state!r}"

    fake_pool = ["fake-cheap", "fake-mid"]
    orig_candidates = _se._candidate_provider_ids
    orig_eligible = energy_registry.is_auto_selectable
    orig_audit = _se._append_bandit_pull
    orig_save = parent.save_checkpoint
    _se._candidate_provider_ids = lambda: list(fake_pool)
    energy_registry.is_auto_selectable = lambda pid: pid in fake_pool

    audit_calls: list[dict] = []
    async def _stub_audit(**kwargs):
        audit_calls.append(kwargs)
        return True
    _se._append_bandit_pull = _stub_audit

    save_calls: list[int] = []
    async def _stub_save():
        save_calls.append(1)
    parent.save_checkpoint = _stub_save

    try:
        pid, chosen = _se._resolve_provider(["bandit"], parent_pcna=parent)
        assert pid in fake_pool, f"picked {pid!r} not in {fake_pool}"
        assert chosen and chosen.get("arm_id") == pid, f"bad arm shape: {chosen!r}"
        assert any(a.get("arm_id") == pid for a in parent.bandit_state["provider"]), (
            f"arm {pid!r} not on parent: {parent.bandit_state!r}"
        )

        pulls_before = int(chosen.get("pulls", 0))
        payload = await _se._record_bandit_reward(
            parent, chosen,
            delta={"phi_delta": 0.05, "psi_delta": 0.04,
                   "omega_delta": 0.03, "theta_circles_delta": 1},
            cost_usd=0.01, total_tokens=500,
            spawn_id="test-bandit-round-trip",
        )
        assert payload and payload["domain"] == "provider" and payload["arm_id"] == pid
        assert payload["shape"] == "coherence_per_dollar"
        assert payload["cost_usd"] == 0.01, f"cost not recorded: {payload!r}"
        assert payload["audit_persisted"] is True, f"audit not awaited: {payload!r}"
        assert payload["checkpoint_persisted"] is True, (
            f"checkpoint not awaited: {payload!r}"
        )
        assert len(audit_calls) == 1, f"audit insert call count: {audit_calls!r}"
        assert audit_calls[0]["arm_id"] == pid
        assert audit_calls[0]["cost_usd"] == 0.01
        assert len(save_calls) == 1, f"checkpoint not saved exactly once: {save_calls!r}"
        assert int(chosen.get("pulls", 0)) == pulls_before + 1, (
            f"pulls did not increment: {pulls_before} → {chosen.get('pulls')}"
        )
        assert float(chosen.get("avg_reward", 0.0)) > 0.0, (
            f"avg_reward stuck at 0: {chosen!r}"
        )
    finally:
        _se._candidate_provider_ids = orig_candidates
        energy_registry.is_auto_selectable = orig_eligible
        _se._append_bandit_pull = orig_audit
        parent.save_checkpoint = orig_save


def test_bandit_skips_human_only() -> None:
    """Cost gate blocks UCB1 cold-start pick of a human-only-tier provider.

    Deterministic: monkey-patches the candidate pool to a single fake
    "human-only" id and stubs is_auto_selectable to reject it. No real
    provider config is consulted.
    """
    from python.engine import PCNAEngine
    from python.services import spawn_executor as _se
    from python.services.energy_registry import energy_registry

    parent = PCNAEngine()
    fake_human_only = "fake-pro-human-only"
    orig_candidates = _se._candidate_provider_ids
    orig_eligible = energy_registry.is_auto_selectable
    _se._candidate_provider_ids = lambda: [fake_human_only]
    energy_registry.is_auto_selectable = lambda pid: pid != fake_human_only
    try:
        try:
            _se._resolve_provider(["bandit"], parent_pcna=parent)
        except ValueError as exc:
            assert "human-only" in str(exc), f"wrong rejection message: {exc!r}"
        else:
            raise AssertionError("cost gate bypassed: bandit picked a human-only arm")
    finally:
        _se._candidate_provider_ids = orig_candidates
        energy_registry.is_auto_selectable = orig_eligible


def test_bandit_select_arm_handles_negative_rewards() -> None:
    """select_arm must not silently return None when all rewards are negative.

    A -1.0 best_score floor would have masked the regression on every
    arm and left the selector disabled. We seed three pulled arms with
    deeply negative avg_reward and assert the highest-scoring one is
    still chosen.
    """
    from python.services.bandit import select_arm
    arms = [
        {"arm_id": "a", "pulls": 5, "avg_reward": -10.0,
         "ucb_score": 0.0, "enabled": True},
        {"arm_id": "b", "pulls": 5, "avg_reward": -1000.0,
         "ucb_score": 0.0, "enabled": True},
        {"arm_id": "c", "pulls": 5, "avg_reward": -50.0,
         "ucb_score": 0.0, "enabled": True},
    ]
    chosen = select_arm(arms)
    assert chosen is not None, (
        "select_arm returned None despite enabled arms — -1.0 floor regression"
    )
    # Best avg_reward (least-negative) wins because exploration term is
    # equal across arms with equal pulls.
    assert chosen["arm_id"] == "a", (
        f"expected highest avg_reward arm 'a', got {chosen.get('arm_id')!r}"
    )


def test_bandit_state_round_trips_through_checkpoint() -> None:
    """Task #112 — bandit_state survives checkpoint save/load."""
    from python.engine.pcna import _arm_to_json, _arm_from_json
    from datetime import datetime
    arm = {
        "arm_id": "openai", "pulls": 5, "total_reward": 1.5, "avg_reward": 0.3,
        "ema_reward": 0.4, "ucb_score": 1.2, "enabled": True,
        "last_pulled": datetime(2026, 4, 30, 12, 0, 0),
    }
    j = _arm_to_json(arm)
    assert isinstance(j["last_pulled"], str), "datetime must serialize to str"
    back = _arm_from_json(j)
    assert isinstance(back["last_pulled"], datetime), "string must round-trip to datetime"
    assert back["pulls"] == 5 and back["arm_id"] == "openai"
    # Old snapshots without bandit_state default to {} — handled by load_checkpoint
    # via `data.get("bandit_state") or {}`. Empty/missing input here:
    assert _arm_from_json({}).get("last_pulled") is None
    assert _arm_to_json({"arm_id": "x"}).get("last_pulled") is None
