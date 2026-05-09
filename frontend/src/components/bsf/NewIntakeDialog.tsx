'use client'

import { useState } from 'react'
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
import { newIntakeSchema, type NewIntakeFormValues, extractErrorMessage } from './schemas'

interface NewIntakeDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}

export function NewIntakeDialog({ open, onOpenChange, onSuccess }: NewIntakeDialogProps) {
  const [apiError, setApiError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    setValue,
    reset,
    formState: { errors },
  } = useForm<NewIntakeFormValues>({
    resolver: zodResolver(newIntakeSchema),
    defaultValues: {
      intake_date: '',
      food_waste_kg: undefined,
      contamination_level: undefined,
      batch_start: '',
      livestock_recipient: '',
    },
  })

  const { mutate, isPending } = useMutation({
    mutationFn: (payload: Record<string, unknown>) => bsfApi.createBatch(payload),
    onSuccess: () => {
      onSuccess()
      onOpenChange(false)
    },
    onError: (err) => {
      setApiError(extractErrorMessage(err, 'Failed to create batch'))
    },
  })

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen) {
      reset()
      setApiError(null)
    }
    onOpenChange(nextOpen)
  }

  function onSubmit(values: NewIntakeFormValues) {
    const payload: Record<string, unknown> = {
      intake_date: values.intake_date,
      food_waste_kg: values.food_waste_kg,
      contamination_level: values.contamination_level,
    }
    if (values.batch_start) payload.batch_start = values.batch_start
    if (values.livestock_recipient) payload.livestock_recipient = values.livestock_recipient
    mutate(payload)
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="bg-white border-gray-200 text-gray-800 sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-gray-900">New Intake</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4 mt-2">
          {/* Intake Date */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-gray-500">Intake Date <span className="text-red-400">*</span></Label>
            <Input
              type="date"
              {...register('intake_date')}
              className="bg-white border-gray-200 text-gray-800"
            />
            {errors.intake_date && (
              <p className="text-xs text-red-400">{errors.intake_date.message}</p>
            )}
          </div>

          {/* Food Waste (kg) */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-gray-500">Food Waste (kg) <span className="text-red-400">*</span></Label>
            <Input
              type="number"
              step="0.001"
              min="0"
              {...register('food_waste_kg', { valueAsNumber: true })}
              className="bg-white border-gray-200 text-gray-800"
            />
            {errors.food_waste_kg && (
              <p className="text-xs text-red-400">{errors.food_waste_kg.message}</p>
            )}
          </div>

          {/* Contamination Level */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-gray-500">Contamination Level <span className="text-red-400">*</span></Label>
            <Select onValueChange={(val) => setValue('contamination_level', val as NewIntakeFormValues['contamination_level'], { shouldValidate: true })}>
              <SelectTrigger className="bg-white border-gray-200 text-gray-800">
                <SelectValue placeholder="Select level" />
              </SelectTrigger>
              <SelectContent className="bg-white border-gray-200 text-gray-800">
                <SelectItem value="clean">Clean</SelectItem>
                <SelectItem value="minor">Minor</SelectItem>
                <SelectItem value="rejected">Rejected</SelectItem>
              </SelectContent>
            </Select>
            {errors.contamination_level && (
              <p className="text-xs text-red-400">{errors.contamination_level.message}</p>
            )}
          </div>

          {/* Batch Start (optional) */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-gray-500">Batch Start <span className="text-gray-400 text-xs">(optional)</span></Label>
            <Input
              type="date"
              {...register('batch_start')}
              className="bg-white border-gray-200 text-gray-800"
            />
            {errors.batch_start && (
              <p className="text-xs text-red-400">{errors.batch_start.message}</p>
            )}
          </div>

          {/* Livestock Recipient (optional) */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-gray-500">Livestock Recipient <span className="text-gray-400 text-xs">(optional)</span></Label>
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
          {apiError && (
            <p className="text-sm text-red-400">{apiError}</p>
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
              className="bg-green-600 hover:bg-green-700 text-gray-900"
            >
              {isPending ? (
                <>
                  <Loader2 className="animate-spin w-4 h-4 mr-2" />
                  Creating…
                </>
              ) : (
                'Create Batch'
              )}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

