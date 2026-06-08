import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { RefreshCw, Check, Star, ExternalLink, Search, SortAsc, SortDesc, X, Languages, FileText, Loader2, ChevronLeft, ChevronRight, Calendar } from 'lucide-react'
import api from '@/services/api'
import type { Article, PaginatedResponse } from '@/types'
import clsx from 'clsx'

// Helper to get date string in YYYY-MM-DD format for date input
const formatDateForInput = (date: Date): string => {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

// Get start of day in local timezone as ISO string
const getStartOfDay = (dateStr: string): string => {
  const date = new Date(dateStr + 'T00:00:00')
  return date.toISOString()
}

// Get end of day in local timezone as ISO string  
const getEndOfDay = (dateStr: string): string => {
  const date = new Date(dateStr + 'T23:59:59')
  return date.toISOString()
}

// Get today's date string
const getToday = () => formatDateForInput(new Date())

// Get yesterday's date string
const getYesterday = () => {
  const yesterday = new Date()
  yesterday.setDate(yesterday.getDate() - 1)
  return formatDateForInput(yesterday)
}

// Helper function to strip HTML tags and get plain text
const stripHtml = (html: string | null | undefined): string => {
  if (!html) return ''
  const doc = new DOMParser().parseFromString(html, 'text/html')
  return doc.body.textContent || ''
}

// Helper function to parse translation JSON (title and content)
const parseTranslation = (translation: string | null | undefined): { title: string; content: string } => {
  if (!translation) return { title: '', content: '' }
  
  try {
    const data = JSON.parse(translation)
    return {
      title: data.title || '',
      content: data.content || ''
    }
  } catch {
    // Fallback for old format (plain text)
    return { title: '', content: translation }
  }
}

const PAGE_SIZE = 30

export default function HomePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const queryClient = useQueryClient()
  const articleListRef = useRef<HTMLDivElement | null>(null)
  const [selectedArticle, setSelectedArticle] = useState<Article | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [isSearching, setIsSearching] = useState(false)
  const [sortBy, setSortBy] = useState<'published_at' | 'created_at' | 'title'>('published_at')
  const [sortOrder, setSortOrder] = useState<'desc' | 'asc'>('desc')
  const [showTranslation, setShowTranslation] = useState(true)
  const [currentPage, setCurrentPage] = useState(1)
  const [searchPage, setSearchPage] = useState(1)
  const [dateFilter, setDateFilter] = useState<'all' | 'today' | 'yesterday' | 'custom'>('all')
  const [customDateStart, setCustomDateStart] = useState('')
  const [customDateEnd, setCustomDateEnd] = useState('')
  const [showDatePicker, setShowDatePicker] = useState(false)

  const feedId = searchParams.get('feed')
  const categoryId = searchParams.get('category')
  const keywordId = searchParams.get('keyword_id')
  const isFavorite = searchParams.get('favorite') === 'true'

  useEffect(() => {
    if (keywordId) {
      setSearchQuery('')
      setIsSearching(false)
      setSearchPage(1)
      setCurrentPage(1)
      setSelectedArticle(null)
    }
  }, [keywordId])

  // Calculate date range based on filter - returns ISO timestamps
  const getDateRange = () => {
    let dateStr = ''
    let endDateStr = ''
    
    if (dateFilter === 'today') {
      dateStr = getToday()
      endDateStr = dateStr
    } else if (dateFilter === 'yesterday') {
      dateStr = getYesterday()
      endDateStr = dateStr
    } else if (dateFilter === 'custom' && customDateStart) {
      dateStr = customDateStart
      endDateStr = customDateEnd || customDateStart
    }
    
    if (!dateStr) return { start: '', end: '' }
    
    // Convert to ISO timestamps with timezone
    return {
      start: getStartOfDay(dateStr),
      end: getEndOfDay(endDateStr)
    }
  }

  const { data, isLoading } = useQuery({
    queryKey: ['articles', feedId, categoryId, keywordId, isFavorite, sortBy, sortOrder, currentPage, dateFilter, customDateStart, customDateEnd],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (feedId) params.append('feed_id', feedId)
      if (categoryId) params.append('category_id', categoryId)
      if (keywordId) params.append('keyword_id', keywordId)
      if (isFavorite) params.append('is_favorite', 'true')
      params.append('sort_by', sortBy)
      params.append('sort_order', sortOrder)
      params.append('page', currentPage.toString())
      params.append('page_size', PAGE_SIZE.toString())
      
      // Add date filter
      const dateRange = getDateRange()
      if (dateRange.start) params.append('date_from', dateRange.start)
      if (dateRange.end) params.append('date_to', dateRange.end)
      
      const response = await api.get<PaginatedResponse<Article>>(`/articles?${params}`)
      return response.data
    },
    enabled: !isSearching,
    refetchInterval: 30000,
  })

  const { data: searchData, isLoading: isSearchLoading } = useQuery({
    queryKey: ['articles-search', searchQuery, feedId, categoryId, searchPage],
    queryFn: async () => {
      const params = new URLSearchParams()
      params.append('q', searchQuery)
      if (feedId) params.append('feed_id', feedId)
      if (categoryId) params.append('category_id', categoryId)
      params.append('page', searchPage.toString())
      params.append('page_size', PAGE_SIZE.toString())
      
      const response = await api.get<PaginatedResponse<Article>>(`/articles/search?${params}`)
      return response.data
    },
    enabled: isSearching && searchQuery.length > 0,
  })


  const markReadMutation = useMutation({
    mutationFn: async (articleId: number) => {
      await api.put(`/articles/${articleId}/read`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['articles'] })
      queryClient.invalidateQueries({ queryKey: ['feeds'] })
      queryClient.invalidateQueries({ queryKey: ['categories'] })
      queryClient.invalidateQueries({ queryKey: ['keywords'] })
    },
  })

  const toggleFavoriteMutation = useMutation({
    mutationFn: async (articleId: number) => {
      const response = await api.put<{ is_favorite: boolean }>(`/articles/${articleId}/favorite`)
      return response.data
    },
    onSuccess: (data, articleId) => {
      queryClient.invalidateQueries({ queryKey: ['articles'] })
      queryClient.invalidateQueries({ queryKey: ['articles-search'] })
      if (selectedArticle?.id === articleId) {
        setSelectedArticle(prev => prev ? { ...prev, is_favorite: data.is_favorite } : null)
      }
    },
  })

  const translateMutation = useMutation({
    mutationFn: async (articleId: number) => {
      const response = await api.post<{ translation: string }>(`/articles/${articleId}/translate?target_language=zh-CN`)
      return response.data
    },
    onSuccess: (data) => {
      if (selectedArticle) {
        setSelectedArticle(prev => prev ? { ...prev, translation: data.translation } : null)
      }
      queryClient.invalidateQueries({ queryKey: ['articles'] })
    },
  })

  const summarizeMutation = useMutation({
    mutationFn: async (articleId: number) => {
      const response = await api.post<{ summary: string }>(`/articles/${articleId}/summarize`)
      return response.data
    },
    onSuccess: (data) => {
      if (selectedArticle) {
        setSelectedArticle(prev => prev ? { ...prev, summary: data.summary } : null)
      }
      queryClient.invalidateQueries({ queryKey: ['articles'] })
    },
  })

  const markAllReadMutation = useMutation({
    mutationFn: async () => {
      await api.post('/articles/mark-all-read', {
        feed_id: feedId ? parseInt(feedId) : null,
        category_id: categoryId ? parseInt(categoryId) : null,
        keyword_id: keywordId ? parseInt(keywordId) : null,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['articles'] })
      queryClient.invalidateQueries({ queryKey: ['feeds'] })
      queryClient.invalidateQueries({ queryKey: ['categories'] })
      queryClient.invalidateQueries({ queryKey: ['keywords'] })
    },
  })

  const refreshFeedMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.post(`/feeds/${id}/refresh`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['articles'] })
      queryClient.invalidateQueries({ queryKey: ['feeds'] })
      queryClient.invalidateQueries({ queryKey: ['keywords'] })
    },
  })

  const refreshAllMutation = useMutation({
    mutationFn: async (catId: number | null) => {
      const params = catId ? `?category_id=${catId}` : ''
      const response = await api.post<{ total: number; success: number; new_articles: number }>(`/feeds/refresh-all${params}`)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['articles'] })
      queryClient.invalidateQueries({ queryKey: ['feeds'] })
      queryClient.invalidateQueries({ queryKey: ['categories'] })
      queryClient.invalidateQueries({ queryKey: ['keywords'] })
    },
  })

  const handleSelectArticle = async (article: Article) => {
    setSelectedArticle(article)
    if (!article.is_read) {
      markReadMutation.mutate(article.id)
    }
  }

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (searchQuery.trim()) {
      if (keywordId) {
        const nextParams = new URLSearchParams(searchParams)
        nextParams.delete('keyword_id')
        setSearchParams(nextParams)
      }
      setIsSearching(true)
      setSearchPage(1)
    }
  }

  const clearSearch = () => {
    if (keywordId) {
      const nextParams = new URLSearchParams(searchParams)
      nextParams.delete('keyword_id')
      setSearchParams(nextParams)
    }
    setSearchQuery('')
    setIsSearching(false)
    setSearchPage(1)
  }

  const toggleSortOrder = () => {
    setSortOrder(prev => prev === 'desc' ? 'asc' : 'desc')
    setCurrentPage(1)
  }

  const currentData = isSearching ? searchData : data
  const articles = currentData?.items || []
  const loading = isSearching ? isSearchLoading : isLoading
  const totalPages = currentData?.total_pages || 1
  const page = isSearching ? searchPage : currentPage
  const setPage = isSearching ? setSearchPage : setCurrentPage

  const goToPage = (newPage: number) => {
    if (newPage >= 1 && newPage <= totalPages) {
      setPage(newPage)
      requestAnimationFrame(() => {
        articleListRef.current?.scrollTo({ top: 0 })
      })
    }
  }


  return (
    <div className="flex h-full">
      {/* Article List */}
      <div className={clsx(
        'border-r dark:border-gray-700 bg-white dark:bg-gray-800 overflow-y-auto',
        selectedArticle ? 'hidden md:block md:w-96' : 'w-full md:w-96'
      )} ref={articleListRef}>
        {/* Toolbar */}
        <div className="sticky top-0 bg-white dark:bg-gray-800 border-b dark:border-gray-700 p-3 space-y-2">
          {/* Search Bar */}
          <form onSubmit={handleSearch} className="flex gap-2">
            <div className="flex-1 relative">
              <input
                type="text"
                placeholder="搜索文章..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-8 pr-8 py-1.5 text-sm border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-1 focus:ring-primary-500"
              />
              <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              {searchQuery && (
                <button
                  type="button"
                  onClick={clearSearch}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>
            <button
              type="submit"
              disabled={!searchQuery.trim()}
              className="px-3 py-1.5 text-sm bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50"
            >
              搜索
            </button>
          </form>
          
          {/* Actions Bar */}
          <div className="flex items-center gap-2 flex-wrap">
            <div className="flex items-center gap-1">
              <button
                onClick={() => {
                  if (feedId) {
                    refreshFeedMutation.mutate(parseInt(feedId))
                  } else if (categoryId) {
                    refreshAllMutation.mutate(parseInt(categoryId))
                  } else if (!isFavorite) {
                    refreshAllMutation.mutate(null)
                  }
                }}
                disabled={refreshFeedMutation.isPending || refreshAllMutation.isPending || isFavorite}
                className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded disabled:opacity-50 dark:text-gray-300"
                title={feedId ? "同步订阅源" : categoryId ? "同步该分类所有订阅" : "同步所有订阅"}
              >
                <RefreshCw className={clsx("w-4 h-4", (refreshFeedMutation.isPending || refreshAllMutation.isPending) && "animate-spin")} />
              </button>
              <button
                onClick={() => markAllReadMutation.mutate()}
                disabled={markAllReadMutation.isPending}
                className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded dark:text-gray-300"
                title="全部标记已读"
              >
                <Check className="w-4 h-4" />
              </button>
            </div>
            
            {/* Sort Controls */}
            {!isSearching && (
              <>
                <div className="flex items-center gap-1">
                  <select
                    value={sortBy}
                    onChange={(e) => { setSortBy(e.target.value as typeof sortBy); setCurrentPage(1) }}
                    className="text-xs border dark:border-gray-600 rounded px-2 py-1 bg-white dark:bg-gray-700 dark:text-gray-200"
                  >
                    <option value="published_at">发布时间</option>
                    <option value="created_at">抓取时间</option>
                    <option value="title">标题</option>
                  </select>
                  <button
                    onClick={toggleSortOrder}
                    className="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded dark:text-gray-300"
                    title={sortOrder === 'desc' ? '降序' : '升序'}
                  >
                    {sortOrder === 'desc' ? <SortDesc className="w-4 h-4" /> : <SortAsc className="w-4 h-4" />}
                  </button>
                </div>
                
                {/* Date Filter */}
                <div className="flex items-center gap-1 relative">
                  <button
                    onClick={() => { setDateFilter(dateFilter === 'today' ? 'all' : 'today'); setCurrentPage(1) }}
                    className={clsx(
                      'px-2 py-1 text-xs rounded transition-colors whitespace-nowrap',
                      dateFilter === 'today' 
                        ? 'bg-primary-600 text-white' 
                        : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                    )}
                  >
                    今天
                  </button>
                  <button
                    onClick={() => { setDateFilter(dateFilter === 'yesterday' ? 'all' : 'yesterday'); setCurrentPage(1) }}
                    className={clsx(
                      'px-2 py-1 text-xs rounded transition-colors whitespace-nowrap',
                      dateFilter === 'yesterday' 
                        ? 'bg-primary-600 text-white' 
                        : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                    )}
                  >
                    昨天
                  </button>
                  <button
                    onClick={() => setShowDatePicker(!showDatePicker)}
                    className={clsx(
                      'p-1.5 rounded transition-colors',
                      dateFilter === 'custom' 
                        ? 'bg-primary-600 text-white' 
                        : 'hover:bg-gray-100 dark:hover:bg-gray-700 dark:text-gray-300'
                    )}
                    title="自定义日期"
                  >
                    <Calendar className="w-4 h-4" />
                  </button>
                  
                  {/* Date Picker Dropdown */}
                  {showDatePicker && (
                    <div className="absolute top-full right-0 mt-1 p-3 bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg shadow-lg z-10 min-w-[200px]">
                      <div className="space-y-2">
                        <div>
                          <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">开始日期</label>
                          <input
                            type="date"
                            value={customDateStart}
                            onChange={(e) => setCustomDateStart(e.target.value)}
                            className="w-full px-2 py-1 text-sm border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white"
                          />
                        </div>
                        <div>
                          <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">结束日期</label>
                          <input
                            type="date"
                            value={customDateEnd}
                            onChange={(e) => setCustomDateEnd(e.target.value)}
                            className="w-full px-2 py-1 text-sm border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white"
                          />
                        </div>
                        <div className="flex gap-2 pt-1">
                          <button
                            onClick={() => {
                              if (customDateStart) {
                                setDateFilter('custom')
                                setCurrentPage(1)
                              }
                              setShowDatePicker(false)
                            }}
                            disabled={!customDateStart}
                            className="flex-1 px-2 py-1 text-xs bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50"
                          >
                            确定
                          </button>
                          <button
                            onClick={() => setShowDatePicker(false)}
                            className="px-2 py-1 text-xs border dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-700 dark:text-gray-300"
                          >
                            取消
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </>
            )}
            
            <span className="text-sm text-gray-500 dark:text-gray-400 ml-auto">
              {isSearching && <span className="text-primary-600 dark:text-primary-400 mr-1">搜索结果:</span>}
              {currentData?.total || 0} 篇文章
            </span>
          </div>
        </div>

        {/* List */}
        {loading ? (
          <div className="p-4 text-center text-gray-500 dark:text-gray-400">加载中...</div>
        ) : articles.length === 0 ? (
          <div className="p-4 text-center text-gray-500 dark:text-gray-400">暂无文章</div>
        ) : (
          <>
            <div className="divide-y dark:divide-gray-700">
              {articles.map((article) => (
                <div
                  key={article.id}
                  className={clsx(
                    'p-4 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors',
                    selectedArticle?.id === article.id && 'bg-primary-50 dark:bg-primary-900/30',
                    !article.is_read && 'bg-white dark:bg-gray-800',
                    article.is_read && 'bg-gray-50 dark:bg-gray-800/50'
                  )}
                >
                  <div className="flex items-start gap-2">
                    <div 
                      className="flex-1 min-w-0 cursor-pointer"
                      onClick={() => handleSelectArticle(article)}
                    >
                      <div className="flex items-center gap-2">
                        <h3 className={clsx(
                          'text-sm truncate flex-1',
                          !article.is_read ? 'font-semibold text-gray-900 dark:text-white' : 'text-gray-600 dark:text-gray-400'
                        )}>
                          {article.title}
                        </h3>
                      </div>
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 line-clamp-2">
                        {stripHtml(article.summary || article.content)?.slice(0, 150)}
                      </p>
                      <div className="flex items-center gap-2 mt-2 text-xs text-gray-400 dark:text-gray-500">
                        <span>{new Date(article.published_at).toLocaleString('zh-CN', { 
                          year: 'numeric', 
                          month: '2-digit', 
                          day: '2-digit',
                          hour: '2-digit',
                          minute: '2-digit'
                        })}</span>
                        {article.feed_title && <span className="truncate max-w-[120px]" title={article.feed_title}>· {article.feed_title}</span>}
                        {article.author && <span>· {article.author}</span>}
                      </div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        toggleFavoriteMutation.mutate(article.id)
                      }}
                      className="p-1.5 hover:bg-gray-200 dark:hover:bg-gray-600 rounded flex-shrink-0"
                      title={article.is_favorite ? '取消收藏' : '收藏'}
                    >
                      <Star className={clsx(
                        'w-4 h-4',
                        article.is_favorite ? 'text-yellow-500 fill-yellow-500' : 'text-gray-300 dark:text-gray-500 hover:text-yellow-400'
                      )} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
            
            {/* Pagination */}
            {totalPages > 1 && (
              <div className="sticky bottom-0 bg-white dark:bg-gray-800 border-t dark:border-gray-700 p-3 flex items-center justify-center gap-2">
                <button
                  onClick={() => goToPage(1)}
                  disabled={page === 1}
                  className="px-2 py-1 text-xs border dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed dark:text-gray-300"
                >
                  首页
                </button>
                <button
                  onClick={() => goToPage(page - 1)}
                  disabled={page === 1}
                  className="p-1 border dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed dark:text-gray-300"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <span className="text-sm text-gray-600 dark:text-gray-400 px-2">
                  {page} / {totalPages}
                </span>
                <button
                  onClick={() => goToPage(page + 1)}
                  disabled={page === totalPages}
                  className="p-1 border dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed dark:text-gray-300"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
                <button
                  onClick={() => goToPage(totalPages)}
                  disabled={page === totalPages}
                  className="px-2 py-1 text-xs border dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed dark:text-gray-300"
                >
                  末页
                </button>
              </div>
            )}
          </>
        )}
      </div>


      {/* Article Detail */}
      <div className={clsx(
        'flex-1 overflow-y-auto bg-white dark:bg-gray-800',
        selectedArticle ? 'block' : 'hidden md:block'
      )}>
        {selectedArticle ? (
          <>
            <div className="sticky top-0 bg-white dark:bg-gray-800 border-b dark:border-gray-700 p-3 flex items-center gap-2">
                <button
                  onClick={() => setSelectedArticle(null)}
                  className="md:hidden p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded dark:text-gray-200"
                >
                  ← 返回
                </button>
                <div className="ml-auto flex items-center gap-1">
                  <button
                    onClick={() => translateMutation.mutate(selectedArticle.id)}
                    disabled={translateMutation.isPending}
                    className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded text-purple-600 dark:text-purple-400 disabled:opacity-50"
                    title="翻译"
                  >
                    {translateMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Languages className="w-4 h-4" />}
                  </button>
                  <button
                    onClick={() => summarizeMutation.mutate(selectedArticle.id)}
                    disabled={summarizeMutation.isPending}
                    className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded text-green-600 dark:text-green-400 disabled:opacity-50"
                    title="AI 整理"
                  >
                    {summarizeMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
                  </button>
                  {selectedArticle.link && (
                    <a
                      href={selectedArticle.link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded dark:text-gray-300"
                      title="打开原文"
                    >
                      <ExternalLink className="w-4 h-4" />
                    </a>
                  )}
                </div>
            </div>
            <article className="p-6 max-w-3xl mx-auto">
                {(() => {
                  const translatedData = parseTranslation(selectedArticle.translation)
                  const showingTranslation = selectedArticle.translation && showTranslation
                  
                  return (
                    <>
                      <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                        {showingTranslation && translatedData.title ? translatedData.title : selectedArticle.title}
                      </h1>
                      <div className="flex items-center gap-4 text-sm text-gray-500 dark:text-gray-400 mb-6">
                        <span>{new Date(selectedArticle.published_at).toLocaleString()}</span>
                        {selectedArticle.author && <span>作者: {selectedArticle.author}</span>}
                      </div>
                      {selectedArticle.summary && (
                        <div className="mb-6 p-4 bg-green-50 dark:bg-green-900/30 rounded-lg">
                          <h3 className="text-sm font-semibold text-green-700 dark:text-green-400 mb-2">AI 整理</h3>
                          <div className="text-gray-700 dark:text-gray-300 prose prose-sm dark:prose-invert max-w-none whitespace-pre-wrap">
                            {selectedArticle.summary}
                          </div>
                        </div>
                      )}
                      {selectedArticle.translation && (
                        <div className="mb-4 flex gap-2">
                          <button
                            onClick={() => setShowTranslation(true)}
                            className={clsx(
                              'px-3 py-1 text-sm rounded',
                              showTranslation ? 'bg-primary-600 text-white' : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600'
                            )}
                          >
                            译文
                          </button>
                          <button
                            onClick={() => setShowTranslation(false)}
                            className={clsx(
                              'px-3 py-1 text-sm rounded',
                              !showTranslation ? 'bg-primary-600 text-white' : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600'
                            )}
                          >
                            原文
                          </button>
                        </div>
                      )}
                      {showingTranslation ? (
                        <div
                          className="prose prose-sm dark:prose-invert max-w-none dark:text-gray-200"
                          dangerouslySetInnerHTML={{
                            __html: translatedData.content
                          }}
                        />
                      ) : (
                        <div
                          className="prose prose-sm dark:prose-invert max-w-none dark:text-gray-200"
                          dangerouslySetInnerHTML={{
                            __html: selectedArticle.full_content || selectedArticle.content || ''
                          }}
                        />
                      )}
                    </>
                  )
                })()}
            </article>
          </>
        ) : (
          <div className="h-full flex items-center justify-center p-8 text-center">
            <div>
              <FileText className="w-12 h-12 mx-auto mb-3 text-gray-300 dark:text-gray-600" />
              <h2 className="text-base font-medium text-gray-700 dark:text-gray-200">选择一篇文章</h2>
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">左侧列表会保持可见，内容将在这里打开</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
