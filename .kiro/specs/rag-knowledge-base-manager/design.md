# Design Document: RAG Knowledge Base Manager

## Overview

The RAG Knowledge Base Manager extends the Hi-Tech Waste Management platform's AI Assistant page with a dedicated document management interface. It allows authorised users to view, upload, delete, and re-trigger ingestion of documents that feed the AI assistant's RAG pipeline.

The feature spans three layers:

1. **Backend model extension** — two new columns (`file_size_bytes`, `ingestion_error`) on the `documents` table, surfaced through updated Pydantic schemas and a new re-ingest endpoint.
2. **OCR pipeline extension** — pdfplumber-first, OCR-fallback per page for scanned PDFs, plus a new `_extract_image()` path for PNG/JPEG/WEBP/TIFF uploads.
3. **Frontend UI** — a `KnowledgeBaseManager` React component added as a second tab on the `/ai-assistant` page, using TanStack Query for data fetching and polling.

---

## Architecture

```
Frontend
  AI Assistant Page
    Tab 1: AIAssistantChat + Sidebar (unchanged)
    Tab 2: KnowledgeBaseManager
      KbStatsBar
      KbDocumentTable
      KbUploadDialog
      KbDeleteConfirmDialog

API Layer
  GET  /api/v1/ai/documents          → list_documents
  POST /api/v1/ai/ingest-document    → ingest_document (updated)
  DELETE /api/v1/ai/documents/:id    → delete_document (updated RBAC)
  POST /api/v1/ai/documents/:id/re-ingest → re_ingest_document (NEW)
  GET  /api/v1/ai/rag-status         → rag_status

Backend
  ingest_document → Document DB record + ingest_document_task (Celery)
  ingest_document_task → pipeline.py extract_text
    PDF  → _extract_pdf (pdfplumber + _ocr_pdf_page fallback per page)
    Image → _extract_image (pytesseract, NEW)
  → Milvus vector store
  → _mark_document_status (writes ingestion_error on failure)
```

---

## Components and Interfaces

### Backend: `backend/models/document.py`

Two new columns on the `Document` ORM class:

```python
from sqlalchemy import BigInteger

file_size_bytes: Mapped[Optional[int]] = mapped_column(
    BigInteger, nullable=True,
    comment="Size of the uploaded file in bytes at upload time"
)
ingestion_error: Mapped[Optional[str]] = mapped_column(
    Text, nullable=True,
    comment="Last error message from a failed ingestion attempt; null on success"
)
```

`DocumentRead` updated:

```python
class DocumentRead(BaseModel):
    # ... existing fields ...
    file_size_bytes: Optional[int] = None
    ingestion_error: Optional[str] = None
```

### Backend: `backend/rag/pipeline.py`

`_extract_pdf()` rewritten with per-page pdfplumber-first, OCR-fallback:

```python
def _extract_pdf(file_path: str) -> str:
    pages = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text and text.strip():
                pages.append(text)
            else:
                ocr_text = _ocr_pdf_page(page.page_number - 1, file_path)
                if ocr_text:
                    pages.append(ocr_text)
    return "\n\n".join(pages)

def _ocr_pdf_page(page_index: int, file_path: str) -> str:
    try:
        from pdf2image import convert_from_path
        import pytesseract
        images = convert_from_path(file_path, first_page=page_index+1, last_page=page_index+1)
        return pytesseract.image_to_string(images[0]) if images else ""
    except ImportError:
        logger.warning("pytesseract/pdf2image not available; OCR skipped for page %d", page_index)
        return ""

def _extract_image(file_path: str) -> str:
    try:
        from PIL import Image
        import pytesseract
        return pytesseract.image_to_string(Image.open(file_path))
    except ImportError:
        logger.warning("pytesseract not available; image OCR skipped for %s", file_path)
        return ""
```

`extract_text()` gains image routing:

```python
IMAGE_MIMES = {"image/png", "image/jpeg", "image/webp", "image/tiff"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".tiff"}

# Add before the PDF check:
if mime in IMAGE_MIMES or os.path.splitext(file_path)[1].lower() in IMAGE_EXTS:
    return _extract_image(file_path)
```

### Backend: `backend/rag/ingestion.py`

MIME map extended:

```python
mime_map = {
    ".pdf":  "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt":  "text/plain",
    ".md":   "text/markdown",
    ".csv":  "text/csv",
    ".png":  "image/png",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".tiff": "image/tiff",
}
```

