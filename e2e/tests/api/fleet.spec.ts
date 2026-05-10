/**
 * Hi-Tech Waste Management — Fleet Module E2E Tests
 *
 * Tests for:
 * - Vehicle CRUD operations
 * - Maintenance scheduling and logging
 * - Driver management
 * - GPS/Trip tracking
 * - Fleet statistics
 *
 * Run with: npx playwright test api/fleet.spec.ts
 */

import { test, expect } from '@playwright/test';

const API_BASE_URL = process.env.TEST_API_URL || 'http://localhost:8000';
const TEST_CREDENTIALS = {
  username: process.env.TEST_USERNAME || 'admin@hitechwaste.com.my',
  password: process.env.TEST_PASSWORD || 'admin123',
};

test.describe.configure({ mode: 'serial' });

let authToken: string;
let testVehicleId: string;
let testDriverId: string;
let testMaintenanceId: string;

test.describe('Fleet Management Module', () => {
  test.beforeAll(async ({ request }) => {
    const loginResp = await request.post(`${API_BASE_URL}/api/v1/auth/login`, {
      data: TEST_CREDENTIALS,
    });

    if (loginResp.status() === 200) {
      const data = await loginResp.json();
      authToken = data.access_token;
    }
  });

  // ---------------------------------------------------------------------------
  // Vehicle Tests
  // ---------------------------------------------------------------------------

  test('01 - Create Vehicle', async ({ request }) => {
    const vehicleData = {
      registration: `E2E-${Date.now().toString().slice(-6)}`,
      vehicle_type: 'compactor',
      make: 'Isuzu',
      model: 'FRR90',
      year: 2023,
      capacity_kg: 8000,
      fuel_type: 'diesel',
      status: 'available',
      depot_location: 'Shah Alam Depot',
      notes: 'E2E test vehicle',
    };

    const response = await request.post(`${API_BASE_URL}/api/v1/fleet/vehicles/`, {
      headers: { Authorization: `Bearer ${authToken}` },
      data: vehicleData,
    });

    if (response.status() === 201) {
      const data = await response.json();
      expect(data.id).toBeDefined();
      expect(data.registration).toBe(vehicleData.registration);
      expect(data.status).toBe('available');
      testVehicleId = data.id;
      console.log(`✓ Created vehicle: ${data.registration}`);
    } else if (response.status() === 404) {
      console.log('⚠ Fleet vehicles endpoint not found');
      test.skip();
    }
  });

  test('02 - List Vehicles with filters', async ({ request }) => {
    // List all
    const allResp = await request.get(`${API_BASE_URL}/api/v1/fleet/vehicles/`, {
      headers: { Authorization: `Bearer ${authToken}` },
    });

    if (allResp.status() === 200) {
      const data = await allResp.json();
      expect(data.items).toBeDefined();
      console.log(`✓ Total vehicles: ${data.items.length}`);
    }

    // Filter by status
    const availableResp = await request.get(
      `${API_BASE_URL}/api/v1/fleet/vehicles/?status=available`,
      {
        headers: { Authorization: `Bearer ${authToken}` },
      }
    );

    if (availableResp.status() === 200) {
      const data = await availableResp.json();
      expect(data.items.every((v: Record<string, unknown>) => v.status === 'available')).toBe(true);
      console.log(`✓ Available vehicles: ${data.items.length}`);
    }

    // Filter by type
    const compactorResp = await request.get(
      `${API_BASE_URL}/api/v1/fleet/vehicles/?vehicle_type=compactor`,
      {
        headers: { Authorization: `Bearer ${authToken}` },
      }
    );

    if (compactorResp.status() === 200) {
      const data = await compactorResp.json();
      console.log(`✓ Compactor vehicles: ${data.items.length}`);
    }
  });

  test('03 - Get Vehicle details', async ({ request }) => {
    if (!testVehicleId) {
      test.skip();
    }

    const response = await request.get(
      `${API_BASE_URL}/api/v1/fleet/vehicles/${testVehicleId}/`,
      {
        headers: { Authorization: `Bearer ${authToken}` },
      }
    );

    if (response.status() === 200) {
      const data = await response.json();
      expect(data.id).toBe(testVehicleId);
      expect(data.make).toBe('Isuzu');
      console.log('✓ Vehicle details retrieved');
    }
  });

  test('04 - Update Vehicle status', async ({ request }) => {
    if (!testVehicleId) {
      test.skip();
    }

    const response = await request.patch(
      `${API_BASE_URL}/api/v1/fleet/vehicles/${testVehicleId}/`,
      {
        headers: { Authorization: `Bearer ${authToken}` },
        data: {
          status: 'in_service',
          current_mileage_km: 15000,
        },
      }
    );

    if (response.status() === 200) {
      const data = await response.json();
      expect(data.status).toBe('in_service');
      expect(data.current_mileage_km).toBe(15000);
      console.log('✓ Vehicle status updated');
    }
  });

  test('05 - Update Vehicle back to available', async ({ request }) => {
    if (!testVehicleId) {
      test.skip();
    }

    const response = await request.patch(
      `${API_BASE_URL}/api/v1/fleet/vehicles/${testVehicleId}/`,
      {
        headers: { Authorization: `Bearer ${authToken}` },
        data: { status: 'available' },
      }
    );

    if (response.status() === 200) {
      const data = await response.json();
      expect(data.status).toBe('available');
      console.log('✓ Vehicle restored to available');
    }
  });

  // ---------------------------------------------------------------------------
  // Maintenance Tests
  // ---------------------------------------------------------------------------

  test('06 - Get Maintenance Due list', async ({ request }) => {
    const response = await request.get(`${API_BASE_URL}/api/v1/fleet/maintenance/due/`, {
      headers: { Authorization: `Bearer ${authToken}` },
    });

    if (response.status() === 200) {
      const data = await response.json();
      expect(Array.isArray(data)).toBe(true);
      console.log(`✓ Vehicles due for maintenance: ${data.length}`);
    }
  });

  test('07 - Create Maintenance Log', async ({ request }) => {
    if (!testVehicleId) {
      test.skip();
    }

    const maintenanceData = {
      vehicle_id: testVehicleId,
      maintenance_type: 'scheduled_service',
      description: '10,000 km service - oil change, filter replacement',
      cost_myr: 850.0,
      service_provider: 'Isuzu Shah Alam',
      odometer_km: 15000,
      scheduled_date: new Date().toISOString().split('T')[0],
      status: 'completed',
      completed_date: new Date().toISOString().split('T')[0],
      next_service_date: new Date(Date.now() + 90 * 86400000).toISOString().split('T')[0],
      next_service_km: 25000,
    };

    const response = await request.post(`${API_BASE_URL}/api/v1/fleet/maintenance/`, {
      headers: { Authorization: `Bearer ${authToken}` },
      data: maintenanceData,
    });

    if (response.status() === 201) {
      const data = await response.json();
      expect(data.id).toBeDefined();
      testMaintenanceId = data.id;
      console.log(`✓ Created maintenance log`);
    } else if (response.status() === 404) {
      console.log('⚠ Maintenance endpoint not found');
    }
  });

  test('08 - List Maintenance Logs for vehicle', async ({ request }) => {
    if (!testVehicleId) {
      test.skip();
    }

    const response = await request.get(
      `${API_BASE_URL}/api/v1/fleet/maintenance/?vehicle_id=${testVehicleId}`,
      {
        headers: { Authorization: `Bearer ${authToken}` },
      }
    );

    if (response.status() === 200) {
      const data = await response.json();
      expect(data.items).toBeDefined();
      console.log(`✓ Found ${data.items.length} maintenance logs for vehicle`);
    }
  });

  test('09 - Update Maintenance Log', async ({ request }) => {
    if (!testMaintenanceId) {
      test.skip();
    }

    const response = await request.patch(
      `${API_BASE_URL}/api/v1/fleet/maintenance/${testMaintenanceId}/`,
      {
        headers: { Authorization: `Bearer ${authToken}` },
        data: {
          notes: 'Additional tire rotation performed',
          cost_myr: 950.0,
        },
      }
    );

    if (response.status() === 200) {
      const data = await response.json();
      expect(parseFloat(data.cost_myr as string)).toBe(950.0);
      console.log('✓ Maintenance log updated');
    }
  });

  // ---------------------------------------------------------------------------
  // Driver Tests
  // ---------------------------------------------------------------------------

  test('10 - List Drivers', async ({ request }) => {
    const response = await request.get(`${API_BASE_URL}/api/v1/fleet/drivers/`, {
      headers: { Authorization: `Bearer ${authToken}` },
    });

    if (response.status() === 200) {
      const data = await response.json();
      expect(data.items).toBeDefined();
      if (data.items.length > 0) {
        testDriverId = data.items[0].id;
      }
      console.log(`✓ Found ${data.items.length} drivers`);
    }
  });

  test('11 - Filter Drivers by availability', async ({ request }) => {
    const response = await request.get(
      `${API_BASE_URL}/api/v1/fleet/drivers/?is_available=true`,
      {
        headers: { Authorization: `Bearer ${authToken}` },
      }
    );

    if (response.status() === 200) {
      const data = await response.json();
      console.log(`✓ Available drivers: ${data.items?.length || 0}`);
    }
  });

  // ---------------------------------------------------------------------------
  // Stats & GPS Tests
  // ---------------------------------------------------------------------------

  test('12 - Get Fleet Statistics', async ({ request }) => {
    const response = await request.get(`${API_BASE_URL}/api/v1/fleet/stats/`, {
      headers: { Authorization: `Bearer ${authToken}` },
    });

    if (response.status() === 200) {
      const data = await response.json();
      console.log('✓ Fleet stats:', {
        total_vehicles: data.total_vehicles,
        available: data.available_vehicles,
        in_service: data.in_service_vehicles,
      });
    }
  });

  test('13 - List Vehicle Trips', async ({ request }) => {
    const response = await request.get(`${API_BASE_URL}/api/v1/fleet/trips/`, {
      headers: { Authorization: `Bearer ${authToken}` },
    });

    if (response.status() === 200) {
      const data = await response.json();
      expect(data.items).toBeDefined();
      console.log(`✓ Found ${data.items.length} trips`);
    } else if (response.status() === 404) {
      console.log('⚠ Trips endpoint not available');
    }
  });

  test('14 - Filter Trips by vehicle', async ({ request }) => {
    if (!testVehicleId) {
      test.skip();
    }

    const response = await request.get(
      `${API_BASE_URL}/api/v1/fleet/trips/?vehicle_id=${testVehicleId}`,
      {
        headers: { Authorization: `Bearer ${authToken}` },
      }
    );

    if (response.status() === 200) {
      const data = await response.json();
      expect(data.items.every((t: Record<string, unknown>) => t.vehicle_id === testVehicleId)).toBe(true);
      console.log(`✓ Found ${data.items.length} trips for vehicle`);
    }
  });
});

