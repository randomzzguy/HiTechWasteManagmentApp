# Design Document: AI Agents & RAG System

## Overview

The AI Agents & RAG System is the intelligence layer of the Hi-Tech Waste Management platform. Five specialised agents — Compliance, ESG & Carbon, Operations & Scheduling, Fleet & Maintenance, and Client Intelligence — run on Celery Beat schedules and respond to on-demand queries via the AI chat endpoint. All agents share a common infrastructure: the `AgentBaseTask` Celery base class, the RAG retrieval pipeline (Milvus + Ollama), the `agent_events` persistence table, and the WebSocket broadcast mechanism.

The core implementation is substantially complete. This design documents the current architecture, identifies the remaining gaps, and defines the correctness properties used for property-based testing.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Next.js Frontend                                │
│  AIAssistantChat (SSE reader) │ AgentAlertFeed │ AgentStatusPanel   │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ POST /api/v1/ai/chat (SSE)
                           │ GET  /api/v1/ai/agent-events
                           │ WS   /ws/agent-alerts
┌──────────────────────────▼──────────────────────────────────────────┐
│                     FastAPI Backend                                 │
│                                                                     │
│  routers/ai.py                                                      │
│  ├── POST /chat          → SSE stream (RAG + Ollama)                │
│  ├── GET  /agent-events  → paginated agent event list               │
│  ├── POST /ingest-document → file upload + Celery task              │
│  ├── GET  /documents     → document list with ingestion status      │
│  ├── POST /documents/{id}/re-ingest → reset + re-queue             │
│  └── GET  /rag-status    → Milvus + Ollama health                   │
│                                                                     │
│  agents/orchestrator.py                                             │
│  ├── detect_intent(message) → 'compliance'|'esg'|'operations'|...  │
│  └── get_agent_system_prompt(intent) → system prompt string        │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
   ┌───────────┐    ┌─────────────┐   ┌──────────────┐
   │  Ollama   │    │   Milvus    │   │  PostgreSQL  │
   │ llama3    │    │ hitech_rag  │   │ agent_events │
   │ nomic-    │    │ collection  │   │ documents    │
   │ embed-text│    │             │   │              │
   └───────────┘    └─────────────┘   └──────────────┘

Celery Beat Tasks (agents queue):
  run_compliance_agent  → every 6h
  run_esg_agent         → Monday 08:00 MST
  run_operations_agent  → daily 06:00 MST
  run_fleet_agent       → daily 07:00 MST
  (Client Intelligence Agent is on-demand only — no scheduled run)
```

### Request Flow — Chat Endpoint

```
User message
  → POST /api/v1/ai/chat
  → detect_intent(message) → agent intent
  → get_agent_system_prompt(intent) → system prompt
  → _retrieve_rag_context(query, client_id, collection, top_k)
      → Ollama /api/embeddings → query vector
      → Milvus search (COSINE, IVF_FLAT, nprobe=16) → top-k chunks
  → _build_system_prompt(chunks, client_id) → augmented prompt
  → Ollama /api/chat (stream=True) → token stream
  → SSE: metadata → token* → done
```

### Request Flow — Scheduled Agent Run

```
Celery Beat trigger
  → AgentBaseTask.run()
  → SyncSessionLocal() → DB query (domain-specific)
  → _call_ollama(prompt, system_prompt) → LLM text
  → _persist_event(agent_name, event_type, severity, title, body)
  → _broadcast_alert(event) → POST /internal/broadcast-alert
      → WebSocket manager → all connected clients on 'agent-alerts'
```

---

## Components and Interfaces

### Backend: `agents/orchestrator.py`

Already implemented. Key functions:

```python
def detect_intent(message: str) -> str:
    # Keyword scoring across 5 intent categories
    # Returns: 'compliance' | 'esg' | 'operations' | 'fleet' | 'client'
    # Default: 'client' when all scores = 0

def get_agent_system_prompt(intent: str, client_id: str | None = None) -> str:
    # Returns the specialised system prompt for the given intent
    # Optionally scopes to a specific client

def build_messages(
    user_message: str,
    system_prompt: str,
    conversation_history: list[dict] | None = None,
    max_history: int = 20,
) -> list[dict]:
    # Constructs [system, ...history[-20:], user] message list
