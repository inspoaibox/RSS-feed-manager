import { useSyncIntervals } from '@/hooks/useSyncIntervals'
import { activeTranslateMethods,feedBrowserEngineLabels,proxyProtocols,resolveFeedBrowserEngine,resolveFeedProxyMode,translationSourceLanguages,usesSourceLanguage } from '@/pages/settings/shared'
import api from '@/services/api'
import type { AIModel,Category,Feed,FeedBrowserEngine,FeedProxyMode,FeedSourceType,ProxyPoolGroups,TranslateMethod } from '@/types'
import { getApiErrorMessage } from '@/utils/apiError'
import { useMutation,useQuery,useQueryClient } from '@tanstack/react-query'
import { Check,ChevronDown,ChevronUp,Download,Edit2,Languages,Plus,RefreshCw,Search,Trash2,Upload,X } from 'lucide-react'
import { useMemo,useState } from 'react'

export default function FeedsTab() {
  const queryClient = useQueryClient()
  const { syncIntervals, defaultSyncInterval } = useSyncIntervals()
  const [showAddForm, setShowAddForm] = useState(false)
  const [newFeedUrl, setNewFeedUrl] = useState('')
  const [newFeedSourceType, setNewFeedSourceType] = useState<FeedSourceType>('rss')
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
  const [newFeedTranslateTitle, setNewFeedTranslateTitle] = useState(true)
  const [newFeedTranslateContent, setNewFeedTranslateContent] = useState(false)
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
    translate_title: boolean
    translate_content: boolean
  }>({ title: '', category_id: null, fetch_interval: 3600, is_active: true, use_playwright: false, browser_engine: 'http', proxy_mode: 'none', proxy_enabled: false, proxy_url: '', proxy_pool_country: '', proxy_pool_protocol: '', auto_translate: false, auto_summarize: false, source_language: '', target_language: 'zh-CN', translate_method: 'none', translate_title: true, translate_content: false })
  
  // Filter states
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<number | 'all' | 'uncategorized'>('all')
  const [refreshingFeedIds, setRefreshingFeedIds] = useState<Set<number>>(() => new Set())

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
        source_type: newFeedSourceType,
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
        source_language: usesSourceLanguage(newFeedTranslateMethod) && newFeedSourceLanguage ? newFeedSourceLanguage : null,
        target_language: newFeedTranslateMethod !== 'none' ? newFeedTargetLanguage : null,
        translate_method: newFeedTranslateMethod,
        translate_title: newFeedTranslateTitle,
        translate_content: newFeedTranslateContent
      })
      return response.data
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['feeds'] })
      queryClient.invalidateQueries({ queryKey: ['categories'] })
      queryClient.invalidateQueries({ queryKey: ['articles'] })
      queryClient.invalidateQueries({ queryKey: ['keyword-counts'] })
      setShowAddForm(false)
      setNewFeedUrl('')
      setNewFeedSourceType('rss')
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
      setNewFeedTranslateTitle(true)
      setNewFeedTranslateContent(false)
      setMessage({ type: 'success', text: `订阅源 "${data.title || newFeedUrl}" 添加成功` })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: unknown) => {
      setMessage({ type: 'error', text: getApiErrorMessage(err, '添加订阅失败') })
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
        source_language: usesSourceLanguage(data.translate_method) && data.source_language ? data.source_language : null,
      })
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['feeds'] })
      queryClient.invalidateQueries({ queryKey: ['categories'] })
      queryClient.invalidateQueries({ queryKey: ['keyword-counts'] })
      setEditingId(null)
      setMessage({ type: 'success', text: '订阅源已更新' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: unknown) => {
      const detail = getApiErrorMessage(err, '请求失败，请重试')
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
      queryClient.invalidateQueries({ queryKey: ['keyword-counts'] })
      setMessage({ type: 'success', text: '订阅源已删除' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: unknown) => {
      const detail = getApiErrorMessage(err, '请求失败，请重试')
      setMessage({ type: 'error', text: detail || '删除失败' })
    },
  })

  const refreshFeedMutation = useMutation({
    mutationFn: async (feedId: number) => {
      const response = await api.post(`/feeds/${feedId}/refresh`)
      return response.data
    },
    onMutate: (feedId) => {
      setRefreshingFeedIds((prev) => {
        const next = new Set(prev)
        next.add(feedId)
        return next
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['feeds'] })
      queryClient.invalidateQueries({ queryKey: ['categories'] })
      queryClient.invalidateQueries({ queryKey: ['articles'] })
      queryClient.invalidateQueries({ queryKey: ['keyword-counts'] })
      setMessage({ type: 'success', text: '订阅源刷新成功' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: unknown) => {
      const detail = getApiErrorMessage(err, '请求失败，请重试')
      setMessage({ type: 'error', text: detail || '刷新失败' })
    },
    onSettled: (_data, _error, feedId) => {
      setRefreshingFeedIds((prev) => {
        const next = new Set(prev)
        next.delete(feedId)
        return next
      })
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
    onError: (err: unknown) => {
      const detail = getApiErrorMessage(err, '请求失败，请重试')
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
    onError: (err: unknown) => {
      const detail = getApiErrorMessage(err, '请求失败，请重试')
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
    } catch {
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
    } catch (err: unknown) {
      const detail = getApiErrorMessage(err, '请求失败，请重试')
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
      translate_method: feed.translate_method || 'none',
      translate_title: feed.translate_title ?? true,
      translate_content: feed.translate_content ?? false
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
    const match = url.match(/(?:t\.me|telegram\.me)\/([^/?]+)/)
    if (match) {
      return `https://rsshub.app/telegram/channel/${match[1]}`
    }
    return url
  }

  const handleUrlChange = (url: string) => {
    if (newFeedSourceType === 'rss' && isTelegramUrl(url)) {
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
          <div className="flex gap-2">
            <select
              value={newFeedSourceType}
              onChange={(e) => {
                const sourceType = e.target.value as FeedSourceType
                setNewFeedSourceType(sourceType)
                if (sourceType === 'whmcs' && newFeedBrowserEngine === 'cloakbrowser') {
                  setNewFeedBrowserEngine('http')
                }
              }}
              className="w-44 px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
            >
              <option value="rss">普通订阅源</option>
              <option value="whmcs">WHMCS 监控</option>
            </select>
            <input
              type="text"
              placeholder={newFeedSourceType === 'whmcs' ? 'WHMCS 产品页地址' : 'RSS 订阅地址 (支持 Telegram 频道链接自动转换)'}
              value={newFeedUrl}
              onChange={(e) => handleUrlChange(e.target.value)}
              className="flex-1 px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
            />
          </div>
          <div>
            {newFeedSourceType === 'rss' && (
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              💡 支持直接粘贴 Telegram 频道链接 (如 https://t.me/channel_name)，将自动转换为 RSSHub 格式
              </p>
            )}
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
              {newFeedSourceType === 'rss' && (
                <option value="cloakbrowser">增强浏览器模式 (CloakBrowser)</option>
              )}
            </select>
            <span className="text-xs text-yellow-600 dark:text-yellow-400">
              {newFeedSourceType === 'whmcs' ? 'WHMCS 监控支持普通抓取或 Playwright' : 'CloakBrowser 作为独立增强方案'}
            </span>
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
            {usesSourceLanguage(newFeedTranslateMethod) && (
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
            {newFeedTranslateMethod !== 'none' && (
              <div className="flex items-center gap-2 p-2 bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-800 rounded">
                <span className="text-sm dark:text-blue-200">翻译范围:</span>
                <label className="flex items-center gap-1">
                  <input
                    type="checkbox"
                    checked={newFeedTranslateTitle}
                    onChange={(e) => {
                      const checked = e.target.checked
                      if (!checked && !newFeedTranslateContent) {
                        setMessage({ type: 'error', text: '至少需要翻译标题或正文' })
                        return
                      }
                      setNewFeedTranslateTitle(checked)
                    }}
                  />
                  <span className="text-sm dark:text-blue-200">标题</span>
                </label>
                <label className="flex items-center gap-1">
                  <input
                    type="checkbox"
                    checked={newFeedTranslateContent}
                    onChange={(e) => {
                      const checked = e.target.checked
                      if (!checked && !newFeedTranslateTitle) {
                        setMessage({ type: 'error', text: '至少需要翻译标题或正文' })
                        return
                      }
                      setNewFeedTranslateContent(checked)
                    }}
                  />
                  <span className="text-sm dark:text-blue-200">正文</span>
                </label>
              </div>
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
                setNewFeedSourceType('rss')
                setNewFeedCategory(null)
                setNewFeedBrowserEngine('http')
                setNewFeedProxyMode('none')
                setNewFeedProxyUrl('')
                setNewFeedProxyPoolCountry('')
                setNewFeedProxyPoolProtocol('')
                setNewFeedAutoSummarize(false)
                setNewFeedTranslateMethod('none')
                setNewFeedTranslateTitle(true)
                setNewFeedTranslateContent(false)
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
                          source_language: usesSourceLanguage(method) ? editData.source_language : '',
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
                  {usesSourceLanguage(editData.translate_method) && (
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

                {editData.translate_method !== 'none' && (
                  <div className="flex items-center gap-2 p-2 bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-800 rounded">
                    <span className="text-sm dark:text-blue-200">翻译范围:</span>
                    <label className="flex items-center gap-1">
                      <input
                        type="checkbox"
                        checked={editData.translate_title}
                        onChange={(e) => {
                          const checked = e.target.checked
                          if (!checked && !editData.translate_content) {
                            setMessage({ type: 'error', text: '至少需要翻译标题或正文' })
                            return
                          }
                          setEditData({ ...editData, translate_title: checked })
                        }}
                      />
                      <span className="text-sm dark:text-blue-200">标题</span>
                    </label>
                    <label className="flex items-center gap-1">
                      <input
                        type="checkbox"
                        checked={editData.translate_content}
                        onChange={(e) => {
                          const checked = e.target.checked
                          if (!checked && !editData.translate_title) {
                            setMessage({ type: 'error', text: '至少需要翻译标题或正文' })
                            return
                          }
                          setEditData({ ...editData, translate_content: checked })
                        }}
                      />
                      <span className="text-sm dark:text-blue-200">正文</span>
                    </label>
                  </div>
                )}

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
                {(() => {
                  const isRefreshingThisFeed = refreshingFeedIds.has(feed.id)
                  return (
                    <button
                      onClick={() => refreshFeedMutation.mutate(feed.id)}
                      disabled={isRefreshingThisFeed}
                      className="p-2 text-primary-500 hover:bg-primary-50 dark:hover:bg-primary-900/30 rounded disabled:opacity-50"
                      title="刷新订阅源"
                    >
                      <RefreshCw className={`w-4 h-4 ${isRefreshingThisFeed ? 'animate-spin' : ''}`} />
                    </button>
                  )
                })()}
                {activeTranslateMethods.includes(feed.translate_method) && (
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
