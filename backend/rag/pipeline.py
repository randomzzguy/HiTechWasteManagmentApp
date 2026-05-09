# =============================================================
# Hi-Tech Waste Management — RAG Pipeline
# Document chunking, embedding, and Milvus storage
# =============================================================

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

IMAGE_MIMES = {"image/png", "image/jpeg", "image/webp", "image/tiff"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".tiff"}

# =============================================================
# Text Extraction
# =============================================================


def extract_text(file_path: str, mime_type: str) -> str:
    """
    Extract plain text from a document file.

    Supports: PDF, DOCX, TXT, CSV, Markdown.
    Returns extracted text as a single string.
    """
    import os

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Document file not found: {file_path}")

    mime = (mime_type or "").lower()

    # Image
    if mime in IMAGE_MIMES or os.path.splitext(file_path)[1].lower() in IMAGE_EXTS:
        return _extract_image(file_path)

    # PDF
    if "pdf" in mime or file_path.lower().endswith(".pdf"):
        return _extract_pdf(file_path)

    # DOCX
    if "wordprocessingml" in mime or file_path.lower().endswith(".docx"):
        return _extract_docx(file_path)

    # CSV
    if "csv" in mime or file_path.lower().endswith(".csv"):
        return _extract_csv(file_path)

    # Plain text / Markdown
    return _extract_text(file_path)


def _extract_pdf(file_path: str) -> str:
    """Extract text from a PDF using pdfplumber, with per-page OCR fallback."""
    try:
        import pdfplumber  # type: ignore[import]

        pages: list[str] = []
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
    except Exception as exc:
        logger.error("PDF extraction failed for %s: %s", file_path, exc)
        raise


def _ocr_pdf_page(page_index: int, file_path: str) -> str:
    """OCR a single PDF page using pdf2image + pytesseract."""
    try:
        from pdf2image import convert_from_path  # type: ignore[import]
        import pytesseract  # type: ignore[import]

        images = convert_from_path(
            file_path, first_page=page_index + 1, last_page=page_index + 1
        )
        return pytesseract.image_to_string(images[0]) if images else ""
    except ImportError:
        logger.warning(
            "pytesseract/pdf2image not available; OCR skipped for page %d", page_index
        )
        return ""


def _extract_image(file_path: str) -> str:
    """Extract text from an image file using pytesseract OCR."""
    try:
        from PIL import Image  # type: ignore[import]
        import pytesseract  # type: ignore[import]

        return pytesseract.image_to_string(Image.open(file_path))
    except ImportError:
        logger.warning(
            "pytesseract not available; image OCR skipped for %s", file_path
        )
        return ""


def _extract_docx(file_path: str) -> str:
    """Extract text from a DOCX file using python-docx."""
    try:
        import docx  # type: ignore[import]

        doc = docx.Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs)
    except ImportError:
        logger.warning("python-docx not installed; falling back to plain text read")
        return _extract_text(file_path)
    except Exception as exc:
        logger.error("DOCX extraction failed for %s: %s", file_path, exc)
        raise


