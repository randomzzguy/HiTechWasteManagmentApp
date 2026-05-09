# Implementation Plan: AI Agents & RAG System

## Overview

The core infrastructure (Celery tasks for all 5 agents, RAG pipeline, SSE chat endpoint, agent event persistence, document ingestion) is already implemented. The remaining work is:

1. **Wire intent detection into the chat endpoint** — the orchestrator's `detect_intent` is not called from `routers/ai.py`
2. **Add agent trigger endpoints** — "Run Now" buttons need backend support
3. **Wire WebSocket updates into AgentAlertFeed** — currently polls only
4. **Add "Run Now" buttons to AgentStatusPanel** — UI gap
5. **Property-based and unit tests** — 15 properties defined in the design

## Tasks

- [x] 1. Wire intent detection into the chat endpoint
  - In `backend/routers/ai.py`, import `detect_intent` and `get_agent_system_prompt` from `agents/orchestrator.py`
  - In the `chat()` endpoint, call `intent = detect_intent(payload.message)` before building the system prompt
  - Replace the inline `_build_system_prompt` call with `get_agent_system_prompt(intent, str(effective_client_id) if effective_client_id else None)` as the base, then append the RAG context section to it
  - Include the detected `intent` in the SSE `metadata` event data: `{"model": ..., "rag_chunks_used": ..., "intent": intent, "client_id": ...}`
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [x] 2. Consolidate RAG retrieval to use shared retriever
  - Replace the inline `_retrieve_rag_context` function in `routers/ai.py` with a call to `rag.retriever.retrieve_context` (the async version)
  - Pass `milvus_host=settings.MILVUS_HOST`, `milvus_port=settings.MILVUS_PORT`, `ollama_base_url=settings.OLLAMA_BASE_URL`, `embed_model=settings.OLLAMA_EMBED_MODEL`
  - Remove the now-redundant inline function
  - _Requirements: 12.1, 12.3, 12.5, 12.6_

- [x] 3. Add agent trigger endpoints
  - In `backend/routers/ai.py`, add `POST /agents/{agent_name}/trigger` endpoint
  - Accept `agent_name` as a path parameter; validate it is one of `{'compliance', 'esg', 'operations', 'fleet'}`; return HTTP 422 for unknown agent names
  - Restrict to `management` and `superadmin` roles using `require_roles`
  - Map agent names to their Celery tasks: `compliance → run_compliance_agent.delay()`, `esg → run_esg_agent.delay()`, `operations → run_operations_agent.delay()`, `fleet → run_fleet_agent.delay()`
  - Return `{"agent": agent_name, "task_id": task.id, "message": "Agent run triggered"}` with HTTP 202
  - _Requirements: 16.4, 16.5, 18.4_

- [x] 4. Wire WebSocket updates into AgentAlertFeed
  - In `frontend/src/components/ai/AgentAlertFeed.tsx`, import `useWebSocket` hook from `hooks/useWebSocket.ts`
  - Subscribe to the `agent-alerts` WebSocket channel
  - WHEN a WebSocket message arrives with `event = 'alert'`, prepend the new event to the local query cache using `queryClient.setQueryData(['agent-events'], ...)` so it appears immediately without waiting for the next poll
  - Keep the existing 30-second `refetchInterval` as a fallback
  - _Requirements: 15.3_

- [x] 5. Add "Run Now" buttons to AgentStatusPanel
  - In `frontend/src/components/ai/AgentStatusPanel.tsx`, add a "Run Now" button to each of the four scheduled agent cards (Compliance, ESG, Operations, Fleet)
  - The button calls `aiApi.triggerAgent(agentName)` via a `useMutation`; on success show `toast.success("Agent run triggered")`; on error show `toast.error(...)`
  - Add `triggerAgent: (name: string) => Promise<{task_id: string}>` to `aiApi` in `frontend/src/lib/api.ts` calling `POST /api/v1/ai/agents/{name}/trigger`
  - Hide the "Run Now" button for users whose session role is not `management` or `superadmin`
  - Show a spinner on the button while the mutation is pending
  - _Requirements: 16.4, 16.5, 18.4_

