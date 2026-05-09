# Requirements Document

## Introduction

The **Operational Field Management** feature extends the Hi-Tech Waste Management platform with five tightly integrated sub-systems that formalise the company's physical field operations. Currently, supervisors coordinate ~50 staff via WhatsApp calls, compaction equipment is tracked informally, container fill levels are estimated by memory, operational disruptions are unlogged, and recycler deliveries lack structured proof-of-delivery. This feature replaces all of those manual workflows with structured, auditable, platform-native processes.

The five sub-systems are:

1. **Compaction Equipment Tracking** — deployment registry, utilisation, and maintenance scheduling for hydraulic compaction machines at client sites
2. **Container Logistics** — container inventory, fill-level tracking, pickup triggers, and delivery to recyclers
3. **Labour Deployment Management** — site-based team assignments and shift scheduling for ~50 staff, replacing WhatsApp coordination
4. **Operational Disruption Log** — structured logging of landfill delays, highway restricted time zones, and vehicle breakdowns with job impact tracking and resolution workflow
5. **Recycler Delivery Workflow** — container-to-recycler delivery with proof of delivery, reconciliation against recyclable records, and downstream buyer confirmation

All five sub-systems integrate with the existing Jobs, Fleet, Recyclables, and Clients modules.

---

## Glossary

- **Compaction_Machine**: A hydraulic compaction unit owned by Hi-Tech and deployed at a client site to densify solid waste, reducing truck trip frequency.
- **Container**: A physical receptacle (skip bin, roll-on/roll-off box, or compaction chamber) that holds densified waste material at a client site until it is full and ready for transport.
- **Fill_Level**: The estimated percentage of a Container's capacity that is currently occupied by waste material, expressed as an integer from 0 to 100.
- **Pickup_Trigger**: An automated or manual signal that a Container has reached or exceeded its configured fill threshold and requires collection.
- **Staff_Member**: An employee of Hi-Tech Waste Management, including both local and foreign workers supplied via a labour agent, who performs field waste-segregation or operational duties.
- **Shift**: A scheduled work period assigned to one or more Staff_Members at a specific client site, with a defined start time, end time, and role.
- **Site_Assignment**: The record linking one or more Staff_Members to a client site for a given date range, including their designated roles and supervisor.
- **Disruption**: An unplanned operational event — specifically a landfill delay, highway restricted time zone violation risk, or vehicle breakdown — that impacts one or more active Jobs.
- **Disruption_Log**: The structured record of a Disruption, capturing type, timestamp, affected Jobs, resolution steps, and closure confirmation.
- **Recycler_Delivery**: A trip in which a Container of segregated recyclable material is transported from a client site to an appointed downstream recycler.
- **Proof_of_Delivery**: Documentary evidence (photo, weight ticket, and digital acknowledgement) that a Recycler_Delivery was received and accepted by the recycler.
- **Delivery_Reconciliation**: The process of matching the weight and material breakdown declared on a Recycler_Delivery against the corresponding Recyclable_Record in the platform.
- **Buyer_Confirmation**: A downstream buyer's acknowledgement that a Recycler_Delivery has been received, weighed, and accepted, including the buyer's recorded weight.
- **Operations_Manager**: A platform user with role `operations_manager` responsible for scheduling, fleet, and field staff oversight.
- **Field_Supervisor**: A platform user with role `field_supervisor` responsible for on-site team management, shift check-ins, and disruption reporting.
- **Driver**: A platform user with role `driver` responsible for vehicle operation, container transport, and delivery confirmation.
- **System**: The Hi-Tech Waste Management platform (FastAPI backend + Next.js frontend).

---

## Requirements

---

### Requirement 1: Compaction Machine Registry

**User Story:** As an Operations_Manager, I want a registry of all hydraulic compaction machines with their current deployment status, so that I can see at a glance which machines are deployed, where, and which are available or under maintenance.

#### Acceptance Criteria

