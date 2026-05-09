# Requirements Document

## Introduction

The RAG Knowledge Base Manager is a dedicated section of the Hi-Tech Waste Management platform's AI Assistant page that allows authorised users to view, upload, delete, and re-ingest documents that feed the AI assistant's Retrieval-Augmented Generation (RAG) system. The feature also extends the backend's text extraction pipeline to support scanned PDFs and image files via OCR, closing a critical gap where image-only PDF pages and image uploads currently yield no extractable text. The Document ORM model is extended with `file_size_bytes` and `ingestion_error` fields to enable failure tracking and surfacing of error details in the UI.

---

## Glossary

- **Knowledge_Base_Manager**: The frontend component and associated backend logic that manages the RAG document corpus.
- **RAG_System**: The Retrieval-Augmented Generation pipeline comprising document ingestion, Milvus vector storage, and context retrieval used by the AI Assistant.
- **Document**: A file record stored in the `documents` PostgreSQL table, representing a file that has been or is being ingested into the RAG_System.
- **Ingestion_Pipeline**: The Celery task chain (`ingest_document_task`) that extracts text, chunks it, generates embeddings, and stores vectors in Milvus.
- **OCR_Engine**: The pytesseract + pdf2image subsystem responsible for extracting text from scanned PDFs and image files.
- **Milvus**: The vector database storing document chunk embeddings, accessible at `MILVUS_HOST:MILVUS_PORT`.
- **Text_PDF**: A PDF file that contains a machine-readable text layer extractable by pdfplumber.
- **Scanned_PDF**: A PDF file whose pages are composed entirely of rasterised images with no text layer; pdfplumber returns empty text for these pages.
- **Image_File**: A file in PNG, JPG/JPEG, WEBP, or TIFF format containing a photograph, scan, or rendering of a document.
- **Doc_Type**: The classification of a document: `regulation`, `contract`, `sop`, `report`, or `manual`.
- **Ingestion_Status**: The current state of a Document's RAG processing: `pending` (not yet ingested), `ingested` (successfully stored in Milvus), or `failed` (ingestion attempted but errored).
- **Management_Role**: A user whose `role` is `management` or `superadmin`.
- **Viewer_Role**: Any authenticated user regardless of role.
- **Stats_Bar**: The summary statistics panel at the top of the Knowledge_Base_Manager showing aggregate document and chunk counts.
- **Re_Ingest**: The action of re-queuing a failed Document through the Ingestion_Pipeline without re-uploading the file.

---

## Requirements

### Requirement 1: Document Listing

**User Story:** As a Viewer_Role user, I want to see all documents currently in the knowledge base with their ingestion status, so that I can understand what information the AI assistant has access to.

#### Acceptance Criteria

1. THE Knowledge_Base_Manager SHALL display a table of all Document records returned by `GET /api/v1/ai/documents`, with columns: Title, Doc_Type, Ingestion_Status, file size, upload date, and Actions.
2. WHEN the document list is loading, THE Knowledge_Base_Manager SHALL display a skeleton loading state in place of the table rows.
3. WHEN the `GET /api/v1/ai/documents` request fails, THE Knowledge_Base_Manager SHALL display an error message and a retry button.
4. WHEN the document list is empty, THE Knowledge_Base_Manager SHALL display an empty-state message indicating no documents have been uploaded yet.
5. THE Knowledge_Base_Manager SHALL display the Ingestion_Status of each Document as one of three distinct visual states: `ingested` (success), `pending` (in progress), or `failed` (error).
6. WHEN a Document has Ingestion_Status `failed` and an `ingestion_error` value is present, THE Knowledge_Base_Manager SHALL display the error message in a tooltip or expandable row detail.
7. THE Knowledge_Base_Manager SHALL display the Stats_Bar above the document table showing: total document count, ingested count, pending count, and total Milvus chunk count sourced from `GET /api/v1/ai/rag-status`.

---

