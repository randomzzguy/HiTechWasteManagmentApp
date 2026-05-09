'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Shield, Plus, Search, RefreshCw, AlertCircle,
  AlertTriangle, Clock, CheckCircle2, ChevronRight,
} from 'lucide-react'
import { complianceApi } from '@/lib/api'
import { formatDate, cn } from '@/lib/utils'

interface SwBatch {
  id: string
  sw_code: string
  waste_description: string
  quantity_kg: number
  physical_state: string
  storage_start_date: string
  storage_deadline?: string
  days_remaining?: number
  status: string
  client_id: string
  consignment_note_id?: string
}

const STATUS_STYLES: Record<string, string> = {
  in_storage:  'bg-brand-50 text-brand-600 border-brand-200',
  dispatched:  'bg-amber-50 text-amber-600 border-amber-200',
  processed:   'bg-green-50 text-green-600 border-green-200',
}

function urgencyStyle(days?: number): string {
  if (days === undefined || days === null) return 'text-gray-500'
  if (days < 0) return 'text-red-400 font-bold'
  if (days <= 2) return 'text-red-400 font-semibold'
  if (days <= 10) return 'text-amber-400 font-semibold'
  return 'text-gray-500'
}

function urgencyIcon(days?: number) {
  if (days === undefined || days === null) return null
  if (days < 0) return <AlertTriangle className="w-3.5 h-3.5 text-red-400" />
  if (days <= 10) return <Clock className="w-3.5 h-3.5 text-amber-400" />
  return null
}