1. THE System SHALL maintain a registry of Compaction_Machines, each identified by a unique UUID, an asset tag, a model name, a serial number, and a current status.
2. THE System SHALL enforce that each Compaction_Machine status is one of: `available`, `deployed`, `maintenance`, or `decommissioned`.
3. WHEN a Compaction_Machine is created, THE System SHALL record the purchase date, rated compaction force in kilonewtons, and the owning company as Hi-Tech Waste Management.
4. THE System SHALL expose a `GET /api/v1/equipment/compactors` endpoint that returns all Compaction_Machines with their current status, deployment site, and next scheduled service date.
5. IF a Compaction_Machine with status `deployed` is requested for a new deployment, THEN THE System SHALL reject the request with HTTP 409 and an error message identifying the current deployment site.

---

### Requirement 2: Compaction Machine Deployment Tracking

**User Story:** As an Operations_Manager, I want to record which compaction machine is deployed at which client site and for how long, so that I can track utilisation and plan rotations.

#### Acceptance Criteria

1. WHEN a Compaction_Machine is deployed to a client site, THE System SHALL create a deployment record linking the Compaction_Machine UUID, the client UUID, the site address, the deployment start date, and the Staff_Member who authorised the deployment.
2. WHEN a Compaction_Machine is retrieved from a client site, THE System SHALL record the retrieval date on the deployment record and update the Compaction_Machine status to `available`.
3. THE System SHALL calculate the utilisation rate for each Compaction_Machine as the ratio of total deployed days to total calendar days in a given period, expressed as a percentage rounded to one decimal place.
4. THE System SHALL expose a `GET /api/v1/equipment/compactors/{id}/deployments` endpoint that returns the full deployment history for a Compaction_Machine, ordered by deployment start date descending.
5. WHILE a Compaction_Machine has status `deployed`, THE System SHALL display the current client site name, deployment duration in days, and the next scheduled service date on the machine's detail page.

---

### Requirement 3: Compaction Machine Maintenance Scheduling

**User Story:** As an Operations_Manager, I want the system to schedule and alert on compaction machine maintenance, so that machines do not fail at client sites due to missed servicing.

#### Acceptance Criteria

1. THE System SHALL store a maintenance interval in days for each Compaction_Machine, defaulting to 90 days if not specified at creation.
2. WHEN a maintenance service is completed and recorded, THE System SHALL set the next scheduled service date to the service completion date plus the machine's maintenance interval.
3. WHEN the current date is within 14 days of a Compaction_Machine's next scheduled service date, THE System SHALL generate an alert visible to Operations_Manager and Field_Supervisor roles.
4. WHEN the current date equals or exceeds a Compaction_Machine's next scheduled service date and no service has been recorded, THE System SHALL escalate the alert severity to `critical` and update the Compaction_Machine status to `maintenance`.
5. THE System SHALL expose a `GET /api/v1/equipment/compactors/due-service` endpoint that returns all Compaction_Machines whose next scheduled service date is within the next 30 days, ordered by urgency ascending.
6. THE System SHALL record each maintenance event with: service date, service type, technician or workshop name, cost in MYR, and the Staff_Member who logged the record.

---

### Requirement 4: Container Inventory Management

**User Story:** As an Operations_Manager, I want a complete inventory of all containers with their current location and status, so that I can manage container allocation across client sites.

#### Acceptance Criteria

1. THE System SHALL maintain a registry of Containers, each identified by a unique UUID, a container code, a container type (one of: `skip_bin`, `roll_on_roll_off`, `compaction_chamber`), a capacity in cubic metres, and a current status.
2. THE System SHALL enforce that each Container status is one of: `available`, `at_site`, `in_transit`, `at_recycler`, or `decommissioned`.
3. WHEN a Container is assigned to a client site, THE System SHALL record the client UUID, site address, assigned Compaction_Machine UUID (if applicable), assignment date, and the target waste material type.
4. THE System SHALL expose a `GET /api/v1/containers` endpoint that returns all Containers with their current status, current location, Fill_Level, and last updated timestamp.
5. IF a Container with status other than `available` is requested for a new site assignment, THEN THE System SHALL reject the request with HTTP 409 and an error message stating the Container's current status and location.

