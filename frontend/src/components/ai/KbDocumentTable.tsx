'use client'

import { RefreshCw, Trash2 } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'

export interface DocumentRecord {
  id: string
  title: string
  doc_type: string
  mime_type: string | null
  ingested_into_rag: boolean
  ingestion_error: string | null
  file_size_bytes: number | null
  uploaded_at: string
  client_id: string | null
}

export type IngestionStatus = 'ingested' | 'pending' | 'failed'

export function deriveStatus(doc: DocumentRecord): IngestionStatus {
  if (doc.ingestion_error) return 'failed'
  if (doc.ingested_into_rag) return 'ingested'
  return 'pending'
}

function formatBytes(bytes: number | null): string {
  if (bytes === null || bytes === undefined) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatRelativeDate(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  if (days < 30) return `${days}d ago`
  return new Date(iso).toLocaleDateString()
}

interface StatusBadgeProps {
  doc: DocumentRecord
}

function StatusBadge({ doc }: StatusBadgeProps) {
  const status = deriveStatus(doc)

  const badge = (
    <span
      className={
        status === 'ingested'
          ? 'inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold border bg-green-50 text-green-600 border-green-200'
          : status === 'pending'
          ? 'inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold border bg-amber-50 text-amber-600 border-amber-200'
          : 'inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold border bg-red-50 text-red-600 border-red-200 cursor-help'
      }
    >
      {status === 'ingested' ? 'Ingested' : status === 'pending' ? 'Pending' : 'Failed'}
    </span>
  )

  if (status === 'failed' && doc.ingestion_error) {
    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>{badge}</TooltipTrigger>
          <TooltipContent className="max-w-xs text-xs">
            {doc.ingestion_error}
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    )
  }

  return badge
}

interface KbDocumentTableProps {
  documents: DocumentRecord[]
  isManagement: boolean
  onDelete: (doc: DocumentRecord) => void
  onReIngest: (doc: DocumentRecord) => void
  isDeleting: boolean
  isReIngesting: boolean
  deletingId?: string
  reIngestingId?: string
}

export default function KbDocumentTable({
  documents,
  isManagement,
  onDelete,
  onReIngest,
  isDeleting,
  isReIngesting,
  deletingId,
  reIngestingId,
}: KbDocumentTableProps) {
  if (documents.length === 0) {
    return (
      <div className="text-center py-12 text-gray-400">
        <p className="text-sm">No documents in the knowledge base yet.</p>
        {isManagement && (
          <p className="text-xs mt-1">Upload a document to get started.</p>
        )}
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left">
        <thead>
          <tr className="border-b border-gray-200 bg-gray-50">
            <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">
              Title
            </th>
            <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">
              Type
            </th>
            <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">
              Size
            </th>
            <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">
              Status
            </th>
            <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">
              Uploaded
            </th>
            {isManagement && (
              <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap text-right">
                Actions
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {documents.map((doc) => {
            const status = deriveStatus(doc)
            return (
              <tr key={doc.id} className="border-b border-gray-100 hover:bg-gray-50 transition-colors">
                <td className="px-4 py-3 text-gray-900 font-medium max-w-[200px] truncate">
                  {doc.title}
                </td>
                <td className="px-4 py-3">
                  <span className="text-xs text-gray-500 capitalize">{doc.doc_type}</span>
                </td>
                <td className="px-4 py-3 text-xs text-gray-500">
                  {formatBytes(doc.file_size_bytes)}
                </td>
                <td className="px-4 py-3">
                  <StatusBadge doc={doc} />
                </td>
                <td className="px-4 py-3 text-xs text-gray-500">
                  {formatRelativeDate(doc.uploaded_at)}
                </td>
                {isManagement && (
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      {status === 'failed' && (
                        <button
                          onClick={() => onReIngest(doc)}
                          disabled={isReIngesting && reIngestingId === doc.id}
                          className="h-7 px-2 text-xs text-amber-600 hover:text-amber-700 hover:bg-amber-50 rounded transition-colors disabled:opacity-50"
                          title="Re-ingest document"
                        >
                          <RefreshCw
                            className={`w-3.5 h-3.5 ${
                              isReIngesting && reIngestingId === doc.id
                                ? 'animate-spin'
                                : ''
                            }`}
                          />
                        </button>
                      )}
                      <button
                        onClick={() => onDelete(doc)}
                        disabled={isDeleting && deletingId === doc.id}
                        className="h-7 px-2 text-xs text-red-600 hover:text-red-700 hover:bg-red-50 rounded transition-colors disabled:opacity-50"
                        title="Delete document"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </td>
                )}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export function KbDocumentTableSkeleton() {
  return (
    <div className="space-y-2">
      {[1, 2, 3].map((i) => (
        <div key={i} className="flex items-center gap-4 p-3">
          <Skeleton className="h-4 w-48 bg-gray-200" />
          <Skeleton className="h-4 w-20 bg-gray-200" />
          <Skeleton className="h-4 w-16 bg-gray-200" />
          <Skeleton className="h-5 w-16 bg-gray-200 rounded" />
          <Skeleton className="h-4 w-20 bg-gray-200" />
        </div>
      ))}
    </div>
  )
}
