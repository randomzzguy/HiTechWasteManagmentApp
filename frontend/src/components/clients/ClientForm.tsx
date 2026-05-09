'use client'

import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { clientsApi } from '@/lib/api'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { Separator } from '@/components/ui/separator'
import { toast } from 'sonner'
import { Loader2, Plus, Trash2 } from 'lucide-react'

// ── Types ─────────────────────────────────────────────────────

interface ClientFormProps {
  open: boolean
  onClose: () => void
  onSuccess?: (clientId: string) => void
}

const BILLING_MODELS = [
  { value: 'tonnage', label: 'Per Tonne' },
  { value: 'trip', label: 'Per Trip' },
  { value: 'lumpsum', label: 'Lump Sum / Retainer' },
]

const WASTE_TYPES = [
  'General Waste',
  'Recyclables',
  'Scheduled Waste',
  'Food Waste',
  'Clinical Waste',
  'E-Waste',
  'Construction Waste',
]

const COLLECTION_FREQUENCIES = [
  { value: 'daily', label: 'Daily' },
  { value: 'weekly', label: 'Weekly' },
  { value: 'fortnightly', label: 'Fortnightly' },
  { value: 'monthly', label: 'Monthly' },
  { value: 'on_call', label: 'On Call' },
]

interface WasteStreamInput {
  waste_type: string
  estimated_kg_per_month: string
  collection_frequency: string
  special_handling_notes: string
}

// ── Form ──────────────────────────────────────────────────────

