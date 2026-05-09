'use client'

import { useEffect, useState, useCallback } from 'react'
import { Bell, BellOff, AlertTriangle, Info, CheckCircle2, RefreshCw } from 'lucide-react'

interface AgentEvent {
  id: string
  agent_name: string
  event_type: string
  severity: 'info' | 'warning' | 'critical'
  title: string
  body: string | null
  reference_type: string | null
  reference_id: string | null
  is_read: boolean
  created_at: string
}

interface EventsResponse {
  total: number
  unread_count: number
  critical_unread_count: number
  items: AgentEvent[]
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
const WS_BASE = process.env.NEXT_PUBLIC_WS_URL ?? 'ws://localhost:8000'

function getToken(): string {
  if (typeof window === 'undefined') return ''
  return (
    sessionStorage.getItem('access_token') ??
    localStorage.getItem('access_token') ??
    ''
  )
}

function severityColor(severity: string) {
  switch (severity) {
    case 'critical':
      return 'text-red-400 bg-red-50 border-red-200'
    case 'warning':
      return 'text-yellow-400 bg-amber-50 border-amber-200'
    default:
      return 'text-brand-400 bg-brand-50 border-brand-200'
  }
}

function SeverityIcon({ severity }: { severity: string }) {
  if (severity === 'critical')
    return <AlertTriangle className="w-3.5 h-3.5 text-red-400 flex-shrink-0" />
  if (severity === 'warning')
    return <AlertTriangle className="w-3.5 h-3.5 text-yellow-400 flex-shrink-0" />
  return <Info className="w-3.5 h-3.5 text-brand-400 flex-shrink-0" />
}

function formatTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return new Date(iso).toLocaleDateString('en-MY', { day: 'numeric', month: 'short' })
}

function agentLabel(name: string): string {
  const map: Record<string, string> = {
    compliance: 'Compliance',
    esg: 'ESG',
    operations: 'Operations',
    fleet: 'Fleet',
    client_intelligence: 'Client Intel',
  }
  return map[name] ?? name
}

export default function AgentAlertFeed() {
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [criticalCount, setCriticalCount] = useState(0)
  const [loading, setLoading] = useState(false)
  const [filter, setFilter] = useState<'all' | 'unread' | 'critical'>('all')
  const [expanded, setExpanded] = useState<string | null>(null)

  const fetchEvents = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ limit: '30', skip: '0' })
      if (filter === 'unread') params.set('is_read', 'false')
      if (filter === 'critical') params.set('severity', 'critical')

      const res = await fetch(`${API_BASE}/api/v1/ai/agent-events?${params}`, {
        headers: { Authorization: `Bearer ${getToken()}` },
      })
      if (!res.ok) return
      const data: EventsResponse = await res.json()
      setEvents(data.items ?? [])
      setUnreadCount(data.unread_count ?? 0)
      setCriticalCount(data.critical_unread_count ?? 0)
    } catch {
      // Silently fail
    } finally {
      setLoading(false)
    }
  }, [filter])

  useEffect(() => {
    fetchEvents()
  }, [fetchEvents])

  // WebSocket for real-time alerts
  useEffect(() => {
    const token = getToken()
    if (!token) return

    let ws: WebSocket | null = null
    let reconnectTimer: ReturnType<typeof setTimeout>

    const connect = () => {
      try {
        ws = new WebSocket(`${WS_BASE}/ws/agent-alerts?token=${token}`)

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)
            if (data.event === 'alert' || data.event === 'agent_event') {
              fetchEvents()
            }
          } catch {
            // Ignore parse errors
          }
        }

        ws.onclose = () => {
          reconnectTimer = setTimeout(connect, 5000)
        }
      } catch {
        reconnectTimer = setTimeout(connect, 5000)
      }
    }

    connect()
    return () => {
      clearTimeout(reconnectTimer)
      ws?.close()
    }
  }, [fetchEvents])

  const markRead = async (id: string) => {
    try {
      await fetch(`${API_BASE}/api/v1/ai/agent-events/${id}/read`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${getToken()}`,
        },
        body: JSON.stringify({ is_read: true }),
      })
      setEvents((prev) =>
        prev.map((e) => (e.id === id ? { ...e, is_read: true } : e))
      )
      setUnreadCount((c) => Math.max(0, c - 1))
    } catch {
      // Silently fail
    }
  }

  const markAllRead = async () => {
    try {
      await fetch(`${API_BASE}/api/v1/ai/agent-events/mark-all-read`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${getToken()}` },
      })
      setEvents((prev) => prev.map((e) => ({ ...e, is_read: true })))
      setUnreadCount(0)
      setCriticalCount(0)
    } catch {
      // Silently fail
    }
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
        <div className="flex items-center gap-2">
          <Bell className="w-4 h-4 text-gray-500" />
          <h3 className="text-sm font-semibold text-gray-900">Agent Alerts</h3>
          {unreadCount > 0 && (
            <span className="px-1.5 py-0.5 rounded-full text-xs font-medium bg-red-500/20 text-red-400 border border-red-500/20">
              {unreadCount}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={fetchEvents}
            disabled={loading}
            className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <RefreshCw
              className={`w-3.5 h-3.5 text-gray-500 ${loading ? 'animate-spin' : ''}`}
            />
          </button>
          {unreadCount > 0 && (
            <button
              onClick={markAllRead}
              className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
              title="Mark all as read"
            >
              <BellOff className="w-3.5 h-3.5 text-gray-500" />
            </button>
          )}
        </div>
      </div>

      {/* Filter tabs */}
      <div className="flex border-b border-gray-100">
        {(['all', 'unread', 'critical'] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`flex-1 py-2 text-xs font-medium capitalize transition-colors ${
              filter === f
                ? 'text-gray-900 border-b-2 border-brand-600'
                : 'text-gray-400 hover:text-gray-700'
            }`}
          >
            {f}
            {f === 'critical' && criticalCount > 0 && (
              <span className="ml-1 text-red-400">({criticalCount})</span>
            )}
          </button>
        ))}
      </div>

      {/* Events list */}
      <div className="flex-1 overflow-y-auto divide-y divide-gray-100 max-h-96">
        {events.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-10 text-gray-400">
            <CheckCircle2 className="w-8 h-8 mb-2 opacity-30" />
            <p className="text-sm">No alerts</p>
          </div>
        ) : (
          events.map((event) => (
            <div
              key={event.id}
              className={`px-4 py-3 cursor-pointer hover:bg-gray-50 transition-colors ${
                !event.is_read ? 'bg-brand-50/50' : ''
              }`}
              onClick={() => {
                setExpanded(expanded === event.id ? null : event.id)
                if (!event.is_read) markRead(event.id)
              }}
            >
              <div className="flex items-start gap-2.5">
                <SeverityIcon severity={event.severity} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span
                      className={`text-xs px-1.5 py-0.5 rounded border ${severityColor(event.severity)}`}
                    >
                      {agentLabel(event.agent_name)}
                    </span>
                    <span className="text-xs text-gray-400">
                      {formatTime(event.created_at)}
                    </span>
                    {!event.is_read && (
                      <span className="w-1.5 h-1.5 rounded-full bg-brand-400 flex-shrink-0" />
                    )}
                  </div>
                  <p className="text-sm text-gray-800 leading-snug">{event.title}</p>
                  {expanded === event.id && event.body && (
                    <p className="mt-1.5 text-xs text-gray-500 leading-relaxed">
                      {event.body}
                    </p>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
