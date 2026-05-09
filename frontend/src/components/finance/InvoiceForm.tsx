'use client'

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { financeApi, clientsApi, jobsApi } from '@/lib/api'
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

interface InvoiceFormProps {
  open: boolean
  onClose: () => void
  onSuccess?: (invoiceId: string) => void
}

interface LineItem {
  description: string
  quantity: string
  unit_price_myr: string
  unit: string
}

// ── Form ──────────────────────────────────────────────────────

export default function InvoiceForm({ open, onClose, onSuccess }: InvoiceFormProps) {
  const qc = useQueryClient()

  const [form, setForm] = useState({
    client_id: '',
    issue_date: new Date().toISOString().split('T')[0],
    due_date: '',
    tax_rate: '0',
    notes: '',
  })

  const [lineItems, setLineItems] = useState<LineItem[]>([
    { description: '', quantity: '1', unit_price_myr: '', unit: 'trip' },
  ])

  const [selectedJobIds, setSelectedJobIds] = useState<string[]>([])
  const [errors, setErrors] = useState<Record<string, string>>({})

  // Fetch clients
  const { data: clientsData } = useQuery({
    queryKey: ['clients-dropdown'],
    queryFn: () => clientsApi.list({ limit: 200, is_active: true } as Parameters<typeof clientsApi.list>[0]),
    staleTime: 5 * 60_000,
    enabled: open,
  })

  // Fetch completed jobs for selected client
  const { data: jobsData } = useQuery({
    queryKey: ['jobs-completed', form.client_id],
    queryFn: () => jobsApi.list({
      client_id: form.client_id,
      status: 'completed',
      limit: 100,
    } as Parameters<typeof jobsApi.list>[0]),
    enabled: open && !!form.client_id,
    staleTime: 60_000,
  })

  const clients = (clientsData as { items?: { id: string; company_name: string }[] } | null)?.items ?? []
  const completedJobs = (jobsData as { items?: { id: string; job_number: string; job_type: string; scheduled_date?: string }[] } | null)?.items ?? []

  // Compute totals
  const subtotal = lineItems.reduce((sum, item) => {
    const qty = parseFloat(item.quantity) || 0
    const price = parseFloat(item.unit_price_myr) || 0
    return sum + qty * price
  }, 0)
  const taxRate = parseFloat(form.tax_rate) || 0
  const taxAmount = subtotal * (taxRate / 100)
  const total = subtotal + taxAmount

  const mutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => financeApi.createInvoice(data),
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ['finance'] })
      toast.success(`Invoice ${(result as Record<string, string>).invoice_number} created`)
      onSuccess?.((result as Record<string, string>).id)
      handleClose()
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { error?: { detail?: string } } } })
        ?.response?.data?.error?.detail ?? 'Failed to create invoice'
      toast.error(msg)
    },
  })

  function validate(): boolean {
    const e: Record<string, string> = {}
    if (!form.client_id) e.client_id = 'Client is required'
    if (!form.issue_date) e.issue_date = 'Issue date is required'
    if (lineItems.every((li) => !li.description.trim())) {
      e.line_items = 'At least one line item with a description is required'
    }
    setErrors(e)
    return Object.keys(e).length === 0
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!validate()) return

    const validLineItems = lineItems
      .filter((li) => li.description.trim())
      .map((li) => ({
        description: li.description.trim(),
        quantity: parseFloat(li.quantity) || 1,
        unit_price_myr: parseFloat(li.unit_price_myr) || 0,
        unit: li.unit || 'trip',
        line_total_myr: (parseFloat(li.quantity) || 1) * (parseFloat(li.unit_price_myr) || 0),
      }))

    const payload: Record<string, unknown> = {
      client_id: form.client_id,
      issue_date: form.issue_date,
      line_items: validLineItems,
      subtotal_myr: subtotal,
      tax_myr: taxAmount,
      total_myr: total,
    }
    if (form.due_date) payload.due_date = form.due_date
    if (form.notes.trim()) payload.notes = form.notes.trim()
    if (selectedJobIds.length > 0) payload.job_ids = selectedJobIds

    mutation.mutate(payload)
  }

  function handleClose() {
    setForm({
      client_id: '', issue_date: new Date().toISOString().split('T')[0],
      due_date: '', tax_rate: '0', notes: '',
    })
    setLineItems([{ description: '', quantity: '1', unit_price_myr: '', unit: 'trip' }])
    setSelectedJobIds([])
    setErrors({})
    onClose()
  }

  function addLineItem() {
    setLineItems((li) => [...li, { description: '', quantity: '1', unit_price_myr: '', unit: 'trip' }])
  }

  function removeLineItem(i: number) {
    setLineItems((li) => li.filter((_, idx) => idx !== i))
  }

  function updateLineItem(i: number, key: keyof LineItem, value: string) {
    setLineItems((li) => li.map((item, idx) => idx === i ? { ...item, [key]: value } : item))
  }

  function toggleJob(jobId: string) {
    setSelectedJobIds((ids) =>
      ids.includes(jobId) ? ids.filter((id) => id !== jobId) : [...ids, jobId]
    )
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
          <DialogTitle className="text-gray-900">New Invoice</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-5 py-2">
          {/* Client + dates */}
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-3 space-y-1.5">
              <Label className="text-gray-600 text-xs">Client *</Label>
              <Select value={form.client_id} onValueChange={(v) => {
                setForm((f) => ({ ...f, client_id: v }))
                setSelectedJobIds([])
              }}>
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
            <div className="space-y-1.5">
              <Label className="text-gray-600 text-xs">Issue Date *</Label>
              <Input type="date" {...f('issue_date')}
                className="bg-white border-gray-300 text-gray-900 text-sm" />
              {errors.issue_date && <p className="text-xs text-red-500">{errors.issue_date}</p>}
            </div>
            <div className="space-y-1.5">
              <Label className="text-gray-600 text-xs">Due Date</Label>
              <Input type="date" {...f('due_date')}
                className="bg-white border-gray-300 text-gray-900 text-sm" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-gray-600 text-xs">Tax Rate (%)</Label>
              <Input type="number" min="0" max="100" step="0.1" {...f('tax_rate')}
                placeholder="0" className="bg-white border-gray-300 text-gray-900 text-sm" />
            </div>
          </div>

          {/* Link completed jobs */}
          {form.client_id && completedJobs.length > 0 && (
            <>
              <Separator className="bg-gray-200" />
              <div className="space-y-2">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                  Link Completed Jobs (optional)
                </p>
                <div className="max-h-32 overflow-y-auto space-y-1">
                  {completedJobs.map((job) => (
                    <label key={job.id} className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-gray-50 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={selectedJobIds.includes(job.id)}
                        onChange={() => toggleJob(job.id)}
                        className="accent-emerald-500"
                      />
                      <span className="text-xs font-mono text-emerald-400">{job.job_number}</span>
                      <span className="text-xs text-gray-500">{job.job_type.replace(/_/g, ' ')}</span>
                      {job.scheduled_date && (
                        <span className="text-xs text-gray-400 ml-auto">{job.scheduled_date}</span>
                      )}
                    </label>
                  ))}
                </div>
              </div>
            </>
          )}

          <Separator className="bg-gray-200" />

          {/* Line items */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Line Items *</p>
              <Button type="button" variant="ghost" size="sm" onClick={addLineItem}
                className="text-xs text-emerald-400 hover:text-emerald-300 h-7 px-2">
                <Plus className="w-3 h-3 mr-1" /> Add Line
              </Button>
            </div>
            {errors.line_items && <p className="text-xs text-red-500">{errors.line_items}</p>}

            {/* Header */}
            <div className="grid grid-cols-12 gap-2 px-1">
              {['Description', 'Qty', 'Unit', 'Unit Price (MYR)', ''].map((h) => (
                <p key={h} className={`text-[10px] text-gray-500 font-semibold uppercase ${h === 'Description' ? 'col-span-5' : h === '' ? 'col-span-1' : 'col-span-2'}`}>{h}</p>
              ))}
            </div>

            {lineItems.map((item, i) => (
              <div key={i} className="grid grid-cols-12 gap-2 items-center">
                <div className="col-span-5">
                  <Input value={item.description}
                    onChange={(e) => updateLineItem(i, 'description', e.target.value)}
                    placeholder="e.g. Waste collection service — June 2025"
                    className="bg-white border-gray-300 text-gray-900 text-xs h-8" />
                </div>
                <div className="col-span-2">
                  <Input type="number" min="0" step="0.01" value={item.quantity}
                    onChange={(e) => updateLineItem(i, 'quantity', e.target.value)}
                    className="bg-white border-gray-300 text-gray-900 text-xs h-8" />
                </div>
                <div className="col-span-2">
                  <Select value={item.unit} onValueChange={(v) => updateLineItem(i, 'unit', v)}>
                    <SelectTrigger className="bg-white border-gray-300 text-gray-900 text-xs h-8">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-white border-gray-200">
                      {['trip', 'tonne', 'month', 'unit', 'hour', 'lot'].map((u) => (
                        <SelectItem key={u} value={u} className="text-gray-900 text-xs hover:bg-gray-50">{u}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="col-span-2">
                  <Input type="number" min="0" step="0.01" value={item.unit_price_myr}
                    onChange={(e) => updateLineItem(i, 'unit_price_myr', e.target.value)}
                    placeholder="0.00"
                    className="bg-white border-gray-300 text-gray-900 text-xs h-8" />
                </div>
                <div className="col-span-1 flex justify-center">
                  {lineItems.length > 1 && (
                    <Button type="button" variant="ghost" size="sm" onClick={() => removeLineItem(i)}
                      className="h-8 w-8 p-0 text-slate-500 hover:text-red-500">
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                  )}
                </div>
              </div>
            ))}

            {/* Totals */}
            <div className="flex flex-col items-end gap-1 pt-2 border-t border-gray-200">
              <div className="flex items-center gap-8 text-xs">
                <span className="text-gray-500">Subtotal</span>
                <span className="text-gray-900 font-mono w-24 text-right">MYR {subtotal.toFixed(2)}</span>
              </div>
              <div className="flex items-center gap-8 text-xs">
                <span className="text-gray-500">Tax ({taxRate}%)</span>
                <span className="text-gray-900 font-mono w-24 text-right">MYR {taxAmount.toFixed(2)}</span>
              </div>
              <div className="flex items-center gap-8 text-sm font-semibold">
                <span className="text-gray-900">Total</span>
                <span className="text-emerald-400 font-mono w-24 text-right">MYR {total.toFixed(2)}</span>
              </div>
            </div>
          </div>

          {/* Notes */}
          <div className="space-y-1.5">
            <Label className="text-gray-600 text-xs">Notes</Label>
            <Textarea {...f('notes')} placeholder="Payment terms, bank details, or other notes…" rows={2}
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
            ) : `Create Invoice — MYR ${total.toFixed(2)}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