export default function ClientForm({ open, onClose, onSuccess }: ClientFormProps) {
  const qc = useQueryClient()

  const [form, setForm] = useState({
    company_name: '',
    industry_vertical: '',
    ssm_number: '',
    address: '',
    city: '',
    state: '',
    pic_name: '',
    pic_email: '',
    pic_phone: '',
    contract_start: '',
    contract_end: '',
    sla_diversion_target: '',
    billing_model: '',
    notes: '',
  })

  const [wasteStreams, setWasteStreams] = useState<WasteStreamInput[]>([])
  const [errors, setErrors] = useState<Record<string, string>>({})

  const mutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => clientsApi.create(data),
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ['clients'] })
      toast.success(`Client "${(result as Record<string, string>).company_name}" created`)
      onSuccess?.((result as Record<string, string>).id)
      handleClose()
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { error?: { detail?: string } } } })
        ?.response?.data?.error?.detail
      if (typeof detail === 'string' && detail.includes('SSM')) {
        setErrors((e) => ({ ...e, ssm_number: detail }))
      } else {
        toast.error(detail ?? 'Failed to create client')
      }
    },
  })

  function validate(): boolean {
    const e: Record<string, string> = {}
    if (!form.company_name.trim()) e.company_name = 'Company name is required'
    if (form.pic_email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.pic_email)) {
      e.pic_email = 'Invalid email address'
    }
    if (form.sla_diversion_target) {
      const v = parseFloat(form.sla_diversion_target)
      if (isNaN(v) || v < 0 || v > 100) e.sla_diversion_target = 'Must be 0–100'
    }
    setErrors(e)
    return Object.keys(e).length === 0
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!validate()) return

    const payload: Record<string, unknown> = {
      company_name: form.company_name.trim(),
      is_active: true,
    }
    if (form.industry_vertical.trim()) payload.industry_vertical = form.industry_vertical.trim()
    if (form.ssm_number.trim()) payload.ssm_number = form.ssm_number.trim()
    if (form.address.trim()) payload.address = form.address.trim()
    if (form.city.trim()) payload.city = form.city.trim()
    if (form.state.trim()) payload.state = form.state.trim()
    if (form.pic_name.trim()) payload.pic_name = form.pic_name.trim()
    if (form.pic_email.trim()) payload.pic_email = form.pic_email.trim()
    if (form.pic_phone.trim()) payload.pic_phone = form.pic_phone.trim()
    if (form.contract_start) payload.contract_start = form.contract_start
    if (form.contract_end) payload.contract_end = form.contract_end
    if (form.sla_diversion_target) payload.sla_diversion_target = parseFloat(form.sla_diversion_target)
    if (form.billing_model) payload.billing_model = form.billing_model
    if (form.notes.trim()) payload.notes = form.notes.trim()

    if (wasteStreams.length > 0) {
      payload.waste_streams = wasteStreams
        .filter((ws) => ws.waste_type)
        .map((ws) => ({
          waste_type: ws.waste_type,
          estimated_kg_per_month: ws.estimated_kg_per_month ? parseFloat(ws.estimated_kg_per_month) : null,
          collection_frequency: ws.collection_frequency || null,
          special_handling_notes: ws.special_handling_notes || null,
        }))
    }

    mutation.mutate(payload)
  }

  function handleClose() {
    setForm({
      company_name: '', industry_vertical: '', ssm_number: '', address: '',
      city: '', state: '', pic_name: '', pic_email: '', pic_phone: '',
      contract_start: '', contract_end: '', sla_diversion_target: '',
      billing_model: '', notes: '',
    })
    setWasteStreams([])
    setErrors({})
    onClose()
  }

  function addWasteStream() {
    setWasteStreams((ws) => [...ws, { waste_type: '', estimated_kg_per_month: '', collection_frequency: '', special_handling_notes: '' }])
  }

  function removeWasteStream(i: number) {
    setWasteStreams((ws) => ws.filter((_, idx) => idx !== i))
  }

  function updateWasteStream(i: number, key: keyof WasteStreamInput, value: string) {
    setWasteStreams((ws) => ws.map((item, idx) => idx === i ? { ...item, [key]: value } : item))
  }

  function f(key: keyof typeof form) {
    return {
      value: form[key],
      onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
        setForm((prev) => ({ ...prev, [key]: e.target.value })),
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && handleClose()}>
      <DialogContent className="bg-white border-gray-200 text-gray-900 max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-gray-900">New Client</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-5 py-2">
          {/* Company info */}
          <div className="space-y-3">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Company</p>
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2 space-y-1.5">
                <Label className="text-gray-600 text-xs">Company Name *</Label>
                <Input {...f('company_name')} placeholder="e.g. Unilever Malaysia Holdings Sdn Bhd"
                  className="bg-white border-gray-300 text-gray-900 text-sm" />
                {errors.company_name && <p className="text-xs text-red-500">{errors.company_name}</p>}
              </div>
              <div className="space-y-1.5">
                <Label className="text-gray-600 text-xs">Industry</Label>
                <Input {...f('industry_vertical')} placeholder="e.g. FMCG / Manufacturing"
                  className="bg-white border-gray-300 text-gray-900 text-sm" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-gray-600 text-xs">SSM Number</Label>
                <Input {...f('ssm_number')} placeholder="e.g. 199001012345"
                  className="bg-white border-gray-300 text-gray-900 text-sm" />
                {errors.ssm_number && <p className="text-xs text-red-500">{errors.ssm_number}</p>}
              </div>
            </div>
            <div className="space-y-1.5">
              <Label className="text-gray-600 text-xs">Address</Label>
              <Textarea {...f('address')} placeholder="Street address…" rows={2}
                className="bg-white border-gray-300 text-gray-900 text-sm resize-none" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-gray-600 text-xs">City</Label>
                <Input {...f('city')} placeholder="e.g. Petaling Jaya"
                  className="bg-white border-gray-300 text-gray-900 text-sm" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-gray-600 text-xs">State</Label>
                <Input {...f('state')} placeholder="e.g. Selangor"
                  className="bg-white border-gray-300 text-gray-900 text-sm" />
              </div>
            </div>
          </div>

          <Separator className="bg-gray-200" />

          {/* PIC */}
          <div className="space-y-3">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Primary Contact (PIC)</p>
            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-1.5">
                <Label className="text-gray-600 text-xs">Name</Label>
                <Input {...f('pic_name')} placeholder="Full name"
                  className="bg-white border-gray-300 text-gray-900 text-sm" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-gray-600 text-xs">Email</Label>
                <Input type="email" {...f('pic_email')} placeholder="email@company.com"
                  className="bg-white border-gray-300 text-gray-900 text-sm" />
                {errors.pic_email && <p className="text-xs text-red-500">{errors.pic_email}</p>}
              </div>
              <div className="space-y-1.5">
                <Label className="text-gray-600 text-xs">Phone</Label>
                <Input {...f('pic_phone')} placeholder="+60123456789"
                  className="bg-white border-gray-300 text-gray-900 text-sm" />
              </div>
            </div>
          </div>

          <Separator className="bg-gray-200" />

          {/* Contract */}
          <div className="space-y-3">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Contract & SLA</p>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-gray-600 text-xs">Contract Start</Label>
                <Input type="date" {...f('contract_start')}
                  className="bg-white border-gray-300 text-gray-900 text-sm" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-gray-600 text-xs">Contract End</Label>
                <Input type="date" {...f('contract_end')}
                  className="bg-white border-gray-300 text-gray-900 text-sm" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-gray-600 text-xs">Diversion Target (%)</Label>
                <Input type="number" min="0" max="100" step="0.1" {...f('sla_diversion_target')}
                  placeholder="e.g. 70"
                  className="bg-white border-gray-300 text-gray-900 text-sm" />
                {errors.sla_diversion_target && <p className="text-xs text-red-500">{errors.sla_diversion_target}</p>}
              </div>
              <div className="space-y-1.5">
                <Label className="text-gray-600 text-xs">Billing Model</Label>
                <Select value={form.billing_model} onValueChange={(v) => setForm((f) => ({ ...f, billing_model: v }))}>
                  <SelectTrigger className="bg-white border-gray-300 text-gray-900 text-sm">
                    <SelectValue placeholder="Select…" />
                  </SelectTrigger>
                  <SelectContent className="bg-white border-gray-200">
                    {BILLING_MODELS.map((m) => (
                      <SelectItem key={m.value} value={m.value} className="text-gray-900 hover:bg-gray-50">
                        {m.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>

          <Separator className="bg-gray-200" />

          {/* Waste streams */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Waste Streams</p>
              <Button type="button" variant="ghost" size="sm" onClick={addWasteStream}
                className="text-xs text-emerald-400 hover:text-emerald-300 h-7 px-2">
                <Plus className="w-3 h-3 mr-1" /> Add Stream
              </Button>
            </div>
            {wasteStreams.map((ws, i) => (
              <div key={i} className="grid grid-cols-12 gap-2 items-start p-3 rounded-lg bg-gray-50 border border-gray-200">
                <div className="col-span-4 space-y-1">
                  <Label className="text-gray-500 text-[10px]">Waste Type</Label>
                  <Select value={ws.waste_type} onValueChange={(v) => updateWasteStream(i, 'waste_type', v)}>
                    <SelectTrigger className="bg-white border-gray-300 text-gray-900 text-xs h-8">
                      <SelectValue placeholder="Type…" />
                    </SelectTrigger>
                    <SelectContent className="bg-white border-gray-200">
                      {WASTE_TYPES.map((t) => (
                        <SelectItem key={t} value={t} className="text-white text-xs hover:bg-gray-200">{t}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="col-span-3 space-y-1">
                  <Label className="text-gray-500 text-[10px]">Est. kg/month</Label>
                  <Input type="number" min="0" value={ws.estimated_kg_per_month}
                    onChange={(e) => updateWasteStream(i, 'estimated_kg_per_month', e.target.value)}
                    placeholder="kg" className="bg-white border-gray-300 text-gray-900 text-xs h-8" />
                </div>
                <div className="col-span-4 space-y-1">
                  <Label className="text-gray-500 text-[10px]">Frequency</Label>
                  <Select value={ws.collection_frequency} onValueChange={(v) => updateWasteStream(i, 'collection_frequency', v)}>
                    <SelectTrigger className="bg-white border-gray-300 text-gray-900 text-xs h-8">
                      <SelectValue placeholder="Freq…" />
                    </SelectTrigger>
                    <SelectContent className="bg-white border-gray-200">
                      {COLLECTION_FREQUENCIES.map((f) => (
                        <SelectItem key={f.value} value={f.value} className="text-white text-xs hover:bg-gray-200">{f.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="col-span-1 flex items-end pb-0.5">
                  <Button type="button" variant="ghost" size="sm" onClick={() => removeWasteStream(i)}
                    className="h-8 w-8 p-0 text-slate-500 hover:text-red-500">
                    <Trash2 className="w-3.5 h-3.5" />
                  </Button>
                </div>
              </div>
            ))}
          </div>

          {/* Notes */}
          <div className="space-y-1.5">
            <Label className="text-gray-600 text-xs">Notes</Label>
            <Textarea {...f('notes')} placeholder="Internal notes…" rows={2}
              className="bg-white border-gray-300 text-gray-900 text-sm resize-none" />
          </div>
        </form>

        <DialogFooter className="gap-2">
          <Button variant="ghost" onClick={handleClose} className="text-gray-500 hover:text-gray-900">
            Cancel
          </Button>
          <Button onClick={handleSubmit as unknown as React.MouseEventHandler}
            disabled={mutation.isPending}
            className="bg-emerald-600 hover:bg-emerald-700 text-white">
            {mutation.isPending ? (
              <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Creating…</>
            ) : 'Create Client'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

