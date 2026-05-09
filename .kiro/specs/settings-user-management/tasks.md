# Implementation Plan: Settings User Management

## Overview

Wire the inert "Add User" and "Edit" buttons on the Settings page to a shared `UserFormDialog` component, backed by three new FastAPI endpoints for creating, updating, and deactivating users. The implementation follows existing codebase patterns: `require_roles()` for access control, `hash_password()` for credential security, TanStack Query v5 for cache invalidation, and Sonner for toast feedback.

## Tasks

- [x] 1. Add backend user management endpoints to `backend/routers/settings.py`
  - [x] 1.1 Implement `POST /api/v1/settings/users/` — create user endpoint
    - Import `UserCreate`, `UserRead` from `backend/models/user.py` and `require_roles`, `hash_password` from `backend/routers/auth.py`
    - Add `require_roles("superadmin", "management")` dependency
    - Hash the plain-text password via `hash_password()` before inserting
    - Check email uniqueness with a `SELECT` before insert; raise `409 Conflict` with message `"A user with email '{email}' already exists."` if duplicate found
    - Insert new `User` ORM instance via `db.add()` + `await db.commit()` + `await db.refresh()`
    - Return `UserRead.model_validate(user)` with `status_code=201`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x] 1.2 Implement `PATCH /api/v1/settings/users/{id}/` — partial update endpoint
    - Accept `id: uuid.UUID` path parameter and `UserUpdate` body
    - Fetch user by primary key; raise `404 Not Found` with `"User '{id}' not found."` if absent
    - Iterate over `payload.model_dump(exclude_none=True)` and apply only non-`None` fields to the ORM instance
    - If `password` key is present in the update dict, call `hash_password()` and store result in `hashed_password`; remove `password` from the dict before applying other fields
    - Commit, refresh, and return `UserRead.model_validate(user)` with `status_code=200`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [x] 1.3 Implement `POST /api/v1/settings/users/{id}/deactivate/` — deactivate endpoint
    - Accept `id: uuid.UUID` path parameter
    - Fetch user by primary key; raise `404 Not Found` if absent
    - Set `user.is_active = False` unconditionally (idempotent — no error if already false)
    - Commit, refresh, and return `UserRead.model_validate(user)` with `status_code=200`
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 2. Add `settingsApi` client methods in `frontend/src/lib/api.ts`
  - Add `createUser(data)` → `POST /api/v1/settings/users/`
  - Add `updateUser(id, data)` → `PATCH /api/v1/settings/users/{id}/`
  - Add `deactivateUser(id)` → `POST /api/v1/settings/users/{id}/deactivate/`
  - Follow the existing Axios instance pattern used by other domain API objects in `api.ts`
  - _Requirements: 1.5, 2.3, 3.3_

