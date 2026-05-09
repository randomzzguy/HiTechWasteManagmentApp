'use client'

import { useRef, useState } from 'react'
import { Upload } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Progress } from '@/components/ui/progress'

const ACCEPTED_EXTENSIONS = '.pdf,.docx,.txt,.csv,.md,.png,.jpg,.jpeg,.webp,.tiff'
const MAX_SIZE_BYTES = 50 * 1024 * 1024 // 50 MB

const DOC_TYPES = [
  { value: 'regulation', label: 'Regulation' },
  { value: 'contract', label: 'Contract' },
  { value: 'sop', label: 'SOP' },
  { value: 'report', label: 'Report' },
  { value: 'manual', label: 'Manual' },
]

export interface UploadFormData {
  file: File
  title: string
  doc_type: string
  client_id?: string
}

interface KbUploadDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (data: UploadFormData) => void
  isUploading: boolean
  clients?: Array<{ id: string; name: string }>
}

export default function KbUploadDialog({
  open,
  onOpenChange,
  onSubmit,
  isUploading,
  clients = [],
}: KbUploadDialogProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [title, setTitle] = useState('')
  const [docType, setDocType] = useState('')
  const [clientId, setClientId] = useState('')
  const [fileError, setFileError] = useState<string | null>(null)

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null
    setFileError(null)
    if (file) {
      if (file.size > MAX_SIZE_BYTES) {
        setFileError(`File exceeds the 50 MB limit (${(file.size / 1024 / 1024).toFixed(1)} MB)`)
        setSelectedFile(null)
        return
      }
      setSelectedFile(file)
      if (!title) {
        // Pre-fill title from filename (strip extension)
        setTitle(file.name.replace(/\.[^/.]+$/, ''))
      }
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!selectedFile || !title.trim() || !docType) return
    onSubmit({
      file: selectedFile,
      title: title.trim(),
      doc_type: docType,
      client_id: clientId || undefined,
    })
  }

  function handleClose(open: boolean) {
    if (!isUploading) {
      if (!open) {
        // Reset form on close
        setSelectedFile(null)
        setTitle('')
        setDocType('')
        setClientId('')
        setFileError(null)
        if (fileInputRef.current) fileInputRef.current.value = ''
      }
      onOpenChange(open)
    }
  }

  const canSubmit = selectedFile && title.trim() && docType && !fileError && !isUploading

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="bg-white border-gray-200 text-gray-900 sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-gray-900">Upload Document</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* File picker */}
          <div className="space-y-1.5">
            <Label className="text-gray-600">File</Label>
            <div
              className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center cursor-pointer hover:border-brand-500 hover:bg-brand-50/30 transition-colors"
              onClick={() => fileInputRef.current?.click()}
            >
              {selectedFile ? (
                <div>
                  <p className="text-sm text-gray-900 font-medium truncate">{selectedFile.name}</p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-2">
                  <Upload className="w-6 h-6 text-gray-400" />
                  <p className="text-sm text-gray-500">Click to select a file</p>
                  <p className="text-xs text-gray-400">PDF, DOCX, TXT, CSV, MD, PNG, JPG, WEBP, TIFF · Max 50 MB</p>
                </div>
              )}
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPTED_EXTENSIONS}
              onChange={handleFileChange}
              className="hidden"
            />
            {fileError && (
              <p className="text-xs text-red-500">{fileError}</p>
            )}
          </div>

          {/* Title */}
          <div className="space-y-1.5">
            <Label htmlFor="kb-title" className="text-gray-600">
              Title <span className="text-red-500">*</span>
            </Label>
            <Input
              id="kb-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              maxLength={500}
              placeholder="Document title"
              className="bg-white border-gray-300 text-gray-900 placeholder:text-gray-400 focus:border-brand-500"
            />
          </div>

          {/* Doc type */}
          <div className="space-y-1.5">
            <Label className="text-gray-600">
              Document Type <span className="text-red-500">*</span>
            </Label>
            <Select value={docType} onValueChange={setDocType}>
              <SelectTrigger className="bg-white border-gray-300 text-gray-900">
                <SelectValue placeholder="Select type…" />
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

          {/* Optional client */}
          {clients.length > 0 && (
            <div className="space-y-1.5">
              <Label className="text-gray-600">Client (optional)</Label>
              <Select value={clientId} onValueChange={setClientId}>
                <SelectTrigger className="bg-white border-gray-300 text-gray-900">
                  <SelectValue placeholder="Platform-wide (no client)" />
                </SelectTrigger>
                <SelectContent className="bg-white border-gray-200">
                  <SelectItem value="" className="text-gray-900 focus:bg-gray-50">
                    Platform-wide
                  </SelectItem>
                  {clients.map((c) => (
                    <SelectItem key={c.id} value={c.id} className="text-gray-900 focus:bg-gray-50">
                      {c.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {/* Upload progress */}
          {isUploading && (
            <div className="space-y-1.5">
              <p className="text-xs text-gray-500">Uploading…</p>
              <Progress value={undefined} className="h-1.5 bg-gray-200" />
            </div>
          )}

          <DialogFooter className="gap-2">
            <Button
              type="button"
              variant="ghost"
              onClick={() => handleClose(false)}
              disabled={isUploading}
              className="text-gray-500 hover:text-gray-900"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={!canSubmit}
              className="bg-brand-600 hover:bg-brand-700 text-white"
            >
              {isUploading ? 'Uploading…' : 'Upload'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
