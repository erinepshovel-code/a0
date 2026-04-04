# CLAUDE.md — AI Assistant Guide for a0

This file describes the repository structure, development workflows, and conventions for AI assistants working in this codebase.

---

## Repository Overview

This repository contains two sibling Python packages:

| Package | Path | Purpose |
|---------|------|---------|
| **a0python** | `a0python/` | Full application stack: CLI, Gradio web UI, adapters, cores, governance |
| **edcm-org** | `edcm-org/` | Standalone EDCM diagnostic library (stdlib only, no external deps) |

The root `a0/` directory is the primary implementation module (symlinked or mirrored in `a0python/a0/`).

**Core concept:** The system implements the PTCA (Prime Tensor Circular Architecture) — a governance-first, multi-subagent reasoning framework. EDCM (Energy-based Dialogue/Cognitive Metrics) provides the diagnostic layer for measuring conversational strain, deflection, refusal, and coherence.

---

## Directory Structure

```
a0/                          # Primary implementation
├── a0.py                    # CLI entry point (reads JSON, calls handle())
├── contract.py              # A0Request / A0Response dataclasses
├── router.py                # Request dispatch logic
├── model_adapter.py         # ModelAdapter protocol + LocalEchoAdapter
├── state.py                 # Volatile config (last_model)
├── logging.py               # Event logging (JSONL)
├── jury.py                  # Jury adjudication layer (Laws 4, 5)
├── memory.py                # Continuity substrate (Law 11)
├── tiers.py                 # Tier 1 (volatile) / Tier 2 (committed) state
├── invariants.py            # InvalidStateError + require_hmmm()
├── heartbeat.py             # Maintenance-only lifecycle cycle
├── bandit.py                # Advisory salience machinery (advisory only)
├── provenance.py            # Append-only event logs with hash-chain
│
├── adapters/                # Model integration layer
│   ├── claude_agent_adapter.py  # Full PTCA subagent pipeline (Claude Agent SDK)
│   ├── subagents.py             # Phi/Psi/Omega/Jury/Bandit subagent definitions
│   ├── local_adapter.py         # Stub
│   ├── openai_adapter.py        # Stub
│   └── gemini_adapter.py        # Stub
│
├── tools/                   # Tool implementations (mostly stubs)
│   ├── edcm_tool.py         # run_edcm(text)
│   ├── pdf_tool.py          # run_pdf_extract(files)
│   └── whisper_tool.py      # run_whisper_segments(files)
│
├── cores/                   # Tensor field implementations
│   ├── _base.py             # PrivateCore base class
│   ├── phi.py               # Structural field (negation, contradiction detection)
│   ├── phonon.py            # Phonon transport layer
│   ├── psi/                 # Semantic field (lexical diversity, semantic density)
│   └── omega/               # Synthesis field (coherence, resolution, emission)
│       └── tensors/
│           ├── interdependent_way/
│           │   ├── architecture.py
│           │   ├── hmmm.py
│           │   └── laws.py      # 14 PTCA Core Laws
│           └── supporting/
│               ├── glossary.py
│               └── specs.py
│
├── guardian/                # Output gating and oversight
│   ├── approval_gate.py     # Requires approval for external effects
│   ├── audit.py             # Audit event recording
│   ├── emitter.py           # Guardian-gated JSON output (sole emitter, Law 9)
│   ├── recovery.py          # Quarantine + recovery shell
│   ├── sentinels.py         # 12 PTCA sentinel checks
│   └── ui/                  # Gradio web UI + Textual TUI fallback
│       ├── circles.py       # PCTA visualization
│       ├── seeds.py         # PTCA seed visualization
│       └── web/app.py       # Gradio web server
│
├── connectors/
│   └── emergent_connector.py    # Hub-style payload adapter
│
├── service/app.py           # FastAPI wrapper (disabled by default)
├── state/                   # Runtime state (a0_state.json created at runtime)
└── logs/                    # Event logs ({task_id}.jsonl)

edcm-org/                    # EDCM diagnostic library
├── src/edcm_org/
│   ├── types.py             # Metrics, Params, OutputEnvelope dataclasses
│   ├── metrics/             # Primary (C,R,D,N,L,O) + secondary (F,E,I) + progress (P)
│   ├── params/              # alpha, complexity, delta_max estimation
│   ├── basins/              # 8 EDCM diagnostic basin types + detection
│   ├── governance/          # Privacy guard, gaming detection, interventions
│   ├── io/                  # Data loaders and windowing
│   ├── eval/                # Spec compliance checker
│   └── cli.py               # edcm-org CLI entry point
└── tests/                   # 4 test files
```

