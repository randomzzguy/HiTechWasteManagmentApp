# Design Document — Labour Forms

## Overview

This feature activates two non-functional buttons on the `/labour` page: **Add Staff** and **Create Site Assignment**. Each button opens a shadcn `Dialog` containing a validated form built with React Hook Form + Zod. On success the form calls the existing FastAPI endpoints, invalidates the relevant TanStack Query cache keys, and shows a Sonner toast. No backend changes are required.

The implementation adds:
- `frontend/src/components/labour/AddStaffDialog.tsx`
- `frontend/src/components/labour/CreateSiteAssignmentDialog.tsx`
- Two new `labourApi` methods: `listUsers` (proxying `settingsApi.listUsers`) and `listClients` (proxying `clientsApi.list`) for dropdown data — or the dialogs can call the existing domain APIs directly.
- Wiring in `frontend/src/app/(dashboard)/labour/page.tsx` to control open/close state.

---

## Architecture

```
Labour Page (page.tsx)
│
├── open state: addStaffOpen (boolean)
├── open state: assignmentOpen (boolean)
│
├── <AddStaffDialog open={addStaffOpen} onOpenChange={setAddStaffOpen} onSuccess={handleStaffSuccess} />
└── <CreateSiteAssignmentDialog open={assignmentOpen} onOpenChange={setAssignmentOpen} onSuccess={handleAssignmentSuccess} />
```

Both dialogs are **controlled** — the page owns the `open` boolean and passes `onOpenChange` so the dialog can close itself on Escape / outside-click (shadcn Dialog handles this natively). The `onSuccess` callback is invoked after a successful API response; the page uses it to fire the Sonner toast and invalidate the TanStack Query cache.

Data flow for each dialog:

```
User fills form
  → RHF validates via zodResolver
  → useMutation calls labourApi method
  → on success: onSuccess() → invalidateQueries + toast.success
  → on error:   parse AxiosError → toast.error (stay open)
```

---

## Components and Interfaces

### AddStaffDialog

```typescript
// frontend/src/components/labour/AddStaffDialog.tsx
interface AddStaffDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}
```

Internal state:
- React Hook Form instance bound to `AddStaffFormValues`
- `useMutation` wrapping `labourApi.createStaff`
- `useQuery` for users dropdown (enabled only when `open === true`)
- Watched `employment_type` field to conditionally show/hide Work Permit Expiry

### CreateSiteAssignmentDialog

```typescript
// frontend/src/components/labour/CreateSiteAssignmentDialog.tsx
interface CreateSiteAssignmentDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}
```

Internal state:
- React Hook Form instance bound to `SiteAssignmentFormValues`
- `useMutation` wrapping `labourApi.createSiteAssignment`
- `useQuery` for clients dropdown (enabled when `open`)
- `useQuery` for staff dropdown (enabled when `open`)
- `useFieldArray` for the `members` array (team members + per-member role)

### Labour Page wiring

```typescript
// page.tsx additions
const [addStaffOpen, setAddStaffOpen] = useState(false)
const [assignmentOpen, setAssignmentOpen] = useState(false)
const queryClient = useQueryClient()

const handleStaffSuccess = () => {
  queryClient.invalidateQueries({ queryKey: ['staff'] })
  toast.success('Staff profile created')
}

const handleAssignmentSuccess = () => {
  queryClient.invalidateQueries({ queryKey: ['staff'] })
  toast.success('Site assignment created')
}
```

The existing `+ Add Staff` button gets `onClick={() => setAddStaffOpen(true)}`. A new `+ Create Site Assignment` button is added alongside it.

---

## Data Models

### Zod Schema — Add Staff Form

```typescript
import { z } from 'zod'

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
  work_permit_expiry: z.string().optional(),  // ISO date string or empty
  notes: z.string().optional(),
})

export type AddStaffFormValues = z.infer<typeof addStaffSchema>
```

The `work_permit_expiry` field is only included in the API payload when `employment_type === 'foreign_worker'`; otherwise it is stripped before submission. The field is hidden in the UI for other employment types and its RHF value is reset to `''` via `setValue('work_permit_expiry', '')` inside a `useEffect` watching `employment_type`.

### Zod Schema — Create Site Assignment Form

```typescript
import { z } from 'zod'

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
    members: z
      .array(memberSchema)
      .min(1, 'At least one team member is required'),
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
    (data) =>
      data.members.some((m) => m.role_at_site === 'field_supervisor'),
    {
      message: 'At least one team member must have the role Field Supervisor',
      path: ['members'],
    }
  )

export type SiteAssignmentFormValues = z.infer<typeof siteAssignmentSchema>
```

### API payload mapping

`AddStaffFormValues` maps 1-to-1 to `StaffProfileCreate`. Before calling `labourApi.createStaff`, the component strips `work_permit_expiry` when `employment_type !== 'foreign_worker'` and converts empty strings to `undefined` for optional fields.

