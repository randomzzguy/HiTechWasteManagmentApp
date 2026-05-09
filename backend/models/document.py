# =============================================================
# Hi-Tech Waste Management — Document, Certificate & Agent Event Models
# SQLAlchemy 2.0 async ORM + Pydantic v2 schemas
# =============================================================

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from models.client import Client
    from models.user import User

from database import Base
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

# =============================================================
# Valid value sets
# =============================================================

CERT_TYPES = {"recycling", "destruction", "esg_report"}
AGENT_EVENT_TYPES = {"alert", "action", "recommendation", "report"}
AGENT_SEVERITIES = {"info", "warning", "critical"}
DOC_TYPES = {"regulation", "contract", "sop", "report", "manual"}


# =============================================================
# SQLAlchemy ORM Models
# =============================================================


class Certificate(Base):
    """
    Represents an officially issued certificate for a compliance or
    sustainability event:
        - recycling      : Certificate of Recycling for a RecyclableRecord
        - destruction    : Certificate of Destruction for a DestructionJob
        - esg_report     : ESG / sustainability report certificate

    reference_id is a soft foreign key (UUID only, no DB constraint)
    pointing to the parent record (RecyclableRecord, DestructionJob, etc.)
    depending on cert_type.

    is_void is set to True when a certificate has been revoked or superseded.
    """

    __tablename__ = "certificates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        index=True,
    )
    cert_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
        comment="recycling | destruction | esg_report",
    )
    reference_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment=(
            "Soft FK to the parent record "
            "(RecyclableRecord.id, DestructionJob.id, etc.)"
        ),
    )
    client_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        index=True,
    )
    issued_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Hi-Tech staff member who issued / authorised the certificate",
    )
    pdf_path: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Filesystem or object-storage path to the generated PDF",
    )
    is_void: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="True when certificate has been revoked or superseded",
    )

    # ── Relationships ─────────────────────────────────────────
    client: Mapped[Optional["Client"]] = relationship(
        "Client",
        foreign_keys=[client_id],
        lazy="selectin",
    )
    issuer: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[issued_by],
        lazy="selectin",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Certificate id={self.id} type={self.cert_type} "
            f"client_id={self.client_id} void={self.is_void}>"
        )


class AgentEvent(Base):
    """
    Records an event emitted by one of the AI/automation agents in the platform.

    agent_name examples:
        ComplianceAgent, FleetAgent, ESGAgent, BillingAgent, RAGAgent

    event_type choices:
        alert | action | recommendation | report

    severity choices:
        info | warning | critical

    reference_type + reference_id together identify the resource the event
    relates to (e.g. reference_type="ScheduledWasteBatch", reference_id=<uuid>).
    """

    __tablename__ = "agent_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        index=True,
    )
    agent_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Name of the agent that emitted this event",
    )
    event_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
        comment="alert | action | recommendation | report",
    )
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="info",
        index=True,
        comment="info | warning | critical",
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Short human-readable event title",
    )
    body: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Full event description / narrative",
    )
    reference_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment=(
            "Model/entity type this event relates to, "
            "e.g. 'ScheduledWasteBatch', 'Job', 'Vehicle'"
        ),
    )
    reference_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="UUID of the referenced resource",
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="True once a user has acknowledged/read this event",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        index=True,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<AgentEvent id={self.id} agent={self.agent_name} "
            f"type={self.event_type} severity={self.severity} read={self.is_read}>"
        )


class Document(Base):
    """
    Stores metadata for documents uploaded to the platform.

    Documents may be:
        - Regulatory references (DOE regulations, EQA requirements)
        - Client contracts / SLAs
        - Internal SOPs
        - Generated reports
        - Training manuals

    When ingested_into_rag=True the document content has been chunked,
    embedded, and stored in the Milvus vector database under milvus_collection.
    The RAG pipeline uses these embeddings to answer natural-language queries.

    client_id is nullable — regulatory docs and internal manuals are not
    client-specific.
    """

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
        comment="Human-readable document title",
    )
    doc_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
        comment="regulation | contract | sop | report | manual",
    )
    client_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Client this document belongs to; null for platform-wide documents",
    )
    file_path: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Filesystem or object-storage (MinIO/S3) path to the file",
    )
    mime_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="MIME type of the file, e.g. application/pdf, text/plain",
    )
    ingested_into_rag: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="True once the document has been embedded and stored in Milvus",
    )
    milvus_collection: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Milvus collection name where this document's chunks are stored",
    )
    uploaded_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who uploaded the document",
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        index=True,
    )
    file_size_bytes: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Size of the uploaded file in bytes at upload time",
    )
    ingestion_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Last error message from a failed ingestion attempt; null on success",
    )

    # ── Relationships ─────────────────────────────────────────
    client: Mapped[Optional["Client"]] = relationship(
        "Client",
        foreign_keys=[client_id],
        lazy="selectin",
    )
    uploader: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[uploaded_by],
        lazy="selectin",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Document id={self.id} title='{self.title}' "
            f"type={self.doc_type} rag={self.ingested_into_rag}>"
        )