---

### Requirement 5: Container Fill-Level Tracking

**User Story:** As a Field_Supervisor, I want to record and update the fill level of containers at client sites, so that pickups are triggered at the right time and truck trips are minimised.

#### Acceptance Criteria

1. WHEN a Field_Supervisor submits a fill-level update for a Container, THE System SHALL record the Fill_Level percentage (integer 0–100), the timestamp, the reporting Staff_Member UUID, and an optional photo attachment URL.
2. THE System SHALL store the complete fill-level history for each Container, retaining all readings with their timestamps.
3. WHEN a Container's Fill_Level reaches or exceeds the configured pickup threshold (default 85%), THE System SHALL automatically create a Pickup_Trigger record and notify the Operations_Manager via the platform notification system.
4. THE System SHALL expose a `GET /api/v1/containers/{id}/fill-history` endpoint that returns all fill-level readings for a Container ordered by timestamp descending.
5. WHILE a Container has an active Pickup_Trigger, THE System SHALL display a visual indicator on the container list and map views to distinguish it from containers below threshold.
6. IF a fill-level update is submitted with a value outside the range 0–100, THEN THE System SHALL reject the request with HTTP 422 and a descriptive validation error.

---

### Requirement 6: Container Pickup and Transport Workflow

**User Story:** As an Operations_Manager, I want to manage the full pickup-to-recycler workflow for full containers, so that container transport is tracked from site departure to recycler arrival.

#### Acceptance Criteria

1. WHEN a Pickup_Trigger is acknowledged by an Operations_Manager, THE System SHALL create a Job of type `general_collection` linked to the Container UUID and the client, with status `confirmed`.
2. WHEN a Driver departs a client site with a Container, THE System SHALL record the departure timestamp, the Driver UUID, the Vehicle UUID, and update the Container status to `in_transit`.
3. WHEN a Container arrives at a recycler facility, THE System SHALL record the arrival timestamp and update the Container status to `at_recycler`.
4. WHEN a Container is emptied at a recycler and returned to service, THE System SHALL reset the Container's Fill_Level to 0, update the status to `available`, and close the associated Pickup_Trigger.
5. THE System SHALL expose a `GET /api/v1/containers/{id}/transport-log` endpoint that returns the full transport history for a Container, including all status transitions with timestamps and responsible Staff_Member UUIDs.

---

### Requirement 7: Staff Registry and Role Management

**User Story:** As an Operations_Manager, I want a registry of all field staff with their roles, employment type, and current assignment status, so that I can plan deployments and track workforce availability.

#### Acceptance Criteria

1. THE System SHALL maintain a Staff_Member registry linked to the existing `users` table, extended with: employment type (one of: `permanent`, `contract`, `foreign_worker`), labour agent name (nullable), IC or passport number (stored encrypted), and current assignment status.
2. THE System SHALL enforce that each Staff_Member's current assignment status is one of: `available`, `on_site`, `on_leave`, or `inactive`.
3. THE System SHALL expose a `GET /api/v1/labour/staff` endpoint that returns all Staff_Members with their current assignment status, current site (if `on_site`), role, and employment type.
4. WHEN a Staff_Member's assignment status changes, THE System SHALL record the previous status, new status, timestamp, and the Operations_Manager UUID who made the change.
5. WHERE a Staff_Member has employment type `foreign_worker`, THE System SHALL store the work permit expiry date and generate an alert 30 days before expiry, visible to Operations_Manager and superadmin roles.

---

### Requirement 8: Site-Based Team Assignment

**User Story:** As an Operations_Manager, I want to assign teams of staff to client sites with defined roles and date ranges, so that each site has the right people for waste segregation duties.

#### Acceptance Criteria

