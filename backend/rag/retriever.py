# =============================================================
# Hi-Tech Waste Management — RAG Retriever
# Milvus vector search with Ollama embeddings
# =============================================================

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Default Milvus collection for platform-wide documents
DEFAULT_COLLECTION = "hitech_rag"

# Supported search metric
METRIC_TYPE = "COSINE"


async def retrieve_context(
    query: str,
    ollama_base_url: str,
    embed_model: str,
    milvus_host: str,
    milvus_port: int,
    collection_name: str | None = None,
    client_id: str | None = None,
    top_k: int = 8,
) -> list[dict[str, Any]]:
    """
    Retrieve relevant context chunks from Milvus for a given query.

    Steps:
    1. Generate a query embedding via Ollama's embedding endpoint.
    2. Search the specified (or default) Milvus collection using COSINE similarity.
    3. Optionally filter results by client_id for scoped queries.
    4. Return the top-k results as a list of context dicts.

    Returns an empty list on any error so callers degrade gracefully.

    Args:
        query:           The user's query text to embed and search
        ollama_base_url: Base URL for the Ollama API (e.g. http://localhost:11434)
        embed_model:     Embedding model name (e.g. nomic-embed-text)
        milvus_host:     Milvus gRPC host
        milvus_port:     Milvus gRPC port
        collection_name: Target collection (defaults to DEFAULT_COLLECTION)
        client_id:       Optional client UUID string for filtered search
        top_k:           Number of results to return (default 8 for richer blending)

    Returns:
        List of dicts with keys: text, source, doc_type, score, chunk_index
    """
    try:
        import httpx
        from pymilvus import MilvusClient  # type: ignore[import]

        # Step 1 — Generate query embedding
        async with httpx.AsyncClient(timeout=30.0) as http:
            embed_resp = await http.post(
                f"{ollama_base_url}/api/embeddings",
                json={"model": embed_model, "prompt": query},
            )
            embed_resp.raise_for_status()
            embedding = embed_resp.json().get("embedding", [])

        if not embedding:
            logger.warning("Ollama returned empty embedding for RAG query: %r", query[:80])
            return []

        # Step 2 — Determine target collection
        target_collection = collection_name or DEFAULT_COLLECTION

        # Step 3 — Search Milvus
        milvus_uri = f"http://{milvus_host}:{milvus_port}"
        client = MilvusClient(uri=milvus_uri)

        # Build optional filter expression
        filter_expr = None
        if client_id:
            # Search both client-specific and platform-wide docs
            filter_expr = f'client_id == "{client_id}" || client_id == ""'

        search_params = {"metric_type": METRIC_TYPE, "params": {"nprobe": 16}}

        results = client.search(
            collection_name=target_collection,
            data=[embedding],
            anns_field="embedding",
            search_params=search_params,
            limit=top_k,
            output_fields=["text", "source", "client_id", "doc_type", "chunk_index"],
            filter=filter_expr,
        )

        # Step 4 — Format results
        chunks: list[dict[str, Any]] = []
        for hit_list in results:
            for hit in hit_list:
                entity = hit.get("entity", {})
                chunks.append(
                    {
                        "text": entity.get("text", ""),
                        "source": entity.get("source", "Unknown"),
                        "doc_type": entity.get("doc_type", ""),
                        "score": round(float(hit.get("distance", 0.0)), 4),
                        "chunk_index": entity.get("chunk_index", 0),
                        "client_id": entity.get("client_id", ""),
                    }
                )

        logger.debug(
            "RAG retrieved %d chunks from '%s' for query: %r",
            len(chunks),
            target_collection,
            query[:60],
        )
        return chunks

    except Exception as exc:
        logger.warning("RAG retrieval failed (non-fatal): %s", exc)
        return []


def retrieve_context_sync(
    query: str,
    ollama_base_url: str,
    embed_model: str,
    milvus_host: str,
    milvus_port: int,
    collection_name: str | None = None,
    client_id: str | None = None,
    top_k: int = 8,
) -> list[dict[str, Any]]:
    """
    Synchronous version of retrieve_context for use in Celery tasks.

    Uses httpx.Client (blocking) instead of httpx.AsyncClient.
    """
    try:
        import httpx
        from pymilvus import MilvusClient  # type: ignore[import]

        # Generate embedding synchronously
        with httpx.Client(timeout=30.0) as http:
            embed_resp = http.post(
                f"{ollama_base_url}/api/embeddings",
                json={"model": embed_model, "prompt": query},
            )
            embed_resp.raise_for_status()
            embedding = embed_resp.json().get("embedding", [])

        if not embedding:
            logger.warning("Ollama returned empty embedding (sync) for query: %r", query[:80])
            return []

        target_collection = collection_name or DEFAULT_COLLECTION
        milvus_uri = f"http://{milvus_host}:{milvus_port}"
        client = MilvusClient(uri=milvus_uri)

        filter_expr = None
        if client_id:
            filter_expr = f'client_id == "{client_id}" || client_id == ""'

        search_params = {"metric_type": METRIC_TYPE, "params": {"nprobe": 16}}

        results = client.search(
            collection_name=target_collection,
            data=[embedding],
            anns_field="embedding",
            search_params=search_params,
            limit=top_k,
            output_fields=["text", "source", "client_id", "doc_type", "chunk_index"],
            filter=filter_expr,
        )

        chunks: list[dict[str, Any]] = []
        for hit_list in results:
            for hit in hit_list:
                entity = hit.get("entity", {})
                chunks.append(
                    {
                        "text": entity.get("text", ""),
                        "source": entity.get("source", "Unknown"),
                        "doc_type": entity.get("doc_type", ""),
                        "score": round(float(hit.get("distance", 0.0)), 4),
                        "chunk_index": entity.get("chunk_index", 0),
                        "client_id": entity.get("client_id", ""),
                    }
                )

        return chunks

    except Exception as exc:
        logger.warning("RAG retrieval (sync) failed (non-fatal): %s", exc)
        return []


def list_collections(milvus_host: str, milvus_port: int) -> list[str]:
    """
    List all Milvus collections. Used for health checks and admin tooling.
    Returns an empty list if Milvus is unreachable.
    """
    try:
        from pymilvus import MilvusClient  # type: ignore[import]

        client = MilvusClient(uri=f"http://{milvus_host}:{milvus_port}")
        return client.list_collections()
    except Exception as exc:
        logger.warning("Could not list Milvus collections: %s", exc)
        return []


def collection_stats(
    milvus_host: str,
    milvus_port: int,
    collection_name: str = DEFAULT_COLLECTION,
) -> dict[str, Any]:
    """
    Return basic stats for a Milvus collection (row count, etc.).
    Used by the /health endpoint and admin dashboard.
    """
    try:
        from pymilvus import MilvusClient  # type: ignore[import]

        client = MilvusClient(uri=f"http://{milvus_host}:{milvus_port}")
        if not client.has_collection(collection_name):
            return {"collection": collection_name, "exists": False, "row_count": 0}

        stats = client.get_collection_stats(collection_name)
        return {
            "collection": collection_name,
            "exists": True,
            "row_count": int(stats.get("row_count", 0)),
        }
    except Exception as exc:
        logger.warning("Could not get Milvus collection stats: %s", exc)
        return {"collection": collection_name, "exists": False, "error": str(exc)}
