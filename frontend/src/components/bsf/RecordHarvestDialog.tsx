'use client'

import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { bsfApi } from '@/lib/api'
import {
  harvestSchema,
  type HarvestFormValues,
  extractErrorMessage,
  computeConversionPreview,
} from './schemas'

interface BsfBatch {
  id: string
  intake_date: string
  food_waste_kg?: number
  contamination_level?: string
  larvae_output_kg?: number
  conversion_ratio?: number
  livestock_recipient?: string
  batch_start?: string
  batch_end?: string
  status: string
}

interface RecordHarvestDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  batch: BsfBatch | null
  onSuccess: () => void
}

export function RecordHarvestDialog({
  open,
  onOpenChange,
  batch,
  onSuccess,
}: RecordHarvestDialogProps) {
  const [apiError, setApiError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    setValue,
    reset,
    watch,
    formState: { errors },
  } = useForm<HarvestFormValues>({
    resolver: zodResolver(harvestSchema),
    defaultValues: {
      larvae_output_kg: undefined,
      batch_end: '',
      status: undefined,
      contamination_level: undefined,
      livestock_recipient: '',
      intake_date: batch?.intake_date ?? '',
    },
  })

  // Reset form with fresh defaults whenever the batch changes
  useEffect(() => {
    reset({
      larvae_output_kg: undefined,
      batch_end: '',
      status: undefined,
      contamination_level: undefined,
      livestock_recipient: '',
      intake_date: batch?.intake_date ?? '',
    })
    setApiError(null)
  }, [batch, reset])

  const larvaeOutputKg = watch('larvae_output_kg')
  const conversionPreview = computeConversionPreview(
    larvaeOutputKg ?? 0,
    batch?.food_waste_kg ?? 0,
  )

  const { mutate, isPending } = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      bsfApi.updateBatch(batch!.id, payload),
    onSuccess: () => {
      onSuccess()
      onOpenChange(false)
    },
    onError: (err) => {
      setApiError(extractErrorMessage(err, 'Failed to record harvest'))
    },
  })

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen) {
      reset({
        larvae_output_kg: undefined,
        batch_end: '',
        status: undefined,
        contamination_level: undefined,
        livestock_recipient: '',
        intake_date: batch?.intake_date ?? '',
      })
      setApiError(null)
    }
    onOpenChange(nextOpen)
  }

  function onSubmit(values: HarvestFormValues) {
    // Strip intake_date (context only) and omit empty optional strings
    const payload: Record<string, unknown> = {
      larvae_output_kg: values.larvae_output_kg,
      batch_end: values.batch_end,
      status: values.status,
    }
    if (values.contamination_level) payload.contamination_level = values.contamination_level
    if (values.livestock_recipient) payload.livestock_recipient = values.livestock_recipient
    mutate(payload)
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="bg-white border-gray-200 text-gray-800 sm:max-w-md max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-gray-900">Record Harvest</DialogTitle>
        </DialogHeader>

        {/* Batch info */}
        {batch?.food_waste_kg != null && (
          <p className="text-xs text-gray-500 -mt-1">
            Batch food waste: <span className="text-gray-700 font-medium">{batch.food_waste_kg} kg</span>
          </p>
        )}

        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4 mt-1">
          {/* Larvae Output (kg) */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-gray-500">
              Larvae Output (kg) <span className="text-red-400">*</span>
            </Label>
            <Input
              type="number"
              step="0.001"
              min="0"
              {...register('larvae_output_kg', { valueAsNumber: true })}
              className="bg-white border-gray-200 text-gray-800"
            />
            {errors.larvae_output_kg && (
              <p className="text-xs text-red-400">{errors.larvae_output_kg.message}</p>
            )}
          </div>

          {/* Conversion Ratio Preview */}
          <div className="flex items-center justify-between px-3 py-2 rounded-lg bg-white border border-gray-200">
            <span className="text-xs text-gray-500">Conversion Ratio Preview</span>
            <span className="text-sm font-semibold text-green-400">{conversionPreview}</span>
          </div>

          {/* Batch End Date */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-gray-500">
              Batch End Date <span className="text-red-400">*</span>
            </Label>
            <Input
              type="date"
              {...register('batch_end')}
              className="bg-white border-gray-200 text-gray-800"
            />
            {errors.batch_end && (
              <p className="text-xs text-red-400">{errors.batch_end.message}</p>
            )}
          </div>

          {/* Status */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-gray-500">
              Status <span className="text-red-400">*</span>
            </Label>
            <Select
              onValueChange={(val) =>
                setValue('status', val as HarvestFormValues['status'], { shouldValidate: true })
              }
            >
              <SelectTrigger className="bg-white border-gray-200 text-gray-800">
                <SelectValue placeholder="Select status" />
              </SelectTrigger>
              <SelectContent className="bg-white border-gray-200 text-gray-800">
                <SelectItem value="completed">Completed</SelectItem>
                <SelectItem value="rejected">Rejected</SelectItem>
              </SelectContent>
            </Select>
            {errors.status && (
              <p className="text-xs text-red-400">{errors.status.message}</p>
            )}
          </div>

          {/* Contamination Level (optional) */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-gray-500">
              Contamination Level{' '}
              <span className="text-gray-400 text-xs">(optional)</span>
            </Label>
            <Select
              onValueChange={(val) =>
                setValue(
                  'contamination_level',
                  val as HarvestFormValues['contamination_level'],
                  { shouldValidate: true },
                )
              }
            >
              <SelectTrigger className="bg-white border-gray-200 text-gray-800">
                <SelectValue placeholder="Select level" />
              </SelectTrigger>
              <SelectContent className="bg-white border-gray-200 text-gray-800">
                <SelectItem value="clean">
                  <span className="text-green-400">Clean</span>
                </SelectItem>
                <SelectItem value="minor">
                  <span className="text-amber-400">Minor</span>
                </SelectItem>
                <SelectItem value="rejected">
                  <span className="text-red-400">Rejected</span>
                </SelectItem>
              </SelectContent>
            </Select>
            {errors.contamination_level && (
              <p className="text-xs text-red-400">{errors.contamination_level.message}</p>
            )}
          </div>

          {/* Livestock Recipient (optional) */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-gray-500">
              Livestock Recipient{' '}
              <span className="text-gray-400 text-xs">(optional)</span>
            </Label>
            <Input
              type="text"
              {...register('livestock_recipient')}
              placeholder="e.g. Farm A"
              className="bg-white border-gray-200 text-gray-800"
            />
            {errors.livestock_recipient && (
              <p className="text-xs text-red-400">{errors.livestock_recipient.message}</p>
            )}
          </div>

          {/* API Error */}
          {apiError && <p className="text-sm text-red-400">{apiError}</p>}

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
              className="bg-green-600 hover:bg-green-700 text-gray-900"
            >
              {isPending ? (
                <>
                  <Loader2 className="animate-spin w-4 h-4 mr-2" />
                  Saving…
                </>
              ) : (
                'Record Harvest'
              )}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

