# Implementation Plan: BSF Farm Data Entry

## Overview

Wire up the two missing data-entry workflows on the BSF Farm page: a New Intake dialog (creates a batch) and a Record Harvest dialog (closes out an active batch). Both dialogs use React Hook Form + Zod validation and call existing `bsfApi` methods. No backend or `api.ts` changes are needed.

## Tasks

- [x] 1. Create `frontend/src/components/bsf/schemas.ts`
  - Define `newIntakeSchema` with fields: `intake_date` (required string), `food_waste_kg` (positive number), `contamination_level` (enum: clean/minor/rejected, required), `batch_start` (optional string), `livestock_recipient` (optional string, max 255)
  - Add `superRefine` cross-field rule: if `batch_start` is provided and `batch_start < intake_date`, add a Zod issue on `batch_start`
  - Export `NewIntakeFormValues` as `z.infer<typeof newIntakeSchema>`
  - Define `harvestSchema` with fields: `larvae_output_kg` (number >= 0), `batch_end` (required string), `status` (enum: completed/rejected, required), `contamination_level` (optional enum), `livestock_recipient` (optional string, max 255), `intake_date` (string — context only, not submitted)
  - Add `superRefine` cross-field rule: if `batch_end < intake_date`, add a Zod issue on `batch_end`
  - Export `HarvestFormValues` as `z.infer<typeof harvestSchema>`
  - Export `extractErrorMessage(err: unknown, fallback: string): string` helper that unwraps Axios error `detail` (string or array) or falls back to the provided string
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 6.1, 6.2, 6.3, 6.4_

- [x] 2. Create `frontend/src/components/bsf/NewIntakeDialog.tsx`
  - [x] 2.1 Scaffold the component with `NewIntakeDialogProps` interface (`open`, `onOpenChange`, `onSuccess`) and `'use client'` directive
    - Import shadcn/ui `Dialog`, `DialogContent`, `DialogHeader`, `DialogTitle`, `DialogFooter`, `Input`, `Select`, `Button`, `Form` primitives
    - Initialise React Hook Form with `zodResolver(newIntakeSchema)` and sensible default values
    - _Requirements: 1.1, 1.2, 1.3_
  - [x] 2.2 Implement form fields and layout
    - Render `intake_date` as `<Input type="date">`, `food_waste_kg` as `<Input type="number">`, `contamination_level` as `<Select>` (clean / minor / rejected), `batch_start` as `<Input type="date">` (optional), `livestock_recipient` as `<Input type="text">` (optional)
    - Use dark slate theme: `slate-900` dialog background, `slate-700` input borders, `slate-400` labels, `green-600` submit button — consistent with `CONTAMINATION_STYLES` in the page
    - Render `<FormMessage>` under each field for inline Zod errors
    - _Requirements: 1.2, 9.1, 9.2_
  - [x] 2.3 Implement `useMutation` submission and error handling
    - Wire `useMutation` calling `bsfApi.createBatch` with the validated form values (omit undefined optionals before sending)
    - On success: call `onSuccess()` then `onOpenChange(false)`
    - On error: call `extractErrorMessage` and set `apiError` state; render `<p className="text-sm text-red-400">` above the footer buttons
    - Disable the "Create Batch" button and show a spinner while `isPending`
    - Reset the form inside the `onOpenChange` handler when `open` transitions to `false`
    - _Requirements: 1.4, 3.1, 3.2, 3.4_

- [x] 3. Create `frontend/src/components/bsf/RecordHarvestDialog.tsx`
  - [x] 3.1 Scaffold the component with `RecordHarvestDialogProps` interface (`open`, `onOpenChange`, `batch: BsfBatch | null`, `onSuccess`) and `'use client'` directive
    - Initialise React Hook Form with `zodResolver(harvestSchema)`; set `intake_date` default from `batch?.intake_date ?? ''`
    - _Requirements: 4.2, 4.3_
  - [x] 3.2 Implement form fields, layout, and conversion ratio preview
    - Render `larvae_output_kg` as `<Input type="number">`, `batch_end` as `<Input type="date">`, `status` as `<Select>` (completed / rejected), `contamination_level` as optional `<Select>` with colour-coded option labels matching `CONTAMINATION_STYLES`, `livestock_recipient` as optional `<Input type="text">`
    - Use `watch('larvae_output_kg')` to derive `conversionPreview`: when `larvaeOutputKg > 0` and `batch?.food_waste_kg > 0`, display `((larvaeOutputKg / batch.food_waste_kg) * 100).toFixed(1) + '%'`; otherwise display `'—'`
    - Render the preview as a read-only info row (e.g. `"Conversion ratio: 25.3%"`) that updates on every keystroke
    - Apply dark slate theme consistent with the page; use `green-600` submit button
    - _Requirements: 4.3, 5.1, 5.2, 5.3, 9.1, 9.2, 9.3_
  - [x] 3.3 Implement `useMutation` submission and error handling
    - Wire `useMutation` calling `bsfApi.updateBatch(batch.id, payload)` where `payload` is the form values with `intake_date` stripped out
    - On success: call `onSuccess()` then `onOpenChange(false)`
    - On error: call `extractErrorMessage` and set `apiError` state; render inline error above footer
    - Disable submit button and show spinner while `isPending`
    - Reset the form inside the `onOpenChange` handler when `open` transitions to `false`
    - _Requirements: 4.4, 7.1, 7.2, 7.4_

