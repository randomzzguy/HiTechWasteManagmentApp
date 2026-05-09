/**
 * Unit tests for UserFormDialog component
 *
 * Requirements covered: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8,
 *                       2.1, 2.3, 2.5, 2.6,
 *                       3.1, 3.2, 3.6,
 *                       4.1, 4.2, 4.3, 4.5, 4.6
 */

import React from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SessionProvider } from 'next-auth/react'

// ---------------------------------------------------------------------------
// Mock next-auth so SessionProvider works without a real server
// ---------------------------------------------------------------------------
vi.mock('next-auth/react', async (importOriginal) => {
  const actual = await importOriginal<typeof import('next-auth/react')>()
  return {
    ...actual,
    SessionProvider: ({ children }: { children: React.ReactNode }) =>
      React.createElement(React.Fragment, null, children),
    useSession: () => ({
      data: {
        user: { id: '1', email: 'admin@test.com', name: 'Admin', role: 'superadmin' },
        access_token: 'test-token',
        expires: '2099-01-01',
      },
      status: 'authenticated',
    }),
  }
})

// ---------------------------------------------------------------------------
// Mock settingsApi
// ---------------------------------------------------------------------------
const mockCreateUser = vi.fn()
const mockUpdateUser = vi.fn()
const mockDeactivateUser = vi.fn()

vi.mock('@/lib/api', () => ({
  settingsApi: {
    createUser: (...args: unknown[]) => mockCreateUser(...args),
    updateUser: (...args: unknown[]) => mockUpdateUser(...args),
    deactivateUser: (...args: unknown[]) => mockDeactivateUser(...args),
  },
}))

// ---------------------------------------------------------------------------
// Mock sonner so we can assert toast calls
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
// Import component under test (after mocks are set up)
// ---------------------------------------------------------------------------
import UserFormDialog, { type UserRow, type UserFormDialogProps } from '../UserFormDialog'

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

const VALID_ROLES = [
  'superadmin',
  'management',
  'operations_manager',
  'field_supervisor',
  'driver',
  'compliance_officer',
  'client',
] as const

const makeQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

interface WrapperProps {
  children: React.ReactNode
}

function Wrapper({ children }: WrapperProps) {
  const qc = makeQueryClient()
  return (
    <QueryClientProvider client={qc}>
      <SessionProvider>{children}</SessionProvider>
    </QueryClientProvider>
  )
}

const defaultCreateProps = {
  mode: 'create' as const,
  user: null,
  open: true,
  onOpenChange: vi.fn(),
  onSuccess: vi.fn(),
}

const sampleUser: UserRow = {
  id: 'user-uuid-123',
  email: 'jane@example.com',
  full_name: 'Jane Doe',
  role: 'driver',
  is_active: true,
  created_at: '2024-01-15T10:00:00Z',
}

function renderDialog(props: Partial<UserFormDialogProps> = {}) {
  const merged = { ...defaultCreateProps, ...props }
  return render(
    <Wrapper>
      <UserFormDialog {...merged} />
    </Wrapper>
  )
}

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks()
  // Default: mutations resolve successfully
  mockCreateUser.mockResolvedValue({ id: 'new-id', email: 'test@test.com' })
  mockUpdateUser.mockResolvedValue({ id: sampleUser.id, email: sampleUser.email })
  mockDeactivateUser.mockResolvedValue(undefined)
})

afterEach(() => {
  vi.restoreAllMocks()
})

// ---------------------------------------------------------------------------
// 1. Create mode — rendering
// ---------------------------------------------------------------------------

