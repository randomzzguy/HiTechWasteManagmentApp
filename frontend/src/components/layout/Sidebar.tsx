'use client'

import Link from 'next/link'
import Image from 'next/image'
import { usePathname } from 'next/navigation'
import { useSession } from 'next-auth/react'
import { useState } from 'react'
import {
  LayoutDashboard,
  Users,
  ClipboardList,
  Truck,
  Scale,
  Shield,
  Recycle,
  Flame,
  BarChart3,
  DollarSign,
  Bot,
  FileText,
  Settings,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  Menu,
  X,
  Container,
  HardHat,
  AlertTriangle,
  PackageCheck,
  Smartphone,
} from 'lucide-react'
import { cn } from '@/lib/utils'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type UserRole = string

interface NavItem {
  label: string
  href: string
  icon: React.ElementType
  allowedRoles?: UserRole[]
  highlight?: boolean
  badge?: string
}

interface NavGroup {
  label: string
  collapsible: boolean
  defaultOpen: boolean
  items: NavItem[]
}

// ---------------------------------------------------------------------------
// Role check
// ---------------------------------------------------------------------------

function canSeeItem(item: NavItem, role?: string): boolean {
  if (!item.allowedRoles) {
    // Items with no allowedRoles are visible to all authenticated users
    return true
  }
  if (!role) return false
  return item.allowedRoles.includes(role)
}

// ---------------------------------------------------------------------------
// Navigation groups
// ---------------------------------------------------------------------------

const ADMIN_SUPERVISOR = [
  'superadmin', 'admin', 'management', 'manager',
  'operations_manager', 'field_supervisor', 'supervisor', 'compliance_officer',
]
const ADMIN_MANAGER = ['superadmin', 'admin', 'management', 'manager']
const ADMIN_DRIVER = [
  'superadmin', 'admin', 'management', 'manager',
  'operations_manager', 'field_supervisor', 'supervisor', 'driver', 'compliance_officer',
]
const ADMIN_ONLY = ['superadmin', 'admin']

