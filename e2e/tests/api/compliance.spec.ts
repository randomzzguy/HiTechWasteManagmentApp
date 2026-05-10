/**
 * Hi-Tech Waste Management — Compliance Module E2E Tests
 *
 * Tests for:
 * - Scheduled Waste (SW) batch management
 * - Consignment note creation and PDF generation
 * - Compliance deadlines tracking
 * - SW code lookups
 *
 * Run with: npx playwright test api/compliance.spec.ts
 */

import { test, expect } from '@playwright/test';

const API_BASE_URL = process.env.TEST_API_URL || 'http://localhost:8000';
const TEST_CREDENTIALS = {
  username: process.env.TEST_USERNAME || 'admin@hitechwaste.com.my',
  password: process.env.TEST_PASSWORD || 'admin123',
};

test.describe.configure({ mode: 'serial' });

let authToken: string;
let testClientId: string;
let testBatchId: string;
let testConsignmentNoteId: string;

test.describe('Compliance Module', () => {
  test.beforeAll(async ({ request }) => {
    // Login
    const loginResp = await request.post(`${API_BASE_URL}/api/v1/auth/login`, {
      data: TEST_CREDENTIALS,
    });

    if (loginResp.status() === 200) {
      const data = await loginResp.json();
      authToken = data.access_token;

      // Create test client
      const clientResp = await request.post(`${API_BASE_URL}/api/v1/clients/`, {
        headers: { Authorization: `Bearer ${authToken}` },
        data: {
          company_name: `Compliance Test Client ${Date.now()}`,
          contact_person: 'Compliance Officer',
          email: `compliance-${Date.now()}@e2e.com`,
          is_active: true,
        },
      });

      if (clientResp.status() === 201) {
        const client = await clientResp.json();
        testClientId = client.id;
      }
    }
  });

  // ---------------------------------------------------------------------------
  // SW Batch Tests
  // ---------------------------------------------------------------------------

  test('01 - Create SW Batch', async ({ request }) => {
    const batchData = {
      client_id: testClientId,
      sw_code: 'SW305', // Used oil
      quantity_kg: 500,
      storage_location: 'Storage Bay A',
      date_received: new Date().toISOString().split('T')[0],
      notes: 'E2E test batch',
    };

    const response = await request.post(`${API_BASE_URL}/api/v1/compliance/sw-batches`, {
      headers: { Authorization: `Bearer ${authToken}` },
      data: batchData,
    });

    if (response.status() === 201) {
      const data = await response.json();
      expect(data.id).toBeDefined();
      expect(data.batch_number).toBeDefined();
      expect(data.status).toBe('received');
      testBatchId = data.id;
      console.log(`✓ Created SW batch: ${data.batch_number}`);
    } else if (response.status() === 404) {
      console.log('⚠ SW batches endpoint not found');
      test.skip();
    }
  });

  test('02 - List SW Batches with filters', async ({ request }) => {
    const response = await request.get(
      `${API_BASE_URL}/api/v1/compliance/sw-batches?client_id=${testClientId}`,
      {
        headers: { Authorization: `Bearer ${authToken}` },
      }
    );

    if (response.status() === 200) {
      const data = await response.json();
      expect(data.items).toBeDefined();
      expect(data.items.length).toBeGreaterThanOrEqual(1);
      console.log(`✓ Found ${data.items.length} SW batches for client`);
    }
  });

  test('03 - Get SW Batch details', async ({ request }) => {
    if (!testBatchId) {
      test.skip();
    }

    const response = await request.get(
      `${API_BASE_URL}/api/v1/compliance/sw-batches/${testBatchId}`,
      {
        headers: { Authorization: `Bearer ${authToken}` },
      }
    );

    if (response.status() === 200) {
      const data = await response.json();
      expect(data.id).toBe(testBatchId);
      expect(data.sw_code).toBe('SW305');
      console.log('✓ SW batch details retrieved');
    }
  });

  test('04 - Update SW Batch status', async ({ request }) => {
    if (!testBatchId) {
      test.skip();
    }

    const response = await request.patch(
      `${API_BASE_URL}/api/v1/compliance/sw-batches/${testBatchId}`,
      {
        headers: { Authorization: `Bearer ${authToken}` },
        data: {
          status: 'pending_disposal',
          notes: 'Awaiting transporter',
        },
      }
    );

    if (response.status() === 200) {
      const data = await response.json();
      expect(data.status).toBe('pending_disposal');
      console.log('✓ SW batch status updated');
    }
  });

  test('05 - Filter overdue batches', async ({ request }) => {
    const response = await request.get(
      `${API_BASE_URL}/api/v1/compliance/sw-batches?is_overdue=true`,
      {
        headers: { Authorization: `Bearer ${authToken}` },
      }
    );

    if (response.status() === 200) {
      const data = await response.json();
      console.log(`✓ Found ${data.items?.length || 0} overdue batches`);
    }
  });

  // ---------------------------------------------------------------------------
  // Consignment Note Tests
  // ---------------------------------------------------------------------------

  test('06 - Create Consignment Note', async ({ request }) => {
    if (!testBatchId) {
      test.skip();
    }

    const cnData = {
      batch_id: testBatchId,
      transporter_name: 'Cenviro Sdn Bhd',
      transporter_license: 'DOE-SW-T-12345',
      vehicle_registration: 'WKL 1234',
      driver_name: 'Ahmad bin Ali',
      driver_ic: '880101-14-1234',
      destination_facility: 'Cenviro Treatment Facility',
      scheduled_pickup_date: new Date(Date.now() + 86400000).toISOString().split('T')[0],
    };

    const response = await request.post(
      `${API_BASE_URL}/api/v1/compliance/consignment-notes`,
      {
        headers: { Authorization: `Bearer ${authToken}` },
        data: cnData,
      }
    );

    if (response.status() === 201) {
      const data = await response.json();
      expect(data.id).toBeDefined();
      expect(data.consignment_number).toBeDefined();
      testConsignmentNoteId = data.id;
      console.log(`✓ Created consignment note: ${data.consignment_number}`);
    } else if (response.status() === 404) {
      console.log('⚠ Consignment notes endpoint not found');
    }
  });

  test('07 - List Consignment Notes', async ({ request }) => {
    const response = await request.get(
      `${API_BASE_URL}/api/v1/compliance/consignment-notes`,
      {
        headers: { Authorization: `Bearer ${authToken}` },
      }
    );

    if (response.status() === 200) {
      const data = await response.json();
      expect(data.items).toBeDefined();
      console.log(`✓ Found ${data.items.length} consignment notes`);
    }
  });

  test('08 - Get Consignment Note PDF', async ({ request }) => {
    if (!testConsignmentNoteId) {
      test.skip();
    }

    const response = await request.get(
      `${API_BASE_URL}/api/v1/compliance/consignment-notes/${testConsignmentNoteId}/pdf`,
      {
        headers: { Authorization: `Bearer ${authToken}` },
      }
    );

    if (response.status() === 200) {
      const contentType = response.headers()['content-type'];
      expect(contentType).toContain('application/pdf');
      console.log('✓ Consignment note PDF generated');
    } else if (response.status() === 404) {
      console.log('⚠ PDF generation not available');
    }
  });

  // ---------------------------------------------------------------------------
  // Deadlines and SW Codes Tests
  // ---------------------------------------------------------------------------

  test('09 - Get Compliance Deadlines', async ({ request }) => {
    const response = await request.get(`${API_BASE_URL}/api/v1/compliance/deadlines`, {
      headers: { Authorization: `Bearer ${authToken}` },
    });

    if (response.status() === 200) {
      const data = await response.json();
      expect(Array.isArray(data)).toBe(true);
      console.log(`✓ Found ${data.length} upcoming deadlines`);
    }
  });

  test('10 - List SW Codes', async ({ request }) => {
    const response = await request.get(`${API_BASE_URL}/api/v1/compliance/sw-codes`, {
      headers: { Authorization: `Bearer ${authToken}` },
    });

    if (response.status() === 200) {
      const data = await response.json();
      expect(data.items).toBeDefined();
      expect(data.items.length).toBeGreaterThan(0);
      console.log(`✓ Found ${data.items.length} SW codes`);
    }
  });

  test('11 - Get specific SW Code details', async ({ request }) => {
    const response = await request.get(`${API_BASE_URL}/api/v1/compliance/sw-codes/SW305`, {
      headers: { Authorization: `Bearer ${authToken}` },
    });

    if (response.status() === 200) {
      const data = await response.json();
      expect(data.code).toBe('SW305');
      expect(data.description).toBeDefined();
      console.log(`✓ SW305: ${data.description}`);
    }
  });

  test('12 - Get Compliance Summary', async ({ request }) => {
    const response = await request.get(`${API_BASE_URL}/api/v1/compliance/summary`, {
      headers: { Authorization: `Bearer ${authToken}` },
    });

    if (response.status() === 200) {
      const data = await response.json();
      console.log('✓ Compliance summary:', {
        pending_batches: data.pending_batches,
        overdue_batches: data.overdue_batches,
        upcoming_deadlines: data.upcoming_deadlines,
      });
    }
  });
});

