'use client'

import { useState } from 'react'
import { useForm, useFieldArray } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Loader2, X } from 'lucide-react'
import { toast } from 'sonner'
import axios from 'axios'

import { clientsApi, labourApi } from '@/lib/api'
import {
  siteAssignmentSchema,
  type SiteAssignmentFormValues,
  buildSiteAssignmentPayload,
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

interface CreateSiteAssignmentDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ROLE_OPTIONS = [
  { value: 'field_supervisor', label: 'Field Supervisor' },
  { value: 'waste_segregator', label: 'Waste Segregator' },
  { value: 'driver_assistant', label: 'Driver Assistant' },
  { value: 'general_worker', label: 'General Worker' },
] as const

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CreateSiteAssignmentDialog({
  open,
  onOpenChange,
  onSuccess,
}: CreateSiteAssignmentDialogProps) {
  const [pendingStaffId, setPendingStaffId] = useState<string>('')

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    reset,
    control,
    formState: { errors },
  } = useForm<SiteAssignmentFormValues>({
    resolver: zodResolver(siteAssignmentSchema),
    defaultValues: {
      client_id: '',
      site_address: '',
      supervisor_id: '',
      start_date: '',
      end_date: '',
      members: [],
      notes: '',
    },
  })

  const { fields, append, remove } = useFieldArray({ control, name: 'members' })

  // Clients dropdown
  const { data: clientsData } = useQuery({
    queryKey: ['clients-dropdown'],
    queryFn: () => clientsApi.list({ page_size: 200 }),
    staleTime: 5 * 60_000,
    enabled: open,
  })

  // Staff dropdown (used for both supervisor and team members)
  const { data: staffList = [] } = useQuery({
    queryKey: ['staff-dropdown'],
    queryFn: () => labourApi.listStaff(),
    staleTime: 5 * 60_000,
    enabled: open,
  })

  const clients = clientsData?.results ?? []

  // IDs already added as members — filter them out of the picker
  const addedIds = new Set(fields.map((f) => f.staff_profile_id))
  const availableForPicker = staffList.filter((s) => !addedIds.has(s.id))

  // Mutation
  const { mutate, isPending } = useMutation({
    mutationFn: (values: SiteAssignmentFormValues) =>
      labourApi.createSiteAssignment(buildSiteAssignmentPayload(values)),
    onSuccess: () => {
      onSuccess()
      onOpenChange(false)
      reset()
      setPendingStaffId('')
    },
    onError: (err) => {
      const is409 = axios.isAxiosError(err) && err.response?.status === 409
      const message = is409
        ? (axios.isAxiosError(err) && (err.response?.data?.detail ?? err.response?.data?.message)) ||
          'Conflict: overlapping assignment'
        : extractErrorMessage(err, 'An unexpected error occurred')
      toast.error(message as string)
    },
  })

  const onSubmit = (values: SiteAssignmentFormValues) => mutate(values)

  function handleAddMember() {
    if (!pendingStaffId) return
    append({ staff_profile_id: pendingStaffId, role_at_site: 'general_worker' })
    setPendingStaffId('')
  }

  // Helper to get display name for a staff profile
  function staffName(s: unknown): string {
    const staff = s as { user?: { full_name?: string; email?: string }; id?: string }
    return staff?.user?.full_name ?? staff?.user?.email ?? staff?.id?.slice(0, 8) ?? '—'
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-white border-gray-200 text-gray-800 sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="text-gray-800">Create Site Assignment</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)}>
          <div className="overflow-y-auto max-h-[70vh] space-y-4 pr-1 mt-2">

            {/* Client */}
            <div className="space-y-1.5">
              <Label className="text-gray-700">Client *</Label>
              <Select
                onValueChange={(val) => setValue('client_id', val, { shouldValidate: true })}
              >
                <SelectTrigger className="bg-white border-gray-300 text-gray-800">
                  <SelectValue placeholder="Select a client…" />
                </SelectTrigger>
                <SelectContent className="bg-white border-gray-200">
                  {clients.map((c) => {
                    const id = c.id as string
                    const label = (c.company_name as string) || (c.name as string) || id
                    return (
                      <SelectItem key={id} value={id} className="text-gray-800 focus:bg-gray-100">
                        {label}
                      </SelectItem>
                    )
                  })}
                </SelectContent>
              </Select>
              {errors.client_id && (
                <p className="text-xs text-red-400">{errors.client_id.message}</p>
              )}
            </div>

            {/* Site Address */}
            <div className="space-y-1.5">
              <Label className="text-gray-700">Site Address *</Label>
              <Input
                {...register('site_address')}
                placeholder="Enter site address…"
                className="bg-white border-gray-300 text-gray-800 placeholder:text-gray-400"
              />
              {errors.site_address && (
                <p className="text-xs text-red-400">{errors.site_address.message}</p>
              )}
            </div>

            {/* Supervisor */}
            <div className="space-y-1.5">
              <Label className="text-gray-700">Supervisor *</Label>
              <Select
                onValueChange={(val) => setValue('supervisor_id', val, { shouldValidate: true })}
              >
                <SelectTrigger className="bg-white border-gray-300 text-gray-800">
                  <SelectValue placeholder="Select a supervisor…" />
                </SelectTrigger>
                <SelectContent className="bg-white border-gray-200">
                  {staffList.map((s) => (
                    <SelectItem key={s.id} value={s.id} className="text-gray-800 focus:bg-gray-100">
                      {staffName(s)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {errors.supervisor_id && (
                <p className="text-xs text-red-400">{errors.supervisor_id.message}</p>
              )}
            </div>

            {/* Start Date */}
            <div className="space-y-1.5">
              <Label className="text-gray-700">Start Date *</Label>
              <Input
                {...register('start_date')}
                type="date"
                className="bg-white border-gray-300 text-gray-800"
              />
              {errors.start_date && (
                <p className="text-xs text-red-400">{errors.start_date.message}</p>
              )}
            </div>

            {/* End Date */}
            <div className="space-y-1.5">
              <Label className="text-gray-700">End Date</Label>
              <Input
                {...register('end_date')}
                type="date"
                className="bg-white border-gray-300 text-gray-800"
              />
              {errors.end_date && (
                <p className="text-xs text-red-400">{errors.end_date.message}</p>
              )}
            </div>

            {/* Team Members */}
            <div className="space-y-2">
              <Label className="text-gray-700">Team Members *</Label>

              {/* Picker row */}
              <div className="flex gap-2">
                <Select value={pendingStaffId} onValueChange={setPendingStaffId}>
                  <SelectTrigger className="bg-white border-gray-300 text-gray-800 flex-1">
                    <SelectValue placeholder="Select staff member…" />
                  </SelectTrigger>
                  <SelectContent className="bg-white border-gray-200">
                    {availableForPicker.map((s) => (
                      <SelectItem key={s.id} value={s.id} className="text-gray-800 focus:bg-gray-100">
                        {staffName(s)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  type="button"
                  onClick={handleAddMember}
                  disabled={!pendingStaffId}
                  className="bg-gray-100 hover:bg-slate-600 text-gray-800 shrink-0"
                >
                  Add Member
                </Button>
              </div>

              {/* Added members list */}
              {fields.length > 0 && (
                <div className="space-y-2 mt-1">
                  {fields.map((field, index) => {
                    const staffMember = staffList.find((s) => s.id === field.staff_profile_id)
                    return (
                      <div
                        key={field.id}
                        className="flex items-center gap-2 p-2 rounded-md bg-white border border-gray-200"
                      >
                        <span className="text-sm text-gray-700 flex-1 truncate">
                          {staffMember ? staffName(staffMember) : field.staff_profile_id.slice(0, 8)}
                        </span>
                        <Select
                          defaultValue={field.role_at_site}
                          onValueChange={(val) =>
                            setValue(
                              `members.${index}.role_at_site`,
                              val as SiteAssignmentFormValues['members'][number]['role_at_site'],
                              { shouldValidate: true }
                            )
                          }
                        >
                          <SelectTrigger className="bg-white border-gray-300 text-gray-800 w-44 shrink-0">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent className="bg-white border-gray-200">
                            {ROLE_OPTIONS.map((opt) => (
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
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          onClick={() => remove(index)}
                          className="text-gray-500 hover:text-red-400 hover:bg-transparent shrink-0 h-7 w-7"
                        >
                          <X className="w-4 h-4" />
                        </Button>
                      </div>
                    )
                  })}
                </div>
              )}

              {/* Members array error */}
              {errors.members && !Array.isArray(errors.members) && (
                <p className="text-xs text-red-400">
                  {(errors.members as { message?: string }).message}
                </p>
              )}
            </div>

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
          </div>

          {/* Submit */}
          <div className="flex justify-end pt-4">
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
                'Save Assignment'
              )}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

