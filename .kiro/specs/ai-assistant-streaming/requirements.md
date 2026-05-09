# Requirements Document

## Introduction

The AI Assistant Streaming feature completes the end-to-end SSE (Server-Sent Events) integration between the FastAPI backend and the Next.js 14 frontend for the `/ai-assistant` page of the Hi-Tech Waste Management Platform. The backend already emits named SSE events (`metadata`, `token`, `done`, `error`) via `POST /api/v1/ai/chat`. The frontend `AIAssistantChat.tsx` currently only parses `data:` lines and ignores `event:` lines, causing the `rag_chunks_used` metadata to be missed when it arrives in the `metadata` event before any tokens stream. This spec covers fixing the SSE parser, surfacing RAG chunk counts correctly, adding a backend health indicator in the chat header, and verifying that `AgentStatusPanel` and `AgentAlertFeed` load correctly from their respective endpoints.

## Glossary

- **SSE_Parser**: The client-side logic in `AIAssistantChat.tsx` that reads the raw SSE byte stream from `response.body` and extracts event type and data payloads.
- **SSE_Event**: A single Server-Sent Event consisting of an optional `event:` line followed by a `data:` line, terminated by a blank line.
- **Named_Event**: An SSE event that carries an `event:` field (e.g. `event: metadata`, `event: token`, `event: done`, `event: error`).
- **Metadata_Event**: The first SSE event emitted by the backend before any tokens, carrying `{"model": "...", "rag_chunks_used": N, "client_id": "..."}`.
- **Token_Event**: An SSE event carrying `{"token": "...", "done": false}` representing one streamed LLM token.
- **Done_Event**: The final SSE event carrying `{"token": "", "done": true, "total_tokens": N, "rag_chunks_used": N}`.
- **Error_Event**: An SSE event carrying `{"error": "..."}` emitted when the backend encounters a connection or LLM error.
- **RAG_Chunks_Used**: The integer count of Milvus context chunks injected into the LLM prompt for a given response.
- **Health_Indicator**: A small status badge in the `AIAssistantChat` header showing whether Ollama and the backend are reachable.
- **AgentStatusPanel**: The React component at `frontend/src/components/ai/AgentStatusPanel.tsx` that displays AI agent run statuses and infrastructure health (Ollama, Milvus) by polling `GET /api/v1/ai/rag-status`.
- **AgentAlertFeed**: The React component at `frontend/src/components/ai/AgentAlertFeed.tsx` that displays agent-emitted alerts by polling `GET /api/v1/ai/agent-events` and subscribing to the WebSocket at `/ws/agent-alerts`.
- **RAG_Status_Endpoint**: `GET /api/v1/ai/rag-status` — returns Ollama and Milvus connectivity status.
- **Agent_Events_Endpoint**: `GET /api/v1/ai/agent-events` — returns paginated agent alert events.
- **Chat_Endpoint**: `POST /api/v1/ai/chat` — accepts a chat request and streams SSE events.
- **Ollama**: The local LLM runtime serving the `llama3` model on port 11434.
- **AIAssistantChat**: The React component at `frontend/src/components/ai/AIAssistantChat.tsx` responsible for the chat UI and SSE streaming.

## Requirements

### Requirement 1: Named SSE Event Parsing

**User Story:** As a developer, I want the SSE parser to correctly handle named SSE events, so that the frontend can distinguish between `metadata`, `token`, `done`, and `error` events and process each appropriately.

#### Acceptance Criteria

1. WHEN the SSE_Parser reads a line beginning with `event:`, THE SSE_Parser SHALL store the trimmed event name as the current event type for the next `data:` line.
2. WHEN the SSE_Parser reads a line beginning with `data:` and a current event type has been stored, THE SSE_Parser SHALL process the data payload according to the stored event type and then clear the stored event type.
3. WHEN the SSE_Parser reads a line beginning with `data:` and no current event type has been stored, THE SSE_Parser SHALL process the data payload using the default token-accumulation logic (backward-compatible behaviour).
4. WHEN the SSE_Parser encounters a blank line, THE SSE_Parser SHALL reset the current event type to null, completing the current SSE_Event boundary.
5. THE SSE_Parser SHALL process `event:` and `data:` lines in the order they appear in the stream without reordering.

