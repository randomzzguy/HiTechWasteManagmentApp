"use client"

import { useState, useEffect, useRef } from "react"
import { useQuery } from "@tanstack/react-query"
import { Truck, MapPin, Wrench, RefreshCw, AlertTriangle, CheckCircle2, Activity } from "lucide-react"
import { fleetApi } from "@/lib/api"
import { formatDate, cn } from "@/lib/utils"
import { useWebSocket } from "@/hooks/useWebSocket"

interface Vehicle {
  id: string
  registration: string
  vehicle_type: string
  make?: string
  model?: string
  status: string
  assigned_driver_id?: string
  next_service_date?: string
  odometer_km?: number
  gps_device_id?: string
  capacity_kg?: number
}

interface GpsPosition {
  vehicle_id: string
  lat: number
  lng: number
  speed_kmh?: number
  heading?: number
  timestamp?: string
}

const STATUS_STYLES: Record<string, string> = {
  available:   "bg-green-50 text-green-600 border-green-200",
  on_trip:     "bg-brand-50 text-brand-600 border-brand-200",
  maintenance: "bg-amber-50 text-amber-600 border-amber-200",
  retired:     "bg-gray-100 text-gray-600 border-gray-300",
}

const STATUS_DOT: Record<string, string> = {
  available:   "bg-green-400",
  on_trip:     "bg-brand-400 animate-pulse",
  maintenance: "bg-amber-400",
  retired:     "bg-slate-500",
}

