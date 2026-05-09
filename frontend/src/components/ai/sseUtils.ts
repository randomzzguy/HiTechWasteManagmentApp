export type SseEventType = 'metadata' | 'token' | 'done' | 'error' | null

export interface SseDispatchResult {
  tokenDelta?: string       // text to append to fullContent
  ragChunks?: number        // rag_chunks_used to store
  isDone?: boolean          // true when stream is complete
  errorText?: string        // error message to display
}

export function dispatchSseEvent(
  eventType: SseEventType,
  data: Record<string, unknown>
): SseDispatchResult {
  switch (eventType) {
    case 'metadata':
      return { ragChunks: (data.rag_chunks_used as number) ?? 0 }
    case 'token':
      if (data.done) return { isDone: true, ragChunks: (data.rag_chunks_used as number) ?? 0 }
      return { tokenDelta: (data.token as string) ?? '' }
    case 'done':
      return { isDone: true, ragChunks: (data.rag_chunks_used as number) ?? 0 }
    case 'error':
      return { errorText: (data.error as string) ?? 'Unknown error' }
    default:
      // Backward-compat: unnamed data lines treated as token events
      if (data.token !== undefined) return { tokenDelta: data.token as string }
      if (data.done) return { isDone: true }
      if (data.error) return { errorText: data.error as string }
      if (data.rag_chunks_used !== undefined) return { ragChunks: data.rag_chunks_used as number }
      return {}
  }
}
