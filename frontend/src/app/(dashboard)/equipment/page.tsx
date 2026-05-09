'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { equipmentApi } from '@/lib/api'
import { CompactionMachine, Container } from '@/types/operational-field'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { AlertTriangle, CheckCircle2, Clock, Package, Wrench } from 'lucide-react'
import { cn } from '@/lib/utils'
import CompactorForm from '@/components/equipment/CompactorForm'
import ContainerForm from '@/components/equipment/ContainerForm'

// ── Status badge helpers ──────────────────────────────────────

const compactorStatusColor: Record<string, string> = {
  available:      'bg-green-50 text-green-600 border-green-200',
  deployed:       'bg-brand-50 text-brand-600 border-brand-200',
  maintenance:    'bg-amber-50 text-amber-600 border-amber-200',
  decommissioned: 'bg-gray-100 text-gray-500 border-gray-300',
}

const containerStatusColor: Record<string, string> = {
  available:      'bg-green-50 text-green-600 border-green-200',
  at_site:        'bg-brand-50 text-brand-600 border-brand-200',
  in_transit:     'bg-violet-50 text-violet-600 border-violet-200',
  at_recycler:    'bg-cyan-50 text-cyan-600 border-cyan-200',
  decommissioned: 'bg-gray-100 text-gray-500 border-gray-300',
}

function StatusBadge({ status, colorMap }: { status: string; colorMap: Record<string, string> }) {
  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border',
        colorMap[status] ?? 'bg-gray-100 text-gray-500 border-gray-300'
      )}
    >
      {status.replace(/_/g, ' ')}
    </span>
  )
}

function FillBar({ level, threshold }: { level: number; threshold: number }) {
  const isHigh = level >= threshold
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
        <div
          className={cn(
            'h-full rounded-full transition-all',
            isHigh ? 'bg-red-500' : level > 60 ? 'bg-amber-500' : 'bg-emerald-500'
          )}
          style={{ width: `${level}%` }}
        />
      </div>
      <span className={cn('text-xs font-mono w-8 text-right', isHigh ? 'text-red-400' : 'text-gray-500')}>
        {level}%
      </span>
    </div>
  )
}

// ── Summary cards ─────────────────────────────────────────────

function SummaryCard({
  title,
  value,
  icon: Icon,
  color,
}: {
  title: string
  value: number
  icon: React.ElementType
  color: string
}) {
  return (
    <Card className="bg-white border-gray-200">
      <CardContent className="p-4 flex items-center gap-3">
        <div className={cn('p-2 rounded-lg', color)}>
          <Icon className="w-4 h-4" />
        </div>
        <div>
          <p className="text-2xl font-bold text-gray-900">{value}</p>
          <p className="text-xs text-gray-500">{title}</p>
        </div>
      </CardContent>
    </Card>
  )
}

// ── Main page ─────────────────────────────────────────────────

