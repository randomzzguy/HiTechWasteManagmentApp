#!/usr/bin/env python3
"""
Hi-Tech Waste Management - RAG Document Ingestion Script
Ingests regulatory PDFs and SOPs into Milvus for the AI assistant.

Usage:
    cd backend
    python ../scripts/ingest_docs.py --dir ../docs/
    python ../scripts/ingest_docs.py --file ../docs/sw_codes_malaysia.pdf --type regulation
"""
import sys, os, argparse, asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/backend")

# Override Docker service hostnames to localhost for local script execution
for k, v in {
    "DATABASE_URL": "postgresql://hitech:password@localhost:5432/hitech_waste",
    "REDIS_URL":    "redis://localhost:6379",
    "MILVUS_HOST":  "localhost",
    "OLLAMA_BASE_URL": "http://localhost:11434",
}.items():
    os.environ[k] = v

import uuid
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import text
from database import AsyncSessionLocal
from config import get_settings

settings = get_settings()

# Document catalogue — maps filename patterns to metadata
DOC_CATALOGUE = {
    "sw_codes_malaysia":       {"title": "Malaysia Scheduled Waste Codes — First Schedule (EQA 1974)", "doc_type": "regulation"},
    "eqa_act_127":             {"title": "Environmental Quality Act 1974 (Act 127)",                   "doc_type": "regulation"},
    "eswis_guide":             {"title": "e-SWIS Consignment Note User Guide — DOE Malaysia",          "doc_type": "regulation"},
    "ghg_scope3_methodology":  {"title": "GHG Protocol — Scope 3 Category 5 Methodology",             "doc_type": "manual"},
    "carbon_emission_factors": {"title": "Malaysia Carbon Emission Factors (MyCC / IPCC AR6)",        "doc_type": "manual"},
}

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".csv"}


async def ingest_file(file_path: str, doc_type: str, title: str, client_id: str | None = None) -> dict:
    """Ingest a single document into the RAG knowledge base."""
    from rag.pipeline import extract_text, clean_text, chunk_text, generate_embedding, ensure_collection, store_chunks

    collection = f"client_{client_id.replace('-','')}" if client_id else "hitech_rag"
    milvus_uri = f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}"
    doc_id = str(uuid.uuid4())

    print(f"  Processing: {os.path.basename(file_path)}")

    # Determine MIME type
    ext = Path(file_path).suffix.lower()
    mime_map = {".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ".txt": "text/plain", ".md": "text/markdown", ".csv": "text/csv"}
    mime_type = mime_map.get(ext, "text/plain")

    # Extract and chunk
    raw_text = extract_text(file_path, mime_type)
    if not raw_text.strip():
        print(f"    WARNING: No text extracted from {file_path}")
        return {"success": False, "error": "No text extracted"}

    cleaned = clean_text(raw_text)
    chunks = chunk_text(cleaned, chunk_size=800, overlap=100)
    print(f"    Chunks: {len(chunks)}")

    # Embed
    embeddings = []
    for i, chunk in enumerate(chunks):
        try:
            emb = generate_embedding(chunk, settings.OLLAMA_BASE_URL, settings.OLLAMA_EMBED_MODEL)
            embeddings.append(emb)
            if (i + 1) % 10 == 0:
                print(f"    Embedded {i+1}/{len(chunks)} chunks...")
        except Exception as e:
            print(f"    WARNING: Embedding failed for chunk {i}: {e}")
            embeddings.append([])

    valid_pairs = [(c, e) for c, e in zip(chunks, embeddings) if e]
    if not valid_pairs:
        return {"success": False, "error": "All embeddings failed"}

    valid_chunks, valid_embeddings = zip(*valid_pairs)

    # Store in Milvus
    ensure_collection(milvus_uri, collection, dim=len(valid_embeddings[0]))
    stored = store_chunks(
        milvus_uri=milvus_uri, collection_name=collection,
        chunks=list(valid_chunks), embeddings=list(valid_embeddings),
        document_id=doc_id, source=title,
        client_id=client_id or "", doc_type=doc_type,
    )

    # Record in DB
    async with AsyncSessionLocal() as session:
        await session.execute(text("""
            INSERT INTO documents (id, title, doc_type, client_id, file_path, mime_type, ingested_into_rag, milvus_collection, uploaded_at)
            VALUES (:id, :title, :dtype, :cid, :fpath, :mime, TRUE, :coll, :now)
            ON CONFLICT DO NOTHING
        """), {
            "id": doc_id, "title": title, "dtype": doc_type,
            "cid": client_id, "fpath": file_path, "mime": mime_type,
            "coll": collection, "now": datetime.now(timezone.utc),
        })
        await session.commit()

    print(f"    Stored {stored} chunks in collection '{collection}'")
    return {"success": True, "doc_id": doc_id, "chunks_stored": stored}


async def ingest_directory(directory: str) -> None:
    """Ingest all supported documents in a directory."""
    dir_path = Path(directory)
    if not dir_path.exists():
        print(f"ERROR: Directory not found: {directory}")
        return

    files = [f for f in dir_path.iterdir() if f.suffix.lower() in SUPPORTED_EXTENSIONS]
    if not files:
        print(f"No supported documents found in {directory}")
        return

    print(f"Found {len(files)} documents to ingest from {directory}\n")
    results = {"success": 0, "failed": 0}

    for f in files:
        # Look up metadata from catalogue
        stem = f.stem.lower().replace("-", "_").replace(" ", "_")
        meta = next((v for k, v in DOC_CATALOGUE.items() if k in stem), None)
        if meta:
            title = meta["title"]
            doc_type = meta["doc_type"]
        else:
            title = f.stem.replace("_", " ").replace("-", " ").title()
            doc_type = "manual"

        result = await ingest_file(str(f), doc_type, title)
        if result["success"]:
            results["success"] += 1
        else:
            results["failed"] += 1

    print(f"\nIngestion complete: {results['success']} succeeded, {results['failed']} failed")


def main():
    parser = argparse.ArgumentParser(description="Ingest documents into the RAG knowledge base")
    parser.add_argument("--dir",    help="Directory of documents to ingest")
    parser.add_argument("--file",   help="Single file to ingest")
    parser.add_argument("--type",   default="manual", help="Document type: regulation|contract|sop|report|manual")
    parser.add_argument("--title",  help="Document title (for single file)")
    parser.add_argument("--client", help="Client UUID to scope the document (optional)")
    args = parser.parse_args()

    if not args.dir and not args.file:
        parser.print_help()
        sys.exit(1)

    if args.file:
        title = args.title or Path(args.file).stem.replace("_", " ").title()
        asyncio.run(ingest_file(args.file, args.type, title, args.client))
    elif args.dir:
        asyncio.run(ingest_directory(args.dir))


if __name__ == "__main__":
    main()