- [x] 4. Wire dialogs into `frontend/src/app/(dashboard)/bsf-farm/page.tsx`
  - [x] 4.1 Add dialog state and `handleSuccess` callback
    - Add `useState` for `intakeOpen`, `harvestOpen` (booleans), and `selectedBatch` (`BsfBatch | null`)
    - Add `useQueryClient()` (already imported via TanStack Query)
    - Implement `handleSuccess`: invalidate `['bsf', 'batches']` and `['bsf', 'stats']` query keys, then call `toast.success('Saved successfully')` (Sonner)
    - Implement `openHarvest(batch: BsfBatch)`: set `selectedBatch` and `setHarvestOpen(true)`
    - _Requirements: 3.3, 7.3_
  - [x] 4.2 Connect "New Intake" button and render `<NewIntakeDialog>`
    - Change the existing "New Intake" button `onClick` to `() => setIntakeOpen(true)`
    - Render `<NewIntakeDialog open={intakeOpen} onOpenChange={setIntakeOpen} onSuccess={handleSuccess} />` at the bottom of the JSX tree
    - _Requirements: 1.1_
  - [x] 4.3 Add "Record Harvest" row action and render `<RecordHarvestDialog>`
    - In the batch row's action cell, replace (or add alongside) the existing "View" button with a conditional "Record Harvest" button: only render it when `b.status === 'active'`
    - Button should be `opacity-0 group-hover:opacity-100` (same hover pattern as the existing "View" button), calling `openHarvest(b)` on click
    - Render `<RecordHarvestDialog open={harvestOpen} onOpenChange={setHarvestOpen} batch={selectedBatch} onSuccess={handleSuccess} />` at the bottom of the JSX tree
    - Clear `selectedBatch` when `harvestOpen` transitions to `false` (inside `onOpenChange` or a `useEffect`)
    - _Requirements: 4.1, 4.2, 4.4_

- [x] 5. Checkpoint — verify integration
  - Ensure all TypeScript types resolve without errors (`npm run lint` from `frontend/`)
  - Confirm "New Intake" button opens the dialog, Cancel closes and resets it
  - Confirm "Record Harvest" button appears only on active rows and opens the harvest dialog pre-populated with the correct batch
  - Ensure all tests pass, ask the user if questions arise.

- [ ]* 6. Write property-based tests for Zod schemas (`frontend/src/components/bsf/__tests__/schemas.test.ts`)
  - [ ]* 6.1 Write property test for Property 1: positive food waste required for intake
    - Use fast-check; generate `fc.oneof(fc.constant(0), fc.float({ max: -0.001 }), fc.constant(null), fc.constant(undefined))`
    - Assert `newIntakeSchema.safeParse({ ...validBase, food_waste_kg: value }).success === false`
    - **Property 1: Positive food waste required for intake**
    - **Validates: Requirements 2.2**
  - [ ]* 6.2 Write property test for Property 2: batch start cannot precede intake date
    - Generate pairs of ISO date strings where `batch_start < intake_date`
    - Assert parse fails and error path includes `'batch_start'`
    - **Property 2: Batch start cannot precede intake date**
    - **Validates: Requirements 2.4**
  - [ ]* 6.3 Write property test for Property 3: conversion ratio preview consistency
    - Extract `computeConversionPreview(larvaeKg, foodWasteKg)` as a pure function from `RecordHarvestDialog` (or inline the formula)
    - Generate `fc.tuple(fc.float({ min: 0.001, max: 10000 }), fc.float({ min: 0.001, max: 10000 }))`
    - Assert result equals `((larvaeKg / foodWasteKg) * 100).toFixed(1) + '%'`
    - **Property 3: Conversion ratio preview consistent with inputs**
    - **Validates: Requirements 5.1, 5.3**
  - [ ]* 6.4 Write property test for Property 4: non-negative larvae output required for harvest
    - Generate `fc.oneof(fc.float({ max: -0.001 }), fc.constant(null), fc.constant(undefined))`
    - Assert `harvestSchema.safeParse({ ...validHarvestBase, larvae_output_kg: value }).success === false`
    - **Property 4: Non-negative larvae output required for harvest**
    - **Validates: Requirements 6.1**
  - [ ]* 6.5 Write property test for Property 5: batch end cannot precede intake date
    - Generate pairs of ISO date strings where `batch_end < intake_date`
    - Assert parse fails and error path includes `'batch_end'`
    - **Property 5: Batch end cannot precede intake date**
    - **Validates: Requirements 6.4**

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- `bsfApi.createBatch` and `bsfApi.updateBatch` already exist in `src/lib/api.ts` — no API changes needed
- `useQueryClient` is already imported in the page — just add the invalidation calls
- The `BsfBatch` interface is already defined locally in `page.tsx`; import or re-use it in the dialog components
- Property tests require `fast-check` — install with `npm install --save-dev fast-check` if not already present
- Each task references specific requirements for traceability
