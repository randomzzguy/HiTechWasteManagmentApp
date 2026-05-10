/**
 * Hi-Tech Waste Management — ESG & Sustainability Module E2E Tests
 *
 * Tests for:
 * - Carbon emission tracking
 * - Waste diversion rate calculations
 * - SDG alignment
 * - ESG report generation
 * - Client and company dashboards
 *
 * Run with: npx playwright test api/esg.spec.ts
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
let testCarbonRecordId: string;
let testReportJobId: string;

test.describe('ESG & Sustainability Module', () => {
  test.beforeAll(async ({ request }) => {
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
          company_name: `ESG Test Client ${Date.now()}`,
          contact_person: 'ESG Manager',
          email: `esg-${Date.now()}@e2e.com`,
          is_active: true,
          sla_diversion_target: 75,
        },
      });

      if (clientResp.status() === 201) {
        const client = await clientResp.json();
        testClientId = client.id;
      }
    }
  });

  // ---------------------------------------------------------------------------
  // Carbon Tracking Tests
  // ---------------------------------------------------------------------------

  test('01 - Create Carbon Record', async ({ request }) => {
    const carbonData = {
      client_id: testClientId,
      scope: 'scope_3',
      category: 'waste_disposal',
      emission_kg_co2e: 1250.5,
      activity_type: 'waste_collection',
      activity_quantity: 5000,
      activity_unit: 'kg',
      emission_factor: 0.25,
      date: new Date().toISOString().split('T')[0],
      notes: 'E2E test carbon record',
    };

    const response = await request.post(`${API_BASE_URL}/api/v1/esg/carbon-records/`, {
      headers: { Authorization: `Bearer ${authToken}` },
      data: carbonData,
    });

    if (response.status() === 201) {
      const data = await response.json();
      expect(data.id).toBeDefined();
      expect(parseFloat(data.emission_kg_co2e as string)).toBe(1250.5);
      testCarbonRecordId = data.id;
      console.log(`✓ Created carbon record: ${data.emission_kg_co2e} kg CO2e`);
    } else if (response.status() === 404) {
      console.log('⚠ Carbon records endpoint not found');
      test.skip();
    }
  });

  test('02 - List Carbon Records with filters', async ({ request }) => {
    const response = await request.get(
      `${API_BASE_URL}/api/v1/esg/carbon-records/?client_id=${testClientId}`,
      {
        headers: { Authorization: `Bearer ${authToken}` },
      }
    );

    if (response.status() === 200) {
      const data = await response.json();
      expect(data.items).toBeDefined();
      console.log(`✓ Found ${data.items.length} carbon records for client`);
    }
  });

  test('03 - Filter Carbon Records by scope', async ({ request }) => {
    const response = await request.get(
      `${API_BASE_URL}/api/v1/esg/carbon-records/?scope=scope_3`,
      {
        headers: { Authorization: `Bearer ${authToken}` },
      }
    );

    if (response.status() === 200) {
      const data = await response.json();
      expect(data.items.every((r: Record<string, unknown>) => r.scope === 'scope_3')).toBe(true);
      console.log(`✓ Scope 3 records: ${data.items.length}`);
    }
  });

  test('04 - Filter Carbon Records by date range', async ({ request }) => {
    const today = new Date();
    const lastMonth = new Date(today.getTime() - 30 * 86400000);

    const response = await request.get(
      `${API_BASE_URL}/api/v1/esg/carbon-records/?date_from=${lastMonth.toISOString().split('T')[0]}&date_to=${today.toISOString().split('T')[0]}`,
      {
        headers: { Authorization: `Bearer ${authToken}` },
      }
    );

    if (response.status() === 200) {
      const data = await response.json();
      console.log(`✓ Carbon records in last 30 days: ${data.items.length}`);
    }
  });

  // ---------------------------------------------------------------------------
  // Diversion Rate Tests
  // ---------------------------------------------------------------------------

  test('05 - Get Diversion Rates', async ({ request }) => {
    const response = await request.get(`${API_BASE_URL}/api/v1/esg/diversion-rates/`, {
      headers: { Authorization: `Bearer ${authToken}` },
    });

    if (response.status() === 200) {
      const data = await response.json();
      expect(Array.isArray(data)).toBe(true);
      console.log(`✓ Diversion rate data points: ${data.length}`);
    }
  });

  test('06 - Get Diversion Rates for client', async ({ request }) => {
    if (!testClientId) {
      test.skip();
    }

    const response = await request.get(
      `${API_BASE_URL}/api/v1/esg/diversion-rates/?client_id=${testClientId}`,
      {
        headers: { Authorization: `Bearer ${authToken}` },
      }
    );

    if (response.status() === 200) {
      const data = await response.json();
      console.log(`✓ Client diversion rate data: ${data.length} entries`);
    }
  });

  test('07 - Get Diversion Rates with granularity', async ({ request }) => {
    const granularities = ['monthly', 'quarterly', 'yearly'];

    for (const granularity of granularities) {
      const response = await request.get(
        `${API_BASE_URL}/api/v1/esg/diversion-rates/?granularity=${granularity}`,
        {
          headers: { Authorization: `Bearer ${authToken}` },
        }
      );

      if (response.status() === 200) {
        console.log(`✓ ${granularity} diversion rates available`);
      }
    }
  });

  // ---------------------------------------------------------------------------
  // SDG Alignment Tests
  // ---------------------------------------------------------------------------

  test('08 - Get SDG Alignment', async ({ request }) => {
    const response = await request.get(`${API_BASE_URL}/api/v1/esg/sdg-alignment/`, {
      headers: { Authorization: `Bearer ${authToken}` },
    });

    if (response.status() === 200) {
      const data = await response.json();
      expect(Array.isArray(data)).toBe(true);

      // Check for relevant SDGs (12: Responsible Consumption, 13: Climate Action)
      const relevantSdgs = data.filter((s: Record<string, unknown>) =>
        [12, 13, 11, 14, 15].includes(s.sdg_number as number)
      );
      console.log(`✓ Relevant SDGs: ${relevantSdgs.length}`);
    }
  });

  test('09 - Get Client-specific SDG Alignment', async ({ request }) => {
    if (!testClientId) {
      test.skip();
    }

    const response = await request.get(
      `${API_BASE_URL}/api/v1/esg/sdg-alignment/?client_id=${testClientId}`,
      {
        headers: { Authorization: `Bearer ${authToken}` },
      }
    );

    if (response.status() === 200) {
      const data = await response.json();
      console.log(`✓ Client SDG alignment: ${data.length} goals`);
    }
  });

  // ---------------------------------------------------------------------------
  // Dashboard Tests
  // ---------------------------------------------------------------------------

  test('10 - Get Company ESG Dashboard', async ({ request }) => {
    const response = await request.get(`${API_BASE_URL}/api/v1/esg/company/dashboard/`, {
      headers: { Authorization: `Bearer ${authToken}` },
    });

    if (response.status() === 200) {
      const data = await response.json();
      console.log('✓ Company ESG dashboard:', {
        total_waste_diverted_kg: data.total_waste_diverted_kg,
        diversion_rate_percent: data.diversion_rate_percent,
        carbon_avoided_kg: data.carbon_avoided_kg,
      });
    }
  });

  test('11 - Get Client ESG Dashboard', async ({ request }) => {
    if (!testClientId) {
      test.skip();
    }

    const response = await request.get(
      `${API_BASE_URL}/api/v1/esg/clients/${testClientId}/dashboard/`,
      {
        headers: { Authorization: `Bearer ${authToken}` },
      }
    );

    if (response.status() === 200) {
      const data = await response.json();
      console.log('✓ Client ESG dashboard retrieved');
    }
  });

  test('12 - Get ESG Dashboard with period filter', async ({ request }) => {
    const today = new Date();
    const lastQuarter = new Date(today.getTime() - 90 * 86400000);

    const response = await request.get(
      `${API_BASE_URL}/api/v1/esg/company/dashboard/?period_start=${lastQuarter.toISOString().split('T')[0]}&period_end=${today.toISOString().split('T')[0]}`,
      {
        headers: { Authorization: `Bearer ${authToken}` },
      }
    );

    if (response.status() === 200) {
      console.log('✓ ESG dashboard with period filter');
    }
  });

  // ---------------------------------------------------------------------------
  // Report Generation Tests
  // ---------------------------------------------------------------------------

  test('13 - Generate ESG Report', async ({ request }) => {
    const reportConfig = {
      report_type: 'sustainability',
      period_start: new Date(Date.now() - 365 * 86400000).toISOString().split('T')[0],
      period_end: new Date().toISOString().split('T')[0],
      include_sections: ['carbon_emissions', 'diversion_rates', 'sdg_alignment'],
      format: 'pdf',
    };

    const response = await request.post(`${API_BASE_URL}/api/v1/esg/reports/generate/`, {
      headers: { Authorization: `Bearer ${authToken}` },
      data: reportConfig,
    });

    if (response.status() === 201 || response.status() === 202) {
      const data = await response.json();
      expect(data.job_id || data.id).toBeDefined();
      testReportJobId = data.job_id || data.id;
      console.log(`✓ Report generation started: ${testReportJobId}`);
    } else if (response.status() === 404) {
      console.log('⚠ Report generation endpoint not found');
    }
  });

  test('14 - Check Report Job status', async ({ request }) => {
    if (!testReportJobId) {
      test.skip();
    }

    // Poll for completion (with timeout)
    let attempts = 0;
    const maxAttempts = 10;

    while (attempts < maxAttempts) {
      const response = await request.get(
        `${API_BASE_URL}/api/v1/esg/reports/${testReportJobId}/`,
        {
          headers: { Authorization: `Bearer ${authToken}` },
        }
      );

      if (response.status() === 200) {
        const data = await response.json();
        console.log(`✓ Report status: ${data.status}`);

        if (data.status === 'completed' || data.status === 'failed') {
          break;
        }
      }

      await new Promise((r) => setTimeout(r, 1000));
      attempts++;
    }
  });

  test('15 - Download ESG Report', async ({ request }) => {
    if (!testReportJobId) {
      test.skip();
    }

    const response = await request.get(
      `${API_BASE_URL}/api/v1/esg/reports/${testReportJobId}/download/`,
      {
        headers: { Authorization: `Bearer ${authToken}` },
      }
    );

    if (response.status() === 200) {
      const contentType = response.headers()['content-type'];
      expect(contentType).toMatch(/application\/(pdf|octet-stream)/);
      console.log('✓ Report downloaded');
    } else if (response.status() === 404 || response.status() === 400) {
      console.log('⚠ Report not ready or not found');
    }
  });
});

// ---------------------------------------------------------------------------
// Error Handling Tests
// ---------------------------------------------------------------------------

test.describe('ESG Error Handling', () => {
  test('should reject invalid scope', async ({ request }) => {
    const response = await request.post(`${API_BASE_URL}/api/v1/esg/carbon-records/`, {
      headers: { Authorization: `Bearer ${authToken}` },
      data: {
        client_id: testClientId,
        scope: 'invalid_scope',
        emission_kg_co2e: 100,
        date: new Date().toISOString().split('T')[0],
      },
    });

    expect(response.status()).toBeGreaterThanOrEqual(400);
  });

  test('should reject negative emissions', async ({ request }) => {
    const response = await request.post(`${API_BASE_URL}/api/v1/esg/carbon-records/`, {
      headers: { Authorization: `Bearer ${authToken}` },
      data: {
        client_id: testClientId,
        scope: 'scope_1',
        emission_kg_co2e: -100,
        date: new Date().toISOString().split('T')[0],
      },
    });

    expect(response.status()).toBeGreaterThanOrEqual(400);
  });

  test('should reject invalid date range', async ({ request }) => {
    const response = await request.get(
      `${API_BASE_URL}/api/v1/esg/diversion-rates/?period_start=2025-12-31&period_end=2025-01-01`,
      {
        headers: { Authorization: `Bearer ${authToken}` },
      }
    );

    // Should either return 400 or empty results
    expect(response.status()).toBeLessThan(500);
  });

  test('should return 404 for non-existent client dashboard', async ({ request }) => {
    const response = await request.get(
      `${API_BASE_URL}/api/v1/esg/clients/00000000-0000-0000-0000-000000000000/dashboard/`,
      {
        headers: { Authorization: `Bearer ${authToken}` },
      }
    );

    expect(response.status()).toBe(404);
  });

  test('should require authentication', async ({ request }) => {
    const response = await request.get(`${API_BASE_URL}/api/v1/esg/carbon-records/`);
    expect(response.status()).toBe(401);
  });
});
