import {
  useQuery,
  useMutation,
  useQueryClient,
  UseQueryOptions,
} from '@tanstack/react-query'
import { fleetApi, VehicleListParams } from '@/lib/api'
import type {
  Vehicle,
  VehicleListResponse,
  MaintenanceDueItem,
  MaintenanceLog,
  Driver,
  FleetStats,
  Trip,
} from '@/types/vehicle'

// ---------------------------------------------------------------------------
// Query Keys
// ---------------------------------------------------------------------------

export const fleetKeys = {
  all: ['fleet'] as const,

  vehicles: () => [...fleetKeys.all, 'vehicles'] as const,
  vehicleList: (params?: VehicleListParams) =>
    [...fleetKeys.vehicles(), 'list', params] as const,
  vehicleDetail: (id: string) =>
    [...fleetKeys.vehicles(), 'detail', id] as const,

  maintenance: () => [...fleetKeys.all, 'maintenance'] as const,
  maintenanceDue: () => [...fleetKeys.maintenance(), 'due'] as const,
  maintenanceLogs: (vehicleId?: string) =>
    [...fleetKeys.maintenance(), 'logs', vehicleId] as const,

  drivers: () => [...fleetKeys.all, 'drivers'] as const,
  driverList: (params?: Record<string, unknown>) =>
    [...fleetKeys.drivers(), 'list', params] as const,

  stats: () => [...fleetKeys.all, 'stats'] as const,

  trips: (params?: Record<string, unknown>) =>
    [...fleetKeys.all, 'trips', params] as const,
}

// ---------------------------------------------------------------------------
// useVehicles — paginated list with optional filtering
// ---------------------------------------------------------------------------

export function useVehicles(
  params?: VehicleListParams,
  options?: Omit<UseQueryOptions<VehicleListResponse>, 'queryKey' | 'queryFn'>
) {
  return useQuery<VehicleListResponse>({
    queryKey: fleetKeys.vehicleList(params),
    queryFn: () => fleetApi.listVehicles(params) as unknown as Promise<VehicleListResponse>,
    staleTime: 30_000,
    refetchInterval: 60_000, // fleet status changes frequently
    ...options,
  })
}

// ---------------------------------------------------------------------------
// useVehicle — single vehicle by ID
// ---------------------------------------------------------------------------

export function useVehicle(
  id: string | null | undefined,
  options?: Omit<UseQueryOptions<Vehicle>, 'queryKey' | 'queryFn'>
) {
  return useQuery<Vehicle>({
    queryKey: fleetKeys.vehicleDetail(id ?? ''),
    queryFn: () => fleetApi.getVehicle(id!) as unknown as Promise<Vehicle>,
    enabled: !!id,
    staleTime: 30_000,
    ...options,
  })
}

// ---------------------------------------------------------------------------
// useMaintenanceDue — vehicles with upcoming / overdue maintenance
// ---------------------------------------------------------------------------

export function useMaintenanceDue(
  options?: Omit<UseQueryOptions<MaintenanceDueItem[]>, 'queryKey' | 'queryFn'>
) {
  return useQuery<MaintenanceDueItem[]>({
    queryKey: fleetKeys.maintenanceDue(),
    queryFn: () =>
      fleetApi.getMaintenanceDue() as unknown as Promise<MaintenanceDueItem[]>,
    staleTime: 5 * 60_000, // 5 minutes
    refetchInterval: 10 * 60_000, // 10 minutes
    ...options,
  })
}

// ---------------------------------------------------------------------------
// useMaintenanceLogs — maintenance log entries, optionally filtered by vehicle
// ---------------------------------------------------------------------------

export function useMaintenanceLogs(
  vehicleId?: string,
  options?: Omit<
    UseQueryOptions<{ count: number; results: MaintenanceLog[] }>,
    'queryKey' | 'queryFn'
  >
) {
  return useQuery<{ count: number; results: MaintenanceLog[] }>({
    queryKey: fleetKeys.maintenanceLogs(vehicleId),
    queryFn: () =>
      fleetApi.listMaintenanceLogs(vehicleId) as unknown as Promise<{
        count: number
        results: MaintenanceLog[]
      }>,
    staleTime: 60_000,
    ...options,
  })
}

