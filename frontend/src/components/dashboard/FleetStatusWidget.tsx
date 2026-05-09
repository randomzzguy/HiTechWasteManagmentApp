'use client'

import { useQuery } from '@tanstack/react-query'
import { Truck, Wrench, CheckCircle2, XCircle, ExternalLink, AlertTriangle } from 'lucide-react'
import Link from 'next/link'
import { cn } from '@/lib/utils'
import { fleetApi } from '@/lib/api'
import type { FleetStats } from '@/types/vehicle'

// ---------------------------------------------------------------------------
// Placeholder data
// ---------------------------------------------------------------------------

const PLACEHOLDER: FleetStats = {
  total_vehicles: 22,
  available: 4,
  on_trip: 16,
  maintenance: 2,
  breakdown: 0,
  retired: 0,
  utilisation_rate_percent: 73,
  total_distance_today_km: 842,
  total_trips_today: 18,
  maintenance_due_7_days: 3,
}

// ---------------------------------------------------------------------------
// Status card config
// ---------------------------------------------------------------------------

interface StatusCardConfig {
  key: keyof FleetStats
  label: string
  icon: React.ElementType
  iconBg: string
  iconColor: string
  textColor: string
  borderColor: string
  bgColor: string
}

const STATUS_CARDS: StatusCardConfig[] = [
  {
    key: 'available',
    label: 'Available',
    icon: CheckCircle2,
    iconBg: 'bg-green-50',
    iconColor: 'text-green-400',
    textColor: 'text-green-600',
    borderColor: 'border-green-200',
    bgColor: 'bg-green-50',
  },
  {
    key: 'on_trip',
    label: 'On Trip',
    icon: Truck,
    iconBg: 'bg-brand-50',
    iconColor: 'text-brand-400',
    textColor: 'text-brand-600',
    borderColor: 'border-brand-200',
    bgColor: 'bg-brand-50',
  },
  {
    key: 'maintenance',
    label: 'Maintenance',
    icon: Wrench,
    iconBg: 'bg-amber-50',
    iconColor: 'text-amber-400',
    textColor: 'text-amber-600',
    borderColor: 'border-amber-200',
    bgColor: 'bg-amber-50',
  },
  {
    key: 'retired',
    label: 'Retired',
    icon: XCircle,
    iconBg: 'bg-gray-100',
    iconColor: 'text-gray-400',
    textColor: 'text-gray-500',
    borderColor: 'border-gray-200',
    bgColor: 'bg-gray-50',
  },
]

// ---------------------------------------------------------------------------
// Individual status card
// ---------------------------------------------------------------------------

interface StatusCardProps {
  config: StatusCardConfig
  count: number
  loading?: boolean
}

function StatusCard({ config, count, loading }: StatusCardProps) {
  const Icon = config.icon

  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-2 p-4 rounded-xl border transition-all duration-200',
        'hover:scale-[1.02] hover:shadow-lg hover:shadow-black/10',
        config.bgColor,
        config.borderColor
      )}
    >
      {/* Icon */}
      <div
        className={cn(
          'flex items-center justify-center w-9 h-9 rounded-lg',
          config.iconBg
        )}
      >
        <Icon className={cn('w-4 h-4', config.iconColor)} />
      </div>

      {/* Count */}
      {loading ? (
        <div className="h-7 w-10 rounded bg-gray-200 animate-pulse" />
      ) : (
        <span className={cn('text-2xl font-bold leading-none', config.textColor)}>
          {count}
        </span>
      )}

      {/* Label */}
      <span className="text-xs font-medium text-gray-500 text-center leading-tight">
        {config.label}
      </span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Breakdown bar
// ---------------------------------------------------------------------------

interface BreakdownBarProps {
  stats: FleetStats
}

