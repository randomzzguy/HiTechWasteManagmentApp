# Requirements Document

## Introduction

The Labour Forms feature activates two currently non-functional buttons on the `/labour` page of the Hi-Tech Waste Management Platform: **"Add Staff"** and **"Create Site Assignment"**. Each button opens a modal dialog containing a validated form. On successful submission the form calls the existing FastAPI backend endpoints (`POST /api/v1/labour/staff` and `POST /api/v1/labour/sites/assignments`), invalidates the relevant TanStack Query caches, and provides immediate user feedback via a Sonner toast. No new backend endpoints are required; all backend logic already exists.

This feature is high-priority for a client demo and must match the platform's dark slate UI theme (slate-950 background, slate-800 cards, emerald-500 accents) using shadcn/ui Dialog, Form, and Select primitives.

---

## Glossary

- **Add_Staff_Form**: The modal dialog rendered when the user clicks "Add Staff" on the Labour page.
- **Site_Assignment_Form**: The modal dialog rendered when the user clicks "Create Site Assignment" on the Labour page.
- **Labour_Page**: The Next.js page at `/labour` (`frontend/src/app/(dashboard)/labour/page.tsx`).
- **labourApi**: The domain API object in `frontend/src/lib/api.ts` that wraps all `/api/v1/labour/*` calls.
- **Staff_Profile**: A backend record (`staff_profiles` table) linking a platform user to employment metadata.
- **Site_Assignment**: A backend record (`site_assignments` table) linking a team of staff to a client site for a date range.
- **TanStack_Query**: The server-state library (v5) used for data fetching and cache invalidation.
- **Sonner**: The toast notification library used across the platform for success and error feedback.
- **shadcn_Dialog**: The `Dialog` / `DialogContent` component from shadcn/ui used to render modal overlays.
- **React_Hook_Form**: The form state management library used with `zodResolver` for schema validation.
- **Zod**: The TypeScript-first schema validation library used to define form schemas.

---

## Requirements

### Requirement 1: Add Staff Modal Trigger

**User Story:** As an operations manager, I want to click "Add Staff" and see a modal form, so that I can create a new staff profile without leaving the Labour page.

#### Acceptance Criteria

1. WHEN the user clicks the "Add Staff" button on the Labour_Page, THE Labour_Page SHALL open the Add_Staff_Form as a modal overlay using shadcn_Dialog.
2. WHEN the Add_Staff_Form is open, THE Labour_Page SHALL remain visible and interactive in the background behind the modal overlay.
3. WHEN the user presses the Escape key or clicks outside the Add_Staff_Form, THE Add_Staff_Form SHALL close without submitting data.
4. THE Add_Staff_Form SHALL render within the existing dark slate UI theme (slate-800 card background, emerald-500 primary action button).

---

### Requirement 2: Add Staff Form Fields and Validation

**User Story:** As an operations manager, I want the Add Staff form to collect all required staff profile fields with inline validation, so that I submit only valid data to the backend.

#### Acceptance Criteria

1. THE Add_Staff_Form SHALL include a required **User** selector that lists existing platform users from `GET /api/v1/settings/users/` and maps the selection to `user_id` (UUID).
2. THE Add_Staff_Form SHALL include a required **Employment Type** selector with exactly three options: `permanent`, `contract`, `foreign_worker`.
3. THE Add_Staff_Form SHALL include an optional **Labour Agent Name** text input with a maximum length of 200 characters.
4. THE Add_Staff_Form SHALL include an optional **Work Permit Expiry** date picker, enabled only when the selected employment type is `foreign_worker`.
5. THE Add_Staff_Form SHALL include an optional **Notes** textarea with no enforced maximum length.
6. WHEN the user submits the Add_Staff_Form with the **User** field empty, THE Add_Staff_Form SHALL display an inline validation error on the User field and SHALL NOT call `labourApi.createStaff`.
7. WHEN the user submits the Add_Staff_Form with the **Employment Type** field empty, THE Add_Staff_Form SHALL display an inline validation error on the Employment Type field and SHALL NOT call `labourApi.createStaff`.
8. WHEN the user selects an employment type other than `foreign_worker`, THE Add_Staff_Form SHALL hide the Work Permit Expiry field and SHALL clear any previously entered value.
9. WHEN the user enters a Labour Agent Name exceeding 200 characters, THE Add_Staff_Form SHALL display an inline validation error on that field and SHALL NOT call `labourApi.createStaff`.

