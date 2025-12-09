import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Rss, User, Mail, Lock, ShieldCheck } from 'lucide-react'
import { useSiteStore } from '@/stores/siteStore'
import api from '@/services/api'
import type { RegisterRequest } from '@/types'

export default function RegisterPage() {
  const navigate = useNavigate()
  const { siteName, setSiteName } = useSiteStore()
  const [formData, setFormData] = useState<RegisterRequest>({
    username: '',
    email: '',
    password: '',
  })
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')

  const { data: regStatus, isLoading: checkingStatus } = useQuery({
    queryKey: ['registration-status'],
    queryFn: async () => {
      const response = await api.get<{ allow_registration: boolean; has_users: boolean; site_name: string }>('/system/registration-status')
      return response.data
    },
  })

  useEffect(() => {
    if (regStatus?.site_name) {
      setSiteName(regStatus.site_name)
    }
  }, [regStatus?.site_name, setSiteName])

  // 如果注册关闭且已有用户，重定向到登录页
  useEffect(() => {
    if (regStatus && !regStatus.allow_registration && regStatus.has_users) {
      navigate('/login', { replace: true })
    }
  }, [regStatus, navigate])

  const registerMutation = useMutation({
    mutationFn: async (data: RegisterRequest) => {
      const response = await api.post('/auth/register', data)
      return response.data
    },
    onSuccess: () => {
      navigate('/login', { state: { message: '注册成功，请登录' } })
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      if (Array.isArray(detail)) {
        setError(detail.map((d: any) => d.msg).join(', '))
      } else {
        setError(detail || '注册失败，请重试')
      }
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    
    if (formData.password !== confirmPassword) {
      setError('两次输入的密码不一致')
      return
    }
    
    if (formData.password.length < 6) {
      setError('密码长度至少为6位')
      return
    }
    
    registerMutation.mutate(formData)
  }

  const isFirstUser = regStatus?.has_users === false

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
            {isFirstUser ? <ShieldCheck className="w-8 h-8 text-white" /> : <Rss className="w-8 h-8 text-white" />}
          </div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">{siteName}</h1>
          <p className="mt-2 text-gray-600 dark:text-gray-400">
            {isFirstUser ? '创建管理员账户以开始使用' : '创建账户，开始订阅之旅'}
          </p>
        </div>

        {/* 注册卡片 */}
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl shadow-gray-200/50 dark:shadow-none border border-gray-100 dark:border-gray-700 p-8">
          {isFirstUser && (
            <div className="mb-6 p-4 bg-primary-50 dark:bg-primary-900/20 rounded-xl border border-primary-100 dark:border-primary-800">
              <p className="text-sm text-primary-700 dark:text-primary-300 flex items-center gap-2">
                <ShieldCheck className="w-4 h-4" />
                首次使用，此账户将成为管理员
              </p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
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
                <label htmlFor="email" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  邮箱
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <Mail className="h-5 w-5 text-gray-400" />
                  </div>
                  <input
                    id="email"
                    type="email"
                    required
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    className="block w-full pl-10 pr-4 py-3 border border-gray-200 dark:border-gray-600 rounded-xl bg-gray-50 dark:bg-gray-700/50 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all"
                    placeholder="请输入邮箱地址"
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
                    placeholder="请输入密码（至少6位）"
                  />
                </div>
              </div>

              <div>
                <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  确认密码
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <Lock className="h-5 w-5 text-gray-400" />
                  </div>
                  <input
                    id="confirmPassword"
                    type="password"
                    required
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="block w-full pl-10 pr-4 py-3 border border-gray-200 dark:border-gray-600 rounded-xl bg-gray-50 dark:bg-gray-700/50 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all"
                    placeholder="请再次输入密码"
                  />
                </div>
              </div>
            </div>

            <button
              type="submit"
              disabled={registerMutation.isPending || checkingStatus || (regStatus && !regStatus.allow_registration)}
              className="w-full py-3 px-4 bg-primary-600 hover:bg-primary-700 text-white font-medium rounded-xl shadow-lg shadow-primary-600/30 hover:shadow-primary-600/40 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
            >
              {checkingStatus ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  检查中...
                </span>
              ) : registerMutation.isPending ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  注册中...
                </span>
              ) : isFirstUser ? '创建管理员账户' : '注册'}
            </button>
          </form>

          <div className="mt-6 text-center">
            <p className="text-gray-600 dark:text-gray-400">
              已有账户？{' '}
              <Link to="/login" className="text-primary-600 dark:text-primary-400 hover:text-primary-700 font-medium">
                立即登录
              </Link>
            </p>
          </div>
        </div>

        {/* 底部装饰 */}
        <p className="mt-8 text-center text-sm text-gray-500 dark:text-gray-500">
          安全注册 · 数据加密传输
        </p>
      </div>
    </div>
  )
}