### Requirement 2: RAG Chunks Used — Capture from Metadata Event

**User Story:** As an operations user, I want to see how many document chunks were used to answer my question, so that I can understand whether the response was RAG-augmented or purely LLM-generated.

#### Acceptance Criteria

1. WHEN the SSE_Parser receives a Named_Event of type `metadata`, THE AIAssistantChat SHALL parse the `rag_chunks_used` field from the data payload and store it as the pending RAG chunk count for the current response.
2. WHEN the SSE_Parser receives a Named_Event of type `done`, THE AIAssistantChat SHALL finalise the assistant message with the `rag_chunks_used` value captured from either the Metadata_Event or the Done_Event, whichever is non-zero.
3. WHEN `rag_chunks_used` is greater than zero, THE AIAssistantChat SHALL display the count below the assistant message bubble in the format `N document chunk(s) referenced`.
4. WHEN `rag_chunks_used` is zero or undefined, THE AIAssistantChat SHALL display no chunk count annotation below the assistant message bubble.
5. WHEN the RAG toggle is set to off by the user, THE AIAssistantChat SHALL display no chunk count annotation regardless of any value received in the stream.

### Requirement 3: Backend Health Indicator in Chat Header

**User Story:** As a user, I want to see whether the AI backend is reachable before I send a message, so that I know immediately if the service is down rather than waiting for a failed response.

#### Acceptance Criteria

1. WHEN the AIAssistantChat component mounts, THE AIAssistantChat SHALL fetch `GET /api/v1/ai/rag-status` to determine Ollama and backend reachability.
2. WHEN the RAG_Status_Endpoint returns `ollama.connected: true`, THE Health_Indicator SHALL display a green dot with the label `Ollama online` in the chat header.
3. WHEN the RAG_Status_Endpoint returns `ollama.connected: false` or the request fails, THE Health_Indicator SHALL display a red dot with the label `Ollama offline` in the chat header.
4. WHILE the initial health check is in progress, THE Health_Indicator SHALL display a neutral grey dot with the label `Checking…` in the chat header.
5. THE AIAssistantChat SHALL re-poll the RAG_Status_Endpoint every 60 seconds to keep the Health_Indicator current.
6. IF the RAG_Status_Endpoint request fails with a network error, THEN THE AIAssistantChat SHALL treat the status as `ollama.connected: false` and update the Health_Indicator accordingly.

### Requirement 4: Error Event Handling and User-Facing Error States

**User Story:** As a user, I want clear error messages when the AI service is unavailable or returns an error, so that I understand what went wrong and what to do next.

#### Acceptance Criteria

1. WHEN the SSE_Parser receives a Named_Event of type `error`, THE AIAssistantChat SHALL replace the streaming assistant message bubble with the error text from `data.error` and mark the message with the error style.
2. WHEN the `fetch` call to the Chat_Endpoint throws a network error (e.g. `TypeError: Failed to fetch`), THE AIAssistantChat SHALL display the message `Failed to connect to the AI service. Please ensure Ollama is running and try again.` in an error-styled assistant bubble.
3. WHEN the Chat_Endpoint returns an HTTP status code other than 200, THE AIAssistantChat SHALL display the message `The AI service returned an error (HTTP N). Please try again.` where N is the status code, in an error-styled assistant bubble.
4. WHEN the user clicks the stop button during streaming, THE AIAssistantChat SHALL abort the fetch request and mark the partial message as complete without the error style.
5. IF an error occurs during streaming, THEN THE AIAssistantChat SHALL re-enable the input field and send button so the user can retry.