// ---------------------------------------------------------------------------
// useFleetStats
// ---------------------------------------------------------------------------

export function useFleetStats(
  options?: Omit<UseQueryOptions<FleetStats>, 'queryKey' | 'queryFn'>
) {
  return useQuery<FleetStats>({
    queryKey: fleetKeys.stats(),
    queryFn: () => fleetApi.getFleetStats() as unknown as Promise<FleetStats>,
    staleTime: 30_000,
    refetchInterval: 60_000,
    ...options,
  })
}

// ---------------------------------------------------------------------------
// useDrivers — list of drivers
// ---------------------------------------------------------------------------

export function useDrivers(
  params?: Record<string, unknown>,
  options?: Omit<
    UseQueryOptions<{ count: number; results: Driver[] }>,
    'queryKey' | 'queryFn'
  >
) {
  return useQuery<{ count: number; results: Driver[] }>({
    queryKey: fleetKeys.driverList(params),
    queryFn: () =>
      fleetApi.listDrivers(params) as unknown as Promise<{
        count: number
        results: Driver[]
      }>,
    staleTime: 60_000,
    ...options,
  })
}

// ---------------------------------------------------------------------------
// useTrips
// ---------------------------------------------------------------------------

export function useTrips(
  params?: { vehicle_id?: string; driver_id?: string; page?: number },
  options?: Omit<
    UseQueryOptions<{ count: number; results: Trip[] }>,
    'queryKey' | 'queryFn'
  >
) {
  return useQuery<{ count: number; results: Trip[] }>({
    queryKey: fleetKeys.trips(params),
    queryFn: () =>
      fleetApi.listTrips(params) as unknown as Promise<{
        count: number
        results: Trip[]
      }>,
    staleTime: 30_000,
    ...options,
  })
}

// ---------------------------------------------------------------------------
// useCreateVehicle
// ---------------------------------------------------------------------------

export function useCreateVehicle() {
  const queryClient = useQueryClient()

  return useMutation<Vehicle, Error, Record<string, unknown>>({
    mutationFn: (data) =>
      fleetApi.createVehicle(data) as unknown as Promise<Vehicle>,

    onSuccess: (newVehicle) => {
      // Invalidate all vehicle lists
      queryClient.invalidateQueries({ queryKey: fleetKeys.vehicles() })
      queryClient.invalidateQueries({ queryKey: fleetKeys.stats() })

      // Pre-populate detail cache
      queryClient.setQueryData<Vehicle>(
        fleetKeys.vehicleDetail(newVehicle.id),
        newVehicle
      )
    },
  })
}

// ---------------------------------------------------------------------------
// useUpdateVehicle
// ---------------------------------------------------------------------------

export function useUpdateVehicle() {
  const queryClient = useQueryClient()

  return useMutation<
    Vehicle,
    Error,
    { id: string; data: Partial<Record<string, unknown>> }
  >({
    mutationFn: ({ id, data }) =>
      fleetApi.updateVehicle(id, data) as unknown as Promise<Vehicle>,

    onSuccess: (updatedVehicle) => {
      queryClient.setQueryData<Vehicle>(
        fleetKeys.vehicleDetail(updatedVehicle.id),
        updatedVehicle
      )
      queryClient.invalidateQueries({ queryKey: fleetKeys.vehicles() })
      queryClient.invalidateQueries({ queryKey: fleetKeys.stats() })
    },

    // Optimistic update
    onMutate: async ({ id, data }) => {
      await queryClient.cancelQueries({
        queryKey: fleetKeys.vehicleDetail(id),
      })

      const previous = queryClient.getQueryData<Vehicle>(
        fleetKeys.vehicleDetail(id)
      )

      if (previous) {
        queryClient.setQueryData<Vehicle>(fleetKeys.vehicleDetail(id), {
          ...previous,
          ...(data as Partial<Vehicle>),
          updated_at: new Date().toISOString(),
        })
      }

      return { previous }
    },

    onError: (_err, { id }, context) => {
      const ctx = context as { previous?: Vehicle } | undefined
      if (ctx?.previous) {
        queryClient.setQueryData<Vehicle>(
          fleetKeys.vehicleDetail(id),
          ctx.previous
        )
      }
    },
  })
}

