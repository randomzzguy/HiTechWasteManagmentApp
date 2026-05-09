# Implementation Plan: RAG Knowledge Base Manager

## Overview

Extend the Hi-Tech platform with a full-stack document management interface for the RAG knowledge base. Implementation order: backend model → OCR pipeline → endpoint updates → Celery error tracking → Docker/deps → frontend API client → UI components → page integration.

## Tasks

- [x] 1. Extend the Document model and generate the Alembic migration
  - [x] 1.1 Add `file_size_bytes` and `ingestion_error` columns to the `Document` ORM class in `backend/models/document.py`
    - Add `file_size_bytes: Mapped[Optional[int]]` as `BigInteger`, nullable, with comment "Size of the uploaded file in bytes at upload time"
    - Add `ingestion_error: Mapped[Optional[str]]` as `Text`, nullable, with comment "Last error message from a failed ingestion attempt; null on success"
    - Import `BigInteger` from `sqlalchemy` alongside existing imports
    - _Requirements: 8.1, 8.2_

  - [x] 1.2 Update `DocumentRead` Pydantic schema to expose the two new fields
    - Add `file_size_bytes: Optional[int] = None` to `DocumentRead`
    - Add `ingestion_error: Optional[str] = None` to `DocumentRead`
    - _Requirements: 8.6_

  - [x] 1.3 Generate the Alembic migration for the two new columns
    - Run `alembic revision --autogenerate -m "add_document_file_size_ingestion_error"` from `backend/`
    - Verify the generated migration contains `op.add_column('documents', sa.Column('file_size_bytes', sa.BigInteger(), nullable=True))` and the matching `ingestion_error` column
    - Verify the downgrade removes both columns
    - _Requirements: 8.8_

- [x] 2. Extend the OCR pipeline in `backend/rag/pipeline.py`
  - [x] 2.1 Rewrite `_extract_pdf()` with per-page pdfplumber-first, OCR-fallback strategy
    - Replace the current loop body: if `page.extract_text()` returns non-empty text, append it; otherwise call `_ocr_pdf_page(page.page_number - 1, file_path)` and append the result if non-empty
    - _Requirements: 6.1, 6.2, 6.4_

  - [x] 2.2 Add `_ocr_pdf_page(page_index, file_path)` helper function to `pipeline.py`
    - Import `pdf2image.convert_from_path` and `pytesseract` inside the function body guarded by `try/except ImportError`
    - On `ImportError`, log a warning and return `""`
    - Convert the single page using `first_page=page_index+1, last_page=page_index+1`
    - Return `pytesseract.image_to_string(images[0])` if images list is non-empty, else `""`
    - _Requirements: 6.1, 6.3_

  - [x] 2.3 Add `_extract_image(file_path)` function to `pipeline.py`
    - Import `PIL.Image` and `pytesseract` inside the function body guarded by `try/except ImportError`
    - On `ImportError`, log a warning and return `""`
    - Return `pytesseract.image_to_string(Image.open(file_path))`
    - _Requirements: 7.2, 7.4_

  - [x] 2.4 Add image routing branch to `extract_text()` in `pipeline.py`
    - Define `IMAGE_MIMES = {"image/png", "image/jpeg", "image/webp", "image/tiff"}` and `IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".tiff"}` at module level
    - Add a branch before the PDF check: if `mime in IMAGE_MIMES` or the file extension is in `IMAGE_EXTS`, return `_extract_image(file_path)`
    - _Requirements: 7.1, 7.4_

  - [ ]* 2.5 Write property test for OCR fallback trigger logic (Property 1)
    - **Property 1: OCR fallback is triggered iff pdfplumber returns no text**
    - Use `hypothesis` with `@given(pages=st.lists(st.text(), min_size=1, max_size=20))` to mock pdfplumber page objects and assert `_ocr_pdf_page` is called exactly for pages where `extract_text()` returns empty/whitespace
    - **Validates: Requirements 6.1, 6.4**

  - [ ]* 2.6 Write property test for image extraction return type (Property 2)
    - **Property 2: Image extraction always returns a string**
    - Use `hypothesis` with arbitrary valid image paths and mock `pytesseract`/`PIL` to assert `_extract_image()` always returns `str` and never raises, including when pytesseract is unavailable
    - **Validates: Requirements 7.2, 7.3**

- [x] 3. Update `backend/rag/ingestion.py` — extend MIME map for image types
  - Add `.png`, `.jpg`, `.jpeg`, `.webp`, `.tiff` entries to the `mime_map` dict in `ingest_document_from_path()`
  - _Requirements: 7.6_

