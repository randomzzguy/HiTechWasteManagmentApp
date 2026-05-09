import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
import { format, formatDistanceToNow, parseISO, isValid } from 'date-fns'

// ---------------------------------------------------------------------------
// Tailwind class merger
// ---------------------------------------------------------------------------
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// ---------------------------------------------------------------------------
// Date helpers
// ---------------------------------------------------------------------------

/**
 * Format an ISO date string or Date object to a human-readable date.
 * @param date  ISO string, Date object, or undefined/null
 * @param fmt   date-fns format string (default: "dd MMM yyyy")
 */
export function formatDate(
  date: string | Date | null | undefined,
  fmt = 'dd MMM yyyy'
): string {
  if (!date) return '—'
  const d = typeof date === 'string' ? parseISO(date) : date
  if (!isValid(d)) return '—'
  return format(d, fmt)
}

/**
 * Format an ISO date string to "dd MMM yyyy, HH:mm".
 */
export function formatDateTime(date: string | Date | null | undefined): string {
  return formatDate(date, 'dd MMM yyyy, HH:mm')
}

/**
 * Return a relative time string, e.g. "3 hours ago".
 */
export function formatTimeAgo(date: string | Date | null | undefined): string {
  if (!date) return '—'
  const d = typeof date === 'string' ? parseISO(date) : date
  if (!isValid(d)) return '—'
  return formatDistanceToNow(d, { addSuffix: true })
}

/**
 * Format a month string "YYYY-MM" to "Jan 2025".
 */
export function formatMonth(month: string | null | undefined): string {
  if (!month) return '—'
  const d = parseISO(`${month}-01`)
  if (!isValid(d)) return month
  return format(d, 'MMM yyyy')
}

// ---------------------------------------------------------------------------
// Weight helpers
// ---------------------------------------------------------------------------

/**
 * Format weight in kilograms.
 * Values >= 1 000 kg are shown as tonnes to 2 d.p.
 * Values < 1 000 kg are shown as kg with no decimal.
 *
 * @example formatWeight(2500)  → "2.50 t"
 * @example formatWeight(850)   → "850 kg"
 */
export function formatWeight(kg: number | null | undefined): string {
  if (kg === null || kg === undefined || isNaN(Number(kg))) return '—'
  const n = Number(kg)
  if (n >= 1_000) {
    return `${(n / 1_000).toFixed(2)} t`
  }
  return `${n.toLocaleString('en-MY', { maximumFractionDigits: 0 })} kg`
}

/**
 * Format weight always as tonnes, to the given decimal places.
 */
export function formatWeightTonnes(
  kg: number | null | undefined,
  decimals = 2
): string {
  if (kg === null || kg === undefined || isNaN(Number(kg))) return '—'
  return `${(Number(kg) / 1_000).toFixed(decimals)} t`
}

// ---------------------------------------------------------------------------
// Currency helpers (Malaysian Ringgit)
// ---------------------------------------------------------------------------

/**
 * Format a numeric value as Malaysian Ringgit.
 * @example formatCurrency(12345.6)  → "RM 12,345.60"
 * @example formatCurrency(0)        → "RM 0.00"
 */
export function formatCurrency(
  myr: number | null | undefined,
  opts?: { compact?: boolean; decimals?: number }
): string {
  if (myr === null || myr === undefined || isNaN(Number(myr))) return '—'
  const n = Number(myr)
  const decimals = opts?.decimals ?? 2

  if (opts?.compact) {
    if (Math.abs(n) >= 1_000_000) {
      return `RM ${(n / 1_000_000).toFixed(1)}M`
    }
    if (Math.abs(n) >= 1_000) {
      return `RM ${(n / 1_000).toFixed(1)}K`
    }
  }

  return `RM ${n.toLocaleString('en-MY', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`
}

// ---------------------------------------------------------------------------
// Percentage helpers
// ---------------------------------------------------------------------------

/**
 * Format a number as a percentage string.
 * @example formatPercent(87.4)   → "87.4%"
 * @example formatPercent(0.874)  → "87.4%"   (when asDecimal = true)
 */
export function formatPercent(
  n: number | null | undefined,
  opts?: { decimals?: number; asDecimal?: boolean }
): string {
  if (n === null || n === undefined || isNaN(Number(n))) return '—'
  let val = Number(n)
  if (opts?.asDecimal) val = val * 100
  return `${val.toFixed(opts?.decimals ?? 1)}%`
}

// ---------------------------------------------------------------------------
// Number helpers
// ---------------------------------------------------------------------------

/**
 * Format a plain number with thousands separators.
 */
export function formatNumber(
  n: number | null | undefined,
  decimals = 0
): string {
  if (n === null || n === undefined || isNaN(Number(n))) return '—'
  return Number(n).toLocaleString('en-MY', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}

/**
 * Format carbon / CO₂e emissions.
 * Values >= 1 000 kg are shown as tonnes.
 */
export function formatCarbon(
  kg_co2e: number | null | undefined
): string {
  if (kg_co2e === null || kg_co2e === undefined || isNaN(Number(kg_co2e))) {
    return '—'
  }
  const n = Number(kg_co2e)
  if (Math.abs(n) >= 1_000) {
    return `${(n / 1_000).toFixed(2)} t CO₂e`
  }
  return `${n.toFixed(1)} kg CO₂e`
}

// ---------------------------------------------------------------------------
// Misc helpers
// ---------------------------------------------------------------------------

/**
 * Truncate a string to maxLen characters, appending "…" if truncated.
 */
export function truncate(str: string, maxLen: number): string {
  if (str.length <= maxLen) return str
  return `${str.slice(0, maxLen)}…`
}

/**
 * Convert a snake_case or SCREAMING_SNAKE_CASE string to Title Case.
 * @example snakeToTitle("in_progress")  → "In Progress"
 */
export function snakeToTitle(str: string): string {
  return str
    .toLowerCase()
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

/**
 * Build initials from a full name (up to 2 chars).
 * @example getInitials("Ahmad bin Razak")  → "AR"
 */
export function getInitials(name: string | null | undefined): string {
  if (!name) return '?'
  const parts = name.trim().split(/\s+/)
  if (parts.length === 1) return parts[0][0]?.toUpperCase() ?? '?'
  return (
    (parts[0][0] ?? '') + (parts[parts.length - 1][0] ?? '')
  ).toUpperCase()
}

/**
 * Generate a deterministic Tailwind background-color class for avatars
 * based on a string seed (e.g. user name).
 */
const AVATAR_COLORS = [
  'bg-red-500',
  'bg-orange-500',
  'bg-amber-500',
  'bg-yellow-500',
  'bg-lime-500',
  'bg-green-600',
  'bg-emerald-600',
  'bg-brand-500',
  'bg-cyan-500',
  'bg-sky-500',
  'bg-brand-600',
  'bg-indigo-500',
  'bg-violet-600',
  'bg-purple-600',
  'bg-fuchsia-500',
  'bg-pink-500',
] as const

export function avatarColor(seed: string): string {
  let hash = 0
  for (let i = 0; i < seed.length; i++) {
    hash = seed.charCodeAt(i) + ((hash << 5) - hash)
  }
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length]
}

/**
 * Clamp a number between min and max.
 */
export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

/**
 * Sleep for ms milliseconds (useful in async retry logic).
 */
export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