---

### Requirement 3: Add Staff Form Submission

**User Story:** As an operations manager, I want the Add Staff form to submit to the backend and give me immediate feedback, so that I know whether the staff record was created successfully.

#### Acceptance Criteria

1. WHEN the user submits a valid Add_Staff_Form, THE Add_Staff_Form SHALL call `labourApi.createStaff` with the collected field values mapped to the `StaffProfileCreate` schema (`user_id`, `employment_type`, `labour_agent_name`, `work_permit_expiry`, `notes`).
2. WHEN `labourApi.createStaff` returns a successful response, THE Add_Staff_Form SHALL close the modal and THE Labour_Page SHALL display a Sonner success toast with the message "Staff profile created".
3. WHEN `labourApi.createStaff` returns a successful response, THE Labour_Page SHALL invalidate the `['staff']` TanStack_Query cache key so the staff table refreshes automatically.
4. WHEN `labourApi.createStaff` returns an HTTP 409 conflict error, THE Add_Staff_Form SHALL remain open and SHALL display a Sonner error toast with the message "A staff profile already exists for this user".
5. WHEN `labourApi.createStaff` returns any other HTTP error, THE Add_Staff_Form SHALL remain open and SHALL display a Sonner error toast containing the error message from the response body.
6. WHILE the Add_Staff_Form submission is in progress, THE Add_Staff_Form SHALL disable the submit button and display a loading indicator on it.

---

### Requirement 4: Create Site Assignment Modal Trigger

**User Story:** As an operations manager, I want to click "Create Site Assignment" and see a modal form, so that I can assign a team of staff to a client site without leaving the Labour page.

#### Acceptance Criteria

1. WHEN the user clicks the "Create Site Assignment" button on the Labour_Page, THE Labour_Page SHALL open the Site_Assignment_Form as a modal overlay using shadcn_Dialog.
2. WHEN the Site_Assignment_Form is open, THE Labour_Page SHALL remain visible and interactive in the background behind the modal overlay.
3. WHEN the user presses the Escape key or clicks outside the Site_Assignment_Form, THE Site_Assignment_Form SHALL close without submitting data.
4. THE Site_Assignment_Form SHALL render within the existing dark slate UI theme (slate-800 card background, emerald-500 primary action button).

---

### Requirement 5: Create Site Assignment Form Fields and Validation

**User Story:** As an operations manager, I want the Create Site Assignment form to collect all required assignment fields with inline validation, so that I submit only valid data to the backend.

#### Acceptance Criteria

1. THE Site_Assignment_Form SHALL include a required **Client** selector that lists active clients from `GET /api/v1/clients/` and maps the selection to `client_id` (UUID).
2. THE Site_Assignment_Form SHALL include a required **Site Address** text input with no enforced maximum length.
3. THE Site_Assignment_Form SHALL include a required **Supervisor** selector that lists available staff from `GET /api/v1/labour/staff` and maps the selection to `supervisor_id` (UUID).
4. THE Site_Assignment_Form SHALL include a required **Start Date** date picker that maps to `start_date` (ISO date string).
5. THE Site_Assignment_Form SHALL include an optional **End Date** date picker that maps to `end_date` (ISO date string).
6. THE Site_Assignment_Form SHALL include a required **Team Members** multi-select that lists available staff from `GET /api/v1/labour/staff` and collects one or more `{ staff_profile_id, role_at_site }` entries mapping to the `members` array.
7. THE Site_Assignment_Form SHALL include a required **Role at Site** selector per team member with the following options: `field_supervisor`, `waste_segregator`, `driver_assistant`, `general_worker`.
8. THE Site_Assignment_Form SHALL include an optional **Notes** textarea.
9. WHEN the user submits the Site_Assignment_Form with the **Client** field empty, THE Site_Assignment_Form SHALL display an inline validation error and SHALL NOT call `labourApi.createSiteAssignment`.
10. WHEN the user submits the Site_Assignment_Form with the **Site Address** field empty, THE Site_Assignment_Form SHALL display an inline validation error and SHALL NOT call `labourApi.createSiteAssignment`.
11. WHEN the user submits the Site_Assignment_Form with the **Supervisor** field empty, THE Site_Assignment_Form SHALL display an inline validation error and SHALL NOT call `labourApi.createSiteAssignment`.
12. WHEN the user submits the Site_Assignment_Form with the **Start Date** field empty, THE Site_Assignment_Form SHALL display an inline validation error and SHALL NOT call `labourApi.createSiteAssignment`.
13. WHEN the user submits the Site_Assignment_Form with no **Team Members** selected, THE Site_Assignment_Form SHALL display an inline validation error and SHALL NOT call `labourApi.createSiteAssignment`.
14. WHEN the user provides an **End Date** that is before the **Start Date**, THE Site_Assignment_Form SHALL display an inline validation error on the End Date field and SHALL NOT call `labourApi.createSiteAssignment`.
15. WHEN the user submits the Site_Assignment_Form and none of the selected team members has the role `field_supervisor`, THE Site_Assignment_Form SHALL display an inline validation error stating "At least one team member must have the role Field Supervisor" and SHALL NOT call `labourApi.createSiteAssignment`.

