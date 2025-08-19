'use client'

import { useState, useEffect } from 'react'
import { motion, useMotionValue, useTransform, PanInfo } from 'framer-motion'
import { ExternalLink, MessageCircle, TrendingUp, X, Heart, Star } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Idea, FeedbackType } from '@/types/api'
import { formatScore, formatTimeAgo, truncateText, getSubredditColor, sanitizeUrl } from '@/lib/utils'

interface IdeaCardProps {
  idea: Idea
  onSwipe: (ideaId: string, direction: FeedbackType) => void
  isTop?: boolean
}

export function IdeaCard({ idea, onSwipe, isTop = false }: IdeaCardProps) {
  const [exitX, setExitX] = useState(0)
  const x = useMotionValue(0)
  const rotate = useTransform(x, [-200, 200], [-25, 25])
  const opacity = useTransform(x, [-200, -150, 0, 150, 200], [0, 1, 1, 1, 0])

  // Cleanup motion values on unmount to prevent memory leaks
  useEffect(() => {
    return () => {
      x.destroy()
      rotate.destroy()
      opacity.destroy()
    }
  }, [x, rotate, opacity])

  const handleDragEnd = (event: any, info: PanInfo) => {
    const threshold = 100
    
    if (info.offset.x > threshold) {
      // Swipe right - Save
      setExitX(200)
      onSwipe(idea.idea_id, 'save')
    } else if (info.offset.x < -threshold) {
      // Swipe left - Reject
      setExitX(-200)
      onSwipe(idea.idea_id, 'reject')
    } else {
      // Snap back
      x.set(0)
    }
  }

  const handleButtonAction = (action: FeedbackType) => {
    if (action === 'reject') {
      setExitX(-200)
    } else if (action === 'save') {
      setExitX(200)
    } else if (action === 'superlike') {
      setExitX(0) // Superlike goes up
    }
    onSwipe(idea.idea_id, action)
  }

  return (
    <motion.div
      className="absolute inset-0 idea-card"
      style={{ x, rotate, opacity }}
      drag={isTop ? "x" : false}
      dragConstraints={{ left: 0, right: 0 }}
      onDragEnd={handleDragEnd}
      animate={exitX !== 0 ? { x: exitX, opacity: 0 } : {}}
      transition={{ duration: 0.3 }}
    >
      <div className="bg-white rounded-xl shadow-lg border border-gray-200 h-full flex flex-col overflow-hidden">
        {/* Header */}
        <div className="p-4 border-b bg-gray-50">
          <div className="flex items-center justify-between mb-2">
            <Badge className={getSubredditColor(idea.subreddit)}>
              r/{idea.subreddit}
            </Badge>
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <div className="flex items-center gap-1">
                <TrendingUp className="w-4 h-4" />
                {formatScore(idea.score)}
              </div>
              <div className="flex items-center gap-1">
                <MessageCircle className="w-4 h-4" />
                {idea.num_comments}
              </div>
            </div>
          </div>
          <h3 className="font-semibold text-lg leading-tight">
            {truncateText(idea.title, 100)}
          </h3>
          <p className="text-sm text-gray-500 mt-1">
            {formatTimeAgo(idea.created_at)}
          </p>
        </div>

        {/* Content */}
        <div className="flex-1 p-4 overflow-y-auto">
          <p className="text-gray-700 leading-relaxed">
            {truncateText(idea.snippet, 400)}
          </p>
        </div>

        {/* Footer */}
        <div className="p-4 border-t bg-gray-50">
          <div className="flex items-center justify-between">
            <a
              href={sanitizeUrl(idea.source_url)}
              target="_blank"
              rel="noopener noreferrer nofollow"
              className="flex items-center gap-1 text-sm text-blue-600 hover:text-blue-800"
              onClick={(e) => {
                // Additional safety check
                const url = sanitizeUrl(idea.source_url)
                if (!url || (!url.startsWith('https://reddit.com') && !url.startsWith('https://www.reddit.com'))) {
                  e.preventDefault()
                  alert('Invalid or unsafe URL')
                }
              }}
            >
              <ExternalLink className="w-4 h-4" />
              View on Reddit
            </a>
            
            {isTop && (
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleButtonAction('reject')}
                  className="text-red-600 hover:text-red-700 hover:bg-red-50"
                >
                  <X className="w-4 h-4" />
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleButtonAction('superlike')}
                  className="text-yellow-600 hover:text-yellow-700 hover:bg-yellow-50"
                >
                  <Star className="w-4 h-4" />
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleButtonAction('save')}
                  className="text-green-600 hover:text-green-700 hover:bg-green-50"
                >
                  <Heart className="w-4 h-4" />
                </Button>
              </div>
            )}
          </div>
        </div>

        {/* Swipe indicators */}
        {isTop && (
          <>
            <motion.div
              className="absolute top-4 left-4 bg-red-500 text-white px-3 py-1 rounded-full font-bold text-sm"
              style={{ opacity: useTransform(x, [-150, -50], [1, 0]) }}
            >
              REJECT
            </motion.div>
            <motion.div
              className="absolute top-4 right-4 bg-green-500 text-white px-3 py-1 rounded-full font-bold text-sm"
              style={{ opacity: useTransform(x, [50, 150], [1, 0]) }}
            >
              SAVE
            </motion.div>
          </>
        )}
      </div>
    </motion.div>
  )
}
