# Tech Stack

## Frontend
- **Framework**: Next.js 14 (App Router), TypeScript, React 18
- **UI**: shadcn/ui (Radix UI primitives), Tailwind CSS, Lucide icons
- **Charts**: Recharts
- **Maps**: Leaflet + react-leaflet
- **State**: TanStack Query v5 (server state), Zustand (client state)
- **HTTP**: Axios with Bearer token interceptors; SSE via native `fetch` for AI streaming
- **Auth**: NextAuth.js v4 with JWT strategy, CredentialsProvider → FastAPI backend
- **Notifications**: Sonner (toasts)

## Backend
- **Framework**: FastAPI (Python 3.11), Uvicorn
- **ORM**: SQLAlchemy 2.0 async (asyncpg driver for FastAPI, psycopg2 for Celery)
- **Validation**: Pydantic v2 + pydantic-settings
- **Auth**: python-jose (JWT), passlib/bcrypt
- **Task Queue**: Celery 5 + Redis broker; celery-beat for scheduled tasks
- **PDF**: WeasyPrint + ReportLab + Jinja2 HTML templates
- **MQTT**: aiomqtt (async) for GPS telemetry ingestion
- **HTTP Client**: httpx (async), aiohttp

## Databases & Infrastructure
- **Primary DB**: PostgreSQL 15 via TimescaleDB image (`timescale/timescaledb:latest-pg15`)
- **Time-series**: TimescaleDB hypertable on `weighbridge_records` (partition key: `recorded_at`)
- **Vector DB**: Milvus v2.3 (with etcd + MinIO dependencies) on port 19530
- **Cache / Broker**: Redis 7 on port 6379
- **LLM**: Ollama (llama3 default, nomic-embed-text for embeddings) on port 11434
- **MQTT Broker**: Eclipse Mosquitto 2 on port 1883
- **Object Storage**: MinIO (used by Milvus) on port 9000

## Key Conventions
- All REST routes are prefixed `/api/v1/`
- WebSocket routes use raw `/ws/*` paths (no `/api/v1` prefix)
- Error envelope: `{ "error": { "code", "message", "detail" } }`
- UUIDs used as primary keys throughout (`uuid.uuid4`, PostgreSQL `UUID` type)
- Settings loaded via `pydantic-settings` from `.env`; accessed via `get_settings()` singleton (`@lru_cache`)
- Async DB sessions via `get_db()` FastAPI dependency; sync sessions via `SyncSessionLocal` for Celery
- Alembic for production migrations; `create_all_tables()` for dev convenience on startup

## Common Commands

### Start full stack
```bash
docker compose up -d
```

### Start specific service
```bash
docker compose up -d postgres redis ollama
```

### Backend (local dev, from `backend/`)
```bash
uvicorn main:app --reload --port 8000
```

### Celery worker (from `backend/`)
```bash
celery -A tasks.celery_app worker --loglevel=info --concurrency=4
```

### Celery beat scheduler (from `backend/`)
```bash
celery -A tasks.celery_app beat --loglevel=info
```

### Frontend (from `frontend/`)
```bash
npm run dev      # development
npm run build    # production build
npm run lint     # ESLint
```

### Database migrations (from `backend/`)
```bash
alembic upgrade head
alembic revision --autogenerate -m "description"
```

### Pull Ollama models
```bash
docker exec hitech_ollama ollama pull llama3
docker exec hitech_ollama ollama pull nomic-embed-text
```

### Health checks
- API liveness: `GET /`
- API readiness (checks DB + Redis + Ollama): `GET /health`
- API docs: `GET /docs`
