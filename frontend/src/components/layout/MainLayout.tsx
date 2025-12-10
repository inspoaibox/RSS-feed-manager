import { useState, useEffect } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Menu, X, Rss, FolderOpen, Star, Settings, LogOut, ChevronDown, ChevronRight, User, BarChart3, Sparkles } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import { useSiteStore } from '@/stores/siteStore'
import api from '@/services/api'
import type { Category, Feed } from '@/types'
import clsx from 'clsx'

interface SidebarProps {
  isOpen: boolean
  onClose: () => void
}

function Sidebar({ isOpen, onClose }: SidebarProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const clearAuth = useAuthStore((state) => state.clearAuth)
  const user = useAuthStore((state) => state.user)
  const [expandedCategories, setExpandedCategories] = useState<Set<number>>(new Set())
  const { siteName, setSiteName } = useSiteStore()

  // 获取公开设置（网站名称）
  const { data: publicSettings } = useQuery({
    queryKey: ['public-settings'],
    queryFn: async () => {
      const response = await api.get<{ site_name: string }>('/system/public-settings')
      return response.data
    },
    staleTime: 60000,
  })

  useEffect(() => {
    if (publicSettings?.site_name) {
      setSiteName(publicSettings.site_name)
    }
  }, [publicSettings?.site_name, setSiteName])

  const { data: categories = [] } = useQuery({
    queryKey: ['categories'],
    queryFn: async () => {
      const response = await api.get<Category[]>('/categories')
      return response.data
    },
    refetchInterval: 30000,
  })

  const { data: feeds = [] } = useQuery({
    queryKey: ['feeds'],
    queryFn: async () => {
      const response = await api.get<Feed[]>('/feeds')
      return response.data
    },
    refetchInterval: 30000,
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
  const totalUnread = feeds.reduce((sum, f) => sum + (f.unread_count || 0), 0)

  // 检查当前路由是否匹配
  const isActive = (path: string) => {
    if (path === '/') return location.pathname === '/' && !location.search
    return location.pathname + location.search === path
  }

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 backdrop-blur-sm z-20 lg:hidden"
          onClick={onClose}
        />
      )}
      
      {/* Sidebar */}
      <aside
        className={clsx(
          'fixed lg:static inset-y-0 left-0 z-30 w-72 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 transform transition-transform duration-300 ease-in-out flex flex-col',
          isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        )}
      >
        {/* Header with gradient */}
        <div className="bg-gradient-to-r from-primary-600 to-primary-700 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-white/20 rounded-xl flex items-center justify-center">
                <Rss className="w-5 h-5 text-white" />
              </div>
              <div>
                <h1 className="text-lg font-bold text-white">{siteName}</h1>
                <p className="text-xs text-primary-100">订阅管理器</p>
              </div>
            </div>
            <button onClick={onClose} className="lg:hidden text-white/80 hover:text-white">
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto p-3 space-y-1">
          {/* All Articles */}
          <button
            onClick={() => navigate('/')}
            className={clsx(
              'w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200',
              isActive('/') 
                ? 'bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 font-medium' 
                : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700/50'
            )}
          >
            <Rss className="w-5 h-5" />
            <span className="flex-1 text-left">全部文章</span>
            {totalUnread > 0 && (
              <span className="px-2 py-0.5 text-xs font-medium bg-primary-100 dark:bg-primary-900 text-primary-700 dark:text-primary-300 rounded-full">
                {totalUnread}
              </span>
            )}
          </button>

          {/* Favorites */}
          <button
            onClick={() => navigate('/?favorite=true')}
            className={clsx(
              'w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200',
              isActive('/?favorite=true')
                ? 'bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 font-medium'
                : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700/50'
            )}
          >
            <Star className="w-5 h-5" />
            <span>收藏</span>
          </button>

          {/* AI Analysis */}
          <button
            onClick={() => navigate('/ai-analysis')}
            className={clsx(
              'w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200',
              location.pathname === '/ai-analysis'
                ? 'bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 font-medium'
                : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700/50'
            )}
          >
            <Sparkles className="w-5 h-5" />
            <span>AI 分析</span>
          </button>

          {/* Categories */}
          {categories.length > 0 && (
            <div className="pt-4">
              <div className="px-3 py-2 text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider">
                分类
              </div>
              <div className="space-y-0.5">
                {categories.map((category) => {
                  const categoryFeeds = feeds.filter((f) => f.category_id === category.id)
                  const isExpanded = expandedCategories.has(category.id)
                  const categoryActive = location.search === `?category=${category.id}`
                  return (
                    <div key={category.id}>
                      <div className={clsx(
                        'flex items-center gap-1 px-3 py-2 rounded-xl transition-all duration-200',
                        categoryActive
                          ? 'bg-primary-50 dark:bg-primary-900/30'
                          : 'hover:bg-gray-100 dark:hover:bg-gray-700/50'
                      )}>
                        <button
                          onClick={() => toggleCategory(category.id)}
                          className="p-1 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-lg transition-colors"
                        >
                          {isExpanded ? (
                            <ChevronDown className="w-4 h-4 text-gray-500" />
                          ) : (
                            <ChevronRight className="w-4 h-4 text-gray-500" />
                          )}
                        </button>
                        <button
                          onClick={() => {
                            setExpandedCategories((prev) => new Set(prev).add(category.id))
                            navigate(`/?category=${category.id}`)
                          }}
                          className={clsx(
                            'flex-1 flex items-center gap-2 text-left',
                            categoryActive ? 'text-primary-700 dark:text-primary-300 font-medium' : 'text-gray-700 dark:text-gray-300'
                          )}
                        >
                          <FolderOpen className="w-4 h-4" />
                          <span className="flex-1 truncate">{category.name}</span>
                          {category.unread_count > 0 && (
                            <span className="px-2 py-0.5 text-xs font-medium bg-primary-100 dark:bg-primary-900 text-primary-700 dark:text-primary-300 rounded-full">
                              {category.unread_count}
                            </span>
                          )}
                        </button>
                      </div>
                      {isExpanded && categoryFeeds.length > 0 && (
                        <div className="ml-4 pl-4 border-l-2 border-gray-100 dark:border-gray-700 space-y-0.5 mt-1">
                          {categoryFeeds.map((feed) => {
                            const feedActive = location.search === `?feed=${feed.id}`
                            return (
                              <button
                                key={feed.id}
                                onClick={() => navigate(`/?feed=${feed.id}`)}
                                className={clsx(
                                  'w-full flex items-center gap-2 px-3 py-2 text-sm rounded-lg transition-all duration-200',
                                  feedActive
                                    ? 'bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 font-medium'
                                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700/50 hover:text-gray-900 dark:hover:text-gray-200'
                                )}
                              >
                                <span className="flex-1 text-left truncate">{feed.title}</span>
                                {feed.unread_count > 0 && (
                                  <span className="text-xs text-gray-500 dark:text-gray-400">{feed.unread_count}</span>
                                )}
                              </button>
                            )
                          })}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Uncategorized Feeds */}
          {uncategorizedFeeds.length > 0 && (
            <div className="pt-4">
              <div className="px-3 py-2 text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider">
                未分类
              </div>
              <div className="space-y-0.5">
                {uncategorizedFeeds.map((feed) => {
                  const feedActive = location.search === `?feed=${feed.id}`
                  return (
                    <button
                      key={feed.id}
                      onClick={() => navigate(`/?feed=${feed.id}`)}
                      className={clsx(
                        'w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200',
                        feedActive
                          ? 'bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 font-medium'
                          : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700/50'
                      )}
                    >
                      <Rss className="w-4 h-4" />
                      <span className="flex-1 text-left truncate">{feed.title}</span>
                      {feed.unread_count > 0 && (
                        <span className="px-2 py-0.5 text-xs font-medium bg-primary-100 dark:bg-primary-900 text-primary-700 dark:text-primary-300 rounded-full">
                          {feed.unread_count}
                        </span>
                      )}
                    </button>
                  )
                })}
              </div>
            </div>
          )}
        </nav>

        {/* Footer with user info */}
        <div className="border-t border-gray-200 dark:border-gray-700 p-3 space-y-1">
          {/* User info */}
          {user && (
            <div className="flex items-center gap-3 px-3 py-2 mb-2">
              <div className="w-8 h-8 bg-primary-100 dark:bg-primary-900/50 rounded-full flex items-center justify-center">
                <User className="w-4 h-4 text-primary-600 dark:text-primary-400" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 dark:text-white truncate">{user.username}</p>
                <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{user.email}</p>
              </div>
            </div>
          )}
          
          <button
            onClick={() => navigate('/stats')}
            className={clsx(
              'w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200',
              location.pathname === '/stats'
                ? 'bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 font-medium'
                : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700/50'
            )}
          >
            <BarChart3 className="w-5 h-5" />
            <span>统计</span>
          </button>
          <button
            onClick={() => navigate('/settings')}
            className={clsx(
              'w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200',
              location.pathname === '/settings'
                ? 'bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 font-medium'
                : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700/50'
            )}
          >
            <Settings className="w-5 h-5" />
            <span>设置</span>
          </button>
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-3 py-2.5 text-gray-700 dark:text-gray-300 hover:bg-red-50 dark:hover:bg-red-900/20 hover:text-red-600 dark:hover:text-red-400 rounded-xl transition-all duration-200"
          >
            <LogOut className="w-5 h-5" />
            <span>退出登录</span>
          </button>
        </div>
      </aside>
    </>
  )
}

export default function MainLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const siteName = useSiteStore((state) => state.siteName)

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-900">
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Mobile header */}
        <header className="lg:hidden flex items-center gap-4 p-4 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 shadow-sm">
          <button 
            onClick={() => setSidebarOpen(true)} 
            className="p-2 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
              <Rss className="w-4 h-4 text-white" />
            </div>
            <h1 className="text-lg font-semibold text-gray-900 dark:text-white">{siteName}</h1>
          </div>
        </header>
        
        <div className="flex-1 overflow-auto">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
