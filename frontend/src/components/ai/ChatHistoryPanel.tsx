'use client'

import { useEffect, useState } from 'react'
import { History, MessageSquare, Trash2, X, Clock, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ChatSession {
  id: string
  title: string          // first user message (truncated)
  createdAt: string      // ISO timestamp
  messageCount: number
  messages: StoredMessage[]
}

export interface StoredMessage {
  role: 'user' | 'assistant'
  content: string
  ragChunksUsed?: number
  error?: boolean
}

const STORAGE_KEY = 'hitech_ai_chat_history'
const MAX_SESSIONS = 50

// ---------------------------------------------------------------------------
// Storage helpers
// ---------------------------------------------------------------------------

export function loadSessions(): ChatSession[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as ChatSession[]) : []
  } catch {
    return []
  }
}

export function saveSession(session: ChatSession): void {
  if (typeof window === 'undefined') return
  try {
    const sessions = loadSessions()
    const existing = sessions.findIndex((s) => s.id === session.id)
    if (existing >= 0) {
      sessions[existing] = session
    } else {
      sessions.unshift(session)
    }
    // Keep only the most recent MAX_SESSIONS
    const trimmed = sessions.slice(0, MAX_SESSIONS)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed))
  } catch {
    // Ignore storage errors (e.g. quota exceeded)
  }
}

export function deleteSession(id: string): void {
  if (typeof window === 'undefined') return
  try {
    const sessions = loadSessions().filter((s) => s.id !== id)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions))
  } catch {}
}

export function clearAllSessions(): void {
  if (typeof window === 'undefined') return
  localStorage.removeItem(STORAGE_KEY)
}

// ---------------------------------------------------------------------------
// Relative time helper
// ---------------------------------------------------------------------------

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  if (days < 7) return `${days}d ago`
  return new Date(iso).toLocaleDateString('en-MY', { day: 'numeric', month: 'short' })
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface ChatHistoryPanelProps {
  open: boolean
  onClose: () => void
  onLoadSession: (session: ChatSession) => void
  currentSessionId?: string
}

export default function ChatHistoryPanel({
  open,
  onClose,
  onLoadSession,
  currentSessionId,
}: ChatHistoryPanelProps) {
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [confirmClear, setConfirmClear] = useState(false)

  // Reload sessions whenever panel opens
  useEffect(() => {
    if (open) {
      setSessions(loadSessions())
    }
  }, [open])

  function handleDelete(id: string, e: React.MouseEvent) {
    e.stopPropagation()
    deleteSession(id)
    setSessions((prev) => prev.filter((s) => s.id !== id))
  }

  function handleClearAll() {
    if (!confirmClear) {
      setConfirmClear(true)
      setTimeout(() => setConfirmClear(false), 3000)
      return
    }
    clearAllSessions()
    setSessions([])
    setConfirmClear(false)
  }

  // Group sessions by date
  const today = new Date().toDateString()
  const yesterday = new Date(Date.now() - 86400000).toDateString()

  function getGroup(iso: string): string {
    const d = new Date(iso).toDateString()
    if (d === today) return 'Today'
    if (d === yesterday) return 'Yesterday'
    const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000)
    if (diff < 7) return 'This week'
    if (diff < 30) return 'This month'
    return 'Older'
  }

  const grouped = sessions.reduce<Record<string, ChatSession[]>>((acc, s) => {
    const g = getGroup(s.createdAt)
    if (!acc[g]) acc[g] = []
    acc[g].push(s)
    return acc
  }, {})

  const groupOrder = ['Today', 'Yesterday', 'This week', 'This month', 'Older']

  return (
    <>
      {/* Backdrop */}
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/20 backdrop-blur-sm"
          onClick={onClose}
          aria-hidden
        />
      )}

      {/* Panel */}
      <div
        className={cn(
          'fixed top-0 left-0 z-50 h-full w-72 flex flex-col',
          'bg-white border-r border-gray-200 shadow-xl',
          'transition-transform duration-300 ease-in-out',
          open ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3.5 border-b border-gray-200">
          <div className="flex items-center gap-2">
            <History className="w-4 h-4 text-brand-600" />
            <h2 className="text-sm font-semibold text-gray-900">Chat History</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Session list */}
        <div className="flex-1 overflow-y-auto py-2">
          {sessions.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full gap-3 px-6 text-center">
              <div className="w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center">
                <MessageSquare className="w-5 h-5 text-gray-400" />
              </div>
              <p className="text-sm font-medium text-gray-600">No chat history yet</p>
              <p className="text-xs text-gray-400 leading-relaxed">
                Your conversations will appear here after you start chatting.
              </p>
            </div>
          ) : (
            groupOrder.map((group) => {
              const groupSessions = grouped[group]
              if (!groupSessions?.length) return null
              return (
                <div key={group}>
                  <p className="px-4 py-2 text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
                    {group}
                  </p>
                  {groupSessions.map((session) => (
                    <button
                      key={session.id}
                      onClick={() => { onLoadSession(session); onClose() }}
                      className={cn(
                        'w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors group relative',
                        currentSessionId === session.id && 'bg-brand-50 border-r-2 border-brand-600'
                      )}
                    >
                      <div className="flex items-start gap-2 pr-6">
                        <MessageSquare className="w-3.5 h-3.5 text-gray-400 flex-shrink-0 mt-0.5" />
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-medium text-gray-800 truncate leading-snug">
                            {session.title}
                          </p>
                          <div className="flex items-center gap-2 mt-0.5">
                            <Clock className="w-2.5 h-2.5 text-gray-400" />
                            <span className="text-[10px] text-gray-400">
                              {relativeTime(session.createdAt)}
                            </span>
                            <span className="text-[10px] text-gray-300">·</span>
                            <span className="text-[10px] text-gray-400">
                              {session.messageCount} msg{session.messageCount !== 1 ? 's' : ''}
                            </span>
                          </div>
                        </div>
                      </div>
                      {/* Delete button */}
                      <button
                        onClick={(e) => handleDelete(session.id, e)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 p-1 rounded text-gray-400 hover:text-red-500 hover:bg-red-50 transition-all"
                        title="Delete session"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </button>
                  ))}
                </div>
              )
            })
          )}
        </div>

        {/* Footer */}
        {sessions.length > 0 && (
          <div className="border-t border-gray-200 p-3">
            <button
              onClick={handleClearAll}
              className={cn(
                'w-full flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-medium transition-colors',
                confirmClear
                  ? 'bg-red-50 text-red-600 border border-red-200 hover:bg-red-100'
                  : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100 border border-gray-200'
              )}
            >
              <Trash2 className="w-3.5 h-3.5" />
              {confirmClear ? 'Click again to confirm' : 'Clear all history'}
            </button>
          </div>
        )}
      </div>
    </>
  )
}
