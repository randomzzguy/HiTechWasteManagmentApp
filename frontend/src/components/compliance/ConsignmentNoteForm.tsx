'use client'

import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { complianceApi } from '@/lib/api'
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

// ---------------------------------------------------------------------------
// Schema
// ---------------------------------------------------------------------------

const schema = z.object({
  transport_date: z.string().min(1, 'Transport date is required'),
  transporter_name: z.string().min(1, 'Transporter name is required'),
  transporter_licence: z.string().optional(),
  vehicle_registration: z.string().optional(),
  processing_facility: z.string().min(1, 'Processing facility is required'),
  facility_licence_no: z.string().optional(),
  quantity_kg: z
    .number({ invalid_type_error: 'Must be a number' })
    .positive('Must be greater than 0'),
  notes: z.string().optional(),
})

type FormValues = z.infer<typeof schema>

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ConsignmentNoteFormProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  batchId: string
  swCode: string
  onSuccess: () => void
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ConsignmentNoteForm({
  open,
  onOpenChange,
  batchId,
  swCode,
  onSuccess,
}: ConsignmentNoteFormProps) {
  const [apiError, setApiError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      transport_date: '',
      transporter_name: '',
      transporter_licence: '',
      vehicle_registration: '',
      processing_facility: '',
      facility_licence_no: '',
      quantity_kg: undefined,
      notes: '',
    },
  })

  const { mutate, isPending } = useMutation({
    mutationFn: (values: FormValues) =>
      complianceApi.createConsignmentNote({
        batch_id: batchId,
        transport_date: values.transport_date,
        transporter_name: values.transporter_name,
        vehicle_registration: values.vehicle_registration || undefined,
        processing_facility: values.processing_facility,
        cenviro_reference: values.facility_licence_no || undefined,
      }),
    onSuccess: () => {
      onSuccess()
      onOpenChange(false)
      reset()
      setApiError(null)
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? 'Failed to create consignment note'
      setApiError(typeof msg === 'string' ? msg : 'Failed to create consignment note')
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
          <DialogTitle className="text-gray-900">
            Create Consignment Note
            {swCode && (
              <span className="ml-2 text-sm font-normal text-amber-500">
                {swCode}
              </span>
            )}
          </DialogTitle>
        </DialogHeader>

        <form
          onSubmit={handleSubmit((v) => mutate(v))}
          className="flex flex-col gap-4 mt-2"
        >
          {/* Transport Date */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-gray-600 text-xs">
              Transport Date <span className="text-red-500">*</span>
            </Label>
            <Input
              type="date"
              {...register('transport_date')}
              className="bg-white border-gray-300 text-gray-900"
            />
            {errors.transport_date && (
              <p className="text-xs text-red-500">{errors.transport_date.message}</p>
            )}
          </div>

          {/* Transporter Name */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-gray-600 text-xs">
              Transporter Name <span className="text-red-500">*</span>
            </Label>
            <Input
              {...register('transporter_name')}
              placeholder="e.g. Cenviro Sdn Bhd"
              className="bg-white border-gray-300 text-gray-900"
            />
            {errors.transporter_name && (
              <p className="text-xs text-red-500">{errors.transporter_name.message}</p>
            )}
          </div>

          {/* Vehicle Registration + Transporter Licence */}
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label className="text-gray-600 text-xs">Vehicle Registration</Label>
              <Input
                {...register('vehicle_registration')}
                placeholder="e.g. WXY 1234"
                className="bg-white border-gray-300 text-gray-900"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label className="text-gray-600 text-xs">Transporter Licence</Label>
              <Input
                {...register('transporter_licence')}
                placeholder="Licence no."
                className="bg-white border-gray-300 text-gray-900"
              />
            </div>
          </div>

          {/* Processing Facility */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-gray-600 text-xs">
              Processing Facility <span className="text-red-500">*</span>
            </Label>
            <Input
              {...register('processing_facility')}
              placeholder="e.g. Kualiti Alam Sdn Bhd, Bukit Nanas"
              className="bg-white border-gray-300 text-gray-900"
            />
            {errors.processing_facility && (
              <p className="text-xs text-red-500">{errors.processing_facility.message}</p>
            )}
          </div>

          {/* Facility Licence + Quantity */}
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label className="text-gray-600 text-xs">Facility Licence No.</Label>
              <Input
                {...register('facility_licence_no')}
                placeholder="DOE licence"
                className="bg-white border-gray-300 text-gray-900"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label className="text-gray-600 text-xs">
                Quantity (kg) <span className="text-red-500">*</span>
              </Label>
              <Input
                type="number"
                step="0.001"
                min="0"
                {...register('quantity_kg', { valueAsNumber: true })}
                placeholder="e.g. 250"
                className="bg-white border-gray-300 text-gray-900"
              />
              {errors.quantity_kg && (
                <p className="text-xs text-red-500">{errors.quantity_kg.message}</p>
              )}
            </div>
          </div>

          {/* Notes */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-gray-600 text-xs">Notes</Label>
            <Textarea
              {...register('notes')}
              placeholder="Optional notes…"
              rows={2}
              className="bg-white border-gray-300 text-gray-900 resize-none"
            />
          </div>

          {/* API error */}
          {apiError && (
            <p className="text-sm text-red-500">{apiError}</p>
          )}

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
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Creating…
                </>
              ) : (
                'Create Consignment Note'
              )}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
