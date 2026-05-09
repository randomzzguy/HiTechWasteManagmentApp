# =============================================================
# Hi-Tech Waste Management — RAG Package
# =============================================================

from .pipeline import (
    extract_text,
    clean_text,
    chunk_text,
    generate_embedding,
    ensure_collection,
    store_chunks,
)
from .retriever import retrieve_context, retrieve_context_sync, collection_stats
from .ingestion import ingest_document_from_path, delete_document_from_collection
from .prompts import build_rag_system_prompt, build_standalone_prompt

__all__ = [
    "extract_text",
    "clean_text",
    "chunk_text",
    "generate_embedding",
    "ensure_collection",
    "store_chunks",
    "retrieve_context",
    "retrieve_context_sync",
    "collection_stats",
    "ingest_document_from_path",
    "delete_document_from_collection",
    "build_rag_system_prompt",
    "build_standalone_prompt",
]
