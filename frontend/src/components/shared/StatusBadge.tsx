import { cn } from '@/lib/utils'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type BadgeStatus =
  | 'draft'
  | 'confirmed'
  | 'dispatched'
  | 'in_progress'
  | 'completed'
  | 'invoiced'
  | 'cancelled'
  | 'critical'
  | 'warning'
  | 'info'
  | 'success'
  | 'active'
  | 'inactive'
  | 'suspended'
  | 'prospect'
  | 'available'
  | 'on_trip'
  | 'maintenance'
  | 'breakdown'
  | 'retired'
  | 'in_storage'
  | 'pending_disposal'
  | 'consigned'
  | 'disposed'
  | 'overdue'
  | 'rejected'
  | 'standard'
  | 'premium'
  | 'enterprise'
  | 'scheduled'
  | 'low'
  | 'normal'
  | 'high'
  | 'urgent'
  | 'pending'
  | 'paid'
  | 'unpaid'
  | 'partial'
  | 'open'
  | 'closed'
  | string

export type BadgeSize = 'xs' | 'sm' | 'md'

export type BadgeVariant = 'filled' | 'outline' | 'subtle'

// ---------------------------------------------------------------------------
// Status → visual config mapping
// ---------------------------------------------------------------------------

interface StatusConfig {
  label: string
  className: string
  dot?: string
}

const STATUS_MAP: Record<string, StatusConfig> = {
  // ── Job statuses ──────────────────────────────────────────────────────────
  draft:       { label: 'Draft',       className: 'bg-gray-100 text-gray-600 border-gray-300',       dot: 'bg-gray-400' },
  confirmed:   { label: 'Confirmed',   className: 'bg-brand-50 text-brand-600 border-brand-200',         dot: 'bg-brand-400' },
  dispatched:  { label: 'Dispatched',  className: 'bg-violet-50 text-violet-600 border-violet-200',   dot: 'bg-violet-400' },
  in_progress: { label: 'In Progress', className: 'bg-amber-50 text-amber-600 border-amber-200',      dot: 'bg-amber-400' },
  completed:   { label: 'Completed',   className: 'bg-green-50 text-green-600 border-green-200',      dot: 'bg-green-400' },
  invoiced:    { label: 'Invoiced',    className: 'bg-purple-50 text-purple-600 border-purple-200',   dot: 'bg-purple-400' },
  cancelled:   { label: 'Cancelled',   className: 'bg-red-50 text-red-500 border-red-200 line-through', dot: 'bg-red-400' },

  // ── Alert / severity ──────────────────────────────────────────────────────
  critical: { label: 'Critical', className: 'bg-red-50 text-red-600 border-red-200',     dot: 'bg-red-400' },
  warning:  { label: 'Warning',  className: 'bg-amber-50 text-amber-600 border-amber-200', dot: 'bg-amber-400' },
  info:     { label: 'Info',     className: 'bg-brand-50 text-brand-600 border-brand-200',   dot: 'bg-brand-400' },
  success:  { label: 'Success',  className: 'bg-green-50 text-green-600 border-green-200', dot: 'bg-green-400' },

  // ── Client statuses ───────────────────────────────────────────────────────
  active:    { label: 'Active',    className: 'bg-green-50 text-green-600 border-green-200', dot: 'bg-green-400' },
  inactive:  { label: 'Inactive',  className: 'bg-gray-100 text-gray-500 border-gray-300',  dot: 'bg-gray-400' },
  suspended: { label: 'Suspended', className: 'bg-red-50 text-red-500 border-red-200',      dot: 'bg-red-400' },
  prospect:  { label: 'Prospect',  className: 'bg-cyan-50 text-cyan-600 border-cyan-200',   dot: 'bg-cyan-400' },

  // ── Client tiers ──────────────────────────────────────────────────────────
  standard:   { label: 'Standard',   className: 'bg-gray-100 text-gray-600 border-gray-300',       dot: 'bg-gray-400' },
  premium:    { label: 'Premium',    className: 'bg-amber-50 text-amber-600 border-amber-200',      dot: 'bg-amber-400' },
  enterprise: { label: 'Enterprise', className: 'bg-purple-50 text-purple-600 border-purple-200',   dot: 'bg-purple-400' },

  // ── Vehicle statuses ──────────────────────────────────────────────────────
  available:   { label: 'Available',   className: 'bg-green-50 text-green-600 border-green-200', dot: 'bg-green-400' },
  on_trip:     { label: 'On Trip',     className: 'bg-brand-50 text-brand-600 border-brand-200',    dot: 'bg-brand-400' },
  maintenance: { label: 'Maintenance', className: 'bg-amber-50 text-amber-600 border-amber-200', dot: 'bg-amber-400' },
  breakdown:   { label: 'Breakdown',   className: 'bg-red-50 text-red-600 border-red-200',       dot: 'bg-red-400' },
  retired:     { label: 'Retired',     className: 'bg-gray-100 text-gray-400 border-gray-200',   dot: 'bg-gray-400' },

  // ── SW Batch statuses ─────────────────────────────────────────────────────
  in_storage:      { label: 'In Storage',      className: 'bg-brand-50 text-brand-600 border-brand-200',     dot: 'bg-brand-400' },
  pending_disposal:{ label: 'Pending Disposal', className: 'bg-amber-50 text-amber-600 border-amber-200',  dot: 'bg-amber-400' },
  consigned:       { label: 'Consigned',        className: 'bg-violet-50 text-violet-600 border-violet-200', dot: 'bg-violet-400' },
  disposed:        { label: 'Disposed',         className: 'bg-green-50 text-green-600 border-green-200',  dot: 'bg-green-400' },
  overdue:         { label: 'Overdue',          className: 'bg-red-50 text-red-600 border-red-200',        dot: 'bg-red-400' },
  rejected:        { label: 'Rejected',         className: 'bg-red-50 text-red-500 border-red-200',        dot: 'bg-red-400' },

  // ── Priority ──────────────────────────────────────────────────────────────
  low:    { label: 'Low',    className: 'bg-gray-100 text-gray-500 border-gray-300',  dot: 'bg-gray-400' },
  normal: { label: 'Normal', className: 'bg-brand-50 text-brand-500 border-brand-200',   dot: 'bg-brand-400' },
  high:   { label: 'High',   className: 'bg-amber-50 text-amber-600 border-amber-200', dot: 'bg-amber-400' },
  urgent: { label: 'Urgent', className: 'bg-red-50 text-red-600 border-red-200',      dot: 'bg-red-400' },

  // ── Maintenance ───────────────────────────────────────────────────────────
  scheduled: { label: 'Scheduled', className: 'bg-brand-50 text-brand-600 border-brand-200', dot: 'bg-brand-400' },

  // ── Finance / invoice ─────────────────────────────────────────────────────
  pending: { label: 'Pending', className: 'bg-amber-50 text-amber-600 border-amber-200',    dot: 'bg-amber-400' },
  paid:    { label: 'Paid',    className: 'bg-green-50 text-green-600 border-green-200',    dot: 'bg-green-400' },
  unpaid:  { label: 'Unpaid',  className: 'bg-red-50 text-red-600 border-red-200',          dot: 'bg-red-400' },
  partial: { label: 'Partial', className: 'bg-orange-50 text-orange-600 border-orange-200', dot: 'bg-orange-400' },
  open:    { label: 'Open',    className: 'bg-brand-50 text-brand-600 border-brand-200',       dot: 'bg-brand-400' },
  closed:  { label: 'Closed',  className: 'bg-gray-100 text-gray-500 border-gray-300',      dot: 'bg-gray-400' },
}

