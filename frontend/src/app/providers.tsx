'use client'

import { useState } from 'react'
import { SessionProvider } from 'next-auth/react'
import {
  QueryClient,
  QueryClientProvider,
  defaultShouldDehydrateQuery,
} from '@tanstack/react-query'

// ---------------------------------------------------------------------------
// QueryClient factory — creates a new client per component mount.
// This is the recommended pattern for Next.js App Router to avoid sharing
// state between requests on the server.
// ---------------------------------------------------------------------------

function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // With SSR we usually want a higher staleTime to avoid refetching
        // immediately on the client after a server render.
        staleTime: 60 * 1000, // 1 minute

        // Retry failed requests up to 2 times with exponential backoff
        retry: 2,
        retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 30_000),

        // Refetch on window focus so data stays fresh when the user
        // returns to the tab after a while.
        refetchOnWindowFocus: true,

        // Don't refetch on reconnect for every query by default —
        // individual hooks can opt in.
        refetchOnReconnect: 'always',
      },
      mutations: {
        // Show errors in the console during development
        onError:
          process.env.NODE_ENV === 'development'
            ? (error: unknown) => {
                console.error('[React Query mutation error]', error)
              }
            : undefined,
      },
      dehydrate: {
        // Include pending queries in the dehydrated state so Suspense
        // boundaries can be used with prefetched data.
        shouldDehydrateQuery: (query) =>
          defaultShouldDehydrateQuery(query) ||
          query.state.status === 'pending',
      },
    },
  })
}

// Singleton for the browser — ensures the same QueryClient instance is
// reused across re-renders (avoids cache loss on hot reload in dev).
let browserQueryClient: QueryClient | undefined

function getQueryClient(): QueryClient {
  if (typeof window === 'undefined') {
    // Server: always create a new QueryClient so different requests
    // don't share the same cache.
    return makeQueryClient()
  }

  // Browser: reuse the existing client or create one on first call.
  if (!browserQueryClient) {
    browserQueryClient = makeQueryClient()
  }

  return browserQueryClient
}

// ---------------------------------------------------------------------------
// ReactQueryProvider — thin wrapper to avoid calling getQueryClient() during
// render on the server (which would create a new client on every render).
// ---------------------------------------------------------------------------

interface ReactQueryProviderProps {
  children: React.ReactNode
}

export function ReactQueryProvider({ children }: ReactQueryProviderProps) {
  // NOTE: Avoid useState here if we need server-side pre-population later.
  // Using a ref-like pattern via the module-level singleton is fine for now.
  const [queryClient] = useState(() => getQueryClient())

  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  )
}

// ---------------------------------------------------------------------------
// Combined Providers — wraps the entire app with all global providers.
// ---------------------------------------------------------------------------

interface ProvidersProps {
  children: React.ReactNode
  /** Next-Auth session passed from a Server Component via `getServerSession` */
  session?: Parameters<typeof SessionProvider>[0]['session']
}

export function Providers({ children, session }: ProvidersProps) {
  return (
    <SessionProvider
      session={session}
      // Refetch the session every 5 minutes so the JWT stays fresh
      refetchInterval={5 * 60}
      // Re-fetch the session when the window regains focus
      refetchOnWindowFocus={true}
    >
      <ReactQueryProvider>
        {children}
      </ReactQueryProvider>
    </SessionProvider>
  )
}

export default Providers
