'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import {
  Plus, Search, Filter, ClipboardList, Calendar, Truck,
  ChevronRight, RefreshCw, AlertCircle,
} from 'lucide-react'
import { jobsApi } from '@/lib/api'
import { formatDate, snakeToTitle, cn } from '@/lib/utils'
import type { Job, JobStatus, JobType } from '@/types/job'
import JobForm from '@/components/jobs/JobForm'

// ---------------------------------------------------------------------------
// Status badge colours
// ---------------------------------------------------------------------------

const STATUS_STYLES: Record<JobStatus, string> = {
  draft:       'bg-gray-100 text-gray-600 border-gray-300',
  confirmed:   'bg-brand-50 text-brand-600 border-brand-200',
  dispatched:  'bg-violet-50 text-violet-600 border-violet-200',
  in_progress: 'bg-amber-50 text-amber-600 border-amber-200',
  completed:   'bg-green-50 text-green-600 border-green-200',
  invoiced:    'bg-brand-50 text-brand-600 border-brand-200',
  cancelled:   'bg-red-50 text-red-600 border-red-200',
}

const JOB_TYPE_LABELS: Record<string, string> = {
  general_collection:    'General',
  scheduled_waste:       'Scheduled Waste',
  witnessed_destruction: 'Destruction',
  food_waste_bsf:        'BSF / Food Waste',
  equipment_rental:      'Equipment Rental',
  consultancy:           'Consultancy',
}

const STATUS_FILTERS: { label: string; value: string }[] = [
  { label: 'All', value: '' },
  { label: 'Draft', value: 'draft' },
  { label: 'Confirmed', value: 'confirmed' },
  { label: 'Dispatched', value: 'dispatched' },
  { label: 'In Progress', value: 'in_progress' },
  { label: 'Completed', value: 'completed' },
  { label: 'Invoiced', value: 'invoiced' },
]

// ---------------------------------------------------------------------------
// Job row
// ---------------------------------------------------------------------------

function JobRow({ job }: { job: Job }) {
  const router = useRouter()
  return (
    <tr
      className="border-b border-gray-100 hover:bg-gray-50 transition-colors group cursor-pointer"
      onClick={() => router.push(`/jobs/${job.id}`)}
    >
      <td className="px-4 py-3">
        <span className="font-mono text-xs font-semibold text-green-400">
          {job.job_number}
        </span>
      </td>
      <td className="px-4 py-3">
        <span className="text-sm text-gray-900 font-medium">{job.client_name}</span>
      </td>
      <td className="px-4 py-3 hidden sm:table-cell">
        <span className="text-xs text-gray-500">
          {JOB_TYPE_LABELS[job.job_type] ?? snakeToTitle(job.job_type)}
        </span>
      </td>
      <td className="px-4 py-3">
        <span
          className={cn(
            'inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold border',
            STATUS_STYLES[job.status] ?? 'bg-gray-100 text-gray-600 border-gray-300'
          )}
        >
          {snakeToTitle(job.status)}
        </span>
      </td>
      <td className="px-4 py-3 hidden sm:table-cell">
        <span className="text-xs text-gray-500">
          {job.scheduled_date ? formatDate(job.scheduled_date) : '—'}
        </span>
      </td>
      <td className="px-4 py-3 hidden md:table-cell">
        <span className="text-xs text-gray-500">
          {job.driver_name ?? '—'}
        </span>
      </td>
      <td className="px-4 py-3 hidden md:table-cell">
        <span className="text-xs text-gray-500">
          {job.vehicle_registration ?? '—'}
        </span>
      </td>
      <td className="px-4 py-3 text-right">
        <span className="opacity-0 group-hover:opacity-100 transition-opacity inline-flex items-center gap-1 text-xs text-gray-500 hover:text-gray-900 px-2 py-1 rounded hover:bg-gray-100">
          View <ChevronRight className="w-3 h-3" />
        </span>
      </td>
    </tr>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function JobsPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [page, setPage] = useState(0)
  const [formOpen, setFormOpen] = useState(false)
  const PAGE_SIZE = 50

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['jobs', { search, statusFilter, page }],
    queryFn: () =>
      jobsApi.list({
        search: search || undefined,
        status: statusFilter || undefined,
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      } as Parameters<typeof jobsApi.list>[0]),
    staleTime: 30_000,
  })

  const jobs = (data as { items?: Job[] } | null)?.items ?? []
  const total = (data as { total?: number } | null)?.total ?? 0
  const totalPages = Math.ceil(total / PAGE_SIZE)

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Jobs</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Collection orders and service jobs
          </p>
        </div>
        <button
          className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-500 text-white text-sm font-semibold rounded-lg transition-colors"
          onClick={() => setFormOpen(true)}
        >
          <Plus className="w-4 h-4" />
          New Job
        </button>
      </div>

      <JobForm open={formOpen} onClose={() => setFormOpen(false)} />

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        {/* Search */}
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search job number, notes…"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(0) }}
            className="w-full pl-9 pr-3 py-2 bg-white border border-gray-300 rounded-lg text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500/20"
          />
        </div>

        {/* Status filter tabs */}
        <div className="flex items-center gap-1 bg-gray-100 border border-gray-200 rounded-lg p-1 overflow-x-auto">
          {STATUS_FILTERS.map((f) => (
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
            Failed to load jobs. Check your connection and try again.
          </div>
        )}

        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">Job #</th>
                <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">Client</th>
                <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap hidden sm:table-cell">Type</th>
                <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">Status</th>
                <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap hidden sm:table-cell">Scheduled</th>
                <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap hidden md:table-cell">Driver</th>
                <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap hidden md:table-cell">Vehicle</th>
                <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap"></th>
              </tr>
            </thead>
            <tbody>
              {isLoading
                ? Array.from({ length: 8 }).map((_, i) => (
                    <tr key={i} className="border-b border-gray-100">
                      {Array.from({ length: 8 }).map((_, j) => (
                        <td key={j} className="px-4 py-3">
                          <div className="h-4 rounded bg-gray-200 animate-pulse" style={{ width: `${60 + Math.random() * 40}%` }} />
                        </td>
                      ))}
                    </tr>
                  ))
                : jobs.length === 0
                ? (
                    <tr>
                      <td colSpan={8} className="px-4 py-12 text-center text-gray-400 text-sm">
                        <ClipboardList className="w-8 h-8 mx-auto mb-2 opacity-30" />
                        No jobs found
                      </td>
                    </tr>
                  )
                : jobs.map((job) => <JobRow key={job.id} job={job} />)
              }
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {total > PAGE_SIZE && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200 text-xs text-gray-500">
            <span>{total} total jobs</span>
            <div className="flex items-center gap-2">
              <button
                disabled={page === 0}
                onClick={() => setPage((p) => p - 1)}
                className="px-3 py-1.5 rounded bg-gray-100 hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors text-gray-700"
              >
                Previous
              </button>
              <span className="hidden sm:inline">Page {page + 1} of {totalPages}</span>
              <button
                disabled={page >= totalPages - 1}
                onClick={() => setPage((p) => p + 1)}
                className="px-3 py-1.5 rounded bg-gray-100 hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors text-gray-700"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
