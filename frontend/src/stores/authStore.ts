import { create } from 'zustand'
import type { User } from '@/types'
import { queryClient } from '@/queryClient'

interface AuthState {
  user: User | null
  accessToken: string | null
  isAuthenticated: boolean
  isInitialized: boolean
  authEpoch: number
  setAuth: (user: User, accessToken: string) => void
  setAccessToken: (accessToken: string | null) => void
  setInitialized: () => void
  clearAuth: () => void
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  accessToken: null,
  isAuthenticated: false,
  isInitialized: false,
  authEpoch: 0,
  setAuth: (user, accessToken) => {
    const currentUser = get().user
    if (currentUser && currentUser.id !== user.id) {
      queryClient.clear()
    }
    set({ user, accessToken, isAuthenticated: true, authEpoch: get().authEpoch + 1 })
  },
  setAccessToken: (accessToken) => set({ accessToken }),
  setInitialized: () => set({ isInitialized: true }),
  clearAuth: () => {
    queryClient.clear()
    set({ user: null, accessToken: null, isAuthenticated: false, authEpoch: get().authEpoch + 1 })
  },
}))
