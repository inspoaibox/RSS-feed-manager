import { lazy, Suspense, useEffect } from 'react'
import axios from 'axios'
import { Routes, Route, Navigate } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import { useSiteStore } from '@/stores/siteStore'
import { ThemeProvider } from '@/components/ThemeProvider'
import MainLayout from '@/components/layout/MainLayout'
import api, { refreshAccessToken } from '@/services/api'
import { queryClient } from '@/queryClient'
import type { User } from '@/types'

const LoginPage = lazy(() => import('@/pages/LoginPage'))
const RegisterPage = lazy(() => import('@/pages/RegisterPage'))
const HomePage = lazy(() => import('@/pages/HomePage'))
const SettingsPage = lazy(() => import('@/pages/SettingsPage'))
const StatsPage = lazy(() => import('@/pages/StatsPage'))
const AIAnalysisPage = lazy(() => import('@/pages/AIAnalysisPage'))
const RecommendationsPage = lazy(() => import('@/pages/RecommendationsPage'))

const CACHE_USER_KEY = 'cache-user-id'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  return <>{children}</>
}

function App() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const user = useAuthStore((state) => state.user)
  const isInitialized = useAuthStore((state) => state.isInitialized)
  const setAuth = useAuthStore((state) => state.setAuth)
  const clearAuth = useAuthStore((state) => state.clearAuth)
  const setInitialized = useAuthStore((state) => state.setInitialized)
  const siteName = useSiteStore((state) => state.siteName)

  useEffect(() => {
    let active = true
    localStorage.removeItem('auth-storage')
    const initialize = async () => {
      try {
        const accessToken = await refreshAccessToken()
        const response = await api.get<User>('/auth/me')
        if (active) setAuth(response.data, accessToken)
      } catch (error) {
        if (active) clearAuth()
        if (axios.isAxiosError(error) && error.response?.status !== 401) {
          console.error('Failed to initialize session', error)
        }
      } finally {
        if (active) setInitialized()
      }
    }
    initialize()
    return () => {
      active = false
    }
  }, [clearAuth, setAuth, setInitialized])

  // 检查缓存的用户 ID 是否与当前用户匹配
  useEffect(() => {
    if (user) {
      const cachedUserId = localStorage.getItem(CACHE_USER_KEY)
      const currentUserId = String(user.id)
      
      if (cachedUserId && cachedUserId !== currentUserId) {
        // 用户 ID 不匹配，清除所有缓存
        console.log('User changed, clearing cache...')
        queryClient.clear()
      }
      
      // 更新缓存的用户 ID
      localStorage.setItem(CACHE_USER_KEY, currentUserId)
    } else {
      // 用户登出，清除缓存的用户 ID
      localStorage.removeItem(CACHE_USER_KEY)
    }
  }, [user])

  // 更新页面标题和 PWA 名称
  useEffect(() => {
    document.title = siteName
    // 更新 Apple PWA 标题
    const appleTitleMeta = document.getElementById('apple-mobile-web-app-title')
    if (appleTitleMeta) {
      appleTitleMeta.setAttribute('content', siteName)
    }
  }, [siteName])

  if (!isInitialized) {
    return (
      <div className="min-h-screen grid place-items-center bg-gray-50 dark:bg-gray-900">
        <Loader2 className="h-6 w-6 animate-spin text-primary-600" aria-label="Loading" />
      </div>
    )
  }

  return (
    <ThemeProvider>
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 transition-colors">
        <Suspense fallback={<div className="min-h-screen grid place-items-center"><Loader2 className="h-6 w-6 animate-spin text-primary-600" /></div>}>
        <Routes>
        {/* Public routes */}
        <Route
          path="/login"
          element={isAuthenticated ? <Navigate to="/" replace /> : <LoginPage />}
        />
        <Route
          path="/register"
          element={isAuthenticated ? <Navigate to="/" replace /> : <RegisterPage />}
        />

        {/* Protected routes */}
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <MainLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<HomePage />} />
          <Route path="ai-analysis" element={<AIAnalysisPage />} />
          <Route path="recommendations" element={<RecommendationsPage />} />
          <Route path="stats" element={<StatsPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>

        {/* Catch all */}
        <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </Suspense>
      </div>
    </ThemeProvider>
  )
}

export default App