### Requirement 5: AgentStatusPanel Loads from RAG Status Endpoint

**User Story:** As an operations manager, I want the Agent Status panel to show live infrastructure health, so that I can confirm Ollama and Milvus are operational before relying on AI features.

#### Acceptance Criteria

1. WHEN the AgentStatusPanel component mounts, THE AgentStatusPanel SHALL fetch `GET /api/v1/ai/rag-status` and display the `ollama.connected` and `milvus.connected` values as coloured status dots.
2. WHEN `ollama.connected` is true, THE AgentStatusPanel SHALL render a green dot next to the label `Ollama`.
3. WHEN `milvus.connected` is true, THE AgentStatusPanel SHALL render a green dot next to the label `Milvus`.
4. WHEN either `ollama.connected` or `milvus.connected` is false, THE AgentStatusPanel SHALL render a red dot next to the respective label.
5. IF the RAG_Status_Endpoint request fails, THEN THE AgentStatusPanel SHALL silently retain the previous status values without crashing.
6. THE AgentStatusPanel SHALL re-poll the RAG_Status_Endpoint every 60 seconds.

### Requirement 6: AgentAlertFeed Loads from Agent Events Endpoint

**User Story:** As an operations manager, I want the Agent Alert Feed to display real-time alerts from AI agents, so that I can act on compliance deadlines, fleet maintenance warnings, and ESG anomalies.

#### Acceptance Criteria

1. WHEN the AgentAlertFeed component mounts, THE AgentAlertFeed SHALL fetch `GET /api/v1/ai/agent-events` with default parameters `limit=30&skip=0` and render the returned items.
2. WHEN the Agent_Events_Endpoint returns a non-empty `items` array, THE AgentAlertFeed SHALL render each event showing its `title`, `severity` badge, `agent_name` label, and relative `created_at` timestamp.
3. WHEN the Agent_Events_Endpoint returns an empty `items` array, THE AgentAlertFeed SHALL display the empty state message `No alerts`.
4. WHEN the user selects the `unread` filter tab, THE AgentAlertFeed SHALL re-fetch with `is_read=false` and display only unread events.
5. WHEN the user selects the `critical` filter tab, THE AgentAlertFeed SHALL re-fetch with `severity=critical` and display only critical events.
6. WHEN the user clicks an unread event, THE AgentAlertFeed SHALL call `PATCH /api/v1/ai/agent-events/{id}/read` with `{"is_read": true}` and update the event's visual state to read.
7. WHEN the user clicks `Mark all as read`, THE AgentAlertFeed SHALL call `POST /api/v1/ai/agent-events/mark-all-read` and update all visible events to the read state.
8. IF the Agent_Events_Endpoint request fails, THEN THE AgentAlertFeed SHALL silently retain the previous event list without crashing.
9. WHEN a WebSocket message is received on `/ws/agent-alerts` with `event: "alert"` or `event: "agent_event"`, THE AgentAlertFeed SHALL re-fetch the event list to include the new alert.

### Requirement 7: Streaming Resilience and Stop Behaviour

**User Story:** As a user, I want to be able to stop a streaming response mid-way and immediately send a new message, so that I can correct a poorly-phrased question without waiting for the full response.

#### Acceptance Criteria

1. WHEN the user clicks the stop button during streaming, THE AIAssistantChat SHALL call `AbortController.abort()` on the active fetch request within 100ms of the click.
2. WHEN the fetch is aborted, THE AIAssistantChat SHALL set `isStreaming` to false and mark the partial assistant message as complete (not an error).
3. WHEN `isStreaming` is false, THE AIAssistantChat SHALL enable the textarea and send button so the user can compose and send a new message.
4. WHILE `isStreaming` is true, THE AIAssistantChat SHALL disable the textarea and replace the send button with the stop button.
5. WHEN a new message is sent while a previous stream is still active (e.g. via programmatic call), THE AIAssistantChat SHALL abort the previous stream before initiating the new fetch request.
