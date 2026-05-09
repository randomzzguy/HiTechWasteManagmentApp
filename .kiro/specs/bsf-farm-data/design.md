# Design Document — BSF Farm Data Entry

## Overview

This feature activates the two missing data-entry workflows on the `/bsf-farm` page:

1. **New Intake** — the existing "New Intake" button opens a Dialog form that calls `bsfApi.createBatch` to create a new BSF batch record.
2. **Record Harvest** — active batch rows gain a "Record Harvest" hover action that opens a Dialog form calling `bsfApi.updateBatch` to record larvae output and close out the batch.

Both `bsfApi.createBatch` and `bsfApi.updateBatch` already exist in `src/lib/api.ts` — no API client changes are required. The backend endpoints (`POST /api/v1/bsf/batches/` and `PATCH /api/v1/bsf/batches/{id}/`) are already live. The implementation is purely frontend: two new dialog components, their Zod schemas, and wiring in the BSF Farm page.

---

## Architecture

```
BSF Farm Page (page.tsx)
│
├── open state: intakeOpen (boolean)
├── open state: harvestOpen (boolean)
├── selected state: selectedBatch (BsfBatch | null)
│
├── <NewIntakeDialog
│     open={intakeOpen}
│     onOpenChange={setIntakeOpen}
│     onSuccess={handleSuccess}
│   />
│
└── <RecordHarvestDialog
      open={harvestOpen}
      onOpenChange={setHarvestOpen}
      batch={selectedBatch}
      onSuccess={handleSuccess}
    />
```

Both dialogs are **controlled** — the page owns the `open` boolean and passes `onOpenChange` so shadcn's Dialog can close itself on Escape / outside-click. `selectedBatch` is set when the user clicks "Record Harvest" on a row and cleared when the harvest dialog closes.

Data flow for each dialog:

```
User fills form
  → RHF validates via zodResolver(schema)
  → useMutation calls bsfApi method
  → onSuccess: close dialog + queryClient.invalidateQueries + toast.success
  → onError:   extractErrorMessage(err) → setApiError state → toast.error (stay open)
```

---

## Components and Interfaces

### NewIntakeDialog

```typescript
// frontend/src/components/bsf/NewIntakeDialog.tsx
interface NewIntakeDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}
```

Internal state:
- React Hook Form instance bound to `NewIntakeFormValues` (via `zodResolver(newIntakeSchema)`)
- `useMutation` wrapping `bsfApi.createBatch`
- `apiError: string | null` for displaying server-side errors inline
- Form is reset via `form.reset()` inside the `onOpenChange` handler when closing

### RecordHarvestDialog

```typescript
// frontend/src/components/bsf/RecordHarvestDialog.tsx
interface RecordHarvestDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  batch: BsfBatch | null   // pre-populates food_waste_kg for ratio preview
  onSuccess: () => void
}
```

Internal state:
- React Hook Form instance bound to `HarvestFormValues` (via `zodResolver(harvestSchema)`)
- `useMutation` wrapping `bsfApi.updateBatch`
- `larvaeOutputKg = watch('larvae_output_kg')` — drives the live conversion ratio preview
- `apiError: string | null` for server-side errors
- Form is reset when `open` transitions to `false`

### BSF Farm Page wiring

```typescript
// Additions to frontend/src/app/(dashboard)/bsf-farm/page.tsx
const [intakeOpen, setIntakeOpen] = useState(false)
const [harvestOpen, setHarvestOpen] = useState(false)
const [selectedBatch, setSelectedBatch] = useState<BsfBatch | null>(null)
const queryClient = useQueryClient()

function handleSuccess() {
  queryClient.invalidateQueries({ queryKey: ['bsf', 'batches'] })
  queryClient.invalidateQueries({ queryKey: ['bsf', 'stats'] })
  toast.success('Saved successfully')
}

function openHarvest(batch: BsfBatch) {
  setSelectedBatch(batch)
  setHarvestOpen(true)
}
```

The "New Intake" button's `onClick` sets `setIntakeOpen(true)`. Each active batch row renders a "Record Harvest" button (visible on hover) whose `onClick` calls `openHarvest(batch)`.

---

## Data Models

### Zod Schemas

