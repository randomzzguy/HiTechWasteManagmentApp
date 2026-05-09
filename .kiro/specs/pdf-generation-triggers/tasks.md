# Implementation Plan: pdf-generation-triggers

## Overview

Add PDF download capability to five dashboard pages via a shared `DownloadPdfButton` component, two new `api.ts` methods, and targeted wiring changes. All changes are frontend-only.

## Tasks

- [x] 1. Add missing API methods to `api.ts`
  - Add `generateCertificatePDF: (id: string) => Promise<Blob>` to `recyclablesApi`, issuing GET `/api/v1/recyclables/chain-of-custody/{id}/pdf/` with `responseType: 'blob'`
  - Add `downloadReport: (jobId: string) => Promise<Blob>` to `esgApi`, issuing GET `/api/v1/esg/reports/{jobId}/download/` with `responseType: 'blob'`
  - Follow the identical pattern of `destructionApi.generateCertificatePDF` and `financeApi.generateInvoicePDF` already in the file
  - _Requirements: 2.1, 2.2, 2.3, 7.3_

- [x] 2. Create `DownloadPdfButton` component
  - [x] 2.1 Implement `frontend/src/components/shared/DownloadPdfButton.tsx`
    - Mark `'use client'`; accept props `{ label, onDownload, filename?, className? }`
    - Use shadcn/ui `<Button variant="outline" size="sm">` with `FileDown` icon (Lucide)
    - On click: set `isLoading = true`, disable button, call `onDownload()`
    - On resolve: call inline `blobDownload(blob, filename ?? 'document.pdf')`, fire `toast.success("PDF downloaded successfully")`, set `isLoading = false`
    - On reject: fire `toast.error("Failed to download PDF")`, set `isLoading = false`
    - While loading: replace icon with `<Loader2 className="animate-spin" />`
    - `blobDownload`: create object URL, set anchor `href` + `download`, call `a.click()`, revoke URL — anchor never appended to DOM
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 8.1, 8.2_

  - [ ]* 2.2 Write property tests for `DownloadPdfButton`
    - Use fast-check; minimum 100 iterations each
    - **Property 1: Loading state disables button while download is pending** — arbitrary async delay; assert `disabled` is true throughout — _Validates: Requirements 1.2, 1.3_
    - **Property 2: Blob download sequence is always complete** — `fc.string()` filename + `fc.uint8Array()` blob content; assert `createObjectURL` → anchor `download` attr → `revokeObjectURL` order — _Validates: Requirements 1.4, 8.1_
    - **Property 3: Error always restores enabled state** — `fc.anything()` as rejection value; assert button enabled and spinner absent after rejection — _Validates: Requirements 1.7_

- [x] 3. Wire into Destruction page
  - Import `DownloadPdfButton` in `frontend/src/app/(dashboard)/destruction/page.tsx`
  - In the Certificate column, render `<DownloadPdfButton>` alongside the "Issued" badge only when `job.certificate_issued === true`; "Pending" rows unchanged
  - `onDownload`: `() => destructionApi.generateCertificatePDF(job.id)`
  - `filename`: `destruction-certificate-${job.id}.pdf`
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [ ]* 3.1 Write property test for Destruction button visibility
    - **Property 5: Destruction button visibility matches certificate_issued** — `fc.boolean()` for `certificate_issued`; assert button present iff `true` — _Validates: Requirements 3.1, 3.3_

- [x] 4. Wire into Finance page
  - Import `DownloadPdfButton` in `frontend/src/app/(dashboard)/finance/page.tsx`
  - Add a download cell to each invoice row (last column before the View chevron)
  - `onDownload`: `() => financeApi.generateInvoicePDF(inv.id)`
  - `filename`: `invoice-${inv.id}.pdf`
  - _Requirements: 5.1, 5.2, 5.3_

- [x] 5. Wire into Recyclables page
  - Import `DownloadPdfButton` in `frontend/src/app/(dashboard)/recyclables/page.tsx`
  - Add a new last column to each chain-of-custody record row
  - `onDownload`: `() => recyclablesApi.generateCertificatePDF(r.id)`
  - `filename`: `recycling-certificate-${r.id}.pdf`
  - _Requirements: 6.1, 6.2, 6.3_

- [x] 6. Wire into Compliance / Scheduled-Waste page
  - Import `DownloadPdfButton` in `frontend/src/app/(dashboard)/compliance/scheduled-waste/page.tsx`
  - Replace the existing static `<Download>` anchor (currently conditional on `cn.pdf_path`) with `<DownloadPdfButton>` on every consignment note row unconditionally
  - `onDownload`: `() => complianceApi.generateConsignmentNotePDF(cn.id as string)`
  - `filename`: `consignment-note-${cn.id}.pdf`
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [x] 7. Wire into ESG page
  - Import `DownloadPdfButton` in `frontend/src/app/(dashboard)/esg/page.tsx`
  - Add a `generatedReports` state array (`useState<{ jobId: string }[]>`)
  - After `esgApi.generateReport` resolves, push the returned `jobId` into `generatedReports`
  - Render a "Generated Reports" section below the SDG tags panel listing each entry with a `<DownloadPdfButton>`
  - `onDownload`: `() => esgApi.downloadReport(job.jobId)`
  - `filename`: `esg-report-${job.jobId}.pdf`
  - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [x] 8. Checkpoint — lint and type check
  - Run `npm run lint` and `npx tsc --noEmit` from `frontend/`; resolve all errors before considering the feature complete
  - Ensure all tests pass, ask the user if questions arise.
