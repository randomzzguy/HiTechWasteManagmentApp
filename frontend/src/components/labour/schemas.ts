import { z } from 'zod'
import axios from 'axios'

// ---------------------------------------------------------------------------
// Add Staff Schema
// ---------------------------------------------------------------------------

export const addStaffSchema = z.object({
  user_id: z.string().uuid({ message: 'Please select a user' }),
  employment_type: z.enum(['permanent', 'contract', 'foreign_worker'], {
    required_error: 'Please select an employment type',
  }),
  labour_agent_name: z
    .string()
    .max(200, 'Labour agent name must be 200 characters or fewer')
    .optional()
    .or(z.literal('')),
  work_permit_expiry: z.string().optional(),
  notes: z.string().optional(),
})

export type AddStaffFormValues = z.infer<typeof addStaffSchema>

// ---------------------------------------------------------------------------
// Site Assignment Schema
// ---------------------------------------------------------------------------

const memberSchema = z.object({
  staff_profile_id: z.string().uuid(),
  role_at_site: z.enum([
    'field_supervisor',
    'waste_segregator',
    'driver_assistant',
    'general_worker',
  ]),
})

export const siteAssignmentSchema = z
  .object({
    client_id: z.string().uuid({ message: 'Please select a client' }),
    site_address: z.string().min(1, 'Site address is required'),
    supervisor_id: z.string().uuid({ message: 'Please select a supervisor' }),
    start_date: z.string().min(1, 'Start date is required'),
    end_date: z.string().optional(),
    members: z.array(memberSchema).min(1, 'At least one team member is required'),
    notes: z.string().optional(),
  })
  .refine(
    (data) => {
      if (!data.end_date || data.end_date === '') return true
      return data.end_date >= data.start_date
    },
    { message: 'End date must be on or after start date', path: ['end_date'] }
  )
  .refine(
    (data) => data.members.some((m) => m.role_at_site === 'field_supervisor'),
    {
      message: 'At least one team member must have the role Field Supervisor',
      path: ['members'],
    }
  )

export type SiteAssignmentFormValues = z.infer<typeof siteAssignmentSchema>

// ---------------------------------------------------------------------------
// Payload builders
// ---------------------------------------------------------------------------

export function buildAddStaffPayload(values: AddStaffFormValues): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    user_id: values.user_id,
    employment_type: values.employment_type,
  }

  if (values.labour_agent_name && values.labour_agent_name !== '') {
    payload.labour_agent_name = values.labour_agent_name
  }

  if (values.employment_type === 'foreign_worker' && values.work_permit_expiry) {
    payload.work_permit_expiry = values.work_permit_expiry
  }

  if (values.notes && values.notes !== '') {
    payload.notes = values.notes
  }

  return payload
}

export function buildSiteAssignmentPayload(values: SiteAssignmentFormValues): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    client_id: values.client_id,
    site_address: values.site_address,
    supervisor_id: values.supervisor_id,
    start_date: values.start_date,
    members: values.members,
  }

  if (values.end_date && values.end_date !== '') {
    payload.end_date = values.end_date
  }

  if (values.notes && values.notes !== '') {
    payload.notes = values.notes
  }

  return payload
}

// ---------------------------------------------------------------------------
// Shared error extraction helper
// ---------------------------------------------------------------------------

export function extractErrorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map((d: { msg: string }) => d.msg).join(', ')
    return err.response?.data?.message ?? fallback
  }
  return fallback
}
