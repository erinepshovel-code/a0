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
# === END CONTRACTS ===
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional

from sqlalchemy import text as _sa_text

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


def _resolve_provider(providers: Any) -> str:
    """Pick the provider id this row should bind to.

    `providers` may arrive as a JSON-encoded string (older inserts) or
    a list (newer). First entry wins for single-mode. 'active' resolves
    to the system's currently active provider. Empty / malformed input
    raises ValueError — the executor will mark the row failed.
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
    if pid == "active":
        active = energy_registry.get_active_provider()
        if not active:
            raise ValueError("no active provider configured for 'active' binding")
        return active
    return pid


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
    try:
        if mode not in _SUPPORTED_MODES:
            raise NotImplementedError(
                f"orchestration_mode={mode!r} not implemented by spawn_executor; "
                f"supported: {sorted(_SUPPORTED_MODES)}"
            )
        provider_id = _resolve_provider(row.get("providers"))

        # ---- (2) fork child PCNA from primary -------------------------
        parent_pcna, pcna_err = _try_get_primary_pcna()
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
                merge_payload = {
                    "sub_agent_name": sub_name,
                    "provider": provider_id,
                    "before": before,
                    "after": after,
                    "delta": delta,
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
