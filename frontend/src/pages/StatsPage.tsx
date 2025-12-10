import { useQuery } from '@tanstack/react-query'
import { BarChart3, TrendingUp, Rss, BookOpen, Star, Clock } from 'lucide-react'
// @ts-ignore
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts'
import api from '@/services/api'

interface OverviewStats {
  total_feeds: number
  active_feeds: number
  total_articles: number
  unread_articles: number
  favorite_articles: number
  today_articles: number
  this_week_articles: number
}

interface DailyArticleCount {
  date: string
  count: number
}

interface FeedActivityStats {
  feed_id: number
  feed_title: string
  article_count: number
  last_article_date: string | null
}

interface CategoryStats {
  category_id: number | null
  category_name: string
  feed_count: number
  article_count: number
}

interface HourlyDistribution {
  hour: number
  count: number
}

interface StatsResponse {
  overview: OverviewStats
  daily_trend: DailyArticleCount[]
  feed_activity: FeedActivityStats[]
  category_distribution: CategoryStats[]
  hourly_distribution: HourlyDistribution[]
}

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16']

export default function StatsPage() {
  const { data: stats, isLoading, error } = useQuery({
    queryKey: ['stats'],
    queryFn: async () => {
      const response = await api.get<StatsResponse>('/stats?days=30')
      return response.data
    },
  })

  if (isLoading) {
    return (
      <div className="p-6 flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  if (error || !stats) {
    return (
      <div className="p-6 text-center text-red-500">
        加载统计数据失败
      </div>
    )
  }

  const { overview, daily_trend, feed_activity, category_distribution, hourly_distribution } = stats

  // Format daily trend for chart (show last 14 days labels)
  const trendData = daily_trend.map((item, index) => ({
    ...item,
    shortDate: index % 3 === 0 ? item.date.slice(5) : ''
  }))

  // Format hourly data
  const hourlyData = hourly_distribution.map(item => ({
    ...item,
    label: `${item.hour}:00`
  }))

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold dark:text-white flex items-center gap-2">
        <BarChart3 className="w-7 h-7" />
        数据统计
      </h1>

      {/* Overview Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4">
        <StatCard
          icon={<Rss className="w-5 h-5" />}
          label="订阅源"
          value={overview.total_feeds}
          subValue={`${overview.active_feeds} 活跃`}
          color="blue"
        />
        <StatCard
          icon={<BookOpen className="w-5 h-5" />}
          label="总文章"
          value={overview.total_articles}
          color="green"
        />
        <StatCard
          icon={<Clock className="w-5 h-5" />}
          label="未读"
          value={overview.unread_articles}
          color="orange"
        />
        <StatCard
          icon={<Star className="w-5 h-5" />}
          label="收藏"
          value={overview.favorite_articles}
          color="yellow"
        />
        <StatCard
          icon={<TrendingUp className="w-5 h-5" />}
          label="今日新增"
          value={overview.today_articles}
          color="purple"
        />
        <StatCard
          icon={<TrendingUp className="w-5 h-5" />}
          label="本周新增"
          value={overview.this_week_articles}
          color="cyan"
        />
        <StatCard
          icon={<BookOpen className="w-5 h-5" />}
          label="阅读率"
          value={`${overview.total_articles > 0 ? Math.round((1 - overview.unread_articles / overview.total_articles) * 100) : 0}%`}
          color="pink"
        />
      </div>

      {/* Daily Trend Chart */}
      <div className="bg-white dark:bg-gray-800 rounded-lg p-4 shadow">
        <h2 className="text-lg font-semibold mb-4 dark:text-white">文章增长趋势（近30天）</h2>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={trendData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis 
                dataKey="date" 
                tick={{ fontSize: 12 }}
                tickFormatter={(value: string) => value.slice(5)}
                interval="preserveStartEnd"
              />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip 
                contentStyle={{ 
                  backgroundColor: 'var(--tooltip-bg, #fff)',
                  border: '1px solid #e5e7eb',
                  borderRadius: '8px'
                }}
                labelFormatter={(label: string) => `日期: ${label}`}
                formatter={(value: number) => [`${value} 篇`, '文章数']}
              />
              <Line 
                type="monotone" 
                dataKey="count" 
                stroke="#3b82f6" 
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Feed Activity */}
        <div className="bg-white dark:bg-gray-800 rounded-lg p-4 shadow">
          <h2 className="text-lg font-semibold mb-4 dark:text-white">订阅源活跃度（近30天）</h2>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={feed_activity.slice(0, 10)} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis type="number" tick={{ fontSize: 12 }} />
                <YAxis 
                  type="category" 
                  dataKey="feed_title" 
                  tick={{ fontSize: 11 }}
                  width={120}
                  tickFormatter={(value: string) => value.length > 15 ? value.slice(0, 15) + '...' : value}
                />
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: 'var(--tooltip-bg, #fff)',
                    border: '1px solid #e5e7eb',
                    borderRadius: '8px'
                  }}
                  formatter={(value: number) => [`${value} 篇`, '文章数']}
                />
                <Bar dataKey="article_count" fill="#10b981" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Category Distribution */}
        <div className="bg-white dark:bg-gray-800 rounded-lg p-4 shadow">
          <h2 className="text-lg font-semibold mb-4 dark:text-white">分类分布</h2>
          <div className="h-72">
            {category_distribution.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={category_distribution}
                    dataKey="article_count"
                    nameKey="category_name"
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    label={({ category_name, percent }: { category_name: string; percent: number }) => 
                      `${category_name} ${(percent * 100).toFixed(0)}%`
                    }
                    labelLine={false}
                  >
                    {category_distribution.map((_, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: 'var(--tooltip-bg, #fff)',
                      border: '1px solid #e5e7eb',
                      borderRadius: '8px'
                    }}
                    formatter={(value: number, name: string) => [`${value} 篇`, name]}
                  />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-gray-500">
                暂无分类数据
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Hourly Distribution */}
      <div className="bg-white dark:bg-gray-800 rounded-lg p-4 shadow">
        <h2 className="text-lg font-semibold mb-4 dark:text-white">文章发布时间分布（24小时）</h2>
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={hourlyData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis 
                dataKey="hour" 
                tick={{ fontSize: 11 }}
                tickFormatter={(value: number) => `${value}时`}
              />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip 
                contentStyle={{ 
                  backgroundColor: 'var(--tooltip-bg, #fff)',
                  border: '1px solid #e5e7eb',
                  borderRadius: '8px'
                }}
                labelFormatter={(label: number) => `${label}:00 - ${label}:59`}
                formatter={(value: number) => [`${value} 篇`, '文章数']}
              />
              <Bar dataKey="count" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Feed Activity Table */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
        <h2 className="text-lg font-semibold p-4 border-b dark:border-gray-700 dark:text-white">
          订阅源详情
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 dark:bg-gray-700">
              <tr>
                <th className="px-4 py-3 text-left text-sm font-medium text-gray-600 dark:text-gray-300">订阅源</th>
                <th className="px-4 py-3 text-right text-sm font-medium text-gray-600 dark:text-gray-300">近30天文章</th>
                <th className="px-4 py-3 text-right text-sm font-medium text-gray-600 dark:text-gray-300">最后更新</th>
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-gray-700">
              {feed_activity.map((feed) => (
                <tr key={feed.feed_id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                  <td className="px-4 py-3 text-sm dark:text-gray-200">{feed.feed_title}</td>
                  <td className="px-4 py-3 text-sm text-right dark:text-gray-200">
                    <span className={`px-2 py-1 rounded ${
                      feed.article_count > 10 ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
                      feed.article_count > 0 ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' :
                      'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400'
                    }`}>
                      {feed.article_count}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-right text-gray-500 dark:text-gray-400">
                    {feed.last_article_date 
                      ? new Date(feed.last_article_date).toLocaleDateString('zh-CN')
                      : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function StatCard({ 
  icon, label, value, subValue, color 
}: { 
  icon: React.ReactNode
  label: string
  value: number | string
  subValue?: string
  color: 'blue' | 'green' | 'orange' | 'yellow' | 'purple' | 'cyan' | 'pink'
}) {
  const colorClasses = {
    blue: 'bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400',
    green: 'bg-green-50 text-green-600 dark:bg-green-900/30 dark:text-green-400',
    orange: 'bg-orange-50 text-orange-600 dark:bg-orange-900/30 dark:text-orange-400',
    yellow: 'bg-yellow-50 text-yellow-600 dark:bg-yellow-900/30 dark:text-yellow-400',
    purple: 'bg-purple-50 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400',
    cyan: 'bg-cyan-50 text-cyan-600 dark:bg-cyan-900/30 dark:text-cyan-400',
    pink: 'bg-pink-50 text-pink-600 dark:bg-pink-900/30 dark:text-pink-400',
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg p-4 shadow">
      <div className={`w-10 h-10 rounded-lg flex items-center justify-center mb-2 ${colorClasses[color]}`}>
        {icon}
      </div>
      <p className="text-2xl font-bold dark:text-white">{value}</p>
      <p className="text-sm text-gray-500 dark:text-gray-400">{label}</p>
      {subValue && (
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">{subValue}</p>
      )}
    </div>
  )
}
