import NextAuth, { NextAuthOptions, Session, User } from 'next-auth'
import CredentialsProvider from 'next-auth/providers/credentials'
import { JWT } from 'next-auth/jwt'

// ---------------------------------------------------------------------------
// Extended types
// ---------------------------------------------------------------------------

declare module 'next-auth' {
  interface Session {
    user: {
      id: string
      email: string
      name: string
      role: string
      profile_photo_url?: string
    }
    access_token: string
    expires: string
  }

  interface User {
    id: string
    email: string
    name: string
    role: string
    profile_photo_url?: string
    access_token: string
  }
}

declare module 'next-auth/jwt' {
  interface JWT {
    id: string
    email: string
    name: string
    role: string
    profile_photo_url?: string
    access_token: string
    expires_at?: number
  }
}

// ---------------------------------------------------------------------------
// NextAuth configuration
// ---------------------------------------------------------------------------

export const authOptions: NextAuthOptions = {
  providers: [
    CredentialsProvider({
      id: 'credentials',
      name: 'Email & Password',
      credentials: {
        email: {
          label: 'Email',
          type: 'email',
          placeholder: 'you@hitech-waste.com',
        },
        password: {
          label: 'Password',
          type: 'password',
        },
      },

      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) {
          throw new Error('Email and password are required.')
        }

        try {
          // Server-side calls use the internal Docker service name.
          // Browser-side calls use NEXT_PUBLIC_API_URL.
          const baseUrl =
            process.env.BACKEND_URL ??
            process.env.NEXT_PUBLIC_API_URL ??
            'http://localhost:8000'

          const res = await fetch(`${baseUrl}/api/v1/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              username: credentials.email,
              password: credentials.password,
            }),
          })

          if (!res.ok) {
            let message = 'Invalid email or password.'
            try {
              const body = await res.json()
              if (body?.detail) message = body.detail
              else if (body?.message) message = body.message
              else if (body?.non_field_errors?.[0])
                message = body.non_field_errors[0]
            } catch {
              // ignore JSON parse errors
            }
            throw new Error(message)
          }

          const data = await res.json()

          if (!data?.access_token || !data?.user) {
            throw new Error('Unexpected response from authentication server.')
          }

          const user: User = {
            id: String(data.user.id),
            email: data.user.email,
            name: data.user.full_name ?? data.user.name ?? data.user.email,
            role: data.user.role ?? 'viewer',
            profile_photo_url: data.user.profile_photo_url ?? undefined,
            access_token: data.access_token,
          }

          return user
        } catch (err: unknown) {
          // Re-throw so NextAuth surfaces it as a callbackUrl error
          if (err instanceof Error) throw err
          throw new Error('Authentication failed. Please try again.')
        }
      },
    }),
  ],

  // -------------------------------------------------------------------------
  // JWT strategy — token stored in an httpOnly cookie
  // -------------------------------------------------------------------------
  session: {
    strategy: 'jwt',
    // 8-hour session lifetime
    maxAge: 8 * 60 * 60,
  },

  // -------------------------------------------------------------------------
  // JWT callbacks
  // -------------------------------------------------------------------------
  callbacks: {
    /**
     * Runs when a JWT is created (sign-in) or updated (session access).
     * We persist the backend access token and user metadata inside the JWT.
     */
    async jwt({ token, user }: { token: JWT; user?: User }) {
      if (user) {
        // First sign-in: copy user data into the token
        token.id = user.id
        token.email = user.email
        token.name = user.name
        token.role = user.role
        token.profile_photo_url = user.profile_photo_url
        token.access_token = user.access_token
        // Record when the access token was issued
        token.expires_at = Math.floor(Date.now() / 1000) + 8 * 60 * 60
      }
      return token
    },

    /**
     * Runs whenever a Session is accessed via `useSession()` or `getSession()`.
     * Exposes selected token fields to the client.
     */
    async session({ session, token }: { session: Session; token: JWT }) {
      session.user = {
        id: token.id,
        email: token.email,
        name: token.name,
        role: token.role,
        profile_photo_url: token.profile_photo_url,
      }
      session.access_token = token.access_token
      return session
    },
  },

  // -------------------------------------------------------------------------
  // Pages
  // -------------------------------------------------------------------------
  pages: {
    signIn: '/login',
    error: '/login',
  },

  // -------------------------------------------------------------------------
  // Security
  // -------------------------------------------------------------------------
  secret: process.env.NEXTAUTH_SECRET,

  // Enable debug logging only in development
  debug: process.env.NODE_ENV !== 'production',

  // Disable secure cookies — running on HTTP localhost (no HTTPS)
  useSecureCookies: false,

  cookies: {
    sessionToken: {
      name: 'next-auth.session-token',
      options: {
        httpOnly: true,
        sameSite: 'lax' as const,
        path: '/',
        secure: false,
      },
    },
  },
}

export default NextAuth(authOptions)
