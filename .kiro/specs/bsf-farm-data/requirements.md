# Requirements Document

## Introduction

The BSF Farm page (`/bsf-farm`) currently displays batch data in a read-only table with stats cards and pagination. Two critical data-entry workflows are missing: operators cannot create new food waste intake records, and they cannot record harvest results against active batches. This feature wires up the "New Intake" button with a modal form and adds a "Record Harvest" action to active batch rows, enabling the full BSF bioconversion lifecycle to be managed from the frontend. Both workflows call existing backend endpoints (`POST /api/v1/bsf/batches/` and `PATCH /api/v1/bsf/batches/{id}/`) via `bsfApi` in `src/lib/api.ts`.

## Glossary

- **BSF_Farm_Page**: The Next.js page at `/bsf-farm` that displays BSF batch data.
- **New_Intake_Modal**: The shadcn/ui Dialog component triggered by the "New Intake" button, used to create a new BSF batch.
- **Harvest_Modal**: The shadcn/ui Dialog component triggered from an active batch row, used to record harvest results.
- **BSF_Batch**: A record in the `bsf_batches` table representing one food waste intake and its associated larvae conversion cycle.
- **Batch_Table**: The table on the BSF Farm page listing all BSF batches with pagination.
- **bsfApi**: The domain API client object in `src/lib/api.ts` that wraps all BSF-related HTTP calls.
- **Conversion_Ratio**: The ratio of `larvae_output_kg` to `food_waste_kg`, expressed as a decimal (e.g. 0.25 = 25%).
- **Active_Batch**: A BSF_Batch with `status === "active"`.
- **TanStack_Query**: The server-state management library (v5) used for data fetching, caching, and cache invalidation.
- **Contamination_Level**: A quality classification of the food waste input — one of `clean`, `minor`, or `rejected`.

---

## Requirements

### Requirement 1: New Intake Modal — Trigger and Display

**User Story:** As an operations manager, I want to open a "New Intake" form by clicking the existing "New Intake" button, so that I can record a new food waste intake without leaving the BSF Farm page.

#### Acceptance Criteria

1. WHEN the user clicks the "New Intake" button in the BSF_Farm_Page header, THE New_Intake_Modal SHALL open as a centered Dialog overlay.
2. THE New_Intake_Modal SHALL display a form with the following fields: `intake_date` (date picker, required), `food_waste_kg` (number input, required), `contamination_level` (select: clean / minor / rejected, required), `batch_start` (date picker, optional), and `livestock_recipient` (text input, optional).
3. WHEN the New_Intake_Modal is open, THE New_Intake_Modal SHALL display a "Cancel" button and a "Create Batch" submit button.
4. WHEN the user clicks "Cancel" or clicks outside the dialog, THE New_Intake_Modal SHALL close and discard all unsaved form state.

---

### Requirement 2: New Intake Form — Validation

**User Story:** As an operations manager, I want the New Intake form to validate my input before submission, so that I cannot accidentally create an invalid batch record.

#### Acceptance Criteria

1. WHEN the user submits the New_Intake_Modal form with `intake_date` empty, THE New_Intake_Modal SHALL display an inline validation error on the `intake_date` field and SHALL NOT submit the form.
2. WHEN the user submits the New_Intake_Modal form with `food_waste_kg` empty or less than or equal to zero, THE New_Intake_Modal SHALL display an inline validation error on the `food_waste_kg` field and SHALL NOT submit the form.
3. WHEN the user submits the New_Intake_Modal form with `contamination_level` unselected, THE New_Intake_Modal SHALL display an inline validation error on the `contamination_level` field and SHALL NOT submit the form.
4. IF `batch_start` is provided and is earlier than `intake_date`, THEN THE New_Intake_Modal SHALL display an inline validation error on the `batch_start` field and SHALL NOT submit the form.

---

### Requirement 3: New Intake Form — Submission

**User Story:** As an operations manager, I want the New Intake form to call the backend API and refresh the batch list on success, so that the new batch is immediately visible in the table.

#### Acceptance Criteria

1. WHEN the user submits a valid New_Intake_Modal form, THE New_Intake_Modal SHALL call `bsfApi.createBatch` with the form values as a `POST` request to `/api/v1/bsf/batches/`.
2. WHILE the New_Intake_Modal form submission is in progress, THE New_Intake_Modal SHALL disable the "Create Batch" button and display a loading indicator.
3. WHEN `bsfApi.createBatch` returns a success response, THE New_Intake_Modal SHALL close, THE BSF_Farm_Page SHALL invalidate the `['bsf', 'batches']` and `['bsf', 'stats']` TanStack_Query cache keys, and THE BSF_Farm_Page SHALL display a success toast notification.
4. IF `bsfApi.createBatch` returns an error response, THEN THE New_Intake_Modal SHALL remain open, SHALL display the error message returned by the API, and SHALL re-enable the "Create Batch" button.

---

### Requirement 4: Record Harvest — Trigger and Display

**User Story:** As an operations manager, I want to open a "Record Harvest" form from an active batch row, so that I can record larvae output and close out the batch.

#### Acceptance Criteria

