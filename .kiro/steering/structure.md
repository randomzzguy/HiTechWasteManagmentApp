# Project Structure

## Root Layout
```
/
├── backend/          # FastAPI application
├── frontend/         # Next.js 14 application
├── mosquitto/        # Mosquitto MQTT broker config
├── scripts/          # DB setup SQL and seed scripts
├── docker-compose.yml
├── .env.example
└── PLAN.md           # Master reference document
```

## Backend (`backend/`)

```
backend/
├── main.py           # FastAPI app, middleware, router registration, lifespan
├── config.py         # pydantic-settings Settings class; use get_settings()
├── database.py       # Async + sync engines, Base, get_db() dependency
├── models/           # SQLAlchemy ORM models + Pydantic schemas (co-located)
├── routers/          # One file per domain: auth, clients, jobs, fleet, weighbridge,
│                     #   compliance, recyclables, destruction, bsf, esg, finance,
│                     #   reports, ai, websocket
├── agents/           # AI agent logic: orchestrator.py + one file per agent
├── rag/              # RAG pipeline: pipeline.py, ingestion, retriever, prompts
├── services/         # Business logic: pdf_generator, carbon_calculator, etc.
├── tasks/            # Celery: celery_app.py, agent_tasks.py, rag_tasks.py
├── mqtt/             # MQTT gateway for GPS telemetry ingestion
└── websocket/        # WebSocket connection manager
```

### Backend Patterns
- **Models file structure**: Each `models/*.py` contains both the SQLAlchemy ORM class and its Pydantic schemas (`*Create`, `*Read`, `*Update`) in the same file
- **Router pattern**: Routers use `get_db: AsyncSession = Depends(get_db)` for DB access; import settings via `get_settings()`
- **Agent routing**: `agents/orchestrator.py` detects intent via keyword scoring and returns the appropriate system prompt; actual LLM calls happen in the router
- **Celery tasks**: Import `SyncSessionLocal` directly; never use async sessions in tasks
- **Internal broadcast**: Celery workers push WebSocket alerts via `POST /internal/broadcast-alert` (Docker-internal only, not in public schema)

## Frontend (`frontend/src/`)

```
src/
├── app/
│   ├── (auth)/           # Login page, auth layout
│   ├── (dashboard)/      # All protected pages; shared dashboard layout
│   │   ├── layout.tsx    # Sidebar + TopBar + NotificationPanel shell
│   │   ├── dashboard/    # KPI overview page
│   │   ├── jobs/         # Job list + [id] detail
│   │   ├── clients/      # Client list + [id] detail
│   │   ├── fleet/        # Vehicle list + [id] detail
│   │   ├── weighbridge/
│   │   ├── compliance/scheduled-waste/
│   │   ├── recyclables/
│   │   ├── destruction/
│   │   ├── bsf-farm/
│   │   ├── esg/
│   │   ├── finance/
│   │   ├── ai-assistant/
│   │   ├── reports/
│   │   └── settings/
│   └── api/auth/         # NextAuth route handler
├── components/
│   ├── ui/               # shadcn/ui primitives (do not edit directly)
│   ├── layout/           # Sidebar, TopBar, NotificationPanel
│   ├── dashboard/        # KpiCards, TonnageChart, JobStatusSummary, etc.
│   ├── jobs/             # JobKanban, JobTable, JobForm, JobDetailPanel
│   ├── fleet/            # FleetMap, VehicleCard, MaintenanceCalendar
│   ├── compliance/       # SwBatchTable, ConsignmentNoteForm, DeadlineCalendar
│   ├── esg/              # CarbonDashboard, DiversionGauge, SdgAlignmentBadges
│   ├── ai/               # AIAssistantChat, AgentStatusPanel, AgentAlertFeed
│   └── shared/           # DataTable, StatusBadge, FileUploader, ConfirmDialog
├── hooks/                # useWebSocket, useJobs, useFleet, useAgentAlerts
├── lib/
│   ├── api.ts            # Axios instance + all API client functions (grouped by domain)
│   ├── auth.ts           # NextAuth options
│   └── utils.ts          # cn() and shared helpers
└── types/                # TypeScript interfaces: job.ts, client.ts, vehicle.ts, etc.
```

### Frontend Patterns
- **Route groups**: `(auth)` and `(dashboard)` are Next.js route groups — they share layouts but don't appear in the URL
- **API calls**: All calls go through `src/lib/api.ts` domain objects (`jobsApi`, `fleetApi`, `complianceApi`, etc.) — never call `axios` or `fetch` directly in components
- **AI streaming**: The AI chat uses native `fetch` with SSE (`EventSource`-style reader loop), not Axios, because Axios doesn't support streaming
- **Auth token**: Stored in `sessionStorage` / `localStorage` as `access_token`; injected by the Axios request interceptor automatically
- **Dark theme**: The UI uses a dark slate palette (`slate-950` backgrounds, `slate-800` cards, `emerald-500` accents). Match this when adding new components
- **Component naming**: PascalCase for all components; kebab-case for page directories
- **`'use client'` directive**: Required on any component using hooks, browser APIs, or event handlers
