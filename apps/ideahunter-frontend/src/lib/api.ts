import { ApiResponse, AuthResponse, DeckResponse, AcceptedIdeasResponse, FeedbackType, WhoAmIResponse } from '@/types/api'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

class ApiClient {
  private getAuthHeaders(): HeadersInit {
    const token = localStorage.getItem('access_token')
    return token ? { Authorization: `Bearer ${token}` } : {}
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    const url = `${API_BASE_URL}${endpoint}`
    
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeaders(),
        ...options.headers,
      },
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || `HTTP ${response.status}`)
    }

    return response.json()
  }

  async authenticateWithGoogle(token: string): Promise<AuthResponse> {
    const response = await fetch(`${API_BASE_URL}/api/oauth/google`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token }),
    })

    if (!response.ok) {
      throw new Error('Authentication failed')
    }

    return response.json()
  }

  async whoami(): Promise<WhoAmIResponse> {
    const response = await fetch(`${API_BASE_URL}/whoami`, {
      headers: this.getAuthHeaders(),
    })

    if (!response.ok) {
      return { authenticated: false }
    }

    const data = await response.json()
    return { authenticated: true, user: data.user }
  }

  async getIdeasDeck(limit: number = 20): Promise<ApiResponse<DeckResponse>> {
    return this.request(`/api/ideas/deck?limit=${limit}`)
  }

  async submitIdeaFeedback(ideaId: string, feedbackType: FeedbackType, notes?: string): Promise<ApiResponse<any>> {
    return this.request('/api/ideas/feedback', {
      method: 'POST',
      body: JSON.stringify({
        idea_id: ideaId,
        feedback_type: feedbackType,
        notes,
      }),
    })
  }

  async getAcceptedIdeas(): Promise<ApiResponse<AcceptedIdeasResponse>> {
    return this.request('/api/ideas/accepted')
  }

  async syncRedditIdeas(): Promise<ApiResponse<any>> {
    return this.request('/api/ideas/sync', {
      method: 'POST',
      body: JSON.stringify({}),
    })
  }
}

export const apiClient = new ApiClient()
