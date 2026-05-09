'use client'

import { useQuery } from '@tanstack/react-query'
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  TooltipProps,
} from 'recharts'
import { ClipboardList, ExternalLink } from 'lucide-react'
import Link from 'next/link'
import { cn } from '@/lib/utils'
import { jobsApi } from '@/lib/api'
import type { JobStatus } from '@/types/job'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface StatusSlice {
  status: JobStatus
  label: string
  count: number
  color: string
  bgClass: string
  textClass: string
}

// ---------------------------------------------------------------------------
// Status config
// ---------------------------------------------------------------------------

const STATUS_CONFIG: Record<
  JobStatus,
  { label: string; color: string; bgClass: string; textClass: string }
> = {
  draft: {
    label: 'Draft',
    color: '#64748b',
    bgClass: 'bg-gray-100',
    textClass: 'text-gray-600',
  },
  confirmed: {
    label: 'Confirmed',
    color: '#3b82f6',
    bgClass: 'bg-brand-50',
    textClass: 'text-brand-600',
  },
  dispatched: {
    label: 'Dispatched',
    color: '#8b5cf6',
    bgClass: 'bg-violet-50',
    textClass: 'text-violet-600',
  },
  in_progress: {
    label: 'In Progress',
    color: '#f59e0b',
    bgClass: 'bg-amber-50',
    textClass: 'text-amber-600',
  },
  completed: {
    label: 'Completed',
    color: '#22c55e',
    bgClass: 'bg-green-50',
    textClass: 'text-green-600',
  },
  invoiced: {
    label: 'Invoiced',
    color: '#a855f7',
    bgClass: 'bg-purple-50',
    textClass: 'text-purple-600',
  },
  cancelled: {
    label: 'Cancelled',
    color: '#ef4444',
    bgClass: 'bg-red-50',
    textClass: 'text-red-500',
  },
}

// ---------------------------------------------------------------------------
// Placeholder data
// ---------------------------------------------------------------------------

const PLACEHOLDER_COUNTS: Record<JobStatus, number> = {
  draft: 0,
  confirmed: 0,
  dispatched: 0,
  in_progress: 0,
  completed: 0,
  invoiced: 0,
  cancelled: 0,
}

// ---------------------------------------------------------------------------
// Custom Tooltip
// ---------------------------------------------------------------------------