// ---------------------------------------------------------------------------
// Fallback config for unknown statuses
// ---------------------------------------------------------------------------

function getStatusConfig(status: string): StatusConfig {
  const normalised = status.toLowerCase().replace(/[\s-]/g, '_')
  if (STATUS_MAP[normalised]) return STATUS_MAP[normalised]

  // Auto-generate a label from the raw string
  return {
    label: status
      .replace(/_/g, ' ')
      .replace(/-/g, ' ')
      .replace(/\b\w/g, (c) => c.toUpperCase()),
    className: 'bg-gray-100 text-gray-600 border-gray-300',
    dot: 'bg-gray-400',
  }
}

// ---------------------------------------------------------------------------
// Size config
// ---------------------------------------------------------------------------

const SIZE_CLASSES: Record<BadgeSize, string> = {
  xs: 'px-1.5 py-0.5 text-[10px] gap-1',
  sm: 'px-2 py-0.5 text-xs gap-1',
  md: 'px-2.5 py-1 text-sm gap-1.5',
}

const DOT_SIZE_CLASSES: Record<BadgeSize, string> = {
  xs: 'w-1.5 h-1.5',
  sm: 'w-1.5 h-1.5',
  md: 'w-2 h-2',
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface StatusBadgeProps {
  status: BadgeStatus
  /** Override the displayed label */
  label?: string
  size?: BadgeSize
  /** Show a coloured dot before the label */
  dot?: boolean
  /** Use outline style instead of filled */
  variant?: BadgeVariant
  className?: string
  /** Make the badge a pill (fully rounded) */
  pill?: boolean
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function StatusBadge({
  status,
  label,
  size = 'sm',
  dot = false,
  variant = 'filled',
  className,
  pill = true,
}: StatusBadgeProps) {
  const config = getStatusConfig(String(status))
  const displayLabel = label ?? config.label
  const sizeClass = SIZE_CLASSES[size]
  const dotSizeClass = DOT_SIZE_CLASSES[size]

  let variantClass = config.className

  if (variant === 'outline') {
    // Keep text colour, remove background, keep border
    variantClass = config.className
      .split(' ')
      .filter((c) => !c.startsWith('bg-'))
      .join(' ')
      .concat(' bg-transparent')
  } else if (variant === 'subtle') {
    // Slightly dimmer background
    variantClass = config.className
      .split(' ')
      .map((c) => {
        if (c.startsWith('bg-') && c.includes('/')) {
          // Reduce opacity
          return c.replace(/\/\d+/, '/20')
        }
        return c
      })
      .join(' ')
  }

  return (
    <span
      className={cn(
        'inline-flex items-center font-semibold border leading-none',
        pill ? 'rounded-full' : 'rounded',
        sizeClass,
        variantClass,
        className
      )}
    >
      {dot && config.dot && (
        <span
          className={cn('rounded-full flex-shrink-0', dotSizeClass, config.dot)}
          aria-hidden
        />
      )}
      {displayLabel}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Named exports for convenience
// ---------------------------------------------------------------------------

/** Pre-configured with dot=true */
export function StatusDot({
  status,
  label,
  size = 'sm',
  className,
}: Omit<StatusBadgeProps, 'dot'>) {
  return (
    <StatusBadge
      status={status}
      label={label}
      size={size}
      dot
      className={className}
    />
  )
}

/** Just the coloured dot (no text) */
export function OnlyDot({
  status,
  size = 'sm',
  className,
}: {
  status: BadgeStatus
  size?: BadgeSize
  className?: string
}) {
  const config = getStatusConfig(String(status))
  const dotSizeClass = DOT_SIZE_CLASSES[size]

  return (
    <span
      className={cn(
        'inline-block rounded-full flex-shrink-0',
        dotSizeClass,
        config.dot ?? 'bg-slate-400',
        className
      )}
      aria-hidden
    />
  )
}