```typescript
// frontend/src/components/bsf/schemas.ts

import { z } from 'zod'

export const newIntakeSchema = z
  .object({
    intake_date: z.string().min(1, 'Intake date is required'),
    food_waste_kg: z
      .number({ invalid_type_error: 'Must be a number' })
      .positive('Must be greater than 0'),
    contamination_level: z.enum(['clean', 'minor', 'rejected'], {
      required_error: 'Contamination level is required',
    }),
    batch_start: z.string().optional(),
    livestock_recipient: z.string().max(255).optional(),
  })
  .superRefine((data, ctx) => {
    if (data.batch_start && data.batch_start < data.intake_date) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['batch_start'],
        message: 'Batch start cannot be earlier than intake date',
      })
    }
  })

export type NewIntakeFormValues = z.infer<typeof newIntakeSchema>

export const harvestSchema = z
  .object({
    larvae_output_kg: z
      .number({ invalid_type_error: 'Must be a number' })
      .min(0, 'Cannot be negative'),
    batch_end: z.string().min(1, 'Batch end date is required'),
    status: z.enum(['completed', 'rejected'], {
      required_error: 'Status is required',
    }),
    contamination_level: z.enum(['clean', 'minor', 'rejected']).optional(),
    livestock_recipient: z.string().max(255).optional(),
    // intake_date is passed as context for cross-field validation, not submitted
    intake_date: z.string(),
  })
  .superRefine((data, ctx) => {
    if (data.batch_end && data.batch_end < data.intake_date) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['batch_end'],
        message: 'Batch end cannot be earlier than intake date',
      })
    }
  })

export type HarvestFormValues = z.infer<typeof harvestSchema>
```

`intake_date` is injected into the harvest form's default values from `batch.intake_date` and is used only for cross-field validation — it is stripped from the PATCH payload before submission.

### API Payload Types

The existing `bsfApi` methods accept `Record<string, unknown>`, which is sufficient. No changes to `api.ts` are needed. The payload shapes are:

**createBatch payload** (from `NewIntakeFormValues`, omitting undefined optionals):
```typescript
{
  intake_date: string        // ISO date "YYYY-MM-DD"
  food_waste_kg: number
  contamination_level: 'clean' | 'minor' | 'rejected'
  batch_start?: string       // ISO date, optional
  livestock_recipient?: string
}
```

**updateBatch payload** (from `HarvestFormValues`, omitting `intake_date`):
```typescript
{
  larvae_output_kg: number
  batch_end: string          // ISO date "YYYY-MM-DD"
  status: 'completed' | 'rejected'
  contamination_level?: 'clean' | 'minor' | 'rejected'
  livestock_recipient?: string
}
```

### Conversion Ratio Preview

The preview is a pure derived value computed in the render function — no state needed:

```typescript
const larvaeOutputKg = watch('larvae_output_kg')

const conversionPreview =
  larvaeOutputKg != null &&
  larvaeOutputKg > 0 &&
  batch?.food_waste_kg != null &&
  batch.food_waste_kg > 0
    ? `${((larvaeOutputKg / batch.food_waste_kg) * 100).toFixed(1)}%`
    : '—'
```

This updates on every keystroke because `watch()` triggers a re-render whenever the field value changes.

### Error Handling

The `extractErrorMessage` helper (already defined in `src/components/labour/schemas.ts`) is re-exported from `src/components/bsf/schemas.ts` or imported directly:

```typescript
export function extractErrorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map((d: { msg: string }) => d.msg).join(', ')
    return err.response?.data?.message ?? fallback
  }
  return fallback
}
```

In each dialog's `onError` mutation handler:
```typescript
onError: (err) => {
  const message = extractErrorMessage(err, 'An unexpected error occurred')
  setApiError(message)
}
```

The `apiError` string is rendered as a `<p className="text-sm text-red-400">` below the form fields, above the action buttons.

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Positive food waste is required for intake

*For any* value of `food_waste_kg` that is zero, negative, or absent, the `newIntakeSchema` Zod validator SHALL return a validation error on the `food_waste_kg` field and SHALL NOT produce a valid parse result.

**Validates: Requirements 2.2**

---

### Property 2: Batch start cannot precede intake date

*For any* pair of ISO date strings `(intake_date, batch_start)` where `batch_start < intake_date`, the `newIntakeSchema` cross-field validator SHALL return a validation error on the `batch_start` field.

**Validates: Requirements 2.4**

---

### Property 3: Conversion ratio preview is always consistent with inputs

*For any* `larvae_output_kg >= 0` and `food_waste_kg > 0`, the conversion ratio preview value SHALL equal `(larvae_output_kg / food_waste_kg) * 100` rounded to one decimal place, formatted as a percentage string (e.g. `"25.3%"`).

**Validates: Requirements 5.1, 5.3**

---

### Property 4: Non-negative larvae output is required for harvest

