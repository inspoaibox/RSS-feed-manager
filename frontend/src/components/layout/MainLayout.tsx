import { useState } from 'react'
import { Outlet, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Menu, X, Rss, FolderOpen, Star, Settings, LogOut, ChevronDown, ChevronRight } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import api from '@/services/api'
import type { Category, Feed } from '@/types'
import clsx from 'clsx'

interface SidebarProps {
  isOpen: boolean
  onClose: () => void
}

function Sidebar({ isOpen, onClose }: SidebarProps) {
  const navigate = useNavigate()
  const clearAuth = useAuthStore((state) => state.clearAuth)
  const [expandedCategories, setExpandedCategories] = useState<Set<number>>(new Set())

  const { data: categories = [] } = useQuery({
    queryKey: ['categories'],
    queryFn: async () => {
      const response = await api.get<Category[]>('/categories')
      return response.data
    },
    refetchInterval: 30000, // 每30秒自动刷新
  })

  const { data: feeds = [] } = useQuery({
    queryKey: ['feeds'],
    queryFn: async () => {
      const response = await api.get<Feed[]>('/feeds')
      return response.data
    },
    refetchInterval: 30000, // 每30秒自动刷新
  })

  const toggleCategory = (categoryId: number) => {
    setExpandedCategories((prev) => {
      const next = new Set(prev)
      if (next.has(categoryId)) {
        next.delete(categoryId)
      } else {
        next.add(categoryId)
      }
      return next
    })
  }

  const handleLogout = async () => {
    try {
      await api.post('/auth/logout')
    } catch {
      // Ignore errors
    }
    clearAuth()
    navigate('/login')
  }

  const uncategorizedFeeds = feeds.filter((f) => !f.category_id)

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 z-20 lg:hidden"
          onClick={onClose}
        />
      )}
      
      {/* Sidebar */}
      <aside
        className={clsx(
          'fixed lg:static inset-y-0 left-0 z-30 w-64 bg-white border-r transform transition-transform duration-200 ease-in-out',
          isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        )}
      >
        <div className="flex flex-col h-full">
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b">
            <h1 className="text-xl font-bold text-gray-900">RSS 管理器</h1>
            <button onClick={onClose} className="lg:hidden">
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Navigation */}
          <nav className="flex-1 overflow-y-auto p-2">
            {/* All Articles */}
            <button
              onClick={() => navigate('/')}
              className="w-full flex items-center gap-2 px-3 py-2 text-gray-700 hover:bg-gray-100 rounded-md"
            >
              <Rss className="w-4 h-4" />
              <span>全部文章</span>
            </button>

            {/* Favorites */}
            <button
              onClick={() => navigate('/?favorite=true')}
              className="w-full flex items-center gap-2 px-3 py-2 text-gray-700 hover:bg-gray-100 rounded-md"
            >
              <Star className="w-4 h-4" />
              <span>收藏</span>
            </button>

            {/* Categories */}
            <div className="mt-4">
              <div className="px-3 py-2 text-xs font-semibold text-gray-500 uppercase">
                分类
              </div>
              {categories.map((category) => {
                const categoryFeeds = feeds.filter((f) => f.category_id === category.id)
                const isExpanded = expandedCategories.has(category.id)
                return (
                  <div key={category.id}>
                    <div className="flex items-center gap-1 px-3 py-2 text-gray-700 hover:bg-gray-100 rounded-md">
                      <button
                        onClick={() => toggleCategory(category.id)}
                        className="p-0.5 hover:bg-gray-200 rounded"
                      >
                        {isExpanded ? (
                          <ChevronDown className="w-4 h-4" />
                        ) : (
                          <ChevronRight className="w-4 h-4" />
                        )}
                      </button>
                      <button
                        onClick={() => navigate(`/?category=${category.id}`)}
                        className="flex-1 flex items-center gap-2 text-left"
                      >
                        <FolderOpen className="w-4 h-4" />
                        <span className="flex-1 truncate">{category.name}</span>
                        {category.unread_count > 0 && (
                          <span className="text-xs bg-blue-100 text-blue-600 px-2 py-0.5 rounded-full">
                            {category.unread_count}
                          </span>
                        )}
                      </button>
                    </div>
                    {isExpanded && categoryFeeds.length > 0 && (
                      <div className="ml-6">
                        {categoryFeeds.map((feed) => (
                          <button
                            key={feed.id}
                            onClick={() => navigate(`/?feed=${feed.id}`)}
                            className="w-full flex items-center gap-2 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-md"
                          >
                            <span className="flex-1 text-left truncate">{feed.title}</span>
                            {feed.unread_count > 0 && (
                              <span className="text-xs text-gray-500">{feed.unread_count}</span>
                            )}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>

            {/* Uncategorized Feeds */}
            {uncategorizedFeeds.length > 0 && (
              <div className="mt-4">
                <div className="px-3 py-2 text-xs font-semibold text-gray-500 uppercase">
                  未分类
                </div>
                {uncategorizedFeeds.map((feed) => (
                  <button
                    key={feed.id}
                    onClick={() => navigate(`/?feed=${feed.id}`)}
                    className="w-full flex items-center gap-2 px-3 py-2 text-gray-700 hover:bg-gray-100 rounded-md"
                  >
                    <Rss className="w-4 h-4" />
                    <span className="flex-1 text-left truncate">{feed.title}</span>
                    {feed.unread_count > 0 && (
                      <span className="text-xs bg-blue-100 text-blue-600 px-2 py-0.5 rounded-full">
                        {feed.unread_count}
                      </span>
                    )}
                  </button>
                ))}
              </div>
            )}
          </nav>

          {/* Footer */}
          <div className="border-t p-2">
            <button
              onClick={() => navigate('/settings')}
              className="w-full flex items-center gap-2 px-3 py-2 text-gray-700 hover:bg-gray-100 rounded-md"
            >
              <Settings className="w-4 h-4" />
              <span>设置</span>
            </button>
            <button
              onClick={handleLogout}
              className="w-full flex items-center gap-2 px-3 py-2 text-gray-700 hover:bg-gray-100 rounded-md"
            >
              <LogOut className="w-4 h-4" />
              <span>退出登录</span>
            </button>
          </div>
        </div>
      </aside>
    </>
  )
}

export default function MainLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="flex h-screen bg-gray-50">
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Mobile header */}
        <header className="lg:hidden flex items-center gap-4 p-4 bg-white border-b">
          <button onClick={() => setSidebarOpen(true)}>
            <Menu className="w-6 h-6" />
          </button>
          <h1 className="text-lg font-semibold">RSS 管理器</h1>
        </header>
        
        <div className="flex-1 overflow-auto">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
