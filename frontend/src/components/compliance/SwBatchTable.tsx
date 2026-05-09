'use client'

import { AlertTriangle, Clock, CheckCircle2, FileText, ChevronRight } from 'lucide-react'
import { formatDate, cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'

interface SwBatch {
  id: string
  sw_code: string
  waste_description: string
  quantity_kg: number
  physical_state: string
  storage_start_date: string
  storage_deadline?: string
  days_remaining?: number
  status: string
  client_id: string
  consignment_note_id?: string
}

interface SwBatchTableProps {
  batches: SwBatch[]
  isLoading?: boolean
  onSelect?: (batch: SwBatch) => void
}

const STATUS_VARIANT: Record<string, 'info' | 'warning' | 'success'> = {
  in_storage:  'info',
  dispatched:  'warning',
  processed:   'success',
}

function DaysIndicator({ days }: { days?: number }) {
  if (days === undefined || days === null) return <span className="text-gray-400 text-xs">—</span>

  if (days < 0) return (
    <span className="flex items-center gap-1 text-xs font-bold text-red-400">
      <AlertTriangle className="w-3 h-3" />{Math.abs(days)}d overdue
    </span>
  )
  if (days <= 2) return (
    <span className="flex items-center gap-1 text-xs font-semibold text-red-400">
      <AlertTriangle className="w-3 h-3" />{days}d left
    </span>
  )
  if (days <= 10) return (
    <span className="flex items-center gap-1 text-xs font-semibold text-amber-400">
      <Clock className="w-3 h-3" />{days}d left
    </span>
  )
  return <span className="text-xs text-gray-500">{days}d left</span>
}

export default function SwBatchTable({ batches, isLoading, onSelect }: SwBatchTableProps) {
  if (isLoading) return (
    <div className="space-y-2">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="h-14 rounded-lg bg-gray-100 animate-pulse" />
      ))}
    </div>
  )

  if (batches.length === 0) return (
    <div className="flex flex-col items-center justify-center py-10 text-gray-400 gap-2">
      <CheckCircle2 className="w-8 h-8 opacity-30" />
      <p className="text-sm">No scheduled waste batches</p>
    </div>
  )

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left">
        <thead>
          <tr className="border-b border-gray-200 bg-gray-50">
            {['SW Code', 'Description', 'Qty (kg)', 'State', 'Storage Start', 'Deadline', 'Days Left', 'Status', 'CN', ''].map(h => (
              <th key={h} className="px-3 py-2.5 text-[11px] font-semibold text-gray-400 uppercase tracking-wider whitespace-nowrap">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {batches.map(b => (
            <tr
              key={b.id}
              onClick={() => onSelect?.(b)}
              className={cn(
                'border-b border-gray-100 transition-colors group',
                onSelect && 'cursor-pointer hover:bg-gray-50'
              )}
            >
              <td className="px-3 py-2.5">
                <span className="font-mono text-xs font-bold text-amber-400">{b.sw_code}</span>
              </td>
              <td className="px-3 py-2.5 max-w-[160px]">
                <span className="text-xs text-gray-700 truncate block">{b.waste_description}</span>
              </td>
              <td className="px-3 py-2.5">
                <span className="text-xs text-gray-700">{Number(b.quantity_kg).toLocaleString()}</span>
              </td>
              <td className="px-3 py-2.5">
                <span className="text-xs text-gray-500 capitalize">{b.physical_state}</span>
              </td>
              <td className="px-3 py-2.5">
                <span className="text-xs text-gray-500">{formatDate(b.storage_start_date)}</span>
              </td>
              <td className="px-3 py-2.5">
                <span className={cn('text-xs', b.days_remaining !== undefined && b.days_remaining < 0 ? 'text-red-400' : 'text-gray-500')}>
                  {b.storage_deadline ? formatDate(b.storage_deadline) : '—'}
                </span>
              </td>
              <td className="px-3 py-2.5">
                <DaysIndicator days={b.days_remaining} />
              </td>
              <td className="px-3 py-2.5">
                <Badge variant={STATUS_VARIANT[b.status] ?? 'secondary'}>
                  {b.status.replace('_', ' ')}
                </Badge>
              </td>
              <td className="px-3 py-2.5">
                {b.consignment_note_id
                  ? <CheckCircle2 className="w-4 h-4 text-green-400" />
                  : <span className="text-xs text-gray-400">—</span>
                }
              </td>
              <td className="px-3 py-2.5 text-right">
                {onSelect && <ChevronRight className="w-4 h-4 text-gray-400 group-hover:text-gray-700 transition-colors" />}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

