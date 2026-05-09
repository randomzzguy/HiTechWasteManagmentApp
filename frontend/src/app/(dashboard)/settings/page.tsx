'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useSession } from 'next-auth/react'
import {
  Settings, Users, Plus, RefreshCw, AlertCircle,
  CheckCircle2, XCircle, Shield, Bell, Mail, MessageSquare, Send,
} from 'lucide-react'
import { settingsApi } from '@/lib/api'
import { formatDate, cn } from '@/lib/utils'
import { toast } from 'sonner'
import UserFormDialog, { type UserRow } from '@/components/settings/UserFormDialog'

interface User {
  id: string
  email: string
  full_name: string
  role: string
  is_active: boolean
  created_at: string
}

const ROLE_STYLES: Record<string, string> = {
  superadmin:          'bg-red-900/40 text-red-300 border-red-700/50',
  management:          'bg-purple-900/40 text-purple-300 border-purple-700/50',
  operations_manager:  'bg-brand-900/40 text-brand-300 border-brand-700/50',
  field_supervisor:    'bg-amber-900/40 text-amber-300 border-amber-700/50',
  driver:              'bg-gray-100 text-gray-600 border-gray-300',
  compliance_officer:  'bg-brand-900/40 text-brand-300 border-brand-700/50',
  client:              'bg-green-900/40 text-green-300 border-green-700/50',
}

type Tab = 'users' | 'system' | 'notifications'

