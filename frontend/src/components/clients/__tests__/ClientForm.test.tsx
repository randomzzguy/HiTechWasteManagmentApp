/**
 * Unit tests for ClientForm component
 *
 * Tests cover:
 * - Form rendering and sections
 * - Client-side validation
 * - Waste stream management (add/remove)
 * - Successful client creation
 * - Error handling (including SSM duplicate)
 * - Form reset on close
 */

import React from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// ---------------------------------------------------------------------------
// Mock API modules
// ---------------------------------------------------------------------------

const mockClientsCreate = vi.fn()

vi.mock('@/lib/api', () => ({
  clientsApi: {
    create: (...args: unknown[]) => mockClientsCreate(...args),
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

import ClientForm from '../ClientForm'

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

function renderClientForm(props: Partial<typeof defaultProps> = {}) {
  const merged = { ...defaultProps, ...props }
  return render(
    <Wrapper>
      <ClientForm {...merged} />
    </Wrapper>
  )
}

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks()
  mockClientsCreate.mockResolvedValue({
    id: 'new-client-id',
    company_name: 'Test Company',
  })
})

afterEach(() => {
  vi.restoreAllMocks()
})

// ---------------------------------------------------------------------------
// 1. Rendering tests
// ---------------------------------------------------------------------------

describe('ClientForm — Rendering', () => {
  it('renders the New Client dialog title', () => {
    renderClientForm()
    expect(screen.getByText('New Client')).toBeInTheDocument()
  })

  it('renders Company section', () => {
    renderClientForm()
    expect(screen.getByText(/company name/i)).toBeInTheDocument()
    expect(screen.getByText(/industry/i)).toBeInTheDocument()
    expect(screen.getByText(/ssm number/i)).toBeInTheDocument()
    expect(screen.getByText(/address/i)).toBeInTheDocument()
  })

  it('renders Primary Contact (PIC) section', () => {
    renderClientForm()
    expect(screen.getByText(/primary contact/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/full name/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/email@company.com/i)).toBeInTheDocument()
  })

  it('renders Contract & SLA section', () => {
    renderClientForm()
    expect(screen.getByText(/contract & sla/i)).toBeInTheDocument()
    expect(screen.getByText(/contract start/i)).toBeInTheDocument()
    expect(screen.getByText(/contract end/i)).toBeInTheDocument()
    expect(screen.getByText(/diversion target/i)).toBeInTheDocument()
    expect(screen.getByText(/billing model/i)).toBeInTheDocument()
  })

  it('renders Waste Streams section with Add Stream button', () => {
    renderClientForm()
    expect(screen.getByText(/waste streams/i)).toBeInTheDocument()
    expect(screen.getByText(/add stream/i)).toBeInTheDocument()
  })

  it('renders Cancel and Create Client buttons', () => {
    renderClientForm()
    expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /create client/i })).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// 2. Validation tests
// ---------------------------------------------------------------------------

describe('ClientForm — Validation', () => {
  it('shows error when company name is empty', async () => {
    renderClientForm()
    await userEvent.click(screen.getByRole('button', { name: /create client/i }))
    await waitFor(() => {
      expect(screen.getByText(/company name is required/i)).toBeInTheDocument()
    })
    expect(mockClientsCreate).not.toHaveBeenCalled()
  })

  it('shows error for invalid email format', async () => {
    renderClientForm()

    // Fill company name (required)
    const companyInput = screen.getByPlaceholderText(/unilever/i)
    await userEvent.type(companyInput, 'Test Company')

    // Enter invalid email
    const emailInput = screen.getByPlaceholderText(/email@company.com/i)
    await userEvent.type(emailInput, 'invalid-email')

    await userEvent.click(screen.getByRole('button', { name: /create client/i }))
    await waitFor(() => {
      expect(screen.getByText(/invalid email address/i)).toBeInTheDocument()
    })
    expect(mockClientsCreate).not.toHaveBeenCalled()
  })

  it('shows error for invalid diversion target (>100)', async () => {
    renderClientForm()

    const companyInput = screen.getByPlaceholderText(/unilever/i)
    await userEvent.type(companyInput, 'Test Company')

    const diversionInput = screen.getByPlaceholderText(/e\.g\. 70/i)
    await userEvent.type(diversionInput, '150')

    await userEvent.click(screen.getByRole('button', { name: /create client/i }))
    await waitFor(() => {
      expect(screen.getByText(/must be 0–100/i)).toBeInTheDocument()
    })
    expect(mockClientsCreate).not.toHaveBeenCalled()
  })

  it('shows error for negative diversion target', async () => {
    renderClientForm()

    const companyInput = screen.getByPlaceholderText(/unilever/i)
    await userEvent.type(companyInput, 'Test Company')

    const diversionInput = screen.getByPlaceholderText(/e\.g\. 70/i)
    await userEvent.type(diversionInput, '-10')

    await userEvent.click(screen.getByRole('button', { name: /create client/i }))
    await waitFor(() => {
      expect(screen.getByText(/must be 0–100/i)).toBeInTheDocument()
    })
  })
})

// ---------------------------------------------------------------------------
// 3. Waste stream management tests
// ---------------------------------------------------------------------------

describe('ClientForm — Waste Streams', () => {
  it('adds a waste stream when Add Stream is clicked', async () => {
    renderClientForm()

    await userEvent.click(screen.getByText(/add stream/i))

    // Should see waste stream form fields
    await waitFor(() => {
      expect(screen.getByText(/waste type/i)).toBeInTheDocument()
      expect(screen.getByText(/est\. kg\/month/i)).toBeInTheDocument()
      expect(screen.getByText(/frequency/i)).toBeInTheDocument()
    })
  })

  it('can add multiple waste streams', async () => {
    renderClientForm()

    await userEvent.click(screen.getByText(/add stream/i))
    await userEvent.click(screen.getByText(/add stream/i))

    // Should have 2 waste stream rows
    const wasteTypeLabels = screen.getAllByText(/waste type/i)
    expect(wasteTypeLabels).toHaveLength(2)
  })

  it('removes a waste stream when delete is clicked', async () => {
    renderClientForm()

    await userEvent.click(screen.getByText(/add stream/i))

    // Find and click delete button
    const deleteButtons = screen.getAllByRole('button').filter((btn) =>
      btn.querySelector('svg.lucide-trash-2')
    )
    expect(deleteButtons).toHaveLength(1)

    await userEvent.click(deleteButtons[0])

    // Waste stream should be removed
    await waitFor(() => {
      expect(screen.queryByText(/est\. kg\/month/i)).not.toBeInTheDocument()
    })
  })
})

// ---------------------------------------------------------------------------
// 4. Successful submission tests
// ---------------------------------------------------------------------------

describe('ClientForm — Successful Submission', () => {
  it('calls clientsApi.create with minimal required payload', async () => {
    const onSuccess = vi.fn()
    renderClientForm({ onSuccess })

    const companyInput = screen.getByPlaceholderText(/unilever/i)
    await userEvent.type(companyInput, 'New Client Company')

    await userEvent.click(screen.getByRole('button', { name: /create client/i }))

    await waitFor(() => {
      expect(mockClientsCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          company_name: 'New Client Company',
          is_active: true,
        })
      )
    })
  })

  it('calls clientsApi.create with full payload', async () => {
    renderClientForm()

    // Company info
    await userEvent.type(screen.getByPlaceholderText(/unilever/i), 'Full Test Company')
    await userEvent.type(screen.getByPlaceholderText(/fmcg/i), 'Manufacturing')
    await userEvent.type(screen.getByPlaceholderText(/199001012345/i), 'SSM-12345')
    await userEvent.type(screen.getByPlaceholderText(/street address/i), '123 Main Street')
    await userEvent.type(screen.getByPlaceholderText(/petaling jaya/i), 'Shah Alam')
    await userEvent.type(screen.getByPlaceholderText(/selangor/i), 'Selangor')

    // PIC info
    await userEvent.type(screen.getByPlaceholderText(/full name/i), 'John Doe')
    await userEvent.type(screen.getByPlaceholderText(/email@company.com/i), 'john@test.com')
    await userEvent.type(screen.getByPlaceholderText(/\+60123456789/i), '+60123456789')

    // Contract
    await userEvent.type(screen.getByPlaceholderText(/e\.g\. 70/i), '80')

    await userEvent.click(screen.getByRole('button', { name: /create client/i }))

    await waitFor(() => {
      expect(mockClientsCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          company_name: 'Full Test Company',
          industry_vertical: 'Manufacturing',
          ssm_number: 'SSM-12345',
          address: '123 Main Street',
          city: 'Shah Alam',
          state: 'Selangor',
          pic_name: 'John Doe',
          pic_email: 'john@test.com',
          pic_phone: '+60123456789',
          sla_diversion_target: 80,
        })
      )
    })
  })

  it('includes waste streams in payload', async () => {
    renderClientForm()

    await userEvent.type(screen.getByPlaceholderText(/unilever/i), 'Test Company')

    // Add waste stream
    await userEvent.click(screen.getByText(/add stream/i))

    // Select waste type
    const wasteTypeTriggers = screen.getAllByRole('combobox')
    const wasteTypeTrigger = wasteTypeTriggers.find(
      (el) => el.textContent?.includes('Type') || el.getAttribute('aria-label')?.includes('waste')
    ) || wasteTypeTriggers[wasteTypeTriggers.length - 3]

    await userEvent.click(wasteTypeTrigger)
    const generalWasteOption = await screen.findByText('General Waste')
    await userEvent.click(generalWasteOption)

    await userEvent.click(screen.getByRole('button', { name: /create client/i }))

    await waitFor(() => {
      expect(mockClientsCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          waste_streams: expect.arrayContaining([
            expect.objectContaining({
              waste_type: 'General Waste',
            }),
          ]),
        })
      )
    })
  })

  it('shows success toast after creation', async () => {
    renderClientForm()

    await userEvent.type(screen.getByPlaceholderText(/unilever/i), 'Toast Test Company')
    await userEvent.click(screen.getByRole('button', { name: /create client/i }))

    await waitFor(() => {
      expect(mockToastSuccess).toHaveBeenCalledWith(
        expect.stringContaining('Test Company')
      )
    })
  })

  it('calls onSuccess with client id', async () => {
    const onSuccess = vi.fn()
    renderClientForm({ onSuccess })

    await userEvent.type(screen.getByPlaceholderText(/unilever/i), 'Success Test')
    await userEvent.click(screen.getByRole('button', { name: /create client/i }))

    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalledWith('new-client-id')
    })
  })

  it('calls onClose after successful creation', async () => {
    const onClose = vi.fn()
    renderClientForm({ onClose })

    await userEvent.type(screen.getByPlaceholderText(/unilever/i), 'Close Test')
    await userEvent.click(screen.getByRole('button', { name: /create client/i }))

    await waitFor(() => {
      expect(onClose).toHaveBeenCalled()
    })
  })
})