---

## Architecture — The PTCA Three-Tier Stack

### Tiers

| Tier | Name | Role |
|------|------|------|
| PCNA | Prime Circular Neural Architecture | Five tensor fields (phi, psi, omega, guardian, memory) — inference engine |
| PCTA | Prime Circular Tensor Architecture | Circle tensors (phase-coordinate spectral transform) — spectral layer |
| PTCA | Prime Tensor Circular Architecture | 53-node routing lattice (49 compute + 4 sentinel seeds) — distributed routing |

### Tensor Fields

| Field | Module | Responsibility |
|-------|--------|----------------|
| **Phi** | `cores/phi.py` | Structural processing: negation, conditionals, contradiction detection |
| **Psi** | `cores/psi/` | Semantic processing: lexical diversity, semantic density |
| **Omega** | `cores/omega/` | Synthesis: coherence, resolution, text emission |
| **Guardian** | `guardian/` | Output gating — sole authorized emitter (Law 9) |
| **Memory** | `memory.py` | Continuity substrate, Jury-adjudicated, optionally encrypted |

### The 14 PTCA Core Laws (non-negotiable)

Defined in `a0/cores/omega/tensors/interdependent_way/laws.py`. Key laws to know:

- **Law 3** — Two-tier state model: Tier 1 (volatile, cycle-local) vs. Tier 2 (committed, identity-bearing)
- **Law 4, 5** — All Tier 2 persistence requires Jury adjudication; conflicts are preserved, never silently merged
- **Law 9, 10** — Guardian is the **sole authorized emitter**; all external output passes through Guardian
- **Law 11** — Memory is a continuity substrate; requires Jury token for every committed write
- **Law 13** — Bandit provides **advisory salience only**; it cannot choose, determine truth, or override Jury/Guardian
- **Law 14** — Fail-closed invariants: `require_hmmm()` blocks execution if the required `hmmm` field is missing

### Request/Response Contract

```python
# a0/contract.py
@dataclass
class A0Request:
    task_id: str           # UUID (auto-generated if absent)
    input: dict            # text, files, metadata
    tools_allowed: list    # e.g. ["pdf_extract", "whisper", "edcm"]
    mode: str              # "analyze" | "route" | "act"
    hmmm: dict             # hint/metadata passthrough — REQUIRED (Law 14)

@dataclass
class A0Response:
    task_id: str
    result: dict           # text, artifacts
    logs: list             # event log
    hmmm: dict             # passthrough
```

### Router Dispatch Order (`a0/router.py`)

1. `pdf_extract` in tools_allowed + files → `run_pdf_extract()`
2. `whisper` in tools_allowed + files → `run_whisper_segments()`
3. `edcm` in tools_allowed → `run_edcm(text)`
4. Fallback → select adapter, call `adapter.complete(messages)`

All dispatches are logged to `a0/logs/{task_id}.jsonl`.

### Adapter Protocol

```python
# a0/model_adapter.py
class ModelAdapter(Protocol):
    name: str
    def complete(self, messages: List[Dict], **kwargs) -> Dict[str, Any]: ...
```

Active adapters:
- `LocalEchoAdapter` — echoes last user message (always functional, used for testing)
- `ClaudeAgentAdapter` — full PTCA subagent pipeline (requires `anthropic-sdk` optional deps)
- `OpenAIAdapter`, `GeminiAdapter` — stubs only

---