// ---------------------------------------------------------------------------
// useCreateMaintenanceLog
// ---------------------------------------------------------------------------

export function useCreateMaintenanceLog() {
  const queryClient = useQueryClient()

  return useMutation<MaintenanceLog, Error, Record<string, unknown>>({
    mutationFn: (data) =>
      fleetApi.createMaintenanceLog(data) as unknown as Promise<MaintenanceLog>,

    onSuccess: (log) => {
      queryClient.invalidateQueries({
        queryKey: fleetKeys.maintenanceLogs(log.vehicle_id),
      })
      queryClient.invalidateQueries({ queryKey: fleetKeys.maintenanceDue() })
      // Refresh vehicle detail so next_service_date is updated
      queryClient.invalidateQueries({
        queryKey: fleetKeys.vehicleDetail(log.vehicle_id),
      })
    },
  })
}

// ---------------------------------------------------------------------------
// useUpdateMaintenanceLog
// ---------------------------------------------------------------------------

export function useUpdateMaintenanceLog() {
  const queryClient = useQueryClient()

  return useMutation<
    MaintenanceLog,
    Error,
    { id: string; data: Partial<Record<string, unknown>> }
  >({
    mutationFn: ({ id, data }) =>
      fleetApi.updateMaintenanceLog(id, data) as unknown as Promise<MaintenanceLog>,

    onSuccess: (log) => {
      queryClient.invalidateQueries({
        queryKey: fleetKeys.maintenanceLogs(log.vehicle_id),
      })
      queryClient.invalidateQueries({ queryKey: fleetKeys.maintenanceDue() })
      queryClient.invalidateQueries({
        queryKey: fleetKeys.vehicleDetail(log.vehicle_id),
      })
    },
  })
}

// ---------------------------------------------------------------------------
// Utility — derive fleet summary counts from a vehicle list
// ---------------------------------------------------------------------------

export function deriveFleetCounts(vehicles: Vehicle[]): {
  available: number
  on_trip: number
  maintenance: number
  breakdown: number
  retired: number
  total: number
  utilisation_rate_percent: number
} {
  const counts = {
    available: 0,
    on_trip: 0,
    maintenance: 0,
    breakdown: 0,
    retired: 0,
  }

  for (const v of vehicles) {
    if (v.status in counts) {
      counts[v.status as keyof typeof counts]++
    }
  }

  const total = vehicles.length
  const active = counts.on_trip
  const utilisation_rate_percent =
    total > 0 ? Math.round((active / (total - counts.retired)) * 100) : 0

  return { ...counts, total, utilisation_rate_percent }
}

// ---------------------------------------------------------------------------
// Utility — urgency colour mapping for maintenance items
// ---------------------------------------------------------------------------

export const MAINTENANCE_URGENCY_COLORS: Record<
  MaintenanceDueItem['urgency'],
  { text: string; bg: string; border: string }
> = {
  overdue:  { text: 'text-red-400',    bg: 'bg-red-900/30',    border: 'border-red-700' },
  critical: { text: 'text-orange-400', bg: 'bg-orange-900/30', border: 'border-orange-700' },
  warning:  { text: 'text-amber-400',  bg: 'bg-amber-900/30',  border: 'border-amber-700' },
  upcoming: { text: 'text-brand-400',   bg: 'bg-brand-900/30',   border: 'border-brand-700' },
}