### Backend: `backend/routers/ai.py`

**`POST /api/v1/ai/ingest-document`** changes:
- `ALLOWED_MIME_TYPES` gains `image/png`, `image/jpeg`, `image/webp`, `image/tiff`
- `file_size_bytes=len(file_content)` set on `Document` at creation
- `require_roles("management", "superadmin")` dependency added

**`POST /api/v1/ai/documents/{document_id}/re-ingest`** (new):

```python
@router.post("/documents/{document_id}/re-ingest", status_code=200)
async def re_ingest_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    if current_user.get("role") not in {"management", "superadmin"}:
        raise HTTPException(status_code=403, detail="Only management roles can re-ingest documents")
    doc = await db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    doc.ingestion_error = None
    doc.ingested_into_rag = False
    await db.flush()
    task = ingest_document_task.delay(
        document_id=str(document_id),
        file_path=doc.file_path,
        collection_name=doc.milvus_collection or "hitech_rag",
        client_id=str(doc.client_id) if doc.client_id else None,
        doc_type=doc.doc_type,
    )
    return {
        "document_id": str(document_id),
        "title": doc.title,
        "ingested_into_rag": False,
        "ingestion_error": None,
        "task_id": task.id,
        "message": "Re-ingestion task queued successfully.",
    }
```

### Backend: `backend/tasks/rag_tasks.py`

`_mark_document_status()` updated:

```python
def _mark_document_status(
    document_id: str,
    ingested: bool,
    error_message: Optional[str] = None,
) -> None:
    with SyncSessionLocal() as session:
        session.execute(
            text("""
                UPDATE documents
                SET ingested_into_rag = :ingested,
                    ingestion_error = :error_msg
                WHERE id = :doc_id::uuid
            """),
            {"ingested": ingested, "doc_id": document_id, "error_msg": error_message},
        )
        session.commit()
```

`RAGBaseTask.on_failure` hook:

```python
def on_failure(self, exc, task_id, args, kwargs, einfo):
    document_id = args[0] if args else kwargs.get("document_id")
    if document_id:
        _mark_document_status(document_id, ingested=False, error_message=repr(exc))
```

### Frontend: `frontend/src/lib/api.ts`

```typescript
export const aiApi = {
  listDocuments: (params?: { skip?: number; limit?: number; doc_type?: string; client_id?: string }) =>
    api.get('/api/v1/ai/documents', { params }).then(r => r.data),

  uploadDocument: (formData: FormData) =>
    api.post('/api/v1/ai/ingest-document', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(r => r.data),

  deleteDocument: (id: string): Promise<void> =>
    api.delete(`/api/v1/ai/documents/${id}`).then(() => undefined),

  reIngestDocument: (id: string) =>
    api.post(`/api/v1/ai/documents/${id}/re-ingest`).then(r => r.data),

  getRagStatus: () =>
    api.get('/api/v1/ai/rag-status').then(r => r.data),
}
```

### Frontend: `KnowledgeBaseManager` component tree

| Component | File | Responsibility |
|---|---|---|
| `KnowledgeBaseManager` | `components/ai/KnowledgeBaseManager.tsx` | Orchestrator — queries, mutations, polling, toast transitions |
| `KbStatsBar` | `components/ai/KbStatsBar.tsx` | 4 metric cards: Total, Ingested, Pending, Milvus Chunks |
| `KbDocumentTable` | `components/ai/KbDocumentTable.tsx` | shadcn Table with status badges, tooltips, action buttons |
| `KbUploadDialog` | `components/ai/KbUploadDialog.tsx` | shadcn Dialog — file input, title, doc_type, optional client |
| `KbDeleteConfirmDialog` | `components/ai/KbDeleteConfirmDialog.tsx` | shadcn AlertDialog — deletion confirmation |

**Status derivation:**

```typescript
function deriveStatus(doc: DocumentRecord): 'ingested' | 'pending' | 'failed' {
  if (doc.ingestion_error) return 'failed'
  if (doc.ingested_into_rag) return 'ingested'
  return 'pending'
}
```

**Polling logic:**

```typescript
const hasPendingDocs = documents?.items?.some(
  (d) => !d.ingested_into_rag && !d.ingestion_error
) ?? false

useQuery({
  queryKey: ['ai-documents'],
  queryFn: () => aiApi.listDocuments(),
  refetchInterval: hasPendingDocs ? 10_000 : false,
})
```