### Requirement 2: Document Upload

**User Story:** As a Management_Role user, I want to upload new documents to the knowledge base, so that the AI assistant can answer questions using the latest regulatory, contractual, and operational information.

#### Acceptance Criteria

1. THE Knowledge_Base_Manager SHALL display an upload button that is visible only to Management_Role users.
2. WHEN the upload button is clicked, THE Knowledge_Base_Manager SHALL open a file picker that accepts files with extensions: `.pdf`, `.docx`, `.txt`, `.csv`, `.md`, `.png`, `.jpg`, `.jpeg`, `.webp`, `.tiff`.
3. WHEN a file is selected, THE Knowledge_Base_Manager SHALL display a pre-upload form requiring the user to provide a document title (max 500 characters) and select a Doc_Type from: `regulation`, `contract`, `sop`, `report`, `manual`.
4. WHEN a file exceeding 50 MB is selected, THE Knowledge_Base_Manager SHALL display a validation error and prevent submission.
5. WHEN the upload form is submitted, THE Knowledge_Base_Manager SHALL POST the file and metadata to `POST /api/v1/ai/ingest-document` and display an upload progress indicator.
6. WHEN the upload request succeeds, THE Knowledge_Base_Manager SHALL add the new Document to the table with Ingestion_Status `pending` and display a success toast notification.
7. WHEN the upload request fails, THE Knowledge_Base_Manager SHALL display an error toast notification with the server-returned error message and leave the form open for correction.
8. THE Knowledge_Base_Manager SHALL accept an optional client association on the upload form, allowing Management_Role users to scope a document to a specific client.

---

### Requirement 3: Ingestion Status Polling

**User Story:** As a Management_Role user, I want to see live ingestion status updates after uploading a document, so that I know when the AI assistant can start using the new content.

#### Acceptance Criteria

1. WHEN one or more Documents have Ingestion_Status `pending`, THE Knowledge_Base_Manager SHALL poll `GET /api/v1/ai/documents` at a 10-second interval to refresh document statuses.
2. WHEN all Documents have Ingestion_Status `ingested` or `failed` (no pending documents remain), THE Knowledge_Base_Manager SHALL stop polling.
3. WHEN a Document transitions from Ingestion_Status `pending` to `ingested`, THE Knowledge_Base_Manager SHALL display a success toast notification identifying the document by title.
4. WHEN a Document transitions from Ingestion_Status `pending` to `failed`, THE Knowledge_Base_Manager SHALL display a warning toast notification identifying the document by title.
5. THE Knowledge_Base_Manager SHALL update the Stats_Bar counts whenever the document list is refreshed.

---

### Requirement 4: Document Deletion

**User Story:** As a Management_Role user, I want to delete documents from the knowledge base, so that outdated or incorrect information is removed from the AI assistant's context.

#### Acceptance Criteria

1. THE Knowledge_Base_Manager SHALL display a delete action button per document row that is visible only to Management_Role users.
2. WHEN the delete button is clicked, THE Knowledge_Base_Manager SHALL display a confirmation dialog stating the document title and warning that the action will remove the document from both the database and Milvus vector store.
3. WHEN the user confirms deletion, THE Knowledge_Base_Manager SHALL send `DELETE /api/v1/ai/documents/{id}` and display a loading state on the confirmation dialog.
4. WHEN the deletion request succeeds, THE Knowledge_Base_Manager SHALL remove the document row from the table, display a success toast notification, and refresh the Stats_Bar.
5. WHEN the deletion request fails, THE Knowledge_Base_Manager SHALL display an error toast notification with the server-returned error message and keep the document row in the table.
6. WHEN the user cancels the confirmation dialog, THE Knowledge_Base_Manager SHALL close the dialog and take no further action.

---

### Requirement 5: Failed Ingestion Re-Ingest

**User Story:** As a Management_Role user, I want to re-trigger ingestion for documents that failed processing, so that I can recover from transient errors without re-uploading the file.

