// Feature: ai-assistant-streaming
import { describe, it, expect } from 'vitest'
import * as fc from 'fast-check'
import { dispatchSseEvent } from './sseUtils'

describe('dispatchSseEvent property tests', () => {
  // Property 5: Metadata rag_chunks_used is captured
  // Validates: Requirements 2.1
  it('Property 5: metadata event returns ragChunks equal to rag_chunks_used for any non-negative integer', () => {
    fc.assert(
      fc.property(fc.nat(), (n) => {
        const result = dispatchSseEvent('metadata', { rag_chunks_used: n })
        expect(result.ragChunks).toBe(n)
        expect(result.tokenDelta).toBeUndefined()
        expect(result.isDone).toBeUndefined()
        expect(result.errorText).toBeUndefined()
      }),
      { numRuns: 100 }
    )
  })

  // Property 7: Error event text is preserved
  // Validates: Requirements 4.1
  it('Property 7: error event returns errorText equal to data.error for any non-empty string', () => {
    fc.assert(
      fc.property(fc.string({ minLength: 1 }), (msg) => {
        const result = dispatchSseEvent('error', { error: msg })
        expect(result.errorText).toBe(msg)
        expect(result.tokenDelta).toBeUndefined()
        expect(result.isDone).toBeUndefined()
        expect(result.ragChunks).toBeUndefined()
      }),
      { numRuns: 100 }
    )
  })

  // Property 3: Unnamed data lines use default token logic
  // Validates: Requirements 1.3
  it('Property 3: null event type with token field returns tokenDelta', () => {
    fc.assert(
      fc.property(fc.string(), (token) => {
        const result = dispatchSseEvent(null, { token })
        expect(result.tokenDelta).toBe(token)
        expect(result.isDone).toBeUndefined()
        expect(result.errorText).toBeUndefined()
      }),
      { numRuns: 100 }
    )
  })
})
