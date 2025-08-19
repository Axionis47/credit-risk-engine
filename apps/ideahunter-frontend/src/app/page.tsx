'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { IdeaDeck } from '@/components/IdeaDeck'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { apiClient } from '@/lib/api'
import { User, WhoAmIResponse } from '@/types/api'

// FORCE DYNAMIC RENDERING - ABSOLUTELY NO STATIC GENERATION
export const dynamic = 'force-dynamic'
export const revalidate = 0
export const fetchCache = 'force-no-store'
export const runtime = 'nodejs'

declare global {
  interface Window {
    google: any;
  }
}

export default function Home() {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isClient, setIsClient] = useState(false)
  const [googleLoaded, setGoogleLoaded] = useState(false)

  // Removed development logging to prevent production leakage

  useEffect(() => {
    setIsClient(true)
    loadGoogleScript()
  }, [])

  useEffect(() => {
    checkAuth()
  }, [])

  const loadGoogleScript = () => {
    if (window.google) {
      setGoogleLoaded(true)
      return
    }

    const script = document.createElement('script')
    script.src = 'https://accounts.google.com/gsi/client'
    script.async = true
    script.defer = true
    script.onload = () => {
      setGoogleLoaded(true)
    }
    document.head.appendChild(script)
  }

  const checkAuth = async () => {
    try {
      const response: WhoAmIResponse = await apiClient.whoami()
      if (response.authenticated && response.user) {
        setUser(response.user)
      }
      // Remove mock authentication bypass - require real auth
    } catch (error) {
      // Log error securely without exposing sensitive data
      if (process.env.NODE_ENV === 'development') {
        console.error('Auth check failed')
      }
      // Don't create mock users - require real authentication
    } finally {
      setIsLoading(false)
    }
  }

  const handleGoogleAuth = async (token: string) => {
    try {
      const authResponse = await apiClient.authenticateWithGoogle(token)
      // Token is now stored in httpOnly cookie by the server
      setUser(authResponse.user)
    } catch (error) {
      if (process.env.NODE_ENV === 'development') {
        console.error('Google auth failed:', error)
      }
      alert('Authentication failed. Please try again.')
    }
  }

  const handleSignOut = async () => {
    try {
      // Call logout endpoint to clear httpOnly cookie
      await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/logout`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'X-Requested-With': 'XMLHttpRequest'
        }
      })
    } catch (error) {
      if (process.env.NODE_ENV === 'development') {
        console.error('Logout failed')
      }
    } finally {
      setUser(null)
    }
  }

  if (isLoading || !isClient) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-400 mx-auto mb-4"></div>
          <p className="text-purple-200">Loading stunning design...</p>
        </div>
      </div>
    )
  }

  if (!user) {
    return (
      <div className="min-h-screen relative overflow-hidden">
        {/* Animated Background */}
        <div className="absolute inset-0 bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-purple-900/20 via-transparent to-transparent"></div>
          <div className="absolute top-0 left-0 w-full h-full">
            <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-purple-500/10 rounded-full blur-3xl animate-pulse"></div>
            <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl animate-pulse delay-1000"></div>
            <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-pink-500/10 rounded-full blur-3xl animate-pulse delay-2000"></div>
          </div>
        </div>

        {/* Floating Elements */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-20 left-10 w-2 h-2 bg-purple-400/30 rounded-full animate-bounce delay-300"></div>
          <div className="absolute top-40 right-20 w-3 h-3 bg-blue-400/30 rounded-full animate-bounce delay-700"></div>
          <div className="absolute bottom-40 left-20 w-2 h-2 bg-pink-400/30 rounded-full animate-bounce delay-1000"></div>
          <div className="absolute bottom-20 right-10 w-3 h-3 bg-indigo-400/30 rounded-full animate-bounce delay-500"></div>
        </div>

        {/* Main Content */}
        <div className="relative z-10 min-h-screen flex items-center justify-center px-4">
          <div className="max-w-lg w-full">
            {/* Main Card */}
            <div className="bg-white/10 backdrop-blur-xl rounded-3xl p-8 shadow-2xl border border-white/20 relative overflow-hidden">
              {/* Card Background Effect */}
              <div className="absolute inset-0 bg-gradient-to-br from-white/5 to-transparent rounded-3xl"></div>

              {/* Content */}
              <div className="relative z-10">
                {/* Logo Section */}
                <div className="text-center mb-8">
                  <div className="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-purple-500 to-pink-500 rounded-3xl mb-6 shadow-2xl relative">
                    <div className="absolute inset-0 bg-gradient-to-br from-purple-400 to-pink-400 rounded-3xl blur-lg opacity-50"></div>
                    <span className="text-3xl relative z-10">🎯</span>
                  </div>

                  <h1 className="text-4xl font-bold mb-3">
                    <span className="bg-gradient-to-r from-purple-400 via-pink-400 to-blue-400 bg-clip-text text-transparent">
                      Idea Hunter
                    </span>
                  </h1>

                  <p className="text-white/80 text-lg leading-relaxed">
                    Discover and save brilliant content ideas from Reddit's most creative communities
                  </p>
                </div>

                {/* Features Grid */}
                <div className="grid grid-cols-1 gap-4 mb-8">
                  <div className="group flex items-center gap-4 p-4 bg-white/5 rounded-2xl border border-white/10 hover:bg-white/10 transition-all duration-300">
                    <div className="w-12 h-12 bg-gradient-to-br from-purple-500/20 to-purple-600/20 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform">
                      <span className="text-xl">🔍</span>
                    </div>
                    <div>
                      <h3 className="text-white font-semibold">Discover Trending Ideas</h3>
                      <p className="text-white/60 text-sm">Find viral content before it explodes</p>
                    </div>
                  </div>

                  <div className="group flex items-center gap-4 p-4 bg-white/5 rounded-2xl border border-white/10 hover:bg-white/10 transition-all duration-300">
                    <div className="w-12 h-12 bg-gradient-to-br from-pink-500/20 to-pink-600/20 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform">
                      <span className="text-xl">💾</span>
                    </div>
                    <div>
                      <h3 className="text-white font-semibold">Save Your Favorites</h3>
                      <p className="text-white/60 text-sm">Build your personal idea collection</p>
                    </div>
                  </div>

                  <div className="group flex items-center gap-4 p-4 bg-white/5 rounded-2xl border border-white/10 hover:bg-white/10 transition-all duration-300">
                    <div className="w-12 h-12 bg-gradient-to-br from-blue-500/20 to-blue-600/20 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform">
                      <span className="text-xl">📊</span>
                    </div>
                    <div>
                      <h3 className="text-white font-semibold">Track Performance</h3>
                      <p className="text-white/60 text-sm">Monitor engagement and success rates</p>
                    </div>
                  </div>
                </div>

                {/* CTA Button */}
                <div className="space-y-6">
                  {googleLoaded && process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ? (
                    <div
                      id="google-signin-button"
                      className="w-full flex justify-center"
                      ref={(element) => {
                        if (element && window.google && !element.hasChildNodes()) {
                          window.google.accounts.id.initialize({
                            client_id: process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID,
                            callback: (response: any) => handleGoogleAuth(response.credential),
                          })
                          window.google.accounts.id.renderButton(element, {
                            theme: 'filled_blue',
                            size: 'large',
                            width: 300,
                            text: 'continue_with'
                          })
                        }
                      }}
                    />
                  ) : (
                    <div className="w-full flex justify-center py-4">
                      <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-purple-400"></div>
                    </div>
                  )}


                  <p className="text-white/60 text-center text-sm">
                    Join thousands of creators discovering their next viral idea
                  </p>

                  {/* Demo Notice */}
                  <div className="bg-amber-500/10 border border-amber-500/20 rounded-2xl p-4 backdrop-blur-sm">
                    <div className="flex items-center gap-3 mb-2">
                      <div className="w-8 h-8 bg-amber-500/20 rounded-lg flex items-center justify-center">
                        <span className="text-amber-400">⚡</span>
                      </div>
                      <span className="text-amber-300 font-semibold">Demo Mode Active</span>
                    </div>
                    <p className="text-amber-200/80 text-sm leading-relaxed">
                      Experience the full app with sample data. Click above to start exploring amazing content ideas!
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-6">
            <h1 className="text-xl font-semibold flex items-center gap-2">
              🎯 Idea Hunter
            </h1>
            <nav className="flex items-center gap-4">
              <Link 
                href="/" 
                className="text-sm font-medium text-primary border-b-2 border-primary pb-1"
              >
                Deck
              </Link>
              <Link 
                href="/accepted" 
                className="text-sm text-muted-foreground hover:text-foreground"
              >
                Accepted
              </Link>
            </nav>
          </div>
          
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              {user.picture && (
                <img 
                  src={user.picture} 
                  alt={user.name}
                  className="w-6 h-6 rounded-full"
                />
              )}
              <span className="text-sm text-muted-foreground">{user.name}</span>
            </div>
            <button
              onClick={handleSignOut}
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-6xl mx-auto px-6 py-8">
        <div className="text-center mb-8">
          <h2 className="text-2xl font-bold mb-2">Discover Ideas</h2>
          <p className="text-muted-foreground">
            Swipe through curated content ideas from Reddit
          </p>
        </div>

        <ErrorBoundary>
          <IdeaDeck />
        </ErrorBoundary>
      </main>
    </div>
  )
}
