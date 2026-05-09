'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Leaf, TrendingDown, TrendingUp, Recycle, Zap, RefreshCw,
} from 'lucide-react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar, Legend,
} from 'recharts'
import { toast } from 'sonner'
import { esgApi } from '@/lib/api'
import { formatCarbon, formatWeight, formatPercent, cn } from '@/lib/utils'
import DownloadPdfButton from '@/components/shared/DownloadPdfButton'

export default function ESGPage() {
  const [generatedReports, setGeneratedReports] = useState<{ jobId: string; generatedAt: string }[]>([])

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['esg', 'company-dashboard'],
    queryFn: () => esgApi.getCompanyDashboard(),
    staleTime: 10 * 60_000,
  })

  const dashboard = data as Record<string, unknown> | null

  const kpis = [
    {
      label: 'Total CO₂ Saved',
      value: formatCarbon(dashboard?.total_co2_saved_kgco2e as number),
      icon: Leaf,
      color: 'text-green-400',
      bg: 'bg-green-50 border-green-200',
      desc: 'Net carbon benefit this period',
    },
    {
      label: 'Waste Processed',
      value: formatWeight(dashboard?.total_waste_processed_kg as number),
      icon: Recycle,
      color: 'text-brand-400',
      bg: 'bg-brand-50 border-brand-200',
      desc: 'Total net weight collected',
    },
    {
      label: 'Diversion Rate',
      value: formatPercent(dashboard?.overall_diversion_rate_pct as number),
      icon: TrendingUp,
      color: 'text-emerald-400',
      bg: 'bg-emerald-50 border-emerald-200',
      desc: 'Recyclable / total waste',
    },
    {
      label: 'Transport Emissions',
      value: formatCarbon(dashboard?.total_transport_emissions_kgco2e as number),
      icon: Zap,
      color: 'text-amber-400',
      bg: 'bg-amber-50 border-amber-200',
      desc: 'Fleet CO₂e this period',
    },
  ]

  const monthlyTrend = (dashboard?.monthly_co2_trend as Record<string, unknown>[] | undefined) ?? []
  const topClients = (dashboard?.top_clients_by_co2_saved as Record<string, unknown>[] | undefined) ?? []
  const sdgTags = (dashboard?.sdg_tags as string[] | undefined) ?? []

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">ESG & Carbon</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Company-wide sustainability performance
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={async () => {
              try {
                const result = await esgApi.generateReport({ period: 'monthly' })
                const jobId = (result as Record<string, string>).job_id ?? (result as Record<string, string>).id
                if (jobId) {
                  setGeneratedReports(prev => [...prev, { jobId, generatedAt: new Date().toISOString() }])
                  toast.success('ESG report generated')
                }
              } catch {
                toast.error('Failed to generate ESG report')
              }
            }}
            className="flex items-center gap-1.5 px-3 py-2 text-xs text-white bg-green-600 hover:bg-green-500 rounded-lg transition-colors"
          >
            Generate Report
          </button>
          <button
            onClick={() => refetch()}
            className="flex items-center gap-1.5 px-3 py-2 text-xs text-gray-500 hover:text-gray-900 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </button>
        </div>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {kpis.map((kpi) => (
          <div key={kpi.label} className={cn('flex items-center gap-4 p-4 rounded-xl border bg-white', kpi.bg)}>
            <div className={cn('w-11 h-11 rounded-xl flex items-center justify-center border flex-shrink-0', kpi.bg)}>
              <kpi.icon className={cn('w-5 h-5', kpi.color)} />
            </div>
            <div>
              <p className="text-xs text-gray-400 font-semibold uppercase tracking-wider">{kpi.label}</p>
              {isLoading
                ? <div className="h-6 w-24 rounded bg-gray-200 animate-pulse mt-1" />
                : <p className={cn('text-xl font-bold mt-0.5', kpi.color)}>{kpi.value}</p>
              }
              <p className="text-[11px] text-gray-400 mt-0.5">{kpi.desc}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Monthly CO₂ trend */}
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">Monthly CO₂ Impact</h3>
          {isLoading ? (
            <div className="h-48 rounded bg-gray-200 animate-pulse" />
          ) : monthlyTrend.length === 0 ? (
            <div className="h-48 flex items-center justify-center text-gray-400 text-sm">No data yet</div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={monthlyTrend} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="savingsGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#22c55e" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
                <XAxis dataKey="period" tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={false} width={40} />
                <Tooltip contentStyle={{ background: '#ffffff', border: '1px solid #e5e7eb', borderRadius: 8, fontSize: 12, color: '#111827' }} />
                <Area type="monotone" dataKey="savings_kgco2e" name="CO₂ Saved" stroke="#22c55e" strokeWidth={2} fill="url(#savingsGrad)" dot={false} />
                <Area type="monotone" dataKey="transport_kgco2e" name="Transport" stroke="#f59e0b" strokeWidth={1.5} strokeDasharray="4 2" fill="none" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Top clients */}
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">Top Clients by CO₂ Saved</h3>
          {isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="h-8 rounded bg-gray-200 animate-pulse" />
              ))}
            </div>
          ) : topClients.length === 0 ? (
            <div className="h-48 flex items-center justify-center text-gray-400 text-sm">No data yet</div>
          ) : (
            <div className="space-y-3">
              {topClients.map((c, i) => {
                const saved = Number(c.co2_saved_kgco2e ?? 0)
                const max = Number((topClients[0] as Record<string, unknown>).co2_saved_kgco2e ?? 1)
                const pct = max > 0 ? (saved / max) * 100 : 0
                return (
                  <div key={String(c.client_id)} className="flex items-center gap-3">
                    <span className="text-xs text-gray-400 w-4 text-right">{i + 1}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-gray-900 truncate">{String(c.company_name)}</span>
                        <span className="text-xs text-green-400 font-semibold ml-2 flex-shrink-0">{formatCarbon(saved)}</span>
                      </div>
                      <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
                        <div className="h-full bg-green-500 rounded-full transition-all" style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>

      {/* SDG tags */}
      {sdgTags.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">UN SDG Alignment</h3>
          <div className="flex flex-wrap gap-2">
            {sdgTags.map((tag) => (
              <span key={tag} className="px-3 py-1.5 rounded-full text-xs font-semibold bg-green-50 text-green-700 border border-green-200">
                {tag}
              </span>
            ))}
          </div>
        </div>
      )}

      {generatedReports.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">Generated Reports</h3>
          <div className="flex flex-col gap-2">
            {generatedReports.map((report) => (
              <div key={report.jobId} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-200">
                <div>
                  <p className="text-xs font-mono text-gray-700">{report.jobId}</p>
                  <p className="text-[11px] text-gray-400 mt-0.5">Generated {new Date(report.generatedAt).toLocaleString()}</p>
                </div>
                <DownloadPdfButton
                  label="Download Report"
                  onDownload={() => esgApi.downloadReport(report.jobId)}
                  filename={`esg-report-${report.jobId}.pdf`}
                />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
