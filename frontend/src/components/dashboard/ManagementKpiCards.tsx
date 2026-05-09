'use client'

import { useQuery } from '@tanstack/react-query'
import {
  DollarSign,
  AlertCircle,
  TrendingUp,
  TrendingDown,
  Minus,
  Wrench,
  Users,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { financeApi, fleetApi, clientsApi } from '@/lib/api'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatMYR(value: number): string {
  if (value >= 1_000_000) return `RM ${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `RM ${(value / 1_000).toFixed(1)}K`
  return `RM ${value.toLocaleString('en-MY', { minimumFractionDigits: 0 })}`
}

function TrendBadge({ current, previous }: { current: number; previous: number }) {
  if (!previous) return null
  const pct = ((current - previous) / previous) * 100
  const up = pct > 0
  const neutral = pct === 0
  const Icon = neutral ? Minus : up ? TrendingUp : TrendingDown
  const color = neutral ? 'text-gray-500' : up ? 'text-green-600' : 'text-red-500'
  return (
    <span className={cn('flex items-center gap-0.5 text-xs font-semibold', color)}>
      <Icon className="w-3 h-3" />
      {neutral ? 'No change' : `${up ? '+' : ''}${pct.toFixed(1)}% vs last month`}
    </span>
  )
}

function Skeleton() {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4 animate-pulse flex flex-col gap-3">
      <div className="flex items-start justify-between">
        <div className="space-y-2 flex-1">
          <div className="h-3 w-28 bg-gray-200 rounded" />
          <div className="h-7 w-24 bg-gray-200 rounded" />
        </div>
        <div className="w-10 h-10 bg-gray-200 rounded-xl" />
      </div>
      <div className="h-px bg-gray-100" />
      <div className="h-3 w-36 bg-gray-200 rounded" />
    </div>
  )
}

interface CardProps {
  title: string
  value: string
  subtitle: string
  trend?: React.ReactNode
  icon: React.ElementType
  iconBg: string
  iconColor: string
  alert?: boolean
}

function MgmtCard({ title, value, subtitle, trend, icon: Icon, iconBg, iconColor, alert }: CardProps) {
  return (
    <div className={cn(
      'bg-white border rounded-xl p-4 flex flex-col gap-3 hover:border-gray-300 transition-colors',
      alert ? 'border-red-200' : 'border-gray-200'
    )}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1 min-w-0 flex-1">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider truncate">{title}</p>
          <p className={cn('text-2xl font-bold leading-none mt-1', alert ? 'text-red-600' : 'text-gray-900')}>
            {value}
          </p>
        </div>
        <div className={cn('flex-shrink-0 flex items-center justify-center w-10 h-10 rounded-xl', iconBg)}>
          <Icon className={cn('w-5 h-5', iconColor)} />
        </div>
      </div>
      <div className="border-t border-gray-100 pt-2 flex flex-col gap-1">
        <span className="text-xs text-gray-500">{subtitle}</span>
        {trend}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component — only rendered for management/admin roles
// ---------------------------------------------------------------------------

export default function ManagementKpiCards() {
  const now = new Date()
  const thisMonthStart = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().split('T')[0]
  const thisMonthEnd = new Date(now.getFullYear(), now.getMonth() + 1, 0).toISOString().split('T')[0]
  const lastMonthStart = new Date(now.getFullYear(), now.getMonth() - 1, 1).toISOString().split('T')[0]
  const lastMonthEnd = new Date(now.getFullYear(), now.getMonth(), 0).toISOString().split('T')[0]

  const { data: revenueThis, isLoading: r1Loading } = useQuery({
    queryKey: ['mgmt-kpi', 'revenue-this'],
    queryFn: () => financeApi.getRevenueStats({ period_start: thisMonthStart, period_end: thisMonthEnd }),
    staleTime: 5 * 60_000,
  })

  const { data: revenueLast, isLoading: r2Loading } = useQuery({
    queryKey: ['mgmt-kpi', 'revenue-last'],
    queryFn: () => financeApi.getRevenueStats({ period_start: lastMonthStart, period_end: lastMonthEnd }),
    staleTime: 5 * 60_000,
  })

  const { data: ageing, isLoading: ageingLoading } = useQuery({
    queryKey: ['mgmt-kpi', 'ageing'],
    queryFn: () => financeApi.getReceivablesAgeing(),
    staleTime: 5 * 60_000,
  })

  const { data: maintenanceDue, isLoading: maintLoading } = useQuery({
    queryKey: ['mgmt-kpi', 'maintenance-due'],
    queryFn: () => fleetApi.getMaintenanceDue(),
    staleTime: 10 * 60_000,
  })

  const { data: clientsData, isLoading: clientsLoading } = useQuery({
    queryKey: ['mgmt-kpi', 'clients'],
    queryFn: () => clientsApi.list({ limit: 1 } as Parameters<typeof clientsApi.list>[0]),
    staleTime: 10 * 60_000,
  })

  const isLoading = r1Loading || r2Loading || ageingLoading || maintLoading || clientsLoading

  const thisRevenue = Number((revenueThis as Record<string, unknown>)?.total_revenue_myr ?? 0)
  const lastRevenue = Number((revenueLast as Record<string, unknown>)?.total_revenue_myr ?? 0)

  const overdueAmount = Number((ageing as Record<string, unknown>)?.overdue_total_myr ?? 0)
  const overdueCount = Number((ageing as Record<string, unknown>)?.overdue_count ?? 0)

  const maintCount = Array.isArray(maintenanceDue) ? maintenanceDue.length : 0

  const totalClients = Number(
    (clientsData as { total?: number } | null)?.total ??
    (clientsData as { count?: number } | null)?.count ?? 0
  )

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} />)}
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
      {/* Revenue this month */}
      <MgmtCard
        title="Revenue This Month"
        value={formatMYR(thisRevenue)}
        subtitle="Invoiced & collected"
        icon={DollarSign}
        iconBg="bg-emerald-50 border border-emerald-200"
        iconColor="text-emerald-500"
        trend={<TrendBadge current={thisRevenue} previous={lastRevenue} />}
      />

      {/* Overdue invoices */}
      <MgmtCard
        title="Overdue Invoices"
        value={overdueCount > 0 ? `${overdueCount} invoices` : 'None'}
        subtitle={overdueCount > 0 ? `${formatMYR(overdueAmount)} outstanding` : 'All invoices current'}
        icon={AlertCircle}
        iconBg={overdueCount > 0 ? 'bg-red-50 border border-red-200' : 'bg-green-50 border border-green-200'}
        iconColor={overdueCount > 0 ? 'text-red-500' : 'text-green-500'}
        alert={overdueCount > 0}
      />

      {/* Vehicles due for maintenance */}
      <MgmtCard
        title="Maintenance Due"
        value={maintCount > 0 ? `${maintCount} vehicles` : 'All clear'}
        subtitle={maintCount > 0 ? 'Service overdue or due within 14 days' : 'No vehicles due for service'}
        icon={Wrench}
        iconBg={maintCount > 0 ? 'bg-amber-50 border border-amber-200' : 'bg-green-50 border border-green-200'}
        iconColor={maintCount > 0 ? 'text-amber-500' : 'text-green-500'}
        alert={maintCount > 3}
      />

      {/* Active clients */}
      <MgmtCard
        title="Active Clients"
        value={totalClients > 0 ? totalClients.toString() : '—'}
        subtitle="Registered client accounts"
        icon={Users}
        iconBg="bg-brand-50 border border-brand-200"
        iconColor="text-brand-500"
      />
    </div>
  )
}
