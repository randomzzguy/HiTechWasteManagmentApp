/**
 * Unit tests for JobForm component
 *
 * Tests cover:
 * - Form rendering and field presence
 * - Client-side validation
 * - Successful job creation
 * - Error handling
 * - Form reset on close
 */

import React from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// ---------------------------------------------------------------------------
// Mock API modules
// ---------------------------------------------------------------------------

const mockJobsCreate = vi.fn()
const mockClientsList = vi.fn()
const mockVehiclesList = vi.fn()

vi.mock('@/lib/api', () => ({
  jobsApi: {
    create: (...args: unknown[]) => mockJobsCreate(...args),
  },
  clientsApi: {
    list: (...args: unknown[]) => mockClientsList(...args),
  },
  fleetApi: {
    listVehicles: (...args: unknown[]) => mockVehiclesList(...args),
  },
}))

// ---------------------------------------------------------------------------
// Mock sonner toast
// ---------------------------------------------------------------------------

const mockToastSuccess = vi.fn()
const mockToastError = vi.fn()

vi.mock('sonner', () => ({
  toast: {
    success: (...args: unknown[]) => mockToastSuccess(...args),
    error: (...args: unknown[]) => mockToastError(...args),
  },
}))

// ---------------------------------------------------------------------------
// Import component under test
// ---------------------------------------------------------------------------

import JobForm from '../JobForm'

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

const makeQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

function Wrapper({ children }: { children: React.ReactNode }) {
  const qc = makeQueryClient()
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

const defaultProps = {
  open: true,
  onClose: vi.fn(),
  onSuccess: vi.fn(),
}

const mockClients = {
  items: [
    { id: 'client-1', company_name: 'Acme Corp' },
    { id: 'client-2', company_name: 'TechCo Industries' },
  ],
}

const mockVehicles = {
  items: [
    { id: 'vehicle-1', registration: 'ABC123', vehicle_type: 'compactor' },
    { id: 'vehicle-2', registration: 'XYZ789', vehicle_type: 'roll_off' },
  ],
}

function renderJobForm(props: Partial<typeof defaultProps> = {}) {
  const merged = { ...defaultProps, ...props }
  return render(
    <Wrapper>
      <JobForm {...merged} />
    </Wrapper>
  )
}

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks()
  mockClientsList.mockResolvedValue(mockClients)
  mockVehiclesList.mockResolvedValue(mockVehicles)
  mockJobsCreate.mockResolvedValue({ id: 'new-job-id', job_number: 'JOB-2024-0001' })
})

afterEach(() => {
  vi.restoreAllMocks()
})

// ---------------------------------------------------------------------------
// 1. Rendering tests
// ---------------------------------------------------------------------------

describe('JobForm — Rendering', () => {
  it('renders the New Job dialog title', async () => {
    renderJobForm()
    expect(screen.getByText('New Job')).toBeInTheDocument()
  })

  it('renders all required form fields', async () => {
    renderJobForm()
    expect(screen.getByText(/client/i)).toBeInTheDocument()
    expect(screen.getByText(/job type/i)).toBeInTheDocument()
    expect(screen.getByText(/scheduled date/i)).toBeInTheDocument()
    expect(screen.getByText(/collection address/i)).toBeInTheDocument()
  })

  it('renders Cancel and Create Job buttons', () => {
    renderJobForm()
    expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /create job/i })).toBeInTheDocument()
  })

  it('fetches clients when dialog opens', async () => {
    renderJobForm()
    await waitFor(() => {
      expect(mockClientsList).toHaveBeenCalled()
    })
  })

  it('fetches vehicles when dialog opens', async () => {
    renderJobForm()
    await waitFor(() => {
      expect(mockVehiclesList).toHaveBeenCalled()
    })
  })
})

// ---------------------------------------------------------------------------
// 2. Validation tests
// ---------------------------------------------------------------------------

