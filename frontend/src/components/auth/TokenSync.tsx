'use client'

import { useEffect } from 'react'
import { useSession } from 'next-auth/react'

/**
 * Syncs the NextAuth access_token into sessionStorage so the Axios
 * interceptor can inject it as a Bearer token on every API request.
 *
 * Must be rendered inside <SessionProvider> — place it in the root layout.
 */
export default function TokenSync() {
  const { data: session, status } = useSession()

  useEffect(() => {
    if (status === 'authenticated' && session?.access_token) {
      sessionStorage.setItem('access_token', session.access_token)
    } else if (status === 'unauthenticated') {
      sessionStorage.removeItem('access_token')
      localStorage.removeItem('access_token')
    }
  }, [session, status])

  return null
}