1. WHEN the user hovers over a row in the Batch_Table where `status === "active"`, THE Batch_Table SHALL display a "Record Harvest" action button in the row's action cell.
2. WHEN the user clicks the "Record Harvest" button on an Active_Batch row, THE Harvest_Modal SHALL open pre-populated with the selected batch's `id` and `food_waste_kg` (used for conversion ratio preview).
3. THE Harvest_Modal SHALL display a form with the following fields: `larvae_output_kg` (number input, required, >= 0), `batch_end` (date picker, required), `status` (select: completed / rejected, required), `contamination_level` (select: clean / minor / rejected, optional update), and `livestock_recipient` (text input, optional).
4. WHEN the user clicks "Cancel" or clicks outside the Harvest_Modal, THE Harvest_Modal SHALL close and discard all unsaved form state.

---

### Requirement 5: Record Harvest — Conversion Ratio Preview

**User Story:** As an operations manager, I want to see a live conversion ratio preview as I enter larvae output, so that I can verify the result before saving.

#### Acceptance Criteria

1. WHILE the Harvest_Modal is open and `larvae_output_kg` has a valid numeric value >= 0, THE Harvest_Modal SHALL display a conversion ratio preview calculated as `larvae_output_kg / food_waste_kg`, formatted as a percentage to one decimal place (e.g. "25.3%").
2. WHEN `larvae_output_kg` is empty or zero, THE Harvest_Modal SHALL display "—" in place of the conversion ratio preview.
3. THE Harvest_Modal SHALL update the conversion ratio preview in real time as the user types in the `larvae_output_kg` field, without requiring form submission.

---

### Requirement 6: Record Harvest — Validation

**User Story:** As an operations manager, I want the Record Harvest form to validate my input before submission, so that I cannot save an incomplete or inconsistent harvest record.

#### Acceptance Criteria

1. WHEN the user submits the Harvest_Modal form with `larvae_output_kg` empty or negative, THE Harvest_Modal SHALL display an inline validation error on the `larvae_output_kg` field and SHALL NOT submit the form.
2. WHEN the user submits the Harvest_Modal form with `batch_end` empty, THE Harvest_Modal SHALL display an inline validation error on the `batch_end` field and SHALL NOT submit the form.
3. WHEN the user submits the Harvest_Modal form with `status` unselected, THE Harvest_Modal SHALL display an inline validation error on the `status` field and SHALL NOT submit the form.
4. IF `batch_end` is provided and is earlier than the Active_Batch's `intake_date`, THEN THE Harvest_Modal SHALL display an inline validation error on the `batch_end` field and SHALL NOT submit the form.

---

### Requirement 7: Record Harvest — Submission

**User Story:** As an operations manager, I want the Record Harvest form to call the backend API and refresh the batch list on success, so that the batch status and harvest data are immediately reflected in the table.

#### Acceptance Criteria

1. WHEN the user submits a valid Harvest_Modal form, THE Harvest_Modal SHALL call `bsfApi.updateBatch` with the batch `id` and form values as a `PATCH` request to `/api/v1/bsf/batches/{id}/`.
2. WHILE the Harvest_Modal form submission is in progress, THE Harvest_Modal SHALL disable the submit button and display a loading indicator.
3. WHEN `bsfApi.updateBatch` returns a success response, THE Harvest_Modal SHALL close, THE BSF_Farm_Page SHALL invalidate the `['bsf', 'batches']` and `['bsf', 'stats']` TanStack_Query cache keys, and THE BSF_Farm_Page SHALL display a success toast notification.
4. IF `bsfApi.updateBatch` returns an error response, THEN THE Harvest_Modal SHALL remain open, SHALL display the error message returned by the API, and SHALL re-enable the submit button.

---

### Requirement 8: bsfApi — Create and Update Batch Methods

**User Story:** As a developer, I want `bsfApi` in `src/lib/api.ts` to expose `createBatch` and `updateBatch` methods, so that the modal components have a typed, consistent interface for all BSF API calls.

#### Acceptance Criteria

1. THE bsfApi SHALL expose a `createBatch(payload: BSFBatchCreate)` method that sends a `POST` request to `/api/v1/bsf/batches/` and returns the created `BSFBatchRead` object.
2. THE bsfApi SHALL expose an `updateBatch(id: string, payload: BSFBatchUpdate)` method that sends a `PATCH` request to `/api/v1/bsf/batches/{id}/` and returns the updated `BSFBatchRead` object.
3. WHEN `createBatch` or `updateBatch` receives a non-2xx HTTP response, THE bsfApi SHALL reject the returned Promise with the error response body so that calling components can display the API error message.
4. THE bsfApi `createBatch` payload SHALL include: `intake_date` (string, ISO date), `food_waste_kg` (number), `contamination_level` (string), and optionally `batch_start` (string, ISO date) and `livestock_recipient` (string).
5. THE bsfApi `updateBatch` payload SHALL include: `larvae_output_kg` (number), `batch_end` (string, ISO date), `status` (string), and optionally `contamination_level` (string) and `livestock_recipient` (string).

---

### Requirement 9: Visual Design Consistency

**User Story:** As a user, I want the new modals to match the existing BSF Farm page visual style, so that the UI feels cohesive.

#### Acceptance Criteria

1. THE New_Intake_Modal and Harvest_Modal SHALL use the dark slate theme: `slate-900` dialog background, `slate-700` input borders, `slate-400` label text, and `emerald-500` / `green-600` primary action button colours.
2. THE New_Intake_Modal and Harvest_Modal SHALL use shadcn/ui `Dialog`, `Input`, `Select`, and `Button` primitives consistent with the rest of the dashboard.
3. WHERE `contamination_level` is displayed in the Harvest_Modal, THE Harvest_Modal SHALL apply the same colour coding used in the Batch_Table: `text-green-400` for `clean`, `text-amber-400` for `minor`, and `text-red-400` for `rejected`.
