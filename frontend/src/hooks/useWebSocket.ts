import { useEffect, useRef, useState, useCallback } from 'react'
import { sleep } from '@/lib/utils'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ConnectionStatus =
  | 'connecting'
  | 'connected'
  | 'disconnected'
  | 'reconnecting'
  | 'error'

export interface WebSocketMessage<T = unknown> {
  type: string
  payload: T
  timestamp: string
}

export interface UseWebSocketOptions {
  /** Whether to automatically connect on mount (default: true) */
  enabled?: boolean
  /** Query params appended to the URL */
  params?: Record<string, string>
  /** Initial reconnect delay in ms (default: 1000) */
  reconnectDelayMs?: number
  /** Maximum reconnect delay in ms (default: 30_000) */
  maxReconnectDelayMs?: number
  /** Maximum number of reconnect attempts before giving up (default: Infinity) */
  maxRetries?: number
  /** Called when the connection is opened */
  onOpen?: (event: Event) => void
  /** Called when a raw message arrives (before state update) */
  onMessage?: (event: MessageEvent) => void
  /** Called when the connection is closed */
  onClose?: (event: CloseEvent) => void
  /** Called on an error */
  onError?: (event: Event) => void
}

export interface UseWebSocketReturn<T = unknown> {
  lastMessage: WebSocketMessage<T> | null
  sendMessage: (data: unknown) => void
  connectionStatus: ConnectionStatus
  reconnect: () => void
  disconnect: () => void
}

// ---------------------------------------------------------------------------
// Helper — build full WS URL
// ---------------------------------------------------------------------------

