# Implementation Plan: Operational Field Management

## Overview

All five sub-systems (Compaction Equipment, Container Logistics, Labour Deployment, Disruption Log, Recycler Delivery) have their SQLAlchemy ORM models, FastAPI routers, frontend pages, TypeScript types, and API client methods already scaffolded. The remaining work is:

1. **Alembic migration** — create the new tables in the database
2. **AuditLog model + session event hook** — implement the cross-cutting audit trail
3. **`detect_no_checkout` Celery task** — the fourth scheduled task is missing
4. **Backend router completions** — several endpoints have gaps (status validation, notification broadcasts, audit writes, RBAC on remaining endpoints)
5. **Frontend page completions** — Labour, Disruptions, and Recycler Deliveries pages are stubs; Equipment page needs detail panels and fill-level update UI
6. **Frontend component completions** — SiteAssignmentForm, ShiftScheduler, AttendanceTable, ResolutionPanel, ProofOfDeliveryForm, ReconciliationPanel, BuyerConfirmationForm, OperationalFieldSummaryCard
7. **Property-based and unit tests** — 19 properties defined in the design, plus integration tests

## Tasks

- [ ] 1. Create Alembic migration for all operational field tables
  - Write `backend/alembic/versions/xxxx_add_operational_field_tables.py` using `op.create_table()` for all 16 tables: `compaction_machines`, `compactor_deployments`, `compactor_maintenance_logs`, `containers`, `container_fill_readings`, `pickup_triggers`, `container_transport_logs`, `staff_profiles`, `staff_status_history`, `site_assignments`, `site_assignment_members`, `shifts`, `shift_attendances`, `disruption_logs`, `disruption_job_impacts`, `recycler_deliveries`
  - Set `down_revision` to `'a1b2c3d4e5f6'` (the current head migration)
  - Include all FK constraints, indexes, and default values matching the ORM models
  - Add `audit_logs` table with columns: `id UUID PK`, `entity_type VARCHAR(50)`, `entity_id UUID`, `operation VARCHAR(20)`, `previous_state JSONB`, `new_state JSONB`, `changed_by UUID FK users.id SET NULL`, `changed_at TIMESTAMPTZ server_default=now()`
  - _Requirements: 1.1, 4.1, 7.1, 11.1, 14.1, 19.1_

- [ ] 2. Implement AuditLog ORM model and session event hook
  - [ ] 2.1 Add `AuditLog` SQLAlchemy model to `backend/models/` (new file `audit.py`) with all fields from the design; add Pydantic `AuditLogRead` schema
    - Fields: `id`, `entity_type`, `entity_id`, `operation`, `previous_state` (JSON nullable), `new_state` (JSON), `changed_by` (FK users.id SET NULL), `changed_at` (tz-aware, server_default)
    - _Requirements: 19.1_
  - [ ] 2.2 Register SQLAlchemy `after_flush` session event in `backend/database.py` that inspects `session.new`, `session.dirty` for tracked entity types (`CompactionMachine`, `Container`, `SiteAssignment`, `Shift`, `DisruptionLog`, `RecyclerDelivery`) and writes `AuditLog` records in the same transaction
    - Tracked operations: `create` (session.new), `update`/`status_change` (session.dirty)
    - Capture `previous_state` from the ORM instance's expired attributes before flush; `new_state` from the current state
    - If the audit write raises, the originating transaction must roll back (HTTP 500)
    - _Requirements: 19.1, 19.3_
  - [ ]* 2.3 Write property test for audit log completeness (Property 18)
    - **Property 18: Audit log completeness**
    - **Validates: Requirements 19.1, 19.3**

