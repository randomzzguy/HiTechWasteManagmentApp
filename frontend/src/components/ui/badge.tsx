import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
  {
    variants: {
      variant: {
        default: 'border-transparent bg-green-600 text-white',
        secondary: 'border-transparent bg-gray-100 text-gray-600',
        destructive: 'border-transparent bg-red-900/50 text-red-300 border-red-700',
        outline: 'border-gray-300 text-gray-600',
        warning: 'border-transparent bg-amber-900/50 text-amber-300 border-amber-700',
        success: 'border-transparent bg-green-900/50 text-green-300 border-green-700',
        info: 'border-transparent bg-brand-900/50 text-brand-300 border-brand-700',
      },
    },
    defaultVariants: { variant: 'default' },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />
}

export { Badge, badgeVariants }


