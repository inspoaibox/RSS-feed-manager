import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, Bell, Power, History } from 'lucide-react'
import api from '@/services/api'
import type {
  NotificationSubscription,
  SubscriptionCreate,
  SubscriptionListResponse,
  PushStats,
} from '@/types/push-notification'
import clsx from 'clsx'
import BrowserPermissionStatus from './push/BrowserPermissionStatus'
import AddSubscriptionModal from './push/AddSubscriptionModal'
import PushHistory from './push/PushHistory'

export default function PushNotificationSettings() {
  const queryClient = useQueryClient()
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [showAddModal, setShowAddModal] = useState(false)
  const [showHistory, setShowHistory] = useState(false)

  // Fetch subscriptions
  const { data: subsData, isLoading: subsLoading } = useQuery({
    queryKey: ['push-subscriptions'],
    queryFn: async () => {
      const response = await api.get<SubscriptionListResponse>('/push-notifications/subscriptions')
      return response.data
    },
  })

  // Fetch stats
  const { data: statsData } = useQuery({
    queryKey: ['push-stats'],
    queryFn: async () => {
      const response = await api.get<PushStats>('/push-notifications/pushes/stats')
      return response.data
    },
  })

  // Create subscription
  const createMutation = useMutation({
    mutationFn: async (data: SubscriptionCreate) => {
      const response = await api.post('/push-notifications/subscriptions', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['push-subscriptions'] })
      queryClient.invalidateQueries({ queryKey: ['push-stats'] })
      setShowAddModal(false)
      setMessage({ type: 'success', text: '订阅已创建' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      setMessage({ type: 'error', text: detail || '创建失败' })
    },
  })

  // Toggle subscription
  const toggleMutation = useMutation({
    mutationFn: async (id: number) => {
      const response = await api.post(`/push-notifications/subscriptions/${id}/toggle`)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['push-subscriptions'] })
      setMessage({ type: 'success', text: '订阅状态已更新' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      setMessage({ type: 'error', text: detail || '更新失败' })
    },
  })

  // Delete subscription
  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/push-notifications/subscriptions/${id}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['push-subscriptions'] })
      queryClient.invalidateQueries({ queryKey: ['push-stats'] })
      setMessage({ type: 'success', text: '订阅已删除' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      setMessage({ type: 'error', text: detail || '删除失败' })
    },
  })

  const subscriptions = subsData?.subscriptions || []
  const stats = statsData || { total_pushes: 0, unread_pushes: 0, clicked_pushes: 0 }

  return (
    <div className="space-y-6">
      {message && (
        <div
          className={`p-3 rounded ${
            message.type === 'success'
              ? 'bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-400'
              : 'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-400'
          }`}
        >
          {message.text}
        </div>
      )}

      {/* Header */}
      <div>
        <h3 className="font-medium dark:text-white flex items-center gap-2 text-lg">
          <Bell className="w-5 h-5" />
          推送通知设置
        </h3>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          订阅特定内容的更新通知，即使关闭网页也不会错过重要信息
        </p>
      </div>

      {/* Browser Permission Status */}
      <BrowserPermissionStatus />

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-4 border dark:border-gray-700 rounded-lg bg-blue-50 dark:bg-blue-900/20">
          <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">{stats.total_pushes}</div>
          <div className="text-sm text-gray-600 dark:text-gray-400 mt-1">总推送数</div>
        </div>
        <div className="p-4 border dark:border-gray-700 rounded-lg bg-amber-50 dark:bg-amber-900/20">
          <div className="text-2xl font-bold text-amber-600 dark:text-amber-400">{stats.unread_pushes}</div>
          <div className="text-sm text-gray-600 dark:text-gray-400 mt-1">未读推送</div>
        </div>
        <div className="p-4 border dark:border-gray-700 rounded-lg bg-green-50 dark:bg-green-900/20">
          <div className="text-2xl font-bold text-green-600 dark:text-green-400">{stats.clicked_pushes}</div>
          <div className="text-sm text-gray-600 dark:text-gray-400 mt-1">已点击</div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between">
        <h4 className="font-medium dark:text-white">我的订阅规则</h4>
        <div className="flex gap-2">
          <button
            onClick={() => setShowHistory(!showHistory)}
            className="flex items-center gap-1 px-3 py-2 border dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-700 dark:text-gray-200"
          >
            <History className="w-4 h-4" />
            推送历史
          </button>
          <button
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-1 px-3 py-2 bg-primary-600 text-white rounded hover:bg-primary-700"
          >
            <Plus className="w-4 h-4" />
            添加订阅
          </button>
        </div>
      </div>

      {/* History Panel */}
      {showHistory && (
        <div className="border dark:border-gray-700 rounded-lg p-4 bg-gray-50 dark:bg-gray-800">
          <PushHistory />
        </div>
      )}

      {/* Subscriptions List */}
      {subsLoading ? (
        <div className="text-center py-8 text-gray-500 dark:text-gray-400">加载中...</div>
      ) : subscriptions.length === 0 ? (
        <div className="text-center py-12 border dark:border-gray-700 rounded-lg">
          <Bell className="w-12 h-12 mx-auto mb-3 text-gray-300 dark:text-gray-600" />
          <p className="text-gray-500 dark:text-gray-400 mb-4">还没有订阅规则</p>
          <button
            onClick={() => setShowAddModal(true)}
            className="px-4 py-2 bg-primary-600 text-white rounded hover:bg-primary-700"
          >
            创建第一个订阅
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {subscriptions.map((sub) => (
            <SubscriptionCard
              key={sub.id}
              subscription={sub}
              onToggle={() => toggleMutation.mutate(sub.id)}
              onDelete={() => {
                if (confirm(`确定删除订阅"${sub.name}"吗？`)) {
                  deleteMutation.mutate(sub.id)
                }
              }}
            />
          ))}
        </div>
      )}

      {/* Add Subscription Modal */}
      {showAddModal && (
        <AddSubscriptionModal
          onClose={() => setShowAddModal(false)}
          onSubmit={(data) => createMutation.mutate(data)}
          isLoading={createMutation.isPending}
        />
      )}
    </div>
  )
}

