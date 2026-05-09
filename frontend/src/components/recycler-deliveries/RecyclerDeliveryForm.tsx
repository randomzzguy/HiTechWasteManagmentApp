'use client'

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { recyclerDeliveriesApi, equipmentApi } from '@/lib/api'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { toast } from 'sonner'
import { Loader2, Plus, Trash2 } from 'lucide-react'

interface RecyclerDeliveryFormProps {
  open: boolean
  onClose: () => void
}

const MATERIAL_TYPES = ['paper_kg', 'pet_kg', 'hdpe_kg', 'aluminium_kg', 'ferrous_kg', 'glass_kg', 'ewaste_kg']

export default function RecyclerDeliveryForm({ open, onClose }: RecyclerDeliveryFormProps) {
  const qc = useQueryClient()
  const [form, setForm] = useState({
    container_id: '',
    buyer_id: '',
    vehicle_id: '',
    planned_departure_at: '',
  })
  const [materials, setMaterials] = useState<Record<string, string>>({})
  const [errors, setErrors] = useState<Record<string, string>>({})

  const { data: containersData } = useQuery({
    queryKey: ['containers-at-site'],
    queryFn: () => equipmentApi.listContainers({ status: 'at_site' }),
    enabled: open,
    staleTime: 60_000,
  })

  // Fetch buyers from recyclables API
  const { data: buyersData } = useQuery({
    queryKey: ['downstream-buyers'],
    queryFn: () => fetch('/api/v1/recyclables/buyers', {
      headers: { Authorization: `Bearer ${sessionStorage.getItem('access_token')}` }
    }).then(r => r.json()),
    enabled: open,
    staleTime: 5 * 60_000,
  })

  const containers = containersData ?? []
  const buyers = (buyersData as { id: string; company_name: string }[] | null) ?? []

  const totalWeight = Object.values(materials).reduce((sum, v) => sum + (parseFloat(v) || 0), 0)

  const mutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => recyclerDeliveriesApi.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['recycler-deliveries'] })
      toast.success('Recycler delivery created')
      handleClose()
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { error?: { detail?: string } } } })?.response?.data?.error?.detail ?? 'Failed to create delivery'
      toast.error(msg)
    },
  })

  function validate() {
    const e: Record<string, string> = {}
    if (!form.container_id) e.container_id = 'Container is required'
    if (!form.buyer_id) e.buyer_id = 'Buyer is required'
    if (totalWeight <= 0) e.materials = 'At least one material weight is required'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!validate()) return

    const breakdown: Record<string, number> = {}
    Object.entries(materials).forEach(([k, v]) => {
      if (v && parseFloat(v) > 0) breakdown[k] = parseFloat(v)
    })

    const payload: Record<string, unknown> = {
      container_id: form.container_id,
      buyer_id: form.buyer_id,
      declared_material_breakdown: breakdown,
      declared_total_weight_kg: totalWeight,
    }
    if (form.vehicle_id) payload.vehicle_id = form.vehicle_id
    if (form.planned_departure_at) payload.planned_departure_at = new Date(form.planned_departure_at).toISOString()

    mutation.mutate(payload)
  }

  function handleClose() {
    setForm({ container_id: '', buyer_id: '', vehicle_id: '', planned_departure_at: '' })
    setMaterials({})
    setErrors({})
    onClose()
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && handleClose()}>
      <DialogContent className="bg-white border-gray-200 text-gray-900 max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader><DialogTitle className="text-gray-900">New Recycler Delivery</DialogTitle></DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 py-2">
          <div className="space-y-1.5">
            <Label className="text-gray-700 text-xs">Container *</Label>
            <Select value={form.container_id} onValueChange={(v) => setForm((p) => ({ ...p, container_id: v }))}>
              <SelectTrigger className="bg-white border-gray-200 text-gray-900 text-sm">
                <SelectValue placeholder="Select container at site…" />
              </SelectTrigger>
              <SelectContent className="bg-white border-gray-200">
                {containers.map((c) => (
                  <SelectItem key={c.id} value={c.id} className="text-gray-900 hover:bg-gray-100">
                    {c.container_code} — {c.target_material_type ?? 'mixed'} ({c.fill_level}% full)
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {errors.container_id && <p className="text-xs text-red-400">{errors.container_id}</p>}
          </div>

          <div className="space-y-1.5">
            <Label className="text-gray-700 text-xs">Downstream Buyer *</Label>
            <Select value={form.buyer_id} onValueChange={(v) => setForm((p) => ({ ...p, buyer_id: v }))}>
              <SelectTrigger className="bg-white border-gray-200 text-gray-900 text-sm">
                <SelectValue placeholder="Select recycler…" />
              </SelectTrigger>
              <SelectContent className="bg-white border-gray-200">
                {buyers.map((b) => (
                  <SelectItem key={b.id} value={b.id} className="text-gray-900 hover:bg-gray-100">{b.company_name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            {errors.buyer_id && <p className="text-xs text-red-400">{errors.buyer_id}</p>}
          </div>

          <div className="space-y-1.5">
            <Label className="text-gray-700 text-xs">Planned Departure</Label>
            <Input type="datetime-local" value={form.planned_departure_at}
              onChange={(e) => setForm((p) => ({ ...p, planned_departure_at: e.target.value }))}
              className="bg-white border-gray-200 text-gray-900 text-sm" />
          </div>

          <Separator className="bg-gray-100" />

          <div className="space-y-2">
            <Label className="text-gray-700 text-xs">Material Breakdown (kg) *</Label>
            {errors.materials && <p className="text-xs text-red-400">{errors.materials}</p>}
            <div className="grid grid-cols-2 gap-2">
              {MATERIAL_TYPES.map((mat) => (
                <div key={mat} className="flex items-center gap-2">
                  <span className="text-xs text-gray-500 w-20 capitalize">{mat.replace('_kg', '')}</span>
                  <Input type="number" min="0" step="0.01"
                    value={materials[mat] ?? ''}
                    onChange={(e) => setMaterials((m) => ({ ...m, [mat]: e.target.value }))}
                    placeholder="0" className="bg-white border-gray-200 text-gray-900 text-xs h-8 flex-1" />
                </div>
              ))}
            </div>
            {totalWeight > 0 && (
              <div className="flex items-center justify-between px-3 py-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                <span className="text-xs text-gray-500">Total Declared Weight</span>
                <span className="text-sm font-bold text-emerald-400">{totalWeight.toFixed(2)} kg</span>
              </div>
            )}
          </div>
        </form>
        <DialogFooter className="gap-2">
          <Button variant="ghost" onClick={handleClose} className="text-gray-500 hover:text-gray-900">Cancel</Button>
          <Button onClick={handleSubmit as unknown as React.MouseEventHandler} disabled={mutation.isPending} className="bg-emerald-600 hover:bg-emerald-700 text-gray-900">
            {mutation.isPending ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Creating…</> : 'Create Delivery'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

