import type { Metadata, Viewport } from 'next'
import { Inter } from 'next/font/google'
import { Toaster } from 'sonner'
import { Providers } from './providers'
import TokenSync from '@/components/auth/TokenSync'
import './globals.css'
import 'leaflet/dist/leaflet.css'

// ---------------------------------------------------------------------------
// Font
// ---------------------------------------------------------------------------

const inter = Inter({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-inter',
})

// ---------------------------------------------------------------------------
// Metadata
// ---------------------------------------------------------------------------

export const metadata: Metadata = {
  title: {
    default: 'Hi-Tech Waste Management',
    template: '%s | Hi-Tech Waste Management',
  },
  description:
    'AI-Integrated Operations Platform for professional waste management — scheduled waste, recyclables, fleet, compliance, and ESG reporting.',
  keywords: [
    'waste management',
    'scheduled waste',
    'ESG',
    'compliance',
    'fleet management',
    'Malaysia',
    'DOE',
    'recycling',
  ],
  authors: [{ name: 'Hi-Tech Waste Management Sdn Bhd' }],
  creator: 'Hi-Tech Waste Management Sdn Bhd',
  robots: {
    index: false, // Internal operations platform — don't index
    follow: false,
  },
  icons: {
    icon: '/favicon.ico',
    shortcut: '/favicon-16x16.png',
    apple: '/apple-touch-icon.png',
  },
}

export const viewport: Viewport = {
  themeColor: [
    { media: '(prefers-color-scheme: dark)', color: '#0f172a' },
    { media: '(prefers-color-scheme: light)', color: '#ffffff' },
  ],
  width: 'device-width',
  initialScale: 1,
}

// ---------------------------------------------------------------------------
// Root Layout
// ---------------------------------------------------------------------------

interface RootLayoutProps {
  children: React.ReactNode
}

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html
      lang="en"
      className={inter.variable}
      suppressHydrationWarning
    >
      <body className="min-h-screen bg-gray-50 text-gray-900 antialiased font-sans transition-colors duration-200">
        <Providers>
          <TokenSync />
          {children}

          {/* Global toast notifications */}
          <Toaster
            position="top-right"
            expand={false}
            richColors
            closeButton
            duration={4000}
            toastOptions={{
              classNames: {
                toast: 'rounded-xl shadow-2xl bg-white border border-gray-200',
                title: 'text-sm font-semibold text-gray-900',
                description: 'text-xs text-gray-500',
                actionButton: 'bg-brand-600 text-white text-xs rounded-md px-2 py-1',
                cancelButton: 'bg-gray-100 text-gray-600 text-xs rounded-md px-2 py-1',
                closeButton: 'bg-gray-100 border-gray-200 text-gray-500 hover:bg-gray-200',
                success: 'border-green-500',
                error: 'border-red-500',
                warning: 'border-amber-500',
                info: 'border-brand-500',
              },
            }}
          />
        </Providers>
      </body>
    </html>
  )
}

