'use client'

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { disruptionsApi, jobsApi } from '@/lib/api'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { toast } from 'sonner'
import { Loader2 } from 'lucide-react'

interface DisruptionFormProps {
  open: boolean
  onClose: () => void
}

const DISRUPTION_TYPES = [
  { value: 'landfill_delay', label: 'Landfill Delay' },
  { value: 'highway_restriction', label: 'Highway Restriction' },
  { value: 'vehicle_breakdown', label: 'Vehicle Breakdown' },
  { value: 'site_access_denied', label: 'Site Access Denied' },
  { value: 'other', label: 'Other' },
]

const SEVERITY_OPTIONS = [
  { value: 'info', label: 'Info' },
  { value: 'warning', label: 'Warning' },
  { value: 'critical', label: 'Critical' },
]

export default function DisruptionForm({ open, onClose }: DisruptionFormProps) {
  const qc = useQueryClient()
  const [form, setForm] = useState({
    disruption_type: '',
    severity: 'warning',
    description: '',
  })
  const [selectedJobIds, setSelectedJobIds] = useState<string[]>([])
  const [errors, setErrors] = useState<Record<string, string>>({})

  const { data: jobsData } = useQuery({
    queryKey: ['jobs-active-disruption'],
    queryFn: () => jobsApi.list({ status: 'in_progress', limit: 50 } as Parameters<typeof jobsApi.list>[0]),
    enabled: open,
    staleTime: 60_000,
  })

  const activeJobs = (jobsData as { items?: { id: string; job_number: string; client_name?: string }[] } | null)?.items ?? []

  const mutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => disruptionsApi.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['disruptions'] })
      toast.success('Disruption logged')
      handleClose()
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { error?: { detail?: string } } } })?.response?.data?.error?.detail ?? 'Failed to log disruption'
      toast.error(msg)
    },
  })

  function validate() {
    const e: Record<string, string> = {}
    if (!form.disruption_type) e.disruption_type = 'Disruption type is required'
    if (!form.description.trim()) e.description = 'Description is required'
    if (selectedJobIds.length === 0) e.jobs = 'At least one affected job is required'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!validate()) return

    const payload: Record<string, unknown> = {
      disruption_type: form.disruption_type,
      severity: form.severity,
      description: form.description.trim(),
      affected_job_ids: selectedJobIds,
    }
    mutation.mutate(payload)
  }

  function handleClose() {
    setForm({ disruption_type: '', severity: 'warning', description: '' })
    setSelectedJobIds([])
    setErrors({})
    onClose()
  }

  function toggleJob(id: string) {
    setSelectedJobIds((ids) => ids.includes(id) ? ids.filter((i) => i !== id) : [...ids, id])
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && handleClose()}>
      <DialogContent className="bg-white border-gray-200 text-gray-900 max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader><DialogTitle className="text-gray-900">Log Incident</DialogTitle></DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 py-2">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-gray-700 text-xs">Type *</Label>
              <Select value={form.disruption_type} onValueChange={(v) => setForm((p) => ({ ...p, disruption_type: v }))}>
                <SelectTrigger className="bg-white border-gray-200 text-gray-900 text-sm">
                  <SelectValue placeholder="Select type…" />
                </SelectTrigger>
                <SelectContent className="bg-white border-gray-200">
                  {DISRUPTION_TYPES.map((t) => (
                    <SelectItem key={t.value} value={t.value} className="text-gray-900 hover:bg-gray-100">{t.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {errors.disruption_type && <p className="text-xs text-red-400">{errors.disruption_type}</p>}
            </div>

            <div className="space-y-1.5">
              <Label className="text-gray-700 text-xs">Severity *</Label>
              <Select value={form.severity} onValueChange={(v) => setForm((p) => ({ ...p, severity: v }))}>
                <SelectTrigger className="bg-white border-gray-200 text-gray-900 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-white border-gray-200">
                  {SEVERITY_OPTIONS.map((s) => (
                    <SelectItem key={s.value} value={s.value} className="text-gray-900 hover:bg-gray-100">{s.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label className="text-gray-700 text-xs">Description *</Label>
            <Textarea
              value={form.description}
              onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))}
              placeholder="Describe the incident and its impact…"
              rows={3}
              className="bg-white border-gray-200 text-gray-900 text-sm resize-none"
            />
            {errors.description && <p className="text-xs text-red-400">{errors.description}</p>}
          </div>

          <div className="space-y-2">
            <Label className="text-gray-700 text-xs">Affected Jobs * (select at least one)</Label>
            {errors.jobs && <p className="text-xs text-red-400">{errors.jobs}</p>}
            {activeJobs.length === 0 ? (
              <p className="text-xs text-gray-400 px-2">No active jobs found</p>
            ) : (
              <div className="max-h-36 overflow-y-auto space-y-1 border border-gray-200 rounded-lg p-2">
                {activeJobs.map((job) => (
                  <label key={job.id} className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-gray-50 cursor-pointer">
                    <input type="checkbox" checked={selectedJobIds.includes(job.id)} onChange={() => toggleJob(job.id)} className="accent-brand-500" />
                    <span className="text-xs font-mono text-brand-600">{job.job_number}</span>
                    {job.client_name && <span className="text-xs text-gray-500">{job.client_name}</span>}
                  </label>
                ))}
              </div>
            )}
          </div>
        </form>
        <DialogFooter className="gap-2">
          <Button variant="ghost" onClick={handleClose} className="text-gray-500 hover:text-gray-900">Cancel</Button>
          <Button onClick={handleSubmit as unknown as React.MouseEventHandler} disabled={mutation.isPending} className="bg-red-600 hover:bg-red-700 text-white">
            {mutation.isPending ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Logging…</> : 'Log Incident'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
