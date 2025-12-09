import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
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

  // Check if registration is allowed
  const { data: regStatus, isLoading: checkingStatus } = useQuery({
    queryKey: ['registration-status'],
    queryFn: async () => {
      const response = await api.get<{ allow_registration: boolean; has_users: boolean; site_name: string }>('/system/registration-status')
      return response.data
    },
  })

  // 更新网站名称
  useEffect(() => {
    if (regStatus?.site_name) {
      setSiteName(regStatus.site_name)
    }
  }, [regStatus?.site_name, setSiteName])

  useEffect(() => {
    if (regStatus && !regStatus.allow_registration) {
      setError('注册功能已关闭，请联系管理员')
    }
  }, [regStatus])

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
      setError('两次输入的密码不一�?)
      return
    }
    
    if (formData.password.length < 6) {
      setError('密码长度至少�?�?)
      return
    }
    
    registerMutation.mutate(formData)
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
      <div className="max-w-md w-full space-y-8 p-8 bg-white dark:bg-gray-800 rounded-lg shadow">
        <div>
          <h2 className="text-center text-3xl font-bold text-gray-900 dark:text-white">
            {siteName}
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600 dark:text-gray-400">创建新账�?/p>
        </div>
        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          {error && (
            <div className="bg-red-50 dark:bg-red-900/30 text-red-500 dark:text-red-400 p-3 rounded text-sm">
              {error}
            </div>
          )}
          <div className="space-y-4">
            <div>
              <label htmlFor="username" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                用户�?
              </label>
              <input
                id="username"
                type="text"
                required
                value={formData.username}
                onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm bg-white dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-primary-500 focus:border-primary-500"
              />
            </div>
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                邮箱
              </label>
              <input
                id="email"
                type="email"
                required
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm bg-white dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-primary-500 focus:border-primary-500"
              />
            </div>
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                密码
              </label>
              <input
                id="password"
                type="password"
                required
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm bg-white dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-primary-500 focus:border-primary-500"
              />
            </div>
            <div>
              <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                确认密码
              </label>
              <input
                id="confirmPassword"
                type="password"
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm bg-white dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-primary-500 focus:border-primary-500"
              />
            </div>
          </div>
          <button
            type="submit"
            disabled={registerMutation.isPending || checkingStatus || (regStatus && !regStatus.allow_registration)}
            className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50"
          >
            {checkingStatus ? '检查中...' : registerMutation.isPending ? '注册�?..' : regStatus?.has_users === false ? '创建管理员账�? : '注册'}
          </button>
          <p className="text-center text-sm text-gray-600 dark:text-gray-400">
            已有账户？{' '}
            <Link to="/login" className="text-primary-600 dark:text-primary-400 hover:text-primary-500">
              立即登录
            </Link>
          </p>
        </form>
      </div>
    </div>
  )
}
