# Requirements Document

## Introduction

The Settings page of the Hi-Tech Waste Management Platform currently lists platform users but provides no way to create or modify them through the UI. The "Add User" button and per-row "Edit" button are both inert. This feature wires both buttons to modal dialog forms backed by new backend API endpoints, enabling `superadmin` and `management` users to create new platform accounts, update existing user details (including password resets), and deactivate users — all without leaving the Settings page.

## Glossary

- **Settings_Page**: The Next.js page at `/settings` that renders the Users tab.
- **User_Form**: A shadcn/ui `Dialog` containing a controlled form for creating or editing a platform user.
- **Add_User_Form**: The variant of User_Form opened by the "Add User" button; all fields are blank on open.
- **Edit_User_Form**: The variant of User_Form opened by a row's "Edit" button; fields are pre-populated with the selected user's current data.
- **Users_API**: The FastAPI router at `backend/routers/settings.py` that handles user management endpoints under `/api/v1/settings/users/`.
- **User**: A record in the `users` PostgreSQL table, represented by the `User` SQLAlchemy model in `backend/models/user.py`.
- **Role**: One of the seven fixed string values that control access: `superadmin`, `management`, `operations_manager`, `field_supervisor`, `driver`, `compliance_officer`, `client`.
- **Admin_User**: A currently authenticated user whose `role` is `superadmin` or `management`.
- **Password_Hash**: The bcrypt-hashed representation of a plain-text password, produced by `hash_password()` in `backend/routers/auth.py`.
- **TanStack_Query**: The server-state library (v5) used in the frontend for data fetching, caching, and cache invalidation.
- **Sonner**: The toast notification library used for success and error feedback.

---

## Requirements

### Requirement 1: Add User Button Opens a Creation Form

**User Story:** As an Admin_User, I want to click "Add User" and fill in a form, so that I can create new platform accounts without using the database directly.

#### Acceptance Criteria

1. WHEN an Admin_User clicks the "Add User" button on the Settings_Page Users tab, THE Settings_Page SHALL open the Add_User_Form in a modal dialog.
2. THE Add_User_Form SHALL contain the following fields: Full Name (text, required), Email (email, required), Password (password, required), Role (select, required), and Active status (checkbox, default checked).
3. THE Add_User_Form SHALL populate the Role select with all seven valid Role values: `superadmin`, `management`, `operations_manager`, `field_supervisor`, `driver`, `compliance_officer`, `client`.
4. WHEN the Add_User_Form is opened, THE Add_User_Form SHALL set focus to the Full Name field.
5. WHEN an Admin_User submits the Add_User_Form with all required fields valid, THE Add_User_Form SHALL call `settingsApi.createUser()` with the form data.
6. WHEN `settingsApi.createUser()` succeeds, THE Settings_Page SHALL close the Add_User_Form, display a Sonner success toast, and invalidate the `['settings', 'users']` TanStack_Query cache key to refresh the user list.
7. IF `settingsApi.createUser()` returns an error, THEN THE Add_User_Form SHALL remain open and display a Sonner error toast containing the error message returned by the Users_API.
8. WHEN an Admin_User clicks the Cancel button or presses Escape, THE Add_User_Form SHALL close without submitting and without modifying any data.

---

### Requirement 2: Edit Button Opens a Pre-Populated Edit Form

**User Story:** As an Admin_User, I want to click "Edit" on a user row and update that user's details, so that I can correct information or change a user's role without recreating the account.

#### Acceptance Criteria

1. WHEN an Admin_User clicks the "Edit" button on a user row, THE Settings_Page SHALL open the Edit_User_Form in a modal dialog pre-populated with that user's `full_name`, `email`, `role`, and `is_active` values.
2. THE Edit_User_Form SHALL contain the same fields as the Add_User_Form, except the Password field SHALL be optional and labelled "New Password (leave blank to keep current)".
3. WHEN an Admin_User submits the Edit_User_Form, THE Edit_User_Form SHALL call `settingsApi.updateUser(id, data)` with only the fields that have changed, omitting the password field if it is blank.
4. WHEN `settingsApi.updateUser()` succeeds, THE Settings_Page SHALL close the Edit_User_Form, display a Sonner success toast, and invalidate the `['settings', 'users']` TanStack_Query cache key.
5. IF `settingsApi.updateUser()` returns an error, THEN THE Edit_User_Form SHALL remain open and display a Sonner error toast containing the error message returned by the Users_API.
6. WHEN an Admin_User clicks the Cancel button or presses Escape, THE Edit_User_Form SHALL close without submitting.

---

### Requirement 3: Deactivate User Action

**User Story:** As an Admin_User, I want to deactivate a user from the Edit form, so that I can revoke access without permanently deleting the account.

#### Acceptance Criteria

1. WHERE the selected user's `is_active` is `true`, THE Edit_User_Form SHALL display a "Deactivate User" button styled as a destructive action (red).
2. WHEN an Admin_User clicks "Deactivate User", THE Edit_User_Form SHALL display an inline confirmation prompt before proceeding.
3. WHEN the Admin_User confirms deactivation, THE Edit_User_Form SHALL call `settingsApi.deactivateUser(id)`.
4. WHEN `settingsApi.deactivateUser()` succeeds, THE Settings_Page SHALL close the Edit_User_Form, display a Sonner success toast, and invalidate the `['settings', 'users']` TanStack_Query cache key.
5. IF `settingsApi.deactivateUser()` returns an error, THEN THE Edit_User_Form SHALL display a Sonner error toast and remain open.
6. WHERE the selected user's `is_active` is `false`, THE Edit_User_Form SHALL NOT display the "Deactivate User" button.