*For any* value of `larvae_output_kg` that is negative or absent, the `harvestSchema` Zod validator SHALL return a validation error on the `larvae_output_kg` field and SHALL NOT produce a valid parse result.

**Validates: Requirements 6.1**

---

### Property 5: Batch end cannot precede intake date

*For any* pair of ISO date strings `(intake_date, batch_end)` where `batch_end < intake_date`, the `harvestSchema` cross-field validator SHALL return a validation error on the `batch_end` field.

**Validates: Requirements 6.4**

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| `createBatch` / `updateBatch` returns 4xx/5xx | Dialog stays open; `apiError` state set; error rendered inline; submit button re-enabled |
| 401 Unauthorized | Axios interceptor redirects to `/login` before the mutation `onError` fires |
| Network timeout | Axios rejects with `AxiosError`; `extractErrorMessage` returns fallback string |
| Zod validation failure | RHF prevents submission; inline field errors rendered via `<FormMessage>` |
| `batch_start` before `intake_date` | Zod `superRefine` adds issue; RHF renders error on `batch_start` field |
| `batch_end` before `intake_date` | Zod `superRefine` adds issue; RHF renders error on `batch_end` field |

---

## Testing Strategy

### Unit / Example-Based Tests

Focus on concrete scenarios that property tests don't cover:

- Dialog opens when trigger button is clicked
- Dialog closes and resets form on Cancel
- Required fields show inline errors on empty submission
- `contamination_level` unselected shows validation error
- `status` unselected shows validation error
- Submit button is disabled and shows spinner during pending mutation
- Success path: dialog closes, toast shown, cache invalidated
- Error path: dialog stays open, API error message rendered, button re-enabled
- "Record Harvest" button appears on hover for active rows only
- Harvest dialog pre-populates `food_waste_kg` from selected batch
- Conversion ratio shows "—" when `larvae_output_kg` is empty or zero
- `contamination_level` colour coding matches Batch_Table classes

### Property-Based Tests

Use a PBT library (e.g. **fast-check** for TypeScript) with a minimum of **100 iterations** per property. Each test targets the pure Zod schema logic — no DOM or network required.

**Property 1 — Positive food waste required**
```
Tag: Feature: bsf-farm-data, Property 1: positive food waste required for intake
Generator: fc.oneof(fc.constant(0), fc.float({ max: -0.001 }), fc.constant(null), fc.constant(undefined))
Assert: newIntakeSchema.safeParse({ ...validBase, food_waste_kg: value }).success === false
```

**Property 2 — Batch start cannot precede intake date**
```
Tag: Feature: bsf-farm-data, Property 2: batch start cannot precede intake date
Generator: fc.tuple(fc.date(), fc.date()).filter(([a, b]) => b < a).map(([intake, start]) => [toISO(intake), toISO(start)])
Assert: newIntakeSchema.safeParse({ ...validBase, intake_date, batch_start }).success === false
        AND error path includes 'batch_start'
```

**Property 3 — Conversion ratio preview consistency**
```
Tag: Feature: bsf-farm-data, Property 3: conversion ratio preview consistent with inputs
Generator: fc.tuple(fc.float({ min: 0.001, max: 10000 }), fc.float({ min: 0.001, max: 10000 }))
Assert: computeConversionPreview(larvaeKg, foodWasteKg) === ((larvaeKg / foodWasteKg) * 100).toFixed(1) + '%'
```

**Property 4 — Non-negative larvae output required**
```
Tag: Feature: bsf-farm-data, Property 4: non-negative larvae output required for harvest
Generator: fc.oneof(fc.float({ max: -0.001 }), fc.constant(null), fc.constant(undefined))
Assert: harvestSchema.safeParse({ ...validHarvestBase, larvae_output_kg: value }).success === false
```

**Property 5 — Batch end cannot precede intake date**
```
Tag: Feature: bsf-farm-data, Property 5: batch end cannot precede intake date
Generator: fc.tuple(fc.date(), fc.date()).filter(([a, b]) => b < a).map(([intake, end]) => [toISO(intake), toISO(end)])
Assert: harvestSchema.safeParse({ ...validHarvestBase, intake_date, batch_end }).success === false
        AND error path includes 'batch_end'
```

### Test File Locations

```
frontend/src/components/bsf/__tests__/
  NewIntakeDialog.test.tsx      # example-based tests for intake dialog
  RecordHarvestDialog.test.tsx  # example-based tests for harvest dialog
  schemas.test.ts               # property-based tests for Zod schemas + ratio preview
```
