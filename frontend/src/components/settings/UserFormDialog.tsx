'use client'

import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation } from '@tanstack/react-query'
import { Loader2, AlertTriangle } from 'lucide-react'
import { toast } from 'sonner'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { settingsApi } from '@/lib/api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface UserRow {
  id: string
  email: string
  full_name: string
  role: string
  is_active: boolean
  created_at: string
}

export interface UserFormDialogProps {
  mode: 'create' | 'edit'
  user?: UserRow | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}

// ---------------------------------------------------------------------------
// Constants
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

const ROLE_LABELS: Record<string, string> = {
  superadmin: 'Super Admin',
  management: 'Management',
  operations_manager: 'Operations Manager',
  field_supervisor: 'Field Supervisor',
  driver: 'Driver',
  compliance_officer: 'Compliance Officer',
  client: 'Client',
}

// ---------------------------------------------------------------------------
// Zod schemas
// ---------------------------------------------------------------------------

const createUserSchema = z.object({
  full_name: z.string().min(1, 'Full name is required').trim(),
  email: z.string().email('Invalid email address'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
  role: z.enum(VALID_ROLES, { required_error: 'Role is required' }),
  is_active: z.boolean(),
})

const editUserSchema = z.object({
  full_name: z.string().min(1, 'Full name is required').trim(),
  email: z.string().email('Invalid email address'),
  password: z
    .string()
    .optional()
    .refine((v) => !v || v.length >= 8, {
      message: 'Password must be at least 8 characters',
    }),
  role: z.enum(VALID_ROLES, { required_error: 'Role is required' }),
  is_active: z.boolean(),
})

type CreateFormValues = z.infer<typeof createUserSchema>
type EditFormValues = z.infer<typeof editUserSchema>
type FormValues = CreateFormValues | EditFormValues

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function UserFormDialog({
  mode,
  user,
  open,
  onOpenChange,
  onSuccess,
}: UserFormDialogProps) {
  const [confirmDeactivate, setConfirmDeactivate] = useState(false)

  const schema = mode === 'create' ? createUserSchema : editUserSchema

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    reset,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      full_name: user?.full_name ?? '',
      email: user?.email ?? '',
      password: '',
      role: (user?.role as typeof VALID_ROLES[number]) ?? 'client',
      is_active: user?.is_active ?? true,
    },
  })

  // Re-populate when user prop changes (switching between rows)
  useEffect(() => {
    if (open) {
      reset({
        full_name: user?.full_name ?? '',
        email: user?.email ?? '',
        password: '',
        role: (user?.role as typeof VALID_ROLES[number]) ?? 'client',
        is_active: user?.is_active ?? true,
      })
      setConfirmDeactivate(false)
    }
  }, [open, user, reset])

  const isActiveValue = watch('is_active')
  const roleValue = watch('role')

  // ---------------------------------------------------------------------------
  // Mutations
  // ---------------------------------------------------------------------------

  const createMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => settingsApi.createUser(data),
    onSuccess: () => {
      toast.success('User created successfully')
      onSuccess()
      onOpenChange(false)
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail
      toast.error(detail ?? 'Failed to create user')
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Record<string, unknown> }) =>
      settingsApi.updateUser(id, data),
    onSuccess: () => {
      toast.success('User updated successfully')
      onSuccess()
      onOpenChange(false)
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail
      toast.error(detail ?? 'Failed to update user')
    },
  })

  const deactivateMutation = useMutation({
    mutationFn: (id: string) => settingsApi.deactivateUser(id),
    onSuccess: () => {
      toast.success('User deactivated')
      onSuccess()
      onOpenChange(false)
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail
      toast.error(detail ?? 'Failed to deactivate user')
    },
  })

  const isPending =
    createMutation.isPending ||
    updateMutation.isPending ||
    deactivateMutation.isPending

  // ---------------------------------------------------------------------------
  // Submit handler
  // ---------------------------------------------------------------------------

  const onSubmit = (values: FormValues) => {
    if (mode === 'create') {
      createMutation.mutate(values as Record<string, unknown>)
    } else if (user) {
      // Diff — only send changed fields
      const changed: Record<string, unknown> = {}
      if (values.full_name !== user.full_name) changed.full_name = values.full_name
      if (values.email !== user.email) changed.email = values.email
      if (values.role !== user.role) changed.role = values.role
      if (values.is_active !== user.is_active) changed.is_active = values.is_active
      const pw = (values as EditFormValues).password
      if (pw && pw.length > 0) changed.password = pw

      if (Object.keys(changed).length === 0) {
        onOpenChange(false)
        return
      }
      updateMutation.mutate({ id: user.id, data: changed })
    }
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-gray-900">
            {mode === 'create' ? 'Add User' : 'Edit User'}
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4 py-2">
          {/* Full Name */}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="full_name" className="text-sm font-medium text-gray-700">
              Full Name
            </Label>
            <Input
              id="full_name"
              autoFocus
              disabled={isPending}
              placeholder="e.g. Ahmad bin Razak"
              {...register('full_name')}
              className="bg-white border-gray-300 text-gray-900 placeholder:text-gray-400"
            />
            {errors.full_name && (
              <p className="text-xs text-red-500">{errors.full_name.message}</p>
            )}
          </div>

          {/* Email */}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="email" className="text-sm font-medium text-gray-700">
              Email
            </Label>
            <Input
              id="email"
              type="email"
              disabled={isPending}
              placeholder="user@hitech.com.my"
              {...register('email')}
              className="bg-white border-gray-300 text-gray-900 placeholder:text-gray-400"
            />
            {errors.email && (
              <p className="text-xs text-red-500">{errors.email.message}</p>
            )}
          </div>

          {/* Password */}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="password" className="text-sm font-medium text-gray-700">
              {mode === 'edit' ? 'New Password (leave blank to keep current)' : 'Password'}
            </Label>
            <Input
              id="password"
              type="password"
              disabled={isPending}
              placeholder={mode === 'edit' ? '••••••••' : 'Min. 8 characters'}
              {...register('password')}
              className="bg-white border-gray-300 text-gray-900 placeholder:text-gray-400"
            />
            {errors.password && (
              <p className="text-xs text-red-500">{errors.password.message}</p>
            )}
          </div>

          {/* Role */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-sm font-medium text-gray-700">Role</Label>
            <Select
              disabled={isPending}
              value={roleValue}
              onValueChange={(v) => setValue('role', v as typeof VALID_ROLES[number], { shouldValidate: true })}
            >
              <SelectTrigger className="bg-white border-gray-300 text-gray-900">
                <SelectValue placeholder="Select a role" />
              </SelectTrigger>
              <SelectContent>
                {VALID_ROLES.map((r) => (
                  <SelectItem key={r} value={r}>
                    {ROLE_LABELS[r]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {errors.role && (
              <p className="text-xs text-red-500">{errors.role.message}</p>
            )}
          </div>

          {/* Active status */}
          <div className="flex items-center justify-between rounded-lg border border-gray-200 bg-gray-50 px-3 py-2.5">
            <div>
              <p className="text-sm font-medium text-gray-700">Active</p>
              <p className="text-xs text-gray-400">User can log in to the platform</p>
            </div>
            <Switch
              disabled={isPending}
              checked={isActiveValue}
              onCheckedChange={(v) => setValue('is_active', v)}
            />
          </div>

          {/* Deactivate action (edit mode, active users only) */}
          {mode === 'edit' && user?.is_active && (
            <div className="border-t border-gray-200 pt-3">
              {!confirmDeactivate ? (
                <button
                  type="button"
                  disabled={isPending}
                  onClick={() => setConfirmDeactivate(true)}
                  className="text-xs text-red-500 hover:text-red-700 hover:underline disabled:opacity-50 transition-colors"
                >
                  Deactivate this user
                </button>
              ) : (
                <div className="flex items-start gap-2 rounded-lg bg-red-50 border border-red-200 p-3">
                  <AlertTriangle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <p className="text-xs font-medium text-red-700 mb-2">
                      Are you sure? This will revoke their access immediately.
                    </p>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        disabled={isPending}
                        onClick={() => deactivateMutation.mutate(user!.id)}
                        className="px-3 py-1 text-xs font-semibold text-white bg-red-600 hover:bg-red-700 rounded disabled:opacity-50 transition-colors"
                      >
                        {deactivateMutation.isPending ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : (
                          'Confirm'
                        )}
                      </button>
                      <button
                        type="button"
                        disabled={isPending}
                        onClick={() => setConfirmDeactivate(false)}
                        className="px-3 py-1 text-xs text-gray-600 hover:text-gray-900 bg-white border border-gray-300 rounded disabled:opacity-50 transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          <DialogFooter className="gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              disabled={isPending}
              onClick={() => onOpenChange(false)}
              className="border-gray-300 text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={isPending}
              className="bg-green-600 hover:bg-green-500 text-white"
            >
              {isPending ? (
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
              ) : null}
              {mode === 'create' ? 'Create User' : 'Save Changes'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
