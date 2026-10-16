import api from '@/services/api'
import { getApiErrorMessage } from '@/utils/apiError'
import { useQuery,useQueryClient } from '@tanstack/react-query'
import { Download,FolderOpen,RefreshCw,Trash2,Upload } from 'lucide-react'
import { useState } from 'react'

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

export default function BackupTab() {
  const queryClient = useQueryClient()
  const [passphrase, setPassphrase] = useState('')
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
      const response = await api.post('/backup/export', { passphrase }, { responseType: 'blob' })
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
    } catch {
      setMessage({ type: 'error', text: '导出失败' })
    }
  }

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    
    const formData = new FormData()
    formData.append('file', file)
    if (passphrase) formData.append('passphrase', passphrase)
    
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
    } catch (err: unknown) {
      const detail = getApiErrorMessage(err, '请求失败，请重试')
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
    } catch (err: unknown) {
      const detail = getApiErrorMessage(err, '请求失败，请重试')
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
    } catch (err: unknown) {
      const detail = getApiErrorMessage(err, '请求失败，请重试')
      setMessage({ type: 'error', text: detail || 'WebDAV 配置保存失败' })
    } finally {
      setWebdavSaving(false)
    }
  }

  const handleWebDAVUpload = async () => {
    setWebdavUploading(true)
    try {
      await api.post('/backup/webdav/upload', { passphrase })
      setMessage({ type: 'success', text: '备份已上传到 WebDAV' })
      refetchBackups()
      setTimeout(() => setMessage(null), 3000)
    } catch (err: unknown) {
      const detail = getApiErrorMessage(err, '请求失败，请重试')
      setMessage({ type: 'error', text: detail || '上传备份失败' })
    } finally {
      setWebdavUploading(false)
    }
  }

  const handleWebDAVRestore = async (filename: string) => {
    if (!confirm(`确定要从 "${filename}" 恢复备份吗？已存在的数据会按唯一标识更新。`)) return
    
    setRestoringFile(filename)
    try {
      const response = await api.post(`/backup/webdav/restore/${encodeURIComponent(filename)}`, { passphrase })
      setImportResult(response.data)
      invalidateBackupRelatedQueries()
      
      if (response.data.errors?.length === 0) {
        setMessage({ type: 'success', text: '备份恢复成功' })
      } else {
        setMessage({ type: 'error', text: '部分数据恢复失败，请查看详情' })
      }
    } catch (err: unknown) {
      const detail = getApiErrorMessage(err, '请求失败，请重试')
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
    } catch (err: unknown) {
      const detail = getApiErrorMessage(err, '请求失败，请重试')
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
    } catch (err: unknown) {
      const detail = getApiErrorMessage(err, '请求失败，请重试')
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
          导出和云端上传会加密全部配置与文章。恢复时需要原备份密码，旧版未加密 JSON 仍可导入。
        </p>
      </div>

      {/* 本地操作按钮 */}
      <label className="block space-y-2 text-sm text-gray-700 dark:text-gray-300">
        <span>备份密码（12 至 256 个字符，请自行妥善保存）</span>
        <input type="password" autoComplete="new-password" minLength={12} maxLength={256}
          value={passphrase} onChange={(event) => setPassphrase(event.target.value)}
          className="input w-full max-w-md" />
        <span className="block text-xs text-gray-500">密码不会存入数据库；遗失后无法解密备份。</span>
      </label>
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
