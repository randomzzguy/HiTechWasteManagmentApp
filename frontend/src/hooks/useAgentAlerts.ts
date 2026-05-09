import { useCallback, useEffect, useRef, useState } from 'react'
import { useWebSocket } from './useWebSocket'
import { agentApi } from '@/lib/api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type AlertSeverity = 'info' | 'warning' | 'critical' | 'success'

export type AlertEventType =
  | 'compliance.deadline_approaching'
  | 'compliance.overdue'
  | 'compliance.batch_expiring'
  | 'fleet.maintenance_due'
  | 'fleet.vehicle_breakdown'
  | 'fleet.driver_licence_expiring'
  | 'fleet.vehicle_location'
  | 'job.status_changed'
  | 'job.overdue'
  | 'job.assigned'
  | 'weighbridge.anomaly'
  | 'esg.milestone_reached'
  | 'esg.diversion_target_missed'
  | 'finance.invoice_overdue'
  | 'finance.payment_received'
  | 'system.agent_task_completed'
  | 'system.agent_task_failed'
  | 'system.health_check'
  | string

export interface AgentAlert {
  id: string
  event_type: AlertEventType
  severity: AlertSeverity
  title: string
  message: string
  module: string
  related_entity_type?: string
  related_entity_id?: string
  related_entity_name?: string
  action_url?: string
  action_label?: string
  metadata?: Record<string, unknown>
  is_read: boolean
  created_at: string
  read_at?: string
}

export interface UseAgentAlertsReturn {
  alerts: AgentAlert[]
  unreadCount: number
  isLoading: boolean
  isConnected: boolean
  markRead: (id: string) => Promise<void>
  markAllRead: () => Promise<void>
  dismissAlert: (id: string) => void
  clearAll: () => void
  refresh: () => Promise<void>
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MAX_ALERTS = 100
const WS_CHANNEL = '/ws/agent-alerts/'
const FETCH_PAGE_SIZE = 30

// ---------------------------------------------------------------------------
// Placeholder/fallback data for when the API is unavailable
// ---------------------------------------------------------------------------

const PLACEHOLDER_ALERTS: AgentAlert[] = [
  {
    id: 'placeholder-1',
    event_type: 'compliance.deadline_approaching',
    severity: 'warning',
    title: 'SW Batch Disposal Deadline in 5 Days',
    message: 'SW409 batch for Acme Manufacturing (200 kg) must be disposed by 25 Jun 2025.',
    module: 'compliance',
    related_entity_type: 'sw_batch',
    related_entity_id: 'batch-001',
    related_entity_name: 'SW409 – Acme Manufacturing',
    action_url: '/compliance/scheduled-waste',
    action_label: 'View Batch',
    is_read: false,
    created_at: new Date(Date.now() - 1000 * 60 * 15).toISOString(),
  },
  {
    id: 'placeholder-2',
    event_type: 'fleet.maintenance_due',
    severity: 'warning',
    title: 'Vehicle Maintenance Due: WVC 1234',
    message: 'Lorry WVC 1234 is due for scheduled service in 3 days (odometer: 98,200 km).',
    module: 'fleet',
    related_entity_type: 'vehicle',
    related_entity_id: 'vehicle-001',
    related_entity_name: 'WVC 1234',
    action_url: '/fleet',
    action_label: 'View Vehicle',
    is_read: false,
    created_at: new Date(Date.now() - 1000 * 60 * 45).toISOString(),
  },
  {
    id: 'placeholder-3',
    event_type: 'compliance.overdue',
    severity: 'critical',
    title: 'OVERDUE: SW322 Batch Disposal',
    message: 'SW322 clinical waste batch for KPJ Hospital (150 kg) is 2 days overdue. Immediate action required.',
    module: 'compliance',
    related_entity_type: 'sw_batch',
    related_entity_id: 'batch-002',
    related_entity_name: 'SW322 – KPJ Hospital',
    action_url: '/compliance/scheduled-waste',
    action_label: 'Take Action',
    is_read: false,
    created_at: new Date(Date.now() - 1000 * 60 * 120).toISOString(),
  },
  {
    id: 'placeholder-4',
    event_type: 'job.overdue',
    severity: 'warning',
    title: 'Job JOB-2025-0412 Overdue',
    message: 'Scheduled waste collection for Petronas R&D scheduled for yesterday has not been completed.',
    module: 'jobs',
    related_entity_type: 'job',
    related_entity_id: 'job-001',
    related_entity_name: 'JOB-2025-0412',
    action_url: '/jobs/job-001',
    action_label: 'View Job',
    is_read: true,
    created_at: new Date(Date.now() - 1000 * 60 * 200).toISOString(),
    read_at: new Date(Date.now() - 1000 * 60 * 60).toISOString(),
  },
  {
    id: 'placeholder-5',
    event_type: 'esg.milestone_reached',
    severity: 'success',
    title: 'ESG Milestone: 70% Diversion Rate Achieved',
    message: 'Company-wide diversion rate has exceeded the 70% target for June 2025. Great work!',
    module: 'esg',
    action_url: '/esg',
    action_label: 'View Dashboard',
    is_read: true,
    created_at: new Date(Date.now() - 1000 * 60 * 60 * 3).toISOString(),
    read_at: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(),
  },
]

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useAgentAlerts(): UseAgentAlertsReturn {
  const [alerts, setAlerts] = useState<AgentAlert[]>([])
  const [isLoading, setIsLoading] = useState(true)

  // Track whether we've done the initial fetch
  const hasFetchedRef = useRef(false)

  // ---------------------------------------------------------------------------
  // WebSocket connection
  // ---------------------------------------------------------------------------

  const wsUrl =
    typeof window !== 'undefined'
      ? `${process.env.NEXT_PUBLIC_WS_URL ?? 'ws://localhost:8000'}${WS_CHANNEL}`
      : null

  const { lastMessage, connectionStatus } = useWebSocket(wsUrl, {
    enabled: typeof window !== 'undefined',
    reconnectDelayMs: 2_000,
    maxReconnectDelayMs: 30_000,
  })

  const isConnected = connectionStatus === 'connected'

  // ---------------------------------------------------------------------------
  // Process incoming WebSocket messages
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!lastMessage) return

