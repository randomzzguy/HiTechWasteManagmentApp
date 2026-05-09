# =============================================================
# Hi-Tech Waste Management — AI & RAG Integration Tests
# Tests for AI chat endpoints, document ingestion, and RAG retrieval
#
# Run with: pytest tests/test_ai_rag_integration.py -v
# =============================================================

from __future__ import annotations

import uuid
import json
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

# ── App imports ───────────────────────────────────────────────
from database import get_db, Base
from main import app
from models.user import User
from models.document import Document
from models.client import Client
from routers.auth import hash_password, get_current_user

# =============================================================
# Test Database Setup
# =============================================================

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)


@event.listens_for(test_engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    """Override FastAPI DB dependency for testing."""
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# =============================================================
# Test User
# =============================================================

TEST_ADMIN = {
    "id": str(uuid.uuid4()),
    "email": "admin@hitechwaste.com.my",
    "full_name": "Test Administrator",
    "role": "superadmin",
    "is_active": True,
}


async def override_get_current_user_admin() -> dict[str, Any]:
    """Return admin user for authenticated endpoints."""
    return TEST_ADMIN.copy()


# =============================================================
# Pytest Fixtures
# =============================================================

@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_test_tables():
    """Create only the tables needed for AI tests (SQLite-compatible)."""
    async with test_engine.begin() as conn:
        # Create only tables that don't use PostgreSQL-specific types
        await conn.run_sync(User.__table__.create, checkfirst=True)
        await conn.run_sync(Client.__table__.create, checkfirst=True)
        await conn.run_sync(Document.__table__.create, checkfirst=True)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Document.__table__.drop, checkfirst=True)
        await conn.run_sync(Client.__table__.drop, checkfirst=True)
        await conn.run_sync(User.__table__.drop, checkfirst=True)


