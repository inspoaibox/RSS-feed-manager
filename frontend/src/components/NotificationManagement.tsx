import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Edit2, Trash2, Bell, Info, Wrench, Check, X } from 'lucide-react'
import api from '@/services/api'
import type { Notification, NotificationListResponse, NotificationCreate, NotificationUpdate } from '@/types/notification'
import clsx from 'clsx'

const typeConfig = {
  system: { icon: Info, color: 'text-blue-500', bg: 'bg-blue-50 dark:bg-blue-900/30', label: '系统公告' },
  update: { icon: Bell, color: 'text-green-500', bg: 'bg-green-50 dark:bg-green-900/30', label: '更新通知' },
  maintenance: { icon: Wrench, color: 'text-orange-500', bg: 'bg-orange-50 dark:bg-orange-900/30', label: '维护通知' },
}

export default function NotificationManagement() {
  const queryClient = useQueryClient()
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [showAddForm, setShowAddForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  
  // Form state
  const [formData, setFormData] = useState<NotificationCreate>({
    title: '',
    content: '',
    type: 'system',
    expires_at: null,
  })

  const { data, isLoading } = useQuery({
    queryKey: ['admin-notifications'],
    queryFn: async () => {
      const response = await api.get<NotificationListResponse>('/notifications')
      return response.data
    },
  })

  const createMutation = useMutation({
    mutationFn: async (data: NotificationCreate) => {
      const response = await api.post('/notifications', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-notifications'] })
      queryClient.invalidateQueries({ queryKey: ['unread-notifications'] })
      queryClient.invalidateQueries({ queryKey: ['unread-count'] })
      setShowAddForm(false)
      resetForm()
      setMessage({ type: 'success', text: '通知已发布' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      setMessage({ type: 'error', text: detail || '发布失败' })
    },
  })

  const updateMutation = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: NotificationUpdate }) => {
      const response = await api.put(`/notifications/${id}`, data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-notifications'] })
      queryClient.invalidateQueries({ queryKey: ['unread-notifications'] })
      queryClient.invalidateQueries({ queryKey: ['unread-count'] })
      setEditingId(null)
      resetForm()
      setMessage({ type: 'success', text: '通知已更新' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      setMessage({ type: 'error', text: detail || '更新失败' })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/notifications/${id}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-notifications'] })
      queryClient.invalidateQueries({ queryKey: ['unread-notifications'] })
      queryClient.invalidateQueries({ queryKey: ['unread-count'] })
      setMessage({ type: 'success', text: '通知已删除' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      setMessage({ type: 'error', text: detail || '删除失败' })
    },
  })

  const resetForm = () => {
    setFormData({
      title: '',
      content: '',
      type: 'system',
      expires_at: null,
    })
  }

  const startEdit = (notification: Notification) => {
    setEditingId(notification.id)
    setFormData({
      title: notification.title,
      content: notification.content,
      type: notification.type,
      expires_at: notification.expires_at,
    })
  }

  const handleSubmit = () => {
    if (editingId) {
      updateMutation.mutate({ id: editingId, data: formData })
    } else {
      createMutation.mutate(formData)
    }
  }

  const notifications = data?.notifications || []

  return (
    <div className="space-y-4">
      {message && (
        <div className={`p-3 rounded ${message.type === 'success' ? 'bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-400' : 'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-400'}`}>
          {message.text}
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-medium dark:text-white flex items-center gap-2">
            <Bell className="w-5 h-5" />
            通知管理
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            发布系统通知，用户登录后会弹窗提示
          </p>
        </div>
        {!showAddForm && !editingId && (
          <button
            onClick={() => setShowAddForm(true)}
            className="flex items-center gap-1 px-3 py-2 bg-primary-600 text-white rounded hover:bg-primary-700"
          >
            <Plus className="w-4 h-4" /> 发布通知
          </button>
        )}
      </div>

      {/* Add/Edit Form */}
      {(showAddForm || editingId) && (
        <div className="p-4 border dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-700 space-y-4">
          <h4 className="font-medium dark:text-white">
            {editingId ? '编辑通知' : '发布新通知'}
          </h4>
          
          <div>
            <label className="block text-sm font-medium dark:text-gray-300 mb-1">标题</label>
            <input
              type="text"
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              placeholder="通知标题"
              className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
            />
          </div>

          <div>
            <label className="block text-sm font-medium dark:text-gray-300 mb-1">内容</label>
            <textarea
              value={formData.content}
              onChange={(e) => setFormData({ ...formData, content: e.target.value })}
              placeholder="通知内容（支持换行）"
              rows={4}
              className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white resize-none"
            />
          </div>

          <div className="flex gap-4 flex-wrap">
            <div>
              <label className="block text-sm font-medium dark:text-gray-300 mb-1">类型</label>
              <select
                value={formData.type}
                onChange={(e) => setFormData({ ...formData, type: e.target.value as 'system' | 'update' | 'maintenance' })}
                className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
              >
                <option value="system">系统公告</option>
                <option value="update">更新通知</option>
                <option value="maintenance">维护通知</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium dark:text-gray-300 mb-1">过期时间（可选）</label>
              <input
                type="datetime-local"
                value={formData.expires_at ? new Date(formData.expires_at).toISOString().slice(0, 16) : ''}
                onChange={(e) => setFormData({ ...formData, expires_at: e.target.value ? new Date(e.target.value).toISOString() : null })}
                className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
              />
            </div>
          </div>

          <div className="flex gap-2">
            <button
              onClick={handleSubmit}
              disabled={!formData.title || !formData.content || createMutation.isPending || updateMutation.isPending}
              className="px-4 py-2 bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50"
            >
              {createMutation.isPending || updateMutation.isPending ? '保存中...' : editingId ? '更新' : '发布'}
            </button>
            <button
              onClick={() => {
                setShowAddForm(false)
                setEditingId(null)
                resetForm()
              }}
              className="px-4 py-2 border dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-600 dark:text-gray-200"
            >
              取消
            </button>
          </div>
        </div>
      )}

      {/* Notification List */}
      {isLoading ? (
        <div className="text-center py-8 text-gray-500 dark:text-gray-400">加载中...</div>
      ) : notifications.length === 0 ? (
        <div className="text-center py-8 text-gray-500 dark:text-gray-400">
          <Bell className="w-12 h-12 mx-auto mb-2 opacity-50" />
          <p>暂无通知</p>
        </div>
      ) : (
        <div className="border dark:border-gray-700 rounded-lg divide-y dark:divide-gray-700">
          {notifications.map((notification) => {
            const config = typeConfig[notification.type] || typeConfig.system
            const Icon = config.icon
            const isExpired = notification.expires_at && new Date(notification.expires_at) < new Date()
            
            return (
              <div key={notification.id} className={clsx('p-4', !notification.is_active && 'opacity-60')}>
                <div className="flex items-start gap-3">
                  <div className={clsx('p-2 rounded-lg', config.bg)}>
                    <Icon className={clsx('w-5 h-5', config.color)} />
                  </div>
                  
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h4 className="font-medium dark:text-white">{notification.title}</h4>
                      <span className={clsx('px-2 py-0.5 text-xs rounded', config.bg, config.color)}>
                        {config.label}
                      </span>
                      {!notification.is_active && (
                        <span className="px-2 py-0.5 text-xs rounded bg-gray-100 dark:bg-gray-700 text-gray-500">
                          已禁用
                        </span>
                      )}
                      {isExpired && (
                        <span className="px-2 py-0.5 text-xs rounded bg-red-100 dark:bg-red-900/30 text-red-500">
                          已过期
                        </span>
                      )}
                    </div>
                    
                    <p className="text-sm text-gray-600 dark:text-gray-300 mt-1 whitespace-pre-wrap">
                      {notification.content}
                    </p>
                    
                    <div className="flex items-center gap-4 mt-2 text-xs text-gray-400 dark:text-gray-500">
                      <span>
                        {new Date(notification.created_at).toLocaleString('zh-CN')}
                      </span>
                      {notification.creator_name && (
                        <span>发布者: {notification.creator_name}</span>
                      )}
                      {notification.expires_at && (
                        <span>
                          过期: {new Date(notification.expires_at).toLocaleString('zh-CN')}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-1">
                    {/* Toggle active */}
                    <button
                      onClick={() => updateMutation.mutate({ 
                        id: notification.id, 
                        data: { is_active: !notification.is_active } 
                      })}
                      disabled={updateMutation.isPending}
                      className={clsx(
                        'p-2 rounded hover:bg-gray-100 dark:hover:bg-gray-700',
                        notification.is_active ? 'text-green-500' : 'text-gray-400'
                      )}
                      title={notification.is_active ? '禁用通知' : '启用通知'}
                    >
                      {notification.is_active ? <Check className="w-4 h-4" /> : <X className="w-4 h-4" />}
                    </button>
                    
                    {/* Edit */}
                    <button
                      onClick={() => startEdit(notification)}
                      className="p-2 text-gray-500 hover:text-primary-600 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
                      title="编辑"
                    >
                      <Edit2 className="w-4 h-4" />
                    </button>
                    
                    {/* Delete */}
                    <button
                      onClick={() => {
                        if (confirm('确定要删除这条通知吗？')) {
                          deleteMutation.mutate(notification.id)
                        }
                      }}
                      disabled={deleteMutation.isPending}
                      className="p-2 text-gray-500 hover:text-red-600 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
                      title="删除"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
