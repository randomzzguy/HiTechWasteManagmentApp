# Hi-Tech Waste Management - AI Assistant Features Guide

This guide documents all AI-powered features available in the Hi-Tech Waste Management system.

---

## Overview

The AI Assistant provides 6 major feature categories with 30+ functions to streamline waste management operations:

1. **Database Operations** - Read/write database through natural language
2. **Bulk Import** - CSV/Excel data import with AI validation
3. **Smart Scheduling** - Auto-assign jobs and optimize routes
4. **Compliance Monitoring** - Track permits, licenses, and deadlines
5. **Invoice Intelligence** - AR aging and collection strategies
6. **ESG Reporting** - Sustainability metrics and carbon tracking

---

## 1. Database Agent

**Purpose:** Query and modify the database using natural language chat.

### Available Operations

| Function | Description | Example Query |
|----------|-------------|---------------|
| `query_database` | Read data from any table | "Show all clients in Kuala Lumpur" |
| `create_record` | Create new records | "Add a new client ABC Sdn Bhd" |
| `update_record` | Update existing records | "Update client status to active" |
| `delete_record` | Delete records | "Delete the test job" |
| `search_records` | Search with filters | "Find jobs scheduled for tomorrow" |

### Supported Entities

- **Clients** - Company info, contacts, waste streams
- **Jobs** - Scheduled waste, recycling, BSF, destruction
- **Vehicles** - Fleet management, maintenance, trips
- **Invoices** - Billing, payments, line items
- **Employees** - Staff, drivers, certifications
- **BSF Batches** - Insect protein production
- **Destruction Jobs** - Certificate tracking
- **Scheduled Waste** - DOE compliance tracking
- **Recyclables** - Material recovery, downstream buyers

### Example Chat Interactions

```
User: "Show me all active clients"
AI: Found 42 active clients:
    1. ABC Manufacturing Sdn Bhd - Industrial Waste
    2. XYZ Retail Chain - General Waste
    ...

User: "Create a scheduled waste job for ABC Corp tomorrow"
AI: Created Job ID: SW-2026-089
    - Client: ABC Corp
    - Type: Scheduled Waste
    - Date: 2026-04-29
    - Status: Confirmed

User: "What's the total outstanding for client XYZ?"
AI: XYZ Sdn Bhd has 3 outstanding invoices:
    Total: 45,000.00 MYR
    - INV-2026-015: 20,000 MYR (overdue 15 days)
    - INV-2026-023: 15,000 MYR (due in 5 days)
    - INV-2026-031: 10,000 MYR (current)
```

---

## 2. Bulk Import Agent

**Purpose:** Import CSV/Excel files with AI-powered column mapping and validation.

### Features

| Feature | Description |
|---------|-------------|
| **Auto Column Mapping** | AI matches CSV columns to database fields |
| **Data Validation** | Validates formats, duplicates, required fields |
| **Error Reporting** | Shows exactly which rows failed and why |
| **Preview Mode** | Review before committing changes |
| **Batch Processing** | Handles large files efficiently |

### Supported Import Types

- **Clients** - Company names, addresses, contacts
- **Jobs** - Job types, dates, locations
- **Waste Records** - Quantities, types, disposal methods
- **Invoices** - Line items, amounts, due dates
- **Vehicle Records** - Registrations, maintenance schedules
- **Employees** - Staff details, roles, certifications

### How to Use

1. **In AI Chat:** Click the file upload button (paperclip icon)
2. **Drag & Drop:** CSV or Excel file into the chat
3. **AI Analysis:** Agent analyzes columns and suggests mappings
4. **Review:** Confirm or adjust column mappings
5. **Import:** AI validates and imports with progress tracking

### Example Chat Interactions

```
User: [Uploads clients.csv]
AI: Analyzing file... Found 50 client records.

    Detected columns:
    - "Company Name" → client_name
    - "Contact Person" → contact_name
    - "Phone" → phone
    - "Email" → email
    - "Address" → address
    
    Validation Results:
    ✅ 48 records ready to import
    ⚠️ 2 records have issues:
      Row 12: Missing email (optional)
      Row 37: Duplicate phone number
    
    Proceed with import?

User: "Yes, import them"
AI: Importing... 
    ✅ Successfully imported 48 clients
    ⏱️ Duration: 3.2 seconds
```

---

## 3. Smart Scheduling Agent

**Purpose:** AI-powered job assignment, route optimization, and conflict detection.

### Features

