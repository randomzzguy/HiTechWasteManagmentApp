'use client'

import { useQuery } from '@tanstack/react-query'
import { Wrench, AlertTriangle, CheckCircle2, Clock } from 'lucide-react'
import { fleetApi } from '@/lib/api'
import { formatDate, cn } from '@/lib/utils'

interface MaintenanceItem {
  id: string
  registration: string
  vehicle_type: string
  next_service_date?: string
  days_until_service?: number
  is_overdue: boolean
  severity: string
  flag_reason: string
}

export default function MaintenanceCalendar() {
  const { data, isLoading } = useQuery({
    queryKey: ['maintenance-due'],
    queryFn: () => fleetApi.getMaintenanceDue(),
    staleTime: 5 * 60_000,
    refetchInterval: 10 * 60_000,
  })

  const items = (data as { items?: MaintenanceItem[] } | null)?.items ?? []

  const overdue = items.filter(i => i.is_overdue)
  const critical = items.filter(i => !i.is_overdue && (i.days_until_service ?? 99) <= 7)
  const upcoming = items.filter(i => !i.is_overdue && (i.days_until_service ?? 99) > 7)

  const Section = ({ title, items: list, color }: { title: string; items: MaintenanceItem[]; color: string }) => {
    if (list.length === 0) return null
    return (
      <div>
        <p className={cn('text-xs font-semibold uppercase tracking-wider mb-2', color)}>{title} ({list.length})</p>
        <div className="space-y-2">
          {list.map(v => (
            <div key={v.id} className={cn(
              'flex items-center justify-between p-3 rounded-lg border',
              v.is_overdue ? 'bg-red-900/20 border-red-800/40' :
              (v.days_until_service ?? 99) <= 7 ? 'bg-amber-900/20 border-amber-800/40' :
              'bg-gray-100 border-gray-200'
            )}>
              <div className="flex items-center gap-2">
                {v.is_overdue
                  ? <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0" />
                  : (v.days_until_service ?? 99) <= 7
                  ? <Wrench className="w-4 h-4 text-amber-400 flex-shrink-0" />
                  : <Clock className="w-4 h-4 text-gray-500 flex-shrink-0" />
                }
                <div>
                  <p className="text-sm font-mono font-semibold text-gray-900">{v.registration}</p>
                  <p className="text-xs text-gray-500 capitalize">{v.vehicle_type.replace('_', ' ')}</p>
                </div>
              </div>
              <div className="text-right">
                {v.next_service_date && (
                  <p className="text-xs text-gray-700">{formatDate(v.next_service_date)}</p>
                )}
                <p className={cn('text-xs font-semibold',
                  v.is_overdue ? 'text-red-400' :
                  (v.days_until_service ?? 99) <= 7 ? 'text-amber-400' : 'text-gray-500'
                )}>
                  {v.is_overdue
                    ? `${Math.abs(v.days_until_service ?? 0)}d overdue`
                    : v.days_until_service != null
                    ? `${v.days_until_service}d`
                    : 'No date'
                  }
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5">
      <div className="flex items-center gap-2 mb-4">
        <Wrench className="w-4 h-4 text-amber-400" />
        <h3 className="text-sm font-semibold text-gray-900">Maintenance Schedule</h3>
        {items.length > 0 && (
          <span className="ml-auto text-xs text-amber-400 font-semibold">{items.length} vehicles</span>
        )}
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-14 rounded-lg bg-gray-100 animate-pulse" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-8 text-gray-400 gap-2">
          <CheckCircle2 className="w-8 h-8 text-green-500/50" />
          <p className="text-sm">All vehicles are up to date</p>
        </div>
      ) : (
        <div className="space-y-4">
          <Section title="Overdue" items={overdue} color="text-red-400" />
          <Section title="Due within 7 days" items={critical} color="text-amber-400" />
          <Section title="Upcoming (8–60 days)" items={upcoming} color="text-gray-500" />
        </div>
      )}
    </div>
  )
}