export default function SettingsPage() {
  const { data: session } = useSession()
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<Tab>('users')
  const [page, setPage] = useState(0)
  const PAGE_SIZE = 50

  const [dialogState, setDialogState] = useState<{
    open: boolean
    mode: 'create' | 'edit'
    user: UserRow | null
  }>({ open: false, mode: 'create', user: null })

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['settings', 'users', { page }],
    queryFn: () =>
      settingsApi.listUsers({
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      } as Parameters<typeof settingsApi.listUsers>[0]),
    staleTime: 60_000,
    enabled: activeTab === 'users',
  })

  const { data: sysConfig } = useQuery({
    queryKey: ['settings', 'config'],
    queryFn: () => settingsApi.getSystemConfig(),
    staleTime: 30_000,
    enabled: activeTab === 'notifications',
  })

  const testEmailMutation = useMutation({
    mutationFn: (to: string) => settingsApi.sendTestEmail(to),
    onSuccess: (data) => {
      if (data.success) {
        toast.success('Test email sent successfully')
      } else {
        toast.error(data.message ?? 'SMTP not configured or failed')
      }
    },
    onError: () => toast.error('Failed to send test email'),
  })

  const users = (data as { items?: User[] } | null)?.items ?? []
  const total = (data as { total?: number } | null)?.total ?? 0
  const totalPages = Math.ceil(total / PAGE_SIZE)

  const isAdmin = ['superadmin', 'management'].includes(session?.user?.role ?? '')

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            User management and system configuration
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 bg-gray-100 border border-gray-200 rounded-lg p-1 w-fit">
        {[
          { id: 'users' as Tab, label: 'Users', icon: Users },
          { id: 'system' as Tab, label: 'System', icon: Settings },
          { id: 'notifications' as Tab, label: 'Notifications', icon: Bell },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-md text-sm font-semibold transition-colors',
              activeTab === tab.id
                ? 'bg-brand-600 text-white'
                : 'text-gray-500 hover:text-gray-900 hover:bg-white'
            )}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Users tab */}
      {activeTab === 'users' && (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
            <span className="text-sm font-semibold text-gray-900">Platform Users</span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => refetch()}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-gray-500 hover:text-gray-900 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                Refresh
              </button>
              {isAdmin && (
                <button
                  onClick={() => setDialogState({ open: true, mode: 'create', user: null })}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-white bg-green-600 hover:bg-green-500 rounded-lg transition-colors"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Add User
                </button>
              )}
            </div>
          </div>

          {isError && (
            <div className="flex items-center gap-2 p-4 text-red-500 text-sm">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              Failed to load users.
            </div>
          )}

          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50">
                  {['Name', 'Email', 'Role', 'Status', 'Joined', ''].map((h) => (
                    <th key={h} className="px-4 py-3 text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {isLoading
                  ? Array.from({ length: 6 }).map((_, i) => (
                      <tr key={i} className="border-b border-gray-100">
                        {Array.from({ length: 6 }).map((_, j) => (
                          <td key={j} className="px-4 py-3">
                            <div className="h-4 rounded bg-gray-200 animate-pulse" style={{ width: `${50 + Math.random() * 50}%` }} />
                          </td>
                        ))}
                      </tr>
                    ))
                  : users.length === 0
                  ? (
                      <tr>
                        <td colSpan={6} className="px-4 py-12 text-center text-gray-400 text-sm">
                          <Users className="w-8 h-8 mx-auto mb-2 opacity-30" />
                          No users found
                        </td>
                      </tr>
                    )
                  : users.map((u) => (
                      <tr key={u.id} className="border-b border-gray-100 hover:bg-gray-50 transition-colors">
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-green-600 to-emerald-700 flex items-center justify-center flex-shrink-0">
                              <span className="text-[10px] font-bold text-white">
                                {u.full_name.split(' ').map((n) => n[0]).join('').slice(0, 2).toUpperCase()}
                              </span>
                            </div>
                            <span className="text-sm text-gray-900 font-medium">{u.full_name}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <span className="text-xs text-gray-500">{u.email}</span>
                        </td>
                        <td className="px-4 py-3">
                          <span className={cn(
                            'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold border',
                            ROLE_STYLES[u.role] ?? 'bg-gray-100 text-gray-600 border-gray-300'
                          )}>
                            <Shield className="w-2.5 h-2.5" />
                            {u.role.replace('_', ' ')}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          {u.is_active ? (
                            <span className="flex items-center gap-1 text-xs text-green-400">
                              <CheckCircle2 className="w-3 h-3" /> Active
                            </span>
                          ) : (
                            <span className="flex items-center gap-1 text-xs text-gray-400">
                              <XCircle className="w-3 h-3" /> Inactive
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <span className="text-xs text-gray-400">{formatDate(u.created_at)}</span>
                        </td>
                        <td className="px-4 py-3 text-right">
                          {isAdmin && (
                            <button
                              onClick={() => setDialogState({ open: true, mode: 'edit', user: u as UserRow })}
                              className="text-xs text-gray-400 hover:text-gray-900 px-2 py-1 rounded hover:bg-gray-100 transition-colors"
                            >
                              Edit
                            </button>
                          )}
                        </td>
                      </tr>
                    ))
                }
              </tbody>
            </table>
          </div>

          {total > PAGE_SIZE && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200 text-xs text-gray-500">
              <span>{total} total users</span>
              <div className="flex items-center gap-2">
                <button disabled={page === 0} onClick={() => setPage((p) => p - 1)}
                  className="px-3 py-1.5 rounded bg-gray-100 hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors text-gray-700">
                  Previous
                </button>
                <span>Page {page + 1} of {totalPages}</span>
                <button disabled={page >= totalPages - 1} onClick={() => setPage((p) => p + 1)}
                  className="px-3 py-1.5 rounded bg-gray-100 hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors text-gray-700">
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* User form dialog */}
      <UserFormDialog
        mode={dialogState.mode}
        user={dialogState.user}
        open={dialogState.open}
        onOpenChange={(open) => setDialogState((s) => ({ ...s, open }))}
        onSuccess={() =>
          queryClient.invalidateQueries({ queryKey: ['settings', 'users'] })
        }
      />

      {/* System tab */}
      {activeTab === 'system' && (
        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <p className="text-sm text-gray-500">
            System configuration settings will be available here.
          </p>
        </div>
      )}

      {/* Notifications tab */}
      {activeTab === 'notifications' && (
        <div className="flex flex-col gap-4">
          {/* Email / SMTP */}
          <div className="bg-white border border-gray-200 rounded-xl p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-8 h-8 rounded-lg bg-brand-50 flex items-center justify-center">
                <Mail className="w-4 h-4 text-brand-600" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-gray-900">Email (SMTP)</h3>
                <p className="text-xs text-gray-500">Job status updates and compliance alerts</p>
              </div>
              <div className="ml-auto">
                {(sysConfig as Record<string, unknown>)?.smtp_configured ? (
                  <span className="flex items-center gap-1.5 text-xs font-medium text-green-600 bg-green-50 border border-green-200 px-2.5 py-1 rounded-full">
                    <CheckCircle2 className="w-3 h-3" /> Configured
                  </span>
                ) : (
                  <span className="flex items-center gap-1.5 text-xs font-medium text-amber-600 bg-amber-50 border border-amber-200 px-2.5 py-1 rounded-full">
                    <AlertCircle className="w-3 h-3" /> Not configured
                  </span>
                )}
              </div>
            </div>

            {!!(sysConfig as Record<string, unknown>)?.smtp_configured && (
              <div className="text-xs text-gray-500 mb-4 space-y-1">
                <p>Host: <span className="text-gray-700 font-mono">{String((sysConfig as Record<string, unknown>).smtp_host ?? '')}</span></p>
                <p>From: <span className="text-gray-700">{String((sysConfig as Record<string, unknown>).smtp_from_name ?? '')}</span></p>
              </div>
            )}

            {!(sysConfig as Record<string, unknown>)?.smtp_configured && (
              <p className="text-xs text-gray-400 mb-4">
                Set <code className="bg-gray-100 px-1 rounded">SMTP_USER</code> and{' '}
                <code className="bg-gray-100 px-1 rounded">SMTP_PASSWORD</code> in your{' '}
                <code className="bg-gray-100 px-1 rounded">.env</code> to enable email notifications.
              </p>
            )}

            <button
              onClick={() => testEmailMutation.mutate(session?.user?.email ?? '')}
              disabled={testEmailMutation.isPending || !(sysConfig as Record<string, unknown>)?.smtp_configured}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-brand-600 hover:bg-brand-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors"
            >
              {testEmailMutation.isPending ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
              Send Test Email
            </button>
            {session?.user?.email && (
              <p className="text-xs text-gray-400 mt-2">
                Will send to <span className="text-gray-600">{session.user.email}</span>
              </p>
            )}
          </div>

          {/* WhatsApp */}
          <div className="bg-white border border-gray-200 rounded-xl p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-8 h-8 rounded-lg bg-green-50 flex items-center justify-center">
                <MessageSquare className="w-4 h-4 text-green-600" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-gray-900">WhatsApp Business</h3>
                <p className="text-xs text-gray-500">Real-time driver and client messaging</p>
              </div>
              <div className="ml-auto">
                {(sysConfig as Record<string, unknown>)?.whatsapp_configured ? (
                  <span className="flex items-center gap-1.5 text-xs font-medium text-green-600 bg-green-50 border border-green-200 px-2.5 py-1 rounded-full">
                    <CheckCircle2 className="w-3 h-3" /> Configured
                  </span>
                ) : (
                  <span className="flex items-center gap-1.5 text-xs font-medium text-amber-600 bg-amber-50 border border-amber-200 px-2.5 py-1 rounded-full">
                    <AlertCircle className="w-3 h-3" /> Not configured
                  </span>
                )}
              </div>
            </div>
            {!(sysConfig as Record<string, unknown>)?.whatsapp_configured && (
              <p className="text-xs text-gray-400">
                Set <code className="bg-gray-100 px-1 rounded">WHATSAPP_API_URL</code> and{' '}
                <code className="bg-gray-100 px-1 rounded">WHATSAPP_API_TOKEN</code> in your{' '}
                <code className="bg-gray-100 px-1 rounded">.env</code> to enable WhatsApp notifications.
                See <code className="bg-gray-100 px-1 rounded">.env.example</code> for setup instructions.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
