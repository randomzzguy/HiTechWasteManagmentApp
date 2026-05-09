'use client'

import { CheckCircle2, Clock, Database, FileText } from 'lucide-react'

interface KbStatsBarProps {
  total: number
  ingested: number
  pending: number
  milvusChunks: number
}

interface StatCardProps {
  icon: React.ReactNode
  label: string
  value: number
}

function StatCard({ icon, label, value }: StatCardProps) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 flex items-center gap-3">
      <div className="text-brand-600 flex-shrink-0">{icon}</div>
      <div>
        <p className="text-2xl font-bold text-gray-900">{value.toLocaleString()}</p>
        <p className="text-xs text-gray-500 mt-0.5">{label}</p>
      </div>
    </div>
  )
}

export default function KbStatsBar({ total, ingested, pending, milvusChunks }: KbStatsBarProps) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      <StatCard
        icon={<FileText className="w-5 h-5" />}
        label="Total Documents"
        value={total}
      />
      <StatCard
        icon={<CheckCircle2 className="w-5 h-5" />}
        label="Ingested"
        value={ingested}
      />
      <StatCard
        icon={<Clock className="w-5 h-5" />}
        label="Pending"
        value={pending}
      />
      <StatCard
        icon={<Database className="w-5 h-5" />}
        label="Milvus Chunks"
        value={milvusChunks}
      />
    </div>
  )
}
