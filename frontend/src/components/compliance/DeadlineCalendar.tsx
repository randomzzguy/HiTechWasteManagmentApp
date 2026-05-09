'use client'

import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, Clock, CheckCircle2, Shield } from 'lucide-react'
import { complianceApi } from '@/lib/api'
import { formatDate, cn } from '@/lib/utils'

interface DeadlineItem {
  batch_id: string
  sw_code: string
  waste_description: string
  quantity_kg: number
  storage_deadline?: string
  days_remaining?: number
  severity: string
  is_overdue: boolean
  client_id: string
}

export default function DeadlineCalendar() {
  const { data, isLoading } = useQuery({
    queryKey: ['compliance-deadlines'],
    queryFn: () => complianceApi.getDeadlines(),
    staleTime: 5 * 60_000,
    refetchInterval: 10 * 60_000,
  })

  const result = data as { items?: DeadlineItem[]; summary?: Record<string, number> } | null
  const items = result?.items ?? []
  const summary = result?.summary ?? {}

  const overdue = items.filter(i => i.is_overdue)
  const critical = items.filter(i => !i.is_overdue && (i.days_remaining ?? 99) <= 2)
  const warning = items.filter(i => !i.is_overdue && (i.days_remaining ?? 99) > 2 && (i.days_remaining ?? 99) <= 10)
  const info = items.filter(i => !i.is_overdue && (i.days_remaining ?? 99) > 10)

  const ItemRow = ({ item }: { item: DeadlineItem }) => (
    <div className={cn(
      'flex items-center justify-between p-3 rounded-lg border',
      item.is_overdue ? 'bg-red-900/20 border-red-800/40' :
      (item.days_remaining ?? 99) <= 2 ? 'bg-red-900/10 border-red-800/30' :
      (item.days_remaining ?? 99) <= 10 ? 'bg-amber-900/20 border-amber-800/40' :
      'bg-gray-100 border-gray-200'
    )}>
      <div className="flex items-center gap-2 min-w-0">
        {item.is_overdue || (item.days_remaining ?? 99) <= 2
          ? <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0" />
          : (item.days_remaining ?? 99) <= 10
          ? <Clock className="w-4 h-4 text-amber-400 flex-shrink-0" />
          : <Shield className="w-4 h-4 text-brand-400 flex-shrink-0" />
        }
        <div className="min-w-0">
          <p className="text-xs font-mono font-bold text-amber-400">{item.sw_code}</p>
          <p className="text-xs text-gray-500 truncate">{item.waste_description}</p>
        </div>
      </div>
      <div className="text-right flex-shrink-0 ml-3">
        {item.storage_deadline && (
          <p className="text-xs text-gray-700">{formatDate(item.storage_deadline)}</p>
        )}
        <p className={cn('text-xs font-semibold',
          item.is_overdue ? 'text-red-400' :
          (item.days_remaining ?? 99) <= 10 ? 'text-amber-400' : 'text-gray-500'
        )}>
          {item.is_overdue
            ? `${Math.abs(item.days_remaining ?? 0)}d overdue`
            : `${item.days_remaining}d left`
          }
        </p>
      </div>
    </div>
  )

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5">
      <div className="flex items-center gap-2 mb-4">
        <Shield className="w-4 h-4 text-amber-400" />
        <h3 className="text-sm font-semibold text-gray-900">90-Day Deadline Tracker</h3>
        {items.length > 0 && (
          <span className="ml-auto text-xs text-amber-400 font-semibold">{items.length} batches</span>
        )}
      </div>

      {/* Summary pills */}
      {items.length > 0 && (
        <div className="flex gap-2 mb-4 flex-wrap">
          {summary.overdue > 0 && (
            <span className="text-xs px-2 py-1 rounded-full bg-red-900/40 text-red-300 border border-red-800/40 font-semibold">
              {summary.overdue} overdue
            </span>
          )}
          {summary.critical > 0 && (
            <span className="text-xs px-2 py-1 rounded-full bg-red-900/20 text-red-400 border border-red-800/30 font-semibold">
              {summary.critical} critical
            </span>
          )}
          {summary.warning > 0 && (
            <span className="text-xs px-2 py-1 rounded-full bg-amber-900/30 text-amber-300 border border-amber-800/40 font-semibold">
              {summary.warning} warning
            </span>
          )}
        </div>
      )}

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-14 rounded-lg bg-gray-100 animate-pulse" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-8 text-gray-400 gap-2">
          <CheckCircle2 className="w-8 h-8 text-green-500/50" />
          <p className="text-sm">No upcoming deadlines in the next 30 days</p>
        </div>
      ) : (
        <div className="space-y-2 max-h-80 overflow-y-auto">
          {[...overdue, ...critical, ...warning, ...info].map(item => (
            <ItemRow key={item.batch_id} item={item} />
          ))}
        </div>
      )}
    </div>
  )
}

