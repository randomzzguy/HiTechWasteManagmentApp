'use client'
import { useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, ClipboardList, Truck, FileText, AlertCircle, ChevronRight, Upload, RefreshCw } from 'lucide-react'
import { jobsApi } from '@/lib/api'
import { formatDate, formatDateTime, formatWeight, snakeToTitle, cn } from '@/lib/utils'
import UploadDocumentDialog from '@/components/jobs/UploadDocumentDialog'

const STATUS_STYLES: Record<string, string> = {
  draft:       'bg-gray-100 text-gray-600 border-gray-300',
  confirmed:   'bg-brand-50 text-brand-600 border-brand-200',
  dispatched:  'bg-violet-50 text-violet-600 border-violet-200',
  in_progress: 'bg-amber-50 text-amber-600 border-amber-200',
  completed:   'bg-green-50 text-green-600 border-green-200',
  invoiced:    'bg-brand-50 text-brand-600 border-brand-200',
  cancelled:   'bg-red-50 text-red-500 border-red-200',
}
const PIPELINE = ['draft','confirmed','dispatched','in_progress','completed','invoiced']

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const qc = useQueryClient()
  const [uploadOpen, setUploadOpen] = useState(false)

  const { data: job, isLoading, isError } = useQuery({
    queryKey: ['job', id],
    queryFn: () => jobsApi.get(id),
    staleTime: 30_000,
  })

  const statusMutation = useMutation({
    mutationFn: ({ status }: { status: string }) => jobsApi.updateStatus(id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['job', id] }),
  })

  const j = job as Record<string, unknown> | null

  if (isLoading) return (
    <div className="flex items-center justify-center h-64">
      <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
    </div>
  )

  if (isError || !j) return (
    <div className="flex flex-col items-center justify-center h-64 gap-3 text-gray-400">
      <AlertCircle className="w-10 h-10" />
      <p>Job not found.</p>
      <button onClick={() => router.back()} className="text-brand-600 hover:underline text-sm">Go back</button>
    </div>
  )

  const currentIdx = PIPELINE.indexOf(j.status as string)
  const nextStatus = PIPELINE[currentIdx + 1]

  return (
    <div className="flex flex-col gap-6 max-w-5xl">
      {/* Header */}
      <div className="flex items-start gap-4 flex-wrap">
        <button
          onClick={() => router.back()}
          className="mt-1 p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-700 transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-2xl font-bold text-gray-900 font-mono">{j.job_number as string}</h1>
            <span className={cn(
              'inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold border',
              STATUS_STYLES[j.status as string] ?? 'bg-gray-100 text-gray-600 border-gray-300'
            )}>
              {snakeToTitle(j.status as string)}
            </span>
          </div>
          <p className="text-sm text-gray-500 mt-1">
            {snakeToTitle(j.job_type as string)} · {j.client_name as string}
          </p>
        </div>
        {nextStatus && (
          <button
            onClick={() => statusMutation.mutate({ status: nextStatus })}
            disabled={statusMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white text-sm font-semibold rounded-lg transition-colors disabled:opacity-50"
          >
            {statusMutation.isPending
              ? <RefreshCw className="w-4 h-4 animate-spin" />
              : <ChevronRight className="w-4 h-4" />
            }
            Mark {snakeToTitle(nextStatus)}
          </button>
        )}
      </div>

      {/* Details grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-3">
          <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
            <ClipboardList className="w-4 h-4 text-brand-600" /> Job Details
          </h3>
          {[
            ['Client', j.client_name],
            ['Type', snakeToTitle(j.job_type as string)],
            ['Scheduled', j.scheduled_date ? formatDate(j.scheduled_date as string) : '—'],
            ['Address', j.collection_address],
            ['Est. Weight', j.estimated_weight_kg ? formatWeight(j.estimated_weight_kg as number) : '—'],
            ['Actual Weight', j.actual_weight_kg ? formatWeight(j.actual_weight_kg as number) : '—'],
            ['Disposal Route', j.disposal_route ? snakeToTitle(j.disposal_route as string) : '—'],
            ['Completed', j.completed_at ? formatDateTime(j.completed_at as string) : '—'],
          ].filter(([, v]) => v && v !== '—').map(([label, value]) => (
            <div key={label as string} className="flex justify-between gap-4">
              <span className="text-xs text-gray-500 flex-shrink-0">{label as string}</span>
              <span className="text-xs text-gray-800 text-right font-medium">{String(value ?? '')}</span>
            </div>
          ))}
        </div>

        <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-3">
          <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
            <Truck className="w-4 h-4 text-brand-600" /> Vehicle Assignment
          </h3>
          {[
            ['Driver', j.driver_name],
            ['Vehicle', j.vehicle_registration],
            ['Supervisor', j.supervisor_name],
          ].map(([label, value]) => (
            <div key={label as string} className="flex justify-between gap-4">
              <span className="text-xs text-gray-500">{label as string}</span>
              <span className="text-xs text-gray-800 font-medium">{String(value ?? '') || '—'}</span>
            </div>
          ))}
          {!!j.notes && (
            <div className="pt-2 border-t border-gray-100">
              <p className="text-xs text-gray-500 mb-1">Notes</p>
              <p className="text-xs text-gray-700 whitespace-pre-wrap">{j.notes as string}</p>
            </div>
          )}
        </div>
      </div>

      {/* Documents */}
      <div className="bg-white border border-gray-200 rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
            <FileText className="w-4 h-4 text-brand-600" /> Documents
          </h3>
          <button
            onClick={() => setUploadOpen(true)}
            className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-900 px-3 py-1.5 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">
            <Upload className="w-3.5 h-3.5" /> Upload
          </button>
        </div>
        {Array.isArray(j.documents) && (j.documents as unknown[]).length > 0 ? (
          <div className="space-y-2">
            {(j.documents as Record<string, unknown>[]).map((doc) => (
              <div key={doc.id as string} className="flex items-center justify-between p-3 bg-gray-50 border border-gray-200 rounded-lg">
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4 text-gray-400" />
                  <span className="text-sm text-gray-800">{(doc.name as string) || (doc.title as string)}</span>
                </div>
                <a
                  href={(doc.url as string) || '#'}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-brand-600 hover:underline font-medium"
                >
                  Download
                </a>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-400 text-center py-6">No documents attached yet</p>
        )}
      </div>

      <UploadDocumentDialog
        open={uploadOpen}
        onOpenChange={setUploadOpen}
        jobId={id}
        onSuccess={() => qc.invalidateQueries({ queryKey: ['job', id] })}
      />
    </div>
  )
}
