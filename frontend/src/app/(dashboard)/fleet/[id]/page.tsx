'use client'

import { useParams, useRouter } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Truck, Wrench, Activity, AlertCircle, MapPin, Gauge } from 'lucide-react'
import { fleetApi } from '@/lib/api'
import { formatDate, formatDateTime, cn } from '@/lib/utils'

const STATUS_STYLES: Record<string, string> = {
  available:   'bg-green-50 text-green-600 border-green-200',
  on_trip:     'bg-blue-50 text-blue-600 border-blue-200',
  maintenance: 'bg-amber-50 text-amber-600 border-amber-200',
  retired:     'bg-gray-100 text-gray-500 border-gray-300',
}

export default function VehicleDetailPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()

  const { data: vehicle, isLoading, isError } = useQuery({
    queryKey: ['vehicle', id],
    queryFn: () => fleetApi.getVehicle(id),
    staleTime: 30_000,
  })

  const { data: tripsData } = useQuery({
    queryKey: ['vehicle-trips', id],
    queryFn: () => fleetApi.listTrips({ vehicle_id: id, limit: 10 } as Parameters<typeof fleetApi.listTrips>[0]),
    staleTime: 60_000,
  })

  const { data: maintenanceLogs } = useQuery({
    queryKey: ['vehicle-maintenance', id],
    queryFn: () => fleetApi.listMaintenanceLogs(id),
    staleTime: 60_000,
  })

  const v = vehicle as Record<string, unknown> | null
  const trips = (tripsData as { items?: Record<string, unknown>[] } | null)?.items ?? []
  const logs = (maintenanceLogs as { items?: Record<string, unknown>[] } | null)?.items ?? []

  if (isLoading) return (
    <div className="flex items-center justify-center h-64">
      <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
    </div>
  )

  if (isError || !v) return (
    <div className="flex flex-col items-center justify-center h-64 gap-3 text-gray-400">
      <AlertCircle className="w-10 h-10" />
      <p>Vehicle not found.</p>
      <button onClick={() => router.back()} className="text-blue-600 hover:underline text-sm">Go back</button>
    </div>
  )

  const isServiceDue = v.next_service_date &&
    new Date(v.next_service_date as string) <= new Date(Date.now() + 14 * 86400000)
  const isServiceOverdue = v.next_service_date &&
    new Date(v.next_service_date as string) < new Date()

  return (
    <div className="flex flex-col gap-6 max-w-4xl">
      {/* Header */}
      <div className="flex items-start gap-4 flex-wrap">
        <button
          onClick={() => router.back()}
          className="mt-1 p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-700 transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <div className="w-10 h-10 rounded-xl bg-blue-50 border border-blue-200 flex items-center justify-center flex-shrink-0">
              <Truck className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900 font-mono">{v.registration as string}</h1>
              <p className="text-sm text-gray-500">
                {(v.vehicle_type as string).replace(/_/g, ' ')} · {v.make as string} {v.model as string} {String(v.year ?? '')}
              </p>
            </div>
            <span className={cn(
              'px-2.5 py-1 rounded-full text-xs font-semibold border',
              STATUS_STYLES[v.status as string] ?? 'bg-gray-100 text-gray-600 border-gray-300'
            )}>
              {(v.status as string).replace(/_/g, ' ')}
            </span>
          </div>
        </div>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-white border border-gray-200 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <Gauge className="w-3.5 h-3.5 text-gray-400" />
            <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider">Odometer</p>
          </div>
          <p className="text-sm font-bold text-gray-900">
            {v.odometer_km ? `${Number(v.odometer_km).toLocaleString()} km` : 'N/A'}
          </p>
        </div>
        <div className="bg-white border border-gray-200 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <Truck className="w-3.5 h-3.5 text-gray-400" />
            <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider">Capacity</p>
          </div>
          <p className="text-sm font-bold text-blue-600">
            {v.capacity_kg ? `${Number(v.capacity_kg).toLocaleString()} kg` : 'N/A'}
          </p>
        </div>
        <div className={cn('bg-white border rounded-xl p-4', isServiceOverdue ? 'border-red-200 bg-red-50' : isServiceDue ? 'border-amber-200 bg-amber-50' : 'border-gray-200')}>
          <div className="flex items-center gap-2 mb-1">
            <Wrench className="w-3.5 h-3.5 text-gray-400" />
            <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider">Next Service</p>
          </div>
          <p className={cn('text-sm font-bold', isServiceOverdue ? 'text-red-600' : isServiceDue ? 'text-amber-600' : 'text-gray-900')}>
            {v.next_service_date ? formatDate(v.next_service_date as string) : 'Not set'}
          </p>
        </div>
        <div className="bg-white border border-gray-200 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <MapPin className="w-3.5 h-3.5 text-gray-400" />
            <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider">GPS Device</p>
          </div>
          <p className={cn('text-sm font-bold', v.gps_device_id ? 'text-green-600' : 'text-gray-400')}>
            {(v.gps_device_id as string) || 'Not fitted'}
          </p>
        </div>
      </div>

      {/* Recent Trips */}
      <div className="bg-white border border-gray-200 rounded-xl p-5">
        <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2 mb-4">
          <Activity className="w-4 h-4 text-blue-500" /> Recent Trips
        </h3>
        {trips.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50">
                  {['Departure', 'Arrival', 'Distance', 'Fuel', 'Notes'].map(h => (
                    <th key={h} className="pb-2 px-3 py-2 text-[11px] font-semibold text-gray-500 uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {trips.map((t, i) => (
                  <tr key={i} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="px-3 py-2.5 text-xs text-gray-700">{t.departure_time ? formatDateTime(t.departure_time as string) : '—'}</td>
                    <td className="px-3 py-2.5 text-xs text-gray-700">{t.arrival_time ? formatDateTime(t.arrival_time as string) : '—'}</td>
                    <td className="px-3 py-2.5 text-xs text-gray-700">{t.distance_km ? `${Number(t.distance_km).toFixed(1)} km` : '—'}</td>
                    <td className="px-3 py-2.5 text-xs text-gray-700">{t.fuel_litres ? `${Number(t.fuel_litres).toFixed(1)} L` : '—'}</td>
                    <td className="px-3 py-2.5 text-xs text-gray-500 truncate max-w-[200px]">{(t.notes as string) || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-gray-400 text-center py-6">No trip records found</p>
        )}
      </div>

      {/* Maintenance History */}
      <div className="bg-white border border-gray-200 rounded-xl p-5">
        <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2 mb-4">
          <Wrench className="w-4 h-4 text-amber-500" /> Maintenance History
        </h3>
        {logs.length > 0 ? (
          <div className="space-y-2">
            {logs.map((log, i) => (
              <div key={i} className="flex items-center justify-between p-3 bg-gray-50 border border-gray-200 rounded-lg">
                <div>
                  <p className="text-sm font-semibold text-gray-900">{log.service_type as string}</p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {(log.workshop as string) || 'Workshop N/A'} · {log.service_date ? formatDate(log.service_date as string) : 'N/A'}
                  </p>
                </div>
                <div className="text-right">
                  {!!log.cost_myr && (
                    <p className="text-xs font-semibold text-green-600">RM {Number(log.cost_myr).toFixed(2)}</p>
                  )}
                  {!!log.odometer_at_service_km && (
                    <p className="text-xs text-gray-400">{Number(log.odometer_at_service_km).toLocaleString()} km</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-400 text-center py-6">No maintenance records found</p>
        )}
      </div>
    </div>
  )
}
