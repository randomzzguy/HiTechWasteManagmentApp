# Product: Hi-Tech Waste Management Platform

An AI-integrated operations platform for **Hi-Tech Waste Management Sdn. Bhd.** (Shah Alam, Malaysia), replacing fragmented spreadsheets and manual processes with a unified intelligence layer.

## Core Purpose
Manage the full lifecycle of industrial, commercial, and institutional (ICI) solid waste operations — from client collection orders through disposal, compliance, and sustainability reporting.

## Key Modules
- **Jobs** — collection order lifecycle: `draft → confirmed → dispatched → in_progress → completed → invoiced`
- **Fleet** — vehicle registry, real-time GPS (MQTT), driver assignment, maintenance scheduling
- **Weighbridge** — tonnage tracking with TimescaleDB time-series storage; diversion rate calculations
- **Scheduled Waste Compliance** — DOE EQA Act 127 / SW codes, 90-day storage rule enforcement, e-SWIS consignment notes
- **Recyclables** — chain-of-custody from client to downstream buyer, recycling certificates
- **Witnessed Destruction** — legally defensible certificates with dual sign-off
- **BSF Farm** — food waste intake → larvae conversion → protein output circularity tracking
- **ESG & Carbon** — Scope 3 Category 5 reporting, SDG alignment, client-facing sustainability reports
- **Finance** — invoice generation, payment tracking, revenue analytics
- **AI Assistant** — RAG-powered chat across all operational data and Malaysian regulatory documents

## User Roles
`superadmin` | `management` | `operations_manager` | `field_supervisor` | `driver` | `compliance_officer` | `client`

## Domain Context
- Malaysian regulatory environment: DOE, EQA Act 127, Scheduled Wastes Regulations 2005, e-SWIS, Cenviro
- Currency: MYR; language: English + Bahasa Malaysia (bilingual reports)
- SW codes follow Malaysia's First Schedule (e.g. SW305, SW410)