- [x] 4. Update `backend/routers/ai.py` — endpoint changes
  - [x] 4.1 Add image MIME types to `ALLOWED_MIME_TYPES` in `ingest_document()`
    - Add `"image/png"`, `"image/jpeg"`, `"image/webp"`, `"image/tiff"` to the set
    - _Requirements: 7.5_

  - [x] 4.2 Populate `file_size_bytes` on the `Document` record at creation in `ingest_document()`
    - Pass `file_size_bytes=len(file_content)` when constructing the `Document` ORM instance
    - _Requirements: 8.3_

  - [x] 4.3 Add RBAC guard to `ingest_document()` and tighten `delete_document()`
    - For `ingest_document`: check `current_user.get("role") not in {"management", "superadmin"}` and raise `HTTP 403` with message "Only management roles can upload documents to the knowledge base"
    - For `delete_document`: update the existing role check to only `{"management", "superadmin"}` (remove `operations_manager`)
    - _Requirements: 9.1, 9.2, 9.5_

  - [x] 4.4 Update `list_documents()` response to include `file_size_bytes` and `ingestion_error` per item
    - Add `"file_size_bytes": d.file_size_bytes` and `"ingestion_error": d.ingestion_error` to the dict comprehension in the `items` list
    - _Requirements: 8.7_

  - [x] 4.5 Add `POST /documents/{document_id}/re-ingest` endpoint to `ai.py`
    - Require `management` or `superadmin` role; return `HTTP 403` otherwise
    - Fetch `Document` by `document_id`; return `HTTP 404` if not found
    - Reset `doc.ingestion_error = None` and `doc.ingested_into_rag = False`, then `await db.flush()`
    - Re-queue `ingest_document_task.delay(...)` with the existing `doc.file_path`, `doc.milvus_collection`, `doc.client_id`, `doc.doc_type`
    - Return `{ document_id, title, ingested_into_rag: False, ingestion_error: None, task_id, message }`
    - _Requirements: 5.2, 5.5, 8.5_

  - [ ]* 4.6 Write property test for RBAC on write endpoints (Property 6)
    - **Property 6: Role-based access control on write endpoints**
    - Use `hypothesis` with `@given(role=st.sampled_from(['driver', 'field_supervisor', 'client', 'compliance_officer']))` and FastAPI `TestClient` to assert `POST /ingest-document` and `DELETE /documents/{id}` return `HTTP 403`
    - **Validates: Requirements 9.1, 9.2, 9.5**

  - [ ]* 4.7 Write property test for read endpoint accessibility (Property 7)
    - **Property 7: Read endpoint is accessible to all authenticated users**
    - Use `hypothesis` with `@given(role=st.sampled_from(['driver', 'management', 'superadmin', 'client', 'operations_manager']))` to assert `GET /documents` returns `HTTP 200`
    - **Validates: Requirements 9.3**

  - [ ]* 4.8 Write property test for re-ingest error state reset (Property 5)
    - **Property 5: Re-ingest resets error state**
    - For any `Document` with a non-null `ingestion_error`, assert that after calling `POST /documents/{id}/re-ingest` the response has `ingestion_error = null` and `ingested_into_rag = false`
    - **Validates: Requirements 5.5, 8.5**

- [x] 5. Update `backend/tasks/rag_tasks.py` — ingestion error tracking
  - [x] 5.1 Add `error_message: Optional[str] = None` parameter to `_mark_document_status()`
    - Update the SQL `UPDATE` statement to also set `ingestion_error = :error_msg`
    - _Requirements: 8.4, 8.5_

  - [x] 5.2 Pass error strings to `_mark_document_status()` on all failure paths in `ingest_document_task`
    - "No text could be extracted from the document" path → pass that string as `error_message`
    - "No chunks could be generated from the document text" path → pass that string
    - "All chunk embeddings failed" path → pass that string
    - `SoftTimeLimitExceeded` path → pass `"Task timed out"`
    - Generic `except Exception` path → pass `str(exc)`
    - On success path → pass `error_message=None`
    - _Requirements: 8.4_

  - [x] 5.3 Add `on_failure` hook to `RAGBaseTask` that calls `_mark_document_status` with the exception string
    - Extract `document_id` from `args[0]` (first positional arg) or `kwargs.get("document_id")`
    - Call `_mark_document_status(document_id, ingested=False, error_message=repr(exc))`
    - _Requirements: 8.4_

  - [x] 5.4 Update the MIME map in `ingest_document_task` to include image extensions
    - Mirror the same image extension entries added to `ingestion.py` in task 3
    - _Requirements: 7.1_

  - [ ]* 5.5 Write property test for ingestion error written on task failure (Property 4)
    - **Property 4: Ingestion error is written on task failure**
    - Use `hypothesis` with `@given(error_msg=st.text(min_size=1))` to assert that after `_mark_document_status(doc_id, ingested=False, error_message=error_msg)`, the DB row has `ingestion_error` equal to the provided string
    - **Validates: Requirements 8.4**

