'use client'

import { useSession } from 'next-auth/react'
import KpiCards from '@/components/dashboard/KpiCards'
import ManagementKpiCards from '@/components/dashboard/ManagementKpiCards'
import TonnageChart from '@/components/dashboard/TonnageChart'
import JobStatusSummary from '@/components/dashboard/JobStatusSummary'
import FleetStatusWidget from '@/components/dashboard/FleetStatusWidget'
import ComplianceAlerts from '@/components/dashboard/ComplianceAlerts'
import OperationalFieldWidget from '@/components/dashboard/OperationalFieldWidget'
import ClientPortalDashboard from '@/components/client-portal/ClientPortalDashboard'

const MGMT_ROLES = ['superadmin', 'management']

export default function DashboardPage() {
  const { data: session } = useSession()
  const role = session?.user?.role

  if (role === 'client') {
    return <ClientPortalDashboard />
  }

  const isMgmt = MGMT_ROLES.includes(role ?? '')

  return (
    <div className="flex flex-col gap-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Operations Dashboard</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Real-time overview of waste management operations
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1.5 text-xs text-brand-600 bg-brand-50 border border-brand-200 px-2.5 py-1.5 rounded-lg">
            <span className="w-1.5 h-1.5 rounded-full bg-brand-600 animate-pulse" />
            Live Data
          </span>
        </div>
      </div>

      {/* Management KPIs — revenue, overdue invoices, maintenance, clients */}
      {isMgmt && <ManagementKpiCards />}

      {/* Operational KPI Cards Row */}
      <KpiCards />

      {/* Main content grid */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2">
          <TonnageChart />
        </div>
        <div className="xl:col-span-1">
          <JobStatusSummary />
        </div>
      </div>

      {/* Secondary grid */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <FleetStatusWidget />
        <ComplianceAlerts />
        <OperationalFieldWidget />
      </div>
    </div>
  )
}
