'use client'

import { useState } from 'react'
import { FileDown, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface DownloadPdfButtonProps {
  label: string
  onDownload: () => Promise<Blob>
  filename?: string
  className?: string
}

function blobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export default function DownloadPdfButton({
  label,
  onDownload,
  filename = 'document.pdf',
  className,
}: DownloadPdfButtonProps) {
  const [isLoading, setIsLoading] = useState(false)

  async function handleClick() {
    if (isLoading) return
    setIsLoading(true)
    try {
      const blob = await onDownload()
      blobDownload(blob, filename)
      toast.success('PDF downloaded successfully')
    } catch {
      toast.error('Failed to download PDF')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Button
      variant="outline"
      size="sm"
      disabled={isLoading}
      onClick={handleClick}
      className={cn('gap-1.5', className)}
    >
      {isLoading ? (
        <Loader2 className="w-3.5 h-3.5 animate-spin" />
      ) : (
        <FileDown className="w-3.5 h-3.5" />
      )}
      {label}
    </Button>
  )
}
