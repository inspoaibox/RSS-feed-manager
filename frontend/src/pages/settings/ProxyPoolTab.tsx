import { ProxyEditState,proxyProtocols,ProxyUpdatePayload } from '@/pages/settings/shared'
import api from '@/services/api'
import type { ProxyPoolEntry,ProxyPoolGroups,ProxyPoolImportResult,ProxyPoolTestResult,ProxyProtocol } from '@/types'
import { getApiErrorMessage } from '@/utils/apiError'
import { useMutation,useQuery,useQueryClient } from '@tanstack/react-query'
import { Check,Edit2,Plus,RefreshCw,Trash2,Upload,X } from 'lucide-react'
import { useMemo,useState } from 'react'

export default function ProxyPoolTab() {
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
  const [proxyEdit, setProxyEdit] = useState<ProxyEditState>({
    raw: '',
    default_protocol: 'http' as ProxyProtocol,
    country: '',
    is_active: true,
    fail_count: '0',
  })
  const [proxyEditOriginal, setProxyEditOriginal] = useState<ProxyPoolEntry | null>(null)

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
      setProxyEditOriginal(null)
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
    setProxyEditOriginal(proxy)
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

    if (!proxyEditOriginal || proxyEditOriginal.id !== id) {
      showMessage('error', '代理编辑状态已过期，请重新打开编辑')
      setEditingProxyId(null)
      setProxyEditOriginal(null)
      return
    }

    const nextRaw = proxyEdit.raw.trim()
    const nextCountry = proxyEdit.country.trim() ? proxyEdit.country.trim() : null
    const nextFailCount = Math.max(0, parseInt(proxyEdit.fail_count) || 0)
    const payload: ProxyUpdatePayload = {}

    if (nextRaw !== proxyEditOriginal.proxy_url) {
      payload.raw = nextRaw
    }
    if (proxyEdit.default_protocol !== proxyEditOriginal.protocol) {
      payload.default_protocol = proxyEdit.default_protocol
    }
    if ((proxyEditOriginal.country || null) !== nextCountry) {
      payload.country = nextCountry
    }
    if (proxyEdit.is_active !== proxyEditOriginal.is_active) {
      payload.is_active = proxyEdit.is_active
    }
    if (nextFailCount !== proxyEditOriginal.fail_count) {
      payload.fail_count = nextFailCount
    }

    if (Object.keys(payload).length === 0) {
      setEditingProxyId(null)
      setProxyEditOriginal(null)
      return
    }

    updateMutation.mutate({
      id,
      data: payload,
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
                          onClick={() => {
                            setEditingProxyId(null)
                            setProxyEditOriginal(null)
                          }}
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
                    <td className="p-3 text-gray-600 dark:text-gray-300">{proxy.fail_count}</td>
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
