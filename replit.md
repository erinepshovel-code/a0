# a0p — a research instrument

## Overview
a0p is a public research instrument exploring agent, energy-provider, and PCNA (Physically Conscious Neural Architecture) dynamics. It is designed for open access and serves as a deployed instance of the `a0` codebase. The project is donation-funded and does not solicit subscriptions. Its core purpose is to research advanced AI agent behaviors and their interactions within a defined architectural framework, focusing on areas like autonomous research, multi-armed bandits for decision-making, and sophisticated agent lifecycle management.

## User Preferences
- Clear and concise explanations.
- Iterative development and continuous feedback.
- Confirmation before significant codebase or external system changes.
- Detailed logging and transparency into the agent's decision-making process.
- Control over AI model selection and custom tool definitions.
- Feature toggles and tunable parameters.
- Mobile-first UI with dark mode by default.
- Full token accounting with per-model, per-stage, per-conversation cost tracking.
- All AI model conversations logged verbatim.
- Data export (transcripts, conversations, credentials list, system config).

## System Architecture

### Runtime
The application uses a three-tier architecture: an Express.js server (port 5000) for authentication, session management, and API proxying; a Vite development server (port 5001) for the React frontend; and a Python/FastAPI backend (port 8001) for AI and data processing. The Express server is the sole public entry point, securing the Python backend.

### Security
Security is enforced by internal header validation (`x-a0p-internal`) for Python backend access, and public endpoints like guest chat are rate-limited. Session secrets and internal API keys are configurable via environment variables.

### Python Backend (`python/`)
The Python backend, built with FastAPI, houses the core AI logic and data management. Key components include:
- **Database**: Async SQLAlchemy for ORM and migrations.
- **PCNA Engine**: A 53-node ring topology for the Physically Conscious Neural Architecture.
- **Services**: A variety of services manage agent lifecycle (`agent_lifecycle.py`), energy providers (`energy_registry.py`), inference orchestration (`inference.py`), research capabilities (`research.py`), and behavioral directives (`edcm.py`).
- **Energy Providers**: A modular system for integrating various LLMs (e.g., OpenAI, xAI Grok, Google Gemini, Anthropic Claude) via dedicated provider files.
- **Agent Spawning**: A background executor (`spawn_executor.py`) manages the lifecycle of sub-agents, including forking, inference, and merging of PCNA states.
- **Storage**: Core and domain-specific CRUD operations are managed by `storage/core.py` and `storage/domain.py`.

### Frontend (`client/`)
The frontend is a metadata-driven React + Vite + TypeScript application with Tailwind CSS and shadcn/ui components.
- **Dynamic UI**: The UI structure, including tabs and field rendering, is dynamically generated from backend metadata (`/api/v1/ui/structure`).
- **Component-based**: Utilizes `FieldRenderer`, `TabRenderer`, and `TabShell` for flexible UI construction.
- **Console and Chat**: Dedicated pages for agent console management and user chat interactions.
- **Admin Interfaces**: Includes admin-only interfaces for managing prompt contexts and system configurations.
- **Regression Guards**: Automated e2e tests and static preflight checks ensure UI consistency and prevent rendering issues for dynamically generated tabs.

### Database
PostgreSQL is used as the primary database, managed with SQLAlchemy for Python and Drizzle ORM for schema management (TypeScript).

### Agent Architecture
- **ZFAE Agent**: `a0(zeta fun alpha echo) {EnergyProvider}` represents the primary agent, with sub-agents (`a0(zeta{n}) {Provider}`) being PCNA forks for specific tasks.
- **Energy Providers (LLMs)**: LLMs are treated as energy sources and managed by an energy registry, supporting various models like Grok-4, Gemini 2.5/3, Claude Sonnet, and OpenAI GPT-5/5.5.
- **PCNA Engine**: A 53-node circular topology with Phi, Psi, Omega, and Theta rings, incorporating coherence tracking and state encryption.

### Key Concepts
- **UI_META + DATA_SCHEMA**: Enables metadata-driven UI generation and API documentation.
- **Heartbeat**: A 30-second tick for scheduled tasks like auditing, snapshots, and research.
- **Bandits**: Multi-Armed Bandit (UCB1) algorithms for optimizing tool, model, and routing decisions.
- **EDCM**: Behavioral directive scoring for agents.
- **Sub-agent lifecycle**: Defined process for forking, executing, and absorbing sub-agents.
- **Prompt Caching**: A multi-agent friendly caching strategy that orders system prompts from stable to volatile to maximize cache hits across different agents and turns, with specific pricing and normalization for various LLM providers.

### The Forge
A character-sheet style agent creation system (`forge.py`) allowing users to define agents with archetypes (e.g., Sage, Paladin), personality traits, stats, and suggested tools. It features self-updating registries for tools and models and supports per-user agent namespaces.

## External Dependencies
- **AI**: Gemini 2.5 Flash (Replit integration), Grok-3 Mini (XAI_API_KEY), Claude (Anthropic), OpenAI GPT-5/5.5.
- **Google Services**: Gmail, Google Drive (Replit connectors).
- **GitHub**: Repository operations, Codespace management (Replit connector + GITHUB_PAT).
- **Authentication**: Replit Auth (OpenID Connect).
- **Payments**: Stripe (for donations and one-off purchases, sandbox, Replit integration).
- **Database**: PostgreSQL (Replit managed).