export default function CompliancePage() {
  const [statusFilter, setStatusFilter] = useState('')
  const [expiringSoon, setExpiringSoon] = useState(false)
  const [page, setPage] = useState(0)
  const PAGE_SIZE = 50

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['compliance', 'batches', { statusFilter, expiringSoon, page }],
    queryFn: () =>
      complianceApi.listBatches({
        status: statusFilter || undefined,
        is_overdue: expiringSoon || undefined,
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      } as Parameters<typeof complianceApi.listBatches>[0]),
    staleTime: 30_000,
  })

  const { data: deadlineData } = useQuery({
    queryKey: ['compliance', 'deadlines'],
    queryFn: () => complianceApi.getDeadlines(),
    staleTime: 5 * 60_000,
  })

  const batches = (data as { items?: SwBatch[] } | null)?.items ?? []
  const total = (data as { total?: number } | null)?.total ?? 0
  const totalPages = Math.ceil(total / PAGE_SIZE)

  const deadlines = deadlineData as unknown as Record<string, unknown> | null
  const summary = deadlines?.summary as Record<string, number> | undefined

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Scheduled Waste Compliance</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            SW batch tracking, 90-day rule enforcement, consignment notes
          </p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-500 text-white text-sm font-semibold rounded-lg transition-colors">
          <Plus className="w-4 h-4" />
          New SW Batch
        </button>
      </div>

      {/* Alert summary */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: 'Overdue', value: summary.overdue ?? 0, color: 'text-red-400', bg: 'bg-red-50 border-red-200', icon: AlertTriangle },
            { label: 'Critical (≤2 days)', value: summary.critical ?? 0, color: 'text-red-400', bg: 'bg-red-50 border-red-200', icon: AlertTriangle },
            { label: 'Warning (≤10 days)', value: summary.warning ?? 0, color: 'text-amber-400', bg: 'bg-amber-50 border-amber-200', icon: Clock },
            { label: 'Info', value: summary.info ?? 0, color: 'text-brand-400', bg: 'bg-brand-50 border-brand-200', icon: CheckCircle2 },
          ].map((item) => (
            <div key={item.label} className={cn('flex items-center gap-3 p-3 rounded-xl border bg-white', item.bg)}>
              <item.icon className={cn('w-5 h-5 flex-shrink-0', item.color)} />
              <div>
                <p className="text-xs text-gray-400">{item.label}</p>
                <p className={cn('text-xl font-bold', item.color)}>{item.value}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="flex items-center gap-1 bg-gray-100 border border-gray-200 rounded-lg p-1">
          {[
            { label: 'All', value: '' },
            { label: 'In Storage', value: 'in_storage' },
            { label: 'Dispatched', value: 'dispatched' },
            { label: 'Processed', value: 'processed' },
          ].map((f) => (
            <button
              key={f.value}
              onClick={() => { setStatusFilter(f.value); setPage(0) }}
              className={cn(
                'px-3 py-1.5 rounded-md text-xs font-semibold transition-colors',
                statusFilter === f.value
                  ? 'bg-brand-600 text-white'
                  : 'text-gray-500 hover:text-gray-900 hover:bg-white'
              )}
            >
              {f.label}
            </button>
          ))}
        </div>

        <button
          onClick={() => { setExpiringSoon((v) => !v); setPage(0) }}
          className={cn(
            'flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-lg border transition-colors',
            expiringSoon
              ? 'bg-amber-900/30 border-amber-700 text-amber-300'
              : 'bg-white border-gray-300 text-gray-500 hover:text-gray-900 hover:bg-gray-50'
          )}
        >
          <AlertTriangle className="w-3.5 h-3.5" />
          Expiring Soon
        </button>

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
            Failed to load compliance data.
          </div>
        )}

        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                {['SW Code', 'Description', 'Quantity', 'State', 'Storage Start', 'Deadline', 'Days Left', 'Status', 'CN', ''].map((h) => (
                  <th key={h} className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading
                ? Array.from({ length: 8 }).map((_, i) => (
                    <tr key={i} className="border-b border-gray-100">
                      {Array.from({ length: 10 }).map((_, j) => (
                        <td key={j} className="px-4 py-3">
                          <div className="h-4 rounded bg-gray-200 animate-pulse" style={{ width: `${50 + Math.random() * 50}%` }} />
                        </td>
                      ))}
                    </tr>
                  ))
                : batches.length === 0
                ? (
                    <tr>
                      <td colSpan={10} className="px-4 py-12 text-center text-gray-400 text-sm">
                        <Shield className="w-8 h-8 mx-auto mb-2 opacity-30" />
                        No scheduled waste batches found
                      </td>
                    </tr>
                  )
                : batches.map((b) => (
                    <tr key={b.id} className="border-b border-gray-100 hover:bg-gray-50 transition-colors group">
                      <td className="px-4 py-3">
                        <span className="font-mono text-xs font-bold text-amber-400">{b.sw_code}</span>
                      </td>
                      <td className="px-4 py-3 max-w-[200px]">
                        <span className="text-xs text-gray-700 truncate block">{b.waste_description}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-xs text-gray-700">{Number(b.quantity_kg).toLocaleString()} kg</span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-xs text-gray-500 capitalize">{b.physical_state}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-xs text-gray-500">{formatDate(b.storage_start_date)}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={cn('text-xs', b.days_remaining !== undefined && b.days_remaining < 0 ? 'text-red-400' : 'text-gray-500')}>
                          {b.storage_deadline ? formatDate(b.storage_deadline) : '—'}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={cn('flex items-center gap-1 text-xs', urgencyStyle(b.days_remaining))}>
                          {urgencyIcon(b.days_remaining)}
                          {b.days_remaining !== undefined
                            ? b.days_remaining < 0
                              ? `${Math.abs(b.days_remaining)}d overdue`
                              : `${b.days_remaining}d`
                            : '—'}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={cn(
                          'inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold border',
                          STATUS_STYLES[b.status] ?? 'bg-gray-100 text-gray-600 border-gray-300'
                        )}>
                          {b.status.replace('_', ' ')}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {b.consignment_note_id ? (
                          <CheckCircle2 className="w-4 h-4 text-green-400" />
                        ) : (
                          <span className="text-xs text-gray-400">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button className="opacity-0 group-hover:opacity-100 transition-opacity inline-flex items-center gap-1 text-xs text-gray-500 hover:text-gray-900 px-2 py-1 rounded hover:bg-gray-100">
                          View <ChevronRight className="w-3 h-3" />
                        </button>
                      </td>
                    </tr>
                  ))
              }
            </tbody>
          </table>
        </div>

        {total > PAGE_SIZE && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200 text-xs text-gray-500">
            <span>{total} total batches</span>
            <div className="flex items-center gap-2">
              <button disabled={page === 0} onClick={() => setPage((p) => p - 1)}
                className="px-3 py-1.5 rounded bg-gray-100 hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors text-gray-700">
                Previous
              </button>
              <span>Page {page + 1} of {totalPages}</span>
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
