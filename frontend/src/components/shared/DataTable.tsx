'use client'

import { useState, useMemo, useCallback } from 'react'
import {
  ChevronUp,
  ChevronDown,
  ChevronsUpDown,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  Search,
  X,
  Loader2,
  Inbox,
} from 'lucide-react'
import { cn } from '@/lib/utils'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type SortDirection = 'asc' | 'desc' | null

export interface ColumnDef<T> {
  /** Unique column key */
  key: string
  /** Header label */
  header: string
  /** Render the cell content. Receives the row data and the raw value. */
  cell?: (row: T, value: unknown) => React.ReactNode
  /** Key on the row object to read the raw value from (defaults to `key`) */
  accessor?: keyof T | ((row: T) => unknown)
  /** Whether this column is sortable (client-side) */
  sortable?: boolean
  /** Extra className for the <th> */
  headerClassName?: string
  /** Extra className for each <td> in this column */
  cellClassName?: string
  /** Fixed width (e.g. "120px" or "10%") */
  width?: string
  /** Minimum width */
  minWidth?: string
  /** Align cell content */
  align?: 'left' | 'center' | 'right'
  /** Hide on small screens */
  hideOnMobile?: boolean
}

export interface DataTableProps<T> {
  /** Column definitions */
  columns: ColumnDef<T>[]
  /** Row data */
  data: T[]
  /** Key extractor for React reconciliation */
  rowKey: keyof T | ((row: T) => string | number)
  /** Called when a row is clicked */
  onRowClick?: (row: T) => void
  /** Show a search/filter box above the table */
  searchable?: boolean
  /** Placeholder text for the search input */
  searchPlaceholder?: string
  /** Keys to search across (defaults to all string/number values) */
  searchKeys?: (keyof T)[]
  /** External search value (controlled) */
  searchValue?: string
  /** Called when the internal search value changes */
  onSearchChange?: (value: string) => void
  /** Enable pagination */
  pagination?: boolean
  /** Rows per page options */
  pageSizeOptions?: number[]
  /** Default page size */
  defaultPageSize?: number
  /** Total row count (for server-side pagination) */
  totalCount?: number
  /** Current page (controlled, for server-side pagination) */
  page?: number
  /** Called when page changes (server-side pagination) */
  onPageChange?: (page: number) => void
  /** Called when page size changes */
  onPageSizeChange?: (size: number) => void
  /** Show a loading overlay */
  loading?: boolean
  /** Empty state message */
  emptyMessage?: string
  /** Empty state sub-message */
  emptySubMessage?: string
  /** Custom empty state node */
  emptyState?: React.ReactNode
  /** Extra content rendered in the toolbar (right side) */
  toolbarRight?: React.ReactNode
  /** Extra content rendered in the toolbar (left side, after search) */
  toolbarLeft?: React.ReactNode
  /** Table caption (accessibility) */
  caption?: string
  /** Extra className on the root wrapper */
  className?: string
  /** Extra className on the table element */
  tableClassName?: string
  /** Whether rows are clickable (adds cursor-pointer + hover) */
  clickable?: boolean
  /** Highlight rows matching this predicate */
  highlightRow?: (row: T) => boolean
  /** Default sort column key */
  defaultSortKey?: string
  /** Default sort direction */
  defaultSortDir?: SortDirection
  /** Whether sorting is handled server-side */
  serverSideSort?: boolean
  /** Called when sort changes (server-side) */
  onSortChange?: (key: string, dir: SortDirection) => void
  /** Whether pagination is server-side */
  serverSidePagination?: boolean
  /** Compact row styling */
  compact?: boolean
  /** Show row count summary in footer */
  showRowCount?: boolean
  /** Extra classes for each <tr> */
  rowClassName?: (row: T) => string
  /** Sticky header */
  stickyHeader?: boolean
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getRowKey<T>(
  row: T,
  rowKey: DataTableProps<T>['rowKey']
): string | number {
  if (typeof rowKey === 'function') return rowKey(row)
  return row[rowKey] as string | number
}

function getCellValue<T>(row: T, col: ColumnDef<T>): unknown {
  if (col.accessor) {
    if (typeof col.accessor === 'function') return col.accessor(row)
    return row[col.accessor]
  }
  return (row as Record<string, unknown>)[col.key]
}

function matchesSearch<T>(row: T, query: string, keys?: (keyof T)[]): boolean {
  const q = query.toLowerCase()
  const entries = keys
    ? keys.map((k) => row[k])
    : Object.values(row as Record<string, unknown>)

  return entries.some((val) => {
    if (val === null || val === undefined) return false
    if (typeof val === 'object') return false
    return String(val).toLowerCase().includes(q)
  })
}

function sortRows<T>(
  rows: T[],
  key: string,
  dir: SortDirection,
  columns: ColumnDef<T>[]
): T[] {
  if (!dir || !key) return rows
  const col = columns.find((c) => c.key === key)
  if (!col) return rows

  return [...rows].sort((a, b) => {
    const av = getCellValue(a, col)
    const bv = getCellValue(b, col)

    if (av === null || av === undefined) return 1
    if (bv === null || bv === undefined) return -1

    let cmp = 0
    if (typeof av === 'number' && typeof bv === 'number') {
      cmp = av - bv
    } else {
      cmp = String(av).localeCompare(String(bv), undefined, { numeric: true })
    }

    return dir === 'asc' ? cmp : -cmp
  })
}

// ---------------------------------------------------------------------------
// Sort icon
// ---------------------------------------------------------------------------

function SortIcon({ dir }: { dir: SortDirection }) {
  if (dir === 'asc') return <ChevronUp className="w-3.5 h-3.5 text-green-400" />
  if (dir === 'desc') return <ChevronDown className="w-3.5 h-3.5 text-green-400" />
  return <ChevronsUpDown className="w-3.5 h-3.5 text-gray-600 group-hover:text-gray-600" />
}

// ---------------------------------------------------------------------------
// Pagination controls
// ---------------------------------------------------------------------------

interface PaginationProps {
  page: number
  pageSize: number
  totalCount: number
  pageSizeOptions: number[]
  onPageChange: (p: number) => void
  onPageSizeChange: (s: number) => void
  showRowCount: boolean
}

function Pagination({
  page,
  pageSize,
  totalCount,
  pageSizeOptions,
  onPageChange,
  onPageSizeChange,
  showRowCount,
}: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize))
  const start = Math.min(totalCount, (page - 1) * pageSize + 1)
  const end = Math.min(totalCount, page * pageSize)

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 border-t border-gray-100 bg-gray-50/60">
      {/* Row count info */}
      {showRowCount && (
        <p className="text-xs text-gray-500 tabular-nums">
          {totalCount === 0 ? (
            'No results'
          ) : (
            <>
              Showing{' '}
              <span className="font-medium text-gray-700">{start}</span>–
              <span className="font-medium text-gray-700">{end}</span> of{' '}
              <span className="font-medium text-gray-700">
                {totalCount.toLocaleString()}
              </span>{' '}
              result{totalCount !== 1 ? 's' : ''}
            </>
          )}
        </p>
      )}

      <div className="flex items-center gap-3 ml-auto">
        {/* Page size selector */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">Rows per page:</span>
          <select
            value={pageSize}
            onChange={(e) => {
              onPageSizeChange(Number(e.target.value))
              onPageChange(1)
            }}
            className="text-xs bg-white border border-gray-300 text-gray-700 rounded-md px-2 py-1 focus:outline-none focus:border-brand-600 focus:ring-1 focus:ring-brand-600/30"
          >
            {pageSizeOptions.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>

        {/* Page navigation */}
        <div className="flex items-center gap-1">
          <button
            onClick={() => onPageChange(1)}
            disabled={page <= 1}
            className="flex items-center justify-center w-7 h-7 rounded-md text-gray-500 hover:text-gray-900 hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            aria-label="First page"
          >
            <ChevronsLeft className="w-4 h-4" />
          </button>
          <button
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1}
            className="flex items-center justify-center w-7 h-7 rounded-md text-gray-500 hover:text-gray-900 hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            aria-label="Previous page"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>

          <span className="px-2 text-xs text-gray-500 tabular-nums">
            <span className="font-semibold text-gray-900">{page}</span>
            {' / '}
            <span>{totalPages}</span>
          </span>

          <button
            onClick={() => onPageChange(page + 1)}
            disabled={page >= totalPages}
            className="flex items-center justify-center w-7 h-7 rounded-md text-gray-500 hover:text-gray-900 hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            aria-label="Next page"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
          <button
            onClick={() => onPageChange(totalPages)}
            disabled={page >= totalPages}
            className="flex items-center justify-center w-7 h-7 rounded-md text-gray-500 hover:text-gray-900 hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            aria-label="Last page"
          >
            <ChevronsRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main DataTable component
// ---------------------------------------------------------------------------

export default function DataTable<T>({
  columns,
  data,
  rowKey,
  onRowClick,
  searchable = false,
  searchPlaceholder = 'Search…',
  searchKeys,
  searchValue: externalSearch,
  onSearchChange,
  pagination = true,
  pageSizeOptions = [10, 25, 50, 100],
  defaultPageSize = 25,
  totalCount: externalTotal,
  page: externalPage,
  onPageChange: externalPageChange,
  onPageSizeChange: externalPageSizeChange,
  loading = false,
  emptyMessage = 'No results found',
  emptySubMessage = 'Try adjusting your search or filters.',
  emptyState,
  toolbarRight,
  toolbarLeft,
  caption,
  className,
  tableClassName,
  clickable,
  highlightRow,
  defaultSortKey,
  defaultSortDir = null,
  serverSideSort = false,
  onSortChange,
  serverSidePagination = false,
  compact = false,
  showRowCount = true,
  rowClassName,
  stickyHeader = false,
}: DataTableProps<T>) {
  // ── Internal state ──────────────────────────────────────────────────────
  const [internalSearch, setInternalSearch] = useState('')
  const [internalPage, setInternalPage] = useState(1)
  const [internalPageSize, setInternalPageSize] = useState(defaultPageSize)
  const [sortKey, setSortKey] = useState<string>(defaultSortKey ?? '')
  const [sortDir, setSortDir] = useState<SortDirection>(defaultSortDir)

  // Use external or internal controlled values
  const searchQuery =
    externalSearch !== undefined ? externalSearch : internalSearch
  const currentPage =
    externalPage !== undefined ? externalPage : internalPage
  const pageSize = internalPageSize

  // ── Handlers ────────────────────────────────────────────────────────────

  const handleSearchChange = useCallback(
    (val: string) => {
      if (onSearchChange) {
        onSearchChange(val)
      } else {
        setInternalSearch(val)
      }
      // Reset to page 1 on search
      if (!serverSidePagination) setInternalPage(1)
    },
    [onSearchChange, serverSidePagination]
  )

  const handlePageChange = useCallback(
    (p: number) => {
      if (externalPageChange) {
        externalPageChange(p)
      } else {
        setInternalPage(p)
      }
    },
    [externalPageChange]
  )

  const handlePageSizeChange = useCallback(
    (s: number) => {
      setInternalPageSize(s)
      if (externalPageSizeChange) externalPageSizeChange(s)
      handlePageChange(1)
    },
    [externalPageSizeChange, handlePageChange]
  )

  const handleSort = useCallback(
    (key: string) => {
      let nextDir: SortDirection
      if (sortKey !== key) {
        nextDir = 'asc'
      } else if (sortDir === 'asc') {
        nextDir = 'desc'
      } else if (sortDir === 'desc') {
        nextDir = null
      } else {
        nextDir = 'asc'
      }

      setSortKey(nextDir ? key : '')
      setSortDir(nextDir)

      if (serverSideSort && onSortChange) {
        onSortChange(key, nextDir)
      }
    },
    [sortKey, sortDir, serverSideSort, onSortChange]
  )

  // ── Derived / processed data ────────────────────────────────────────────

  const filtered = useMemo(() => {
    if (serverSidePagination || !searchQuery.trim()) return data
    return data.filter((row) => matchesSearch(row, searchQuery, searchKeys))
  }, [data, searchQuery, searchKeys, serverSidePagination])

  const sorted = useMemo(() => {
    if (serverSideSort || !sortKey || !sortDir) return filtered
    return sortRows(filtered, sortKey, sortDir, columns)
  }, [filtered, sortKey, sortDir, serverSideSort, columns])

  const totalCount = externalTotal ?? sorted.length

  const paginated = useMemo(() => {
    if (!pagination || serverSidePagination) return sorted
    const start = (currentPage - 1) * pageSize
    return sorted.slice(start, start + pageSize)
  }, [sorted, pagination, serverSidePagination, currentPage, pageSize])

  const isClickable = clickable ?? !!onRowClick

  // ── Render ──────────────────────────────────────────────────────────────

  const hasToolbar = searchable || toolbarRight || toolbarLeft

  return (
    <div
      className={cn(
        'flex flex-col bg-white border border-gray-200 rounded-2xl overflow-hidden shadow-sm',
        className
      )}
    >
      {/* ---------------------------------------------------------------- */}
      {/* Toolbar                                                            */}
      {/* ---------------------------------------------------------------- */}
      {hasToolbar && (
        <div className="flex flex-wrap items-center gap-3 px-4 py-3 border-b border-gray-100 bg-gray-50/60">
          {/* Search box */}
          {searchable && (
            <div className="relative flex-1 min-w-[180px] max-w-xs">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-600 pointer-events-none" />
              <input
                type="search"
                value={searchQuery}
                onChange={(e) => handleSearchChange(e.target.value)}
                placeholder={searchPlaceholder}
                className="w-full pl-8 pr-8 py-1.5 text-sm bg-white border border-gray-300 text-gray-900 placeholder-gray-400 rounded-lg focus:outline-none focus:border-brand-600 focus:ring-1 focus:ring-brand-600/30 transition-colors"
              />
              {searchQuery && (
                <button
                  onClick={() => handleSearchChange('')}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-700 transition-colors"
                  aria-label="Clear search"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          )}

          {/* Left toolbar slot */}
          {toolbarLeft}

          {/* Spacer */}
          <div className="flex-1" />

          {/* Right toolbar slot */}
          {toolbarRight}
        </div>
      )}

      {/* ---------------------------------------------------------------- */}
      {/* Table wrapper                                                       */}
      {/* ---------------------------------------------------------------- */}
      <div className="relative overflow-x-auto flex-1">
        {/* Loading overlay */}
        {loading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-white/70 backdrop-blur-sm">
            <div className="flex items-center gap-2.5 bg-white border border-gray-200 rounded-xl px-4 py-2.5 shadow-xl">
              <Loader2 className="w-4 h-4 text-brand-600 animate-spin" />
              <span className="text-sm text-gray-700 font-medium">Loading…</span>
            </div>
          </div>
        )}

        <table
          className={cn('w-full text-sm text-left', tableClassName)}
          aria-busy={loading}
        >
          {caption && (
            <caption className="sr-only">{caption}</caption>
          )}

          {/* ── Header ─────────────────────────────────────────────────── */}
          <thead
            className={cn(
              'bg-gray-50/80 border-b border-gray-200',
              stickyHeader && 'sticky top-0 z-10'
            )}
          >
            <tr>
              {columns.map((col) => {
                const isSorted = sortKey === col.key
                const alignClass =
                  col.align === 'center'
                    ? 'text-center'
                    : col.align === 'right'
                    ? 'text-right'
                    : 'text-left'

                return (
                  <th
                    key={col.key}
                    scope="col"
                    style={{
                      width: col.width,
                      minWidth: col.minWidth,
                    }}
                    className={cn(
                      'px-4 py-3 text-xs font-semibold text-gray-600 whitespace-nowrap',
                      alignClass,
                      col.sortable &&
                        'cursor-pointer select-none group hover:text-gray-900 transition-colors',
                      col.hideOnMobile && 'hidden md:table-cell',
                      col.headerClassName
                    )}
                    onClick={col.sortable ? () => handleSort(col.key) : undefined}
                    aria-sort={
                      col.sortable
                        ? isSorted
                          ? sortDir === 'asc'
                            ? 'ascending'
                            : 'descending'
                          : 'none'
                        : undefined
                    }
                  >
                    <span className="inline-flex items-center gap-1">
                      {col.header}
                      {col.sortable && <SortIcon dir={isSorted ? sortDir : null} />}
                    </span>
                  </th>
                )
              })}
            </tr>
          </thead>

          {/* ── Body ───────────────────────────────────────────────────── */}
          <tbody>
            {paginated.length === 0 && !loading ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-16 text-center">
                  {emptyState ?? (
                    <div className="flex flex-col items-center gap-3">
                      <div className="flex items-center justify-center w-12 h-12 rounded-full bg-gray-100">
                        <Inbox className="w-5 h-5 text-gray-400" />
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-gray-500">
                          {emptyMessage}
                        </p>
                        {emptySubMessage && (
                          <p className="text-xs text-gray-400 mt-1">
                            {emptySubMessage}
                          </p>
                        )}
                      </div>
                    </div>
                  )}
                </td>
              </tr>
            ) : (
              paginated.map((row) => {
                const key = getRowKey(row, rowKey)
                const isHighlighted = highlightRow?.(row) ?? false
                const extraRowClass = rowClassName?.(row) ?? ''

                return (
                  <tr
                    key={key}
                    onClick={onRowClick ? () => onRowClick(row) : undefined}
                    className={cn(
                      'border-b border-gray-100 transition-colors duration-100',
                      compact ? 'text-xs' : 'text-sm',
                      isClickable &&
                        'cursor-pointer hover:bg-gray-50 active:bg-gray-100',
                      isHighlighted && 'bg-amber-50 hover:bg-amber-50',
                      extraRowClass
                    )}
                  >
                    {columns.map((col) => {
                      const value = getCellValue(row, col)
                      const alignClass =
                        col.align === 'center'
                          ? 'text-center'
                          : col.align === 'right'
                          ? 'text-right'
                          : 'text-left'

                      return (
                        <td
                          key={col.key}
                          style={{
                            width: col.width,
                            minWidth: col.minWidth,
                          }}
                          className={cn(
                            compact ? 'px-4 py-2' : 'px-4 py-3',
                            'text-gray-700',
                            alignClass,
                            col.hideOnMobile && 'hidden md:table-cell',
                            col.cellClassName
                          )}
                        >
                          {col.cell
                            ? col.cell(row, value)
                            : value === null || value === undefined
                            ? <span className="text-gray-600">—</span>
                            : String(value)}
                        </td>
                      )
                    })}
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>

      {/* ---------------------------------------------------------------- */}
      {/* Pagination                                                          */}
      {/* ---------------------------------------------------------------- */}
      {pagination && (
        <Pagination
          page={currentPage}
          pageSize={pageSize}
          totalCount={totalCount}
          pageSizeOptions={pageSizeOptions}
          onPageChange={handlePageChange}
          onPageSizeChange={handlePageSizeChange}
          showRowCount={showRowCount}
        />
      )}
    </div>
  )
}