1. WHEN a Site_Assignment is created, THE System SHALL record: the client UUID, site address, a list of Staff_Member UUIDs with their designated roles, the assignment start date, the planned end date, and the supervising Field_Supervisor UUID.
2. THE System SHALL enforce that a Site_Assignment includes at least one Staff_Member with the role `field_supervisor`.
3. WHEN a Staff_Member is added to a Site_Assignment, THE System SHALL update that Staff_Member's assignment status to `on_site` and record the site reference.
4. WHEN a Site_Assignment ends or a Staff_Member is removed from it, THE System SHALL update that Staff_Member's assignment status to `available`.
5. IF a Staff_Member is already `on_site` at a different client site and is added to a new Site_Assignment with an overlapping date range, THEN THE System SHALL reject the request with HTTP 409 and identify the conflicting assignment.
6. THE System SHALL expose a `GET /api/v1/labour/sites/{client_id}/assignments` endpoint that returns all active and historical Site_Assignments for a client, ordered by start date descending.

---

### Requirement 9: Shift Scheduling

**User Story:** As a Field_Supervisor, I want to create and manage shift schedules for staff at my assigned sites, so that coverage is planned in advance and attendance can be tracked.

#### Acceptance Criteria

1. WHEN a Shift is created, THE System SHALL record: the Site_Assignment UUID, the shift date, start time, end time, a list of assigned Staff_Member UUIDs, the shift type (one of: `morning`, `afternoon`, `night`), and the creating Field_Supervisor UUID.
2. THE System SHALL expose a `GET /api/v1/labour/shifts` endpoint that accepts `site_id`, `date_from`, and `date_to` query parameters and returns all Shifts within the specified range, including assigned staff names and roles.
3. WHEN a Staff_Member checks in to a Shift, THE System SHALL record the actual check-in timestamp and the Staff_Member UUID; WHEN a Staff_Member checks out, THE System SHALL record the actual check-out timestamp.
4. IF a Shift is created with an end time earlier than or equal to its start time on the same calendar date, THEN THE System SHALL reject the request with HTTP 422 and a descriptive validation error.
5. IF a Staff_Member is assigned to two Shifts on the same date at the same site with overlapping time ranges, THEN THE System SHALL reject the second assignment with HTTP 409 and identify the conflicting Shift.
6. THE System SHALL calculate the total scheduled hours per Staff_Member per week by summing the durations of all Shifts assigned to that Staff_Member within the week, and expose this via `GET /api/v1/labour/staff/{id}/hours-summary`.

---

### Requirement 10: Shift Attendance and Absence Tracking

**User Story:** As an Operations_Manager, I want to track actual attendance against scheduled shifts, so that I can identify absenteeism patterns and ensure client sites are adequately staffed.

#### Acceptance Criteria

1. WHEN a Shift's scheduled end time passes and a Staff_Member has not checked out, THE System SHALL mark that Staff_Member's attendance record for that Shift as `no_checkout` and notify the supervising Field_Supervisor.
2. WHEN a Staff_Member is marked absent for a Shift, THE System SHALL record the absence reason (one of: `sick_leave`, `annual_leave`, `no_show`, `emergency`), the Staff_Member UUID, and the Field_Supervisor UUID who recorded the absence.
3. THE System SHALL expose a `GET /api/v1/labour/attendance` endpoint that accepts `staff_id`, `date_from`, and `date_to` query parameters and returns attendance records with check-in time, check-out time, and attendance status for each Shift.
4. WHEN the absence rate for a client site exceeds 20% of scheduled staff on any given day, THE System SHALL generate an alert visible to Operations_Manager and management roles, identifying the site and the number of absent staff.
5. THE System SHALL calculate the attendance rate for each Staff_Member as the ratio of attended Shifts to scheduled Shifts within a given period, expressed as a percentage rounded to one decimal place.

---

### Requirement 11: Disruption Log — Creation and Classification

**User Story:** As a Field_Supervisor or Driver, I want to log operational disruptions with structured data, so that the impact on jobs is captured and management can act quickly.

#### Acceptance Criteria