// Subscription Card Component
function SubscriptionCard({
  subscription,
  onToggle,
  onDelete,
}: {
  subscription: NotificationSubscription
  onToggle: () => void
  onDelete: () => void
}) {
  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'feed':
        return '📰'
      case 'category':
        return '📁'
      case 'keyword':
        return '🔍'
      default:
        return '📌'
    }
  }

  const getTypeLabel = (type: string) => {
    switch (type) {
      case 'feed':
        return '订阅源'
      case 'category':
        return '分组'
      case 'keyword':
        return '关键词'
      default:
        return type
    }
  }

  return (
    <div
      className={clsx(
        'p-4 border dark:border-gray-700 rounded-lg transition-opacity',
        !subscription.is_enabled && 'opacity-50'
      )}
    >
      <div className="flex items-start gap-3">
        <div className="text-2xl">{getTypeIcon(subscription.subscription_type)}</div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-2">
            <h4 className="font-medium dark:text-white">{subscription.name}</h4>
            <span className="px-2 py-0.5 text-xs rounded bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400">
              {getTypeLabel(subscription.subscription_type)}
            </span>
            {!subscription.is_enabled && (
              <span className="px-2 py-0.5 text-xs rounded bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400">
                已禁用
              </span>
            )}
          </div>

          <div className="text-sm text-gray-600 dark:text-gray-300">
            {subscription.target_name || subscription.keyword || '-'}
          </div>

          <div className="flex items-center gap-3 mt-2 text-xs text-gray-500 dark:text-gray-400">
            {subscription.browser_notification && <span>🌐 浏览器通知</span>}
            {subscription.desktop_notification && <span>🖥️ 桌面通知</span>}
            {subscription.quiet_hours && <span>🌙 静默时间</span>}
          </div>
        </div>

        <div className="flex items-center gap-1">
          {/* Toggle */}
          <button
            onClick={onToggle}
            className={clsx(
              'p-2 rounded hover:bg-gray-100 dark:hover:bg-gray-700',
              subscription.is_enabled ? 'text-green-600 dark:text-green-400' : 'text-gray-400'
            )}
            title={subscription.is_enabled ? '禁用' : '启用'}
          >
            <Power className="w-4 h-4" />
          </button>

          {/* Delete */}
          <button
            onClick={onDelete}
            className="p-2 text-gray-500 hover:text-red-600 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
            title="删除"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