describe('Create mode — rendering', () => {
  it('renders the Add User dialog title', () => {
    renderDialog()
    expect(screen.getByText('Add User')).toBeInTheDocument()
  })

  it('renders all required form fields', () => {
    renderDialog()
    expect(screen.getByLabelText(/full name/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/^email$/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument()
    expect(screen.getByText(/role/i)).toBeInTheDocument()
    expect(screen.getByText(/active/i)).toBeInTheDocument()
  })

  it('labels the password field as "Password" in create mode', () => {
    renderDialog()
    expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument()
    expect(screen.queryByText(/leave blank/i)).not.toBeInTheDocument()
  })

  it('renders Cancel and Create User buttons', () => {
    renderDialog()
    expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /create user/i })).toBeInTheDocument()
  })

  it('does NOT render the Deactivate button in create mode', () => {
    renderDialog()
    expect(screen.queryByText(/deactivate/i)).not.toBeInTheDocument()
  })

  it('renders all 7 valid roles in the role select', async () => {
    renderDialog()
    // Open the select — Radix renders options in a portal after opening
    const trigger = screen.getByRole('combobox')
    await userEvent.click(trigger)
    // After opening, listbox items are rendered in the portal
    const listbox = await screen.findByRole('listbox')
    expect(listbox).toBeInTheDocument()
    // Check that all 7 role labels appear somewhere in the document
    const ROLE_LABELS_MAP: Record<string, string> = {
      superadmin: 'Super Admin',
      management: 'Management',
      operations_manager: 'Operations Manager',
      field_supervisor: 'Field Supervisor',
      driver: 'Driver',
      compliance_officer: 'Compliance Officer',
      client: 'Client',
    }
    for (const role of VALID_ROLES) {
      // Use getAllByText since Radix may render the label in multiple places
      expect(screen.getAllByText(ROLE_LABELS_MAP[role]).length).toBeGreaterThan(0)
    }
  })
})

// ---------------------------------------------------------------------------
// 2. Edit mode — rendering and pre-population
// ---------------------------------------------------------------------------