1. WHEN a Disruption_Log is created, THE System SHALL record: disruption type (one of: `landfill_delay`, `highway_restriction`, `vehicle_breakdown`, `site_access_denied`, `other`), the timestamp of occurrence, the reporting Staff_Member UUID, a free-text description, and a list of affected Job UUIDs.
2. THE System SHALL enforce that at least one affected Job UUID is provided when creating a Disruption_Log.
3. WHEN a Disruption_Log is created with type `vehicle_breakdown`, THE System SHALL require the Vehicle UUID and automatically update the Vehicle status to `maintenance` in the Fleet module.
4. WHEN a Disruption_Log is created with type `highway_restriction`, THE System SHALL require the affected highway name and the restriction time window (start time and end time).
5. THE System SHALL expose a `POST /api/v1/disruptions` endpoint that accepts the Disruption_Log payload and returns the created record with HTTP 201.
6. WHEN a Disruption_Log is created, THE System SHALL immediately notify all Operations_Manager and management role users via the platform notification system with the disruption type, affected jobs count, and reporting staff name.

---

### Requirement 12: Disruption Log — Job Impact Tracking

**User Story:** As an Operations_Manager, I want to see the quantified impact of each disruption on affected jobs, so that I can prioritise resolution and communicate delays to clients.

#### Acceptance Criteria

1. WHEN a Disruption_Log is linked to a Job, THE System SHALL record the estimated delay duration in minutes for that Job, the original scheduled completion time, and the revised estimated completion time.
2. THE System SHALL expose a `GET /api/v1/disruptions/{id}/impact` endpoint that returns all affected Jobs with their original scheduled times, estimated delay durations, and current Job statuses.
3. WHILE a Disruption_Log has status `open`, THE System SHALL display the disruption on the Operations Dashboard with the elapsed time since the disruption was logged, the number of affected Jobs, and the assigned resolver's name.
4. THE System SHALL expose a `GET /api/v1/jobs/{id}/disruptions` endpoint that returns all Disruption_Logs linked to a given Job, ordered by occurrence timestamp descending.
5. THE System SHALL calculate the total disruption-caused delay in minutes per Job by summing the estimated delay durations of all linked open Disruption_Logs.

---

### Requirement 13: Disruption Log — Resolution Workflow

**User Story:** As an Operations_Manager, I want a structured resolution workflow for disruptions, so that every disruption has a clear owner, resolution steps, and a formal closure record.

#### Acceptance Criteria

1. WHEN a Disruption_Log is created, THE System SHALL set its status to `open` and allow an Operations_Manager to assign a resolver Staff_Member UUID.
2. WHEN a resolver submits a resolution update, THE System SHALL record the update text, the timestamp, and the resolver's Staff_Member UUID, and append it to the Disruption_Log's resolution history.
3. WHEN an Operations_Manager closes a Disruption_Log, THE System SHALL require a closure note, record the closure timestamp and the closing Staff_Member UUID, and update the status to `resolved`.
4. WHEN a Disruption_Log of type `vehicle_breakdown` is resolved, THE System SHALL require the Vehicle UUID and prompt the Operations_Manager to update the Vehicle status in the Fleet module before closure is permitted.
5. IF a Disruption_Log has been `open` for more than 4 hours without a resolution update, THEN THE System SHALL escalate the alert severity to `critical` and notify management role users.
6. THE System SHALL expose a `GET /api/v1/disruptions` endpoint that accepts `status`, `type`, `date_from`, and `date_to` query parameters and returns matching Disruption_Logs ordered by occurrence timestamp descending.

---

### Requirement 14: Recycler Delivery — Initiation and Manifest

**User Story:** As an Operations_Manager, I want to initiate a recycler delivery with a formal manifest, so that every container-to-recycler trip has a documented record before the vehicle departs.

#### Acceptance Criteria

