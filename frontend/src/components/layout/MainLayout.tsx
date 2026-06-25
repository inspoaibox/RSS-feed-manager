import { useState, useEffect, useMemo } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Menu, X, Rss, FolderOpen, Star, Settings, LogOut, ChevronDown, ChevronRight, User, BarChart3, Sparkles, Bell, Hash, Plus, Trash2, SlidersHorizontal } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import { useSiteStore } from '@/stores/siteStore'
import api from '@/services/api'
import type { Category, Feed, KeywordSubscription, KeywordSubscriptionCount } from '@/types'
import type { UnreadCountResponse } from '@/types/notification'
import NotificationModal from '@/components/NotificationModal'
import clsx from 'clsx'

interface PublicSettings {
  site_name: string
  show_favorites_menu: boolean
  show_ai_analysis_menu: boolean
  show_recommendations_menu: boolean
}

interface SidebarProps {
  isOpen: boolean
  onClose: () => void
  onOpenNotifications: () => void
  unreadCount: number
}

type KeywordCreatePayload = {
  keyword: string
  excluded_category_ids: number[]
  excluded_feed_ids: number[]
}

function Sidebar({ isOpen, onClose, onOpenNotifications, unreadCount }: SidebarProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()
  const clearAuth = useAuthStore((state) => state.clearAuth)
  const user = useAuthStore((state) => state.user)
  const [expandedCategories, setExpandedCategories] = useState<Set<number>>(new Set())
  const [newKeyword, setNewKeyword] = useState('')
  const [keywordMessage, setKeywordMessage] = useState<{ type: 'error' | 'success'; text: string } | null>(null)
  const [keywordManagerOpen, setKeywordManagerOpen] = useState(false)
  const [keywordSourceFilterOpen, setKeywordSourceFilterOpen] = useState(false)
  const [keywordExcludedCategoryIds, setKeywordExcludedCategoryIds] = useState<number[]>([])
  const [keywordExcludedFeedIds, setKeywordExcludedFeedIds] = useState<number[]>([])
  const [selectedKeywordIds, setSelectedKeywordIds] = useState<Set<number>>(new Set())
  const { siteName, setSiteName } = useSiteStore()
  const activeKeywordId = new URLSearchParams(location.search).get('keyword_id')

  // 获取公开设置（网站名称和菜单显示）
  const { data: publicSettings } = useQuery({
    queryKey: ['public-settings'],
    queryFn: async () => {
      const response = await api.get<PublicSettings>('/system/public-settings')
      return response.data
    },
    staleTime: 60000,
  })

  const showFavoritesMenu = publicSettings?.show_favorites_menu ?? true
  const showAiAnalysisMenu = publicSettings?.show_ai_analysis_menu ?? true
  const showRecommendationsMenu = publicSettings?.show_recommendations_menu ?? true

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

  const { data: keywordSubscriptions = [] } = useQuery({
    queryKey: ['keywords'],
    queryFn: async () => {
      const response = await api.get<KeywordSubscription[]>('/keywords', {
        params: { include_counts: false },
      })
      return response.data
    },
    refetchInterval: 30000,
  })

  const { data: keywordCounts = [] } = useQuery({
    queryKey: ['keyword-counts'],
    queryFn: async () => {
      const response = await api.get<KeywordSubscriptionCount[]>('/keywords/counts')
      return response.data
    },
    enabled: keywordSubscriptions.length > 0,
    refetchInterval: 30000,
  })

  const keywordCountById = useMemo(() => {
    return new Map(keywordCounts.map((count) => [count.id, count]))
  }, [keywordCounts])

  const keywordsWithCounts = useMemo(() => {
    return keywordSubscriptions.map((keyword) => {
      const counts = keywordCountById.get(keyword.id)
      return counts ? { ...keyword, ...counts } : keyword
    })
  }, [keywordSubscriptions, keywordCountById])

  const keywordExcludedCategorySet = useMemo(
    () => new Set(keywordExcludedCategoryIds),
    [keywordExcludedCategoryIds]
  )
  const keywordExcludedFeedSet = useMemo(
    () => new Set(keywordExcludedFeedIds),
    [keywordExcludedFeedIds]
  )

  const resetKeywordSourceFilters = () => {
    setKeywordExcludedCategoryIds([])
    setKeywordExcludedFeedIds([])
  }

  const keywordSourceSummary = useMemo(() => {
    if (keywordExcludedCategoryIds.length === 0 && keywordExcludedFeedIds.length === 0) {
      return '默认全选订阅源'
    }

    const parts: string[] = []
    if (keywordExcludedCategoryIds.length > 0) {
      parts.push(`排除 ${keywordExcludedCategoryIds.length} 个分组`)
    }
    if (keywordExcludedFeedIds.length > 0) {
      parts.push(`排除 ${keywordExcludedFeedIds.length} 个订阅源`)
    }
    return parts.join('，')
  }, [keywordExcludedCategoryIds, keywordExcludedFeedIds])

  const createKeywordMutation = useMutation({
    mutationFn: async (payload: KeywordCreatePayload) => {
      const response = await api.post<KeywordSubscription>('/keywords', {
        keyword: payload.keyword,
        name: payload.keyword,
        match_title: true,
        match_content: true,
        match_author: false,
        match_feed_title: false,
        excluded_category_ids: payload.excluded_category_ids,
        excluded_feed_ids: payload.excluded_feed_ids,
      })
      return response.data
    },
    onSuccess: (keyword) => {
      queryClient.setQueryData<KeywordSubscription[]>(['keywords'], (current = []) => {
        if (current.some((item) => item.id === keyword.id)) {
          return current.map((item) => item.id === keyword.id ? keyword : item)
        }
        return [...current, keyword]
      })
      queryClient.invalidateQueries({ queryKey: ['keywords'] })
      queryClient.invalidateQueries({ queryKey: ['keyword-counts'] })
      setNewKeyword('')
      resetKeywordSourceFilters()
      setKeywordSourceFilterOpen(false)
      setKeywordMessage({ type: 'success', text: '关键词订阅已添加' })
      navigate(`/?keyword_id=${keyword.id}`)
      setTimeout(() => setKeywordMessage(null), 3000)
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      setKeywordMessage({ type: 'error', text: detail || '添加关键词失败' })
      setTimeout(() => setKeywordMessage(null), 3000)
    },
  })

  const deleteKeywordMutation = useMutation({
    mutationFn: async (keywordId: number) => {
      await api.delete(`/keywords/${keywordId}`)
      return keywordId
    },
    onSuccess: (keywordId) => {
      queryClient.setQueryData<KeywordSubscription[]>(['keywords'], (current = []) => {
        return current.filter((keyword) => keyword.id !== keywordId)
      })
      queryClient.setQueryData<KeywordSubscriptionCount[]>(['keyword-counts'], (current = []) => {
        return current.filter((count) => count.id !== keywordId)
      })
      queryClient.invalidateQueries({ queryKey: ['keywords'] })
      queryClient.invalidateQueries({ queryKey: ['keyword-counts'] })
      if (activeKeywordId === String(keywordId)) {
        navigate('/')
      }
      setSelectedKeywordIds((prev) => {
        const next = new Set(prev)
        next.delete(keywordId)
        return next
      })
    },
  })

  const deleteSelectedKeywordsMutation = useMutation({
    mutationFn: async (keywordIds: number[]) => {
      await Promise.all(keywordIds.map((keywordId) => api.delete(`/keywords/${keywordId}`)))
      return keywordIds
    },
    onSuccess: (keywordIds) => {
      queryClient.setQueryData<KeywordSubscription[]>(['keywords'], (current = []) => {
        return current.filter((keyword) => !keywordIds.includes(keyword.id))
      })
      queryClient.setQueryData<KeywordSubscriptionCount[]>(['keyword-counts'], (current = []) => {
        return current.filter((count) => !keywordIds.includes(count.id))
      })
      queryClient.invalidateQueries({ queryKey: ['keywords'] })
      queryClient.invalidateQueries({ queryKey: ['keyword-counts'] })
      if (activeKeywordId && keywordIds.includes(Number(activeKeywordId))) {
        navigate('/')
      }
      setSelectedKeywordIds(new Set())
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      setKeywordMessage({ type: 'error', text: detail || '批量删除关键词失败' })
      setTimeout(() => setKeywordMessage(null), 3000)
    },
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

  const handleCreateKeyword = (e: React.FormEvent) => {
    e.preventDefault()
    const keyword = newKeyword.trim()
    if (!keyword) return
    createKeywordMutation.mutate({
      keyword,
      excluded_category_ids: keywordExcludedCategoryIds,
      excluded_feed_ids: keywordExcludedFeedIds,
    })
  }

  const toggleKeywordCategory = (categoryId: number) => {
    setKeywordExcludedCategoryIds((current) => (
      current.includes(categoryId)
        ? current.filter((item) => item !== categoryId)
        : [...current, categoryId]
    ))
  }

  const toggleKeywordFeed = (feedId: number) => {
    setKeywordExcludedFeedIds((current) => (
      current.includes(feedId)
        ? current.filter((item) => item !== feedId)
        : [...current, feedId]
    ))
  }

  const isKeywordFeedIncluded = (feed: Feed) => (
    !keywordExcludedFeedSet.has(feed.id)
    && !(feed.category_id && keywordExcludedCategorySet.has(feed.category_id))
  )

  const toggleSelectedKeyword = (keywordId: number) => {
    setSelectedKeywordIds((prev) => {
      const next = new Set(prev)
      if (next.has(keywordId)) {
        next.delete(keywordId)
      } else {
        next.add(keywordId)
      }
      return next
    })
  }

  const allKeywordsSelected = keywordsWithCounts.length > 0 && selectedKeywordIds.size === keywordsWithCounts.length

  const toggleAllKeywords = () => {
    setSelectedKeywordIds(
      allKeywordsSelected
        ? new Set()
        : new Set(keywordsWithCounts.map((keyword) => keyword.id))
    )
  }

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

          {(showFavoritesMenu || showAiAnalysisMenu || showRecommendationsMenu) && (
            <div className="grid grid-cols-2 gap-2">
              {showFavoritesMenu && (
                <button
                  onClick={() => navigate('/?favorite=true')}
                  className={clsx(
                    'min-w-0 flex items-center justify-center gap-2 px-2 py-2.5 rounded-xl text-sm transition-all duration-200',
                    isActive('/?favorite=true')
                      ? 'bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 font-medium'
                      : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700/50'
                  )}
                >
                  <Star className="w-4 h-4 flex-shrink-0" />
                  <span className="truncate">收藏</span>
                </button>
              )}

              {showAiAnalysisMenu && (
                <button
                  onClick={() => navigate('/ai-analysis')}
                  className={clsx(
                    'min-w-0 flex items-center justify-center gap-2 px-2 py-2.5 rounded-xl text-sm transition-all duration-200',
                    location.pathname === '/ai-analysis'
                      ? 'bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 font-medium'
                      : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700/50'
                  )}
                >
                  <Sparkles className="w-4 h-4 flex-shrink-0" />
                  <span className="truncate">AI 分析</span>
                </button>
              )}

              {showRecommendationsMenu && (
                <button
                  onClick={() => navigate('/recommendations')}
                  className={clsx(
                    'min-w-0 flex items-center justify-center gap-2 px-2 py-2.5 rounded-xl text-sm transition-all duration-200',
                    location.pathname === '/recommendations'
                      ? 'bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 font-medium'
                      : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700/50'
                  )}
                >
                  <Star className="w-4 h-4 flex-shrink-0" />
                  <span className="truncate">订阅推荐</span>
                </button>
              )}
            </div>
          )}

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

          {/* Keyword Subscriptions */}
          <div className="pt-4">
            <div className="px-3 py-2 flex items-center justify-between gap-2">
              <div className="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider">
                关键词订阅
              </div>
              {keywordsWithCounts.length > 0 && (
                <button
                  onClick={() => setKeywordManagerOpen(true)}
                  className="text-xs text-primary-600 dark:text-primary-400 hover:text-primary-700 dark:hover:text-primary-300"
                >
                  管理
                </button>
              )}
            </div>
            <form onSubmit={handleCreateKeyword} className="px-3 mb-2 space-y-2">
              <div className="flex items-center gap-2">
                <div className="relative flex-1 min-w-0">
                  <Hash className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400" />
                  <input
                    type="text"
                    value={newKeyword}
                    onChange={(e) => setNewKeyword(e.target.value)}
                    placeholder="关键词"
                    maxLength={200}
                    className="w-full pl-7 pr-2 py-1.5 text-sm border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-200 placeholder:text-gray-400 focus:outline-none focus:ring-1 focus:ring-primary-500"
                  />
                </div>
                <button
                  type="button"
                  onClick={() => setKeywordSourceFilterOpen((current) => !current)}
                  className={clsx(
                    'p-2 rounded-lg border transition-colors',
                    keywordSourceFilterOpen || keywordExcludedCategoryIds.length > 0 || keywordExcludedFeedIds.length > 0
                      ? 'border-primary-300 bg-primary-50 text-primary-700 dark:border-primary-700 dark:bg-primary-900/30 dark:text-primary-300'
                      : 'border-gray-200 text-gray-500 hover:bg-gray-100 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700'
                  )}
                  title={keywordSourceSummary}
                >
                  <SlidersHorizontal className="w-4 h-4" />
                </button>
                <button
                  type="submit"
                  disabled={!newKeyword.trim() || createKeywordMutation.isPending}
                  className="p-2 rounded-lg bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  title="添加关键词订阅"
                >
                  <Plus className="w-4 h-4" />
                </button>
              </div>

              <div className="text-[11px] text-gray-500 dark:text-gray-400">
                {keywordSourceSummary}
              </div>

              {keywordSourceFilterOpen && (
                <div className="rounded-lg border border-gray-200 bg-gray-50 px-2 py-2 dark:border-gray-700 dark:bg-gray-800/60">
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <div className="text-xs font-medium text-gray-700 dark:text-gray-200">来源筛选</div>
                    <button
                      type="button"
                      onClick={resetKeywordSourceFilters}
                      className="text-[11px] text-primary-600 hover:text-primary-700 dark:text-primary-400 dark:hover:text-primary-300"
                    >
                      恢复全选
                    </button>
                  </div>

                  <div className="max-h-56 space-y-2 overflow-y-auto pr-1">
                    {categories.map((category) => {
                      const categoryFeeds = feeds.filter((feed) => feed.category_id === category.id)
                      const categoryIncluded = !keywordExcludedCategorySet.has(category.id)

                      return (
                        <div key={category.id} className="rounded-md border border-gray-200 bg-white px-2 py-2 dark:border-gray-700 dark:bg-gray-800">
                          <label className="flex items-center gap-2 text-xs font-medium text-gray-700 dark:text-gray-200">
                            <input
                              type="checkbox"
                              checked={categoryIncluded}
                              onChange={() => toggleKeywordCategory(category.id)}
                              className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                            />
                            <span className="flex-1 truncate">{category.name}</span>
                            <span className="text-[11px] text-gray-400 dark:text-gray-500">{categoryFeeds.length}</span>
                          </label>

                          {categoryFeeds.length > 0 && (
                            <div className="mt-2 space-y-1 border-l border-gray-200 pl-4 dark:border-gray-700">
                              {categoryFeeds.map((feed) => (
                                <label
                                  key={feed.id}
                                  className={clsx(
                                    'flex items-center gap-2 text-xs',
                                    categoryIncluded
                                      ? 'text-gray-600 dark:text-gray-300'
                                      : 'text-gray-400 dark:text-gray-500'
                                  )}
                                >
                                  <input
                                    type="checkbox"
                                    checked={isKeywordFeedIncluded(feed)}
                                    disabled={!categoryIncluded}
                                    onChange={() => toggleKeywordFeed(feed.id)}
                                    className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                                  />
                                  <span className="truncate">{feed.title}</span>
                                </label>
                              ))}
                            </div>
                          )}
                        </div>
                      )
                    })}

                    {uncategorizedFeeds.length > 0 && (
                      <div className="rounded-md border border-gray-200 bg-white px-2 py-2 dark:border-gray-700 dark:bg-gray-800">
                        <div className="mb-2 text-xs font-medium text-gray-700 dark:text-gray-200">未分类订阅源</div>
                        <div className="space-y-1">
                          {uncategorizedFeeds.map((feed) => (
                            <label key={feed.id} className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-300">
                              <input
                                type="checkbox"
                                checked={!keywordExcludedFeedSet.has(feed.id)}
                                onChange={() => toggleKeywordFeed(feed.id)}
                                className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                              />
                              <span className="truncate">{feed.title}</span>
                            </label>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </form>
            {keywordMessage && (
              <div className={clsx(
                'mx-3 mb-2 px-2 py-1 text-xs rounded-lg',
                keywordMessage.type === 'success'
                  ? 'bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-300'
                  : 'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300'
              )}>
                {keywordMessage.text}
              </div>
            )}
            {keywordsWithCounts.length > 0 && (
              <div className="px-3 flex flex-wrap gap-2">
                {keywordsWithCounts.map((keyword) => {
                  const keywordActive = activeKeywordId === String(keyword.id)
                  const keywordCount = keyword.unread_count > 0 ? keyword.unread_count : keyword.article_count
                  return (
                    <div key={keyword.id} className={clsx('relative max-w-full', keywordActive ? 'z-10' : '')}>
                      <button
                        onClick={() => navigate(`/?keyword_id=${keyword.id}`)}
                        className={clsx(
                          'max-w-full min-w-0 flex items-center gap-0 px-2.5 py-1.5 rounded-full text-xs transition-all duration-200',
                          keywordActive
                            ? 'bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 font-medium ring-1 ring-primary-200 dark:ring-primary-800'
                            : 'bg-gray-50 dark:bg-gray-700/50 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                        )}
                        title={keyword.keyword}
                      >
                        <Hash className="w-3.5 h-3.5 flex-shrink-0" />
                        <span className="truncate max-w-28">{keyword.name || keyword.keyword}</span>
                      </button>
                      {keywordCount > 0 && (
                        <span className={clsx(
                          'absolute -top-1 -right-1 min-w-4 h-4 px-0.5 rounded-full text-[8px] leading-none font-semibold flex items-center justify-center pointer-events-none',
                          keyword.unread_count > 0
                            ? 'bg-orange-100 dark:bg-orange-900 text-orange-700 dark:text-orange-200'
                            : 'bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-300'
                        )}>
                          {keywordCount > 99 ? '99+' : keywordCount}
                        </span>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </div>
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
              {/* Notification bell */}
              <button
                onClick={onOpenNotifications}
                className="relative p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                title="通知"
              >
                <Bell className="w-5 h-5 text-gray-500 dark:text-gray-400" />
                {unreadCount > 0 && (
                  <span className="absolute -top-0.5 -right-0.5 w-5 h-5 bg-red-500 text-white text-xs font-medium rounded-full flex items-center justify-center">
                    {unreadCount > 9 ? '9+' : unreadCount}
                  </span>
                )}
              </button>
            </div>
          )}
          
          <div className="grid grid-cols-3 gap-2">
            <button
              onClick={() => navigate('/stats')}
              title="统计"
              aria-label="统计"
              className={clsx(
                'h-11 flex items-center justify-center rounded-xl transition-all duration-200',
                location.pathname === '/stats'
                  ? 'bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300'
                  : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700/50'
              )}
            >
              <BarChart3 className="w-5 h-5" />
            </button>
            <button
              onClick={() => navigate('/settings')}
              title="设置"
              aria-label="设置"
              className={clsx(
                'h-11 flex items-center justify-center rounded-xl transition-all duration-200',
                location.pathname === '/settings'
                  ? 'bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300'
                  : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700/50'
              )}
            >
              <Settings className="w-5 h-5" />
            </button>
            <button
              onClick={handleLogout}
              title="退出登录"
              aria-label="退出登录"
              className="h-11 flex items-center justify-center rounded-xl text-gray-700 dark:text-gray-300 hover:bg-red-50 dark:hover:bg-red-900/20 hover:text-red-600 dark:hover:text-red-400 transition-all duration-200"
            >
              <LogOut className="w-5 h-5" />
            </button>
          </div>
        </div>
      </aside>

      {keywordManagerOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md rounded-lg bg-white dark:bg-gray-800 shadow-xl">
            <div className="flex items-center justify-between border-b border-gray-200 dark:border-gray-700 px-4 py-3">
              <div>
                <h2 className="text-base font-semibold text-gray-900 dark:text-white">管理关键词订阅</h2>
                <p className="text-xs text-gray-500 dark:text-gray-400">删除操作不会删除文章，只删除关键词筛选入口</p>
              </div>
              <button
                onClick={() => setKeywordManagerOpen(false)}
                className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-700"
                title="关闭"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="max-h-[60vh] overflow-y-auto px-4 py-3">
              {keywordsWithCounts.length === 0 ? (
                <div className="py-8 text-center text-sm text-gray-500 dark:text-gray-400">暂无关键词订阅</div>
              ) : (
                <div className="space-y-2">
                  <label className="flex items-center gap-3 rounded-lg border border-gray-200 px-3 py-2 text-sm dark:border-gray-700 dark:text-gray-200">
                    <input
                      type="checkbox"
                      checked={allKeywordsSelected}
                      onChange={toggleAllKeywords}
                      className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                    />
                    <span className="flex-1">全选</span>
                    <span className="text-xs text-gray-500 dark:text-gray-400">{selectedKeywordIds.size} / {keywordsWithCounts.length}</span>
                  </label>

                  {keywordsWithCounts.map((keyword) => {
                    const keywordCount = keyword.unread_count > 0 ? keyword.unread_count : keyword.article_count
                    return (
                      <div
                        key={keyword.id}
                        className="flex items-center gap-3 rounded-lg border border-gray-200 px-3 py-2 dark:border-gray-700"
                      >
                        <input
                          type="checkbox"
                          checked={selectedKeywordIds.has(keyword.id)}
                          onChange={() => toggleSelectedKeyword(keyword.id)}
                          className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                        />
                        <button
                          onClick={() => {
                            navigate(`/?keyword_id=${keyword.id}`)
                            setKeywordManagerOpen(false)
                          }}
                          className="min-w-0 flex-1 text-left"
                          title={keyword.keyword}
                        >
                          <div className="flex items-center gap-2 text-sm font-medium text-gray-900 dark:text-white">
                            <Hash className="h-3.5 w-3.5 text-gray-400" />
                            <span className="truncate">{keyword.name || keyword.keyword}</span>
                          </div>
                          <div className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
                            {keywordCount} 篇文章，{keyword.unread_count} 未读
                          </div>
                        </button>
                        <button
                          onClick={() => deleteKeywordMutation.mutate(keyword.id)}
                          disabled={deleteKeywordMutation.isPending || deleteSelectedKeywordsMutation.isPending}
                          className="rounded-lg p-2 text-gray-400 hover:bg-red-50 hover:text-red-600 disabled:opacity-50 dark:hover:bg-red-900/20 dark:hover:text-red-400"
                          title="删除"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>

            <div className="flex items-center justify-between gap-3 border-t border-gray-200 dark:border-gray-700 px-4 py-3">
              <button
                onClick={() => setSelectedKeywordIds(new Set())}
                disabled={selectedKeywordIds.size === 0 || deleteSelectedKeywordsMutation.isPending}
                className="px-3 py-2 text-sm text-gray-600 hover:text-gray-900 disabled:opacity-50 dark:text-gray-300 dark:hover:text-white"
              >
                清空选择
              </button>
              <div className="flex gap-2">
                <button
                  onClick={() => setKeywordManagerOpen(false)}
                  className="rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-700"
                >
                  关闭
                </button>
                <button
                  onClick={() => deleteSelectedKeywordsMutation.mutate(Array.from(selectedKeywordIds))}
                  disabled={selectedKeywordIds.size === 0 || deleteSelectedKeywordsMutation.isPending}
                  className="rounded-lg bg-red-600 px-3 py-2 text-sm text-white hover:bg-red-700 disabled:opacity-50"
                >
                  批量删除
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

export default function MainLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [notificationModalOpen, setNotificationModalOpen] = useState(false)
  const [hasShownInitialNotification, setHasShownInitialNotification] = useState(false)
  const siteName = useSiteStore((state) => state.siteName)

  // Query unread notification count
  const { data: unreadData } = useQuery({
    queryKey: ['unread-count'],
    queryFn: async () => {
      const response = await api.get<UnreadCountResponse>('/notifications/unread/count')
      return response.data
    },
    refetchInterval: 60000, // Refresh every minute
  })

  const unreadCount = unreadData?.count || 0

  // Auto-show notification modal on first load if there are unread notifications
  useEffect(() => {
    if (unreadCount > 0 && !hasShownInitialNotification) {
      setNotificationModalOpen(true)
      setHasShownInitialNotification(true)
    }
  }, [unreadCount, hasShownInitialNotification])

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-900">
      <Sidebar 
        isOpen={sidebarOpen} 
        onClose={() => setSidebarOpen(false)}
        onOpenNotifications={() => setNotificationModalOpen(true)}
        unreadCount={unreadCount}
      />
      
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Mobile header */}
        <header className="lg:hidden flex items-center gap-4 p-4 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 shadow-sm">
          <button 
            onClick={() => setSidebarOpen(true)} 
            className="p-2 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-2 flex-1">
            <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
              <Rss className="w-4 h-4 text-white" />
            </div>
            <h1 className="text-lg font-semibold text-gray-900 dark:text-white">{siteName}</h1>
          </div>
          {/* Mobile notification bell */}
          <button
            onClick={() => setNotificationModalOpen(true)}
            className="relative p-2 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
          >
            <Bell className="w-5 h-5" />
            {unreadCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 w-5 h-5 bg-red-500 text-white text-xs font-medium rounded-full flex items-center justify-center">
                {unreadCount > 9 ? '9+' : unreadCount}
              </span>
            )}
          </button>
        </header>
        
        <div className="flex-1 overflow-auto">
          <Outlet />
        </div>
      </main>

      {/* Notification Modal */}
      <NotificationModal 
        isOpen={notificationModalOpen} 
        onClose={() => setNotificationModalOpen(false)} 
      />
    </div>
  )
}
