'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Users, Phone, Mail, Plus, AlertCircle, RefreshCw } from 'lucide-react'
import { cn } from '@/lib/utils'
import api from '@/lib/api'

interface StaffMember {
  id: string
  full_name: string
  role: string
  email: string
  phone?: string
  is_active: boolean
}

const ROLE_LABELS: Record<string, string> = {
  field_supervisor: 'Field Supervisor',
  driver: 'Driver',
  operations_manager: 'Operations Manager',
  compliance_officer: 'Compliance Officer',
  management: 'Management',
  superadmin: 'Super Admin',
  client: 'Client',
}

const ROLE_COLORS: Record<string, string> = {
  field_supervisor: 'bg-amber-50 text-amber-700 border-amber-200',
  driver: 'bg-brand-50 text-brand-700 border-brand-200',
  operations_manager: 'bg-purple-50 text-purple-700 border-purple-200',
  compliance_officer: 'bg-brand-50 text-brand-700 border-brand-200',
  management: 'bg-indigo-50 text-indigo-700 border-indigo-200',
  superadmin: 'bg-red-50 text-red-700 border-red-200',
}

export default function LabourPage() {
  const [roleFilter, setRoleFilter] = useState('all')

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['staff-directory', roleFilter],
    queryFn: () =>
      api
        .get('/api/v1/settings/users/', {
          params: {
            is_active: true,
            ...(roleFilter !== 'all' ? { role: roleFilter } : {}),
            limit: 200,
          },
        })
        .then((r) => r.data),
    staleTime: 60_000,
  })

  const staff: StaffMember[] = (data?.items ?? []).filter((u: StaffMember) =>
    ['field_supervisor', 'driver', 'operations_manager', 'compliance_officer'].includes(u.role)
  )

  const fieldRoles = ['all', 'field_supervisor', 'driver', 'operations_manager', 'compliance_officer']

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Staff Directory</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Field staff and operational team members
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="flex items-center gap-1.5 px-3 py-2 text-xs text-gray-500 hover:text-gray-900 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh
        </button>
      </div>

      {/* Role filter pills */}
      <div className="flex flex-wrap gap-2">
        {fieldRoles.map((r) => (
          <button
            key={r}
            onClick={() => setRoleFilter(r)}
            className={cn(
              'px-3 py-1.5 rounded-full text-xs font-semibold border transition-colors',
              roleFilter === r
                ? 'bg-brand-600 text-white border-brand-600'
                : 'bg-white text-gray-600 border-gray-300 hover:border-gray-400'
            )}
          >
            {r === 'all' ? 'All Roles' : ROLE_LABELS[r] ?? r}
          </button>
        ))}
      </div>

      {/* Staff grid */}
      {isError && (
        <div className="flex items-center gap-2 p-4 text-red-500 text-sm bg-red-50 border border-red-200 rounded-xl">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          Failed to load staff directory.
        </div>
      )}

      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="bg-white border border-gray-200 rounded-xl p-4 animate-pulse">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 rounded-full bg-gray-200" />
                <div className="flex-1 space-y-1.5">
                  <div className="h-3.5 bg-gray-200 rounded w-3/4" />
                  <div className="h-3 bg-gray-200 rounded w-1/2" />
                </div>
              </div>
              <div className="h-3 bg-gray-200 rounded w-full" />
            </div>
          ))}
        </div>
      ) : staff.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-gray-400">
          <Users className="w-10 h-10 mb-3 opacity-30" />
          <p className="text-sm">No staff found for this role</p>
          <p className="text-xs mt-1">Add staff via Settings → Users</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {staff.map((s) => (
            <div
              key={s.id}
              className="bg-white border border-gray-200 rounded-xl p-4 hover:border-gray-300 transition-colors"
            >
              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-brand-600 to-brand-700 flex items-center justify-center flex-shrink-0 shadow-sm">
                  <span className="text-sm font-bold text-white">
                    {s.full_name.split(' ').map((n) => n[0]).join('').slice(0, 2).toUpperCase()}
                  </span>
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-gray-900 truncate">{s.full_name}</p>
                  <span className={cn(
                    'inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold border mt-0.5',
                    ROLE_COLORS[s.role] ?? 'bg-gray-100 text-gray-600 border-gray-300'
                  )}>
                    {ROLE_LABELS[s.role] ?? s.role}
                  </span>
                </div>
              </div>
              <div className="space-y-1.5">
                <div className="flex items-center gap-2 text-xs text-gray-500">
                  <Mail className="w-3 h-3 flex-shrink-0" />
                  <span className="truncate">{s.email}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <p className="text-xs text-gray-400 text-center">
        To add or edit staff, go to <span className="font-medium text-gray-600">Settings → Users</span>
      </p>
    </div>
  )
}
