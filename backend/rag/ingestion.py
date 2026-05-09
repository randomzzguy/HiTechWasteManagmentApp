# =============================================================
# Hi-Tech Waste Management — RAG Document Ingestion
# High-level ingestion orchestration (delegates to pipeline.py)
# =============================================================

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def ingest_document_from_path(
    file_path: str,
    document_id: str,
    title: str,
    doc_type: str,
    client_id: str | None,
    collection_name: str,
    ollama_base_url: str,
    embed_model: str,
    milvus_host: str,
    milvus_port: int,
) -> dict[str, Any]:
    """
    High-level document ingestion orchestrator.

    Delegates to pipeline.py for the actual work:
    1. Extract text from the document file
    2. Clean and chunk the text
    3. Generate embeddings for each chunk
    4. Store chunks + embeddings in Milvus

    Returns a summary dict with chunk counts and timing.

    Args:
        file_path:       Absolute path to the document file on disk
        document_id:     UUID string of the Document DB record
        title:           Document title (used as the 'source' label in Milvus)
        doc_type:        regulation | contract | sop | report | manual
        client_id:       Optional client UUID string (empty string for platform-wide)
        collection_name: Target Milvus collection
        ollama_base_url: Ollama API base URL
        embed_model:     Embedding model name
        milvus_host:     Milvus gRPC host
        milvus_port:     Milvus gRPC port

    Returns:
        {
            "document_id": str,
            "chunks_created": int,
            "chunks_embedded": int,
            "chunks_stored": int,
            "success": bool,
            "error": str | None,
        }
    """
    from rag.pipeline import (
        chunk_text,
        clean_text,
        ensure_collection,
        extract_text,
        generate_embedding,
        store_chunks,
    )

    result: dict[str, Any] = {
        "document_id": document_id,
        "chunks_created": 0,
        "chunks_embedded": 0,
        "chunks_stored": 0,
        "success": False,
        "error": None,
    }

    try:
        # Determine MIME type from file extension
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

        # Extract text
        raw_text = extract_text(file_path, mime_type)
        if not raw_text.strip():
            result["error"] = "No text could be extracted from the document"
            return result

        # Clean and chunk
        cleaned = clean_text(raw_text)
        chunks = chunk_text(cleaned, chunk_size=800, overlap=100)
        result["chunks_created"] = len(chunks)

        if not chunks:
            result["error"] = "No chunks could be generated from the document text"
            return result

        # Generate embeddings
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
                embeddings.append([])  # placeholder to keep lists aligned

        # Filter out failed embeddings
        valid_pairs = [(c, e) for c, e in zip(chunks, embeddings) if e]
        result["chunks_embedded"] = len(valid_pairs)

        if not valid_pairs:
            result["error"] = "All chunk embeddings failed"
            return result

        valid_chunks, valid_embeddings = zip(*valid_pairs)

        # Ensure collection exists
        milvus_uri = f"http://{milvus_host}:{milvus_port}"
        ensure_collection(milvus_uri, collection_name, dim=len(valid_embeddings[0]))

        # Store in Milvus
        stored = store_chunks(
            milvus_uri=milvus_uri,
            collection_name=collection_name,
            chunks=list(valid_chunks),
            embeddings=list(valid_embeddings),
            document_id=document_id,
            source=title,
            client_id=client_id or "",
            doc_type=doc_type,
        )
        result["chunks_stored"] = stored
        result["success"] = True

        logger.info(
            "Document ingestion complete | doc_id=%s | chunks=%d | stored=%d",
            document_id,
            len(valid_chunks),
            stored,
        )

    except Exception as exc:
        logger.error("Document ingestion failed for %s: %s", document_id, exc, exc_info=True)
        result["error"] = str(exc)

    return result


def delete_document_from_collection(
    document_id: str,
    collection_name: str,
    milvus_host: str,
    milvus_port: int,
) -> int:
    """
    Delete all chunks belonging to a document from a Milvus collection.

    Returns the number of chunks deleted.
    """
    try:
        from pymilvus import MilvusClient  # type: ignore[import]

        milvus_uri = f"http://{milvus_host}:{milvus_port}"
        client = MilvusClient(uri=milvus_uri)

        if not client.has_collection(collection_name):
            logger.warning(
                "Collection '%s' does not exist — cannot delete document %s",
                collection_name,
                document_id,
            )
            return 0

        # Delete by filter expression
        expr = f'document_id == "{document_id}"'
        result = client.delete(collection_name=collection_name, filter=expr)

        deleted_count = result.get("delete_count", 0)
        logger.info(
            "Deleted %d chunks for document %s from collection '%s'",
            deleted_count,
            document_id,
            collection_name,
        )
        return deleted_count

    except Exception as exc:
        logger.error(
            "Failed to delete document %s from Milvus: %s", document_id, exc
        )
        return 0