def _extract_csv(file_path: str) -> str:
    """Extract text from a CSV file, formatting rows as readable lines."""
    import csv

    rows: list[str] = []
    with open(file_path, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        for row in reader:
            rows.append(" | ".join(cell.strip() for cell in row))
    return "\n".join(rows)


def _extract_text(file_path: str) -> str:
    """Read a plain text or Markdown file."""
    with open(file_path, encoding="utf-8", errors="replace") as f:
        return f.read()


# =============================================================
# Text Cleaning
# =============================================================


def clean_text(text: str) -> str:
    """
    Normalise whitespace and remove junk characters from extracted text.
    Preserves paragraph structure (double newlines).
    """
    # Normalise line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Collapse runs of 3+ newlines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Collapse runs of spaces/tabs within a line
    text = re.sub(r"[ \t]+", " ", text)
    # Strip leading/trailing whitespace per line
    lines = [line.strip() for line in text.split("\n")]
    return "\n".join(lines).strip()


# =============================================================
# Text Chunking
# =============================================================


def chunk_text(
    text: str,
    chunk_size: int = 800,
    overlap: int = 100,
) -> list[str]:
    """
    Split text into overlapping chunks of approximately `chunk_size` tokens.

    Uses word-boundary splitting with sentence-boundary preference.
    Each chunk overlaps the previous by `overlap` words to preserve context
    across chunk boundaries.

    Returns a list of text chunks.
    """
    if not text.strip():
        return []

    # Split into sentences first to avoid mid-sentence cuts
    sentences = _split_sentences(text)

    chunks: list[str] = []
    current_words: list[str] = []
    current_len = 0

    for sentence in sentences:
        words = sentence.split()
        if not words:
            continue

        # If adding this sentence would exceed chunk_size, flush current chunk
        if current_len + len(words) > chunk_size and current_words:
            chunks.append(" ".join(current_words))
            # Keep overlap words from the end of the current chunk
            current_words = current_words[-overlap:] if overlap > 0 else []
            current_len = len(current_words)

        current_words.extend(words)
        current_len += len(words)

    # Flush remaining words
    if current_words:
        chunks.append(" ".join(current_words))

    return [c.strip() for c in chunks if c.strip()]


def _split_sentences(text: str) -> list[str]:
    """
    Split text into sentences using simple punctuation heuristics.
    Falls back to paragraph splitting for non-sentence text (e.g. tables).
    """
    # Split on sentence-ending punctuation followed by whitespace
    parts = re.split(r"(?<=[.!?])\s+", text)
    # Also split on paragraph boundaries
    result: list[str] = []
    for part in parts:
        sub = part.split("\n\n")
        result.extend(sub)
    return [s.strip() for s in result if s.strip()]


# =============================================================
# Embedding Generation
# =============================================================


def generate_embedding(text: str, ollama_base_url: str, embed_model: str) -> list[float]:
    """
    Generate a single embedding vector for the given text using Ollama.

    Makes a synchronous HTTP call (for use in Celery tasks).
    Returns a list of floats (768-dimensional for nomic-embed-text).
    Raises on failure after 2 retries.
    """
    import time

    import httpx

    max_retries = 2
    last_exc: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(
                    f"{ollama_base_url}/api/embeddings",
                    json={"model": embed_model, "prompt": text},
                )
                resp.raise_for_status()
                embedding = resp.json().get("embedding", [])
                if not embedding:
                    raise ValueError("Ollama returned empty embedding vector")
                return embedding
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries:
                logger.warning(
                    "Embedding attempt %d failed: %s — retrying in 2s", attempt + 1, exc
                )
                time.sleep(2)

    raise RuntimeError(f"Embedding failed after {max_retries + 1} attempts: {last_exc}")


# =============================================================
# Milvus Storage
# =============================================================


def ensure_collection(
    milvus_uri: str,
    collection_name: str,
    dim: int = 768,
) -> None:
    """
    Create a Milvus collection if it does not already exist.

    Schema:
        id          : VARCHAR(64) — primary key (UUID string)
        embedding   : FLOAT_VECTOR(dim) — the chunk embedding
        text        : VARCHAR(65535) — chunk text
        source      : VARCHAR(500) — document title / filename
        document_id : VARCHAR(64) — parent document UUID
        client_id   : VARCHAR(64) — client UUID or empty string
        doc_type    : VARCHAR(50) — regulation | contract | sop | report | manual
        chunk_index : INT64 — position of chunk within document
    """
    from pymilvus import (  # type: ignore[import]
        CollectionSchema,
        DataType,
        FieldSchema,
        MilvusClient,
    )

    client = MilvusClient(uri=milvus_uri)

    if client.has_collection(collection_name):
        return

    fields = [
        FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=64, is_primary=True),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=500),
        FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="client_id", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="doc_type", dtype=DataType.VARCHAR, max_length=50),
        FieldSchema(name="chunk_index", dtype=DataType.INT64),
    ]
    schema = CollectionSchema(fields=fields, description=f"RAG collection: {collection_name}")

    client.create_collection(
        collection_name=collection_name,
        schema=schema,
        index_params=client.prepare_index_params(
            field_name="embedding",
            index_type="IVF_FLAT",
            metric_type="COSINE",
            params={"nlist": 128},
        ),
    )
    logger.info("Created Milvus collection: %s (dim=%d)", collection_name, dim)


def store_chunks(
    milvus_uri: str,
    collection_name: str,
    chunks: list[str],
    embeddings: list[list[float]],
    document_id: str,
    source: str,
    client_id: str,
    doc_type: str,
) -> int:
    """
    Insert chunk embeddings into a Milvus collection.

    Returns the number of chunks successfully inserted.
    """
    import uuid as _uuid

    from pymilvus import MilvusClient  # type: ignore[import]

    if not chunks or not embeddings:
        return 0

    client = MilvusClient(uri=milvus_uri)

    data: list[dict[str, Any]] = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        data.append(
            {
                "id": str(_uuid.uuid4()),
                "embedding": embedding,
                "text": chunk[:65000],  # Truncate to Milvus VARCHAR limit
                "source": source[:500],
                "document_id": document_id,
                "client_id": client_id or "",
                "doc_type": doc_type,
                "chunk_index": i,
            }
        )

    result = client.insert(collection_name=collection_name, data=data)
    inserted = len(result.get("ids", data))
    logger.info(
        "Stored %d chunks in Milvus collection '%s' for document %s",
        inserted,
        collection_name,
        document_id,
    )
    return inserted
