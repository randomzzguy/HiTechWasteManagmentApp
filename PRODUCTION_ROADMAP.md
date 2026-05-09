# Hi-Tech Waste Management — Production Readiness Roadmap

> Last updated: April 2026  
> Status: Demo → Production

This document tracks every gap between the current demo state and a fully production-ready release. Items are grouped by domain and ordered by priority.

---

## 1. Security & Authentication

### Critical (must fix before any real users)

- [ ] **Rotate all secrets** — `JWT_SECRET`, `NEXTAUTH_SECRET`, `MINIO_ACCESS_KEY/SECRET`, `POSTGRES_PASSWORD` in `.env` are all demo values. Generate cryptographically strong secrets (≥ 64 chars) and store them in a secrets manager (AWS Secrets Manager, HashiCorp Vault, or at minimum a `.env.production` that is never committed).
- [ ] **Lock down CORS** — `ALLOWED_ORIGINS=*` in config must be replaced with the actual production domain(s) (e.g. `https://app.hitechwaste.com.my`).
- [ ] **HTTPS everywhere** — Add TLS termination via a reverse proxy (Nginx/Caddy/Traefik) or a cloud load balancer. All HTTP traffic must redirect to HTTPS. Update `NEXTAUTH_URL` and `NEXT_PUBLIC_API_URL` to `https://`.
- [ ] **JWT refresh token rotation** — The current auth flow issues access tokens only. Implement refresh token rotation so sessions survive without re-login, and revoke refresh tokens on logout.
- [ ] **Rate limiting** — Add `slowapi` (or Nginx `limit_req`) to auth endpoints (`/api/v1/auth/login`, `/api/v1/auth/register`) to prevent brute-force attacks.
- [ ] **Password policy enforcement** — Minimum 8 chars is set in the frontend Zod schema but not enforced server-side in the `UserCreate` Pydantic model. Add `min_length=8` validation to `backend/models/user.py`.
- [ ] **Internal broadcast endpoint protection** — `POST /internal/broadcast-alert` has no authentication. Add a shared secret header check or bind it to `127.0.0.1` only via Nginx so it is never reachable from outside the Docker network.
- [ ] **Remove `DEBUG=False` default** — Confirm `DEBUG=False` and `APP_ENV=production` are set in the production `.env`. The `create_all_tables()` dev shortcut must not run in production.

### Important

- [ ] **Session invalidation on deactivate** — When a user is deactivated via `POST /settings/users/{id}/deactivate/`, any existing JWT tokens for that user remain valid until expiry. Add a token blocklist (Redis set) checked in `get_current_user`.
- [ ] **Audit log** — No audit trail exists for sensitive operations (user creation, job status changes, certificate issuance). Add an `audit_logs` table and middleware that records `user_id`, `action`, `resource_type`, `resource_id`, `timestamp`, `ip_address`.
- [ ] **File upload validation** — `POST /jobs/{id}/documents` validates MIME type from the `Content-Type` header, which is client-supplied and spoofable. Add server-side magic-byte validation using `python-magic`.

---

## 2. Database & Migrations

- [ ] **Regenerate the initial Alembic migration** — `6038e5e1e9dd_initial_schema.py` is a no-op (`pass` in both `upgrade` and `downgrade`). Run `alembic revision --autogenerate -m "initial_schema"` against a live database to produce the real DDL. This is required before any production deployment.
- [ ] **TimescaleDB hypertable creation** — The `weighbridge_records` table needs `SELECT create_hypertable('weighbridge_records', 'recorded_at')` called after table creation. Add this to the Alembic migration or a post-migration script.
- [ ] **Recurring job templates persistence** — `_RECURRING_TEMPLATES` in `backend/routers/jobs.py` is an in-memory dict. It is wiped on every restart. Create a `recurring_job_templates` DB table and migrate the CRUD endpoints to use it.
- [ ] **Report task store persistence** — `_TASK_STORE` in `backend/routers/reports.py` is also in-memory. Migrate to a `report_tasks` DB table or use Celery's Redis result backend exclusively.
- [ ] **Database connection pooling** — Set explicit pool sizes in `database.py` (`pool_size`, `max_overflow`, `pool_pre_ping=True`) appropriate for production load. The current defaults may exhaust connections under concurrent traffic.
- [ ] **Backup strategy** — No backup configuration exists. Set up automated `pg_dump` to object storage (MinIO or S3) on a daily schedule via Celery Beat or a cron job.
- [ ] **Index review** — Verify that all foreign keys and frequently filtered columns (`job.status`, `job.client_id`, `job.scheduled_date`, `weighbridge_records.recorded_at`, `scheduled_waste_batches.storage_deadline`) have database indexes. Add missing indexes in a migration.

---

## 3. PDF Generation & Templates

