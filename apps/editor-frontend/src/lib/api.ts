import { ApiResponse, AuthResponse, RetrieveResponse, ImproveResponse, ReferenceScript } from '@/types/api'

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

  async whoami() {
    return this.request('/whoami')
  }

  async retrieveReference(draftBody: string): Promise<ApiResponse<RetrieveResponse>> {
    return this.request('/api/retrieve', {
      method: 'POST',
      body: JSON.stringify({ draft_body: draftBody }),
    })
  }

  async improveScript(
    draftBody: string,
    reference?: ReferenceScript,
    targetWordCount?: number,
    styleNotes?: string
  ): Promise<ApiResponse<ImproveResponse>> {
    return this.request('/api/improve', {
      method: 'POST',
      body: JSON.stringify({
        draft_body: draftBody,
        reference,
        target_word_count: targetWordCount,
        style_notes: styleNotes,
      }),
    })
  }
}

export const apiClient = new ApiClient()
