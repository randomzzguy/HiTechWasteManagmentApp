'use client'

import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { complianceApi, clientsApi } from '@/lib/api'
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

const schema = z.object({
  client_id: z.string().uuid({ message: 'Please select a client' }),
  sw_code: z.string().min(1, 'SW code is required').max(20),
  waste_description: z.string().min(1, 'Description is required').max(500),
  quantity_kg: z
    .number({ invalid_type_error: 'Must be a number' })
    .positive('Must be greater than 0'),
  physical_state: z.enum(['solid', 'liquid', 'sludge', 'gas'], {
    required_error: 'Physical state is required',
  }),
  container_type: z.string().max(100).optional(),
  container_count: z
    .number({ invalid_type_error: 'Must be a number' })
    .int()
    .positive()
    .optional(),
  storage_start_date: z.string().min(1, 'Storage start date is required'),
})

type FormValues = z.infer<typeof schema>

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface SwBatchFormProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}

// ---------------------------------------------------------------------------
// Common SW codes for quick selection
// ---------------------------------------------------------------------------

const COMMON_SW_CODES = [
  { code: 'SW 305', label: 'SW 305 — Used lubricating oil' },
  { code: 'SW 306', label: 'SW 306 — Spent solvent' },
  { code: 'SW 322', label: 'SW 322 — Clinical waste' },
  { code: 'SW 408', label: 'SW 408 — Contaminated containers' },
  { code: 'SW 409', label: 'SW 409 — Contaminated absorbents' },
  { code: 'SW 410', label: 'SW 410 — Lead-acid batteries' },
  { code: 'SW 420', label: 'SW 420 — Electronic waste' },
  { code: 'SW 422', label: 'SW 422 — Fluorescent lamps' },
]

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function SwBatchForm({
  open,
  onOpenChange,
  onSuccess,
}: SwBatchFormProps) {
  const [apiError, setApiError] = useState<string | null>(null)

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
      client_id: '',
      sw_code: '',
      waste_description: '',
      quantity_kg: undefined,
      physical_state: 'solid',
      container_type: '',
      container_count: undefined,
      storage_start_date: new Date().toISOString().split('T')[0],
    },
  })

  // Clients dropdown
  const { data: clientsData } = useQuery({
    queryKey: ['clients-dropdown-sw'],
    queryFn: () => clientsApi.list({ page_size: 200, is_active: true } as Parameters<typeof clientsApi.list>[0]),
    staleTime: 5 * 60_000,
    enabled: open,
  })
  const clients = (clientsData as unknown as { results?: { id: string; company_name: string }[] } | null)?.results
    ?? (clientsData as unknown as { items?: { id: string; company_name: string }[] } | null)?.items
    ?? []

  const { mutate, isPending } = useMutation({
    mutationFn: (values: FormValues) =>
      complianceApi.createBatch({
        client_id: values.client_id,
        sw_code: values.sw_code,
        waste_description: values.waste_description,
        quantity_kg: values.quantity_kg,
        physical_state: values.physical_state,
        storage_start_date: values.storage_start_date,
        ...(values.container_type ? { container_type: values.container_type } : {}),
        ...(values.container_count ? { container_count: values.container_count } : {}),
      }),
    onSuccess: () => {
      onSuccess()
      onOpenChange(false)
      reset()
      setApiError(null)
      toast.success('SW batch created')
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Failed to create SW batch'
      setApiError(typeof msg === 'string' ? msg : 'Failed to create SW batch')
    },
  })

  function handleOpenChange(next: boolean) {
    if (!next) {
      reset()
      setApiError(null)
    }
    onOpenChange(next)
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="bg-white border-gray-200 text-gray-900 sm:max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-gray-900">New Scheduled Waste Batch</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit((v) => mutate(v))} className="flex flex-col gap-4 mt-2">
          {/* Client */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-gray-600 text-xs">Client <span className="text-red-500">*</span></Label>
            <Select onValueChange={(v) => setValue('client_id', v, { shouldValidate: true })}>
              <SelectTrigger className="bg-white border-gray-300 text-gray-900">
                <SelectValue placeholder="Select client…" />
              </SelectTrigger>
              <SelectContent className="bg-white border-gray-200">
                {clients.map((c) => (
                  <SelectItem key={c.id} value={c.id} className="text-gray-900 focus:bg-gray-50">
                    {c.company_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {errors.client_id && <p className="text-xs text-red-500">{errors.client_id.message}</p>}
          </div>

          {/* SW Code */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-gray-600 text-xs">SW Code <span className="text-red-500">*</span></Label>
            <div className="flex gap-2">
              <Input
                {...register('sw_code')}
                placeholder="e.g. SW 305"
                className="bg-white border-gray-300 text-gray-900 flex-1"
              />
              <Select onValueChange={(v) => setValue('sw_code', v, { shouldValidate: true })}>
                <SelectTrigger className="bg-white border-gray-300 text-gray-900 w-32 text-xs">
                  <SelectValue placeholder="Quick pick" />
                </SelectTrigger>
                <SelectContent className="bg-white border-gray-200">
                  {COMMON_SW_CODES.map((c) => (
                    <SelectItem key={c.code} value={c.code} className="text-gray-900 text-xs focus:bg-gray-50">
                      {c.code}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {errors.sw_code && <p className="text-xs text-red-500">{errors.sw_code.message}</p>}
          </div>

          {/* Waste Description */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-gray-600 text-xs">Waste Description <span className="text-red-500">*</span></Label>
            <Textarea
              {...register('waste_description')}
              placeholder="e.g. Used lubricating oil from machinery"
              rows={2}
              className="bg-white border-gray-300 text-gray-900 resize-none"
            />
            {errors.waste_description && <p className="text-xs text-red-500">{errors.waste_description.message}</p>}
          </div>

          {/* Quantity + Physical State */}
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label className="text-gray-600 text-xs">Quantity (kg) <span className="text-red-500">*</span></Label>
              <Input
                type="number"
                step="0.001"
                min="0"
                {...register('quantity_kg', { valueAsNumber: true })}
                placeholder="e.g. 450"
                className="bg-white border-gray-300 text-gray-900"
              />
              {errors.quantity_kg && <p className="text-xs text-red-500">{errors.quantity_kg.message}</p>}
            </div>
            <div className="flex flex-col gap-1.5">
              <Label className="text-gray-600 text-xs">Physical State <span className="text-red-500">*</span></Label>
              <Select
                defaultValue="solid"
                onValueChange={(v) => setValue('physical_state', v as FormValues['physical_state'], { shouldValidate: true })}
              >
                <SelectTrigger className="bg-white border-gray-300 text-gray-900">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-white border-gray-200">
                  {['solid', 'liquid', 'sludge', 'gas'].map((s) => (
                    <SelectItem key={s} value={s} className="text-gray-900 capitalize focus:bg-gray-50">{s}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {errors.physical_state && <p className="text-xs text-red-500">{errors.physical_state.message}</p>}
            </div>
          </div>

          {/* Container Type + Count */}
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label className="text-gray-600 text-xs">Container Type</Label>
              <Input
                {...register('container_type')}
                placeholder="e.g. 200L drum"
                className="bg-white border-gray-300 text-gray-900"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label className="text-gray-600 text-xs">Container Count</Label>
              <Input
                type="number"
                min="1"
                step="1"
                {...register('container_count', { valueAsNumber: true })}
                placeholder="e.g. 3"
                className="bg-white border-gray-300 text-gray-900"
              />
            </div>
          </div>

          {/* Storage Start Date */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-gray-600 text-xs">Storage Start Date <span className="text-red-500">*</span></Label>
            <Input
              type="date"
              {...register('storage_start_date')}
              className="bg-white border-gray-300 text-gray-900"
            />
            {errors.storage_start_date && <p className="text-xs text-red-500">{errors.storage_start_date.message}</p>}
            <p className="text-[11px] text-amber-600">
              ⚠ 90-day disposal deadline will be calculated from this date
            </p>
          </div>

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
              className="bg-brand-600 hover:bg-brand-700 text-white"
            >
              {isPending ? (
                <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Creating…</>
              ) : (
                'Create SW Batch'
              )}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