| Feature | Description |
|---------|-------------|
| **Auto-Assignment** | Suggests best vehicle/driver for jobs |
| **Route Optimization** | Minimizes travel time and fuel costs |
| **Conflict Detection** | Identifies scheduling overlaps |
| **Priority Scoring** | Ranks jobs by urgency, location, capacity |
| **Batch Scheduling** | Schedule multiple jobs at once |

### Scheduling Factors

**Assignment Scoring:**
- Vehicle proximity to job location
- Driver qualifications/certifications
- Vehicle capacity vs. waste volume
- Driver shift availability
- Historical performance

**Route Optimization:**
- Shortest path calculation (Haversine formula)
- Traffic pattern awareness
- Fuel efficiency optimization
- Time window constraints
- Vehicle capacity utilization

### Example Chat Interactions

```
User: "Suggest assignments for today's unassigned jobs"
AI: Found 8 unassigned jobs for today.

    Suggested Assignments:
    
    Job SW-2026-089 (ABC Corp, 500kg)
    → Vehicle: Lorry-03 (PJ1234)
    → Driver: Ahmad (Hazmat certified)
    → Score: 92/100
    → Est. travel: 12km, 25 mins
    
    Job RC-2026-045 (XYZ Plaza, recyclables)
    → Vehicle: Van-02 (WL4567)
    → Driver: Sarah (Recycling route)
    → Score: 88/100
    → Est. travel: 8km, 18 mins
    
    Apply these assignments?

User: "Optimize route for Vehicle PJ1234 today"
AI: Optimized Route for Lorry-03 (PJ1234):

    Current Route: 78km total
    Optimized Route: 54km total (-31%)
    
    Sequence:
    1. Warehouse (start) - 8:00 AM
    2. ABC Manufacturing (12km) - 8:45 AM
    3. XYZ Industrial Park (8km) - 9:30 AM
    4. 123 Logistics Hub (15km) - 10:45 AM
    5. Warehouse (return) - 19km
    
    Fuel saved: ~8 liters
    Time saved: ~1.5 hours

User: "Check for scheduling conflicts this week"
AI: Analyzed 45 scheduled jobs for conflicts.

    Found 2 conflicts:
    
    🔴 CONFLICT #1:
       Job SW-2026-091 overlaps with SW-2026-092
       - Both use Driver: Ahmad
       - Monday 9:00 AM - 11:30 AM
       
    🔴 CONFLICT #2:
       Job DJ-2026-015 vehicle capacity exceeded
       - Requires 3,500kg capacity
       - Assigned vehicle: 2,000kg max
       
    Suggested resolutions provided.
```

---

## 4. Compliance Monitoring Agent

**Purpose:** Track permits, licenses, regulatory deadlines, and generate alerts.

### Monitored Compliance Areas

| Category | Items Monitored | Regulation |
|----------|-----------------|------------|
| **Scheduled Waste** | Storage deadlines (90/180 day DOE rule) | DOE Malaysia |
| **Vehicle Road Tax** | JPJ road tax expiry | Road Transport Act 1987 |
| **Vehicle Insurance** | Insurance policy expiry | Motor Vehicles Act 1963 |
| **Vehicle PUSPAKOM** | Commercial vehicle inspection | CVLB Regulations |
| **Downstream Licenses** | Recycler license validity | DOE EQ Act 1974 |
| **Destruction Certs** | Certificate issuance status | Contractual |
| **Consignment Notes** | Waste tracking status | DOE tracking |

### Alert Levels

| Level | Trigger | Action Required |
|-------|---------|-----------------|
| 🟢 Compliant | All good | None |
| 🟡 Warning | Due within 30 days | Schedule renewal |
| 🟠 Critical | Due within 7 days | Urgent action |
| 🔴 Expired | Past deadline | Immediate compliance |

### Example Chat Interactions

