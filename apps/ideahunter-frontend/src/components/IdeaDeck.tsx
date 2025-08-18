'use client'

import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { RefreshCw, Loader2 } from 'lucide-react'
import { IdeaCard } from './IdeaCard'
import { Button } from '@/components/ui/button'
import { apiClient } from '@/lib/api'
import { Idea, FeedbackType } from '@/types/api'

export function IdeaDeck() {
  const [currentIdeas, setCurrentIdeas] = useState<Idea[]>([])
  const queryClient = useQueryClient()

  // Fetch ideas deck
  const { data: deckData, isLoading, error, refetch } = useQuery({
    queryKey: ['ideas-deck'],
    queryFn: () => apiClient.getIdeasDeck(20),
    refetchOnWindowFocus: false,
  })

  // Submit feedback mutation
  const feedbackMutation = useMutation({
    mutationFn: ({ ideaId, feedbackType }: { ideaId: string; feedbackType: FeedbackType }) =>
      apiClient.submitIdeaFeedback(ideaId, feedbackType),
    onSuccess: () => {
      // Remove the top card after successful feedback
      setCurrentIdeas(prev => prev.slice(1))
    },
    onError: (error) => {
      console.error('Feedback submission failed:', error)
      // Optionally show error toast
    }
  })

  // Update current ideas when deck data changes
  useEffect(() => {
    if (deckData?.success && deckData.data?.ideas) {
      setCurrentIdeas(deckData.data.ideas)
    }
  }, [deckData])

  const handleSwipe = (ideaId: string, direction: FeedbackType) => {
    feedbackMutation.mutate({ ideaId, feedbackType: direction })
  }

  const handleRefresh = () => {
    refetch()
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin mx-auto mb-4 text-primary" />
          <p className="text-muted-foreground">Loading ideas...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <p className="text-red-600 mb-4">Failed to load ideas</p>
          <Button onClick={handleRefresh} variant="outline">
            <RefreshCw className="w-4 h-4 mr-2" />
            Try Again
          </Button>
        </div>
      </div>
    )
  }

  if (!currentIdeas.length) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center max-w-md">
          <div className="text-6xl mb-4">🎯</div>
          <h3 className="text-xl font-semibold mb-2">No more ideas!</h3>
          <p className="text-muted-foreground mb-4">
            You've gone through all available ideas. Check back later for more, or ask an admin to sync from Reddit.
          </p>
          <Button onClick={handleRefresh} variant="outline">
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-md mx-auto">
      {/* Card Stack */}
      <div className="relative h-96 card-stack">
        {currentIdeas.slice(0, 3).map((idea, index) => (
          <IdeaCard
            key={idea.idea_id}
            idea={idea}
            onSwipe={handleSwipe}
            isTop={index === 0}
          />
        ))}
      </div>

      {/* Instructions */}
      <div className="mt-6 text-center text-sm text-muted-foreground">
        <p className="mb-2">
          Swipe left to reject, right to save, or use the buttons
        </p>
        <div className="flex items-center justify-center gap-4">
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 bg-red-500 rounded-full"></div>
            <span>Reject</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 bg-yellow-500 rounded-full"></div>
            <span>Superlike</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 bg-green-500 rounded-full"></div>
            <span>Save</span>
          </div>
        </div>
      </div>

      {/* Stats */}
      {deckData?.success && deckData.data && (
        <div className="mt-4 text-center text-sm text-muted-foreground">
          <p>
            {currentIdeas.length} of {deckData.data.total_available} ideas remaining
          </p>
        </div>
      )}
    </div>
  )
}