## EDCM Metrics Reference

EDCM treats conversational dysfunction as a form of conserved energy flowing through a circuit.

### Metric Catalog

| Symbol | Name | Range | Description |
|--------|------|-------|-------------|
| **C** | Strain | [0, 1] | Cognitive/conversational load |
| **R** | Refusal | [0, 1] | Blocked/refused contributions |
| **D** | Deflection | [0, 1] | Avoidance or topic-shifting |
| **N** | Noise | [0, 1] | Low-signal or incoherent content |
| **L** | Coherence Loss | [0, 1] | Loss of logical thread |
| **O** | Overconfidence | [0, 1] | Unwarranted certainty |
| **F** | Fixation | [-1, 1] | Requires ≥2 windows |
| **E** | Escalation | [-1, 1] | Requires ≥2 windows |
| **I** | Inhibition | [-1, 1] | Requires ≥2 windows |
| **P** | Progress | [0, 1] | Decisions + commitments rate |

All ranges are hard-clamped by spec. Tests enforce these bounds.

### 8 EDCM Diagnostic Basins

Defined in `edcm-org/src/edcm_org/basins/taxonomy.py`:
1. `human_only` — topic requires human judgment
2. `standard` — normal operation
3. `cognitive_overload` — C > threshold
4. `refusal_loop` — R > threshold
5. `deflection_spiral` — D > threshold
6. `noise_cascade` — N > threshold
7. `stagnation` — P below threshold
8. `escalation_crisis` — E > threshold (multi-window)

### Governance Rules (Hard Rules, Never Relaxed)

- **No individual aggregation** — `EDCMPrivacyGuard` never outputs metrics for a single person
- **PII stripping** — Names, emails, IDs stripped before analysis
- **Gaming alerts** — 5 gaming patterns always computed and included in output
- **Minimum aggregation unit** — team/department/organization levels only

---

## Development Workflows

### Installation

```bash
# Full development environment
cd a0python
pip install -e ".[dev,anthropic,agent,tools]"

# EDCM library only
cd edcm-org
pip install -e ".[dev]"
```

### Configuration

Copy `a0python/.env.example` to `a0python/.env` and set:

```bash
A0_MODEL=local-echo          # adapter: local-echo | anthropic-api | claude-agent | local-ollama | local-llama | emergent
ANTHROPIC_API_KEY=sk-...     # required for anthropic-api and claude-agent adapters
A0_LOCAL_MODEL=llama3.2      # ollama model name
A0_OLLAMA_BASE=http://localhost:11434
A0_MEMORY_KEY=               # optional Fernet key for encrypted memory
A0_PORT=7860
A0_HOST=0.0.0.0
A0_RUNTIME=inference         # inference | training (Path B)
```

### Running the Application

```bash
# CLI (JSON in, JSON out)
echo '{"task_id": "t1", "input": {"text": "hello"}, "tools_allowed": [], "mode": "analyze", "hmmm": {}}' | python -m a0.a0

# Or from file
python -m a0.a0 request.json

# Gradio web UI
a0-web
# or
python -m a0.guardian.ui.web.app

# FastAPI service (disabled by default, not production-ready)
# Enable in service/app.py
```

### Running Tests

```bash
# All tests
python -m pytest edcm-org/tests/ tests/

# EDCM library tests only
python -m pytest edcm-org/tests/

# A0 smoke test only
python -m pytest tests/test_smoke.py

# With coverage (edcm-org requires ≥80%)
python -m pytest edcm-org/tests/ --cov=edcm_org --cov-branch --cov-fail-under=80
```

### EDCM CLI

```bash
edcm-org \
  --org <org_id> \
  --meeting <meeting_transcript.txt> \
  [--tickets <tickets.csv>] \
  --out <result.json> \
  [--aggregation department|team|organization] \
  [--window-id <window_id>]
```

---

## Key Conventions

### Python Style

