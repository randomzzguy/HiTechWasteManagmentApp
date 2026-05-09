'use client'

import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Flame, Plus, RefreshCw, AlertCircle, ChevronRight,
  CheckCircle2, Clock, FileText,
} from 'lucide-react'
import { destructionApi } from '@/lib/api'
import { formatDate, cn } from '@/lib/utils'
import DownloadPdfButton from '@/components/shared/DownloadPdfButton'
import DestructionJobForm from '@/components/destruction/DestructionJobForm'

interface DestructionJob {
  id: string
  job_id?: string
  goods_description: string
  quantity_units?: number
  weight_kg?: number
  destruction_method?: string
  destruction_date?: string
  destruction_location?: string
  certificate_issued: boolean
  reason_codes?: string[]
}

const METHOD_LABELS: Record<string, string> = {
  shredding:           'Shredding',
  incineration:        'Incineration',
  landfill_compaction: 'Landfill Compaction',
}

export default function DestructionPage() {
  const [page, setPage] = useState(0)
  const [formOpen, setFormOpen] = useState(false)
  const queryClient = useQueryClient()
  const PAGE_SIZE = 50

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['destruction', 'jobs', { page }],
    queryFn: () =>
      destructionApi.listJobs({
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      } as Parameters<typeof destructionApi.listJobs>[0]),
    staleTime: 60_000,
  })

  const jobs = (data as { items?: DestructionJob[] } | null)?.items ?? []
  const total = (data as { total?: number } | null)?.total ?? 0
  const totalPages = Math.ceil(total / PAGE_SIZE)

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Witnessed Destruction</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Secure destruction jobs and certificates of destruction
          </p>
        </div>
        <button
          onClick={() => setFormOpen(true)}
          className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-500 text-white text-sm font-semibold rounded-lg transition-colors">
          <Plus className="w-4 h-4" />
          New Destruction Job
        </button>
      </div>

      {/* Table */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
          <span className="text-sm font-semibold text-gray-900">Destruction Jobs</span>
          <button
            onClick={() => refetch()}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-gray-500 hover:text-gray-900 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </button>
        </div>

        {isError && (
          <div className="flex items-center gap-2 p-4 text-red-500 text-sm">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            Failed to load destruction jobs.
          </div>
        )}

        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">Goods Description</th>
                <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap hidden sm:table-cell">Qty / Weight</th>
                <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap hidden sm:table-cell">Method</th>
                <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">Date</th>
                <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap hidden md:table-cell">Location</th>
                <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap hidden md:table-cell">Reason</th>
                <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">Certificate</th>
                <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap hidden sm:table-cell"></th>
              </tr>
            </thead>
            <tbody>
              {isLoading
                ? Array.from({ length: 6 }).map((_, i) => (
                    <tr key={i} className="border-b border-gray-100">
                      {Array.from({ length: 8 }).map((_, j) => (
                        <td key={j} className="px-4 py-3">
                          <div className="h-4 rounded bg-gray-200 animate-pulse" style={{ width: `${50 + Math.random() * 50}%` }} />
                        </td>
                      ))}
                    </tr>
                  ))
                : jobs.length === 0
                ? (
                    <tr>
                      <td colSpan={8} className="px-4 py-12 text-center text-gray-400 text-sm">
                        <Flame className="w-8 h-8 mx-auto mb-2 opacity-30" />
                        No destruction jobs found
                      </td>
                    </tr>
                  )
                : jobs.map((job) => (
                    <tr key={job.id} className="border-b border-gray-100 hover:bg-gray-50 transition-colors group">
                      <td className="px-4 py-3 max-w-[200px]">
                        <span className="text-sm text-gray-900 truncate block">{job.goods_description}</span>
                      </td>
                      <td className="px-4 py-3 hidden sm:table-cell">
                        <div className="flex flex-col text-xs text-gray-500">
                          {job.quantity_units != null && <span>{job.quantity_units.toLocaleString()} units</span>}
                          {job.weight_kg != null && <span>{Number(job.weight_kg).toLocaleString()} kg</span>}
                        </div>
                      </td>
                      <td className="px-4 py-3 hidden sm:table-cell">
                        <span className="text-xs text-gray-500">
                          {job.destruction_method ? (METHOD_LABELS[job.destruction_method] ?? job.destruction_method) : '—'}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-xs text-gray-500">{job.destruction_date ? formatDate(job.destruction_date) : '—'}</span>
                      </td>
                      <td className="px-4 py-3 max-w-[150px] hidden md:table-cell">
                        <span className="text-xs text-gray-500 truncate block">{job.destruction_location ?? '—'}</span>
                      </td>
                      <td className="px-4 py-3 hidden md:table-cell">
                        <div className="flex flex-wrap gap-1">
                          {(job.reason_codes ?? []).map((r) => (
                            <span key={r} className="text-[10px] bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded capitalize">
                              {r.replace('_', ' ')}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        {job.certificate_issued ? (
                          <div className="flex items-center gap-2">
                            <span className="flex items-center gap-1 text-xs text-green-400">
                              <CheckCircle2 className="w-3.5 h-3.5" /> Issued
                            </span>
                            <DownloadPdfButton
                              label="Download"
                              onDownload={() => destructionApi.generateCertificatePDF(job.id)}
                              filename={`destruction-certificate-${job.id}.pdf`}
                            />
                          </div>
                        ) : (
                          <span className="flex items-center gap-1 text-xs text-gray-400">
                            <Clock className="w-3.5 h-3.5" /> Pending
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right hidden sm:table-cell">
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
            <span>{total} total jobs</span>
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

      <DestructionJobForm
        open={formOpen}
        onOpenChange={setFormOpen}
        onSuccess={() => queryClient.invalidateQueries({ queryKey: ['destruction', 'jobs'] })}
      />
    </div>
  )
}