- [x] 6. Update Docker and Python dependencies
  - [x] 6.1 Add `pytesseract` and `pdf2image` to `backend/requirements.txt`
    - Add `pytesseract>=0.3.13` and `pdf2image>=1.17.0` under the PDF/processing section
    - _Requirements: 6.7_

  - [x] 6.2 Add `tesseract-ocr` and `poppler-utils` system packages to `backend/Dockerfile`
    - Add `RUN apt-get update && apt-get install -y tesseract-ocr poppler-utils && rm -rf /var/lib/apt/lists/*` before the `pip install` step
    - _Requirements: 6.6_

- [x] 7. Add `aiApi` methods to `frontend/src/lib/api.ts`
  - Add `listDocuments`, `uploadDocument`, `deleteDocument`, `reIngestDocument`, `getRagStatus` to the `aiApi` export object
  - `uploadDocument` must use `Content-Type: multipart/form-data`
  - Follow the existing Axios instance pattern used by other domain API objects in `api.ts`
  - _Requirements: 2.5, 4.3, 5.2_

- [x] 8. Implement `KnowledgeBaseManager` and sub-components
  - [x] 8.1 Create `frontend/src/components/ai/KbStatsBar.tsx`
    - Accept `{ total, ingested, pending, milvusChunks }` props
    - Render four metric cards using `slate-800` card style and `emerald-500` accent
    - Use Lucide icons: `FileText` (total), `CheckCircle2` (ingested), `Clock` (pending), `Database` (chunks)
    - _Requirements: 1.7, 10.4, 10.6_

  - [x] 8.2 Create `frontend/src/components/ai/KbDocumentTable.tsx`
    - Accept `{ documents, isManagement, onDelete, onReIngest, isDeleting, isReIngesting }` props
    - Render a shadcn `Table` with columns: Title, Type, Size (formatted bytes), Status badge, Uploaded (relative date), Actions
    - Implement `deriveStatus(doc)` helper: `ingestion_error` → `'failed'`, `ingested_into_rag` → `'ingested'`, else `'pending'`
    - Status badge colours: `bg-emerald-500/20 text-emerald-400` (ingested), `bg-amber-500/20 text-amber-400` (pending), `bg-red-500/20 text-red-400` (failed)
    - Show delete button and re-ingest button (on failed rows only) conditionally when `isManagement` is true
    - Show `ingestion_error` in a `Tooltip` on the failed badge
    - Add horizontal scroll wrapper for viewports < 768px
    - _Requirements: 1.1, 1.5, 1.6, 4.1, 5.1, 10.5, 10.7_

  - [x] 8.3 Create `frontend/src/components/ai/KbUploadDialog.tsx`
    - Accept `{ open, onOpenChange, onSubmit, isUploading }` props
    - Render a shadcn `Dialog` with: file input (`accept=".pdf,.docx,.txt,.csv,.md,.png,.jpg,.jpeg,.webp,.tiff"`), title text field (max 500 chars), doc_type `Select`, optional client `Select`
    - Client-side validation: file > 50 MB shows an inline error and blocks submission
    - Show upload progress indicator while `isUploading` is true
    - _Requirements: 2.2, 2.3, 2.4, 2.5, 2.8_

  - [x] 8.4 Create `frontend/src/components/ai/KbDeleteConfirmDialog.tsx`
    - Accept `{ open, onOpenChange, document, onConfirm, isDeleting }` props
    - Render a shadcn `AlertDialog` naming the document title and warning about Milvus removal
    - Show loading state on the confirm button while `isDeleting` is true
    - _Requirements: 4.2, 4.3_

  - [x] 8.5 Create `frontend/src/components/ai/KnowledgeBaseManager.tsx`
    - Mark `'use client'` at the top
    - Use `useSession()` from `next-auth/react` to derive `isManagement = ['management', 'superadmin'].includes(session?.user?.role ?? '')`
    - Implement `useQuery` for `['ai-documents']` and `['rag-status']` with `refetchInterval: hasPendingDocs ? 10_000 : false`
    - Implement `uploadMutation`, `deleteMutation`, `reIngestMutation` with `queryClient.invalidateQueries({ queryKey: ['ai-documents'] })` on success
    - Wire status-transition toasts by comparing previous query data with new data in `onSuccess`
    - Render loading skeleton (3 rows), error state with retry button, and empty state as per requirements
    - Compose `KbStatsBar`, `KbDocumentTable`, `KbUploadDialog`, `KbDeleteConfirmDialog`
    - _Requirements: 1.2, 1.3, 1.4, 2.6, 2.7, 3.1, 3.2, 3.3, 3.4, 3.5, 4.4, 4.5, 5.3, 5.4, 9.4_

  - [ ]* 8.6 Write property test for status badge determinism (Property 8)
    - **Property 8: Status badge colour is deterministic from document fields**
    - Use `fast-check` with `fc.record({ ingested_into_rag: fc.boolean(), ingestion_error: fc.option(fc.string()) })` to assert `deriveStatus` always returns the same value for the same inputs
    - **Validates: Requirements 1.5, 10.7**

  - [ ]* 8.7 Write property test for polling interval logic (Property 9)
    - **Property 9: Polling is active iff pending documents exist**
    - Use `fast-check` with `fc.array(fc.record({ ingested_into_rag: fc.boolean(), ingestion_error: fc.option(fc.string()) }))` to assert `refetchInterval` is `10_000` iff at least one doc has `ingested_into_rag=false` and `ingestion_error=null`
    - **Validates: Requirements 3.1, 3.2**

  - [ ]* 8.8 Write property test for stats bar count consistency (Property 10)
    - **Property 10: Stats bar counts are consistent with document list**
    - Use `fast-check` with an array of document records to assert the derived total, ingested, and pending counts match the counts computed directly from the array
    - **Validates: Requirements 3.5, 1.7**

  - [ ]* 8.9 Write property test for management-only UI controls (Property 11)
    - **Property 11: Management-only UI controls are hidden from non-management users**
    - Use `fast-check` with `fc.constantFrom('driver', 'field_supervisor', 'client', 'compliance_officer')` to render `KbDocumentTable` with `isManagement=false` and assert upload, delete, and re-ingest buttons are absent from the rendered output
    - **Validates: Requirements 2.1, 4.1, 5.1, 9.4**

