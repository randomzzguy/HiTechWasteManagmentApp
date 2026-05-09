export type SDGGoal =
  | 'SDG_3'   // Good Health and Well-being
  | 'SDG_6'   // Clean Water and Sanitation
  | 'SDG_7'   // Affordable and Clean Energy
  | 'SDG_8'   // Decent Work and Economic Growth
  | 'SDG_9'   // Industry, Innovation and Infrastructure
  | 'SDG_11'  // Sustainable Cities and Communities
  | 'SDG_12'  // Responsible Consumption and Production
  | 'SDG_13'  // Climate Action
  | 'SDG_14'  // Life Below Water
  | 'SDG_15'  // Life on Land
  | 'SDG_17'; // Partnerships for the Goals

export type ReportingFramework =
  | 'GRI'       // Global Reporting Initiative
  | 'TCFD'      // Task Force on Climate-related Financial Disclosures
  | 'SASB'      // Sustainability Accounting Standards Board
  | 'CDP'       // Carbon Disclosure Project
  | 'UN_SDG'    // UN Sustainable Development Goals
  | 'BURSA_SR'  // Bursa Malaysia Sustainability Reporting
  | 'ISO_14001' // Environmental Management
  | 'ISO_50001'; // Energy Management

export type EmissionScope = 'scope_1' | 'scope_2' | 'scope_3';

export type CarbonUnit = 'kg_co2e' | 'tonne_co2e';

export interface SDGTag {
  goal: SDGGoal;
  goal_number: number;
  title: string;
  description: string;
  icon_url?: string;
  color: string;
  relevance_score: number; // 0-100
  supporting_activities: string[];
  metrics_achieved: SDGMetric[];
}

export interface SDGMetric {
  indicator: string;
  value: number;
  unit: string;
  description: string;
  period: string;
}

export interface CarbonRecord {
  id: string;
  client_id?: string;
  client_name?: string;
  job_id?: string;
  job_number?: string;
  record_date: string;
  month: string; // YYYY-MM
  scope: EmissionScope;
  activity_type:
    | 'transport_collection'
    | 'transport_disposal'
    | 'waste_disposal_landfill'
    | 'waste_incineration'
    | 'waste_composting'
    | 'recycling_avoided'
    | 'energy_recovery'
    | 'bsf_processing'
    | 'facility_operations'
    | 'other';
  description: string;
  quantity: number;
  quantity_unit: string;
  emission_factor: number;
  emission_factor_source: string;
  gross_emissions_kg_co2e: number;
  avoided_emissions_kg_co2e: number;
  net_emissions_kg_co2e: number;
  is_verified: boolean;
  verified_by?: string;
  verified_at?: string;
  notes?: string;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface DiversionRate {
  period: string; // YYYY-MM or YYYY-QQ or YYYY
  period_label: string;
  total_waste_kg: number;
  diverted_kg: number;
  landfilled_kg: number;
  incinerated_kg: number;
  recycled_kg: number;
  composted_kg: number;
  energy_recovered_kg: number;
  bsf_processed_kg: number;
  diversion_rate_percent: number;
  target_diversion_rate_percent?: number;
  target_met: boolean;
  vs_previous_period_percent?: number;
}

export interface MaterialRecovery {
  material_code: string;
  material_name: string;
  material_category: string;
  quantity_recovered_kg: number;
  market_value_myr: number;
  carbon_avoided_kg_co2e: number;
  end_destination: string;
  recycler_name?: string;
  recycler_licence?: string;
  certificate_url?: string;
}

export interface ESGDashboard {
  client_id: string;
  client_name: string;
  client_account_code: string;
  reporting_period_start: string;
  reporting_period_end: string;
  generated_at: string;

  // Waste metrics
  total_waste_generated_kg: number;
  total_waste_diverted_kg: number;
  total_waste_disposed_kg: number;
  diversion_rate_percent: number;
  diversion_rate_target_percent?: number;
  diversion_vs_target_percent?: number;

  // Carbon metrics
  total_gross_emissions_kg_co2e: number;
  total_avoided_emissions_kg_co2e: number;
  net_carbon_impact_kg_co2e: number;
  carbon_intensity_kg_per_tonne_waste?: number;

  // Recovery metrics
  total_recyclables_kg: number;
  total_recyclables_value_myr: number;
  scheduled_waste_diverted_kg: number;
  bsf_processed_kg: number;
  energy_recovered_mwh?: number;

