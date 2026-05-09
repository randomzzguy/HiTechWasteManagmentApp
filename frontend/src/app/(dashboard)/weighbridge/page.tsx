'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Scale, Plus, Search, RefreshCw, AlertCircle, TrendingUp,
} from 'lucide-react'
import { weighbridgeApi } from '@/lib/api'
import { formatDateTime, formatWeight, cn } from '@/lib/utils'
import WeighbridgeForm from '@/components/weighbridge/WeighbridgeForm'

interface WeighbridgeRecord {
  id: string
  recorded_at: string
  job_id?: string
  client_id?: string
  gross_weight_kg?: number
  tare_weight_kg?: number
  net_weight_kg?: number
  waste_type_breakdown?: Record<string, number>
  operator_id?: string
  notes?: string
}

export default function WeighbridgePage() {
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(0)
  const [formOpen, setFormOpen] = useState(false)
  const PAGE_SIZE = 50

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['weighbridge', { page }],
    queryFn: () =>
      weighbridgeApi.listRecords({
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      } as Parameters<typeof weighbridgeApi.listRecords>[0]),
    staleTime: 30_000,
  })

  const { data: statsData } = useQuery({
    queryKey: ['weighbridge', 'stats', 'monthly'],
    queryFn: () => weighbridgeApi.getTonnageStats({ period: 'monthly' }),
    staleTime: 5 * 60_000,
  })

  const records = (data as { items?: WeighbridgeRecord[] } | null)?.items ?? []
  const total = (data as { total?: number } | null)?.total ?? 0
  const totalPages = Math.ceil(total / PAGE_SIZE)

  const stats = statsData as Record<string, unknown> | null
  const summaryStats = stats?.summary as Record<string, number> | undefined

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Weighbridge</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Tonnage records and diversion tracking
          </p>
        </div>
        <button
          className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-500 text-white text-sm font-semibold rounded-lg transition-colors"
          onClick={() => setFormOpen(true)}
        >
          <Plus className="w-4 h-4" />
          New Record
        </button>
      </div>

      <WeighbridgeForm open={formOpen} onClose={() => setFormOpen(false)} onSuccess={() => setFormOpen(false)} />

      {/* Summary cards */}
      {summaryStats && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {[
            { label: 'Total Net Weight', value: formatWeight(summaryStats.total_net_kg), icon: Scale, color: 'text-green-400', bg: 'bg-green-50 border-green-200' },
            { label: 'Total Gross Weight', value: formatWeight(summaryStats.total_gross_kg), icon: TrendingUp, color: 'text-brand-400', bg: 'bg-brand-50 border-brand-200' },
            { label: 'Total Records', value: summaryStats.total_record_count?.toLocaleString() ?? '—', icon: Scale, color: 'text-gray-500', bg: 'bg-gray-100 border-gray-200' },
          ].map((card) => (
            <div key={card.label} className={cn('flex items-center gap-4 p-4 rounded-xl border bg-white', card.bg)}>
              <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center border', card.bg)}>
                <card.icon className={cn('w-5 h-5', card.color)} />
              </div>
              <div>
                <p className="text-xs text-gray-400 font-semibold uppercase tracking-wider">{card.label}</p>
                <p className="text-xl font-bold text-gray-900 mt-0.5">{card.value}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search by job or client…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-white border border-gray-300 rounded-lg text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500/20"
          />
        </div>
        <button
          onClick={() => refetch()}
          className="flex items-center gap-1.5 px-3 py-2 text-xs text-gray-500 hover:text-gray-900 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh
        </button>
      </div>

      {/* Table */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        {isError && (
          <div className="flex items-center gap-2 p-4 text-red-500 text-sm">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            Failed to load weighbridge records.
          </div>
        )}

        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">Recorded At</th>
                <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap hidden sm:table-cell">Gross Weight</th>
                <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap hidden sm:table-cell">Tare Weight</th>
                <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">Net Weight</th>
                <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap hidden md:table-cell">Waste Breakdown</th>
                <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap hidden md:table-cell">Notes</th>
              </tr>
            </thead>
            <tbody>
              {isLoading
                ? Array.from({ length: 8 }).map((_, i) => (
                    <tr key={i} className="border-b border-gray-100">
                      {Array.from({ length: 6 }).map((_, j) => (
                        <td key={j} className="px-4 py-3">
                          <div className="h-4 rounded bg-gray-200 animate-pulse" style={{ width: `${50 + Math.random() * 50}%` }} />
                        </td>
                      ))}
                    </tr>
                  ))
                : records.length === 0
                ? (
                    <tr>
                      <td colSpan={6} className="px-4 py-12 text-center text-gray-400 text-sm">
                        <Scale className="w-8 h-8 mx-auto mb-2 opacity-30" />
                        No weighbridge records found
                      </td>
                    </tr>
                  )
                : records.map((r) => (
                    <tr key={r.id} className="border-b border-gray-100 hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3">
                        <span className="text-xs text-gray-700">{formatDateTime(r.recorded_at)}</span>
                      </td>
                      <td className="px-4 py-3 hidden sm:table-cell">
                        <span className="text-xs text-gray-700">{formatWeight(r.gross_weight_kg)}</span>
                      </td>
                      <td className="px-4 py-3 hidden sm:table-cell">
                        <span className="text-xs text-gray-500">{formatWeight(r.tare_weight_kg)}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-sm font-semibold text-green-400">{formatWeight(r.net_weight_kg)}</span>
                      </td>
                      <td className="px-4 py-3 hidden md:table-cell">
                        {r.waste_type_breakdown ? (
                          <div className="flex flex-wrap gap-1">
                            {Object.entries(r.waste_type_breakdown)
                              .filter(([, v]) => v > 0)
                              .map(([k, v]) => (
                                <span key={k} className="text-[10px] bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded">
                                  {k.replace('_kg', '')}: {formatWeight(v)}
                                </span>
                              ))}
                          </div>
                        ) : <span className="text-xs text-gray-400">—</span>}
                      </td>
                      <td className="px-4 py-3 hidden md:table-cell">
                        <span className="text-xs text-gray-400 truncate max-w-[200px] block">{r.notes ?? '—'}</span>
                      </td>
                    </tr>
                  ))
              }
            </tbody>
          </table>
        </div>

        {total > PAGE_SIZE && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200 text-xs text-gray-500">
            <span>{total} total records</span>
            <div className="flex items-center gap-2">
              <button disabled={page === 0} onClick={() => setPage((p) => p - 1)}
                className="px-3 py-1.5 rounded bg-gray-100 hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors text-gray-700">
                Previous
              </button>
              <span className="hidden sm:inline">Page {page + 1} of {totalPages}</span>
              <button disabled={page >= totalPages - 1} onClick={() => setPage((p) => p + 1)}
                className="px-3 py-1.5 rounded bg-gray-100 hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors text-gray-700">
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
