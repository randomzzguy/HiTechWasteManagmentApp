'use client'

import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { equipmentApi } from '@/lib/api'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { toast } from 'sonner'
import { Loader2 } from 'lucide-react'

interface CompactorFormProps {
  open: boolean
  onClose: () => void
}

export default function CompactorForm({ open, onClose }: CompactorFormProps) {
  const qc = useQueryClient()
  const [form, setForm] = useState({
    asset_tag: '',
    model_name: '',
    serial_number: '',
    compaction_force_kn: '',
    maintenance_interval_days: '90',
    purchase_date: '',
    notes: '',
  })
  const [errors, setErrors] = useState<Record<string, string>>({})

  const mutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => equipmentApi.createCompactor(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['compactors'] })
      toast.success('Compaction machine registered')
      handleClose()
    },
    onError: () => toast.error('Failed to register compaction machine'),
  })

  function validate() {
    const e: Record<string, string> = {}
    if (!form.asset_tag.trim()) e.asset_tag = 'Asset tag is required'
    if (!form.model_name.trim()) e.model_name = 'Model name is required'
    if (!form.serial_number.trim()) e.serial_number = 'Serial number is required'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!validate()) return
    const payload: Record<string, unknown> = {
      asset_tag: form.asset_tag.trim(),
      model_name: form.model_name.trim(),
      serial_number: form.serial_number.trim(),
      maintenance_interval_days: parseInt(form.maintenance_interval_days) || 90,
    }
    if (form.compaction_force_kn) payload.compaction_force_kn = parseFloat(form.compaction_force_kn)
    if (form.purchase_date) payload.purchase_date = form.purchase_date
    if (form.notes.trim()) payload.notes = form.notes.trim()
    mutation.mutate(payload)
  }

  function handleClose() {
    setForm({ asset_tag: '', model_name: '', serial_number: '', compaction_force_kn: '', maintenance_interval_days: '90', purchase_date: '', notes: '' })
    setErrors({})
    onClose()
  }

  function f(key: keyof typeof form) {
    return { value: form[key], onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setForm((p) => ({ ...p, [key]: e.target.value })) }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && handleClose()}>
      <DialogContent className="bg-white border-gray-200 text-gray-900 max-w-md">
        <DialogHeader><DialogTitle className="text-gray-900">Register Compaction Machine</DialogTitle></DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 py-2">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-gray-700 text-xs">Asset Tag *</Label>
              <Input {...f('asset_tag')} placeholder="CM-001" className="bg-white border-gray-200 text-gray-900 text-sm" />
              {errors.asset_tag && <p className="text-xs text-red-400">{errors.asset_tag}</p>}
            </div>
            <div className="space-y-1.5">
              <Label className="text-gray-700 text-xs">Serial Number *</Label>
              <Input {...f('serial_number')} placeholder="HK200-2024-001" className="bg-white border-gray-200 text-gray-900 text-sm" />
              {errors.serial_number && <p className="text-xs text-red-400">{errors.serial_number}</p>}
            </div>
          </div>
          <div className="space-y-1.5">
            <Label className="text-gray-700 text-xs">Model Name *</Label>
            <Input {...f('model_name')} placeholder="e.g. Husmann HK-200" className="bg-white border-gray-200 text-gray-900 text-sm" />
            {errors.model_name && <p className="text-xs text-red-400">{errors.model_name}</p>}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-gray-700 text-xs">Compaction Force (kN)</Label>
              <Input type="number" min="0" {...f('compaction_force_kn')} placeholder="200" className="bg-white border-gray-200 text-gray-900 text-sm" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-gray-700 text-xs">Service Interval (days)</Label>
              <Input type="number" min="1" {...f('maintenance_interval_days')} className="bg-white border-gray-200 text-gray-900 text-sm" />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label className="text-gray-700 text-xs">Purchase Date</Label>
            <Input type="date" {...f('purchase_date')} className="bg-white border-gray-200 text-gray-900 text-sm" />
          </div>
          <div className="space-y-1.5">
            <Label className="text-gray-700 text-xs">Notes</Label>
            <Textarea {...f('notes')} rows={2} className="bg-white border-gray-200 text-gray-900 text-sm resize-none" />
          </div>
        </form>
        <DialogFooter className="gap-2">
          <Button variant="ghost" onClick={handleClose} className="text-gray-500 hover:text-gray-900">Cancel</Button>
          <Button onClick={handleSubmit as unknown as React.MouseEventHandler} disabled={mutation.isPending} className="bg-emerald-600 hover:bg-emerald-700 text-gray-900">
            {mutation.isPending ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Saving…</> : 'Register Machine'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

