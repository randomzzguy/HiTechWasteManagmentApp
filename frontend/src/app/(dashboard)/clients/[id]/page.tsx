'use client'

import { useParams, useRouter } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Building2, Users, ClipboardList, Leaf, AlertCircle, Mail, Phone } from 'lucide-react'
import { clientsApi } from '@/lib/api'
import { formatDate, formatWeight, formatPercent, formatCarbon, cn } from '@/lib/utils'

export default function ClientDetailPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()

  const { data: client, isLoading, isError } = useQuery({
    queryKey: ['client', id],
    queryFn: () => clientsApi.get(id),
    staleTime: 60_000,
  })

  const { data: esgData } = useQuery({
    queryKey: ['client-esg', id],
    queryFn: () => clientsApi.getESGSummary(id),
    staleTime: 5 * 60_000,
  })

  const c = client as Record<string, unknown> | null
  const esg = esgData as Record<string, unknown> | null

  if (isLoading) return (
    <div className="flex items-center justify-center h-64">
      <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
    </div>
  )

  if (isError || !c) return (
    <div className="flex flex-col items-center justify-center h-64 gap-3 text-gray-400">
      <AlertCircle className="w-10 h-10" />
      <p>Client not found.</p>
      <button onClick={() => router.back()} className="text-brand-600 hover:underline text-sm">Go back</button>
    </div>
  )

  return (
    <div className="flex flex-col gap-6 max-w-5xl">
      {/* Header */}
      <div className="flex items-start gap-4 flex-wrap">
        <button
          onClick={() => router.back()}
          className="mt-1 p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-700 transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <div className="w-10 h-10 rounded-xl bg-brand-50 border border-brand-200 flex items-center justify-center flex-shrink-0">
              <Building2 className="w-5 h-5 text-brand-600" />
            </div>
            <div className="min-w-0">
              <h1 className="text-2xl font-bold text-gray-900">{c.company_name as string}</h1>
              <p className="text-sm text-gray-500">
                {c.industry_vertical as string}
                {[c.city, c.state].filter(Boolean).length > 0 && ` · ${[c.city, c.state].filter(Boolean).join(', ')}`}
              </p>
            </div>
          </div>
        </div>
        <span className={cn(
          'px-2.5 py-1 rounded-full text-xs font-semibold border flex-shrink-0',
          c.is_active
            ? 'bg-green-50 text-green-600 border-green-200'
            : 'bg-gray-100 text-gray-500 border-gray-300'
        )}>
          {c.is_active ? 'Active' : 'Inactive'}
        </span>
      </div>

      {/* ESG KPIs */}
      {esg && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: 'CO₂ Saved', value: formatCarbon(esg.total_co2_avoided_kgco2e as number), color: 'text-green-600', bg: 'bg-green-50 border-green-200' },
            { label: 'Diversion Rate', value: formatPercent(esg.diversion_rate_pct as number), color: 'text-emerald-600', bg: 'bg-emerald-50 border-emerald-200' },
            { label: 'Waste Processed', value: formatWeight(esg.total_waste_processed_kg as number), color: 'text-brand-600', bg: 'bg-brand-50 border-brand-200' },
            { label: 'Recyclables', value: formatWeight(esg.total_recyclable_kg as number), color: 'text-brand-600', bg: 'bg-brand-50 border-brand-200' },
          ].map(kpi => (
            <div key={kpi.label} className={cn('bg-white border rounded-xl p-4', kpi.bg)}>
              <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider">{kpi.label}</p>
              <p className={cn('text-xl font-bold mt-1', kpi.color)}>{kpi.value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Details grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Contact & Contract */}
        <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-3">
          <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
            <Users className="w-4 h-4 text-brand-500" /> Contact & Contract
          </h3>

          {/* PIC contact */}
          {!!c.pic_name && (
            <div className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
              <div className="w-8 h-8 rounded-full bg-brand-100 flex items-center justify-center flex-shrink-0">
                <span className="text-xs font-bold text-brand-700">
                  {(c.pic_name as string).split(' ').map((n: string) => n[0]).join('').slice(0, 2).toUpperCase()}
                </span>
              </div>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-gray-900">{c.pic_name as string}</p>
                {!!c.pic_email && (
                  <a href={`mailto:${c.pic_email as string}`} className="flex items-center gap-1 text-xs text-brand-600 hover:underline mt-0.5">
                    <Mail className="w-3 h-3" />{c.pic_email as string}
                  </a>
                )}
                {!!c.pic_phone && (
                  <p className="flex items-center gap-1 text-xs text-gray-500 mt-0.5">
                    <Phone className="w-3 h-3" />{c.pic_phone as string}
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Contract details */}
          {[
            ['SSM Number', c.ssm_number],
            ['Contract Start', c.contract_start ? formatDate(c.contract_start as string) : null],
            ['Contract End', c.contract_end ? formatDate(c.contract_end as string) : null],
            ['Billing Model', c.billing_model ? (c.billing_model as string).replace('_', ' ') : null],
            ['Diversion Target', c.sla_diversion_target ? `${c.sla_diversion_target}%` : null],
          ].filter(([, v]) => v).map(([label, value]) => (
            <div key={label as string} className="flex justify-between gap-4">
              <span className="text-xs text-gray-500 flex-shrink-0">{label as string}</span>
              <span className="text-xs text-gray-800 text-right font-medium">{String(value ?? '')}</span>
            </div>
          ))}

          {!!c.notes && (
            <div className="pt-2 border-t border-gray-100">
              <p className="text-xs text-gray-500 mb-1">Notes</p>
              <p className="text-xs text-gray-700">{c.notes as string}</p>
            </div>
          )}
        </div>

        {/* Waste Streams */}
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2 mb-3">
            <Leaf className="w-4 h-4 text-green-500" /> Waste Streams
          </h3>
          {Array.isArray(c.waste_streams) && (c.waste_streams as unknown[]).length > 0 ? (
            <div className="space-y-2">
              {(c.waste_streams as Record<string, unknown>[]).map((ws, i) => (
                <div key={i} className="flex items-center justify-between p-2.5 bg-gray-50 border border-gray-200 rounded-lg">
                  <span className="text-xs font-semibold text-gray-800 capitalize">{ws.waste_type as string}</span>
                  <div className="flex items-center gap-3 text-right">
                    {!!ws.estimated_kg_per_month && (
                      <span className="text-xs text-gray-500">{formatWeight(ws.estimated_kg_per_month as number)}/mo</span>
                    )}
                    {!!ws.collection_frequency && (
                      <span className="text-[10px] bg-brand-50 text-brand-600 border border-brand-200 px-1.5 py-0.5 rounded-full capitalize">
                        {(ws.collection_frequency as string).replace('_', ' ')}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-400 text-center py-4">No waste streams configured</p>
          )}
        </div>
      </div>

      {/* Jobs link */}
      <div className="bg-white border border-gray-200 rounded-xl p-5">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
            <ClipboardList className="w-4 h-4 text-amber-500" /> Collection History
          </h3>
          <a
            href={`/jobs?client_id=${id}`}
            className="text-xs text-brand-600 hover:underline font-medium"
          >
            View all jobs →
          </a>
        </div>
        <p className="text-sm text-gray-400 text-center py-4">
          Use the Jobs page and filter by this client to see their full collection history.
        </p>
      </div>
    </div>
  )
}
