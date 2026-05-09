# Requirements Document

## Introduction

This feature adds PDF download triggers to the Hi-Tech Waste Management Platform frontend. The backend already exposes five PDF generation endpoints (destruction certificates, recycling chain-of-custody certificates, consignment notes, ESG reports, and invoices) but the frontend has no UI controls to invoke them. This feature introduces a reusable `DownloadPdfButton` component and wires it into the Destruction, Recyclables, Compliance/Scheduled-Waste, Finance, and ESG pages. It also adds the missing `generateCertificatePDF` method to `recyclablesApi` in `api.ts`.

## Glossary

- **DownloadPdfButton**: A reusable React client component that accepts an async download function, triggers a Blob-to-file download in the browser, and provides loading and error feedback.
- **Blob Download Pattern**: The sequence of calling an API endpoint with `responseType: 'blob'`, creating an object URL via `URL.createObjectURL`, programmatically clicking a hidden anchor element, and then revoking the object URL.
- **Sonner Toast**: The toast notification library already installed in the platform, used for success and error feedback.
- **recyclablesApi**: The Axios-backed API client object in `frontend/src/lib/api.ts` that handles all `/api/v1/recyclables/` endpoints.
- **destructionApi**: The Axios-backed API client object in `frontend/src/lib/api.ts` that handles all `/api/v1/destruction/` endpoints.
- **complianceApi**: The Axios-backed API client object in `frontend/src/lib/api.ts` that handles all `/api/v1/compliance/` endpoints.
- **financeApi**: The Axios-backed API client object in `frontend/src/lib/api.ts` that handles all `/api/v1/finance/` endpoints.
- **esgApi**: The Axios-backed API client object in `frontend/src/lib/api.ts` that handles all `/api/v1/esg/` endpoints.
- **Chain-of-Custody Record**: A recyclable material record that has a traceable path from client to downstream buyer, identified by a UUID, accessible via `/api/v1/recyclables/chain-of-custody/{id}/pdf/`.
- **Destruction Certificate**: A legally defensible document issued for a witnessed destruction job, identified by a UUID, accessible via `/api/v1/destruction/certificates/{id}/pdf/`.
- **Consignment Note**: A DOE-mandated scheduled waste transport document, identified by a UUID, accessible via `/api/v1/compliance/consignment-notes/{id}/pdf/`.
- **ESG Report**: A generated sustainability report identified by a job UUID, accessible via `/api/v1/esg/reports/{jobId}/download/`.
- **Invoice PDF**: A finance invoice document identified by a UUID, accessible via `/api/v1/finance/invoices/{id}/pdf/`.

---

## Requirements

### Requirement 1: Reusable DownloadPdfButton Component

**User Story:** As a platform user, I want a consistent PDF download button across all pages, so that I have a predictable experience when downloading any document type.

#### Acceptance Criteria

1. THE `DownloadPdfButton` SHALL accept a `label` prop of type `string`, an `onDownload` prop of type `() => Promise<Blob>`, and an optional `className` prop of type `string`.
2. WHEN the user clicks `DownloadPdfButton`, THE `DownloadPdfButton` SHALL call the `onDownload` function and display a loading spinner in place of the download icon for the duration of the async operation.
3. WHILE the `onDownload` function is pending, THE `DownloadPdfButton` SHALL disable the button to prevent duplicate concurrent download requests.
4. WHEN the `onDownload` function resolves with a `Blob`, THE `DownloadPdfButton` SHALL trigger a browser file download using `URL.createObjectURL` and a programmatically clicked anchor element, then revoke the object URL via `URL.revokeObjectURL`.
5. WHEN the `onDownload` function resolves successfully, THE `DownloadPdfButton` SHALL display a Sonner success toast with the message "PDF downloaded successfully".
6. IF the `onDownload` function rejects with an error, THEN THE `DownloadPdfButton` SHALL display a Sonner error toast with the message "Failed to download PDF".
7. IF the `onDownload` function rejects with an error, THEN THE `DownloadPdfButton` SHALL restore the button to its non-loading, enabled state.
8. THE `DownloadPdfButton` SHALL be implemented as a `'use client'` component located at `frontend/src/components/shared/DownloadPdfButton.tsx`.
9. THE `DownloadPdfButton` SHALL use the shadcn/ui `Button` component as its base element with the `variant="outline"` and `size="sm"` defaults.

---

### Requirement 2: Add generateCertificatePDF to recyclablesApi

**User Story:** As a developer, I want a `generateCertificatePDF` method on `recyclablesApi`, so that the Recyclables page can download chain-of-custody certificates using the same API client pattern as other domains.

#### Acceptance Criteria

1. THE `recyclablesApi` object in `frontend/src/lib/api.ts` SHALL expose a `generateCertificatePDF` method with the signature `(id: string) => Promise<Blob>`.
2. WHEN `recyclablesApi.generateCertificatePDF` is called with a valid `id`, THE `recyclablesApi` SHALL issue a GET request to `/api/v1/recyclables/chain-of-custody/{id}/pdf/` with `responseType: 'blob'`.
3. THE `recyclablesApi.generateCertificatePDF` method SHALL follow the same implementation pattern as `destructionApi.generateCertificatePDF` and `financeApi.generateInvoicePDF` already present in `api.ts`.

