# Design Document — Settings User Management

## Overview

This feature wires the inert "Add User" and "Edit" buttons on the Settings page to a shared `UserFormDialog` modal component, backed by three new FastAPI endpoints. The design reuses existing patterns throughout the codebase: `require_roles()` for access control, `hash_password()` for credential security, TanStack Query v5 for cache invalidation, and Sonner for toast feedback.

The core idea is a single `UserFormDialog` component that operates in two modes — `create` and `edit` — controlled by a `mode` prop and an optional `user` prop. This avoids duplicating form logic while keeping the two variants visually and behaviourally distinct where the requirements differ (optional password, deactivate button).

---

## Architecture

```
Settings Page (page.tsx)
  │
  ├── [Add User button] ──────────────────────────────────────────┐
  │                                                               ▼
  └── [Edit button per row] ──────────────────────────────► UserFormDialog
                                                              (mode: create | edit)
                                                                   │
                                                    ┌──────────────┼──────────────┐
                                                    ▼              ▼              ▼
                                             createUser()   updateUser()  deactivateUser()
                                                    │              │              │
                                                    └──────────────┴──────────────┘
                                                                   │
                                                         FastAPI Settings Router
                                                                   │
                                                    ┌──────────────┼──────────────┐
                                                    ▼              ▼              ▼
                                          POST /users/   PATCH /users/{id}/  POST /users/{id}/deactivate/
                                                    │              │              │
                                                    └──────────────┴──────────────┘
                                                                   │
                                                          PostgreSQL users table
```

**Data flow for create:**
1. Admin clicks "Add User" → `setDialogState({ open: true, mode: 'create', user: null })`
2. `UserFormDialog` renders with blank fields
3. On submit → `settingsApi.createUser(data)` → `POST /api/v1/settings/users/`
4. Backend hashes password, inserts row, returns `UserRead`
5. On success → close dialog, `toast.success(...)`, `queryClient.invalidateQueries(['settings', 'users'])`

**Data flow for edit:**
1. Admin clicks "Edit" on row → `setDialogState({ open: true, mode: 'edit', user: rowData })`
2. `UserFormDialog` renders pre-populated; password field is optional
3. On submit → diff against original, call `settingsApi.updateUser(id, changedFields)`
4. Backend applies partial update, returns `UserRead`
5. On success → same close/toast/invalidate pattern

---

## Components and Interfaces

### `UserFormDialog` (`frontend/src/components/settings/UserFormDialog.tsx`)

```typescript
interface UserFormDialogProps {
  mode: 'create' | 'edit'
  user?: UserRow | null          // pre-populate in edit mode
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void          // called after successful mutation; parent invalidates cache
}

interface UserRow {
  id: string
  email: string
  full_name: string
  role: string
  is_active: boolean
  created_at: string
}
```

**Internal state:**
- `useForm` (react-hook-form) with Zod resolver for validation
- `confirmDeactivate: boolean` — controls inline deactivation confirmation
- `isPending` — derived from mutation `.isPending`; disables all inputs + submit

**Form fields:**

| Field | Type | Required | Validation |
|---|---|---|---|
| `full_name` | text input | always | non-empty after trim |
| `email` | email input | always | RFC 5322 via Zod `z.string().email()` |
| `password` | password input | create only | min 8 chars; optional in edit |
| `role` | shadcn Select | always | one of 7 valid roles |
| `is_active` | shadcn Checkbox | always | boolean, default true |

**Deactivate button:** rendered only in edit mode when `user.is_active === true`. On first click sets `confirmDeactivate = true` and shows an inline "Are you sure?" prompt with Confirm/Cancel. On confirm calls `deactivateUser`.

**Mutations used:**
- `useMutation` wrapping `settingsApi.createUser` (create mode)
- `useMutation` wrapping `settingsApi.updateUser` (edit mode)
- `useMutation` wrapping `settingsApi.deactivateUser` (edit mode, deactivate path)

All three share the same `onSuccess` / `onError` pattern:
- `onSuccess`: call `onSuccess()` prop (parent invalidates), `toast.success(...)`, close dialog
- `onError`: `toast.error(err.response?.data?.detail ?? 'An error occurred')`

### Settings Page changes (`frontend/src/app/(dashboard)/settings/page.tsx`)

Add dialog state:
```typescript
const [dialogState, setDialogState] = useState<{
  open: boolean
  mode: 'create' | 'edit'
  user: UserRow | null
}>({ open: false, mode: 'create', user: null })
```

Wire "Add User" button:
```tsx
onClick={() => setDialogState({ open: true, mode: 'create', user: null })}
```

Wire "Edit" button per row:
```tsx
onClick={() => setDialogState({ open: true, mode: 'edit', user: u })}
```

Render `UserFormDialog` at the bottom of the Users tab section, passing `onSuccess` as:
```typescript
() => queryClient.invalidateQueries({ queryKey: ['settings', 'users'] })
```

