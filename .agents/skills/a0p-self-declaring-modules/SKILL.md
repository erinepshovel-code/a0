---
name: a0p-self-declaring-modules
description: The core architectural pattern in a0p for building registries that grow without central edits. Each module declares its own metadata + handler in one file, a filesystem scanner discovers them at boot, and the registry is generated. Used by route modules, distill skills, a0-skills, and (now) tools. Pairs with a0p-module-doctrine which enforces the 400-line cap that this pattern naturally satisfies. Load this skill before building any new registry, refactoring a centralized dispatcher, or adding a "drop-a-file-and-it-shows-up" surface.
---

# Self-Declaring Modules

The pattern a0p uses everywhere a registry exists: **metadata + handler colocated in one file, scanner discovers them, registry is generated at boot.** Never edit a central list.

This skill is the *meta-pattern*. The 400-line cap and `# DOC` conventions in `a0p-module-doctrine` are how individual modules behave; this skill is how the *registries that hold them* are built.

---

## The Pattern

```
python/services/<registry_name>/
├── __init__.py          # Scanner + dispatcher. Discovery only — no business logic.
├── tool_a.py            # SCHEMA = {...} + async def handle(...)
├── tool_b.py            # SCHEMA = {...} + async def handle(...)
└── tool_c.py            # SCHEMA = {...} + async def handle(...)
```

Three rules. Violate any of them and the pattern degrades back into the central-dispatcher problem you were trying to escape.

### Rule 1 — Schema and handler are colocated

Every module exports both:

```python
# python/services/tools/image_generate.py
SCHEMA = {
    "type": "function",
    "function": {
        "name": "image_generate",
        "description": "Generate an image with Imagen-3.",
        "parameters": { ... },
    },
    "tier": "free",
    "approval_scope": None,
    "enabled": True,
}

async def handle(prompt: str, aspect_ratio: str = "1:1", **_) -> dict:
    ...
```

If a future "schema in DB" overlay applies (operational toggles like `enabled`, `tier`, `description_override`), it merges *on top of* the file-declared SCHEMA — the file remains source of truth for shape.

### Rule 2 — The scanner is deterministic and cache-stable

```python
def _discover() -> dict[str, ModuleType]:
    out = {}
    for path in sorted(glob.glob(_PATTERN)):    # sorted for stability
        spec = importlib.util.spec_from_file_location(...)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        out[mod.SCHEMA["function"]["name"]] = mod
    return out
```

- **`sorted(glob)`** — discovery order must be byte-identical across runs. Anything injected into prompt prefixes (manifest, tool list) must be cache-stable or you blow the prefix-cache savings.
- **mtime fingerprint** — cache the discovery output keyed by `tuple((path, mtime) for path in files)`. Re-scan only when the fingerprint changes. See `_discover_a0_skills` and `_discover_distillers` in `tool_executor.py` for the canonical implementations.
- **Lazy bodies, eager metadata** — load every SCHEMA at boot (cheap, prompt prefix needs them); load handler bodies on demand if they're heavy (image-gen SDK imports, etc.).

### Rule 3 — Registration is by file presence, not by central list

The registry is generated from the scanner output. There is **no `ALL_TOOLS = [...]` list to edit**. To add a tool, drop a file. To remove a tool, delete the file. To disable, set `SCHEMA["enabled"] = False`.

This is why the pattern needs the 400-line cap (see `a0p-module-doctrine` §Hard Rules) — once you have it, no module ever grows large enough to need to be split, because each one is one tool / one route / one skill / one distiller.

---

## Existing examples in this codebase

Read at least one before adding a new registry:

| Registry | Location | Scanner | Notes |
|---|---|---|---|
| Route modules | `python/routes/*.py` | `collect_doc_meta()`, `collect_ui_meta()` | Has 4-place registration in `__init__.py` — legacy pattern, predates full discovery. New registries should not require manual registration. |
| Distill skills | `.agents/skills/distill-*/SKILL.md` | `_discover_distillers()` in `tool_executor.py` | Pure-content; no handler. |
| a0-skills | `.agents/skills/a0-*/SKILL.md` | `_discover_a0_skills()` in `tool_executor.py` | Manifest cached into doctrine prefix. |
| ZFAE tools (legacy) | `python/services/tool_executor.py` (single file) | None — central registry | **Anti-pattern. Currently being refactored to this skill.** |

---

## Operational metadata fields (recommended)

Every SCHEMA should declare these even when the value is the default — explicit > implicit, and the scanner can use them for filtering:

```python
SCHEMA = {
    "type": "function",
    "function": { ... },                # The OpenAI-shape function declaration

    "tier": "free",                     # free | seeker | operator | patron | admin
    "approval_scope": None,             # None or scope name from approval_scopes table
    "enabled": True,                    # File-level enable; runtime DB overlay can flip
    "category": "media",                # For UI grouping in tools tab
    "cost_hint": "high",                # "free" | "low" | "medium" | "high"
    "side_effects": ["filesystem"],     # ["filesystem", "network", "billing", "external_account"]
    "version": 1,                       # Bump on breaking schema changes
}
```

The scanner exposes a typed view (e.g. `class ToolSpec`) that other systems consume — never reach into raw SCHEMA dicts from outside the registry module.

---

## When NOT to use this pattern

- **Single-implementation utilities** — `python/services/sigma.py` is one Σ store, not a registry. Don't fragment it.
- **Cross-cutting concerns** — auth, logging, the doctrine prefix builder. These are not extensible by file-drop and shouldn't pretend to be.
- **Anything called inside a hot loop** — the discovery scan is mtime-cached but adds at least one `os.stat` per file. Don't put per-request work behind it.

---

## Refactor checklist (when converting a central dispatcher to this pattern)

1. Create `python/services/<name>/__init__.py` with scanner + dispatcher + cache.
2. Extract each tool/handler/etc. to its own file. Each file: `SCHEMA = {...}` + `async def handle(...)`. Keep under 400 lines (`a0p-module-doctrine` §Hard Rules).
3. Replace the central `TOOL_SCHEMAS_CHAT = [...]` and `if name == "x": ...` dispatch with calls into the registry.
4. Verify boot: `python -c "from python.services.<name> import registry; print(len(registry()))"`.
5. Run the existing tests — they should pass without modification if the dispatcher contract is preserved (`registry()`, `dispatch(name, **kwargs)`).
6. Add one new test: `test_every_tool_module_declares_schema_and_handle` — parametrize over discovered modules, assert both attributes exist and SCHEMA validates.
7. Re-stamp annotations: `python scripts/annotate.py`.
8. Confirm `tool_executor.py` (or whatever the old central file was) is now a thin re-export shim or deleted entirely.

---

## Anti-patterns to refuse

- **Registry edits required to add a module** — if a new file requires editing a central list, the pattern is broken.
- **Schema in code, handler somewhere else** — guarantees drift. Same file, always.
- **Non-deterministic discovery order** — `os.listdir()` without sorting will silently corrupt prompt-prefix caches across runs on different filesystems.
- **One file declaring two registry entries** — split it. The 400-line cap is your friend here, not your enemy.
- **Hot-reload that re-discovers on every request** — mtime cache or boot-time freeze. Pick one.
