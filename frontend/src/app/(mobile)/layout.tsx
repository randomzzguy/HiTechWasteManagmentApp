import type { Metadata, Viewport } from 'next'

export const metadata: Metadata = {
  title: 'Hi-Tech Driver App',
  description: 'Driver job management',
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
}

export default function MobileLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-gray-50">
      {children}
    </div>
  )
}