---

## Data Models

### Pydantic Schemas (in `backend/models/user.py` — already defined)

`UserCreate`, `UserUpdate`, and `UserRead` are already present in `backend/models/user.py`. The backend endpoints will import them from there. No new schema files are needed.

Key points:
- `UserCreate.password` — plain text, min 8 chars; hashed before storage
- `UserUpdate` — all fields optional; `password` optional, min 8 chars if provided
- `UserRead` — excludes `hashed_password`; includes `id`, `email`, `full_name`, `role`, `is_active`, `created_at`
- Role validation via `VALID_ROLES` set (already defined in `models/user.py`)

### Frontend TypeScript types

```typescript
// Zod schema for create form
const createUserSchema = z.object({
  full_name: z.string().min(1, 'Full name is required').trim(),
  email: z.string().email('Invalid email address'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
  role: z.enum(['superadmin', 'management', 'operations_manager',
                'field_supervisor', 'driver', 'compliance_officer', 'client']),
  is_active: z.boolean().default(true),
})

// Zod schema for edit form (password optional)
const editUserSchema = createUserSchema.extend({
  password: z.string().min(8, 'Password must be at least 8 characters').optional().or(z.literal('')),
})
```

### Backend — New Endpoints

Three new endpoints added to `backend/routers/settings.py`:

**`POST /api/v1/settings/users/`**
- Auth: `require_roles("superadmin", "management")`
- Body: `UserCreate`
- Hashes password via `hash_password()`
- Checks email uniqueness; raises `409` if duplicate
- Inserts via SQLAlchemy ORM
- Returns `UserRead`, status `201`

**`PATCH /api/v1/settings/users/{id}/`**
- Auth: `require_roles("superadmin", "management")`
- Body: `UserUpdate`
- Fetches user by UUID; raises `404` if not found
- Applies only non-`None` fields; hashes password if provided
- Returns `UserRead`, status `200`

**`POST /api/v1/settings/users/{id}/deactivate/`**
- Auth: `require_roles("superadmin", "management")`
- Fetches user by UUID; raises `404` if not found
- Sets `is_active = False` (idempotent — no error if already false)
- Returns `UserRead`, status `200`

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Form submission sends all valid user data

*For any* valid combination of full name, email, password (≥8 chars), role, and active status, submitting the Add User form should result in `settingsApi.createUser` being called with a payload that exactly matches the entered values.

**Validates: Requirements 1.5**

---

### Property 2: Edit form pre-population round-trip

*For any* user record, opening the Edit form for that user should pre-populate all form fields (full_name, email, role, is_active) with values that match the user record.

**Validates: Requirements 2.1**

---

### Property 3: Partial update sends only changed fields

*For any* user record and any non-empty subset of editable fields that differ from the original values, submitting the Edit form should call `settingsApi.updateUser` with a payload containing exactly those changed fields — no more, no less — and should omit the password field when it is left blank.

**Validates: Requirements 2.3**

---

### Property 4: Empty/whitespace names are rejected client-side

*For any* string composed entirely of whitespace characters (including the empty string), attempting to submit the Add User form with that value in the Full Name field should display an inline validation error and should not call `settingsApi.createUser`.

**Validates: Requirements 4.1**

---

### Property 5: Invalid email formats are rejected client-side

*For any* string that does not conform to a valid email format (missing `@`, missing domain, etc.), attempting to submit the Add User form with that value in the Email field should display an inline validation error and should not call `settingsApi.createUser`.

**Validates: Requirements 4.2**

---

### Property 6: Short passwords are rejected client-side

*For any* password string of length 0–7, attempting to submit the Add User form (or the Edit form when a new password is entered) should display an inline validation error and should not call the relevant API method.

**Validates: Requirements 4.3, 4.5**

---

### Property 7: Backend create stores hashed password and returns safe UserRead

*For any* valid `UserCreate` payload, the `POST /users/` endpoint should store a `hashed_password` that is not equal to the plain-text password, and the response body should contain `id`, `email`, `full_name`, `role`, `is_active`, `created_at` but must not contain `hashed_password`.

**Validates: Requirements 5.1, 5.2**

---

### Property 8: Backend partial update applies only provided fields

*For any* existing user and any `UserUpdate` payload with a non-empty subset of fields set to non-`None` values, the `PATCH /users/{id}/` endpoint should update exactly those fields in the database and leave all other fields unchanged.

**Validates: Requirements 6.1**

---

### Property 9: Backend password update stores new bcrypt hash

*For any* `UserUpdate` payload that includes a `password` field, the stored `hashed_password` after the PATCH should verify correctly against the new plain-text password (using `verify_password`) and should differ from the previous `hashed_password`.

**Validates: Requirements 6.2**

---

### Property 10: Deactivation is idempotent

