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

export interface PerformanceMetrics {
  views: number
  ctr?: number
  avg_view_duration_s?: number
  retention_30s?: number
}

export interface ReferenceScript {
  video_id: string
  body: string
  duration_seconds: number
  performance: PerformanceMetrics
  similarity_score: number
  performance_score: number
  combined_score: number
}

export interface RetrieveResponse {
  ref: ReferenceScript | null
  alternates: ReferenceScript[]
  total_candidates: number
  search_time_ms: number
  reason?: string
}

export interface CoherenceScore {
  score: number
  passed: boolean
  notes: string
}

export interface ImprovedScript {
  title: string
  hook: string
  body: string
  word_count: number
  coherence: CoherenceScore
  diff_summary?: string
  style_principles: string[]
}

export interface ImproveResponse {
  result: ImprovedScript
  warnings: string[]
  processing_time_ms: number
  tuner_passes: number
}

export interface ApiResponse<T> {
  success: boolean
  data?: T
  error?: string
  trace_id?: string
}
