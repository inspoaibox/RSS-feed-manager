import { useSyncIntervals } from '@/hooks/useSyncIntervals'
import { proxyProtocols,translationSourceLanguages,usesSourceLanguage } from '@/pages/settings/shared'
import api from '@/services/api'
import type { AIModel,Category,CustomRule,FeedProxyMode,ProxyPoolGroups,TranslateMethod } from '@/types'
import { getApiErrorMessage } from '@/utils/apiError'
import { useMutation,useQuery,useQueryClient } from '@tanstack/react-query'
import { Edit2,Plus,RefreshCw,Trash2 } from 'lucide-react'
import { useState } from 'react'

export default function RulesTab() {
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
    proxy_mode: 'none' as FeedProxyMode,
    proxy_enabled: false,
    proxy_url: '',
    proxy_pool_country: '',
    proxy_pool_protocol: '',
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

  const { data: proxyGroups = { countries: [], protocols: [] } } = useQuery({
    queryKey: ['proxy-groups'],
    queryFn: async () => {
      const response = await api.get<ProxyPoolGroups>('/proxies/groups')
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
        list_selector: formData.list_selector.trim(),
        title_selector: formData.title_selector.trim(),
        link_selector: formData.link_selector.trim() || null,
        content_selector: formData.content_selector.trim() || null,
        date_selector: formData.date_selector.trim() || null,
        proxy_mode: formData.proxy_mode,
        proxy_enabled: formData.proxy_mode !== 'none',
        proxy_url: formData.proxy_mode === 'single' ? formData.proxy_url.trim() : null,
        proxy_pool_country: formData.proxy_mode === 'pool' && formData.proxy_pool_country ? formData.proxy_pool_country : null,
        proxy_pool_protocol: formData.proxy_mode === 'pool' && formData.proxy_pool_protocol ? formData.proxy_pool_protocol : null,
        auto_translate: formData.translate_method !== 'none',
        source_language: usesSourceLanguage(formData.translate_method) && formData.source_language ? formData.source_language : null,
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
    onError: (err: unknown) => {
      const detail = getApiErrorMessage(err, '请求失败，请重试')
      setMessage({ type: 'error', text: detail || '添加失败' })
    },
  })

  const updateRuleMutation = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: typeof formData }) => {
      const payload = {
        ...data,
        cookies: data.cookies || null,
        list_selector: data.list_selector.trim(),
        title_selector: data.title_selector.trim(),
        link_selector: data.link_selector.trim() || null,
        content_selector: data.content_selector.trim() || null,
        date_selector: data.date_selector.trim() || null,
        proxy_mode: data.proxy_mode,
        proxy_enabled: data.proxy_mode !== 'none',
        proxy_url: data.proxy_mode === 'single' ? data.proxy_url.trim() : null,
        proxy_pool_country: data.proxy_mode === 'pool' && data.proxy_pool_country ? data.proxy_pool_country : null,
        proxy_pool_protocol: data.proxy_mode === 'pool' && data.proxy_pool_protocol ? data.proxy_pool_protocol : null,
        auto_translate: data.translate_method !== 'none',
        source_language: usesSourceLanguage(data.translate_method) && data.source_language ? data.source_language : null,
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
    onError: (err: unknown) => {
      const detail = getApiErrorMessage(err, '请求失败，请重试')
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
    onError: (err: unknown) => {
      const detail = getApiErrorMessage(err, '请求失败，请重试')
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
      queryClient.invalidateQueries({ queryKey: ['keyword-counts'] })
      setMessage({ type: 'success', text: `抓取完成，新增 ${data.articles_found} 篇文章` })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: unknown) => {
      const detail = getApiErrorMessage(err, '请求失败，请重试')
      setMessage({ type: 'error', text: detail || '抓取失败' })
    },
  })

  const testRuleMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        target_url: formData.target_url,
        list_selector: formData.list_selector.trim(),
        title_selector: formData.title_selector.trim(),
        link_selector: formData.link_selector.trim() || null,
        content_selector: formData.content_selector.trim() || null,
        date_selector: formData.date_selector.trim() || null,
        use_playwright: formData.use_playwright,
        proxy_mode: formData.proxy_mode,
        proxy_enabled: formData.proxy_mode !== 'none',
        proxy_url: formData.proxy_mode === 'single' ? formData.proxy_url.trim() : null,
        proxy_pool_country: formData.proxy_mode === 'pool' && formData.proxy_pool_country ? formData.proxy_pool_country : null,
        proxy_pool_protocol: formData.proxy_mode === 'pool' && formData.proxy_pool_protocol ? formData.proxy_pool_protocol : null,
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
    onError: (err: unknown) => {
      const detail = getApiErrorMessage(err, '请求失败，请重试')
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
      proxy_mode: rule.proxy_mode || (rule.proxy_enabled ? 'single' : 'none'),
      proxy_enabled: rule.proxy_mode !== 'none',
      proxy_url: rule.proxy_url || '',
      proxy_pool_country: rule.proxy_pool_country || '',
      proxy_pool_protocol: rule.proxy_pool_protocol || '',
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
            placeholder="标题选择器 (必填，相对于列表项内部)"
            value={formData.title_selector}
            onChange={(e) => setFormData({ ...formData, title_selector: e.target.value })}
            className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
          />
          <input
            type="text"
            placeholder="链接选择器 (可选，留空则使用列表项内第一个链接)"
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
                source_language: usesSourceLanguage(method) ? formData.source_language : '',
              })
            }}
            className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
          >
            <option value="none">不翻译</option>
            <option value="google">Google 翻译</option>
            <option value="argos">本地翻译</option>
            <option value="mc_translation">Mc-Translation</option>
            <option value="ai" disabled={!hasDefaultModel}>AI 翻译{!hasDefaultModel ? ' (需配置)' : ''}</option>
          </select>
          {usesSourceLanguage(formData.translate_method) && (
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
      <div className="grid gap-2 p-2 bg-slate-50 dark:bg-gray-800 border border-slate-200 dark:border-gray-600 rounded text-sm">
        <div className="flex items-center gap-2">
          <span className="text-gray-700 dark:text-gray-200">代理配置</span>
          <select
            value={formData.proxy_mode}
            onChange={(e) => {
              const mode = e.target.value as FeedProxyMode
              setFormData({
                ...formData,
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
        {formData.proxy_mode === 'single' && (
          <input
            type="text"
            value={formData.proxy_url}
            onChange={(e) => setFormData({ ...formData, proxy_url: e.target.value })}
            placeholder="http://user:pass@host:port 或 socks5://host:port"
            className="w-full px-3 py-2 border dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-700 dark:text-white"
          />
        )}
        {formData.proxy_mode === 'pool' && (
          <div className="grid grid-cols-2 gap-2">
            <select
              value={formData.proxy_pool_country}
              onChange={(e) => setFormData({ ...formData, proxy_pool_country: e.target.value })}
              className="px-3 py-2 border dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-700 dark:text-white"
            >
              <option value="">全部国家</option>
              {proxyGroups.countries.map((country) => (
                <option key={country} value={country}>{country.toUpperCase()}</option>
              ))}
            </select>
            <select
              value={formData.proxy_pool_protocol}
              onChange={(e) => setFormData({ ...formData, proxy_pool_protocol: e.target.value })}
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
      
      {testRuleMutation.data && (
        <div className={`p-3 rounded ${testRuleMutation.data.success ? 'bg-green-50 dark:bg-green-900/30' : 'bg-red-50 dark:bg-red-900/30'}`}>
          {testRuleMutation.data.success ? (
            <div>
              <p className="text-green-700 dark:text-green-400 font-medium mb-2">找到 {testRuleMutation.data.items_found} 个条目</p>
              {testRuleMutation.data.sample_items && testRuleMutation.data.sample_items.length > 0 && (
                <div className="mt-2 space-y-2">
                  <p className="text-sm text-gray-600 dark:text-gray-400">预览（前 5 条）：</p>
                  {testRuleMutation.data.sample_items.map((item: { title: string; link?: string; content?: string }, idx: number) => (
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
          disabled={!formData.target_url || (formData.rule_type === 'general' && (!formData.list_selector.trim() || !formData.title_selector.trim())) || (formData.proxy_mode === 'single' && !formData.proxy_url.trim()) || testRuleMutation.isPending}
          className="px-4 py-2 border dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-600 dark:text-gray-200 disabled:opacity-50"
        >
          测试规则
        </button>
        <button
          onClick={() => isEdit ? updateRuleMutation.mutate({ id: editingId!, data: formData }) : addRuleMutation.mutate()}
          disabled={!formData.name || !formData.target_url || (formData.rule_type === 'general' && (!formData.list_selector.trim() || !formData.title_selector.trim())) || (formData.proxy_mode === 'single' && !formData.proxy_url.trim()) || addRuleMutation.isPending || updateRuleMutation.isPending}
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
          自定义规则用于抓取没有 RSS 的网页列表，按 CSS 选择器提取每条内容的标题、链接、摘要和时间。
        </p>
        
        {showHelp && (
          <div className="mt-4 space-y-4 text-sm text-blue-800 dark:text-primary-300">
            <div>
              <h4 className="font-medium mb-2">先看懂要抓什么：</h4>
              <ul className="list-disc list-inside space-y-1 text-blue-700 dark:text-primary-400">
                <li><span className="font-medium">目标网址</span> - 包含文章、活动或商品列表的页面 URL。</li>
                <li><span className="font-medium">列表选择器</span> - 先选中每一条重复出现的卡片/列表项；匹配到 20 条，就会抓 20 条。</li>
                <li><span className="font-medium">标题选择器</span> - 在每条列表项内部选中标题文字，必填。</li>
                <li><span className="font-medium">链接选择器</span> - 在每条列表项内部选中详情链接，通常和标题选择器相同；留空时会使用列表项里的第一个链接。</li>
                <li><span className="font-medium">内容选择器</span> - 可选，在每条列表项内部选中摘要、时间地点、价格、状态等补充内容。</li>
                <li><span className="font-medium">日期选择器</span> - 可选，在每条列表项内部选中发布时间或活动时间。</li>
              </ul>
            </div>

            <div className="bg-white dark:bg-gray-800 p-3 rounded border border-blue-200 dark:border-gray-600">
              <h4 className="font-medium mb-2">最重要的规则：</h4>
              <ul className="list-disc list-inside space-y-1 text-blue-700 dark:text-primary-400">
                <li>列表选择器是在整页里找重复卡片。</li>
                <li>标题、链接、内容、日期选择器都是在每一张卡片内部继续找。</li>
                <li>如果测试显示 0 条，优先检查列表选择器。</li>
                <li>如果有条目但标题为空，检查标题选择器。</li>
                <li>如果有标题但链接为空，检查链接选择器。</li>
              </ul>
            </div>
            
            <div>
              <h4 className="font-medium mb-2">示例 - 活动列表：</h4>
              <div className="bg-white dark:bg-gray-800 p-3 rounded border border-blue-200 dark:border-gray-600 space-y-2">
                <p><span className="text-gray-500 dark:text-gray-400">列表选择器：</span> <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">li.event-item</code> 或 <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">.activity-card</code></p>
                <p><span className="text-gray-500 dark:text-gray-400">标题选择器：</span> <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">h3 a</code> 或 <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">.event-title a</code></p>
                <p><span className="text-gray-500 dark:text-gray-400">链接选择器：</span> <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">h3 a</code> 或 <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">.event-title a</code></p>
                <p><span className="text-gray-500 dark:text-gray-400">内容选择器：</span> <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">.event-meta</code> 或 <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">.summary</code></p>
                <p><span className="text-gray-500 dark:text-gray-400">日期选择器：</span> <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">.event-time</code> 或 <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">time</code></p>
              </div>
            </div>
            
            <div>
              <h4 className="font-medium mb-2">示例 - 新闻/博客列表：</h4>
              <div className="bg-white dark:bg-gray-800 p-3 rounded border border-blue-200 dark:border-gray-600 space-y-2">
                <p><span className="text-gray-500 dark:text-gray-400">目标网址：</span> <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">https://example.com/blog</code></p>
                <p><span className="text-gray-500 dark:text-gray-400">列表选择器：</span> <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">article.post</code> 或 <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">.post-item</code></p>
                <p><span className="text-gray-500 dark:text-gray-400">标题选择器：</span> <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">h2 a</code> 或 <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">.post-title a</code></p>
                <p><span className="text-gray-500 dark:text-gray-400">链接选择器：</span> <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">a.read-more</code> 或 <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">h2 a</code></p>
                <p><span className="text-gray-500 dark:text-gray-400">内容选择器：</span> <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">.excerpt</code> 或 <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">.summary</code></p>
                <p><span className="text-gray-500 dark:text-gray-400">日期选择器：</span> <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">time</code> 或 <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">.date</code></p>
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
                      {rule.translate_method === 'mc_translation' && <span>Mc-Translation</span>}
                      {rule.proxy_mode === 'single' && <span>单个代理</span>}
                      {rule.proxy_mode === 'pool' && (
                        <span>
                          代理池{rule.proxy_pool_country ? `/${rule.proxy_pool_country.toUpperCase()}` : ''}{rule.proxy_pool_protocol ? `/${rule.proxy_pool_protocol}` : ''}
                        </span>
                      )}
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
