export type JobStatus =
  | 'draft'
  | 'confirmed'
  | 'dispatched'
  | 'in_progress'
  | 'completed'
  | 'invoiced'
  | 'cancelled';

export type JobType =
  | 'scheduled_waste'
  | 'recyclables'
  | 'general_waste'
  | 'destruction'
  | 'bsf_intake'
  | 'clinical_waste'
  | 'e_waste'
  | 'construction_waste';

export type RecurrenceFrequency = 'daily' | 'weekly' | 'fortnightly' | 'monthly' | 'quarterly';

export interface JobAddress {
  line1: string;
  line2?: string;
  city: string;
  state: string;
  postcode: string;
  country: string;
  lat?: number;
  lng?: number;
}

export interface WeighbridgeRecord {
  id: string;
  tare_weight_kg: number;
  gross_weight_kg: number;
  net_weight_kg: number;
  timestamp: string;
  operator_name: string;
  vehicle_registration: string;
}

export interface JobDocument {
  id: string;
  name: string;
  type: 'consignment_note' | 'certificate' | 'photo' | 'invoice' | 'manifest' | 'other';
  url: string;
  uploaded_at: string;
  uploaded_by: string;
  size_bytes: number;
}

export interface JobTimeline {
  id: string;
  status: JobStatus;
  timestamp: string;
  actor_name: string;
  actor_id: string;
  note?: string;
}

export interface Job {
  id: string;
  job_number: string;
  client_id: string;
  client_name: string;
  client_account_code: string;
  job_type: JobType;
  status: JobStatus;
  scheduled_date: string;
  scheduled_time?: string;
  completed_at?: string;
  pickup_address: JobAddress;
  disposal_site?: string;
  vehicle_id?: string;
  vehicle_registration?: string;
  driver_id?: string;
  driver_name?: string;
  estimated_weight_kg?: number;
  actual_weight_kg?: number;
  waste_streams: string[];
  sw_codes?: string[];
  notes?: string;
  internal_notes?: string;
  weighbridge_record?: WeighbridgeRecord;
  documents: JobDocument[];
  timeline: JobTimeline[];
  recurring_template_id?: string;
  is_recurring: boolean;
  priority: 'low' | 'normal' | 'high' | 'urgent';
  created_at: string;
  updated_at: string;
  created_by: string;
  invoice_id?: string;
  total_amount?: number;
  po_number?: string;
}

export interface JobCreate {
  client_id: string;
  job_type: JobType;
  scheduled_date: string;
  scheduled_time?: string;
  pickup_address: JobAddress;
  disposal_site?: string;
  vehicle_id?: string;
  driver_id?: string;
  estimated_weight_kg?: number;
  waste_streams: string[];
  sw_codes?: string[];
  notes?: string;
  priority?: 'low' | 'normal' | 'high' | 'urgent';
  is_recurring?: boolean;
  recurring_template_id?: string;
  po_number?: string;
}

export interface JobUpdate {
  status?: JobStatus;
  scheduled_date?: string;
  scheduled_time?: string;
  pickup_address?: Partial<JobAddress>;
  disposal_site?: string;
  vehicle_id?: string;
  driver_id?: string;
  estimated_weight_kg?: number;
  waste_streams?: string[];
  sw_codes?: string[];
  notes?: string;
  internal_notes?: string;
  priority?: 'low' | 'normal' | 'high' | 'urgent';
  po_number?: string;
}

export interface RecurringTemplate {
  id: string;
  client_id: string;
  client_name: string;
  job_type: JobType;
  frequency: RecurrenceFrequency;
  day_of_week?: number;
  day_of_month?: number;
  pickup_address: JobAddress;
  vehicle_id?: string;
  driver_id?: string;
  estimated_weight_kg?: number;
  waste_streams: string[];
  sw_codes?: string[];
  notes?: string;
  is_active: boolean;
  next_scheduled: string;
  last_generated: string;
  created_at: string;
  updated_at: string;
}

export interface JobListParams {
  page?: number;
  page_size?: number;
  status?: JobStatus | JobStatus[];
  job_type?: JobType;
  client_id?: string;
  driver_id?: string;
  vehicle_id?: string;
  date_from?: string;
  date_to?: string;
  search?: string;
  ordering?: string;
}

export interface JobListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: Job[];
}

export interface JobStatusCount {
  status: JobStatus;
  count: number;
}

export interface JobKanbanColumn {
  status: JobStatus;
  label: string;
  jobs: Job[];
  color: string;
}
