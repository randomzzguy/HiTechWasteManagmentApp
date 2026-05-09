"use client"

import { useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import {
  Shield, Plus, Search, RefreshCw, AlertCircle, AlertTriangle,
  Clock, CheckCircle2, ChevronRight, FileText, Download,
} from "lucide-react"
import { toast } from "sonner"
import { complianceApi } from "@/lib/api"
import { formatDate, cn } from "@/lib/utils"
import DownloadPdfButton from "@/components/shared/DownloadPdfButton"
import ConsignmentNoteForm from "@/components/compliance/ConsignmentNoteForm"
import SwBatchForm from "@/components/compliance/SwBatchForm"

const STATUS_STYLES: Record<string, string> = {
  in_storage:  "bg-brand-50 text-brand-600 border-brand-200",
  dispatched:  "bg-amber-50 text-amber-600 border-amber-200",
  processed:   "bg-green-50 text-green-600 border-green-200",
}

function urgencyStyle(days?: number): string {
  if (days === undefined || days === null) return "text-gray-500"
  if (days < 0) return "text-red-400 font-bold"
  if (days <= 2) return "text-red-400 font-semibold"
  if (days <= 10) return "text-amber-400 font-semibold"
  return "text-gray-500"
}

export default function ScheduledWastePage() {
  const [statusFilter, setStatusFilter] = useState("")
  const [swCodeFilter, setSwCodeFilter] = useState("")
  const [expiringSoon, setExpiringSoon] = useState(false)
  const [page, setPage] = useState(0)
  const PAGE_SIZE = 50

  const [cnFormOpen, setCnFormOpen] = useState(false)
  const [selectedBatchId, setSelectedBatchId] = useState<string>('')
  const [selectedSwCode, setSelectedSwCode] = useState<string>('')
  const [swBatchFormOpen, setSwBatchFormOpen] = useState(false)
  const queryClient = useQueryClient()

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["sw-batches", { statusFilter, swCodeFilter, expiringSoon, page }],
    queryFn: () => complianceApi.listBatches({
      status: statusFilter || undefined,
      sw_code: swCodeFilter || undefined,
      is_overdue: expiringSoon || undefined,
      skip: page * PAGE_SIZE, limit: PAGE_SIZE,
    } as Parameters<typeof complianceApi.listBatches>[0]),
    staleTime: 30_000,
  })

  const { data: swCodes } = useQuery({
    queryKey: ["sw-codes"],
    queryFn: () => complianceApi.listSWCodes({ limit: 100 } as Parameters<typeof complianceApi.listSWCodes>[0]),
    staleTime: Infinity,
  })

  const { data: cnData } = useQuery({
    queryKey: ["consignment-notes"],
    queryFn: () => complianceApi.listConsignmentNotes({ limit: 20 } as Parameters<typeof complianceApi.listConsignmentNotes>[0]),
    staleTime: 60_000,
  })

  const batches = (data as { items?: Record<string, unknown>[] } | null)?.items ?? []
  const total = (data as { total?: number } | null)?.total ?? 0
  const totalPages = Math.ceil(total / PAGE_SIZE)
  const codes = (swCodes as { items?: Record<string, unknown>[] } | null)?.items ?? []
  const notes = (cnData as { items?: Record<string, unknown>[] } | null)?.items ?? []

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Scheduled Waste Manager</h1>
          <p className="text-sm text-gray-500 mt-0.5">SW code library, batch tracking, 90-day rule enforcement</p>
        </div>
        <button
          onClick={() => setSwBatchFormOpen(true)}
          className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-500 text-white text-sm font-semibold rounded-lg transition-colors">
          <Plus className="w-4 h-4" /> New SW Batch
        </button>
      </div>

      {/* SW Code quick reference */}
      {codes.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <Shield className="w-4 h-4 text-amber-400" /> SW Code Library (First Schedule, EQA Act 127)
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 max-h-48 overflow-y-auto">
            {codes.map((code, i) => (
              <div key={i} className="flex items-start gap-2 p-2 bg-gray-100 rounded-lg">
                <span className="font-mono text-xs font-bold text-amber-400 flex-shrink-0 mt-0.5">{code.sw_code as string}</span>
                <span className="text-xs text-gray-700 leading-tight">{code.description as string}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-col sm:flex-row flex-wrap gap-3">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input type="text" placeholder="Filter by SW code…" value={swCodeFilter}
            onChange={e => { setSwCodeFilter(e.target.value); setPage(0) }}
            className="w-full pl-9 pr-3 py-2 bg-white border border-gray-300 rounded-lg text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500/20" />
        </div>
        <div className="flex items-center gap-1 bg-gray-100 border border-gray-200 rounded-lg p-1">
          {[{ label: "All", value: "" }, { label: "In Storage", value: "in_storage" }, { label: "Dispatched", value: "dispatched" }, { label: "Processed", value: "processed" }].map(f => (
            <button key={f.value} onClick={() => { setStatusFilter(f.value); setPage(0) }}
              className={cn("px-3 py-1.5 rounded-md text-xs font-semibold transition-colors",
                statusFilter === f.value ? "bg-brand-600 text-white" : "text-gray-500 hover:text-gray-900 hover:bg-white")}>
              {f.label}
            </button>
          ))}
        </div>
        <button onClick={() => { setExpiringSoon(v => !v); setPage(0) }}
          className={cn("flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-lg border transition-colors",
            expiringSoon ? "bg-amber-900/30 border-amber-700 text-amber-300" : "bg-white border-gray-300 text-gray-500 hover:text-gray-900 hover:bg-gray-50")}>
          <AlertTriangle className="w-3.5 h-3.5" /> Expiring Soon
        </button>
        <button onClick={() => refetch()} className="flex items-center gap-1.5 px-3 py-2 text-xs text-gray-500 hover:text-gray-900 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      {/* Batches table */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        {isError && <div className="flex items-center gap-2 p-4 text-red-500 text-sm"><AlertCircle className="w-4 h-4" /> Failed to load batches.</div>}
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                {[
                  { label: "SW Code", cls: "" },
                  { label: "Description", cls: "" },
                  { label: "Qty (kg)", cls: "hidden sm:table-cell" },
                  { label: "State", cls: "hidden sm:table-cell" },
                  { label: "Storage Start", cls: "hidden md:table-cell" },
                  { label: "Deadline", cls: "hidden sm:table-cell" },
                  { label: "Days Left", cls: "" },
                  { label: "Status", cls: "" },
                  { label: "CN", cls: "" },
                  { label: "", cls: "hidden sm:table-cell" },
                ].map(h => (
                  <th key={h.label} className={cn("px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap", h.cls)}>{h.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading ? Array.from({ length: 6 }).map((_, i) => (
                <tr key={i} className="border-b border-gray-100">
                  {Array.from({ length: 10 }).map((_, j) => (
                    <td key={j} className="px-4 py-3"><div className="h-4 rounded bg-gray-200 animate-pulse" style={{ width: `${50 + Math.random() * 50}%` }} /></td>
                  ))}
                </tr>
              )) : batches.length === 0 ? (
                <tr><td colSpan={10} className="px-4 py-12 text-center text-gray-400 text-sm">
                  <Shield className="w-8 h-8 mx-auto mb-2 opacity-30" />No scheduled waste batches found
                </td></tr>
              ) : batches.map((b, i) => {
                const days = b.days_remaining as number | undefined
                return (
                  <tr key={i} className="border-b border-gray-100 hover:bg-gray-50 transition-colors group">
                    <td className="px-4 py-3"><span className="font-mono text-xs font-bold text-amber-400">{b.sw_code as string}</span></td>
                    <td className="px-4 py-3 max-w-[180px]"><span className="text-xs text-gray-700 truncate block">{b.waste_description as string}</span></td>
                    <td className="px-4 py-3 hidden sm:table-cell"><span className="text-xs text-gray-700">{Number(b.quantity_kg).toLocaleString()}</span></td>
                    <td className="px-4 py-3 hidden sm:table-cell"><span className="text-xs text-gray-500 capitalize">{b.physical_state as string}</span></td>
                    <td className="px-4 py-3 hidden md:table-cell"><span className="text-xs text-gray-500">{formatDate(b.storage_start_date as string)}</span></td>
                    <td className="px-4 py-3 hidden sm:table-cell"><span className={cn("text-xs", days !== undefined && days < 0 ? "text-red-400" : "text-gray-500")}>{b.storage_deadline ? formatDate(b.storage_deadline as string) : "—"}</span></td>
                    <td className="px-4 py-3">
                      <span className={cn("flex items-center gap-1 text-xs", urgencyStyle(days))}>
                        {days !== undefined && days <= 10 && <AlertTriangle className="w-3 h-3" />}
                        {days !== undefined ? (days < 0 ? `${Math.abs(days)}d overdue` : `${days}d`) : "—"}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={cn("inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold border", STATUS_STYLES[b.status as string] ?? "bg-gray-100 text-gray-600 border-gray-300")}>
                        {(b.status as string).replace("_", " ")}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {b.consignment_note_id ? <CheckCircle2 className="w-4 h-4 text-green-400" /> : (
                        <button
                          onClick={() => {
                            setSelectedBatchId(b.id as string)
                            setSelectedSwCode(b.sw_code as string)
                            setCnFormOpen(true)
                          }}
                          className="text-xs text-brand-500 hover:underline flex items-center gap-1"
                        >
                          <FileText className="w-3 h-3" /> Create CN
                        </button>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right hidden sm:table-cell">
                      <button className="opacity-0 group-hover:opacity-100 transition-opacity inline-flex items-center gap-1 text-xs text-gray-500 hover:text-gray-900 px-2 py-1 rounded hover:bg-gray-100">
                        View <ChevronRight className="w-3 h-3" />
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        {total > PAGE_SIZE && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200 text-xs text-gray-500">
            <span>{total} total batches</span>
            <div className="flex items-center gap-2">
              <button disabled={page === 0} onClick={() => setPage(p => p - 1)} className="px-3 py-1.5 rounded bg-gray-100 hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors text-gray-700">Previous</button>
              <span className="hidden sm:inline">Page {page + 1} of {totalPages}</span>
              <button disabled={page >= totalPages - 1} onClick={() => setPage(p => p + 1)} className="px-3 py-1.5 rounded bg-gray-100 hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors text-gray-700">Next</button>
            </div>
          </div>
        )}
      </div>

      {/* Consignment notes */}
      {notes.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2 mb-3"><FileText className="w-4 h-4 text-brand-400" /> Recent Consignment Notes</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-gray-200">
                  {[
                    { label: "CN Number", cls: "" },
                    { label: "Transport Date", cls: "hidden sm:table-cell" },
                    { label: "Transporter", cls: "hidden sm:table-cell" },
                    { label: "Facility", cls: "hidden md:table-cell" },
                    { label: "Status", cls: "" },
                    { label: "PDF", cls: "" },
                  ].map(h => (
                    <th key={h.label} className={cn("pb-2 text-[11px] font-semibold text-gray-500 uppercase tracking-wider pr-4", h.cls)}>{h.label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {notes.map((note, i) => (
                  <tr key={i} className="border-b border-gray-100">
                    <td className="py-2 pr-4 font-mono text-xs font-semibold text-gray-900">{note.note_number as string}</td>
                    <td className="py-2 pr-4 text-xs text-gray-500 hidden sm:table-cell">{note.transport_date ? formatDate(note.transport_date as string) : "—"}</td>
                    <td className="py-2 pr-4 text-xs text-gray-500 hidden sm:table-cell">{(note.transporter_name as string) || "—"}</td>
                    <td className="py-2 pr-4 text-xs text-gray-500 truncate max-w-[150px] hidden md:table-cell">{(note.processing_facility as string) || "—"}</td>
                    <td className="py-2 pr-4">
                      <span className={cn("text-xs px-2 py-0.5 rounded-full",
                        note.status === "processed" ? "bg-green-50 text-green-600" :
                        note.status === "submitted" ? "bg-brand-50 text-brand-600" : "bg-gray-100 text-gray-500")}>
                        {note.status as string}
                      </span>
                    </td>
                    <td className="py-2">
                      <DownloadPdfButton
                        label="Download PDF"
                        onDownload={() => complianceApi.generateConsignmentNotePDF(note.id as string)}
                        filename={`consignment-note-${note.id as string}.pdf`}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <ConsignmentNoteForm
        open={cnFormOpen}
        onOpenChange={setCnFormOpen}
        batchId={selectedBatchId}
        swCode={selectedSwCode}
        onSuccess={() => {
          queryClient.invalidateQueries({ queryKey: ['consignment-notes'] })
          queryClient.invalidateQueries({ queryKey: ['sw-batches'] })
          toast.success('Consignment note created')
        }}
      />

      <SwBatchForm
        open={swBatchFormOpen}
        onOpenChange={setSwBatchFormOpen}
        onSuccess={() => {
          queryClient.invalidateQueries({ queryKey: ['sw-batches'] })
        }}
      />
    </div>
  )
}
