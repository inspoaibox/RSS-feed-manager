import api from '@/services/api'
import type { Category } from '@/types'
import { getApiErrorMessage } from '@/utils/apiError'
import { useMutation,useQuery,useQueryClient } from '@tanstack/react-query'
import { Check,ChevronDown,ChevronUp,Edit2,Trash2,X } from 'lucide-react'
import { useState } from 'react'

export default function CategoriesTab() {
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
    onError: (err: unknown) => {
      const detail = getApiErrorMessage(err, '请求失败，请重试')
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
    onError: (err: unknown) => {
      const detail = getApiErrorMessage(err, '请求失败，请重试')
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
    onError: (err: unknown) => {
      const detail = getApiErrorMessage(err, '请求失败，请重试')
      setMessage({ type: 'error', text: detail || '删除失败' })
    },
  })

  const reorderMutation = useMutation({
    mutationFn: async (categoryIds: number[]) => {
      const response = await api.put('/categories/reorder', { category_ids: categoryIds })
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['categories'] })
    },
    onError: (err: unknown) => {
      const detail = getApiErrorMessage(err, '请求失败，请重试')
      setMessage({ type: 'error', text: detail || '排序失败' })
    },
  })

  const moveCategory = (categoryId: number, direction: 'up' | 'down') => {
    const currentIndex = categories.findIndex(c => c.id === categoryId)
    if (currentIndex === -1) return
    
    const newIndex = direction === 'up' ? currentIndex - 1 : currentIndex + 1
    if (newIndex < 0 || newIndex >= categories.length) return
    
    const newCategories = [...categories]
    const [removed] = newCategories.splice(currentIndex, 1)
    newCategories.splice(newIndex, 0, removed)
    
    reorderMutation.mutate(newCategories.map(c => c.id))
  }

  return (
    <div>
      {message && (
        <div className={`mb-4 p-3 rounded ${message.type === 'success' ? 'bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-400' : 'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-400'}`}>
          {message.text}
        </div>
      )}
      <div className="flex gap-2 mb-4">
        <input
          type="text"
          placeholder="新分类名称"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          className="flex-1 px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white"
        />
        <button
          onClick={() => createMutation.mutate()}
          disabled={!newName || createMutation.isPending}
          className="px-4 py-2 bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50"
        >
          添加
        </button>
      </div>

      <div className="border dark:border-gray-700 rounded divide-y dark:divide-gray-700">
        {categories.map((category) => (
          <div key={category.id} className="flex items-center gap-4 p-4">
            {editingId === category.id ? (
              <>
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="flex-1 px-3 py-1 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white"
                />
                <button
                  onClick={() => updateMutation.mutate({ id: category.id, name: editName })}
                  className="p-2 text-green-600 dark:text-green-400 hover:bg-green-50 dark:hover:bg-green-900/30 rounded"
                >
                  <Check className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setEditingId(null)}
                  className="p-2 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
                >
                  <X className="w-4 h-4" />
                </button>
              </>
            ) : (
              <>
                {/* Sort buttons */}
                <div className="flex flex-col gap-0.5">
                  <button
                    onClick={() => moveCategory(category.id, 'up')}
                    disabled={categories.indexOf(category) === 0 || reorderMutation.isPending}
                    className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded disabled:opacity-30 disabled:cursor-not-allowed"
                    title="上移"
                  >
                    <ChevronUp className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => moveCategory(category.id, 'down')}
                    disabled={categories.indexOf(category) === categories.length - 1 || reorderMutation.isPending}
                    className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded disabled:opacity-30 disabled:cursor-not-allowed"
                    title="下移"
                  >
                    <ChevronDown className="w-4 h-4" />
                  </button>
                </div>
                <span className="flex-1 dark:text-white">{category.name}</span>
                <span className="text-sm text-gray-500 dark:text-gray-400">{category.feed_count} 个订阅</span>
                <button
                  onClick={() => { setEditingId(category.id); setEditName(category.name) }}
                  className="p-2 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
                >
                  <Edit2 className="w-4 h-4" />
                </button>
                <button
                  onClick={() => deleteMutation.mutate(category.id)}
                  className="p-2 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 rounded"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </>
            )}
          </div>
        ))}
        {categories.length === 0 && (
          <div className="p-4 text-center text-gray-500 dark:text-gray-400">暂无分类</div>
        )}
      </div>
    </div>
  )
}
