'use client'

import { useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useSession } from 'next-auth/react'
import { toast } from 'sonner'
import { AlertCircle, RefreshCw, Upload } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { aiApi } from '@/lib/api'
import KbStatsBar from './KbStatsBar'
import KbDocumentTable, {
  DocumentRecord,
  KbDocumentTableSkeleton,
  deriveStatus,
} from './KbDocumentTable'
import KbUploadDialog, { UploadFormData } from './KbUploadDialog'
import KbDeleteConfirmDialog from './KbDeleteConfirmDialog'

interface DocumentsResponse {
  total: number
  skip: number
  limit: number
  items: DocumentRecord[]
}

interface RagStatusResponse {
  documents?: {
    total_in_db?: number
    ingested_into_rag?: number
    pending_ingestion?: number
  }
  milvus?: {
    collections?: Array<{ name: string; row_count: number | string }>
  }
}

function getTotalMilvusChunks(ragStatus: RagStatusResponse | undefined): number {
  if (!ragStatus?.milvus?.collections) return 0
  return ragStatus.milvus.collections.reduce((sum, c) => {
    const count = typeof c.row_count === 'number' ? c.row_count : 0
    return sum + count
  }, 0)
}

export default function KnowledgeBaseManager() {
  const { data: session } = useSession()
  const queryClient = useQueryClient()
  const isManagement = ['management', 'superadmin'].includes(
    (session?.user as { role?: string } | undefined)?.role ?? ''
  )

  const [uploadOpen, setUploadOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<DocumentRecord | null>(null)
  const [deletingId, setDeletingId] = useState<string | undefined>()
  const [reIngestingId, setReIngestingId] = useState<string | undefined>()

  // Track previous document statuses for transition toasts
  const prevDocsRef = useRef<DocumentRecord[]>([])

  // ── Queries ──────────────────────────────────────────────────────────────

  const {
    data: docsData,
    isLoading: docsLoading,
    isError: docsError,
    refetch: refetchDocs,
  } = useQuery<DocumentsResponse>({
    queryKey: ['ai-documents'],
    queryFn: () => aiApi.listDocuments({ limit: 200 }) as unknown as Promise<DocumentsResponse>,
    refetchInterval: () => {
      const docs = queryClient.getQueryData<DocumentsResponse>(['ai-documents'])
      const hasPending = docs?.items?.some(
        (d) => !d.ingested_into_rag && !d.ingestion_error
      ) ?? false
      return hasPending ? 10_000 : false
    },
    select: (data) => {
      // Fire status-transition toasts
      const prev = prevDocsRef.current
      if (prev.length > 0) {
        data.items.forEach((doc) => {
          const prevDoc = prev.find((p) => p.id === doc.id)
          if (!prevDoc) return
          const prevStatus = deriveStatus(prevDoc)
          const newStatus = deriveStatus(doc)
          if (prevStatus === 'pending' && newStatus === 'ingested') {
            toast.success(`"${doc.title}" ingested successfully`)
          } else if (prevStatus === 'pending' && newStatus === 'failed') {
            toast.warning(`"${doc.title}" ingestion failed`)
          }
        })
      }
      prevDocsRef.current = data.items
      return data
    },
  })

  const { data: ragStatus } = useQuery<RagStatusResponse>({
    queryKey: ['rag-status'],
    queryFn: () => aiApi.getRagStatus() as Promise<RagStatusResponse>,
    refetchInterval: 30_000,
  })

  // ── Mutations ─────────────────────────────────────────────────────────────

  const uploadMutation = useMutation({
    mutationFn: (formData: FormData) => aiApi.uploadDocument(formData),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-documents'] })
      queryClient.invalidateQueries({ queryKey: ['rag-status'] })
      setUploadOpen(false)
      toast.success('Document uploaded and queued for ingestion')
    },
    onError: (err: unknown) => {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Failed to upload document'
      toast.error(detail)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => aiApi.deleteDocument(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-documents'] })
      queryClient.invalidateQueries({ queryKey: ['rag-status'] })
      setDeleteTarget(null)
      setDeletingId(undefined)
      toast.success('Document deleted')
    },
    onError: (err: unknown) => {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Failed to delete document'
      setDeletingId(undefined)
      toast.error(detail)
    },
  })

  const reIngestMutation = useMutation({
    mutationFn: (id: string) => aiApi.reIngestDocument(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-documents'] })
      setReIngestingId(undefined)
      toast.success('Re-ingestion queued')
    },
    onError: (err: unknown) => {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Failed to re-ingest document'
      setReIngestingId(undefined)
      toast.error(detail)
    },
  })

  // ── Handlers ──────────────────────────────────────────────────────────────

  function handleUploadSubmit(formData: UploadFormData) {
    const fd = new FormData()
    fd.append('file', formData.file)
    const params = new URLSearchParams({
      title: formData.title,
      doc_type: formData.doc_type,
    })
    if (formData.client_id) params.set('client_id', formData.client_id)
    uploadMutation.mutate(fd)
  }

  function handleDeleteConfirm() {
    if (!deleteTarget) return
    setDeletingId(deleteTarget.id)
    deleteMutation.mutate(deleteTarget.id)
  }

  function handleReIngest(doc: DocumentRecord) {
    setReIngestingId(doc.id)
    reIngestMutation.mutate(doc.id)
  }

  // ── Derived stats ─────────────────────────────────────────────────────────

  const docs = docsData?.items ?? []
  const total = docs.length
  const ingested = docs.filter((d) => deriveStatus(d) === 'ingested').length
  const pending = docs.filter((d) => deriveStatus(d) === 'pending').length
  const milvusChunks = getTotalMilvusChunks(ragStatus)

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-4">
      {/* Stats bar */}
      <KbStatsBar
        total={total}
        ingested={ingested}
        pending={pending}
        milvusChunks={milvusChunks}
      />

      {/* Content */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
          <span className="text-sm font-semibold text-gray-900">
            {docsLoading ? 'Loading documents…' : `${total} document${total !== 1 ? 's' : ''}`}
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => refetchDocs()}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-gray-500 hover:text-gray-900 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Refresh
            </button>
            {isManagement && (
              <button
                onClick={() => setUploadOpen(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-white bg-green-600 hover:bg-green-500 rounded-lg transition-colors"
              >
                <Upload className="w-3.5 h-3.5" />
                Upload
              </button>
            )}
          </div>
        </div>

        {docsError && (
          <div className="flex items-center gap-2 p-4 text-red-500 text-sm">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            Failed to load documents.
          </div>
        )}

        {docsLoading ? (
          <div className="p-4">
            <KbDocumentTableSkeleton />
          </div>
        ) : (
          <KbDocumentTable
            documents={docs}
            isManagement={isManagement}
            onDelete={(doc) => setDeleteTarget(doc)}
            onReIngest={handleReIngest}
            isDeleting={deleteMutation.isPending}
            isReIngesting={reIngestMutation.isPending}
            deletingId={deletingId}
            reIngestingId={reIngestingId}
          />
        )}
      </div>

      {/* Upload dialog */}
      <KbUploadDialog
        open={uploadOpen}
        onOpenChange={setUploadOpen}
        onSubmit={handleUploadSubmit}
        isUploading={uploadMutation.isPending}
      />

      {/* Delete confirm dialog */}
      <KbDeleteConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        document={deleteTarget}
        onConfirm={handleDeleteConfirm}
        isDeleting={deleteMutation.isPending}
      />
    </div>
  )
}