```
User: "Show compliance dashboard"
AI: Compliance Dashboard - April 2026

    Monitoring 47 compliance items:
    ✅ 38 compliant
    ⚠️ 5 warnings (due within 30 days)
    🔴 4 critical (due within 7 days)
    
    Top Alerts:
    🚨 SW Batch SW305 - 2 days until DOE deadline
    🚨 Vehicle PJX1234 - Road tax expired 5 days ago
    ⚠️ 3 vehicles need PUSPAKOM inspection
    
    Compliance Health: 81% (needs attention)

User: "Check scheduled waste compliance for client ABC"
AI: Scheduled Waste Compliance - ABC Corp

    Found 3 scheduled waste batches:
    
    🔴 Batch SW410 - 5 days PAST DOE deadline
       Status: VIOLATION
       Action: Dispose immediately or request extension
       Penalty risk: HIGH
       
    ⚠️ Batch SW305 - Due in 10 days
       Status: WARNING
       Action: Schedule disposal within 10 days
       
    ✅ Batch SW104 - 45 days remaining
       Status: COMPLIANT
       
    Overall ABC Corp Status: AT RISK

User: "Generate DOE compliance report for Q1 2026"
AI: DOE Compliance Report - Q1 2026
    
    Period: 2026-01-01 to 2026-03-31
    Items checked: 142
    
    Summary:
    ✅ Compliant: 128 (90%)
    ⚠️ Warnings: 11 (8%)
    🔴 Violations: 3 (2%)
    
    Violations Found:
    1. SW Batch SW298 - 2 days storage exceeded
    2. SW Batch SW301 - Missing consignment note
    3. Vehicle BKG4567 - PUSPAKOM 3 days expired
    
    Recommendations:
    1. URGENT: 2 SW batches need disposal
    2. Follow up on consignment note JN-2026-015
    3. Schedule vehicle inspection for BKG4567
```

---

## 5. Invoice Intelligence Agent

**Purpose:** AR aging reports, collection strategies, payment predictions, and risk scoring.

### Features

| Feature | Description |
|---------|-------------|
| **Aging Reports** | AR by buckets (current, 30, 60, 90, 120+) |
| **Risk Scoring** | AI-powered invoice risk assessment |
| **Client Profiles** | Payment behavior analysis |
| **Collection Strategies** | Tailored action plans per client |
| **Payment Predictions** | ML-based payment probability |
| **Collection Prompts** | AI-crafted email & call scripts |

### Aging Buckets

| Bucket | Days | Status |
|--------|------|--------|
| Current | 0-30 | On track |
| 31-60 | Early delinquency | Watch |
| 61-90 | Moderate risk | Action needed |
| 91-120 | High risk | Urgent |
| 120+ | Critical | Collection/legal |

### Collection Tones

- **Professional** - Standard business communication
- **Friendly** - Warm but firm
- **Firm** - Assertive, deadline-focused
- **Urgent** - Immediate action required

### Example Chat Interactions

```
User: "Show aging report"
AI: Accounts Receivable Aging Report

    Total Outstanding: 250,000 MYR (42 invoices)
    
    Current (0-30):     150,000 MYR (60%)
    31-60 days:          50,000 MYR (20%) ⚠️
    61-90 days:          30,000 MYR (12%) 🔶
    91-120 days:         15,000 MYR (6%)  🔴
    120+ days:            5,000 MYR (2%)  🚨
    
    Delinquent: 100,000 MYR (40%)
    
    Top Risk Items:
    🔴 INV-2026-015 - ABC Corp - 45,000 MYR (95 days)
    🔴 INV-2026-008 - XYZ Sdn Bhd - 12,000 MYR (87 days)
    
    DSO (Days Sales Outstanding): 42 days

User: "Get collection strategy for client ABC Corp"
AI: Collection Strategy for ABC Corp
   
    Risk Level: HIGH
    Outstanding: 85,000 MYR (3 invoices)
    Oldest Overdue: 67 days
    
    Recommended Sequence:
    1. Collection Call (Today) - Priority: HIGH
       Script: "Hello, this is [Name] from Hi-Tech. I'm calling
       regarding the outstanding balance of 85,000 MYR. 
       How can we help facilitate payment today?"
       
    2. Demand Letter (+2 days) - Auto-generated
       Subject: IMMEDIATE ATTENTION REQUIRED
       
    3. Legal Notice (+14 days if no response)
       
    Expected Collection Rate: 65%
    Timeline: 14 days
    
    Client Profile:
    - On-time rate: 45% (deteriorating)
    - Avg days to pay: 52
    - Recommendation: Require deposit for new jobs

User: "Generate urgent collection message for XYZ"
AI: Generated Collection Prompt (URGENT)

    Subject: URGENT: FINAL NOTICE - Payment Required Immediately
    
    Message:
    XYZ Sdn Bhd,
    
    URGENT: 25,000.00 MYR is severely overdue (98 days).
    This is your FINAL NOTICE before legal action.
    
    You must contact us within 48 hours to avoid escalation.
    
    Contact: [phone] [email]
    
    Call Script:
    "URGENT COLLECTION CALL. This matter requires immediate 
    resolution. 25,000 MYR is 98 days overdue. I need a 
    payment commitment right now or this will be escalated."

User: "Will invoice INV-2026-015 be paid on time?"
AI: Payment Prediction for INV-2026-015
    
    Confidence: 75%
    
    Predicted Payment: 2026-05-15
    Amount: 12,500 MYR
    
    Probabilities:
    - On-time (by due date): 25%
    - Late payment: 45%
    - Default: 30%
    
    Risk Factors:
    ⚠️ Client has deteriorating payment trend
    ⚠️ Invoice is significantly overdue (45 days)
    ⚠️ Large invoice amount
    
    Recommendation: Proactive collection call recommended
```