---

### Requirement 4: Client-Side Form Validation

**User Story:** As an Admin_User, I want the form to catch obvious mistakes before submission, so that I receive immediate feedback without a round-trip to the server.

#### Acceptance Criteria

1. WHEN an Admin_User attempts to submit the Add_User_Form with the Full Name field empty, THE Add_User_Form SHALL display an inline validation error on that field and SHALL NOT submit.
2. WHEN an Admin_User attempts to submit the Add_User_Form with an Email value that does not match the RFC 5322 email format, THE Add_User_Form SHALL display an inline validation error on the Email field and SHALL NOT submit.
3. WHEN an Admin_User attempts to submit the Add_User_Form with a Password shorter than 8 characters, THE Add_User_Form SHALL display an inline validation error on the Password field and SHALL NOT submit.
4. WHEN an Admin_User attempts to submit the Add_User_Form without selecting a Role, THE Add_User_Form SHALL display an inline validation error on the Role field and SHALL NOT submit.
5. WHEN an Admin_User enters a New Password in the Edit_User_Form that is shorter than 8 characters, THE Edit_User_Form SHALL display an inline validation error on the Password field and SHALL NOT submit.
6. WHILE a form submission is in progress, THE User_Form SHALL disable all input fields and the submit button to prevent duplicate submissions.

---

### Requirement 5: Backend — Create User Endpoint

**User Story:** As an Admin_User, I want the platform to persist new user accounts securely, so that new users can log in immediately after creation.

#### Acceptance Criteria

1. WHEN a `POST /api/v1/settings/users/` request is received with a valid `UserCreate` payload, THE Users_API SHALL hash the plain-text password using `hash_password()` and insert a new `User` record into the database.
2. WHEN the `POST /api/v1/settings/users/` request succeeds, THE Users_API SHALL return a `201 Created` response containing the new user's data serialised as `UserRead` (excluding `hashed_password`).
3. IF the `email` in the `POST /api/v1/settings/users/` request already exists in the database, THEN THE Users_API SHALL return a `409 Conflict` response with a descriptive error message.
4. IF the `role` in the `POST /api/v1/settings/users/` request is not one of the seven valid Role values, THEN THE Users_API SHALL return a `422 Unprocessable Entity` response.
5. IF the caller's JWT does not belong to an Admin_User, THEN THE Users_API SHALL return a `403 Forbidden` response for `POST /api/v1/settings/users/`.

---

### Requirement 6: Backend — Update User Endpoint

**User Story:** As an Admin_User, I want partial updates to user records to be applied atomically, so that only the fields I change are modified.

#### Acceptance Criteria

1. WHEN a `PATCH /api/v1/settings/users/{id}/` request is received with a valid `UserUpdate` payload, THE Users_API SHALL apply only the non-null fields from the payload to the matching `User` record.
2. WHEN the `UserUpdate` payload includes a `password` field, THE Users_API SHALL hash the new password using `hash_password()` before storing it, replacing the existing `hashed_password`.
3. WHEN the `PATCH /api/v1/settings/users/{id}/` request succeeds, THE Users_API SHALL return a `200 OK` response containing the updated user serialised as `UserRead`.
4. IF the `{id}` in the `PATCH /api/v1/settings/users/{id}/` path does not match any `User` record, THEN THE Users_API SHALL return a `404 Not Found` response.
5. IF the `role` in the `UserUpdate` payload is not one of the seven valid Role values, THEN THE Users_API SHALL return a `422 Unprocessable Entity` response.
6. IF the caller's JWT does not belong to an Admin_User, THEN THE Users_API SHALL return a `403 Forbidden` response for `PATCH /api/v1/settings/users/{id}/`.

---

### Requirement 7: Backend — Deactivate User Endpoint

**User Story:** As an Admin_User, I want a dedicated deactivate endpoint, so that revoking access is an explicit, auditable action separate from general edits.

#### Acceptance Criteria

1. WHEN a `POST /api/v1/settings/users/{id}/deactivate/` request is received, THE Users_API SHALL set the matching `User` record's `is_active` field to `false`.
2. WHEN the `POST /api/v1/settings/users/{id}/deactivate/` request succeeds, THE Users_API SHALL return a `200 OK` response containing the updated user serialised as `UserRead`.
3. IF the `{id}` in the `POST /api/v1/settings/users/{id}/deactivate/` path does not match any `User` record, THEN THE Users_API SHALL return a `404 Not Found` response.
4. IF the caller's JWT does not belong to an Admin_User, THEN THE Users_API SHALL return a `403 Forbidden` response for `POST /api/v1/settings/users/{id}/deactivate/`.
5. IF the target `User` record's `is_active` is already `false`, THEN THE Users_API SHALL still return a `200 OK` response (idempotent operation).

---

### Requirement 8: Access Control — UI Visibility

**User Story:** As a non-admin user, I want the user management controls to be hidden from me, so that I cannot accidentally trigger actions I am not authorised to perform.

#### Acceptance Criteria

1. WHILE the authenticated user's role is NOT `superadmin` or `management`, THE Settings_Page SHALL NOT render the "Add User" button.
2. WHILE the authenticated user's role is NOT `superadmin` or `management`, THE Settings_Page SHALL NOT render the "Edit" button on any user row.
3. THE Settings_Page SHALL derive the Admin_User check from the NextAuth session `role` field, not from a separate API call.
