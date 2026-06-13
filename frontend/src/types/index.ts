// User types
export interface User {
  id: number
  username: string
  email: string
  is_admin: boolean
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
  position: number
  feed_count: number
  unread_count: number
}

// Feed types
export type FeedBrowserEngine = 'http' | 'playwright' | 'cloakbrowser'
export type FeedProxyMode = 'none' | 'single' | 'pool'
export type ProxyProtocol = 'http' | 'https' | 'socks4' | 'socks5' | 'socks5h'
export type TranslateMethod = 'none' | 'ai' | 'google' | 'argos'

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
  source_language: string | null
  target_language: string | null
  translate_method: TranslateMethod
  use_playwright: boolean
  browser_engine: FeedBrowserEngine
  proxy_enabled: boolean
  proxy_url: string | null
  proxy_mode: FeedProxyMode
  proxy_pool_country: string | null
  proxy_pool_protocol: ProxyProtocol | null
  position: number
}

export interface ProxyPoolEntry {
  id: number
  protocol: ProxyProtocol
  host: string
  port: number
  username: string | null
  password: string | null
  country: string | null
  source_format: string
  proxy_url: string
  is_active: boolean
  fail_count: number
  last_used_at: string | null
  last_tested_at: string | null
  last_latency_ms: number | null
  last_error: string | null
  created_at: string
  updated_at: string | null
}

export interface ProxyPoolGroups {
  countries: string[]
  protocols: ProxyProtocol[]
}

export interface ProxyPoolImportResult {
  imported: number
  skipped: number
  errors: string[]
  items: ProxyPoolEntry[]
}

export interface ProxyPoolTestItem {
  id: number
  success: boolean
  latency_ms: number | null
  error: string | null
  is_active: boolean
  fail_count: number
}

export interface ProxyPoolTestResult {
  total: number
  success: number
  failed: number
  results: ProxyPoolTestItem[]
}

export interface GoogleTranslateKey {
  id: number
  name: string
  masked_api_key: string
  is_active: boolean
  position: number
  limit_days: number | null
  limit_articles: number | null
  limit_characters: number | null
  usage_started_at: string | null
  usage_article_count: number
  usage_character_count: number
  last_used_at: string | null
  last_error: string | null
  fail_count: number
  is_exhausted: boolean
  created_at: string
  updated_at: string | null
}

export interface ArgosPackageInfo {
  source_language: string
  source_name: string | null
  target_language: string
  target_name: string | null
  package_version: string | null
  argos_version: string | null
  package_type: string
  installed: boolean
}

export interface ArgosPackagesResponse {
  installed: ArgosPackageInfo[]
  available: ArgosPackageInfo[]
  available_error: string | null
}

export interface ArgosPackageTestResult {
  success: boolean
  message: string
  translation: string | null
}

export interface ArgosTranslationLog {
  id: number
  article_id: number | null
  feed_id: number | null
  feed_title: string | null
  article_title: string | null
  source_language: string
  target_language: string
  status: 'translating' | 'completed' | 'failed'
  title_chars: number
  content_chars: number
  duration_ms: number | null
  error: string | null
  started_at: string
  completed_at: string | null
}

export interface ArgosTranslationLogsResponse {
  items: ArgosTranslationLog[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

// Keyword subscription types
export interface KeywordSubscription {
  id: number
  name: string
  keyword: string
  is_active: boolean
  match_title: boolean
  match_content: boolean
  match_author: boolean
  match_feed_title: boolean
  position: number
  article_count: number
  unread_count: number
  created_at: string
  updated_at: string | null
}

export interface KeywordSubscriptionCount {
  id: number
  article_count: number
  unread_count: number
}

// Article types
export type TranslationStatus = 'none' | 'queued' | 'translating' | 'completed' | 'failed'

export interface Article {
  id: number
  feed_id: number
  feed_title: string | null
  title: string
  link: string
  content: string | null
  full_content: string | null
  summary: string | null
  translation: string | null
  translation_status: TranslationStatus
  translation_error: string | null
  translation_started_at: string | null
  translation_completed_at: string | null
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
  user_id: number
  feed_id: number | null
  name: string
  target_url: string
  rule_type: 'general' | 'telegram'
  cookies: string | null
  list_selector: string
  title_selector: string
  link_selector: string | null
  content_selector: string | null
  date_selector: string | null
  fetch_interval: number
  use_playwright: boolean
  auto_translate: boolean
  auto_summarize: boolean
  source_language: string | null
  target_language: string | null
  translate_method: TranslateMethod
  is_active: boolean
  category_id: number | null
  last_fetched_at: string | null
  last_error: string | null
  error_count: number
  created_at: string
  updated_at: string | null
}

// Pagination
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

// Recommended Feed types
export interface RecommendedFeed {
  id: number
  url: string
  title: string
  description: string | null
  icon_url: string | null
  categories: string
  is_active: boolean
  subscriber_count: number
  is_subscribed: boolean
}