- [x] 3. Create `frontend/src/components/settings/UserFormDialog.tsx`
  - [x] 3.1 Scaffold the component with props interface and Zod schemas
    - Define `UserFormDialogProps` interface: `mode`, `user`, `open`, `onOpenChange`, `onSuccess`
    - Define `UserRow` interface matching the shape returned by `settingsApi.listUsers`
    - Define `createUserSchema` (all fields required, password min 8)
    - Define `editUserSchema` extending create schema with password optional or empty string
    - _Requirements: 1.2, 1.3, 2.2, 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x] 3.2 Implement form fields and layout inside a shadcn `Dialog`
    - Use `useForm` with `zodResolver`; default values from `user` prop in edit mode, blank in create mode
    - Render Full Name (text), Email (email), Password (password, labelled "New Password (leave blank to keep current)" in edit mode), Role (shadcn `Select` with all 7 roles), Active status (shadcn `Checkbox`)
    - Set `autoFocus` on the Full Name field so it receives focus on open (Requirement 1.4)
    - Display inline `FormMessage` under each field for Zod validation errors
    - _Requirements: 1.2, 1.3, 1.4, 2.1, 2.2, 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x] 3.3 Wire create and edit mutations with loading and error handling
    - `useMutation` wrapping `settingsApi.createUser` for create mode
    - `useMutation` wrapping `settingsApi.updateUser` for edit mode; diff form values against original `user` prop and send only changed fields; omit `password` if blank
    - `onSuccess`: call `onSuccess()` prop, `toast.success(...)`, call `onOpenChange(false)`
    - `onError`: `toast.error(err?.response?.data?.detail ?? 'An error occurred')`
    - Derive `isPending` from active mutation; disable all inputs and submit button while pending; show spinner on submit button
    - _Requirements: 1.5, 1.6, 1.7, 2.3, 2.4, 2.5, 4.6_

  - [x] 3.4 Implement deactivate action with inline confirmation
    - Render "Deactivate User" button only in edit mode when `user.is_active === true`
    - Style as destructive (red variant)
    - On first click set `confirmDeactivate = true` and render inline "Are you sure?" prompt with Confirm and Cancel buttons
    - On confirm: call `settingsApi.deactivateUser(user.id)` via a third `useMutation`; on success call `onSuccess()`, `toast.success(...)`, `onOpenChange(false)`; on error `toast.error(...)`
    - On cancel: reset `confirmDeactivate = false`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [x] 4. Update `frontend/src/app/(dashboard)/settings/page.tsx` to wire the dialog
  - Add `useQueryClient` import and instantiate it
  - Add `dialogState` state: `{ open: boolean, mode: 'create' | 'edit', user: UserRow | null }`
  - Wire "Add User" button `onClick` to `setDialogState({ open: true, mode: 'create', user: null })`
  - Wire each row's "Edit" button `onClick` to `setDialogState({ open: true, mode: 'edit', user: u })`
  - Render `<UserFormDialog>` at the bottom of the Users tab section with `onSuccess` calling `queryClient.invalidateQueries({ queryKey: ['settings', 'users'] })`
  - _Requirements: 1.1, 1.6, 2.1, 2.4, 3.4, 8.1, 8.2, 8.3_

- [x] 5. Checkpoint — verify backend and frontend wiring
  - Ensure all TypeScript types compile without errors
  - Ensure all three backend endpoints are reachable and return correct status codes for happy-path requests
  - Ask the user if any questions arise before proceeding to tests.

- [x] 6. Write property-based and integration tests for the backend
  - [x] 6.1 Create `backend/tests/test_settings_users.py` with pytest + hypothesis setup
    - Set up async test client fixture using `httpx.AsyncClient` with the FastAPI app
    - Create helper fixtures for admin JWT token and a seeded test user
    - _Requirements: 5.1, 6.1, 7.1_

  - [ ]* 6.2 Write property test for backend create — Property 7
    - **Property 7: Backend create stores hashed password and returns safe UserRead**
    - Use `@given(st.builds(UserCreate, email=st.emails(), password=st.text(min_size=8), full_name=st.text(min_size=1), role=st.sampled_from(list(VALID_ROLES)), is_active=st.booleans()))`
    - POST to `/api/v1/settings/users/` with admin token; assert `hashed_password` absent from response body; assert `verify_password(plain, stored_hash)` is `True` by querying DB directly
    - **Validates: Requirements 5.1, 5.2**

  - [ ]* 6.3 Write property test for backend partial update — Property 8
    - **Property 8: Backend partial update applies only provided fields**
    - Use `@given(st.fixed_dictionaries({...}))` generating a non-empty subset of `UserUpdate` fields
    - PATCH existing user; assert only provided fields changed in DB; assert all other fields match pre-patch snapshot
    - **Validates: Requirements 6.1**

  - [ ]* 6.4 Write property test for backend password update — Property 9
    - **Property 9: Backend password update stores new bcrypt hash**
    - Use `@given(st.text(min_size=8))` for new password
    - PATCH existing user with new password; assert stored hash differs from previous hash; assert `verify_password(new_plain, new_hash)` is `True`
    - **Validates: Requirements 6.2**

  - [ ]* 6.5 Write property test for deactivation idempotency — Property 10
    - **Property 10: Deactivation is idempotent**
    - Use `@given(st.booleans())` to seed user as active or already inactive
    - Call `POST /users/{id}/deactivate/` twice; assert both responses are `200` and `is_active` is `false`
    - **Validates: Requirements 7.1, 7.5**

  - [ ]* 6.6 Write integration tests for error cases
    - `POST /users/` with duplicate email → assert `409`
    - `POST /users/` with invalid role → assert `422`
    - `PATCH /users/{id}/` with unknown UUID → assert `404`
    - `POST /users/{id}/deactivate/` with unknown UUID → assert `404`
    - All three endpoints with non-admin JWT → assert `403`
    - _Requirements: 5.3, 5.4, 5.5, 6.4, 6.6, 7.3, 7.4_

