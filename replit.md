# a0p — Autonomous AI Agent Platform

## Overview
a0p is an autonomous AI agent platform designed as a research instrument to explore and advance AI capabilities. It allows users to interact with a primary AI agent (ZFAE) and its sub-agents, leveraging various LLMs as "energy providers." The platform focuses on transparency, user control over AI interactions, and a modular architecture. Its core purpose is to facilitate research into AI agents, their lifecycle, and interaction with different LLM capabilities. The project emphasizes open access, with no paywalls for core features, and is funded through donations.

## User Preferences
- Clear and concise explanations; iterative development.
- Confirmation before significant codebase or external system changes.
- Detailed logging and transparency into the agent's decision-making.
- Owner control over AI model selection and tool definitions.
- Feature toggles and tunable parameters surfaced in UI.
- Mobile-first UI with dark mode by default.
- Full token accounting per-model, per-stage, per-conversation.
- All AI model conversations logged verbatim.
- Data export (transcripts, conversations, credentials list, system config).

## System Architecture

### Core Design Principles
The platform follows a metadata-driven approach where the Python/FastAPI backend declares `UI_META` and `DATA_SCHEMA` per route module, enabling the React frontend to act as a generic renderer. This ensures UI consistency and simplifies feature development. Access control is strictly two-tiered: an "Owner" with full administrative privileges and "Everyone" (including guests) with per-user CRUD capabilities and compute quotas. A gating contract enforces these access rules across all mutation routes.

### Runtime Environment
The application runs on three interconnected services:
- **Express Server (Port 5000):** Handles authentication, session management, guest chat, and proxies API requests to the Python backend, serving as the sole public entry point.
- **Vite Dev Server (Port 5001):** Hosts the React frontend during development.
- **Python/FastAPI Backend (Port 8001):** The primary AI and data backend, accessible only via the Express proxy.

All services are orchestrated via `scripts/start-dev.sh`. Edge security is maintained through an internal API secret exchanged between Express and Python.

### Python Backend
The Python backend, built with FastAPI, is responsible for AI logic, data management, and core services. Key components include:
- **Database Integration:** Async SQLAlchemy for PostgreSQL, with Drizzle ORM for schema management.
- **PCNA Engine:** A 53-node ring topology with Phi, Psi, Omega, and Theta rings for agent state management and propagation.
- **Agent Management:** Services for ZFAE agent definition, sub-agent lifecycle (forking, execution, merging), and bandit-based selection (UCB1).
- **Energy Registry:** Manages LLM providers, their pricing, and dispatching.
- **Gating Service:** Centralized enforcement of access control rules.
- **EDCM:** Behavioral directive scoring for agents.
- **Module Convention:** Adheres to a strict module doctrine for file structure, documentation, and hot-swapping.

### Frontend
The frontend, built with React, Vite, TypeScript, Tailwind CSS, and shadcn/ui, is fully metadata-driven. It dynamically renders UI components based on metadata fetched from the backend, supporting features like console tabs, chat, and an agent "Forge" for character-sheet style agent creation. Mobile-first design and dark mode are default.

### Agent Architecture
- **ZFAE Agent:** The primary agent, owning one PCNA instance.
- **Sub-agents:** Fork the PCNA instance, execute tasks using specific LLM providers, and merge results back into the parent PCNA.
- **Energy Providers:** LLMs (Grok, Gemini, Claude, OpenAI) are treated as computational resources, registered and managed by the `energy_registry`.
- **Prompt Caching:** A multi-agent friendly strategy composes system prompts in stable-to-volatile order, leveraging cache breakpoints for efficiency across different LLM providers.

## External Dependencies
- **AI Models:** Gemini 2.5 Flash (Replit integration), Grok (xAI), Claude (Anthropic), OpenAI (GPT-5 mini, GPT-5.5, GPT-5.5 Pro).
- **Cloud Services:** Google (Gmail, Drive via Replit connectors).
- **Version Control:** GitHub (repository operations, Codespace management via Replit connector).
- **Authentication:** Replit Auth (OpenID Connect).
- **Payments:** Stripe (for donations, sandbox via Replit integration).
- **Database:** PostgreSQL (Replit managed).