# =============================================================
# Pydantic Schemas — Certificate
# =============================================================


class CertificateCreate(BaseModel):
    cert_type: str = Field(
        ...,
        description="recycling | destruction | esg_report",
    )
    reference_id: Optional[uuid.UUID] = Field(
        default=None,
        description="UUID of the parent resource (RecyclableRecord, DestructionJob, etc.)",
    )
    client_id: Optional[uuid.UUID] = None
    issued_by: Optional[uuid.UUID] = None
    pdf_path: Optional[str] = None

    model_config = ConfigDict(str_strip_whitespace=True)

    def validate_cert_type(self) -> "CertificateCreate":
        if self.cert_type not in CERT_TYPES:
            raise ValueError(f"cert_type must be one of {sorted(CERT_TYPES)}")
        return self


class CertificateUpdate(BaseModel):
    pdf_path: Optional[str] = None
    is_void: Optional[bool] = None
    issued_by: Optional[uuid.UUID] = None

    model_config = ConfigDict(str_strip_whitespace=True)


class CertificateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    cert_type: str
    reference_id: Optional[uuid.UUID]
    client_id: Optional[uuid.UUID]
    issued_at: datetime
    issued_by: Optional[uuid.UUID]
    pdf_path: Optional[str]
    is_void: bool


# =============================================================
# Pydantic Schemas — AgentEvent
# =============================================================


class AgentEventCreate(BaseModel):
    agent_name: str = Field(
        ...,
        max_length=100,
        examples=["ComplianceAgent"],
    )
    event_type: str = Field(
        ...,
        description="alert | action | recommendation | report",
    )
    severity: str = Field(
        default="info",
        description="info | warning | critical",
    )
    title: str = Field(..., max_length=255)
    body: Optional[str] = None
    reference_type: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Model name the event relates to, e.g. 'ScheduledWasteBatch'",
    )
    reference_id: Optional[uuid.UUID] = None

    model_config = ConfigDict(str_strip_whitespace=True)

    def validate_enums(self) -> "AgentEventCreate":
        if self.event_type not in AGENT_EVENT_TYPES:
            raise ValueError(f"event_type must be one of {sorted(AGENT_EVENT_TYPES)}")
        if self.severity not in AGENT_SEVERITIES:
            raise ValueError(f"severity must be one of {sorted(AGENT_SEVERITIES)}")
        return self


class AgentEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_name: str
    event_type: str
    severity: str
    title: str
    body: Optional[str]
    reference_type: Optional[str]
    reference_id: Optional[uuid.UUID]
    is_read: bool
    created_at: datetime


class AgentEventMarkRead(BaseModel):
    """Payload for PATCH /agent-events/{id}/read."""

    is_read: bool = True


# =============================================================
# Pydantic Schemas — Document
# =============================================================


class DocumentCreate(BaseModel):
    title: str = Field(..., max_length=500)
    doc_type: str = Field(
        ...,
        description="regulation | contract | sop | report | manual",
    )
    client_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Omit for platform-wide documents",
    )
    file_path: Optional[str] = None
    mime_type: Optional[str] = Field(
        default=None,
        max_length=100,
        examples=["application/pdf"],
    )
    uploaded_by: Optional[uuid.UUID] = None

    model_config = ConfigDict(str_strip_whitespace=True)

    def validate_doc_type(self) -> "DocumentCreate":
        if self.doc_type not in DOC_TYPES:
            raise ValueError(f"doc_type must be one of {sorted(DOC_TYPES)}")
        return self


class DocumentUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=500)
    doc_type: Optional[str] = None
    client_id: Optional[uuid.UUID] = None
    file_path: Optional[str] = None
    mime_type: Optional[str] = Field(default=None, max_length=100)
    ingested_into_rag: Optional[bool] = None
    milvus_collection: Optional[str] = Field(default=None, max_length=100)

    model_config = ConfigDict(str_strip_whitespace=True)


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    doc_type: str
    client_id: Optional[uuid.UUID]
    file_path: Optional[str]
    mime_type: Optional[str]
    ingested_into_rag: bool
    milvus_collection: Optional[str]
    uploaded_by: Optional[uuid.UUID]
    uploaded_at: datetime
    file_size_bytes: Optional[int] = None
    ingestion_error: Optional[str] = None


class DocumentIngestStatusRead(BaseModel):
    """
    Returned after triggering a RAG ingestion task for a document.
    """

    document_id: uuid.UUID
    title: str
    ingested_into_rag: bool
    milvus_collection: Optional[str]
    task_id: Optional[str] = Field(
        default=None,
        description="Celery task ID if ingestion was queued asynchronously",
    )
    message: str