#### Acceptance Criteria

1. THE Knowledge_Base_Manager SHALL display a re-ingest action button on document rows where Ingestion_Status is `failed`, visible only to Management_Role users.
2. WHEN the re-ingest button is clicked, THE Knowledge_Base_Manager SHALL POST to `POST /api/v1/ai/documents/{id}/re-ingest` and set the document's Ingestion_Status to `pending`.
3. WHEN the re-ingest request succeeds, THE Knowledge_Base_Manager SHALL display a success toast notification and begin polling for status updates per Requirement 3.
4. WHEN the re-ingest request fails, THE Knowledge_Base_Manager SHALL display an error toast notification with the server-returned error message.
5. THE Backend SHALL reset the `ingestion_error` field to `null` on the Document record when a re-ingest task is queued.

---

### Requirement 6: OCR Support for Scanned PDFs

**User Story:** As a Management_Role user, I want to upload scanned PDF documents and have their text extracted via OCR, so that image-only PDFs such as scanned regulations and contracts are searchable by the AI assistant.

#### Acceptance Criteria

1. WHEN the Ingestion_Pipeline processes a PDF file and pdfplumber extracts no text from a page, THE OCR_Engine SHALL convert that page to a PIL image using pdf2image and extract text using pytesseract.
2. WHEN the OCR_Engine processes a page, THE Ingestion_Pipeline SHALL append the OCR-extracted text for that page to the document's full text alongside any text-layer pages.
3. WHEN pytesseract is not installed or Tesseract is not available in the execution environment, THE Ingestion_Pipeline SHALL log a warning and continue ingestion with whatever text was extractable, rather than failing the entire task.
4. THE `_extract_pdf()` function in `backend/rag/pipeline.py` SHALL apply the pdfplumber-first, OCR-fallback strategy per page, so that hybrid PDFs (some text pages, some scanned pages) are fully extracted.
5. WHEN a PDF file yields zero text from both pdfplumber and OCR across all pages, THE Ingestion_Pipeline SHALL mark the Document with Ingestion_Status `failed` and set `ingestion_error` to a descriptive message indicating no text was extractable.
6. THE Docker container running the Celery worker SHALL have `tesseract-ocr` and `poppler-utils` installed as system packages to support pytesseract and pdf2image respectively.
7. THE `backend/requirements.txt` SHALL include `pytesseract` and `pdf2image` as Python dependencies.

---

### Requirement 7: OCR Support for Image Files

**User Story:** As a Management_Role user, I want to upload image files (photos of documents, whiteboard captures, scanned forms) and have their text extracted via OCR, so that visual documents are included in the AI assistant's knowledge base.

#### Acceptance Criteria

1. THE Ingestion_Pipeline SHALL support image files with MIME types: `image/png`, `image/jpeg`, `image/webp`, `image/tiff`.
2. WHEN the Ingestion_Pipeline processes an image file, THE OCR_Engine SHALL open the image using PIL and extract text using pytesseract.
3. WHEN pytesseract extracts no text from an image file, THE Ingestion_Pipeline SHALL mark the Document with Ingestion_Status `failed` and set `ingestion_error` to a message indicating no text was found in the image.
4. THE `extract_text()` function in `backend/rag/pipeline.py` SHALL route image MIME types to a new `_extract_image()` function that uses pytesseract for OCR.
5. THE `POST /api/v1/ai/ingest-document` endpoint SHALL accept image MIME types (`image/png`, `image/jpeg`, `image/webp`, `image/tiff`) in its allowed MIME type set.
6. THE `backend/rag/ingestion.py` MIME type map SHALL include entries for `.png`, `.jpg`, `.jpeg`, `.webp`, and `.tiff` extensions mapping to their respective `image/*` MIME types.

---

### Requirement 8: Document Model Extension

**User Story:** As a developer, I want the Document model to track file size and ingestion error details, so that the UI can display meaningful failure information and storage statistics.

