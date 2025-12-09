import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface SiteState {
  siteName: string
  setSiteName: (name: string) => void
}

export const useSiteStore = create<SiteState>()(
  persist(
    (set) => ({
      siteName: 'RSS 管理器',
      setSiteName: (name: string) => set({ siteName: name }),
    }),
    {
      name: 'site-storage',
    }
  )
)