const NAV_GROUPS: NavGroup[] = [
  {
    label: 'Overview',
    collapsible: false,
    defaultOpen: true,
    items: [
      // No allowedRoles → visible to everyone including client
      { label: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
    ],
  },
  {
    label: 'Operations',
    collapsible: true,
    defaultOpen: true,
    items: [
      { label: 'Jobs', href: '/jobs', icon: ClipboardList, allowedRoles: [...ADMIN_DRIVER, 'client'] },
      { label: 'Fleet', href: '/fleet', icon: Truck, allowedRoles: ADMIN_SUPERVISOR },
      { label: 'Weighbridge', href: '/weighbridge', icon: Scale, allowedRoles: ADMIN_SUPERVISOR },
      { label: 'Staff', href: '/labour', icon: HardHat, allowedRoles: ADMIN_SUPERVISOR },
      { label: 'Equipment', href: '/equipment', icon: Container, allowedRoles: ADMIN_SUPERVISOR },
      { label: 'Incidents', href: '/disruptions', icon: AlertTriangle, allowedRoles: ADMIN_DRIVER },
    ],
  },
  {
    label: 'Compliance & Waste',
    collapsible: true,
    defaultOpen: true,
    items: [
      { label: 'Scheduled Waste', href: '/compliance/scheduled-waste', icon: Shield, allowedRoles: ADMIN_SUPERVISOR },
      { label: 'Recyclables', href: '/recyclables', icon: Recycle, allowedRoles: ADMIN_SUPERVISOR },
      { label: 'Destruction', href: '/destruction', icon: Flame, allowedRoles: ADMIN_SUPERVISOR },
      { label: 'Deliveries', href: '/recycler-deliveries', icon: PackageCheck, allowedRoles: ADMIN_DRIVER },
    ],
  },
  {
    label: 'Sustainability',
    collapsible: true,
    defaultOpen: false,
    items: [
      { label: 'ESG & Carbon', href: '/esg', icon: BarChart3, allowedRoles: [...ADMIN_MANAGER, 'client'] },
    ],
  },
  {
    label: 'Business',
    collapsible: true,
    defaultOpen: false,
    items: [
      { label: 'Clients', href: '/clients', icon: Users, allowedRoles: ADMIN_SUPERVISOR },
      { label: 'Finance', href: '/finance', icon: DollarSign, allowedRoles: ADMIN_MANAGER },
      { label: 'Reports', href: '/reports', icon: FileText, allowedRoles: ADMIN_SUPERVISOR },
    ],
  },
  {
    label: 'System',
    collapsible: true,
    defaultOpen: false,
    items: [
      { label: 'Driver App', href: '/driver', icon: Smartphone, allowedRoles: ['driver'], highlight: true },
      { label: 'AI Assistant', href: '/ai-assistant', icon: Bot, highlight: true, allowedRoles: [...ADMIN_DRIVER, ...ADMIN_MANAGER] },
      { label: 'Settings', href: '/settings', icon: Settings, allowedRoles: ADMIN_ONLY },
    ],
  },
]

// ---------------------------------------------------------------------------
// NavLink
// ---------------------------------------------------------------------------

interface NavLinkProps {
  item: NavItem
  isActive: boolean
  collapsed: boolean
}

function NavLink({ item, isActive, collapsed }: NavLinkProps) {
  const Icon = item.icon

  return (
    <Link
      href={item.href}
      title={collapsed ? item.label : undefined}
      className={cn(
        'relative group flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-150',
        isActive
          ? 'bg-brand-600/10 text-brand-700 font-semibold ring-1 ring-brand-600/20'
          : item.highlight
          ? 'text-brand-600 hover:bg-brand-50 hover:text-brand-700'
          : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900',
        collapsed && 'justify-center px-2'
      )}
    >
      <Icon
        className={cn(
          'flex-shrink-0',
          collapsed ? 'w-5 h-5' : 'w-4 h-4',
          isActive ? 'text-brand-600' : item.highlight ? 'text-brand-500' : 'text-gray-400 group-hover:text-gray-600'
        )}
      />
      {!collapsed && (
        <span className="truncate flex-1">{item.label}</span>
      )}
      {!collapsed && item.highlight && !isActive && (
        <span className="text-[10px] font-bold text-brand-600 bg-brand-50 border border-brand-200 px-1.5 py-0.5 rounded-full leading-none">
          AI
        </span>
      )}
      {!collapsed && item.badge && (
        <span className="text-[10px] font-bold bg-red-500 text-white px-1.5 py-0.5 rounded-full leading-none min-w-[1.25rem] text-center">
          {item.badge}
        </span>
      )}
      {/* Tooltip for collapsed state */}
      {collapsed && (
        <span className="absolute left-full ml-2 px-2 py-1 text-xs font-medium text-white bg-gray-800 rounded-md opacity-0 group-hover:opacity-100 pointer-events-none whitespace-nowrap z-50 shadow-lg transition-opacity duration-150">
          {item.label}
        </span>
      )}
    </Link>
  )
}

// ---------------------------------------------------------------------------
// NavGroupSection
// ---------------------------------------------------------------------------

interface NavGroupSectionProps {
  group: NavGroup
  visibleItems: NavItem[]
  isOpen: boolean
  onToggle: () => void
  collapsed: boolean
  isItemActive: (href: string) => boolean
}

function NavGroupSection({ group, visibleItems, isOpen, onToggle, collapsed, isItemActive }: NavGroupSectionProps) {
  if (visibleItems.length === 0) return null

  return (
    <div>
      {/* Group header */}
      {!collapsed && (
        group.collapsible ? (
          <button
            onClick={onToggle}
            className="w-full flex items-center justify-between px-3 py-2 group"
          >
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
              {group.label}
            </span>
            <ChevronDown
              className={cn(
                'w-3.5 h-3.5 text-gray-400 transition-transform duration-200',
                isOpen ? 'rotate-0' : '-rotate-90'
              )}
            />
          </button>
        ) : (
          <div className="px-3 py-2">
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
              {group.label}
            </span>
          </div>
        )
      )}

      {/* Items */}
      {(isOpen || !group.collapsible) && (
        <div className={cn('flex flex-col gap-0.5', collapsed ? 'px-2' : 'px-2')}>
          {visibleItems.map((item) => (
            <NavLink
              key={item.href}
              item={item}
              isActive={isItemActive(item.href)}
              collapsed={collapsed}
            />
          ))}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Sidebar
// ---------------------------------------------------------------------------

interface SidebarProps {
  className?: string
}

export default function Sidebar({ className }: SidebarProps) {
  const pathname = usePathname()
  const { data: session } = useSession()
  const userRole = session?.user?.role

  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)

  // Track open/closed state per group
  const [groupOpen, setGroupOpen] = useState<Record<string, boolean>>(() => {
    const init: Record<string, boolean> = {}
    NAV_GROUPS.forEach((g) => { init[g.label] = g.defaultOpen })
    return init
  })

  function toggleGroup(label: string) {
    setGroupOpen((prev) => ({ ...prev, [label]: !prev[label] }))
  }

  function isItemActive(href: string): boolean {
    if (href === '/dashboard') return pathname === '/dashboard'
    return pathname.startsWith(href)
  }

  const sidebarContent = (
    <div
      className={cn(
        'flex flex-col h-full bg-white border-r border-gray-200 transition-all duration-300',
        collapsed ? 'w-16' : 'w-64',
        className
      )}
    >
      {/* Brand header */}
      <div className={cn(
        'flex items-center flex-shrink-0 bg-gradient-to-b from-brand-700 to-brand-800',
        collapsed ? 'justify-center px-2 py-4' : 'gap-3 px-4 py-4'
      )}>
        <div className="flex-shrink-0 flex items-center justify-center w-8 h-8 rounded-lg bg-white/20 shadow overflow-hidden">
          <Image
            src="/logo.png"
            alt="Hi-Tech Waste"
            width={32}
            height={32}
            className="rounded"
          />
        </div>
        {!collapsed && (
          <div className="flex flex-col leading-tight min-w-0">
            <span className="text-white font-bold text-sm tracking-tight truncate">
              Hi-Tech Waste
            </span>
            <span className="text-brand-200 text-[10px] font-semibold tracking-widest uppercase truncate">
              Management
            </span>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav
        className="flex-1 overflow-y-auto overflow-x-hidden py-2 scrollbar-hide"
        aria-label="Main navigation"
      >
        <div className="flex flex-col gap-1">
          {NAV_GROUPS.map((group, idx) => {
            const visibleItems = group.items.filter((item) => canSeeItem(item, userRole))
            return (
              <div key={group.label}>
                {idx > 0 && <div className="border-t border-gray-100 my-1" />}
                <NavGroupSection
                  group={group}
                  visibleItems={visibleItems}
                  isOpen={groupOpen[group.label] ?? group.defaultOpen}
                  onToggle={() => toggleGroup(group.label)}
                  collapsed={collapsed}
                  isItemActive={isItemActive}
                />
              </div>
            )
          })}
        </div>
      </nav>

      {/* User strip */}
      {session?.user && (
        <div className={cn(
          'border-t border-gray-200 p-3 flex-shrink-0 bg-gray-50',
          collapsed ? 'flex justify-center' : 'flex items-center gap-3'
        )}>
          <div
            className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-brand-600 to-brand-700 flex items-center justify-center shadow"
            title={session.user.name ?? undefined}
          >
            <span className="text-xs font-bold text-white">
              {session.user.name
                ?.split(' ')
                .map((n) => n[0])
                .join('')
                .slice(0, 2)
                .toUpperCase() ?? '?'}
            </span>
          </div>
          {!collapsed && (
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-gray-800 truncate leading-tight">
                {session.user.name}
              </p>
              <p className="text-[10px] text-gray-400 capitalize truncate leading-tight mt-0.5">
                {(session.user.role ?? 'viewer').replace(/_/g, ' ')}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Collapse toggle */}
      <button
        onClick={() => setCollapsed((v) => !v)}
        className={cn(
          'hidden lg:flex items-center justify-center',
          'w-full py-2.5 border-t border-gray-200',
          'bg-gray-50 text-gray-500 hover:text-gray-700 hover:bg-gray-100',
          'transition-colors duration-150 text-xs gap-1.5'
        )}
        aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      >
        {collapsed ? (
          <ChevronRight className="w-4 h-4" />
        ) : (
          <>
            <ChevronLeft className="w-4 h-4" />
            <span>Collapse</span>
          </>
        )}
      </button>
    </div>
  )

  return (
    <>
      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm lg:hidden"
          onClick={() => setMobileOpen(false)}
          aria-hidden
        />
      )}

      {/* Mobile toggle button */}
      <button
        className="fixed top-4 left-4 z-50 lg:hidden flex items-center justify-center w-9 h-9 rounded-lg bg-brand-700 border border-brand-600 text-white hover:bg-brand-600 shadow-lg"
        onClick={() => setMobileOpen((v) => !v)}
        aria-label="Toggle navigation"
      >
        {mobileOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
      </button>

      {/* Mobile drawer */}
      <div
        className={cn(
          'fixed inset-y-0 left-0 z-50 lg:hidden transition-transform duration-300',
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <div className="h-full w-64">{sidebarContent}</div>
      </div>

      {/* Desktop sidebar */}
      <div className="hidden lg:flex h-full flex-shrink-0">
        {sidebarContent}
      </div>
    </>
  )
}
