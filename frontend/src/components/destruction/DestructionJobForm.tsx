'use client'

import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { destructionApi, jobsApi } from '@/lib/api'
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
// Schema
// ---------------------------------------------------------------------------

const REASON_CODES = [
  'EXPIRED', 'DEFECTIVE', 'COUNTERFEIT', 'CONFIDENTIAL',
  'RECALLED', 'DAMAGED', 'NON_COMPLIANT', 'OBSOLETE',
  'OVERSTOCK', 'CONTAMINATED',
]

const schema = z.object({
  goods_description: z.string().min(5, 'Description must be at least 5 characters'),
  quantity_units: z
    .number({ invalid_type_error: 'Must be a number' })
    .int()
    .positive()
    .optional(),
  weight_kg: z
    .number({ invalid_type_error: 'Must be a number' })
    .nonnegative()
    .optional(),
  destruction_method: z.enum(['shredding', 'incineration', 'landfill_compaction'], {
    required_error: 'Destruction method is required',
  }),
  destruction_date: z.string().optional(),
  destruction_location: z.string().optional(),
  witness_client_name: z.string().optional(),
  witness_client_designation: z.string().optional(),
  reason_codes: z.array(z.string()).optional(),
  job_id: z.string().optional(),
})

type FormValues = z.infer<typeof schema>

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface DestructionJobFormProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function DestructionJobForm({
  open,
  onOpenChange,
  onSuccess,
}: DestructionJobFormProps) {
  const [apiError, setApiError] = useState<string | null>(null)
  const [selectedReasons, setSelectedReasons] = useState<string[]>([])

  const {
    register,
    handleSubmit,
    setValue,
    reset,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      goods_description: '',
      destruction_method: 'shredding',
      destruction_date: '',
      destruction_location: '',
      witness_client_name: '',
      witness_client_designation: '',
      job_id: '',
    },
  })

  // Fetch recent jobs for optional linking
  const { data: jobsData } = useQuery({
    queryKey: ['jobs-dropdown-destruction'],
    queryFn: () => jobsApi.list({ limit: 50, status: 'confirmed' } as Parameters<typeof jobsApi.list>[0]),
    staleTime: 5 * 60_000,
    enabled: open,
  })
  const jobs = (jobsData as { items?: { id: string; job_number: string; client_name?: string }[] } | null)?.items ?? []

  function toggleReason(code: string) {
    const next = selectedReasons.includes(code)
      ? selectedReasons.filter((r) => r !== code)
      : [...selectedReasons, code]
    setSelectedReasons(next)
    setValue('reason_codes', next)
  }

  const { mutate, isPending } = useMutation({
    mutationFn: (values: FormValues) => {
      const payload: Record<string, unknown> = {
        goods_description: values.goods_description,
        destruction_method: values.destruction_method,
      }
      if (values.quantity_units) payload.quantity_units = values.quantity_units
      if (values.weight_kg !== undefined) payload.weight_kg = values.weight_kg
      if (values.destruction_date) payload.destruction_date = values.destruction_date
      if (values.destruction_location) payload.destruction_location = values.destruction_location
      if (values.witness_client_name) payload.witness_client_name = values.witness_client_name
      if (values.witness_client_designation) payload.witness_client_designation = values.witness_client_designation
      if (selectedReasons.length > 0) payload.reason_codes = selectedReasons
      if (values.job_id) payload.job_id = values.job_id
      return destructionApi.createJob(payload)
    },
    onSuccess: () => {
      onSuccess()
      onOpenChange(false)
      reset()
      setSelectedReasons([])
      setApiError(null)
      toast.success('Destruction job created')
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Failed to create destruction job'
      setApiError(typeof msg === 'string' ? msg : 'Failed to create destruction job')
    },
  })

  function handleOpenChange(next: boolean) {
    if (!next) {
      reset()
      setSelectedReasons([])
      setApiError(null)
    }
    onOpenChange(next)
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="bg-white border-gray-200 text-gray-900 sm:max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-gray-900">New Destruction Job</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit((v) => mutate(v))} className="flex flex-col gap-4 mt-2">
          {/* Goods Description */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-gray-600 text-xs">Goods Description <span className="text-red-500">*</span></Label>
            <Textarea
              {...register('goods_description')}
              placeholder="e.g. Expired pharmaceutical products — 500 cartons of Panadol 500mg"
              rows={2}
              className="bg-white border-gray-300 text-gray-900 resize-none"
            />
            {errors.goods_description && <p className="text-xs text-red-500">{errors.goods_description.message}</p>}
          </div>

          {/* Quantity + Weight */}
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label className="text-gray-600 text-xs">Quantity (units)</Label>
              <Input
                type="number"
                min="1"
                step="1"
                {...register('quantity_units', { valueAsNumber: true })}
                placeholder="e.g. 500"
                className="bg-white border-gray-300 text-gray-900"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label className="text-gray-600 text-xs">Weight (kg)</Label>
              <Input
                type="number"
                step="0.001"
                min="0"
                {...register('weight_kg', { valueAsNumber: true })}
                placeholder="e.g. 250"
                className="bg-white border-gray-300 text-gray-900"
              />
            </div>
          </div>

          {/* Destruction Method */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-gray-600 text-xs">Destruction Method <span className="text-red-500">*</span></Label>
            <Select
              defaultValue="shredding"
              onValueChange={(v) => setValue('destruction_method', v as FormValues['destruction_method'], { shouldValidate: true })}
            >
              <SelectTrigger className="bg-white border-gray-300 text-gray-900">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-white border-gray-200">
                <SelectItem value="shredding" className="text-gray-900 focus:bg-gray-50">Shredding</SelectItem>
                <SelectItem value="incineration" className="text-gray-900 focus:bg-gray-50">Incineration</SelectItem>
                <SelectItem value="landfill_compaction" className="text-gray-900 focus:bg-gray-50">Landfill Compaction</SelectItem>
              </SelectContent>
            </Select>
            {errors.destruction_method && <p className="text-xs text-red-500">{errors.destruction_method.message}</p>}
          </div>

          {/* Date + Location */}
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label className="text-gray-600 text-xs">Destruction Date</Label>
              <Input
                type="date"
                {...register('destruction_date')}
                className="bg-white border-gray-300 text-gray-900"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label className="text-gray-600 text-xs">Location / Facility</Label>
              <Input
                {...register('destruction_location')}
                placeholder="e.g. Hi-Tech Shah Alam Facility"
                className="bg-white border-gray-300 text-gray-900"
              />
            </div>
          </div>

          {/* Client Witness */}
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label className="text-gray-600 text-xs">Client Witness Name</Label>
              <Input
                {...register('witness_client_name')}
                placeholder="Full name"
                className="bg-white border-gray-300 text-gray-900"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label className="text-gray-600 text-xs">Witness Designation</Label>
              <Input
                {...register('witness_client_designation')}
                placeholder="e.g. QA Manager"
                className="bg-white border-gray-300 text-gray-900"
              />
            </div>
          </div>

          {/* Reason Codes */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-gray-600 text-xs">Reason Codes</Label>
            <div className="flex flex-wrap gap-1.5">
              {REASON_CODES.map((code) => (
                <button
                  key={code}
                  type="button"
                  onClick={() => toggleReason(code)}
                  className={`text-[11px] px-2 py-1 rounded-full border font-medium transition-colors ${
                    selectedReasons.includes(code)
                      ? 'bg-brand-600 text-white border-brand-600'
                      : 'bg-white text-gray-600 border-gray-300 hover:border-brand-400 hover:text-brand-600'
                  }`}
                >
                  {code.replace(/_/g, ' ')}
                </button>
              ))}
            </div>
          </div>

          {/* Link to Job (optional) */}
          {jobs.length > 0 && (
            <div className="flex flex-col gap-1.5">
              <Label className="text-gray-600 text-xs">Link to Job (optional)</Label>
              <Select onValueChange={(v) => setValue('job_id', v)}>
                <SelectTrigger className="bg-white border-gray-300 text-gray-900">
                  <SelectValue placeholder="Select confirmed job…" />
                </SelectTrigger>
                <SelectContent className="bg-white border-gray-200">
                  {jobs.map((j) => (
                    <SelectItem key={j.id} value={j.id} className="text-gray-900 focus:bg-gray-50">
                      {j.job_number}{j.client_name ? ` — ${j.client_name}` : ''}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {/* API error */}
          {apiError && <p className="text-sm text-red-500">{apiError}</p>}

          {/* Footer */}
          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="ghost"
              onClick={() => onOpenChange(false)}
              className="text-gray-500 hover:text-gray-900"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={isPending}
              className="bg-red-600 hover:bg-red-700 text-white"
            >
              {isPending ? (
                <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Creating…</>
              ) : (
                'Create Destruction Job'
              )}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