describe('Edit mode — rendering and pre-population', () => {
  it('renders the Edit User dialog title', () => {
    renderDialog({ mode: 'edit', user: sampleUser })
    expect(screen.getByText('Edit User')).toBeInTheDocument()
  })

  it('pre-populates Full Name from user prop', () => {
    renderDialog({ mode: 'edit', user: sampleUser })
    const input = screen.getByLabelText(/full name/i) as HTMLInputElement
    expect(input.value).toBe(sampleUser.full_name)
  })

  it('pre-populates Email from user prop', () => {
    renderDialog({ mode: 'edit', user: sampleUser })
    const input = screen.getByLabelText(/^email$/i) as HTMLInputElement
    expect(input.value).toBe(sampleUser.email)
  })

  it('labels the password field as "New Password (leave blank to keep current)" in edit mode', () => {
    renderDialog({ mode: 'edit', user: sampleUser })
    expect(screen.getByText(/new password \(leave blank to keep current\)/i)).toBeInTheDocument()
  })

  it('renders Save Changes button in edit mode', () => {
    renderDialog({ mode: 'edit', user: sampleUser })
    expect(screen.getByRole('button', { name: /save changes/i })).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// 3. Deactivate button visibility (Requirement 3.1, 3.6)
// ---------------------------------------------------------------------------

describe('Deactivate button visibility', () => {
  it('shows Deactivate button when user is active in edit mode', () => {
    renderDialog({ mode: 'edit', user: { ...sampleUser, is_active: true } })
    expect(screen.getByText(/deactivate this user/i)).toBeInTheDocument()
  })

  it('does NOT show Deactivate button when user is inactive in edit mode', () => {
    renderDialog({ mode: 'edit', user: { ...sampleUser, is_active: false } })
    expect(screen.queryByText(/deactivate this user/i)).not.toBeInTheDocument()
  })

  it('does NOT show Deactivate button in create mode', () => {
    renderDialog({ mode: 'create', user: null })
    expect(screen.queryByText(/deactivate this user/i)).not.toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// 4. Deactivate confirmation flow (Requirement 3.2, 3.3)
// ---------------------------------------------------------------------------

describe('Deactivate confirmation flow', () => {
  it('shows inline confirmation prompt after clicking Deactivate', async () => {
    renderDialog({ mode: 'edit', user: { ...sampleUser, is_active: true } })
    await userEvent.click(screen.getByText(/deactivate this user/i))
    expect(screen.getByText(/are you sure/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /confirm/i })).toBeInTheDocument()
    // There are two Cancel buttons now (dialog footer + confirmation inline)
    expect(screen.getAllByRole('button', { name: /cancel/i })).toHaveLength(2)
  })

  it('hides confirmation prompt when Cancel is clicked in confirmation', async () => {
    renderDialog({ mode: 'edit', user: { ...sampleUser, is_active: true } })
    await userEvent.click(screen.getByText(/deactivate this user/i))
    // There are two Cancel buttons: the inline confirmation one and the dialog footer one
    const allCancelButtons = screen.getAllByRole('button', { name: /cancel/i })
    expect(allCancelButtons).toHaveLength(2)
    // The inline confirmation cancel is the one without the shadcn Button ring-offset-background class
    const inlineConfirmCancel = allCancelButtons.find(
      (btn) => !btn.className.includes('ring-offset-background')
    )!
    await userEvent.click(inlineConfirmCancel)
    expect(screen.queryByText(/are you sure/i)).not.toBeInTheDocument()
    expect(mockDeactivateUser).not.toHaveBeenCalled()
  })

  it('calls deactivateUser with user id on confirm', async () => {
    const onSuccess = vi.fn()
    const onOpenChange = vi.fn()
    renderDialog({
      mode: 'edit',
      user: { ...sampleUser, is_active: true },
      onSuccess,
      onOpenChange,
    })
    await userEvent.click(screen.getByText(/deactivate this user/i))
    await userEvent.click(screen.getByRole('button', { name: /confirm/i }))
    await waitFor(() => {
      expect(mockDeactivateUser).toHaveBeenCalledWith(sampleUser.id)
    })
  })

  it('calls onSuccess and closes dialog after successful deactivation', async () => {
    const onSuccess = vi.fn()
    const onOpenChange = vi.fn()
    renderDialog({
      mode: 'edit',
      user: { ...sampleUser, is_active: true },
      onSuccess,
      onOpenChange,
    })
    await userEvent.click(screen.getByText(/deactivate this user/i))
    await userEvent.click(screen.getByRole('button', { name: /confirm/i }))
    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalled()
      expect(onOpenChange).toHaveBeenCalledWith(false)
    })
  })
})

// ---------------------------------------------------------------------------
// 5. Cancel button closes dialog without API call (Requirement 1.8, 2.6)
// ---------------------------------------------------------------------------

describe('Cancel button behaviour', () => {
  it('calls onOpenChange(false) when Cancel is clicked in create mode', async () => {
    const onOpenChange = vi.fn()
    renderDialog({ onOpenChange })
    await userEvent.click(screen.getByRole('button', { name: /cancel/i }))
    expect(onOpenChange).toHaveBeenCalledWith(false)
    expect(mockCreateUser).not.toHaveBeenCalled()
  })

  it('calls onOpenChange(false) when Cancel is clicked in edit mode', async () => {
    const onOpenChange = vi.fn()
    renderDialog({ mode: 'edit', user: sampleUser, onOpenChange })
    await userEvent.click(screen.getByRole('button', { name: /cancel/i }))
    expect(onOpenChange).toHaveBeenCalledWith(false)
    expect(mockUpdateUser).not.toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------------------
// 6. Client-side validation (Requirement 4.1, 4.2, 4.3, 4.5)
// ---------------------------------------------------------------------------

describe('Client-side validation', () => {
  it('shows validation error and does not submit when Full Name is empty', async () => {
    renderDialog()
    // Clear the full name field and submit
    const fullNameInput = screen.getByLabelText(/full name/i)
    await userEvent.clear(fullNameInput)
    await userEvent.click(screen.getByRole('button', { name: /create user/i }))
    await waitFor(() => {
      expect(screen.getByText(/full name is required/i)).toBeInTheDocument()
    })
    expect(mockCreateUser).not.toHaveBeenCalled()
  })

  it('shows validation error and does not submit when Email is invalid', async () => {
    renderDialog()
    // Fill in full name so it doesn't block submission
    await userEvent.type(screen.getByLabelText(/full name/i), 'Test User')
    // Fill in a valid password so it doesn't block submission
    await userEvent.type(screen.getByLabelText(/^password$/i), 'password123')
    // Leave email empty — an empty string fails z.string().email() validation
    // (jsdom sanitizes type="email" inputs and rejects invalid values,
    // so we test with an empty email which also triggers the Zod email error)
    await userEvent.click(screen.getByRole('button', { name: /create user/i }))
    await waitFor(() => {
      // Zod error message from the schema: 'Invalid email address'
      expect(screen.getByText('Invalid email address')).toBeInTheDocument()
    })
    expect(mockCreateUser).not.toHaveBeenCalled()
  })

  it('shows validation error and does not submit when Password is too short in create mode', async () => {
    renderDialog()
    const fullNameInput = screen.getByLabelText(/full name/i)
    const emailInput = screen.getByLabelText(/^email$/i)
    const passwordInput = screen.getByLabelText(/^password$/i)

    await userEvent.type(fullNameInput, 'Test User')
    await userEvent.type(emailInput, 'test@example.com')
    await userEvent.type(passwordInput, 'short') // < 8 chars
    await userEvent.click(screen.getByRole('button', { name: /create user/i }))
    await waitFor(() => {
      expect(screen.getByText(/at least 8 characters/i)).toBeInTheDocument()
    })
    expect(mockCreateUser).not.toHaveBeenCalled()
  })

  it('shows validation error when new password in edit mode is too short', async () => {
    renderDialog({ mode: 'edit', user: sampleUser })
    const passwordInput = screen.getByLabelText(/new password/i)
    await userEvent.type(passwordInput, 'short') // < 8 chars
    await userEvent.click(screen.getByRole('button', { name: /save changes/i }))
    await waitFor(() => {
      expect(screen.getByText(/at least 8 characters/i)).toBeInTheDocument()
    })
    expect(mockUpdateUser).not.toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------------------
// 7. Successful create submission (Requirement 1.5, 1.6)
// ---------------------------------------------------------------------------

describe('Successful create submission', () => {
  it('calls createUser with form data on valid submission', async () => {
    const onSuccess = vi.fn()
    const onOpenChange = vi.fn()
    renderDialog({ onSuccess, onOpenChange })

    await userEvent.type(screen.getByLabelText(/full name/i), 'Ahmad Razak')
    await userEvent.type(screen.getByLabelText(/^email$/i), 'ahmad@example.com')
    await userEvent.type(screen.getByLabelText(/^password$/i), 'securepass123')

    await userEvent.click(screen.getByRole('button', { name: /create user/i }))

    await waitFor(() => {
      expect(mockCreateUser).toHaveBeenCalledWith(
        expect.objectContaining({
          full_name: 'Ahmad Razak',
          email: 'ahmad@example.com',
          password: 'securepass123',
        })
      )
    })
  })

  it('calls onSuccess and closes dialog after successful create', async () => {
    const onSuccess = vi.fn()
    const onOpenChange = vi.fn()
    renderDialog({ onSuccess, onOpenChange })

    await userEvent.type(screen.getByLabelText(/full name/i), 'Ahmad Razak')
    await userEvent.type(screen.getByLabelText(/^email$/i), 'ahmad@example.com')
    await userEvent.type(screen.getByLabelText(/^password$/i), 'securepass123')
    await userEvent.click(screen.getByRole('button', { name: /create user/i }))

    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalled()
      expect(onOpenChange).toHaveBeenCalledWith(false)
    })
  })

  it('shows success toast after successful create', async () => {
    renderDialog()
    await userEvent.type(screen.getByLabelText(/full name/i), 'Ahmad Razak')
    await userEvent.type(screen.getByLabelText(/^email$/i), 'ahmad@example.com')
    await userEvent.type(screen.getByLabelText(/^password$/i), 'securepass123')
    await userEvent.click(screen.getByRole('button', { name: /create user/i }))

    await waitFor(() => {
      expect(mockToastSuccess).toHaveBeenCalledWith(expect.stringMatching(/created/i))
    })
  })
})

// ---------------------------------------------------------------------------
// 8. Error handling — dialog stays open, error toast shown (Requirement 1.7, 2.5)
// ---------------------------------------------------------------------------

describe('Error handling', () => {
  it('shows error toast and keeps dialog open when createUser fails', async () => {
    const apiError = {
      response: { data: { detail: 'A user with this email already exists.' } },
    }
    mockCreateUser.mockRejectedValueOnce(apiError)

    const onOpenChange = vi.fn()
    renderDialog({ onOpenChange })

    await userEvent.type(screen.getByLabelText(/full name/i), 'Ahmad Razak')
    await userEvent.type(screen.getByLabelText(/^email$/i), 'duplicate@example.com')
    await userEvent.type(screen.getByLabelText(/^password$/i), 'securepass123')
    await userEvent.click(screen.getByRole('button', { name: /create user/i }))

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith('A user with this email already exists.')
    })
    // Dialog should NOT be closed
    expect(onOpenChange).not.toHaveBeenCalledWith(false)
  })

  it('shows error toast and keeps dialog open when updateUser fails', async () => {
    const apiError = {
      response: { data: { detail: 'User not found.' } },
    }
    mockUpdateUser.mockRejectedValueOnce(apiError)

    const onOpenChange = vi.fn()
    renderDialog({ mode: 'edit', user: sampleUser, onOpenChange })

    // Change the full name to trigger a diff
    const fullNameInput = screen.getByLabelText(/full name/i)
    await userEvent.clear(fullNameInput)
    await userEvent.type(fullNameInput, 'New Name')
    await userEvent.click(screen.getByRole('button', { name: /save changes/i }))

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith('User not found.')
    })
    expect(onOpenChange).not.toHaveBeenCalledWith(false)
  })

  it('shows fallback error message when API error has no detail', async () => {
    mockCreateUser.mockRejectedValueOnce(new Error('Network Error'))

    renderDialog()
    await userEvent.type(screen.getByLabelText(/full name/i), 'Ahmad Razak')
    await userEvent.type(screen.getByLabelText(/^email$/i), 'ahmad@example.com')
    await userEvent.type(screen.getByLabelText(/^password$/i), 'securepass123')
    await userEvent.click(screen.getByRole('button', { name: /create user/i }))

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith(expect.stringMatching(/failed|error/i))
    })
  })

  it('shows error toast when deactivateUser fails', async () => {
    const apiError = {
      response: { data: { detail: 'Failed to deactivate user.' } },
    }
    mockDeactivateUser.mockRejectedValueOnce(apiError)

    renderDialog({ mode: 'edit', user: { ...sampleUser, is_active: true } })
    await userEvent.click(screen.getByText(/deactivate this user/i))
    await userEvent.click(screen.getByRole('button', { name: /confirm/i }))

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith('Failed to deactivate user.')
    })
  })
})

// ---------------------------------------------------------------------------
// 9. Loading state — inputs disabled while pending (Requirement 4.6)
// ---------------------------------------------------------------------------

describe('Loading state', () => {
  it('disables inputs and submit button while mutation is pending', async () => {
    // Make createUser hang indefinitely so we can inspect the pending state
    let resolveCreate!: (value: unknown) => void
    mockCreateUser.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveCreate = resolve
      })
    )

    renderDialog()
    await userEvent.type(screen.getByLabelText(/full name/i), 'Ahmad Razak')
    await userEvent.type(screen.getByLabelText(/^email$/i), 'ahmad@example.com')
    await userEvent.type(screen.getByLabelText(/^password$/i), 'securepass123')

    await userEvent.click(screen.getByRole('button', { name: /create user/i }))

    // While pending, inputs should be disabled
    await waitFor(() => {
      expect(screen.getByLabelText(/full name/i)).toBeDisabled()
      expect(screen.getByLabelText(/^email$/i)).toBeDisabled()
      expect(screen.getByLabelText(/^password$/i)).toBeDisabled()
      expect(screen.getByRole('button', { name: /create user/i })).toBeDisabled()
    })

    // Resolve the mutation to clean up
    act(() => resolveCreate({ id: 'new-id' }))
  })
})