- [ ] 3. Implement `detect_no_checkout` Celery task
  - Add `detect_no_checkout` task to `backend/tasks/operational_field_tasks.py` using `AgentBaseTask` base class and `SyncSessionLocal`
  - Schedule: every 15 minutes (add to `BEAT_SCHEDULE` in `celery_app.py` as `timedelta(minutes=15)`)
  - Logic: query `shift_attendances` joined to `shifts` where `shift_date = today`, `check_out_at IS NULL`, `check_in_at IS NOT NULL`, and `shift.end_time < NOW()` (UTC-adjusted for MST); update `status = 'no_checkout'`; broadcast alert via `POST /internal/broadcast-alert` for each affected staff member; persist agent event
  - Use `self.retry(exc=exc)` on unexpected exceptions; catch `SoftTimeLimitExceeded` without retry
  - _Requirements: 10.1_

- [ ] 4. Complete equipment router — status validation, RBAC, and notification broadcasts
  - [ ] 4.1 Add status enum validation to `PATCH /compactors/{id}` — reject invalid `status` values with HTTP 422 using `COMPACTOR_STATUSES`; add equivalent validation to `POST /containers` and `PATCH /containers/{id}` using `CONTAINER_STATUSES`
    - _Requirements: 1.2, 4.2_
  - [ ] 4.2 Wire WebSocket notification broadcast in `POST /containers/{id}/fill-level` when a new `PickupTrigger` is created — call `ws_manager.broadcast_agent_alert()` with trigger details (non-blocking, fire-and-forget via `asyncio.create_task`)
    - _Requirements: 5.3_
  - [ ]* 4.3 Write property test for compaction machine status validation (Property 1)
    - **Property 1: Compaction machine status validation**
    - **Validates: Requirements 1.2**
  - [ ]* 4.4 Write property test for maintenance next-service-date computation (Property 2)
    - **Property 2: Maintenance next-service-date computation**
    - **Validates: Requirements 3.2**
  - [ ]* 4.5 Write property test for due-service filter correctness (Property 3)
    - **Property 3: Due-service filter correctness**
    - **Validates: Requirements 3.5**
  - [ ]* 4.6 Write property test for fill-level history accumulation (Property 4)
    - **Property 4: Fill-level history accumulation**
    - **Validates: Requirements 5.2, 5.4**
  - [ ]* 4.7 Write property test for pickup trigger threshold idempotency (Property 5)
    - **Property 5: Pickup trigger threshold**
    - **Validates: Requirements 5.3**
  - [ ]* 4.8 Write property test for fill-level range validation (Property 6)
    - **Property 6: Fill-level range validation**
    - **Validates: Requirements 5.6**
  - [ ]* 4.9 Write property test for container lifecycle round-trip (Property 7)
    - **Property 7: Container lifecycle round-trip**
    - **Validates: Requirements 6.4, 17.3**

- [ ] 5. Complete labour router — hours summary, overlapping shift validation, and notification broadcasts
  - [ ] 5.1 Add absence rate alert in `POST /shifts/{id}/mark-absent` — after marking absent, query the day's attendance for the site; if absent rate > 20% of scheduled staff, broadcast a `warning` alert via `ws_manager.broadcast_agent_alert()` (non-blocking)
    - _Requirements: 10.4_
  - [ ] 5.2 Verify `GET /staff/{id}/hours-summary` rounds `total_scheduled_hours` to exactly 2 decimal places using `round(total_minutes / 60, 2)`; add a guard that returns `0.0` when no shifts exist for the week
    - _Requirements: 9.6_
  - [ ]* 5.3 Write property test for site assignment requires field supervisor (Property 8)
    - **Property 8: Site assignment requires field supervisor**
    - **Validates: Requirements 8.2**
  - [ ]* 5.4 Write property test for staff status transitions on assignment (Property 9)
    - **Property 9: Staff status transitions on assignment**
    - **Validates: Requirements 8.3, 8.4**
  - [ ]* 5.5 Write property test for shift time validation (Property 10)
    - **Property 10: Shift time validation**
    - **Validates: Requirements 9.4**
  - [ ]* 5.6 Write property test for weekly hours summation (Property 11)
    - **Property 11: Weekly hours summation**
    - **Validates: Requirements 9.6**

