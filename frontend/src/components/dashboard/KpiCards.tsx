'use client'

import { useQuery } from '@tanstack/react-query'
import {
  Weight,
  ClipboardList,
  Truck,
  Shield,
  TrendingUp,
  TrendingDown,
  Minus,
  AlertTriangle,
  CheckCircle2,
  Activity,
} from 'lucide-react'
import { cn, formatWeight, formatPercent } from '@/lib/utils'
import { weighbridgeApi, jobsApi, fleetApi, complianceApi } from '@/lib/api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface KpiData {
  totalTonnageThisMonth: number
  totalTonnageLastMonth: number
  activeJobsCount: number
  activeJobsBreakdown: {
    confirmed: number
    dispatched: number
    in_progress: number
  }
  fleetUtilisation: number
  totalActiveVehicles: number
  totalVehicles: number
  complianceAlerts: number
  criticalAlerts: number
}

interface TrendProps {
  current: number
  previous: number
  unit?: string
  invertColors?: boolean
}

// ---------------------------------------------------------------------------
// Trend indicator
// ---------------------------------------------------------------------------

function TrendIndicator({ current, previous, unit = '', invertColors = false }: TrendProps) {
  if (previous === 0) return null

  const diff = current - previous
  const pct = (diff / previous) * 100
  const isUp = diff > 0
  const isNeutral = diff === 0

  let colorClass: string
  let Icon: React.ElementType

  if (isNeutral) {
    colorClass = 'text-gray-500'
    Icon = Minus
  } else if (isUp) {
    colorClass = invertColors ? 'text-red-400' : 'text-green-400'
    Icon = TrendingUp
  } else {
    colorClass = invertColors ? 'text-green-400' : 'text-red-400'
    Icon = TrendingDown
  }

  return (
    <span className={cn('flex items-center gap-0.5 text-xs font-semibold', colorClass)}>
      <Icon className="w-3.5 h-3.5" />
      {isNeutral ? (
        <span>No change</span>
      ) : (
        <span>
          {isUp ? '+' : ''}
          {pct.toFixed(1)}% vs last month
        </span>
      )}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Ring chart for fleet utilisation
// ---------------------------------------------------------------------------

function RingChart({ percent, size = 48 }: { percent: number; size?: number }) {
  const radius = (size - 8) / 2
  const circumference = 2 * Math.PI * radius
  const dash = (percent / 100) * circumference
  const gap = circumference - dash

  return (
    <svg width={size} height={size} className="-rotate-90">
      {/* Background ring */}
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        className="stroke-gray-200"
        strokeWidth={6}
      />
      {/* Progress ring */}
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke={percent >= 80 ? '#22c55e' : percent >= 50 ? '#f59e0b' : '#ef4444'}
        strokeWidth={6}
        strokeDasharray={`${dash} ${gap}`}
        strokeLinecap="round"
        className="transition-all duration-700"
      />
    </svg>
  )
}

// ---------------------------------------------------------------------------
// Individual KPI card
// ---------------------------------------------------------------------------

interface KpiCardProps {
  title: string
  value: React.ReactNode
  subtitle?: React.ReactNode
  trend?: React.ReactNode
  icon: React.ElementType
  iconBg: string
  iconColor: string
  badge?: React.ReactNode
  extra?: React.ReactNode
  loading?: boolean
}

function KpiCard({
  title,
  value,
  subtitle,
  trend,
  icon: Icon,
  iconBg,
  iconColor,
  badge,
  extra,
  loading = false,
}: KpiCardProps) {
  return (
    <div className="bg-white border border-gray-200 rounded-2xl p-5 flex flex-col gap-4 shadow-sm hover:border-gray-300 hover:shadow-md transition-all duration-200">
      {/* Header row */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1 min-w-0 flex-1">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider truncate">
            {title}
          </p>

          {loading ? (
            <div className="h-8 w-28 rounded bg-gray-200 animate-pulse mt-1" />
          ) : (
            <div className="flex items-baseline gap-2 flex-wrap mt-1">
              <span className="text-2xl font-bold text-gray-900 leading-none">
                {value}
              </span>
              {badge}
            </div>
          )}
        </div>

        {/* Icon */}
        <div
          className={cn(
            'flex-shrink-0 flex items-center justify-center w-11 h-11 rounded-xl',
            iconBg
          )}
        >
          <Icon className={cn('w-5 h-5', iconColor)} />
        </div>
      </div>

      {/* Extra content (e.g. ring chart + breakdown) */}
      {extra && !loading && (
        <div>{extra}</div>
      )}

      {/* Subtitle + trend */}
      <div className="flex flex-col gap-1 mt-auto pt-1 border-t border-gray-100">
        {loading ? (
          <div className="h-3.5 w-40 rounded bg-gray-200 animate-pulse" />
        ) : (
          <>
            {subtitle && (
              <span className="text-xs text-gray-500">{subtitle}</span>
            )}
            {trend}
          </>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Skeleton loading state
// ---------------------------------------------------------------------------

function KpiSkeleton() {
  return (
    <div className="bg-white border border-gray-200 rounded-2xl p-5 flex flex-col gap-4 overflow-hidden">
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-2 flex-1">
          <div className="h-3 w-32 rounded skeleton-shimmer" />
          <div className="h-8 w-28 rounded skeleton-shimmer mt-1" />
        </div>
        <div className="w-11 h-11 rounded-xl skeleton-shimmer flex-shrink-0" />
      </div>
      <div className="h-px bg-gray-100" />
      <div className="h-3 w-40 rounded skeleton-shimmer" />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Mock / placeholder data (used when API is unavailable)
// ---------------------------------------------------------------------------

const PLACEHOLDER_DATA: KpiData = {
  totalTonnageThisMonth: 1_847_250,
  totalTonnageLastMonth: 1_612_000,
  activeJobsCount: 34,
  activeJobsBreakdown: {
    confirmed: 12,
    dispatched: 8,
    in_progress: 14,
  },
  fleetUtilisation: 73,
  totalActiveVehicles: 16,
  totalVehicles: 22,
  complianceAlerts: 7,
  criticalAlerts: 2,
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function KpiCards() {
  // ── Fetch tonnage stats ─────────────────────────────────────────────────
  const { data: tonnageData, isLoading: tonnageLoading } = useQuery({
    queryKey: ['kpi', 'tonnage'],
    queryFn: async () => {
      try {
        return await weighbridgeApi.getTonnageStats({ period: 'monthly' })
      } catch {
        return null
      }
    },
    staleTime: 5 * 60_000,
    refetchInterval: 10 * 60_000,
  })

  // ── Fetch job status counts ─────────────────────────────────────────────
  const { data: jobCounts, isLoading: jobsLoading } = useQuery({
    queryKey: ['kpi', 'jobs'],
    queryFn: async () => {
      try {
        return await jobsApi.getStatusCounts()
      } catch {
        return null
      }
    },
    staleTime: 60_000,
    refetchInterval: 60_000,
  })

  // ── Fetch fleet stats ───────────────────────────────────────────────────
  const { data: fleetData, isLoading: fleetLoading } = useQuery({
    queryKey: ['kpi', 'fleet'],
    queryFn: async () => {
      try {
        return await fleetApi.getFleetStats()
      } catch {
        return null
      }
    },
    staleTime: 30_000,
    refetchInterval: 60_000,
  })

  // ── Fetch compliance summary ────────────────────────────────────────────
  const { data: complianceData, isLoading: complianceLoading } = useQuery({
    queryKey: ['kpi', 'compliance'],
    queryFn: async () => {
      try {
        return await complianceApi.getComplianceSummary()
      } catch {
        return null
      }
    },
    staleTime: 5 * 60_000,
    refetchInterval: 10 * 60_000,
  })

  // ── Derive values (fall back to placeholder) ────────────────────────────

  const tonnageThisMonth =
    (tonnageData as Record<string, number> | null)?.current_month_kg ??
    PLACEHOLDER_DATA.totalTonnageThisMonth

  const tonnageLastMonth =
    (tonnageData as Record<string, number> | null)?.last_month_kg ??
    PLACEHOLDER_DATA.totalTonnageLastMonth

  const activeJobs =
    jobCounts != null
      ? ((jobCounts as Record<string, number>).confirmed ?? 0) +
        ((jobCounts as Record<string, number>).dispatched ?? 0) +
        ((jobCounts as Record<string, number>).in_progress ?? 0)
      : PLACEHOLDER_DATA.activeJobsCount

  const jobBreakdown = {
    confirmed:
      (jobCounts as Record<string, number> | null)?.confirmed ??
      PLACEHOLDER_DATA.activeJobsBreakdown.confirmed,
    dispatched:
      (jobCounts as Record<string, number> | null)?.dispatched ??
      PLACEHOLDER_DATA.activeJobsBreakdown.dispatched,
    in_progress:
      (jobCounts as Record<string, number> | null)?.in_progress ??
      PLACEHOLDER_DATA.activeJobsBreakdown.in_progress,
  }

  const utilisationPct =
    (fleetData as Record<string, number> | null)?.utilisation_rate_percent ??
    PLACEHOLDER_DATA.fleetUtilisation

  const onTripCount =
    (fleetData as Record<string, number> | null)?.on_trip ??
    PLACEHOLDER_DATA.totalActiveVehicles

  const totalVehicles =
    (fleetData as Record<string, number> | null)?.total_vehicles ??
    PLACEHOLDER_DATA.totalVehicles

  const complianceAlerts =
    (complianceData as Record<string, number> | null)?.overdue_count ??
    PLACEHOLDER_DATA.complianceAlerts

  const criticalAlerts =
    (complianceData as Record<string, number> | null)?.upcoming_deadlines_7_days ??
    PLACEHOLDER_DATA.criticalAlerts

  const isLoading =
    tonnageLoading || jobsLoading || fleetLoading || complianceLoading

  // ---------------------------------------------------------------------------
  // Cards config
  // ---------------------------------------------------------------------------

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
      {/* ── Card 1: Total Tonnage ──────────────────────────────────────────── */}
      {isLoading ? (
        <KpiSkeleton />
      ) : (
        <KpiCard
          title="Total Tonnage This Month"
          icon={Weight}
          iconBg="bg-green-50 border border-green-200"
          iconColor="text-green-400"
          value={formatWeight(tonnageThisMonth)}
          subtitle="Gross weight processed"
          trend={
            <TrendIndicator
              current={tonnageThisMonth}
              previous={tonnageLastMonth}
            />
          }
        />
      )}

      {/* ── Card 2: Active Jobs ─────────────────────────────────────────────── */}
      {isLoading ? (
        <KpiSkeleton />
      ) : (
        <KpiCard
          title="Active Jobs"
          icon={ClipboardList}
          iconBg="bg-brand-50 border border-brand-200"
          iconColor="text-brand-400"
          value={activeJobs.toString()}
          subtitle="Confirmed · Dispatched · In Progress"
          trend={
            <span className="flex items-center gap-3 flex-wrap">
              <span className="flex items-center gap-1 text-xs text-brand-400">
                <span className="w-2 h-2 rounded-full bg-brand-400 inline-block" />
                {jobBreakdown.confirmed} confirmed
              </span>
              <span className="flex items-center gap-1 text-xs text-violet-400">
                <span className="w-2 h-2 rounded-full bg-violet-400 inline-block" />
                {jobBreakdown.dispatched} dispatched
              </span>
              <span className="flex items-center gap-1 text-xs text-amber-400">
                <span className="w-2 h-2 rounded-full bg-amber-400 inline-block" />
                {jobBreakdown.in_progress} in progress
              </span>
            </span>
          }
          badge={
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-brand-50 text-brand-600 border border-brand-200">
              <Activity className="w-2.5 h-2.5" />
              Live
            </span>
          }
        />
      )}

      {/* ── Card 3: Fleet Utilisation ──────────────────────────────────────── */}
      {isLoading ? (
        <KpiSkeleton />
      ) : (
        <KpiCard
          title="Fleet Utilisation"
          icon={Truck}
          iconBg="bg-amber-50 border border-amber-200"
          iconColor="text-amber-400"
          value={formatPercent(utilisationPct)}
          subtitle={`${onTripCount} of ${totalVehicles} vehicles active`}
          trend={
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  'text-xs font-semibold',
                  utilisationPct >= 80
                    ? 'text-green-400'
                    : utilisationPct >= 50
                    ? 'text-amber-400'
                    : 'text-red-400'
                )}
              >
                {utilisationPct >= 80
                  ? '● High utilisation'
                  : utilisationPct >= 50
                  ? '● Moderate utilisation'
                  : '● Low utilisation'}
              </span>
            </div>
          }
          extra={
            <div className="flex items-center gap-4">
              <RingChart percent={utilisationPct} size={52} />
              <div className="flex flex-col gap-1.5 text-xs">
                <span className="flex items-center gap-2 text-green-400">
                  <span className="w-2 h-2 rounded-full bg-green-400" />
                  {(fleetData as Record<string, number> | null)?.available ?? 4} available
                </span>
                <span className="flex items-center gap-2 text-brand-400">
                  <span className="w-2 h-2 rounded-full bg-brand-400" />
                  {onTripCount} on trip
                </span>
                <span className="flex items-center gap-2 text-amber-400">
                  <span className="w-2 h-2 rounded-full bg-amber-400" />
                  {(fleetData as Record<string, number> | null)?.maintenance ?? 2} maintenance
                </span>
              </div>
            </div>
          }
        />
      )}

      {/* ── Card 4: Compliance Alerts ──────────────────────────────────────── */}
      {isLoading ? (
        <KpiSkeleton />
      ) : (
        <KpiCard
          title="Compliance Alerts"
          icon={Shield}
          iconBg={
            criticalAlerts > 0
              ? 'bg-red-50 border border-red-200'
              : 'bg-green-50 border border-green-200'
          }
          iconColor={criticalAlerts > 0 ? 'text-red-400' : 'text-green-400'}
          value={complianceAlerts.toString()}
          subtitle="Overdue SW batches"
          badge={
            criticalAlerts > 0 ? (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-red-50 text-red-600 border border-red-200">
                <AlertTriangle className="w-2.5 h-2.5" />
                {criticalAlerts} due in 7 days
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-green-50 text-green-600 border border-green-200">
                <CheckCircle2 className="w-2.5 h-2.5" />
                On track
              </span>
            )
          }
          trend={
            complianceAlerts > 0 ? (
              <span className="text-xs text-red-400 flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" />
                Immediate action required for overdue items
              </span>
            ) : (
              <span className="text-xs text-green-400 flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3" />
                All batches within disposal timeline
              </span>
            )
          }
        />
      )}
    </div>
  )
}
