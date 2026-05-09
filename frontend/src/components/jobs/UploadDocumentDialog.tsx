'use client'

import { useState, useRef } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Upload, X, FileText, Loader2, AlertCircle } from 'lucide-react'
import { toast } from 'sonner'
import { jobsApi } from '@/lib/api'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface UploadDocumentDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  jobId: string
  onSuccess: () => void
}

const DOC_TYPES = [
  { value: 'delivery_order', label: 'Delivery Order' },
  { value: 'weighbridge_ticket', label: 'Weighbridge Ticket' },
  { value: 'consignment_note', label: 'Consignment Note' },
  { value: 'certificate', label: 'Certificate' },
  { value: 'photo', label: 'Photo / Evidence' },
  { value: 'invoice', label: 'Invoice' },
  { value: 'other', label: 'Other' },
]

const MAX_SIZE_MB = 20
const ACCEPTED = '.pdf,.doc,.docx,.jpg,.jpeg,.png,.txt,.csv'

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function UploadDocumentDialog({
  open,
  onOpenChange,
  jobId,
  onSuccess,
}: UploadDocumentDialogProps) {
  const [file, setFile] = useState<File | null>(null)
  const [docType, setDocType] = useState('other')
  const [dragOver, setDragOver] = useState(false)
  const [fileError, setFileError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const { mutate, isPending } = useMutation({
    mutationFn: () => {
      if (!file) throw new Error('No file selected')
      const formData = new FormData()
      formData.append('file', file)
      formData.append('doc_type', docType)
      return jobsApi.uploadDocument(jobId, formData)
    },
    onSuccess: () => {
      onSuccess()
      onOpenChange(false)
      handleReset()
      toast.success('Document uploaded successfully')
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Failed to upload document'
      toast.error(typeof msg === 'string' ? msg : 'Failed to upload document')
    },
  })

  function handleReset() {
    setFile(null)
    setDocType('other')
    setFileError(null)
    setDragOver(false)
  }

  function handleOpenChange(next: boolean) {
    if (!next) handleReset()
    onOpenChange(next)
  }

  function validateAndSetFile(f: File) {
    setFileError(null)
    if (f.size > MAX_SIZE_MB * 1024 * 1024) {
      setFileError(`File exceeds ${MAX_SIZE_MB} MB limit`)
      return
    }
    setFile(f)
  }

  function handleInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]
    if (f) validateAndSetFile(f)
    e.target.value = ''
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragOver(false)
    const f = e.dataTransfer.files?.[0]
    if (f) validateAndSetFile(f)
  }

  function formatSize(bytes: number) {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="bg-white border-gray-200 text-gray-900 sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-gray-900">Upload Document</DialogTitle>
        </DialogHeader>

        <div className="flex flex-col gap-4 mt-2">
          {/* Document type */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-gray-600 text-xs">Document Type</Label>
            <Select value={docType} onValueChange={setDocType}>
              <SelectTrigger className="bg-white border-gray-300 text-gray-900">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-white border-gray-200">
                {DOC_TYPES.map((t) => (
                  <SelectItem key={t.value} value={t.value} className="text-gray-900 focus:bg-gray-50">
                    {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Drop zone */}
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPTED}
            onChange={handleInputChange}
            className="sr-only"
            aria-hidden
          />

          {!file ? (
            <div
              role="button"
              tabIndex={0}
              onClick={() => inputRef.current?.click()}
              onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && inputRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              className={`flex flex-col items-center justify-center gap-3 p-8 rounded-xl border-2 border-dashed cursor-pointer transition-all ${
                dragOver
                  ? 'border-brand-500 bg-brand-50'
                  : 'border-gray-300 bg-gray-50 hover:border-brand-400 hover:bg-brand-50/30'
              }`}
            >
              <div className={`w-12 h-12 rounded-full flex items-center justify-center ${dragOver ? 'bg-brand-100' : 'bg-gray-100'}`}>
                <Upload className={`w-6 h-6 ${dragOver ? 'text-brand-600' : 'text-gray-400'}`} />
              </div>
              <div className="text-center">
                <p className="text-sm font-semibold text-gray-700">
                  {dragOver ? 'Release to upload' : 'Drop file here or click to browse'}
                </p>
                <p className="text-xs text-gray-400 mt-1">
                  PDF, Word, Excel, images · Max {MAX_SIZE_MB} MB
                </p>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-3 p-4 bg-brand-50 border border-brand-200 rounded-xl">
              <div className="w-10 h-10 rounded-lg bg-brand-100 flex items-center justify-center flex-shrink-0">
                <FileText className="w-5 h-5 text-brand-600" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-gray-900 truncate">{file.name}</p>
                <p className="text-xs text-gray-500">{formatSize(file.size)}</p>
              </div>
              <button
                type="button"
                onClick={() => setFile(null)}
                className="text-gray-400 hover:text-gray-700 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* File error */}
          {fileError && (
            <div className="flex items-center gap-2 text-xs text-red-500">
              <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
              {fileError}
            </div>
          )}

          {/* Footer */}
          <div className="flex justify-end gap-2 pt-1">
            <Button
              type="button"
              variant="ghost"
              onClick={() => onOpenChange(false)}
              className="text-gray-500 hover:text-gray-900"
            >
              Cancel
            </Button>
            <Button
              type="button"
              disabled={!file || isPending}
              onClick={() => mutate()}
              className="bg-brand-600 hover:bg-brand-700 text-white"
            >
              {isPending ? (
                <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Uploading…</>
              ) : (
                <><Upload className="w-4 h-4 mr-2" />Upload</>
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
