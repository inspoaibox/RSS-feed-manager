import { useState } from 'react'
import { X } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import api from '@/services/api'
import type { SubscriptionCreate, SubscriptionType, QuietHours } from '@/types/push-notification'
import type { Feed, Category } from '@/types'

interface AddSubscriptionModalProps {
  onClose: () => void
  onSubmit: (data: SubscriptionCreate) => void
  isLoading: boolean
}

export default function AddSubscriptionModal({ onClose, onSubmit, isLoading }: AddSubscriptionModalProps) {
  const [formData, setFormData] = useState<SubscriptionCreate>({
    name: '',
    subscription_type: 'feed',
    browser_notification: true,
    desktop_notification: true,
  })

  const [quietHours, setQuietHours] = useState<QuietHours>({ start: '', end: '' })
  const [enableQuietHours, setEnableQuietHours] = useState(false)

  // Fetch feeds
  const { data: feedsData } = useQuery({
    queryKey: ['feeds'],
    queryFn: async () => {
      const response = await api.get<Feed[]>('/feeds')
      return response.data
    },
    enabled: formData.subscription_type === 'feed',
  })

  // Fetch categories
  const { data: categoriesData } = useQuery({
    queryKey: ['categories'],
    queryFn: async () => {
      const response = await api.get<Category[]>('/categories')
      return response.data
    },
    enabled: formData.subscription_type === 'category',
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    // Validate
    if (!formData.name.trim()) {
      alert('请输入订阅名称')
      return
    }

    if (formData.subscription_type === 'feed' && !formData.target_id) {
      alert('请选择订阅源')
      return
    }

    if (formData.subscription_type === 'category' && !formData.target_id) {
      alert('请选择分组')
      return
    }

    if (formData.subscription_type === 'keyword' && !formData.keyword?.trim()) {
      alert('请输入关键词')
      return
    }

    // Build submission data
    const submitData: SubscriptionCreate = {
      ...formData,
      quiet_hours: enableQuietHours && quietHours.start && quietHours.end ? quietHours : undefined,
    }

    onSubmit(submitData)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />

      {/* Modal */}
      <div className="relative bg-white dark:bg-gray-800 rounded-lg shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b dark:border-gray-700">
          <h3 className="font-medium text-lg dark:text-white">添加订阅规则</h3>
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {/* Name */}
          <div>
            <label className="block text-sm font-medium dark:text-gray-300 mb-1">
              订阅名称 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="例如：重要新闻提醒"
              className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white"
            />
          </div>

          {/* Subscription Type */}
          <div>
            <label className="block text-sm font-medium dark:text-gray-300 mb-1">
              订阅类型 <span className="text-red-500">*</span>
            </label>
            <select
              value={formData.subscription_type}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  subscription_type: e.target.value as SubscriptionType,
                  target_id: undefined,
                  keyword: undefined,
                })
              }
              className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white"
            >
              <option value="feed">单个订阅源</option>
              <option value="category">订阅源分组</option>
              <option value="keyword">关键词</option>
            </select>
          </div>

          {/* Feed Selector */}
          {formData.subscription_type === 'feed' && (
            <div>
              <label className="block text-sm font-medium dark:text-gray-300 mb-1">
                选择订阅源 <span className="text-red-500">*</span>
              </label>
              <select
                value={formData.target_id || ''}
                onChange={(e) => setFormData({ ...formData, target_id: Number(e.target.value) })}
                className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white"
              >
                <option value="">请选择...</option>
                {feedsData?.map((feed) => (
                  <option key={feed.id} value={feed.id}>
                    {feed.title}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Category Selector */}
          {formData.subscription_type === 'category' && (
            <div>
              <label className="block text-sm font-medium dark:text-gray-300 mb-1">
                选择分组 <span className="text-red-500">*</span>
              </label>
              <select
                value={formData.target_id || ''}
                onChange={(e) => setFormData({ ...formData, target_id: Number(e.target.value) })}
                className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white"
              >
                <option value="">请选择...</option>
                {categoriesData?.map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Keyword Input */}
          {formData.subscription_type === 'keyword' && (
            <div>
              <label className="block text-sm font-medium dark:text-gray-300 mb-1">
                关键词 <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={formData.keyword || ''}
                onChange={(e) => setFormData({ ...formData, keyword: e.target.value })}
                placeholder="例如：AI、GPT、区块链"
                className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white"
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                当文章标题或内容包含该关键词时推送
              </p>
            </div>
          )}

          {/* Notification Methods */}
          <div>
            <label className="block text-sm font-medium dark:text-gray-300 mb-2">通知方式</label>
            <div className="space-y-2">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.browser_notification}
                  onChange={(e) =>
                    setFormData({ ...formData, browser_notification: e.target.checked })
                  }
                  className="w-4 h-4 rounded"
                />
                <span className="text-sm dark:text-gray-300">浏览器通知</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.desktop_notification}
                  onChange={(e) =>
                    setFormData({ ...formData, desktop_notification: e.target.checked })
                  }
                  className="w-4 h-4 rounded"
                />
                <span className="text-sm dark:text-gray-300">桌面通知</span>
              </label>
            </div>
          </div>

          {/* Quiet Hours */}
          <div>
            <label className="flex items-center gap-2 cursor-pointer mb-2">
              <input
                type="checkbox"
                checked={enableQuietHours}
                onChange={(e) => setEnableQuietHours(e.target.checked)}
                className="w-4 h-4 rounded"
              />
              <span className="text-sm font-medium dark:text-gray-300">设置静默时间</span>
            </label>

            {enableQuietHours && (
              <div className="flex items-center gap-2 ml-6">
                <input
                  type="time"
                  value={quietHours.start}
                  onChange={(e) => setQuietHours({ ...quietHours, start: e.target.value })}
                  className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white"
                />
                <span className="text-sm dark:text-gray-300">至</span>
                <input
                  type="time"
                  value={quietHours.end}
                  onChange={(e) => setQuietHours({ ...quietHours, end: e.target.value })}
                  className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white"
                />
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="flex gap-2 pt-4">
            <button
              type="submit"
              disabled={isLoading}
              className="flex-1 px-4 py-2 bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50"
            >
              {isLoading ? '保存中...' : '保存'}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-700 dark:text-gray-200"
            >
              取消
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
