---
name: a0p-agent-instantiation
description: Authoritative coding-agent guide for adding, changing, or debugging a0p agent instantiation. Use this whenever work touches Forge agent creation, AgentInstance construction/run semantics, PCNA sub-agent spawning or merging, sub_agent_spawn, spawn_executor, agent_runs lifecycle rows, or Claude SDK subagent definitions. This skill derives the correct method from the current implementation and tells coding agents which path to use instead of inventing a new one.
---

# a0p Agent Instantiation Method

Agent instantiation in a0p has three different seams. Pick the seam that matches the job; do not blend them.

1. **Runtime model handle** — `python/services/agent_instance.py::AgentInstance`
   - Use when code needs “an agent that can run messages against a model.”
   - Construction is intentionally side-effect-free. The model is called only by `.run()`.
   - Prefer `from_model(...)` for ad-hoc chat/focus/CLI work and `from_agent_id(...)` for user-owned Forge agents.

2. **Persistent Forge agent** — `python/routes/forge.py::instantiate`
   - Use when the user creates a named, reusable agent row in `agent_instances`.
   - Require `x-user-id`, validate tools against `TOOL_SCHEMAS_CHAT`, resolve the model through the model catalog, enforce per-user name uniqueness, then insert the row.
   - Do not silently fall back to a hard-coded model. `resolve_forge_model_id` requires either a body `model_id` or configured active provider.

3. **PCNA sub-agent run** — `python/services/tools/sub_agent_spawn.py` plus `python/services/spawn_executor.py`
   - Use when an existing run forks a child task for background or parallel work.
   - The tool inserts a fresh `agent_runs` row and returns a `run_id`; it does not call a model itself.
   - The executor atomically claims pending rows, binds run ContextVars, constructs an `AgentInstance`, runs the child task, logs events, and finalizes the run.

There is also an **in-memory PCNA fork registry** in `python/services/agent_lifecycle.py`. It owns live child PCNA engines for manual/admin spawn and merge operations. It is not a replacement for `agent_runs`; when a sub-run exists, pass `parent_run_id` and `run_id` into the registry so caps and orphan checks can reconcile memory with the DB.

---

## Decision table

| If you are asked to... | Use this path | Avoid |
|---|---|---|
| Run one model-backed agent from code | `AgentInstance.from_model(...).run(...)` | Direct provider calls from feature code |
| Run a user’s saved Forge agent | `await AgentInstance.from_agent_id(agent_id, user_id)` | Loading `agent_instances` without owner scoping |
| Create a reusable user-visible agent | `POST /api/v1/forge/instantiate` / `python/routes/forge.py` | Writing ad-hoc rows with unvalidated tools/models |
| Spawn parallel child work from an active run | `sub_agent_spawn` → `spawn_executor` → `sub_agent_merge` | Calling the model inside the spawn tool |
| Add Claude SDK private subagents | `a0/adapters/subagents.py` and mode maps | Giving private cores write tools or direct user output |
| Add a new spawning tool or orchestration mode | First load `a0p-fleet-runs` and follow its lifecycle checklist | New lifecycle states, log event names, or cap behavior invented locally |

---

## Canonical sub-agent lifecycle

Follow this shape for any code that creates child runs:

1. Read parent lineage with `get_current_run_id()`, `get_current_root_run_id()`, and `get_current_depth()`.
2. Read the user tier from `current_user_tier`.
3. Call `check_can_spawn(parent_run_id, parent_depth, tier)` before creating anything.
4. On cap failure, emit `cap_hit`, flush if practical, and return/raise an explicit cap error. Never silently downgrade.
5. Generate a UUID run id. `root_run_id` is the parent root or the new id for roots; child depth is `parent_depth + 1`.
6. Insert `agent_runs` before doing model work. Initial status is `running`; include `parent_run_id`, `root_run_id`, `depth`, `orchestration_mode`, `cut_mode`, `providers`, `spawned_by_tool`, and a short `task_summary`.
7. Emit `spawn_start` with enough payload to explain what was spawned.
8. Let `spawn_executor` claim and execute the row. Its claim/heartbeat/retry behavior is the supervisor boundary.
9. Bind run ContextVars inside the executor before model/tool work, and reset them in `finally`.
10. Emit `provider_response`, `tool_result`, `merge`, and `error` events using the allowed Fleet vocabulary.
11. Finalize exactly once with a terminal status and aggregated token/cost totals, then `await flush()`.
12. Merge/retire PCNA child state through `sub_agent_merge` or lifecycle helpers; do not leave live registry entries orphaned from DB rows.

