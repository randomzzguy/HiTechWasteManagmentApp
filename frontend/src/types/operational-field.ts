// =============================================================
// Hi-Tech Waste Management — Operational Field Management Types
// Compaction equipment, containers, labour, disruptions,
// and recycler deliveries.
// =============================================================

// ── Compaction Equipment ──────────────────────────────────────

export type CompactorStatus = 'available' | 'deployed' | 'maintenance' | 'decommissioned'

export interface CompactionMachine {
  id: string
  asset_tag: string
  model_name: string
  serial_number: string
  status: CompactorStatus
  purchase_date?: string
  compaction_force_kn?: number
  maintenance_interval_days: number
  last_service_date?: string
  next_service_date?: string
  notes?: string
  created_at: string
  updated_at: string
}

export interface CompactorDeployment {
  id: string
  machine_id: string
  client_id: string
  site_address: string
  deployment_start: string
  deployment_end?: string
  authorised_by?: string
  notes?: string
  created_at: string
}

export interface CompactorMaintenanceLog {
  id: string
  machine_id: string
  service_date: string
  service_type: string
  technician_name?: string
  cost_myr?: number
  logged_by?: string
  notes?: string
  created_at: string
}

// ── Containers ────────────────────────────────────────────────

export type ContainerStatus = 'available' | 'at_site' | 'in_transit' | 'at_recycler' | 'decommissioned'
export type ContainerType = 'skip_bin' | 'roll_on_roll_off' | 'compaction_chamber'

export interface Container {
  id: string
  container_code: string
  container_type: ContainerType
  capacity_m3?: number
  status: ContainerStatus
  current_client_id?: string
  current_site_address?: string
  current_compactor_id?: string
  target_material_type?: string
  fill_level: number
  pickup_threshold: number
  assigned_date?: string
  notes?: string
  created_at: string
  updated_at: string
}

export interface FillReading {
  id: string
  container_id: string
  fill_level: number
  recorded_at: string
  reported_by?: string
  photo_url?: string
  notes?: string
}

export interface PickupTrigger {
  id: string
  container_id: string
  triggered_at: string
  fill_level_at_trigger: number
  acknowledged_at?: string
  acknowledged_by?: string
  linked_job_id?: string
  is_active: boolean
  closed_at?: string
}

export interface TransportLogEntry {
  id: string
  from_status: string
  to_status: string
  transitioned_at: string
  responsible_user_id?: string
  vehicle_id?: string
  notes?: string
}

// ── Labour ────────────────────────────────────────────────────

export type EmploymentType = 'permanent' | 'contract' | 'foreign_worker'
export type StaffAssignmentStatus = 'available' | 'on_site' | 'on_leave' | 'inactive'
export type ShiftType = 'morning' | 'afternoon' | 'night'
export type AttendanceStatus = 'present' | 'absent' | 'no_checkout' | 'late'
export type AbsenceReason = 'sick_leave' | 'annual_leave' | 'no_show' | 'emergency'

export interface StaffProfile {
  id: string
  user_id: string
  employment_type: EmploymentType
  labour_agent_name?: string
  assignment_status: StaffAssignmentStatus
  current_site_assignment_id?: string
  work_permit_expiry?: string
  notes?: string
  created_at: string
  updated_at: string
}

export interface SiteAssignmentMember {
  id: string
  assignment_id: string
  staff_profile_id: string
  role_at_site: string
  joined_at: string
  left_at?: string
}

export interface SiteAssignment {
  id: string
  client_id: string
  site_address: string
  supervisor_id: string
  start_date: string
  end_date?: string
  is_active: boolean
  notes?: string
  created_at: string
  members: SiteAssignmentMember[]
}

export interface ShiftAttendance {
  id: string
  shift_id: string
  staff_profile_id: string
  status: AttendanceStatus
  check_in_at?: string
  check_out_at?: string
  absence_reason?: AbsenceReason
  notes?: string
}

export interface Shift {
  id: string
  site_assignment_id: string
  shift_date: string
  shift_type: ShiftType
  start_time: string
  end_time: string
  created_by?: string
  notes?: string
  created_at: string
  attendances: ShiftAttendance[]
}

// ── Disruptions ───────────────────────────────────────────────

export type DisruptionType =
  | 'landfill_delay'
  | 'highway_restriction'
  | 'vehicle_breakdown'
  | 'site_access_denied'
  | 'other'

export type DisruptionStatus = 'open' | 'resolved'
export type DisruptionSeverity = 'info' | 'warning' | 'critical'

export interface DisruptionJobImpact {
  id: string
  disruption_id: string
  job_id: string
  estimated_delay_minutes?: number
  original_scheduled_completion?: string
  revised_estimated_completion?: string
  notes?: string
}

export interface ResolutionHistoryEntry {
  text: string
  timestamp: string
  resolver_id: string
}

export interface DisruptionLog {
  id: string
  disruption_type: DisruptionType
  status: DisruptionStatus
  severity: DisruptionSeverity
  occurred_at: string
  reported_by?: string
  description: string
  affected_job_ids?: string[]
  vehicle_id?: string
  highway_name?: string
  restriction_start_time?: string
  restriction_end_time?: string
  resolver_id?: string
  resolution_history?: ResolutionHistoryEntry[]
  closure_note?: string
  closed_at?: string
  closed_by?: string
  created_at: string
  updated_at: string
  job_impacts: DisruptionJobImpact[]
}

// ── Recycler Deliveries ───────────────────────────────────────

export type DeliveryStatus =
  | 'pending_departure'
  | 'in_transit'
  | 'arrived'
  | 'proof_submitted'
  | 'reconciliation_discrepancy'
  | 'completed'
  | 'cancelled'

export interface RecyclerDelivery {
  id: string
  container_id: string
  buyer_id: string
  vehicle_id?: string
  driver_id?: string
  status: DeliveryStatus
  declared_material_breakdown?: Record<string, number>
  declared_total_weight_kg?: number
  planned_departure_at?: string
  departed_at?: string
  arrived_at?: string
  proof_photos?: string[]
  weight_ticket_ref?: string
  recycler_recorded_weight_kg?: number
  proof_submitted_at?: string
  weight_variance_kg?: number
  weight_variance_pct?: number
  reconciliation_status?: string
  reconciliation_justification?: string
  buyer_rep_name?: string
  buyer_confirmed_breakdown?: Record<string, number>
  buyer_reference_number?: string
  buyer_confirmed_at?: string
  recyclable_record_id?: string
  created_at: string
  updated_at: string
}

export interface ReconciliationDetails {
  delivery_id: string
  declared_total_weight_kg?: number
  recycler_recorded_weight_kg?: number
  variance_kg?: number
  variance_pct?: number
  reconciliation_status?: string
}

// ── Operational Field Summary ─────────────────────────────────

export interface OperationalAlert {
  type: string
  severity: 'info' | 'warning' | 'critical'
  message: string
}

export interface OperationalFieldSummary {
  generated_at: string
  compaction_machines: Record<string, number>
  containers: Record<string, number>
  staff: Record<string, number>
  disruptions_open: Record<string, number>
  recycler_deliveries: Record<string, number>
  alerts: OperationalAlert[]
  alert_count: number
}
