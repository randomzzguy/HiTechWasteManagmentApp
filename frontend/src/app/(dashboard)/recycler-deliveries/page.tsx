'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { recyclerDeliveriesApi } from '@/lib/api'
import { RecyclerDelivery, DeliveryStatus } from '@/types/operational-field'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { AlertTriangle, CheckCircle2, Clock, Truck, Package } from 'lucide-react'
import { cn } from '@/lib/utils'
import RecyclerDeliveryForm from '@/components/recycler-deliveries/RecyclerDeliveryForm'

// ── Helpers ───────────────────────────────────────────────────

const statusColor: Record<string, string> = {
  pending_departure: 'bg-slate-500/15 text-gray-500 border-slate-500/30',
  in_transit: 'bg-brand-500/15 text-brand-400 border-brand-500/30',
  arrived: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30',
  proof_submitted: 'bg-violet-500/15 text-violet-400 border-violet-500/30',
  reconciliation_discrepancy: 'bg-red-500/15 text-red-400 border-red-500/30',
  completed: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  cancelled: 'bg-slate-600/15 text-gray-400 border-gray-300/30',
}

const statusLabel: Record<string, string> = {
  pending_departure: 'Pending Departure',
  in_transit: 'In Transit',
  arrived: 'Arrived',
  proof_submitted: 'Proof Submitted',
  reconciliation_discrepancy: 'Discrepancy',
  completed: 'Completed',
  cancelled: 'Cancelled',
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={cn(
      'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border',
      statusColor[status] ?? 'bg-slate-500/15 text-gray-500 border-slate-500/30'
    )}>
      {statusLabel[status] ?? status}
    </span>
  )
}

function formatWeight(kg?: number): string {
  if (kg == null) return '—'
  return `${kg.toLocaleString()} kg`
}

// ── Main page ─────────────────────────────────────────────────

export default function RecyclerDeliveriesPage() {
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [formOpen, setFormOpen] = useState(false)

  const { data: deliveries = [], isLoading } = useQuery({
    queryKey: ['recycler-deliveries', statusFilter],
    queryFn: () =>
      recyclerDeliveriesApi.list({
        status: statusFilter === 'all' ? undefined : statusFilter,
      }),
  })

  const discrepancies = deliveries.filter((d) => d.status === 'reconciliation_discrepancy').length
  const inTransit = deliveries.filter((d) => d.status === 'in_transit').length
  const pending = deliveries.filter((d) => d.status === 'pending_departure').length

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Recycler Deliveries</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Container-to-recycler delivery tracking with proof of delivery
          </p>
        </div>
        <Button className="bg-emerald-600 hover:bg-emerald-700 text-gray-900 text-sm" onClick={() => setFormOpen(true)}>
          + New Delivery
        </Button>
      </div>

      <RecyclerDeliveryForm open={formOpen} onClose={() => setFormOpen(false)} />

      {/* Discrepancy alert */}
      {discrepancies > 0 && (
        <div className="flex items-center gap-3 p-3 rounded-lg bg-red-500/10 border border-red-500/30">
          <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0" />
          <p className="text-sm text-red-300">
            <span className="font-semibold">{discrepancies} delivery/deliveries</span> have weight reconciliation discrepancies requiring review.
          </p>
        </div>
      )}

      {/* Summary pills */}
      <div className="flex gap-3 flex-wrap">
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white border border-gray-200">
          <Truck className="w-3.5 h-3.5 text-brand-400" />
          <span className="text-sm text-gray-700"><span className="font-semibold text-gray-900">{inTransit}</span> in transit</span>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white border border-gray-200">
          <Clock className="w-3.5 h-3.5 text-gray-400" />
          <span className="text-sm text-gray-700"><span className="font-semibold text-gray-900">{pending}</span> pending departure</span>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white border border-gray-200">
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
          <span className="text-sm text-gray-700">
            <span className="font-semibold text-gray-900">
              {deliveries.filter((d) => d.status === 'completed').length}
            </span> completed
          </span>
        </div>
      </div>

      {/* Filter */}
      <div className="flex gap-3">
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-52 bg-white border-gray-300 text-gray-700 text-sm">
            <SelectValue />
          </SelectTrigger>
          <SelectContent className="bg-white border-gray-200">
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="pending_departure">Pending Departure</SelectItem>
            <SelectItem value="in_transit">In Transit</SelectItem>
            <SelectItem value="arrived">Arrived</SelectItem>
            <SelectItem value="proof_submitted">Proof Submitted</SelectItem>
            <SelectItem value="reconciliation_discrepancy">Discrepancy</SelectItem>
            <SelectItem value="completed">Completed</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <Card className="bg-white border-gray-200">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow className="border-gray-200 hover:bg-transparent">
                <TableHead className="text-gray-500">Delivery ID</TableHead>
                <TableHead className="text-gray-500">Status</TableHead>
                <TableHead className="text-gray-500">Declared Weight</TableHead>
                <TableHead className="text-gray-500">Recycler Weight</TableHead>
                <TableHead className="text-gray-500">Variance</TableHead>
                <TableHead className="text-gray-500">Planned Departure</TableHead>
                <TableHead className="text-gray-500">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-gray-400 py-8">Loading…</TableCell>
                </TableRow>
              ) : deliveries.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-gray-400 py-8">No deliveries found</TableCell>
                </TableRow>
              ) : (
                deliveries.map((d) => (
                  <TableRow key={d.id} className="border-gray-200 hover:bg-gray-50">
                    <TableCell className="font-mono text-xs text-gray-500">{d.id.slice(0, 8)}…</TableCell>
                    <TableCell>
                      <StatusBadge status={d.status} />
                    </TableCell>
                    <TableCell className="text-gray-700 text-sm">
                      {formatWeight(d.declared_total_weight_kg)}
                    </TableCell>
                    <TableCell className="text-gray-700 text-sm">
                      {formatWeight(d.recycler_recorded_weight_kg)}
                    </TableCell>
                    <TableCell>
                      {d.weight_variance_pct != null ? (
                        <span className={cn(
                          'text-sm font-medium',
                          d.weight_variance_pct > 5 ? 'text-red-400' : 'text-emerald-400'
                        )}>
                          {d.weight_variance_pct.toFixed(1)}%
                        </span>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </TableCell>
                    <TableCell className="text-gray-500 text-xs">
                      {d.planned_departure_at
                        ? new Date(d.planned_departure_at).toLocaleDateString('en-MY', {
                            day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
                          })
                        : '—'}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        {d.status === 'pending_departure' && (
                          <Button variant="ghost" size="sm" className="text-xs text-brand-400 hover:text-brand-300 h-7 px-2">
                            Depart
                          </Button>
                        )}
                        {d.status === 'in_transit' && (
                          <Button variant="ghost" size="sm" className="text-xs text-cyan-400 hover:text-cyan-300 h-7 px-2">
                            Arrived
                          </Button>
                        )}
                        {d.status === 'arrived' && (
                          <Button variant="ghost" size="sm" className="text-xs text-violet-400 hover:text-violet-300 h-7 px-2">
                            Submit Proof
                          </Button>
                        )}
                        {d.status === 'reconciliation_discrepancy' && (
                          <Button variant="ghost" size="sm" className="text-xs text-red-400 hover:text-red-300 h-7 px-2">
                            Review
                          </Button>
                        )}
                        {d.status === 'proof_submitted' && (
                          <Button variant="ghost" size="sm" className="text-xs text-emerald-400 hover:text-emerald-300 h-7 px-2">
                            Confirm
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}

