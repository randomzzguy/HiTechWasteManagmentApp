'use client'

import { useState, useRef, useCallback, useId } from 'react'
import {
  Upload,
  X,
  FileText,
  Image,
  File,
  CheckCircle2,
  AlertCircle,
  Loader2,
  FolderOpen,
  Paperclip,
} from 'lucide-react'
import { cn } from '@/lib/utils'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type FileUploaderStatus = 'idle' | 'uploading' | 'success' | 'error'

export interface UploadedFile {
  id: string
  file: File
  name: string
  size: number
  type: string
  status: FileUploaderStatus
  progress: number
  error?: string
  url?: string
  previewUrl?: string
}

export interface FileUploaderProps {
  /** Accepted MIME types or file extensions (e.g. "image/*,.pdf") */
  accept?: string
  /** Whether multiple files can be selected */
  multiple?: boolean
  /** Maximum file size in bytes (default: 20 MB) */
  maxSize?: number
  /** Maximum number of files allowed */
  maxFiles?: number
  /** Current list of uploaded files (controlled) */
  files?: UploadedFile[]
  /** Called when files are added (before upload) */
  onFilesAdded?: (files: UploadedFile[]) => void
  /** Called when a file is removed */
  onFileRemove?: (fileId: string) => void
  /** Called with each file to perform the actual upload.
   *  Should update `progress` and `status` via onFileUpdate. */
  onUpload?: (file: UploadedFile) => Promise<void>
  /** Called when a file's metadata changes (progress, status, url, etc.) */
  onFileUpdate?: (fileId: string, update: Partial<UploadedFile>) => void
  /** Disabled state */
  disabled?: boolean
  /** Label shown in the dropzone */
  dropLabel?: string
  /** Sub-label shown in the dropzone */
  dropSubLabel?: string
  /** Whether to auto-upload as soon as files are added */
  autoUpload?: boolean
  /** Extra className on the root wrapper */
  className?: string
  /** Compact mode — smaller dropzone */
  compact?: boolean
  /** Show preview thumbnails for image files */
  showPreviews?: boolean
}

// ---------------------------------------------------------------------------
// File icon helper
// ---------------------------------------------------------------------------

function FileIcon({
  mimeType,
  className,
}: {
  mimeType: string
  className?: string
}) {
  if (mimeType.startsWith('image/')) {
    {/* eslint-disable-next-line jsx-a11y/alt-text */}
    return <Image className={cn('w-4 h-4', className)} />
  }
  if (
    mimeType === 'application/pdf' ||
    mimeType.includes('word') ||
    mimeType.includes('excel') ||
    mimeType.includes('spreadsheet') ||
    mimeType.includes('text')
  ) {
    return <FileText className={cn('w-4 h-4', className)} />
  }
  return <File className={cn('w-4 h-4', className)} />
}

// ---------------------------------------------------------------------------
// Format file size
// ---------------------------------------------------------------------------

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// ---------------------------------------------------------------------------
// Generate a simple unique ID
// ---------------------------------------------------------------------------

let _idCounter = 0
function generateId(): string {
  return `file-${Date.now()}-${++_idCounter}`
}

// ---------------------------------------------------------------------------
// FileRow — individual file in the list
// ---------------------------------------------------------------------------

interface FileRowProps {
  file: UploadedFile
  onRemove: (id: string) => void
  showPreview: boolean
  disabled: boolean
}

