import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User } from '@/types'

interface AuthState {
  user: User | null
  accessToken: string | null
  refreshToken: string | null
  isAuthenticated: boolean
  setAuth: (user: User, accessToken: string, refreshToken: string) => void
  clearAuth: () => void
}

// 清除 React Query 缓存的函数
const clearQueryCache = () => {
  // 动态导入避免循环依赖
  import('@/main').then(({ queryClient }) => {
    queryClient.clear()
  }).catch(() => {
    // 忽略导入错误
  })
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      setAuth: (user, accessToken, refreshToken) => {
        // 如果是不同用户登录，清除缓存
        const currentUser = get().user
        if (currentUser && currentUser.id !== user.id) {
          clearQueryCache()
        }
        set({
          user,
          accessToken,
          refreshToken,
          isAuthenticated: true,
        })
      },
      clearAuth: () => {
        // 登出时清除所有缓存
        clearQueryCache()
        set({
          user: null,
          accessToken: null,
          refreshToken: null,
          isAuthenticated: false,
        })
      },
    }),
    {
      name: 'auth-storage',
    }
  )
)
