import { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { useSiteStore } from '@/stores/siteStore'
import { ThemeProvider } from '@/components/ThemeProvider'
import LoginPage from '@/pages/LoginPage'
import RegisterPage from '@/pages/RegisterPage'
import MainLayout from '@/components/layout/MainLayout'
import HomePage from '@/pages/HomePage'
import SettingsPage from '@/pages/SettingsPage'
import { queryClient } from '@/main'

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
  const siteName = useSiteStore((state) => state.siteName)

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

  return (
    <ThemeProvider>
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 transition-colors">
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
          <Route path="settings" element={<SettingsPage />} />
        </Route>

        {/* Catch all */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      </div>
    </ThemeProvider>
  )
}

export default App
