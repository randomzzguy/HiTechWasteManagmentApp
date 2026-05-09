'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  TooltipProps,
} from 'recharts'
import { BarChart2, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { cn, formatWeight, formatDate } from '@/lib/utils'
import { weighbridgeApi } from '@/lib/api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Period = 'daily' | 'weekly' | 'monthly'

interface DataPoint {
  label: string
  date: string
  tonnage_kg: number
  jobs_count: number
}

// ---------------------------------------------------------------------------
// Placeholder data generators
// ---------------------------------------------------------------------------

function generateDailyData(): DataPoint[] {
  const now = new Date()
  return Array.from({ length: 30 }, (_, i) => {
    const d = new Date(now)
    d.setDate(now.getDate() - (29 - i))
    const base = 55_000 + Math.sin(i * 0.4) * 15_000
    const noise = (Math.random() - 0.5) * 20_000
    return {
      label: formatDate(d, 'dd MMM'),
      date: d.toISOString(),
      tonnage_kg: Math.max(0, Math.round(base + noise)),
      jobs_count: Math.round(3 + Math.random() * 7),
    }
  })
}

function generateWeeklyData(): DataPoint[] {
  const now = new Date()
  return Array.from({ length: 12 }, (_, i) => {
    const d = new Date(now)
    d.setDate(now.getDate() - (11 - i) * 7)
    const base = 380_000 + Math.sin(i * 0.5) * 80_000
    const noise = (Math.random() - 0.5) * 60_000
    return {
      label: `Wk ${formatDate(d, 'dd MMM')}`,
      date: d.toISOString(),
      tonnage_kg: Math.max(0, Math.round(base + noise)),
      jobs_count: Math.round(18 + Math.random() * 20),
    }
  })
}

function generateMonthlyData(): DataPoint[] {
  const now = new Date()
  const months = [
    'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
  ]
  return Array.from({ length: 12 }, (_, i) => {
    const d = new Date(now.getFullYear(), now.getMonth() - (11 - i), 1)
    const base = 1_500_000 + Math.sin(i * 0.4) * 300_000
    const noise = (Math.random() - 0.5) * 200_000
    return {
      label: months[d.getMonth()],
      date: d.toISOString(),
      tonnage_kg: Math.max(0, Math.round(base + noise)),
      jobs_count: Math.round(70 + Math.random() * 40),
    }
  })
}

const PLACEHOLDER: Record<Period, DataPoint[]> = {
  daily: generateDailyData(),
  weekly: generateWeeklyData(),
  monthly: generateMonthlyData(),
}

// ---------------------------------------------------------------------------
// Custom Tooltip
// ---------------------------------------------------------------------------

function CustomTooltip({ active, payload, label }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null

  const tonnage = payload[0]?.value ?? 0
  const jobs = payload[1]?.value ?? 0

  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-lg px-4 py-3 min-w-[170px]">
      <p className="text-xs font-semibold text-gray-500 mb-2">{label}</p>
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center justify-between gap-4">
          <span className="flex items-center gap-1.5 text-xs text-gray-500">
            <span className="w-2.5 h-2.5 rounded-sm bg-green-500 inline-block flex-shrink-0" />
            Tonnage
          </span>
          <span className="text-xs font-bold text-gray-900">
            {formatWeight(tonnage)}
          </span>
        </div>
        <div className="flex items-center justify-between gap-4">
          <span className="flex items-center gap-1.5 text-xs text-gray-500">
            <span className="w-2.5 h-2.5 rounded-sm bg-brand-500/60 inline-block flex-shrink-0" />
            Jobs
          </span>
          <span className="text-xs font-bold text-gray-700">{jobs}</span>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Period tab button
// ---------------------------------------------------------------------------

interface TabButtonProps {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}

function TabButton({ active, onClick, children }: TabButtonProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'px-3 py-1.5 rounded-lg text-xs font-semibold transition-all duration-150',
        active
          ? 'bg-brand-600 text-white shadow-md shadow-brand-900/20'
          : 'text-gray-500 hover:text-gray-900 hover:bg-gray-100'
      )}
    >
      {children}
    </button>
  )
}

