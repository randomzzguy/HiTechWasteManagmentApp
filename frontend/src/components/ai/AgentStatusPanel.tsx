'use client'

import { useEffect, useState } from 'react'
import { CheckCircle2, Clock, AlertTriangle, RefreshCw, Zap } from 'lucide-react'

interface AgentStatus {
  name: string
  display_name: string
  last_run: string | null
  next_run: string | null
  last_status: 'success' | 'failed' | 'running' | 'never'
  events_today: number
  schedule: string
}

const AGENT_ICONS: Record<string, string> = {
  compliance: '⚖️',
  esg: '🌿',
  operations: '📋',
  fleet: '🚛',
  client_intelligence: '🤝',
}

const MOCK_AGENTS: AgentStatus[] = [
  {
    name: 'compliance',
    display_name: 'Compliance Agent',
    last_run: null,
    next_run: null,
    last_status: 'never',
    events_today: 0,
    schedule: 'Every 6 hours',
  },
  {
    name: 'esg',
    display_name: 'ESG & Carbon Agent',
    last_run: null,
    next_run: null,
    last_status: 'never',
    events_today: 0,
    schedule: 'Weekly (Mon 08:00 MYT)',
  },
  {
    name: 'operations',
    display_name: 'Operations Agent',
    last_run: null,
    next_run: null,
    last_status: 'never',
    events_today: 0,
    schedule: 'Daily 06:00 MYT',
  },
  {
    name: 'fleet',
    display_name: 'Fleet & Maintenance Agent',
    last_run: null,
    next_run: null,
    last_status: 'never',
    events_today: 0,
    schedule: 'Daily 07:00 MYT',
  },
  {
    name: 'client_intelligence',
    display_name: 'Client Intelligence Agent',
    last_run: null,
    next_run: null,
    last_status: 'never',
    events_today: 0,
    schedule: 'Weekly (Sun 09:00 MYT)',
  },
]

function getToken(): string {
  if (typeof window === 'undefined') return ''
  return (
    sessionStorage.getItem('access_token') ??
    localStorage.getItem('access_token') ??
    ''
  )
}

function formatRelative(iso: string | null): string {
  if (!iso) return 'Never'
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

export default function AgentStatusPanel() {
  const [agents, setAgents] = useState<AgentStatus[]>(MOCK_AGENTS)
  const [loading, setLoading] = useState(false)
  const [ragStatus, setRagStatus] = useState<{
    milvus: boolean
    ollama: boolean
  } | null>(null)

  const fetchStatus = async () => {
    setLoading(true)
    try {
      const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
      const token = getToken()

      const ragRes = await fetch(`${API_BASE}/api/v1/ai/rag-status`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (ragRes.ok) {
        const data = await ragRes.json()
        setRagStatus({
          milvus: data.milvus?.connected ?? false,
          ollama: data.ollama?.connected ?? false,
        })
      }
    } catch {
      // Silently fail — show mock data
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 60_000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
        <div className="flex items-center gap-2">
          <Zap className="w-4 h-4 text-yellow-400" />
          <h3 className="text-sm font-semibold text-gray-900">Agent Status</h3>
        </div>
        <button
          onClick={fetchStatus}
          disabled={loading}
          className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
        >
          <RefreshCw
            className={`w-3.5 h-3.5 text-gray-500 ${loading ? 'animate-spin' : ''}`}
          />
        </button>
      </div>

      {/* Infrastructure status */}
      {ragStatus && (
        <div className="px-4 py-2 border-b border-gray-100 flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <div
              className={`w-1.5 h-1.5 rounded-full ${
                ragStatus.ollama ? 'bg-green-400' : 'bg-red-400'
              }`}
            />
            <span className="text-xs text-gray-500">Ollama</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div
              className={`w-1.5 h-1.5 rounded-full ${
                ragStatus.milvus ? 'bg-green-400' : 'bg-red-400'
              }`}
            />
            <span className="text-xs text-gray-500">Milvus</span>
          </div>
        </div>
      )}

      {/* Agent list */}
      <div className="divide-y divide-gray-100">
        {agents.map((agent) => (
          <div key={agent.name} className="px-4 py-3 flex items-center gap-3">
            <span className="text-lg leading-none">{AGENT_ICONS[agent.name] ?? '🤖'}</span>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-800 truncate">
                {agent.display_name}
              </p>
              <p className="text-xs text-gray-400">{agent.schedule}</p>
            </div>
            <div className="text-right flex-shrink-0">
              <div className="flex items-center gap-1.5 justify-end">
                {agent.last_status === 'success' ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-green-400" />
                ) : agent.last_status === 'failed' ? (
                  <AlertTriangle className="w-3.5 h-3.5 text-red-400" />
                ) : agent.last_status === 'running' ? (
                  <RefreshCw className="w-3.5 h-3.5 text-brand-400 animate-spin" />
                ) : (
                  <Clock className="w-3.5 h-3.5 text-gray-400" />
                )}
                <span className="text-xs text-gray-500">
                  {formatRelative(agent.last_run)}
                </span>
              </div>
              {agent.events_today > 0 && (
                <p className="text-xs text-yellow-400 mt-0.5">
                  {agent.events_today} event{agent.events_today !== 1 ? 's' : ''} today
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
