# Hi-Tech Waste Management — AI-Integrated Operations Platform
## PLAN.md — Master Development Reference
**Version:** 1.0.0
**Client:** Hi-Tech Waste Management Sdn Bhd
**HQ:** Shah Alam, Selangor, Malaysia
**Founded:** 1992
**Last Updated:** 2026-04-16

---

## Table of Contents

1. [Project Vision](#1-project-vision)
2. [Tech Stack](#2-tech-stack)
3. [System Architecture](#3-system-architecture)
4. [User Roles & Permissions](#4-user-roles--permissions)
5. [File & Folder Structure](#5-file--folder-structure)
6. [Core Modules](#6-core-modules)
7. [AI Agents](#7-ai-agents)
8. [Database Schema](#8-database-schema)
9. [API Route Map](#9-api-route-map)
10. [WebSocket Event Catalogue](#10-websocket-event-catalogue)
11. [RAG Knowledge Base](#11-rag-knowledge-base)
12. [Dashboard Pages](#12-dashboard-pages)
13. [Development Tracks](#13-development-tracks)
14. [Environment Variables](#14-environment-variables)
15. [Running the Project](#15-running-the-project)

---

## 1. Project Vision

A full-stack, AI-powered operations platform for Hi-Tech Waste Management Sdn Bhd — Malaysia's ICI-focused solid waste solutions company operating since 1992. The system replaces fragmented spreadsheets, WhatsApp coordination, and manual compliance paperwork with a unified intelligence layer that manages:

- **Job lifecycle** — from client collection order to final disposal destination
- **Fleet operations** — real-time GPS, driver assignment, maintenance scheduling
- **Regulatory compliance** — DOE scheduled waste (Act 127), e-SWIS consignment notes, 90-day storage rule
- **Recyclables traceability** — full chain-of-custody from client premises to downstream buyer
- **Witnessed destruction** — legally defensible certificates for brand-protection clients
- **ESG & carbon reporting** — client-facing diversion rates, GHG Scope 3 data, SDG alignment
- **BSF farm circularity** — food waste intake → larvae conversion → protein output tracking
- **RAG AI assistant** — natural language queries across all operational data and regulatory documents

The platform positions Hi-Tech not just as a waste collector but as a strategic sustainability partner to its multinational and institutional clients.

---

## 2. Tech Stack

| Layer              | Technology                                      | Purpose                                          |
|--------------------|-------------------------------------------------|--------------------------------------------------|
| Frontend           | Next.js 14 (App Router), TypeScript             | Main dashboard UI                                |
| UI Components      | shadcn/ui, Tailwind CSS, Recharts               | Design system, charts                            |
| Backend            | FastAPI (Python 3.11)                           | REST API, agent orchestration                    |
| Primary Database   | PostgreSQL 15                                   | Core relational data                             |
| Time-Series DB     | TimescaleDB (PostgreSQL extension)              | Tonnage history, sensor/GPS streams              |
| Vector Store       | Milvus                                          | RAG document embeddings                          |
| Cache & Pub/Sub    | Redis 7                                         | Session cache, WebSocket broker, job queue       |
| Local LLM          | Ollama (llama3 / mistral)                       | AI agent reasoning, RAG responses                |
| IoT / Telematics   | MQTT via Mosquitto + aiomqtt                    | Live GPS vehicle feeds                           |
| Job Queue          | Celery + Redis                                  | Async tasks (PDF gen, agent runs, email)         |
| PDF Generation     | WeasyPrint / ReportLab                          | Certificates, ESG reports, consignment notes     |
| Authentication     | NextAuth.js + JWT                               | Role-based access control                        |
| Containerisation   | Docker Compose                                  | Full local + production environment              |
| Embeddings Model   | nomic-embed-text (via Ollama)                   | Document ingestion for RAG                       |

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Next.js Frontend                             │
│   Dashboard │ Job Board │ Fleet Map │ Compliance │ ESG │ AI Chat    │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ REST + WebSocket
┌──────────────────────────▼──────────────────────────────────────────┐
│                        FastAPI Backend                              │
│                                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────────────┐  │
│  │ REST Routes │  │  WebSocket   │  │     Agent Orchestrator    │  │
│  │  /api/v1/*  │  │   Manager   │  │  (5 AI Agents + RAG)      │  │
│  └─────────────┘  └──────────────┘  └───────────────────────────┘  │
│                                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────────────┐  │
│  │   Celery    │  │ MQTT Gateway │  │     PDF Generator         │  │
│  │ Task Queue  │  │ (aiomqtt)    │  │  (WeasyPrint/ReportLab)   │  │
│  └─────────────┘  └──────────────┘  └───────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
         │              │              │              │
   ┌─────▼──────┐ ┌─────▼──────┐ ┌────▼──────┐ ┌────▼───────┐
   │ PostgreSQL │ │   Redis    │ │  Milvus   │ │   Ollama   │
   │+TimescaleDB│ │            │ │(Vector DB)│ │ (Local LLM)│
   └────────────┘ └────────────┘ └───────────┘ └────────────┘
         │
   ┌─────▼──────┐
   │ Mosquitto  │
   │(MQTT Broker│
   │ - GPS Feed)│
   └────────────┘
```

---

## 4. User Roles & Permissions

| Role                  | Description                                                                 |
|-----------------------|-----------------------------------------------------------------------------|
| `superadmin`          | Full system access, user management, all config                             |
| `management`          | All dashboards, all reports, AI agents, ESG analytics, finance overview     |
| `operations_manager`  | Job management, fleet, scheduling, client management, compliance            |
| `field_supervisor`    | Job status updates, driver assignment, weighbridge entry, photo uploads     |
| `driver`              | Mobile-optimised job view, check-ins, trip logs (read-own-only)             |
| `compliance_officer`  | Scheduled waste module, consignment notes, e-SWIS logs, DOE documents      |
| `client`              | Read-only portal — own jobs, weights, certificates, ESG reports             |

---

## 5. File & Folder Structure

```
hitech-waste-platform/
│
├── PLAN.md                          ← This file
├── docker-compose.yml
├── .env.example
│
├── frontend/                        ← Next.js 14 App
│   ├── package.json
│   ├── tailwind.config.ts
│   ├── next.config.ts
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx
│   │   │   ├── (auth)/
│   │   │   │   ├── login/page.tsx
│   │   │   │   └── layout.tsx
│   │   │   └── (dashboard)/
│   │   │       ├── layout.tsx
│   │   │       ├── dashboard/page.tsx
│   │   │       ├── clients/
│   │   │       │   ├── page.tsx
│   │   │       │   └── [id]/page.tsx
│   │   │       ├── jobs/
│   │   │       │   ├── page.tsx
│   │   │       │   └── [id]/page.tsx
│   │   │       ├── fleet/
│   │   │       │   ├── page.tsx
│   │   │       │   └── [id]/page.tsx
│   │   │       ├── weighbridge/page.tsx
│   │   │       ├── compliance/
│   │   │       │   ├── page.tsx
│   │   │       │   └── scheduled-waste/page.tsx
│   │   │       ├── recyclables/page.tsx
│   │   │       ├── destruction/page.tsx
│   │   │       ├── bsf-farm/page.tsx
│   │   │       ├── esg/page.tsx
│   │   │       ├── finance/page.tsx
│   │   │       ├── ai-assistant/page.tsx
│   │   │       ├── reports/page.tsx
│   │   │       └── settings/page.tsx
│   │   ├── components/
│   │   │   ├── ui/                  ← shadcn/ui primitives
│   │   │   ├── layout/
│   │   │   │   ├── Sidebar.tsx
│   │   │   │   ├── TopBar.tsx
│   │   │   │   └── NotificationPanel.tsx
│   │   │   ├── dashboard/
│   │   │   │   ├── KpiCards.tsx
│   │   │   │   ├── TonnageChart.tsx
│   │   │   │   ├── JobStatusSummary.tsx
│   │   │   │   ├── FleetStatusWidget.tsx
│   │   │   │   └── ComplianceAlerts.tsx
│   │   │   ├── jobs/
│   │   │   │   ├── JobKanban.tsx
│   │   │   │   ├── JobTable.tsx
│   │   │   │   ├── JobForm.tsx
│   │   │   │   └── JobDetailPanel.tsx
│   │   │   ├── fleet/
│   │   │   │   ├── FleetMap.tsx
│   │   │   │   ├── VehicleCard.tsx
│   │   │   │   └── MaintenanceCalendar.tsx
│   │   │   ├── compliance/
│   │   │   │   ├── SwBatchTable.tsx
│   │   │   │   ├── ConsignmentNoteForm.tsx
│   │   │   │   └── DeadlineCalendar.tsx
│   │   │   ├── esg/
│   │   │   │   ├── CarbonDashboard.tsx
│   │   │   │   ├── DiversionGauge.tsx
│   │   │   │   └── SdgAlignmentBadges.tsx
│   │   │   ├── ai/
│   │   │   │   ├── AIAssistantChat.tsx
│   │   │   │   ├── AgentStatusPanel.tsx
│   │   │   │   └── AgentAlertFeed.tsx
│   │   │   └── shared/
│   │   │       ├── DataTable.tsx
│   │   │       ├── StatusBadge.tsx
│   │   │       ├── FileUploader.tsx
│   │   │       └── ConfirmDialog.tsx
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts
│   │   │   ├── useJobs.ts
│   │   │   ├── useFleet.ts
│   │   │   └── useAgentAlerts.ts
│   │   ├── lib/
│   │   │   ├── api.ts
│   │   │   ├── auth.ts
│   │   │   └── utils.ts
│   │   └── types/
│   │       ├── job.ts
│   │       ├── client.ts
│   │       ├── vehicle.ts
│   │       ├── compliance.ts
│   │       └── esg.ts
│
├── backend/                         ← FastAPI App
│   ├── requirements.txt
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── job.py
│   │   ├── vehicle.py
│   │   ├── weighbridge.py
│   │   ├── scheduled_waste.py
│   │   ├── recyclable.py
│   │   ├── destruction.py
│   │   ├── bsf.py
│   │   ├── esg.py
│   │   ├── invoice.py
│   │   └── document.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── clients.py
│   │   ├── jobs.py
│   │   ├── fleet.py
│   │   ├── weighbridge.py
│   │   ├── compliance.py
│   │   ├── recyclables.py
│   │   ├── destruction.py
│   │   ├── bsf.py
│   │   ├── esg.py
│   │   ├── finance.py
│   │   ├── reports.py
│   │   ├── ai.py
│   │   └── websocket.py
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── orchestrator.py
│   │   ├── compliance_agent.py
│   │   ├── esg_agent.py
│   │   ├── operations_agent.py
│   │   ├── client_intelligence_agent.py
│   │   └── fleet_agent.py
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── pipeline.py
│   │   ├── ingestion.py
│   │   ├── retriever.py
│   │   └── prompts.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── pdf_generator.py
│   │   ├── certificate_service.py
│   │   ├── carbon_calculator.py
│   │   ├── eswis_formatter.py
│   │   ├── notification_service.py
│   │   └── scheduler.py
│   ├── mqtt/
│   │   ├── __init__.py
│   │   └── gateway.py
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── celery_app.py
│   │   ├── report_tasks.py
│   │   └── agent_tasks.py
│   └── websocket/
│       ├── __init__.py
│       └── manager.py
│
├── mosquitto/
│   └── mosquitto.conf
│
├── scripts/
│   ├── seed_db.py
│   ├── ingest_docs.py
│   └── create_tables.sql
│
└── docs/
    ├── sw_codes_malaysia.pdf        ← DOE First Schedule
    ├── eqa_act_127.pdf
    ├── eswis_guide.pdf
    ├── ghg_scope3_methodology.pdf
    └── carbon_emission_factors_my.pdf
```

---

## 6. Core Modules

### Module 1 — Client Management
- Client profiles: company name, industry vertical, registered address, PIC contacts, client portal credentials
- Per-client waste stream profile: waste types, estimated volumes, collection frequency
- Contract terms, SLA definitions, and renewal dates
- Client portal (read-only): own jobs, weigh records, certificates, ESG snapshots
- Client-level ESG dashboard: diversion rate, CO₂ abated, recycling % over time

### Module 2 — Job & Collection Order Management
- **Job Types:** `general_collection` | `scheduled_waste` | `witnessed_destruction` | `food_waste_bsf` | `equipment_rental` | `consultancy`
- **Status Pipeline:** `draft → confirmed → dispatched → in_progress → completed → invoiced`
- Recurring job templates with auto-generation (daily / weekly / monthly / ad-hoc)
- Mandatory document checklist per job type (e.g. consignment note required for scheduled waste)
- Photo attachment per job (collection point, loaded vehicle, disposal receipt)
- Full audit trail — who changed what and when

### Module 3 — Fleet & Route Management
- Vehicle registry: registration, type, capacity, assigned driver, GPS device ID
- Daily route planning — cluster jobs by zone and assign to available vehicles
- Real-time GPS map (MQTT → WebSocket → frontend Leaflet/Mapbox map)
- Fuel log entry per trip; consumption trend charts per vehicle
- Preventive maintenance scheduler: alert at mileage threshold or time interval
- Breakdown reporting and downtime logging

### Module 4 — Weighbridge & Tonnage Tracking
- Weighbridge form: client, job ref, date/time, gross weight, tare weight → auto net weight
- Waste type split per weigh-in (recyclables, general, scheduled, food)
- TimescaleDB hypertable for all weight records (fast time-range queries)
- Diversion rate = (recyclable + diverted weight) / total weight × 100
- Tonnage trend charts: daily/weekly/monthly/annual, filterable by client or waste type
- Discrepancy alerts when net weight deviates >20% from client estimate

### Module 5 — Scheduled Waste Compliance
- Full SW code library (First Schedule, EQA Act 127) — searchable, with descriptions
- Batch tracking: SW code, quantity, physical state, packaging type, storage start date
- **90-day storage rule enforcement:** red alert at day 80, critical at day 88
- e-SWIS consignment note builder: pre-filled from batch data, PDF export
- Cenviro coordination: pickup request log, transport confirmation, processing receipt
- Audit trail for every scheduled waste movement — legally defensible

### Module 6 — Recyclables Recovery & Traceability
- Material breakdown per collection: paper, OCC cardboard, PET/HDPE plastic, aluminium, ferrous, glass, e-waste
- Weight recorded per material stream, per client, per job
- Downstream buyer registry and material-to-buyer allocation
- Chain-of-custody: collection → sorting facility → buyer → certificate
- Market price tracking per material type (MYR/kg) for revenue estimation
- Client recycling certificate auto-generation (PDF) with material breakdown and weights

### Module 7 — Witnessed & Secured Destruction
- Destruction job workflow with mandatory photo/video upload at each stage
- Dual digital sign-off: Hi-Tech supervisor + client representative
- **Certificate of Destruction** auto-generated (PDF): date, location, goods description, quantity/weight, destruction method, signatories, company stamp
- Report formats for: Customs tax exemption, insurance/supplier claims, brand protection audit
- Immutable audit log — once signed, records cannot be altered

### Module 8 — Food Waste & BSF Farm Management
- Client food waste jobs linked directly to farm intake log
- Farm intake: date received, weight, client source, contamination assessment, accept/reject
- Batch tracking: larvae growth stages, feed consumption, mortality rate
- Larvae-to-livestock conversion records: output weight, livestock recipient
- Circularity report per client: kg food waste in → kg protein out
- Farm capacity dashboard: current load vs maximum capacity

### Module 9 — Carbon Footprint & ESG Reporting
- Per-job carbon model:
  - Transport emissions: fuel consumed × distance × Malaysia transport emission factor
  - Landfill avoidance credit: tonnes diverted × landfill methane emission factor
  - Recycling credit: per-material GHG savings (WRAP/GHG Protocol basis)
  - Waste-to-energy credit: calorific value × avoided grid emission factor
- Per-client ESG dashboard: Scope 3 Category 5 (waste generated in operations)
- SDG tagging: SDG 12 (Responsible Consumption), SDG 13 (Climate Action), SDG 15 (Life on Land)
- Monthly/quarterly ESG PDF report — branded, bilingual (EN/BM), client-ready
- Company-wide aggregated carbon performance vs prior year

### Module 10 — Invoicing & Finance Overview
- Invoice generation per completed job: tonnage-based, trip-based, or lump sum
- Payment status tracking: `unpaid → partial → paid → overdue`
- Revenue breakdown: by service type, by client, by month
- Fuel cost vs revenue margin per route (profitability by vehicle)
- Outstanding receivables ageing report

### Module 11 — Compaction Equipment Tracking
- Registry of hydraulic compaction machines (asset tag, model, serial, status)
- Status pipeline: `available → deployed → maintenance → decommissioned`
- Deployment records: which machine is at which client site, duration, authorised by
- Utilisation rate calculation: deployed days / calendar days in period
- Maintenance scheduling: configurable interval (default 90 days), 14-day warning alerts
- Auto-escalation to `critical` + status → `maintenance` when service date passes
- Maintenance log: service date, type, technician, cost in MYR
- Celery task: daily check at 07:30 MST

### Module 12 — Container Logistics
- Container inventory: skip bins, roll-on/roll-off, compaction chambers
- Status pipeline: `available → at_site → in_transit → at_recycler → available`
- Site assignment: links container to client site + compaction machine + material type
- Fill-level tracking: timestamped readings with optional photo, full history retained
- Automatic pickup trigger at configurable threshold (default 85%)
- Pickup trigger acknowledgement creates a `general_collection` job automatically
- Transport log: every status transition recorded with timestamp and responsible user
- Recycler delivery workflow: manifest → depart → arrive → proof of delivery → reconciliation → buyer confirmation
- Weight reconciliation: auto-flags >5% variance between declared and recycler-recorded weight
- Buyer confirmation closes chain-of-custody and updates `recyclable_records`

### Module 13 — Labour Deployment Management
- Staff profile registry linked to `users` table
- Employment types: `permanent`, `contract`, `foreign_worker`
- Foreign worker work permit expiry tracking with 30-day alert (Celery daily task)
- Assignment status: `available → on_site → on_leave → inactive`
- Site assignments: team of staff linked to client site with date range and supervisor
- Conflict detection: rejects overlapping assignments for the same staff member
- Shift scheduling: morning / afternoon / night shifts with start/end times
- Check-in / check-out recording per shift per staff member
- Absence tracking: sick_leave, annual_leave, no_show, emergency
- Attendance rate calculation per staff member
- Site absence rate alert when >20% of scheduled staff absent on a given day
- Replaces WhatsApp-based coordination for ~50 field staff

### Module 14 — Operational Disruption Log
- Structured logging for: `landfill_delay`, `highway_restriction`, `vehicle_breakdown`, `site_access_denied`, `other`
- Vehicle breakdown auto-sets vehicle status to `maintenance` in Fleet module
- Highway restriction requires highway name and time window
- Job impact tracking: estimated delay in minutes, original vs revised completion time
- Resolution workflow: assign resolver → resolution updates → formal closure with note
- Vehicle breakdown closure requires confirmation that vehicle status was updated
- Auto-escalation: disruptions open >4 hours → severity `critical` + management notification
- Celery task: every 30 minutes escalation check
- Operational dashboard shows elapsed time, affected job count, resolver name

---

## 7. AI Agents

### Agent 1 — Compliance Agent
**Trigger:** Scheduled (every 6h) + event-driven (new SW batch created)
**Data Sources:** `scheduled_waste_batches`, `consignment_notes`, SW code library (RAG), DOE regulations (RAG)
**Responsibilities:**
- Monitor 90-day storage deadlines; alert at day 80 and day 88
- Flag jobs missing required compliance documents before closure
- Answer staff queries: SW codes, packaging requirements, storage rules
- Draft pre-filled e-SWIS consignment notes from batch data
- Detect missing Cenviro coordination records

**Example Prompts It Handles:**
> "What's the SW code for spent hydraulic oil?"
> "Which scheduled waste batches are expiring this week?"
> "Is this batch correctly labelled for SW305?"

---

### Agent 2 — ESG & Carbon Agent
**Trigger:** Scheduled (weekly) + on-demand
**Data Sources:** `carbon_records`, `weighbridge_records`, `recyclable_records`, GHG methodology docs (RAG)
**Responsibilities:**
- Calculate and update per-client diversion rates after each job closes
- Alert management when a client's diversion rate drops below agreed target
- Draft ESG narrative summaries in English and Bahasa Malaysia
- Generate SDG alignment talking points for client presentations
- Benchmark client performance vs industry averages

**Example Prompts It Handles:**
> "How much CO₂ did Unilever Malaysia avoid this quarter?"
> "Write an ESG summary for Client X for their annual report."
> "Which clients are underperforming on diversion targets?"

---

### Agent 3 — Operations & Scheduling Agent
**Trigger:** Each morning at 06:00 + on-demand
**Data Sources:** `jobs`, `vehicles`, `trips`, driver roster
**Responsibilities:**
- Suggest optimal daily job-to-vehicle assignments (zone clustering, load capacity)
- Alert when a recurring job hasn't been auto-scheduled
- Detect scheduling conflicts (same driver, overlapping jobs)
- Flag underutilised vehicles or overloaded routes
- Recommend route resequencing to minimise fuel cost

**Example Prompts It Handles:**
> "Which drivers are free tomorrow afternoon in Shah Alam?"
> "Assign today's 8 jobs to the available fleet optimally."
> "There are 3 vehicles idle today — is there capacity to take on an urgent job?"

---

### Agent 4 — Client Intelligence Agent *(RAG-Primary)*
**Trigger:** On-demand via AI assistant chat
**Data Sources:** All client records, job history, tonnage data, contracts, correspondence (RAG)
**Responsibilities:**
- Answer natural language queries about any client
- Surface upsell/cross-sell opportunities from waste stream data
- Draft client-facing emails, status updates, and reports
- Flag clients with declining volumes (churn signal)
- Generate new-staff briefings on client history and preferences

**Example Prompts It Handles:**
> "What was ABC Manufacturing's average monthly waste volume in 2025?"
> "Which clients generate food waste but aren't enrolled in the BSF programme?"
> "Draft a service renewal email for Nestle Malaysia."

---

### Agent 5 — Fleet & Maintenance Agent
**Trigger:** Scheduled (daily) + MQTT event-driven (GPS anomaly)
**Data Sources:** `vehicles`, `trips`, `maintenance_logs`, fuel records, GPS stream
**Responsibilities:**
- Alert when a vehicle is due for service (mileage or time threshold)
- Flag unusual fuel consumption patterns
- Detect GPS route deviations from assigned job zones
- Identify vehicles with repeated breakdowns (retirement/replacement signal)
- Generate monthly fleet utilisation and cost reports

**Example Prompts It Handles:**
> "When is HWM-1234 due for its next service?"
> "Which vehicles used more than 20% above average fuel this week?"
> "Show me all breakdowns in the last 90 days."

---

## 8. Database Schema

### Core Tables

```sql
-- Clients
CREATE TABLE clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name VARCHAR(200) NOT NULL,
    industry_vertical VARCHAR(100),
    ssm_number VARCHAR(50),
    address TEXT,
    city VARCHAR(100),
    state VARCHAR(100),
    pic_name VARCHAR(150),
    pic_email VARCHAR(150),
    pic_phone VARCHAR(30),
    portal_user_id UUID REFERENCES users(id),
    contract_start DATE,
    contract_end DATE,
    sla_diversion_target DECIMAL(5,2),   -- % target
    billing_model VARCHAR(50),            -- 'tonnage' | 'trip' | 'lumpsum'
    notes TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Waste Streams per Client
CREATE TABLE client_waste_streams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID REFERENCES clients(id),
    waste_type VARCHAR(100),              -- 'general' | 'recyclable' | 'scheduled' | 'food' | 'clinical'
    estimated_kg_per_month DECIMAL(10,2),
    collection_frequency VARCHAR(50),
    special_handling_notes TEXT
);

-- Jobs
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_number VARCHAR(30) UNIQUE NOT NULL,
    client_id UUID REFERENCES clients(id),
    job_type VARCHAR(50) NOT NULL,        -- 'general_collection' | 'scheduled_waste' | 'witnessed_destruction' | 'food_waste_bsf' | 'equipment_rental' | 'consultancy'
    status VARCHAR(30) DEFAULT 'draft',   -- 'draft' | 'confirmed' | 'dispatched' | 'in_progress' | 'completed' | 'invoiced'
    scheduled_date DATE,
    scheduled_time_start TIME,
    collection_address TEXT,
    assigned_vehicle_id UUID REFERENCES vehicles(id),
    assigned_driver_id UUID REFERENCES users(id),
    assigned_supervisor_id UUID REFERENCES users(id),
    estimated_weight_kg DECIMAL(10,2),
    actual_weight_kg DECIMAL(10,2),
    disposal_route VARCHAR(100),          -- 'landfill' | 'recycler' | 'wte' | 'bsf_farm' | 'cenviro'
    notes TEXT,
    completed_at TIMESTAMPTZ,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Vehicles
CREATE TABLE vehicles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    registration VARCHAR(20) UNIQUE NOT NULL,
    vehicle_type VARCHAR(50),             -- 'compactor' | 'hook_loader' | 'open_lorry' | 'skip_truck' | 'van'
    make VARCHAR(100),
    model VARCHAR(100),
    year INT,
    capacity_kg DECIMAL(10,2),
    gps_device_id VARCHAR(100),
    assigned_driver_id UUID REFERENCES users(id),
    last_service_date DATE,
    next_service_date DATE,
    odometer_km DECIMAL(10,2),
    status VARCHAR(30) DEFAULT 'available', -- 'available' | 'on_trip' | 'maintenance' | 'retired'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Trips
CREATE TABLE trips (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES jobs(id),
    vehicle_id UUID REFERENCES vehicles(id),
    driver_id UUID REFERENCES users(id),
    start_odometer DECIMAL(10,2),
    end_odometer DECIMAL(10,2),
    distance_km DECIMAL(10,2),
    fuel_litres DECIMAL(10,2),
    departure_time TIMESTAMPTZ,
    arrival_time TIMESTAMPTZ,
    gps_track JSONB,                      -- Array of {lat, lng, timestamp}
    notes TEXT
);

-- Weighbridge Records (TimescaleDB hypertable)
CREATE TABLE weighbridge_records (
    id UUID DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES jobs(id),
    client_id UUID REFERENCES clients(id),
    recorded_at TIMESTAMPTZ NOT NULL,
    gross_weight_kg DECIMAL(10,2) NOT NULL,
    tare_weight_kg DECIMAL(10,2) NOT NULL,
    net_weight_kg DECIMAL(10,2) GENERATED ALWAYS AS (gross_weight_kg - tare_weight_kg) STORED,
    waste_type_breakdown JSONB,           -- {"recyclable": 120, "general": 80, "food": 40}
    operator_id UUID REFERENCES users(id),
    notes TEXT,
    PRIMARY KEY (id, recorded_at)
);
SELECT create_hypertable('weighbridge_records', 'recorded_at');

-- Scheduled Waste Batches
CREATE TABLE scheduled_waste_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES jobs(id),
    client_id UUID REFERENCES clients(id),
    sw_code VARCHAR(20) NOT NULL,         -- e.g. 'SW305', 'SW410'
    waste_description TEXT,
    quantity_kg DECIMAL(10,2),
    physical_state VARCHAR(30),           -- 'solid' | 'liquid' | 'sludge' | 'gas'
    container_type VARCHAR(50),
    container_count INT,
    storage_start_date DATE NOT NULL,
    storage_deadline DATE GENERATED ALWAYS AS (storage_start_date + INTERVAL '90 days') STORED,
    status VARCHAR(30) DEFAULT 'in_storage', -- 'in_storage' | 'dispatched' | 'processed'
    consignment_note_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Consignment Notes
CREATE TABLE consignment_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id UUID REFERENCES scheduled_waste_batches(id),
    note_number VARCHAR(50) UNIQUE,
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    cenviro_reference VARCHAR(100),
    transport_date DATE,
    transporter_name VARCHAR(150),
    vehicle_registration VARCHAR(20),
    processing_facility VARCHAR(150),
    status VARCHAR(30) DEFAULT 'draft',   -- 'draft' | 'submitted' | 'confirmed' | 'processed'
    pdf_path TEXT,
    signed_by_hitech UUID REFERENCES users(id),
    signed_by_client UUID REFERENCES users(id)
);

-- Recyclable Records
CREATE TABLE recyclable_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES jobs(id),
    client_id UUID REFERENCES clients(id),
    recorded_at TIMESTAMPTZ DEFAULT NOW(),
    material_breakdown JSONB NOT NULL,    -- {"paper_kg": 100, "pet_kg": 50, "aluminium_kg": 20, ...}
    total_recyclable_kg DECIMAL(10,2),
    buyer_id UUID REFERENCES downstream_buyers(id),
    sale_value_myr DECIMAL(10,2),
    certificate_id UUID
);

-- Downstream Buyers
CREATE TABLE downstream_buyers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name VARCHAR(200),
    material_types TEXT[],                -- ['paper', 'pet', 'aluminium']
    contact_name VARCHAR(150),
    contact_phone VARCHAR(30),
    address TEXT,
    license_number VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE
);

-- Destruction Jobs
CREATE TABLE destruction_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES jobs(id),
    goods_description TEXT NOT NULL,
    quantity_units INT,
    weight_kg DECIMAL(10,2),
    destruction_method VARCHAR(100),      -- 'shredding' | 'incineration' | 'landfill_compaction'
    destruction_date DATE,
    destruction_location TEXT,
    witness_hitech_id UUID REFERENCES users(id),
    witness_client_name VARCHAR(150),
    witness_client_designation VARCHAR(100),
    media_files JSONB,                    -- Array of {type, url, captured_at}
    certificate_issued BOOLEAN DEFAULT FALSE,
    certificate_id UUID,
    reason_codes TEXT[]                   -- ['tax_exemption', 'insurance', 'brand_protection']
);

-- BSF Farm Batches
CREATE TABLE bsf_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    intake_date DATE NOT NULL,
    source_job_ids UUID[],
    food_waste_kg DECIMAL(10,2),
    client_sources JSONB,                 -- {"client_id": kg, ...}
    contamination_level VARCHAR(20),      -- 'clean' | 'minor' | 'rejected'
    larvae_output_kg DECIMAL(10,2),
    conversion_ratio DECIMAL(5,3),
    livestock_recipient VARCHAR(200),
    batch_start DATE,
    batch_end DATE,
    status VARCHAR(30) DEFAULT 'active'
);

-- Carbon Records
CREATE TABLE carbon_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES jobs(id),
    client_id UUID REFERENCES clients(id),
    calculated_at TIMESTAMPTZ DEFAULT NOW(),
    transport_emissions_kgco2e DECIMAL(10,3),
    landfill_avoidance_kgco2e DECIMAL(10,3),
    recycling_credit_kgco2e DECIMAL(10,3),
    wte_credit_kgco2e DECIMAL(10,3),
    net_carbon_impact_kgco2e DECIMAL(10,3),
    methodology_notes TEXT
);

-- Certificates
CREATE TABLE certificates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cert_type VARCHAR(50) NOT NULL,       -- 'recycling' | 'destruction' | 'esg_report'
    reference_id UUID,                    -- job_id or report_id
    client_id UUID REFERENCES clients(id),
    issued_at TIMESTAMPTZ DEFAULT NOW(),
    issued_by UUID REFERENCES users(id),
    pdf_path TEXT,
    is_void BOOLEAN DEFAULT FALSE
);

-- Invoices
CREATE TABLE invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_number VARCHAR(30) UNIQUE,
    client_id UUID REFERENCES clients(id),
    job_ids UUID[],
    issue_date DATE,
    due_date DATE,
    line_items JSONB,
    subtotal_myr DECIMAL(12,2),
    tax_myr DECIMAL(12,2),
    total_myr DECIMAL(12,2),
    status VARCHAR(20) DEFAULT 'unpaid',  -- 'unpaid' | 'partial' | 'paid' | 'overdue'
    paid_amount_myr DECIMAL(12,2) DEFAULT 0,
    notes TEXT
);

-- Agent Events
CREATE TABLE agent_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name VARCHAR(50) NOT NULL,
    event_type VARCHAR(50),               -- 'alert' | 'action' | 'recommendation' | 'report'
    severity VARCHAR(20),                 -- 'info' | 'warning' | 'critical'
    title VARCHAR(200),
    body TEXT,
    reference_type VARCHAR(50),           -- 'job' | 'vehicle' | 'sw_batch' | 'client'
    reference_id UUID,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Documents (RAG Source Files)
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(300),
    doc_type VARCHAR(50),                 -- 'regulation' | 'contract' | 'sop' | 'report' | 'manual'
    client_id UUID REFERENCES clients(id), -- null for global docs
    file_path TEXT,
    mime_type VARCHAR(50),
    ingested_into_rag BOOLEAN DEFAULT FALSE,
    milvus_collection VARCHAR(100),
    uploaded_by UUID REFERENCES users(id),
    uploaded_at TIMESTAMPTZ DEFAULT NOW()
);

-- Operational Field Management Tables (Module 11-14)

-- Compaction Machines
CREATE TABLE compaction_machines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_tag VARCHAR(50) UNIQUE NOT NULL,
    model_name VARCHAR(150) NOT NULL,
    serial_number VARCHAR(100) UNIQUE NOT NULL,
    status VARCHAR(20) DEFAULT 'available',   -- available | deployed | maintenance | decommissioned
    purchase_date DATE,
    compaction_force_kn DECIMAL(8,2),
    maintenance_interval_days INT DEFAULT 90,
    last_service_date DATE,
    next_service_date DATE,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE compactor_deployments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    machine_id UUID REFERENCES compaction_machines(id),
    client_id UUID REFERENCES clients(id),
    site_address TEXT NOT NULL,
    deployment_start DATE NOT NULL,
    deployment_end DATE,
    authorised_by UUID REFERENCES users(id),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE compactor_maintenance_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    machine_id UUID REFERENCES compaction_machines(id),
    service_date DATE NOT NULL,
    service_type VARCHAR(100) NOT NULL,
    technician_name VARCHAR(200),
    cost_myr DECIMAL(10,2),
    logged_by UUID REFERENCES users(id),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Containers
CREATE TABLE containers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    container_code VARCHAR(50) UNIQUE NOT NULL,
    container_type VARCHAR(30) NOT NULL,      -- skip_bin | roll_on_roll_off | compaction_chamber
    capacity_m3 DECIMAL(8,2),
    status VARCHAR(20) DEFAULT 'available',   -- available | at_site | in_transit | at_recycler | decommissioned
    current_client_id UUID REFERENCES clients(id),
    current_site_address TEXT,
    current_compactor_id UUID REFERENCES compaction_machines(id),
    target_material_type VARCHAR(50),
    fill_level INT DEFAULT 0,
    pickup_threshold INT DEFAULT 85,
    assigned_date DATE,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE container_fill_readings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    container_id UUID REFERENCES containers(id),
    fill_level INT NOT NULL,
    recorded_at TIMESTAMPTZ DEFAULT NOW(),
    reported_by UUID REFERENCES users(id),
    photo_url TEXT,
    notes TEXT
);

CREATE TABLE pickup_triggers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    container_id UUID REFERENCES containers(id),
    triggered_at TIMESTAMPTZ DEFAULT NOW(),
    fill_level_at_trigger INT NOT NULL,
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by UUID REFERENCES users(id),
    linked_job_id UUID REFERENCES jobs(id),
    is_active BOOLEAN DEFAULT TRUE,
    closed_at TIMESTAMPTZ
);

CREATE TABLE container_transport_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    container_id UUID REFERENCES containers(id),
    from_status VARCHAR(20) NOT NULL,
    to_status VARCHAR(20) NOT NULL,
    transitioned_at TIMESTAMPTZ DEFAULT NOW(),
    responsible_user_id UUID REFERENCES users(id),
    vehicle_id UUID REFERENCES vehicles(id),
    notes TEXT
);

-- Recycler Deliveries
CREATE TABLE recycler_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    container_id UUID REFERENCES containers(id),
    buyer_id UUID REFERENCES downstream_buyers(id),
    vehicle_id UUID REFERENCES vehicles(id),
    driver_id UUID REFERENCES users(id),
    status VARCHAR(30) DEFAULT 'pending_departure',
    declared_material_breakdown JSONB,
    declared_total_weight_kg DECIMAL(10,3),
    planned_departure_at TIMESTAMPTZ,
    departed_at TIMESTAMPTZ,
    arrived_at TIMESTAMPTZ,
    proof_photos JSONB,
    weight_ticket_ref VARCHAR(100),
    recycler_recorded_weight_kg DECIMAL(10,3),
    proof_submitted_at TIMESTAMPTZ,
    weight_variance_kg DECIMAL(10,3),
    weight_variance_pct DECIMAL(6,3),
    reconciliation_status VARCHAR(30),
    reconciliation_justification TEXT,
    buyer_rep_name VARCHAR(200),
    buyer_confirmed_breakdown JSONB,
    buyer_reference_number VARCHAR(100),
    buyer_confirmed_at TIMESTAMPTZ,
    recyclable_record_id UUID REFERENCES recyclable_records(id),
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Labour Deployment
CREATE TABLE staff_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID UNIQUE REFERENCES users(id),
    employment_type VARCHAR(20) NOT NULL,     -- permanent | contract | foreign_worker
    labour_agent_name VARCHAR(200),
    id_number_encrypted TEXT,
    assignment_status VARCHAR(20) DEFAULT 'available',
    current_site_assignment_id UUID,
    work_permit_expiry DATE,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE staff_status_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    staff_profile_id UUID REFERENCES staff_profiles(id),
    previous_status VARCHAR(20) NOT NULL,
    new_status VARCHAR(20) NOT NULL,
    changed_at TIMESTAMPTZ DEFAULT NOW(),
    changed_by UUID REFERENCES users(id),
    notes TEXT
);

CREATE TABLE site_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID REFERENCES clients(id),
    site_address TEXT NOT NULL,
    supervisor_id UUID REFERENCES users(id),
    start_date DATE NOT NULL,
    end_date DATE,
    is_active BOOLEAN DEFAULT TRUE,
    notes TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE site_assignment_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assignment_id UUID REFERENCES site_assignments(id),
    staff_profile_id UUID REFERENCES staff_profiles(id),
    role_at_site VARCHAR(50) NOT NULL,
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    left_at TIMESTAMPTZ
);

CREATE TABLE shifts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_assignment_id UUID REFERENCES site_assignments(id),
    shift_date DATE NOT NULL,
    shift_type VARCHAR(20) NOT NULL,          -- morning | afternoon | night
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    created_by UUID REFERENCES users(id),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE shift_attendances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shift_id UUID REFERENCES shifts(id),
    staff_profile_id UUID REFERENCES staff_profiles(id),
    status VARCHAR(20) DEFAULT 'present',     -- present | absent | no_checkout | late
    check_in_at TIMESTAMPTZ,
    check_out_at TIMESTAMPTZ,
    absence_reason VARCHAR(30),
    recorded_by UUID REFERENCES users(id),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Disruption Logs
CREATE TABLE disruption_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    disruption_type VARCHAR(30) NOT NULL,     -- landfill_delay | highway_restriction | vehicle_breakdown | site_access_denied | other
    status VARCHAR(20) DEFAULT 'open',        -- open | resolved
    severity VARCHAR(20) DEFAULT 'warning',   -- info | warning | critical
    occurred_at TIMESTAMPTZ DEFAULT NOW(),
    reported_by UUID REFERENCES users(id),
    description TEXT NOT NULL,
    affected_job_ids TEXT[],
    vehicle_id UUID REFERENCES vehicles(id),
    highway_name VARCHAR(200),
    restriction_start_time TIME,
    restriction_end_time TIME,
    resolver_id UUID REFERENCES users(id),
    resolution_history JSONB DEFAULT '[]',
    closure_note TEXT,
    closed_at TIMESTAMPTZ,
    closed_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE disruption_job_impacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    disruption_id UUID REFERENCES disruption_logs(id),
    job_id UUID REFERENCES jobs(id),
    estimated_delay_minutes INT,
    original_scheduled_completion TIMESTAMPTZ,
    revised_estimated_completion TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 9. API Route Map

```
AUTH
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh
POST   /api/v1/auth/logout

CLIENTS
GET    /api/v1/clients
POST   /api/v1/clients
GET    /api/v1/clients/{id}
PUT    /api/v1/clients/{id}
GET    /api/v1/clients/{id}/jobs
GET    /api/v1/clients/{id}/esg-summary
GET    /api/v1/clients/{id}/certificates

JOBS
GET    /api/v1/jobs
POST   /api/v1/jobs
GET    /api/v1/jobs/{id}
PUT    /api/v1/jobs/{id}
PATCH  /api/v1/jobs/{id}/status
POST   /api/v1/jobs/{id}/documents
GET    /api/v1/jobs/recurring/templates
POST   /api/v1/jobs/recurring/templates

FLEET
GET    /api/v1/fleet/vehicles
POST   /api/v1/fleet/vehicles
GET    /api/v1/fleet/vehicles/{id}
PUT    /api/v1/fleet/vehicles/{id}
GET    /api/v1/fleet/vehicles/{id}/trips
POST   /api/v1/fleet/trips
GET    /api/v1/fleet/maintenance/due
POST   /api/v1/fleet/maintenance/logs

WEIGHBRIDGE
GET    /api/v1/weighbridge/records
POST   /api/v1/weighbridge/records
GET    /api/v1/weighbridge/stats/tonnage
GET    /api/v1/weighbridge/stats/diversion

COMPLIANCE
GET    /api/v1/compliance/sw-batches
POST   /api/v1/compliance/sw-batches
GET    /api/v1/compliance/sw-batches/{id}
PATCH  /api/v1/compliance/sw-batches/{id}/status
GET    /api/v1/compliance/deadlines
POST   /api/v1/compliance/consignment-notes
GET    /api/v1/compliance/consignment-notes/{id}/pdf
GET    /api/v1/compliance/sw-codes/search

RECYCLABLES
GET    /api/v1/recyclables/records
POST   /api/v1/recyclables/records
GET    /api/v1/recyclables/stats
GET    /api/v1/recyclables/buyers
POST   /api/v1/recyclables/buyers
POST   /api/v1/recyclables/{id}/certificate

DESTRUCTION
GET    /api/v1/destruction/jobs
POST   /api/v1/destruction/jobs
GET    /api/v1/destruction/jobs/{id}
POST   /api/v1/destruction/jobs/{id}/sign
POST   /api/v1/destruction/jobs/{id}/certificate

BSF FARM
GET    /api/v1/bsf/batches
POST   /api/v1/bsf/batches
GET    /api/v1/bsf/batches/{id}
PATCH  /api/v1/bsf/batches/{id}
GET    /api/v1/bsf/stats/circularity

ESG
GET    /api/v1/esg/carbon-records
GET    /api/v1/esg/client/{id}/dashboard
GET    /api/v1/esg/company/dashboard
POST   /api/v1/esg/reports/generate
GET    /api/v1/esg/reports/{id}/pdf

FINANCE
GET    /api/v1/finance/invoices
POST   /api/v1/finance/invoices
GET    /api/v1/finance/invoices/{id}
PATCH  /api/v1/finance/invoices/{id}/payment
GET    /api/v1/finance/stats/revenue

AI / AGENTS
POST   /api/v1/ai/chat
GET    /api/v1/ai/agent-events
PATCH  /api/v1/ai/agent-events/{id}/read
POST   /api/v1/ai/ingest-document
GET    /api/v1/ai/rag-status

REPORTS
POST   /api/v1/reports/generate
GET    /api/v1/reports/{id}/download

WEBSOCKET
WS     /ws/dashboard
WS     /ws/fleet
WS     /ws/agent-alerts

EQUIPMENT (Module 11-12)
GET    /api/v1/equipment/compactors
POST   /api/v1/equipment/compactors
GET    /api/v1/equipment/compactors/due-service
GET    /api/v1/equipment/compactors/{id}
PATCH  /api/v1/equipment/compactors/{id}
GET    /api/v1/equipment/compactors/{id}/deployments
POST   /api/v1/equipment/compactors/{id}/deployments
POST   /api/v1/equipment/compactors/{id}/deployments/{dep_id}/retrieve
GET    /api/v1/equipment/compactors/{id}/maintenance
POST   /api/v1/equipment/compactors/{id}/maintenance
GET    /api/v1/equipment/containers
POST   /api/v1/equipment/containers
GET    /api/v1/equipment/containers/{id}
POST   /api/v1/equipment/containers/{id}/assign-site
POST   /api/v1/equipment/containers/{id}/fill-level
GET    /api/v1/equipment/containers/{id}/fill-history
GET    /api/v1/equipment/containers/{id}/transport-log
POST   /api/v1/equipment/containers/{id}/transport
POST   /api/v1/equipment/containers/{id}/pickup-triggers/{tid}/acknowledge

LABOUR (Module 13)
GET    /api/v1/labour/staff
POST   /api/v1/labour/staff
GET    /api/v1/labour/staff/{id}
PATCH  /api/v1/labour/staff/{id}
GET    /api/v1/labour/staff/{id}/hours-summary
GET    /api/v1/labour/sites/{client_id}/assignments
POST   /api/v1/labour/sites/assignments
POST   /api/v1/labour/sites/assignments/{id}/close
GET    /api/v1/labour/shifts
POST   /api/v1/labour/shifts
POST   /api/v1/labour/shifts/{id}/check-in
POST   /api/v1/labour/shifts/{id}/check-out
POST   /api/v1/labour/shifts/{id}/mark-absent
GET    /api/v1/labour/attendance

DISRUPTIONS (Module 14)
GET    /api/v1/disruptions
POST   /api/v1/disruptions
GET    /api/v1/disruptions/{id}
PATCH  /api/v1/disruptions/{id}
POST   /api/v1/disruptions/{id}/resolution-update
POST   /api/v1/disruptions/{id}/close
GET    /api/v1/disruptions/{id}/impact

RECYCLER DELIVERIES (Module 12)
GET    /api/v1/recycler-deliveries
POST   /api/v1/recycler-deliveries
GET    /api/v1/recycler-deliveries/{id}
POST   /api/v1/recycler-deliveries/{id}/depart
POST   /api/v1/recycler-deliveries/{id}/arrive
POST   /api/v1/recycler-deliveries/{id}/proof
GET    /api/v1/recycler-deliveries/{id}/reconciliation
POST   /api/v1/recycler-deliveries/{id}/reconciliation-review
POST   /api/v1/recycler-deliveries/{id}/buyer-confirmation

OPERATIONAL FIELD SUMMARY
GET    /api/v1/operational-field/summary
GET    /api/v1/operational-field/jobs/{job_id}/disruptions
```

---

## 10. WebSocket Event Catalogue

| Event Name                      | Direction        | Payload Summary                                         |
|----------------------------------|------------------|---------------------------------------------------------|
| `job.status_changed`            | Server → Client  | `{job_id, old_status, new_status, job_number}`          |
| `job.created`                   | Server → Client  | `{job_id, job_number, client_name, scheduled_date}`     |
| `fleet.vehicle_location`        | Server → Client  | `{vehicle_id, registration, lat, lng, timestamp}`       |
| `fleet.vehicle_status_changed`  | Server → Client  | `{vehicle_id, old_status, new_status}`                  |
| `fleet.maintenance_due`         | Server → Client  | `{vehicle_id, registration, due_date, odometer_alert}`  |
| `compliance.sw_batch_alert`     | Server → Client  | `{batch_id, sw_code, days_remaining, severity}`         |
| `compliance.document_missing`   | Server → Client  | `{job_id, job_number, missing_docs[]}`                  |
| `weighbridge.record_created`    | Server → Client  | `{job_id, net_weight_kg, waste_type_breakdown}`         |
| `agent.alert`                   | Server → Client  | `{agent_name, severity, title, body, reference_id}`     |
| `agent.recommendation`          | Server → Client  | `{agent_name, title, body, action_url}`                 |
| `bsf.intake_received`           | Server → Client  | `{batch_id, food_waste_kg, client_count}`               |
| `certificate.issued`            | Server → Client  | `{cert_id, cert_type, client_name, pdf_url}`            |
| `client.connected`              | Client → Server  | `{user_id, role}`                                       |
| `ping`                          | Client → Server  | `{}`                                                    |
| `pong`                          | Server → Client  | `{timestamp}`                                           |

---

## 11. RAG Knowledge Base

### Document Collections in Milvus

| Collection Name          | Content                                                             |
|--------------------------|---------------------------------------------------------------------|
| `regulations`            | EQA Act 127, SW codes (First Schedule), DOE guidelines, OSHA       |
| `eswis_guides`           | e-SWIS user manual, consignment note format, Cenviro requirements   |
| `carbon_methodology`     | GHG Protocol Scope 3, WRAP emission factors, MY grid factor         |
| `client_contracts`       | Per-client contracts and SLA terms (scoped per client in query)     |
| `operational_records`    | Job history, weighbridge logs, tonnage reports (structured summary) |
| `company_sops`           | Hi-Tech internal procedures, service manuals, onboarding guides     |
| `esg_frameworks`         | TCFD, GRI, UN SDG alignment guides, ESG reporting best practices    |

### Ingestion Pipeline
1. PDF uploaded via `/api/v1/ai/ingest-document`
2. `pdfplumber` extracts text per page
3. Text chunked (512 tokens, 50-token overlap)
4. `nomic-embed-text` via Ollama generates embeddings
5. Vectors stored in Milvus with metadata: `{doc_id, collection, page, chunk_index}`
6. Document marked `ingested_into_rag = TRUE` in PostgreSQL

### RAG Query Flow
1. User message → `/api/v1/ai/chat`
2. Query embedded with `nomic-embed-text`
3. Top-k chunks retrieved from relevant Milvus collection
4. Retrieved chunks + conversation history injected into Ollama system prompt
5. LLM response streamed back to frontend via Server-Sent Events

---

## 12. Dashboard Pages

| Route                    | Page Name                    | Key Components                                              |
|--------------------------|------------------------------|-------------------------------------------------------------|
| `/dashboard`             | Operations Overview          | KPI cards, tonnage chart, job status ring, fleet map widget, compliance alerts |
| `/clients`               | Client Directory             | Client table with search/filter, waste stream tags          |
| `/clients/[id]`          | Client Profile               | Detail view, jobs history, ESG snapshot, certificates       |
| `/jobs`                  | Job Management               | Kanban board + table toggle, create job modal               |
| `/jobs/[id]`             | Job Detail                   | Full job timeline, documents, weighbridge link, signatures  |
| `/fleet`                 | Fleet Operations             | Live GPS map, vehicle list, maintenance calendar            |
| `/fleet/[id]`            | Vehicle Detail               | Trip history, fuel log, maintenance records, GPS replay     |
| `/weighbridge`           | Weighbridge Entry & History  | Entry form, tonnage charts, diversion rate gauge            |
| `/compliance`            | Compliance Overview          | SW batch tracker, deadline calendar, consignment note log   |
| `/compliance/scheduled-waste` | Scheduled Waste Manager | SW code search, batch table, 90-day countdown indicators  |
| `/recyclables`           | Recyclables Recovery         | Material breakdown charts, chain-of-custody table, buyer map |
| `/destruction`           | Witnessed Destruction        | Destruction job table, certificate vault                    |
| `/bsf-farm`              | BSF Farm Manager             | Intake log, active batches, circularity flow diagram        |
| `/esg`                   | ESG & Carbon Dashboard       | Carbon charts, diversion rates, SDG badges, report builder  |
| `/finance`               | Finance Overview             | Invoice table, revenue charts, receivables ageing           |
| `/ai-assistant`          | AI Assistant                 | Full-page chat UI, agent status panel, alert feed           |
| `/reports`               | Report Generator             | Report type selector, date/client filters, PDF export       |
| `/settings`              | System Settings              | Users, roles, vehicle registry, SW code library, material prices |

---

## 13. Development Tracks

### Track A — Foundation *(~2–3 days)*
- [ ] Docker Compose setup (PostgreSQL+TimescaleDB, Redis, Milvus, Ollama, Mosquitto)
- [ ] FastAPI project scaffold with folder structure
- [ ] All database tables created (`create_tables.sql`)
- [ ] TimescaleDB hypertable for `weighbridge_records`
- [ ] JWT authentication (login, refresh, role middleware)
- [ ] Next.js 14 scaffold with App Router, shadcn/ui, Tailwind
- [ ] Sidebar navigation with all routes
- [ ] TopBar with notifications bell
- [ ] RAG pipeline: ingestion, embedding, retriever (`rag/`)
- [ ] AI Assistant page (chat UI + SSE streaming from Ollama)
- [ ] Agent orchestrator shell (5 agent stubs)
- [ ] WebSocket manager with base events
- [ ] `PLAN.md` included in project root

### Track B — Core Operations *(~3–4 days)*
- [ ] Client management module (CRUD + portal user creation)
- [ ] Job management module (all types, full status pipeline, Kanban UI)
- [ ] Recurring job template system
- [ ] Weighbridge entry form + TimescaleDB queries + tonnage charts
- [ ] Recyclables module (material breakdown, buyer registry, chain-of-custody)
- [ ] Dashboard KPI cards and tonnage chart (live data)

### Track C — Compliance & Destruction *(~2–3 days)*
- [ ] SW code library (seeded from First Schedule)
- [ ] Scheduled waste batch tracker with 90-day countdown
- [ ] e-SWIS consignment note builder + PDF export
- [ ] Compliance Agent (full implementation)
- [ ] Witnessed destruction job workflow with media upload
- [ ] Certificate of Destruction PDF generator
- [ ] Recycling certificate PDF generator

### Track D — Fleet & Telematics *(~2–3 days)*
- [ ] Vehicle registry CRUD
- [ ] Trip logging (manual entry)
- [ ] MQTT gateway (aiomqtt) consuming GPS feed → Redis → WebSocket
- [ ] Fleet map page (Leaflet.js with live vehicle markers)
- [ ] Preventive maintenance scheduler + alert system
- [ ] Fleet Agent (full implementation)
- [ ] Operations & Scheduling Agent (full implementation)

### Track E — ESG, BSF & Client Portal *(~2–3 days)*
- [ ] Carbon calculator service (per-job emission model)
- [ ] Per-client ESG dashboard with Recharts visualisations
- [ ] SDG alignment tagging
- [ ] ESG PDF report generator (branded, bilingual EN/BM)
- [ ] ESG Agent (full implementation)
- [ ] BSF farm intake and batch tracking module
- [ ] Circularity reporting per client
- [ ] Client portal login (NextAuth + scoped data access)

### Track F — Intelligence, Finance & Polish *(~2–3 days)*
- [ ] Client Intelligence Agent (full RAG implementation)
- [ ] Finance module (invoice generation, payment tracking, revenue charts)
- [ ] Report generator page (PDF export, all report types)
- [ ] Full RAG document ingestion (regulatory docs, SOPs seeded)
- [ ] Agent alert feed on dashboard (real-time WebSocket)
- [ ] Full bug audit and resolution
- [ ] Mobile-optimised views for driver role
- [ ] Seed data script (`seed_db.py`) with realistic sample data
- [ ] Final version → **v1.0**

---

## 14. Environment Variables

```env
# Database
DATABASE_URL=postgresql://hitech:password@localhost:5432/hitech_waste
REDIS_URL=redis://localhost:6379

# Milvus
MILVUS_HOST=localhost
MILVUS_PORT=19530

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3
OLLAMA_EMBED_MODEL=nomic-embed-text

# MQTT
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883
MQTT_TOPIC_GPS=fleet/gps/#

# Auth
JWT_SECRET=your-secret-key-here
JWT_EXPIRE_MINUTES=60
NEXTAUTH_SECRET=your-nextauth-secret
NEXTAUTH_URL=http://localhost:3000

# App
BACKEND_URL=http://localhost:8000
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000

# PDF / Reports
REPORT_OUTPUT_DIR=/app/generated_reports
CERTIFICATE_TEMPLATE_DIR=/app/templates/certificates

# Notifications (optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=notifications@hitechwaste.com.my
SMTP_PASSWORD=
WHATSAPP_API_URL=
```

---

## 15. Running the Project

```bash
# 1. Clone the repository
git clone https://github.com/your-org/hitech-waste-platform.git
cd hitech-waste-platform

# 2. Copy environment file
cp .env.example .env
# Edit .env with your values

# 3. Start all infrastructure services
docker-compose up -d postgres redis milvus ollama mosquitto

# 4. Pull LLM models
ollama pull llama3
ollama pull nomic-embed-text

# 5. Create database tables
cd backend
pip install -r requirements.txt
python -c "from database import engine; from models import *; Base.metadata.create_all(engine)"
psql $DATABASE_URL -f scripts/create_tables.sql

# 6. Seed the database with sample data
python scripts/seed_db.py

# 7. Ingest regulatory documents into RAG
python scripts/ingest_docs.py --dir ../docs/

# 8. Start the backend
uvicorn main:app --reload --port 8000

# 9. Start Celery worker
celery -A tasks.celery_app worker --loglevel=info

# 10. Start the frontend
cd ../frontend
npm install
npm run dev
# → http://localhost:3000

# 11. (Optional) Start MQTT GPS simulator for testing
python scripts/mqtt_gps_simulator.py
```

---

*This document is the single source of truth for the Hi-Tech Waste Management AI Platform. All future development tracks should reference this file for schema, routes, agent responsibilities, and module scope.*

*Built for Hi-Tech Waste Management Sdn Bhd — Shah Alam, Selangor, Malaysia.*
*Platform Architecture by Zeyad × Claude (Anthropic), April 2026.*