**Role check:**

```typescript
const { data: session } = useSession()
const isManagement = ['management', 'superadmin'].includes(session?.user?.role ?? '')
```

---

## Data Models

### `documents` table (extended)

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | UUID | No | Primary key |
| `title` | VARCHAR(500) | No | |
| `doc_type` | VARCHAR(30) | No | regulation \| contract \| sop \| report \| manual |
| `client_id` | UUID | Yes | FK → clients.id |
| `file_path` | Text | Yes | |
| `mime_type` | VARCHAR(100) | Yes | |
| `ingested_into_rag` | Boolean | No | |
| `milvus_collection` | VARCHAR(100) | Yes | |
| `uploaded_by` | UUID | Yes | FK → users.id |
| `uploaded_at` | Timestamp TZ | No | |
| `file_size_bytes` | BigInteger | Yes | **NEW** |
| `ingestion_error` | Text | Yes | **NEW** |

### Alembic migration

```python
op.add_column('documents', sa.Column('file_size_bytes', sa.BigInteger(), nullable=True))
op.add_column('documents', sa.Column('ingestion_error', sa.Text(), nullable=True))
```

### Ingestion status derivation

```
ingestion_error IS NOT NULL  →  failed
ingested_into_rag = true     →  ingested
otherwise                    →  pending
```

---

## Correctness Properties

### Property 1: OCR fallback triggered iff pdfplumber returns no text
For any PDF page where pdfplumber returns empty/whitespace text, `_ocr_pdf_page` must be called; for pages with text, it must not be called.
**Validates: Requirements 6.1, 6.4**

### Property 2: Image extraction always returns a string
For any valid image file path, `_extract_image()` returns a `str` (possibly empty) and never raises, including when pytesseract is unavailable.
**Validates: Requirements 7.2, 7.3**

### Property 3: File size is always recorded accurately
For any uploaded file with byte content of length N, `file_size_bytes` in the DB equals N.
**Validates: Requirements 8.3**

### Property 4: Ingestion error is written on task failure
For any exception raised during `ingest_document_task`, `ingestion_error` is set to a non-null string.
**Validates: Requirements 8.4**

### Property 5: Re-ingest resets error state
After `POST /documents/{id}/re-ingest`, the returned document has `ingestion_error = null` and `ingested_into_rag = false`.
**Validates: Requirements 5.5, 8.5**

### Property 6: RBAC on write endpoints
For any user whose role is not `management` or `superadmin`, write endpoints return HTTP 403.
**Validates: Requirements 9.1, 9.2, 9.5**

### Property 7: Read endpoint accessible to all authenticated users
For any authenticated user regardless of role, `GET /documents` returns HTTP 200.
**Validates: Requirements 9.3**

### Property 8: Status badge colour is deterministic
The same `(ingested_into_rag, ingestion_error)` values always produce the same status label and colour class.
**Validates: Requirements 1.5, 10.7**

### Property 9: Polling active iff pending documents exist
`refetchInterval` is `10_000` iff at least one document has `ingested_into_rag=false` and `ingestion_error=null`; otherwise `false`.
**Validates: Requirements 3.1, 3.2**

### Property 10: Stats bar counts consistent with document list
Total, Ingested, and Pending counts in the Stats_Bar equal the counts derived directly from the document list.
**Validates: Requirements 3.5, 1.7**

### Property 11: Management-only UI controls hidden from non-management users
For any user whose role is not `management` or `superadmin`, upload, delete, and re-ingest buttons are not rendered.
**Validates: Requirements 2.1, 4.1, 5.1, 9.4**

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| File > 50 MB | HTTP 413 |
| Unsupported MIME type | HTTP 415 |
| Non-management write call | HTTP 403 |
| Document not found | HTTP 404 |
| File save fails | HTTP 500; no DB record created |
| Celery unavailable at upload | Document created; `task_status: "worker_unavailable"` |
| pytesseract not installed | Warning logged; OCR skipped; pipeline continues |
| All pages yield no text | `ingestion_error` set; `ingested_into_rag` remains false |
| Milvus unavailable | Celery retries (max 3, 30s delay); `ingestion_error` set after final failure |
| Re-ingest on non-existent doc | HTTP 404 |