*For any* user record (whether currently active or inactive), calling `POST /users/{id}/deactivate/` should always result in `is_active = false` and return `200 OK` — calling it a second time should produce the same outcome as calling it once.

**Validates: Requirements 7.1, 7.5**

---

## Error Handling

### Frontend

| Scenario | Behaviour |
|---|---|
| API returns `409 Conflict` (duplicate email) | `toast.error("A user with this email already exists.")` — dialog stays open |
| API returns `422 Unprocessable Entity` | `toast.error(detail)` — dialog stays open |
| API returns `403 Forbidden` | `toast.error("You do not have permission to perform this action.")` |
| Network error / timeout | `toast.error("Request failed. Please try again.")` |
| Submission in progress | All inputs + submit button disabled; submit button shows spinner |

Error messages are extracted from `err.response?.data?.detail` (FastAPI's default error envelope field). If absent, a generic fallback is shown.

### Backend

| Scenario | HTTP Status | Detail |
|---|---|---|
| Duplicate email on create | `409 Conflict` | `"A user with email '{email}' already exists."` |
| Invalid role value | `422 Unprocessable Entity` | Pydantic validation error (automatic) |
| User ID not found | `404 Not Found` | `"User '{id}' not found."` |
| Caller not admin | `403 Forbidden` | Raised by `require_roles()` dependency |
| Missing/invalid JWT | `401 Unauthorized` | Raised by `get_current_user()` dependency |

---

## Testing Strategy

### Unit / Component Tests (Vitest + React Testing Library)

Focus on concrete examples and edge cases:

- `UserFormDialog` renders correct fields in create vs edit mode
- Role select contains all seven valid options
- Deactivate button visible only when `is_active === true`
- Cancel / Escape closes dialog without calling any API method
- Success path: dialog closes, `onSuccess` called
- Error path: dialog stays open, error toast shown
- Loading state: inputs and submit button disabled during mutation

### Property-Based Tests (fast-check, minimum 100 iterations each)

Use `fast-check` for the frontend properties and `hypothesis` for the backend properties.

**Frontend (fast-check):**

- **Property 1** — `fc.record({ full_name: fc.string({ minLength: 1 }), email: fc.emailAddress(), password: fc.string({ minLength: 8 }), role: fc.constantFrom(...VALID_ROLES), is_active: fc.boolean() })` → assert `createUser` called with matching payload.
  Tag: `Feature: settings-user-management, Property 1: form submission sends all valid user data`

- **Property 2** — `fc.record({ id: fc.uuid(), full_name: fc.string({ minLength: 1 }), email: fc.emailAddress(), role: fc.constantFrom(...VALID_ROLES), is_active: fc.boolean(), created_at: fc.date().map(d => d.toISOString()) })` → open edit dialog, assert each field matches.
  Tag: `Feature: settings-user-management, Property 2: edit form pre-population round-trip`

- **Property 3** — Generate user + random subset of changed fields → submit → assert `updateUser` payload matches changed fields only.
  Tag: `Feature: settings-user-management, Property 3: partial update sends only changed fields`

- **Property 4** — `fc.string().filter(s => s.trim() === '')` → submit → assert inline error, `createUser` not called.
  Tag: `Feature: settings-user-management, Property 4: empty/whitespace names rejected`

- **Property 5** — `fc.string().filter(s => !isValidEmail(s))` → submit → assert inline error, `createUser` not called.
  Tag: `Feature: settings-user-management, Property 5: invalid email formats rejected`

- **Property 6** — `fc.string({ maxLength: 7 })` → submit → assert inline error, API not called.
  Tag: `Feature: settings-user-management, Property 6: short passwords rejected`

**Backend (hypothesis + pytest-asyncio):**

- **Property 7** — `@given(st.builds(UserCreate, ...))` → POST → assert `hashed_password` not in response, `verify_password(plain, stored_hash)` is True.
  Tag: `Feature: settings-user-management, Property 7: backend create stores hashed password`

- **Property 8** — `@given(existing_user, st.builds(UserUpdate, ...))` → PATCH → assert only provided fields changed.
  Tag: `Feature: settings-user-management, Property 8: backend partial update applies only provided fields`

- **Property 9** — `@given(existing_user, st.text(min_size=8))` → PATCH with password → assert new hash verifies against new plain text.
  Tag: `Feature: settings-user-management, Property 9: backend password update stores new bcrypt hash`

- **Property 10** — `@given(existing_user)` → deactivate twice → assert both return 200 and `is_active=false`.
  Tag: `Feature: settings-user-management, Property 10: deactivation is idempotent`

### Integration Tests

- `POST /users/` with duplicate email returns `409`
- `POST /users/` with invalid role returns `422`
- `PATCH /users/{id}/` with unknown UUID returns `404`
- `POST /users/{id}/deactivate/` with unknown UUID returns `404`
- All three endpoints return `403` when called with a non-admin JWT
