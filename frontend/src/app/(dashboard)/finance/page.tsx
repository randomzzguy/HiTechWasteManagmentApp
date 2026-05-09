'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  DollarSign, Plus, RefreshCw, AlertCircle, Clock,
  CheckCircle2, AlertTriangle, ChevronRight,
} from 'lucide-react'
import { financeApi } from '@/lib/api'
import { formatDate, formatCurrency, cn } from '@/lib/utils'
import InvoiceForm from '@/components/finance/InvoiceForm'
import DownloadPdfButton from '@/components/shared/DownloadPdfButton'

interface Invoice {
  id: string
  invoice_number: string
  client_id: string
  issue_date?: string
  due_date?: string
  total_myr?: number
  paid_amount_myr?: number
  status: string
  notes?: string
}

const STATUS_STYLES: Record<string, string> = {
  unpaid:   'bg-amber-50 text-amber-600 border-amber-200',
  partial:  'bg-brand-50 text-brand-600 border-brand-200',
  paid:     'bg-green-50 text-green-600 border-green-200',
  overdue:  'bg-red-50 text-red-600 border-red-200',
}

const STATUS_ICONS: Record<string, React.ElementType> = {
  unpaid:  Clock,
  partial: Clock,
  paid:    CheckCircle2,
  overdue: AlertTriangle,
}

