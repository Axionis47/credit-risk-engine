'use client'

import { useEffect, useState } from 'react'
import { ScriptEditor } from '@/components/ScriptEditor'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { apiClient } from '@/lib/api'
import { User, WhoAmIResponse } from '@/types/api'

declare global {
  interface Window {
    google: any;
  }
}

export default function Home() {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [googleLoaded, setGoogleLoaded] = useState(false)
  const [authError, setAuthError] = useState<string | null>(null)

  useEffect(() => {
    checkAuth()
    loadGoogleScript()
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
      initializeGoogleSignIn()
    }
    document.head.appendChild(script)
  }

  const initializeGoogleSignIn = () => {
    if (window.google && process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID) {
      window.google.accounts.id.initialize({
        client_id: process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID,
        callback: handleGoogleCallback,
      })
    } else {
      console.error('Google Client ID not configured')
    }
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

  const handleGoogleCallback = async (response: any) => {
    try {
      const authResponse = await apiClient.authenticateWithGoogle(response.credential)
      // Token is now stored in httpOnly cookie by the server
      setUser(authResponse.user)
    } catch (error) {
      if (process.env.NODE_ENV === 'development') {
        console.error('Google auth failed')
      }
      // Use proper error UI instead of alert
      setAuthError('Authentication failed. Please try again.')
    }
  }

  const handleGoogleAuth = async (token: string) => {
    try {
      const authResponse = await apiClient.authenticateWithGoogle(token)
      // Token is now stored in httpOnly cookie by the server
      setUser(authResponse.user)
    } catch (error) {
      if (process.env.NODE_ENV === 'development') {
        console.error('Google auth failed')
      }
      // Use proper error UI instead of alert
      setAuthError('Authentication failed. Please try again.')
    }
  }

  const renderGoogleSignInButton = () => {
    if (!googleLoaded) return null

    return (
      <div
        id="google-signin-button"
        className="flex justify-center"
        ref={(element) => {
          if (element && window.google && !element.hasChildNodes()) {
            window.google.accounts.id.renderButton(element, {
              theme: 'outline',
              size: 'large',
              width: 250,
            })
          }
        }}
      />
    )
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
      setAuthError(null)
    }
  }

  if (isLoading) {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading...</p>
        </div>
      </div>
    )
  }

  if (!user) {
    return (
      <div className="h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
        <div className="max-w-md w-full mx-4">
          <div className="bg-white rounded-lg shadow-lg p-8 text-center">
            <h1 className="text-2xl font-bold mb-2">Script Improver</h1>
            <p className="text-muted-foreground mb-6">
              AI-powered script improvement with reference matching
            </p>
            
            <div className="space-y-4">
              {authError && (
                <div className="bg-red-50 border border-red-200 rounded-md p-3 text-sm text-red-700">
                  {authError}
                </div>
              )}

              {renderGoogleSignInButton()}

              <p className="text-xs text-muted-foreground">
                Sign in to access the script improvement tool
              </p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <header className="border-b bg-white px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h1 className="text-xl font-semibold">Script Improver</h1>
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
      </header>

      {/* Main Content */}
      <main className="flex-1">
        <ErrorBoundary>
          <ScriptEditor />
        </ErrorBoundary>
      </main>
    </div>
  )
}
