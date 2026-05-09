import type { Metadata } from 'next'
import Image from 'next/image'

export const metadata: Metadata = {
  title: 'Sign In',
  description: 'Sign in to Hi-Tech Waste Management Operations Platform',
}

interface AuthLayoutProps {
  children: React.ReactNode
}

export default function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <div className="min-h-screen w-full flex flex-col items-center justify-center relative overflow-hidden bg-gradient-to-br from-brand-700 via-brand-800 to-brand-900">
      {/* Subtle radial overlays */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_left,_rgba(255,255,255,0.08)_0%,_transparent_60%)]" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_right,_rgba(0,0,0,0.2)_0%,_transparent_70%)]" />

      {/* Subtle grid pattern */}
      <div
        className="absolute inset-0 opacity-[0.04]"
        style={{
          backgroundImage: `linear-gradient(rgba(255,255,255,0.3) 1px, transparent 1px),
                            linear-gradient(90deg, rgba(255,255,255,0.3) 1px, transparent 1px)`,
          backgroundSize: '40px 40px',
        }}
      />

      {/* Floating decorative orbs */}
      <div className="absolute top-[-10%] left-[-5%] w-96 h-96 bg-brand-500/20 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-5%] w-80 h-80 bg-brand-400/15 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute top-1/3 right-[10%] w-64 h-64 bg-white/5 rounded-full blur-2xl pointer-events-none" />

      {/* Top logo / branding bar */}
      <div className="relative z-10 flex items-center gap-3 mb-8 select-none">
        <Image
          src="/logo.png"
          alt="Hi-Tech Waste Management"
          width={48}
          height={48}
          className="rounded-xl shadow-lg shadow-brand-900/40"
          priority
        />
      </div>

      {/* Main content card */}
      <div className="relative z-10 w-full max-w-md px-4">
        <div className="bg-white border border-gray-200 rounded-2xl shadow-2xl shadow-black/30 overflow-hidden">
          {/* Top accent bar */}
          <div className="h-0.5 w-full bg-gradient-to-r from-transparent via-brand-500 to-transparent opacity-80" />

          <div className="p-8">
            {children}
          </div>
        </div>
      </div>

      {/* Bottom tagline */}
      <p className="relative z-10 mt-8 text-xs text-brand-200/70 text-center select-none">
        © {new Date().getFullYear()} Hi-Tech Waste Management Sdn Bhd &mdash; All rights reserved
      </p>
    </div>
  )
}