- [x] 7. Write property-based and unit tests for the frontend
  - [x] 7.1 Create `frontend/src/components/settings/__tests__/UserFormDialog.test.tsx` with Vitest + RTL setup
    - Mock `settingsApi.createUser`, `settingsApi.updateUser`, `settingsApi.deactivateUser`
    - Wrap renders in `QueryClientProvider` and `SessionProvider`
    - _Requirements: 1.1, 2.1, 3.1_

  - [ ]* 7.2 Write property test for form submission payload — Property 1
    - **Property 1: Form submission sends all valid user data**
    - Use `fc.record({ full_name: fc.string({ minLength: 1 }), email: fc.emailAddress(), password: fc.string({ minLength: 8 }), role: fc.constantFrom(...VALID_ROLES), is_active: fc.boolean() })`
    - Fill form fields, submit, assert `createUser` called with payload matching generated values
    - **Validates: Requirements 1.5**

  - [ ]* 7.3 Write property test for edit form pre-population — Property 2
    - **Property 2: Edit form pre-population round-trip**
    - Use `fc.record({ id: fc.uuid(), full_name: fc.string({ minLength: 1 }), email: fc.emailAddress(), role: fc.constantFrom(...VALID_ROLES), is_active: fc.boolean(), created_at: fc.date().map(d => d.toISOString()) })`
    - Open dialog in edit mode with generated user; assert each field's displayed value matches the user record
    - **Validates: Requirements 2.1**

  - [ ]* 7.4 Write property test for partial update payload — Property 3
    - **Property 3: Partial update sends only changed fields**
    - Generate a base user and a random non-empty subset of changed fields; fill only those fields; submit; assert `updateUser` called with exactly those changed fields and no password key when password left blank
    - **Validates: Requirements 2.3**

  - [ ]* 7.5 Write property test for whitespace name rejection — Property 4
    - **Property 4: Empty/whitespace names are rejected client-side**
    - Use `fc.string().filter(s => s.trim() === '')`
    - Fill Full Name with generated whitespace string; attempt submit; assert inline validation error visible; assert `createUser` not called
    - **Validates: Requirements 4.1**

  - [ ]* 7.6 Write property test for invalid email rejection — Property 5
    - **Property 5: Invalid email formats are rejected client-side**
    - Use `fc.string().filter(s => !isValidEmail(s))`
    - Fill Email with generated invalid string; attempt submit; assert inline validation error; assert `createUser` not called
    - **Validates: Requirements 4.2**

  - [ ]* 7.7 Write property test for short password rejection — Property 6
    - **Property 6: Short passwords are rejected client-side**
    - Use `fc.string({ maxLength: 7 })`
    - Fill Password with generated short string; attempt submit; assert inline validation error; assert API not called
    - **Validates: Requirements 4.3, 4.5**

  - [ ]* 7.8 Write unit tests for component behaviour
    - Deactivate button visible only when `is_active === true` in edit mode
    - Cancel button and Escape key close dialog without calling any API method
    - All inputs and submit button disabled while mutation is pending
    - Error toast shown and dialog stays open when API returns an error
    - _Requirements: 1.8, 2.6, 3.2, 3.6, 4.6_

- [x] 8. Final checkpoint — ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- Property tests validate universal correctness properties (Properties 1–10 from design doc)
- Unit/integration tests validate specific examples and error conditions
- The `require_roles` and `hash_password` helpers are imported from `backend/routers/auth.py`
- Pydantic schemas (`UserCreate`, `UserUpdate`, `UserRead`, `VALID_ROLES`) are already defined in `backend/models/user.py` — no new schema files needed
