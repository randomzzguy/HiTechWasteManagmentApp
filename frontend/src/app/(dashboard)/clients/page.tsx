'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import {
  Plus, Search, Users, Building2, ChevronRight,
  RefreshCw, AlertCircle, CheckCircle2, XCircle,
} from 'lucide-react'
import { clientsApi } from '@/lib/api'
import { formatDate, cn } from '@/lib/utils'
import ClientForm from '@/components/clients/ClientForm'

interface Client {
  id: string
  company_name: string
  industry_vertical?: string
  city?: string
  state?: string
  pic_name?: string
  pic_email?: string
  is_active: boolean
  contract_end?: string
  sla_diversion_target?: number
}

export default function ClientsPage() {
  const router = useRouter()
  const [search, setSearch] = useState('')
  const [activeFilter, setActiveFilter] = useState<boolean | undefined>(undefined)
  const [page, setPage] = useState(0)
  const [formOpen, setFormOpen] = useState(false)
  const PAGE_SIZE = 50

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['clients', { search, activeFilter, page }],
    queryFn: () =>
      clientsApi.list({
        search: search || undefined,
        is_active: activeFilter,
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      } as Parameters<typeof clientsApi.list>[0]),
    staleTime: 60_000,
  })

  const clients = (data as { items?: Client[] } | null)?.items ?? []
  const total = (data as { total?: number } | null)?.total ?? 0
  const totalPages = Math.ceil(total / PAGE_SIZE)

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Clients</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Client accounts and waste stream profiles
          </p>
        </div>
        <button
          className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-500 text-white text-sm font-semibold rounded-lg transition-colors"
          onClick={() => setFormOpen(true)}
        >
          <Plus className="w-4 h-4" />
          New Client
        </button>
      </div>

      <ClientForm open={formOpen} onClose={() => setFormOpen(false)} />

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search company name…"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(0) }}
            className="w-full pl-9 pr-3 py-2 bg-white border border-gray-300 rounded-lg text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500/20"
          />
        </div>

        <div className="flex items-center gap-1 bg-gray-100 border border-gray-200 rounded-lg p-1">
          {[
            { label: 'All', value: undefined },
            { label: 'Active', value: true },
            { label: 'Inactive', value: false },
          ].map((f) => (
            <button
              key={String(f.value)}
              onClick={() => { setActiveFilter(f.value); setPage(0) }}
              className={cn(
                'px-3 py-1.5 rounded-md text-xs font-semibold transition-colors',
                activeFilter === f.value
                  ? 'bg-brand-600 text-white'
                  : 'text-gray-500 hover:text-gray-900 hover:bg-white'
              )}
            >
              {f.label}
            </button>
          ))}
        </div>

        <button
          onClick={() => refetch()}
          className="flex items-center gap-1.5 px-3 py-2 text-xs text-gray-500 hover:text-gray-900 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh
        </button>
      </div>

      {/* Table */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        {isError && (
          <div className="flex items-center gap-2 p-4 text-red-500 text-sm">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            Failed to load clients.
          </div>
        )}

        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">Company</th>
                <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap hidden sm:table-cell">Industry</th>
                <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap hidden sm:table-cell">Location</th>
                <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap hidden md:table-cell">PIC</th>
                <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap hidden md:table-cell">Contract End</th>
                <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap hidden lg:table-cell">Diversion Target</th>
                <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">Status</th>
                <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap hidden sm:table-cell"></th>
              </tr>
            </thead>
            <tbody>
              {isLoading
                ? Array.from({ length: 8 }).map((_, i) => (
                    <tr key={i} className="border-b border-gray-100">
                      {Array.from({ length: 8 }).map((_, j) => (
                        <td key={j} className="px-4 py-3">
                          <div className="h-4 rounded bg-gray-200 animate-pulse" style={{ width: `${50 + Math.random() * 50}%` }} />
                        </td>
                      ))}
                    </tr>
                  ))
                : clients.length === 0
                ? (
                    <tr>
                      <td colSpan={8} className="px-4 py-12 text-center text-gray-400 text-sm">
                        <Users className="w-8 h-8 mx-auto mb-2 opacity-30" />
                        No clients found
                      </td>
                    </tr>
                  )
                : clients.map((client) => (
                    <tr
                      key={client.id}
                      className="border-b border-gray-100 hover:bg-gray-50 transition-colors group cursor-pointer"
                      onClick={() => router.push(`/clients/${client.id}`)}
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div className="w-7 h-7 rounded-lg bg-gray-100 flex items-center justify-center flex-shrink-0">
                            <Building2 className="w-3.5 h-3.5 text-gray-500" />
                          </div>
                          <span className="text-sm font-medium text-gray-900">{client.company_name}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 hidden sm:table-cell">
                        <span className="text-xs text-gray-500">{client.industry_vertical ?? '—'}</span>
                      </td>
                      <td className="px-4 py-3 hidden sm:table-cell">
                        <span className="text-xs text-gray-500">
                          {[client.city, client.state].filter(Boolean).join(', ') || '—'}
                        </span>
                      </td>
                      <td className="px-4 py-3 hidden md:table-cell">
                        <div className="flex flex-col">
                          <span className="text-xs text-gray-900">{client.pic_name ?? '—'}</span>
                          {client.pic_email && (
                            <span className="text-[11px] text-gray-400">{client.pic_email}</span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 hidden md:table-cell">
                        <span className={cn(
                          'text-xs',
                          client.contract_end && new Date(client.contract_end) < new Date()
                            ? 'text-red-400'
                            : 'text-gray-500'
                        )}>
                          {client.contract_end ? formatDate(client.contract_end) : '—'}
                        </span>
                      </td>
                      <td className="px-4 py-3 hidden lg:table-cell">
                        <span className="text-xs text-gray-500">
                          {client.sla_diversion_target != null ? `${client.sla_diversion_target}%` : '—'}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {client.is_active ? (
                          <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-green-400">
                            <CheckCircle2 className="w-3 h-3" /> Active
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-gray-400">
                            <XCircle className="w-3 h-3" /> Inactive
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right hidden sm:table-cell">
                        <button className="opacity-0 group-hover:opacity-100 transition-opacity inline-flex items-center gap-1 text-xs text-gray-500 hover:text-gray-900 px-2 py-1 rounded hover:bg-gray-100">
                          View <ChevronRight className="w-3 h-3" />
                        </button>
                      </td>
                    </tr>
                  ))
              }
            </tbody>
          </table>
        </div>

        {total > PAGE_SIZE && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200 text-xs text-gray-500">
            <span>{total} total clients</span>
            <div className="flex items-center gap-2">
              <button disabled={page === 0} onClick={() => setPage((p) => p - 1)}
                className="px-3 py-1.5 rounded bg-gray-100 hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors text-gray-700">
                Previous
              </button>
              <span className="hidden sm:inline">Page {page + 1} of {totalPages}</span>
              <button disabled={page >= totalPages - 1} onClick={() => setPage((p) => p + 1)}
                className="px-3 py-1.5 rounded bg-gray-100 hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors text-gray-700">
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
