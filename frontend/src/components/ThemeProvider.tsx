import { useEffect } from 'react'
import { useThemeStore } from '@/stores/themeStore'

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const { mode, color } = useThemeStore()

  useEffect(() => {
    const root = document.documentElement
    
    // Apply dark mode
    if (mode === 'dark') {
      root.classList.add('dark')
    } else {
      root.classList.remove('dark')
    }
    
    // Apply color theme
    root.setAttribute('data-theme', color)
  }, [mode, color])

  return <>{children}</>
}