`SiteAssignmentFormValues` maps 1-to-1 to `SiteAssignmentCreate`. The `members` array is already in the correct `{ staff_profile_id, role_at_site }` shape.

### labourApi additions

Two read methods are needed for dropdown population. They already exist on other domain objects but are added to `labourApi` for co-location:

```typescript
// In labourApi (api.ts)
listUsersForDropdown: (params?: { is_active?: boolean }): Promise<PaginatedResponse<Record<string, unknown>>> =>
  api.get('/api/v1/settings/users/', { params: { page_size: 200, ...params } }).then(getData),

listClientsForDropdown: (params?: { status?: string }): Promise<PaginatedResponse<Record<string, unknown>>> =>
  api.get('/api/v1/clients/', { params: { page_size: 200, ...params } }).then(getData),
```

Alternatively the dialogs can import `settingsApi.listUsers` and `clientsApi.list` directly — both approaches are acceptable. The direct import approach avoids duplication and is preferred.

---

## Team Members Multi-Select UX

The `members` field in `CreateSiteAssignmentDialog` uses `useFieldArray` from React Hook Form. The UX is a two-step interaction:

1. **Staff picker**: A shadcn `Select` (or a custom combobox) lets the user pick a staff member from the available list. Clicking "Add Member" appends `{ staff_profile_id: selectedId, role_at_site: '' }` to the field array.
2. **Role selector**: Each appended member renders as a row showing the staff member's name and a `Select` for `role_at_site`. The user must choose a role before submitting.
3. **Remove**: Each row has a remove button (×) that calls `remove(index)`.

```
┌─────────────────────────────────────────────────────┐
│ Team Members *                                       │
│ ┌──────────────────────────────┐  [+ Add Member]    │
│ │ Select staff member…         │                    │
│ └──────────────────────────────┘                    │
│                                                     │
│  John Doe    [Field Supervisor ▼]  [×]              │
│  Jane Smith  [Waste Segregator ▼]  [×]              │
└─────────────────────────────────────────────────────┘
```

Staff already added to the members list are filtered out of the picker dropdown to prevent duplicates. The validation error for the `members` array (empty array or no field_supervisor) is displayed below the member list using `formState.errors.members?.message` or `formState.errors.members?.root?.message`.

---

## TanStack Query Cache Invalidation Strategy

| Event | Cache keys invalidated |
|---|---|
| `createStaff` success | `['staff']` |
| `createSiteAssignment` success | `['staff']` |

The `['staff']` key covers the `listStaff` query already running on the Labour page. Invalidating it causes the staff table to refetch automatically, reflecting the new staff profile's `assignment_status` changes.

Dropdown queries use separate, scoped keys with `staleTime: 5 * 60_000` (5 minutes) and are only enabled when the dialog is open:

```typescript
useQuery({
  queryKey: ['users-dropdown'],
  queryFn: () => settingsApi.listUsers({ page_size: 200, is_active: true }),
  staleTime: 5 * 60_000,
  enabled: open,
})

useQuery({
  queryKey: ['clients-dropdown'],
  queryFn: () => clientsApi.list({ page_size: 200 }),
  staleTime: 5 * 60_000,
  enabled: open,
})

useQuery({
  queryKey: ['staff-dropdown'],
  queryFn: () => labourApi.listStaff(),
  staleTime: 5 * 60_000,
  enabled: open,
})
```

These dropdown keys are not invalidated on success — the data is stable enough for the 5-minute window.

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Add Staff schema rejects missing required fields

*For any* form submission object where `user_id` is absent or not a valid UUID, or where `employment_type` is absent or not one of the three valid values, the `addStaffSchema` Zod parse SHALL return a failure result and SHALL NOT produce a valid `AddStaffFormValues` object.

**Validates: Requirements 2.6, 2.7**

### Property 2: Labour agent name length boundary

*For any* string value assigned to `labour_agent_name`, the `addStaffSchema` SHALL accept it when its length is ≤ 200 characters and SHALL reject it when its length is > 200 characters.

**Validates: Requirements 2.3, 2.9**

### Property 3: Work permit expiry visibility is determined by employment type

*For any* employment type value, the `work_permit_expiry` field SHALL be visible and enabled if and only if the employment type is `foreign_worker`. For all other employment type values (`permanent`, `contract`), the field SHALL be hidden and its value SHALL be cleared.

**Validates: Requirements 2.4, 2.8**

### Property 4: Add Staff payload maps form values correctly

*For any* valid `AddStaffFormValues` object, the payload passed to `labourApi.createStaff` SHALL contain exactly the fields `user_id`, `employment_type`, and optionally `labour_agent_name`, `work_permit_expiry` (only when `employment_type === 'foreign_worker'`), and `notes`, with values identical to those in the form object.

