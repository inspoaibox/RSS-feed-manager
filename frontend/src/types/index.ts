// User types
export interface User {
  id: number
  username: string
  email: string
  created_at: string
}

// Auth types
export interface LoginRequest {
  username: string
  password: string
}

export interface RegisterRequest {
  username: string
  email: string
  password: string
}

export interface AuthResponse {
  access_token: string
  refresh_token: string
  user: User
}

// Category types
export interface Category {
  id: number
  name: string
  feed_count: number
  unread_count: number
}

// Feed types
export interface Feed {
  id: number
  url: string
  title: string
  description: string | null
  site_url: string | null
  icon_url: string | null
  category_id: number | null
  unread_count: number
  article_count: number
  auto_translate: boolean
  auto_summarize: boolean
  fetch_interval: number
  last_fetched_at: string | null
  is_active: boolean
  target_language: string | null
  use_playwright: boolean
}

// Article types
export interface Article {
  id: number
  feed_id: number
  title: string
  link: string
  content: string | null
  full_content: string | null
  summary: string | null
  translation: string | null
  author: string | null
  published_at: string
  is_read: boolean
  is_favorite: boolean
}

// AI types
export interface AIProvider {
  id: number
  name: string
  type: 'openai' | 'gemini' | 'openai_compatible'
  base_url: string | null
  is_active: boolean
}

export interface AIModel {
  id: number
  provider_id: number
  model_id: string
  name: string
  is_default: boolean
}

// Custom Rule types
export interface CustomRule {
  id: number
  name: string
  target_url: string
  list_selector: string
  title_selector: string
  link_selector: string
  content_selector: string | null
  date_selector: string | null
  fetch_interval: number
  is_active: boolean
  category_id: number | null
}

// Pagination
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}
