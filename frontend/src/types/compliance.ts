export type BatchStatus =
  | 'in_storage'
  | 'pending_disposal'
  | 'consigned'
  | 'disposed'
  | 'overdue'
  | 'rejected';

export type SWCategory =
  | 'SW1'   // Used oil
  | 'SW2'   // Spent solvent
  | 'SW3'   // Waste containing mercury
  | 'SW4'   // Waste containing cadmium
  | 'SW5'   // Pesticide waste
  | 'SW6'   // Pharmaceutical waste
  | 'SW7'   // Halogenated organic solvents
  | 'SW8'   // Non-halogenated organic solvents
  | 'SW9'   // Acid or alkaline solutions
  | 'SW10'  // Waste oil or water emulsions
  | 'SW11'  // Reactive chemicals
  | 'SW312' // Cytotoxic drugs
  | 'SW322' // Clinical waste
  | 'SW408' // Contaminated containers
  | 'SW409' // Contaminated absorbent materials
  | 'SW410' // Contaminated equipment
  | 'SW411' // Fly ash / bottom ash
  | 'SW412' // Sludge from industrial processes';

export type DisposalMethod =
  | 'incineration'
  | 'chemical_treatment'
  | 'solidification'
  | 'landfill_approved'
  | 'recovery'
  | 'neutralisation'
  | 'encapsulation'
  | 'export';

export interface SWCode {
  code: string;
  category: SWCategory;
  description: string;
  disposal_methods: DisposalMethod[];
  max_storage_days: number;
  requires_etp: boolean;
  is_reactive: boolean;
  is_flammable: boolean;
  is_toxic: boolean;
  is_corrosive: boolean;
  un_number?: string;
  hazard_class?: string;
  packaging_group?: string;
  handling_instructions: string;
  ppe_required: string[];
  emergency_procedure?: string;
  created_at: string;
  updated_at: string;
}

export interface StorageLocation {
  id: string;
  facility_name: string;
  location_code: string;
  area_name: string;
  capacity_kg: number;
  current_load_kg: number;
  is_dedicated_sw: boolean;
  temperature_controlled: boolean;
  segregation_zone: string;
}

export interface ScheduledWasteBatch {
  id: string;
  batch_number: string;
  client_id: string;
  client_name: string;
  client_account_code: string;
  sw_code: string;
  sw_description: string;
  sw_category: SWCategory;
  status: BatchStatus;
  quantity_kg: number;
  quantity_litres?: number;
  physical_state: 'solid' | 'liquid' | 'sludge' | 'gas';
  storage_start_date: string;
  disposal_deadline: string;
  days_in_storage: number;
  days_until_deadline: number;
  is_overdue: boolean;
  storage_location_id?: string;
  storage_location?: StorageLocation;
  container_count: number;
  container_type: string;
  disposal_method: DisposalMethod;
  approved_contractor_id?: string;
  approved_contractor_name?: string;
  consignment_note_id?: string;
  consignment_note_number?: string;
  job_id?: string;
  job_number?: string;
  received_from_client_date?: string;
  disposed_date?: string;
  disposal_facility?: string;
  disposal_licence_number?: string;
  manifest_number?: string;
  hazard_class?: string;
  un_number?: string;
  packaging_group?: string;
  temperature_min_c?: number;
  temperature_max_c?: number;
  special_handling_notes?: string;
  documents: BatchDocument[];
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface BatchDocument {
  id: string;
  doc_type: 'consignment_note' | 'disposal_certificate' | 'lab_analysis' | 'manifest' | 'photo' | 'other';
  name: string;
  url: string;
  uploaded_at: string;
  uploaded_by: string;
}

export interface ConsignmentNote {
  id: string;
  note_number: string;
  batch_id: string;
  batch_number: string;
  client_id: string;
  client_name: string;
  client_address: string;
  client_contact_name: string;
  client_contact_phone: string;
  sw_code: string;
  sw_description: string;
  quantity_kg: number;
  quantity_litres?: number;
  physical_state: string;
  container_count: number;
  container_type: string;
  hazard_class: string;
  un_number?: string;
  disposal_method: DisposalMethod;
  contractor_name: string;
  contractor_licence: string;
  contractor_address: string;
  disposal_facility_name: string;
  disposal_facility_address: string;
  disposal_facility_licence: string;
  transport_vehicle_registration: string;
  driver_name: string;
  driver_ic_number: string;
  scheduled_transport_date: string;
  actual_transport_date?: string;
  received_at_facility_date?: string;
  received_by?: string;
  generator_signature?: string;
  contractor_signature?: string;
  facility_signature?: string;
  doe_form_a_reference?: string;
  status: 'draft' | 'issued' | 'in_transit' | 'received' | 'completed' | 'rejected';
  rejection_reason?: string;
  special_instructions?: string;
  emergency_contact_name: string;
  emergency_contact_phone: string;
  document_url?: string;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface ComplianceDeadline {
  id: string;
  type: 'sw_disposal' | 'licence_renewal' | 'audit' | 'report_submission' | 'doe_notification';
  title: string;
  description: string;
  due_date: string;
  days_until_due: number;
  is_overdue: boolean;
  severity: 'info' | 'warning' | 'critical';
  related_entity_type?: string;
  related_entity_id?: string;
  related_entity_name?: string;
  assigned_to_id?: string;
  assigned_to_name?: string;
  is_completed: boolean;
  completed_at?: string;
  completed_by?: string;
  notes?: string;
}

export interface ComplianceSummary {
  total_sw_batches: number;
  in_storage: number;
  pending_disposal: number;
  consigned: number;
  overdue: number;
  disposed_this_month: number;
  total_sw_kg_in_storage: number;
  upcoming_deadlines_7_days: number;
  upcoming_deadlines_30_days: number;
  overdue_count: number;
  compliance_score_percent: number;
  last_doe_audit_date?: string;
  next_doe_audit_date?: string;
  doe_licence_number: string;
  doe_licence_expiry: string;
}

export interface ScheduledWasteListParams {
  page?: number;
  page_size?: number;
  status?: BatchStatus | BatchStatus[];
  sw_code?: string;
  client_id?: string;
  date_from?: string;
  date_to?: string;
  is_overdue?: boolean;
  search?: string;
  ordering?: string;
}

export interface ScheduledWasteListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: ScheduledWasteBatch[];
}

export interface DOELicence {
  id: string;
  licence_number: string;
  licence_type: 'contractor' | 'facility' | 'storage' | 'transport';
  issued_to: string;
  issued_date: string;
  expiry_date: string;
  covered_sw_codes: string[];
  disposal_methods_covered: DisposalMethod[];
  status: 'active' | 'expired' | 'suspended' | 'pending_renewal';
  document_url?: string;
}
