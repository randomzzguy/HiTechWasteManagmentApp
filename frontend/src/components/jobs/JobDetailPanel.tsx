'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { X, ChevronRight, Truck, User, Calendar, Weight, FileText, RefreshCw } from 'lucide-react'
import { jobsApi } from '@/lib/api'
import { formatDate, formatDateTime, formatWeight, snakeToTitle, cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

const STATUS_PIPELINE = ['draft', 'confirmed', 'dispatched', 'in_progress', 'completed', 'invoiced']

const STATUS_VARIANT: Record<string, 'default' | 'secondary' | 'warning' | 'success' | 'info' | 'destructive'> = {
  draft:       'secondary',
  confirmed:   'info',
  dispatched:  'info',
  in_progress: 'warning',
  completed:   'success',
  invoiced:    'success',
}

interface JobDetailPanelProps {
  jobId: string
  onClose: () => void
}

export default function JobDetailPanel({ jobId, onClose }: JobDetailPanelProps) {
  const qc = useQueryClient()

  const { data: job, isLoading } = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => jobsApi.get(jobId),
    staleTime: 30_000,
  })

  const statusMutation = useMutation({
    mutationFn: (status: string) => jobsApi.updateStatus(jobId, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['job', jobId] }),
  })

  const j = job as Record<string, unknown> | null
  const currentIdx = j ? STATUS_PIPELINE.indexOf(j.status as string) : -1
  const nextStatus = STATUS_PIPELINE[currentIdx + 1]
  const hasAddress = !!j?.collection_address

  return (
    <div className="flex flex-col h-full bg-white border-l border-gray-200 w-96 flex-shrink-0">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
        <div>
          {j && <p className="font-mono text-sm font-bold text-green-400">{j.job_number as string}</p>}
          {j && <p className="text-xs text-gray-500">{snakeToTitle(j.job_type as string)}</p>}
        </div>
        <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500 hover:text-gray-900 transition-colors">
          <X className="w-4 h-4" />
        </button>
      </div>

      {isLoading ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="w-6 h-6 border-2 border-green-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : j ? (
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Status + advance */}
          <div className="flex items-center justify-between">
            <Badge variant={STATUS_VARIANT[j.status as string] ?? 'secondary'}>
              {snakeToTitle(j.status as string)}
            </Badge>
            {nextStatus && (
              <Button size="sm" onClick={() => statusMutation.mutate(nextStatus)} disabled={statusMutation.isPending}>
                {statusMutation.isPending ? <RefreshCw className="w-3 h-3 animate-spin mr-1" /> : <ChevronRight className="w-3 h-3 mr-1" />}
                {snakeToTitle(nextStatus)}
              </Button>
            )}
          </div>

          {/* Details */}
          {[
            { icon: User, label: 'Client', value: j.client_name as string },
            { icon: Calendar, label: 'Scheduled', value: j.scheduled_date ? formatDate(j.scheduled_date as string) : '—' },
            { icon: Truck, label: 'Vehicle', value: (j.vehicle_registration as string) || '—' },
            { icon: User, label: 'Driver', value: (j.driver_name as string) || '—' },
            { icon: Weight, label: 'Est. Weight', value: j.estimated_weight_kg ? formatWeight(j.estimated_weight_kg as number) : '—' },
            { icon: Weight, label: 'Actual Weight', value: j.actual_weight_kg ? formatWeight(j.actual_weight_kg as number) : '—' },
          ].map(({ icon: Icon, label, value }) => (
            <div key={label} className="flex items-start gap-3">
              <Icon className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-xs text-gray-400">{label}</p>
                <p className="text-sm text-gray-900">{String(value ?? '')}</p>
              </div>
            </div>
          ))}

          {hasAddress ? (
            <div className="p-3 bg-gray-100 rounded-lg">
              <p className="text-xs text-gray-400 mb-1">Collection Address</p>
              <p className="text-xs text-gray-700">{j.collection_address as string}</p>
            </div>
          ) : null}
          {!!(j.notes as string) ? (
            <div className="p-3 bg-gray-100 rounded-lg">
              <p className="text-xs text-gray-400 mb-1">Notes</p>
              <p className="text-xs text-gray-700 whitespace-pre-wrap">{j.notes as string}</p>
            </div>
          ) : null}

          {!!(j.completed_at as string) ? (
            <div className="flex items-center gap-2 text-xs text-green-400">
              <span className="w-2 h-2 rounded-full bg-green-400" />
              Completed {formatDateTime(j.completed_at as string)}
            </div>
          ) : null}
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">Job not found</div>
      )}

      {/* Footer */}
      <div className="p-4 border-t border-gray-200">
        <a href={`/jobs/${jobId}`} className="block w-full">
          <Button variant="outline" className="w-full">
            <FileText className="w-4 h-4 mr-2" /> Open Full Detail
          </Button>
        </a>
      </div>
    </div>
  )
}