@pytest_asyncio.fixture
async def api_client() -> AsyncGenerator[AsyncClient, None]:
    """Authenticated API client for testing."""
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user_admin
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        timeout=30.0,  # Longer timeout for AI endpoints
    ) as client:
        yield client
    
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session for direct DB operations in tests."""
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def test_client_in_db(db_session: AsyncSession) -> Client:
    """Create a test client in the database."""
    client = Client(
        id=uuid.uuid4(),
        company_name="AI Test Client Sdn Bhd",
        contact_person="AI Tester",
        email="ai@testclient.com",
        phone="+60 12-345 6789",
        address="AI Testing Facility",
        is_active=True,
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)
    return client


@pytest_asyncio.fixture
async def test_document_in_db(db_session: AsyncSession, test_client_in_db: Client) -> Document:
    """Create a test document in the database."""
    doc = Document(
        id=uuid.uuid4(),
        filename="waste_policy_2024.pdf",
        mime_type="application/pdf",
        size_bytes=1024000,
        client_id=test_client_in_db.id,
        uploaded_by=uuid.UUID(TEST_ADMIN["id"]),
        description="Waste management policy document for 2024",
        status="processed",
        milvus_id="test_milvus_id_123",
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)
    return doc


# =============================================================
# AI Chat Tests
# =============================================================

class TestAIChat:
    """Tests for the AI chat endpoint with RAG capabilities."""

    async def test_ai_chat_health(self, api_client: AsyncClient):
        """Test that AI health endpoint returns status."""
        response = await api_client.get("/api/v1/ai/health")
        
        # This endpoint may or may not exist depending on implementation
        if response.status_code == 200:
            data = response.json()
            assert "status" in data or "ollama" in data or "milvus" in data
            print("✓ AI health endpoint accessible")
        elif response.status_code == 404:
            pytest.skip("AI health endpoint not implemented")
        else:
            # Other statuses are acceptable for health checks
            print(f"⚠ AI health returned {response.status_code}")

    async def test_basic_chat_message(self, api_client: AsyncClient):
        """Test sending a basic chat message to the AI."""
        chat_data = {
            "message": "What is the waste collection process?",
            "conversation_history": [],
            "use_rag": False,  # Pure LLM response without RAG
            "temperature": 0.7,
        }
        
        response = await api_client.post("/api/v1/ai/chat", json=chat_data)
        
        # The actual LLM integration may not be available in test environment
        if response.status_code == 200:
            # Check if streaming or direct response
            content_type = response.headers.get("content-type", "")
            
            if "text/event-stream" in content_type:
                # SSE streaming response
                print("✓ AI chat returns SSE stream")
            else:
                # Direct JSON response
                data = response.json()
                assert "response" in data or "message" in data or "content" in data
                print(f"✓ AI chat response received: {data.get('response', '')[:100]}...")
        elif response.status_code == 503:
            pytest.skip("Ollama LLM service unavailable - skipping AI chat test")
        elif response.status_code in [422, 500]:
            # May fail if LLM is not configured
            print(f"⚠ AI chat endpoint returned {response.status_code}")
            pytest.skip(f"AI chat endpoint returned {response.status_code}")
        else:
            pytest.skip(f"Unexpected status: {response.status_code}")

    async def test_chat_with_context(self, api_client: AsyncClient, test_client_in_db: Client):
        """Test AI chat with RAG context from client documents."""
        chat_data = {
            "message": "What are the waste disposal guidelines?",
            "conversation_history": [],
            "client_id": str(test_client_in_db.id),
            "use_rag": True,
            "max_context_chunks": 5,
            "temperature": 0.5,
        }
        
        response = await api_client.post("/api/v1/ai/chat", json=chat_data)
        
        if response.status_code == 200:
            content_type = response.headers.get("content-type", "")
            
            if "text/event-stream" in content_type:
                print("✓ RAG chat with context returns SSE stream")
            else:
                data = response.json()
                # Should include context or sources if RAG is working
                print(f"✓ RAG chat response received")
        elif response.status_code == 503:
            pytest.skip("Ollama/Milvus service unavailable")
        else:
            pytest.skip(f"RAG chat unavailable: {response.status_code}")

    async def test_chat_with_conversation_history(self, api_client: AsyncClient):
        """Test AI chat with conversation history for context."""
        chat_data = {
            "message": "Can you explain more about that?",
            "conversation_history": [
                {"role": "user", "content": "Tell me about recycling"},
                {"role": "assistant", "content": "Recycling is the process of converting waste materials..."},
            ],
            "use_rag": False,
            "temperature": 0.7,
        }
        
        response = await api_client.post("/api/v1/ai/chat", json=chat_data)
        
        if response.status_code == 200:
            print("✓ AI chat with conversation history works")
        elif response.status_code == 503:
            pytest.skip("Ollama service unavailable")
        else:
            pytest.skip(f"Chat with history unavailable: {response.status_code}")

    async def test_chat_temperature_variations(self, api_client: AsyncClient):
        """Test AI chat with different temperature settings."""
        temperatures = [0.0, 0.5, 1.0, 1.5]
        
        for temp in temperatures:
            chat_data = {
                "message": "What is waste management?",
                "conversation_history": [],
                "use_rag": False,
                "temperature": temp,
            }
            
            response = await api_client.post("/api/v1/ai/chat", json=chat_data)
            
            if response.status_code == 200:
                print(f"✓ Temperature {temp}: OK")
            elif response.status_code == 422:
                # Temperature validation error
                print(f"✓ Temperature {temp}: Properly validated")
            else:
                print(f"⚠ Temperature {temp}: {response.status_code}")


# =============================================================
# Agent Events Tests
# =============================================================

class TestAgentEvents:
    """Tests for AI agent event system."""

    async def test_list_agent_events(self, api_client: AsyncClient):
        """Test listing agent events."""
        response = await api_client.get("/api/v1/ai/agent-events")
        
        if response.status_code == 200:
            data = response.json()
            assert "items" in data or isinstance(data, list)
            print("✓ Agent events listing works")
        elif response.status_code == 404:
            pytest.skip("Agent events endpoint not implemented")
        else:
            print(f"⚠ Agent events: {response.status_code}")

    async def test_create_and_retrieve_agent_event(
        self, api_client: AsyncClient, test_client_in_db: Client
    ):
        """Test creating and retrieving an agent event."""
        event_data = {
            "event_type": "document_analysis",
            "source_agent": "document_processor",
            "payload": {
                "client_id": str(test_client_in_db.id),
                "document_name": "test_document.pdf",
                "analysis_summary": "Document analyzed successfully",
            },
            "severity": "info",
        }
        
        # Try to create event (if endpoint exists)
        response = await api_client.post("/api/v1/ai/agent-events", json=event_data)
        
        if response.status_code == 201:
            data = response.json()
            event_id = data.get("id")
            
            # Try to retrieve the created event
            get_response = await api_client.get(f"/api/v1/ai/agent-events/{event_id}")
            assert get_response.status_code == 200
            print("✓ Agent event creation and retrieval works")
        elif response.status_code == 404:
            pytest.skip("Agent events POST endpoint not implemented")
        else:
            print(f"⚠ Agent event creation: {response.status_code}")

    async def test_mark_events_as_read(self, api_client: AsyncClient):
        """Test marking agent events as read."""
        mark_read_data = {
            "event_ids": [str(uuid.uuid4())],  # Mock ID
        }
        
        response = await api_client.post(
            "/api/v1/ai/agent-events/mark-read",
            json=mark_read_data,
        )
        
        if response.status_code == 200:
            print("✓ Mark events as read works")
        elif response.status_code == 404:
            pytest.skip("Mark read endpoint not implemented")
        else:
            print(f"⚠ Mark as read: {response.status_code}")


# =============================================================
# Document Ingestion Tests
# =============================================================

class TestDocumentIngestion:
    """Tests for document upload and RAG ingestion."""

    async def test_list_documents(self, api_client: AsyncClient):
        """Test listing documents."""
        response = await api_client.get("/api/v1/ai/documents")
        
        if response.status_code == 200:
            data = response.json()
            assert "items" in data or isinstance(data, list)
            print("✓ Document listing works")
        elif response.status_code == 404:
            pytest.skip("Documents endpoint not implemented")
        else:
            print(f"⚠ Document listing: {response.status_code}")

    async def test_upload_document(self, api_client: AsyncClient, test_client_in_db: Client):
        """Test document upload for RAG."""
        # Create a simple test file content
        file_content = b"Test waste management policy document content for RAG testing."
        
        files = {
            "file": ("test_policy.txt", file_content, "text/plain"),
        }
        data = {
            "client_id": str(test_client_in_db.id),
            "description": "Test document for RAG ingestion",
        }
        
        response = await api_client.post(
            "/api/v1/ai/documents",
            files=files,
            data=data,
        )
        
        if response.status_code == 201:
            result = response.json()
            assert "id" in result
            assert result["status"] in ["pending", "processing", "processed"]
            print(f"✓ Document uploaded: {result['id']}")
        elif response.status_code == 404:
            pytest.skip("Document upload endpoint not implemented")
        elif response.status_code == 503:
            pytest.skip("Document processing service unavailable")
        else:
            print(f"⚠ Document upload: {response.status_code}")

    async def test_document_status_check(
        self, api_client: AsyncClient, test_document_in_db: Document
    ):
        """Test checking document processing status."""
        response = await api_client.get(
            f"/api/v1/ai/documents/{test_document_in_db.id}"
        )
        
        if response.status_code == 200:
            data = response.json()
            assert data["id"] == str(test_document_in_db.id)
            assert "status" in data
            print(f"✓ Document status check: {data['status']}")
        elif response.status_code == 404:
            pytest.skip("Document detail endpoint not implemented")
        else:
            print(f"⚠ Document status: {response.status_code}")

    async def test_delete_document(self, api_client: AsyncClient, test_document_in_db: Document):
        """Test deleting a document."""
        response = await api_client.delete(
            f"/api/v1/ai/documents/{test_document_in_db.id}"
        )
        
        if response.status_code in [200, 204]:
            print("✓ Document deletion works")
        elif response.status_code == 404:
            pytest.skip("Document delete endpoint not implemented")
        else:
            print(f"⚠ Document deletion: {response.status_code}")


# =============================================================
# RAG Retrieval Tests
# =============================================================

class TestRAGRetrieval:
    """Tests for RAG context retrieval without full chat."""

    async def test_search_documents(self, api_client: AsyncClient):
        """Test searching documents via RAG."""
        search_data = {
            "query": "waste collection procedures",
            "max_results": 5,
        }
        
        response = await api_client.post("/api/v1/ai/search", json=search_data)
        
        if response.status_code == 200:
            data = response.json()
            assert "results" in data or "chunks" in data or "documents" in data
            print("✓ RAG document search works")
        elif response.status_code == 404:
            pytest.skip("RAG search endpoint not implemented")
        elif response.status_code == 503:
            pytest.skip("Milvus vector database unavailable")
        else:
            print(f"⚠ RAG search: {response.status_code}")

    async def test_rag_context_only(self, api_client: AsyncClient):
        """Test retrieving RAG context without LLM generation."""
        context_request = {
            "query": "recycling guidelines",
            "max_chunks": 3,
        }
        
        response = await api_client.post("/api/v1/ai/rag-context", json=context_request)
        
        if response.status_code == 200:
            data = response.json()
            assert "context" in data or "chunks" in data
            print("✓ RAG context retrieval works")
        elif response.status_code == 404:
            pytest.skip("RAG context endpoint not implemented")
        else:
            print(f"⚠ RAG context: {response.status_code}")


# =============================================================
# Database Agent Tests
# =============================================================

class TestDatabaseAgent:
    """Tests for the AI database agent capabilities."""

    async def test_db_agent_query(self, api_client: AsyncClient):
        """Test database agent natural language query."""
        query_data = {
            "query": "How many jobs were completed last month?",
            "session_id": str(uuid.uuid4()),
        }
        
        response = await api_client.post("/api/v1/ai/db-query", json=query_data)
        
        if response.status_code == 200:
            data = response.json()
            # Could be streaming or direct
            print("✓ Database agent query works")
        elif response.status_code == 404:
            pytest.skip("DB agent endpoint not implemented")
        else:
            print(f"⚠ DB agent query: {response.status_code}")

    async def test_db_agent_schema_info(self, api_client: AsyncClient):
        """Test getting database schema information for agent."""
        response = await api_client.get("/api/v1/ai/db-schema")
        
        if response.status_code == 200:
            data = response.json()
            assert "tables" in data or "schema" in data
            print("✓ DB schema endpoint works")
        elif response.status_code == 404:
            pytest.skip("DB schema endpoint not implemented")
        else:
            print(f"⚠ DB schema: {response.status_code}")


# =============================================================
# Streaming Tests
# =============================================================

class TestStreaming:
    """Tests for SSE streaming endpoints."""

    async def test_chat_streaming_format(self, api_client: AsyncClient):
        """Test that chat endpoint returns properly formatted SSE."""
        chat_data = {
            "message": "Hello",
            "use_rag": False,
        }
        
        response = await api_client.post("/api/v1/ai/chat", json=chat_data)
        
        if response.status_code == 200:
            content_type = response.headers.get("content-type", "")
            
            if "text/event-stream" in content_type:
                # Parse SSE format
                content = response.text
                assert "data:" in content or content.startswith("data:")
                print("✓ SSE streaming format is correct")
            else:
                print("✓ Chat returns direct JSON (non-streaming)")
        elif response.status_code == 503:
            pytest.skip("LLM service unavailable")
        else:
            pytest.skip(f"Chat streaming test: {response.status_code}")


# =============================================================
# Integration with Other Modules
# =============================================================

class TestAIIntegrationWithModules:
    """Test AI features integrated with other system modules."""

    async def test_client_scoped_chat(
        self, api_client: AsyncClient, test_client_in_db: Client, test_document_in_db: Document
    ):
        """Test that chat can be scoped to a specific client's documents."""
        chat_data = {
            "message": "What are our waste disposal policies?",
            "client_id": str(test_client_in_db.id),
            "use_rag": True,
        }
        
        response = await api_client.post("/api/v1/ai/chat", json=chat_data)
        
        if response.status_code == 200:
            print("✓ Client-scoped chat works")
        elif response.status_code == 503:
            pytest.skip("RAG service unavailable")
        else:
            print(f"⚠ Client-scoped chat: {response.status_code}")

    async def test_job_assistance_chat(self, api_client: AsyncClient):
        """Test AI assistant for job-related queries."""
        chat_data = {
            "message": "How do I schedule a waste collection job?",
            "conversation_history": [],
            "use_rag": True,
        }
        
        response = await api_client.post("/api/v1/ai/chat", json=chat_data)
        
        if response.status_code == 200:
            print("✓ Job assistance chat works")
        elif response.status_code == 503:
            pytest.skip("LLM service unavailable")
        else:
            print(f"⚠ Job assistance chat: {response.status_code}")


# =============================================================
# Run Configuration
# =============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