describe('JobForm — Validation', () => {
  it('shows error when client is not selected', async () => {
    renderJobForm()
    await userEvent.click(screen.getByRole('button', { name: /create job/i }))
    await waitFor(() => {
      expect(screen.getByText(/client is required/i)).toBeInTheDocument()
    })
    expect(mockJobsCreate).not.toHaveBeenCalled()
  })

  it('shows error when job type is not selected', async () => {
    renderJobForm()
    // Select a client first
    const clientTrigger = screen.getAllByRole('combobox')[0]
    await userEvent.click(clientTrigger)
    const clientOption = await screen.findByText('Acme Corp')
    await userEvent.click(clientOption)

    await userEvent.click(screen.getByRole('button', { name: /create job/i }))
    await waitFor(() => {
      expect(screen.getByText(/job type is required/i)).toBeInTheDocument()
    })
    expect(mockJobsCreate).not.toHaveBeenCalled()
  })

  it('shows error when scheduled date is empty', async () => {
    renderJobForm()
    // Select client
    const clientTrigger = screen.getAllByRole('combobox')[0]
    await userEvent.click(clientTrigger)
    const clientOption = await screen.findByText('Acme Corp')
    await userEvent.click(clientOption)

    // Select job type
    const jobTypeTrigger = screen.getAllByRole('combobox')[1]
    await userEvent.click(jobTypeTrigger)
    const jobTypeOption = await screen.findByText('General Collection')
    await userEvent.click(jobTypeOption)

    await userEvent.click(screen.getByRole('button', { name: /create job/i }))
    await waitFor(() => {
      expect(screen.getByText(/scheduled date is required/i)).toBeInTheDocument()
    })
    expect(mockJobsCreate).not.toHaveBeenCalled()
  })

  it('shows error when collection address is empty', async () => {
    renderJobForm()
    // Select client
    const clientTrigger = screen.getAllByRole('combobox')[0]
    await userEvent.click(clientTrigger)
    const clientOption = await screen.findByText('Acme Corp')
    await userEvent.click(clientOption)

    // Select job type
    const jobTypeTrigger = screen.getAllByRole('combobox')[1]
    await userEvent.click(jobTypeTrigger)
    const jobTypeOption = await screen.findByText('General Collection')
    await userEvent.click(jobTypeOption)

    // Set date
    const dateInput = screen.getByLabelText(/scheduled date/i) as HTMLInputElement
    await userEvent.type(dateInput, '2025-01-15')

    await userEvent.click(screen.getByRole('button', { name: /create job/i }))
    await waitFor(() => {
      expect(screen.getByText(/collection address is required/i)).toBeInTheDocument()
    })
    expect(mockJobsCreate).not.toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------------------
// 3. Successful submission tests
// ---------------------------------------------------------------------------

describe('JobForm — Successful Submission', () => {
  it('calls jobsApi.create with correct payload', async () => {
    const onSuccess = vi.fn()
    const onClose = vi.fn()
    renderJobForm({ onSuccess, onClose })

    // Select client
    const clientTrigger = screen.getAllByRole('combobox')[0]
    await userEvent.click(clientTrigger)
    const clientOption = await screen.findByText('Acme Corp')
    await userEvent.click(clientOption)

    // Select job type
    const jobTypeTrigger = screen.getAllByRole('combobox')[1]
    await userEvent.click(jobTypeTrigger)
    const jobTypeOption = await screen.findByText('General Collection')
    await userEvent.click(jobTypeOption)

    // Set date
    const dateInput = screen.getByLabelText(/scheduled date/i) as HTMLInputElement
    await userEvent.type(dateInput, '2025-01-15')

    // Set collection address
    const addressInput = screen.getByPlaceholderText(/full collection address/i)
    await userEvent.type(addressInput, '123 Test Street, Kuala Lumpur')

    await userEvent.click(screen.getByRole('button', { name: /create job/i }))

    await waitFor(() => {
      expect(mockJobsCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          client_id: 'client-1',
          job_type: 'general_collection',
          scheduled_date: '2025-01-15',
          collection_address: '123 Test Street, Kuala Lumpur',
        })
      )
    })
  })

  it('shows success toast after creation', async () => {
    renderJobForm()

    // Fill form
    const clientTrigger = screen.getAllByRole('combobox')[0]
    await userEvent.click(clientTrigger)
    await userEvent.click(await screen.findByText('Acme Corp'))

    const jobTypeTrigger = screen.getAllByRole('combobox')[1]
    await userEvent.click(jobTypeTrigger)
    await userEvent.click(await screen.findByText('General Collection'))

    const dateInput = screen.getByLabelText(/scheduled date/i) as HTMLInputElement
    await userEvent.type(dateInput, '2025-01-15')

    const addressInput = screen.getByPlaceholderText(/full collection address/i)
    await userEvent.type(addressInput, '123 Test Street')

    await userEvent.click(screen.getByRole('button', { name: /create job/i }))

    await waitFor(() => {
      expect(mockToastSuccess).toHaveBeenCalledWith(expect.stringContaining('JOB-2024-0001'))
    })
  })

  it('calls onSuccess with job id after creation', async () => {
    const onSuccess = vi.fn()
    renderJobForm({ onSuccess })

    // Fill form
    const clientTrigger = screen.getAllByRole('combobox')[0]
    await userEvent.click(clientTrigger)
    await userEvent.click(await screen.findByText('Acme Corp'))

    const jobTypeTrigger = screen.getAllByRole('combobox')[1]
    await userEvent.click(jobTypeTrigger)
    await userEvent.click(await screen.findByText('General Collection'))

    const dateInput = screen.getByLabelText(/scheduled date/i) as HTMLInputElement
    await userEvent.type(dateInput, '2025-01-15')

    const addressInput = screen.getByPlaceholderText(/full collection address/i)
    await userEvent.type(addressInput, '123 Test Street')

    await userEvent.click(screen.getByRole('button', { name: /create job/i }))

    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalledWith('new-job-id')
    })
  })

  it('includes optional fields when provided', async () => {
    renderJobForm()

    // Required fields
    const clientTrigger = screen.getAllByRole('combobox')[0]
    await userEvent.click(clientTrigger)
    await userEvent.click(await screen.findByText('Acme Corp'))

    const jobTypeTrigger = screen.getAllByRole('combobox')[1]
    await userEvent.click(jobTypeTrigger)
    await userEvent.click(await screen.findByText('General Collection'))

    const dateInput = screen.getByLabelText(/scheduled date/i) as HTMLInputElement
    await userEvent.type(dateInput, '2025-01-15')

    const addressInput = screen.getByPlaceholderText(/full collection address/i)
    await userEvent.type(addressInput, '123 Test Street')

    // Optional: weight
    const weightInput = screen.getByPlaceholderText(/e\.g\. 500/i)
    await userEvent.type(weightInput, '1500')

    // Optional: notes
    const notesInput = screen.getByPlaceholderText(/optional notes/i)
    await userEvent.type(notesInput, 'Test notes for this job')

    await userEvent.click(screen.getByRole('button', { name: /create job/i }))

    await waitFor(() => {
      expect(mockJobsCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          estimated_weight_kg: 1500,
          notes: 'Test notes for this job',
        })
      )
    })
  })
})