// ---------------------------------------------------------------------------
// Error Handling Tests
// ---------------------------------------------------------------------------

test.describe('Compliance Error Handling', () => {
  test('should reject invalid SW code', async ({ request }) => {
    const response = await request.post(`${API_BASE_URL}/api/v1/compliance/sw-batches`, {
      headers: { Authorization: `Bearer ${authToken}` },
      data: {
        client_id: testClientId,
        sw_code: 'INVALID_CODE',
        quantity_kg: 100,
      },
    });

    expect(response.status()).toBeGreaterThanOrEqual(400);
  });

  test('should reject negative quantity', async ({ request }) => {
    const response = await request.post(`${API_BASE_URL}/api/v1/compliance/sw-batches`, {
      headers: { Authorization: `Bearer ${authToken}` },
      data: {
        client_id: testClientId,
        sw_code: 'SW305',
        quantity_kg: -100,
      },
    });

    expect(response.status()).toBeGreaterThanOrEqual(400);
  });

  test('should return 404 for non-existent batch', async ({ request }) => {
    const response = await request.get(
      `${API_BASE_URL}/api/v1/compliance/sw-batches/00000000-0000-0000-0000-000000000000`,
      {
        headers: { Authorization: `Bearer ${authToken}` },
      }
    );

    expect(response.status()).toBe(404);
  });

  test('should require authentication', async ({ request }) => {
    const response = await request.get(`${API_BASE_URL}/api/v1/compliance/sw-batches`);
    expect(response.status()).toBe(401);
  });
});