function BreakdownBar({ stats }: BreakdownBarProps) {
  const active = stats.total_vehicles - stats.retired
  if (active === 0) return null

  const segments = [
    { count: stats.on_trip,      color: 'bg-brand-500',   label: 'On Trip' },
    { count: stats.available,    color: 'bg-green-500',  label: 'Available' },
    { count: stats.maintenance,  color: 'bg-amber-500',  label: 'Maintenance' },
    { count: stats.breakdown,    color: 'bg-red-500',    label: 'Breakdown' },
  ].filter((s) => s.count > 0)

  return (
    <div className="mt-4 px-1">
      {/* Label */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] text-gray-400 uppercase tracking-wider font-semibold">
          Fleet breakdown
        </span>
        <span className="text-[11px] text-gray-500">
          {active} active vehicles
        </span>
      </div>

      {/* Stacked bar */}
      <div className="flex h-2.5 rounded-full overflow-hidden gap-0.5">
        {segments.map((seg) => (
          <div
            key={seg.label}
            className={cn('rounded-full transition-all duration-700', seg.color)}
            style={{ flex: seg.count }}
            title={`${seg.label}: ${seg.count}`}
          />
        ))}
      </div>

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2">
        {segments.map((seg) => (
          <span key={seg.label} className="flex items-center gap-1.5 text-[11px] text-gray-500">
            <span className={cn('w-2 h-2 rounded-full inline-block', seg.color)} />
            {seg.count} {seg.label}
          </span>
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------

function Skeleton() {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5 animate-pulse">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-gray-200" />
          <div className="flex flex-col gap-1.5">
            <div className="h-4 w-32 rounded bg-gray-200" />
            <div className="h-3 w-24 rounded bg-gray-200" />
          </div>
        </div>
        <div className="h-4 w-16 rounded bg-gray-200" />
      </div>
      <div className="grid grid-cols-4 gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-28 rounded-xl bg-gray-200" />
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function FleetStatusWidget() {
  const { data: rawStats, isLoading } = useQuery({
    queryKey: ['fleet-stats-widget'],
    queryFn: async () => {
      try {
        return await fleetApi.getFleetStats() as unknown as FleetStats
      } catch {
        return null
      }
    },
    staleTime: 30_000,
    refetchInterval: 60_000,
  })

  const { data: maintenanceDue } = useQuery({
    queryKey: ['maintenance-due-widget'],
    queryFn: async () => {
      try {
        const result = await fleetApi.getMaintenanceDue()
        return result as Record<string, unknown>[]
      } catch {
        return null
      }
    },
    staleTime: 5 * 60_000,
  })

  if (isLoading) return <Skeleton />

  const stats: FleetStats = rawStats ?? PLACEHOLDER
  const dueCount = maintenanceDue?.length ?? stats.maintenance_due_7_days

  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between gap-4 px-5 pt-5 pb-4 border-b border-gray-100">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-amber-50 border border-amber-200">
            <Truck className="w-4 h-4 text-amber-400" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-gray-900">Fleet Status</h3>
            <p className="text-xs text-gray-400 mt-0.5">
              {stats.total_vehicles} vehicles · {stats.total_trips_today} trips today
            </p>
          </div>
        </div>

        <Link
          href="/fleet"
          className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-900 transition-colors"
        >
          View fleet
          <ExternalLink className="w-3 h-3" />
        </Link>
      </div>

      {/* Content */}
      <div className="p-5">
        {/* Status grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {STATUS_CARDS.map((cfg) => (
            <StatusCard
              key={cfg.key}
              config={cfg}
              count={(stats[cfg.key] as number) ?? 0}
              loading={isLoading}
            />
          ))}
        </div>

        {/* Breakdown bar */}
        <BreakdownBar stats={stats} />

        {/* Stats row */}
        <div className="mt-4 pt-4 border-t border-gray-100 grid grid-cols-3 gap-4">
          {/* Utilisation */}
          <div className="flex flex-col gap-0.5">
            <span className="text-[11px] text-gray-400 uppercase tracking-wider font-semibold">
              Utilisation
            </span>
            <span
              className={cn(
                'text-lg font-bold leading-none',
                stats.utilisation_rate_percent >= 80
                  ? 'text-green-400'
                  : stats.utilisation_rate_percent >= 50
                  ? 'text-amber-400'
                  : 'text-red-400'
              )}
            >
              {stats.utilisation_rate_percent}%
            </span>
          </div>

          {/* Distance today */}
          <div className="flex flex-col gap-0.5">
            <span className="text-[11px] text-gray-400 uppercase tracking-wider font-semibold">
              Distance Today
            </span>
            <span className="text-lg font-bold leading-none text-gray-900">
              {stats.total_distance_today_km.toLocaleString()} km
            </span>
          </div>

          {/* Maintenance due */}
          <div className="flex flex-col gap-0.5">
            <span className="text-[11px] text-gray-400 uppercase tracking-wider font-semibold">
              Maint. Due (7d)
            </span>
            <div className="flex items-center gap-1.5">
              {dueCount > 0 && (
                <AlertTriangle className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" />
              )}
              <span
                className={cn(
                  'text-lg font-bold leading-none',
                  dueCount > 0 ? 'text-amber-400' : 'text-green-400'
                )}
              >
                {dueCount}
              </span>
            </div>
          </div>
        </div>

        {/* Breakdown alert */}
        {stats.breakdown > 0 && (
          <div className="mt-4 flex items-center gap-2.5 px-3 py-2.5 bg-red-50 border border-red-200 rounded-lg">
            <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0" />
            <p className="text-xs text-red-600">
              <span className="font-semibold">{stats.breakdown} vehicle{stats.breakdown !== 1 ? 's' : ''}</span>{' '}
              currently in breakdown. Immediate attention required.
            </p>
            <Link
              href="/fleet"
              className="ml-auto flex-shrink-0 text-xs text-red-500 hover:text-red-600 font-medium transition-colors"
            >
              View →
            </Link>
          </div>
        )}

        {/* Placeholder note */}
        {!rawStats && (
          <p className="mt-3 text-center text-[11px] text-gray-400 italic">
            Sample data — connect to backend for live status
          </p>
        )}
      </div>
    </div>
  )
}
