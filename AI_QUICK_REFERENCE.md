# AI Assistant - Quick Reference Card

**6 AI Features | 30+ Functions | One Chat Interface**

---

## 🗄️ 1. DATABASE AGENT
**Read/Write Database via Natural Language**

| What You Can Say | What It Does |
|------------------|--------------|
| "Show all clients in KL" | Query database |
| "Add new client ABC Sdn Bhd" | Create records |
| "Update client status to active" | Update records |
| "Delete the test job" | Delete records |
| "Find jobs for tomorrow" | Search with filters |

**Supported:** Clients, Jobs, Vehicles, Invoices, Employees, Waste Records, BSF, Destruction

---

## 📁 2. BULK IMPORT AGENT
**CSV/Excel Import with AI Validation**

| Feature | Benefit |
|---------|---------|
| Drag & Drop | Upload CSV/Excel files |
| Auto Column Mapping | AI matches columns to fields |
| Data Validation | Catches errors before import |
| Preview Mode | Review before committing |

**Supported:** Clients, Jobs, Waste Records, Invoices, Vehicles, Employees

**How:** Click paperclip icon in chat → Drop file → Review mappings → Import

---

## 📅 3. SMART SCHEDULING AGENT
**Auto-Assign Jobs & Optimize Routes**

| Function | Description |
|----------|-------------|
| `Suggest Assignments` | Best vehicle/driver for jobs |
| `Optimize Route` | Minimize travel time/fuel |
| `Detect Conflicts` | Find scheduling overlaps |
| `Batch Schedule` | Schedule multiple jobs |

**Example:**
```
"Suggest assignments for today's unassigned jobs"
"Optimize route for Vehicle PJ1234"
"Check for scheduling conflicts this week"
```

---

## ⚖️ 4. COMPLIANCE MONITORING AGENT
**Track Permits, Licenses & Deadlines**

| Monitored Item | Alert Levels |
|----------------|--------------|
| Scheduled Waste (DOE 90/180 day) | 🟡 30 days / 🔴 7 days / 🚨 Expired |
| Vehicle Road Tax | 🟡 30 days / 🔴 7 days / 🚨 Expired |
| Vehicle Insurance | 🟡 30 days / 🔴 7 days / 🚨 Expired |
| PUSPAKOM Inspection | 🟡 30 days / 🔴 7 days / 🚨 Expired |
| Downstream Licenses | 🟡 30 days / 🔴 7 days / 🚨 Expired |
| Destruction Certificates | Track issuance status |
| Consignment Notes | DOE tracking compliance |

**Example:**
```
"Show compliance dashboard"
"Check DOE compliance for client ABC"
"Generate Q1 2026 compliance report"
```

---

## 💰 5. INVOICE INTELLIGENCE AGENT
**AR Aging, Collections & Payment Predictions**

| Feature | What It Does |
|---------|--------------|
| **Aging Report** | AR by buckets (current, 30, 60, 90, 120+) |
| **Risk Scoring** | AI assesses invoice risk |
| **Client Profile** | Payment behavior analysis |
| **Collection Strategy** | Tailored action plans |
| **Payment Prediction** | ML-based probability |
| **Collection Prompts** | AI email/call scripts |

**Collection Tones:** Professional | Friendly | Firm | Urgent

**Example:**
```
"Show aging report"
"Get collection strategy for client XYZ"
"Generate urgent collection message for ABC"
"Will invoice INV-2026-015 be paid on time?"
```

---

## 🌱 6. ESG REPORT GENERATION AGENT
**Sustainability Reports & Carbon Tracking**

| Component | Metrics |
|-----------|---------|
| **Carbon** | Emissions, avoidance, net impact, trees equivalent |
| **Waste** | Diversion rate, recycling, circular economy |
| **Social** | Clients served, jobs completed |
| **Governance** | Compliance, audit findings |
| **SDG** | UN Sustainable Development Goals mapping |

**SDGs Contributed To:**
- 12: Responsible Consumption (waste diversion)
- 13: Climate Action (carbon avoidance)
- 11: Sustainable Cities (urban waste)
- 8: Decent Work (job creation)

**Example:**
```
"Generate ESG report for April 2026"
"Show ESG dashboard"
"Generate sustainability report for client ABC"
"What's our carbon footprint this month?"
"Which SDGs are we contributing to?"
```

---

## 🎯 QUICK COMMANDS

### Database
- "Show [entity] where [condition]"
- "Create [entity] with [details]"
- "Update [entity] [id] set [field] to [value]"
- "Delete [entity] [id]"

### Import
- Drop CSV/Excel file in chat
- "Preview this import"
- "Execute import"

### Scheduling
- "Suggest assignments for [date]"
- "Optimize route for [vehicle]"
- "Check for conflicts"

### Compliance
- "Show compliance dashboard"
- "Check [type] compliance for [client]"
- "Generate [period] compliance report"

### Invoices
- "Show aging report"
- "Get collection strategy for [client]"
- "Generate [tone] collection message for [client]"

### ESG
- "Generate ESG report for [period]"
- "Show ESG dashboard"
- "Generate client sustainability report for [client]"

---

## 📊 SYSTEM STATUS

All 6 AI Features: ✅ **ACTIVE**

| Feature | Status | Functions |
|---------|--------|-----------|
| Database Agent | ✅ Live | 5 |
| Bulk Import | ✅ Live | 4 |
| Smart Scheduling | ✅ Live | 6 |
| Compliance Monitoring | ✅ Live | 6 |
| Invoice Intelligence | ✅ Live | 6 |
| ESG Reporting | ✅ Live | 5 |

**Total:** 30+ AI Functions Available

---

## 📖 FULL DOCUMENTATION

- **Detailed Guide:** [AI_FEATURES_GUIDE.md](./AI_FEATURES_GUIDE.md)
- **API Docs:** http://localhost:8000/docs (when running)
- **Project README:** [README.md](./README.md)

---

## 💡 TIPS FOR BEST RESULTS

1. **Be Specific:** "Clients in KL" vs "Show clients"
2. **Use IDs:** "Update client [UUID]" for precision
3. **Specify Time:** "Jobs for tomorrow" vs "Jobs"
4. **Provide Context:** "Urgent collection for XYZ" vs "Collection message"

---

**Toggle Mode:** Use the switch in chat to select Database Mode vs Chat Mode

---

*Quick Reference v1.0 | April 2026*