- [ ] **Create actual Jinja2 HTML templates** — `backend/templates/` and `backend/templates/certificates/` directories are empty. The certificate service (`certificate_service.py`) has inline HTML strings. Extract these into proper `.html` Jinja2 template files so they can be styled and maintained independently.
- [ ] **Report templates are placeholder-only** — `report_tasks.py` generates minimal key-value table PDFs. Each of the 6 report types (`esg_monthly`, `tonnage_summary`, `compliance_audit`, `fleet_utilisation`, `recyclables_recovery`, `invoice_ageing`) needs a proper data-rich template with charts, branding, and all relevant data queried from the DB.
- [ ] **ESG report data completeness** — The ESG monthly report only queries `recyclable_records`. It needs to pull carbon calculations, SDG metrics, diversion rates, and scope 3 data from the relevant tables.
- [ ] **Consignment note PDF** — `complianceApi.generateConsignmentNotePDF` is called from the frontend but the backend endpoint needs to be verified as fully implemented with the correct e-SWIS format fields.
- [ ] **Company branding assets** — Replace placeholder ROC number (`123456-X`) and DOE license (`SW-2024-001`) in certificate templates with real values. Add the company logo to PDF headers.
- [ ] **PDF storage cleanup** — Generated PDFs accumulate in `generated_reports/` indefinitely. Add a Celery Beat task to purge files older than a configurable retention period (e.g. 90 days).

---

## 4. Celery & Background Tasks

- [ ] **Celery Beat scheduled tasks** — `backend/services/scheduler.py` exists but its tasks need to be verified as registered in `celery_app.py` beat schedule. Confirm the following run on schedule:
  - 90-day scheduled waste deadline alerts (daily)
  - Contract expiry alerts (daily)
  - Recurring job instance creation from templates (daily)
- [ ] **Celery result backend** — Configure `CELERY_RESULT_BACKEND` to use Redis (`redis://redis:6379/1`) so `AsyncResult` polling in the reports router works reliably. Currently falls back to the in-memory store.
- [ ] **Celery task routing** — The `reports` queue is defined in task decorators but `docker-compose.yml` starts a single worker with no queue specification. Add `-Q default,reports,agents` to the worker command, or add a dedicated reports worker.
- [ ] **Dead letter queue** — Configure a dead-letter queue for failed tasks so they can be inspected and retried without being silently dropped.
- [ ] **RAG ingestion task** — `backend/tasks/rag_tasks.py` needs to be verified: confirm it ingests all 5 documents in `docs/` into Milvus on startup or via a one-time task, and that re-ingestion is idempotent.

---

## 5. AI / RAG System

- [ ] **Milvus collection initialisation** — The RAG pipeline must create the Milvus collection with the correct schema and index on first run. Add a startup check in the lifespan handler that creates the collection if it does not exist.
- [ ] **Ollama model availability check** — The health endpoint checks Ollama reachability but not whether the required models (`llama3.1:8b`, `nomic-embed-text`) are actually pulled. Add a model availability check and surface it in `/health`.
- [ ] **RAG document versioning** — When `docs/` files are updated, the Milvus collection needs to be re-ingested. Add a hash-based change detection mechanism so only changed documents are re-embedded.
- [ ] **Agent response streaming robustness** — The SSE parser fix from the `ai-assistant-streaming` spec is implemented, but error recovery (network drops mid-stream, Ollama timeout) needs to be tested end-to-end and the frontend should show a retry button on stream failure.
- [ ] **Context window management** — Long conversations will eventually exceed the LLM context window. Implement conversation summarisation or a sliding window strategy in `agents/orchestrator.py`.
- [ ] **Agent tool calls** — The current agents return text responses only. For production, agents should be able to query live DB data (e.g. "show me overdue jobs") via structured tool calls rather than relying solely on RAG retrieval.

---

## 6. Frontend — Incomplete Pages & Features

### Pages with stub/placeholder content

- [ ] **Dashboard KPI cards** — Verify all KPI values are fetched from real API endpoints, not hardcoded. Confirm `dashboardApi` methods exist in `api.ts` and the backend `/api/v1/dashboard/` endpoint is implemented.
- [ ] **Fleet map** — `FleetMap` component uses Leaflet. Confirm real-time GPS positions are being pushed via WebSocket from the MQTT gateway and the map updates live. Test with the GPS simulator profile.
- [ ] **Weighbridge page** — Confirm the TimescaleDB time-series chart is rendering real data and the tonnage trend query uses TimescaleDB `time_bucket` for efficient aggregation.
- [ ] **Client portal** — `frontend/src/components/client-portal/` exists. Confirm the client-role restricted views are fully wired and tested. Clients should only see their own jobs, invoices, and certificates.
- [ ] **Reports page** — The report generation UI needs a polling loop that calls `GET /reports/{task_id}/status` every 5 seconds until `status === 'success'`, then enables the download button.
- [ ] **Recycler deliveries page** — Confirm `recycler-deliveries` page and `recyclerDeliveriesApi` are fully wired end-to-end.
- [ ] **Disruptions page** — Confirm the disruptions CRUD is fully functional with the backend router.
- [ ] **Equipment page** — Confirm equipment CRUD and assignment to jobs is fully functional.

