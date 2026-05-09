'use client'

import { useEffect, useRef } from 'react'
import { AlertTriangle, Trash2, X, Loader2, CheckCircle, Info } from 'lucide-react'
import { cn } from '@/lib/utils'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ConfirmDialogVariant = 'default' | 'destructive' | 'warning' | 'info'

export interface ConfirmDialogProps {
  /** Whether the dialog is open */
  open: boolean
  /** Dialog title */
  title: string
  /** Dialog description / body text */
  description?: string
  /** Custom body content (replaces description if provided) */
  children?: React.ReactNode
  /** Label for the confirm button (default: "Confirm") */
  confirmLabel?: string
  /** Label for the cancel button (default: "Cancel") */
  cancelLabel?: string
  /** Called when the user confirms */
  onConfirm: () => void | Promise<void>
  /** Called when the user cancels or closes the dialog */
  onCancel: () => void
  /** Visual variant — affects icon and button colour */
  variant?: ConfirmDialogVariant
  /** Show a loading spinner on the confirm button */
  loading?: boolean
  /** Disable the confirm button */
  confirmDisabled?: boolean
  /** Whether clicking the backdrop closes the dialog (default: true) */
  closeOnBackdrop?: boolean
  /** Whether pressing Escape closes the dialog (default: true) */
  closeOnEscape?: boolean
  /** Additional className for the dialog panel */
  className?: string
}

// ---------------------------------------------------------------------------
// Variant config
// ---------------------------------------------------------------------------

interface VariantConfig {
  icon: React.ElementType
  iconWrapperClass: string
  iconClass: string
  confirmButtonClass: string
  confirmButtonHoverClass: string
}

