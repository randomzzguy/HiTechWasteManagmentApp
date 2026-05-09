# Implementation Plan: Labour Forms

## Overview

Activate the "Add Staff" and "Create Site Assignment" buttons on the Labour page by implementing two controlled Dialog components with React Hook Form + Zod validation, wiring them into the page, and covering the Zod schemas and payload builders with fast-check property-based tests.

`labourApi.createStaff` and `labourApi.createSiteAssignment` already exist in `api.ts`. No new API methods are required — dropdown data comes from `settingsApi.listUsers` and `clientsApi.list` directly.

## Tasks

- [x] 1. Create Zod schemas and payload builder helpers
  - Create `frontend/src/components/labour/schemas.ts`
  - Define and export `addStaffSchema` and `AddStaffFormValues` exactly as specified in the design
  - Define and export `siteAssignmentSchema` and `SiteAssignmentFormValues` exactly as specified in the design (including both `.refine()` calls)
  - Export a pure `buildAddStaffPayload(values: AddStaffFormValues)` function that strips `work_permit_expiry` when `employment_type !== 'foreign_worker'` and converts empty strings to `undefined` for optional fields
  - Export a pure `buildSiteAssignmentPayload(values: SiteAssignmentFormValues)` function that converts empty `end_date` to `undefined`
  - Export a shared `extractErrorMessage(err: unknown, fallback: string): string` helper
  - _Requirements: 2.3, 2.4, 2.8, 2.9, 3.1, 5.14, 5.15, 6.1_

- [ ]* 1.1 Write property tests for `addStaffSchema` (Properties 1–4)
  - Create `frontend/src/components/labour/__tests__/schemas.property.test.ts`
  - Install `fast-check` as a dev dependency if not already present (`npm install -D fast-check`)
  - **Property 1: Add Staff schema rejects missing required fields** — generate objects with absent/invalid `user_id` or `employment_type`; assert `addStaffSchema.safeParse` returns `success: false`
    - `// Feature: labour-forms, Property 1`
    - **Validates: Requirements 2.6, 2.7**
  - **Property 2: Labour agent name length boundary** — generate strings of random length; assert schema accepts ≤ 200 chars and rejects > 200 chars
    - `// Feature: labour-forms, Property 2`
    - **Validates: Requirements 2.3, 2.9**
  - **Property 3: Work permit expiry visibility logic** — generate random employment type values; assert `buildAddStaffPayload` includes `work_permit_expiry` iff `employment_type === 'foreign_worker'`
    - `// Feature: labour-forms, Property 3`
    - **Validates: Requirements 2.4, 2.8**
  - **Property 4: Add Staff payload maps form values correctly** — generate valid `AddStaffFormValues` objects; assert `buildAddStaffPayload` output matches field-for-field
    - `// Feature: labour-forms, Property 4`
    - **Validates: Requirements 3.1**

- [ ]* 1.2 Write property tests for `siteAssignmentSchema` (Properties 5–8)
  - Add to the same test file `frontend/src/components/labour/__tests__/schemas.property.test.ts`
  - **Property 5: Site Assignment schema rejects missing required fields** — generate objects with one or more of `client_id`, `site_address`, `supervisor_id`, `start_date`, `members` missing or empty; assert `siteAssignmentSchema.safeParse` returns `success: false`
    - `// Feature: labour-forms, Property 5`
    - **Validates: Requirements 5.9, 5.10, 5.11, 5.12, 5.13**
  - **Property 6: End date must not precede start date** — generate `(start_date, end_date)` pairs where `end_date < start_date`; assert schema rejects with error on `end_date` path
    - `// Feature: labour-forms, Property 6`
    - **Validates: Requirements 5.14**
  - **Property 7: Members array must contain at least one field supervisor** — generate `members` arrays with no `field_supervisor` entry; assert schema rejects with error on `members` path
    - `// Feature: labour-forms, Property 7`
    - **Validates: Requirements 5.15**
  - **Property 8: Site Assignment payload maps form values correctly** — generate valid `SiteAssignmentFormValues` objects; assert `buildSiteAssignmentPayload` output matches field-for-field
    - `// Feature: labour-forms, Property 8`
    - **Validates: Requirements 6.1**

