# a0p

**a0p is an instrument of research, not a product.** It exists to be used,
inspected, and learned from. One agent (`a0(zeta fun alpha echo)`) owns one
PCNA core; LLMs (Gemini, Claude, Grok, GPT-5) are *energy providers*, not
agents; sub-agents fork PCNA, execute, and merge back. The console exposes
every internal — bandits, EDCM directives, PCNA rings, sub-agent merges,
prompt caches, model routing — for inspection.

## How to use

Open the deployed app, log in (or stay anonymous for guest chat), and explore.
Every console tab is open to every visitor. Per-user CRUD (your conversations,
your uploads, your forge agents) is yours to read and write. Per-user compute
quotas exist as budget guardrails, not paywalls.

## How to support

a0p is funded by donations. The pricing page (`/pricing`) shows a single
donation widget with no tiers, no features unlocked, no recurring charge.

> I don't have the cash required for 501c3 status, so I have to report it for
> taxes, but every tax payer is allowed to claim up to five hundred dollars in
> charitable donations per year without receipts required.

The EDCMbone explainer is the one product on the platform: 3 sessions free,
then $50 for 3 sessions ($16.67 each). That price reflects the underlying
expert-time math and is not a knob.

## Who can change the code or the instrument

There are exactly two write-access tiers:

1. **Owner** (the maintainer, identified by `ADMIN_USER_ID` /
   `ADMIN_PASSWORD`). Only the owner may execute writes that alter the
   instrument itself: code-adjacent configuration, shared learning state,
   model routing, system toggles, PCNA merges, EDCM weights, sub-agent
   spawn/merge, memory flush.
2. **Everyone else** (including anonymous visitors). May freely read every
   tab and freely perform per-user CRUD bounded by ownership checks.

This split is enforced in code by `python/services/gating.py::require_admin`
and a contract in `python/tests/contracts/gating.py` that walks every
mutation route and asserts each handler either calls a recognized owner gate
or appears on the explicit `python/services/gating_allowlist.py` allowlist.
The contract refuses to pass otherwise.

## Run it locally

1. Set required secrets: `SESSION_SECRET`, `INTERNAL_API_SECRET`,
   `OPENAI_API_KEY`, `XAI_API_KEY`, `STRIPE_SECRET_KEY`,
   `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`, `ADMIN_PASSWORD`,
   `DATABASE_URL`.
2. Run `bash scripts/start-dev.sh`. Three processes come up together:
   Express on `:5000` (public), Python/FastAPI on `:8001` (internal),
   Vite on `:5001` (internal, proxied through Express).
3. Verify invariants: `python python/tests/contract_runner.py`
   (16 pass expected).
4. Verify console regressions: `npx playwright test`.

For deeper architecture, doctrine, and the full module map see
[`replit.md`](./replit.md).
