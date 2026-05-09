'use client'

import { useEffect, useRef } from 'react'
import {
  X,
  Bell,
  BellOff,
  CheckCheck,
  AlertTriangle,
  AlertCircle,
  Info,
  CheckCircle2,
  ExternalLink,
  RefreshCw,
  Wifi,
  WifiOff,
} from 'lucide-react'
import Link from 'next/link'
import { cn, formatTimeAgo } from '@/lib/utils'
import { useAgentAlerts, type AgentAlert, type AlertSeverity } from '@/hooks/useAgentAlerts'

// ---------------------------------------------------------------------------
// Severity config
// ---------------------------------------------------------------------------

const SEVERITY_CONFIG: Record<
  AlertSeverity,
  {
    icon: React.ElementType
    iconClass: string
    badgeClass: string
    borderClass: string
    label: string
  }
> = {
  critical: {
    icon: AlertCircle,
    iconClass: 'text-red-400',
    badgeClass: 'bg-red-50 text-red-600 border border-red-200',
    borderClass: 'border-l-red-500',
    label: 'Critical',
  },
  warning: {
    icon: AlertTriangle,
    iconClass: 'text-amber-400',
    badgeClass: 'bg-amber-50 text-amber-600 border border-amber-200',
    borderClass: 'border-l-amber-500',
    label: 'Warning',
  },
  info: {
    icon: Info,
    iconClass: 'text-brand-400',
    badgeClass: 'bg-brand-50 text-brand-600 border border-brand-200',
    borderClass: 'border-l-brand-500',
    label: 'Info',
  },
  success: {
    icon: CheckCircle2,
    iconClass: 'text-green-400',
    badgeClass: 'bg-green-50 text-green-600 border border-green-200',
    borderClass: 'border-l-green-500',
    label: 'Success',
  },
}

// ---------------------------------------------------------------------------
// Alert item
// ---------------------------------------------------------------------------

interface AlertItemProps {
  alert: AgentAlert
  onMarkRead: (id: string) => void
  onDismiss: (id: string) => void
}

