import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ExternalLink, ChevronLeft, ChevronRight } from 'lucide-react'
import api from '@/services/api'
import type { PushListResponse } from '@/types/push-notification'
import clsx from 'clsx'

export default function PushHistory() {
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined)
  const pageSize = 10

  const { data, isLoading } = useQuery({
    queryKey: ['push-history', page, statusFilter],
    queryFn: async () => {
      const params: any = { page, size: pageSize }
      if (statusFilter) {
        params.status = statusFilter
      }
      const response = await api.get<PushListResponse>('/push-notifications/pushes', { params })
      return response.data
    },
  })

  const pushes = data?.pushes || []
  const totalPages = Math.ceil((data?.total || 0) / pageSize)

  const getStatusBadge = (status: string) => {
    const configs = {
      sent: { label: '已发送', className: 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300' },
      read: { label: '已读', className: 'bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-300' },
      clicked: { label: '已点击', className: 'bg-purple-50 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300' },
      failed: { label: '失败', className: 'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300' },
    }
    const config = configs[status as keyof typeof configs] || configs.sent
    return (
      <span className={clsx('px-2 py-0.5 text-xs rounded', config.className)}>
        {config.label}
      </span>
    )
  }

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 1) return '刚刚'
    if (diffMins < 60) return `${diffMins} 分钟前`
    if (diffHours < 24) return `${diffHours} 小时前`
    if (diffDays < 7) return `${diffDays} 天前`
    return date.toLocaleDateString('zh-CN')
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h4 className="font-medium dark:text-white">推送历史</h4>

        {/* Status Filter */}
        <select
          value={statusFilter || ''}
          onChange={(e) => {
            setStatusFilter(e.target.value || undefined)
            setPage(1)
          }}
          className="px-3 py-1.5 text-sm border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white"
        >
          <option value="">全部状态</option>
          <option value="sent">已发送</option>
          <option value="read">已读</option>
          <option value="clicked">已点击</option>
          <option value="failed">失败</option>
        </select>
      </div>

      {/* List */}
      {isLoading ? (
        <div className="text-center py-8 text-gray-500 dark:text-gray-400">加载中...</div>
      ) : pushes.length === 0 ? (
        <div className="text-center py-8 text-gray-500 dark:text-gray-400">暂无推送记录</div>
      ) : (
        <div className="space-y-2">
          {pushes.map((push) => (
            <div
              key={push.id}
              className="p-3 border dark:border-gray-700 rounded hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
            >
              <div className="flex items-start gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <span className="text-sm font-medium dark:text-white truncate">
                      {push.article_title}
                    </span>
                    {getStatusBadge(push.status)}
                  </div>

                  <div className="flex items-center gap-3 text-xs text-gray-500 dark:text-gray-400">
                    <span>📌 {push.subscription_name}</span>
                    <span>🕒 {formatDate(push.pushed_at)}</span>
                  </div>
                </div>

                {push.article_link && (
                  <a
                    href={push.article_link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
                    title="打开文章"
                  >
                    <ExternalLink className="w-4 h-4 text-gray-500 dark:text-gray-400" />
                  </a>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-4 border-t dark:border-gray-700">
          <div className="text-sm text-gray-500 dark:text-gray-400">
            共 {data?.total || 0} 条记录，第 {page} / {totalPages} 页
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page === 1}
              className="p-1.5 border dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>

            <button
              onClick={() => setPage(Math.min(totalPages, page + 1))}
              disabled={page === totalPages}
              className="p-1.5 border dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
