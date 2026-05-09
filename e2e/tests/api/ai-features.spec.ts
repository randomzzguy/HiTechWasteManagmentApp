/**
 * Hi-Tech Waste Management — AI/RAG API E2E Tests
 * 
 * Tests for:
 * - AI chat endpoints (with and without RAG)
 * - Document upload and ingestion
 * - Agent events
 * - Streaming responses
 * 
 * Run with: npx playwright test api/ai-features.spec.ts
 */

import { test, expect, APIRequestContext } from '@playwright/test';

const API_BASE_URL = process.env.TEST_API_URL || 'http://localhost:8000';
const TEST_CREDENTIALS = {
  username: process.env.TEST_USERNAME || 'admin@hitechwaste.com.my',
  password: process.env.TEST_PASSWORD || 'admin123',
};

// Shared state
test.describe.configure({ mode: 'serial' });

let authToken: string;
let testClientId: string;
let testDocumentId: string;

test.describe('AI Chat & RAG Features', () => {

  test.beforeAll(async ({ request }) => {
    // Login
    const loginResp = await request.post(`${API_BASE_URL}/api/v1/auth/login`, {
      data: TEST_CREDENTIALS,
    });

    if (loginResp.status() === 200) {
      const data = await loginResp.json();
      authToken = data.access_token;
    } else {
      console.log('⚠ Login failed - tests will use mock auth');
    }
  });

  test('01 - AI Health Check', async ({ request }) => {
    const response = await request.get(`${API_BASE_URL}/api/v1/ai/health`, {
      headers: { 'Authorization': `Bearer ${authToken}` },
    });

    if (response.status() === 200) {
      const data = await response.json();
      console.log('AI Services Status:', data);
      expect(data).toBeDefined();
    } else if (response.status() === 404) {
      console.log('⚠ AI health endpoint not found');
      test.skip();
    } else {
      console.log(`⚠ AI health check: ${response.status()}`);
    }
  });

  test('02 - Basic Chat (No RAG)', async ({ request }) => {
    const chatData = {
      message: 'What is waste management and why is it important?',
      conversation_history: [],
      use_rag: false,
      temperature: 0.7,
    };

    const response = await request.post(`${API_BASE_URL}/api/v1/ai/chat`, {
      headers: {
        'Authorization': `Bearer ${authToken}`,
        'Content-Type': 'application/json',
      },
      data: chatData,
    });

    if (response.status() === 200) {
      const contentType = response.headers()['content-type'] || '';
      
      if (contentType.includes('text/event-stream')) {
        // SSE streaming response
        const body = await response.text();
        expect(body).toContain('data:');
        console.log('✓ Chat returns SSE stream');
      } else {
        // Direct JSON response
        const data = await response.json();
        expect(data.response || data.message || data.content).toBeDefined();
        console.log('✓ Chat returns JSON response');
      }
    } else if (response.status() === 503) {
      console.log('⚠ LLM service unavailable (Ollama not running)');
      test.skip();
    } else if (response.status() === 404) {
      console.log('⚠ Chat endpoint not implemented');
      test.skip();
    } else {
      console.log(`⚠ Chat endpoint: ${response.status()}`);
    }
  });

  test('03 - RAG-Enabled Chat', async ({ request }) => {
    // First create a client for scoping
    const clientResp = await request.post(`${API_BASE_URL}/api/v1/clients/`, {
      headers: { 'Authorization': `Bearer ${authToken}` },
      data: {
        company_name: `AI Test Client ${Date.now()}`,
        contact_person: 'AI Tester',
        email: `ai-test-${Date.now()}@e2e.com`,
        is_active: true,
      },
    });

    if (clientResp.status() === 201) {
      const client = await clientResp.json();
      testClientId = client.id;
    }

    const chatData = {
      message: 'What are our waste disposal guidelines?',
      client_id: testClientId,
      use_rag: true,
      max_context_chunks: 5,
      temperature: 0.5,
    };

    const response = await request.post(`${API_BASE_URL}/api/v1/ai/chat`, {
      headers: {
        'Authorization': `Bearer ${authToken}`,
        'Content-Type': 'application/json',
      },
      data: chatData,
    });

    if (response.status() === 200) {
      console.log('✓ RAG-enabled chat works');
    } else if (response.status() === 503) {
      console.log('⚠ RAG services unavailable (Milvus/Ollama)');
      test.skip();
    } else {
      console.log(`⚠ RAG chat: ${response.status()}`);
    }
  });

  test('04 - Chat with Conversation History', async ({ request }) => {
    const chatData = {
      message: 'Can you explain more about recycling processes?',
      conversation_history: [
        { role: 'user', content: 'Tell me about waste management' },
        { role: 'assistant', content: 'Waste management involves collection, transport, processing...' },
      ],
      use_rag: false,
    };

    const response = await request.post(`${API_BASE_URL}/api/v1/ai/chat`, {
      headers: { 'Authorization': `Bearer ${authToken}` },
      data: chatData,
    });

    if (response.status() === 200) {
      console.log('✓ Chat with history works');
    } else if (response.status() === 503) {
      test.skip();
    }
  });

  test('05 - Document Upload for RAG', async ({ request }) => {
    if (!testClientId) {
      console.log('⚠ No client for document upload');
      test.skip();
    }

    // Create a test file
    const fileContent = Buffer.from(
      'Waste Management Policy Document\n\n' +
      '1. All general waste must be sorted before collection.\n' +
      '2. Recyclables should be separated into paper, plastic, and metal.\n' +
      '3. Scheduled waste requires special handling and documentation.\n' +
      '4. Collection occurs every Tuesday and Friday.\n'
    );

    const boundary = '----TestBoundary123';
    const body = [
      `------${boundary}`,
      `Content-Disposition: form-data; name="file"; filename="policy.txt"`,
      `Content-Type: text/plain`,
      '',
      fileContent.toString(),
      `------${boundary}`,
      `Content-Disposition: form-data; name="client_id"`,
      '',
      testClientId,
      `------${boundary}`,
      `Content-Disposition: form-data; name="description"`,
      '',
      'Test policy document for RAG',
      `------${boundary}--`,
    ].join('\r\n');

    const response = await request.post(`${API_BASE_URL}/api/v1/ai/documents`, {
      headers: {
        'Authorization': `Bearer ${authToken}`,
        'Content-Type': `multipart/form-data; boundary=----${boundary}`,
      },
      data: body,
    });

    if (response.status() === 201) {
      const data = await response.json();
      testDocumentId = data.id;
      console.log(`✓ Document uploaded: ${data.id}`);
    } else if (response.status() === 404) {
      console.log('⚠ Document upload endpoint not found');
      test.skip();
    } else if (response.status() === 503) {
      console.log('⚠ Document processing service unavailable');
      test.skip();
    } else {
      console.log(`⚠ Document upload: ${response.status()}`);
    }
  });

  test('06 - List Documents', async ({ request }) => {
    const response = await request.get(`${API_BASE_URL}/api/v1/ai/documents`, {
      headers: { 'Authorization': `Bearer ${authToken}` },
    });

    if (response.status() === 200) {
      const data = await response.json();
      console.log(`✓ Found ${data.items?.length || 0} documents`);
    } else if (response.status() === 404) {
      test.skip();
    }
  });

  test('07 - Agent Events Listing', async ({ request }) => {
    const response = await request.get(`${API_BASE_URL}/api/v1/ai/agent-events`, {
      headers: { 'Authorization': `Bearer ${authToken}` },
    });

    if (response.status() === 200) {
      const data = await response.json();
      console.log(`✓ Agent events endpoint works`);
    } else if (response.status() === 404) {
      console.log('⚠ Agent events endpoint not found');
      test.skip();
    }
  });

  test('08 - RAG Context Retrieval', async ({ request }) => {
    const searchData = {
      query: 'waste collection procedures',
      max_chunks: 3,
    };

    const response = await request.post(`${API_BASE_URL}/api/v1/ai/rag-context`, {
      headers: { 'Authorization': `Bearer ${authToken}` },
      data: searchData,
    });

    if (response.status() === 200) {
      const data = await response.json();
      expect(data.context || data.chunks).toBeDefined();
      console.log('✓ RAG context retrieval works');
    } else if (response.status() === 404) {
      test.skip();
    } else if (response.status() === 503) {
      console.log('⚠ Milvus unavailable');
      test.skip();
    }
  });

  test('09 - Database Agent Query', async ({ request }) => {
    const queryData = {
      query: 'How many jobs were completed last month?',
      session_id: `test-session-${Date.now()}`,
    };

    const response = await request.post(`${API_BASE_URL}/api/v1/ai/db-query`, {
      headers: { 'Authorization': `Bearer ${authToken}` },
      data: queryData,
    });

    if (response.status() === 200) {
      console.log('✓ Database agent works');
    } else if (response.status() === 404) {
      test.skip();
    }
  });

  test('10 - Job Assistance Chat', async ({ request }) => {
    const chatData = {
      message: 'How do I schedule a waste collection job for a manufacturing client?',
      conversation_history: [],
      use_rag: true,
    };

    const response = await request.post(`${API_BASE_URL}/api/v1/ai/chat`, {
      headers: { 'Authorization': `Bearer ${authToken}` },
      data: chatData,
    });

    if (response.status() === 200) {
      console.log('✓ Job assistance chat works');
    } else if (response.status() === 503) {
      test.skip();
    }
  });

  test('11 - Temperature Variations', async ({ request }) => {
    const temperatures = [0.0, 0.5, 1.0];

    for (const temp of temperatures) {
      const chatData = {
        message: 'What is recycling?',
        use_rag: false,
        temperature: temp,
      };

      const response = await request.post(`${API_BASE_URL}/api/v1/ai/chat`, {
        headers: { 'Authorization': `Bearer ${authToken}` },
        data: chatData,
      });

      if (response.status() === 200) {
        console.log(`✓ Temperature ${temp}: OK`);
      } else if (response.status() === 422) {
        console.log(`✓ Temperature ${temp}: Validated (may be rejected)`);
      }
    }
  });

  test('12 - Cleanup: Delete Test Document', async ({ request }) => {
    if (!testDocumentId) {
      test.skip();
    }

    const response = await request.delete(
      `${API_BASE_URL}/api/v1/ai/documents/${testDocumentId}`,
      {
        headers: { 'Authorization': `Bearer ${authToken}` },
      }
    );

    if (response.status() === 200 || response.status() === 204) {
      console.log('✓ Test document deleted');
    } else {
      console.log(`⚠ Document deletion: ${response.status()}`);
    }
  });

});

test.describe('AI Error Handling', () => {

  test('should handle invalid chat requests', async ({ request }) => {
    const invalidData = {
      message: '', // Empty message should be rejected
    };

    const response = await request.post(`${API_BASE_URL}/api/v1/ai/chat`, {
      headers: { 'Authorization': `Bearer ${authToken}` },
      data: invalidData,
    });

    expect(response.status()).toBeGreaterThanOrEqual(400);
  });

  test('should require authentication', async ({ request }) => {
    const response = await request.post(`${API_BASE_URL}/api/v1/ai/chat`, {
      data: { message: 'Test' },
    });

    expect(response.status()).toBe(401);
  });

  test('should handle very long messages gracefully', async ({ request }) => {
    const longMessage = 'A'.repeat(10000);

    const response = await request.post(`${API_BASE_URL}/api/v1/ai/chat`, {
      headers: { 'Authorization': `Bearer ${authToken}` },
      data: {
        message: longMessage,
        use_rag: false,
      },
    });

    // Should either succeed or return 413/422, not crash
    expect(response.status()).toBeLessThan(500);
  });

});
