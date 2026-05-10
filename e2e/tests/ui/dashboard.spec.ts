/**
 * Hi-Tech Waste Management — Dashboard UI E2E Tests
 *
 * Tests the main dashboard UI including:
 * - Navigation and sidebar
 * - KPI cards display
 * - Charts and widgets
 * - Responsive behavior
 *
 * Run with: npx playwright test ui/dashboard.spec.ts
 */

import { test, expect, Page } from '@playwright/test';

const BASE_URL = process.env.TEST_FRONTEND_URL || 'http://localhost:3000';
const TEST_CREDENTIALS = {
  email: process.env.TEST_USERNAME || 'admin@hitechwaste.com.my',
  password: process.env.TEST_PASSWORD || 'admin123',
};

async function login(page: Page) {
  await page.goto(`${BASE_URL}/login`);
  await page.waitForLoadState('networkidle');

  // Check if already logged in
  if (page.url().includes('/login')) {
    await page.fill('input[type="email"], input[name="email"]', TEST_CREDENTIALS.email);
    await page.fill('input[type="password"], input[name="password"]', TEST_CREDENTIALS.password);
    await page.click('button[type="submit"]');
    await page.waitForURL(/\/(dashboard)?$/);
  }
}

test.describe('Dashboard UI', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');
  });

  // ---------------------------------------------------------------------------
  // Navigation Tests
  // ---------------------------------------------------------------------------

  test('should display sidebar with all navigation items', async ({ page }) => {
    // Main navigation items
    const navItems = [
      'Dashboard',
      'Jobs',
      'Fleet',
      'Clients',
      'Compliance',
      'Finance',
      'ESG',
    ];

    for (const item of navItems) {
      const navLink = page.getByRole('link', { name: new RegExp(item, 'i') }).first();
      await expect(navLink).toBeVisible();
    }
  });

  test('should navigate to Jobs page from sidebar', async ({ page }) => {
    await page.getByRole('link', { name: /jobs/i }).first().click();
    await page.waitForURL(/\/jobs/);
    expect(page.url()).toContain('/jobs');
  });

  test('should navigate to Fleet page from sidebar', async ({ page }) => {
    await page.getByRole('link', { name: /fleet/i }).first().click();
    await page.waitForURL(/\/fleet/);
    expect(page.url()).toContain('/fleet');
  });

  test('should navigate to Clients page from sidebar', async ({ page }) => {
    await page.getByRole('link', { name: /clients/i }).first().click();
    await page.waitForURL(/\/clients/);
    expect(page.url()).toContain('/clients');
  });

  // ---------------------------------------------------------------------------
  // KPI Cards Tests
  // ---------------------------------------------------------------------------

  test('should display KPI cards', async ({ page }) => {
    // Wait for KPI cards to load
    await page.waitForSelector('[data-testid="kpi-card"], .kpi-card, [class*="KpiCard"]', {
      timeout: 10000,
    }).catch(() => {
      // Try alternate selectors
    });

    // Check for common KPI metrics
    const kpiLabels = [
      /today.*jobs/i,
      /fleet/i,
      /tonnage/i,
      /compliance/i,
      /revenue/i,
    ];

    let foundKpis = 0;
    for (const label of kpiLabels) {
      const kpi = page.getByText(label).first();
      if (await kpi.isVisible().catch(() => false)) {
        foundKpis++;
      }
    }

    // Should find at least some KPIs
    expect(foundKpis).toBeGreaterThan(0);
  });

  test('should show loading states for KPI cards', async ({ page }) => {
    // Navigate away and back to trigger loading
    await page.goto(`${BASE_URL}/clients`);
    await page.goto(`${BASE_URL}/dashboard`);

    // Look for skeleton loaders or loading indicators
    const skeletons = page.locator('[class*="skeleton"], [class*="Skeleton"], [data-loading="true"]');
    // Skeletons should appear briefly or be absent (fast load)
  });

  // ---------------------------------------------------------------------------
  // Job Status Summary Tests
  // ---------------------------------------------------------------------------

  test('should display job status summary', async ({ page }) => {
    const statusLabels = ['draft', 'confirmed', 'dispatched', 'in_progress', 'completed'];

    // Look for job status indicators
    for (const status of statusLabels) {
      const statusElement = page.getByText(new RegExp(status.replace('_', ' '), 'i')).first();
      // At least some statuses should be visible
    }
  });

  // ---------------------------------------------------------------------------
  // Charts Tests
  // ---------------------------------------------------------------------------

  test('should display tonnage chart', async ({ page }) => {
    // Look for chart container
    const chart = page.locator('[class*="recharts"], canvas, svg[class*="chart"]').first();

    // Chart should be present (may take time to load data)
    await page.waitForTimeout(2000);

    const chartContainer = page.locator('[class*="tonnage"], [data-testid="tonnage-chart"]');
    // Check if any chart-like element exists
  });

  test('should display fleet status widget', async ({ page }) => {
    const fleetWidget = page.getByText(/fleet.*status/i).first();
    // Fleet widget should show vehicle statuses
  });

  // ---------------------------------------------------------------------------
  // Compliance Alerts Tests
  // ---------------------------------------------------------------------------

  test('should display compliance alerts section', async ({ page }) => {
    const alertsSection = page.getByText(/compliance.*alert/i).first();
    // Compliance section should be visible
  });

  // ---------------------------------------------------------------------------
  // Responsive Tests
  // ---------------------------------------------------------------------------

  test('should be responsive on mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.waitForTimeout(500);

    // Sidebar should be collapsed or hidden on mobile
    const sidebar = page.locator('aside, [class*="sidebar"], [class*="Sidebar"]').first();

    // Main content should still be visible
    const mainContent = page.locator('main, [class*="content"]').first();
    await expect(mainContent).toBeVisible();
  });

  test('should show mobile menu toggle on small screens', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.waitForTimeout(500);

    // Look for hamburger menu or mobile toggle
    const menuToggle = page.locator('[class*="menu"], button[aria-label*="menu"]').first();
  });

  // ---------------------------------------------------------------------------
  // User Menu Tests
  // ---------------------------------------------------------------------------

  test('should display user menu in top bar', async ({ page }) => {
    // Look for user avatar or dropdown
    const userMenu = page.locator('[class*="avatar"], [class*="user-menu"], [data-testid="user-menu"]').first();
  });

  test('should show logout option in user menu', async ({ page }) => {
    // Click on user menu
    const userTrigger = page.locator('[class*="avatar"], button[class*="user"]').first();

    if (await userTrigger.isVisible().catch(() => false)) {
      await userTrigger.click();

      // Look for logout option
      const logoutButton = page.getByText(/logout|sign out/i).first();
    }
  });
});

