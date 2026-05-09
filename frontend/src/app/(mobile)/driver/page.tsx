'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useSession } from 'next-auth/react'
import { jobsApi } from '@/lib/api'
import { toast } from 'sonner'
import {
  MapPin, Clock, CheckCircle2, Truck, ChevronRight,
  AlertCircle, RefreshCw, Package, Phone, LogOut,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { signOut } from 'next-auth/react'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Job {
  id: string
  job_number: string
  status: string
  job_type: string
  client_name?: string
  collection_address?: string
  scheduled_date?: string
  scheduled_time_start?: string
  estimated_weight_kg?: number
  notes?: string
  pic_phone?: string
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STATUS_PIPELINE = ['draft', 'confirmed', 'dispatched', 'in_progress', 'completed', 'invoiced']

const STATUS_CONFIG: Record<string, { label: string; bg: string; text: string; dot: string }> = {
  confirmed:   { label: 'Confirmed',   bg: 'bg-brand-50',   text: 'text-brand-700',   dot: 'bg-brand-500' },
  dispatched:  { label: 'Dispatched',  bg: 'bg-violet-50', text: 'text-violet-700', dot: 'bg-violet-500' },
  in_progress: { label: 'In Progress', bg: 'bg-amber-50',  text: 'text-amber-700',  dot: 'bg-amber-500' },
  completed:   { label: 'Completed',   bg: 'bg-green-50',  text: 'text-green-700',  dot: 'bg-green-500' },
}

const NEXT_ACTION: Record<string, { label: string; bg: string }> = {
  confirmed:   { label: 'Start Journey',    bg: 'bg-violet-600 hover:bg-violet-700' },
  dispatched:  { label: 'Arrive at Site',   bg: 'bg-amber-500 hover:bg-amber-600' },
  in_progress: { label: 'Mark Completed',   bg: 'bg-green-600 hover:bg-green-700' },
}

// ---------------------------------------------------------------------------
// Job Card
// ---------------------------------------------------------------------------

function JobCard({ job, onAdvance, isPending }: {
  job: Job
  onAdvance: (id: string, nextStatus: string) => void
  isPending: boolean
}) {
  const [expanded, setExpanded] = useState(false)
  const cfg = STATUS_CONFIG[job.status]
  const action = NEXT_ACTION[job.status]
  const currentIdx = STATUS_PIPELINE.indexOf(job.status)
  const nextStatus = STATUS_PIPELINE[currentIdx + 1]

  return (
    <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
      {/* Card header */}
      <button
        className="w-full text-left p-4 flex items-start gap-3"
        onClick={() => setExpanded((v) => !v)}
      >
        <div className={cn('mt-0.5 w-2.5 h-2.5 rounded-full flex-shrink-0', cfg?.dot ?? 'bg-gray-400')} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <span className="font-mono text-sm font-bold text-gray-900">{job.job_number}</span>
            {cfg && (
              <span className={cn('text-[11px] font-semibold px-2 py-0.5 rounded-full', cfg.bg, cfg.text)}>
                {cfg.label}
              </span>
            )}
          </div>
          <p className="text-sm font-semibold text-gray-800 mt-0.5 truncate">
            {job.client_name ?? 'Unknown Client'}
          </p>
          {job.collection_address && (
            <div className="flex items-start gap-1.5 mt-1.5">
              <MapPin className="w-3.5 h-3.5 text-gray-400 flex-shrink-0 mt-0.5" />
              <p className="text-xs text-gray-500 leading-snug">{job.collection_address}</p>
            </div>
          )}
          {job.scheduled_time_start && (
            <div className="flex items-center gap-1.5 mt-1">
              <Clock className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
              <p className="text-xs text-gray-500">{job.scheduled_time_start}</p>
            </div>
          )}
        </div>
        <ChevronRight className={cn('w-4 h-4 text-gray-400 flex-shrink-0 mt-1 transition-transform', expanded && 'rotate-90')} />
      </button>

      {/* Expanded details */}
      {expanded && (
        <div className="px-4 pb-3 border-t border-gray-100 pt-3 space-y-2">
          {job.estimated_weight_kg && (
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <Package className="w-4 h-4 text-gray-400" />
              Est. {Number(job.estimated_weight_kg).toLocaleString()} kg
            </div>
          )}
          {job.notes && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-2.5">
              <p className="text-xs text-amber-800 font-medium mb-0.5">Notes</p>
              <p className="text-xs text-amber-700 leading-relaxed">{job.notes}</p>
            </div>
          )}
          {job.collection_address && (
            <a
              href={`https://maps.google.com/?q=${encodeURIComponent(job.collection_address)}`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-sm text-brand-600 font-medium py-1"
            >
              <MapPin className="w-4 h-4" />
              Open in Google Maps
            </a>
          )}
        </div>
      )}

      {/* Action button */}
      {action && nextStatus && (
        <div className="px-4 pb-4">
          <button
            onClick={() => onAdvance(job.id, nextStatus)}
            disabled={isPending}
            className={cn(
              'w-full py-3.5 rounded-xl text-white font-bold text-sm transition-colors disabled:opacity-50',
              action.bg
            )}
          >
            {isPending ? (
              <span className="flex items-center justify-center gap-2">
                <RefreshCw className="w-4 h-4 animate-spin" /> Updating…
              </span>
            ) : (
              action.label
            )}
          </button>
        </div>
      )}

      {/* Completed state */}
      {job.status === 'completed' && (
        <div className="px-4 pb-4">
          <div className="flex items-center justify-center gap-2 py-3 bg-green-50 rounded-xl border border-green-200">
            <CheckCircle2 className="w-5 h-5 text-green-600" />
            <span className="text-sm font-semibold text-green-700">Job Completed</span>
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function DriverPage() {
  const { data: session } = useSession()
  const qc = useQueryClient()
  const today = new Date().toISOString().split('T')[0]

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['driver-jobs', today],
    queryFn: () =>
      jobsApi.list({
        date_from: today,
        date_to: today,
        limit: 50,
      } as Parameters<typeof jobsApi.list>[0]),
    staleTime: 60_000,
    refetchInterval: 2 * 60_000,
  })

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      jobsApi.updateStatus(id, status),
    onSuccess: (_, { status }) => {
      qc.invalidateQueries({ queryKey: ['driver-jobs'] })
      const labels: Record<string, string> = {
        dispatched: 'Journey started',
        in_progress: 'Arrived at site',
        completed: 'Job completed ✓',
      }
      toast.success(labels[status] ?? 'Status updated')
    },
    onError: () => toast.error('Failed to update status'),
  })

  const allJobs = (data as { items?: Job[] } | null)?.items ?? []

  // Show only jobs assigned to this driver that are actionable
  const myJobs = allJobs.filter((j) =>
    ['confirmed', 'dispatched', 'in_progress', 'completed'].includes(j.status)
  )

  const activeCount = myJobs.filter((j) => j.status !== 'completed').length
  const completedCount = myJobs.filter((j) => j.status === 'completed').length

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Top bar */}
      <div className="bg-brand-700 text-white px-4 pt-safe-top pb-4">
        <div className="flex items-center justify-between pt-3">
          <div>
            <p className="text-xs text-brand-200 font-medium">Hi-Tech Waste Management</p>
            <h1 className="text-lg font-bold mt-0.5">
              {session?.user?.name?.split(' ')[0] ?? 'Driver'}&apos;s Jobs
            </h1>
          </div>
          <button
            onClick={() => signOut({ callbackUrl: '/login' })}
            className="p-2 rounded-lg bg-brand-600 hover:bg-brand-500 transition-colors"
            title="Sign out"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>

        {/* Date + summary */}
        <div className="flex items-center gap-3 mt-3">
          <div className="flex items-center gap-1.5 bg-brand-600/50 rounded-lg px-3 py-1.5">
            <Clock className="w-3.5 h-3.5 text-brand-200" />
            <span className="text-xs font-medium text-brand-100">
              {new Date().toLocaleDateString('en-MY', { weekday: 'short', day: 'numeric', month: 'short' })}
            </span>
          </div>
          <div className="flex items-center gap-1.5 bg-brand-600/50 rounded-lg px-3 py-1.5">
            <Truck className="w-3.5 h-3.5 text-brand-200" />
            <span className="text-xs font-medium text-brand-100">
              {activeCount} active · {completedCount} done
            </span>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="px-4 py-4 space-y-3 pb-safe-bottom">
        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="bg-white rounded-2xl border border-gray-200 p-4 animate-pulse">
                <div className="flex gap-3">
                  <div className="w-2.5 h-2.5 rounded-full bg-gray-200 mt-1" />
                  <div className="flex-1 space-y-2">
                    <div className="h-4 bg-gray-200 rounded w-1/3" />
                    <div className="h-3 bg-gray-200 rounded w-2/3" />
                    <div className="h-3 bg-gray-200 rounded w-1/2" />
                  </div>
                </div>
                <div className="mt-4 h-12 bg-gray-200 rounded-xl" />
              </div>
            ))}
          </div>
        ) : isError ? (
          <div className="flex flex-col items-center justify-center py-16 text-gray-400 gap-3">
            <AlertCircle className="w-10 h-10" />
            <p className="text-sm">Failed to load jobs</p>
            <button
              onClick={() => refetch()}
              className="text-brand-600 text-sm font-medium flex items-center gap-1.5"
            >
              <RefreshCw className="w-4 h-4" /> Try again
            </button>
          </div>
        ) : myJobs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-gray-400 gap-3">
            <CheckCircle2 className="w-12 h-12 text-green-400" />
            <p className="text-base font-semibold text-gray-700">All clear for today!</p>
            <p className="text-sm text-gray-400">No jobs scheduled for today.</p>
          </div>
        ) : (
          <>
            {/* Active jobs first */}
            {myJobs
              .filter((j) => j.status !== 'completed')
              .map((job) => (
                <JobCard
                  key={job.id}
                  job={job}
                  onAdvance={(id, status) => statusMutation.mutate({ id, status })}
                  isPending={statusMutation.isPending && statusMutation.variables?.id === job.id}
                />
              ))}

            {/* Completed jobs */}
            {completedCount > 0 && (
              <>
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider pt-2 px-1">
                  Completed Today
                </p>
                {myJobs
                  .filter((j) => j.status === 'completed')
                  .map((job) => (
                    <JobCard
                      key={job.id}
                      job={job}
                      onAdvance={(id, status) => statusMutation.mutate({ id, status })}
                      isPending={false}
                    />
                  ))}
              </>
            )}
          </>
        )}

        {/* Refresh button */}
        <button
          onClick={() => refetch()}
          className="w-full py-3 text-sm text-gray-500 flex items-center justify-center gap-2 hover:text-gray-700 transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh jobs
        </button>
      </div>
    </div>
  )
}
