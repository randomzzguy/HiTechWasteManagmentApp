'use client'

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { weighbridgeApi, clientsApi, jobsApi } from '@/lib/api'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { toast } from 'sonner'
import { Loader2 } from 'lucide-react'

interface WeighbridgeFormProps {
  open: boolean
  onClose: () => void
  onSuccess?: () => void
}

const WASTE_TYPES = ['recyclable', 'general_waste', 'scheduled_waste', 'food_waste', 'clinical_waste']

export default function WeighbridgeForm({ open, onClose, onSuccess }: WeighbridgeFormProps) {
  const qc = useQueryClient()

  const [form, setForm] = useState({
    client_id: '',
    job_id: '',
    gross_weight_kg: '',
    tare_weight_kg: '',
    notes: '',
  })
  const [breakdown, setBreakdown] = useState<Record<string, string>>({})
  const [errors, setErrors] = useState<Record<string, string>>({})

  const { data: clientsData } = useQuery({
    queryKey: ['clients-dropdown'],
    queryFn: () => clientsApi.list({ limit: 200, is_active: true } as Parameters<typeof clientsApi.list>[0]),
    staleTime: 5 * 60_000,
    enabled: open,
  })

  const { data: jobsData } = useQuery({
    queryKey: ['jobs-active', form.client_id],
    queryFn: () => jobsApi.list({ client_id: form.client_id, status: 'in_progress', limit: 50 } as Parameters<typeof jobsApi.list>[0]),
    enabled: open && !!form.client_id,
    staleTime: 60_000,
  })

  const clients = (clientsData as { items?: { id: string; company_name: string }[] } | null)?.items ?? []
  const jobs = (jobsData as { items?: { id: string; job_number: string }[] } | null)?.items ?? []

  const gross = parseFloat(form.gross_weight_kg) || 0
  const tare = parseFloat(form.tare_weight_kg) || 0
  const net = Math.max(0, gross - tare)

  const mutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => weighbridgeApi.createRecord(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['weighbridge'] })
      toast.success('Weighbridge record created')
      onSuccess?.()
      handleClose()
    },
    onError: () => toast.error('Failed to create weighbridge record'),
  })

  function validate(): boolean {
    const e: Record<string, string> = {}
    if (!form.client_id) e.client_id = 'Client is required'
    if (!form.gross_weight_kg || gross <= 0) e.gross_weight_kg = 'Gross weight is required'
    if (!form.tare_weight_kg || tare <= 0) e.tare_weight_kg = 'Tare weight is required'
    if (tare >= gross) e.tare_weight_kg = 'Tare must be less than gross weight'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!validate()) return

    const wasteBreakdown: Record<string, number> = {}
    Object.entries(breakdown).forEach(([k, v]) => {
      if (v) wasteBreakdown[`${k}_kg`] = parseFloat(v)
    })

    const payload: Record<string, unknown> = {
      client_id: form.client_id,
      gross_weight_kg: gross,
      tare_weight_kg: tare,
    }
    if (form.job_id) payload.job_id = form.job_id
    if (Object.keys(wasteBreakdown).length > 0) payload.waste_type_breakdown = wasteBreakdown
    if (form.notes.trim()) payload.notes = form.notes.trim()

    mutation.mutate(payload)
  }

  function handleClose() {
    setForm({ client_id: '', job_id: '', gross_weight_kg: '', tare_weight_kg: '', notes: '' })
    setBreakdown({})
    setErrors({})
    onClose()
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && handleClose()}>
      <DialogContent className="bg-white border-gray-200 text-gray-900 max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-gray-900">New Weighbridge Record</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 py-2">
          <div className="space-y-1.5">
            <Label className="text-gray-600 text-xs">Client *</Label>
            <Select value={form.client_id} onValueChange={(v) => setForm((f) => ({ ...f, client_id: v, job_id: '' }))}>
              <SelectTrigger className="bg-white border-gray-300 text-gray-900 text-sm">
                <SelectValue placeholder="Select client…" />
              </SelectTrigger>
              <SelectContent className="bg-white border-gray-200">
                {clients.map((c) => (
                  <SelectItem key={c.id} value={c.id} className="text-gray-900 hover:bg-gray-50">{c.company_name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            {errors.client_id && <p className="text-xs text-red-500">{errors.client_id}</p>}
          </div>

          {jobs.length > 0 && (
            <div className="space-y-1.5">
              <Label className="text-gray-600 text-xs">Link to Job (optional)</Label>
              <Select value={form.job_id} onValueChange={(v) => setForm((f) => ({ ...f, job_id: v }))}>
                <SelectTrigger className="bg-white border-gray-300 text-gray-900 text-sm">
                  <SelectValue placeholder="Select active job…" />
                </SelectTrigger>
                <SelectContent className="bg-white border-gray-200">
                  {jobs.map((j) => (
                    <SelectItem key={j.id} value={j.id} className="text-gray-900 hover:bg-gray-50">{j.job_number}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-gray-600 text-xs">Gross Weight (kg) *</Label>
              <Input type="number" min="0" step="0.01" value={form.gross_weight_kg}
                onChange={(e) => setForm((f) => ({ ...f, gross_weight_kg: e.target.value }))}
                placeholder="e.g. 5200" className="bg-white border-gray-300 text-gray-900 text-sm" />
              {errors.gross_weight_kg && <p className="text-xs text-red-500">{errors.gross_weight_kg}</p>}
            </div>
            <div className="space-y-1.5">
              <Label className="text-gray-600 text-xs">Tare Weight (kg) *</Label>
              <Input type="number" min="0" step="0.01" value={form.tare_weight_kg}
                onChange={(e) => setForm((f) => ({ ...f, tare_weight_kg: e.target.value }))}
                placeholder="e.g. 1800" className="bg-white border-gray-300 text-gray-900 text-sm" />
              {errors.tare_weight_kg && <p className="text-xs text-red-500">{errors.tare_weight_kg}</p>}
            </div>
          </div>

          {net > 0 && (
            <div className="flex items-center justify-between px-3 py-2 rounded-lg bg-emerald-50 border border-emerald-200">
              <span className="text-xs text-gray-500">Net Weight</span>
              <span className="text-sm font-bold text-emerald-400">{net.toLocaleString()} kg</span>
            </div>
          )}

          <div className="space-y-2">
            <Label className="text-gray-600 text-xs">Waste Type Breakdown (optional)</Label>
            <div className="grid grid-cols-2 gap-2">
              {WASTE_TYPES.map((type) => (
                <div key={type} className="flex items-center gap-2">
                  <span className="text-xs text-gray-500 w-24 capitalize">{type.replace('_', ' ')}</span>
                  <Input type="number" min="0" step="0.01"
                    value={breakdown[type] ?? ''}
                    onChange={(e) => setBreakdown((b) => ({ ...b, [type]: e.target.value }))}
                    placeholder="kg" className="bg-white border-gray-300 text-gray-900 text-xs h-8 flex-1" />
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-1.5">
            <Label className="text-gray-600 text-xs">Notes</Label>
            <Textarea value={form.notes} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
              placeholder="Optional notes…" rows={2}
              className="bg-white border-gray-300 text-gray-900 text-sm resize-none" />
          </div>
        </form>

        <DialogFooter className="gap-2">
          <Button variant="ghost" onClick={handleClose} className="text-gray-500 hover:text-gray-900">Cancel</Button>
          <Button onClick={handleSubmit as unknown as React.MouseEventHandler}
            disabled={mutation.isPending} className="bg-emerald-600 hover:bg-emerald-700 text-white">
            {mutation.isPending ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Saving…</> : 'Save Record'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

