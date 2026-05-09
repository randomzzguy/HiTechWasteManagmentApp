'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import {
  Calendar,
  User,
  Truck,
  Weight,
  MoreHorizontal,
  Plus,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'
import { cn, formatDate, formatWeight } from '@/lib/utils'
import StatusBadge from '@/components/shared/StatusBadge'
import type { Job, JobStatus } from '@/types/job'
import { JOB_STATUS_COLUMNS } from '@/hooks/useJobs'

// ---------------------------------------------------------------------------
// Job type badge colours
// ---------------------------------------------------------------------------

const JOB_TYPE_COLORS: Record<string, string> = {
  scheduled_waste: 'bg-red-900/40 text-red-300 border-red-800/40',
  recyclables: 'bg-green-900/40 text-green-300 border-green-800/40',
  general_waste: 'bg-gray-100 text-gray-700 border-gray-300/40',
  destruction: 'bg-orange-900/40 text-orange-300 border-orange-800/40',
  bsf_intake: 'bg-lime-900/40 text-lime-300 border-lime-800/40',
  clinical_waste: 'bg-purple-900/40 text-purple-300 border-purple-800/40',
  e_waste: 'bg-cyan-900/40 text-cyan-300 border-cyan-800/40',
  construction_waste: 'bg-amber-900/40 text-amber-300 border-amber-800/40',
}

