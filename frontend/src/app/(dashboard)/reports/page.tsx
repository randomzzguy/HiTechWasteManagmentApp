'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  FileText, Download, RefreshCw, AlertCircle,
  Clock, CheckCircle2, XCircle, Loader2, Play,
} from 'lucide-react'
import { toast } from 'sonner'
import { reportsApi } from '@/lib/api'
import { formatDateTime, cn } from '@/lib/utils'
import DownloadPdfButton from '@/components/shared/DownloadPdfButton'

interface Report {
  id: string
  status: string
  created_at?: string
  pdf_url?: string
  config?: Record<string, unknown>
}

const STATUS_STYLES: Record<string, string> = {
  pending: 'bg-amber-50 text-amber-600 border-amber-200',
  running: 'bg-brand-50 text-brand-600 border-brand-200',
  success: 'bg-green-50 text-green-600 border-green-200',
  failure: 'bg-red-50 text-red-600 border-red-200',
}

const STATUS_ICONS: Record<string, React.ElementType> = {
  pending: Clock,
  running: Loader2,
  success: CheckCircle2,
  failure: XCircle,
}

export default function ReportsPage() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(0)
  const [generatingId, setGeneratingId] = useState<string | null>(null)
  const [dateRange, setDateRange] = useState<{ from: string; to: string }>({
    from: '',
    to: '',
  })
  const PAGE_SIZE = 20

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['reports', { page }],
    queryFn: () =>
      reportsApi.listReports({
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      } as Parameters<typeof reportsApi.listReports>[0]),
    staleTime: 30_000,
    refetchInterval: 15_000,
  })

  const { data: reportTypes } = useQuery({
    queryKey: ['reports', 'types'],
    queryFn: () => reportsApi.listReportTypes(),
    staleTime: Infinity,
  })

  const generateMutation = useMutation({
    mutationFn: (config: Record<string, unknown>) =>
      reportsApi.generateReport(config),
    onSuccess: () => {
      toast.success('Report generation started')
      queryClient.invalidateQueries({ queryKey: ['reports'] })
      setGeneratingId(null)
    },
    onError: () => {
      toast.error('Failed to generate report')
      setGeneratingId(null)
    },
  })

  function handleGenerate(type: Record<string, unknown>) {
    const typeId = String(type.id ?? type.name ?? 'report')
    setGeneratingId(typeId)
    const config: Record<string, unknown> = {
      report_type: type.id ?? type.name,
      format: 'pdf',
    }
    if (dateRange.from) config.period_from = dateRange.from
    if (dateRange.to) config.period_to = dateRange.to
    generateMutation.mutate(config)
  }

  const reports = (data as { items?: Report[] } | null)?.items ?? []
  const total = (data as { total?: number } | null)?.total ?? 0
  const totalPages = Math.ceil(total / PAGE_SIZE)
  const types = Array.isArray(reportTypes) ? reportTypes as Record<string, unknown>[] : []

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Reports</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Generate and download operational and ESG reports
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

      {/* Date range picker */}
      <div className="flex flex-wrap items-end gap-3 bg-white border border-gray-200 rounded-xl px-4 py-3">
        <div className="flex flex-col gap-1">
          <label className="text-[11px] font-semibold text-gray-500 uppercase tracking-wider">
            Period From
          </label>
          <input
            type="date"
            value={dateRange.from}
            onChange={(e) => setDateRange((d) => ({ ...d, from: e.target.value }))}
            className="h-8 px-2 text-sm text-gray-900 bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[11px] font-semibold text-gray-500 uppercase tracking-wider">
            Period To
          </label>
          <input
            type="date"
            value={dateRange.to}
            min={dateRange.from || undefined}
            onChange={(e) => setDateRange((d) => ({ ...d, to: e.target.value }))}
            className="h-8 px-2 text-sm text-gray-900 bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
        {(dateRange.from || dateRange.to) && (
          <button
            onClick={() => setDateRange({ from: '', to: '' })}
            className="h-8 px-3 text-xs text-gray-500 hover:text-gray-900 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
          >
            Clear
          </button>
        )}
        <p className="text-xs text-gray-400 self-end pb-0.5">
          {dateRange.from || dateRange.to
            ? `Generating for: ${dateRange.from || '…'} → ${dateRange.to || '…'}`
            : 'No date range set — backend will use its default period'}
        </p>
      </div>

      {/* Report type cards */}
      {types.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {types.map((t) => {
            const typeId = String(t.id ?? t.name)
            const isGenerating = generatingId === typeId && generateMutation.isPending
            return (
              <div key={typeId} className="bg-white border border-gray-200 rounded-xl p-4 hover:border-gray-300 transition-colors">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-gray-900">{String((t.name ?? t.label ?? 'Report') as string)}</p>
                    {!!t.description && (
                      <p className="text-xs text-gray-400 mt-1 leading-relaxed">{String(t.description as string)}</p>
                    )}
                  </div>
                  <button
                    onClick={() => handleGenerate(t)}
                    disabled={generateMutation.isPending}
                    className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 bg-brand-600 hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-xs font-semibold rounded-lg transition-colors"
                  >
                    {isGenerating ? (
                      <Loader2 className="w-3 h-3 animate-spin" />
                    ) : (
                      <Play className="w-3 h-3" />
                    )}
                    {isGenerating ? 'Generating…' : 'Generate'}
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Reports list */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-200">
          <span className="text-sm font-semibold text-gray-900">Generated Reports</span>
        </div>

        {isError && (
          <div className="flex items-center gap-2 p-4 text-red-500 text-sm">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            Failed to load reports.
          </div>
        )}

        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                {['Report ID', 'Created', 'Status', 'Download'].map((h) => (
                  <th key={h} className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading
                ? Array.from({ length: 5 }).map((_, i) => (
                    <tr key={i} className="border-b border-gray-100">
                      {Array.from({ length: 4 }).map((_, j) => (
                        <td key={j} className="px-4 py-3">
                          <div className="h-4 rounded bg-gray-200 animate-pulse" style={{ width: `${50 + Math.random() * 50}%` }} />
                        </td>
                      ))}
                    </tr>
                  ))
                : reports.length === 0
                ? (
                    <tr>
                      <td colSpan={4} className="px-4 py-12 text-center text-gray-400 text-sm">
                        <FileText className="w-8 h-8 mx-auto mb-2 opacity-30" />
                        No reports generated yet. Click Generate on a report type above.
                      </td>
                    </tr>
                  )
                : reports.map((r) => {
                    const StatusIcon = STATUS_ICONS[r.status] ?? Clock
                    return (
                      <tr key={r.id} className="border-b border-gray-100 hover:bg-gray-50 transition-colors">
                        <td className="px-4 py-3">
                          <span className="font-mono text-xs text-gray-500">{r.id.slice(0, 8)}…</span>
                        </td>
                        <td className="px-4 py-3">
                          <span className="text-xs text-gray-500">{r.created_at ? formatDateTime(r.created_at) : '—'}</span>
                        </td>
                        <td className="px-4 py-3">
                          <span className={cn(
                            'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold border',
                            STATUS_STYLES[r.status] ?? 'bg-gray-100 text-gray-600 border-gray-300'
                          )}>
                            <StatusIcon className={cn('w-3 h-3', r.status === 'running' && 'animate-spin')} />
                            {r.status}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          {r.status === 'success' ? (
                            <DownloadPdfButton
                              label="Download"
                              onDownload={() => reportsApi.downloadReport(r.id)}
                              filename={`report-${r.id}.pdf`}
                            />
                          ) : r.pdf_url ? (
                            <a
                              href={r.pdf_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 text-xs text-brand-600 hover:text-brand-700 font-semibold"
                            >
                              <Download className="w-3.5 h-3.5" />
                              Download PDF
                            </a>
                          ) : (
                            <span className="text-xs text-gray-400">—</span>
                          )}
                        </td>
                      </tr>
                    )
                  })
              }
            </tbody>
          </table>
        </div>

        {total > PAGE_SIZE && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200 text-xs text-gray-500">
            <span>{total} total reports</span>
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
