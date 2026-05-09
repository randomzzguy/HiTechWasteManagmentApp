'use client'

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { jobsApi, clientsApi, fleetApi } from '@/lib/api'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { toast } from 'sonner'
import { Loader2 } from 'lucide-react'

// ── Types ─────────────────────────────────────────────────────

interface JobFormProps {
  open: boolean
  onClose: () => void
  onSuccess?: (jobId: string) => void
}

const JOB_TYPES = [
  { value: 'general_collection', label: 'General Collection' },
  { value: 'scheduled_waste', label: 'Scheduled Waste' },
  { value: 'witnessed_destruction', label: 'Witnessed Destruction' },
  { value: 'food_waste_bsf', label: 'Food Waste / BSF' },
  { value: 'equipment_rental', label: 'Equipment Rental' },
  { value: 'consultancy', label: 'Consultancy' },
]

const DISPOSAL_ROUTES = [
  { value: 'recycler', label: 'Recycler' },
  { value: 'landfill', label: 'Landfill' },
  { value: 'wte', label: 'Waste-to-Energy' },
  { value: 'bsf_farm', label: 'BSF Farm' },
  { value: 'cenviro', label: 'Cenviro (Scheduled Waste)' },
]

// ── Form ──────────────────────────────────────────────────────

export default function JobForm({ open, onClose, onSuccess }: JobFormProps) {
  const qc = useQueryClient()

  const [form, setForm] = useState({
    client_id: '',
    job_type: '',
    scheduled_date: '',
    scheduled_time_start: '',
    collection_address: '',
    assigned_vehicle_id: '',
    assigned_driver_id: '',
    estimated_weight_kg: '',
    disposal_route: '',
    notes: '',
  })

  const [errors, setErrors] = useState<Record<string, string>>({})

  // Fetch clients for dropdown
  const { data: clientsData } = useQuery({
    queryKey: ['clients-dropdown'],
    queryFn: () => clientsApi.list({ limit: 200, is_active: true } as Parameters<typeof clientsApi.list>[0]),
    staleTime: 5 * 60_000,
    enabled: open,
  })

  // Fetch vehicles for dropdown
  const { data: vehiclesData } = useQuery({
    queryKey: ['vehicles-dropdown'],
    queryFn: () => fleetApi.listVehicles({ limit: 50 } as Parameters<typeof fleetApi.listVehicles>[0]),
    staleTime: 5 * 60_000,
    enabled: open,
  })

  const clients = (clientsData as { items?: { id: string; company_name: string }[] } | null)?.items ?? []
  const vehicles = (vehiclesData as { items?: { id: string; registration: string; vehicle_type: string }[] } | null)?.items ?? []

  const mutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => jobsApi.create(data),
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ['jobs'] })
      toast.success(`Job ${(result as Record<string, string>).job_number} created`)
      onSuccess?.((result as Record<string, string>).id)
      handleClose()
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { error?: { detail?: string } } } })
        ?.response?.data?.error?.detail ?? 'Failed to create job'
      toast.error(msg)
    },
  })

  function validate(): boolean {
    const e: Record<string, string> = {}
    if (!form.client_id) e.client_id = 'Client is required'
    if (!form.job_type) e.job_type = 'Job type is required'
    if (!form.scheduled_date) e.scheduled_date = 'Scheduled date is required'
    if (!form.collection_address.trim()) e.collection_address = 'Collection address is required'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!validate()) return

    const payload: Record<string, unknown> = {
      client_id: form.client_id,
      job_type: form.job_type,
      scheduled_date: form.scheduled_date,
      collection_address: form.collection_address,
    }
    if (form.scheduled_time_start) payload.scheduled_time_start = form.scheduled_time_start
    if (form.assigned_vehicle_id) payload.assigned_vehicle_id = form.assigned_vehicle_id
    if (form.estimated_weight_kg) payload.estimated_weight_kg = parseFloat(form.estimated_weight_kg)
    if (form.disposal_route) payload.disposal_route = form.disposal_route
    if (form.notes.trim()) payload.notes = form.notes.trim()

    mutation.mutate(payload)
  }

  function handleClose() {
    setForm({
      client_id: '', job_type: '', scheduled_date: '', scheduled_time_start: '',
      collection_address: '', assigned_vehicle_id: '', assigned_driver_id: '',
      estimated_weight_kg: '', disposal_route: '', notes: '',
    })
    setErrors({})
    onClose()
  }

  function field(key: keyof typeof form) {
    return {
      value: form[key],
      onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
        setForm((f) => ({ ...f, [key]: e.target.value })),
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && handleClose()}>
      <DialogContent className="bg-white border-gray-200 text-gray-900 max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-gray-900">New Job</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 py-2">
          {/* Client */}
          <div className="space-y-1.5">
            <Label className="text-gray-600 text-xs">Client *</Label>
            <Select value={form.client_id} onValueChange={(v) => setForm((f) => ({ ...f, client_id: v }))}>
              <SelectTrigger className="bg-white border-gray-300 text-gray-900 text-sm">
                <SelectValue placeholder="Select client…" />
              </SelectTrigger>
              <SelectContent className="bg-white border-gray-200">
                {clients.map((c) => (
                  <SelectItem key={c.id} value={c.id} className="text-gray-900 hover:bg-gray-50">
                    {c.company_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {errors.client_id && <p className="text-xs text-red-500">{errors.client_id}</p>}
          </div>

          {/* Job type */}
          <div className="space-y-1.5">
            <Label className="text-gray-600 text-xs">Job Type *</Label>
            <Select value={form.job_type} onValueChange={(v) => setForm((f) => ({ ...f, job_type: v }))}>
              <SelectTrigger className="bg-white border-gray-300 text-gray-900 text-sm">
                <SelectValue placeholder="Select type…" />
              </SelectTrigger>
              <SelectContent className="bg-white border-gray-200">
                {JOB_TYPES.map((t) => (
                  <SelectItem key={t.value} value={t.value} className="text-gray-900 hover:bg-gray-50">
                    {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {errors.job_type && <p className="text-xs text-red-500">{errors.job_type}</p>}
          </div>

          {/* Date + time */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-gray-600 text-xs">Scheduled Date *</Label>
              <Input
                type="date"
                {...field('scheduled_date')}
                className="bg-white border-gray-300 text-gray-900 text-sm"
              />
              {errors.scheduled_date && <p className="text-xs text-red-500">{errors.scheduled_date}</p>}
            </div>
            <div className="space-y-1.5">
              <Label className="text-gray-600 text-xs">Start Time</Label>
              <Input
                type="time"
                {...field('scheduled_time_start')}
                className="bg-white border-gray-300 text-gray-900 text-sm"
              />
            </div>
          </div>

          {/* Collection address */}
          <div className="space-y-1.5">
            <Label className="text-gray-600 text-xs">Collection Address *</Label>
            <Textarea
              {...field('collection_address')}
              placeholder="Full collection address…"
              rows={2}
              className="bg-white border-gray-300 text-gray-900 text-sm resize-none"
            />
            {errors.collection_address && <p className="text-xs text-red-500">{errors.collection_address}</p>}
          </div>

          {/* Vehicle */}
          <div className="space-y-1.5">
            <Label className="text-gray-600 text-xs">Assign Vehicle</Label>
            <Select value={form.assigned_vehicle_id} onValueChange={(v) => setForm((f) => ({ ...f, assigned_vehicle_id: v }))}>
              <SelectTrigger className="bg-white border-gray-300 text-gray-900 text-sm">
                <SelectValue placeholder="Select vehicle (optional)…" />
              </SelectTrigger>
              <SelectContent className="bg-white border-gray-200">
                {vehicles.map((v) => (
                  <SelectItem key={v.id} value={v.id} className="text-gray-900 hover:bg-gray-50">
                    {v.registration} — {v.vehicle_type.replace('_', ' ')}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Est. weight + disposal route */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-gray-600 text-xs">Est. Weight (kg)</Label>
              <Input
                type="number"
                min="0"
                step="0.1"
                placeholder="e.g. 500"
                {...field('estimated_weight_kg')}
                className="bg-white border-gray-300 text-gray-900 text-sm"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-gray-600 text-xs">Disposal Route</Label>
              <Select value={form.disposal_route} onValueChange={(v) => setForm((f) => ({ ...f, disposal_route: v }))}>
                <SelectTrigger className="bg-white border-gray-300 text-gray-900 text-sm">
                  <SelectValue placeholder="Select…" />
                </SelectTrigger>
                <SelectContent className="bg-white border-gray-200">
                  {DISPOSAL_ROUTES.map((r) => (
                    <SelectItem key={r.value} value={r.value} className="text-gray-900 hover:bg-gray-50">
                      {r.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Notes */}
          <div className="space-y-1.5">
            <Label className="text-gray-600 text-xs">Notes</Label>
            <Textarea
              {...field('notes')}
              placeholder="Optional notes…"
              rows={2}
              className="bg-white border-gray-300 text-gray-900 text-sm resize-none"
            />
          </div>
        </form>

        <DialogFooter className="gap-2">
          <Button
            variant="ghost"
            onClick={handleClose}
            className="text-gray-500 hover:text-gray-900"
          >
            Cancel
          </Button>
          <Button
            onClick={handleSubmit as unknown as React.MouseEventHandler}
            disabled={mutation.isPending}
            className="bg-emerald-600 hover:bg-emerald-700 text-white"
          >
            {mutation.isPending ? (
              <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Creating…</>
            ) : (
              'Create Job'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