// ---------------------------------------------------------------------------
// 5. Error handling tests
// ---------------------------------------------------------------------------

describe('ClientForm — Error Handling', () => {
  it('shows field error for duplicate SSM number', async () => {
    mockClientsCreate.mockRejectedValueOnce({
      response: { data: { error: { detail: 'SSM number already exists' } } },
    })

    renderClientForm()

    await userEvent.type(screen.getByPlaceholderText(/unilever/i), 'Test Company')
    await userEvent.type(screen.getByPlaceholderText(/199001012345/i), 'DUPLICATE-SSM')
    await userEvent.click(screen.getByRole('button', { name: /create client/i }))

    await waitFor(() => {
      expect(screen.getByText(/ssm number already exists/i)).toBeInTheDocument()
    })
  })

  it('shows toast for generic API errors', async () => {
    mockClientsCreate.mockRejectedValueOnce({
      response: { data: { error: { detail: 'Server error' } } },
    })

    renderClientForm()

    await userEvent.type(screen.getByPlaceholderText(/unilever/i), 'Test Company')
    await userEvent.click(screen.getByRole('button', { name: /create client/i }))

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith('Server error')
    })
  })

  it('shows fallback error message for unknown errors', async () => {
    mockClientsCreate.mockRejectedValueOnce(new Error('Network error'))

    renderClientForm()

    await userEvent.type(screen.getByPlaceholderText(/unilever/i), 'Test Company')
    await userEvent.click(screen.getByRole('button', { name: /create client/i }))

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith('Failed to create client')
    })
  })
})