function AlertItem({ alert, onMarkRead, onDismiss }: AlertItemProps) {
  const config = SEVERITY_CONFIG[alert.severity] ?? SEVERITY_CONFIG.info
  const Icon = config.icon

  return (
    <div
      className={cn(
        'relative flex gap-3 px-4 py-3.5 border-b border-gray-100',
        'border-l-2 transition-colors duration-150',
        config.borderClass,
        alert.is_read
          ? 'bg-transparent opacity-60 hover:opacity-80'
          : 'bg-brand-50/40 hover:bg-brand-50/60'
      )}
    >
      {/* Unread dot */}
      {!alert.is_read && (
        <span className="absolute top-3.5 right-3 w-2 h-2 rounded-full bg-green-500 flex-shrink-0" />
      )}

      {/* Icon */}
      <div className="flex-shrink-0 mt-0.5">
        <Icon className={cn('w-4 h-4', config.iconClass)} />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0 pr-4">
        {/* Header row */}
        <div className="flex items-start gap-2 flex-wrap">
          <span
            className={cn(
              'inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold leading-none',
              config.badgeClass
            )}
          >
            {config.label}
          </span>
          {alert.module && (
            <span
              className={cn(
                'inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium leading-none bg-gray-100 text-gray-500 border border-gray-200 capitalize'
              )}
            >
              {alert.module.replace(/_/g, ' ')}
            </span>
          )}
        </div>

        {/* Title */}
        <p
          className={cn(
            'mt-1.5 text-sm leading-snug',
            alert.is_read ? 'text-gray-400 font-normal' : 'text-gray-900 font-semibold'
          )}
        >
          {alert.title}
        </p>

        {/* Message */}
        <p className="mt-1 text-xs text-gray-500 leading-relaxed line-clamp-2">
          {alert.message}
        </p>

        {/* Footer */}
        <div className="mt-2 flex items-center gap-3 flex-wrap">
          <span className="text-[11px] text-gray-400">
            {formatTimeAgo(alert.created_at)}
          </span>

          {/* Action link */}
          {alert.action_url && alert.action_label && (
            <Link
              href={alert.action_url}
              className="inline-flex items-center gap-1 text-[11px] text-green-500 hover:text-green-600 font-medium transition-colors"
              onClick={() => {
                if (!alert.is_read) onMarkRead(alert.id)
              }}
            >
              {alert.action_label}
              <ExternalLink className="w-2.5 h-2.5" />
            </Link>
          )}

          {/* Mark as read */}
          {!alert.is_read && (
            <button
              onClick={() => onMarkRead(alert.id)}
              className="inline-flex items-center gap-1 text-[11px] text-gray-400 hover:text-gray-700 transition-colors"
            >
              Mark read
            </button>
          )}
        </div>
      </div>

      {/* Dismiss button */}
      <button
        onClick={() => onDismiss(alert.id)}
        className="absolute top-3 right-3 flex-shrink-0 text-gray-400 hover:text-gray-600 transition-colors p-0.5 rounded"
        aria-label="Dismiss"
      >
        <X className="w-3 h-3" />
      </button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
      <div className="flex items-center justify-center w-14 h-14 rounded-full bg-gray-100 mb-4">
        <BellOff className="w-6 h-6 text-gray-400" />
      </div>
      <p className="text-sm font-semibold text-gray-700">All clear</p>
      <p className="text-xs text-gray-400 mt-1 leading-relaxed">
        No alerts at the moment. We&apos;ll notify you when something needs your attention.
      </p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Loading skeleton
// ---------------------------------------------------------------------------

function LoadingSkeleton() {
  return (
    <div className="flex flex-col gap-0">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="px-4 py-3.5 border-b border-gray-100 border-l-2 border-l-gray-200">
          <div className="flex gap-3">
            <div className="w-4 h-4 rounded bg-gray-200 animate-pulse flex-shrink-0 mt-0.5" />
            <div className="flex-1 space-y-2">
              <div className="flex gap-2">
                <div className="h-4 w-14 rounded bg-gray-200 animate-pulse" />
                <div className="h-4 w-10 rounded bg-gray-200 animate-pulse" />
              </div>
              <div className="h-4 w-3/4 rounded bg-gray-200 animate-pulse" />
              <div className="h-3 w-full rounded bg-gray-100 animate-pulse" />
              <div className="h-3 w-1/2 rounded bg-gray-100 animate-pulse" />
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// NotificationPanel
// ---------------------------------------------------------------------------

interface NotificationPanelProps {
  open: boolean
  onClose: () => void
}

export default function NotificationPanel({ open, onClose }: NotificationPanelProps) {
  const {
    alerts,
    unreadCount,
    isLoading,
    isConnected,
    markRead,
    markAllRead,
    dismissAlert,
    refresh,
  } = useAgentAlerts()

  const panelRef = useRef<HTMLDivElement>(null)

  // Close on Escape key
  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if (e.key === 'Escape' && open) onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open, onClose])

  // Trap focus: close on outside click
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (
        open &&
        panelRef.current &&
        !panelRef.current.contains(e.target as Node)
      ) {
        onClose()
      }
    }
    // Use a slight delay so the button that opens the panel doesn't
    // immediately trigger this handler.
    const id = setTimeout(() => {
      document.addEventListener('mousedown', handler)
    }, 50)
    return () => {
      clearTimeout(id)
      document.removeEventListener('mousedown', handler)
    }
  }, [open, onClose])

  // Split into unread + read
  const unread = alerts.filter((a) => !a.is_read)
  const read = alerts.filter((a) => a.is_read)

  return (
    <>
      {/* Backdrop (only on mobile) */}
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm md:hidden"
          aria-hidden
          onClick={onClose}
        />
      )}

      {/* Panel */}
      <div
        ref={panelRef}
        role="dialog"
        aria-label="Notifications"
        aria-modal="true"
        className={cn(
          'fixed top-0 right-0 z-50 h-full w-full max-w-sm',
          'flex flex-col',
          'bg-white border-l border-gray-200',
          'shadow-2xl shadow-black/50',
          'transition-transform duration-300 ease-in-out',
          open ? 'translate-x-0' : 'translate-x-full'
        )}
      >
        {/* ---------------------------------------------------------------- */}
        {/* Header                                                            */}
        {/* ---------------------------------------------------------------- */}
        <div className="flex-shrink-0 flex items-center justify-between px-4 py-3.5 border-b border-gray-200 bg-white">
          <div className="flex items-center gap-2.5">
            <Bell className="w-4 h-4 text-gray-500" />
            <h2 className="text-sm font-semibold text-gray-900">Notifications</h2>
            {unreadCount > 0 && (
              <span className="inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1.5 rounded-full bg-red-500 text-[11px] font-bold text-white leading-none">
                {unreadCount > 99 ? '99+' : unreadCount}
              </span>
            )}
          </div>

          <div className="flex items-center gap-1">
            {/* Live indicator */}
            <div
              className={cn(
                'flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium',
                isConnected
                  ? 'text-green-600 bg-green-50'
                  : 'text-gray-400 bg-gray-100'
              )}
              title={isConnected ? 'Live updates active' : 'Not connected'}
            >
              {isConnected ? (
                <Wifi className="w-3 h-3" />
              ) : (
                <WifiOff className="w-3 h-3" />
              )}
              <span className="hidden sm:inline">
                {isConnected ? 'Live' : 'Offline'}
              </span>
            </div>

            {/* Refresh */}
            <button
              onClick={refresh}
              className="flex items-center justify-center w-7 h-7 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors"
              aria-label="Refresh notifications"
              title="Refresh"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>

            {/* Close */}
            <button
              onClick={onClose}
              className="flex items-center justify-center w-7 h-7 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors"
              aria-label="Close notifications"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* ---------------------------------------------------------------- */}
        {/* Actions bar                                                        */}
        {/* ---------------------------------------------------------------- */}
        {!isLoading && alerts.length > 0 && (
          <div className="flex-shrink-0 flex items-center justify-between px-4 py-2 border-b border-gray-200 bg-gray-50">
            <span className="text-xs text-gray-500">
              {alerts.length} notification{alerts.length !== 1 ? 's' : ''}
            </span>
            {unreadCount > 0 && (
              <button
                onClick={markAllRead}
                className="flex items-center gap-1.5 text-xs text-green-500 hover:text-green-600 font-medium transition-colors"
              >
                <CheckCheck className="w-3.5 h-3.5" />
                Mark all as read
              </button>
            )}
          </div>
        )}

        {/* ---------------------------------------------------------------- */}
        {/* Content                                                            */}
        {/* ---------------------------------------------------------------- */}
        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <LoadingSkeleton />
          ) : alerts.length === 0 ? (
            <EmptyState />
          ) : (
            <>
              {/* Unread section */}
              {unread.length > 0 && (
                <section>
                  <div className="sticky top-0 z-10 px-4 py-2 bg-white/90 backdrop-blur-sm border-b border-gray-100">
                    <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
                      Unread · {unread.length}
                    </span>
                  </div>
                  {unread.map((alert) => (
                    <AlertItem
                      key={alert.id}
                      alert={alert}
                      onMarkRead={markRead}
                      onDismiss={dismissAlert}
                    />
                  ))}
                </section>
              )}

              {/* Read section */}
              {read.length > 0 && (
                <section>
                  <div className="sticky top-0 z-10 px-4 py-2 bg-white/90 backdrop-blur-sm border-b border-gray-100">
                    <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
                      Earlier · {read.length}
                    </span>
                  </div>
                  {read.map((alert) => (
                    <AlertItem
                      key={alert.id}
                      alert={alert}
                      onMarkRead={markRead}
                      onDismiss={dismissAlert}
                    />
                  ))}
                </section>
              )}
            </>
          )}
        </div>

        {/* ---------------------------------------------------------------- */}
        {/* Footer                                                             */}
        {/* ---------------------------------------------------------------- */}
        <div className="flex-shrink-0 px-4 py-3 border-t border-gray-200 bg-white">
          <Link
            href="/ai-assistant"
            onClick={onClose}
            className="flex items-center justify-center w-full py-2 rounded-lg text-xs font-medium text-gray-500 hover:text-gray-900 hover:bg-gray-50 border border-gray-200 hover:border-gray-300 transition-all duration-150 gap-2"
          >
            <Bell className="w-3.5 h-3.5" />
            View all in AI Assistant
          </Link>
        </div>
      </div>
    </>
  )
}