- [ ] 6. Complete disruptions router — notification broadcast on creation and RBAC enforcement
  - [ ] 6.1 Add notification broadcast in `POST /disruptions/` — after creating the disruption, call `ws_manager.broadcast_agent_alert()` with `disruption_type`, `affected_jobs_count`, and `reporter_name` (non-blocking via `asyncio.create_task`)
    - _Requirements: 11.6_
  - [ ] 6.2 Add `GET /api/v1/operational-field/audit-log` endpoint to `routers/operational_field.py` — accepts `entity_type`, `entity_id`, `date_from`, `date_to` query params; returns `AuditLog` records ordered by `changed_at` desc; restrict to `superadmin` and `operations_manager` roles using `require_roles`
    - _Requirements: 19.2_
  - [ ]* 6.3 Write property test for disruption requires at least one affected job (Property 12)
    - **Property 12: Disruption requires at least one affected job**
    - **Validates: Requirements 11.2**
  - [ ]* 6.4 Write property test for resolution history accumulation (Property 13)
    - **Property 13: Resolution history accumulation**
    - **Validates: Requirements 13.2**
  - [ ]* 6.5 Write property test for disruption filter correctness (Property 14)
    - **Property 14: Disruption filter correctness**
    - **Validates: Requirements 13.6**

- [ ] 7. Complete recycler deliveries router — reconciliation notification and recyclable record linkage
  - [ ] 7.1 Add notification broadcast in `POST /recycler-deliveries/{id}/proof` when `status` becomes `reconciliation_discrepancy` — call `ws_manager.broadcast_agent_alert()` with variance amount and percentage (non-blocking)
    - _Requirements: 16.2_
  - [ ] 7.2 In `POST /recycler-deliveries/{id}/buyer-confirmation`, after setting `status = 'completed'`, update the linked `RecyclableRecord`'s `buyer_id` field (already partially implemented — also update `sale_value_myr` if buyer confirmed breakdown total differs from declared; log a warning if `recyclable_record_id` is None)
    - _Requirements: 17.2, 17.6_
  - [ ]* 7.3 Write property test for delivery weight reconciliation computation (Property 15)
    - **Property 15: Delivery weight reconciliation computation**
    - **Validates: Requirements 16.1, 16.2**
  - [ ]* 7.4 Write property test for delivery manifest weight tolerance (Property 16)
    - **Property 16: Delivery manifest weight tolerance**
    - **Validates: Requirements 14.3**

- [ ] 8. Checkpoint — run backend tests and verify all routers respond correctly
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Write backend unit and integration tests
  - [ ] 9.1 Create `backend/tests/test_operational_field.py` with pytest + httpx `AsyncClient` tests covering all domain-specific error cases from the design's error handling table
    - Test: deploy already-deployed machine → HTTP 409
    - Test: assign non-available container → HTTP 409
    - Test: fill level outside 0–100 → HTTP 422
    - Test: site assignment missing field_supervisor → HTTP 422
    - Test: overlapping staff assignment → HTTP 409
    - Test: shift end_time ≤ start_time → HTTP 422
    - Test: disruption with no affected jobs → HTTP 422
    - Test: vehicle breakdown without vehicle_id → HTTP 422
    - Test: close vehicle_breakdown without fleet update → HTTP 422
    - Test: delivery with inactive buyer → HTTP 422
    - Test: delivery weight mismatch > 0.5 kg → HTTP 422
    - Test: proof without photo URL → HTTP 422
    - Test: accept discrepancy without justification → HTTP 422
    - _Requirements: 1.5, 4.5, 5.6, 8.2, 8.5, 9.4, 11.2, 11.3, 13.4, 14.2, 14.3, 15.5_
  - [ ] 9.2 Add Celery task tests in `test_operational_field.py` — mock `SyncSessionLocal` and `_broadcast_alert`; verify `check_compactor_service` escalates overdue machines to `maintenance` status; verify `check_work_permit_expiry` generates alerts for permits within 30 days; verify `escalate_stale_disruptions` updates severity to `critical`; verify `detect_no_checkout` marks `no_checkout` for missed checkouts
    - _Requirements: 3.3, 3.4, 7.5, 10.1, 13.5_
  - [ ]* 9.3 Write property test for operational summary count accuracy (Property 17)
    - **Property 17: Operational summary count accuracy**
    - **Validates: Requirements 18.1**
  - [ ]* 9.4 Write property test for RBAC enforcement (Property 19)
    - **Property 19: RBAC enforcement**
    - **Validates: Requirements 20.1, 20.2, 20.5**

