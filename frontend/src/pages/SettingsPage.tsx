import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, Edit2, Check, X, Upload, Download, RefreshCw, Save, FolderOpen, Languages } from 'lucide-react'
import api from '@/services/api'
import type { Category, Feed, AIProvider, AIModel, CustomRule } from '@/types'

type Tab = 'feeds' | 'categories' | 'ai' | 'rules' | 'backup'

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<Tab>('feeds')

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">设置</h1>
      
      {/* Tabs */}
      <div className="flex border-b mb-6 flex-wrap">
        {[
          { id: 'feeds', label: '订阅源' },
          { id: 'categories', label: '分类' },
          { id: 'ai', label: 'AI 设置' },
          { id: 'rules', label: '自定义规则' },
          { id: 'backup', label: '备份恢复' },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as Tab)}
            className={`px-4 py-2 border-b-2 -mb-px ${
              activeTab === tab.id
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'feeds' && <FeedsTab />}
      {activeTab === 'categories' && <CategoriesTab />}
      {activeTab === 'ai' && <AITab />}
      {activeTab === 'rules' && <RulesTab />}
      {activeTab === 'backup' && <BackupTab />}
    </div>
  )
}

function FeedsTab() {
  const queryClient = useQueryClient()
  const [showAddForm, setShowAddForm] = useState(false)
  const [newFeedUrl, setNewFeedUrl] = useState('')
  const [newFeedCategory, setNewFeedCategory] = useState<number | null>(null)
  const [newFeedInterval, setNewFeedInterval] = useState(3600)
  const [newFeedPlaywright, setNewFeedPlaywright] = useState(false)
  const [newFeedAutoTranslate, setNewFeedAutoTranslate] = useState(false)
  const [newFeedAutoSummarize, setNewFeedAutoSummarize] = useState(false)
  const [newFeedTargetLanguage, setNewFeedTargetLanguage] = useState('zh-CN')
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editData, setEditData] = useState<{
    title: string
    category_id: number | null
    fetch_interval: number
    is_active: boolean
    use_playwright: boolean
    auto_translate: boolean
    auto_summarize: boolean
    target_language: string
  }>({ title: '', category_id: null, fetch_interval: 3600, is_active: true, use_playwright: false, auto_translate: false, auto_summarize: false, target_language: 'zh-CN' })

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

  const addFeedMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post('/feeds', { 
        url: newFeedUrl, 
        category_id: newFeedCategory,
        fetch_interval: newFeedInterval,
        use_playwright: newFeedPlaywright,
        auto_translate: newFeedAutoTranslate,
        auto_summarize: newFeedAutoSummarize,
        target_language: newFeedAutoTranslate ? newFeedTargetLanguage : null
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
      setNewFeedPlaywright(false)
      setNewFeedAutoTranslate(false)
      setNewFeedAutoSummarize(false)
      setNewFeedTargetLanguage('zh-CN')
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
      const response = await api.put(`/feeds/${id}`, data)
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
      auto_translate: feed.auto_translate,
      auto_summarize: feed.auto_summarize,
      target_language: feed.target_language || 'zh-CN'
    })
  }

  const formatInterval = (seconds: number) => {
    if (seconds < 3600) return `${Math.floor(seconds / 60)} 分钟`
    return `${Math.floor(seconds / 3600)} 小时`
  }

  return (
    <div>
      {message && (
        <div className={`mb-4 p-3 rounded ${message.type === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
          {message.text}
        </div>
      )}
      <div className="flex items-center gap-2 mb-4">
        <button
          onClick={() => setShowAddForm(true)}
          className="flex items-center gap-1 px-3 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          <Plus className="w-4 h-4" /> 添加订阅
        </button>
        <button
          onClick={handleExport}
          className="flex items-center gap-1 px-3 py-2 border rounded hover:bg-gray-50"
        >
          <Download className="w-4 h-4" /> 导出 OPML
        </button>
        <label className="flex items-center gap-1 px-3 py-2 border rounded hover:bg-gray-50 cursor-pointer">
          <Upload className="w-4 h-4" /> 导入 OPML
          <input type="file" accept=".opml,.xml" onChange={handleImport} className="hidden" />
        </label>
      </div>

      {showAddForm && (
        <div className="mb-4 p-4 border rounded bg-gray-50 space-y-3">
          <input
            type="url"
            placeholder="RSS 订阅地址"
            value={newFeedUrl}
            onChange={(e) => setNewFeedUrl(e.target.value)}
            className="w-full px-3 py-2 border rounded"
          />
          <div className="flex gap-2">
            <select
              value={newFeedCategory || ''}
              onChange={(e) => setNewFeedCategory(e.target.value ? parseInt(e.target.value) : null)}
              className="flex-1 px-3 py-2 border rounded"
            >
              <option value="">未分类</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
            <select
              value={newFeedInterval}
              onChange={(e) => setNewFeedInterval(parseInt(e.target.value))}
              className="flex-1 px-3 py-2 border rounded"
            >
              <option value={60}>1 分钟</option>
              <option value={120}>2 分钟</option>
              <option value={180}>3 分钟</option>
              <option value={240}>4 分钟</option>
              <option value={300}>5 分钟</option>
              <option value={900}>15 分钟</option>
              <option value={1800}>30 分钟</option>
              <option value={3600}>1 小时</option>
              <option value={7200}>2 小时</option>
              <option value={14400}>4 小时</option>
              <option value={43200}>12 小时</option>
              <option value={86400}>24 小时</option>
            </select>
          </div>
          <label className="flex items-center gap-2 p-2 bg-yellow-50 border border-yellow-200 rounded">
            <input
              type="checkbox"
              checked={newFeedPlaywright}
              onChange={(e) => setNewFeedPlaywright(e.target.checked)}
            />
            <span className="text-sm">使用浏览器模式 (Playwright)</span>
            <span className="text-xs text-yellow-600">适用于 Cloudflare 保护的网站</span>
          </label>
          <div className="flex gap-2 flex-wrap">
            <label className="flex items-center gap-2 p-2 bg-blue-50 border border-blue-200 rounded">
              <input
                type="checkbox"
                checked={newFeedAutoTranslate}
                onChange={(e) => setNewFeedAutoTranslate(e.target.checked)}
              />
              <span className="text-sm">启用 AI 翻译</span>
            </label>
            {newFeedAutoTranslate && (
              <select
                value={newFeedTargetLanguage}
                onChange={(e) => setNewFeedTargetLanguage(e.target.value)}
                className="px-3 py-2 border rounded text-sm"
              >
                <option value="zh-CN">简体中文</option>
                <option value="zh-TW">繁体中文</option>
                <option value="en">English</option>
                <option value="ja">日本語</option>
                <option value="ko">한국어</option>
              </select>
            )}
            <label className="flex items-center gap-2 p-2 bg-green-50 border border-green-200 rounded">
              <input
                type="checkbox"
                checked={newFeedAutoSummarize}
                onChange={(e) => setNewFeedAutoSummarize(e.target.checked)}
              />
              <span className="text-sm">启用 AI 整理</span>
            </label>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => addFeedMutation.mutate()}
              disabled={!newFeedUrl || addFeedMutation.isPending}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
            >
              {addFeedMutation.isPending ? '添加中...' : '添加'}
            </button>
            <button
              onClick={() => { setShowAddForm(false); setNewFeedUrl(''); setNewFeedCategory(null); setNewFeedPlaywright(false); setNewFeedAutoTranslate(false); setNewFeedAutoSummarize(false) }}
              className="px-4 py-2 border rounded hover:bg-gray-100"
            >
              取消
            </button>
          </div>
        </div>
      )}

      <div className="border rounded divide-y">
        {feeds.map((feed) => (
          <div key={feed.id} className="p-4">
            {editingId === feed.id ? (
              <div className="space-y-3">
                <div className="text-sm text-gray-500 bg-gray-100 px-3 py-2 rounded truncate">
                  {feed.url}
                </div>
                <input
                  type="text"
                  value={editData.title}
                  onChange={(e) => setEditData({ ...editData, title: e.target.value })}
                  className="w-full px-3 py-2 border rounded"
                  placeholder="订阅源标题"
                />
                <div className="flex gap-2">
                  <select
                    value={editData.category_id || ''}
                    onChange={(e) => setEditData({ ...editData, category_id: e.target.value ? parseInt(e.target.value) : null })}
                    className="flex-1 px-3 py-2 border rounded"
                  >
                    <option value="">未分类</option>
                    {categories.map((c) => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                  <select
                    value={editData.fetch_interval}
                    onChange={(e) => setEditData({ ...editData, fetch_interval: parseInt(e.target.value) })}
                    className="flex-1 px-3 py-2 border rounded"
                  >
                    <option value={60}>1 分钟</option>
                    <option value={120}>2 分钟</option>
                    <option value={180}>3 分钟</option>
                    <option value={240}>4 分钟</option>
                    <option value={300}>5 分钟</option>
                    <option value={900}>15 分钟</option>
                    <option value={1800}>30 分钟</option>
                    <option value={3600}>1 小时</option>
                    <option value={7200}>2 小时</option>
                    <option value={14400}>4 小时</option>
                    <option value={43200}>12 小时</option>
                    <option value={86400}>24 小时</option>
                  </select>
                  <label className="flex items-center gap-2 px-3 py-2 border rounded">
                    <input
                      type="checkbox"
                      checked={editData.is_active}
                      onChange={(e) => setEditData({ ...editData, is_active: e.target.checked })}
                    />
                    启用
                  </label>
                </div>
                <label className="flex items-center gap-2 p-2 bg-yellow-50 border border-yellow-200 rounded text-sm">
                  <input
                    type="checkbox"
                    checked={editData.use_playwright}
                    onChange={(e) => setEditData({ ...editData, use_playwright: e.target.checked })}
                  />
                  浏览器模式 (Playwright)
                </label>
                <div className="flex gap-2 flex-wrap">
                  <label className="flex items-center gap-2 p-2 bg-blue-50 border border-blue-200 rounded text-sm">
                    <input
                      type="checkbox"
                      checked={editData.auto_translate}
                      onChange={(e) => setEditData({ ...editData, auto_translate: e.target.checked })}
                    />
                    AI 翻译
                  </label>
                  {editData.auto_translate && (
                    <select
                      value={editData.target_language}
                      onChange={(e) => setEditData({ ...editData, target_language: e.target.value })}
                      className="px-3 py-2 border rounded text-sm"
                    >
                      <option value="zh-CN">简体中文</option>
                      <option value="zh-TW">繁体中文</option>
                      <option value="en">English</option>
                      <option value="ja">日本語</option>
                      <option value="ko">한국어</option>
                    </select>
                  )}
                  <label className="flex items-center gap-2 p-2 bg-green-50 border border-green-200 rounded text-sm">
                    <input
                      type="checkbox"
                      checked={editData.auto_summarize}
                      onChange={(e) => setEditData({ ...editData, auto_summarize: e.target.checked })}
                    />
                    AI 整理
                  </label>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => updateFeedMutation.mutate({ id: feed.id, data: editData })}
                    disabled={updateFeedMutation.isPending}
                    className="p-2 text-green-600 hover:bg-green-50 rounded"
                  >
                    <Check className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => setEditingId(null)}
                    className="p-2 text-gray-500 hover:bg-gray-100 rounded"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-4">
                <div className="flex-1 min-w-0">
                  <h3 className="font-medium truncate">{feed.title || '无标题'}</h3>
                  <p className="text-sm text-gray-500 truncate">{feed.url}</p>
                  <div className="flex gap-3 mt-1 text-xs text-gray-400 flex-wrap">
                    <span>同步间隔: {formatInterval(feed.fetch_interval)}</span>
                    {feed.category_id && categories.find(c => c.id === feed.category_id) && (
                      <span>分类: {categories.find(c => c.id === feed.category_id)?.name}</span>
                    )}
                    <span className={feed.is_active ? 'text-green-500' : 'text-red-500'}>
                      {feed.is_active ? '已启用' : '已禁用'}
                    </span>
                    {feed.use_playwright && (
                      <span className="text-yellow-600">🌐 浏览器模式</span>
                    )}
                    {feed.auto_translate && (
                      <span className="text-blue-600">🌐 AI翻译</span>
                    )}
                    {feed.auto_summarize && (
                      <span className="text-green-600">📝 AI整理</span>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => refreshFeedMutation.mutate(feed.id)}
                  disabled={refreshFeedMutation.isPending}
                  className="p-2 text-blue-500 hover:bg-blue-50 rounded disabled:opacity-50"
                  title="刷新订阅源"
                >
                  <RefreshCw className={`w-4 h-4 ${refreshFeedMutation.isPending ? 'animate-spin' : ''}`} />
                </button>
                {feed.auto_translate && (
                  <button
                    onClick={() => translateAllMutation.mutate(feed.id)}
                    disabled={translateAllMutation.isPending}
                    className="p-2 text-purple-500 hover:bg-purple-50 rounded disabled:opacity-50"
                    title="翻译所有旧文章"
                  >
                    <Languages className="w-4 h-4" />
                  </button>
                )}
                <button
                  onClick={() => startEdit(feed)}
                  className="p-2 text-gray-500 hover:bg-gray-100 rounded"
                  title="编辑"
                >
                  <Edit2 className="w-4 h-4" />
                </button>
                <button
                  onClick={() => deleteFeedMutation.mutate(feed.id)}
                  className="p-2 text-red-500 hover:bg-red-50 rounded"
                  title="删除"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>
        ))}
        {feeds.length === 0 && (
          <div className="p-4 text-center text-gray-500">暂无订阅源</div>
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

  return (
    <div>
      {message && (
        <div className={`mb-4 p-3 rounded ${message.type === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
          {message.text}
        </div>
      )}
      <div className="flex gap-2 mb-4">
        <input
          type="text"
          placeholder="新分类名称"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          className="flex-1 px-3 py-2 border rounded"
        />
        <button
          onClick={() => createMutation.mutate()}
          disabled={!newName || createMutation.isPending}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
        >
          添加
        </button>
      </div>

      <div className="border rounded divide-y">
        {categories.map((category) => (
          <div key={category.id} className="flex items-center gap-4 p-4">
            {editingId === category.id ? (
              <>
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="flex-1 px-3 py-1 border rounded"
                />
                <button
                  onClick={() => updateMutation.mutate({ id: category.id, name: editName })}
                  className="p-2 text-green-600 hover:bg-green-50 rounded"
                >
                  <Check className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setEditingId(null)}
                  className="p-2 text-gray-500 hover:bg-gray-100 rounded"
                >
                  <X className="w-4 h-4" />
                </button>
              </>
            ) : (
              <>
                <span className="flex-1">{category.name}</span>
                <span className="text-sm text-gray-500">{category.feed_count} 个订阅</span>
                <button
                  onClick={() => { setEditingId(category.id); setEditName(category.name) }}
                  className="p-2 text-gray-500 hover:bg-gray-100 rounded"
                >
                  <Edit2 className="w-4 h-4" />
                </button>
                <button
                  onClick={() => deleteMutation.mutate(category.id)}
                  className="p-2 text-red-500 hover:bg-red-50 rounded"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </>
            )}
          </div>
        ))}
        {categories.length === 0 && (
          <div className="p-4 text-center text-gray-500">暂无分类</div>
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
      const response = await api.get<{ translate_prompt: string; summarize_prompt: string }>('/ai/settings')
      return response.data
    },
  })

  // Initialize prompts when settings load
  if (settings && !prompts.translate && !prompts.summarize) {
    setPrompts({
      translate: settings.translate_prompt,
      summarize: settings.summarize_prompt,
    })
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

  const defaultModel = models.find(m => m.is_default)

  return (
    <div className="space-y-6">
      {message && (
        <div className={`p-3 rounded ${message.type === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
          {message.text}
        </div>
      )}

      {/* Default Model Selection */}
      <div className="p-4 border rounded bg-blue-50">
        <h2 className="text-lg font-semibold mb-3">默认模型</h2>
        <select
          value={defaultModel?.id || ''}
          onChange={(e) => e.target.value && setDefaultModelMutation.mutate(parseInt(e.target.value))}
          className="w-full px-3 py-2 border rounded bg-white"
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
          <p className="text-sm text-gray-500 mt-2">请先添加 AI 渠道并获取模型</p>
        )}
      </div>

      {/* Providers */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">AI 渠道</h2>
          <button
            onClick={() => setShowAddProvider(true)}
            className="flex items-center gap-1 px-3 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            <Plus className="w-4 h-4" /> 添加渠道
          </button>
        </div>

        {showAddProvider && (
          <div className="mb-4 p-4 border rounded bg-gray-50 space-y-3">
            <input
              type="text"
              placeholder="渠道名称"
              value={newProvider.name}
              onChange={(e) => setNewProvider({ ...newProvider, name: e.target.value })}
              className="w-full px-3 py-2 border rounded"
            />
            <select
              value={newProvider.type}
              onChange={(e) => setNewProvider({ ...newProvider, type: e.target.value as any })}
              className="w-full px-3 py-2 border rounded"
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
              className="w-full px-3 py-2 border rounded"
            />
            {newProvider.type === 'openai_compatible' && (
              <input
                type="url"
                placeholder="Base URL (如 https://api.example.com/v1)"
                value={newProvider.base_url}
                onChange={(e) => setNewProvider({ ...newProvider, base_url: e.target.value })}
                className="w-full px-3 py-2 border rounded"
              />
            )}
            <div className="flex gap-2">
              <button
                onClick={() => addProviderMutation.mutate()}
                disabled={!newProvider.name || !newProvider.api_key || addProviderMutation.isPending}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
              >
                保存
              </button>
              <button
                onClick={() => setShowAddProvider(false)}
                className="px-4 py-2 border rounded hover:bg-gray-100"
              >
                取消
              </button>
            </div>
          </div>
        )}

        <div className="border rounded divide-y">
          {providers.map((provider) => {
            const providerModels = models.filter(m => m.provider_id === provider.id)
            return (
              <div key={provider.id} className="p-4">
                <div className="flex items-center gap-4 mb-2">
                  <div className="flex-1">
                    <h3 className="font-medium">{provider.name}</h3>
                    <p className="text-sm text-gray-500">{provider.type}</p>
                  </div>
                  <button
                    onClick={() => fetchModelsMutation.mutate(provider.id)}
                    disabled={fetchModelsMutation.isPending}
                    className="px-3 py-1 text-sm border rounded hover:bg-gray-50"
                  >
                    获取模型
                  </button>
                  <button
                    onClick={() => deleteProviderMutation.mutate(provider.id)}
                    className="p-2 text-red-500 hover:bg-red-50 rounded"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
                {providerModels.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {providerModels.map(model => (
                      <span
                        key={model.id}
                        className={`px-2 py-0.5 text-xs rounded ${model.is_default ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'}`}
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
            <div className="p-4 text-center text-gray-500">暂无 AI 渠道</div>
          )}
        </div>
      </div>

      {/* Prompts */}
      <div>
        <h2 className="text-lg font-semibold mb-4">Prompt 设置</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              翻译 Prompt
              <span className="text-gray-400 font-normal ml-2">（使用 {'{target_language}'} 作为目标语言占位符）</span>
            </label>
            <textarea
              value={prompts.translate}
              onChange={(e) => setPrompts({ ...prompts, translate: e.target.value })}
              className="w-full px-3 py-2 border rounded h-24 text-sm"
              placeholder="You are a translator..."
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              整理 Prompt
            </label>
            <textarea
              value={prompts.summarize}
              onChange={(e) => setPrompts({ ...prompts, summarize: e.target.value })}
              className="w-full px-3 py-2 border rounded h-24 text-sm"
              placeholder="You are a summarizer..."
            />
          </div>
          <button
            onClick={() => savePromptsMutation.mutate()}
            disabled={savePromptsMutation.isPending}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
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
  const [showAddRule, setShowAddRule] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const emptyRule = {
    name: '',
    target_url: '',
    list_selector: '',
    title_selector: '',
    link_selector: '',
    content_selector: '',
    is_active: true,
  }
  const [formData, setFormData] = useState(emptyRule)

  const { data: rules = [] } = useQuery({
    queryKey: ['custom-rules'],
    queryFn: async () => {
      const response = await api.get<CustomRule[]>('/rules')
      return response.data
    },
  })

  const addRuleMutation = useMutation({
    mutationFn: async () => {
      await api.post('/rules', formData)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['custom-rules'] })
      setShowAddRule(false)
      setFormData(emptyRule)
      setMessage({ type: 'success', text: '规则添加成功' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      setMessage({ type: 'error', text: detail || '添加失败' })
    },
  })

  const updateRuleMutation = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: typeof formData }) => {
      await api.put(`/rules/${id}`, data)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['custom-rules'] })
      setEditingId(null)
      setFormData(emptyRule)
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
      setMessage({ type: 'success', text: '规则已删除' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      setMessage({ type: 'error', text: detail || '删除失败' })
    },
  })

  const testRuleMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post('/rules/test', formData)
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
        error?: string
      }>('/rules/generate', { target_url: url })
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
      list_selector: rule.list_selector,
      title_selector: rule.title_selector,
      link_selector: rule.link_selector,
      content_selector: rule.content_selector || '',
      is_active: rule.is_active,
    })
  }

  const cancelEdit = () => {
    setEditingId(null)
    setShowAddRule(false)
    setFormData(emptyRule)
  }

  const renderForm = (isEdit: boolean) => (
    <div className="mb-4 p-4 border rounded bg-gray-50 space-y-3">
      <input
        type="text"
        placeholder="规则名称"
        value={formData.name}
        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
        className="w-full px-3 py-2 border rounded"
      />
      <div className="flex gap-2">
        <input
          type="url"
          placeholder="目标网址"
          value={formData.target_url}
          onChange={(e) => setFormData({ ...formData, target_url: e.target.value })}
          className="flex-1 px-3 py-2 border rounded"
        />
        <button
          type="button"
          onClick={() => generateRuleMutation.mutate(formData.target_url)}
          disabled={!formData.target_url || generateRuleMutation.isPending}
          className="px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700 disabled:opacity-50 whitespace-nowrap"
        >
          {generateRuleMutation.isPending ? '分析中...' : '🤖 AI 生成'}
        </button>
      </div>
      <input
        type="text"
        placeholder="列表选择器 (CSS Selector)"
        value={formData.list_selector}
        onChange={(e) => setFormData({ ...formData, list_selector: e.target.value })}
        className="w-full px-3 py-2 border rounded"
      />
      <input
        type="text"
        placeholder="标题选择器"
        value={formData.title_selector}
        onChange={(e) => setFormData({ ...formData, title_selector: e.target.value })}
        className="w-full px-3 py-2 border rounded"
      />
      <input
        type="text"
        placeholder="链接选择器"
        value={formData.link_selector}
        onChange={(e) => setFormData({ ...formData, link_selector: e.target.value })}
        className="w-full px-3 py-2 border rounded"
      />
      <input
        type="text"
        placeholder="内容选择器 (可选)"
        value={formData.content_selector}
        onChange={(e) => setFormData({ ...formData, content_selector: e.target.value })}
        className="w-full px-3 py-2 border rounded"
      />
      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={formData.is_active}
          onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
        />
        启用规则
      </label>
      
      {testRuleMutation.data && (
        <div className={`p-3 rounded ${testRuleMutation.data.success ? 'bg-green-50' : 'bg-red-50'}`}>
          {testRuleMutation.data.success ? (
            <p className="text-green-700">找到 {testRuleMutation.data.items_found} 个条目</p>
          ) : (
            <p className="text-red-700">测试失败: {testRuleMutation.data.error}</p>
          )}
        </div>
      )}
      
      <div className="flex gap-2">
        <button
          onClick={() => testRuleMutation.mutate()}
          disabled={!formData.target_url || !formData.list_selector || testRuleMutation.isPending}
          className="px-4 py-2 border rounded hover:bg-gray-100 disabled:opacity-50"
        >
          测试规则
        </button>
        <button
          onClick={() => isEdit ? updateRuleMutation.mutate({ id: editingId!, data: formData }) : addRuleMutation.mutate()}
          disabled={!formData.name || !formData.target_url || addRuleMutation.isPending || updateRuleMutation.isPending}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {isEdit ? '更新' : '保存'}
        </button>
        <button
          onClick={cancelEdit}
          className="px-4 py-2 border rounded hover:bg-gray-100"
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
        <div className={`mb-4 p-3 rounded ${message.type === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
          {message.text}
        </div>
      )}
      
      {/* 使用说明 */}
      <div className="mb-4 p-4 bg-blue-50 border border-blue-200 rounded">
        <div className="flex items-center justify-between">
          <h3 className="font-medium text-blue-800">什么是自定义抓取规则？</h3>
          <button 
            onClick={() => setShowHelp(!showHelp)}
            className="text-blue-600 text-sm hover:underline"
          >
            {showHelp ? '收起' : '查看详情'}
          </button>
        </div>
        <p className="text-sm text-blue-700 mt-1">
          自定义规则用于抓取没有 RSS 订阅的网站内容，通过 CSS 选择器提取文章列表。
        </p>
        
        {showHelp && (
          <div className="mt-4 space-y-4 text-sm text-blue-800">
            <div>
              <h4 className="font-medium mb-2">字段说明：</h4>
              <ul className="list-disc list-inside space-y-1 text-blue-700">
                <li><span className="font-medium">目标网址</span> - 要抓取的网页 URL</li>
                <li><span className="font-medium">列表选择器</span> - 文章列表项的 CSS 选择器（每个匹配元素代表一篇文章）</li>
                <li><span className="font-medium">标题选择器</span> - 在列表项内，文章标题的选择器</li>
                <li><span className="font-medium">链接选择器</span> - 在列表项内，文章链接的选择器（通常是 a 标签）</li>
                <li><span className="font-medium">内容选择器</span> - 可选，文章摘要/内容的选择器</li>
              </ul>
            </div>
            
            <div>
              <h4 className="font-medium mb-2">示例 - 抓取 Hacker News：</h4>
              <div className="bg-white p-3 rounded border border-blue-200 space-y-2">
                <p><span className="text-gray-500">目标网址：</span> <code className="bg-gray-100 px-1 rounded">https://news.ycombinator.com</code></p>
                <p><span className="text-gray-500">列表选择器：</span> <code className="bg-gray-100 px-1 rounded">.athing</code></p>
                <p><span className="text-gray-500">标题选择器：</span> <code className="bg-gray-100 px-1 rounded">.titleline &gt; a</code></p>
                <p><span className="text-gray-500">链接选择器：</span> <code className="bg-gray-100 px-1 rounded">.titleline &gt; a</code></p>
              </div>
            </div>
            
            <div>
              <h4 className="font-medium mb-2">示例 - 抓取博客文章列表：</h4>
              <div className="bg-white p-3 rounded border border-blue-200 space-y-2">
                <p><span className="text-gray-500">目标网址：</span> <code className="bg-gray-100 px-1 rounded">https://example.com/blog</code></p>
                <p><span className="text-gray-500">列表选择器：</span> <code className="bg-gray-100 px-1 rounded">article.post</code> 或 <code className="bg-gray-100 px-1 rounded">.post-item</code></p>
                <p><span className="text-gray-500">标题选择器：</span> <code className="bg-gray-100 px-1 rounded">h2.title</code> 或 <code className="bg-gray-100 px-1 rounded">.post-title</code></p>
                <p><span className="text-gray-500">链接选择器：</span> <code className="bg-gray-100 px-1 rounded">a.read-more</code> 或 <code className="bg-gray-100 px-1 rounded">h2 a</code></p>
                <p><span className="text-gray-500">内容选择器：</span> <code className="bg-gray-100 px-1 rounded">.excerpt</code> 或 <code className="bg-gray-100 px-1 rounded">.summary</code></p>
              </div>
            </div>
            
            <div>
              <h4 className="font-medium mb-2">如何获取 CSS 选择器：</h4>
              <ol className="list-decimal list-inside space-y-1 text-blue-700">
                <li>在浏览器中打开目标网页</li>
                <li>按 F12 打开开发者工具</li>
                <li>使用元素选择器（左上角箭头图标）点击要抓取的元素</li>
                <li>右键点击 HTML 元素 → 复制 → 复制选择器</li>
                <li>简化选择器，保留关键的 class 或 id</li>
              </ol>
            </div>
            
            <p className="text-blue-600 italic">
              提示：添加规则后点击"测试规则"按钮验证选择器是否正确。
            </p>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">自定义抓取规则</h2>
        <button
          onClick={() => { setShowAddRule(true); setEditingId(null); setFormData(emptyRule) }}
          className="flex items-center gap-1 px-3 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          <Plus className="w-4 h-4" /> 添加规则
        </button>
      </div>

      {showAddRule && !editingId && renderForm(false)}

      <div className="border rounded divide-y">
        {rules.map((rule) => (
          <div key={rule.id}>
            {editingId === rule.id ? (
              renderForm(true)
            ) : (
              <div className="flex items-center gap-4 p-4">
                <div className="flex-1">
                  <h3 className="font-medium">{rule.name}</h3>
                  <p className="text-sm text-gray-500 truncate">{rule.target_url}</p>
                </div>
                <span className={`px-2 py-1 text-xs rounded ${rule.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                  {rule.is_active ? '启用' : '禁用'}
                </span>
                <button
                  onClick={() => startEdit(rule)}
                  className="p-2 text-gray-500 hover:bg-gray-100 rounded"
                >
                  <Edit2 className="w-4 h-4" />
                </button>
                <button
                  onClick={() => deleteRuleMutation.mutate(rule.id)}
                  className="p-2 text-red-500 hover:bg-red-50 rounded"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>
        ))}
        {rules.length === 0 && (
          <div className="p-4 text-center text-gray-500">暂无自定义规则</div>
        )}
      </div>
    </div>
  )
}

function BackupTab() {
  const queryClient = useQueryClient()
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [importResult, setImportResult] = useState<{
    categories_imported: number
    feeds_imported: number
    ai_providers_imported: number
    custom_rules_imported: number
    errors: string[]
  } | null>(null)

  const handleExport = async () => {
    try {
      const response = await api.get('/backup/export', { responseType: 'blob' })
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      
      // Get filename from header or use default
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
      
      setMessage({ type: 'success', text: '配置已导出' })
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
      
      // Refresh all data
      queryClient.invalidateQueries({ queryKey: ['feeds'] })
      queryClient.invalidateQueries({ queryKey: ['categories'] })
      queryClient.invalidateQueries({ queryKey: ['ai-providers'] })
      queryClient.invalidateQueries({ queryKey: ['ai-models'] })
      queryClient.invalidateQueries({ queryKey: ['custom-rules'] })
      
      if (response.data.errors?.length === 0) {
        setMessage({ type: 'success', text: '配置导入成功' })
      } else {
        setMessage({ type: 'error', text: '部分配置导入失败，请查看详情' })
      }
    } catch (err: any) {
      const detail = err.response?.data?.detail
      setMessage({ type: 'error', text: detail || '导入失败' })
    }
    
    // Reset file input
    e.target.value = ''
  }

  return (
    <div className="space-y-6">
      {message && (
        <div className={`p-3 rounded ${message.type === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
          {message.text}
        </div>
      )}

      {/* 说明 */}
      <div className="p-4 bg-blue-50 border border-blue-200 rounded">
        <h3 className="font-medium text-blue-800 mb-2">备份与恢复</h3>
        <p className="text-sm text-blue-700">
          导出功能会将所有配置保存为 JSON 文件，包括：订阅源、分类、AI 设置、自定义规则。
          导入时会跳过已存在的配置，不会覆盖现有数据。
        </p>
      </div>

      {/* 操作按钮 */}
      <div className="flex gap-4">
        <button
          onClick={handleExport}
          className="flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          <Save className="w-5 h-5" />
          导出所有配置
        </button>
        
        <label className="flex items-center gap-2 px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 cursor-pointer">
          <FolderOpen className="w-5 h-5" />
          导入配置文件
          <input
            type="file"
            accept=".json"
            onChange={handleImport}
            className="hidden"
          />
        </label>
      </div>

      {/* 导入结果 */}
      {importResult && (
        <div className="p-4 border rounded bg-gray-50">
          <h3 className="font-medium mb-3">导入结果</h3>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div className="flex justify-between p-2 bg-white rounded">
              <span>分类</span>
              <span className="font-medium text-green-600">+{importResult.categories_imported}</span>
            </div>
            <div className="flex justify-between p-2 bg-white rounded">
              <span>订阅源</span>
              <span className="font-medium text-green-600">+{importResult.feeds_imported}</span>
            </div>
            <div className="flex justify-between p-2 bg-white rounded">
              <span>AI 渠道</span>
              <span className="font-medium text-green-600">+{importResult.ai_providers_imported}</span>
            </div>
            <div className="flex justify-between p-2 bg-white rounded">
              <span>自定义规则</span>
              <span className="font-medium text-green-600">+{importResult.custom_rules_imported}</span>
            </div>
          </div>
          
          {importResult.errors.length > 0 && (
            <div className="mt-4">
              <h4 className="text-sm font-medium text-red-600 mb-2">错误信息：</h4>
              <ul className="text-sm text-red-600 list-disc list-inside">
                {importResult.errors.map((err, i) => (
                  <li key={i}>{err}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* 备份内容说明 */}
      <div className="border rounded">
        <h3 className="font-medium p-4 border-b bg-gray-50">备份包含的内容</h3>
        <div className="divide-y">
          <div className="p-4 flex items-center gap-3">
            <span className="w-8 h-8 flex items-center justify-center bg-blue-100 text-blue-600 rounded">📁</span>
            <div>
              <p className="font-medium">分类</p>
              <p className="text-sm text-gray-500">所有自定义分类名称</p>
            </div>
          </div>
          <div className="p-4 flex items-center gap-3">
            <span className="w-8 h-8 flex items-center justify-center bg-orange-100 text-orange-600 rounded">📰</span>
            <div>
              <p className="font-medium">订阅源</p>
              <p className="text-sm text-gray-500">URL、标题、分类、同步间隔、启用状态</p>
            </div>
          </div>
          <div className="p-4 flex items-center gap-3">
            <span className="w-8 h-8 flex items-center justify-center bg-purple-100 text-purple-600 rounded">🤖</span>
            <div>
              <p className="font-medium">AI 设置</p>
              <p className="text-sm text-gray-500">AI 渠道配置（包含 API Key）、模型列表</p>
            </div>
          </div>
          <div className="p-4 flex items-center gap-3">
            <span className="w-8 h-8 flex items-center justify-center bg-green-100 text-green-600 rounded">🕷️</span>
            <div>
              <p className="font-medium">自定义规则</p>
              <p className="text-sm text-gray-500">抓取规则配置（URL、选择器等）</p>
            </div>
          </div>
        </div>
      </div>

      <p className="text-sm text-gray-500">
        注意：备份文件包含 API Key 等敏感信息，请妥善保管。文章内容不包含在备份中。
      </p>
    </div>
  )
}