const VARIANT_CONFIG: Record<ConfirmDialogVariant, VariantConfig> = {
  default: {
    icon: CheckCircle,
    iconWrapperClass: 'bg-green-50 border border-green-200',
    iconClass: 'text-green-500',
    confirmButtonClass: 'bg-green-600 hover:bg-green-500 focus-visible:ring-green-500',
    confirmButtonHoverClass: 'hover:bg-green-500',
  },
  destructive: {
    icon: Trash2,
    iconWrapperClass: 'bg-red-50 border border-red-200',
    iconClass: 'text-red-500',
    confirmButtonClass: 'bg-red-600 hover:bg-red-500 focus-visible:ring-red-500',
    confirmButtonHoverClass: 'hover:bg-red-500',
  },
  warning: {
    icon: AlertTriangle,
    iconWrapperClass: 'bg-amber-50 border border-amber-200',
    iconClass: 'text-amber-500',
    confirmButtonClass: 'bg-amber-600 hover:bg-amber-500 focus-visible:ring-amber-500',
    confirmButtonHoverClass: 'hover:bg-amber-500',
  },
  info: {
    icon: Info,
    iconWrapperClass: 'bg-brand-50 border border-brand-200',
    iconClass: 'text-brand-500',
    confirmButtonClass: 'bg-brand-600 hover:bg-brand-500 focus-visible:ring-brand-500',
    confirmButtonHoverClass: 'hover:bg-brand-500',
  },
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ConfirmDialog({
  open,
  title,
  description,
  children,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  onConfirm,
  onCancel,
  variant = 'default',
  loading = false,
  confirmDisabled = false,
  closeOnBackdrop = true,
  closeOnEscape = true,
  className,
}: ConfirmDialogProps) {
  const config = VARIANT_CONFIG[variant]
  const Icon = config.icon

  const cancelButtonRef = useRef<HTMLButtonElement>(null)
  const confirmButtonRef = useRef<HTMLButtonElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)

  // ── Focus management ─────────────────────────────────────────────────────

  useEffect(() => {
    if (open) {
      // Focus the cancel button by default (safer default for destructive actions)
      setTimeout(() => {
        cancelButtonRef.current?.focus()
      }, 50)
    }
  }, [open])

  // ── Keyboard handling ────────────────────────────────────────────────────

  useEffect(() => {
    if (!open) return

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape' && closeOnEscape) {
        e.preventDefault()
        onCancel()
        return
      }

      // Trap focus within the dialog
      if (e.key === 'Tab' && panelRef.current) {
        const focusable = panelRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        )
        const first = focusable[0]
        const last = focusable[focusable.length - 1]

        if (e.shiftKey) {
          if (document.activeElement === first) {
            e.preventDefault()
            last?.focus()
          }
        } else {
          if (document.activeElement === last) {
            e.preventDefault()
            first?.focus()
          }
        }
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [open, closeOnEscape, onCancel])

  // ── Prevent body scroll when open ───────────────────────────────────────

  useEffect(() => {
    if (open) {
      const previous = document.body.style.overflow
      document.body.style.overflow = 'hidden'
      return () => {
        document.body.style.overflow = previous
      }
    }
  }, [open])

  // ── Confirm handler ──────────────────────────────────────────────────────

  async function handleConfirm() {
    if (confirmDisabled || loading) return
    await onConfirm()
  }

  // ── Backdrop click ───────────────────────────────────────────────────────

  function handleBackdropClick(e: React.MouseEvent<HTMLDivElement>) {
    if (
      closeOnBackdrop &&
      e.target === e.currentTarget &&
      !loading
    ) {
      onCancel()
    }
  }

  // ── Don't render if closed ───────────────────────────────────────────────

  if (!open) return null

  return (
    // Backdrop
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
      aria-describedby={description || children ? 'confirm-dialog-description' : undefined}
      className={cn(
        'fixed inset-0 z-50 flex items-center justify-center p-4',
        'bg-black/40 backdrop-blur-sm',
        'animate-in'
      )}
      onClick={handleBackdropClick}
    >
      {/* Panel */}
      <div
        ref={panelRef}
        className={cn(
          'relative w-full max-w-md',
          'bg-white border border-gray-200',
          'rounded-2xl shadow-2xl shadow-black/20',
          'overflow-hidden',
          'animate-in',
          className
        )}
        // Prevent clicks inside from bubbling to backdrop
        onClick={(e) => e.stopPropagation()}
      >
        {/* Top accent line */}
        <div
          className={cn(
            'h-0.5 w-full',
            variant === 'destructive' && 'bg-gradient-to-r from-transparent via-red-500 to-transparent',
            variant === 'warning' && 'bg-gradient-to-r from-transparent via-amber-500 to-transparent',
            variant === 'info' && 'bg-gradient-to-r from-transparent via-brand-500 to-transparent',
            variant === 'default' && 'bg-gradient-to-r from-transparent via-green-500 to-transparent',
          )}
        />

        {/* Close button */}
        <button
          type="button"
          onClick={() => !loading && onCancel()}
          disabled={loading}
          className={cn(
            'absolute top-4 right-4 z-10',
            'flex items-center justify-center w-7 h-7 rounded-lg',
            'text-gray-400 hover:text-gray-700 hover:bg-gray-100',
            'transition-colors duration-150',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gray-300',
            'disabled:pointer-events-none disabled:opacity-50'
          )}
          aria-label="Close dialog"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Content */}
        <div className="px-6 pt-6 pb-5">
          {/* Icon + Title */}
          <div className="flex items-start gap-4">
            {/* Icon */}
            <div
              className={cn(
                'flex-shrink-0 flex items-center justify-center w-11 h-11 rounded-xl',
                config.iconWrapperClass
              )}
              aria-hidden
            >
              <Icon className={cn('w-5 h-5', config.iconClass)} />
            </div>

            {/* Title & description */}
            <div className="flex-1 min-w-0 pt-0.5 pr-6">
              <h2
                id="confirm-dialog-title"
                className="text-base font-bold text-gray-900 leading-snug"
              >
                {title}
              </h2>

              {(description || children) && (
                <div
                  id="confirm-dialog-description"
                  className="mt-2"
                >
                  {children ? (
                    <div className="text-sm text-gray-500 leading-relaxed">
                      {children}
                    </div>
                  ) : (
                    <p className="text-sm text-gray-500 leading-relaxed">
                      {description}
                    </p>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Divider */}
        <div className="border-t border-gray-200 mx-0" />

        {/* Footer / action buttons */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 bg-gray-50">
          {/* Cancel */}
          <button
            ref={cancelButtonRef}
            type="button"
            onClick={() => !loading && onCancel()}
            disabled={loading}
            className={cn(
              'px-4 py-2 rounded-lg text-sm font-semibold',
              'text-gray-700 bg-white border border-gray-300',
              'hover:bg-gray-50 hover:text-gray-900 hover:border-gray-400',
              'transition-all duration-150',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gray-300 focus-visible:ring-offset-2 focus-visible:ring-offset-white',
              'disabled:pointer-events-none disabled:opacity-50'
            )}
          >
            {cancelLabel}
          </button>

          {/* Confirm */}
          <button
            ref={confirmButtonRef}
            type="button"
            onClick={handleConfirm}
            disabled={loading || confirmDisabled}
            className={cn(
              'relative px-4 py-2 rounded-lg text-sm font-semibold',
              'text-white shadow-lg',
              'transition-all duration-150',
              'active:scale-[0.98]',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-white',
              config.confirmButtonClass,
              'disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100',
              loading || confirmDisabled ? '' : config.confirmButtonHoverClass,
            )}
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Please wait…</span>
              </span>
            ) : (
              confirmLabel
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Convenience wrappers
// ---------------------------------------------------------------------------

/** Pre-configured destructive confirm dialog */
export function DeleteConfirmDialog(
  props: Omit<ConfirmDialogProps, 'variant' | 'confirmLabel'> & {
    itemName?: string
    confirmLabel?: string
  }
) {
  const { itemName, ...rest } = props
  return (
    <ConfirmDialog
      variant="destructive"
      confirmLabel={props.confirmLabel ?? 'Delete'}
      description={
        props.description ??
        (itemName
          ? `Are you sure you want to delete "${itemName}"? This action cannot be undone.`
          : 'Are you sure you want to delete this item? This action cannot be undone.')
      }
      {...rest}
    />
  )
}

/** Pre-configured warning confirm dialog */
export function WarningConfirmDialog(
  props: Omit<ConfirmDialogProps, 'variant'>
) {
  return <ConfirmDialog variant="warning" {...props} />
}