// ---------------------------------------------------------------------------
// Summary stats bar
// ---------------------------------------------------------------------------

interface SummaryProps {
  data: DataPoint[]
  period: Period
}

function SummaryBar({ data, period }: SummaryProps) {
  if (data.length === 0) return null

  const total = data.reduce((s, d) => s + d.tonnage_kg, 0)
  const average = total / data.length
  const latest = data[data.length - 1]?.tonnage_kg ?? 0
  const previous = data[data.length - 2]?.tonnage_kg ?? 0
  const diff = latest - previous
  const diffPct = previous > 0 ? (diff / previous) * 100 : 0
  const isUp = diff > 0
  const isNeutral = diff === 0

  const periodLabel = period === 'daily' ? 'today' : period === 'weekly' ? 'this week' : 'this month'

  return (
    <div className="grid grid-cols-3 gap-4 px-1 pb-2">
      {/* Total */}
      <div className="flex flex-col gap-0.5">
        <span className="text-[11px] text-gray-400 uppercase tracking-wider font-semibold">
          Total ({period === 'daily' ? '30d' : period === 'weekly' ? '12wk' : '12mo'})
        </span>
        <span className="text-base font-bold text-gray-900">{formatWeight(total)}</span>
      </div>

      {/* Average */}
      <div className="flex flex-col gap-0.5">
        <span className="text-[11px] text-gray-400 uppercase tracking-wider font-semibold">
          Avg / {period === 'daily' ? 'day' : period === 'weekly' ? 'week' : 'month'}
        </span>
        <span className="text-base font-bold text-gray-900">{formatWeight(average)}</span>
      </div>

      {/* Latest vs previous */}
      <div className="flex flex-col gap-0.5">
        <span className="text-[11px] text-gray-400 uppercase tracking-wider font-semibold">
          {periodLabel.charAt(0).toUpperCase() + periodLabel.slice(1)}
        </span>
        <div className="flex items-baseline gap-2">
          <span className="text-base font-bold text-gray-900">{formatWeight(latest)}</span>
          {!isNeutral && (
            <span
              className={cn(
                'flex items-center gap-0.5 text-[11px] font-semibold',
                isUp ? 'text-green-400' : 'text-red-400'
              )}
            >
              {isUp ? (
                <TrendingUp className="w-3 h-3" />
              ) : (
                <TrendingDown className="w-3 h-3" />
              )}
              {Math.abs(diffPct).toFixed(1)}%
            </span>
          )}
          {isNeutral && (
            <span className="flex items-center gap-0.5 text-[11px] font-semibold text-gray-500">
              <Minus className="w-3 h-3" />
              0%
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function TonnageChart() {
  const [period, setPeriod] = useState<Period>('daily')

  // Fetch data from API, fall back to placeholder
  const { data: apiData, isLoading } = useQuery({
    queryKey: ['tonnage-chart', period],
    queryFn: async () => {
      try {
        const result = await weighbridgeApi.getTonnageStats({ period })
        const raw = result as Record<string, unknown>
        const points = raw?.data_points as DataPoint[] | undefined
        if (Array.isArray(points) && points.length > 0) return points
        return null
      } catch {
        return null
      }
    },
    staleTime: 5 * 60_000,
    refetchInterval: 10 * 60_000,
  })

  const chartData: DataPoint[] = apiData ?? PLACEHOLDER[period]

  // Y-axis formatter
  function yAxisFormatter(value: number): string {
    if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}kt`
    if (value >= 1_000) return `${(value / 1_000).toFixed(0)}t`
    return `${value}kg`
  }

  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 px-5 pt-5 pb-4 border-b border-gray-100">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-green-50 border border-green-200">
            <BarChart2 className="w-4 h-4 text-green-400" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-gray-900">Tonnage Processed</h3>
            <p className="text-xs text-gray-400 mt-0.5">Weight collected & processed over time</p>
          </div>
        </div>

        {/* Period tabs */}
        <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-1">
          <TabButton active={period === 'daily'} onClick={() => setPeriod('daily')}>
            Daily
          </TabButton>
          <TabButton active={period === 'weekly'} onClick={() => setPeriod('weekly')}>
            Weekly
          </TabButton>
          <TabButton active={period === 'monthly'} onClick={() => setPeriod('monthly')}>
            Monthly
          </TabButton>
        </div>
      </div>

      {/* Summary stats */}
      <div className="px-5 pt-4">
        {isLoading ? (
          <div className="grid grid-cols-3 gap-4 pb-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="flex flex-col gap-1">
                <div className="h-3 w-20 rounded bg-gray-200 animate-pulse" />
                <div className="h-5 w-24 rounded bg-gray-200 animate-pulse" />
              </div>
            ))}
          </div>
        ) : (
          <SummaryBar data={chartData} period={period} />
        )}
      </div>

      {/* Chart */}
      <div className="px-2 pb-4">
        {isLoading ? (
          <div className="h-[260px] flex items-center justify-center">
            <div className="flex flex-col items-center gap-3">
              <div className="w-8 h-8 border-2 border-green-500 border-t-transparent rounded-full animate-spin" />
              <span className="text-xs text-gray-400">Loading chart data…</span>
            </div>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart
              data={chartData}
              margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
            >
              <defs>
                <linearGradient id="tonnageGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#16a34a" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#16a34a" stopOpacity={0.02} />
                </linearGradient>
                <linearGradient id="jobsGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.01} />
                </linearGradient>
              </defs>

              <CartesianGrid
                strokeDasharray="3 3"
                stroke="#e5e7eb"
                vertical={false}
              />

              <XAxis
                dataKey="label"
                tick={{ fill: '#64748b', fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                interval={
                  period === 'daily'
                    ? Math.floor(chartData.length / 7)
                    : 'preserveStartEnd'
                }
              />

              <YAxis
                tickFormatter={yAxisFormatter}
                tick={{ fill: '#64748b', fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                width={48}
              />

              <Tooltip content={<CustomTooltip />} />

              {/* Tonnage area */}
              <Area
                type="monotone"
                dataKey="tonnage_kg"
                name="Tonnage"
                stroke="#16a34a"
                strokeWidth={2}
                fill="url(#tonnageGradient)"
                dot={false}
                activeDot={{
                  r: 4,
                  fill: '#16a34a',
                  stroke: '#f9fafb',
                  strokeWidth: 2,
                }}
              />

              {/* Jobs count area (secondary, scaled) */}
              <Area
                type="monotone"
                dataKey="jobs_count"
                name="Jobs"
                stroke="#3b82f6"
                strokeWidth={1.5}
                strokeDasharray="4 2"
                fill="url(#jobsGradient)"
                dot={false}
                activeDot={{
                  r: 3,
                  fill: '#3b82f6',
                  stroke: '#f9fafb',
                  strokeWidth: 2,
                }}
                yAxisId={0}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-5 px-5 pb-4">
        <span className="flex items-center gap-1.5 text-[11px] text-gray-500">
          <span className="w-6 h-0.5 bg-green-500 rounded inline-block" />
          Tonnage (kg)
        </span>
        <span className="flex items-center gap-1.5 text-[11px] text-gray-500">
          <span
            className="w-6 h-0.5 rounded inline-block"
            style={{
              background:
                'repeating-linear-gradient(to right, #3b82f6 0, #3b82f6 4px, transparent 4px, transparent 6px)',
            }}
          />
          Jobs count
        </span>
        {!apiData && (
          <span className="ml-auto text-[11px] text-gray-400 italic">
            Sample data
          </span>
        )}
      </div>
    </div>
  )
}
