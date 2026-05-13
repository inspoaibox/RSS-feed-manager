import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { X, Bell, Info, Wrench, ChevronLeft, ChevronRight } from 'lucide-react'
import api from '@/services/api'
import type { NotificationListResponse, MarkReadResponse } from '@/types/notification'
import clsx from 'clsx'

interface NotificationModalProps {
  isOpen: boolean
  onClose: () => void
}

const typeConfig = {
  system: { icon: Info, color: 'text-blue-500', bg: 'bg-blue-50 dark:bg-blue-900/30', label: '系统公告' },
  update: { icon: Bell, color: 'text-green-500', bg: 'bg-green-50 dark:bg-green-900/30', label: '更新通知' },
  maintenance: { icon: Wrench, color: 'text-orange-500', bg: 'bg-orange-50 dark:bg-orange-900/30', label: '维护通知' },
}

export default function NotificationModal({ isOpen, onClose }: NotificationModalProps) {
  const queryClient = useQueryClient()
  const [currentIndex, setCurrentIndex] = useState(0)

  const { data, isLoading } = useQuery({
    queryKey: ['unread-notifications'],
    queryFn: async () => {
      const response = await api.get<NotificationListResponse>('/notifications/unread')
      return response.data
    },
    enabled: isOpen,
  })

  const markReadMutation = useMutation({
    mutationFn: async (notificationId: number) => {
      const response = await api.post<MarkReadResponse>(`/notifications/${notificationId}/read`)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['unread-notifications'] })
      queryClient.invalidateQueries({ queryKey: ['unread-count'] })
    },
  })

  const markAllReadMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post<MarkReadResponse>('/notifications/read-all')
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['unread-notifications'] })
      queryClient.invalidateQueries({ queryKey: ['unread-count'] })
      onClose()
    },
  })

  const notifications = data?.notifications || []
  const currentNotification = notifications[currentIndex]

  // Reset index when notifications change
  useEffect(() => {
    if (currentIndex >= notifications.length && notifications.length > 0) {
      setCurrentIndex(notifications.length - 1)
    }
  }, [notifications.length, currentIndex])

  const handleMarkRead = () => {
    if (currentNotification) {
      markReadMutation.mutate(currentNotification.id)
      if (notifications.length === 1) {
        onClose()
      } else if (currentIndex >= notifications.length - 1) {
        setCurrentIndex(Math.max(0, currentIndex - 1))
      }
    }
  }

  const handlePrev = () => {
    setCurrentIndex((prev) => Math.max(0, prev - 1))
  }

  const handleNext = () => {
    setCurrentIndex((prev) => Math.min(notifications.length - 1, prev + 1))
  }

  if (!isOpen) return null

  const config = currentNotification ? typeConfig[currentNotification.type] : typeConfig.system
  const Icon = config.icon

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className="relative bg-white dark:bg-gray-800 rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center">
            <div className="animate-spin w-8 h-8 border-4 border-primary-500 border-t-transparent rounded-full mx-auto"></div>
            <p className="mt-4 text-gray-500 dark:text-gray-400">加载中...</p>
          </div>
        ) : notifications.length === 0 ? (
          <div className="p-8 text-center">
            <Bell className="w-12 h-12 text-gray-300 dark:text-gray-600 mx-auto" />
            <p className="mt-4 text-gray-500 dark:text-gray-400">暂无新通知</p>
            <button
              onClick={onClose}
              className="mt-4 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
            >
              关闭
            </button>
          </div>
        ) : currentNotification ? (
          <>
            {/* Header */}
            <div className={clsx('px-6 py-4 flex items-center justify-between', config.bg)}>
              <div className="flex items-center gap-3">
                <Icon className={clsx('w-6 h-6', config.color)} />
                <span className={clsx('text-sm font-medium', config.color)}>{config.label}</span>
              </div>
              <button
                onClick={onClose}
                className="p-1 hover:bg-black/10 dark:hover:bg-white/10 rounded-lg transition-colors"
              >
                <X className="w-5 h-5 text-gray-500 dark:text-gray-400" />
              </button>
            </div>

            {/* Content */}
            <div className="p-6">
              <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-3">
                {currentNotification.title}
              </h2>
              <div 
                className="text-gray-600 dark:text-gray-300 prose dark:prose-invert max-w-none"
                dangerouslySetInnerHTML={{ __html: currentNotification.content.replace(/\n/g, '<br/>') }}
              />
              <p className="mt-4 text-xs text-gray-400 dark:text-gray-500">
                {new Date(currentNotification.created_at).toLocaleString('zh-CN')}
                {currentNotification.creator_name && ` · ${currentNotification.creator_name}`}
              </p>
            </div>

            {/* Footer */}
            <div className="px-6 py-4 bg-gray-50 dark:bg-gray-900/50 flex items-center justify-between">
              {/* Pagination */}
              <div className="flex items-center gap-2">
                {notifications.length > 1 && (
                  <>
                    <button
                      onClick={handlePrev}
                      disabled={currentIndex === 0}
                      className="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      <ChevronLeft className="w-5 h-5" />
                    </button>
                    <span className="text-sm text-gray-500 dark:text-gray-400">
                      {currentIndex + 1} / {notifications.length}
                    </span>
                    <button
                      onClick={handleNext}
                      disabled={currentIndex === notifications.length - 1}
                      className="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      <ChevronRight className="w-5 h-5" />
                    </button>
                  </>
                )}
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2">
                {notifications.length > 1 && (
                  <button
                    onClick={() => markAllReadMutation.mutate()}
                    disabled={markAllReadMutation.isPending}
                    className="px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors"
                  >
                    全部已读
                  </button>
                )}
                <button
                  onClick={handleMarkRead}
                  disabled={markReadMutation.isPending}
                  className="px-4 py-1.5 text-sm bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors"
                >
                  {markReadMutation.isPending ? '处理中...' : '我知道了'}
                </button>
              </div>
            </div>
          </>
        ) : null}
      </div>
    </div>
  )
}
