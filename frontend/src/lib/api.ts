import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios'

// ---------------------------------------------------------------------------
// Axios instance
// ---------------------------------------------------------------------------

const api: AxiosInstance = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000',
  timeout: 30_000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// ---------------------------------------------------------------------------
// Request interceptor — inject Bearer token from sessionStorage
// ---------------------------------------------------------------------------

api.interceptors.request.use(
  (config) => {
    if (typeof window !== 'undefined') {
      const token =
        sessionStorage.getItem('access_token') ??
        localStorage.getItem('access_token')
      if (token) {
        config.headers = config.headers ?? {}
        config.headers['Authorization'] = `Bearer ${token}`
      }
    }
    return config
  },
  (error) => Promise.reject(error)
)

// ---------------------------------------------------------------------------
// Response interceptor — handle 401 → redirect to /login
// ---------------------------------------------------------------------------

api.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error) => {
    if (error.response?.status === 401) {
      if (typeof window !== 'undefined') {
        sessionStorage.removeItem('access_token')
        localStorage.removeItem('access_token')
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default api

// ---------------------------------------------------------------------------
// Generic helpers
// ---------------------------------------------------------------------------

function getData<T>(res: AxiosResponse<T>): T {
  return res.data
}

// ---------------------------------------------------------------------------
// Types used in API calls (lightweight — full types live in src/types/)
// ---------------------------------------------------------------------------

export interface PaginatedParams {
  page?: number
  page_size?: number
  search?: string
  ordering?: string
  [key: string]: unknown
}

export interface PaginatedResponse<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

// ---------------------------------------------------------------------------
// Auth API
// ---------------------------------------------------------------------------

export interface LoginPayload {
  email: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: {
    id: string
    email: string
    full_name: string
    role: string
    is_active: boolean
    profile_photo_url?: string
  }
}

export const authApi = {
  login: (email: string, password: string): Promise<LoginResponse> =>
    api
      .post<LoginResponse>('/api/v1/auth/login', { username: email, password })
      .then(getData),

  logout: (): Promise<void> =>
    api.post('/api/v1/auth/logout').then(() => undefined),

  me: (): Promise<LoginResponse['user']> =>
    api.get<LoginResponse['user']>('/api/v1/auth/me').then(getData),

  refreshToken: (refreshToken: string): Promise<LoginResponse> =>
    api
      .post<LoginResponse>('/api/v1/auth/refresh', { refresh_token: refreshToken })
      .then(getData),

  changePassword: (
    currentPassword: string,
    newPassword: string
  ): Promise<void> =>
    api
      .post('/api/v1/auth/change-password', {
        current_password: currentPassword,
        new_password: newPassword,
      })
      .then(() => undefined),
}

// ---------------------------------------------------------------------------
// Clients API
// ---------------------------------------------------------------------------

export interface ClientListParams extends PaginatedParams {
  status?: string
  industry?: string
  tier?: string
  account_manager_id?: string
}

export const clientsApi = {
  list: (params?: ClientListParams): Promise<PaginatedResponse<Record<string, unknown>>> =>
    api.get('/api/v1/clients/', { params }).then(getData),

  get: (id: string): Promise<Record<string, unknown>> =>
    api.get(`/api/v1/clients/${id}/`).then(getData),

  create: (data: Record<string, unknown>): Promise<Record<string, unknown>> =>
    api.post('/api/v1/clients/', data).then(getData),

  update: (
    id: string,
    data: Partial<Record<string, unknown>>
  ): Promise<Record<string, unknown>> =>
    api.patch(`/api/v1/clients/${id}/`, data).then(getData),

  delete: (id: string): Promise<void> =>
    api.delete(`/api/v1/clients/${id}/`).then(() => undefined),

  getWasteStreams: (id: string): Promise<Record<string, unknown>[]> =>
    api.get(`/api/v1/clients/${id}/waste-streams/`).then(getData),

  addWasteStream: (
    id: string,
    data: Record<string, unknown>
  ): Promise<Record<string, unknown>> =>
    api.post(`/api/v1/clients/${id}/waste-streams/`, data).then(getData),

  getCertificates: (id: string): Promise<Record<string, unknown>[]> =>
    api.get(`/api/v1/clients/${id}/certificates/`).then(getData),

  getESGSummary: (
    id: string,
    params?: { period_start?: string; period_end?: string }
  ): Promise<Record<string, unknown>> =>
    api.get(`/api/v1/clients/${id}/esg-summary/`, { params }).then(getData),
}

// ---------------------------------------------------------------------------
// Jobs API
// ---------------------------------------------------------------------------

export interface JobListParams extends PaginatedParams {
  status?: string | string[]
  job_type?: string
  client_id?: string
  driver_id?: string
  vehicle_id?: string
  date_from?: string
  date_to?: string
}

export const jobsApi = {
  list: (params?: JobListParams): Promise<PaginatedResponse<Record<string, unknown>>> =>
    api.get('/api/v1/jobs/', { params }).then(getData),

  get: (id: string): Promise<Record<string, unknown>> =>
    api.get(`/api/v1/jobs/${id}/`).then(getData),

  create: (data: Record<string, unknown>): Promise<Record<string, unknown>> =>
    api.post('/api/v1/jobs/', data).then(getData),

  update: (
    id: string,
    data: Partial<Record<string, unknown>>
  ): Promise<Record<string, unknown>> =>
    api.patch(`/api/v1/jobs/${id}/`, data).then(getData),

  updateStatus: (id: string, status: string, note?: string): Promise<Record<string, unknown>> =>
    api
      .post(`/api/v1/jobs/${id}/status/`, { status, note })
      .then(getData),

  delete: (id: string): Promise<void> =>
    api.delete(`/api/v1/jobs/${id}/`).then(() => undefined),

  getTimeline: (id: string): Promise<Record<string, unknown>[]> =>
    api.get(`/api/v1/jobs/${id}/timeline/`).then(getData),

  uploadDocument: (id: string, formData: FormData): Promise<Record<string, unknown>> =>
    api
      .post(`/api/v1/jobs/${id}/documents/`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then(getData),

  deleteDocument: (jobId: string, docId: string): Promise<void> =>
    api
      .delete(`/api/v1/jobs/${jobId}/documents/${docId}/`)
      .then(() => undefined),

  getStatusCounts: (): Promise<Record<string, number>> =>
    api.get('/api/v1/jobs/status-counts/').then(getData),
}

// ---------------------------------------------------------------------------
// Fleet API
// ---------------------------------------------------------------------------

export interface VehicleListParams extends PaginatedParams {
  status?: string | string[]
  vehicle_type?: string
  depot_id?: string
  driver_id?: string
}

export const fleetApi = {
  listVehicles: (
    params?: VehicleListParams
  ): Promise<PaginatedResponse<Record<string, unknown>>> =>
    api.get('/api/v1/fleet/vehicles/', { params }).then(getData),

  getVehicle: (id: string): Promise<Record<string, unknown>> =>
    api.get(`/api/v1/fleet/vehicles/${id}/`).then(getData),

  createVehicle: (data: Record<string, unknown>): Promise<Record<string, unknown>> =>
    api.post('/api/v1/fleet/vehicles/', data).then(getData),

  updateVehicle: (
    id: string,
    data: Partial<Record<string, unknown>>
  ): Promise<Record<string, unknown>> =>
    api.patch(`/api/v1/fleet/vehicles/${id}/`, data).then(getData),

  getMaintenanceDue: (): Promise<Record<string, unknown>[]> =>
    api.get('/api/v1/fleet/maintenance/due/').then(getData),

  listMaintenanceLogs: (
    vehicleId?: string
  ): Promise<PaginatedResponse<Record<string, unknown>>> =>
    api
      .get('/api/v1/fleet/maintenance/', {
        params: vehicleId ? { vehicle_id: vehicleId } : undefined,
      })
      .then(getData),

  createMaintenanceLog: (
    data: Record<string, unknown>
  ): Promise<Record<string, unknown>> =>
    api.post('/api/v1/fleet/maintenance/', data).then(getData),

  updateMaintenanceLog: (
    id: string,
    data: Partial<Record<string, unknown>>
  ): Promise<Record<string, unknown>> =>
    api.patch(`/api/v1/fleet/maintenance/${id}/`, data).then(getData),

  listDrivers: (
    params?: PaginatedParams
  ): Promise<PaginatedResponse<Record<string, unknown>>> =>
    api.get('/api/v1/fleet/drivers/', { params }).then(getData),

  getFleetStats: (): Promise<Record<string, unknown>> =>
    api.get('/api/v1/fleet/stats/').then(getData),

  listTrips: (
    params?: PaginatedParams & { vehicle_id?: string; driver_id?: string }
  ): Promise<PaginatedResponse<Record<string, unknown>>> =>
    api.get('/api/v1/fleet/trips/', { params }).then(getData),
}

// ---------------------------------------------------------------------------
// Weighbridge API
// ---------------------------------------------------------------------------

export interface TonnageStatsParams {
  period?: 'daily' | 'weekly' | 'monthly'
  date_from?: string
  date_to?: string
  client_id?: string
  job_type?: string
}

export interface DiversionStatsParams {
  period_start?: string
  period_end?: string
  client_id?: string
  granularity?: 'monthly' | 'quarterly' | 'yearly'
}

export const weighbridgeApi = {
  createRecord: (data: Record<string, unknown>): Promise<Record<string, unknown>> =>
    api.post('/api/v1/weighbridge/records/', data).then(getData),

  getRecord: (id: string): Promise<Record<string, unknown>> =>
    api.get(`/api/v1/weighbridge/records/${id}/`).then(getData),

  listRecords: (
    params?: PaginatedParams & { job_id?: string; date_from?: string; date_to?: string }
  ): Promise<PaginatedResponse<Record<string, unknown>>> =>
    api.get('/api/v1/weighbridge/records/', { params }).then(getData),

  updateRecord: (
    id: string,
    data: Partial<Record<string, unknown>>
  ): Promise<Record<string, unknown>> =>
    api.patch(`/api/v1/weighbridge/records/${id}/`, data).then(getData),

  getTonnageStats: (params?: TonnageStatsParams): Promise<Record<string, unknown>> =>
    api.get('/api/v1/weighbridge/stats/tonnage/', { params }).then(getData),

  getDiversionStats: (params?: DiversionStatsParams): Promise<Record<string, unknown>> =>
    api.get('/api/v1/weighbridge/stats/diversion/', { params }).then(getData),

  getMonthlyTonnage: (params?: {
    year?: number
    client_id?: string
  }): Promise<Record<string, unknown>[]> =>
    api.get('/api/v1/weighbridge/stats/monthly/', { params }).then(getData),
}

// ---------------------------------------------------------------------------
// Compliance API
// ---------------------------------------------------------------------------

export interface BatchListParams extends PaginatedParams {
  status?: string | string[]
  sw_code?: string
  client_id?: string
  date_from?: string
  date_to?: string
  is_overdue?: boolean
}

export const complianceApi = {
  listBatches: (
    params?: BatchListParams
  ): Promise<PaginatedResponse<Record<string, unknown>>> =>
    api.get('/api/v1/compliance/sw-batches', { params }).then(getData),

  getBatch: (id: string): Promise<Record<string, unknown>> =>
    api.get(`/api/v1/compliance/sw-batches/${id}`).then(getData),

  createBatch: (data: Record<string, unknown>): Promise<Record<string, unknown>> =>
    api.post('/api/v1/compliance/sw-batches', data).then(getData),

  updateBatch: (
    id: string,
    data: Partial<Record<string, unknown>>
  ): Promise<Record<string, unknown>> =>
    api.patch(`/api/v1/compliance/sw-batches/${id}`, data).then(getData),

  getDeadlines: (): Promise<Record<string, unknown>[]> =>
    api.get('/api/v1/compliance/deadlines').then(getData),

  listConsignmentNotes: (
    params?: PaginatedParams & { batch_id?: string; status?: string }
  ): Promise<PaginatedResponse<Record<string, unknown>>> =>
    api.get('/api/v1/compliance/consignment-notes', { params }).then(getData),

  getConsignmentNote: (id: string): Promise<Record<string, unknown>> =>
    api.get(`/api/v1/compliance/consignment-notes/${id}`).then(getData),

  createConsignmentNote: (
    data: Record<string, unknown>
  ): Promise<Record<string, unknown>> =>
    api.post('/api/v1/compliance/consignment-notes', data).then(getData),

  generateConsignmentNotePDF: (id: string): Promise<Blob> =>
    api
      .get(`/api/v1/compliance/consignment-notes/${id}/pdf`, {
        responseType: 'blob',
      })
      .then(getData),

  listSWCodes: (
    params?: PaginatedParams
  ): Promise<PaginatedResponse<Record<string, unknown>>> =>
    api.get('/api/v1/compliance/sw-codes', { params }).then(getData),

  getSWCode: (code: string): Promise<Record<string, unknown>> =>
    api.get(`/api/v1/compliance/sw-codes/${code}`).then(getData),

  getComplianceSummary: (): Promise<Record<string, unknown>> =>
    api.get('/api/v1/compliance/summary').then(getData),
}

// ---------------------------------------------------------------------------
// ESG API
// ---------------------------------------------------------------------------

export interface ESGDashboardParams {
  period_start?: string
  period_end?: string
  granularity?: 'monthly' | 'quarterly' | 'yearly'
}

export const esgApi = {
  getClientDashboard: (
    id: string,
    params?: ESGDashboardParams
  ): Promise<Record<string, unknown>> =>
    api.get(`/api/v1/esg/clients/${id}/dashboard/`, { params }).then(getData),

  getCompanyDashboard: (
    params?: ESGDashboardParams
  ): Promise<Record<string, unknown>> =>
    api.get('/api/v1/esg/company/dashboard/', { params }).then(getData),

  getCarbonRecords: (
    params?: PaginatedParams & {
      client_id?: string
      scope?: string
      date_from?: string
      date_to?: string
    }
  ): Promise<PaginatedResponse<Record<string, unknown>>> =>
    api.get('/api/v1/esg/carbon-records/', { params }).then(getData),

  createCarbonRecord: (
    data: Record<string, unknown>
  ): Promise<Record<string, unknown>> =>
    api.post('/api/v1/esg/carbon-records/', data).then(getData),

  getDiversionRates: (
    params?: ESGDashboardParams & { client_id?: string }
  ): Promise<Record<string, unknown>[]> =>
    api.get('/api/v1/esg/diversion-rates/', { params }).then(getData),

  generateReport: (config: Record<string, unknown>): Promise<Record<string, unknown>> =>
    api.post('/api/v1/esg/reports/generate/', config).then(getData),

  getReportJob: (jobId: string): Promise<Record<string, unknown>> =>
    api.get(`/api/v1/esg/reports/${jobId}/`).then(getData),

  getSdgAlignment: (
    clientId?: string,
    params?: ESGDashboardParams
  ): Promise<Record<string, unknown>[]> =>
    api
      .get('/api/v1/esg/sdg-alignment/', {
        params: { client_id: clientId, ...params },
      })
      .then(getData),

  downloadReport: (jobId: string): Promise<Blob> =>
    api
      .get(`/api/v1/esg/reports/${jobId}/download/`, {
        responseType: 'blob',
      })
      .then(getData),
}

// ---------------------------------------------------------------------------
// Recyclables API
// ---------------------------------------------------------------------------

export const recyclablesApi = {
  listMaterials: (
    params?: PaginatedParams
  ): Promise<PaginatedResponse<Record<string, unknown>>> =>
    api.get('/api/v1/recyclables/records', { params }).then(getData),

  getRecoveryStats: (params?: {
    period_start?: string
    period_end?: string
    client_id?: string
  }): Promise<Record<string, unknown>> =>
    api.get('/api/v1/recyclables/stats', { params }).then(getData),

  listChainOfCustody: (
    params?: PaginatedParams
  ): Promise<PaginatedResponse<Record<string, unknown>>> =>
    api.get('/api/v1/recyclables/chain-of-custody', { params }).then(getData),

  getMaterialPrices: (): Promise<Record<string, unknown>[]> =>
    api.get('/api/v1/recyclables/material-prices').then(getData),

  updateMaterialPrice: (
    code: string,
    data: Record<string, unknown>
  ): Promise<Record<string, unknown>> =>
    api.patch(`/api/v1/recyclables/material-prices/${code}`, data).then(getData),

  generateCertificatePDF: (id: string): Promise<Blob> =>
    api
      .get(`/api/v1/recyclables/chain-of-custody/${id}/pdf`, {
        responseType: 'blob',
      })
      .then(getData),
}

// ---------------------------------------------------------------------------
// Destruction API
// ---------------------------------------------------------------------------

export const destructionApi = {
  listJobs: (
    params?: PaginatedParams & { status?: string }
  ): Promise<PaginatedResponse<Record<string, unknown>>> =>
    api.get('/api/v1/destruction/jobs', { params }).then(getData),

  getJob: (id: string): Promise<Record<string, unknown>> =>
    api.get(`/api/v1/destruction/jobs/${id}`).then(getData),

  createJob: (data: Record<string, unknown>): Promise<Record<string, unknown>> =>
    api.post('/api/v1/destruction/jobs', data).then(getData),

  updateJob: (
    id: string,
    data: Partial<Record<string, unknown>>
  ): Promise<Record<string, unknown>> =>
    api.patch(`/api/v1/destruction/jobs/${id}`, data).then(getData),

  listCertificates: (
    params?: PaginatedParams
  ): Promise<PaginatedResponse<Record<string, unknown>>> =>
    api.get('/api/v1/destruction/certificates', { params }).then(getData),

  getCertificate: (id: string): Promise<Record<string, unknown>> =>
    api.get(`/api/v1/destruction/certificates/${id}`).then(getData),

  generateCertificatePDF: (id: string): Promise<Blob> =>
    api
      .get(`/api/v1/destruction/certificates/${id}/pdf`, {
        responseType: 'blob',
      })
      .then(getData),
}

// ---------------------------------------------------------------------------
// BSF Farm API
// ---------------------------------------------------------------------------

export const bsfApi = {
  listBatches: (
    params?: PaginatedParams & { status?: string }
  ): Promise<PaginatedResponse<Record<string, unknown>>> =>
    api.get('/api/v1/bsf/batches/', { params }).then(getData),

  getBatch: (id: string): Promise<Record<string, unknown>> =>
    api.get(`/api/v1/bsf/batches/${id}/`).then(getData),

  createBatch: (data: Record<string, unknown>): Promise<Record<string, unknown>> =>
    api.post('/api/v1/bsf/batches/', data).then(getData),

  updateBatch: (
    id: string,
    data: Partial<Record<string, unknown>>
  ): Promise<Record<string, unknown>> =>
    api.patch(`/api/v1/bsf/batches/${id}/`, data).then(getData),

  listIntakeLogs: (
    params?: PaginatedParams
  ): Promise<PaginatedResponse<Record<string, unknown>>> =>
    api.get('/api/v1/bsf/intake-logs/', { params }).then(getData),

  createIntakeLog: (
    data: Record<string, unknown>
  ): Promise<Record<string, unknown>> =>
    api.post('/api/v1/bsf/intake-logs/', data).then(getData),

  getFarmStats: (): Promise<Record<string, unknown>> =>
    api.get('/api/v1/bsf/stats/').then(getData),
}

// ---------------------------------------------------------------------------
// Finance API
// ---------------------------------------------------------------------------

export const financeApi = {
  listInvoices: (
    params?: PaginatedParams & {
      status?: string
      client_id?: string
      date_from?: string
      date_to?: string
    }
  ): Promise<PaginatedResponse<Record<string, unknown>>> =>
    api.get('/api/v1/finance/invoices/', { params }).then(getData),

  getInvoice: (id: string): Promise<Record<string, unknown>> =>
    api.get(`/api/v1/finance/invoices/${id}/`).then(getData),

  createInvoice: (data: Record<string, unknown>): Promise<Record<string, unknown>> =>
    api.post('/api/v1/finance/invoices/', data).then(getData),

  updateInvoice: (
    id: string,
    data: Partial<Record<string, unknown>>
  ): Promise<Record<string, unknown>> =>
    api.patch(`/api/v1/finance/invoices/${id}/`, data).then(getData),

  getRevenueStats: (params?: {
    period_start?: string
    period_end?: string
    granularity?: string
  }): Promise<Record<string, unknown>> =>
    api.get('/api/v1/finance/stats/revenue/', { params }).then(getData),

  getReceivablesAgeing: (): Promise<Record<string, unknown>> =>
    api.get('/api/v1/finance/stats/receivables-ageing/').then(getData),

  sendInvoiceEmail: (id: string): Promise<void> =>
    api.post(`/api/v1/finance/invoices/${id}/send/`).then(() => undefined),

  generateInvoicePDF: (id: string): Promise<Blob> =>
    api
      .get(`/api/v1/finance/invoices/${id}/pdf/`, { responseType: 'blob' })
      .then(getData),
}

// ---------------------------------------------------------------------------
// Reports API
// ---------------------------------------------------------------------------

export const reportsApi = {
  listReportTypes: (): Promise<Record<string, unknown>[]> =>
    api.get('/api/v1/reports/types/').then(getData),

  generateReport: (config: Record<string, unknown>): Promise<Record<string, unknown>> =>
    api.post('/api/v1/reports/generate/', config).then(getData),

  getReportJob: (jobId: string): Promise<Record<string, unknown>> =>
    api.get(`/api/v1/reports/${jobId}/`).then(getData),

  listReports: (
    params?: PaginatedParams
  ): Promise<PaginatedResponse<Record<string, unknown>>> =>
    api.get('/api/v1/reports/', { params }).then(getData),

  downloadReport: (jobId: string): Promise<Blob> =>
    api
      .get(`/api/v1/reports/${jobId}/download/`, { responseType: 'blob' })
      .then(getData),
}

// ---------------------------------------------------------------------------
// Settings API
// ---------------------------------------------------------------------------

export const settingsApi = {
  listUsers: (
    params?: PaginatedParams & { role?: string; is_active?: boolean }
  ): Promise<PaginatedResponse<Record<string, unknown>>> =>
    api.get('/api/v1/settings/users/', { params }).then(getData),

  createUser: (data: Record<string, unknown>): Promise<Record<string, unknown>> =>
    api.post('/api/v1/settings/users/', data).then(getData),

  updateUser: (
    id: string,
    data: Partial<Record<string, unknown>>
  ): Promise<Record<string, unknown>> =>
    api.patch(`/api/v1/settings/users/${id}/`, data).then(getData),

  deactivateUser: (id: string): Promise<void> =>
    api.post(`/api/v1/settings/users/${id}/deactivate/`).then(() => undefined),

  getSystemConfig: (): Promise<Record<string, unknown>> =>
    api.get('/api/v1/settings/config/').then(getData),

  updateSystemConfig: (
    data: Record<string, unknown>
  ): Promise<Record<string, unknown>> =>
    api.patch('/api/v1/settings/config/', data).then(getData),

  sendTestEmail: (to: string): Promise<{ success: boolean; message: string }> =>
    api.post('/api/v1/settings/test-email', { to }).then(getData),
}

// ---------------------------------------------------------------------------
// AI Agent API
// ---------------------------------------------------------------------------

export interface AgentEventParams extends PaginatedParams {
  severity?: string
  is_read?: boolean
  event_type?: string
  date_from?: string
  date_to?: string
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
}

export const agentApi = {
  getEvents: (
    params?: AgentEventParams
  ): Promise<PaginatedResponse<Record<string, unknown>>> =>
    api.get('/api/v1/agent/events/', { params }).then(getData),

  getEvent: (id: string): Promise<Record<string, unknown>> =>
    api.get(`/api/v1/agent/events/${id}/`).then(getData),

  markRead: (id: string): Promise<void> =>
    api.post(`/api/v1/agent/events/${id}/read/`).then(() => undefined),

  markAllRead: (): Promise<void> =>
    api.post('/api/v1/agent/events/read-all/').then(() => undefined),

  chat: (
    message: string,
    history: ChatMessage[]
  ): Promise<Record<string, unknown>> =>
    api
      .post('/api/v1/agent/chat/', { message, history })
      .then(getData),

  /**
   * Returns a URL that streams SSE tokens for a given message.
   * The caller is responsible for opening an EventSource.
   */
  getChatStreamUrl: (message: string, history: ChatMessage[]): string => {
    const base = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
    const params = new URLSearchParams({
      message,
      history: JSON.stringify(history),
    })
    return `${base}/api/v1/agent/chat/stream/?${params.toString()}`
  },

  getAgentStatuses: (): Promise<Record<string, unknown>[]> =>
    api.get('/api/v1/agent/statuses/').then(getData),

  getUnreadCount: (): Promise<{ count: number }> =>
    api.get('/api/v1/agent/events/unread-count/').then(getData),
}

// ---------------------------------------------------------------------------
// Equipment API — Compaction Machines & Containers
// ---------------------------------------------------------------------------

import type {
  CompactionMachine,
  CompactorDeployment,
  CompactorMaintenanceLog,
  Container,
  FillReading,
  PickupTrigger,
  TransportLogEntry,
  StaffProfile,
  SiteAssignment,
  Shift,
  ShiftAttendance,
  DisruptionLog,
  RecyclerDelivery,
  ReconciliationDetails,
  OperationalFieldSummary,
} from '@/types/operational-field'

export const equipmentApi = {
  // Compactors
  listCompactors: (status?: string): Promise<CompactionMachine[]> =>
    api.get('/api/v1/equipment/compactors', { params: status ? { status } : undefined }).then(getData),

  getCompactor: (id: string): Promise<CompactionMachine> =>
    api.get(`/api/v1/equipment/compactors/${id}`).then(getData),

  createCompactor: (data: Record<string, unknown>): Promise<CompactionMachine> =>
    api.post('/api/v1/equipment/compactors', data).then(getData),

  updateCompactor: (id: string, data: Record<string, unknown>): Promise<CompactionMachine> =>
    api.patch(`/api/v1/equipment/compactors/${id}`, data).then(getData),

  getDueService: (): Promise<CompactionMachine[]> =>
    api.get('/api/v1/equipment/compactors/due-service').then(getData),

  listDeployments: (machineId: string): Promise<CompactorDeployment[]> =>
    api.get(`/api/v1/equipment/compactors/${machineId}/deployments`).then(getData),

  deployCompactor: (machineId: string, data: Record<string, unknown>): Promise<CompactorDeployment> =>
    api.post(`/api/v1/equipment/compactors/${machineId}/deployments`, data).then(getData),

  retrieveCompactor: (machineId: string, deploymentId: string): Promise<CompactorDeployment> =>
    api.post(`/api/v1/equipment/compactors/${machineId}/deployments/${deploymentId}/retrieve`).then(getData),

  listMaintenance: (machineId: string): Promise<CompactorMaintenanceLog[]> =>
    api.get(`/api/v1/equipment/compactors/${machineId}/maintenance`).then(getData),

  logMaintenance: (machineId: string, data: Record<string, unknown>): Promise<CompactorMaintenanceLog> =>
    api.post(`/api/v1/equipment/compactors/${machineId}/maintenance`, data).then(getData),

  // Containers
  listContainers: (params?: { status?: string; client_id?: string }): Promise<Container[]> =>
    api.get('/api/v1/equipment/containers', { params }).then(getData),

  getContainer: (id: string): Promise<Container> =>
    api.get(`/api/v1/equipment/containers/${id}`).then(getData),

  createContainer: (data: Record<string, unknown>): Promise<Container> =>
    api.post('/api/v1/equipment/containers', data).then(getData),

  assignToSite: (id: string, data: Record<string, unknown>): Promise<Container> =>
    api.post(`/api/v1/equipment/containers/${id}/assign-site`, data).then(getData),

  updateFillLevel: (id: string, data: { fill_level: number; photo_url?: string; notes?: string }): Promise<FillReading> =>
    api.post(`/api/v1/equipment/containers/${id}/fill-level`, data).then(getData),

  getFillHistory: (id: string): Promise<FillReading[]> =>
    api.get(`/api/v1/equipment/containers/${id}/fill-history`).then(getData),

  getTransportLog: (id: string): Promise<TransportLogEntry[]> =>
    api.get(`/api/v1/equipment/containers/${id}/transport-log`).then(getData),

  updateTransportStatus: (id: string, data: Record<string, unknown>): Promise<Container> =>
    api.post(`/api/v1/equipment/containers/${id}/transport`, data).then(getData),

  acknowledgeTrigger: (containerId: string, triggerId: string): Promise<PickupTrigger> =>
    api.post(`/api/v1/equipment/containers/${containerId}/pickup-triggers/${triggerId}/acknowledge`).then(getData),
}

// ---------------------------------------------------------------------------
// Labour API — Staff, Site Assignments, Shifts, Attendance
// ---------------------------------------------------------------------------

export const labourApi = {
  listStaff: (params?: { assignment_status?: string; employment_type?: string }): Promise<StaffProfile[]> =>
    api.get('/api/v1/labour/staff', { params }).then(getData),

  getStaff: (id: string): Promise<StaffProfile> =>
    api.get(`/api/v1/labour/staff/${id}`).then(getData),

  createStaff: (data: Record<string, unknown>): Promise<StaffProfile> =>
    api.post('/api/v1/labour/staff', data).then(getData),

  updateStaff: (id: string, data: Record<string, unknown>): Promise<StaffProfile> =>
    api.patch(`/api/v1/labour/staff/${id}`, data).then(getData),

  getHoursSummary: (id: string, weekStart?: string): Promise<Record<string, unknown>> =>
    api.get(`/api/v1/labour/staff/${id}/hours-summary`, { params: weekStart ? { week_start: weekStart } : undefined }).then(getData),

  listSiteAssignments: (clientId: string, activeOnly?: boolean): Promise<SiteAssignment[]> =>
    api.get(`/api/v1/labour/sites/${clientId}/assignments`, { params: activeOnly ? { active_only: true } : undefined }).then(getData),

  createSiteAssignment: (data: Record<string, unknown>): Promise<SiteAssignment> =>
    api.post('/api/v1/labour/sites/assignments', data).then(getData),

  closeSiteAssignment: (id: string): Promise<SiteAssignment> =>
    api.post(`/api/v1/labour/sites/assignments/${id}/close`).then(getData),

  listShifts: (params?: { site_id?: string; date_from?: string; date_to?: string }): Promise<Shift[]> =>
    api.get('/api/v1/labour/shifts', { params }).then(getData),

  createShift: (data: Record<string, unknown>): Promise<Shift> =>
    api.post('/api/v1/labour/shifts', data).then(getData),

  checkIn: (shiftId: string, staffProfileId: string): Promise<ShiftAttendance> =>
    api.post(`/api/v1/labour/shifts/${shiftId}/check-in`, { staff_profile_id: staffProfileId }).then(getData),

  checkOut: (shiftId: string, staffProfileId: string): Promise<ShiftAttendance> =>
    api.post(`/api/v1/labour/shifts/${shiftId}/check-out`, { staff_profile_id: staffProfileId }).then(getData),

  markAbsent: (shiftId: string, data: Record<string, unknown>): Promise<ShiftAttendance> =>
    api.post(`/api/v1/labour/shifts/${shiftId}/mark-absent`, data).then(getData),

  getAttendance: (params?: { staff_id?: string; date_from?: string; date_to?: string }): Promise<ShiftAttendance[]> =>
    api.get('/api/v1/labour/attendance', { params }).then(getData),
}

// ---------------------------------------------------------------------------
// Disruptions API
// ---------------------------------------------------------------------------

export const disruptionsApi = {
  list: (params?: { status?: string; disruption_type?: string; date_from?: string; date_to?: string }): Promise<DisruptionLog[]> =>
    api.get('/api/v1/disruptions/', { params }).then(getData),

  get: (id: string): Promise<DisruptionLog> =>
    api.get(`/api/v1/disruptions/${id}`).then(getData),

  create: (data: Record<string, unknown>): Promise<DisruptionLog> =>
    api.post('/api/v1/disruptions/', data).then(getData),

  update: (id: string, data: Record<string, unknown>): Promise<DisruptionLog> =>
    api.patch(`/api/v1/disruptions/${id}`, data).then(getData),

  addResolutionUpdate: (id: string, updateText: string): Promise<DisruptionLog> =>
    api.post(`/api/v1/disruptions/${id}/resolution-update`, { update_text: updateText }).then(getData),

  close: (id: string, data: { closure_note: string; vehicle_status_updated?: boolean }): Promise<DisruptionLog> =>
    api.post(`/api/v1/disruptions/${id}/close`, data).then(getData),

  getImpact: (id: string): Promise<Record<string, unknown>[]> =>
    api.get(`/api/v1/disruptions/${id}/impact`).then(getData),

  getJobDisruptions: (jobId: string): Promise<DisruptionLog[]> =>
    api.get(`/api/v1/operational-field/jobs/${jobId}/disruptions`).then(getData),
}

// ---------------------------------------------------------------------------
// Recycler Deliveries API
// ---------------------------------------------------------------------------

export const recyclerDeliveriesApi = {
  list: (params?: { status?: string; buyer_id?: string; date_from?: string; date_to?: string }): Promise<RecyclerDelivery[]> =>
    api.get('/api/v1/recycler-deliveries/', { params }).then(getData),

  get: (id: string): Promise<RecyclerDelivery> =>
    api.get(`/api/v1/recycler-deliveries/${id}`).then(getData),

  create: (data: Record<string, unknown>): Promise<RecyclerDelivery> =>
    api.post('/api/v1/recycler-deliveries/', data).then(getData),

  depart: (id: string): Promise<RecyclerDelivery> =>
    api.post(`/api/v1/recycler-deliveries/${id}/depart`).then(getData),

  arrive: (id: string): Promise<RecyclerDelivery> =>
    api.post(`/api/v1/recycler-deliveries/${id}/arrive`).then(getData),

  submitProof: (id: string, data: { proof_photos: string[]; weight_ticket_ref: string; recycler_recorded_weight_kg: number }): Promise<RecyclerDelivery> =>
    api.post(`/api/v1/recycler-deliveries/${id}/proof`, data).then(getData),

  getReconciliation: (id: string): Promise<ReconciliationDetails> =>
    api.get(`/api/v1/recycler-deliveries/${id}/reconciliation`).then(getData),

  reviewReconciliation: (id: string, data: { action: 'accept' | 'reject'; justification?: string }): Promise<RecyclerDelivery> =>
    api.post(`/api/v1/recycler-deliveries/${id}/reconciliation-review`, data).then(getData),

  submitBuyerConfirmation: (id: string, data: Record<string, unknown>): Promise<RecyclerDelivery> =>
    api.post(`/api/v1/recycler-deliveries/${id}/buyer-confirmation`, data).then(getData),
}

// ---------------------------------------------------------------------------
// Operational Field Summary API
// ---------------------------------------------------------------------------

export const operationalFieldApi = {
  getSummary: (): Promise<OperationalFieldSummary> =>
    api.get('/api/v1/operational-field/summary').then(getData),
}

// ---------------------------------------------------------------------------
// AI Knowledge Base API
// ---------------------------------------------------------------------------

export interface ListDocumentsParams {
  skip?: number
  limit?: number
  doc_type?: string
  client_id?: string
  ingested_only?: boolean
}

export const aiApi = {
  listDocuments: (params?: ListDocumentsParams): Promise<Record<string, unknown>> =>
    api.get('/api/v1/ai/documents', { params }).then(getData),

  uploadDocument: (formData: FormData): Promise<Record<string, unknown>> =>
    api
      .post('/api/v1/ai/ingest-document', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then(getData),

  deleteDocument: (id: string): Promise<void> =>
    api.delete(`/api/v1/ai/documents/${id}`).then(() => undefined),

  reIngestDocument: (id: string): Promise<Record<string, unknown>> =>
    api.post(`/api/v1/ai/documents/${id}/re-ingest`).then(getData),

  getRagStatus: (): Promise<Record<string, unknown>> =>
    api.get('/api/v1/ai/rag-status').then(getData),
}
