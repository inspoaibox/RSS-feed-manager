import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { RefreshCw, Check, Star, ExternalLink, Search, SortAsc, SortDesc, X, Languages, FileText, Loader2 } from 'lucide-react'
import api from '@/services/api'
import type { Article, PaginatedResponse } from '@/types'
import clsx from 'clsx'

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

export default function HomePage() {
  const [searchParams] = useSearchParams()
  const queryClient = useQueryClient()
  const [selectedArticle, setSelectedArticle] = useState<Article | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [isSearching, setIsSearching] = useState(false)
  const [sortBy, setSortBy] = useState<'published_at' | 'created_at' | 'title'>('published_at')
  const [sortOrder, setSortOrder] = useState<'desc' | 'asc'>('desc')
  const [showTranslation, setShowTranslation] = useState(true)

  const feedId = searchParams.get('feed')
  const categoryId = searchParams.get('category')
  const isFavorite = searchParams.get('favorite') === 'true'

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['articles', feedId, categoryId, isFavorite, sortBy, sortOrder, isSearching ? null : 'list'],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (feedId) params.append('feed_id', feedId)
      if (categoryId) params.append('category_id', categoryId)
      if (isFavorite) params.append('is_favorite', 'true')
      params.append('sort_by', sortBy)
      params.append('sort_order', sortOrder)
      params.append('page_size', '50')
      
      const response = await api.get<PaginatedResponse<Article>>(`/articles?${params}`)
      return response.data
    },
    enabled: !isSearching,
    refetchInterval: 30000, // 每30秒自动刷新
  })

  const { data: searchData, isLoading: isSearchLoading, refetch: refetchSearch } = useQuery({
    queryKey: ['articles-search', searchQuery, feedId, categoryId],
    queryFn: async () => {
      const params = new URLSearchParams()
      params.append('q', searchQuery)
      if (feedId) params.append('feed_id', feedId)
      if (categoryId) params.append('category_id', categoryId)
      params.append('page_size', '50')
      
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
      // Update selected article if it's the one being toggled
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
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['articles'] })
      queryClient.invalidateQueries({ queryKey: ['feeds'] })
      queryClient.invalidateQueries({ queryKey: ['categories'] })
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
      setIsSearching(true)
    }
  }

  const clearSearch = () => {
    setSearchQuery('')
    setIsSearching(false)
  }

  const toggleSortOrder = () => {
    setSortOrder(prev => prev === 'desc' ? 'asc' : 'desc')
  }

  const currentData = isSearching ? searchData : data
  const articles = currentData?.items || []
  const loading = isSearching ? isSearchLoading : isLoading

  return (
    <div className="flex h-full">
      {/* Article List */}
      <div className={clsx(
        'border-r bg-white overflow-y-auto',
        selectedArticle ? 'hidden md:block md:w-96' : 'w-full'
      )}>
        {/* Toolbar */}
        <div className="sticky top-0 bg-white border-b p-3 space-y-2">
          {/* Search Bar */}
          <form onSubmit={handleSearch} className="flex gap-2">
            <div className="flex-1 relative">
              <input
                type="text"
                placeholder="搜索文章..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-8 pr-8 py-1.5 text-sm border rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
              <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              {searchQuery && (
                <button
                  type="button"
                  onClick={clearSearch}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>
            <button
              type="submit"
              disabled={!searchQuery.trim()}
              className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
            >
              搜索
            </button>
          </form>
          
          {/* Actions Bar */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => isSearching ? refetchSearch() : refetch()}
              className="p-2 hover:bg-gray-100 rounded"
              title="刷新"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
            <button
              onClick={() => markAllReadMutation.mutate()}
              disabled={markAllReadMutation.isPending}
              className="p-2 hover:bg-gray-100 rounded"
              title="全部标记已读"
            >
              <Check className="w-4 h-4" />
            </button>
            
            {/* Sort Controls */}
            {!isSearching && (
              <>
                <div className="h-4 w-px bg-gray-300 mx-1" />
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
                  className="text-xs border rounded px-2 py-1"
                >
                  <option value="published_at">发布时间</option>
                  <option value="created_at">抓取时间</option>
                  <option value="title">标题</option>
                </select>
                <button
                  onClick={toggleSortOrder}
                  className="p-1.5 hover:bg-gray-100 rounded"
                  title={sortOrder === 'desc' ? '降序' : '升序'}
                >
                  {sortOrder === 'desc' ? <SortDesc className="w-4 h-4" /> : <SortAsc className="w-4 h-4" />}
                </button>
              </>
            )}
            
            <span className="text-sm text-gray-500 ml-auto">
              {isSearching && <span className="text-blue-600 mr-1">搜索结果:</span>}
              {currentData?.total || 0} 篇文章
            </span>
          </div>
        </div>

        {/* List */}
        {loading ? (
          <div className="p-4 text-center text-gray-500">加载中...</div>
        ) : articles.length === 0 ? (
          <div className="p-4 text-center text-gray-500">暂无文章</div>
        ) : (
          <div className="divide-y">
            {articles.map((article) => (
              <div
                key={article.id}
                className={clsx(
                  'p-4 hover:bg-gray-50 transition-colors',
                  selectedArticle?.id === article.id && 'bg-blue-50',
                  !article.is_read && 'bg-white',
                  article.is_read && 'bg-gray-50'
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
                        !article.is_read ? 'font-semibold text-gray-900' : 'text-gray-600'
                      )}>
                        {article.title}
                      </h3>
                    </div>
                    <p className="text-xs text-gray-500 mt-1 line-clamp-2">
                      {stripHtml(article.summary || article.content)?.slice(0, 150)}
                    </p>
                    <div className="flex items-center gap-2 mt-2 text-xs text-gray-400">
                      <span>{new Date(article.published_at).toLocaleString('zh-CN', { 
                        year: 'numeric', 
                        month: '2-digit', 
                        day: '2-digit',
                        hour: '2-digit',
                        minute: '2-digit'
                      })}</span>
                      {article.author && <span>· {article.author}</span>}
                    </div>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      toggleFavoriteMutation.mutate(article.id)
                    }}
                    className="p-1.5 hover:bg-gray-200 rounded flex-shrink-0"
                    title={article.is_favorite ? '取消收藏' : '收藏'}
                  >
                    <Star className={clsx(
                      'w-4 h-4',
                      article.is_favorite ? 'text-yellow-500 fill-yellow-500' : 'text-gray-300 hover:text-yellow-400'
                    )} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Article Detail */}
      {selectedArticle && (
        <div className="flex-1 overflow-y-auto bg-white">
          <div className="sticky top-0 bg-white border-b p-3 flex items-center gap-2">
            <button
              onClick={() => setSelectedArticle(null)}
              className="md:hidden p-2 hover:bg-gray-100 rounded"
            >
              ← 返回
            </button>
            <div className="ml-auto flex items-center gap-1">
              <button
                onClick={() => translateMutation.mutate(selectedArticle.id)}
                disabled={translateMutation.isPending}
                className="p-2 hover:bg-gray-100 rounded text-purple-600 disabled:opacity-50"
                title="AI 翻译"
              >
                {translateMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Languages className="w-4 h-4" />}
              </button>
              <button
                onClick={() => summarizeMutation.mutate(selectedArticle.id)}
                disabled={summarizeMutation.isPending}
                className="p-2 hover:bg-gray-100 rounded text-green-600 disabled:opacity-50"
                title="AI 整理"
              >
                {summarizeMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
              </button>
              {selectedArticle.link && (
                <a
                  href={selectedArticle.link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="p-2 hover:bg-gray-100 rounded"
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
                  <h1 className="text-2xl font-bold text-gray-900 mb-4">
                    {showingTranslation && translatedData.title ? translatedData.title : selectedArticle.title}
                  </h1>
                  <div className="flex items-center gap-4 text-sm text-gray-500 mb-6">
                    <span>{new Date(selectedArticle.published_at).toLocaleString()}</span>
                    {selectedArticle.author && <span>作者: {selectedArticle.author}</span>}
                  </div>
                  {selectedArticle.summary && (
                    <div className="mb-6 p-4 bg-green-50 rounded-lg">
                      <h3 className="text-sm font-semibold text-green-700 mb-2">AI 整理</h3>
                      <div className="text-gray-700 prose prose-sm max-w-none whitespace-pre-wrap">
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
                          showTranslation ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                        )}
                      >
                        译文
                      </button>
                      <button
                        onClick={() => setShowTranslation(false)}
                        className={clsx(
                          'px-3 py-1 text-sm rounded',
                          !showTranslation ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                        )}
                      >
                        原文
                      </button>
                    </div>
                  )}
                  {showingTranslation ? (
                    <div className="prose prose-sm max-w-none whitespace-pre-wrap">
                      {translatedData.content}
                    </div>
                  ) : (
                    <div
                      className="prose prose-sm max-w-none"
                      dangerouslySetInnerHTML={{
                        __html: selectedArticle.full_content || selectedArticle.content || ''
                      }}
                    />
                  )}
                </>
              )
            })()}
          </article>
        </div>
      )}
    </div>
  )
}