- [x] 6. Checkpoint — verify intent routing and agent triggers work end-to-end
  - Send a test chat message containing "SW code" and verify the SSE `metadata` event contains `"intent": "compliance"`
  - Send a test chat message with no keywords and verify `"intent": "client"`
  - Call `POST /api/v1/ai/agents/compliance/trigger` and verify a Celery task is queued
  - Ensure all TypeScript types compile without errors (`npx tsc --noEmit` from `frontend/`)

- [ ] 7. Write property-based tests for pure logic functions
  - Create `backend/tests/test_ai_agents_properties.py` using Hypothesis
  - Each test must have a docstring with tag: `Feature: ai-agents-rag-system, Property {N}: {property_text}`
  - Configure `@settings(max_examples=100)` on each test
  - [ ] 7.1 Property 1: Intent detection is deterministic
    - `@given(st.text())` — call `detect_intent` twice with same input; assert results are equal
    - **Validates: Requirements 10.1, 10.2**
  - [ ] 7.2 Property 2: Intent detection defaults to 'client' on no match
    - `@given(st.text(alphabet=st.characters(whitelist_categories=('Nd',))))` — numeric-only strings contain no keywords; assert result is `'client'`
    - **Validates: Requirements 10.3**
  - [ ] 7.3 Property 3: Intent detection is case-insensitive
    - `@given(st.sampled_from(['sw code', 'carbon', 'schedule', 'fleet', 'client']))` — assert `detect_intent(kw.upper()) == detect_intent(kw.lower())`
    - **Validates: Requirements 10.4**
  - [ ] 7.4 Property 4: Chunk count is bounded by text length
    - `@given(st.text())` — assert `len(chunk_text(t)) == 0` iff `t.strip() == ''`; assert `len(chunk_text(t)) >= 1` when `t.strip() != ''`
    - **Validates: Requirements 11.4**
  - [ ] 7.5 Property 5: Chunk overlap preserves context (approximate)
    - `@given(st.text(min_size=200), st.integers(min_value=50, max_value=200), st.integers(min_value=10, max_value=50))` — for consecutive chunks, verify last N words of chunk i appear in chunk i+1
    - **Validates: Requirements 11.4**
  - [ ] 7.6 Property 6: Chunk text is a subset of original text
    - `@given(st.text(min_size=1))` — for each chunk, verify all words appear in original text
    - **Validates: Requirements 11.4**
  - [ ] 7.7 Property 7: Clean text preserves non-whitespace content
    - `@given(st.text())` — assert set of non-whitespace tokens in `clean_text(t)` equals set in `t`
    - **Validates: Requirements 11.4**
  - [ ] 7.8 Property 8: Agent system prompt contains agent identity
    - `@given(st.sampled_from(['compliance', 'esg', 'operations', 'fleet', 'client']))` — assert prompt contains "Hi-Tech" and agent-specific identity phrase
    - **Validates: Requirements 2.3, 4.3, 6.2, 8.2, 9.3**
  - [ ] 7.9 Property 9: Client-scoped system prompt contains client_id
    - `@given(st.sampled_from(['compliance', 'esg', 'operations', 'fleet', 'client']), st.uuids().map(str))` — assert `get_agent_system_prompt(intent, client_id)` contains `client_id`
    - **Validates: Requirements 9.5**
  - [ ] 7.10 Property 13: Agent event severity is always valid
    - `@given(st.sampled_from(['info', 'warning', 'critical']))` — assert `_persist_event(severity=s)` stores exactly `s` in the DB
    - **Validates: Requirements 14.1**
  - [ ] 7.11 Property 15: ESG diversion rate calculation is correct
    - `@given(st.floats(min_value=0.001, max_value=100000), st.floats(min_value=0, max_value=100000))` — assert `round((R / W) * 100, 2)` matches expected formula; assert 0 when W=0
    - **Validates: Requirements 3.3**