### Missing UI features

- [ ] **Pagination controls** — Most list pages fetch with `limit=50` but have no UI pagination or infinite scroll. Add pagination to Jobs, Clients, Fleet, Weighbridge, Finance, and Compliance pages.
- [ ] **Search and filter persistence** — Filter state is lost on page navigation. Persist filters to URL query params using `useSearchParams`.
- [ ] **Export to CSV** — Management users need CSV export on Jobs, Weighbridge, and Finance pages. Add a backend `GET /api/v1/{resource}/export.csv` endpoint and a frontend download button.
- [ ] **Bulk actions** — Jobs page needs bulk status update (e.g. confirm multiple jobs at once) for operations efficiency.
- [ ] **Mobile responsiveness** — The dark slate dashboard layout needs testing on mobile viewports. Sidebar should collapse to a drawer on small screens.
- [ ] **Loading skeletons** — Replace raw spinners with shadcn `Skeleton` components on all data-heavy pages for better perceived performance.
- [ ] **Empty states** — All list pages need proper empty state illustrations/messages when no data exists (new client with no jobs, etc.).

---

## 7. Notifications

- [ ] **SMTP credentials** — `SMTP_PASSWORD` is blank in `.env`. Configure a real SMTP provider (Gmail App Password, SendGrid, AWS SES) and test the `send_test_email` endpoint.
- [ ] **WhatsApp Business API** — `WHATSAPP_API_URL` and `WHATSAPP_API_TOKEN` are blank. Register a WhatsApp Business account, obtain API credentials, and configure them. Test with `send_whatsapp_job_status`.
- [ ] **Email templates** — Job status emails in `notification_service.py` use inline HTML strings. Extract to Jinja2 templates in `backend/templates/email/` for maintainability and branding consistency.
- [ ] **Notification preferences** — Users currently receive all notifications. Add a `notification_preferences` table and a settings UI so users can opt in/out of email and WhatsApp per event type.
- [ ] **In-app notification centre** — The `NotificationPanel` component exists in the layout. Confirm it is connected to the WebSocket `agent-alerts` room and persists notifications to a `notifications` DB table so they survive page refresh.

---

## 8. Infrastructure & DevOps

- [ ] **Production Docker Compose / Kubernetes** — The current `docker-compose.yml` is suitable for a single-server deployment but has no resource limits, no secrets management, and mounts the source code as a volume (dev mode). Create a `docker-compose.prod.yml` that:
  - Builds production images (no source volume mounts)
  - Sets `APP_ENV=production`
  - Adds `mem_limit` and `cpus` constraints
  - Uses Docker secrets or environment variable injection from a secrets manager