// ---------------------------------------------------------------------------
// 10. Edit mode — partial update diff (Requirement 2.3)
// ---------------------------------------------------------------------------

describe('Edit mode — partial update diff', () => {
  it('sends only changed fields to updateUser', async () => {
    renderDialog({ mode: 'edit', user: sampleUser })

    // Only change the full name
    const fullNameInput = screen.getByLabelText(/full name/i)
    await userEvent.clear(fullNameInput)
    await userEvent.type(fullNameInput, 'Jane Smith')

    await userEvent.click(screen.getByRole('button', { name: /save changes/i }))

    await waitFor(() => {
      expect(mockUpdateUser).toHaveBeenCalledWith(
        sampleUser.id,
        expect.objectContaining({ full_name: 'Jane Smith' })
      )
      // Should NOT include email since it wasn't changed
      const callArgs = mockUpdateUser.mock.calls[0][1] as Record<string, unknown>
      expect(callArgs).not.toHaveProperty('email')
    })
  })

  it('omits password from update payload when left blank', async () => {
    renderDialog({ mode: 'edit', user: sampleUser })

    // Change full name but leave password blank
    const fullNameInput = screen.getByLabelText(/full name/i)
    await userEvent.clear(fullNameInput)
    await userEvent.type(fullNameInput, 'Jane Smith')

    await userEvent.click(screen.getByRole('button', { name: /save changes/i }))

    await waitFor(() => {
      const callArgs = mockUpdateUser.mock.calls[0][1] as Record<string, unknown>
      expect(callArgs).not.toHaveProperty('password')
    })
  })

  it('closes dialog without calling updateUser when no fields changed', async () => {
    const onOpenChange = vi.fn()
    renderDialog({ mode: 'edit', user: sampleUser, onOpenChange })

    // Submit without changing anything
    await userEvent.click(screen.getByRole('button', { name: /save changes/i }))

    await waitFor(() => {
      expect(mockUpdateUser).not.toHaveBeenCalled()
      expect(onOpenChange).toHaveBeenCalledWith(false)
    })
  })
})
