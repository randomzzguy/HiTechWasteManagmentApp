'use client'

import { Suspense, useState } from 'react'
import { signIn } from 'next-auth/react'
import { useRouter, useSearchParams } from 'next/navigation'
import Image from 'next/image'
import { Mail, Lock, Loader2, AlertCircle, Eye, EyeOff } from 'lucide-react'

function LoginForm() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const callbackUrl = searchParams.get('callbackUrl') ?? '/dashboard'

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Surface any error passed by NextAuth via URL (e.g. after a failed redirect)
  const urlError = searchParams.get('error')
  const urlErrorMessage =
    urlError === 'CredentialsSignin'
      ? 'Invalid email or password. Please try again.'
      : urlError
      ? 'An authentication error occurred. Please try again.'
      : null

  const displayError = error ?? urlErrorMessage

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setError(null)

    if (!email.trim()) {
      setError('Please enter your email address.')
      return
    }
    if (!password) {
      setError('Please enter your password.')
      return
    }

    setIsLoading(true)

    try {
      const result = await signIn('credentials', {
        email: email.trim().toLowerCase(),
        password,
        redirect: false,
        callbackUrl,
      })

      if (!result) {
        setError('An unexpected error occurred. Please try again.')
        return
      }

      if (result.error) {
        if (
          result.error === 'CredentialsSignin' ||
          result.error.toLowerCase().includes('invalid')
        ) {
          setError('Invalid email or password. Please try again.')
        } else {
          setError(result.error)
        }
        return
      }

      if (result.ok) {
        // Hard redirect so the session cookie is read fresh on the new page
        window.location.href = result.url ?? callbackUrl
      }
    } catch (err: unknown) {
      console.error('[Login] Unexpected error:', err)
      setError('An unexpected error occurred. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="text-center">
        <div className="flex items-center justify-center gap-2.5 mb-4">
          <Image
            src="/logo.png"
            alt="Hi-Tech Waste Management"
            width={40}
            height={40}
            className="rounded-xl shadow-lg shadow-brand-900/20"
            priority
          />
          <h1 className="text-xl font-bold text-gray-900 tracking-tight">
            Hi-Tech Waste Management
          </h1>
        </div>
        <h2 className="text-2xl font-bold text-gray-900 mt-1">Welcome back</h2>
        <p className="text-sm text-gray-500 mt-1">
          AI-Integrated Operations Platform
        </p>
      </div>

      {/* Error Banner */}
      {displayError && (
        <div
          role="alert"
          className="flex items-start gap-3 p-3.5 rounded-lg bg-red-50 border border-red-200 text-sm text-red-600 animate-in"
        >
          <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0 text-red-500" />
          <span>{displayError}</span>
        </div>
      )}

      {/* Form */}
      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
        {/* Email */}
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="email"
            className="text-xs font-semibold text-gray-500 uppercase tracking-wider"
          >
            Email Address
          </label>
          <div className="relative">
            <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
            <input
              id="email"
              type="email"
              autoComplete="email"
              autoFocus
              required
              disabled={isLoading}
              value={email}
              onChange={(e) => {
                setEmail(e.target.value)
                setError(null)
              }}
              placeholder="you@hitech-waste.com"
              className={[
                'w-full pl-10 pr-4 py-2.5 rounded-lg text-sm',
                'bg-gray-50 border text-gray-900 placeholder-gray-400',
                'transition-all duration-150 outline-none',
                displayError
                  ? 'border-red-300 focus:border-red-500 focus:ring-2 focus:ring-red-500/20'
                  : 'border-gray-300 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20',
                'disabled:opacity-50 disabled:cursor-not-allowed',
              ].join(' ')}
            />
          </div>
        </div>

        {/* Password */}
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <label
              htmlFor="password"
              className="text-xs font-semibold text-gray-500 uppercase tracking-wider"
            >
              Password
            </label>
            <button
              type="button"
              tabIndex={-1}
              className="text-xs text-brand-600 hover:text-brand-700 transition-colors"
              onClick={() =>
                setError('Password reset is not available in this demo.')
              }
            >
              Forgot password?
            </button>
          </div>
          <div className="relative">
            <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
            <input
              id="password"
              type={showPassword ? 'text' : 'password'}
              autoComplete="current-password"
              required
              disabled={isLoading}
              value={password}
              onChange={(e) => {
                setPassword(e.target.value)
                setError(null)
              }}
              placeholder="••••••••"
              className={[
                'w-full pl-10 pr-10 py-2.5 rounded-lg text-sm',
                'bg-gray-50 border text-gray-900 placeholder-gray-400',
                'transition-all duration-150 outline-none',
                displayError
                  ? 'border-red-300 focus:border-red-500 focus:ring-2 focus:ring-red-500/20'
                  : 'border-gray-300 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20',
                'disabled:opacity-50 disabled:cursor-not-allowed',
              ].join(' ')}
            />
            <button
              type="button"
              tabIndex={-1}
              disabled={isLoading}
              onClick={() => setShowPassword((v) => !v)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors disabled:pointer-events-none"
              aria-label={showPassword ? 'Hide password' : 'Show password'}
            >
              {showPassword ? (
                <EyeOff className="w-4 h-4" />
              ) : (
                <Eye className="w-4 h-4" />
              )}
            </button>
          </div>
        </div>

        {/* Submit */}
        <button
          type="submit"
          disabled={isLoading || !email || !password}
          className={[
            'relative mt-2 w-full flex items-center justify-center gap-2',
            'px-4 py-2.5 rounded-lg text-sm font-semibold',
            'bg-gradient-to-r from-brand-600 to-brand-700',
            'text-white shadow-lg shadow-brand-900/20',
            'transition-all duration-200',
            'hover:from-brand-500 hover:to-brand-600 hover:shadow-brand-800/30',
            'active:scale-[0.98]',
            'disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:from-brand-600 disabled:hover:to-brand-700',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white',
          ].join(' ')}
        >
          {isLoading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Signing in…</span>
            </>
          ) : (
            <span>Sign In</span>
          )}
        </button>
      </form>

      {/* Divider */}
      <div className="relative flex items-center gap-3">
        <div className="flex-1 h-px bg-gray-200" />
        <span className="text-xs text-gray-400">SECURE PORTAL</span>
        <div className="flex-1 h-px bg-gray-200" />
      </div>

      {/* Footer note */}
      <p className="text-center text-xs text-gray-400 leading-relaxed">
        This platform is for authorised Hi-Tech Waste Management personnel only.
        <br />
        Unauthorised access is prohibited.
      </p>
    </div>
  )
}

export default function LoginPage() {
  return (
    <Suspense fallback={
      <div className="flex flex-col gap-6">
        <div className="text-center">
          <div className="flex items-center justify-center gap-2.5 mb-4">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-brand-600 to-brand-800">
              <div className="w-5 h-5 bg-white/30 rounded animate-pulse" />
            </div>
            <h1 className="text-xl font-bold text-gray-900 tracking-tight">Hi-Tech Waste Management</h1>
          </div>
          <div className="h-8 w-48 mx-auto rounded bg-gray-200 animate-pulse mt-2" />
        </div>
      </div>
    }>
      <LoginForm />
    </Suspense>
  )
}
