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

  // 获取注册状态和公开设置
  const { data: regStatus } = useQuery({
    queryKey: ['registration-status'],
    queryFn: async () => {
      const response = await api.get<{ allow_registration: boolean; has_users: boolean; site_name: string }>('/system/registration-status')
      return response.data
    },
  })

  // 获取 OAuth 状态
  const { data: oauthStatus } = useQuery({
    queryKey: ['oauth-status'],
    queryFn: async () => {
      const response = await api.get<{ linuxdo_enabled: boolean; linuxdo_auth_url?: string }>('/auth/status')
      return response.data
    },
  })

  // 处理 OAuth 回调
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const oauthSuccess = params.get('oauth_success')
    const accessToken = params.get('access_token')
    const refreshToken = params.get('refresh_token')
    const oauthError = params.get('error')
    
    if (oauthSuccess === 'true' && accessToken && refreshToken) {
      // OAuth 登录成功
      api.get('/auth/me', { headers: { Authorization: `Bearer ${accessToken}` } })
        .then(response => {
          setAuth(response.data, accessToken, refreshToken)
          navigate('/')
        })
        .catch(() => {
          setError('OAuth 登录失败，请重试')
        })
      // 清除 URL 参数
      window.history.replaceState({}, '', window.location.pathname)
    } else if (oauthError) {
      const message = params.get('message')
      // 转换错误消息为中文
      const errorMessages: Record<string, string> = {
        'registration_disabled': '注册已关闭，仅允许已注册用户通过 OAuth 登录',
        'oauth_error': 'OAuth 认证失败',
        'missing_params': '缺少必要参数',
        'invalid_state': '无效的状态参数，请重试',
        'not_configured': 'OAuth 未配置',
        'invalid_config': 'OAuth 配置无效',
        'token_exchange_failed': '获取令牌失败',
        'no_access_token': '未获取到访问令牌',
        'userinfo_failed': '获取用户信息失败',
        'no_user_id': '未获取到用户ID',
      }
      const displayMessage = message ? (errorMessages[message] || message) : oauthError
      setError(`OAuth 登录失败: ${displayMessage}`)
      window.history.replaceState({}, '', window.location.pathname)
    }
  }, [navigate, setAuth])

  useEffect(() => {
    if (regStatus?.site_name) {
      setSiteName(regStatus.site_name)
    }
  }, [regStatus?.site_name, setSiteName])

  // 是否允许注册（未开启注册但没有用户时也允许，用于创建首个管理员）
  const allowRegister = regStatus?.allow_registration || regStatus?.has_users === false

  const loginMutation = useMutation({
    mutationFn: async (data: LoginRequest) => {
      const response = await api.post<AuthResponse>('/auth/login', data)
      return response.data
    },
    onSuccess: async (data) => {
      // 清除旧用户的缓存数据
      const { queryClient } = await import('@/main')
      queryClient.clear()
      
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

          {/* OAuth 登录 */}
          {oauthStatus?.linuxdo_enabled && (
            <div className="mt-6">
              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-gray-200 dark:border-gray-600"></div>
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className="px-2 bg-white dark:bg-gray-800 text-gray-500 dark:text-gray-400">或</span>
                </div>
              </div>
              <button
                type="button"
                onClick={() => {
                  if (oauthStatus?.linuxdo_auth_url) {
                    window.location.href = oauthStatus.linuxdo_auth_url
                  } else {
                    window.location.href = '/api/v1/auth/linuxdo/login'
                  }
                }}
                className="mt-4 w-full py-3 px-4 bg-[#f0b90b] hover:bg-[#d9a60a] text-black font-medium rounded-xl shadow-lg hover:shadow-xl focus:outline-none focus:ring-2 focus:ring-[#f0b90b] focus:ring-offset-2 transition-all duration-200 flex items-center justify-center gap-2"
              >
                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/>
                </svg>
                使用 Linux.do 登录
              </button>
            </div>
          )}

          {allowRegister && (
            <div className="mt-6 text-center">
              <p className="text-gray-600 dark:text-gray-400">
                还没有账户？{' '}
                <Link to="/register" className="text-primary-600 dark:text-primary-400 hover:text-primary-700 font-medium">
                  立即注册
                </Link>
              </p>
            </div>
          )}
        </div>

        {/* 底部装饰 */}
        <p className="mt-8 text-center text-sm text-gray-500 dark:text-gray-500">
          安全登录 · 数据加密传输
        </p>
      </div>
    </div>
  )
}
