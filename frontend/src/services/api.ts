import axios from 'axios'
import { useAuthStore } from '@/stores/authStore'

const api = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
})

// Flag to prevent multiple refresh attempts
let isRefreshing = false
let failedQueue: Array<{
  resolve: (token: string) => void
  reject: (error: any) => void
}> = []

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error)
    } else {
      prom.resolve(token!)
    }
  })
  failedQueue = []
}

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().accessToken
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor to handle auth errors and auto-refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    // If 401 and not already retrying
    if (error.response?.status === 401 && !originalRequest._retry) {
      // Don't retry refresh token requests
      if (originalRequest.url?.includes('/auth/refresh')) {
        useAuthStore.getState().clearAuth()
        return Promise.reject(error)
      }

      if (isRefreshing) {
        // Wait for the refresh to complete
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        })
          .then((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`
            return api(originalRequest)
          })
          .catch((err) => Promise.reject(err))
      }

      originalRequest._retry = true
      isRefreshing = true

      const refreshToken = useAuthStore.getState().refreshToken

      if (!refreshToken) {
        useAuthStore.getState().clearAuth()
        isRefreshing = false
        return Promise.reject(error)
      }

      try {
        const response = await axios.post('/api/v1/auth/refresh', {
          refresh_token: refreshToken,
        })

        const { access_token, refresh_token: newRefreshToken } = response.data
        const currentUser = useAuthStore.getState().user

        if (currentUser) {
          useAuthStore.getState().setAuth(currentUser, access_token, newRefreshToken)
        }

        processQueue(null, access_token)

        originalRequest.headers.Authorization = `Bearer ${access_token}`
        return api(originalRequest)
      } catch (refreshError) {
        processQueue(refreshError, null)
        useAuthStore.getState().clearAuth()
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    return Promise.reject(error)
  }
)

// ============ Content Analysis API ============

export interface AnalyzeRequest {
  query: string
  page?: number
  page_size?: number
  use_semantic_search?: boolean
}

export interface ArticleResult {
  id: number
  title: string
  feed_title: string
  link: string | null
  published_at: string | null
  relevance_score: number
  snippet: string
}

export interface AnalyzeResponse {
  query: string
  analysis: string | null
  articles: ArticleResult[]
  total: number
  page: number
  page_size: number
  search_type: string
}

export interface QueryHistoryItem {
  id: number
  query: string
  created_at: string
}

export interface QueryHistoryResponse {
  queries: QueryHistoryItem[]
}

export const analyzeContent = async (data: AnalyzeRequest): Promise<AnalyzeResponse> => {
  const response = await api.post('/ai/analyze', data)
  return response.data
}

export const getQueryHistory = async (): Promise<QueryHistoryResponse> => {
  const response = await api.get('/ai/history')
  return response.data
}

export const deleteQueryHistory = async (queryId: number): Promise<void> => {
  await api.delete(`/ai/history/${queryId}`)
}

// Embedding status and generation
export interface EmbeddingStatus {
  total: number
  with_embedding: number
  without_embedding: number
  percentage: number
}

export const getEmbeddingStatus = async (): Promise<EmbeddingStatus> => {
  const response = await api.get('/ai/embeddings/status')
  return response.data
}

export const generateEmbeddings = async (limit?: number): Promise<{ message: string; task_id: string | null }> => {
  const url = limit ? `/ai/embeddings/generate?limit=${limit}` : '/ai/embeddings/generate'
  const response = await api.post(url)
  return response.data
}

// Task status and management
export interface TaskStatus {
  task_id: string
  status: 'PENDING' | 'STARTED' | 'PROGRESS' | 'SUCCESS' | 'FAILURE' | 'REVOKED'
  ready: boolean
  result?: {
    success: boolean
    processed?: number
    errors?: number
    total?: number
    cancelled?: boolean
    message?: string
    error?: string
  }
  error?: string
}

export interface TaskProgress {
  current_batch: number
  total_batches: number
  processed: number
  errors: number
  total: number
}

export const getEmbeddingTaskStatus = async (taskId: string): Promise<TaskStatus> => {
  const response = await api.get(`/ai/embeddings/task/${taskId}`)
  return response.data
}

export const cancelEmbeddingTask = async (taskId: string): Promise<{ task_id: string; message: string }> => {
  const response = await api.post(`/ai/embeddings/task/${taskId}/cancel`)
  return response.data
}

export interface ActiveTask {
  task_id: string
  status: string
  worker?: string
  started?: number
}

export const getActiveEmbeddingTasks = async (): Promise<{ tasks: ActiveTask[] }> => {
  const response = await api.get('/ai/embeddings/tasks')
  return response.data
}

export default api