- [ ] **Nginx reverse proxy** — Add an Nginx service to `docker-compose.prod.yml` that:
  - Terminates TLS (Let's Encrypt via Certbot or pre-provisioned cert)
  - Proxies `/api/` and `/ws/` to the backend
  - Serves the Next.js frontend (or proxies to it)
  - Adds security headers (`X-Frame-Options`, `X-Content-Type-Options`, `Strict-Transport-Security`, `Content-Security-Policy`)
- [ ] **Ollama production deployment** — Ollama runs on the host machine in the current setup. For production, either containerise it with GPU passthrough or use a managed LLM API (OpenAI-compatible endpoint) and update `OLLAMA_BASE_URL`.
- [ ] **Log aggregation** — Container logs are written to stdout only. Set up a log aggregation stack (Loki + Grafana, or ship to CloudWatch/Datadog) so logs are searchable and retained.
- [ ] **Monitoring & alerting** — Add Prometheus metrics to the FastAPI app (`prometheus-fastapi-instrumentator`) and set up Grafana dashboards for request latency, error rates, Celery queue depth, and DB connection pool usage.
- [ ] **CI/CD pipeline** — No CI/CD exists. Set up GitHub Actions (or equivalent) with:
  - Lint (`ruff`, `eslint`)
  - Type check (`mypy`, `tsc --noEmit`)
  - Unit + property tests (`pytest`, `vitest --run`)
  - Docker image build and push to a registry
  - Automated deployment to staging on merge to `main`
- [ ] **Health check endpoints in load balancer** — Configure the load balancer or container orchestrator to use `GET /health` (not just `GET /`) as the readiness probe, so traffic is only routed to instances where DB, Redis, and Ollama are all reachable.

---

## 9. Data Integrity & Business Logic

- [ ] **Job number collision under concurrency** — `_generate_job_number` uses a COUNT query which is not atomic. Under concurrent job creation, two requests could generate the same number. Replace with a PostgreSQL sequence (`CREATE SEQUENCE job_number_seq`) and use `nextval()`.
- [ ] **Scheduled waste 90-day rule enforcement** — The compliance router needs to enforce that a consignment note cannot be created for a batch that has already exceeded 90 days in storage. Add a server-side check, not just a frontend warning.
- [ ] **Invoice → Job linkage** — When a job is marked `invoiced`, verify that an invoice record is actually created or linked. Currently the status transition does not enforce this.
- [ ] **Weighbridge record immutability** — Once a weighbridge record is submitted, it should be immutable (or require a correction workflow with audit trail) to maintain data integrity for compliance reporting.
- [ ] **BSF batch status transitions** — Validate that a batch can only be harvested once and that `completed`/`rejected` batches cannot be re-opened without a superadmin override.
- [ ] **Destruction certificate dual sign-off** — The certificate model has `witness_hitech_name` and `witness_client_name` fields but no digital signature or approval workflow. Add a two-step approval: Hi-Tech staff submits, client portal user approves, then the certificate PDF is generated.
- [ ] **Carbon calculation accuracy** — `backend/services/carbon_calculator.py` needs to be verified against the emission factors in `docs/carbon_emission_factors_my.txt` and the GHG Scope 3 methodology in `docs/ghg_scope3_methodology.txt`. Have a compliance officer review the formulas.

---

## 10. Testing

- [ ] **Backend integration tests** — No `backend/tests/` directory exists. Create a pytest suite with:
  - Auth flow (login, token refresh, role-based access)
  - Job lifecycle (create → confirm → dispatch → complete → invoice)
  - Compliance 90-day rule enforcement
  - Weighbridge record creation and TimescaleDB query
  - PDF generation (smoke test that a non-empty PDF is produced)
- [ ] **Frontend E2E tests** — No Playwright or Cypress tests exist. Add E2E tests for:
  - Login and role-based redirect
  - Create a job and advance through the status pipeline
  - Generate and download a PDF certificate
  - AI assistant sends a message and receives a streaming response
- [ ] **Property-based tests (optional specs)** — Several spec tasks are marked optional (`*`). Complete the property tests for:
  - `bsf/schemas.ts` (Properties 1–5)
  - `labour/schemas.ts` (Properties 1–8)
  - `settings/UserFormDialog` (Properties 1–6, backend Properties 7–10)
  - `DownloadPdfButton` (Properties 1–3)
- [ ] **Load testing** — Run `locust` or `k6` against the API to identify bottlenecks before go-live. Focus on the weighbridge time-series query, report generation queue, and WebSocket connection limits.

---

## 11. Compliance & Regulatory

- [ ] **e-SWIS integration** — The consignment note format must match the DOE e-SWIS submission format exactly. Verify the fields in `compliance` router against the e-SWIS guide in `docs/eswis_guide.txt` and add any missing fields.
- [ ] **SW code validation** — Validate that SW codes entered by users exist in Malaysia's First Schedule. Cross-reference against `docs/sw_codes_malaysia.txt` server-side, not just in the frontend dropdown.
- [ ] **EQA Act 127 deadline enforcement** — The 90-day storage rule must trigger automated alerts at 60, 75, and 89 days. Verify the Celery Beat scheduler is configured for all three thresholds.
- [ ] **Bilingual PDF support** — Reports and certificates must be available in both English and Bahasa Malaysia per the product spec. Add a `language` parameter to PDF generation endpoints and create BM Jinja2 template variants.
- [ ] **Data retention policy** — Define and implement a data retention policy (e.g. compliance records kept for 7 years per EQA requirements). Add soft-delete with `deleted_at` timestamps to all relevant models.

---

## 12. Pre-Launch Checklist

- [ ] All `.env` secrets rotated and stored securely
- [ ] Alembic migration regenerated and tested against a clean DB
- [ ] TimescaleDB hypertable created for `weighbridge_records`
- [ ] All 5 RAG documents ingested into Milvus
- [ ] Ollama models pulled (`llama3.1:8b`, `nomic-embed-text`)
- [ ] SMTP and WhatsApp credentials configured and tested
- [ ] CORS locked to production domain
- [ ] HTTPS configured with valid TLS certificate
- [ ] Nginx security headers in place
- [ ] `GET /health` returns 200 for all services
- [ ] Celery workers and Beat scheduler running and processing tasks
- [ ] At least one superadmin user seeded in the database
- [ ] PDF generation tested for all 6 report types and 2 certificate types
- [ ] Client portal tested with a client-role user
- [ ] GPS simulator tested with real vehicle data
- [ ] Backup and restore procedure documented and tested
- [ ] Monitoring dashboards live and alerting configured
