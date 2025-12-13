import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Rss, Users, Check, Plus, Loader2 } from 'lucide-react'
import api from '@/services/api'
import type { RecommendedFeed, Category } from '@/types'

interface RecommendationStatus {
  enabled: boolean
  category_tags: string[]
}

export default function RecommendationsPage() {
  const queryClient = useQueryClient()
  const [selectedTag, setSelectedTag] = useState<string | null>(null)
  const [subscribeModal, setSubscribeModal] = useState<RecommendedFeed | null>(null)
  const [selectedCategory, setSelectedCategory] = useState<number | null>(null)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  // 获取推荐状态
  const { data: status, isLoading: statusLoading } = useQuery({
    queryKey: ['recommendations-status'],
    queryFn: async () => {
      const response = await api.get<RecommendationStatus>('/recommendations/status')
      return response.data
    },
  })

  // 获取推荐列表
  const { data: recommendations = [], isLoading: listLoading } = useQuery({
    queryKey: ['recommendations', selectedTag],
    queryFn: async () => {
      const params = selectedTag ? { category: selectedTag } : {}
      const response = await api.get<RecommendedFeed[]>('/recommendations', { params })
      return response.data
    },
    enabled: status?.enabled,
  })

  // 获取用户分类
  const { data: categories = [] } = useQuery({
    queryKey: ['categories'],
    queryFn: async () => {
      const response = await api.get<Category[]>('/categories')
      return response.data
    },
  })

  // 订阅
  const subscribeMutation = useMutation({
    mutationFn: async ({ id, categoryId }: { id: number; categoryId: number | null }) => {
      const response = await api.post(`/recommendations/${id}/subscribe`, { category_id: categoryId })
      return response.data
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['recommendations'] })
      queryClient.invalidateQueries({ queryKey: ['feeds'] })
      queryClient.invalidateQueries({ queryKey: ['categories'] })
      setSubscribeModal(null)
      setMessage({ type: 'success', text: data.message || '订阅成功' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      setMessage({ type: 'error', text: detail || '订阅失败' })
    },
  })

  if (statusLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-primary-500" />
      </div>
    )
  }

  if (!status?.enabled) {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <div className="text-center py-16">
          <Rss className="w-16 h-16 mx-auto text-gray-300 dark:text-gray-600 mb-4" />
          <h2 className="text-xl font-medium text-gray-600 dark:text-gray-400 mb-2">订阅推荐功能未开启</h2>
          <p className="text-gray-500 dark:text-gray-500">请联系管理员开启此功能</p>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold dark:text-white mb-2">订阅推荐</h1>
        <p className="text-gray-600 dark:text-gray-400">发现优质 RSS 订阅源，一键订阅</p>
      </div>

      {message && (
        <div className={`mb-4 p-3 rounded ${message.type === 'success' ? 'bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-400' : 'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-400'}`}>
          {message.text}
        </div>
      )}

      {/* 分类标签筛选 */}
      {status.category_tags.length > 0 && (
        <div className="mb-6 flex gap-2 flex-wrap">
          <button
            onClick={() => setSelectedTag(null)}
            className={`px-3 py-1.5 rounded-full text-sm transition-colors ${
              selectedTag === null
                ? 'bg-primary-600 text-white'
                : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
            }`}
          >
            全部
          </button>
          {status.category_tags.map(tag => (
            <button
              key={tag}
              onClick={() => setSelectedTag(tag)}
              className={`px-3 py-1.5 rounded-full text-sm transition-colors ${
                selectedTag === tag
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
              }`}
            >
              {tag}
            </button>
          ))}
        </div>
      )}

      {/* 推荐列表 */}
      {listLoading ? (
        <div className="flex items-center justify-center h-32">
          <Loader2 className="w-6 h-6 animate-spin text-primary-500" />
        </div>
      ) : recommendations.length === 0 ? (
        <div className="text-center py-12 text-gray-500 dark:text-gray-400">
          暂无推荐源
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {recommendations.map(rec => (
            <div
              key={rec.id}
              className="p-4 border dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 hover:shadow-md transition-shadow"
            >
              <div className="flex items-start gap-3">
                {rec.icon_url ? (
                  <img src={rec.icon_url} alt="" className="w-10 h-10 rounded flex-shrink-0" />
                ) : (
                  <div className="w-10 h-10 rounded bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center flex-shrink-0">
                    <Rss className="w-5 h-5 text-primary-600 dark:text-primary-400" />
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <h3 className="font-medium dark:text-white truncate">{rec.title}</h3>
                    {rec.is_subscribed ? (
                      <span className="flex items-center gap-1 text-xs text-green-600 dark:text-green-400 flex-shrink-0">
                        <Check className="w-3.5 h-3.5" />
                        已订阅
                      </span>
                    ) : (
                      <button
                        onClick={() => {
                          setSubscribeModal(rec)
                          setSelectedCategory(null)
                        }}
                        className="flex items-center gap-1 px-2.5 py-1 text-xs bg-primary-600 text-white rounded hover:bg-primary-700 transition-colors flex-shrink-0"
                      >
                        <Plus className="w-3.5 h-3.5" />
                        订阅
                      </button>
                    )}
                  </div>
                  {rec.description && (
                    <p className="text-sm text-gray-500 dark:text-gray-400 line-clamp-2 mt-1">
                      {rec.description}
                    </p>
                  )}
                  <div className="flex items-center gap-3 mt-2 text-xs text-gray-400 dark:text-gray-500">
                    <span className="flex items-center gap-1">
                      <Users className="w-3 h-3" />
                      {rec.subscriber_count} 人订阅
                    </span>
                    {rec.categories && (
                      <span className="truncate">
                        {rec.categories.split(',').map(c => c.trim()).join(' · ')}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 订阅弹窗 */}
      {subscribeModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-md w-full">
            <h3 className="text-lg font-medium dark:text-white mb-4">
              订阅 "{subscribeModal.title}"
            </h3>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                选择分类
              </label>
              <select
                value={selectedCategory || ''}
                onChange={(e) => setSelectedCategory(e.target.value ? parseInt(e.target.value) : null)}
                className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white"
              >
                <option value="">未分类</option>
                {categories.map(cat => (
                  <option key={cat.id} value={cat.id}>{cat.name}</option>
                ))}
              </select>
            </div>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setSubscribeModal(null)}
                className="px-4 py-2 border dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-700 dark:text-gray-200"
              >
                取消
              </button>
              <button
                onClick={() => subscribeMutation.mutate({ id: subscribeModal.id, categoryId: selectedCategory })}
                disabled={subscribeMutation.isPending}
                className="px-4 py-2 bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50 flex items-center gap-2"
              >
                {subscribeMutation.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
                确认订阅
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
