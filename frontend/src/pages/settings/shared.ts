import type { Feed,FeedBrowserEngine,FeedProxyMode,ProxyProtocol,TranslateMethod } from '@/types'

export type Tab = 'feeds' | 'categories' | 'ai' | 'rules' | 'proxies' | 'backup' | 'appearance' | 'notifications' | 'system'
export type AIProviderFormState = {
  name: string
  type: 'openai' | 'gemini' | 'openai_compatible'
  api_key: string
  base_url: string
}
export type AIModelFormState = {
  model_id: string
  name: string
}

export const feedBrowserEngineLabels: Record<FeedBrowserEngine, string> = {
  http: '普通抓取',
  playwright: 'Playwright',
  cloakbrowser: 'CloakBrowser',
}

export const createEmptyAIProviderForm = (): AIProviderFormState => ({
  name: '',
  type: 'openai',
  api_key: '',
  base_url: '',
})

export const createEmptyAIModelForm = (): AIModelFormState => ({
  model_id: '',
  name: '',
})

export const proxyProtocols: ProxyProtocol[] = ['http', 'https', 'socks4', 'socks5', 'socks5h']
export const translationSourceLanguages = [
  { value: 'en', label: 'English' },
  { value: 'zh', label: '中文' },
  { value: 'ja', label: '日本語' },
  { value: 'ko', label: '한국어' },
  { value: 'fr', label: 'Français' },
  { value: 'de', label: 'Deutsch' },
  { value: 'es', label: 'Español' },
  { value: 'ru', label: 'Русский' },
  { value: 'pt', label: 'Português' },
  { value: 'it', label: 'Italiano' },
  { value: 'ar', label: 'العربية' },
  { value: 'nl', label: 'Nederlands' },
  { value: 'tr', label: 'Türkçe' },
  { value: 'vi', label: 'Tiếng Việt' },
  { value: 'id', label: 'Bahasa Indonesia' },
  { value: 'th', label: 'ไทย' },
  { value: 'hi', label: 'हिन्दी' },
  { value: 'fa', label: 'فارسی' },
  { value: 'pl', label: 'Polski' },
  { value: 'uk', label: 'Українська' },
  { value: 'sv', label: 'Svenska' },
  { value: 'ms', label: 'Bahasa Melayu' },
]

export const getTranslationLanguageLabel = (value: string | null | undefined) => {
  if (!value) return ''
  return translationSourceLanguages.find((language) => language.value === value)?.label || value
}

export const sourceLanguageTranslateMethods = new Set<TranslateMethod>(['argos', 'mc_translation'])
export const activeTranslateMethods: TranslateMethod[] = ['ai', 'google', 'argos', 'mc_translation']
export const usesSourceLanguage = (method: TranslateMethod) => sourceLanguageTranslateMethods.has(method)

export type ProxyUpdatePayload = {
  raw?: string
  default_protocol?: ProxyProtocol
  country?: string | null
  is_active?: boolean
  fail_count?: number
}

export type ProxyEditState = {
  raw: string
  default_protocol: ProxyProtocol
  country: string
  is_active: boolean
  fail_count: string
}

export const resolveFeedBrowserEngine = (feed: Feed): FeedBrowserEngine => {
  return feed.browser_engine || (feed.use_playwright ? 'playwright' : 'http')
}

export const resolveFeedProxyMode = (feed: Feed): FeedProxyMode => {
  return feed.proxy_mode || (feed.proxy_enabled ? 'single' : 'none')
}


export const formatDurationMs = (durationMs: number | null) => {
  if (durationMs === null || durationMs === undefined) return '-'
  if (durationMs < 1000) return `${durationMs} ms`
  return `${(durationMs / 1000).toFixed(2)} s`
}

export const formatDateTime = (value: string | null | undefined) => {
  return value ? new Date(value).toLocaleString('zh-CN') : '-'
}

export const getArgosLogStatusLabel = (status: string) => {
  if (status === 'completed') return '完成'
  if (status === 'failed') return '失败'
  if (status === 'translating') return '翻译中'
  return status
}

export const getArgosLogStatusClass = (status: string) => {
  if (status === 'completed') return 'text-emerald-700 dark:text-emerald-300'
  if (status === 'failed') return 'text-red-700 dark:text-red-300'
  return 'text-blue-700 dark:text-blue-300'
}
