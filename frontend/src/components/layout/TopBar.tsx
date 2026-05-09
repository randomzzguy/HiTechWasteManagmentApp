'use client'

import { useState, useRef, useEffect } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import { useSession, signOut } from 'next-auth/react'
import {
  Bell,
  Search,
  LogOut,
  User,
  Settings,
  ChevronDown,
  X,
  HelpCircle,
} from 'lucide-react'
import { cn, getInitials, avatarColor } from '@/lib/utils'
import { useAgentAlerts } from '@/hooks/useAgentAlerts'

// ---------------------------------------------------------------------------
// Route → title mapping
// ---------------------------------------------------------------------------

const ROUTE_TITLES: Record<string, { title: string; subtitle?: string }> = {
  '/dashboard': { title: 'Dashboard', subtitle: 'Operations Overview' },
  '/clients': { title: 'Clients', subtitle: 'Client Directory' },
  '/jobs': { title: 'Jobs', subtitle: 'Job Management' },
  '/fleet': { title: 'Fleet', subtitle: 'Fleet Operations' },
  '/weighbridge': { title: 'Weighbridge', subtitle: 'Weight Records & Tonnage' },
  '/compliance': { title: 'Compliance', subtitle: 'Regulatory Compliance' },
  '/compliance/scheduled-waste': { title: 'Scheduled Waste', subtitle: 'SW Batch Tracker' },
  '/recyclables': { title: 'Recyclables', subtitle: 'Material Recovery' },
  '/destruction': { title: 'Destruction', subtitle: 'Witnessed Destruction' },
  '/bsf-farm': { title: 'BSF Farm', subtitle: 'Black Soldier Fly Operations' },
  '/esg': { title: 'ESG & Carbon', subtitle: 'Sustainability Dashboard' },
  '/finance': { title: 'Finance', subtitle: 'Invoicing & Revenue' },
  '/ai-assistant': { title: 'AI Assistant', subtitle: 'Intelligent Operations Assistant' },
  '/reports': { title: 'Reports', subtitle: 'Report Generator' },
  '/settings': { title: 'Settings', subtitle: 'System Configuration' },
  '/labour': { title: 'Labour', subtitle: 'Labour Management' },
  '/equipment': { title: 'Equipment', subtitle: 'Equipment Registry' },
  '/disruptions': { title: 'Disruptions', subtitle: 'Operational Disruptions' },
  '/recycler-deliveries': { title: 'Deliveries', subtitle: 'Recycler Deliveries' },
}

function getRouteInfo(pathname: string): { title: string; subtitle?: string } {
  if (ROUTE_TITLES[pathname]) return ROUTE_TITLES[pathname]
  const segments = pathname.split('/').filter(Boolean)
  for (let i = segments.length; i > 0; i--) {
    const candidate = '/' + segments.slice(0, i).join('/')
    if (ROUTE_TITLES[candidate]) return ROUTE_TITLES[candidate]
  }
  const last = segments[segments.length - 1] ?? ''
  return {
    title: last.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()) || 'Hi-Tech Waste',
  }
}

// ---------------------------------------------------------------------------
// SearchBar
// ---------------------------------------------------------------------------