export default function FleetPage() {
  const [selectedVehicle, setSelectedVehicle] = useState<string | null>(null)
  const [gpsPositions, setGpsPositions] = useState<Record<string, GpsPosition>>({})
  const mapRef = useRef<HTMLDivElement>(null)
  const leafletMapRef = useRef<unknown>(null)
  const markersRef = useRef<Record<string, unknown>>({})

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["fleet-vehicles"],
    queryFn: () => fleetApi.listVehicles({ limit: 100 } as Parameters<typeof fleetApi.listVehicles>[0]),
    staleTime: 30_000,
    refetchInterval: 60_000,
  })

  const { data: statsData } = useQuery({
    queryKey: ["fleet-stats"],
    queryFn: () => fleetApi.getFleetStats(),
    staleTime: 30_000,
  })

  const { data: maintenanceDue } = useQuery({
    queryKey: ["fleet-maintenance-due"],
    queryFn: () => fleetApi.getMaintenanceDue(),
    staleTime: 5 * 60_000,
  })

  // WebSocket for live GPS
  const wsUrl = typeof window !== "undefined"
    ? `${process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000"}/ws/fleet`
    : null

  const { lastMessage } = useWebSocket(wsUrl, { enabled: true })

  useEffect(() => {
    if (!lastMessage) return
    const msg = lastMessage as { type?: string; event?: string; vehicle_id?: string; lat?: number; lng?: number; speed_kmh?: number }
    if ((msg.type === "gps_broadcast" || msg.event === "gps_update") && msg.vehicle_id) {
      setGpsPositions(prev => ({
        ...prev,
        [msg.vehicle_id!]: {
          vehicle_id: msg.vehicle_id!,
          lat: msg.lat ?? 3.1390,
          lng: msg.lng ?? 101.6869,
          speed_kmh: msg.speed_kmh,
          timestamp: new Date().toISOString(),
        }
      }))
    }
  }, [lastMessage])

  // Initialize Leaflet map
  useEffect(() => {
    if (!mapRef.current || leafletMapRef.current) return
    if (typeof window === "undefined") return

    import("leaflet").then((L) => {
      // Fix default icon paths
      delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
        iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
        shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
      })

      const map = L.map(mapRef.current!, { center: [3.1390, 101.6869], zoom: 11 })
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "© OpenStreetMap contributors",
      }).addTo(map)
      leafletMapRef.current = map
    }).catch(() => {})

    return () => {
      if (leafletMapRef.current) {
        (leafletMapRef.current as { remove: () => void }).remove()
        leafletMapRef.current = null
      }
    }
  }, [])

  // Update markers when GPS positions change
  useEffect(() => {
    if (!leafletMapRef.current) return
    import("leaflet").then((L) => {
      const map = leafletMapRef.current as { addLayer: (l: unknown) => void; removeLayer: (l: unknown) => void }
      Object.entries(gpsPositions).forEach(([vid, pos]) => {
        const existing = markersRef.current[vid] as { setLatLng: (ll: unknown) => void } | undefined
        if (existing) {
          existing.setLatLng([pos.lat, pos.lng])
        } else {
          const icon = L.divIcon({
            html: `<div style="background:#3b82f6;width:12px;height:12px;border-radius:50%;border:2px solid white;box-shadow:0 0 6px rgba(59,130,246,0.8)"></div>`,
            iconSize: [12, 12], iconAnchor: [6, 6],
          })
          const marker = L.marker([pos.lat, pos.lng], { icon })
          marker.bindPopup(`Vehicle: ${vid}<br>Speed: ${pos.speed_kmh ?? 0} km/h`)
          ;(map as unknown as { addLayer: (l: unknown) => void }).addLayer(marker)
          markersRef.current[vid] = marker
        }
      })
    }).catch(() => {})
  }, [gpsPositions])

  const vehicles = (data as { items?: Vehicle[] } | null)?.items ?? []
  const stats = statsData as unknown as Record<string, number> | null
  const maintenanceList = Array.isArray(maintenanceDue) ? maintenanceDue as Record<string, unknown>[] : []

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Fleet Operations</h1>
          <p className="text-sm text-gray-500 mt-0.5">Live GPS tracking, vehicle registry, and maintenance</p>
        </div>
        <button onClick={() => refetch()} className="flex items-center gap-1.5 px-3 py-2 text-xs text-gray-500 hover:text-gray-900 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: "Total Vehicles", value: stats.total_vehicles ?? vehicles.length, color: "text-gray-900" },
            { label: "Available", value: stats.available ?? vehicles.filter(v => v.status === "available").length, color: "text-green-400" },
            { label: "On Trip", value: stats.on_trip ?? vehicles.filter(v => v.status === "on_trip").length, color: "text-brand-400" },
            { label: "Maintenance Due", value: maintenanceList.length, color: "text-amber-400" },
          ].map(s => (
            <div key={s.label} className="bg-white border border-gray-200 rounded-xl p-4">
              <p className="text-xs text-gray-400 font-semibold uppercase tracking-wider">{s.label}</p>
              <p className={cn("text-2xl font-bold mt-1", s.color)}>{s.value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Map + vehicle list */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        {/* Live map */}
        <div className="xl:col-span-2 bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
            <div className="flex items-center gap-2">
              <MapPin className="w-4 h-4 text-green-400" />
              <span className="text-sm font-semibold text-gray-900">Live Fleet Map</span>
            </div>
            <div className="flex items-center gap-1.5 text-xs text-gray-500">
              <span className="w-2 h-2 rounded-full bg-brand-400 animate-pulse inline-block" />
              {Object.keys(gpsPositions).length} vehicles tracked
            </div>
          </div>
          <div ref={mapRef} style={{ height: "400px", background: "#f9fafb" }}>
            {Object.keys(gpsPositions).length === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-gray-400 gap-2">
                <MapPin className="w-8 h-8 opacity-30" />
                <p className="text-sm">Waiting for GPS data via MQTT...</p>
                <p className="text-xs">Map will populate when vehicles connect</p>
              </div>
            )}
          </div>
        </div>

        {/* Vehicle list */}
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-200">
            <span className="text-sm font-semibold text-gray-900">Vehicles ({vehicles.length})</span>
          </div>
          <div className="overflow-y-auto" style={{ maxHeight: "440px" }}>
            {isLoading ? (
              Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="p-3 border-b border-gray-100 animate-pulse">
                  <div className="h-4 bg-gray-200 rounded w-24 mb-2" />
                  <div className="h-3 bg-gray-200 rounded w-16" />
                </div>
              ))
            ) : vehicles.map(v => (
              <button key={v.id} onClick={() => setSelectedVehicle(v.id === selectedVehicle ? null : v.id)}
                className={cn("w-full text-left p-3 border-b border-gray-100 hover:bg-gray-50 transition-colors",
                  selectedVehicle === v.id && "bg-brand-50")}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className={cn("w-2 h-2 rounded-full flex-shrink-0", STATUS_DOT[v.status] ?? "bg-slate-500")} />
                    <span className="text-sm font-mono font-semibold text-gray-900">{v.registration}</span>
                  </div>
                  <span className={cn("text-[10px] px-1.5 py-0.5 rounded-full border", STATUS_STYLES[v.status] ?? "bg-gray-100 text-gray-600 border-gray-300")}>
                    {v.status.replace("_", " ")}
                  </span>
                </div>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-xs text-gray-400">{v.vehicle_type.replace("_", " ")}</span>
                  {v.make && <span className="text-xs text-gray-400">· {v.make} {v.model}</span>}
                </div>
                {gpsPositions[v.id] && (
                  <div className="flex items-center gap-1 mt-1">
                    <Activity className="w-3 h-3 text-brand-400" />
                    <span className="text-xs text-brand-400">{gpsPositions[v.id].speed_kmh ?? 0} km/h</span>
                  </div>
                )}
                {v.next_service_date && new Date(v.next_service_date) <= new Date(Date.now() + 14 * 86400000) && (
                  <div className="flex items-center gap-1 mt-1">
                    <AlertTriangle className="w-3 h-3 text-amber-400" />
                    <span className="text-xs text-amber-400">Service: {formatDate(v.next_service_date)}</span>
                  </div>
                )}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Maintenance due */}
      {maintenanceList.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-amber-400 flex items-center gap-2 mb-3">
            <Wrench className="w-4 h-4" /> Maintenance Due ({maintenanceList.length})
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {maintenanceList.slice(0, 6).map((v, i) => (
              <div key={i} className={cn("p-3 rounded-lg border", v.is_overdue ? "bg-red-50 border-red-200" : "bg-amber-50 border-amber-200")}>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-mono font-semibold text-gray-900">{v.registration as string}</span>
                  <span className={cn("text-xs font-semibold", v.is_overdue ? "text-red-400" : "text-amber-400")}>
                    {v.is_overdue ? `${Math.abs(v.days_until_service as number)}d overdue` : `${v.days_until_service}d`}
                  </span>
                </div>
                <p className="text-xs text-gray-500 mt-0.5">{v.vehicle_type as string} · {v.next_service_date ? formatDate(v.next_service_date as string) : "No date set"}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