  // Trend data
  monthly_diversion_rates: DiversionRate[];
  monthly_carbon_records: MonthlyCarbonSummary[];
  material_recovery_breakdown: MaterialRecovery[];

  // SDG alignment
  sdg_alignments: SDGTag[];

  // Compliance
  certifications_issued: number;
  consignment_notes_count: number;
  compliance_score_percent: number;

  // Comparative
  vs_industry_average_diversion_percent?: number;
  vs_national_average_diversion_percent?: number;
  peer_percentile?: number;
}

export interface MonthlyCarbonSummary {
  month: string; // YYYY-MM
  month_label: string;
  gross_emissions_kg_co2e: number;
  avoided_emissions_kg_co2e: number;
  net_emissions_kg_co2e: number;
  transport_emissions_kg_co2e: number;
  disposal_emissions_kg_co2e: number;
  recycling_credits_kg_co2e: number;
}

export interface CompanyESGDashboard {
  reporting_period_start: string;
  reporting_period_end: string;
  generated_at: string;

  // Portfolio metrics
  total_clients_reporting: number;
  total_waste_processed_kg: number;
  total_waste_diverted_kg: number;
  overall_diversion_rate_percent: number;
  overall_diversion_target_percent: number;

  // Carbon portfolio
  total_gross_emissions_kg_co2e: number;
  total_avoided_emissions_kg_co2e: number;
  net_carbon_impact_kg_co2e: number;
  carbon_credits_generated?: number;

  // Fleet emissions
  fleet_transport_emissions_kg_co2e: number;
  fleet_total_distance_km: number;
  fleet_fuel_consumed_litres: number;
  fleet_avg_emission_intensity_kg_per_km: number;

  // Recovery highlights
  total_recyclables_recovered_kg: number;
  total_recyclables_value_myr: number;
  total_scheduled_waste_processed_kg: number;
  total_bsf_processed_kg: number;
  total_destruction_kg: number;

  // Monthly trends
  monthly_diversion_rates: DiversionRate[];
  monthly_carbon_summary: MonthlyCarbonSummary[];
  top_clients_by_diversion: ClientDiversionSummary[];
  waste_stream_breakdown: WasteStreamESG[];

  // SDG alignment
  company_sdg_alignments: SDGTag[];

  // Certifications & compliance
  total_certifications_issued: number;
  total_consignment_notes: number;
  doe_audits_passed: number;
  regulatory_compliance_score: number;

  // Reporting frameworks tracked
  frameworks: ReportingFramework[];
}

export interface ClientDiversionSummary {
  client_id: string;
  client_name: string;
  total_waste_kg: number;
  diverted_kg: number;
  diversion_rate_percent: number;
  rank: number;
}

export interface WasteStreamESG {
  material_code: string;
  material_name: string;
  category: 'recyclable' | 'scheduled_waste' | 'general' | 'organic' | 'clinical' | 'e_waste';
  total_kg: number;
  percent_of_total: number;
  diverted_kg: number;
  diversion_rate_percent: number;
  carbon_avoided_kg_co2e: number;
  revenue_myr?: number;
}

export interface ESGReportConfig {
  client_id?: string; // null = company-wide
  period_start: string;
  period_end: string;
  frameworks: ReportingFramework[];
  include_carbon_detail: boolean;
  include_sdg_mapping: boolean;
  include_material_recovery: boolean;
  include_compliance_summary: boolean;
  include_comparative_analysis: boolean;
  branding_logo_url?: string;
  custom_message?: string;
  output_format: 'pdf' | 'excel' | 'json';
}

export interface ESGReportJob {
  id: string;
  config: ESGReportConfig;
  status: 'queued' | 'generating' | 'completed' | 'failed';
  progress_percent: number;
  download_url?: string;
  error_message?: string;
  created_by: string;
  created_at: string;
  completed_at?: string;
}

export interface CarbonIntensityBenchmark {
  industry_type: string;
  metric: string;
  unit: string;
  company_value: number;
  industry_average: number;
  best_in_class: number;
  percentile_rank: number;
}

export interface GHGInventory {
  reporting_year: number;
  scope_1_total_kg_co2e: number;
  scope_2_total_kg_co2e: number;
  scope_3_total_kg_co2e: number;
  total_kg_co2e: number;
  base_year: number;
  base_year_total_kg_co2e: number;
  reduction_vs_base_year_percent: number;
  reduction_target_percent: number;
  target_year: number;
  methodology: string;
  verification_statement?: string;
  verified_by?: string;
}