function CustomTooltip({ active, payload }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null

  const entry = payload[0]
  const slice = entry?.payload as StatusSlice | undefined
  if (!slice) return null

  const total = payload[0]?.payload?.total as number | undefined

  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-lg px-4 py-3 min-w-[160px]">
      <div className="flex items-center gap-2 mb-2">
        <span
          className="w-3 h-3 rounded-full flex-shrink-0"
          style={{ backgroundColor: slice.color }}
        />
        <span className="text-sm font-semibold text-gray-900">{slice.label}</span>
      </div>
      <div className="flex items-center justify-between gap-4">
        <span className="text-xs text-gray-500">Jobs</span>
        <span className="text-sm font-bold text-gray-900">{slice.count}</span>
      </div>
      {total != null && total > 0 && (
        <div className="flex items-center justify-between gap-4 mt-0.5">
          <span className="text-xs text-gray-500">Share</span>
          <span className="text-xs font-semibold text-gray-700">
            {((slice.count / total) * 100).toFixed(1)}%
          </span>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Custom legend
// ---------------------------------------------------------------------------

interface LegendItemProps {
  slice: StatusSlice
  total: number
}

function LegendItem({ slice, total }: LegendItemProps) {
  const pct = total > 0 ? (slice.count / total) * 100 : 0

  return (
    <div className="flex items-center justify-between gap-2 py-1.5 px-2 rounded-lg hover:bg-gray-50 transition-colors group">
      <div className="flex items-center gap-2 min-w-0">
        <span
          className="w-2.5 h-2.5 rounded-full flex-shrink-0"
          style={{ backgroundColor: slice.color }}
        />
        <span className="text-xs text-gray-700 truncate group-hover:text-gray-900 transition-colors">
          {slice.label}
        </span>
      </div>
      <div className="flex items-center gap-3 flex-shrink-0">
        <div className="hidden sm:flex w-20 h-1.5 bg-gray-200 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${pct}%`,
              backgroundColor: slice.color,
            }}
          />
        </div>
        <span className="text-xs font-bold text-gray-900 tabular-nums w-6 text-right">
          {slice.count}
        </span>
        <span className="text-[10px] text-gray-400 tabular-nums w-10 text-right">
          {pct.toFixed(0)}%
        </span>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------

function Skeleton() {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5 animate-pulse">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-9 h-9 rounded-lg bg-gray-200" />
        <div className="flex flex-col gap-1.5">
          <div className="h-4 w-32 rounded bg-gray-200" />
          <div className="h-3 w-48 rounded bg-gray-200" />
        </div>
      </div>
      <div className="flex gap-6">
        <div className="w-[160px] h-[160px] rounded-full bg-gray-200 flex-shrink-0" />
        <div className="flex-1 flex flex-col gap-2 pt-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-6 rounded bg-gray-200" />
          ))}
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function JobStatusSummary() {
  const { data: rawCounts, isLoading, error } = useQuery({
    queryKey: ['job-status-counts'],
    queryFn: async () => {
      try {
        const result = await jobsApi.getStatusCounts()
        // API returns { total, by_status: { draft: n, confirmed: n, ... } }
        const byStatus = (result as { by_status?: Record<JobStatus, number> })?.by_status
        if (!byStatus) {
          console.error('JobStatusSummary: API returned invalid data structure:', result)
        }
        return byStatus ?? null
      } catch (err) {
        console.error('JobStatusSummary: API call failed:', err)
        return null
      }
    },
    staleTime: 0,
    refetchInterval: 30_000,
  })

  const counts: Record<JobStatus, number> = rawCounts ?? PLACEHOLDER_COUNTS

  // Build slices (exclude statuses with 0 count for cleaner pie)
  const slices: StatusSlice[] = (Object.entries(STATUS_CONFIG) as Array<[JobStatus, typeof STATUS_CONFIG[JobStatus]]>)
    .map(([status, cfg]) => ({
      status,
      ...cfg,
      count: counts[status] ?? 0,
    }))
    .filter((s) => s.count > 0)

  const total = slices.reduce((s, d) => s + d.count, 0)

  // Enrich slices with total for tooltip
  const enrichedSlices = slices.map((s) => ({ ...s, total }))

  if (isLoading) return <Skeleton />

  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between gap-4 px-5 pt-5 pb-4 border-b border-gray-100">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-brand-50 border border-brand-200">
            <ClipboardList className="w-4 h-4 text-brand-400" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-gray-900">Job Status Summary</h3>
            <p className="text-xs text-gray-400 mt-0.5">
              {total} total jobs across all statuses
            </p>
          </div>
        </div>

        <Link
          href="/jobs"
          className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-900 transition-colors"
        >
          View all
          <ExternalLink className="w-3 h-3" />
        </Link>
      </div>

      {/* Content */}
      <div className="p-5">
        {total === 0 ? (
          // Empty state
          <div className="flex flex-col items-center justify-center py-10 text-center">
            <div className="flex items-center justify-center w-12 h-12 rounded-full bg-gray-100 mb-3">
              <ClipboardList className="w-5 h-5 text-gray-400" />
            </div>
            <p className="text-sm font-semibold text-gray-500">No jobs found</p>
            <p className="text-xs text-gray-400 mt-1">
              Jobs will appear here once created.
            </p>
          </div>
        ) : (
          <div className="flex flex-col sm:flex-row items-center gap-4 sm:gap-6">
            {/* Pie chart */}
            <div className="relative flex-shrink-0">
              <ResponsiveContainer width={180} height={180}>
                <PieChart>
                  <Pie
                    data={enrichedSlices}
                    cx="50%"
                    cy="50%"
                    innerRadius={52}
                    outerRadius={78}
                    paddingAngle={2}
                    dataKey="count"
                    strokeWidth={0}
                  >
                    {enrichedSlices.map((slice) => (
                      <Cell
                        key={slice.status}
                        fill={slice.color}
                        opacity={0.9}
                      />
                    ))}
                  </Pie>
                  <Tooltip content={<CustomTooltip />} />
                </PieChart>
              </ResponsiveContainer>

              {/* Centre label */}
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                <span className="text-2xl font-bold text-gray-900 leading-none">
                  {total}
                </span>
                <span className="text-[11px] text-gray-500 mt-0.5 font-medium">
                  Total
                </span>
              </div>
            </div>

            {/* Legend */}
            <div className="flex-1 w-full">
              {/* Column headers */}
              <div className="flex items-center justify-between px-2 mb-1">
                <span className="text-[10px] text-gray-400 uppercase tracking-wider font-semibold">
                  Status
                </span>
                <div className="flex items-center gap-3">
                  <span className="text-[10px] text-gray-400 uppercase tracking-wider font-semibold hidden sm:block w-20 text-right">
                    Bar
                  </span>
                  <span className="text-[10px] text-gray-400 uppercase tracking-wider font-semibold w-6 text-right">
                    #
                  </span>
                  <span className="text-[10px] text-gray-400 uppercase tracking-wider font-semibold w-10 text-right">
                    %
                  </span>
                </div>
              </div>

              <div className="flex flex-col">
                {enrichedSlices.map((slice) => (
                  <LegendItem key={slice.status} slice={slice} total={total} />
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Active jobs highlight */}
        {total > 0 && (
          <div className="mt-4 pt-4 border-t border-gray-100">
            <div className="grid grid-cols-3 gap-3">
              {(['confirmed', 'dispatched', 'in_progress'] as JobStatus[]).map((status) => {
                const cfg = STATUS_CONFIG[status]
                const count = counts[status] ?? 0
                return (
                  <div
                    key={status}
                    className={cn(
                      'flex flex-col items-center gap-1 p-2.5 rounded-lg border',
                      cfg.bgClass,
                      'border-current/20'
                    )}
                    style={{ borderColor: `${cfg.color}30` }}
                  >
                    <span
                      className={cn('text-xl font-bold leading-none', cfg.textClass)}
                    >
                      {count}
                    </span>
                    <span className="text-[10px] text-gray-400 font-medium text-center leading-tight">
                      {cfg.label}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Placeholder indicator */}
        {!rawCounts && (
          <p className="mt-3 text-center text-[11px] text-gray-400 italic">
            Sample data — connect to backend for live counts
          </p>
        )}
      </div>
    </div>
  )
}
