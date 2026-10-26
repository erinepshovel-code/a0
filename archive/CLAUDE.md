# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Commands

```bash
# Development (starts all 3 processes: Vite :5001, Express :5000, Python :8001)
scripts/start-dev.sh

# Production build (Vite → dist/public/, esbuild → dist/index.cjs)
npm run build

# TypeScript type checking
npm run check

# Push Drizzle schema to PostgreSQL
npm run db:push

# Re-stamp all files with N:M ratio annotation (required after edits)
python scripts/annotate.py
```

### Tests

```bash
# Install Playwright browser (first time only)
npx playwright install chromium

# Run all e2e tests (requires dev server on :5000)
npx playwright test

# Run a single test file
npx playwright test tests/e2e/console-tabs.spec.ts

# Console-tab regression guard (static preflight, no browser needed)
node scripts/check-console-tabs.mjs
```

---

## Architecture

This is a 3-process autonomous AI agent platform with a metadata-driven console UI.

### Process Topology

```
Browser → Express (:5000) → [proxy /api/*] → Python/FastAPI (:8001, internal only)
                         ↘ [dev] Vite (:5001)
```

- **Express** (`server/`) — Auth, sessions, guest-chat rate limiting, static serving. Adds `x-a0p-internal: <INTERNAL_API_SECRET>` and user identity headers (`x-user-id`, `x-user-email`, `x-user-role`) to every proxied request. Never expose the Python port directly.
- **Python/FastAPI** (`python/`) — All AI orchestration, PCNA engine, agent lifecycle, billing, heartbeat scheduler. Validates `x-a0p-internal` on every request.
- **Vite** — Dev only; proxied by Express.

### Frontend (Metadata-Driven Console)

`client/src/hooks/use-ui-structure.ts` polls `GET /api/v1/ui/structure`, which aggregates `UI_META` from every Python route module. The console (`client/src/pages/console.tsx`) renders tabs from this structure:

- Tabs listed in `CUSTOM_TAB_RENDERERS` → custom React component
- All other tabs → generic `TabRenderer` (schema-driven via `DATA_SCHEMA`)

The **console-tab regression guard** (`scripts/check-console-tabs.mjs`) and e2e test (`tests/e2e/console-tabs.spec.ts`) enforce that every API-declared tab has either a custom renderer or sections. CI blocks deploy on failure.

### Python Route Modules

Each route file in `python/routes/` is self-declaring: it exports a FastAPI `router` and defines `UI_META`/`DATA_SCHEMA` at the top. **Adding a new route requires 4 edits to `python/routes/__init__.py`**:
1. Import the router
2. Add to `ALL_ROUTERS`
3. Add filename to `collect_doc_meta()` file list
4. Add module name to `collect_ui_meta()` module list

File naming convention: `{name}.py` = self-contained module; `{name}_api.py` = thin delegate to a service in `python/services/`.

### Key Python Services

- `python/services/inference.py` — Orchestrates LLM calls (Grok-3 Mini/Grok-4 default, Claude, Gemini) across registered energy providers; injects tier-specific `prompt_context`
- `python/services/heartbeat.py` — 30-second tick: audit snapshots, memory checkpoints, PCNA propagation, sub-agent cleanup
- `python/services/tool_executor.py` — Tool invocation with approval gates
- `python/engine/pcna.py` — Six-ring PCNA inference pipeline (Phi/Psi/Omega/Guardian/Memory-L/Memory-S); six steps: Project → Inject → Propagate → PTCA-seed → PTCA-circle → Coherence (53-node ring engine)
- `python/services/edcm.py` — Behavioral directive scoring (CM, DA, DRIFT, DVG, INT, TBF); fires corrective actions and guides LLM selection
- `python/engine/sigma.py` — SigmaCore: encodes the workspace filesystem as a prime-ring tensor; companion to the Psi ring; has its own console tab (`SigmaTab`)

### Database

Schema source of truth is `shared/schema.ts` (Drizzle ORM); applied via `npm run db:push`. Python accesses the same PostgreSQL database via SQLAlchemy async (`python/database.py`, `python/models.py`).

### Auth & Tiers

Auth is handled entirely by Express. Tiers (Free → Seeker → Operator → Patron → Founder Lifetime) are stored on the user record, updated via Stripe webhook (`python/routes/billing.py`), and injected into the LLM system prompt as `prompt_context`.

### Skills System

The `skills/` directory and `skills-lock.json` implement a plugin-style skill registry. The `.agents/` directory contains agent-specific configuration and skill definitions (e.g., `.agents/skills/a0p-module-doctrine/SKILL.md`). Consult `.agents/skills/a0p-module-doctrine/SKILL.md` for authoritative module conventions before adding route modules.

---

## Conventions

- **File annotation** — Every file opens/closes with `// N:M` or `# N:M` (code:comment ratio). Run `python scripts/annotate.py` after edits.
- **Python route DOC blocks** — Each route file includes `# DOC module:`, `# DOC label:`, `# DOC description:`, `# DOC tier:`, `# DOC endpoint:` headers.
- **No file over 400 lines** — Annotation warns; split before it triggers CI.
- **All frontend `/api/*` calls go through Express on :5000** — never call Python :8001 directly.
- **Dynamic SQL UPDATE** — Use the column allowlist pattern already established in the codebase.

---

## Key Files

| File | Purpose |
|------|---------|
| `replit.md` | Platform overview and user preferences |
| `DEPLOYMENT.md` | GCP/Cloud Run setup and secrets |
| `spec.md` | Full agent platform spec (PCNA, EDCM, sentinel channels) |
| `.agents/skills/a0p-module-doctrine/SKILL.md` | Authoritative module conventions |
| `skills-lock.json` | Skill registry lock file |
| `python/routes/__init__.py` | Module registration (edit when adding routes) |
| `client/src/pages/console.tsx` | `CUSTOM_TAB_RENDERERS` map and tab rendering logic |
| `.github/workflows/deploy.yml` | CI pipeline (regression guard → deploy) |

---

## Environment Variables

Required in production (dev has safe fallbacks except where noted):

```bash
SESSION_SECRET          # Express session encryption (no fallback in prod)
INTERNAL_API_SECRET     # Express→Python shared secret (random per-process in dev — use start-dev.sh)
DATABASE_URL            # PostgreSQL connection string
XAI_API_KEY             # Grok (primary LLM / energy provider)
STRIPE_SECRET_KEY       # Stripe billing
STRIPE_WEBHOOK_SECRET   # Stripe webhook validation
ADMIN_USER_ID           # User ID allowed to write prompt contexts
```

---

## Git Workflow

- Main branch: `main`
- Feature branches: `<type>/<description>` (e.g., `claude/add-feature-abc`)
- Author: Erin Patrick Spencer
- License: see LICENSE
