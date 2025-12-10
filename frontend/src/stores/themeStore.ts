import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type ThemeMode = 'light' | 'dark'
export type ThemeColor = 'blue' | 'green' | 'purple' | 'orange' | 'rose' | 'cyan' | 'sunset' | 'ocean'

interface ThemeState {
  mode: ThemeMode
  color: ThemeColor
  setMode: (mode: ThemeMode) => void
  setColor: (color: ThemeColor) => void
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set) => ({
      mode: 'light',
      color: 'blue',
      setMode: (mode) => set({ mode }),
      setColor: (color) => set({ color }),
    }),
    {
      name: 'theme-storage',
    }
  )
)

// Theme color definitions - used for display in settings
export const themeColors = {
  blue: {
    primary: 'bg-blue-600',
    primaryHover: 'hover:bg-blue-700',
    primaryText: 'text-blue-600',
    primaryBg: 'bg-blue-100',
    accent: 'bg-blue-500',
  },
  green: {
    primary: 'bg-green-600',
    primaryHover: 'hover:bg-green-700',
    primaryText: 'text-green-600',
    primaryBg: 'bg-green-100',
    accent: 'bg-green-500',
  },
  purple: {
    primary: 'bg-purple-600',
    primaryHover: 'hover:bg-purple-700',
    primaryText: 'text-purple-600',
    primaryBg: 'bg-purple-100',
    accent: 'bg-purple-500',
  },
  orange: {
    primary: 'bg-orange-600',
    primaryHover: 'hover:bg-orange-700',
    primaryText: 'text-orange-600',
    primaryBg: 'bg-orange-100',
    accent: 'bg-orange-500',
  },
  rose: {
    primary: 'bg-rose-600',
    primaryHover: 'hover:bg-rose-700',
    primaryText: 'text-rose-600',
    primaryBg: 'bg-rose-100',
    accent: 'bg-rose-500',
  },
  cyan: {
    primary: 'bg-cyan-600',
    primaryHover: 'hover:bg-cyan-700',
    primaryText: 'text-cyan-600',
    primaryBg: 'bg-cyan-100',
    accent: 'bg-cyan-500',
  },
  sunset: {
    primary: 'bg-orange-600',
    primaryHover: 'hover:bg-orange-700',
    primaryText: 'text-orange-600',
    primaryBg: 'bg-orange-100',
    accent: 'bg-orange-500',
  },
  ocean: {
    primary: 'bg-teal-600',
    primaryHover: 'hover:bg-teal-700',
    primaryText: 'text-teal-600',
    primaryBg: 'bg-teal-100',
    accent: 'bg-teal-500',
  },
}

// Helper function to get current theme colors
export function getThemeColors(color: ThemeColor) {
  return themeColors[color]
}