function FileRow({ file, onRemove, showPreview, disabled }: FileRowProps) {
  const isImage = file.type.startsWith('image/')
  const showThumb = showPreview && isImage && file.previewUrl

  return (
    <div
      className={cn(
        'flex items-center gap-3 px-3 py-2.5 rounded-lg border transition-colors',
        file.status === 'error'
          ? 'bg-red-50 border-red-200'
          : file.status === 'success'
          ? 'bg-green-50 border-green-200'
          : 'bg-white border-gray-200'
      )}
    >
      {/* Thumbnail or icon */}
      <div className="flex-shrink-0">
        {showThumb ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={file.previewUrl}
            alt={file.name}
            className="w-8 h-8 rounded object-cover border border-gray-200"
          />
        ) : (
          <div
            className={cn(
              'flex items-center justify-center w-8 h-8 rounded border',
              file.status === 'error'
                ? 'bg-red-50 border-red-200 text-red-500'
                : file.status === 'success'
                ? 'bg-green-50 border-green-200 text-green-500'
                : 'bg-gray-100 border-gray-200 text-gray-500'
            )}
          >
            <FileIcon mimeType={file.type} />
          </div>
        )}
      </div>

      {/* File info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p
            className={cn(
              'text-xs font-medium truncate',
              file.status === 'error' ? 'text-red-600' : 'text-gray-800'
            )}
            title={file.name}
          >
            {file.name}
          </p>
          <span className="text-[10px] text-gray-500 flex-shrink-0">
            {formatSize(file.size)}
          </span>
        </div>

        {/* Progress bar */}
        {file.status === 'uploading' && (
          <div className="mt-1 h-1 w-full bg-gray-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-green-500 rounded-full transition-all duration-300"
              style={{ width: `${file.progress}%` }}
            />
          </div>
        )}

        {/* Error message */}
        {file.status === 'error' && file.error && (
          <p className="mt-0.5 text-[10px] text-red-400 truncate">{file.error}</p>
        )}
      </div>

      {/* Status icon */}
      <div className="flex-shrink-0 flex items-center gap-1.5">
        {file.status === 'uploading' && (
          <Loader2 className="w-3.5 h-3.5 text-green-400 animate-spin" />
        )}
        {file.status === 'success' && (
          <CheckCircle2 className="w-3.5 h-3.5 text-green-400" />
        )}
        {file.status === 'error' && (
          <AlertCircle className="w-3.5 h-3.5 text-red-400" />
        )}

        {/* Remove button */}
        <button
          type="button"
          onClick={() => onRemove(file.id)}
          disabled={disabled || file.status === 'uploading'}
          className={cn(
            'flex items-center justify-center w-5 h-5 rounded',
            'text-gray-400 hover:text-gray-700 hover:bg-gray-100',
            'transition-colors duration-150',
            'disabled:pointer-events-none disabled:opacity-40',
            'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-slate-500'
          )}
          aria-label={`Remove ${file.name}`}
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// FileUploader
// ---------------------------------------------------------------------------

export default function FileUploader({
  accept,
  multiple = false,
  maxSize = 20 * 1024 * 1024, // 20 MB
  maxFiles = 10,
  files: externalFiles,
  onFilesAdded,
  onFileRemove,
  onUpload,
  onFileUpdate,
  disabled = false,
  dropLabel,
  dropSubLabel,
  autoUpload = false,
  className,
  compact = false,
  showPreviews = true,
}: FileUploaderProps) {
  const inputId = useId()
  const inputRef = useRef<HTMLInputElement>(null)

  // Internal files state (used when not controlled externally)
  const [internalFiles, setInternalFiles] = useState<UploadedFile[]>([])
  const [isDragOver, setIsDragOver] = useState(false)
  const [dragError, setDragError] = useState<string | null>(null)

  const files = externalFiles ?? internalFiles

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  function updateFile(fileId: string, update: Partial<UploadedFile>) {
    if (onFileUpdate) {
      onFileUpdate(fileId, update)
    } else {
      setInternalFiles((prev) =>
        prev.map((f) => (f.id === fileId ? { ...f, ...update } : f))
      )
    }
  }

  function addFiles(newFiles: UploadedFile[]) {
    if (onFilesAdded) {
      onFilesAdded(newFiles)
    } else {
      setInternalFiles((prev) => [...prev, ...newFiles])
    }
  }

  function removeFile(fileId: string) {
    if (onFileRemove) {
      onFileRemove(fileId)
    } else {
      setInternalFiles((prev) => prev.filter((f) => f.id !== fileId))
    }
  }

  // ---------------------------------------------------------------------------
  // Validate and process dropped / selected files
  // ---------------------------------------------------------------------------

  const processFiles = useCallback(
    async (rawFiles: FileList | File[]) => {
      setDragError(null)
      const fileArray = Array.from(rawFiles)

      // Cap at maxFiles
      const remaining = maxFiles - files.length
      if (remaining <= 0) {
        setDragError(`Maximum ${maxFiles} file${maxFiles !== 1 ? 's' : ''} allowed.`)
        return
      }
      const toProcess = fileArray.slice(0, remaining)

      if (fileArray.length > remaining) {
        setDragError(
          `Only ${remaining} file${remaining !== 1 ? 's' : ''} added (limit: ${maxFiles}).`
        )
      }

      // Parse accepted extensions / MIME types
      const acceptedTypes = accept
        ? accept
            .split(',')
            .map((s) => s.trim().toLowerCase())
            .filter(Boolean)
        : []

      const newUploadedFiles: UploadedFile[] = []

      for (const file of toProcess) {
        // Size check
        if (file.size > maxSize) {
          setDragError(
            `"${file.name}" exceeds the ${formatSize(maxSize)} size limit.`
          )
          continue
        }

        // Type check
        if (acceptedTypes.length > 0) {
          const mime = file.type.toLowerCase()
          const ext = ('.' + file.name.split('.').pop()).toLowerCase()
          const accepted = acceptedTypes.some((t) => {
            if (t.endsWith('/*')) {
              return mime.startsWith(t.slice(0, -2))
            }
            if (t.startsWith('.')) {
              return ext === t
            }
            return mime === t
          })
          if (!accepted) {
            setDragError(`"${file.name}" has an unsupported file type.`)
            continue
          }
        }

        // Build preview URL for images
        let previewUrl: string | undefined
        if (showPreviews && file.type.startsWith('image/')) {
          previewUrl = URL.createObjectURL(file)
        }

        newUploadedFiles.push({
          id: generateId(),
          file,
          name: file.name,
          size: file.size,
          type: file.type || 'application/octet-stream',
          status: 'idle',
          progress: 0,
          previewUrl,
        })
      }

      if (newUploadedFiles.length === 0) return

      addFiles(newUploadedFiles)

      if (autoUpload && onUpload) {
        for (const uf of newUploadedFiles) {
          updateFile(uf.id, { status: 'uploading', progress: 0 })
          try {
            await onUpload({ ...uf, status: 'uploading', progress: 0 })
            updateFile(uf.id, { status: 'success', progress: 100 })
          } catch (err: unknown) {
            updateFile(uf.id, {
              status: 'error',
              error:
                err instanceof Error
                  ? err.message
                  : 'Upload failed. Please try again.',
            })
          }
        }
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [files.length, maxFiles, maxSize, accept, autoUpload, onUpload, showPreviews]
  )

  // ---------------------------------------------------------------------------
  // Drag events
  // ---------------------------------------------------------------------------

  function handleDragEnter(e: React.DragEvent) {
    e.preventDefault()
    e.stopPropagation()
    if (!disabled) setIsDragOver(true)
  }

  function handleDragLeave(e: React.DragEvent) {
    e.preventDefault()
    e.stopPropagation()
    // Only clear drag over when leaving the root element
    if (e.currentTarget === e.target || !e.currentTarget.contains(e.relatedTarget as Node)) {
      setIsDragOver(false)
    }
  }

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault()
    e.stopPropagation()
    if (!disabled) {
      e.dataTransfer.dropEffect = 'copy'
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    e.stopPropagation()
    setIsDragOver(false)

    if (disabled) return

    const { files: droppedFiles } = e.dataTransfer
    if (droppedFiles.length > 0) {
      processFiles(droppedFiles)
    }
  }

  // ---------------------------------------------------------------------------
  // File input change
  // ---------------------------------------------------------------------------

  function handleInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const { files: selectedFiles } = e.target
    if (selectedFiles && selectedFiles.length > 0) {
      processFiles(selectedFiles)
    }
    // Reset the input so the same file can be re-selected
    e.target.value = ''
  }

  // ---------------------------------------------------------------------------
  // Click to browse
  // ---------------------------------------------------------------------------

  function handleZoneClick() {
    if (!disabled) {
      inputRef.current?.click()
    }
  }

  function handleZoneKeyDown(e: React.KeyboardEvent) {
    if (!disabled && (e.key === 'Enter' || e.key === ' ')) {
      e.preventDefault()
      inputRef.current?.click()
    }
  }

  // ---------------------------------------------------------------------------
  // Accepted file type display string
  // ---------------------------------------------------------------------------

  function acceptedTypesLabel(): string {
    if (!accept) return 'Any file type'
    return accept
      .split(',')
      .map((s) => s.trim())
      .join(', ')
  }

  const isAtLimit = files.length >= maxFiles
  const canAdd = !disabled && !isAtLimit

  const defaultDropLabel = compact
    ? 'Click or drag files here'
    : multiple
    ? 'Drop files here or click to browse'
    : 'Drop a file here or click to browse'

  const defaultDropSubLabel = compact
    ? `${acceptedTypesLabel()} · Max ${formatSize(maxSize)}`
    : [
        accept ? `Accepted: ${acceptedTypesLabel()}` : null,
        `Max size: ${formatSize(maxSize)}`,
        multiple && maxFiles < Infinity ? `Max files: ${maxFiles}` : null,
      ]
        .filter(Boolean)
        .join(' · ')

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className={cn('flex flex-col gap-3', className)}>
      {/* ------------------------------------------------------------------ */}
      {/* Hidden file input                                                     */}
      {/* ------------------------------------------------------------------ */}
      <input
        ref={inputRef}
        id={inputId}
        type="file"
        accept={accept}
        multiple={multiple}
        onChange={handleInputChange}
        disabled={disabled}
        className="sr-only"
        aria-hidden="true"
        tabIndex={-1}
      />

      {/* ------------------------------------------------------------------ */}
      {/* Dropzone                                                              */}
      {/* ------------------------------------------------------------------ */}
      {canAdd && (
        <div
          role="button"
          tabIndex={disabled ? -1 : 0}
          aria-label="File upload area. Press Enter or Space to browse files, or drag and drop."
          aria-disabled={disabled}
          onClick={handleZoneClick}
          onKeyDown={handleZoneKeyDown}
          onDragEnter={handleDragEnter}
          onDragLeave={handleDragLeave}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
          className={cn(
            'relative flex flex-col items-center justify-center text-center',
            'border-2 border-dashed rounded-xl cursor-pointer',
            'transition-all duration-200 select-none',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-green-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white',
            compact ? 'px-4 py-4 gap-1' : 'px-6 py-8 gap-3',
            isDragOver && !disabled
              ? 'border-brand-500 bg-brand-50 scale-[1.01]'
              : disabled
              ? 'border-gray-200 bg-gray-50 cursor-not-allowed opacity-60'
              : 'border-gray-300 bg-gray-50 hover:border-gray-400 hover:bg-gray-100'
          )}
        >
          {/* Upload icon */}
          <div
            className={cn(
              'flex items-center justify-center rounded-full transition-colors duration-200',
              compact ? 'w-8 h-8' : 'w-12 h-12',
              isDragOver
                ? 'bg-brand-50 text-brand-600'
                : 'bg-gray-100 text-gray-400'
            )}
          >
            {isDragOver ? (
              <FolderOpen className={cn(compact ? 'w-4 h-4' : 'w-6 h-6')} />
            ) : (
              <Upload className={cn(compact ? 'w-4 h-4' : 'w-6 h-6')} />
            )}
          </div>

          {/* Labels */}
          <div className={cn('flex flex-col gap-0.5', compact && 'gap-0')}>
            <p
              className={cn(
                'font-semibold',
                compact ? 'text-xs text-gray-500' : 'text-sm text-gray-800',
                isDragOver && 'text-brand-600'
              )}
            >
              {isDragOver
                ? 'Release to upload'
                : dropLabel ?? defaultDropLabel}
            </p>
            {!compact && (
              <p className="text-xs text-gray-500">
                {dropSubLabel ?? defaultDropSubLabel}
              </p>
            )}
            {compact && (
              <p className="text-[10px] text-gray-500">
                {dropSubLabel ?? defaultDropSubLabel}
              </p>
            )}
          </div>

          {/* Browse link hint */}
          {!compact && !isDragOver && (
            <p className="text-xs text-brand-600 font-medium flex items-center gap-1">
              <Paperclip className="w-3 h-3" />
              Browse files
            </p>
          )}

          {/* Drag overlay indicator */}
          {isDragOver && (
            <div className="absolute inset-0 rounded-xl border-2 border-green-500 bg-green-900/10 pointer-events-none" />
          )}
        </div>
      )}

      {/* At limit notice */}
      {isAtLimit && !disabled && (
        <p className="text-xs text-amber-400 text-center py-2 px-3 bg-amber-50 border border-amber-200 rounded-lg">
          Maximum {maxFiles} file{maxFiles !== 1 ? 's' : ''} reached. Remove a file to add more.
        </p>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* Drag / validation error                                               */}
      {/* ------------------------------------------------------------------ */}
      {dragError && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-red-950/40 border border-red-800/50 text-xs text-red-600">
          <AlertCircle className="w-3.5 h-3.5 flex-shrink-0 text-red-400" />
          <span>{dragError}</span>
          <button
            type="button"
            onClick={() => setDragError(null)}
            className="ml-auto text-red-500 hover:text-red-600 transition-colors"
            aria-label="Dismiss error"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* File list                                                             */}
      {/* ------------------------------------------------------------------ */}
      {files.length > 0 && (
        <div className="flex flex-col gap-1.5">
          {/* Header */}
          <div className="flex items-center justify-between px-1">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
              {files.length} file{files.length !== 1 ? 's' : ''} selected
            </p>
            {files.length > 1 && (
              <button
                type="button"
                onClick={() => {
                  if (externalFiles) {
                    // In controlled mode, remove all via callback
                    files.forEach((f) => onFileRemove?.(f.id))
                  } else {
                    setInternalFiles([])
                  }
                }}
                disabled={disabled || files.some((f) => f.status === 'uploading')}
                className="text-[11px] text-gray-400 hover:text-red-500 transition-colors disabled:pointer-events-none disabled:opacity-50"
              >
                Remove all
              </button>
            )}
          </div>

          {/* File rows */}
          <div className="flex flex-col gap-1">
            {files.map((file) => (
              <FileRow
                key={file.id}
                file={file}
                onRemove={removeFile}
                showPreview={showPreviews}
                disabled={disabled}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}