- [ ] 10. Write all property-based tests in a single file
  - Create `backend/tests/test_operational_field_properties.py` using Hypothesis
  - Each test function must have a docstring with tag: `Feature: operational-field-management, Property {N}: {property_text}`
  - Configure `@settings(max_examples=100)` on each test
  - Implement all property tests referenced in tasks 4.3–4.9, 5.3–5.6, 6.3–6.5, 7.3–7.4, 2.3, 9.3, 9.4 as individual `@given(...)` test functions
  - Use `hypothesis.strategies` (`st.integers`, `st.dates`, `st.text`, `st.lists`, `st.uuids`, `st.decimals`) to generate inputs
  - For router-level properties (1, 3, 5, 6, 8, 10, 12, 14, 15, 16, 17, 19): use `httpx.AsyncClient` with `app` mounted; for pure-logic properties (2, 4, 7, 9, 11, 13, 18): test the business logic functions directly
  - _Requirements: 1.2, 3.2, 3.5, 5.2, 5.3, 5.4, 5.6, 6.4, 8.2, 8.3, 8.4, 9.4, 9.6, 11.2, 13.2, 13.6, 14.3, 16.1, 16.2, 17.3, 18.1, 19.1, 19.3, 20.1, 20.2, 20.5_

- [ ] 11. Complete the Labour frontend page
  - [ ] 11.1 Replace the current stub in `frontend/src/app/(dashboard)/labour/page.tsx` with a full implementation using `labourApi` — add tabbed layout with tabs: "Staff Profiles", "Site Assignments", "Shifts", "Attendance"
    - Staff Profiles tab: table of `StaffProfile` records (from `labourApi.listStaff`) with columns: name (from linked user), employment type, assignment status badge, current site, work permit expiry (red if within 30 days); "Add Staff" button opens `AddStaffDialog`
    - Site Assignments tab: client selector + `labourApi.listSiteAssignments`; table with site address, supervisor, start/end date, active badge, member count; "New Assignment" button opens `CreateSiteAssignmentDialog`
    - Shifts tab: date range filter + `labourApi.listShifts`; table with shift date, type badge, site, start/end time, staff count; "Create Shift" button opens `ShiftScheduler` dialog
    - Attendance tab: staff + date range filter + `labourApi.getAttendance`; table with staff name, shift date, check-in, check-out, status badge
    - _Requirements: 7.3, 8.6, 9.2, 10.3_
  - [ ] 11.2 Build `ShiftScheduler` dialog component at `frontend/src/components/labour/ShiftScheduler.tsx`
    - Form fields: site assignment selector (from `labourApi.listSiteAssignments`), shift date, shift type (morning/afternoon/night), start time, end time, staff multi-select (from `labourApi.listStaff` filtered to `on_site` at selected assignment)
    - Client-side validation: end time must be after start time; at least one staff member required
    - On submit: call `labourApi.createShift`; invalidate `['shifts']` query; show success toast
    - _Requirements: 9.1, 9.4_
  - [ ] 11.3 Build `AttendanceTable` component at `frontend/src/components/labour/AttendanceTable.tsx`
    - Renders attendance records with check-in/check-out times, status badge (present/absent/no_checkout/late), absence reason
    - Inline "Check In" / "Check Out" / "Mark Absent" action buttons that call `labourApi.checkIn`, `labourApi.checkOut`, `labourApi.markAbsent` respectively
    - Optimistic update via TanStack Query `useMutation`; show toast on success/error
    - _Requirements: 9.3, 10.2_

