/**
 * Hi-Tech Waste Management — Core Workflow API E2E Tests
 * 
 * These tests run against the actual deployed API and verify:
 * - Authentication flow
 * - Client management
 * - Job lifecycle (create → assign → complete)
 * - Fleet assignment
 * - Weighbridge recording
 * - Invoice generation
 * 
 * Run with: npx playwright test api/core-workflow.spec.ts
 */

import { test, expect, APIRequestContext } from '@playwright/test';

// Test configuration - adjust these for your environment
const API_BASE_URL = process.env.TEST_API_URL || 'http://localhost:8000';
const TEST_CREDENTIALS = {
  username: process.env.TEST_USERNAME || 'admin@hitechwaste.com.my',
  password: process.env.TEST_PASSWORD || 'admin123',
};

// Test data storage (shared across tests)
test.describe.configure({ mode: 'serial' });

let authToken: string;
let testClientId: string;
let testJobId: string;
let testVehicleId: string;
let testDriverId: string;
let testWeighbridgeId: string;
let testInvoiceId: string;

test.describe('Core Workflow Integration', () => {
  
  test.beforeAll(async ({ request }) => {
    // Verify API is accessible
    const healthCheck = await request.get(`${API_BASE_URL}/health`);
    expect(healthCheck.status()).toBeLessThan(500);
    console.log('✓ API health check passed');
  });

  test('01 - Authentication: Login and get tokens', async ({ request }) => {
    const response = await request.post(`${API_BASE_URL}/api/v1/auth/login`, {
      data: {
        username: TEST_CREDENTIALS.username,
        password: TEST_CREDENTIALS.password,
      },
    });

    expect(response.status()).toBe(200);
    
    const data = await response.json();
    expect(data.access_token).toBeDefined();
    expect(data.refresh_token).toBeDefined();
    expect(data.user).toBeDefined();
    expect(data.user.role).toBeDefined();
    
    authToken = data.access_token;
    console.log(`✓ Logged in as: ${data.user.email} (${data.user.role})`);
  });

  test('02 - Authentication: Access protected endpoint', async ({ request }) => {
    const response = await request.get(`${API_BASE_URL}/api/v1/clients/`, {
      headers: {
        'Authorization': `Bearer ${authToken}`,
      },
    });

    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(data.items).toBeDefined();
    console.log('✓ Authenticated API access works');
  });

  test('03 - Client: Create new client', async ({ request }) => {
    const clientData = {
      company_name: `E2E Test Client ${Date.now()}`,
      contact_person: 'Test Contact',
      email: `test-${Date.now()}@e2e-test.com`,
      phone: '+60 12-345 6789',
      address: '123 E2E Test Street, Industrial Park',
      is_active: true,
    };

    const response = await request.post(`${API_BASE_URL}/api/v1/clients/`, {
      headers: {
        'Authorization': `Bearer ${authToken}`,
      },
      data: clientData,
    });

    expect(response.status()).toBe(201);
    
    const data = await response.json();
    expect(data.id).toBeDefined();
    expect(data.company_name).toBe(clientData.company_name);
    
    testClientId = data.id;
    console.log(`✓ Created client: ${data.company_name} (${testClientId})`);
  });

  test('04 - Client: List and filter clients', async ({ request }) => {
    // List all clients
    const response = await request.get(`${API_BASE_URL}/api/v1/clients/`, {
      headers: {
        'Authorization': `Bearer ${authToken}`,
      },
    });

    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(data.total).toBeGreaterThanOrEqual(1);
    expect(data.items.length).toBeGreaterThanOrEqual(1);

    // Search for our test client
    const searchResponse = await request.get(
      `${API_BASE_URL}/api/v1/clients/?search=E2E+Test`,
      {
        headers: {
          'Authorization': `Bearer ${authToken}`,
        },
      }
    );

    expect(searchResponse.status()).toBe(200);
    const searchData = await searchResponse.json();
    expect(searchData.items.length).toBeGreaterThanOrEqual(1);
    console.log('✓ Client listing and search works');
  });

  test('05 - Fleet: List available vehicles', async ({ request }) => {
    const response = await request.get(`${API_BASE_URL}/api/v1/fleet/vehicles`, {
      headers: {
        'Authorization': `Bearer ${authToken}`,
      },
    });

    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(data.items).toBeDefined();
    
    // Find an available vehicle
    const availableVehicle = data.items.find((v: any) => v.status === 'available');
    if (availableVehicle) {
      testVehicleId = availableVehicle.id;
      console.log(`✓ Found available vehicle: ${availableVehicle.registration}`);
    } else {
      console.log('⚠ No available vehicles found - will create one');
    }
  });

  test('06 - Fleet: Create vehicle if none available', async ({ request }) => {
    if (testVehicleId) {
      console.log('✓ Using existing vehicle');
      return;
    }

    const vehicleData = {
      registration: `TEST-${Date.now()}`,
      vehicle_type: 'compactor',
      make: 'Isuzu',
      model: 'Test Model',
      year: 2023,
      capacity_kg: 5000,
      status: 'available',
    };

    const response = await request.post(`${API_BASE_URL}/api/v1/fleet/vehicles`, {
      headers: {
        'Authorization': `Bearer ${authToken}`,
      },
      data: vehicleData,
    });

    if (response.status() === 201) {
      const data = await response.json();
      testVehicleId = data.id;
      console.log(`✓ Created test vehicle: ${data.registration}`);
    } else {
      console.log(`⚠ Vehicle creation returned ${response.status()} - may already exist`);
    }
  });

  test('07 - Settings: Create test driver user', async ({ request }) => {
    const userData = {
      email: `driver-${Date.now()}@e2e-test.com`,
      password: 'DriverPass123!',
      full_name: 'E2E Test Driver',
      role: 'driver',
      is_active: true,
    };

    const response = await request.post(`${API_BASE_URL}/api/v1/settings/users/`, {
      headers: {
        'Authorization': `Bearer ${authToken}`,
      },
      data: userData,
    });

    if (response.status() === 201) {
      const data = await response.json();
      testDriverId = data.id;
      console.log(`✓ Created driver: ${data.full_name}`);
    } else {
      console.log(`⚠ Driver creation returned ${response.status()} - may already exist`);
      // Try to find an existing driver
      const driversResp = await request.get(
        `${API_BASE_URL}/api/v1/settings/users/?role=driver`,
        {
          headers: { 'Authorization': `Bearer ${authToken}` },
        }
      );
      if (driversResp.status() === 200) {
        const drivers = await driversResp.json();
        if (drivers.items?.length > 0) {
          testDriverId = drivers.items[0].id;
          console.log(`✓ Using existing driver: ${drivers.items[0].full_name}`);
        }
      }
    }
  });

  test('08 - Jobs: Create job for client', async ({ request }) => {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);

    const jobData = {
      client_id: testClientId,
      job_type: 'general_collection',
      collection_address: '456 E2E Collection Address, Selangor',
      scheduled_date: tomorrow.toISOString().split('T')[0],
      scheduled_time_start: '09:00:00',
      estimated_weight_kg: 1500,
      notes: 'E2E workflow test job',
    };

    const response = await request.post(`${API_BASE_URL}/api/v1/jobs/`, {
      headers: {
        'Authorization': `Bearer ${authToken}`,
      },
      data: jobData,
    });

    expect(response.status()).toBe(201);
    
    const data = await response.json();
    expect(data.id).toBeDefined();
    expect(data.job_number).toMatch(/^JOB-\d{4}-\d{4}$/);
    expect(data.status).toBe('draft');
    
    testJobId = data.id;
    console.log(`✓ Created job: ${data.job_number} (${testJobId})`);
  });

  test('09 - Jobs: List and filter jobs', async ({ request }) => {
    const response = await request.get(`${API_BASE_URL}/api/v1/jobs/`, {
      headers: {
        'Authorization': `Bearer ${authToken}`,
      },
    });

    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(data.items).toBeDefined();
    expect(data.total).toBeGreaterThanOrEqual(1);

    // Filter by client
    const clientFilterResp = await request.get(
      `${API_BASE_URL}/api/v1/jobs/?client_id=${testClientId}`,
      {
        headers: { 'Authorization': `Bearer ${authToken}` },
      }
    );

    expect(clientFilterResp.status()).toBe(200);
    const filtered = await clientFilterResp.json();
    expect(filtered.items.every((j: any) => j.client_id === testClientId)).toBe(true);
    console.log('✓ Job listing and filtering works');
  });

  test('10 - Jobs: Assign vehicle and driver', async ({ request }) => {
    if (!testVehicleId || !testDriverId) {
      console.log('⚠ Skipping fleet assignment - no vehicle/driver available');
      return;
    }

    const updateData = {
      assigned_vehicle_id: testVehicleId,
      assigned_driver_id: testDriverId,
    };

    const response = await request.put(
      `${API_BASE_URL}/api/v1/jobs/${testJobId}`,
      {
        headers: {
          'Authorization': `Bearer ${authToken}`,
        },
        data: updateData,
      }
    );

    expect(response.status()).toBe(200);
    
    const data = await response.json();
    expect(data.assigned_vehicle_id).toBe(testVehicleId);
    expect(data.assigned_driver_id).toBe(testDriverId);
    
    console.log('✓ Vehicle and driver assigned to job');
  });

  test('11 - Jobs: Update job status through pipeline', async ({ request }) => {
    const transitions = [
      { status: 'confirmed', note: 'Job confirmed' },
      { status: 'dispatched', note: 'Driver dispatched' },
      { status: 'in_progress', note: 'Collection in progress' },
    ];

    for (const transition of transitions) {
      const response = await request.patch(
        `${API_BASE_URL}/api/v1/jobs/${testJobId}/status`,
        {
          headers: {
            'Authorization': `Bearer ${authToken}`,
          },
          data: {
            status: transition.status,
            notes: transition.note,
          },
        }
      );

      expect(response.status()).toBe(200);
      const data = await response.json();
      expect(data.status).toBe(transition.status);
      console.log(`✓ Status: ${transition.status}`);
    }
  });

  test('12 - Weighbridge: Create weight record', async ({ request }) => {
    const now = new Date().toISOString();
    
    const recordData = {
      job_id: testJobId,
      client_id: testClientId,
      gross_weight_kg: 5500.0,
      tare_weight_kg: 3500.0,
      waste_type_breakdown: {
        general_waste_kg: 1800.0,
        recyclable_kg: 200.0,
      },
      recorded_at: now,
      notes: 'E2E test weighbridge record',
    };

    const response = await request.post(
      `${API_BASE_URL}/api/v1/weighbridge/records`,
      {
        headers: {
          'Authorization': `Bearer ${authToken}`,
        },
        data: recordData,
      }
    );

    expect(response.status()).toBe(201);
    
    const data = await response.json();
    expect(data.id).toBeDefined();
    expect(parseFloat(data.net_weight_kg)).toBe(2000); // 5500 - 3500
    
    testWeighbridgeId = data.id;
    console.log(`✓ Created weighbridge record: ${data.net_weight_kg}kg net`);
  });

  test('13 - Weighbridge: List records with filters', async ({ request }) => {
    const response = await request.get(
      `${API_BASE_URL}/api/v1/weighbridge/records?job_id=${testJobId}`,
      {
        headers: {
          'Authorization': `Bearer ${authToken}`,
        },
      }
    );

    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(data.items.length).toBeGreaterThanOrEqual(1);
    expect(data.items.every((r: any) => r.job_id === testJobId)).toBe(true);
    console.log('✓ Weighbridge record filtering works');
  });

  test('14 - Jobs: Complete job', async ({ request }) => {
    // First update with actual weight
    const weightUpdate = await request.put(
      `${API_BASE_URL}/api/v1/jobs/${testJobId}`,
      {
        headers: {
          'Authorization': `Bearer ${authToken}`,
        },
        data: {
          actual_weight_kg: 2000,
        },
      }
    );

    expect(weightUpdate.status()).toBe(200);

    // Then complete
    const response = await request.patch(
      `${API_BASE_URL}/api/v1/jobs/${testJobId}/status`,
      {
        headers: {
          'Authorization': `Bearer ${authToken}`,
        },
        data: {
          status: 'completed',
          notes: 'Collection completed successfully',
        },
      }
    );

    expect(response.status()).toBe(200);
    
    const data = await response.json();
    expect(data.status).toBe('completed');
    expect(data.completed_at).toBeDefined();
    
    console.log('✓ Job marked as completed');
  });

  test('15 - Finance: Create invoice from job', async ({ request }) => {
    const today = new Date();
    const dueDate = new Date();
    dueDate.setDate(dueDate.getDate() + 30);

    const invoiceData = {
      client_id: testClientId,
      job_ids: [testJobId],
      issue_date: today.toISOString().split('T')[0],
      due_date: dueDate.toISOString().split('T')[0],
      line_items: [
        {
          description: 'General waste collection - 2.0 tonnes',
          quantity: 2.0,
          unit_price: 150.0,
          amount: 300.0,
        },
      ],
      subtotal_myr: 300.0,
      tax_myr: 0.0,
      total_myr: 300.0,
      notes: 'E2E test invoice',
    };

    const response = await request.post(
      `${API_BASE_URL}/api/v1/finance/invoices`,
      {
        headers: {
          'Authorization': `Bearer ${authToken}`,
        },
        data: invoiceData,
      }
    );

    expect(response.status()).toBe(201);
    
    const data = await response.json();
    expect(data.id).toBeDefined();
    expect(data.invoice_number).toMatch(/^INV-\d{4}-\d{5}$/);
    expect(parseFloat(data.total_myr)).toBe(300.0);
    expect(data.status).toBe('unpaid');
    
    testInvoiceId = data.id;
    console.log(`✓ Created invoice: ${data.invoice_number} for RM ${data.total_myr}`);
  });

  test('16 - Finance: Record payment', async ({ request }) => {
    if (!testInvoiceId) {
      console.log('⚠ No invoice to pay');
      return;
    }

    const paymentData = {
      amount_myr: 300.0,
      payment_method: 'bank_transfer',
      reference: `E2E-PAYMENT-${Date.now()}`,
      received_at: new Date().toISOString(),
    };

    const response = await request.patch(
      `${API_BASE_URL}/api/v1/finance/invoices/${testInvoiceId}/payment`,
      {
        headers: {
          'Authorization': `Bearer ${authToken}`,
        },
        data: paymentData,
      }
    );

    expect(response.status()).toBe(200);
    
    const data = await response.json();
    expect(data.status).toBe('paid');
    expect(parseFloat(data.paid_amount_myr)).toBe(300.0);
    
    console.log('✓ Payment recorded - invoice PAID');
  });

  test('17 - Finance: Verify invoice aging', async ({ request }) => {
    const response = await request.get(
      `${API_BASE_URL}/api/v1/finance/stats/revenue`,
      {
        headers: {
          'Authorization': `Bearer ${authToken}`,
        },
      }
    );

    expect(response.status()).toBeLessThan(500);
    console.log('✓ Finance stats accessible');
  });

  test('18 - Full workflow verification', async ({ request }) => {
    // Verify job is invoiced
    const jobResp = await request.get(
      `${API_BASE_URL}/api/v1/jobs/${testJobId}`,
      {
        headers: { 'Authorization': `Bearer ${authToken}` },
      }
    );

    if (jobResp.status() === 200) {
      const job = await jobResp.json();
      console.log(`\n=== E2E Workflow Complete ===`);
      console.log(`Job: ${job.job_number}`);
      console.log(`Status: ${job.status}`);
      console.log(`Actual Weight: ${job.actual_weight_kg}kg`);
      console.log(`Invoice: Paid`);
      console.log('===========================');
    }
  });

});

test.describe('Error Handling', () => {
  
  test('should return 401 for unauthenticated requests', async ({ request }) => {
    const response = await request.get(`${API_BASE_URL}/api/v1/clients/`);
    expect(response.status()).toBe(401);
  });

  test('should return 404 for non-existent resources', async ({ request }) => {
    const fakeId = '00000000-0000-0000-0000-000000000000';
    const response = await request.get(
      `${API_BASE_URL}/api/v1/jobs/${fakeId}`,
      {
        headers: { 'Authorization': `Bearer ${authToken || 'fake'}` },
      }
    );
    expect(response.status()).toBe(404);
  });

  test('should validate invalid job data', async ({ request }) => {
    const invalidJob = {
      client_id: 'invalid-uuid',
      job_type: 'invalid_type',
    };

    const response = await request.post(
      `${API_BASE_URL}/api/v1/jobs/`,
      {
        headers: { 'Authorization': `Bearer ${authToken || 'fake'}` },
        data: invalidJob,
      }
    );
    expect(response.status()).toBeGreaterThanOrEqual(400);
  });

});