The important distinction: **spawn records intent and lineage; executor performs work; merge absorbs results**.

---

## Runtime AgentInstance rules

When instantiating an `AgentInstance`:

- Treat `model_id`, `system_prompt`, `use_tools`, and `user_id` as the explicit binding contract.
- Resolve the provider with `ensure_resolved()` only when a caller needs the provider before the first `.run()`.
- Let `.run()` propagate `ValueError`, `PermissionError`, and `RuntimeError`; upstream code should decide how to surface failures.
- Keep `enforce_tier=True` and `enforce_enabled=True` unless an upstream path already enforced those gates and documents why it is safe to disable them.
- Preserve `meta` for traceability only. Do not send it to the model.

A correct minimal pattern:

```python
agent = AgentInstance.from_model(
    model_id,
    user_id=user_id,
    system_prompt=system_prompt,
    use_tools=True,
)
content, usage = await agent.run(messages, max_tokens=8000)
```

---

## Forge instantiation rules

When changing `python/routes/forge.py` or `python/services/forge_instantiation.py`:

- Require a signed-in caller via `require_forge_user_id`; never create user-owned agents anonymously.
- Resolve the archetype first, then derive default prompt/personality/tools from it.
- Validate requested tools against the live `TOOL_SCHEMAS_CHAT` names.
- Resolve the requested model through `resolve_forge_model_id` and `_validate_model`; do not introduce a default provider literal.
- Enforce per-user unique names before insert.
- Store personality, stats, loadout, avatar, and backstory as data on `agent_instances`; do not bake them into code paths that should remain model-agnostic.

---

## Claude SDK subagent definitions

When editing `a0/adapters/subagents.py` or `a0/adapters/claude_agent_adapter.py`:

- Keep private cognitive cores read-only: `Read`, `Grep`, `Glob` only.
- Let Meta-13/the parent own final user-visible output. Private subagents inform; they do not emit to the user.
- Update `MODE_SUBAGENTS` when adding a role so modes intentionally expose only the roles they need.
- Track invoked agents from Task/Agent tool-use metadata; do not expose private reasoning as the public answer.

---

## Common failure patterns to reject

- A spawn function calls the model directly before inserting `agent_runs`.
- New child work skips `check_can_spawn` or silently ignores `SpawnCapExceeded`.
- ContextVars are set without reset tokens.
- A background task relies on ambient context instead of copying/rebinding run scope.
- Code writes new `agent_runs.status` values not understood by Fleet/executor.
- Provider/model resolution falls back to a hard-coded vendor.
- Forge loads an agent by id without `owner_id` scoping.
- A private subagent is given write tools or direct authority over user-visible output.

---

## Files to inspect first

```text
python/services/agent_instance.py          # runtime model-backed agent handle
python/routes/forge.py                     # persistent Forge instantiation endpoint
python/services/forge_instantiation.py     # Forge identity/model helper functions
python/services/tools/sub_agent_spawn.py   # child run row creation and cap check
python/services/spawn_executor.py          # claims and executes spawned run rows
python/services/agent_lifecycle.py         # canonical live PCNA child registry
python/services/spawn_caps.py              # depth/fanout/concurrent-live cap enforcement
python/services/run_context.py             # run ContextVars and bind/reset helpers
python/services/run_logger.py              # allowed structured event vocabulary
a0/adapters/claude_agent_adapter.py        # Claude SDK parent orchestration
a0/adapters/subagents.py                   # Claude SDK private role definitions
```

If your change touches `agent_runs`, run lifecycle logging, or sub-agent spawning, load `a0p-fleet-runs` before editing. If it introduces or changes model tier choice, load `a0p-model-selector` too.