function buildUrl(
  url: string,
  params?: Record<string, string>
): string {
  try {
    // Accept full ws:// URLs or relative paths
    const base =
      url.startsWith('ws://') || url.startsWith('wss://')
        ? url
        : `${process.env.NEXT_PUBLIC_WS_URL ?? 'ws://localhost:8000'}${url}`

    if (!params || Object.keys(params).length === 0) return base

    const separator = base.includes('?') ? '&' : '?'
    const query = new URLSearchParams(params).toString()
    return `${base}${separator}${query}`
  } catch {
    return url
  }
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useWebSocket<T = unknown>(
  url: string | null | undefined,
  options: UseWebSocketOptions = {}
): UseWebSocketReturn<T> {
  const {
    enabled = true,
    params,
    reconnectDelayMs = 1_000,
    maxReconnectDelayMs = 30_000,
    maxRetries = Infinity,
    onOpen,
    onMessage,
    onClose,
    onError,
  } = options

  const [lastMessage, setLastMessage] = useState<WebSocketMessage<T> | null>(null)
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('disconnected')

  const wsRef = useRef<WebSocket | null>(null)
  const retryCountRef = useRef(0)
  const isMountedRef = useRef(true)
  const shouldReconnectRef = useRef(true)
  const connectingRef = useRef(false)

  // Keep options in a ref so callbacks are always fresh
  const optionsRef = useRef(options)
  useEffect(() => {
    optionsRef.current = options
  })

  // ---------------------------------------------------------------------------
  // connect
  // ---------------------------------------------------------------------------

  const connect = useCallback(() => {
    if (!url || !enabled || !isMountedRef.current) return
    if (connectingRef.current) return
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    connectingRef.current = true

    const fullUrl = buildUrl(url, params)

    setConnectionStatus(
      retryCountRef.current > 0 ? 'reconnecting' : 'connecting'
    )

    let ws: WebSocket
    try {
      ws = new WebSocket(fullUrl)
    } catch (err) {
      console.error('[useWebSocket] Failed to construct WebSocket:', err)
      connectingRef.current = false
      setConnectionStatus('error')
      return
    }

    wsRef.current = ws

    ws.onopen = (event: Event) => {
      if (!isMountedRef.current) return
      retryCountRef.current = 0
      connectingRef.current = false
      setConnectionStatus('connected')
      optionsRef.current.onOpen?.(event)
    }

    ws.onmessage = (event: MessageEvent) => {
      if (!isMountedRef.current) return
      optionsRef.current.onMessage?.(event)

      try {
        const parsed = JSON.parse(event.data as string) as WebSocketMessage<T>
        setLastMessage({
          ...parsed,
          timestamp: parsed.timestamp ?? new Date().toISOString(),
        })
      } catch {
        // If the message is not JSON, wrap it in a generic envelope
        setLastMessage({
          type: 'raw',
          payload: event.data as T,
          timestamp: new Date().toISOString(),
        })
      }
    }

    ws.onerror = (event: Event) => {
      if (!isMountedRef.current) return
      console.error('[useWebSocket] WebSocket error:', event)
      setConnectionStatus('error')
      optionsRef.current.onError?.(event)
    }

    ws.onclose = (event: CloseEvent) => {
      connectingRef.current = false
      if (!isMountedRef.current) return

      optionsRef.current.onClose?.(event)

      if (!shouldReconnectRef.current) {
        setConnectionStatus('disconnected')
        return
      }

      // Don't reconnect on normal closure (1000) or going away (1001)
      if (event.code === 1000 || event.code === 1001) {
        setConnectionStatus('disconnected')
        return
      }

      const attempt = retryCountRef.current + 1

      if (attempt > maxRetries) {
        console.warn(
          `[useWebSocket] Max retries (${maxRetries}) reached. Giving up.`
        )
        setConnectionStatus('error')
        return
      }

      retryCountRef.current = attempt
      setConnectionStatus('reconnecting')

      // Exponential backoff with jitter
      const delay = Math.min(
        reconnectDelayMs * Math.pow(2, attempt - 1) + Math.random() * 500,
        maxReconnectDelayMs
      )

      console.info(
        `[useWebSocket] Reconnecting in ${Math.round(delay)}ms (attempt ${attempt})`
      )

      sleep(delay).then(() => {
        if (isMountedRef.current && shouldReconnectRef.current) {
          connect()
        }
      })
    }
  }, [url, enabled, params, reconnectDelayMs, maxReconnectDelayMs, maxRetries]) // eslint-disable-line react-hooks/exhaustive-deps

  // ---------------------------------------------------------------------------
  // sendMessage
  // ---------------------------------------------------------------------------

  const sendMessage = useCallback((data: unknown) => {
    const ws = wsRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      console.warn('[useWebSocket] Cannot send: WebSocket is not open.')
      return
    }
    try {
      ws.send(typeof data === 'string' ? data : JSON.stringify(data))
    } catch (err) {
      console.error('[useWebSocket] Send error:', err)
    }
  }, [])

  // ---------------------------------------------------------------------------
  // disconnect
  // ---------------------------------------------------------------------------

  const disconnect = useCallback(() => {
    shouldReconnectRef.current = false
    retryCountRef.current = 0
    const ws = wsRef.current
    if (ws) {
      ws.close(1000, 'Client disconnect')
      wsRef.current = null
    }
    setConnectionStatus('disconnected')
  }, [])

  // ---------------------------------------------------------------------------
  // reconnect (manual)
  // ---------------------------------------------------------------------------

  const reconnect = useCallback(() => {
    shouldReconnectRef.current = true
    retryCountRef.current = 0
    const ws = wsRef.current
    if (ws && ws.readyState !== WebSocket.CLOSED) {
      ws.close()
    }
    wsRef.current = null
    connect()
  }, [connect])

  // ---------------------------------------------------------------------------
  // Mount / unmount
  // ---------------------------------------------------------------------------

  useEffect(() => {
    isMountedRef.current = true
    shouldReconnectRef.current = true

    if (url && enabled) {
      connect()
    }

    return () => {
      isMountedRef.current = false
      shouldReconnectRef.current = false
      const ws = wsRef.current
      if (ws) {
        ws.close(1000, 'Component unmount')
        wsRef.current = null
      }
    }
  }, [url, enabled, connect])

  return {
    lastMessage,
    sendMessage,
    connectionStatus,
    reconnect,
    disconnect,
  }
}

export default useWebSocket