function jobTypeLabel(type: string): string {
  return type
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

// ---------------------------------------------------------------------------
// Priority indicator
// ---------------------------------------------------------------------------

const PRIORITY_DOT: Record<string, string> = {
  low: 'bg-slate-500',
  normal: 'bg-brand-400',
  high: 'bg-amber-400',
  urgent: 'bg-red-500 animate-pulse',
}

// ---------------------------------------------------------------------------
// Kanban card
// ---------------------------------------------------------------------------

interface KanbanCardProps {
  job: Job
  onClick: (job: Job) => void
}

function KanbanCard({ job, onClick }: KanbanCardProps) {
  const typeColorClass =
    JOB_TYPE_COLORS[job.job_type] ??
    'bg-gray-100 text-gray-700 border-gray-300/40'

  const priorityDot =
    PRIORITY_DOT[job.priority] ?? PRIORITY_DOT.normal

  return (
    <div
      onClick={() => onClick(job)}
      className={cn(
        'bg-white border border-gray-200 rounded-lg p-3 cursor-pointer',
        'transition-all duration-150',
        'hover:border-slate-500 hover:shadow-md hover:shadow-black/30',
        'active:scale-[0.99]',
        job.priority === 'urgent' && 'border-red-800/60 hover:border-red-700',
      )}
    >
      {/* Top row: job number + priority dot */}
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-2">
          {/* Priority dot */}
          <span
            className={cn(
              'w-2 h-2 rounded-full flex-shrink-0',
              priorityDot,
            )}
            title={`Priority: ${job.priority}`}
          />
          <span className="text-xs font-bold text-gray-900 font-mono">
            {job.job_number}
          </span>
        </div>
        <button
          onClick={(e) => e.stopPropagation()}
          className="text-gray-400 hover:text-gray-700 transition-colors p-0.5 rounded"
          aria-label="Job options"
        >
          <MoreHorizontal className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Client name */}
      <p className="text-sm font-semibold text-gray-700 truncate mb-2 leading-snug">
        {job.client_name}
      </p>

      {/* Job type badge */}
      <span
        className={cn(
          'inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold border leading-none mb-3',
          typeColorClass,
        )}
      >
        {jobTypeLabel(job.job_type)}
      </span>

      {/* Details */}
      <div className="flex flex-col gap-1.5">
        {/* Date */}
        <div className="flex items-center gap-1.5 text-[11px] text-gray-500">
          <Calendar className="w-3 h-3 flex-shrink-0 text-gray-400" />
          <span>{formatDate(job.scheduled_date)}</span>
          {job.scheduled_time && (
            <span className="text-gray-400">{job.scheduled_time}</span>
          )}
        </div>

        {/* Driver */}
        {job.driver_name && (
          <div className="flex items-center gap-1.5 text-[11px] text-gray-500">
            <User className="w-3 h-3 flex-shrink-0 text-gray-400" />
            <span className="truncate">{job.driver_name}</span>
          </div>
        )}

        {/* Vehicle */}
        {job.vehicle_registration && (
          <div className="flex items-center gap-1.5 text-[11px] text-gray-500">
            <Truck className="w-3 h-3 flex-shrink-0 text-gray-400" />
            <span>{job.vehicle_registration}</span>
          </div>
        )}

        {/* Weight */}
        {(job.actual_weight_kg ?? job.estimated_weight_kg) != null && (
          <div className="flex items-center gap-1.5 text-[11px] text-gray-500">
            <Weight className="w-3 h-3 flex-shrink-0 text-gray-400" />
            <span>
              {formatWeight(job.actual_weight_kg ?? job.estimated_weight_kg)}
              {!job.actual_weight_kg && (
                <span className="text-gray-400 ml-1">(est.)</span>
              )}
            </span>
          </div>
        )}
      </div>

      {/* SW codes */}
      {job.sw_codes && job.sw_codes.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {job.sw_codes.slice(0, 3).map((code) => (
            <span
              key={code}
              className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-bold bg-red-900/30 text-red-400 border border-red-800/30 leading-none"
            >
              {code}
            </span>
          ))}
          {job.sw_codes.length > 3 && (
            <span className="text-[10px] text-gray-400">
              +{job.sw_codes.length - 3}
            </span>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Kanban column
// ---------------------------------------------------------------------------

interface KanbanColumnProps {
  status: JobStatus
  label: string
  color: string
  bgColor: string
  jobs: Job[]
  onCardClick: (job: Job) => void
  onAddJob?: () => void
}

function KanbanColumn({
  status,
  label,
  color,
  bgColor,
  jobs,
  onCardClick,
  onAddJob,
}: KanbanColumnProps) {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div
      className={cn(
        'flex-shrink-0 w-[280px] flex flex-col rounded-xl border border-gray-200',
        bgColor,
      )}
    >
      {/* Column header */}
      <div className="flex items-center justify-between px-3 py-3 border-b border-gray-100">
        <div className="flex items-center gap-2">
          <StatusBadge status={status} size="sm" dot />
          <span className={cn('text-xs font-bold', color)}>{label}</span>
          <span
            className={cn(
              'flex items-center justify-center min-w-[1.25rem] h-5 px-1.5 rounded-full text-[10px] font-bold',
              'bg-gray-100 text-gray-700',
            )}
          >
            {jobs.length}
          </span>
        </div>

        <div className="flex items-center gap-1">
          {/* Add job button (for actionable statuses) */}
          {status === 'draft' && onAddJob && (
            <button
              onClick={onAddJob}
              className="flex items-center justify-center w-6 h-6 rounded-md text-gray-400 hover:text-green-400 hover:bg-gray-100 transition-colors"
              aria-label="Add new job"
              title="New job"
            >
              <Plus className="w-3.5 h-3.5" />
            </button>
          )}

          {/* Collapse toggle */}
          <button
            onClick={() => setCollapsed((v) => !v)}
            className="flex items-center justify-center w-6 h-6 rounded-md text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors"
            aria-label={collapsed ? 'Expand column' : 'Collapse column'}
          >
            {collapsed ? (
              <ChevronDown className="w-3.5 h-3.5" />
            ) : (
              <ChevronUp className="w-3.5 h-3.5" />
            )}
          </button>
        </div>
      </div>

      {/* Cards */}
      {!collapsed && (
        <div className="flex flex-col gap-2 p-2 overflow-y-auto max-h-[calc(100vh-280px)] scrollbar-hide">
          {jobs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 px-3 text-center">
              <div className="w-8 h-8 rounded-full bg-white flex items-center justify-center mb-2">
                <span className="text-gray-400 text-lg">○</span>
              </div>
              <p className="text-xs text-gray-400">No jobs</p>
            </div>
          ) : (
            jobs.map((job) => (
              <KanbanCard key={job.id} job={job} onClick={onCardClick} />
            ))
          )}
        </div>
      )}

      {/* Collapsed summary */}
      {collapsed && jobs.length > 0 && (
        <div className="px-3 py-2">
          <p className="text-[11px] text-gray-400">
            {jobs.length} job{jobs.length !== 1 ? 's' : ''} hidden
          </p>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main JobKanban component
// ---------------------------------------------------------------------------

interface JobKanbanProps {
  jobs: Job[]
  loading?: boolean
  onJobClick?: (job: Job) => void
  onAddJob?: () => void
}

export default function JobKanban({
  jobs,
  loading = false,
  onJobClick,
  onAddJob,
}: JobKanbanProps) {
  const router = useRouter()

  // Group jobs by status
  const grouped: Record<JobStatus, Job[]> = {} as Record<JobStatus, Job[]>
  for (const col of JOB_STATUS_COLUMNS) {
    grouped[col.status] = []
  }
  for (const job of jobs) {
    if (grouped[job.status]) {
      grouped[job.status].push(job)
    }
  }

  // Sort within each column by scheduled_date ascending, urgent first
  for (const col of JOB_STATUS_COLUMNS) {
    grouped[col.status].sort((a, b) => {
      const priorityOrder: Record<string, number> = {
        urgent: 0,
        high: 1,
        normal: 2,
        low: 3,
      }
      const pa = priorityOrder[a.priority] ?? 2
      const pb = priorityOrder[b.priority] ?? 2
      if (pa !== pb) return pa - pb
      return (
        new Date(a.scheduled_date).getTime() -
        new Date(b.scheduled_date).getTime()
      )
    })
  }

  function handleCardClick(job: Job) {
    if (onJobClick) {
      onJobClick(job)
    } else {
      router.push(`/jobs/${job.id}`)
    }
  }

  // Loading skeleton
  if (loading) {
    return (
      <div className="flex gap-4 overflow-x-auto pb-4 scrollbar-hide">
        {JOB_STATUS_COLUMNS.map((col) => (
          <div
            key={col.status}
            className="flex-shrink-0 w-[280px] bg-gray-50 rounded-xl border border-gray-200 animate-pulse"
          >
            <div className="flex items-center gap-2 px-3 py-3 border-b border-gray-200">
              <div className="h-5 w-20 rounded-full bg-gray-100" />
              <div className="h-5 w-5 rounded-full bg-gray-100" />
            </div>
            <div className="flex flex-col gap-2 p-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="h-28 rounded-lg bg-white" />
              ))}
            </div>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="flex gap-4 overflow-x-auto pb-4 scrollbar-hide min-h-[400px]">
      {JOB_STATUS_COLUMNS.map((col) => (
        <KanbanColumn
          key={col.status}
          status={col.status}
          label={col.label}
          color={col.color}
          bgColor={col.bgColor}
          jobs={grouped[col.status] ?? []}
          onCardClick={handleCardClick}
          onAddJob={col.status === 'draft' ? onAddJob : undefined}
        />
      ))}
    </div>
  )
}