- All modules use `from __future__ import annotations`
- Dataclasses for contract/type definitions (`A0Request`, `A0Response`, `Metrics`, `Params`, etc.)
- Protocol-based interfaces for pluggable components (`ModelAdapter`)
- Prefer explicit failure over silent fallback — fail-closed is the architectural default (Law 14)

### The `hmmm` Field

- Present in `A0Request`, `A0Response`, and many internal objects
- Carries hint/metadata through the pipeline
- **Required** — `require_hmmm()` raises `InvalidStateError` if missing (Law 14)
- Do not remove or default it to `None`; always pass `{}` at minimum

### State & Persistence

- **Tier 1 (volatile):** cycle-local, never persisted directly — just use normal variables
- **Tier 2 (committed):** requires a `jury_token` from `jury.py` before writing to memory
- Never write to `a0/state/` or `memory.py` without going through `Jury`
- Log events to `a0/logs/{task_id}.jsonl` (append-only JSONL)

### Output / Emission

- **All external output must go through `guardian/emitter.py`** (Law 9)
- Never emit JSON directly from tool or adapter code
- Use `guardian/approval_gate.py` for any action with external effects

### Bandit (Advisory Only)

- `bandit.py` weights candidates and modulates exploration
- It **cannot** make final decisions, determine truth, or override Jury/Guardian/Meta-13
- If you add salience logic, it belongs in `bandit.py`; if you add decision logic, it belongs elsewhere (Jury or router)

### Adapters

- New adapters implement `ModelAdapter` protocol in `a0/adapters/`
- Adapter name registered in `state.py` / environment config
- Stub adapters (`openai_adapter.py`, `gemini_adapter.py`) exist as templates

### edcm-org Library Rules

- **Zero external dependencies** — stdlib only in `edcm-org/src/`
- All metrics hard-clamped to spec ranges before output
- Privacy guard must be applied before any output — never expose individual-level data
- Gaming alerts are always computed and cannot be suppressed

---

## Known Limitations (v0.1)

From `suggest.md` and `spec.md`:

| Priority | Issue | Location |
|----------|-------|----------|
| **P0** | Marker counting uses naive split — misses edge cases | `edcm-org/src/edcm_org/metrics/extraction_helpers.py` |
| **P0** | Alpha parameter hardcoded to 0.5 — needs multi-window history | `edcm-org/src/edcm_org/params/alpha.py` |
| **P0** | `c_reduction` hardcoded to `0.0` in basin detection | `edcm-org/src/edcm_org/basins/detect.py` |
| **P1** | No JSON error handling on malformed input in router | `a0/router.py` |
| **P1** | Log files unbounded — no rotation | `a0/logging.py` |
| **P1** | State file (`a0_state.json`) has no file locking | `a0/state.py` |
| **P2** | Tool backends are stubs | `a0/tools/` |
| **P2** | OpenAI and Gemini adapters are stubs | `a0/adapters/` |
| **P2** | Window splitting ignores sentence boundaries | `edcm-org/src/edcm_org/io/loaders.py` |

Do not add workarounds that mask these issues; fix the root cause or leave a `# TODO(P0):` comment.

---

## File Relationships Quick Reference

| Want to... | Look at... |
|-----------|-----------|
| Change request/response shape | `a0/contract.py` |
| Add a new model adapter | `a0/adapters/`, implement `ModelAdapter` protocol |
| Add a new tool | `a0/tools/`, register in `a0/router.py` |
| Modify routing logic | `a0/router.py` |
| Change output format | `a0/guardian/emitter.py` |
| Add governance/audit logic | `a0/guardian/audit.py`, `sentinels.py` |
| Add EDCM metrics | `edcm-org/src/edcm_org/metrics/` |
| Modify basin detection | `edcm-org/src/edcm_org/basins/detect.py` |
| Add privacy rules | `edcm-org/src/edcm_org/governance/privacy.py` |
| Change PTCA laws | `a0/cores/omega/tensors/interdependent_way/laws.py` (avoid — immutable by design) |
| Understand the spec | `spec.md`, `README.md`, `edcm-org/spec/` |
| See the improvement backlog | `suggest.md` |
