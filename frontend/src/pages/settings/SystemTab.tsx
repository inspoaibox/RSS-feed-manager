import NotificationManagement from '@/components/NotificationManagement'
import PushNotificationSettings from '@/components/PushNotificationSettings'
import api from '@/services/api'
import { getApiErrorMessage } from '@/utils/apiError'
import { useMutation,useQuery,useQueryClient } from '@tanstack/react-query'
import { Check,Edit2,Plus,RefreshCw,Shield,Star,Trash2,X } from 'lucide-react'
import { useState } from 'react'

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
    } catch (err: unknown) {
      setMessage({ type: 'error', text: getApiErrorMessage(err, '验证失败') })
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
    onError: (err: unknown) => {
      setMessage({ type: 'error', text: getApiErrorMessage(err, '添加失败') })
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
    onError: (err: unknown) => {
      setMessage({ type: 'error', text: getApiErrorMessage(err, '更新失败') })
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
    onError: (err: unknown) => {
      setMessage({ type: 'error', text: getApiErrorMessage(err, '删除失败') })
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
  browser_fetch: BrowserFetchSettings
  worker_runtime: WorkerRuntimeSettings
  browser_worker_runtime: BrowserWorkerRuntimeSettings
}

type BrowserWaitUntil = 'domcontentloaded' | 'load' | 'networkidle'

interface BrowserFetchSettings {
  feed_browser_refresh_dispatch_limit: number
  custom_rule_browser_dispatch_limit: number
  playwright_timeout_seconds: number
  cloakbrowser_timeout_seconds: number
  playwright_wait_until: BrowserWaitUntil
  cloakbrowser_wait_until: BrowserWaitUntil
  viewport_width: number
  viewport_height: number
  user_agent: string
  user_agent_pool: string[]
  user_agent_rotate: boolean
  block_images: boolean
  block_media: boolean
  cloakbrowser_humanize: boolean
  cloakbrowser_geoip: boolean
}

interface BrowserWorkerRuntimeSettings {
  browser_worker_concurrency: number
  browser_worker_max_tasks_per_child: number
  browser_worker_cpus: number
}

interface WorkerRuntimeSettings {
  worker_concurrency: number
  worker_max_tasks_per_child: number
  worker_cpus: number
}

const DEFAULT_BROWSER_FETCH_SETTINGS: BrowserFetchSettings = {
  feed_browser_refresh_dispatch_limit: 50,
  custom_rule_browser_dispatch_limit: 1,
  playwright_timeout_seconds: 90,
  cloakbrowser_timeout_seconds: 90,
  playwright_wait_until: 'networkidle',
  cloakbrowser_wait_until: 'networkidle',
  viewport_width: 1920,
  viewport_height: 1080,
  user_agent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  user_agent_pool: [],
  user_agent_rotate: false,
  block_images: false,
  block_media: false,
  cloakbrowser_humanize: true,
  cloakbrowser_geoip: false,
}

const BROWSER_WAIT_OPTIONS: Array<{ value: BrowserWaitUntil; label: string }> = [
  { value: 'domcontentloaded', label: 'DOM 加载完成' },
  { value: 'load', label: '页面 Load' },
  { value: 'networkidle', label: '网络空闲' },
]

const USER_AGENT_TEMPLATES = [
  { label: 'Chrome Windows', value: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' },
  { label: 'Chrome macOS', value: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' },
  { label: 'Firefox Windows', value: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0' },
  { label: 'Safari macOS', value: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15' },
  { label: 'Edge Windows', value: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0' },
  { label: 'iPhone Safari', value: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1' },
  { label: 'Android Chrome', value: 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.144 Mobile Safari/537.36' },
]

const formatCpuLimit = (value: number | null | undefined) => {
  if (value === null || value === undefined) return '-'
  return value <= 0 ? '不限制' : `${value} CPU`
}

type SystemSubTab = 'general' | 'sync' | 'workers' | 'browser' | 'oauth' | 'recommendations' | 'announcements' | 'push-notifications' | 'users'

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

export default function SystemTab() {
  const queryClient = useQueryClient()
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [siteName, setSiteName] = useState('')
  const [syncIntervals, setSyncIntervals] = useState<SyncIntervalOption[]>([])
  const [defaultSyncInterval, setDefaultSyncInterval] = useState(3600)
  const [browserFetchSettings, setBrowserFetchSettings] = useState<BrowserFetchSettings>(DEFAULT_BROWSER_FETCH_SETTINGS)
  const [workerSettings, setWorkerSettings] = useState<WorkerRuntimeSettings>({
    worker_concurrency: 5,
    worker_max_tasks_per_child: 20,
    worker_cpus: 1.0,
  })
  const [browserWorkerSettings, setBrowserWorkerSettings] = useState<BrowserWorkerRuntimeSettings>({
    browser_worker_concurrency: 3,
    browser_worker_max_tasks_per_child: 20,
    browser_worker_cpus: 0,
  })
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
      if (response.data.browser_fetch) {
        setBrowserFetchSettings(response.data.browser_fetch)
      }
      if (response.data.worker_runtime) {
        setWorkerSettings(response.data.worker_runtime)
      }
      if (response.data.browser_worker_runtime) {
        setBrowserWorkerSettings(response.data.browser_worker_runtime)
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
      browser_fetch?: BrowserFetchSettings
      worker_runtime?: WorkerRuntimeSettings
      browser_worker_runtime?: BrowserWorkerRuntimeSettings
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
    onError: (err: unknown) => {
      const detail = getApiErrorMessage(err, '请求失败，请重试')
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
    onError: (err: unknown) => {
      const detail = getApiErrorMessage(err, '请求失败，请重试')
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
    onError: (err: unknown) => {
      const detail = getApiErrorMessage(err, '请求失败，请重试')
      setMessage({ type: 'error', text: detail || '删除失败' })
    },
  })

  const [activeSubTab, setActiveSubTab] = useState<SystemSubTab>('general')

  const updateBrowserFetchSetting = <K extends keyof BrowserFetchSettings>(
    key: K,
    value: BrowserFetchSettings[K],
  ) => {
    setBrowserFetchSettings((prev) => ({ ...prev, [key]: value }))
  }

  if (isLoading) {
    return <div className="text-center py-8 text-gray-500 dark:text-gray-400">加载中...</div>
  }

  const subTabs = [
    { id: 'general', label: '基本设置' },
    { id: 'sync', label: '同步设置' },
    { id: 'workers', label: '任务队列' },
    { id: 'browser', label: '浏览器抓取' },
    { id: 'oauth', label: '第三方登录' },
    { id: 'recommendations', label: '订阅推荐' },
    { id: 'announcements', label: '公告管理' },
    { id: 'push-notifications', label: '推送通知' },
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

      {/* 任务队列启动参数 */}
      {activeSubTab === 'workers' && (
        <div className="p-4 border dark:border-gray-700 rounded-lg">
          <h3 className="font-medium mb-4 dark:text-white flex items-center gap-2">
            <RefreshCw className="w-5 h-5" />
            任务队列配置
          </h3>

          <div className="space-y-6">
            {/* 普通 Worker 配置 */}
            <div className="p-4 border dark:border-gray-700 rounded-lg bg-gray-50 dark:bg-gray-800">
              <div className="flex items-center justify-between gap-3 mb-4">
                <h4 className="font-medium dark:text-gray-100">普通 Worker</h4>
                <span className="text-xs font-mono text-gray-500 dark:text-gray-400">feed, translation, celery</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <label className="block">
                  <span className="block text-sm font-medium dark:text-gray-300 mb-1">并发数</span>
                  <input
                    type="number"
                    min={1}
                    max={20}
                    value={workerSettings.worker_concurrency}
                    onChange={(e) => setWorkerSettings({ ...workerSettings, worker_concurrency: Number(e.target.value) })}
                    className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
                  />
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">当前: {settings?.worker_runtime?.worker_concurrency ?? '-'}</p>
                </label>

                <label className="block">
                  <span className="block text-sm font-medium dark:text-gray-300 mb-1">子进程最大任务数</span>
                  <input
                    type="number"
                    min={1}
                    max={200}
                    value={workerSettings.worker_max_tasks_per_child}
                    onChange={(e) => setWorkerSettings({ ...workerSettings, worker_max_tasks_per_child: Number(e.target.value) })}
                    className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
                  />
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">当前: {settings?.worker_runtime?.worker_max_tasks_per_child ?? '-'}</p>
                </label>

                <label className="block">
                  <span className="block text-sm font-medium dark:text-gray-300 mb-1">CPU 限额</span>
                  <input
                    type="number"
                    min={0}
                    max={16}
                    step={0.1}
                    value={workerSettings.worker_cpus}
                    onChange={(e) => setWorkerSettings({ ...workerSettings, worker_cpus: Number(e.target.value) })}
                    className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
                  />
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">当前: {formatCpuLimit(settings?.worker_runtime?.worker_cpus)}</p>
                </label>
              </div>

              <p className="text-xs text-gray-500 dark:text-gray-400 mt-3">
                提示：0 表示不限制 CPU，建议根据服务器性能调整
              </p>
            </div>

            {/* 浏览器 Worker 配置 */}
            <div className="p-4 border dark:border-gray-700 rounded-lg bg-gray-50 dark:bg-gray-800">
              <div className="flex items-center justify-between gap-3 mb-4">
                <h4 className="font-medium dark:text-gray-100">浏览器 Worker</h4>
                <span className="text-xs font-mono text-gray-500 dark:text-gray-400">browser</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <label className="block">
                  <span className="block text-sm font-medium dark:text-gray-300 mb-1">并发数</span>
                  <input
                    type="number"
                    min={1}
                    max={20}
                    value={browserWorkerSettings.browser_worker_concurrency}
                    onChange={(e) => setBrowserWorkerSettings({ ...browserWorkerSettings, browser_worker_concurrency: Number(e.target.value) })}
                    className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
                  />
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">当前: {settings?.browser_worker_runtime?.browser_worker_concurrency ?? '-'}</p>
                </label>

                <label className="block">
                  <span className="block text-sm font-medium dark:text-gray-300 mb-1">子进程最大任务数</span>
                  <input
                    type="number"
                    min={1}
                    max={200}
                    value={browserWorkerSettings.browser_worker_max_tasks_per_child}
                    onChange={(e) => setBrowserWorkerSettings({ ...browserWorkerSettings, browser_worker_max_tasks_per_child: Number(e.target.value) })}
                    className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
                  />
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">当前: {settings?.browser_worker_runtime?.browser_worker_max_tasks_per_child ?? '-'}</p>
                </label>

                <label className="block">
                  <span className="block text-sm font-medium dark:text-gray-300 mb-1">CPU 限额</span>
                  <input
                    type="number"
                    min={0}
                    max={16}
                    step={0.1}
                    value={browserWorkerSettings.browser_worker_cpus}
                    onChange={(e) => setBrowserWorkerSettings({ ...browserWorkerSettings, browser_worker_cpus: Number(e.target.value) })}
                    className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
                  />
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">当前: {formatCpuLimit(settings?.browser_worker_runtime?.browser_worker_cpus)}</p>
                </label>
              </div>

              <p className="text-xs text-gray-500 dark:text-gray-400 mt-3">
                提示：浏览器 Worker 消耗内存较多，建议并发数不超过 5
              </p>
            </div>

            {/* 保存按钮和说明 */}
            <div className="border-t dark:border-gray-700 pt-4">
              <button
                onClick={() => updateSettingsMutation.mutate({
                  worker_runtime: workerSettings,
                  browser_worker_runtime: browserWorkerSettings
                })}
                disabled={updateSettingsMutation.isPending}
                className="px-4 py-2 bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50 transition-colors"
              >
                {updateSettingsMutation.isPending ? '保存中...' : '保存配置'}
              </button>

              <div className="mt-4 p-4 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded">
                <h5 className="font-medium text-yellow-800 dark:text-yellow-200 mb-2">重要提示</h5>
                <p className="text-sm text-yellow-700 dark:text-yellow-300 mb-3">
                  并发数和子进程最大任务数保存后会写入系统设置，重启对应 Worker 容器后生效：
                </p>
                <div className="bg-gray-900 dark:bg-gray-950 text-gray-100 p-3 rounded font-mono text-xs overflow-x-auto">
                  cd /root/RSS-feed-manager<br />
                  docker compose -f docker-compose.prod.yml -f docker-compose.prod.build.yml --profile browser restart celery_worker celery_browser_worker
                </div>
                <p className="text-xs text-yellow-700 dark:text-yellow-300 mt-3">
                  CPU 限额属于 Docker 容器资源配置，需要重新创建容器才会应用。
                </p>
              </div>

              <div className="mt-4 text-sm text-gray-600 dark:text-gray-400">
                <p className="font-medium mb-2">配置建议（根据服务器规格）：</p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
                  <div>• 1核2G: 普通Worker并发1, CPU 0.8</div>
                  <div>• 2核4G: 普通Worker并发2, CPU 1.5</div>
                  <div>• 4核8G: 普通Worker并发3, CPU 2.0</div>
                  <div>• 8核16G: 普通Worker并发5, CPU 4.0</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 浏览器抓取设置 */}
      {activeSubTab === 'browser' && (
        <div className="p-4 border dark:border-gray-700 rounded-lg">
          <h3 className="font-medium mb-4 dark:text-white flex items-center gap-2">
            <RefreshCw className="w-5 h-5" />
            浏览器抓取设置
          </h3>

          <div className="space-y-6">
            <div>
              <h4 className="text-sm font-medium dark:text-gray-200 mb-3">队列派发</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <label className="block">
                  <span className="block text-sm font-medium dark:text-gray-300 mb-1">RSS 浏览器每轮派发</span>
                  <input
                    type="number"
                    min={1}
                    max={500}
                    value={browserFetchSettings.feed_browser_refresh_dispatch_limit}
                    onChange={(e) => updateBrowserFetchSetting('feed_browser_refresh_dispatch_limit', Number(e.target.value))}
                    className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
                  />
                </label>
                <label className="block">
                  <span className="block text-sm font-medium dark:text-gray-300 mb-1">自定义规则浏览器每轮派发</span>
                  <input
                    type="number"
                    min={1}
                    max={100}
                    value={browserFetchSettings.custom_rule_browser_dispatch_limit}
                    onChange={(e) => updateBrowserFetchSetting('custom_rule_browser_dispatch_limit', Number(e.target.value))}
                    className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
                  />
                </label>
              </div>
            </div>

            <div>
              <h4 className="text-sm font-medium dark:text-gray-200 mb-3">页面加载</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <label className="block">
                  <span className="block text-sm font-medium dark:text-gray-300 mb-1">Playwright 超时（秒）</span>
                  <input
                    type="number"
                    min={5}
                    max={300}
                    value={browserFetchSettings.playwright_timeout_seconds}
                    onChange={(e) => updateBrowserFetchSetting('playwright_timeout_seconds', Number(e.target.value))}
                    className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
                  />
                </label>
                <label className="block">
                  <span className="block text-sm font-medium dark:text-gray-300 mb-1">CloakBrowser 超时（秒）</span>
                  <input
                    type="number"
                    min={5}
                    max={300}
                    value={browserFetchSettings.cloakbrowser_timeout_seconds}
                    onChange={(e) => updateBrowserFetchSetting('cloakbrowser_timeout_seconds', Number(e.target.value))}
                    className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
                  />
                </label>
                <label className="block">
                  <span className="block text-sm font-medium dark:text-gray-300 mb-1">Playwright 等待策略</span>
                  <select
                    value={browserFetchSettings.playwright_wait_until}
                    onChange={(e) => updateBrowserFetchSetting('playwright_wait_until', e.target.value as BrowserWaitUntil)}
                    className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
                  >
                    {BROWSER_WAIT_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  <span className="block text-sm font-medium dark:text-gray-300 mb-1">CloakBrowser 等待策略</span>
                  <select
                    value={browserFetchSettings.cloakbrowser_wait_until}
                    onChange={(e) => updateBrowserFetchSetting('cloakbrowser_wait_until', e.target.value as BrowserWaitUntil)}
                    className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
                  >
                    {BROWSER_WAIT_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                </label>
              </div>
            </div>

            <div>
              <h4 className="text-sm font-medium dark:text-gray-200 mb-3">User-Agent 池</h4>

              <div className="space-y-3">
                {/* 随机轮换开关 */}
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={browserFetchSettings.user_agent_rotate}
                    onChange={(e) => updateBrowserFetchSetting('user_agent_rotate', e.target.checked)}
                    className="w-5 h-5 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                  />
                  <span className="font-medium dark:text-white">随机轮换 User-Agent</span>
                  <span className="text-xs text-gray-500 dark:text-gray-400">每次抓取随机选择一个 UA</span>
                </label>

                {/* UA 列表 */}
                <div className="space-y-2">
                  {(browserFetchSettings.user_agent_pool || []).map((ua, index) => (
                    <div key={index} className="flex gap-2">
                      <input
                        type="text"
                        value={ua}
                        onChange={(e) => {
                          const newPool = [...(browserFetchSettings.user_agent_pool || [])]
                          newPool[index] = e.target.value
                          updateBrowserFetchSetting('user_agent_pool', newPool)
                        }}
                        placeholder="输入 User-Agent"
                        className="flex-1 px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white text-sm"
                      />
                      <button
                        onClick={() => {
                          const newPool = (browserFetchSettings.user_agent_pool || []).filter((_, i) => i !== index)
                          updateBrowserFetchSetting('user_agent_pool', newPool)
                        }}
                        className="px-3 py-2 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30 rounded"
                        title="删除"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>

                {/* 添加 UA 按钮 */}
                <div className="flex gap-2">
                  <button
                    onClick={() => {
                      const newPool = [...(browserFetchSettings.user_agent_pool || []), '']
                      updateBrowserFetchSetting('user_agent_pool', newPool)
                    }}
                    className="px-3 py-2 text-sm bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-200 rounded hover:bg-gray-200 dark:hover:bg-gray-600"
                  >
                    <Plus className="w-4 h-4 inline mr-1" />
                    添加自定义 UA
                  </button>
                </div>

                {/* 预设模板 */}
                <div className="border-t dark:border-gray-700 pt-3">
                  <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">快速添加常用 User-Agent：</p>
                  <div className="grid grid-cols-2 gap-2">
                    {USER_AGENT_TEMPLATES.map((template) => (
                      <button
                        key={template.label}
                        onClick={() => {
                          const newPool = [...(browserFetchSettings.user_agent_pool || []), template.value]
                          updateBrowserFetchSetting('user_agent_pool', newPool)
                        }}
                        className="px-3 py-2 text-xs bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded hover:bg-blue-100 dark:hover:bg-blue-900/50"
                      >
                        {template.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* 后备 UA */}
                <div className="border-t dark:border-gray-700 pt-3">
                  <label className="block">
                    <span className="block text-sm font-medium dark:text-gray-300 mb-1">
                      后备 User-Agent
                      <span className="text-xs text-gray-500 dark:text-gray-400 ml-2">（当 UA 池为空时使用）</span>
                    </span>
                    <textarea
                      rows={2}
                      value={browserFetchSettings.user_agent}
                      onChange={(e) => updateBrowserFetchSetting('user_agent', e.target.value)}
                      className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white text-sm"
                    />
                  </label>
                </div>
              </div>
            </div>

            <div>
              <h4 className="text-sm font-medium dark:text-gray-200 mb-3">资源与增强模式</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={browserFetchSettings.block_images}
                    onChange={(e) => updateBrowserFetchSetting('block_images', e.target.checked)}
                    className="w-5 h-5 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                  />
                  <span className="font-medium dark:text-white">拦截图片</span>
                </label>
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={browserFetchSettings.block_media}
                    onChange={(e) => updateBrowserFetchSetting('block_media', e.target.checked)}
                    className="w-5 h-5 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                  />
                  <span className="font-medium dark:text-white">拦截媒体和字体</span>
                </label>
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={browserFetchSettings.cloakbrowser_humanize}
                    onChange={(e) => updateBrowserFetchSetting('cloakbrowser_humanize', e.target.checked)}
                    className="w-5 h-5 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                  />
                  <span className="font-medium dark:text-white">CloakBrowser humanize</span>
                </label>
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={browserFetchSettings.cloakbrowser_geoip}
                    onChange={(e) => updateBrowserFetchSetting('cloakbrowser_geoip', e.target.checked)}
                    className="w-5 h-5 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                  />
                  <span className="font-medium dark:text-white">CloakBrowser geoip</span>
                </label>
              </div>
            </div>

            <button
              onClick={() => updateSettingsMutation.mutate({ browser_fetch: browserFetchSettings })}
              disabled={updateSettingsMutation.isPending}
              className="px-4 py-2 bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50"
            >
              {updateSettingsMutation.isPending ? '保存中...' : '保存浏览器抓取设置'}
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

      {/* 公告管理 */}
      {activeSubTab === 'announcements' && (
        <div className="p-4 border dark:border-gray-700 rounded-lg">
          <NotificationManagement />
        </div>
      )}

      {/* 推送通知 */}
      {activeSubTab === 'push-notifications' && (
        <div className="p-4 border dark:border-gray-700 rounded-lg">
          <PushNotificationSettings />
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