1. WHEN a Recycler_Delivery is initiated, THE System SHALL record: the Container UUID, the downstream buyer UUID (from the existing `downstream_buyers` table), the assigned Vehicle UUID, the assigned Driver UUID, the declared material breakdown by waste type in kilograms, the declared total weight in kilograms, and the planned departure datetime.
2. THE System SHALL enforce that the downstream buyer UUID references an active record in the `downstream_buyers` table; IF the buyer is inactive, THEN THE System SHALL reject the request with HTTP 422.
3. THE System SHALL enforce that the declared total weight equals the sum of all declared material breakdown weights, with a tolerance of 0.5 kg; IF the totals do not reconcile within tolerance, THEN THE System SHALL reject the request with HTTP 422 and identify the discrepancy.
4. WHEN a Recycler_Delivery is created, THE System SHALL set its status to `pending_departure` and link it to the associated Container UUID.
5. THE System SHALL expose a `POST /api/v1/recycler-deliveries` endpoint that accepts the delivery manifest payload and returns the created record with HTTP 201.

---

### Requirement 15: Recycler Delivery — Proof of Delivery

**User Story:** As a Driver, I want to capture proof of delivery at the recycler facility, so that there is an auditable record that the material was received.

#### Acceptance Criteria

1. WHEN a Driver marks a Recycler_Delivery as arrived at the recycler facility, THE System SHALL record the arrival timestamp, the Driver UUID, and update the Recycler_Delivery status to `arrived`.
2. WHEN a Driver submits proof of delivery, THE System SHALL require: at least one photo attachment URL, the recycler's weight ticket reference number, and the recycler-recorded weight in kilograms.
3. WHEN proof of delivery is submitted, THE System SHALL update the Recycler_Delivery status to `proof_submitted` and record the submission timestamp.
4. THE System SHALL expose a `POST /api/v1/recycler-deliveries/{id}/proof` endpoint that accepts the proof-of-delivery payload and returns the updated record.
5. IF proof of delivery is submitted without at least one photo attachment URL, THEN THE System SHALL reject the request with HTTP 422 and a descriptive validation error.

---

### Requirement 16: Recycler Delivery — Reconciliation Against Recyclable Records

**User Story:** As an Operations_Manager, I want the system to reconcile the delivered weight against the recyclable record for the same container, so that discrepancies are flagged before the delivery is closed.

#### Acceptance Criteria

1. WHEN a Recycler_Delivery reaches status `proof_submitted`, THE System SHALL automatically compare the recycler-recorded weight against the declared total weight on the delivery manifest and compute the variance in kilograms and as a percentage.
2. IF the weight variance between the recycler-recorded weight and the declared total weight exceeds 5%, THEN THE System SHALL flag the Recycler_Delivery with status `reconciliation_discrepancy` and notify the Operations_Manager with the variance amount and percentage.
3. WHEN an Operations_Manager reviews a reconciliation discrepancy, THE System SHALL allow the Operations_Manager to either accept the variance with a written justification or reject the delivery and request re-weighing.
4. THE System SHALL link the Recycler_Delivery to the corresponding Recyclable_Record in the `recyclable_records` table using the Container UUID and the delivery date as the matching key.
5. THE System SHALL expose a `GET /api/v1/recycler-deliveries/{id}/reconciliation` endpoint that returns the declared weight, recycler-recorded weight, variance in kg, variance percentage, and reconciliation status.

---

### Requirement 17: Recycler Delivery — Buyer Confirmation and Closure

**User Story:** As an Operations_Manager, I want to record the downstream buyer's formal confirmation of receipt, so that the delivery chain-of-custody is complete and the recyclable record can be finalised.

#### Acceptance Criteria

