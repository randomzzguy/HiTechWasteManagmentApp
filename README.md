# Hi-Tech Waste Management System

A comprehensive AI-powered waste management platform for Malaysia, featuring intelligent scheduling, compliance monitoring, invoice management, and ESG reporting.

---

## AI Assistant Features

The system includes a powerful **AI Assistant** with 6 major feature categories and 30+ functions to streamline operations:

### 1. Database Agent
Query and modify the database using natural language. No SQL required.
- **Query:** "Show all clients in Kuala Lumpur"
- **Create:** "Add new client ABC Sdn Bhd"
- **Update:** "Update client status to active"
- **Delete:** "Delete the test job"
- **Search:** "Find jobs scheduled for tomorrow"

### 2. Bulk Import Agent
Import CSV/Excel files with AI-powered column mapping and validation.
- Auto-detects and maps CSV columns to database fields
- Validates data formats and identifies duplicates
- Preview before committing changes
- Supports: Clients, Jobs, Waste Records, Invoices, Vehicles, Employees

### 3. Smart Scheduling Agent
AI-powered job assignment and route optimization.
- **Auto-Assignment:** Suggests best vehicle/driver combinations
- **Route Optimization:** Minimizes travel time and fuel costs
- **Conflict Detection:** Identifies scheduling overlaps
- **Priority Scoring:** Ranks jobs by urgency, location, capacity

### 4. Compliance Monitoring Agent
Track permits, licenses, and regulatory deadlines with automated alerts.
- **Monitored Items:**
  - Scheduled waste storage deadlines (DOE 90/180 day rule)
  - Vehicle road tax, insurance, PUSPAKOM
  - Downstream buyer licenses
  - Destruction certificates
  - Consignment notes status
- **Alert Levels:** Warning (30 days), Critical (7 days), Expired
- **Reports:** DOE compliance, regulatory audits

### 5. Invoice Intelligence Agent
AR aging reports, collection strategies, and payment predictions.
- **Aging Reports:** Current, 30, 60, 90, 120+ day buckets
- **Risk Scoring:** AI-powered invoice risk assessment
- **Client Profiles:** Payment behavior analysis
- **Collection Strategies:** Tailored action plans per client
- **Payment Predictions:** ML-based payment probability
- **Collection Prompts:** AI-crafted email & call scripts

### 6. ESG Report Generation Agent
Automated Environmental, Social, and Governance (ESG) sustainability reporting.
- **Carbon Tracking:** Emissions, avoidance, net impact, trees equivalent
- **Waste Diversion:** Recycling rates, circular economy metrics
- **SDG Mapping:** UN Sustainable Development Goal contributions
- **Report Types:** Monthly, quarterly, annual, client-specific
- **Dashboard:** Real-time sustainability metrics

**📖 Detailed documentation:** [AI_FEATURES_GUIDE.md](./AI_FEATURES_GUIDE.md)

---

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Git

### Setup

1. **Clone the repository:**
```bash
git clone <repository-url>
cd HiTechWasteManagmentApp
```

2. **Environment setup:**
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. **Start services:**
```bash
docker-compose up -d
```

4. **Access the application:**
- Frontend: http://localhost:3000
- API Documentation: http://localhost:8000/docs
- Backend API: http://localhost:8000

---

## System Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Frontend      │────▶│   Backend API   │────▶│   PostgreSQL   │
│   (Next.js)     │     │   (FastAPI)     │     │   (Database)   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌─────────────────┐
                        │   AI Assistant  │
                        │   (OpenAI GPT)  │
                        └─────────────────┘
