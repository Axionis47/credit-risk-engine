'use client'

import { useEffect, useState } from 'react'
import { ScriptEditor } from '@/components/ScriptEditor'
import { apiClient } from '@/lib/api'
import { User } from '@/types/api'

export default function Home() {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    checkAuth()
  }, [])

  const checkAuth = async () => {
    try {
      const response = await apiClient.whoami()
      if (response.authenticated && response.user) {
        setUser(response.user)
      }
    } catch (error) {
      console.error('Auth check failed:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleGoogleAuth = async (token: string) => {
    try {
      const authResponse = await apiClient.authenticateWithGoogle(token)
      localStorage.setItem('access_token', authResponse.access_token)
      setUser(authResponse.user)
    } catch (error) {
      console.error('Google auth failed:', error)
      alert('Authentication failed. Please try again.')
    }
  }

  const handleSignOut = () => {
    localStorage.removeItem('access_token')
    setUser(null)
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
              <div 
                id="google-signin-button"
                className="flex justify-center"
              >
                {/* Google Sign-In button will be rendered here */}
                <button
                  onClick={() => {
                    // This would integrate with Google Sign-In
                    // For demo purposes, we'll simulate auth
                    const mockToken = 'mock-google-token'
                    handleGoogleAuth(mockToken)
                  }}
                  className="bg-white border border-gray-300 rounded-lg px-6 py-3 text-sm font-medium text-gray-700 hover:bg-gray-50 flex items-center gap-3"
                >
                  <svg className="w-5 h-5" viewBox="0 0 24 24">
                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                  </svg>
                  Continue with Google
                </button>
              </div>
              
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
        <ScriptEditor />
      </main>
    </div>
  )
}
