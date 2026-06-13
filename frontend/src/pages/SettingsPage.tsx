import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, Edit2, Check, X, Upload, Download, RefreshCw, FolderOpen, Languages, ChevronUp, ChevronDown, Search, Shield, Star, History } from 'lucide-react'
import api from '@/services/api'
import type { ArgosPackageInfo, ArgosPackagesResponse, ArgosPackageTestResult, ArgosTranslationLogsResponse, Category, Feed, AIProvider, AIModel, CustomRule, FeedBrowserEngine, FeedProxyMode, GoogleTranslateKey, ProxyPoolEntry, ProxyPoolGroups, ProxyPoolImportResult, ProxyPoolTestResult, ProxyProtocol, TranslateMethod } from '@/types'
import { useThemeStore, type ThemeColor } from '@/stores/themeStore'
import { useAuthStore } from '@/stores/authStore'
import { useSyncIntervals } from '@/hooks/useSyncIntervals'
import NotificationManagement from '@/components/NotificationManagement'

type Tab = 'feeds' | 'categories' | 'ai' | 'rules' | 'proxies' | 'backup' | 'appearance' | 'system'

const feedBrowserEngineLabels: Record<FeedBrowserEngine, string> = {
  http: '普通抓取',
  playwright: 'Playwright',
  cloakbrowser: 'CloakBrowser',
}

const proxyProtocols: ProxyProtocol[] = ['http', 'https', 'socks4', 'socks5', 'socks5h']
const translationSourceLanguages = [
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

const getTranslationLanguageLabel = (value: string | null | undefined) => {
  if (!value) return ''
  return translationSourceLanguages.find((language) => language.value === value)?.label || value
}

type ProxyUpdatePayload = {
  raw?: string
  default_protocol?: ProxyProtocol
  country?: string | null
  is_active?: boolean
  fail_count?: number
}

const resolveFeedBrowserEngine = (feed: Feed): FeedBrowserEngine => {
  return feed.browser_engine || (feed.use_playwright ? 'playwright' : 'http')
}

const resolveFeedProxyMode = (feed: Feed): FeedProxyMode => {
  return feed.proxy_mode || (feed.proxy_enabled ? 'single' : 'none')
}

const getApiErrorMessage = (error: unknown, fallback: string) => {
  const response = (error as { response?: { data?: { detail?: unknown } } } | null)?.response
  const detail = response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((item) => {
      if (item && typeof item === 'object' && 'msg' in item) {
        return String((item as { msg?: unknown }).msg)
      }
      return String(item)
    }).join(', ')
  }
  return typeof detail === 'string' ? detail : fallback
}

const formatDurationMs = (durationMs: number | null) => {
  if (durationMs === null || durationMs === undefined) return '-'
  if (durationMs < 1000) return `${durationMs} ms`
  return `${(durationMs / 1000).toFixed(2)} s`
}

const formatDateTime = (value: string | null | undefined) => {
  return value ? new Date(value).toLocaleString('zh-CN') : '-'
}

const getArgosLogStatusLabel = (status: string) => {
  if (status === 'completed') return '完成'
  if (status === 'failed') return '失败'
  if (status === 'translating') return '翻译中'
  return status
}

const getArgosLogStatusClass = (status: string) => {
  if (status === 'completed') return 'text-emerald-700 dark:text-emerald-300'
  if (status === 'failed') return 'text-red-700 dark:text-red-300'
  return 'text-blue-700 dark:text-blue-300'
}

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<Tab>('feeds')
  const user = useAuthStore((state) => state.user)
  const isAdmin = user?.is_admin ?? false

  const tabs = [
    { id: 'feeds', label: '订阅源' },
    { id: 'categories', label: '分类' },
    { id: 'ai', label: 'AI 设置' },
    { id: 'rules', label: '自定义规则' },
    { id: 'proxies', label: '代理池' },
    { id: 'backup', label: '备份恢复' },
    { id: 'appearance', label: '外观' },
    ...(isAdmin ? [{ id: 'system', label: '系统设置', icon: Shield }] : []),
  ]

  // Render tab content - only render active tab to reduce initial load
  const renderTabContent = () => {
    switch (activeTab) {
      case 'feeds':
        return <FeedsTab />
      case 'categories':
        return <CategoriesTab />
      case 'ai':
        return <AITab />
      case 'rules':
        return <RulesTab />
      case 'proxies':
        return <ProxyPoolTab />
      case 'backup':
        return <BackupTab />
      case 'appearance':
        return <AppearanceTab />
      case 'system':
        return isAdmin ? <SystemTab /> : null
      default:
        return null
    }
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <h1 className="text-2xl font-bold mb-6 dark:text-white">设置</h1>
      
      {/* Tabs */}
      <div className="flex border-b dark:border-gray-700 mb-6 flex-wrap">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as Tab)}
            className={`px-4 py-2 border-b-2 -mb-px flex items-center gap-1 ${
              activeTab === tab.id
                ? 'border-primary-500 text-primary-600 dark:text-primary-400'
                : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
            }`}
          >
            {tab.id === 'system' && <Shield className="w-4 h-4" />}
            {tab.label}
          </button>
        ))}
      </div>

      {renderTabContent()}
    </div>
  )
}