export default function FinancePage() {
  const [statusFilter, setStatusFilter] = useState('')
  const [page, setPage] = useState(0)
  const [formOpen, setFormOpen] = useState(false)
  const PAGE_SIZE = 50

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['finance', 'invoices', { statusFilter, page }],
    queryFn: () =>
      financeApi.listInvoices({
        status: statusFilter || undefined,
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      } as Parameters<typeof financeApi.listInvoices>[0]),
    staleTime: 60_000,
  })

  const { data: revenueData } = useQuery({
    queryKey: ['finance', 'revenue'],
    queryFn: () => financeApi.getRevenueStats(),
    staleTime: 10 * 60_000,
  })

  const { data: ageingData } = useQuery({
    queryKey: ['finance', 'ageing'],
    queryFn: () => financeApi.getReceivablesAgeing(),
    staleTime: 10 * 60_000,
  })

  const invoices = (data as { items?: Invoice[] } | null)?.items ?? []
  const total = (data as { total?: number } | null)?.total ?? 0
  const totalPages = Math.ceil(total / PAGE_SIZE)

  const revenue = revenueData as Record<string, unknown> | null
  const ageing = ageingData as Record<string, unknown> | null

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Finance</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Invoices, revenue, and receivables
          </p>
        </div>
        <button
          className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-500 text-white text-sm font-semibold rounded-lg transition-colors"
          onClick={() => setFormOpen(true)}
        >
          <Plus className="w-4 h-4" />
          New Invoice
        </button>
      </div>

      <InvoiceForm open={formOpen} onClose={() => setFormOpen(false)} />

      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[
          {
            label: 'Total Revenue (YTD)',
            value: formatCurrency(revenue?.total_revenue_myr as number),
            icon: DollarSign,
            color: 'text-green-400',
            bg: 'bg-green-50 border-green-200',
          },
          {
            label: 'Outstanding Receivables',
            value: formatCurrency(ageing?.total_outstanding_myr as number),
            icon: Clock,
            color: 'text-amber-400',
            bg: 'bg-amber-50 border-amber-200',
          },
          {
            label: 'Overdue Amount',
            value: formatCurrency(ageing?.overdue_myr as number),
            icon: AlertTriangle,
            color: 'text-red-400',
            bg: 'bg-red-50 border-red-200',
          },
        ].map((card) => (
          <div key={card.label} className={cn('flex items-center gap-4 p-4 rounded-xl border bg-white', card.bg)}>
            <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center border flex-shrink-0', card.bg)}>
              <card.icon className={cn('w-5 h-5', card.color)} />
            </div>
            <div>
              <p className="text-xs text-gray-400 font-semibold uppercase tracking-wider">{card.label}</p>
              <p className={cn('text-xl font-bold mt-0.5', card.color)}>{card.value}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <div className="flex items-center gap-1 bg-gray-100 border border-gray-200 rounded-lg p-1">
          {[
            { label: 'All', value: '' },
            { label: 'Unpaid', value: 'unpaid' },
            { label: 'Partial', value: 'partial' },
            { label: 'Paid', value: 'paid' },
            { label: 'Overdue', value: 'overdue' },
          ].map((f) => (
            <button
              key={f.value}
              onClick={() => { setStatusFilter(f.value); setPage(0) }}
              className={cn(
                'px-3 py-1.5 rounded-md text-xs font-semibold transition-colors',
                statusFilter === f.value
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
            Failed to load invoices.
          </div>
        )}

        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">Invoice #</th>
                <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap hidden sm:table-cell">Issue Date</th>
                <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap hidden sm:table-cell">Due Date</th>
                <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">Total</th>
                <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap hidden md:table-cell">Paid</th>
                <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap hidden md:table-cell">Balance</th>
                <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">Status</th>
                <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap hidden sm:table-cell">PDF</th>
                <th className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap hidden sm:table-cell"></th>
              </tr>
            </thead>
            <tbody>
              {isLoading
                ? Array.from({ length: 8 }).map((_, i) => (
                    <tr key={i} className="border-b border-gray-100">
                      {Array.from({ length: 9 }).map((_, j) => (
                        <td key={j} className="px-4 py-3">
                          <div className="h-4 rounded bg-gray-200 animate-pulse" style={{ width: `${50 + Math.random() * 50}%` }} />
                        </td>
                      ))}
                    </tr>
                  ))
                : invoices.length === 0
                ? (
                    <tr>
                      <td colSpan={9} className="px-4 py-12 text-center text-gray-400 text-sm">
                        <DollarSign className="w-8 h-8 mx-auto mb-2 opacity-30" />
                        No invoices found
                      </td>
                    </tr>
                  )
                : invoices.map((inv) => {
                    const balance = (inv.total_myr ?? 0) - (inv.paid_amount_myr ?? 0)
                    const StatusIcon = STATUS_ICONS[inv.status] ?? Clock
                    return (
                      <tr key={inv.id} className="border-b border-gray-100 hover:bg-gray-50 transition-colors group">
                        <td className="px-4 py-3">
                          <span className="font-mono text-xs font-semibold text-gray-900">{inv.invoice_number}</span>
                        </td>
                        <td className="px-4 py-3 hidden sm:table-cell">
                          <span className="text-xs text-gray-500">{inv.issue_date ? formatDate(inv.issue_date) : '—'}</span>
                        </td>
                        <td className="px-4 py-3 hidden sm:table-cell">
                          <span className={cn('text-xs', inv.status === 'overdue' ? 'text-red-400 font-semibold' : 'text-gray-500')}>
                            {inv.due_date ? formatDate(inv.due_date) : '—'}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <span className="text-sm font-semibold text-gray-900">{formatCurrency(inv.total_myr)}</span>
                        </td>
                        <td className="px-4 py-3 hidden md:table-cell">
                          <span className="text-xs text-green-400">{formatCurrency(inv.paid_amount_myr)}</span>
                        </td>
                        <td className="px-4 py-3 hidden md:table-cell">
                          <span className={cn('text-xs font-semibold', balance > 0 ? 'text-amber-400' : 'text-gray-400')}>
                            {formatCurrency(balance)}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <span className={cn(
                            'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold border',
                            STATUS_STYLES[inv.status] ?? 'bg-gray-100 text-gray-600 border-gray-300'
                          )}>
                            <StatusIcon className="w-3 h-3" />
                            {inv.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 hidden sm:table-cell">
                          <DownloadPdfButton
                            label="Download"
                            onDownload={() => financeApi.generateInvoicePDF(inv.id)}
                            filename={`invoice-${inv.id}.pdf`}
                          />
                        </td>
                        <td className="px-4 py-3 text-right hidden sm:table-cell">
                          <button className="opacity-0 group-hover:opacity-100 transition-opacity inline-flex items-center gap-1 text-xs text-gray-500 hover:text-gray-900 px-2 py-1 rounded hover:bg-gray-100">
                            View <ChevronRight className="w-3 h-3" />
                          </button>
                        </td>
                      </tr>
                    )
                  })
              }
            </tbody>
          </table>
        </div>

        {total > PAGE_SIZE && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200 text-xs text-gray-500">
            <span>{total} total invoices</span>
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