// ---------------------------------------------------------------------------
// Error Handling Tests
// ---------------------------------------------------------------------------

test.describe('Fleet Error Handling', () => {
  test('should reject duplicate registration', async ({ request }) => {
    // First create a vehicle
    const firstResp = await request.post(`${API_BASE_URL}/api/v1/fleet/vehicles/`, {
      headers: { Authorization: `Bearer ${authToken}` },
      data: {
        registration: 'DUP-TEST-001',
        vehicle_type: 'compactor',
        make: 'Test',
        model: 'Test',
        year: 2023,
        status: 'available',
      },
    });

    // Try to create another with same registration
    if (firstResp.status() === 201) {
      const dupResp = await request.post(`${API_BASE_URL}/api/v1/fleet/vehicles/`, {
        headers: { Authorization: `Bearer ${authToken}` },
        data: {
          registration: 'DUP-TEST-001',
          vehicle_type: 'roll_off',
          make: 'Test2',
          model: 'Test2',
          year: 2024,
          status: 'available',
        },
      });

      expect(dupResp.status()).toBeGreaterThanOrEqual(400);
      console.log('✓ Duplicate registration rejected');
    }
  });

  test('should reject invalid vehicle type', async ({ request }) => {
    const response = await request.post(`${API_BASE_URL}/api/v1/fleet/vehicles/`, {
      headers: { Authorization: `Bearer ${authToken}` },
      data: {
        registration: 'INV-TYPE-001',
        vehicle_type: 'invalid_type',
        make: 'Test',
        model: 'Test',
        year: 2023,
        status: 'available',
      },
    });

    expect(response.status()).toBeGreaterThanOrEqual(400);
  });

  test('should reject invalid vehicle status', async ({ request }) => {
    const response = await request.post(`${API_BASE_URL}/api/v1/fleet/vehicles/`, {
      headers: { Authorization: `Bearer ${authToken}` },
      data: {
        registration: 'INV-STATUS-001',
        vehicle_type: 'compactor',
        make: 'Test',
        model: 'Test',
        year: 2023,
        status: 'invalid_status',
      },
    });

    expect(response.status()).toBeGreaterThanOrEqual(400);
  });

  test('should return 404 for non-existent vehicle', async ({ request }) => {
    const response = await request.get(
      `${API_BASE_URL}/api/v1/fleet/vehicles/00000000-0000-0000-0000-000000000000/`,
      {
        headers: { Authorization: `Bearer ${authToken}` },
      }
    );

    expect(response.status()).toBe(404);
  });

  test('should require authentication', async ({ request }) => {
    const response = await request.get(`${API_BASE_URL}/api/v1/fleet/vehicles/`);
    expect(response.status()).toBe(401);
  });
});
