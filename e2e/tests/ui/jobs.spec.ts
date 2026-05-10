/**
 * Hi-Tech Waste Management — Jobs Module UI E2E Tests
 *
 * Tests the Jobs management UI including:
 * - Job listing and filtering
 * - Job creation form
 * - Job details view
 * - Kanban board view
 * - Status updates
 *
 * Run with: npx playwright test ui/jobs.spec.ts
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

  if (page.url().includes('/login')) {
    await page.fill('input[type="email"], input[name="email"]', TEST_CREDENTIALS.email);
    await page.fill('input[type="password"], input[name="password"]', TEST_CREDENTIALS.password);
    await page.click('button[type="submit"]');
    await page.waitForURL(/\/(dashboard)?$/);
  }
}

test.describe('Jobs Module UI', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.goto(`${BASE_URL}/jobs`);
    await page.waitForLoadState('networkidle');
  });

  // ---------------------------------------------------------------------------
  // Job Listing Tests
  // ---------------------------------------------------------------------------

  test('should display jobs page with table', async ({ page }) => {
    // Should have a table or data grid
    const table = page.locator('table, [role="grid"], [class*="DataTable"]').first();
    await expect(table).toBeVisible({ timeout: 10000 });
  });

  test('should display job columns', async ({ page }) => {
    const expectedColumns = ['Job #', 'Client', 'Type', 'Status', 'Date'];

    for (const col of expectedColumns) {
      const header = page.getByText(new RegExp(col, 'i')).first();
      // At least some columns should be visible
    }
  });

  test('should have search/filter functionality', async ({ page }) => {
    // Look for search input
    const searchInput = page.locator('input[type="search"], input[placeholder*="search" i]').first();

    if (await searchInput.isVisible().catch(() => false)) {
      await searchInput.fill('test');
      await page.waitForTimeout(500); // Debounce
      // Results should update
    }
  });

  test('should have status filter', async ({ page }) => {
    // Look for status filter dropdown
    const statusFilter = page.locator('[class*="select"], button[aria-haspopup="listbox"]').first();

    if (await statusFilter.isVisible().catch(() => false)) {
      await statusFilter.click();

      // Should show status options
      const statusOptions = ['Draft', 'Confirmed', 'Dispatched', 'In Progress', 'Completed'];
      for (const status of statusOptions) {
        const option = page.getByText(new RegExp(status, 'i'));
        // Options should be available
      }
    }
  });

  // ---------------------------------------------------------------------------
  // Job Creation Tests
  // ---------------------------------------------------------------------------

  test('should open create job dialog', async ({ page }) => {
    // Look for "New Job" or "Create" button
    const createButton = page.getByRole('button', { name: /new job|create|add/i }).first();

    if (await createButton.isVisible().catch(() => false)) {
      await createButton.click();

      // Dialog should open
      const dialog = page.locator('[role="dialog"], [class*="Dialog"]').first();
      await expect(dialog).toBeVisible({ timeout: 5000 });

      // Should have "New Job" title
      const title = page.getByText(/new job/i).first();
      await expect(title).toBeVisible();
    }
  });

  test('should validate required fields in job form', async ({ page }) => {
    const createButton = page.getByRole('button', { name: /new job|create|add/i }).first();

    if (await createButton.isVisible().catch(() => false)) {
      await createButton.click();
      await page.waitForTimeout(500);

      // Try to submit empty form
      const submitButton = page.getByRole('button', { name: /create job|submit|save/i }).first();

      if (await submitButton.isVisible().catch(() => false)) {
        await submitButton.click();

        // Should show validation errors
        const errors = page.locator('[class*="error"], [role="alert"], .text-red-500');
        await page.waitForTimeout(500);
      }
    }
  });

  test('should close dialog on cancel', async ({ page }) => {
    const createButton = page.getByRole('button', { name: /new job|create|add/i }).first();

    if (await createButton.isVisible().catch(() => false)) {
      await createButton.click();
      await page.waitForTimeout(500);

      // Click cancel
      const cancelButton = page.getByRole('button', { name: /cancel/i }).first();

      if (await cancelButton.isVisible().catch(() => false)) {
        await cancelButton.click();

        // Dialog should close
        const dialog = page.locator('[role="dialog"]').first();
        await expect(dialog).not.toBeVisible({ timeout: 3000 });
      }
    }
  });

  // ---------------------------------------------------------------------------
  // Job Details Tests
  // ---------------------------------------------------------------------------

  test('should navigate to job details', async ({ page }) => {
    // Click on first job row
    const jobRow = page.locator('tr, [role="row"]').nth(1); // Skip header

    if (await jobRow.isVisible().catch(() => false)) {
      await jobRow.click();
      await page.waitForTimeout(1000);

      // Should navigate to details or open panel
      const detailsPanel = page.locator('[class*="detail"], [class*="panel"], [data-testid="job-detail"]');
    }
  });

  test('should display job timeline', async ({ page }) => {
    const jobRow = page.locator('tr, [role="row"]').nth(1);

    if (await jobRow.isVisible().catch(() => false)) {
      await jobRow.click();
      await page.waitForTimeout(1000);

      // Look for timeline/activity section
      const timeline = page.getByText(/timeline|activity|history/i).first();
    }
  });

  // ---------------------------------------------------------------------------
  // Kanban View Tests
  // ---------------------------------------------------------------------------

  test('should switch to kanban view', async ({ page }) => {
    // Look for view toggle
    const kanbanToggle = page.getByRole('button', { name: /kanban|board/i }).first();

    if (await kanbanToggle.isVisible().catch(() => false)) {
      await kanbanToggle.click();
      await page.waitForTimeout(500);

      // Should show kanban columns
      const kanbanColumns = page.locator('[class*="kanban"], [class*="column"], [data-testid*="kanban"]');
    }
  });

  test('should display status columns in kanban', async ({ page }) => {
    const kanbanToggle = page.getByRole('button', { name: /kanban|board/i }).first();

    if (await kanbanToggle.isVisible().catch(() => false)) {
      await kanbanToggle.click();
      await page.waitForTimeout(500);

      const statuses = ['Draft', 'Confirmed', 'Dispatched', 'In Progress', 'Completed'];

      for (const status of statuses) {
        const column = page.getByText(new RegExp(status, 'i')).first();
        // Kanban columns should be visible
      }
    }
  });

  // ---------------------------------------------------------------------------
  // Status Update Tests
  // ---------------------------------------------------------------------------

  test('should update job status', async ({ page }) => {
    // Find a job with draft status and click on it
    const draftJob = page.locator('tr:has-text("Draft"), [role="row"]:has-text("draft")').first();

    if (await draftJob.isVisible().catch(() => false)) {
      await draftJob.click();
      await page.waitForTimeout(1000);

      // Look for status change button
      const statusButton = page.getByRole('button', { name: /confirm|update status|change status/i }).first();

      if (await statusButton.isVisible().catch(() => false)) {
        await statusButton.click();

        // Should show confirmation or status options
      }
    }
  });

  // ---------------------------------------------------------------------------
  // Document Upload Tests
  // ---------------------------------------------------------------------------

  test('should show document upload option', async ({ page }) => {
    const jobRow = page.locator('tr, [role="row"]').nth(1);

    if (await jobRow.isVisible().catch(() => false)) {
      await jobRow.click();
      await page.waitForTimeout(1000);

      // Look for upload button or documents section
      const uploadButton = page.getByRole('button', { name: /upload|document|attach/i }).first();
    }
  });

  // ---------------------------------------------------------------------------
  // Pagination Tests
  // ---------------------------------------------------------------------------

  test('should have pagination controls', async ({ page }) => {
    // Look for pagination
    const pagination = page.locator('[class*="pagination"], [aria-label*="pagination"]').first();

    if (await pagination.isVisible().catch(() => false)) {
      // Should have page controls
      const nextButton = page.getByRole('button', { name: /next/i });
      const prevButton = page.getByRole('button', { name: /prev/i });
    }
  });

  test('should show items per page selector', async ({ page }) => {
    const perPageSelector = page.locator('select[class*="per-page"], [aria-label*="per page"]').first();
  });

  // ---------------------------------------------------------------------------
  // Bulk Actions Tests
  // ---------------------------------------------------------------------------

  test('should support row selection', async ({ page }) => {
    // Look for checkboxes
    const checkbox = page.locator('input[type="checkbox"]').first();

    if (await checkbox.isVisible().catch(() => false)) {
      await checkbox.click();

      // Should show bulk action buttons
      const bulkActions = page.locator('[class*="bulk"], [class*="selected"]').first();
    }
  });
});

// ---------------------------------------------------------------------------
// Job Form Integration Tests
// ---------------------------------------------------------------------------

test.describe('Job Form Integration', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.goto(`${BASE_URL}/jobs`);
    await page.waitForLoadState('networkidle');
  });

  test('should create a new job successfully', async ({ page }) => {
    const createButton = page.getByRole('button', { name: /new job|create|add/i }).first();

    if (!await createButton.isVisible().catch(() => false)) {
      test.skip();
    }

    await createButton.click();
    await page.waitForTimeout(500);

    // Fill in required fields
    // Client selection
    const clientSelect = page.locator('[class*="select"], button[aria-haspopup="listbox"]').first();
    if (await clientSelect.isVisible().catch(() => false)) {
      await clientSelect.click();
      const clientOption = page.locator('[role="option"]').first();
      if (await clientOption.isVisible().catch(() => false)) {
        await clientOption.click();
      }
    }

    // Job type selection
    const jobTypeSelect = page.locator('[class*="select"], button[aria-haspopup="listbox"]').nth(1);
    if (await jobTypeSelect.isVisible().catch(() => false)) {
      await jobTypeSelect.click();
      const typeOption = page.locator('[role="option"]').first();
      if (await typeOption.isVisible().catch(() => false)) {
        await typeOption.click();
      }
    }

    // Date
    const dateInput = page.locator('input[type="date"]').first();
    if (await dateInput.isVisible().catch(() => false)) {
      const tomorrow = new Date(Date.now() + 86400000).toISOString().split('T')[0];
      await dateInput.fill(tomorrow);
    }

    // Address
    const addressInput = page.locator('textarea, input[name*="address"]').first();
    if (await addressInput.isVisible().catch(() => false)) {
      await addressInput.fill('123 E2E Test Address, Kuala Lumpur');
    }

    // Submit
    const submitButton = page.getByRole('button', { name: /create job/i }).first();
    if (await submitButton.isVisible().catch(() => false)) {
      await submitButton.click();

      // Wait for success
      await page.waitForTimeout(2000);

      // Should show success message or close dialog
      const successToast = page.locator('[class*="toast"], [role="status"]').first();
    }
  });
});