function FeedsTab() {
  const queryClient = useQueryClient()
  const { syncIntervals, defaultSyncInterval } = useSyncIntervals()
  const [showAddForm, setShowAddForm] = useState(false)
  const [newFeedUrl, setNewFeedUrl] = useState('')
  const [newFeedCategory, setNewFeedCategory] = useState<number | null>(null)
  const [newFeedInterval, setNewFeedInterval] = useState<number | null>(null)
  const [newFeedBrowserEngine, setNewFeedBrowserEngine] = useState<FeedBrowserEngine>('http')
  const [newFeedProxyMode, setNewFeedProxyMode] = useState<FeedProxyMode>('none')
  const [newFeedProxyUrl, setNewFeedProxyUrl] = useState('')
  const [newFeedProxyPoolCountry, setNewFeedProxyPoolCountry] = useState('')
  const [newFeedProxyPoolProtocol, setNewFeedProxyPoolProtocol] = useState('')

  const [newFeedAutoSummarize, setNewFeedAutoSummarize] = useState(false)
  const [newFeedSourceLanguage, setNewFeedSourceLanguage] = useState('')
  const [newFeedTargetLanguage, setNewFeedTargetLanguage] = useState('zh-CN')
  const [newFeedTranslateMethod, setNewFeedTranslateMethod] = useState<TranslateMethod>('none')
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editData, setEditData] = useState<{
    title: string
    category_id: number | null
    fetch_interval: number
    is_active: boolean
    use_playwright: boolean
    browser_engine: FeedBrowserEngine
    proxy_mode: FeedProxyMode
    proxy_enabled: boolean
    proxy_url: string
    proxy_pool_country: string
    proxy_pool_protocol: string
    auto_translate: boolean
    auto_summarize: boolean
    source_language: string
    target_language: string
    translate_method: TranslateMethod
  }>({ title: '', category_id: null, fetch_interval: 3600, is_active: true, use_playwright: false, browser_engine: 'http', proxy_mode: 'none', proxy_enabled: false, proxy_url: '', proxy_pool_country: '', proxy_pool_protocol: '', auto_translate: false, auto_summarize: false, source_language: '', target_language: 'zh-CN', translate_method: 'none' })
  
  // Filter states
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<number | 'all' | 'uncategorized'>('all')

  const { data: feeds = [] } = useQuery({
    queryKey: ['feeds'],
    queryFn: async () => {
      const response = await api.get<Feed[]>('/feeds')
      return response.data
    },
  })

  const { data: categories = [] } = useQuery({
    queryKey: ['categories'],
    queryFn: async () => {
      const response = await api.get<Category[]>('/categories')
      return response.data
    },
  })

  const { data: proxyGroups = { countries: [], protocols: [] } } = useQuery({
    queryKey: ['proxy-groups'],
    queryFn: async () => {
      const response = await api.get<ProxyPoolGroups>('/proxies/groups')
      return response.data
    },
  })

  // 获取 AI 模型列表，用于检查是否有默认模型
  const { data: aiModels = [] } = useQuery({
    queryKey: ['ai-models'],
    queryFn: async () => {
      const response = await api.get<AIModel[]>('/ai/models')
      return response.data
    },
  })
  const hasDefaultModel = aiModels.some(m => m.is_default)

  const addFeedMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post('/feeds', { 
        url: newFeedUrl, 
        category_id: newFeedCategory,
        fetch_interval: newFeedInterval ?? defaultSyncInterval,
        use_playwright: newFeedBrowserEngine !== 'http',
        browser_engine: newFeedBrowserEngine,
        proxy_mode: newFeedProxyMode,
        proxy_enabled: newFeedProxyMode !== 'none',
        proxy_url: newFeedProxyMode === 'single' ? newFeedProxyUrl.trim() : null,
        proxy_pool_country: newFeedProxyMode === 'pool' && newFeedProxyPoolCountry ? newFeedProxyPoolCountry : null,
        proxy_pool_protocol: newFeedProxyMode === 'pool' && newFeedProxyPoolProtocol ? newFeedProxyPoolProtocol : null,
        auto_translate: newFeedTranslateMethod !== 'none',
        auto_summarize: newFeedAutoSummarize,
        source_language: newFeedTranslateMethod === 'argos' && newFeedSourceLanguage ? newFeedSourceLanguage : null,
        target_language: newFeedTranslateMethod !== 'none' ? newFeedTargetLanguage : null,
        translate_method: newFeedTranslateMethod
      })
      return response.data
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['feeds'] })
      queryClient.invalidateQueries({ queryKey: ['categories'] })
      queryClient.invalidateQueries({ queryKey: ['articles'] })
      setShowAddForm(false)
      setNewFeedUrl('')
      setNewFeedCategory(null)
      setNewFeedInterval(3600)
      setNewFeedBrowserEngine('http')
      setNewFeedProxyMode('none')
      setNewFeedProxyUrl('')
      setNewFeedProxyPoolCountry('')
      setNewFeedProxyPoolProtocol('')
      setNewFeedAutoSummarize(false)
      setNewFeedSourceLanguage('')
      setNewFeedTargetLanguage('zh-CN')
      setNewFeedTranslateMethod('none')
      setMessage({ type: 'success', text: `订阅源 "${data.title || newFeedUrl}" 添加成功` })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      const errorMsg = Array.isArray(detail) ? detail.map((d: any) => d.msg).join(', ') : (detail || '添加失败，请检查 URL 是否正确')
      setMessage({ type: 'error', text: errorMsg })
    },
  })

  const updateFeedMutation = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: typeof editData }) => {
      const response = await api.put(`/feeds/${id}`, {
        ...data,
        proxy_enabled: data.proxy_mode !== 'none',
        proxy_url: data.proxy_mode === 'single' ? data.proxy_url.trim() : null,
        proxy_pool_country: data.proxy_mode === 'pool' && data.proxy_pool_country ? data.proxy_pool_country : null,
        proxy_pool_protocol: data.proxy_mode === 'pool' && data.proxy_pool_protocol ? data.proxy_pool_protocol : null,
        source_language: data.translate_method === 'argos' && data.source_language ? data.source_language : null,
      })
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['feeds'] })
      queryClient.invalidateQueries({ queryKey: ['categories'] })
      setEditingId(null)
      setMessage({ type: 'success', text: '订阅源已更新' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      setMessage({ type: 'error', text: detail || '更新失败' })
    },
  })

  const deleteFeedMutation = useMutation({
    mutationFn: async (feedId: number) => {
      await api.delete(`/feeds/${feedId}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['feeds'] })
      queryClient.invalidateQueries({ queryKey: ['categories'] })
      queryClient.invalidateQueries({ queryKey: ['articles'] })
      setMessage({ type: 'success', text: '订阅源已删除' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      setMessage({ type: 'error', text: detail || '删除失败' })
    },
  })

  const refreshFeedMutation = useMutation({
    mutationFn: async (feedId: number) => {
      const response = await api.post(`/feeds/${feedId}/refresh`)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['feeds'] })
      queryClient.invalidateQueries({ queryKey: ['categories'] })
      queryClient.invalidateQueries({ queryKey: ['articles'] })
      setMessage({ type: 'success', text: '订阅源刷新成功' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      setMessage({ type: 'error', text: detail || '刷新失败' })
    },
  })

  const translateAllMutation = useMutation({
    mutationFn: async (feedId: number) => {
      const response = await api.post(`/feeds/${feedId}/translate-all`)
      return response.data
    },
    onSuccess: (data) => {
      setMessage({ type: 'success', text: data.message || '翻译任务已启动' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      setMessage({ type: 'error', text: detail || '启动翻译失败' })
    },
  })

  const reorderMutation = useMutation({
    mutationFn: async (feedIds: number[]) => {
      const response = await api.put('/feeds/reorder', { feed_ids: feedIds })
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['feeds'] })
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      setMessage({ type: 'error', text: detail || '排序失败' })
    },
  })

  const moveFeed = (feedId: number, direction: 'up' | 'down') => {
    // Find index in filtered feeds array
    const currentFilteredIndex = filteredFeeds.findIndex(f => f.id === feedId)
    if (currentFilteredIndex === -1) return
    
    const newFilteredIndex = direction === 'up' ? currentFilteredIndex - 1 : currentFilteredIndex + 1
    if (newFilteredIndex < 0 || newFilteredIndex >= filteredFeeds.length) return
    
    // Swap in filtered list, then rebuild full list maintaining relative order
    const targetFeed = filteredFeeds[newFilteredIndex]
    
    // Find positions in full feeds array
    const currentFullIndex = feeds.findIndex(f => f.id === feedId)
    const targetFullIndex = feeds.findIndex(f => f.id === targetFeed.id)
    
    const newFeeds = [...feeds]
    const [removed] = newFeeds.splice(currentFullIndex, 1)
    newFeeds.splice(targetFullIndex, 0, removed)
    
    reorderMutation.mutate(newFeeds.map(f => f.id))
  }

  const handleExport = async () => {
    try {
      const response = await api.get('/feeds/export/opml', { responseType: 'blob' })
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', 'feeds.opml')
      document.body.appendChild(link)
      link.click()
      link.remove()
    } catch (err: any) {
      setMessage({ type: 'error', text: '导出失败' })
    }
  }

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    
    const formData = new FormData()
    formData.append('file', file)
    
    try {
      const response = await api.post('/feeds/import', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      queryClient.invalidateQueries({ queryKey: ['feeds'] })
      setMessage({ type: 'success', text: `成功导入 ${response.data.imported || 0} 个订阅源` })
      setTimeout(() => setMessage(null), 3000)
    } catch (err: any) {
      const detail = err.response?.data?.detail
      setMessage({ type: 'error', text: detail || '导入失败' })
    }
  }

  const startEdit = (feed: Feed) => {
    setEditingId(feed.id)
    setEditData({
      title: feed.title,
      category_id: feed.category_id,
      fetch_interval: feed.fetch_interval,
      is_active: feed.is_active,
      use_playwright: feed.use_playwright,
      browser_engine: resolveFeedBrowserEngine(feed),
      proxy_mode: resolveFeedProxyMode(feed),
      proxy_enabled: resolveFeedProxyMode(feed) !== 'none',
      proxy_url: feed.proxy_url || '',
      proxy_pool_country: feed.proxy_pool_country || '',
      proxy_pool_protocol: feed.proxy_pool_protocol || '',
      auto_translate: feed.auto_translate,
      auto_summarize: feed.auto_summarize,
      source_language: feed.source_language || '',
      target_language: feed.target_language || 'zh-CN',
      translate_method: feed.translate_method || 'none'
    })
  }

  const formatInterval = (seconds: number) => {
    if (seconds < 3600) return `${Math.floor(seconds / 60)} 分钟`
    return `${Math.floor(seconds / 3600)} 小时`
  }

  // Filter feeds by category and search query
  const filteredFeeds = useMemo(() => {
    return feeds.filter(feed => {
      // Category filter
      if (selectedCategory === 'uncategorized' && feed.category_id !== null) return false
      if (typeof selectedCategory === 'number' && feed.category_id !== selectedCategory) return false
      
      // Search filter
      if (searchQuery) {
        const query = searchQuery.toLowerCase()
        return feed.title.toLowerCase().includes(query) || feed.url.toLowerCase().includes(query)
      }
      return true
    })
  }, [feeds, selectedCategory, searchQuery])

  // Check if URL is Telegram
  const isTelegramUrl = (url: string) => {
    return url.includes('t.me/') || url.includes('telegram.me/')
  }

  // Convert Telegram URL to RSSHub format
  const convertTelegramUrl = (url: string) => {
    const match = url.match(/(?:t\.me|telegram\.me)\/([^\/\?]+)/)
    if (match) {
      return `https://rsshub.app/telegram/channel/${match[1]}`
    }
    return url
  }

  const handleUrlChange = (url: string) => {
    if (isTelegramUrl(url)) {
      setNewFeedUrl(convertTelegramUrl(url))
      setMessage({ type: 'success', text: '已自动转换为 RSSHub 格式' })
      setTimeout(() => setMessage(null), 3000)
    } else {
      setNewFeedUrl(url)
    }
  }

  return (
    <div>
      {message && (
        <div className={`mb-4 p-3 rounded ${message.type === 'success' ? 'bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-400' : 'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-400'}`}>
          {message.text}
        </div>
      )}
      
      {/* Action buttons */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <button
          onClick={() => setShowAddForm(true)}
          className="flex items-center gap-1 px-3 py-2 bg-primary-600 text-white rounded hover:bg-primary-700"
        >
          <Plus className="w-4 h-4" /> 添加订阅
        </button>
        <button
          onClick={handleExport}
          className="flex items-center gap-1 px-3 py-2 border dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-700 dark:text-gray-200"
        >
          <Upload className="w-4 h-4" /> 导出 OPML
        </button>
        <label className="flex items-center gap-1 px-3 py-2 border dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-700 dark:text-gray-200 cursor-pointer">
          <Download className="w-4 h-4" /> 导入 OPML
          <input type="file" accept=".opml,.xml" onChange={handleImport} className="hidden" />
        </label>
      </div>

      {/* Search and Category Filter */}
      <div className="mb-4 space-y-3">
        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="搜索订阅源..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white"
          />
        </div>
        
        {/* Category tabs */}
        <div className="flex gap-2 flex-wrap">
          <button
            onClick={() => setSelectedCategory('all')}
            className={`px-3 py-1.5 rounded-full text-sm transition-colors ${
              selectedCategory === 'all'
                ? 'bg-primary-600 text-white'
                : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
            }`}
          >
            全部 ({feeds.length})
          </button>
          <button
            onClick={() => setSelectedCategory('uncategorized')}
            className={`px-3 py-1.5 rounded-full text-sm transition-colors ${
              selectedCategory === 'uncategorized'
                ? 'bg-primary-600 text-white'
                : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
            }`}
          >
            未分类 ({feeds.filter(f => !f.category_id).length})
          </button>
          {categories.map(cat => (
            <button
              key={cat.id}
              onClick={() => setSelectedCategory(cat.id)}
              className={`px-3 py-1.5 rounded-full text-sm transition-colors ${
                selectedCategory === cat.id
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
              }`}
            >
              {cat.name} ({feeds.filter(f => f.category_id === cat.id).length})
            </button>
          ))}
        </div>
      </div>

      {showAddForm && (
        <div className="mb-4 p-4 border dark:border-gray-600 rounded bg-gray-50 dark:bg-gray-700 space-y-3">
          <div>
            <input
              type="text"
              placeholder="RSS 订阅地址 (支持 Telegram 频道链接自动转换)"
              value={newFeedUrl}
              onChange={(e) => handleUrlChange(e.target.value)}
              className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
            />
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              💡 支持直接粘贴 Telegram 频道链接 (如 https://t.me/channel_name)，将自动转换为 RSSHub 格式
            </p>
          </div>
          <div className="flex gap-2">
            <select
              value={newFeedCategory || ''}
              onChange={(e) => setNewFeedCategory(e.target.value ? parseInt(e.target.value) : null)}
              className="flex-1 px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
            >
              <option value="">未分类</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
            <select
              value={newFeedInterval ?? defaultSyncInterval}
              onChange={(e) => setNewFeedInterval(parseInt(e.target.value))}
              className="flex-1 px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
            >
              {syncIntervals.map((interval) => (
                <option key={interval.value} value={interval.value}>{interval.label}</option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-2 p-2 bg-yellow-50 dark:bg-yellow-900/30 border border-yellow-200 dark:border-yellow-800 rounded">
            <span className="text-sm dark:text-yellow-200">抓取方式</span>
            <select
              value={newFeedBrowserEngine}
              onChange={(e) => setNewFeedBrowserEngine(e.target.value as FeedBrowserEngine)}
              className="px-2 py-1 border dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-800 dark:text-white"
            >
              <option value="http">普通抓取</option>
              <option value="playwright">浏览器模式 (Playwright)</option>
              <option value="cloakbrowser">增强浏览器模式 (CloakBrowser)</option>
            </select>
            <span className="text-xs text-yellow-600 dark:text-yellow-400">CloakBrowser 作为独立增强方案</span>
          </div>
          <div className="grid gap-2 p-2 bg-slate-50 dark:bg-gray-800 border border-slate-200 dark:border-gray-600 rounded">
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-700 dark:text-gray-200">代理配置</span>
              <select
                value={newFeedProxyMode}
                onChange={(e) => setNewFeedProxyMode(e.target.value as FeedProxyMode)}
                className="px-2 py-1 border dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-700 dark:text-white"
              >
                <option value="none">不使用代理</option>
                <option value="single">单个代理</option>
                <option value="pool">代理池轮询</option>
              </select>
            </div>
            {newFeedProxyMode === 'single' && (
              <input
                type="text"
                value={newFeedProxyUrl}
                onChange={(e) => setNewFeedProxyUrl(e.target.value)}
                placeholder="http://user:pass@host:port 或 socks5://host:port"
                className="w-full px-3 py-2 border dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-700 dark:text-white"
              />
            )}
            {newFeedProxyMode === 'pool' && (
              <div className="grid grid-cols-2 gap-2">
                <select
                  value={newFeedProxyPoolCountry}
                  onChange={(e) => setNewFeedProxyPoolCountry(e.target.value)}
                  className="px-3 py-2 border dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-700 dark:text-white"
                >
                  <option value="">全部国家</option>
                  {proxyGroups.countries.map((country) => (
                    <option key={country} value={country}>{country.toUpperCase()}</option>
                  ))}
                </select>
                <select
                  value={newFeedProxyPoolProtocol}
                  onChange={(e) => setNewFeedProxyPoolProtocol(e.target.value)}
                  className="px-3 py-2 border dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-700 dark:text-white"
                >
                  <option value="">全部协议</option>
                  {proxyProtocols.map((protocol) => (
                    <option key={protocol} value={protocol}>{protocol}</option>
                  ))}
                </select>
              </div>
            )}
          </div>
          <div className="flex gap-2 flex-wrap items-center">
            <div className="flex items-center gap-2 p-2 bg-primary-50 dark:bg-primary-900/30 border border-blue-200 dark:border-blue-800 rounded">
              <span className="text-sm dark:text-blue-200">翻译方式:</span>
              <select
                value={newFeedTranslateMethod}
                onChange={(e) => {
                  const method = e.target.value as TranslateMethod
                  if (method === 'ai' && !hasDefaultModel) {
                    setMessage({ type: 'error', text: '请先在 AI 设置中设置默认模型' })
                    return
                  }
                  setNewFeedTranslateMethod(method)
                }}
                className="px-2 py-1 border dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-800 dark:text-white"
              >
                <option value="none">不翻译</option>
                <option value="google">Google 翻译</option>
                <option value="argos">本地翻译</option>
                <option value="ai" disabled={!hasDefaultModel}>AI 翻译{!hasDefaultModel ? ' (需配置)' : ''}</option>
              </select>
            </div>
            {newFeedTranslateMethod === 'argos' && (
              <select
                value={newFeedSourceLanguage}
                onChange={(e) => setNewFeedSourceLanguage(e.target.value)}
                className="px-3 py-2 border dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-800 dark:text-white"
              >
                <option value="">默认源语言</option>
                {translationSourceLanguages.map((language) => (
                  <option key={language.value} value={language.value}>{language.label}</option>
                ))}
              </select>
            )}
            {newFeedTranslateMethod !== 'none' && (
              <select
                value={newFeedTargetLanguage}
                onChange={(e) => setNewFeedTargetLanguage(e.target.value)}
                className="px-3 py-2 border dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-800 dark:text-white"
              >
                <option value="zh-CN">简体中文</option>
                <option value="zh-TW">繁体中文</option>
                <option value="en">English</option>
                <option value="ja">日本語</option>
                <option value="ko">한국어</option>
              </select>
            )}
            <label className={`flex items-center gap-2 p-2 bg-green-50 dark:bg-green-900/30 border border-green-200 dark:border-green-800 rounded ${!hasDefaultModel ? 'opacity-50' : ''}`}>
              <input
                type="checkbox"
                checked={newFeedAutoSummarize}
                onChange={(e) => {
                  if (e.target.checked && !hasDefaultModel) {
                    setMessage({ type: 'error', text: '请先在 AI 设置中设置默认模型' })
                    return
                  }
                  setNewFeedAutoSummarize(e.target.checked)
                }}
              />
              <span className="text-sm dark:text-green-200">启用 AI 整理</span>
            </label>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => addFeedMutation.mutate()}
              disabled={!newFeedUrl || (newFeedProxyMode === 'single' && !newFeedProxyUrl.trim()) || addFeedMutation.isPending}
              className="px-4 py-2 bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50"
            >
              {addFeedMutation.isPending ? '添加中...' : '添加'}
            </button>
            <button
              onClick={() => {
                setShowAddForm(false)
                setNewFeedUrl('')
                setNewFeedCategory(null)
                setNewFeedBrowserEngine('http')
                setNewFeedProxyMode('none')
                setNewFeedProxyUrl('')
                setNewFeedProxyPoolCountry('')
                setNewFeedProxyPoolProtocol('')
                setNewFeedAutoSummarize(false)
                setNewFeedTranslateMethod('none')
              }}
              className="px-4 py-2 border dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-600 dark:text-gray-200"
            >
              取消
            </button>
          </div>
        </div>
      )}

      <div className="border dark:border-gray-700 rounded divide-y dark:divide-gray-700">
        {filteredFeeds.map((feed) => (
          <div key={feed.id} className="p-4">
            {editingId === feed.id ? (
              <div className="space-y-3">
                <div className="text-sm text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-700 px-3 py-2 rounded truncate">
                  {feed.url}
                </div>
                <input
                  type="text"
                  value={editData.title}
                  onChange={(e) => setEditData({ ...editData, title: e.target.value })}
                  className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
                  placeholder="订阅源标题"
                />
                <div className="flex gap-2">
                  <select
                    value={editData.category_id || ''}
                    onChange={(e) => setEditData({ ...editData, category_id: e.target.value ? parseInt(e.target.value) : null })}
                    className="flex-1 px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
                  >
                    <option value="">未分类</option>
                    {categories.map((c) => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                  <select
                    value={editData.fetch_interval}
                    onChange={(e) => setEditData({ ...editData, fetch_interval: parseInt(e.target.value) })}
                    className="flex-1 px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
                  >
                    {syncIntervals.map((interval) => (
                      <option key={interval.value} value={interval.value}>{interval.label}</option>
                    ))}
                  </select>
                  <label className="flex items-center gap-2 px-3 py-2 border dark:border-gray-600 rounded dark:text-gray-200">
                    <input
                      type="checkbox"
                      checked={editData.is_active}
                      onChange={(e) => setEditData({ ...editData, is_active: e.target.checked })}
                    />
                    启用
                  </label>
                </div>
                <div className="flex items-center gap-2 p-2 bg-yellow-50 dark:bg-yellow-900/30 border border-yellow-200 dark:border-yellow-800 rounded text-sm dark:text-yellow-200">
                  <span>抓取方式</span>
                  <select
                    value={editData.browser_engine}
                    onChange={(e) => {
                      const browserEngine = e.target.value as FeedBrowserEngine
                      setEditData({
                        ...editData,
                        browser_engine: browserEngine,
                        use_playwright: browserEngine !== 'http',
                      })
                    }}
                    className="px-2 py-1 border dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-800 dark:text-white"
                  >
                    <option value="http">普通抓取</option>
                    <option value="playwright">Playwright</option>
                    <option value="cloakbrowser">CloakBrowser</option>
                  </select>
                </div>
                <div className="grid gap-2 p-2 bg-slate-50 dark:bg-gray-800 border border-slate-200 dark:border-gray-600 rounded text-sm">
                  <div className="flex items-center gap-2">
                    <span className="text-gray-700 dark:text-gray-200">代理配置</span>
                    <select
                      value={editData.proxy_mode}
                      onChange={(e) => {
                        const mode = e.target.value as FeedProxyMode
                        setEditData({
                          ...editData,
                          proxy_mode: mode,
                          proxy_enabled: mode !== 'none',
                        })
                      }}
                      className="px-2 py-1 border dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-700 dark:text-white"
                    >
                      <option value="none">不使用代理</option>
                      <option value="single">单个代理</option>
                      <option value="pool">代理池轮询</option>
                    </select>
                  </div>
                  {editData.proxy_mode === 'single' && (
                    <input
                      type="text"
                      value={editData.proxy_url}
                      onChange={(e) => setEditData({ ...editData, proxy_url: e.target.value })}
                      placeholder="http://user:pass@host:port 或 socks5://host:port"
                      className="w-full px-3 py-2 border dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-700 dark:text-white"
                    />
                  )}
                  {editData.proxy_mode === 'pool' && (
                    <div className="grid grid-cols-2 gap-2">
                      <select
                        value={editData.proxy_pool_country}
                        onChange={(e) => setEditData({ ...editData, proxy_pool_country: e.target.value })}
                        className="px-3 py-2 border dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-700 dark:text-white"
                      >
                        <option value="">全部国家</option>
                        {proxyGroups.countries.map((country) => (
                          <option key={country} value={country}>{country.toUpperCase()}</option>
                        ))}
                      </select>
                      <select
                        value={editData.proxy_pool_protocol}
                        onChange={(e) => setEditData({ ...editData, proxy_pool_protocol: e.target.value })}
                        className="px-3 py-2 border dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-700 dark:text-white"
                      >
                        <option value="">全部协议</option>
                        {proxyProtocols.map((protocol) => (
                          <option key={protocol} value={protocol}>{protocol}</option>
                        ))}
                      </select>
                    </div>
                  )}
                </div>
                <div className="flex gap-2 flex-wrap items-center">
                  <div className="flex items-center gap-2 p-2 bg-primary-50 dark:bg-primary-900/30 border border-blue-200 dark:border-blue-800 rounded text-sm">
                    <span className="dark:text-blue-200">翻译:</span>
                    <select
                      value={editData.translate_method}
                      onChange={(e) => {
                        const method = e.target.value as TranslateMethod
                        if (method === 'ai' && !hasDefaultModel) {
                          setMessage({ type: 'error', text: '请先在 AI 设置中设置默认模型' })
                          return
                        }
                        setEditData({
                          ...editData,
                          translate_method: method,
                          auto_translate: method !== 'none',
                          source_language: method === 'argos' ? editData.source_language : '',
                        })
                      }}
                      className="px-2 py-1 border dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-800 dark:text-white"
                    >
                      <option value="none">不翻译</option>
                      <option value="google">Google</option>
                      <option value="argos">本地</option>
                      <option value="ai" disabled={!hasDefaultModel}>AI{!hasDefaultModel ? ' (需配置)' : ''}</option>
                    </select>
                  </div>
                  {editData.translate_method === 'argos' && (
                    <select
                      value={editData.source_language}
                      onChange={(e) => setEditData({ ...editData, source_language: e.target.value })}
                      className="px-3 py-2 border dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-800 dark:text-white"
                    >
                      <option value="">默认源语言</option>
                      {translationSourceLanguages.map((language) => (
                        <option key={language.value} value={language.value}>{language.label}</option>
                      ))}
                    </select>
                  )}
                  {editData.translate_method !== 'none' && (
                    <select
                      value={editData.target_language}
                      onChange={(e) => setEditData({ ...editData, target_language: e.target.value })}
                      className="px-3 py-2 border dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-800 dark:text-white"
                    >
                      <option value="zh-CN">简体中文</option>
                      <option value="zh-TW">繁体中文</option>
                      <option value="en">English</option>
                      <option value="ja">日本語</option>
                      <option value="ko">한국어</option>
                    </select>
                  )}
                  <label className={`flex items-center gap-2 p-2 bg-green-50 dark:bg-green-900/30 border border-green-200 dark:border-green-800 rounded text-sm dark:text-green-200 ${!hasDefaultModel ? 'opacity-50' : ''}`}>
                    <input
                      type="checkbox"
                      checked={editData.auto_summarize}
                      onChange={(e) => {
                        if (e.target.checked && !hasDefaultModel) {
                          setMessage({ type: 'error', text: '请先在 AI 设置中设置默认模型' })
                          return
                        }
                        setEditData({ ...editData, auto_summarize: e.target.checked })
                      }}
                    />
                    AI 整理
                  </label>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => updateFeedMutation.mutate({ id: feed.id, data: editData })}
                    disabled={updateFeedMutation.isPending || (editData.proxy_mode === 'single' && !editData.proxy_url.trim())}
                    className="p-2 text-green-600 dark:text-green-400 hover:bg-green-50 dark:hover:bg-green-900/30 rounded"
                  >
                    <Check className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => setEditingId(null)}
                    className="p-2 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-4">
                {/* Sort buttons - hide only when searching */}
                {!searchQuery && (
                  <div className="flex flex-col gap-0.5">
                    <button
                      onClick={() => moveFeed(feed.id, 'up')}
                      disabled={filteredFeeds.indexOf(feed) === 0 || reorderMutation.isPending}
                      className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded disabled:opacity-30 disabled:cursor-not-allowed"
                      title="上移"
                    >
                      <ChevronUp className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => moveFeed(feed.id, 'down')}
                      disabled={filteredFeeds.indexOf(feed) === filteredFeeds.length - 1 || reorderMutation.isPending}
                      className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded disabled:opacity-30 disabled:cursor-not-allowed"
                      title="下移"
                    >
                      <ChevronDown className="w-4 h-4" />
                    </button>
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <h3 className="font-medium truncate dark:text-white">{feed.title || '无标题'}</h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400 truncate">{feed.url}</p>
                  <div className="flex gap-3 mt-1 text-xs text-gray-400 dark:text-gray-500 flex-wrap">
                    <span>同步间隔: {formatInterval(feed.fetch_interval)}</span>
                    {feed.category_id && categories.find(c => c.id === feed.category_id) && (
                      <span>分类: {categories.find(c => c.id === feed.category_id)?.name}</span>
                    )}
                    <span className={feed.is_active ? 'text-green-500' : 'text-red-500'}>
                      {feed.is_active ? '已启用' : '已禁用'}
                    </span>
                    {resolveFeedBrowserEngine(feed) !== 'http' && (
                      <span className="text-yellow-600 dark:text-yellow-400">🌐 {feedBrowserEngineLabels[resolveFeedBrowserEngine(feed)]}</span>
                    )}
                    {resolveFeedProxyMode(feed) === 'single' && (
                      <span className="text-slate-600 dark:text-slate-300">单代理</span>
                    )}
                    {resolveFeedProxyMode(feed) === 'pool' && (
                      <span className="text-slate-600 dark:text-slate-300">
                        代理池{feed.proxy_pool_country ? `/${feed.proxy_pool_country.toUpperCase()}` : ''}{feed.proxy_pool_protocol ? `/${feed.proxy_pool_protocol}` : ''}
                      </span>
                    )}
                    {feed.translate_method === 'google' && (
                      <span className="text-blue-600 dark:text-blue-400">🌐 Google翻译</span>
                    )}
                    {feed.translate_method === 'ai' && (
                      <span className="text-primary-600 dark:text-primary-400">🤖 AI翻译</span>
                    )}
                    {feed.translate_method === 'argos' && (
                      <span className="text-emerald-600 dark:text-emerald-400">本地翻译</span>
                    )}
                    {feed.auto_summarize && (
                      <span className="text-green-600 dark:text-green-400">📝 AI整理</span>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => refreshFeedMutation.mutate(feed.id)}
                  disabled={refreshFeedMutation.isPending}
                  className="p-2 text-primary-500 hover:bg-primary-50 dark:hover:bg-primary-900/30 rounded disabled:opacity-50"
                  title="刷新订阅源"
                >
                  <RefreshCw className={`w-4 h-4 ${refreshFeedMutation.isPending ? 'animate-spin' : ''}`} />
                </button>
                {(['ai', 'google', 'argos'] as TranslateMethod[]).includes(feed.translate_method) && (
                  <button
                    onClick={() => translateAllMutation.mutate(feed.id)}
                    disabled={translateAllMutation.isPending}
                    className="p-2 text-purple-500 hover:bg-purple-50 dark:hover:bg-purple-900/30 rounded disabled:opacity-50"
                    title="翻译所有旧文章"
                  >
                    <Languages className="w-4 h-4" />
                  </button>
                )}
                <button
                  onClick={() => startEdit(feed)}
                  className="p-2 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
                  title="编辑"
                >
                  <Edit2 className="w-4 h-4" />
                </button>
                <button
                  onClick={() => deleteFeedMutation.mutate(feed.id)}
                  className="p-2 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 rounded"
                  title="删除"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>
        ))}
        {filteredFeeds.length === 0 && (
          <div className="p-4 text-center text-gray-500 dark:text-gray-400">
            {feeds.length === 0 ? '暂无订阅源' : '没有匹配的订阅源'}
          </div>
        )}
      </div>
    </div>
  )
}

function ProxyPoolTab() {
  const queryClient = useQueryClient()
  const [singleRaw, setSingleRaw] = useState('')
  const [bulkRaw, setBulkRaw] = useState('')
  const [defaultProtocol, setDefaultProtocol] = useState<ProxyProtocol>('http')
  const [singleCountry, setSingleCountry] = useState('')
  const [bulkDefaultCountry, setBulkDefaultCountry] = useState('')
  const [newProxiesActive, setNewProxiesActive] = useState(true)
  const [filterCountry, setFilterCountry] = useState('')
  const [filterProtocol, setFilterProtocol] = useState('')
  const [filterActive, setFilterActive] = useState<'all' | 'active' | 'inactive'>('all')
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const [testUrl, setTestUrl] = useState('https://www.gstatic.com/generate_204')
  const [testTimeout, setTestTimeout] = useState(10)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [importErrors, setImportErrors] = useState<string[]>([])
  const [editingProxyId, setEditingProxyId] = useState<number | null>(null)
  const [proxyEdit, setProxyEdit] = useState({
    raw: '',
    default_protocol: 'http' as ProxyProtocol,
    country: '',
    is_active: true,
    fail_count: '0',
  })

  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds])

  const activeParam = filterActive === 'all' ? undefined : filterActive === 'active'
  const { data: proxies = [] } = useQuery({
    queryKey: ['proxies', filterCountry, filterProtocol, filterActive],
    queryFn: async () => {
      const response = await api.get<ProxyPoolEntry[]>('/proxies', {
        params: {
          country: filterCountry || undefined,
          protocol: filterProtocol || undefined,
          active: activeParam,
        },
      })
      return response.data
    },
  })

  const { data: proxyGroups = { countries: [], protocols: [] } } = useQuery({
    queryKey: ['proxy-groups'],
    queryFn: async () => {
      const response = await api.get<ProxyPoolGroups>('/proxies/groups')
      return response.data
    },
  })

  const invalidateProxyData = () => {
    queryClient.invalidateQueries({ queryKey: ['proxies'] })
    queryClient.invalidateQueries({ queryKey: ['proxy-groups'] })
    queryClient.invalidateQueries({ queryKey: ['feeds'] })
  }

  const showMessage = (type: 'success' | 'error', text: string) => {
    setMessage({ type, text })
    setTimeout(() => setMessage(null), 3000)
  }

  const createMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post<ProxyPoolEntry>('/proxies', {
        raw: singleRaw,
        default_protocol: defaultProtocol,
        country: singleCountry || null,
        is_active: newProxiesActive,
      })
      return response.data
    },
    onSuccess: () => {
      invalidateProxyData()
      setSingleRaw('')
      setImportErrors([])
      showMessage('success', '代理已添加')
    },
    onError: (err: unknown) => {
      showMessage('error', getApiErrorMessage(err, '添加代理失败'))
    },
  })

  const importMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post<ProxyPoolImportResult>('/proxies/import', {
        content: bulkRaw,
        default_protocol: defaultProtocol,
        default_country: bulkDefaultCountry || null,
        is_active: newProxiesActive,
      })
      return response.data
    },
    onSuccess: (data) => {
      invalidateProxyData()
      setSelectedIds([])
      setBulkRaw(data.errors.length ? bulkRaw : '')
      setImportErrors(data.errors.slice(0, 8))
      showMessage('success', `导入 ${data.imported} 个，跳过 ${data.skipped} 个，失败 ${data.errors.length} 个`)
    },
    onError: (err: unknown) => {
      showMessage('error', getApiErrorMessage(err, '批量导入失败'))
    },
  })

  const updateMutation = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: ProxyUpdatePayload }) => {
      const response = await api.put<ProxyPoolEntry>(`/proxies/${id}`, data)
      return response.data
    },
    onSuccess: () => {
      invalidateProxyData()
      setEditingProxyId(null)
    },
    onError: (err: unknown) => {
      showMessage('error', getApiErrorMessage(err, '更新代理失败'))
    },
  })

  const bulkUpdateMutation = useMutation({
    mutationFn: async ({ ids, isActive }: { ids: number[]; isActive: boolean }) => {
      await Promise.all(ids.map((id) => api.put(`/proxies/${id}`, { is_active: isActive })))
    },
    onSuccess: (_, variables) => {
      invalidateProxyData()
      setSelectedIds([])
      showMessage('success', variables.isActive ? '已启用选中代理' : '已停用选中代理')
    },
    onError: (err: unknown) => {
      showMessage('error', getApiErrorMessage(err, '批量更新失败'))
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/proxies/${id}`)
    },
    onSuccess: (_, id) => {
      invalidateProxyData()
      setSelectedIds((current) => current.filter((item) => item !== id))
      showMessage('success', '代理已删除')
    },
    onError: (err: unknown) => {
      showMessage('error', getApiErrorMessage(err, '删除代理失败'))
    },
  })

  const deleteSelectedMutation = useMutation({
    mutationFn: async (ids: number[]) => {
      await Promise.all(ids.map((id) => api.delete(`/proxies/${id}`)))
    },
    onSuccess: () => {
      invalidateProxyData()
      setSelectedIds([])
      showMessage('success', '选中代理已删除')
    },
    onError: (err: unknown) => {
      showMessage('error', getApiErrorMessage(err, '批量删除失败'))
    },
  })

  const testMutation = useMutation({
    mutationFn: async (ids: number[]) => {
      const response = await api.post<ProxyPoolTestResult>('/proxies/test', {
        ids,
        test_url: testUrl,
        timeout: testTimeout,
      })
      return response.data
    },
    onSuccess: (data) => {
      invalidateProxyData()
      showMessage('success', `测速完成：成功 ${data.success} 个，失败 ${data.failed} 个`)
    },
    onError: (err: unknown) => {
      showMessage('error', getApiErrorMessage(err, '代理测速失败'))
    },
  })

  const visibleIds = proxies.map((proxy) => proxy.id)
  const allVisibleSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedSet.has(id))
  const activeCount = proxies.filter((proxy) => proxy.is_active).length
  const inactiveCount = proxies.length - activeCount

  const toggleSelected = (id: number) => {
    setSelectedIds((current) => (
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id]
    ))
  }

  const toggleAllVisible = () => {
    setSelectedIds((current) => {
      if (allVisibleSelected) {
        return current.filter((id) => !visibleIds.includes(id))
      }
      return Array.from(new Set([...current, ...visibleIds]))
    })
  }

  const runTest = (ids: number[]) => {
    if (ids.length === 0) {
      showMessage('error', '没有可测速的代理')
      return
    }
    testMutation.mutate(ids)
  }

  const startProxyEdit = (proxy: ProxyPoolEntry) => {
    setEditingProxyId(proxy.id)
    setProxyEdit({
      raw: proxy.proxy_url,
      default_protocol: proxy.protocol,
      country: proxy.country || '',
      is_active: proxy.is_active,
      fail_count: proxy.fail_count.toString(),
    })
  }

  const saveProxyEdit = (id: number) => {
    if (!proxyEdit.raw.trim()) {
      showMessage('error', '代理不能为空')
      return
    }

    updateMutation.mutate({
      id,
      data: {
        raw: proxyEdit.raw.trim(),
        default_protocol: proxyEdit.default_protocol,
        country: proxyEdit.country.trim() ? proxyEdit.country.trim() : null,
        is_active: proxyEdit.is_active,
        fail_count: Math.max(0, parseInt(proxyEdit.fail_count) || 0),
      },
    })
  }

  return (
    <div className="space-y-4">
      {message && (
        <div className={`p-3 rounded ${message.type === 'success' ? 'bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-400' : 'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-400'}`}>
          {message.text}
        </div>
      )}

      <div className="p-4 border dark:border-gray-700 rounded bg-gray-50 dark:bg-gray-800 space-y-3">
        <div className="grid gap-2 md:grid-cols-[1fr_140px_120px_120px]">
          <input
            type="text"
            value={singleRaw}
            onChange={(e) => setSingleRaw(e.target.value)}
            placeholder="http://user:pass@1.2.3.4:8080"
            className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white"
          />
          <select
            value={defaultProtocol}
            onChange={(e) => setDefaultProtocol(e.target.value as ProxyProtocol)}
            className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white"
          >
            {proxyProtocols.map((protocol) => (
              <option key={protocol} value={protocol}>{protocol}</option>
            ))}
          </select>
          <input
            type="text"
            value={singleCountry}
            onChange={(e) => setSingleCountry(e.target.value)}
            placeholder="单个国家"
            className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white"
          />
          <button
            onClick={() => createMutation.mutate()}
            disabled={!singleRaw.trim() || createMutation.isPending}
            className="flex items-center justify-center gap-1 px-3 py-2 bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50"
          >
            <Plus className="w-4 h-4" /> 添加
          </button>
        </div>
        <label className="inline-flex items-center gap-2 text-sm text-gray-600 dark:text-gray-300">
          <input
            type="checkbox"
            checked={newProxiesActive}
            onChange={(e) => setNewProxiesActive(e.target.checked)}
          />
          导入后启用
        </label>
        <textarea
          value={bulkRaw}
          onChange={(e) => setBulkRaw(e.target.value)}
          placeholder={'http://user:pass@1.2.3.4:8080\n1.2.3.4:8080:user:pass\nusername,password,1.2.3.4,8080'}
          rows={7}
          className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white font-mono text-sm"
        />
        <div className="flex gap-2 flex-wrap">
          <input
            type="text"
            value={bulkDefaultCountry}
            onChange={(e) => setBulkDefaultCountry(e.target.value)}
            placeholder="批量国家"
            className="w-32 px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white"
          />
          <button
            onClick={() => importMutation.mutate()}
            disabled={!bulkRaw.trim() || importMutation.isPending}
            className="flex items-center gap-1 px-3 py-2 bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50"
          >
            <Upload className="w-4 h-4" /> 批量导入
          </button>
          <button
            onClick={() => { setBulkRaw(''); setImportErrors([]) }}
            disabled={!bulkRaw && importErrors.length === 0}
            className="px-3 py-2 border dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-700 dark:text-gray-200 disabled:opacity-50"
          >
            清空
          </button>
        </div>
        {importErrors.length > 0 && (
          <div className="p-3 bg-red-50 dark:bg-red-900/30 rounded text-sm text-red-700 dark:text-red-300 space-y-1">
            {importErrors.map((error) => (
              <div key={error} className="truncate">{error}</div>
            ))}
          </div>
        )}
      </div>

      <div className="p-3 border dark:border-gray-700 rounded bg-white dark:bg-gray-800 space-y-3">
        <div className="flex gap-2 flex-wrap items-center">
          <select
            value={filterCountry}
            onChange={(e) => { setFilterCountry(e.target.value); setSelectedIds([]) }}
            className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white"
          >
            <option value="">全部国家</option>
            {proxyGroups.countries.map((country) => (
              <option key={country} value={country}>{country.toUpperCase()}</option>
            ))}
          </select>
          <select
            value={filterProtocol}
            onChange={(e) => { setFilterProtocol(e.target.value); setSelectedIds([]) }}
            className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white"
          >
            <option value="">全部协议</option>
            {proxyProtocols.map((protocol) => (
              <option key={protocol} value={protocol}>{protocol}</option>
            ))}
          </select>
          <select
            value={filterActive}
            onChange={(e) => { setFilterActive(e.target.value as 'all' | 'active' | 'inactive'); setSelectedIds([]) }}
            className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white"
          >
            <option value="all">全部状态</option>
            <option value="active">已启用</option>
            <option value="inactive">已停用</option>
          </select>
          <input
            type="text"
            value={testUrl}
            onChange={(e) => setTestUrl(e.target.value)}
            className="min-w-[220px] flex-1 px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white"
          />
          <input
            type="number"
            min={1}
            max={60}
            value={testTimeout}
            onChange={(e) => setTestTimeout(Math.max(1, Math.min(60, parseInt(e.target.value) || 10)))}
            className="w-24 px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white"
          />
        </div>
        <div className="flex gap-2 flex-wrap items-center text-sm">
          <span className="text-gray-500 dark:text-gray-400">共 {proxies.length} 个，启用 {activeCount} 个，停用 {inactiveCount} 个</span>
          <button
            onClick={() => runTest(selectedIds)}
            disabled={selectedIds.length === 0 || testMutation.isPending}
            className="flex items-center gap-1 px-3 py-1.5 border dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-700 dark:text-gray-200 disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${testMutation.isPending ? 'animate-spin' : ''}`} /> 测试选中
          </button>
          <button
            onClick={() => runTest(visibleIds)}
            disabled={visibleIds.length === 0 || testMutation.isPending}
            className="flex items-center gap-1 px-3 py-1.5 border dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-700 dark:text-gray-200 disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${testMutation.isPending ? 'animate-spin' : ''}`} /> 测试筛选
          </button>
          <button
            onClick={() => bulkUpdateMutation.mutate({ ids: selectedIds, isActive: true })}
            disabled={selectedIds.length === 0 || bulkUpdateMutation.isPending}
            className="px-3 py-1.5 border dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-700 dark:text-gray-200 disabled:opacity-50"
          >
            启用选中
          </button>
          <button
            onClick={() => bulkUpdateMutation.mutate({ ids: selectedIds, isActive: false })}
            disabled={selectedIds.length === 0 || bulkUpdateMutation.isPending}
            className="px-3 py-1.5 border dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-700 dark:text-gray-200 disabled:opacity-50"
          >
            停用选中
          </button>
          <button
            onClick={() => deleteSelectedMutation.mutate(selectedIds)}
            disabled={selectedIds.length === 0 || deleteSelectedMutation.isPending}
            className="px-3 py-1.5 text-red-600 dark:text-red-400 border border-red-200 dark:border-red-800 rounded hover:bg-red-50 dark:hover:bg-red-900/30 disabled:opacity-50"
          >
            删除选中
          </button>
        </div>
      </div>

      <div className="border dark:border-gray-700 rounded overflow-x-auto">
        <table className="w-full min-w-[900px] text-sm">
          <thead className="bg-gray-50 dark:bg-gray-800 text-gray-600 dark:text-gray-300">
            <tr>
              <th className="w-10 p-3 text-left">
                <input
                  type="checkbox"
                  checked={allVisibleSelected}
                  onChange={toggleAllVisible}
                />
              </th>
              <th className="p-3 text-left">代理</th>
              <th className="p-3 text-left">分组</th>
              <th className="p-3 text-left">状态</th>
              <th className="p-3 text-left">延迟</th>
              <th className="p-3 text-left">失败</th>
              <th className="p-3 text-left">错误</th>
              <th className="p-3 text-right">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y dark:divide-gray-700">
            {proxies.map((proxy) => (
              <tr key={proxy.id} className="dark:text-gray-100">
                <td className="p-3">
                  <input
                    type="checkbox"
                    checked={selectedSet.has(proxy.id)}
                    onChange={() => toggleSelected(proxy.id)}
                  />
                </td>
                {editingProxyId === proxy.id ? (
                  <>
                    <td className="p-3">
                      <input
                        type="text"
                        value={proxyEdit.raw}
                        onChange={(e) => setProxyEdit({ ...proxyEdit, raw: e.target.value })}
                        className="w-full px-2 py-1 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white font-mono text-xs"
                      />
                    </td>
                    <td className="p-3">
                      <div className="grid grid-cols-2 gap-2">
                        <select
                          value={proxyEdit.default_protocol}
                          onChange={(e) => setProxyEdit({ ...proxyEdit, default_protocol: e.target.value as ProxyProtocol })}
                          className="px-2 py-1 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white"
                        >
                          {proxyProtocols.map((protocol) => (
                            <option key={protocol} value={protocol}>{protocol}</option>
                          ))}
                        </select>
                        <input
                          type="text"
                          value={proxyEdit.country}
                          onChange={(e) => setProxyEdit({ ...proxyEdit, country: e.target.value })}
                          placeholder="国家"
                          className="px-2 py-1 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white"
                        />
                      </div>
                    </td>
                    <td className="p-3">
                      <label className="inline-flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={proxyEdit.is_active}
                          onChange={(e) => setProxyEdit({ ...proxyEdit, is_active: e.target.checked })}
                        />
                        启用
                      </label>
                    </td>
                    <td className="p-3 text-gray-500 dark:text-gray-400">保存后更新</td>
                    <td className="p-3">
                      <input
                        type="number"
                        min={0}
                        value={proxyEdit.fail_count}
                        onChange={(e) => setProxyEdit({ ...proxyEdit, fail_count: e.target.value })}
                        className="w-20 px-2 py-1 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white"
                      />
                    </td>
                    <td className="p-3 text-gray-500 dark:text-gray-400">-</td>
                    <td className="p-3">
                      <div className="flex justify-end gap-1">
                        <button
                          onClick={() => saveProxyEdit(proxy.id)}
                          disabled={!proxyEdit.raw.trim() || updateMutation.isPending}
                          className="p-2 text-green-600 dark:text-green-400 hover:bg-green-50 dark:hover:bg-green-900/30 rounded disabled:opacity-50"
                          title="保存"
                        >
                          <Check className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => setEditingProxyId(null)}
                          className="p-2 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
                          title="取消"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </>
                ) : (
                  <>
                    <td className="p-3">
                      <div className="font-medium">{proxy.host}:{proxy.port}</div>
                      <div className="text-xs text-gray-500 dark:text-gray-400 truncate max-w-[320px]">
                        {proxy.username ? `${proxy.username}@` : ''}{proxy.protocol}://{proxy.host}:{proxy.port}
                      </div>
                    </td>
                    <td className="p-3">
                      <div className="flex gap-1 flex-wrap">
                        <span className="px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-700">{proxy.protocol}</span>
                        <span className="px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-700">{proxy.country ? proxy.country.toUpperCase() : '未分组'}</span>
                        <span className="px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-700">{proxy.source_format}</span>
                      </div>
                    </td>
                    <td className="p-3">
                      <span className={proxy.is_active ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
                        {proxy.is_active ? '启用' : '停用'}
                      </span>
                    </td>
                    <td className="p-3 text-gray-600 dark:text-gray-300">
                      {proxy.last_latency_ms === null ? '-' : `${proxy.last_latency_ms}ms`}
                    </td>
                    <td className="p-3 text-gray-600 dark:text-gray-300">{proxy.fail_count}/5</td>
                    <td className="p-3 max-w-[220px] truncate text-gray-500 dark:text-gray-400" title={proxy.last_error || ''}>
                      {proxy.last_error || '-'}
                    </td>
                    <td className="p-3">
                      <div className="flex justify-end gap-1">
                        <button
                          onClick={() => runTest([proxy.id])}
                          disabled={testMutation.isPending}
                          className="p-2 text-primary-500 hover:bg-primary-50 dark:hover:bg-primary-900/30 rounded disabled:opacity-50"
                          title="测速"
                        >
                          <RefreshCw className={`w-4 h-4 ${testMutation.isPending ? 'animate-spin' : ''}`} />
                        </button>
                        <button
                          onClick={() => startProxyEdit(proxy)}
                          className="p-2 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
                          title="编辑"
                        >
                          <Edit2 className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => updateMutation.mutate({ id: proxy.id, data: { is_active: !proxy.is_active } })}
                          disabled={updateMutation.isPending}
                          className="p-2 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded disabled:opacity-50"
                          title={proxy.is_active ? '停用' : '启用'}
                        >
                          {proxy.is_active ? <X className="w-4 h-4" /> : <Check className="w-4 h-4" />}
                        </button>
                        <button
                          onClick={() => updateMutation.mutate({ id: proxy.id, data: { fail_count: 0, is_active: true } })}
                          disabled={updateMutation.isPending}
                          className="p-2 text-green-600 dark:text-green-400 hover:bg-green-50 dark:hover:bg-green-900/30 rounded disabled:opacity-50"
                          title="重置失败"
                        >
                          <Check className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => deleteMutation.mutate(proxy.id)}
                          disabled={deleteMutation.isPending}
                          className="p-2 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 rounded disabled:opacity-50"
                          title="删除"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
        {proxies.length === 0 && (
          <div className="p-4 text-center text-gray-500 dark:text-gray-400">暂无代理</div>
        )}
      </div>
    </div>
  )
}

function CategoriesTab() {
  const queryClient = useQueryClient()
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editName, setEditName] = useState('')
  const [newName, setNewName] = useState('')
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  const { data: categories = [] } = useQuery({
    queryKey: ['categories'],
    queryFn: async () => {
      const response = await api.get<Category[]>('/categories')
      return response.data
    },
  })

  const createMutation = useMutation({
    mutationFn: async () => {
      await api.post('/categories', { name: newName })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['categories'] })
      setNewName('')
      setMessage({ type: 'success', text: '分类添加成功' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      setMessage({ type: 'error', text: detail || '添加失败' })
    },
  })

  const updateMutation = useMutation({
    mutationFn: async ({ id, name }: { id: number; name: string }) => {
      await api.put(`/categories/${id}`, { name })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['categories'] })
      setEditingId(null)
      setMessage({ type: 'success', text: '分类已更新' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      setMessage({ type: 'error', text: detail || '更新失败' })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/categories/${id}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['categories'] })
      setMessage({ type: 'success', text: '分类已删除' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      setMessage({ type: 'error', text: detail || '删除失败' })
    },
  })

  const reorderMutation = useMutation({
    mutationFn: async (categoryIds: number[]) => {
      const response = await api.put('/categories/reorder', { category_ids: categoryIds })
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['categories'] })
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      setMessage({ type: 'error', text: detail || '排序失败' })
    },
  })

  const moveCategory = (categoryId: number, direction: 'up' | 'down') => {
    const currentIndex = categories.findIndex(c => c.id === categoryId)
    if (currentIndex === -1) return
    
    const newIndex = direction === 'up' ? currentIndex - 1 : currentIndex + 1
    if (newIndex < 0 || newIndex >= categories.length) return
    
    const newCategories = [...categories]
    const [removed] = newCategories.splice(currentIndex, 1)
    newCategories.splice(newIndex, 0, removed)
    
    reorderMutation.mutate(newCategories.map(c => c.id))
  }

  return (
    <div>
      {message && (
        <div className={`mb-4 p-3 rounded ${message.type === 'success' ? 'bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-400' : 'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-400'}`}>
          {message.text}
        </div>
      )}
      <div className="flex gap-2 mb-4">
        <input
          type="text"
          placeholder="新分类名称"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          className="flex-1 px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white"
        />
        <button
          onClick={() => createMutation.mutate()}
          disabled={!newName || createMutation.isPending}
          className="px-4 py-2 bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50"
        >
          添加
        </button>
      </div>

      <div className="border dark:border-gray-700 rounded divide-y dark:divide-gray-700">
        {categories.map((category) => (
          <div key={category.id} className="flex items-center gap-4 p-4">
            {editingId === category.id ? (
              <>
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="flex-1 px-3 py-1 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white"
                />
                <button
                  onClick={() => updateMutation.mutate({ id: category.id, name: editName })}
                  className="p-2 text-green-600 dark:text-green-400 hover:bg-green-50 dark:hover:bg-green-900/30 rounded"
                >
                  <Check className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setEditingId(null)}
                  className="p-2 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
                >
                  <X className="w-4 h-4" />
                </button>
              </>
            ) : (
              <>
                {/* Sort buttons */}
                <div className="flex flex-col gap-0.5">
                  <button
                    onClick={() => moveCategory(category.id, 'up')}
                    disabled={categories.indexOf(category) === 0 || reorderMutation.isPending}
                    className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded disabled:opacity-30 disabled:cursor-not-allowed"
                    title="上移"
                  >
                    <ChevronUp className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => moveCategory(category.id, 'down')}
                    disabled={categories.indexOf(category) === categories.length - 1 || reorderMutation.isPending}
                    className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded disabled:opacity-30 disabled:cursor-not-allowed"
                    title="下移"
                  >
                    <ChevronDown className="w-4 h-4" />
                  </button>
                </div>
                <span className="flex-1 dark:text-white">{category.name}</span>
                <span className="text-sm text-gray-500 dark:text-gray-400">{category.feed_count} 个订阅</span>
                <button
                  onClick={() => { setEditingId(category.id); setEditName(category.name) }}
                  className="p-2 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
                >
                  <Edit2 className="w-4 h-4" />
                </button>
                <button
                  onClick={() => deleteMutation.mutate(category.id)}
                  className="p-2 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 rounded"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </>
            )}
          </div>
        ))}
        {categories.length === 0 && (
          <div className="p-4 text-center text-gray-500 dark:text-gray-400">暂无分类</div>
        )}
      </div>
    </div>
  )
}


