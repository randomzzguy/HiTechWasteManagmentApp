'use client'

import { useQuery } from '@tanstack/react-query'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar, Cell,
} from 'recharts'
import { Leaf, TrendingDown, TrendingUp, Zap, Recycle } from 'lucide-react'
import { esgApi } from '@/lib/api'
import { formatCarbon, formatWeight, formatPercent, cn } from '@/lib/utils'
import DiversionGauge from './DiversionGauge'
import SdgAlignmentBadges from './SdgAlignmentBadges'

interface CarbonDashboardProps {
  clientId?: string
}

export default function CarbonDashboard({ clientId }: CarbonDashboardProps) {
  const { data, isLoading } = useQuery({
    queryKey: ['esg-dashboard', clientId ?? 'company'],
    queryFn: () => clientId
      ? esgApi.getClientDashboard(clientId)
      : esgApi.getCompanyDashboard(),
    staleTime: 10 * 60_000,
  })

  const d = data as Record<string, unknown> | null

  const kpis = [
    {
      label: 'CO₂ Saved',
      value: formatCarbon(d?.total_co2_saved_kgco2e as number),
      icon: Leaf,
      color: 'text-green-400',
      bg: 'bg-green-900/20 border-green-800/30',
      desc: 'Net carbon benefit',
    },
    {
      label: 'Transport Emissions',
      value: formatCarbon(d?.total_transport_emissions_kgco2e as number),
      icon: Zap,
      color: 'text-amber-400',
      bg: 'bg-amber-900/20 border-amber-800/30',
      desc: 'Fleet CO₂e',
    },
    {
      label: 'Landfill Avoided',
      value: formatCarbon(d?.total_landfill_avoidance_kgco2e as number),
      icon: TrendingDown,
      color: 'text-brand-400',
      bg: 'bg-brand-900/20 border-brand-800/30',
      desc: 'Methane credit',
    },
    {
      label: 'Recycling Credit',
      value: formatCarbon(d?.total_recycling_credit_kgco2e as number),
      icon: Recycle,
      color: 'text-brand-400',
      bg: 'bg-brand-900/20 border-brand-800/30',
      desc: 'Material savings',
    },
  ]

  const monthlyTrend = (d?.monthly_co2_trend as Record<string, unknown>[] | undefined) ?? []
  const diversionHistory = (d?.diversion_rate_history as Record<string, unknown>[] | undefined) ?? []
  const recyclingBreakdown = (d?.recycling_breakdown as { material: string; total_kg: number }[] | undefined) ?? []
  const sdgTags = (d?.sdg_tags as string[] | undefined) ?? []
  const diversionRate = d?.diversion_rate_pct as number | undefined
  const diversionTarget = 70 // default target

  const MATERIAL_COLORS: Record<string, string> = {
    paper: '#fbbf24', pet: '#60a5fa', hdpe: '#34d399',
    aluminium: '#94a3b8', ferrous: '#f97316', glass: '#a78bfa', ewaste: '#f472b6',
  }

  if (isLoading) return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="h-24 rounded-xl bg-gray-100 animate-pulse" />
      ))}
    </div>
  )

  return (
    <div className="flex flex-col gap-6">
      {/* KPI cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {kpis.map(kpi => (
          <div key={kpi.label} className={cn('flex items-center gap-3 p-4 rounded-xl border bg-white', kpi.bg)}>
            <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center border flex-shrink-0', kpi.bg)}>
              <kpi.icon className={cn('w-5 h-5', kpi.color)} />
            </div>
            <div>
              <p className="text-xs text-gray-400 font-semibold uppercase tracking-wider">{kpi.label}</p>
              <p className={cn('text-lg font-bold mt-0.5', kpi.color)}>{kpi.value}</p>
              <p className="text-[10px] text-gray-400">{kpi.desc}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Diversion gauge */}
        {diversionRate !== undefined && (
          <div className="bg-white border border-gray-200 rounded-xl p-5 flex flex-col items-center justify-center">
            <DiversionGauge rate={diversionRate} target={diversionTarget} size={180} />
          </div>
        )}

        {/* Monthly CO₂ trend */}
        <div className={cn('bg-white border border-gray-200 rounded-xl p-5', diversionRate !== undefined ? 'xl:col-span-2' : 'xl:col-span-3')}>
          <h3 className="text-sm font-semibold text-gray-900 mb-4">Monthly CO₂ Impact</h3>
          {monthlyTrend.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <AreaChart data={monthlyTrend} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="co2Grad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#22c55e" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
                <XAxis dataKey="period" tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={false} width={40} />
                <Tooltip contentStyle={{ background: '#ffffff', border: '1px solid #e5e7eb', borderRadius: 8, fontSize: 12 }} />
                <Area type="monotone" dataKey="savings_kgco2e" name="CO₂ Saved" stroke="#22c55e" strokeWidth={2} fill="url(#co2Grad)" dot={false} />
                <Area type="monotone" dataKey="transport_kgco2e" name="Transport" stroke="#f59e0b" strokeWidth={1.5} strokeDasharray="4 2" fill="none" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-44 flex items-center justify-center text-gray-400 text-sm">No trend data yet</div>
          )}
        </div>
      </div>

      {/* Recycling breakdown + SDG */}
      {(recyclingBreakdown.length > 0 || sdgTags.length > 0) && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          {recyclingBreakdown.length > 0 && (
            <div className="bg-white border border-gray-200 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-gray-900 mb-4">Recycling by Material</h3>
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={recyclingBreakdown} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
                  <XAxis dataKey="material" tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={false} width={40} />
                  <Tooltip contentStyle={{ background: '#ffffff', border: '1px solid #e5e7eb', borderRadius: 8, fontSize: 12 }} />
                  <Bar dataKey="total_kg" name="kg" radius={[4, 4, 0, 0]}>
                    {recyclingBreakdown.map((entry, i) => (
                      <Cell key={i} fill={MATERIAL_COLORS[entry.material] ?? '#64748b'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {sdgTags.length > 0 && (
            <div className="bg-white border border-gray-200 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-gray-900 mb-4">UN SDG Alignment</h3>
              <SdgAlignmentBadges tags={sdgTags} size="md" />
            </div>
          )}
        </div>
      )}
    </div>
  )
}

