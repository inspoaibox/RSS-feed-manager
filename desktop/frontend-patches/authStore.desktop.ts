/**
 * Desktop version auth store - No authentication
 * Replace frontend/src/stores/authStore.ts with this file for desktop build
 */
import { create } from 'zustand'

interface User {
  id: number
  username: string
  email: string
  is_admin: boolean
}

interface AuthState {
  isAuthenticated: boolean
  user: User | null
  accessToken: string | null
  refreshToken: string | null
  setAuth: (user: User, accessToken: string, refreshToken: string) => void
  clearAuth: () => void
  updateTokens: (accessToken: string, refreshToken: string) => void
}

// Desktop mode: Always authenticated as default user
export const useAuthStore = create<AuthState>(() => ({
  isAuthenticated: true,
  user: {
    id: 1,
    username: 'Desktop User',
    email: 'desktop@local',
    is_admin: true,
  },
  accessToken: 'desktop-mode-no-token-needed',
  refreshToken: 'desktop-mode-no-token-needed',
  setAuth: () => {
    // No-op in desktop mode
  },
  clearAuth: () => {
    // No-op in desktop mode
  },
  updateTokens: () => {
    // No-op in desktop mode
  },
}))
