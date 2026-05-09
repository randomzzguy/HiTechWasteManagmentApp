'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { ChevronRight, ArrowUpDown } from 'lucide-react'
import { formatDate, formatWeight, snakeToTitle, cn } from '@/lib/utils'
import type { Job, JobStatus } from '@/types/job'

const STATUS_STYLES: Record<JobStatus, string> = {
  draft:       'bg-gray-100 text-gray-700 border-gray-300',
  confirmed:   'bg-brand-900/50 text-brand-300 border-brand-700',
  dispatched:  'bg-violet-900/50 text-violet-300 border-violet-700',
  in_progress: 'bg-amber-900/50 text-amber-300 border-amber-700',
  completed:   'bg-green-900/50 text-green-300 border-green-700',
  invoiced:    'bg-brand-900/50 text-brand-300 border-brand-700',
  cancelled:   'bg-red-900/50 text-red-300 border-red-700',
}

interface JobTableProps {
  jobs: Job[]
  isLoading?: boolean
}

type SortKey = 'job_number' | 'scheduled_date' | 'status' | 'client_name'

export default function JobTable({ jobs, isLoading = false }: JobTableProps) {
  const router = useRouter()
  const [sortKey, setSortKey] = useState<SortKey>('scheduled_date')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('asc') }
  }

  const sorted = [...jobs].sort((a, b) => {
    const av = a[sortKey] ?? ''
    const bv = b[sortKey] ?? ''
    const cmp = String(av).localeCompare(String(bv))
    return sortDir === 'asc' ? cmp : -cmp
  })

  const SortHeader = ({ label, k }: { label: string; k: SortKey }) => (
    <th
      className="px-4 py-3 text-[11px] font-semibold text-gray-400 uppercase tracking-wider whitespace-nowrap cursor-pointer hover:text-gray-700 transition-colors"
      onClick={() => toggleSort(k)}
    >
      <span className="flex items-center gap-1">
        {label}
        <ArrowUpDown className={cn('w-3 h-3', sortKey === k ? 'text-green-400' : 'opacity-30')} />
      </span>
    </th>
  )

  if (isLoading) return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <tbody>
          {Array.from({ length: 6 }).map((_, i) => (
            <tr key={i} className="border-b border-gray-100">
              {Array.from({ length: 7 }).map((_, j) => (
                <td key={j} className="px-4 py-3">
                  <div className="h-4 rounded bg-gray-100 animate-pulse" style={{ width: `${50 + Math.random() * 40}%` }} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left">
        <thead>
          <tr className="border-b border-gray-200 bg-gray-50">
            <SortHeader label="Job #" k="job_number" />
            <SortHeader label="Client" k="client_name" />
            <th className="px-4 py-3 text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Type</th>
            <SortHeader label="Status" k="status" />
            <SortHeader label="Scheduled" k="scheduled_date" />
            <th className="px-4 py-3 text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Driver</th>
            <th className="px-4 py-3 text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Weight</th>
            <th className="px-4 py-3" />
          </tr>
        </thead>
        <tbody>
          {sorted.length === 0 ? (
            <tr>
              <td colSpan={8} className="px-4 py-12 text-center text-gray-400 text-sm">No jobs found</td>
            </tr>
          ) : sorted.map(job => (
            <tr
              key={job.id}
              onClick={() => router.push(`/jobs/${job.id}`)}
              className="border-b border-gray-100 hover:bg-gray-50 transition-colors cursor-pointer group"
            >
              <td className="px-4 py-3">
                <span className="font-mono text-xs font-semibold text-green-400">{job.job_number}</span>
              </td>
              <td className="px-4 py-3">
                <span className="text-sm text-gray-900 font-medium">{job.client_name}</span>
              </td>
              <td className="px-4 py-3">
                <span className="text-xs text-gray-500">{snakeToTitle(job.job_type)}</span>
              </td>
              <td className="px-4 py-3">
                <span className={cn('inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold border', STATUS_STYLES[job.status])}>
                  {snakeToTitle(job.status)}
                </span>
              </td>
              <td className="px-4 py-3">
                <span className="text-xs text-gray-500">{job.scheduled_date ? formatDate(job.scheduled_date) : '—'}</span>
              </td>
              <td className="px-4 py-3">
                <span className="text-xs text-gray-500">{job.driver_name ?? '—'}</span>
              </td>
              <td className="px-4 py-3">
                <span className="text-xs text-gray-500">
                  {job.actual_weight_kg ? formatWeight(job.actual_weight_kg) : job.estimated_weight_kg ? `~${formatWeight(job.estimated_weight_kg)}` : '—'}
                </span>
              </td>
              <td className="px-4 py-3 text-right">
                <ChevronRight className="w-4 h-4 text-gray-400 group-hover:text-gray-700 transition-colors" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