- [ ] 12. Complete the Disruptions frontend page
  - [ ] 12.1 Add `ResolutionPanel` component at `frontend/src/components/disruptions/ResolutionPanel.tsx`
    - Slide-over or expandable panel triggered by clicking a disruption row
    - Displays: disruption detail, resolution history timeline (from `d.resolution_history`), elapsed time since occurrence
    - "Add Update" textarea + submit button → calls `disruptionsApi.addResolutionUpdate`; invalidates `['disruptions']`
    - "Assign Resolver" user selector (from `settingsApi.listUsers` filtered to `operations_manager`) → calls `disruptionsApi.update`
    - "Close Disruption" button (visible to ops_manager/superadmin) → opens confirmation dialog with closure note textarea; for `vehicle_breakdown` type, shows checkbox "Vehicle status updated in Fleet module"; calls `disruptionsApi.close`
    - _Requirements: 12.3, 13.1, 13.2, 13.3, 13.4_
  - [ ] 12.2 Wire the "Resolve" action button in `disruptions/page.tsx` to open `ResolutionPanel` with the selected disruption; add job impact count column that links to `disruptionsApi.getImpact`
    - _Requirements: 12.3, 12.4_

- [ ] 13. Complete the Recycler Deliveries frontend page
  - [ ] 13.1 Build `ProofOfDeliveryForm` component at `frontend/src/components/recycler-deliveries/ProofOfDeliveryForm.tsx`
    - Dialog form with fields: photo URLs (dynamic list, minimum 1), weight ticket reference, recycler recorded weight (kg)
    - Client-side validation: at least one photo URL required; weight must be > 0
    - On submit: calls `recyclerDeliveriesApi.submitProof`; invalidates `['recycler-deliveries']`; shows success toast
    - _Requirements: 15.2, 15.3, 15.5_
  - [ ] 13.2 Build `ReconciliationPanel` component at `frontend/src/components/recycler-deliveries/ReconciliationPanel.tsx`
    - Displays declared weight, recycler weight, variance kg, variance %, reconciliation status
    - For `reconciliation_discrepancy` status: shows "Accept" and "Reject" buttons; "Accept" requires justification textarea; calls `recyclerDeliveriesApi.reviewReconciliation`
    - _Requirements: 16.3, 16.5_
  - [ ] 13.3 Build `BuyerConfirmationForm` component at `frontend/src/components/recycler-deliveries/BuyerConfirmationForm.tsx`
    - Dialog form with fields: buyer rep name, confirmed breakdown (dynamic key-value pairs for material types), optional buyer reference number
    - On submit: calls `recyclerDeliveriesApi.submitBuyerConfirmation`; invalidates `['recycler-deliveries']`
    - _Requirements: 17.1, 17.4_
  - [ ] 13.4 Wire all action buttons in `recycler-deliveries/page.tsx` to their respective components: "Depart" → `recyclerDeliveriesApi.depart`, "Arrived" → `recyclerDeliveriesApi.arrive`, "Submit Proof" → opens `ProofOfDeliveryForm`, "Review" → opens `ReconciliationPanel`, "Confirm" → opens `BuyerConfirmationForm`
    - _Requirements: 15.1, 16.3, 17.1_

- [ ] 14. Complete the Equipment frontend page — fill-level update and deployment panels
  - [ ] 14.1 Add `FillLevelUpdateDialog` component inline in `equipment/page.tsx` or as a separate file — dialog with fill level slider (0–100), optional photo URL input, optional notes; calls `equipmentApi.updateFillLevel`; invalidates `['containers']`; shows pickup trigger toast if fill level ≥ threshold
    - _Requirements: 5.1, 5.3_
  - [ ] 14.2 Add "Update Fill" button to each container row in the containers table (visible when `status === 'at_site'`); add "Acknowledge" button for containers with active pickup triggers (calls `equipmentApi.acknowledgeTrigger`); add visual indicator (red border or badge) on container rows where `fill_level >= pickup_threshold`
    - _Requirements: 5.5, 6.1_
  - [ ] 14.3 Add deployment detail panel — clicking a compactor row expands or opens a slide-over showing deployment history (`equipmentApi.listDeployments`) and maintenance log (`equipmentApi.listMaintenance`); include "Deploy" button (opens form with client selector and site address) and "Log Maintenance" button (opens form with service date, type, technician, cost)
    - _Requirements: 2.4, 2.5, 3.6_

