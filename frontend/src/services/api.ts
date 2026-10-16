import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { useAuthStore } from '@/stores/authStore'

const api = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
})

let refreshPromise: Promise<string> | null = null

export const refreshAccessToken = (): Promise<string> => {
  if (!refreshPromise) {
    const epoch = useAuthStore.getState().authEpoch
    refreshPromise = axios.post<{ access_token: string }>(
      '/api/v1/auth/refresh', {}, { withCredentials: true },
    ).then(({ data }) => {
      if (useAuthStore.getState().authEpoch !== epoch) throw new Error('Session changed')
      useAuthStore.getState().setAccessToken(data.access_token)
      return data.access_token
    }).finally(() => { refreshPromise = null })
  }
  return refreshPromise
}

api.interceptors.request.use((config) => {
  const authConfig = config as InternalAxiosRequestConfig & { _authEpoch?: number }
  authConfig._authEpoch ??= useAuthStore.getState().authEpoch
  const token = useAuthStore.getState().accessToken
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use((response) => response, async (error: AxiosError) => {
  const request = error.config as (InternalAxiosRequestConfig & { _retry?: boolean; _authEpoch?: number }) | undefined
  const authRoute = request?.url?.startsWith('/auth/') && request.url !== '/auth/me'
  if (!request || error.response?.status !== 401 || request._retry || authRoute ||
      request._authEpoch !== useAuthStore.getState().authEpoch) {
    return Promise.reject(error)
  }
  request._retry = true
  try {
    const token = await refreshAccessToken()
    request.headers.Authorization = `Bearer ${token}`
    return api(request)
  } catch (refreshError) {
    useAuthStore.getState().clearAuth()
    return Promise.reject(refreshError)
  }
})

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
    current_batch?: number
    total_batches?: number
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
