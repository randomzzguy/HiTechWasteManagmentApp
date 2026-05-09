# =============================================================
# Hi-Tech Waste Management — AI Router
# RAG chat (SSE streaming), agent events, document ingestion,
# and RAG system health endpoint
# =============================================================

from __future__ import annotations

import json
import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from config import get_settings
from database import get_db
from fastapi import APIRouter, Depends, File, HTTPException, Path, Query, UploadFile, status
from models.document import AgentEvent, AgentEventMarkRead, AgentEventRead, Document
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from routers.auth import get_current_user

# Database Agent imports
from agents.database_agent import (
    DatabaseAgent,
    DatabaseAction,
    DatabaseOperationRequest,
    DatabaseOperationResult,
    EntityType,
    get_database_agent_system_prompt,
    DB_AGENT_FUNCTIONS,
    PendingOperation,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# In-memory storage for pending database operations (per session)
# In production, use Redis or database-backed session storage
_pending_db_operations: Dict[str, Dict[str, Any]] = {}

router = APIRouter()

# =============================================================
# Request / Response Schemas
# =============================================================


class ChatMessage(BaseModel):
    """A single message in a conversation history."""

    role: str = Field(
        ...,
        description="Message role: 'user' | 'assistant' | 'system'",
    )
    content: str = Field(..., description="Message text content")


class ChatRequest(BaseModel):
    """Request body for POST /ai/chat."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=8192,
        description="The user's current message / query",
    )
    conversation_history: Optional[List[ChatMessage]] = Field(
        default=None,
        description=(
            "Previous messages in the conversation for multi-turn context. "
            "Oldest messages first, newest last."
        ),
    )
    client_id: Optional[uuid.UUID] = Field(
        default=None,
        description=(
            "Optional client UUID to scope the RAG retrieval to "
            "documents and data belonging to a specific client."
        ),
    )
    use_rag: bool = Field(
        default=True,
        description=(
            "Whether to retrieve relevant context from the vector store "
            "before generating the response. Set to False for pure LLM chat."
        ),
    )
    collection_name: Optional[str] = Field(
        default=None,
        description=(
            "Specific Milvus collection to search. "
            "If omitted, searches the default collection."
        ),
    )
    max_context_chunks: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of RAG context chunks to retrieve and inject.",
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="LLM sampling temperature (0=deterministic, 2=highly creative)",
    )

    model_config = ConfigDict(str_strip_whitespace=True)


class DocumentIngestRequest(BaseModel):
    """Metadata payload for POST /ai/ingest-document (when not uploading a file)."""

    title: str = Field(..., max_length=500)
    doc_type: str = Field(
        ...,
        description="regulation | contract | sop | report | manual",
    )
    client_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Client this document belongs to; null for platform-wide documents",
    )
    file_path: Optional[str] = Field(
        default=None,
        description="Existing file path if the document is already on disk",
    )
    mime_type: Optional[str] = Field(
        default=None,
        max_length=100,
        description="MIME type, e.g. application/pdf",
    )
    milvus_collection: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Target Milvus collection name (defaults to 'hitech_rag')",
    )

    model_config = ConfigDict(str_strip_whitespace=True)


# =============================================================
# RAG Context Retrieval Helper
# =============================================================


async def _retrieve_rag_context(
    query: str,
    client_id: Optional[uuid.UUID],
    collection_name: Optional[str],
    top_k: int,
) -> List[Dict[str, Any]]:
    """
    Retrieves relevant context chunks from Milvus for a given query.

    Steps:
    1. Generate a query embedding via Ollama's embedding model.
    2. Search the specified (or default) Milvus collection.
    3. Return the top-k results as a list of context dicts.

    Returns an empty list on any error so the chat endpoint gracefully
    degrades to pure LLM generation when the vector store is unavailable.
    """
    try:
        from pymilvus import MilvusClient  # type: ignore[import]

        # Step 1 — Generate query embedding
        async with httpx.AsyncClient(timeout=30.0) as http:
            embed_resp = await http.post(
                f"{settings.OLLAMA_BASE_URL}/api/embeddings",
                json={
                    "model": settings.OLLAMA_EMBED_MODEL,
                    "prompt": query,
                },
            )
            embed_resp.raise_for_status()
            embedding = embed_resp.json().get("embedding", [])

        if not embedding:
            logger.warning("Ollama returned empty embedding for RAG query")
            return []

        # Step 2 — Search Milvus
        target_collection = (
            collection_name
            or (f"client_{str(client_id).replace('-', '')}" if client_id else None)
            or "hitech_rag"
        )

        client = MilvusClient(
            uri=f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}"
        )

        search_params = {"metric_type": "COSINE", "params": {"nprobe": 16}}

        # Build filter expression if client-scoped
        filter_expr = None
        if client_id:
            filter_expr = f'client_id == "{str(client_id)}"'

        results = client.search(
            collection_name=target_collection,
            data=[embedding],
            anns_field="embedding",
            search_params=search_params,
            limit=top_k,
            output_fields=["text", "source", "client_id", "doc_type", "chunk_index"],
            filter=filter_expr,
        )

        chunks: List[Dict[str, Any]] = []
        for hit_list in results:
            for hit in hit_list:
                entity = hit.get("entity", {})
                chunks.append(
                    {
                        "text": entity.get("text", ""),
                        "source": entity.get("source", "Unknown"),
                        "doc_type": entity.get("doc_type", ""),
                        "score": hit.get("distance", 0.0),
                        "chunk_index": entity.get("chunk_index", 0),
                    }
                )

        logger.debug(
            "RAG retrieved %d chunks from collection '%s'",
            len(chunks),
            target_collection,
        )
        return chunks

    except Exception as exc:
        logger.warning("RAG context retrieval failed: %s", exc)
        return []


def _build_system_prompt(
    context_chunks: List[Dict[str, Any]],
    client_id: Optional[uuid.UUID],
) -> str:
    """
    Builds the system prompt injected before the user message.

    When context chunks are available, they are formatted as a numbered
    list under a "CONTEXT" section so the LLM can reference them.
    """
    base_prompt = (
        "You are HiTech AI, the intelligent assistant for Hi-Tech Waste Management "
        "Sdn. Bhd., a Malaysian environmental services company specialising in "
        "waste collection, scheduled waste compliance, recyclables recovery, "
        "witnessed destruction, BSF bioconversion, and ESG reporting.\n\n"
        "You have deep knowledge of:\n"
        "- Malaysian environmental regulations (EQA 1974, Scheduled Wastes Regulations 2005)\n"
        "- DOE compliance requirements and scheduled waste codes (SW codes)\n"
        "- Waste diversion and circular economy principles\n"
        "- Carbon accounting and ESG reporting frameworks (GHG Protocol, IPCC)\n"
        "- Hi-Tech's operations, client management, and service portfolio\n\n"
        "Always be accurate, professional, and concise. "
        "If you are uncertain, say so rather than guessing. "
        "When citing regulations, reference the specific section or clause."
    )

    if client_id:
        base_prompt += (
            f"\n\nYou are currently assisting with data scoped to client ID: {client_id}. "
            "Focus your responses on this client's waste streams, compliance status, "
            "and service history where relevant."
        )

    if context_chunks:
        context_section = "\n\n--- RELEVANT CONTEXT ---\n"
        for i, chunk in enumerate(context_chunks, 1):
            source = chunk.get("source", "Unknown")
            text = chunk.get("text", "").strip()
            context_section += f"\n[{i}] Source: {source}\n{text}\n"
        context_section += "\n--- END CONTEXT ---\n"
        context_section += (
            "\nUse the above context to inform your answer. "
            "If the context does not contain the answer, rely on your general knowledge "
            "but indicate that the information is not from the retrieved documents."
        )
        base_prompt += context_section

    return base_prompt


# =============================================================
# POST /chat — RAG SSE streaming chat
# =============================================================


@router.post(
    "/chat",
    summary="RAG-augmented streaming chat",
    description=(
        "Accepts a user message and optional conversation history. "
        "Retrieves relevant context from the Milvus vector store (RAG), "
        "injects it into the prompt, and streams the Ollama LLM response "
        "as Server-Sent Events (SSE). "
        "Each SSE event contains a token chunk in the `data` field. "
        "A final `[DONE]` event signals completion."
    ),
)
async def chat(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> EventSourceResponse:
    """
    RAG-augmented LLM chat with SSE streaming.

    **Flow:**
    1. Retrieve relevant context chunks from Milvus (if `use_rag=True`).
    2. Build a system prompt with injected context.
    3. Construct the full message list (system + history + user message).
    4. Stream the Ollama `/api/chat` response token-by-token as SSE events.

    **SSE event format:**
    ```
    data: {"token": "Hello", "done": false}
    data: {"token": " world", "done": false}
    data: {"token": "", "done": true, "total_tokens": 42}
    ```

    **Client disconnection** is handled gracefully — streaming stops when
    the client closes the connection.
    """
    # Apply client-portal scoping
    effective_client_id = payload.client_id
    if current_user.get("role") == "client" and effective_client_id is None:
        from models.client import Client as ClientModel

        client_result = await db.execute(
            select(ClientModel).where(
                ClientModel.portal_user_id == uuid.UUID(current_user["sub"])
            )
        )
        client_obj = client_result.scalar_one_or_none()
        if client_obj:
            effective_client_id = client_obj.id

    # Snapshot values for the async generator (avoid closure-over-mutable issues)
    user_message = payload.message
    conversation_history = payload.conversation_history or []
    use_rag = payload.use_rag
    collection_name = payload.collection_name
    max_chunks = payload.max_context_chunks
    temperature = payload.temperature

    async def event_generator() -> AsyncGenerator[Dict[str, Any], None]:
        """
        Async generator that:
        1. Optionally retrieves RAG context.
        2. Streams Ollama /api/chat response as SSE events.
        3. Handles errors gracefully with an error SSE event.
        """
        try:
            # Step 1 — RAG context retrieval
            context_chunks: List[Dict[str, Any]] = []
            if use_rag:
                context_chunks = await _retrieve_rag_context(
                    query=user_message,
                    client_id=effective_client_id,
                    collection_name=collection_name,
                    top_k=max_chunks,
                )

            # Step 2 — Build system prompt
            system_prompt = _build_system_prompt(context_chunks, effective_client_id)

            # Step 3 — Construct Ollama messages
            messages: List[Dict[str, str]] = [
                {"role": "system", "content": system_prompt}
            ]

            # Add conversation history (last 10 turns to avoid context overflow)
            recent_history = conversation_history[-20:] if conversation_history else []
            for hist_msg in recent_history:
                messages.append({"role": hist_msg.role, "content": hist_msg.content})

            # Add current user message
            messages.append({"role": "user", "content": user_message})

            # Send a metadata event with RAG info before streaming tokens
            yield {
                "event": "metadata",
                "data": json.dumps(
                    {
                        "model": settings.OLLAMA_MODEL,
                        "rag_chunks_used": len(context_chunks),
                        "client_id": str(effective_client_id)
                        if effective_client_id
                        else None,
                    }
                ),
            }

            # Step 4 — Stream Ollama response
            total_tokens = 0
            full_response = ""

            async with httpx.AsyncClient(timeout=120.0) as http_client:
                async with http_client.stream(
                    "POST",
                    f"{settings.OLLAMA_BASE_URL}/api/chat",
                    json={
                        "model": settings.OLLAMA_MODEL,
                        "messages": messages,
                        "stream": True,
                        "options": {
                            "temperature": temperature,
                            "num_predict": 2048,
                        },
                    },
                ) as response:
                    if response.status_code != 200:
                        error_body = await response.aread()
                        logger.error(
                            "Ollama API error %d: %s",
                            response.status_code,
                            error_body.decode("utf-8", errors="replace"),
                        )
                        yield {
                            "event": "error",
                            "data": json.dumps(
                                {
                                    "error": (
                                        f"LLM service returned status {response.status_code}. "
                                        "Please try again."
                                    )
                                }
                            ),
                        }
                        return

                    async for raw_line in response.aiter_lines():
                        if not raw_line.strip():
                            continue

                        try:
                            chunk_data = json.loads(raw_line)
                        except json.JSONDecodeError:
                            continue

                        message_chunk = chunk_data.get("message", {})
                        token = message_chunk.get("content", "")
                        done = chunk_data.get("done", False)

                        if token:
                            full_response += token
                            total_tokens += 1
                            yield {
                                "event": "token",
                                "data": json.dumps({"token": token, "done": False}),
                            }

                        if done:
                            eval_count = chunk_data.get("eval_count", total_tokens)
                            yield {
                                "event": "done",
                                "data": json.dumps(
                                    {
                                        "token": "",
                                        "done": True,
                                        "total_tokens": eval_count,
                                        "rag_chunks_used": len(context_chunks),
                                    }
                                ),
                            }
                            break

        except httpx.ConnectError:
            logger.error("Cannot connect to Ollama at %s", settings.OLLAMA_BASE_URL)
            yield {
                "event": "error",
                "data": json.dumps(
                    {
                        "error": (
                            "The AI service is currently unreachable. "
                            f"Please ensure Ollama is running at {settings.OLLAMA_BASE_URL}."
                        )
                    }
                ),
            }
        except httpx.TimeoutException:
            logger.error(
                "Ollama request timed out for user %s", current_user.get("sub")
            )
            yield {
                "event": "error",
                "data": json.dumps(
                    {
                        "error": (
                            "The AI service timed out. "
                            "Please try a shorter message or retry later."
                        )
                    }
                ),
            }
        except Exception as exc:
            logger.exception(
                "Unexpected error in chat SSE stream for user %s: %s",
                current_user.get("sub"),
                exc,
            )
            yield {
                "event": "error",
                "data": json.dumps(
                    {
                        "error": (
                            "An unexpected error occurred during AI response generation. "
                            "Please try again."
                        )
                    }
                ),
            }

    return EventSourceResponse(event_generator())


# =============================================================
# GET /agent-events — list agent events
# =============================================================


@router.get(
    "/agent-events",
    response_model=Dict[str, Any],
    summary="List agent events",
    description=(
        "Returns a paginated list of events emitted by the AI agents. "
        "Filter by is_read status, agent_name, severity, and event_type."
    ),
)
# Alias for frontend compatibility
@router.get(
    "/agent/events",
    response_model=Dict[str, Any],
    summary="List agent events (alias)",
    description="Alias for /agent-events for frontend compatibility.",
    include_in_schema=False,
)
async def list_agent_events(
    skip: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=50, ge=1, le=500, description="Max records to return"),
    is_read: Optional[bool] = Query(
        default=None,
        description="Filter by read status (True=read, False=unread)",
    ),
    agent_name: Optional[str] = Query(
        default=None,
        description=(
            "Filter by agent name, e.g. ComplianceAgent, FleetAgent, ESGAgent"
        ),
    ),
    severity: Optional[str] = Query(
        default=None,
        description="Filter by severity: info | warning | critical",
    ),
    event_type: Optional[str] = Query(
        default=None,
        description="Filter by event type: alert | action | recommendation | report",
    ),
    reference_type: Optional[str] = Query(
        default=None,
        description="Filter by reference entity type, e.g. 'ScheduledWasteBatch'",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Returns a paginated, filterable list of AI agent events.

    Agent events are emitted automatically by the platform's AI agents:
    - **ComplianceAgent**: scheduled waste deadline alerts
    - **FleetAgent**: maintenance due alerts, route efficiency recommendations
    - **ESGAgent**: carbon impact reports, diversion rate trend alerts
    - **BillingAgent**: overdue invoice notifications
    - **RAGAgent**: document ingestion status and query logs
    """
    filters: list = []

    if is_read is not None:
        filters.append(AgentEvent.is_read == is_read)
    if agent_name:
        filters.append(AgentEvent.agent_name.ilike(f"%{agent_name}%"))
    if severity:
        filters.append(AgentEvent.severity == severity)
    if event_type:
        filters.append(AgentEvent.event_type == event_type)
    if reference_type:
        filters.append(AgentEvent.reference_type == reference_type)

    base_stmt = select(AgentEvent)
    if filters:
        base_stmt = base_stmt.where(and_(*filters))

    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total_result = await db.execute(count_stmt)
    total: int = total_result.scalar_one()

    # Unread critical events first, then by created_at descending
    stmt = (
        base_stmt.order_by(
            AgentEvent.is_read.asc(),
            AgentEvent.severity.desc(),
            AgentEvent.created_at.desc(),
        )
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    events = result.scalars().all()

    # Summary counts for the dashboard notification badge
    unread_stmt = select(func.count()).where(AgentEvent.is_read == False)  # noqa: E712
    unread_result = await db.execute(unread_stmt)
    unread_count: int = unread_result.scalar_one()

    critical_unread_stmt = select(func.count()).where(
        and_(
            AgentEvent.is_read == False,  # noqa: E712
            AgentEvent.severity == "critical",
        )
    )
    critical_result = await db.execute(critical_unread_stmt)
    critical_unread_count: int = critical_result.scalar_one()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "unread_count": unread_count,
        "critical_unread_count": critical_unread_count,
        "items": [AgentEventRead.model_validate(e) for e in events],
    }


# =============================================================
# PATCH /agent-events/{id}/read — mark event as read
# =============================================================


@router.patch(
    "/agent-events/{event_id}/read",
    response_model=AgentEventRead,
    summary="Mark an agent event as read",
    description="Sets the is_read flag on an agent event to True (or False to unmark).",
)
async def mark_event_read(
    event_id: uuid.UUID,
    payload: AgentEventMarkRead,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> AgentEventRead:
    """
    Marks an agent event as read (or unread if is_read=False is provided).

    Typically called when a user clicks on a notification in the UI
    to dismiss it from the unread badge count.
    """
    result = await db.execute(select(AgentEvent).where(AgentEvent.id == event_id))
    event = result.scalar_one_or_none()

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent event {event_id} not found",
        )

    event.is_read = payload.is_read
    await db.flush()
    await db.refresh(event)

    logger.debug(
        "AgentEvent %s marked is_read=%s by user %s",
        event_id,
        payload.is_read,
        current_user.get("sub"),
    )
    return AgentEventRead.model_validate(event)


# =============================================================
# POST /agent-events/mark-all-read — bulk mark all as read
# =============================================================


@router.post(
    "/agent-events/mark-all-read",
    response_model=Dict[str, Any],
    summary="Mark all agent events as read",
    description=(
        "Bulk-marks all unread agent events as read. "
        "Optionally filter by severity to only clear events of a specific severity."
    ),
)
async def mark_all_events_read(
    severity: Optional[str] = Query(
        default=None,
        description="Only mark events of this severity: info | warning | critical",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """Bulk-marks unread agent events as read."""
    from sqlalchemy import update

    filters: list = [AgentEvent.is_read == False]  # noqa: E712
    if severity:
        filters.append(AgentEvent.severity == severity)

    stmt = (
        update(AgentEvent)
        .where(and_(*filters))
        .values(is_read=True)
        .returning(func.count())
    )
    result = await db.execute(stmt)
    # Count may not be directly available — use a count query instead
    count_result = await db.execute(
        select(func.count()).where(
            and_(AgentEvent.is_read == True)  # noqa: E712
        )
    )

    logger.info(
        "All agent events marked as read by user %s (severity filter: %s)",
        current_user.get("sub"),
        severity or "all",
    )

    return {
        "message": "All matching agent events have been marked as read.",
        "severity_filter": severity,
    }


# =============================================================
# POST /ingest-document — upload and ingest a document into RAG
# =============================================================


@router.post(
    "/ingest-document",
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest a document into the RAG knowledge base",
    description=(
        "Uploads a document file, saves it to disk, creates a Document DB record, "
        "and triggers a Celery task to chunk, embed, and store the content in Milvus. "
        "Returns the document metadata and the Celery task_id for status polling."
    ),
)
async def ingest_document(
    file: Optional[UploadFile] = File(default=None),
    title: Optional[str] = Query(default=None, max_length=500),
    doc_type: str = Query(
        default="manual",
        description="regulation | contract | sop | report | manual",
    ),
    client_id: Optional[str] = Query(
        default=None,
        description="Client UUID (optional — omit for platform-wide documents)",
    ),
    milvus_collection: Optional[str] = Query(
        default=None,
        max_length=100,
        description="Target Milvus collection (defaults to 'hitech_rag')",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Uploads a document and triggers RAG ingestion.

    **Upload workflow:**
    1. Validate and save the uploaded file to REPORT_OUTPUT_DIR/rag_documents/.
    2. Create a Document record in the database.
    3. Queue a Celery task (`tasks.rag_tasks.ingest_document`) to:
       a. Extract text from the document (PDF, DOCX, TXT supported).
       b. Chunk the text into overlapping segments.
       c. Generate embeddings via Ollama.
       d. Store chunks + embeddings in Milvus.
       e. Mark the Document record as `ingested_into_rag=True`.
    4. Return document metadata and task_id for status polling.

    **Supported file types:** PDF, DOCX, TXT, CSV, Markdown
    """
    import os
    import shutil

    if file is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A file must be uploaded",
        )

    # RBAC: only management / superadmin may upload documents
    if current_user.get("role") not in {"management", "superadmin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only management roles can upload documents to the knowledge base",
        )

    # Validate MIME type
    ALLOWED_MIME_TYPES = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
        "text/plain",
        "text/csv",
        "text/markdown",
        "application/octet-stream",  # fallback for some clients
        "image/png",
        "image/jpeg",
        "image/webp",
        "image/tiff",
    }
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Unsupported file type: {file.content_type}. "
                f"Allowed types: {', '.join(sorted(ALLOWED_MIME_TYPES - {'application/octet-stream'}))}"
            ),
        )

    # File size limit: 50 MB
    MAX_SIZE_BYTES = 50 * 1024 * 1024
    file_content = await file.read()
    if len(file_content) > MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds the 50 MB limit. Uploaded: {len(file_content) / 1024 / 1024:.1f} MB",
        )

    # Resolve client UUID
    resolved_client_id: Optional[uuid.UUID] = None
    if client_id:
        try:
            resolved_client_id = uuid.UUID(client_id)
            from models.client import Client as ClientModel

            client_result = await db.execute(
                select(ClientModel).where(ClientModel.id == resolved_client_id)
            )
            if client_result.scalar_one_or_none() is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Client {client_id} not found",
                )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid client_id format: {client_id}",
            )

    # Save file to disk
    upload_dir = os.path.join(settings.REPORT_OUTPUT_DIR, "rag_documents")
    os.makedirs(upload_dir, exist_ok=True)

    doc_id = uuid.uuid4()
    safe_filename = f"{doc_id}_{file.filename}"
    file_path = os.path.join(upload_dir, safe_filename)

    try:
        with open(file_path, "wb") as f:
            f.write(file_content)
    except OSError as exc:
        logger.error("Failed to save uploaded document: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save uploaded document",
        )

    # Resolve title from filename if not provided
    document_title = title or file.filename or safe_filename

    # Determine Milvus collection
    target_collection = milvus_collection or (
        f"client_{str(resolved_client_id).replace('-', '')}"
        if resolved_client_id
        else "hitech_rag"
    )

    # Create Document DB record
    doc = Document(
        id=doc_id,
        title=document_title,
        doc_type=doc_type,
        client_id=resolved_client_id,
        file_path=file_path,
        mime_type=file.content_type,
        ingested_into_rag=False,
        milvus_collection=target_collection,
        uploaded_by=uuid.UUID(current_user["sub"]),
        uploaded_at=datetime.now(timezone.utc),
        file_size_bytes=len(file_content),
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)

    # Queue Celery ingestion task
    task_id: Optional[str] = None
    task_status = "pending"

    try:
        from tasks.rag_tasks import ingest_document_task  # type: ignore[import]

        task = ingest_document_task.delay(
            document_id=str(doc_id),
            file_path=file_path,
            collection_name=target_collection,
            client_id=str(resolved_client_id) if resolved_client_id else None,
            doc_type=doc_type,
        )
        task_id = task.id
        task_status = "queued"
        logger.info(
            "Document ingestion task queued: doc_id=%s task_id=%s collection=%s",
            doc_id,
            task_id,
            target_collection,
        )
    except Exception as exc:
        logger.warning(
            "Could not queue document ingestion task for doc %s: %s",
            doc_id,
            exc,
        )
        task_status = "worker_unavailable"

    logger.info(
        "Document '%s' uploaded and registered (id=%s) by user %s",
        document_title,
        doc_id,
        current_user["sub"],
    )

    return {
        "document_id": str(doc_id),
        "title": document_title,
        "doc_type": doc_type,
        "client_id": str(resolved_client_id) if resolved_client_id else None,
        "file_path": file_path,
        "mime_type": file.content_type,
        "file_size_bytes": len(file_content),
        "ingested_into_rag": False,
        "milvus_collection": target_collection,
        "uploaded_by": current_user["sub"],
        "uploaded_at": doc.uploaded_at.isoformat(),
        "task_id": task_id,
        "task_status": task_status,
        "message": (
            "Document uploaded and ingestion task queued. "
            f"Poll GET /ai/rag-status to monitor progress (task_id={task_id})."
            if task_id
            else (
                "Document uploaded. "
                "Ingestion could not be queued — ensure the Celery worker is running."
            )
        ),
    }


# =============================================================
# GET /rag-status — RAG system health and statistics
# =============================================================


@router.get(
    "/rag-status",
    response_model=Dict[str, Any],
    summary="RAG system health and statistics",
    description=(
        "Returns the health status of the RAG subsystem: "
        "Milvus connectivity, available collections, document counts, "
        "and Ollama embedding model availability."
    ),
)
async def rag_status(
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Checks the health and reports statistics for the RAG subsystem.

    **Checks performed:**
    1. **Milvus connectivity**: Can the backend connect to the Milvus gRPC endpoint?
    2. **Milvus collections**: Lists all available collections and their document counts.
    3. **Ollama embedding model**: Is the configured embedding model available?
    4. **DB document stats**: Number of documents in the DB vs ingested into RAG.

    Returns a structured health report suitable for the system settings panel
    and the backend `/health` endpoint.
    """
    health: Dict[str, Any] = {
        "milvus": {
            "connected": False,
            "host": settings.MILVUS_HOST,
            "port": settings.MILVUS_PORT,
            "collections": [],
            "error": None,
        },
        "ollama": {
            "connected": False,
            "base_url": settings.OLLAMA_BASE_URL,
            "chat_model": settings.OLLAMA_MODEL,
            "embed_model": settings.OLLAMA_EMBED_MODEL,
            "available_models": [],
            "error": None,
        },
        "documents": {
            "total_in_db": 0,
            "ingested_into_rag": 0,
            "pending_ingestion": 0,
        },
        "overall_status": "degraded",
    }

    # ── Check Milvus ──────────────────────────────────────────
    try:
        from pymilvus import MilvusClient  # type: ignore[import]

        milvus_client = MilvusClient(
            uri=f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}"
        )
        collections = milvus_client.list_collections()

        collection_stats = []
        for coll_name in collections:
            try:
                stats = milvus_client.get_collection_stats(coll_name)
                row_count = (
                    int(stats.get("row_count", 0)) if isinstance(stats, dict) else 0
                )
                collection_stats.append(
                    {
                        "name": coll_name,
                        "row_count": row_count,
                    }
                )
            except Exception:
                collection_stats.append({"name": coll_name, "row_count": "unknown"})

        health["milvus"]["connected"] = True
        health["milvus"]["collections"] = collection_stats
        health["milvus"]["collection_count"] = len(collections)

    except Exception as exc:
        health["milvus"]["error"] = str(exc)
        logger.warning("Milvus health check failed: %s", exc)

    # ── Check Ollama ──────────────────────────────────────────
    try:
        async with httpx.AsyncClient(timeout=5.0) as http:
            # Check available models
            tags_resp = await http.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if tags_resp.status_code == 200:
                models_data = tags_resp.json()
                available_models = [
                    m.get("name", "") for m in models_data.get("models", [])
                ]
                health["ollama"]["connected"] = True
                health["ollama"]["available_models"] = available_models

                # Verify configured models are available
                health["ollama"]["chat_model_available"] = any(
                    settings.OLLAMA_MODEL in m for m in available_models
                )
                health["ollama"]["embed_model_available"] = any(
                    settings.OLLAMA_EMBED_MODEL in m for m in available_models
                )
            else:
                health["ollama"]["error"] = (
                    f"Ollama API returned status {tags_resp.status_code}"
                )

    except httpx.ConnectError as exc:
        health["ollama"]["error"] = f"Cannot connect to Ollama: {exc}"
        logger.warning("Ollama health check failed: %s", exc)
    except Exception as exc:
        health["ollama"]["error"] = str(exc)
        logger.warning("Ollama health check failed: %s", exc)

    # ── DB Document Statistics ────────────────────────────────
    try:
        total_docs_result = await db.execute(select(func.count(Document.id)))
        total_docs: int = total_docs_result.scalar_one()

        ingested_result = await db.execute(
            select(func.count(Document.id)).where(
                Document.ingested_into_rag == True  # noqa: E712
            )
        )
        ingested_docs: int = ingested_result.scalar_one()

        health["documents"] = {
            "total_in_db": total_docs,
            "ingested_into_rag": ingested_docs,
            "pending_ingestion": total_docs - ingested_docs,
        }

        # Recent documents (last 5)
        recent_docs_result = await db.execute(
            select(Document).order_by(Document.uploaded_at.desc()).limit(5)
        )
        recent_docs = recent_docs_result.scalars().all()
        health["documents"]["recent"] = [
            {
                "id": str(d.id),
                "title": d.title,
                "doc_type": d.doc_type,
                "ingested": d.ingested_into_rag,
                "collection": d.milvus_collection,
                "uploaded_at": d.uploaded_at.isoformat(),
            }
            for d in recent_docs
        ]
    except Exception as exc:
        health["documents"]["error"] = str(exc)
        logger.warning("Document stats query failed: %s", exc)

    # ── Overall Status ────────────────────────────────────────
    milvus_ok = health["milvus"]["connected"]
    ollama_ok = health["ollama"]["connected"]

    if milvus_ok and ollama_ok:
        health["overall_status"] = "ok"
    elif not milvus_ok and not ollama_ok:
        health["overall_status"] = "critical"
    else:
        health["overall_status"] = "degraded"

    health["checked_at"] = datetime.now(timezone.utc).isoformat()

    return health


# =============================================================
# GET /documents — list ingested documents
# =============================================================


@router.get(
    "/documents",
    response_model=Dict[str, Any],
    summary="List documents in the RAG knowledge base",
    description=(
        "Returns a paginated list of documents that have been uploaded "
        "to the platform, with their ingestion status."
    ),
)
async def list_documents(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    ingested_only: bool = Query(
        default=False,
        description="Return only documents that have been ingested into Milvus",
    ),
    doc_type: Optional[str] = Query(
        default=None,
        description="Filter by document type: regulation | contract | sop | report | manual",
    ),
    client_id: Optional[uuid.UUID] = Query(
        default=None,
        description="Filter by client UUID",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """Returns a paginated list of uploaded documents with RAG ingestion status."""

    filters: list = []

    if ingested_only:
        filters.append(Document.ingested_into_rag == True)  # noqa: E712
    if doc_type:
        filters.append(Document.doc_type == doc_type)
    if client_id:
        filters.append(Document.client_id == client_id)

    # Client-portal users see only their own documents
    if current_user.get("role") == "client" and client_id is None:
        from models.client import Client as ClientModel

        client_result = await db.execute(
            select(ClientModel).where(
                ClientModel.portal_user_id == uuid.UUID(current_user["sub"])
            )
        )
        client_obj = client_result.scalar_one_or_none()
        if client_obj:
            filters.append(Document.client_id == client_obj.id)

    base_stmt = select(Document)
    if filters:
        base_stmt = base_stmt.where(and_(*filters))

    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total_result = await db.execute(count_stmt)
    total: int = total_result.scalar_one()

    stmt = base_stmt.order_by(Document.uploaded_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    documents = result.scalars().all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": [
            {
                "id": str(d.id),
                "title": d.title,
                "doc_type": d.doc_type,
                "client_id": str(d.client_id) if d.client_id else None,
                "mime_type": d.mime_type,
                "ingested_into_rag": d.ingested_into_rag,
                "milvus_collection": d.milvus_collection,
                "uploaded_by": str(d.uploaded_by) if d.uploaded_by else None,
                "uploaded_at": d.uploaded_at.isoformat(),
                "file_size_bytes": d.file_size_bytes,
                "ingestion_error": d.ingestion_error,
            }
            for d in documents
        ],
    }


# =============================================================
# DELETE /documents/{id} — remove a document
# =============================================================


@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Delete a document from the knowledge base",
    description=(
        "Deletes a document from the database and optionally removes "
        "its embeddings from Milvus."
    ),
)
async def delete_document(
    document_id: uuid.UUID,
    remove_from_milvus: bool = Query(
        default=True,
        description="Whether to also delete the document's chunks from Milvus",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> None:
    """
    Deletes a document record and optionally its Milvus embeddings.

    Only management / superadmin roles can delete documents.
    Client-portal users cannot delete documents.
    """
    if current_user.get("role") not in {
        "superadmin",
        "management",
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only management roles can delete documents",
        )

    doc_result = await db.execute(select(Document).where(Document.id == document_id))
    doc = doc_result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )

    # Attempt to remove from Milvus if requested
    if remove_from_milvus and doc.ingested_into_rag and doc.milvus_collection:
        try:
            from pymilvus import MilvusClient  # type: ignore[import]

            milvus_client = MilvusClient(
                uri=f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}"
            )
            # Delete by document_id filter expression
            milvus_client.delete(
                collection_name=doc.milvus_collection,
                filter=f'document_id == "{str(document_id)}"',
            )
            logger.info(
                "Removed Milvus embeddings for document %s from collection %s",
                document_id,
                doc.milvus_collection,
            )
        except Exception as exc:
            logger.warning(
                "Failed to remove Milvus embeddings for document %s: %s",
                document_id,
                exc,
            )
            # Non-fatal — proceed with DB deletion

    # Delete DB record
    await db.delete(doc)
    await db.flush()

    logger.info(
        "Document %s ('%s') deleted by user %s",
        document_id,
        doc.title,
        current_user["sub"],
    )


# =============================================================
# POST /documents/{document_id}/re-ingest — re-queue ingestion
# =============================================================


@router.post(
    "/documents/{document_id}/re-ingest",
    status_code=200,
    response_model=Dict[str, Any],
    summary="Re-queue a document for RAG ingestion",
    description=(
        "Resets the ingestion state of a document and re-queues the Celery "
        "ingestion task. Useful for retrying failed ingestions or refreshing "
        "document embeddings after content changes."
    ),
)
async def re_ingest_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """Re-queues ingestion for an existing document, resetting any prior error state."""
    if current_user.get("role") not in {"management", "superadmin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only management roles can re-ingest documents",
        )

    doc = await db.get(Document, document_id)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )

    doc.ingestion_error = None
    doc.ingested_into_rag = False
    await db.flush()

    from tasks.rag_tasks import ingest_document_task  # type: ignore[import]

    task = ingest_document_task.delay(
        document_id=str(document_id),
        file_path=doc.file_path,
        collection_name=doc.milvus_collection or "hitech_rag",
        client_id=str(doc.client_id) if doc.client_id else None,
        doc_type=doc.doc_type,
    )

    logger.info(
        "Re-ingestion task queued: doc_id=%s task_id=%s", document_id, task.id
    )

    return {
        "document_id": str(document_id),
        "title": doc.title,
        "ingested_into_rag": False,
        "ingestion_error": None,
        "task_id": task.id,
        "message": "Re-ingestion task queued successfully.",
    }


# =============================================================
# Database Agent Chat Endpoint
# Chat with AI that can perform database operations
# =============================================================


class DatabaseChatRequest(BaseModel):
    """Request body for POST /ai/chat-db — database-enabled chat."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=8192,
        description="The user's message / query",
    )
    conversation_history: Optional[List[ChatMessage]] = Field(
        default=None,
        description="Previous messages for context",
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Session ID for tracking pending operations",
    )
    client_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Optional client scope",
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="LLM sampling temperature",
    )


class DatabaseChatResponse(BaseModel):
    """Response for database-enabled chat (non-streaming for simplicity)."""

    response: str = Field(..., description="AI assistant's response")
    session_id: str = Field(..., description="Session ID for continuity")
    operations_performed: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Database operations that were executed",
    )
    pending_operation: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Details if awaiting more user input",
    )
    model_config = ConfigDict(str_strip_whitespace=True)


@router.post(
    "/chat-db",
    response_model=DatabaseChatResponse,
    summary="Database-enabled AI chat",
    description=(
        "Chat with the AI assistant that can read and write to the database. "
        "The AI can query records, create new clients/jobs/vehicles, update data, "
        "and delete records (with confirmation). "
        "Use session_id to maintain context across multiple messages for multi-step operations."
    ),
)
async def chat_with_database(
    payload: DatabaseChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> DatabaseChatResponse:
    """
    Chat with AI that has database access capabilities.

    **Features:**
    - Query and search records (clients, jobs, vehicles, etc.)
    - Create new records with field validation
    - Update existing records
    - Delete records (with confirmation)
    - Multi-step data collection for complex operations

    **Supported Entities:**
    - client, job, vehicle, user, scheduled_waste_batch
    - carbon_record, recyclable_record, container, compaction_machine
    - bsf_batch, destruction_job, trip, recurring_job_template

    **Session Management:**
    Provide a session_id to maintain context across multiple messages.
    The AI will remember pending operations (e.g., creating a client
    where you're collecting required fields).
    """
    # Generate or use existing session ID
    session_id = payload.session_id or str(uuid.uuid4())

    # Initialize database agent
    db_agent = DatabaseAgent(db, current_user)

    # Restore pending operations from session storage
    if session_id in _pending_db_operations:
        for op_id, op_data in _pending_db_operations[session_id].items():
            db_agent._pending_operations[op_id] = PendingOperation(**op_data)

    # Build system prompt
    system_prompt = get_database_agent_system_prompt()

    # Add user context
    system_prompt += f"\n\nCurrent user: {current_user.get('full_name', 'Unknown')} (ID: {current_user.get('sub')})"
    system_prompt += f"\nUser role: {current_user.get('role', 'unknown')}"
    if payload.client_id:
        system_prompt += f"\nScoped to client: {payload.client_id}"

    # Check for pending operation in the message
    user_message = payload.message
    operations_performed: List[Dict[str, Any]] = []
    pending_operation: Optional[Dict[str, Any]] = None

    # Try to parse pending operation update from message
    for op_id, pending in list(db_agent._pending_operations.items()):
        # If user is responding to a pending operation, try to extract data
        if pending.missing_required_fields:
            # Try to parse the message as field data
            try:
                # Use LLM to extract field values from natural language
                extracted_data = await _extract_fields_from_message(
                    user_message,
                    pending.missing_required_fields,
                    pending.entity_type,
                )
                if extracted_data:
                    updated_pending = db_agent.update_pending_operation(op_id, extracted_data)
                    if updated_pending and not updated_pending.missing_required_fields:
                        # All fields collected - execute the operation
                        request = DatabaseOperationRequest(
                            action=pending.action,
                            entity_type=pending.entity_type,
                            data=updated_pending.collected_data,
                        )
                        result = await db_agent.execute_operation(request)
                        operations_performed.append(result.model_dump())
                        db_agent.remove_pending_operation(op_id)

                        # Update user message to indicate completion
                        user_message = f"[DATA_COLLECTED] Continue with the {pending.action.value} operation for {pending.entity_type.value}"
            except Exception as exc:
                logger.debug("Could not extract fields from message: %s", exc)

    # Build messages for LLM
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": system_prompt}
    ]

    # Add conversation history (last 10 turns)
    if payload.conversation_history:
        recent_history = payload.conversation_history[-20:]
        for msg in recent_history:
            messages.append({"role": msg.role, "content": msg.content})

    # Add any pending operations info
    active_pending = list(db_agent._pending_operations.values())
    if active_pending:
        pending_context = "\n\nPENDING OPERATIONS:\n"
        for op in active_pending:
            pending_context += f"- Operation {op.operation_id}: {op.action.value} {op.entity_type.value}"
            pending_context += f" (missing: {', '.join(op.missing_required_fields)})\n"
        messages.append({"role": "system", "content": pending_context})

    # Add current user message
    messages.append({"role": "user", "content": user_message})

    # Call Ollama with function calling
    try:
        async with httpx.AsyncClient(timeout=120.0) as http:
            response = await http.post(
                f"{settings.OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": settings.OLLAMA_MODEL,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": payload.temperature,
                        "num_predict": 2048,
                    },
                    "tools": DB_AGENT_FUNCTIONS,
                },
            )
            response.raise_for_status()
            result = response.json()

            # Check if the model wants to call a function
            tool_calls = result.get("message", {}).get("tool_calls", [])
            ai_message = result.get("message", {}).get("content", "")

            # Process tool calls
            if tool_calls:
                for tool_call in tool_calls:
                    function = tool_call.get("function", {})
                    function_name = function.get("name", "")
                    arguments = json.loads(function.get("arguments", "{}"))

                    # Execute database operation
                    operation_result = await _execute_tool_call(
                        function_name, arguments, db_agent
                    )
                    operations_performed.append(operation_result.model_dump())

                    # If operation needs more data, create pending operation
                    if (
                        not operation_result.success
                        and operation_result.error == "MISSING_REQUIRED_FIELDS"
                        and function_name == "create_database"
                    ):
                        pending = db_agent.create_pending_operation(
                            action=DatabaseAction.CREATE,
                            entity_type=EntityType(arguments.get("entity_type")),
                            collected_data=arguments.get("data", {}),
                        )
                        pending_operation = {
                            "operation_id": pending.operation_id,
                            "action": pending.action.value,
                            "entity_type": pending.entity_type.value,
                            "missing_fields": pending.missing_required_fields,
                            "collected_data": pending.collected_data,
                        }

                # Get final response from LLM with operation results
                messages.append({
                    "role": "assistant",
                    "content": ai_message,
                    "tool_calls": tool_calls,
                })

                # Add tool results
                for op_result in operations_performed:
                    messages.append({
                        "role": "tool",
                        "content": json.dumps(op_result),
                    })

                # Get final response
                final_response = await http.post(
                    f"{settings.OLLAMA_BASE_URL}/api/chat",
                    json={
                        "model": settings.OLLAMA_MODEL,
                        "messages": messages,
                        "stream": False,
                        "options": {
                            "temperature": payload.temperature,
                            "num_predict": 2048,
                        },
                    },
                )
                final_response.raise_for_status()
                final_result = final_response.json()
                ai_message = final_result.get("message", {}).get("content", ai_message)

            # Save pending operations to session storage
            _pending_db_operations[session_id] = {
                op_id: {
                    "operation_id": op.operation_id,
                    "action": op.action.value,
                    "entity_type": op.entity_type.value,
                    "collected_data": op.collected_data,
                    "missing_required_fields": op.missing_required_fields,
                    "created_at": op.created_at.isoformat(),
                }
                for op_id, op in db_agent._pending_operations.items()
            }

            return DatabaseChatResponse(
                response=ai_message,
                session_id=session_id,
                operations_performed=operations_performed,
                pending_operation=pending_operation,
            )

    except httpx.ConnectError:
        logger.error("Cannot connect to Ollama at %s", settings.OLLAMA_BASE_URL)
        return DatabaseChatResponse(
            response=(
                f"I'm unable to connect to the AI service at {settings.OLLAMA_BASE_URL}. "
                "Please ensure Ollama is running."
            ),
            session_id=session_id,
            operations_performed=[],
        )
    except Exception as exc:
        logger.exception("Database chat error")
        return DatabaseChatResponse(
            response=f"An error occurred: {str(exc)}. Please try again.",
            session_id=session_id,
            operations_performed=[],
        )


async def _execute_tool_call(
    function_name: str,
    arguments: Dict[str, Any],
    db_agent: DatabaseAgent,
) -> DatabaseOperationResult:
    """Execute a database tool call and return the result."""
    try:
        if function_name == "query_database":
            request = DatabaseOperationRequest(
                action=DatabaseAction.QUERY,
                entity_type=EntityType(arguments["entity_type"]),
                filters=arguments.get("filters"),
                entity_id=arguments.get("entity_id"),
            )
        elif function_name == "list_database":
            request = DatabaseOperationRequest(
                action=DatabaseAction.LIST,
                entity_type=EntityType(arguments["entity_type"]),
                filters=arguments.get("filters"),
                limit=arguments.get("limit", 50),
            )
        elif function_name == "create_database":
            request = DatabaseOperationRequest(
                action=DatabaseAction.CREATE,
                entity_type=EntityType(arguments["entity_type"]),
                data=arguments.get("data", {}),
            )
        elif function_name == "update_database":
            request = DatabaseOperationRequest(
                action=DatabaseAction.UPDATE,
                entity_type=EntityType(arguments["entity_type"]),
                entity_id=arguments["entity_id"],
                data=arguments.get("data", {}),
            )
        elif function_name == "delete_database":
            request = DatabaseOperationRequest(
                action=DatabaseAction.DELETE,
                entity_type=EntityType(arguments["entity_type"]),
                entity_id=arguments["entity_id"],
            )
        elif function_name == "get_schema":
            request = DatabaseOperationRequest(
                action=DatabaseAction.GET_SCHEMA,
                entity_type=EntityType(arguments["entity_type"]),
            )
        else:
            return DatabaseOperationResult(
                success=False,
                action=DatabaseAction.QUERY,
                entity_type="unknown",
                message=f"Unknown function: {function_name}",
                error="UNKNOWN_FUNCTION",
            )

        return await db_agent.execute_operation(request)

    except Exception as exc:
        logger.exception("Tool call execution failed")
        return DatabaseOperationResult(
            success=False,
            action=DatabaseAction.QUERY,
            entity_type=arguments.get("entity_type", "unknown"),
            message=f"Execution failed: {str(exc)}",
            error=str(exc),
        )


async def _extract_fields_from_message(
    message: str,
    fields: List[str],
    entity_type: EntityType,
) -> Optional[Dict[str, Any]]:
    """Use LLM to extract field values from natural language."""
    try:
        prompt = f"""Extract the following field values from this user message for creating a {entity_type.value}:

Fields needed: {', '.join(fields)}

User message: "{message}"

Return ONLY a JSON object with the extracted values. Use null for missing fields.
Example: {{"company_name": "Acme Corp", "pic_email": "john@acme.com"}}"""

        async with httpx.AsyncClient(timeout=30.0) as http:
            response = await http.post(
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": settings.OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                },
            )
            response.raise_for_status()
            result = response.json()
            extracted = json.loads(result.get("response", "{}"))
            return extracted if extracted else None
    except Exception:
        return None


# =============================================================
# Direct Database Operation Endpoints (for programmatic use)
# =============================================================


@router.post(
    "/db-operation",
    response_model=DatabaseOperationResult,
    summary="Direct database operation",
    description="Execute a direct database operation without AI processing.",
)
async def direct_db_operation(
    request: DatabaseOperationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> DatabaseOperationResult:
    """
    Execute a direct database operation.

    This endpoint bypasses AI processing and directly executes
    the requested database operation.
    """
    # Check permissions based on role
    if current_user.get("role") not in {"superadmin", "management", "staff"}:
        if request.action in {DatabaseAction.CREATE, DatabaseAction.UPDATE, DatabaseAction.DELETE}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for write operations",
            )

    db_agent = DatabaseAgent(db, current_user)
    return await db_agent.execute_operation(request)


@router.get(
    "/db-schema/{entity_type}",
    summary="Get entity schema",
    description="Get schema information for an entity type including required fields.",
)
async def get_entity_schema(
    entity_type: EntityType,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get schema information for an entity type."""
    db_agent = DatabaseAgent(db, current_user)
    schema_info = await db_agent.get_entity_schema(entity_type)
    return schema_info.model_dump()


@router.get(
    "/db-pending-operations",
    summary="List pending operations",
    description="List pending database operations for a session.",
)
async def list_pending_operations(
    session_id: str = Query(..., description="Session ID"),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """List pending database operations for a session."""
    operations = _pending_db_operations.get(session_id, {})
    return {
        "session_id": session_id,
        "pending_operations": operations,
        "count": len(operations),
    }


@router.delete(
    "/db-pending-operations/{session_id}/{operation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Cancel pending operation",
)
async def cancel_pending_operation(
    session_id: str,
    operation_id: str,
    current_user: Any = Depends(get_current_user),
) -> None:
    """Cancel a pending database operation."""
    if session_id in _pending_db_operations:
        if operation_id in _pending_db_operations[session_id]:
            del _pending_db_operations[session_id][operation_id]


# =============================================================
# Bulk Import Endpoints
# Import data from CSV/Excel files
# =============================================================


# Import bulk import agent components
from agents.bulk_import_agent import (
    BulkImportAgent,
    BulkImportRequest,
    BulkImportResponse,
    ImportPreviewRequest,
    ImportPreviewResponse,
    ImportTemplateResponse,
    ImportStatus,
)


@router.post(
    "/bulk-import",
    response_model=BulkImportResponse,
    summary="Bulk import from file",
    description="Import multiple records from CSV/Excel file. Supports clients, jobs, vehicles, users, and more.",
)
async def bulk_import(
    request: BulkImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> BulkImportResponse:
    """
    Bulk import entities from a file.

    **Supported formats:** CSV, Excel (.xlsx, .xls)

    **Supported entities:**
    - client, job, vehicle, user, container, compaction_machine
    - scheduled_waste_batch, carbon_record, recyclable_record
    - bsf_batch, destruction_job

    **Features:**
    - Automatic column mapping
    - Data validation with detailed error reporting
    - Partial import support (skip_errors=True)
    - Dry run mode to preview without creating

    **Example workflow:**
    1. Upload file and get preview (POST /bulk-import-preview)
    2. Review suggested column mappings
    3. Execute import with dry_run=true to validate
    4. Execute import with dry_run=false to create records
    """
    # Check permissions
    if current_user.get("role") not in {"superadmin", "management", "staff", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions for bulk import",
        )

    try:
        # Decode file content
        import base64
        file_content = base64.b64decode(request.file_content_base64)

        # Initialize import agent
        import_agent = BulkImportAgent(db, current_user)

        # Parse file
        rows = await import_agent.parse_file(
            file_content, request.filename, request.entity_type
        )

        # Convert explicit column mappings if provided
        column_mappings = None
        if request.column_mappings:
            from agents.bulk_import_agent import ColumnMapping
            column_mappings = {}
            for file_col, entity_field in request.column_mappings.items():
                column_mappings[file_col] = ColumnMapping(
                    file_column=file_col,
                    entity_field=entity_field,
                )

        # Execute import
        result = await import_agent.validate_and_import(
            rows=rows,
            entity_type=request.entity_type,
            column_mappings=column_mappings,
            skip_errors=request.skip_errors,
            dry_run=request.dry_run,
        )

        # Convert errors to dict
        error_dicts = []
        for error in result.errors[:10]:  # Limit to first 10 errors
            error_dicts.append({
                "row_number": error.row_number,
                "error_message": error.error_message,
                "field_errors": error.field_errors,
            })

        return BulkImportResponse(
            import_id=result.import_id,
            entity_type=result.entity_type.value,
            status=result.status.value,
            total_rows=result.total_rows,
            successful_rows=result.successful_rows,
            failed_rows=result.failed_rows,
            created_count=len(result.created_ids),
            errors=error_dicts,
            warnings=result.warnings,
            summary=result.summary,
            processing_time_seconds=result.processing_time_seconds,
        )

    except Exception as exc:
        logger.exception("Bulk import failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import failed: {str(exc)}",
        )


@router.post(
    "/bulk-import-preview",
    response_model=ImportPreviewResponse,
    summary="Preview bulk import",
    description="Preview what would be imported without creating records. Shows column mappings and sample data.",
)
async def bulk_import_preview(
    request: ImportPreviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> ImportPreviewResponse:
    """
    Preview a bulk import operation.

    Returns:
    - Detected columns from the file
    - Suggested column mappings to entity fields
    - Sample of transformed data (first 3 rows)
    - Missing required fields if any
    """
    try:
        import base64
        file_content = base64.b64decode(request.file_content_base64)

        import_agent = BulkImportAgent(db, current_user)

        # Parse file
        rows = await import_agent.parse_file(
            file_content, request.filename, request.entity_type
        )

        if not rows:
            return ImportPreviewResponse(
                entity_type=request.entity_type.value,
                total_rows=0,
                detected_columns=[],
                suggested_mappings={},
                sample_transformed=[],
                missing_required_fields=[],
                can_import=False,
            )

        # Get column mappings
        columns = list(rows[0].keys())
        suggested_mappings = import_agent.suggest_column_mappings(
            columns, request.entity_type
        )

        # Get missing required fields
        from agents.bulk_import_agent import ENTITY_METADATA
        meta = ENTITY_METADATA.get(request.entity_type, {})
        required_fields = set(meta.get("required_fields", []))
        mapped_fields = {v for v in suggested_mappings.values() if v != "(not matched)"}
        missing_required = list(required_fields - mapped_fields)

        # Transform sample rows
        column_mappings = import_agent.auto_map_columns(columns, request.entity_type)
        sample_transformed = []
        for row in rows[:3]:
            transformed = import_agent._transform_row(row, column_mappings)
            sample_transformed.append(transformed)

        return ImportPreviewResponse(
            entity_type=request.entity_type.value,
            total_rows=len(rows),
            detected_columns=columns,
            suggested_mappings=suggested_mappings,
            sample_transformed=sample_transformed,
            missing_required_fields=missing_required,
            can_import=len(missing_required) == 0,
        )

    except Exception as exc:
        logger.exception("Import preview failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Preview failed: {str(exc)}",
        )


@router.get(
    "/bulk-import-template/{entity_type}",
    response_model=ImportTemplateResponse,
    summary="Get import template",
    description="Get CSV template with column headers for a specific entity type.",
)
async def bulk_import_template(
    entity_type: EntityType,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> ImportTemplateResponse:
    """
    Get a CSV template for bulk importing a specific entity type.

    Returns column headers with examples. Required columns marked with *.
    """
    try:
        import_agent = BulkImportAgent(db, current_user)
        template_columns = import_agent.get_import_template(entity_type)

        # Build example CSV
        from agents.bulk_import_agent import ENTITY_METADATA
        meta = ENTITY_METADATA.get(entity_type, {})
        required = meta.get("required_fields", [])
        create_schema = meta.get("create_schema")

        example_csv = ",".join(template_columns) + "\n"
        if create_schema:
            # Add sample data row
            example_data = {}
            schema = create_schema.model_json_schema()
            for field_name, field_info in schema.get("properties", {}).items():
                if field_name == "waste_streams":
                    continue
                field_type = field_info.get("type", "string")
                if field_type == "string":
                    example_data[field_name] = f"example_{field_name}"
                elif field_type == "number":
                    example_data[field_name] = "100.50"
                elif field_type == "integer":
                    example_data[field_name] = "42"
                elif field_type == "boolean":
                    example_data[field_name] = "true"

            row_values = []
            for col in template_columns:
                # Remove * marker to get field name
                field = col.replace("*", "").strip().lower().replace(" ", "_")
                # Find actual field name
                for actual_field in schema.get("properties", {}).keys():
                    if actual_field.lower().replace("_", " ") == col.replace("*", "").strip().lower():
                        field = actual_field
                        break
                val = example_data.get(field, "")
                row_values.append(val)

            example_csv += ",".join(row_values)

        return ImportTemplateResponse(
            entity_type=entity_type.value,
            required_columns=[c.replace("*", "") for c in template_columns if "*" in c],
            optional_columns=[c for c in template_columns if "*" not in c],
            example_csv=example_csv,
        )

    except Exception as exc:
        logger.exception("Template generation failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Template generation failed: {str(exc)}",
        )


# =============================================================
# Bulk Import Integration with Database Agent Chat
# Add bulk import functions to AI agent
# =============================================================

# Extend database agent functions with bulk import
BULK_IMPORT_FUNCTIONS = [
    {
        "name": "preview_bulk_import",
        "description": "Preview a bulk import from a file before executing. Use this to check column mappings and validate data.",
        "parameters": {
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "enum": [e.value for e in EntityType],
                    "description": "The type of entity to import"
                },
                "filename": {
                    "type": "string",
                    "description": "Name of the file being uploaded"
                }
            },
            "required": ["entity_type", "filename"]
        }
    },
    {
        "name": "execute_bulk_import",
        "description": "Execute a bulk import from a CSV or Excel file. Only use this after confirming column mappings are correct.",
        "parameters": {
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "enum": [e.value for e in EntityType],
                    "description": "The type of entity to import"
                },
                "filename": {
                    "type": "string",
                    "description": "Name of the file"
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "If true, validate only without creating records",
                    "default": True
                },
                "skip_errors": {
                    "type": "boolean",
                    "description": "If true, continue importing on row errors",
                    "default": True
                }
            },
            "required": ["entity_type", "filename"]
        }
    },
    {
        "name": "get_import_template",
        "description": "Get a CSV template for importing a specific entity type. Use this when user asks for a template or example file.",
        "parameters": {
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "enum": [e.value for e in EntityType],
                    "description": "The entity type to get template for"
                }
            },
            "required": ["entity_type"]
        }
    }
]


# Combined functions for database agent with bulk import
DB_AGENT_WITH_IMPORT_FUNCTIONS = DB_AGENT_FUNCTIONS + BULK_IMPORT_FUNCTIONS


# =============================================================
# Smart Scheduling Endpoints
# AI-powered job scheduling and route optimization
# =============================================================

from agents.smart_scheduling_agent import (
    SmartSchedulingAgent,
    ScheduleRequest,
    ScheduleResponse,
    RouteRequest,
    RouteResponse,
    ConflictResponse,
    BatchScheduleRequest,
    BatchScheduleResponse,
    ConflictType,
)


@router.post(
    "/schedule/suggest",
    response_model=ScheduleResponse,
    summary="Get job scheduling suggestions",
    description="Get AI-suggested job assignments based on capacity, geography, and priority.",
)
async def suggest_schedule(
    request: ScheduleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> ScheduleResponse:
    """
    Get AI-powered job scheduling suggestions.
    
    The AI analyzes unassigned jobs and available vehicles to suggest optimal assignments
    considering:
    - Vehicle capacity matching
    - Geographic proximity
    - Time windows
    - Job priority
    
    **Strategies:**
    - `balanced`: Distribute jobs evenly across vehicles
    - `speed`: Minimize travel time (assign to nearest vehicles)
    - `efficiency`: Maximize vehicle utilization
    
    **Example:**
    ```json
    {
        "target_date": "2026-04-30",
        "strategy": "balanced",
        "auto_assign": false
    }
    ```
    """
    try:
        agent = SmartSchedulingAgent(db, current_user)
        
        # Get job IDs if not provided
        job_ids = None
        if request.job_ids:
            job_ids = [UUID(jid) for jid in request.job_ids]
        
        # Get suggestions
        if job_ids:
            # Batch schedule specific jobs
            suggestion = await agent.batch_schedule_jobs(
                job_ids=job_ids,
                target_date=request.target_date,
                strategy=request.strategy
            )
        else:
            # Auto-schedule all unassigned jobs
            suggestion = await agent.suggest_job_assignments(
                target_date=request.target_date
            )
        
        # Check for conflicts
        conflicts = await agent.detect_conflicts(
            date_from=request.target_date,
            date_to=request.target_date
        )
        
        # Auto-assign if requested
        if request.auto_assign and suggestion.assignments:
            await agent.apply_assignments(suggestion.assignments, commit=True)
        
        # Convert assignments to dict
        assignment_dicts = []
        for a in suggestion.assignments:
            assignment_dicts.append({
                "job_id": str(a.job_id),
                "vehicle_id": str(a.vehicle_id),
                "driver_id": str(a.driver_id) if a.driver_id else None,
                "scheduled_date": a.scheduled_date.isoformat(),
                "estimated_start_time": a.estimated_start_time.isoformat() if a.estimated_start_time else None,
                "estimated_end_time": a.estimated_end_time.isoformat() if a.estimated_end_time else None,
                "confidence_score": a.confidence_score,
                "notes": a.notes,
            })
        
        # Convert conflicts to dict
        conflict_dicts = []
        for c in conflicts:
            conflict_dicts.append({
                "type": c.conflict_type.value,
                "severity": c.severity,
                "description": c.description,
                "affected_jobs": [str(j) for j in c.affected_jobs],
                "affected_vehicles": [str(v) for v in c.affected_vehicles],
                "suggested_resolution": c.suggested_resolution,
            })
        
        return ScheduleResponse(
            suggestion_type=suggestion.suggestion_type,
            priority=suggestion.priority,
            description=suggestion.description,
            assignments=assignment_dicts,
            affected_jobs=[str(j) for j in suggestion.affected_jobs],
            reasoning=suggestion.reasoning,
            estimated_efficiency_gain=suggestion.estimated_efficiency_gain,
            conflicts_detected=conflict_dicts,
        )
        
    except Exception as exc:
        logger.exception("Schedule suggestion failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scheduling failed: {str(exc)}",
        )


@router.post(
    "/schedule/route",
    response_model=RouteResponse,
    summary="Optimize route for vehicle",
    description="Get optimized route for a vehicle's assigned jobs using nearest-neighbor algorithm.",
)
async def optimize_route(
    request: RouteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> RouteResponse:
    """
    Optimize the route for a vehicle's assigned jobs.
    
    Uses nearest-neighbor algorithm to minimize travel distance.
    Considers:
    - Job locations (lat/lng)
    - Service duration
    - Travel time between stops
    
    **Example:**
    ```json
    {
        "vehicle_id": "abc-123",
        "target_date": "2026-04-30"
    }
    ```
    """
    try:
        agent = SmartSchedulingAgent(db, current_user)
        
        job_ids = None
        if request.job_ids:
            job_ids = [UUID(jid) for jid in request.job_ids]
        
        route = await agent.optimize_route(
            vehicle_id=UUID(request.vehicle_id),
            target_date=request.target_date,
            job_ids=job_ids
        )
        
        if not route:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No route could be generated for this vehicle and date"
            )
        
        # Convert stops to dict
        stop_dicts = []
        for s in route.stops:
            stop_dicts.append({
                "stop_order": s.stop_order,
                "job_id": str(s.job_id),
                "client_name": s.client_name,
                "address": s.address,
                "lat": s.lat,
                "lng": s.lng,
                "estimated_arrival": s.estimated_arrival.isoformat(),
                "estimated_duration": s.estimated_duration,
                "waste_type": s.waste_type,
            })
        
        return RouteResponse(
            vehicle_id=str(route.vehicle_id),
            vehicle_name=route.vehicle_name,
            driver_name=route.driver_name,
            date=route.date,
            stops=stop_dicts,
            total_distance_km=route.total_distance_km,
            total_duration_minutes=route.total_duration_minutes,
            start_time=route.start_time.isoformat(),
            end_time=route.end_time.isoformat(),
            efficiency_score=route.efficiency_score,
        )
        
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Route optimization failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Route optimization failed: {str(exc)}",
        )


@router.get(
    "/schedule/conflicts",
    response_model=ConflictResponse,
    summary="Detect scheduling conflicts",
    description="Detect double-bookings, capacity overruns, and other scheduling conflicts.",
)
async def detect_conflicts_endpoint(
    date_from: date = Query(default_factory=date.today),
    date_to: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> ConflictResponse:
    """
    Detect scheduling conflicts for a date range.
    
    Detects:
    - Double-booked vehicles
    - Double-booked drivers  
    - Capacity exceeded
    - Overlapping time windows
    - Missing permits
    
    **Query Parameters:**
    - `date_from`: Start date (default: today)
    - `date_to`: End date (default: same as from)
    """
    try:
        agent = SmartSchedulingAgent(db, current_user)
        
        if not date_to:
            date_to = date_from
        
        conflicts = await agent.detect_conflicts(
            date_from=date_from,
            date_to=date_to
        )
        
        # Convert to dict
        conflict_dicts = []
        critical = 0
        warning = 0
        
        for c in conflicts:
            if c.severity == "critical":
                critical += 1
            elif c.severity == "warning":
                warning += 1
            
            conflict_dicts.append({
                "type": c.conflict_type.value,
                "severity": c.severity,
                "description": c.description,
                "affected_jobs": [str(j) for j in c.affected_jobs],
                "affected_vehicles": [str(v) for v in c.affected_vehicles],
                "affected_drivers": [str(d) for d in c.affected_drivers],
                "suggested_resolution": c.suggested_resolution,
            })
        
        return ConflictResponse(
            conflicts=conflict_dicts,
            total_conflicts=len(conflicts),
            critical_count=critical,
            warning_count=warning,
        )
        
    except Exception as exc:
        logger.exception("Conflict detection failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Conflict detection failed: {str(exc)}",
        )


@router.post(
    "/schedule/batch",
    response_model=BatchScheduleResponse,
    summary="Batch schedule jobs",
    description="Schedule multiple jobs at once using specified strategy.",
)
async def batch_schedule(
    request: BatchScheduleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> BatchScheduleResponse:
    """
    Batch schedule multiple jobs using different strategies.
    
    **Strategies:**
    - `balanced`: Distribute evenly across vehicles
    - `speed`: Assign to nearest vehicles (minimize travel)
    - `efficiency`: Maximize vehicle utilization
    
    **Example:**
    ```json
    {
        "job_ids": ["job-1", "job-2", "job-3"],
        "target_date": "2026-04-30",
        "strategy": "speed",
        "apply_immediately": true
    }
    ```
    """
    try:
        agent = SmartSchedulingAgent(db, current_user)
        
        job_ids = [UUID(jid) for jid in request.job_ids]
        
        suggestion = await agent.batch_schedule_jobs(
            job_ids=job_ids,
            target_date=request.target_date,
            strategy=request.strategy
        )
        
        # Apply if requested
        apply_result = {"applied": 0, "failed": 0}
        if request.apply_immediately and suggestion.assignments:
            apply_result = await agent.apply_assignments(
                suggestion.assignments,
                commit=True
            )
        
        # Build response
        assigned_job_ids = [str(a.job_id) for a in suggestion.assignments]
        unassigned = [jid for jid in request.job_ids if jid not in assigned_job_ids]
        
        assignment_dicts = []
        for a in suggestion.assignments:
            assignment_dicts.append({
                "job_id": str(a.job_id),
                "vehicle_id": str(a.vehicle_id),
                "confidence": a.confidence_score,
                "notes": a.notes,
            })
        
        return BatchScheduleResponse(
            scheduled=len(suggestion.assignments),
            failed=apply_result.get("failed", 0),
            strategy_used=request.strategy,
            assignments=assignment_dicts,
            unassigned_jobs=unassigned,
        )
        
    except Exception as exc:
        logger.exception("Batch scheduling failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch scheduling failed: {str(exc)}",
        )


@router.post(
    "/schedule/apply",
    response_model=Dict[str, Any],
    summary="Apply schedule suggestions",
    description="Apply AI-suggested assignments to the database.",
)
async def apply_schedule(
    assignment_data: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Apply schedule suggestions to the database.
    
    **Request Body:**
    ```json
    {
        "assignments": [
            {
                "job_id": "uuid",
                "vehicle_id": "uuid",
                "driver_id": "uuid",
                "scheduled_date": "2026-04-30"
            }
        ]
    }
    ```
    """
    try:
        agent = SmartSchedulingAgent(db, current_user)
        
        # Convert input to Assignment objects
        from agents.smart_scheduling_agent import Assignment
        from datetime import datetime
        
        assignments = []
        for a in assignment_data.get("assignments", []):
            assignment = Assignment(
                job_id=UUID(a["job_id"]),
                vehicle_id=UUID(a["vehicle_id"]),
                driver_id=UUID(a["driver_id"]) if a.get("driver_id") else None,
                scheduled_date=datetime.strptime(a["scheduled_date"], "%Y-%m-%d").date() if a.get("scheduled_date") else date.today(),
            )
            assignments.append(assignment)
        
        result = await agent.apply_assignments(assignments, commit=True)
        
        return {
            "success": True,
            "applied": result["applied"],
            "failed": result["failed"],
            "details": result["details"]
        }
        
    except Exception as exc:
        logger.exception("Apply schedule failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to apply schedule: {str(exc)}",
        )


# =============================================================
# Smart Scheduling Integration with AI Chat
# Add scheduling functions to database agent
# =============================================================

SCHEDULING_FUNCTIONS = [
    {
        "name": "suggest_job_assignments",
        "description": "Get AI suggestions for assigning unassigned jobs to vehicles. Considers capacity, location, and priority.",
        "parameters": {
            "type": "object",
            "properties": {
                "target_date": {
                    "type": "string",
                    "description": "Date to schedule for (YYYY-MM-DD)"
                },
                "strategy": {
                    "type": "string",
                    "enum": ["balanced", "speed", "efficiency"],
                    "description": "Scheduling strategy"
                }
            },
            "required": ["target_date"]
        }
    },
    {
        "name": "optimize_vehicle_route",
        "description": "Optimize the route for a vehicle's assigned jobs to minimize travel distance.",
        "parameters": {
            "type": "object",
            "properties": {
                "vehicle_id": {
                    "type": "string",
                    "description": "ID of the vehicle"
                },
                "date": {
                    "type": "string",
                    "description": "Date for the route (YYYY-MM-DD)"
                }
            },
            "required": ["vehicle_id", "date"]
        }
    },
    {
        "name": "detect_scheduling_conflicts",
        "description": "Detect double-bookings, capacity conflicts, and other scheduling issues.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Date to check (YYYY-MM-DD)"
                }
            },
            "required": ["date"]
        }
    },
    {
        "name": "batch_schedule_jobs",
        "description": "Schedule multiple jobs at once using a specific strategy.",
        "parameters": {
            "type": "object",
            "properties": {
                "job_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of job IDs to schedule"
                },
                "target_date": {
                    "type": "string",
                    "description": "Date to schedule for (YYYY-MM-DD)"
                },
                "strategy": {
                    "type": "string",
                    "enum": ["balanced", "speed", "efficiency"],
                    "default": "balanced"
                }
            },
            "required": ["job_ids", "target_date"]
        }
    }
]


# Combined functions for full AI agent capability
AI_AGENT_FUNCTIONS = DB_AGENT_WITH_IMPORT_FUNCTIONS + SCHEDULING_FUNCTIONS


# =============================================================
# Compliance Monitoring Endpoints
# AI-powered compliance tracking and permit expiration alerts
# =============================================================

from agents.compliance_monitoring_agent import (
    ComplianceMonitoringAgent,
    ComplianceDashboardRequest,
    ComplianceDashboardResponse,
    ComplianceCheckRequest,
    ComplianceCheckResponse,
    ComplianceReportRequest,
    ComplianceReportResponse,
    ComplianceAlertResponse,
    ComplianceType,
    ComplianceStatus,
    AlertPriority,
)


@router.get(
    "/compliance/dashboard",
    response_model=ComplianceDashboardResponse,
    summary="Get compliance dashboard",
    description="Get comprehensive compliance overview with counts, alerts, and upcoming deadlines.",
)
async def compliance_dashboard(
    client_id: Optional[str] = Query(None, description="Filter by client ID"),
    vehicle_id: Optional[str] = Query(None, description="Filter by vehicle ID"),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> ComplianceDashboardResponse:
    """
    Get compliance dashboard with:
    - Total compliance items monitored
    - Status breakdown (compliant/warning/critical/expired)
    - Upcoming deadlines (next 30 days)
    - Active alerts requiring attention
    - Human-readable summary
    
    **Query Parameters:**
    - `client_id`: Optional filter for specific client
    - `vehicle_id`: Optional filter for specific vehicle
    """
    try:
        agent = ComplianceMonitoringAgent(db, current_user)
        
        # Build filters
        compliance_types = None
        
        dashboard = await agent.get_compliance_dashboard(
            compliance_types=compliance_types
        )
        
        # Convert dataclasses to dicts
        upcoming = []
        for item in dashboard.upcoming_deadlines:
            upcoming.append({
                "item_id": str(item.item_id),
                "type": item.compliance_type.value,
                "entity_name": item.entity_name,
                "description": item.description,
                "deadline": item.deadline.isoformat() if item.deadline else None,
                "days_remaining": item.days_remaining,
                "status": item.status.value,
                "required_action": item.required_action,
            })
        
        alerts = []
        for alert in dashboard.recent_alerts:
            alerts.append({
                "alert_id": alert.alert_id,
                "type": alert.compliance_type.value,
                "priority": alert.priority.value,
                "title": alert.title,
                "description": alert.description,
                "affected_entities": alert.affected_entities,
                "suggested_action": alert.suggested_action,
                "created_at": alert.created_at.isoformat(),
            })
        
        return ComplianceDashboardResponse(
            total_items=dashboard.total_items,
            compliant_count=dashboard.compliant_count,
            warning_count=dashboard.warning_count,
            critical_count=dashboard.critical_count,
            expired_count=dashboard.expired_count,
            items_by_type=dashboard.items_by_type,
            upcoming_deadlines=upcoming,
            recent_alerts=alerts,
            summary_text=dashboard.summary_text,
        )
        
    except Exception as exc:
        logger.exception("Compliance dashboard failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load compliance dashboard: {str(exc)}",
        )


@router.post(
    "/compliance/check",
    response_model=ComplianceCheckResponse,
    summary="Run compliance check",
    description="Run targeted compliance check for specific types or entities.",
)
async def compliance_check(
    request: ComplianceCheckRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> ComplianceCheckResponse:
    """
    Run compliance check and get detailed results.
    
    **Types:**
    - `scheduled_waste_deadline` - DOE storage deadline compliance
    - `vehicle_road_tax` - Vehicle road tax validity
    - `vehicle_insurance` - Vehicle insurance expiry
    - `vehicle_puspakom` - PUSPAKOM inspection dates
    - `downstream_license` - Downstream buyer licenses
    - `destruction_certificate` - Pending destruction certificates
    - `consignment_note` - Consignment note tracking
    
    **Example:**
    ```json
    {
        "compliance_type": "scheduled_waste_deadline",
        "client_id": "uuid",
        "days_lookahead": 30
    }
    ```
    """
    try:
        agent = ComplianceMonitoringAgent(db, current_user)
        
        items = []
        
        # Run specific check based on type
        if request.compliance_type == "scheduled_waste_deadline":
            cid = UUID(request.client_id) if request.client_id else None
            items = await agent.check_scheduled_waste_compliance(client_id=cid)
        elif request.compliance_type in ["vehicle_road_tax", "vehicle_insurance", "vehicle_puspakom"]:
            vid = UUID(request.vehicle_id) if request.vehicle_id else None
            items = await agent.check_vehicle_compliance(vehicle_id=vid)
        elif request.compliance_type == "downstream_license":
            items = await agent.check_downstream_buyer_compliance()
        elif request.compliance_type == "destruction_certificate":
            items = await agent.check_destruction_certificate_compliance()
        elif request.compliance_type == "consignment_note":
            items = await agent.check_consignment_note_compliance()
        else:
            # Run all checks
            items.extend(await agent.check_scheduled_waste_compliance())
            items.extend(await agent.check_vehicle_compliance())
            items.extend(await agent.check_downstream_buyer_compliance())
            items.extend(await agent.check_destruction_certificate_compliance())
            items.extend(await agent.check_consignment_note_compliance())
        
        # Filter by lookahead
        cutoff_date = date.today() + timedelta(days=request.days_lookahead)
        filtered_items = [
            item for item in items
            if item.deadline is None or item.deadline <= cutoff_date
        ]
        
        # Build response
        critical = len([i for i in filtered_items if i.status == ComplianceStatus.CRITICAL])
        warning = len([i for i in filtered_items if i.status == ComplianceStatus.WARNING])
        
        item_dicts = []
        for item in filtered_items:
            item_dicts.append({
                "item_id": str(item.item_id),
                "type": item.compliance_type.value,
                "entity_name": item.entity_name,
                "description": item.description,
                "deadline": item.deadline.isoformat() if item.deadline else None,
                "days_remaining": item.days_remaining,
                "status": item.status.value,
                "regulation": item.regulation_reference,
                "action_required": item.required_action,
                "metadata": item.metadata,
            })
        
        # Generate summary
        summary = f"Found {len(filtered_items)} items: {critical} critical, {warning} warnings"
        
        return ComplianceCheckResponse(
            items_checked=len(items),
            issues_found=critical + warning,
            critical_count=critical,
            warning_count=warning,
            items=item_dicts,
            summary=summary,
        )
        
    except Exception as exc:
        logger.exception("Compliance check failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Compliance check failed: {str(exc)}",
        )


@router.post(
    "/compliance/report",
    response_model=ComplianceReportResponse,
    summary="Generate compliance report",
    description="Generate a compliance report for a specific period.",
)
async def compliance_report(
    request: ComplianceReportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> ComplianceReportResponse:
    """
    Generate compliance report for regulatory submission.
    
    **Example:**
    ```json
    {
        "start_date": "2026-01-01",
        "end_date": "2026-03-31",
        "regulatory_body": "DOE Malaysia"
    }
    ```
    """
    try:
        agent = ComplianceMonitoringAgent(db, current_user)
        
        report = await agent.generate_compliance_report(
            start_date=request.start_date,
            end_date=request.end_date,
            regulatory_body=request.regulatory_body
        )
        
        return ComplianceReportResponse(
            report_period=report.report_period,
            generated_at=report.generated_at,
            items_checked=report.items_checked,
            violations_found=report.violations_found,
            violations_by_type=report.violations_by_type,
            recommendations=report.recommendations,
            regulatory_body=report.regulatory_body,
        )
        
    except Exception as exc:
        logger.exception("Compliance report generation failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Report generation failed: {str(exc)}",
        )


@router.get(
    "/compliance/alerts",
    response_model=ComplianceAlertResponse,
    summary="Get compliance alerts",
    description="Get current compliance alerts requiring attention.",
)
async def compliance_alerts(
    priority: Optional[str] = Query(None, description="Filter by priority: urgent, high, medium, low"),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> ComplianceAlertResponse:
    """
    Get compliance alerts.
    
    **Query Parameters:**
    - `priority`: Filter by priority level
    """
    try:
        agent = ComplianceMonitoringAgent(db, current_user)
        
        # Get dashboard which includes alerts
        dashboard = await agent.get_compliance_dashboard()
        
        # Filter by priority if specified
        alerts = dashboard.recent_alerts
        if priority:
            alerts = [a for a in alerts if a.priority.value == priority.lower()]
        
        # Convert to dicts
        alert_dicts = []
        for alert in alerts:
            alert_dicts.append({
                "alert_id": alert.alert_id,
                "type": alert.compliance_type.value,
                "priority": alert.priority.value,
                "title": alert.title,
                "description": alert.description,
                "affected_items": [str(i) for i in alert.affected_items],
                "affected_entities": alert.affected_entities,
                "suggested_action": alert.suggested_action,
                "auto_resolve": alert.auto_resolve_possible,
                "created_at": alert.created_at.isoformat(),
            })
        
        urgent = len([a for a in alerts if a.priority == AlertPriority.URGENT])
        high = len([a for a in alerts if a.priority == AlertPriority.HIGH])
        
        return ComplianceAlertResponse(
            alerts=alert_dicts,
            total_alerts=len(alerts),
            urgent_count=urgent,
            high_count=high,
        )
        
    except Exception as exc:
        logger.exception("Compliance alerts failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load alerts: {str(exc)}",
        )


@router.get(
    "/compliance/entity/{entity_type}/{entity_id}",
    response_model=Dict[str, Any],
    summary="Get entity compliance status",
    description="Get compliance summary for a specific entity (client, vehicle).",
)
async def entity_compliance(
    entity_type: str = Path(..., description="Entity type: client, vehicle"),
    entity_id: str = Path(..., description="Entity UUID"),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get compliance status for a specific entity.
    
    **Path Parameters:**
    - `entity_type`: `client` or `vehicle`
    - `entity_id`: UUID of the entity
    """
    try:
        agent = ComplianceMonitoringAgent(db, current_user)
        
        if entity_type not in ["client", "vehicle"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported entity type: {entity_type}. Use 'client' or 'vehicle'"
            )
        
        summary = await agent.get_compliance_summary_for_entity(
            entity_type=entity_type,
            entity_id=UUID(entity_id)
        )
        
        return summary
        
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Entity compliance check failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get compliance status: {str(exc)}",
        )


# =============================================================
# Compliance Monitoring Integration with AI Chat
# Add compliance functions to AI agent
# =============================================================

COMPLIANCE_FUNCTIONS = [
    {
        "name": "check_compliance_dashboard",
        "description": "Get the compliance dashboard overview showing all monitored items, their status, and any alerts.",
        "parameters": {
            "type": "object",
            "properties": {
                "compliance_type": {
                    "type": "string",
                    "enum": ["scheduled_waste_deadline", "vehicle_road_tax", "vehicle_insurance", "vehicle_puspakom", "downstream_license", "destruction_certificate", "consignment_note"],
                    "description": "Optional: Filter by specific compliance type"
                },
                "client_id": {
                    "type": "string",
                    "description": "Optional: Filter by client ID"
                }
            },
            "required": []
        }
    },
    {
        "name": "check_scheduled_waste_compliance",
        "description": "Check scheduled waste batches against DOE 90-day storage deadline. Returns batches approaching or past deadline.",
        "parameters": {
            "type": "object",
            "properties": {
                "client_id": {
                    "type": "string",
                    "description": "Optional client ID to filter"
                }
            },
            "required": []
        }
    },
    {
        "name": "check_vehicle_compliance",
        "description": "Check vehicle permits: road tax, insurance, PUSPAKOM inspection dates.",
        "parameters": {
            "type": "object",
            "properties": {
                "vehicle_id": {
                    "type": "string",
                    "description": "Optional vehicle ID to check specific vehicle"
                }
            },
            "required": []
        }
    },
    {
        "name": "generate_compliance_report",
        "description": "Generate a compliance report for a specific date range, suitable for regulatory submission.",
        "parameters": {
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "Report start date (YYYY-MM-DD)"
                },
                "end_date": {
                    "type": "string",
                    "description": "Report end date (YYYY-MM-DD)"
                },
                "regulatory_body": {
                    "type": "string",
                    "enum": ["DOE Malaysia", "JPJ", "Custom"],
                    "default": "DOE Malaysia"
                }
            },
            "required": ["start_date", "end_date"]
        }
    },
    {
        "name": "get_compliance_alerts",
        "description": "Get current compliance alerts requiring attention. Shows urgent and high priority issues.",
        "parameters": {
            "type": "object",
            "properties": {
                "priority": {
                    "type": "string",
                    "enum": ["urgent", "high", "medium", "low"],
                    "description": "Filter by priority level"
                }
            },
            "required": []
        }
    }
]


# Final combined functions for complete AI agent capability
AI_AGENT_ALL_FUNCTIONS = AI_AGENT_FUNCTIONS + COMPLIANCE_FUNCTIONS


# =============================================================
# Invoice Intelligence Endpoints
# AI-powered aging reports, collection strategies, and risk scoring
# =============================================================

from agents.invoice_intelligence_agent import (
    InvoiceIntelligenceAgent,
    AgingReportRequest,
    AgingReportResponse,
    ClientProfileRequest,
    ClientProfileResponse,
    CollectionStrategyRequest,
    CollectionStrategyResponse,
    PortfolioMetricsResponse,
    PaymentPredictionRequest,
    PaymentPredictionResponse,
    CollectionPromptRequest,
    CollectionPromptResponse,
    RiskLevel,
    CollectionPriority,
)


@router.get(
    "/invoice/aging",
    response_model=AgingReportResponse,
    summary="Get aging report",
    description="Generate accounts receivable aging report with buckets and risk analysis.",
)
async def aging_report(
    client_id: Optional[str] = Query(None, description="Filter by client ID"),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> AgingReportResponse:
    """
    Generate aging report showing outstanding invoices by aging buckets.
    
    **Aging Buckets:**
    - Current: 0-30 days
    - 31-60 days: Early delinquency
    - 61-90 days: Moderate risk
    - 91-120 days: High risk
    - 120+ days: Critical / collection
    
    **Query Parameters:**
    - `client_id`: Optional filter for specific client
    """
    try:
        agent = InvoiceIntelligenceAgent(db, current_user)
        
        cid = UUID(client_id) if client_id else None
        summary, invoices = await agent.get_aging_report(client_id=cid)
        
        # Convert invoice details
        invoice_dicts = []
        for inv in invoices:
            invoice_dicts.append({
                "invoice_id": str(inv.invoice_id),
                "invoice_number": inv.invoice_number,
                "client_name": inv.client_name,
                "issue_date": inv.issue_date.isoformat(),
                "due_date": inv.due_date.isoformat(),
                "total_amount": float(inv.total_amount),
                "outstanding": float(inv.outstanding),
                "days_overdue": inv.days_overdue,
                "aging_bucket": inv.aging_bucket.value,
                "risk_level": inv.risk_level.value,
                "status": inv.status,
            })
        
        return AgingReportResponse(
            total_outstanding=float(summary.total_outstanding),
            total_invoices=summary.total_invoices,
            current_amount=float(summary.current_amount),
            bucket_31_60=float(summary.bucket_31_60),
            bucket_61_90=float(summary.bucket_61_90),
            bucket_91_120=float(summary.bucket_91_120),
            bucket_120_plus=float(summary.bucket_120_plus),
            past_due_amount=float(summary.past_due_amount),
            delinquent_percentage=summary.delinquent_percentage,
            invoice_details=invoice_dicts,
        )
        
    except Exception as exc:
        logger.exception("Aging report failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate aging report: {str(exc)}",
        )


@router.get(
    "/invoice/client-profile/{client_id}",
    response_model=ClientProfileResponse,
    summary="Get client payment profile",
    description="Analyze client payment history and behavior patterns.",
)
async def client_profile(
    client_id: str = Path(..., description="Client UUID"),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> ClientProfileResponse:
    """
    Get comprehensive payment behavior profile for a client.
    
    Includes:
    - Payment history analysis
    - Average days to pay
    - On-time payment rate
    - Risk level assessment
    - Credit recommendations
    
    **Path Parameters:**
    - `client_id`: UUID of the client
    """
    try:
        agent = InvoiceIntelligenceAgent(db, current_user)
        
        profile = await agent.get_client_payment_profile(UUID(client_id))
        
        return ClientProfileResponse(
            client_id=str(profile.client_id),
            client_name=profile.client_name,
            total_invoices_issued=profile.total_invoices_issued,
            total_paid_full=profile.total_paid_full,
            total_paid_partial=profile.total_paid_partial,
            total_unpaid=profile.total_unpaid,
            average_days_to_pay=profile.average_days_to_pay,
            on_time_payment_rate=profile.on_time_payment_rate,
            average_invoice_amount=float(profile.average_invoice_amount),
            total_lifetime_value=float(profile.total_lifetime_value),
            risk_level=profile.risk_level.value,
            credit_recommendation=profile.credit_recommendation,
            payment_trend=profile.payment_trend,
        )
        
    except Exception as exc:
        logger.exception("Client profile failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get client profile: {str(exc)}",
        )


@router.get(
    "/invoice/collection-strategy/{client_id}",
    response_model=CollectionStrategyResponse,
    summary="Get collection strategy",
    description="Generate tailored collection strategy for a client.",
)
async def collection_strategy(
    client_id: str = Path(..., description="Client UUID"),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> CollectionStrategyResponse:
    """
    Get AI-recommended collection strategy for a client.
    
    Strategy includes:
    - Risk-based escalation levels
    - Recommended action sequence
    - Suggested message templates
    - Timeline expectations
    - Success probability
    
    **Path Parameters:**
    - `client_id`: UUID of the client
    """
    try:
        agent = InvoiceIntelligenceAgent(db, current_user)
        
        strategy = await agent.generate_collection_strategy(UUID(client_id))
        
        # Convert actions
        action_responses = []
        for action in strategy.actions:
            action_responses.append(CollectionActionResponse(
                action_id=action.action_id,
                action_type=action.action_type,
                priority=action.priority.value,
                invoice_ids=[str(i) for i in action.invoice_ids],
                client_name=action.client_name,
                total_outstanding=float(action.total_outstanding),
                recommended_date=action.recommended_date.isoformat(),
                suggested_message=action.suggested_message,
                escalation_level=action.escalation_level,
                expected_outcome=action.expected_outcome,
                automated=action.automated,
            ))
        
        return CollectionStrategyResponse(
            client_id=str(strategy.client_id),
            client_name=strategy.client_name,
            total_outstanding=float(strategy.total_outstanding),
            risk_level=strategy.risk_level.value,
            actions=action_responses,
            recommended_sequence=strategy.recommended_sequence,
            timeline_days=strategy.timeline_days,
            expected_collection_rate=strategy.expected_collection_rate,
            notes=strategy.notes,
        )
        
    except Exception as exc:
        logger.exception("Collection strategy failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate collection strategy: {str(exc)}",
        )


@router.get(
    "/invoice/portfolio-metrics",
    response_model=PortfolioMetricsResponse,
    summary="Get portfolio metrics",
    description="Get overall receivables portfolio health metrics.",
)
async def portfolio_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> PortfolioMetricsResponse:
    """
    Get comprehensive portfolio metrics including:
    - Total outstanding receivables
    - DSO (Days Sales Outstanding)
    - Aging distribution
    - Risk distribution
    - Collection rates
    - Trend direction
    """
    try:
        agent = InvoiceIntelligenceAgent(db, current_user)
        
        metrics = await agent.get_portfolio_metrics()
        
        return PortfolioMetricsResponse(
            total_outstanding=float(metrics.total_outstanding),
            total_invoices=metrics.total_invoices,
            unique_clients=metrics.unique_clients,
            average_dso=metrics.average_dso,
            current_amount=float(metrics.aging_summary.current_amount),
            past_due_30_60=float(metrics.aging_summary.bucket_31_60),
            past_due_60_90=float(metrics.aging_summary.bucket_61_90),
            past_due_90_plus=float(
                metrics.aging_summary.bucket_91_120 + metrics.aging_summary.bucket_120_plus
            ),
            risk_low=float(metrics.risk_distribution[RiskLevel.LOW]),
            risk_medium=float(metrics.risk_distribution[RiskLevel.MEDIUM]),
            risk_high=float(metrics.risk_distribution[RiskLevel.HIGH]),
            risk_critical=float(metrics.risk_distribution[RiskLevel.CRITICAL]),
            trend_direction=metrics.trend_direction,
        )
        
    except Exception as exc:
        logger.exception("Portfolio metrics failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get portfolio metrics: {str(exc)}",
        )


@router.get(
    "/invoice/predict-payment/{invoice_id}",
    response_model=PaymentPredictionResponse,
    summary="Predict invoice payment",
    description="AI prediction of when and how much an invoice will be paid.",
)
async def predict_payment(
    invoice_id: str = Path(..., description="Invoice UUID"),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> PaymentPredictionResponse:
    """
    Get AI prediction for invoice payment.
    
    Predictions include:
    - Probability of on-time payment
    - Probability of late payment
    - Probability of default
    - Predicted payment date
    - Risk factors
    
    **Path Parameters:**
    - `invoice_id`: UUID of the invoice
    """
    try:
        agent = InvoiceIntelligenceAgent(db, current_user)
        
        prediction = await agent.predict_payment(UUID(invoice_id))
        
        return PaymentPredictionResponse(
            invoice_id=str(prediction.invoice_id),
            prediction_confidence=prediction.prediction_confidence,
            predicted_payment_date=prediction.predicted_payment_date.isoformat() if prediction.predicted_payment_date else None,
            predicted_payment_amount=float(prediction.predicted_payment_amount),
            probability_on_time=prediction.probability_on_time,
            probability_late=prediction.probability_late,
            probability_default=prediction.probability_default,
            risk_factors=prediction.risk_factors,
        )
        
    except Exception as exc:
        logger.exception("Payment prediction failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to predict payment: {str(exc)}",
        )


@router.post(
    "/invoice/collection-prompt",
    response_model=CollectionPromptResponse,
    summary="Generate collection prompt",
    description="Generate AI-crafted collection message for a client.",
)
async def collection_prompt(
    request: CollectionPromptRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> CollectionPromptResponse:
    """
    Generate a collection prompt message tailored to the client.
    
    **Tones:**
    - `professional`: Standard business tone
    - `friendly`: Warm but firm
    - `firm`: Assertive without being aggressive
    - `urgent`: Immediate action required
    
    **Request Body:**
    ```json
    {
        "client_id": "uuid",
        "tone": "professional"
    }
    ```
    """
    try:
        agent = InvoiceIntelligenceAgent(db, current_user)
        
        # Get client data
        profile = await agent.get_client_payment_profile(UUID(request.client_id))
        invoices = await agent.get_outstanding_invoices(client_id=UUID(request.client_id))
        
        total_outstanding = sum(inv.outstanding for inv in invoices)
        invoice_count = len(invoices)
        
        # Determine urgency
        max_days = max((inv.days_overdue for inv in invoices), default=0)
        if max_days > 90:
            urgency = "critical"
            action = "Immediate legal notice recommended"
        elif max_days > 60:
            urgency = "high"
            action = "Collection call and demand letter required"
        elif max_days > 30:
            urgency = "medium"
            action = "Email reminder with follow-up call"
        else:
            urgency = "low"
            action = "Gentle email reminder"
        
        # Generate message based on tone
        tones = {
            "professional": {
                "subject": f"Payment Reminder - Invoice Outstanding ({total_outstanding:,.2f} MYR)",
                "message": f"Dear {profile.client_name},\n\nWe hope this message finds you well. We are writing to remind you of the outstanding balance of {total_outstanding:,.2f} MYR for {invoice_count} invoice(s).\n\nPlease arrange payment at your earliest convenience. If you have any questions or concerns, please don't hesitate to contact us.\n\nThank you for your continued business.",
                "script": f"Hello, this is [Your Name] from Hi-Tech Waste Management. I'm calling regarding the outstanding balance of {total_outstanding:,.2f} MYR from {profile.client_name}. How can we help facilitate payment today?",
            },
            "friendly": {
                "subject": f"Friendly reminder about your invoice",
                "message": f"Hi {profile.client_name},\n\nJust a quick note about the {total_outstanding:,.2f} MYR balance on your account. No rush, but we'd appreciate it if you could take care of this when you have a moment.\n\nLet us know if you need anything!",
                "script": f"Hi! Just following up on the {total_outstanding:,.2f} MYR balance. Everything OK on your end? Can we help get this sorted out?",
            },
            "firm": {
                "subject": f"IMMEDIATE ATTENTION REQUIRED: Outstanding Balance {total_outstanding:,.2f} MYR",
                "message": f"{profile.client_name},\n\nThis is a formal notice that payment of {total_outstanding:,.2f} MYR is now {max_days} days overdue. Please remit payment within 5 business days to avoid further action.\n\nContact us immediately to discuss.",
                "script": f"This is a collection call for {total_outstanding:,.2f} MYR overdue for {max_days} days. When can we expect payment? We need a commitment today.",
            },
            "urgent": {
                "subject": f"URGENT: FINAL NOTICE - Payment Required Immediately",
                "message": f"{profile.client_name},\n\nURGENT: {total_outstanding:,.2f} MYR is severely overdue ({max_days} days). This is your FINAL NOTICE before legal action.\n\nYou must contact us within 48 hours to avoid escalation.\n\nContact: [phone] [email]",
                "script": f"URGENT COLLECTION CALL. This matter requires immediate resolution. {total_outstanding:,.2f} MYR is {max_days} days overdue. I need a payment commitment right now or this will be escalated to legal.",
            },
        }
        
        tone_data = tones.get(request.tone, tones["professional"])
        
        return CollectionPromptResponse(
            client_id=request.client_id,
            client_name=profile.client_name,
            outstanding_amount=float(total_outstanding),
            invoice_count=invoice_count,
            suggested_message=tone_data["message"],
            subject_line=tone_data["subject"],
            call_script=tone_data["script"],
            urgency_level=urgency,
            recommended_action=action,
        )
        
    except Exception as exc:
        logger.exception("Collection prompt failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate collection prompt: {str(exc)}",
        )


# =============================================================
# Invoice Intelligence Integration with AI Chat
# =============================================================

INVOICE_INTELLIGENCE_FUNCTIONS = [
    {
        "name": "get_aging_report",
        "description": "Generate accounts receivable aging report showing outstanding invoices by age buckets (current, 30, 60, 90, 120+ days).",
        "parameters": {
            "type": "object",
            "properties": {
                "client_id": {
                    "type": "string",
                    "description": "Optional: Filter by specific client ID"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_client_payment_profile",
        "description": "Analyze client payment history, average days to pay, on-time rate, and risk level.",
        "parameters": {
            "type": "object",
            "properties": {
                "client_id": {
                    "type": "string",
                    "description": "Client ID to analyze"
                }
            },
            "required": ["client_id"]
        }
    },
    {
        "name": "generate_collection_strategy",
        "description": "Create a tailored collection strategy for a client including action sequence, messages, and timeline.",
        "parameters": {
            "type": "object",
            "properties": {
                "client_id": {
                    "type": "string",
                    "description": "Client ID to generate strategy for"
                }
            },
            "required": ["client_id"]
        }
    },
    {
        "name": "get_portfolio_metrics",
        "description": "Get overall receivables portfolio health including DSO, aging distribution, and risk breakdown.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "predict_invoice_payment",
        "description": "AI prediction of when and how much an invoice will be paid, including risk factors.",
        "parameters": {
            "type": "object",
            "properties": {
                "invoice_id": {
                    "type": "string",
                    "description": "Invoice ID to predict"
                }
            },
            "required": ["invoice_id"]
        }
    },
    {
        "name": "generate_collection_prompt",
        "description": "Generate AI-crafted collection email or call script for a client.",
        "parameters": {
            "type": "object",
            "properties": {
                "client_id": {
                    "type": "string",
                    "description": "Client ID to generate message for"
                },
                "tone": {
                    "type": "string",
                    "enum": ["professional", "friendly", "firm", "urgent"],
                    "default": "professional",
                    "description": "Tone of the message"
                }
            },
            "required": ["client_id"]
        }
    }
]


# Final combined functions - complete AI agent capability
AI_AGENT_COMPLETE_FUNCTIONS = AI_AGENT_ALL_FUNCTIONS + INVOICE_INTELLIGENCE_FUNCTIONS


# =============================================================
# ESG Report Generation Endpoints
# AI-powered sustainability reporting and ESG analytics
# =============================================================

from agents.esg_report_agent import (
    ESGReportAgent,
    ESGReportRequest,
    ESGReportResponse,
    ESGDashboardResponse,
    ClientESGReportResponse,
    ReportPeriod,
    CarbonMetricsResponse,
    WasteMetricsResponse,
    RecyclableMetricsResponse,
    SDGContributionResponse,
)


@router.post(
    "/esg/report",
    response_model=ESGReportResponse,
    summary="Generate ESG report",
    description="Generate comprehensive Environmental, Social, and Governance (ESG) sustainability report.",
)
async def generate_esg_report(
    request: ESGReportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> ESGReportResponse:
    """
    Generate ESG sustainability report for a period.
    
    **Report Types:**
    - `monthly`: Monthly sustainability summary
    - `quarterly`: Quarterly ESG report
    - `annual`: Annual sustainability report
    - `custom`: Custom date range
    
    **Report Includes:**
    - Carbon footprint and emissions
    - Waste diversion metrics
    - Recycling recovery rates
    - UN SDG contributions
    - Executive summary
    - Recommendations
    
    **Request Body:**
    ```json
    {
        "period": "monthly",
        "year": 2026,
        "month": 4,
        "client_id": null
    }
    ```
    """
    try:
        agent = ESGReportAgent(db, current_user)
        
        # Map string period to enum
        period_map = {
            "monthly": ReportPeriod.MONTHLY,
            "quarterly": ReportPeriod.QUARTERLY,
            "annual": ReportPeriod.ANNUAL,
            "custom": ReportPeriod.CUSTOM,
        }
        period = period_map.get(request.period, ReportPeriod.MONTHLY)
        
        # Generate report
        report = await agent.generate_report(
            period=period,
            year=request.year,
            month=request.month,
            quarter=request.quarter,
            custom_start=request.start_date,
            custom_end=request.end_date,
            client_id=UUID(request.client_id) if request.client_id else None,
        )
        
        # Convert SDG contributions
        sdg_responses = []
        for sdg in report.sdg_contributions:
            sdg_responses.append(SDGContributionResponse(
                sdg_number=sdg.sdg_number,
                sdg_name=sdg.sdg_name,
                contribution_description=sdg.contribution_description,
                metrics=sdg.metrics,
                impact_level=sdg.impact_level,
            ))
        
        return ESGReportResponse(
            report_id=report.report_id,
            report_title=report.report_title,
            reporting_period=report.reporting_period,
            start_date=report.start_date.isoformat(),
            end_date=report.end_date.isoformat(),
            generated_at=report.generated_at.isoformat(),
            
            carbon_metrics=CarbonMetricsResponse(
                total_emissions_kgco2e=float(report.carbon_metrics.total_emissions_kgco2e),
                total_avoided_kgco2e=float(report.carbon_metrics.total_avoided_kgco2e),
                net_impact_kgco2e=float(report.carbon_metrics.net_impact_kgco2e),
                net_positive=report.carbon_metrics.net_positive,
                transport_emissions=float(report.carbon_metrics.transport_emissions),
                landfill_avoidance=float(report.carbon_metrics.landfill_avoidance),
                recycling_credits=float(report.carbon_metrics.recycling_credits),
                wte_credits=float(report.carbon_metrics.wte_credits),
                trees_equivalent=float(report.carbon_metrics.carbon_offset_equivalent),
            ),
            
            waste_metrics=WasteMetricsResponse(
                total_waste_collected_kg=float(report.waste_metrics.total_waste_collected_kg),
                total_waste_diverted_kg=float(report.waste_metrics.total_waste_diverted_kg),
                total_recycled_kg=float(report.waste_metrics.total_recycled_kg),
                total_wte_kg=float(report.waste_metrics.total_wte_kg),
                total_landfill_kg=float(report.waste_metrics.total_landfill_kg),
                total_composted_kg=float(report.waste_metrics.total_composted_kg),
                diversion_rate=report.waste_metrics.diversion_rate,
                recycling_rate=report.waste_metrics.recycling_rate,
                circular_economy_rate=report.waste_metrics.circular_economy_rate,
            ),
            
            recyclable_metrics=RecyclableMetricsResponse(
                total_collections=report.recyclable_metrics.total_collections,
                total_weight_kg=float(report.recyclable_metrics.total_weight_kg),
                material_breakdown={k: float(v) for k, v in report.recyclable_metrics.material_breakdown.items()},
                downstream_partners=report.recyclable_metrics.downstream_partners,
                delivery_count=report.recyclable_metrics.delivery_count,
                estimated_recovery_value_myr=float(
                    report.recyclable_metrics.total_weight_kg * report.recyclable_metrics.avg_recovery_value_per_kg
                ),
            ),
            
            sdg_contributions=sdg_responses,
            
            executive_summary=report.executive_summary,
            key_achievements=report.key_achievements,
            improvement_areas=report.improvement_areas,
            recommendations=report.recommendations,
            
            pdf_url=None,  # Would be generated async
        )
        
    except Exception as exc:
        logger.exception("ESG report generation failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate ESG report: {str(exc)}",
        )


@router.get(
    "/esg/dashboard",
    response_model=ESGDashboardResponse,
    summary="Get ESG dashboard",
    description="Get real-time ESG dashboard metrics including MTD and YTD statistics.",
)
async def esg_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> ESGDashboardResponse:
    """
    Get real-time ESG dashboard with current metrics.
    
    **Returns:**
    - Month-to-date carbon and waste metrics
    - Year-to-date totals
    - Trend indicators
    - Active alerts
    """
    try:
        agent = ESGReportAgent(db, current_user)
        
        dashboard = await agent.get_dashboard_metrics()
        
        return ESGDashboardResponse(
            month_to_date_carbon=CarbonMetricsResponse(
                total_emissions_kgco2e=float(dashboard.month_to_date_carbon.total_emissions_kgco2e),
                total_avoided_kgco2e=float(dashboard.month_to_date_carbon.total_avoided_kgco2e),
                net_impact_kgco2e=float(dashboard.month_to_date_carbon.net_impact_kgco2e),
                net_positive=dashboard.month_to_date_carbon.net_positive,
                transport_emissions=float(dashboard.month_to_date_carbon.transport_emissions),
                landfill_avoidance=float(dashboard.month_to_date_carbon.landfill_avoidance),
                recycling_credits=float(dashboard.month_to_date_carbon.recycling_credits),
                wte_credits=float(dashboard.month_to_date_carbon.wte_credits),
                trees_equivalent=float(dashboard.month_to_date_carbon.carbon_offset_equivalent),
            ),
            month_to_date_waste=WasteMetricsResponse(
                total_waste_collected_kg=float(dashboard.month_to_date_waste.total_waste_collected_kg),
                total_waste_diverted_kg=float(dashboard.month_to_date_waste.total_waste_diverted_kg),
                total_recycled_kg=float(dashboard.month_to_date_waste.total_recycled_kg),
                total_wte_kg=float(dashboard.month_to_date_waste.total_wte_kg),
                total_landfill_kg=float(dashboard.month_to_date_waste.total_landfill_kg),
                total_composted_kg=float(dashboard.month_to_date_waste.total_composted_kg),
                diversion_rate=dashboard.month_to_date_waste.diversion_rate,
                recycling_rate=dashboard.month_to_date_waste.recycling_rate,
                circular_economy_rate=dashboard.month_to_date_waste.circular_economy_rate,
            ),
            year_to_date_carbon=CarbonMetricsResponse(
                total_emissions_kgco2e=float(dashboard.year_to_date_carbon.total_emissions_kgco2e),
                total_avoided_kgco2e=float(dashboard.year_to_date_carbon.total_avoided_kgco2e),
                net_impact_kgco2e=float(dashboard.year_to_date_carbon.net_impact_kgco2e),
                net_positive=dashboard.year_to_date_carbon.net_positive,
                transport_emissions=float(dashboard.year_to_date_carbon.transport_emissions),
                landfill_avoidance=float(dashboard.year_to_date_carbon.landfill_avoidance),
                recycling_credits=float(dashboard.year_to_date_carbon.recycling_credits),
                wte_credits=float(dashboard.year_to_date_carbon.wte_credits),
                trees_equivalent=float(dashboard.year_to_date_carbon.carbon_offset_equivalent),
            ),
            year_to_date_waste=WasteMetricsResponse(
                total_waste_collected_kg=float(dashboard.year_to_date_waste.total_waste_collected_kg),
                total_waste_diverted_kg=float(dashboard.year_to_date_waste.total_waste_diverted_kg),
                total_recycled_kg=float(dashboard.year_to_date_waste.total_recycled_kg),
                total_wte_kg=float(dashboard.year_to_date_waste.total_wte_kg),
                total_landfill_kg=float(dashboard.year_to_date_waste.total_landfill_kg),
                total_composted_kg=float(dashboard.year_to_date_waste.total_composted_kg),
                diversion_rate=dashboard.year_to_date_waste.diversion_rate,
                recycling_rate=dashboard.year_to_date_waste.recycling_rate,
                circular_economy_rate=dashboard.year_to_date_waste.circular_economy_rate,
            ),
            top_performing_clients=dashboard.top_performing_clients,
            trends=dashboard.trends,
            alerts=dashboard.alerts,
        )
        
    except Exception as exc:
        logger.exception("ESG dashboard failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get ESG dashboard: {str(exc)}",
        )


@router.get(
    "/esg/client-report/{client_id}",
    response_model=ClientESGReportResponse,
    summary="Get client ESG report",
    description="Generate sustainability report for a specific client.",
)
async def client_esg_report(
    client_id: str = Path(..., description="Client UUID"),
    period: str = Query("annual", description="Report period: monthly, quarterly, annual"),
    year: Optional[int] = Query(None, description="Year (defaults to current)"),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> ClientESGReportResponse:
    """
    Generate client-specific ESG sustainability report.
    
    Perfect for sharing with clients to demonstrate
    environmental impact of their waste management.
    
    **Path Parameters:**
    - `client_id`: Client UUID
    
    **Query Parameters:**
    - `period`: monthly, quarterly, annual
    - `year`: Report year
    """
    try:
        agent = ESGReportAgent(db, current_user)
        
        period_map = {
            "monthly": ReportPeriod.MONTHLY,
            "quarterly": ReportPeriod.QUARTERLY,
            "annual": ReportPeriod.ANNUAL,
        }
        report_period = period_map.get(period, ReportPeriod.ANNUAL)
        
        report = await agent.get_client_esg_report(
            client_id=UUID(client_id),
            period=report_period,
            year=year,
        )
        
        return ClientESGReportResponse(
            client_id=str(report.client_id),
            client_name=report.client_name,
            reporting_period=report.reporting_period,
            waste_collected_kg=float(report.waste_collected_kg),
            waste_diverted_kg=float(report.waste_diverted_kg),
            diversion_rate=report.diversion_rate,
            carbon_impact_kgco2e=float(report.carbon_impact_kgco2e),
            environmental_benefits=report.environmental_benefits,
            certificates_generated=report.certificates_generated,
            compliance_status=report.compliance_status,
        )
        
    except Exception as exc:
        logger.exception("Client ESG report failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate client ESG report: {str(exc)}",
        )


# =============================================================
# ESG Integration with AI Chat
# =============================================================

ESG_FUNCTIONS = [
    {
        "name": "generate_esg_report",
        "description": "Generate comprehensive ESG (Environmental, Social, Governance) sustainability report for a period.",
        "parameters": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "enum": ["monthly", "quarterly", "annual"],
                    "default": "monthly",
                    "description": "Report period"
                },
                "year": {
                    "type": "integer",
                    "description": "Year for the report"
                },
                "month": {
                    "type": "integer",
                    "description": "Month for monthly report (1-12)"
                },
                "client_id": {
                    "type": "string",
                    "description": "Optional: Generate report for specific client"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_esg_dashboard",
        "description": "Get real-time ESG dashboard with month-to-date and year-to-date sustainability metrics.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_carbon_footprint",
        "description": "Calculate carbon footprint and emissions for a period, including avoided emissions.",
        "parameters": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "enum": ["monthly", "quarterly", "annual"],
                    "default": "monthly",
                    "description": "Time period"
                },
                "client_id": {
                    "type": "string",
                    "description": "Optional: Filter by client"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_waste_diversion_metrics",
        "description": "Get waste diversion metrics including recycling rates and circular economy indicators.",
        "parameters": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "enum": ["monthly", "quarterly", "annual"],
                    "default": "monthly",
                    "description": "Time period"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_client_sustainability_report",
        "description": "Generate sustainability report for a specific client showing their environmental impact.",
        "parameters": {
            "type": "object",
            "properties": {
                "client_id": {
                    "type": "string",
                    "description": "Client ID to generate report for"
                },
                "period": {
                    "type": "string",
                    "enum": ["monthly", "quarterly", "annual"],
                    "default": "annual",
                    "description": "Report period"
                }
            },
            "required": ["client_id"]
        }
    }
]


# Final combined functions - all AI capabilities
AI_AGENT_ALL_CAPABILITIES = AI_AGENT_COMPLETE_FUNCTIONS + ESG_FUNCTIONS