// ---------------------------------------------------------------------------
// 4. Error handling tests
// ---------------------------------------------------------------------------

describe('JobForm — Error Handling', () => {
  it('shows error toast when API fails', async () => {
    mockJobsCreate.mockRejectedValueOnce({
      response: { data: { error: { detail: 'Server error occurred' } } },
    })

    renderJobForm()

    // Fill form
    const clientTrigger = screen.getAllByRole('combobox')[0]
    await userEvent.click(clientTrigger)
    await userEvent.click(await screen.findByText('Acme Corp'))

    const jobTypeTrigger = screen.getAllByRole('combobox')[1]
    await userEvent.click(jobTypeTrigger)
    await userEvent.click(await screen.findByText('General Collection'))

    const dateInput = screen.getByLabelText(/scheduled date/i) as HTMLInputElement
    await userEvent.type(dateInput, '2025-01-15')

    const addressInput = screen.getByPlaceholderText(/full collection address/i)
    await userEvent.type(addressInput, '123 Test Street')

    await userEvent.click(screen.getByRole('button', { name: /create job/i }))

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith('Server error occurred')
    })
  })

  it('shows fallback error message when no detail provided', async () => {
    mockJobsCreate.mockRejectedValueOnce(new Error('Network error'))

    renderJobForm()

    // Fill form
    const clientTrigger = screen.getAllByRole('combobox')[0]
    await userEvent.click(clientTrigger)
    await userEvent.click(await screen.findByText('Acme Corp'))

    const jobTypeTrigger = screen.getAllByRole('combobox')[1]
    await userEvent.click(jobTypeTrigger)
    await userEvent.click(await screen.findByText('General Collection'))

    const dateInput = screen.getByLabelText(/scheduled date/i) as HTMLInputElement
    await userEvent.type(dateInput, '2025-01-15')

    const addressInput = screen.getByPlaceholderText(/full collection address/i)
    await userEvent.type(addressInput, '123 Test Street')

    await userEvent.click(screen.getByRole('button', { name: /create job/i }))

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith('Failed to create job')
    })
  })
})

// ---------------------------------------------------------------------------
// 5. Cancel / close behavior tests
// ---------------------------------------------------------------------------

describe('JobForm — Cancel Behavior', () => {
  it('calls onClose when Cancel button is clicked', async () => {
    const onClose = vi.fn()
    renderJobForm({ onClose })

    await userEvent.click(screen.getByRole('button', { name: /cancel/i }))
    expect(onClose).toHaveBeenCalled()
  })

  it('does not call API when Cancel is clicked', async () => {
    renderJobForm()

    // Fill some data
    const addressInput = screen.getByPlaceholderText(/full collection address/i)
    await userEvent.type(addressInput, '123 Test Street')

    await userEvent.click(screen.getByRole('button', { name: /cancel/i }))
    expect(mockJobsCreate).not.toHaveBeenCalled()
  })
})