- [ ] 8. Write unit and integration tests
  - Create `backend/tests/test_ai_agents.py` with pytest + httpx `AsyncClient`
  - [ ] 8.1 Intent detection unit tests
    - Test each keyword routes to the correct agent (one test per agent)
    - Test empty string → 'client'
    - Test mixed-case keyword → correct agent
    - Test ambiguous message (keywords from two agents) → agent with higher score wins
  - [ ] 8.2 System prompt unit tests
    - Test each agent prompt contains required identity phrases
    - Test client-scoped prompt contains client_id
    - Test unknown intent falls back to 'client' prompt
  - [ ] 8.3 Chunking unit tests
    - Test empty string → empty list
    - Test single word → single chunk
    - Test text shorter than chunk_size → single chunk
    - Test text longer than chunk_size → multiple chunks
    - Test overlap: consecutive chunks share words
  - [ ] 8.4 SSE stream integration tests
    - Mock Ollama to return a fixed response; verify event sequence: metadata → token(s) → done
    - Mock Ollama to be unreachable; verify error event is emitted
    - Verify `intent` field appears in metadata event after task 1 is complete
  - [ ] 8.5 Agent trigger endpoint tests
    - Test valid agent name → 202 with task_id
    - Test unknown agent name → 422
    - Test non-management role → 403
  - [ ] 8.6 RBAC tests
    - Test `POST /ingest-document` with driver role → 403
    - Test `POST /agents/compliance/trigger` with operations_manager role → 403
    - Test `GET /agent-events` with any authenticated role → 200
  - [ ] 8.7 Compliance agent unit test
    - Mock DB to return 3 batches (1 overdue, 2 warning); run `run_compliance_agent`; assert 3 agent events created with correct severities
  - [ ] 8.8 ESG agent unit test
    - Mock DB to return 2 clients (1 below target, 1 above); run `run_esg_agent`; assert 1 warning event + 1 report event created
  - [ ]* 8.9 Property 10: SSE metadata event precedes token events
    - Use `httpx.AsyncClient` with mocked Ollama; collect all SSE events; assert first event has `event='metadata'`
    - **Validates: Requirements 13.2, 13.3**
  - [ ]* 8.10 Property 11: SSE stream terminates with done event
    - Use `httpx.AsyncClient` with mocked Ollama; collect all SSE events; assert last event has `event='done'` with `done=True`
    - **Validates: Requirements 13.4**
  - [ ]* 8.11 Property 12: RAG degradation on Milvus unavailability
    - Mock Milvus to raise `ConnectionError`; send chat request; assert stream completes without error event
    - **Validates: Requirements 12.5**
  - [ ]* 8.12 Property 14: Compliance agent creates events for all near-deadline batches
    - `@given(st.integers(min_value=0, max_value=20))` — mock N batches within 14 days; run agent; assert exactly N events created
    - **Validates: Requirements 1.2, 1.3**

- [ ] 9. Write frontend component tests
  - [ ]* 9.1 Create `frontend/src/components/ai/__tests__/AgentAlertFeed.test.tsx`
    - Test: renders event list with correct severity badge colours (red=critical, amber=warning, blue=info)
    - Test: clicking an event calls `PATCH /agent-events/{id}/read` and expands body
    - Test: unread count badge shows correct number
    - Test: WebSocket message prepends new event to top of list
  - [ ]* 9.2 Create `frontend/src/components/ai/__tests__/AgentStatusPanel.test.tsx`
    - Test: "Run Now" button hidden for non-management users
    - Test: "Run Now" button calls `aiApi.triggerAgent` and shows success toast
    - Test: spinner shown while mutation is pending

- [ ] 10. Final checkpoint — ensure all tests pass
  - Run `pytest backend/tests/test_ai_agents.py backend/tests/test_ai_agents_properties.py -v`
  - Run `npx vitest run` from `frontend/`
  - Run `npm run lint` from `frontend/`
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP delivery
- The five agent Celery tasks (`run_compliance_agent`, `run_esg_agent`, `run_operations_agent`, `run_fleet_agent`) are fully implemented — no changes needed to their core logic
- The RAG pipeline (`pipeline.py`, `retriever.py`) is fully implemented — task 2 only consolidates the duplicate inline function in `ai.py`
- The `AgentBaseTask` base class provides `_persist_event`, `_broadcast_alert`, and `_call_ollama` helpers used by all agent tasks
- Property tests for pure functions (Properties 1–9, 13, 15) do not require a running server — they test `detect_intent`, `get_agent_system_prompt`, `chunk_text`, and `clean_text` directly
- The `useWebSocket` hook in `frontend/src/hooks/useWebSocket.ts` already handles the WebSocket connection — task 4 only needs to subscribe to the `agent-alerts` channel and update the query cache
- Celery Beat schedules are already configured in `tasks/celery_app.py` for all four scheduled agents
