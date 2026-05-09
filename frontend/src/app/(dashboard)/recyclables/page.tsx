'use client'

import { useQuery } from '@tanstack/react-query'
import { Recycle, RefreshCw, AlertCircle, Package } from 'lucide-react'
import { recyclablesApi } from '@/lib/api'
import { formatWeight, formatCurrency, formatDateTime, cn } from '@/lib/utils'
import DownloadPdfButton from '@/components/shared/DownloadPdfButton'

interface RecyclableRecord {
  id: string
  recorded_at: string
  job_id?: string
  client_id?: string
  material_breakdown?: Record<string, number>
  total_recyclable_kg?: number
  buyer_id?: string
  sale_value_myr?: number
}

const MATERIAL_COLORS: Record<string, string> = {
  paper:     'bg-yellow-900/40 text-yellow-300',
  pet:       'bg-brand-900/40 text-brand-300',
  hdpe:      'bg-cyan-900/40 text-cyan-300',
  aluminium: 'bg-gray-100 text-gray-600',
  ferrous:   'bg-orange-900/40 text-orange-300',
  glass:     'bg-brand-900/40 text-brand-300',
  ewaste:    'bg-purple-900/40 text-purple-300',
}

export default function RecyclablesPage() {
  const { data: statsData, isLoading: statsLoading } = useQuery({
    queryKey: ['recyclables', 'stats'],
    queryFn: () => recyclablesApi.getRecoveryStats(),
    staleTime: 10 * 60_000,
  })

  const { data: materialsData, isLoading: materialsLoading, isError, refetch } = useQuery({
    queryKey: ['recyclables', 'materials'],
    queryFn: () => recyclablesApi.listMaterials({ limit: 50 } as Parameters<typeof recyclablesApi.listMaterials>[0]),
    staleTime: 30_000,
  })

  const stats = statsData as Record<string, unknown> | null
  const records = (materialsData as { items?: RecyclableRecord[] } | null)?.items ?? []
  const materialBreakdown = (stats?.material_breakdown as { material: string; total_kg: number; revenue_myr?: number }[]) ?? []

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Recyclables</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Material recovery, chain-of-custody, and buyer allocation
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="flex items-center gap-1.5 px-3 py-2 text-xs text-gray-500 hover:text-gray-900 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh
        </button>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[
          { label: 'Total Recyclable', value: formatWeight(stats?.total_recyclable_kg as number), color: 'text-green-400' },
          { label: 'Total Revenue', value: formatCurrency(stats?.total_revenue_myr as number), color: 'text-emerald-400' },
          { label: 'Records', value: String(stats?.record_count ?? '—'), color: 'text-gray-700' },
        ].map((card) => (
          <div key={card.label} className="bg-white border border-gray-200 rounded-xl p-4">
            <p className="text-xs text-gray-400 font-semibold uppercase tracking-wider">{card.label}</p>
            {statsLoading
              ? <div className="h-6 w-24 rounded bg-gray-200 animate-pulse mt-1" />
              : <p className={cn('text-xl font-bold mt-1', card.color)}>{card.value}</p>
            }
          </div>
        ))}
      </div>

      {/* Material breakdown */}
      {materialBreakdown.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">Material Breakdown</h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
            {materialBreakdown.map((m) => (
              <div key={m.material} className={cn('rounded-lg p-3 text-center', MATERIAL_COLORS[m.material] ?? 'bg-gray-100 text-gray-600')}>
                <p className="text-xs font-semibold capitalize">{m.material}</p>
                <p className="text-sm font-bold mt-1">{formatWeight(m.total_kg)}</p>
                {m.revenue_myr != null && (
                  <p className="text-[10px] opacity-70 mt-0.5">{formatCurrency(m.revenue_myr, { compact: true })}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Records table */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        {isError && (
          <div className="flex items-center gap-2 p-4 text-red-500 text-sm">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            Failed to load recyclable records.
          </div>
        )}

        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                {[
                  { label: 'Recorded At', cls: '' },
                  { label: 'Total Weight', cls: '' },
                  { label: 'Material Breakdown', cls: 'hidden sm:table-cell' },
                  { label: 'Sale Value', cls: 'hidden sm:table-cell' },
                  { label: 'Certificate', cls: 'hidden sm:table-cell' },
                ].map((h) => (
                  <th key={h.label} className={cn("px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap", h.cls)}>
                    {h.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {materialsLoading
                ? Array.from({ length: 6 }).map((_, i) => (
                    <tr key={i} className="border-b border-gray-100">
                      {Array.from({ length: 4 }).map((_, j) => (
                        <td key={j} className="px-4 py-3">
                          <div className="h-4 rounded bg-gray-200 animate-pulse" style={{ width: `${50 + Math.random() * 50}%` }} />
                        </td>
                      ))}
                    </tr>
                  ))
                : records.length === 0
                ? (
                    <tr>
                      <td colSpan={4} className="px-4 py-12 text-center text-gray-400 text-sm">
                        <Recycle className="w-8 h-8 mx-auto mb-2 opacity-30" />
                        No recyclable records found
                      </td>
                    </tr>
                  )
                : records.map((r) => (
                    <tr key={r.id} className="border-b border-gray-100 hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3">
                        <span className="text-xs text-gray-700">{formatDateTime(r.recorded_at)}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-sm font-semibold text-green-400">{formatWeight(r.total_recyclable_kg)}</span>
                      </td>
                      <td className="px-4 py-3 hidden sm:table-cell">
                        {r.material_breakdown ? (
                          <div className="flex flex-wrap gap-1">
                            {Object.entries(r.material_breakdown)
                              .filter(([, v]) => v > 0)
                              .map(([k, v]) => (
                                <span key={k} className={cn('text-[10px] px-1.5 py-0.5 rounded', MATERIAL_COLORS[k.replace('_kg', '')] ?? 'bg-gray-100 text-gray-600')}>
                                  {k.replace('_kg', '')}: {formatWeight(v)}
                                </span>
                              ))}
                          </div>
                        ) : <span className="text-xs text-gray-400">—</span>}
                      </td>
                      <td className="px-4 py-3 hidden sm:table-cell">
                        <span className="text-xs text-emerald-400">{r.sale_value_myr != null ? formatCurrency(r.sale_value_myr) : '—'}</span>
                      </td>
                      <td className="px-4 py-3 hidden sm:table-cell">
                        <DownloadPdfButton
                          label="Download"
                          onDownload={() => recyclablesApi.generateCertificatePDF(r.id)}
                          filename={`recycling-certificate-${r.id}.pdf`}
                        />
                      </td>
                    </tr>
                  ))
              }
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
