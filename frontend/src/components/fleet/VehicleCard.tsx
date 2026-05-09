'use client'

import { Truck, Wrench, MapPin, AlertTriangle, Activity } from 'lucide-react'
import { formatDate, cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'

interface VehicleCardProps {
  vehicle: {
    id: string
    registration: string
    vehicle_type: string
    make?: string
    model?: string
    status: string
    odometer_km?: number
    next_service_date?: string
    gps_device_id?: string
    capacity_kg?: number
  }
  isSelected?: boolean
  liveSpeed?: number
  onClick?: () => void
}

const STATUS_VARIANT: Record<string, 'success' | 'info' | 'warning' | 'secondary'> = {
  available:   'success',
  on_trip:     'info',
  maintenance: 'warning',
  retired:     'secondary',
}

const TYPE_ICONS: Record<string, string> = {
  compactor:   '🚛',
  hook_loader: '🏗️',
  open_lorry:  '🚚',
  skip_truck:  '🚜',
  van:         '🚐',
}

export default function VehicleCard({ vehicle: v, isSelected, liveSpeed, onClick }: VehicleCardProps) {
  const isServiceDue = v.next_service_date &&
    new Date(v.next_service_date) <= new Date(Date.now() + 14 * 86400000)

  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full text-left p-4 rounded-xl border transition-all duration-150',
        isSelected
          ? 'bg-gray-100 border-green-600 shadow-md shadow-green-900/20'
          : 'bg-white border-gray-200 hover:border-gray-300 hover:bg-gray-50'
      )}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="flex items-center gap-2">
          <span className="text-lg">{TYPE_ICONS[v.vehicle_type] ?? '🚛'}</span>
          <div>
            <p className="font-mono text-sm font-bold text-gray-900">{v.registration}</p>
            <p className="text-xs text-gray-500 capitalize">{v.vehicle_type.replace('_', ' ')}</p>
          </div>
        </div>
        <Badge variant={STATUS_VARIANT[v.status] ?? 'secondary'}>
          {v.status.replace('_', ' ')}
        </Badge>
      </div>

      {/* Make/model */}
      {(v.make || v.model) && (
        <p className="text-xs text-gray-400 mb-2">{[v.make, v.model].filter(Boolean).join(' ')}</p>
      )}

      {/* Stats row */}
      <div className="flex items-center gap-3 flex-wrap">
        {v.odometer_km != null && (
          <span className="flex items-center gap-1 text-xs text-gray-500">
            <Activity className="w-3 h-3" />
            {Number(v.odometer_km).toLocaleString()} km
          </span>
        )}
        {v.capacity_kg != null && (
          <span className="flex items-center gap-1 text-xs text-gray-500">
            <Truck className="w-3 h-3" />
            {Number(v.capacity_kg).toLocaleString()} kg
          </span>
        )}
        {v.gps_device_id && (
          <span className="flex items-center gap-1 text-xs text-green-500">
            <MapPin className="w-3 h-3" />
            GPS
          </span>
        )}
        {liveSpeed !== undefined && (
          <span className="flex items-center gap-1 text-xs text-brand-400 font-semibold">
            <Activity className="w-3 h-3 animate-pulse" />
            {liveSpeed} km/h
          </span>
        )}
      </div>

      {/* Service warning */}
      {isServiceDue && (
        <div className="flex items-center gap-1.5 mt-2 text-xs text-amber-400">
          <AlertTriangle className="w-3 h-3" />
          Service due {formatDate(v.next_service_date!)}
        </div>
      )}
    </button>
  )
}