export default function EquipmentPage() {
  const [tab, setTab] = useState('compactors')
  const [compactorFormOpen, setCompactorFormOpen] = useState(false)
  const [containerFormOpen, setContainerFormOpen] = useState(false)

  const { data: compactors = [], isLoading: loadingCompactors } = useQuery({
    queryKey: ['compactors'],
    queryFn: () => equipmentApi.listCompactors(),
  })

  const { data: containers = [], isLoading: loadingContainers } = useQuery({
    queryKey: ['containers'],
    queryFn: () => equipmentApi.listContainers(),
  })

  const { data: dueService = [] } = useQuery({
    queryKey: ['compactors-due-service'],
    queryFn: () => equipmentApi.getDueService(),
  })

  // Summary counts
  const compactorCounts = compactors.reduce(
    (acc, m) => ({ ...acc, [m.status]: (acc[m.status] ?? 0) + 1 }),
    {} as Record<string, number>
  )
  const containerCounts = containers.reduce(
    (acc, c) => ({ ...acc, [c.status]: (acc[c.status] ?? 0) + 1 }),
    {} as Record<string, number>
  )
  const needsPickup = containers.filter(
    (c) => c.fill_level >= c.pickup_threshold && c.status === 'at_site'
  ).length

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Equipment</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Compaction machines and container inventory
          </p>
        </div>
        <Button
          className="bg-emerald-600 hover:bg-emerald-700 text-white text-sm"
          onClick={() => tab === 'compactors' ? setCompactorFormOpen(true) : setContainerFormOpen(true)}
        >
          + {tab === 'compactors' ? 'Add Compactor' : 'Add Container'}
        </Button>
      </div>

      <CompactorForm open={compactorFormOpen} onClose={() => setCompactorFormOpen(false)} />
      <ContainerForm open={containerFormOpen} onClose={() => setContainerFormOpen(false)} />

      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <SummaryCard
          title="Compactors deployed"
          value={compactorCounts.deployed ?? 0}
          icon={Wrench}
          color="bg-brand-50 text-brand-600"
        />
        <SummaryCard
          title="Service due soon"
          value={dueService.length}
          icon={Clock}
          color="bg-amber-50 text-amber-600"
        />
        <SummaryCard
          title="Containers at site"
          value={containerCounts.at_site ?? 0}
          icon={Package}
          color="bg-violet-50 text-violet-600"
        />
        <SummaryCard
          title="Pickup needed"
          value={needsPickup}
          icon={AlertTriangle}
          color="bg-red-50 text-red-600"
        />
      </div>

      {/* Tabs */}
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="bg-gray-100 border border-gray-200">
          <TabsTrigger value="compactors" className="data-[state=active]:bg-white text-gray-700">
            Compaction Machines ({compactors.length})
          </TabsTrigger>
          <TabsTrigger value="containers" className="data-[state=active]:bg-white text-gray-700">
            Containers ({containers.length})
          </TabsTrigger>
        </TabsList>

        {/* Compactors tab */}
        <TabsContent value="compactors">
          <Card className="bg-white border-gray-200">
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow className="border-gray-200 hover:bg-transparent">
                    <TableHead className="text-gray-500">Asset Tag</TableHead>
                    <TableHead className="text-gray-500">Model</TableHead>
                    <TableHead className="text-gray-500">Status</TableHead>
                    <TableHead className="text-gray-500">Next Service</TableHead>
                    <TableHead className="text-gray-500">Force (kN)</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loadingCompactors ? (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center text-gray-400 py-8">
                        Loading…
                      </TableCell>
                    </TableRow>
                  ) : compactors.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center text-gray-400 py-8">
                        No compaction machines registered
                      </TableCell>
                    </TableRow>
                  ) : (
                    compactors.map((m) => (
                      <TableRow key={m.id} className="border-gray-200 hover:bg-gray-50">
                        <TableCell className="font-mono text-sm text-gray-900">{m.asset_tag}</TableCell>
                        <TableCell className="text-gray-700">{m.model_name}</TableCell>
                        <TableCell>
                          <StatusBadge status={m.status} colorMap={compactorStatusColor} />
                        </TableCell>
                        <TableCell className="text-gray-700 text-sm">
                          {m.next_service_date ? (
                            <span
                              className={cn(
                                new Date(m.next_service_date) <= new Date()
                                  ? 'text-red-400 font-medium'
                                  : 'text-gray-700'
                              )}
                            >
                              {m.next_service_date}
                            </span>
                          ) : (
                            <span className="text-gray-400">—</span>
                          )}
                        </TableCell>
                        <TableCell className="text-gray-700 text-sm">
                          {m.compaction_force_kn ?? '—'}
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Containers tab */}
        <TabsContent value="containers">
          <Card className="bg-white border-gray-200">
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow className="border-gray-200 hover:bg-transparent">
                    <TableHead className="text-gray-500">Code</TableHead>
                    <TableHead className="text-gray-500">Type</TableHead>
                    <TableHead className="text-gray-500">Status</TableHead>
                    <TableHead className="text-gray-500">Fill Level</TableHead>
                    <TableHead className="text-gray-500">Material</TableHead>
                    <TableHead className="text-gray-500">Site</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loadingContainers ? (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center text-gray-400 py-8">
                        Loading…
                      </TableCell>
                    </TableRow>
                  ) : containers.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center text-gray-400 py-8">
                        No containers registered
                      </TableCell>
                    </TableRow>
                  ) : (
                    containers.map((c) => (
                      <TableRow key={c.id} className="border-gray-200 hover:bg-gray-50">
                        <TableCell className="font-mono text-sm text-gray-900">{c.container_code}</TableCell>
                        <TableCell className="text-gray-700 text-sm capitalize">
                          {c.container_type.replace(/_/g, ' ')}
                        </TableCell>
                        <TableCell>
                          <StatusBadge status={c.status} colorMap={containerStatusColor} />
                        </TableCell>
                        <TableCell className="w-36">
                          {c.status === 'at_site' ? (
                            <FillBar level={c.fill_level} threshold={c.pickup_threshold} />
                          ) : (
                            <span className="text-gray-400 text-xs">—</span>
                          )}
                        </TableCell>
                        <TableCell className="text-gray-700 text-sm capitalize">
                          {c.target_material_type?.replace(/_/g, ' ') ?? '—'}
                        </TableCell>
                        <TableCell className="text-gray-500 text-xs max-w-[180px] truncate">
                          {c.current_site_address ?? '—'}
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
