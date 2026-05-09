'use client'

import { useQuery } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import {
  AlertTriangle,
  CheckCircle2,
  Container,
  HardHat,
  PackageCheck,
  Wrench,
  ChevronRight,
  RefreshCw,
} from 'lucide-react'
import { operationalFieldApi } from '@/lib/api'
import { OperationalFieldSummary, OperationalAlert } from '@/types/operational-field'
import { cn } from '@/lib/utils'

// ── Helpers ───────────────────────────────────────────────────

const severityColor = {
  info: 'text-brand-400 bg-brand-50 border-brand-200',
  warning: 'text-amber-400 bg-amber-50 border-amber-200',
  critical: 'text-red-400 bg-red-50 border-red-200',
}

const severityDot = {
  info: 'bg-brand-400',
  warning: 'bg-amber-400',
  critical: 'bg-red-400 animate-pulse',
}

function StatusCount({
  label,
  value,
  color,
}: {
  label: string
  value: number
  color: string
}) {
  return (
    <div className="flex items-center justify-between py-1">
      <span className="text-xs text-gray-500">{label}</span>
      <span className={cn('text-xs font-semibold tabular-nums', color)}>{value}</span>
    </div>
  )
}

function AlertRow({ alert }: { alert: OperationalAlert }) {
  return (
    <div
      className={cn(
        'flex items-start gap-2 px-3 py-2 rounded-lg border text-xs',
        severityColor[alert.severity]
      )}
    >
      <span
        className={cn(
          'w-1.5 h-1.5 rounded-full mt-1 flex-shrink-0',
          severityDot[alert.severity]
        )}
      />
      <span className="leading-relaxed">{alert.message}</span>
    </div>
  )
}

// ── Main widget ───────────────────────────────────────────────

export default function OperationalFieldWidget() {
  const router = useRouter()

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['operational-field-summary'],
    queryFn: () => operationalFieldApi.getSummary(),
    staleTime: 60_000,
    refetchInterval: 2 * 60_000, // poll every 2 minutes
  })

  const summary = data as OperationalFieldSummary | null

  const compactors = summary?.compaction_machines ?? {}
  const containers = summary?.containers ?? {}
  const staff = summary?.staff ?? {}
  const disruptions = summary?.disruptions_open ?? {}
  const deliveries = summary?.recycler_deliveries ?? {}
  const alerts = summary?.alerts ?? []

  const criticalAlerts = alerts.filter((a) => a.severity === 'critical').length
  const warningAlerts = alerts.filter((a) => a.severity === 'warning').length

  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-emerald-50 flex items-center justify-center">
            <Container className="w-3.5 h-3.5 text-emerald-400" />
          </div>
          <span className="text-sm font-semibold text-gray-900">Field Operations</span>
          {criticalAlerts > 0 && (
            <span className="flex items-center gap-1 text-[10px] font-bold text-red-400 bg-red-50 border border-red-200 px-1.5 py-0.5 rounded-full">
              <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse" />
              {criticalAlerts} critical
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => refetch()}
            className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
            title="Refresh"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="p-5 space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-4 rounded bg-gray-200 animate-pulse" style={{ width: `${60 + i * 10}%` }} />
          ))}
        </div>
      ) : (
        <div className="p-5 space-y-5">
          {/* Active alerts */}
          {alerts.length > 0 && (
            <div className="space-y-2">
              {alerts.slice(0, 3).map((alert, i) => (
                <AlertRow key={i} alert={alert} />
              ))}
              {alerts.length > 3 && (
                <p className="text-xs text-gray-400 text-center">
                  +{alerts.length - 3} more alert{alerts.length - 3 > 1 ? 's' : ''}
                </p>
              )}
            </div>
          )}

          {alerts.length === 0 && (
            <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-emerald-50 border border-emerald-200">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
              <span className="text-xs text-emerald-400">All field operations normal</span>
            </div>
          )}

          {/* Status grid */}
          <div className="grid grid-cols-2 gap-4">
            {/* Compactors */}
            <div className="space-y-1">
              <div className="flex items-center gap-1.5 mb-2">
                <Wrench className="w-3.5 h-3.5 text-gray-500" />
                <span className="text-xs font-semibold text-gray-700">Compactors</span>
              </div>
              <StatusCount label="Deployed" value={compactors.deployed ?? 0} color="text-brand-400" />
              <StatusCount label="Available" value={compactors.available ?? 0} color="text-emerald-400" />
              <StatusCount label="Maintenance" value={compactors.maintenance ?? 0} color="text-amber-400" />
            </div>

            {/* Containers */}
            <div className="space-y-1">
              <div className="flex items-center gap-1.5 mb-2">
                <Container className="w-3.5 h-3.5 text-gray-500" />
                <span className="text-xs font-semibold text-gray-700">Containers</span>
              </div>
              <StatusCount label="At site" value={containers.at_site ?? 0} color="text-brand-400" />
              <StatusCount label="In transit" value={containers.in_transit ?? 0} color="text-violet-400" />
              <StatusCount label="Available" value={containers.available ?? 0} color="text-emerald-400" />
            </div>

            {/* Staff */}
            <div className="space-y-1">
              <div className="flex items-center gap-1.5 mb-2">
                <HardHat className="w-3.5 h-3.5 text-gray-500" />
                <span className="text-xs font-semibold text-gray-700">Staff</span>
              </div>
              <StatusCount label="On site" value={staff.on_site ?? 0} color="text-brand-400" />
              <StatusCount label="Available" value={staff.available ?? 0} color="text-emerald-400" />
              <StatusCount label="On leave" value={staff.on_leave ?? 0} color="text-gray-400" />
            </div>

            {/* Deliveries */}
            <div className="space-y-1">
              <div className="flex items-center gap-1.5 mb-2">
                <PackageCheck className="w-3.5 h-3.5 text-gray-500" />
                <span className="text-xs font-semibold text-gray-700">Deliveries</span>
              </div>
              <StatusCount label="In transit" value={deliveries.in_transit ?? 0} color="text-violet-400" />
              <StatusCount
                label="Discrepancy"
                value={deliveries.reconciliation_discrepancy ?? 0}
                color={deliveries.reconciliation_discrepancy ? 'text-red-400' : 'text-gray-400'}
              />
              <StatusCount label="Completed" value={deliveries.completed ?? 0} color="text-emerald-400" />
            </div>
          </div>

          {/* Open disruptions */}
          {(disruptions.warning || disruptions.critical) ? (
            <div className="flex items-center justify-between pt-2 border-t border-gray-200">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                <span className="text-xs text-gray-700">
                  <span className="font-semibold text-gray-900">
                    {(disruptions.warning ?? 0) + (disruptions.critical ?? 0)}
                  </span>{' '}
                  open disruption{((disruptions.warning ?? 0) + (disruptions.critical ?? 0)) !== 1 ? 's' : ''}
                </span>
              </div>
              <button
                onClick={() => router.push('/disruptions')}
                className="flex items-center gap-1 text-xs text-amber-400 hover:text-amber-500 transition-colors"
              >
                View <ChevronRight className="w-3 h-3" />
              </button>
            </div>
          ) : null}
        </div>
      )}
    </div>
  )
}