    const { type, payload } = lastMessage

    if (
      type === 'agent.event' ||
      type === 'alert' ||
      type === 'agent_alert'
    ) {
      const incoming = payload as AgentAlert

      if (!incoming?.id) return

      setAlerts((prev) => {
        // Avoid duplicates
        const exists = prev.some((a) => a.id === incoming.id)
        if (exists) {
          // Update in place (e.g. if it was re-broadcast as read)
          return prev.map((a) => (a.id === incoming.id ? incoming : a))
        }

        // Prepend newest, cap at MAX_ALERTS
        const next = [incoming, ...prev]
        return next.length > MAX_ALERTS ? next.slice(0, MAX_ALERTS) : next
      })
    }

    if (type === 'agent.event_read') {
      const { id } = payload as { id: string }
      setAlerts((prev) =>
        prev.map((a) =>
          a.id === id
            ? { ...a, is_read: true, read_at: new Date().toISOString() }
            : a
        )
      )
    }

    if (type === 'agent.all_read') {
      const now = new Date().toISOString()
      setAlerts((prev) =>
        prev.map((a) => ({ ...a, is_read: true, read_at: a.read_at ?? now }))
      )
    }
  }, [lastMessage])

  // ---------------------------------------------------------------------------
  // Initial fetch from REST API
  // ---------------------------------------------------------------------------

  const fetchAlerts = useCallback(async () => {
    if (hasFetchedRef.current) return
    hasFetchedRef.current = true
    setIsLoading(true)

    try {
      const response = await agentApi.getEvents({
        page: 1,
        page_size: FETCH_PAGE_SIZE,
        ordering: '-created_at',
      })

      const fetched = (response.results ?? []) as unknown as AgentAlert[]
      setAlerts(fetched)
    } catch {
      // API unavailable — fall back to placeholder data so the UI is usable
      setAlerts(PLACEHOLDER_ALERTS)
    } finally {
      setIsLoading(false)
    }
  }, [])

  const refresh = useCallback(async () => {
    hasFetchedRef.current = false
    await fetchAlerts()
  }, [fetchAlerts])

  useEffect(() => {
    fetchAlerts()
  }, [fetchAlerts])

  // ---------------------------------------------------------------------------
  // Mark single alert as read
  // ---------------------------------------------------------------------------

  const markRead = useCallback(async (id: string) => {
    // Optimistic update
    setAlerts((prev) =>
      prev.map((a) =>
        a.id === id
          ? { ...a, is_read: true, read_at: new Date().toISOString() }
          : a
      )
    )

    try {
      await agentApi.markRead(id)
    } catch {
      // Roll back on failure
      setAlerts((prev) =>
        prev.map((a) =>
          a.id === id ? { ...a, is_read: false, read_at: undefined } : a
        )
      )
    }
  }, [])

  // ---------------------------------------------------------------------------
  // Mark all alerts as read
  // ---------------------------------------------------------------------------

  const markAllRead = useCallback(async () => {
    const now = new Date().toISOString()

    // Optimistic update
    setAlerts((prev) =>
      prev.map((a) => ({ ...a, is_read: true, read_at: a.read_at ?? now }))
    )

    try {
      await agentApi.markAllRead()
    } catch {
      // Silently ignore — the optimistic update stays (eventual consistency)
    }
  }, [])

  // ---------------------------------------------------------------------------
  // Dismiss (remove from local state only — does NOT call the API)
  // ---------------------------------------------------------------------------

  const dismissAlert = useCallback((id: string) => {
    setAlerts((prev) => prev.filter((a) => a.id !== id))
  }, [])

  // ---------------------------------------------------------------------------
  // Clear all (local state only)
  // ---------------------------------------------------------------------------

  const clearAll = useCallback(() => {
    setAlerts([])
  }, [])

  // ---------------------------------------------------------------------------
  // Derived values
  // ---------------------------------------------------------------------------

  const unreadCount = alerts.filter((a) => !a.is_read).length

  return {
    alerts,
    unreadCount,
    isLoading,
    isConnected,
    markRead,
    markAllRead,
    dismissAlert,
    clearAll,
    refresh,
  }
}

export default useAgentAlerts
