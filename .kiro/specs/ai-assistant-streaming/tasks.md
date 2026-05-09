# Implementation Plan: AI Assistant Streaming

## Overview

Minimal targeted fixes to `AIAssistantChat.tsx`: extract `dispatchSseEvent` as a pure exported function, fix the SSE parser to track named event types, and add a health indicator in the chat header. No changes to `AgentStatusPanel` or `AgentAlertFeed`.

## Tasks

- [x] 1. Extract `dispatchSseEvent` as a pure exported function
  - Create `frontend/src/components/ai/sseUtils.ts` with the `SseEventType`, `SseDispatchResult` types and the `dispatchSseEvent` function as defined in the design
  - Export `dispatchSseEvent` so it can be imported by `AIAssistantChat.tsx` and property tests
  - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 4.1_

  - [ ]* 1.1 Write property tests for `dispatchSseEvent`
    - **Property 5: Metadata rag_chunks_used is captured** — for any non-negative integer N, `dispatchSseEvent('metadata', { rag_chunks_used: N })` returns `{ ragChunks: N }`
    - **Validates: Requirements 2.1**
    - **Property 7: Error event text is preserved** — for any non-empty string, `dispatchSseEvent('error', { error: msg })` returns `{ errorText: msg }`
    - **Validates: Requirements 4.1**
    - **Property 3: Unnamed data lines use default token logic** — for any string token with no event type, result contains `tokenDelta`
    - **Validates: Requirements 1.3**

- [x] 2. Fix the SSE parser in `sendMessage` to track `currentEventType`
  - Add `let currentEventType: string | null = null` inside the reader loop in `sendMessage`
  - Replace the existing `for (const line of lines)` block with the state-machine logic from the design: set `currentEventType` on `event:` lines, clear on blank lines, pass to `dispatchSseEvent` on `data:` lines
  - Apply the `SseDispatchResult` from `dispatchSseEvent` to update `fullContent`, `ragChunks`, streaming state, and error state
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 4.1_

  - [ ]* 2.1 Write property tests for SSE parser state machine
    - **Property 1: Event type captured from `event:` lines** — for any string value, a line `event: <value>` sets `currentEventType` to the trimmed value
    - **Validates: Requirements 1.1**
    - **Property 2: Data dispatch clears event type** — after processing a `data:` line, `currentEventType` is null
    - **Validates: Requirements 1.2**
    - **Property 4: Blank lines reset event type** — for any set event type, a blank line results in `currentEventType === null`
    - **Validates: Requirements 1.4**

- [x] 3. Add health indicator state and fetch to `AIAssistantChat`
  - Add `HealthStatus` type and `healthStatus` state (`'checking'` initial value)
  - Add `checkHealth` callback that fetches `GET /api/v1/ai/rag-status` and sets state to `'online'` or `'offline'`; catches network errors as `'offline'`
  - Add `useEffect` that calls `checkHealth()` on mount and sets a 60-second `setInterval`; cleans up on unmount
  - Add the health indicator dot + label JSX in the chat header between the title block and the RAG toggle, using `healthConfig` as defined in the design
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [x] 4. Checkpoint — lint and type check
  - Run `npm run lint` from `frontend/` and fix any reported issues
  - Ensure TypeScript compiles without errors (`tsc --noEmit`)
  - Ensure all tests pass, ask the user if questions arise.