```

### Tech Stack

**Frontend:**
- Next.js 14 (React)
- TypeScript
- Tailwind CSS
- Shadcn/ui components

**Backend:**
- FastAPI (Python)
- SQLAlchemy 2.0 (async ORM)
- Pydantic v2 (validation)
- Celery (background tasks)
- Redis (caching & message broker)

**AI Integration:**
- OpenAI GPT-4 API
- Function calling for tool use
- RAG (Retrieval-Augmented Generation)
- Streaming responses

**Infrastructure:**
- Docker & Docker Compose
- PostgreSQL 15
- Redis 7
- MinIO (S3-compatible storage)
- Mosquitto (MQTT broker)

---

## API Endpoints

### AI Agent Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/ai/chat-db` | POST | Database-enabled chat |
| `/api/v1/ai/import/analyze` | POST | Analyze import file |
| `/api/v1/ai/import/execute` | POST | Execute bulk import |
| `/api/v1/ai/schedule/suggest` | POST | Suggest job assignments |
| `/api/v1/ai/schedule/route` | POST | Optimize routes |
| `/api/v1/ai/schedule/conflicts` | GET | Detect conflicts |
| `/api/v1/ai/compliance/dashboard` | GET | Compliance overview |
| `/api/v1/ai/compliance/check` | POST | Run compliance check |
| `/api/v1/ai/compliance/report` | POST | Generate compliance report |
| `/api/v1/ai/invoice/aging` | GET | AR aging report |
| `/api/v1/ai/invoice/collection-strategy/{id}` | GET | Collection strategy |
| `/api/v1/ai/invoice/portfolio-metrics` | GET | Portfolio health |
| `/api/v1/ai/esg/report` | POST | Generate ESG report |
| `/api/v1/ai/esg/dashboard` | GET | ESG dashboard |
| `/api/v1/ai/esg/client-report/{id}` | GET | Client ESG report |

**Full API documentation:** http://localhost:8000/docs (when running)

---

## Development

### Backend Development

```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt

# Run development server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Development

```bash
cd frontend
npm install

# Run development server
npm run dev
```

### Running Tests

```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
npm test
```

---

## Project Structure

```
HiTechWasteManagmentApp/
├── AI_FEATURES_GUIDE.md    # AI Assistant documentation
├── README.md               # This file
├── PLAN.md                 # Project planning document
├── PRODUCTION_ROADMAP.md   # Production deployment roadmap
├── docker-compose.yml      # Docker orchestration
├── backend/                # FastAPI backend
│   ├── agents/             # AI agent modules
│   │   ├── database_agent.py
│   │   ├── bulk_import_agent.py
│   │   ├── smart_scheduling_agent.py
│   │   ├── compliance_monitoring_agent.py
│   │   ├── invoice_intelligence_agent.py
│   │   └── esg_report_agent.py
│   ├── models/             # SQLAlchemy models
│   ├── routers/            # API endpoints
│   ├── tasks/              # Celery background tasks
│   └── templates/          # Report templates
├── frontend/               # Next.js frontend
│   ├── src/
│   │   ├── components/     # React components
│   │   │   └── ai/         # AI Assistant components
│   │   └── app/            # Next.js pages
└── docs/                   # Documentation
```

---

## Features Overview

### Core Waste Management
- **Client Management:** Onboarding, waste streams, locations
- **Job Scheduling:** Scheduled waste, recycling, BSF, destruction
- **Fleet Management:** Vehicles, drivers, maintenance, trips
- **Invoice & Billing:** Automated invoicing, payments, aging
- **Compliance:** DOE regulations, permit tracking, certificates
- **Reporting:** Operational, financial, sustainability reports

### AI-Powered Features
- **Natural Language Queries:** Ask the database anything
- **Smart Import:** CSV/Excel with AI validation
- **Intelligent Scheduling:** Auto-assign and optimize routes
- **Proactive Compliance:** Deadline tracking and alerts
- **AR Intelligence:** Aging, collections, payment predictions
- **ESG Automation:** Carbon tracking, SDG reporting

---

## Documentation

- **[AI Features Guide](./AI_FEATURES_GUIDE.md)** - Complete AI Assistant documentation
- **[Production Roadmap](./PRODUCTION_ROADMAP.md)** - Deployment planning
- **[API Docs](http://localhost:8000/docs)** - Interactive API documentation (when running)

---

## License

[Add license information here]

---

## Support

For issues or questions:
1. Check the [AI Features Guide](./AI_FEATURES_GUIDE.md)
2. Review API documentation at `/docs`
3. Contact system administrator

---

*Built for sustainable waste management in Malaysia*