- [x] 9. Integrate `KnowledgeBaseManager` into the AI Assistant page
  - Convert `frontend/src/app/(dashboard)/ai-assistant/page.tsx` to a `'use client'` component
  - Wrap the page content in shadcn `Tabs` with `defaultValue="assistant"`
  - Add `TabsList` with two `TabsTrigger` items: `"assistant"` (label "AI Assistant") and `"knowledge-base"` (label "Knowledge Base")
  - Move the existing grid layout (AIAssistantChat + sidebar) into `<TabsContent value="assistant">`
  - Add `<TabsContent value="knowledge-base"><KnowledgeBaseManager /></TabsContent>`
  - Remove the `export const metadata` export (incompatible with `'use client'`)
  - _Requirements: 10.1, 10.2, 10.3_

- [x] 10. Checkpoint — verify end-to-end correctness
  - Verify the Alembic migration applies cleanly with `alembic upgrade head`
  - Verify `GET /api/v1/ai/documents` response includes `file_size_bytes` and `ingestion_error` fields
  - Verify `POST /api/v1/ai/ingest-document` accepts a PNG file and returns a task_id
  - Verify `POST /api/v1/ai/documents/{id}/re-ingest` resets `ingestion_error` to null
  - Run `npm run lint` from `frontend/` and fix any reported issues
  - Ensure all non-optional tests pass
  - Ask the user if any questions arise before proceeding

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Property tests use `hypothesis` (Python backend) and `fast-check` (TypeScript frontend)
- The Alembic migration (task 1.3) must be run before starting the backend after these changes
- The Docker image must be rebuilt after tasks 6.1 and 6.2 to install `tesseract-ocr` and `poppler-utils`
- `operations_manager` is intentionally excluded from write-endpoint RBAC per requirements 9.1 and 9.2
- The `aiApi` object may already partially exist in `api.ts` — check before adding duplicate methods
