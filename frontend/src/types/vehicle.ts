export type VehicleStatus = 'available' | 'on_trip' | 'maintenance' | 'breakdown' | 'retired';

export type VehicleType =
  | 'lorry'
  | 'compactor'
  | 'roll_on_roll_off'
  | 'tanker'
  | 'van'
  | 'pickup'
  | 'crane_truck'
  | 'tipper';

export type FuelType = 'diesel' | 'petrol' | 'electric' | 'hybrid' | 'cng';

export type MaintenanceType =
  | 'scheduled_service'
  | 'oil_change'
  | 'tyre_replacement'
  | 'brake_service'
  | 'engine_repair'
  | 'electrical'
  | 'body_repair'
  | 'roadworthy_inspection'
  | 'puspakom'
  | 'other';

export interface GPSLocation {
  lat: number;
  lng: number;
  speed_kmh?: number;
  heading?: number;
  altitude_m?: number;
  accuracy_m?: number;
  timestamp: string;
}

export interface Driver {
  id: string;
  employee_id: string;
  full_name: string;
  license_number: string;
  license_class: string;
  license_expiry: string;
  phone: string;
  email?: string;
  status: 'available' | 'on_duty' | 'off_duty' | 'on_leave' | 'inactive';
  current_vehicle_id?: string;
  current_vehicle_registration?: string;
  profile_photo_url?: string;
  joined_date: string;
  total_trips: number;
  total_distance_km: number;
}

export interface Vehicle {
  id: string;
  registration: string;
  make: string;
  model: string;
  year: number;
  vehicle_type: VehicleType;
  fuel_type: FuelType;
  status: VehicleStatus;
  payload_capacity_kg: number;
  volume_capacity_m3?: number;
  current_driver_id?: string;
  current_driver_name?: string;
  last_gps_location?: GPSLocation;
  odometer_km: number;
  next_service_km?: number;
  next_service_date?: string;
  road_tax_expiry: string;
  insurance_expiry: string;
  puspakom_expiry: string;
  purchase_date: string;
  purchase_price_myr?: number;
  depot_id?: string;
  depot_name?: string;
  notes?: string;
  tags: string[];
  active_trip_id?: string;
  total_trips: number;
  total_distance_km: number;
  total_tonnage_kg: number;
  created_at: string;
  updated_at: string;
}

export interface Trip {
  id: string;
  trip_number: string;
  job_id: string;
  job_number: string;
  vehicle_id: string;
  vehicle_registration: string;
  driver_id: string;
  driver_name: string;
  status: 'pending' | 'en_route_pickup' | 'at_pickup' | 'en_route_disposal' | 'at_disposal' | 'completed' | 'cancelled';
  started_at?: string;
  completed_at?: string;
  pickup_address: string;
  disposal_site: string;
  start_odometer_km?: number;
  end_odometer_km?: number;
  distance_km?: number;
  fuel_consumed_litres?: number;
  cargo_weight_kg?: number;
  gps_track: GPSLocation[];
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface MaintenanceLog {
  id: string;
  vehicle_id: string;
  vehicle_registration: string;
  maintenance_type: MaintenanceType;
  description: string;
  status: 'scheduled' | 'in_progress' | 'completed' | 'overdue' | 'cancelled';
  scheduled_date: string;
  completed_date?: string;
  odometer_at_service_km?: number;
  next_service_km?: number;
  next_service_date?: string;
  workshop_name?: string;
  technician_name?: string;
  parts_cost_myr?: number;
  labour_cost_myr?: number;
  total_cost_myr?: number;
  invoice_number?: string;
  document_url?: string;
  notes?: string;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface VehicleListParams {
  page?: number;
  page_size?: number;
  status?: VehicleStatus | VehicleStatus[];
  vehicle_type?: VehicleType;
  depot_id?: string;
  driver_id?: string;
  search?: string;
  ordering?: string;
}

export interface VehicleListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: Vehicle[];
}

export interface MaintenanceDueItem {
  vehicle_id: string;
  vehicle_registration: string;
  vehicle_type: VehicleType;
  maintenance_type: MaintenanceType;
  due_date: string;
  days_until_due: number;
  odometer_km: number;
  km_until_due?: number;
  urgency: 'overdue' | 'critical' | 'warning' | 'upcoming';
  last_service_date?: string;
}

export interface FleetStats {
  total_vehicles: number;
  available: number;
  on_trip: number;
  maintenance: number;
  breakdown: number;
  retired: number;
  utilisation_rate_percent: number;
  total_distance_today_km: number;
  total_trips_today: number;
  maintenance_due_7_days: number;
}
