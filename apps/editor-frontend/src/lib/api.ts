import { ApiResponse, AuthResponse, RetrieveResponse, ImproveResponse, ReferenceScript, WhoAmIResponse } from '@/types/api'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL

if (!API_BASE_URL) {
  throw new Error('NEXT_PUBLIC_API_URL environment variable is required')
}

class ApiClient {
  private getAuthHeaders(): HeadersInit {
    // Use httpOnly cookies for security instead of localStorage
    return {}
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    const url = `${API_BASE_URL}${endpoint}`

    const response = await fetch(url, {
      ...options,
      credentials: 'include', // Include httpOnly cookies
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest', // CSRF protection
        ...this.getAuthHeaders(),
        ...options.headers,
      },
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      const errorMessage = errorData.detail || errorData.message || `HTTP ${response.status}`
      throw new Error(errorMessage)
    }

    return response.json()
  }

  async authenticateWithGoogle(token: string): Promise<AuthResponse> {
    const response = await fetch(`${API_BASE_URL}/api/oauth/google`, {
      method: 'POST',
      credentials: 'include', // Include cookies for secure token storage
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest' // CSRF protection
      },
      body: JSON.stringify({ token }),
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || 'Authentication failed')
    }

    return response.json()
  }

  async whoami(): Promise<WhoAmIResponse> {
    const response = await fetch(`${API_BASE_URL}/whoami`, {
      credentials: 'include', // Include httpOnly cookies
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        ...this.getAuthHeaders()
      },
    })

    if (!response.ok) {
      return { authenticated: false }
    }

    const data = await response.json()
    return { authenticated: true, user: data.user }
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
    // Always use gateway API for proper authentication and routing
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