**Validates: Requirements 3.1**

### Property 5: Site Assignment schema rejects missing required fields

*For any* form submission object missing any of `client_id`, `site_address`, `supervisor_id`, `start_date`, or `members` (empty array), the `siteAssignmentSchema` Zod parse SHALL return a failure result.

**Validates: Requirements 5.9, 5.10, 5.11, 5.12, 5.13**

### Property 6: End date must not precede start date

*For any* `(start_date, end_date)` pair where `end_date` is provided and `end_date < start_date`, the `siteAssignmentSchema` refine SHALL reject the object with an error on the `end_date` path.

**Validates: Requirements 5.14**

### Property 7: Members array must contain at least one field supervisor

*For any* `members` array where no element has `role_at_site === 'field_supervisor'`, the `siteAssignmentSchema` refine SHALL reject the object with an error on the `members` path.

**Validates: Requirements 5.15**

### Property 8: Site Assignment payload maps form values correctly

*For any* valid `SiteAssignmentFormValues` object, the payload passed to `labourApi.createSiteAssignment` SHALL contain exactly the fields `client_id`, `site_address`, `supervisor_id`, `start_date`, `members`, and optionally `end_date` and `notes`, with values identical to those in the form object.

**Validates: Requirements 6.1**

---

## Error Handling

### Axios error extraction

Both dialogs use a shared helper to extract a human-readable message from an Axios error:

```typescript
function extractErrorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map((d) => d.msg).join(', ')
    return err.response?.data?.message ?? fallback
  }
  return fallback
}
```

### 409 Conflict

- **Add Staff 409**: The backend does not currently return 409 for duplicate staff profiles (it would return 422 or 500 on a unique constraint violation). The frontend handles it defensively: if `err.response?.status === 409`, show `"A staff profile already exists for this user"`.
- **Site Assignment 409**: The backend explicitly returns 409 when a staff member has an overlapping assignment. The `detail` field contains the specific message (e.g. `"Staff member X has overlapping assignment at Y"`). This is passed directly to the toast.

### Mutation error handler pattern

```typescript
onError: (err) => {
  const is409 = axios.isAxiosError(err) && err.response?.status === 409
  const message = is409
    ? CONFLICT_MESSAGE   // form-specific constant
    : extractErrorMessage(err, 'An unexpected error occurred')
  toast.error(message)
  // dialog stays open — no onOpenChange(false) call
}
```

### Loading state

`useMutation` provides `isPending`. The submit button renders:

```tsx
<Button type="submit" disabled={isPending} className="bg-emerald-600 hover:bg-emerald-700">
  {isPending ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Saving…</> : 'Save'}
</Button>
```

---

## Testing Strategy

### Unit tests (Vitest + React Testing Library)

Focus on specific examples and edge cases:

- Dialog opens when trigger button is clicked
- Dialog closes on Escape key / outside click
- Success path: mock `labourApi.createStaff` → verify toast and dialog close
- 409 path: mock returns 409 → verify specific toast message, dialog stays open
- Generic error path: mock returns 500 → verify generic toast, dialog stays open
- Loading state: submit button is disabled while mutation is pending
- Work permit expiry field hidden for `permanent` and `contract` types
- Work permit expiry field visible for `foreign_worker` type
- Removing a team member from the members list
- `field_supervisor` validation error shown when no member has that role

### Property-based tests (fast-check, minimum 100 iterations each)

Each property test references its design property via a comment tag:
`// Feature: labour-forms, Property N: <property_text>`

- **Property 1**: Generate random objects with missing/invalid `user_id` or `employment_type` → assert `addStaffSchema.safeParse` returns `success: false`
- **Property 2**: Generate strings of random length → assert schema accepts ≤ 200 chars and rejects > 200 chars
- **Property 3**: Generate random employment type values → assert field visibility logic returns `true` iff value is `'foreign_worker'`
- **Property 4**: Generate valid `AddStaffFormValues` objects → assert the constructed payload matches field-for-field
- **Property 5**: Generate objects with one or more required fields missing → assert `siteAssignmentSchema.safeParse` returns `success: false`
- **Property 6**: Generate `(start_date, end_date)` pairs where `end_date < start_date` → assert schema rejects with error on `end_date`
- **Property 7**: Generate `members` arrays with no `field_supervisor` entry → assert schema rejects with error on `members`
- **Property 8**: Generate valid `SiteAssignmentFormValues` objects → assert the constructed payload matches field-for-field

The Zod schemas (`addStaffSchema`, `siteAssignmentSchema`) are pure functions with no side effects, making them ideal candidates for property-based testing. The payload-mapping logic (Properties 4 and 8) is extracted into a pure `buildPayload(values)` helper function in each component file to make it independently testable.