- [x] 2. Implement `AddStaffDialog` component
  - Create `frontend/src/components/labour/AddStaffDialog.tsx` with `'use client'`
  - Accept props: `open: boolean`, `onOpenChange: (open: boolean) => void`, `onSuccess: () => void`
  - Use `useQuery` with `queryKey: ['users-dropdown']`, `enabled: open`, `staleTime: 5 * 60_000` calling `settingsApi.listUsers({ page_size: 200, is_active: true })`
  - Wire `useForm<AddStaffFormValues>` with `zodResolver(addStaffSchema)` and `defaultValues`
  - Use `useMutation` wrapping `labourApi.createStaff(buildAddStaffPayload(values))`; on success call `onSuccess()` then `onOpenChange(false)`; on error call `toast.error(extractErrorMessage(...))`  with 409 special-casing per design
  - Use `useEffect` watching `employment_type` to call `setValue('work_permit_expiry', '')` when type is not `foreign_worker`
  - Render shadcn `Dialog > DialogContent > DialogHeader` with title "Add Staff"
  - Render shadcn `Form > FormField` for each field: User (Select), Employment Type (Select), Labour Agent Name (Input), Work Permit Expiry (date Input, conditionally rendered), Notes (Textarea)
  - Render submit `Button` with `disabled={isPending}` and `<Loader2 className="animate-spin" />` spinner when pending; styled `bg-emerald-600 hover:bg-emerald-700`
  - Reset form on successful close via `form.reset()` inside `onSuccess`
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 3.1, 3.2, 3.4, 3.5, 3.6, 7.1, 7.3, 7.5_

- [ ]* 2.1 Write unit tests for `AddStaffDialog`
  - Create `frontend/src/components/labour/__tests__/AddStaffDialog.test.tsx`
  - Mock `labourApi.createStaff`, `settingsApi.listUsers`, `sonner`
  - Test: dialog renders when `open={true}`; submit button disabled while `isPending`; work permit field hidden for `permanent`/`contract`, visible for `foreign_worker`; success path closes dialog and calls `onSuccess`; 409 shows specific toast and dialog stays open; 500 shows generic toast and dialog stays open
  - _Requirements: 1.3, 2.4, 2.8, 3.2, 3.4, 3.5, 3.6_

- [x] 3. Implement `CreateSiteAssignmentDialog` component
  - Create `frontend/src/components/labour/CreateSiteAssignmentDialog.tsx` with `'use client'`
  - Accept props: `open: boolean`, `onOpenChange: (open: boolean) => void`, `onSuccess: () => void`
  - Use three `useQuery` calls (all `enabled: open`, `staleTime: 5 * 60_000`):
    - `queryKey: ['clients-dropdown']` → `clientsApi.list({ page_size: 200 })`
    - `queryKey: ['staff-dropdown']` → `labourApi.listStaff()`
    - (supervisor uses the same staff-dropdown data)
  - Wire `useForm<SiteAssignmentFormValues>` with `zodResolver(siteAssignmentSchema)` and `defaultValues` (empty `members: []`)
  - Use `useFieldArray({ control, name: 'members' })` for the team members list
  - Maintain local `useState<string>` for the "pending staff picker" select value; clicking "Add Member" calls `append({ staff_profile_id: selectedId, role_at_site: '' as any })` and resets the picker
  - Filter already-added `staff_profile_id` values out of the staff picker dropdown to prevent duplicates
  - Use `useMutation` wrapping `labourApi.createSiteAssignment(buildSiteAssignmentPayload(values))`; on success call `onSuccess()` then `onOpenChange(false)`; on error call `toast.error(extractErrorMessage(...))` with 409 pass-through per design
  - Render shadcn `Dialog > DialogContent > DialogHeader` with title "Create Site Assignment"
  - Render `FormField` for: Client (Select), Site Address (Input), Supervisor (Select), Start Date (date Input), End Date (date Input, optional), Team Members section (picker + field array rows), Notes (Textarea)
  - Each member row shows staff name, a `Select` for `role_at_site`, and a remove `Button` calling `remove(index)`
  - Display `formState.errors.members?.message` or `formState.errors.members?.root?.message` below the member list
  - Render submit `Button` with `disabled={isPending}` spinner; styled `bg-emerald-600 hover:bg-emerald-700`
  - Reset form on successful close via `form.reset()`
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 5.10, 5.11, 5.12, 5.13, 5.14, 5.15, 6.1, 6.2, 6.4, 6.5, 6.6, 7.2, 7.4, 7.6_

