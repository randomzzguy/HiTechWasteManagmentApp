'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { disruptionsApi } from '@/lib/api'
import { DisruptionLog, DisruptionType, DisruptionSeverity } from '@/types/operational-field'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { AlertTriangle, CheckCircle2, Clock, Truck, MapPin, Factory } from 'lucide-react'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'
import DisruptionForm from '@/components/disruptions/DisruptionForm'

// ── Helpers ───────────────────────────────────────────────────

const severityColor: Record<string, string> = {
  info: 'bg-brand-500/15 text-brand-400 border-brand-500/30',
  warning: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
  critical: 'bg-red-500/15 text-red-400 border-red-500/30',
}

const typeIcon: Record<string, React.ElementType> = {
  landfill_delay: Factory,
  highway_restriction: MapPin,
  vehicle_breakdown: Truck,
  site_access_denied: AlertTriangle,
  other: AlertTriangle,
}

const typeLabel: Record<string, string> = {
  landfill_delay: 'Landfill Delay',
  highway_restriction: 'Highway Restriction',
  vehicle_breakdown: 'Vehicle Breakdown',
  site_access_denied: 'Site Access Denied',
  other: 'Other',
}

function SeverityBadge({ severity }: { severity: string }) {
  return (
    <span className={cn('inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border capitalize', severityColor[severity])}>
      {severity}
    </span>
  )
}

function elapsed(dateStr: string): string {
  const ms = Date.now() - new Date(dateStr).getTime()
  const h = Math.floor(ms / 3600000)
  const m = Math.floor((ms % 3600000) / 60000)
  if (h > 0) return `${h}h ${m}m ago`
  return `${m}m ago`
}

// ── Main page ─────────────────────────────────────────────────

export default function DisruptionsPage() {
  const [statusFilter, setStatusFilter] = useState<string>('open')
  const [typeFilter, setTypeFilter] = useState<string>('all')
  const [formOpen, setFormOpen] = useState(false)
  const queryClient = useQueryClient()

  const { data: disruptions = [], isLoading } = useQuery({
    queryKey: ['disruptions', statusFilter, typeFilter],
    queryFn: () =>
      disruptionsApi.list({
        status: statusFilter === 'all' ? undefined : statusFilter,
        disruption_type: typeFilter === 'all' ? undefined : typeFilter,
      }),
  })

  const openCount = disruptions.filter((d) => d.status === 'open').length
  const criticalCount = disruptions.filter((d) => d.severity === 'critical' && d.status === 'open').length

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Incidents</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Operational incident log — landfill delays, highway restrictions, breakdowns
          </p>
        </div>
        <Button className="bg-emerald-600 hover:bg-emerald-700 text-white text-sm" onClick={() => setFormOpen(true)}>
          + Log Disruption
        </Button>
      </div>

      <DisruptionForm open={formOpen} onClose={() => setFormOpen(false)} />

      {/* Alert banner for critical open disruptions */}
      {criticalCount > 0 && (
        <div className="flex items-center gap-3 p-3 rounded-lg bg-red-500/10 border border-red-500/30">
          <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0" />
          <p className="text-sm text-red-300">
            <span className="font-semibold">{criticalCount} critical disruption(s)</span> require immediate attention.
          </p>
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-3">
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-36 bg-white border-gray-300 text-gray-700 text-sm">
            <SelectValue />
          </SelectTrigger>
          <SelectContent className="bg-white border-gray-200">
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="open">Open</SelectItem>
            <SelectItem value="resolved">Resolved</SelectItem>
          </SelectContent>
        </Select>

        <Select value={typeFilter} onValueChange={setTypeFilter}>
          <SelectTrigger className="w-48 bg-white border-gray-300 text-gray-700 text-sm">
            <SelectValue />
          </SelectTrigger>
          <SelectContent className="bg-white border-gray-200">
            <SelectItem value="all">All types</SelectItem>
            <SelectItem value="landfill_delay">Landfill Delay</SelectItem>
            <SelectItem value="highway_restriction">Highway Restriction</SelectItem>
            <SelectItem value="vehicle_breakdown">Vehicle Breakdown</SelectItem>
            <SelectItem value="site_access_denied">Site Access Denied</SelectItem>
            <SelectItem value="other">Other</SelectItem>
          </SelectContent>
        </Select>

        <div className="ml-auto flex items-center gap-2 text-sm text-gray-500">
          <span className="font-medium text-gray-900">{openCount}</span> open
          {criticalCount > 0 && (
            <span className="text-red-400 font-medium">· {criticalCount} critical</span>
          )}
        </div>
      </div>

      {/* Table */}
      <Card className="bg-white border-gray-200">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow className="border-gray-200 hover:bg-transparent">
                <TableHead className="text-gray-500">Type</TableHead>
                <TableHead className="text-gray-500">Severity</TableHead>
                <TableHead className="text-gray-500">Description</TableHead>
                <TableHead className="text-gray-500">Jobs Affected</TableHead>
                <TableHead className="text-gray-500">Occurred</TableHead>
                <TableHead className="text-gray-500">Status</TableHead>
                <TableHead className="text-gray-500">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-gray-400 py-8">Loading…</TableCell>
                </TableRow>
              ) : disruptions.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-gray-400 py-8">
                    {statusFilter === 'open' ? 'No open disruptions — all clear!' : 'No disruptions found'}
                  </TableCell>
                </TableRow>
              ) : (
                disruptions.map((d) => {
                  const Icon = typeIcon[d.disruption_type] ?? AlertTriangle
                  return (
                    <TableRow key={d.id} className="border-gray-200 hover:bg-gray-50">
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Icon className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
                          <span className="text-sm text-gray-700">{typeLabel[d.disruption_type]}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <SeverityBadge severity={d.severity} />
                      </TableCell>
                      <TableCell className="text-gray-700 text-sm max-w-[220px] truncate">
                        {d.description}
                      </TableCell>
                      <TableCell className="text-gray-700 text-sm">
                        {d.affected_job_ids?.length ?? 0}
                      </TableCell>
                      <TableCell className="text-gray-500 text-xs whitespace-nowrap">
                        {elapsed(d.occurred_at)}
                      </TableCell>
                      <TableCell>
                        <span className={cn(
                          'inline-flex items-center gap-1 text-xs font-medium',
                          d.status === 'open' ? 'text-amber-400' : 'text-emerald-400'
                        )}>
                          {d.status === 'open' ? (
                            <Clock className="w-3 h-3" />
                          ) : (
                            <CheckCircle2 className="w-3 h-3" />
                          )}
                          {d.status}
                        </span>
                      </TableCell>
                      <TableCell>
                        {d.status === 'open' && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-xs text-gray-500 hover:text-gray-900 h-7 px-2"
                          >
                            Resolve
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  )
                })
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
