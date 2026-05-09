'use client'

import { useSession } from 'next-auth/react'
import { useQuery } from '@tanstack/react-query'
import { Briefcase, Leaf, TrendingUp, Calendar, Hash } from 'lucide-react'
import { jobsApi, weighbridgeApi, esgApi } from '@/lib/api'
import DownloadPdfButton from '@/components/shared/DownloadPdfButton'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function KpiCard({
  label,
  value,
  sub,
  icon: Icon,
  accent,
}: {
  label: string
  value: string | number
  sub?: string
  icon: React.ElementType
  accent?: string
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 flex items-start gap-4 shadow-sm">
      <div className={`flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center ${accent ?? 'bg-brand-50'}`}>
        <Icon className="w-5 h-5 text-brand-600" />
      </div>
      <div className="min-w-0">
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</p>
        <p className="text-2xl font-bold text-gray-900 mt-0.5">{value}</p>
        {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
      </div>
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    completed: 'bg-green-100 text-green-700',
    in_progress: 'bg-brand-100 text-brand-700',
    dispatched: 'bg-yellow-100 text-yellow-700',
    confirmed: 'bg-brand-100 text-brand-700',
    draft: 'bg-gray-100 text-gray-600',
    invoiced: 'bg-purple-100 text-purple-700',
    cancelled: 'bg-red-100 text-red-600',
  }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium capitalize ${map[status] ?? 'bg-gray-100 text-gray-600'}`}>
      {status.replace(/_/g, ' ')}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function ClientPortalDashboard() {
  const { data: session } = useSession()
  const userName = session?.user?.name ?? 'Client'

  const { data: jobsData } = useQuery({
    queryKey: ['client-portal-jobs'],
    queryFn: () => jobsApi.list({ limit: 10 }),
  })

  const { data: tonnageStats } = useQuery({
    queryKey: ['client-portal-tonnage'],
    queryFn: () => weighbridgeApi.getTonnageStats({ period: 'monthly' }),
  })

  const { data: esgData } = useQuery({
    queryKey: ['client-portal-esg'],
    queryFn: () => esgApi.getCompanyDashboard(),
  })

  const jobs = (jobsData?.results ?? []) as Record<string, unknown>[]
  const activeJobs = jobs.filter((j) => !['completed', 'invoiced', 'cancelled'].includes(j.status as string)).length
  const totalTonnage = (tonnageStats?.total_tonnes as number | undefined) ?? 0
  const diversionRate = (esgData?.diversion_rate as number | undefined) ?? 0
  const co2Saved = (esgData?.co2_saved_tonnes as number | undefined) ?? 0
  const sdgTags = (esgData?.sdg_tags as string[] | undefined) ?? []

  async function handleDownloadEsg(): Promise<Blob> {
    const job = await esgApi.generateReport({
      report_type: 'esg_summary',
      period: 'monthly',
    })
    const jobId = job.job_id as string
    // Poll until ready (max 30s)
    for (let i = 0; i < 30; i++) {
      await new Promise((r) => setTimeout(r, 1000))
      const status = await esgApi.getReportJob(jobId)
      if (status.status === 'completed') break
    }
    return esgApi.downloadReport(jobId)
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Welcome, {userName}</h1>
          <p className="text-sm text-gray-500 mt-0.5">Your sustainability &amp; waste management overview</p>
        </div>
        <DownloadPdfButton
          label="Download ESG Report"
          onDownload={handleDownloadEsg}
          filename="esg-report.pdf"
        />
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <KpiCard
          label="Active Jobs"
          value={activeJobs}
          sub="Currently in progress"
          icon={Briefcase}
          accent="bg-brand-50"
        />
        <KpiCard
          label="Waste Processed"
          value={`${totalTonnage.toFixed(1)} t`}
          sub="This month"
          icon={TrendingUp}
          accent="bg-brand-50"
        />
        <KpiCard
          label="Diversion Rate"
          value={`${diversionRate.toFixed(1)}%`}
          sub="Landfill diversion"
          icon={Leaf}
          accent="bg-green-50"
        />
      </div>

      {/* Recent Jobs */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100">
          <h2 className="text-sm font-semibold text-gray-800">Recent Jobs</h2>
          <p className="text-xs text-gray-400 mt-0.5">Last 10 collection orders</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-left">
                <th className="px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  <span className="flex items-center gap-1.5"><Hash className="w-3 h-3" />Job #</span>
                </th>
                <th className="px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Type</th>
                <th className="px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Status</th>
                <th className="px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  <span className="flex items-center gap-1.5"><Calendar className="w-3 h-3" />Scheduled</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {jobs.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-5 py-8 text-center text-sm text-gray-400">
                    No jobs found
                  </td>
                </tr>
              ) : (
                jobs.map((job) => (
                  <tr key={job.id as string} className="hover:bg-gray-50 transition-colors">
                    <td className="px-5 py-3 font-mono text-xs text-gray-700">
                      {(job.job_number as string) ?? (job.id as string)?.slice(0, 8)}
                    </td>
                    <td className="px-5 py-3 text-gray-700 capitalize">
                      {((job.job_type as string) ?? '—').replace(/_/g, ' ')}
                    </td>
                    <td className="px-5 py-3">
                      <StatusBadge status={(job.status as string) ?? 'draft'} />
                    </td>
                    <td className="px-5 py-3 text-gray-500 text-xs">
                      {job.scheduled_date
                        ? new Date(job.scheduled_date as string).toLocaleDateString('en-MY', {
                            day: '2-digit',
                            month: 'short',
                            year: 'numeric',
                          })
                        : '—'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ESG Summary */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
        <h2 className="text-sm font-semibold text-gray-800 mb-4">ESG Summary</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="flex flex-col gap-1">
            <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">CO₂ Saved</p>
            <p className="text-xl font-bold text-gray-900">{co2Saved.toFixed(2)} t</p>
            <p className="text-xs text-gray-400">Scope 3 Category 5</p>
          </div>
          <div className="flex flex-col gap-1">
            <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">Diversion Rate</p>
            <p className="text-xl font-bold text-gray-900">{diversionRate.toFixed(1)}%</p>
            <p className="text-xs text-gray-400">Landfill avoidance</p>
          </div>
          <div className="flex flex-col gap-1">
            <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">SDG Alignment</p>
            {sdgTags.length > 0 ? (
              <div className="flex flex-wrap gap-1.5 mt-1">
                {sdgTags.map((tag) => (
                  <span
                    key={tag}
                    className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-brand-50 text-brand-700 border border-brand-200"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-400">—</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
