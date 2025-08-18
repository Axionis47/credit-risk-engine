export interface User {
  id: string
  email: string
  name: string
  picture?: string
  verified_email: boolean
}

export interface AuthResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: User
}

export interface Idea {
  idea_id: string
  title: string
  snippet: string
  source_url: string
  subreddit: string
  score: number
  num_comments: number
  created_at: string
  fetched_at: string
}

export interface SavedIdea extends Idea {
  saved_at?: string
  superliked_at?: string
  notes?: string
}

export interface DeckResponse {
  ideas: Idea[]
  has_more: boolean
  total_available: number
}

export interface AcceptedIdeasResponse {
  saved: SavedIdea[]
  superliked: SavedIdea[]
  total_count: number
}

export interface ApiResponse<T> {
  success: boolean
  data?: T
  error?: string
  trace_id?: string
}

export type FeedbackType = 'reject' | 'save' | 'superlike'