```

**Gap:** `detect_intent` is not called from `routers/ai.py` — the chat endpoint uses its own inline system prompt builder. The orchestrator's intent detection needs to be wired into the chat endpoint so the correct agent system prompt is used.

### Backend: `tasks/agent_tasks.py`

Already implemented: `run_compliance_agent`, `run_esg_agent`, `run_operations_agent`, `run_fleet_agent`.

**Gap:** `run_client_intelligence_agent` is not implemented as a Celery task (it is on-demand only, which is correct). However, the Fleet Agent's MQTT-triggered GPS anomaly detection is not yet wired to the MQTT gateway.

**Gap:** Agent trigger endpoints (`POST /api/v1/ai/agents/{name}/trigger`) are not yet implemented.

### Backend: `rag/pipeline.py`

Already implemented: `extract_text`, `clean_text`, `chunk_text`, `generate_embedding`, `ensure_collection`, `store_chunks`.

### Backend: `rag/retriever.py`

Already implemented: `retrieve_context` (async), `retrieve_context_sync`, `list_collections`, `collection_stats`.

**Gap:** The chat endpoint (`routers/ai.py`) has its own inline `_retrieve_rag_context` function that duplicates `retriever.retrieve_context`. These should be consolidated to use the shared retriever.

### Backend: `routers/ai.py`

Already implemented: `POST /chat`, `GET /agent-events`, `PATCH /agent-events/{id}/read`, `POST /agent-events/mark-all-read`, `POST /ingest-document`, `GET /documents`, `DELETE /documents/{id}`, `POST /documents/{id}/re-ingest`, `GET /rag-status`.

**Gap:** The chat endpoint does not call `detect_intent` from the orchestrator — it uses a single generic system prompt. The intent-based routing needs to be wired in.

**Gap:** Agent trigger endpoints are missing.

### Frontend: `components/ai/AIAssistantChat.tsx`

Already implemented with SSE streaming, RAG toggle, health indicator, and conversation history.

### Frontend: `components/ai/AgentAlertFeed.tsx`

Already implemented as a basic list. **Gap:** WebSocket integration for real-time updates is not yet wired — the component only polls.

### Frontend: `components/ai/AgentStatusPanel.tsx`

Already implemented as a basic status display. **Gap:** "Run Now" buttons are not yet implemented.

---

## Data Models

### AgentEvent (existing — `models/document.py`)

```python
class AgentEvent(Base):
    __tablename__ = "agent_events"

    id: UUID (PK)
    agent_name: str(50)        # compliance | esg | operations | fleet | client
    event_type: str(50)        # alert | action | recommendation | report
    severity: str(20)          # info | warning | critical
    title: str(200)
    body: Text
    reference_type: str(50)    # job | vehicle | sw_batch | client | document
    reference_id: UUID (nullable)
    is_read: bool (default False)
    created_at: DateTime(tz=True)
```

### Document (existing — `models/document.py`)

```python
class Document(Base):
    __tablename__ = "documents"

    id: UUID (PK)
    title: str(500)
    doc_type: str(50)          # regulation | contract | sop | report | manual
    file_path: str(1000)
    mime_type: str(100)
    file_size_bytes: int (nullable)
    milvus_collection: str(100)
    client_id: UUID (nullable, FK clients.id)
    ingested_into_rag: bool (default False)
    ingestion_error: Text (nullable)
    uploaded_by: UUID (FK users.id)
    created_at: DateTime(tz=True)
```

---

## API Endpoint Summary

### Existing Endpoints (already implemented)

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/ai/chat` | RAG SSE streaming chat |
| GET | `/api/v1/ai/agent-events` | List agent events (filterable, paginated) |
| PATCH | `/api/v1/ai/agent-events/{id}/read` | Mark event as read |
| POST | `/api/v1/ai/agent-events/mark-all-read` | Bulk mark all read |
| POST | `/api/v1/ai/ingest-document` | Upload + ingest document |
| GET | `/api/v1/ai/documents` | List documents with ingestion status |
| DELETE | `/api/v1/ai/documents/{id}` | Delete document + Milvus chunks |
| POST | `/api/v1/ai/documents/{id}/re-ingest` | Re-queue failed ingestion |
| GET | `/api/v1/ai/rag-status` | RAG system health |

### New Endpoints (to be implemented)

| Method | Path | Description | Roles |
|---|---|---|---|
| POST | `/api/v1/ai/agents/{name}/trigger` | Manually trigger a scheduled agent run | management, superadmin |

---

## Correctness Properties

### Property 1: Intent detection is deterministic

*For any* message string, `detect_intent(message)` SHALL always return the same intent value when called multiple times with the same input. The function is pure (no side effects, no randomness).

**Validates: Requirements 10.1, 10.2**

---

### Property 2: Intent detection defaults to 'client' on no match

*For any* message string that contains no keywords from any of the five intent categories, `detect_intent(message)` SHALL return `'client'`.

**Validates: Requirements 10.3**

---

### Property 3: Intent detection is case-insensitive

*For any* keyword K in the intent keyword map, `detect_intent(K.upper())` SHALL return the same intent as `detect_intent(K.lower())`.

**Validates: Requirements 10.4**

---

### Property 4: Chunk count is bounded by text length