function AITab() {
  const queryClient = useQueryClient()
  const [showAddProvider, setShowAddProvider] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [newProvider, setNewProvider] = useState({
    name: '',
    type: 'openai' as 'openai' | 'gemini' | 'openai_compatible',
    api_key: '',
    base_url: '',
  })
  const [prompts, setPrompts] = useState({
    translate: '',
    summarize: '',
  })
  const [newGoogleKey, setNewGoogleKey] = useState({
    name: '',
    api_key: '',
    is_active: true,
    limit_days: '',
    limit_articles: '',
    limit_characters: '',
  })
  const [editingGoogleKeyId, setEditingGoogleKeyId] = useState<number | null>(null)
  const [googleKeyEdit, setGoogleKeyEdit] = useState({
    name: '',
    api_key: '',
    is_active: true,
    limit_days: '',
    limit_articles: '',
    limit_characters: '',
  })
  const [argosLogPage, setArgosLogPage] = useState(1)
  const [showArgosLogsModal, setShowArgosLogsModal] = useState(false)
  const argosLogPageSize = 10

  const { data: providers = [] } = useQuery({
    queryKey: ['ai-providers'],
    queryFn: async () => {
      const response = await api.get<AIProvider[]>('/ai/providers')
      return response.data
    },
  })

  const { data: models = [] } = useQuery({
    queryKey: ['ai-models'],
    queryFn: async () => {
      const response = await api.get<AIModel[]>('/ai/models')
      return response.data
    },
  })

  const { data: settings } = useQuery({
    queryKey: ['ai-settings'],
    queryFn: async () => {
      const response = await api.get<{
        translate_prompt: string
        summarize_prompt: string
        embedding_provider_id: number | null
        embedding_model: string | null
        argos_source_language: string | null
      }>('/ai/settings')
      return response.data
    },
  })

  const { data: googleTranslateKeys = [] } = useQuery({
    queryKey: ['google-translate-keys'],
    queryFn: async () => {
      const response = await api.get<GoogleTranslateKey[]>('/ai/google-translate-keys')
      return response.data
    },
  })

  const { data: argosPackages, isLoading: argosPackagesLoading, error: argosPackagesError } = useQuery<ArgosPackagesResponse>({
    queryKey: ['argos-packages'],
    queryFn: async () => {
      const response = await api.get<ArgosPackagesResponse>('/ai/argos/packages')
      return response.data
    },
    retry: false,
  })

  const { data: argosTranslationLogs, isLoading: argosLogsLoading } = useQuery<ArgosTranslationLogsResponse>({
    queryKey: ['argos-translation-logs', argosLogPage],
    queryFn: async () => {
      const response = await api.get<ArgosTranslationLogsResponse>('/ai/argos/translation-logs', {
        params: { page: argosLogPage, page_size: argosLogPageSize },
      })
      return response.data
    },
    enabled: showArgosLogsModal,
    refetchInterval: showArgosLogsModal ? 10000 : false,
  })

  const [embeddingConfig, setEmbeddingConfig] = useState<{
    provider_id: number | null
    model: string
  }>({ provider_id: null, model: '' })
  const [argosSourceLanguage, setArgosSourceLanguage] = useState('en')
  const [argosSettingsLoaded, setArgosSettingsLoaded] = useState(false)
  const [argosInstallForm, setArgosInstallForm] = useState({
    source_language: 'en',
    target_language: 'zh',
  })
  const [argosTestForm, setArgosTestForm] = useState({
    source_language: 'en',
    target_language: 'zh',
    text: 'Hello world',
  })
  const [argosTestResult, setArgosTestResult] = useState<ArgosPackageTestResult | null>(null)

  const buildGoogleKeyPayload = (form: typeof newGoogleKey, includeApiKey: boolean) => ({
    name: form.name.trim(),
    ...(includeApiKey && form.api_key.trim() ? { api_key: form.api_key.trim() } : {}),
    is_active: form.is_active,
    limit_days: form.limit_days ? parseInt(form.limit_days) : null,
    limit_articles: form.limit_articles ? parseInt(form.limit_articles) : null,
    limit_characters: form.limit_characters ? parseInt(form.limit_characters) : null,
  })

  // Initialize prompts and embedding config when settings load
  if (settings && !prompts.translate && !prompts.summarize) {
    setPrompts({
      translate: settings.translate_prompt,
      summarize: settings.summarize_prompt,
    })
  }
  
  // Initialize embedding config when settings load
  if (settings && embeddingConfig.provider_id === null && !embeddingConfig.model) {
    if (settings.embedding_provider_id || settings.embedding_model) {
      setEmbeddingConfig({
        provider_id: settings.embedding_provider_id,
        model: settings.embedding_model || '',
      })
    }
  }

  if (settings && !argosSettingsLoaded) {
    setArgosSourceLanguage(settings.argos_source_language || 'en')
    setArgosSettingsLoaded(true)
  }
  const addProviderMutation = useMutation({
    mutationFn: async () => {
      await api.post('/ai/providers', newProvider)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-providers'] })
      setShowAddProvider(false)
      setNewProvider({ name: '', type: 'openai', api_key: '', base_url: '' })
      setMessage({ type: 'success', text: '渠道添加成功' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: any) => {
      setMessage({ type: 'error', text: err.response?.data?.detail || '添加失败' })
    },
  })

  const deleteProviderMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/ai/providers/${id}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-providers'] })
      queryClient.invalidateQueries({ queryKey: ['ai-models'] })
      setMessage({ type: 'success', text: '渠道已删除' })
      setTimeout(() => setMessage(null), 3000)
    },
  })

  const setDefaultModelMutation = useMutation({
    mutationFn: async (modelId: number) => {
      await api.put(`/ai/models/${modelId}/default`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-models'] })
      setMessage({ type: 'success', text: '默认模型已更新' })
      setTimeout(() => setMessage(null), 3000)
    },
  })

  const fetchModelsMutation = useMutation({
    mutationFn: async (providerId: number) => {
      await api.post(`/ai/providers/${providerId}/fetch-models`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-models'] })
      setMessage({ type: 'success', text: '模型列表已更新' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: any) => {
      setMessage({ type: 'error', text: err.response?.data?.detail || '获取模型失败' })
    },
  })

  const savePromptsMutation = useMutation({
    mutationFn: async () => {
      await api.put('/ai/settings', {
        translate_prompt: prompts.translate,
        summarize_prompt: prompts.summarize,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-settings'] })
      setMessage({ type: 'success', text: 'Prompt 已保存' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: any) => {
      setMessage({ type: 'error', text: err.response?.data?.detail || '保存失败' })
    },
  })

  const saveEmbeddingConfigMutation = useMutation({
    mutationFn: async () => {
      await api.put('/ai/settings', {
        embedding_provider_id: embeddingConfig.provider_id,
        embedding_model: embeddingConfig.model || null,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-settings'] })
      setMessage({ type: 'success', text: 'Embedding 模型已保存' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: any) => {
      setMessage({ type: 'error', text: err.response?.data?.detail || '保存失败' })
    },
  })

  const saveArgosConfigMutation = useMutation({
    mutationFn: async () => {
      await api.put('/ai/settings', {
        argos_source_language: argosSourceLanguage || 'en',
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-settings'] })
      setMessage({ type: 'success', text: '本地翻译设置已保存' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: any) => {
      setMessage({ type: 'error', text: err.response?.data?.detail || '保存失败' })
    },
  })

  const refreshArgosPackagesMutation = useMutation({
    mutationFn: async () => {
      const response = await api.get<ArgosPackagesResponse>('/ai/argos/packages', {
        params: { refresh: true },
      })
      return response.data
    },
    onSuccess: (data) => {
      queryClient.setQueryData(['argos-packages'], data)
      setMessage({
        type: data.available_error ? 'error' : 'success',
        text: data.available_error || 'Argos 语言包列表已刷新',
      })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: unknown) => {
      setMessage({ type: 'error', text: getApiErrorMessage(err, '刷新语言包列表失败') })
    },
  })

  const installArgosPackageMutation = useMutation({
    mutationFn: async (payload?: { source_language: string; target_language: string }) => {
      const response = await api.post<ArgosPackageInfo>('/ai/argos/packages/install', payload || argosInstallForm)
      return response.data
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['argos-packages'] })
      setMessage({
        type: 'success',
        text: `Argos 语言包已安装: ${data.source_language} -> ${data.target_language}`,
      })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: unknown) => {
      setMessage({ type: 'error', text: getApiErrorMessage(err, '安装语言包失败') })
    },
  })

  const uninstallArgosPackageMutation = useMutation({
    mutationFn: async (pkg: ArgosPackageInfo) => {
      const response = await api.delete<{ success: boolean; message: string }>(
        `/ai/argos/packages/${encodeURIComponent(pkg.source_language)}/${encodeURIComponent(pkg.target_language)}`
      )
      return response.data
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['argos-packages'] })
      setMessage({ type: 'success', text: data.message })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: unknown) => {
      setMessage({ type: 'error', text: getApiErrorMessage(err, '卸载语言包失败') })
    },
  })

  const testArgosPackageMutation = useMutation({
    mutationFn: async (payload?: { source_language: string; target_language: string; text?: string }) => {
      const response = await api.post<ArgosPackageTestResult>('/ai/argos/test', {
        source_language: payload?.source_language || argosTestForm.source_language,
        target_language: payload?.target_language || argosTestForm.target_language,
        text: payload?.text || argosTestForm.text,
      })
      return response.data
    },
    onSuccess: (data) => {
      setArgosTestResult(data)
      setMessage({ type: data.success ? 'success' : 'error', text: data.message })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: unknown) => {
      setArgosTestResult(null)
      setMessage({ type: 'error', text: getApiErrorMessage(err, '测试语言包失败') })
    },
  })

  const clearArgosLogsMutation = useMutation({
    mutationFn: async () => {
      const response = await api.delete<{ success: boolean; deleted: number }>('/ai/argos/translation-logs')
      return response.data
    },
    onSuccess: (data) => {
      setArgosLogPage(1)
      queryClient.invalidateQueries({ queryKey: ['argos-translation-logs'] })
      setMessage({ type: 'success', text: `已清除 ${data.deleted} 条本地翻译记录` })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: unknown) => {
      setMessage({ type: 'error', text: getApiErrorMessage(err, '清除本地翻译记录失败') })
    },
  })

  const addGoogleKeyMutation = useMutation({
    mutationFn: async () => {
      await api.post('/ai/google-translate-keys', buildGoogleKeyPayload(newGoogleKey, true))
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['google-translate-keys'] })
      setNewGoogleKey({
        name: '',
        api_key: '',
        is_active: true,
        limit_days: '',
        limit_articles: '',
        limit_characters: '',
      })
      setMessage({ type: 'success', text: 'Google API Key 已添加' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: unknown) => {
      setMessage({ type: 'error', text: getApiErrorMessage(err, '添加失败') })
    },
  })

  const updateGoogleKeyMutation = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: typeof googleKeyEdit }) => {
      await api.put(`/ai/google-translate-keys/${id}`, buildGoogleKeyPayload(data, true))
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['google-translate-keys'] })
      setEditingGoogleKeyId(null)
      setMessage({ type: 'success', text: 'Google API Key 已更新' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: unknown) => {
      setMessage({ type: 'error', text: getApiErrorMessage(err, '更新失败') })
    },
  })

  const deleteGoogleKeyMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/ai/google-translate-keys/${id}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['google-translate-keys'] })
      setMessage({ type: 'success', text: 'Google API Key 已删除' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: unknown) => {
      setMessage({ type: 'error', text: getApiErrorMessage(err, '删除失败') })
    },
  })

  const resetGoogleKeyMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.post(`/ai/google-translate-keys/${id}/reset`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['google-translate-keys'] })
      setMessage({ type: 'success', text: 'Google API Key 用量已重置' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: unknown) => {
      setMessage({ type: 'error', text: getApiErrorMessage(err, '重置失败') })
    },
  })

  const testGoogleKeyMutation = useMutation({
    mutationFn: async (id: number) => {
      const response = await api.post<{ success: boolean; message: string }>(`/ai/google-translate-keys/${id}/test`)
      return response.data
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['google-translate-keys'] })
      setMessage({ type: data.success ? 'success' : 'error', text: data.message })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: unknown) => {
      setMessage({ type: 'error', text: getApiErrorMessage(err, '测试失败') })
    },
  })

  const defaultModel = models.find(m => m.is_default)
  const activeGoogleKeyCount = googleTranslateKeys.filter((key) => key.is_active).length
  const installedArgosPackages = argosPackages?.installed || []
  const availableArgosPackages = argosPackages?.available || []
  const argosLogs = argosTranslationLogs?.items || []
  const argosLogTotal = argosTranslationLogs?.total || 0
  const argosLogTotalPages = argosTranslationLogs?.total_pages || 1
  const visibleAvailableArgosPackages = availableArgosPackages
    .filter((pkg) => !pkg.installed)
    .slice(0, 12)
  const selectedInstallPackageInstalled = installedArgosPackages.some(
    (pkg) =>
      pkg.source_language === argosInstallForm.source_language &&
      pkg.target_language === argosInstallForm.target_language
  )
  const argosPackagesErrorText = argosPackagesError
    ? getApiErrorMessage(argosPackagesError, '本地翻译语言包读取失败')
    : null

  const startGoogleKeyEdit = (key: GoogleTranslateKey) => {
    setEditingGoogleKeyId(key.id)
    setGoogleKeyEdit({
      name: key.name,
      api_key: '',
      is_active: key.is_active,
      limit_days: key.limit_days?.toString() || '',
      limit_articles: key.limit_articles?.toString() || '',
      limit_characters: key.limit_characters?.toString() || '',
    })
  }

  return (
    <div className="space-y-6">
      {message && (
        <div className={`p-3 rounded ${message.type === 'success' ? 'bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-400' : 'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-400'}`}>
          {message.text}
        </div>
      )}

      {/* Default Model Selection */}
      <div className="p-4 border dark:border-gray-700 rounded bg-primary-50 dark:bg-primary-900/30">
        <h2 className="text-lg font-semibold mb-3 dark:text-white">默认模型</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">用于 AI 翻译、整理和分析总结</p>
        <select
          value={defaultModel?.id || ''}
          onChange={(e) => e.target.value && setDefaultModelMutation.mutate(parseInt(e.target.value))}
          className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
          disabled={models.length === 0}
        >
          <option value="">请选择默认模型</option>
          {providers.map(provider => {
            const providerModels = models.filter(m => m.provider_id === provider.id)
            if (providerModels.length === 0) return null
            return (
              <optgroup key={provider.id} label={provider.name}>
                {providerModels.map(model => (
                  <option key={model.id} value={model.id}>
                    {model.model_id}
                  </option>
                ))}
              </optgroup>
            )
          })}
        </select>
        {models.length === 0 && (
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">请先添加 AI 渠道并获取模型</p>
        )}
      </div>

      {/* Embedding Model Configuration */}
      <div className="p-4 border dark:border-gray-700 rounded bg-green-50 dark:bg-green-900/30">
        <h2 className="text-lg font-semibold mb-3 dark:text-white">Embedding 模型</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-3">用于 AI 分析的语义搜索功能，需要 OpenAI 兼容的 Embedding API</p>
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">AI 渠道</label>
            <select
              value={embeddingConfig.provider_id || ''}
              onChange={(e) => setEmbeddingConfig({ ...embeddingConfig, provider_id: e.target.value ? parseInt(e.target.value) : null })}
              className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
            >
              <option value="">请选择渠道</option>
              {providers.map(provider => (
                <option key={provider.id} value={provider.id}>{provider.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">模型名称</label>
            <input
              type="text"
              value={embeddingConfig.model}
              onChange={(e) => setEmbeddingConfig({ ...embeddingConfig, model: e.target.value })}
              placeholder="text-embedding-3-small"
              className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
            />
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
              常用模型：text-embedding-3-small, text-embedding-3-large, text-embedding-ada-002
            </p>
          </div>
          <button
            onClick={() => saveEmbeddingConfigMutation.mutate()}
            disabled={saveEmbeddingConfigMutation.isPending || !embeddingConfig.provider_id}
            className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
          >
            保存 Embedding 配置
          </button>
        </div>
      </div>

      {/* Local Translation Configuration */}
      <div className="p-4 border dark:border-gray-700 rounded bg-emerald-50 dark:bg-emerald-900/30">
        <h2 className="text-lg font-semibold mb-3 dark:text-white flex items-center gap-2">
          <Languages className="w-5 h-5" /> 本地翻译
        </h2>
        <div className="space-y-4">
          <div className="flex gap-2 flex-wrap items-center">
            <select
              value={argosSourceLanguage}
              onChange={(e) => setArgosSourceLanguage(e.target.value)}
              className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
              aria-label="默认源语言"
            >
              {translationSourceLanguages.map((language) => (
                <option key={language.value} value={language.value}>{language.label}</option>
              ))}
            </select>
            <button
              onClick={() => saveArgosConfigMutation.mutate()}
              disabled={saveArgosConfigMutation.isPending}
              className="px-4 py-2 bg-emerald-600 text-white rounded hover:bg-emerald-700 disabled:opacity-50"
            >
              保存默认源语言
            </button>
            <button
              onClick={() => refreshArgosPackagesMutation.mutate()}
              disabled={refreshArgosPackagesMutation.isPending}
              className="flex items-center gap-1 px-3 py-2 border border-emerald-300 dark:border-emerald-700 text-emerald-700 dark:text-emerald-300 rounded hover:bg-emerald-100 dark:hover:bg-emerald-900/50 disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${refreshArgosPackagesMutation.isPending ? 'animate-spin' : ''}`} />
              刷新语言包
            </button>
            <button
              onClick={() => {
                setArgosLogPage(1)
                setShowArgosLogsModal(true)
              }}
              className="flex items-center gap-1 px-3 py-2 border border-emerald-300 dark:border-emerald-700 text-emerald-700 dark:text-emerald-300 rounded hover:bg-emerald-100 dark:hover:bg-emerald-900/50"
            >
              <History className="w-4 h-4" />
              翻译记录
            </button>
          </div>

          <div className="flex flex-wrap gap-2 text-xs text-gray-600 dark:text-gray-300">
            <span className="px-2 py-1 bg-white dark:bg-gray-800 border dark:border-gray-700 rounded">
              已安装 {installedArgosPackages.length}
            </span>
            <span className="px-2 py-1 bg-white dark:bg-gray-800 border dark:border-gray-700 rounded">
              可安装 {availableArgosPackages.length}
            </span>
            {argosPackagesLoading && <span className="px-2 py-1 text-emerald-700 dark:text-emerald-300">加载中</span>}
          </div>

          {(argosPackagesErrorText || argosPackages?.available_error) && (
            <div className="p-2 text-sm text-red-700 dark:text-red-300 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded">
              {argosPackagesErrorText || argosPackages?.available_error}
            </div>
          )}

          <div className="grid gap-3 lg:grid-cols-2">
            <div className="border dark:border-gray-700 rounded bg-white dark:bg-gray-800 overflow-hidden">
              <div className="px-3 py-2 bg-gray-50 dark:bg-gray-700 text-sm font-medium dark:text-white">
                已安装语言包
              </div>
              <div className="divide-y dark:divide-gray-700">
                {installedArgosPackages.length === 0 && (
                  <div className="p-3 text-sm text-gray-500 dark:text-gray-400">暂无已安装语言包</div>
                )}
                {installedArgosPackages.map((pkg) => (
                  <div key={`${pkg.source_language}-${pkg.target_language}`} className="p-3 flex items-center gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium dark:text-white truncate">
                        {getTranslationLanguageLabel(pkg.source_language)} → {getTranslationLanguageLabel(pkg.target_language)}
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
                        {pkg.source_language} → {pkg.target_language}
                        {pkg.package_version ? ` · v${pkg.package_version}` : ''}
                      </div>
                    </div>
                    <button
                      onClick={() => testArgosPackageMutation.mutate({
                        source_language: pkg.source_language,
                        target_language: pkg.target_language,
                      })}
                      disabled={testArgosPackageMutation.isPending}
                      className="px-2 py-1 text-xs border dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50 dark:text-gray-200"
                    >
                      测试
                    </button>
                    <button
                      onClick={() => uninstallArgosPackageMutation.mutate(pkg)}
                      disabled={uninstallArgosPackageMutation.isPending}
                      className="p-1.5 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 rounded disabled:opacity-50"
                      title="卸载语言包"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            </div>

            <div className="border dark:border-gray-700 rounded bg-white dark:bg-gray-800 p-3 space-y-3">
              <div className="text-sm font-medium dark:text-white">安装语言包</div>
              <div className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
                <select
                  value={argosInstallForm.source_language}
                  onChange={(e) => setArgosInstallForm({ ...argosInstallForm, source_language: e.target.value })}
                  className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
                  aria-label="安装源语言"
                >
                  {translationSourceLanguages.map((language) => (
                    <option key={language.value} value={language.value}>{language.label}</option>
                  ))}
                </select>
                <select
                  value={argosInstallForm.target_language}
                  onChange={(e) => setArgosInstallForm({ ...argosInstallForm, target_language: e.target.value })}
                  className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
                  aria-label="安装目标语言"
                >
                  {translationSourceLanguages.map((language) => (
                    <option key={language.value} value={language.value}>{language.label}</option>
                  ))}
                </select>
                <button
                  onClick={() => installArgosPackageMutation.mutate(argosInstallForm)}
                  disabled={
                    installArgosPackageMutation.isPending ||
                    argosInstallForm.source_language === argosInstallForm.target_language ||
                    selectedInstallPackageInstalled
                  }
                  className="flex items-center justify-center gap-1 px-3 py-2 bg-emerald-600 text-white rounded hover:bg-emerald-700 disabled:opacity-50"
                >
                  <Download className="w-4 h-4" /> 安装
                </button>
              </div>
              {selectedInstallPackageInstalled && (
                <div className="text-xs text-emerald-700 dark:text-emerald-300">当前语言包已安装</div>
              )}

              <div className="space-y-2">
                <div className="text-sm font-medium dark:text-white">可安装语言包</div>
                {visibleAvailableArgosPackages.length === 0 ? (
                  <div className="text-sm text-gray-500 dark:text-gray-400">暂无可安装列表</div>
                ) : (
                  <div className="grid gap-2">
                    {visibleAvailableArgosPackages.map((pkg) => (
                      <div key={`${pkg.source_language}-${pkg.target_language}`} className="flex items-center gap-2 text-sm">
                        <span className="flex-1 min-w-0 truncate dark:text-gray-200">
                          {getTranslationLanguageLabel(pkg.source_language)} → {getTranslationLanguageLabel(pkg.target_language)}
                        </span>
                        <button
                          onClick={() => installArgosPackageMutation.mutate({
                            source_language: pkg.source_language,
                            target_language: pkg.target_language,
                          })}
                          disabled={installArgosPackageMutation.isPending}
                          className="px-2 py-1 text-xs border border-emerald-300 dark:border-emerald-700 text-emerald-700 dark:text-emerald-300 rounded hover:bg-emerald-50 dark:hover:bg-emerald-900/30 disabled:opacity-50"
                        >
                          安装
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="border dark:border-gray-700 rounded bg-white dark:bg-gray-800 p-3 space-y-3">
            <div className="text-sm font-medium dark:text-white">翻译测试</div>
            <div className="grid gap-2 md:grid-cols-[150px_150px_1fr_auto]">
              <select
                value={argosTestForm.source_language}
                onChange={(e) => setArgosTestForm({ ...argosTestForm, source_language: e.target.value })}
                className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
                aria-label="测试源语言"
              >
                {translationSourceLanguages.map((language) => (
                  <option key={language.value} value={language.value}>{language.label}</option>
                ))}
              </select>
              <select
                value={argosTestForm.target_language}
                onChange={(e) => setArgosTestForm({ ...argosTestForm, target_language: e.target.value })}
                className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
                aria-label="测试目标语言"
              >
                {translationSourceLanguages.map((language) => (
                  <option key={language.value} value={language.value}>{language.label}</option>
                ))}
              </select>
              <input
                type="text"
                value={argosTestForm.text}
                onChange={(e) => setArgosTestForm({ ...argosTestForm, text: e.target.value })}
                className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
                placeholder="测试文本"
              />
              <button
                onClick={() => testArgosPackageMutation.mutate(argosTestForm)}
                disabled={
                  testArgosPackageMutation.isPending ||
                  !argosTestForm.text.trim() ||
                  argosTestForm.source_language === argosTestForm.target_language
                }
                className="px-4 py-2 bg-emerald-600 text-white rounded hover:bg-emerald-700 disabled:opacity-50"
              >
                测试
              </button>
            </div>
            {argosTestResult && (
              <div className={`p-2 text-sm border rounded ${
                argosTestResult.success
                  ? 'text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-900/30 border-emerald-200 dark:border-emerald-800'
                  : 'text-red-700 dark:text-red-300 bg-red-50 dark:bg-red-900/30 border-red-200 dark:border-red-800'
              }`}>
                <div>{argosTestResult.message}</div>
                {argosTestResult.translation && (
                  <div className="mt-1 text-gray-700 dark:text-gray-200 break-words">{argosTestResult.translation}</div>
                )}
              </div>
            )}
          </div>

          {showArgosLogsModal && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
              <div className="w-full max-w-6xl max-h-[85vh] bg-white dark:bg-gray-900 border dark:border-gray-700 rounded shadow-xl flex flex-col overflow-hidden">
                <div className="px-4 py-3 border-b dark:border-gray-700 flex flex-wrap items-center gap-2">
                  <div className="text-base font-medium dark:text-white">本地翻译记录</div>
                  <span className="text-xs text-gray-500 dark:text-gray-400">共 {argosLogTotal} 条</span>
                  <button
                    onClick={() => queryClient.invalidateQueries({ queryKey: ['argos-translation-logs'] })}
                    className="ml-auto p-1.5 text-gray-500 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded"
                    title="刷新记录"
                  >
                    <RefreshCw className={`w-4 h-4 ${argosLogsLoading ? 'animate-spin' : ''}`} />
                  </button>
                  <button
                    onClick={() => {
                      if (window.confirm('确定清除所有本地翻译记录？')) {
                        clearArgosLogsMutation.mutate()
                      }
                    }}
                    disabled={clearArgosLogsMutation.isPending || argosLogTotal === 0}
                    className="flex items-center gap-1 px-2 py-1.5 text-sm text-red-600 dark:text-red-300 border border-red-200 dark:border-red-800 rounded hover:bg-red-50 dark:hover:bg-red-900/30 disabled:opacity-50"
                  >
                    <Trash2 className="w-4 h-4" />
                    清除
                  </button>
                  <button
                    onClick={() => setShowArgosLogsModal(false)}
                    className="p-1.5 text-gray-500 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded"
                    title="关闭"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
                <div className="flex-1 overflow-auto">
                  <table className="w-full min-w-[920px] text-sm">
                    <thead className="sticky top-0 bg-gray-50 dark:bg-gray-800 text-gray-600 dark:text-gray-300">
                      <tr>
                        <th className="p-3 text-left">文章</th>
                        <th className="p-3 text-left">订阅源</th>
                        <th className="p-3 text-left">语言</th>
                        <th className="p-3 text-left">字符</th>
                        <th className="p-3 text-left">耗时</th>
                        <th className="p-3 text-left">状态</th>
                        <th className="p-3 text-left">时间</th>
                        <th className="p-3 text-left">错误</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y dark:divide-gray-700">
                      {argosLogs.map((log) => (
                        <tr key={log.id} className="dark:text-gray-100">
                          <td className="p-3 max-w-[240px] truncate" title={log.article_title || ''}>
                            {log.article_title || '-'}
                          </td>
                          <td className="p-3 max-w-[160px] truncate text-gray-600 dark:text-gray-300" title={log.feed_title || ''}>
                            {log.feed_title || '-'}
                          </td>
                          <td className="p-3 text-gray-600 dark:text-gray-300">
                            {log.source_language} → {log.target_language}
                          </td>
                          <td className="p-3 text-gray-600 dark:text-gray-300">
                            {(log.title_chars + log.content_chars).toLocaleString()}
                            <span className="text-xs text-gray-400 dark:text-gray-500 ml-1">
                              ({log.title_chars}/{log.content_chars})
                            </span>
                          </td>
                          <td className="p-3 font-mono text-gray-700 dark:text-gray-200">
                            {formatDurationMs(log.duration_ms)}
                          </td>
                          <td className={`p-3 ${getArgosLogStatusClass(log.status)}`}>
                            {getArgosLogStatusLabel(log.status)}
                          </td>
                          <td className="p-3 text-gray-500 dark:text-gray-400">
                            <div>{formatDateTime(log.started_at)}</div>
                            {log.completed_at && (
                              <div className="text-xs">{formatDateTime(log.completed_at)}</div>
                            )}
                          </td>
                          <td className="p-3 max-w-[220px] truncate text-gray-500 dark:text-gray-400" title={log.error || ''}>
                            {log.error || '-'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {!argosLogsLoading && argosLogs.length === 0 && (
                    <div className="p-4 text-center text-gray-500 dark:text-gray-400">暂无本地翻译记录</div>
                  )}
                  {argosLogsLoading && argosLogs.length === 0 && (
                    <div className="p-4 text-center text-gray-500 dark:text-gray-400">加载中...</div>
                  )}
                </div>
                {argosLogTotalPages > 1 && (
                  <div className="px-4 py-3 border-t dark:border-gray-700 flex items-center justify-end gap-2 text-sm">
                    <button
                      onClick={() => setArgosLogPage((page) => Math.max(1, page - 1))}
                      disabled={argosLogPage <= 1}
                      className="px-2 py-1 border dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50 dark:text-gray-200"
                    >
                      上一页
                    </button>
                    <span className="text-gray-500 dark:text-gray-400">
                      {argosLogPage} / {argosLogTotalPages}
                    </span>
                    <button
                      onClick={() => setArgosLogPage((page) => Math.min(argosLogTotalPages, page + 1))}
                      disabled={argosLogPage >= argosLogTotalPages}
                      className="px-2 py-1 border dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50 dark:text-gray-200"
                    >
                      下一页
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Google Translate API Keys */}
      <div className="p-4 border dark:border-gray-700 rounded bg-yellow-50 dark:bg-yellow-900/30">
        <h2 className="text-lg font-semibold mb-3 dark:text-white flex items-center gap-2">
          <Languages className="w-5 h-5" /> Google 翻译设置
        </h2>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-3">
          可配置多个 Google Cloud Translation API Key，并按天数、文章数或字符数达到阈值后自动切换。未配置付费 Key 时仍使用免费接口。
        </p>
        <div className="space-y-3">
          <div className="grid gap-2 md:grid-cols-[1fr_1fr_90px_110px_130px_130px]">
            <input
              type="text"
              value={newGoogleKey.name}
              onChange={(e) => setNewGoogleKey({ ...newGoogleKey, name: e.target.value })}
              placeholder="名称"
              className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
            />
            <input
              type="password"
              value={newGoogleKey.api_key}
              onChange={(e) => setNewGoogleKey({ ...newGoogleKey, api_key: e.target.value })}
              placeholder="Google Translate API Key"
              className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
            />
            <input
              type="number"
              min={1}
              value={newGoogleKey.limit_days}
              onChange={(e) => setNewGoogleKey({ ...newGoogleKey, limit_days: e.target.value })}
              placeholder="天数"
              className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
            />
            <input
              type="number"
              min={1}
              value={newGoogleKey.limit_articles}
              onChange={(e) => setNewGoogleKey({ ...newGoogleKey, limit_articles: e.target.value })}
              placeholder="文章数"
              className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
            />
            <input
              type="number"
              min={1}
              value={newGoogleKey.limit_characters}
              onChange={(e) => setNewGoogleKey({ ...newGoogleKey, limit_characters: e.target.value })}
              placeholder="字符数"
              className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
            />
            <button
              onClick={() => addGoogleKeyMutation.mutate()}
              disabled={!newGoogleKey.name.trim() || !newGoogleKey.api_key.trim() || addGoogleKeyMutation.isPending}
              className="flex items-center justify-center gap-1 px-3 py-2 bg-yellow-600 text-white rounded hover:bg-yellow-700 disabled:opacity-50"
            >
              <Plus className="w-4 h-4" /> 添加
            </button>
          </div>
          <label className="inline-flex items-center gap-2 text-sm text-gray-600 dark:text-gray-300">
            <input
              type="checkbox"
              checked={newGoogleKey.is_active}
              onChange={(e) => setNewGoogleKey({ ...newGoogleKey, is_active: e.target.checked })}
            />
            添加后启用
          </label>
          <div className="text-xs text-gray-500 dark:text-gray-400">
            获取 API Key: <a href="https://console.cloud.google.com/apis/credentials" target="_blank" rel="noopener noreferrer" className="text-primary-500 hover:underline">Google Cloud Console</a>。当前共 {googleTranslateKeys.length} 个 Key，启用 {activeGoogleKeyCount} 个。
          </div>

          <div className="overflow-x-auto border dark:border-gray-700 rounded bg-white dark:bg-gray-800">
            <table className="w-full min-w-[960px] text-sm">
              <thead className="bg-gray-50 dark:bg-gray-700 text-gray-600 dark:text-gray-300">
                <tr>
                  <th className="p-3 text-left">Key</th>
                  <th className="p-3 text-left">切换阈值</th>
                  <th className="p-3 text-left">当前用量</th>
                  <th className="p-3 text-left">状态</th>
                  <th className="p-3 text-left">最近错误</th>
                  <th className="p-3 text-right">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-gray-700">
                {googleTranslateKeys.map((key) => (
                  <tr key={key.id} className="dark:text-gray-100">
                    {editingGoogleKeyId === key.id ? (
                      <>
                        <td className="p-3 space-y-2">
                          <input
                            type="text"
                            value={googleKeyEdit.name}
                            onChange={(e) => setGoogleKeyEdit({ ...googleKeyEdit, name: e.target.value })}
                            className="w-full px-2 py-1 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white"
                          />
                          <input
                            type="password"
                            value={googleKeyEdit.api_key}
                            onChange={(e) => setGoogleKeyEdit({ ...googleKeyEdit, api_key: e.target.value })}
                            placeholder="新 Key，留空不变"
                            className="w-full px-2 py-1 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white"
                          />
                        </td>
                        <td className="p-3">
                          <div className="grid grid-cols-3 gap-2">
                            <input
                              type="number"
                              min={1}
                              value={googleKeyEdit.limit_days}
                              onChange={(e) => setGoogleKeyEdit({ ...googleKeyEdit, limit_days: e.target.value })}
                              placeholder="天"
                              className="px-2 py-1 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white"
                            />
                            <input
                              type="number"
                              min={1}
                              value={googleKeyEdit.limit_articles}
                              onChange={(e) => setGoogleKeyEdit({ ...googleKeyEdit, limit_articles: e.target.value })}
                              placeholder="文章"
                              className="px-2 py-1 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white"
                            />
                            <input
                              type="number"
                              min={1}
                              value={googleKeyEdit.limit_characters}
                              onChange={(e) => setGoogleKeyEdit({ ...googleKeyEdit, limit_characters: e.target.value })}
                              placeholder="字符"
                              className="px-2 py-1 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white"
                            />
                          </div>
                        </td>
                        <td className="p-3 text-gray-500 dark:text-gray-400">保存后生效</td>
                        <td className="p-3">
                          <label className="inline-flex items-center gap-2">
                            <input
                              type="checkbox"
                              checked={googleKeyEdit.is_active}
                              onChange={(e) => setGoogleKeyEdit({ ...googleKeyEdit, is_active: e.target.checked })}
                            />
                            启用
                          </label>
                        </td>
                        <td className="p-3 text-gray-500 dark:text-gray-400">-</td>
                        <td className="p-3">
                          <div className="flex justify-end gap-1">
                            <button
                              onClick={() => updateGoogleKeyMutation.mutate({ id: key.id, data: googleKeyEdit })}
                              disabled={!googleKeyEdit.name.trim() || updateGoogleKeyMutation.isPending}
                              className="p-2 text-green-600 dark:text-green-400 hover:bg-green-50 dark:hover:bg-green-900/30 rounded disabled:opacity-50"
                              title="保存"
                            >
                              <Check className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => setEditingGoogleKeyId(null)}
                              className="p-2 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
                              title="取消"
                            >
                              <X className="w-4 h-4" />
                            </button>
                          </div>
                        </td>
                      </>
                    ) : (
                      <>
                        <td className="p-3">
                          <div className="font-medium">{key.name}</div>
                          <div className="text-xs text-gray-500 dark:text-gray-400 font-mono">{key.masked_api_key}</div>
                        </td>
                        <td className="p-3 text-gray-600 dark:text-gray-300">
                          <div>天数: {key.limit_days ?? '不限'}</div>
                          <div>文章: {key.limit_articles ?? '不限'}</div>
                          <div>字符: {key.limit_characters ?? '不限'}</div>
                        </td>
                        <td className="p-3 text-gray-600 dark:text-gray-300">
                          <div>{key.usage_article_count} 篇</div>
                          <div>{key.usage_character_count.toLocaleString()} 字符</div>
                          <div className="text-xs text-gray-400 dark:text-gray-500">
                            {key.usage_started_at ? new Date(key.usage_started_at).toLocaleDateString('zh-CN') : '未开始'}
                          </div>
                        </td>
                        <td className="p-3">
                          <div className={key.is_active ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
                            {key.is_active ? '启用' : '停用'}
                          </div>
                          {key.is_exhausted && (
                            <div className="text-xs text-yellow-600 dark:text-yellow-400">已达阈值</div>
                          )}
                          <div className="text-xs text-gray-400 dark:text-gray-500">失败 {key.fail_count}/5</div>
                        </td>
                        <td className="p-3 max-w-[220px] truncate text-gray-500 dark:text-gray-400" title={key.last_error || ''}>
                          {key.last_error || '-'}
                        </td>
                        <td className="p-3">
                          <div className="flex justify-end gap-1">
                            <button
                              onClick={() => testGoogleKeyMutation.mutate(key.id)}
                              disabled={testGoogleKeyMutation.isPending}
                              className="p-2 text-primary-500 hover:bg-primary-50 dark:hover:bg-primary-900/30 rounded disabled:opacity-50"
                              title="测试"
                            >
                              <RefreshCw className={`w-4 h-4 ${testGoogleKeyMutation.isPending ? 'animate-spin' : ''}`} />
                            </button>
                            <button
                              onClick={() => startGoogleKeyEdit(key)}
                              className="p-2 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
                              title="编辑"
                            >
                              <Edit2 className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => resetGoogleKeyMutation.mutate(key.id)}
                              disabled={resetGoogleKeyMutation.isPending}
                              className="p-2 text-green-600 dark:text-green-400 hover:bg-green-50 dark:hover:bg-green-900/30 rounded disabled:opacity-50"
                              title="重置用量"
                            >
                              <Check className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => updateGoogleKeyMutation.mutate({
                                id: key.id,
                                data: {
                                  name: key.name,
                                  api_key: '',
                                  is_active: !key.is_active,
                                  limit_days: key.limit_days?.toString() || '',
                                  limit_articles: key.limit_articles?.toString() || '',
                                  limit_characters: key.limit_characters?.toString() || '',
                                },
                              })}
                              disabled={updateGoogleKeyMutation.isPending}
                              className="p-2 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded disabled:opacity-50"
                              title={key.is_active ? '停用' : '启用'}
                            >
                              {key.is_active ? <X className="w-4 h-4" /> : <Check className="w-4 h-4" />}
                            </button>
                            <button
                              onClick={() => deleteGoogleKeyMutation.mutate(key.id)}
                              disabled={deleteGoogleKeyMutation.isPending}
                              className="p-2 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 rounded disabled:opacity-50"
                              title="删除"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
            {googleTranslateKeys.length === 0 && (
              <div className="p-4 text-center text-gray-500 dark:text-gray-400">暂无付费 API Key，将使用免费接口</div>
            )}
          </div>
        </div>
      </div>

      {/* Providers */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold dark:text-white">AI 渠道</h2>
          <button
            onClick={() => setShowAddProvider(true)}
            className="flex items-center gap-1 px-3 py-2 bg-primary-600 text-white rounded hover:bg-primary-700"
          >
            <Plus className="w-4 h-4" /> 添加渠道
          </button>
        </div>

        {showAddProvider && (
          <div className="mb-4 p-4 border dark:border-gray-600 rounded bg-gray-50 dark:bg-gray-700 space-y-3">
            <input
              type="text"
              placeholder="渠道名称"
              value={newProvider.name}
              onChange={(e) => setNewProvider({ ...newProvider, name: e.target.value })}
              className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
            />
            <select
              value={newProvider.type}
              onChange={(e) => setNewProvider({ ...newProvider, type: e.target.value as any })}
              className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
            >
              <option value="openai">OpenAI</option>
              <option value="gemini">Google Gemini</option>
              <option value="openai_compatible">OpenAI 兼容</option>
            </select>
            <input
              type="password"
              placeholder="API Key"
              value={newProvider.api_key}
              onChange={(e) => setNewProvider({ ...newProvider, api_key: e.target.value })}
              className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
            />
            {newProvider.type === 'openai_compatible' && (
              <input
                type="url"
                placeholder="Base URL (如 https://api.example.com/v1)"
                value={newProvider.base_url}
                onChange={(e) => setNewProvider({ ...newProvider, base_url: e.target.value })}
                className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
              />
            )}
            <div className="flex gap-2">
              <button
                onClick={() => addProviderMutation.mutate()}
                disabled={!newProvider.name || !newProvider.api_key || addProviderMutation.isPending}
                className="px-4 py-2 bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50"
              >
                保存
              </button>
              <button
                onClick={() => setShowAddProvider(false)}
                className="px-4 py-2 border dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-600 dark:text-gray-200"
              >
                取消
              </button>
            </div>
          </div>
        )}

        <div className="border dark:border-gray-700 rounded divide-y dark:divide-gray-700">
          {providers.map((provider) => {
            const providerModels = models.filter(m => m.provider_id === provider.id)
            return (
              <div key={provider.id} className="p-4">
                <div className="flex items-center gap-4 mb-2">
                  <div className="flex-1">
                    <h3 className="font-medium dark:text-white">{provider.name}</h3>
                    <p className="text-sm text-gray-500 dark:text-gray-400">{provider.type}</p>
                  </div>
                  <button
                    onClick={() => fetchModelsMutation.mutate(provider.id)}
                    disabled={fetchModelsMutation.isPending}
                    className="px-3 py-1 text-sm border dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-700 dark:text-gray-200"
                  >
                    获取模型
                  </button>
                  <button
                    onClick={() => deleteProviderMutation.mutate(provider.id)}
                    className="p-2 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 rounded"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
                {providerModels.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {providerModels.map(model => (
                      <span
                        key={model.id}
                        className={`px-2 py-0.5 text-xs rounded ${model.is_default ? 'bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-400' : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300'}`}
                      >
                        {model.model_id}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
          {providers.length === 0 && (
            <div className="p-4 text-center text-gray-500 dark:text-gray-400">暂无 AI 渠道</div>
          )}
        </div>
      </div>

      {/* Prompts */}
      <div>
        <h2 className="text-lg font-semibold mb-4 dark:text-white">Prompt 设置</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              翻译 Prompt
              <span className="text-gray-400 font-normal ml-2">（使用 {'{target_language}'} 作为目标语言占位符）</span>
            </label>
            <textarea
              value={prompts.translate}
              onChange={(e) => setPrompts({ ...prompts, translate: e.target.value })}
              className="w-full px-3 py-2 border dark:border-gray-600 rounded h-24 text-sm bg-white dark:bg-gray-700 dark:text-white"
              placeholder="You are a translator..."
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              整理 Prompt
            </label>
            <textarea
              value={prompts.summarize}
              onChange={(e) => setPrompts({ ...prompts, summarize: e.target.value })}
              className="w-full px-3 py-2 border dark:border-gray-600 rounded h-24 text-sm bg-white dark:bg-gray-700 dark:text-white"
              placeholder="You are a summarizer..."
            />
          </div>
          <button
            onClick={() => savePromptsMutation.mutate()}
            disabled={savePromptsMutation.isPending}
            className="px-4 py-2 bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50"
          >
            保存 Prompt
          </button>
        </div>
      </div>
    </div>
  )
}

function RulesTab() {
  const queryClient = useQueryClient()
  const { syncIntervals, defaultSyncInterval } = useSyncIntervals()
  const [showAddRule, setShowAddRule] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [showPromptEditor, setShowPromptEditor] = useState(false)
  const [customPrompt, setCustomPrompt] = useState('')
  const getEmptyRule = () => ({
    name: '',
    target_url: '',
    rule_type: 'general' as 'general' | 'telegram',
    cookies: '',
    list_selector: '',
    title_selector: '',
    link_selector: '',
    content_selector: '',
    date_selector: '',
    category_id: null as number | null,
    fetch_interval: defaultSyncInterval,
    use_playwright: false,
    auto_translate: false,
    auto_summarize: false,
    source_language: '',
    target_language: 'zh-CN',
    translate_method: 'none' as TranslateMethod,
    is_active: true,
  })
  const [formData, setFormData] = useState(getEmptyRule())

  // Fetch default prompt
  const { data: defaultPromptData } = useQuery({
    queryKey: ['default-generate-prompt'],
    queryFn: async () => {
      const response = await api.get<{ prompt: string }>('/rules/generate/default-prompt')
      return response.data
    },
  })

  const { data: categories = [] } = useQuery({
    queryKey: ['categories'],
    queryFn: async () => {
      const response = await api.get<Category[]>('/categories')
      return response.data
    },
  })

  const { data: rules = [] } = useQuery({
    queryKey: ['custom-rules'],
    queryFn: async () => {
      const response = await api.get<CustomRule[]>('/rules')
      return response.data
    },
  })

  const { data: aiModels = [] } = useQuery({
    queryKey: ['ai-models'],
    queryFn: async () => {
      const response = await api.get<AIModel[]>('/ai/models')
      return response.data
    },
  })
  const hasDefaultModel = aiModels.some((model) => model.is_default)

  const addRuleMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        ...formData,
        cookies: formData.cookies || null,
        link_selector: formData.link_selector || null,
        content_selector: formData.content_selector || null,
        date_selector: formData.date_selector || null,
        auto_translate: formData.translate_method !== 'none',
        source_language: formData.translate_method === 'argos' && formData.source_language ? formData.source_language : null,
        target_language: formData.translate_method !== 'none' ? formData.target_language : null,
      }
      await api.post('/rules', payload)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['custom-rules'] })
      queryClient.invalidateQueries({ queryKey: ['feeds'] })
      setShowAddRule(false)
      setFormData(getEmptyRule())
      setMessage({ type: 'success', text: '规则添加成功，点击刷新按钮立即抓取' })
      setTimeout(() => setMessage(null), 5000)
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      setMessage({ type: 'error', text: detail || '添加失败' })
    },
  })

  const updateRuleMutation = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: typeof formData }) => {
      const payload = {
        ...data,
        cookies: data.cookies || null,
        link_selector: data.link_selector || null,
        content_selector: data.content_selector || null,
        date_selector: data.date_selector || null,
        auto_translate: data.translate_method !== 'none',
        source_language: data.translate_method === 'argos' && data.source_language ? data.source_language : null,
        target_language: data.translate_method !== 'none' ? data.target_language : null,
      }
      await api.put(`/rules/${id}`, payload)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['custom-rules'] })
      queryClient.invalidateQueries({ queryKey: ['feeds'] })
      setEditingId(null)
      setFormData(getEmptyRule())
      setMessage({ type: 'success', text: '规则已更新' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      setMessage({ type: 'error', text: detail || '更新失败' })
    },
  })

  const deleteRuleMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/rules/${id}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['custom-rules'] })
      queryClient.invalidateQueries({ queryKey: ['feeds'] })
      setMessage({ type: 'success', text: '规则已删除' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      setMessage({ type: 'error', text: detail || '删除失败' })
    },
  })

  const executeRuleMutation = useMutation({
    mutationFn: async (id: number) => {
      const response = await api.post<{ success: boolean; articles_found: number }>(`/rules/${id}/execute`)
      return response.data
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['custom-rules'] })
      queryClient.invalidateQueries({ queryKey: ['feeds'] })
      queryClient.invalidateQueries({ queryKey: ['articles'] })
      setMessage({ type: 'success', text: `抓取完成，新增 ${data.articles_found} 篇文章` })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      setMessage({ type: 'error', text: detail || '抓取失败' })
    },
  })

  const testRuleMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        target_url: formData.target_url,
        list_selector: formData.list_selector,
        title_selector: formData.title_selector,
        link_selector: formData.link_selector || null,
        content_selector: formData.content_selector || null,
        date_selector: formData.date_selector || null,
        use_playwright: formData.use_playwright,
      }
      const response = await api.post('/rules/test', payload)
      return response.data
    },
  })

  const generateRuleMutation = useMutation({
    mutationFn: async (url: string) => {
      const response = await api.post<{
        success: boolean
        name?: string
        list_selector?: string
        title_selector?: string
        link_selector?: string
        content_selector?: string
        date_selector?: string
        error?: string
      }>('/rules/generate', { 
        target_url: url,
        custom_prompt: customPrompt || null
      })
      return response.data
    },
    onSuccess: (data) => {
      if (data.success) {
        setFormData(prev => ({
          ...prev,
          name: data.name || prev.name,
          list_selector: data.list_selector || '',
          title_selector: data.title_selector || '',
          link_selector: data.link_selector || '',
          content_selector: data.content_selector || '',
          date_selector: data.date_selector || '',
        }))
        setMessage({ type: 'success', text: 'AI 已生成规则，请检查并测试' })
        setTimeout(() => setMessage(null), 5000)
      } else {
        setMessage({ type: 'error', text: data.error || 'AI 生成失败' })
      }
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      setMessage({ type: 'error', text: detail || 'AI 生成失败' })
    },
  })

  const startEdit = (rule: CustomRule) => {
    setEditingId(rule.id)
    setShowAddRule(false)
    setFormData({
      name: rule.name,
      target_url: rule.target_url,
      rule_type: (rule.rule_type as 'general' | 'telegram') || 'general',
      cookies: rule.cookies || '',
      list_selector: rule.list_selector,
      title_selector: rule.title_selector,
      link_selector: rule.link_selector || '',
      content_selector: rule.content_selector || '',
      date_selector: rule.date_selector || '',
      category_id: rule.category_id,
      fetch_interval: rule.fetch_interval,
      use_playwright: rule.use_playwright,
      auto_translate: rule.auto_translate,
      auto_summarize: rule.auto_summarize,
      source_language: rule.source_language || '',
      target_language: rule.target_language || 'zh-CN',
      translate_method: rule.translate_method || (rule.auto_translate ? 'ai' : 'none'),
      is_active: rule.is_active,
    })
  }

  const cancelEdit = () => {
    setEditingId(null)
    setShowAddRule(false)
    setFormData(getEmptyRule())
  }

  const handleRuleTypeChange = (type: 'general' | 'telegram') => {
    if (type === 'telegram') {
      setFormData({
        ...formData,
        rule_type: type,
        list_selector: '.tgme_widget_message_wrap',
        title_selector: '.tgme_widget_message_text',
        link_selector: '.tgme_widget_message_date',
        content_selector: '.tgme_widget_message_text',
      })
    } else {
      setFormData({
        ...formData,
        rule_type: type,
        list_selector: '',
        title_selector: '',
        link_selector: '',
        content_selector: '',
      })
    }
  }

  const renderForm = (isEdit: boolean) => (
    <div className="mb-4 p-4 border dark:border-gray-600 rounded bg-gray-50 dark:bg-gray-700 space-y-3">
      <div className="flex gap-2">
        <select
          value={formData.rule_type}
          onChange={(e) => handleRuleTypeChange(e.target.value as 'general' | 'telegram')}
          className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
        >
          <option value="general">通用规则</option>
          <option value="telegram">Telegram 频道</option>
        </select>
        <input
          type="text"
          placeholder="规则名称"
          value={formData.name}
          onChange={(e) => setFormData({ ...formData, name: e.target.value })}
          className="flex-1 px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
        />
      </div>
      <div className="flex gap-2">
        <input
          type="url"
          placeholder={
            formData.rule_type === 'telegram' ? 'Telegram 频道链接 (如 https://t.me/s/channel_name)' :
            '目标网址'
          }
          value={formData.target_url}
          onChange={(e) => setFormData({ ...formData, target_url: e.target.value })}
          className="flex-1 px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
        />
        {formData.rule_type === 'general' && (
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => generateRuleMutation.mutate(formData.target_url)}
              disabled={!formData.target_url || generateRuleMutation.isPending}
              className="px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700 disabled:opacity-50 whitespace-nowrap"
            >
              {generateRuleMutation.isPending ? '分析中...' : '🤖 AI 生成'}
            </button>
            <button
              type="button"
              onClick={() => {
                if (!customPrompt && defaultPromptData?.prompt) {
                  setCustomPrompt(defaultPromptData.prompt)
                }
                setShowPromptEditor(!showPromptEditor)
              }}
              className="px-3 py-2 border dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-600 dark:text-gray-200 text-sm"
            >
              {showPromptEditor ? '收起 Prompt' : '编辑 Prompt'}
            </button>
          </div>
        )}
      </div>
      {formData.rule_type === 'general' && showPromptEditor && (
        <div className="p-3 bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-800 rounded">
          <div className="flex items-center justify-between mb-2">
            <label className="text-sm font-medium text-purple-800 dark:text-purple-300">AI 生成 Prompt</label>
            <button
              type="button"
              onClick={() => setCustomPrompt(defaultPromptData?.prompt || '')}
              className="text-xs text-purple-600 dark:text-purple-400 hover:underline"
            >
              恢复默认
            </button>
          </div>
          <textarea
            value={customPrompt || defaultPromptData?.prompt || ''}
            onChange={(e) => setCustomPrompt(e.target.value)}
            className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white text-xs h-48 font-mono"
            placeholder="AI 生成规则的 Prompt..."
          />
          <p className="text-xs text-purple-600 dark:text-purple-400 mt-1">
            可用变量: {'{target_url}'}, {'{page_title}'}, {'{html_content}'}
          </p>
        </div>
      )}
      {formData.rule_type === 'general' && (
        <>
          <input
            type="text"
            placeholder="列表选择器 (CSS Selector)"
            value={formData.list_selector}
            onChange={(e) => setFormData({ ...formData, list_selector: e.target.value })}
            className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
          />
          <input
            type="text"
            placeholder="链接选择器 (可选，留空则用标题生成ID)"
            value={formData.link_selector}
            onChange={(e) => setFormData({ ...formData, link_selector: e.target.value })}
            className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
          />
          <input
            type="text"
            placeholder="内容选择器 (可选)"
            value={formData.content_selector}
            onChange={(e) => setFormData({ ...formData, content_selector: e.target.value })}
            className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
          />
          <input
            type="text"
            placeholder="日期选择器 (可选)"
            value={formData.date_selector}
            onChange={(e) => setFormData({ ...formData, date_selector: e.target.value })}
            className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
          />
          <input
            type="text"
            placeholder="Cookies (可选，用于需要登录的网站)"
            value={formData.cookies}
            onChange={(e) => setFormData({ ...formData, cookies: e.target.value })}
            className="w-full px-3 py-2 border dark:border-gray-600 rounded text-xs bg-white dark:bg-gray-800 dark:text-white"
          />
        </>
      )}
      <div className="flex gap-2">
        <select
          value={formData.category_id || ''}
          onChange={(e) => setFormData({ ...formData, category_id: e.target.value ? parseInt(e.target.value) : null })}
          className="flex-1 px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
        >
          <option value="">未分类</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
        <select
          value={formData.fetch_interval}
          onChange={(e) => setFormData({ ...formData, fetch_interval: parseInt(e.target.value) })}
          className="flex-1 px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
        >
          {syncIntervals.map((interval) => (
            <option key={interval.value} value={interval.value}>{interval.label}</option>
          ))}
        </select>
      </div>
      <div className="flex gap-4">
        <div className="flex gap-2 flex-wrap">
          <select
            value={formData.translate_method}
            onChange={(e) => {
              const method = e.target.value as TranslateMethod
              if (method === 'ai' && !hasDefaultModel) {
                setMessage({ type: 'error', text: '请先在 AI 设置中设置默认模型' })
                return
              }
              setFormData({
                ...formData,
                translate_method: method,
                auto_translate: method !== 'none',
                source_language: method === 'argos' ? formData.source_language : '',
              })
            }}
            className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
          >
            <option value="none">不翻译</option>
            <option value="google">Google 翻译</option>
            <option value="argos">本地翻译</option>
            <option value="ai" disabled={!hasDefaultModel}>AI 翻译{!hasDefaultModel ? ' (需配置)' : ''}</option>
          </select>
          {formData.translate_method === 'argos' && (
            <select
              value={formData.source_language}
              onChange={(e) => setFormData({ ...formData, source_language: e.target.value })}
              className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
            >
              <option value="">默认源语言</option>
              {translationSourceLanguages.map((language) => (
                <option key={language.value} value={language.value}>{language.label}</option>
              ))}
            </select>
          )}
          {formData.translate_method !== 'none' && (
            <select
              value={formData.target_language}
              onChange={(e) => setFormData({ ...formData, target_language: e.target.value })}
              className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
            >
              <option value="zh-CN">中文</option>
              <option value="zh-TW">繁体中文</option>
              <option value="en">English</option>
              <option value="ja">日本語</option>
              <option value="ko">한국어</option>
            </select>
          )}
          <label className="flex items-center gap-2 p-2 border dark:border-gray-600 rounded text-sm dark:text-gray-200">
            <input
              type="checkbox"
              checked={formData.auto_summarize}
              onChange={(e) => setFormData({ ...formData, auto_summarize: e.target.checked })}
            />
            AI整理
          </label>
        </div>
      </div>
      <div className="flex gap-4">
        <label className="flex items-center gap-2 p-2 bg-yellow-50 dark:bg-yellow-900/30 border border-yellow-200 dark:border-yellow-800 rounded text-sm dark:text-yellow-200">
          <input
            type="checkbox"
            checked={formData.use_playwright}
            onChange={(e) => setFormData({ ...formData, use_playwright: e.target.checked })}
          />
          浏览器模式 (Playwright)
        </label>
        <label className="flex items-center gap-2 dark:text-gray-200">
          <input
            type="checkbox"
            checked={formData.is_active}
            onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
          />
          启用规则
        </label>
      </div>
      
      {testRuleMutation.data && (
        <div className={`p-3 rounded ${testRuleMutation.data.success ? 'bg-green-50 dark:bg-green-900/30' : 'bg-red-50 dark:bg-red-900/30'}`}>
          {testRuleMutation.data.success ? (
            <div>
              <p className="text-green-700 dark:text-green-400 font-medium mb-2">找到 {testRuleMutation.data.items_found} 个条目</p>
              {testRuleMutation.data.sample_items && testRuleMutation.data.sample_items.length > 0 && (
                <div className="mt-2 space-y-2">
                  <p className="text-sm text-gray-600 dark:text-gray-400">预览（前 5 条）：</p>
                  {testRuleMutation.data.sample_items.map((item: any, idx: number) => (
                    <div key={idx} className="p-2 bg-white dark:bg-gray-800 rounded border dark:border-gray-600 text-sm">
                      <p className="font-medium truncate dark:text-white">{item.title || '(无标题)'}</p>
                      {item.link && <p className="text-xs text-primary-600 dark:text-primary-400 truncate">{item.link}</p>}
                      {item.content && <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{item.content}</p>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <p className="text-red-700 dark:text-red-400">测试失败: {testRuleMutation.data.error}</p>
          )}
        </div>
      )}
      
      <div className="flex gap-2">
        <button
          onClick={() => testRuleMutation.mutate()}
          disabled={!formData.target_url || !formData.list_selector || testRuleMutation.isPending}
          className="px-4 py-2 border dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-600 dark:text-gray-200 disabled:opacity-50"
        >
          测试规则
        </button>
        <button
          onClick={() => isEdit ? updateRuleMutation.mutate({ id: editingId!, data: formData }) : addRuleMutation.mutate()}
          disabled={!formData.name || !formData.target_url || addRuleMutation.isPending || updateRuleMutation.isPending}
          className="px-4 py-2 bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50"
        >
          {isEdit ? '更新' : '保存'}
        </button>
        <button
          onClick={cancelEdit}
          className="px-4 py-2 border dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-600 dark:text-gray-200"
        >
          取消
        </button>
      </div>
    </div>
  )

  const [showHelp, setShowHelp] = useState(false)

  return (
    <div>
      {message && (
        <div className={`mb-4 p-3 rounded ${message.type === 'success' ? 'bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-400' : 'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-400'}`}>
          {message.text}
        </div>
      )}
      
      {/* 使用说明 */}
      <div className="mb-4 p-4 bg-primary-50 dark:bg-primary-900/30 border border-blue-200 dark:border-blue-800 rounded">
        <div className="flex items-center justify-between">
          <h3 className="font-medium text-blue-800 dark:text-primary-300">什么是自定义抓取规则？</h3>
          <button 
            onClick={() => setShowHelp(!showHelp)}
            className="text-primary-600 dark:text-primary-400 text-sm hover:underline"
          >
            {showHelp ? '收起' : '查看详情'}
          </button>
        </div>
        <p className="text-sm text-blue-700 dark:text-primary-400 mt-1">
          自定义规则用于抓取没有 RSS 订阅的网站内容，通过 CSS 选择器提取文章列表。
        </p>
        
        {showHelp && (
          <div className="mt-4 space-y-4 text-sm text-blue-800 dark:text-primary-300">
            <div>
              <h4 className="font-medium mb-2">字段说明：</h4>
              <ul className="list-disc list-inside space-y-1 text-blue-700 dark:text-primary-400">
                <li><span className="font-medium">目标网址</span> - 要抓取的网页 URL</li>
                <li><span className="font-medium">列表选择器</span> - 文章列表项的 CSS 选择器（每个匹配元素代表一篇文章）</li>
                <li><span className="font-medium">标题选择器</span> - 在列表项内，文章标题的选择器</li>
                <li><span className="font-medium">链接选择器</span> - 在列表项内，文章链接的选择器（通常是 a 标签）</li>
                <li><span className="font-medium">内容选择器</span> - 可选，文章摘要/内容的选择器</li>
              </ul>
            </div>
            
            <div>
              <h4 className="font-medium mb-2">示例 - 抓取 Hacker News：</h4>
              <div className="bg-white dark:bg-gray-800 p-3 rounded border border-blue-200 dark:border-gray-600 space-y-2">
                <p><span className="text-gray-500 dark:text-gray-400">目标网址：</span> <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">https://news.ycombinator.com</code></p>
                <p><span className="text-gray-500 dark:text-gray-400">列表选择器：</span> <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">.athing</code></p>
                <p><span className="text-gray-500 dark:text-gray-400">标题选择器：</span> <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">.titleline &gt; a</code></p>
                <p><span className="text-gray-500 dark:text-gray-400">链接选择器：</span> <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">.titleline &gt; a</code></p>
              </div>
            </div>
            
            <div>
              <h4 className="font-medium mb-2">示例 - 抓取博客文章列表：</h4>
              <div className="bg-white dark:bg-gray-800 p-3 rounded border border-blue-200 dark:border-gray-600 space-y-2">
                <p><span className="text-gray-500 dark:text-gray-400">目标网址：</span> <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">https://example.com/blog</code></p>
                <p><span className="text-gray-500 dark:text-gray-400">列表选择器：</span> <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">article.post</code> 或 <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">.post-item</code></p>
                <p><span className="text-gray-500 dark:text-gray-400">标题选择器：</span> <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">h2.title</code> 或 <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">.post-title</code></p>
                <p><span className="text-gray-500 dark:text-gray-400">链接选择器：</span> <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">a.read-more</code> 或 <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">h2 a</code></p>
                <p><span className="text-gray-500 dark:text-gray-400">内容选择器：</span> <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">.excerpt</code> 或 <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">.summary</code></p>
              </div>
            </div>
            
            <div>
              <h4 className="font-medium mb-2">如何获取 CSS 选择器：</h4>
              <ol className="list-decimal list-inside space-y-1 text-blue-700 dark:text-primary-400">
                <li>在浏览器中打开目标网页</li>
                <li>按 F12 打开开发者工具</li>
                <li>使用元素选择器（左上角箭头图标）点击要抓取的元素</li>
                <li>右键点击 HTML 元素 → 复制 → 复制选择器</li>
                <li>简化选择器，保留关键的 class 或 id</li>
              </ol>
            </div>
            
            <p className="text-primary-600 dark:text-primary-400 italic">
              提示：添加规则后点击"测试规则"按钮验证选择器是否正确。
            </p>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold dark:text-white">自定义抓取规则</h2>
        <button
          onClick={() => { setShowAddRule(true); setEditingId(null); setFormData(getEmptyRule()) }}
          className="flex items-center gap-1 px-3 py-2 bg-primary-600 text-white rounded hover:bg-primary-700"
        >
          <Plus className="w-4 h-4" /> 添加规则
        </button>
      </div>

      {showAddRule && !editingId && renderForm(false)}

      <div className="border dark:border-gray-700 rounded divide-y dark:divide-gray-700">
        {rules.map((rule) => {
          const formatInterval = (seconds: number) => {
            if (seconds < 3600) return `${Math.floor(seconds / 60)} 分钟`
            return `${Math.floor(seconds / 3600)} 小时`
          }
          const categoryName = categories.find(c => c.id === rule.category_id)?.name
          
          return (
            <div key={rule.id}>
              {editingId === rule.id ? (
                renderForm(true)
              ) : (
                <div className="flex items-center gap-4 p-4">
                  <div className="flex-1">
                    <h3 className="font-medium dark:text-white">{rule.name}</h3>
                    <p className="text-sm text-gray-500 dark:text-gray-400 truncate">{rule.target_url}</p>
                    <div className="flex gap-3 mt-1 text-xs text-gray-400 dark:text-gray-500">
                      <span>同步间隔: {formatInterval(rule.fetch_interval)}</span>
                      {categoryName && <span>分类: {categoryName}</span>}
                      {rule.translate_method === 'google' && <span>Google翻译</span>}
                      {rule.translate_method === 'ai' && <span>AI翻译</span>}
                      {rule.translate_method === 'argos' && <span>本地翻译</span>}
                      {rule.auto_summarize && <span>AI整理</span>}
                      {rule.last_fetched_at && (
                        <span>上次抓取: {new Date(rule.last_fetched_at).toLocaleString('zh-CN')}</span>
                      )}
                    </div>
                  </div>
                  <span className={`px-2 py-1 text-xs rounded ${rule.is_active ? 'bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-400' : 'bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400'}`}>
                    {rule.is_active ? '启用' : '禁用'}
                  </span>
                  <button
                    onClick={() => executeRuleMutation.mutate(rule.id)}
                    disabled={executeRuleMutation.isPending}
                    className="p-2 text-primary-500 hover:bg-primary-50 dark:hover:bg-primary-900/30 rounded disabled:opacity-50"
                    title="立即抓取"
                  >
                    <RefreshCw className={`w-4 h-4 ${executeRuleMutation.isPending ? 'animate-spin' : ''}`} />
                  </button>
                  <button
                    onClick={() => startEdit(rule)}
                    className="p-2 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
                  >
                    <Edit2 className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => deleteRuleMutation.mutate(rule.id)}
                    className="p-2 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 rounded"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              )}
            </div>
          )
        })}
        {rules.length === 0 && (
          <div className="p-4 text-center text-gray-500 dark:text-gray-400">暂无自定义规则</div>
        )}
      </div>
    </div>
  )
}

// WebDAV types
interface WebDAVConfig {
  server_url: string
  username: string
  password: string
  backup_path: string
}

interface WebDAVBackupInfo {
  filename: string
  size: number
  modified: string
}

interface ImportResult {
  success: boolean
  categories_imported: number
  feeds_imported: number
  articles_imported?: number
  user_articles_imported?: number
  ai_providers_imported: number
  ai_models_imported?: number
  custom_rules_imported: number
  keyword_subscriptions_imported?: number
  proxy_pool_entries_imported?: number
  google_translate_keys_imported?: number
  analysis_queries_imported?: number
  recommended_feeds_imported?: number
  notifications_imported?: number
  user_notification_reads_imported?: number
  updated?: number
  errors: string[]
}

function BackupTab() {
  const queryClient = useQueryClient()
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [importResult, setImportResult] = useState<ImportResult | null>(null)
  
  // WebDAV states
  const [showWebDAVConfig, setShowWebDAVConfig] = useState(false)
  const [webdavConfig, setWebdavConfig] = useState<WebDAVConfig>({
    server_url: '',
    username: '',
    password: '',
    backup_path: '/rss_manager_backups/',
  })
  const [webdavSaving, setWebdavSaving] = useState(false)
  const [webdavTesting, setWebdavTesting] = useState(false)
  const [webdavUploading, setWebdavUploading] = useState(false)
  const [restoringFile, setRestoringFile] = useState<string | null>(null)
  const [deletingFile, setDeletingFile] = useState<string | null>(null)

  const invalidateBackupRelatedQueries = () => {
    ;[
      'feeds',
      'categories',
      'articles',
      'ai-providers',
      'ai-models',
      'ai-settings',
      'custom-rules',
      'keywords',
      'keyword-counts',
      'proxies',
      'proxy-groups',
      'google-translate-keys',
      'admin-recommendations',
      'webdav-config',
    ].forEach((queryKey) => {
      queryClient.invalidateQueries({ queryKey: [queryKey] })
    })
  }

  // Fetch WebDAV config
  const { data: webdavConfigData, refetch: refetchWebdavConfig } = useQuery({
    queryKey: ['webdav-config'],
    queryFn: async () => {
      const response = await api.get('/backup/webdav/config')
      return response.data
    },
  })

  // Fetch WebDAV backup list
  const { data: webdavBackups = [], refetch: refetchBackups, isLoading: loadingBackups } = useQuery({
    queryKey: ['webdav-backups'],
    queryFn: async () => {
      const response = await api.get('/backup/webdav/list')
      return response.data.backups as WebDAVBackupInfo[]
    },
    enabled: webdavConfigData?.configured === true,
  })

  const handleExport = async () => {
    try {
      const response = await api.get('/backup/export', { responseType: 'blob' })
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      
      const contentDisposition = response.headers['content-disposition']
      let filename = 'rss_manager_backup.json'
      if (contentDisposition) {
        const match = contentDisposition.match(/filename=(.+)/)
        if (match) filename = match[1]
      }
      
      link.setAttribute('download', filename)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      
      setMessage({ type: 'success', text: '备份已导出' })
      setTimeout(() => setMessage(null), 3000)
    } catch (err: any) {
      setMessage({ type: 'error', text: '导出失败' })
    }
  }

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    
    const formData = new FormData()
    formData.append('file', file)
    
    try {
      const response = await api.post('/backup/import', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      
      setImportResult(response.data)
      invalidateBackupRelatedQueries()
      
      if (response.data.errors?.length === 0) {
        setMessage({ type: 'success', text: '备份导入成功' })
      } else {
        setMessage({ type: 'error', text: '部分数据导入失败，请查看详情' })
      }
    } catch (err: any) {
      const detail = err.response?.data?.detail
      setMessage({ type: 'error', text: detail || '导入失败' })
    }
    
    e.target.value = ''
  }

  // WebDAV handlers
  const handleTestWebDAVConnection = async () => {
    setWebdavTesting(true)
    try {
      await api.post('/backup/webdav/test', webdavConfig)
      setMessage({ type: 'success', text: 'WebDAV 连接测试成功' })
      setTimeout(() => setMessage(null), 3000)
    } catch (err: any) {
      const detail = err.response?.data?.detail
      setMessage({ type: 'error', text: detail || 'WebDAV 连接测试失败' })
    } finally {
      setWebdavTesting(false)
    }
  }

  const handleSaveWebDAVConfig = async () => {
    setWebdavSaving(true)
    try {
      await api.post('/backup/webdav/config', webdavConfig)
      setMessage({ type: 'success', text: 'WebDAV 配置已保存' })
      setShowWebDAVConfig(false)
      refetchWebdavConfig()
      refetchBackups()
      setTimeout(() => setMessage(null), 3000)
    } catch (err: any) {
      const detail = err.response?.data?.detail
      setMessage({ type: 'error', text: detail || 'WebDAV 配置保存失败' })
    } finally {
      setWebdavSaving(false)
    }
  }

  const handleWebDAVUpload = async () => {
    setWebdavUploading(true)
    try {
      await api.post('/backup/webdav/upload')
      setMessage({ type: 'success', text: '备份已上传到 WebDAV' })
      refetchBackups()
      setTimeout(() => setMessage(null), 3000)
    } catch (err: any) {
      const detail = err.response?.data?.detail
      setMessage({ type: 'error', text: detail || '上传备份失败' })
    } finally {
      setWebdavUploading(false)
    }
  }

  const handleWebDAVRestore = async (filename: string) => {
    if (!confirm(`确定要从 "${filename}" 恢复备份吗？已存在的数据会按唯一标识更新。`)) return
    
    setRestoringFile(filename)
    try {
      const response = await api.post(`/backup/webdav/restore/${encodeURIComponent(filename)}`)
      setImportResult(response.data)
      invalidateBackupRelatedQueries()
      
      if (response.data.errors?.length === 0) {
        setMessage({ type: 'success', text: '备份恢复成功' })
      } else {
        setMessage({ type: 'error', text: '部分数据恢复失败，请查看详情' })
      }
    } catch (err: any) {
      const detail = err.response?.data?.detail
      setMessage({ type: 'error', text: detail || '恢复备份失败' })
    } finally {
      setRestoringFile(null)
    }
  }

  const handleWebDAVDelete = async (filename: string) => {
    if (!confirm(`确定要删除备份 "${filename}" 吗？此操作不可恢复。`)) return
    
    setDeletingFile(filename)
    try {
      await api.delete(`/backup/webdav/delete/${encodeURIComponent(filename)}`)
      setMessage({ type: 'success', text: '备份已删除' })
      refetchBackups()
      setTimeout(() => setMessage(null), 3000)
    } catch (err: any) {
      const detail = err.response?.data?.detail
      setMessage({ type: 'error', text: detail || '删除备份失败' })
    } finally {
      setDeletingFile(null)
    }
  }

  const handleWebDAVDownload = async (filename: string) => {
    try {
      const response = await api.get(`/backup/webdav/download/${encodeURIComponent(filename)}`, { responseType: 'blob' })
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', filename)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch (err: any) {
      const detail = err.response?.data?.detail
      setMessage({ type: 'error', text: detail || '下载备份失败' })
    }
  }

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  return (
    <div className="space-y-6">
      {message && (
        <div className={`p-3 rounded ${message.type === 'success' ? 'bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-400' : 'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-400'}`}>
          {message.text}
        </div>
      )}

      {/* 本地备份说明 */}
      <div className="p-4 bg-primary-50 dark:bg-primary-900/30 border border-blue-200 dark:border-blue-800 rounded">
        <h3 className="font-medium text-blue-800 dark:text-primary-300 mb-2">本地备份与恢复</h3>
        <p className="text-sm text-blue-700 dark:text-primary-400">
          导出会将配置和数据库内容保存为 JSON 文件。导入时按唯一标识新增或更新已有数据。
        </p>
      </div>

      {/* 本地操作按钮 */}
      <div className="flex gap-4 flex-wrap">
        <button
          onClick={handleExport}
          className="flex items-center gap-2 px-6 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
        >
          <Download className="w-5 h-5" />
          导出到本地
        </button>
        
        <label className="flex items-center gap-2 px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 cursor-pointer">
          <FolderOpen className="w-5 h-5" />
          从本地导入
          <input
            type="file"
            accept=".json"
            onChange={handleImport}
            className="hidden"
          />
        </label>
      </div>

      {/* WebDAV 备份 */}
      <div className="border dark:border-gray-700 rounded">
        <div className="p-4 border-b dark:border-gray-700 bg-gray-50 dark:bg-gray-700 flex justify-between items-center">
          <div>
            <h3 className="font-medium dark:text-white">WebDAV 云备份</h3>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              {webdavConfigData?.configured 
                ? `已连接: ${webdavConfigData.server_url}` 
                : '未配置 WebDAV 服务器'}
            </p>
          </div>
          <button
            onClick={() => {
              if (webdavConfigData?.configured) {
                setWebdavConfig({
                  server_url: webdavConfigData.server_url || '',
                  username: webdavConfigData.username || '',
                  password: '',
                  backup_path: webdavConfigData.backup_path || '/rss_manager_backups/',
                })
              }
              setShowWebDAVConfig(!showWebDAVConfig)
            }}
            className="px-4 py-2 text-sm bg-primary-600 text-white rounded hover:bg-primary-700"
          >
            {webdavConfigData?.configured ? '修改配置' : '配置 WebDAV'}
          </button>
        </div>

        {/* WebDAV 配置表单 */}
        {showWebDAVConfig && (
          <div className="p-4 border-b dark:border-gray-700 bg-gray-50 dark:bg-gray-800 space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1 dark:text-gray-300">服务器地址</label>
              <input
                type="url"
                value={webdavConfig.server_url}
                onChange={(e) => setWebdavConfig({ ...webdavConfig, server_url: e.target.value })}
                placeholder="https://dav.example.com"
                className="w-full px-3 py-2 border dark:border-gray-600 rounded dark:bg-gray-700 dark:text-white"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-1 dark:text-gray-300">用户名</label>
                <input
                  type="text"
                  value={webdavConfig.username}
                  onChange={(e) => setWebdavConfig({ ...webdavConfig, username: e.target.value })}
                  className="w-full px-3 py-2 border dark:border-gray-600 rounded dark:bg-gray-700 dark:text-white"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1 dark:text-gray-300">密码</label>
                <input
                  type="password"
                  value={webdavConfig.password}
                  onChange={(e) => setWebdavConfig({ ...webdavConfig, password: e.target.value })}
                  placeholder={webdavConfigData?.configured ? '留空保持不变' : ''}
                  className="w-full px-3 py-2 border dark:border-gray-600 rounded dark:bg-gray-700 dark:text-white"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1 dark:text-gray-300">备份路径</label>
              <input
                type="text"
                value={webdavConfig.backup_path}
                onChange={(e) => setWebdavConfig({ ...webdavConfig, backup_path: e.target.value })}
                placeholder="/rss_manager_backups/"
                className="w-full px-3 py-2 border dark:border-gray-600 rounded dark:bg-gray-700 dark:text-white"
              />
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleTestWebDAVConnection}
                disabled={webdavTesting || !webdavConfig.server_url || !webdavConfig.username}
                className="px-4 py-2 border border-primary-600 text-primary-600 dark:text-primary-400 rounded hover:bg-primary-50 dark:hover:bg-primary-900/30 disabled:opacity-50"
              >
                {webdavTesting ? '测试中...' : '测试连接'}
              </button>
              <button
                onClick={handleSaveWebDAVConfig}
                disabled={webdavSaving || !webdavConfig.server_url || !webdavConfig.username}
                className="px-4 py-2 bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50"
              >
                {webdavSaving ? '保存中...' : '保存配置'}
              </button>
              <button
                onClick={() => setShowWebDAVConfig(false)}
                className="px-4 py-2 border dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-700 dark:text-gray-300"
              >
                取消
              </button>
            </div>
          </div>
        )}

        {/* WebDAV 操作按钮 */}
        {webdavConfigData?.configured && (
          <div className="p-4 border-b dark:border-gray-700 flex gap-4">
            <button
              onClick={handleWebDAVUpload}
              disabled={webdavUploading}
              className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50"
            >
              <Upload className="w-4 h-4" />
              {webdavUploading ? '上传中...' : '备份到 WebDAV'}
            </button>
            <button
              onClick={() => refetchBackups()}
              disabled={loadingBackups}
              className="flex items-center gap-2 px-4 py-2 border dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-700 dark:text-gray-300"
            >
              <RefreshCw className={`w-4 h-4 ${loadingBackups ? 'animate-spin' : ''}`} />
              刷新列表
            </button>
          </div>
        )}

        {/* WebDAV 备份列表 */}
        {webdavConfigData?.configured && (
          <div className="divide-y dark:divide-gray-700">
            {loadingBackups ? (
              <div className="p-4 text-center text-gray-500 dark:text-gray-400">加载中...</div>
            ) : webdavBackups.length === 0 ? (
              <div className="p-4 text-center text-gray-500 dark:text-gray-400">暂无备份</div>
            ) : (
              webdavBackups.map((backup) => (
                <div key={backup.filename} className="p-4 flex items-center justify-between">
                  <div>
                    <p className="font-medium dark:text-white">{backup.filename}</p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      {formatFileSize(backup.size)} · {backup.modified}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleWebDAVDownload(backup.filename)}
                      className="p-2 text-gray-600 hover:text-primary-600 dark:text-gray-400 dark:hover:text-primary-400"
                      title="下载"
                    >
                      <Download className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleWebDAVRestore(backup.filename)}
                      disabled={restoringFile === backup.filename}
                      className="px-3 py-1 text-sm bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
                    >
                      {restoringFile === backup.filename ? '恢复中...' : '恢复'}
                    </button>
                    <button
                      onClick={() => handleWebDAVDelete(backup.filename)}
                      disabled={deletingFile === backup.filename}
                      className="p-2 text-red-600 hover:text-red-700 dark:text-red-400 disabled:opacity-50"
                      title="删除"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* 导入结果 */}
      {importResult && (
        <div className="p-4 border dark:border-gray-700 rounded bg-gray-50 dark:bg-gray-700">
          <h3 className="font-medium mb-3 dark:text-white">导入/恢复结果</h3>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
            {[
              ['分类', importResult.categories_imported],
              ['订阅源', importResult.feeds_imported],
              ['文章', importResult.articles_imported || 0],
              ['阅读/收藏状态', importResult.user_articles_imported || 0],
              ['AI 渠道', importResult.ai_providers_imported],
              ['AI 模型', importResult.ai_models_imported || 0],
              ['自定义规则', importResult.custom_rules_imported],
              ['关键词订阅', importResult.keyword_subscriptions_imported || 0],
              ['代理池', importResult.proxy_pool_entries_imported || 0],
              ['Google Key', importResult.google_translate_keys_imported || 0],
              ['分析历史', importResult.analysis_queries_imported || 0],
              ['推荐订阅', importResult.recommended_feeds_imported || 0],
              ['通知', importResult.notifications_imported || 0],
              ['通知阅读', importResult.user_notification_reads_imported || 0],
              ['已更新', importResult.updated || 0],
            ].map(([label, count]) => (
              <div key={label} className="flex justify-between p-2 bg-white dark:bg-gray-800 rounded dark:text-gray-200">
                <span>{label}</span>
                <span className="font-medium text-green-600 dark:text-green-400">+{count}</span>
              </div>
            ))}
          </div>
          
          {importResult.errors.length > 0 && (
            <div className="mt-4">
              <h4 className="text-sm font-medium text-red-600 dark:text-red-400 mb-2">错误信息：</h4>
              <ul className="text-sm text-red-600 dark:text-red-400 list-disc list-inside">
                {importResult.errors.map((err, i) => (
                  <li key={i}>{err}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* 备份内容说明 */}
      <div className="border dark:border-gray-700 rounded">
        <h3 className="font-medium p-4 border-b dark:border-gray-700 bg-gray-50 dark:bg-gray-700 dark:text-white">备份包含的内容</h3>
        <div className="divide-y dark:divide-gray-700">
          <div className="p-4 flex items-center gap-3">
            <span className="w-8 h-8 flex items-center justify-center bg-primary-100 dark:bg-primary-900/50 text-primary-600 dark:text-primary-400 rounded">📁</span>
            <div>
              <p className="font-medium dark:text-white">分类</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">名称、描述、排序</p>
            </div>
          </div>
          <div className="p-4 flex items-center gap-3">
            <span className="w-8 h-8 flex items-center justify-center bg-orange-100 dark:bg-orange-900/50 text-orange-600 dark:text-orange-400 rounded">📰</span>
            <div>
              <p className="font-medium dark:text-white">订阅源与文章</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">订阅设置、文章内容、翻译、摘要、阅读/收藏状态</p>
            </div>
          </div>
          <div className="p-4 flex items-center gap-3">
            <span className="w-8 h-8 flex items-center justify-center bg-purple-100 dark:bg-purple-900/50 text-purple-600 dark:text-purple-400 rounded">🤖</span>
            <div>
              <p className="font-medium dark:text-white">AI 设置</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">AI 渠道、模型、提示词、Embedding 配置、Google 翻译 Key</p>
            </div>
          </div>
          <div className="p-4 flex items-center gap-3">
            <span className="w-8 h-8 flex items-center justify-center bg-green-100 dark:bg-green-900/50 text-green-600 dark:text-green-400 rounded">🕷️</span>
            <div>
              <p className="font-medium dark:text-white">自定义规则</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">抓取规则配置（URL、选择器等）</p>
            </div>
          </div>
          <div className="p-4 flex items-center gap-3">
            <span className="w-8 h-8 flex items-center justify-center bg-cyan-100 dark:bg-cyan-900/50 text-cyan-600 dark:text-cyan-400 rounded">#</span>
            <div>
              <p className="font-medium dark:text-white">关键词与代理池</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">关键词订阅、代理 IP、国家/协议分组、测试状态</p>
            </div>
          </div>
          <div className="p-4 flex items-center gap-3">
            <span className="w-8 h-8 flex items-center justify-center bg-amber-100 dark:bg-amber-900/50 text-amber-600 dark:text-amber-400 rounded">i</span>
            <div>
              <p className="font-medium dark:text-white">其它数据</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">分析历史、用户创建的推荐订阅和通知</p>
            </div>
          </div>
        </div>
      </div>

      <p className="text-sm text-gray-500 dark:text-gray-400">
        注意：备份文件包含 API Key、代理账号密码、Cookies、WebDAV 配置等敏感信息，请妥善保管。
      </p>
    </div>
  )
}

function AppearanceTab() {
  const { mode, color, setMode, setColor } = useThemeStore()

  // 主题颜色
  const colorOptions: { value: ThemeColor; label: string; bgClass: string }[] = [
    { value: 'blue', label: '蓝色', bgClass: 'bg-blue-500' },
    { value: 'green', label: '绿色', bgClass: 'bg-green-500' },
    { value: 'purple', label: '紫色', bgClass: 'bg-purple-500' },
    { value: 'orange', label: '橙色', bgClass: 'bg-orange-500' },
    { value: 'rose', label: '玫红', bgClass: 'bg-rose-500' },
    { value: 'cyan', label: '青色', bgClass: 'bg-cyan-500' },
    { value: 'indigo', label: '靛蓝', bgClass: 'bg-indigo-500' },
    { value: 'amber', label: '琥珀', bgClass: 'bg-amber-500' },
    { value: 'red', label: '红色', bgClass: 'bg-red-500' },
    { value: 'pink', label: '粉色', bgClass: 'bg-pink-500' },
    { value: 'teal', label: '青绿', bgClass: 'bg-teal-500' },
    { value: 'slate', label: '石板', bgClass: 'bg-slate-500' },
  ]

  return (
    <div className="space-y-8">
      {/* 主题模式 */}
      <div>
        <h3 className="font-medium mb-4 dark:text-white">主题模式</h3>
        <div className="flex gap-4">
          <button
            onClick={() => setMode('light')}
            className={`flex-1 p-4 rounded-xl border-2 transition-all duration-300 ${
              mode === 'light'
                ? 'border-primary-500 bg-gradient-to-br from-primary-50 to-white dark:from-primary-900/30 dark:to-gray-800 shadow-lg'
                : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600 hover:shadow-md'
            }`}
          >
            <div className="w-full h-24 rounded-lg bg-gradient-to-br from-white to-gray-50 border mb-3 flex items-center justify-center overflow-hidden relative">
              <div className="absolute top-2 left-2 w-3 h-3 rounded-full bg-yellow-400 shadow-lg shadow-yellow-400/50"></div>
              <div className="w-16 h-3 bg-gray-200 rounded-full"></div>
            </div>
            <p className={`text-center font-medium ${mode === 'light' ? 'text-primary-600' : 'text-gray-600 dark:text-gray-400'}`}>
              浅色模式
            </p>
          </button>
          <button
            onClick={() => setMode('dark')}
            className={`flex-1 p-4 rounded-xl border-2 transition-all duration-300 ${
              mode === 'dark'
                ? 'border-primary-500 bg-gradient-to-br from-primary-50 to-white dark:from-primary-900/30 dark:to-gray-800 shadow-lg'
                : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600 hover:shadow-md'
            }`}
          >
            <div className="w-full h-24 rounded-lg bg-gradient-to-br from-gray-800 to-gray-900 border border-gray-700 mb-3 flex items-center justify-center overflow-hidden relative">
              <div className="absolute top-2 left-2 w-3 h-3 rounded-full bg-indigo-400 shadow-lg shadow-indigo-400/50"></div>
              <div className="absolute top-3 right-3 w-1.5 h-1.5 rounded-full bg-white/30"></div>
              <div className="absolute top-5 right-6 w-1 h-1 rounded-full bg-white/20"></div>
              <div className="w-16 h-3 bg-gray-600 rounded-full"></div>
            </div>
            <p className={`text-center font-medium ${mode === 'dark' ? 'text-primary-600 dark:text-primary-400' : 'text-gray-600 dark:text-gray-400'}`}>
              深色模式
            </p>
          </button>
        </div>
      </div>

      {/* 主题颜色 */}
      <div>
        <h3 className="font-medium mb-4 dark:text-white">主题颜色</h3>
        <div className="flex gap-4 flex-wrap">
          {colorOptions.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setColor(opt.value)}
              className={`flex flex-col items-center gap-2 p-3 rounded-lg border-2 transition-all ${
                color === opt.value
                  ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/20'
                  : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
              }`}
            >
              <div className={`w-10 h-10 rounded-full ${opt.bgClass}`}></div>
              <span className={`text-sm ${color === opt.value ? 'text-primary-600 dark:text-primary-400 font-medium' : 'text-gray-600 dark:text-gray-400'}`}>
                {opt.label}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* 预览 */}
      <div>
        <h3 className="font-medium mb-4 dark:text-white">预览</h3>
        <div className={`p-4 rounded-lg border ${mode === 'dark' ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'}`}>
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded-full bg-primary-500"></div>
            <div>
              <p className={`font-medium ${mode === 'dark' ? 'text-white' : 'text-gray-900'}`}>示例标题</p>
              <p className={`text-sm ${mode === 'dark' ? 'text-gray-400' : 'text-gray-500'}`}>这是一段示例文字</p>
            </div>
          </div>
          <button className="px-4 py-2 rounded text-white bg-primary-600 hover:bg-primary-700">
            示例按钮
          </button>
        </div>
      </div>
    </div>
  )
}

interface OAuthConfig {
  enabled: boolean
  client_id: string
  client_secret: string
  authorize_url: string
  token_url: string
  userinfo_url: string
}

interface SyncIntervalOption {
  value: number
  label: string
}

interface RecommendedFeedAdmin {
  id: number
  url: string
  title: string
  description: string | null
  icon_url: string | null
  categories: string
  use_playwright: boolean
  is_active: boolean
  subscriber_count: number
}

function RecommendationsManagement({ 
  enabled, 
  onToggle, 
  isPending 
}: { 
  enabled: boolean
  onToggle: (enabled: boolean) => void
  isPending: boolean
}) {
  const queryClient = useQueryClient()
  const [showAddForm, setShowAddForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [formData, setFormData] = useState({
    url: '',
    title: '',
    description: '',
    icon_url: '',
    categories: '',
    use_playwright: false,
  })
  const [validating, setValidating] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  const { data: recommendations = [], isLoading } = useQuery({
    queryKey: ['admin-recommendations'],
    queryFn: async () => {
      const response = await api.get<RecommendedFeedAdmin[]>('/recommendations/admin/all')
      return response.data
    },
  })

  const validateFeed = async () => {
    if (!formData.url) return
    setValidating(true)
    setMessage(null)
    try {
      const response = await api.post<{ success: boolean; title: string; description: string; icon_url: string; article_count: number }>(
        '/recommendations/admin/validate',
        null,
        { params: { url: formData.url, use_playwright: formData.use_playwright } }
      )
      setFormData({
        ...formData,
        title: formData.title || response.data.title || '',
        description: formData.description || response.data.description || '',
        icon_url: formData.icon_url || response.data.icon_url || '',
      })
      setMessage({ type: 'success', text: `验证成功！发现 ${response.data.article_count} 篇文章` })
      setTimeout(() => setMessage(null), 3000)
    } catch (err: any) {
      setMessage({ type: 'error', text: err.response?.data?.detail || '验证失败' })
    } finally {
      setValidating(false)
    }
  }

  const createMutation = useMutation({
    mutationFn: async (data: typeof formData) => {
      const response = await api.post('/recommendations/admin', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-recommendations'] })
      setShowAddForm(false)
      setFormData({ url: '', title: '', description: '', icon_url: '', categories: '', use_playwright: false })
      setMessage({ type: 'success', text: '推荐源已添加' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: any) => {
      setMessage({ type: 'error', text: err.response?.data?.detail || '添加失败' })
    },
  })

  const updateMutation = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: Partial<typeof formData & { is_active: boolean }> }) => {
      const response = await api.put(`/recommendations/admin/${id}`, data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-recommendations'] })
      setEditingId(null)
      setMessage({ type: 'success', text: '推荐源已更新' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: any) => {
      setMessage({ type: 'error', text: err.response?.data?.detail || '更新失败' })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/recommendations/admin/${id}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-recommendations'] })
      setMessage({ type: 'success', text: '推荐源已删除' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: any) => {
      setMessage({ type: 'error', text: err.response?.data?.detail || '删除失败' })
    },
  })

  const startEdit = (rec: RecommendedFeedAdmin) => {
    setEditingId(rec.id)
    setFormData({
      url: rec.url,
      title: rec.title,
      description: rec.description || '',
      icon_url: rec.icon_url || '',
      categories: rec.categories,
      use_playwright: rec.use_playwright,
    })
  }

  return (
    <div className="p-4 border dark:border-gray-700 rounded-lg">
      <h3 className="font-medium mb-4 dark:text-white flex items-center gap-2">
        <Star className="w-5 h-5" />
        订阅推荐
      </h3>
      
      {message && (
        <div className={`mb-4 p-3 rounded ${message.type === 'success' ? 'bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-400' : 'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-400'}`}>
          {message.text}
        </div>
      )}

      {/* 开关 */}
      <label className="flex items-center gap-3 cursor-pointer mb-4">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => onToggle(e.target.checked)}
          disabled={isPending}
          className="w-5 h-5 rounded border-gray-300 text-primary-600 focus:ring-primary-500 disabled:opacity-50"
        />
        <div>
          <p className="font-medium dark:text-white">启用订阅推荐功能</p>
          <p className="text-sm text-gray-500 dark:text-gray-400">开启后，用户可以在"订阅推荐"页面浏览并一键订阅推荐源</p>
        </div>
      </label>

      {enabled && (
        <>
          {/* 添加按钮 */}
          <div className="mb-4">
            <button
              onClick={() => {
                setShowAddForm(true)
                setFormData({ url: '', title: '', description: '', icon_url: '', categories: '', use_playwright: false })
              }}
              className="flex items-center gap-1 px-3 py-2 bg-primary-600 text-white rounded hover:bg-primary-700"
            >
              <Plus className="w-4 h-4" /> 添加推荐源
            </button>
          </div>

          {/* 添加/编辑表单 */}
          {(showAddForm || editingId !== null) && (
            <div className="mb-4 p-4 border dark:border-gray-600 rounded bg-gray-50 dark:bg-gray-700 space-y-3">
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="RSS 订阅地址"
                  value={formData.url}
                  onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                  className="flex-1 px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
                />
                <button
                  onClick={validateFeed}
                  disabled={!formData.url || validating}
                  className="px-3 py-2 border dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-600 dark:text-gray-200 disabled:opacity-50"
                >
                  {validating ? '验证中...' : '验证'}
                </button>
              </div>
              <label className="flex items-center gap-2 p-2 bg-yellow-50 dark:bg-yellow-900/30 border border-yellow-200 dark:border-yellow-800 rounded">
                <input
                  type="checkbox"
                  checked={formData.use_playwright}
                  onChange={(e) => setFormData({ ...formData, use_playwright: e.target.checked })}
                />
                <span className="text-sm dark:text-yellow-200">使用浏览器模式 (Playwright)</span>
                <span className="text-xs text-yellow-600 dark:text-yellow-400">适用于 Cloudflare 保护的网站</span>
              </label>
              <input
                type="text"
                placeholder="标题（验证后自动填充）"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
              />
              <input
                type="text"
                placeholder="描述（可选，验证后自动填充）"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
              />
              <input
                type="text"
                placeholder="图标 URL（可选，验证后自动填充）"
                value={formData.icon_url}
                onChange={(e) => setFormData({ ...formData, icon_url: e.target.value })}
                className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
              />
              <input
                type="text"
                placeholder="分类标签（逗号分隔，如：技术,新闻,AI）"
                value={formData.categories}
                onChange={(e) => setFormData({ ...formData, categories: e.target.value })}
                className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
              />
              <div className="flex gap-2">
                <button
                  onClick={() => {
                    if (editingId !== null) {
                      updateMutation.mutate({ id: editingId, data: formData })
                    } else {
                      createMutation.mutate(formData)
                    }
                  }}
                  disabled={!formData.url || createMutation.isPending || updateMutation.isPending}
                  className="px-4 py-2 bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50"
                >
                  {createMutation.isPending || updateMutation.isPending ? '保存中...' : (editingId !== null ? '更新' : '添加')}
                </button>
                <button
                  onClick={() => {
                    setShowAddForm(false)
                    setEditingId(null)
                    setFormData({ url: '', title: '', description: '', icon_url: '', categories: '', use_playwright: false })
                  }}
                  className="px-4 py-2 border dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-600 dark:text-gray-200"
                >
                  取消
                </button>
              </div>
            </div>
          )}

          {/* 推荐源列表 */}
          {isLoading ? (
            <div className="text-center py-4 text-gray-500 dark:text-gray-400">加载中...</div>
          ) : recommendations.length === 0 ? (
            <div className="text-center py-4 text-gray-500 dark:text-gray-400">暂无推荐源</div>
          ) : (
            <div className="border dark:border-gray-700 rounded divide-y dark:divide-gray-700">
              {recommendations.map((rec) => (
                <div key={rec.id} className="p-3 flex items-center gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium dark:text-white truncate">{rec.title}</span>
                      {rec.use_playwright && (
                        <span className="px-2 py-0.5 text-xs bg-yellow-100 dark:bg-yellow-900/50 text-yellow-700 dark:text-yellow-300 rounded">浏览器</span>
                      )}
                      {!rec.is_active && (
                        <span className="px-2 py-0.5 text-xs bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 rounded">已禁用</span>
                      )}
                    </div>
                    <p className="text-sm text-gray-500 dark:text-gray-400 truncate">{rec.url}</p>
                    <div className="flex items-center gap-2 mt-1 text-xs text-gray-400 dark:text-gray-500">
                      {rec.categories && <span>{rec.categories}</span>}
                      <span>·</span>
                      <span>{rec.subscriber_count} 人订阅</span>
                    </div>
                  </div>
                  <div className="flex gap-1">
                    <button
                      onClick={() => startEdit(rec)}
                      className="p-2 text-gray-500 hover:text-primary-600 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
                      title="编辑"
                    >
                      <Edit2 className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => updateMutation.mutate({ id: rec.id, data: { is_active: !rec.is_active } })}
                      className={`p-2 rounded ${rec.is_active ? 'text-yellow-600 hover:bg-yellow-50 dark:hover:bg-yellow-900/30' : 'text-green-600 hover:bg-green-50 dark:hover:bg-green-900/30'}`}
                      title={rec.is_active ? '禁用' : '启用'}
                    >
                      {rec.is_active ? <X className="w-4 h-4" /> : <Check className="w-4 h-4" />}
                    </button>
                    <button
                      onClick={() => {
                        if (confirm(`确定要删除推荐源 "${rec.title}" 吗？`)) {
                          deleteMutation.mutate(rec.id)
                        }
                      }}
                      className="p-2 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 rounded"
                      title="删除"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}

interface SystemSettings {
  allow_registration: boolean
  site_name: string
  oauth_linuxdo: OAuthConfig
  sync_intervals: SyncIntervalOption[]
  default_sync_interval: number
  enable_feed_recommendations: boolean
  show_favorites_menu: boolean
  show_ai_analysis_menu: boolean
  show_recommendations_menu: boolean
}

// 所有可选的同步间隔
const ALL_SYNC_INTERVALS: SyncIntervalOption[] = [
  { value: 60, label: '1 分钟' },
  { value: 120, label: '2 分钟' },
  { value: 180, label: '3 分钟' },
  { value: 240, label: '4 分钟' },
  { value: 300, label: '5 分钟' },
  { value: 900, label: '15 分钟' },
  { value: 1800, label: '30 分钟' },
  { value: 3600, label: '1 小时' },
  { value: 7200, label: '2 小时' },
  { value: 14400, label: '4 小时' },
  { value: 43200, label: '12 小时' },
  { value: 86400, label: '24 小时' },
]

function SystemTab() {
  const queryClient = useQueryClient()
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [siteName, setSiteName] = useState('')
  const [syncIntervals, setSyncIntervals] = useState<SyncIntervalOption[]>([])
  const [defaultSyncInterval, setDefaultSyncInterval] = useState(3600)
  const [oauthLinuxdo, setOauthLinuxdo] = useState<OAuthConfig>({
    enabled: false,
    client_id: '',
    client_secret: '',
    authorize_url: 'https://connect.linux.do/oauth2/authorize',
    token_url: 'https://connect.linux.do/oauth2/token',
    userinfo_url: 'https://connect.linux.do/api/user',
  })

  const { data: settings, isLoading } = useQuery({
    queryKey: ['system-settings'],
    queryFn: async () => {
      const response = await api.get<SystemSettings>('/system/settings')
      setSiteName(response.data.site_name)
      if (response.data.oauth_linuxdo) {
        setOauthLinuxdo(response.data.oauth_linuxdo)
      }
      if (response.data.sync_intervals) {
        setSyncIntervals(response.data.sync_intervals)
      }
      if (response.data.default_sync_interval) {
        setDefaultSyncInterval(response.data.default_sync_interval)
      }
      return response.data
    },
  })

  const { data: users } = useQuery({
    queryKey: ['system-users'],
    queryFn: async () => {
      const response = await api.get<Array<{
        id: number
        username: string
        email: string
        is_active: boolean
        is_admin: boolean
        created_at: string | null
        last_login_at: string | null
      }>>('/system/users')
      return response.data
    },
  })

  const updateSettingsMutation = useMutation({
    mutationFn: async (data: { 
      allow_registration?: boolean
      site_name?: string
      oauth_linuxdo?: OAuthConfig
      sync_intervals?: SyncIntervalOption[]
      default_sync_interval?: number
      enable_feed_recommendations?: boolean
      show_favorites_menu?: boolean
      show_ai_analysis_menu?: boolean
      show_recommendations_menu?: boolean
    }) => {
      const response = await api.put('/system/settings', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['system-settings'] })
      queryClient.invalidateQueries({ queryKey: ['public-settings'] })
      queryClient.invalidateQueries({ queryKey: ['oauth-status'] })
      setMessage({ type: 'success', text: '设置已保存' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      setMessage({ type: 'error', text: detail || '保存失败' })
    },
  })

  const updateUserMutation = useMutation({
    mutationFn: async ({ userId, data }: { userId: number; data: { is_active?: boolean; is_admin?: boolean } }) => {
      const response = await api.put(`/system/users/${userId}`, data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['system-users'] })
      setMessage({ type: 'success', text: '用户已更新' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      setMessage({ type: 'error', text: detail || '更新失败' })
    },
  })

  const deleteUserMutation = useMutation({
    mutationFn: async (userId: number) => {
      await api.delete(`/system/users/${userId}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['system-users'] })
      setMessage({ type: 'success', text: '用户已删除' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      setMessage({ type: 'error', text: detail || '删除失败' })
    },
  })

  const [activeSubTab, setActiveSubTab] = useState<'general' | 'sync' | 'oauth' | 'recommendations' | 'notifications' | 'users'>('general')

  if (isLoading) {
    return <div className="text-center py-8 text-gray-500 dark:text-gray-400">加载中...</div>
  }

  const subTabs = [
    { id: 'general', label: '基本设置' },
    { id: 'sync', label: '同步设置' },
    { id: 'oauth', label: '第三方登录' },
    { id: 'recommendations', label: '订阅推荐' },
    { id: 'notifications', label: '通知管理' },
    { id: 'users', label: '用户管理' },
  ]

  return (
    <div className="space-y-6">
      {message && (
        <div className={`p-3 rounded ${message.type === 'success' ? 'bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-400' : 'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-400'}`}>
          {message.text}
        </div>
      )}

      {/* Sub Tabs */}
      <div className="flex gap-2 flex-wrap">
        {subTabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveSubTab(tab.id as typeof activeSubTab)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeSubTab === tab.id
                ? 'bg-primary-600 text-white'
                : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* 基本设置 */}
      {activeSubTab === 'general' && (
        <div className="space-y-6">
          {/* 网站设置 */}
          <div className="p-4 border dark:border-gray-700 rounded-lg">
            <h3 className="font-medium mb-4 dark:text-white flex items-center gap-2">
              <Shield className="w-5 h-5" />
              网站设置
            </h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium dark:text-gray-300 mb-2">网站名称</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={siteName}
                    onChange={(e) => setSiteName(e.target.value)}
                    placeholder="RSS 管理器"
                    className="flex-1 px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
              />
              <button
                onClick={() => updateSettingsMutation.mutate({ site_name: siteName })}
                disabled={updateSettingsMutation.isPending}
                className="px-4 py-2 bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50"
              >
                {updateSettingsMutation.isPending ? '保存中...' : '保存'}
              </button>
            </div>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">自定义网站名称，将显示在侧边栏和页面标题中</p>
          </div>
        </div>
      </div>

          {/* 左侧菜单显示 */}
          <div className="p-4 border dark:border-gray-700 rounded-lg">
            <h3 className="font-medium mb-4 dark:text-white flex items-center gap-2">
              <Shield className="w-5 h-5" />
              左侧菜单显示
            </h3>
            <div className="space-y-4">
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings?.show_favorites_menu ?? true}
                  onChange={(e) => updateSettingsMutation.mutate({ show_favorites_menu: e.target.checked })}
                  disabled={updateSettingsMutation.isPending}
                  className="w-5 h-5 rounded border-gray-300 text-primary-600 focus:ring-primary-500 disabled:opacity-50"
                />
                <div>
                  <p className="font-medium dark:text-white">显示收藏入口</p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">控制左侧菜单中的「收藏」按钮是否显示</p>
                </div>
              </label>

              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings?.show_ai_analysis_menu ?? true}
                  onChange={(e) => updateSettingsMutation.mutate({ show_ai_analysis_menu: e.target.checked })}
                  disabled={updateSettingsMutation.isPending}
                  className="w-5 h-5 rounded border-gray-300 text-primary-600 focus:ring-primary-500 disabled:opacity-50"
                />
                <div>
                  <p className="font-medium dark:text-white">显示 AI 分析入口</p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">控制左侧菜单中的「AI 分析」按钮是否显示</p>
                </div>
              </label>

              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings?.show_recommendations_menu ?? true}
                  onChange={(e) => updateSettingsMutation.mutate({ show_recommendations_menu: e.target.checked })}
                  disabled={updateSettingsMutation.isPending}
                  className="w-5 h-5 rounded border-gray-300 text-primary-600 focus:ring-primary-500 disabled:opacity-50"
                />
                <div>
                  <p className="font-medium dark:text-white">显示订阅推荐入口</p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">控制左侧菜单中的「订阅推荐」按钮是否显示</p>
                </div>
              </label>
            </div>
          </div>

          {/* 注册设置 */}
          <div className="p-4 border dark:border-gray-700 rounded-lg">
            <h3 className="font-medium mb-4 dark:text-white flex items-center gap-2">
              <Shield className="w-5 h-5" />
              注册设置
            </h3>
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={settings?.allow_registration ?? true}
                onChange={(e) => updateSettingsMutation.mutate({ allow_registration: e.target.checked })}
                disabled={updateSettingsMutation.isPending}
                className="w-5 h-5 rounded border-gray-300 text-primary-600 focus:ring-primary-500 disabled:opacity-50"
              />
              <div>
                <p className="font-medium dark:text-white">允许新用户注册</p>
                <p className="text-sm text-gray-500 dark:text-gray-400">关闭后，只有管理员可以添加新用户</p>
              </div>
            </label>
          </div>
        </div>
      )}

      {/* 同步间隔设置 */}
      {activeSubTab === 'sync' && (
      <div className="p-4 border dark:border-gray-700 rounded-lg">
        <h3 className="font-medium mb-4 dark:text-white flex items-center gap-2">
          <RefreshCw className="w-5 h-5" />
          同步间隔设置
        </h3>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
          控制用户可选择的订阅源同步间隔选项。取消勾选的选项将不会显示给用户。
        </p>
        <div className="space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
            {ALL_SYNC_INTERVALS.map((interval) => (
              <label key={interval.value} className="flex items-center gap-2 p-2 border dark:border-gray-600 rounded cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700">
                <input
                  type="checkbox"
                  checked={syncIntervals.some(i => i.value === interval.value)}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setSyncIntervals([...syncIntervals, interval].sort((a, b) => a.value - b.value))
                    } else {
                      setSyncIntervals(syncIntervals.filter(i => i.value !== interval.value))
                    }
                  }}
                  className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                />
                <span className="text-sm dark:text-gray-200">{interval.label}</span>
              </label>
            ))}
          </div>
          <div className="flex items-center gap-4">
            <label className="text-sm dark:text-gray-300">默认间隔：</label>
            <select
              value={defaultSyncInterval}
              onChange={(e) => setDefaultSyncInterval(parseInt(e.target.value))}
              className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
            >
              {syncIntervals.map((interval) => (
                <option key={interval.value} value={interval.value}>{interval.label}</option>
              ))}
            </select>
          </div>
          <button
            onClick={() => updateSettingsMutation.mutate({ sync_intervals: syncIntervals, default_sync_interval: defaultSyncInterval })}
            disabled={updateSettingsMutation.isPending || syncIntervals.length === 0}
            className="px-4 py-2 bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50"
          >
            {updateSettingsMutation.isPending ? '保存中...' : '保存同步设置'}
          </button>
        </div>
      </div>
      )}

      {/* OAuth 设置 - Linux.do */}
      {activeSubTab === 'oauth' && (
      <div className="p-4 border dark:border-gray-700 rounded-lg">
        <h3 className="font-medium mb-4 dark:text-white flex items-center gap-2">
          <Shield className="w-5 h-5" />
          第三方登录 - Linux.do
        </h3>
        <div className="space-y-4">
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={oauthLinuxdo.enabled}
              onChange={(e) => {
                const newConfig = { ...oauthLinuxdo, enabled: e.target.checked }
                setOauthLinuxdo(newConfig)
                // Auto-save when disabling OAuth
                if (!e.target.checked) {
                  updateSettingsMutation.mutate({ oauth_linuxdo: newConfig })
                }
              }}
              disabled={updateSettingsMutation.isPending}
              className="w-5 h-5 rounded border-gray-300 text-primary-600 focus:ring-primary-500 disabled:opacity-50"
            />
            <div>
              <p className="font-medium dark:text-white">启用 Linux.do 登录</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">允许用户使用 Linux.do 账号登录</p>
            </div>
          </label>
          
          {oauthLinuxdo.enabled && (
            <div className="space-y-3 pl-8">
              <div>
                <label className="block text-sm font-medium dark:text-gray-300 mb-1">Client ID</label>
                <input
                  type="text"
                  value={oauthLinuxdo.client_id}
                  onChange={(e) => setOauthLinuxdo({ ...oauthLinuxdo, client_id: e.target.value })}
                  placeholder="OAuth Client ID"
                  className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
                />
              </div>
              <div>
                <label className="block text-sm font-medium dark:text-gray-300 mb-1">Client Secret</label>
                <input
                  type="password"
                  value={oauthLinuxdo.client_secret}
                  onChange={(e) => setOauthLinuxdo({ ...oauthLinuxdo, client_secret: e.target.value })}
                  placeholder="OAuth Client Secret"
                  className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
                />
              </div>
              <div>
                <label className="block text-sm font-medium dark:text-gray-300 mb-1">Authorization URL</label>
                <input
                  type="text"
                  value={oauthLinuxdo.authorize_url}
                  onChange={(e) => setOauthLinuxdo({ ...oauthLinuxdo, authorize_url: e.target.value })}
                  placeholder="https://connect.linux.do/oauth2/authorize"
                  className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
                />
              </div>
              <div>
                <label className="block text-sm font-medium dark:text-gray-300 mb-1">Token URL</label>
                <input
                  type="text"
                  value={oauthLinuxdo.token_url}
                  onChange={(e) => setOauthLinuxdo({ ...oauthLinuxdo, token_url: e.target.value })}
                  placeholder="https://connect.linux.do/oauth2/token"
                  className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
                />
              </div>
              <div>
                <label className="block text-sm font-medium dark:text-gray-300 mb-1">User Info URL</label>
                <input
                  type="text"
                  value={oauthLinuxdo.userinfo_url}
                  onChange={(e) => setOauthLinuxdo({ ...oauthLinuxdo, userinfo_url: e.target.value })}
                  placeholder="https://connect.linux.do/api/user"
                  className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
                />
              </div>
              <div className="p-3 bg-gray-50 dark:bg-gray-800 rounded text-sm">
                <p className="font-medium dark:text-gray-300 mb-1">回调地址 (Redirect URI):</p>
                <code className="text-primary-600 dark:text-primary-400 break-all">
                  {window.location.origin}/api/v1/auth/callback/linuxdo
                </code>
              </div>
              <button
                onClick={() => updateSettingsMutation.mutate({ oauth_linuxdo: oauthLinuxdo })}
                disabled={updateSettingsMutation.isPending}
                className="px-4 py-2 bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50"
              >
                {updateSettingsMutation.isPending ? '保存中...' : '保存 OAuth 设置'}
              </button>
            </div>
          )}
        </div>
      </div>
      )}

      {/* 订阅推荐设置 */}
      {activeSubTab === 'recommendations' && (
        <RecommendationsManagement 
          enabled={settings?.enable_feed_recommendations ?? false}
          onToggle={(enabled) => updateSettingsMutation.mutate({ enable_feed_recommendations: enabled })}
          isPending={updateSettingsMutation.isPending}
        />
      )}

      {/* 通知管理 */}
      {activeSubTab === 'notifications' && (
        <div className="p-4 border dark:border-gray-700 rounded-lg">
          <NotificationManagement />
        </div>
      )}

      {/* 用户列表 */}
      {activeSubTab === 'users' && (
      <div className="p-4 border dark:border-gray-700 rounded-lg">
        <h3 className="font-medium mb-4 dark:text-white">用户管理</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm table-fixed">
            <thead>
              <tr className="border-b dark:border-gray-700">
                <th className="text-left py-2 px-3 dark:text-gray-300 w-12">ID</th>
                <th className="text-left py-2 px-3 dark:text-gray-300 w-24">用户名</th>
                <th className="text-left py-2 px-3 dark:text-gray-300 w-48">邮箱</th>
                <th className="text-left py-2 px-3 dark:text-gray-300 w-20">角色</th>
                <th className="text-left py-2 px-3 dark:text-gray-300 w-16">状态</th>
                <th className="text-left py-2 px-3 dark:text-gray-300 w-40">注册时间</th>
                <th className="text-left py-2 px-3 dark:text-gray-300 w-40">最后登录</th>
                <th className="text-left py-2 px-3 dark:text-gray-300">操作</th>
              </tr>
            </thead>
            <tbody>
              {users?.map((user) => (
                <tr key={user.id} className="border-b dark:border-gray-700">
                  <td className="py-2 px-3 dark:text-gray-300">{user.id}</td>
                  <td className="py-2 px-3 dark:text-white font-medium truncate" title={user.username}>{user.username}</td>
                  <td className="py-2 px-3 dark:text-gray-300 truncate" title={user.email}>{user.email}</td>
                  <td className="py-2 px-3">
                    {user.is_admin ? (
                      <span className="px-2 py-0.5 bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300 rounded text-xs">管理员</span>
                    ) : (
                      <span className="px-2 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 rounded text-xs">普通用户</span>
                    )}
                  </td>
                  <td className="py-2 px-3">
                    {user.is_active ? (
                      <span className="text-green-600 dark:text-green-400">正常</span>
                    ) : (
                      <span className="text-red-600 dark:text-red-400">已禁用</span>
                    )}
                  </td>
                  <td className="py-2 px-3 text-gray-500 dark:text-gray-400">
                    {user.created_at ? new Date(user.created_at).toLocaleString('zh-CN') : '-'}
                  </td>
                  <td className="py-2 px-3 text-gray-500 dark:text-gray-400">
                    {user.last_login_at ? new Date(user.last_login_at).toLocaleString('zh-CN') : '-'}
                  </td>
                  <td className="py-2 px-3">
                    <div className="flex gap-1 flex-wrap">
                      {/* 切换管理员 */}
                      <button
                        onClick={() => {
                          if (confirm(`确定要${user.is_admin ? '取消' : '设为'}管理员吗？`)) {
                            updateUserMutation.mutate({ userId: user.id, data: { is_admin: !user.is_admin } })
                          }
                        }}
                        disabled={updateUserMutation.isPending}
                        className={`px-2 py-1 text-xs rounded ${
                          user.is_admin 
                            ? 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600' 
                            : 'bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300 hover:bg-purple-200 dark:hover:bg-purple-900'
                        }`}
                        title={user.is_admin ? '取消管理员' : '设为管理员'}
                      >
                        {user.is_admin ? '取消管理' : '设为管理'}
                      </button>
                      {/* 切换状态 */}
                      <button
                        onClick={() => {
                          if (confirm(`确定要${user.is_active ? '禁用' : '启用'}该用户吗？${user.is_active ? '禁用后用户将无法登录。' : ''}`)) {
                            updateUserMutation.mutate({ userId: user.id, data: { is_active: !user.is_active } })
                          }
                        }}
                        disabled={updateUserMutation.isPending}
                        className={`px-2 py-1 text-xs rounded ${
                          user.is_active 
                            ? 'bg-yellow-100 dark:bg-yellow-900/50 text-yellow-700 dark:text-yellow-300 hover:bg-yellow-200 dark:hover:bg-yellow-900' 
                            : 'bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300 hover:bg-green-200 dark:hover:bg-green-900'
                        }`}
                        title={user.is_active ? '禁用用户' : '启用用户'}
                      >
                        {user.is_active ? '禁用' : '启用'}
                      </button>
                      {/* 删除用户 */}
                      <button
                        onClick={() => {
                          if (confirm(`确定要删除用户 "${user.username}" 吗？\n\n⚠️ 此操作不可恢复！将删除该用户的所有数据，包括订阅源、文章、规则等。`)) {
                            deleteUserMutation.mutate(user.id)
                          }
                        }}
                        disabled={deleteUserMutation.isPending}
                        className="px-2 py-1 text-xs rounded bg-red-100 dark:bg-red-900/50 text-red-700 dark:text-red-300 hover:bg-red-200 dark:hover:bg-red-900"
                        title="删除用户"
                      >
                        删除
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      )}
    </div>
  )
}