1. WHEN a Buyer_Confirmation is recorded, THE System SHALL capture: the downstream buyer UUID, the buyer's representative name, the buyer's confirmed received weight in kilograms per material type, the confirmation timestamp, and an optional buyer reference number.
2. WHEN a Buyer_Confirmation is recorded and the reconciliation status is not `reconciliation_discrepancy`, THE System SHALL update the Recycler_Delivery status to `completed` and update the linked Recyclable_Record's `buyer_id` and `sale_value_myr` fields.
3. WHEN a Recycler_Delivery reaches status `completed`, THE System SHALL update the associated Container status to `available` and reset its Fill_Level to 0.
4. THE System SHALL expose a `POST /api/v1/recycler-deliveries/{id}/buyer-confirmation` endpoint that accepts the Buyer_Confirmation payload and returns the updated Recycler_Delivery record.
5. THE System SHALL expose a `GET /api/v1/recycler-deliveries` endpoint that accepts `status`, `buyer_id`, `date_from`, and `date_to` query parameters and returns matching Recycler_Deliveries ordered by planned departure datetime descending.
6. WHEN a Recycler_Delivery is completed, THE System SHALL make the delivery record available to the existing Recyclables module chain-of-custody view, linked by the Recyclable_Record UUID.

---

### Requirement 18: Operational Dashboard Integration

**User Story:** As an Operations_Manager, I want a unified operational field view on the dashboard, so that I can monitor equipment, containers, staff, disruptions, and pending deliveries from a single screen.

#### Acceptance Criteria

1. THE System SHALL provide a dashboard section that displays: count of Compaction_Machines by status, count of Containers by status, count of Staff_Members by assignment status, count of open Disruption_Logs by severity, and count of Recycler_Deliveries by status.
2. WHEN any of the following conditions are true, THE System SHALL display a highlighted alert on the operational dashboard: a Compaction_Machine service is overdue, a Container has an unacknowledged Pickup_Trigger older than 2 hours, an open Disruption_Log has been unresolved for more than 4 hours, or a Recycler_Delivery has status `reconciliation_discrepancy`.
3. THE System SHALL expose a `GET /api/v1/operational-field/summary` endpoint that returns the aggregated counts and active alerts described in criteria 1 and 2, suitable for polling by the frontend dashboard.
4. WHERE the Operations_Agent AI agent is active, THE System SHALL make the operational field summary data available to the agent for inclusion in its daily briefing and scheduling recommendations.

---

### Requirement 19: Audit Trail and Data Integrity

**User Story:** As a superadmin or Operations_Manager, I want every state change across all five sub-systems to be recorded in an audit trail, so that the history of all field operations is traceable and non-repudiable.

#### Acceptance Criteria

1. THE System SHALL record an audit event for every create, update, and status-change operation across Compaction_Machine, Container, Site_Assignment, Shift, Disruption_Log, and Recycler_Delivery entities, capturing: entity type, entity UUID, operation type, previous state (JSON), new state (JSON), timestamp, and the acting user UUID.
2. THE System SHALL expose a `GET /api/v1/audit-log` endpoint that accepts `entity_type`, `entity_id`, `date_from`, and `date_to` query parameters and returns matching audit events ordered by timestamp descending, accessible only to `superadmin` and `operations_manager` roles.
3. WHEN an audit event is written, THE System SHALL ensure the write is atomic with the originating operation; IF the audit write fails, THEN THE System SHALL roll back the originating operation and return HTTP 500.
4. THE System SHALL retain audit events for a minimum of 2 years before they are eligible for archival.

---

### Requirement 20: Role-Based Access Control for Field Operations

**User Story:** As a superadmin, I want field operations data to be accessible only to users with appropriate roles, so that sensitive staff and operational data is protected.

#### Acceptance Criteria

1. THE System SHALL restrict write access to Compaction_Machine and Container records to users with roles `superadmin` or `operations_manager`.
2. THE System SHALL restrict write access to Site_Assignment and Shift records to users with roles `superadmin`, `operations_manager`, or `field_supervisor`.
3. THE System SHALL restrict Disruption_Log creation to users with roles `superadmin`, `operations_manager`, `field_supervisor`, or `driver`; resolution and closure SHALL be restricted to `superadmin` and `operations_manager`.
4. THE System SHALL restrict Recycler_Delivery initiation and Buyer_Confirmation recording to users with roles `superadmin` or `operations_manager`; proof-of-delivery submission SHALL also be permitted for `driver`.
5. IF a user attempts an operation outside their permitted roles, THEN THE System SHALL return HTTP 403 with an error message identifying the required role.
