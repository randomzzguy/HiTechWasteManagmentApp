# Design Document: pdf-generation-triggers

## Overview

This feature adds PDF download capability to five dashboard pages by introducing a single reusable `DownloadPdfButton` component and wiring it into each page. Two new API methods are added to `api.ts` (`recyclablesApi.generateCertificatePDF` and `esgApi.downloadReport`). The backend already exposes all five PDF endpoints; this is purely a frontend change.

The scope is intentionally narrow:
- One new shared component (`DownloadPdfButton`)
- Two new lines in `api.ts`
- Five page-level wiring changes (one per page)

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Page Component (Destruction / Finance / Recyclables /  │
│  Compliance/scheduled-waste / ESG)                      │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │  DownloadPdfButton                               │   │
│  │  props: label, onDownload, filename, className   │   │
│  │                                                  │   │
│  │  onClick → onDownload() → Blob                   │   │
│  │         → blobDownload(blob, filename)           │   │
│  │         → toast.success / toast.error            │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  onDownload = () => domainApi.generateXxxPDF(id)        │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  api.ts domain object │
              │  GET /…/pdf/          │
              │  responseType: 'blob' │
              └───────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  FastAPI backend      │
              │  (already exists)     │
              └───────────────────────┘
```

No new routes, no new backend code, no new state management. The component is self-contained: it owns its own `isLoading` boolean via `useState`.

---

## Components and Interfaces

### DownloadPdfButton

**Location:** `frontend/src/components/shared/DownloadPdfButton.tsx`

```typescript
interface DownloadPdfButtonProps {
  label: string
  onDownload: () => Promise<Blob>
  filename?: string        // defaults to "document.pdf"
  className?: string
}
```

**Behaviour:**
1. Renders a shadcn/ui `<Button variant="outline" size="sm">` with a `FileDown` icon from Lucide.
2. On click: sets `isLoading = true`, disables the button, calls `onDownload()`.
3. On resolve: calls `blobDownload(blob, filename)`, fires `toast.success("PDF downloaded successfully")`, sets `isLoading = false`.
4. On reject: fires `toast.error("Failed to download PDF")`, sets `isLoading = false`.
5. While loading: replaces the icon with a `Loader2` spinner (animated via `animate-spin`).

**Blob download utility (inline, not exported):**

```typescript
function blobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
```

The anchor element is never appended to the DOM — `a.click()` works without it in all modern browsers. `revokeObjectURL` is called synchronously after `click()` because the browser has already queued the download by that point.

### api.ts additions

Two methods are added, following the identical pattern of `destructionApi.generateCertificatePDF` and `financeApi.generateInvoicePDF`:

```typescript
// Inside recyclablesApi
generateCertificatePDF: (id: string): Promise<Blob> =>
  api
    .get(`/api/v1/recyclables/chain-of-custody/${id}/pdf/`, {
      responseType: 'blob',
    })
    .then(getData),

// Inside esgApi
downloadReport: (jobId: string): Promise<Blob> =>
  api
    .get(`/api/v1/esg/reports/${jobId}/download/`, {
      responseType: 'blob',
    })
    .then(getData),
