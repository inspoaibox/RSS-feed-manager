import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Search, Sparkles, Clock, X, ExternalLink, Loader2, Database, RefreshCw } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import {
  analyzeContent,
  getQueryHistory,
  deleteQueryHistory,
  getEmbeddingStatus,
  generateEmbeddings,
  type AnalyzeResponse,
  type ArticleResult,
} from '@/services/api'

export default function AIAnalysisPage() {
  const [query, setQuery] = useState('')
  const [result, setResult] = useState<AnalyzeResponse | null>(null)
  const queryClient = useQueryClient()

  // 获取查询历史
  const { data: historyData } = useQuery({
    queryKey: ['queryHistory'],
    queryFn: getQueryHistory,
  })

  // 获取 embedding 状态
  const { data: embeddingStatus } = useQuery({
    queryKey: ['embeddingStatus'],
    queryFn: getEmbeddingStatus,
  })

  // 分析 mutation
  const analyzeMutation = useMutation({
    mutationFn: analyzeContent,
    onSuccess: (data) => {
      setResult(data)
      queryClient.invalidateQueries({ queryKey: ['queryHistory'] })
    },
  })

  // 删除历史 mutation
  const deleteMutation = useMutation({
    mutationFn: deleteQueryHistory,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['queryHistory'] })
    },
  })

  // 生成 embedding mutation
  const generateMutation = useMutation({
    mutationFn: () => generateEmbeddings(100),
    onSuccess: () => {
      // 延迟刷新状态，给任务一些执行时间
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ['embeddingStatus'] })
      }, 3000)
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (query.trim()) {
      analyzeMutation.mutate({ query: query.trim() })
    }
  }

  const handleHistoryClick = (historyQuery: string) => {
    setQuery(historyQuery)
    analyzeMutation.mutate({ query: historyQuery })
  }


  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      {/* Embedding 状态卡片 */}
      {embeddingStatus && (
        <div className="bg-gradient-to-r from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20 rounded-lg p-4 border border-green-200 dark:border-green-800">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Database className="w-5 h-5 text-green-600 dark:text-green-400" />
              <div>
                <div className="text-sm font-medium text-green-800 dark:text-green-300">
                  语义搜索索引
                </div>
                <div className="text-xs text-green-600 dark:text-green-400">
                  {embeddingStatus.with_embedding} / {embeddingStatus.total} 篇文章已索引 ({embeddingStatus.percentage}%)
                </div>
              </div>
            </div>
            {embeddingStatus.without_embedding > 0 && (
              <button
                onClick={() => generateMutation.mutate()}
                disabled={generateMutation.isPending}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
              >
                {generateMutation.isPending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <RefreshCw className="w-4 h-4" />
                )}
                生成索引
              </button>
            )}
          </div>
          {generateMutation.isSuccess && (
            <div className="mt-2 text-xs text-green-600 dark:text-green-400">
              ✓ 任务已启动，正在后台生成索引...
            </div>
          )}
        </div>
      )}

      {/* 搜索框 */}
      <form onSubmit={handleSubmit} className="relative">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="输入你想了解的话题，如：Python 相关的技术文章"
              className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          <button
            type="submit"
            disabled={!query.trim() || analyzeMutation.isPending}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {analyzeMutation.isPending ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Sparkles className="w-5 h-5" />
            )}
            分析
          </button>
        </div>
      </form>

      {/* 查询历史 */}
      {historyData?.queries && historyData.queries.length > 0 && (
        <div className="bg-gray-50 rounded-lg p-4">
          <div className="flex items-center gap-2 text-gray-600 mb-3">
            <Clock className="w-4 h-4" />
            <span className="text-sm font-medium">最近查询</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {historyData.queries.map((item) => (
              <div
                key={item.id}
                className="flex items-center gap-1 bg-white px-3 py-1.5 rounded-full border border-gray-200 hover:border-blue-300 cursor-pointer group"
              >
                <span
                  onClick={() => handleHistoryClick(item.query)}
                  className="text-sm text-gray-700 hover:text-blue-600"
                >
                  {item.query}
                </span>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    deleteMutation.mutate(item.id)
                  }}
                  className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}


      {/* 加载状态 */}
      {analyzeMutation.isPending && (
        <div className="flex items-center justify-center py-12">
          <div className="flex items-center gap-3 text-gray-500">
            <Loader2 className="w-6 h-6 animate-spin" />
            <span>正在分析中，请稍候...</span>
          </div>
        </div>
      )}

      {/* 错误提示 */}
      {analyzeMutation.isError && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
          分析失败，请稍后重试
        </div>
      )}

      {/* 分析结果 */}
      {result && !analyzeMutation.isPending && (
        <div className="space-y-6">
          {/* AI 分析卡片 */}
          {result.analysis && (
            <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-lg p-6 border border-blue-100">
              <div className="flex items-center gap-2 text-blue-700 mb-4">
                <Sparkles className="w-5 h-5" />
                <span className="font-medium">AI 分析结果</span>
                <span className="text-xs text-blue-500 bg-blue-100 px-2 py-0.5 rounded">
                  {result.search_type === 'semantic' ? '语义搜索' : '关键词搜索'}
                </span>
              </div>
              <div className="prose prose-blue max-w-none">
                <ReactMarkdown>{result.analysis}</ReactMarkdown>
              </div>
            </div>
          )}

          {/* 相关文章列表 */}
          <div>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-medium text-gray-900">
                相关文章 ({result.total} 篇)
              </h3>
            </div>

            {result.articles.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                未找到相关文章，请尝试其他关键词
              </div>
            ) : (
              <div className="space-y-4">
                {result.articles.map((article) => (
                  <ArticleCard key={article.id} article={article} />
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}


// 文章卡片组件
function ArticleCard({ article }: { article: ArticleResult }) {
  const relevancePercent = Math.round(article.relevance_score * 100)

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <h4 className="font-medium text-gray-900 mb-1 line-clamp-2">
            {article.link ? (
              <a
                href={article.link}
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-blue-600 flex items-center gap-1"
              >
                {article.title}
                <ExternalLink className="w-3 h-3 flex-shrink-0" />
              </a>
            ) : (
              article.title
            )}
          </h4>
          <div className="flex items-center gap-3 text-sm text-gray-500 mb-2">
            <span className="truncate">{article.feed_title}</span>
            {article.published_at && (
              <>
                <span>•</span>
                <span>{new Date(article.published_at).toLocaleDateString('zh-CN')}</span>
              </>
            )}
          </div>
          <p className="text-sm text-gray-600 line-clamp-2">{article.snippet}</p>
        </div>
        <div className="flex-shrink-0">
          <div
            className={`px-2 py-1 rounded text-xs font-medium ${
              relevancePercent >= 80
                ? 'bg-green-100 text-green-700'
                : relevancePercent >= 60
                ? 'bg-yellow-100 text-yellow-700'
                : 'bg-gray-100 text-gray-600'
            }`}
          >
            {relevancePercent}%
          </div>
        </div>
      </div>
    </div>
  )
}
