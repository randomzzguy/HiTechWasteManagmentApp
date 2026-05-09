import { z } from 'zod'
import axios from 'axios'

// ---------------------------------------------------------------------------
// New Intake Schema
// ---------------------------------------------------------------------------

export const newIntakeSchema = z.object({
  intake_date: z.string().min(1, 'Intake date is required'),
  food_waste_kg: z.number({ invalid_type_error: 'Must be a number' }).positive('Must be greater than 0'),
  contamination_level: z.enum(['clean', 'minor', 'rejected'], {
    required_error: 'Contamination level is required',
  }),
  batch_start: z.string().optional(),
  livestock_recipient: z.string().max(255).optional(),
}).superRefine((data, ctx) => {
  if (data.batch_start && data.batch_start < data.intake_date) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['batch_start'],
      message: 'Batch start cannot be earlier than intake date',
    })
  }
})

export type NewIntakeFormValues = z.infer<typeof newIntakeSchema>

// ---------------------------------------------------------------------------
// Harvest Schema
// ---------------------------------------------------------------------------

export const harvestSchema = z.object({
  larvae_output_kg: z.number({ invalid_type_error: 'Must be a number' }).min(0, 'Cannot be negative'),
  batch_end: z.string().min(1, 'Batch end date is required'),
  status: z.enum(['completed', 'rejected'], { required_error: 'Status is required' }),
  contamination_level: z.enum(['clean', 'minor', 'rejected']).optional(),
  livestock_recipient: z.string().max(255).optional(),
  intake_date: z.string(), // context only, not submitted
}).superRefine((data, ctx) => {
  if (data.batch_end && data.intake_date && data.batch_end < data.intake_date) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['batch_end'],
      message: 'Batch end cannot be earlier than intake date',
    })
  }
})

export type HarvestFormValues = z.infer<typeof harvestSchema>

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

// ---------------------------------------------------------------------------
// Conversion ratio preview
// ---------------------------------------------------------------------------

export function computeConversionPreview(larvaeKg: number, foodWasteKg: number): string {
  if (larvaeKg > 0 && foodWasteKg > 0) {
    return ((larvaeKg / foodWasteKg) * 100).toFixed(1) + '%'
  }
  return '—'
}