*For any* text string T and chunk parameters (chunk_size, overlap), `len(chunk_text(T, chunk_size, overlap))` SHALL be 0 if T is empty or whitespace-only, and SHALL be at least 1 if T contains at least one non-whitespace word.

**Validates: Requirements 11.4**

---

### Property 5: Chunk overlap preserves context

*For any* text T chunked with overlap O > 0, for any two consecutive chunks C_i and C_{i+1}, the last O words of C_i SHALL appear as the first O words of C_{i+1} (approximately — sentence-boundary splitting may cause minor deviations).

**Validates: Requirements 11.4**

---

### Property 6: Chunk text is a subset of original text

*For any* text T and any chunk C produced by `chunk_text(T)`, every word in C SHALL appear in T. No words are invented or modified during chunking.

**Validates: Requirements 11.4**

---

### Property 7: Clean text preserves non-whitespace content

*For any* text T, `clean_text(T)` SHALL not remove any non-whitespace characters. The set of non-whitespace tokens in `clean_text(T)` SHALL equal the set of non-whitespace tokens in T.

**Validates: Requirements 11.4**

---

### Property 8: Agent system prompt contains agent identity

*For any* valid intent string I in `{'compliance', 'esg', 'operations', 'fleet', 'client'}`, `get_agent_system_prompt(I)` SHALL return a string containing the word "Hi-Tech" and a domain-specific identity phrase (e.g. "Compliance Agent", "ESG", "Operations", "Fleet", "Client Intelligence").

**Validates: Requirements 2.3, 4.3, 6.2, 8.2, 9.3**

---

### Property 9: Client-scoped system prompt contains client_id

*For any* valid intent I and any non-None `client_id` string, `get_agent_system_prompt(I, client_id)` SHALL return a string containing the `client_id` value.

**Validates: Requirements 9.5**

---

### Property 10: SSE metadata event precedes token events

*For any* valid chat request, the first SSE event emitted SHALL have `event = 'metadata'`. No `token` events SHALL be emitted before the `metadata` event.

**Validates: Requirements 13.2, 13.3**

---

### Property 11: SSE stream terminates with done event

*For any* successful chat request, the last SSE event emitted SHALL have `event = 'done'` with `done = True` in the data payload.

**Validates: Requirements 13.4**

---

### Property 12: RAG degradation on Milvus unavailability

*For any* chat request where Milvus is unreachable, the SSE stream SHALL still emit `metadata`, `token`, and `done` events (using pure LLM generation). No `error` event SHALL be emitted solely due to Milvus unavailability.

**Validates: Requirements 12.5**

---

### Property 13: Agent event severity is always valid

*For any* `Agent_Event` record created by any agent task, the `severity` field SHALL be one of `{'info', 'warning', 'critical'}`. No other values are permitted.

**Validates: Requirements 14.1**

---

### Property 14: Compliance agent creates events for all near-deadline batches

*For any* set of `scheduled_waste_batches` where N batches have `storage_deadline <= CURRENT_DATE + 14 days` and `status = 'in_storage'`, the compliance agent run SHALL create exactly N `Agent_Event` records (one per batch).

**Validates: Requirements 1.2, 1.3**

---

### Property 15: ESG diversion rate calculation is correct

*For any* client with `total_waste_kg = W` and `total_recyclable_kg = R` where W > 0, the ESG agent SHALL compute `diversion_rate = round((R / W) * 100, 2)`. For W = 0, the rate SHALL be 0.

**Validates: Requirements 3.3**

---

---

## Testing Strategy

### Property-Based Tests (Hypothesis)

File: `backend/tests/test_ai_agents_properties.py`

All 15 properties above are implemented as Hypothesis `@given(...)` tests with `@settings(max_examples=100)`.

Pure-logic properties (1–9, 13, 15) test functions directly without HTTP calls.
Integration properties (10–12, 14) use `httpx.AsyncClient` with the FastAPI app mounted and mocked Ollama/Milvus.

### Unit and Integration Tests

File: `backend/tests/test_ai_agents.py`

- Intent detection: verify each keyword routes to the correct agent
- System prompt: verify each agent prompt contains required identity phrases
- Chunking: verify empty input, single-word input, and large document inputs
- SSE stream: verify event sequence (metadata → token* → done)
- Agent event creation: verify compliance agent creates correct events for mock batch data
- RBAC: verify 403 on ingest-document for non-management roles
- Re-ingest: verify error state is reset and task is re-queued

### Frontend Tests (Vitest + RTL)

File: `frontend/src/components/ai/__tests__/AgentAlertFeed.test.tsx`

- Renders event list with correct severity badge colours
- Marks event as read on click
- Unread count badge updates correctly
- WebSocket message triggers immediate re-render
