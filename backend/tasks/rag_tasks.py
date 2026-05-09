# =============================================================
# Hi-Tech Waste Management — RAG Celery Tasks
# Document ingestion: extract → chunk → embed → store in Milvus
# =============================================================

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from celery import Task
from celery.exceptions import SoftTimeLimitExceeded

from tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


class RAGBaseTask(Task):
    """Base task class for RAG ingestion tasks."""

    abstract = True
    max_retries = 3
    default_retry_delay = 30

    def on_failure(self, exc: Exception, task_id: str, args, kwargs, einfo) -> None:
        logger.error(
            "RAG task FAILED | task=%s | task_id=%s | exc=%s",
            self.name,
            task_id,
            repr(exc),
            exc_info=True,
        )
        document_id = args[0] if args else kwargs.get("document_id")
        if document_id:
            _mark_document_status(document_id, ingested=False, error_message=repr(exc))


@celery_app.task(
    bind=True,
    base=RAGBaseTask,
    name="tasks.rag_tasks.ingest_document_task",
    queue="agents",
)
def ingest_document_task(
    self: RAGBaseTask,
    document_id: str,
    file_path: str,
    collection_name: str,
    client_id: str | None = None,
    doc_type: str = "manual",
) -> dict[str, Any]:
    """
    Celery task to ingest a document into the RAG knowledge base.

    Steps:
    1. Extract text from the document file (PDF, DOCX, TXT, CSV).
    2. Clean and chunk the text into overlapping segments.
    3. Generate embeddings for each chunk via Ollama.
    4. Ensure the target Milvus collection exists.
    5. Store chunks + embeddings in Milvus.
    6. Mark the Document DB record as ingested_into_rag=True.

    Returns a summary dict with chunk counts and timing.
    """
    logger.info(
        "RAG ingestion starting | doc_id=%s | collection=%s | file=%s",
        document_id,
        collection_name,
        file_path,
    )
    start_time = datetime.now(tz=timezone.utc)
    results: dict[str, Any] = {
        "document_id": document_id,
        "collection_name": collection_name,
        "started_at": start_time.isoformat(),
        "chunks_created": 0,
        "chunks_embedded": 0,
        "chunks_stored": 0,
        "success": False,
    }

    # Read config from environment
    ollama_base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    embed_model = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")
    milvus_host = os.environ.get("MILVUS_HOST", "localhost")
    milvus_port = os.environ.get("MILVUS_PORT", "19530")
    milvus_uri = f"http://{milvus_host}:{milvus_port}"

    try:
        from rag.pipeline import (
            chunk_text,
            clean_text,
            ensure_collection,
            extract_text,
            generate_embedding,
            store_chunks,
        )

        # Step 1 — Determine MIME type from file extension
        mime_map = {
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".txt": "text/plain",
            ".md": "text/markdown",
            ".csv": "text/csv",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".tiff": "image/tiff",
        }
        ext = os.path.splitext(file_path)[1].lower()
        mime_type = mime_map.get(ext, "text/plain")

        # Step 2 — Extract text
        raw_text = extract_text(file_path, mime_type)
        if not raw_text.strip():
            logger.warning("No text extracted from document %s", document_id)
            _mark_document_status(document_id, ingested=False, error_message="No text could be extracted from the document")
            results["error"] = "No text could be extracted from the document"
            return results

        # Step 3 — Clean and chunk
        cleaned = clean_text(raw_text)
        chunks = chunk_text(cleaned, chunk_size=800, overlap=100)
        results["chunks_created"] = len(chunks)
        logger.info("Document %s: %d chunks created", document_id, len(chunks))

        if not chunks:
            logger.warning("No chunks generated for document %s", document_id)
            _mark_document_status(document_id, ingested=False, error_message="No chunks could be generated from the document text")
            results["error"] = "No chunks could be generated from the document text"
            return results

        # Step 4 — Generate embeddings
        embeddings: list[list[float]] = []
        for i, chunk in enumerate(chunks):
            try:
                embedding = generate_embedding(chunk, ollama_base_url, embed_model)
                embeddings.append(embedding)
            except Exception as exc:
                logger.warning(
                    "Skipping chunk %d for doc %s — embedding failed: %s",
                    i,
                    document_id,
                    exc,
                )
                # Insert placeholder to keep chunk/embedding lists aligned
                embeddings.append([])

        # Filter out chunks with failed embeddings
        valid_pairs = [
            (chunk, emb)
            for chunk, emb in zip(chunks, embeddings)
            if emb
        ]
        results["chunks_embedded"] = len(valid_pairs)

        if not valid_pairs:
            logger.error("All embeddings failed for document %s", document_id)
            _mark_document_status(document_id, ingested=False, error_message="All chunk embeddings failed")
            results["error"] = "All chunk embeddings failed"
            return results

        valid_chunks, valid_embeddings = zip(*valid_pairs)

        # Step 5 — Ensure Milvus collection exists
        ensure_collection(milvus_uri, collection_name, dim=len(valid_embeddings[0]))

        # Step 6 — Get document source title from DB
        source_title = _get_document_title(document_id) or os.path.basename(file_path)

        # Step 7 — Store in Milvus
        stored = store_chunks(
            milvus_uri=milvus_uri,
            collection_name=collection_name,
            chunks=list(valid_chunks),
            embeddings=list(valid_embeddings),
            document_id=document_id,
            source=source_title,
            client_id=client_id or "",
            doc_type=doc_type,
        )
        results["chunks_stored"] = stored

        # Step 8 — Mark document as ingested in DB
        _mark_document_status(document_id, ingested=True, error_message=None)
        results["success"] = True

        logger.info(
            "RAG ingestion complete | doc_id=%s | chunks=%d | stored=%d",
            document_id,
            len(valid_chunks),
            stored,
        )

    except SoftTimeLimitExceeded:
        logger.warning("RAG ingestion soft time limit exceeded for doc %s", document_id)
        _mark_document_status(document_id, ingested=False, error_message="Task timed out")
        results["error"] = "Task timed out"
    except Exception as exc:
        logger.error("RAG ingestion failed for doc %s: %s", document_id, exc, exc_info=True)
        _mark_document_status(document_id, ingested=False, error_message=str(exc))
        results["error"] = str(exc)
        raise self.retry(exc=exc)

    results["completed_at"] = datetime.now(tz=timezone.utc).isoformat()
    return results


def _mark_document_status(document_id: str, ingested: bool, error_message: Optional[str] = None) -> None:
    """Update the ingested_into_rag flag and ingestion_error on the Document DB record."""
    try:
        from database import SyncSessionLocal
        from sqlalchemy import text

        with SyncSessionLocal() as session:
            session.execute(
                text(
                    """
                    UPDATE documents
                    SET ingested_into_rag = :ingested,
                        ingestion_error = :error_msg
                    WHERE id = :doc_id::uuid
                    """
                ),
                {"ingested": ingested, "doc_id": document_id, "error_msg": error_message},
            )
            session.commit()
    except Exception as exc:
        logger.error("Failed to update document ingestion status: %s", exc)


def _get_document_title(document_id: str) -> str | None:
    """Fetch the document title from the DB for use as the RAG source label."""
    try:
        from database import SyncSessionLocal
        from sqlalchemy import text

        with SyncSessionLocal() as session:
            row = session.execute(
                text("SELECT title FROM documents WHERE id = :doc_id::uuid"),
                {"doc_id": document_id},
            ).first()
            return row[0] if row else None
    except Exception:
        return None
