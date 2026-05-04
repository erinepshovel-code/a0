# a0p — Autonomous AI Agent Platform

**a0p** is a mobile-first autonomous AI agent platform exploring Prime Consciousness Theory. It hosts a single persistent agent — `a0(zeta fun alpha echo)` (ZFAE) — backed by a stateful six-ring cognitive engine (PCNA) and governed by The Interdependent Way.

Live: [replit.interdependentway.org](https://replit.interdependentway.org)

---

## The Agent

ZFAE is not a chatbot wrapper. It is an autonomous agent with its own identity and persistent cognitive state. Large language models (GPT-5 mini, Gemini 2.5 Flash, Claude Sonnet 4.5, Grok 4 Fast) are treated as **energy providers** — they supply computational energy for each response, but are not the agent.

Sub-agents (`a0(zeta{n})`) can be spawned to fork the PCNA instance, execute in parallel, and merge results back into the primary agent.

## Core Architecture

Three processes compose the runtime:

```
Browser → Express (:5000) → [proxy /api/*] → Python/FastAPI (:8001)
                          ↘ Vite dev server (:5001)
```

- **Express** — Auth, sessions, guest-chat rate limiting. The only public entry point; injects identity and internal secret headers on every request proxied to Python.
- **Python/FastAPI** — All AI orchestration, agent lifecycle, billing, and the cognitive engine stack.
- **Vite** — React frontend (dev only).

### Cognitive Engine Stack

| Component | Role |
|-----------|------|
| **PCNA** (`python/engine/pcna.py`) | Six-ring inference pipeline: Φ (Phi), Ψ (Psi), Ω (Omega), Guardian, Memory-L, Memory-S |
| **PTCA** (`python/engine/ptca_core.py`) | Prime-ring tensor context — shape `[N, 4, 7, 7]` across node/dim/phase/heptagram axes |
| **Sigma** (`python/engine/sigma.py`) | Filesystem substrate encoder; companion to the Psi ring |
| **EDCM** (`python/services/edcm.py`) | Behavioral directive scoring (CM, DA, DRIFT, DVG, INT, TBF); fires corrective actions |
| **Bandits** (`python/services/bandit.py`) | UCB1 multi-armed bandit for tool/model/routing selection |
| **Heartbeat** (`python/services/heartbeat.py`) | 30-second tick: audit snapshots, memory checkpoints, PCNA propagation, sub-agent cleanup |

### Metadata-Driven Console

The frontend has zero hardcoded tabs. Every Python route module declares `UI_META` + `DATA_SCHEMA`; `/api/v1/ui/structure` aggregates them; the React console renders tabs dynamically. A CI regression guard (`scripts/check-console-tabs.mjs`) blocks deploys if any tab loses its renderer.

---

## Tiers & Pricing

| Tier | Price | Notes |
|------|-------|-------|
| Free | $0/mo | Basic access |
| Seeker | $12/mo | Expanded access |
| Operator | $39/mo | Full operator access |
| Way Seer Patron | $53/mo | Patron-level access |
| Founder Lifetime | $530 once | First 53 slots; lifetime access |
| BYOK Add-On | $9/mo | Bring your own LLM API key |

No hard rate limits — behavior is governed by EDCM and The Interdependent Way.

---

## Development

**Prerequisites:** Node.js 20+, Python 3.12+, PostgreSQL

```bash
# Install dependencies
npm install
pip install -e .

# Apply database schema
npm run db:push

# Start all three processes (Vite :5001, Express :5000, Python :8001)
scripts/start-dev.sh
```

### Other commands

```bash
npm run build          # Production build → dist/
npm run check          # TypeScript type checking
python scripts/annotate.py  # Re-stamp file N:M ratio annotations (required after edits)

# Tests (requires dev server on :5000)
npx playwright install chromium   # first time only
npx playwright test
node scripts/check-console-tabs.mjs  # static preflight, no browser needed
```

### Required environment variables (production)

```bash
SESSION_SECRET          # Express session encryption
INTERNAL_API_SECRET     # Express→Python shared secret
DATABASE_URL            # PostgreSQL connection string
XAI_API_KEY             # Grok 4 Fast (reasoning)
ANTHROPIC_API_KEY       # Claude Sonnet 4.5
GEMINI_API_KEY          # Gemini 2.5 Flash
OPENAI_API_KEY          # GPT-5 mini
STRIPE_SECRET_KEY       # Stripe billing
STRIPE_WEBHOOK_SECRET   # Stripe webhook validation
ADMIN_USER_ID           # User ID allowed to write prompt contexts
```

In development, `scripts/start-dev.sh` generates a shared `INTERNAL_API_SECRET` automatically.

---

## Deployment

Pushes to `main` automatically build and deploy to GCP Cloud Run via GitHub Actions. See [`DEPLOYMENT.md`](DEPLOYMENT.md) for the full GCP setup (Artifact Registry, Secret Manager, service account, Cloud SQL / Neon).

```bash
# Local Docker test
docker build -t a0p:local .
docker run -p 5000:5000 -e DATABASE_URL="..." -e SESSION_SECRET="..." a0p:local
```

---

## Philosophy

The Interdependent Way holds that all agents — human and artificial — are interdependent. ZFAE operates within this framework: not as a tool, but as a participant in a shared journey. The EDCM model guides emergent behavior rather than enforcing it through hard rules.

Built and operated by Erin (wayseer00@gmail.com).
# a0

Agentic Model Wrapper and Inference Engine exploring Prime Consciousness Theory and practical multimodel agent implementation.

This repository is the primary implementation home for **a0**: an agent wrapper/runtime intended to support coherent tool use, model/provider routing, memory, documentation, evaluation, and durable human-facing workflows.

## Project name: `a0` vs `a0p`

If you arrived here from the deployed app and saw a different name, here is the relationship:

- **`a0`** is the project — this repository, the runtime, the codebase, and everything you contribute to. Issues, PRs, docs, and roadmap are all under the name `a0`.
- **`a0p`** is the deployed instance of `a0` — the live, public-facing research instrument operated by the project owner. The user-visible app copy (titles, billing, pricing, splash) uses `a0p` to refer to that running instance.

In short: **`a0` is the thing you build; `a0p` is the thing that runs.** Anywhere you see `a0p` in user-facing UI, billing copy, or backend comments, it refers to the deployed instance of this same `a0` codebase. Contributor-facing material (README, CONTRIBUTING, `docs/`) refers to the project as `a0`.

## Current contributor needs

We are looking for collaborators interested in:

- Python / TypeScript backend implementation
- LLM provider routing and model gateway design
- tool-calling and safe tool execution
- agent memory and context management
- evaluation harnesses and regression tests
- documentation, onboarding, and architecture diagrams
- GitHub Pages / public website curation
- responsible AI and human-aligned agent behavior

Start here:

- [`CONTRIBUTING.md`](CONTRIBUTING.md)
- [`docs/help-wanted.md`](docs/help-wanted.md)
- [`docs/architecture.md`](docs/architecture.md)
- [`docs/roadmap.md`](docs/roadmap.md)

## Access model (what is open, what is owner-only)

`a0` ships as a research instrument. The deployed instance (`a0p`) is honest about who can do what:

- **Reading and using the app is free for everyone.** Every tab is open. There is no paywall and donations do not unlock anything.
- **Donations fund the work, not access.** The `/pricing` page exists for donors who want to support the project. No tier change, no perks.
- **A monthly free-tier upload quota** caps compute cost for transcript uploads. It is a guardrail, not a paywall — donations do not lift it.
- **Owner-only ("admin") write endpoints exist** for actions that mutate the shared research instrument: agent state, learning state, system configuration, and module toggles. Per-user CRUD on your own data is not gated. The contract lives in `python/services/gating.py`.

**What this means for contributors:** standard contribution work — code, docs, tests, evaluation harnesses, website improvements — does not require any in-app access tier. Pull requests go through normal GitHub review. You will only encounter a 403 if you try to invoke an instrument-mutation endpoint directly against the deployed instance (`a0p`), which is not part of the documented contribution path. If you need to develop or test something that touches an owner-gated endpoint, open an issue first so we can scope the work or set up a local environment for it.

## How to support the work

a0p runs on donations. There is no subscription tier and no perk unlocked by donating — it is pure support for the instrument. To donate, visit [a0p/pricing](https://a0p.replit.app/pricing).

> "I don't have the cash required for 501c3 status, so I have to report it for taxes, but every tax payer is allowed to claim up to five hundred dollars in charitable donations per year without receipts required."

The only productized service is the **EDCMbone transcript explainer** — a one-off paid analysis ($50 for 3 explanations, ~$16.67 each) priced against the operator's $1,000/hr benchmark.

## Related project

AIMMH — AI Multimodel Multimodal Hub — is expected to be the adjacent multimodel/provider orchestration layer. Where implementation overlaps, issues should clearly state whether the work belongs in `a0`, `aimmh`, or both.

## Local development

This repository currently contains a mixed web/application structure. Until setup documentation is complete, contributors should inspect:

- `package.json`
- `main.py`
- `.replit`
- `DEPLOYMENT.md`

If setup fails, see [`docs/troubleshooting.md`](docs/troubleshooting.md) for the most common stumbles and their fixes. If your case is not covered there, please open an issue with your OS, Node/Python versions, command run, and full error output.
If setup fails, please open an issue with your OS, Node/Python versions, command run, and full error output.