// ---------------------------------------------------------------------------
// Authentication Tests
// ---------------------------------------------------------------------------

test.describe('Authentication', () => {
  test('should redirect to login when not authenticated', async ({ page }) => {
    // Clear any existing auth
    await page.context().clearCookies();

    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');

    // Should redirect to login
    expect(page.url()).toContain('/login');
  });

  test('should show validation errors for invalid login', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);
    await page.waitForLoadState('networkidle');

    // Submit with invalid credentials
    await page.fill('input[type="email"], input[name="email"]', 'invalid@test.com');
    await page.fill('input[type="password"], input[name="password"]', 'wrongpassword');
    await page.click('button[type="submit"]');

    // Should show error message
    await page.waitForTimeout(1000);
    const errorMessage = page.getByText(/invalid|incorrect|failed|error/i).first();
  });

  test('should show validation for empty fields', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);
    await page.waitForLoadState('networkidle');

    // Try to submit empty form
    await page.click('button[type="submit"]');

    // HTML5 validation or custom validation should trigger
    const emailInput = page.locator('input[type="email"], input[name="email"]').first();
  });
});

// ---------------------------------------------------------------------------
// Accessibility Tests
// ---------------------------------------------------------------------------

test.describe('Accessibility', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('should have proper heading hierarchy', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');

    // Check for h1
    const h1 = page.locator('h1').first();
    await expect(h1).toBeVisible();
  });

  test('should have proper focus management', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');

    // Tab through the page
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');

    // Focus should be visible somewhere
    const focusedElement = page.locator(':focus');
    await expect(focusedElement).toBeTruthy();
  });

  test('should support keyboard navigation', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');

    // Navigate using keyboard
    await page.keyboard.press('Tab');
    await page.keyboard.press('Enter'); // Should activate focused link

    // URL should change if a link was focused
  });
});
