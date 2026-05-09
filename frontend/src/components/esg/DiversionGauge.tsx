'use client'

import { cn } from '@/lib/utils'

interface DiversionGaugeProps {
  rate: number          // 0–100
  target?: number       // SLA target %
  size?: number         // SVG size in px
  label?: string
  showTarget?: boolean
}

export default function DiversionGauge({
  rate,
  target,
  size = 160,
  label = 'Diversion Rate',
  showTarget = true,
}: DiversionGaugeProps) {
  const clampedRate = Math.min(100, Math.max(0, rate))
  const clampedTarget = target ? Math.min(100, Math.max(0, target)) : undefined

  // Arc geometry — 270° sweep starting from bottom-left
  const cx = size / 2
  const cy = size / 2
  const r = (size - 24) / 2
  const startAngle = 135  // degrees
  const sweepAngle = 270  // degrees

  const toRad = (deg: number) => (deg * Math.PI) / 180

  const arcPath = (pct: number) => {
    const angle = startAngle + (sweepAngle * pct) / 100
    const x = cx + r * Math.cos(toRad(angle))
    const y = cy + r * Math.sin(toRad(angle))
    const largeArc = sweepAngle * pct / 100 > 180 ? 1 : 0

    const startX = cx + r * Math.cos(toRad(startAngle))
    const startY = cy + r * Math.sin(toRad(startAngle))

    return `M ${startX} ${startY} A ${r} ${r} 0 ${largeArc} 1 ${x} ${y}`
  }

  const targetAngle = clampedTarget
    ? startAngle + (sweepAngle * clampedTarget) / 100
    : null

  const targetX = targetAngle ? cx + r * Math.cos(toRad(targetAngle)) : 0
  const targetY = targetAngle ? cy + r * Math.sin(toRad(targetAngle)) : 0

  const isAboveTarget = clampedTarget ? clampedRate >= clampedTarget : true
  const gaugeColor = isAboveTarget ? '#22c55e' : clampedRate >= (clampedTarget ?? 0) * 0.8 ? '#f59e0b' : '#ef4444'

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size}>
          {/* Background track */}
          <path
            d={arcPath(100)}
            fill="none"
            stroke="#1e293b"
            strokeWidth={10}
            strokeLinecap="round"
          />
          {/* Rate arc */}
          {clampedRate > 0 && (
            <path
              d={arcPath(clampedRate)}
              fill="none"
              stroke={gaugeColor}
              strokeWidth={10}
              strokeLinecap="round"
              style={{ transition: 'all 0.8s ease-out', filter: `drop-shadow(0 0 6px ${gaugeColor}60)` }}
            />
          )}
          {/* Target marker */}
          {targetAngle && (
            <circle
              cx={targetX}
              cy={targetY}
              r={5}
              fill="#f59e0b"
              stroke="#0f172a"
              strokeWidth={2}
            />
          )}
        </svg>

        {/* Center text */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={cn('text-3xl font-bold', isAboveTarget ? 'text-green-400' : 'text-amber-400')}>
            {clampedRate.toFixed(1)}%
          </span>
          {clampedTarget && (
            <span className="text-xs text-slate-500 mt-0.5">
              Target: {clampedTarget}%
            </span>
          )}
        </div>
      </div>

      <div className="text-center">
        <p className="text-sm font-semibold text-white">{label}</p>
        {clampedTarget && (
          <p className={cn('text-xs mt-0.5', isAboveTarget ? 'text-green-400' : 'text-amber-400')}>
            {isAboveTarget
              ? `✓ ${(clampedRate - clampedTarget).toFixed(1)}% above target`
              : `${(clampedTarget - clampedRate).toFixed(1)}% below target`
            }
          </p>
        )}
      </div>
    </div>
  )
}
