'use client'

import { useEffect, useRef, useState } from 'react'
import { MapPin, Activity } from 'lucide-react'
import { useWebSocket } from '@/hooks/useWebSocket'

interface GpsPosition {
  vehicle_id: string
  lat: number
  lng: number
  speed_kmh?: number
  heading?: number
  timestamp?: string
}

interface FleetMapProps {
  height?: number
  selectedVehicleId?: string | null
}

export default function FleetMap({ height = 400, selectedVehicleId }: FleetMapProps) {
  const mapRef = useRef<HTMLDivElement>(null)
  const leafletMapRef = useRef<unknown>(null)
  const markersRef = useRef<Record<string, unknown>>({})
  const [positions, setPositions] = useState<Record<string, GpsPosition>>({})
  const [mapReady, setMapReady] = useState(false)

  const wsUrl = typeof window !== 'undefined'
    ? `${process.env.NEXT_PUBLIC_WS_URL ?? 'ws://localhost:8000'}/ws/fleet`
    : null

  const { lastMessage, connectionStatus } = useWebSocket(wsUrl, { enabled: true })

  // Process GPS messages
  useEffect(() => {
    if (!lastMessage) return
    const msg = lastMessage as unknown as Record<string, unknown>
    if ((msg.event === 'gps_broadcast' || msg.type === 'gps_update') && msg.vehicle_id) {
      setPositions(prev => ({
        ...prev,
        [msg.vehicle_id as string]: {
          vehicle_id: msg.vehicle_id as string,
          lat: (msg.lat as number) ?? 3.1390,
          lng: (msg.lng as number) ?? 101.6869,
          speed_kmh: msg.speed_kmh as number | undefined,
          timestamp: new Date().toISOString(),
        }
      }))
    }
  }, [lastMessage])

  // Init Leaflet
  useEffect(() => {
    if (!mapRef.current || leafletMapRef.current || typeof window === 'undefined') return

    import('leaflet').then(L => {
      delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
        iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
        shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
      })

      const map = L.map(mapRef.current!, { center: [3.1390, 101.6869], zoom: 11, zoomControl: true })
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 19,
      }).addTo(map)

      leafletMapRef.current = map
      setMapReady(true)
    }).catch(() => {})

    return () => {
      if (leafletMapRef.current) {
        (leafletMapRef.current as { remove: () => void }).remove()
        leafletMapRef.current = null
        markersRef.current = {}
      }
    }
  }, [])

  // Update markers
  useEffect(() => {
    if (!mapReady || !leafletMapRef.current) return

    import('leaflet').then(L => {
      const map = leafletMapRef.current as {
        addLayer: (l: unknown) => void
        removeLayer: (l: unknown) => void
        setView: (ll: [number, number], z: number) => void
      }

      Object.entries(positions).forEach(([vid, pos]) => {
        const isSelected = vid === selectedVehicleId
        const color = isSelected ? '#22c55e' : '#3b82f6'
        const size = isSelected ? 16 : 12

        const icon = L.divIcon({
          html: `<div style="background:${color};width:${size}px;height:${size}px;border-radius:50%;border:2px solid white;box-shadow:0 0 8px ${color}80;transition:all 0.3s"></div>`,
          iconSize: [size, size],
          iconAnchor: [size / 2, size / 2],
          className: '',
        })

        const existing = markersRef.current[vid] as {
          setLatLng: (ll: [number, number]) => void
          setIcon: (i: unknown) => void
          getPopup: () => { setContent: (s: string) => void } | null
        } | undefined

        if (existing) {
          existing.setLatLng([pos.lat, pos.lng])
          existing.setIcon(icon)
        } else {
          const marker = L.marker([pos.lat, pos.lng], { icon })
          marker.bindPopup(`<b>${vid}</b><br>Speed: ${pos.speed_kmh ?? 0} km/h`)
          ;(map as unknown as { addLayer: (l: unknown) => void }).addLayer(marker)
          markersRef.current[vid] = marker
        }
      })

      // Pan to selected vehicle
      if (selectedVehicleId && positions[selectedVehicleId]) {
        const pos = positions[selectedVehicleId]
        map.setView([pos.lat, pos.lng], 14)
      }
    }).catch(() => {})
  }, [positions, mapReady, selectedVehicleId])

  const trackedCount = Object.keys(positions).length

  return (
    <div className="relative rounded-xl overflow-hidden border border-gray-200" style={{ height }}>
      <div ref={mapRef} style={{ height: '100%', background: '#ffffff' }} />

      {/* Status overlay */}
      <div className="absolute top-3 right-3 flex items-center gap-1.5 bg-gray-50 backdrop-blur-sm px-2.5 py-1.5 rounded-lg border border-gray-200 text-xs">
        <span className={`w-2 h-2 rounded-full ${connectionStatus === 'connected' ? 'bg-green-400 animate-pulse' : 'bg-slate-500'}`} />
        <span className="text-gray-700">
          {connectionStatus === 'connected' ? `${trackedCount} tracked` : 'Connecting…'}
        </span>
      </div>

      {/* Empty state */}
      {trackedCount === 0 && (
        <div className="absolute inset-0 flex flex-col items-center justify-center text-gray-400 pointer-events-none">
          <MapPin className="w-8 h-8 opacity-30 mb-2" />
          <p className="text-sm">Waiting for GPS data</p>
          <p className="text-xs opacity-60">Vehicles will appear when they connect</p>
        </div>
      )}
    </div>
  )
}

