import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Rss, User, Lock } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import { useSiteStore } from '@/stores/siteStore'
import api from '@/services/api'
import type { AuthResponse, LoginRequest } from '@/types'

export default function LoginPage() {
  const navigate = useNavigate()
  const setAuth = useAuthStore((state) => state.setAuth)
  const { siteName, setSiteName } = useSiteStore()
  const [formData, setFormData] = useState<LoginRequest>({
    username: '',
    password: '',
  })
  const [error, setError] = useState('')

  // 获取公开设置
  const { data: publicSettings } = useQuery({
    queryKey: ['public-settings'],
    queryFn: async () => {
      const response = await api.get<{ site_name: string }>('/system/public-settings')
      return response.data
    },
  })

  useEffect(() => {
    if (publicSettings?.site_name) {
      setSiteName(publicSettings.site_name)
    }
  }, [publicSettings?.site_name, setSiteName])

  const loginMutation = useMutation({
    mutationFn: async (data: LoginRequest) => {
      const response = await api.post<AuthResponse>('/auth/login', data)
      return response.data
    },
    onSuccess: (data) => {
      setAuth(data.user, data.access_token, data.refresh_token)
      navigate('/')
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      if (Array.isArray(detail)) {
        setError(detail.map((d: any) => d.msg).join(', '))
      } else {
        setError(detail || '登录失败，请重试')
      }
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    loginMutation.mutate(formData)
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 via-white to-primary-100 dark:from-gray-900 dark:via-gray-800 dark:to-gray-900 p-4">
      {/* 装饰背景 */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-primary-200 dark:bg-primary-900/20 rounded-full blur-3xl opacity-50"></div>
        <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-primary-300 dark:bg-primary-800/20 rounded-full blur-3xl opacity-50"></div>
      </div>

      <div className="relative max-w-md w-full">
        {/* Logo 和标题 */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-primary-600 rounded-2xl shadow-lg shadow-primary-600/30 mb-4">
            <Rss className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">{siteName}</h1>
          <p className="mt-2 text-gray-600 dark:text-gray-400">欢迎回来，请登录您的账户</p>
        </div>

        {/* 登录卡片 */}
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl shadow-gray-200/50 dark:shadow-none border border-gray-100 dark:border-gray-700 p-8">
          <form onSubmit={handleSubmit} className="space-y-6">
            {error && (
              <div className="bg-red-50 dark:bg-red-900/30 text-red-600 dark:text-red-400 p-4 rounded-xl text-sm flex items-center gap-2">
                <svg className="w-5 h-5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                </svg>
                {error}
              </div>
            )}

            <div className="space-y-4">
              <div>
                <label htmlFor="username" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  用户名
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <User className="h-5 w-5 text-gray-400" />
                  </div>
                  <input
                    id="username"
                    type="text"
                    required
                    value={formData.username}
                    onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                    className="block w-full pl-10 pr-4 py-3 border border-gray-200 dark:border-gray-600 rounded-xl bg-gray-50 dark:bg-gray-700/50 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all"
                    placeholder="请输入用户名"
                  />
                </div>
              </div>

              <div>
                <label htmlFor="password" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  密码
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <Lock className="h-5 w-5 text-gray-400" />
                  </div>
                  <input
                    id="password"
                    type="password"
                    required
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    className="block w-full pl-10 pr-4 py-3 border border-gray-200 dark:border-gray-600 rounded-xl bg-gray-50 dark:bg-gray-700/50 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all"
                    placeholder="请输入密码"
                  />
                </div>
              </div>
            </div>

            <button
              type="submit"
              disabled={loginMutation.isPending}
              className="w-full py-3 px-4 bg-primary-600 hover:bg-primary-700 text-white font-medium rounded-xl shadow-lg shadow-primary-600/30 hover:shadow-primary-600/40 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
            >
              {loginMutation.isPending ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  登录中...
                </span>
              ) : '登录'}
            </button>
          </form>

          <div className="mt-6 text-center">
            <p className="text-gray-600 dark:text-gray-400">
              还没有账户？{' '}
              <Link to="/register" className="text-primary-600 dark:text-primary-400 hover:text-primary-700 font-medium">
                立即注册
              </Link>
            </p>
          </div>
        </div>

        {/* 底部装饰 */}
        <p className="mt-8 text-center text-sm text-gray-500 dark:text-gray-500">
          安全登录 · 数据加密传输
        </p>
      </div>
    </div>
  )
}