---

## 6. ESG Report Generation Agent

**Purpose:** Automated Environmental, Social, and Governance (ESG) sustainability reporting.

### Report Components

| Category | Metrics |
|----------|---------|
| **Environmental** | Carbon footprint, waste diversion, recycling rates |
| **Social** | Clients served, jobs completed, new onboardings |
| **Governance** | Compliance violations, audit findings, certificates |
| **SDG Mapping** | UN Sustainable Development Goal contributions |

### Carbon Tracking

| Metric | Description |
|--------|-------------|
| Transport Emissions | CO₂ from vehicle fuel |
| Landfill Avoidance | Credit for diverted waste |
| Recycling Credits | Carbon saved via material recovery |
| WTE Credits | Waste-to-energy benefits |
| Net Impact | Overall carbon position |
| Trees Equivalent | Visual comparison metric |

### SDG Contributions

| SDG | Name | How We Contribute |
|-----|------|-------------------|
| 12 | Responsible Consumption | Waste diversion from landfill |
| 13 | Climate Action | Carbon avoidance |
| 11 | Sustainable Cities | Urban waste management |
| 8 | Decent Work | Job creation, economic value |

### Report Types

- **Monthly** - Monthly sustainability summary
- **Quarterly** - Quarterly ESG report
- **Annual** - Full year sustainability report
- **Custom** - Any date range
- **Client-specific** - Individual client impact report

### Example Chat Interactions

```
User: "Generate ESG report for April 2026"
AI: Monthly ESG Report - April 2026

    🌱 ENVIRONMENTAL IMPACT
    
    Carbon Metrics:
    - Total Emissions: 1,250 kgCO₂e
    - Total Avoided: 4,800 kgCO₂e
    - Net Impact: -3,550 kgCO₂e ✅
    - Trees Equivalent: 178 trees planted!
    
    Waste Diversion:
    - Total Collected: 45,000 kg
    - Diverted from Landfill: 38,250 kg (85%)
    - Recycled: 32,000 kg (71%)
    - Composted (BSF): 4,200 kg
    
    ♻️ RECYCLABLE RECOVERY
    - Collections: 156
    - Total Weight: 32,000 kg
    - Material Breakdown:
      • Paper/Cardboard: 15,000 kg
      • Plastics: 8,500 kg
      • Metals: 5,200 kg
      • Glass: 3,300 kg
    
    👥 SOCIAL IMPACT
    - Clients Served: 42
    - Jobs Completed: 389
    - New Clients: 5
    
    🎯 UN SDG CONTRIBUTIONS
    ✅ SDG 12 - 85% waste diversion - HIGH impact
    ✅ SDG 13 - Net carbon avoidance 3.55 tonnes - HIGH impact
    ✅ SDG 11 - Served 42 urban clients - MEDIUM impact
    ✅ SDG 8 - 389 jobs completed - MEDIUM impact
    
    📋 RECOMMENDATIONS
    1. Maintain >80% diversion rate
    2. Expand plastic recycling capacity
    3. Track client-specific carbon savings

User: "Show ESG dashboard"
AI: ESG Dashboard - April 2026

    Month-to-Date (Apr 1-28):
    ┌─────────────────────────────────────────┐
    │ Carbon    │ -2,840 kgCO₂e  ✅ Net Pos  │
    │ Waste     │ 78% diverted   ⬆️ Improving │
    │ Recycling │ 1,850 kg       ➡️ Stable    │
    └─────────────────────────────────────────┘
    
    Year-to-Date (Jan-Apr):
    - Carbon Avoided: 12,500 kgCO₂e
    - Waste Diverted: 152 tonnes
    - Clients Served: 168
    
    🚨 Alerts:
    ⚠️ Diversion rate below 80% target (current: 78%)
    
    📈 Trends:
    Carbon Impact: improving ⬆️
    Waste Diversion: improving ⬆️
    Recycling Rate: stable ➡️

User: "Generate sustainability report for client ABC Corp"
AI: Client ESG Report - ABC Corp - 2026

    Your Environmental Impact This Year:
    
    🌍 Carbon Footprint: -450 kgCO₂e
       (You helped avoid 450 kg of CO₂!)
    
    ♻️ Waste Management:
    - Total Waste: 12,500 kg
    - Diverted from Landfill: 11,000 kg (88%)
    - Recycled: 8,500 kg
    
    📜 Certificates: 3 destruction certificates issued
    
    ✅ Compliance Status: Fully Compliant
    
    Environmental Benefits:
    ✅ Diverted 88% of waste from landfill
    ✅ Contributed to carbon avoidance of 450 kgCO₂e
    ✅ Recycled 8,500 kg of materials back into economy
    ✅ Equivalent to planting 23 trees
    
    Thank you for being a sustainability champion!

User: "What's our carbon footprint this month?"
AI: Your carbon footprint for April 2026:

    Emissions: 1,250 kgCO₂e
    Avoided: 4,800 kgCO₂e
    Net: -3,550 kgCO₂e ✅
    
    This means you've achieved net-positive impact,
    equivalent to planting 178 trees!

User: "Which SDGs are we contributing to?"
AI: Your operations contribute to 4 UN SDGs:

    SDG 12 (Responsible Consumption) - HIGH impact
    - 85% waste diversion rate
    
    SDG 13 (Climate Action) - HIGH impact  
    - Net carbon avoidance of 3.55 tonnes
    
    SDG 11 (Sustainable Cities) - MEDIUM impact
    - Serving 42 urban clients
    
    SDG 8 (Decent Work) - MEDIUM impact
    - 389 jobs completed
```