- [ ] 15. Add `OperationalFieldSummaryCard` to the dashboard
  - [ ] 15.1 Create `frontend/src/components/dashboard/OperationalFieldSummaryCard.tsx` — card component that calls `operationalFieldApi.getSummary()` via TanStack Query (poll every 60 seconds with `refetchInterval: 60_000`); displays: compactor status counts, container status counts, staff status counts, open disruption counts by severity, delivery status counts, and active alerts with severity icons
    - _Requirements: 18.1, 18.2, 18.3_
  - [ ] 15.2 Import and render `OperationalFieldSummaryCard` in `frontend/src/app/(dashboard)/dashboard/page.tsx` — add it as a new section below the existing KPI cards
    - _Requirements: 18.1_

- [ ] 16. Add sidebar navigation links for all four new pages
  - In `frontend/src/components/layout/Sidebar.tsx` (or equivalent layout file), add navigation items for: Equipment (`/equipment`, Wrench icon), Labour (`/labour`, Users icon), Disruptions (`/disruptions`, AlertTriangle icon), Recycler Deliveries (`/recycler-deliveries`, Truck icon)
  - Group them under an "Operations" section header if the sidebar supports grouping; otherwise add them after the existing Jobs link
  - _Requirements: 18.1_

- [ ] 17. Write frontend component tests
  - [ ]* 17.1 Create `frontend/src/components/equipment/__tests__/FillBar.test.tsx` — test that `FillBar` renders red when `fill_level >= threshold`, amber when `fill_level > 60`, green otherwise; test that `fill_level = 100` renders correctly
    - _Requirements: 5.5_
  - [ ]* 17.2 Create `frontend/src/components/labour/__tests__/ShiftScheduler.test.tsx` — test that form rejects submission when `end_time <= start_time`; test that at least one staff member is required
    - _Requirements: 9.4_
  - [ ]* 17.3 Create `frontend/src/components/recycler-deliveries/__tests__/ProofOfDeliveryForm.test.tsx` — test that form rejects submission with zero photo URLs; test that weight must be > 0
    - _Requirements: 15.5_
  - [ ]* 17.4 Create `frontend/src/components/recycler-deliveries/__tests__/ReconciliationPanel.test.tsx` — test that "Accept" button requires justification text before enabling submit; test that variance > 5% renders in red
    - _Requirements: 16.3_

- [ ] 18. Final checkpoint — run full test suite and verify end-to-end flows
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP delivery
- All backend routers (`equipment.py`, `labour.py`, `disruptions.py`, `recycler_deliveries.py`, `operational_field.py`) are already scaffolded and registered in `main.py` — tasks build on top of the existing implementations
- Celery tasks 1–3 (`check_compactor_service`, `check_work_permit_expiry`, `escalate_stale_disruptions`) are already implemented in `operational_field_tasks.py`; only task 4 (`detect_no_checkout`) needs to be added
- The `detect_no_checkout` beat schedule entry must be added to `BEAT_SCHEDULE` in `celery_app.py` alongside the task implementation
- All TypeScript types are defined in `frontend/src/types/operational-field.ts` and all API client methods are defined in `frontend/src/lib/api.ts` — no new type or API client work is needed
- Property-based tests use Hypothesis (already installed); test file is `backend/tests/test_operational_field_properties.py`
- The AuditLog `after_flush` hook must be registered before the first `AsyncSession` is created — register it in `database.py` after the `Base` and engine setup
- IC/passport numbers (`id_number_encrypted`) must be encrypted using Fernet with `settings.SECRET_KEY` before storage; the `AddStaffDialog` component should accept the plaintext value and the backend router must encrypt it before persisting
- Checkpoints reference the pytest command: `pytest backend/tests/test_operational_field.py -v` and `pytest backend/tests/test_operational_field_properties.py -v --hypothesis-seed=0`