---

### Requirement 6: Create Site Assignment Form Submission

**User Story:** As an operations manager, I want the Create Site Assignment form to submit to the backend and give me immediate feedback, so that I know whether the assignment was created successfully.

#### Acceptance Criteria

1. WHEN the user submits a valid Site_Assignment_Form, THE Site_Assignment_Form SHALL call `labourApi.createSiteAssignment` with the collected field values mapped to the `SiteAssignmentCreate` schema (`client_id`, `site_address`, `supervisor_id`, `start_date`, `end_date`, `members`, `notes`).
2. WHEN `labourApi.createSiteAssignment` returns a successful response, THE Site_Assignment_Form SHALL close the modal and THE Labour_Page SHALL display a Sonner success toast with the message "Site assignment created".
3. WHEN `labourApi.createSiteAssignment` returns a successful response, THE Labour_Page SHALL invalidate the `['staff']` TanStack_Query cache key so updated staff statuses are reflected in the staff table.
4. WHEN `labourApi.createSiteAssignment` returns an HTTP 409 conflict error, THE Site_Assignment_Form SHALL remain open and SHALL display a Sonner error toast with the message from the response body (e.g. "Staff member X has overlapping assignment").
5. WHEN `labourApi.createSiteAssignment` returns any other HTTP error, THE Site_Assignment_Form SHALL remain open and SHALL display a Sonner error toast containing the error message from the response body.
6. WHILE the Site_Assignment_Form submission is in progress, THE Site_Assignment_Form SHALL disable the submit button and display a loading indicator on it.

---

### Requirement 7: Form Component Architecture

**User Story:** As a frontend developer, I want the two forms implemented as isolated, reusable components, so that they can be maintained and tested independently of the Labour page.

#### Acceptance Criteria

1. THE Add_Staff_Form SHALL be implemented as a standalone React component at `frontend/src/components/labour/AddStaffDialog.tsx`.
2. THE Site_Assignment_Form SHALL be implemented as a standalone React component at `frontend/src/components/labour/CreateSiteAssignmentDialog.tsx`.
3. THE Add_Staff_Form SHALL use React_Hook_Form with a Zod schema for all field validation logic.
4. THE Site_Assignment_Form SHALL use React_Hook_Form with a Zod schema for all field validation logic.
5. THE Add_Staff_Form SHALL accept an `onSuccess` callback prop that the Labour_Page uses to trigger cache invalidation and toast display.
6. THE Site_Assignment_Form SHALL accept an `onSuccess` callback prop that the Labour_Page uses to trigger cache invalidation and toast display.
7. THE Labour_Page SHALL wire the "Add Staff" button to control the open state of the Add_Staff_Form dialog.
8. THE Labour_Page SHALL wire the "Create Site Assignment" button to control the open state of the Site_Assignment_Form dialog.