---

## Quick Reference: All AI Functions

### Database Operations
- `query_database` - Query any entity
- `create_record` - Create new records
- `update_record` - Update existing records
- `delete_record` - Delete records
- `search_records` - Search with filters

### Bulk Import
- `analyze_import_file` - Preview CSV/Excel
- `execute_bulk_import` - Import validated data
- `get_import_progress` - Check import status
- `cancel_import` - Abort ongoing import

### Smart Scheduling
- `get_unassigned_jobs` - List jobs needing assignment
- `suggest_job_assignments` - AI assignment recommendations
- `optimize_route` - Optimize vehicle routes
- `detect_conflicts` - Find scheduling conflicts
- `batch_schedule_jobs` - Schedule multiple jobs
- `apply_assignments` - Confirm and apply assignments

### Compliance Monitoring
- `check_compliance_dashboard` - Overview of all compliance
- `check_scheduled_waste_compliance` - DOE deadline tracking
- `check_vehicle_compliance` - Permit/license tracking
- `check_downstream_compliance` - Buyer license validation
- `generate_compliance_report` - Regulatory reports
- `get_compliance_alerts` - Active alerts summary

### Invoice Intelligence
- `get_aging_report` - AR aging analysis
- `get_client_payment_profile` - Payment behavior
- `generate_collection_strategy` - Collection action plans
- `get_portfolio_metrics` - Overall AR health
- `predict_invoice_payment` - Payment forecasting
- `generate_collection_prompt` - Message/script generation

### ESG Reporting
- `generate_esg_report` - Sustainability reports
- `get_esg_dashboard` - Real-time metrics
- `get_carbon_footprint` - Carbon analysis
- `get_waste_diversion_metrics` - Diversion tracking
- `get_client_sustainability_report` - Client impact

---

## Using the AI Assistant

### Access Methods

1. **Web Interface:** Navigate to AI Assistant page in the frontend
2. **API:** Call `/api/v1/ai/chat-db` for database operations
3. **Chat:** Natural language queries in the chat interface

### Tips for Best Results

1. **Be Specific:** "Show me clients in KL" vs "Show clients"
2. **Use IDs:** "Update client [UUID]" for precise targeting
3. **Specify Time:** "Jobs for tomorrow" vs "Jobs"
4. **Provide Context:** "Urgent collection for XYZ" vs "Collection message"

### Toggle Between Modes

In the AI chat interface, use the toggle switch to select:
- **Database Mode** - For read/write operations
- **Chat Mode** - For general queries and RAG

---

## Support

For issues or questions about AI features:
1. Check this guide for examples
2. Review API documentation at `/docs`
3. Contact system administrator

---

*Last Updated: April 2026*
*Version: 1.0 - All 6 AI Features Active*
