export type ClientStatus = 'active' | 'inactive' | 'suspended' | 'prospect';

export type ClientTier = 'standard' | 'premium' | 'enterprise';

export type IndustryType =
  | 'manufacturing'
  | 'healthcare'
  | 'hospitality'
  | 'retail'
  | 'construction'
  | 'education'
  | 'government'
  | 'food_beverage'
  | 'chemical'
  | 'electronics'
  | 'logistics'
  | 'other';

export interface ClientContact {
  id: string;
  name: string;
  title: string;
  email: string;
  phone: string;
  is_primary: boolean;
  receives_reports: boolean;
  receives_invoices: boolean;
}

export interface ClientAddress {
  line1: string;
  line2?: string;
  city: string;
  state: string;
  postcode: string;
  country: string;
  lat?: number;
  lng?: number;
}

export interface ClientWasteStream {
  id: string;
  client_id: string;
  material_code: string;
  material_name: string;
  sw_code?: string;
  is_scheduled_waste: boolean;
  typical_quantity_kg_per_month: number;
  unit_rate_myr: number;
  collection_frequency: string;
  last_collected_at?: string;
  notes?: string;
}

export interface ClientContract {
  id: string;
  contract_number: string;
  start_date: string;
  end_date: string;
  is_active: boolean;
  monthly_value_myr: number;
  payment_terms_days: number;
  auto_renew: boolean;
  document_url?: string;
}

export interface ClientCertificate {
  id: string;
  cert_type: 'scheduled_waste_disposal' | 'recycling' | 'destruction' | 'iso_compliance' | 'esg_report';
  cert_number: string;
  issued_date: string;
  expiry_date?: string;
  issued_by: string;
  document_url: string;
  job_id?: string;
}

export interface Client {
  id: string;
  account_code: string;
  company_name: string;
  trade_name?: string;
  industry: IndustryType;
  status: ClientStatus;
  tier: ClientTier;
  registration_number: string;
  tax_id?: string;
  billing_address: ClientAddress;
  site_address: ClientAddress;
  contacts: ClientContact[];
  waste_streams: ClientWasteStream[];
  active_contract?: ClientContract;
  contracts: ClientContract[];
  certificates: ClientCertificate[];
  credit_limit_myr: number;
  outstanding_balance_myr: number;
  payment_terms_days: number;
  account_manager_id?: string;
  account_manager_name?: string;
  notes?: string;
  tags: string[];
  created_at: string;
  updated_at: string;
  last_job_date?: string;
  total_jobs_count: number;
  total_tonnage_kg: number;
  total_revenue_myr: number;
  esg_reporting_enabled: boolean;
  portal_access_enabled: boolean;
}

export interface ClientCreate {
  company_name: string;
  trade_name?: string;
  industry: IndustryType;
  registration_number: string;
  tax_id?: string;
  billing_address: ClientAddress;
  site_address: ClientAddress;
  contacts: Omit<ClientContact, 'id' | 'client_id'>[];
  tier?: ClientTier;
  credit_limit_myr?: number;
  payment_terms_days?: number;
  account_manager_id?: string;
  notes?: string;
  tags?: string[];
  esg_reporting_enabled?: boolean;
  portal_access_enabled?: boolean;
}

export interface ClientUpdate {
  company_name?: string;
  trade_name?: string;
  industry?: IndustryType;
  status?: ClientStatus;
  tier?: ClientTier;
  registration_number?: string;
  tax_id?: string;
  billing_address?: Partial<ClientAddress>;
  site_address?: Partial<ClientAddress>;
  credit_limit_myr?: number;
  payment_terms_days?: number;
  account_manager_id?: string;
  notes?: string;
  tags?: string[];
  esg_reporting_enabled?: boolean;
  portal_access_enabled?: boolean;
}

export interface ESGSummary {
  client_id: string;
  client_name: string;
  period_start: string;
  period_end: string;
  total_waste_generated_kg: number;
  total_waste_diverted_kg: number;
  total_waste_disposed_kg: number;
  diversion_rate_percent: number;
  carbon_avoided_kg_co2e: number;
  carbon_emitted_kg_co2e: number;
  net_carbon_impact_kg_co2e: number;
  recyclables_recovered_kg: number;
  scheduled_waste_disposed_kg: number;
  waste_by_stream: WasteByStream[];
  monthly_breakdown: MonthlyESGBreakdown[];
  sdg_alignments: string[];
  certifications_issued: number;
  report_generated_at: string;
}

export interface WasteByStream {
  material_code: string;
  material_name: string;
  total_kg: number;
  percent_of_total: number;
  destination: string;
  carbon_impact_kg_co2e: number;
}

export interface MonthlyESGBreakdown {
  month: string;
  total_kg: number;
  diverted_kg: number;
  disposed_kg: number;
  diversion_rate_percent: number;
  carbon_avoided_kg_co2e: number;
}

export interface ClientListParams {
  page?: number;
  page_size?: number;
  status?: ClientStatus;
  industry?: IndustryType;
  tier?: ClientTier;
  account_manager_id?: string;
  search?: string;
  ordering?: string;
}

export interface ClientListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: Client[];
}