#### Acceptance Criteria

1. THE `Document` SQLAlchemy ORM model SHALL include a `file_size_bytes` column of type `BigInteger`, nullable, storing the size of the uploaded file in bytes.
2. THE `Document` SQLAlchemy ORM model SHALL include an `ingestion_error` column of type `Text`, nullable, storing the last error message from a failed ingestion attempt.
3. THE `POST /api/v1/ai/ingest-document` endpoint SHALL populate `file_size_bytes` with the byte length of the uploaded file at the time of Document record creation.
4. WHEN the `ingest_document_task` Celery task fails or produces no extractable text, THE task SHALL write the error message string to the `ingestion_error` column of the corresponding Document record.
5. WHEN the `ingest_document_task` Celery task succeeds, THE task SHALL set `ingestion_error` to `null` on the corresponding Document record.
6. THE `DocumentRead` Pydantic schema SHALL expose `file_size_bytes` (Optional[int]) and `ingestion_error` (Optional[str]) fields so the frontend can consume them.
7. THE `GET /api/v1/ai/documents` endpoint SHALL include `file_size_bytes` and `ingestion_error` in each document's response payload.
8. THE backend SHALL provide an Alembic migration adding the `file_size_bytes` and `ingestion_error` columns to the `documents` table.

---

### Requirement 9: Role-Based Access Control

**User Story:** As a system administrator, I want upload and delete actions to be restricted to management and superadmin roles, so that the knowledge base is not accidentally modified by field staff or client portal users.

#### Acceptance Criteria

1. THE `POST /api/v1/ai/ingest-document` endpoint SHALL return HTTP 403 if the authenticated user's role is not `management` or `superadmin`.
2. THE `DELETE /api/v1/ai/documents/{id}` endpoint SHALL return HTTP 403 if the authenticated user's role is not `management` or `superadmin`.
3. THE `GET /api/v1/ai/documents` endpoint SHALL be accessible to all authenticated users regardless of role.
4. THE Knowledge_Base_Manager SHALL hide the upload button, delete action buttons, and re-ingest action buttons from users whose role is not `management` or `superadmin`.
5. IF a non-Management_Role user attempts to call `POST /api/v1/ai/ingest-document` or `DELETE /api/v1/ai/documents/{id}` directly, THEN THE backend SHALL return HTTP 403 with a descriptive error message.

---

### Requirement 10: UI Integration and Design

**User Story:** As a user, I want the Knowledge Base Manager to be easily accessible from the AI Assistant page and visually consistent with the rest of the platform, so that it feels like a native part of the application.

#### Acceptance Criteria

1. THE AI Assistant page (`/ai-assistant`) SHALL present the Knowledge_Base_Manager as a second tab alongside the existing chat interface, labelled "Knowledge Base".
2. WHEN the "Knowledge Base" tab is active, THE page SHALL display the Knowledge_Base_Manager component occupying the full content area.
3. WHEN the "AI Assistant" tab is active, THE page SHALL display the existing chat layout (AIAssistantChat + AgentStatusPanel + AgentAlertFeed) unchanged.
4. THE Knowledge_Base_Manager SHALL use the platform's dark slate design system: `slate-950` page background, `slate-800/900` card backgrounds, `emerald-500` accent colour for primary actions, and Lucide icons consistent with the rest of the UI.
5. THE Knowledge_Base_Manager SHALL be responsive, displaying the document table with horizontal scroll on viewports narrower than 768px rather than breaking the layout.
6. THE Stats_Bar SHALL display four metric cards: "Total Documents", "Ingested", "Pending", and "Milvus Chunks", each with an appropriate Lucide icon and the platform's card styling.
7. THE document table's Ingestion_Status column SHALL use colour-coded badges: emerald for `ingested`, amber for `pending`, and red for `failed`, consistent with the `StatusBadge` shared component pattern.
