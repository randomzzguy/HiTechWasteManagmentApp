'use client'

import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import axios from 'axios'

import { settingsApi, labourApi } from '@/lib/api'
import {
  addStaffSchema,
  type AddStaffFormValues,
  buildAddStaffPayload,
  extractErrorMessage,
} from './schemas'

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface AddStaffDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const EMPLOYMENT_TYPE_OPTIONS = [
  { value: 'permanent', label: 'Permanent' },
  { value: 'contract', label: 'Contract' },
  { value: 'foreign_worker', label: 'Foreign Worker' },
] as const

const CONFLICT_MESSAGE = 'A staff profile already exists for this user'

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function AddStaffDialog({ open, onOpenChange, onSuccess }: AddStaffDialogProps) {
  const {
    register,
    handleSubmit,
    setValue,
    watch,
    reset,
    formState: { errors },
  } = useForm<AddStaffFormValues>({
    resolver: zodResolver(addStaffSchema),
    defaultValues: {
      user_id: '',
      employment_type: undefined,
      labour_agent_name: '',
      work_permit_expiry: '',
      notes: '',
    },
  })

  const employmentType = watch('employment_type')

  // Reset work_permit_expiry when employment type changes away from foreign_worker
  useEffect(() => {
    if (employmentType !== 'foreign_worker') {
      setValue('work_permit_expiry', '')
    }
  }, [employmentType, setValue])

  // Users dropdown query — only fetch when dialog is open
  const { data: usersData } = useQuery({
    queryKey: ['users-dropdown'],
    queryFn: () => settingsApi.listUsers({ page_size: 200, is_active: true }),
    staleTime: 5 * 60_000,
    enabled: open,
  })

  const users = usersData?.results ?? []

  // Create staff mutation
  const { mutate, isPending } = useMutation({
    mutationFn: (values: AddStaffFormValues) =>
      labourApi.createStaff(buildAddStaffPayload(values)),
    onSuccess: () => {
      onSuccess()
      onOpenChange(false)
      reset()
    },
    onError: (err) => {
      const is409 = axios.isAxiosError(err) && err.response?.status === 409
      const message = is409
        ? CONFLICT_MESSAGE
        : extractErrorMessage(err, 'An unexpected error occurred')
      toast.error(message)
    },
  })

  const onSubmit = (values: AddStaffFormValues) => mutate(values)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-white border-gray-200 text-gray-800 sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-gray-800">Add Staff</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 mt-2">
          {/* User */}
          <div className="space-y-1.5">
            <Label className="text-gray-700">User *</Label>
            <Select
              onValueChange={(val) => setValue('user_id', val, { shouldValidate: true })}
            >
              <SelectTrigger className="bg-white border-gray-300 text-gray-800">
                <SelectValue placeholder="Select a user…" />
              </SelectTrigger>
              <SelectContent className="bg-white border-gray-200">
                {users.map((u) => {
                  const id = u.id as string
                  const label = (u.full_name as string) || (u.email as string)
                  return (
                    <SelectItem
                      key={id}
                      value={id}
                      className="text-gray-800 focus:bg-gray-100"
                    >
                      {label}
                    </SelectItem>
                  )
                })}
              </SelectContent>
            </Select>
            {errors.user_id && (
              <p className="text-xs text-red-400">{errors.user_id.message}</p>
            )}
          </div>

          {/* Employment Type */}
          <div className="space-y-1.5">
            <Label className="text-gray-700">Employment Type *</Label>
            <Select
              onValueChange={(val) =>
                setValue(
                  'employment_type',
                  val as AddStaffFormValues['employment_type'],
                  { shouldValidate: true }
                )
              }
            >
              <SelectTrigger className="bg-white border-gray-300 text-gray-800">
                <SelectValue placeholder="Select employment type…" />
              </SelectTrigger>
              <SelectContent className="bg-white border-gray-200">
                {EMPLOYMENT_TYPE_OPTIONS.map((opt) => (
                  <SelectItem
                    key={opt.value}
                    value={opt.value}
                    className="text-gray-800 focus:bg-gray-100"
                  >
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {errors.employment_type && (
              <p className="text-xs text-red-400">{errors.employment_type.message}</p>
            )}
          </div>

          {/* Labour Agent Name */}
          <div className="space-y-1.5">
            <Label className="text-gray-700">Labour Agent Name</Label>
            <Input
              {...register('labour_agent_name')}
              placeholder="Optional — max 200 characters"
              className="bg-white border-gray-300 text-gray-800 placeholder:text-gray-400"
            />
            {errors.labour_agent_name && (
              <p className="text-xs text-red-400">{errors.labour_agent_name.message}</p>
            )}
          </div>

          {/* Work Permit Expiry — only shown for foreign_worker */}
          {employmentType === 'foreign_worker' && (
            <div className="space-y-1.5">
              <Label className="text-gray-700">Work Permit Expiry</Label>
              <Input
                {...register('work_permit_expiry')}
                type="date"
                className="bg-white border-gray-300 text-gray-800"
              />
              {errors.work_permit_expiry && (
                <p className="text-xs text-red-400">{errors.work_permit_expiry.message}</p>
              )}
            </div>
          )}

          {/* Notes */}
          <div className="space-y-1.5">
            <Label className="text-gray-700">Notes</Label>
            <Textarea
              {...register('notes')}
              placeholder="Optional notes…"
              rows={3}
              className="bg-white border-gray-300 text-gray-800 placeholder:text-gray-400 resize-none"
            />
            {errors.notes && (
              <p className="text-xs text-red-400">{errors.notes.message}</p>
            )}
          </div>

          {/* Submit */}
          <div className="flex justify-end pt-2">
            <Button
              type="submit"
              disabled={isPending}
              className="bg-emerald-600 hover:bg-emerald-700 text-gray-900"
            >
              {isPending ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Saving…
                </>
              ) : (
                'Save Staff'
              )}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