```

### Page wiring summary

| Page | Component location | `onDownload` call | `filename` |
|---|---|---|---|
| Destruction | Certificate column, only when `job.certificate_issued === true` | `() => destructionApi.generateCertificatePDF(job.id)` | `destruction-certificate-${job.id}.pdf` |
| Finance | Last column of each invoice row | `() => financeApi.generateInvoicePDF(inv.id)` | `invoice-${inv.id}.pdf` |
| Recyclables | New last column of each record row | `() => recyclablesApi.generateCertificatePDF(r.id)` | `recycling-certificate-${r.id}.pdf` |
| Compliance/scheduled-waste | PDF column of consignment notes table, replaces static Download link | `() => complianceApi.generateConsignmentNotePDF(cn.id as string)` | `consignment-note-${cn.id}.pdf` |
| ESG | Per completed report job entry | `() => esgApi.downloadReport(job.jobId)` | `esg-report-${job.jobId}.pdf` |

**Destruction page detail:** The existing "Certificate" column already shows `<CheckCircle2> Issued` or `<Clock> Pending`. The `DownloadPdfButton` is rendered alongside the "Issued" badge — only when `job.certificate_issued === true`. The "Pending" rows are unchanged.

**Compliance page detail:** The consignment notes sub-table currently renders a static `<Download>` anchor only when `cn.pdf_path` is truthy. This is replaced with `<DownloadPdfButton>` on every row unconditionally, since the API generates the PDF on demand regardless of `pdf_path`.

**ESG page detail:** The ESG page currently shows KPI cards and charts but no report job list. A minimal "Generated Reports" section is added below the SDG tags panel, querying `esgApi.getReportJob` is not needed — the page will use the existing `generateReport` flow's returned `jobId`. In practice the simplest integration is to add a small state-driven list of recently generated report jobs (stored in component state after `generateReport` resolves) and render a `DownloadPdfButton` for each completed one.

---

## Data Models

No new data models are introduced. The feature operates entirely on existing record IDs already present in each page's query results.

The only typing addition is the `DownloadPdfButtonProps` interface defined in the component file itself.

**Existing fields used per page:**

| Page | ID field used |
|---|---|
| Destruction | `DestructionJob.id` + `DestructionJob.certificate_issued` |
| Finance | `Invoice.id` |
| Recyclables | `RecyclableRecord.id` |
| Compliance | consignment note object's `id` field (already fetched via `listConsignmentNotes`) |
| ESG | `jobId` returned by `esgApi.generateReport` |


---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Loading state disables button while download is pending

*For any* `onDownload` function that returns a pending Promise, clicking `DownloadPdfButton` should result in the button being both in a loading visual state and disabled (not clickable) for the entire duration of the pending operation.

**Validates: Requirements 1.2, 1.3**

---

### Property 2: Blob download sequence is always complete

*For any* `Blob` value returned by `onDownload`, the component should call `URL.createObjectURL` with that blob, set the result as the `href` of an anchor element with the correct `download` attribute, trigger a click on that anchor, and then call `URL.revokeObjectURL` with the same URL — in that order.

**Validates: Requirements 1.4, 8.1**

---

### Property 3: Error always restores enabled state

*For any* error thrown or rejected by `onDownload` (regardless of error type, message, or value), after the rejection settles the button should be enabled and not in a loading state.

**Validates: Requirements 1.7**

---

### Property 4: API URL contains the provided id

*For any* valid `id` string passed to `recyclablesApi.generateCertificatePDF` or `esgApi.downloadReport`, the resulting HTTP GET request URL should contain that exact `id` in the correct path position, and the request config should have `responseType: 'blob'`.

**Validates: Requirements 2.2, 7.3**

---

### Property 5: Destruction button visibility matches certificate_issued

*For any* destruction job row, a `DownloadPdfButton` should be rendered if and only if `certificate_issued` is `true`. Rows where `certificate_issued` is `false` must not render the button.

**Validates: Requirements 3.1, 3.3**

---

### Property 6: Filename encodes document type and id

*For any* document id passed to a page's `DownloadPdfButton`, the `filename` prop supplied to the component should equal `"{document-type}-{id}.pdf"` where `{document-type}` is the fixed prefix for that page (`destruction-certificate`, `invoice`, `recycling-certificate`, `consignment-note`, `esg-report`).

**Validates: Requirements 3.4, 4.3, 5.3, 6.3, 7.4**

---

## Error Handling

| Failure scenario | Handling |
|---|---|
| API returns non-2xx (e.g. 404, 500) | Axios rejects; `DownloadPdfButton` catches in its `try/catch`, shows error toast, restores enabled state |
| API returns 401 | Axios response interceptor redirects to `/login` before the component's catch runs |
| `URL.createObjectURL` throws (e.g. empty blob) | Caught by the same `try/catch`; error toast shown |
| User clicks button twice rapidly | Second click is a no-op because button is disabled while first download is pending |
| Network timeout (>30 s) | Axios instance has a 30 s timeout; rejects with a timeout error; component shows error toast |

No error state is persisted beyond the toast — the button always returns to its default enabled state after any failure, allowing the user to retry.

---

## Testing Strategy

### Unit / example-based tests

- Render `DownloadPdfButton` with a mock `onDownload` that resolves — verify `toast.success` is called with `"PDF downloaded successfully"`.
- Render `DownloadPdfButton` with a mock `onDownload` that rejects — verify `toast.error` is called with `"Failed to download PDF"`.
- Render without `filename` prop — verify anchor `download` attribute defaults to `"document.pdf"`.
- Render with `variant="outline"` and `size="sm"` — verify shadcn `Button` receives those props.

### Property-based tests

PBT applies here because the component has clear input/output behavior (props in → DOM state + side-effects out) and several universal properties hold across all inputs. Use **fast-check** (already compatible with the Jest/Vitest setup in Next.js projects).

Each property test runs a minimum of **100 iterations**.

Tag format: `// Feature: pdf-generation-triggers, Property {N}: {property_text}`

| Property | Generator inputs | Assertion |
|---|---|---|
| P1 — Loading disables button | Arbitrary async delay (fc.integer for ms) | Button `disabled` attribute is true while promise is pending |
| P2 — Blob download sequence | `fc.string()` for filename, `fc.uint8Array()` for blob content | `createObjectURL` called → anchor `download` = filename → `revokeObjectURL` called |
| P3 — Error restores state | `fc.anything()` as rejection value | After rejection, button is enabled and spinner is gone |
| P4 — API URL contains id | `fc.uuid()` for id | Request URL matches expected path pattern; `responseType === 'blob'` |
| P5 — Destruction visibility | `fc.boolean()` for `certificate_issued` | Button present iff `certificate_issued === true` |
| P6 — Filename encodes type+id | `fc.uuid()` for id, one of five document types | `filename` prop equals `"{type}-{id}.pdf"` |

### Integration tests

- Mount each page with MSW mocking the relevant PDF endpoint returning a small valid PDF blob — verify the download is triggered end-to-end.
- These are 1–2 examples per page, not property-based, since they test the wiring between page and API rather than logic that varies with input.