// ---------------------------------------------------------------------------
// 6. Cancel / close behavior tests
// ---------------------------------------------------------------------------

describe('ClientForm — Cancel Behavior', () => {
  it('calls onClose when Cancel button is clicked', async () => {
    const onClose = vi.fn()
    renderClientForm({ onClose })

    await userEvent.click(screen.getByRole('button', { name: /cancel/i }))
    expect(onClose).toHaveBeenCalled()
  })

  it('does not call API when Cancel is clicked', async () => {
    renderClientForm()

    await userEvent.type(screen.getByPlaceholderText(/unilever/i), 'Will Cancel')
    await userEvent.click(screen.getByRole('button', { name: /cancel/i }))

    expect(mockClientsCreate).not.toHaveBeenCalled()
  })

  it('resets form when reopened', async () => {
    const { rerender } = renderClientForm()

    await userEvent.type(screen.getByPlaceholderText(/unilever/i), 'Previous Value')

    // Close dialog
    rerender(
      <Wrapper>
        <ClientForm open={false} onClose={vi.fn()} />
      </Wrapper>
    )

    // Reopen dialog
    rerender(
      <Wrapper>
        <ClientForm open={true} onClose={vi.fn()} />
      </Wrapper>
    )

    const input = screen.getByPlaceholderText(/unilever/i) as HTMLInputElement
    expect(input.value).toBe('')
  })
})
