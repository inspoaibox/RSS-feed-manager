import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { useAuthStore } from '@/stores/authStore'
import api from '@/services/api'
import type { AuthResponse, LoginRequest } from '@/types'

export default function LoginPage() {
  const navigate = useNavigate()
  const setAuth = useAuthStore((state) => state.setAuth)
  const [formData, setFormData] = useState<LoginRequest>({
    username: '',
    password: '',
  })
  const [error, setError] = useState('')

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
      // Handle validation errors (array) or string error
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
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full space-y-8 p-8 bg-white rounded-lg shadow">
        <div>
          <h2 className="text-center text-3xl font-bold text-gray-900">
            RSS 订阅管理器
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600">登录您的账户</p>
        </div>
        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          {error && (
            <div className="bg-red-50 text-red-500 p-3 rounded text-sm">
              {error}
            </div>
          )}
          <div className="space-y-4">
            <div>
              <label htmlFor="username" className="block text-sm font-medium text-gray-700">
                用户名
              </label>
              <input
                id="username"
                type="text"
                required
                value={formData.username}
                onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700">
                密码
              </label>
              <input
                id="password"
                type="password"
                required
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
          </div>
          <button
            type="submit"
            disabled={loginMutation.isPending}
            className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
          >
            {loginMutation.isPending ? '登录中...' : '登录'}
          </button>
          <p className="text-center text-sm text-gray-600">
            还没有账户？{' '}
            <Link to="/register" className="text-blue-600 hover:text-blue-500">
              立即注册
            </Link>
          </p>
        </form>
      </div>
    </div>
  )
}
