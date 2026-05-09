'use client'

import { cn } from '@/lib/utils'

interface SdgBadge {
  number: number
  title: string
  color: string
  icon: string
}

const SDG_DATA: Record<number, SdgBadge> = {
  3:  { number: 3,  title: 'Good Health',           color: '#4C9F38', icon: '❤️' },
  6:  { number: 6,  title: 'Clean Water',            color: '#26BDE2', icon: '💧' },
  7:  { number: 7,  title: 'Clean Energy',           color: '#FCC30B', icon: '⚡' },
  9:  { number: 9,  title: 'Industry & Innovation',  color: '#FD6925', icon: '🏭' },
  11: { number: 11, title: 'Sustainable Cities',     color: '#FD9D24', icon: '🏙️' },
  12: { number: 12, title: 'Responsible Consumption',color: '#BF8B2E', icon: '♻️' },
  13: { number: 13, title: 'Climate Action',         color: '#3F7E44', icon: '🌍' },
  15: { number: 15, title: 'Life on Land',           color: '#56C02B', icon: '🌿' },
  17: { number: 17, title: 'Partnerships',           color: '#19486A', icon: '🤝' },
}

interface SdgAlignmentBadgesProps {
  tags: string[]   // e.g. ["SDG 12: Responsible Consumption", "SDG 13: Climate Action"]
  size?: 'sm' | 'md' | 'lg'
  showTitle?: boolean
}

function extractSdgNumber(tag: string): number | null {
  const match = tag.match(/SDG\s*(\d+)/i)
  return match ? parseInt(match[1]) : null
}

export default function SdgAlignmentBadges({ tags, size = 'md', showTitle = true }: SdgAlignmentBadgesProps) {
  const sdgNumbers = tags
    .map(extractSdgNumber)
    .filter((n): n is number => n !== null && n in SDG_DATA)

  if (sdgNumbers.length === 0) return null

  const sizeClasses = {
    sm: 'w-8 h-8 text-xs',
    md: 'w-12 h-12 text-sm',
    lg: 'w-16 h-16 text-base',
  }

  return (
    <div className="flex flex-wrap gap-3">
      {sdgNumbers.map(num => {
        const sdg = SDG_DATA[num]
        return (
          <div key={num} className="flex flex-col items-center gap-1.5 group">
            <div
              className={cn(
                'rounded-lg flex items-center justify-center font-bold text-white shadow-md transition-transform group-hover:scale-110',
                sizeClasses[size]
              )}
              style={{ backgroundColor: sdg.color }}
              title={`SDG ${sdg.number}: ${sdg.title}`}
            >
              <span>{sdg.icon}</span>
            </div>
            {showTitle && (
              <div className="text-center">
                <p className="text-[10px] font-bold text-gray-500">SDG {sdg.number}</p>
                {size !== 'sm' && (
                  <p className="text-[9px] text-gray-400 max-w-[60px] leading-tight text-center">{sdg.title}</p>
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