function SearchBar() {
  const [query, setQuery] = useState('')
  const [focused, setFocused] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        inputRef.current?.focus()
      }
      if (e.key === 'Escape' && focused) {
        inputRef.current?.blur()
        setQuery('')
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [focused])

  return (
    <div className="relative hidden md:block">
      <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-brand-300 pointer-events-none" />
      <input
        ref={inputRef}
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        placeholder="Search…"
        className={cn(
          'pl-8 pr-12 py-1.5 rounded-lg text-sm text-white placeholder-brand-300',
          'bg-brand-600 border transition-all duration-150 outline-none w-52 lg:w-72',
          focused
            ? 'border-white ring-2 ring-white/20'
            : 'border-brand-500 hover:border-brand-400'
        )}
      />
      {!focused && !query && (
        <kbd className="absolute right-2.5 top-1/2 -translate-y-1/2 hidden lg:inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded border border-brand-500 bg-brand-800 text-brand-300 text-[10px] font-mono pointer-events-none">
          ⌘K
        </kbd>
      )}
      {query && (
        <button
          onClick={() => setQuery('')}
          className="absolute right-2.5 top-1/2 -translate-y-1/2 text-brand-300 hover:text-white transition-colors"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// NotificationBell
// ---------------------------------------------------------------------------

interface NotificationBellProps {
  unreadCount: number
  onClick: () => void
}

function NotificationBell({ unreadCount, onClick }: NotificationBellProps) {
  return (
    <button
      onClick={onClick}
      className="relative flex items-center justify-center w-8 h-8 rounded-lg text-brand-200 hover:text-white hover:bg-brand-600 transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40"
      aria-label={unreadCount > 0 ? `${unreadCount} unread notifications` : 'Notifications'}
    >
      <Bell className="w-4 h-4" />
      {unreadCount > 0 && (
        <span
          className="absolute -top-0.5 -right-0.5 flex items-center justify-center min-w-[1.1rem] h-[1.1rem] px-1 rounded-full text-[10px] font-bold text-white leading-none bg-red-500 animate-pulse"
          aria-hidden
        >
          {unreadCount > 99 ? '99+' : unreadCount}
        </span>
      )}
    </button>
  )
}

// ---------------------------------------------------------------------------
// UserDropdown
// ---------------------------------------------------------------------------

interface UserDropdownProps {
  name: string
  email: string
  role: string
}

function UserDropdown({ name, email, role }: UserDropdownProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const router = useRouter()

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    if (open) document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    if (open) document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open])

  async function handleSignOut() {
    setOpen(false)
    await signOut({ callbackUrl: '/login' })
  }

  const initials = getInitials(name)
  const bgClass = avatarColor(name)
  const roleLabel = role
    ? role.charAt(0).toUpperCase() + role.slice(1).replace(/_/g, ' ')
    : 'Viewer'

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className={cn(
          'flex items-center gap-2 pl-1.5 pr-2 py-1 rounded-lg',
          'text-sm text-brand-100 hover:text-white',
          'hover:bg-brand-600 transition-all duration-150',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40',
          open && 'bg-brand-600 text-white'
        )}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <span className={cn('flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold text-white flex-shrink-0', bgClass)}>
          {initials}
        </span>
        <span className="hidden sm:flex flex-col items-start leading-tight">
          <span className="text-xs font-semibold text-white truncate max-w-[120px]">{name}</span>
          <span className="text-[10px] text-brand-300">{roleLabel}</span>
        </span>
        <ChevronDown className={cn('w-3.5 h-3.5 text-brand-300 transition-transform duration-150 hidden sm:block', open && 'rotate-180')} />
      </button>

      {/* Dropdown panel — light on dark topbar */}
      {open && (
        <div
          role="menu"
          className="absolute right-0 mt-2 w-64 z-50 bg-white border border-gray-200 rounded-xl shadow-2xl shadow-black/20 animate-in"
        >
          <div className="px-4 py-3 border-b border-gray-100">
            <div className="flex items-center gap-3">
              <span className={cn('flex items-center justify-center w-10 h-10 rounded-full text-sm font-bold text-white flex-shrink-0', bgClass)}>
                {initials}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-gray-900 truncate">{name}</p>
                <p className="text-xs text-gray-500 truncate">{email}</p>
                <span className="mt-1 inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-semibold bg-brand-50 text-brand-700 border border-brand-200">
                  {roleLabel}
                </span>
              </div>
            </div>
          </div>

          <div className="py-1.5">
            <button
              role="menuitem"
              onClick={() => { setOpen(false); router.push('/settings') }}
              className="w-full flex items-center gap-3 px-4 py-2 text-sm text-gray-700 hover:text-gray-900 hover:bg-gray-50 transition-colors text-left"
            >
              <User className="w-4 h-4 text-gray-400" />
              <span>My Profile</span>
            </button>
            <button
              role="menuitem"
              onClick={() => { setOpen(false); router.push('/settings') }}
              className="w-full flex items-center gap-3 px-4 py-2 text-sm text-gray-700 hover:text-gray-900 hover:bg-gray-50 transition-colors text-left"
            >
              <Settings className="w-4 h-4 text-gray-400" />
              <span>Settings</span>
            </button>
            <button
              role="menuitem"
              onClick={() => setOpen(false)}
              className="w-full flex items-center gap-3 px-4 py-2 text-sm text-gray-700 hover:text-gray-900 hover:bg-gray-50 transition-colors text-left"
            >
              <HelpCircle className="w-4 h-4 text-gray-400" />
              <span>Help & Support</span>
            </button>
          </div>

          <div className="border-t border-gray-100 py-1.5">
            <button
              role="menuitem"
              onClick={handleSignOut}
              className="w-full flex items-center gap-3 px-4 py-2 text-sm text-red-500 hover:text-red-600 hover:bg-red-50 transition-colors text-left"
            >
              <LogOut className="w-4 h-4" />
              <span>Sign Out</span>
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main TopBar
// ---------------------------------------------------------------------------

interface TopBarProps {
  onNotificationsClick?: () => void
}

export default function TopBar({ onNotificationsClick }: TopBarProps) {
  const pathname = usePathname()
  const { data: session } = useSession()
  const { unreadCount } = useAgentAlerts()

  const { title, subtitle } = getRouteInfo(pathname)

  function handleBellClick() {
    onNotificationsClick?.()
  }

  return (
    <header className="flex-shrink-0 h-14 flex items-center justify-between px-4 lg:px-6 bg-gradient-to-r from-brand-800 to-brand-700 border-b border-brand-600/80 z-30">
      {/* Left: Page title */}
      <div className="flex items-center gap-3 min-w-0">
        {/* Mobile spacing for hamburger button */}
        <div className="w-8 lg:hidden flex-shrink-0" />
        <div className="min-w-0">
          <h1 className="text-base font-bold text-white leading-tight truncate">{title}</h1>
          {subtitle && (
            <p className="text-xs text-gray-200 leading-tight truncate hidden sm:block">{subtitle}</p>
          )}
        </div>
      </div>

      {/* Right: actions */}
      <div className="flex items-center gap-2">
        <SearchBar />

        <NotificationBell unreadCount={unreadCount} onClick={handleBellClick} />

        {/* Divider */}
        <div className="w-px h-6 bg-brand-600 mx-1 hidden sm:block" />

        {session?.user ? (
          <UserDropdown
            name={session.user.name ?? session.user.email ?? 'User'}
            email={session.user.email ?? ''}
            role={session.user.role ?? 'viewer'}
          />
        ) : (
          <div className="w-7 h-7 rounded-full bg-brand-600 animate-pulse" />
        )}
      </div>
    </header>
  )
}
