'use client'

import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { equipmentApi } from '@/lib/api'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { toast } from 'sonner'
import { Loader2 } from 'lucide-react'

interface ContainerFormProps {
  open: boolean
  onClose: () => void
}

const CONTAINER_TYPES = [
  { value: 'skip_bin', label: 'Skip Bin' },
  { value: 'roll_on_roll_off', label: 'Roll-On/Roll-Off' },
  { value: 'compaction_chamber', label: 'Compaction Chamber' },
]

export default function ContainerForm({ open, onClose }: ContainerFormProps) {
  const qc = useQueryClient()
  const [form, setForm] = useState({
    container_code: '',
    container_type: '',
    capacity_m3: '',
    pickup_threshold: '85',
    notes: '',
  })
  const [errors, setErrors] = useState<Record<string, string>>({})

  const mutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => equipmentApi.createContainer(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['containers'] })
      toast.success('Container registered')
      handleClose()
    },
    onError: () => toast.error('Failed to register container'),
  })

  function validate() {
    const e: Record<string, string> = {}
    if (!form.container_code.trim()) e.container_code = 'Container code is required'
    if (!form.container_type) e.container_type = 'Container type is required'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!validate()) return
    const payload: Record<string, unknown> = {
      container_code: form.container_code.trim(),
      container_type: form.container_type,
      pickup_threshold: parseInt(form.pickup_threshold) || 85,
    }
    if (form.capacity_m3) payload.capacity_m3 = parseFloat(form.capacity_m3)
    if (form.notes.trim()) payload.notes = form.notes.trim()
    mutation.mutate(payload)
  }

  function handleClose() {
    setForm({ container_code: '', container_type: '', capacity_m3: '', pickup_threshold: '85', notes: '' })
    setErrors({})
    onClose()
  }

  function f(key: keyof typeof form) {
    return { value: form[key], onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setForm((p) => ({ ...p, [key]: e.target.value })) }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && handleClose()}>
      <DialogContent className="bg-white border-gray-200 text-gray-900 max-w-md">
        <DialogHeader><DialogTitle className="text-gray-900">Register Container</DialogTitle></DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 py-2">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-gray-700 text-xs">Container Code *</Label>
              <Input {...f('container_code')} placeholder="CNT-007" className="bg-white border-gray-200 text-gray-900 text-sm" />
              {errors.container_code && <p className="text-xs text-red-400">{errors.container_code}</p>}
            </div>
            <div className="space-y-1.5">
              <Label className="text-gray-700 text-xs">Capacity (m³)</Label>
              <Input type="number" min="0" step="0.1" {...f('capacity_m3')} placeholder="20" className="bg-white border-gray-200 text-gray-900 text-sm" />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label className="text-gray-700 text-xs">Container Type *</Label>
            <Select value={form.container_type} onValueChange={(v) => setForm((p) => ({ ...p, container_type: v }))}>
              <SelectTrigger className="bg-white border-gray-200 text-gray-900 text-sm">
                <SelectValue placeholder="Select type…" />
              </SelectTrigger>
              <SelectContent className="bg-white border-gray-200">
                {CONTAINER_TYPES.map((t) => (
                  <SelectItem key={t.value} value={t.value} className="text-gray-900 hover:bg-gray-100">{t.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            {errors.container_type && <p className="text-xs text-red-400">{errors.container_type}</p>}
          </div>
          <div className="space-y-1.5">
            <Label className="text-gray-700 text-xs">Pickup Threshold (%)</Label>
            <Input type="number" min="1" max="100" {...f('pickup_threshold')} className="bg-white border-gray-200 text-gray-900 text-sm" />
            <p className="text-[10px] text-gray-400">Trigger a pickup notification when fill level reaches this %</p>
          </div>
          <div className="space-y-1.5">
            <Label className="text-gray-700 text-xs">Notes</Label>
            <Textarea {...f('notes')} rows={2} className="bg-white border-gray-200 text-gray-900 text-sm resize-none" />
          </div>
        </form>
        <DialogFooter className="gap-2">
          <Button variant="ghost" onClick={handleClose} className="text-gray-500 hover:text-gray-900">Cancel</Button>
          <Button onClick={handleSubmit as unknown as React.MouseEventHandler} disabled={mutation.isPending} className="bg-emerald-600 hover:bg-emerald-700 text-gray-900">
            {mutation.isPending ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Saving…</> : 'Register Container'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