---

### Requirement 3: Destruction Certificate Download Button

**User Story:** As an operations manager, I want a "Download Certificate" button on each destruction certificate row, so that I can retrieve the legally defensible PDF for any completed destruction job.

#### Acceptance Criteria

1. WHEN the Destruction page renders a certificate row where `certificate_issued` is `true`, THE Destruction Page SHALL display a `DownloadPdfButton` labelled "Download Certificate" in that row's action column.
2. WHEN the user clicks the "Download Certificate" button on a destruction certificate row, THE Destruction Page SHALL call `destructionApi.generateCertificatePDF` with the certificate's `id` and pass the result to the `DownloadPdfButton`'s `onDownload` prop.
3. WHILE `certificate_issued` is `false` on a destruction job row, THE Destruction Page SHALL NOT render a `DownloadPdfButton` for that row.
4. THE downloaded destruction certificate file SHALL be saved with the filename `destruction-certificate-{id}.pdf`.

---

### Requirement 4: Consignment Note PDF Download Button

**User Story:** As a compliance officer, I want a "Download PDF" button on each consignment note row, so that I can retrieve the DOE-mandated consignment note document for record-keeping and submission.

#### Acceptance Criteria

1. WHEN the Scheduled Waste page renders a consignment note row, THE Scheduled Waste Page SHALL display a `DownloadPdfButton` labelled "Download PDF" in that row's PDF column.
2. WHEN the user clicks the "Download PDF" button on a consignment note row, THE Scheduled Waste Page SHALL call `complianceApi.generateConsignmentNotePDF` with the consignment note's `id` and pass the result to the `DownloadPdfButton`'s `onDownload` prop.
3. THE downloaded consignment note file SHALL be saved with the filename `consignment-note-{id}.pdf`.
4. THE `DownloadPdfButton` for consignment notes SHALL replace the existing static "Download" link that currently renders only when `cn.pdf_path` is truthy, making the download available for all consignment note rows regardless of `pdf_path`.

---

### Requirement 5: Invoice PDF Download Button

**User Story:** As a finance officer, I want a "Download Invoice" button on each invoice row, so that I can retrieve the invoice PDF for billing and audit purposes.

#### Acceptance Criteria

1. WHEN the Finance page renders an invoice row, THE Finance Page SHALL display a `DownloadPdfButton` labelled "Download Invoice" in that row's action column.
2. WHEN the user clicks the "Download Invoice" button on an invoice row, THE Finance Page SHALL call `financeApi.generateInvoicePDF` with the invoice's `id` and pass the result to the `DownloadPdfButton`'s `onDownload` prop.
3. THE downloaded invoice file SHALL be saved with the filename `invoice-{id}.pdf`.

---

### Requirement 6: Recyclables Chain-of-Custody Certificate Download Button

**User Story:** As an operations manager, I want a "Download Certificate" button on each chain-of-custody record row, so that I can retrieve the recycling certificate for downstream buyer verification.

#### Acceptance Criteria

1. WHEN the Recyclables page renders a chain-of-custody record row, THE Recyclables Page SHALL display a `DownloadPdfButton` labelled "Download Certificate" in that row's action column.
2. WHEN the user clicks the "Download Certificate" button on a chain-of-custody record row, THE Recyclables Page SHALL call `recyclablesApi.generateCertificatePDF` with the record's `id` and pass the result to the `DownloadPdfButton`'s `onDownload` prop.
3. THE downloaded recycling certificate file SHALL be saved with the filename `recycling-certificate-{id}.pdf`.

---

### Requirement 7: ESG Report Download Button

**User Story:** As a sustainability manager, I want a "Download Report" button on completed ESG report jobs, so that I can retrieve the generated sustainability PDF for client distribution.

#### Acceptance Criteria

1. WHEN the ESG page renders a completed report job entry, THE ESG Page SHALL display a `DownloadPdfButton` labelled "Download Report" for that entry.
2. WHEN the user clicks the "Download Report" button on an ESG report entry, THE ESG Page SHALL call `esgApi.downloadReport` with the report's `jobId` and pass the result to the `DownloadPdfButton`'s `onDownload` prop.
3. THE `esgApi` object in `frontend/src/lib/api.ts` SHALL expose a `downloadReport` method with the signature `(jobId: string) => Promise<Blob>` that issues a GET request to `/api/v1/esg/reports/{jobId}/download/` with `responseType: 'blob'`.
4. THE downloaded ESG report file SHALL be saved with the filename `esg-report-{jobId}.pdf`.

---

### Requirement 8: Filename Derivation for Downloads

**User Story:** As a platform user, I want downloaded PDF files to have meaningful, predictable filenames, so that I can identify documents in my filesystem without opening them.

#### Acceptance Criteria

1. THE `DownloadPdfButton` SHALL accept an optional `filename` prop of type `string` that, when provided, sets the `download` attribute on the anchor element used to trigger the file save.
2. IF the `filename` prop is not provided, THEN THE `DownloadPdfButton` SHALL use `"document.pdf"` as the default filename.
3. THE calling page component SHALL always supply a `filename` prop to `DownloadPdfButton` using the pattern `"{document-type}-{id}.pdf"` as specified in Requirements 3 through 7.