- [ ]* 3.1 Write unit tests for `CreateSiteAssignmentDialog`
  - Create `frontend/src/components/labour/__tests__/CreateSiteAssignmentDialog.test.tsx`
  - Mock `labourApi.createSiteAssignment`, `labourApi.listStaff`, `clientsApi.list`, `sonner`
  - Test: dialog renders when `open={true}`; adding a member appends a row; removing a member removes the row; field_supervisor validation error shown when no member has that role; end date before start date shows validation error; success path closes dialog and calls `onSuccess`; 409 shows response body message and dialog stays open
  - _Requirements: 4.3, 5.14, 5.15, 6.2, 6.4, 6.5, 6.6_

- [x] 4. Checkpoint — Ensure all tests pass
  - Run `npx vitest --run` from `frontend/` and confirm all property and unit tests pass
  - Fix any type errors reported by `tsc --noEmit`
  - Ask the user if any questions arise before proceeding

- [x] 5. Wire dialogs into the Labour page
  - Edit `frontend/src/app/(dashboard)/labour/page.tsx`
  - Add imports: `AddStaffDialog`, `CreateSiteAssignmentDialog`, `useQueryClient` from `@tanstack/react-query`, `toast` from `sonner`
  - Add state: `const [addStaffOpen, setAddStaffOpen] = useState(false)` and `const [assignmentOpen, setAssignmentOpen] = useState(false)`
  - Add `const queryClient = useQueryClient()`
  - Implement `handleStaffSuccess`: `queryClient.invalidateQueries({ queryKey: ['staff'] })` then `toast.success('Staff profile created')`
  - Implement `handleAssignmentSuccess`: `queryClient.invalidateQueries({ queryKey: ['staff'] })` then `toast.success('Site assignment created')`
  - Wire the existing `+ Add Staff` button: add `onClick={() => setAddStaffOpen(true)}`
  - Add a new `+ Create Site Assignment` button next to it: `onClick={() => setAssignmentOpen(true)}`, styled `bg-slate-700 hover:bg-slate-600 text-white text-sm`
  - Render `<AddStaffDialog open={addStaffOpen} onOpenChange={setAddStaffOpen} onSuccess={handleStaffSuccess} />` inside the page JSX
  - Render `<CreateSiteAssignmentDialog open={assignmentOpen} onOpenChange={setAssignmentOpen} onSuccess={handleAssignmentSuccess} />` inside the page JSX
  - _Requirements: 1.1, 1.2, 1.3, 3.2, 3.3, 4.1, 4.2, 4.3, 6.2, 6.3, 7.7, 7.8_

- [x] 6. Final checkpoint — Ensure all tests pass
  - Run `npx vitest --run` from `frontend/` and confirm the full test suite is green
  - Run `npm run lint` from `frontend/` and fix any ESLint errors
  - Ask the user if any questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- `buildAddStaffPayload` and `buildSiteAssignmentPayload` are pure functions in `schemas.ts` — this makes Properties 4 and 8 independently testable without mounting any component
- The design explicitly prefers importing `settingsApi` and `clientsApi` directly in the dialogs over adding proxy methods to `labourApi`
- `createStaff` and `createSiteAssignment` already exist in `labourApi` — no `api.ts` changes are needed
- Dropdown query keys (`users-dropdown`, `clients-dropdown`, `staff-dropdown`) are intentionally not invalidated on success; their 5-minute `staleTime` is sufficient
