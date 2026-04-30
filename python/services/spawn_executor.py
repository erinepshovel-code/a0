# 248:14
# N:M
"""spawn_executor — execute the rows that sub_agent_spawn writes.

Closes the gap between `sub_agent_spawn` (which inserts an agent_runs
row but calls no model) and the inference layer (which has no awareness
of pending rows). The poller claims rows atomically, binds run-scoped
ContextVars, constructs an AgentInstance against the row's declared
provider, runs one inference turn with the row's task_summary as the
user message, and writes the result back via run_logger.emit so it
flows into the existing agent_logs stream and the merge tool's
JSONL artifact archival pipeline.

State machine (only state field on agent_runs is touched here):

    running   — written by sub_agent_spawn, awaiting executor
    executing — claimed by executor, inference in progress
    completed — inference finished, result + usage logged
    failed    — inference raised; error logged on the row
    merged    — sub_agent_merge called by parent (terminal — owned by merge)

Concurrency: rows are claimed via UPDATE … WHERE id IN (SELECT … FOR
UPDATE SKIP LOCKED LIMIT 1) RETURNING. Same shape as the stripe webhook
idempotency claim — a row can only be claimed once even across restarts
or competing poller instances.

Honest single-concern:
  * This module ONLY executes pending spawn rows. Orchestration modes
    (fan_out, council, daisy_chain, etc.) get a NotImplementedError
    until their own modules land — no silent fallback to single-mode.
  * Provider resolution honors the row's `providers` list. "active"
    resolves to energy_registry.get_active_provider(). Anything else is
    used as the model_id directly (resolve_model_id handles legacy
    provider-id matching). Failure to resolve raises and the row is
    marked failed — not silently rerouted.

# === CONTRACTS ===
# id: spawn_executor_claim_atomic
#   given: a single 'running' agent_runs row exists
#   then:  two concurrent _claim_one_pending() calls succeed once and
#          return None once; the row's status is 'executing' afterwards
#   class: idempotency
#   call:  python.tests.contracts.spawn_executor.test_claim_atomic
#
# id: spawn_executor_skips_non_running
#   given: an agent_runs row with status='completed' (or 'failed', 'merged')
#   then:  _claim_one_pending() does not return it
#   class: correctness
#   call:  python.tests.contracts.spawn_executor.test_skips_non_running
#
# id: spawn_executor_marks_failed_on_exception
#   given: a claimed row whose providers list resolves to an unknown id
#   then:  _execute_one raises no exception, the row's final status is
#          'failed', and an 'error' event was logged for the run_id
#   class: correctness
#   call:  python.tests.contracts.spawn_executor.test_marks_failed_on_exception
#
# id: spawn_executor_resolve_provider_rejects_empty
#   given: an empty list or malformed providers value
#   then:  _resolve_provider raises ValueError (no silent default-to-active)
#   class: correctness
#   call:  python.tests.contracts.spawn_executor.test_resolve_provider_rejects_empty
#
# id: spawn_executor_snapshot_pcna_shape
#   given: a primary-shaped PCNAEngine instance
#   then:  _snapshot_pcna returns the four delta-tracked floats/ints
#          (phi, psi, omega, theta_circles); types and ordering are
#          stable so log consumers can subtract before/after dicts
#   class: correctness
#   call:  python.tests.contracts.spawn_executor.test_snapshot_pcna_shape
#
# id: spawn_executor_merge_helpers_tolerate_no_pcna
#   given: a missing primary PCNA (cold-start or test bootstrap)
#   then:  _try_get_primary_pcna returns None and _retire_fork_quietly
#          returns without raising — degraded mode never crashes the
#          executor, satisfying the no-silent-fallback rule by routing
#          the absence into a 'pcna_fork_skipped' log event instead of
#          masking it as success
#   class: correctness
#   call:  python.tests.contracts.spawn_executor.test_merge_helpers_tolerate_no_pcna
#
# id: spawn_executor_bandit_round_trip
#   given: a parent PCNA with empty bandit_state and the 'bandit' sentinel
#   then:  _resolve_provider picks an auto-selectable arm onto
#          parent.bandit_state['provider'], and _record_bandit_reward
#          increments pulls + shifts avg_reward — no bandit_arms touch
#   class: correctness
#   call:  python.tests.contracts.spawn_executor.test_bandit_round_trip
#
# id: spawn_executor_bandit_skips_human_only
#   given: a candidate pool containing only a human-only provider id
#   then:  _resolve_provider raises ValueError — the cost gate prevents
#          UCB1's first-pass exploration from hitting the expensive tier
#   class: security
#   call:  python.tests.contracts.spawn_executor.test_bandit_skips_human_only
#
# id: spawn_executor_bandit_state_round_trips_through_checkpoint
#   given: a bandit arm with a datetime last_pulled field
#   then:  _arm_to_json / _arm_from_json round-trip cleanly so PCNA's
#          save_checkpoint / load_checkpoint can persist bandit_state
#          across restarts; missing fields default safely
#   class: correctness
#   call:  python.tests.contracts.spawn_executor.test_bandit_state_round_trips_through_checkpoint
# === END CONTRACTS ===
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional

from sqlalchemy import text as _sa_text

from . import bandit as _bandit
from .agent_instance import AgentInstance
from .energy_registry import energy_registry
from .run_context import bind_run, reset_run
from .run_logger import get_run_logger

_log = logging.getLogger("a0p.spawn_executor")

# Poll interval when no pending rows. Latency vs DB load tradeoff —
# 1s is fine for current spawn rates; lower via LISTEN/NOTIFY later if
# needed.
POLL_INTERVAL_S = 1.0

# Cap on how many sub-agent executions we'll have in-flight at once.
# A safety belt above and beyond spawn_caps (which bounds depth+fanout
# per parent). This bounds total concurrent model calls from ALL roots.
MAX_INFLIGHT = 16
_inflight: set[asyncio.Task] = set()


# Modes the executor is willing to drive end-to-end. Anything else
# raises NotImplementedError per the no-silent-fallback doctrine.
_SUPPORTED_MODES = frozenset({"single"})


async def _claim_one_pending() -> Optional[dict[str, Any]]:
    """Atomically claim one running spawn row. Returns row dict or None.

    SKIP LOCKED so multiple poller instances coexist; the WHERE clause
    is constrained to spawned_by_tool='sub_agent_spawn' so root-agent
    runs (which are written by other code paths) are not picked up.
    """
    from ..database import get_session
    sql = _sa_text(
        "UPDATE agent_runs "
        "SET status = 'executing' "
        "WHERE id = ("
        "  SELECT id FROM agent_runs "
        "  WHERE status = 'running' "
        "    AND spawned_by_tool = 'sub_agent_spawn' "
        "  ORDER BY started_at ASC "
        "  FOR UPDATE SKIP LOCKED LIMIT 1"
        ") "
        "RETURNING id, parent_run_id, root_run_id, depth, "
        "          orchestration_mode, providers, task_summary"
    )
    async with get_session() as s:
        row = (await s.execute(sql)).mappings().first()
        if row is None:
            return None
        return dict(row)


async def _persist_resolved_provider(
    run_id: str,
    provider_id: str,
    *,
    bandit_pull: Optional[dict] = None,
) -> None:
    """Persist the resolved provider AND, when present, the bandit pull
    metadata onto the agent_runs row. A crash between fork and merge
    leaves an unambiguous record of what arm was pulled, on which
    domain, with what UCB score and pulls_before — so a recovery job
    can reattribute the reward without guessing.
    """
    try:
        from ..database import get_session
        async with get_session() as s:
            await s.execute(
                _sa_text(
                    "UPDATE agent_runs "
                    "SET providers = CAST(:p AS jsonb), "
                    "    bandit_pull = CAST(:bp AS jsonb) "
                    "WHERE id = :id"
                ),
                {
                    "p": json.dumps([provider_id]),
                    "bp": json.dumps(bandit_pull) if bandit_pull else None,
                    "id": run_id,
                },
            )
    except Exception as exc:
        _log.warning(
            "[spawn_executor] could not persist resolved provider on %s: %s",
            run_id, exc,
        )


async def _mark_terminal(run_id: str, status: str, usage: dict | None = None) -> None:
    from ..database import get_session
    tokens = int((usage or {}).get("total_tokens", 0) or 0)
    cost = float((usage or {}).get("total_cost_usd", 0.0) or 0.0)
    async with get_session() as s:
        await s.execute(
            _sa_text(
                "UPDATE agent_runs "
                "SET status = :st, ended_at = CURRENT_TIMESTAMP, "
                "    total_tokens = :tok, total_cost_usd = :cost "
                "WHERE id = :id"
            ),
            {"st": status, "tok": tokens, "cost": cost, "id": run_id},
        )


# Both sentinels go through the bandit; explicit provider ids bypass it.
_SENTINEL_ACTIVE = "active"
_SENTINEL_BANDIT = "bandit"
_AUTO_SENTINELS = frozenset({_SENTINEL_ACTIVE, _SENTINEL_BANDIT})


def _candidate_provider_ids() -> list[str]:
    """Available providers for the bandit pool (env keys present)."""
    return [s["id"] for s in energy_registry.list_providers() if s.get("available")]


def _resolve_provider(
    providers: Any,
    *,
    parent_pcna: Any = None,
) -> tuple[str, Optional[dict]]:
    """Resolve providers field → (provider_id, chosen_arm_or_None).

    Sentinels "active" and "bandit" both run UCB1 over the cost-gated
    candidate pool ("active" = single-arm over the active provider).
    Explicit provider ids bypass the bandit. Malformed input raises.
    """
    if isinstance(providers, str):
        try:
            providers = json.loads(providers)
        except json.JSONDecodeError as exc:
            raise ValueError(f"providers field not valid JSON: {exc}") from exc
    if not isinstance(providers, list) or not providers:
        raise ValueError("providers list is empty or wrong shape")
    pid = str(providers[0]).strip()
    if not pid:
        raise ValueError("first provider entry is empty")

    if pid in _AUTO_SENTINELS:
        # Both "active" and "bandit" are bandit-driven learning paths.
        # "active" narrows the candidate pool to just the active
        # provider (1-arm bandit — still records reward history);
        # "bandit" considers every auto-selectable provider.
        if parent_pcna is None:
            raise ValueError(
                f"{pid!r} selector requires a reachable parent PCNA "
                f"(bandit_state lives on the PCNA core)"
            )
        if pid == _SENTINEL_ACTIVE:
            active = energy_registry.get_active_provider()
            if not active:
                raise ValueError("no active provider configured for 'active' binding")
            candidates = [active]
        else:
            candidates = _candidate_provider_ids()
            if not candidates:
                raise ValueError(
                    "'bandit' selector found no available providers"
                )
        arms = parent_pcna.bandit_state.setdefault("provider", [])
        chosen = _bandit.select_filtered(
            arms,
            candidates,
            is_eligible=energy_registry.is_auto_selectable,
        )
        if chosen is None:
            # Cost gate filtered everything out — surface the cause
            # rather than mark the row failed with a generic error.
            raise ValueError(
                f"{pid!r} selector: every candidate is human-only "
                f"(cost above gpt-5.5 baseline). Spawn explicitly "
                f"with a non-flagged provider id."
            )
        return str(chosen["arm_id"]), chosen

    # Explicit provider id — the caller's choice IS the human
    # instantiation event; cost gate does not apply.
    return pid, None


def _compute_cost_usd(provider_id: str, usage: Optional[dict]) -> float:
    """Real USD cost from a provider usage dict using pricing.json.

    Returns 0.0 when usage is missing or pricing is unknown — the
    bandit's cost floor (_MIN_COST_USD) handles the divide-by-zero;
    callers can detect the gap by reading usage themselves.
    """
    if not usage:
        return 0.0
    try:
        cb = energy_registry.cache_breakdown(usage)
        return float(energy_registry.estimate_cost(
            provider_id,
            cb.get("fresh_input", 0),
            cb.get("output", 0),
            cb.get("cache_read", 0),
            cb.get("cache_write", 0),
        ))
    except Exception as exc:
        _log.warning("[spawn_executor] cost estimation failed: %s", exc)
        return 0.0


async def _record_bandit_reward(
    parent_pcna: Any,
    arm: Optional[dict],
    *,
    delta: dict,
    cost_usd: float,
    total_tokens: int,
    spawn_id: str,
    shape: str = _bandit.DEFAULT_REWARD_SHAPE,
) -> Optional[dict]:
    """Update chosen arm + AWAIT bandit_pulls audit insert + checkpoint PCNA."""
    if arm is None or parent_pcna is None:
        return None
    try:
        reward = _bandit.compute_reward(
            delta, cost_usd=cost_usd, total_tokens=total_tokens, shape=shape,
        )
    except Exception as exc:
        _log.warning("[spawn_executor] reward compute failed: %s", exc)
        return None

    arm = _bandit.update_arm_stats(arm, reward)
    arm_id = str(arm.get("arm_id", ""))
    payload = {
        "domain": "provider",
        "arm_id": arm_id,
        "reward": reward,
        "shape": shape,
        "cost_usd": float(cost_usd),
        "pulls_after": int(arm.get("pulls", 0)),
        "avg_reward_after": float(arm.get("avg_reward", 0.0)),
        "ema_reward_after": float(arm.get("ema_reward", 0.0)),
    }
    pcna_id = getattr(parent_pcna.theta, "instance_id", "unknown")
    audit_ok = await _append_bandit_pull(
        spawn_id=spawn_id, parent_pcna_id=pcna_id, domain="provider",
        arm_id=arm_id, reward=reward, shape=shape, cost_usd=cost_usd,
    )
    payload["audit_persisted"] = audit_ok
    # Persist updated bandit_state so a restart between merge and the
    # next fork does not lose this learning event.
    try:
        await parent_pcna.save_checkpoint()
        payload["checkpoint_persisted"] = True
    except Exception as exc:
        _log.error("[spawn_executor] PCNA checkpoint save failed: %s", exc)
        payload["checkpoint_persisted"] = False
    return payload


async def _append_bandit_pull(
    *, spawn_id: str, parent_pcna_id: str, domain: str,
    arm_id: str, reward: float, shape: str, cost_usd: float,
) -> bool:
    """Awaited INSERT into bandit_pulls; True on success, False on failure
    (logged). The merge still completes either way — the in-memory PCNA
    update is the source of truth for the next pull."""
    try:
        from ..database import get_session
        async with get_session() as s:
            await s.execute(
                _sa_text(
                    "INSERT INTO bandit_pulls "
                    "(spawn_id, parent_pcna_id, domain, arm_id, reward, "
                    " reward_shape, cost_usd) "
                    "VALUES (:sid, :pid, :dom, :aid, :rw, :sh, :cu)"
                ),
                {"sid": spawn_id, "pid": parent_pcna_id, "dom": domain,
                 "aid": arm_id, "rw": float(reward), "sh": shape,
                 "cu": float(cost_usd)},
            )
        return True
    except Exception as exc:
        _log.error("[spawn_executor] bandit_pulls INSERT failed: %s", exc)
        return False


def _snapshot_pcna(p) -> dict:
    """Capture the four observable PCNA quantities used as merge deltas.

    Cheap — reads four floats off in-memory ring state. Safe to call on
    the same PCNA before and after absorb to compute the learning gain.
    """
    return {
        "phi": round(float(p.phi.ring_coherence), 6),
        "psi": round(float(p.psi.ring_coherence), 6),
        "omega": round(float(p.omega.ring_coherence), 6),
        "theta_circles": int(p.theta.circle_count.mean()),
    }


def _try_get_primary_pcna() -> tuple[Any, Optional[str]]:
    """Return (primary_pcna_or_None, error_or_None).

    Lazy import from ``python.main`` (where the singleton lives) so this
    module stays importable during early bootstrap and so the lazy import
    cleanly breaks the main↔services cycle. The two-value return surfaces
    *why* the PCNA was unreachable rather than collapsing into a silent
    None — callers log the reason so a real bug never masquerades as a
    benign 'primary unavailable' skip.
    """
    try:
        from ..main import get_pcna
    except Exception as exc:
        return None, f"import_failed: {type(exc).__name__}: {exc}"[:200]
    try:
        p = get_pcna()
    except Exception as exc:
        return None, f"call_failed: {type(exc).__name__}: {exc}"[:200]
    if p is None:
        return None, "get_pcna_returned_none"
    return p, None


def _retire_fork_quietly(parent_pcna, sub_name: str) -> None:
    """Best-effort fork cleanup for failure paths. Never raises."""
    if not sub_name or parent_pcna is None:
        return
    try:
        from .agent_lifecycle import merge_sub_agent
        merge_sub_agent(parent_pcna, sub_name)
    except Exception:
        pass


async def _execute_one(row: dict[str, Any]) -> None:
    """Run one claimed spawn row to terminal status. Never raises.

    Lifecycle (single mode):
      1. Bind run-scoped ContextVars from the row.
      2. Fork a child PCNA from the primary (if reachable). The fork
         carries the parent's full ring topology — the sub-agent's work
         updates THIS state, not the primary's.
      3. Construct an AgentInstance against the row's declared provider
         and run one inference turn with the row's task_summary.
      4. Feed the task and the model response into child.infer() so the
         child PCNA accumulates observations from the work just done.
      5. Snapshot parent state, absorb the child back into the parent,
         snapshot again — log the merge event with full before/after/delta
         payload so the user can SEE alpha echo's learning gain.
      6. Mark the row terminal (completed | failed). On any failure the
         fork is best-effort retired so it doesn't leak in _sub_agents.

    Exceptions during execution are converted to status='failed' plus
    an 'error' event on the run's log stream. The poller never sees
    them (so a single bad row cannot wedge the loop).
    """
    run_id = row["id"]
    mode = row.get("orchestration_mode") or "single"
    tokens = bind_run(
        run_id=run_id,
        depth=int(row.get("depth") or 0),
        root_run_id=row.get("root_run_id") or run_id,
        parent_run_id=row.get("parent_run_id"),
    )
    logger = get_run_logger()
    sub_name: Optional[str] = None
    parent_pcna = None
    merge_payload: Optional[dict] = None
    chosen_arm: Optional[dict] = None
    try:
        if mode not in _SUPPORTED_MODES:
            raise NotImplementedError(
                f"orchestration_mode={mode!r} not implemented by spawn_executor; "
                f"supported: {sorted(_SUPPORTED_MODES)}"
            )

        # ---- (2) fork child PCNA from primary -------------------------
        # Parent PCNA must resolve first so the bandit sentinel can read
        # parent.bandit_state. Resolution may raise (cost-gate failure);
        # the row is then marked failed in the outer except.
        parent_pcna, pcna_err = _try_get_primary_pcna()
        provider_id, chosen_arm = _resolve_provider(
            row.get("providers"),
            parent_pcna=parent_pcna,
        )
        if chosen_arm is not None:
            # Capture the pull metadata (domain, arm, ucb, pulls_before,
            # parent_pcna_id) so a crash before merge does not lose
            # the attribution chain. Persisted on agent_runs.bandit_pull
            # in the same UPDATE that resolves providers.
            pull_meta = {
                "domain": "provider",
                "arm_id": chosen_arm.get("arm_id"),
                "pulls_before": int(chosen_arm.get("pulls", 0)),
                "ucb_score": chosen_arm.get("ucb_score"),
                "parent_pcna_id": (
                    getattr(parent_pcna.theta, "instance_id", "unknown")
                    if parent_pcna is not None else None
                ),
            }
            await _persist_resolved_provider(
                run_id, provider_id, bandit_pull=pull_meta,
            )
            logger.emit("custom", {"phase": "bandit_pull", **pull_meta})
        if parent_pcna is not None:
            try:
                from .agent_lifecycle import spawn_sub_agent
                fork_info = spawn_sub_agent(parent_pcna, provider=provider_id)
                sub_name = fork_info.get("sub_agent_name")
                logger.emit("custom", {"phase": "pcna_fork", **fork_info})
            except Exception as exc:
                logger.emit("error", {
                    "stage": "pcna_fork",
                    "error": str(exc)[:300],
                })
                sub_name = None
        else:
            # explicit, not silent — the reason is logged so a genuine
            # bug here surfaces in the run stream instead of presenting
            # as a benign skip
            logger.emit("error", {
                "stage": "pcna_fork_skipped",
                "reason": pcna_err or "primary_pcna_unreachable",
            })

        # ---- (3) inference --------------------------------------------
        instance = AgentInstance.from_model(
            model_id=provider_id,
            user_id=None,
            use_tools=True,
            enforce_tier=False,
            enforce_enabled=True,
        )
        messages = [{"role": "user", "content": row.get("task_summary") or ""}]
        content, usage = await instance.run(messages)

        # ---- (4) feed observations to child PCNA ----------------------
        if sub_name:
            try:
                from .agent_lifecycle import get_sub_agent_engine
                child = get_sub_agent_engine(sub_name)
                if child is not None:
                    if row.get("task_summary"):
                        child.infer(row["task_summary"])
                    if content:
                        child.infer(content[:2000])
            except Exception as exc:
                logger.emit("error", {
                    "stage": "child_infer",
                    "error": str(exc)[:300],
                })

        # ---- (5) absorb child back into parent ------------------------
        if sub_name and parent_pcna is not None:
            try:
                from .agent_lifecycle import merge_sub_agent as _merge_now
                before = _snapshot_pcna(parent_pcna)
                absorb_result = _merge_now(parent_pcna, sub_name)
                after = _snapshot_pcna(parent_pcna)
                delta = {
                    "phi_delta": round(after["phi"] - before["phi"], 6),
                    "psi_delta": round(after["psi"] - before["psi"], 6),
                    "omega_delta": round(after["omega"] - before["omega"], 6),
                    "theta_circles_delta": (
                        after["theta_circles"] - before["theta_circles"]
                    ),
                }
                # Task #112 — fork=pull, merge=reward. Cost is computed
                # from provider pricing (not a missing usage["total_cost_usd"]
                # field), so coherence_per_dollar is actually cost-aware.
                cost_usd = _compute_cost_usd(provider_id, usage)
                total_tokens = int((usage or {}).get("total_tokens", 0) or 0)
                bandit_reward_payload = await _record_bandit_reward(
                    parent_pcna,
                    chosen_arm,
                    delta=delta,
                    cost_usd=cost_usd,
                    total_tokens=total_tokens,
                    spawn_id=run_id,
                )

                merge_payload = {
                    "sub_agent_name": sub_name,
                    "provider": provider_id,
                    "before": before,
                    "after": after,
                    "delta": delta,
                    "bandit": bandit_reward_payload,
                    **absorb_result,
                }
                sub_name = None  # ownership transferred — fork retired by absorb
                logger.emit("merge", merge_payload)
            except Exception as exc:
                logger.emit("error", {
                    "stage": "pcna_merge",
                    "error": str(exc)[:300],
                })

        logger.emit("spawn_complete", {
            "provider": provider_id,
            "content_preview": (content or "")[:500],
            "usage": usage,
            "mode": mode,
            "merge": merge_payload,
        })
        await _mark_terminal(run_id, "completed", usage)
    except Exception as exc:
        logger.emit("error", {
            "stage": "spawn_executor.execute",
            "error_type": type(exc).__name__,
            "error": str(exc)[:500],
        }, level="ERROR")
        try:
            await _mark_terminal(run_id, "failed")
        except Exception as inner:
            _log.error(
                "[spawn_executor] failed to mark run %s as failed: %s",
                run_id, inner,
            )
    finally:
        _retire_fork_quietly(parent_pcna, sub_name or "")
        reset_run(tokens)
        try:
            from .run_logger import flush as _flush
            await _flush()
        except Exception:
            pass


def _on_inflight_done(task: asyncio.Task) -> None:
    _inflight.discard(task)


async def _poll_loop() -> None:
    """Forever-loop. Claims and dispatches; sleeps when idle.

    Backpressure: when MAX_INFLIGHT is reached we stop claiming new
    rows and wait for any in-flight to finish before claiming again.
    The poller itself never raises; per-iteration exceptions log and
    sleep one cycle.
    """
    while True:
        try:
            if len(_inflight) >= MAX_INFLIGHT:
                await asyncio.sleep(POLL_INTERVAL_S)
                continue
            row = await _claim_one_pending()
            if row is None:
                await asyncio.sleep(POLL_INTERVAL_S)
                continue
            task = asyncio.create_task(
                _execute_one(row),
                name=f"spawn_exec_{row['id'][:8]}",
            )
            _inflight.add(task)
            task.add_done_callback(_on_inflight_done)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _log.exception("[spawn_executor] poll iteration failed: %s", exc)
            await asyncio.sleep(POLL_INTERVAL_S)


def inflight_count() -> int:
    """Test / introspection helper."""
    return len(_inflight)
# N:M
# 248:14
