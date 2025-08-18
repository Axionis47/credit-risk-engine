'use client'

import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import { ExternalLink, MessageCircle, TrendingUp, Star, Heart, ArrowLeft } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { apiClient } from '@/lib/api'
import { User, SavedIdea } from '@/types/api'
import { formatScore, formatTimeAgo, getSubredditColor } from '@/lib/utils'

export default function AcceptedPage() {
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

  // Fetch accepted ideas
  const { data: acceptedData, isLoading: isLoadingAccepted, error } = useQuery({
    queryKey: ['accepted-ideas'],
    queryFn: () => apiClient.getAcceptedIdeas(),
    enabled: !!user,
    refetchOnWindowFocus: false,
  })

  const handleSignOut = () => {
    localStorage.removeItem('access_token')
    setUser(null)
  }

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading...</p>
        </div>
      </div>
    )
  }

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-muted-foreground mb-4">Please sign in to view your accepted ideas</p>
          <Link href="/">
            <Button>Go to Home</Button>
          </Link>
        </div>
      </div>
    )
  }

  const savedIdeas = acceptedData?.success ? acceptedData.data?.saved || [] : []
  const superlikedIdeas = acceptedData?.success ? acceptedData.data?.superliked || [] : []
  const totalCount = savedIdeas.length + superlikedIdeas.length

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-6">
            <Link href="/" className="flex items-center gap-2 text-muted-foreground hover:text-foreground">
              <ArrowLeft className="w-4 h-4" />
              Back to Deck
            </Link>
            <h1 className="text-xl font-semibold flex items-center gap-2">
              🎯 Idea Hunter
            </h1>
            <nav className="flex items-center gap-4">
              <Link 
                href="/" 
                className="text-sm text-muted-foreground hover:text-foreground"
              >
                Deck
              </Link>
              <span className="text-sm font-medium text-primary border-b-2 border-primary pb-1">
                Accepted
              </span>
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
      <main className="max-w-4xl mx-auto px-6 py-8">
        <div className="text-center mb-8">
          <h2 className="text-2xl font-bold mb-2">Your Accepted Ideas</h2>
          <p className="text-muted-foreground">
            {totalCount} ideas saved for future reference
          </p>
        </div>

        {isLoadingAccepted ? (
          <div className="flex items-center justify-center h-64">
            <div className="text-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
              <p className="text-muted-foreground">Loading your ideas...</p>
            </div>
          </div>
        ) : error ? (
          <div className="flex items-center justify-center h-64">
            <div className="text-center">
              <p className="text-red-600 mb-4">Failed to load accepted ideas</p>
              <Button onClick={() => window.location.reload()} variant="outline">
                Try Again
              </Button>
            </div>
          </div>
        ) : totalCount === 0 ? (
          <div className="flex items-center justify-center h-64">
            <div className="text-center max-w-md">
              <div className="text-6xl mb-4">💡</div>
              <h3 className="text-xl font-semibold mb-2">No ideas saved yet</h3>
              <p className="text-muted-foreground mb-4">
                Start swiping through ideas on the deck to build your collection of saved content ideas.
              </p>
              <Link href="/">
                <Button>
                  Go to Deck
                </Button>
              </Link>
            </div>
          </div>
        ) : (
          <div className="space-y-8">
            {/* Superliked Ideas */}
            {superlikedIdeas.length > 0 && (
              <section>
                <div className="flex items-center gap-2 mb-4">
                  <Star className="w-5 h-5 text-yellow-500" />
                  <h3 className="text-lg font-semibold">Superliked ({superlikedIdeas.length})</h3>
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                  {superlikedIdeas.map((idea) => (
                    <IdeaItem key={idea.idea_id} idea={idea} type="superlike" />
                  ))}
                </div>
              </section>
            )}

            {/* Saved Ideas */}
            {savedIdeas.length > 0 && (
              <section>
                <div className="flex items-center gap-2 mb-4">
                  <Heart className="w-5 h-5 text-green-500" />
                  <h3 className="text-lg font-semibold">Saved ({savedIdeas.length})</h3>
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                  {savedIdeas.map((idea) => (
                    <IdeaItem key={idea.idea_id} idea={idea} type="save" />
                  ))}
                </div>
              </section>
            )}
          </div>
        )}
      </main>
    </div>
  )
}

function IdeaItem({ idea, type }: { idea: SavedIdea; type: 'save' | 'superlike' }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 hover:shadow-md transition-shadow">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <Badge className={getSubredditColor(idea.subreddit)}>
          r/{idea.subreddit}
        </Badge>
        <div className="flex items-center gap-2">
          {type === 'superlike' ? (
            <Star className="w-4 h-4 text-yellow-500" />
          ) : (
            <Heart className="w-4 h-4 text-green-500" />
          )}
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <div className="flex items-center gap-1">
              <TrendingUp className="w-3 h-3" />
              {formatScore(idea.score)}
            </div>
            <div className="flex items-center gap-1">
              <MessageCircle className="w-3 h-3" />
              {idea.num_comments}
            </div>
          </div>
        </div>
      </div>

      {/* Title */}
      <h4 className="font-medium text-sm leading-tight mb-2">
        {idea.title}
      </h4>

      {/* Snippet */}
      <p className="text-sm text-gray-600 leading-relaxed mb-3 line-clamp-3">
        {idea.snippet}
      </p>

      {/* Footer */}
      <div className="flex items-center justify-between text-xs text-gray-500">
        <span>{formatTimeAgo(idea.created_at)}</span>
        <a
          href={idea.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1 text-blue-600 hover:text-blue-800"
        >
          <ExternalLink className="w-3 h-3" />
          Reddit
        </a>
      </div>

      {/* Notes */}
      {idea.notes && (
        <div className="mt-3 pt-3 border-t">
          <p className="text-xs text-gray-600 italic">
            Note: {idea.notes}
          </p>
        </div>
      )}
    </div>
  )
}
